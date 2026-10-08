[日本語](開発仕様書.md) | [English](Development_Specification_EN.md)

# SatBox Cloud Development Specification
Created: 7 October 2026
Revised: 8 October 2026
Scope: current source code and agreed interface/operational behavior at this revision

## 1. Purpose and scope

Provide SatBox orbit calculations, pass predictions, and AOS alerts as an independent
Python application with individual QTH settings for multiple web users.
The existing public deployment is https://ji1fgx.com/satbox/. Other hosts and domains
are also supported through deployment-specific configuration.
The cloud application operates independently of the ESP32 firmware.
Rotator control, radio control, Doppler correction, and automatic antenna tracking
are outside its scope.

## 2. Development history and status

Development began with fixed-input device comparisons, single-satellite calculations,
and multi-satellite predictions. Web interfaces, accounts, individual predictions,
Web Push, administration, maps, and bilingual display were subsequently added.
Early instructions not to implement web or registration features were stage-specific
constraints, not current limitations. This document records implemented behavior,
not just proposed design. Numerical comparisons and deployment acceptance are tracked
separately; similar displayed values do not prove exact device agreement or delivery.

## 3. Actual structure and responsibilities

```text
satbox-cloud/
```text
satbox_orbit/             Framework-independent orbit and pass engine
  observer.py            QTH and WGS84 observing location
  orbit.py               TLE validation, SGP4, AZ/EL at a given time
  passes.py              AOS/LOS, peak elevation, result types
  catalog.py             NASA.ALL parsing and record selection
  multiple.py            Multi-satellite computation, filtering, ordering
  comparison.py          Device comparison
  display.py             CLI formatting
satbox_web/              Flask application, authentication, pages, administration
  predictions.py         Configuration, selection, and cache integration
  cache.py               SQLite prediction cache
  storage.py             Users, QTH, roles, satellite selection
  profile.py             QTH validation and grid calculation
  notifications.py       Alert settings, schedule, checkbox updates
  push.py                Device APIs, test requests, notification detail page
  tle_update.py          Administrator download, validation, catalog replacement
  satellite_map.py        Current-position API
  templates/             HTML pages
  static/                Styles, browser behavior, translation, Service Worker
satbox_notifications/    Conditions, planning/storage, delivery, tests, private paths
satbox_db.py              SQLite compatibility adapter
predict.py / predict_multi.py / compare.py / prepare_input.py  CLI tools
web.py                   Local development server
serve_web.py              Waitress behind an HTTPS proxy
prepare_notifications.py / send_notifications.py  Background processes
setup_push.py / setup_admin.py / manage_admin.py  Setup and administration CLI
notification_workers.sh  Linux worker manager
deploy/xserver-public/    Public CGI entry template
Manual/                  Bilingual README, installation guides, specifications
```
```

The orbit engine does not require a user ID, callsign, database, delivery method,
or Flask. Downloading is separate from calculations; planning is separate from
delivery. The calculation engine does not make network requests.

## 4. Time, coordinates, and units

Internal timestamps are timezone-aware UTC. External times require Z or a UTC offset.
Display and alert-hour checks use the user's IANA time zone. ZoneInfo applies regional
daylight-saving rules.
Latitude: WGS84 geodetic, north positive, −90 to 90 degrees.
Longitude: east positive, −180 to 180 degrees.
Altitude: meters, accepted range −500 to 10,000; used as WGS84 ellipsoid height.
Users and device comparisons must account for differences from elevation above sea level.
AZ: north 0°, east 90°. EL: geometric elevation. Map altitude and footprint use km.
Displayed precision and numerical search resolution do not guarantee physical accuracy.

## 5. TLE and shared configuration

web-qth.json selects the saved catalog with tle_file; relative paths use the config
directory. tle_metadata_file identifies download/save metadata, Last-Modified,
SHA-256, and related fields. horizon_deg is the shared geometric AOS/LOS threshold.
satellites provides defaults until a user saves an individual selection.
Orbit construction requires 69-character TLE lines with valid checksums and matching
satellite numbers. Catalog parsing, update-time checks, and strict orbit construction
are separate stages. Invalid TLE/propagation errors are not treated as valid predictions.
Ordinary page rendering and the orbit engine do not automatically download TLE data.

## 6. Orbit/pass calculation and device comparison

Use Skyfield EarthSatellite/SGP4 with default WGS72 satellite constants and a WGS84
observer. Time conversion uses bundled data without automatic Earth-rotation downloads.
No refraction, terrain/building obstruction, or horizon-dip correction is applied.
Use find_events candidates and refine AOS/LOS crossings by bisection. For passes with
multiple maxima, use the highest peak. Basic results require complete AOS/LOS events;
clipped interval boundaries produce warnings. Record individual failures while retaining
successful results for other satellites.

