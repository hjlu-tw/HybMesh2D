from __future__ import annotations
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTabBar, QLabel, QSizePolicy, QCheckBox,
    QStackedWidget, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut, QColor, QFont
from app.views.sidebar import SidebarView
from app.views.canvas import CanvasView
from app.views.log_panel import LogPanel
from app.views.mesh_canvas import MeshCanvasView
from app.views.panels.mesh_config_panel import MeshConfigPanel
from app.views.panels.mesh_stats_panel import MeshStatsPanel


class MainWindow(QMainWindow):
    """
    Top-level window.
    Layout: [Sidebar] | [Tab-bar + shared CanvasView]
    All sessions share one canvas; the tab-bar is the session selector.
    """

    mode_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HybMesh PreProcessor")
        self.resize(1450, 900)
        self.setStyleSheet("background: #0c0d16; color: #a0a8c0;")

        # ── Sidebar Stack ─────────────────────────────────────────────────
        self.sidebar_stack = QStackedWidget(self)
        self.sidebar_stack.setFixedWidth(350)

        self.sidebar_view = SidebarView(self.sidebar_stack)
        self.sidebar_stack.addWidget(self.sidebar_view)

        # Mesh Generation Sidebar Container
        self.mesh_sidebar = QWidget(self.sidebar_stack)
        self.mesh_sidebar.setStyleSheet("background: #121422;")
        mesh_sb_layout = QVBoxLayout(self.mesh_sidebar)
        mesh_sb_layout.setContentsMargins(0, 0, 0, 0)
        mesh_sb_layout.setSpacing(6)

        self.mesh_config_panel = MeshConfigPanel(self.mesh_sidebar)
        self.mesh_stats_panel = MeshStatsPanel(self.mesh_sidebar)

        mesh_sb_layout.addWidget(self.mesh_config_panel, stretch=7)
        mesh_sb_layout.addWidget(self.mesh_stats_panel, stretch=3)
        self.sidebar_stack.addWidget(self.mesh_sidebar)

        # ── Right panel: tab-bar row + shared canvas ──────────────────────
        self.right_panel = QWidget(self)
        self.right_panel.setStyleSheet("background: #0c0d16;")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Tab-bar toolbar row
        self.tab_row = QWidget(self.right_panel)
        self.tab_row.setFixedHeight(38)
        self.tab_row.setStyleSheet("background: #06070d; border-bottom: 1px solid #1c1e36;")
        tab_hl = QHBoxLayout(self.tab_row)
        tab_hl.setContentsMargins(4, 2, 4, 2)
        tab_hl.setSpacing(0)

        self.tab_bar = QTabBar(self.tab_row)
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

        self.mode_combo = QComboBox(self.tab_row)
        self.mode_combo.addItems(["PreProcessor (CAD)", "Mesh Generator"])
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background: #181b30;
                color: #dde2ff;
                border: 1px solid #2d3356;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11px;
                min-width: 150px;
                margin-right: 6px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border-left: 1px solid #2d3356;
            }
        """)
        tab_hl.addWidget(self.mode_combo)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        # ── Canvas Toolbar ────────────────────────────────────────────────
        self.canvas_toolbar = QWidget(self.right_panel)
        self.canvas_toolbar.setFixedHeight(36)
        self.canvas_toolbar.setStyleSheet("background: #06070d; border-bottom: 1px solid #1c1e36;")
        tb_layout = QHBoxLayout(self.canvas_toolbar)
        tb_layout.setContentsMargins(10, 0, 10, 0)
        tb_layout.setSpacing(15)

        # Helper to create buttons
        def create_tb_btn(text: str, tooltip: str) -> QPushButton:
            btn = QPushButton(text, self.canvas_toolbar)
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
            v = QWidget(self.canvas_toolbar)
            v.setFixedWidth(1)
            v.setFixedHeight(16)
            v.setStyleSheet("background-color: #1c1e36;")
            return v

        self.show_vertices_cb = QCheckBox("Show Geometry Vertices", self.canvas_toolbar)
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

        self.show_nodes_cb = QCheckBox("Show Resampled Nodes", self.canvas_toolbar)
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

        self.quality_check_cb = QCheckBox("Show Quality Heatmap", self.canvas_toolbar)
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

        # Shared Canvas Stack
        self.canvas_stack = QStackedWidget(self.right_panel)
        self.canvas_view = CanvasView(self.canvas_stack)
        self.canvas_stack.addWidget(self.canvas_view)
        
        self.mesh_canvas_view = MeshCanvasView(self.canvas_stack)
        self.canvas_stack.addWidget(self.mesh_canvas_view)

        right_layout.addWidget(self.tab_row)
        right_layout.addWidget(self.canvas_toolbar)
        right_layout.addWidget(self.canvas_stack, stretch=1)

        # ── Central layout: sidebar | right ───────────────────────────────
        self.central = QWidget(self)
        self.central.setStyleSheet("background: #0c0d16;")
        hl = QHBoxLayout(self.central)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        hl.addWidget(self.sidebar_stack)
        hl.addWidget(self.right_panel, stretch=1)
        self.setCentralWidget(self.central)

        # ── Log console (dock, bottom) ────────────────────────────────────
        self.log_panel = LogPanel(self)
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

    def _on_mode_changed(self, idx: int):
        self.sidebar_stack.setCurrentIndex(idx)
        self.canvas_stack.setCurrentIndex(idx)
        is_pre = (idx == 0)
        self.undo_btn.setVisible(is_pre)
        self.redo_btn.setVisible(is_pre)
        self.show_vertices_cb.setVisible(is_pre)
        self.show_nodes_cb.setVisible(is_pre)
        self.quality_check_cb.setVisible(is_pre)
        self.focus_geom_btn.setVisible(is_pre)
        self.mode_changed.emit(idx)
