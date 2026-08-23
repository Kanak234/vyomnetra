"""PySide6 Application Shell for VYOMNETRA."""

import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QLineEdit,
    QComboBox,
    QStatusBar,
    QGroupBox,
    QSplitter,
    QHeaderView,
)

from vyomnetra.config import settings
from vyomnetra.ui.theme import DARK_STYLESHEET
from vyomnetra.utils.logger import get_logger, log_data_fetch
from vyomnetra.ingest.db import DatabaseManager
from vyomnetra.ingest.adapters import CelesTrakAdapter
from vyomnetra.ingest.health import get_data_health_summary

logger = get_logger("vyomnetra.ui")


def create_not_implemented_banner(phase_name: str) -> QLabel:
    """Helper creating a prominent 'NOT IMPLEMENTED — Phase N' badge."""
    banner = QLabel(f"🚧 NOT IMPLEMENTED — {phase_name}")
    banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
    banner.setStyleSheet(
        "background-color: #312e81; color: #a5b4fc; border: 1px solid #6366f1; "
        "padding: 8px; border-radius: 6px; font-weight: bold; font-size: 14px;"
    )
    return banner


class MainWindow(QMainWindow):
    """Main Application Window for VYOMNETRA."""

    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.setWindowTitle(f"{settings.app_name} v{settings.app_version} — Space Situational Awareness Workbench")
        self.resize(1280, 800)
        
        # Apply dark theme
        self.setStyleSheet(DARK_STYLESHEET)

        # Build UI layout
        self._init_menu_bar()
        self._init_ui()
        self._init_status_bar()
        
        # Refresh initial data tables
        self.refresh_catalogue_table()
        self.refresh_health_table()
        
        logger.info("VYOMNETRA main window initialized successfully.")

    def _init_menu_bar(self):
        """Builds top menu bar."""
        menu_bar = self.menuBar()
        
        file_menu = menu_bar.addMenu("&File")
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        data_menu = menu_bar.addMenu("&Data")
        fetch_action = QAction("&Fetch CelesTrak Catalogue", self)
        fetch_action.triggered.connect(self.on_fetch_catalogue)
        data_menu.addAction(fetch_action)
        
        val_menu = menu_bar.addMenu("&Validation")
        run_val_action = QAction("&Run All Validation Tiers", self)
        run_val_action.triggered.connect(self.on_run_validation)
        val_menu.addAction(run_val_action)

    def _init_ui(self):
        """Constructs tabbed layout."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # Tabs
        self.tabs = QTabWidget(self)
        
        self.globe_tab = self._create_globe_panel()
        self.catalogue_tab = self._create_catalogue_panel()
        self.conjunction_tab = self._create_conjunction_panel()
        self.pass_tab = self._create_pass_panel()
        self.nl_tab = self._create_nl_panel()
        self.science_tab = self._create_science_panel()
        self.health_tab = self._create_health_panel()
        self.validation_tab = self._create_validation_panel()
        
        self.tabs.addTab(self.globe_tab, "🌐 3D Globe")
        self.tabs.addTab(self.catalogue_tab, "📡 Catalogue")
        self.tabs.addTab(self.conjunction_tab, "⚠️ Conjunctions")
        self.tabs.addTab(self.pass_tab, "🔭 Pass Planner")
        self.tabs.addTab(self.nl_tab, "🧠 NL Assistant & CoT")
        self.tabs.addTab(self.science_tab, "🔬 Space Science")
        self.tabs.addTab(self.health_tab, "📊 Data Health & Audit")
        self.tabs.addTab(self.validation_tab, "🧪 Validation Harness")
        
        main_layout.addWidget(self.tabs)

    def _create_globe_panel(self) -> QWidget:
        """3D Globe View Panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(create_not_implemented_banner("Phase 4: 3D Globe & Catalogue Table"))
        
        header = QLabel("<h3>3D Orbital Globe & Tracking View</h3>")
        header.setStyleSheet("color: #38bdf8;")
        layout.addWidget(header)
        
        placeholder = QLabel("CesiumJS / OpenGL Globe View Host\n[25,000+ Catalogue Objects Rendering Target]")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("background: #0f172a; border: 2px dashed #334155; border-radius: 8px; color: #64748b; font-size: 16px;")
        layout.addWidget(placeholder)
        
        return widget

    def _create_catalogue_panel(self) -> QWidget:
        """Satellite Catalogue Table Panel (IMPLEMENTED IN PHASE 1)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        header_layout = QHBoxLayout()
        header = QLabel("<h3>NORAD GP Satellite Catalogue (Live Database)</h3>")
        header.setStyleSheet("color: #38bdf8;")
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        fetch_btn = QPushButton("🔄 Refresh / Fetch GP Data")
        fetch_btn.clicked.connect(self.on_fetch_catalogue)
        header_layout.addWidget(fetch_btn)
        
        layout.addLayout(header_layout)
        
        self.catalogue_table = QTableWidget(0, 7)
        self.catalogue_table.setHorizontalHeaderLabels([
            "NORAD ID", "Name", "Designator", "Epoch (UTC)", "Inclination (°)", "Period (min)", "Fetch ID"
        ])
        self.catalogue_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.catalogue_table)
        
        return widget

    def _create_conjunction_panel(self) -> QWidget:
        """Close Approach Screening Panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(create_not_implemented_banner("Phase 5: Conjunction Close-Approach Screening"))
        
        header = QLabel("<h3>Conjunction Assessment & Close Approaches</h3>")
        header.setStyleSheet("color: #38bdf8;")
        layout.addWidget(header)
        
        banner = QLabel("⚠️ UNCERTAINTY NOTICE: Public TLEs carry kilometre-scale position uncertainty and no covariance. Probability of collision (Pc) is an order-of-magnitude screening indicator.")
        banner.setWordWrap(True)
        banner.setStyleSheet("background: #451a03; border: 1px solid #f59e0b; padding: 10px; border-radius: 6px; color: #fef3c7;")
        layout.addWidget(banner)
        
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Primary Object", "Secondary Object", "TCA (UTC)", "Miss Distance (km)", "Rel Velocity (km/s)", "Calculated Pc"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        
        return widget

    def _create_pass_panel(self) -> QWidget:
        """Topocentric Pass Prediction Panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(create_not_implemented_banner("Phase 3: Visibility, Passes & Observation Log"))
        
        header_layout = QHBoxLayout()
        header = QLabel("<h3>Ground Site Pass Predictor & Observation Log</h3>")
        header.setStyleSheet("color: #38bdf8;")
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Target Ground Site:"))
        
        site_combo = QComboBox()
        for site_key, site in settings.sites.items():
            site_combo.addItem(f"{site.name} ({site.latitude_deg:.2f}°N, {site.longitude_deg:.2f}°E)", site_key)
        header_layout.addWidget(site_combo)
        
        layout.addLayout(header_layout)
        
        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(["Satellite", "Rise Time (UTC)", "Max El Time", "Max El (°)", "Set Time", "Est. Mag", "Naked Eye Visible?"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        
        return widget

    def _create_nl_panel(self) -> QWidget:
        """Natural Language Assistant & CoT Orchestrator Panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(create_not_implemented_banner("Phase 7 & 8: Knowledge Graph, NL Query & CoT Planner"))
        
        header = QLabel("<h3>Knowledge Graph & Chain-of-Thought Query Engine</h3>")
        header.setStyleSheet("color: #38bdf8;")
        layout.addWidget(header)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        top_box = QGroupBox("Query Input & Tool Execution Plan")
        top_layout = QVBoxLayout(top_box)
        query_input = QLineEdit()
        query_input.setPlaceholderText("Ask VYOMNETRA (e.g., 'What Starlink satellites pass over Hazaribagh tonight under 5km miss distance?')")
        top_layout.addWidget(query_input)
        
        plan_view = QTextEdit()
        plan_view.setReadOnly(True)
        plan_view.setPlaceholderText("Decoded Chain-of-Thought tool execution plan will appear here...")
        top_layout.addWidget(plan_view)
        
        splitter.addWidget(top_box)
        
        bot_box = QGroupBox("Cites & Structured Response")
        bot_layout = QVBoxLayout(bot_box)
        res_view = QTextEdit()
        res_view.setReadOnly(True)
        res_view.setPlaceholderText("Audited answer with exact data lineage records...")
        bot_layout.addWidget(res_view)
        
        splitter.addWidget(bot_box)
        layout.addWidget(splitter)
        
        return widget

    def _create_science_panel(self) -> QWidget:
        """Space Science Workbench Panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(create_not_implemented_banner("Phase 9: Space-Science Light Curve Pipeline"))
        
        header = QLabel("<h3>Space Science Workbench — Light Curve & Transit Search</h3>")
        header.setStyleSheet("color: #38bdf8;")
        layout.addWidget(header)
        
        placeholder = QLabel("TESS / Kepler Light Curve & Box Least Squares Transit Periodogram")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("background: #0f172a; border: 1px dashed #334155; border-radius: 8px; color: #64748b; font-size: 14px;")
        layout.addWidget(placeholder)
        
        return widget

    def _create_health_panel(self) -> QWidget:
        """Data Health and Audit Logs Panel (IMPLEMENTED IN PHASE 1)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        header = QLabel("<h3>Data Source Health & Lineage Audit Log (Live Engine)</h3>")
        header.setStyleSheet("color: #38bdf8;")
        layout.addWidget(header)
        
        self.health_table = QTableWidget(0, 8)
        self.health_table.setHorizontalHeaderLabels([
            "Source Name", "URL", "Last Fetch (UTC)", "Staleness (hrs)", "HTTP Status", "Records", "Rejected", "Hash"
        ])
        self.health_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.health_table)
        
        return widget

    def _create_validation_panel(self) -> QWidget:
        """Validation Harness Panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(create_not_implemented_banner("Phase 2 & Section 5: Multi-Tier Validation Harness"))
        
        header = QLabel("<h3>5-Tier Verification & Benchmark Suite</h3>")
        header.setStyleSheet("color: #38bdf8;")
        layout.addWidget(header)
        
        table = QTableWidget(5, 4)
        table.setHorizontalHeaderLabels(["Tier", "Test Name", "Tolerance", "Status"])
        
        tiers = [
            ("Tier 1", "SGP4 Vallado Reference (SGP4-VER.TLE)", "Pos < 1e-6 km, Vel < 1e-9 km/s", "NOT RUN"),
            ("Tier 2", "Skyfield Cross-Implementation Agreement", "Agreement < 1.0 m", "NOT RUN"),
            ("Tier 3", "JPL Horizons Reference Pass Check", "Pass Time < 30s, Max El < 1.0°", "NOT RUN"),
            ("Tier 4", "Naked-Eye Physical Observation Residuals", "User Empirical Delta", "NOT RUN"),
            ("Tier 5", "Synthetic Conjunction Oracle Screening", "Zero False Negatives", "NOT RUN"),
        ]
        
        for idx, (tier, name, tol, status) in enumerate(tiers):
            table.setItem(idx, 0, QTableWidgetItem(tier))
            table.setItem(idx, 1, QTableWidgetItem(name))
            table.setItem(idx, 2, QTableWidgetItem(tol))
            table.setItem(idx, 3, QTableWidgetItem(status))
            
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        
        run_btn = QPushButton("▶ Run All Validation Tiers")
        run_btn.clicked.connect(self.on_run_validation)
        layout.addWidget(run_btn)
        
        return widget

    def _init_status_bar(self):
        """Status bar showing system status."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.refresh_status_bar()

    def refresh_status_bar(self):
        """Refreshes status bar with database satellite count."""
        sat_count = len(self.db_manager.get_all_satellites())
        self.status_bar.showMessage(
            f"VYOMNETRA Ready | Database: {sat_count} satellites ingested | DB: {settings.get_db_path().name}"
        )

    def refresh_catalogue_table(self):
        """Loads satellite records from SQLite into Catalogue table."""
        satellites = self.db_manager.get_all_satellites()
        self.catalogue_table.setRowCount(len(satellites))
        
        for row_idx, sat in enumerate(satellites[:1000]):  # Display top 1000 for fast UI rendering
            period_min = round(1440.0 / sat.mean_motion, 2) if sat.mean_motion > 0 else 0.0
            self.catalogue_table.setItem(row_idx, 0, QTableWidgetItem(str(sat.norad_id)))
            self.catalogue_table.setItem(row_idx, 1, QTableWidgetItem(sat.name))
            self.catalogue_table.setItem(row_idx, 2, QTableWidgetItem(sat.international_designator or ""))
            self.catalogue_table.setItem(row_idx, 3, QTableWidgetItem(sat.epoch_utc))
            self.catalogue_table.setItem(row_idx, 4, QTableWidgetItem(f"{sat.inclination_deg:.2f}°"))
            self.catalogue_table.setItem(row_idx, 5, QTableWidgetItem(f"{period_min:.2f} m"))
            self.catalogue_table.setItem(row_idx, 6, QTableWidgetItem(str(sat.fetch_id)))

    def refresh_health_table(self):
        """Populates Data Health table from SQLite fetch logs."""
        health_data = get_data_health_summary(self.db_manager)
        self.health_table.setRowCount(len(health_data))
        
        for row_idx, item in enumerate(health_data):
            self.health_table.setItem(row_idx, 0, QTableWidgetItem(str(item["source_name"])))
            self.health_table.setItem(row_idx, 1, QTableWidgetItem(str(item["source_url"])))
            self.health_table.setItem(row_idx, 2, QTableWidgetItem(str(item["last_fetch_utc"])))
            self.health_table.setItem(row_idx, 3, QTableWidgetItem(f"{item['staleness_hours']} hrs"))
            self.health_table.setItem(row_idx, 4, QTableWidgetItem(str(item["http_status"])))
            self.health_table.setItem(row_idx, 5, QTableWidgetItem(str(item["record_count"])))
            self.health_table.setItem(row_idx, 6, QTableWidgetItem(str(item["rejected_count"])))
            hash_short = str(item["content_hash"])[:8] + "..." if item["content_hash"] else ""
            self.health_table.setItem(row_idx, 7, QTableWidgetItem(hash_short))

    def on_fetch_catalogue(self):
        """Handler for fetching GP Catalogue."""
        self.status_bar.showMessage("Fetching CelesTrak GP catalogue...")
        adapter = CelesTrakAdapter(self.db_manager)
        try:
            fetch_log, satellites = adapter.fetch()
            self.refresh_catalogue_table()
            self.refresh_health_table()
            self.refresh_status_bar()
            logger.info(f"UI Fetch complete: Ingested {len(satellites)} satellites under fetch ID {fetch_log.id}.")
        except Exception as e:
            logger.error(f"UI Catalogue fetch error: {e}")
            self.status_bar.showMessage(f"Fetch failed: {e}")

    def on_run_validation(self):
        """Handler for validation execution."""
        self.status_bar.showMessage("Executing Validation Suite...")


def launch_app():
    """Main application launcher."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(launch_app())
