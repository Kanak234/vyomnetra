"""Phase 7 REST API, Health Endpoints & SDK Integration Tests.

Validates FastAPI endpoints (/health, /readiness, /satellites, /conjunctions, /query, /pass-schedule, /space-weather, /metrics)
and the Python SDK SSAPlatform interface.
"""

from fastapi.testclient import TestClient
import pytest

from vyomnetra.api.app import app
from vyomnetra.sdk import SSAPlatform

client = TestClient(app)


def test_api_health_endpoint():
    """Tests /health liveness probe."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_api_readiness_endpoint():
    """Tests /readiness probe checking datastore."""
    resp = client.get("/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ready", "degraded")
    assert "total_satellites" in data


def test_api_satellites_endpoint():
    """Tests /satellites catalogue endpoint."""
    resp = client.get("/satellites?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_api_conjunctions_endpoint():
    """Tests /conjunctions screening endpoint."""
    resp = client.get("/conjunctions?duration_hours=12")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data


def test_api_query_endpoint():
    """Tests /query natural language endpoint."""
    resp = client.post("/query", json={"prompt": "What satellite passes exist over Hazaribagh?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "cot_plan_text" in data
    assert "final_answer" in data


def test_api_pass_schedule_endpoint():
    """Tests /pass-schedule endpoint."""
    resp = client.get("/pass-schedule?site_key=hazaribagh")
    assert resp.status_code == 200
    data = resp.json()
    assert "passes" in data


def test_api_space_weather_endpoint():
    """Tests /space-weather endpoint."""
    resp = client.get("/space-weather")
    assert resp.status_code == 200
    data = resp.json()
    assert "f10_7_index" in data


def test_api_prometheus_metrics():
    """Tests /metrics endpoint for Prometheus exposition format."""
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "vyomnetra_satellites_total" in resp.text
    assert "vyomnetra_conjunctions_total" in resp.text


def test_python_sdk_interface():
    """Tests high-level SSAPlatform SDK wrapper."""
    platform = SSAPlatform()
    sats = platform.get_satellites()
    assert isinstance(sats, list)

    sw = platform.get_space_weather()
    assert sw.f10_7_index > 0

    val_res = platform.run_validation()
    assert len(val_res) == 5
