from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor


# ── Dark-theme palette ────────────────────────────────────────────────────────
_CANVAS_BG = '#0c0d16'
_CANVAS_FG = '#6b738c'

_COL_SPLIT    = '#FF6E6E'   # red — split points
_COL_SELECTED = '#00E5FF'   # cyan — selected point
_COL_ACTIVE   = '#FFB347'   # orange — active segment
_COL_RESAMPLED = '#FF79C6'  # magenta — resampled result
_COL_PREVIEW  = '#FF8C42'   # orange — formula preview


class CanvasView(QWidget):
    """
    Shared interactive canvas that can display multiple geometry sessions
    simultaneously.  Only the ACTIVE session has editable markers
    (split points, selected point, active segment).
    """

    point_clicked = pyqtSignal(int)  # nearest index in active session's points

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOption('background', _CANVAS_BG)
        pg.setConfigOption('foreground', _CANVAS_FG)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setAspectLocked(True)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        layout.addWidget(self.plot_widget)

        # ── Per-session geometry layers ───────────────────────────────────
        self._geometries: dict[int, pg.PlotDataItem] = {}   # sid → curve
        self._geo_colors: dict[int, str] = {}               # sid → color str

        # ── Active-session overlays (single set, reused across sessions) ──

        # Resampled output — magenta dashed
        self.resampled_curve = self.plot_widget.plot(
            pen=pg.mkPen(_COL_RESAMPLED, width=2, style=Qt.PenStyle.DashLine),
            symbol='o', symbolBrush=_COL_RESAMPLED, symbolSize=5)

        # Active segment — thick orange
        self.active_segment_curve = self.plot_widget.plot(
            pen=pg.mkPen(_COL_ACTIVE, width=4))

        # Curve-formula preview — orange dashed
        self.curve_preview_item = self.plot_widget.plot(
            pen=pg.mkPen(_COL_PREVIEW, width=2, style=Qt.PenStyle.DashLine),
            symbol='o', symbolBrush=_COL_PREVIEW, symbolSize=4)

        # Split points — red dots
        self.split_scatter = pg.ScatterPlotItem(
            size=10, pen=pg.mkPen(None), brush=pg.mkBrush(_COL_SPLIT))
        self.plot_widget.addItem(self.split_scatter)

        # Selected point — cyan hollow circle
        self.selected_scatter = pg.ScatterPlotItem(
            size=14, pen=pg.mkPen(_COL_SELECTED, width=2), brush=None)
        self.plot_widget.addItem(self.selected_scatter)

        # Quality bad nodes — red 'x'
        self.quality_bad_scatter = pg.ScatterPlotItem(
            size=10, symbol='x', pen=pg.mkPen('#FF5252', width=2), brush=None)
        self.plot_widget.addItem(self.quality_bad_scatter)

        # Mouse-coordinate label
        self.coord_label = pg.TextItem('', anchor=(-0.1, 1.1),
                                       color=_CANVAS_FG)
        self.plot_widget.addItem(self.coord_label, ignoreBounds=True)
        self.coord_label.setZValue(100)

        # ── Active-session points (for hit-testing) ───────────────────────
        self._active_points: np.ndarray | None = None

        # ── Persistent background curve segments ──────────────────────────
        self._curve_segment_items: list[pg.PlotDataItem] = []

        # ── Mouse events ──────────────────────────────────────────────────
        self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

    # ═════════════════════════════════════════════════════════════════════
    # Multi-geometry management
    # ═════════════════════════════════════════════════════════════════════

    def add_geometry(self, session_id: int, points: np.ndarray | None,
                     color: str):
        """Add a new geometry layer for a session."""
        curve = self.plot_widget.plot(
            pen=pg.mkPen(color, width=2),
            symbolBrush=pg.mkBrush(color), symbolSize=3)
        if points is not None and len(points) > 0:
            curve.setData(points[:, 0], points[:, 1])
        self._geometries[session_id] = curve
        self._geo_colors[session_id] = color

    def update_geometry(self, session_id: int, points: np.ndarray | None):
        """Update an existing geometry layer."""
        if session_id not in self._geometries:
            return
        if points is not None and len(points) > 0:
            self._geometries[session_id].setData(points[:, 0], points[:, 1])
        else:
            self._geometries[session_id].setData([], [])

    def remove_geometry(self, session_id: int):
        """Remove a session's geometry layer."""
        if session_id in self._geometries:
            self.plot_widget.removeItem(self._geometries.pop(session_id))
            self._geo_colors.pop(session_id, None)

    def highlight_geometry(self, active_session_id: int):
        """
        Bold the active session's curve; mute all others.
        Active: width=2.5, full colour, symbol size=4.
        Inactive: width=1, 60 alpha (approx 23% opacity), symbol size=1.5.
        """
        for sid, curve in self._geometries.items():
            color_str = self._geo_colors.get(sid, '#64B5F6')
            if sid == active_session_id:
                curve.setPen(pg.mkPen(color_str, width=2.5))
                curve.setSymbolBrush(pg.mkBrush(color_str))
                curve.setSymbolSize(4)
            else:
                c = QColor(color_str)
                c.setAlpha(60)
                curve.setPen(pg.mkPen(c, width=1))
                c2 = QColor(color_str)
                c2.setAlpha(40)
                curve.setSymbolBrush(pg.mkBrush(c2))
                curve.setSymbolSize(1.5)

    def set_active_geometry_dimmed(self, active_session_id: int, dimmed: bool):
        """Dim the active geometry's base line so the selected segment stands out."""
        if active_session_id in self._geometries:
            curve = self._geometries[active_session_id]
            color_str = self._geo_colors.get(active_session_id, '#64B5F6')
            if dimmed:
                c = QColor(color_str)
                c.setAlpha(70)
                curve.setPen(pg.mkPen(c, width=1.5))
                c2 = QColor(color_str)
                c2.setAlpha(50)
                curve.setSymbolBrush(pg.mkBrush(c2))
                curve.setSymbolSize(2.5)
            else:
                # Restore to normal active style
                curve.setPen(pg.mkPen(color_str, width=2.5))
                curve.setSymbolBrush(pg.mkBrush(color_str))
                curve.setSymbolSize(4)

    def set_geometry_visible(self, session_id: int, visible: bool):
        """Toggle the visibility of a specific geometry layer."""
        if session_id in self._geometries:
            self._geometries[session_id].setVisible(visible)

    def set_active_overlays_visible(self, visible: bool):
        """Toggle the visibility of the active session overlays."""
        self.resampled_curve.setVisible(visible)
        self.active_segment_curve.setVisible(visible)
        self.curve_preview_item.setVisible(visible)
        self.split_scatter.setVisible(visible)
        self.selected_scatter.setVisible(visible)

    def fit_to_geometry(self, session_id: int):
        """Fit the view box to the points of a specific geometry layer."""
        if session_id in self._geometries:
            curve = self._geometries[session_id]
            x_data, y_data = curve.getData()
            if x_data is not None and len(x_data) > 0:
                min_x, max_x = np.min(x_data), np.max(x_data)
                min_y, max_y = np.min(y_data), np.max(y_data)
                dx = max_x - min_x
                dy = max_y - min_y
                if dx == 0: dx = 1.0
                if dy == 0: dy = 1.0
                self.plot_widget.plotItem.vb.setRange(
                    xRange=[min_x - 0.05 * dx, max_x + 0.05 * dx],
                    yRange=[min_y - 0.05 * dy, max_y + 0.05 * dy]
                )

    def fit_all(self):
        """Auto-range to show all loaded geometries."""
        self.plot_widget.autoRange()

    # ═════════════════════════════════════════════════════════════════════
    # Active-session overlays
    # ═════════════════════════════════════════════════════════════════════

    def set_active_points(self, points: np.ndarray | None):
        """Set the active session's display points for hit-testing."""
        self._active_points = points

    def update_split_points(self, indices: list[int]):
        if self._active_points is not None and indices:
            sp = self._active_points[indices]
            self.split_scatter.setData(sp[:, 0], sp[:, 1])
        else:
            self.split_scatter.clear()

    def update_selected_point(self, idx: int | None):
        if self._active_points is not None and idx is not None:
            pt = self._active_points[idx]
            self.selected_scatter.setData([pt[0]], [pt[1]])
        else:
            self.selected_scatter.clear()

    def update_active_segment(self, start_idx: int | None,
                               end_idx: int | None):
        if (self._active_points is not None
                and start_idx is not None and end_idx is not None
                and start_idx <= end_idx):
            sp = self._active_points[start_idx:end_idx + 1]
            self.active_segment_curve.setData(sp[:, 0], sp[:, 1])
        else:
            self.active_segment_curve.setData([], [])

    def load_resampled_data(self, points: np.ndarray | None, show_quality: bool = False):
        if points is not None and len(points) > 0:
            if show_quality and len(points) >= 2:
                diffs = np.diff(points, axis=0)
                ds = np.sqrt(np.sum(diffs**2, axis=1))
                ds[ds < 1e-12] = 1e-12
                ratios = np.ones(len(points))
                if len(points) >= 3:
                    ratios[1:-1] = ds[1:] / ds[:-1]
                
                brushes = []
                bad_x = []
                bad_y = []
                for i, r in enumerate(ratios):
                    if i == 0 or i == len(ratios) - 1:
                        brushes.append(pg.mkBrush("#2ECC71"))
                        continue
                    val = max(r, 1.0 / r) if r > 0 else 1e12
                    if val <= 1.05:
                        brushes.append(pg.mkBrush("#2ECC71"))
                    elif val <= 1.20:
                        brushes.append(pg.mkBrush("#E67E22"))
                    else:
                        brushes.append(pg.mkBrush("#FF5252"))
                        bad_x.append(points[i, 0])
                        bad_y.append(points[i, 1])
                
                self.resampled_curve.setData(points[:, 0], points[:, 1], symbol='o', symbolBrush=brushes)
                if bad_x:
                    self.quality_bad_scatter.setData(bad_x, bad_y)
                else:
                    self.quality_bad_scatter.clear()
            else:
                self.resampled_curve.setData(points[:, 0], points[:, 1], symbol='o', symbolBrush=pg.mkBrush(_COL_RESAMPLED))
                self.quality_bad_scatter.clear()
        else:
            self.resampled_curve.setData([], [])
            self.quality_bad_scatter.clear()

    def clear_resampled(self):
        self.resampled_curve.setData([], [])
        self.quality_bad_scatter.clear()

    def update_curve_preview(self, points: np.ndarray | None):
        if points is not None and len(points) > 0:
            self.curve_preview_item.setData(points[:, 0], points[:, 1], symbol='o')
        else:
            self.curve_preview_item.setData([], [])

    def clear_curve_preview(self):
        self.curve_preview_item.setData([], [])

    def clear_active_overlays(self):
        """Clear all markers that belong to the active session."""
        self.split_scatter.clear()
        self.selected_scatter.clear()
        self.active_segment_curve.setData([], [])
        self.resampled_curve.setData([], [])
        self.curve_preview_item.setData([], [])
        self.quality_bad_scatter.clear()
        self.update_curve_segments([])

    def update_curve_segments(self, segments_pts: list[np.ndarray]):
        """Clear and redraw all curve segments to keep them visible when deselected."""
        # Remove existing items from the plot
        for item in self._curve_segment_items:
            self.plot_widget.removeItem(item)
        self._curve_segment_items.clear()

        # Add new items
        for pts in segments_pts:
            if pts is not None and len(pts) > 0:
                # Plot with a slightly thin, neutral line
                item = self.plot_widget.plot(
                    pts[:, 0], pts[:, 1],
                    pen=pg.mkPen('#5c637a', width=1.5, style=Qt.PenStyle.SolidLine)
                )
                self._curve_segment_items.append(item)

    # ═════════════════════════════════════════════════════════════════════
    # Mouse handlers
    # ═════════════════════════════════════════════════════════════════════

    def _on_mouse_clicked(self, event):
        if self._active_points is None or not self.split_scatter.isVisible():
            return
        btn = event.button()
        if btn != Qt.MouseButton.LeftButton and btn != 1:
            return
        pos = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
        x, y = pos.x(), pos.y()
        dists = np.sqrt((self._active_points[:, 0] - x) ** 2
                        + (self._active_points[:, 1] - y) ** 2)
        self.point_clicked.emit(int(np.argmin(dists)))

    def _on_mouse_moved(self, pos):
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mp = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            self.coord_label.setPos(mp.x(), mp.y())
            self.coord_label.setText(
                f"X: {mp.x():.4f}\nY: {mp.y():.4f}")
