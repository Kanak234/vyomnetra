"""Phase 5 Conjunction Screening & Collision Probability Unit & Integration Tests.

Validates RIC frame rotation, Foster 2D Probability of Collision calculation,
conjunction severity assignment, and candidate pair spatial screening.
"""

from datetime import datetime, timezone
import numpy as np
import pytest

from vyomnetra.conjunction.screening import (
    ConjunctionScreeningEngine,
    ConjunctionAlert,
    calculate_foster_2d_pc,
    assign_conjunction_severity,
    teme_to_ric_matrix
)
from vyomnetra.ingest.models import SatelliteRecord


def test_teme_to_ric_matrix():
    """Tests TEME -> RIC (Radial, In-track, Cross-track) rotation matrix orthogonality."""
    r_teme = np.array([7000.0, 0.0, 0.0])
    v_teme = np.array([0.0, 7.5, 0.0])

    ric_mat = teme_to_ric_matrix(r_teme, v_teme)

    assert ric_mat.shape == (3, 3)
    # Rotation matrix must be orthogonal: R^T * R = I
    identity_check = ric_mat.T @ ric_mat
    assert np.allclose(identity_check, np.eye(3), atol=1e-6)


def test_calculate_foster_2d_pc():
    """Tests 2D Foster Probability of Collision (Pc) calculation."""
    # Zero miss distance should yield high Pc
    pc_headon = calculate_foster_2d_pc(miss_distance_km=0.0)
    assert 1e-4 < pc_headon <= 1.0

    # Large miss distance (e.g. 50 km) should yield negligible Pc ~ 0
    pc_far = calculate_foster_2d_pc(miss_distance_km=50.0)
    assert pc_far < 1e-10


def test_assign_conjunction_severity():
    """Tests conjunction alert severity grading logic."""
    assert assign_conjunction_severity(0.5, pc=1e-3) == "CRITICAL"
    assert assign_conjunction_severity(2.0, pc=1e-5) == "HIGH"
    assert assign_conjunction_severity(8.0, pc=1e-6) == "MEDIUM"
    assert assign_conjunction_severity(25.0, pc=1e-8) == "LOW"


def test_conjunction_screening_engine_screening():
    """Tests conjunction screening engine on two close satellites."""
    sat1 = SatelliteRecord(
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

    # Identical satellite (duplicate orbit) should trigger close approach / conjunction
    sat2 = SatelliteRecord(
        norad_id=99999,
        name="TARGET DEBRIS",
        international_designator="2024-001A",
        object_type="DEBRIS",
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
        raw_tle_line1="1 99999U 24001A   24001.50000000  .00016717  00000-0  30000-3 0  9990",
        raw_tle_line2="2 99999  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    )

    engine = ConjunctionScreeningEngine()
    start_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    alerts = engine.screen_catalogue([sat1, sat2], start_dt, duration_hours=2.0, max_miss_distance_km=10.0)

    assert len(alerts) >= 1
    a = alerts[0]
    assert a.primary_norad in (25544, 99999)
    assert a.secondary_norad in (25544, 99999)
    assert a.miss_distance_km < 1.0
    assert a.severity == "CRITICAL"
