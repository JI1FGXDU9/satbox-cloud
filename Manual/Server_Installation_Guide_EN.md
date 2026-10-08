[日本語](サーバー設置手順.md) | [English](Server_Installation_Guide_EN.md)

# SatBox Cloud Server Installation Guide

## 1. Scope and deployment methods

This guide covers Linux-based hosting for SatBox Cloud. It includes an XSERVER
example, but other shared hosts, Python hosting services, and VPS providers can
also be used if their plans meet the requirements below.
When considering providers such as Sakura Rental Server or Lolipop!, check the
specific plan's Python, CGI, SSH, Cron, and process policies. The provider's name
alone does not establish compatibility. This guide does not guarantee operation
on every provider or plan.

Method A: Python CGI on shared hosting
```text
Uses Apache CGI execution and URL rewriting. The public entry consists of
index.cgi and .htaccess. The deploy/xserver-public/ directory is an XSERVER
template and requires changes for a different environment. If .htaccess is
unavailable, configure equivalent routing through the hosting service.
```

Method B: WSGI or VPS
```text
For Python application hosting or a VPS that permits persistent processes.
serve_web.py can run Waitress behind an HTTPS reverse proxy. Do not combine
CGI and Waitress behind the same public entry point.
```

PHP-only plans and static HTML hosting cannot run this application unchanged.
FTP transfers files; Python, dependencies, and scheduled jobs also need setup.

## 2. Required hosting capabilities

- A Python environment compatible with the dependencies, plus venv and pip.
```text
The existing XSERVER installation uses a user-installed Python 3.12.
```
- Skyfield, SGP4, NumPy, Flask, SQLite, and cryptography/Web Push dependencies.
- SSH or equivalent facilities for creating an environment and installing packages.
- For Method A: Python CGI, URL rewriting, and executable file permissions.
- For Method B: WSGI hosting or permission to operate Waitress and an HTTPS proxy.
- HTTPS, writable private storage, and SQLite file locking.
- Outbound HTTPS connections to AMSAT and Web Push delivery services.
- Cron or permitted persistent workers for notifications when the page is closed.

Shared hosting may limit CPU, memory, and CGI execution time. Begin with a small
satellite selection because the first prediction can be expensive. Ask the host
about the minimum Cron interval and restrictions on background processes.

## 3. Directory layout and files to upload

Replace ACCOUNT, DOMAIN, and the public directory with values for your server.

```text
Private application: /home/ACCOUNT/DOMAIN/satbox-cloud/
Private data:        /home/ACCOUNT/satbox-data/
Public CGI entry:    /home/ACCOUNT/DOMAIN/public_html/satbox/
Public URL:          https://DOMAIN/satbox/
```

The public directory may be named public_html, www, or htdocs. Keep the full
application and private data outside directories that browsers can download.

Main application files to upload:
```text
satbox_web/, satbox_orbit/, satbox_notifications/, satbox_db.py
web-qth.json, nasa.all, iss-qth.source.json (timestamp metadata)
requirements.txt, requirements-web.txt, requirements-xserver.txt
setup_push.py, setup_admin.py, manage_admin.py
prepare_notifications.py, send_notifications.py
serve_web.py, notification_workers.sh, deploy/
```

Check that tle_file and tle_metadata_file in web-qth.json match the real filenames.
Preserve the templates/ and static/ directory structure within satbox_web/.
Normally do not upload __pycache__, local .venv, backup, tests, logs, or update ZIPs.
Do not overwrite the server's existing virtual environment, databases, session.key,
or Web Push keys with local update files. Back up the server application and
private data before updating.

## 4. Python environment and dependencies

Use SSH to enter the application directory. Create the environment only on initial
installation. Replace python3 with the required interpreter path if necessary.

```text
cd /home/ACCOUNT/DOMAIN/satbox-cloud
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-web.txt
.venv/bin/python -c "import flask, skyfield, sgp4, numpy; from satbox_db import sqlite3; print(sqlite3.sqlite_version)"
```

On the existing older Linux XSERVER environment with user-installed Python 3.12,
the normal NumPy version may fail to build. Use the existing environment's
requirements-xserver.txt in that case:

