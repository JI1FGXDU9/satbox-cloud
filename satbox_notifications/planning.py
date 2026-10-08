"""Pure UTC-based AOS plans with each observer's local quiet hours."""
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class NotificationPreferences:
    enabled_satellites: tuple[str, ...] = ()
    min_maxel_deg: float = 10.0
    lead_minutes: int = 5
    start_minute: int = 420
    end_minute: int = 1440


@dataclass(frozen=True)
class NotificationPlan:
    satellite_name: str
    send_at: datetime
    aos: datetime
    maxel: float
    aos_az: float


def format_minutes(value):
    return f'{value // 60:02d}:{value % 60:02d}'


def parse_time(value, allow_24=False):
    text = str(value).strip()
    if allow_24 and text == '24:00':
        return 1440
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', text):
        raise ValueError('時刻はHH:MMで指定してください。終了時刻には24:00も使用できます。')
    hour, minute = map(int, text.split(':'))
    return hour * 60 + minute


def validate_preferences(data, names):
    selected = data.get('enabled_satellites', [])
    if not isinstance(selected, (tuple, list)) or not all(isinstance(n, str) for n in selected):
        raise ValueError('通知する衛星を選択してください。')
    if len(set(selected)) != len(selected) or not set(selected).issubset(names):
        raise ValueError('利用可能な衛星だけを選択してください。')
    try:
        minimum = float(data.get('min_maxel_deg', 10))
        lead_text = str(data.get('lead_minutes', 5))
        if not re.fullmatch(r'\d{1,3}', lead_text):
            raise ValueError
        lead = int(lead_text)
    except (ValueError, TypeError):
        raise ValueError('最低最大仰角は数値、通知の何分前は整数で指定してください。') from None
    if not math.isfinite(minimum) or not 0 <= minimum <= 90:
        raise ValueError('通知対象の最低最大仰角は0～90度です。')
    if not 0 <= lead <= 180:
        raise ValueError('通知はAOSの0～180分前で指定してください。')
    return NotificationPreferences(tuple(n for n in names if n in selected), minimum, lead,
        parse_time(data.get('start_time', '07:00')), parse_time(data.get('end_time', '24:00'), True))


def allowed_at(local, start, end):
    minute = local.hour * 60 + local.minute
    # Same convention as SatBox: equal start/end means all day;
    # start inclusive, end exclusive; overnight windows are supported.
    if start == end:
        return True
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


def build_plan(passes, preferences, timezone_name, now):
    if now.tzinfo is None:
        raise ValueError('Planning time must include a UTC offset')
    now = now.astimezone(timezone.utc)
    zone = ZoneInfo(timezone_name)
    selected = set(preferences.enabled_satellites)
    result = []
    seen = set()
    for p in passes:
        if p['name'] not in selected or p['maxel'] < preferences.min_maxel_deg:
            continue
        aos = p['aos'].astimezone(timezone.utc)
        send_at = aos - timedelta(minutes=preferences.lead_minutes)
        if aos < now or send_at < now:
            continue  # Never invent a late notification for an already missed deadline.
        if not allowed_at(send_at.astimezone(zone), preferences.start_minute, preferences.end_minute):
            continue
        key = (p['name'], aos)
        if key not in seen:
            seen.add(key)
            result.append(NotificationPlan(p['name'], send_at, aos, p['maxel'], p['aos_az']))
    return tuple(sorted(result, key=lambda p: (p.send_at, p.satellite_name)))
