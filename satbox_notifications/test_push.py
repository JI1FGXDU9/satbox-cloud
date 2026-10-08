"""User-requested test pushes; no orbit calculation or AOS queue changes."""
import json
import secrets
import time
from datetime import timedelta
from .push import validate_subscription


def initialize(store):
    with store.connect() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS push_test_requests (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created REAL NOT NULL,
                repeat_count INTEGER NOT NULL DEFAULT 3,
                interval_seconds INTEGER NOT NULL DEFAULT 7
            );
            CREATE INDEX IF NOT EXISTS push_test_user ON push_test_requests(user_id,created);
            CREATE TABLE IF NOT EXISTS push_test_jobs (
                request_id TEXT NOT NULL REFERENCES push_test_requests(id) ON DELETE CASCADE,
                subscription_id TEXT NOT NULL REFERENCES push_subscriptions(id) ON DELETE CASCADE,
                state TEXT NOT NULL DEFAULT 'pending',
                PRIMARY KEY(request_id,subscription_id)
            );
            CREATE TABLE IF NOT EXISTS push_test_preferences (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                repeat_count INTEGER NOT NULL, interval_seconds INTEGER NOT NULL
            );
        ''')
        columns = {r['name'] for r in db.execute('PRAGMA table_info(push_test_requests)')}
        for name, default in [('repeat_count',3),('interval_seconds',7)]:
            if name not in columns:
                db.execute(f'ALTER TABLE push_test_requests ADD COLUMN {name} INTEGER NOT NULL DEFAULT {default}')



def preferences(store, user_id):
    initialize(store)
    with store.connect() as db:
        row = db.execute('SELECT repeat_count,interval_seconds FROM push_test_preferences WHERE user_id=?',(user_id,)).fetchone()
        return dict(row) if row else dict(repeat_count=3,interval_seconds=7)


def validate_repeat(repeat_count, interval_seconds):
    try:
        repeat_count, interval_seconds = int(repeat_count), int(interval_seconds)
    except (ValueError,TypeError):
        raise ValueError('送信回数と間隔秒は整数で指定してください。')
    if not 1 <= repeat_count <= 5 or not 1 <= interval_seconds <= 15:
        raise ValueError('送信回数は1～5回、間隔は1～15秒で指定してください。')
    return repeat_count, interval_seconds


def save_repeat(db, user_id, repeat_count, interval_seconds):
    db.execute('INSERT INTO push_test_preferences VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET repeat_count=excluded.repeat_count,interval_seconds=excluded.interval_seconds',
               (user_id,repeat_count,interval_seconds))


def enqueue(store, user_id, now, repeat_count=3, interval_seconds=7):
    repeat_count, interval_seconds = validate_repeat(repeat_count,interval_seconds)
    initialize(store)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        latest = db.execute('SELECT MAX(created) FROM push_test_requests WHERE user_id=?', (user_id,)).fetchone()[0]
        if latest is not None and now.timestamp() - latest < 60:
            raise ValueError('テスト通知は1分に1回です。少し待ってからお試しください。')
        devices = db.execute('SELECT id FROM push_subscriptions WHERE user_id=?', (user_id,)).fetchall()
        if not devices:
            raise ValueError('登録済みの端末がありません。「通知端末登録」で先に登録してください。')
        identity = secrets.token_hex(16)
        db.execute('INSERT INTO push_test_requests(id,user_id,created,repeat_count,interval_seconds) VALUES (?,?,?,?,?)',
                   (identity,user_id,now.timestamp(),repeat_count,interval_seconds))
        db.execute('INSERT INTO push_test_preferences VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET repeat_count=excluded.repeat_count,interval_seconds=excluded.interval_seconds',
                   (user_id,repeat_count,interval_seconds))
        db.executemany('INSERT INTO push_test_jobs(request_id,subscription_id) VALUES (?,?)',
                       [(identity,r['id']) for r in devices])
    return len(devices)


def deliver_tests(store, now, transport=None, limit=20):
    initialize(store)
    config = store.config()
    if not config:
        return dict(test_accepted=0,test_failed=0)
    if transport is None:
        from pywebpush import webpush
        transport = webpush
    accepted = failed = 0
    initial, started = now, time.monotonic()
    # Claim once before sending: a test must not keep alerting after a network error.
    for _ in range(limit):
        now = initial + timedelta(seconds=time.monotonic()-started)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM push_test_requests WHERE created<?', (now.timestamp()-86400,))
            db.execute("UPDATE push_test_jobs SET state='expired' WHERE state='pending' AND request_id IN (SELECT id FROM push_test_requests WHERE created<?)", (now.timestamp()-120,))
            job = db.execute('''SELECT j.request_id,j.subscription_id,s.user_id,s.encrypted,r.repeat_count,r.interval_seconds
                FROM push_test_jobs j JOIN push_test_requests r ON r.id=j.request_id
                JOIN push_subscriptions s ON s.id=j.subscription_id AND s.user_id=r.user_id
                WHERE j.state='pending' ORDER BY r.created LIMIT 1''').fetchone()
            if job is None:
                break
            db.execute("UPDATE push_test_jobs SET state='sending' WHERE request_id=? AND subscription_id=?", (job['request_id'],job['subscription_id']))
        status = None
        # Use the immutable request settings for this burst.
        # A transport failure stops this device's burst; there is no retry.
        for sequence in range(1,job['repeat_count']+1):
            try:
                with store.connect() as db:
                    valid = db.execute('SELECT 1 FROM push_subscriptions WHERE id=? AND user_id=?', (job['subscription_id'],job['user_id'])).fetchone()
                if not valid:
                    status = 410
                    break
                subscription = validate_subscription(json.loads(store.cipher().decrypt(job['encrypted'].encode())))
                payload = dict(title=f"SatBox テスト通知 {sequence}/{job['repeat_count']}",body='通知音テストです。衛星のAOS通知ではありません。',
                               url=config['base_url']+'/notification-settings',tag='satbox-test-'+job['request_id']+'-'+str(sequence))
                response = transport(subscription_info=subscription,data=json.dumps(payload,ensure_ascii=False),
                    vapid_private_key=str(store.folder/'vapid-private.pem'),vapid_claims={'sub':config['subject']},ttl=60,timeout=15)
                status = response.status_code
            except Exception as exc:
                response = getattr(exc,'response',None)
                status = response.status_code if response is not None else None
            if status is None or not 200 <= status < 300:
                break
            if sequence < job['repeat_count']:
                time.sleep(job['interval_seconds'])
        success = status is not None and 200 <= status < 300
        with store.connect() as db:
            db.execute('UPDATE push_test_jobs SET state=? WHERE request_id=? AND subscription_id=?',
                       ('accepted' if success else 'failed',job['request_id'],job['subscription_id']))
            if status in (404,410):
                db.execute('DELETE FROM push_subscriptions WHERE id=? AND user_id=?', (job['subscription_id'],job['user_id']))
        if success:
            accepted += 1
        else:
            failed += 1
    return dict(test_accepted=accepted,test_failed=failed)
