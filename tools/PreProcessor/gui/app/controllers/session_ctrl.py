from __future__ import annotations
import os
import numpy as np
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QListWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from app.models.session import GeometrySession

class SessionControllerMixin:
    """Mixin containing session management, tab switching, and file loading logic."""

    def new_blank_tab(self):
        self._new_session("")

    def _new_session(self, file_path: str = "") -> GeometrySession:
        """Create a session and add a tab to the shared canvas."""
        session = GeometrySession(file_path)

        # Append BEFORE addTab so switch_tab (triggered by currentChanged)
        # can already find the session in self.sessions
        self.sessions.append(session)
        self._refresh_session_colors()

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
            self._update_undo_redo_buttons(session)

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
        self._refresh_session_colors()
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
        for session in self.sessions:
            name = session.display_name
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            state = Qt.CheckState.Checked if session.is_visible else Qt.CheckState.Unchecked
            item.setCheckState(state)
            item.setData(Qt.ItemDataRole.UserRole, session.session_id)
            if hasattr(session, "color") and session.color:
                item.setForeground(QColor(session.color))
            sb.geom_list.addItem(item)

        if 0 <= self.active_idx < sb.geom_list.count():
            sb.geom_list.setCurrentRow(self.active_idx)

        sb.geom_list.blockSignals(False)

    def handle_geom_visibility_changed(self, item: QListWidgetItem):
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id is None:
            return
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
        current = item.checkState() == Qt.CheckState.Checked
        item.setCheckState(
            Qt.CheckState.Unchecked if current else Qt.CheckState.Checked)

    def focus_to_selected_geometry(self):
        session = self.active_session()
        if session:
            self.main_window.canvas_view.fit_to_geometry(session.session_id)

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
        if file_path.lower().endswith(".json"):
            self._load_json_config_direct(file_path)
            return
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

            abs_path = os.path.abspath(file_path)
            if abs_path not in session.mesh_config.geom_files:
                session.mesh_config.geom_files.append(abs_path)

            self._apply_geometry_update(session, re_detect=True)
            if session is self.active_session():
                self._sync_sidebar_to_session()
            n_pts = len(session.original_points)
            n_seg = max(0, len(session.split_indices) - 1)
            self.main_window.log_panel.log(
                f"Loaded '{os.path.basename(file_path)}' — "
                f"{n_pts} points, {n_seg} auto-detected edges.")
        except Exception as e:
            self.main_window.log_panel.log(f"Error loading file: {e}")

    def _load_json_config_direct(self, file_path: str):
        try:
            import json
            with open(file_path) as f:
                config = json.load(f)
            self._apply_json_config(config, file_path)
            self.main_window.log_panel.log(f"Loaded JSON configuration from '{os.path.basename(file_path)}'")
        except Exception as e:
            self.main_window.log_panel.log(f"Error loading JSON: {e}")

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
        if not input_file:
            self.main_window.log_panel.log("[WARNING] JSON config lacks 'input_file'. Configuration load aborted.")
            return

        # Try to resolve relative path if not absolute
        if input_file and not os.path.isabs(input_file):
            candidate1 = os.path.abspath(os.path.join(os.path.dirname(config_path), input_file))
            candidate2 = os.path.abspath(os.path.join(os.path.dirname(config_path), "..", "..", input_file))
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
            candidate3 = os.path.abspath(os.path.join(root_dir, input_file))
            
            if os.path.exists(candidate1):
                input_file = candidate1
            elif os.path.exists(candidate2):
                input_file = candidate2
            elif os.path.exists(candidate3):
                input_file = candidate3

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
            self._refresh_session_colors()
        else:
            session = self._new_session(input_file)

        session.project_model.load_from_config(config)

        if input_file and os.path.exists(input_file):
            try:
                session.original_points = np.loadtxt(input_file)
                abs_path = os.path.abspath(input_file)
                if abs_path not in session.mesh_config.geom_files:
                    session.mesh_config.geom_files.append(abs_path)
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

    def _refresh_session_colors(self):
        """Re-assign palette colors to active sessions to keep coloring organized and synced."""
        from app.models.session import SESSION_COLORS
        for i, session in enumerate(self.sessions):
            new_color = SESSION_COLORS[i % len(SESSION_COLORS)]
            session.color = new_color
            if hasattr(self.main_window, 'canvas_view'):
                self.main_window.canvas_view.update_geometry_color(session.session_id, new_color)
