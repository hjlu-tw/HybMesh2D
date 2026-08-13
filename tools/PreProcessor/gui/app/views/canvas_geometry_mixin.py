from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


# ── Dark-theme palette ────────────────────────────────────────────────────────
_CANVAS_BG = '#0c0d16'
_CANVAS_FG = '#6b738c'

_COL_SPLIT    = '#FF6E6E'   # red — split points
_COL_SELECTED = '#00E5FF'   # cyan — selected point
_COL_ACTIVE   = '#FFB347'   # orange — active segment
_COL_RESAMPLED = '#FF79C6'  # magenta — resampled result
_COL_PREVIEW  = '#FF8C42'   # orange — formula preview
_COL_CLOSING  = '#FFD700'   # gold — auto-added closing edge (dashed)


class CanvasGeometryMixin:
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

    def update_geometry(self, session_id: int, points: np.ndarray | None,
                        connect: np.ndarray | None = None):
        """Update an existing geometry layer.

        ``connect`` is pyqtgraph's per-point flag array (1 = join point i to
        i+1). The whole geometry is ONE polyline item, so without it two pieces
        that merely sit next to each other in ``original_points`` are drawn
        joined — a straight line across the gap that looks like real geometry
        and belongs to no edge. The caller derives the breaks from the model
        (see ``controller._geometry_connect``); ``None`` keeps the plain
        connect-everything path.
        """
        if session_id not in self._geometries:
            return
        if points is not None and len(points) > 0:
            if connect is not None:
                self._geometries[session_id].setData(
                    points[:, 0], points[:, 1], connect=connect)
            else:
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
