"""
AppController — multi-session, command-pattern, preview/save-separated controller.
"""
from __future__ import annotations
import os
import math
import tempfile
import copy

import numpy as np
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QListWidgetItem, QApplication
from PyQt6.QtCore import QTimer, Qt

from app.views.main_window import MainWindow
from app.views.canvas import CanvasView
from app.views.output_dialog import OutputDialog
from app.models.session import GeometrySession
from app.models.project import ProjectModel
from app.models.segment import SegmentModel
from app.workers.backend_run import BackendWorker
from app.commands.split_cmds import AddSplitCmd, RemoveSplitCmd, AutoDetectSplitCmd
from app.commands.vertex_cmds import InsertVertexCmd
from app.commands.segment_cmds import (
    UpdateStrategyCmd, RemoveSegmentCmd,
    AddCurveSegmentCmd, ToggleIsClosedCmd, ToggleGlobalSplineCmd, ToggleMatchPreviousCmd, UpdateSegmentStateCmd,
    CreateSegmentsFromIndicesCmd, BakeCurveToGeometryCmd, DuplicateTransformCmd
)


# ── Formula evaluator (Python-side, for canvas preview only) ─────────────────

def _eval_formula(expr: str, var_name: str, val: float) -> float:
    """Safely evaluate a single math expression."""
    safe = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    safe["pi"] = math.pi
    safe[var_name] = float(val)
    try:
        return float(eval(expr.replace("^", "**"), {"__builtins__": {}}, safe))
    except Exception:
        return float("nan")


def _eval_formula_array(expr: str, var_name: str,
                        vals: np.ndarray) -> np.ndarray:
    return np.array([_eval_formula(expr, var_name, v) for v in vals])


def _parse_vertices_str(s: str) -> np.ndarray:
    pairs = s.split(";")
    pts = []
    for p in pairs:
        if not p.strip():
            continue
        parts = p.split(",")
        if len(parts) == 2:
            try:
                pts.append([float(parts[0].strip()), float(parts[1].strip())])
            except ValueError:
                pass
    if len(pts) < 2:
        return np.array([[0.0, 0.0], [1.0, 1.0]])
    return np.array(pts)


