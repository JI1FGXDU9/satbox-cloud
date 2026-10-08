[日本語](README_jp.md) | [English](README.md)

# SatBox Cloud

SatBox Cloud predicts amateur radio satellite passes from each user's observing
location (QTH). It provides a pass list, countdowns, a satellite map, Web Push
notifications, and browser voice announcements. It also includes command-line
tools for orbital calculations and comparisons with an ESP32 SatBox device.

This README describes the current application. The Japanese README also includes
initial development records after its current feature overview. Use the server
installation guide for current deployment and operation.

## Features

- Individual accounts and QTH settings: callsign, latitude, longitude, altitude,
  time zone, Maidenhead grid locator, and a 24- or 48-hour prediction period.
- Satellite selection from a locally saved `nasa.all` catalog. There is no
  10-satellite limit; more satellites increase the initial calculation time.
- AOS and LOS times, maximum elevation, azimuth at AOS, and countdowns.
- Current passes and upcoming passes, ordered by AOS. Active passes appear in red
  and show time remaining until LOS.
- LOCAL/GMT controls for the pass times. The current-time panel displays both
  local and GMT time, together with the user's time zone.
- A fixed map centered on the observing location, with satellite position,
  footprint, movement direction, and azimuth/elevation gauges.
- Per-satellite alerts, a minimum peak elevation, local alert hours, and a lead
  time before AOS.
- Web Push delivery to registered phones and PCs, repeated notifications, and
  test notifications.
- Advance and AOS voice announcements while the pass page is open.
- Administration for user roles and shared NASA.ALL updates.
- Japanese and English interfaces, including login, registration, pass predictions,
  QTH settings, satellite selection, scheduled alerts, alert settings, device
  registration, administration, and account deletion.

## Documentation and project layout

This file is in `Manual/`. Run the commands below from the project root,
`satbox-cloud/`, rather than from `Manual/`.

```text
satbox-cloud/
├── satbox_orbit/           Orbit calculations and pass search
├── satbox_web/             Flask application, templates, and browser scripts
├── satbox_notifications/   Scheduling, Push delivery, and private storage
├── satbox_db.py            SQLite compatibility adapter
├── web.py                 Local development server
├── serve_web.py           Waitress behind an HTTPS reverse proxy
├── prepare_notifications.py
├── send_notifications.py
├── setup_push.py
├── setup_admin.py
├── manage_admin.py
├── notification_workers.sh
├── web-qth.json            Shared catalog and prediction configuration
├── nasa.all                Saved TLE catalog
├── iss-qth.source.json     TLE metadata, as configured in web-qth.json
├── deploy/xserver-public/  CGI deployment template
└── Manual/
    ├── README.md
    ├── README_jp.md
    ├── Server_Installation_Guide_EN.md
    └── サーバー設置手順.md
```

The [English installation guide](Server_Installation_Guide_EN.md) covers shared
hosting, CGI, WSGI/VPS deployment, private storage, and background notification
jobs. The [Japanese installation guide](サーバー設置手順.md) covers the same topics.
The original `XSERVER設置手順.txt` has been replaced by these provider-neutral guides.
The names `requirements-xserver.txt` and `deploy/xserver-public/` remain specific
to the existing XSERVER environment.

## Run locally on Windows

Use a Python version compatible with the dependency files. The orbital tools were
developed for Python 3.11 or later. From PowerShell in the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv\Scripts\python.exe web.py --port 8081
```

Open `http://127.0.0.1:8081/`. Stop the server with Ctrl+C. If an existing virtual
environment already contains the dependencies, use it instead of creating another.

For testing from a phone on the same local network:

```powershell
.\.venv\Scripts\python.exe web.py --host 0.0.0.0 --port 8081
```

Open `http://YOUR-PC-LAN-IP:8081/` on the phone. Find the PC's address with `ipconfig`
and allow access on the intended private network if needed. This is for local
testing. The Flask development server is not a production server. Web Push on a
phone requires an HTTPS deployment; ordinary LAN HTTP is insufficient.

## Accounts and QTH

Choose Japanese or English on the login page, then create an account. Registration
collects a login ID, password, callsign, latitude, longitude, altitude, time zone,
grid locator, and prediction period.

