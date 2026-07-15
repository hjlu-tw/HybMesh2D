from __future__ import annotations
import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsPathItem, QLabel
from PyQt6.QtCore import Qt, QTimer
from app.models.vtk_mesh import VTKMesh
from app.models.mesh_config import MeshConfig
from app.utils import BC_COLORS, DEFAULT_BC_COLOR
from app.views.mesh_canvas_fills_mixin import MeshCanvasFillsMixin
from app.views.mesh_canvas_bc_mixin import MeshCanvasBCMixin
from app.views.mesh_canvas_geom_mixin import MeshCanvasGeomMixin

# Dark-theme palette matching CAD Canvas
_CANVAS_BG = '#0c0d16'
_CANVAS_FG = '#6b738c'


class MeshCanvasView(MeshCanvasFillsMixin, MeshCanvasBCMixin, MeshCanvasGeomMixin, QWidget):
    """Canvas widget for visualizing 2D unstructured meshes with quality and BC filters."""

    # Above this cell count the per-element translucent fills (O(cells)
    # QPainterPath work) are skipped — the wireframe alone stays responsive.
    FILL_CELL_LIMIT = 200_000

    # (#9) Distinct colours assigned to free-form patch/group labels (those not
    # in the semantic BC_COLORS map), cycled in first-appearance order.
    _BC_PALETTE = [
        "#e63946", "#457b9d", "#2a9d8f", "#e9c46a", "#f4a261",
        "#9b5de5", "#00bbf9", "#f15bb5", "#80ed99", "#ff8fab",
    ]

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
        # When the domain comes from a custom geometry outline (not the X/Y box)
        # the rectangular domain box and its per-edge BC colours are meaningless,
        # so they are suppressed regardless of the show_* toggles.
        self.domain_is_custom = False
        # Overlay highlighting the geometry currently selected in the config list.
        self._sel_highlight_item: pg.PlotDataItem | None = None
        # The view is auto-fit once (initial content / explicit refit); after
        # that, preview refreshes (e.g. a role change) must NOT move the view, so
        # selecting a domain role doesn't yank the camera around.
        self._did_initial_fit = False

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

        # (#9) Per-segment BC/patch coloured overlays for the GEOMETRY outlines
        # (read from each geometry's .meta), so BC Preview colours the actual
        # edges by their patch/group — works for custom domains too, unlike the
        # rectangle-box preview above. `_bc_label_colors` assigns a stable colour
        # to each free-form label (known BC-type names use the shared BC_COLORS).
        self.geom_bc_items: list[pg.PlotDataItem] = []
        self._bc_label_colors: dict[str, str] = {}

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
        # Refinement-seed previews (rendered dashed/orange, kept separate from
        # the boundary geometry previews so each can be refreshed independently)
        self.seed_preview_items: list[pg.PlotDataItem] = []

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

        for item in self.geom_bc_items:
            self.plot_widget.removeItem(item)
        self.geom_bc_items.clear()

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
        has_previews = len(self.geom_preview_items) > 0 or len(self.seed_preview_items) > 0
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
            self.domain_box_item.setVisible(visible and not self.domain_is_custom)

    def set_domain_is_custom(self, is_custom: bool):
        """Record that the domain comes from a custom geometry outline (Domain
        Source = Custom geometry). Hides the rectangular box and its per-edge BC
        colours, which only describe the rectangular domain."""
        self.domain_is_custom = bool(is_custom)
        if self.domain_box_item is not None:
            self.domain_box_item.setVisible(self.show_domain_box and not self.domain_is_custom)
        # The four rectangle-edge BC colours don't apply to a custom domain, but
        # the geometry-outline patch colours (#9) do — refresh both.
        self._rebuild_bc_preview_from_config()
        self._rebuild_geom_bc_preview()

    def set_bc_coloring_visible(self, visible: bool):
        """Toggle display of colored boundary conditions."""
        self.show_bc_coloring = visible
        for item in self.bc_items:
            item.setVisible(visible)
        for item in self.bc_preview_items:
            item.setVisible(visible)
        # (#9) geometry-outline patch colours follow the same toggle; rebuild so
        # newly-turned-on colouring picks up the current .meta labels.
        self._rebuild_geom_bc_preview()

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
            # (#9) Colour the geometry outlines by their per-segment patch/group.
            self._rebuild_geom_bc_preview()
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
        self.domain_box_item.setVisible(self.show_domain_box and not self.domain_is_custom)

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
            # Stretch to the rectangular domain box only when it is actually the
            # domain (not a custom-geometry domain, where the box is hidden and
            # its stale -10..10 extent would wrongly zoom the view out).
            if (self.show_domain_box and self.mesh_config
                    and not self.domain_is_custom):
                xmin = min(xmin, self.mesh_config.domain_x_min)
                xmax = max(xmax, self.mesh_config.domain_x_max)
                ymin = min(ymin, self.mesh_config.domain_y_min)
                ymax = max(ymax, self.mesh_config.domain_y_max)
            self.plot_widget.setXRange(xmin, xmax, padding=0.06)
            self.plot_widget.setYRange(ymin, ymax, padding=0.06)
            # Pin the view: later preview refreshes won't auto-move it.
            self._did_initial_fit = True

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

        # Undirected edge list, vectorised over the tri/quad bulk (the rare
        # variable-length polygons loop). Each cell's edges are (v_k, v_{k+1});
        # sorting each pair makes them undirected so shared edges dedupe. An
        # edge used by one cell is a boundary edge, by two is interior.
        edge_arrays = []
        if self.mesh.triangles:
            T = np.asarray(self.mesh.triangles, dtype=np.int64)
            edge_arrays.append(np.stack([T, np.roll(T, -1, axis=1)], axis=2).reshape(-1, 2))
        if self.mesh.quads:
            Q = np.asarray(self.mesh.quads, dtype=np.int64)
            edge_arrays.append(np.stack([Q, np.roll(Q, -1, axis=1)], axis=2).reshape(-1, 2))
        for poly in self.mesh.polygons:
            a = np.asarray(poly, dtype=np.int64)
            edge_arrays.append(np.stack([a, np.roll(a, -1)], axis=1))

        if edge_arrays:
            all_edges = np.concatenate(edge_arrays, axis=0)
            all_edges.sort(axis=1)                                  # undirected
            uniq, counts = np.unique(all_edges, axis=0, return_counts=True)
            # Interleave endpoints -> [u0,v0,u1,v1,...] for connect='pairs'.
            seg = self.mesh.points[uniq.reshape(-1)]
            self.wireframe_item = self.plot_widget.plot(
                seg[:, 0], seg[:, 1],
                pen=pg.mkPen('#6d7faf', width=1.2),
                connect='pairs'
            )
            self.wireframe_item.setZValue(10)
            self.wireframe_item.setVisible(self.show_wireframe)
        else:
            uniq = np.empty((0, 2), dtype=np.int64)
            counts = np.empty((0,), dtype=np.int64)

        if self.mesh_config:
            self.update_domain_box(
                self.mesh_config.domain_x_min,
                self.mesh_config.domain_x_max,
                self.mesh_config.domain_y_min,
                self.mesh_config.domain_y_max
            )

        boundary_edges = uniq[counts == 1]
        if len(boundary_edges):
            self._rebuild_boundary_coloring(
                [(int(u), int(v)) for u, v in boundary_edges])

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

        if self.domain_is_custom:
            # Custom-geometry domain: the outer edges belong to the outline, NOT
            # the rectangle sides. Classifying them by bbox proximity mislabels
            # e.g. a circle's top/right arcs as YMax/XMax (=outlet). Group every
            # boundary edge as "geom" so it's coloured uniformly by BC Geom
            # instead of gaining spurious inlet/outlet colours.
            bc_groups["geom"] = list(boundary_edges)
        else:
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
