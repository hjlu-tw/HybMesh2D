from __future__ import annotations
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTabBar, QLabel, QSizePolicy, QStackedWidget, QComboBox, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from app.views.sidebar import SidebarView
from app.views.canvas import CanvasView
from app.views.log_panel import LogPanel
from app.views.mesh_canvas import MeshCanvasView
from app.views.result_canvas import ResultCanvasView
from app.views.panels.mesh_config_panel import MeshConfigPanel
from app.views.panels.mesh_stats_panel import MeshStatsPanel
from app.views.panels.solver_config_panel import SolverConfigPanel
from app.views.panels.solver_monitor_panel import SolverMonitorPanel
from app.views.panels.stl3d_panel import Stl3dConfigPanel
from app.views.stl3d_canvas import Stl3dCanvasView
from app.views.panels.result_panel import ResultControlPanel
from app.views.main_window_menu_mixin import MainWindowMenuMixin
from app.views.main_window_toolbar_mixin import MainWindowToolbarMixin
from app.views.main_window_toolbar_build_mixin import MainWindowToolbarBuildMixin
from app.views.main_window_statusbar_mixin import MainWindowStatusBarMixin


# Mixins listed BEFORE QMainWindow so the Qt virtual overrides they provide
# (eventFilter / resizeEvent) resolve super() to QMainWindow, not object.
class MainWindow(MainWindowMenuMixin, MainWindowToolbarMixin,
                 MainWindowToolbarBuildMixin, MainWindowStatusBarMixin,
                 QMainWindow):
    """
    Top-level window.
    Layout: [Sidebar] | [Tab-bar + shared CanvasView]
    All sessions share one canvas; the tab-bar is the session selector.
    """

    mode_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HybMesh PreProcessor")
        # A smaller minimum so the window fits (and can be shrunk on) laptop /
        # scaled displays. The old 1200x800 floor forced the window larger than
        # small screens, pushing the left sidebar's lower fields + footer buttons
        # off the visible area. Every sidebar page is scrollable, so content
        # stays reachable at this size.
        self.setMinimumSize(900, 600)
        # Open at a comfortable size but never larger than the available screen.
        from PyQt6.QtWidgets import QApplication
        scr = QApplication.primaryScreen()
        if scr is not None:
            avail = scr.availableGeometry()
            self.resize(min(1450, avail.width()), min(900, avail.height()))
        else:
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
        # Results sidebar: color-scale (clim) control + field statistics
        # (complements the canvas toolbar's variable/colormap/overlay controls).
        self.result_control_panel = ResultControlPanel(self.sidebar_stack)
        self.sidebar_stack.addWidget(self.result_control_panel)     # idx 4
        # Immersed-solid (STL -> phi) preprocessor config sidebar page
        self.stl3d_config_panel = Stl3dConfigPanel(self.sidebar_stack)
        self.sidebar_stack.addWidget(self.stl3d_config_panel)       # idx 5

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
        # Preferred (not Expanding) so the bar spans only its tabs; a trailing
        # stretch (added before the mode selector) absorbs the free space, which
        # keeps the mode selector pinned to the right in every mode.
        self.tab_bar.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
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
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.mesh_tab_bar.addTab("Mesh 1")
        self.mesh_tab_bar.setVisible(False)
        tab_hl.addWidget(self.mesh_tab_bar)

        self.mode_combo = QComboBox(self.tab_row)
        self.mode_combo.addItems([
            "PreProcessor (CAD)", "Mesh Generator", "Mesh Statistics",
            "Solver", "Results", "Immersed Boundary (φ)",
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
                margin-right: 6px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border-left: 1px solid #2d3356;
            }
        """)
        # Pin the width to the widest tab name (measured in the bold QSS font) so
        # the selector never resizes when a longer/shorter tab is selected.
        from PyQt6.QtGui import QFontMetrics
        _mc_font = QFont(self.mode_combo.font()); _mc_font.setBold(True)
        _mc_fm = QFontMetrics(_mc_font)
        _mc_w = max(_mc_fm.horizontalAdvance(self.mode_combo.itemText(i))
                    for i in range(self.mode_combo.count()))
        self.mode_combo.setFixedWidth(_mc_w + 46)   # + text padding, arrow, slack
        # Stretch before the selector so it stays pinned to the right (fixed
        # position) whether or not a tab strip is visible in the current mode.
        tab_hl.addStretch(1)

        # "Run All" — one click runs CAD resample -> mesh -> solver -> results.
        # Lives in the persistent tab row (not the rebuilt canvas toolbar) so it
        # is available in every mode.
        self.run_all_btn = QPushButton("▶ Run All", self.tab_row)
        self.run_all_btn.setToolTip(
            "Run the full pipeline for the active geometry:\n"
            "CAD resample → mesh generation → solver → results contour.")
        self.run_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e4620;
                color: #eaf6ea;
                border: 1px solid #2d5630;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 11px;
                margin-right: 8px;
            }
            QPushButton:hover {
                background-color: #2c5e2e;
                border-color: #22c55e;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #1a1f3b;
                color: #4a4e69;
                border-color: #1c1e36;
            }
        """)
        tab_hl.addWidget(self.run_all_btn)

        tab_hl.addWidget(self.mode_combo)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self._build_canvas_toolbar()
        # Shared Canvas Stack
        self.canvas_stack = QStackedWidget(self.right_panel)
        self.canvas_view = CanvasView(self.canvas_stack)
        self.canvas_stack.addWidget(self.canvas_view)
        
        self.mesh_canvas_view = MeshCanvasView(self.canvas_stack)
        self.canvas_stack.addWidget(self.mesh_canvas_view)          # idx 1

        # Results canvas (matplotlib, Phase 4.3)
        self.result_canvas_view = ResultCanvasView(self.canvas_stack)
        self.canvas_stack.addWidget(self.result_canvas_view)        # idx 2

        # Solver monitor (live residual plot) is the Solver-mode canvas.
        self.solver_monitor_panel = SolverMonitorPanel(self.canvas_stack)
        self.canvas_stack.addWidget(self.solver_monitor_panel)      # idx 3

        # Immersed-solid 3D viewport (STL + domain box/grid + phi cells).
        self.stl3d_canvas = Stl3dCanvasView(self.canvas_stack)
        self.canvas_stack.addWidget(self.stl3d_canvas)              # idx 4

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
        # Required by QMainWindow.saveState()/restoreState(): a dock without an
        # objectName is skipped (with a runtime warning), so its size, visibility
        # and floating state could never be restored between sessions.
        log_dock.setObjectName("logConsoleDock")
        self.log_dock = log_dock
        log_dock.setWidget(self.log_panel)
        log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        log_dock.setMinimumHeight(48)
        log_dock.setStyleSheet(
            "QDockWidget { background: #06070d; color: #8892b0; }"
            "QDockWidget::title { background: #121422; padding: 3px; }")
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        # Default to a small log console height.
        self.resizeDocks([log_dock], [80], Qt.Orientation.Vertical)

        # Status bar last: it reads the mode combo and the panels.
        self._build_status_bar()

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
        # CAD->geom, Mesh/Stats->mesh canvas, Solver->monitor, Results->result
        # canvas, Immersed Solid (5)->stl3d 3D viewport (idx 4).
        canvas_map = {0: 0, 1: 1, 2: 1, 3: 3, 4: 2, 5: 4}
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

        # Solver / Immersed-Boundary run+cancel toolbar buttons (idx 3 / 5).
        for w in self.solver_tb_widgets:
            w.setVisible(idx == 3)
        for w in self.ib_tb_widgets:
            w.setVisible(idx == 5)

        # A run in flight keeps its progress bar across a mode switch; hide the
        # bar only when no stage owns it (see claim_progress/release_progress).
        self.progress_bar.setVisible(self._progress_owner is not None)

        self.adjust_toolbar_layout()
        self.mode_changed.emit(idx)

    def closeEvent(self, event):
        if hasattr(self, "controller") and self.controller is not None:
            if not self.controller.handle_close_event():
                event.ignore()
                return
        event.accept()
