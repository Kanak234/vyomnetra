"""Pytest configuration and shared fixtures for VYOMNETRA."""

import os
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    """Provides offscreen Qt Application instance for PySide6 tests."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provides temporary directory for testing data outputs."""
    return tmp_path / "vyomnetra_test_data"