def _sample_polyline_pinned(vertices: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Sample n points along a closed polyline, guaranteeing that every specified
    vertex is included in the output. Interior points are distributed between
    vertices proportionally to each edge's length, resolving ties/remainders
    stably using fractional remainders to match the C++ backend.

    Args:
        vertices: shape (k+1, 2) where vertices[0] == vertices[-1] (closed polygon)
        n: total output points, including all k distinct vertices plus the
           repeated first vertex at the end.  n must be >= k+1.
    Returns:
        (xs, ys): 1-D arrays of length n
    """
    k = len(vertices) - 1          # number of distinct vertices / edges
    if k < 1:
        return np.full(n, vertices[0, 0]), np.full(n, vertices[0, 1])

    diffs = np.diff(vertices, axis=0)
    edge_lengths = np.sqrt(np.sum(diffs ** 2, axis=1))  # shape (k,)
    L_total = float(np.sum(edge_lengths))

    if L_total < 1e-12:
        return np.full(n, vertices[0, 0]), np.full(n, vertices[0, 1])

    # n_pinned = k distinct vertices + 1 repeated start vertex = k+1
    n_pinned = k + 1
    n_interior = max(0, n - n_pinned)   # interior (non-vertex) points to distribute

    # Proportional allocation of interior points per edge
    exact = n_interior * edge_lengths / L_total
    edge_interior = np.floor(exact).astype(int)
    remainders = exact - edge_interior

    # Distribute any remaining points using stable sort on fractional remainders descending
    remaining = n_interior - int(np.sum(edge_interior))
    if remaining > 0:
        order = np.argsort(-remainders, kind='stable')
        for i in range(remaining):
            edge_interior[order[i % k]] += 1

    # Build output: for each edge, emit vertex then interior points
    xs: list[float] = []
    ys: list[float] = []
    for i in range(k):
        v_s = vertices[i]
        v_e = vertices[i + 1]
        xs.append(float(v_s[0]))
        ys.append(float(v_s[1]))
        ni = int(edge_interior[i])
        for j in range(1, ni + 1):
            t = j / (ni + 1)
            xs.append(float(v_s[0] + t * (v_e[0] - v_s[0])))
            ys.append(float(v_s[1] + t * (v_e[1] - v_s[1])))
    # Close: append repeated first vertex
    xs.append(float(vertices[-1][0]))
    ys.append(float(vertices[-1][1]))

    return np.array(xs), np.array(ys)


def _resample_polyline_uniform(xs: np.ndarray, ys: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Resample a 2D polyline (xs, ys) to have n points spaced uniformly in arc length.
    Matches the C++ backend's linear interpolation logic.
    """
    if len(xs) < 2:
        return xs, ys
    dx = np.diff(xs)
    dy = np.diff(ys)
    dists = np.sqrt(dx**2 + dy**2)
    s = np.zeros(len(xs))
    s[1:] = np.cumsum(dists)
    
    L = s[-1]
    if L < 1e-12:
        return np.linspace(xs[0], xs[-1], n), np.linspace(ys[0], ys[-1], n)
        
    tS = np.linspace(0.0, L, n)
    xs_new = np.interp(tS, s, xs)
    ys_new = np.interp(tS, s, ys)
    return xs_new, ys_new

# ═════════════════════════════════════════════════════════════════════════════

class AppController:

    def __init__(self):
        self.main_window = MainWindow()
        self.sessions: list[GeometrySession] = []
        self.active_idx: int = -1

        self._connecting_signals = False  # guard against re-entrant connects
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

        # ── Keyboard shortcuts ──────────────────────────────────────────
        self.main_window.setup_shortcuts(self)

    # ═════════════════════════════════════════════════════════════════════
    # Session helpers
    # ═════════════════════════════════════════════════════════════════════

    def show_main_window(self):
        self.main_window.show()

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

    def new_blank_tab(self):
        self._new_session("")

    def auto_detect_segments(self, angle_threshold_deg: float = 30.0):
        """Auto-detect segment boundaries based on sharp angles.

        Args:
            angle_threshold_deg: The angle (in degrees) above which a corner
                is considered sharp enough to split. Default is 30 degrees.
        """
        session = self.active_session()
        if not session or session.original_points is None:
            self.main_window.log_panel.log("No geometry loaded.")
            return

        points = session.original_points.copy()
        pm = session.project_model
        if pm.is_closed and len(points) > 0:
            if not np.allclose(points[0], points[-1]):
                points = np.vstack((points, points[0]))

        new_indices = self._auto_detect_features(points, angle_threshold_deg)
        cmd = AutoDetectSplitCmd(
            session, new_indices,
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Auto-detected {len(new_indices) - 1} edges based on sharp angles (threshold: {angle_threshold_deg}°).")

    def auto_detect_segments_from_button(self):
        """Slot for the Auto Detect Segments button.

        If a segment is selected, only splits that segment (works for both file and curve segments).
        Otherwise, splits the entire geometry.
        """
        session = self.active_session()
        if not session:
            return

        # Check if a segment is selected (file or curve)
        seg_idx = session.current_segment_idx
        seg = None
        if 0 <= seg_idx < len(session.project_model.segments):
            seg = session.project_model.get_segment(seg_idx)

        # Retrieve the custom threshold angle from the sidebar UI
        sb = self.main_window.sidebar_view
        angle_threshold = sb.auto_split_angle_sb.value()

        if seg:
            # If it's a file segment, we need original_points to be loaded
            if seg.type == "file" and session.original_points is None:
                self.main_window.log_panel.log("No geometry loaded for file segment.")
                return

            # Detect features (works for both file and curve segments)
            new_indices = self._auto_detect_features_for_segment(seg_idx, angle_threshold)
            if len(new_indices) >= 2:
                cmd = CreateSegmentsFromIndicesCmd(
                    session, seg_idx, new_indices,
                    refresh_cb=lambda: self._apply_geometry_update(session))
                session.command_history.execute(cmd)
                self.main_window.log_panel.log(
                    f"Auto-detected {len(new_indices) - 1} sub-edges for edge {seg.id} (threshold: {angle_threshold}°).")
            else:
                self.main_window.log_panel.log("No sharp corners detected for selected edge.")
            return

        # No segment selected - split entire geometry
        if session.original_points is None:
            self.main_window.log_panel.log("No geometry loaded.")
            return
        self.auto_detect_segments(angle_threshold_deg=angle_threshold)

    def _new_session(self, file_path: str = "") -> GeometrySession:
        """Create a session and add a tab to the shared canvas."""
        session = GeometrySession(file_path)
        session.controller = self  # Store controller reference for commands

        # Append BEFORE addTab so switch_tab (triggered by currentChanged)
        # can already find the session in self.sessions
        self.sessions.append(session)

        # Add tab (may trigger currentChanged → switch_tab)
        label = os.path.basename(file_path) if file_path else "Untitled"
        self.main_window.tab_widget.addTab(label)

        # Add geometry layer to the shared canvas
        self.main_window.canvas_view.add_geometry(
            session.session_id, None, session.color)
        self.main_window.canvas_view.set_geometry_visible(
            session.session_id, session.is_visible)

        # Explicitly set active index to the new tab
        new_idx = len(self.sessions) - 1
        self.active_idx = new_idx
        self.main_window.tab_widget.setCurrentIndex(new_idx)
        self._sync_geometry_list()
        return session

    def switch_tab(self, idx: int):
        if idx < 0 or idx >= len(self.sessions):
            self.active_idx = -1
            return
        self.active_idx = idx
        self._sync_sidebar_to_session()
        session = self.active_session()
        if session:
            self.main_window.update_title(
                session.display_name, session.is_geometry_modified)
            
            # Select corresponding row in sidebar geometries list
            sb = self.main_window.sidebar_view
            sb.geom_list.blockSignals(True)
            if 0 <= idx < sb.geom_list.count():
                sb.geom_list.setCurrentRow(idx)
            sb.geom_list.blockSignals(False)

            # Switch active geometries on the shared canvas
            self.main_window.canvas_view.highlight_geometry(session.session_id)
            
            # Use closed points for active points to prevent index out of bounds
            pts = session.original_points
            if pts is not None:
                pts = pts.copy()
                if session.project_model.is_closed and len(pts) > 0:
                    if not np.allclose(pts[0], pts[-1]):
                        pts = np.vstack((pts, pts[0]))
            self.main_window.canvas_view.set_active_points(pts)
            
            # Clear overlays first, then rebuild active overlays
            self.main_window.canvas_view.clear_active_overlays()
            self._show_duplicate_preview = False
            self.main_window.canvas_view.clear_duplicate_preview()
            if session.original_points is not None:
                self.main_window.canvas_view.update_split_points(session.split_indices)
                self.main_window.canvas_view.update_selected_point(session.selected_point_idx)
                
                # Active segment
                if session.current_segment_idx >= 0 and session.current_segment_idx < len(session.project_model.segments):
                    seg = session.project_model.segments[session.current_segment_idx]
                    self.main_window.canvas_view.update_active_segment(seg.start_index, seg.end_index)
            
            # Resampled preview
            if session.resampled_points is not None:
                self.main_window.canvas_view.load_resampled_data(
                    session.resampled_points, self.main_window.quality_check_cb.isChecked())
            
            # Sync active overlays visibility with session visibility
            self.main_window.canvas_view.set_active_overlays_visible(session.is_visible)

    def close_tab(self, idx: int):
        if idx < 0 or idx >= len(self.sessions):
            return
        session = self.sessions[idx]
        if session.is_geometry_modified:
            reply = QMessageBox.question(
                self.main_window,
                "Unsaved Changes",
                f"'{session.display_name}' has unsaved changes. Close anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

        # Remove geometry from shared canvas
        self.main_window.canvas_view.remove_geometry(session.session_id)

        # Block signals during tab removal and list popping to keep states synchronized
        self.main_window.tab_widget.blockSignals(True)
        self.main_window.tab_widget.removeTab(idx)
        self.sessions.pop(idx)
        self.main_window.tab_widget.blockSignals(False)

        # Adjust active index
        n = len(self.sessions)
        if n == 0:
            self.active_idx = -1
            self._clear_sidebar()
            self.main_window.canvas_view.clear_active_overlays()
            self.main_window.canvas_view.set_active_points(None)
            self._sync_geometry_list()
        else:
            # Shift active_idx appropriately
            if idx == self.active_idx:
                self.active_idx = min(idx, n - 1)
            elif idx < self.active_idx:
                self.active_idx -= 1
            # If idx > active_idx, self.active_idx is unchanged

            self.main_window.tab_widget.blockSignals(True)
            self.main_window.tab_widget.setCurrentIndex(self.active_idx)
            self.main_window.tab_widget.blockSignals(False)
            self._sync_geometry_list()
            self.switch_tab(self.active_idx)

    def _update_tab_title(self):
        session = self.active_session()
        if session and 0 <= self.active_idx < self.main_window.tab_widget.count():
            self.main_window.tab_widget.setTabText(
                self.active_idx, session.display_name)
            self.main_window.update_title(
                session.display_name, session.is_geometry_modified)
            self._sync_geometry_list()

    def _sync_geometry_list(self):
        sb = self.main_window.sidebar_view
        # Block both itemChanged AND currentRowChanged while rebuilding the list
        sb.geom_list.blockSignals(True)
        sb.geom_list.clear()
        from PyQt6.QtCore import Qt
        for session in self.sessions:
            name = session.display_name
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            state = Qt.CheckState.Checked if session.is_visible else Qt.CheckState.Unchecked
            item.setCheckState(state)
            item.setData(Qt.ItemDataRole.UserRole, session.session_id)
            sb.geom_list.addItem(item)

        if 0 <= self.active_idx < sb.geom_list.count():
            sb.geom_list.setCurrentRow(self.active_idx)

        sb.geom_list.blockSignals(False)

    def _update_canvas_curve_segments(self):
        session = self.active_session()
        if not session:
            return

        segments_pts = []
        for idx, seg in enumerate(session.project_model.segments):
            if seg.type == "curve" and idx != session.current_segment_idx:
                n = seg.parameters.get("n_points", 100)
                try:
                    xs, ys = self._compute_curve_preview_pts(seg, n)
                    if xs is not None and ys is not None and len(xs) > 0:
                        segments_pts.append(np.column_stack([xs, ys]))
                except Exception:
                    pass
        self.main_window.canvas_view.update_curve_segments(session.session_id, segments_pts)

    def handle_geom_visibility_changed(self, item: QListWidgetItem):
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id is None:
            return
        from PyQt6.QtCore import Qt
        is_checked = item.checkState() == Qt.CheckState.Checked
        for session in self.sessions:
            if session.session_id == session_id:
                session.is_visible = is_checked
                self.main_window.canvas_view.set_geometry_visible(session_id, is_checked)
                if session is self.active_session():
                    self.main_window.canvas_view.set_active_overlays_visible(is_checked)
                break

    def handle_geom_list_row_changed(self, row: int):
        if row < 0 or row >= len(self.sessions):
            return
        # Guard: only switch if it's actually a different tab to avoid feedback loops
        if row == self.active_idx:
            return
        self.main_window.tab_widget.setCurrentIndex(row)

    def handle_geom_list_double_clicked(self, item: QListWidgetItem):
        session_id = item.data(Qt.ItemDataRole.UserRole)
        self.main_window.canvas_view.fit_to_geometry(session_id)

    def toggle_selected_geometry_visibility(self):
        """Toggle the visibility of the currently selected geometry in the list."""
        sb = self.main_window.sidebar_view
        row = sb.geom_list.currentRow()
        if row < 0 or row >= sb.geom_list.count():
            return
        item = sb.geom_list.item(row)
        if item is None:
            return
        from PyQt6.QtCore import Qt
        current = item.checkState() == Qt.CheckState.Checked
        item.setCheckState(
            Qt.CheckState.Unchecked if current else Qt.CheckState.Checked)
        # itemChanged signal will call handle_geom_visibility_changed automatically

    def focus_to_selected_geometry(self):
        session = self.active_session()
        if session:
            self.main_window.canvas_view.fit_to_geometry(session.session_id)

    # ═════════════════════════════════════════════════════════════════════
    # File loading
    # ═════════════════════════════════════════════════════════════════════

    def load_geometry(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.main_window, "Open Geometry File(s)",
            "examples/geometries", "Data Files (*.dat)")
        for fp in file_paths:
            if os.path.exists(fp):
                self._load_geometry_file(fp)
            else:
                self.main_window.log_panel.log(f"File not found: {fp}")

    def load_geometry_from_path(self, file_path: str):
        if os.path.exists(file_path):
            self._load_geometry_file(file_path)
        else:
            self.main_window.log_panel.log(f"File not found: {file_path}")

    def _load_geometry_file(self, file_path: str):
        try:
            # Check if active session is empty/untitled and has no loaded points
            active = self.active_session()
            if active and not active.file_path and active.original_points is None:
                session = active
                # Update tab text
                label = os.path.basename(file_path)
                self.main_window.tab_widget.setTabText(self.active_idx, label)
                session.file_path = file_path
                session.color = session.SESSION_COLORS[
                    (session.session_id - 1) % len(session.SESSION_COLORS)]
            else:
                session = self._new_session(file_path)

            session.project_model.input_file = file_path
            session.project_model.output_file = session.default_output_path
            session.original_points = np.loadtxt(file_path)

            self._apply_geometry_update(session, re_detect=True)
            if session is self.active_session():
                self._sync_sidebar_to_session()
            n_pts = len(session.original_points)
            n_seg = len(session.split_indices) - 1
            self.main_window.log_panel.log(
                f"Loaded '{os.path.basename(file_path)}' — "
                f"{n_pts} points, {n_seg} auto-detected edges.")
        except Exception as e:
            self.main_window.log_panel.log(f"Error loading file: {e}")

    # ═════════════════════════════════════════════════════════════════════
    # JSON config loading
    # ═════════════════════════════════════════════════════════════════════

    def load_json_config(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Load JSON Config", "",
            "JSON Files (*.json);;All Files (*)")
        if not file_path:
            return
        try:
            import json
            with open(file_path) as f:
                config = json.load(f)
            self._apply_json_config(config, file_path)
        except Exception as e:
            self.main_window.log_panel.log(f"Error loading JSON: {e}")

    def _apply_json_config(self, config: dict, config_path: str):
        input_file = config.get("input_file", "")

        # If input file doesn't exist, ask user
        if input_file and not os.path.exists(input_file):
            self.main_window.log_panel.log(
                f"input_file '{input_file}' not found. Please select .dat manually.")
            input_file, _ = QFileDialog.getOpenFileName(
                self.main_window, "Select Geometry File",
                "", "Data Files (*.dat)")
            if not input_file:
                return
            config["input_file"] = input_file

        # Check if active session is empty/untitled and has no loaded points
        active = self.active_session()
        if active and not active.file_path and active.original_points is None:
            session = active
            label = os.path.basename(input_file) if input_file else "Untitled"
            self.main_window.tab_widget.setTabText(self.active_idx, label)
            session.file_path = input_file
            session.color = session.SESSION_COLORS[
                (session.session_id - 1) % len(session.SESSION_COLORS)]
        else:
            session = self._new_session(input_file)

        session.project_model.load_from_config(config)

        if input_file and os.path.exists(input_file):
            try:
                session.original_points = np.loadtxt(input_file)
            except Exception as e:
                self.main_window.log_panel.log(f"Error reading geometry: {e}")
                return

        # Restore split_indices from file segments in config
        session.split_indices = (
            session.project_model.get_split_indices_from_file_segments())

        # Apply geometry without auto-detecting features
        self._apply_geometry_update(session, re_detect=False)

        if session is self.active_session():
            self._sync_sidebar_to_session()

        self.main_window.log_panel.log(
            f"Loaded config '{os.path.basename(config_path)}' — "
            f"{len(session.project_model.segments)} segments.")

    # ═════════════════════════════════════════════════════════════════════
    # Geometry helpers
    # ═════════════════════════════════════════════════════════════════════

    def _auto_detect_features(self, points: np.ndarray,
                              angle_threshold_deg: float = 30.0) -> list[int]:
        indices = [0]
        n = len(points)
        threshold_rad = math.radians(angle_threshold_deg)
        for i in range(1, n - 1):
            v1 = points[i] - points[i - 1]
            v2 = points[i + 1] - points[i]
            n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
            if n1 == 0 or n2 == 0:
                continue
            dot = float(np.clip(np.dot(v1 / n1, v2 / n2), -1.0, 1.0))
            if math.acos(dot) > threshold_rad:
                indices.append(i)
        if (n - 1) not in indices:
            indices.append(n - 1)
        return indices

    def _auto_detect_features_for_segment(self, segment_idx: int, angle_threshold_deg: float = 30.0) -> list[int]:
        """Auto-detect split indices for a specific segment, returning new split indices.

        For file segments: returns global indices into original_points.
        For curve segments: returns local indices into the generated curve points.
        """
        session = self.active_session()
        if not session:
            return []

        seg = session.project_model.get_segment(segment_idx)
        if not seg:
            return []

        if seg.type == "file":
            if session.original_points is None:
                return []
            # Extract points for this segment
            start, end = seg.start_index, seg.end_index
            if start < 0 or end < 0 or end <= start:
                return []

            segment_points = session.original_points[start:end + 1]

            # Detect features within this segment's local indices
            local_indices = self._auto_detect_features(segment_points, angle_threshold_deg)

            # Convert back to global indices
            global_indices = [start + idx for idx in local_indices]
            return sorted(list(set(global_indices)))
        else:
            # For curve segments: generate points and detect features
            n = seg.parameters.get("n_points", 100)
            try:
                xs, ys = self._compute_curve_preview_pts(seg, n)
            except Exception:
                return []

            if xs is None or len(xs) < 2:
                return []

            # Stack into points array
            segment_points = np.column_stack([xs, ys])

            # Detect features (returns local indices [0, n-1])
            local_indices = self._auto_detect_features(segment_points, angle_threshold_deg)
            return sorted(list(set(local_indices)))

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

    def _refresh_segment_list(self, clear_resampled: bool = True):
        session = self.active_session()
        if not session:
            return
        sb = self.main_window.sidebar_view
        
        sb.file_segment_list.blockSignals(True)
        sb.curve_segment_list.blockSignals(True)
        sb.file_segment_list.clear()
        sb.curve_segment_list.clear()

        for idx, seg in enumerate(session.project_model.segments):
            if seg.type == "curve":
                c_type = getattr(seg, "curve_type", "custom")
                if c_type == "custom":
                    c_label = f"Curve ({'Param' if seg.curve_mode == 'parametric' else 'Explicit'})"
                elif c_type == "horizontal_line":
                    c_label = "H Line"
                elif c_type == "vertical_line":
                    c_label = "V Line"
                elif c_type == "line":
                    c_label = "Line"
                elif c_type == "circle":
                    c_label = "Circle"
                elif c_type == "triangle":
                    c_label = "Triangle"
                elif c_type == "quadrilateral":
                    c_label = "Quad"
                elif c_type == "polygon":
                    c_label = "Polygon"
                else:
                    c_label = c_type.capitalize()
                lbl = f"Edge {seg.id}: {c_label}"
                item = QListWidgetItem(lbl)
                item.setData(Qt.ItemDataRole.UserRole, idx)
                sb.curve_segment_list.addItem(item)
            else:
                lbl = (f"Edge {seg.id}: "
                       f"Idx {seg.start_index} → {seg.end_index}")
                item = QListWidgetItem(lbl)
                item.setData(Qt.ItemDataRole.UserRole, idx)
                sb.file_segment_list.addItem(item)

        sb.file_segment_list.blockSignals(False)
        sb.curve_segment_list.blockSignals(False)

        session.current_segment_idx = -1
        sb.remove_seg_btn.setEnabled(False)
        sb.show_segment_props(False)
        self._update_canvas_curve_segments()
        self.main_window.canvas_view.update_active_segment(None, None)
        self.main_window.canvas_view.clear_curve_preview(session.session_id)
        if clear_resampled:
            session.resampled_points = None
            self.main_window.canvas_view.clear_resampled()

    # ═════════════════════════════════════════════════════════════════════
    # Sidebar ↔ Session sync
    # ═════════════════════════════════════════════════════════════════════

    def _sync_sidebar_to_session(self):
        session = self.active_session()
        sb = self.main_window.sidebar_view
        if not session:
            self._clear_sidebar()
            return

        pm = session.project_model

        # File label
        if session.file_path:
            sb.file_name_label.setText(
                f"File: {os.path.basename(session.file_path)}")
            sb.file_name_label.setStyleSheet(
                "color: #dde6ff; font-weight: bold; margin-bottom: 5px;")
        else:
            sb.file_name_label.setText("No geometry imported")
            sb.file_name_label.setStyleSheet(
                "color: #6a7aaa; font-style: italic; margin-bottom: 5px;")

        # is_closed
        sb.is_closed_combo.blockSignals(True)
        sb.is_closed_combo.setCurrentText(str(pm.is_closed))
        sb.is_closed_combo.blockSignals(False)

        # Advanced
        sb.global_spline_cb.blockSignals(True)
        sb.global_spline_cb.setChecked(pm.global_spline)
        sb.global_spline_cb.blockSignals(False)
        sb.set_transform_from_dict(pm.transform)

        # Selection state
        sb.selected_info.setText("Selected Vertex: None")
        sb.split_btn.setEnabled(False)
        sb.remove_split_btn.setEnabled(False)

        self._refresh_segment_list(clear_resampled=False)
        self._sync_geometry_list()

    def _clear_sidebar(self):
        sb = self.main_window.sidebar_view
        sb.file_name_label.setText("No geometry imported")
        sb.file_segment_list.clear()
        sb.curve_segment_list.clear()
        sb.selected_info.setText("Selected Vertex: None")
        sb.split_btn.setEnabled(False)
        sb.remove_split_btn.setEnabled(False)
        sb.remove_seg_btn.setEnabled(False)
        sb.show_segment_props(False)
        self._sync_geometry_list()

    # ═════════════════════════════════════════════════════════════════════
    # Point selection
    # ═════════════════════════════════════════════════════════════════════

    def handle_point_clicked(self, idx: int):
        session = self.active_session()
        if not session:
            return
        session.selected_point_idx = idx
        self.main_window.canvas_view.update_selected_point(idx)

        sb = self.main_window.sidebar_view
        sb.selected_info.setText(f"Selected Vertex: Index {idx}")

        n_pts = (len(session.original_points)
                 if session.original_points is not None else 0)
        is_closed = session.project_model.is_closed
        is_endpoint = (idx == 0 or idx == n_pts - 1) if not is_closed else False
        is_split = idx in session.split_indices

        sb.split_btn.setEnabled(not is_split)
        sb.remove_split_btn.setEnabled(is_split and not is_endpoint)

    # ═════════════════════════════════════════════════════════════════════
    # Split / Remove commands
    # ═════════════════════════════════════════════════════════════════════

    def add_split_point(self):
        session = self.active_session()
        if session is None or session.selected_point_idx is None:
            return
        idx = session.selected_point_idx
        if idx in session.split_indices:
            return

        cmd = AddSplitCmd(
            session, idx,
            sync_cb=lambda: self._on_split_changed(session),
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Added split point at index {idx}.")
        self.handle_point_clicked(idx)

    def remove_split_point(self):
        session = self.active_session()
        if session is None or session.selected_point_idx is None:
            return
        idx = session.selected_point_idx
        if idx not in session.split_indices:
            return
        keep = self.main_window.sidebar_view.keep_vertex_cb.isChecked()
        cmd = RemoveSplitCmd(
            session, idx, keep,
            sync_cb=lambda: self._on_split_changed(session),
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        action = "kept" if keep else "deleted"
        self.main_window.log_panel.log(
            f"Removed split point at {idx} (vertex {action}).")
        if keep:
            self.handle_point_clicked(idx)

    def _on_split_changed(self, session: GeometrySession):
        """Called after a lightweight split-only change (no geometry modification)."""
        if session is self.active_session():
            self.main_window.canvas_view.update_split_points(session.split_indices)
        self._sync_file_segments(session)

    # ═════════════════════════════════════════════════════════════════════
    # Insert vertex
    # ═════════════════════════════════════════════════════════════════════

    def handle_insert_point(self):
        session = self.active_session()
        if session is None or session.original_points is None:
            self.main_window.log_panel.log("No geometry loaded.")
            return
        sb = self.main_window.sidebar_view
        x = sb.insert_x.value()
        y = sb.insert_y.value()
        p = np.array([x, y])

        # Find nearest edge
        pts = session.original_points
        n = len(pts)
        best_idx, min_dist = 0, float("inf")
        for i in range(n - 1):
            v, w = pts[i], pts[i + 1]
            l2 = np.sum((w - v) ** 2)
            t = (np.dot(p - v, w - v) / l2) if l2 > 0 else 0
            t = float(np.clip(t, 0, 1))
            dist = np.linalg.norm(p - (v + t * (w - v)))
            if dist < min_dist:
                min_dist = dist
                best_idx = i

        insert_idx = best_idx + 1
        cmd = InsertVertexCmd(
            session, insert_idx, p, list(session.split_indices),
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Inserted ({x:.4f}, {y:.4f}) at index {insert_idx}.")
        self.handle_point_clicked(insert_idx)

    # ═════════════════════════════════════════════════════════════════════
    # Segment selection & properties
    # ═════════════════════════════════════════════════════════════════════

    def handle_file_segment_selected(self, row: int):
        if row < 0:
            return
        sb = self.main_window.sidebar_view
        sb.curve_segment_list.blockSignals(True)
        sb.curve_segment_list.setCurrentRow(-1)
        sb.curve_segment_list.blockSignals(False)

        item = sb.file_segment_list.item(row)
        if item:
            idx = item.data(Qt.ItemDataRole.UserRole)
            self.handle_segment_selected(idx)

    def handle_curve_segment_selected(self, row: int):
        if row < 0:
            return
        sb = self.main_window.sidebar_view
        sb.file_segment_list.blockSignals(True)
        sb.file_segment_list.setCurrentRow(-1)
        sb.file_segment_list.blockSignals(False)

        item = sb.curve_segment_list.item(row)
        if item:
            idx = item.data(Qt.ItemDataRole.UserRole)
            self.handle_segment_selected(idx)

    def _select_segment_by_index(self, index: int):
        sb = self.main_window.sidebar_view
        if index < 0:
            sb.file_segment_list.blockSignals(True)
            sb.file_segment_list.setCurrentRow(-1)
            sb.file_segment_list.blockSignals(False)

            sb.curve_segment_list.blockSignals(True)
            sb.curve_segment_list.setCurrentRow(-1)
            sb.curve_segment_list.blockSignals(False)

            self.handle_segment_selected(-1)
            return

        session = self.active_session()
        if not session or index >= len(session.project_model.segments):
            return

        seg = session.project_model.segments[index]
        if seg.type == "file":
            row = -1
            for r in range(sb.file_segment_list.count()):
                item = sb.file_segment_list.item(r)
                if item.data(Qt.ItemDataRole.UserRole) == index:
                    row = r
                    break
            sb.curve_segment_list.blockSignals(True)
            sb.curve_segment_list.setCurrentRow(-1)
            sb.curve_segment_list.blockSignals(False)

            sb.file_segment_list.blockSignals(True)
            sb.file_segment_list.setCurrentRow(row)
            sb.file_segment_list.blockSignals(False)
        else:
            row = -1
            for r in range(sb.curve_segment_list.count()):
                item = sb.curve_segment_list.item(r)
                if item.data(Qt.ItemDataRole.UserRole) == index:
                    row = r
                    break
            sb.file_segment_list.blockSignals(True)
            sb.file_segment_list.setCurrentRow(-1)
            sb.file_segment_list.blockSignals(False)

            sb.curve_segment_list.blockSignals(True)
            sb.curve_segment_list.setCurrentRow(row)
            sb.curve_segment_list.blockSignals(False)

        self.handle_segment_selected(index)

    def handle_segment_selected(self, row: int):
        session = self.active_session()
        if not session:
            return
        sb = self.main_window.sidebar_view
        if row < 0:
            self.main_window.canvas_view.update_active_segment(None, None)
            self.main_window.canvas_view.clear_curve_preview(session.session_id)
            self.main_window.canvas_view.clear_duplicate_preview()
            self._show_duplicate_preview = False
            session.current_segment_idx = -1
            sb.remove_seg_btn.setEnabled(False)
            sb.show_segment_props(False)
            return

        session.current_segment_idx = row
        seg = session.project_model.get_segment(row)
        if not seg:
            self.main_window.canvas_view.update_active_segment(None, None)
            self.main_window.canvas_view.clear_curve_preview(session.session_id)
            self._show_duplicate_preview = False
            sb.remove_seg_btn.setEnabled(False)
            sb.show_segment_props(False)
            return

        # Highlight on canvas
        if seg.type == "file":
            self.main_window.canvas_view.update_active_segment(
                seg.start_index, seg.end_index)
            self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, True)
            self.main_window.canvas_view.clear_curve_preview(session.session_id)
        else:
            self.main_window.canvas_view.update_active_segment(None, None)
            self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, False)

        # Enable remove segment button for both file and curve segments
        sb.remove_seg_btn.setEnabled(True)

        # Populate sidebar
        self._is_populating = True
        try:
            sb.show_segment_props(True)
            is_curve = (seg.type == "curve")
            if is_curve:
                sb.segment_type_label.setText("Analytic Edge")
                sb.show_curve_segment(seg)
                sb.strategy_combo.setVisible(False)
                sb.param_stack.setVisible(False)
            else:
                sb.segment_type_label.setText("Discrete Edge")
                sb.show_file_segment(seg.start_index, seg.end_index)
                sb.strategy_combo.setVisible(True)
                sb.param_stack.setVisible(True)
                sb.strategy_combo.blockSignals(True)
                sb.strategy_combo.setCurrentText(seg.strategy)
                sb.strategy_combo.blockSignals(False)
                sb.switch_param_form(seg.strategy)
                self._populate_form_from_segment(seg)

            # Show transform duplicate group for all segments
            sb._transform_dup_group.setVisible(True)

            sb.match_previous_cb.blockSignals(True)
            sb.match_previous_cb.setChecked(seg.match_previous)
            sb.match_previous_cb.blockSignals(False)

            # Update base point values
            self.update_duplicate_base_point()
            self._show_duplicate_preview = False

            # Snapshot params for undo
            session.param_snapshot = copy.deepcopy(seg.parameters)
            session.segment_state_snapshot = copy.deepcopy(seg.to_dict())
        finally:
            self._is_populating = False
            self.main_window.canvas_view.clear_duplicate_preview()

        self._update_canvas_curve_segments()
        if seg.type == "curve":
            self.preview_curve_formula()

    def handle_strategy_changed(self, strategy_name: str):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return
        cmd = UpdateStrategyCmd(
            session, session.current_segment_idx, strategy_name,
            repopulate_cb=self._repopulate_strategy)
        session.command_history.execute(cmd)
        session.param_snapshot = copy.deepcopy(seg.parameters)
        session.segment_state_snapshot = copy.deepcopy(seg.to_dict())
        self.main_window.log_panel.log(
            f"Edge {seg.id}: distribution → {strategy_name}")

    def _repopulate_strategy(self, strategy_name: str):
        session = self.active_session()
        if not session:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if seg:
            self._populate_form_from_segment(seg)
        self.main_window.sidebar_view.switch_param_form(strategy_name)

    def _populate_form_from_segment(self, seg: SegmentModel):
        sb = self.main_window.sidebar_view

        def block(b):
            for w in [sb.uniform_n, sb.tanh_n, sb.tanh_intensity,
                      sb.cosine_n, sb.curv_n, sb.curv_sens,
                      sb.geo_n, sb.geo_ratio, sb.uniform_spacing]:
                w.blockSignals(b)
            sb.uniform_type_combo.blockSignals(b)

        block(True)
        p = seg.parameters
        if seg.strategy == "uniform":
            if "spacing" in p:
                sb.uniform_type_combo.setCurrentText("By Spacing")
                sb.uniform_spacing.setValue(p["spacing"])
                sb._toggle_uniform_mode(True)
            else:
                sb.uniform_type_combo.setCurrentText("By Node Count")
                sb.uniform_n.setValue(p.get("n_points", 50))
                sb._toggle_uniform_mode(False)
        elif seg.strategy == "tanh":
            sb.tanh_n.setValue(p.get("n_points", 50))
            sb.tanh_intensity.setValue(p.get("intensity", 2.0))
        elif seg.strategy == "cosine":
            sb.cosine_n.setValue(p.get("n_points", 50))
        elif seg.strategy == "curvature":
            sb.curv_n.setValue(p.get("n_points", 50))
            sb.curv_sens.setValue(p.get("sensitivity", 1.5))
        elif seg.strategy == "geometric":
            sb.geo_n.setValue(p.get("n_points", 50))
            sb.geo_ratio.setValue(p.get("ratio", 1.2))
            sb.geo_ratio_end.setValue(p.get("ratio_end", 1.0))
        block(False)

    def update_segment_params(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        if self._is_populating:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return
        self._read_params_into_segment(seg)
        self._record_segment_state_change()

    def _record_segment_state_change(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        if self._is_populating:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return
        
        current_state = seg.to_dict()
        old_state = session.segment_state_snapshot
        
        if current_state != old_state:
            seg_idx = session.current_segment_idx
            def refresh():
                if session is self.active_session():
                    self._apply_geometry_update(session)
                    if 0 <= seg_idx < len(session.project_model.segments):
                        self._select_segment_by_index(seg_idx)
            
            cmd = UpdateSegmentStateCmd(session, session.current_segment_idx, old_state, current_state, refresh_cb=refresh)
            session.command_history.record(cmd)
            session.segment_state_snapshot = current_state


    def _read_params_into_segment(self, seg: SegmentModel):
        sb = self.main_window.sidebar_view
        seg.parameters.clear()
        if seg.strategy == "uniform":
            if sb.uniform_type_combo.currentText() == "By Spacing":
                seg.parameters["spacing"] = sb.uniform_spacing.value()
            else:
                seg.parameters["n_points"] = sb.uniform_n.value()
        elif seg.strategy == "tanh":
            seg.parameters["n_points"] = sb.tanh_n.value()
            seg.parameters["intensity"] = sb.tanh_intensity.value()
        elif seg.strategy == "cosine":
            seg.parameters["n_points"] = sb.cosine_n.value()
        elif seg.strategy == "curvature":
            seg.parameters["n_points"] = sb.curv_n.value()
            seg.parameters["sensitivity"] = sb.curv_sens.value()
        elif seg.strategy == "geometric":
            seg.parameters["n_points"] = sb.geo_n.value()
            seg.parameters["ratio"] = sb.geo_ratio.value()
            end_ratio = sb.geo_ratio_end.value()
            if end_ratio != 1.0:
                seg.parameters["ratio_end"] = end_ratio
            else:
                seg.parameters.pop("ratio_end", None)

    def update_match_previous(self, checked: bool):
        session = self.active_session()
        if session and session.current_segment_idx >= 0:
            seg = session.project_model.get_segment(session.current_segment_idx)
            if seg and seg.match_previous != checked:
                def update_cb(val):
                    sb = self.main_window.sidebar_view
                    sb.match_previous_cb.blockSignals(True)
                    sb.match_previous_cb.setChecked(val)
                    sb.match_previous_cb.blockSignals(False)
                    self._apply_geometry_update(session)
                cmd = ToggleMatchPreviousCmd(session, session.current_segment_idx, checked, update_cb)
                session.command_history.execute(cmd)

    # ═════════════════════════════════════════════════════════════════════
    # Global settings
    # ═════════════════════════════════════════════════════════════════════

    def handle_is_closed_changed(self, text: str):
        session = self.active_session()
        if session:
            is_closed = (text == "True")
            if session.project_model.is_closed != is_closed:
                def refresh():
                    sb = self.main_window.sidebar_view
                    sb.is_closed_combo.blockSignals(True)
                    sb.is_closed_combo.setCurrentText(str(session.project_model.is_closed))
                    sb.is_closed_combo.blockSignals(False)
                    self._apply_geometry_update(session)
                cmd = ToggleIsClosedCmd(session, is_closed, refresh)
                session.command_history.execute(cmd)

    def handle_global_spline_changed(self, checked: bool):
        session = self.active_session()
        if session:
            if session.project_model.global_spline != checked:
                def refresh():
                    sb = self.main_window.sidebar_view
                    sb.global_spline_cb.blockSignals(True)
                    sb.global_spline_cb.setChecked(session.project_model.global_spline)
                    sb.global_spline_cb.blockSignals(False)
                    self._apply_geometry_update(session)
                cmd = ToggleGlobalSplineCmd(session, checked, refresh)
                session.command_history.execute(cmd)

    # ═════════════════════════════════════════════════════════════════════
    # Curve segment
    # ═════════════════════════════════════════════════════════════════════

    def add_curve_segment(self):
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No geometry session active.")
            return
        cmd = AddCurveSegmentCmd(
            session,
            refresh_cb=self._refresh_segment_list,
            select_cb=self._select_segment_by_index
        )
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Added Analytic Edge {cmd.added_seg.id}.")

    def bake_selected_curve(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve":
            return
        
        n = seg.parameters.get("n_points", 100)
        xs, ys = self._compute_curve_preview_pts(seg, n)
        if xs is None or len(xs) < 2:
            self.main_window.log_panel.log("Cannot convert curve: invalid preview points.")
            return

        cmd = BakeCurveToGeometryCmd(session, session.current_segment_idx, self._refresh_segment_list)
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(f"Converted Edge {cmd.seg_id} to Discrete.")
        self.main_window.canvas_view.clear_curve_preview(session.session_id)
        self._apply_geometry_update(session)
        self._update_canvas_curve_segments()

    def _sync_active_curve_segment_from_ui(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve":
            return
        
        sb = self.main_window.sidebar_view
        CURVE_TYPES = ["custom", "horizontal_line", "vertical_line", "line", "circle", "triangle", "quadrilateral", "polygon"]
        idx = sb.curve_type_combo.currentIndex()
        if 0 <= idx < len(CURVE_TYPES):
            seg.curve_type = CURVE_TYPES[idx]
        else:
            seg.curve_type = "custom"

        seg.curve_mode = "parametric" if sb.curve_mode_param.isChecked() else "explicit"
        seg.x_formula = sb.curve_x_formula.text()
        seg.y_formula = sb.curve_y_formula.text()
        seg.formula = sb.curve_formula.text()
        seg.t_min = sb.curve_t_min.value()
        seg.t_max = sb.curve_t_max.value()
        seg.parameters["n_points"] = sb.curve_n.value()
        seg.start_index = sb.curve_start_node.value()
        seg.end_index = sb.curve_end_node.value()

        # Sync parameters based on curve type
        if seg.curve_type == "horizontal_line":
            seg.parameters["y"] = sb.h_line_y.value()
            seg.parameters["x0"] = sb.h_line_x_start.value()
            seg.parameters["x1"] = sb.h_line_x_end.value()
        elif seg.curve_type == "vertical_line":
            seg.parameters["x"] = sb.v_line_x.value()
            seg.parameters["y0"] = sb.v_line_y_start.value()
            seg.parameters["y1"] = sb.v_line_y_end.value()
        elif seg.curve_type == "line":
            seg.parameters["x0"] = sb.line_x0.value()
            seg.parameters["y0"] = sb.line_y0.value()
            seg.parameters["x1"] = sb.line_x1.value()
            seg.parameters["y1"] = sb.line_y1.value()
        elif seg.curve_type == "circle":
            seg.parameters["cx"] = sb.circle_cx.value()
            seg.parameters["cy"] = sb.circle_cy.value()
            seg.parameters["r"] = sb.circle_r.value()
        elif seg.curve_type == "triangle":
            seg.parameters["x0"] = sb.tri_x0.value()
            seg.parameters["y0"] = sb.tri_y0.value()
            seg.parameters["x1"] = sb.tri_x1.value()
            seg.parameters["y1"] = sb.tri_y1.value()
            seg.parameters["x2"] = sb.tri_x2.value()
            seg.parameters["y2"] = sb.tri_y2.value()
        elif seg.curve_type == "quadrilateral":
            seg.parameters["x0"] = sb.quad_x0.value()
            seg.parameters["y0"] = sb.quad_y0.value()
            seg.parameters["x1"] = sb.quad_x1.value()
            seg.parameters["y1"] = sb.quad_y1.value()
            seg.parameters["x2"] = sb.quad_x2.value()
            seg.parameters["y2"] = sb.quad_y2.value()
            seg.parameters["x3"] = sb.quad_x3.value()
            seg.parameters["y3"] = sb.quad_y3.value()
        elif seg.curve_type == "polygon":
            seg.parameters["vertices_str"] = sb.poly_vertices.text()

    def handle_curve_type_changed(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve":
            return
        self._sync_active_curve_segment_from_ui()
        # Update list item text
        sb = self.main_window.sidebar_view
        seg_idx = session.current_segment_idx
        item = None
        for row in range(sb.curve_segment_list.count()):
            curr_item = sb.curve_segment_list.item(row)
            if curr_item.data(Qt.ItemDataRole.UserRole) == seg_idx:
                item = curr_item
                break
        if item is not None:
            c_type = seg.curve_type
            if c_type == "custom":
                c_label = f"Curve ({'Param' if seg.curve_mode == 'parametric' else 'Explicit'})"
            elif c_type == "horizontal_line":
                c_label = "H Line"
            elif c_type == "vertical_line":
                c_label = "V Line"
            elif c_type == "line":
                c_label = "Line"
            elif c_type == "circle":
                c_label = "Circle"
            elif c_type == "triangle":
                c_label = "Triangle"
            elif c_type == "quadrilateral":
                c_label = "Quad"
            elif c_type == "polygon":
                c_label = "Polygon"
            else:
                c_label = c_type.capitalize()
            item.setText(f"Edge {seg.id}: {c_label}")
        self.preview_curve_formula()

    def preview_curve_formula(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        if self._is_populating:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve":
            return

        self._sync_active_curve_segment_from_ui()

        n = seg.parameters.get("n_points", 100)
        try:
            xs, ys = self._compute_curve_preview_pts(seg, n)
            if xs is None or ys is None or len(xs) == 0:
                self.main_window.canvas_view.clear_curve_preview(session.session_id)
                return

            pts = np.column_stack([xs, ys])
            show_symbols = (session.resampled_points is None)
            self.main_window.canvas_view.update_curve_preview(session.session_id, pts, show_symbols=show_symbols)
            self.main_window.log_panel.log(
                f"Curve preview updated ({len(pts)} points).")
            self._update_canvas_curve_segments()
            self._record_segment_state_change()
            self.update_duplicate_base_point()
            self.update_duplicate_preview()
        except Exception as e:
            self.main_window.log_panel.log(f"Formula error: {e}")
            self.main_window.canvas_view.clear_curve_preview(session.session_id)

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

    # ═════════════════════════════════════════════════════════════════════
    # Segment deletion & quality check toggles
    # ═════════════════════════════════════════════════════════════════════

    def remove_selected_segment(self):
        session = self.active_session()
        if not session:
            return
        idx = session.current_segment_idx
        if idx < 0 or idx >= len(session.project_model.segments):
            return
        seg = session.project_model.segments[idx]

        cmd = RemoveSegmentCmd(session, idx, self._on_segment_removed)
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(f"Removed Edge {seg.id}.")

    def _on_segment_removed(self):
        session = self.active_session()
        if not session:
            return
        self._apply_geometry_update(session)
        self._refresh_segment_list()
        self._sync_geometry_list()
        self.main_window.canvas_view.clear_curve_preview(session.session_id)
        self._update_canvas_curve_segments()
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, session.is_geometry_modified)

    # ═════════════════════════════════════════════════════════════════════
    # Duplicate with Transform
    # ═════════════════════════════════════════════════════════════════════

    def duplicate_with_transform(self):
        """Generate preview points for the active segment, apply the
        selected geometric transform, and add a new Polygon curve segment."""
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            self.main_window.log_panel.log("No segment selected.")
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return

        # --- Get points to duplicate
        if seg.type == "file":
            if session.original_points is None or len(session.original_points) == 0:
                self.main_window.log_panel.log("No file points loaded.")
                return
            pts = session.original_points[seg.start_index : seg.end_index + 1]
            xs = pts[:, 0].copy()
            ys = pts[:, 1].copy()
            n = len(pts)
        else:
            self._sync_active_curve_segment_from_ui()
            n = seg.parameters.get("n_points", 100)
            try:
                xs, ys = self._compute_curve_preview_pts(seg, n)
            except Exception as e:
                self.main_window.log_panel.log(f"Cannot compute preview for transform: {e}")
                return

        if xs is None or len(xs) < 2:
            self.main_window.log_panel.log("Edge has no valid points — cannot duplicate.")
            return

        xs = xs.copy()
        ys = ys.copy()

        # --- Apply transform ------------------------------------------------
        sb = self.main_window.sidebar_view
        t_idx = sb.dup_type_combo.currentIndex()

        if t_idx == 0:   # Rotate
            theta = math.radians(sb.dup_rot_angle.value())
            px, py = sb.dup_rot_px.value(), sb.dup_rot_py.value()
            xr = xs - px;  yr = ys - py
            xs_new = px + xr * math.cos(theta) - yr * math.sin(theta)
            ys_new = py + xr * math.sin(theta) + yr * math.cos(theta)
            xs, ys = xs_new, ys_new
        elif t_idx == 1: # Mirror Horizontal (flip y around axis_y)
            axis_y = sb.dup_mh_py.value()
            ys = 2.0 * axis_y - ys
        elif t_idx == 2: # Mirror Vertical (flip x around axis_x)
            axis_x = sb.dup_mv_px.value()
            xs = 2.0 * axis_x - xs
        elif t_idx == 3: # Mirror Axis (arbitrary)
            px, py = sb.dup_ma_px.value(), sb.dup_ma_py.value()
            dx, dy = sb.dup_ma_dx.value(), sb.dup_ma_dy.value()
            d_len = math.hypot(dx, dy)
            if d_len < 1e-12:
                self.main_window.log_panel.log("Mirror axis direction is zero — cannot mirror.")
                return
            dx /= d_len;  dy /= d_len
            # Reflect point (x,y) through line through (px,py) with direction (dx,dy)
            xr = xs - px;  yr = ys - py
            dot = xr * dx + yr * dy
            xs = 2.0 * (px + dot * dx) - xs
            ys = 2.0 * (py + dot * dy) - ys
        elif t_idx == 4: # Point Symmetry
            cx, cy = sb.dup_ps_px.value(), sb.dup_ps_py.value()
            xs = 2.0 * cx - xs
            ys = 2.0 * cy - ys
        elif t_idx == 5: # Translate
            dx = sb.dup_trans_dx.value()
            dy = sb.dup_trans_dy.value()
            xs = xs + dx
            ys = ys + dy
        elif t_idx == 6: # Scale
            factor = sb.dup_scale_factor.value()
            px = sb.dup_scale_px.value()
            py = sb.dup_scale_py.value()
            xs = px + (xs - px) * factor
            ys = py + (ys - py) * factor

        # --- Create new polygon curve segment from transformed points --------
        v_str = ";".join(f"{x:.6g},{y:.6g}" for x, y in zip(xs, ys))
        new_seg = SegmentModel(session.project_model._next_curve_id, -1, -1)
        new_seg.type = "curve"
        new_seg.curve_type = "polygon"
        new_seg.parameters["vertices_str"] = v_str
        new_seg.parameters["n_points"] = n
        new_seg.start_index = -1
        new_seg.end_index = -1

        def select_cb(idx):
            self._select_segment_by_index(idx)

        delete_original = sb.dup_delete_orig_cb.isChecked()

        cmd = DuplicateTransformCmd(
            session=session,
            seg_idx=session.current_segment_idx,
            new_seg=new_seg,
            delete_original=delete_original,
            refresh_cb=self._refresh_segment_list,
            select_cb=select_cb
        )
        session.command_history.execute(cmd)
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, True)
        
        action_name = "Moved/Transformed" if delete_original else "Duplicated"
        self.main_window.log_panel.log(
            f"{action_name} Edge {seg.id} as Edge {new_seg.id} ({sb.dup_type_combo.currentText()}).")
        self._show_duplicate_preview = False
        self.main_window.canvas_view.clear_duplicate_preview()

    def handle_dup_type_changed(self):
        if self._is_populating:
            return
        self._show_duplicate_preview = True
        self.update_duplicate_base_point()
        self.update_duplicate_preview()

    def handle_dup_base_mode_changed(self):
        if self._is_populating:
            return
        self._show_duplicate_preview = True
        self.update_duplicate_base_point()
        self.update_duplicate_preview()

    def on_duplicate_param_changed(self):
        if self._is_populating:
            return
        self._show_duplicate_preview = True
        self.update_duplicate_preview()

    def update_duplicate_base_point(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return

        sb = self.main_window.sidebar_view
        t_idx = sb.dup_type_combo.currentIndex()
        if t_idx == 5: # Translate
            sb.dup_base_mode_combo.setEnabled(False)
            sb.dup_trans_dx.setEnabled(True)
            sb.dup_trans_dy.setEnabled(True)
            return
        else:
            sb.dup_base_mode_combo.setEnabled(True)

        mode = sb.dup_base_mode_combo.currentText()
        if mode == "Custom (Manual)":
            sb.dup_rot_px.setEnabled(True)
            sb.dup_rot_py.setEnabled(True)
            sb.dup_mh_py.setEnabled(True)
            sb.dup_mv_px.setEnabled(True)
            sb.dup_ma_px.setEnabled(True)
            sb.dup_ma_py.setEnabled(True)
            sb.dup_ps_px.setEnabled(True)
            sb.dup_ps_py.setEnabled(True)
            sb.dup_scale_px.setEnabled(True)
            sb.dup_scale_py.setEnabled(True)
            return

        # Disable fields for Start / End Point mode
        sb.dup_rot_px.setEnabled(False)
        sb.dup_rot_py.setEnabled(False)
        sb.dup_mh_py.setEnabled(False)
        sb.dup_mv_px.setEnabled(False)
        sb.dup_ma_px.setEnabled(False)
        sb.dup_ma_py.setEnabled(False)
        sb.dup_ps_px.setEnabled(False)
        sb.dup_ps_py.setEnabled(False)
        sb.dup_scale_px.setEnabled(False)
        sb.dup_scale_py.setEnabled(False)

        # Retrieve points of current segment
        if seg.type == "file":
            if session.original_points is None or len(session.original_points) == 0:
                return
            pts = session.original_points[seg.start_index : seg.end_index + 1]
            if len(pts) == 0:
                return
            if mode == "Start Point":
                px, py = pts[0][0], pts[0][1]
            else:
                px, py = pts[-1][0], pts[-1][1]
        else:
            n = seg.parameters.get("n_points", 100)
            try:
                xs, ys = self._compute_curve_preview_pts(seg, n)
            except Exception:
                return
            if xs is None or len(xs) == 0:
                return
            if mode == "Start Point":
                px, py = xs[0], ys[0]
            else:
                px, py = xs[-1], ys[-1]

        # Populate coordinates
        sb.dup_rot_px.blockSignals(True)
        sb.dup_rot_py.blockSignals(True)
        sb.dup_mh_py.blockSignals(True)
        sb.dup_mv_px.blockSignals(True)
        sb.dup_ma_px.blockSignals(True)
        sb.dup_ma_py.blockSignals(True)
        sb.dup_ps_px.blockSignals(True)
        sb.dup_ps_py.blockSignals(True)
        sb.dup_scale_px.blockSignals(True)
        sb.dup_scale_py.blockSignals(True)

        sb.dup_rot_px.setValue(px)
        sb.dup_rot_py.setValue(py)
        sb.dup_mh_py.setValue(py)
        sb.dup_mv_px.setValue(px)
        sb.dup_ma_px.setValue(px)
        sb.dup_ma_py.setValue(py)
        sb.dup_ps_px.setValue(px)
        sb.dup_ps_py.setValue(py)
        sb.dup_scale_px.setValue(px)
        sb.dup_scale_py.setValue(py)

        sb.dup_rot_px.blockSignals(False)
        sb.dup_rot_py.blockSignals(False)
        sb.dup_mh_py.blockSignals(False)
        sb.dup_mv_px.blockSignals(False)
        sb.dup_ma_px.blockSignals(False)
        sb.dup_ma_py.blockSignals(False)
        sb.dup_ps_px.blockSignals(False)
        sb.dup_ps_py.blockSignals(False)
        sb.dup_scale_px.blockSignals(False)
        sb.dup_scale_py.blockSignals(False)

    def update_duplicate_preview(self):
        if not self._show_duplicate_preview:
            self.main_window.canvas_view.clear_duplicate_preview()
            return

        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            self.main_window.canvas_view.clear_duplicate_preview()
            return
        
        sb = self.main_window.sidebar_view
        if not sb._transform_dup_group.isVisible():
            self.main_window.canvas_view.clear_duplicate_preview()
            return

        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            self.main_window.canvas_view.clear_duplicate_preview()
            return

        # 1. Get original points
        if seg.type == "file":
            if session.original_points is None or len(session.original_points) == 0:
                self.main_window.canvas_view.clear_duplicate_preview()
                return
            pts = session.original_points[seg.start_index : seg.end_index + 1]
            xs = pts[:, 0].copy()
            ys = pts[:, 1].copy()
            n = len(pts)
        else:
            n = seg.parameters.get("n_points", 100)
            try:
                xs, ys = self._compute_curve_preview_pts(seg, n)
            except Exception:
                self.main_window.canvas_view.clear_duplicate_preview()
                return

        if xs is None or len(xs) < 2:
            self.main_window.canvas_view.clear_duplicate_preview()
            return

        xs = xs.copy()
        ys = ys.copy()

        # 2. Apply transform
        t_idx = sb.dup_type_combo.currentIndex()

        if t_idx == 0:   # Rotate
            theta = math.radians(sb.dup_rot_angle.value())
            px, py = sb.dup_rot_px.value(), sb.dup_rot_py.value()
            xr = xs - px;  yr = ys - py
            xs_new = px + xr * math.cos(theta) - yr * math.sin(theta)
            ys_new = py + xr * math.sin(theta) + yr * math.cos(theta)
            xs, ys = xs_new, ys_new
        elif t_idx == 1: # Mirror Horizontal (flip y around axis_y)
            axis_y = sb.dup_mh_py.value()
            ys = 2.0 * axis_y - ys
        elif t_idx == 2: # Mirror Vertical (flip x around axis_x)
            axis_x = sb.dup_mv_px.value()
            xs = 2.0 * axis_x - xs
        elif t_idx == 3: # Mirror Axis (arbitrary)
            px, py = sb.dup_ma_px.value(), sb.dup_ma_py.value()
            dx, dy = sb.dup_ma_dx.value(), sb.dup_ma_dy.value()
            d_len = math.hypot(dx, dy)
            if d_len >= 1e-12:
                dx /= d_len;  dy /= d_len
                xr = xs - px;  yr = ys - py
                dot = xr * dx + yr * dy
                xs = 2.0 * (px + dot * dx) - xs
                ys = 2.0 * (py + dot * dy) - ys
        elif t_idx == 4: # Point Symmetry
            cx, cy = sb.dup_ps_px.value(), sb.dup_ps_py.value()
            xs = 2.0 * cx - xs
            ys = 2.0 * cy - ys
        elif t_idx == 5: # Translate
            dx = sb.dup_trans_dx.value()
            dy = sb.dup_trans_dy.value()
            xs = xs + dx
            ys = ys + dy
        elif t_idx == 6: # Scale
            factor = sb.dup_scale_factor.value()
            px = sb.dup_scale_px.value()
            py = sb.dup_scale_py.value()
            xs = px + (xs - px) * factor
            ys = py + (ys - py) * factor

        pts_new = np.column_stack([xs, ys])
        self.main_window.canvas_view.update_duplicate_preview(pts_new)

    def _compute_curve_preview_pts(
            self, seg: SegmentModel, n: int
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Compute (xs, ys) for the given curve segment without updating the canvas."""
        gp = None
        session = self.active_session()
        if session:
            gp = session.original_points

        if seg.curve_type == "horizontal_line":
            y_val = seg.parameters.get("y", 0.0)
            x0 = seg.parameters.get("x0", 0.0)
            x1 = seg.parameters.get("x1", 1.0)
            xs_raw = np.linspace(x0, x1, n)
            ys_raw = np.full(n, y_val)
            xs, ys = _resample_polyline_uniform(xs_raw, ys_raw, n)
        elif seg.curve_type == "vertical_line":
            x_val = seg.parameters.get("x", 0.0)
            y0 = seg.parameters.get("y0", 0.0)
            y1 = seg.parameters.get("y1", 1.0)
            xs_raw = np.full(n, x_val)
            ys_raw = np.linspace(y0, y1, n)
            xs, ys = _resample_polyline_uniform(xs_raw, ys_raw, n)
        elif seg.curve_type == "line":
            x0 = seg.parameters.get("x0", 0.0);  y0 = seg.parameters.get("y0", 0.0)
            x1 = seg.parameters.get("x1", 1.0);  y1 = seg.parameters.get("y1", 1.0)
            xs_raw = np.linspace(x0, x1, n)
            ys_raw = np.linspace(y0, y1, n)
            xs, ys = _resample_polyline_uniform(xs_raw, ys_raw, n)
        elif seg.curve_type == "circle":
            cx = seg.parameters.get("cx", 0.0);  cy = seg.parameters.get("cy", 0.0)
            r  = seg.parameters.get("r",  1.0)
            ts = np.linspace(0.0, 2.0 * math.pi, n)
            xs_raw = cx + r * np.cos(ts)
            ys_raw = cy + r * np.sin(ts)
            xs, ys = _resample_polyline_uniform(xs_raw, ys_raw, n)
        elif seg.curve_type == "triangle":
            verts = np.array([
                [seg.parameters.get("x0", 0.0), seg.parameters.get("y0", 0.0)],
                [seg.parameters.get("x1", 1.0), seg.parameters.get("y1", 0.0)],
                [seg.parameters.get("x2", 0.5), seg.parameters.get("y2", 1.0)],
                [seg.parameters.get("x0", 0.0), seg.parameters.get("y0", 0.0)],
            ])
            xs, ys = _sample_polyline_pinned(verts, n)
        elif seg.curve_type == "quadrilateral":
            verts = np.array([
                [seg.parameters.get("x0", 0.0), seg.parameters.get("y0", 0.0)],
                [seg.parameters.get("x1", 1.0), seg.parameters.get("y1", 0.0)],
                [seg.parameters.get("x2", 1.0), seg.parameters.get("y2", 1.0)],
                [seg.parameters.get("x3", 0.0), seg.parameters.get("y3", 1.0)],
                [seg.parameters.get("x0", 0.0), seg.parameters.get("y0", 0.0)],
            ])
            xs, ys = _sample_polyline_pinned(verts, n)
        elif seg.curve_type == "polygon":
            v_str = seg.parameters.get("vertices_str", "0,0; 1,0; 1,1; 0,1")
            verts = _parse_vertices_str(v_str)
            xs, ys = _sample_polyline_pinned(verts, n)
        else:  # custom
            t_vals = np.linspace(seg.t_min, seg.t_max, n)
            if seg.curve_mode == "parametric":
                xs_raw = _eval_formula_array(seg.x_formula, "t", t_vals)
                ys_raw = _eval_formula_array(seg.y_formula, "t", t_vals)
            else:
                xs_raw = t_vals
                ys_raw = _eval_formula_array(seg.formula, "x", t_vals)
            xs, ys = _resample_polyline_uniform(xs_raw, ys_raw, n)

        valid = np.isfinite(xs) & np.isfinite(ys)
        if not np.any(valid):
            return None, None
        xs, ys = xs[valid], ys[valid]

        # Apply anchoring if start/end node are set
        if gp is not None and len(xs) >= 2:
            si, ei = seg.start_index, seg.end_index
            sv = (si >= 0 and si < len(gp))
            ev = (ei >= 0 and ei < len(gp))
            P0 = np.array([xs[0], ys[0]])
            P1 = np.array([xs[-1], ys[-1]])
            if sv and ev:
                Q0, Q1 = gp[si], gp[ei]
                dx_P, dy_P = P1 - P0
                L_P2 = dx_P**2 + dy_P**2
                if L_P2 > 1e-12:
                    dx_Q, dy_Q = Q1 - Q0
                    A = (dx_Q * dx_P + dy_Q * dy_P) / L_P2
                    B = (dy_Q * dx_P - dx_Q * dy_P) / L_P2
                    xr = xs - P0[0];  yr = ys - P0[1]
                    xs = A * xr - B * yr + Q0[0]
                    ys = B * xr + A * yr + Q0[1]
                else:
                    xs = xs - P0[0] + Q0[0];  ys = ys - P0[1] + Q0[1]
                # Enforce exact endpoints
                xs[0], ys[0] = Q0[0], Q0[1]
                xs[-1], ys[-1] = Q1[0], Q1[1]
            elif sv:
                Q0 = gp[si]
                xs = xs - P0[0] + Q0[0];  ys = ys - P0[1] + Q0[1]
                # Enforce exact start endpoint
                xs[0], ys[0] = Q0[0], Q0[1]
            elif ev:
                Q1 = gp[ei]
                xs = xs - P1[0] + Q1[0];  ys = ys - P1[1] + Q1[1]
                # Enforce exact end endpoint
                xs[-1], ys[-1] = Q1[0], Q1[1]

        return xs, ys

    def handle_quality_check_toggled(self, checked: bool):
        session = self.active_session()
        if session and session.resampled_points is not None:
            self.main_window.canvas_view.load_resampled_data(
                session.resampled_points, checked)

    def handle_show_vertices_toggled(self, checked: bool):
        self.main_window.canvas_view.set_geometry_symbols_visible(checked)

    def handle_show_nodes_toggled(self, checked: bool):
        self.main_window.canvas_view.set_resampled_nodes_visible(checked)

    # ═════════════════════════════════════════════════════════════════════
    # Backend execution
    # ═════════════════════════════════════════════════════════════════════

    def _find_executable(self) -> str | None:
        candidates = [
            "../../../build/surface_resampler",
            "./build/surface_resampler",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def _write_temp_config(self, session: GeometrySession,
                           output_path: str) -> tuple[str, list[str]]:
        """Write config to a temp file and return its path and a list of extra temp files."""
        self._sync_active_curve_segment_from_ui()
        pm = session.project_model

        orig_input = pm.input_file
        orig_output = pm.output_file

        created_files = []

        # If geometry was modified (or it's a blank tab with curve points), save points to a temp .dat
        if (session.is_geometry_modified or not session.file_path) and session.original_points is not None:
            tmp_dat = tempfile.NamedTemporaryFile(
                dir=self.temp_dir, suffix=".dat", delete=False, mode="w")
            np.savetxt(tmp_dat.name, session.original_points, fmt="%.10f")
            pm.input_file = tmp_dat.name
            created_files.append(tmp_dat.name)
            tmp_dat.close()
        else:
            pm.input_file = session.file_path

        pm.output_file = output_path

        # Sync transform from sidebar
        pm.transform = self.main_window.sidebar_view.get_transform_dict()

        tmp_cfg = tempfile.NamedTemporaryFile(
            dir=self.temp_dir, suffix=".json", delete=False, mode="w")
        pm.export_config(tmp_cfg.name)
        created_files.append(tmp_cfg.name)
        tmp_cfg.close()

        # Restore original paths so we don't pollute the project model
        pm.input_file = orig_input
        pm.output_file = orig_output

        return tmp_cfg.name, created_files

    def preview_backend(self):
        """Run backend with a temp output path; display result on canvas."""
        session = self.active_session()
        if not session:
            return
        if not session.project_model.input_file and not session.project_model.segments:
            self.main_window.log_panel.log("No geometry loaded.")
            return
        exe = self._find_executable()
        if not exe:
            self.main_window.log_panel.log(
                "Executable not found. Please build the C++ project.")
            return

        tmp_out = tempfile.NamedTemporaryFile(
            dir=self.temp_dir, suffix="_preview.dat", delete=False)
        tmp_out_name = tmp_out.name
        tmp_out.close()

        cfg_path, created_files = self._write_temp_config(session, tmp_out_name)
        to_cleanup = created_files + [tmp_out_name]

        self.main_window.sidebar_view.preview_btn.setEnabled(False)
        self.main_window.log_panel.log("--- Preview: Starting Backend ---")
        self._run_backend(exe, cfg_path, session,
                          on_finish=lambda rc: self._on_preview_finished(
                              rc, tmp_out_name, to_cleanup, session))

    def save_output(self):
        """Ask user for output path, then run backend and save."""
        session = self.active_session()
        if not session:
            return
        if not session.project_model.input_file and not session.project_model.segments:
            self.main_window.log_panel.log("No geometry loaded.")
            return
        exe = self._find_executable()
        if not exe:
            self.main_window.log_panel.log(
                "Executable not found. Please build the C++ project.")
            return

        default_out = session.project_model.output_file
        import tempfile
        tmp_dir = tempfile.gettempdir()
        if default_out and (tmp_dir in default_out or "/tmp" in default_out or "Temporary" in default_out):
            default_out = ""

        if not default_out:
            default_out = session.default_output_path

        dlg = OutputDialog(default_out, self.main_window)
        if dlg.exec() != OutputDialog.DialogCode.Accepted:
            return

        out_path = dlg.output_path
        session.project_model.output_file = out_path
        cfg_path, created_files = self._write_temp_config(session, out_path)

        self.main_window.sidebar_view.save_btn.setEnabled(False)
        self.main_window.log_panel.log("--- Save: Starting Backend ---")
        self._run_backend(exe, cfg_path, session,
                          on_finish=lambda rc: self._on_save_finished(
                              rc, out_path, created_files, session))

    def generate_json(self):
        session = self.active_session()
        if not session:
            return
        self._sync_active_curve_segment_from_ui()
        if not session.project_model.input_file and not session.project_model.segments:
            self.main_window.log_panel.log("No geometry loaded.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Export JSON Config",
            "gui_config.json", "JSON Files (*.json)")
        if not path:
            return

        pm = session.project_model
        orig_input = pm.input_file
        pm.input_file = session.file_path

        pm.transform = self.main_window.sidebar_view.get_transform_dict()
        pm.export_config(path)

        pm.input_file = orig_input
        self.main_window.log_panel.log(f"Config exported: {path}")

    def _run_backend(self, exe: str, cfg_path: str,
                     session: GeometrySession, on_finish):
        if hasattr(self, "_worker") and self._worker is not None and self._worker.isRunning():
            self.main_window.log_panel.log("Backend is already running. Please wait.")
            return
        self._worker = BackendWorker(exe, cfg_path)
        self._worker.log_signal.connect(self.main_window.log_panel.log)
        self._worker.finished_signal.connect(on_finish)
        self._worker.start()

    def _on_preview_finished(self, rc: int, tmp_out: str, to_cleanup: list[str],
                             session: GeometrySession):
        self.main_window.sidebar_view.preview_btn.setEnabled(True)
        try:
            if rc == 0 and os.path.exists(tmp_out):
                try:
                    pts = np.loadtxt(tmp_out)
                    session.resampled_points = pts
                    if session is self.active_session():
                        show_q = self.main_window.quality_check_cb.isChecked()
                        self.main_window.canvas_view.load_resampled_data(pts, show_q)
                        self.preview_curve_formula()
                    self.main_window.log_panel.log(
                        f"Preview done ({len(pts)} points).")
                except Exception as e:
                    self.main_window.log_panel.log(f"Preview load error: {e}")
            else:
                self.main_window.log_panel.log(
                    f"--- Preview Backend Failed (code {rc}) ---")
        finally:
            for path in to_cleanup:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    self.main_window.log_panel.log(f"Failed to delete temp file {path}: {e}")

    def _on_save_finished(self, rc: int, out_path: str, to_cleanup: list[str],
                          session: GeometrySession):
        self.main_window.sidebar_view.save_btn.setEnabled(True)
        try:
            if rc == 0:
                self.main_window.log_panel.log(
                    f"--- Saved to: {out_path} ---")
                if os.path.exists(out_path):
                    try:
                        pts = np.loadtxt(out_path)
                        session.resampled_points = pts
                        if session is self.active_session():
                            show_q = self.main_window.quality_check_cb.isChecked()
                            self.main_window.canvas_view.load_resampled_data(pts, show_q)
                            self.preview_curve_formula()
                        self.main_window.log_panel.log(
                            f"Loaded result ({len(pts)} points).")
                    except Exception as e:
                        self.main_window.log_panel.log(f"Result load error: {e}")
            else:
                self.main_window.log_panel.log(
                    f"--- Backend Failed (code {rc}) ---")
        finally:
            for path in to_cleanup:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    self.main_window.log_panel.log(f"Failed to delete temp file {path}: {e}")
