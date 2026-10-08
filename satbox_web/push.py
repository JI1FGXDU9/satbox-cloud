"""Authenticated Web Push registration and saved Pass detail routes."""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, send_from_directory, url_for
from .auth import login_required

push = Blueprint('push', __name__)

def store():
    return current_app.extensions['push']

def secure_registration():
    config = store().config()
    # Do not trust forwarded headers unless an explicitly configured proxy handles them.
    if not request.is_secure:
        abort(400, 'スマートフォンの通知登録はHTTPSで開いてください。')
    if not config:
        abort(503, 'Web Pushの公開URLと鍵が未設定です。')
    from urllib.parse import urlsplit
    expected = urlsplit(config['base_url'])
    if request.host.lower() != expected.netloc.lower():
        abort(400, '設定されたHTTPS公開URLで開いてください。')

@push.get('/service-worker.js')
def worker():
    response = send_from_directory(current_app.static_folder, 'service-worker.js', mimetype='text/javascript')
    response.headers['Service-Worker-Allowed'] = request.script_root + '/'
    return response

@push.get('/push-settings')
@login_required
def settings():
    return render_template('push_settings.html',devices=store().devices(g.user['id']),
        configured=bool(store().config()),public_key=store().public_key() if store().config() else '')

@push.post('/push/register')
@login_required
def register():
    secure_registration()
    try:
        subscription = json.loads(request.form.get('subscription',''))
        identity = store().add(g.user['id'],subscription,request.form.get('label',''),current_app.extensions['clock']())
        return jsonify(id=identity)
    except (ValueError,TypeError):
        return jsonify(error='端末を登録できません。通知先・鍵・登録上限・別ユーザーの登録を確認してください。'),400

@push.post('/push/current')
@login_required
def current():
    return jsonify(id=store().by_endpoint(g.user['id'],request.form.get('endpoint','')))

@push.post('/push/test')
@login_required
def test_notification():
    secure_registration()
    from satbox_notifications.test_push import enqueue
    try:
        repeats = request.form.get('repeat_count','3')
        interval = request.form.get('interval_seconds','7')
        count = enqueue(store(),g.user['id'],current_app.extensions['clock'](),repeats,interval)
        flash(f'登録済みの{count}端末へ{int(repeats)}回・待ち時間{int(interval)}秒のテスト通知を予約し、設定を保存しました。送信プログラムが稼働していれば通常数秒で送信します。')
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for('notifications.settings'))

@push.post('/push/remove')
@login_required
def remove():
    if not store().remove(g.user['id'],request.form.get('id','')):
        return jsonify(error='登録が見つかりません。'),404
    return jsonify(ok=True)

@push.get('/pass/<identity>')
@login_required
def detail(identity):
    saved = store().pass_detail(g.user['id'],identity)
    if saved is None:
        abort(404)
    zone = ZoneInfo(g.user['timezone_name'])
    for key in ('aos','los','maximum_at'):
        saved[key] = datetime.fromisoformat(saved[key]).astimezone(zone)
    return render_template('pass_detail.html',row=saved)
