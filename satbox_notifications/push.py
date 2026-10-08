"""Encrypted browser subscriptions and durable delivery; no orbit imports."""
import base64
import hashlib
import json
import math
import os
import secrets
import time
from datetime import timedelta
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from .storage import NotificationStore
from .planning import allowed_at

def validate_subscription(value):
    if not isinstance(value, dict):
        raise ValueError('端末登録データが無効です。')
    endpoint = value.get('endpoint', '')
    if not isinstance(endpoint, str) or len(endpoint) > 4096:
        raise ValueError('通知先が無効です。')
    url = urlsplit(endpoint)
    host = (url.hostname or '').lower()
    # Browser vendor services only: user input must not become arbitrary server requests.
    allowed = host in ('fcm.googleapis.com', 'updates.push.services.mozilla.com', 'updates-autopush.stage.mozaws.net') or host.endswith('.push.apple.com') or host == 'web.push.apple.com' or host.endswith('.notify.windows.com')
    if url.scheme != 'https' or not allowed or url.username or url.password or url.port not in (None, 443) or url.fragment:
        raise ValueError('対応するブラウザーのHTTPS通知先を登録してください。')
    keys = value.get('keys', {})
    if not isinstance(keys, dict):
        raise ValueError('通知鍵が無効です。')
    clean = {}
    for key, size in (('p256dh',65), ('auth',16)):
        raw = keys.get(key, '')
        if not isinstance(raw, str) or len(raw) > 128:
            raise ValueError('通知鍵が無効です。')
        try:
            decoded = base64.b64decode(raw + '=' * (-len(raw) % 4), altchars=b'-_', validate=True)
            if len(decoded) != size:
                raise ValueError()
            if key == 'p256dh':
                ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decoded)
        except (ValueError, TypeError):
            raise ValueError('通知鍵が無効です。') from None
        clean[key] = raw
    return dict(endpoint=endpoint, keys=clean)

def initialize_push(folder, base_url, subject):
    folder = Path(folder)
    url = urlsplit(base_url)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('公開URLはHTTPSのURLで指定してください。')
    if not (subject.startswith('mailto:') or subject.startswith('https://')):
        raise ValueError('連絡先はmailto:メールアドレス、またはHTTPS URLで指定してください。')
    folder.mkdir(parents=True, exist_ok=True)
    for name, content in (
        ('push-encryption.key', Fernet.generate_key()),
        ('vapid-private.pem', ec.generate_private_key(ec.SECP256R1()).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))):
        try:
            fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
    settings = dict(base_url=base_url.rstrip('/'), subject=subject)
    path = folder / 'push-config.json'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(settings, stream)

