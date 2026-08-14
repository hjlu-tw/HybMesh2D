from __future__ import annotations
import numpy as np
from app.services.geometry_service import (
    GeometryService)
from app.utils import block_signals

class TransformControllerMixin:
    """Mixin containing geometric transform, duplication, and mirroring logic."""


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
        spec = sb.transform_spec()
        if not spec.has_reference_point:
            sb.set_transform_reference_applicable(False)
            return

        sb.set_transform_reference_applicable(True)
        # Pivot / axis spin boxes are user-editable only in Custom mode; for
        # every other mode they are driven by the computed reference point and
        # shown read-only. (Mirror-axis direction fields are always editable.)
        if spec.base_mode == "Custom (Manual)":
            sb.set_transform_reference(None)
            return

        pt = self._compute_dup_reference_point(session, spec.base_mode)
        if pt is None:
            return
        sb.set_transform_reference(pt)

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
            with block_signals(btn):
                btn.setChecked(on)
                btn.setText("✎  Editing on Canvas" if on else "✎  Edit on Canvas")

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

        # The gizmo mirrors the form, so it is placed from the same spec the
        # transform itself is computed from — no second reading of the widgets,
        # and no second copy of "which field is this transform's pivot".
        spec = sb.transform_spec()
        if spec.kind == "rotate":       # pivot + draggable angle handle
            canvas.show_transform_handles({'rotate': {
                'pivot': spec.rot_pivot, 'angle': spec.angle_deg}})
        elif spec.kind == "mirror_h":   # horizontal axis line
            canvas.show_transform_handles({'hline': spec.axis_y})
        elif spec.kind == "mirror_v":   # vertical axis line
            canvas.show_transform_handles({'vline': spec.axis_x})
        elif spec.kind == "mirror_axis":
            canvas.show_transform_handles({'axis': {
                'pivot': spec.axis_pivot, 'dir': spec.axis_dir}})
        elif spec.kind == "point_symmetry":
            canvas.show_transform_handles({'point': spec.sym_centre})
        elif spec.kind == "scale":
            canvas.show_transform_handles({'point': spec.scale_pivot})
        elif spec.kind == "translate":
            # Drag the selection centre to a destination.
            anchor = self._compute_dup_reference_point(session, "Center (selection)")
            if anchor is None:
                canvas.clear_transform_handles()
                return
            ax, ay = anchor
            canvas.show_transform_handles({'translate': {
                'anchor': (ax, ay),
                'dest': (ax + spec.delta[0], ay + spec.delta[1])}})
        else:
            canvas.clear_transform_handles()

    def _on_transform_handle_dragged(self, kind: str, x: float, y: float):
        """Live-update the transform form and the ghost preview as the user
        drags the base-point / axis handle on the canvas."""
        if self._is_populating:
            return
        sb = self.main_window.sidebar_view

        if kind == "translate":
            # The gizmo reports the DESTINATION of the selection centre, so the
            # shift vector is derived here — the form stores a delta, not a
            # point, and only the controller knows where the selection is.
            anchor = self._compute_dup_reference_point(
                self.active_session(), "Center (selection)")
            if anchor is not None:
                sb.set_transform_handle("translate", x - anchor[0], y - anchor[1])
        else:
            # Every handle except the rotate gizmo's angle moves a base point,
            # which implies the user wants a custom reference rather than the
            # computed one.
            if kind != "rotate_angle":
                sb.use_custom_transform_reference()
            sb.set_transform_handle(kind, x, y)

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
