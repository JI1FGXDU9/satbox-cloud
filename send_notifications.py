"""Deliver precomputed queues only. Never import or invoke the orbit engine."""
import argparse
import time
from datetime import datetime,timezone
from satbox_notifications.paths import private_folder
from satbox_notifications.push import PushStore,deliver_due
from satbox_notifications.test_push import deliver_tests

def main():
    parser=argparse.ArgumentParser(description='Send due Web Push notifications from saved queues')
    parser.add_argument('--config')
    parser.add_argument('--data-dir')
    parser.add_argument('--loop',action='store_true',help='Poll saved queue every second')
    args=parser.parse_args()
    store=PushStore(private_folder(args.config,args.data_dir))
    if not store.config(): parser.error('Run setup_push.py first')
    while True:
        result=deliver_due(store,datetime.now(timezone.utc))
        result.update(deliver_tests(store,datetime.now(timezone.utc)))
        if any(result.values()): print(result,flush=True)
        if not args.loop: break
        time.sleep(1)

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: pass
