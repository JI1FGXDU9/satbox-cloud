"""Standard WSGI CGI entry for Xserver; no listening socket or proxy trust."""
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit
from wsgiref.handlers import CGIHandler

def normalize_environment(environ, mount='/satbox'):
    # Apache REQUEST_URI retains the original route after .htaccess rewriting.
    original=urlsplit(environ.get('REQUEST_URI',mount+'/')).path
    if original != mount and not original.startswith(mount+'/'):
        raise ValueError('Request is outside the application mount')
    path=original[len(mount):] or '/'
    if path=='/index.cgi': path='/'
    elif path.startswith('/index.cgi/'): path=path[len('/index.cgi'):]
    # WSGI PATH_INFO is a latin-1 representation of URL-decoded UTF-8 bytes.
    environ['SCRIPT_NAME']=mount
    environ['PATH_INFO']=unquote(path,encoding='utf-8',errors='strict').encode('utf-8').decode('latin-1')

def main():
    from .app import create_app
    project=Path(__file__).parents[1]
    normalize_environment(os.environ)
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    app=create_app(project/'web-qth.json')
    app.config['SESSION_COOKIE_SECURE']=True
    app.config['SESSION_COOKIE_PATH']='/satbox/'

    @app.before_request
    def require_https():
        from flask import request,redirect
        if not request.is_secure:
            # Canonical host is fixed; never use user-supplied forwarded headers.
            return redirect('https://ji1fgx.com'+request.script_root+request.full_path.rstrip('?'),code=308)

    CGIHandler().run(app)
