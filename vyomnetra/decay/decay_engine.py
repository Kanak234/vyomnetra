"""VYOMNETRA Re-entry & Orbital Lifetime Estimation Engine.

Calculates drag-induced semi-major axis decay rate da/dt, remaining orbital lifetime
for Low Earth Orbit (LEO) satellites based on BSTAR, ballistic coefficient B, and space weather.
Includes Monte Carlo re-entry window uncertainty (1,000 samples over B* and solar flux)
and sub-satellite ground track footprint generation.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple, Dict, Any
import numpy as np

from vyomnetra.ingest.models import SatelliteRecord
from vyomnetra.science.space_weather import estimate_atmospheric_density, get_current_space_weather
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.decay.engine")

EARTH_RADIUS_KM = 6378.137
MU_EARTH = 398600.4418  # km^3 / s^2


@dataclass
class ReentryMonteCarloResult:
    """Dataclass holding 1,000-sample Monte Carlo re-entry window analysis."""
    norad_id: int
    sat_name: str
    num_samples: int
    median_lifetime_days: float  # 50% confidence point
    confidence_50_pct_start_utc: datetime
    confidence_50_pct_end_utc: datetime
    confidence_95_pct_start_utc: datetime
    confidence_95_pct_end_utc: datetime
    ground_track_footprint: List[Dict[str, float]]  # List of {'lat': float, 'lon': float, 'alt_km': float}


@dataclass
class OrbitDecayEstimate:
    """Dataclass holding decay prediction results with built-in confidence intervals."""
    norad_id: int
    name: str
    current_perigee_km: float
    current_apogee_km: float
    decay_rate_km_per_day: float
    estimated_lifetime_days: float
    predicted_reentry_utc: Optional[datetime]
    reentry_risk_level: str  # HIGH, MEDIUM, LOW, SAFE
    confidence_interval_days: float = 0.0
    reentry_window_start_utc: Optional[datetime] = None
    reentry_window_end_utc: Optional[datetime] = None
    monte_carlo_result: Optional[ReentryMonteCarloResult] = None


class OrbitDecayEngine:
    """Engine estimating drag decay rate, remaining orbit lifetime, Monte Carlo windows, and ground track footprint."""

    def estimate_lifetime(
        self,
        sat: SatelliteRecord,
        f10_7: float = 150.0,
        kp: float = 3.0
    ) -> OrbitDecayEstimate:
        """Estimates decay rate (km/day) and remaining orbital lifetime in days with confidence intervals."""
        mean_motion = sat.mean_motion  # rev/day
        ecc = sat.eccentricity
        bstar = sat.bstar

        if mean_motion <= 0:
            mean_motion = 1.0

        n_rad_sec = (mean_motion * 2.0 * np.pi) / 86400.0
        a_km = (MU_EARTH / (n_rad_sec ** 2)) ** (1.0 / 3.0)

        r_perigee_km = a_km * (1.0 - ecc) - EARTH_RADIUS_KM
        r_apogee_km = a_km * (1.0 + ecc) - EARTH_RADIUS_KM

        avg_alt_km = (r_perigee_km + r_apogee_km) / 2.0

        if avg_alt_km > 1500.0:
            return OrbitDecayEstimate(
                norad_id=sat.norad_id,
                name=sat.name,
                current_perigee_km=round(r_perigee_km, 2),
                current_apogee_km=round(r_apogee_km, 2),
                decay_rate_km_per_day=0.0001,
                estimated_lifetime_days=36500.0,
                predicted_reentry_utc=None,
                reentry_risk_level="SAFE",
                confidence_interval_days=3650.0,
                reentry_window_start_utc=None,
                reentry_window_end_utc=None
            )

        rho = estimate_atmospheric_density(avg_alt_km, f10_7=f10_7, kp=kp)
        bstar_eff = max(1e-6, abs(bstar))

        v_orb_kms = np.sqrt(MU_EARTH / a_km)
        decay_rate_km_day = 2.0 * a_km * bstar_eff * (rho / 1.57e-7) * (v_orb_kms / 7.5) * 0.1
        decay_rate_km_day = max(0.001, decay_rate_km_day)

        usable_alt_km = max(0.0, avg_alt_km - 120.0)
        lifetime_days = usable_alt_km / decay_rate_km_day

        conf_days = round(lifetime_days * 0.20, 1)

        now_dt = datetime.now(timezone.utc)
        reentry_dt = now_dt + timedelta(days=lifetime_days) if lifetime_days < 3650.0 else None
        window_start = now_dt + timedelta(days=max(0.0, lifetime_days - conf_days)) if lifetime_days < 3650.0 else None
        window_end = now_dt + timedelta(days=lifetime_days + conf_days) if lifetime_days < 3650.0 else None

        if lifetime_days < 30.0:
            risk = "HIGH"
        elif lifetime_days < 180.0:
            risk = "MEDIUM"
        elif lifetime_days < 365.0:
            risk = "LOW"
        else:
            risk = "SAFE"

        # Monte Carlo Re-entry Window Analysis
        mc_result = self.simulate_reentry_monte_carlo(sat, base_lifetime_days=lifetime_days, f10_7=f10_7, kp=kp)

        return OrbitDecayEstimate(
            norad_id=sat.norad_id,
            name=sat.name,
            current_perigee_km=round(r_perigee_km, 2),
            current_apogee_km=round(r_apogee_km, 2),
            decay_rate_km_per_day=round(decay_rate_km_day, 4),
            estimated_lifetime_days=round(lifetime_days, 1),
            predicted_reentry_utc=reentry_dt,
            reentry_risk_level=risk,
            confidence_interval_days=conf_days,
            reentry_window_start_utc=window_start,
            reentry_window_end_utc=window_end,
            monte_carlo_result=mc_result
        )

    def simulate_reentry_monte_carlo(
        self,
        sat: SatelliteRecord,
        base_lifetime_days: float,
        f10_7: float = 150.0,
        kp: float = 3.0,
        num_samples: int = 1000
    ) -> ReentryMonteCarloResult:
        """Executes 1,000 Monte Carlo iterations varying B* and F10.7 to generate 50% and 95% confidence windows."""
        np.random.seed(sat.norad_id % 100000)

        # Sample variations: BSTAR (sigma = 15%), F10.7 (sigma = 20%)
        bstar_samples = np.random.normal(loc=1.0, scale=0.15, size=num_samples)
        f107_samples = np.random.normal(loc=1.0, scale=0.20, size=num_samples)

        bstar_samples = np.clip(bstar_samples, 0.5, 2.0)
        f107_samples = np.clip(f107_samples, 0.5, 2.0)

        # Lifetime variation scales inversely with drag factor (bstar * f107)
        lifetime_samples = base_lifetime_days / (bstar_samples * f107_samples)

        p25, p50, p75 = np.percentile(lifetime_samples, [25, 50, 75])
        p2_5, p97_5 = np.percentile(lifetime_samples, [2.5, 97.5])

        now_dt = datetime.now(timezone.utc)
        c50_start = now_dt + timedelta(days=max(0.0, float(p25)))
        c50_end = now_dt + timedelta(days=float(p75))

        c95_start = now_dt + timedelta(days=max(0.0, float(p2_5)))
        c95_end = now_dt + timedelta(days=float(p97_5))

        footprint = self.generate_reentry_ground_track_footprint(sat, num_points=50)

        return ReentryMonteCarloResult(
            norad_id=sat.norad_id,
            sat_name=sat.name,
            num_samples=num_samples,
            median_lifetime_days=round(float(p50), 2),
            confidence_50_pct_start_utc=c50_start,
            confidence_50_pct_end_utc=c50_end,
            confidence_95_pct_start_utc=c95_start,
            confidence_95_pct_end_utc=c95_end,
            ground_track_footprint=footprint
        )

    def generate_reentry_ground_track_footprint(
        self,
        sat: SatelliteRecord,
        num_points: int = 50
    ) -> List[Dict[str, float]]:
        """Generates sub-satellite latitude/longitude ground track footprint for re-entry corridor."""
        inc_deg = sat.inclination_deg
        raan_deg = sat.raan_deg

        footprint = []
        # Generate points along last orbital descent track
        for i in range(num_points):
            fraction = i / (num_points - 1)
            u = fraction * 2.0 * np.pi  # Argument of latitude

            lat = np.arcsin(np.sin(np.radians(inc_deg)) * np.sin(u))
            lon = np.radians(raan_deg) + np.arctan2(np.cos(np.radians(inc_deg)) * np.sin(u), np.cos(u)) - (fraction * np.pi)

            lat_deg = float(np.degrees(lat))
            lon_deg = float((np.degrees(lon) + 180.0) % 360.0 - 180.0)
            alt_km = float(150.0 - fraction * 70.0)  # Descent from 150 km to 80 km

            footprint.append({
                "latitude_deg": round(lat_deg, 4),
                "longitude_deg": round(lon_deg, 4),
                "altitude_km": round(alt_km, 2)
            })

        return footprint
