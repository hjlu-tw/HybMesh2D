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
from app.views.canvas_geometry_mixin import CanvasGeometryMixin
from app.views.canvas_selection_mixin import CanvasSelectionMixin


# ── Dark-theme palette ────────────────────────────────────────────────────────
_CANVAS_BG = '#0c0d16'
_CANVAS_FG = '#6b738c'

_COL_SPLIT    = '#FF6E6E'   # red — split points
_COL_SELECTED = '#00E5FF'   # cyan — selected point
_COL_ACTIVE   = '#FFB347'   # orange — active segment
_COL_RESAMPLED = '#FF79C6'  # magenta — resampled result
_COL_PREVIEW  = '#FF8C42'   # orange — formula preview
_COL_CLOSING  = '#FFD700'   # gold — auto-added closing edge (dashed)


class CanvasView(QWidget, CanvasRenderMixin, CanvasTransformMixin,
                 CanvasDrawMixin, CanvasEventsMixin,
                 CanvasGeometryMixin, CanvasSelectionMixin):
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
    endpoint_weld_requested = pyqtSignal(float, float, float, float, bool)  # (from_x, from_y, to_x, to_y, weld) — weld tool


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
        # Positions of the currently-shown open endpoints (for the weld tool's
        # hit-testing); kept in sync by show/clear_open_endpoint_markers.
        self._open_endpoint_pts: np.ndarray | None = None
        # Cyan ring highlighting the endpoint armed by the weld tool (first click).
        self._endpoint_pick_marker = pg.ScatterPlotItem(
            size=20, symbol='o', pen=pg.mkPen('#00E5FF', width=3),
            brush=pg.mkBrush(0, 229, 255, 60))
        self._endpoint_pick_marker.setZValue(37)
        self.plot_widget.addItem(self._endpoint_pick_marker)

        # Auto-added closing edge — a gold dashed segment marking the last→first
        # bridge when a closed loop has a real gap, so the auto-closure is visible
        # and not mistaken for real geometry. Above the base polyline (z=5),
        # below the point markers.
        self._closing_edge = self.plot_widget.plot(
            [], [], pen=pg.mkPen(_COL_CLOSING, width=2.5,
                                 style=Qt.PenStyle.DashLine))
        self._closing_edge.setZValue(15)

        # ── Endpoint weld tool state (drag-to-weld) ───────────────────────
        self._endpoint_tool: bool = False        # True while the weld tool is active
        self._endpoint_from: tuple | None = None  # (legacy) armed source endpoint
        self._weld_handles: list = []             # draggable TargetItems, one per endpoint
        self._weld_src: dict = {}                 # id(handle) -> its original (x, y)

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


    # ═════════════════════════════════════════════════════════════════════
    # Active-session overlays
    # ═════════════════════════════════════════════════════════════════════


    # ── Resampled / quality rendering, transform handles, interactive drawing
    #    and mouse handlers live in the canvas_*_mixin.py siblings (methods
    #    resolve through the MRO onto attributes created in __init__ above).
