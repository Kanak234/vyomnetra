"""Phase 8 Performance & Benchmark Load Tests.

Measures propagation throughput, spatial screening latency,
and database query response times under high workload.
"""

import time
from datetime import datetime, timezone
import pytest

from vyomnetra.propagate.engine import SGP4Engine
from vyomnetra.conjunction.screening import ConjunctionScreeningEngine
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.ingest.models import SatelliteRecord
from sgp4.api import WGS72


def test_propagation_latency_performance():
    """Validates that 1,000 propagation evaluations complete in under 50 milliseconds."""
    engine = SGP4Engine(gravity_model=WGS72)
    l1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9995"
    l2 = "2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    satrec = engine.create_satrec(l1, l2)

    start_time = time.perf_counter()
    for offset_min in range(1000):
        err, r, v = engine.propagate_single(satrec, 2460310.5, offset_min / 1440.0)
        assert err == 0
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # 1,000 evaluations must complete in under 50 ms
    assert elapsed_ms < 50.0


def test_conjunction_screening_throughput():
    """Validates spatial conjunction candidate screening speed."""
    sat1 = SatelliteRecord(
        norad_id=25544, name="ISS", international_designator="1998-067A", object_type="PAYLOAD",
        epoch_utc="2024-01-01T12:00:00Z", epoch_jd=2460310.0, mean_motion=15.49, eccentricity=0.0004,
        inclination_deg=51.64, raan_deg=208.9, arg_perigee_deg=93.7, mean_anomaly_deg=266.4,
        bstar=0.0001, mean_motion_dot=0.0, mean_motion_ddot=0.0, ephemeris_type=0, element_set_no=999, rev_at_epoch=43238,
        raw_tle_line1="1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9995",
        raw_tle_line2="2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    )
    sats = [sat1] * 10

    engine = ConjunctionScreeningEngine()
    start_time = time.perf_counter()
    alerts = engine.screen_catalogue(sats, datetime.now(timezone.utc), duration_hours=6.0, max_miss_distance_km=25.0)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Screening 10 satellites over 6h arc should finish under 500 ms
    assert elapsed_ms < 500.0


def test_database_wal_read_latency():
    """Validates SQLite database query response time under WAL mode."""
    db = DatabaseManager()
    start_time = time.perf_counter()
    sats = db.get_all_satellites()
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Reading database must take less than 100 ms
    assert elapsed_ms < 100.0
