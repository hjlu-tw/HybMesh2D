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
from PyQt6.QtCore import QTimer

from app.views.main_window import MainWindow
from app.views.canvas import CanvasView
from app.views.output_dialog import OutputDialog
from app.models.session import GeometrySession
from app.models.project import ProjectModel
from app.models.segment import SegmentModel
from app.workers.backend_run import BackendWorker
from app.commands.split_cmds import AddSplitCmd, RemoveSplitCmd, AutoDetectSplitCmd
from app.commands.vertex_cmds import InsertVertexCmd
from app.commands.segment_cmds import UpdateStrategyCmd, UpdateParamsCmd


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


# ═════════════════════════════════════════════════════════════════════════════

class AppController:

    def __init__(self):
        self.main_window = MainWindow()
        self.sessions: list[GeometrySession] = []
        self.active_idx: int = -1

        self._connecting_signals = False  # guard against re-entrant connects
        self._param_snapshot: dict = {}   # for UpdateParamsCmd debounce

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
        sb.segment_list.currentRowChanged.connect(self.handle_segment_selected)
        sb.strategy_combo.currentTextChanged.connect(
            self.handle_strategy_changed)
        sb.is_closed_combo.currentTextChanged.connect(
            self.handle_is_closed_changed)
        sb.preview_btn.clicked.connect(self.preview_backend)
        sb.save_btn.clicked.connect(self.save_output)
        sb.generate_btn.clicked.connect(self.generate_json)
        sb.add_curve_seg_btn.clicked.connect(self.add_curve_segment)
        sb.curve_preview_btn.clicked.connect(self.preview_curve_formula)

        # Parameter-change signals (all route to update_segment_params)
        for widget in [sb.uniform_n, sb.tanh_n, sb.tanh_intensity,
                       sb.cosine_n, sb.curv_n, sb.curv_sens,
                       sb.geo_n, sb.geo_ratio, sb.uniform_spacing]:
            widget.valueChanged.connect(self.update_segment_params)
        sb.uniform_type_combo.currentTextChanged.connect(
            self.update_segment_params)
        sb.match_previous_cb.toggled.connect(self.update_match_previous)

        # Advanced settings
        sb.global_spline_cb.toggled.connect(self.handle_global_spline_changed)

        # New tab button
        sb.new_tab_btn.clicked.connect(self.new_blank_tab)
        sb.auto_detect_btn.clicked.connect(self.auto_detect_segments)

        # Geometries visibility / focus
        sb.geom_list.itemChanged.connect(self.handle_geom_visibility_changed)
        sb.geom_list.currentRowChanged.connect(self.handle_geom_list_row_changed)
        sb.geom_list.itemDoubleClicked.connect(self.handle_geom_list_double_clicked)
        sb.focus_geom_btn.clicked.connect(self.focus_to_selected_geometry)

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

    def auto_detect_segments(self):
        session = self.active_session()
        if not session or session.original_points is None:
            self.main_window.log_panel.log("No geometry loaded.")
            return

        points = session.original_points.copy()
        pm = session.project_model
        if pm.is_closed and len(points) > 0:
            if not np.allclose(points[0], points[-1]):
                points = np.vstack((points, points[0]))

        new_indices = self._auto_detect_features(points)
        cmd = AutoDetectSplitCmd(
            session, new_indices,
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Auto-detected {len(new_indices) - 1} segments based on sharp angles.")

    def _new_session(self, file_path: str = "") -> GeometrySession:
        """Create a session and add a tab to the shared canvas."""
        session = GeometrySession(file_path)

        # Append BEFORE addTab so switch_tab (triggered by currentChanged)
        # can already find the session in self.sessions
        self.sessions.append(session)

        # Add tab (may trigger currentChanged → switch_tab)
        label = os.path.basename(file_path) if file_path else "Untitled"
        self.main_window.tab_widget.addTab(label)

        # Add geometry layer to the shared canvas
        self.main_window.canvas_view.add_geometry(
            session.session_id, None, session.color)

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
            if session.original_points is not None:
                self.main_window.canvas_view.update_split_points(session.split_indices)
                self.main_window.canvas_view.update_selected_point(session.selected_point_idx)
                
                # Active segment
                if session.current_segment_idx >= 0 and session.current_segment_idx < len(session.project_model.segments):
                    seg = session.project_model.segments[session.current_segment_idx]
                    self.main_window.canvas_view.update_active_segment(seg.start_idx, seg.end_idx)
                
                # Resampled preview
                if session.resampled_points is not None:
                    self.main_window.canvas_view.load_resampled_data(session.resampled_points)
            
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

        self.main_window.tab_widget.removeTab(idx)
        self.sessions.pop(idx)

        # Adjust active index
        n = len(self.sessions)
        if n == 0:
            self.active_idx = -1
            self._clear_sidebar()
            self.main_window.canvas_view.clear_active_overlays()
            self.main_window.canvas_view.set_active_points(None)
        else:
            self.active_idx = min(idx, n - 1)
            self.main_window.tab_widget.setCurrentIndex(self.active_idx)

        self._sync_geometry_list()

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

    def handle_geom_visibility_changed(self, item: QListWidgetItem):
        session_id = item.data(Qt.ItemDataRole.UserRole)
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
        if row != self.active_idx:
            self.main_window.tab_widget.setCurrentIndex(row)

    def handle_geom_list_double_clicked(self, item: QListWidgetItem):
        session_id = item.data(Qt.ItemDataRole.UserRole)
        self.main_window.canvas_view.fit_to_geometry(session_id)

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
                f"{n_pts} points, {n_seg} auto-detected segments.")
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

        if re_detect:
            session.split_indices = self._auto_detect_features(points)

        # Only update active overlays if this is the active session
        if session is self.active_session():
            self.main_window.canvas_view.set_active_points(points)
            self.main_window.canvas_view.update_split_points(session.split_indices)
            session.selected_point_idx = None
            self.main_window.canvas_view.update_selected_point(None)

            # Reset sidebar point info
            sb = self.main_window.sidebar_view
            sb.selected_info.setText("Selected Point: None")
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

    def _refresh_segment_list(self):
        session = self.active_session()
        if not session:
            return
        sb = self.main_window.sidebar_view
        sb.segment_list.blockSignals(True)
        sb.segment_list.clear()
        for seg in session.project_model.segments:
            if seg.type == "curve":
                lbl = (f"Segment {seg.id}: Curve "
                       f"({'Param' if seg.curve_mode == 'parametric' else 'Explicit'})")
            else:
                lbl = (f"Segment {seg.id}: "
                       f"Idx {seg.start_index} → {seg.end_index}")
            sb.segment_list.addItem(lbl)
        sb.segment_list.blockSignals(False)
        session.current_segment_idx = -1
        self.main_window.canvas_view.update_active_segment(None, None)

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
            sb.file_name_label.setText("No file loaded")
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
        sb.selected_info.setText("Selected Point: None")
        sb.split_btn.setEnabled(False)
        sb.remove_split_btn.setEnabled(False)

        self._refresh_segment_list()
        self._sync_geometry_list()

    def _clear_sidebar(self):
        sb = self.main_window.sidebar_view
        sb.file_name_label.setText("No file loaded")
        sb.segment_list.clear()
        sb.selected_info.setText("Selected Point: None")
        sb.split_btn.setEnabled(False)
        sb.remove_split_btn.setEnabled(False)
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
        sb.selected_info.setText(f"Selected Point: Index {idx}")

        n_pts = (len(session.original_points)
                 if session.original_points is not None else 0)
        is_endpoint = (idx == 0 or idx == n_pts - 1)
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

    def handle_segment_selected(self, row: int):
        session = self.active_session()
        if not session:
            return
        sb = self.main_window.sidebar_view
        if row < 0:
            self.main_window.canvas_view.update_active_segment(None, None)
            session.current_segment_idx = -1
            return

        session.current_segment_idx = row
        seg = session.project_model.get_segment(row)
        if not seg:
            self.main_window.canvas_view.update_active_segment(None, None)
            return

        # Highlight on canvas
        if seg.type == "file":
            self.main_window.canvas_view.update_active_segment(
                seg.start_index, seg.end_index)
            self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, True)
        else:
            self.main_window.canvas_view.update_active_segment(None, None)
            self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, False)

        # Populate sidebar
        sb.show_segment_props(True)
        if seg.type == "curve":
            sb.segment_type_label.setText("📐 Curve Segment")
            sb.show_curve_segment(seg)
            sb.strategy_combo.setVisible(False)
            sb.param_stack.setVisible(False)
        else:
            sb.segment_type_label.setText("📁 File Segment")
            sb.show_file_segment(seg.start_index, seg.end_index)
            sb.strategy_combo.setVisible(True)
            sb.param_stack.setVisible(True)
            sb.strategy_combo.blockSignals(True)
            sb.strategy_combo.setCurrentText(seg.strategy)
            sb.strategy_combo.blockSignals(False)
            sb.switch_param_form(seg.strategy)
            self._populate_form_from_segment(seg)

        sb.match_previous_cb.blockSignals(True)
        sb.match_previous_cb.setChecked(seg.match_previous)
        sb.match_previous_cb.blockSignals(False)

        # Snapshot params for undo
        self._param_snapshot = copy.deepcopy(seg.parameters)

    def handle_strategy_changed(self, strategy_name: str):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return
        old_params_snapshot = copy.deepcopy(self._param_snapshot)
        cmd = UpdateStrategyCmd(
            session, session.current_segment_idx, strategy_name,
            repopulate_cb=self._repopulate_strategy)
        session.command_history.execute(cmd)
        self._param_snapshot = copy.deepcopy(seg.parameters)
        self.main_window.log_panel.log(
            f"Segment {seg.id}: strategy → {strategy_name}")

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
                sb.uniform_type_combo.setCurrentText("Specify Spacing")
                sb.uniform_spacing.setValue(p["spacing"])
                sb._toggle_uniform_mode(True)
            else:
                sb.uniform_type_combo.setCurrentText("Specify Num Points")
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
        block(False)

    def update_segment_params(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return
        old_params = copy.deepcopy(self._param_snapshot)
        self._read_params_into_segment(seg)
        # Only push to history when value actually changes
        new_params = copy.deepcopy(seg.parameters)
        if new_params != old_params:
            cmd = UpdateParamsCmd(
                session, session.current_segment_idx, old_params, new_params)
            # Push without re-executing (already applied by read)
            session.command_history._undo_stack.append(cmd)
            session.command_history._redo_stack.clear()
            self._param_snapshot = new_params

    def _read_params_into_segment(self, seg: SegmentModel):
        sb = self.main_window.sidebar_view
        seg.parameters.clear()
        if seg.strategy == "uniform":
            if sb.uniform_type_combo.currentText() == "Specify Spacing":
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

    def update_match_previous(self, checked: bool):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if seg:
            seg.match_previous = checked

    # ═════════════════════════════════════════════════════════════════════
    # Global settings
    # ═════════════════════════════════════════════════════════════════════

    def handle_is_closed_changed(self, text: str):
        session = self.active_session()
        if session:
            session.project_model.is_closed = (text == "True")
            self._apply_geometry_update(session)

    def handle_global_spline_changed(self, checked: bool):
        session = self.active_session()
        if session:
            session.project_model.global_spline = checked

    # ═════════════════════════════════════════════════════════════════════
    # Curve segment
    # ═════════════════════════════════════════════════════════════════════

    def add_curve_segment(self):
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No geometry session active.")
            return
        seg = session.project_model.add_curve_segment()
        self._refresh_segment_list()
        # Select the new segment in the list
        sb = self.main_window.sidebar_view
        new_row = len(session.project_model.segments) - 1
        sb.segment_list.setCurrentRow(new_row)
        self.main_window.log_panel.log(
            f"Added Curve Segment {seg.id}.")

    def preview_curve_formula(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve":
            return

        # Read current form values into seg
        sb = self.main_window.sidebar_view
        n = sb.curve_n.value()
        t_min = sb.curve_t_min.value()
        t_max = sb.curve_t_max.value()
        is_param = sb.curve_mode_param.isChecked()

        t_vals = np.linspace(t_min, t_max, n)
        try:
            if is_param:
                x_expr = sb.curve_x_formula.text()
                y_expr = sb.curve_y_formula.text()
                xs = _eval_formula_array(x_expr, "t", t_vals)
                ys = _eval_formula_array(y_expr, "t", t_vals)
                seg.curve_mode = "parametric"
                seg.x_formula = x_expr
                seg.y_formula = y_expr
            else:
                expr = sb.curve_formula.text()
                xs = t_vals
                ys = _eval_formula_array(expr, "x", t_vals)
                seg.curve_mode = "explicit"
                seg.formula = expr

            seg.t_min = t_min
            seg.t_max = t_max
            seg.parameters["n_points"] = n

            valid = np.isfinite(xs) & np.isfinite(ys)
            pts = np.column_stack([xs[valid], ys[valid]])
            self.main_window.canvas_view.update_curve_preview(pts)
            self.main_window.log_panel.log(
                f"Curve preview updated ({len(pts)} points).")
        except Exception as e:
            self.main_window.log_panel.log(f"Formula error: {e}")
            self.main_window.canvas_view.clear_curve_preview()

    # ═════════════════════════════════════════════════════════════════════
    # Undo / Redo
    # ═════════════════════════════════════════════════════════════════════

    def undo(self):
        session = self.active_session()
        if session:
            if session.command_history.undo():
                self.main_window.log_panel.log("Undo.")
                self._sync_geometry_list()
            else:
                self.main_window.log_panel.log("Nothing to undo.")

    def redo(self):
        session = self.active_session()
        if session:
            if session.command_history.redo():
                self.main_window.log_panel.log("Redo.")
                self._sync_geometry_list()
            else:
                self.main_window.log_panel.log("Nothing to redo.")

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
        pm = session.project_model

        orig_input = pm.input_file
        orig_output = pm.output_file

        created_files = []

        # If geometry was modified, save modified points to a temp .dat
        if session.is_geometry_modified and session.original_points is not None:
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
        if not session or not session.project_model.input_file:
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
        if not session or not session.project_model.input_file:
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
        if not session or not session.project_model.input_file:
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
                        self.main_window.canvas_view.load_resampled_data(pts)
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
                            self.main_window.canvas_view.load_resampled_data(pts)
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
