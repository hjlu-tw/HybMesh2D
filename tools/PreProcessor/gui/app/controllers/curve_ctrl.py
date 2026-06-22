from __future__ import annotations
import math
import numpy as np
from PyQt6.QtCore import Qt
from app.models.segment import SegmentModel
from app.models.session import GeometrySession
from app.commands.segment_cmds import AddCurveSegmentCmd, BakeCurveToGeometryCmd
from app.services.geometry_service import GeometryService
from app.models import shape_spec

# Curve-type list, indexed by the type combo's row order.
CURVE_TYPES = ["custom", "horizontal_line", "vertical_line", "line",
               "circle", "triangle", "quadrilateral", "polygon"]


class CurveControllerMixin:
    """Mixin containing analytic curve management, previewing, and baking logic."""

    def add_curve_segment(self):
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No geometry session active.")
            return
        cmd = AddCurveSegmentCmd(
            session,
            refresh_cb=self._refresh_segment_list,
            select_cb=self._select_segment_by_index
        )
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Added Analytic Edge {cmd.added_seg.id}.")

    def bake_selected_curve(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve":
            return
        
        n = seg.parameters.get("n_points", 100)
        xs, ys = GeometryService.compute_curve_preview_pts(seg, n, session.original_points)
        if xs is None or len(xs) < 2:
            self.main_window.log_panel.log("Cannot convert curve: invalid preview points.")
            return

        cmd = BakeCurveToGeometryCmd(session, session.current_segment_idx, self._refresh_segment_list)
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(f"Converted Edge {cmd.seg_id} to Discrete.")
        self.main_window.canvas_view.clear_curve_preview(session.session_id)
        self._apply_geometry_update(session)
        self._update_canvas_curve_segments()

    def _sync_active_curve_segment_from_ui(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve":
            return
        
        sb = self.main_window.sidebar_view
        idx = sb.curve_type_combo.currentIndex()
        if 0 <= idx < len(CURVE_TYPES):
            seg.curve_type = CURVE_TYPES[idx]
        else:
            seg.curve_type = "custom"

        seg.curve_mode = "parametric" if sb.curve_mode_param.isChecked() else "explicit"
        seg.x_formula = sb.curve_x_formula.text()
        seg.y_formula = sb.curve_y_formula.text()
        seg.formula = sb.curve_formula.text()
        seg.t_min = sb.curve_t_min.value()
        seg.t_max = sb.curve_t_max.value()
        seg.parameters["n_points"] = sb.curve_n.value()
        seg.start_index = sb.curve_start_node.value()
        seg.end_index = sb.curve_end_node.value()

        # Sync shape-defining parameters from the sidebar widgets (one source of
        # the per-type widget↔param mapping lives in shape_spec).
        if seg.curve_type in shape_spec.SIDEBAR_ATTRS or seg.curve_type == "polygon":
            seg.parameters.update(shape_spec.read_widget_params(sb, seg.curve_type))

    def handle_curve_type_changed(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve":
            return

        # If the user actually switched the shape type, reset that type's
        # parameters to clean defaults so the shared shape widgets do not carry
        # over stale values (e.g. a vertices_str left from a transformed polygon
        # — the cause of the "polygon default = last transform residual" bug).
        sb = self.main_window.sidebar_view
        idx = sb.curve_type_combo.currentIndex()
        new_type = CURVE_TYPES[idx] if 0 <= idx < len(CURVE_TYPES) else "custom"
        if new_type != seg.curve_type and not self._is_populating:
            seg.curve_type = new_type
            if new_type in shape_spec.DEFAULTS:
                for k in shape_spec.ALL_SHAPE_KEYS:
                    seg.parameters.pop(k, None)
                seg.parameters.update(shape_spec.DEFAULTS[new_type])
            # Push the fresh defaults into the shape widgets before syncing back.
            self._is_populating = True
            try:
                sb.show_curve_segment(seg)
            finally:
                self._is_populating = False

        self._sync_active_curve_segment_from_ui()
        # Update the edge row's label in the model tree
        sb = self.main_window.sidebar_view
        seg_idx = session.current_segment_idx
        item = sb.geometry_tree.edge_item_by_index(session.session_id, seg_idx)
        if item is not None:
            c_type = seg.curve_type
            from app.utils import CURVE_TYPE_LABELS
            lbl_val = CURVE_TYPE_LABELS.get(c_type, c_type.capitalize())
            c_label = lbl_val(seg) if callable(lbl_val) else lbl_val
            item.setText(0, f"Edge {seg.id}: {c_label}")
        self.preview_curve_formula()
        self._refresh_edge_handles()

    def preview_curve_formula(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        if self._is_populating:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve":
            return

        self._sync_active_curve_segment_from_ui()
        n = seg.parameters.get("n_points", 100)
        xs, ys = GeometryService.compute_curve_preview_pts(seg, n, session.original_points)
        if xs is not None and ys is not None and len(xs) > 0:
            self.main_window.canvas_view.update_curve_preview(
                session.session_id, np.column_stack([xs, ys]))
        else:
            self.main_window.canvas_view.clear_curve_preview(session.session_id)

    def _update_canvas_curve_segments(self):
        session = self.active_session()
        if not session:
            return

        segments_pts = []
        for idx, seg in enumerate(session.project_model.segments):
            if seg.type == "curve" and idx != session.current_segment_idx:
                n = seg.parameters.get("n_points", 100)
                try:
                    xs, ys = GeometryService.compute_curve_preview_pts(seg, n, session.original_points)
                    if xs is not None and ys is not None and len(xs) > 0:
                        segments_pts.append(np.column_stack([xs, ys]))
                except Exception:
                    pass
        self.main_window.canvas_view.update_curve_segments(session.session_id, segments_pts)
        # Keep the always-on endpoint markers in sync with the current edges.
        self._refresh_endpoint_markers()

    def _refresh_endpoint_markers(self):
        """Always show a clear marker at every edge's endpoints for the active
        session (so endpoints are visible at all times, not just while editing).
        During a create-edit session the pending flow manages the markers."""
        if self._edit_in_progress():
            return
        session = self.active_session()
        canvas = self.main_window.canvas_view
        if not session:
            canvas.clear_endpoint_markers()
            return
        canvas.show_endpoint_markers(self._snap_targets(session))

    # ══════════════════════════════════════════════════════════════════════
    # Interactive shape creation (tool → draw on canvas → add edge)
    # ══════════════════════════════════════════════════════════════════════

    def enter_shape_tool(self, tool: str):
        """Start a shape tool. ``tool`` is one of
        'line'|'circle'|'rectangle'|'triangle'|'polygon'|'custom'.

        For 'custom' the formula dialog opens straight away (with a live canvas
        preview).  For the geometric shapes the canvas enters interactive
        click-to-place mode — each placed point shows a draggable control point
        and a live preview — and once the shape is complete the numeric dialog
        opens automatically, pre-filled with the drawn values."""
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No geometry session active.")
            return
        if tool == "custom":
            self.open_custom_formula_dialog()
            return
        canvas = self.main_window.canvas_view
        canvas.clear_edge_handles()
        canvas.clear_transform_handles()
        self._show_duplicate_preview = False
        canvas.start_draw_mode(tool)
        self.main_window.log_panel.log(
            f"Add {tool}: click on the canvas to place points; drag a point to "
            f"adjust (right-click to cancel).")

    def on_shape_drawn(self, tool: str, pts: list):
        """The interactive drawing is complete — start a modeless edit session:
        editable control points stay on the canvas (draggable) AND a non-modal
        numeric dialog opens, both bound live to the same pending edge.  The edge
        is only created when the user presses 'Create Edge'."""
        session = self.active_session()
        canvas = self.main_window.canvas_view
        if not session or not pts:
            canvas.clear_draw_artifacts()
            return

        params, curve_type = self._shape_params_from_points(tool, pts)
        if params is None:
            canvas.clear_draw_artifacts()
            self.main_window.log_panel.log(f"Could not build {tool}.")
            return

        # Drop the green drawing artifacts; the edit session uses its own
        # (cyan) control-point handles bound to the pending edge.
        canvas.clear_draw_artifacts()

        new_id = session.project_model._next_curve_id
        seg = SegmentModel(new_id, -1, -1)
        seg.type = "curve"
        seg.curve_type = curve_type
        seg.curve_mode = "parametric"
        seg.parameters = {"n_points": 50}
        seg.parameters.update(params)
        self._begin_pending_edit(seg)

    # ── Modeless create-edit session (control points + live numeric dialog) ──

    def _begin_pending_edit(self, seg, is_new=True):
        self._pending_seg = seg
        self._pending_is_new = is_new
        # Snapshot params so cancelling an *edit* restores the original shape.
        self._pending_orig = None if is_new else dict(seg.parameters)
        # Clear the static selection highlight / transform gizmo so only the
        # live preview + control points are shown during the edit.
        canvas = self.main_window.canvas_view
        canvas.update_active_segments_pts([])
        canvas.clear_transform_handles()
        self._show_pending_handles()
        self._preview_pending()
        from app.views.shape_dialog import ShapeParamDialog
        dlg = ShapeParamDialog(seg, self.main_window,
                               changed_cb=self._on_pending_dialog_changed,
                               confirm_text="Create Edge" if is_new else "Apply")
        dlg.setModal(False)
        # Tool window: floats above the main window (even while dragging control
        # points on the canvas) but recedes when switching apps.
        dlg.setWindowFlags(Qt.WindowType.Tool)
        dlg.accepted.connect(self._commit_pending_edge)
        dlg.rejected.connect(self._cancel_pending_edit)
        dlg.finished.connect(lambda _r, d=dlg: d.deleteLater())
        self._pending_dialog = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _show_pending_handles(self):
        canvas = self.main_window.canvas_view
        if self._pending_seg is None:
            canvas.clear_edge_handles()
            canvas.clear_endpoint_markers()
            return
        cps = self._edge_control_points(self._pending_seg)
        canvas.show_edge_handles([{"id": hid, "pos": pos} for hid, pos in cps])
        # Clearly mark other edges' endpoints (the snap targets) — excluding the
        # edge currently being edited so it does not target its own points.
        session = self.active_session()
        if session is not None:
            canvas.show_endpoint_markers(
                self._snap_targets(session, exclude=self._pending_seg))

    def _preview_pending(self):
        session = self.active_session()
        seg = self._pending_seg
        if not session or seg is None:
            return
        canvas = self.main_window.canvas_view
        try:
            xs, ys = GeometryService.compute_curve_preview_pts(
                seg, seg.parameters.get("n_points", 50), session.original_points)
        except Exception:
            xs, ys = None, None
        if xs is not None and ys is not None and len(xs) > 0:
            canvas.update_curve_preview(session.session_id, np.column_stack([xs, ys]))
        else:
            canvas.clear_curve_preview(session.session_id)

    def _on_pending_handle_dragged(self, handle_id, x, y, finished):
        """A control point of the pending edge was dragged on the canvas → update
        the edge, mirror the value into the dialog, and refresh the preview.

        The dragged endpoint auto-snaps to a nearby endpoint of another edge so
        edges connect exactly; the handle locks onto the snap target on release."""
        seg = self._pending_seg
        if seg is None:
            return
        session = self.active_session()
        snapped = False
        if session is not None:
            x, y, snapped = self._snap_point(
                x, y, self._snap_targets(session, exclude=seg))
        self._apply_handle_drag_to_params(seg, handle_id, x, y)
        if self._pending_dialog is not None:
            self._pending_dialog.set_values(
                seg.parameters, seg.parameters.get("n_points", 50))
        self._preview_pending()
        if finished:
            # Reposition dependent handles (and lock the dragged one onto the
            # snap target, e.g. the circle rim after a move).
            self._show_pending_handles()

    def _snap_targets(self, session, exclude=None) -> list[tuple[float, float]]:
        """Endpoints (first/last point) of every edge — the candidate points a
        dragged control point can snap to (and the always-on markers). Pass
        ``exclude`` (the edge being edited) so it does not target its own points."""
        targets: list[tuple[float, float]] = []
        for seg in session.project_model.segments:
            if seg is exclude:
                continue
            pts = GeometryService.get_segment_points(session, seg)
            if pts is None or len(pts[0]) == 0:
                continue
            xs, ys = pts
            targets.append((float(xs[0]), float(ys[0])))
            targets.append((float(xs[-1]), float(ys[-1])))
        return targets

    def _snap_point(self, x, y, targets):
        """Snap (x, y) to the nearest target endpoint within a view-scaled
        tolerance. Returns (x, y, snapped)."""
        if not targets:
            return x, y, False
        try:
            vb = self.main_window.canvas_view.plot_widget.plotItem.vb
            (x0, x1), (y0, y1) = vb.viewRange()
            tol = 0.025 * max(abs(x1 - x0), abs(y1 - y0), 1e-9)
        except Exception:
            tol = 1e-6
        best = None
        best_d = tol
        for tx, ty in targets:
            d = math.hypot(x - tx, y - ty)
            if d <= best_d:
                best_d = d
                best = (tx, ty)
        if best is not None:
            return best[0], best[1], True
        return x, y, False

    def _snap_draw_xy(self, x, y):
        """Canvas snap_cb: snap a placement click/cursor to a nearby endpoint."""
        session = self.active_session()
        if not session:
            return x, y
        # Exclude the edge currently being edited (if any) from the targets.
        exclude = self._pending_seg or self._pending_file_seg
        sx, sy, _ = self._snap_point(x, y, self._snap_targets(session, exclude=exclude))
        return sx, sy

    def _edit_in_progress(self) -> bool:
        return self._pending_seg is not None or self._pending_file is not None

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
        dlg.setWindowFlags(Qt.WindowType.Tool)
        dlg.accepted.connect(self._commit_file_edit)
        dlg.rejected.connect(self._cancel_file_edit)
        dlg.finished.connect(lambda _r, d=dlg: d.deleteLater())
        self._pending_file_dialog = dlg
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
        self._clear_file_edit_state()
        if session is None:
            return
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
        self._show_pending_handles()
        self._preview_pending()

    def _commit_pending_edge(self):
        seg = self._pending_seg
        is_new = self._pending_is_new
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
            # Editing an existing edge: params were mutated in place — just
            # redraw and reselect it.
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
        self._clear_pending_state()
        if (not is_new) and seg is not None and orig is not None:
            # Restore the edited edge's original shape.
            seg.parameters = orig
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
        canvas.clear_edge_handles()
        if session is not None:
            canvas.clear_curve_preview(session.session_id)
        # Restore the always-on endpoint markers for the remaining edges.
        self._refresh_endpoint_markers()

    @staticmethod
    def _apply_handle_drag_to_params(seg, handle_id, x, y):
        """Mutate a shape's defining parameters from a dragged control point."""
        shape_spec.apply_drag(seg.curve_type, seg.parameters, handle_id, x, y)

    @staticmethod
    def _shape_params_from_points(tool: str, pts: list):
        """Map the drawn canvas points → (parameters, curve_type)."""
        return shape_spec.params_from_points(tool, pts)

    def open_custom_formula_dialog(self):
        """Open the custom-formula dialog with a LIVE canvas preview (and fit the
        view to it on first show), then add the resulting analytic edge."""
        session = self.active_session()
        if not session:
            return
        canvas = self.main_window.canvas_view
        self._custom_preview_fitted = False
        from app.views.shape_dialog import CustomFormulaDialog
        dlg = CustomFormulaDialog(self.main_window,
                                  preview_cb=self._preview_custom_formula)
        accepted = dlg.exec()
        canvas.clear_curve_preview(session.session_id)
        if not accepted:
            return
        cfg = dlg.result_config()

        new_id = session.project_model._next_curve_id
        seg = SegmentModel(new_id, -1, -1)
        seg.type = "curve"
        seg.curve_type = "custom"
        seg.curve_mode = cfg["mode"]
        seg.x_formula = cfg["x_formula"]
        seg.y_formula = cfg["y_formula"]
        seg.formula = cfg["formula"]
        seg.t_min = cfg["t_min"]
        seg.t_max = cfg["t_max"]
        seg.parameters = {"n_points": cfg["n_points"]}

        cmd = AddCurveSegmentCmd(
            session,
            refresh_cb=self._refresh_segment_list,
            select_cb=self._select_segment_by_index,
            preconfigured_seg=seg,
        )
        session.command_history.execute(cmd)
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, True)
        self.main_window.log_panel.log(f"Added Custom Formula Edge {seg.id}.")

    def _preview_custom_formula(self, cfg: dict):
        """Live-render a custom-formula config to the canvas while its dialog is
        open; fit the view to it on the first valid preview (req 2)."""
        session = self.active_session()
        if not session:
            return
        seg = SegmentModel(0, -1, -1)
        seg.type = "curve"
        seg.curve_type = "custom"
        seg.curve_mode = cfg["mode"]
        seg.x_formula = cfg["x_formula"]
        seg.y_formula = cfg["y_formula"]
        seg.formula = cfg["formula"]
        seg.t_min = cfg["t_min"]
        seg.t_max = cfg["t_max"]
        canvas = self.main_window.canvas_view
        try:
            xs, ys = GeometryService.compute_curve_preview_pts(
                seg, int(cfg["n_points"]), session.original_points)
        except Exception:
            xs, ys = None, None
        if xs is not None and ys is not None and len(xs) > 0:
            pts = np.column_stack([xs, ys])
            canvas.update_curve_preview(session.session_id, pts)
            # Fit the view on every change while the formula dialog is open (req 2).
            canvas.fit_to_points(pts)
        else:
            canvas.clear_curve_preview(session.session_id)

    # ══════════════════════════════════════════════════════════════════════
    # Editable control-point handles for the selected analytic edge
    # ══════════════════════════════════════════════════════════════════════

    def _edge_control_points(self, seg):
        """Return [(handle_id, (x, y)), ...] control points for ``seg``'s shape,
        using its raw defining parameters (no anchoring/transform)."""
        return shape_spec.control_points(
            getattr(seg, "curve_type", "custom"), seg.parameters)

    def _refresh_edge_handles(self):
        """Selecting an edge shows only the (orange) highlight — no on-canvas
        control-point markers (they were perceived as stray base-point markers).
        Numeric editing is done through the double-click dialog instead.  This
        stays a single chokepoint so handles are always cleared on selection.

        Exception: while a create-edit session is active, its control points
        must be left untouched."""
        if self._edit_in_progress():
            return
        self.main_window.canvas_view.clear_edge_handles()

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
        # Apply the drag through the shared handle→param mapping, then push the
        # result back into the (silently-updated) sidebar widgets.
        params = shape_spec.read_widget_params(sb, ct)
        shape_spec.apply_drag(ct, params, handle_id, x, y)
        shape_spec.write_widget_params(sb, ct, params, silent=True)

        # Sync the (silently-updated) widgets into the segment and re-preview.
        self.preview_curve_formula()
        if finished:
            session.is_geometry_modified = True
            self.main_window.update_title(session.display_name, True)
            # Re-snap the handles (e.g. circle rim onto the new radius ring).
            self._refresh_edge_handles()

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
            # modeless dialog + snapping) on the existing edge.
            self._begin_pending_edit(seg, is_new=False)

    def _edit_custom_formula(self, seg):
        """Reopen the custom-formula dialog (pre-filled) to edit an existing
        custom edge."""
        session = self.active_session()
        if not session:
            return
        from app.views.shape_dialog import CustomFormulaDialog
        dlg = CustomFormulaDialog(self.main_window, seg=seg)
        if not dlg.exec():
            return
        cfg = dlg.result_config()
        seg.curve_mode = cfg["mode"]
        seg.x_formula = cfg["x_formula"]
        seg.y_formula = cfg["y_formula"]
        seg.formula = cfg["formula"]
        seg.t_min = cfg["t_min"]
        seg.t_max = cfg["t_max"]
        seg.parameters["n_points"] = cfg["n_points"]
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
        if dlg.exec():
            updates, n_points = dlg.result_params()
            seg.parameters.update(updates)
            seg.parameters["n_points"] = n_points
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
