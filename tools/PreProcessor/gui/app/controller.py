"""
AppController — multi-session, command-pattern, preview/save-separated controller.
"""
from __future__ import annotations
import os
import tempfile
import numpy as np

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMenu

from app.views.main_window import MainWindow
from app.views.canvas import CanvasView
from app.models.session import GeometrySession
from app.models.mesh_config import MeshConfig
from app.models.project import ProjectModel

from app.controllers import (
    SessionControllerMixin,
    SessionLoadControllerMixin,
    SessionTabsControllerMixin,
    SessionIOControllerMixin,
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
    PostprocessControllerMixin,
    Stl3dControllerMixin,
    Stl3dFitControllerMixin,
    ExtrudeControllerMixin,
    PipelineControllerMixin,
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
    PostprocessControllerMixin,
    Stl3dControllerMixin,
    Stl3dFitControllerMixin,
    ExtrudeControllerMixin,
    PipelineControllerMixin,
    SignalWiringMixin,
    LifecycleControllerMixin,
):

    def __init__(self):
        self.main_window = MainWindow()
        self.main_window.controller = self
        self.sessions: list[GeometrySession] = []
        self.active_idx: int = -1
        
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

        self._is_populating = False       # guard against feedback loops during form population
        self._show_duplicate_preview = False  # flag to show duplicate preview line
        self._pending_seg = None          # analytic edge being created/edited (modeless dialog open)
        self._pending_dialog = None
        self._pending_is_new = True       # True = creating, False = editing an existing edge
        self._pending_orig = None         # original params snapshot (to restore on cancel of an edit)
        self._pending_orig_state = None   # full state snapshot (to make committing an edit undoable)
        # Pre-drag snapshot so an on-canvas vertex drag is one undo step.
        self._drag_orig_state = None
        self._custom_preview_fitted = False
        # Discrete-geometry editing (imported file edges): the connected shape is
        # edited by its corner vertices; each edge re-fits between its corners.
        self._pending_file = None         # (i0, i1) corners of the double-clicked edge
        self._pending_file_seg = None
        self._pending_file_dialog = None
        self._pending_geom_orig = None    # pristine original_points snapshot (revert)
        self._pending_geom_specs = None   # [{i0, i1, interior:[idx,...]}] per edge
        self._pending_geom_cur = None     # {corner_index: [x, y]} current corner positions
        self._pending_geom_corners = None # sorted corner indices (handle order)

        # Create a dedicated temp directory for the application lifecycle
        self.temp_dir = tempfile.mkdtemp(prefix="hybmesh_preprocessor_")
        QApplication.instance().aboutToQuit.connect(self.cleanup_temp_dir)

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
        self._autosave_timer = QTimer(self.main_window)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(60000)  # every 60 s


    # ═════════════════════════════════════════════════════════════════════
    # Coordination and Core Orchestration Methods
    # ═════════════════════════════════════════════════════════════════════

    def show_main_window(self):
        self.main_window.show()

    def handle_mode_changed(self, idx: int):
        """Update Mesh Config Panel and Mesh Canvas View when switching modes."""
        if idx in [1, 2]:  # Mesh Generator or Statistics Mode
            self.main_window.mesh_config_panel.set_config(self.global_mesh_config)
            
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
            gmc.geom_roles = dict(getattr(cfg, "geom_roles", {}) or {})
            # #4: keep per-group BC assignments current so the Solver "Detect from
            # Mesh" pre-seeds them even if the user hasn't regenerated since.
            gmc.group_bc = dict(getattr(cfg, "group_bc", {}) or {})
        mw.mesh_canvas_view.update_mesh_config(cfg)
        self._refresh_mesh_previews(cfg)


    def active_session(self) -> GeometrySession | None:
        if 0 <= self.active_idx < len(self.sessions):
            return self.sessions[self.active_idx]
        return None

    def active_canvas(self) -> CanvasView | None:
        return self.main_window.canvas_view


    def _apply_geometry_update(self, session: GeometrySession,
                               re_detect: bool = False):
        if session.original_points is None:
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

        # Update geometry on the shared canvas
        self.main_window.canvas_view.update_geometry(session.session_id, points)
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
            self.main_window.canvas_view.set_active_overlays_visible(session.is_visible)

            # Mark the auto-added closing segment distinctly; keep the sidebar
            # closure control + resolved-state hint in sync.
            self._refresh_closing_edge(session)
            self._sync_closed_mode_ui(session)

            # Reset sidebar point info
            sb = self.main_window.sidebar_view
            sb.selected_info.setText("Selected Vertex: None")
            sb.split_btn.setEnabled(False)
            sb.remove_split_btn.setEnabled(False)
        else:
            session.selected_point_idx = None

        self._sync_file_segments(session)
        self._update_undo_redo_buttons(session)

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

    # ═════════════════════════════════════════════════════════════════════
    # Undo / Redo
    # ═════════════════════════════════════════════════════════════════════

    def undo(self):
        session = self.active_session()
        if session:
            self._after_history_change(session, session.command_history.undo(), "Undo")

    def redo(self):
        session = self.active_session()
        if session:
            self._after_history_change(session, session.command_history.redo(), "Redo")

    def _after_history_change(self, session, cmd, verb: str):
        """Shared post-command bookkeeping for undo()/redo().

        The toolbar buttons are refreshed by ``CommandHistory.on_change`` fired
        from inside ``undo()``/``redo()``, so they are not re-toggled here.
        """
        if cmd is None:
            self.main_window.log_panel.log(f"Nothing to {verb.lower()}.")
            return
        self.main_window.log_panel.log(f"{verb} ({cmd.description()})")
        self._sync_geometry_list()
        self.redraw_canvas(announce=False)   # leave no stray highlight/handle
        # Reseed the edit baseline so the next in-place form edit diffs against
        # the restored state. to_dict() already returns a fresh dict, so the
        # previous extra deepcopy was redundant.
        if session.current_segment_idx >= 0:
            seg = session.project_model.get_segment(session.current_segment_idx)
            if seg:
                session.segment_state_snapshot = seg.to_dict()

    def _update_undo_redo_buttons(self, session: GeometrySession = None):
        """Enable or disable undo/redo buttons in toolbar based on history stack status."""
        if session is None:
            session = self.active_session()
        if session:
            can_undo = session.command_history.can_undo
            can_redo = session.command_history.can_redo
            self.main_window.undo_btn.setEnabled(can_undo)
            self.main_window.redo_btn.setEnabled(can_redo)
        else:
            self.main_window.undo_btn.setEnabled(False)
            self.main_window.redo_btn.setEnabled(False)