Comparisons require identical TLE, QTH, dates, horizon, and altitude reference.
Differences are Python minus SatBox; azimuth uses the shortest signed angular difference.
Compare only when exactly one complete candidate overlaps the reference interval.
Do not add arbitrary correction offsets or pass/fail tolerances. Check SGP4 constants,
UTC conversion, numerical types, search resolution, rounding, and initially visible
passes. Historical fixed-TLE examples are not current prediction inputs.

## 7. Accounts and QTH

Login ID: 3–64 letters/digits or _ . - /, beginning with a letter or digit.
Password: 8–128 characters with matching confirmation; stored as an scrypt hash.
Callsign: 2–32 letters/digits or / -, stored uppercase.
Latitude, longitude, and altitude must be finite and within the specified ranges.
Require a valid regional time zone. Maidenhead locators have 4, 6, or 8 characters
and must match coordinates; a blank field generates a six-character locator.
Prediction duration is 24 or 48 hours. QTH can be changed after registration.
Login ID and callsign are distinct; QTH settings do not change the login ID.
New users have ordinary privileges; registration cannot set the administrator flag.

## 8. Authentication and sessions

Use sessions and CSRF validation for authentication and state changes. Login failures
are limited by login ID and IP; ten failures trigger a 15-minute restriction.
The configured session duration is 12 hours; the user's session_token is also checked.
The login script retrieves a fresh same-origin token from /login-token before posting.
An old/mismatched form does not authenticate and is replaced without echoing a password.
Cookies are HttpOnly and SameSite=Lax; enable Secure for production HTTPS.
Individual reads and updates derive ownership from the authenticated server-side ID.

## 9. Satellite selection

Available NASA.ALL satellites appear on the left, the user's observing selection on
the right. Support search, selected/all additions and removals, and saving. Narrow
screens stack the lists. There is no ten-satellite limit; empty selections are valid.
Reject unknown or duplicate posted satellites. Display missing saved TLE entries so
users can remove them. Store selection per user and use it for predictions and alert
choices. Removing a satellite clears its alert selection and queue atomically.
Disabling an alert is distinct from removing an observing satellite.

## 10. Prediction cache

Store payload, generation time, expiry, and owner in passes.sqlite3. Keys include
user ID, QTH, duration, TLE hash/lines, satellite selection, horizon, and calculation
conditions. Successful results last 1,800 seconds; partial errors last 60 seconds.
Search with one hour of padding before now and after the requested duration.
The current display extraction condition is now < LOS <= now + duration. A pass
whose AOS is before the interval end but whose LOS is later is excluded by this rule.
Serialize cache misses in the cache database without locking the account database
during orbital computation. Web predictions use min_maxel_deg=0 to retain passes
outside alert elevation conditions.

## 11. Pass page

List active/upcoming passes by AOS and hide rows after LOS. Columns are satellite/
alert checkbox, countdown, AOS, LOS, peak elevation, AOS azimuth, and alert status.
Keep condition-excluded passes with low-elevation or alert-hours badges.
Update countdowns every second; active passes are red and count down to LOS.
Reload the list every 60 seconds. Use server time plus performance.now rather than
relying entirely on the device clock.
The summary shows QTH, coordinates/grid, both LOCAL/GMT clocks, TLE update time,
and catalog filename. Coordinates use three decimals; TLE time omits seconds.
Show local date/time, GMT time, and time zone on one line. LOCAL/GMT controls affect
AOS/LOS display only, not internal UTC or alert-hour checks. Store that display mode
in localStorage under satbox-time-mode. Use a table on desktop and labeled cards on
narrow screens. Place language controls to the left of Refresh list.

## 12. Map and gauges

Place the map left of the list on wide screens and above it on narrow screens.
Center on the saved QTH at fixed zoom 3. Disable dragging, wheel/pinch/double-click
zoom, keyboard movement, and zoom buttons. Recenter after resizing and do not restore
old center/zoom settings.
Checking an alert checkbox selects that pass for the map. Without a selection, use
the first remaining pass. After the selected pass ends, return to the first pass.
Preserve selection across reloads in user-specific sessionStorage. There are no
separate map links or satellite dropdowns.
Before AOS: hide satellite, footprint, and direction; show AOS azimuth on AZ and 0°
on EL, including needles. During a pass: retrieve /mapdata every two seconds and
update name, subpoint, altitude, AZ, and EL.
Footprint radius in km = 6371 × acos(6371 / (6371 + altitude_km)).
Estimate movement direction from consecutive positions and draw a red dashed line.
Show the observing location separately. Clear stale graphics on selection changes
and discard responses for an old target. Reduce polling in hidden tabs; display
retrieval failures and retry. Use Leaflet 1.9.4 and OpenStreetMap with attribution
and a suitable tile referrer policy. Pre-AOS hiding is a UI rule, not a calculation limit.