- Passwords contain 8–128 characters and are stored as hashes, not plaintext.
- The login ID and callsign are separate. The login ID is not changed in QTH settings.
- Latitude is positive north and negative south; longitude is positive east and
  negative west. Altitude is entered in meters.
- Use a time zone region such as `Asia/Manila`, `Asia/Tokyo`, or `Europe/London`.
  Daylight saving time follows that region's rules.
- Grid locators contain 4, 6, or 8 characters and must match the coordinates.
  Leave the field blank to calculate a 6-character locator automatically.
- The example QTH at latitude 8.209, longitude 123.860001, and altitude 20 m has
  grid locator `PJ18WF`.

Use QTH settings after registration to update your observing location. Accounts
registered in another browser can be tested independently. Cookies are not
separated by TCP port, so use different browser profiles when comparing accounts
on ports 8080 and 8081.

The chosen language is stored in the site's browser `localStorage` and survives
browser restarts. The pass page also has Japanese/English buttons to the left of
Refresh list. Changing language reloads the page. Separate browsers, devices,
private browsing sessions, or cleared site data do not share this preference.

## Pass predictions and map

The pass page uses the saved local TLE file. Its clock and countdowns update every
second, and the list reloads every 60 seconds. Reloading waits for an ongoing voice
announcement to finish.

The prediction cache includes the user, QTH, TLE contents, selected satellites,
and prediction conditions. A missing or invalidated cache causes recalculation.
Normal page refreshes reuse cached results where possible. The calculation engine
does not download TLE data automatically.

Passes outside notification conditions remain in the list with elevation or
alert-hours badges. Alert hours are checked against the scheduled alert time.
The notification checkbox is linked across passes of the same satellite.

Checking a satellite's notification checkbox also selects that pass for the map.
Without a selected pass, the first remaining pass is used. After the selected pass
ends, the map returns to the first remaining pass. The map view remains centered
on the QTH; dragging, wheel zoom, touch zoom, and zoom controls are disabled.

Before AOS, the satellite marker is hidden, Az shows the pass's AOS azimuth, and
El shows 0°. During the pass, the map retrieves the current satellite position
every two seconds and displays its footprint, movement direction, and live Az/El.
The current display policy does not imply that pre-AOS positions are impossible
to calculate.

The map uses Leaflet and OpenStreetMap tiles. Keep attribution and the tile
`referrerPolicy` setting in `satellite-map.js`; suppressing the required referrer
can cause a 403 tile error. See the
[OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/).

TLE update time is the local download/save time from metadata whose SHA-256 matches
the current catalog. Older metadata can fall back to the source's Last-Modified
time. The pass page displays minutes without seconds, so repeated downloads within
the same minute may show the same time. It is not the individual satellite's TLE epoch.

## Satellite selection

The left list contains available satellites; the right list contains your observing
selection. Search the available list, then use:

- `>` to add selected satellites.
- `<` to remove selected satellites.
- `>>` to add all satellites.
- `<<` to remove all satellites.

Save to apply the selection. Empty selections are allowed. Satellites missing from
the latest catalog are marked as having no TLE and can be removed. Removing a
satellite also removes its alert selection and scheduled notifications. Turning an
alert off does not remove the satellite from the observing selection.

## Alerts and notification devices

In Alert settings, select satellites, a minimum peak elevation, lead minutes
before AOS, and local start/end times. The end time can be `24:00`. Overnight ranges
such as 22:00–06:00 are supported; equal start/end times allow alerts all day.

Scheduled alerts show the planned send time, user, satellite, AOS, maximum elevation,
and status. Active passes and passes whose scheduled alert time has already passed
are not added as new scheduled alerts. QTH, TLE, and alert changes regenerate the
schedule.

Use Notification devices on each phone or PC to allow browser notifications and
register that browser. Multiple devices can be registered. A removed device no
longer receives notifications. Device registration is specific to the public URL;
registrations created for a local site do not automatically apply to the hosted site.

The page displays the browser permission (`default`, `denied`, or `granted`) and
the registration stage. If blocked, check both site permissions and OS/browser-app
notification settings. The server must be configured for Web Push, and the
background scheduler and sender must be running.

### Repeated alerts and tests

