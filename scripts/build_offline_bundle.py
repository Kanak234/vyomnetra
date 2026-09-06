#!/usr/bin/env python3
"""Offline-First SSA Bundle Package Generator.

Packages the complete standalone offline bundle containing models, database snapshots,
cached space weather payloads, seed catalogues, and static WebGL assets into a compressed release bundle.
"""

import sys
import tarfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

# Add workspace root to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vyomnetra.config import settings
from vyomnetra.utils.logger import get_logger

logger = get_logger("scripts.build_offline_bundle")


def build_offline_bundle() -> Path:
    """Builds offline distribution bundle archive."""
    root_dir = Path(__file__).parent.parent
    dist_dir = root_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    bundle_name = f"vyomnetra_offline_bundle_{timestamp}"
    bundle_staging = dist_dir / bundle_name
    bundle_staging.mkdir(parents=True, exist_ok=True)

    logger.info(f"Staging offline bundle at {bundle_staging}...")

    # Copy data directory (DB, models, seeds)
    data_dir = settings.get_db_path().parent
    if data_dir.exists():
        shutil.copytree(data_dir, bundle_staging / "data", dirs_exist_ok=True)

    # Copy static assets / HTML globe
    web_globe = root_dir / "vyomnetra" / "render" / "web_globe.html"
    if web_globe.exists():
        (bundle_staging / "web").mkdir(exist_ok=True)
        shutil.copy2(web_globe, bundle_staging / "web" / "index.html")

    # Create archive
    archive_path = dist_dir / f"{bundle_name}.tar.gz"
    logger.info(f"Compressing offline bundle into {archive_path.name}...")

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(bundle_staging, arcname=bundle_name)

    shutil.rmtree(bundle_staging, ignore_errors=True)

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    logger.info(f"Offline bundle creation SUCCESSFUL! Archive size: {size_mb:.2f} MB ({archive_path})")

    return archive_path


if __name__ == "__main__":
    archive = build_offline_bundle()
    print(f"Bundle build complete: {archive}")
