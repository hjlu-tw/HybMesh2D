from __future__ import annotations
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QMenu
from app.commands.segment_cmds import (
    AddCurveSegmentCmd, UpdateSegmentStateCmd)
from app.commands.vertex_cmds import ReplaceGeometryPointsCmd
from app.services.geometry_service import (
    format_vertices_str, project_point_to_segment)
from app.models import shape_spec


class CurveEditControllerMixin:
    """Mixin containing analytic-edge editing/manipulation: imported (discrete)
    edge endpoint editing, on-canvas control-point handles, commit/cancel of the
    modeless create-edit session, and the numeric (double-click) editors."""

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

    def _on_pending_dialog_changed(self, params, n_points):
        """The numeric dialog changed → update the pending edge, reposition the
        canvas control points, and refresh the preview (live, req 1)."""
        seg = self._pending_seg
        if seg is None:
            return
        seg.parameters.update(params)
        seg.parameters["n_points"] = n_points
        # #1: a polygon switched back to By Node Count no longer sends 'spacing';
        # clear any stale key so the backend uses the node count (mirrors the
        # sidebar's _sync_active_curve_segment_from_ui).
        if getattr(seg, "curve_type", "") == "polygon" and "spacing" not in params:
            seg.parameters.pop("spacing", None)
        # The polygon dialog's open/closed toggle lives outside `params`; mirror
        # it onto the segment so the live preview honours it immediately.
        dlg = self._pending_dialog
        if dlg is not None and hasattr(dlg, "is_closed") \
                and getattr(seg, "curve_type", "") == "polygon":
            seg.closed = dlg.is_closed()
        self._show_pending_handles()
        self._preview_pending()

    def _record_segment_state_edit(self, session, seg, old_state, refresh_cb=None):
        """Record an in-place edit of an existing segment so it is undoable.

        ``old_state`` is ``seg.to_dict()`` captured BEFORE the edit; the edit has
        already been applied in place, so the command is *recorded* (not executed)
        — which also clears the redo stack. Returns True if a command was pushed.
        """
        if seg is None or session is None or old_state is None:
            return False
        segs = session.project_model.segments
        try:
            idx = segs.index(seg)
        except ValueError:
            # The pending segment object was orphaned (e.g. an intervening
            # undo deep-copied the list). Fall back to a stable id match so the
            # edit is still recorded rather than silently dropped.
            idx = next((i for i, s in enumerate(segs) if s.id == seg.id), -1)
            if idx < 0:
                self.main_window.log_panel.log(
                    "Edit not recorded: the edge is no longer present.")
                return False
            seg = segs[idx]
        new_state = seg.to_dict()
        if new_state == old_state:
            return False
        if refresh_cb is None:
            refresh_cb = self._refresh_segment_list
        cmd = UpdateSegmentStateCmd(session, idx, old_state, new_state,
                                    refresh_cb=refresh_cb)
        session.command_history.record(cmd)
        return True

    def _commit_pending_edge(self):
        seg = self._pending_seg
        is_new = self._pending_is_new
        orig_state = self._pending_orig_state
        session = self.active_session()
        self._clear_pending_state()
        if seg is None or not session:
            return
        if is_new:
            cmd = AddCurveSegmentCmd(
                session,
                refresh_cb=self._refresh_segment_list,
                select_cb=self._select_segment_by_index,
                preconfigured_seg=seg,
            )
            session.command_history.execute(cmd)
            self.main_window.log_panel.log(f"Added {seg.curve_type} Edge {seg.id}.")
        else:
            # Editing an existing edge: params were mutated in place — record the
            # change (undoable) then redraw and reselect it.
            self._record_segment_state_edit(session, seg, orig_state)
            self._refresh_segment_list()
            try:
                self._select_segment_by_index(
                    session.project_model.segments.index(seg))
            except ValueError:
                pass
            self.main_window.log_panel.log(f"Updated {seg.curve_type} Edge {seg.id}.")
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, True)

    def _cancel_pending_edit(self):
        seg = self._pending_seg
        is_new = self._pending_is_new
        orig = self._pending_orig
        orig_state = self._pending_orig_state
        self._clear_pending_state()
        if (not is_new) and seg is not None and orig is not None:
            # Restore the edited edge's original shape (incl. the open/closed
            # flag the polygon dialog may have toggled).
            seg.parameters = orig
            if orig_state is not None and hasattr(seg, "closed"):
                seg.closed = bool(orig_state.get("closed", True))
            self._refresh_segment_list()
            self.main_window.log_panel.log("Edit cancelled (reverted).")
        else:
            self.main_window.log_panel.log("Add edge cancelled.")

    def _clear_pending_state(self):
        session = self.active_session()
        canvas = self.main_window.canvas_view
        self._pending_seg = None
        self._pending_dialog = None
        self._pending_is_new = True
        self._pending_orig = None
        self._pending_orig_state = None
        canvas.clear_edge_handles()
        if session is not None:
            canvas.clear_curve_preview(session.session_id)
        # Restore the always-on endpoint markers for the remaining edges.
        self._refresh_endpoint_markers()

    # ══════════════════════════════════════════════════════════════════════
    # Editable control-point handles for the selected analytic edge
    # ══════════════════════════════════════════════════════════════════════

    def _edge_control_points(self, seg):
        """Return [(handle_id, (x, y)), ...] control points for ``seg``'s shape,
        using its raw defining parameters (no anchoring/transform)."""
        return shape_spec.control_points(
            getattr(seg, "curve_type", "custom"), seg.parameters)

    def _refresh_edge_handles(self):
        """Show draggable vertex handles for the selected vertex-defined edge
        (polygon / triangle / quadrilateral) so it can be reshaped directly on
        the canvas; a drag routes through ``_on_edge_handle_dragged`` and writes
        the new coordinates back to the sidebar table (both stay in sync). Any
        other selection — or ``custom`` — shows none. Square markers keep the
        vertices visually distinct from the round transform pivot/base gizmo
        (the ambiguity that had these hidden before).

        Exception: while a create-edit session is active, its control points
        must be left untouched."""
        # This is the selection/refresh chokepoint, so it is also where a
        # committed-edge drag's pre-drag snapshot is retired: clearing it here
        # guarantees a stale snapshot from a drag that ended abnormally (its
        # finished-event guard tripped, or selection changed mid-drag) can never
        # leak into the NEXT drag and record an undo against the wrong segment.
        self._drag_orig_state = None
        if self._edit_in_progress():
            return
        canvas = self.main_window.canvas_view
        session = self.active_session()
        seg = (session.project_model.get_segment(session.current_segment_idx)
               if session and session.current_segment_idx >= 0 else None)
        editable = ("polygon", "triangle", "quadrilateral", "arc")
        if (seg is None or seg.type != "curve"
                or getattr(seg, "curve_type", "custom") not in editable):
            canvas.clear_edge_handles()
            return
        cps = self._edge_control_points(seg)
        # A hand-authored polygon has a handful of vertices; a baked/imported one
        # can have hundreds — that many draggable markers is cluttered and slow,
        # and such shapes are reshaped through the sidebar table instead.
        if not cps or len(cps) > 60:
            canvas.clear_edge_handles()
            return
        canvas.show_edge_handles(
            [{"id": hid, "pos": pos, "symbol": "s", "size": 12}
             for hid, pos in cps])

    def _on_edge_handle_dragged(self, handle_id: str, x: float, y: float,
                                finished: bool):
        """Live-update the shape from a dragged control point on the canvas."""
        # Route to whichever edit session owns the handles.
        if self._pending_file is not None:
            self._on_file_handle_dragged(handle_id, x, y, finished)
            return
        if self._pending_seg is not None:
            self._on_pending_handle_dragged(handle_id, x, y, finished)
            return
        if self._is_populating:
            return
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve":
            return
        sb = self.main_window.sidebar_view
        ct = seg.curve_type
        if ct not in shape_spec.SIDEBAR_ATTRS and ct != "polygon":
            return
        # Snapshot the pre-drag state once so the whole drag (many move events)
        # collapses into a single undo step; this branch fires only for an
        # already-committed edge (a create-edit session is routed off above).
        if self._drag_orig_state is None:
            self._drag_orig_state = seg.to_dict()
        # Apply the drag through the shared handle→param mapping, then push the
        # result back into the (silently-updated) sidebar widgets.
        params = shape_spec.read_widget_params(sb, ct)
        lock = (ct == "arc" and getattr(sb, "arc_lock_radius", None) is not None
                and sb.arc_lock_radius.isChecked())
        shape_spec.apply_drag(ct, params, handle_id, x, y, lock_radius=lock)
        shape_spec.write_widget_params(sb, ct, params, silent=True)

        # Sync the (silently-updated) widgets into the segment and re-preview.
        self.preview_curve_formula()
        if finished:
            old_state = self._drag_orig_state
            self._drag_orig_state = None
            # Record the completed move as one undoable edit + re-snap the handles
            # (e.g. circle rim onto the new radius ring); no-op if unchanged.
            self._finalize_edge_edit(session, seg, old_state)

    # ══════════════════════════════════════════════════════════════════════
    # Numeric (double-click) editor — the "Both" precise-entry path
    # ══════════════════════════════════════════════════════════════════════

    def handle_canvas_segment_double_clicked(self, x: float, y: float):
        """Double-click on the canvas: select the nearest edge and, if it is an
        analytic shape, open its numeric parameter dialog."""
        if self._edit_in_progress():
            return
        self.handle_canvas_segment_clicked(x, y, extend_selection=False)
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return
        if seg.type == "file":
            # Imported discrete edge → edit its endpoints.
            self._begin_file_edit(seg)
            return
        if seg.type != "curve":
            return
        if seg.curve_type == "custom":
            self._edit_custom_formula(seg)
        else:
            # Re-open the same interactive edit session (control points +
            # modeless dialog + snapping) on the existing edge. Polygon/polyline
            # included: its dialog shows the vertex table plus an open/closed
            # toggle, alongside the on-canvas vertex handles.
            self._begin_pending_edit(seg, is_new=False)

    # ── Polygon on-canvas vertex insert / delete (right-click) ─────────────
    def handle_canvas_context_menu(self, x: float, y: float):
        """Right-click over the selected polygon → insert a vertex on the nearest
        edge or delete the nearest vertex. Both are undoable and sync the sidebar
        vertex table. No-op unless the selected edge is a polygon."""
        if self._edit_in_progress():
            return
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve" or seg.curve_type != "polygon":
            return
        sb = self.main_window.sidebar_view
        params = shape_spec.read_widget_params(sb, "polygon")
        verts = [(float(vx), float(vy))
                 for _, (vx, vy) in shape_spec.control_points("polygon", params)]
        if len(verts) < 3:
            return
        closed = bool(getattr(seg, "closed", True))
        click = np.array([x, y], dtype=float)
        vi = min(range(len(verts)),
                 key=lambda i: (verts[i][0] - x) ** 2 + (verts[i][1] - y) ** 2)
        edge_i, proj = self._nearest_polygon_edge(verts, click, closed)

        menu = QMenu(self.main_window)
        act_ins = menu.addAction("Insert vertex here")
        act_ins.setEnabled(edge_i is not None)
        act_del = menu.addAction("Delete nearest vertex")
        # A polygon needs at least 3 vertices.
        act_del.setEnabled(len(verts) > 3)
        chosen = menu.exec(QCursor.pos())
        if chosen is None:
            return
        if chosen is act_ins and edge_i is not None:
            new_verts = (verts[:edge_i + 1] + [(float(proj[0]), float(proj[1]))]
                         + verts[edge_i + 1:])
        elif chosen is act_del and len(verts) > 3:
            new_verts = verts[:vi] + verts[vi + 1:]
        else:
            return
        self._commit_polygon_vertices(session, seg, sb, new_verts)

    def _nearest_polygon_edge(self, verts, click, closed):
        """(edge_start_index, projected_point) for the polygon edge nearest to
        ``click`` — projection clamped to the segment; the closing edge is
        considered only when ``closed``. Returns (None, click) if no edge."""
        n = len(verts)
        edges = list(range(n - 1)) + ([n - 1] if closed and n >= 3 else [])
        best_i, best_d, best_p = None, float("inf"), click
        for i in edges:
            proj, _ = project_point_to_segment(click, verts[i], verts[(i + 1) % n])
            d = float(np.hypot(*(click - proj)))
            if d < best_d:
                best_i, best_d, best_p = i, d, proj
        return best_i, best_p

    def _commit_polygon_vertices(self, session, seg, sb, new_verts):
        """Apply a new polygon vertex list: push it to the sidebar table, sync it
        into the segment + re-preview, re-show the on-canvas handles, and record
        the change as one undo step."""
        old_state = seg.to_dict()
        shape_spec.write_widget_params(
            sb, "polygon", {"vertices_str": format_vertices_str(new_verts)},
            silent=True)
        # preview_curve_formula() reads the sidebar back into seg.parameters and
        # redraws; recording afterwards captures the applied change as undoable.
        self.preview_curve_formula()
        self._finalize_edge_edit(session, seg, old_state)

    def _finalize_edge_edit(self, session, seg, old_state):
        """Record a completed in-place edge edit (drag / vertex insert-delete) as
        one undo step, flag the session modified, and re-snap the canvas handles.
        No-op recording if ``old_state`` is None or the shape is unchanged."""
        self._record_segment_state_edit(session, seg, old_state)
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, True)
        self._refresh_edge_handles()

    def _edit_custom_formula(self, seg):
        """Reopen the custom-formula dialog (pre-filled) to edit an existing
        custom edge."""
        session = self.active_session()
        if not session:
            return
        from app.views.shape_dialog import CustomFormulaDialog
        dlg = CustomFormulaDialog(self.main_window, seg=seg)
        from app.utils import offset_popup
        offset_popup(dlg, self.main_window)
        if not dlg.exec():
            return
        cfg = dlg.result_config()
        old_state = seg.to_dict()
        seg.curve_mode = cfg["mode"]
        seg.x_formula = cfg["x_formula"]
        seg.y_formula = cfg["y_formula"]
        seg.formula = cfg["formula"]
        seg.t_min = cfg["t_min"]
        seg.t_max = cfg["t_max"]
        seg.parameters["n_points"] = cfg["n_points"]
        self._record_segment_state_edit(session, seg, old_state)
        self._is_populating = True
        try:
            self.main_window.sidebar_view.show_curve_segment(seg)
        finally:
            self._is_populating = False
        self.preview_curve_formula()
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, True)
        self.main_window.log_panel.log(f"Edited Custom Formula Edge {seg.id}.")

    def open_edge_param_dialog(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve" or seg.curve_type == "custom":
            return
        from app.views.shape_dialog import ShapeParamDialog
        dlg = ShapeParamDialog(seg, self.main_window)
        from app.utils import offset_popup
        offset_popup(dlg, self.main_window)
        if dlg.exec():
            updates, n_points = dlg.result_params()
            old_state = seg.to_dict()
            seg.parameters.update(updates)
            seg.parameters["n_points"] = n_points
            if getattr(seg, "curve_type", "") == "polygon" \
                    and hasattr(dlg, "is_closed"):
                seg.closed = dlg.is_closed()
            self._record_segment_state_edit(session, seg, old_state)
            # Reflect the new values in the sidebar then re-preview.
            self._is_populating = True
            try:
                self.main_window.sidebar_view.show_curve_segment(seg)
            finally:
                self._is_populating = False
            self.preview_curve_formula()
            self._refresh_edge_handles()
            session.is_geometry_modified = True
            self.main_window.update_title(session.display_name, True)
            self.main_window.log_panel.log(f"Edited Edge {seg.id}.")
