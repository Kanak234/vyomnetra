"""BAH Conjunction Screening Capability Module Implementation."""

from typing import Dict, Any
from vyomnetra.bah.framework import CapabilityModule, CapabilityMetadata
from vyomnetra.conjunction.screening import ConjunctionScreeningEngine
from vyomnetra.ingest.db import DatabaseManager


class ConjunctionScreeningModule(CapabilityModule):
    """BAH Capability wrapping Conjunction Screening Engine."""

    def __init__(self):
        meta = CapabilityMetadata(
            module_id="bah.capability.conjunction",
            name="Conjunction Screening Capability",
            version="1.0.0",
            author="VYOMNETRA",
            description="High-performance spatial screening and close-approach warnings."
        )
        super().__init__(meta)
        self.engine = None
        self.db = None

    def initialize(self, config: Dict[str, Any]) -> bool:
        self.engine = ConjunctionScreeningEngine()
        self.db = DatabaseManager()
        self.is_initialized = True
        return True

    def execute(self, input_payload: Dict[str, Any]) -> Dict[str, Any]:
        dur = input_payload.get("duration_hours", 24.0)
        max_miss = input_payload.get("max_miss_km", 50.0)
        sats = self.db.get_all_satellites()
        from datetime import datetime, timezone
        alerts = self.engine.screen_catalogue(sats[:20], start_dt=datetime.now(timezone.utc), duration_hours=dur, max_miss_distance_km=max_miss)
        return {
            "module_id": self.metadata.module_id,
            "status": "SUCCESS",
            "alert_count": len(alerts),
            "alerts": [
                {
                    "primary": a.primary_name,
                    "secondary": a.secondary_name,
                    "miss_km": a.miss_distance_km,
                    "severity": a.severity
                } for a in alerts
            ]
        }

    def shutdown(self) -> bool:
        self.is_initialized = False
        return True
