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

        with block_signals(*pivot_fields):
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
        with block_signals(spin):
            spin.setValue(value)

    def _force_base_mode_custom(self):
        """A manual drag means the user wants a custom reference point: switch
        Base Point to Custom (so the dragged value is kept and editable)."""
        sb = self.main_window.sidebar_view
        if sb.dup_base_mode_combo.currentText() != "Custom (Manual)":
            with block_signals(sb.dup_base_mode_combo):
                sb.dup_base_mode_combo.setCurrentText("Custom (Manual)")
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
