from __future__ import annotations
import math
import numpy as np
from app.models.segment import SegmentModel
from app.commands.segment_cmds import (
    AddCurveSegmentCmd, BakeCurveToGeometryCmd)
from app.services.geometry_service import (
    GeometryService)
from app.models import shape_spec

# Curve-type list, indexed by the type combo's row order.
CURVE_TYPES = ["custom", "horizontal_line", "vertical_line", "line",
               "circle", "triangle", "quadrilateral", "polygon", "arc"]


def _polygon_perimeter(verts) -> float:
    """Closed-polygon perimeter (incl. the closing edge) from a list of (x, y).
    Used to convert a target spacing into a node count for By-Spacing mode (#2)."""
    n = len(verts)
    if n < 2:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def _apply_default_polygon_spacing(params: dict):
    """#1: newly-created polygons distribute *By Spacing* by default so density
    follows the perimeter length instead of a fixed node count. The default
    spacing targets ~100 nodes at the shape's own scale (perimeter / 100), so it
    stays sensible whatever the geometry's units; it falls back to 0.1 when the
    perimeter is unknown. Mutates ``params`` in place."""
    per = _polygon_perimeter(shape_spec.polygon_vertices(params))
    spacing = round(per / 100.0, 6) if per > 0 else 0.1
    params["spacing"] = spacing
    if per > 0:
        params["n_points"] = max(2, int(round(per / spacing)))


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

    # ── Join / Close edges → one closed polygon ────────────────────────────


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

        # #2: a polygon distributed "By Spacing" derives its node count from the
        # (now up-to-date) vertices' perimeter, so point density follows edge
        # length; 'spacing' is kept for round-trip. Any other mode drops the key
        # so the spinbox node count governs (the backend consumes n_points).
        if (seg.curve_type == "polygon"
                and sb.curve_dist_mode.currentText() == "By Spacing"):
            spacing = max(1e-9, sb.curve_spacing.value())
            seg.parameters["spacing"] = spacing
            per = _polygon_perimeter(shape_spec.polygon_vertices(seg.parameters))
            if per > 0:
                seg.parameters["n_points"] = max(2, int(round(per / spacing)))
        else:
            seg.parameters.pop("spacing", None)

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
            # #1: switching to a polygon defaults it to By-Spacing distribution
            # (density follows the perimeter). Non-polygon types drop any leftover
            # 'spacing' so they stay node-count.
            if new_type == "polygon":
                _apply_default_polygon_spacing(seg.parameters)
            else:
                seg.parameters.pop("spacing", None)
            # Push the fresh defaults into the shape widgets before syncing back.
            with self.populating():
                sb.show_curve_segment(seg)

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
                except Exception as e:
                    # A broken curve formula shouldn't silently drop the edge's
                    # preview — log it so the user can see which edge is bad.
                    self.main_window.log_panel.log(
                        f"[Curve] [WARNING] Edge {seg.id} preview failed: {e}")
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


    # ── Modeless create-edit session (control points + live numeric dialog) ──


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
        from app.utils import offset_popup
        offset_popup(dlg, self.main_window)
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
