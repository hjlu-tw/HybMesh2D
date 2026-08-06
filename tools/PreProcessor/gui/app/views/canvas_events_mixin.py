"""Mouse event handlers (click/move/throttled coordinate read-out and
rubber-band box forwarding), extracted verbatim from CanvasView (behaviour
unchanged). These methods are connected in CanvasView.__init__ to the plot
scene signals and read/write attributes created there (resolved via the MRO).
They emit the public CanvasView signals (point_clicked, segment_clicked, …)."""
from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import Qt

from app.services.logging_setup import get_logger

_log = get_logger(__name__)


class CanvasEventsMixin:
    def _active_points_have_seam(self) -> bool:
        """True when the active display array carries an appended closing seam
        (a copy of index 0 at the end) — as produced for a CLOSED curve by the
        controller's geometry refresh. Detected by an exact coincidence of the
        first and last display points over a real loop (>= 3 points), matching
        how the seam is appended (a verbatim copy of point 0)."""
        ap = self._active_points
        if ap is None or len(ap) < 3:
            return False
        return bool(ap[0, 0] == ap[-1, 0] and ap[0, 1] == ap[-1, 1])

    def _model_point_index(self, display_idx: int) -> int:
        """Map a display-array index (which may include the appended closing
        seam of a closed curve) back to the editable ``original_points`` index
        space so hit-testing and the move/split code share ONE index space."""
        if self._active_points_have_seam() \
                and display_idx == len(self._active_points) - 1:
            return 0
        return display_idx

    def _emit_box_selected(self, x0, y0, x1, y1, extend):
        """Forward a rubber-band selection rect from the view box. Only acts
        when a session is loaded; the controller resolves what falls inside."""
        if self._active_session_id is None:
            return
        self.box_selected.emit(x0, y0, x1, y1, extend)

    def _pixel_dist(self, x, y, sx, sy):
        """Pixel distance between view-coord (x, y) and scene pos (sx, sy)."""
        vb = self.plot_widget.plotItem.vb
        p = vb.mapViewToScene(pg.Point(x, y))
        return ((p.x() - sx) ** 2 + (p.y() - sy) ** 2) ** 0.5

    def _nearest_open_endpoint(self, sx, sy, exclude=None, px=28.0):
        """The open-endpoint position nearest scene pos (sx, sy) within ``px``
        pixels, or None. ``exclude`` (x, y) is skipped (the armed source)."""
        pts = self._open_endpoint_pts
        if pts is None or len(pts) == 0:
            return None
        best = None; best_d = px
        for p in pts:
            if exclude is not None and abs(p[0] - exclude[0]) < 1e-9 \
                    and abs(p[1] - exclude[1]) < 1e-9:
                continue
            d = self._pixel_dist(p[0], p[1], sx, sy)
            if d < best_d:
                best_d = d; best = (float(p[0]), float(p[1]))
        return best

    def _nearest_vertex(self, sx, sy, px=28.0):
        """The active-geometry vertex nearest scene pos (sx, sy) within ``px``
        pixels, or None. Lets the weld tool arm ANY point, not just a red open
        endpoint — so two arbitrary points can be welded even when the geometry
        is already closed and shows no open-endpoint warnings."""
        ap = self._active_points
        if ap is None or len(ap) == 0:
            return None
        best = None; best_d = px
        for p in ap:
            d = self._pixel_dist(p[0], p[1], sx, sy)
            if d < best_d:
                best_d = d; best = (float(p[0]), float(p[1]))
        return best

    def _on_mouse_clicked(self, event):
        # ── Endpoint weld tool: welding is by DRAGGING the per-endpoint
        #    handles (see canvas_draw_mixin); a plain click does nothing here.
        #    Right-click cancels the tool. ────────────────────────────────
        if getattr(self, '_endpoint_tool', False):
            event.accept()
            if event.button() == Qt.MouseButton.RightButton:
                self.stop_endpoint_tool()
            return

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
        # Right-click in edge mode → context-menu request (polygon vertex
        # insert/delete). The controller resolves what's under the cursor and
        # only acts when a polygon is selected; harmless otherwise.
        if btn == Qt.MouseButton.RightButton and self._selection_mode == 'edge':
            rpos = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
            event.accept()
            self.segment_context_requested.emit(rpos.x(), rpos.y())
            return
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

        # For a CLOSED curve the display array carries an extra seam point
        # (a copy of index 0 appended at the end so the polyline draws shut),
        # while the editable model (original_points) has no such copy. Clicking
        # that appended seam yields nearest_idx == len-1, which is out of range
        # for the model and would make the move/split silently no-op. Fold that
        # seam index back onto index 0 so the emitted index is always a valid
        # original_points index (hit-test and move share ONE index space).
        nearest_idx = self._model_point_index(nearest_idx)

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
                        _log.warning(
                            "snap callback failed; the draw preview is "
                            "unsnapped", exc_info=True)
                prev = self._draw_preview_points(cursor)
                if prev is not None and len(prev) > 0:
                    self._draw_preview.setData(prev[:, 0], prev[:, 1])
                self._update_draw_hint(cursor)
        else:
            # Mouse left the canvas area — clear the read-out so a stale
            # coordinate does not linger over the scene.
            self.coord_label.setText("")
