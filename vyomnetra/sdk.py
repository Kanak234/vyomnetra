"""VYOMNETRA Space Situational Awareness Python SDK.

Provides high-level Pythonic interface for SSA operations:
>>> import vyomnetra
>>> platform = vyomnetra.SSAPlatform()
>>> sats = platform.get_satellites()
>>> alerts = platform.screen_conjunctions()
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.conjunction.screening import ConjunctionScreeningEngine, ConjunctionAlert
from vyomnetra.visibility.passes import PassPredictor, PredictedPass
from vyomnetra.decay.decay_engine import OrbitDecayEngine, OrbitDecayEstimate
from vyomnetra.knowledge.nl_assistant import NLQueryAssistant
from vyomnetra.science.space_weather import get_current_space_weather
from vyomnetra.validate.harness import MultiTierValidationHarness
from vyomnetra.config import settings


class SSAPlatform:
    """Unified Python SDK interface for the VYOMNETRA SSA Platform."""

    def __init__(self, db_path: Optional[str] = None):
        self.db = DatabaseManager()
        self.conjunction_engine = ConjunctionScreeningEngine()
        self.pass_predictor = PassPredictor()
        self.decay_engine = OrbitDecayEngine()
        self.nl_assistant = NLQueryAssistant()
        self.harness = MultiTierValidationHarness()

    def get_satellites(self) -> List[Any]:
        """Returns all satellite records currently stored in local database."""
        return self.db.get_all_satellites()

    def screen_conjunctions(
        self,
        duration_hours: float = 24.0,
        max_miss_distance_km: float = 50.0
    ) -> List[ConjunctionAlert]:
        """Runs SGP4 candidate pair spatial screening and Foster 2D Pc calculation."""
        satellites = self.get_satellites()
        now_dt = datetime.now(timezone.utc)
        return self.conjunction_engine.screen_catalogue(
            satellites, start_dt=now_dt, duration_hours=duration_hours, max_miss_distance_km=max_miss_distance_km
        )

    def predict_passes(
        self,
        site_name: str = "hazaribagh",
        duration_hours: float = 24.0,
        min_elevation_deg: float = 10.0
    ) -> List[PredictedPass]:
        """Predicts topocentric passes over specified ground station."""
        site = settings.sites.get(site_name.lower(), settings.sites.get("hazaribagh"))
        satellites = self.get_satellites()
        now_dt = datetime.now(timezone.utc)
        all_passes = []
        for sat in satellites[:5]:
            p_list = self.pass_predictor.predict_passes(
                sat, site, start_dt=now_dt, duration_hours=duration_hours, min_elevation_deg=min_elevation_deg
            )
            all_passes.extend(p_list)
        all_passes.sort(key=lambda p: p.aos_dt)
        return all_passes

    def estimate_orbit_decay(self, sat_record: Any) -> OrbitDecayEstimate:
        """Estimates LEO drag decay rate and remaining orbital lifetime."""
        return self.decay_engine.estimate_lifetime(sat_record)

    def query(self, prompt: str) -> Dict[str, Any]:
        """Executes natural language query via Chain-of-Thought orchestrator."""
        return self.nl_assistant.process_user_prompt(prompt)

    def get_space_weather(self) -> Any:
        """Returns current solar radio flux and geomagnetic Kp/Ap storm indices."""
        return get_current_space_weather()

    def run_validation(self) -> List[Any]:
        """Executes full 5-tier system validation suite."""
        satellites = self.get_satellites()
        return self.harness.run_all_tiers(satellites)
