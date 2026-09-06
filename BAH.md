# 🇮🇳 Bharatiya Antariksh Hackathon (BAH) Extensibility Framework

VYOMNETRA includes native support for running and testing Bharatiya Antariksh Hackathon problem statements across 2024, 2025, and 2026 problem tracks.

---

## Supported Problem Statements

1. **BAH-2024-DEBRIS**: Debris Re-entry Window & Impact Area Estimator. Predicts $da/dt$ drag decay and remaining orbital lifetime.
2. **BAH-2025-CONSTELLATION**: Mega-Constellation Conjunction Avoidance Scheduler. Screens candidate pairs and computes Foster 2D $P_c$.
3. **BAH-2026-RPO-THREAT**: Adversarial Co-Orbital RPO & Inspection Detection. Flags un-announced proximity operations within $50\text{ km}$.
4. **BAH-2026-SPACE-WEATHER**: Geomagnetic Storm Atmospheric Drag Impact. Models atmospheric density spikes during $G_4$/$G_5$ solar storms.

---

## Execution Example

```python
from vyomnetra.bah.framework import BAHFrameworkRunner
from vyomnetra.ingest.db import DatabaseManager

runner = BAHFrameworkRunner()
db = DatabaseManager()
satellites = db.get_all_satellites()

# Execute BAH 2024 Debris Module
report = runner.execute_problem_statement("BAH-2024-DEBRIS", satellites)
print(report)
```
