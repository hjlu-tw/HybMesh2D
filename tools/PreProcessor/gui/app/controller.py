"""
AppController — multi-session, command-pattern, preview/save-separated controller.
"""
from __future__ import annotations
import os
import tempfile
from contextlib import contextmanager

import numpy as np

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from app.services import user_log
from app.services.edge_edit import EdgeEditSession
from app.views.main_window import MainWindow
from app.views.canvas import CanvasView
from app.commands.base import CommandHistory
from app.models.session import GeometrySession
from app.models.mesh_config import MeshConfig
from app.models.project import ProjectModel

from app.controllers import (
    SessionControllerMixin,
    SessionLoadControllerMixin,
    SessionTabsControllerMixin,
    SessionIOControllerMixin,
    ProjectStateControllerMixin,
    SegmentControllerMixin,
    SegmentCanvasControllerMixin,
    SegmentVertexControllerMixin,
    SegmentAutoDetectControllerMixin,
    SegmentPropsControllerMixin,
    SegmentDistributionControllerMixin,
    TransformControllerMixin,
    TransformApplyControllerMixin,
    CurveControllerMixin,
    CurveJoinControllerMixin,
    CurveDrawControllerMixin,
    CurveEditControllerMixin,
    FileEditControllerMixin,
    PendingEditControllerMixin,
    BackendControllerMixin,
    MeshGenControllerMixin,
    MeshExportControllerMixin,
    MeshLayersControllerMixin,
    OpenEndpointControllerMixin,
    SolverControllerMixin,
    SolverBcControllerMixin,
    SolverToolsControllerMixin,
    CaseExportControllerMixin,
    PostprocessControllerMixin,
    SurfaceSourceControllerMixin,
    Stl3dControllerMixin,
    Stl3dFitControllerMixin,
    ExtrudeControllerMixin,
    PipelineControllerMixin,
    PipelineIoControllerMixin,
    UndoControllerMixin,
    UnitsControllerMixin,
    PanelSyncControllerMixin,
    BatchControllerMixin,
    SignalWiringMixin,
    LifecycleControllerMixin,
)
from app.models.solver_config import SolverConfig
from app.models.stl3d_config import Stl3dConfig


