from __future__ import annotations
from PyQt6.QtWidgets import QGraphicsPathItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainterPath, QPen, QBrush


class MeshCanvasFillsMixin:
    """Quality/element-type coloured path-fill construction for MeshCanvasView.

    Extracted verbatim from mesh_canvas.py; methods reference ``self.*``
    (``self.mesh``, ``self.color_mode``, ``self.filled_items``,
    ``self.plot_widget``, ``self.FILL_CELL_LIMIT``) via the MRO of the host
    QWidget subclass, so behaviour is unchanged.
    """

    def _rebuild_mesh_fills(self):
        """Construct only the quality/element colored path fills."""
        for item in self.filled_items:
            self.plot_widget.removeItem(item)
        self.filled_items.clear()

        if not self.mesh or len(self.mesh.points) == 0:
            return

        total_cells = (len(self.mesh.triangles) + len(self.mesh.quads)
                       + len(self.mesh.polygons))
        if total_cells > self.FILL_CELL_LIMIT:
            # Skip fills on very large meshes; the wireframe conveys the mesh and
            # stays responsive. Log once per distinct mesh so it's not silent.
            if getattr(self, "_fills_skipped_for", None) != id(self.mesh):
                self._fills_skipped_for = id(self.mesh)
                print(f"[mesh] {total_cells} cells > {self.FILL_CELL_LIMIT}: element "
                      "fills / quality shading skipped for performance "
                      "(wireframe shown).")
            return

        if self.color_mode == "uniform":
            path = QPainterPath()
            for tri in self.mesh.triangles:
                self._add_poly_to_path(path, tri)
            for quad in self.mesh.quads:
                self._add_poly_to_path(path, quad)
            for poly in self.mesh.polygons:
                self._add_poly_to_path(path, poly)
            self._add_path_item(path, QBrush(QColor(43, 61, 99, 45)))

        elif self.color_mode == "element_type":
            path_tri = QPainterPath()
            path_quad = QPainterPath()
            path_poly = QPainterPath()

            for tri in self.mesh.triangles:
                self._add_poly_to_path(path_tri, tri)
            for quad in self.mesh.quads:
                self._add_poly_to_path(path_quad, quad)
            for poly in self.mesh.polygons:
                self._add_poly_to_path(path_poly, poly)

            if not path_tri.isEmpty():
                self._add_path_item(path_tri, QBrush(QColor(64, 150, 238, 40)))
            if not path_quad.isEmpty():
                self._add_path_item(path_quad, QBrush(QColor(139, 92, 246, 40)))
            if not path_poly.isEmpty():
                self._add_path_item(path_poly, QBrush(QColor(245, 158, 11, 40)))

        elif self.color_mode == "quality_aspect":
            path_good = QPainterPath()
            path_fair = QPainterPath()
            path_poor = QPainterPath()
            path_bad = QPainterPath()

            ratios = self.mesh.get_element_aspect_ratios()
            all_cells = (
                [(tri, "tri") for tri in self.mesh.triangles] +
                [(quad, "quad") for quad in self.mesh.quads] +
                [(poly, "poly") for poly in self.mesh.polygons]
            )

            for idx, (cell, _) in enumerate(all_cells):
                r = ratios[idx]
                if r <= 1.25:
                    self._add_poly_to_path(path_good, cell)
                elif r <= 1.8:
                    self._add_poly_to_path(path_fair, cell)
                elif r <= 2.5:
                    self._add_poly_to_path(path_poor, cell)
                else:
                    self._add_poly_to_path(path_bad, cell)

            if not path_good.isEmpty():
                self._add_path_item(path_good, QBrush(QColor(16, 185, 129, 45)))
            if not path_fair.isEmpty():
                self._add_path_item(path_fair, QBrush(QColor(163, 230, 53, 45)))
            if not path_poor.isEmpty():
                self._add_path_item(path_poor, QBrush(QColor(245, 158, 11, 45)))
            if not path_bad.isEmpty():
                self._add_path_item(path_bad, QBrush(QColor(239, 68, 68, 60)))

        elif self.color_mode == "quality_skewness":
            path_good = QPainterPath()
            path_fair = QPainterPath()
            path_poor = QPainterPath()
            path_bad = QPainterPath()

            skew_vals = self.mesh.get_element_skewness()
            all_cells = (
                [(tri, "tri") for tri in self.mesh.triangles] +
                [(quad, "quad") for quad in self.mesh.quads] +
                [(poly, "poly") for poly in self.mesh.polygons]
            )

            for idx, (cell, _) in enumerate(all_cells):
                s = skew_vals[idx]
                if s <= 0.25:
                    self._add_poly_to_path(path_good, cell)
                elif s <= 0.50:
                    self._add_poly_to_path(path_fair, cell)
                elif s <= 0.75:
                    self._add_poly_to_path(path_poor, cell)
                else:
                    self._add_poly_to_path(path_bad, cell)

            if not path_good.isEmpty():
                self._add_path_item(path_good, QBrush(QColor(16, 185, 129, 45)))
            if not path_fair.isEmpty():
                self._add_path_item(path_fair, QBrush(QColor(163, 230, 53, 45)))
            if not path_poor.isEmpty():
                self._add_path_item(path_poor, QBrush(QColor(245, 158, 11, 45)))
            if not path_bad.isEmpty():
                self._add_path_item(path_bad, QBrush(QColor(239, 68, 68, 60)))

    def _add_poly_to_path(self, path: QPainterPath, nodes: tuple[int, ...] | list[int]):
        """Helper to append a polygon coordinates path to the painter path."""
        p = self.mesh.points[list(nodes)]
        path.moveTo(p[0, 0], p[0, 1])
        for k in range(1, len(p)):
            path.lineTo(p[k, 0], p[k, 1])
        path.closeSubpath()

    def _add_path_item(self, path: QPainterPath, brush: QBrush):
        """Wrap and add the painter path into the plot scene."""
        item = QGraphicsPathItem(path)
        item.setBrush(brush)
        item.setPen(QPen(Qt.PenStyle.NoPen))
        item.setZValue(5)
        self.plot_widget.addItem(item)
        self.filled_items.append(item)
