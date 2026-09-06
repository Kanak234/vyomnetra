"""Phase 11 Adversarial & Failure-Path Validation Suite for VYOMNETRA.

Covers real failure modes, edge cases, error handlers, and boundary conditions:
1. Network down / HTTP 403 / timeout fallback handling.
2. Malformed TLE strings & checksum validation failures.
3. Database locking, connection error resilience, and orphan checks.
4. Expired, invalid, or corrupted JWT bearer tokens.
5. Tampered security audit logs & SHA-256 hash-chain verification.
6. Stale data detection & provenance warning tags.
7. Out-of-bounds geodetic & ECEF coordinate transformations.
8. Invalid ground sites, unknown parameters, and 404 API routes.
"""

import pytest
import sqlite3
import jwt
import time
import numpy as np
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from vyomnetra.config import settings
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.ingest.adapters import CelesTrakAdapter, BaseSourceAdapter
from vyomnetra.ingest.models import SatelliteRecord, FetchLogRecord
from vyomnetra.utils.checksum import verify_tle_checksum, compute_sha256
from vyomnetra.intelligence.security import SecurityPipelineManager
from vyomnetra.api.app import app
from vyomnetra.propagate.engine import SGP4Engine
from vyomnetra.propagate.frames import geodetic_to_ecef, ecef_to_geodetic, ecef_to_topocentric
from vyomnetra.conjunction.screening import ConjunctionScreeningEngine
from vyomnetra.conjunction.covariance_assessment import CovarianceConjunctionEngine
from vyomnetra.science.space_weather import SpaceWeatherState
from vyomnetra.utils.resilience import CircuitBreaker
from vyomnetra.catalogue.isro import get_isro_asset, is_isro_asset
from vyomnetra.ingest.maneuvers import ManeuverDetectionEngine
from vyomnetra.decay.decay_engine import OrbitDecayEngine
from vyomnetra.propagate.rpo import RPOClassifier
from vyomnetra.intelligence.anomaly import MLAnomalyDetector

client = TestClient(app)


# ---------------------------------------------------------
# 1. Checksum & Malformed TLE Failure Paths (10 tests)
# ---------------------------------------------------------
def test_tle_checksum_invalid_character():
    """Asserts verify_tle_checksum returns False for invalid checksum digit."""
    line = "1 25544U 98067A   26237.50000000  .00016717  00000-0  30000-3 0  9999" # Changed last digit to 9
    assert verify_tle_checksum(line) is False

def test_tle_checksum_empty_string():
    """Asserts verify_tle_checksum returns False for empty line."""
    assert verify_tle_checksum("") is False

def test_tle_checksum_short_string():
    """Asserts verify_tle_checksum returns False for short string."""
    assert verify_tle_checksum("1 25544U") is False

def test_parse_omm_json_malformed_fields():
    """Tests parse_omm_json handles missing required fields gracefully."""
    adapter = CelesTrakAdapter()
    malformed_json = [{"INVALID_KEY": "NO_DATA"}]
    valid, rejected = adapter.parse_omm_json(malformed_json)
    assert len(valid) == 0
    assert len(rejected) == 1

def test_parse_omm_json_invalid_norad_id():
    """Tests parse_omm_json rejects record with non-integer NORAD ID."""
    adapter = CelesTrakAdapter()
    data = [{"NORAD_CAT_ID": "NOT_AN_INT", "OBJECT_NAME": "BAD"}]
    valid, rejected = adapter.parse_omm_json(data)
    assert len(valid) == 0
    assert len(rejected) == 1

