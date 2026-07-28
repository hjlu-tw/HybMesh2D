"""Editable analytic-edge control-point handles, endpoint markers, interactive
shape drawing (line/circle/rectangle/triangle/polygon) and curve-segment
rendering, extracted verbatim from CanvasView (behaviour unchanged). These
methods read/write attributes created in CanvasView.__init__ (resolved through
the MRO) and emit ``shape_drawn`` when an interactive draw completes."""
from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor


class CanvasDrawMixin:
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
            self._open_endpoint_pts = pts
        else:
            self._open_endpoint_markers.clear()
            self._open_endpoint_pts = None

    def clear_open_endpoint_markers(self):
        self._open_endpoint_markers.clear()
        self._open_endpoint_pts = None

    # ── Endpoint weld tool (drag-to-weld) ──────────────────────────────────
    # Each endpoint gets a draggable handle; drag one onto another point to weld
    # them (the dragged endpoint moves onto the drop position, snapping to the
    # nearest endpoint/vertex when close). Dropping in free space just moves the
    # endpoint there. Right-click cancels. (Replaces the old two-click flow.)
    def start_endpoint_tool(self):
        """Enter the drag-to-weld tool: show a draggable handle on every endpoint;
        drag one onto a target point to weld (or into free space to move it)."""
        self.cancel_draw_mode()          # never both tools at once
        self._endpoint_tool = True
        self._endpoint_from = None
        self._endpoint_pick_marker.clear()
        self._build_weld_handles()
        try:
            self.plot_widget.setCursor(Qt.CursorShape.OpenHandCursor)
        except Exception:
            pass

    def stop_endpoint_tool(self):
        self._endpoint_tool = False
        self._endpoint_from = None
        self._endpoint_pick_marker.clear()
        self._clear_weld_handles()
        try:
            self.plot_widget.unsetCursor()
        except Exception:
            pass

    def _weld_source_points(self):
        """Every draggable weld point: all edge endpoints (white markers) plus any
        red open endpoints, de-duplicated within a tiny tolerance."""
        pts = []
        try:
            xs, ys = self._endpoint_markers.getData()
            if xs is not None and ys is not None:
                pts.extend((float(a), float(b)) for a, b in zip(xs, ys))
        except Exception:
            pass
        if self._open_endpoint_pts is not None:
            pts.extend((float(p[0]), float(p[1])) for p in self._open_endpoint_pts)
        uniq = []
        for x, y in pts:
            if not any(abs(x - ux) < 1e-9 and abs(y - uy) < 1e-9 for ux, uy in uniq):
                uniq.append((x, y))
        return uniq

    def _clear_weld_handles(self):
        for it in getattr(self, "_weld_handles", []):
            self.plot_widget.removeItem(it)
        self._weld_handles = []
        self._weld_src = {}

    def _build_weld_handles(self):
        """(Re)create a draggable TargetItem over each weld point."""
        self._clear_weld_handles()
        for (x, y) in self._weld_source_points():
            t = pg.TargetItem(pos=(x, y), size=14, movable=True, symbol='o',
                              pen=pg.mkPen('#FF5252', width=2.4),
                              brush=pg.mkBrush(255, 82, 82, 90),
                              hoverBrush=pg.mkBrush('#FF8A80'))
            t.setZValue(208)
            t.sigPositionChanged.connect(lambda it: self._on_weld_drag(it))
            t.sigPositionChangeFinished.connect(lambda it: self._on_weld_drop(it))
            self.plot_widget.addItem(t)
            self._weld_handles.append(t)
            self._weld_src[id(t)] = (x, y)

    def _rebuild_weld_handles_if_active(self):
        if getattr(self, "_endpoint_tool", False):
            self._build_weld_handles()

    def _nearest_weld_target(self, it, px=28.0):
        """Nearest snap point (any endpoint or active vertex) to handle ``it``'s
        current position within ``px`` pixels, excluding its own source. None if
        nothing is close enough (→ a free move)."""
        p = it.pos()
        sp = self.plot_widget.plotItem.vb.mapViewToScene(
            pg.Point(float(p.x()), float(p.y())))
        sx, sy = sp.x(), sp.y()
        src = getattr(self, "_weld_src", {}).get(id(it))
        cands = list(self._weld_source_points())
        if self._active_points is not None:
            cands.extend((float(q[0]), float(q[1])) for q in self._active_points)
        best = None
        best_d = px
        for (cx, cy) in cands:
            if src is not None and abs(cx - src[0]) < 1e-9 and abs(cy - src[1]) < 1e-9:
                continue
            d = self._pixel_dist(cx, cy, sx, sy)
            if d < best_d:
                best_d = d
                best = (cx, cy)
        return best

    def _on_weld_drag(self, it):
        """Live: ring the snap target the dragged endpoint would weld onto."""
        tgt = self._nearest_weld_target(it)
        if tgt is not None:
            self._endpoint_pick_marker.setData([tgt[0]], [tgt[1]])
        else:
            self._endpoint_pick_marker.clear()

    def _on_weld_drop(self, it):
        """Drop: weld/move the dragged endpoint onto the snapped point (or the free
        drop position when nothing is close)."""
        src = getattr(self, "_weld_src", {}).get(id(it))
        if src is None:
            return
        p = it.pos()
        tgt = self._nearest_weld_target(it)
        tx, ty = tgt if tgt is not None else (float(p.x()), float(p.y()))
        self._endpoint_pick_marker.clear()
        fx, fy = src
        # Always a move/weld of the dragged endpoint to the drop/snap position.
        self.endpoint_weld_requested.emit(fx, fy, tx, ty, True)
        # The handler refreshes the geometry synchronously; rebuild the handles on
        # the next tick (never mutate the item list from inside its own signal).
        QTimer.singleShot(0, self._rebuild_weld_handles_if_active)

    def _arm_endpoint(self, x, y):
        """Mark (x, y) as the armed source endpoint and highlight it (cyan ring)."""
        self._endpoint_from = (float(x), float(y))
        self._endpoint_pick_marker.setData([x], [y])

    def show_closing_edge(self, p_last, p_first):
        """Draw the gold dashed segment bridging last→first (the auto-added
        closure) so it reads as distinct from real geometry edges."""
        p0 = np.asarray(p_last, dtype=float)
        p1 = np.asarray(p_first, dtype=float)
        self._closing_edge.setData([p0[0], p1[0]], [p0[1], p1[1]])

    def clear_closing_edge(self):
        self._closing_edge.setData([], [])

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
    _DRAW_NPTS = {'line': 2, 'circle': 2, 'arc': 3, 'rectangle': 2,
                  'triangle': 3, 'polygon': None, 'polyline': None}

    def start_draw_mode(self, tool: str):
        """Enter interactive shape-drawing mode for ``tool``.  Clicks place the
        defining points (each becomes a draggable control point) with a live
        rubber-band preview; once the shape is complete the canvas emits
        ``shape_drawn`` (the controller then opens the numeric dialog).  The
        initial prompt is centred in the current view so it is always visible."""
        self.clear_draw_artifacts()
        self.stop_endpoint_tool()        # never both tools at once
        self._draw_tool = tool
        self._draw_pts = []
        # Freeze the view while drawing: placing the first point (a single point)
        # or updating the rubber-band preview must not trigger pyqtgraph
        # auto-ranging to a tiny extent. The view stays put until the shape is
        # complete; explicit fit_to_* calls still work afterwards.
        try:
            self.plot_widget.getViewBox().disableAutoRange()
        except Exception:
            pass
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
        if tool == 'arc':
            return ("Click the arc centre" if n == 0 else
                    "Click to set the radius (and start angle)" if n == 1 else
                    "Click to set the end angle")
        if tool == 'rectangle':
            return "Click a corner" if n == 0 else "Click the opposite corner"
        if tool == 'triangle':
            return f"Click point {n + 1} of 3"
        if tool == 'polygon':
            return ("Click to add vertices — double-click to finish"
                    if n < 3 else
                    f"{n} vertices — double-click to finish")
        if tool == 'polyline':
            return ("Click to add points — double-click to finish"
                    if n < 2 else
                    f"{n} points — double-click to finish (open polyline)")
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
        if tool == 'arc':
            # Click 1 = centre, click 2 = radius/start-angle, click 3 = end
            # angle. Preview a full circle while the radius is being set, then
            # the CCW arc while the end angle is being set.
            n_placed = len(self._draw_pts)
            if n_placed == 0:
                return np.array(live, dtype=float)
            cx, cy = self._draw_pts[0]
            if n_placed == 1:
                px, py = cursor_pt if cursor_pt is not None else self._draw_pts[0]
                r = math.hypot(px - cx, py - cy)
                if r < 1e-9:
                    return np.array([[cx, cy]], dtype=float)
                ts = np.linspace(0, 2 * math.pi, 64)
                return np.column_stack([cx + r * np.cos(ts), cy + r * np.sin(ts)])
            rx, ry = self._draw_pts[1]
            r = math.hypot(rx - cx, ry - cy)
            t0 = math.atan2(ry - cy, rx - cx)
            ax, ay = cursor_pt if cursor_pt is not None else self._draw_pts[-1]
            sweep = (math.atan2(ay - cy, ax - cx) - t0) % (2 * math.pi)
            ts = np.linspace(t0, t0 + sweep, 64)
            return np.column_stack([cx + r * np.cos(ts), cy + r * np.sin(ts)])
        if tool == 'rectangle' and len(live) >= 2:
            (x0, y0), (x1, y1) = live[0], live[1]
            return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]])
        if tool in ('triangle', 'polygon', 'polyline') and len(live) >= 2:
            arr = np.array(live, dtype=float)
            # Close visually once enough vertices exist — but a polyline stays
            # OPEN (never bridges last→first).
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

        if tool in ('polygon', 'polyline'):
            if is_double:                # finish the free polygon / polyline
                min_pts = 3 if tool == 'polygon' else 2
                if len(self._draw_pts) >= min_pts:
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
