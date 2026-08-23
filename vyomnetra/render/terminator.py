"""Solar Terminator Boundary Engine.

Calculates the day/night solar terminator line across Earth's surface for a given UTC datetime.
"""

from datetime import datetime, timezone
from typing import List, Tuple
import numpy as np

from vyomnetra.visibility.illumination import get_sun_position_ecef
from vyomnetra.propagate.frames import EARTH_RADIUS_KM
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.render.terminator")


def get_solar_subpoint(epoch_dt: datetime) -> Tuple[float, float]:
    """Computes sub-solar point (latitude_deg, longitude_deg) on Earth's surface."""
    r_sun_ecef = get_sun_position_ecef(epoch_dt)
    r_norm = np.linalg.norm(r_sun_ecef)
    
    # Sub-solar latitude = asin(z / r)
    sub_lat_rad = np.arcsin(r_sun_ecef[2] / r_norm)
    # Sub-solar longitude = atan2(y, x)
    sub_lon_rad = np.arctan2(r_sun_ecef[1], r_sun_ecef[0])
    
    return float(np.degrees(sub_lat_rad)), float(np.degrees(sub_lon_rad))


def calculate_solar_terminator_points(epoch_dt: datetime, num_points: int = 180) -> Tuple[np.ndarray, np.ndarray]:
    """Calculates lat/lon array and 3D ECEF positions of the day/night solar terminator circle.
    
    Returns:
        (lat_lon_arr: Nx2 array of [lat_deg, lon_deg], ecef_pts: Nx3 array of [X, Y, Z] in km)
    """
    sub_lat_deg, sub_lon_deg = get_solar_subpoint(epoch_dt)
    sub_lat = np.radians(sub_lat_deg)
    sub_lon = np.radians(sub_lon_deg)
    
    # Great circle perpendicular to sub-solar vector
    lons = np.linspace(-180.0, 180.0, num_points)
    lons_rad = np.radians(lons)
    
    # tan(lat) = -cos(lon - sub_lon) / tan(sub_lat)
    # If sub_lat ~ 0 (equinox), lat ~ 90 - abs(lon - sub_lon)
    if abs(np.sin(sub_lat)) < 1e-4:
        lats = 90.0 - np.abs(lons - sub_lon_deg)
        lats = np.clip(lats, -90.0, 90.0)
    else:
        tan_lat = -np.cos(lons_rad - sub_lon) / np.tan(sub_lat)
        lats_rad = np.arctan(tan_lat)
        lats = np.degrees(lats_rad)
        
    lat_lon_arr = np.column_stack((lats, lons))
    
    # Convert lat/lon to 3D ECEF on Earth surface
    rad_lats = np.radians(lats)
    rad_lons = np.radians(lons)
    
    x = EARTH_RADIUS_KM * np.cos(rad_lats) * np.cos(rad_lons)
    y = EARTH_RADIUS_KM * np.cos(rad_lats) * np.sin(rad_lons)
    z = EARTH_RADIUS_KM * np.sin(rad_lats)
    
    ecef_pts = np.column_stack((x, y, z))
    return lat_lon_arr, ecef_pts
