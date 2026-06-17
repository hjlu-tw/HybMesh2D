from __future__ import annotations
import math
import numpy as np
from app.models.segment import SegmentModel
from app.models.session import GeometrySession
from app.commands.segment_cmds import DuplicateMultipleTransformCmd
from app.services.geometry_service import GeometryService, _parse_vertices_str

class TransformControllerMixin:
    """Mixin containing geometric transform, duplication, and mirroring logic."""

    def duplicate_with_transform(self):
        """Apply the selected geometric transform to every selected edge.

        The transform is type-preserving (like industrial CAD): a line stays a
        line, a circle stays a circle, polygons/triangles/quads keep their type
        — only their defining parameters are transformed. Discrete (file) edges
        and custom-formula curves, which have no closed-form image under the
        transform, fall back to a Polygon of the transformed sample points.
        Operates on all edges selected in the model tree; originals are kept
        unless 'Delete original' is set."""
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No segment selected.")
            return
        sb = self.main_window.sidebar_view

        indices = self.get_selected_segment_indices()
        if not indices:
            self.main_window.log_panel.log("No segment selected.")
            return

        # A zero-length custom mirror axis is the only fully-degenerate case;
        # reject it once up front so a per-edge None can mean "no valid points".
        if sb.dup_type_combo.currentIndex() == 3:
            if math.hypot(sb.dup_ma_dx.value(), sb.dup_ma_dy.value()) < 1e-12:
                self.main_window.log_panel.log(
                    "Mirror axis direction is zero — cannot mirror.")
                return

        delete_original = sb.dup_delete_orig_cb.isChecked()

        new_segs = []
        seg_indices = []
        new_ids = []
        next_id = session.project_model._next_curve_id

        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if not seg:
                continue

            # Only the active curve segment carries unsaved UI edits.
            if seg.type == "curve" and idx == session.current_segment_idx:
                self._sync_active_curve_segment_from_ui()

            new_seg = self._build_transformed_segment(session, seg, next_id)
            if new_seg is None:
                self.main_window.log_panel.log(
                    f"Edge {seg.id} has no valid points — skipped.")
                continue

            new_segs.append(new_seg)
            seg_indices.append(idx)
            new_ids.append(new_seg.id)
            next_id += 1

        if not new_segs:
            self.main_window.log_panel.log("No valid edges to transform.")
            return

        def select_cb(idx):
            self._select_segment_by_index(idx)

        # When the originals are deleted, point data changes, so redraw the
        # base geometry (via _apply_geometry_update) — otherwise the moved
        # edge's old vertices linger on the canvas as a stale, unselectable
        # ghost. A plain duplicate leaves points untouched, so the lighter
        # list refresh suffices. (Both run on undo too.)
        refresh_cb = ((lambda: self._apply_geometry_update(session))
                      if delete_original else self._refresh_segment_list)
        cmd = DuplicateMultipleTransformCmd(
            session=session,
            seg_indices=seg_indices,
            new_segs=new_segs,
            delete_original=delete_original,
            refresh_cb=refresh_cb,
            select_cb=select_cb,
        )
        session.command_history.execute(cmd)
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, True)

        action_name = "Moved/Transformed" if delete_original else "Duplicated"
        ids_str = ", ".join(str(i) for i in new_ids)
        self.main_window.log_panel.log(
            f"{action_name} {len(new_segs)} edge(s) as Edge {ids_str} "
            f"({sb.dup_type_combo.currentText()}).")
        self._show_duplicate_preview = False
        self.main_window.canvas_view.clear_duplicate_preview()
        self.main_window.canvas_view.clear_transform_handles()

    def _build_transformed_segment(self, session, seg, new_id):
        """Build a new curve segment that is `seg` after the active transform,
        preserving the analytic type where the (similarity) transform allows it.

        Returns None when the edge has no usable points. The mirror-axis
        degenerate case is rejected by the caller before this is reached."""
        def T(pts):
            """Transform a short list of defining points; None if degenerate."""
            xs = np.array([p[0] for p in pts], dtype=float)
            ys = np.array([p[1] for p in pts], dtype=float)
            res = self._apply_transform(xs, ys)
            if res is None:
                return None
            txs, tys = res
            return [(float(x), float(y)) for x, y in zip(txs, tys)]

        new_seg = SegmentModel(new_id, -1, -1)
        new_seg.type = "curve"
        # Carry the source edge's resampling strategy and spacing params so a
        # moved/duplicated edge keeps its feel instead of resetting to uniform.
        new_seg.strategy = seg.strategy
        new_seg.parameters = dict(seg.parameters)
        new_seg.start_index = -1
        new_seg.end_index = -1

        ct = getattr(seg, "curve_type", "custom")
        p = seg.parameters

        # ── Lines (incl. axis-aligned, re-classified after the transform) ────
        if seg.type == "curve" and ct in ("line", "horizontal_line", "vertical_line"):
            if ct == "horizontal_line":
                ends = [(p.get("x0", 0.0), p.get("y", 0.0)),
                        (p.get("x1", 1.0), p.get("y", 0.0))]
            elif ct == "vertical_line":
                ends = [(p.get("x", 0.0), p.get("y0", 0.0)),
                        (p.get("x", 0.0), p.get("y1", 1.0))]
            else:
                ends = [(p.get("x0", 0.0), p.get("y0", 0.0)),
                        (p.get("x1", 1.0), p.get("y1", 1.0))]
            t = T(ends)
            if t is None:
                return None
            (ax, ay), (bx, by) = t
            tol = 1e-9 * max(1.0, abs(ax) + abs(ay) + abs(bx) + abs(by))
            for k in ("x", "y", "x0", "y0", "x1", "y1"):
                new_seg.parameters.pop(k, None)
            if abs(ay - by) <= tol:          # stayed horizontal
                new_seg.curve_type = "horizontal_line"
                new_seg.parameters.update({"y": ay, "x0": ax, "x1": bx})
            elif abs(ax - bx) <= tol:        # became vertical
                new_seg.curve_type = "vertical_line"
                new_seg.parameters.update({"x": ax, "y0": ay, "y1": by})
            else:                            # general line
                new_seg.curve_type = "line"
                new_seg.parameters.update({"x0": ax, "y0": ay, "x1": bx, "y1": by})
            return new_seg

        # ── Circle (similarity transforms keep it circular) ──────────────────
        if seg.type == "curve" and ct == "circle":
            cx, cy, r = p.get("cx", 0.0), p.get("cy", 0.0), p.get("r", 1.0)
            # Transform the centre and a rim point; |Δ| recovers the new radius
            # (handles rotation/mirror = unchanged, uniform scale = r·factor).
            t = T([(cx, cy), (cx + r, cy)])
            if t is None:
                return None
            (ncx, ncy), (ex, ey) = t
            new_seg.curve_type = "circle"
            new_seg.parameters.update(
                {"cx": ncx, "cy": ncy, "r": math.hypot(ex - ncx, ey - ncy)})
            return new_seg

        # ── Triangle / Quadrilateral / Polygon (transform the vertices) ──────
        if seg.type == "curve" and ct in ("triangle", "quadrilateral", "polygon"):
            if ct == "triangle":
                src = [(p.get("x0", 0.0), p.get("y0", 0.0)),
                       (p.get("x1", 1.0), p.get("y1", 0.0)),
                       (p.get("x2", 0.5), p.get("y2", 1.0))]
            elif ct == "quadrilateral":
                src = [(p.get(f"x{i}", 0.0), p.get(f"y{i}", 0.0)) for i in range(4)]
            else:
                src = [(float(x), float(y))
                       for x, y in _parse_vertices_str(p.get("vertices_str", ""))]
            t = T(src)
            if t is None:
                return None
            new_seg.curve_type = ct
            if ct in ("triangle", "quadrilateral"):
                for i, (x, y) in enumerate(t):
                    new_seg.parameters[f"x{i}"] = x
                    new_seg.parameters[f"y{i}"] = y
            else:
                new_seg.parameters["vertices_str"] = ";".join(
                    f"{x:.6g},{y:.6g}" for x, y in t)
            return new_seg

        # ── Fallback: discrete (file) edges and custom-formula curves ────────
        # No closed-form image under the transform → bake the transformed sample
        # points into a Polygon (the industrial 'explode' equivalent).
        pts_tuple = GeometryService.get_segment_points(session, seg)
        if pts_tuple is None:
            return None
        xs, ys = pts_tuple
        res = self._apply_transform(np.asarray(xs, dtype=float),
                                    np.asarray(ys, dtype=float))
        if res is None:
            return None
        txs, tys = res
        new_seg.curve_type = "polygon"
        new_seg.parameters["vertices_str"] = ";".join(
            f"{x:.6g},{y:.6g}" for x, y in zip(txs, tys))
        new_seg.parameters["n_points"] = len(txs)
        return new_seg

    def _apply_transform(self, xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
        """Apply the selected geometric transform to the points xs and ys."""
        sb = self.main_window.sidebar_view
        t_idx = sb.dup_type_combo.currentIndex()
        xs = xs.copy()
        ys = ys.copy()

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
                return None
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

        return xs, ys


    def _open_transform(self):
        """Open the Duplicate & Transform window and immediately show the base
        point / mirror-axis gizmo and the live result preview on the canvas."""
        self.main_window.sidebar_view.open_transform_dialog()
        self._show_duplicate_preview = True
        self.update_duplicate_base_point()
        self.update_duplicate_preview()
        self._refresh_transform_handles()

    def _close_transform(self):
        """The Duplicate & Transform window was closed → clear its gizmo/preview."""
        self._show_duplicate_preview = False
        self.main_window.canvas_view.clear_duplicate_preview()
        self.main_window.canvas_view.clear_transform_handles()
        # Restore the selected analytic edge's control handles, if any.
        self._refresh_edge_handles()

    def handle_dup_interactive_toggled(self, checked: bool):
        """Explicit entry point for interactive placement: show (or hide) the
        draggable base point / axis handle together with the live result
        preview on the canvas."""
        if self._is_populating:
            return
        self._show_duplicate_preview = checked
        if checked:
            self.update_duplicate_base_point()
        self.update_duplicate_preview()
        self._refresh_transform_handles()

    def handle_dup_type_changed(self):
        if self._is_populating:
            return
        self._show_duplicate_preview = True
        self.update_duplicate_base_point()
        self.update_duplicate_preview()
        self._refresh_transform_handles()

    def handle_dup_base_mode_changed(self):
        if self._is_populating:
            return
        self._show_duplicate_preview = True
        self.update_duplicate_base_point()
        self.update_duplicate_preview()
        self._refresh_transform_handles()

    def on_duplicate_param_changed(self):
        if self._is_populating:
            return
        self._show_duplicate_preview = True
        self.update_duplicate_preview()
        self._refresh_transform_handles()

    def update_duplicate_base_point(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return

        sb = self.main_window.sidebar_view
        t_idx = sb.dup_type_combo.currentIndex()
        if t_idx == 5: # Translate — no reference point
            sb.dup_base_mode_combo.setEnabled(False)
            sb.dup_trans_dx.setEnabled(True)
            sb.dup_trans_dy.setEnabled(True)
            return

        sb.dup_base_mode_combo.setEnabled(True)
        mode = sb.dup_base_mode_combo.currentText()

        # Pivot / axis spin boxes are user-editable only in Custom mode; for
        # every other mode they are driven by the computed reference point and
        # shown read-only. (Mirror-axis direction fields are always editable.)
        pivot_fields = [
            sb.dup_rot_px, sb.dup_rot_py, sb.dup_mh_py, sb.dup_mv_px,
            sb.dup_ma_px, sb.dup_ma_py, sb.dup_ps_px, sb.dup_ps_py,
            sb.dup_scale_px, sb.dup_scale_py,
        ]
        manual = (mode == "Custom (Manual)")
        for w in pivot_fields:
            w.setEnabled(manual)
        if manual:
            return

        pt = self._compute_dup_reference_point(session, mode)
        if pt is None:
            return
        px, py = pt

        for w in pivot_fields:
            w.blockSignals(True)
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
        for w in pivot_fields:
            w.blockSignals(False)

    def _compute_dup_reference_point(self, session, mode):
        """Return (px, py) for the duplicate/transform reference point.

        "Center (selection)" uses the bounding-box centre of every selected
        edge so a multi-edge Rotate/Scale pivots about the group instead of
        flying off around the origin; "Start/End Point" use the active edge's
        first/last point.
        """
        if mode == "Center (selection)":
            xs_parts, ys_parts = [], []
            for idx in self.get_selected_segment_indices():
                s = session.project_model.get_segment(idx)
                if not s:
                    continue
                pts = GeometryService.get_segment_points(session, s)
                if pts is None or len(pts[0]) == 0:
                    continue
                xs_parts.append(np.asarray(pts[0]))
                ys_parts.append(np.asarray(pts[1]))
            if not xs_parts:
                return None
            xs = np.concatenate(xs_parts)
            ys = np.concatenate(ys_parts)
            return (0.5 * (float(xs.min()) + float(xs.max())),
                    0.5 * (float(ys.min()) + float(ys.max())))

        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return None
        pts = GeometryService.get_segment_points(session, seg)
        if pts is None or len(pts[0]) == 0:
            return None
        xs, ys = pts
        if mode == "Start Point":
            return (float(xs[0]), float(ys[0]))
        return (float(xs[-1]), float(ys[-1]))

    # ── Draggable canvas handle for the base point / mirror axis ──────────

    def _refresh_transform_handles(self):
        """Show (or update) the draggable base-point / axis handle on the
        canvas to match the active transform, or hide it when not applicable."""
        sb = self.main_window.sidebar_view
        canvas = self.main_window.canvas_view
        session = self.active_session()

        has_sel = bool(session) and session.current_segment_idx >= 0
        on = has_sel and bool(self._show_duplicate_preview)

        # Keep the "Edit on Canvas" toggle in sync with the interactive state.
        btn = getattr(sb, 'dup_interactive_btn', None)
        if btn is not None:
            btn.blockSignals(True)
            btn.setChecked(on)
            btn.setText("✎  Editing on Canvas" if on else "✎  Edit on Canvas")
            btn.blockSignals(False)

        # Only show handles while the user is actively setting up a transform
        # (a live preview is active). On a fresh selection or right after Apply
        # there is no preview, so the canvas stays clean and fully clickable
        # instead of being covered by a draggable marker / mirror axis line.
        if not on:
            canvas.clear_transform_handles()
            # No transform preview → restore the selected edge's control points.
            self._refresh_edge_handles()
            return

        # Transform gizmo and edge control points must not overlap on canvas.
        canvas.clear_edge_handles()

        t_idx = sb.dup_type_combo.currentIndex()
        if t_idx == 0:    # Rotate — pivot + draggable angle handle
            canvas.show_transform_handles({'rotate': {
                'pivot': (sb.dup_rot_px.value(), sb.dup_rot_py.value()),
                'angle': sb.dup_rot_angle.value()}})
        elif t_idx == 1:  # Mirror Horizontal — horizontal axis line
            canvas.show_transform_handles({'hline': sb.dup_mh_py.value()})
        elif t_idx == 2:  # Mirror Vertical — vertical axis line
            canvas.show_transform_handles({'vline': sb.dup_mv_px.value()})
        elif t_idx == 3:  # Mirror Axis — pivot + direction
            canvas.show_transform_handles({'axis': {
                'pivot': (sb.dup_ma_px.value(), sb.dup_ma_py.value()),
                'dir': (sb.dup_ma_dx.value(), sb.dup_ma_dy.value())}})
        elif t_idx == 4:  # Point Symmetry — centre point
            canvas.show_transform_handles(
                {'point': (sb.dup_ps_px.value(), sb.dup_ps_py.value())})
        elif t_idx == 6:  # Scale — pivot point
            canvas.show_transform_handles(
                {'point': (sb.dup_scale_px.value(), sb.dup_scale_py.value())})
        elif t_idx == 5:  # Translate — drag the selection centre to a destination
            anchor = self._compute_dup_reference_point(session, "Center (selection)")
            if anchor is None:
                canvas.clear_transform_handles()
                return
            ax, ay = anchor
            canvas.show_transform_handles({'translate': {
                'anchor': (ax, ay),
                'dest': (ax + sb.dup_trans_dx.value(),
                         ay + sb.dup_trans_dy.value())}})
        else:
            canvas.clear_transform_handles()

    @staticmethod
    def _spin_set_silent(spin, value):
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)

    def _force_base_mode_custom(self):
        """A manual drag means the user wants a custom reference point: switch
        Base Point to Custom (so the dragged value is kept and editable)."""
        sb = self.main_window.sidebar_view
        if sb.dup_base_mode_combo.currentText() != "Custom (Manual)":
            sb.dup_base_mode_combo.blockSignals(True)
            sb.dup_base_mode_combo.setCurrentText("Custom (Manual)")
            sb.dup_base_mode_combo.blockSignals(False)
        for w in (sb.dup_rot_px, sb.dup_rot_py, sb.dup_mh_py, sb.dup_mv_px,
                  sb.dup_ma_px, sb.dup_ma_py, sb.dup_ps_px, sb.dup_ps_py,
                  sb.dup_scale_px, sb.dup_scale_py):
            w.setEnabled(True)

    def _on_transform_handle_dragged(self, kind: str, x: float, y: float):
        """Live-update the relevant spin box(es) and ghost preview as the user
        drags the base-point / axis handle on the canvas."""
        if self._is_populating:
            return
        sb = self.main_window.sidebar_view
        t_idx = sb.dup_type_combo.currentIndex()

        if kind == 'translate':
            # Destination of the selection centre → derive the shift vector.
            anchor = self._compute_dup_reference_point(
                self.active_session(), "Center (selection)")
            if anchor is not None:
                self._spin_set_silent(sb.dup_trans_dx, x - anchor[0])
                self._spin_set_silent(sb.dup_trans_dy, y - anchor[1])
            self._show_duplicate_preview = True
            self.update_duplicate_preview()
            return

        if kind == 'rotate_angle':
            # The rotate gizmo reports the absolute clock-hand angle (deg) in x.
            self._spin_set_silent(sb.dup_rot_angle, x)
            self._show_duplicate_preview = True
            self.update_duplicate_preview()
            return

        # All other handles act on a base point → imply a custom reference.
        self._force_base_mode_custom()

        if kind == 'point':
            if t_idx == 0:
                self._spin_set_silent(sb.dup_rot_px, x)
                self._spin_set_silent(sb.dup_rot_py, y)
            elif t_idx == 4:
                self._spin_set_silent(sb.dup_ps_px, x)
                self._spin_set_silent(sb.dup_ps_py, y)
            elif t_idx == 6:
                self._spin_set_silent(sb.dup_scale_px, x)
                self._spin_set_silent(sb.dup_scale_py, y)
        elif kind == 'hline':
            self._spin_set_silent(sb.dup_mh_py, y)
        elif kind == 'vline':
            self._spin_set_silent(sb.dup_mv_px, x)
        elif kind == 'axis_pivot':
            self._spin_set_silent(sb.dup_ma_px, x)
            self._spin_set_silent(sb.dup_ma_py, y)
        elif kind == 'axis_dir':
            self._spin_set_silent(sb.dup_ma_dx, x)
            self._spin_set_silent(sb.dup_ma_dy, y)

        self._show_duplicate_preview = True
        self.update_duplicate_preview()

    def update_duplicate_preview(self):
        if not self._show_duplicate_preview:
            self.main_window.canvas_view.clear_duplicate_preview()
            return

        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            self.main_window.canvas_view.clear_duplicate_preview()
            return

        # Preview every selected edge so it matches the multi-edge apply.
        # (Gated on selection + the interactive flag above — the ghost lives on
        # the geometry canvas and is simply not visible on other pages.)
        indices = self.get_selected_segment_indices()
        if not indices:
            self.main_window.canvas_view.clear_duplicate_preview()
            return

        pieces = []
        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if not seg:
                continue
            pts_tuple = GeometryService.get_segment_points(session, seg)
            if pts_tuple is None or len(pts_tuple[0]) < 2:
                continue
            xs, ys = pts_tuple
            transformed = self._apply_transform(xs, ys)
            if transformed is None:
                self.main_window.canvas_view.clear_duplicate_preview()
                return
            txs, tys = transformed
            pieces.append(np.column_stack([txs, tys]))

        if not pieces:
            self.main_window.canvas_view.clear_duplicate_preview()
            return

        if len(pieces) == 1:
            pts_new = pieces[0]
        else:
            # Separate disconnected pieces with a NaN gap (connect='finite').
            sep = np.full((1, 2), np.nan)
            parts = []
            for k, p in enumerate(pieces):
                if k > 0:
                    parts.append(sep)
                parts.append(p)
            pts_new = np.vstack(parts)

        self.main_window.canvas_view.update_duplicate_preview(pts_new)