## 13. Alert conditions and schedules

Per-user settings: enabled satellites, peak elevation 0–90°, lead time 0–180 minutes,
and start/end times. Defaults: 10°, five minutes, 07:00–24:00, no enabled satellites.
Scheduled send time = AOS − lead_minutes. Convert it to local time for hour checks.
Start is inclusive; end exclusive. Support overnight windows; equal times allow all day.
Do not create new alerts with a missed send time or past AOS. Storage may preserve
existing imminent jobs within the delivery grace period. Deduplicate satellite/pass
plans and invalidate/regenerate after QTH, selection, condition, or TLE changes.
The schedule page shows pending plans, not a full delivery-history interface.

## 14. Background processing

prepare_notifications.py generates per-user predictions and plans. In --loop mode,
check every five seconds for catalog/config file and user QTH, zone, duration, or
selection changes. Refresh after changes or 15 minutes. Web settings saves also
invalidate plans.
send_notifications.py sends stored regular/test jobs only and does not invoke the
orbit engine. --loop checks every second. Use permitted Cron or persistent operation.
notification_workers.sh uses PID files, logs, flock, Linux /proc, and the project's
.venv/bin/python. Restart after a server reboot requires separate configuration.

## 15. Web Push, repetitions, and tests

Require HTTPS, a Service Worker, browser/OS permission, and server-side keys.
Subscriptions belong to users and can be labeled, registered, and removed. Validate
endpoint, keys, owner, and limits; encrypt stored subscription information.
Notification clicks open a saved-pass detail URL whose ownership is checked.
Track regular delivery count, next time, attempts, and result per pass/device.
Support 1–5 sends and 1–15 seconds between sends; defaults are three and seven.
Regular alerts and tests share preferences. After successful regular sends, schedule
the next time without blocking other users by sleeping.
Regular sends check the 120-second lateness window and the five-second AOS grace,
among other conditions. Do not send to registrations created after the scheduled
time, jobs outside conditions, or removed queues. Remove invalid 404/410 subscriptions.
Push-service acceptance does not guarantee device display or sound.
Allow tests once per minute per user, scheduled for all registered devices. Device
settings determine sound. Test buttons save repeat preferences, not other unsaved
alert conditions. Tests ignore hours/elevation and discard requests older than 120
seconds. Test repetitions use a separate delivery implementation with per-device
waiting. Delivery delays, OS suppression, and short leads prevent guarantees about
full repeat counts or exact sound intervals.

## 16. Voice announcements

While the pass page is open, use speechSynthesis for enabled satellites. Advance
speech occurs at Push send time + 30 seconds; a five-minute lead speaks at 4:30 before
AOS. Rising speech occurs at AOS without that delay. Zero lead produces rising only;
there is no LOS speech. Apply peak-elevation and separate advance/AOS hour checks.
Speak each event once, independently of Push repeats; queue overlapping satellites.
Deduplicate within the tab using sessionStorage and do not replay stale suspended
events in a burst. Delay list reloads while speaking. A click/tap may retry a recent
browser-blocked utterance. Japanese uses phonetic satellite names; English uses
English text and voices. Closed/locked/background pages or unsupported browsers
cannot be guaranteed to speak.

## 17. Japanese/English interfaces

Store ja/en under satbox-language in same-origin localStorage. Select on login or
pass pages; the same site's browser keeps the preference across restarts. Cleared
data, other browsers/devices, and private sessions do not share it.
Covered pages: login, registration, QTH, passes, satellite selection, schedule,
alert settings, devices, administration, withdrawal, and completion.
login.js, register-language.js, and pass-language.js implement page translation.
Pass-related pages also translate dynamic text, aria-label, title, data labels,
and placeholders. Language is not stored in the server-side user profile.
Generic server errors, notification detail pages, OS permission/native validation
messages, and server-delivered Push bodies are separate from this browser translation
and are not fully bilingual. Without JavaScript, Japanese server rendering is the default.

## 18. Administration and TLE updates

Only administrators can access administration and role/catalog changes. User rows
show ID, callsign, QTH, grid, zone, satellite/device counts, and role; do not show
password hashes, session tokens, or Push secrets. Register normally and use
setup_admin.py for the first administrator; refuse initial setup if one exists.
Use the page for subsequent promotion/demotion; preserve the last administrator.
manage_admin.py provides recovery administration. Use the same private data/config.
Download from the fixed AMSAT HTTPS source with a 2 MB limit; validate duplicate
names, pairs, and models. Lock concurrent updates, back up TLE/metadata in tle-backups,
and replace atomically. Metadata includes saved_utc, last_modified, sha256, source,
and satellite_count. With a matching digest, display saved_utc first, falling back
to Last-Modified for older records. Invalidate old notification queues after updates;
changed contents generate new cache keys. An identical download updates its save
timestamp without requiring different orbital results.

