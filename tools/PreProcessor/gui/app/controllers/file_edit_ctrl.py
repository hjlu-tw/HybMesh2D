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
        if gp is None or len(gp) == 0:
            return
        n = len(gp)

        # Build per-edge specs (corner indices + interior indices) for every
        # discrete edge, and the set of corner vertices.
        specs = []
        corners = set()
        for s in session.project_model.segments:
            if s.type != "file":
                continue
            si = s.start_index
            if s.end_index < n:
                ei = s.end_index
                interior = list(range(si + 1, ei))
            else:  # closing edge wraps back to the first point
                ei = 0
                interior = list(range(si + 1, n))
            if not (0 <= si < n and 0 <= ei < n) or si == ei:
                continue
            specs.append({"i0": si, "i1": ei, "interior": interior})
            corners.add(si)
            corners.add(ei)
        if not specs or not corners:
            self.main_window.log_panel.log("This geometry can't be edited directly.")
            return

        # Corners of the double-clicked edge (shown in the numeric dialog).
        ci0 = seg.start_index
        ci1 = seg.end_index if seg.end_index < n else 0

        self._pending_file = (ci0, ci1)
        self._pending_file_seg = seg
        self._pending_geom_orig = gp.copy()
        self._pending_geom_specs = specs
        self._pending_geom_corners = sorted(corners)
        self._pending_geom_cur = {k: list(gp[k]) for k in corners}

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
        self._pending_file_dialog = dlg
        offset_popup(dlg, self.main_window)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _show_file_handles(self):
        """One draggable handle per corner vertex of the whole shape."""
        session = self.active_session()
        canvas = self.main_window.canvas_view
        if self._pending_file is None or session is None:
            return
        cur = self._pending_geom_cur
        canvas.show_edge_handles([
            {"id": f"c{k}", "pos": tuple(cur[k])}
            for k in self._pending_geom_corners])

    def _refit_geom(self, session):
        """Re-fit every edge between its current corners via the similarity
        transform from its ORIGINAL layout — interior points redistribute,
        straight edges stay straight between their corners."""
        gp = session.original_points
        orig = self._pending_geom_orig
        cur = self._pending_geom_cur
        for spec in self._pending_geom_specs:
            i0, i1 = spec["i0"], spec["i1"]
            op0, op1 = orig[i0], orig[i1]
            cp0, cp1 = cur[i0], cur[i1]
            dxP, dyP = float(op1[0] - op0[0]), float(op1[1] - op0[1])
            LP2 = dxP * dxP + dyP * dyP
            dxQ, dyQ = float(cp1[0] - cp0[0]), float(cp1[1] - cp0[1])
            if LP2 > 1e-12:
                A = (dxQ * dxP + dyQ * dyP) / LP2
                B = (dyQ * dxP - dxQ * dyP) / LP2
                for i in spec["interior"]:
                    xr = float(orig[i][0]) - op0[0]
                    yr = float(orig[i][1]) - op0[1]
                    gp[i] = [A * xr - B * yr + cp0[0], B * xr + A * yr + cp0[1]]
            else:
                for i in spec["interior"]:
                    gp[i] = [float(orig[i][0]) - op0[0] + cp0[0],
                             float(orig[i][1]) - op0[1] + cp0[1]]
            gp[i0] = list(cp0)
            gp[i1] = list(cp1)

    def _on_file_handle_dragged(self, handle_id, x, y, finished):
        session = self.active_session()
        if session is None or self._pending_file is None:
            return
        try:
            k = int(handle_id[1:])  # "c<idx>"
        except (ValueError, IndexError):
            return
        self._pending_geom_cur[k] = [x, y]
        self._refit_geom(session)
        self._redraw_file_geometry(session)
        # Mirror into the numeric dialog if this corner is one of its two.
        if self._pending_file_dialog is not None:
            ci0, ci1 = self._pending_file
            if k in (ci0, ci1):
                cur = self._pending_geom_cur
                self._pending_file_dialog.set_points(tuple(cur[ci0]), tuple(cur[ci1]))
        if finished:
            self._show_file_handles()

    def _on_file_dialog_changed(self, p0, p1):
        session = self.active_session()
        if session is None or self._pending_file is None:
            return
        ci0, ci1 = self._pending_file
        self._pending_geom_cur[ci0] = list(p0)
        self._pending_geom_cur[ci1] = list(p1)
        self._refit_geom(session)
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
        orig = self._pending_geom_orig
        self._clear_file_edit_state()
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
        self.main_window.log_panel.log("Updated geometry shape.")

    def _cancel_file_edit(self):
        session = self.active_session()
        orig = self._pending_geom_orig
        if session is not None and orig is not None:
            session.original_points = orig
        self._clear_file_edit_state()
        if session is not None:
            self._apply_geometry_update(session)
        self.main_window.log_panel.log("Shape edit cancelled (reverted).")

    def _clear_file_edit_state(self):
        self._pending_file = None
        self._pending_file_seg = None
        self._pending_file_dialog = None
        self._pending_geom_orig = None
        self._pending_geom_specs = None
        self._pending_geom_cur = None
        self._pending_geom_corners = None
        self.main_window.canvas_view.clear_edge_handles()
        self._refresh_endpoint_markers()
