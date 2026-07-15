"""Resampled-output / quality-heatmap / preview rendering, extracted verbatim
from CanvasView (behaviour unchanged). These methods draw the active session's
resampled result, the quality colour-heatmap, curve previews and the duplicate
preview, and clear those overlays. They read/write attributes created in
CanvasView.__init__ (resolved through the MRO) — they are pure mixin methods."""
from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import Qt

# Palette constants used by the rendering methods (kept identical to canvas.py).
_COL_RESAMPLED = '#FF79C6'  # magenta — resampled result


class CanvasRenderMixin:
    @staticmethod
    def _detect_gap_indices(points: np.ndarray) -> set:
        """Heuristic split of a flat point list into disconnected pieces.

        Returns the set of indices i where point i should NOT connect to i+1
        (a gap), detected as inter-point distances far above the median. Used
        as a fallback when the backend did not supply exact piece markers.
        """
        if points is None or len(points) < 2:
            return set()
        diffs = np.diff(points, axis=0)
        ds = np.sqrt(np.sum(diffs**2, axis=1))
        ds[ds < 1e-12] = 1e-12
        median_d = np.median(ds)
        gap_threshold = max(10.0 * median_d, 1e-3)
        return set(np.where(ds > gap_threshold)[0])

    @staticmethod
    def _connect_array(n: int, gap_indices: set) -> np.ndarray:
        """Build a pyqtgraph ``connect`` array of length n: 1 = connect point i
        to i+1, 0 = break the polyline after point i (at every gap)."""
        connect = np.ones(n, dtype=np.uint8)
        for gi in gap_indices:
            if 0 <= gi < n:
                connect[gi] = 0
        if n > 0:
            connect[-1] = 0
        return connect

    def load_resampled_data(self, points: np.ndarray | None, show_quality: bool = False,
                            quality_mode: str = 'length', gap_indices: set | None = None):
        if points is not None and len(points) > 0:
            # Exact piece boundaries from the backend (preview markers) when
            # provided; otherwise fall back to the distance heuristic.
            gaps = gap_indices if gap_indices is not None else self._detect_gap_indices(points)
            if show_quality and len(points) >= 2:
                diffs = np.diff(points, axis=0)
                ds = np.sqrt(np.sum(diffs**2, axis=1))
                ds[ds < 1e-12] = 1e-12

                gap_indices = gaps

                def compute_sub_ratios(sub_ds, sub_pts):
                    # A single-segment piece has no neighbour to compare against,
                    # so its ratio stays 1.0 (handled by the np.ones_like default).
                    sub_ratios = np.ones_like(sub_ds)
                    if len(sub_ds) >= 2:
                        # Only treat as a closed loop when the piece is large enough
                        # to actually be one; otherwise an open arc whose endpoints
                        # merely coincide would get the wrap-around ratio.
                        is_closed = len(sub_pts) >= 4 and np.allclose(sub_pts[0], sub_pts[-1])
                        if is_closed:
                            interface_ratios = np.zeros(len(sub_ds))
                            for j in range(len(sub_ds) - 1):
                                r1 = sub_ds[j] / sub_ds[j+1]
                                r2 = sub_ds[j+1] / sub_ds[j]
                                interface_ratios[j+1] = max(r1, r2)
                            r1 = sub_ds[-1] / sub_ds[0]
                            r2 = sub_ds[0] / sub_ds[-1]
                            interface_ratios[0] = max(r1, r2)
                            for i in range(len(sub_ds)):
                                next_idx = (i + 1) % len(sub_ds)
                                sub_ratios[i] = max(interface_ratios[i], interface_ratios[next_idx])
                        else:
                            interface_ratios = np.zeros(len(sub_ds) - 1)
                            for j in range(len(sub_ds) - 1):
                                r1 = sub_ds[j] / sub_ds[j+1]
                                r2 = sub_ds[j+1] / sub_ds[j]
                                interface_ratios[j] = max(r1, r2)
                            sub_ratios[0] = interface_ratios[0]
                            sub_ratios[-1] = interface_ratios[-1]
                            for i in range(1, len(sub_ds) - 1):
                                sub_ratios[i] = max(interface_ratios[i-1], interface_ratios[i])
                    return sub_ratios

                if quality_mode == 'ratio':
                    ratios = np.ones_like(ds)
                    start = 0
                    for gap_idx in sorted(gap_indices):
                        if gap_idx > start:
                            sub_ds = ds[start:gap_idx]
                            sub_pts = points[start:gap_idx+1]
                            ratios[start:gap_idx] = compute_sub_ratios(sub_ds, sub_pts)
                        start = gap_idx + 1
                    if start < len(ds):
                        sub_ds = ds[start:]
                        sub_pts = points[start:]
                        ratios[start:] = compute_sub_ratios(sub_ds, sub_pts)
                    vals = ratios
                    self.colorbar_widget.title_text = "Ratio"
                else:
                    vals = ds
                    self.colorbar_widget.title_text = "Length"

                # Determine color limits excluding gaps to avoid skews
                valid_vals = [vals[i] for i in range(len(vals)) if i not in gap_indices]
                if len(valid_vals) > 0:
                    if quality_mode == 'ratio':
                        min_val = 1.0
                        max_val = max(1.3, np.max(valid_vals))
                    else:
                        min_val = np.min(valid_vals)
                        max_val = np.max(valid_vals)
                else:
                    if quality_mode == 'ratio':
                        min_val = 1.0
                        max_val = 1.3
                    else:
                        min_val = np.min(vals)
                        max_val = np.max(vals)

                self.colorbar_widget.quality_mode = quality_mode
                self.colorbar_widget.set_range(min_val, max_val)
                self.colorbar_widget.setVisible(True)

                self.color_coded_segments.setData(points, vals, min_val, max_val, False, [], quality_mode, gap_indices)
                # Draw resampled node markers on top of the colour-coded
                # segments too, honouring the "Nodes" toggle. Previously the
                # symbol was forced off in heatmap mode, so ticking "Nodes"
                # showed nothing whenever the quality heatmap was on.
                sym = 'o' if self._show_nodes else None
                self.resampled_curve.setData(
                    points[:, 0], points[:, 1], pen=None,
                    symbol=sym, symbolBrush=pg.mkBrush(_COL_RESAMPLED), symbolSize=5)
                self.quality_bad_scatter.clear()
            else:
                self.colorbar_widget.setVisible(False)
                self.color_coded_segments.setData(None, None, 0, 0, False, [])

                sym = 'o' if self._show_nodes else None
                self.resampled_curve.setData(
                    points[:, 0], points[:, 1],
                    pen=pg.mkPen(_COL_RESAMPLED, width=2, style=Qt.PenStyle.DashLine),
                    symbol=sym, symbolBrush=pg.mkBrush(_COL_RESAMPLED),
                    connect=self._connect_array(len(points), gaps)
                )
                self.quality_bad_scatter.clear()
        else:
            self.colorbar_widget.setVisible(False)
            self.color_coded_segments.setData(None, None, 0, 0, False, [])
            self.resampled_curve.setData([], [])
            self.quality_bad_scatter.clear()

    def clear_resampled(self):
        self.colorbar_widget.setVisible(False)
        self.color_coded_segments.setData(None, None, 0, 0, False, [])
        self.resampled_curve.setData([], [])
        self.quality_bad_scatter.clear()

    def update_curve_preview(self, session_id: int, points: np.ndarray | None, show_symbols: bool = True):
        if session_id not in self._curve_preview_items:
            return
        if points is not None and len(points) > 0:
            sym = 'o' if (show_symbols and self._show_symbols) else None
            self._curve_preview_items[session_id].setData(points[:, 0], points[:, 1], symbol=sym)
        else:
            self._curve_preview_items[session_id].setData([], [])

    def clear_curve_preview(self, session_id: int):
        if session_id in self._curve_preview_items:
            self._curve_preview_items[session_id].setData([], [])

    def clear_active_overlays(self):
        """Clear all markers that belong to the active session."""
        self.split_scatter.clear()
        self.selected_scatter.clear()
        self.active_segment_curve.setData([], [])
        for item in self._multi_segment_curves:
            self.plot_widget.removeItem(item)
        self._multi_segment_curves.clear()
        self.resampled_curve.setData([], [])
        self.colorbar_widget.setVisible(False)
        self.color_coded_segments.setData(None, None, 0, 0, False, [])
        self.quality_bad_scatter.clear()
        self.duplicate_preview_curve.setData([], [])
        self._endpoint_markers.clear()
        self._open_endpoint_markers.clear()

    def clear_segment_highlight(self):
        """Clear only the active-segment / multi-segment highlight overlays.

        Called after a successful Preview run so the resampled result is not
        obscured by the orange selection overlay.  The edge-list selection is
        preserved, so the user can immediately continue editing.
        """
        self.active_segment_curve.setData([], [])
        for item in self._multi_segment_curves:
            self.plot_widget.removeItem(item)
        self._multi_segment_curves.clear()

    def update_duplicate_preview(self, points: np.ndarray | None):
        """Update the duplicate preview curve with transformed points.

        Multiple selected edges may be passed as a single array separated by
        rows of NaN; ``connect='finite'`` keeps those pieces visually distinct.
        """
        if points is not None and len(points) > 0:
            sym = 'o' if self._show_symbols else None
            self.duplicate_preview_curve.setData(
                points[:, 0], points[:, 1], symbol=sym, connect='finite')
        else:
            self.duplicate_preview_curve.setData([], [])

    def clear_duplicate_preview(self):
        """Clear the duplicate preview curve."""
        self.duplicate_preview_curve.setData([], [])
