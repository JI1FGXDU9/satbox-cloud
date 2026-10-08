"""Administrator-only views and manually triggered shared catalog updates."""
from functools import wraps
import hashlib
import json
from flask import Blueprint,current_app,g,abort,render_template,redirect,url_for,flash,request
from .auth import login_required

admin = Blueprint('admin',__name__)


def admin_required(function):
    @login_required
    @wraps(function)
    def wrapped(*args,**kwargs):
        if not g.user.get('is_admin'):
            abort(403)
        return function(*args,**kwargs)
    return wrapped


@admin.get('/admin')
@admin_required
def dashboard():
    service = current_app.extensions['predictions']
    try:
        config,raw,catalog = service.catalog(all_records=True)
        from .app import tle_updated
        updated = tle_updated(config,service.config_path.parent,raw)
        rows = []
        with current_app.extensions['users'].connect() as db:
            users = db.execute('''SELECT id,login_id,callsign,email,latitude_deg,longitude_deg,altitude_m,
                timezone_name,grid_locator,satellite_selection,is_admin FROM users ORDER BY login_id''').fetchall()
            for user in users:
                row = dict(user)
                row['satellites_count'] = len(service.selected_names(row,config,catalog))
                row['devices_count'] = db.execute('SELECT COUNT(*) FROM push_subscriptions WHERE user_id=?',(user['id'],)).fetchone()[0]
                rows.append(row)
        return render_template('admin.html',users=rows,catalog_count=len(catalog),updated=updated)
    except (OSError,ValueError,UnicodeError):
        current_app.logger.exception('Cannot load admin page')
        return render_template('error.html'),503


@admin.post('/admin/update-tle')
@admin_required
def update_tle():
    from .tle_update import update_catalog
    try:
        count = update_catalog(current_app.extensions['predictions'].config_path,
                               current_app.extensions['push'].folder)
        with current_app.extensions['notifications'].connect() as db:
            config_path=current_app.extensions['predictions'].config_path
            config=json.loads(config_path.read_text(encoding='utf-8-sig'))
            digest=hashlib.sha256((config_path.parent/config['tle_file']).read_bytes()).hexdigest()
            db.execute('INSERT INTO notification_catalog_state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET digest=excluded.digest',(digest,))
            db.execute('DELETE FROM notification_queue')
            db.execute('DELETE FROM notification_plan_state')
        flash(f'NASA.ALLを更新しました（{count}衛星）。新しいTLEでPassを再計算します。')
    except (OSError,ValueError,UnicodeError,TimeoutError):
        current_app.logger.warning('NASA.ALL update failed')
        flash('NASA.ALLを更新できませんでした。通信・ファイル権限・更新中でないか確認してください。')
    return redirect(url_for('admin.dashboard'))


@admin.post('/admin/user-role')
@admin_required
def user_role():
    action = request.form.get('action')
    if action not in ('grant','revoke'):
        abort(400)
    try:
        changed = current_app.extensions['users'].set_admin(
            request.form.get('login_id',''), action == 'grant', actor_id=g.user['id'])
        if not changed:
            abort(404)
        flash('管理者に昇格しました。' if action == 'grant' else '管理者権限を解除しました。')
    except PermissionError:
        abort(403)
    except ValueError:
        flash('最後の管理者は解除できません。先に別のユーザーを管理者に昇格させてください。')
    # Self-demotion takes effect immediately, including the redirect destination.
    user = current_app.extensions['users'].by_id(g.user['id'])
    return redirect(url_for('admin.dashboard' if user and user['is_admin'] else 'auth.login'))


@admin.post('/admin/delete-user')
@admin_required
def delete_user():
    target = current_app.extensions['users'].by_login(request.form.get('login_id', ''))
    if target is None:
        abort(404)
    try:
        current_app.extensions['users'].delete_account(
            target['id'], current_app.extensions['pass_cache'].path, actor_id=g.user['id'])
        flash('ユーザーを削除しました。')
    except PermissionError:
        abort(403)
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for('admin.dashboard'))
