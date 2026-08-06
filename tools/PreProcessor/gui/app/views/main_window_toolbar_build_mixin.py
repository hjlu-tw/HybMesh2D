from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QLabel, QCheckBox,
    QComboBox, QProgressBar, QGridLayout
)
from app.styles import TOOLBAR_CHECKBOX_STYLE


# Mixins listed BEFORE QMainWindow so the Qt virtual overrides they provide
# (eventFilter / resizeEvent) resolve super() to QMainWindow, not object.


class MainWindowToolbarBuildMixin:
    """Builds the canvas toolbar (all display toggles/combos), extracted
    from MainWindow.__init__. Runs on the composed window (self.*)."""

    def _build_canvas_toolbar(self):
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
        self.cad_clear_btn = create_tb_btn(
            "Clear", "Clear transient overlays (resample/duplicate preview, "
            "handles) from the canvas — keeps the geometry")
        self.cad_clear_all_btn = create_tb_btn(
            "Clear All", "Remove ALL geometry (every edge, points and splits) "
            "from the active CAD tab — undoable")
        self.cad_redraw_btn = create_tb_btn(
            "Redraw", "Redraw the canvas — clear leftover markers/handles from the "
            "previous action and re-render the geometry")
        
        # New CAD Previews
        self.cad_preview_btn = create_tb_btn("Preview", "Run PreProcessor and preview geometry/boundary conditions")
        self.cad_curve_preview_btn = create_tb_btn("Preview Edge", "Preview the selected curve equation")
        self.cad_file_preview_btn = create_tb_btn("Apply", "Apply and preview the selected imported file segment")
        self.cad_curve_preview_btn.setVisible(False)
        self.cad_file_preview_btn.setVisible(False)
        # Cancel the running resample (surface_resampler). Disabled until a run
        # is in flight — mirrors mesh Generate/Cancel.
        self.cad_cancel_btn = create_tb_btn("Cancel", "Cancel the running resample")
        self.cad_cancel_btn.setEnabled(False)

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
        self.mesh_clear_btn = create_tb_btn("Clear", "Clear the displayed mesh from the canvas")

        # One-click hand-off of the just-generated grid to the Solver stage
        # (stages the Star-CD .vrt/.cel/.bnd into results/meshes, links them into
        # the Solver panel, detects BCs, and switches to the Solver tab).
        self.mesh_send_solver_btn = create_tb_btn(
            "Send to Solver  →",
            "Send the generated grid to the Solver (links the Star-CD mesh and "
            "switches to the Solver tab)")
        self.mesh_send_solver_btn.setStyleSheet("""
            QPushButton {
                background-color: #241540;
                color: #dde2ff;
                border: 1px solid #3a2560;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #35205e;
                border-color: #9a6ad4;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #0b0c16;
                color: #4a4e69;
                border-color: #1b1d2e;
            }
        """)

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

        # No stage owns the shared progress bar yet (see claim_progress).
        self._progress_owner = None

        # Track layouts for visibility toggling
        self.cad_tb_widgets = [
            self.focus_geom_btn, self.cad_clear_btn, self.cad_clear_all_btn,
            self.cad_redraw_btn,
            self.cad_preview_btn, self.cad_curve_preview_btn, self.cad_file_preview_btn,
            self.cad_cancel_btn,
            self.show_vertices_cb, self.show_nodes_cb, self.quality_check_cb,
            self.cad_sep2,
        ]

        self.mesh_tb_widgets = [
            self.mesh_preview_btn, self.mesh_generate_btn, self.mesh_cancel_btn,
            self.mesh_send_solver_btn,
            self.mesh_focus_btn, self.mesh_clear_btn, self.mesh_show_wireframe_cb, self.mesh_show_bc_cb,
            self.mesh_show_domain_cb, self.mesh_color_label, self.mesh_color_mode_combo,
            self.mesh_sep2, self.mesh_sep3, self.mesh_sep4
        ]

        # Hide mesh widgets on start
        for w in self.mesh_tb_widgets:
            w.setVisible(False)

        # Solver "Run Solver"/"Cancel" and Immersed-Boundary "Generate phi"/
        # "Cancel" live in the top canvas toolbar (like mesh Generate/Cancel)
        # rather than in their side panels. The buttons are owned by the panels
        # (so controller.py keeps its clicked/enable wiring); reparent them onto
        # the toolbar here and drive their visibility per mode.
        self.solver_tb_widgets = [
            self.solver_config_panel.run_solver_btn,
            self.solver_config_panel.cancel_solver_btn,
        ]
        self.ib_tb_widgets = [
            self.stl3d_config_panel.run_btn,
            self.stl3d_config_panel.cancel_btn,
            self.stl3d_config_panel.send_solver_btn,
        ]
        for w in self.solver_tb_widgets + self.ib_tb_widgets:
            w.setParent(self.canvas_toolbar)
            w.setVisible(False)

    # ---- Shared progress bar ownership --------------------------------- #
    # One bar is shared by every stage (CAD resample, mesh, solver, STL3d) and
    # those runs can overlap — a CAD Preview does not block mesh Generate. The
    # claim/release pair makes the LAST run to start own the bar, so a finishing
    # run can no longer hide or reset a bar another run is still driving.

    def claim_progress(self, owner: str, determinate: bool = False):
        """Take over the toolbar progress bar for `owner` and show it.

        `determinate` picks the 0-100 range for runs that parse a % from stdout;
        the default is the indeterminate busy animation."""
        self._progress_owner = owner
        pb = self.progress_bar
        pb.setRange(0, 100) if determinate else pb.setRange(0, 0)
        pb.setValue(0)
        pb.setVisible(True)
        # Name the work in the status bar: the bar alone showed movement but never
        # WHAT was moving. Mirrored from the three ownership methods so every
        # existing and future call site is covered without touching them.
        self.set_status_activity(owner)

    def set_progress(self, owner: str, pct: int):
        """Advance the bar only while `owner` still holds it, so a background run
        cannot drive the percentage another stage is displaying."""
        if self._progress_owner != owner:
            return
        self.progress_bar.setValue(pct)
        # After the guard, so a non-owner cannot relabel the status bar either.
        self.set_status_activity(owner, pct)

    def release_progress(self, owner: str):
        """Hide the bar — but only if `owner` still holds it. A run that started
        later owns the bar now and must keep showing its own progress."""
        if self._progress_owner != owner:
            return
        self._progress_owner = None
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.set_status_activity(None)
