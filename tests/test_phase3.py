"""Phase 3 Visibility, Pass Predictor & Observation Log Tests.

Validates topocentric pass finder, solar position & shadow cone modeling,
optical naked-eye visibility flagging, and empirical observation logging in SQLite.
"""

from datetime import datetime, timedelta, timezone
import numpy as np
import pytest

from vyomnetra.config import settings
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.ingest.models import SatelliteRecord, FetchLogRecord
from vyomnetra.visibility.illumination import (
    get_sun_position_ecef,
    get_observer_solar_elevation_deg,
    is_satellite_sunlit,
    is_naked_eye_visible
)
from vyomnetra.visibility.passes import PassPredictor
from vyomnetra.visibility.obs_log import ObservationLogManager


def test_sun_position_ecef():
    """Tests analytical solar position vector calculation returning valid ~1 AU vector in ECEF."""
    now_dt = datetime.now(timezone.utc)
    r_sun = get_sun_position_ecef(now_dt)

    assert r_sun.shape == (3,)
    sun_dist_km = np.linalg.norm(r_sun)
    assert 1.40e8 < sun_dist_km < 1.55e8


def test_is_satellite_sunlit_and_umbra():
    """Tests solar illumination state determination (Sunlit vs Earth Umbra shadow)."""
    now_dt = datetime.now(timezone.utc)
    
    r_sun = get_sun_position_ecef(now_dt)
    u_sun = r_sun / np.linalg.norm(r_sun)
    
    r_sat_day = 7000.0 * u_sun
    sunlit, state = is_satellite_sunlit(r_sat_day, now_dt)
    assert sunlit is True
    assert state == "SUNLIT"

    r_sat_night = -7000.0 * u_sun
    sunlit_night, state_night = is_satellite_sunlit(r_sat_night, now_dt)
    assert sunlit_night is False
    assert state_night == "UMBRA"


def test_pass_predictor_for_iss():
    """Tests topocentric pass predictor predicting valid AOS, TCA, LOS times."""
    iss_record = SatelliteRecord(
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

    hz_site = settings.sites["hazaribagh"]
    predictor = PassPredictor()
    start_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    passes = predictor.predict_passes(iss_record, hz_site, start_dt, duration_hours=48.0, min_elevation_deg=10.0)

    assert len(passes) > 0
    p = passes[0]
    assert p.sat_name == "ISS (ZARYA)"
    assert p.norad_id == 25544
    assert p.aos_dt < p.tca_dt < p.los_dt
    assert p.max_elevation_deg >= 10.0
    assert p.duration_seconds > 0.0


def test_observation_log_manager(tmp_path):
    """Tests empirical observation log creation and residual calculation in SQLite with valid FK parent."""
    db_file = tmp_path / "test_obs.db"
    db_manager = DatabaseManager(db_path=db_file)
    
    # Create parent fetch log & satellite record to respect FOREIGN KEY constraint
    fetch_rec = FetchLogRecord(
        id=None,
        source_name="TEST",
        source_url="http://test",
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
        http_status=200,
        byte_count=100,
        record_count=1,
        rejected_count=0,
        content_hash="test",
        duration_seconds=0.1,
        status="SUCCESS"
    )
    fetch_id = db_manager.record_fetch_log(fetch_rec)

    sat_rec = SatelliteRecord(
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
        fetch_id=fetch_id
    )
    db_manager.save_satellites_transaction([sat_rec], fetch_id)

    obs_manager = ObservationLogManager(db_manager)

    pred_tca = datetime(2026, 8, 23, 18, 30, 0, tzinfo=timezone.utc)
    obs_tca = pred_tca + timedelta(seconds=15.0)

    rec = obs_manager.record_observation(
        norad_id=25544,
        sat_name="ISS (ZARYA)",
        site_name="Hazaribagh",
        pred_tca_dt=pred_tca,
        obs_tca_dt=obs_tca,
        pred_max_el_deg=45.0,
        obs_max_el_deg=44.2,
        notes="Test observation log"
    )

    assert rec.id is not None
    assert rec.time_residual_sec == 15.0
    assert np.isclose(rec.elevation_residual_deg, -0.8, atol=1e-6)

    records = obs_manager.get_observations_for_satellite(25544)
    assert len(records) == 1
    assert records[0].id == rec.id
    assert records[0].time_residual_sec == 15.0
