from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsPathItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainterPath, QPen, QBrush
from app.models.vtk_mesh import VTKMesh
from app.models.mesh_config import MeshConfig

# Dark-theme palette matching CAD Canvas
_CANVAS_BG = '#0c0d16'
_CANVAS_FG = '#6b738c'

class MeshCanvasView(QWidget):
    """Canvas widget for visualizing 2D unstructured meshes with quality and BC filters."""

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
        self.mesh_config: MeshConfig | None = None
        self.color_mode = "element_type"  # Options: "uniform", "element_type", "quality_aspect", "quality_skewness"

        self.show_wireframe = True
        self.show_domain_box = True
        self.show_bc_coloring = True

        # Wireframe plot item
        self.wireframe_item: pg.PlotDataItem | None = None

        # Bounding box plot item
        self.domain_box_item: pg.PlotDataItem | None = None

        # Filled graphics items list (Grouped paths for performance)
        self.filled_items: list[QGraphicsPathItem] = []

        # Boundary condition colored items
        self.bc_items: list[pg.PlotDataItem] = []

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

        if self.domain_box_item is not None:
            self.plot_widget.removeItem(self.domain_box_item)
            self.domain_box_item = None

        for item in self.bc_items:
            self.plot_widget.removeItem(item)
        self.bc_items.clear()

        for item in self.filled_items:
            self.plot_widget.removeItem(item)
        self.filled_items.clear()
        self.coord_label.setText("")

    def set_color_mode(self, mode: str):
        """Set the rendering color mode and refresh the display."""
        valid_modes = ["uniform", "element_type", "quality_aspect", "quality_skewness"]
        if mode not in valid_modes:
            raise ValueError(f"Invalid color mode: {mode}")
        self.color_mode = mode
        if self.mesh:
            self._rebuild_mesh_items()

    def set_wireframe_visible(self, visible: bool):
        """Toggle display of the mesh wireframe edges."""
        self.show_wireframe = visible
        if self.wireframe_item is not None:
            self.wireframe_item.setVisible(visible)

    def set_domain_box_visible(self, visible: bool):
        """Toggle display of the domain bounding box."""
        self.show_domain_box = visible
        if self.domain_box_item is not None:
            self.domain_box_item.setVisible(visible)

    def set_bc_coloring_visible(self, visible: bool):
        """Toggle display of colored boundary conditions."""
        self.show_bc_coloring = visible
        for item in self.bc_items:
            item.setVisible(visible)

    def update_mesh_config(self, cfg: MeshConfig | None):
        """Sync MeshConfig mapping for domain box and boundary conditions rendering."""
        self.mesh_config = cfg
        if self.mesh_config and self.mesh:
            self.update_domain_box(
                self.mesh_config.domain_x_min,
                self.mesh_config.domain_x_max,
                self.mesh_config.domain_y_min,
                self.mesh_config.domain_y_max
            )
            self._rebuild_mesh_items()

    def update_domain_box(self, xmin: float, xmax: float, ymin: float, ymax: float):
        """Render calculations domain box coordinates as a dashed border."""
        xs = [xmin, xmax, xmax, xmin, xmin]
        ys = [ymin, ymin, ymax, ymax, ymin]
        if self.domain_box_item is None:
            self.domain_box_item = self.plot_widget.plot(
                xs, ys,
                pen=pg.mkPen('#e9c46a', width=1.5, style=Qt.PenStyle.DashLine)
            )
            self.domain_box_item.setZValue(15)
        else:
            self.domain_box_item.setData(xs, ys)
        self.domain_box_item.setVisible(self.show_domain_box)

    def auto_range(self):
        """Automatically fit the view bounds to display the full mesh."""
        if self.mesh and len(self.mesh.points) > 0:
            xmin, xmax, ymin, ymax = self.mesh.bounds
            # If domain box is active and mesh config exists, stretch slightly to fit domain
            if self.show_domain_box and self.mesh_config:
                xmin = min(xmin, self.mesh_config.domain_x_min)
                xmax = max(xmax, self.mesh_config.domain_x_max)
                ymin = min(ymin, self.mesh_config.domain_y_min)
                ymax = max(ymax, self.mesh_config.domain_y_max)
            self.plot_widget.setXRange(xmin, xmax, padding=0.06)
            self.plot_widget.setYRange(ymin, ymax, padding=0.06)

    def _rebuild_mesh_items(self):
        """Construct wireframe, quality path fills, and boundary condition lines."""
        if not self.mesh or len(self.mesh.points) == 0:
            return

        # 1. Clear existing items
        if self.wireframe_item is not None:
            self.plot_widget.removeItem(self.wireframe_item)
            self.wireframe_item = None

        for item in self.filled_items:
            self.plot_widget.removeItem(item)
        self.filled_items.clear()

        for item in self.bc_items:
            self.plot_widget.removeItem(item)
        self.bc_items.clear()

        # 2. Rebuild wireframe (connect='pairs')
        edges = set()
        edge_cell_count = {}

        def register_edges(nodes):
            n = len(nodes)
            for k in range(n):
                edge = tuple(sorted((nodes[k], nodes[(k + 1) % n])))
                edges.add(edge)
                edge_cell_count[edge] = edge_cell_count.get(edge, 0) + 1

        for tri in self.mesh.triangles:
            register_edges(tri)
        for quad in self.mesh.quads:
            register_edges(quad)
        for poly in self.mesh.polygons:
            register_edges(poly)

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
            xs, ys,
            pen=pg.mkPen('#2d3345', width=1),
            connect='pairs'
        )
        self.wireframe_item.setZValue(10)
        self.wireframe_item.setVisible(self.show_wireframe)

        # 3. Create domain box if config exists
        if self.mesh_config:
            self.update_domain_box(
                self.mesh_config.domain_x_min,
                self.mesh_config.domain_x_max,
                self.mesh_config.domain_y_min,
                self.mesh_config.domain_y_max
            )

        # 4. Paint fills based on color mode
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
                self._add_path_item(path_good, QBrush(QColor(16, 185, 129, 45)))  # Emerald
            if not path_fair.isEmpty():
                self._add_path_item(path_fair, QBrush(QColor(163, 230, 53, 45)))  # Lime
            if not path_poor.isEmpty():
                self._add_path_item(path_poor, QBrush(QColor(245, 158, 11, 45)))  # Orange
            if not path_bad.isEmpty():
                self._add_path_item(path_bad, QBrush(QColor(239, 68, 68, 60)))   # Red

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
                self._add_path_item(path_good, QBrush(QColor(16, 185, 129, 45)))  # Emerald
            if not path_fair.isEmpty():
                self._add_path_item(path_fair, QBrush(QColor(163, 230, 53, 45)))  # Lime
            if not path_poor.isEmpty():
                self._add_path_item(path_poor, QBrush(QColor(245, 158, 11, 45)))  # Orange
            if not path_bad.isEmpty():
                self._add_path_item(path_bad, QBrush(QColor(239, 68, 68, 60)))   # Red

        # 5. Paint boundary conditions with colors
        boundary_edges = [edge for edge, count in edge_cell_count.items() if count == 1]
        if boundary_edges:
            self._rebuild_boundary_coloring(boundary_edges)

    def _rebuild_boundary_coloring(self, boundary_edges: list[tuple[int, int]]):
        """Categorize boundary edges into domain limits XMin/XMax/YMin/YMax or Geom, and draw them colored."""
        g_xmin, g_xmax, g_ymin, g_ymax = self.mesh.bounds
        dx = g_xmax - g_xmin
        dy = g_ymax - g_ymin
        tol = 0.005 * max(dx, dy)

        bc_colors = {
            "wall": '#ef4444',       # Red
            "farfield": '#06b6d4',   # Cyan
            "inlet": '#22c55e',      # Green
            "outlet": '#3b82f6',     # Blue
            "symmetry": '#f97316',   # Orange
        }
        default_bc_color = '#9ca3af'  # Gray

        bc_names = {
            "xmin": "wall",
            "xmax": "wall",
            "ymin": "wall",
            "ymax": "wall",
            "geom": "wall"
        }
        if self.mesh_config:
            bc_names["xmin"] = self.mesh_config.bc_xmin.lower()
            bc_names["xmax"] = self.mesh_config.bc_xmax.lower()
            bc_names["ymin"] = self.mesh_config.bc_ymin.lower()
            bc_names["ymax"] = self.mesh_config.bc_ymax.lower()
            bc_names["geom"] = self.mesh_config.bc_geom.lower()

        bc_groups = {"xmin": [], "xmax": [], "ymin": [], "ymax": [], "geom": []}

        for u, v in boundary_edges:
            p1 = self.mesh.points[u]
            p2 = self.mesh.points[v]

            if abs(p1[0] - g_xmin) < tol and abs(p2[0] - g_xmin) < tol:
                bc_groups["xmin"].append((u, v))
            elif abs(p1[0] - g_xmax) < tol and abs(p2[0] - g_xmax) < tol:
                bc_groups["xmax"].append((u, v))
            elif abs(p1[1] - g_ymin) < tol and abs(p2[1] - g_ymin) < tol:
                bc_groups["ymin"].append((u, v))
            elif abs(p1[1] - g_ymax) < tol and abs(p2[1] - g_ymax) < tol:
                bc_groups["ymax"].append((u, v))
            else:
                bc_groups["geom"].append((u, v))

        for key, edge_list in bc_groups.items():
            if not edge_list:
                continue

            xs_bc = np.empty(2 * len(edge_list), dtype=np.float64)
            ys_bc = np.empty(2 * len(edge_list), dtype=np.float64)
            for idx, (u, v) in enumerate(edge_list):
                xs_bc[2 * idx] = self.mesh.points[u, 0]
                xs_bc[2 * idx + 1] = self.mesh.points[v, 0]
                ys_bc[2 * idx] = self.mesh.points[u, 1]
                ys_bc[2 * idx + 1] = self.mesh.points[v, 1]

            bc_type = bc_names[key]
            color = bc_colors.get(bc_type, default_bc_color)

            bc_item = self.plot_widget.plot(
                xs_bc, ys_bc,
                pen=pg.mkPen(color, width=3),
                connect='pairs'
            )
            bc_item.setZValue(20)
            bc_item.setVisible(self.show_bc_coloring)
            self.plot_widget.addItem(bc_item)
            self.bc_items.append(bc_item)

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

    def _on_mouse_moved(self, pos):
        """Update coordinates label following the mouse cursor."""
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mp = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            self.coord_label.setPos(mp.x(), mp.y())
            self.coord_label.setText(f"X: {mp.x():.4f}\nY: {mp.y():.4f}")
