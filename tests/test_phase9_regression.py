"""Phase 9 System Regression, Backup & Audit Verification Tests.

Validates zero-downtime database online backup, integrity hash verification,
security audit trail, and end-to-end multi-module pipeline execution.
"""

from pathlib import Path
from datetime import datetime, timezone
import pytest

from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.intelligence.security import SecurityPipelineManager
from vyomnetra.conjunction.screening import ConjunctionScreeningEngine, ConjunctionAlert
from vyomnetra.sdk import SSAPlatform


def test_database_online_backup():
    """Validates online database backup generation and non-zero byte size."""
    db = DatabaseManager()
    backup_file = db.backup_database()

    assert backup_file.exists()
    assert backup_file.stat().st_size > 0
    # Clean up temporary backup
    backup_file.unlink(missing_ok=True)


def test_database_zero_orphan_records():
    """Enforces zero orphan satellite records in SQLite database."""
    db = DatabaseManager()
    orphan_count = db.check_orphan_records()
    assert orphan_count == 0


def test_security_audit_logging_and_tampering():
    """Validates security audit log signatures and tampering detection."""
    sec = SecurityPipelineManager()
    data = {"norad_id": 25544, "event": "MANEUVER_DETECTED", "timestamp": "2024-01-01T12:00:00Z"}
    
    sig = sec.generate_hmac_signature(data)
    assert len(sig) == 64
    assert sec.verify_hmac_signature(data, sig) is True

    # Modified data must fail signature verification
    tampered_data = {"norad_id": 25544, "event": "NORMAL", "timestamp": "2024-01-01T12:00:00Z"}
    assert sec.verify_hmac_signature(tampered_data, sig) is False


def test_end_to_end_sdk_full_pipeline():
    """Validates complete SSAPlatform pipeline through SDK."""
    platform = SSAPlatform()
    
    sats = platform.get_satellites()
    assert isinstance(sats, list)

    alerts = platform.screen_conjunctions(duration_hours=12.0)
    assert isinstance(alerts, list)

    passes = platform.predict_passes(site_name="hazaribagh", duration_hours=12.0)
    assert isinstance(passes, list)

    sw = platform.get_space_weather()
    assert sw.f10_7_index > 0.0

    query_res = platform.query("Show satellite lifetime decay estimates")
    assert "decay" in query_res["cot_plan_text"].lower() or "decay" in query_res["final_answer"].lower()
