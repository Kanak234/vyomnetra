"""VYOMNETRA Intelligence Layer — Anomaly Detection & Threat Assessment.

Provides ML & heuristic algorithms for:
- Isolation Forest ML Anomaly Detection over orbital element time-series with feature explainability.
- Orbital maneuver detection (delta-v, mean motion, inclination/RAAN drift anomalies).
- Adversarial satellite behavior recognition (Co-orbital Rendezvous & Proximity Operations - RPO).
- Strategic threat assessment matrix for aerospace defense workflows.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest

from vyomnetra.ingest.models import SatelliteRecord
from vyomnetra.config import settings
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.intelligence.anomaly")


@dataclass
class AnomalyReport:
    """Dataclass describing an orbital anomaly or suspicious behavior."""
    norad_id: int
    name: str
    anomaly_type: str  # MANEUVER, DRAG_SPIKE, DEORBIT_WARNING, RPO_PROXIMITY, ML_ORBITAL_ANOMALY
    severity: str      # CRITICAL, HIGH, MEDIUM, LOW
    confidence_score: float  # 0.0 to 1.0
    description: str
    detected_at_utc: datetime
    top_contributing_features: Optional[List[Tuple[str, float]]] = None


@dataclass
class ThreatAssessment:
    """Dataclass describing strategic threat level of a satellite."""
    norad_id: int
    name: str
    classification: str   # UNCLASSIFIED, RESTRICTED, CONFIDENTIAL, SECRET, TOP SECRET
    threat_score: float    # 0.0 (Harmless) to 10.0 (High Threat)
    threat_category: str  # RECONNAISSANCE, ASAT_CO_ORBITAL, ELECTRONIC_WARFARE, UNKNOWN
    proximity_target_norad: Optional[int] = None
    recommended_action: str = "MONITOR"


class MLAnomalyDetector:
    """Scikit-Learn Isolation Forest ML Model with Feature Explainability for Orbital Anomalies."""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or (settings.get_db_path().parent / "models" / "anomaly_isolation_forest.joblib")
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model: Optional[IsolationForest] = None
        self.feature_names = ["delta_mean_motion", "delta_inclination", "delta_raan", "bstar_shift", "decay_residual"]
        self.feature_means = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
        self.feature_stds = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
        self._load_or_initialize()

    def _load_or_initialize(self):
        """Loads existing model from disk or initializes a default trained model."""
        if self.model_path.exists():
            try:
                data = joblib.load(self.model_path)
                self.model = data["model"]
                self.feature_means = data.get("means", self.feature_means)
                self.feature_stds = data.get("stds", self.feature_stds)
                logger.info(f"Loaded trained IsolationForest model from {self.model_path}")
                return
            except Exception as e:
                logger.warning(f"Failed loading model from {self.model_path}: {e}")

        # Initialize and train default IsolationForest model on synthetic baseline distribution
        self.model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        X_dummy = np.random.normal(0.0, 1.0, (500, 5))
        self.model.fit(X_dummy)
        self.save_model()

    def save_model(self):
        """Persists trained model and normalization parameters to disk."""
        data = {
            "model": self.model,
            "means": self.feature_means,
            "stds": self.feature_stds
        }
        joblib.dump(data, self.model_path)
        logger.info(f"Saved IsolationForest model to {self.model_path}")

    def train_on_history(self, feature_matrix: np.ndarray):
        """Trains/retrains the Isolation Forest model on historical TLE feature vectors."""
        if len(feature_matrix) < 20:
            logger.warning("Insufficient feature matrix size for retraining ML anomaly model.")
            return

        self.feature_means = np.mean(feature_matrix, axis=0)
        self.feature_stds = np.std(feature_matrix, axis=0) + 1e-8
        X_norm = (feature_matrix - self.feature_means) / self.feature_stds

        self.model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        self.model.fit(X_norm)
        self.save_model()

    def predict_anomaly(
        self,
        norad_id: int,
        sat_name: str,
        delta_mean_motion: float,
        delta_inclination: float,
        delta_raan: float,
        bstar_shift: float,
        decay_residual: float
    ) -> Tuple[bool, float, List[Tuple[str, float]], AnomalyReport]:
        """Predicts anomaly status for an orbital observation and generates human-readable feature explanations."""
        raw_feat = np.array([delta_mean_motion, delta_inclination, delta_raan, bstar_shift, decay_residual])
        norm_feat = (raw_feat - self.feature_means) / self.feature_stds

        score = float(-self.model.score_samples([norm_feat])[0])  # Higher score = more anomalous
        is_anomaly = bool(self.model.predict([norm_feat])[0] == -1)

        # Feature contribution attribution (Z-score deviation from norm)
        deviations = np.abs(norm_feat)
        total_dev = np.sum(deviations) + 1e-8
        contributions = [(name, float(round(dev / total_dev * 100.0, 1))) for name, dev in zip(self.feature_names, deviations)]
        contributions.sort(key=lambda x: x[1], reverse=True)

        top_3 = contributions[:3]
        top_str = ", ".join([f"{name} ({pct}%)" for name, pct in top_3])

        severity = "CRITICAL" if score > 0.75 else "HIGH" if score > 0.60 else "MEDIUM"
        conf = float(np.clip(score, 0.5, 0.99))

        desc = (
            f"ML Anomaly Alert for {sat_name} (NORAD {norad_id}). Anomaly score: {score:.3f}. "
            f"Primary contributing features: {top_str}."
        )

        report = AnomalyReport(
            norad_id=norad_id,
            name=sat_name,
            anomaly_type="ML_ORBITAL_ANOMALY",
            severity=severity if is_anomaly else "LOW",
            confidence_score=conf,
            description=desc,
            detected_at_utc=datetime.now(timezone.utc),
            top_contributing_features=top_3
        )

        return is_anomaly, score, top_3, report


def detect_orbital_maneuver(
    prev_record: SatelliteRecord,
    curr_record: SatelliteRecord,
    mean_motion_threshold: float = 0.05,
    inclination_threshold_deg: float = 0.01,
    bstar_jump_threshold: float = 0.001
) -> Optional[AnomalyReport]:
    """Detects orbital maneuver by comparing consecutive TLE epoch updates."""
    if prev_record.norad_id != curr_record.norad_id:
        return None

    delta_n = abs(curr_record.mean_motion - prev_record.mean_motion)
    delta_inc = abs(curr_record.inclination_deg - prev_record.inclination_deg)
    delta_bstar = abs(curr_record.bstar - prev_record.bstar)

    now_dt = datetime.now(timezone.utc)

    if delta_n >= mean_motion_threshold:
        return AnomalyReport(
            norad_id=curr_record.norad_id,
            name=curr_record.name,
            anomaly_type="MANEUVER",
            severity="HIGH" if delta_n > 0.2 else "MEDIUM",
            confidence_score=min(1.0, delta_n / 0.1),
            description=f"Significant mean motion shift: Δn = {delta_n:.4f} rev/day (Orbital Maneuver).",
            detected_at_utc=now_dt
        )
    elif delta_inc >= inclination_threshold_deg:
        return AnomalyReport(
            norad_id=curr_record.norad_id,
            name=curr_record.name,
            anomaly_type="MANEUVER",
            severity="HIGH",
            confidence_score=min(1.0, delta_inc / 0.05),
            description=f"Out-of-plane orbital plane change: Δi = {delta_inc:.4f}°.",
            detected_at_utc=now_dt
        )
    elif delta_bstar >= bstar_jump_threshold:
        return AnomalyReport(
            norad_id=curr_record.norad_id,
            name=curr_record.name,
            anomaly_type="DRAG_SPIKE",
            severity="MEDIUM",
            confidence_score=0.85,
            description=f"Abnormal BSTAR drag spike: ΔB* = {delta_bstar:.6f} 1/er.",
            detected_at_utc=now_dt
        )

    return None


def detect_rpo_proximity_operations(
    chaser: SatelliteRecord,
    target: SatelliteRecord,
    separation_distance_km: float,
    relative_velocity_kms: float
) -> Optional[AnomalyReport]:
    """Detects suspicious Rendezvous and Proximity Operations (RPO) between chaser and target."""
    if separation_distance_km < 50.0:
        now_dt = datetime.now(timezone.utc)
        severity = "CRITICAL" if separation_distance_km < 10.0 else "HIGH"
        confidence = min(1.0, (50.0 - separation_distance_km) / 40.0)

        return AnomalyReport(
            norad_id=chaser.norad_id,
            name=chaser.name,
            anomaly_type="RPO_PROXIMITY",
            severity=severity,
            confidence_score=round(confidence, 2),
            description=(
                f"Active Co-Orbital RPO detected! Object {chaser.name} (#{chaser.norad_id}) "
                f"is within {separation_distance_km:.2f} km of target {target.name} (#{target.norad_id}) "
                f"with relative speed {relative_velocity_kms:.3f} km/s."
            ),
            detected_at_utc=now_dt
        )

    return None


def calculate_threat_assessment(
    sat: SatelliteRecord,
    proximity_target_norad: Optional[int] = None,
    separation_distance_km: float = 9999.0
) -> ThreatAssessment:
    """Calculates strategic threat score and classification level for tracked satellite."""
    base_score = 1.0
    category = "RECONNAISSANCE"
    classification = "UNCLASSIFIED"
    action = "MONITOR"

    name_upper = sat.name.upper()

    if "DEBRIS" in name_upper or "R/B" in name_upper:
        category = "SPACE_DEBRIS"
        base_score = 0.5
    elif "STARLINK" in name_upper or "ONEWEB" in name_upper:
        category = "COMMUNICATIONS_CONSTELLATION"
        base_score = 1.5
    elif "CARTOSAT" in name_upper or "RISAT" in name_upper or "EOS" in name_upper:
        category = "EARTH_OBSERVATION"
        classification = "RESTRICTED"
        base_score = 3.0
    elif "GSAT" in name_upper or "NAVIC" in name_upper:
        category = "STRATEGIC_COMMUNICATIONS"
        classification = "CONFIDENTIAL"
        base_score = 4.0
    elif "CO-ORBITAL" in name_upper or "INSPECTOR" in name_upper or "DEFENSE" in name_upper:
        category = "ASAT_CO_ORBITAL"
        classification = "SECRET"
        base_score = 7.5

    if separation_distance_km < 100.0:
        base_score += min(5.0, (100.0 - separation_distance_km) / 10.0)
        action = "ALERT_DEFENSE_OPS"
        if base_score > 7.0:
            classification = "TOP SECRET"

    threat_score = float(np.clip(base_score, 0.0, 10.0))

    return ThreatAssessment(
        norad_id=sat.norad_id,
        name=sat.name,
        classification=classification,
        threat_score=round(threat_score, 1),
        threat_category=category,
        proximity_target_norad=proximity_target_norad,
        recommended_action=action
    )
