#!/usr/bin/env python3
"""Point-in-Time Database Restoration CLI Tool.

Restores database from specified backup snapshot file with pre-flight integrity check.
"""

import sys
import sqlite3
import shutil
from pathlib import Path
from typing import Optional

# Add workspace root to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vyomnetra.config import settings
from vyomnetra.utils.logger import get_logger

logger = get_logger("scripts.restore")


def restore_database(snapshot_file: Optional[Path] = None):
    """Restores active database from specified snapshot file."""
    db_path = settings.get_db_path()
    backup_dir = db_path.parent / "backups"

    if snapshot_file is None:
        snapshots = sorted(list(backup_dir.glob("vyomnetra_backup_*.sqlite3")), key=lambda p: p.stat().st_mtime)
        if not snapshots:
            logger.error("No backup snapshots found in backups directory!")
            sys.exit(1)
        snapshot_file = snapshots[-1]

    if not snapshot_file.exists():
        logger.error(f"Backup snapshot file {snapshot_file} does not exist!")
        sys.exit(1)

    logger.info(f"Verifying integrity of snapshot {snapshot_file.name} before restoration...")

    conn = sqlite3.connect(snapshot_file)
    cursor = conn.cursor()
    cursor.execute("PRAGMA quick_check;")
    res = cursor.fetchone()
    conn.close()

    if not res or res[0] != "ok":
        logger.critical(f"Snapshot integrity check failed! Aborting restoration.")
        sys.exit(1)

    # Perform safe atomic copy
    temp_target = db_path.with_suffix(".tmp")
    shutil.copy2(snapshot_file, temp_target)
    shutil.move(temp_target, db_path)

    logger.info(f"Successfully restored database from {snapshot_file.name} to {db_path.name}")


if __name__ == "__main__":
    snap_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    restore_database(snap_path)
