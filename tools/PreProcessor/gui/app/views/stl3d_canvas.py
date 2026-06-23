"""3D viewport for the STL3d immersed-solid preprocessor.

Renders the loaded STL surface together with a live overlay of the Cartesian
domain box and a decimated grid, so the user can see the box enclosing the
geometry while editing the domain/resolution. After a run it shows the phi
field's solid cells (optionally a single z-slice) for validation.
"""
from __future__ import annotations

import numpy as np
import pyqtgraph.opengl as gl
from PyQt6.QtWidgets import QWidget, QVBoxLayout

# Cap the number of grid lines drawn per axis: the panel reports the true
# Nx/Ny/Nz, but rendering 128 planes per face is unreadable and slow.
_MAX_DIV = 16

_C_STL = (0.62, 0.71, 0.92, 1.0)
_C_BOX = (0.36, 0.78, 0.92, 1.0)     # bright cyan box edges
_C_GRID = (0.30, 0.34, 0.52, 0.55)   # dim lattice on the faces
_C_SOLID = (0.95, 0.30, 0.27, 1.0)   # phi = 1
_C_FLUID = (0.45, 0.50, 0.66, 0.25)  # phi = 0 (faint)


def _box_edge_segments(b) -> np.ndarray:
    """12 edges of the box (xmin,xmax,ymin,ymax,zmin,zmax) as line-pair verts."""
    x0, x1, y0, y1, z0, z1 = b
    c = np.array([
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
    ], dtype=np.float64)
    edges = [(0, 1), (1, 2), (2, 3), (3, 0),
             (4, 5), (5, 6), (6, 7), (7, 4),
             (0, 4), (1, 5), (2, 6), (3, 7)]
    return np.array([c[i] for e in edges for i in e], dtype=np.float64)


def _face_grid_segments(b) -> np.ndarray:
    """Decimated grid lines on the 6 box faces (line-pair vertex list)."""
    x0, x1, y0, y1, z0, z1 = b

    def pos(lo, hi):
        if hi <= lo:
            return np.array([lo])
        return np.linspace(lo, hi, _MAX_DIV)

    xs, ys, zs = pos(x0, x1), pos(y0, y1), pos(z0, z1)
    segs: list[list[float]] = []

    def add(p0, p1):
        segs.append(list(p0)); segs.append(list(p1))

    # z = const faces: lines along x (varying y) and along y (varying x)
    for z in (z0, z1):
        for y in ys:
            add((x0, y, z), (x1, y, z))
        for x in xs:
            add((x, y0, z), (x, y1, z))
        if z1 <= z0:
            break
    # x = const faces: lines along y and z
    for x in (x0, x1):
        for z in zs:
            add((x, y0, z), (x, y1, z))
        for y in ys:
            add((x, y, z0), (x, y, z1))
        if x1 <= x0:
            break
    # y = const faces: lines along x and z
    for y in (y0, y1):
        for z in zs:
            add((x0, y, z), (x1, y, z))
        for x in xs:
            add((x, y, z0), (x, y, z1))
        if y1 <= y0:
            break

    return np.array(segs, dtype=np.float64) if segs else np.empty((0, 3))


