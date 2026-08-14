from __future__ import annotations
import numpy as np
from app.services.geometry_service import GeometryService
from app.utils import block_signals


class SegmentCanvasControllerMixin:
    """Mixin containing canvas-driven edge selection: click/box hit-testing,
    highlight rendering, and segment polyline helpers.

    Also owns the two things the base-geometry layer needs from the model —
    when to wipe it (:meth:`_clear_geometry_canvas`) and where it must NOT join
    consecutive points (:meth:`_geometry_connect`) — both called from
    ``controller._apply_geometry_update``."""

    def _clear_geometry_canvas(self, session):
        """Wipe what the session's DISCRETE geometry drew, for a session that no
        longer has any (Clear All, or the last file edge converted away).

        USER-REPORTED: 'Clear All' then 'Redraw' left the old geometry on the
        canvas. The rebuild is driven by ``_apply_geometry_update``, which
        returned as its first statement when ``original_points`` was None — so
        the model was empty, every rebuild path agreed the model was empty, and
        the pyqtgraph items simply kept the last data anyone had pushed into
        them. Nothing else re-clears them, because clearing IS this method's job.

        Analytic (curve) edges are deliberately untouched: a session can have a
        drawn circle and no discrete points at all, and those items belong to
        ``_update_canvas_curve_segments``.
        """
        cv = self.main_window.canvas_view
        cv.update_geometry(session.session_id, None)
        if session is not self.active_session():
            return
        cv.set_active_points(None)
        cv.update_split_points([])
        cv.update_selected_point(None)
        cv.clear_closing_edge()
        cv.clear_open_endpoint_markers()
        cv.clear_resampled()
        sb = self.main_window.sidebar_view
        sb.geom_stats_panel.update_stats(
            None, closed=False, n_segments=len(session.project_model.segments),
            unit=self.length_unit_symbol())
        sb.show_vertex_selection(None)
        self.refresh_status_selection()

    @staticmethod
    def _geometry_connect(pm, n_orig: int, n_pts: int):
        """Where the base polyline must BREAK, as a pyqtgraph connect array.

        USER-REPORTED: converting the four sides of a quadrilateral to discrete
        out of order drew a diagonal. Two pieces that do not touch are still
        adjacent in ``original_points``, and the geometry is drawn as a single
        polyline, so the canvas joined them — a line that belongs to no edge,
        cannot be selected, and looks exactly like geometry.

        The breaks are read off the MODEL, not guessed from point spacing: the
        rebuild in ``update_file_segments_from_indices`` already drops the
        bridging index pair, so an index interval covered by no file segment is
        precisely a discontinuity. (A spacing heuristic would also break a
        legitimately long straight edge next to a finely sampled arc.)

        Returns None — connect everything, the fast path — when the model has
        fewer than two file segments or every interval is covered.
        """
        file_segs = [s for s in pm.segments if s.type == "file"]
        if len(file_segs) < 2 or n_pts < 3 or n_orig < 2:
            return None
        cov = np.zeros(n_pts, dtype=np.uint8)
        for s in file_segs:
            a, b = sorted((int(s.start_index), int(s.end_index)))
            a, b = max(0, a), min(n_orig - 1, b)
            if b > a:
                cov[a:b] = 1
        if n_pts > n_orig:
            # The caller appended the first point to close the display loop;
            # that seam is a real edge, and no file segment spans it.
            cov[n_orig - 1] = 1
        cov[-1] = 0                       # nothing follows the last point
        if cov[:n_pts - 1].all():
            return None
        return cov

    def _deselect_all_edges(self, session):
        """Clear the edge selection and its canvas highlight (empty-canvas click)."""
        sb = self.main_window.sidebar_view
        tree = sb.geometry_tree
        with block_signals(tree):
            tree.clear_edge_selection()
        session.current_segment_idx = -1
        self.handle_segment_selected(-1)
        self.highlight_selected_segments()

    def highlight_selected_segments(self):
        """Highlight every selected edge on the canvas — discrete (file) AND
        analytic (curve) — and dim the base geometry while a selection exists."""
        session = self.active_session()
        if not session:
            return
        sb = self.main_window.sidebar_view

        selected_indices = sb.geometry_tree.selected_edge_indices()
        self._update_join_button(selected_indices)

        if not selected_indices:
            self.main_window.canvas_view.update_active_segments_pts([])
            self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, False)
            return

        # Build a highlight polyline for each selected edge (any type).
        pieces = []
        primary_pos = 0
        current_idx = getattr(session, 'current_segment_idx', -1)
        for seg_idx in selected_indices:
            seg = session.project_model.get_segment(seg_idx)
            if not seg:
                continue
            poly = self._segment_polyline(session, seg)
            if poly is None:
                continue
            pieces.append(poly)
            if seg_idx == current_idx:
                primary_pos = len(pieces) - 1

        self.main_window.canvas_view.update_active_segments_pts(pieces, primary_idx=primary_pos)
        self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, bool(pieces))

    def _segment_polyline(self, session, seg) -> np.ndarray | None:
        """Return a segment's display points as an (N, 2) array, or None.

        Delegates to GeometryService.get_segment_points so discrete (file),
        analytic (curve) and closed-loop closing edges are all hit-tested with
        exactly the points used for transform / preview."""
        res = GeometryService.get_segment_points(session, seg)
        if res is None or len(res[0]) < 2:
            return None
        return np.column_stack([res[0], res[1]])

    @staticmethod
    def _point_to_polyline_dist(x: float, y: float, sp: np.ndarray) -> float:
        """Minimum distance from (x, y) to the polyline through points ``sp``."""
        best = float('inf')
        for i in range(len(sp) - 1):
            ax, ay = float(sp[i][0]), float(sp[i][1])
            bx, by = float(sp[i + 1][0]), float(sp[i + 1][1])
            dx, dy = bx - ax, by - ay
            len_sq = dx * dx + dy * dy
            if len_sq < 1e-20:
                d = ((x - ax) ** 2 + (y - ay) ** 2) ** 0.5
            else:
                t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / len_sq))
                d = ((x - (ax + t * dx)) ** 2 + (y - (ay + t * dy)) ** 2) ** 0.5
            if d < best:
                best = d
        return best

    def handle_canvas_segment_clicked(self, x: float, y: float, extend_selection: bool = False):
        """Handle a canvas click in edge selection mode: select/toggle the
        nearest segment. Both discrete (file) and analytic (curve/polygon)
        segments are considered, so a transformed/duplicated result can be
        clicked directly on the canvas instead of only via the edge list."""
        # Ignore selection clicks while creating/editing an edge (modeless dialog
        # open), so the in-progress control points are not cleared by a stray click.
        if self._edit_in_progress():
            return
        session = self.active_session()
        if not session:
            return

        segments = session.project_model.segments
        best_seg_idx = -1
        best_dist = float('inf')
        for seg_idx, seg in enumerate(segments):
            sp = self._segment_polyline(session, seg)
            if sp is None or len(sp) < 2:
                continue
            d = self._point_to_polyline_dist(x, y, sp)
            if d < best_dist:
                best_dist = d
                best_seg_idx = seg_idx

        # Clicking empty canvas (no edge, or too far from any edge) clears the
        # current highlight — unless the user is extending a selection.
        def _missed():
            if not extend_selection:
                self._deselect_all_edges(session)

        if best_seg_idx < 0:
            _missed()
            return

        # Reject clicks too far from any segment (3% of the visible range).
        vb = self.main_window.canvas_view.plot_widget.plotItem.vb
        view_range = vb.viewRange()
        x_range = abs(view_range[0][1] - view_range[0][0])
        y_range = abs(view_range[1][1] - view_range[1][0])
        data_threshold = max(x_range, y_range) * 0.03
        if best_dist > data_threshold:
            _missed()
            return

        sb = self.main_window.sidebar_view
        tree = sb.geometry_tree

        # Find and select/toggle the matching edge row in the model tree.
        found_item = tree.edge_item_by_index(session.session_id, best_seg_idx)

        with block_signals(tree):
            if found_item:
                if extend_selection:
                    found_item.setSelected(not found_item.isSelected())
                    if found_item.isSelected():
                        tree.setCurrentItem(found_item)
                        session.current_segment_idx = best_seg_idx
                    else:
                        sel = tree.selected_edge_indices()
                        session.current_segment_idx = sel[0] if sel else -1
                else:
                    tree.clear_edge_selection()
                    found_item.setSelected(True)
                    tree.setCurrentItem(found_item)
                    session.current_segment_idx = best_seg_idx

        seg = session.project_model.get_segment(session.current_segment_idx)
        sb.set_bake_curve_enabled(bool(seg and seg.type == "curve"))
        self.handle_segment_selected(session.current_segment_idx)
        self.highlight_selected_segments()

    def handle_canvas_box_selected(self, x0: float, y0: float,
                                   x1: float, y1: float, extend: bool = False):
        """Handle a rubber-band box selection from the canvas (edge mode).

        Selects every edge segment (discrete or analytic) with at least one
        point inside the box. Shift+drag replaces the current selection;
        Ctrl/Cmd+drag adds to it. No-op in vertex mode."""
        if self._edit_in_progress():
            return
        canvas = self.main_window.canvas_view
        if getattr(canvas, '_selection_mode', 'vertex') != 'edge':
            return
        session = self.active_session()
        if not session:
            return

        xmin, xmax = (x0, x1) if x0 <= x1 else (x1, x0)
        ymin, ymax = (y0, y1) if y0 <= y1 else (y1, y0)

        segments = session.project_model.segments
        hit_set = set()
        for seg_idx, seg in enumerate(segments):
            sp = self._segment_polyline(session, seg)
            if sp is None or len(sp) < 2:
                continue
            inside = ((sp[:, 0] >= xmin) & (sp[:, 0] <= xmax) &
                      (sp[:, 1] >= ymin) & (sp[:, 1] <= ymax))
            if np.any(inside):
                hit_set.add(seg_idx)

        sb = self.main_window.sidebar_view
        tree = sb.geometry_tree
        last_idx = -1
        with block_signals(tree):
            if not extend:
                tree.clear_edge_selection()
            for item in tree.edge_items(session.session_id):
                idx = tree.edge_index(item)
                if idx in hit_set:
                    item.setSelected(True)
                    tree.setCurrentItem(item)
                    last_idx = idx

        if last_idx >= 0:
            session.current_segment_idx = last_idx
            seg = session.project_model.get_segment(last_idx)
            sb.set_bake_curve_enabled(bool(seg and seg.type == "curve"))
            self.handle_segment_selected(last_idx)
        elif not extend:
            sb.set_bake_curve_enabled(False)
            self.handle_segment_selected(-1)
        self.highlight_selected_segments()

        if hit_set:
            self.log(f"Box-selected {len(hit_set)} edge(s).")
