from __future__ import annotations
import os
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTabBar, QLabel, QSizePolicy, QCheckBox,
    QStackedWidget, QComboBox, QFrame, QScrollArea, QMenu, QProgressBar, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QEvent
from PyQt6.QtGui import QKeySequence, QShortcut, QColor, QFont
from app.views.sidebar import SidebarView
from app.views.canvas import CanvasView
from app.views.log_panel import LogPanel
from app.views.mesh_canvas import MeshCanvasView
from app.views.result_canvas import ResultCanvasView
from app.views.panels.mesh_config_panel import MeshConfigPanel
from app.views.panels.mesh_stats_panel import MeshStatsPanel
from app.views.panels.solver_config_panel import SolverConfigPanel
from app.views.panels.solver_monitor_panel import SolverMonitorPanel
from app.styles import TOOLBAR_CHECKBOX_STYLE


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
        self.setMinimumSize(1200, 800)
        self.resize(1450, 900)
        self.setStyleSheet("background: #0c0d16; color: #a0a8c0;")

        # ── Sidebar Stack ─────────────────────────────────────────────────
        self.sidebar_stack = QStackedWidget(self)
        self.sidebar_stack.setMinimumWidth(300)
        self.sidebar_stack.setMaximumWidth(430)
        self.sidebar_stack.setFixedWidth(360)

        self.sidebar_view = SidebarView(self.sidebar_stack)
        self.sidebar_stack.addWidget(self.sidebar_view)

        # Mesh Configuration Sidebar Page (directly in stack)
        self.mesh_config_panel = MeshConfigPanel(self.sidebar_stack)
        self.sidebar_stack.addWidget(self.mesh_config_panel)

        # Mesh Statistics Sidebar Page (wrapped in scroll area)
        self.stats_scroll = QScrollArea(self.sidebar_stack)
        self.stats_scroll.setWidgetResizable(True)
        self.stats_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.stats_scroll.setStyleSheet("background: #0c0d16;")
        self.stats_scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: #0c0d16;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #2c2e43;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3e415e;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.mesh_stats_panel = MeshStatsPanel(self.stats_scroll)
        self.stats_scroll.setWidget(self.mesh_stats_panel)
        self.sidebar_stack.addWidget(self.stats_scroll)

        # Solver config sidebar page (Phase 4.1). The monitor (idx 4) is still a
        # placeholder until Phase 4.2.
        self.solver_config_panel = SolverConfigPanel(self.sidebar_stack)
        self.sidebar_stack.addWidget(self.solver_config_panel)      # idx 3
        self.solver_monitor_panel = SolverMonitorPanel(self.sidebar_stack)
        self.sidebar_stack.addWidget(self.solver_monitor_panel)     # idx 4

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
        tab_bar_style = """
            QTabBar {
                background: transparent;
            }
            QTabBar::tab {
                background: transparent;
                color: #a5b0cf;
                border: 1px solid transparent;
                border-bottom: none;
                padding: 5px 24px 5px 12px;
                margin-right: 2px;
                border-radius: 4px 4px 0 0;
                min-width: 100px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #2a4a7f;
                color: #ffffff;
                border: 1px solid #5a9ad4;
                border-bottom: 3px solid #7cb8f0;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
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
        """
        self.tab_bar.setStyleSheet(tab_bar_style)
        self.tab_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tab_hl.addWidget(self.tab_bar)

        # Mesh Generator / Statistics share their own tab strip, kept separate
        # from the CAD geometry tabs. Mesh state is global/shared, so these
        # tabs are visual workspaces — only one is shown depending on mode.
        self.mesh_tab_bar = QTabBar(self.tab_row)
        self.mesh_tab_bar.setTabsClosable(True)
        self.mesh_tab_bar.setMovable(True)
        self.mesh_tab_bar.setExpanding(False)
        self.mesh_tab_bar.setStyleSheet(tab_bar_style)
        self.mesh_tab_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.mesh_tab_bar.addTab("Mesh 1")
        self.mesh_tab_bar.setVisible(False)
        tab_hl.addWidget(self.mesh_tab_bar)

        self.mode_combo = QComboBox(self.tab_row)
        self.mode_combo.addItems([
            "PreProcessor (CAD)", "Mesh Generator", "Mesh Statistics",
            "Solver", "Results",
        ])
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
        self.canvas_toolbar.setStyleSheet("background: #06070d; border-bottom: 1px solid #1c1e36;")
        self.tb_layout = QGridLayout(self.canvas_toolbar)
        self.tb_layout.setContentsMargins(10, 2, 10, 2)
        self.tb_layout.setHorizontalSpacing(8)
        self.tb_layout.setVerticalSpacing(4)

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

        self.undo_btn = create_tb_btn("Undo", "Undo last action (Ctrl+Z)")
        self.redo_btn = create_tb_btn("Redo", "Redo last action (Ctrl+Shift+Z)")
        self.focus_geom_btn = create_tb_btn("Fit View", "Fit canvas view to selected geometry")
        
        # New CAD Previews
        self.cad_preview_btn = create_tb_btn("Preview", "Run PreProcessor and preview geometry/boundary conditions")
        self.cad_curve_preview_btn = create_tb_btn("Preview Edge", "Preview the selected curve equation")
        self.cad_file_preview_btn = create_tb_btn("Apply", "Apply and preview the selected imported file segment")
        self.cad_curve_preview_btn.setVisible(False)
        self.cad_file_preview_btn.setVisible(False)

        # Separators
        def create_sep():
            v = QWidget(self.canvas_toolbar)
            v.setFixedWidth(1)
            v.setFixedHeight(16)
            v.setStyleSheet("background-color: #1c1e36;")
            return v

        self.cad_sep1 = create_sep()
        self.cad_sep2 = create_sep()

        self.show_vertices_cb = QCheckBox("Vertices", self.canvas_toolbar)
        self.show_vertices_cb.setToolTip("Show/hide geometry vertices (points) on the canvas")
        self.show_vertices_cb.setStyleSheet(TOOLBAR_CHECKBOX_STYLE)
        self.show_vertices_cb.setChecked(True)

        self.show_nodes_cb = QCheckBox("Nodes", self.canvas_toolbar)
        self.show_nodes_cb.setToolTip("Show/hide resampled nodes on the canvas")
        self.show_nodes_cb.setStyleSheet(TOOLBAR_CHECKBOX_STYLE)
        self.show_nodes_cb.setChecked(True)

        self.quality_check_cb = QCheckBox("Heatmap", self.canvas_toolbar)
        self.quality_check_cb.setToolTip("Show/hide geometry quality heatmap (Length / Ratio)")
        self.quality_check_cb.setStyleSheet(TOOLBAR_CHECKBOX_STYLE)

        self.quality_mode_combo = QComboBox(self.canvas_toolbar)
        self.quality_mode_combo.addItems(["Length", "Ratio"])
        self.quality_mode_combo.setStyleSheet("""
            QComboBox {
                background: #181b30;
                color: #dde2ff;
                border: 1px solid #2d3356;
                border-radius: 4px;
                padding: 3px 8px;
                font-weight: bold;
                font-size: 10px;
                min-width: 80px;
            }
        """)
        self.quality_mode_combo.setVisible(False)

        # NOTE: the Vertex/Edge selection-mode selector now lives in the sidebar,
        # next to the model tree (see SidebarView.select_mode_combo), so it sits
        # with the selection it filters rather than in the canvas toolbar.

        # Mesh Generation Toolbar controls
        self.mesh_preview_btn = create_tb_btn("BC Preview", "Preview calculation domain and boundary geometries")
        self.mesh_generate_btn = create_tb_btn("Generate", "Run HybMesh2D to generate grid")
        self.mesh_generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e4620;
                color: #dde2ff;
                border: 1px solid #2d5630;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2c5e2e;
                border-color: #22c55e;
                color: #ffffff;
            }
        """)
        self.mesh_cancel_btn = create_tb_btn("Cancel", "Cancel background mesh generation")
        self.mesh_cancel_btn.setEnabled(False)
        self.mesh_cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a1c1c;
                color: #dde2ff;
                border: 1px solid #5d2d2d;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #6a2c2c;
                border-color: #ef4444;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #1a1f3b;
                color: #4a4e69;
                border-color: #1c1e36;
            }
        """)

        self.mesh_focus_btn = create_tb_btn("Fit View", "Fit canvas to mesh or preview boundaries")

        self.mesh_show_wireframe_cb = QCheckBox("Mesh", self.canvas_toolbar)
        self.mesh_show_wireframe_cb.setToolTip("Show/hide mesh wireframe")
        self.mesh_show_wireframe_cb.setStyleSheet(TOOLBAR_CHECKBOX_STYLE)
        self.mesh_show_wireframe_cb.setChecked(True)

        self.mesh_show_bc_cb = QCheckBox("BCs", self.canvas_toolbar)
        self.mesh_show_bc_cb.setToolTip("Show/hide boundary conditions")
        self.mesh_show_bc_cb.setStyleSheet(TOOLBAR_CHECKBOX_STYLE)
        self.mesh_show_bc_cb.setChecked(True)

        self.mesh_show_domain_cb = QCheckBox("Domain", self.canvas_toolbar)
        self.mesh_show_domain_cb.setToolTip("Show/hide calculation domain boundary")
        self.mesh_show_domain_cb.setStyleSheet(TOOLBAR_CHECKBOX_STYLE)
        self.mesh_show_domain_cb.setChecked(True)

        self.mesh_color_label = QLabel("", self.canvas_toolbar) # Hidden dummy
        self.mesh_color_label.setVisible(False)

        self.mesh_color_mode_combo = QComboBox(self.canvas_toolbar)
        self.mesh_color_mode_combo.addItems([
            "Element Type", 
            "Quality (Aspect Ratio)", 
            "Quality (Skewness)",
            "Uniform"
        ])
        self.mesh_color_mode_combo.setStyleSheet("""
            QComboBox {
                background: #181b30;
                color: #dde2ff;
                border: 1px solid #2d3356;
                border-radius: 4px;
                padding: 3px 8px;
                font-weight: bold;
                font-size: 10px;
                min-width: 140px;
            }
        """)

        self.mesh_sep2 = create_sep()
        self.mesh_sep3 = create_sep()
        self.mesh_sep4 = create_sep()

        self.progress_bar = QProgressBar(self.canvas_toolbar)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setFixedWidth(100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #181b30;
                border: 1px solid #2d3356;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #22c55e;
                border-radius: 3px;
            }
        """)

        # Track layouts for visibility toggling
        self.cad_tb_widgets = [
            self.focus_geom_btn,
            self.cad_preview_btn, self.cad_curve_preview_btn, self.cad_file_preview_btn,
            self.show_vertices_cb, self.show_nodes_cb, self.quality_check_cb,
            self.cad_sep2,
        ]

        self.mesh_tb_widgets = [
            self.mesh_preview_btn, self.mesh_generate_btn, self.mesh_cancel_btn,
            self.mesh_focus_btn, self.mesh_show_wireframe_cb, self.mesh_show_bc_cb,
            self.mesh_show_domain_cb, self.mesh_color_label, self.mesh_color_mode_combo,
            self.mesh_sep2, self.mesh_sep3, self.mesh_sep4
        ]

        # Hide mesh widgets on start
        for w in self.mesh_tb_widgets:
            w.setVisible(False)

        # Shared Canvas Stack
        self.canvas_stack = QStackedWidget(self.right_panel)
        self.canvas_view = CanvasView(self.canvas_stack)
        self.canvas_stack.addWidget(self.canvas_view)
        
        self.mesh_canvas_view = MeshCanvasView(self.canvas_stack)
        self.canvas_stack.addWidget(self.mesh_canvas_view)          # idx 1

        # Results canvas (matplotlib, Phase 4.3)
        self.result_canvas_view = ResultCanvasView(self.canvas_stack)
        self.canvas_stack.addWidget(self.result_canvas_view)        # idx 2

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

        # Install event filter on all toolbar widgets to detect visibility changes dynamically
        always_visible_tb_widgets = [self.undo_btn, self.redo_btn, self.cad_sep1]
        all_toolbar_widgets = self.cad_tb_widgets + self.mesh_tb_widgets + always_visible_tb_widgets + [self.progress_bar, self.quality_mode_combo]
        for w in all_toolbar_widgets:
            w.installEventFilter(self)

        self._layout_queued = False
        self.adjust_toolbar_layout()

        # ── Log console (dock, bottom) ────────────────────────────────────
        self.log_panel = LogPanel(self)
        self.log_panel.setStyleSheet(
            "background: #06070d; color: #8892b0; font-family: monospace;")
        log_dock = QDockWidget("Log Console", self)
        log_dock.setWidget(self.log_panel)
        log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        log_dock.setMinimumHeight(48)
        log_dock.setStyleSheet(
            "QDockWidget { background: #06070d; color: #8892b0; }"
            "QDockWidget::title { background: #121422; padding: 3px; }")
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        # Default to a small log console height.
        self.resizeDocks([log_dock], [80], Qt.Orientation.Vertical)

    # ── Shortcuts ─────────────────────────────────────────────────────────

    def setup_shortcuts(self, controller):
        # 1. Initialize QShortcuts (Global hotkeys)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(controller.undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(controller.redo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(controller.redo)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(controller.load_geometry)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(controller.save_output)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(controller.new_blank_tab)
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(controller.new_blank_tab)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(lambda: controller.close_tab(controller.active_idx))
        QShortcut(QKeySequence("F5"), self).activated.connect(controller.preview_backend)

        # 2. Setup standard Menu Bar
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #090a12;
                color: #a0a8c0;
                border-bottom: 1px solid #1c1e36;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 4px 10px;
            }
            QMenuBar::item:selected {
                background-color: #1e2235;
                color: #ffffff;
            }
            QMenu {
                background-color: #121422;
                color: #a0a8c0;
                border: 1px solid #1c1e36;
            }
            QMenu::item {
                padding: 6px 20px;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
        """)

        file_menu = menubar.addMenu("File")

        load_action = file_menu.addAction("Load Geometry...")
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(controller.load_geometry)

        load_json_action = file_menu.addAction("Load JSON Config...")
        load_json_action.triggered.connect(controller.load_json_config)

        file_menu.addSeparator()

        self.recent_menu = file_menu.addMenu("Open Recent")
        controller.init_recent_files()

        file_menu.addSeparator()

        new_tab_action = file_menu.addAction("New Tab")
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.triggered.connect(controller.new_blank_tab)

        close_tab_action = file_menu.addAction("Close Tab")
        close_tab_action.setShortcut("Ctrl+W")
        close_tab_action.triggered.connect(lambda: controller.close_tab(controller.active_idx))

        file_menu.addSeparator()

        save_action = file_menu.addAction("Export Mesh (.dat)...")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(controller.save_output)

        save_json_action = file_menu.addAction("Save Configuration (.json)...")
        save_json_action.triggered.connect(controller.generate_json)

        file_menu.addSeparator()

        save_ws_action = file_menu.addAction("Save Workspace...")
        save_ws_action.triggered.connect(controller.save_workspace)

        load_ws_action = file_menu.addAction("Load Workspace...")
        load_ws_action.triggered.connect(controller.load_workspace)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def refresh_recent_files_menu(self, files: list[str], controller):
        self.recent_menu.clear()
        if not files:
            empty_action = self.recent_menu.addAction("No Recent Files")
            empty_action.setEnabled(False)
            return
        for f in files:
            action = self.recent_menu.addAction(os.path.basename(f))
            action.setToolTip(f)
            # Use default argument in lambda to bind loop variable f properly
            action.triggered.connect(lambda checked, path=f: controller.load_recent_file(path))

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

    def _make_placeholder(self, text: str) -> QWidget:
        """A simple centred-label stub widget used for not-yet-built pages."""
        w = QWidget()
        w.setStyleSheet("background: #0c0d16;")
        lay = QVBoxLayout(w)
        lbl = QLabel(text, w)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #4a4e69; font-size: 13px;")
        lay.addWidget(lbl)
        return w

    def _on_mode_changed(self, idx: int):
        self.sidebar_stack.setCurrentIndex(idx)
        # Canvas mapping: CAD->0, Mesh/Stats/Solver->1 (mesh canvas), Results->2.
        canvas_map = {0: 0, 1: 1, 2: 1, 3: 1, 4: 2}
        self.canvas_stack.setCurrentIndex(canvas_map.get(idx, 0))

        is_pre = (idx == 0)
        is_mesh = (idx in (1, 2))
        # CAD shows its per-file geometry tabs; the Mesh Generator / Statistics
        # pages show their own separate tab strip. They never share tabs, but
        # both keep their open tabs alive when the other mode is showing.
        self.tab_bar.setVisible(is_pre)
        self.mesh_tab_bar.setVisible(is_mesh)
        for w in self.cad_tb_widgets:
            w.setVisible(is_pre)

        # The Length/Ratio selector belongs to CAD mode and only when the
        # heatmap is on; kept out of cad_tb_widgets so it is not force-shown.
        self.quality_mode_combo.setVisible(is_pre and self.quality_check_cb.isChecked())

        if is_pre:
            props = self.sidebar_view.edge_props_panel
            is_curve_active = props.isVisible() and props._curve_group.isVisible()
            self.cad_curve_preview_btn.setVisible(is_curve_active)
            # The toolbar "Apply" (file preview) duplicated "Preview"; keep hidden.
            self.cad_file_preview_btn.setVisible(False)

        for w in self.mesh_tb_widgets:
            w.setVisible(is_mesh)
        self.progress_bar.setVisible(False)

        self.adjust_toolbar_layout()
        self.mode_changed.emit(idx)

    def eventFilter(self, watched, event) -> bool:
        if event.type() in (QEvent.Type.Show, QEvent.Type.Hide):
            if not getattr(self, '_layout_queued', False):
                self._layout_queued = True
                QTimer.singleShot(0, self._run_queued_layout)
        return super().eventFilter(watched, event)

    def _run_queued_layout(self):
        self._layout_queued = False
        self.adjust_toolbar_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_toolbar_layout()

    def adjust_toolbar_layout(self):
        # Prevent recursion
        if getattr(self, '_adjusting_layout', False):
            return
        self._adjusting_layout = True
        
        try:
            # Clear layout first
            while self.tb_layout.count() > 0:
                self.tb_layout.takeAt(0)
                
            # Reset all column stretches
            for col in range(30):
                self.tb_layout.setColumnStretch(col, 0)
                
            idx = self.sidebar_stack.currentIndex()
            width = self.width()
            
            # Determine threshold based on mode
            if idx == 0:
                threshold = 1200
                is_narrow = (width < threshold)
                
                if is_narrow:
                    self.canvas_toolbar.setFixedHeight(68)
                    # cad_sep2 is redundant in two-row mode; hide so it is not
                    # left visible-but-unpositioned after the grid is rebuilt.
                    self.cad_sep2.setVisible(False)

                    row0_widgets = [
                        self.undo_btn,
                        self.redo_btn,
                        self.cad_sep1,
                        self.focus_geom_btn,
                        self.cad_preview_btn,
                        self.cad_curve_preview_btn,
                        self.cad_file_preview_btn,
                    ]
                    row1_widgets = [
                        self.show_vertices_cb,
                        self.show_nodes_cb,
                        self.quality_check_cb,
                        self.quality_mode_combo,
                    ]
                    
                    # Add to row 0
                    col_idx = 0
                    for w in row0_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 0, col_idx)
                            col_idx += 1
                            
                    # Add to row 1
                    col_idx = 0
                    for w in row1_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 1, col_idx)
                            col_idx += 1
                            
                    max_col = max(self.tb_layout.columnCount() - 1, 0)
                    self.tb_layout.setColumnStretch(max_col + 1, 1)
                else:
                    self.canvas_toolbar.setFixedHeight(36)
                    self.cad_sep2.setVisible(True)
                    all_widgets = [
                        self.undo_btn,
                        self.redo_btn,
                        self.cad_sep1,
                        self.focus_geom_btn,
                        self.cad_preview_btn,
                        self.cad_curve_preview_btn,
                        self.cad_file_preview_btn,
                        self.cad_sep2,
                        self.show_vertices_cb,
                        self.show_nodes_cb,
                        self.quality_check_cb,
                        self.quality_mode_combo,
                    ]
                    col_idx = 0
                    for w in all_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 0, col_idx)
                            col_idx += 1
                    self.tb_layout.setColumnStretch(col_idx, 1)

            elif idx in (1, 2):  # Mesh modes
                threshold = 1100
                is_narrow = (width < threshold)
                
                if is_narrow:
                    self.canvas_toolbar.setFixedHeight(68)
                    # mesh_sep3 is redundant in two-row mode; hide so it is not
                    # left visible-but-unpositioned after the grid is rebuilt.
                    self.mesh_sep3.setVisible(False)
                    row0_widgets = [
                        self.undo_btn,
                        self.redo_btn,
                        self.cad_sep1,
                        self.mesh_preview_btn,
                        self.mesh_generate_btn,
                        self.mesh_cancel_btn,
                        self.mesh_sep2,
                        self.mesh_focus_btn,
                    ]
                    row1_widgets = [
                        self.mesh_show_wireframe_cb,
                        self.mesh_show_bc_cb,
                        self.mesh_show_domain_cb,
                        self.mesh_sep4,
                        self.mesh_color_label,
                        self.mesh_color_mode_combo,
                        self.progress_bar,
                    ]
                    
                    # Add to row 0
                    col_idx = 0
                    for w in row0_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 0, col_idx)
                            col_idx += 1
                            
                    # Add to row 1
                    col_idx = 0
                    for w in row1_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 1, col_idx)
                            col_idx += 1
                            
                    max_col = max(self.tb_layout.columnCount() - 1, 0)
                    self.tb_layout.setColumnStretch(max_col + 1, 1)
                else:
                    self.canvas_toolbar.setFixedHeight(36)
                    self.mesh_sep3.setVisible(True)
                    all_widgets = [
                        self.undo_btn,
                        self.redo_btn,
                        self.cad_sep1,
                        self.mesh_preview_btn,
                        self.mesh_generate_btn,
                        self.mesh_cancel_btn,
                        self.mesh_sep2,
                        self.mesh_focus_btn,
                        self.mesh_sep3,
                        self.mesh_show_wireframe_cb,
                        self.mesh_show_bc_cb,
                        self.mesh_show_domain_cb,
                        self.mesh_sep4,
                        self.mesh_color_label,
                        self.mesh_color_mode_combo,
                        self.progress_bar,
                    ]
                    col_idx = 0
                    for w in all_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 0, col_idx)
                            col_idx += 1
                    self.tb_layout.setColumnStretch(col_idx, 1)

            else:  # Solver / Results modes — minimal toolbar; panels own their controls
                self.canvas_toolbar.setFixedHeight(36)
                self.mesh_sep3.setVisible(False)
                col_idx = 0
                for w in (self.undo_btn, self.redo_btn, self.cad_sep1):
                    if w.isVisible():
                        self.tb_layout.addWidget(w, 0, col_idx)
                        col_idx += 1
                self.tb_layout.setColumnStretch(col_idx, 1)
        finally:
            self._adjusting_layout = False

    def closeEvent(self, event):
        if hasattr(self, "controller") and self.controller is not None:
            if not self.controller.handle_close_event():
                event.ignore()
                return
        event.accept()
