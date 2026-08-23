"""Phase 4 3D Globe & Rendering Tests.

Validates Earth 3D sphere mesh creation, ground station ECEF overlay & horizon ring,
day/night solar terminator boundary curve calculation, and satellite orbit arc generation.
"""

from datetime import datetime, timezone
import numpy as np
import pytest

from vyomnetra.config import settings
from vyomnetra.ingest.models import SatelliteRecord
from vyomnetra.render.globe_engine import (
    get_earth_sphere_mesh,
    get_ground_site_ecef,
    get_ground_site_coverage_ring,
    generate_satellite_orbit_trajectory
)
from vyomnetra.render.terminator import calculate_solar_terminator_points, get_solar_subpoint


def test_earth_sphere_mesh():
    """Tests 3D Earth sphere mesh array generation."""
    x, y, z = get_earth_sphere_mesh(radius=6378.137, num_lat=10, num_lon=20)
    assert x.shape == (20, 10)
    assert y.shape == (20, 10)
    assert z.shape == (20, 10)
    
    # Check max radius
    radii = np.sqrt(x**2 + y**2 + z**2)
    assert np.allclose(radii, 6378.137, atol=1e-3)


def test_ground_site_ecef_and_coverage():
    """Tests ground station 3D ECEF position and horizon coverage ring generation."""
    hz_site = settings.sites["hazaribagh"]
    site_ecef = get_ground_site_ecef(hz_site)
    
    assert site_ecef.shape == (3,)
    dist_km = np.linalg.norm(site_ecef)
    assert 6370.0 < dist_km < 6390.0

    ring_pts = get_ground_site_coverage_ring(hz_site, num_pts=36)
    assert ring_pts.shape == (36, 3)


def test_solar_terminator_calculation():
    """Tests solar terminator day/night boundary 3D curve generation."""
    now_dt = datetime.now(timezone.utc)
    sub_lat, sub_lon = get_solar_subpoint(now_dt)
    assert -90.0 <= sub_lat <= 90.0
    assert -180.0 <= sub_lon <= 180.0

    lat_lon_arr, ecef_pts = calculate_solar_terminator_points(now_dt, num_points=100)
    assert lat_lon_arr.shape == (100, 2)
    assert ecef_pts.shape == (100, 3)

    dists = np.linalg.norm(ecef_pts, axis=1)
    assert np.allclose(dists, 6378.137, atol=1.0)


def test_satellite_orbit_trajectory():
    """Tests 3D SGP4 orbit trajectory arc generation in ECEF."""
    iss_rec = SatelliteRecord(
        norad_id=25544,
        name="ISS (ZARYA)",
        international_designator="1998-067A",
        object_type="PAYLOAD",
        epoch_utc="2024-01-01T12:00:00Z",
        epoch_jd=2460310.0,
        mean_motion=15.49575918,
        eccentricity=0.0004817,
        inclination_deg=51.6400,
        raan_deg=208.9163,
        arg_perigee_deg=93.7377,
        mean_anomaly_deg=266.4950,
        bstar=0.00016717,
        mean_motion_dot=0.0,
        mean_motion_ddot=0.0,
        ephemeris_type=0,
        element_set_no=999,
        rev_at_epoch=43238,
        raw_tle_line1="1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9995",
        raw_tle_line2="2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    )

    now_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    pos_ecef, vel_ecef, dt_list = generate_satellite_orbit_trajectory(iss_rec, now_dt, duration_minutes=95.0, step_seconds=60.0)

    assert pos_ecef.shape[0] == 95
    assert pos_ecef.shape[1] == 3
    assert len(dt_list) == 95

    radii = np.linalg.norm(pos_ecef, axis=1)
    assert np.all((radii > 6500.0) & (radii < 7500.0))