class PushStore(NotificationStore):
    def __init__(self, folder):
        self.folder = Path(folder)
        super().__init__(self.folder / 'users.sqlite3')
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    endpoint_hash TEXT NOT NULL UNIQUE, encrypted TEXT NOT NULL, label TEXT NOT NULL,
                    created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS push_deliveries (
                    subscription_id TEXT NOT NULL REFERENCES push_subscriptions(id) ON DELETE CASCADE,
                    pass_id TEXT NOT NULL REFERENCES notification_passes(id) ON DELETE CASCADE,
                    state TEXT NOT NULL, attempts INTEGER NOT NULL, next_try REAL NOT NULL,
                    last_status INTEGER,
                    PRIMARY KEY(subscription_id,pass_id)
                );
            """)

        # Extend the existing per-device ledger without replaying sent passes.
        from .test_push import initialize
        initialize(self)
        with self.connect() as db:
            columns = {r['name'] for r in db.execute('PRAGMA table_info(push_deliveries)')}
            for name, default in [('sent_count',0),('repeat_total',1),('interval_seconds',7)]:
                if name not in columns:
                    db.execute(f'ALTER TABLE push_deliveries ADD COLUMN {name} INTEGER NOT NULL DEFAULT {default}')

    def config(self):
        try:
            data = json.loads((self.folder / 'push-config.json').read_text(encoding='utf-8'))
            if not data['base_url'].startswith('https://'):
                return None
            return data if (self.folder / 'vapid-private.pem').is_file() and (self.folder / 'push-encryption.key').is_file() else None
        except (OSError, ValueError, KeyError):
            return None

    def public_key(self):
        private = serialization.load_pem_private_key((self.folder/'vapid-private.pem').read_bytes(), None)
        raw = private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        return base64.urlsafe_b64encode(raw).decode().rstrip('=')

    def cipher(self):
        return Fernet((self.folder/'push-encryption.key').read_bytes())

    def add(self, user_id, subscription, label, now):
        subscription = validate_subscription(subscription)
        endpoint_hash = hashlib.sha256(subscription['endpoint'].encode()).hexdigest()
        encrypted = self.cipher().encrypt(json.dumps(subscription).encode()).decode()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT id,user_id FROM push_subscriptions WHERE endpoint_hash=?', (endpoint_hash,)).fetchone()
            if existing and existing['user_id'] != user_id:
                raise ValueError('この端末は別のユーザーが登録済みです。元のユーザーで解除してください。')
            if not existing and db.execute('SELECT COUNT(*) FROM push_subscriptions WHERE user_id=?',(user_id,)).fetchone()[0] >= 20:
                raise ValueError('端末の登録上限は20台です。不要な登録を解除してください。')
            identity = existing['id'] if existing else secrets.token_hex(16)
            db.execute('INSERT INTO push_subscriptions VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET encrypted=excluded.encrypted,label=excluded.label',
                (identity, user_id, endpoint_hash, encrypted, str(label).strip()[:80] or 'ブラウザー', now.timestamp()))
        return identity

    def devices(self, user_id):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,label,created FROM push_subscriptions WHERE user_id=? ORDER BY created', (user_id,))]

    def remove(self, user_id, identity):
        with self.connect() as db:
            return db.execute('DELETE FROM push_subscriptions WHERE user_id=? AND id=?', (user_id, identity)).rowcount

    def by_endpoint(self, user_id, endpoint):
        digest = hashlib.sha256(endpoint.encode()).hexdigest()
        with self.connect() as db:
            row = db.execute('SELECT id FROM push_subscriptions WHERE user_id=? AND endpoint_hash=?', (user_id,digest)).fetchone()
            return row['id'] if row else None

    def pass_detail(self, user_id, identity):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM notification_passes WHERE user_id=? AND id=?', (user_id,identity)).fetchone()
            return json.loads(row['payload']) if row else None

    def claim(self, now):
        epoch = now.timestamp()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute("""SELECT q.*,p.id AS pass_id,p.payload,s.id AS subscription_id,s.encrypted,s.created,u.timezone_name,
                    d.state,d.attempts,d.next_try,d.sent_count,d.repeat_total,d.interval_seconds,n.start_minute,n.end_minute,
                    COALESCE(t.repeat_count,3) AS configured_count,COALESCE(t.interval_seconds,7) AS configured_interval
                FROM notification_queue q
                JOIN notification_passes p ON p.user_id=q.user_id AND p.satellite_name=q.satellite_name AND p.aos=q.aos
                JOIN push_subscriptions s ON s.user_id=q.user_id
                JOIN users u ON u.id=q.user_id
                JOIN notification_settings n ON n.user_id=q.user_id
                LEFT JOIN push_deliveries d ON d.subscription_id=s.id AND d.pass_id=p.id
                LEFT JOIN push_test_preferences t ON t.user_id=q.user_id
                WHERE q.send_at>=? AND q.send_at<=?
                ORDER BY q.send_at,s.id""", ((now-timedelta(seconds=120)).isoformat(),now.isoformat())).fetchall()
            for row in rows:
                send = datetime.fromisoformat(row['send_at']).timestamp()
                aos = datetime.fromisoformat(row['aos']).timestamp()
                # No stale burst after downtime; send at most 120s late, never after AOS.
                if row['created'] > send or not (send <= epoch <= send+120 and epoch <= aos+5):
                    continue
                if not allowed_at(now.astimezone(ZoneInfo(row['timezone_name'])),row['start_minute'],row['end_minute']):
                    continue
                if row['state'] in ('sent','failed') or (row['next_try'] is not None and row['next_try'] > epoch):
                    continue
                attempts = (row['attempts'] or 0)+1
                total = row['repeat_total'] if row['state'] is not None else row['configured_count']
                interval = row['interval_seconds'] if row['state'] is not None else row['configured_interval']
                sent_count = row['sent_count'] or 0
                db.execute("""INSERT INTO push_deliveries(subscription_id,pass_id,state,attempts,next_try,last_status,sent_count,repeat_total,interval_seconds)
                    VALUES (?,?,'sending',?,?,NULL,?,?,?)
                    ON CONFLICT(subscription_id,pass_id) DO UPDATE SET state='sending',attempts=excluded.attempts,next_try=excluded.next_try""",
                    (row['subscription_id'],row['pass_id'],attempts,epoch+60,sent_count,total,interval))
                return dict(row, attempts=attempts, sent_count=sent_count, repeat_total=total, interval_seconds=interval)
        return None

    def still_valid(self, job):
        with self.connect() as db:
            return db.execute("""SELECT 1 FROM notification_queue q JOIN push_subscriptions s ON s.user_id=q.user_id
                WHERE q.user_id=? AND q.satellite_name=? AND q.aos=? AND q.send_at=? AND s.id=?""",
                (job['user_id'],job['satellite_name'],job['aos'],job['send_at'],job['subscription_id'])).fetchone() is not None

    def finish(self, job, status, now):
        with self.connect() as db:
            if status in (404,410):
                db.execute('DELETE FROM push_subscriptions WHERE id=?', (job['subscription_id'],))
                return
            success = status is not None and 200 <= status < 300
            temporary = status is None or status == 429 or status >= 500
            sent_count = job['sent_count'] + (1 if success else 0)
            if success:
                state = 'sent' if sent_count >= job['repeat_total'] else 'repeat'
                next_try = now.timestamp()+job['interval_seconds']
                attempts = 0
            else:
                state = 'retry' if temporary and job['attempts'] < 3 else 'failed'
                next_try = now.timestamp()+min(60,15*job['attempts'])
                attempts = job['attempts']
            db.execute('UPDATE push_deliveries SET state=?,attempts=?,next_try=?,last_status=?,sent_count=? WHERE subscription_id=? AND pass_id=?',
                (state,attempts,next_try,status,sent_count,job['subscription_id'],job['pass_id']))


def deliver_due(store, now, transport=None, limit=100):
    config = store.config()
    if not config:
        raise ValueError('先にsetup_push.pyでHTTPS公開URLとVAPID鍵を設定してください。')
    if transport is None:
        from pywebpush import webpush
        transport = webpush
    accepted = failed = expired = 0
    start = time.monotonic()
    initial = now
    for _ in range(limit):
        now = initial + timedelta(seconds=time.monotonic()-start)
        job = store.claim(now)
        if job is None:
            break
        if not store.still_valid(job):
            store.finish(job,400,now)
            continue
        aos = datetime.fromisoformat(job['aos'])
        remaining = max(0,math.ceil((aos-now).total_seconds()/60))
        local = aos.astimezone(ZoneInfo(job['timezone_name']))
        payload = dict(title=job['satellite_name'], body=f"AOSまで{remaining}分\nAOS {local:%H:%M}\nMAXEL {job['maxel']:.0f}°",
                       url=config['base_url']+'/pass/'+job['pass_id'], tag='satbox-'+job['pass_id']+'-'+str(job['sent_count']+1))
        status = None
        try:
            subscription = validate_subscription(json.loads(store.cipher().decrypt(job['encrypted'].encode())))
            response = transport(subscription_info=subscription,data=json.dumps(payload,ensure_ascii=False),
                vapid_private_key=str(store.folder/'vapid-private.pem'),vapid_claims={'sub':config['subject']},
                ttl=max(1,min(120,int((aos-now).total_seconds()))),timeout=15)
            status = response.status_code
        except Exception as exc:
            # Never log an exception body: push URLs and keys are sensitive.
            response = getattr(exc,'response',None)
            status = response.status_code if response is not None else None
            if isinstance(exc, (ValueError,TypeError)):
                status = 400
        finished = initial + timedelta(seconds=time.monotonic()-start)
        store.finish(job,status,finished)
        if status in (404,410): expired += 1
        elif status is not None and 200 <= status < 300: accepted += 1
        else: failed += 1
    return dict(accepted=accepted,failed=failed,expired=expired)
