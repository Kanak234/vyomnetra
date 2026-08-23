"""Phase 2 SGP4 Engine, Coordinate Frames & Tier 1 Benchmark Tests.

Validates SGP4 propagation accuracy, TEME-to-ECEF rotation, topocentric Az/El/Range,
and 100% compliance with Vallado SGP4-VER benchmark tolerances (<1e-6 km, <1e-9 km/s).
"""

from datetime import datetime, timezone
import numpy as np
import pytest

from vyomnetra.config import settings
from vyomnetra.propagate.engine import SGP4Engine
from vyomnetra.propagate.frames import teme_to_ecef, ecef_to_topocentric, geodetic_to_ecef
from vyomnetra.propagate.validator import Tier1ValladoValidator


def test_sgp4_engine_single_propagation():
    """Tests single SGP4 satellite propagation returning valid non-zero TEME state vector."""
    engine = SGP4Engine()
    tle1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9995"
    tle2 = "2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"

    satrec = engine.create_satrec(tle1, tle2)
    err, r_teme, v_teme = engine.propagate_single(satrec, satrec.jdsatepoch, satrec.jdsatepochF)

    assert err == 0
    assert r_teme.shape == (3,)
    assert v_teme.shape == (3,)
    # Altitude check for ISS ~ 400 km + Earth radius ~ 6378 km -> ~ 6700-6800 km
    r_norm = np.linalg.norm(r_teme)
    assert 6500.0 < r_norm < 7000.0
    # ISS orbital velocity ~ 7.66 km/s
    v_norm = np.linalg.norm(v_teme)
    assert 7.0 < v_norm < 8.0


def test_sgp4_engine_batch_propagation():
    """Tests vectorized batch propagation of N satellites."""
    engine = SGP4Engine()
    tle1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9995"
    tle2 = "2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"

    satrec = engine.create_satrec(tle1, tle2)
    n_sats = 100
    satrecs = [satrec] * n_sats

    errs, pos_batch, vel_batch = engine.propagate_batch(satrecs, satrec.jdsatepoch, satrec.jdsatepochF + 0.01)

    assert len(errs) == n_sats
    assert np.all(errs == 0)
    assert pos_batch.shape == (n_sats, 3)
    assert vel_batch.shape == (n_sats, 3)


def test_teme_to_ecef_transformation():
    """Tests TEME -> ECEF frame transformation preserving position vector magnitude."""
    r_teme = np.array([5000.0, 3000.0, 2000.0], dtype=np.float64)
    v_teme = np.array([-3.0, 5.0, 4.0], dtype=np.float64)
    now_dt = datetime.now(timezone.utc)

    r_ecef, v_ecef = teme_to_ecef(r_teme, v_teme, now_dt)

    assert r_ecef.shape == (3,)
    assert v_ecef.shape == (3,)
    # Rotation preserves vector norm exactly
    assert np.isclose(np.linalg.norm(r_teme), np.linalg.norm(r_ecef), atol=1e-9)
    # Velocity vector changed due to Earth rotation cross product
    assert not np.array_equal(v_teme, v_ecef)


def test_topocentric_az_el_range_hazaribagh():
    """Tests ECEF -> Topocentric Azimuth/Elevation/Range conversion for Hazaribagh site."""
    site = settings.sites["hazaribagh"]
    site_ecef = geodetic_to_ecef(site.latitude_deg, site.longitude_deg, site.elevation_m)
    
    # Satellite directly 500 km overhead Hazaribagh
    # ECEF vector along Zenith
    lat_rad = np.radians(site.latitude_deg)
    lon_rad = np.radians(site.longitude_deg)
    zenith_dir = np.array([
        np.cos(lat_rad) * np.cos(lon_rad),
        np.cos(lat_rad) * np.sin(lon_rad),
        np.sin(lat_rad)
    ])
    
    sat_ecef = site_ecef + 500.0 * zenith_dir

    az_deg, el_deg, rng_km = ecef_to_topocentric(sat_ecef, site)

    # Elevation directly overhead should be ~90 deg
    assert np.isclose(el_deg, 90.0, atol=1e-2)
    # Range should be ~500 km
    assert np.isclose(rng_km, 500.0, atol=1e-2)


def test_tier_1_vallado_benchmark_suite():
    """HARD RULE #2 / TIER 1 BENCHMARK: Asserts 100% compliance with Vallado reference tolerances."""
    validator = Tier1ValladoValidator()
    results, max_pos_err, max_vel_err, all_passed = validator.run_benchmark_suite()

    assert all_passed is True
    assert max_pos_err <= validator.pos_tol_km
    assert max_vel_err <= validator.vel_tol_kms


def test_wgs84_hazaribagh_ecef_accuracy():
    """Asserts WGS-84 ECEF conversion for Hazaribagh ground station to within 1 metre tolerance."""
    site = settings.sites["hazaribagh"]
    # WGS-84 exact position: lat=23.9968°N, lon=85.3647°E, elev=610.0m
    # Expected ECEF (km): X=471.19236257, Y=5811.57826021, Z=2578.20771181, |r|=6375.234829 km
    site_ecef = geodetic_to_ecef(site.latitude_deg, site.longitude_deg, site.elevation_m)
    
    expected_ecef = np.array([471.19236257, 5811.57826021, 2578.20771181], dtype=np.float64)
    # 1 metre = 0.001 km
    assert np.allclose(site_ecef, expected_ecef, atol=1e-3)
    
    norm_km = np.linalg.norm(site_ecef)
    assert np.isclose(norm_km, 6375.234829, atol=1e-3)
