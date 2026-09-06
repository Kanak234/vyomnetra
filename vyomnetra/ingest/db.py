"""SQLite Database Manager for VYOMNETRA Catalogue and Provenance Data.

Enforces Foreign Key constraints (PRAGMA foreign_keys = ON) so every satellite
record is linked to a traceable fetch log entry. Zero orphan records allowed.
Optimized for concurrent reads with WAL mode and indexing.
"""

import sqlite3
import shutil
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone

from vyomnetra.config import settings
from vyomnetra.ingest.models import SatelliteRecord, FetchLogRecord
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.ingest.db")


class DatabaseManager:
    """Manages SQLite connection, schema creation, WAL pragma configuration, indices, and backups."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.get_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a new SQLite connection with Foreign Keys enabled, auto-vacuum, and WAL mode configured."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA auto_vacuum = INCREMENTAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes database schema tables and indices."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Fetch Logs Table (Provenance)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fetch_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    fetched_at_utc TEXT NOT NULL,
                    http_status INTEGER NOT NULL,
                    byte_count INTEGER NOT NULL,
                    record_count INTEGER NOT NULL,
                    rejected_count INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    status TEXT NOT NULL,
                    error_msg TEXT
                );
            """)

            # 2. Satellites Table (Normalized Catalogue)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS satellites (
                    norad_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    international_designator TEXT,
                    object_type TEXT,
                    epoch_utc TEXT NOT NULL,
                    epoch_jd REAL NOT NULL,
                    mean_motion REAL NOT NULL,
                    eccentricity REAL NOT NULL,
                    inclination_deg REAL NOT NULL,
                    raan_deg REAL NOT NULL,
                    arg_perigee_deg REAL NOT NULL,
                    mean_anomaly_deg REAL NOT NULL,
                    bstar REAL NOT NULL,
                    mean_motion_dot REAL NOT NULL,
                    mean_motion_ddot REAL NOT NULL,
                    ephemeris_type INTEGER NOT NULL,
                    element_set_no INTEGER NOT NULL,
                    rev_at_epoch INTEGER NOT NULL,
                    raw_tle_line1 TEXT,
                    raw_tle_line2 TEXT,
                    fetch_id INTEGER NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    FOREIGN KEY (fetch_id) REFERENCES fetch_logs (id) ON DELETE CASCADE
                );
            """)

            # 3. Rejected Records Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rejected_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fetch_id INTEGER NOT NULL,
                    raw_line TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    rejected_at_utc TEXT NOT NULL,
                    FOREIGN KEY (fetch_id) REFERENCES fetch_logs (id) ON DELETE CASCADE
                );
            """)

            # 4. Conjunction Alerts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conjunction_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    primary_norad INTEGER NOT NULL,
                    primary_name TEXT NOT NULL,
                    secondary_norad INTEGER NOT NULL,
                    secondary_name TEXT NOT NULL,
                    tca_utc TEXT NOT NULL,
                    miss_distance_km REAL NOT NULL,
                    radial_distance_km REAL NOT NULL,
                    in_track_distance_km REAL NOT NULL,
                    cross_track_distance_km REAL NOT NULL,
                    relative_velocity_kms REAL NOT NULL,
                    calculated_pc REAL NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
            """)

            # 5. Health Snapshots Table (Hourly Health & Uptime Tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS health_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_at_utc TEXT NOT NULL,
                    uptime_seconds REAL NOT NULL,
                    total_satellites INTEGER NOT NULL,
                    active_alerts_count INTEGER NOT NULL,
                    data_freshness_hours REAL NOT NULL,
                    status TEXT NOT NULL
                );
            """)

            # Indices for fast spatial and temporal queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_satellites_epoch ON satellites(epoch_jd);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_satellites_inc ON satellites(inclination_deg);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conj_severity_tca ON conjunction_alerts(severity, tca_utc);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fetch_logs_time ON fetch_logs(fetched_at_utc);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_health_time ON health_snapshots(snapshot_at_utc);")


            conn.commit()

    def record_fetch_log(self, fetch_record: FetchLogRecord) -> int:
        """Inserts a fetch log record and returns its generated fetch_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fetch_logs (
                    source_name, source_url, fetched_at_utc, http_status,
                    byte_count, record_count, rejected_count, content_hash,
                    duration_seconds, status, error_msg
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                fetch_record.source_name,
                fetch_record.source_url,
                fetch_record.fetched_at_utc,
                fetch_record.http_status,
                fetch_record.byte_count,
                fetch_record.record_count,
                fetch_record.rejected_count,
                fetch_record.content_hash,
                fetch_record.duration_seconds,
                fetch_record.status,
                fetch_record.error_msg
            ))
            conn.commit()
            fetch_id = cursor.lastrowid
            logger.info(f"Recorded fetch log ID {fetch_id} for source '{fetch_record.source_name}' ({fetch_record.record_count} records).")
            return fetch_id

    def save_satellites_transaction(self, satellites: List[SatelliteRecord], fetch_id: int):
        """Saves or updates satellite records in an atomic transaction linked to fetch_id."""
        if not satellites:
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            rows = []
            for s in satellites:
                rows.append((
                    s.norad_id, s.name, s.international_designator, s.object_type,
                    s.epoch_utc, s.epoch_jd, s.mean_motion, s.eccentricity,
                    s.inclination_deg, s.raan_deg, s.arg_perigee_deg, s.mean_anomaly_deg,
                    s.bstar, s.mean_motion_dot, s.mean_motion_ddot, s.ephemeris_type,
                    s.element_set_no, s.rev_at_epoch, s.raw_tle_line1, s.raw_tle_line2,
                    fetch_id, s.updated_at_utc
                ))

            cursor.executemany("""
                INSERT OR REPLACE INTO satellites (
                    norad_id, name, international_designator, object_type,
                    epoch_utc, epoch_jd, mean_motion, eccentricity,
                    inclination_deg, raan_deg, arg_perigee_deg, mean_anomaly_deg,
                    bstar, mean_motion_dot, mean_motion_ddot, ephemeris_type,
                    element_set_no, rev_at_epoch, raw_tle_line1, raw_tle_line2,
                    fetch_id, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, rows)
            conn.commit()
            logger.info(f"Saved {len(satellites)} satellite records under fetch_id {fetch_id}.")

    def save_rejected_records(self, rejected: List[Tuple[str, str]], fetch_id: int):
        """Saves rejected raw TLE lines and reasons linked to fetch_id."""
        if not rejected:
            return

        now_utc = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            rows = [(fetch_id, line, reason, now_utc) for line, reason in rejected]
            cursor.executemany("""
                INSERT INTO rejected_records (fetch_id, raw_line, reason, rejected_at_utc)
                VALUES (?, ?, ?, ?);
            """, rows)
            conn.commit()

    def save_conjunction_alerts(self, alerts: List[Any]):
        """Saves conjunction alert records into SQLite."""
        if not alerts:
            return

        now_utc = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            rows = []
            for a in alerts:
                rows.append((
                    a.primary_norad, a.primary_name, a.secondary_norad, a.secondary_name,
                    a.tca_utc.isoformat() if isinstance(a.tca_utc, datetime) else str(a.tca_utc),
                    a.miss_distance_km, a.radial_distance_km, a.in_track_distance_km,
                    a.cross_track_distance_km, a.relative_velocity_kms, a.calculated_pc,
                    a.severity, a.status, now_utc
                ))

            cursor.executemany("""
                INSERT INTO conjunction_alerts (
                    primary_norad, primary_name, secondary_norad, secondary_name,
                    tca_utc, miss_distance_km, radial_distance_km, in_track_distance_km,
                    cross_track_distance_km, relative_velocity_kms, calculated_pc,
                    severity, status, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, rows)
            conn.commit()

    def check_orphan_records(self) -> int:
        """Queries for any satellite records lacking a valid parent fetch_logs entry."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM satellites
                WHERE fetch_id IS NULL OR fetch_id NOT IN (SELECT id FROM fetch_logs);
            """)
            count = cursor.fetchone()[0]
            return count

    def get_all_satellites(self) -> List[SatelliteRecord]:
        """Loads all satellite records from database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM satellites;")
            rows = cursor.fetchall()
            
            satellites = []
            for r in rows:
                satellites.append(SatelliteRecord(
                    norad_id=r["norad_id"],
                    name=r["name"],
                    international_designator=r["international_designator"],
                    object_type=r["object_type"],
                    epoch_utc=r["epoch_utc"],
                    epoch_jd=r["epoch_jd"],
                    mean_motion=r["mean_motion"],
                    eccentricity=r["eccentricity"],
                    inclination_deg=r["inclination_deg"],
                    raan_deg=r["raan_deg"],
                    arg_perigee_deg=r["arg_perigee_deg"],
                    mean_anomaly_deg=r["mean_anomaly_deg"],
                    bstar=r["bstar"],
                    mean_motion_dot=r["mean_motion_dot"],
                    mean_motion_ddot=r["mean_motion_ddot"],
                    ephemeris_type=r["ephemeris_type"],
                    element_set_no=r["element_set_no"],
                    rev_at_epoch=r["rev_at_epoch"],
                    raw_tle_line1=r["raw_tle_line1"],
                    raw_tle_line2=r["raw_tle_line2"],
                    fetch_id=r["fetch_id"],
                    updated_at_utc=r["updated_at_utc"]
                ))
            return satellites

    def get_satellite_history(self, norad_id: int, limit_days: int = 30) -> List[SatelliteRecord]:
        """Loads historical satellite records for a given NORAD ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM satellites WHERE norad_id = ? ORDER BY epoch_utc ASC;", (norad_id,))
            rows = cursor.fetchall()
            satellites = []
            for r in rows:
                satellites.append(SatelliteRecord(
                    norad_id=r["norad_id"],
                    name=r["name"],
                    international_designator=r["international_designator"],
                    object_type=r["object_type"],
                    epoch_utc=r["epoch_utc"],
                    epoch_jd=r["epoch_jd"],
                    mean_motion=r["mean_motion"],
                    eccentricity=r["eccentricity"],
                    inclination_deg=r["inclination_deg"],
                    raan_deg=r["raan_deg"],
                    arg_perigee_deg=r["arg_perigee_deg"],
                    mean_anomaly_deg=r["mean_anomaly_deg"],
                    bstar=r["bstar"],
                    mean_motion_dot=r["mean_motion_dot"],
                    mean_motion_ddot=r["mean_motion_ddot"],
                    ephemeris_type=r["ephemeris_type"],
                    element_set_no=r["element_set_no"],
                    rev_at_epoch=r["rev_at_epoch"],
                    raw_tle_line1=r["raw_tle_line1"],
                    raw_tle_line2=r["raw_tle_line2"],
                    fetch_id=r["fetch_id"],
                    updated_at_utc=r["updated_at_utc"]
                ))
            return satellites

    def get_latest_fetch_logs(self) -> List[FetchLogRecord]:
        """Loads all fetch log entries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fetch_logs ORDER BY id DESC;")
            rows = cursor.fetchall()
            
            logs = []
            for r in rows:
                logs.append(FetchLogRecord(
                    id=r["id"],
                    source_name=r["source_name"],
                    source_url=r["source_url"],
                    fetched_at_utc=r["fetched_at_utc"],
                    http_status=r["http_status"],
                    byte_count=r["byte_count"],
                    record_count=r["record_count"],
                    rejected_count=r["rejected_count"],
                    content_hash=r["content_hash"],
                    duration_seconds=r["duration_seconds"],
                    status=r["status"],
                    error_msg=r["error_msg"]
                ))
            return logs

    def backup_database(self, backup_dir: Optional[Path] = None) -> Path:
        """Executes zero-downtime online database backup."""
        b_dir = backup_dir or (self.db_path.parent / "backups")
        b_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest_path = b_dir / f"vyomnetra_backup_{timestamp}.db"
        
        with self.get_connection() as src_conn:
            with sqlite3.connect(dest_path) as dst_conn:
                src_conn.backup(dst_conn)
                
        logger.info(f"Database online backup successfully created: {dest_path}")
        return dest_path
