"""Data Health Monitor & Staleness Accounting Module."""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.ingest.models import SatelliteRecord


def get_data_health_summary(db_manager: Optional[DatabaseManager] = None) -> List[Dict[str, Any]]:
    """Returns data health summary for each ingested source.
    
    Includes source name, URL, last fetch timestamp, staleness age in hours,
    http status, byte count, ingested records count, and rejected records count.
    """
    db = db_manager or DatabaseManager()
    fetch_logs = db.get_latest_fetch_logs()
    
    # Group by source_name to find latest fetch
    sources: Dict[str, Any] = {}
    now_dt = datetime.now(timezone.utc)
    
    for log in fetch_logs:
        if log.source_name not in sources:
            # Calculate staleness age
            try:
                clean_ts = log.fetched_at_utc.replace("Z", "+00:00")
                fetched_dt = datetime.fromisoformat(clean_ts)
                if fetched_dt.tzinfo is None:
                    fetched_dt = fetched_dt.replace(tzinfo=timezone.utc)
                age_hours = (now_dt - fetched_dt).total_seconds() / 3600.0
            except Exception:
                age_hours = 0.0

            sources[log.source_name] = {
                "source_name": log.source_name,
                "source_url": log.source_url,
                "last_fetch_utc": log.fetched_at_utc,
                "staleness_hours": round(age_hours, 2),
                "http_status": log.http_status,
                "byte_count": log.byte_count,
                "record_count": log.record_count,
                "rejected_count": log.rejected_count,
                "content_hash": log.content_hash,
                "status": log.status
            }

    return list(sources.values())


def compute_epoch_age_histogram(db_manager: Optional[DatabaseManager] = None) -> Dict[str, Any]:
    """Computes distribution histogram of TLE epoch age in days over the catalogue."""
    db = db_manager or DatabaseManager()
    satellites = db.get_all_satellites()
    
    if not satellites:
        return {
            "total_satellites": 0,
            "bins": {"0-1 days": 0, "1-3 days": 0, "3-7 days": 0, "7-14 days": 0, "14-30 days": 0, ">30 days": 0},
            "mean_age_days": 0.0,
            "max_age_days": 0.0,
            "min_age_days": 0.0
        }

    now_dt = datetime.now(timezone.utc)
    ages = [sat.get_epoch_age_days(now_dt) for sat in satellites]
    
    bins = {
        "0-1 days": 0,
        "1-3 days": 0,
        "3-7 days": 0,
        "7-14 days": 0,
        "14-30 days": 0,
        ">30 days": 0
    }
    
    for age in ages:
        if age <= 1.0:
            bins["0-1 days"] += 1
        elif age <= 3.0:
            bins["1-3 days"] += 1
        elif age <= 7.0:
            bins["3-7 days"] += 1
        elif age <= 14.0:
            bins["7-14 days"] += 1
        elif age <= 30.0:
            bins["14-30 days"] += 1
        else:
            bins[">30 days"] += 1

    return {
        "total_satellites": len(satellites),
        "bins": bins,
        "mean_age_days": round(sum(ages) / len(ages), 2) if ages else 0.0,
        "max_age_days": round(max(ages), 2) if ages else 0.0,
        "min_age_days": round(min(ages), 2) if ages else 0.0
    }
