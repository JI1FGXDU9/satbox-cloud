"""Account persistence; independent of orbital calculations."""
from satbox_db import sqlite3
import secrets
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path


class UserStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, login_id TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, callsign TEXT NOT NULL,
                    latitude_deg REAL NOT NULL, longitude_deg REAL NOT NULL,
                    altitude_m REAL NOT NULL, timezone_name TEXT NOT NULL,
                    grid_locator TEXT NOT NULL, duration_hours INTEGER NOT NULL DEFAULT 24
                );
                CREATE TABLE IF NOT EXISTS login_attempts (
                    attempt_key TEXT PRIMARY KEY, started REAL NOT NULL, failures INTEGER NOT NULL
                );
            ''')
            db.execute('BEGIN IMMEDIATE')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(users)')}
            if 'session_token' not in columns:
                db.execute('ALTER TABLE users ADD COLUMN session_token TEXT')
            if 'satellite_selection' not in columns:
                db.execute('ALTER TABLE users ADD COLUMN satellite_selection TEXT')
            if 'email' not in columns:
                db.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")
            if 'is_admin' not in columns:
                db.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0')
            for row in db.execute('SELECT id FROM users WHERE session_token IS NULL').fetchall():
                db.execute('UPDATE users SET session_token=? WHERE id=?',
                           (secrets.token_hex(32), row['id']))

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

    def by_id(self, user_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            return dict(row) if row else None

    def by_login(self, login_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM users WHERE login_id=?', (login_id,)).fetchone()
            return dict(row) if row else None

    def all_users(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM users ORDER BY login_id')]

    def register(self, login_id, password_hash, profile):
        with self.connect() as db:
            cursor = db.execute('''INSERT INTO users
                (login_id,password_hash,callsign,latitude_deg,longitude_deg,altitude_m,
                 timezone_name,grid_locator,duration_hours,session_token,email) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (login_id, password_hash, *[profile[k] for k in PROFILE_FIELDS], secrets.token_hex(32), profile.get('email', '')))
            return cursor.lastrowid

    def set_admin(self, login_id, enabled, actor_id=None, initial=False):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if actor_id is not None:
                actor = db.execute('SELECT is_admin FROM users WHERE id=?',(actor_id,)).fetchone()
                if not actor or not actor['is_admin']:
                    raise PermissionError('Administrator access required')
            count = db.execute('SELECT COUNT(*) FROM users WHERE is_admin=1').fetchone()[0]
            if initial and count:
                raise ValueError('An administrator already exists')
            target = db.execute('SELECT is_admin FROM users WHERE login_id=?',(login_id,)).fetchone()
            if not target:
                return 0
            if not enabled and target['is_admin'] and count <= 1:
                raise ValueError('Cannot remove the last administrator')
            return db.execute('UPDATE users SET is_admin=? WHERE login_id=?',
                              (int(enabled),login_id)).rowcount

    def select_satellites(self, user_id, names):
        # Selection, notification cleanup and queue invalidation are atomic.
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE users SET satellite_selection=? WHERE id=?',
                       (json.dumps(names),user_id))
            prefs = db.execute('SELECT satellites FROM notification_settings WHERE user_id=?',(user_id,)).fetchone()
            if prefs:
                enabled = [n for n in json.loads(prefs['satellites']) if n in names]
                db.execute('UPDATE notification_settings SET satellites=? WHERE user_id=?',
                           (json.dumps(enabled),user_id))
            db.execute('DELETE FROM notification_queue WHERE user_id=?',(user_id,))
            db.execute('DELETE FROM notification_plan_state WHERE user_id=?',(user_id,))

    def delete_account(self, user_id, cache_path, actor_id=None):
        # Both databases use rollback journals; delete account and cached QTH together.
        with self.connect() as db:
            db.execute('ATTACH DATABASE ? AS pass_cache', (str(cache_path),))
            db.execute('BEGIN IMMEDIATE')
            if actor_id is not None:
                actor = db.execute('SELECT is_admin FROM users WHERE id=?', (actor_id,)).fetchone()
                if not actor or not actor['is_admin']:
                    raise PermissionError('Administrator access required')
            user = db.execute('SELECT login_id,is_admin FROM users WHERE id=?', (user_id,)).fetchone()
            if user is None:
                return
            if actor_id is not None and user['is_admin']:
                raise ValueError('管理者は削除できません。')
            if user['is_admin'] and db.execute('SELECT COUNT(*) FROM users WHERE is_admin=1').fetchone()[0] <= 1:
                raise ValueError('先に別のユーザーを管理者に昇格させてください。最後の管理者は退会できません。')
            db.execute('DELETE FROM pass_cache.predictions WHERE user_id=?', (user_id,))
            db.execute('DELETE FROM login_attempts WHERE attempt_key=?',
                       ('user:' + hashlib.sha256(user['login_id'].encode()).hexdigest(),))
            db.execute('DELETE FROM users WHERE id=?', (user_id,))

    def update(self, user_id, profile):
        # The authenticated ID is supplied by the server, never from a form.
        with self.connect() as db:
            db.execute('''UPDATE users SET callsign=?,latitude_deg=?,longitude_deg=?,
                altitude_m=?,timezone_name=?,grid_locator=?,duration_hours=? WHERE id=?''',
                (*[profile[k] for k in PROFILE_FIELDS], user_id))
            if 'email' in profile:
                db.execute('UPDATE users SET email=? WHERE id=?', (profile['email'], user_id))

    def blocked(self, key, now):
        with self.connect() as db:
            row = db.execute('SELECT * FROM login_attempts WHERE attempt_key=?', (key,)).fetchone()
            return bool(row and now - row['started'] < 900 and row['failures'] >= 10)

    def failed(self, key, now):
        with self.connect() as db:
            db.execute('DELETE FROM login_attempts WHERE started < ?', (now - 900,))
            db.execute('''INSERT INTO login_attempts VALUES (?, ?, 1)
                ON CONFLICT(attempt_key) DO UPDATE SET failures=failures+1''', (key, now))

    def clear_failures(self, key):
        with self.connect() as db:
            db.execute('DELETE FROM login_attempts WHERE attempt_key=?', (key,))


PROFILE_FIELDS = ('callsign', 'latitude_deg', 'longitude_deg', 'altitude_m',
                  'timezone_name', 'grid_locator', 'duration_hours')
