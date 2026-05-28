"""
AppController — multi-session, command-pattern, preview/save-separated controller.
"""
from __future__ import annotations
import os
import tempfile
import copy
import numpy as np

from PyQt6.QtWidgets import QApplication

from app.views.main_window import MainWindow
from app.views.canvas import CanvasView
from app.models.session import GeometrySession

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
        self.sessions: list[GeometrySession] = []
        self.active_idx: int = -1

        self._is_populating = False       # guard against feedback loops during form population
        self._show_duplicate_preview = False  # flag to show duplicate preview line

        # Create a dedicated temp directory for the application lifecycle
        self.temp_dir = tempfile.mkdtemp(prefix="hybmesh_preprocessor_")
        QApplication.instance().aboutToQuit.connect(self.cleanup_temp_dir)

        # ── Wire static signals (sidebar → controller) ──────────────────
        sb = self.main_window.sidebar_view
        sb.load_btn.clicked.connect(self.load_geometry)
        sb.load_json_btn.clicked.connect(self.load_json_config)
        sb.split_btn.clicked.connect(self.add_split_point)
        sb.remove_split_btn.clicked.connect(self.remove_split_point)
        sb.insert_btn.clicked.connect(self.handle_insert_point)
        sb.file_segment_list.currentRowChanged.connect(self.handle_file_segment_selected)
        sb.curve_segment_list.currentRowChanged.connect(self.handle_curve_segment_selected)
        sb.strategy_combo.currentTextChanged.connect(
            self.handle_strategy_changed)
        sb.is_closed_combo.currentTextChanged.connect(
            self.handle_is_closed_changed)
        sb.preview_btn.clicked.connect(self.preview_backend)
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

        # ── Wire tab signals ────────────────────────────────────────────
        tw = self.main_window.tab_widget
        tw.tabCloseRequested.connect(self.close_tab)
        tw.currentChanged.connect(self.switch_tab)

        # ── Wire shared canvas signals ──────────────────────────────────
        self.main_window.canvas_view.point_clicked.connect(self.handle_point_clicked)

        # ── Wire Mesh Generation signals ───────────────────────────────
        mw = self.main_window
        mw.mode_changed.connect(self.handle_mode_changed)
        mw.mesh_config_panel.load_config_btn.clicked.connect(self.load_mesh_config)
        mw.mesh_config_panel.save_config_btn.clicked.connect(self.save_mesh_config)
        mw.mesh_config_panel.add_active_geom_btn.clicked.connect(self.add_active_preprocessor_geometry)
        mw.mesh_config_panel.run_mesh_btn.clicked.connect(self.run_mesh_generator)
        mw.mesh_config_panel.cancel_mesh_btn.clicked.connect(self.cancel_mesh_generator)

        # Wire Mesh Statistics controls & export
        mw.mesh_stats_panel.color_mode_changed.connect(mw.mesh_canvas_view.set_color_mode)
        mw.mesh_stats_panel.fit_view_requested.connect(mw.mesh_canvas_view.auto_range)
        mw.mesh_stats_panel.show_domain_box_toggled.connect(mw.mesh_canvas_view.set_domain_box_visible)
        mw.mesh_stats_panel.show_bc_coloring_toggled.connect(mw.mesh_canvas_view.set_bc_coloring_visible)
        mw.mesh_stats_panel.show_wireframe_toggled.connect(mw.mesh_canvas_view.set_wireframe_visible)
        mw.mesh_stats_panel.export_vtk_requested.connect(self.export_generated_vtk)
        mw.mesh_stats_panel.export_star_cd_requested.connect(self.export_star_cd)


        # ── Keyboard shortcuts ──────────────────────────────────────────
        self.main_window.setup_shortcuts(self)

    # ═════════════════════════════════════════════════════════════════════
    # Coordination and Core Orchestration Methods
    # ═════════════════════════════════════════════════════════════════════

    def show_main_window(self):
        self.main_window.show()

    def handle_mode_changed(self, idx: int):
        """Update Mesh Config Panel and Mesh Canvas View when switching modes."""
        session = self.active_session()
        if not session:
            return
        if idx == 1:  # Mesh Generator Mode
            self.main_window.mesh_config_panel.set_config(session.mesh_config)
            
            vtk_path = session.vtk_path if session.vtk_path else (self._get_expected_vtk_path(session.mesh_config) if session.mesh_config else "")
            self.main_window.mesh_stats_panel.update_stats(session.vtk_mesh, vtk_path)
            
            self.main_window.mesh_canvas_view.update_mesh_config(session.mesh_config)
            if session.vtk_mesh:
                self.main_window.mesh_canvas_view.render_mesh(session.vtk_mesh)
            else:
                self.main_window.mesh_canvas_view.clear_mesh()


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

    def _sync_file_segments(self, session: GeometrySession):
        """Rebuild file segments from split_indices then update the sidebar list."""
        session.project_model.update_file_segments_from_indices(
            session.split_indices)
        if session is self.active_session():
            self._refresh_segment_list()
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