class AppController(
    SessionControllerMixin,
    SessionLoadControllerMixin,
    SessionTabsControllerMixin,
    SessionIOControllerMixin,
    ProjectStateControllerMixin,
    SegmentControllerMixin,
    SegmentCanvasControllerMixin,
    SegmentVertexControllerMixin,
    SegmentAutoDetectControllerMixin,
    SegmentPropsControllerMixin,
    SegmentDistributionControllerMixin,
    TransformControllerMixin,
    TransformApplyControllerMixin,
    CurveControllerMixin,
    CurveJoinControllerMixin,
    CurveDrawControllerMixin,
    CurveEditControllerMixin,
    FileEditControllerMixin,
    PendingEditControllerMixin,
    BackendControllerMixin,
    MeshGenControllerMixin,
    MeshExportControllerMixin,
    MeshLayersControllerMixin,
    OpenEndpointControllerMixin,
    SolverControllerMixin,
    SolverBcControllerMixin,
    SolverToolsControllerMixin,
    CaseExportControllerMixin,
    PostprocessControllerMixin,
    SurfaceSourceControllerMixin,
    Stl3dControllerMixin,
    Stl3dFitControllerMixin,
    ExtrudeControllerMixin,
    PipelineControllerMixin,
    PipelineIoControllerMixin,
    UndoControllerMixin,
    UnitsControllerMixin,
    PanelSyncControllerMixin,
    BatchControllerMixin,
    SignalWiringMixin,
    LifecycleControllerMixin,
):

    def __init__(self):
        self.main_window = MainWindow()
        self.main_window.controller = self
        self.sessions: list[GeometrySession] = []
        self.active_idx: int = -1

        # Undo history for project-level settings, alongside the per-session CAD
        # histories. Created here, before anything can ask whether undo is
        # available; its recorder is started later (init_project_undo), once the
        # panels hold their startup values.
        self.project_history = CommandHistory()
        self.project_history.on_change = self._update_undo_redo_buttons
        
        self.global_mesh_config = MeshConfig()
        self.global_vtk_mesh = None
        self.global_vtk_path = ""

        # Solver pipeline state (Phase 3)
        self.global_solver_config = SolverConfig()
        self.global_solver_config.ensure_default_binaries()
        self.global_result_path = ""
        self.global_result_data = None
        self._solver_worker = None

        # Full-pipeline (Run All) state
        self._pipeline_running = False
        self._pipeline_result_var = ""

        # Immersed-solid (STL3d) preprocessor state
        self.global_stl3d_config = Stl3dConfig()
        self._stl3d_worker = None
        self._fit_worker = None            # background STL↔φ fit-check worker
        self._stl3d_bbox = None
        self._stl3d_tris = None            # cached STL triangles for the fit check
        self._stl3d_phi_path = ""
        self._stl3d_phi_pts = None         # cached parsed phi field (fit check)
        self._stl3d_phi_val = None
        self._extrude_worker = None        # background 2D-profile → STL extruder
        self._extrude_pending = None       # extrude params awaiting the worker result
        # Held between a worker's result and finished() so a still-unwinding
        # QThread keeps its last ref ("destroyed while running").
        self._retiring_workers: set = set()

        # Depth counter, not a bool: nested population (an outer
        # handle_segment_list_selected whose body triggers another populate) must
        # not have the inner block's exit re-enable change handlers while the
        # outer one is still writing widgets. Read it through the
        # ``_is_populating`` property; set it only via ``populating()``.
        self._populating_depth = 0
        self._show_duplicate_preview = False  # flag to show duplicate preview line
        # BOTH edit kinds — the analytic edge being created/edited (modeless
        # dialog open) and the imported outline being reshaped by its corners —
        # live in ONE owner, not twelve attributes shared by four files. They are
        # alternatives, so ``is_active()`` is one question with one answer. Ask
        # the owner; never reach past it.
        self.edge_edit = EdgeEditSession()
        self._custom_preview_fitted = False

        # Create a dedicated temp directory for the application lifecycle
        self.temp_dir = tempfile.mkdtemp(prefix="hybmesh_preprocessor_")
        QApplication.instance().aboutToQuit.connect(self.cleanup_temp_dir)

        # Seed each stage panel from its model, BEFORE anything can read a panel
        # back. A panel is built holding Qt's un-set widget values (0, or the spin
        # box floor), not its model's defaults, and the panel→model sync fires for
        # ALL panels on every push_panel_config — so the first push (init_solver's)
        # would otherwise read the untouched Mesh panel and overwrite the mesh
        # defaults with BL layers 0, growth 1.001, Gmsh MeshAdapt, outer BCs inlet.
        # Done here, before the signals are wired, so the population is silent.
        self.push_models_to_panels()

        self._wire_sidebar_signals()
        self._wire_tab_signals()
        self._wire_canvas_signals()
        self._wire_mesh_signals()
        self._wire_solver_stl3d_signals()
        self._wire_toolbar_sync()


        # ── Keyboard shortcuts ──────────────────────────────────────────
        self.main_window.setup_shortcuts(self)

        # #7: replace the blunt 1.0 default up/down step on numeric fields with a
        # per-field, value-scaled step (integer counts + explicitly-stepped
        # fields are left untouched).
        from app.utils import apply_smart_spin_steps
        apply_smart_spin_steps(self.main_window)

        self._update_undo_redo_buttons()

        # ── Auto-save / crash recovery (Phase 3) ────────────────────────────
        # A stable path (NOT the per-run temp_dir, which is removed on exit) so
        # an autosave survives a crash and can be offered for recovery next run.
        self._autosave_path = os.path.join(
            tempfile.gettempdir(), "hybmesh_preprocessor_autosave.hws")
        recovered = self._maybe_recover_autosave()
        if not recovered:
            # Open a new blank tab on startup (do not restore previous files)
            self.new_blank_tab()
        # Baseline for project-level (Mesh / Solver / IB) dirty detection. Taken
        # last, once the panels hold their startup state, so nothing is reported
        # as modified before the user has touched anything.
        self._project_baseline: dict | None = None
        self._reset_project_baseline()

        # Start recording project-level edits. After the baseline above, so the
        # startup state is the reference and nothing is recorded before the user
        # touches anything.
        self.init_project_undo()
        self._wire_project_undo_signals()

        # Restore the saved window layout (size/position, Log Console dock,
        # collapsible sections). The stage is restored separately, last, because
        # switching stage populates panels and needs a fully-wired controller.
        from app.services.ui_state import restore_active_stage, restore_ui_state
        restore_ui_state(self.main_window)
        restore_active_stage(self.main_window)

        self._autosave_timer = QTimer(self.main_window)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(60000)  # every 60 s


    # ═════════════════════════════════════════════════════════════════════
    # Coordination and Core Orchestration Methods
    # ═════════════════════════════════════════════════════════════════════

    # ── form-population guard ────────────────────────────────────────────
    @property
    def _is_populating(self) -> bool:
        """True while widgets are being written from the model.

        Change handlers check this to avoid feeding a programmatic write back
        into the model as if the user had typed it.
        """
        return self._populating_depth > 0

    @contextmanager
    def populating(self):
        """Write widgets from the model without the handlers writing back.

        Always use this rather than assigning the flag: it is exception-safe (a
        raise mid-population used to leave the guard stuck on, silently deadening
        every handler for the rest of the session) and re-entrant, so a nested
        populate cannot clear the outer one's guard on the way out.
        """
        self._populating_depth += 1
        try:
            yield
        finally:
            self._populating_depth -= 1

    # ── user-facing log ──────────────────────────────────────────────────
    def log(self, message, level: str | None = None):
        """Say something to the USER (the OUTPUT CONSOLE + the durable log file).

        Use this, never ``self.main_window.log_panel.log(...)``: reaching through
        the view tree ties the message to a window that a headless run does not
        have, which is how every batch/CI/pipeline run used to discard its own
        progress report. See :mod:`app.services.user_log`.

        For DEVELOPER diagnostics (a step allowed to fail, a traceback) use
        ``get_logger(__name__)`` instead — that is a different log with a
        different audience.
        """
        user_log.log(message, level)

    def show_main_window(self):
        self.main_window.show()

    def handle_mode_changed(self, idx: int):
        """Update Mesh Config Panel and Mesh Canvas View when switching modes."""
        if idx in [1, 2]:  # Mesh Generator or Statistics Mode
            self.push_panel_config(self.main_window.mesh_config_panel, self.global_mesh_config)
            
            vtk_path = self.global_vtk_path if self.global_vtk_path else (self._get_expected_vtk_path(self.global_mesh_config) if self.global_mesh_config else "")
            self.main_window.mesh_stats_panel.update_stats(self.global_vtk_mesh, vtk_path)
            
            self.main_window.mesh_canvas_view.update_mesh_config(self.global_mesh_config)
            if self.global_vtk_mesh:
                self.main_window.mesh_canvas_view.render_mesh(self.global_vtk_mesh)
            else:
                self.main_window.mesh_canvas_view.clear_mesh()
            
            # Update the Geometry Layers list panel in MeshConfigPanel
            self.sync_mesh_layers_panel()
        elif idx == 3:  # Solver: pull the latest Mesh-Generator patch BCs (#7)
            self.resync_solver_bc_from_group()
            self.refresh_solver_probe_overlay()  # #4: re-overlay probe markers
        elif idx == 5:  # Immersed Solid (STL -> phi): refresh the 3D overlay
            self.on_stl3d_config_changed()
            self.on_stl3d_display_changed()

    def _refresh_mesh_previews(self, cfg):
        """Refresh geometry (boundary + domain) and seed previews from a config.

        Domain-role geometries (far-field / wall) ARE drawn — excluding them made
        a geometry vanish the moment its role was set to a domain role."""
        mw = self.main_window
        non_seed = [g for g in cfg.geom_files if not cfg.is_seed(g)]
        mw.mesh_canvas_view.update_geometry_previews(non_seed)
        mw.mesh_canvas_view.update_seed_previews(cfg.seed_files)

    def handle_mesh_geom_files_changed(self, geom_files: list[str]):
        """Callback when the set of geometry files changes (add/browse/remove)."""
        mw = self.main_window
        # Cheap role lookup from item data (no full MeshConfig rebuild).
        roles = mw.mesh_config_panel.current_geom_roles()
        seeds = [p for p in geom_files if p in roles]
        boundaries = [p for p in geom_files if p not in roles]
        # The geometry SET changed, so a one-time refit is wanted — let it happen
        # once the new previews finish loading (auto_range now fits to the new
        # set instead of the stale one).
        mw.mesh_canvas_view.request_refit()
        mw.mesh_canvas_view.update_geometry_previews(boundaries)
        mw.mesh_canvas_view.update_seed_previews(seeds)

    def handle_mesh_config_changed(self, cfg):
        """Callback when mesh config is modified or set in the config panel."""
        mw = self.main_window
        # Keep the shared config's per-file roles in step with panel edits, so
        # later layer-list actions (which re-apply global_mesh_config via
        # set_config) don't clobber a seed role the user just set. Only sync when
        # a distinct cfg arrives (i.e. from a role edit), never on the self-apply.
        gmc = getattr(self, "global_mesh_config", None)
        if gmc is not None and cfg is not gmc:
            # One sync, not a hand-picked subset. This used to copy geom_roles and
            # group_bc only (and later the length unit), which meant every OTHER field
            # the user had edited stayed stale in the model until the stage next ran.
            # sync_panel_to_model copies everything the panel authors and preserves
            # what it does not — see controllers/panel_sync_ctrl.py.
            self.sync_panel_to_model("mesh_config_panel")
        mw.mesh_canvas_view.update_mesh_config(cfg)
        self._refresh_mesh_previews(cfg)
        # Relabel the CAD-stage length fields and re-derive the solver's Linf. Cheap
        # and idempotent, so it runs on every config change rather than only on the
        # unit combo — a unit that reaches the mesh config by any other route (a
        # loaded .dat, a pipeline script, a workspace) must propagate too.
        self.sync_length_unit()


    def active_session(self) -> GeometrySession | None:
        if 0 <= self.active_idx < len(self.sessions):
            return self.sessions[self.active_idx]
        return None

    def active_canvas(self) -> CanvasView | None:
        return self.main_window.canvas_view


    def _apply_geometry_update(self, session: GeometrySession,
                               re_detect: bool = False):
        if session.original_points is None:
            self._clear_geometry_canvas(session)
            self._update_undo_redo_buttons(session)
            return
        points = session.original_points.copy()

        # Resolve the effective closure first (Auto derives it from the
        # geometry), so everything below reads an up-to-date pm.is_closed.
        pm = session.project_model
        pm.resolve_closure(session.original_points)

        # Logically close the curve for display / detection / overlays.
        if pm.is_closed and len(points) > 0:
            if not np.allclose(points[0], points[-1]):
                points = np.vstack((points, points[0]))

        # Update geometry on the shared canvas. The base geometry is ONE
        # polyline item, so it is told where NOT to join consecutive points.
        self.main_window.canvas_view.update_geometry(
            session.session_id, points,
            connect=self._geometry_connect(
                pm, len(session.original_points), len(points)))
        self.main_window.canvas_view.set_geometry_visible(session.session_id, session.is_visible)

        if re_detect:
            session.split_indices = ProjectModel.prune_degenerate_splits(
                self._auto_detect_features(points), points)

        # Only update active overlays if this is the active session
        if session is self.active_session():
            self.main_window.canvas_view.set_active_points(points)
            self.main_window.canvas_view.update_split_points(session.split_indices)
            session.selected_point_idx = None
            self.main_window.canvas_view.update_selected_point(None)
            self.refresh_status_selection()
            self.main_window.canvas_view.set_active_overlays_visible(session.is_visible)

            # Mark the auto-added closing segment distinctly; keep the sidebar
            # closure control + resolved-state hint in sync.
            self._refresh_closing_edge(session)
            self._sync_closed_mode_ui(session)

            # Reset sidebar point info
            sb = self.main_window.sidebar_view
            sb.show_vertex_selection(None)
        else:
            session.selected_point_idx = None

        self._sync_file_segments(session)
        self._update_undo_redo_buttons(session)

        # Live metrics for the active geometry. Fed the CLOSED point array (the
        # local `points`, which already has the closing vertex appended when the
        # geometry is closed) so the perimeter and the worst expansion ratio
        # include the seam interval — that is a real mesh edge, and the worst jump
        # is often exactly there.
        if session is self.active_session():
            self.main_window.sidebar_view.geom_stats_panel.update_stats(
                points, closed=bool(pm.is_closed),
                n_segments=len(session.project_model.segments),
                unit=self.length_unit_symbol())

        # Warn (red markers + log) about open / unstitched boundary endpoints.
        if session is self.active_session():
            self.detect_open_endpoints(session)

    def _sync_file_segments(self, session: GeometrySession):
        """Rebuild file segments from split_indices then update the sidebar list."""
        # Persist the de-degenerated split list so a phantom zero-length edge is
        # gone for good (its split markers clear, and a subsequent Remove sticks
        # instead of the rebuild resurrecting it from a stale boundary index).
        session.split_indices = ProjectModel.prune_degenerate_splits(
            session.split_indices, session.original_points)
        session.project_model.update_file_segments_from_indices(
            session.split_indices, points=session.original_points)
        if session is self.active_session():
            self._refresh_segment_list(clear_resampled=False)
        self._update_tab_title()

    # Undo / redo (global, across every CAD session plus project settings) lives
    # in controllers/undo_ctrl.py — see UndoControllerMixin.
