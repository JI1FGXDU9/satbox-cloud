from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from .orbit import utc


@dataclass(frozen=True)
class Pass:
    aos: datetime
    aos_az_deg: float
    maximum_at: datetime
    maximum_el_deg: float
    los: datetime
    los_az_deg: float

    @property
    def duration_seconds(self):
        return (self.los - self.aos).total_seconds()


@dataclass(frozen=True)
class Prediction:
    passes: tuple[Pass, ...]
    visible_at_start: bool
    visible_at_end: bool


def refine_crossing(orbit, seed, start, end, horizon, rising):
    """Solve the actual elevation crossing to a 1 ms time bracket."""
    for seconds in (2, 4, 8, 16, 32, 60):
        left = max(start, seed - timedelta(seconds=seconds))
        right = min(end, seed + timedelta(seconds=seconds))
        a = orbit.angles(left)[1] - horizon
        b = orbit.angles(right)[1] - horizon
        if (a <= 0 <= b) if rising else (a >= 0 >= b):
            break
    else:
        raise ValueError('Could not bracket horizon crossing; enlarge prediction window')
    while (right - left).total_seconds() > 0.001:
        middle = left + (right - left) / 2
        above = orbit.angles(middle)[1] > horizon
        if above == rising:
            right = middle
        else:
            left = middle
    return left + (right - left) / 2


def find_passes(orbit, start, end, horizon_deg=0.0):
    """Return complete passes only; report visibility at both window boundaries.

    Multiple culmination events in one pass are allowed; keep the highest.
    AOS/LOS are crossings of the supplied geometric elevation threshold.
    """
    start, end = utc(start), utc(end)
    if end <= start:
        raise ValueError('Prediction end must be after start')
    if not isfinite(horizon_deg) or not -90 < horizon_deg < 90:
        raise ValueError('Horizon must be strictly between -90 and 90 degrees')
    t0, t1 = (orbit.ts.from_datetime(t) for t in (start, end))
    visible_start = orbit.angles_at(t0)[1] > horizon_deg
    visible_end = orbit.angles_at(t1)[1] > horizon_deg
    times, events = orbit.satellite.find_events(
        orbit.observer, t0, t1, altitude_degrees=horizon_deg)
    result, rise, peak = [], None, None
    for time, event in zip(times, events):
        when = time.utc_datetime()
        if event in (0, 2):
            when = refine_crossing(orbit, when, start, end, horizon_deg, event == 0)
            az, el = orbit.angles(when)
        else:
            az, el = orbit.angles_at(time)
        if event == 0:
            rise, peak = (when, az), None
        elif event == 1 and rise is not None:
            if peak is None or el > peak[1]:
                peak = (when, el)
        elif event == 2:
            if rise is not None and peak is not None:
                result.append(Pass(rise[0], rise[1], peak[0], peak[1], when, az))
            rise, peak = None, None
    return Prediction(tuple(result), visible_start, visible_end)
