from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QLinearGradient


# ── Dark-theme palette ────────────────────────────────────────────────────────
_CANVAS_BG = '#0c0d16'
_CANVAS_FG = '#6b738c'

_COL_SPLIT    = '#FF6E6E'   # red — split points
_COL_SELECTED = '#00E5FF'   # cyan — selected point
_COL_ACTIVE   = '#FFB347'   # orange — active segment
_COL_RESAMPLED = '#FF79C6'  # magenta — resampled result
_COL_PREVIEW  = '#FF8C42'   # orange — formula preview


class ColorBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(70)
        self.min_val = 0.0
        self.max_val = 0.0
        self.title_text = "Length"
        self.setStyleSheet("background-color: #0c0d16; color: #a0a8c0;")

    def set_range(self, min_val: float, max_val: float):
        self.min_val = min_val
        self.max_val = max_val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        painter.fillRect(rect, QColor("#0c0d16"))
        
        margin_top = 30
        margin_bottom = 20
        bar_width = 12
        bar_left = 10
        bar_height = rect.height() - margin_top - margin_bottom
        
        if bar_height <= 0:
            return
            
        gradient = QLinearGradient(QPointF(bar_left, rect.height() - margin_bottom),
                                    QPointF(bar_left, margin_top))
        gradient.setColorAt(0.0, QColor.fromHsvF(0.6666, 1.0, 1.0)) # blue
        gradient.setColorAt(0.5, QColor.fromHsvF(0.3333, 1.0, 1.0)) # green/yellow
        gradient.setColorAt(1.0, QColor.fromHsvF(0.0, 1.0, 1.0))    # red
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRect(bar_left, margin_top, bar_width, bar_height)
        
        painter.setPen(QColor("#a0a8c0"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        
        min_str = f"{self.min_val:.4g}"
        painter.drawText(bar_left + bar_width + 6, rect.height() - margin_bottom + 4, min_str)
        
        max_str = f"{self.max_val:.4g}"
        painter.drawText(bar_left + bar_width + 6, margin_top + 4, max_str)
        
        mid_val = 0.5 * (self.min_val + self.max_val)
        mid_str = f"{mid_val:.4g}"
        painter.drawText(bar_left + bar_width + 6, margin_top + bar_height // 2 + 4, mid_str)
        
        painter.drawText(8, 18, self.title_text)


class ColorCodedSegmentsItem(pg.GraphicsObject):
    def __init__(self):
        super().__init__()
        self.points = None
        self.pens = []
        self.show_symbols = True
        self.symbol_brushes = []
        self._bounds = None

    def setData(self, points, lengths, min_len, max_len, show_symbols, symbol_brushes):
        self.points = points
        self.show_symbols = show_symbols
        self.symbol_brushes = symbol_brushes
        
        self.pens = []
        if points is not None and len(points) >= 2:
            span = max_len - min_len
            for l in lengths:
                t = (l - min_len) / span if span > 1e-12 else 0.0
                t = max(0.0, min(1.0, t))
                color = QColor.fromHsvF((1.0 - t) * 0.6666, 1.0, 1.0)
                self.pens.append(pg.mkPen(color, width=2.5))
            
            x = points[:, 0]
            y = points[:, 1]
            self._bounds = QRectF(x.min(), y.min(), x.max() - x.min(), y.max() - y.min())
        else:
            self._bounds = None
            
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self):
        if self._bounds is None:
            return QRectF()
        return self._bounds

    def paint(self, painter, option, widget):
        if self.points is None or len(self.points) < 2:
            return
        
        for i in range(len(self.points) - 1):
            p0 = self.points[i]
            p1 = self.points[i + 1]
            painter.setPen(self.pens[i])
            painter.drawLine(QPointF(p0[0], p0[1]), QPointF(p1[0], p1[1]))
            
        if self.show_symbols and self.symbol_brushes:
            painter.setPen(pg.mkPen(None))
            for i, p in enumerate(self.points):
                if i < len(self.symbol_brushes):
                    painter.setBrush(self.symbol_brushes[i])
                    painter.drawEllipse(QPointF(p[0], p[1]), 3.0, 3.0)


class CanvasView(QWidget):
    """
    Shared interactive canvas that can display multiple geometry sessions
    simultaneously.  Only the ACTIVE session has editable markers
    (split points, selected point, active segment).
    """

    point_clicked = pyqtSignal(int)       # nearest vertex index in active session's points
    segment_clicked = pyqtSignal(float, float)  # canvas coords when in edge selection mode

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setAspectLocked(True)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        layout.addWidget(self.plot_widget)

        self.colorbar_widget = ColorBarWidget(self)
        self.colorbar_widget.setVisible(False)
        layout.addWidget(self.colorbar_widget)

        # ── Per-session geometry layers ───────────────────────────────────
        self._geometries: dict[int, pg.PlotDataItem] = {}   # sid → curve
        self._geo_colors: dict[int, str] = {}               # sid → color str
        self._curve_preview_items: dict[int, pg.PlotDataItem] = {}         # sid → preview curve
        self._curve_segment_items: dict[int, list[pg.PlotDataItem]] = {}   # sid → list of curves
        self._show_symbols = True
        self._show_nodes = True
        self._active_session_id: int | None = None

        # ── Selection mode ('vertex' or 'edge') ───────────────────────────
        self._selection_mode: str = 'vertex'

        # ── Multi-segment highlight overlays ──────────────────────────────
        self._multi_segment_curves: list[pg.PlotDataItem] = []

        # ── Active-session overlays (single set, reused across sessions) ──

        # Resampled output — magenta dashed
        self.resampled_curve = self.plot_widget.plot(
            pen=pg.mkPen(_COL_RESAMPLED, width=2, style=Qt.PenStyle.DashLine),
            symbol='o', symbolBrush=_COL_RESAMPLED, symbolSize=5)
        self.resampled_curve.setZValue(10)

        # Custom color-coded segments item for quality heatmap
        self.color_coded_segments = ColorCodedSegmentsItem()
        self.color_coded_segments.setZValue(9)
        self.plot_widget.addItem(self.color_coded_segments)

        # Active segment — thick orange with symbols
        self.active_segment_curve = self.plot_widget.plot(
            pen=pg.mkPen(_COL_ACTIVE, width=4),
            symbol='o', symbolBrush=_COL_ACTIVE, symbolSize=5)
        self.active_segment_curve.setZValue(20)

        # Split points — red dots
        self.split_scatter = pg.ScatterPlotItem(
            size=10, pen=pg.mkPen(None), brush=pg.mkBrush(_COL_SPLIT))
        self.split_scatter.setZValue(30)
        self.plot_widget.addItem(self.split_scatter)

        # Selected point — cyan hollow circle
        self.selected_scatter = pg.ScatterPlotItem(
            size=14, pen=pg.mkPen(_COL_SELECTED, width=2), brush=None)
        self.selected_scatter.setZValue(40)
        self.plot_widget.addItem(self.selected_scatter)

        # Quality bad nodes — red 'x'
        self.quality_bad_scatter = pg.ScatterPlotItem(
            size=10, symbol='x', pen=pg.mkPen('#FF5252', width=2), brush=None)
        self.quality_bad_scatter.setZValue(50)
        self.plot_widget.addItem(self.quality_bad_scatter)

        # Duplicate preview segment — dashed cyan curve
        self.duplicate_preview_curve = self.plot_widget.plot(
            pen=pg.mkPen('#00E5FF', width=2, style=Qt.PenStyle.DashLine),
            symbol='o' if self._show_symbols else None, symbolBrush='#00E5FF', symbolSize=4)
        self.duplicate_preview_curve.setZValue(15)

        # Mouse-coordinate label
        self.coord_label = pg.TextItem('', anchor=(-0.1, 1.1),
                                       color=_CANVAS_FG)
        self.plot_widget.addItem(self.coord_label, ignoreBounds=True)
        self.coord_label.setZValue(100)

        # ── Active-session points (for hit-testing) ───────────────────────
        self._active_points: np.ndarray | None = None

        # ── Mouse events ──────────────────────────────────────────────────
        self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Mouse-coordinate throttle timer
        self._mouse_timer = QTimer(self)
        self._mouse_timer.setSingleShot(True)
        self._mouse_timer.timeout.connect(self._throttled_mouse_update)
        self._last_mouse_pos = None

    # ═════════════════════════════════════════════════════════════════════
    # Multi-geometry management
    # ═════════════════════════════════════════════════════════════════════

    def add_geometry(self, session_id: int, points: np.ndarray | None,
                     color: str):
        """Add a new geometry layer for a session."""
        curve = self.plot_widget.plot(
            pen=pg.mkPen(color, width=2),
            symbol='o' if self._show_symbols else None,
            symbolBrush=pg.mkBrush(color), symbolSize=3)
        if points is not None and len(points) > 0:
            curve.setData(points[:, 0], points[:, 1])
        self._geometries[session_id] = curve
        self._geo_colors[session_id] = color

        # Initialize per-session curve preview and segment dictionaries
        preview_curve = self.plot_widget.plot(
            pen=pg.mkPen(_COL_PREVIEW, width=2, style=Qt.PenStyle.DashLine),
            symbol='o' if self._show_symbols else None, symbolBrush=_COL_PREVIEW, symbolSize=4)
        preview_curve.setZValue(5)
        self._curve_preview_items[session_id] = preview_curve
        self._curve_segment_items[session_id] = []

    def update_geometry(self, session_id: int, points: np.ndarray | None):
        """Update an existing geometry layer."""
        if session_id not in self._geometries:
            return
        if points is not None and len(points) > 0:
            self._geometries[session_id].setData(points[:, 0], points[:, 1])
        else:
            self._geometries[session_id].setData([], [])

    def update_geometry_color(self, session_id: int, color: str):
        """Update the display color of an existing geometry layer."""
        if session_id not in self._geometries:
            return
        self._geo_colors[session_id] = color
        curve = self._geometries[session_id]
        curve.setPen(pg.mkPen(color, width=2))
        curve.setSymbolBrush(pg.mkBrush(color))

    def remove_geometry(self, session_id: int):
        """Remove a session's geometry layer."""
        if session_id in self._geometries:
            self.plot_widget.removeItem(self._geometries.pop(session_id))
            self._geo_colors.pop(session_id, None)

        if session_id in self._curve_preview_items:
            self.plot_widget.removeItem(self._curve_preview_items.pop(session_id))

        if session_id in self._curve_segment_items:
            for item in self._curve_segment_items.pop(session_id):
                self.plot_widget.removeItem(item)

    def highlight_geometry(self, active_session_id: int):
        """
        Bold the active session's curve; mute all others.
        Active: width=2.5, full colour, symbol size=4.
        Inactive: width=1, 60 alpha (approx 23% opacity), symbol size=1.5.
        """
        self._active_session_id = active_session_id
        for sid, curve in self._geometries.items():
            color_str = self._geo_colors.get(sid, '#64B5F6')
            curve.setSymbol('o' if self._show_symbols else None)
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

        # Highlight/dim curve previews of each session
        has_resampled = False
        x_data, y_data = self.resampled_curve.getData()
        if x_data is not None and len(x_data) > 0:
            has_resampled = True

        for sid, preview_curve in self._curve_preview_items.items():
            is_active = (sid == active_session_id)
            if is_active and has_resampled:
                preview_curve.setSymbol(None)
            else:
                preview_curve.setSymbol('o' if self._show_symbols else None)

            if is_active:
                # Active preview: full color, dash pen
                preview_curve.setPen(pg.mkPen(_COL_PREVIEW, width=2, style=Qt.PenStyle.DashLine))
                preview_curve.setSymbolBrush(pg.mkBrush(_COL_PREVIEW))
                preview_curve.setSymbolSize(4)
            else:
                # Inactive preview: dim color
                c = QColor(_COL_PREVIEW)
                c.setAlpha(60)
                preview_curve.setPen(pg.mkPen(c, width=1, style=Qt.PenStyle.DashLine))
                preview_curve.setSymbolBrush(pg.mkBrush(c))
                preview_curve.setSymbolSize(1.5)

        # Highlight/dim deselected curve segments of each session
        for sid, items in self._curve_segment_items.items():
            if sid == active_session_id:
                for item in items:
                    item.setSymbol('o' if self._show_symbols else None)
                    item.setPen(pg.mkPen('#5c637a', width=1.5, style=Qt.PenStyle.SolidLine))
                    item.setSymbolBrush(pg.mkBrush('#5c637a'))
                    item.setSymbolSize(3)
            else:
                for item in items:
                    item.setSymbol('o' if self._show_symbols else None)
                    c = QColor('#5c637a')
                    c.setAlpha(60)
                    item.setPen(pg.mkPen(c, width=1, style=Qt.PenStyle.SolidLine))
                    item.setSymbolBrush(pg.mkBrush(c))
                    item.setSymbolSize(1.5)

    def set_active_geometry_dimmed(self, active_session_id: int, dimmed: bool):
        """Dim the active geometry's base line so the selected segment stands out."""
        if active_session_id in self._geometries:
            curve = self._geometries[active_session_id]
            color_str = self._geo_colors.get(active_session_id, '#64B5F6')
            curve.setSymbol('o' if self._show_symbols else None)
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

    def set_geometry_symbols_visible(self, visible: bool):
        """Toggle the visibility of symbols on all geometries."""
        self._show_symbols = visible
        for sid, curve in self._geometries.items():
            curve.setSymbol('o' if visible else None)
        
        self.active_segment_curve.setSymbol('o' if visible else None)
        self.duplicate_preview_curve.setSymbol('o' if visible else None)

        for sid, items in self._curve_segment_items.items():
            for item in items:
                item.setSymbol('o' if visible else None)

        has_resampled = False
        x_data, y_data = self.resampled_curve.getData()
        if x_data is not None and len(x_data) > 0:
            has_resampled = True

        for sid, preview_curve in self._curve_preview_items.items():
            is_active = (sid == self._active_session_id)
            if is_active and has_resampled:
                preview_curve.setSymbol(None)
            else:
                preview_curve.setSymbol('o' if visible else None)

    def set_resampled_nodes_visible(self, visible: bool):
        """Toggle the visibility of symbols representing resampled nodes."""
        self._show_nodes = visible
        self.resampled_curve.setSymbol('o' if visible else None)

    def set_geometry_visible(self, session_id: int, visible: bool):
        """Toggle the visibility of a specific geometry layer and its curve elements."""
        if session_id in self._geometries:
            self._geometries[session_id].setVisible(visible)
        if session_id in self._curve_preview_items:
            self._curve_preview_items[session_id].setVisible(visible)
        if session_id in self._curve_segment_items:
            for item in self._curve_segment_items[session_id]:
                item.setVisible(visible)

    def set_active_overlays_visible(self, visible: bool):
        """Toggle the visibility of the active session overlays."""
        self.resampled_curve.setVisible(visible)
        self.active_segment_curve.setVisible(visible)
        if self._active_session_id in self._curve_preview_items:
            self._curve_preview_items[self._active_session_id].setVisible(visible)
        self.split_scatter.setVisible(visible)
        self.selected_scatter.setVisible(visible)

    def fit_to_geometry(self, session_id: int):
        """Fit the view box to the points of a specific geometry layer or curve segments."""
        pts = []
        if session_id in self._geometries:
            curve = self._geometries[session_id]
            x_data, y_data = curve.getData()
            if x_data is not None and len(x_data) > 0:
                pts.append(np.column_stack([x_data, y_data]))
        if session_id in self._curve_preview_items:
            x_data, y_data = self._curve_preview_items[session_id].getData()
            if x_data is not None and len(x_data) > 0:
                pts.append(np.column_stack([x_data, y_data]))
        if session_id in self._curve_segment_items:
            for item in self._curve_segment_items[session_id]:
                x_data, y_data = item.getData()
                if x_data is not None and len(x_data) > 0:
                    pts.append(np.column_stack([x_data, y_data]))

        if pts:
            all_pts = np.vstack(pts)
            min_x, max_x = np.min(all_pts[:, 0]), np.max(all_pts[:, 0])
            min_y, max_y = np.min(all_pts[:, 1]), np.max(all_pts[:, 1])
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

    def set_selection_mode(self, mode: str):
        """Set the canvas click selection mode: 'vertex' or 'edge'."""
        self._selection_mode = mode

    def update_active_segment(self, start_idx: int | None,
                               end_idx: int | None):
        if (self._active_points is not None
                and start_idx is not None and end_idx is not None
                and start_idx <= end_idx):
            sp = self._active_points[start_idx:end_idx + 1]
            self.active_segment_curve.setData(sp[:, 0], sp[:, 1])
        else:
            self.active_segment_curve.setData([], [])

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
                pen=pg.mkPen(color, width=width),
                symbol='o', symbolBrush=pg.mkBrush(color), symbolSize=5 if is_primary else 4
            )
            item.setZValue(zval)
            self._multi_segment_curves.append(item)

        # Clear the single active_segment_curve to avoid double drawing
        self.active_segment_curve.setData([], [])

    def load_resampled_data(self, points: np.ndarray | None, show_quality: bool = False):
        if points is not None and len(points) > 0:
            if show_quality and len(points) >= 2:
                diffs = np.diff(points, axis=0)
                ds = np.sqrt(np.sum(diffs**2, axis=1))
                ds[ds < 1e-12] = 1e-12
                
                min_len = np.min(ds)
                max_len = np.max(ds)
                self.colorbar_widget.set_range(min_len, max_len)
                self.colorbar_widget.setVisible(True)
                
                self.color_coded_segments.setData(points, ds, min_len, max_len, False, [])
                self.resampled_curve.setData(points[:, 0], points[:, 1], pen=None, symbol=None)
                self.quality_bad_scatter.clear()
            else:
                self.colorbar_widget.setVisible(False)
                self.color_coded_segments.setData(None, None, 0, 0, False, [])
                
                sym = 'o' if self._show_nodes else None
                self.resampled_curve.setData(
                    points[:, 0], points[:, 1],
                    pen=pg.mkPen(_COL_RESAMPLED, width=2, style=Qt.PenStyle.DashLine),
                    symbol=sym, symbolBrush=pg.mkBrush(_COL_RESAMPLED)
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
        """Update the duplicate preview curve with transformed points."""
        if points is not None and len(points) > 0:
            sym = 'o' if self._show_symbols else None
            self.duplicate_preview_curve.setData(points[:, 0], points[:, 1], symbol=sym)
        else:
            self.duplicate_preview_curve.setData([], [])

    def clear_duplicate_preview(self):
        """Clear the duplicate preview curve."""
        self.duplicate_preview_curve.setData([], [])

    def update_curve_segments(self, session_id: int, segments_pts: list[np.ndarray]):
        """Clear and redraw all curve segments to keep them visible when deselected."""
        if session_id not in self._curve_segment_items:
            self._curve_segment_items[session_id] = []

        # Remove existing items for this session from the plot
        for item in self._curve_segment_items[session_id]:
            self.plot_widget.removeItem(item)
        self._curve_segment_items[session_id].clear()

        # Determine styling depending on if this session is the active one
        is_active = (session_id == self._active_session_id)

        # Add new items
        for pts in segments_pts:
            if pts is not None and len(pts) > 0:
                if is_active:
                    pen = pg.mkPen('#5c637a', width=1.5, style=Qt.PenStyle.SolidLine)
                    symbol_brush = pg.mkBrush('#5c637a')
                    symbol_size = 3
                else:
                    c = QColor('#5c637a')
                    c.setAlpha(60)
                    pen = pg.mkPen(c, width=1, style=Qt.PenStyle.SolidLine)
                    symbol_brush = pg.mkBrush(c)
                    symbol_size = 1.5

                item = self.plot_widget.plot(
                    pts[:, 0], pts[:, 1],
                    pen=pen,
                    symbol='o' if self._show_symbols else None, symbolBrush=symbol_brush, symbolSize=symbol_size
                )
                item.setZValue(5)
                self._curve_segment_items[session_id].append(item)

    # ═════════════════════════════════════════════════════════════════════
    # Mouse handlers
    # ═════════════════════════════════════════════════════════════════════

    def _on_mouse_clicked(self, event):
        if self._active_session_id is None or self._active_points is None:
            return
        btn = event.button()
        if btn != Qt.MouseButton.LeftButton:
            return
        pos = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
        x, y = pos.x(), pos.y()

        if self._selection_mode == 'edge':
            # In edge mode: emit segment_clicked with canvas coordinates
            # (segment resolution is done in the controller via point proximity)
            self.segment_clicked.emit(x, y)
            return

        # Vertex mode (default): find nearest point and emit point_clicked
        dists = np.sqrt((self._active_points[:, 0] - x) ** 2
                        + (self._active_points[:, 1] - y) ** 2)
        nearest_idx = int(np.argmin(dists))
        
        # Convert scene pos to pixel distance
        vb = self.plot_widget.plotItem.vb
        nearest_pt = self._active_points[nearest_idx]
        p1 = event.scenePos()
        p2 = vb.mapViewToScene(pg.Point(nearest_pt[0], nearest_pt[1]))
        pixel_dist = ((p1.x() - p2.x())**2 + (p1.y() - p2.y())**2)**0.5
        if pixel_dist < 30:  # 30 pixel threshold
            self.point_clicked.emit(nearest_idx)

    def _on_mouse_moved(self, pos):
        self._last_mouse_pos = pos
        if not self._mouse_timer.isActive():
            self._mouse_timer.start(16)

    def _throttled_mouse_update(self):
        pos = self._last_mouse_pos
        if pos is not None and self.plot_widget.sceneBoundingRect().contains(pos):
            mp = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            self.coord_label.setPos(mp.x(), mp.y())
            self.coord_label.setText(f"X: {mp.x():.4f}\nY: {mp.y():.4f}")
