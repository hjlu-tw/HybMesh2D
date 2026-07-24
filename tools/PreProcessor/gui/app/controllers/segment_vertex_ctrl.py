from __future__ import annotations
import numpy as np
from app.models.session import GeometrySession
from app.commands.split_cmds import AddSplitCmd, RemoveSplitCmd
from app.commands.vertex_cmds import InsertVertexCmd, ReplaceGeometryPointsCmd
from app.services.geometry_service import (
    project_point_to_segment, proportional_edge_move)


class SegmentVertexControllerMixin:
    """Mixin: single-vertex selection, drag/numeric move, split add/remove and
    point insertion. Split out of SegmentControllerMixin to keep each controller
    file under the ~800-line budget; composed into AppController alongside it."""

    def handle_point_clicked(self, idx: int):
        session = self.active_session()
        if not session:
            return
        session.selected_point_idx = idx
        self.main_window.canvas_view.update_selected_point(idx)

        sb = self.main_window.sidebar_view
        sb.selected_info.setText(f"Selected Vertex: Index {idx}")

        n_pts = (len(session.original_points)
                 if session.original_points is not None else 0)
        # Index 0 / N-1 are structural anchors for BOTH open and closed curves:
        # for a closed loop they are the seam, and removing that seam breakpoint
        # (e.g. a circle detected as one segment [0, N-1]) would leave zero file
        # segments — nothing clickable in edge mode. So they're never removable.
        is_endpoint = (idx == 0 or idx == n_pts - 1)
        is_split = idx in session.split_indices

        sb.split_btn.setEnabled(not is_split)
        sb.remove_split_btn.setEnabled(is_split and not is_endpoint)

        # #6: expose a draggable move-handle on the canvas and seed the numeric
        # "Move to" fields with the vertex's current position.
        canvas = self.main_window.canvas_view
        if (session.original_points is not None
                and 0 <= idx < len(session.original_points)):
            x, y = (float(session.original_points[idx][0]),
                    float(session.original_points[idx][1]))
            sb.move_x.blockSignals(True); sb.move_y.blockSignals(True)
            sb.move_x.setValue(x); sb.move_y.setValue(y)
            sb.move_x.blockSignals(False); sb.move_y.blockSignals(False)
            sb.move_btn.setEnabled(True)
            canvas.show_vertex_move_handle(idx, x, y)

    def handle_point_deselected(self):
        """Clear vertex selection when user clicks far from all vertices."""
        session = self.active_session()
        if not session:
            return
        session.selected_point_idx = None
        self._vertex_drag_orig = None
        self.main_window.canvas_view.update_selected_point(None)
        self.main_window.canvas_view.clear_vertex_move_handle()

        sb = self.main_window.sidebar_view
        sb.selected_info.setText("Selected Vertex: None")
        sb.split_btn.setEnabled(False)
        sb.remove_split_btn.setEnabled(False)
        sb.move_btn.setEnabled(False)

    def move_selected_vertex_to(self, x: float = None, y: float = None):
        """Move the selected vertex / split point to (x, y) — from the numeric
        'Move to' fields when x/y are omitted (#6). Undoable geometry edit."""
        session = self.active_session()
        if session is None or session.selected_point_idx is None \
                or session.original_points is None:
            return
        idx = session.selected_point_idx
        pts = session.original_points
        if not (0 <= idx < len(pts)):
            return
        sb = self.main_window.sidebar_view
        if x is None:
            x = sb.move_x.value()
        if y is None:
            y = sb.move_y.value()
        old = pts.copy()
        if np.allclose(old[idx], [x, y]):
            return
        # #2: proportional edge scaling, same as the drag interaction.
        new = proportional_edge_move(old, session.split_indices, idx, x, y)
        cmd = ReplaceGeometryPointsCmd(
            session, old, new,
            refresh_cb=lambda: self._apply_geometry_update(session),
            label="Move vertex")
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Moved vertex {idx} to ({x:.4f}, {y:.4f}).")
        self.handle_point_clicked(idx)

    def _on_vertex_move_dragged(self, idx: int, x: float, y: float, finished: bool):
        """Canvas drag of the selected vertex handle (#6): live-preview while
        dragging, commit one undoable edit on release. The whole edge scales
        proportionally with the drag (#2)."""
        session = self.active_session()
        if session is None or session.original_points is None:
            return
        pts = session.original_points
        if not (0 <= idx < len(pts)):
            return
        if getattr(self, "_vertex_drag_orig", None) is None:
            self._vertex_drag_orig = pts.copy()
        new = proportional_edge_move(self._vertex_drag_orig,
                                     session.split_indices, idx, x, y,
                                     is_closed=session.project_model.is_closed)
        if finished:
            old = self._vertex_drag_orig
            self._vertex_drag_orig = None
            cmd = ReplaceGeometryPointsCmd(
                session, old, new,
                refresh_cb=lambda: self._apply_geometry_update(session),
                label="Move vertex")
            session.command_history.execute(cmd)
            self.handle_point_clicked(idx)
            return
        # Live: update points + redraw without touching the undo stack or the
        # drag handle (the user is still holding it).
        session.original_points = new
        canvas = self.main_window.canvas_view
        disp = new
        if session.project_model.is_closed and len(disp) > 0 \
                and not np.allclose(disp[0], disp[-1]):
            disp = np.vstack((disp, disp[0]))
        canvas.set_active_points(disp)
        canvas.update_geometry(session.session_id, disp)
        canvas.update_split_points(session.split_indices)
        canvas.update_selected_point(idx)

    def add_split_point(self):
        session = self.active_session()
        if session is None or session.selected_point_idx is None:
            return
        idx = session.selected_point_idx
        cmd = AddSplitCmd(
            session, idx,
            sync_cb=lambda: self._on_split_changed(session),
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Added split point at index {idx}.")
        self.handle_point_clicked(idx)

    def remove_split_point(self):
        session = self.active_session()
        if session is None or session.selected_point_idx is None:
            return
        idx = session.selected_point_idx
        if idx not in session.split_indices:
            return
        # Never drop below two split points — the geometry needs at least one
        # spanning segment, or edge mode has nothing to select.
        n_pts = len(session.original_points) if session.original_points is not None else 0
        if idx in (0, n_pts - 1) or len(session.split_indices) <= 2:
            self.main_window.log_panel.log(
                "Can't remove this breakpoint: it's a structural endpoint/seam "
                "(the geometry needs at least one edge segment).")
            return
        keep = self.main_window.sidebar_view.keep_vertex_cb.isChecked()
        cmd = RemoveSplitCmd(
            session, idx, keep,
            sync_cb=lambda: self._on_split_changed(session),
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        action = "kept" if keep else "deleted"
        self.main_window.log_panel.log(
            f"Removed split point at {idx} (vertex {action}).")
        if keep:
            self.handle_point_clicked(idx)

    def _on_split_changed(self, session: GeometrySession):
        """Called after a lightweight split-only change (no geometry modification)."""
        if session is self.active_session():
            self.main_window.canvas_view.update_split_points(session.split_indices)
        self._sync_file_segments(session)

    def handle_insert_point(self):
        session = self.active_session()
        if session is None or session.original_points is None:
            self.main_window.log_panel.log("No geometry loaded.")
            return
        sb = self.main_window.sidebar_view
        x = sb.insert_x.value()
        y = sb.insert_y.value()
        p = np.array([x, y])

        # Find nearest edge
        pts = session.original_points
        n = len(pts)
        best_idx, min_dist = 0, float("inf")
        for i in range(n - 1):
            proj, _ = project_point_to_segment(p, pts[i], pts[i + 1])
            dist = float(np.hypot(*(p - proj)))
            if dist < min_dist:
                min_dist = dist
                best_idx = i

        insert_idx = best_idx + 1
        cmd = InsertVertexCmd(
            session, insert_idx, p, list(session.split_indices),
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Inserted ({x:.4f}, {y:.4f}) at index {insert_idx}.")
        self.handle_point_clicked(insert_idx)
