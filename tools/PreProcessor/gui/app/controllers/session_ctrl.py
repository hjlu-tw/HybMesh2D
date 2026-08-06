from __future__ import annotations
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from app.utils import block_signals


class SessionControllerMixin:
    """Mixin containing session management, tab switching, and file loading logic."""

    def clear_cad_canvas(self):
        """Clear the transient overlays from the CAD canvas — the resample
        preview, duplicate preview, draw rubber-band, transform gizmos and edge
        control-point handles — WITHOUT deleting the geometry or the model tree
        (non-destructive). Use 'Clear All' to remove the geometry itself."""
        session = self.active_session()
        if session is None:
            return
        session.resampled_points = None
        cv = self.main_window.canvas_view
        cv.clear_resampled()
        cv.clear_duplicate_preview()
        cv.clear_draw_artifacts()
        cv.clear_transform_handles()
        cv.clear_edge_handles()
        self._show_duplicate_preview = False
        cv.clear_curve_preview(session.session_id)
        self.main_window.log_panel.log("Cleared CAD overlays (geometry kept).")

    def clear_all_geometry(self):
        """CAD 'Clear All': remove ALL geometry (every edge, its points and
        splits) from the active session and wipe the canvas — undoable."""
        session = self.active_session()
        if session is None:
            return
        pm = session.project_model
        if not pm.segments and session.original_points is None:
            self.main_window.log_panel.log("Nothing to clear.")
            return
        from app.commands.segment_cmds import ClearGeometryCmd

        def _refresh():
            # Rebuild tree + layer rows + canvas. Used on BOTH execute and undo
            # (undo runs only the command's cb), so undoing Clear All restores the
            # model tree, not just the canvas.
            self._refresh_segment_list()
            self._sync_geometry_list()
            self.redraw_canvas(announce=False)

        cmd = ClearGeometryCmd(session, _refresh)
        session.command_history.execute(cmd)
        self._update_undo_redo_buttons(session)
        self.main_window.update_title(session.display_name, session.is_geometry_modified)
        self.main_window.log_panel.log("Cleared all geometry (undoable).")

    def redraw_canvas(self, announce: bool = True):
        """Force a clean re-render of the CAD canvas: drop any leftover handles,
        gizmos and preview overlays from the previous action, then rebuild the
        active geometry, its edges and the open-endpoint / closing markers.

        This is the single canonical "rebuild everything from the model" path;
        undo/redo route through it (announce=False) so a torn-down edit never
        leaves a stray selection highlight or control-point handle behind."""
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
        if announce:
            self.main_window.log_panel.log("Canvas redrawn.")


    def _sync_geometry_list(self):
        """Rebuild the model tree's top-level session rows (layers).

        Edge children are owned by `_refresh_segment_list`; this method must not
        disturb them, nor steal selection away from a currently-selected edge."""
        sb = self.main_window.sidebar_view
        tree = sb.geometry_tree
        with block_signals(tree):

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
