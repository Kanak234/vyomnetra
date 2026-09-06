"""Phase 6 Intelligence, Space Weather, Orbit Decay, CoT Agent & BAH Framework Tests.

Validates orbital anomaly detection, RPO proximity classification, security HMAC signatures,
space weather indices, atmospheric density scaling, decay lifetime, agentic CoT execution,
BAH problem statements, and the 5-tier system validation harness.
"""

from datetime import datetime, timezone
import pytest

from vyomnetra.intelligence.anomaly import (
    detect_orbital_maneuver,
    detect_rpo_proximity_operations,
    calculate_threat_assessment
)
from vyomnetra.intelligence.security import SecurityPipelineManager
from vyomnetra.science.space_weather import (
    classify_geomagnetic_storm,
    estimate_atmospheric_density,
    get_current_space_weather
)
from vyomnetra.decay.decay_engine import OrbitDecayEngine
from vyomnetra.orchestrator.cot_engine import SSAAgentOrchestrator
from vyomnetra.knowledge.nl_assistant import NLQueryAssistant
from vyomnetra.bah.framework import BAHFrameworkRunner
from vyomnetra.validate.harness import MultiTierValidationHarness
from vyomnetra.ingest.models import SatelliteRecord


def test_orbital_maneuver_detection():
    """Tests maneuver detection when mean motion shifts significantly."""
    sat_prev = SatelliteRecord(
        norad_id=25544, name="ISS", international_designator="1998-067A", object_type="PAYLOAD",
        epoch_utc="2024-01-01T12:00:00Z", epoch_jd=2460310.0, mean_motion=15.49, eccentricity=0.0004,
        inclination_deg=51.64, raan_deg=208.9, arg_perigee_deg=93.7, mean_anomaly_deg=266.4,
        bstar=0.0001, mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=999, rev_at_epoch=43238
    )

    sat_curr = SatelliteRecord(
        norad_id=25544, name="ISS", international_designator="1998-067A", object_type="PAYLOAD",
        epoch_utc="2024-01-02T12:00:00Z", epoch_jd=2460311.0, mean_motion=15.60, eccentricity=0.0004,  # Mean motion shifted +0.11
        inclination_deg=51.64, raan_deg=208.9, arg_perigee_deg=93.7, mean_anomaly_deg=266.4,
        bstar=0.0001, mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=999, rev_at_epoch=43253
    )

    report = detect_orbital_maneuver(sat_prev, sat_curr)
    assert report is not None
    assert report.anomaly_type == "MANEUVER"
    assert report.severity in ("HIGH", "MEDIUM")


def test_rpo_proximity_operations():
    """Tests co-orbital RPO proximity operations detection."""
    chaser = SatelliteRecord(
        norad_id=99901, name="INSPECTOR-1", international_designator="2024-001A", object_type="PAYLOAD",
        epoch_utc="2024-01-01T12:00:00Z", epoch_jd=2460310.0, mean_motion=15.0, eccentricity=0.001,
        inclination_deg=51.6, raan_deg=100.0, arg_perigee_deg=90.0, mean_anomaly_deg=45.0,
        bstar=0.0001, mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=999, rev_at_epoch=100
    )

    target = SatelliteRecord(
        norad_id=25544, name="STRATEGIC_ASSET", international_designator="1998-067A", object_type="PAYLOAD",
        epoch_utc="2024-01-01T12:00:00Z", epoch_jd=2460310.0, mean_motion=15.0, eccentricity=0.001,
        inclination_deg=51.6, raan_deg=100.0, arg_perigee_deg=90.0, mean_anomaly_deg=45.0,
        bstar=0.0001, mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=999, rev_at_epoch=100
    )

    report = detect_rpo_proximity_operations(chaser, target, separation_distance_km=8.5, relative_velocity_kms=0.02)
    assert report is not None
    assert report.anomaly_type == "RPO_PROXIMITY"
    assert report.severity == "CRITICAL"


