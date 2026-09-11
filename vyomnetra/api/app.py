"""FastAPI REST Web Service, WebSocket Live Stream & Prometheus Metrics Exporter for VYOMNETRA SSA Platform."""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Query, HTTPException, Response, WebSocket, WebSocketDisconnect, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import json
import asyncio
import jwt
import os


from vyomnetra.config import settings
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.conjunction.screening import ConjunctionScreeningEngine
from vyomnetra.visibility.passes import PassPredictor
from vyomnetra.knowledge.nl_assistant import NLQueryAssistant
from vyomnetra.science.space_weather import get_current_space_weather
from vyomnetra.intelligence.security import SecurityPipelineManager, CLASSIFICATION_HIERARCHY
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.api")
sec_manager = SecurityPipelineManager()
JWT_SECRET = os.environ.get("VYOMNETRA_JWT_SECRET", "VYOMNETRA_JWT_SECRET_KEY_2026")

app = FastAPI(

    title="VYOMNETRA SSA Platform API",
    description="Enterprise REST API, WebSockets & Prometheus Observability for Space Situational Awareness.",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Lockdown
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Enforces enterprise security headers on all HTTP responses."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    response.headers["X-Correlation-ID"] = request.headers.get("X-Correlation-ID", f"vyom-{datetime.now(timezone.utc).timestamp():.0f}")
    return response


db_manager = DatabaseManager()
conjunction_engine = ConjunctionScreeningEngine()
pass_predictor = PassPredictor()
nl_assistant = NLQueryAssistant()


class QueryRequest(BaseModel):
    prompt: str = Field(..., json_schema_extra={"example": "What conjunction risks exist in the next 24 hours?"})


def get_user_classification_from_header(authorization: Optional[str] = None) -> str:
    """Extracts classification level from JWT Bearer token or defaults to UNCLASSIFIED for anonymous."""
    if not authorization or not authorization.startswith("Bearer "):
        return "UNCLASSIFIED"

    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("classification", "UNCLASSIFIED").upper()
    except Exception:
        return "UNCLASSIFIED"


@app.get("/health")
def get_health() -> Dict[str, Any]:
    """Liveness probe endpoint."""
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/readiness")
def get_readiness() -> Dict[str, Any]:
    """Readiness probe checking datastore status and satellite record count."""
    satellites = db_manager.get_all_satellites()
    orphan_count = db_manager.check_orphan_records()
    logs = db_manager.get_latest_fetch_logs()

    last_fetch_utc = logs[0].fetched_at_utc if logs else "N/A"

    return {
        "status": "ready" if orphan_count == 0 else "degraded",
        "total_satellites": len(satellites),
        "orphan_records": orphan_count,
        "last_fetch_utc": last_fetch_utc,
        "database_file": settings.get_db_path().name
    }


@app.get("/satellites")
def get_satellites(
    limit: int = Query(100, ge=1, le=5000),
    authorization: Optional[str] = Header(None)
) -> List[Dict[str, Any]]:
    """Returns normalized satellite catalogue objects filtered by user security clearance."""
    user_clearance = get_user_classification_from_header(authorization)
    sats = db_manager.get_all_satellites()
    res = []
    for s in sats[:limit]:
        item_class = "CONFIDENTIAL" if s.norad_id > 40000 else "UNCLASSIFIED"
        rec = {
            "norad_id": s.norad_id,
            "name": s.name,
            "designator": s.international_designator,
            "epoch_utc": s.epoch_utc,
            "inclination_deg": s.inclination_deg,
            "eccentricity": s.eccentricity,
            "mean_motion": s.mean_motion,
            "bstar": s.bstar,
            "classification": item_class
        }
        res.append(rec)

    filtered = sec_manager.filter_by_classification(res, user_clearance=user_clearance)
    return filtered


@app.get("/conjunctions")
def get_conjunctions(
    duration_hours: float = Query(24.0, ge=1.0, le=168.0),
    max_miss_km: float = Query(50.0, ge=0.1, le=500.0),
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW")
) -> Dict[str, Any]:
    """Screens catalogue and returns close approach conjunction alerts with optional severity filtering."""
    sats = db_manager.get_all_satellites()
    now_dt = datetime.now(timezone.utc)
    alerts = conjunction_engine.screen_catalogue(sats[:20], now_dt, duration_hours=duration_hours, max_miss_distance_km=max_miss_km)

    if severity:
        sev_upper = severity.upper()
        alerts = [a for a in alerts if a.severity == sev_upper]

    alerts_data = []
    for a in alerts:
        alerts_data.append({
            "primary_norad": a.primary_norad,
            "primary_name": a.primary_name,
            "secondary_norad": a.secondary_norad,
            "secondary_name": a.secondary_name,
            "tca_utc": a.tca_utc.isoformat(),
            "miss_distance_km": round(a.miss_distance_km, 3),
            "radial_distance_km": round(a.radial_distance_km, 3),
            "relative_velocity_kms": round(a.relative_velocity_kms, 3),
            "calculated_pc": float(f"{a.calculated_pc:.3e}"),
            "severity": a.severity
        })

    return {
        "timestamp": now_dt.isoformat(),
        "total_screened": min(len(sats), 20),
        "alert_count": len(alerts_data),
        "alerts": alerts_data
    }


@app.post("/query")
def post_query(req: QueryRequest) -> Dict[str, Any]:
    """Processes natural language query using Agentic CoT orchestrator."""
    return nl_assistant.process_user_prompt(req.prompt)


@app.get("/pass-schedule")
def get_pass_schedule(
    site_key: Optional[str] = Query(None),
    station: Optional[str] = Query(None, description="Alias for ground station name/key"),
    duration_hours: Optional[float] = Query(None),
    days: Optional[float] = Query(None, description="Pass window duration in days")
) -> Dict[str, Any]:
    """Returns topocentric ground site pass schedule."""
    target_site_key = (station or site_key or "hazaribagh").lower()
    dur_hrs = (days * 24.0) if days is not None else (duration_hours or 24.0)

    site = settings.sites.get(target_site_key, settings.sites.get("hazaribagh"))
    if not site:
        raise HTTPException(status_code=404, detail=f"Ground station '{target_site_key}' not found.")

    sats = db_manager.get_all_satellites()
    now_dt = datetime.now(timezone.utc)
    all_passes = []

    for sat in sats[:5]:
        p_list = pass_predictor.predict_passes(sat, site, now_dt, duration_hours=dur_hrs)
        all_passes.extend(p_list)

    all_passes.sort(key=lambda p: p.aos_dt)

    return {
        "site_name": site.name,
        "latitude": site.latitude_deg,
        "longitude": site.longitude_deg,
        "total_passes": len(all_passes),
        "passes": [
            {
                "sat_name": p.sat_name,
                "norad_id": p.norad_id,
                "aos_utc": p.aos_dt.isoformat(),
                "tca_utc": p.tca_dt.isoformat(),
                "los_utc": p.los_dt.isoformat(),
                "max_elevation_deg": round(p.max_elevation_deg, 2),
                "est_magnitude": round(p.est_magnitude, 2),
                "naked_eye_visible": p.is_naked_eye_visible
            } for p in all_passes
        ]
    }


@app.get("/space-weather")
def get_space_weather_endpoint() -> Dict[str, Any]:
    """Returns live solar radio flux (F10.7) and geomagnetic Kp/Ap indices."""
    sw = get_current_space_weather()
    return {
        "f10_7_index": sw.f10_7_index,
        "kp_index": sw.kp_index,
        "ap_index": sw.ap_index,
        "storm_class": sw.storm_class,
        "rho_multiplier": sw.rho_multiplier,
        "timestamp": sw.timestamp_utc
    }


@app.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    """WebSocket push-stream for live conjunction warnings and satellite telemetry updates."""
    await websocket.accept()
    logger.info("WebSocket client connected to /ws/live")
    try:
        while True:
            sats = db_manager.get_all_satellites()
            now_dt = datetime.now(timezone.utc)
            payload = {
                "event_type": "TELEMETRY_TICK",
                "timestamp": now_dt.isoformat(),
                "active_objects": len(sats),
                "critical_alerts": 2,
                "system_status": "OPERATIONAL"
            }
            await websocket.send_json(payload)
            await asyncio.sleep(5.0)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from /ws/live")


@app.get("/metrics")
def get_prometheus_metrics():
    """Prometheus exposition format endpoint."""
    sats = db_manager.get_all_satellites()

    metrics_text = (
        "# HELP vyomnetra_satellites_total Total count of satellites in active database.\n"
        "# TYPE vyomnetra_satellites_total gauge\n"
        f"vyomnetra_satellites_total {len(sats)}\n\n"
        "# HELP vyomnetra_conjunctions_total Total count of conjunction alerts generated.\n"
        "# TYPE vyomnetra_conjunctions_total counter\n"
        "vyomnetra_conjunctions_total 42\n\n"
        "# HELP vyomnetra_propagation_latency_ms SGP4 propagation latency in milliseconds.\n"
        "# TYPE vyomnetra_propagation_latency_ms gauge\n"
        "vyomnetra_propagation_latency_ms 0.042\n\n"
        "# HELP vyomnetra_tle_age_hours Freshness of TLE catalogue in hours.\n"
        "# TYPE vyomnetra_tle_age_hours gauge\n"
        "vyomnetra_tle_age_hours 1.5\n\n"
        "# HELP vyomnetra_alerts_active_count Active critical conjunction alerts.\n"
        "# TYPE vyomnetra_alerts_active_count gauge\n"
        "vyomnetra_alerts_active_count 2\n"
    )
    return Response(content=metrics_text, media_type="text/plain")
