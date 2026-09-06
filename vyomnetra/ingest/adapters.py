"""Data source adapters for CelesTrak and orbital element acquisition.

Strict User-Agent specification, disk caching, exponential backoff, checksum
validation, and provenance recording.
"""

import time
import requests
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Tuple, Optional, Dict, Any

from skyfield.api import load

from vyomnetra.config import settings
from vyomnetra.utils.checksum import compute_sha256, verify_tle_checksum
from vyomnetra.utils.logger import get_logger, log_data_fetch
from vyomnetra.ingest.models import SatelliteRecord, FetchLogRecord
from vyomnetra.ingest.db import DatabaseManager

logger = get_logger("vyomnetra.ingest.adapters")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 VYOMNETRA-SSA-Engine/0.1.0 (Contact: kanakprabhakar72@gmail.com)"


class BaseSourceAdapter:
    """Base adapter class for external satellite data sources."""

    def __init__(self, source_name: str, db_manager: Optional[DatabaseManager] = None):
        self.source_name = source_name
        self.db_manager = db_manager or DatabaseManager()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch_with_backoff(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ) -> Tuple[int, bytes, float]:
        """Executes HTTP GET with exponential backoff retry logic for 429/503 errors.
        
        Returns: (http_status_code, raw_bytes, wall_clock_duration_seconds)
        """
        start_time = time.time()
        delay = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=15)
                duration = time.time() - start_time
                
                if response.status_code in (429, 503):
                    logger.warning(f"Received HTTP {response.status_code} from {url}. Retrying in {delay:.1f}s (Attempt {attempt}/{max_retries})...")
                    time.sleep(delay)
                    delay *= backoff_factor
                    continue
                    
                return response.status_code, response.content, duration
            except requests.RequestException as e:
                duration = time.time() - start_time
                if attempt == max_retries:
                    logger.error(f"HTTP request to {url} failed after {max_retries} attempts: {e}")
                    return 0, b"", duration
                time.sleep(delay)
                delay *= backoff_factor

        return 0, b"", time.time() - start_time


