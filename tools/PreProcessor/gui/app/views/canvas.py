from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QPainterPath


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
        self.quality_mode = "length"
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
        if self.quality_mode == "ratio":
            gradient.setColorAt(0.0, QColor.fromHsvF(0.6666, 1.0, 1.0)) # blue (small ratio)
            gradient.setColorAt(0.5, QColor.fromHsvF(0.3333, 1.0, 1.0)) # green/yellow
            gradient.setColorAt(1.0, QColor.fromHsvF(0.0, 1.0, 1.0))    # red (large ratio)
        else:
            gradient.setColorAt(0.0, QColor.fromHsvF(0.0, 1.0, 1.0))    # red (small distance)
            gradient.setColorAt(0.5, QColor.fromHsvF(0.3333, 1.0, 1.0)) # green/yellow
            gradient.setColorAt(1.0, QColor.fromHsvF(0.6666, 1.0, 1.0)) # blue (large distance)
        
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
        self.gap_indices = set()

    def setData(self, points, lengths, min_len, max_len, show_symbols, symbol_brushes, quality_mode='length', gap_indices=None):
        self.points = points
        self.show_symbols = show_symbols
        self.symbol_brushes = symbol_brushes
        self.gap_indices = gap_indices if gap_indices is not None else set()
        
        self.pens = []
        if points is not None and len(points) >= 2:
            span = max_len - min_len
            for l in lengths:
                t = (l - min_len) / span if span > 1e-12 else 0.0
                t = max(0.0, min(1.0, t))
                if quality_mode == 'ratio':
                    color = QColor.fromHsvF((1.0 - t) * 0.6666, 1.0, 1.0)
                else:
                    color = QColor.fromHsvF(t * 0.6666, 1.0, 1.0)
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

        pts = self.points
        n = len(pts)
        gap_indices = getattr(self, 'gap_indices', set())

        # Viewport culling: restrict drawing to the exposed rect (item coords)
        # with a small margin, so pan/zoom stays fast on large datasets instead
        # of redrawing every off-screen segment each frame.
        clip = getattr(option, "exposedRect", None)
        if clip is not None and clip.isValid() and clip.width() > 0:
            m = max(clip.width(), clip.height()) * 0.05 + 1e-12
            cx0, cy0 = clip.left() - m, clip.top() - m
            cx1, cy1 = clip.right() + m, clip.bottom() + m
        else:
            cx0 = cy0 = -1e308
            cx1 = cy1 = 1e308

        # Batch consecutive segments sharing a colour into one QPainterPath so
        # we issue far fewer setPen/draw calls than one drawLine per segment.
        npens = len(self.pens)
        path = None
        cur_pen = None
        cur_key = None

        def flush():
            nonlocal path, cur_pen, cur_key
            if path is not None and cur_pen is not None:
                painter.setPen(cur_pen)
                painter.drawPath(path)
            path = None
            cur_pen = None
            cur_key = None

        for i in range(n - 1):
            if i in gap_indices or i >= npens:
                flush()
                continue
            ax, ay = pts[i][0], pts[i][1]
            bx, by = pts[i + 1][0], pts[i + 1][1]
            if (max(ax, bx) < cx0 or min(ax, bx) > cx1
                    or max(ay, by) < cy0 or min(ay, by) > cy1):
                flush()
                continue
            pen = self.pens[i]
            key = pen.color().rgba()
            if key != cur_key:
                flush()
                cur_key = key
                cur_pen = pen
                path = QPainterPath()
                path.moveTo(ax, ay)
                path.lineTo(bx, by)
            else:
                # Segments are contiguous (share pts[i]); extend the polyline.
                path.lineTo(bx, by)
        flush()

        if self.show_symbols and self.symbol_brushes:
            painter.setPen(pg.mkPen(None))
            nb = len(self.symbol_brushes)
            for i in range(min(n, nb)):
                px, py = pts[i][0], pts[i][1]
                if px < cx0 or px > cx1 or py < cy0 or py > cy1:
                    continue
                painter.setBrush(self.symbol_brushes[i])
                painter.drawEllipse(QPointF(px, py), 3.0, 3.0)


