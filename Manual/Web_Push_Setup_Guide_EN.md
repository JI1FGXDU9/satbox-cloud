[日本語](WEB_PUSH設定手順.md) | [English](Web_Push_Setup_Guide_EN.md)

# SatBox Cloud Web Push Setup and Verification

Revised: 8 October 2026

## 1. Purpose

Use this guide after publishing the application over HTTPS using the
[server installation guide](Server_Installation_Guide_EN.md).
It covers Push keys, device registration, testing, delivery workers, and troubleshooting.
Browser voice announcements are a separate feature. Push delivery after closing the page
requires a running server delivery process.
Run commands from the satbox-cloud root, rather than Manual.

## 2. Requirements

- A public HTTPS URL with a certificate trusted by the device.
- A browser supporting Web Push and Service Workers, with browser and OS notification permission.
- Server Python dependencies and outbound HTTPS access to Push services.
- Provider-approved Cron jobs or persistent workers for planning and delivery.

An ordinary HTTP LAN URL, such as http://192.168.1.10:8081, cannot register smartphone notifications.
For iPhone/iPad, check support for Home Screen web apps on iOS/iPadOS 16.4 or later.
Add the app to the Home Screen, open it from there, and grant notification permission.
Check support on the actual browser/device; see [Apple's Web Push documentation](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers).

Install dependencies on Linux:

```bash
.venv/bin/python -m pip install -r requirements-web.txt
```

For an existing XSERVER environment using requirements-xserver.txt, follow the installation guide.
On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python.exe`.

## 3. Configure private storage and keys

Use the same configuration file and private data directory for the web application,
setup, planning, and delivery. Replace the paths, domain, and contact below.

```bash
.venv/bin/python setup_push.py --base-url https://YOUR-HOST/satbox --subject mailto:YOUR-EMAIL --config web-qth.json --data-dir /home/ACCOUNT/satbox-data
```

- `--base-url`: the actual HTTPS public URL, including any subpath.
- `--subject`: the operator's contact in mailto: format.
- `--config` / `--data-dir`: use the same values for the web application and workers.

setup_push.py only saves configuration; it sends no notifications.
Running it again preserves existing VAPID and encryption keys while updating the URL and contact.
Back up `push-config.json`, `vapid-private.pem`, `push-encryption.key`, `users.sqlite3`,
and related private data together. Do not delete keys or overwrite them with another installation's keys.
Keep databases and keys outside the public HTML directory and protect them with Linux permissions or Windows ACLs.

## 4. HTTPS and Service Worker

For CGI, use the public entry point described in the installation guide.
There is no need to start Waitress just to enable notifications.
For WSGI, start the application behind a trusted HTTPS proxy:

```bash
.venv/bin/python serve_web.py --port 8080 --config web-qth.json --data-dir /home/ACCOUNT/satbox-data
```

serve_web.py binds to 127.0.0.1 and assumes one HTTPS proxy on the same host.
Example inside an existing nginx HTTPS server block:

```nginx
location = /satbox { return 301 /satbox/; }
location /satbox/ {
    proxy_pass http://127.0.0.1:8080/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-Prefix /satbox;
}
```

Configure certificates and public routing for your host. Do not publish the Flask development server in production.
Registration checks HTTPS and the configured host/port; an alias domain will not pass this check.
For `/satbox/`, `/satbox/service-worker.js` must be served as JavaScript and its scope is `/satbox/`.
Exclude authentication, device registration, and Service Worker routes from shared CDN caching.

## 5. Planning and delivery workers

Where persistent processes are permitted, run these in separate terminals/services:

```bash
.venv/bin/python prepare_notifications.py --config web-qth.json --data-dir /home/ACCOUNT/satbox-data --loop
```

```bash
.venv/bin/python send_notifications.py --config web-qth.json --data-dir /home/ACCOUNT/satbox-data --loop
```

The planner checks TLE, QTH, satellite selection, and related changes every five seconds,
and processes changes or a fifteen-minute refresh. Normal orbit cache entries last thirty minutes.
The sender checks saved queues and test requests every second without calculating orbits.
Use only execution methods allowed by the hosting provider. For one-shot Cron jobs, omit `--loop`
and set the working directory and absolute Python path. A one-minute schedule adds polling delay,
as well as network and device delays.
Linux installations can also use notification_workers.sh; see the [installation guide](Server_Installation_Guide_EN.md).
Configure restart after reboot and log management through the OS or provider.
`plan_notifications.py --all` displays plans manually; it does not send notifications.

## 6. User settings and device registration

1. Log in at the actual public HTTPS URL and check QTH and regional time zone.
2. Save observing targets in Satellite selection.
3. Save notification satellites, minimum peak elevation, lead time, and allowed hours in Notification settings.
4. Check Scheduled notifications. Passes outside the conditions or whose send time has passed are not newly scheduled.
5. Open device registration, enter a device name, select the register-this-device button, and grant permission.
6. Register each additional device from its own browser while logged in.

One browser Subscription can belong to only one user.
On a shared device, unregister under the previous account before switching users.
Use the unregister-this-device button or the remove button for a listed registration.
Japanese mode shows the corresponding Japanese labels.

## 7. Test notifications and repetition

The test button in Notification settings queues notifications to all registered devices.

- Repetitions: 1–5; interval: 1–15 seconds. Defaults: three repetitions, seven seconds.
- These settings apply to both ordinary and test notifications. The test button saves them.
- It does not save other unsaved notification conditions.
- Tests are limited to one per user per minute and ignore notification hours/elevation conditions.
- The sender must be running. Test requests older than 120 seconds are discarded.

Sounds follow browser, OS, and device settings. Check behavior with the page closed and the screen locked.
All repetitions, sounds, and exact sound intervals are not guaranteed.
The page language selection is separate from the Push payload; current Push messages are Japanese.

## 8. Verify a real pass

Choose a notification-enabled satellite with a future send time.
The send time is AOS minus the configured lead time, and allowed hours are evaluated at that
send time in the user's QTH time zone.
Tap the received notification and verify that it opens the user's saved pass details.
When logged out, login returns to those details; another user's details return 404.
Check reception on two devices, then remove one registration and verify reception only on the remaining device.
Page voice announcements are separate: advance speech is thirty seconds after the Push schedule,
and AOS speech occurs at AOS.

## 9. Deadlines, failures, and retention

Delivery requires conditions including no more than 120 seconds after the scheduled time
and no more than five seconds after AOS. Old notifications are not sent in a burst after downtime.
Devices registered after the scheduled send time are excluded.
Ordinary delivery saves the next repeat time after each success and repeats within the deadline.
404/410 removes an invalid registration. 429, 5xx, and network failures allow up to three attempts within the deadline.
Push service acceptance does not guarantee display or sound. A crash between acceptance and database recording can cause a resend.
Notification tags identify the pass and repeat number; OS grouping and suppression also affect presentation.
Saved pass details are retained until seven days after LOS, with old records removed during subsequent replanning.

## 10. Troubleshooting and updates

| Symptom | Check |
| --- | --- |
| HTTPS required | HTTPS URL, certificate, CGI/proxy HTTPS recognition |
| Public URL mismatch | base_url in push-config.json and the actual host/port |
| Missing configuration or users | Matching web/setup/worker configuration and private directory |
| Registration fails | Browser support, permission, another user's registration, registration limit |
| No test notification | Sender, request age, outbound access, logs, OS notification settings |
| Tests work but ordinary notifications do not | Satellite enabled, elevation, local allowed hours, send time, planner, deadline |
| Unexpected repeat count or sound | Time remaining before AOS, delay, OS grouping, power saving, sound settings |
| Incorrect click destination | base_url subpath, Service Worker scope, proxy routing |

After updating code, restart affected persistent web/worker processes and reload the browser.
For CGI updates, follow the installation guide. During migration, preserve databases and keys together and update the public URL.
Register devices again when moving to a different origin.
Preparing this document did not send notifications or register devices; perform the checks above in the actual deployment.

## 11. Related documents

- [Server installation guide](Server_Installation_Guide_EN.md)
- [Development specification](Development_Specification_EN.md)
- [Push API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [pywebpush](https://github.com/web-push-libs/pywebpush)
