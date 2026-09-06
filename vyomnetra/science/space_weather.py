"""VYOMNETRA Astrophysics & Space Weather Physics Engine.

Models solar radio flux (F10.7), geomagnetic storm indices (Kp, Ap),
and upper atmospheric density variations (Harris-Priester / Jacchia approximation)
influencing Low Earth Orbit (LEO) drag.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import numpy as np

from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.science.space_weather")


@dataclass
class SpaceWeatherState:
    """Dataclass holding solar and geomagnetic activity indices."""
    timestamp_utc: datetime
    f10_7_index: float      # Solar radio flux (sfu, typically 70 - 250)
    kp_index: float         # Planetary K-index (0.0 - 9.0)
    ap_index: float         # Equivalent planetary amplitude index (0 - 400)
    storm_class: str        # NONE, G1_MINOR, G2_MODERATE, G3_STRONG, G4_SEVERE, G5_EXTREME
    rho_multiplier: float   # Density amplification factor relative to quiet atmosphere


def classify_geomagnetic_storm(kp_index: float) -> str:
    """Classifies geomagnetic storm severity based on NOAA scale."""
    if kp_index >= 9.0:
        return "G5_EXTREME"
    elif kp_index >= 8.0:
        return "G4_SEVERE"
    elif kp_index >= 7.0:
        return "G3_STRONG"
    elif kp_index >= 6.0:
        return "G2_MODERATE"
    elif kp_index >= 5.0:
        return "G1_MINOR"
    else:
        return "NONE"


def estimate_atmospheric_density(
    altitude_km: float,
    f10_7: float = 150.0,
    kp: float = 3.0
) -> float:
    """Estimates neutral atmospheric density rho (kg/m^3) at given altitude (km) using simplified Harris-Priester model.
    
    Valid for LEO altitudes (100 km - 1000 km).
    """
    if altitude_km < 100.0:
        return 1.225  # Sea level density approx (kg/m^3)
    elif altitude_km > 1000.0:
        return 1e-15  # Extremely tenuous exosphere

    # Base scale height model (US Standard Atmosphere / Jacchia approx)
    # rho_0 = 1.225 kg/m3 at h0=0 km, H = 8.5 km to 50 km depending on altitude
    if altitude_km < 200:
        h0 = 120.0
        rho0 = 2.4e-8  # kg/m^3
        H = 25.0
    elif altitude_km < 400:
        h0 = 200.0
        rho0 = 2.8e-10
        H = 45.0
    elif altitude_km < 600:
        h0 = 400.0
        rho0 = 2.8e-12
        H = 60.0
    else:
        h0 = 600.0
        rho0 = 1.4e-13
        H = 80.0

    # Base density
    rho_base = rho0 * np.exp(- (altitude_km - h0) / H)

    # Solar flux & Geomagnetic storm multiplier
    # Solar flux heating expands upper atmosphere
    f10_7_factor = 1.0 + 0.005 * (f10_7 - 100.0)
    kp_factor = 1.0 + 0.15 * max(0.0, kp - 3.0)

    rho_total = rho_base * max(0.5, f10_7_factor) * max(1.0, kp_factor)
    return float(rho_total)


def get_current_space_weather() -> SpaceWeatherState:
    """Returns real-time auto-fetched space weather state from NOAA SWPC with graceful fallback."""
    now_dt = datetime.now(timezone.utc)
    f10_7 = 145.0
    kp = 3.2
    ap = 15.0

    # Attempt live fetch from NOAA SWPC JSON endpoints
    try:
        import urllib.request
        import json
        req = urllib.request.Request(
            "https://services.swpc.noaa.gov/json/f107_cm_flux.json",
            headers={"User-Agent": "VYOMNETRA-SSA-Platform/1.0"}
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                f10_7 = float(data[-1].get("flux", 145.0))
    except Exception as e:
        logger.debug(f"NOAA F10.7 fetch fallback: {e}")

    try:
        import urllib.request
        import json
        req = urllib.request.Request(
            "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json",
            headers={"User-Agent": "VYOMNETRA-SSA-Platform/1.0"}
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 1:
                latest_row = data[-1]
                kp = float(latest_row[1])
                ap = float(latest_row[2]) if len(latest_row) > 2 else kp * 4.0
    except Exception as e:
        logger.debug(f"NOAA Kp fetch fallback: {e}")

    storm = classify_geomagnetic_storm(kp)
    rho_mult = 1.0 + 0.15 * max(0.0, kp - 3.0)

    return SpaceWeatherState(
        timestamp_utc=now_dt,
        f10_7_index=f10_7,
        kp_index=kp,
        ap_index=ap,
        storm_class=storm,
        rho_multiplier=round(rho_mult, 2)
    )

