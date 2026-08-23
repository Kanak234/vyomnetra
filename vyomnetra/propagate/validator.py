"""Tier 1 SGP4 Reference Benchmark Verification Harness (Vallado Benchmark).

Compares SGP4 analytical propagation output against published reference solutions
from Vallado et al. ("Revisiting Spacetrack Report #3", AIAA 2006-6753).
Enforces numeric tolerances: Position < 1e-6 km (1 mm), Velocity < 1e-9 km/s (1 um/s).
Loads test fixtures strictly from test fixture files. Zero TLE literals in source code.
"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from sgp4.api import Satrec, WGS72

from vyomnetra.config import settings
from vyomnetra.utils.logger import get_logger
from vyomnetra.propagate.engine import SGP4Engine

logger = get_logger("vyomnetra.propagate.validator")


@dataclass
class BenchmarkResult:
    """Result of a single Tier 1 benchmark propagation test."""
    sat_name: str
    norad_id: int
    offset_min: float
    r_calc_teme: np.ndarray
    v_calc_teme: np.ndarray
    r_ref_teme: np.ndarray
    v_ref_teme: np.ndarray
    pos_err_km: float
    vel_err_kms: float
    pos_passed: bool
    vel_passed: bool


class Tier1ValladoValidator:
    """Tier 1 SGP4 Reference Benchmark Harness."""

    def __init__(self, pos_tol_km: Optional[float] = None, vel_tol_kms: Optional[float] = None, fixture_path: Optional[Path] = None):
        self.pos_tol_km = pos_tol_km if pos_tol_km is not None else settings.vallado_pos_tolerance_km
        self.vel_tol_kms = vel_tol_kms if vel_tol_kms is not None else settings.vallado_vel_tolerance_kms
        self.engine = SGP4Engine(gravity_model=WGS72)
        self.fixture_path = fixture_path or Path("tests/fixtures/sgp4_ver_reference.json")

    def get_canonical_vallado_test_cases(self) -> List[Dict[str, Any]]:
        """Loads canonical Vallado reference verification test cases from test fixture file."""
        if not self.fixture_path.exists():
            raise FileNotFoundError(f"Tier 1 benchmark fixture file not found at {self.fixture_path}")

        with open(self.fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cases = []
        for item in data:
            benchmarks = []
            for bm in item["benchmarks"]:
                benchmarks.append({
                    "offset_min": float(bm["offset_min"]),
                    "r_ref": np.array(bm["r_ref"], dtype=np.float64),
                    "v_ref": np.array(bm["v_ref"], dtype=np.float64)
                })

            cases.append({
                "name": item["name"],
                "norad_id": item["norad_id"],
                "tle1": item["tle1"],
                "tle2": item["tle2"],
                "benchmarks": benchmarks
            })

        return cases

    def run_benchmark_suite(self) -> Tuple[List[BenchmarkResult], float, float, bool]:
        """Executes full Tier 1 benchmark suite.
        
        Returns:
            results: List of BenchmarkResult objects
            max_pos_err_km: Maximum position error magnitude across all test vectors
            max_vel_err_kms: Maximum velocity error magnitude across all test vectors
            all_passed: True if 100% of benchmark vectors pass tolerance threshold
        """
        cases = self.get_canonical_vallado_test_cases()
        results: List[BenchmarkResult] = []
        max_pos_err = 0.0
        max_vel_err = 0.0
        all_passed = True

        for case in cases:
            satrec = self.engine.create_satrec(case["tle1"], case["tle2"])
            
            for bm in case["benchmarks"]:
                offset_min = bm["offset_min"]
                err, r_calc, v_calc = satrec.sgp4_tsince(offset_min)
                r_calc = np.array(r_calc, dtype=np.float64)
                v_calc = np.array(v_calc, dtype=np.float64)

                r_ref = bm["r_ref"]
                v_ref = bm["v_ref"]

                if err != 0:
                    pos_err = 999.0
                    vel_err = 999.0
                    pos_pass = False
                    vel_pass = False
                else:
                    pos_err = float(np.linalg.norm(r_calc - r_ref))
                    vel_err = float(np.linalg.norm(v_calc - v_ref))
                    
                    pos_pass = pos_err <= self.pos_tol_km
                    vel_pass = vel_err <= self.vel_tol_kms

                max_pos_err = max(max_pos_err, pos_err)
                max_vel_err = max(max_vel_err, vel_err)

                if not (pos_pass and vel_pass):
                    all_passed = False

                res = BenchmarkResult(
                    sat_name=case["name"],
                    norad_id=case["norad_id"],
                    offset_min=offset_min,
                    r_calc_teme=r_calc,
                    v_calc_teme=v_calc,
                    r_ref_teme=r_ref,
                    v_ref_teme=v_ref,
                    pos_err_km=pos_err,
                    vel_err_kms=vel_err,
                    pos_passed=pos_pass,
                    vel_passed=vel_pass
                )
                results.append(res)

        logger.info(
            f"Tier 1 Vallado Benchmark Suite complete ({len(results)} vectors). "
            f"Max Pos Err: {max_pos_err:.3e} km, Max Vel Err: {max_vel_err:.3e} km/s. "
            f"All Passed: {all_passed}"
        )
        return results, max_pos_err, max_vel_err, all_passed
