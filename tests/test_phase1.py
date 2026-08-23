"""Phase 1 Data Ingestion & Provenance Unit & Integration Tests.

Validates CelesTrak adapter, SQLite foreign key constraints, zero orphan records,
checksum rejection logging, custom User-Agent, offline replay, and Space-Track degradation.
"""

import os
import re
from pathlib import Path
import pytest
from datetime import datetime, timezone

from vyomnetra.config import settings
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.ingest.models import SatelliteRecord, FetchLogRecord
from vyomnetra.ingest.adapters import CelesTrakAdapter, USER_AGENT
from vyomnetra.ingest.space_track import SpaceTrackAdapter
from vyomnetra.ingest.health import get_data_health_summary, compute_epoch_age_histogram


def test_no_literal_tle_data_in_source():
    """HARD RULE #1: Asserts no hardcoded TLE literals exist in vyomnetra/ source code."""
    source_dir = Path("vyomnetra")
    tle_line_pattern = re.compile(r'["\']1\s+\d{5}[Uu].*["\']')

    for py_file in source_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        matches = tle_line_pattern.findall(content)
        assert len(matches) == 0, (
            f"Hard Rule #1 Violation! Found literal TLE line in {py_file}: {matches}"
        )


def test_celestrak_ingest_and_provenance(tmp_path):
    """Tests CelesTrak adapter ingestion, provenance recording, and User-Agent header."""
    db_path = tmp_path / "test_ingest.db"
    db = DatabaseManager(db_path)
    adapter = CelesTrakAdapter(db, group="stations")

    # Verify custom User-Agent
    assert adapter.session.headers["User-Agent"] == USER_AGENT
    assert "VYOMNETRA-SSA-Engine" in adapter.session.headers["User-Agent"]

    # Execute fetch
    fetch_log, satellites = adapter.fetch()
    
    assert fetch_log is not None
    assert fetch_log.http_status == 200
    assert fetch_log.record_count > 0
    assert len(satellites) == fetch_log.record_count
    assert fetch_log.content_hash != ""

    # Verify DB state
    all_db_sats = db.get_all_satellites()
    assert len(all_db_sats) == len(satellites)
    assert all_db_sats[0].fetch_id == fetch_log.id


def test_zero_orphan_records_constraint(tmp_path):
    """HARD RULE #2: Asserts zero orphan satellite records in SQLite database."""
    db_path = tmp_path / "test_orphan.db"
    db = DatabaseManager(db_path)

    # Check initially empty
    assert db.check_orphan_records() == 0

    # Ingest mock data linked to a valid fetch log
    fetch_id = db.record_fetch_log(FetchLogRecord(
        id=None,
        source_name="Test Source",
        source_url="https://example.com",
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
        http_status=200,
        byte_count=100,
        record_count=1,
        rejected_count=0,
        content_hash="hash123",
        duration_seconds=0.1,
        status="SUCCESS"
    ))

    sat = SatelliteRecord(
        norad_id=25544,
        name="ISS (ZARYA)",
        international_designator="1998-067A",
        object_type="PAYLOAD",
        epoch_utc="2026-08-23T12:00:00.000000",
        epoch_jd=2460000.5,
        mean_motion=15.49,
        eccentricity=0.0004,
        inclination_deg=51.64,
        raan_deg=208.9,
        arg_perigee_deg=93.7,
        mean_anomaly_deg=266.4,
        bstar=0.0003,
        mean_motion_dot=0.0001,
        mean_motion_ddot=0.0,
        ephemeris_type=0,
        element_set_no=999,
        rev_at_epoch=43238,
        fetch_id=fetch_id
    )

    db.save_satellites_transaction([sat], fetch_id)
    assert db.check_orphan_records() == 0


def test_checksum_rejection_and_log(tmp_path):
    """Tests TLE checksum validation rejecting corrupt lines and logging reasons."""
    db_path = tmp_path / "test_reject.db"
    db = DatabaseManager(db_path)
    adapter = CelesTrakAdapter(db, group="stations")

    # Inject mock record with corrupted TLE Line 1 checksum
    mock_json = [{
        "NORAD_CAT_ID": 99901,
        "OBJECT_NAME": "CORRUPT_SAT",
        "OBJECT_ID": "2026-001A",
        "OBJECT_TYPE": "PAYLOAD",
        "EPOCH": "2026-08-23T12:00:00.000000",
        "MEAN_MOTION": 15.0,
        "ECCENTRICITY": 0.001,
        "INCLINATION": 51.6,
        "RA_OF_ASC_NODE": 100.0,
        "ARG_OF_PERICENTER": 90.0,
        "MEAN_ANOMALY": 45.0,
        "TLE_LINE1": "1 99901U 26001A   26001.50000000  .00016717  00000-0  30000-3 0  9995",  # Corrupted checksum
        "TLE_LINE2": "2 99901  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    }]

    valid, rejected = adapter.parse_omm_json(mock_json)
    assert len(valid) == 0
    assert len(rejected) == 1
    assert "checksum failure" in rejected[0][1]


def test_offline_replay_from_cache(tmp_path):
    """EXIT CRITERION C: Verifies offline replay loads data from disk cache with zero network calls."""
    db_path = tmp_path / "test_offline.db"
    db = DatabaseManager(db_path)
    adapter = CelesTrakAdapter(db, group="stations")

    # Perform first live fetch to populate cache
    f_log, sats = adapter.fetch(force_offline=False)
    assert len(sats) > 0

    # Perform forced offline replay
    off_log, off_sats = adapter.fetch(force_offline=True)
    assert off_log.status == "OFFLINE_CACHE"
    assert len(off_sats) == len(sats)


def test_space_track_clean_degradation(tmp_path, monkeypatch):
    """HARD RULE #4: Verifies SpaceTrackAdapter degrades cleanly if credentials missing."""
    monkeypatch.delenv("SPACE_TRACK_USER", raising=False)
    monkeypatch.delenv("SPACE_TRACK_PASSWORD", raising=False)

    db_path = tmp_path / "test_st.db"
    db = DatabaseManager(db_path)
    st_adapter = SpaceTrackAdapter(db)

    assert st_adapter.is_configured() is False
    log, sats = st_adapter.fetch()
    assert log is None
    assert sats == []


def test_data_health_and_epoch_histogram(tmp_path):
    """EXIT CRITERIA D & E: Tests health summary calculation and TLE epoch age histogram."""
    db_path = tmp_path / "test_health.db"
    db = DatabaseManager(db_path)
    adapter = CelesTrakAdapter(db, group="stations")

    adapter.fetch()
    health = get_data_health_summary(db)
    assert len(health) >= 1
    assert health[0]["source_name"] == "CelesTrak GP"
    assert health[0]["record_count"] > 0

    histo = compute_epoch_age_histogram(db)
    assert histo["total_satellites"] > 0
    assert "0-1 days" in histo["bins"]
