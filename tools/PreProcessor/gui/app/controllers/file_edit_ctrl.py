from __future__ import annotations
import numpy as np
from app.commands.vertex_cmds import ReplaceGeometryPointsCmd


class FileEditControllerMixin:
    """Mixin for editing an imported (discrete/file) edge's endpoints: the
    whole-shape corner-vertex editing session, its draggable handles, and the
    modeless numeric dialog's commit/cancel."""

    # ── Editing an imported (discrete/file) edge's endpoints ────────────────

    def _begin_file_edit(self, seg):
        """Double-click on an imported (discrete) edge → edit the WHOLE connected
        shape by its corner vertices.  Each edge re-fits between its (moving)
        corners, so dragging a shared corner redistributes BOTH adjacent edges —
        like editing a shape in industrial CAD."""
        session = self.active_session()
        gp = session.original_points if session else None
        # The owner builds the edge specs and takes the pristine snapshot; it
        # refuses a geometry whose file segments describe no usable edge.
        if not self.edge_edit.begin_shape(
                seg, gp, session.project_model.segments if session else []):
            if gp is not None and len(gp):
                self.log("This geometry can't be edited directly.")
            return
        ci0, ci1 = self.edge_edit.edge_corners

        canvas = self.main_window.canvas_view
        canvas.update_active_segments_pts([])
        canvas.clear_transform_handles()
        self._show_file_handles()

        from app.views.shape_dialog import FileEndpointDialog
        dlg = FileEndpointDialog(seg.id, tuple(gp[ci0]), tuple(gp[ci1]),
                                 changed_cb=self._on_file_dialog_changed,
                                 parent=self.main_window)
        dlg.setModal(False)
        # Modeless, kept above the app's own main window (Tool window) but not
        # above other apps, and nudged off centre (#2/#8).
        from app.utils import keep_on_top, offset_popup
        keep_on_top(dlg)
        dlg.accepted.connect(self._commit_file_edit)
        dlg.rejected.connect(self._cancel_file_edit)
        dlg.finished.connect(lambda _r, d=dlg: d.deleteLater())
        self.edge_edit.attach_shape_dialog(dlg)
        offset_popup(dlg, self.main_window)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _show_file_handles(self):
        """One draggable handle per corner vertex of the whole shape."""
        canvas = self.main_window.canvas_view
        canvas.show_edge_handles([
            {"id": hid, "pos": pos}
            for hid, pos in self.edge_edit.handle_points()])

    def _on_file_handle_dragged(self, handle_id, x, y, finished):
        session = self.active_session()
        pts = self.edge_edit.move_corner(handle_id, x, y)
        if session is None or pts is None:
            return
        session.original_points = pts
        self._redraw_file_geometry(session)
        # Mirror into the numeric dialog if this corner is one of its two.
        dlg = self.edge_edit.shape_dialog
        key = self.edge_edit.corner_key(handle_id)
        if dlg is not None and key in self.edge_edit.edge_corners:
            dlg.set_points(*self.edge_edit.edge_corner_points())
        if finished:
            self._show_file_handles()

    def _on_file_dialog_changed(self, p0, p1):
        session = self.active_session()
        pts = self.edge_edit.set_edge_corners(p0, p1)
        if session is None or pts is None:
            return
        session.original_points = pts
        self._redraw_file_geometry(session)
        self._show_file_handles()

    def _redraw_file_geometry(self, session):
        gp = session.original_points
        pm = session.project_model
        points = gp.copy()
        if pm.is_closed and len(points) > 0 and not np.allclose(points[0], points[-1]):
            points = np.vstack([points, points[0]])
        canvas = self.main_window.canvas_view
        canvas.update_geometry(session.session_id, points)
        canvas.set_active_points(points)

    def _commit_file_edit(self):
        session = self.active_session()
        done = self.edge_edit.end_shape()
        orig = done.orig if done is not None else None
        self._clear_file_edit_canvas()
        if session is None:
            return
        new_points = session.original_points
        changed = (orig is not None and new_points is not None
                   and not np.array_equal(orig, new_points))
        if changed:
            # The new layout was applied in place during the drag; route it
            # through the undo stack (restore old first so execute() applies it).
            session.original_points = orig

            def refresh(_s=session):
                if _s is self.active_session():
                    self._apply_geometry_update(_s)

            cmd = ReplaceGeometryPointsCmd(session, orig, new_points,
                                           refresh_cb=refresh,
                                           label="Edit geometry shape")
            session.command_history.execute(cmd)
        else:
            self._apply_geometry_update(session)
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, True)
        self.log("Updated geometry shape.")

    def _cancel_file_edit(self):
        session = self.active_session()
        done = self.edge_edit.end_shape()
        if session is not None and done is not None and done.orig is not None:
            session.original_points = done.orig
        self._clear_file_edit_canvas()
        if session is not None:
            self._apply_geometry_update(session)
        self.log("Shape edit cancelled (reverted).")

    def _clear_file_edit_canvas(self):
        """Drop the shape session's canvas decoration. The state itself is the
        owner's and is already gone by the time this runs."""
        self.main_window.canvas_view.clear_edge_handles()
        self._refresh_endpoint_markers()
