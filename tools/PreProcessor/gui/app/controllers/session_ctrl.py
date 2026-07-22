from __future__ import annotations
import os
import numpy as np
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QTreeWidgetItem
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor
from app.models.session import GeometrySession, SESSION_COLORS
from app.utils import repo_root


class SessionControllerMixin:
    """Mixin containing session management, tab switching, and file loading logic."""

    def clear_cad_canvas(self):
        """Clear the transient resampled/preview overlay from the CAD canvas
        without deleting the geometry or the model tree (non-destructive)."""
        session = self.active_session()
        if session is None:
            return
        session.resampled_points = None
        cv = self.main_window.canvas_view
        cv.clear_resampled()
        cv.clear_duplicate_preview()
        self.main_window.log_panel.log("Cleared CAD resampled/preview overlay.")

    def redraw_canvas(self):
        """Force a clean re-render of the CAD canvas: drop any leftover handles,
        gizmos and preview overlays from the previous action, then rebuild the
        active geometry, its edges and the open-endpoint / closing markers."""
        cv = self.main_window.canvas_view
        cv.clear_draw_artifacts()
        cv.clear_transform_handles()
        cv.clear_edge_handles()
        cv.clear_duplicate_preview()
        self._show_duplicate_preview = False
        session = self.active_session()
        if session is not None:
            cv.clear_curve_preview(session.session_id)
            self._apply_geometry_update(session)
            self._update_canvas_curve_segments()
            self.highlight_selected_segments()
            self.detect_open_endpoints(session)
        self.main_window.log_panel.log("Canvas redrawn.")

    def new_blank_tab(self):
        # In Mesh Generator / Statistics modes the separate mesh tab strip is
        # active, so "New Tab" there adds a mesh workspace tab rather than a new
        # CAD geometry session.
        if self.main_window.mode_combo.currentIndex() in (1, 2):
            self.add_mesh_tab()
            return
        self._new_session("")

    def reset_all_state(self, new_blank: bool = True):
        """Tear everything down to a clean slate: all CAD sessions/tabs/canvas
        overlays, the global mesh + solver config, any generated mesh and any
        loaded result. Used when loading a pipeline script so the loaded config
        fully replaces the current one instead of merging onto it.

        With ``new_blank`` a single empty CAD session is left open (so a
        following CAD load reuses it); pass False to leave zero sessions.
        """
        from app.models.mesh_config import MeshConfig
        from app.models.solver_config import SolverConfig
        mw = self.main_window

        # Cancel a CAD resample still running for a session we are about to drop,
        # so its finished-callback can't fire against a torn-down session.
        worker = getattr(self, "_worker", None)
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.wait()

        # 1. Remove every CAD session, its canvas layer, and its tab.
        mw.tab_widget.blockSignals(True)
        while self.sessions:
            session = self.sessions.pop(0)
            session.command_history.on_change = None
            try:
                mw.canvas_view.remove_geometry(session.session_id)
            except Exception:
                pass
        while mw.tab_widget.count() > 0:
            mw.tab_widget.removeTab(0)
        self.active_idx = -1
        mw.canvas_view.clear_active_overlays()
        mw.canvas_view.set_active_points(None)
        # Tear down interactive-editing overlays too. These (the draw rubber-band
        # + control points and the transform gizmos) are NOT tied to a session, so
        # the per-session remove_geometry loop above leaves them on the canvas —
        # they would otherwise linger as stray shapes after a pipeline load.
        for teardown in ("clear_draw_artifacts", "clear_transform_handles"):
            fn = getattr(mw.canvas_view, teardown, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
        mw.tab_widget.blockSignals(False)

        # 2. Reset the shared mesh + solver config to defaults.
        self.global_mesh_config = MeshConfig()
        self.global_solver_config = SolverConfig()
        self.global_solver_config.ensure_default_binaries()

        # 3. Drop generated mesh + loaded results state.
        self.global_vtk_mesh = None
        self.global_vtk_path = ""
        self.global_result_path = ""
        self.global_result_data = None
        self._pipeline_result_var = ""

        # 4. Clear the mesh canvas/stats and push the fresh configs to the panels.
        mw.mesh_canvas_view.clear_mesh()
        mw.mesh_canvas_view.update_geometry_previews([])
        mw.mesh_canvas_view.update_seed_previews([])
        mw.mesh_stats_panel.update_stats(None)
        mw.mesh_config_panel.set_config(self.global_mesh_config)
        mw.solver_config_panel.set_config(self.global_solver_config)

        # 5. Leave one clean CAD session so a following load reuses it.
        if new_blank:
            self._new_session("")
        self.sync_mesh_layers_panel()

    def _new_session(self, file_path: str = "") -> GeometrySession:
        """Create a session and add a tab to the shared canvas."""
        session = GeometrySession(file_path)
        # Number a blank session with the smallest free number among the current
        # blank sessions, so "Untitled" starts at 1 and doesn't skip because
        # other files have been loaded (those don't consume a number).
        if not file_path:
            used = {s._untitled_no for s in self.sessions
                    if not s.file_path and getattr(s, "_untitled_no", None)}
            n = 1
            while n in used:
                n += 1
            session._untitled_no = n
        # Keep the toolbar undo/redo buttons in sync on every stack change,
        # regardless of which command dispatch path ran (the no-arg call always
        # reflects whichever session is active at the time).
        session.command_history.on_change = self._update_undo_redo_buttons

        # Append BEFORE addTab so switch_tab (triggered by currentChanged)
        # can already find the session in self.sessions
        self.sessions.append(session)
        self._refresh_session_colors()

        # Add tab (may trigger currentChanged → switch_tab). Blank sessions use
        # their numbered display name ("Untitled 3") so tabs stay distinct.
        label = os.path.basename(file_path) if file_path else session.display_name
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
            
            # Select corresponding session row in the model tree
            sb = self.main_window.sidebar_view
            tree = sb.geometry_tree
            tree.blockSignals(True)
            node = tree.session_item(session.session_id)
            if node is not None:
                tree.setCurrentItem(node)
            tree.blockSignals(False)

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
            # Drop the transform base-point/axis handle from the previous
            # geometry so it does not linger / show a stale pivot.
            self.main_window.canvas_view.clear_transform_handles()
            if session.original_points is not None:
                self.main_window.canvas_view.update_split_points(session.split_indices)
                self.main_window.canvas_view.update_selected_point(session.selected_point_idx)
                
                # Active segment
                if session.current_segment_idx >= 0 and session.current_segment_idx < len(session.project_model.segments):
                    seg = session.project_model.segments[session.current_segment_idx]
                    self.main_window.canvas_view.update_active_segment(seg.start_index, seg.end_index)
            
            # Resampled preview
            if session.resampled_points is not None:
                mode = self.main_window.quality_mode_combo.currentText().lower()
                self.main_window.canvas_view.load_resampled_data(
                    session.resampled_points, self.main_window.quality_check_cb.isChecked(), mode)
            
            # Sync active overlays visibility with session visibility
            self.main_window.canvas_view.set_active_overlays_visible(session.is_visible)
            self._update_undo_redo_buttons(session)

            # Refresh closure state for the newly-active tab: resolve (Auto
            # tracks the geometry), sync the sidebar control, and redraw the
            # dashed closing-edge marker (a single shared canvas item).
            session.project_model.resolve_closure(session.original_points)
            self._sync_closed_mode_ui(session)
            self._refresh_closing_edge(session)

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

        # If a resample backend is still running for THIS session, cancel and
        # wait for it before tearing the session down, so its finished-callback
        # cannot touch a half-removed session. The mesh generator worker is not
        # tied to a CAD tab (it runs on the global mesh config), so it is left
        # untouched here.
        worker = getattr(self, "_worker", None)
        if (worker is not None and worker.isRunning()
                and getattr(self, "_worker_session", None) is session):
            self.main_window.log_panel.log(
                f"Cancelling backend for '{session.display_name}'...")
            worker.cancel()
            worker.wait()

        # Detach the undo/redo button sync so a late callback on this closed
        # session's history can never fire against the surviving active tab.
        session.command_history.on_change = None

        # Remove geometry from shared canvas
        self.main_window.canvas_view.remove_geometry(session.session_id)

        # Block signals during tab removal and list popping to keep states synchronized
        self.main_window.tab_widget.blockSignals(True)
        self.main_window.tab_widget.removeTab(idx)
        self.sessions.pop(idx)
        self._refresh_session_colors()
        self.main_window.tab_widget.blockSignals(False)

        # Deleting a geometry must also drop it from the mesh generator input
        # list, so a removed geometry never silently reappears in the next
        # generated mesh. Only this geometry's file is removed — any other
        # geometries in a multi-geometry mesh are left untouched. Done after the
        # session is popped so the Geometry Layers list resyncs to the real set.
        self.remove_session_from_mesh_config(session)

        # The mesh canvas previews reflect the (decoupled) global mesh config,
        # not the active CAD tab. Refresh from global geom files rather than
        # clearing, so closing a CAD tab does not wipe the *other* geometries
        # of a multi-geometry mesh.
        if idx == self.active_idx:
            geom_files = (self.global_mesh_config.geom_files
                          if self.global_mesh_config else [])
            self.main_window.mesh_canvas_view.update_geometry_previews(geom_files)

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
        """Rebuild the model tree's top-level session rows (layers).

        Edge children are owned by `_refresh_segment_list`; this method must not
        disturb them, nor steal selection away from a currently-selected edge."""
        sb = self.main_window.sidebar_view
        tree = sb.geometry_tree
        tree.blockSignals(True)

        live_ids = {s.session_id for s in self.sessions}
        # Drop rows whose session was closed.
        for i in reversed(range(tree.topLevelItemCount())):
            if tree.session_id_of(tree.topLevelItem(i)) not in live_ids:
                tree.takeTopLevelItem(i)

        # One row per session, in session order. Reuse the existing row for a
        # session_id (take/insert preserves its edge children) so a resync does
        # not wipe the active layer's edges.
        for i, session in enumerate(self.sessions):
            item = tree.session_item(session.session_id)
            if item is None:
                item = QTreeWidgetItem()
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setData(0, Qt.ItemDataRole.UserRole, ("session", session.session_id))
                tree.insertTopLevelItem(i, item)
            else:
                cur = tree.indexOfTopLevelItem(item)
                if cur != i:
                    tree.takeTopLevelItem(cur)
                    tree.insertTopLevelItem(i, item)
            item.setText(0, session.display_name)
            item.setCheckState(
                0, Qt.CheckState.Checked if session.is_visible else Qt.CheckState.Unchecked)
            if hasattr(session, "color") and session.color:
                item.setForeground(0, QColor(session.color))

        # Highlight the active layer row — but only when no edge is selected, so
        # we never clobber an active edge selection (edges share this widget).
        if not tree.selected_edge_indices() and 0 <= self.active_idx < len(self.sessions):
            node = tree.session_item(self.sessions[self.active_idx].session_id)
            if node is not None:
                tree.setCurrentItem(node)

        tree.blockSignals(False)

    def handle_geom_visibility_changed(self, item, column: int = 0):
        sb = self.main_window.sidebar_view
        if sb.geometry_tree.kind(item) != "session":
            return
        session_id = sb.geometry_tree.session_id_of(item)
        if session_id is None:
            return
        is_checked = item.checkState(0) == Qt.CheckState.Checked
        for session in self.sessions:
            if session.session_id == session_id:
                session.is_visible = is_checked
                self.main_window.canvas_view.set_geometry_visible(session_id, is_checked)
                if session is self.active_session():
                    self.main_window.canvas_view.set_active_overlays_visible(is_checked)
                break

    def handle_tree_current_changed(self, current, previous=None):
        """A session row becoming current navigates to that layer's tab. Edge
        rows do not navigate (their selection is handled separately)."""
        sb = self.main_window.sidebar_view
        if sb.geometry_tree.kind(current) != "session":
            return
        session_id = sb.geometry_tree.session_id_of(current)
        for i, s in enumerate(self.sessions):
            if s.session_id == session_id:
                if i != self.active_idx:
                    self.main_window.tab_widget.setCurrentIndex(i)
                break

    def handle_geom_list_double_clicked(self, item, column: int = 0):
        session_id = self.main_window.sidebar_view.geometry_tree.session_id_of(item)
        if session_id is not None:
            self.main_window.canvas_view.fit_to_geometry(session_id)

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

    def load_stl_geometry(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.main_window, "Import STL Surface(s) — z=0 only",
            "examples/geometries", "STL Files (*.stl)")
        for fp in file_paths:
            if os.path.exists(fp):
                self._load_stl_file(fp)
            else:
                self.main_window.log_panel.log(f"File not found: {fp}")

    def _load_stl_file(self, file_path: str):
        """Load a planar (z=0) STL, auto-detect its boundary outline as surface
        points, and bring each detected loop in as a geometry session.

        The boundary points are written to temporary ``.dat`` files so the rest
        of the pipeline (resampler, mesh generator, export) is unchanged.
        """
        from app.services.stl_loader import load_planar_boundary_loops, STLPlanarError
        try:
            loops = load_planar_boundary_loops(file_path)
        except STLPlanarError as e:
            self.main_window.log_panel.log(f"[STL] {e}")
            QMessageBox.warning(self.main_window, "STL Import Error", str(e))
            return
        except Exception as e:
            self.main_window.log_panel.log(
                f"[STL] Failed to read '{os.path.basename(file_path)}': {e}")
            return

        base = os.path.splitext(os.path.basename(file_path))[0]
        multi = len(loops) > 1
        for i, pts in enumerate(loops):
            suffix = f"_loop{i + 1}" if multi else ""
            dat_path = os.path.join(self.temp_dir, f"{base}{suffix}.dat")
            try:
                np.savetxt(dat_path, pts, fmt="%.10f")
            except Exception as e:
                self.main_window.log_panel.log(f"[STL] Could not stage loop {i + 1}: {e}")
                continue
            self._load_geometry_file(dat_path, record_recent=False)

        # Record the original STL (not the temp .dat) in the recent-files list.
        self.update_recent_files(os.path.abspath(file_path))
        n_total = sum(len(p) for p in loops)
        self.main_window.log_panel.log(
            f"Imported STL '{os.path.basename(file_path)}' — detected "
            f"{len(loops)} boundary loop(s), {n_total} surface points (z=0 plane).")

    def _load_geometry_file(self, file_path: str, record_recent: bool = True):
        if file_path.lower().endswith(".json"):
            self._load_json_config_direct(file_path)
            return
        if file_path.lower().endswith(".stl"):
            self._load_stl_file(file_path)
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
                session._untitled_no = None  # no longer a blank/untitled session
                session.color = SESSION_COLORS[
                    (session.session_id - 1) % len(SESSION_COLORS)]
            else:
                session = self._new_session(file_path)

            session.project_model.input_file = file_path
            session.project_model.output_file = session.default_output_path
            from app.services.geometry_service import load_points_dat
            session.original_points = load_points_dat(file_path)

            abs_path = os.path.abspath(file_path)
            if abs_path not in session.mesh_config.geom_files:
                session.mesh_config.geom_files.append(abs_path)
            if record_recent:
                self.update_recent_files(abs_path)

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
        from app.models.project import CONFIG_FORMAT_VERSION
        # Missing version = legacy v0 (explicit, not "assume current"). A file
        # older than this build is migrated field-by-field by ProjectModel;
        # a NEWER file is loaded read-only best-effort with a clear warning.
        cfg_version = int(config.get("format_version", 0))
        if cfg_version > CONFIG_FORMAT_VERSION:
            self.main_window.log_panel.log(
                f"[WARNING] Config format version {cfg_version} is newer than this "
                f"build supports ({CONFIG_FORMAT_VERSION}). Loading read-only, "
                "best-effort — some settings may be ignored. Save with this build "
                "to write a compatible file."
            )
        elif cfg_version < CONFIG_FORMAT_VERSION:
            self.main_window.log_panel.log(
                f"[INFO] Migrating config from format v{cfg_version} to "
                f"v{CONFIG_FORMAT_VERSION}."
            )

        input_file = config.get("input_file", "")
        if not input_file:
            self.main_window.log_panel.log("[WARNING] JSON config lacks 'input_file'. Configuration load aborted.")
            return

        # Try to resolve relative path if not absolute
        if input_file and not os.path.isabs(input_file):
            candidate1 = os.path.abspath(os.path.join(os.path.dirname(config_path), input_file))
            candidate2 = os.path.abspath(os.path.join(os.path.dirname(config_path), "..", "..", input_file))
            root_dir = repo_root()
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
            if input_file:
                session._untitled_no = None  # adopted a file; no longer untitled
            self._refresh_session_colors()
        else:
            session = self._new_session(input_file)

        session.project_model.load_from_config(config)

        if input_file and os.path.exists(input_file):
            try:
                from app.services.geometry_service import load_points_dat
                session.original_points = load_points_dat(input_file)
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

        self.update_recent_files(config_path)
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

    def update_recent_files(self, file_path: str):
        if not file_path:
            return
        abs_path = os.path.abspath(file_path)
        settings = QSettings("HybMesh", "PreProcessor")
        files = settings.value("recentFiles", [])
        if not isinstance(files, list):
            files = []
        if abs_path in files:
            files.remove(abs_path)
        files.insert(0, abs_path)
        files = files[:10]  # keep up to 10 files
        settings.setValue("recentFiles", files)
        self.main_window.refresh_recent_files_menu(files, self)

    def init_recent_files(self):
        settings = QSettings("HybMesh", "PreProcessor")
        files = settings.value("recentFiles", [])
        if not isinstance(files, list):
            files = []
        self.main_window.refresh_recent_files_menu(files, self)

    def load_recent_file(self, file_path: str):
        if not os.path.exists(file_path):
            self.main_window.log_panel.log(f"Recent file not found: {file_path}")
            # Remove from settings
            settings = QSettings("HybMesh", "PreProcessor")
            files = settings.value("recentFiles", [])
            if isinstance(files, list) and file_path in files:
                files.remove(file_path)
                settings.setValue("recentFiles", files)
                self.main_window.refresh_recent_files_menu(files, self)
            return
        
        if file_path.lower().endswith(".json"):
            try:
                import json
                with open(file_path) as f:
                    config = json.load(f)
                self._apply_json_config(config, file_path)
            except Exception as e:
                self.main_window.log_panel.log(f"Error loading JSON: {e}")
        else:
            self._load_geometry_file(file_path)
