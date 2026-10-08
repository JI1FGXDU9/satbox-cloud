"""Assign/revoke administrator access from the server shell, never via registration."""
import argparse
from satbox_notifications.paths import private_folder
from satbox_web.storage import UserStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['grant','revoke'])
    parser.add_argument('login_id')
    parser.add_argument('--config')
    parser.add_argument('--data-dir')
    args = parser.parse_args()
    store = UserStore(private_folder(args.config,args.data_dir)/'users.sqlite3')
    try:
        changed = store.set_admin(args.login_id.strip().lower(),args.action=='grant')
    except ValueError as exc:
        parser.error(str(exc))
    if not changed:
        parser.error('Registered login ID not found')
    print('Administrator access',args.action,'for',args.login_id)


if __name__ == '__main__':main()
