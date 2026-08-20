"""Draggable transform base-point / axis / rotate / translate handles,
extracted verbatim from CanvasView (behaviour unchanged). These methods build
and drive the interactive gizmos used by the transform tools; drags are
reported through ``self.transform_handle_cb``. They read/write attributes
created in CanvasView.__init__ (resolved through the MRO)."""
from __future__ import annotations
import pyqtgraph as pg
from PyQt6.QtCore import Qt


class CanvasTransformMixin:
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
