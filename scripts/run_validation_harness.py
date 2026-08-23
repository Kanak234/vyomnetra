#!/usr/bin/env python3
"""VYOMNETRA Comprehensive Multi-Tier Validation Harness Script.

Executes all 3 validation tiers against strictly independent, published reference sources:
1. WGS-84 Ellipsoidal Ground Site Accuracy Check (Hazaribagh Ground Station)
2. Tier 1: Vallado AIAA 2006-6753 Official C++ Reference Outputs (tcppver.out / SGP4-VER.TLE)
3. Tier 2: Independent Skyfield ITRS High-Level Position Transformation Engine (24-Hour Arc)
4. Tier 3: JPL Horizons Web API Observer Ephemeris Cross-Validation
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
import numpy as np

from vyomnetra.config import settings, GroundSite
from vyomnetra.propagate.frames import geodetic_to_ecef
from vyomnetra.propagate.validator import SGP4Validator


def run_full_validation():
    print("=" * 100)
    print("VYOMNETRA COMPREHENSIVE MULTI-TIER VALIDATION HARNESS — INDEPENDENT REFERENCE OUTPUT")
    print("=" * 100)

    # --------------------------------------------------------------------------
    # ITEM 1: WGS-84 Ellipsoid Ground Site Accuracy Verification
    # --------------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("[ITEM 1] WGS-84 ELLIPSOID GROUND SITE ACCURACY VERIFICATION (HAZARIBAGH)")
    print("-" * 100)
    
    hz_site = settings.sites["hazaribagh"]
    calc_ecef = geodetic_to_ecef(hz_site.latitude_deg, hz_site.longitude_deg, hz_site.elevation_m)
    
    # Exact double-precision reference vector for Hazaribagh WGS-84 site
    ref_ecef = np.array([471.19236257, 5811.57826021, 2578.20771181], dtype=np.float64)
    dx = abs(calc_ecef[0] - ref_ecef[0]) * 1000.0
    dy = abs(calc_ecef[1] - ref_ecef[1]) * 1000.0
    dz = abs(calc_ecef[2] - ref_ecef[2]) * 1000.0
    total_3d_err_m = float(np.linalg.norm(calc_ecef - ref_ecef)) * 1000.0

    calc_r_mag = float(np.linalg.norm(calc_ecef))
    ref_r_mag = float(np.linalg.norm(ref_ecef))

    print(f"Hazaribagh Geodetic Input:  Lat = {hz_site.latitude_deg}°, Lon = {hz_site.longitude_deg}°, Elev = {hz_site.elevation_m} m")
    print(f"Calculated WGS-84 ECEF:    X = {calc_ecef[0]:.6f} km, Y = {calc_ecef[1]:.6f} km, Z = {calc_ecef[2]:.6f} km")
    print(f"Target Reference ECEF:      X = {ref_ecef[0]:.6f} km, Y = {ref_ecef[1]:.6f} km, Z = {ref_ecef[2]:.6f} km")
    print(f"Calculated Geocentric |r|:  {calc_r_mag:.6f} km (Exact Reference Vector |r|: {ref_r_mag:.6f} km)")
    print(f"Coordinate Residual Errors: dX = {dx:.3f} m, dY = {dy:.3f} m, dZ = {dz:.3f} m")
    print(f"Total 3D Position Error:   {total_3d_err_m:.3f} metres")
    
    wgs84_passed = total_3d_err_m <= 1.0
    print(f"STATUS: WGS-84 ELLIPSOID ACCURACY VERIFIED {'PASSED (< 1.0 m tolerance)' if wgs84_passed else 'FAILED'}")

    # --------------------------------------------------------------------------
    # ITEM 2: Tier 1 Vallado AIAA 2006-6753 Official C++ Reference Benchmark
    # --------------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("[ITEM 2] TIER 1 VALLADO BENCHMARK SUITE (OFFICIAL tcppver.out C++ REFERENCE OUTPUT)")
    print("-" * 100)

    validator = SGP4Validator()
    tier1_map = validator.run_tier1_vallado_benchmark()

    print(f"{'NORAD ID':<10} | {'Satellite Name':<28} | {'Max Pos Err (km)':<18} | {'Max Vel Err (km/s)':<20} | {'Status':<6}")
    print("-" * 90)

    tier1_all_passed = True
    overall_max_pos = 0.0
    overall_max_vel = 0.0
    total_vectors = 0

    for norad_id, res in tier1_map.items():
        if not res.passed:
            tier1_all_passed = False
        overall_max_pos = max(overall_max_pos, res.max_position_error_km)
        overall_max_vel = max(overall_max_vel, res.max_velocity_error_kms)
        total_vectors += res.num_points_evaluated

        status_str = "PASS" if res.passed else "FAIL"
        print(f"{norad_id:<10} | {res.sat_name:<28} | {res.max_position_error_km:.6e}          | {res.max_velocity_error_kms:.6e}            | {status_str}")

    print("-" * 90)
    print(f"Tier 1 Benchmark Suite Summary: {total_vectors} total vectors evaluated across {len(tier1_map)} satellites.")
    print(f"Overall Max Position Error vs tcppver.out C++ reference: {overall_max_pos:.6e} km  (Tolerance: 1.000e-06 km / 1 mm)")
    print(f"Overall Max Velocity Error vs tcppver.out C++ reference: {overall_max_vel:.6e} km/s (Tolerance: 1.000e-09 km/s / 1 um/s)")
    print(f"Tier 1 Overall Status:      {'ALL PASSED' if tier1_all_passed else 'FAILED'}")

    # --------------------------------------------------------------------------
    # ITEM 3: Tier 2 Skyfield High-Level ITRS Celestial Transformation Cross-Validation
    # --------------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("[ITEM 3] TIER 2 SKYFIELD HIGH-LEVEL ITRS TRANSFORMATION AGREEMENT (24-HOUR ARC)")
    print("-" * 100)

    iss_tle1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9995"
    iss_tle2 = "2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    start_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    min_div, mean_div, max_div = validator.run_tier2_skyfield_cross_validation(
        tle_line1=iss_tle1,
        tle_line2=iss_tle2,
        sat_name="ISS (ZARYA)",
        start_dt=start_dt,
        duration_hours=24.0,
        step_minutes=1.0
    )

    print(f"Target Satellite: ISS (ZARYA) (NORAD #25544)")
    print(f"Propagation Arc:  24.0 Hours (1,440 1-minute steps)")
    print(f"Min Position Divergence (VYOMNETRA TEME->ECEF vs Skyfield ITRS):  {min_div:.3f} metres")
    print(f"Mean Position Divergence (VYOMNETRA TEME->ECEF vs Skyfield ITRS): {mean_div:.3f} metres")
    print(f"Max Position Divergence (VYOMNETRA TEME->ECEF vs Skyfield ITRS):  {max_div:.3f} metres")
    
    tier2_passed = max_div <= 200.0
    print(f"Tier 2 Cross-Implementation Status: {'PASSED (< 200.0 m frame alignment delta)' if tier2_passed else 'FAILED'}")

    # --------------------------------------------------------------------------
    # ITEM 4: Tier 3 JPL Horizons Topocentric Ephemeris Observer Cross-Validation
    # --------------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("[ITEM 4] TIER 3 JPL HORIZONS TOPOCENTRIC OBSERVER REFERENCE CROSS-VALIDATION")
    print("-" * 100)

    max_az_err, max_el_err, rows = validator.run_tier3_jpl_horizons_cross_validation(
        lat_deg=hz_site.latitude_deg,
        lon_deg=hz_site.longitude_deg,
        elev_m=hz_site.elevation_m,
        start_dt_str="2024-01-01T12:00:00",
        stop_dt_str="2024-01-01T13:00:00"
    )

    print(f"Target Ground Station: Hazaribagh (WGS-84 {hz_site.latitude_deg}°N, {hz_site.longitude_deg}°E, {hz_site.elevation_m}m)")
    print(f"Reference Source:      JPL Horizons Web API (SSD API / Observer Ephemeris Quantity #4)")
    print(f"Sample Time Arc:       2024-01-01 12:00 UTC to 13:00 UTC (10-minute intervals)")
    print()
    print(f"{'UTC Time':<20} | {'JPL Horizons (Az, El)':<24} | {'VYOMNETRA DE421 (Az, El)':<24} | {'Residuals (dAz, dEl)':<22}")
    print("-" * 98)

    for r in rows:
        t_str = r['time_utc'][:16].replace("T", " ") + " UTC"
        jpl_str = f"Az={r['jpl_az_deg']:6.2f}°, El={r['jpl_el_deg']:6.2f}°"
        calc_str = f"Az={r['calc_az_deg']:6.2f}°, El={r['calc_el_deg']:6.2f}°"
        res_str = f"dAz={r['d_az_deg']:.6f}°, dEl={r['d_el_deg']:.6f}°"
        print(f"{t_str:<20} | {jpl_str:<24} | {calc_str:<24} | {res_str:<22}")

    print("-" * 98)
    print(f"Max Azimuth Residual Error vs JPL Horizons:   {max_az_err:.6f} degrees ({max_az_err*3600.0:.2f} arcsec)")
    print(f"Max Elevation Residual Error vs JPL Horizons: {max_el_err:.6f} degrees ({max_el_err*3600.0:.2f} arcsec)")

    tier3_passed = max_az_err <= 0.05 and max_el_err <= 0.05
    print(f"Tier 3 Cross-Validation Status: {'PASSED (< 0.05° angular tolerance)' if tier3_passed else 'FAILED'}")

    # Final Overall Summary
    all_tiers_passed = wgs84_passed and tier1_all_passed and tier2_passed and tier3_passed
    print("\n" + "=" * 100)
    print(f"{'ALL VALIDATION HARNESS CHECKS EXECUTED SUCCESSFULLY' if all_tiers_passed else 'VALIDATION HARNESS FAILED CHECKS'}")
    print("=" * 100)

    if not all_tiers_passed:
        sys.exit(1)


if __name__ == "__main__":
    run_full_validation()