## 19. Account deletion

Require current password and confirmation checkbox. Delete the authenticated user's
account and associated settings/data, maintaining account/cache consistency.
The last administrator must appoint another administrator before deleting their
account. Clear the session on success and redirect to the completion page.
There is no application undo/recovery feature. Operators manage backup retention.

## 20. Routes and APIs

Paths below are internal; prepend /satbox for that deployment.
GET /: pass page. GET/POST /login, /register, /settings, /withdraw.
POST /logout. GET /login-token, /withdrawn.
GET/POST /satellites, /notification-settings. GET /notification-queue.
POST /notification/satellite: checkbox alert update with form data and CSRF.
GET /push-settings, /service-worker.js, /pass/<identity>.
POST /push/register, /push/current, /push/remove, /push/test.
GET /admin. POST /admin/update-tle, /admin/user-role.
GET /mapdata?name=<satellite>: login required; only the user's selected catalog.
Map JSON: valid, observerLat, observerLon; successful results also include name,
satLat, satLon, altKm, az, el, footprintKm. No target returns 404; calculation/file
failures return 503; unauthenticated users redirect to login.
Apply CSRF to changes, role checks to administration, and ownership to individual data.

## 21. Storage and security

Private paths come from SATBOX_DATA_DIR, --data-dir, or the OS user-data location.
users.sqlite3 contains users, login_attempts, notification_settings, notification_passes,
notification_queue, notification_catalog_state, notification_plan_state,
push_subscriptions, push_deliveries, push_test_preferences, push_test_requests,
and push_test_jobs, among others. passes.sqlite3 contains predictions.
Keep session.key and Push configuration/private/encryption keys private.
Initialize required schema additions without unnecessarily replacing existing DBs/keys.
Web, CLI, Cron, and workers must use the same private directory.
Responses set no-store, nosniff, X-Frame-Options:DENY, Referrer-Policy:same-origin,
and HSTS for HTTPS. Tiles override referrer policy appropriately.
Trust only configured proxy hops/headers; separate public files from secrets.
These safeguards and documentation do not constitute a completed penetration test.

## 22. Deployment and operations

Method A: Python CGI and URL rewriting, with public index.cgi/.htaccess and private
application files. Method B: WSGI/Waitress behind HTTPS. Do not publicly deploy the
Flask development server. Adjust hard-coded paths, domain, and mount in CGI templates.
Use requirements-web.txt generally and requirements-xserver.txt for the existing
environment-specific XSERVER setup. Check shared-host package support, CPU/CGI limits,
Cron, and persistent-process rules. Exclude authenticated/QTH/subscription content
from shared caches. Preserve databases/keys, restart persistent web or changed workers,
and reload browser assets after updates. Keep logs/backups private and monitor size
and worker state. See the two Server Installation Guides in Manual/.

## 23. Verification and acceptance

Calculations: fixed TLE, UTC, horizon crossings, maxima, boundaries, bad inputs, device parity.
Accounts: registration, login limits, CSRF, QTH validation, user isolation.
Predictions: cache reuse/invalidation, active passes, LOS removal, reason badges.
Map: QTH center, fixed interactions, checkbox target, stale responses, pre-AOS gauges,
live position, failure indication.
Alerts: hours/overnight ranges, threshold, deadlines, deduplication, repetition,
test limits, invalid subscriptions.
Speech: language, 30-second advance delay, AOS, deduplication, blocked retries.
Language: persistence/page inheritance, dynamic text/dialogs, retained values and time mode.
Administration/deletion: ordinary-user denial, last-admin protection, backups, identity.
Deployment: HTTPS, CGI/WSGI routing, private storage, registration, real worker delivery.
The user has confirmed deployed map and GMT display. Individual code/render checks
are distinct from acceptance on every device and host. Completing this specification
does not itself send notifications, delete accounts, change roles, or configure hosting.

## 24. Limitations and future work

Actual pass errors depend on TLE age, altitude reference, and model limitations.
Do not guarantee sound counts/timing, background speech, tile availability, or large
shared-host capacity. Potential additions include server-persisted language and
fully localized Push/detail/error pages, consolidated translations, scale testing,
scheduled TLE updates, operational monitoring, and stronger migration/recovery guides.
These are future candidates, not implemented behavior. Update both editions together
when specifications change.
