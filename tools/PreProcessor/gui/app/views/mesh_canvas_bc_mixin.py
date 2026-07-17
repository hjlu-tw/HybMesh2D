from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import Qt
from app.utils import BC_COLORS, DEFAULT_BC_COLOR
from app.services.meta_io import read_meta_segments, read_meta_point_segids


class MeshCanvasBCMixin:
    """Boundary-condition preview/coloring concern for MeshCanvasView.

    Builds/refreshes the BC preview from the mesh config (four rectangle domain
    edges), colours the geometry outlines by their per-segment patch/group
    labels (from the .meta sidecars), and maps BC labels to colours. Lands on
    the same instance as the rest of MeshCanvasView, so all ``self.*`` state
    (plot_widget, mesh_config, bc_preview_items, geom_bc_items, ...) resolves
    normally."""

    def _rebuild_bc_preview_from_config(self):
        """Draw colored BC segments directly on the four domain boundary edges.

        This works even before mesh generation, providing immediate visual feedback
        for the configured boundary condition types.
        """
        for item in self.bc_preview_items:
            self.plot_widget.removeItem(item)
        self.bc_preview_items.clear()

        if not self.mesh_config:
            return
        # A custom-geometry domain carries its boundary conditions on the outline
        # edges (via the .meta sidecar), not on the four rectangle sides, so drawing
        # rectangle-edge BC colours here would be misleading.
        if self.domain_is_custom:
            return

        cfg = self.mesh_config
        xmin, xmax = cfg.domain_x_min, cfg.domain_x_max
        ymin, ymax = cfg.domain_y_min, cfg.domain_y_max

        # Each side: (xs, ys, bc_config_value)
        sides = [
            ([xmin, xmin], [ymin, ymax], cfg.bc_xmin.lower()),  # left
            ([xmax, xmax], [ymin, ymax], cfg.bc_xmax.lower()),  # right
            ([xmin, xmax], [ymin, ymin], cfg.bc_ymin.lower()),  # bottom
            ([xmin, xmax], [ymax, ymax], cfg.bc_ymax.lower()),  # top
        ]

        # #3: until the user has actually configured the domain BCs, draw the
        # four edges NEUTRAL (thin dashed grey) instead of painting the pristine
        # inlet/outlet model defaults as bold semantic colours — those read as
        # arbitrary "weird" colours on a box the user never touched.
        configured = getattr(cfg, "bc_configured", True)
        for xs, ys, bc_val in sides:
            if configured:
                color_str = BC_COLORS.get(bc_val, DEFAULT_BC_COLOR)
                pen = pg.mkPen(color_str, width=4, style=Qt.PenStyle.SolidLine)
            else:
                pen = pg.mkPen(DEFAULT_BC_COLOR, width=2, style=Qt.PenStyle.DashLine)
            item = self.plot_widget.plot(xs, ys, pen=pen)
            item.setZValue(18)
            item.setVisible(self.show_bc_coloring)
            self.bc_preview_items.append(item)

    def _bc_color_for_label(self, label: str) -> str:
        """Colour for a patch/group label. Known BC-type names use the shared
        semantic BC_COLORS; any other free-form label gets a stable palette
        colour assigned in first-appearance order (#9)."""
        key = (label or "").strip().lower()
        if not key:
            return DEFAULT_BC_COLOR
        if key in BC_COLORS:
            return BC_COLORS[key]
        if key not in self._bc_label_colors:
            idx = len(self._bc_label_colors) % len(self._BC_PALETTE)
            self._bc_label_colors[key] = self._BC_PALETTE[idx]
        return self._bc_label_colors[key]

    def _rebuild_geom_bc_preview(self):
        """(#9) Colour each geometry OUTLINE segment by its per-segment patch/
        group label (read from the geometry's .meta sidecar). Runs synchronously
        (the .dat/.meta files are small) so BC Preview immediately shows the
        colours on the corresponding edges — including custom-geometry domains,
        which the rectangle-box preview skips. Segments with no .meta info keep
        the plain grey outline drawn by the async loader."""
        for item in self.geom_bc_items:
            self.plot_widget.removeItem(item)
        self.geom_bc_items.clear()

        if not self.mesh_config or not self.show_bc_coloring:
            return

        for gf in self.mesh_config.geom_files:
            try:
                pts = np.atleast_2d(np.loadtxt(gf))
            except Exception:
                continue
            if pts.shape[0] < 2 or pts.shape[1] < 2:
                continue
            labels = {sid: bc for sid, bc, _k in read_meta_segments(gf)}
            segids = read_meta_point_segids(gf)
            if not segids or len(segids) != pts.shape[0]:
                continue  # no per-segment info → leave the grey outline

            # Draw each maximal run of consecutive points with the same segment
            # id in that segment's label colour; extend one vertex into the next
            # run so adjacent segments meet with no visible gap.
            n = len(segids)
            i = 0
            while i < n:
                sid = segids[i]
                j = i
                while j + 1 < n and segids[j + 1] == sid:
                    j += 1
                end = min(j + 1, n - 1)
                if sid >= 0 and end > i:
                    color = self._bc_color_for_label(labels.get(sid, ""))
                    run = pts[i:end + 1, :2]
                    item = self.plot_widget.plot(
                        run[:, 0], run[:, 1],
                        pen=pg.mkPen(color, width=3))
                    item.setZValue(19)
                    self.geom_bc_items.append(item)
                i = j + 1