class SelectableViewBox(pg.ViewBox):
    """ViewBox with rubber-band box ("圈選") selection.

    A plain left-drag still pans (pyqtgraph default).  Holding a modifier
    while left-dragging draws a selection rectangle; on release the
    data-space rect is reported via ``box_select_cb``:
      • Shift+drag      → replace the current selection with the box contents
      • Ctrl/Cmd+drag   → add the box contents to the current selection
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.box_select_cb = None   # fn(x0, y0, x1, y1, extend: bool)
        self.box_enabled = False    # only active in edge selection mode

    def mouseDragEvent(self, ev, axis=None):
        mods = ev.modifiers()
        is_box = (
            self.box_enabled
            and ev.button() == Qt.MouseButton.LeftButton
            and axis is None
            and bool(mods & (Qt.KeyboardModifier.ShiftModifier
                             | Qt.KeyboardModifier.ControlModifier
                             | Qt.KeyboardModifier.MetaModifier))
        )
        if not is_box:
            super().mouseDragEvent(ev, axis=axis)
            return

        ev.accept()
        p1, p2 = ev.buttonDownPos(), ev.pos()
        if ev.isFinish():
            self.rbScaleBox.hide()
            rect = self.childGroup.mapRectFromParent(QRectF(p1, p2))
            extend = bool(mods & (Qt.KeyboardModifier.ControlModifier
                                  | Qt.KeyboardModifier.MetaModifier))
            if self.box_select_cb is not None:
                self.box_select_cb(rect.left(), rect.top(),
                                   rect.right(), rect.bottom(), extend)
        else:
            self.updateScaleBox(p1, p2)


class CanvasView(QWidget):
    """
    Shared interactive canvas that can display multiple geometry sessions
    simultaneously.  Only the ACTIVE session has editable markers
    (split points, selected point, active segment).
    """

    point_clicked = pyqtSignal(int)       # nearest vertex index in active session's points
    point_deselected = pyqtSignal()        # emitted when clicking far from all vertices (deselect)
    segment_clicked = pyqtSignal(float, float, bool)  # (x, y, extend_selection)
    segment_double_clicked = pyqtSignal(float, float)  # (x, y) — open numeric editor
    box_selected = pyqtSignal(float, float, float, float, bool)  # (x0, y0, x1, y1, extend)
    shape_drawn = pyqtSignal(str, object)  # (tool, [(x, y), ...]) — interactive draw finished


    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._select_vb = SelectableViewBox()
        self._select_vb.box_select_cb = self._emit_box_selected
        self.plot_widget = pg.PlotWidget(viewBox=self._select_vb)
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
        self._selection_mode: str = 'edge'

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

        # Active segment — thick orange without symbols
        self.active_segment_curve = self.plot_widget.plot(
            pen=pg.mkPen(_COL_ACTIVE, width=4))
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

        # ── Draggable transform base-point / axis handles ─────────────────
        # Populated on demand by show_transform_handles(); the controller sets
        # transform_handle_cb to receive live drag updates.
        self.transform_handle_cb = None      # fn(kind:str, x:float, y:float)
        self._transform_items: list = []     # pg items currently shown
        self._suppress_handle_cb = False     # guard programmatic setPos
        self._axis_pivot_item = None
        self._axis_dir_item = None
        self._axis_line_item = None
        self._axis_offset = (1.0, 0.0)       # dir-handle offset from pivot
        self._translate_anchor = None        # source anchor for translate
        self._translate_guide = None         # anchor → destination guide line
        self._rot_pivot_item = None          # rotate gizmo: pivot handle
        self._rot_angle_item = None          # rotate gizmo: angle handle
        self._rot_line_item = None           # rotate gizmo: pivot → angle line
        self._rot_radius = 1.0               # rotate gizmo: angle-handle radius

        # ── Editable control-point handles for the selected analytic edge ──
        # The controller sets edge_handle_cb to receive live drag updates and
        # provides each handle's opaque id so it can map the drag back to the
        # right spin box / vertex.
        self.edge_handle_cb = None           # fn(handle_id:str, x:float, y:float, finished:bool)
        self._edge_handle_items: list = []
        self._suppress_edge_cb = False

        # Endpoint markers — always-on highlight of every edge's endpoints so
        # the user can clearly see where points are (and the snap targets).
        # White rings, distinct from the cyan edit handles and amber transform
        # pivot so they never read as one of those.
        self._endpoint_markers = pg.ScatterPlotItem(
            size=11, symbol='o', pen=pg.mkPen('#FFFFFF', width=1.6),
            brush=pg.mkBrush(12, 13, 22, 200))
        self._endpoint_markers.setZValue(35)
        self.plot_widget.addItem(self._endpoint_markers)

        # Open / unstitched endpoints — red rings warning the boundary is not
        # closed (or two pieces nearly meet). Drawn above the white markers.
        self._open_endpoint_markers = pg.ScatterPlotItem(
            size=15, symbol='o', pen=pg.mkPen('#FF5252', width=2.4),
            brush=pg.mkBrush(255, 82, 82, 70))
        self._open_endpoint_markers.setZValue(36)
        self.plot_widget.addItem(self._open_endpoint_markers)

        # ── Interactive shape-drawing state ───────────────────────────────
        self._draw_tool: str | None = None   # 'line'|'circle'|'rectangle'|'triangle'|'polygon'
        self._draw_pts: list[tuple[float, float]] = []
        self._draw_handle_items: list = []   # draggable control points while drawing
        # Optional snap function (set by the controller): maps a clicked/cursor
        # (x, y) to a nearby edge endpoint so placement clicks snap too.
        self.snap_cb = None                  # fn(x, y) -> (x, y)
        self._draw_preview = self.plot_widget.plot(
            pen=pg.mkPen('#7CFC9A', width=2, style=Qt.PenStyle.DashLine),
            symbol='o', symbolBrush='#7CFC9A', symbolSize=6)
        self._draw_preview.setZValue(210)
        self._draw_hint = pg.TextItem('', anchor=(0, 1), color='#7CFC9A')
        self._draw_hint.setZValue(211)
        self.plot_widget.addItem(self._draw_hint, ignoreBounds=True)
        self._draw_hint.setVisible(False)

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
        """Toggle the visibility of the active session overlays.

        Mode-specific overlays also respect the current selection mode, so
        loading/refreshing in Edge mode does not resurrect the vertex markers
        (and vice-versa)."""
        is_vertex = (self._selection_mode == 'vertex')
        is_edge = (self._selection_mode == 'edge')
        self.resampled_curve.setVisible(visible)
        if self._active_session_id in self._curve_preview_items:
            self._curve_preview_items[self._active_session_id].setVisible(visible)
        self.active_segment_curve.setVisible(visible and is_edge)
        self.split_scatter.setVisible(visible and is_vertex)
        self.selected_scatter.setVisible(visible and is_vertex)

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

    def fit_to_points(self, pts: np.ndarray | None):
        """Fit the view to an arbitrary (N, 2) point array (e.g. a live preview)."""
        if pts is None or len(pts) == 0:
            return
        pts = np.asarray(pts, dtype=float)
        minx, maxx = float(pts[:, 0].min()), float(pts[:, 0].max())
        miny, maxy = float(pts[:, 1].min()), float(pts[:, 1].max())
        dx = (maxx - minx) or 1.0
        dy = (maxy - miny) or 1.0
        self.plot_widget.plotItem.vb.setRange(
            xRange=[minx - 0.1 * dx, maxx + 0.1 * dx],
            yRange=[miny - 0.1 * dy, maxy + 0.1 * dy])

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
        # Only show in vertex mode
        self.split_scatter.setVisible(self._selection_mode == 'vertex')

    def update_selected_point(self, idx: int | None):
        if self._active_points is not None and idx is not None:
            pt = self._active_points[idx]
            self.selected_scatter.setData([pt[0]], [pt[1]])
        else:
            self.selected_scatter.clear()
        # Only show in vertex mode
        self.selected_scatter.setVisible(self._selection_mode == 'vertex')

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
                self.resampled_curve.setData(points[:, 0], points[:, 1], pen=None, symbol=None)
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

    # ── Transform base-point / axis handles ───────────────────────────────
    _HANDLE_COL = '#FFD54A'   # amber

    def _emit_handle(self, kind: str, x: float, y: float):
        if self._suppress_handle_cb:
            return
        if self.transform_handle_cb is not None:
            self.transform_handle_cb(kind, float(x), float(y))

    def clear_transform_handles(self):
        """Remove any draggable base-point / axis handles from the canvas."""
        for it in self._transform_items:
            self.plot_widget.removeItem(it)
        self._transform_items = []
        self._axis_pivot_item = None
        self._axis_dir_item = None
        self._axis_line_item = None
        self._translate_anchor = None
        self._translate_guide = None
        self._rot_pivot_item = None
        self._rot_angle_item = None
        self._rot_line_item = None

    def _view_handle_len(self) -> float:
        """A reasonable on-screen length (data units) for the axis dir handle."""
        try:
            (x0, x1), (y0, y1) = self.plot_widget.getViewBox().viewRange()
            return 0.15 * max(abs(x1 - x0), abs(y1 - y0), 1e-9)
        except Exception:
            return 1.0

    def show_transform_handles(self, spec: dict):
        """Show draggable base-point / line handle(s) for the active transform.

        ``spec`` is one of:
          {'point': (x, y)}                       — pivot / centre marker
          {'rotate': {'pivot': (x, y), 'angle': deg}} — rotate pivot + angle handle
          {'hline': y}                            — horizontal mirror axis
          {'vline': x}                            — vertical mirror axis
          {'axis': {'pivot': (x, y), 'dir': (dx, dy)}} — arbitrary mirror axis
          {'translate': {'anchor': (ax, ay), 'dest': (x, y)}} — move-to handle
        Drags are reported through ``transform_handle_cb(kind, x, y)`` with
        kind in {'point', 'hline', 'vline', 'axis_pivot', 'axis_dir',
        'translate'}.
        """
        self.clear_transform_handles()
        self._suppress_handle_cb = True
        try:
            col = self._HANDLE_COL
            if 'point' in spec:
                x, y = spec['point']
                t = pg.TargetItem(
                    pos=(x, y), size=16, movable=True,
                    pen=pg.mkPen(col, width=2),
                    brush=pg.mkBrush(0, 0, 0, 0),
                    hoverBrush=pg.mkBrush(col))
                t.setZValue(200)
                t.sigPositionChanged.connect(
                    lambda it: self._emit_handle('point', it.pos().x(), it.pos().y()))
                self.plot_widget.addItem(t)
                self._transform_items.append(t)
            elif 'hline' in spec:
                ln = pg.InfiniteLine(
                    pos=spec['hline'], angle=0, movable=True,
                    pen=pg.mkPen(col, width=2, style=Qt.PenStyle.DashLine),
                    hoverPen=pg.mkPen(col, width=3))
                ln.setZValue(200)
                ln.sigPositionChanged.connect(
                    lambda it: self._emit_handle('hline', 0.0, it.value()))
                self.plot_widget.addItem(ln)
                self._transform_items.append(ln)
            elif 'vline' in spec:
                ln = pg.InfiniteLine(
                    pos=spec['vline'], angle=90, movable=True,
                    pen=pg.mkPen(col, width=2, style=Qt.PenStyle.DashLine),
                    hoverPen=pg.mkPen(col, width=3))
                ln.setZValue(200)
                ln.sigPositionChanged.connect(
                    lambda it: self._emit_handle('vline', it.value(), 0.0))
                self.plot_widget.addItem(ln)
                self._transform_items.append(ln)
            elif 'rotate' in spec:
                self._build_rotate_handles(spec['rotate'])
            elif 'axis' in spec:
                self._build_axis_handles(spec['axis'])
            elif 'translate' in spec:
                self._build_translate_handles(spec['translate'])
        finally:
            self._suppress_handle_cb = False

    def _build_rotate_handles(self, rot: dict):
        """Rotate gizmo: a pivot handle plus an angle handle on a ring around
        the pivot.  Dragging the angle handle reports the absolute clock-hand
        angle (degrees) via the 'rotate_angle' kind; dragging the pivot reports
        'point' (so it shares the pivot-update path with the other transforms)."""
        import math
        col = self._HANDLE_COL
        px, py = rot.get('pivot', (0.0, 0.0))
        ang = math.radians(rot.get('angle', 0.0))
        L = self._view_handle_len()
        self._rot_radius = L
        hx, hy = px + L * math.cos(ang), py + L * math.sin(ang)

        line = self.plot_widget.plot(
            [px, hx], [py, hy],
            pen=pg.mkPen(col, width=1.5, style=Qt.PenStyle.DashLine))
        line.setZValue(199)
        pivot = pg.TargetItem(
            pos=(px, py), size=16, movable=True,
            pen=pg.mkPen(col, width=2), brush=pg.mkBrush(0, 0, 0, 0),
            hoverBrush=pg.mkBrush(col))
        pivot.setZValue(201)
        angle = pg.TargetItem(
            pos=(hx, hy), size=13, movable=True, symbol='o',
            pen=pg.mkPen(col, width=2), brush=pg.mkBrush(0, 0, 0, 0),
            hoverBrush=pg.mkBrush(col))
        angle.setZValue(201)

        pivot.sigPositionChanged.connect(self._on_rot_pivot_moved)
        angle.sigPositionChanged.connect(self._on_rot_angle_moved)

        # `line` was already added by plot_widget.plot(); only the handles need it.
        self.plot_widget.addItem(pivot)
        self.plot_widget.addItem(angle)
        for it in (line, pivot, angle):
            self._transform_items.append(it)
        self._rot_line_item = line
        self._rot_pivot_item = pivot
        self._rot_angle_item = angle

    def _on_rot_pivot_moved(self, it):
        import math
        if self._suppress_handle_cb or self._rot_pivot_item is None:
            return
        px, py = it.pos().x(), it.pos().y()
        # Keep the angle handle on its ring relative to the new pivot.
        self._suppress_handle_cb = True
        try:
            if self._rot_angle_item is not None:
                hx, hy = self._rot_angle_item.pos().x(), self._rot_angle_item.pos().y()
                ang = math.atan2(hy - py, hx - px)
                ax, ay = px + self._rot_radius * math.cos(ang), py + self._rot_radius * math.sin(ang)
                self._rot_angle_item.setPos((ax, ay))
                if self._rot_line_item is not None:
                    self._rot_line_item.setData([px, ax], [py, ay])
        finally:
            self._suppress_handle_cb = False
        self._emit_handle('point', px, py)

    def _on_rot_angle_moved(self, it):
        import math
        if self._suppress_handle_cb or self._rot_pivot_item is None:
            return
        px, py = self._rot_pivot_item.pos().x(), self._rot_pivot_item.pos().y()
        hx, hy = it.pos().x(), it.pos().y()
        ang = math.atan2(hy - py, hx - px)
        # Snap the handle back onto the fixed ring so it reads purely as an angle.
        ax, ay = px + self._rot_radius * math.cos(ang), py + self._rot_radius * math.sin(ang)
        self._suppress_handle_cb = True
        try:
            it.setPos((ax, ay))
            if self._rot_line_item is not None:
                self._rot_line_item.setData([px, ax], [py, ay])
        finally:
            self._suppress_handle_cb = False
        self._emit_handle('rotate_angle', math.degrees(ang), 0.0)

    def _build_axis_handles(self, axis: dict):
        import math
        col = self._HANDLE_COL
        px, py = axis.get('pivot', (0.0, 0.0))
        dx, dy = axis.get('dir', (1.0, 0.0))
        n = math.hypot(dx, dy)
        if n < 1e-12:
            dx, dy, n = 1.0, 0.0, 1.0
        L = self._view_handle_len()
        ox, oy = dx / n * L, dy / n * L
        self._axis_offset = (ox, oy)

        line = pg.InfiniteLine(
            pos=(px, py), angle=math.degrees(math.atan2(dy, dx)), movable=False,
            pen=pg.mkPen(col, width=2, style=Qt.PenStyle.DashLine))
        line.setZValue(199)
        pivot = pg.TargetItem(
            pos=(px, py), size=16, movable=True,
            pen=pg.mkPen(col, width=2), brush=pg.mkBrush(0, 0, 0, 0),
            hoverBrush=pg.mkBrush(col))
        pivot.setZValue(201)
        dirh = pg.TargetItem(
            pos=(px + ox, py + oy), size=12, movable=True, symbol='o',
            pen=pg.mkPen(col, width=2), brush=pg.mkBrush(0, 0, 0, 0),
            hoverBrush=pg.mkBrush(col))
        dirh.setZValue(201)

        pivot.sigPositionChanged.connect(self._on_axis_pivot_moved)
        dirh.sigPositionChanged.connect(self._on_axis_dir_moved)

        for it in (line, pivot, dirh):
            self.plot_widget.addItem(it)
            self._transform_items.append(it)
        self._axis_line_item = line
        self._axis_pivot_item = pivot
        self._axis_dir_item = dirh

    def _on_axis_pivot_moved(self, it):
        if self._suppress_handle_cb or self._axis_pivot_item is None:
            return
        px, py = it.pos().x(), it.pos().y()
        ox, oy = self._axis_offset
        self._suppress_handle_cb = True
        try:
            if self._axis_dir_item is not None:
                self._axis_dir_item.setPos((px + ox, py + oy))
            if self._axis_line_item is not None:
                self._axis_line_item.setPos((px, py))
        finally:
            self._suppress_handle_cb = False
        self._emit_handle('axis_pivot', px, py)

    def _on_axis_dir_moved(self, it):
        import math
        if self._suppress_handle_cb or self._axis_pivot_item is None:
            return
        px, py = self._axis_pivot_item.pos().x(), self._axis_pivot_item.pos().y()
        hx, hy = it.pos().x(), it.pos().y()
        ox, oy = hx - px, hy - py
        if math.hypot(ox, oy) < 1e-12:
            return
        self._axis_offset = (ox, oy)
        self._suppress_handle_cb = True
        try:
            if self._axis_line_item is not None:
                self._axis_line_item.setAngle(math.degrees(math.atan2(oy, ox)))
        finally:
            self._suppress_handle_cb = False
        # Report the direction vector (handle - pivot) directly.
        self._emit_handle('axis_dir', ox, oy)

    def _build_translate_handles(self, tr: dict):
        col = self._HANDLE_COL
        ax, ay = tr.get('anchor', (0.0, 0.0))
        dx, dy = tr.get('dest', (ax, ay))

        # Translation vector guide: source anchor → destination.
        guide = self.plot_widget.plot(
            [ax, dx], [ay, dy],
            pen=pg.mkPen(col, width=1.5, style=Qt.PenStyle.DashLine))
        guide.setZValue(199)
        # Source anchor marker (fixed).
        anchor = pg.ScatterPlotItem(
            [ax], [ay], size=11, symbol='+',
            pen=pg.mkPen(col, width=2), brush=pg.mkBrush(0, 0, 0, 0))
        anchor.setZValue(200)
        # Destination handle (draggable) — drag to place the geometry centre.
        dest = pg.TargetItem(
            pos=(dx, dy), size=16, movable=True,
            pen=pg.mkPen(col, width=2), brush=pg.mkBrush(0, 0, 0, 0),
            hoverBrush=pg.mkBrush(col))
        dest.setZValue(201)

        self._translate_anchor = (ax, ay)
        self._translate_guide = guide
        dest.sigPositionChanged.connect(self._on_translate_dest_moved)

        self.plot_widget.addItem(anchor)
        self.plot_widget.addItem(dest)
        self._transform_items += [guide, anchor, dest]

    def _on_translate_dest_moved(self, it):
        if self._suppress_handle_cb or self._translate_anchor is None:
            return
        hx, hy = it.pos().x(), it.pos().y()
        ax, ay = self._translate_anchor
        self._suppress_handle_cb = True
        try:
            if self._translate_guide is not None:
                self._translate_guide.setData([ax, hx], [ay, hy])
        finally:
            self._suppress_handle_cb = False
        self._emit_handle('translate', hx, hy)

    # ── Editable control-point handles for the selected analytic edge ──────

    def clear_edge_handles(self):
        """Remove the draggable control-point handles of the selected edge."""
        for it in self._edge_handle_items:
            self.plot_widget.removeItem(it)
        self._edge_handle_items = []

    def show_endpoint_markers(self, points):
        """Highlight a set of (x, y) endpoints (e.g. snap targets) clearly."""
        if points:
            pts = np.asarray(points, dtype=float)
            self._endpoint_markers.setData(pts[:, 0], pts[:, 1])
        else:
            self._endpoint_markers.clear()

    def clear_endpoint_markers(self):
        self._endpoint_markers.clear()

    def show_open_endpoint_markers(self, points):
        """Highlight open / unstitched endpoints (red) so the user can see the
        boundary is not closed. ``points`` is a list/array of (x, y)."""
        if points is not None and len(points) > 0:
            pts = np.asarray(points, dtype=float)
            self._open_endpoint_markers.setData(pts[:, 0], pts[:, 1])
        else:
            self._open_endpoint_markers.clear()

    def clear_open_endpoint_markers(self):
        self._open_endpoint_markers.clear()

    def show_edge_handles(self, handles: list[dict]):
        """Show draggable control points for the selected analytic edge.

        ``handles`` is a list of ``{'id': str, 'pos': (x, y)}``.  Each drag is
        reported through ``edge_handle_cb(handle_id, x, y, finished)`` so the
        controller can push the new coordinate into the matching spin box /
        polygon vertex.  Passing an empty list just clears the handles."""
        self.clear_edge_handles()
        if not handles:
            return
        col = '#00E5FF'
        self._suppress_edge_cb = True
        try:
            for h in handles:
                hid = h['id']
                x, y = h['pos']
                # Bigger, brighter handle with a solid centre dot so the
                # endpoint is unmistakable on the canvas. ``symbol``/``size``
                # let callers distinguish e.g. a move handle from endpoints.
                kwargs = dict(
                    pos=(x, y), size=h.get('size', 18), movable=True,
                    pen=pg.mkPen(col, width=3),
                    brush=pg.mkBrush(0, 229, 255, 90),
                    hoverBrush=pg.mkBrush(col))
                if 'symbol' in h:
                    kwargs['symbol'] = h['symbol']
                t = pg.TargetItem(**kwargs)
                t.setZValue(206)
                t.sigPositionChanged.connect(
                    lambda it, _id=hid: self._emit_edge_handle(_id, it, False))
                t.sigPositionChangeFinished.connect(
                    lambda it, _id=hid: self._emit_edge_handle(_id, it, True))
                self.plot_widget.addItem(t)
                self._edge_handle_items.append(t)
        finally:
            self._suppress_edge_cb = False

    def _emit_edge_handle(self, handle_id: str, it, finished: bool):
        if self._suppress_edge_cb:
            return
        if self.edge_handle_cb is not None:
            self.edge_handle_cb(handle_id, float(it.pos().x()),
                                float(it.pos().y()), finished)

    # ── Interactive shape drawing ──────────────────────────────────────────

    # Number of points each tool collects (None = variable, finished by a
    # double-click — used for the free polygon tool).
    _DRAW_NPTS = {'line': 2, 'circle': 2, 'rectangle': 2, 'triangle': 3,
                  'polygon': None}

    def start_draw_mode(self, tool: str):
        """Enter interactive shape-drawing mode for ``tool``.  Clicks place the
        defining points (each becomes a draggable control point) with a live
        rubber-band preview; once the shape is complete the canvas emits
        ``shape_drawn`` (the controller then opens the numeric dialog).  The
        initial prompt is centred in the current view so it is always visible."""
        self.clear_draw_artifacts()
        self._draw_tool = tool
        self._draw_pts = []
        self._draw_hint.setVisible(True)
        # Centre the prompt in the current view so the user sees where to click.
        try:
            (x0, x1), (y0, y1) = self.plot_widget.getViewBox().viewRange()
            self._draw_hint.setAnchor((0.5, 0.5))
            self._draw_hint.setPos(0.5 * (x0 + x1), 0.5 * (y0 + y1))
        except Exception:
            pass
        self._draw_hint.setText(self._draw_hint_text())
        try:
            self.plot_widget.setCursor(Qt.CursorShape.CrossCursor)
        except Exception:
            pass

    def cancel_draw_mode(self):
        """Abort drawing entirely (e.g. right-click) and remove all artifacts."""
        self.clear_draw_artifacts()

    def clear_draw_artifacts(self):
        """Remove the draw control points, rubber-band preview and prompt, and
        leave draw mode.  Called by the controller once the add is committed or
        cancelled so the control points only show *before* the edge completes."""
        self._draw_tool = None
        self._draw_pts = []
        for it in self._draw_handle_items:
            self.plot_widget.removeItem(it)
        self._draw_handle_items = []
        self._draw_preview.setData([], [])
        self._draw_hint.setVisible(False)
        try:
            self.plot_widget.unsetCursor()
        except Exception:
            pass

    def is_drawing(self) -> bool:
        return self._draw_tool is not None

    def _draw_hint_text(self) -> str:
        tool = self._draw_tool
        n = len(self._draw_pts)
        if tool == 'line':
            return "Click start point" if n == 0 else "Click end point"
        if tool == 'circle':
            return "Click centre" if n == 0 else "Click to set the radius"
        if tool == 'rectangle':
            return "Click a corner" if n == 0 else "Click the opposite corner"
        if tool == 'triangle':
            return f"Click point {n + 1} of 3"
        if tool == 'polygon':
            return ("Click to add vertices — double-click to finish"
                    if n < 3 else
                    f"{n} vertices — double-click to finish")
        return "Click to place the start point"

    def _add_draw_point(self, x: float, y: float):
        """Append a placed point and give it a draggable control-point handle."""
        i = len(self._draw_pts)
        self._draw_pts.append((x, y))
        col = '#7CFC9A'
        t = pg.TargetItem(
            pos=(x, y), size=12, movable=True,
            pen=pg.mkPen(col, width=2), brush=pg.mkBrush(0, 0, 0, 0),
            hoverBrush=pg.mkBrush(col))
        t.setZValue(212)
        t.sigPositionChanged.connect(
            lambda it, _i=i: self._on_draw_handle_moved(_i, it))
        self.plot_widget.addItem(t)
        self._draw_handle_items.append(t)
        self._refresh_draw_preview(None)
        self._update_draw_hint((x, y))

    def _on_draw_handle_moved(self, i: int, it):
        """A placed control point was dragged before the edge was finished."""
        if 0 <= i < len(self._draw_pts):
            self._draw_pts[i] = (float(it.pos().x()), float(it.pos().y()))
            self._refresh_draw_preview(None)

    def _refresh_draw_preview(self, cursor_pt):
        prev = self._draw_preview_points(cursor_pt)
        if prev is not None and len(prev) > 0:
            self._draw_preview.setData(prev[:, 0], prev[:, 1])
        else:
            self._draw_preview.setData([], [])

    def _update_draw_hint(self, cursor_pt):
        if self._draw_tool is None:
            return
        self._draw_hint.setText(self._draw_hint_text())
        if cursor_pt is not None:
            self._draw_hint.setPos(cursor_pt[0], cursor_pt[1])
        elif self._draw_pts:
            self._draw_hint.setPos(*self._draw_pts[-1])

    def _draw_preview_points(self, cursor_pt):
        """Build the rubber-band preview polyline for the in-progress shape."""
        import math
        tool = self._draw_tool
        pts = list(self._draw_pts)
        if cursor_pt is not None:
            live = pts + [cursor_pt]
        else:
            live = pts
        if not live:
            return None
        if tool == 'circle' and len(live) >= 2:
            cx, cy = live[0]
            r = math.hypot(live[1][0] - cx, live[1][1] - cy)
            ts = np.linspace(0, 2 * math.pi, 64)
            return np.column_stack([cx + r * np.cos(ts), cy + r * np.sin(ts)])
        if tool == 'rectangle' and len(live) >= 2:
            (x0, y0), (x1, y1) = live[0], live[1]
            return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]])
        if tool in ('triangle', 'polygon') and len(live) >= 2:
            arr = np.array(live, dtype=float)
            # Close visually once enough vertices exist.
            if (tool == 'triangle' and len(live) >= 3) or \
               (tool == 'polygon' and len(self._draw_pts) >= 3 and cursor_pt is None):
                arr = np.vstack([arr, arr[0]])
            return arr
        return np.array(live, dtype=float)

    def _commit_draw(self):
        """The shape is fully placed.  Stop collecting clicks but KEEP the
        control points / preview on canvas (so they remain visible until the
        edge is actually created) and emit the drawn points."""
        tool = self._draw_tool
        pts = list(self._draw_pts)
        self._draw_tool = None           # stop collecting; artifacts stay visible
        self._draw_hint.setVisible(False)
        try:
            self.plot_widget.unsetCursor()
        except Exception:
            pass
        if tool and pts:
            self.shape_drawn.emit(tool, pts)

    def _handle_draw_click(self, x: float, y: float, is_double: bool):
        tool = self._draw_tool
        need = self._DRAW_NPTS.get(tool, 2)

        # Snap the placed point to a nearby edge endpoint (incl. the first click).
        if self.snap_cb is not None:
            try:
                x, y = self.snap_cb(x, y)
            except Exception:
                pass

        if tool == 'polygon':
            if is_double:                # finish the free polygon
                if len(self._draw_pts) >= 3:
                    self._commit_draw()
                return
            self._add_draw_point(x, y)
            return

        self._add_draw_point(x, y)
        if need is not None and len(self._draw_pts) >= need:
            self._commit_draw()

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

    def _emit_box_selected(self, x0, y0, x1, y1, extend):
        """Forward a rubber-band selection rect from the view box. Only acts
        when a session is loaded; the controller resolves what falls inside."""
        if self._active_session_id is None:
            return
        self.box_selected.emit(x0, y0, x1, y1, extend)

    def _on_mouse_clicked(self, event):
        # ── Interactive shape drawing intercepts all clicks ───────────────
        if self._draw_tool is not None:
            btn = event.button()
            pos = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
            x, y = pos.x(), pos.y()
            if btn == Qt.MouseButton.RightButton:
                # Right-click cancels the in-progress shape.
                event.accept()
                self.cancel_draw_mode()
                return
            if btn != Qt.MouseButton.LeftButton:
                return
            event.accept()
            is_double = bool(event.double()) if hasattr(event, 'double') else False
            self._handle_draw_click(x, y, is_double)
            return

        if self._active_session_id is None:
            return
        btn = event.button()
        if btn != Qt.MouseButton.LeftButton:
            return
        pos = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
        x, y = pos.x(), pos.y()

        # Double-click an edge → request its numeric editor (handled by the
        # controller, which resolves which edge was hit).
        if (self._selection_mode == 'edge' and hasattr(event, 'double')
                and event.double()):
            self.segment_double_clicked.emit(x, y)
            return

        if self._selection_mode == 'edge':
            # In edge mode: emit segment_clicked with canvas coordinates and extend_selection flag
            # (segment resolution is done in the controller, which handles both
            # discrete and analytic/curve edges — so this works even when there
            # are no discrete points, e.g. a geometry made only of curves).
            modifiers = event.modifiers()
            extend_selection = bool(modifiers & (
                Qt.KeyboardModifier.ControlModifier |
                Qt.KeyboardModifier.ShiftModifier |
                Qt.KeyboardModifier.MetaModifier
            ))
            self.segment_clicked.emit(x, y, extend_selection)
            return

        # Vertex mode (default): find nearest point and emit point_clicked.
        # Guard against empty point arrays: np.argmin() on an empty array
        # raises, e.g. when clicking right after a tab switch before the new
        # session's points are loaded.
        if self._active_points is None or len(self._active_points) == 0:
            return
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
        else:
            # Click was far from all vertices — emit deselect
            self.point_deselected.emit()

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
            # Live rubber-band preview while drawing a shape.
            if self._draw_tool is not None and self._draw_pts:
                cursor = (mp.x(), mp.y())
                if self.snap_cb is not None:
                    try:
                        cursor = self.snap_cb(*cursor)
                    except Exception:
                        pass
                prev = self._draw_preview_points(cursor)
                if prev is not None and len(prev) > 0:
                    self._draw_preview.setData(prev[:, 0], prev[:, 1])
                self._update_draw_hint(cursor)
        else:
            # Mouse left the canvas area — clear the read-out so a stale
            # coordinate does not linger over the scene.
            self.coord_label.setText("")
