# 🚀 VYOMNETRA — Space Situational Awareness (SSA) Platform

[![CI/CD](https://github.com/Kanak234/vyomnetra/actions/workflows/ci.yml/badge.svg)](https://github.com/Kanak234/vyomnetra/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Kanak234/vyomnetra/actions/workflows/codeql.yml/badge.svg)](https://github.com/Kanak234/vyomnetra/actions/workflows/codeql.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**VYOMNETRA** is a production-grade Space Situational Awareness (SSA) platform built using Google Antigravity. It provides high-precision orbital mechanics, automated close-approach conjunction screening (Foster 2D $P_c$), multi-site topocentric pass prediction, satellite maneuver/RPO anomaly detection, space weather decay modeling, natural language agentic reasoning, and complete Bharatiya Antariksh Hackathon (BAH) problem statement execution.


---

## 🏗️ System Architecture

```
+-----------------------------------------------------------------------------------+
|                              VYOMNETRA SSA PLATFORM                                |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  +--------------------+   +-----------------------+   +------------------------+  |
|  | PySide6 GUI Shell  |   | FastAPI REST Service  |   | Python SDK Interface   |  |
|  | (8 Interactive Tabs|   | (/satellites, /query, |   | (import vyomnetra;     |  |
|  |  Zero Placeholders)|   |  /conjunctions, etc.) |   |  SSAPlatform())        |  |
|  +---------+----------+   +-----------+-----------+   +-----------+------------+  |
|            |                          |                       |                   |
|            +--------------------------+-----------------------+                   |
|                                       |                                           |
|  +------------------------------------+----------------------------------------+  |
|  |                          AGENTIC & ENGINE LAYER                             |  |
|  |                                                                             |  |
|  |  [SGP4/SDP4 Orbit Propagator]        [Conjunction Screening & Foster 2D Pc] |  |
|  |  [Topocentric Pass Predictor]        [Intelligence: Maneuver & RPO Anomaly] |  |
|  |  [Space Weather & Drag Decay]        [Chain-of-Thought Tool Orchestrator]   |  |
|  |  [5-Tier Validation Harness]         [BAH Problem Statement Runner]         |  |
|  +------------------------------------+----------------------------------------+  |
|                                       |                                           |
|  +------------------------------------+----------------------------------------+  |
|  |                         PERSISTENCE & SECURITY                              |  |
|  |                                                                             |  |
|  |  SQLite Database (WAL Mode, Foreign Key Constraints, Conjunction Audit)      |  |
|  |  Cybersecurity Layer (HMAC-SHA256 Signatures, Tiered Access Control)          |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## ⚡ 1-Minute Quickstart

### 1. Prerequisites & Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Ingest Satellite Catalogue
```bash
python scripts/verify_ingest.py
```

### 3. Run Validation Test Suite (50+ Tests)
```bash
pytest --verbose
```

### 4. Launch Application Interfaces

**Launch Desktop GUI Workbench:**
```bash
python -m vyomnetra.ui.app
```

**Launch REST API Web Service:**
```bash
uvicorn vyomnetra.api.app:app --host 0.0.0.0 --port 8000
```
Interactive OpenAPI docs available at `http://localhost:8000/docs`.

---

## 📊 Feature Maturity Matrix

| Component | Status | Verification Metric |
| :--- | :---: | :--- |
| **SGP4 Propagation** | Production | Vallado AIAA 2006-6753 $\le 10^{-6}\text{ km}$ |
| **Conjunction Screening** | Production | Foster 2D $P_c$, RIC Frame Transformation |
| **Pass Prediction** | Production | Multi-Site (Hazaribagh, ISTRAC, SDSC), Naked-Eye Mag |
| **Anomaly Intelligence** | Production | Maneuver ($\Delta n, \Delta i$), Co-Orbital RPO Classifier |
| **Space Weather & Decay**| Production | Solar Flux $F_{10.7}$, $K_p$, Harris-Priester Density |
| **Agentic CoT & NL** | Production | Tool Breakdown, Audited Lineage Hash |
| **BAH Hackathon Framework**| Production | Runners for BAH 2024, 2025, 2026 Problems |
| **Cybersecurity** | Production | HMAC-SHA256 Integrity, Tiered Access Clearance |
| **5-Tier Validation** | Production | All 5 Tiers Automated & Passing |

---

## 🐳 Docker Deployment
```bash
docker-compose up -d
```
Access points:
- REST API: `http://localhost:8000`
- Prometheus Metrics: `http://localhost:9090`
- Grafana Dashboard: `http://localhost:3000`

---

## 📜 License & Author
- **Author**: Kanak Prabhakar / Google Antigravity SSA Team
- **Project**: VYOMNETRA Space Situational Awareness Platform
