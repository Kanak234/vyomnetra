"""3D Orbital Globe Mathematical & Trajectory Engine.

Generates 3D Earth sphere mesh, ground site topocentric coverage rings,
and satellite SGP4 orbit trajectory 3D arcs in ECEF frame.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional
import numpy as np
from sgp4.api import WGS72, jday

from vyomnetra.config import GroundSite, settings
from vyomnetra.ingest.models import SatelliteRecord
from vyomnetra.propagate.engine import SGP4Engine
from vyomnetra.propagate.frames import EARTH_RADIUS_KM, teme_to_ecef, ecef_to_topocentric
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.render.globe_engine")


def get_earth_sphere_mesh(radius: float = EARTH_RADIUS_KM, num_lat: int = 30, num_lon: int = 60) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generates 3D mesh matrices (X, Y, Z) for Earth sphere."""
    u = np.linspace(0, 2 * np.pi, num_lon)
    v = np.linspace(0, np.pi, num_lat)
    
    x = radius * np.outer(np.cos(u), np.sin(v))
    y = radius * np.outer(np.sin(u), np.sin(v))
    z = radius * np.outer(np.ones(np.size(u)), np.cos(v))
    
    return x, y, z


def get_ground_site_ecef(site: GroundSite) -> np.ndarray:
    """Converts ground site geodetic (lat, lon, alt) to 3D ECEF position (km)."""
    lat_rad = np.radians(site.latitude_deg)
    lon_rad = np.radians(site.longitude_deg)
    alt_km = site.elevation_m / 1000.0
    
    r = EARTH_RADIUS_KM + alt_km
    x = r * np.cos(lat_rad) * np.cos(lon_rad)
    y = r * np.cos(lat_rad) * np.sin(lon_rad)
    z = r * np.sin(lat_rad)
    
    return np.array([x, y, z], dtype=np.float64)


def get_ground_site_coverage_ring(site: GroundSite, min_el_deg: float = 10.0, num_pts: int = 72) -> np.ndarray:
    """Generates 3D ECEF ring points representing ground site horizon coverage at min_el_deg."""
    site_ecef = get_ground_site_ecef(site)
    lat_rad = np.radians(site.latitude_deg)
    lon_rad = np.radians(site.longitude_deg)
    
    # Zenith unit vector
    u_up = np.array([np.cos(lat_rad) * np.cos(lon_rad), np.cos(lat_rad) * np.sin(lon_rad), np.sin(lat_rad)])
    # East unit vector
    u_east = np.array([-np.sin(lon_rad), np.cos(lon_rad), 0.0])
    # North unit vector
    u_north = np.array([-np.sin(lat_rad) * np.cos(lon_rad), -np.sin(lat_rad) * np.sin(lon_rad), np.cos(lat_rad)])
    
    # Approximate slant distance at 400km altitude for min_el_deg
    slant_dist = 1200.0
    el_rad = np.radians(min_el_deg)
    
    azimuths = np.linspace(0, 2 * np.pi, num_pts)
    ring_pts = []
    
    for az in azimuths:
        # Topocentric SEZ vector
        dx = slant_dist * np.cos(el_rad) * np.sin(az)  # East
        dy = slant_dist * np.cos(el_rad) * np.cos(az)  # North
        dz = slant_dist * np.sin(el_rad)              # Up
        
        pt_ecef = site_ecef + dx * u_east + dy * u_north + dz * u_up
        ring_pts.append(pt_ecef)
        
    return np.array(ring_pts, dtype=np.float64)


def generate_satellite_orbit_trajectory(
    sat_record: SatelliteRecord,
    start_dt: datetime,
    duration_minutes: float = 90.0,
    step_seconds: float = 60.0,
    engine: Optional[SGP4Engine] = None
) -> Tuple[np.ndarray, np.ndarray, List[datetime]]:
    """Propagates satellite over duration_minutes and returns 3D ECEF trajectory points.
    
    Returns:
        (positions_ecef: Nx3 array, velocities_ecef: Nx3 array, timestamps: List[datetime])
    """
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    prop_engine = engine or SGP4Engine(gravity_model=WGS72)
    satrec = prop_engine.create_satrec(sat_record=sat_record)
    
    total_steps = int((duration_minutes * 60.0) / step_seconds)
    pos_list = []
    vel_list = []
    dt_list = []

    for i in range(total_steps):
        t_dt = start_dt + timedelta(seconds=i * step_seconds)
        jd, fr = jday(t_dt.year, t_dt.month, t_dt.day, t_dt.hour, t_dt.minute, t_dt.second + t_dt.microsecond * 1e-6)
        
        err, r_teme, v_teme = prop_engine.propagate_single(satrec, jd, fr)
        if err == 0:
            r_ecef, v_ecef = teme_to_ecef(r_teme, v_teme, t_dt)
            pos_list.append(r_ecef)
            vel_list.append(v_ecef)
            dt_list.append(t_dt)

    if not pos_list:
        return np.empty((0, 3)), np.empty((0, 3)), []

    return np.array(pos_list, dtype=np.float64), np.array(vel_list, dtype=np.float64), dt_list
