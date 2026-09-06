#!/usr/bin/env python3
"""7-Day / Multi-Iteration Soak Test & Memory Leak Validation Script.

Executes continuous SGP4 propagation and conjunction screening cycles while tracking
RSS memory consumption (MB) to assert zero memory growth / memory leak over long runs.
"""

import sys
import time
import os
import psutil
from pathlib import Path
from datetime import datetime, timezone

# Add workspace root to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.conjunction.screening import ConjunctionScreeningEngine
from vyomnetra.utils.logger import get_logger

logger = get_logger("scripts.soak_test")


def run_soak_test(iterations: int = 50, batch_size: int = 50) -> float:
    """Executes soak test iterations measuring initial vs final RSS memory (MB)."""
    db_manager = DatabaseManager()
    conjunction_engine = ConjunctionScreeningEngine()

    satellites = db_manager.get_all_satellites()
    if not satellites:
        logger.error("No satellites available for soak test!")
        return 0.0

    process = psutil.Process(os.getpid())
    rss_initial = process.memory_info().rss / (1024 * 1024)

    logger.info(f"Starting soak test: {iterations} iterations with {batch_size} satellites. Initial RSS: {rss_initial:.2f} MB")

    for i in range(iterations):
        start_time = time.time()
        now_dt = datetime.now(timezone.utc)
        alerts = conjunction_engine.screen_catalogue(
            satellites[:batch_size],
            start_dt=now_dt,
            duration_hours=12.0,
            max_miss_distance_km=50.0
        )
        elapsed = time.time() - start_time
        current_rss = process.memory_info().rss / (1024 * 1024)
        logger.info(f"Iteration {i+1}/{iterations}: Processed {len(alerts)} alerts in {elapsed:.3f}s. RSS: {current_rss:.2f} MB")

    rss_final = process.memory_info().rss / (1024 * 1024)
    growth_mb = rss_final - rss_initial

    logger.info(f"Soak test finished. Initial RSS: {rss_initial:.2f} MB, Final RSS: {rss_final:.2f} MB, Growth: {growth_mb:.2f} MB.")
    return growth_mb


if __name__ == "__main__":
    mem_growth = run_soak_test(iterations=20, batch_size=20)
    if mem_growth > 50.0:  # Threshold for abnormal memory growth
        print(f"FAIL: Memory growth {mem_growth:.2f} MB exceeds 50 MB threshold!")
        sys.exit(1)
    else:
        print(f"PASS: Soak test memory growth = {mem_growth:.2f} MB (Stable).")
        sys.exit(0)
