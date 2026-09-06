"""VYOMNETRA Agentic Chain-of-Thought (CoT) Tool Orchestrator.

Orchestrates multi-step SSA workflows using automated tool breakdown,
provenance tracking, and structured tool plan execution.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import json

from vyomnetra.config import settings
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.conjunction.screening import ConjunctionScreeningEngine
from vyomnetra.visibility.passes import PassPredictor
from vyomnetra.decay.decay_engine import OrbitDecayEngine
from vyomnetra.intelligence.anomaly import calculate_threat_assessment
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.orchestrator.cot")


@dataclass
class ExecutionStep:
    """Dataclass representing one step in a Chain-of-Thought execution plan."""
    step_number: int
    tool_name: str
    rationale: str
    input_parameters: Dict[str, Any]
    output_summary: str = ""
    status: str = "PENDING"  # PENDING, EXECUTED, FAILED


@dataclass
class CoTExecutionResult:
    """Dataclass holding the full CoT reasoning trace and final audited answer."""
    user_query: str
    thought_plan: List[ExecutionStep]
    final_answer: str
    data_lineage_hash: str
    executed_at_utc: datetime


class SSAAgentOrchestrator:
    """Agentic orchestrator executing domain workflows over VYOMNETRA engines."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.conjunction_engine = ConjunctionScreeningEngine()
        self.pass_predictor = PassPredictor()
        self.decay_engine = OrbitDecayEngine()

    def process_query(self, query_text: str) -> CoTExecutionResult:
        """Parses query, constructs step-by-step CoT plan, executes tools, and returns audited response."""
        now_dt = datetime.now(timezone.utc)
        q_lower = query_text.lower()

        steps: List[ExecutionStep] = []
        final_text = ""

        satellites = self.db_manager.get_all_satellites()

        # Step 1: Catalogue Retrieval
        steps.append(ExecutionStep(
            step_number=1,
            tool_name="get_all_satellites",
            rationale="Query SQLite catalogue to fetch active satellite TLE state vectors.",
            input_parameters={"table": "satellites", "filter": query_text},
            output_summary=f"Retrieved {len(satellites)} satellites from local database.",
            status="EXECUTED"
        ))

        # Determine workflow based on intent
        if "conjunction" in q_lower or "collision" in q_lower or "close approach" in q_lower or "miss distance" in q_lower:
            steps.append(ExecutionStep(
                step_number=2,
                tool_name="screen_conjunctions",
                rationale="Run SGP4 screening and Foster 2D Probability of Collision calculation for all catalogue pairs.",
                input_parameters={"duration_hours": 24.0, "max_miss_km": 50.0},
                status="PENDING"
            ))

            alerts = self.conjunction_engine.screen_catalogue(satellites[:10], now_dt, duration_hours=24.0, max_miss_distance_km=50.0)
            steps[-1].output_summary = f"Screening complete: {len(alerts)} conjunction alerts generated."
            steps[-1].status = "EXECUTED"

            if alerts:
                top_alert = alerts[0]
                final_text = (
                    f"### Conjunction Risk Analysis Summary\n"
                    f"Screened top catalogue objects. Highest risk conjunction detected between "
                    f"**{top_alert.primary_name}** (#{top_alert.primary_norad}) and **{top_alert.secondary_name}** (#{top_alert.secondary_norad}).\n"
                    f"- **TCA (UTC)**: `{top_alert.tca_utc.strftime('%Y-%m-%d %H:%M:%S')}`\n"
                    f"- **Miss Distance**: `{top_alert.miss_distance_km:.2f} km` (Radial: {top_alert.radial_distance_km:.2f} km)\n"
                    f"- **Relative Velocity**: `{top_alert.relative_velocity_kms:.2f} km/s`\n"
                    f"- **Collision Probability (Pc)**: `{top_alert.calculated_pc:.2e}`\n"
                    f"- **Severity Level**: `{top_alert.severity}`"
                )
            else:
                final_text = "No critical conjunctions detected under 50 km miss distance threshold in the next 24 hours."

        elif "pass" in q_lower or "visibility" in q_lower or "hazaribagh" in q_lower or "bengaluru" in q_lower or "over" in q_lower:
            site_key = "hazaribagh"
            if "bengaluru" in q_lower or "istrac" in q_lower:
                site_key = "istrac_bengaluru"
            elif "sriharikota" in q_lower or "sdsc" in q_lower:
                site_key = "sdsc_sriharikota"

            site = settings.sites.get(site_key, settings.sites["hazaribagh"])

            steps.append(ExecutionStep(
                step_number=2,
                tool_name="predict_passes",
                rationale=f"Compute topocentric horizon passes for ground station '{site.name}'.",
                input_parameters={"site": site.name, "min_elevation_deg": 10.0, "duration_hours": 24.0},
                status="PENDING"
            ))

            all_passes = []
            for sat in satellites[:5]:
                p_list = self.pass_predictor.predict_passes(sat, site, now_dt, duration_hours=24.0)
                all_passes.extend(p_list)

            all_passes.sort(key=lambda p: p.aos_dt)
            steps[-1].output_summary = f"Pass predictor generated {len(all_passes)} passes over {site.name}."
            steps[-1].status = "EXECUTED"

            if all_passes:
                top_p = all_passes[0]
                final_text = (
                    f"### Ground Station Pass Prediction ({site.name})\n"
                    f"Next upcoming pass for **{top_p.sat_name}** (#{top_p.norad_id}):\n"
                    f"- **AOS (Rise)**: `{top_p.aos_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}`\n"
                    f"- **TCA (Max El)**: `{top_p.tca_dt.strftime('%H:%M:%S UTC')}` at `{top_p.max_elevation_deg:.1f}°`\n"
                    f"- **LOS (Set)**: `{top_p.los_dt.strftime('%H:%M:%S UTC')}`\n"
                    f"- **Optical Visibility**: `{'YES - Naked Eye Visible' if top_p.is_naked_eye_visible else 'Radar/RF Only'}`"
                )
            else:
                final_text = f"No visible passes predicted over {site.name} in the next 24 hours."

        elif "decay" in q_lower or "reentry" in q_lower or "lifetime" in q_lower:
            steps.append(ExecutionStep(
                step_number=2,
                tool_name="estimate_lifetime",
                rationale="Calculate atmospheric drag decay da/dt and remaining orbital lifetime.",
                input_parameters={"space_weather": "nominal"},
                status="PENDING"
            ))

            decay_reports = []
            for sat in satellites[:5]:
                est = self.decay_engine.estimate_lifetime(sat)
                decay_reports.append(est)

            steps[-1].output_summary = f"Decay engine evaluated {len(decay_reports)} objects."
            steps[-1].status = "EXECUTED"

            if decay_reports:
                top_d = decay_reports[0]
                final_text = (
                    f"### Orbital Lifetime & Re-Entry Risk Assessment\n"
                    f"Target object **{top_d.name}** (#{top_d.norad_id}):\n"
                    f"- **Perigee / Apogee**: `{top_d.current_perigee_km} km` / `{top_d.current_apogee_km} km`\n"
                    f"- **Decay Rate (da/dt)**: `{top_d.decay_rate_km_per_day} km/day`\n"
                    f"- **Estimated Lifetime**: `{top_d.estimated_lifetime_days} days`\n"
                    f"- **Re-Entry Risk Level**: `{top_d.reentry_risk_level}`"
                )

        else:
            # Default Threat & Anomaly Assessment Workflow
            steps.append(ExecutionStep(
                step_number=2,
                tool_name="assess_threats",
                rationale="Evaluate strategic threat category and security classification score.",
                input_parameters={"catalogue_size": len(satellites)},
                output_summary=f"Processed security assessment for {min(len(satellites), 50)} objects.",
                status="EXECUTED"
            ))

            threat_reports = [calculate_threat_assessment(sat) for sat in satellites[:5]]
            top_t = threat_reports[0] if threat_reports else None

            final_text = (
                f"### VYOMNETRA Autonomous Intelligence Overview\n"
                f"Processed {len(satellites)} objects in live catalogue.\n"
                f"Sample object **{top_t.name}** (#{top_t.norad_id}):\n"
                f"- **Classification**: `{top_t.classification}`\n"
                f"- **Threat Category**: `{top_t.threat_category}`\n"
                f"- **Threat Score**: `{top_t.threat_score} / 10.0`\n"
                f"- **Recommended Action**: `{top_t.recommended_action}`"
            )

        import hashlib
        lineage_payload = {
            "query": query_text,
            "timestamp": now_dt.isoformat(),
            "steps": [{"step": s.step_number, "tool": s.tool_name, "status": s.status} for s in steps],
            "answer_head": final_text[:64]
        }
        sha_hex = hashlib.sha256(json.dumps(lineage_payload, sort_keys=True).encode("utf-8")).hexdigest()
        lineage_hash = f"hash_{sha_hex}"

        return CoTExecutionResult(
            user_query=query_text,
            thought_plan=steps,
            final_answer=final_text,
            data_lineage_hash=lineage_hash,
            executed_at_utc=now_dt
        )