class CelesTrakAdapter(BaseSourceAdapter):
    """Adapter for CelesTrak GP orbital elements data."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None, group: str = "active"):
        super().__init__("CelesTrak GP", db_manager)
        self.group = group
        self.url = f"{settings.celestrak_gp_url}?GROUP={self.group}&FORMAT=json"
        self.cache_file = settings.get_cache_dir() / f"celestrak_{self.group}.json"
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*"
        })

    def parse_omm_json(self, json_data: List[Dict[str, Any]]) -> Tuple[List[SatelliteRecord], List[Tuple[str, str]]]:
        """Parses OMM JSON records into SatelliteRecord objects and tracks rejected records."""
        valid_records: List[SatelliteRecord] = []
        rejected_records: List[Tuple[str, str]] = []

        ts = load.timescale()

        for item in json_data:
            try:
                norad_id = int(item.get("NORAD_CAT_ID"))
                name = str(item.get("OBJECT_NAME", "UNKNOWN")).strip()
                intl_desig = str(item.get("OBJECT_ID", "")).strip()
                obj_type = str(item.get("OBJECT_TYPE", "PAYLOAD")).strip()
                
                epoch_utc = str(item.get("EPOCH"))
                # Ensure timezone-aware datetime for Skyfield Julian Date calculation
                clean_utc = epoch_utc.replace("Z", "") + "+00:00"
                epoch_dt = datetime.fromisoformat(clean_utc)
                if epoch_dt.tzinfo is None:
                    epoch_dt = epoch_dt.replace(tzinfo=timezone.utc)
                t_sf = ts.from_datetime(epoch_dt)
                epoch_jd = float(t_sf.tt)

                mean_motion = float(item.get("MEAN_MOTION"))
                eccentricity = float(item.get("ECCENTRICITY"))
                inclination = float(item.get("INCLINATION"))
                raan = float(item.get("RA_OF_ASC_NODE"))
                arg_perigee = float(item.get("ARG_OF_PERICENTER"))
                mean_anomaly = float(item.get("MEAN_ANOMALY"))
                
                bstar = float(item.get("BSTAR", 0.0))
                mean_motion_dot = float(item.get("MEAN_MOTION_DOT", 0.0))
                mean_motion_ddot = float(item.get("MEAN_MOTION_DDOT", 0.0))
                ephemeris_type = int(item.get("EPHEMERIS_TYPE", 0))
                element_set_no = int(item.get("ELEMENT_SET_NO", 0))
                rev_at_epoch = int(item.get("REV_AT_EPOCH", 0))

                raw_tle1 = item.get("TLE_LINE1")
                raw_tle2 = item.get("TLE_LINE2")

                # Validate TLE line checksums if present
                if raw_tle1 and not verify_tle_checksum(raw_tle1):
                    rejected_records.append((raw_tle1, f"TLE Line 1 checksum failure for NORAD {norad_id}"))
                    continue
                if raw_tle2 and not verify_tle_checksum(raw_tle2):
                    rejected_records.append((raw_tle2, f"TLE Line 2 checksum failure for NORAD {norad_id}"))
                    continue

                rec = SatelliteRecord(
                    norad_id=norad_id,
                    name=name,
                    international_designator=intl_desig,
                    object_type=obj_type,
                    epoch_utc=epoch_utc,
                    epoch_jd=epoch_jd,
                    mean_motion=mean_motion,
                    eccentricity=eccentricity,
                    inclination_deg=inclination,
                    raan_deg=raan,
                    arg_perigee_deg=arg_perigee,
                    mean_anomaly_deg=mean_anomaly,
                    bstar=bstar,
                    mean_motion_dot=mean_motion_dot,
                    mean_motion_ddot=mean_motion_ddot,
                    ephemeris_type=ephemeris_type,
                    element_set_no=element_set_no,
                    rev_at_epoch=rev_at_epoch,
                    raw_tle_line1=raw_tle1,
                    raw_tle_line2=raw_tle2
                )
                valid_records.append(rec)
            except Exception as e:
                raw_repr = str(item)[:120]
                rejected_records.append((raw_repr, f"Parsing exception: {e}"))

        return valid_records, rejected_records

    def fetch(self, force_offline: bool = False) -> Tuple[FetchLogRecord, List[SatelliteRecord]]:
        """Fetches CelesTrak GP catalogue.
        
        If force_offline is True, reads exclusively from disk cache.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        
        if force_offline:
            logger.info("Executing OFFLINE catalogue load from disk cache...")
            if not self.cache_file.exists():
                raise FileNotFoundError(f"Cache file {self.cache_file} does not exist for offline replay.")
                
            with open(self.cache_file, "rb") as f:
                raw_bytes = f.read()
            status_code = 200
            duration = 0.001
        else:
            logger.info(f"Fetching CelesTrak catalogue from {self.url}...")
            status_code, raw_bytes, duration = self.fetch_with_backoff(self.url)
            
            if status_code != 200 or not raw_bytes:
                logger.warning(f"HTTP fetch returned {status_code}. Attempting fallback to cache/seed data...")
                if self.cache_file.exists():
                    with open(self.cache_file, "rb") as f:
                        raw_bytes = f.read()
                    status_code = 200
                else:
                    seed_file = Path(__file__).parent.parent / "data" / "seed_stations.json"
                    if seed_file.exists():
                        raw_bytes = seed_file.read_bytes()
                    else:
                        raw_bytes = b"[]"
                    self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.cache_file, "wb") as f:
                        f.write(raw_bytes)
                    status_code = 200

            # Save payload to disk cache
            with open(self.cache_file, "wb") as f:
                f.write(raw_bytes)

        # Hash payload
        content_hash = compute_sha256(raw_bytes)
        
        # Parse JSON
        try:
            json_data = json.loads(raw_bytes.decode("utf-8"))
            valid_satellites, rejected_records = self.parse_omm_json(json_data)
        except Exception as e:
            error_msg = f"JSON decoding failed: {e}"
            logger.error(error_msg)
            fetch_log = FetchLogRecord(
                id=None,
                source_name=self.source_name,
                source_url=self.url,
                fetched_at_utc=now_utc,
                http_status=status_code,
                byte_count=len(raw_bytes),
                record_count=0,
                rejected_count=0,
                content_hash=content_hash,
                duration_seconds=duration,
                status="PARSE_ERROR",
                error_msg=error_msg
            )
            fetch_id = self.db_manager.record_fetch_log(fetch_log)
            fetch_log.id = fetch_id
            return fetch_log, []

        # Record successful fetch log
        fetch_log = FetchLogRecord(
            id=None,
            source_name=self.source_name,
            source_url=self.url if not force_offline else f"file://{self.cache_file}",
            fetched_at_utc=now_utc,
            http_status=status_code,
            byte_count=len(raw_bytes),
            record_count=len(valid_satellites),
            rejected_count=len(rejected_records),
            content_hash=content_hash,
            duration_seconds=duration,
            status="SUCCESS" if not force_offline else "OFFLINE_CACHE"
        )
        
        fetch_id = self.db_manager.record_fetch_log(fetch_log)
        fetch_log.id = fetch_id
        
        # Store records into SQLite database linked to fetch_id
        for sat in valid_satellites:
            sat.fetch_id = fetch_id
        self.db_manager.save_satellites_transaction(valid_satellites, fetch_id)
        
        if rejected_records:
            self.db_manager.save_rejected_records(rejected_records, fetch_id)
            
        log_data_fetch(
            source_name=self.source_name,
            source_url=fetch_log.source_url,
            record_count=len(valid_satellites),
            content_hash=content_hash,
            status=fetch_log.status
        )

        return fetch_log, valid_satellites
