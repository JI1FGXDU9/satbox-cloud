"""Shared cached prediction snapshot for Web display and notification planning."""
import hashlib
import json
import math
from pathlib import Path
from satbox_orbit.catalog import read_catalog, select_records


class PredictionService:
    def __init__(self, config_path, cache):
        self.config_path = Path(config_path)
        self.cache = cache

    def catalog(self, user=None, all_records=False):
        config = json.loads(self.config_path.read_text(encoding='utf-8-sig'))
        raw = (self.config_path.parent / config['tle_file']).read_bytes()
        catalog = read_catalog(raw.decode('utf-8-sig'))
        if all_records:
            return config, raw, catalog
        names = self.selected_names(user,config,catalog)
        # A satellite removed from a newer catalog must not break all predictions.
        available = {r.name:r for r in catalog}
        records = tuple(available[n] for n in names if n in available)
        return config, raw, records

    @staticmethod
    def selected_names(user, config, catalog):
        saved = user.get('satellite_selection') if user else None
        if saved is None:
            names = config.get('satellites')
            return list(names) if names is not None else [r.name for r in catalog]
        names = json.loads(saved)
        if not isinstance(names,list) or not all(isinstance(n,str) for n in names):
            raise ValueError('Invalid satellite selection')
        return names

    def get(self, user, now):
        config, raw, records = self.catalog(user)
        horizon, minimum = float(config['horizon_deg']), float(config['min_maxel_deg'])
        if not math.isfinite(horizon) or not -90 < horizon < 90:
            raise ValueError('Invalid horizon')
        if not math.isfinite(minimum) or not 0 <= minimum <= 90:
            raise ValueError('Invalid display maximum elevation threshold')
        digest = hashlib.sha256(raw).hexdigest()
        # Keep all passes in the cache. Display and notification filters are separate.
        rows, errors, generated, hit = self.cache.get(user, dict(config, horizon_deg=horizon,
            min_maxel_deg=0.0), records, digest, now)
        selected = self.selected_names(user,config,records)
        missing = [name for name in selected if name not in {r.name for r in records}]
        errors = list(errors) + [f'{name}: NASA.ALLにTLEがありません。衛星選択を確認してください。' for name in missing]
        source = dict(tle=digest, generated=generated.isoformat(), horizon=horizon,
                      satellites=[r.name for r in records],
                      passes=[(r['name'], r['aos'].isoformat(), r['los'].isoformat()) for r in rows])
        return config, raw, records, rows, errors, generated, hit, source