```text
.venv/bin/python -m pip install --only-binary=numpy,pysqlite3-binary -r requirements-xserver.txt
```

Do not apply this environment-specific file indiscriminately to other hosts.
Choose dependencies compatible with the Python version, OS, CPU, and available
wheels. satbox_db.py falls back to pysqlite3 when standard SQLite is unavailable.
If the existing environment already has all required packages and dependencies
have not changed, reinstalling them is unnecessary.

## 5. Use one private data directory

The web application, administration commands, scheduler, and sender must all use
the same private data directory. For example:

```text
export SATBOX_DATA_DIR=/home/ACCOUNT/satbox-data
mkdir -p "$SATBOX_DATA_DIR"
chmod 700 "$SATBOX_DATA_DIR"
```

CGI may not inherit environment variables from SSH or Cron. For Method A, add the
following after import os and before importing the application in public index.cgi:

```text
os.environ['SATBOX_DATA_DIR'] = '/home/ACCOUNT/satbox-data'
```

For Method B, set the same variable in the hosting or service environment. Set it
in Cron as well, or pass --data-dir to commands that support it. Without an explicit
directory, the application selects a user data location automatically. Specifying
it during deployment helps avoid different databases for different users or jobs.

## 6. Method A: install the CGI entry

Place deploy/xserver-public/index.cgi and .htaccess in the public entry directory.
Check that the destination does not belong to another application before copying.
The full application, databases, and keys do not need to be copied into it.

Change these settings in index.cgi:
```text
The #! line: /home/ACCOUNT/DOMAIN/satbox-cloud/.venv/bin/python
The sys.path.insert path: /home/ACCOUNT/DOMAIN/satbox-cloud
SATBOX_DATA_DIR: the private data directory above
Keep the existing settings that limit BLAS startup threads to one.
```

Change these settings in satbox_web/cgi_entry.py:
```text
Replace the fixed HTTPS redirect host 'https://ji1fgx.com' with 'https://DOMAIN'.
If the public path is not /satbox/, change the default mount argument in
normalize_environment and SESSION_COOKIE_PATH.
```

Change these settings in .htaccess:
```text
Change RewriteBase /satbox/ if the public path differs.
Adapt the CGI handler directives to the provider's requirements.
Do not replace an existing domain-level .htaccess without reviewing it.
```

Save and transfer CGI files with LF line endings and no UTF-8 BOM. XSERVER specifies
755 or 705 for CGI files and their directory. An example using 755:

```text
chmod 755 /home/ACCOUNT/DOMAIN/public_html/satbox
chmod 755 /home/ACCOUNT/DOMAIN/public_html/satbox/index.cgi
chmod 644 /home/ACCOUNT/DOMAIN/public_html/satbox/.htaccess
```

Use the permissions required by other providers. Mode 777 is not needed.
Do not start serve_web.py or Waitress for Method A.

## 7. Method B: WSGI or VPS hosting

If the host provides a WSGI application setting, follow its instructions and expose
the return value of satbox_web.app.create_app() as application, for example. Check
public URL routing, HTTPS, subpath mounting, and session cookie configuration.
For HTTPS-only operation, set SATBOX_COOKIE_SECURE=1.

Example when you manage the reverse proxy yourself:

```text
cd /home/ACCOUNT/DOMAIN/satbox-cloud
export SATBOX_DATA_DIR=/home/ACCOUNT/satbox-data
.venv/bin/python serve_web.py --port 8080
```

serve_web.py listens on 127.0.0.1. It assumes one trusted HTTPS proxy on the same
host and uses X-Forwarded-Proto and X-Forwarded-Prefix for the URL prefix. Configure
the proxy to set these correctly and replace client-supplied values. Multiple
proxy layers require configuration appropriate to that deployment.
Use the host's process manager or systemd for production restarts and logging.

## 8. Initial checks and administrator setup

Open the public HTTPS URL and check:
```text
Login → Japanese/English selection → Account registration → QTH settings
Satellite selection → Pass list → Alert settings → Scheduled alerts
Map, LOCAL/GMT display, and language persistence after reopening the page
```