Set 1–5 sends and a delay of 1–15 seconds between sends. These per-user settings
apply to normal AOS notifications and tests. Set a delay at least as long as the
notification sound. The initial settings are three sends with a seven-second delay.

The test button saves the repeat settings and schedules tests for all your registered
devices. It does not save other unsaved changes in the alert form. Tests ignore
satellite selection, elevation limits, and alert hours, and are limited to once per
minute per user.

The sender tracks successful sends and subsequent send times without blocking
other users with a sleep. Regular sends have timing deadlines, including an AOS
cutoff, so a short lead time may not allow all repetitions. Network delay and device
notification suppression mean delivery intervals and audible sound counts are not
guaranteed. Acceptance by the Push service does not guarantee a displayed or audible
notification on the device.

### Browser voice announcements

While the pass page is open, enabled satellites receive one advance announcement
and one rising announcement at AOS. There is no LOS announcement. Voice uses the
chosen Japanese/English language and available browser voices.

The advance announcement occurs 30 seconds after the configured Push alert time:
a five-minute lead produces speech at four minutes and thirty seconds before AOS.
The AOS rising announcement is not delayed. With a zero-minute lead, only the
rising announcement is generated. Alert-hour and elevation conditions still apply.

Voice announcements are independent of Push repetitions. Events are deduplicated
in the tab's `sessionStorage`; separate tabs can each speak. Old events are not
replayed in a burst after suspension. If the browser blocks speech, the page displays
a notice and a click/tap can retry a recent announcement. Speech is not guaranteed
when the page is closed, locked, or in the background.

## Private storage

Keep application data outside the publicly downloadable directory. Windows defaults
to `%LOCALAPPDATA%\SatBoxCloud\<configuration-path-id>\`. The data includes user
and notification databases, the pass cache, the cookie signing key, and Push keys.

Specify a private location with `--data-dir` on supported commands or with
`SATBOX_DATA_DIR`. The web application, setup commands, scheduler, and sender must
all use the same location. CGI may not inherit variables set in an SSH session.

Back up the complete private data directory with the relevant services stopped.
Changing or deleting `session.key` invalidates existing login cookies. Preserve
production databases and Push keys when uploading application updates.

Authentication uses server-side user IDs and CSRF checks. Login sessions last up to
12 hours under the configured session policy. Login failures are rate limited.
The login script refreshes the CSRF token before submission so an old form can
recover without closing the browser. Failed authentication does not echo the
password back to the page.

## Administration and account deletion

New accounts are ordinary users. To create the first administrator, register the
account normally and run this from the project root on the server:

```bash
.venv/bin/python setup_admin.py YOUR_LOGIN_ID --data-dir /path/to/private-data
```

Initial setup refuses to run if an administrator already exists. Subsequent roles
can be changed in Administration. For shell-based management or recovery:

```bash
.venv/bin/python manage_admin.py grant YOUR_LOGIN_ID --data-dir /path/to/private-data
.venv/bin/python manage_admin.py revoke YOUR_LOGIN_ID --data-dir /path/to/private-data
```

Use the same `--config` and private directory as the deployed application. The last
administrator cannot be demoted or delete their account.

Administration lists users, callsigns, QTH, grids, time zones, selected satellite
counts, registered device counts, and roles. Password hashes, session tokens, and
Push endpoints/keys are not displayed. Ordinary users cannot open this page.

NASA.ALL updates use the fixed HTTPS AMSAT source. The downloader validates the
catalog, uses an update lock, and replaces files atomically. Previous TLE and metadata
are kept in the private `tle-backups/` directory. Updated catalog contents invalidate
old notification schedules and prediction cache keys.

Account deletion requires the current password and an explicit confirmation checkbox.
It removes the account and associated saved data and cannot be undone through the
application. The completion page uses the selected language.

## Server deployment

Follow [Server_Installation_Guide_EN.md](Server_Installation_Guide_EN.md) for the
complete procedure. Preserve the package structure and `__init__.py` files when
uploading. The application needs Python execution, not merely HTML upload.

For typical Python hosting:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-web.txt
```

The existing older XSERVER environment uses a user-installed Python 3.12 and
`requirements-xserver.txt`, including an environment-compatible NumPy and a SQLite
fallback. These versions are not a universal dependency choice for every host.

