# VYOMNETRA — Architecture Decision Records (ADR Log)

## ADR-001: Offline-First Ingestion & Seed Fallback Strategy
- **Context**: External data sources (CelesTrak, NOAA SWPC, Space-Track) can suffer network outages, rate limits, or HTTP 403 blocks.
- **Decision**: Implemented an exponential backoff fetcher with strict browser-aligned User-Agent identification. On network failure or offline mode, the ingestion pipeline seamlessly falls back to a disk-cached snapshot and populates the payload with a `data_age_hours` provenance marker.
- **Consequences**: Zero application crashes due to network interruption. All data records preserve operational metadata.

## ADR-002: Epoch-Versioned TLE History & 3σ Maneuver Detection
- **Context**: Overwriting historical TLEs loses orbital drift context required for anomaly detection and relative motion classification.
- **Decision**: Implemented append-only TLE storage (`tle_history` table) with epoch versioning. Added a 30-day statistical baseline calculator that auto-raises a maneuver event when mean motion ($n$), inclination ($i$), or eccentricity ($e$) deviates beyond $3\sigma$.
- **Consequences**: Enables historical trend analysis and immediate maneuver alerts without external optical/radar tracking inputs.

## ADR-003: ISRO Asset Prioritization & Elevation Floor
- **Context**: Indian national space assets (IRS, INSAT, GSAT, Cartosat, NavIC, Chandrayaan, Aditya-L1) require critical protection.
- **Decision**: Created `vyomnetra/catalogue/isro.py` with curated NORAD IDs. Conjunction screening applies an automatic `HIGH` minimum severity floor and priority queue scheduling for all encounters involving ISRO assets.
- **Consequences**: Protects strategic assets regardless of calculated collision probability ($P_c$) dilution.

## ADR-004: Multi-Algorithm Collision Probability ($P_c$) & Stability Flagging
- **Context**: Standard 2D collision probability calculation (Foster-2D) can degrade in non-spherical or high-dilution scenarios.
- **Decision**: Implemented three independent $P_c$ calculation algorithms (Foster-2D, Alfano 2D/3D, Patera contour integration) alongside covariance growth models. If algorithm outputs diverge by $>1$ order of magnitude, the system flags the assessment as `PC_UNSTABLE` and calculates $P_c^{\text{max}}$ in the dilution region.
- **Consequences**: Provides actionable confidence bounds to operators rather than single-point estimates.

## ADR-005: Atmospheric Density Model & Re-entry Monte Carlo
- **Context**: Re-entry prediction requires accurate upper-atmosphere density modelling and solar flux uncertainty estimation.
- **Decision**: Built a hybrid density model (NRLMSISE-00 / Harris-Priester fallback) coupled with a 1,000-sample Monte Carlo simulator varying $B^*$ drag coefficients and $F_{10.7}$ solar flux. Outputs 50% and 95% confidence windows and sub-satellite ground track footprints.
- **Consequences**: Robust re-entry corridors with explicit statistical bounds.

## ADR-006: ML Anomaly Detection with Feature Explainability
- **Context**: Machine learning alerts without feature attribution cause operator distrust ("black box" problem).
- **Decision**: Implemented an Isolation Forest + rules ensemble trained on orbital element time-series features ($\Delta n, \Delta i, \Delta\Omega, B^*$). Every anomaly verdict returns a top-3 feature contribution list.
- **Consequences**: Transparent anomaly explanations for satellite operations.

## ADR-007: Cryptographic Hash-Chained Audit Logging
- **Context**: Security compliance requires tamper-evident logging of administrative and operational actions.
- **Decision**: Implemented SHA-256 hash chaining across consecutive audit log entries (`previous_hash` linked to `record_hash`). Added `verify_audit_chain()` to detect log alteration.
- **Consequences**: Cryptographically verifiable compliance and tamper resistance.

## ADR-008: 5-Tier Classification RBAC & Security hard-stops
- **Context**: Operational security requires fine-grained access control mapped to sensitivity levels.
- **Decision**: Mapped API JWT authentication to 5 security tiers (`UNCLASSIFIED`, `RESTRICTED`, `CONFIDENTIAL`, `SECRET`, `TOP_SECRET`). Anonymous access defaults strictly to `UNCLASSIFIED`.
- **Consequences**: Protects sensitive satellite catalogs and operational telemetry from unauthorized access.
