"""Create persistent VAPID/encryption keys in the private data folder."""
import argparse
from satbox_notifications.paths import private_folder
from satbox_notifications.push import initialize_push

def main():
    parser=argparse.ArgumentParser(description='Initialize Web Push (does not send notifications)')
    parser.add_argument('--base-url',required=True,help='HTTPS URL, including subpath if used')
    parser.add_argument('--subject',required=True,help='mailto:admin@example.com')
    parser.add_argument('--config')
    parser.add_argument('--data-dir')
    args=parser.parse_args()
    folder=private_folder(args.config,args.data_dir)
    initialize_push(folder,args.base_url,args.subject)
    print('Web Push configuration saved. Existing keys preserved. Private folder:',folder)

if __name__=='__main__': main()