class Stl3dCanvasView(QWidget):
    """OpenGL canvas: STL surface + live domain box/grid + phi solid points."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor(12, 13, 22)        # match app dark theme
        layout.addWidget(self.view)

        self._stl_item: gl.GLMeshItem | None = None
        self._box_item: gl.GLLinePlotItem | None = None
        self._grid_item: gl.GLLinePlotItem | None = None
        self._solid_item: gl.GLScatterPlotItem | None = None
        self._fluid_item: gl.GLScatterPlotItem | None = None

        self._bbox = None              # last STL/domain bbox for camera fit
        self._phi_pts: np.ndarray | None = None
        self._phi_val: np.ndarray | None = None
        self._z_levels: np.ndarray | None = None
        self._slice_k: int | None = None   # None => show all z-layers

        self._show = {"stl": True, "box": True, "grid": True,
                      "solid": True, "fluid": False}

    # ------------------------------------------------------------------ #
    # STL surface
    # ------------------------------------------------------------------ #
    def set_stl(self, tris: np.ndarray | None):
        """Set the STL surface from an (N, 3, 3) triangle-vertex array."""
        if self._stl_item is not None:
            self.view.removeItem(self._stl_item)
            self._stl_item = None
        if tris is None or len(tris) == 0:
            return
        verts = tris.reshape(-1, 3).astype(np.float32)
        faces = np.arange(len(verts), dtype=np.uint32).reshape(-1, 3)
        md = gl.MeshData(vertexes=verts, faces=faces)
        self._stl_item = gl.GLMeshItem(
            meshdata=md, smooth=False, drawEdges=True,
            edgeColor=(0.20, 0.24, 0.40, 1.0), color=_C_STL,
            shader="shaded", glOptions="opaque")
        self._stl_item.setVisible(self._show["stl"])
        self.view.addItem(self._stl_item)

    # ------------------------------------------------------------------ #
    # Domain box + grid (live overlay)
    # ------------------------------------------------------------------ #
    def set_domain(self, bounds):
        """Update the Cartesian domain box + decimated face grid."""
        self._bbox = tuple(float(v) for v in bounds)
        box = _box_edge_segments(self._bbox)
        if self._box_item is None:
            self._box_item = gl.GLLinePlotItem(
                pos=box, color=_C_BOX, width=2.0, mode="lines", antialias=True)
            self._box_item.setVisible(self._show["box"])
            self.view.addItem(self._box_item)
        else:
            self._box_item.setData(pos=box, color=_C_BOX, width=2.0, mode="lines")

        grid = _face_grid_segments(self._bbox)
        if self._grid_item is None:
            self._grid_item = gl.GLLinePlotItem(
                pos=grid, color=_C_GRID, width=1.0, mode="lines", antialias=False)
            self._grid_item.setVisible(self._show["grid"])
            self.view.addItem(self._grid_item)
        else:
            self._grid_item.setData(pos=grid, color=_C_GRID, width=1.0, mode="lines")

    # ------------------------------------------------------------------ #
    # phi result
    # ------------------------------------------------------------------ #
    def set_phi(self, points: np.ndarray, phi: np.ndarray):
        """Store the phi field and render solid (and optional fluid) cells."""
        self._phi_pts = np.asarray(points, dtype=np.float64)
        self._phi_val = np.asarray(phi, dtype=np.float64)
        self._z_levels = np.unique(np.round(self._phi_pts[:, 2], 9)) \
            if len(self._phi_pts) else np.array([])
        self._slice_k = None
        self._refresh_phi()

    def clear_phi(self):
        self._phi_pts = self._phi_val = None
        self._z_levels = None
        for attr in ("_solid_item", "_fluid_item"):
            item = getattr(self, attr)
            if item is not None:
                self.view.removeItem(item)
                setattr(self, attr, None)

    @property
    def n_z_levels(self) -> int:
        return int(len(self._z_levels)) if self._z_levels is not None else 0

    def set_slice(self, k: int | None):
        """Show only z-layer ``k`` (0-based), or all layers when None."""
        self._slice_k = k
        self._refresh_phi()

    def _refresh_phi(self):
        for attr in ("_solid_item", "_fluid_item"):
            item = getattr(self, attr)
            if item is not None:
                self.view.removeItem(item)
                setattr(self, attr, None)
        if self._phi_pts is None or len(self._phi_pts) == 0:
            return

        mask = np.ones(len(self._phi_pts), dtype=bool)
        if (self._slice_k is not None and self._z_levels is not None
                and 0 <= self._slice_k < len(self._z_levels)):
            zsel = self._z_levels[self._slice_k]
            mask = np.isclose(np.round(self._phi_pts[:, 2], 9), zsel)

        pts = self._phi_pts[mask]
        val = self._phi_val[mask]
        solid = pts[val > 0.5].astype(np.float32)
        fluid = pts[val <= 0.5].astype(np.float32)

        if len(solid):
            self._solid_item = gl.GLScatterPlotItem(
                pos=solid, color=_C_SOLID, size=6.0, pxMode=True)
            self._solid_item.setVisible(self._show["solid"])
            self.view.addItem(self._solid_item)
        if len(fluid):
            self._fluid_item = gl.GLScatterPlotItem(
                pos=fluid, color=_C_FLUID, size=3.0, pxMode=True)
            self._fluid_item.setVisible(self._show["fluid"])
            self.view.addItem(self._fluid_item)

    # ------------------------------------------------------------------ #
    # Visibility + camera
    # ------------------------------------------------------------------ #
    def set_visibility(self, **kwargs):
        self._show.update({k: bool(v) for k, v in kwargs.items() if k in self._show})
        pairs = [("stl", self._stl_item), ("box", self._box_item),
                 ("grid", self._grid_item), ("solid", self._solid_item),
                 ("fluid", self._fluid_item)]
        for key, item in pairs:
            if item is not None:
                item.setVisible(self._show[key])

    def fit_view(self):
        """Frame the camera on the current domain box (or STL bbox)."""
        if self._bbox is None:
            return
        x0, x1, y0, y1, z0, z1 = self._bbox
        cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
        span = max(x1 - x0, y1 - y0, z1 - z0, 1e-6)
        try:
            from pyqtgraph import Vector
            self.view.opts["center"] = Vector(cx, cy, cz)
        except Exception:
            pass
        self.view.setCameraPosition(distance=span * 2.2, elevation=28, azimuth=-60)
