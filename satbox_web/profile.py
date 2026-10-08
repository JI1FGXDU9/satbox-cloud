"""QTH input validation and Maidenhead locator, without a Web dependency."""
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def maidenhead(latitude, longitude, length=6):
    # Clamp the north/east boundary to the last valid cell.
    x = min(longitude + 180, math.nextafter(360.0, 0.0))
    y = min(latitude + 90, math.nextafter(180.0, 0.0))
    parts = []
    for divisor, count, alphabet in ((20, 18, 'ABCDEFGHIJKLMNOPQR'),
                                      (2, 10, '0123456789'),
                                      (1 / 12, 24, 'ABCDEFGHIJKLMNOPQRSTUVWX'),
                                      (1 / 120, 10, '0123456789')):
        ix, iy = min(int(x / divisor), count - 1), min(int(y / (divisor / 2)), count - 1)
        parts.extend((alphabet[ix], alphabet[iy]))
        x -= ix * divisor
        y -= iy * divisor / 2
        if len(parts) == length:
            return ''.join(parts)


def validate_profile(data):
    callsign = str(data.get('callsign', '')).strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9/\-]{1,31}', callsign):
        raise ValueError('コールサインは英数字・/・-で2～32文字にしてください。')
    try:
        latitude = float(data['latitude_deg'])
        longitude = float(data['longitude_deg'])
        altitude = float(data['altitude_m'])
    except (ValueError, TypeError, KeyError):
        raise ValueError('緯度・経度・高度を数値で入力してください。') from None
    if not all(math.isfinite(v) for v in (latitude, longitude, altitude)):
        raise ValueError('緯度・経度・高度は有限の数値にしてください。')
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError('緯度は-90～90度、経度は-180～180度です。')
    if not -500 <= altitude <= 10000:
        raise ValueError('高度は-500～10000 mで指定してください。')
    name = str(data.get('timezone_name', '')).strip()
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('有効なタイムゾーン地域名を指定してください。例: Asia/Manila') from None
    grid = str(data.get('grid_locator', '')).strip().upper()
    if not grid:
        grid = maidenhead(latitude, longitude)
    if not re.fullmatch(r'[A-R]{2}[0-9]{2}(?:[A-X]{2}(?:[0-9]{2})?)?', grid):
        raise ValueError('グリッドロケーターは4・6・8文字で指定してください。例: PJ18WF')
    if grid != maidenhead(latitude, longitude, len(grid)):
        raise ValueError('グリッドロケーターが緯度・経度と一致しません。空欄にすると自動計算します。')
    try:
        hours = int(data.get('duration_hours', 24))
    except (ValueError, TypeError):
        raise ValueError('予測範囲は24時間または48時間です。') from None
    if hours not in (24, 48):
        raise ValueError('予測範囲は24時間または48時間です。')
    return dict(callsign=callsign, latitude_deg=latitude, longitude_deg=longitude,
                altitude_m=altitude, timezone_name=name, grid_locator=grid, duration_hours=hours)


def validate_email(value, required=False):
    email = str(value).strip()
    if not email and not required:
        return ''
    if not email or len(email) > 254 or not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", email):
        raise ValueError('有効なメールアドレスを入力してください。')
    local, domain = email.rsplit('@', 1)
    if len(local) > 64 or local.startswith('.') or local.endswith('.') or '..' in local or any(len(label) > 63 for label in domain.split('.')):
        raise ValueError('有効なメールアドレスを入力してください。')
    return local + '@' + domain.lower()
