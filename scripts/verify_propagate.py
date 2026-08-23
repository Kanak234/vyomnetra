#!/usr/bin/env python3
"""Reproducible Phase 2 Verification Script for VYOMNETRA.

Executes and verifies:
1. Tier 1 Vallado SGP4 Reference Benchmark Suite (Pos error < 1e-6 km, Vel error < 1e-9 km/s).
2. TEME -> ECEF (ITRF) coordinate frame transformation engine.
3. Topocentric Azimuth/Elevation/Range for Hazaribagh ground site.
4. Vectorized batch propagation throughput (satellites/sec).
5. PySide6 GUI Validation Harness tab rendering & screenshot capture.
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime, timezone
import numpy as np

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from vyomnetra.config import settings
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.propagate.engine import SGP4Engine
from vyomnetra.propagate.frames import teme_to_ecef, ecef_to_topocentric
from vyomnetra.propagate.validator import Tier1ValladoValidator
from vyomnetra.ui.app import MainWindow


def run_verification():
    print("=" * 80)
    print("VYOMNETRA PHASE 2 PROPAGATION & TIER 1 BENCHMARK VERIFICATION SCRIPT")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 1. Tier 1 Vallado Reference Benchmark Harness
    # --------------------------------------------------------------------------
    print("\n--- [STEP 1] Tier 1 Vallado Reference Benchmark Verification ---")
    validator = Tier1ValladoValidator()
    results, max_pos_err, max_vel_err, all_passed = validator.run_benchmark_suite()

    print(f"Total Test Case Vectors Evaluated: {len(results)}")
    print(f"Target Position Tolerance:         {validator.pos_tol_km:.1e} km (1.0 mm)")
    print(f"Target Velocity Tolerance:         {validator.vel_tol_kms:.1e} km/s (1.0 um/s)")
    print(f"Observed Max Position Residual:    {max_pos_err:.6e} km")
    print(f"Observed Max Velocity Residual:    {max_vel_err:.6e} km/s")
    print(f"Tier 1 Benchmark Status:           {'PASS [GREEN]' if all_passed else 'FAIL [RED]'}")

    for idx, r in enumerate(results, 1):
        pos_status = "PASS" if r.pos_passed else "FAIL"
        vel_status = "PASS" if r.vel_passed else "FAIL"
        print(f"  Vector [{idx}] NORAD #{r.norad_id:<5} ({r.sat_name}) @ +{r.offset_min:>5.1f} min:")
        print(f"    Pos Err: {r.pos_err_km:.3e} km [{pos_status}] | Vel Err: {r.vel_err_kms:.3e} km/s [{vel_status}]")

    assert all_passed, f"Tier 1 Vallado Benchmark FAILED! Max Pos Err: {max_pos_err:.3e} km, Max Vel Err: {max_vel_err:.3e} km/s"

    # --------------------------------------------------------------------------
    # 2. TEME -> ECEF Frame Transformation Verification
    # --------------------------------------------------------------------------
    print("\n--- [STEP 2] TEME -> ECEF (ITRF) Frame Transformation Engine ---")
    now_dt = datetime.now(timezone.utc)
    engine = SGP4Engine()
    
    # Propagate NORAD 5
    cases = validator.get_canonical_vallado_test_cases()
    satrec = engine.create_satrec(cases[0]["tle1"], cases[0]["tle2"])
    err, r_teme, v_teme = engine.propagate_single(satrec, satrec.jdsatepoch, satrec.jdsatepochF)

    r_ecef, v_ecef = teme_to_ecef(r_teme, v_teme, now_dt)

    print(f"Epoch UTC:           {now_dt.isoformat()}")
    print(f"TEME Position (km):  [{r_teme[0]:12.4f}, {r_teme[1]:12.4f}, {r_teme[2]:12.4f}] | Norm: {np.linalg.norm(r_teme):.4f} km")
    print(f"ECEF Position (km):  [{r_ecef[0]:12.4f}, {r_ecef[1]:12.4f}, {r_ecef[2]:12.4f}] | Norm: {np.linalg.norm(r_ecef):.4f} km")
    print(f"TEME Velocity (km/s):[{v_teme[0]:12.6f}, {v_teme[1]:12.6f}, {v_teme[2]:12.6f}]")
    print(f"ECEF Velocity (km/s):[{v_ecef[0]:12.6f}, {v_ecef[1]:12.6f}, {v_ecef[2]:12.6f}]")

    # Pos norm preservation check (pure rotation)
    assert np.abs(np.linalg.norm(r_teme) - np.linalg.norm(r_ecef)) < 1e-9, "Frame rotation altered position vector magnitude!"

    # --------------------------------------------------------------------------
    # 3. Topocentric Azimuth/Elevation/Range for Hazaribagh Ground Site
    # --------------------------------------------------------------------------
    print("\n--- [STEP 3] Topocentric Calculation for Hazaribagh Ground Site ---")
    hz_site = settings.sites["hazaribagh"]
    az_deg, el_deg, rng_km = ecef_to_topocentric(r_ecef, hz_site)

    print(f"Ground Station:  {hz_site.name} ({hz_site.latitude_deg:.4f}°N, {hz_site.longitude_deg:.4f}°E, Elev: {hz_site.elevation_m}m)")
    print(f"Slant Range:     {rng_km:.2f} km")
    print(f"Elevation Angle: {el_deg:.2f}°")
    print(f"Azimuth Angle:   {az_deg:.2f}°")

    # --------------------------------------------------------------------------
    # 4. Vectorized Batch Propagation Throughput Performance
    # --------------------------------------------------------------------------
    print("\n--- [STEP 4] Vectorized Batch Propagation Performance ---")
    n_sats = 10000
    satrecs = [satrec] * n_sats
    
    start_batch = time.time()
    errs, pos_batch, vel_batch = engine.propagate_batch(satrecs, satrec.jdsatepoch, satrec.jdsatepochF + 0.01)
    duration_batch = time.time() - start_batch
    throughput = n_sats / duration_batch

    print(f"Batch Size:      {n_sats:,} satellites")
    print(f"Batch Duration:  {duration_batch * 1000.0:.2f} ms")
    print(f"Throughput:      {throughput:,.0f} satellites/sec")

    assert throughput > 5000, "Propagation throughput below target 5,000 sats/sec!"

    # --------------------------------------------------------------------------
    # 5. PySide6 Validation Harness UI Capture
    # --------------------------------------------------------------------------
    print("\n--- [STEP 5] PySide6 Validation Harness UI Capture ---")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow()
    # Switch to Validation Harness tab (Index 7)
    window.tabs.setCurrentIndex(7)
    window.on_run_validation()
    window.show()

    # Process paint events
    loop = QEventLoop()
    QTimer.singleShot(500, loop.quit)
    loop.exec()
    window.repaint()

    pixmap = window.grab()
    screenshot_path = Path("vyomnetra_validation_harness.png").resolve()
    pixmap.save(str(screenshot_path), "PNG")

    print(f"Validation Harness UI Captured: {screenshot_path}")
    print(f"Image Dimensions: {pixmap.width()} x {pixmap.height()} | Size: {screenshot_path.stat().st_size:,} bytes")

    print("\n" + "=" * 80)
    print("PHASE 2 PROPAGATION & TIER 1 VERIFICATION COMPLETE — ALL TESTS PASSED")
    print("=" * 80)


if __name__ == "__main__":
    run_verification()
