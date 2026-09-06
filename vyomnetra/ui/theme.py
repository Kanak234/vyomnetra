"""Dark and Light theme constants and stylesheets for VYOMNETRA Desktop Application."""

DARK_STYLESHEET = """
QMainWindow {
    background-color: #0b0f19;
    color: #e2e8f0;
}

QWidget {
    background-color: #0b0f19;
    color: #e2e8f0;
    font-family: 'Inter', 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #1e293b;
    background: #0f172a;
    border-radius: 6px;
}

QTabBar::tab {
    background: #0f172a;
    color: #94a3b8;
    padding: 10px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #1e293b;
    border-bottom: none;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #1e293b;
    color: #38bdf8;
    font-weight: bold;
    border-bottom: 2px solid #38bdf8;
}

QTabBar::tab:hover {
    background: #1e293b;
    color: #f8fafc;
}

QGroupBox {
    border: 1px solid #1e293b;
    border-radius: 8px;
    margin-top: 12px;
    font-weight: bold;
    color: #38bdf8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    background-color: #0b0f19;
}

QPushButton {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #0369a1;
}

QPushButton:pressed {
    background-color: #075985;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f8fafc;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #38bdf8;
}

QTableWidget {
    background-color: #0f172a;
    gridline-color: #1e293b;
    border: 1px solid #1e293b;
    border-radius: 6px;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #38bdf8;
    padding: 6px;
    font-weight: bold;
    border: 1px solid #0f172a;
}

QStatusBar {
    background: #0f172a;
    color: #94a3b8;
    border-top: 1px solid #1e293b;
}

QStatusBar::item {
    border: none;
}

QMenuBar {
    background-color: #0f172a;
    color: #e2e8f0;
    border-bottom: 1px solid #1e293b;
}

QMenuBar::item:selected {
    background-color: #1e293b;
    color: #38bdf8;
}

QMenu {
    background-color: #0f172a;
    color: #e2e8f0;
    border: 1px solid #1e293b;
}

QMenu::item:selected {
    background-color: #1e293b;
    color: #38bdf8;
}
"""

LIGHT_STYLESHEET = """
QMainWindow {
    background-color: #f8fafc;
    color: #0f172a;
}

QWidget {
    background-color: #f8fafc;
    color: #0f172a;
    font-family: 'Inter', 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #cbd5e1;
    background: #ffffff;
    border-radius: 6px;
}

QTabBar::tab {
    background: #e2e8f0;
    color: #475569;
    padding: 10px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #0284c7;
    font-weight: bold;
    border-bottom: 2px solid #0284c7;
}

QGroupBox {
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    margin-top: 12px;
    font-weight: bold;
    color: #0284c7;
}

QPushButton {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #0369a1;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    border: 1px solid #94a3b8;
    border-radius: 6px;
    padding: 6px 10px;
    color: #0f172a;
}

QTableWidget {
    background-color: #ffffff;
    gridline-color: #e2e8f0;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
}

QHeaderView::section {
    background-color: #e2e8f0;
    color: #0369a1;
    padding: 6px;
    font-weight: bold;
    border: 1px solid #cbd5e1;
}

QStatusBar {
    background: #e2e8f0;
    color: #334155;
    border-top: 1px solid #cbd5e1;
}

QMenuBar {
    background-color: #e2e8f0;
    color: #0f172a;
    border-bottom: 1px solid #cbd5e1;
}

QMenu {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
}
"""
