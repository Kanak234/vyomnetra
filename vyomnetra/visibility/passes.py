"""Topocentric Satellite Pass Prediction Engine.

Computes satellite passes over ground sites (AOS, TCA, LOS, Max Elevation, Slant Range),
evaluates solar illumination states, and estimates visual magnitudes.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
import numpy as np
from sgp4.api import Satrec, WGS72, jday

from vyomnetra.config import GroundSite, settings
from vyomnetra.ingest.models import SatelliteRecord
from vyomnetra.propagate.engine import SGP4Engine
from vyomnetra.propagate.frames import teme_to_ecef, ecef_to_topocentric
from vyomnetra.visibility.illumination import is_satellite_sunlit, is_naked_eye_visible
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.visibility.passes")


@dataclass
class PassEvent:
    """Dataclass representing a predicted satellite pass over a ground site."""
    sat_name: str
    norad_id: int
    site_name: str
    aos_dt: datetime
    tca_dt: datetime
    los_dt: datetime
    max_elevation_deg: float
    aos_azimuth_deg: float
    tca_azimuth_deg: float
    los_azimuth_deg: float
    min_range_km: float
    duration_seconds: float
    is_sunlit_at_tca: bool
    is_naked_eye_visible: bool
    est_magnitude: float

    def format_pass_summary(self) -> str:
        """Returns concise human-readable summary string of pass."""
        vis_str = "VIS (Naked Eye)" if self.is_naked_eye_visible else ("Sunlit" if self.is_sunlit_at_tca else "Eclipsed")
        return (
            f"[{self.sat_name} #{self.norad_id}] Over {self.site_name} | "
            f"AOS: {self.aos_dt.strftime('%H:%M:%S UTC')} | "
            f"TCA: {self.tca_dt.strftime('%H:%M:%S UTC')} (Max El: {self.max_elevation_deg:.1f}°, Mag: {self.est_magnitude:.1f}) | "
            f"LOS: {self.los_dt.strftime('%H:%M:%S UTC')} | State: {vis_str}"
        )


# Dataclass aliases for API compatibility
GroundPass = PassEvent
PredictedPass = PassEvent


class PassPredictor:
    """Predicts topocentric passes over ground sites."""

    def __init__(self, engine: Optional[SGP4Engine] = None):
        self.engine = engine or SGP4Engine(gravity_model=WGS72)

    def estimate_visual_magnitude(self, sat_name: str, range_km: float, max_el_deg: float) -> float:
        """Estimates visual optical magnitude m = V0 + 5 log10(R / 1000km)."""
        # Baseline intrinsic magnitude V0 for major objects
        v0 = -1.8 if "ISS" in sat_name.upper() else 3.5
        
        # Distance scaling
        range_factor = 5.0 * np.log10(max(range_km, 100.0) / 1000.0)
        
        # Extinction & phase factor near horizon
        extinction = 0.2 / (np.sin(np.radians(max(max_el_deg, 5.0))) + 0.1)
        
        return round(v0 + range_factor + extinction, 1)

    def predict_passes(
        self,
        sat_record: SatelliteRecord,
        site: GroundSite,
        start_dt: datetime,
        duration_hours: float = 24.0,
        min_elevation_deg: float = 10.0,
        step_seconds: float = 30.0
    ) -> List[PassEvent]:
        """Predicts all satellite passes exceeding min_elevation_deg over duration_hours.
        
        Args:
            sat_record: Satellite record
            site: Ground site configuration
            start_dt: UTC start time
            duration_hours: Prediction window in hours
            min_elevation_deg: Minimum elevation threshold in degrees
            step_seconds: Search sampling step in seconds
            
        Returns:
            List of PassEvent dataclass instances
        """
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        satrec = self.engine.create_satrec(sat_record=sat_record)
        passes: List[PassEvent] = []

        total_steps = int((duration_hours * 3600.0) / step_seconds)
        
        in_pass = False
        pass_points = []

        for step in range(total_steps):
            t_dt = start_dt + timedelta(seconds=step * step_seconds)
            
            # SGP4 propagation to t_dt
            jd, fr = jday(t_dt.year, t_dt.month, t_dt.day, t_dt.hour, t_dt.minute, t_dt.second + t_dt.microsecond * 1e-6)
            err, r_teme, v_teme = self.engine.propagate_single(satrec, jd, fr)
            
            if err != 0:
                continue

            r_ecef, v_ecef = teme_to_ecef(r_teme, v_teme, t_dt)
            az_deg, el_deg, range_km = ecef_to_topocentric(r_ecef, site)

            if el_deg >= min_elevation_deg:
                if not in_pass:
                    in_pass = True
                    pass_points = []
                pass_points.append((t_dt, az_deg, el_deg, range_km, r_ecef))
            else:
                if in_pass:
                    in_pass = False
                    if pass_points:
                        pass_event = self._build_pass_event(sat_record, site, pass_points, min_elevation_deg)
                        if pass_event:
                            passes.append(pass_event)
                    pass_points = []

        # Handle pass in progress at window end
        if in_pass and pass_points:
            pass_event = self._build_pass_event(sat_record, site, pass_points, min_elevation_deg)
            if pass_event:
                passes.append(pass_event)

        logger.info(f"Pass Predictor found {len(passes)} passes for {sat_record.name} over {site.name} ({duration_hours}h window).")
        return passes

    def _build_pass_event(
        self,
        sat_record: SatelliteRecord,
        site: GroundSite,
        pass_points: List[Tuple[datetime, float, float, float, np.ndarray]],
        min_elevation_deg: float
    ) -> Optional[PassEvent]:
        """Constructs a PassEvent from sampled pass points."""
        if not pass_points:
            return None

        # Sort by elevation to find Max Elevation Time (TCA)
        tca_pt = max(pass_points, key=lambda pt: pt[2])
        
        aos_pt = pass_points[0]
        los_pt = pass_points[-1]

        aos_dt, aos_az, _, _, _ = aos_pt
        tca_dt, tca_az, max_el, min_rng, r_ecef_tca = tca_pt
        los_dt, los_az, _, _, _ = los_pt

        duration = (los_dt - aos_dt).total_seconds()
        
        # Check solar illumination at TCA
        sunlit, _ = is_satellite_sunlit(r_ecef_tca, tca_dt)
        naked_eye = is_naked_eye_visible(r_ecef_tca, site, tca_dt, max_el, min_elevation_deg)
        est_mag = self.estimate_visual_magnitude(sat_record.name, min_rng, max_el)

        return PassEvent(
            sat_name=sat_record.name,
            norad_id=sat_record.norad_id,
            site_name=site.name,
            aos_dt=aos_dt,
            tca_dt=tca_dt,
            los_dt=los_dt,
            max_elevation_deg=max_el,
            aos_azimuth_deg=aos_az,
            tca_azimuth_deg=tca_az,
            los_azimuth_deg=los_az,
            min_range_km=min_rng,
            duration_seconds=duration,
            is_sunlit_at_tca=sunlit,
            is_naked_eye_visible=naked_eye,
            est_magnitude=est_mag
        )
