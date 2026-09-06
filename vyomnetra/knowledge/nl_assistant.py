"""VYOMNETRA Knowledge Graph & Natural Language Query Assistant.

Parses freeform domain queries across 50+ intent patterns, integrates local knowledge base,
and routes to the SSA Agent Orchestrator for verifiable CoT execution with graceful fallback.
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from vyomnetra.orchestrator.cot_engine import SSAAgentOrchestrator, CoTExecutionResult
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.knowledge.nl_assistant")

# 50+ Natural Language Intent Patterns
INTENT_PATTERNS: List[Tuple[str, str]] = [
    # Conjunction & Collision Assessment (1-10)
    (r"\b(conjunction|conjunctions)\b", "CONJUNCTION_SCREENING"),
    (r"\b(collision|collisions|impact)\b", "CONJUNCTION_SCREENING"),
    (r"\b(close approach|close-approach|proximity encounter)\b", "CONJUNCTION_SCREENING"),
    (r"\b(miss distance|radial distance|in-track|cross-track)\b", "CONJUNCTION_SCREENING"),
    (r"\b(foster 2d|probability of collision|pc calculation)\b", "CONJUNCTION_SCREENING"),
    (r"\b(tca|time of closest approach)\b", "CONJUNCTION_SCREENING"),
    (r"\b(ric frame|rtn frame|covariance)\b", "CONJUNCTION_SCREENING"),
    (r"\b(critical alert|collision risk|threat warning)\b", "CONJUNCTION_SCREENING"),
    (r"\b(satellite pair|space debris collision)\b", "CONJUNCTION_SCREENING"),
    (r"\b(screening window|24h conjunctions)\b", "CONJUNCTION_SCREENING"),

    # Ground Station Pass Predictions & Illumination (11-20)
    (r"\b(pass|passes|pass schedule|pass prediction)\b", "PASS_PREDICTION"),
    (r"\b(hazaribagh|hazaribag|ground station)\b", "PASS_PREDICTION"),
    (r"\b(istrac|bengaluru|bangalore)\b", "PASS_PREDICTION"),
    (r"\b(sdsc|sriharikota|shar)\b", "PASS_PREDICTION"),
    (r"\b(aos|tca|los|rise time|set time)\b", "PASS_PREDICTION"),
    (r"\b(max elevation|elevation angle|slant range)\b", "PASS_PREDICTION"),
    (r"\b(visual magnitude|naked eye|naked-eye)\b", "PASS_PREDICTION"),
    (r"\b(sunlit|eclipsed|twilight|illumination)\b", "PASS_PREDICTION"),
    (r"\b(visible tonight|optical observation|overhead pass)\b", "PASS_PREDICTION"),
    (r"\b(topocentric|azimuth|az/el)\b", "PASS_PREDICTION"),

    # Orbit Decay & Re-Entry Windows (21-30)
    (r"\b(decay|orbit decay|atmospheric drag)\b", "ORBIT_DECAY"),
    (r"\b(reentry|re-entry|re entry|deorbit)\b", "ORBIT_DECAY"),
    (r"\b(lifetime|remaining lifetime|orbital lifetime)\b", "ORBIT_DECAY"),
    (r"\b(semi-major axis decay|da/dt)\b", "ORBIT_DECAY"),
    (r"\b(bstar|drag coefficient|ballistic coefficient)\b", "ORBIT_DECAY"),
    (r"\b(perigee|apogee|altitude decay)\b", "ORBIT_DECAY"),
    (r"\b(re-entry risk|reentry window|confidence interval)\b", "ORBIT_DECAY"),
    (r"\b(leo decay|uncontrolled reentry)\b", "ORBIT_DECAY"),
    (r"\b(upper stage debris decay|rocket body decay)\b", "ORBIT_DECAY"),
    (r"\b(exosphere density decay|atmosphere scale height)\b", "ORBIT_DECAY"),

    # Space Weather & Atmospheric Physics (31-40)
    (r"\b(space weather|solar flux|f10\.7|f107)\b", "SPACE_WEATHER"),
    (r"\b(kp index|ap index|geomagnetic storm)\b", "SPACE_WEATHER"),
    (r"\b(harris-priester|jacchia|atmospheric density)\b", "SPACE_WEATHER"),
    (r"\b(solar activity|solar max|noaa swpc)\b", "SPACE_WEATHER"),
    (r"\b(g1|g2|g3|g4|g5|geomagnetic storm class)\b", "SPACE_WEATHER"),
    (r"\b(density multiplier|upper atmosphere heating)\b", "SPACE_WEATHER"),
    (r"\b(ionosphere|thermosphere density)\b", "SPACE_WEATHER"),
    (r"\b(solar radio flux|geomagnetic index)\b", "SPACE_WEATHER"),
    (r"\b(space weather forecast|solar flare impact)\b", "SPACE_WEATHER"),
    (r"\b(noaa fetch|space weather state)\b", "SPACE_WEATHER"),

    # Intelligence, Maneuvers & Threat Assessment (41-50)
    (r"\b(maneuver|maneuvers|orbital maneuver)\b", "INTELLIGENCE_THREAT"),
    (r"\b(rpo|rendezvous|proximity operations)\b", "INTELLIGENCE_THREAT"),
    (r"\b(co-orbital|co orbital|inspector satellite)\b", "INTELLIGENCE_THREAT"),
    (r"\b(threat|threat score|threat assessment)\b", "INTELLIGENCE_THREAT"),
    (r"\b(classification|unclassified|secret|top secret)\b", "INTELLIGENCE_THREAT"),
    (r"\b(delta-v|delta v|mean motion shift)\b", "INTELLIGENCE_THREAT"),
    (r"\b(adversarial|satellite anomaly|bstar jump)\b", "INTELLIGENCE_THREAT"),
    (r"\b(defense ops|security clearance|hmac signature)\b", "INTELLIGENCE_THREAT"),
    (r"\b(bah|bharatiya antariksh hackathon)\b", "INTELLIGENCE_THREAT"),
    (r"\b(validation|benchmarks|vallado|sgp4-ver)\b", "INTELLIGENCE_THREAT"),
]


class NLQueryAssistant:
    """Natural Language Assistant for SSA queries supporting 50+ intent patterns with graceful fallback."""

    def __init__(self, orchestrator: Optional[SSAAgentOrchestrator] = None):
        self.orchestrator = orchestrator or SSAAgentOrchestrator()

    def classify_intent(self, prompt: str) -> str:
        """Classifies query into intent category based on 50+ natural language patterns."""
        p_lower = prompt.lower()
        for pattern, intent in INTENT_PATTERNS:
            if re.search(pattern, p_lower):
                return intent
        return "UNKNOWN_FALLBACK"

    def process_user_prompt(self, prompt: str) -> Dict[str, Any]:
        """Executes natural language query pipeline and returns formatted dict response."""
        intent = self.classify_intent(prompt)
        logger.info(f"Classified prompt intent: '{intent}' for query: '{prompt}'")

        result: CoTExecutionResult = self.orchestrator.process_query(prompt)

        steps_rendered = []
        for s in result.thought_plan:
            steps_rendered.append(
                f"Step {s.step_number}: [{s.status}] Tool `{s.tool_name}`\n"
                f"  Rationale: {s.rationale}\n"
                f"  Output: {s.output_summary}"
            )

        steps_text = "\n\n".join(steps_rendered)

        return {
            "query": result.user_query,
            "detected_intent": intent,
            "cot_plan_text": steps_text,
            "final_answer": result.final_answer,
            "lineage_hash": result.data_lineage_hash,
            "timestamp": result.executed_at_utc.isoformat()
        }
