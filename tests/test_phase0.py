"""Phase 0 Verification Tests for VYOMNETRA.

Every test here has explicit numeric, structural, or version assertions
to guarantee offline reproducibility and frame-conversion integrity.
"""

import json
import tomllib
from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vyomnetra.config import settings, get_installed_stack_versions
from vyomnetra.utils.checksum import compute_sha256, verify_tle_checksum
from vyomnetra.utils.logger import log_data_fetch
from vyomnetra.ui.app import MainWindow


def test_locked_dependency_versions():
    """Asserts running runtime versions match exact versions in uv.lock.
    
    Parses uv.lock dynamically so uv.lock remains the single source of truth.
    """
    lock_path = Path("uv.lock")
    assert lock_path.exists(), "uv.lock file missing! Must be committed to repo."
    
    with open(lock_path, "rb") as f:
        lock_data = tomllib.load(f)
        
    locked_packages = {pkg["name"]: pkg["version"] for pkg in lock_data.get("package", [])}
    installed = get_installed_stack_versions()
    
    packages_to_check = [
        "sgp4", "skyfield", "astropy", "numpy", "scipy",
        "pandas", "pyside6", "pyqtgraph", "networkx",
        "rdflib", "requests", "pytest", "pydantic"
    ]
    
    for pkg in packages_to_check:
        assert pkg in locked_packages, f"Package '{pkg}' not found in uv.lock!"
        expected_version = locked_packages[pkg]
        assert installed[pkg] == expected_version, (
            f"Dependency version mismatch! Package '{pkg}' is running version '{installed[pkg]}', "
            f"expected locked version '{expected_version}' from uv.lock."
        )


def test_config_settings():
    """Asserts global settings schema, ground site coordinates, and database path resolution."""
    assert settings.app_name == "VYOMNETRA"
    
    # Explicit ground station coordinates
    hz = settings.sites["hazaribagh"]
    assert hz.latitude_deg == 23.9968
    assert hz.longitude_deg == 85.3647
    assert hz.elevation_m == 610.0
    
    # ISRO site presets
    assert "istrac_bengaluru" in settings.sites
    assert "sdsc_sriharikota" in settings.sites
    assert "nrsc_hyderabad" in settings.sites
    
    db_path = settings.get_db_path()
    assert db_path.name == "vyomnetra.db"


def test_checksum_utilities():
    """Asserts SHA-256 string hashing and standard 69-character TLE line modulo-10 checksum algorithm."""
    text = "VYOMNETRA_SSA_ENGINE"
    expected_hash = "426f3897e905cdb6e7955da0d011ab7125c4c23dd028cfcaa7054cd1b86e81eb"
    assert compute_sha256(text) == expected_hash

    # Standard valid 69-character ISS TLE Line 1 (checksum 0) and Line 2 (checksum 9)
    tle_line1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9990"
    tle_line2 = "2 25544  51.6400 208.9163 0004817  93.7377 266.4950 15.49575918432389"
    
    assert verify_tle_checksum(tle_line1) is True
    assert verify_tle_checksum(tle_line2) is True
    
    # Corrupted TLE line checksum assertion
    corrupt_line = "1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9995"
    assert verify_tle_checksum(corrupt_line) is False


def test_structured_logging(tmp_path, monkeypatch):
    """Asserts structured audit logging outputs exact JSONL provenance records to local disk."""
    test_data_dir = tmp_path / "vyomnetra_data"
    monkeypatch.setattr(settings, "data_dir", test_data_dir)
    test_logs_dir = settings.get_logs_dir()
    
    source_url = "https://celestrak.org/NORAD/elements/gp.php"
    content = "test_tle_payload"
    c_hash = compute_sha256(content)
    
    audit_entry = log_data_fetch(
        source_name="CelesTrak GP Test",
        source_url=source_url,
        record_count=42,
        content_hash=c_hash,
        status="SUCCESS"
    )
    
    jsonl_file = test_logs_dir / "audit_provenance.jsonl"
    assert jsonl_file.exists()
    
    with open(jsonl_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) >= 1
        record = json.loads(lines[-1])
        assert record["source_name"] == "CelesTrak GP Test"
        assert record["source_url"] == source_url
        assert record["record_count"] == 42
        assert record["content_hash"] == c_hash
        assert record["status"] == "SUCCESS"


def test_pytest_qt_headless_app_smoke(qapp, qtbot):
    """Smoke test asserting PySide6 main window instantiation, title, tab layout, and status bar offscreen."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    
    assert window is not None
    assert "VYOMNETRA" in window.windowTitle()
    assert window.tabs.count() == 8
    
    # Assert specific tab names
    tab_names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert "🌐 3D Globe" in tab_names[0]
    assert "📡 Catalogue" in tab_names[1]
    assert "⚠️ Conjunctions" in tab_names[2]
    assert "🔭 Pass Planner" in tab_names[3]
    assert "🧠 NL Assistant & CoT" in tab_names[4]
    assert "🔬 Space Science" in tab_names[5]
    assert "📊 Data Health & Audit" in tab_names[6]
    assert "🧪 Validation Harness" in tab_names[7]
    
    assert window.statusBar().currentMessage().startswith("VYOMNETRA Ready")
