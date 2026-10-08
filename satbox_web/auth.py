"""Authentication, CSRF and account forms; no orbital calculations."""
import hashlib
import re
import secrets
from satbox_db import sqlite3
from functools import wraps
from flask import Blueprint, abort, current_app, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from .profile import validate_profile, validate_email

auth = Blueprint('auth', __name__)
_DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(24))


def store():
    return current_app.extensions['users']


def csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']


def login_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('auth.login', next=request.script_root+request.path))
        return function(*args, **kwargs)
    return wrapped


@auth.before_app_request
def protect_and_load():
    g.user = store().by_id(session['user_id']) if 'user_id' in session else None
    if g.user is not None and not secrets.compare_digest(
            str(g.user['session_token']), str(session.get('user_token', ''))):
        g.user = None
        session.clear()
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        expected, provided = session.get('csrf_token'), request.form.get('csrf_token')
        if not expected or not provided or not secrets.compare_digest(expected, provided):
            if request.endpoint == 'auth.login':
                # Recover an old/expired login form without accepting its POST.
                # Never echo or preserve the submitted password in the response.
                return render_template('login.html',
                    error='ログイン画面の情報を更新しました。もう一度ログインしてください。ブラウザーを閉じる必要はありません。',
                    login_id=request.form.get('login_id','')[:64]), 400
            abort(400, 'フォームの有効期限が切れました。ページを開き直してください。')


@auth.get('/login-token')
def login_token():
    # Same-origin JS refreshes the CSRF token immediately before submitting.
    # No CORS allowance and no credentials are accepted by this endpoint.
    response = jsonify(csrf_token=csrf_token())
    response.headers['Cache-Control'] = 'no-store'
    return response


@auth.get('/login')
@auth.post('/login')
def login():
    error = None
    status = 200
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip().lower()[:64]
        password = request.form.get('password', '')
        now = current_app.extensions['clock']().timestamp()
        # Limit both account guessing and attempts from one source; ignore untrusted forwarded headers.
        keys = ('user:' + hashlib.sha256(login_id.encode()).hexdigest(), 'ip:' + (request.remote_addr or 'unknown'))
        if any(store().blocked(key, now) for key in keys):
            error, status = 'ログイン試行が多すぎます。15分後に再試行してください。', 429
        else:
            user = store().by_login(login_id)
            valid = check_password_hash(user['password_hash'] if user else _DUMMY_HASH, password) if len(password) <= 128 else False
            if user and valid:
                for key in keys:
                    store().clear_failures(key)
                session.clear()
                session['user_id'] = user['id']
                session['user_token'] = user['session_token']
                session.permanent = True
                # A notification opened while logged out returns to its own saved Pass.
                next_path = request.args.get('next','')
                detail_prefix = request.script_root + '/pass/'
                if next_path.startswith(detail_prefix) and re.fullmatch(r'[0-9a-f]{32}',next_path[len(detail_prefix):]):
                    return redirect(next_path)
                return redirect(url_for('index'))
            for key in keys:
                store().failed(key, now)
            error = 'ログインIDまたはパスワードが違います。'
    return render_template('login.html', error=error,
                           login_id=request.form.get('login_id','')[:64] if request.method == 'POST' else ''), status


@auth.get('/register')
@auth.post('/register')
def register():
    error = None
    values = dict(current_app.extensions['profile_defaults']) if request.method == 'GET' else request.form
    if request.method == 'POST':
        try:
            login_id = request.form.get('login_id', '').strip().lower()
            if not re.fullmatch(r'[a-z0-9][a-z0-9_.\-/]{2,63}', login_id):
                raise ValueError('ログインIDは英数字・_・.・-・/で3～64文字にしてください。')
            password = request.form.get('password', '')
            if not 8 <= len(password) <= 128:
                raise ValueError('パスワードは8～128文字にしてください。')
            if password != request.form.get('password_confirm'):
                raise ValueError('確認用パスワードが一致しません。')
            profile = validate_profile(request.form)
            profile['email'] = validate_email(request.form.get('email', ''), required=True)
            user_id = store().register(login_id, generate_password_hash(password, method='scrypt'), profile)
            session.clear()
            session['user_id'] = user_id
            session['user_token'] = store().by_id(user_id)['session_token']
            session.permanent = True
            return redirect(url_for('index'))
        except ValueError as exc:
            error = str(exc)
        except sqlite3.IntegrityError:
            error = 'このログインIDは使用済みです。'
    return render_template('profile.html', registering=True, values=values, error=error)


@auth.get('/settings')
@auth.post('/settings')
@login_required
def settings():
    error = None
    values = g.user if request.method == 'GET' else request.form
    if request.method == 'POST':
        try:
            profile = validate_profile(request.form)
            if 'email' in request.form:
                profile['email'] = validate_email(request.form['email'])
            store().update(g.user['id'], profile)
            current_app.extensions['notifications'].invalidate(g.user['id'])
            return redirect(url_for('index'))
        except ValueError as exc:
            error = str(exc)
    return render_template('profile.html', registering=False, values=values, error=error)


@auth.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth.get('/withdraw')
@auth.post('/withdraw')
@login_required
def withdraw():
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if request.form.get('confirm') != 'yes':
            error = '退会の確認チェックを入れてください。'
        elif len(password) > 128 or not check_password_hash(g.user['password_hash'], password):
            error = 'パスワードが違います。'
        else:
            # Ignore any client-supplied user ID: only delete the authenticated account.
            try:
                store().delete_account(g.user['id'], current_app.extensions['pass_cache'].path)
            except ValueError as exc:
                return render_template('withdraw.html', error=str(exc))
            session.clear()
            return redirect(url_for('auth.withdrawn'))
    return render_template('withdraw.html', error=error)


@auth.get('/withdrawn')
def withdrawn():
    return render_template('withdrawn.html')
