from __future__ import annotations
import pyqtgraph as pg
import numpy as np


# ── Dark-theme palette ────────────────────────────────────────────────────────
_CANVAS_BG = '#0c0d16'
_CANVAS_FG = '#6b738c'

_COL_SPLIT    = '#FF6E6E'   # red — split points
_COL_SELECTED = '#00E5FF'   # cyan — selected point
_COL_ACTIVE   = '#FFB347'   # orange — active segment
_COL_RESAMPLED = '#FF79C6'  # magenta — resampled result
_COL_PREVIEW  = '#FF8C42'   # orange — formula preview
_COL_CLOSING  = '#FFD700'   # gold — auto-added closing edge (dashed)


class CanvasSelectionMixin:
    def set_active_points(self, points: np.ndarray | None):
        """Set the active session's display points for hit-testing."""
        self._active_points = points

    def update_split_points(self, indices: list[int]):
        # Filter to in-range indices: after removing a breakpoint/vertex a caller
        # may still pass a stale index that no longer exists, which would raise
        # an IndexError here.
        if self._active_points is not None and indices:
            n = len(self._active_points)
            valid = [i for i in indices if 0 <= i < n]
            if valid:
                sp = self._active_points[valid]
                self.split_scatter.setData(sp[:, 0], sp[:, 1])
            else:
                self.split_scatter.clear()
        else:
            self.split_scatter.clear()
        # Only show in vertex mode
        self.split_scatter.setVisible(self._selection_mode == 'vertex')

    def update_selected_point(self, idx: int | None):
        # Guard the index: the selected vertex may have just been deleted (e.g.
        # removing the picked breakpoint), leaving a stale out-of-range index.
        if (self._active_points is not None and idx is not None
                and 0 <= idx < len(self._active_points)):
            pt = self._active_points[idx]
            self.selected_scatter.setData([pt[0]], [pt[1]])
        else:
            self.selected_scatter.clear()
        # Only show in vertex mode
        self.selected_scatter.setVisible(self._selection_mode == 'vertex')

    def show_vertex_move_handle(self, idx: int, x: float, y: float):
        """Show a single draggable handle at the selected vertex so it can be
        dragged to move the underlying geometry/split point (#6). Drags report
        through ``vertex_move_cb(idx, x, y, finished)``. Vertex mode only."""
        self.clear_vertex_move_handle()
        if self._selection_mode != 'vertex':
            return
        t = pg.TargetItem(pos=(x, y), size=16, movable=True, symbol='o',
                          pen=pg.mkPen('#FFB347', width=3),
                          brush=pg.mkBrush(255, 179, 71, 90),
                          hoverBrush=pg.mkBrush('#FFB347'))
        t.setZValue(207)
        t.sigPositionChanged.connect(
            lambda it, _i=idx: self._emit_vertex_move(_i, it, False))
        t.sigPositionChangeFinished.connect(
            lambda it, _i=idx: self._emit_vertex_move(_i, it, True))
        self.plot_widget.addItem(t)
        self._vertex_move_handle = t

    def clear_vertex_move_handle(self):
        if self._vertex_move_handle is not None:
            self.plot_widget.removeItem(self._vertex_move_handle)
            self._vertex_move_handle = None

    def _emit_vertex_move(self, idx: int, it, finished: bool):
        if self._suppress_vertex_cb:
            return
        if self.vertex_move_cb is not None:
            self.vertex_move_cb(idx, float(it.pos().x()),
                                float(it.pos().y()), finished)

    def set_selection_mode(self, mode: str):
        """Set the canvas click selection mode: 'vertex' or 'edge'.

        Also updates overlay visibility so that:
        - In 'vertex' mode: vertex selection markers (split points, selected point)
          are visible; segment highlight overlays are hidden.
        - In 'edge' mode: segment highlight overlays are visible; vertex markers
          are hidden.
        """
        self._selection_mode = mode
        is_vertex = (mode == 'vertex')
        is_edge = (mode == 'edge')

        # Rubber-band box selection is only meaningful for edges.
        self._select_vb.box_enabled = is_edge

        # Vertex-mode overlays
        self.split_scatter.setVisible(is_vertex)
        self.selected_scatter.setVisible(is_vertex)
        if not is_vertex:
            self.clear_vertex_move_handle()

        # Edge-mode overlays: keep existing segment highlights visible only in edge mode
        self.active_segment_curve.setVisible(is_edge)
        for item in self._multi_segment_curves:
            item.setVisible(is_edge)

    def update_active_segment(self, start_idx: int | None,
                               end_idx: int | None):
        if (self._active_points is not None
                and start_idx is not None and end_idx is not None
                and start_idx <= end_idx):
            sp = self._active_points[start_idx:end_idx + 1]
            self.active_segment_curve.setData(sp[:, 0], sp[:, 1])
        else:
            self.active_segment_curve.setData([], [])
        # Only show in edge mode
        self.active_segment_curve.setVisible(self._selection_mode == 'edge')

    def update_active_segments(self, segment_ranges: list[tuple[int, int]],
                                primary_idx: int = -1):
        """Highlight multiple segments simultaneously.

        segment_ranges: list of (start_index, end_index) for each selected segment.
        primary_idx: The index (into segment_ranges list) of the primary segment
                     that gets orange highlight; all others get a yellow highlight.
        """
        # Clear existing multi-segment overlays
        for item in self._multi_segment_curves:
            self.plot_widget.removeItem(item)
        self._multi_segment_curves.clear()

        if self._active_points is None or not segment_ranges:
            self.active_segment_curve.setData([], [])
            return

        for i, (start, end) in enumerate(segment_ranges):
            if start is None or end is None or start > end:
                continue
            if end >= len(self._active_points):
                end = len(self._active_points) - 1
            sp = self._active_points[start:end + 1]
            if len(sp) < 2:
                continue
            is_primary = (i == primary_idx)
            color = _COL_ACTIVE if is_primary else '#FFD700'  # orange or gold
            width = 4 if is_primary else 2.5
            zval = 20 if is_primary else 18
            item = self.plot_widget.plot(
                sp[:, 0], sp[:, 1],
                pen=pg.mkPen(color, width=width)
            )
            item.setZValue(zval)
            item.setVisible(self._selection_mode == 'edge')
            self._multi_segment_curves.append(item)

        # Clear the single active_segment_curve to avoid double drawing
        self.active_segment_curve.setData([], [])

    def update_active_segments_pts(self, pieces: list, primary_idx: int = -1):
        """Highlight selected edges given their point arrays directly.

        Unlike update_active_segments (which only handles discrete file ranges),
        this accepts arbitrary (N, 2) point arrays so analytic/curve edges and
        closed-loop closing edges are highlighted too."""
        for item in self._multi_segment_curves:
            self.plot_widget.removeItem(item)
        self._multi_segment_curves.clear()
        self.active_segment_curve.setData([], [])
        if not pieces:
            return
        for i, sp in enumerate(pieces):
            if sp is None or len(sp) < 2:
                continue
            is_primary = (i == primary_idx)
            color = _COL_ACTIVE if is_primary else '#FFD700'  # orange / gold
            width = 4 if is_primary else 2.5
            zval = 20 if is_primary else 18
            item = self.plot_widget.plot(
                np.asarray(sp)[:, 0], np.asarray(sp)[:, 1],
                pen=pg.mkPen(color, width=width))
            item.setZValue(zval)
            item.setVisible(self._selection_mode == 'edge')
            self._multi_segment_curves.append(item)
