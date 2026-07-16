from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import QWidget, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QColor
from app.views.canvas_items import ColorBarWidget, ColorCodedSegmentsItem, SelectableViewBox
from app.views.canvas_render_mixin import CanvasRenderMixin
from app.views.canvas_transform_mixin import CanvasTransformMixin
from app.views.canvas_draw_mixin import CanvasDrawMixin
from app.views.canvas_events_mixin import CanvasEventsMixin


# ── Dark-theme palette ────────────────────────────────────────────────────────
_CANVAS_BG = '#0c0d16'
_CANVAS_FG = '#6b738c'

_COL_SPLIT    = '#FF6E6E'   # red — split points
_COL_SELECTED = '#00E5FF'   # cyan — selected point
_COL_ACTIVE   = '#FFB347'   # orange — active segment
_COL_RESAMPLED = '#FF79C6'  # magenta — resampled result
_COL_PREVIEW  = '#FF8C42'   # orange — formula preview


class CanvasView(QWidget, CanvasRenderMixin, CanvasTransformMixin,
                 CanvasDrawMixin, CanvasEventsMixin):
    """
    Shared interactive canvas that can display multiple geometry sessions
    simultaneously.  Only the ACTIVE session has editable markers
    (split points, selected point, active segment).
    """

    point_clicked = pyqtSignal(int)       # nearest vertex index in active session's points
    point_deselected = pyqtSignal()        # emitted when clicking far from all vertices (deselect)
    segment_clicked = pyqtSignal(float, float, bool)  # (x, y, extend_selection)
    segment_double_clicked = pyqtSignal(float, float)  # (x, y) — open numeric editor
    segment_context_requested = pyqtSignal(float, float)  # (x, y) — right-click menu (e.g. polygon vertex insert/delete)
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
        # Disable pyqtgraph's default right-click plot menu (export / axis range /
        # etc.) — this is a CAD canvas, and right-click is repurposed for the
        # polygon vertex insert/delete context menu (segment_context_requested).
        self.plot_widget.setMenuEnabled(False)
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
        # Checkbox state per session (model-tree "eye"). Drives a 3-level
        # brightness: unchecked = dim (still drawn), checked-not-editing =
        # brighter, editing (active) = brightest. Missing entry defaults True.
        self._geo_checked: dict[int, bool] = {}

        # ── Selection mode ('vertex' or 'edge') ───────────────────────────
        self._selection_mode: str = 'edge'

        # ── Draggable move-handle for the selected vertex (#6) ─────────────
        # A single pg.TargetItem shown over the selected vertex in vertex mode;
        # dragging it reports through ``vertex_move_cb(idx, x, y, finished)``.
        self._vertex_move_handle = None
        self.vertex_move_cb = None
        self._suppress_vertex_cb = False

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
        self._geo_checked.setdefault(session_id, True)

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
            self._geo_checked.pop(session_id, None)

        if session_id in self._curve_preview_items:
            self.plot_widget.removeItem(self._curve_preview_items.pop(session_id))

        if session_id in self._curve_segment_items:
            for item in self._curve_segment_items.pop(session_id):
                self.plot_widget.removeItem(item)

    def _emphasis_level(self, sid: int) -> str:
        """3-level emphasis for a session: 'active' (editing) > 'checked'
        (ticked in the model tree, not editing) > 'unchecked' (dim)."""
        if sid == self._active_session_id:
            return 'active'
        return 'checked' if self._geo_checked.get(sid, True) else 'unchecked'

    def highlight_geometry(self, active_session_id: int):
        """
        Three-level brightness driven by editing state + model-tree checkbox:
          - editing (active)          : width=2.5, full colour, symbol size=4
          - checked, not editing      : width=1.6, alpha 200, symbol size=3
          - unchecked                 : width=1,   alpha 60,  symbol size=1.5
        Unchecked geometry is still drawn (dim), not hidden.
        """
        self._active_session_id = active_session_id
        self._restyle_geometries()

    def _restyle_geometries(self):
        """Apply the current 3-level emphasis to every session's curve,
        preview and deselected-segment items. Safe to call repeatedly."""
        for sid, curve in self._geometries.items():
            color_str = self._geo_colors.get(sid, '#64B5F6')
            curve.setSymbol('o' if self._show_symbols else None)
            level = self._emphasis_level(sid)
            if level == 'active':
                curve.setPen(pg.mkPen(color_str, width=2.5))
                curve.setSymbolBrush(pg.mkBrush(color_str))
                curve.setSymbolSize(4)
            elif level == 'checked':
                c = QColor(color_str); c.setAlpha(200)
                curve.setPen(pg.mkPen(c, width=1.6))
                c2 = QColor(color_str); c2.setAlpha(170)
                curve.setSymbolBrush(pg.mkBrush(c2))
                curve.setSymbolSize(3)
            else:  # unchecked
                c = QColor(color_str); c.setAlpha(60)
                curve.setPen(pg.mkPen(c, width=1))
                c2 = QColor(color_str); c2.setAlpha(40)
                curve.setSymbolBrush(pg.mkBrush(c2))
                curve.setSymbolSize(1.5)

        # Curve previews (dashed) mirror the same three levels.
        has_resampled = False
        x_data, _ = self.resampled_curve.getData()
        if x_data is not None and len(x_data) > 0:
            has_resampled = True

        for sid, preview_curve in self._curve_preview_items.items():
            level = self._emphasis_level(sid)
            is_active = (level == 'active')
            if is_active and has_resampled:
                preview_curve.setSymbol(None)
            else:
                preview_curve.setSymbol('o' if self._show_symbols else None)
            if is_active:
                preview_curve.setPen(pg.mkPen(_COL_PREVIEW, width=2, style=Qt.PenStyle.DashLine))
                preview_curve.setSymbolBrush(pg.mkBrush(_COL_PREVIEW))
                preview_curve.setSymbolSize(4)
            elif level == 'checked':
                c = QColor(_COL_PREVIEW); c.setAlpha(180)
                preview_curve.setPen(pg.mkPen(c, width=1.3, style=Qt.PenStyle.DashLine))
                preview_curve.setSymbolBrush(pg.mkBrush(c))
                preview_curve.setSymbolSize(3)
            else:
                c = QColor(_COL_PREVIEW); c.setAlpha(60)
                preview_curve.setPen(pg.mkPen(c, width=1, style=Qt.PenStyle.DashLine))
                preview_curve.setSymbolBrush(pg.mkBrush(c))
                preview_curve.setSymbolSize(1.5)

        # Deselected curve segments (grey) mirror the same three levels.
        for sid, items in self._curve_segment_items.items():
            level = self._emphasis_level(sid)
            for item in items:
                item.setSymbol('o' if self._show_symbols else None)
                if level == 'active':
                    item.setPen(pg.mkPen('#5c637a', width=1.5, style=Qt.PenStyle.SolidLine))
                    item.setSymbolBrush(pg.mkBrush('#5c637a'))
                    item.setSymbolSize(3)
                elif level == 'checked':
                    c = QColor('#5c637a'); c.setAlpha(180)
                    item.setPen(pg.mkPen(c, width=1.2, style=Qt.PenStyle.SolidLine))
                    item.setSymbolBrush(pg.mkBrush(c))
                    item.setSymbolSize(2.5)
                else:
                    c = QColor('#5c637a'); c.setAlpha(60)
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
        """Model-tree checkbox handler. The checkbox now controls *emphasis*,
        not hard visibility: an unchecked layer stays drawn but dim (see the
        3-level scheme in highlight_geometry), so the user keeps spatial
        context of every geometry while the checked / editing ones stand out."""
        self._geo_checked[session_id] = visible
        # Everything stays visible; only the brightness changes.
        if session_id in self._geometries:
            self._geometries[session_id].setVisible(True)
        if session_id in self._curve_preview_items:
            self._curve_preview_items[session_id].setVisible(True)
        if session_id in self._curve_segment_items:
            for item in self._curve_segment_items[session_id]:
                item.setVisible(True)
        self._restyle_geometries()

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

    # ── Resampled / quality rendering, transform handles, interactive drawing
    #    and mouse handlers live in the canvas_*_mixin.py siblings (methods
    #    resolve through the MRO onto attributes created in __init__ above).
