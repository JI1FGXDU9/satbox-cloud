"""User-owned settings and queue preview; delivery uses a separate worker."""
from dataclasses import asdict
from datetime import timezone
from zoneinfo import ZoneInfo
from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, url_for
from satbox_notifications.planning import format_minutes, validate_preferences
from .auth import login_required

notifications = Blueprint('notifications', __name__)


def services():
    return current_app.extensions['predictions'], current_app.extensions['notifications']


def now_utc():
    return current_app.extensions['clock']().astimezone(timezone.utc)


@notifications.get('/notification-settings')
@notifications.post('/notification-settings')
@login_required
def settings():
    predictions, store = services()
    try:
        _, _, records = predictions.catalog(g.user)
        names = [r.name for r in records]
        current = store.get(g.user['id'])
        values = dict(asdict(current), start_time=format_minutes(current.start_minute), end_time=format_minutes(current.end_minute))
        from satbox_notifications.test_push import preferences, validate_repeat, save_repeat
        test_values = preferences(current_app.extensions['push'],g.user['id'])
        error = None
        if request.method == 'POST':
            values = dict(request.form, enabled_satellites=request.form.getlist('enabled_satellites'))
            try:
                updated = validate_preferences(values, names)
                repeats, interval = validate_repeat(request.form.get('repeat_count',test_values['repeat_count']),request.form.get('interval_seconds',test_values['interval_seconds']))
                with store.connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    store._save(db,g.user['id'],updated)
                    save_repeat(db,g.user['id'],repeats,interval)
                return redirect(url_for('notifications.queue'))
            except ValueError as exc:
                error = str(exc)
                test_values = dict(repeat_count=request.form.get('repeat_count',test_values['repeat_count']),interval_seconds=request.form.get('interval_seconds',test_values['interval_seconds']))
        return render_template('notification_settings.html', names=names, values=values, error=error, test_values=test_values)
    except (ValueError, OSError, KeyError):
        current_app.logger.exception('Cannot load notification settings catalog')
        return render_template('error.html'), 503


@notifications.post('/notification/satellite')
@login_required
def satellite():
    predictions, store = services()
    try:
        _, _, records = predictions.catalog(g.user)
        name = request.form.get('satellite_name', '')
        enabled = request.form.get('enabled', '')
        if name not in {r.name for r in records} or enabled not in ('0', '1'):
            return jsonify(error='衛星名またはON/OFFが無効です。'), 400
        settings = store.toggle(g.user['id'], name, enabled == '1')
        config, raw, records, passes, errors, generated, hit, source = predictions.get(g.user, now_utc())
        queue, _ = store.refresh(g.user, passes, source, now_utc())
        return jsonify(enabled_satellites=list(settings.enabled_satellites), queue_count=len(queue),
                       queue_ready=not bool(errors), planned_passes=[dict(name=p['satellite_name'], aos_ms=p['aos'].timestamp()*1000) for p in queue])
    except (ValueError, OSError, KeyError):
        current_app.logger.exception('Cannot update notification satellite')
        return jsonify(error='設定または通知予定を更新できませんでした。一覧を開き直してください。'), 503


@notifications.get('/notification-queue')
@login_required
def queue():
    predictions, store = services()
    try:
        config, raw, records, passes, errors, generated, hit, source = predictions.get(g.user, now_utc())
        rows, planned = store.refresh(g.user, passes, source, now_utc())
        zone = ZoneInfo(g.user['timezone_name'])
        for row in rows:
            row['send_at'] = row['send_at'].astimezone(zone)
            row['aos'] = row['aos'].astimezone(zone)
        prefs = store.get(g.user['id'])
        return render_template('notification_queue.html', rows=rows, errors=errors, prefs=prefs,
            start_time=format_minutes(prefs.start_minute), end_time=format_minutes(prefs.end_minute),
            generated=planned.astimezone(zone) if planned else None)
    except (ValueError, OSError, KeyError):
        current_app.logger.exception('Cannot build notification queue')
        return render_template('error.html'), 503
