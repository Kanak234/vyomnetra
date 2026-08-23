# VYOMNETRA (व्योमनेत्र)

> **Offline-first Desktop Space Situational Awareness (SSA) & Space-Science Workbench**

VYOMNETRA is a high-precision, desktop SSA workbench built on PySide6, SGP4/SDP4 orbit propagation, Skyfield/Astropy astronomical tools, NetworkX/RDFLib knowledge graph, and local Ollama LLM integration.

## Features
- **Offline-First Data Acquisition & Provenance**: Local caching with SHA-256 audit logs and data health metrics.
- **Precision Propagation**: SGP4/SDP4 implementation verified against Vallado benchmark test vectors.
- **Pass Prediction**: Visual magnitude, sunlit states, and topocentric passes over Indian sites (Hazaribagh, ISTRAC, SDSC, NRSC).
- **Conjunction Screening**: 3-stage filter chain + Brent TCA refinement + Foster 2D Collision Probability.
- **Space Science**: Light curve detrending and Box Least Squares transit search pipeline.
- **Local Knowledge Graph & CoT Orchestrator**: NL query interface over RDF graph and step-by-step tool planner via Ollama.

## Setup & Running

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
vyomnetra
```
