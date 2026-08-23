"""Data models for satellite orbital elements and fetch provenance."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any


@dataclass
class SatelliteRecord:
    """Normalized orbital element record for a satellite object."""
    norad_id: int
    name: str
    international_designator: str
    object_type: str
    epoch_utc: str
    epoch_jd: float
    mean_motion: float
    eccentricity: float
    inclination_deg: float
    raan_deg: float
    arg_perigee_deg: float
    mean_anomaly_deg: float
    bstar: float
    mean_motion_dot: float
    mean_motion_ddot: float
    ephemeris_type: int
    element_set_no: int
    rev_at_epoch: int
    raw_tle_line1: Optional[str] = None
    raw_tle_line2: Optional[str] = None
    fetch_id: Optional[int] = None
    updated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def get_epoch_dt(self) -> datetime:
        """Parses epoch_utc string into datetime object."""
        # Handle ISO or standard UTC format
        clean_utc = self.epoch_utc.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(clean_utc)
        except Exception:
            # Fallback if simplified format
            return datetime.now(timezone.utc)

    def get_epoch_age_days(self, now_dt: Optional[datetime] = None) -> float:
        """Calculates age of TLE epoch in days relative to current time."""
        now = now_dt or datetime.now(timezone.utc)
        epoch_dt = self.get_epoch_dt()
        if epoch_dt.tzinfo is None:
            epoch_dt = epoch_dt.replace(tzinfo=timezone.utc)
        delta = now - epoch_dt
        return delta.total_seconds() / 86400.0


@dataclass
class FetchLogRecord:
    """Provenance log record for a data acquisition run."""
    id: Optional[int]
    source_name: str
    source_url: str
    fetched_at_utc: str
    http_status: int
    byte_count: int
    record_count: int
    rejected_count: int
    content_hash: str
    duration_seconds: float
    status: str
    error_msg: Optional[str] = None
