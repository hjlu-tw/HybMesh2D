from __future__ import annotations
import os
import numpy as np
from PyQt6.QtWidgets import QMessageBox
from app.models.session import GeometrySession


class SessionTabsControllerMixin:
    """Mixin containing tab creation / switching / closing and session lifecycle logic."""

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

    def _refresh_session_colors(self):
        """Re-assign palette colors to active sessions to keep coloring organized and synced."""
        from app.models.session import SESSION_COLORS
        for i, session in enumerate(self.sessions):
            new_color = SESSION_COLORS[i % len(SESSION_COLORS)]
            session.color = new_color
            if hasattr(self.main_window, 'canvas_view'):
                self.main_window.canvas_view.update_geometry_color(session.session_id, new_color)
