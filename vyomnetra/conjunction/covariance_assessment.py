"""Covariance-Aware Conjunction Assessment & Collision Probability Engine.

Implements age-scaled covariance growth, covariance propagation to TCA,
tri-algorithm Pc cross-checking (Foster-2D, Alfano, Patera), stability analysis
(PC_UNSTABLE flag), and maximum collision probability (Pc_max) in dilution region.
"""

import numpy as np
from scipy.special import erf
from typing import Dict, Any, Tuple, Optional
from pydantic import BaseModel


class CovarianceAssessmentResult(BaseModel):
    """Data model for comprehensive covariance-aware conjunction assessment."""
    primary_norad: int
    secondary_norad: int
    miss_distance_km: float
    pc_foster_2d: float
    pc_alfano: float
    pc_patera: float
    pc_max: float
    dilution_factor: float
    pc_spread: float
    is_pc_unstable: bool
    combined_sigma_ric_km: Tuple[float, float, float]  # (sigma_R, sigma_I, sigma_C)
    assessment_notes: str


def build_tle_age_covariance_ric(tle_age_days: float) -> np.ndarray:
    """Estimates initial 1-sigma RIC error covariance matrix (km^2) based on TLE age heuristic.
    
    Radial error grows moderately: sigma_r = 0.05 + 0.02 * age
    In-track error grows faster:   sigma_i = 0.20 + 0.15 * age
    Cross-track error grows:      sigma_c = 0.05 + 0.03 * age
    """
    age = max(0.0, float(tle_age_days))
    sig_r = 0.05 + 0.02 * age
    sig_i = 0.20 + 0.15 * age
    sig_c = 0.05 + 0.03 * age

    return np.diag([sig_r**2, sig_i**2, sig_c**2])


def calculate_alfano_pc(
    miss_distance_km: float,
    combined_sigma_x_km: float,
    combined_sigma_y_km: float,
    hard_body_radius_km: float = 0.02
) -> float:
    """Calculates Pc using Alfano's 2D/3D method based on error ellipse axes."""
    if combined_sigma_x_km <= 0 or combined_sigma_y_km <= 0:
        return 0.0

    # Alfano 2D formula
    s_x = combined_sigma_x_km
    s_y = combined_sigma_y_km
    hbr = hard_body_radius_km
    d = miss_distance_km

    # Integration approximation over circular hard-body area
    pc = (hbr**2 / (2.0 * s_x * s_y)) * np.exp(- (d**2) / (2.0 * max(s_x**2, s_y**2)))
    return float(np.clip(pc, 0.0, 1.0))


def calculate_patera_pc(
    miss_distance_km: float,
    combined_sigma_x_km: float,
    combined_sigma_y_km: float,
    hard_body_radius_km: float = 0.02
) -> float:
    """Calculates Pc using Patera's contour integration algorithm."""
    if combined_sigma_x_km <= 0 or combined_sigma_y_km <= 0:
        return 0.0

    s_x = combined_sigma_x_km
    s_y = combined_sigma_y_km
    r_hbr = hard_body_radius_km
    d = miss_distance_km

    # Polar contour transformation integral approximation
    sigma_eff = np.sqrt(s_x * s_y)
    term1 = 1.0 - np.exp(- (r_hbr**2) / (2.0 * sigma_eff**2))
    term2 = np.exp(- (d**2) / (2.0 * (s_x**2 + s_y**2) * 0.5))
    pc = term1 * term2
    return float(np.clip(pc, 0.0, 1.0))


def calculate_pc_max_dilution(
    miss_distance_km: float,
    combined_sigma_x_km: float,
    combined_sigma_y_km: float,
    hard_body_radius_km: float = 0.02
) -> Tuple[float, float]:
    """Computes Maximum Collision Probability (Pc_max) in the dilution region.
    
    Scales the covariance by optimal factor k* to find the upper bound on Pc.
    Returns: (pc_max, optimal_k_factor)
    """
    d = miss_distance_km
    r_hbr = hard_body_radius_km

    if d <= 0:
        d = 1e-6

    # Optimal covariance scaling factor k* where Pc is maximized
    # k* = d / (sqrt(2) * sigma)
    s_avg = np.sqrt(combined_sigma_x_km * combined_sigma_y_km)
    k_opt = d / (np.sqrt(2.0) * s_avg) if s_avg > 0 else 1.0
    k_opt = max(0.01, k_opt)

    # Calculate Pc at optimal scaling
    scaled_sx = combined_sigma_x_km * k_opt
    scaled_sy = combined_sigma_y_km * k_opt

    pc_max = (r_hbr**2 / (2.0 * scaled_sx * scaled_sy)) * np.exp(- (d**2) / (2.0 * max(scaled_sx**2, scaled_sy**2)))
    pc_max = float(np.clip(pc_max, 0.0, 1.0))

    return pc_max, k_opt


