"""SQLite preferences, planning queue and saved Pass details; no notification transport."""
import hashlib
import json
from satbox_db import sqlite3
import secrets
from datetime import timedelta
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from .planning import NotificationPreferences, build_plan


class NotificationStore:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS notification_passes (
                    id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    satellite_name TEXT NOT NULL, aos TEXT NOT NULL, payload TEXT NOT NULL, retained_until TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS notification_pass_lookup ON notification_passes(user_id,satellite_name,aos);
                CREATE TABLE IF NOT EXISTS notification_settings (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    satellites TEXT NOT NULL DEFAULT '[]', min_maxel REAL NOT NULL DEFAULT 10,
                    lead_minutes INTEGER NOT NULL DEFAULT 5, start_minute INTEGER NOT NULL DEFAULT 420,
                    end_minute INTEGER NOT NULL DEFAULT 1440
                );
                CREATE TABLE IF NOT EXISTS notification_queue (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    satellite_name TEXT NOT NULL, aos TEXT NOT NULL, send_at TEXT NOT NULL,
                    maxel REAL NOT NULL, aos_az REAL NOT NULL,
                    PRIMARY KEY (user_id,satellite_name,aos)
                );
                CREATE INDEX IF NOT EXISTS queue_send_at ON notification_queue(send_at);
                CREATE TABLE IF NOT EXISTS notification_catalog_state (
                    id INTEGER PRIMARY KEY CHECK(id=1), digest TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notification_plan_state (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    source_key TEXT NOT NULL, generated_at TEXT NOT NULL
                );
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, user_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM notification_settings WHERE user_id=?', (user_id,)).fetchone()
        if row is None:
            return NotificationPreferences()
        return NotificationPreferences(tuple(json.loads(row['satellites'])), row['min_maxel'],
            row['lead_minutes'], row['start_minute'], row['end_minute'])

    def _save(self, db, user_id, settings):
        db.execute('''INSERT INTO notification_settings VALUES (?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET satellites=excluded.satellites,
            min_maxel=excluded.min_maxel,lead_minutes=excluded.lead_minutes,
            start_minute=excluded.start_minute,end_minute=excluded.end_minute''',
            (user_id, json.dumps(settings.enabled_satellites), settings.min_maxel_deg,
             settings.lead_minutes, settings.start_minute, settings.end_minute))
        self._invalidate(db, user_id)

    def save(self, user_id, settings):
        with self.connect() as db:
            self._save(db, user_id, settings)

    def toggle(self, user_id, name, enabled):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM notification_settings WHERE user_id=?', (user_id,)).fetchone()
            current = NotificationPreferences() if row is None else NotificationPreferences(
                tuple(json.loads(row['satellites'])), row['min_maxel'], row['lead_minutes'], row['start_minute'], row['end_minute'])
            selected = set(current.enabled_satellites)
            selected.add(name) if enabled else selected.discard(name)
            updated = NotificationPreferences(tuple(sorted(selected)), current.min_maxel_deg,
                current.lead_minutes, current.start_minute, current.end_minute)
            self._save(db, user_id, updated)
        return updated

    def _invalidate(self, db, user_id):
        db.execute('DELETE FROM notification_queue WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM notification_plan_state WHERE user_id=?', (user_id,))

    def invalidate(self, user_id):
        with self.connect() as db:
            self._invalidate(db, user_id)

    def refresh(self, user, passes, source, now):
        # Hold the short account transaction while reading settings and building
        # the plan so a concurrent OFF/save cannot restore obsolete queue entries.
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current_user = db.execute('SELECT * FROM users WHERE id=? AND session_token=?',
                                     (user['id'], user['session_token'])).fetchone()
            if current_user is None:
                return [], None
            revision = db.execute('SELECT digest FROM notification_catalog_state WHERE id=1').fetchone()
            if revision and source.get('tle') != revision['digest']:
                return [], None
            profile_fields = ('latitude_deg','longitude_deg','altitude_m','timezone_name','duration_hours')
            if 'satellite_selection' in current_user.keys() and current_user['satellite_selection'] != user.get('satellite_selection'):
                return [], None
            if any(current_user[key] != user[key] for key in profile_fields):
                # An older in-flight page must not rebuild a queue for the previous QTH.
                return [], None
            row = db.execute('SELECT * FROM notification_settings WHERE user_id=?', (user['id'],)).fetchone()
            prefs = NotificationPreferences() if row is None else NotificationPreferences(
                tuple(json.loads(row['satellites'])), row['min_maxel'], row['lead_minutes'], row['start_minute'], row['end_minute'])
            fingerprint = hashlib.sha256(json.dumps(dict(source=source, prefs=asdict(prefs),
                profile=[user[k] for k in profile_fields]),
                sort_keys=True).encode()).hexdigest()
            state = db.execute('SELECT * FROM notification_plan_state WHERE user_id=?', (user['id'],)).fetchone()
            if state is None or state['source_key'] != fingerprint:
                # Persist full engine results for push/details; sender never computes an orbit.
                db.execute('DELETE FROM notification_passes WHERE retained_until < ?', (now.isoformat(),))
                for item in passes:
                    saved = dict(item)
                    for key, value in list(saved.items()):
                        if isinstance(value, datetime): saved[key] = value.isoformat()
                    existing = db.execute('SELECT id,aos FROM notification_passes WHERE user_id=? AND satellite_name=?',
                                          (user['id'],item['name'])).fetchall()
                    # Event refinements on cache refresh must not produce duplicate alerts.
                    identity = next((r['id'] for r in existing if abs((datetime.fromisoformat(r['aos'])-item['aos']).total_seconds()) < 120), secrets.token_hex(16))
                    db.execute('INSERT INTO notification_passes VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET aos=excluded.aos,payload=excluded.payload,retained_until=excluded.retained_until',
                        (identity,user['id'],item['name'],item['aos'].isoformat(),json.dumps(saved),(item['los']+timedelta(days=7)).isoformat()))
                plans = list(build_plan(passes, prefs, user['timezone_name'], now))
                # Preserve an already queued deadline during a concurrent cache refresh.
                # Fresh registrations never receive notifications for past deadlines.
                previous = db.execute('SELECT satellite_name,aos FROM notification_queue WHERE user_id=?',(user['id'],)).fetchall()
                grace = build_plan(passes, prefs, user['timezone_name'], now-timedelta(seconds=120))
                for plan in grace:
                    if plan.send_at < now <= plan.aos and any(r['satellite_name']==plan.satellite_name and abs((datetime.fromisoformat(r['aos'])-plan.aos).total_seconds())<120 for r in previous):
                        plans.append(plan)
                db.execute('DELETE FROM notification_queue WHERE user_id=?', (user['id'],))
                db.executemany('INSERT INTO notification_queue VALUES (?,?,?,?,?,?)',
                    [(user['id'], p.satellite_name, p.aos.isoformat(), p.send_at.isoformat(), p.maxel, p.aos_az) for p in plans])
                db.execute('INSERT OR REPLACE INTO notification_plan_state VALUES (?,?,?)',
                           (user['id'], fingerprint, now.isoformat()))
                generated = now
            else:
                generated = datetime.fromisoformat(state['generated_at'])
            # ISO strings have a consistent UTC offset; numeric comparison retains subseconds.
            rows = db.execute('SELECT * FROM notification_queue WHERE user_id=? ORDER BY send_at,satellite_name', (user['id'],)).fetchall()
            upcoming = []
            for row in rows:
                send_at, aos = datetime.fromisoformat(row['send_at']), datetime.fromisoformat(row['aos'])
                if send_at >= now:
                    upcoming.append(dict(row, send_at=send_at, aos=aos))
        return upcoming, generated
