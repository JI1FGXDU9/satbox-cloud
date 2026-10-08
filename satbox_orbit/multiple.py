"""Framework-independent multi-satellite scheduling."""
from dataclasses import dataclass
from math import isfinite
from .orbit import Orbit, utc
from .passes import Pass, find_passes


@dataclass(frozen=True)
class SatellitePass:
    satellite_name: str
    norad: int
    pass_data: Pass


@dataclass(frozen=True)
class MultiPrediction:
    passes: tuple[SatellitePass, ...]
    excluded_count: int
    notes: tuple[str, ...]
    errors: tuple[str, ...]


def predict_multiple(records, observer, start, end, horizon_deg=0, min_maxel_deg=0):
    start, end = utc(start), utc(end)
    observer.location()
    if end <= start:
        raise ValueError('Prediction end must be after start')
    if not isfinite(horizon_deg) or not -90 < horizon_deg < 90:
        raise ValueError('Horizon must be between -90 and 90 degrees')
    if not isfinite(min_maxel_deg) or not -90 <= min_maxel_deg <= 90:
        raise ValueError('Minimum MAXEL must be within -90..90 degrees')
    passes, notes, errors, excluded = [], [], [], 0
    for record in records:
        try:
            orbit = Orbit(record.name, record.line1, record.line2, observer)
            prediction = find_passes(orbit, start, end, horizon_deg)
            for p in prediction.passes:
                if p.maximum_el_deg >= min_maxel_deg:
                    passes.append(SatellitePass(record.name, orbit.satellite.model.satnum, p))
                else:
                    excluded += 1
            if prediction.visible_at_start or prediction.visible_at_end:
                notes.append(f'{record.name}: incomplete boundary pass omitted')
        except ValueError as exc:
            errors.append(f'{record.name}: {exc}')
    passes.sort(key=lambda row: (row.pass_data.aos, row.satellite_name, row.norad))
    return MultiPrediction(tuple(passes), excluded, tuple(notes), tuple(errors))
