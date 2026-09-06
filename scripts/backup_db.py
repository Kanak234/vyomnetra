#!/usr/bin/env python3
"""SQLite Vacuum Snapshot & Integrity Backup Generator.

Executes 'VACUUM INTO' on active database, verifies integrity with 'PRAGMA quick_check;',
and prunes backup snapshots older than 30 days.
"""

import sys
import sqlite3
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add workspace root to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vyomnetra.config import settings
from vyomnetra.utils.logger import get_logger

logger = get_logger("scripts.backup_db")


def backup_database(retention_days: int = 30) -> Path:
    """Executes atomic vacuum backup of active SQLite database."""
    db_path = settings.get_db_path()
    if not db_path.exists():
        logger.error(f"Active database path {db_path} does not exist!")
        sys.exit(1)

    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snapshot_path = backup_dir / f"vyomnetra_backup_{timestamp}.sqlite3"

    logger.info(f"Initiating VACUUM INTO backup to {snapshot_path}...")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(f"VACUUM INTO '{snapshot_path.as_posix()}'")
        conn.close()
        logger.info("VACUUM INTO command executed successfully.")
    except Exception as e:
        conn.close()
        logger.error(f"Failed to execute VACUUM INTO: {e}")
        sys.exit(1)

    # Verify backup integrity with PRAGMA quick_check
    b_conn = sqlite3.connect(snapshot_path)
    cursor = b_conn.cursor()
    cursor.execute("PRAGMA quick_check;")
    result = cursor.fetchone()
    b_conn.close()

    if not result or result[0] != "ok":
        logger.critical(f"Backup integrity check FAILED for {snapshot_path}! Result: {result}")
        snapshot_path.unlink(missing_ok=True)
        sys.exit(1)

    logger.info(f"Integrity check PASSED for backup {snapshot_path.name}")

    # Prune snapshots older than retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    for old_file in backup_dir.glob("vyomnetra_backup_*.sqlite3"):
        mtime = datetime.fromtimestamp(old_file.stat().st_mtime, timezone.utc)
        if mtime < cutoff:
            logger.info(f"Pruning old backup snapshot: {old_file.name}")
            old_file.unlink(missing_ok=True)

    return snapshot_path


if __name__ == "__main__":
    out_path = backup_database()
    print(f"Backup complete: {out_path}")
