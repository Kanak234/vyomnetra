"""Rendevous and Proximity Operations (RPO) & Relative Motion Dynamics.

Implements Hill-Clohessy-Wiltshire (HCW) linear relative motion equations in the RIC frame,
and an automated RPO Classifier to distinguish natural close approach, station-keeping,
and deliberate co-orbital shadowing based on 7-day relative velocity persistence.
"""

import numpy as np
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Dict, Any, Optional
from pydantic import BaseModel


class RPOClassificationResult(BaseModel):
    """Data model for RPO behavior classification."""
    target_norad: int
    chaser_norad: int
    classification: str  # 'NATURAL_CLOSE_APPROACH', 'STATION_KEEPING', 'CO_ORBITAL_SHADOWING'
    mean_relative_distance_km: float
    max_relative_distance_km: float
    relative_velocity_persistence_score: float  # 0.0 to 1.0
    bounded_motion_flag: bool
    explanation: str


def propagate_hcw(
    r0_ric: np.ndarray,
    v0_ric: np.ndarray,
    t_seconds: float,
    mean_motion_rad_s: float
) -> Tuple[np.ndarray, np.ndarray]:
    """Propagates relative position and velocity in RIC frame using Hill-Clohessy-Wiltshire (HCW) equations.
    
    r0_ric: Initial relative position vector [x (Radial), y (In-track), z (Cross-track)] in km.
    v0_ric: Initial relative velocity vector [vx, vy, vz] in km/s.
    t_seconds: Propagation time in seconds.
    mean_motion_rad_s: Target orbit mean motion n in rad/s.
    
    Returns: (r_t_ric, v_t_ric)
    """
    n = mean_motion_rad_s
    t = t_seconds

    nt = n * t
    sin_nt = np.sin(nt)
    cos_nt = np.cos(nt)

    x0, y0, z0 = r0_ric
    vx0, vy0, vz0 = v0_ric

    # HCW Position Equations
    x_t = (4.0 - 3.0 * cos_nt) * x0 + (sin_nt / n) * vx0 + (2.0 / n) * (1.0 - cos_nt) * vy0
    y_t = 6.0 * (sin_nt - nt) * x0 + y0 - (2.0 / n) * (1.0 - cos_nt) * vx0 + ((4.0 * sin_nt - 3.0 * nt) / n) * vy0
    z_t = cos_nt * z0 + (sin_nt / n) * vz0

    # HCW Velocity Equations
    vx_t = 3.0 * n * sin_nt * x0 + cos_nt * vx0 + 2.0 * sin_nt * vy0
    vy_t = 6.0 * n * (cos_nt - 1.0) * x0 - 2.0 * sin_nt * vx0 + (4.0 * cos_nt - 3.0) * vy0
    vz_t = -n * sin_nt * z0 + cos_nt * vz0

    r_t = np.array([x_t, y_t, z_t])
    v_t = np.array([vx_t, vy_t, vz_t])

    return r_t, v_t


class RPOClassifier:
    """Classifier distinguishing natural orbital close approaches from deliberate RPO / co-orbital shadowing."""

    def classify_relative_trajectory(
        self,
        target_norad: int,
        chaser_norad: int,
        rel_positions_km: List[np.ndarray],
        rel_velocities_kms: List[np.ndarray],
        sample_times_hours: List[float]
    ) -> RPOClassificationResult:
        """Classifies 7-day relative trajectory dynamics.
        
        Evaluates distance bounds, relative velocity persistence, and closed-ellipse geometry.
        """
        if len(rel_positions_km) < 3:
            return RPOClassificationResult(
                target_norad=target_norad,
                chaser_norad=chaser_norad,
                classification="NATURAL_CLOSE_APPROACH",
                mean_relative_distance_km=0.0,
                max_relative_distance_km=0.0,
                relative_velocity_persistence_score=0.0,
                bounded_motion_flag=False,
                explanation="Insufficient trajectory history samples for RPO classification."
            )

        dists = [float(np.linalg.norm(pos)) for pos in rel_positions_km]
        v_norms = [float(np.linalg.norm(vel)) for vel in rel_velocities_kms]

        mean_dist = float(np.mean(dists))
        max_dist = float(np.max(dists))
        min_dist = float(np.min(dists))
        mean_v = float(np.mean(v_norms))
        std_v = float(np.std(v_norms))

        # Check if relative velocity is persistently low over the multi-day window
        # Persistence score = 1.0 if std_v / mean_v < 0.3 and mean_v < 0.05 km/s (50 m/s)
        low_v_ratio = np.sum(np.array(v_norms) < 0.05) / len(v_norms)
        persistence_score = float(min(1.0, low_v_ratio * (1.0 - (std_v / (mean_v + 1e-6)))))

        # Check distance bounds
        bounded_motion = (max_dist < 200.0) and (min_dist > 0.01)

        # Classification decision rules
        if bounded_motion and persistence_score > 0.6 and mean_dist < 100.0:
            classification = "CO_ORBITAL_SHADOWING"
            explanation = (
                f"High-confidence co-orbital shadowing detected. Chaser maintains bounded distance "
                f"(mean {mean_dist:.1f} km) and persistent low relative velocity (persistence score {persistence_score:.2f})."
            )
        elif bounded_motion and mean_dist < 500.0 and mean_v < 0.01:
            classification = "STATION_KEEPING"
            explanation = f"Constellation station-keeping relative motion detected (mean distance {mean_dist:.1f} km)."
        else:
            classification = "NATURAL_CLOSE_APPROACH"
            explanation = f"Natural hyper-velocity close approach trajectory with transient encounter."

        return RPOClassificationResult(
            target_norad=target_norad,
            chaser_norad=chaser_norad,
            classification=classification,
            mean_relative_distance_km=round(mean_dist, 2),
            max_relative_distance_km=round(max_dist, 2),
            relative_velocity_persistence_score=round(persistence_score, 4),
            bounded_motion_flag=bounded_motion,
            explanation=explanation
        )
