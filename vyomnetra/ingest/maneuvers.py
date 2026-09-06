"""Maneuver and Orbital Change Detection Engine.

Analyzes 30-day TLE history per NORAD object to flag orbital element jumps
(mean motion, inclination, eccentricity) exceeding 3-sigma statistical thresholds.
"""

import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.ingest.maneuvers")


class ManeuverEvent(BaseModel):
    """Data model representing a detected maneuver or orbital element discontinuity."""
    norad_id: int
    sat_name: str
    detected_at_utc: str
    parameter_changed: str  # e.g., 'mean_motion', 'inclination_deg', 'eccentricity'
    baseline_mean: float
    baseline_std: float
    observed_value: float
    sigma_deviation: float
    confidence_score: float
    maneuver_type: str  # e.g., 'STATION_KEEPING', 'ORBIT_RAISE', 'INCLINATION_CHANGE', 'UNKNOWN'


class ManeuverDetectionEngine:
    """Statistical change detection engine operating on TLE epoch history."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def detect_maneuvers_for_satellite(
        self,
        norad_id: int,
        history_days: int = 30,
        threshold_sigma: float = 3.0
    ) -> List[ManeuverEvent]:
        """Detects maneuver events for a given satellite by analyzing historical TLE epochs."""
        # Query satellite TLE history from database
        history = self.db_manager.get_satellite_history(norad_id, limit_days=history_days)
        if len(history) < 5:
            return []

        # Sort chronologically by epoch
        history = sorted(history, key=lambda s: s.epoch_utc)
        events: List[ManeuverEvent] = []

        mean_motions = np.array([s.mean_motion for s in history])
        inclinations = np.array([s.inclination_deg for s in history])
        eccentricities = np.array([s.eccentricity for s in history])

        # Evaluate most recent observation against preceding baseline window
        n_obs = len(history) - 1
        latest = history[-1]
        sat_name = latest.name

        metrics = [
            ("mean_motion", mean_motions[:-1], mean_motions[-1]),
            ("inclination_deg", inclinations[:-1], inclinations[-1]),
            ("eccentricity", eccentricities[:-1], eccentricities[-1]),
        ]

        for param_name, baseline_arr, obs_val in metrics:
            b_mean = float(np.mean(baseline_arr))
            b_std = float(np.std(baseline_arr))

            if b_std < 1e-7:
                b_std = 1e-7  # Prevent division by zero

            delta = abs(obs_val - b_mean)
            sigma_dev = delta / b_std

            if sigma_dev >= threshold_sigma:
                # Determine probable maneuver type
                if param_name == "mean_motion":
                    m_type = "ORBIT_RAISE" if obs_val > b_mean else "ORBIT_LOWER"
                elif param_name == "inclination_deg":
                    m_type = "INCLINATION_CHANGE"
                else:
                    m_type = "ECCENTRICITY_SHAPE_CHANGE"

                confidence = min(0.99, 0.5 + (sigma_dev / 20.0))

                evt = ManeuverEvent(
                    norad_id=norad_id,
                    sat_name=sat_name,
                    detected_at_utc=latest.epoch_utc,
                    parameter_changed=param_name,
                    baseline_mean=b_mean,
                    baseline_std=b_std,
                    observed_value=float(obs_val),
                    sigma_deviation=float(sigma_dev),
                    confidence_score=float(confidence),
                    maneuver_type=m_type
                )
                events.append(evt)
                logger.warning(
                    f"Maneuver detected for NORAD {norad_id} ({sat_name}): "
                    f"{param_name} jump = {sigma_dev:.2f}σ ({m_type})"
                )

        return events

    def scan_all_satellites_for_maneuvers(self, threshold_sigma: float = 3.0) -> List[ManeuverEvent]:
        """Scans all satellites in the database for recent maneuver events."""
        sats = self.db_manager.get_all_satellites()
        all_events: List[ManeuverEvent] = []

        norad_ids = list({s.norad_id for s in sats})
        for nid in norad_ids:
            evts = self.detect_maneuvers_for_satellite(nid, threshold_sigma=threshold_sigma)
            all_events.extend(evts)

        return all_events
