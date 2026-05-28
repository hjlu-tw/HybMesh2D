from __future__ import annotations
import math
import numpy as np
from PyQt6.QtCore import Qt
from app.models.segment import SegmentModel
from app.models.session import GeometrySession
from app.commands.segment_cmds import AddCurveSegmentCmd, BakeCurveToGeometryCmd
from app.services.geometry_service import GeometryService

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
        CURVE_TYPES = ["custom", "horizontal_line", "vertical_line", "line", "circle", "triangle", "quadrilateral", "polygon"]
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

        # Sync parameters based on curve type
        if seg.curve_type == "horizontal_line":
            seg.parameters["y"] = sb.h_line_y.value()
            seg.parameters["x0"] = sb.h_line_x_start.value()
            seg.parameters["x1"] = sb.h_line_x_end.value()
        elif seg.curve_type == "vertical_line":
            seg.parameters["x"] = sb.v_line_x.value()
            seg.parameters["y0"] = sb.v_line_y_start.value()
            seg.parameters["y1"] = sb.v_line_y_end.value()
        elif seg.curve_type == "line":
            seg.parameters["x0"] = sb.line_x0.value()
            seg.parameters["y0"] = sb.line_y0.value()
            seg.parameters["x1"] = sb.line_x1.value()
            seg.parameters["y1"] = sb.line_y1.value()
        elif seg.curve_type == "circle":
            seg.parameters["cx"] = sb.circle_cx.value()
            seg.parameters["cy"] = sb.circle_cy.value()
            seg.parameters["r"] = sb.circle_r.value()
        elif seg.curve_type == "triangle":
            seg.parameters["x0"] = sb.tri_x0.value()
            seg.parameters["y0"] = sb.tri_y0.value()
            seg.parameters["x1"] = sb.tri_x1.value()
            seg.parameters["y1"] = sb.tri_y1.value()
            seg.parameters["x2"] = sb.tri_x2.value()
            seg.parameters["y2"] = sb.tri_y2.value()
        elif seg.curve_type == "quadrilateral":
            seg.parameters["x0"] = sb.quad_x0.value()
            seg.parameters["y0"] = sb.quad_y0.value()
            seg.parameters["x1"] = sb.quad_x1.value()
            seg.parameters["y1"] = sb.quad_y1.value()
            seg.parameters["x2"] = sb.quad_x2.value()
            seg.parameters["y2"] = sb.quad_y2.value()
            seg.parameters["x3"] = sb.quad_x3.value()
            seg.parameters["y3"] = sb.quad_y3.value()
        elif seg.curve_type == "polygon":
            seg.parameters["vertices_str"] = sb.poly_vertices.text()

    def handle_curve_type_changed(self):
        session = self.active_session()
        if not session or session.current_segment_idx < 0:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "curve":
            return
        self._sync_active_curve_segment_from_ui()
        # Update list item text
        sb = self.main_window.sidebar_view
        seg_idx = session.current_segment_idx
        item = None
        for row in range(sb.curve_segment_list.count()):
            curr_item = sb.curve_segment_list.item(row)
            if curr_item.data(Qt.ItemDataRole.UserRole) == seg_idx:
                item = curr_item
                break
        if item is not None:
            c_type = seg.curve_type
            from app.utils import CURVE_TYPE_LABELS
            lbl_val = CURVE_TYPE_LABELS.get(c_type, c_type.capitalize())
            c_label = lbl_val(seg) if callable(lbl_val) else lbl_val
            item.setText(f"Edge {seg.id}: {c_label}")
        self.preview_curve_formula()

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
