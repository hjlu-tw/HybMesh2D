from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsPathItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainterPath, QPen, QBrush
from app.models.vtk_mesh import VTKMesh

# Dark-theme palette matching CAD Canvas
_CANVAS_BG = '#0c0d16'
_CANVAS_FG = '#6b738c'

class MeshCanvasView(QWidget):
    """Canvas widget for visualizing 2D unstructured meshes."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Configure pyqtgraph styling
        pg.setConfigOption('background', _CANVAS_BG)
        pg.setConfigOption('foreground', _CANVAS_FG)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setAspectLocked(True)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        layout.addWidget(self.plot_widget)

        self.mesh: VTKMesh | None = None
        self.color_mode = "element_type"  # Options: "uniform", "element_type", "quality"

        # Wireframe plot item
        self.wireframe_item: pg.PlotDataItem | None = None

        # Filled graphics items list (Grouped paths for performance)
        self.filled_items: list[QGraphicsPathItem] = []

        # Mouse coordinate tracking overlay
        self.coord_label = pg.TextItem('', anchor=(-0.1, 1.1), color=_CANVAS_FG)
        self.plot_widget.addItem(self.coord_label, ignoreBounds=True)
        self.coord_label.setZValue(100)

        # Mouse events
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def render_mesh(self, vtk_mesh: VTKMesh):
        """Load and display the given VTK mesh."""
        self.mesh = vtk_mesh
        self._rebuild_mesh_items()
        self.auto_range()

    def clear_mesh(self):
        """Clear all mesh items from the canvas."""
        self.mesh = None
        if self.wireframe_item is not None:
            self.plot_widget.removeItem(self.wireframe_item)
            self.wireframe_item = None

        for item in self.filled_items:
            self.plot_widget.removeItem(item)
        self.filled_items.clear()
        self.coord_label.setText("")

    def set_color_mode(self, mode: str):
        """Set the rendering color mode and refresh the display."""
        if mode not in ["uniform", "element_type", "quality"]:
            raise ValueError(f"Invalid color mode: {mode}")
        self.color_mode = mode
        if self.mesh:
            self._rebuild_mesh_items()

    def auto_range(self):
        """Automatically fit the view bounds to display the full mesh."""
        if self.mesh and len(self.mesh.points) > 0:
            xmin, xmax, ymin, ymax = self.mesh.bounds
            self.plot_widget.setXRange(xmin, xmax, padding=0.05)
            self.plot_widget.setYRange(ymin, ymax, padding=0.05)

    def _rebuild_mesh_items(self):
        """Construct the wireframe and path items for drawing the mesh."""
        if not self.mesh or len(self.mesh.points) == 0:
            return

        # 1. Clear existing items
        if self.wireframe_item is not None:
            self.plot_widget.removeItem(self.wireframe_item)
            self.wireframe_item = None

        for item in self.filled_items:
            self.plot_widget.removeItem(item)
        self.filled_items.clear()

        # 2. Extract unique edges and rebuild wireframe (connect='pairs')
        edges = set()
        for tri in self.mesh.triangles:
            edges.add(tuple(sorted((tri[0], tri[1]))))
            edges.add(tuple(sorted((tri[1], tri[2]))))
            edges.add(tuple(sorted((tri[2], tri[0]))))
        for quad in self.mesh.quads:
            edges.add(tuple(sorted((quad[0], quad[1]))))
            edges.add(tuple(sorted((quad[1], quad[2]))))
            edges.add(tuple(sorted((quad[2], quad[3]))))
            edges.add(tuple(sorted((quad[3], quad[0]))))
        for poly in self.mesh.polygons:
            n = len(poly)
            for k in range(n):
                edges.add(tuple(sorted((poly[k], poly[(k + 1) % n]))))

        edge_list = list(edges)
        n_edges = len(edge_list)

        xs = np.empty(2 * n_edges, dtype=np.float64)
        ys = np.empty(2 * n_edges, dtype=np.float64)

        for idx, (u, v) in enumerate(edge_list):
            xs[2 * idx] = self.mesh.points[u, 0]
            xs[2 * idx + 1] = self.mesh.points[v, 0]
            ys[2 * idx] = self.mesh.points[u, 1]
            ys[2 * idx + 1] = self.mesh.points[v, 1]

        self.wireframe_item = self.plot_widget.plot(
            pen=pg.mkPen('#2d3345', width=1),  # Sleek dark-blue outline for elements
            connect='pairs'
        )
        self.wireframe_item.setZValue(10)

        # 3. Create painter paths and graphics path items based on color mode
        if self.color_mode == "uniform":
            path = QPainterPath()
            for tri in self.mesh.triangles:
                self._add_poly_to_path(path, tri)
            for quad in self.mesh.quads:
                self._add_poly_to_path(path, quad)
            for poly in self.mesh.polygons:
                self._add_poly_to_path(path, poly)

            # Uniform fill color: Soft deep navy/slate
            brush = QBrush(QColor(43, 61, 99, 45))
            self._add_path_item(path, brush)

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

            # Triangular elements: Cornflower blue (semi-transparent)
            if not path_tri.isEmpty():
                self._add_path_item(path_tri, QBrush(QColor(64, 150, 238, 40)))
            # Quadrilateral elements: Vibrant Indigo/Purple (semi-transparent)
            if not path_quad.isEmpty():
                self._add_path_item(path_quad, QBrush(QColor(139, 92, 246, 40)))
            # Polygonal/Other elements: Warm Amber (semi-transparent)
            if not path_poly.isEmpty():
                self._add_path_item(path_poly, QBrush(QColor(245, 158, 11, 40)))

        elif self.color_mode == "quality":
            path_good = QPainterPath()   # Aspect ratio <= 1.25
            path_fair = QPainterPath()   # 1.25 < ratio <= 1.8
            path_poor = QPainterPath()   # 1.8 < ratio <= 2.5
            path_bad = QPainterPath()    # ratio > 2.5

            ratios = self.mesh.get_element_aspect_ratios()
            
            # Combine all cells to map their indices directly to calculated aspect ratios
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

            # Colors for quality categories
            if not path_good.isEmpty():
                self._add_path_item(path_good, QBrush(QColor(16, 185, 129, 45)))  # Emerald Green
            if not path_fair.isEmpty():
                self._add_path_item(path_fair, QBrush(QColor(163, 230, 53, 45)))  # Lime Green
            if not path_poor.isEmpty():
                self._add_path_item(path_poor, QBrush(QColor(245, 158, 11, 45)))  # Orange/Amber
            if not path_bad.isEmpty():
                self._add_path_item(path_bad, QBrush(QColor(239, 68, 68, 60)))   # Red

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
        item.setPen(QPen(Qt.PenStyle.NoPen))  # No extra borders on fills to preserve wireframe color
        item.setZValue(5)  # Under the wireframe
        self.plot_widget.addItem(item)
        self.filled_items.append(item)

    def _on_mouse_moved(self, pos):
        """Update coordinates label following the mouse cursor."""
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mp = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            self.coord_label.setPos(mp.x(), mp.y())
            self.coord_label.setText(f"X: {mp.x():.4f}\nY: {mp.y():.4f}")
