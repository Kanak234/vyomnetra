"""SGP4/SDP4 Orbit Propagation Engine.

Wraps sgp4.api.Satrec for high-precision TEME state vector computation
and vectorized batch propagation.
"""

from typing import List, Tuple, Optional, Union
import numpy as np
from sgp4.api import Satrec, WGS72, WGS84, jday

from vyomnetra.utils.logger import get_logger
from vyomnetra.ingest.models import SatelliteRecord

logger = get_logger("vyomnetra.propagate.engine")


class SGP4Engine:
    """High-precision analytical SGP4/SDP4 propagation engine."""

    def __init__(self, gravity_model=WGS72):
        self.gravity_model = gravity_model

    def create_satrec(
        self,
        tle_line1: Optional[str] = None,
        tle_line2: Optional[str] = None,
        sat_record: Optional[SatelliteRecord] = None
    ) -> Satrec:
        """Instantiates an SGP4 Satrec instance from raw TLE lines or a normalized SatelliteRecord."""
        if tle_line1 and tle_line2:
            return Satrec.twoline2rv(tle_line1, tle_line2, self.gravity_model)

        if sat_record:
            if sat_record.raw_tle_line1 and sat_record.raw_tle_line2:
                return Satrec.twoline2rv(sat_record.raw_tle_line1, sat_record.raw_tle_line2, self.gravity_model)

            # Reconstruct Satrec from normalized OMM elements
            dt = sat_record.get_epoch_dt()
            year = dt.year
            mon = dt.month
            day = dt.day
            hr = dt.hour
            minute = dt.minute
            sec = dt.second + dt.microsecond * 1e-6
            jd, fr = jday(year, mon, day, hr, minute, sec)

            satrec = Satrec()
            satrec.sgp4init(
                self.gravity_model,
                'i',
                sat_record.norad_id,
                jd + fr - 2433281.5,
                sat_record.bstar,
                sat_record.mean_motion_dot,
                sat_record.mean_motion_ddot,
                sat_record.eccentricity,
                np.radians(sat_record.arg_perigee_deg),
                np.radians(sat_record.inclination_deg),
                np.radians(sat_record.mean_anomaly_deg),
                sat_record.mean_motion * (2.0 * np.pi / 1440.0),
                np.radians(sat_record.raan_deg),
            )
            return satrec

        raise ValueError("Must provide either raw TLE lines or a valid SatelliteRecord.")

    def propagate_single(
        self,
        satrec: Satrec,
        jd: float,
        fr: float
    ) -> Tuple[int, np.ndarray, np.ndarray]:
        """Propagates a single satellite to Julian Date (jd + fr).
        
        Returns: (error_code, position_km_teme, velocity_kms_teme)
        """
        e, r, v = satrec.sgp4(jd, fr)
        return e, np.array(r, dtype=np.float64), np.array(v, dtype=np.float64)

    def propagate_batch(
        self,
        satrecs: List[Satrec],
        jd: float,
        fr: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Propagates a batch of N satellites to a common Julian Date (jd + fr).
        
        Returns:
            errors: (N,) int array
            positions: (N, 3) float64 array of TEME positions in km
            velocities: (N, 3) float64 array of TEME velocities in km/s
        """
        n_sats = len(satrecs)
        errors = np.zeros(n_sats, dtype=np.int32)
        positions = np.zeros((n_sats, 3), dtype=np.float64)
        velocities = np.zeros((n_sats, 3), dtype=np.float64)

        for idx, sat in enumerate(satrecs):
            e, r, v = sat.sgp4(jd, fr)
            errors[idx] = e
            if e == 0:
                positions[idx] = r
                velocities[idx] = v

        return errors, positions, velocities

    def propagate_time_series(
        self,
        satrec: Satrec,
        jds: np.ndarray,
        frs: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Vectorized propagation of a single satellite across M time steps using Satrec.sgp4_array().
        
        Returns:
            errors: (M,) int array
            positions: (M, 3) float64 array in TEME km
            velocities: (M, 3) float64 array in TEME km/s
        """
        e, r, v = satrec.sgp4_array(jds, frs)
        return e, np.array(r, dtype=np.float64), np.array(v, dtype=np.float64)
