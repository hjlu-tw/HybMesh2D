from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsPathItem, QLabel
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPainterPath, QPen, QBrush
from app.models.vtk_mesh import VTKMesh
from app.models.mesh_config import MeshConfig
from app.utils import BC_COLORS, DEFAULT_BC_COLOR

# Dark-theme palette matching CAD Canvas
_CANVAS_BG = '#0c0d16'
_CANVAS_FG = '#6b738c'

class GeomLoaderThread(QThread):
    """Loads multiple geometry files in a background thread to prevent UI freezing."""
    loaded_signal = pyqtSignal(int, list)  # (generation token, results)

    def __init__(self, geom_files: list[str], token: int = 0):
        super().__init__()
        self.geom_files = geom_files
        self.token = token

    def run(self):
        import os
        results = []
        for f in self.geom_files:
            if not f or not os.path.exists(f):
                continue
            try:
                pts = np.loadtxt(f)
                if len(pts) > 0:
                    results.append(pts)
            except Exception as e:
                print(f"Error loading preview geometry background {f}: {e}")
        self.loaded_signal.emit(self.token, results)

class MeshCanvasView(QWidget):
    """Canvas widget for visualizing 2D unstructured meshes with quality and BC filters."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

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

        # Boundary condition colored items (from actual mesh boundary edges)
        self.bc_items: list[pg.PlotDataItem] = []

        # BC preview items drawn directly from domain box (no mesh needed)
        self.bc_preview_items: list[pg.PlotDataItem] = []

        # Mouse coordinate tracking overlay
        self.coord_label = pg.TextItem('', anchor=(-0.1, 1.1), color=_CANVAS_FG)
        self.plot_widget.addItem(self.coord_label, ignoreBounds=True)
        self.coord_label.setZValue(100)

        # Mouse events
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Mouse-coordinate throttle timer
        self._mouse_timer = QTimer(self)
        self._mouse_timer.setSingleShot(True)
        self._mouse_timer.timeout.connect(self._throttled_mouse_update)
        self._last_mouse_pos = None

        # Geometry previews
        self.geom_preview_items: list[pg.PlotDataItem] = []

        # Empty state guide label
        self.empty_label = QLabel("Please load geometry data in the CAD tab first\nor load config file.", self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet("""
            color: #6a7aaa;
            font-size: 13px;
            font-weight: bold;
            background: #0f111a;
            border: 2px dashed #2d3356;
            border-radius: 8px;
            padding: 15px;
        """)
        self._update_empty_state()

    def render_mesh(self, vtk_mesh: VTKMesh, fit_view: bool = False):
        """Load and display the given VTK mesh."""
        self.mesh = vtk_mesh
        self._rebuild_mesh_items()
        if fit_view:
            self.auto_range()
        self._update_empty_state()

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

        for item in self.bc_preview_items:
            self.plot_widget.removeItem(item)
        self.bc_preview_items.clear()

        for item in self.filled_items:
            self.plot_widget.removeItem(item)
        self.filled_items.clear()
        self.coord_label.setText("")
        self._update_empty_state()

    def clear_mesh_results(self):
        """Clear only the mesh-related output components, leaving inputs (geometry previews, domain box, BC previews) intact."""
        self.mesh = None
        if self.wireframe_item is not None:
            self.plot_widget.removeItem(self.wireframe_item)
            self.wireframe_item = None

        for item in self.bc_items:
            self.plot_widget.removeItem(item)
        self.bc_items.clear()

        for item in self.filled_items:
            self.plot_widget.removeItem(item)
        self.filled_items.clear()
        self._update_empty_state()


    def update_geometry_previews(self, geom_files: list[str]):
        """Load and display the input boundary geometries as preview lines using a background thread."""
        for item in self.geom_preview_items:
            self.plot_widget.removeItem(item)
        self.geom_preview_items.clear()

        # Bump the generation token so any in-flight loader's result is ignored
        # once superseded. We do NOT block (wait()) on the old thread here, so
        # the UI never freezes while a previous load is still finishing.
        self._geom_loader_gen = getattr(self, "_geom_loader_gen", 0) + 1
        token = self._geom_loader_gen
        # Keep references to running threads so they are not garbage-collected
        # mid-run (which would crash with "QThread destroyed while running").
        self._geom_loader_threads = [
            t for t in getattr(self, "_geom_loader_threads", []) if t.isRunning()]

        thread = GeomLoaderThread(geom_files, token)
        thread.loaded_signal.connect(self._on_geometry_previews_loaded)
        thread.finished.connect(lambda t=thread: self._drop_geom_loader_thread(t))
        self._geom_loader_threads.append(thread)
        self._geom_loader_thread = thread  # last thread (used by close handler)
        thread.start()

    def _drop_geom_loader_thread(self, thread):
        threads = getattr(self, "_geom_loader_threads", [])
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
                pass
        self._error_highlight_items = []



    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.empty_label.setGeometry(
            (self.width() - 420) // 2,
            (self.height() - 100) // 2,
            420,
            100
        )

    def _update_empty_state(self):
        has_mesh = self.mesh is not None and len(self.mesh.points) > 0
        has_previews = len(self.geom_preview_items) > 0
        self.empty_label.setVisible(not (has_mesh or has_previews))

    def set_color_mode(self, mode: str):
        """Set the rendering color mode and refresh the display."""
        valid_modes = ["uniform", "element_type", "quality_aspect", "quality_skewness"]
        if mode not in valid_modes:
            raise ValueError(f"Invalid color mode: {mode}")
        self.color_mode = mode
        if self.mesh:
            self._rebuild_mesh_fills()

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
        for item in self.bc_preview_items:
            item.setVisible(visible)

    def update_mesh_config(self, cfg: MeshConfig | None, fit_view: bool = False):
        """Sync MeshConfig mapping for domain box and boundary conditions rendering."""
        self.mesh_config = cfg
        if self.mesh_config:
            self.update_domain_box(
                self.mesh_config.domain_x_min,
                self.mesh_config.domain_x_max,
                self.mesh_config.domain_y_min,
                self.mesh_config.domain_y_max
            )
            # Always draw BC-colored segments on domain edges (preview, even without mesh)
            self._rebuild_bc_preview_from_config()
            # Update geometry previews from config
            self.update_geometry_previews(self.mesh_config.geom_files)
            if self.mesh:
                self._rebuild_mesh_items()
            elif fit_view:
                self.auto_range()

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
        """Automatically fit the view bounds to display the full mesh or geometry previews."""
        xmin, xmax, ymin, ymax = None, None, None, None
        
        if self.mesh and len(self.mesh.points) > 0:
            xmin, xmax, ymin, ymax = self.mesh.bounds
        elif self.geom_preview_items:
            xs, ys = [], []
            for item in self.geom_preview_items:
                data = item.getData()
                if data and len(data[0]) > 0:
                    xs.extend(data[0])
                    ys.extend(data[1])
            if xs and ys:
                xmin, xmax = min(xs), max(xs)
                ymin, ymax = min(ys), max(ys)

        if xmin is not None:
            # If domain box is active and mesh config exists, stretch slightly to fit domain
            if self.show_domain_box and self.mesh_config:
                xmin = min(xmin, self.mesh_config.domain_x_min)
                xmax = max(xmax, self.mesh_config.domain_x_max)
                ymin = min(ymin, self.mesh_config.domain_y_min)
                ymax = max(ymax, self.mesh_config.domain_y_max)
            self.plot_widget.setXRange(xmin, xmax, padding=0.06)
            self.plot_widget.setYRange(ymin, ymax, padding=0.06)

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

        for xs, ys, bc_val in sides:
            color_str = BC_COLORS.get(bc_val, DEFAULT_BC_COLOR)
            item = self.plot_widget.plot(
                xs, ys,
                pen=pg.mkPen(color_str, width=4, style=Qt.PenStyle.SolidLine)
            )
            item.setZValue(18)
            item.setVisible(self.show_bc_coloring)
            self.bc_preview_items.append(item)

    def _rebuild_mesh_geometry(self):
        """Construct only the wireframe, domain box, and boundary condition lines."""
        if self.wireframe_item is not None:
            self.plot_widget.removeItem(self.wireframe_item)
            self.wireframe_item = None

        for item in self.bc_items:
            self.plot_widget.removeItem(item)
        self.bc_items.clear()

        if not self.mesh or len(self.mesh.points) == 0:
            return

        # Connect-pairs edge list construction
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
            pen=pg.mkPen('#6d7faf', width=1.2),
            connect='pairs'
        )
        self.wireframe_item.setZValue(10)
        self.wireframe_item.setVisible(self.show_wireframe)

        if self.mesh_config:
            self.update_domain_box(
                self.mesh_config.domain_x_min,
                self.mesh_config.domain_x_max,
                self.mesh_config.domain_y_min,
                self.mesh_config.domain_y_max
            )

        boundary_edges = [edge for edge, count in edge_cell_count.items() if count == 1]
        if boundary_edges:
            self._rebuild_boundary_coloring(boundary_edges)

    def _rebuild_mesh_fills(self):
        """Construct only the quality/element colored path fills."""
        for item in self.filled_items:
            self.plot_widget.removeItem(item)
        self.filled_items.clear()

        if not self.mesh or len(self.mesh.points) == 0:
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

    def _rebuild_mesh_items(self):
        """Construct wireframe, quality path fills, and boundary condition lines."""
        self._rebuild_mesh_geometry()
        self._rebuild_mesh_fills()

    def _rebuild_boundary_coloring(self, boundary_edges: list[tuple[int, int]]):
        """Categorize boundary edges into domain limits XMin/XMax/YMin/YMax or Geom, and draw them colored."""
        g_xmin, g_xmax, g_ymin, g_ymax = self.mesh.bounds
        dx = g_xmax - g_xmin
        dy = g_ymax - g_ymin
        tol = 0.005 * max(dx, dy)

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
            color = BC_COLORS.get(bc_type, DEFAULT_BC_COLOR)

            bc_item = self.plot_widget.plot(
                xs_bc, ys_bc,
                pen=pg.mkPen(color, width=3),
                connect='pairs'
            )
            bc_item.setZValue(20)
            bc_item.setVisible(self.show_bc_coloring)
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
        """Update coordinates label following the mouse cursor with throttling."""
        self._last_mouse_pos = pos
        if not self._mouse_timer.isActive():
            self._mouse_timer.start(16)

    def _throttled_mouse_update(self):
        pos = self._last_mouse_pos
        if pos is not None and self.plot_widget.sceneBoundingRect().contains(pos):
            mp = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            self.coord_label.setPos(mp.x(), mp.y())
            self.coord_label.setText(f"X: {mp.x():.4f}\nY: {mp.y():.4f}")