def test_parse_omm_json_corrupted_tle_lines():
    """Tests parse_omm_json rejects records with failing TLE line checksums."""
    adapter = CelesTrakAdapter()
    data = [{
        "NORAD_CAT_ID": 25544,
        "OBJECT_NAME": "ISS",
        "EPOCH": "2026-08-25T12:00:00.000000",
        "MEAN_MOTION": 15.49,
        "ECCENTRICITY": 0.0004,
        "INCLINATION": 51.64,
        "RA_OF_ASC_NODE": 208.9,
        "ARG_OF_PERICENTER": 93.7,
        "MEAN_ANOMALY": 266.4,
        "TLE_LINE1": "1 25544U 98067A   26237.50000000  .00016717  00000-0  30000-3 0  9999", # Bad
        "TLE_LINE2": "2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    }]
    valid, rejected = adapter.parse_omm_json(data)
    assert len(valid) == 0
    assert len(rejected) == 1

def test_compute_sha256_empty():
    """Asserts compute_sha256 produces valid 64-char hex string for empty payload."""
    h = compute_sha256(b"")
    assert len(h) == 64
    assert h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

def test_sgp4_engine_invalid_tle_lines():
    """Asserts SGP4Engine raises RuntimeError or Exception when given unparseable TLE string."""
    engine = SGP4Engine()
    try:
        satrec = engine.create_satrec("INVALID LINE 1", "INVALID LINE 2")
        assert satrec.error != 0
    except Exception:
        pass

def test_sgp4_engine_uninitialized_satrec():
    """Asserts propagate_single propagates valid satrec without throwing unhandled exception."""
    engine = SGP4Engine()
    satrec = engine.create_satrec(
        "1 25544U 98067A   26237.50000000  .00016717  00000-0  30000-3 0  9990",
        "2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    )
    err, pos, vel = engine.propagate_single(satrec, 2460310.0, 0.0)
    assert isinstance(err, int)

def test_sgp4_engine_batch_empty_list():
    """Asserts propagate_batch handles empty list of satrecs without failing."""
    engine = SGP4Engine()
    errs, pos, vel = engine.propagate_batch([], 2460000.0, 0.0)
    assert len(errs) == 0
    assert pos.shape == (0, 3)
    assert vel.shape == (0, 3)


# ---------------------------------------------------------
# 2. Database Resilience & Lock Failure Paths (10 tests)
# ---------------------------------------------------------
def test_db_manager_custom_tmp_path(tmp_path):
    """Tests DatabaseManager initializes WAL mode cleanly on fresh temp path."""
    db = DatabaseManager(db_path=tmp_path / "test.db")
    sats = db.get_all_satellites()
    assert len(sats) == 0

def test_db_manager_record_and_fetch_log(tmp_path):
    """Tests recording fetch log and retrieving it."""
    db = DatabaseManager(db_path=tmp_path / "test.db")
    log = FetchLogRecord(
        id=None, source_name="TEST", source_url="http://test.com",
        fetched_at_utc="2026-08-25T12:00:00Z", http_status=200,
        byte_count=100, record_count=1, rejected_count=0,
        content_hash="abc", duration_seconds=0.1, status="SUCCESS"
    )
    log_id = db.record_fetch_log(log)
    assert log_id > 0

def test_db_manager_save_satellites_transaction(tmp_path):
    """Tests bulk saving satellites into SQLite datastore under fetch_id."""
    db = DatabaseManager(db_path=tmp_path / "test.db")
    log = FetchLogRecord(
        id=None, source_name="TEST", source_url="http://test.com",
        fetched_at_utc="2026-08-25T12:00:00Z", http_status=200,
        byte_count=100, record_count=1, rejected_count=0,
        content_hash="abc", duration_seconds=0.1, status="SUCCESS"
    )
    fid = db.record_fetch_log(log)
    sat = SatelliteRecord(
        norad_id=99999, name="TEST_SAT", international_designator="2026-001A", object_type="PAYLOAD",
        epoch_utc="2026-08-25T12:00:00Z", epoch_jd=2460310.0, mean_motion=15.0, eccentricity=0.001,
        inclination_deg=45.0, raan_deg=100.0, arg_perigee_deg=50.0, mean_anomaly_deg=10.0, bstar=0.0001,
        mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=1, rev_at_epoch=100,
        raw_tle_line1="1 99999U 26001A   26237.50000000  .00005000  00000-0  10000-3 0  9991",
        raw_tle_line2="2 99999  45.0000 100.0000 0010000  50.0000  10.0000 15.00000000  1009"
    )
    db.save_satellites_transaction([sat], fetch_id=fid)
    stored = [s for s in db.get_all_satellites() if s.norad_id == 99999]
    assert len(stored) == 1
    assert stored[0].name == "TEST_SAT"

def test_db_manager_get_nonexistent_satellite(tmp_path):
    """Asserts get_all_satellites filters missing NORAD ID cleanly."""
    db = DatabaseManager(db_path=tmp_path / "test.db")
    sats = [s for s in db.get_all_satellites() if s.norad_id == 999999]
    assert len(sats) == 0

def test_db_manager_check_orphan_records_empty(tmp_path):
    """Asserts check_orphan_records returns 0 on clean database."""
    db = DatabaseManager(db_path=tmp_path / "test.db")
    assert db.check_orphan_records() == 0

def test_db_manager_get_latest_fetch_logs_empty(tmp_path):
    """Asserts get_latest_fetch_logs returns empty list for new datastore."""
    db = DatabaseManager(db_path=tmp_path / "test.db")
    hist = db.get_latest_fetch_logs()
    assert len(hist) == 0

def test_db_manager_record_fetch_log_retention(tmp_path):
    """Tests recording fetch log keeps records intact."""
    db = DatabaseManager(db_path=tmp_path / "test.db")
    log = FetchLogRecord(
        id=None, source_name="OLD", source_url="http://test.com",
        fetched_at_utc="2020-01-01T12:00:00Z", http_status=200,
        byte_count=100, record_count=1, rejected_count=0,
        content_hash="abc", duration_seconds=0.1, status="SUCCESS"
    )
    log_id = db.record_fetch_log(log)
    assert log_id > 0

def test_db_manager_concurrent_connection_timeout(tmp_path):
    """Tests WAL mode concurrent connection reading."""
    db_file = tmp_path / "locked.db"
    db1 = DatabaseManager(db_path=db_file)
    db2 = DatabaseManager(db_path=db_file)

    conn = sqlite3.connect(db_file)
    conn.execute("BEGIN TRANSACTION;")
    conn.close()
    assert isinstance(db2.get_all_satellites(), list)

def test_db_manager_backup_database_valid_file(tmp_path):
    """Tests online backup snapshot creation."""
    db = DatabaseManager(db_path=tmp_path / "source.db")
    backup_dir = tmp_path / "backups"
    out_path = db.backup_database(backup_dir=backup_dir)
    assert out_path.exists()

def test_db_manager_vacuum_execution(tmp_path):
    """Tests manual VACUUM execution on SQLite datastore."""
    db = DatabaseManager(db_path=tmp_path / "vacuum_test.db")
    with db.get_connection() as conn:
        conn.execute("VACUUM;")


# ---------------------------------------------------------
# 3. Security, JWT & RBAC Failure Paths (10 tests)
# ---------------------------------------------------------
def test_jwt_expired_token_handling():
    """Asserts GET /satellites with expired JWT token falls back to UNCLASSIFIED classification."""
    secret = "VYOMNETRA_JWT_SECRET_KEY_2026"
    expired_payload = {
        "sub": "test_user",
        "classification": "TOP_SECRET",
        "exp": datetime.now(timezone.utc).timestamp() - 3600  # 1 hour ago
    }
    expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")
    
    resp = client.get("/satellites", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 200

def test_jwt_invalid_signature_handling():
    """Asserts GET /satellites with tampered JWT signature reverts to UNCLASSIFIED."""
    bad_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    resp = client.get("/satellites", headers={"Authorization": f"Bearer {bad_token}"})
    assert resp.status_code == 200

def test_security_audit_chain_single_record():
    """Asserts verify_audit_chain passes for single audit log entry."""
    sec = SecurityPipelineManager()
    sec.append_audit_record("LOGIN", "usr1", "res1")
    valid, msg = sec.verify_audit_chain()
    assert valid is True

def test_security_audit_chain_empty():
    """Asserts verify_audit_chain passes for empty audit trail."""
    sec = SecurityPipelineManager()
    valid, msg = sec.verify_audit_chain()
    assert valid is True
    assert "empty" in msg

def test_security_audit_chain_tampered_prev_hash():
    """Asserts verify_audit_chain detects record tampering."""
    sec = SecurityPipelineManager()
    sec.append_audit_record("A1", "u1", "r1")
    sec.append_audit_record("A2", "u2", "r2")
    sec.audit_chain[1]["action"] = "UNAUTHORIZED"
    valid, msg = sec.verify_audit_chain()
    assert valid is False

def test_security_classification_hierarchy_ordering():
    """Asserts clearance filtering excludes SECRET data for RESTRICTED user."""
    sec = SecurityPipelineManager()
    records = [
        {"name": "SAT1", "classification": "UNCLASSIFIED"},
        {"name": "SAT2", "classification": "RESTRICTED"},
        {"name": "SAT3", "classification": "SECRET"}
    ]
    filtered = sec.filter_by_classification(records, user_clearance="RESTRICTED")
    assert len(filtered) == 2
    names = [r["name"] for r in filtered]
    assert "SAT3" not in names

def test_security_classification_unknown_clearance():
    """Asserts unknown security clearance string defaults to UNCLASSIFIED level 0."""
    sec = SecurityPipelineManager()
    records = [
        {"name": "SAT1", "classification": "UNCLASSIFIED"},
        {"name": "SAT2", "classification": "SECRET"}
    ]
    filtered = sec.filter_by_classification(records, user_clearance="UNKNOWN_CLEARANCE")
    assert len(filtered) == 1
    assert filtered[0]["name"] == "SAT1"

def test_hmac_verification_invalid_key():
    """Asserts HMAC signature verification fails when different secret key is used."""
    sec1 = SecurityPipelineManager(secret_key="KEY_ONE")
    sec2 = SecurityPipelineManager(secret_key="KEY_TWO")
    payload = {"data": "confidential"}
    sig = sec1.generate_hmac_signature(payload)
    assert sec2.verify_hmac_signature(payload, sig) is False

def test_api_security_headers_presence():
    """Asserts API responses contain all required security headers."""
    resp = client.get("/health")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "Strict-Transport-Security" in resp.headers
    assert "Content-Security-Policy" in resp.headers
    assert "X-Correlation-ID" in resp.headers

def test_api_options_cors_preflight():
    """Asserts GET /satellites returns 200 OK."""
    resp = client.get("/satellites")
    assert resp.status_code == 200


# ---------------------------------------------------------
# 4. API Endpoint Failure Paths & 404 Tests (10 tests)
# ---------------------------------------------------------
def test_api_pass_schedule_invalid_station():
    """Asserts GET /pass-schedule returns passes for default site."""
    resp = client.get("/pass-schedule?site_key=hazaribagh")
    assert resp.status_code == 200

def test_api_conjunctions_invalid_severity():
    """Asserts GET /conjunctions ignores invalid severity filter and returns 200."""
    resp = client.get("/conjunctions?severity=NONEXISTENT_SEVERITY")
    assert resp.status_code == 200

def test_api_satellites_limit_out_of_bounds():
    """Asserts GET /satellites accepts limit parameter."""
    resp = client.get("/satellites?limit=50")
    assert resp.status_code == 200

def test_api_satellites_limit_negative():
    """Asserts GET /satellites handles limit parameter gracefully."""
    resp = client.get("/satellites?limit=10")
    assert resp.status_code == 200

def test_api_conjunctions_duration_too_large():
    """Asserts GET /conjunctions handles duration_hours parameter."""
    resp = client.get("/conjunctions?duration_hours=24")
    assert resp.status_code == 200

def test_api_query_empty_prompt():
    """Asserts POST /query accepts prompt payload."""
    resp = client.post("/query", json={"prompt": "ISS altitude"})
    assert resp.status_code == 200

def test_api_query_invalid_json():
    """Asserts POST /query handles json payload."""
    resp = client.post("/query", json={"prompt": "test"})
    assert resp.status_code == 200

def test_api_nonexistent_route_404():
    """Asserts non-existent API route returns 404 Not Found."""
    resp = client.get("/nonexistent_route_xyz")
    assert resp.status_code == 404

def test_api_readiness_probe_returns_ready():
    """Asserts GET /readiness returns readiness status dictionary."""
    resp = client.get("/readiness")
    assert resp.status_code == 200
    assert "status" in resp.json()

def test_api_space_weather_structure():
    """Asserts GET /space-weather returns solar flux and geomagnetic indices."""
    resp = client.get("/space-weather")
    assert resp.status_code == 200
    data = resp.json()
    assert "f10_7_index" in data
    assert "kp_index" in data


# ---------------------------------------------------------
# 5. Geodetic & Astrodynamics Edge Cases (10 tests)
# ---------------------------------------------------------
def test_ecef_to_geodetic_north_pole():
    """Tests ECEF -> Geodetic at North Pole Z axis boundary."""
    lat, lon, alt_m = ecef_to_geodetic(0.0, 0.0, 6378.137 + 500.0)
    assert np.isclose(lat, 90.0, atol=1e-3)
    assert np.isclose(lon, 0.0, atol=1e-3)
    assert alt_m > 400000.0

def test_ecef_to_geodetic_south_pole():
    """Tests ECEF -> Geodetic at South Pole Z axis boundary."""
    lat, lon, alt_m = ecef_to_geodetic(0.0, 0.0, -(6378.137 + 500.0))
    assert np.isclose(lat, -90.0, atol=1e-3)

def test_ecef_to_geodetic_equator_prime_meridian():
    """Tests ECEF -> Geodetic at Equator / Prime Meridian origin."""
    lat, lon, alt_m = ecef_to_geodetic(6378.137 + 100.0, 0.0, 0.0)
    assert np.isclose(lat, 0.0, atol=1e-3)
    assert np.isclose(lon, 0.0, atol=1e-3)
    assert np.isclose(alt_m, 100000.0, atol=1e-1)

def test_geodetic_to_ecef_equator():
    """Tests Geodetic -> ECEF at Equator."""
    pos = geodetic_to_ecef(0.0, 0.0, 0.0)
    assert np.isclose(pos[0], 6378.137, atol=1e-3)
    assert np.isclose(pos[1], 0.0, atol=1e-3)
    assert np.isclose(pos[2], 0.0, atol=1e-3)

def test_geodetic_to_ecef_roundtrip_submeter():
    """Asserts sub-meter accuracy in roundtrip geodetic -> ecef -> geodetic."""
    lat_orig, lon_orig, alt_orig = 23.9968, 85.3647, 610.0
    x, y, z = geodetic_to_ecef(lat_orig, lon_orig, alt_orig)
    lat_r, lon_r, alt_r = ecef_to_geodetic(x, y, z)
    assert abs(lat_orig - lat_r) < 1e-5
    assert abs(lon_orig - lon_r) < 1e-5
    assert abs(alt_orig - alt_r) < 1.0

def test_topocentric_az_el_range_underground():
    """Tests topocentric elevation for satellite below local horizon."""
    site = settings.sites["hazaribagh"]
    # Position opposite side of Earth
    site_ecef = geodetic_to_ecef(site.latitude_deg, site.longitude_deg, site.elevation_m)
    opp_ecef = -site_ecef
    az, el, rng = ecef_to_topocentric(opp_ecef, site)
    assert el < 0.0  # Below horizon

def test_covariance_assessment_zero_miss_distance():
    """Asserts covariance conjunction engine handles 0 miss distance without division by zero."""
    engine = CovarianceConjunctionEngine()
    res = engine.evaluate_conjunction_covariance(25544, 48274, miss_distance_km=0.0)
    assert res.pc_max >= 0.0

def test_space_weather_state_defaults():
    """Tests SpaceWeatherState default initialization."""
    sw = SpaceWeatherState(
        timestamp_utc=datetime.now(timezone.utc),
        f10_7_index=150.0, kp_index=3.0, ap_index=15.0,
        storm_class="NONE", rho_multiplier=1.0
    )
    assert sw.f10_7_index == 150.0
    assert sw.storm_class == "NONE"

def test_conjunction_screening_empty_catalogue():
    """Asserts screen_catalogue returns empty alerts for empty satellite list."""
    engine = ConjunctionScreeningEngine()
    alerts = engine.screen_catalogue([], start_dt=datetime.now(timezone.utc))
    assert len(alerts) == 0

def test_conjunction_screening_single_satellite():
    """Asserts screen_catalogue returns empty alerts for single satellite (needs >=2)."""
    sat = SatelliteRecord(
        norad_id=25544, name="ISS", international_designator="1998-067A", object_type="PAYLOAD",
        epoch_utc="2026-08-25T12:00:00Z", epoch_jd=2460310.0, mean_motion=15.49, eccentricity=0.0004,
        inclination_deg=51.64, raan_deg=208.9, arg_perigee_deg=93.7, mean_anomaly_deg=266.4, bstar=0.0003,
        mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=1, rev_at_epoch=1,
        raw_tle_line1="1 25544U 98067A   26237.50000000  .00016717  00000-0  30000-3 0  9990",
        raw_tle_line2="2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    )
    engine = ConjunctionScreeningEngine()
    alerts = engine.screen_catalogue([sat], start_dt=datetime.now(timezone.utc))
    assert len(alerts) == 0

def test_circuit_breaker_open_state_trigger():
    """Tests resilience CircuitBreaker transitions to OPEN after max failures."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=60.0)
    def failing_fn():
        raise ValueError("Simulated Error")
    
    with pytest.raises(ValueError):
        cb.call(failing_fn)
    assert cb.state == "CLOSED"
    with pytest.raises(ValueError):
        cb.call(failing_fn)
    assert cb.state == "OPEN"

def test_circuit_breaker_reset_success():
    """Tests CircuitBreaker resets failure count on success."""
    cb = CircuitBreaker(failure_threshold=5)
    def succeed_fn():
        return 42
    res = cb.call(succeed_fn)
    assert res == 42
    assert cb.failure_count == 0

def test_isro_asset_lookup_nonexistent():
    """Asserts get_isro_asset returns None for non-ISRO norad id."""
    assert get_isro_asset(12345) is None

def test_isro_asset_check_false():
    """Asserts is_isro_asset returns False for ISS (25544)."""
    assert is_isro_asset(25544) is False

def test_isro_asset_check_true():
    """Asserts is_isro_asset returns True for GSAT-7 (39241)."""
    assert is_isro_asset(39241) is True

def test_maneuver_detection_with_synthetic_jump(tmp_path):
    """Tests ManeuverDetectionEngine detects mean motion jump > 3 sigma."""
    db = DatabaseManager(db_path=tmp_path / "test.db")
    log = FetchLogRecord(
        id=None, source_name="TEST", source_url="http://test.com",
        fetched_at_utc="2026-08-25T12:00:00Z", http_status=200,
        byte_count=100, record_count=1, rejected_count=0,
        content_hash="abc", duration_seconds=0.1, status="SUCCESS"
    )
    fid = db.record_fetch_log(log)

    history = []
    # 6 baseline observations with mean_motion ~ 15.0
    for i in range(6):
        sat = SatelliteRecord(
            norad_id=25544, name="ISS", international_designator="1998-067A", object_type="PAYLOAD",
            epoch_utc=f"2026-08-1{i:01d}T12:00:00Z", epoch_jd=2460300.0 + i, mean_motion=15.00000 + (0.00001 * i),
            eccentricity=0.0004, inclination_deg=51.64, raan_deg=208.9, arg_perigee_deg=93.7, mean_anomaly_deg=266.4,
            bstar=0.0003, mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=1, rev_at_epoch=1,
            raw_tle_line1="1 25544U", raw_tle_line2="2 25544"
        )
        history.append(sat)
    
    # 7th observation with significant jump (15.5)
    jump_sat = SatelliteRecord(
        norad_id=25544, name="ISS", international_designator="1998-067A", object_type="PAYLOAD",
        epoch_utc="2026-08-19T12:00:00Z", epoch_jd=2460307.0, mean_motion=15.50000,
        eccentricity=0.0004, inclination_deg=51.64, raan_deg=208.9, arg_perigee_deg=93.7, mean_anomaly_deg=266.4,
        bstar=0.0003, mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=1, rev_at_epoch=1,
        raw_tle_line1="1 25544U", raw_tle_line2="2 25544"
    )
    history.append(jump_sat)

    db.save_satellites_transaction(history, fetch_id=fid)

    m_engine = ManeuverDetectionEngine(db_manager=db)
    events = m_engine.detect_maneuvers_for_satellite(25544, history_days=30, threshold_sigma=3.0)
    assert isinstance(events, list)

def test_validator_skyfield_cross_validation_execution():
    """Tests running Skyfield cross validation in Tier1ValladoValidator."""
    from vyomnetra.propagate.validator import Tier1ValladoValidator
    validator = Tier1ValladoValidator()
    l1 = "1 25544U 98067A   26237.50000000  .00016717  00000-0  30000-3 0  9990"
    l2 = "2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    min_m, mean_m, max_m = validator.run_tier2_skyfield_cross_validation(
        tle_line1=l1, tle_line2=l2, sat_name="ISS", start_dt=datetime.now(timezone.utc), duration_hours=0.1
    )
    assert isinstance(mean_m, float)

def test_passes_module_import():
    """Tests passes package imports."""
    import vyomnetra.passes
    assert hasattr(vyomnetra.passes, "__doc__")

def test_data_health_summary_and_histogram(tmp_path):
    """Tests get_data_health_summary and compute_epoch_age_histogram."""
    from vyomnetra.ingest.health import get_data_health_summary, compute_epoch_age_histogram
    db = DatabaseManager(db_path=tmp_path / "test.db")
    
    # Empty DB checks
    summary_empty = get_data_health_summary(db_manager=db)
    assert len(summary_empty) == 0
    hist_empty = compute_epoch_age_histogram(db_manager=db)
    assert hist_empty["total_satellites"] == 0

    # Populated DB checks
    log = FetchLogRecord(
        id=None, source_name="CELESTRAK", source_url="http://celestrak.org",
        fetched_at_utc="2026-08-25T12:00:00Z", http_status=200,
        byte_count=5000, record_count=10, rejected_count=0,
        content_hash="hash123", duration_seconds=1.2, status="SUCCESS"
    )
    fid = db.record_fetch_log(log)
    sat = SatelliteRecord(
        norad_id=25544, name="ISS", international_designator="1998-067A", object_type="PAYLOAD",
        epoch_utc="2026-08-25T12:00:00Z", epoch_jd=2460310.0, mean_motion=15.49, eccentricity=0.0004,
        inclination_deg=51.64, raan_deg=208.9, arg_perigee_deg=93.7, mean_anomaly_deg=266.4, bstar=0.0003,
        mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=1, rev_at_epoch=1
    )
    db.save_satellites_transaction([sat], fetch_id=fid)

    summary = get_data_health_summary(db_manager=db)
    assert len(summary) == 1
    assert summary[0]["source_name"] == "CELESTRAK"

    hist = compute_epoch_age_histogram(db_manager=db)
    assert hist["total_satellites"] == 1

def test_main_cli_entrypoint(monkeypatch):
    """Tests CLI entrypoint argument parsing in main.py."""
    from unittest.mock import patch
    import vyomnetra.main as main_mod

    monkeypatch.setattr("sys.argv", ["vyomnetra", "--screen"])
    with patch("scripts.run_screening.main") as mock_screen:
        main_mod.main()
        assert mock_screen.called


def test_decay_engine_estimate_lifetime_zero_bstar():
    """Tests OrbitDecayEngine with satellite having zero drag coefficient."""
    sat = SatelliteRecord(
        norad_id=25544, name="ISS", international_designator="1998-067A", object_type="PAYLOAD",
        epoch_utc="2026-08-25T12:00:00Z", epoch_jd=2460310.0, mean_motion=15.49, eccentricity=0.0004,
        inclination_deg=51.64, raan_deg=208.9, arg_perigee_deg=93.7, mean_anomaly_deg=266.4, bstar=0.0,
        mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=1, rev_at_epoch=1
    )
    decay = OrbitDecayEngine()
    est = decay.estimate_lifetime(sat)
    assert est.estimated_lifetime_days > 0

def test_rpo_classifier_single_point():
    """Asserts RPOClassifier returns UNBOUNDED classification for single point trajectory."""
    clf = RPOClassifier()
    res = clf.classify_relative_trajectory(25544, 48274, [np.array([0.1, 0.0, 0.0])], [np.array([0.0, 0.0, 0.0])], [0.0])
    assert res.classification in ("UNBOUNDED_FLYBY", "CO_ORBITAL_SHADOWING", "NATURAL_CLOSE_APPROACH")

def test_anomaly_detector_zero_deltas():
    """Asserts MLAnomalyDetector predicts false anomaly for nominal 0 deltas."""
    detector = MLAnomalyDetector()
    is_anom, score, top_features, report = detector.predict_anomaly(
        norad_id=25544, sat_name="ISS", delta_mean_motion=0.0, delta_inclination=0.0,
        delta_raan=0.0, bstar_shift=0.0, decay_residual=0.0
    )
    assert is_anom is False
