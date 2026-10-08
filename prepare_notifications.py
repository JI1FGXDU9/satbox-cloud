"""Scheduled prediction/queue generation, separate from the push sender."""
import argparse
import time
import logging
import json
from datetime import datetime,timezone
from satbox_web.app import create_app

def main():
    parser=argparse.ArgumentParser(description='Refresh saved Pass/notification plans for registered users')
    parser.add_argument('--config')
    parser.add_argument('--data-dir')
    parser.add_argument('--loop',action='store_true',help='Refresh every 15 minutes; engine cache handles repeated requests')
    args=parser.parse_args()
    app=create_app(args.config,data_dir=args.data_dir)
    previous = None
    refreshed = 0
    while True:
        users=app.extensions['users'].all_users()
        config_path=app.extensions['predictions'].config_path
        config=json.loads(config_path.read_text(encoding='utf-8-sig'))
        stat=(config_path.parent/config['tle_file']).stat()
        signature=(stat.st_mtime_ns,stat.st_size,config_path.stat().st_mtime_ns,
            tuple((u['id'],u['latitude_deg'],u['longitude_deg'],u['altitude_m'],u['timezone_name'],u['duration_hours'],u.get('satellite_selection')) for u in users))
        if args.loop and signature==previous and time.monotonic()-refreshed<900:
            time.sleep(5)
            continue
        for user in users:
            try:
                *_,passes,errors,generated,hit,source=app.extensions['predictions'].get(user,datetime.now(timezone.utc))
                app.extensions['notifications'].refresh(user,passes,source,datetime.now(timezone.utc))
                if errors: logging.warning('Partial prediction for user %s',user['id'])
            except Exception:
                logging.exception('Cannot refresh prediction for user %s',user['id'])
        print('Plans refreshed:',len(users),'users',flush=True)
        previous=signature
        refreshed=time.monotonic()
        if not args.loop: break
        time.sleep(5)

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: pass
