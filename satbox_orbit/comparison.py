"""Compare raw prediction values; never apply calibration offsets."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from .orbit import utc
from .passes import Pass, find_passes


@dataclass(frozen=True)
class ReferencePass:
    aos: datetime
    los: datetime
    maximum_el_deg: float
    aos_az_deg: float | None = None

    def validate(self):
        aos, los = utc(self.aos), utc(self.los)
        if los <= aos:
            raise ValueError('SatBox LOS must be after AOS (include the correct dates)')
        if not isfinite(self.maximum_el_deg) or not -90 <= self.maximum_el_deg <= 90:
            raise ValueError('SatBox MAXEL must be finite and within -90..90 degrees')
        if self.aos_az_deg is not None and (
                not isfinite(self.aos_az_deg) or not 0 <= self.aos_az_deg < 360):
            raise ValueError('SatBox AOS AZ must be finite and within 0..360 (exclusive) degrees')
        return ReferencePass(aos, los, self.maximum_el_deg, self.aos_az_deg)


@dataclass(frozen=True)
class Comparison:
    reference: ReferencePass
    predicted: Pass

    @property
    def aos_difference_seconds(self):
        return (self.predicted.aos - self.reference.aos).total_seconds()

    @property
    def los_difference_seconds(self):
        return (self.predicted.los - self.reference.los).total_seconds()

    @property
    def maxel_difference_degrees(self):
        return self.predicted.maximum_el_deg - self.reference.maximum_el_deg

    @property
    def aos_az_difference_degrees(self):
        if self.reference.aos_az_deg is None:
            return None
        return (self.predicted.aos_az_deg - self.reference.aos_az_deg + 180) % 360 - 180


def compare_pass(orbit, reference, horizon_deg, search_margin_minutes=30):
    reference = reference.validate()
    if not isfinite(search_margin_minutes) or search_margin_minutes <= 0:
        raise ValueError('Search margin must be finite and positive')
    margin = timedelta(minutes=search_margin_minutes)
    result = find_passes(orbit, reference.aos - margin, reference.los + margin, horizon_deg)
    candidates = [p for p in result.passes
                  if p.aos < reference.los and p.los > reference.aos]
    if len(candidates) != 1:
        raise ValueError(f'Expected exactly one overlapping complete Python pass; found '
                         f'{len(candidates)}. Check TLE, date, UTC offset, QTH, horizon, '
                         'or increase --search-margin-minutes. No automatic pairing performed.')
    return Comparison(reference, candidates[0])
