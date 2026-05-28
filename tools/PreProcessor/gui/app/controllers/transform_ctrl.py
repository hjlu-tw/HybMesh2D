from __future__ import annotations
import math
import numpy as np
from app.models.segment import SegmentModel
from app.models.session import GeometrySession
from app.commands.segment_cmds import DuplicateTransformCmd
from app.services.geometry_service import GeometryService

class TransformControllerMixin:
    """Mixin containing geometric transform, duplication, and mirroring logic."""

    def duplicate_with_transform(self):
        """Generate preview points for the active segment, apply the
        selected geometric transform, and add a new Polygon curve segment."""
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            self.main_window.log_panel.log("No segment selected.")
            return
        sb = self.main_window.sidebar_view
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return

        # Get points to duplicate
        if seg.type == "curve":
            self._sync_active_curve_segment_from_ui()

        pts_tuple = GeometryService.get_segment_points(session, seg)
        if pts_tuple is None:
            self.main_window.log_panel.log("Edge has no valid points — cannot duplicate.")
            return
        xs, ys = pts_tuple
        n = len(xs)

        transformed = self._apply_transform(xs, ys)
        if transformed is None:
            self.main_window.log_panel.log("Mirror axis direction is zero — cannot mirror.")
            return
        xs, ys = transformed

        # Create new polygon curve segment from transformed points
        v_str = ";".join(f"{x:.6g},{y:.6g}" for x, y in zip(xs, ys))
        new_seg = SegmentModel(session.project_model._next_curve_id, -1, -1)
        new_seg.type = "curve"
        new_seg.curve_type = "polygon"
        new_seg.parameters["vertices_str"] = v_str
        new_seg.parameters["n_points"] = n
        new_seg.start_index = -1
        new_seg.end_index = -1

        def select_cb(idx):
            self._select_segment_by_index(idx)

        delete_original = sb.dup_delete_orig_cb.isChecked()

        cmd = DuplicateTransformCmd(
            session=session,
            seg_idx=session.current_segment_idx,
            new_seg=new_seg,
            delete_original=delete_original,
            refresh_cb=self._refresh_segment_list,
            select_cb=select_cb
        )
        session.command_history.execute(cmd)
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, True)
        
        action_name = "Moved/Transformed" if delete_original else "Duplicated"
        self.main_window.log_panel.log(
            f"{action_name} Edge {seg.id} as Edge {new_seg.id} ({sb.dup_type_combo.currentText()}).")
        self._show_duplicate_preview = False
        self.main_window.canvas_view.clear_duplicate_preview()

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


    def handle_dup_type_changed(self):
        if self._is_populating:
            return
        self._show_duplicate_preview = True
        self.update_duplicate_base_point()
        self.update_duplicate_preview()

    def handle_dup_base_mode_changed(self):
        if self._is_populating:
            return
        self._show_duplicate_preview = True
        self.update_duplicate_base_point()
        self.update_duplicate_preview()

    def on_duplicate_param_changed(self):
        if self._is_populating:
            return
        self._show_duplicate_preview = True
        self.update_duplicate_preview()

    def update_duplicate_base_point(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            return

        sb = self.main_window.sidebar_view
        t_idx = sb.dup_type_combo.currentIndex()
        if t_idx == 5: # Translate
            sb.dup_base_mode_combo.setEnabled(False)
            sb.dup_trans_dx.setEnabled(True)
            sb.dup_trans_dy.setEnabled(True)
            return
        else:
            sb.dup_base_mode_combo.setEnabled(True)

        mode = sb.dup_base_mode_combo.currentText()
        if mode == "Custom (Manual)":
            sb.dup_rot_px.setEnabled(True)
            sb.dup_rot_py.setEnabled(True)
            sb.dup_mh_py.setEnabled(True)
            sb.dup_mv_px.setEnabled(True)
            sb.dup_ma_px.setEnabled(True)
            sb.dup_ma_py.setEnabled(True)
            sb.dup_ps_px.setEnabled(True)
            sb.dup_ps_py.setEnabled(True)
            sb.dup_scale_px.setEnabled(True)
            sb.dup_scale_py.setEnabled(True)
            return

        # Disable fields for Start / End Point mode
        sb.dup_rot_px.setEnabled(False)
        sb.dup_rot_py.setEnabled(False)
        sb.dup_mh_py.setEnabled(False)
        sb.dup_mv_px.setEnabled(False)
        sb.dup_ma_px.setEnabled(False)
        sb.dup_ma_py.setEnabled(False)
        sb.dup_ps_px.setEnabled(False)
        sb.dup_ps_py.setEnabled(False)
        sb.dup_scale_px.setEnabled(False)
        sb.dup_scale_py.setEnabled(False)

        # Retrieve points of current segment
        pts_tuple = GeometryService.get_segment_points(session, seg)
        if pts_tuple is None:
            return
        xs, ys = pts_tuple
        if len(xs) == 0:
            return
        if mode == "Start Point":
            px, py = xs[0], ys[0]
        else:
            px, py = xs[-1], ys[-1]

        # Populate coordinates
        sb.dup_rot_px.blockSignals(True)
        sb.dup_rot_py.blockSignals(True)
        sb.dup_mh_py.blockSignals(True)
        sb.dup_mv_px.blockSignals(True)
        sb.dup_ma_px.blockSignals(True)
        sb.dup_ma_py.blockSignals(True)
        sb.dup_ps_px.blockSignals(True)
        sb.dup_ps_py.blockSignals(True)
        sb.dup_scale_px.blockSignals(True)
        sb.dup_scale_py.blockSignals(True)

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

        sb.dup_rot_px.blockSignals(False)
        sb.dup_rot_py.blockSignals(False)
        sb.dup_mh_py.blockSignals(False)
        sb.dup_mv_px.blockSignals(False)
        sb.dup_ma_px.blockSignals(False)
        sb.dup_ma_py.blockSignals(False)
        sb.dup_ps_px.blockSignals(False)
        sb.dup_ps_py.blockSignals(False)
        sb.dup_scale_px.blockSignals(False)
        sb.dup_scale_py.blockSignals(False)

    def update_duplicate_preview(self):
        if not self._show_duplicate_preview:
            self.main_window.canvas_view.clear_duplicate_preview()
            return

        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            self.main_window.canvas_view.clear_duplicate_preview()
            return
        
        sb = self.main_window.sidebar_view
        if not sb._transform_dup_group.isVisible():
            self.main_window.canvas_view.clear_duplicate_preview()
            return

        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg:
            self.main_window.canvas_view.clear_duplicate_preview()
            return

        # 1. Get original points
        pts_tuple = GeometryService.get_segment_points(session, seg)
        if pts_tuple is None or len(pts_tuple[0]) < 2:
            self.main_window.canvas_view.clear_duplicate_preview()
            return
        xs, ys = pts_tuple

        # 2. Apply transform
        transformed = self._apply_transform(xs, ys)
        if transformed is None:
            self.main_window.canvas_view.clear_duplicate_preview()
            return
        xs, ys = transformed

        pts_new = np.column_stack([xs, ys])
        self.main_window.canvas_view.update_duplicate_preview(pts_new)
