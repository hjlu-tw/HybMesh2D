from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from app.views.mesh_canvas_loader import GeomLoaderThread

from app.services.logging_setup import get_logger

_log = get_logger(__name__)


class MeshCanvasGeomMixin:
    """Geometry-preview loading + highlighting concern for MeshCanvasView.

    Owns async geometry/seed preview loading (with loader tokens/generation
    management), geometry error highlighting / self-intersection overlays, and
    segment/geometry selection highlighting. Lands on the same instance as the
    rest of MeshCanvasView, so all ``self.*`` state resolves normally."""

    def update_geometry_previews(self, geom_files: list[str]):
        """Load and display the input boundary geometries as preview lines using a background thread."""
        # The geometry set is changing; drop any stale selection highlight so it
        # can't linger over a file that is no longer listed.
        self.highlight_geometry_file(None)
        self._render_previews(
            geom_files, self.geom_preview_items,
            "_geom_loader_gen", "_geom_loader_threads",
            self._on_geometry_previews_loaded, last_attr="_geom_loader_thread")

    def _render_previews(self, files, item_list, gen_attr, threads_attr,
                         on_loaded, last_attr=None):
        """Shared preview-load boilerplate for boundary and seed previews: clear
        the current items, bump the generation token (so a superseded load's
        result is ignored), prune finished threads, and spawn a fresh loader.
        Only the target item list and the on_loaded render style differ."""
        for item in item_list:
            self.plot_widget.removeItem(item)
        item_list.clear()

        # Bump the generation token so any in-flight loader's result is ignored
        # once superseded. We do NOT block (wait()) on the old thread here, so
        # the UI never freezes while a previous load is still finishing.
        gen = getattr(self, gen_attr, 0) + 1
        setattr(self, gen_attr, gen)
        # Keep references to running threads so they are not garbage-collected
        # mid-run (which would crash with "QThread destroyed while running").
        running = [t for t in getattr(self, threads_attr, []) if t.isRunning()]
        setattr(self, threads_attr, running)

        thread = GeomLoaderThread(files, gen)
        thread.loaded_signal.connect(on_loaded)
        thread.finished.connect(lambda t=thread: self._drop_loader_thread(t, threads_attr))
        running.append(thread)
        if last_attr is not None:
            setattr(self, last_attr, thread)  # last thread (used by close handler)
        thread.start()

    def _drop_loader_thread(self, thread, threads_attr):
        threads = getattr(self, threads_attr, [])
        if thread in threads:
            threads.remove(thread)

    def _on_geometry_previews_loaded(self, token: int, results: list[np.ndarray]):
        # Ignore results from a superseded request (a newer load has started).
        if token != getattr(self, "_geom_loader_gen", 0):
            return
        # Store the loaded geometry data so we can re-highlight on failure
        self._loaded_geom_data = results
        for pts in results:
            try:
                # If the first and last points are not close, stack first point to close it visually
                if not np.allclose(pts[0], pts[-1]):
                    pts = np.vstack((pts, pts[0]))

                item = self.plot_widget.plot(
                    pts[:, 0], pts[:, 1],
                    pen=pg.mkPen('#4a5070', width=1.5, style=Qt.PenStyle.SolidLine),
                    symbol='o', symbolBrush='#4a5070', symbolSize=3
                )
                item.setZValue(5)
                self.geom_preview_items.append(item)
            except Exception as e:
                print(f"Error rendering loaded preview geometry: {e}")
        self._update_empty_state()
        # Fit once when the first content (or a requested refit) arrives; leave
        # the view alone on later refreshes so a role change doesn't move it.
        if self.geom_preview_items and not self._did_initial_fit:
            self.auto_range()

    def request_refit(self):
        """Ask for a one-time refit on the next preview load (used when the
        geometry SET changes, e.g. add/browse/remove)."""
        self._did_initial_fit = False

    def update_seed_previews(self, seed_files: list[str]):
        """Load and display refinement-seed geometries as dashed orange preview
        lines — a distinct style from body-fitted boundaries. Kept in a separate
        item list so boundary and seed previews refresh independently."""
        self._render_previews(
            seed_files, self.seed_preview_items,
            "_seed_loader_gen", "_seed_loader_threads",
            self._on_seed_previews_loaded)

    def _on_seed_previews_loaded(self, token: int, results: list[np.ndarray]):
        # Ignore results from a superseded request.
        if token != getattr(self, "_seed_loader_gen", 0):
            return
        for pts in results:
            try:
                pts = np.atleast_2d(pts)
                if pts.shape[1] < 2:
                    continue
                # Seeds are often open polylines/points — do NOT force-close them.
                item = self.plot_widget.plot(
                    pts[:, 0], pts[:, 1],
                    pen=pg.mkPen('#e0872e', width=1.6, style=Qt.PenStyle.DashLine),
                    symbol='x', symbolBrush='#e0872e', symbolPen='#e0872e', symbolSize=5
                )
                item.setZValue(6)
                self.seed_preview_items.append(item)
            except Exception as e:
                print(f"Error rendering seed preview geometry: {e}")
        self._update_empty_state()

    def highlight_error_geometry(self, geom_index: int | list[int]):
        """Highlight a specific geometry or list of geometries (0-based index) in red to indicate self-intersection failure.

        Also re-renders all other geometries dimmed so the failed ones stand out.
        """
        self.clear_error_highlights()
        geom_data = getattr(self, '_loaded_geom_data', None)
        if not geom_data:
            return

        target_indices = {geom_index} if isinstance(geom_index, int) else set(geom_index)

        for i, pts in enumerate(geom_data):
            try:
                display_pts = pts.copy()
                if not np.allclose(display_pts[0], display_pts[-1]):
                    display_pts = np.vstack((display_pts, display_pts[0]))
                if i in target_indices:
                    # Red, thick outline for the failed geometry
                    item = self.plot_widget.plot(
                        display_pts[:, 0], display_pts[:, 1],
                        pen=pg.mkPen('#ff3333', width=4, style=Qt.PenStyle.SolidLine)
                    )
                    item.setZValue(25)
                    self._error_highlight_items.append(item)
                else:
                    # Dim other geometries
                    c = QColor('#4a5070')
                    c.setAlpha(80)
                    item = self.plot_widget.plot(
                        display_pts[:, 0], display_pts[:, 1],
                        pen=pg.mkPen(c, width=1, style=Qt.PenStyle.SolidLine),
                    )
                    item.setZValue(5)
                    self._error_highlight_items.append(item)
            except Exception as e:
                print(f"Error highlighting error geometry {i}: {e}")

    def highlight_self_intersection_point(self, x: float, y: float):
        """Draw a prominent marker at the self-intersection coordinate."""
        item = self.plot_widget.plot(
            [x], [y],
            symbol='x',
            symbolSize=14,
            symbolPen=pg.mkPen('#ff3333', width=3)
        )
        item.setZValue(30)
        if not hasattr(self, '_error_highlight_items'):
            self._error_highlight_items = []
        self._error_highlight_items.append(item)

    def clear_error_highlights(self):
        """Remove any error-highlight geometry overlay items."""
        for item in getattr(self, '_error_highlight_items', []):
            try:
                self.plot_widget.removeItem(item)
            except Exception:
                _log.debug("could not remove an error-highlight item", exc_info=True)
        self._error_highlight_items = []

    def highlight_segment(self, coords):
        """Highlight one or more segments' points/edges (Nx2 array). Rows of NaN
        break the polyline, so several disjoint segments can be highlighted at
        once (multi-select in the per-segment BC dialog). Pass None/empty to
        clear."""
        item = getattr(self, "_seg_highlight_item", None)
        if item is not None:
            try:
                self.plot_widget.removeItem(item)
            except Exception:
                _log.debug("could not remove the segment-highlight item", exc_info=True)
            self._seg_highlight_item = None
        if coords is None or len(coords) < 1:
            return
        c = np.atleast_2d(np.asarray(coords, dtype=float))
        if c.shape[1] < 2:
            return
        # connect='finite' → NaN rows split the line into separate segments.
        self._seg_highlight_item = self.plot_widget.plot(
            c[:, 0], c[:, 1], connect='finite',
            pen=pg.mkPen('#ff5bd0', width=4, style=Qt.PenStyle.SolidLine),
            symbol='o', symbolSize=6, symbolBrush='#ff5bd0', symbolPen='#ff5bd0')
        self._seg_highlight_item.setZValue(24)

    def highlight_geometry_file(self, path: str | None):
        """Draw a bright outline over the geometry stored at `path` so the file
        selected in the config list stands out on the canvas. Passing a falsy
        path (or a missing file) just clears the previous highlight."""
        if self._sel_highlight_item is not None:
            try:
                self.plot_widget.removeItem(self._sel_highlight_item)
            except Exception:
                _log.debug(
                    "could not remove the selection-highlight "
                    "item", exc_info=True)
            self._sel_highlight_item = None

        import os
        if not path or not os.path.exists(path):
            return
        try:
            pts = np.atleast_2d(np.loadtxt(path))
        except Exception:
            return
        if pts.shape[0] < 2 or pts.shape[1] < 2:
            return
        # Close a boundary loop visually, but leave open polylines/seeds as-is.
        if pts.shape[0] >= 3 and not np.allclose(pts[0], pts[-1]):
            pts = np.vstack((pts, pts[0]))
        item = self.plot_widget.plot(
            pts[:, 0], pts[:, 1],
            pen=pg.mkPen('#ffe066', width=3, style=Qt.PenStyle.SolidLine))
        item.setZValue(22)
        self._sel_highlight_item = item