For CGI deployment, the application remains private; only `index.cgi` and `.htaccess`
form the public entry. The supplied template contains a specific interpreter path,
application path, redirect domain, and `/satbox/` mount that must be adjusted for a
different deployment. Keep CGI files LF-terminated and BOM-free.

For a VPS or suitable WSGI environment, `serve_web.py` starts Waitress on loopback
behind one trusted HTTPS reverse proxy. Configure HTTPS and prefix headers correctly.
Do not publicly use the Flask development server as the production entry.

Disable shared caching for the application's authenticated pages. The application
sends `Cache-Control: no-store`, but hosting/CDN cache rules also need review.

### Web Push setup and background jobs

After the hosted pages work over HTTPS:

```bash
.venv/bin/python setup_push.py --base-url https://YOUR-DOMAIN/satbox --subject mailto:YOUR-EMAIL --data-dir /path/to/private-data
.venv/bin/python prepare_notifications.py --data-dir /path/to/private-data
.venv/bin/python send_notifications.py --data-dir /path/to/private-data
```

Use the actual URL, email address, and private data path. Do not regenerate existing
production keys unnecessarily. With a `/satbox/` mount, the Service Worker scope is
`/satbox/` and notification clicks open `/satbox/pass/<id>`.

Run preparation and sending through permitted scheduled jobs or persistent workers.
The sender reads the saved queue and does not perform orbit calculations. Cron
polling intervals add delay and must fit the delivery deadlines. A web page request
alone does not keep notifications running when the page is closed.

On Linux hosts that allow persistent processes, the included worker manager uses
the project's `.venv/bin/python`, `bash`, `flock`, and `/proc`:

```bash
export SATBOX_DATA_DIR=/path/to/private-data
bash notification_workers.sh start
bash notification_workers.sh status
bash notification_workers.sh stop
bash notification_workers.sh restart
tail -n 20 logs/prepare.log logs/send.log
```

It manages PID files and logs and limits BLAS startup threads. It does not configure
automatic restart after reboot or termination; use the hosting service's facilities
or a service manager where permitted. Do not use persistent workers on plans that
prohibit them.

## Command-line orbital tools

The CLI tools remain useful independently of the web application. Run them from
the project root using the environment's Python executable.

### Single-satellite prediction

```powershell
.\.venv\Scripts\python.exe predict.py example.json
.\.venv\Scripts\python.exe predict.py example.json --horizon 5
```

`example.json` is a historical fixed-TLE test input, not a current prediction source.
Replace its TLE, QTH, and dates before using it for a current prediction or comparison.

Input fields include:

| Field | Meaning |
| --- | --- |
| `satellite_name` | Satellite name |
| `tle_line1`, `tle_line2` | 69-character TLE lines, including checksum; preserve spaces |
| `latitude_deg` | WGS84 geodetic latitude, north positive |
| `longitude_deg` | Longitude, east positive |
| `altitude_m` | Height above the WGS84 ellipsoid in meters |
| `start_utc` | ISO 8601 timestamp with Z or a UTC offset |
| `duration_hours` | Positive prediction duration |
| `horizon_deg` | Geometric elevation threshold for AOS/LOS |

Output includes AOS time/azimuth, maximum elevation and its time, LOS time/azimuth,
and pass duration. Azimuth is north 0°, east 90°. Display precision is not a physical
accuracy guarantee.

The engine uses Skyfield/SGP4, WGS72 satellite constants, and a WGS84 observer. It
does not apply atmospheric refraction, terrain/building obstruction, or horizon-dip
corrections. Time conversions use bundled Skyfield data rather than downloading
external Earth-rotation corrections. Invalid TLE/input or SGP4 failures are reported.
CLI complete-pass searches may omit passes clipped by the requested interval.

### Prepare an input from NASA.ALL

```powershell
.\.venv\Scripts\python.exe prepare_input.py
.\.venv\Scripts\python.exe predict.py iss-qth.json
.\.venv\Scripts\python.exe prepare_input.py --satellite AO-73 --file nasa.all --start "2026-10-07T00:00:00+08:00"
```

Downloading occurs when explicitly running `prepare_input.py` without `--file`.
The default source is AMSAT. `--file` reuses the local catalog; the calculation
engine itself remains offline. Satellite-name matching is case-insensitive.
`--satellite` and `--norad` cannot be used together; the default satellite is ISS.
`--output` changes the generated input filename.

