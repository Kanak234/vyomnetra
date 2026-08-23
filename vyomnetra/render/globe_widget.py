"""PySide6 Embedded 3D Orbital Globe Widget.

Uses Matplotlib 3D projection canvas inside PySide6 to render:
- Earth 3D surface sphere with latitude/longitude grid lines
- Day/Night solar terminator curve
- Satellite 3D position markers and orbit trajectory arcs
- Ground station positions (Hazaribagh highlighted) with coverage rings
"""

from datetime import datetime, timezone
from typing import List, Optional
import numpy as np

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QSlider,
    QLabel,
    QCheckBox
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D

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


class Globe3DCanvas(FigureCanvasQTAgg):
    """Matplotlib 3D Figure Canvas for rendering Earth and Satellite trajectories."""

    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor="#090d16")
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.ax: Axes3D = self.fig.add_subplot(111, projection="3d", facecolor="#090d16")
        self._init_3d_axes()

    def _init_3d_axes(self):
        """Sets up 3D camera and axis styling for dark space theme."""
        self.ax.set_facecolor("#090d16")
        self.ax.grid(False)
        
        # Hide axis panes
        self.ax.xaxis.pane.fill = False
        self.ax.yaxis.pane.fill = False
        self.ax.zaxis.pane.fill = False
        
        self.ax.xaxis.pane.set_edgecolor("#1e293b")
        self.ax.yaxis.pane.set_edgecolor("#1e293b")
        self.ax.zaxis.pane.set_edgecolor("#1e293b")
        
        self.ax.set_xlabel("X (km)", color="#64748b", fontsize=9)
        self.ax.set_ylabel("Y (km)", color="#64748b", fontsize=9)
        self.ax.set_zlabel("Z (km)", color="#64748b", fontsize=9)
        
        self.ax.tick_params(colors="#475569", labelsize=8)
        self.ax.set_xlim([-10000, 10000])
        self.ax.set_ylim([-10000, 10000])
        self.ax.set_zlim([-10000, 10000])
        self.ax.view_init(elev=20, azim=45)

    def render_globe_scene(
        self,
        satellites: List[SatelliteRecord],
        epoch_dt: datetime,
        show_terminator: bool = True,
        show_coverage: bool = True
    ):
        """Renders 3D Earth, solar terminator, ground sites, and satellite orbit arcs."""
        self.ax.clear()
        self._init_3d_axes()

        # 1. Earth 3D Wireframe / Mesh
        x, y, z = get_earth_sphere_mesh(num_lat=20, num_lon=40)
        self.ax.plot_wireframe(x, y, z, color="#1e3a8a", alpha=0.3, linewidth=0.5)

        # 2. Solar Terminator
        if show_terminator:
            _, term_ecef = calculate_solar_terminator_points(epoch_dt)
            self.ax.plot(
                term_ecef[:, 0], term_ecef[:, 1], term_ecef[:, 2],
                color="#f59e0b", linewidth=1.8, label="Solar Terminator"
            )

        # 3. Ground Sites (Hazaribagh)
        for site_key, site in settings.sites.items():
            site_pos = get_ground_site_ecef(site)
            is_hz = "hazaribagh" in site_key.lower()
            color = "#10b981" if is_hz else "#38bdf8"
            marker = "*" if is_hz else "o"
            msize = 10 if is_hz else 6
            
            self.ax.scatter(
                [site_pos[0]], [site_pos[1]], [site_pos[2]],
                color=color, marker=marker, s=msize * 15, label=f"Site: {site.name}"
            )
            self.ax.text(
                site_pos[0] * 1.08, site_pos[1] * 1.08, site_pos[2] * 1.08,
                f"  {site.name}", color=color, fontsize=8, fontweight="bold"
            )

            if show_coverage and is_hz:
                ring_pts = get_ground_site_coverage_ring(site)
                self.ax.plot(ring_pts[:, 0], ring_pts[:, 1], ring_pts[:, 2], color="#059669", linestyle="--", linewidth=1.0)

        # 4. Satellites & Orbit Trajectories
        colors = ["#ef4444", "#ec4899", "#8b5cf6", "#06b6d4", "#f97316"]
        for idx, sat in enumerate(satellites[:5]):
            c = colors[idx % len(colors)]
            pos_ecef, _, dt_list = generate_satellite_orbit_trajectory(sat, epoch_dt, duration_minutes=95.0, step_seconds=60.0)
            
            if len(pos_ecef) > 0:
                # Trajectory Arc
                self.ax.plot(pos_ecef[:, 0], pos_ecef[:, 1], pos_ecef[:, 2], color=c, alpha=0.7, linewidth=1.2, label=sat.name)
                # Current Position Marker
                curr_pos = pos_ecef[0]
                self.ax.scatter([curr_pos[0]], [curr_pos[1]], [curr_pos[2]], color=c, s=40, zorder=5)
                self.ax.text(
                    curr_pos[0] * 1.05, curr_pos[1] * 1.05, curr_pos[2] * 1.05,
                    f" {sat.name}", color=c, fontsize=8
                )

        self.ax.legend(loc="upper left", facecolor="#0f172a", edgecolor="#334155", labelcolor="#94a3b8", fontsize=7)
        self.draw()


class Globe3DWidget(QWidget):
    """PySide6 Container Widget holding 3D Globe Canvas and Playback Controls."""

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
        layout.setContentsMargins(4, 4, 4, 4)

        # Controls Header Bar
        ctrl_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedWidth(80)
        self.play_btn.clicked.connect(self.toggle_play)
        ctrl_layout.addWidget(self.play_btn)

        self.term_check = QCheckBox("Solar Terminator")
        self.term_check.setChecked(True)
        self.term_check.toggled.connect(self.refresh_scene)
        ctrl_layout.addWidget(self.term_check)

        self.cov_check = QCheckBox("Horizon Ring")
        self.cov_check.setChecked(True)
        self.cov_check.toggled.connect(self.refresh_scene)
        ctrl_layout.addWidget(self.cov_check)

        ctrl_layout.addStretch()
        self.epoch_label = QLabel(f"UTC: {self.current_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        self.epoch_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-family: monospace;")
        ctrl_layout.addWidget(self.epoch_label)

        layout.addLayout(ctrl_layout)

        # 3D Canvas
        self.canvas = Globe3DCanvas(self)
        layout.addWidget(self.canvas)

    def set_satellites(self, satellites: List[SatelliteRecord]):
        """Sets active satellites to display on globe."""
        self.satellites = satellites
        self.refresh_scene()

    def toggle_play(self):
        """Toggles real-time orbit propagation animation."""
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_btn.setText("⏸ Pause")
            self.timer.start(1000)  # Update every 1 second
        else:
            self.play_btn.setText("▶ Play")
            self.timer.stop()

    def _on_timer_tick(self):
        """Timer callback advancing epoch by 60 seconds per frame."""
        from datetime import timedelta
        self.current_dt += timedelta(seconds=60)
        self.epoch_label.setText(f"UTC: {self.current_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        self.refresh_scene()

    def refresh_scene(self):
        """Re-renders 3D scene."""
        self.canvas.render_globe_scene(
            satellites=self.satellites,
            epoch_dt=self.current_dt,
            show_terminator=self.term_check.isChecked(),
            show_coverage=self.cov_check.isChecked()
        )
