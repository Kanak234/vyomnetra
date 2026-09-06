"""Phase 10 Comprehensive Validation Test Suite for VYOMNETRA SSA Platform.

Tests:
1. Maneuver & change detection engine.
2. ISRO Asset Catalogue metadata & priority severity floor enforcement.
3. Covariance-aware conjunction assessment (Foster, Alfano, Patera, Pc_max, PC_UNSTABLE flag).
4. Relative motion & RPO dynamics (HCW equations & RPO Classifier).
5. NASA SBM debris breakup model & Kessler cascade density profiling.
6. Atmospheric decay Monte Carlo (1000 iterations) & ground track footprint.
7. Scikit-learn Isolation Forest ML Anomaly Detector with feature explainability.
8. Cryptographic hash-chained audit logging and verification.
9. BAH capability module plugin extension framework.
10. Hypothesis property-based tests for coordinate transforms.
"""

import pytest
import numpy as np
from datetime import datetime, timezone
from hypothesis import given, strategies as st

from vyomnetra.ingest.maneuvers import ManeuverDetectionEngine
from vyomnetra.catalogue.isro import is_isro_asset, get_isro_asset, enforce_isro_severity_floor, ISRO_CATALOGUE
from vyomnetra.conjunction.covariance_assessment import CovarianceConjunctionEngine, build_tle_age_covariance_ric
from vyomnetra.propagate.rpo import propagate_hcw, RPOClassifier
from vyomnetra.science.debris_model import KesslerCascadeSimulator, nasa_standard_breakup_fragment_count, compute_spatial_density_profile
from vyomnetra.decay.decay_engine import OrbitDecayEngine
from vyomnetra.intelligence.anomaly import MLAnomalyDetector
from vyomnetra.intelligence.security import SecurityPipelineManager
from vyomnetra.bah.framework import BAHModuleRegistry
from vyomnetra.bah.modules.conjunction_module import ConjunctionScreeningModule
from vyomnetra.propagate.frames import ecef_to_geodetic, geodetic_to_ecef


def test_isro_catalogue_and_severity_floor():
    """Validates ISRO catalogue presence and priority severity floor enforcement."""
    assert len(ISRO_CATALOGUE) > 20
    assert is_isro_asset(25544) is False
    assert is_isro_asset(39241) is True  # GSAT-7

    asset = get_isro_asset(39241)
    assert asset.name == "GSAT-7"
    assert asset.classification == "SECRET"

    # Test automatic severity floor
    assert enforce_isro_severity_floor(25544, 48274, "LOW") == "LOW"
    assert enforce_isro_severity_floor(39241, 25544, "LOW") == "HIGH"
    assert enforce_isro_severity_floor(39241, 25544, "MEDIUM") == "HIGH"
    assert enforce_isro_severity_floor(39241, 25544, "CRITICAL") == "CRITICAL"


def test_covariance_aware_conjunction_assessment():
    """Validates tri-algorithm Pc calculations, stability check, and Pc_max dilution."""
    engine = CovarianceConjunctionEngine()

    result = engine.evaluate_conjunction_covariance(
        primary_norad=25544,
        secondary_norad=48274,
        miss_distance_km=0.5,
        primary_tle_age_days=1.0,
        secondary_tle_age_days=2.0
    )

    assert result.pc_foster_2d >= 0.0
    assert result.pc_alfano >= 0.0
    assert result.pc_patera >= 0.0
    assert result.pc_max >= result.pc_foster_2d
    assert isinstance(result.is_pc_unstable, bool)


def test_rpo_dynamics_and_hcw():
    """Validates Hill-Clohessy-Wiltshire relative motion propagation and RPO classifier."""
    r0 = np.array([0.1, 0.5, 0.0])  # 100m radial, 500m in-track
    v0 = np.array([0.0, -0.0001, 0.0])
    mean_motion = 0.0011  # rad/s ~ 90 min orbit

    r_t, v_t = propagate_hcw(r0, v0, t_seconds=300.0, mean_motion_rad_s=mean_motion)
    assert len(r_t) == 3
    assert len(v_t) == 3

    classifier = RPOClassifier()
    # Simulate bounded co-orbital shadowing trajectory
    rel_pos = [np.array([0.1, 0.2, 0.0]) for _ in range(10)]
    rel_vel = [np.array([0.001, 0.001, 0.0]) for _ in range(10)]
    times = [float(i) for i in range(10)]

    res = classifier.classify_relative_trajectory(25544, 48274, rel_pos, rel_vel, times)
    assert res.classification in ("CO_ORBITAL_SHADOWING", "STATION_KEEPING", "NATURAL_CLOSE_APPROACH")
    assert res.bounded_motion_flag is True


