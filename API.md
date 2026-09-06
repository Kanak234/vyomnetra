# 🔌 VYOMNETRA OpenAPI & REST API Specification

The VYOMNETRA REST API provides programmatically accessible endpoints for satellite catalogue management, close-approach conjunction screening, topocentric pass schedules, space weather indices, and natural language agent queries.

Base URL: `http://localhost:8000`

---

## Endpoints Summary

### 1. `GET /health`
- **Description**: Liveness probe returning operational state and server timestamp.
- **Response Example**:
```json
{
  "status": "ok",
  "app_name": "VYOMNETRA",
  "version": "1.0.0",
  "timestamp": "2026-08-25T16:00:00Z"
}
```

### 2. `GET /readiness`
- **Description**: Readiness probe evaluating SQLite datastore, satellite count, and orphan record count.
- **Response Example**:
```json
{
  "status": "ready",
  "total_satellites": 25400,
  "orphan_records": 0,
  "last_fetch_utc": "2026-08-25T15:00:00Z",
  "database_file": "vyomnetra.db"
}
```

### 3. `GET /satellites`
- **Query Parameters**: `limit` (default: 100, max: 5000).
- **Description**: Fetches normalized satellite catalogue records.

### 4. `GET /conjunctions`
- **Query Parameters**: `duration_hours` (default: 24.0), `max_miss_km` (default: 50.0).
- **Description**: Performs SGP4 screening and computes Foster 2D Probability of Collision ($P_c$).

### 5. `POST /query`
- **Body**: `{"prompt": "What Starlink satellites pass over Hazaribagh tonight?"}`
- **Description**: Natural language assistant endpoint executing Chain-of-Thought tool plan.

### 6. `GET /pass-schedule`
- **Query Parameters**: `site_key` (`hazaribagh`, `istrac_bengaluru`, `sdsc_sriharikota`), `duration_hours` (default: 24.0).
- **Description**: Returns topocentric ground station visibility predictions.

### 7. `GET /space-weather`
- **Description**: Returns current solar radio flux ($F_{10.7}$), geomagnetic $K_p$/$A_p$ indices, and density multiplier.

### 8. `GET /metrics`
- **Description**: Prometheus exposition format endpoint for metrics collection (`vyomnetra_satellites_total`, `vyomnetra_conjunctions_total`, etc.).