After registering your own account, create the initial administrator:

```text
cd /home/ACCOUNT/DOMAIN/satbox-cloud
.venv/bin/python setup_admin.py YOUR_LOGIN_ID --data-dir /home/ACCOUNT/satbox-data
```

Replace YOUR_LOGIN_ID with the actual login ID. If an initial administrator already
exists, use Administration or manage_admin.py. NASA.ALL updates affect all users.
The displayed TLE update time is the local save timestamp.

## 9. HTTPS, caching, and the map

Do not place login, QTH, or subscription data in a shared cache. The application
sends Cache-Control: no-store; exclude its public route from server/CDN caching as
well. On XSERVER, check settings such as X Accelerator. After JavaScript updates,
reload with Ctrl+F5 or the browser's equivalent.

The map uses externally hosted Leaflet and OpenStreetMap tiles. Keep visible
attribution and the tile referrer setting, and follow the provider's usage policy.
Removing the tile referrerPolicy option in satellite-map.js can cause a 403 error.
The map stays centered on the observer and displays the selected satellite during
its active pass.

## 10. Web Push setup

After the pages work, configure keys and the public URL using the same private data
directory:

```text
.venv/bin/python setup_push.py --base-url https://DOMAIN/satbox --subject mailto:YOUR-EMAIL --data-dir /home/ACCOUNT/satbox-data
```

Replace DOMAIN and YOUR-EMAIL with your domain and contact address. Change base-url
if you use a different public path. Log in over HTTPS on the phone or PC and use
Notification devices to register it. With a /satbox/ mount, the Service Worker scope
is /satbox/ and notification clicks open /satbox/pass/<id>. Browser and OS permission
are also required. Do not unnecessarily regenerate production keys or overwrite
them with keys from another environment.

## 11. Scheduling and sending notifications

Publishing the web pages alone does not schedule background delivery when they are
closed. Run these commands periodically using the same configuration and data:

```text
.venv/bin/python prepare_notifications.py --data-dir /home/ACCOUNT/satbox-data
.venv/bin/python send_notifications.py --data-dir /home/ACCOUNT/satbox-data
```

In Cron, set the application working directory and use an absolute Python path.
Keep logs private and avoid overlapping runs. A one-minute sender interval can
add up to about one minute of polling delay, plus network and device delays. Check
the delivery deadline in send_notifications.py and notification storage, and
choose an appropriate schedule.

On Linux systems that allow persistent workers, use --loop on both commands or the
included notification_workers.sh. This script requires bash, flock, Linux /proc,
and the application's .venv/bin/python.

```text
export SATBOX_DATA_DIR=/home/ACCOUNT/satbox-data
bash notification_workers.sh start
bash notification_workers.sh status
```

Configure startup after a server reboot separately using the host's tools or systemd.
If persistent workers are prohibited, use permitted scheduled execution instead.

## 12. Troubleshooting and updates

500 error: check CGI/application logs, Python path, packages, line endings, permissions.
404/wrong redirect: check public path, RewriteBase, fixed domain, and mount.
Missing user: verify SATBOX_DATA_DIR for the web application, Cron, and commands.
No notification: check device registration, permissions, alert conditions, jobs, logs.
Map 403: check the referrer setting and tile provider's usage policy.

Upload changed application files with their directory structure preserved. CGI
normally requires no web process restart. Restart a WSGI/Waitress deployment after
application updates. Restart notification workers when their code changes.
Keep databases, keys, and session files private, and verify your backup recovery
procedure.

References (check current provider requirements and policies):
XSERVER CGI: https://www.xserver.ne.jp/manual/man_program_cgi.php
Python WSGI CGIHandler: https://docs.python.org/3/library/wsgiref.html
OpenStreetMap tile policy: https://operations.osmfoundation.org/policies/tiles/

Note: This guide replaces XSERVER設置手順.txt. The environment-specific names
deploy/xserver-public/ and requirements-xserver.txt are retained.

[Web Push setup, device registration, and testing](Web_Push_Setup_Guide_EN.md)
