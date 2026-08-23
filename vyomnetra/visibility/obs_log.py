"""Empirical Observation Log & Residual Engine.

Manages user observation logging in SQLite and computes empirical prediction residuals
(time residual delta_t = t_obs - t_pred, elevation residual delta_el = el_obs - el_pred).
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from vyomnetra.config import settings
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.visibility.obs_log")


@dataclass
class ObservationRecord:
    """Dataclass representing an empirical ground observation record."""
    id: Optional[int]
    norad_id: int
    sat_name: str
    site_name: str
    pred_tca_dt: datetime
    obs_tca_dt: datetime
    pred_max_elevation_deg: float
    obs_max_elevation_deg: float
    time_residual_sec: float
    elevation_residual_deg: float
    notes: str


class ObservationLogManager:
    """Manages empirical observation logs and prediction residuals in SQLite."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self._init_obs_table()

    def _init_obs_table(self):
        """Creates observation_logs table if not present."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS observation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                norad_id INTEGER NOT NULL,
                sat_name TEXT NOT NULL,
                site_name TEXT NOT NULL,
                pred_tca_utc TEXT NOT NULL,
                obs_tca_utc TEXT NOT NULL,
                pred_max_elevation_deg REAL NOT NULL,
                obs_max_elevation_deg REAL NOT NULL,
                time_residual_sec REAL NOT NULL,
                elevation_residual_deg REAL NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (norad_id) REFERENCES satellites(norad_id) ON DELETE CASCADE
            );
            """)

    def record_observation(
        self,
        norad_id: int,
        sat_name: str,
        site_name: str,
        pred_tca_dt: datetime,
        obs_tca_dt: datetime,
        pred_max_el_deg: float,
        obs_max_el_deg: float,
        notes: str = ""
    ) -> ObservationRecord:
        """Computes residuals and logs observation into SQLite."""
        if pred_tca_dt.tzinfo is None:
            pred_tca_dt = pred_tca_dt.replace(tzinfo=timezone.utc)
        if obs_tca_dt.tzinfo is None:
            obs_tca_dt = obs_tca_dt.replace(tzinfo=timezone.utc)

        time_residual_sec = (obs_tca_dt - pred_tca_dt).total_seconds()
        elevation_residual_deg = obs_max_el_deg - pred_max_el_deg

        now_str = datetime.now(timezone.utc).isoformat()

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO observation_logs (
                norad_id, sat_name, site_name, pred_tca_utc, obs_tca_utc,
                pred_max_elevation_deg, obs_max_elevation_deg,
                time_residual_sec, elevation_residual_deg, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                norad_id,
                sat_name,
                site_name,
                pred_tca_dt.isoformat(),
                obs_tca_dt.isoformat(),
                pred_max_el_deg,
                obs_max_el_deg,
                time_residual_sec,
                elevation_residual_deg,
                notes,
                now_str
            ))
            obs_id = cursor.lastrowid

        rec = ObservationRecord(
            id=obs_id,
            norad_id=norad_id,
            sat_name=sat_name,
            site_name=site_name,
            pred_tca_dt=pred_tca_dt,
            obs_tca_dt=obs_tca_dt,
            pred_max_elevation_deg=pred_max_el_deg,
            obs_max_elevation_deg=obs_max_el_deg,
            time_residual_sec=time_residual_sec,
            elevation_residual_deg=elevation_residual_deg,
            notes=notes
        )
        logger.info(
            f"Recorded observation #{obs_id} for NORAD {norad_id} over {site_name}. "
            f"Residuals: dt = {time_residual_sec:+.2f}s, dEl = {elevation_residual_deg:+.2f}°"
        )
        return rec

    def get_observations_for_satellite(self, norad_id: int) -> List[ObservationRecord]:
        """Retrieves observation records for a given satellite."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT id, norad_id, sat_name, site_name, pred_tca_utc, obs_tca_utc,
                   pred_max_elevation_deg, obs_max_elevation_deg,
                   time_residual_sec, elevation_residual_deg, notes
            FROM observation_logs WHERE norad_id = ? ORDER BY id DESC;
            """, (norad_id,))
            rows = cursor.fetchall()

        records = []
        for r in rows:
            records.append(ObservationRecord(
                id=r[0],
                norad_id=r[1],
                sat_name=r[2],
                site_name=r[3],
                pred_tca_dt=datetime.fromisoformat(r[4]),
                obs_tca_dt=datetime.fromisoformat(r[5]),
                pred_max_elevation_deg=r[6],
                obs_max_elevation_deg=r[7],
                time_residual_sec=r[8],
                elevation_residual_deg=r[9],
                notes=r[10]
            ))
        return records
