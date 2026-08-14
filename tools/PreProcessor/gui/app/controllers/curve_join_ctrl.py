from __future__ import annotations
import numpy as np
from PyQt6.QtWidgets import QApplication, QMessageBox
from app.models.segment import SegmentModel
from app.commands.join_cmds import JoinEdgesToPolygonCmd, KeepSeparateAndCloseCmd
from app.services.geometry_service import (
    GeometryService, format_vertices_str, _resample_polyline_uniform)
from app.controllers.curve_ctrl import _apply_default_polygon_spacing


class CurveJoinControllerMixin:
    """Mixin: join/close selected edges into one closed polygon boundary."""

    # ── Join / Close edges → one closed polygon ────────────────────────────
    def join_selected_edges_to_polygon(self):
        """Merge selected edges (curve AND/OR discrete file) that connect
        end-to-end into one polygon edge, clearing the "boundary not closed"
        warning. Acts on the selected edges (≥2); with fewer than 2 selected,
        falls back to every curve/file edge in the session.

        All-straight chains keep clean corner vertices; a discrete or curved
        piece makes the result follow the actual sampled points (an arc stays
        an arc). Closure = the "Force close" checkbox OR a chain that already
        forms a loop; otherwise the result is left open."""
        session = self.active_session()
        if not session:
            return
        pm = session.project_model
        indices = self.get_selected_segment_indices()
        joinable = [i for i in indices
                    if pm.get_segment(i) and pm.get_segment(i).type in ("curve", "file")]
        if len(joinable) < 2:
            joinable = [i for i, s in enumerate(pm.segments)
                        if s.type in ("curve", "file")]
        if len(joinable) < 2:
            self.log(
                "Join needs at least 2 edges — select them in the tree/canvas.")
            return

        edges, all_straight = [], True
        for i in joinable:
            s = pm.get_segment(i)
            pr = GeometryService.get_segment_points(session, s)
            if pr is None or len(pr[0]) < 2:
                self.log(
                    f"Join aborted: Edge {s.id} has no usable points.")
                return
            pts = np.column_stack(pr).astype(float)
            edges.append({"idx": i, "id": s.id, "pts": pts,
                          "p0": pts[0].copy(), "p1": pts[-1].copy()})
            if not (s.type == "curve" and getattr(s, "curve_type", "")
                    in ("line", "horizontal_line", "vertical_line")):
                all_straight = False

        tol = self._endpoint_tolerance(session)
        ordered, is_loop = self._chain_edges(edges, tol)
        if ordered is None:
            self.log(
                "Join aborted: the selected edges do not form a single "
                "connected chain (endpoints must meet within tolerance).")
            return

        try:
            force_close = self.main_window.sidebar_view.join_force_close_cb.isChecked()
        except AttributeError:
            force_close = False
        closed = bool(force_close or is_loop)

        # #1/#2 KEEP vs MERGE. KEEP keeps every selected edge as a SEPARATE,
        # individually selectable & vertex-editable segment (each keeps its own
        # BC), only welding shared endpoints and closing the loop at the project
        # level. MERGE collapses the chain into ONE polygon curve (single BC, no
        # per-vertex selection). Ask; headless defaults to KEEP.
        keep_separate = self._ask_join_keep_separate()
        if keep_separate is None:
            self.log("Join cancelled.")
            return

        state = "closed" if closed else "open"
        if keep_separate:
            cmd = KeepSeparateAndCloseCmd(
                session, [e["idx"] for e in edges], closed, tol,
                refresh_cb=self._refresh_segment_list)
            session.command_history.execute(cmd)
            self.log(
                f"Joined {len(edges)} edges into a {state} boundary — kept as "
                f"{len(edges)} separate, vertex-editable edges.")
        else:
            # MERGE: one polygon. All-straight keeps clean corners; a curved/
            # discrete chain follows its sampled points (smoothed).
            verts = (self._chain_corners(ordered, is_loop) if all_straight
                     else self._chain_merged_points(ordered, is_loop, tol))
            poly = SegmentModel(pm._next_curve_id, -1, -1)
            poly.type = "curve"
            poly.curve_type = "polygon"
            poly.curve_mode = "parametric"
            poly.closed = closed
            poly.parameters = {"n_points": 50, "vertices_str": format_vertices_str(verts)}
            _apply_default_polygon_spacing(poly.parameters)
            cmd = JoinEdgesToPolygonCmd(
                session, [e["idx"] for e in edges], poly,
                refresh_cb=self._refresh_segment_list,
                select_cb=self._select_segment_by_index)
            session.command_history.execute(cmd)
            shape = "corner polygon" if all_straight else "smoothed polyline"
            self.log(
                f"Joined {len(edges)} edges into a {state} {shape} "
                f"({len(verts)} vertices).")
        self._apply_geometry_update(session)
        self._update_canvas_curve_segments()
        self.detect_open_endpoints(session)

    def _chain_edges(self, edges, tol):
        """Order edges into one connected chain by endpoint coincidence,
        orienting each edge's point array head-to-tail. Returns
        (ordered_edges, is_loop) or (None, False) if not one chain. Each
        ordered entry has 'pts' running start→end along the chain, and 'src' —
        the caller's own edge dict, so a caller that needs the ORDER of the
        edges (not just the merged points) can read its 'idx'/'id' back out.

        The chain grows from BOTH of the seed edge's ends: the seed (edges[0], the
        lowest-index selection) may sit in the MIDDLE of an open chain, so a
        forward-only walk would strand every edge on the seed's p0 side and wrongly
        report a valid chain as disconnected."""
        n = len(edges)
        used = [False] * n
        used[0] = True
        # Oriented (point array, source edge) pairs, head→tail along the chain.
        chain = [{"pts": edges[0]["pts"], "src": edges[0]}]
        head_free = edges[0]["p0"]     # dangling end at the head of the chain
        tail_free = edges[0]["p1"]     # dangling end at the tail of the chain
        for _ in range(n - 1):
            attached = False
            for j in range(n):
                if used[j]:
                    continue
                p0, p1, pts = edges[j]["p0"], edges[j]["p1"], edges[j]["pts"]
                # Extend at the tail (chain ... -> tail_free -> new edge).
                if np.hypot(*(p0 - tail_free)) <= tol:
                    chain.append({"pts": pts, "src": edges[j]});        tail_free = p1
                elif np.hypot(*(p1 - tail_free)) <= tol:
                    chain.append({"pts": pts[::-1], "src": edges[j]});  tail_free = p0
                # Extend at the head (new edge -> head_free -> chain ...).
                elif np.hypot(*(p1 - head_free)) <= tol:
                    chain.insert(0, {"pts": pts, "src": edges[j]});        head_free = p0
                elif np.hypot(*(p0 - head_free)) <= tol:
                    chain.insert(0, {"pts": pts[::-1], "src": edges[j]});  head_free = p1
                else:
                    continue
                used[j] = True
                attached = True
                break
            if not attached:
                return None, False
        is_loop = bool(np.hypot(*(tail_free - head_free)) <= tol)
        return chain, is_loop

    @staticmethod
    def _chain_corners(ordered, is_loop):
        """Corner vertices for an all-straight chain: the first point plus the
        end point of each edge, dropping the closing duplicate when it loops."""
        verts = [ordered[0]["pts"][0]]
        for e in ordered:
            verts.append(e["pts"][-1])
        if is_loop and len(verts) > 1:
            verts = verts[:-1]
        return verts

    @staticmethod
    def _chain_merged_points(ordered, is_loop, tol):
        """Concatenate the oriented full point arrays, dropping the duplicated
        junction shared between consecutive edges (and the closing duplicate for
        a loop) — preserves each edge's actual shape (arcs stay arcs)."""
        pts = [ordered[0]["pts"][0]]
        for e in ordered:
            ep = e["pts"]
            for k in range(1, len(ep)):
                pts.append(ep[k])
        pts = np.asarray(pts, float)
        if is_loop and len(pts) > 1 and np.hypot(*(pts[-1] - pts[0])) <= tol:
            pts = pts[:-1]
        # Even out vertex spacing so the downstream resampler distributes points
        # uniformly. Raw concatenated samples are unevenly dense (a discrete arc
        # next to a straight piece), and every polygon vertex is pinned, so
        # without this the preview clusters points. Uniform arc-length resampling
        # keeps the shape (arcs stay arcs) while making the vertices even.
        if len(pts) >= 3:
            if is_loop:
                loop = np.vstack([pts, pts[0]])
                xs, ys = _resample_polyline_uniform(loop[:, 0], loop[:, 1], len(pts) + 1)
                pts = np.column_stack([xs, ys])[:-1]
            else:
                xs, ys = _resample_polyline_uniform(pts[:, 0], pts[:, 1], len(pts))
                pts = np.column_stack([xs, ys])
        return pts

    def _ask_join_keep_separate(self):
        """#1/#2 Ask whether to KEEP the selected edges as separate, individually
        selectable/BC-able edges (weld their shared endpoints and close the loop)
        or MERGE them into one polygon curve. Returns True (keep), False (merge)
        or None (cancel). Factored out so headless tests can stub the choice
        without a modal dialog."""
        # Headless (offscreen/minimal) runs can't service a modal — default to KEEP
        # (the recommended behaviour) so a batch/test join never blocks. Tests that
        # want to exercise MERGE monkeypatch this method to return False.
        app = QApplication.instance()
        if app is not None and app.platformName() in ("offscreen", "minimal"):
            return True
        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Join / Close Edges")
        box.setText("Keep the edges separate, or merge into one polygon?")
        box.setInformativeText(
            "Keep separate — every selected edge stays its own segment (you can "
            "still select its vertices and give it its own boundary condition); "
            "shared endpoints are welded and the loop is closed.\n\n"
            "Merge into one — collapse the chain into a single polygon curve "
            "(one boundary condition, no per-vertex selection).")
        keep_btn = box.addButton("Keep separate", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Merge into one", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(keep_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_btn or clicked is None:
            return None
        return clicked is keep_btn
