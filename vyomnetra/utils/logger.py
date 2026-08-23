"""Structured audit logging system for VYOMNETRA.

Every data fetch, parse, and propagation operation logs with provenance details
(source URL, timestamp, record count, content hash, and status).
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from vyomnetra.config import settings


class AuditLogger:
    """Handles structured JSONL provenance logging and standard console output."""

    def __init__(self, name: str = "vyomnetra"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Ensure log directory exists
        self.log_dir = settings.get_logs_dir()
        self.json_log_path = self.log_dir / "audit_provenance.jsonl"
        self.app_log_path = self.log_dir / "app.log"
        
        # Prevent duplicate handlers if re-initialized
        if not self.logger.handlers:
            # Console Handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

            # Standard File Handler
            file_handler = logging.FileHandler(self.app_log_path, encoding="utf-8")
            file_handler.setFormatter(console_formatter)
            self.logger.addHandler(file_handler)

    def log_provenance(
        self,
        source_name: str,
        source_url: str,
        record_count: int,
        content_hash: str,
        status: str,
        fetch_time_utc: Optional[str] = None,
        error_msg: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Logs a data acquisition or processing step with full audit provenance.
        
        Appends a structured JSON line to `audit_provenance.jsonl`.
        """
        timestamp = fetch_time_utc or datetime.now(timezone.utc).isoformat()
        
        entry = {
            "timestamp_utc": timestamp,
            "source_name": source_name,
            "source_url": source_url,
            "record_count": record_count,
            "content_hash": content_hash,
            "status": status,
            "error": error_msg,
            "metadata": extra_metadata or {}
        }
        
        log_dir = settings.get_logs_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        json_log_path = log_dir / "audit_provenance.jsonl"
        
        # Write JSONL record
        with open(json_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            
        log_msg = (
            f"PROVENANCE [{status}] Source: '{source_name}' ({source_url}) | "
            f"Records: {record_count} | Hash: {content_hash[:8]}..."
        )
        if error_msg:
            log_msg += f" | Error: {error_msg}"
            self.logger.error(log_msg)
        else:
            self.logger.info(log_msg)
            
        return entry


_default_audit_logger = AuditLogger()


def get_logger(name: str = "vyomnetra") -> logging.Logger:
    """Returns a standard Python logger."""
    return logging.getLogger(name)


def log_data_fetch(
    source_name: str,
    source_url: str,
    record_count: int,
    content_hash: str,
    status: str = "SUCCESS",
    fetch_time_utc: Optional[str] = None,
    error_msg: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Helper to record a data fetch provenance event."""
    return _default_audit_logger.log_provenance(
        source_name=source_name,
        source_url=source_url,
        record_count=record_count,
        content_hash=content_hash,
        status=status,
        fetch_time_utc=fetch_time_utc,
        error_msg=error_msg,
        extra_metadata=extra_metadata
    )
