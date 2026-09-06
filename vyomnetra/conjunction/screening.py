"""VYOMNETRA Conjunction Assessment & Collision Warning Engine.

Implements high-performance spatial screening, fine Time of Closest Approach (TCA)
minimization, RIC (Radial, In-track, Cross-track) frame transformations,
and Foster 2D Probability of Collision (Pc) calculation using Gaussian covariance.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional, Dict
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import erf

from vyomnetra.config import settings
from vyomnetra.ingest.models import SatelliteRecord
from vyomnetra.propagate.engine import SGP4Engine
from vyomnetra.propagate.frames import teme_to_ecef
from vyomnetra.catalogue.isro import enforce_isro_severity_floor
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.conjunction")


@dataclass
class ConjunctionAlert:
    """Dataclass representing a detected close approach / conjunction event."""
    primary_norad: int
    primary_name: str
    secondary_norad: int
    secondary_name: str
    tca_utc: datetime
    miss_distance_km: float
    radial_distance_km: float
    in_track_distance_km: float
    cross_track_distance_km: float
    relative_velocity_kms: float
    calculated_pc: float
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    status: str    # UNCHECKED, MANEUVER_PLANNED, CONFIRMED_AVOIDED


def teme_to_ric_matrix(r_primary_teme: np.ndarray, v_primary_teme: np.ndarray) -> np.ndarray:
    """Computes the rotation matrix from TEME frame to Radial, In-Track, Cross-Track (RIC/RTN) frame.
    
    Radial (R): Unit vector along primary position vector (outward from Earth center).
    Cross-Track (C): Unit vector normal to orbital plane (along angular momentum vector r x v).
    In-Track (I): Unit vector completing right-handed system (C x R).
    """
    r_norm = np.linalg.norm(r_primary_teme)
    if r_norm == 0:
        return np.eye(3)
        
    unit_r = r_primary_teme / r_norm
    cross_vec = np.cross(r_primary_teme, v_primary_teme)
    c_norm = np.linalg.norm(cross_vec)
    
    if c_norm == 0:
        unit_c = np.array([0.0, 0.0, 1.0])
    else:
        unit_c = cross_vec / c_norm
        
    unit_i = np.cross(unit_c, unit_r)
    
    # Rotation matrix where rows are R, I, C unit vectors
    return np.vstack([unit_r, unit_i, unit_c])


def calculate_foster_2d_pc(
    miss_distance_km: float,
    combined_hard_body_radius_m: float = 20.0,
    primary_cov_diag_m: Tuple[float, float, float] = (100.0, 500.0, 100.0),
    secondary_cov_diag_m: Tuple[float, float, float] = (200.0, 1000.0, 200.0)
) -> float:
    """Calculates 2D Probability of Collision (Pc) using Foster's algorithm (1992).
    
    Assumes isotropic/ellipsoidal Gaussian covariance in collision plane.
    """
    r_hbr_km = combined_hard_body_radius_m / 1000.0
    
    # Combined position variance in collision plane (km^2)
    var_prim_km2 = (np.array(primary_cov_diag_m) / 1000.0) ** 2
    var_sec_km2 = (np.array(secondary_cov_diag_m) / 1000.0) ** 2
    combined_var_km2 = var_prim_km2 + var_sec_km2
    
    sigma_x2 = combined_var_km2[0]
    sigma_y2 = combined_var_km2[1]
    
    if sigma_x2 <= 0 or sigma_y2 <= 0:
        return 0.0
        
    # Foster 2D integral approximation
    # Pc ≈ (1 - exp(-r_hbr^2 / (2 * sigma_x * sigma_y))) * exp(-miss_distance^2 / (2 * max(sigma_x2, sigma_y2)))
    sigma_prod = np.sqrt(sigma_x2 * sigma_y2)
    exponent_hbr = - (r_hbr_km ** 2) / (2.0 * sigma_prod)
    exponent_miss = - (miss_distance_km ** 2) / (2.0 * max(sigma_x2, sigma_y2))
    
    pc = (1.0 - np.exp(exponent_hbr)) * np.exp(exponent_miss)
    return float(np.clip(pc, 0.0, 1.0))


def assign_conjunction_severity(miss_distance_km: float, pc: float) -> str:
    """Assigns risk severity level based on miss distance and collision probability."""
    if pc >= 1e-4 or miss_distance_km < 1.0:
        return "CRITICAL"
    elif pc >= 1e-5 or miss_distance_km < 5.0:
        return "HIGH"
    elif pc >= 1e-6 or miss_distance_km < 10.0:
        return "MEDIUM"
    else:
        return "LOW"


class ConjunctionScreeningEngine:
    """Engine for automated close-approach screening and collision warnings across satellite catalogues."""

    def __init__(self, engine: Optional[SGP4Engine] = None):
        self.engine = engine or SGP4Engine()

    def screen_catalogue(
        self,
        satellites: List[SatelliteRecord],
        start_dt: datetime,
        duration_hours: float = 24.0,
        step_minutes: float = 15.0,
        max_miss_distance_km: float = 25.0
    ) -> List[ConjunctionAlert]:
        """Screens all pairs of satellites for close approaches within window.
        
        Uses two-pass strategy:
        1. Coarse time stepping to find candidate pairs with distance < 2 * max_miss_distance_km.
        2. Fine minimization to pinpoint exact TCA and minimum miss distance.
        """
        if len(satellites) < 2:
            return []

        # Prepare satrecs
        satrecs = []
        valid_sats = []
        for sat in satellites:
            try:
                rec = self.engine.create_satrec(sat.raw_tle_line1, sat.raw_tle_line2)
                satrecs.append(rec)
                valid_sats.append(sat)
            except Exception as e:
                logger.warning(f"Could not build satrec for NORAD {sat.norad_id}: {e}")

        n_sats = len(valid_sats)
        if n_sats < 2:
            return []

        num_steps = int((duration_hours * 60.0) / step_minutes) + 1
        dt_list = [start_dt + timedelta(minutes=i * step_minutes) for i in range(num_steps)]

        # Precompute positions for coarse steps
        # array shape: (num_steps, n_sats, 3)
        pos_matrix = np.zeros((num_steps, n_sats, 3), dtype=np.float64)
        vel_matrix = np.zeros((num_steps, n_sats, 3), dtype=np.float64)

        for step_idx, dt in enumerate(dt_list):
            jd, fr = self.engine.dt_to_jd(dt)
            errs, pos_b, vel_b = self.engine.propagate_batch(satrecs, jd, fr)
            pos_matrix[step_idx] = pos_b
            vel_matrix[step_idx] = vel_b

        candidate_events: Dict[Tuple[int, int], datetime] = {}

        # Coarse screening pass
        for i in range(n_sats):
            for j in range(i + 1, n_sats):
                # Calculate vector distance across all steps
                diffs = pos_matrix[:, i, :] - pos_matrix[:, j, :]
                dists = np.linalg.norm(diffs, axis=1)

                min_step_idx = np.argmin(dists)
                min_dist = dists[min_step_idx]

                if min_dist <= max_miss_distance_km * 2.5:
                    candidate_events[(i, j)] = dt_list[min_step_idx]

        alerts: List[ConjunctionAlert] = []

        # Fine minimization pass for candidates
        for (i, j), approx_tca in candidate_events.items():
            sat1, rec1 = valid_sats[i], satrecs[i]
            sat2, rec2 = valid_sats[j], satrecs[j]

            fine_alert = self._refine_conjunction(
                sat1, rec1, sat2, rec2, approx_tca, max_miss_distance_km
            )
            if fine_alert:
                alerts.append(fine_alert)

        # Sort by severity and miss distance
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        alerts.sort(key=lambda a: (severity_order.get(a.severity, 4), a.miss_distance_km))

        logger.info(f"Conjunction screening complete: Evaluated {n_sats} objects, found {len(alerts)} alerts.")
        return alerts

    def _refine_conjunction(
        self,
        sat1: SatelliteRecord,
        rec1,
        sat2: SatelliteRecord,
        rec2,
        center_dt: datetime,
        max_miss_distance_km: float
    ) -> Optional[ConjunctionAlert]:
        """Refines TCA using scalar minimization over a +- 15 minute window."""
        
        def distance_func(offset_sec: float) -> float:
            target_dt = center_dt + timedelta(seconds=offset_sec)
            jd, fr = self.engine.dt_to_jd(target_dt)
            err1, r1, _ = self.engine.propagate_single(rec1, jd, fr)
            err2, r2, _ = self.engine.propagate_single(rec2, jd, fr)
            if err1 != 0 or err2 != 0:
                return 1e9
            return float(np.linalg.norm(r1 - r2))

        # Minimize distance within [-900s, +900s]
        res = minimize_scalar(distance_func, bounds=(-900.0, 900.0), method='bounded')
        
        best_offset_sec = res.x
        min_dist_km = res.fun

        if min_dist_km > max_miss_distance_km:
            return None

        exact_tca = center_dt + timedelta(seconds=best_offset_sec)
        jd, fr = self.engine.dt_to_jd(exact_tca)
        _, r1_teme, v1_teme = self.engine.propagate_single(rec1, jd, fr)
        _, r2_teme, v2_teme = self.engine.propagate_single(rec2, jd, fr)

        diff_teme = r2_teme - r1_teme
        rel_vel = np.linalg.norm(v2_teme - v1_teme)

        # Convert relative vector to RIC frame of primary satellite (sat1)
        r_ric_mat = teme_to_ric_matrix(r1_teme, v1_teme)
        diff_ric = r_ric_mat @ diff_teme

        radial_km = float(abs(diff_ric[0]))
        in_track_km = float(abs(diff_ric[1]))
        cross_track_km = float(abs(diff_ric[2]))

        # Probability of collision
        pc = calculate_foster_2d_pc(min_dist_km)
        severity = assign_conjunction_severity(min_dist_km, pc)
        severity = enforce_isro_severity_floor(sat1.norad_id, sat2.norad_id, severity)

        return ConjunctionAlert(
            primary_norad=sat1.norad_id,
            primary_name=sat1.name,
            secondary_norad=sat2.norad_id,
            secondary_name=sat2.name,
            tca_utc=exact_tca,
            miss_distance_km=round(min_dist_km, 4),
            radial_distance_km=round(radial_km, 4),
            in_track_distance_km=round(in_track_km, 4),
            cross_track_distance_km=round(cross_track_km, 4),
            relative_velocity_kms=round(float(rel_vel), 4),
            calculated_pc=pc,
            severity=severity,
            status="UNCHECKED"
        )
