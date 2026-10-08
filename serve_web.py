"""Production WSGI server behind one HTTPS reverse proxy on the same host."""
import argparse
from waitress import serve
from werkzeug.middleware.proxy_fix import ProxyFix
from satbox_web.app import create_app

def main():
    parser=argparse.ArgumentParser(description='Serve SatBox behind a local HTTPS reverse proxy')
    parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--config')
    parser.add_argument('--data-dir')
    args=parser.parse_args()
    app=create_app(args.config,data_dir=args.data_dir)
    app.config['SESSION_COOKIE_SECURE']=True
    app.wsgi_app=ProxyFix(app.wsgi_app,x_for=0,x_proto=1,x_host=0,x_prefix=1)
    serve(app,host='127.0.0.1',port=args.port,clear_untrusted_proxy_headers=False)

if __name__=='__main__': main()
