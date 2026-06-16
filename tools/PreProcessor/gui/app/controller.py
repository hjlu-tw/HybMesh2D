"""
AppController — multi-session, command-pattern, preview/save-separated controller.
"""
from __future__ import annotations
import os
import tempfile
import copy
import numpy as np

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from app.views.main_window import MainWindow
from app.views.canvas import CanvasView
from app.models.session import GeometrySession
from app.models.mesh_config import MeshConfig

from app.controllers import (
    SessionControllerMixin,
    SegmentControllerMixin,
    TransformControllerMixin,
    CurveControllerMixin,
    BackendControllerMixin,
    MeshGenControllerMixin
)


class AppController(
    SessionControllerMixin,
    SegmentControllerMixin,
    TransformControllerMixin,
    CurveControllerMixin,
    BackendControllerMixin,
    MeshGenControllerMixin
):

    def __init__(self):
        self.main_window = MainWindow()
        self.main_window.controller = self
        self.sessions: list[GeometrySession] = []
        self.active_idx: int = -1
        
        self.global_mesh_config = MeshConfig()
        self.global_vtk_mesh = None
        self.global_vtk_path = ""

        self._is_populating = False       # guard against feedback loops during form population
        self._show_duplicate_preview = False  # flag to show duplicate preview line

        # Create a dedicated temp directory for the application lifecycle
        self.temp_dir = tempfile.mkdtemp(prefix="hybmesh_preprocessor_")
        QApplication.instance().aboutToQuit.connect(self.cleanup_temp_dir)

        # ── Wire static signals (sidebar → controller) ──────────────────
        sb = self.main_window.sidebar_view
        sb.load_btn.clicked.connect(self.load_geometry)
        sb.load_stl_btn.clicked.connect(self.load_stl_geometry)
        sb.load_json_btn.clicked.connect(self.load_json_config)
        sb.split_btn.clicked.connect(self.add_split_point)
        sb.remove_split_btn.clicked.connect(self.remove_split_point)
        sb.insert_btn.clicked.connect(self.handle_insert_point)
        # Discrete and analytic edges share one unified list now.
        sb.segment_list.itemSelectionChanged.connect(self.handle_segment_list_selected)
        sb.strategy_combo.currentTextChanged.connect(
            self.handle_strategy_changed)
        sb.is_closed_combo.currentTextChanged.connect(
            self.handle_is_closed_changed)
        if sb.preview_btn:
            sb.preview_btn.clicked.connect(self.preview_backend)
        if sb.file_preview_btn:
            sb.file_preview_btn.clicked.connect(self.preview_backend)
        sb.save_btn.clicked.connect(self.save_output)
        sb.generate_btn.clicked.connect(self.generate_json)
        sb.add_curve_seg_btn.clicked.connect(self.add_curve_segment)
        sb.curve_preview_btn.clicked.connect(self.preview_curve_formula)
        
        # Wire live preview for curve editing
        for w in [sb.curve_t_min, sb.curve_t_max, sb.curve_n,
                  sb.curve_start_node, sb.curve_end_node,
                  sb.h_line_y, sb.h_line_x_start, sb.h_line_x_end,
                  sb.v_line_x, sb.v_line_y_start, sb.v_line_y_end,
                  sb.line_x0, sb.line_y0, sb.line_x1, sb.line_y1,
                  sb.circle_cx, sb.circle_cy, sb.circle_r,
                  sb.tri_x0, sb.tri_y0, sb.tri_x1, sb.tri_y1, sb.tri_x2, sb.tri_y2,
                  sb.quad_x0, sb.quad_y0, sb.quad_x1, sb.quad_y1,
                  sb.quad_x2, sb.quad_y2, sb.quad_x3, sb.quad_y3]:
            w.valueChanged.connect(self.preview_curve_formula)
        for w in [sb.curve_x_formula, sb.curve_y_formula, sb.curve_formula]:
            w.textChanged.connect(self.preview_curve_formula)
        sb.poly_vertices.textChanged.connect(self.preview_curve_formula)
        sb.curve_mode_param.toggled.connect(self.handle_curve_type_changed)
        sb.curve_type_combo.currentIndexChanged.connect(self.handle_curve_type_changed)

        # Undo / Redo / Remove / Quality Check
        self.main_window.undo_btn.clicked.connect(self.undo)
        self.main_window.redo_btn.clicked.connect(self.redo)
        sb.remove_seg_btn.clicked.connect(self.remove_selected_segment)
        sb.curve_bake_btn.clicked.connect(self.bake_selected_curve)
        self.main_window.quality_check_cb.toggled.connect(self.handle_quality_check_toggled)
        self.main_window.quality_mode_combo.currentTextChanged.connect(self.handle_quality_mode_changed)
        self.main_window.show_vertices_cb.toggled.connect(self.handle_show_vertices_toggled)
        self.main_window.show_nodes_cb.toggled.connect(self.handle_show_nodes_toggled)
        sb.dup_btn.clicked.connect(self.duplicate_with_transform)

        # Parameter-change signals (all route to update_segment_params)
        for widget in [sb.uniform_n, sb.tanh_n, sb.tanh_intensity,
                       sb.cosine_n, sb.curv_n, sb.curv_sens,
                       sb.geo_n, sb.geo_ratio, sb.geo_ratio_end, sb.uniform_spacing]:
            widget.valueChanged.connect(self.update_segment_params)
        sb.uniform_type_combo.currentTextChanged.connect(
            self.update_segment_params)
        sb.match_previous_cb.toggled.connect(self.update_match_previous)
        sb.auto_split_btn.clicked.connect(self.auto_detect_segments_from_button)

        # Wire duplicate live preview connections
        sb.dup_interactive_btn.toggled.connect(self.handle_dup_interactive_toggled)
        sb.dup_type_combo.currentIndexChanged.connect(self.handle_dup_type_changed)
        sb.dup_base_mode_combo.currentIndexChanged.connect(self.handle_dup_base_mode_changed)
        sb.dup_delete_orig_cb.toggled.connect(self.on_duplicate_param_changed)
        for w in [sb.dup_rot_angle, sb.dup_rot_px, sb.dup_rot_py,
                  sb.dup_mh_py, sb.dup_mv_px,
                  sb.dup_ma_px, sb.dup_ma_py, sb.dup_ma_dx, sb.dup_ma_dy,
                  sb.dup_ps_px, sb.dup_ps_py,
                  sb.dup_trans_dx, sb.dup_trans_dy,
                  sb.dup_scale_factor, sb.dup_scale_px, sb.dup_scale_py]:
            w.valueChanged.connect(self.on_duplicate_param_changed)

        # Advanced settings
        sb.global_spline_cb.toggled.connect(self.handle_global_spline_changed)

        # New tab button
        sb.new_tab_btn.clicked.connect(self.new_blank_tab)
        sb.auto_detect_btn.clicked.connect(self.auto_detect_segments)

        # Geometries visibility / focus
        sb.geom_list.itemChanged.connect(self.handle_geom_visibility_changed)
        sb.geom_list.currentRowChanged.connect(self.handle_geom_list_row_changed)
        sb.geom_list.itemDoubleClicked.connect(self.handle_geom_list_double_clicked)
        self.main_window.focus_geom_btn.clicked.connect(self.focus_to_selected_geometry)
        sb.toggle_visibility_btn.clicked.connect(self.toggle_selected_geometry_visibility)
        sb.geometry_panel.context_menu_requested.connect(self.show_geometry_context_menu)

        # ── Wire tab signals ────────────────────────────────────────────
        tw = self.main_window.tab_widget
        tw.tabCloseRequested.connect(self.close_tab)
        tw.currentChanged.connect(self.switch_tab)

        # Mesh Generator / Statistics have their own (shared-state) tab strip.
        self.main_window.mesh_tab_bar.tabCloseRequested.connect(self.close_mesh_tab)

        # ── Wire shared canvas signals ──────────────────────────────────
        self.main_window.canvas_view.point_clicked.connect(self.handle_point_clicked)
        self.main_window.canvas_view.point_deselected.connect(self.handle_point_deselected)
        self.main_window.canvas_view.segment_clicked.connect(self.handle_canvas_segment_clicked)
        self.main_window.canvas_view.box_selected.connect(self.handle_canvas_box_selected)
        # Live drag of the transform base point / mirror axis on the canvas.
        self.main_window.canvas_view.transform_handle_cb = self._on_transform_handle_dragged

        # Wire Selection Mode dropdown
        mw = self.main_window
        def _on_selection_mode_changed(index):
            mode = 'vertex' if index == 0 else 'edge'
            # Drop any edge/vertex selection carried over from the previous mode
            # so switching modes always starts from a clean slate (important when
            # several geometry layers are loaded).
            self._clear_cad_selection()
            self.main_window.canvas_view.set_selection_mode(mode)

        mw.select_mode_combo.currentIndexChanged.connect(_on_selection_mode_changed)
        # Default the CAD canvas to Edge mode. The combo is preset to "Edge"
        # before this signal was wired, so push the mode into the canvas once
        # to apply its overlay / box-select side effects.
        self.main_window.canvas_view.set_selection_mode(
            'vertex' if mw.select_mode_combo.currentIndex() == 0 else 'edge')

        # ── Wire Mesh Generation signals ───────────────────────────────
        mw = self.main_window
        mw.mode_changed.connect(self.handle_mode_changed)
        
        mw.mesh_config_panel.load_config_btn.clicked.connect(self.load_mesh_config)
        mw.mesh_config_panel.save_config_btn.clicked.connect(self.save_mesh_config)
        mw.mesh_config_panel.add_active_geom_btn.clicked.connect(self.add_active_preprocessor_geometry)
        mw.mesh_config_panel.preview_btn.clicked.connect(self.preview_mesh_generator)
        mw.mesh_config_panel.run_mesh_btn.clicked.connect(self.run_mesh_generator)
        mw.mesh_config_panel.cancel_mesh_btn.clicked.connect(self.cancel_mesh_generator)
        mw.mesh_config_panel.geom_files_changed.connect(self.handle_mesh_geom_files_changed)
        mw.mesh_config_panel.mesh_config_changed.connect(self.handle_mesh_config_changed)
        mw.mesh_config_panel.layers_list_widget.itemChanged.connect(self.handle_mesh_layer_toggled)
        mw.mesh_config_panel.add_all_sessions_btn.clicked.connect(self.add_all_sessions_to_mesh)

        # Toolbar Mesh Buttons
        mw.mesh_preview_btn.clicked.connect(self.preview_mesh_generator)
        mw.mesh_generate_btn.clicked.connect(self.run_mesh_generator)
        mw.mesh_cancel_btn.clicked.connect(self.cancel_mesh_generator)
        mw.mesh_config_panel.export_vtk_btn.clicked.connect(self.export_generated_vtk)
        mw.mesh_config_panel.export_starcd_btn.clicked.connect(self.export_star_cd)
        mw.mesh_focus_btn.clicked.connect(mw.mesh_canvas_view.auto_range)

        # Wire Toolbar Toggles & Synchronization with Sidebar Panel
        def _make_sync_checkbox_fn(canvas_method, cb_sidebar, cb_toolbar):
            def sync_fn(checked):
                canvas_method(checked)
                for cb in (cb_sidebar, cb_toolbar):
                    cb.blockSignals(True)
                    cb.setChecked(checked)
                    cb.blockSignals(False)
            return sync_fn

        sync_wireframe = _make_sync_checkbox_fn(
            mw.mesh_canvas_view.set_wireframe_visible,
            mw.mesh_stats_panel.show_wireframe_cb,
            mw.mesh_show_wireframe_cb
        )
        sync_bc = _make_sync_checkbox_fn(
            mw.mesh_canvas_view.set_bc_coloring_visible,
            mw.mesh_stats_panel.show_bc_coloring_cb,
            mw.mesh_show_bc_cb
        )
        sync_domain = _make_sync_checkbox_fn(
            mw.mesh_canvas_view.set_domain_box_visible,
            mw.mesh_stats_panel.show_domain_box_cb,
            mw.mesh_show_domain_cb
        )

        def sync_color_mode(text):
            mode_map = {
                "Element Type": "element_type",
                "Quality (Aspect Ratio)": "quality_aspect",
                "Quality (Skewness)": "quality_skewness",
                "Uniform": "uniform"
            }
            mode_val = mode_map.get(text, "uniform")
            mw.mesh_canvas_view.set_color_mode(mode_val)
            
            # Sync toolbar
            mw.mesh_color_mode_combo.blockSignals(True)
            mw.mesh_color_mode_combo.setCurrentText(text)
            mw.mesh_color_mode_combo.blockSignals(False)
            
            # Sync sidebar panel
            mw.mesh_stats_panel.color_mode_combo.blockSignals(True)
            mw.mesh_stats_panel.color_mode_combo.setCurrentText(text)
            mw.mesh_stats_panel.color_mode_combo.blockSignals(False)

        mw.mesh_show_wireframe_cb.toggled.connect(sync_wireframe)
        mw.mesh_stats_panel.show_wireframe_cb.toggled.connect(sync_wireframe)
        
        mw.mesh_show_bc_cb.toggled.connect(sync_bc)
        mw.mesh_stats_panel.show_bc_coloring_cb.toggled.connect(sync_bc)
        
        mw.mesh_show_domain_cb.toggled.connect(sync_domain)
        mw.mesh_stats_panel.show_domain_box_cb.toggled.connect(sync_domain)

        mw.mesh_color_mode_combo.currentTextChanged.connect(sync_color_mode)
        mw.mesh_stats_panel.color_mode_combo.currentTextChanged.connect(sync_color_mode)

        # Wire stats panel buttons
        mw.mesh_stats_panel.fit_view_requested.connect(mw.mesh_canvas_view.auto_range)
        mw.mesh_stats_panel.export_vtk_requested.connect(self.export_generated_vtk)
        mw.mesh_stats_panel.export_star_cd_requested.connect(self.export_star_cd)


        # ── Keyboard shortcuts ──────────────────────────────────────────
        self.main_window.setup_shortcuts(self)

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

    def _maybe_recover_autosave(self) -> bool:
        """Offer to restore an autosave left behind by an unclean shutdown."""
        try:
            if not os.path.exists(self._autosave_path):
                return False
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self.main_window,
                "Recover Unsaved Work",
                "Unsaved work from a previous session was found — the application "
                "may have closed unexpectedly.\n\nRecover it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._read_workspace_file(self._autosave_path)
                self.main_window.log_panel.log("Recovered autosaved workspace.")
                return len(self.sessions) > 0
            # User declined: drop the stale autosave so we don't ask again.
            os.remove(self._autosave_path)
        except Exception as e:
            try:
                self.main_window.log_panel.log(f"Autosave recovery failed: {e}")
            except Exception:
                pass
        return False

    def _autosave(self):
        """Periodically checkpoint modified sessions to the stable autosave path."""
        try:
            if not self.sessions:
                return
            if not any(getattr(s, "is_geometry_modified", False) for s in self.sessions):
                return
            self._write_workspace_file(self._autosave_path)
        except Exception:
            # A background autosave must never interrupt the user (e.g. a
            # transient NaN while editing a live curve); fail silently.
            pass


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

    def handle_mesh_geom_files_changed(self, geom_files: list[str]):
        """Callback when geometry files in mesh config panel are modified."""
        mw = self.main_window
        mw.mesh_canvas_view.update_geometry_previews(geom_files)
        mw.mesh_canvas_view.auto_range()

    def handle_mesh_config_changed(self, cfg):
        """Callback when mesh config is modified or set in the config panel."""
        mw = self.main_window
        mw.mesh_canvas_view.update_mesh_config(cfg)
        mw.mesh_canvas_view.update_geometry_previews(cfg.geom_files)


    def active_session(self) -> GeometrySession | None:
        if 0 <= self.active_idx < len(self.sessions):
            return self.sessions[self.active_idx]
        return None

    def active_canvas(self) -> CanvasView | None:
        return self.main_window.canvas_view

    def cleanup_temp_dir(self):
        """Clean up the dedicated temp directory and all its contents on app exit."""
        if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception:
                pass

    def _apply_geometry_update(self, session: GeometrySession,
                               re_detect: bool = False):
        if session.original_points is None:
            self._update_undo_redo_buttons(session)
            return
        points = session.original_points.copy()

        # Logically close the curve
        pm = session.project_model
        if pm.is_closed and len(points) > 0:
            if not np.allclose(points[0], points[-1]):
                points = np.vstack((points, points[0]))

        # Update geometry on the shared canvas
        self.main_window.canvas_view.update_geometry(session.session_id, points)
        self.main_window.canvas_view.set_geometry_visible(session.session_id, session.is_visible)

        if re_detect:
            session.split_indices = self._auto_detect_features(points)

        # Only update active overlays if this is the active session
        if session is self.active_session():
            self.main_window.canvas_view.set_active_points(points)
            self.main_window.canvas_view.update_split_points(session.split_indices)
            session.selected_point_idx = None
            self.main_window.canvas_view.update_selected_point(None)
            self.main_window.canvas_view.set_active_overlays_visible(session.is_visible)

            # Reset sidebar point info
            sb = self.main_window.sidebar_view
            sb.selected_info.setText("Selected Vertex: None")
            sb.split_btn.setEnabled(False)
            sb.remove_split_btn.setEnabled(False)
        else:
            session.selected_point_idx = None

        self._sync_file_segments(session)
        self._update_undo_redo_buttons(session)

    def _sync_file_segments(self, session: GeometrySession):
        """Rebuild file segments from split_indices then update the sidebar list."""
        session.project_model.update_file_segments_from_indices(
            session.split_indices)
        if session is self.active_session():
            self._refresh_segment_list(clear_resampled=False)
        self._update_tab_title()

    # ═════════════════════════════════════════════════════════════════════
    # Undo / Redo
    # ═════════════════════════════════════════════════════════════════════

    def undo(self):
        session = self.active_session()
        if session:
            cmd = session.command_history.undo()
            if cmd:
                desc = cmd.description()
                self.main_window.log_panel.log(f"Undo ({desc})")
                self._sync_geometry_list()
                if session.current_segment_idx >= 0:
                    seg = session.project_model.get_segment(session.current_segment_idx)
                    if seg:
                        session.segment_state_snapshot = copy.deepcopy(seg.to_dict())
            else:
                self.main_window.log_panel.log("Nothing to undo.")
            self._update_undo_redo_buttons(session)

    def redo(self):
        session = self.active_session()
        if session:
            cmd = session.command_history.redo()
            if cmd:
                desc = cmd.description()
                self.main_window.log_panel.log(f"Redo ({desc})")
                self._sync_geometry_list()
                if session.current_segment_idx >= 0:
                    seg = session.project_model.get_segment(session.current_segment_idx)
                    if seg:
                        session.segment_state_snapshot = copy.deepcopy(seg.to_dict())
            else:
                self.main_window.log_panel.log("Nothing to redo.")
            self._update_undo_redo_buttons(session)

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

    def handle_close_event(self) -> bool:
        """Return True if the app can close, False to cancel closing."""
        modified_sessions = [s for s in self.sessions if s.is_geometry_modified]
        if modified_sessions:
            names = ", ".join([s.display_name for s in modified_sessions])
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self.main_window,
                "Unsaved Changes",
                f"The following sessions have unsaved changes:\n{names}\n\nDo you want to discard them and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return False
        
        # Auto-save workspace on successful exit (disabled to start clean)
        pass

        # Cancel and wait for all running background workers/threads to avoid crash on exit
        if hasattr(self, "_worker") and self._worker is not None:
            if self._worker.isRunning():
                self._worker.cancel()
                self._worker.wait()
                
        if hasattr(self, "_mesh_worker") and self._mesh_worker is not None:
            if self._mesh_worker.isRunning():
                self._mesh_worker.cancel()
                self._mesh_worker.wait()

        mcv = self.main_window.mesh_canvas_view
        loader_threads = list(getattr(mcv, "_geom_loader_threads", []))
        last = getattr(mcv, "_geom_loader_thread", None)
        if last is not None and last not in loader_threads:
            loader_threads.append(last)
        for t in loader_threads:
            if t is not None and t.isRunning():
                try:
                    t.loaded_signal.disconnect()
                except TypeError:
                    pass
                t.wait()

        # Clean shutdown: stop autosave and remove its file so the next launch
        # does not offer to "recover" an intentionally-closed session.
        try:
            if getattr(self, "_autosave_timer", None) is not None:
                self._autosave_timer.stop()
            ap = getattr(self, "_autosave_path", None)
            if ap and os.path.exists(ap):
                os.remove(ap)
        except Exception:
            pass

        try:
            self.main_window.canvas_view.clear()
            self.main_window.mesh_canvas_view.clear_mesh()
        except Exception:
            pass
        return True
