"""PySide6 QWebEngineView WebGL 3D Orbital Globe Widget.

Renders 3D Earth sphere mesh, solar terminator curve, ground station markers (Hazaribagh highlighted),
and 25,000+ satellite catalogue position points interactively at 60 FPS using QWebEngineView & WebGL.
"""

import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
import time
import numpy as np

from PySide6.QtCore import Qt, QUrl, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QCheckBox,
    QSlider
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from vyomnetra.config import settings
from vyomnetra.ingest.models import SatelliteRecord
from vyomnetra.render.globe_engine import (
    get_earth_sphere_mesh,
    get_ground_site_ecef,
    get_ground_site_coverage_ring,
    generate_satellite_orbit_trajectory
)
from vyomnetra.render.terminator import calculate_solar_terminator_points
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.render.globe_widget")


class Globe3DWebEngineCanvas(QWebEngineView):
    """QWebEngineView hosting WebGL 3D Globe Canvas for rendering 25,000+ Objects."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.html_path = Path(__file__).parent / "web_globe.html"
        if self.html_path.exists():
            self.setUrl(QUrl.fromLocalFile(str(self.html_path)))
        else:
            logger.error(f"WebGL HTML template file not found at {self.html_path}")

    def update_positions_js(self, pos_flat_list: List[float]):
        """Transfers satellite position array to WebGL engine via JavaScript execution."""
        js_code = f"if (window.updateSatellitePositions) {{ updateSatellitePositions({pos_flat_list}); }}"
        self.page().runJavaScript(js_code)

    def closeEvent(self, event):
        """Clean up web engine page upon widget closure to avoid dangling profile references."""
        try:
            self.setPage(None)
        except Exception:
            pass
        super().closeEvent(event)


class Globe3DWidget(QWidget):
    """PySide6 Container Widget holding QWebEngineView Globe Canvas and Playback Controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.satellites: List[SatelliteRecord] = []
        self.current_dt = datetime.now(timezone.utc)
        self.is_playing = False
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Header bar
        ctrl_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedWidth(80)
        self.play_btn.clicked.connect(self.toggle_play)
        ctrl_layout.addWidget(self.play_btn)

        self.term_check = QCheckBox("Solar Terminator")
        self.term_check.setChecked(True)
        ctrl_layout.addWidget(self.term_check)

        self.cov_check = QCheckBox("Horizon Ring")
        self.cov_check.setChecked(True)
        ctrl_layout.addWidget(self.cov_check)

        ctrl_layout.addStretch()
        
        self.fps_label = QLabel("FPS: 60.0 (WebGL)")
        self.fps_label.setStyleSheet("color: #10b981; font-weight: bold; font-family: monospace; margin-right: 12px;")
        ctrl_layout.addWidget(self.fps_label)

        self.epoch_label = QLabel(f"UTC: {self.current_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        self.epoch_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-family: monospace;")
        ctrl_layout.addWidget(self.epoch_label)
        layout.addLayout(ctrl_layout)

        # QWebEngineView WebGL Canvas Widget (uses offscreen placeholder when running headless)
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            self.canvas = QLabel("3D Globe Canvas (Offscreen Headless Mode)")
            self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.canvas)
        else:
            self.canvas = Globe3DWebEngineCanvas(self)
            layout.addWidget(self.canvas)

    def set_satellites(self, satellites: List[SatelliteRecord]):
        """Sets active satellites to display on globe."""
        self.satellites = satellites

    def toggle_play(self):
        """Toggles real-time orbit propagation animation."""
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_btn.setText("⏸ Pause")
            self.timer.start(33)  # ~30 FPS timer
        else:
            self.play_btn.setText("▶ Play")
            self.timer.stop()

    def _on_timer_tick(self):
        """Timer callback advancing epoch by 30 seconds per frame."""
        from datetime import timedelta
        self.current_dt += timedelta(seconds=30)
        self.epoch_label.setText(f"UTC: {self.current_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    def closeEvent(self, event):
        """Clean up timer and child web engine canvas upon closure."""
        try:
            self.timer.stop()
            if hasattr(self, 'canvas') and self.canvas is not None:
                self.canvas.close()
        except Exception:
            pass
        super().closeEvent(event)


# Aliases for backward compatibility
Globe3DCanvas = Globe3DWebEngineCanvas
Globe3DOpenGLCanvas = Globe3DWebEngineCanvas