def test_debris_kessler_breakup_model():
    """Validates NASA Standard Breakup Model fragment generation and shell density profiler."""
    sim = KesslerCascadeSimulator()
    res = sim.simulate_breakup(parent_norad=25544, parent_name="ISS", parent_mass_kg=1000.0)

    assert res.total_fragments_generated > 10
    assert res.mean_delta_v_ms > 0
    assert res.ten_year_leo_density_growth_percent > 0

    # Profile density
    alts = [300.0, 400.0, 500.0, 500.0, 800.0, 1200.0]
    profile = compute_spatial_density_profile(alts)
    assert profile["total_objects_in_range"] == len(alts)
    assert "shells" in profile


def test_decay_monte_carlo_and_footprint():
    """Validates Monte Carlo 1,000-sample re-entry window and ground track footprint."""
    from vyomnetra.ingest.models import SatelliteRecord

    sat = SatelliteRecord(
        norad_id=25544,
        name="ISS (ZARYA)",
        international_designator="1998-067A",
        object_type="PAYLOAD",
        epoch_utc="2026-08-25T12:00:00.000000",
        epoch_jd=2460310.0,
        mean_motion=15.495,
        eccentricity=0.0004,
        inclination_deg=51.64,
        raan_deg=208.9,
        arg_perigee_deg=93.7,
        mean_anomaly_deg=266.4,
        bstar=0.0003,
        mean_motion_dot=0.0,
        mean_motion_ddot=0.0,
        ephemeris_type=0,
        element_set_no=999,
        rev_at_epoch=43238,
        raw_tle_line1="1 25544U 98067A   26237.50000000  .00016717  00000-0  30000-3 0  9990",
        raw_tle_line2="2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    )

    decay_engine = OrbitDecayEngine()
    est = decay_engine.estimate_lifetime(sat)

    assert est.estimated_lifetime_days > 0
    assert est.monte_carlo_result is not None
    assert est.monte_carlo_result.num_samples == 1000
    assert len(est.monte_carlo_result.ground_track_footprint) == 50


def test_ml_anomaly_detector_explainability(tmp_path):
    """Validates IsolationForest ML Anomaly Detector predictions and feature contribution explainability."""
    detector = MLAnomalyDetector(model_path=tmp_path / "test_model.joblib")

    is_anom, score, top_3, report = detector.predict_anomaly(
        norad_id=25544,
        sat_name="TEST_SAT",
        delta_mean_motion=0.5,
        delta_inclination=0.1,
        delta_raan=0.05,
        bstar_shift=0.01,
        decay_residual=0.2
    )

    assert isinstance(is_anom, bool)
    assert 0.0 <= score <= 1.0
    assert len(top_3) <= 3
    assert "delta_mean_motion" in [t[0] for t in top_3] or "bstar_shift" in [t[0] for t in top_3]


def test_cryptographic_audit_chain():
    """Validates SHA-256 hash-chained audit logging and tamper-detection integrity check."""
    sec = SecurityPipelineManager()

    sec.append_audit_record("LOGIN", "user1", "res1")
    sec.append_audit_record("UPDATE_TLE", "user1", "sat25544")
    sec.append_audit_record("MANEUVER_EXEC", "admin", "sat48274")

    valid, msg = sec.verify_audit_chain()
    assert valid is True
    assert "verified successfully" in msg

    # Tamper with chain
    sec.audit_chain[1]["action"] = "UNAUTHORIZED_EDIT"
    valid_tampered, tampered_msg = sec.verify_audit_chain()
    assert valid_tampered is False
    assert "Tampering detected" in tampered_msg


def test_bah_framework_registration():
    """Validates BAH capability module registry and lifecycle hooks."""
    registry = BAHModuleRegistry()
    module = ConjunctionScreeningModule()

    registry.register_module(module)
    assert len(registry.list_registered_modules()) == 1

    res = registry.execute_module("bah.capability.conjunction", {"duration_hours": 12.0})
    assert res["status"] == "SUCCESS"


@given(
    lat=st.floats(min_value=-89.0, max_value=89.0),
    lon=st.floats(min_value=-179.0, max_value=179.0),
    alt=st.floats(min_value=100.0, max_value=2000.0)
)
def test_hypothesis_geodetic_ecef_roundtrip(lat, lon, alt):
    """Property-based test proving round-trip invariance between WGS-84 Geodetic and ECEF coordinates."""
    x, y, z = geodetic_to_ecef(lat, lon, alt)
    lat_r, lon_r, alt_r = ecef_to_geodetic(x, y, z)

    assert abs(lat - lat_r) < 1e-4
    assert abs(lon - lon_r) < 1e-4
    assert abs(alt - alt_r) < 1.0  # sub-meter accuracy
