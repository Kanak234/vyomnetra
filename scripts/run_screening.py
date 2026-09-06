#!/usr/bin/env python3
"""CLI runner to execute batch spatial conjunction screening across the satellite catalogue."""

import sys
from datetime import datetime, timezone
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.conjunction.screening import ConjunctionScreeningEngine

def main():
    db = DatabaseManager()
    satellites = db.get_all_satellites()
    print(f"📡 Loaded {len(satellites)} objects from SQLite catalogue.")

    if len(satellites) < 2:
        print("⚠️ Not enough satellites to perform conjunction screening. Ingest catalogue first (scripts/verify_ingest.py).")
        sys.exit(0)

    engine = ConjunctionScreeningEngine()
    now_dt = datetime.now(timezone.utc)
    print(f"🔍 Running 24-hour SGP4 screening & Foster 2D Pc calculation...")
    
    alerts = engine.screen_catalogue(satellites, start_dt=now_dt, duration_hours=24.0, max_miss_distance_km=50.0)
    db.save_conjunction_alerts(alerts)

    print(f"✅ Screening complete. Generated {len(alerts)} conjunction alerts.")
    for idx, a in enumerate(alerts, 1):
        print(
            f"   Alert #{idx} [{a.severity}] TCA: {a.tca_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} | "
            f"Objects: {a.primary_name} (#{a.primary_norad}) vs {a.secondary_name} (#{a.secondary_norad}) | "
            f"Miss: {a.miss_distance_km:.2f} km | Pc: {a.calculated_pc:.2e}"
        )

if __name__ == "__main__":
    main()
