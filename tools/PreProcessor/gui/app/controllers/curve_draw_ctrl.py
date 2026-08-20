from __future__ import annotations
import math
import numpy as np
from app.models.segment import SegmentModel
from app.services.geometry_service import GeometryService
from app.models import shape_spec
from app.controllers.curve_ctrl import _apply_default_polygon_spacing
from app.utils import block_signals


class CurveDrawControllerMixin:
    """Mixin: interactive shape creation and the modeless create-edit session."""

    # ══════════════════════════════════════════════════════════════════════
    # Interactive shape creation (tool → draw on canvas → add edge)
    # ══════════════════════════════════════════════════════════════════════

    def enter_shape_tool(self, tool: str):
        """Start a shape tool. ``tool`` is one of
        'line'|'circle'|'arc'|'rectangle'|'triangle'|'polygon'|'polyline'|'custom'.

        For 'custom' the formula dialog opens straight away (with a live canvas
        preview).  For the geometric shapes the canvas enters interactive
        click-to-place mode — each placed point shows a draggable control point
        and a live preview — and once the shape is complete the numeric dialog
        opens automatically, pre-filled with the drawn values."""
        session = self.active_session()
        if not session:
            self.log("No geometry session active.")
            return
        if tool == "custom":
            self.open_custom_formula_dialog()
            return
        canvas = self.main_window.canvas_view
        canvas.clear_edge_handles()
        canvas.clear_transform_handles()
        self._show_duplicate_preview = False
        canvas.start_draw_mode(tool)
        self.log(
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
            self.log(f"Could not build {tool}.")
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
        if curve_type == "polygon":
            _apply_default_polygon_spacing(seg.parameters)
            # The 'polyline' tool produces a polygon geometry but OPEN (the
            # renderer skips the closing seam); everything else stays closed.
            seg.closed = (tool != "polyline")
        self._begin_pending_edit(seg)

    # ── Modeless create-edit session (control points + live numeric dialog) ──

    def _begin_pending_edit(self, seg, is_new=True):
        # The owner takes the params + state snapshots that cancelling and
        # committing an *edit* need; this method only builds the Qt side. It
        # also REFUSES while another edit is live, so ask first.
        if not self._make_way_for_edit():
            return
        session = self.active_session()
        if not self.edge_edit.begin(seg, is_new=is_new, session=session):
            return
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
        # Modeless, kept above the app's main window (a Tool window) but NOT
        # above other applications, and nudged off centre so it doesn't cover
        # the shape being edited on the canvas.
        from app.utils import keep_on_top, offset_popup
        keep_on_top(dlg)
        dlg.accepted.connect(self._commit_pending_edge)
        dlg.rejected.connect(self._cancel_pending_edit)
        dlg.finished.connect(lambda _r, d=dlg: d.deleteLater())
        self.edge_edit.attach_dialog(dlg)
        offset_popup(dlg, self.main_window)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _show_pending_handles(self):
        canvas = self.main_window.canvas_view
        seg = self.edge_edit.segment
        if seg is None:
            canvas.clear_edge_handles()
            canvas.clear_endpoint_markers()
            return
        cps = self._edge_control_points(seg)
        canvas.show_edge_handles([{"id": hid, "pos": pos} for hid, pos in cps])
        # Clearly mark other edges' endpoints (the snap targets) — excluding the
        # edge currently being edited so it does not target its own points.
        session = self.active_session()
        if session is not None:
            canvas.show_endpoint_markers(
                self._snap_targets(session, exclude=seg))

    def _preview_pending(self):
        session = self.active_session()
        seg = self.edge_edit.segment
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
        seg = self.edge_edit.segment
        if seg is None:
            return
        session = self.active_session()
        snapped = False
        if session is not None:
            x, y, snapped = self._snap_point(
                x, y, self._snap_targets(session, exclude=seg))
        sb = self.main_window.sidebar_view
        lock = (seg.curve_type == "arc"
                and sb.arc_radius_locked())
        self._apply_handle_drag_to_params(seg, handle_id, x, y, lock_radius=lock)
        dlg = self.edge_edit.dialog
        if dlg is not None:
            dlg.set_values(seg.parameters, seg.parameters.get("n_points", 50))
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
        """Canvas snap_cb: snap a placement click/cursor to an endpoint, else the grid.

        Endpoint snapping runs FIRST and wins. Landing exactly on an existing
        geometry point matters more than landing on an abstract grid line: if the grid
        ran last unconditionally it would drag a just-welded endpoint back off the
        geometry, silently reopening the gap the user was closing.
        """
        from app.services.canvas_tools import compose_snap

        # Read the spin box directly: keeping a mirrored `grid_snap_step_value`
        # would be one quantity with two sources, which is exactly how they drift.
        mw = self.main_window
        widget = getattr(mw, "grid_snap_step", None)
        step = float(widget.value()) if widget is not None else 0.0
        if not getattr(mw, "grid_snap_on", False):
            step = 0.0

        session = self.active_session()
        if not session:
            gx, gy, _ = compose_snap(x, y, grid_step=step)
            return gx, gy
        # Exclude the edge currently being edited (if any) from the targets.
        exclude = self.edge_edit.active_segment
        targets = self._snap_targets(session, exclude=exclude)

        def endpoint_snap(px, py):
            sx, sy, _hit = self._snap_point(px, py, targets)
            return sx, sy

        gx, gy, _on_endpoint = compose_snap(
            x, y, endpoint_snap=endpoint_snap, grid_step=step)
        return gx, gy

    def _edit_in_progress(self) -> bool:
        # Two edit kinds, ONE owner — so one thing to ask, and one place where
        # "at most one edit is live" could be enforced.
        return self.edge_edit.is_active()

    @staticmethod
    def _apply_handle_drag_to_params(seg, handle_id, x, y, lock_radius=False):
        """Mutate a shape's defining parameters from a dragged control point."""
        shape_spec.apply_drag(seg.curve_type, seg.parameters, handle_id, x, y,
                              lock_radius=lock_radius)

    @staticmethod
    def _shape_params_from_points(tool: str, pts: list):
        """Map the drawn canvas points → (parameters, curve_type)."""
        return shape_spec.params_from_points(tool, pts)

    # ── Canvas tools: measure / grid snap / view history ──────────────────
    def _on_grid_snap_toggled(self, on: bool):
        """Grid snap is read at placement time, so toggling only affects the NEXT
        click — nothing already placed moves."""
        mw = self.main_window
        mw.grid_snap_on = bool(on)
        step = mw.grid_snap_step.value()
        self.log(
            f"[Canvas] grid snap {'ON' if on else 'OFF'}"
            + (f" (step {step:g})" if on else ""))

    def _on_grid_snap_step_changed(self, value: float):
        # Nothing to store: _snap_draw_xy reads the spin box itself.
        if getattr(self.main_window, "grid_snap_on", False):
            self.log(f"[Canvas] grid snap step {value:g}")

    def _on_measure_toggled(self, on: bool):
        cv = self.main_window.canvas_view
        if on:
            cv.start_measure_tool()
            self.log(
                "[Measure] click two points to read distance / dx / dy / angle "
                "(click again to start a new span).")
            self.main_window.flash_status("Measure: click two points")
        else:
            # Keep the last span drawn: the number is still worth reading after the
            # tool is switched off.
            cv.stop_measure_tool(keep_result=True)

    def _on_measure_ended(self):
        """The canvas left measure mode — by right-click, or because another tool took
        over. Un-check the toggle so the toolbar shows the tool that is actually live;
        the button used to stay pressed while Polygon was drawing."""
        btn = self.main_window.measure_btn
        if not btn.isChecked():
            return
        with block_signals(btn):
            btn.setChecked(False)

    def _on_measure_done(self, m: dict):
        """A completed span: report it where the user is already looking."""
        from app.services.canvas_tools import format_measure
        if not m:
            return
        text = format_measure(m)
        self.log(f"[Measure] {text}")
        self.main_window.flash_status(f"Measured  {text}", 8000)

    def _on_view_history_changed(self, can_back: bool, can_forward: bool):
        self.main_window.view_back_btn.setEnabled(bool(can_back))
        self.main_window.view_fwd_btn.setEnabled(bool(can_forward))
