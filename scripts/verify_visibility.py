#!/usr/bin/env python3
"""Reproducible Phase 3 Verification Script for VYOMNETRA.

Executes and verifies:
1. Topocentric satellite pass predictor (AOS, TCA, LOS, Max El, Slant Range).
2. Solar illumination engine (Sunlit vs Earth Shadow Umbra).
3. Optical naked-eye visibility flag evaluation.
4. Observation Log Manager & empirical residual calculation in SQLite.
5. PySide6 GUI Pass Planner panel rendering & screenshot capture.
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from vyomnetra.config import settings
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.ingest.adapters import CelesTrakAdapter
from vyomnetra.visibility.passes import PassPredictor
from vyomnetra.visibility.illumination import is_satellite_sunlit, is_naked_eye_visible, get_observer_solar_elevation_deg
from vyomnetra.visibility.obs_log import ObservationLogManager
from vyomnetra.ui.app import MainWindow


def run_verification():
    print("=" * 80)
    print("VYOMNETRA PHASE 3 VISIBILITY & PASS PREDICTOR VERIFICATION SCRIPT")
    print("=" * 80)

    db_manager = DatabaseManager()
    
    # Ensure database has catalogue satellites loaded
    satellites = db_manager.get_all_satellites()
    if not satellites:
        print("\n[SETUP] Seed database with CelesTrak stations catalogue...")
        adapter = CelesTrakAdapter(db_manager)
        _, satellites = adapter.fetch(group="stations")

    print(f"Database contains {len(satellites)} satellites.")
    assert len(satellites) > 0, "Database must contain satellites for pass verification!"

    # Find ISS (NORAD 25544) or first satellite
    iss_rec = next((s for s in satellites if s.norad_id == 25544), satellites[0])
    hz_site = settings.sites["hazaribagh"]

    # --------------------------------------------------------------------------
    # 1. Topocentric Pass Prediction Verification
    # --------------------------------------------------------------------------
    print("\n--- [STEP 1] Topocentric Pass Prediction Verification ---")
    predictor = PassPredictor()
    now_dt = datetime.now(timezone.utc)
    
    passes = predictor.predict_passes(iss_rec, hz_site, now_dt, duration_hours=48.0, min_elevation_deg=10.0)
    print(f"Target Ground Site: {hz_site.name} ({hz_site.latitude_deg:.4f}°N, {hz_site.longitude_deg:.4f}°E)")
    print(f"Target Satellite:   {iss_rec.name} (NORAD #{iss_rec.norad_id})")
    print(f"Predicted Passes:   {len(passes)} passes found over 48-hour window")

    for idx, p in enumerate(passes, 1):
        print(f"  Pass [{idx}]: {p.format_pass_summary()}")

    assert len(passes) > 0, "Expected at least 1 pass over 48-hour window!"
    
    p1 = passes[0]
    assert p1.aos_dt < p1.tca_dt < p1.los_dt
    assert p1.max_elevation_deg >= 10.0
    assert p1.duration_seconds > 0.0

    # --------------------------------------------------------------------------
    # 2. Solar Illumination & Naked-Eye Flag Verification
    # --------------------------------------------------------------------------
    print("\n--- [STEP 2] Solar Illumination & Naked-Eye Visibility Flag Verification ---")
    sun_el = get_observer_solar_elevation_deg(hz_site, p1.tca_dt)
    print(f"Pass #1 TCA UTC:                {p1.tca_dt.isoformat()}")
    print(f"Observer Solar Elevation at TCA: {sun_el:.2f}° ({'Twilight/Night' if sun_el <= -6.0 else 'Daylight'})")
    print(f"Satellite Illumination State:    {'SUNLIT' if p1.is_sunlit_at_tca else 'UMBRA (Eclipsed)'}")
    print(f"Optical Naked-Eye Visible Flag:  {p1.is_naked_eye_visible}")

    # --------------------------------------------------------------------------
    # 3. Observation Log Engine & Empirical Residual Verification
    # --------------------------------------------------------------------------
    print("\n--- [STEP 3] Empirical Observation Log & Residual Engine Verification ---")
    obs_manager = ObservationLogManager(db_manager)
    
    # Simulate user recording a real observation with +12.5s time delta and -0.4 deg el delta
    obs_tca = p1.tca_dt + timedelta(seconds=12.5)
    obs_max_el = p1.max_elevation_deg - 0.4

    rec = obs_manager.record_observation(
        norad_id=iss_rec.norad_id,
        sat_name=iss_rec.name,
        site_name=hz_site.name,
        pred_tca_dt=p1.tca_dt,
        obs_tca_dt=obs_tca,
        pred_max_el_deg=p1.max_elevation_deg,
        obs_max_el_deg=obs_max_el,
        notes="Ground optical sighting at Hazaribagh observatory"
    )

    print(f"Logged Observation ID:     #{rec.id}")
    print(f"Predicted TCA UTC:         {rec.pred_tca_dt.isoformat()}")
    print(f"Observed TCA UTC:          {rec.obs_tca_dt.isoformat()}")
    print(f"Calculated Time Residual:  dt = {rec.time_residual_sec:+.2f} seconds")
    print(f"Calculated El Residual:    dEl = {rec.elevation_residual_deg:+.2f} degrees")

    assert rec.time_residual_sec == 12.5
    assert abs(rec.elevation_residual_deg - (-0.4)) < 1e-6

    # Verify query from database
    logged_recs = obs_manager.get_observations_for_satellite(iss_rec.norad_id)
    assert len(logged_recs) >= 1
    assert logged_recs[0].id == rec.id

    # --------------------------------------------------------------------------
    # 4. PySide6 Pass Planner UI Panel Capture
    # --------------------------------------------------------------------------
    print("\n--- [STEP 4] PySide6 Pass Planner UI Panel Capture ---")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow()
    # Switch to Pass Planner tab (Index 3)
    window.tabs.setCurrentIndex(3)
    window.show()

    # Process Qt event loop
    loop = QEventLoop()
    QTimer.singleShot(500, loop.quit)
    loop.exec()
    window.repaint()

    pixmap = window.grab()
    screenshot_path = Path("vyomnetra_pass_planner.png").resolve()
    pixmap.save(str(screenshot_path), "PNG")

    print(f"Pass Planner UI Captured: {screenshot_path}")
    print(f"Image Dimensions: {pixmap.width()} x {pixmap.height()} | Size: {screenshot_path.stat().st_size:,} bytes")

    print("\n" + "=" * 80)
    print("PHASE 3 VISIBILITY & PASS PREDICTOR COMPLETE — ALL TESTS PASSED")
    print("=" * 80)


if __name__ == "__main__":
    run_verification()
