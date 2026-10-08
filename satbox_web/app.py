import hashlib
import json
import logging
import math
import os
import secrets
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from flask import Flask, g, render_template
from satbox_orbit import Observer
from satbox_orbit.catalog import read_catalog, select_records
from .auth import auth, csrf_token, login_required
from .cache import PassCache
from .storage import UserStore
from .predictions import PredictionService
from .notifications import notifications
from .push import push
from .satellites import satellites
from .admin import admin
from .satellite_map import satellite_map
from satbox_notifications.push import PushStore
from satbox_notifications.paths import private_folder
from satbox_notifications.storage import NotificationStore
from satbox_notifications.planning import allowed_at, format_minutes


def tle_updated(config, base, raw):
    """Show the local download time for matching TLE; fall back for old metadata."""
    try:
        data = json.loads((base / config['tle_metadata_file']).read_text(encoding='utf-8-sig'))
        if data['sha256'] != hashlib.sha256(raw).hexdigest():
            return None
        if data.get('saved_utc'):
            return datetime.fromisoformat(data['saved_utc']).astimezone(timezone.utc)
        if data.get('last_modified'):
            return parsedate_to_datetime(data['last_modified']).astimezone(timezone.utc)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def persistent_secret(folder):
    value = os.environ.get('SATBOX_SECRET_KEY')
    if value:
        if len(value) < 32:
            raise ValueError('SATBOX_SECRET_KEY must be at least 32 characters')
        return value
    path = folder / 'session.key'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'w') as stream:
            stream.write(secrets.token_hex(32))
    secret = path.read_text(encoding='utf-8').strip()
    if len(secret) < 32:
        raise ValueError('Invalid session.key; do not start with an empty signing key')
    return secret


def create_app(config_path=None, clock=None, data_dir=None, test_config=None):
    app = Flask(__name__)
    config_path = Path(config_path or Path(__file__).parents[1] / 'web-qth.json').resolve()
    # Keep passwords, sessions and QTH outside the HTML/public project tree.
    folder = private_folder(config_path, data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    clock = clock or (lambda: datetime.now(timezone.utc))
    app.config.update(SECRET_KEY=persistent_secret(folder), MAX_CONTENT_LENGTH=256 * 1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('SATBOX_COOKIE_SECURE') == '1',
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=12))
    if test_config:
        app.config.update(test_config)
    initial = json.loads(config_path.read_text(encoding='utf-8-sig'))
    app.extensions['profile_defaults'] = dict(callsign='', latitude_deg=initial.get('latitude_deg', 0),
        longitude_deg=initial.get('longitude_deg', 0), altitude_m=initial.get('altitude_m', 0),
        timezone_name=initial.get('timezone_name', 'Asia/Manila'), grid_locator='', duration_hours=24)
    app.extensions['clock'] = clock
    app.extensions['users'] = UserStore(folder / 'users.sqlite3')
    app.extensions['pass_cache'] = PassCache(folder / 'passes.sqlite3')
    app.extensions['predictions'] = PredictionService(config_path, app.extensions['pass_cache'])
    app.extensions['notifications'] = NotificationStore(folder / 'users.sqlite3')
    app.extensions['push'] = PushStore(folder)
    app.jinja_env.globals['csrf_token'] = csrf_token
    app.register_blueprint(auth)
    app.register_blueprint(notifications)
    app.register_blueprint(push)
    app.register_blueprint(satellites)
    app.register_blueprint(admin)
    app.register_blueprint(satellite_map)

    @app.get('/')
    @login_required
    def index():
        try:
            zone = ZoneInfo(g.user['timezone_name'])
            observer = Observer(g.user['latitude_deg'], g.user['longitude_deg'], g.user['altitude_m'])
            query_now = clock().astimezone(timezone.utc)
            config, raw, records, all_rows, errors, generated, hit, source = app.extensions['predictions'].get(g.user, query_now)
            horizon = float(config['horizon_deg'])
            queue, _ = app.extensions['notifications'].refresh(g.user, all_rows, source, clock().astimezone(timezone.utc))
            prefs = app.extensions['notifications'].get(g.user['id'])
            minimum = prefs.min_maxel_deg
            rows = [dict(r) for r in all_rows]
            for row in rows:
                row['notification_planned'] = any(p['satellite_name'] == row['name'] and abs((p['aos'] - row['aos']).total_seconds()) < 120 for p in queue)
                reasons = []
                if row['maxel'] < minimum:
                    reasons.append('最低最大仰角未満')
                notification_time = row['aos'] - timedelta(minutes=prefs.lead_minutes)
                row['announcement_ms'] = int((notification_time + timedelta(seconds=30)).timestamp()*1000)
                row['rising_allowed'] = row['maxel'] >= minimum and allowed_at(row['aos'].astimezone(zone),prefs.start_minute,prefs.end_minute)
                if not allowed_at(notification_time.astimezone(zone), prefs.start_minute, prefs.end_minute):
                    reasons.append('通知時間帯外')
                row['muted'] = bool(reasons)
                row['muted_reason'] = '・'.join(reasons)
                row['aos'] = row['aos'].astimezone(zone)
                row['los'] = row['los'].astimezone(zone)
            # Capture display time after calculation, so expensive first prediction
            # does not make the clock/countdown lag behind the server.
            now = clock().astimezone(timezone.utc)
            rows = [r for r in rows if r['los'] > now]
            for row in rows:
                row['active'] = row['aos'] <= now < row['los']
            updated = tle_updated(config, config_path.parent, raw)
            return render_template('index.html', map_names=[r.name for r in records],
                map_initial=rows[0]['name'] if rows else (records[0].name if records else ''), now=now, local_now=now.astimezone(zone),
                timezone_name=g.user['timezone_name'], observer=observer, config=config, rows=rows,
                updated=updated.astimezone(zone) if updated else None, errors=errors,
                horizon=horizon, minimum=minimum, hours=g.user['duration_hours'],
                generated=generated.astimezone(zone), cache_hit=hit,
                notify_satellites=prefs.enabled_satellites, queue_count=len(queue),
                announcement_lead=prefs.lead_minutes,
                start_time=format_minutes(prefs.start_minute), end_time=format_minutes(prefs.end_minute))
        except (ValueError, KeyError, TypeError, OSError, OverflowError) as exc:
            logging.exception('Cannot build satellite pass page')
            return render_template('error.html'), 503

    @app.after_request
    def response_headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        from flask import request
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    return app

