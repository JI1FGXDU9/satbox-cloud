"""Durable prediction cache; only calls the framework-independent engine on a miss."""
import hashlib
import json
from satbox_db import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from satbox_orbit import Observer
from satbox_orbit.multiple import predict_multiple


class PassCache:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE IF NOT EXISTS predictions
                (cache_key TEXT PRIMARY KEY, expires REAL NOT NULL, payload TEXT NOT NULL,
                 user_id INTEGER NOT NULL)''')
            columns = {row[1] for row in db.execute('PRAGMA table_info(predictions)')}
            if 'user_id' not in columns:
                db.execute('ALTER TABLE predictions ADD COLUMN user_id INTEGER')
                # Old hashes cannot identify the owner; regenerate disposable cache once.
                db.execute('DELETE FROM predictions')
            db.execute('CREATE INDEX IF NOT EXISTS predictions_user ON predictions(user_id)')

    def get(self, user, config, records, tle_digest, now):
        hours = user['duration_hours']
        signature = dict(version=2, user_id=user['id'], latitude=user['latitude_deg'],
                         longitude=user['longitude_deg'], altitude=user['altitude_m'],
                         hours=hours, tle=tle_digest,
                         satellites=[(r.name, r.line1, r.line2) for r in records],
                         horizon=config['horizon_deg'], minimum=config['min_maxel_deg'])
        key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
        # The separate cache database serializes cache misses across processes.
        # It never locks the account database during orbit computation.
        db = sqlite3.connect(self.path, timeout=120)
        try:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT expires,payload FROM predictions WHERE cache_key=?', (key,)).fetchone()
            hit = bool(row and row[0] > now.timestamp())
            if hit:
                payload = json.loads(row[1])
            else:
                observer = Observer(user['latitude_deg'], user['longitude_deg'], user['altitude_m'])
                # Padding ensures the full rolling window is covered until expiry.
                start = now - timedelta(hours=1)
                result = predict_multiple(records, observer, start,
                                          now + timedelta(hours=hours + 1),
                                          config['horizon_deg'], config['min_maxel_deg'])
                payload = dict(generated=now.isoformat(), errors=list(result.errors),
                               passes=[dict(name=p.satellite_name, aos=p.pass_data.aos.isoformat(),
                                            los=p.pass_data.los.isoformat(), aos_az=p.pass_data.aos_az_deg,
                                            los_az=p.pass_data.los_az_deg,
                                            maximum_at=p.pass_data.maximum_at.isoformat(),
                                            maxel=p.pass_data.maximum_el_deg) for p in result.passes])
                ttl = 60 if result.errors else 1800
                db.execute('DELETE FROM predictions WHERE expires <= ?', (now.timestamp(),))
                db.execute('INSERT OR REPLACE INTO predictions (cache_key,expires,payload,user_id) VALUES (?,?,?,?)',
                           (key, now.timestamp() + ttl, json.dumps(payload), user['id']))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        limit = now + timedelta(hours=hours)
        rows = []
        for saved in payload['passes']:
            aos, los = datetime.fromisoformat(saved['aos']), datetime.fromisoformat(saved['los'])
            if now < los <= limit:
                rows.append(dict(saved, aos=aos, los=los, aos_ms=int(aos.timestamp() * 1000),
                                 los_ms=int(los.timestamp() * 1000), active=aos <= now < los))
        return rows, payload['errors'], datetime.fromisoformat(payload['generated']), hit