Generated input and source metadata may be overwritten on another run. Preserve
the exact files used for a device comparison. A new TLE can change a historical
prediction even if the observing location and dates are unchanged.

### Multi-satellite predictions

```powershell
.\.venv\Scripts\python.exe predict_multi.py multi-qth.json --start now
.\.venv\Scripts\python.exe predict_multi.py multi-qth.json --min-maxel 0
.\.venv\Scripts\python.exe predict_multi.py multi-qth.json --satellites ISS AO-73 IO-86 --min-maxel 10
```

The supplied `multi-qth.json` contains a historical example date; use `--start now`
or change the date for a current prediction. Relative `tle_file` paths are resolved
against the configuration file's directory. Omitting `satellites` selects all catalog
entries. `horizon_deg` controls AOS/LOS detection; `min_maxel_deg` filters maximum
elevation. Results are ordered by AOS. Errors for individual satellites are reported
without hiding successful results, but the output is then incomplete.

### Compare with ESP32 SatBox

```powershell
.\.venv\Scripts\python.exe compare.py compare-ao-73-example.json
.\.venv\Scripts\python.exe compare.py compare-iss-example.json
```

The comparison examples contain historical screen values and AMSAT TLE data.
They are examples, not proof of agreement with the device's exact TLE. For a valid
comparison, use identical TLE lines, QTH, dates, horizon, altitude reference, and
documented device values. Include an explicit UTC offset for local timestamps.

Differences are Python minus SatBox, using unrounded Python results. No correction
offsets or automatic pass/fail tolerance are applied. The search requires one
complete pass overlapping the reference interval; ambiguous matches are errors.
An optional `aos_az_deg` compares azimuth using the shortest signed angular difference.
`--utc-offset` changes display only, and `--search-margin-minutes` changes the search
interval rather than correcting event times.

Check the TLE character by character, time zones, coordinate signs, units, altitude
reference, geometric horizon, SGP4 constants, search resolution, and display rounding
when investigating differences. Old TLE data increases uncertainty in actual passes.

The original fixed ISS example displayed AOS 15:55:56.795, LOS 16:03:50.947,
maximum elevation 7.375°, and AOS azimuth 2.438° on 2026-10-07 in UTC+8.
These historical numbers must not be interpreted as current pass predictions.

## Maintenance and troubleshooting

- Preserve private databases and keys when updating application files.
- Restart a long-running Flask/WSGI/Waitress server after Python changes. CGI normally
  loads updated code on the next request. Restart notification workers when their
  code changes.
- Reload browser scripts with Ctrl+F5 after uploading updates.
- A missing `push.settings` endpoint after an update can indicate old Python code
  running with newer templates. Restart the web process before rebuilding databases.
- Check CGI/interpreter paths, line endings, file permissions, and server error logs
  for startup failures.
- Verify that web processes, setup commands, and workers use the same private data
  directory if users or registrations appear to be missing.
- Check registration, permissions, conditions, and worker logs when Push is absent.
- Review the tile referrer configuration and provider policy for map 403 errors.

If the project distribution contains the test suite, run it from the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Automated calculation checks do not replace comparison with the physical SatBox
device or verification on the deployed hosting environment.

## References

- [Skyfield satellite calculations](https://rhodesmill.org/skyfield/earth-satellites.html)
- [AMSAT NASA.ALL](https://www.amsat.org/tle/current/nasa.all)
- [Server installation guide](Server_Installation_Guide_EN.md)

de JI1FGX/DU9 · [Contact](mailto:du9@ji1fgx.com)

[Web Push setup, device registration, and testing](Web_Push_Setup_Guide_EN.md)

## Copyright and contact

Copyright © 2026 Kouichi Ueno —  JI1FGX/DU9

For inquiries, please contact [du9@ji1fgx.com](mailto:du9@ji1fgx.com).

## SatBox Cloud introduction and user guide

- Japanese: [https://ji1fgx.com/261008.html](https://ji1fgx.com/261008.html)
- English: [https://ji1fgx.com/en/261008.html](https://ji1fgx.com/en/261008.html)
