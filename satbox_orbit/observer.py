from dataclasses import dataclass
from math import isfinite
from skyfield.api import wgs84


@dataclass(frozen=True)
class Observer:
    latitude_deg: float
    longitude_deg: float
    altitude_m: float

    def location(self):
        values = (self.latitude_deg, self.longitude_deg, self.altitude_m)
        if not all(isfinite(v) for v in values):
            raise ValueError('Observer coordinates must be finite')
        if not -90 <= self.latitude_deg <= 90:
            raise ValueError('Latitude must be between -90 and 90 degrees')
        if not -180 <= self.longitude_deg <= 180:
            raise ValueError('Longitude must be between -180 and 180 degrees')
        return wgs84.latlon(self.latitude_deg, self.longitude_deg,
                           elevation_m=self.altitude_m)
