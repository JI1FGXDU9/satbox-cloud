from datetime import timezone
from math import isfinite
from skyfield.api import EarthSatellite, load
from sgp4.io import verify_checksum


def utc(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Datetime must include Z or a UTC offset')
    return value.astimezone(timezone.utc)


class Orbit:
    def __init__(self, name, line1, line2, observer):
        if not name.strip():
            raise ValueError('Satellite name is required')
        for number, line in enumerate((line1, line2), 1):
            if len(line) != 69 or not line.startswith(f'{number} '):
                raise ValueError('TLE lines must be exactly 69 characters')
        verify_checksum(line1, line2)
        if line1[2:7] != line2[2:7]:
            raise ValueError('TLE catalog numbers do not match')
        self.ts = load.timescale(builtin=True)  # No network downloads.
        self.satellite = EarthSatellite(line1, line2, name, self.ts)
        self.observer = observer.location()
        self.relative = self.satellite - self.observer

    def angles_at(self, time):
        position = self.relative.at(time)
        if position.message:
            raise ValueError(f'SGP4 propagation failed: {position.message}')
        el, az, _ = position.altaz()  # Geometric, no refraction.
        if not all(isfinite(v) for v in (el.degrees, az.degrees)):
            raise ValueError('SGP4 returned non-finite coordinates')
        return float(az.degrees), float(el.degrees)

    def angles(self, when):
        return self.angles_at(self.ts.from_datetime(utc(when)))