def test_security_hmac_and_classification():
    """Tests cybersecurity HMAC integrity signatures and classification clearance filtering."""
    sec = SecurityPipelineManager()
    payload = {"norad_id": 25544, "threat_level": "HIGH", "action": "ALERT"}

    sig = sec.generate_hmac_signature(payload)
    assert len(sig) == 64
    assert sec.verify_hmac_signature(payload, sig) is True

    # Tampered payload check
    tampered_payload = {"norad_id": 25544, "threat_level": "LOW", "action": "ALERT"}
    assert sec.verify_hmac_signature(tampered_payload, sig) is False

    records = [
        {"name": "Public Sat", "classification": "UNCLASSIFIED"},
        {"name": "Cartosat Data", "classification": "RESTRICTED"},
        {"name": "Strategic Asset", "classification": "SECRET"},
        {"name": "Special Payload", "classification": "TOP_SECRET"},
    ]

    filtered_unclass = sec.filter_by_classification(records, user_clearance="UNCLASSIFIED")
    assert len(filtered_unclass) == 1

    filtered_secret = sec.filter_by_classification(records, user_clearance="SECRET")
    assert len(filtered_secret) == 3


def test_space_weather_physics():
    """Tests space weather indices classification and atmospheric density scaling."""
    assert classify_geomagnetic_storm(9.5) == "G5_EXTREME"
    assert classify_geomagnetic_storm(3.0) == "NONE"

    sw = get_current_space_weather()
    assert sw.f10_7_index > 50.0

    rho_400 = estimate_atmospheric_density(400.0, f10_7=150.0, kp=3.0)
    assert 1e-13 < rho_400 < 1e-10

    # Solar storm increases density
    rho_storm = estimate_atmospheric_density(400.0, f10_7=220.0, kp=8.0)
    assert rho_storm > rho_400


def test_orbit_decay_engine():
    """Tests drag decay rate and remaining orbital lifetime calculation."""
    sat = SatelliteRecord(
        norad_id=25544, name="ISS (ZARYA)", international_designator="1998-067A", object_type="PAYLOAD",
        epoch_utc="2024-01-01T12:00:00Z", epoch_jd=2460310.0, mean_motion=15.49575918, eccentricity=0.0004817,
        inclination_deg=51.6400, raan_deg=208.9163, arg_perigee_deg=93.7377, mean_anomaly_deg=266.4950,
        bstar=0.00016717, mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=999, rev_at_epoch=43238
    )

    decay_engine = OrbitDecayEngine()
    est = decay_engine.estimate_lifetime(sat)

    assert est.norad_id == 25544
    assert 350.0 < est.current_perigee_km < 450.0
    assert est.decay_rate_km_per_day > 0.0
    assert est.estimated_lifetime_days > 0.0


def test_agentic_cot_orchestrator():
    """Tests agentic Chain-of-Thought tool execution pipeline."""
    orchestrator = SSAAgentOrchestrator()
    res = orchestrator.process_query("What conjunction risks exist in the next 24 hours?")

    assert len(res.thought_plan) >= 2
    assert res.thought_plan[0].status == "EXECUTED"
    assert res.data_lineage_hash.startswith("hash_")
    assert "Conjunction" in res.final_answer or "No critical conjunctions" in res.final_answer


def test_nl_assistant_query():
    """Tests Natural Language query parsing and formatted output."""
    assistant = NLQueryAssistant()
    resp = assistant.process_user_prompt("Predict satellite passes over Hazaribagh ground station")

    assert "query" in resp
    assert "cot_plan_text" in resp
    assert "final_answer" in resp
    assert "lineage_hash" in resp


def test_bah_framework_runner():
    """Tests Bharatiya Antariksh Hackathon problem statement runner."""
    runner = BAHFrameworkRunner()
    sat = SatelliteRecord(
        norad_id=25544, name="ISS (ZARYA)", international_designator="1998-067A", object_type="PAYLOAD",
        epoch_utc="2024-01-01T12:00:00Z", epoch_jd=2460310.0, mean_motion=15.49575918, eccentricity=0.0004817,
        inclination_deg=51.6400, raan_deg=208.9163, arg_perigee_deg=93.7377, mean_anomaly_deg=266.4950,
        bstar=0.00016717, mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=999, rev_at_epoch=43238,
        raw_tle_line1="1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9995",
        raw_tle_line2="2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    )

    out = runner.execute_problem_statement("BAH-2024-DEBRIS", [sat])
    assert out["problem_id"] == "BAH-2024-DEBRIS"
    assert out["total_evaluated"] == 1


def test_multi_tier_validation_harness():
    """Tests execution of all 5 system validation Tiers."""
    harness = MultiTierValidationHarness()
    summaries = harness.run_all_tiers()

    assert len(summaries) == 5
    for s in summaries:
        assert s.status in ("PASSED", "SKIPPED")
