from __future__ import annotations
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTabBar, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut, QColor, QFont
from app.views.sidebar import SidebarView
from app.views.canvas import CanvasView
from app.views.log_panel import LogPanel


class MainWindow(QMainWindow):
    """
    Top-level window.
    Layout: [Sidebar] | [Tab-bar + shared CanvasView]
    All sessions share one canvas; the tab-bar is the session selector.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HybMesh PreProcessor")
        self.resize(1450, 900)
        self.setStyleSheet("background: #0c0d16; color: #a0a8c0;")

        # ── Sidebar ───────────────────────────────────────────────────────
        self.sidebar_view = SidebarView()
        self.sidebar_view.setFixedWidth(330)

        # ── Right panel: tab-bar row + shared canvas ──────────────────────
        right_panel = QWidget()
        right_panel.setStyleSheet("background: #0c0d16;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Tab-bar toolbar row
        tab_row = QWidget()
        tab_row.setFixedHeight(38)
        tab_row.setStyleSheet("background: #06070d; border-bottom: 1px solid #1c1e36;")
        tab_hl = QHBoxLayout(tab_row)
        tab_hl.setContentsMargins(4, 2, 4, 2)
        tab_hl.setSpacing(0)

        self.tab_bar = QTabBar()
        self.tab_widget = self.tab_bar  # Alias for controller compatibility
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setStyleSheet("""
            QTabBar {
                background: transparent;
            }
            QTabBar::tab {
                background: #252844;
                color: #a5b0cf;
                border: 1px solid #363a60;
                border-bottom: none;
                padding: 5px 24px 5px 12px;
                margin-right: 2px;
                border-radius: 4px 4px 0 0;
                min-width: 100px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #0c0d16;
                color: #ffffff;
                border-bottom: 2px solid #5a9ad4;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background: #2e3155;
                color: #d1d8f0;
            }
            QTabBar::close-button {
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNkZGUyZmYiIHN0cm9rZS13aWR0aD0iNC41IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxsaW5lIHgxPSIxOCIgeTE9IjYiIHgyPSI2IiB5Mj0iMTgiPjwvbGluZT48bGluZSB4MT0iNiIgeTE9IjYiIHgyPSIxOCIgeTI9IjE4Ij48L2xpbmU+PC9zdmc+");
                subcontrol-position: right;
                width: 12px;
                height: 12px;
                margin-right: 4px;
            }
            QTabBar::close-button:hover {
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iNC41IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxsaW5lIHgxPSIxOCIgeTE9IjYiIHgyPSI2IiB5Mj0iMTgiPjwvbGluZT48bGluZSB4MT0iNiIgeTE9IjYiIHgyPSIxOCIgeTI9IjE4Ij48L2xpbmU+PC9zdmc+");
                background-color: #b71c1c;
                border-radius: 2px;
            }
        """)
        self.tab_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tab_hl.addWidget(self.tab_bar)

        # Shared canvas
        self.canvas_view = CanvasView()

        right_layout.addWidget(tab_row)
        right_layout.addWidget(self.canvas_view, stretch=1)

        # ── Central layout: sidebar | right ───────────────────────────────
        central = QWidget()
        central.setStyleSheet("background: #0c0d16;")
        hl = QHBoxLayout(central)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        hl.addWidget(self.sidebar_view)
        hl.addWidget(right_panel, stretch=1)
        self.setCentralWidget(central)

        # ── Log console (dock, bottom) ────────────────────────────────────
        self.log_panel = LogPanel()
        self.log_panel.setStyleSheet(
            "background: #06070d; color: #8892b0; font-family: monospace;")
        log_dock = QDockWidget("Log Console", self)
        log_dock.setWidget(self.log_panel)
        log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        log_dock.setMinimumHeight(90)
        log_dock.setStyleSheet(
            "QDockWidget { background: #06070d; color: #8892b0; }"
            "QDockWidget::title { background: #121422; padding: 4px; }")
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)

    # ── Shortcuts ─────────────────────────────────────────────────────────

    def setup_shortcuts(self, controller):
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(
            controller.undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(
            controller.redo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(
            controller.redo)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(
            controller.load_geometry)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(
            controller.save_output)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(
            controller.new_blank_tab)

    # ── Title / tab helpers ────────────────────────────────────────────────

    def update_title(self, filename: str = "", modified: bool = False):
        base = "HybMesh PreProcessor"
        if filename:
            prefix = "*" if modified else ""
            self.setWindowTitle(f"{prefix}{filename} — {base}")
        else:
            self.setWindowTitle(base)

    def update_tab_text(self, idx: int, text: str, color: str | None = None):
        if 0 <= idx < self.tab_bar.count():
            self.tab_bar.setTabText(idx, text)
            if color:
                self.tab_bar.setTabTextColor(idx, QColor(color))
