"""Current satellite map coordinates using the saved QTH and local TLE."""
import logging
import math
from datetime import timezone
from flask import Blueprint, current_app, g, jsonify, request
from skyfield.api import wgs84
from satbox_orbit import Observer
from satbox_orbit.orbit import Orbit
from .auth import login_required

satellite_map = Blueprint('satellite_map', __name__)


@satellite_map.get('/mapdata')
@login_required
def data():
    observer = Observer(g.user['latitude_deg'], g.user['longitude_deg'], g.user['altitude_m'])
    result = dict(valid=False, observerLat=observer.latitude_deg, observerLon=observer.longitude_deg)
    try:
        _, _, records = current_app.extensions['predictions'].catalog(g.user)
        name = request.args.get('name', records[0].name if records else '')
        record = next((r for r in records if r.name == name), None)
        if record is None:
            return jsonify(dict(result, error='表示対象の衛星がありません')), 404
        orbit = Orbit(record.name, record.line1, record.line2, observer)
        now = current_app.extensions['clock']().astimezone(timezone.utc)
        time = orbit.ts.from_datetime(now)
        position = orbit.satellite.at(time)
        if position.message:
            raise ValueError('SGP4 propagation failed')
        lat, lon = wgs84.latlon_of(position)
        altitude = wgs84.height_of(position).km
        az, el = orbit.angles_at(time)
        values = (lat.degrees, lon.degrees, altitude, az, el)
        if not all(math.isfinite(v) for v in values) or altitude <= 0:
            raise ValueError('Invalid satellite position')
        radius = 6371.0
        result.update(valid=True, name=record.name, satLat=float(lat.degrees),
                      satLon=float(lon.degrees), altKm=float(altitude), az=az, el=el,
                      footprintKm=radius * math.acos(radius / (radius + altitude)))
        return jsonify(result)
    except (ValueError, KeyError, TypeError, OSError, OverflowError):
        logging.exception('Cannot calculate satellite map position')
        return jsonify(dict(result, error='衛星位置を計算できません')), 503