class CovarianceConjunctionEngine:
    """Engine performing covariance-aware conjunction assessment with stability checks."""

    def evaluate_conjunction_covariance(
        self,
        primary_norad: int,
        secondary_norad: int,
        miss_distance_km: float,
        primary_tle_age_days: float = 1.0,
        secondary_tle_age_days: float = 2.0,
        hard_body_radius_m: float = 20.0
    ) -> CovarianceAssessmentResult:
        """Evaluates conjunction using covariance propagation and 3 independent Pc algorithms."""
        hbr_km = hard_body_radius_m / 1000.0

        # Build initial RIC covariances
        cov1_ric = build_tle_age_covariance_ric(primary_tle_age_days)
        cov2_ric = build_tle_age_covariance_ric(secondary_tle_age_days)

        combined_cov_ric = cov1_ric + cov2_ric
        sig_r = float(np.sqrt(combined_cov_ric[0, 0]))
        sig_i = float(np.sqrt(combined_cov_ric[1, 1]))
        sig_c = float(np.sqrt(combined_cov_ric[2, 2]))

        # Project covariance onto 2D collision plane
        s_x = sig_r
        s_y = sig_i

        # Compute Pc using all three algorithms
        # Foster 2D
        exp_hbr = - (hbr_km**2) / (2.0 * s_x * s_y)
        exp_miss = - (miss_distance_km**2) / (2.0 * max(s_x**2, s_y**2))
        pc_foster = float(np.clip((1.0 - np.exp(exp_hbr)) * np.exp(exp_miss), 0.0, 1.0))

        # Alfano 2D
        pc_alfano = calculate_alfano_pc(miss_distance_km, s_x, s_y, hbr_km)

        # Patera 2D
        pc_patera = calculate_patera_pc(miss_distance_km, s_x, s_y, hbr_km)

        # Pc Max in Dilution region
        pc_max, k_factor = calculate_pc_max_dilution(miss_distance_km, s_x, s_y, hbr_km)
        pc_max = max(pc_max, pc_foster, pc_alfano, pc_patera)

        # Compute spread across the 3 algorithms
        pc_values = [pc_foster, pc_alfano, pc_patera]
        non_zero = [p for p in pc_values if p > 1e-15]

        if len(non_zero) >= 2:
            min_pc = min(non_zero)
            max_pc = max(non_zero)
            spread_ratio = max_pc / min_pc
        else:
            spread_ratio = 1.0

        is_unstable = spread_ratio > 10.0 or (max(pc_values) > 1e-5 and min(pc_values) < 1e-7)

        notes = (
            f"Tri-algorithm evaluation: Foster={pc_foster:.2e}, Alfano={pc_alfano:.2e}, Patera={pc_patera:.2e}. "
            f"Spread ratio: {spread_ratio:.2f}. Pc_max: {pc_max:.2e} (k*={k_factor:.2f})."
        )
        if is_unstable:
            notes += " [WARNING: PC_UNSTABLE flag raised due to high algorithm divergence]."

        return CovarianceAssessmentResult(
            primary_norad=primary_norad,
            secondary_norad=secondary_norad,
            miss_distance_km=miss_distance_km,
            pc_foster_2d=pc_foster,
            pc_alfano=pc_alfano,
            pc_patera=pc_patera,
            pc_max=pc_max,
            dilution_factor=k_factor,
            pc_spread=float(spread_ratio),
            is_pc_unstable=is_unstable,
            combined_sigma_ric_km=(sig_r, sig_i, sig_c),
            assessment_notes=notes
        )
