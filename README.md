[English](README.md) | [日本語](README_JP.md)

# SatBox Cloud

SatBox Cloud is a web application for predicting amateur radio satellite passes and receiving AOS alerts in a smartphone or computer browser.

**[Open SatBox Cloud](https://ji1fgx.com/satbox)**

This web version of SatBox focuses on satellite pass prediction and AOS alerts. It does not include radio Doppler control or antenna rotator control. No dedicated Android app is required. On an iPhone, add the site to your Home Screen using Safari.

**[about SatBox Cloud](https://ji1fgx.com/en/260909.html)**

## Main features

- Predict satellite passes for each user's observing location (QTH)
- Set callsign, email address, latitude, longitude, altitude, time zone, and grid locator
- Select satellites from the NASA.ALL catalog
- Display passes in progress and upcoming passes over the next 24 or 48 hours
- Check AOS/LOS times, peak elevation, AOS azimuth, and countdowns
- Show the satellite name and countdown in red during a pass, with the time remaining until LOS
- View the target satellite's position, visibility footprint, azimuth, and elevation on the map during a pass
- Choose satellites for alerts, a minimum peak elevation, how many minutes before AOS to notify you, and allowed alert hours
- Register multiple smartphones and computers under the same account
- Set the number of Web Push notifications and the interval between them
- Tap a notification to open the details of that satellite pass
- Check upcoming notifications in the scheduled alerts list
- Hear voice announcements before AOS and at AOS while the pass list is open
- Use administration to view users and email addresses, change roles, delete regular users, and update NASA.ALL
- Switch between Japanese and English

## Getting started and documentation

For initial setup, follow this order: Create an account → Satellite selection → AOS notification settings → Notification devices → Send a test notification.

- [English introduction and user guide](https://ji1fgx.com/en/261008.html)
- [Japanese introduction and user guide](https://ji1fgx.com/261008.html)
- [Detailed English manual](Manual/README.md)
- [Detailed Japanese manual and development history](Manual/README_jp.md)
- [Server installation guide](Manual/Server_Installation_Guide_EN.md)
- [Web Push setup guide](Manual/Web_Push_Setup_Guide_EN.md)

Allow notifications in your device and browser settings to receive Web Push alerts. Voice announcements work while the pass list is open. Notification sounds and delivery times depend on device settings and network conditions.

## License

This project is licensed under the [MIT License](LICENSE). Third-party libraries and services retain their respective licenses and terms.

## Copyright and contact

Copyright © 2026 Kouichi Ueno — JI1FGX/DU9

For inquiries: [du9@ji1fgx.com](mailto:du9@ji1fgx.com)
