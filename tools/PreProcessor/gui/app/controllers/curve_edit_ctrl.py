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
        # ``theta_m`` (freed arc radius-handle angle) has no sidebar widget, so it
        # is not carried by read/write_widget_params. Persist it straight onto the
        # segment; the UI→segment sync merges with .update() and preserves it.
        if ct == "arc" and "theta_m" in params:
            seg.parameters["theta_m"] = params["theta_m"]

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
