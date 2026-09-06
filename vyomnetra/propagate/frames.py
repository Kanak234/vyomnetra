"""Coordinate Frame Transformations Engine for VYOMNETRA.

Implements TEME -> ECEF (ITRF), TEME -> ECI (GCRF/J2000), and
ECEF -> Topocentric Azimuth/Elevation/Range transformations.
"""

from datetime import datetime, timezone
from typing import Tuple, Union, Optional
import numpy as np
from skyfield.api import load, wgs84, Distance, Velocity

from vyomnetra.config import GroundSite, settings
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.propagate.frames")

# Earth rotation rate in rad/s
EARTH_ROTATION_RATE_RAD_S = 7.292115146706979e-5
# Earth equatorial radius in km (WGS-84)
EARTH_RADIUS_KM = 6378.137


def compute_gast_rad(epoch_dt: datetime) -> float:
    """Computes Greenwich Apparent Sidereal Time (GAST) in radians for a given UTC datetime."""
    ts = load.timescale()
    if epoch_dt.tzinfo is None:
        epoch_dt = epoch_dt.replace(tzinfo=timezone.utc)
    t = ts.from_datetime(epoch_dt)
    gast_hours = t.gast
    return np.radians(gast_hours * 15.0)


def teme_to_ecef(
    r_teme: np.ndarray,
    v_teme: np.ndarray,
    epoch_dt: datetime
) -> Tuple[np.ndarray, np.ndarray]:
    """Transforms position and velocity vectors from TEME to ECEF (ITRF) frame.
    
    Args:
        r_teme: Position vector (3,) or (N, 3) in km
        v_teme: Velocity vector (3,) or (N, 3) in km/s
        epoch_dt: UTC datetime
        
    Returns:
        r_ecef: Position vector in ECEF (km)
        v_ecef: Velocity vector in ECEF (km/s)
    """
    gast_rad = compute_gast_rad(epoch_dt)
    cos_g = np.cos(gast_rad)
    sin_g = np.sin(gast_rad)

    # 3D Rotation matrix Rz(gast)
    R_z = np.array([
        [cos_g,  sin_g, 0.0],
        [-sin_g, cos_g, 0.0],
        [0.0,    0.0,   1.0]
    ], dtype=np.float64)

    if r_teme.ndim == 1:
        r_ecef = R_z @ r_teme
        # Velocity in rotating frame: v_ecef = Rz @ v_teme - omega x r_ecef
        v_rot = R_z @ v_teme
        omega_x_r = np.array([
            -EARTH_ROTATION_RATE_RAD_S * r_ecef[1],
             EARTH_ROTATION_RATE_RAD_S * r_ecef[0],
             0.0
        ], dtype=np.float64)
        v_ecef = v_rot - omega_x_r
    else:
        r_ecef = (R_z @ r_teme.T).T
        v_rot = (R_z @ v_teme.T).T
        omega_x_r = np.column_stack([
            -EARTH_ROTATION_RATE_RAD_S * r_ecef[:, 1],
             EARTH_ROTATION_RATE_RAD_S * r_ecef[:, 0],
             np.zeros(len(r_ecef))
        ])
        v_ecef = v_rot - omega_x_r

    return r_ecef, v_ecef


def geodetic_to_ecef(lat_deg: float, lon_deg: float, elev_m: float) -> np.ndarray:
    """Converts WGS-84 geodetic latitude, longitude, and elevation to ECEF position vector in km."""
    lat_rad = np.radians(lat_deg)
    lon_rad = np.radians(lon_deg)
    h_km = elev_m / 1000.0

    a = EARTH_RADIUS_KM
    f = 1.0 / 298.257223563
    e2 = 2.0 * f - f**2

    N_phi = a / np.sqrt(1.0 - e2 * np.sin(lat_rad)**2)

    x = (N_phi + h_km) * np.cos(lat_rad) * np.cos(lon_rad)
    y = (N_phi + h_km) * np.cos(lat_rad) * np.sin(lon_rad)
    z = (N_phi * (1.0 - e2) + h_km) * np.sin(lat_rad)

    return np.array([x, y, z], dtype=np.float64)


def ecef_to_geodetic(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """Converts ECEF position vector in km to WGS-84 latitude (deg), longitude (deg), elevation (m)."""
    a = EARTH_RADIUS_KM
    f = 1.0 / 298.257223563
    e2 = 2.0 * f - f**2

    r_p = np.sqrt(x**2 + y**2)
    if r_p == 0:
        lat = 90.0 if z > 0 else -90.0
        return lat, 0.0, float(abs(z) - a) * 1000.0

    lon_rad = np.arctan2(y, x)
    lat_rad = np.arctan2(z, r_p * (1.0 - e2))

    for _ in range(5):
        N = a / np.sqrt(1.0 - e2 * np.sin(lat_rad)**2)
        lat_rad = np.arctan2(z + e2 * N * np.sin(lat_rad), r_p)

    N = a / np.sqrt(1.0 - e2 * np.sin(lat_rad)**2)
    alt_km = r_p / np.cos(lat_rad) - N

    return float(np.degrees(lat_rad)), float(np.degrees(lon_rad)), float(alt_km * 1000.0)


def ecef_to_topocentric(
    r_sat_ecef: np.ndarray,
    site: GroundSite
) -> Tuple[float, float, float]:
    """Computes Topocentric Azimuth (deg), Elevation (deg), and Range (km) for a satellite relative to a ground site.
    
    Args:
        r_sat_ecef: Satellite position vector in ECEF (km)
        site: GroundSite configuration
        
    Returns:
        azimuth_deg: Azimuth in degrees [0, 360)
        elevation_deg: Elevation angle in degrees [-90, 90]
        range_km: Slant range distance in km
    """
    r_site_ecef = geodetic_to_ecef(site.latitude_deg, site.longitude_deg, site.elevation_m)
    rho_ecef = r_sat_ecef - r_site_ecef
    range_km = float(np.linalg.norm(rho_ecef))

    lat_rad = np.radians(site.latitude_deg)
    lon_rad = np.radians(site.longitude_deg)

    # Rotation matrix from ECEF to SEZ (South-East-Zenith) local horizon frame
    sin_lat = np.sin(lat_rad)
    cos_lat = np.cos(lat_rad)
    sin_lon = np.sin(lon_rad)
    cos_lon = np.cos(lon_rad)

    R_sez = np.array([
        [sin_lat * cos_lon,  sin_lat * sin_lon, -cos_lat],
        [-sin_lon,           cos_lon,            0.0],
        [cos_lat * cos_lon,  cos_lat * sin_lon,  sin_lat]
    ], dtype=np.float64)

    rho_sez = R_sez @ rho_ecef
    s_south, e_east, z_zenith = rho_sez[0], rho_sez[1], rho_sez[2]

    # Elevation angle
    elevation_rad = np.arcsin(z_zenith / range_km)
    elevation_deg = float(np.degrees(elevation_rad))

    # Azimuth angle measured clockwise from North
    azimuth_rad = np.arctan2(e_east, -s_south)
    if azimuth_rad < 0:
        azimuth_rad += 2.0 * np.pi
    azimuth_deg = float(np.degrees(azimuth_rad))

    return azimuth_deg, elevation_deg, range_km
