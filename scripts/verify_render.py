#!/usr/bin/env python3
"""Reproducible Phase 4 Verification Script for VYOMNETRA.

Executes and verifies:
1. 3D Earth sphere mesh and ground station ECEF overlay generation.
2. Solar terminator day/night boundary 3D curve computation.
3. Satellite SGP4 orbit trajectory 3D arc propagation in ECEF.
4. PySide6 3D Globe panel rendering and screenshot capture.
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
from vyomnetra.ingest.adapters import CelesTrakAdapter
from vyomnetra.render.globe_engine import (
    get_earth_sphere_mesh,
    get_ground_site_ecef,
    get_ground_site_coverage_ring,
    generate_satellite_orbit_trajectory
)
from vyomnetra.render.terminator import calculate_solar_terminator_points, get_solar_subpoint
from vyomnetra.ui.app import MainWindow


def run_verification():
    print("=" * 80)
    print("VYOMNETRA PHASE 4 3D ORBITAL GLOBE VERIFICATION SCRIPT")
    print("=" * 80)

    db_manager = DatabaseManager()
    satellites = db_manager.get_all_satellites()
    if not satellites:
        print("\n[SETUP] Seed database with CelesTrak stations catalogue...")
        adapter = CelesTrakAdapter(db_manager)
        _, satellites = adapter.fetch(group="stations")

    print(f"Database contains {len(satellites)} satellites.")
    assert len(satellites) > 0, "Database must contain satellites for globe verification!"

    # --------------------------------------------------------------------------
    # 1. 3D Earth Sphere & Ground Station Mesh Verification
    # --------------------------------------------------------------------------
    print("\n--- [STEP 1] 3D Earth Sphere & Ground Station Mesh Verification ---")
    x, y, z = get_earth_sphere_mesh(num_lat=20, num_lon=40)
    print(f"Earth Mesh Dimensions: X={x.shape}, Y={y.shape}, Z={z.shape}")
    assert x.shape == (40, 20)

    hz_site = settings.sites["hazaribagh"]
    site_ecef = get_ground_site_ecef(hz_site)
    site_dist_km = np.linalg.norm(site_ecef)
    print(f"Ground Site Hazaribagh ECEF: [{site_ecef[0]:.2f}, {site_ecef[1]:.2f}, {site_ecef[2]:.2f}] km")
    print(f"Hazaribagh Geocentric Distance: {site_dist_km:.3f} km (Expected ~6378.7 km)")
    assert 6370.0 < site_dist_km < 6390.0

    ring_pts = get_ground_site_coverage_ring(hz_site)
    print(f"Hazaribagh Horizon Coverage Ring Points: {ring_pts.shape}")
    assert ring_pts.shape == (72, 3)

    # --------------------------------------------------------------------------
    # 2. Solar Terminator Day/Night Boundary Verification
    # --------------------------------------------------------------------------
    print("\n--- [STEP 2] Solar Terminator Day/Night Boundary Engine Verification ---")
    now_dt = datetime.now(timezone.utc)
    sub_lat, sub_lon = get_solar_subpoint(now_dt)
    print(f"Current Sub-Solar Point: Lat={sub_lat:.2f}°, Lon={sub_lon:.2f}°")

    lat_lon_arr, term_ecef = calculate_solar_terminator_points(now_dt, num_points=180)
    print(f"Solar Terminator Line: {term_ecef.shape[0]} points generated")
    term_dists = np.linalg.norm(term_ecef, axis=1)
    print(f"Terminator Points Surface Radius: Mean={np.mean(term_dists):.2f} km")
    assert np.allclose(term_dists, 6378.137, atol=1.0)

    # --------------------------------------------------------------------------
    # 3. Satellite Orbit Trajectory 3D Arc Verification
    # --------------------------------------------------------------------------
    print("\n--- [STEP 3] Satellite 3D Orbit Trajectory Arc Verification ---")
    iss_rec = next((s for s in satellites if s.norad_id == 25544), satellites[0])
    pos_ecef, vel_ecef, dt_list = generate_satellite_orbit_trajectory(iss_rec, now_dt, duration_minutes=95.0, step_seconds=60.0)
    
    print(f"Target Satellite: {iss_rec.name} (NORAD #{iss_rec.norad_id})")
    print(f"Generated Orbit Points: {pos_ecef.shape[0]} points over 95-minute orbit period")
    
    orbital_radii = np.linalg.norm(pos_ecef, axis=1)
    print(f"Orbital Altitude Range: {np.min(orbital_radii) - 6378.137:.1f} km to {np.max(orbital_radii) - 6378.137:.1f} km")
    assert np.all((orbital_radii > 6500.0) & (orbital_radii < 8000.0))

    # --------------------------------------------------------------------------
    # 4. PySide6 3D Globe UI Screenshot Capture
    # --------------------------------------------------------------------------
    print("\n--- [STEP 4] PySide6 3D Globe UI Screenshot Capture ---")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow()
    # Switch to 3D Globe tab (Index 0)
    window.tabs.setCurrentIndex(0)
    window.show()

    # Process Qt event loop to render Matplotlib canvas
    loop = QEventLoop()
    QTimer.singleShot(1000, loop.quit)
    loop.exec()
    window.repaint()

    pixmap = window.grab()
    screenshot_path = Path("vyomnetra_3d_globe.png").resolve()
    pixmap.save(str(screenshot_path), "PNG")

    print(f"3D Globe UI Captured: {screenshot_path}")
    print(f"Image Dimensions: {pixmap.width()} x {pixmap.height()} | Size: {screenshot_path.stat().st_size:,} bytes")

    print("\n" + "=" * 80)
    print("PHASE 4 3D ORBITAL GLOBE COMPLETE — ALL TESTS PASSED")
    print("=" * 80)


if __name__ == "__main__":
    run_verification()
