from __future__ import annotations
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTabBar, QLabel, QSizePolicy, QCheckBox
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
        self.sidebar_view.setFixedWidth(350)

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

        # ── Canvas Toolbar ────────────────────────────────────────────────
        self.canvas_toolbar = QWidget()
        self.canvas_toolbar.setFixedHeight(36)
        self.canvas_toolbar.setStyleSheet("background: #06070d; border-bottom: 1px solid #1c1e36;")
        tb_layout = QHBoxLayout(self.canvas_toolbar)
        tb_layout.setContentsMargins(10, 0, 10, 0)
        tb_layout.setSpacing(15)

        # Helper to create buttons
        def create_tb_btn(text: str, tooltip: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setToolTip(tooltip)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #181b30;
                    color: #dde2ff;
                    border: 1px solid #2d3356;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #2c3258;
                    border-color: #5a9ad4;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    background-color: #1a1f3b;
                }
                QPushButton:disabled {
                    background-color: #0b0c16;
                    color: #4a4e69;
                    border-color: #1b1d2e;
                }
            """)
            return btn

        self.undo_btn = create_tb_btn("↺ Undo", "Undo last action (Ctrl+Z)")
        self.redo_btn = create_tb_btn("↻ Redo", "Redo last action (Ctrl+Shift+Z)")
        self.focus_geom_btn = create_tb_btn("⛶ Fit to View", "Fit canvas view to selected geometry")

        # Separators
        def create_sep():
            v = QWidget()
            v.setFixedWidth(1)
            v.setFixedHeight(16)
            v.setStyleSheet("background-color: #1c1e36;")
            return v

        self.show_vertices_cb = QCheckBox("Show Geometry Vertices")
        self.show_vertices_cb.setStyleSheet("""
            QCheckBox {
                color: #a0b0d0;
                font-size: 11px;
            }
            QCheckBox:hover {
                color: #ffffff;
            }
        """)
        self.show_vertices_cb.setChecked(True)

        self.show_nodes_cb = QCheckBox("Show Resampled Nodes")
        self.show_nodes_cb.setStyleSheet("""
            QCheckBox {
                color: #a0b0d0;
                font-size: 11px;
            }
            QCheckBox:hover {
                color: #ffffff;
            }
        """)
        self.show_nodes_cb.setChecked(True)

        self.quality_check_cb = QCheckBox("Show Quality Heatmap")
        self.quality_check_cb.setStyleSheet("""
            QCheckBox {
                color: #a0b0d0;
                font-size: 11px;
            }
            QCheckBox:hover {
                color: #ffffff;
            }
        """)

        tb_layout.addWidget(self.undo_btn)
        tb_layout.addWidget(self.redo_btn)
        tb_layout.addWidget(create_sep())
        tb_layout.addWidget(self.focus_geom_btn)
        tb_layout.addWidget(create_sep())
        tb_layout.addWidget(self.show_vertices_cb)
        tb_layout.addWidget(self.show_nodes_cb)
        tb_layout.addWidget(self.quality_check_cb)
        tb_layout.addStretch(1)

        # Shared canvas
        self.canvas_view = CanvasView()

        right_layout.addWidget(tab_row)
        right_layout.addWidget(self.canvas_toolbar)
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
