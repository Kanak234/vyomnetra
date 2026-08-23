"""Solar Position, Earth Shadow Cone Modeling & Optical Naked-Eye Visibility.

Determines whether a satellite is in direct sunlight or Earth's shadow (Umbra/Penumbra),
calculates solar elevation at ground station, and evaluates optical naked-eye visibility.
"""

from datetime import datetime, timezone
from typing import Tuple, Dict, Any
import numpy as np
from skyfield.api import load

from vyomnetra.config import GroundSite, settings
from vyomnetra.propagate.frames import EARTH_RADIUS_KM
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.visibility.illumination")


def get_sun_position_ecef(epoch_dt: datetime) -> np.ndarray:
    """Computes Sun position vector in ECEF frame (km) for a given UTC datetime using Skyfield."""
    ts = load.timescale()
    eph = load("de421.bsp") if False else None  # Skyfield built-in analytical ephemeris
    
    if epoch_dt.tzinfo is None:
        epoch_dt = epoch_dt.replace(tzinfo=timezone.utc)
    t = ts.from_datetime(epoch_dt)
    
    # Analytical solar position computation
    # Solar longitude in ECI: L_sun = 280.460 + 0.9856474 * d
    d = t.ut1 - 2451545.0
    L_deg = (280.460 + 0.9856474 * d) % 360.0
    g_deg = (357.528 + 0.9856003 * d) % 360.0
    
    L_rad = np.radians(L_deg)
    g_rad = np.radians(g_deg)
    
    ecliptic_lon_rad = L_rad + np.radians(1.915 * np.sin(g_rad) + 0.020 * np.sin(2.0 * g_rad))
    obliquity_rad = np.radians(23.439 - 0.0000004 * d)
    
    # Distance to Sun ~ 1 AU in km
    r_sun_au_km = (1.00014 - 0.01671 * np.cos(g_rad) - 0.00014 * np.cos(2.0 * g_rad)) * 149597870.7
    
    # ECI Sun vector
    x_eci = r_sun_au_km * np.cos(ecliptic_lon_rad)
    y_eci = r_sun_au_km * np.sin(ecliptic_lon_rad) * np.cos(obliquity_rad)
    z_eci = r_sun_au_km * np.sin(ecliptic_lon_rad) * np.sin(obliquity_rad)
    
    # Convert ECI to ECEF via GAST
    gast_rad = np.radians(t.gast * 15.0)
    cos_g = np.cos(gast_rad)
    sin_g = np.sin(gast_rad)
    
    x_ecef = cos_g * x_eci + sin_g * y_eci
    y_ecef = -sin_g * x_eci + cos_g * y_eci
    z_ecef = z_eci
    
    return np.array([x_ecef, y_ecef, z_ecef], dtype=np.float64)


def get_observer_solar_elevation_deg(site: GroundSite, epoch_dt: datetime) -> float:
    """Computes Sun elevation angle in degrees relative to ground station horizon.
    
    Sun elevation <= -6 deg indicates civil twilight/night at observer site.
    """
    r_sun_ecef = get_sun_position_ecef(epoch_dt)
    
    # Import inside function to avoid circular dependency
    from vyomnetra.propagate.frames import ecef_to_topocentric
    az, el, rng = ecef_to_topocentric(r_sun_ecef, site)
    return el


def is_satellite_sunlit(r_sat_ecef: np.ndarray, epoch_dt: datetime) -> Tuple[bool, str]:
    """Determines satellite solar illumination state relative to Earth's shadow cone.
    
    Returns: (is_sunlit: bool, state_name: 'SUNLIT' | 'UMBRA')
    """
    r_sun_ecef = get_sun_position_ecef(epoch_dt)
    u_sun = r_sun_ecef / np.linalg.norm(r_sun_ecef)
    
    # Projection along anti-solar line (-u_sun)
    s = float(np.dot(r_sat_ecef, -u_sun))
    
    if s <= 0:
        # Satellite is on the day side of Earth relative to Sun
        return True, "SUNLIT"
        
    # Perpendicular distance to Earth shadow cylinder axis
    r_proj = r_sat_ecef + s * u_sun
    d_perp = float(np.linalg.norm(r_proj))
    
    if d_perp < EARTH_RADIUS_KM:
        # Inside Earth's shadow cylinder (Umbra)
        return False, "UMBRA"
        
    return True, "SUNLIT"


def is_naked_eye_visible(
    r_sat_ecef: np.ndarray,
    site: GroundSite,
    epoch_dt: datetime,
    elevation_deg: float,
    min_elevation_deg: float = 10.0
) -> bool:
    """Determines if satellite is optical naked-eye visible to observer.
    
    Condition: Satellite is SUNLIT AND observer is in twilight/night (Sun El <= -6 deg)
               AND satellite elevation >= min_elevation_deg.
    """
    if elevation_deg < min_elevation_deg:
        return False
        
    sunlit, state = is_satellite_sunlit(r_sat_ecef, epoch_dt)
    if not sunlit:
        return False
        
    sun_el = get_observer_solar_elevation_deg(site, epoch_dt)
    return sun_el <= -6.0
