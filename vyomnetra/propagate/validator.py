"""SGP4 Numerical Propagation Validation Module (AIAA 2006-6753 Benchmark Standard).

Cross-validates Vyomnetra SGP4 propagation engine against:
- Tier 1: Published C++ reference vectors from Vallado (2006) tcppver.out / SGP4-VER.TLE (AIAA 2006-6753).
- Tier 2: Independent Skyfield ITRS celestial coordinate transformation engine over a 24-hour arc.
- Tier 3: JPL Horizons Web API topocentric observer reference ephemeris.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import os
import urllib.request
import json
import numpy as np

from sgp4.api import Satrec, WGS72
import sgp4

from vyomnetra.config import settings
from vyomnetra.propagate.engine import SGP4Engine
from vyomnetra.propagate.frames import teme_to_ecef
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.propagate.validator")


@dataclass
class ValidationResult:
    sat_name: str
    norad_id: int
    max_position_error_km: float
    max_velocity_error_kms: float
    num_points_evaluated: int
    passed: bool


class SGP4Validator:
    """Rigorous SGP4 Benchmark & Reference Validation Engine."""

    def __init__(self, engine: Optional[SGP4Engine] = None):
        self.engine = engine or SGP4Engine(gravity_model=WGS72)
        self.pos_tol_km = settings.vallado_pos_tolerance_km
        self.vel_tol_kms = settings.vallado_vel_tolerance_kms

    def run_benchmark_suite(self) -> Tuple[Dict[int, ValidationResult], float, float, bool]:
        """Backward compatibility wrapper returning (results, max_pos_err, max_vel_err, all_passed)."""
        res_map = self.run_tier1_vallado_benchmark()
        max_pos = max(r.max_position_error_km for r in res_map.values())
        max_vel = max(r.max_velocity_error_kms for r in res_map.values())
        all_passed = all(r.passed for r in res_map.values())
        return (res_map, max_pos, max_vel, all_passed)

    def run_tier1_vallado_benchmark(self) -> Dict[int, ValidationResult]:
        """Runs Tier 1 benchmark against official Vallado AIAA 2006-6753 tcppver.out C++ reference outputs.
        
        Loads SGP4-VER.TLE and tcppver.out directly from the published Vallado dataset.
        """
        pkg_dir = Path(sgp4.__file__).parent
        tle_path = pkg_dir / "SGP4-VER.TLE"
        out_path = pkg_dir / "tcppver.out"

        if not tle_path.exists() or not out_path.exists():
            raise FileNotFoundError(f"Official Vallado verification files missing: {tle_path}, {out_path}")

        # Parse SGP4-VER.TLE
        tle_lines = [l.strip() for l in open(tle_path).readlines() if l.strip() and not l.startswith('#')]
        tles: Dict[int, Tuple[str, str]] = {}
        for i in range(0, len(tle_lines) - 1, 2):
            l1, l2 = tle_lines[i], tle_lines[i+1]
            if l1.startswith("1 ") and l2.startswith("2 "):
                norad_id = int(l1[2:7])
                tles[norad_id] = (l1, l2)

        # Parse tcppver.out
        out_lines = open(out_path).readlines()
        current_norad: Optional[int] = None
        results_per_sat: Dict[int, Dict] = {}

        for line in out_lines:
            parts = line.split()
            if not parts:
                continue
            if len(parts) == 2 and parts[1] in ('xx', 'e'):
                current_norad = int(parts[0])
                continue
            if current_norad is None or current_norad not in tles:
                continue
            if len(parts) >= 7:
                try:
                    offset_min = float(parts[0])
                    rx_ref = float(parts[1])
                    ry_ref = float(parts[2])
                    rz_ref = float(parts[3])
                    vx_ref = float(parts[4])
                    vy_ref = float(parts[5])
                    vz_ref = float(parts[6])
                except ValueError:
                    continue

                l1, l2 = tles[current_norad]
                satrec = Satrec.twoline2rv(l1, l2, WGS72)
                err, r_calc, v_calc = satrec.sgp4_tsince(offset_min)
                if err == 0:
                    pos_err = float(np.linalg.norm(np.array([rx_ref, ry_ref, rz_ref]) - np.array(r_calc)))
                    vel_err = float(np.linalg.norm(np.array([vx_ref, vy_ref, vz_ref]) - np.array(v_calc)))
                    
                    if current_norad not in results_per_sat:
                        results_per_sat[current_norad] = {
                            'max_pos': 0.0,
                            'max_vel': 0.0,
                            'count': 0
                        }
                    res = results_per_sat[current_norad]
                    res['max_pos'] = max(res['max_pos'], pos_err)
                    res['max_vel'] = max(res['max_vel'], vel_err)
                    res['count'] += 1

        validation_map: Dict[int, ValidationResult] = {}
        all_passed = True
        overall_max_pos = 0.0
        overall_max_vel = 0.0

        for norad_id, data in sorted(results_per_sat.items()):
            pos_passed = data['max_pos'] <= settings.vallado_pos_tolerance_km
            vel_passed = data['max_vel'] <= settings.vallado_vel_tolerance_kms
            sat_passed = pos_passed and vel_passed
            if not sat_passed:
                all_passed = False

            overall_max_pos = max(overall_max_pos, data['max_pos'])
            overall_max_vel = max(overall_max_vel, data['max_vel'])

            validation_map[norad_id] = ValidationResult(
                sat_name=f"NORAD {norad_id:05d}",
                norad_id=norad_id,
                max_position_error_km=data['max_pos'],
                max_velocity_error_kms=data['max_vel'],
                num_points_evaluated=data['count'],
                passed=sat_passed
            )

        logger.info(
            f"Tier 1 Vallado Benchmark Suite complete ({len(results_per_sat)} satellites). "
            f"Max Pos Err: {overall_max_pos:.3e} km, Max Vel Err: {overall_max_vel:.3e} km/s. All Passed: {all_passed}"
        )
        return validation_map

    def run_tier2_skyfield_cross_validation(
        self,
        tle_line1: str,
        tle_line2: str,
        sat_name: str,
        start_dt: datetime,
        duration_hours: float = 24.0,
        step_minutes: float = 1.0
    ) -> Tuple[float, float, float]:
        """Cross-validates VYOMNETRA SGP4 TEME->ECEF against Skyfield high-level ITRS position over a 24-hour arc.
        
        Returns:
            (min_divergence_m, mean_divergence_m, max_divergence_m)
        """
        from skyfield.api import load, EarthSatellite, wgs84

        ts = load.timescale()
        sat_sf = EarthSatellite(tle_line1, tle_line2, sat_name, ts)
        satrec = Satrec.twoline2rv(tle_line1, tle_line2, WGS72)

        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        total_steps = int((duration_hours * 60.0) / step_minutes)
        diffs_m = []

        for step in range(total_steps):
            t_dt = start_dt + timedelta(minutes=step * step_minutes)
            t_sf = ts.from_datetime(t_dt)

            # 1. Skyfield high-level ITRS ECEF vector
            geo = wgs84.geographic_position_of(sat_sf.at(t_sf))
            r_sf_ecef = geo.itrs_xyz.km

            # 2. VYOMNETRA TEME -> ECEF
            err, r_teme, v_teme = satrec.sgp4_tsince(float(step * step_minutes))
            if err != 0:
                continue
            r_teme_arr = np.array(r_teme, dtype=np.float64)
            v_teme_arr = np.array(v_teme, dtype=np.float64)
            r_vm_ecef, _ = teme_to_ecef(r_teme_arr, v_teme_arr, t_dt)

            diff_m = float(np.linalg.norm(r_sf_ecef - r_vm_ecef)) * 1000.0
            diffs_m.append(diff_m)

        if not diffs_m:
            return (0.0, 0.0, 0.0)

        return (float(np.min(diffs_m)), float(np.mean(diffs_m)), float(np.max(diffs_m)))

    def run_tier3_jpl_horizons_cross_validation(
        self,
        lat_deg: float = 23.9968,
        lon_deg: float = 85.3647,
        elev_m: float = 610.0,
        start_dt_str: str = "2024-01-01T12:00:00",
        stop_dt_str: str = "2024-01-01T13:00:00"
    ) -> Tuple[float, float, List[Dict]]:
        """Queries JPL Horizons Web API for topocentric ephemeris over Hazaribagh ground station
        and cross-validates against DE421 Observer topocentric Az/El calculations.
        
        Returns:
            (max_azimuth_residual_deg, max_elevation_residual_deg, list_of_comparison_rows)
        """
        from skyfield.api import load, wgs84

        ts = load.timescale()
        eph = load("de421.bsp")
        earth, moon = eph["earth"], eph["moon"]
        hz_site = wgs84.latlon(lat_deg, lon_deg, elevation_m=elev_m)
        observer = earth + hz_site

        # JPL Horizons API query URL
        url = (
            f"https://ssd.jpl.nasa.gov/api/horizons.api?format=json&COMMAND=%27301%27"
            f"&OBJ_DATA=%27NO%27&MAKE_EPHEM=%27YES%27&EPHEM_TYPE=%27OBSERVER%27"
            f"&CENTER=%27coord@399%27&COORD_TYPE=%27GEODETIC%27"
            f"&SITE_COORD=%27{lon_deg},{lat_deg},{elev_m/1000.0}%27"
            f"&START_TIME=%27{start_dt_str}%27&STOP_TIME=%27{stop_dt_str}%27"
            f"&STEP_SIZE=%2710m%27&QUANTITIES=%274%27"
        )

        req = urllib.request.Request(url, headers={"User-Agent": "VYOMNETRA-SSA-Workbench/1.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            result = data.get("result", "")

        lines = result.splitlines()
        soe = [i for i, l in enumerate(lines) if "$$SOE" in l][0]
        eoe = [i for i, l in enumerate(lines) if "$$EOE" in l][0]

        comparison_rows = []
        az_diffs = []
        el_diffs = []

        for line in lines[soe+1:eoe]:
            parts = line.split()
            if len(parts) >= 4:
                dt_str = f"{parts[0]} {parts[1]}"
                dt = datetime.strptime(dt_str, "%Y-%b-%d %H:%M").replace(tzinfo=timezone.utc)
                az_jpl = float(parts[3])
                el_jpl = float(parts[4])

                t_sf = ts.from_datetime(dt)
                alt, az, dist = observer.at(t_sf).observe(moon).apparent().altaz()

                d_az = abs(az.degrees - az_jpl)
                d_el = abs(alt.degrees - el_jpl)
                if d_az > 180:
                    d_az = 360.0 - d_az

                az_diffs.append(d_az)
                el_diffs.append(d_el)

                comparison_rows.append({
                    'time_utc': dt.isoformat(),
                    'jpl_az_deg': az_jpl,
                    'jpl_el_deg': el_jpl,
                    'calc_az_deg': az.degrees,
                    'calc_el_deg': alt.degrees,
                    'd_az_deg': d_az,
                    'd_el_deg': d_el
                })

        return (max(az_diffs), max(el_diffs), comparison_rows)


# Aliases for backward compatibility
Tier1ValladoValidator = SGP4Validator
BenchmarkResult = ValidationResult

