"""3D viewport for the STL3d immersed-solid preprocessor.

Renders the loaded STL surface together with a live overlay of the Cartesian
domain box, so the user can see the box enclosing the geometry while editing
the domain/resolution. After a run it shows the phi field's solid cells
(optionally a single z-slice) for validation.
"""
from __future__ import annotations

import numpy as np
import pyqtgraph.opengl as gl
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QPushButton, QSpinBox,
)

from app.services.phi_quality import FIT_OK_CELLS

_C_STL = (0.62, 0.71, 0.92, 1.0)
_C_BOX = (0.36, 0.78, 0.92, 1.0)     # bright cyan box edges
_C_SOLID = (0.95, 0.30, 0.27, 1.0)   # phi = 1
_C_FLUID = (0.45, 0.50, 0.66, 0.25)  # phi = 0 (faint)

# Fit-deviation heatmap reference scale: deviation is shown in cell counts
# (dev / h), green at 0 → red at this many cells. Shares the fit verdict's
# "acceptable" threshold so the heatmap saturates exactly where the report says
# the surface is under-resolved.
_DEV_VMAX_CELLS = FIT_OK_CELLS

# RdYlGn_r colormap, imported lazily and cached: matplotlib is heavy and is only
# needed once the deviation heatmap is first drawn, never at GUI startup.
_DEV_CMAP = None


def _dev_cmap():
    global _DEV_CMAP
    if _DEV_CMAP is None:
        from matplotlib import colormaps
        _DEV_CMAP = colormaps["RdYlGn_r"]
    return _DEV_CMAP


def _bar_button(text: str, *, base: str, border: str, hover: str,
                padding: str = "3px 10px", checked_bg: str | None = None) -> QPushButton:
    """A compact display-bar push button. Centralises the toolbar QSS so the four
    buttons (2D/3D, Fit View, Clear φ, Clear All) share one style definition."""
    qss = (f"QPushButton{{background:{base};color:#dde2ff;border:1px solid {border};"
           f"border-radius:4px;padding:{padding};font-weight:bold;font-size:11px;}}"
           f"QPushButton:hover{{border-color:{hover};}}")
    if checked_bg:
        qss += f"QPushButton:checked{{background:{checked_bg};border-color:{hover};color:#fff;}}"
    b = QPushButton(text)
    b.setStyleSheet(qss)
    return b


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


class _GLView(gl.GLViewWidget):
    """GLViewWidget with a 2D mode whose mouse behaviour matches the CAD and
    Result canvases: left-drag pans, the wheel zooms about the cursor, and the
    camera is locked top-down (no orbit). 3D restores the normal orbit widget.

    The default is 2D — the panel's view button switches to 3D on demand.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mode_2d = True

    def set_2d(self, on: bool):
        self._mode_2d = bool(on)

    def mouseMoveEvent(self, ev):
        if not self._mode_2d:
            return super().mouseMoveEvent(ev)
        # 2D: drag pans in the view plane (grab-pan, like the CAD/Result canvas);
        # never orbit. 'view' (not 'view-upright') is required because the latter
        # degenerates when the camera looks straight down (elevation 90).
        lpos = ev.position() if hasattr(ev, "position") else ev.localPos()
        if not hasattr(self, "mousePos"):
            self.mousePos = lpos
        diff = lpos - self.mousePos
        self.mousePos = lpos
        if ev.buttons() != Qt.MouseButton.NoButton:
            self.pan(diff.x(), diff.y(), 0, relative="view")
        ev.accept()

    def wheelEvent(self, ev):
        if not self._mode_2d:
            return super().wheelEvent(ev)
        delta = ev.angleDelta().y() or ev.angleDelta().x()
        if delta == 0:
            ev.accept()
            return
        # Zoom about the cursor (CAD/Result convention): record the world point
        # under the cursor, change the zoom, then shift the look-at center so the
        # same world point stays under the cursor.
        pos = ev.position() if hasattr(ev, "position") else ev.posF()
        zc = self.opts["center"].z()
        before = self._world_on_z(pos.x(), pos.y(), zc)
        self.opts["distance"] = max(self.opts["distance"] * (0.999 ** delta), 1e-9)
        after = self._world_on_z(pos.x(), pos.y(), zc)
        if before is not None and after is not None:
            from pyqtgraph import Vector
            c = self.opts["center"]
            self.opts["center"] = Vector(c.x() + (before[0] - after[0]),
                                         c.y() + (before[1] - after[1]), c.z())
        self.update()
        ev.accept()

    def _world_on_z(self, sx, sy, zplane):
        """Unproject screen pixel (sx, sy) onto the world plane z = ``zplane``."""
        from PyQt6.QtGui import QVector4D
        w, h = self.width(), self.height()
        if w == 0 or h == 0:
            return None
        pv = self.projectionMatrix() * self.viewMatrix()
        inv, ok = pv.inverted()
        if not ok:
            return None
        ndc_x = 2.0 * sx / w - 1.0
        ndc_y = 1.0 - 2.0 * sy / h
        near = inv.map(QVector4D(ndc_x, ndc_y, -1.0, 1.0))
        far = inv.map(QVector4D(ndc_x, ndc_y, 1.0, 1.0))
        if near.w() == 0 or far.w() == 0:
            return None
        nx, ny, nz = near.x() / near.w(), near.y() / near.w(), near.z() / near.w()
        fx, fy, fz = far.x() / far.w(), far.y() / far.w(), far.z() / far.w()
        dz = fz - nz
        if abs(dz) < 1e-12:
            return None
        t = (zplane - nz) / dz
        return (nx + (fx - nx) * t, ny + (fy - ny) * t)


class Stl3dCanvasView(QWidget):
    """OpenGL canvas: STL surface + live domain box/grid + phi solid points."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stl_item: gl.GLMeshItem | None = None
        self._box_item: gl.GLLinePlotItem | None = None
        self._solid_item: gl.GLScatterPlotItem | None = None
        self._fluid_item: gl.GLScatterPlotItem | None = None
        self._dev_item: gl.GLScatterPlotItem | None = None

        self._bbox = None              # last STL/domain bbox for camera fit
        self._phi_pts: np.ndarray | None = None
        self._phi_val: np.ndarray | None = None
        self._z_levels: np.ndarray | None = None
        self._slice_k: int | None = None   # None => show all z-layers

        self._dev_pts: np.ndarray | None = None   # fit-deviation heatmap
        self._dev_val: np.ndarray | None = None
        self._dev_h: float = 1.0

        self._show = {"stl": True, "box": True, "solid": True,
                      "fluid": False, "dev": False}

        # ── Top display bar (moved here from the sidebar) ──────────────────
        layout.addWidget(self._build_display_bar())

        self.view = _GLView()
        self.view.setBackgroundColor(12, 13, 22)        # match app dark theme
        self.view.setCameraPosition(elevation=90, azimuth=-90)  # default 2D top-down
        layout.addWidget(self.view, stretch=1)

    # ------------------------------------------------------------------ #
    def _build_display_bar(self) -> QWidget:
        """A toolbar with the visibility toggles, z-slice picker and Fit View —
        the controls that used to live in the sidebar's Display section."""
        bar = QWidget()
        bar.setStyleSheet("background: #06070d; border-bottom: 1px solid #1c1e36;")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(8, 4, 8, 4)
        hl.setSpacing(8)

        def _check(text, tip, on):
            c = QCheckBox(text)
            c.setToolTip(tip)
            c.setChecked(on)
            c.setStyleSheet("color:#a0a8c0; font-size:11px;")
            c.toggled.connect(self.apply_display)
            return c

        self.show_stl_cb = _check("STL surface", "Show the STL surface", True)
        self.show_box_cb = _check("Domain box", "Show the Cartesian domain box", True)
        self.show_solid_cb = _check("Solid (φ=1)", "Show marked solid cells from the last run", True)
        self.show_fluid_cb = _check("Fluid (φ=0)", "Show fluid cells (faint) from the last run", False)
        self.show_dev_cb = _check(
            "Fit Δ", "Show the STL↔φ surface-deviation heatmap from Check Fit "
            f"(green = within a cell, red ≥ {FIT_OK_CELLS:g} cells off)", False)
        for cb in (self.show_stl_cb, self.show_box_cb,
                   self.show_solid_cb, self.show_fluid_cb, self.show_dev_cb):
            hl.addWidget(cb)

        sep = QWidget(); sep.setFixedWidth(1); sep.setFixedHeight(16)
        sep.setStyleSheet("background-color: #1c1e36;")
        hl.addWidget(sep)

        self.slice_all_cb = _check("All z-layers", "Show every z-layer, or isolate one below", True)
        hl.addWidget(self.slice_all_cb)
        klbl = QLabel("k="); klbl.setStyleSheet("color:#7a82a0; font-size:11px;")
        hl.addWidget(klbl)
        self.slice_spin = QSpinBox()
        self.slice_spin.setRange(0, 0)
        self.slice_spin.setEnabled(False)
        self.slice_spin.setToolTip("z-layer index to isolate")
        self.slice_spin.setStyleSheet(
            "QSpinBox{background:#181b30;color:#dde2ff;border:1px solid #2d3356;"
            "border-radius:4px;padding:2px 4px;font-size:11px;max-width:60px;}")
        self.slice_spin.valueChanged.connect(self.apply_display)
        hl.addWidget(self.slice_spin)

        hl.addStretch()

        # 2D/3D view toggle. Default is 2D (top-down, pan/zoom only, like the CAD
        # and Result canvases); checking it switches to the 3D orbit view. The
        # label shows the current mode.
        self.view2d_btn = _bar_button(
            "2D", base="#1d2a3a", border="#2d3356", hover="#5a9ad4",
            padding="3px 12px", checked_bg="#27406a")
        self.view2d_btn.setCheckable(True)
        self.view2d_btn.setToolTip(
            "2D top-down view (pan & zoom only) ↔ 3D orbit view")
        self.view2d_btn.toggled.connect(self._on_view2d_toggled)
        hl.addWidget(self.view2d_btn)

        self.fit_btn = _bar_button("Fit View", base="#1d2a3a", border="#2d3356",
                                   hover="#5a9ad4")
        self.fit_btn.setToolTip("Frame the camera on the domain box")
        self.fit_btn.clicked.connect(self.fit_view)
        hl.addWidget(self.fit_btn)

        self.clear_phi_btn = _bar_button("Clear φ", base="#301a1a",
                                         border="#5d2d2d", hover="#ef4444")
        self.clear_phi_btn.setToolTip("Clear only the phi result (keep the STL surface)")
        hl.addWidget(self.clear_phi_btn)
        self.clear_btn = _bar_button("Clear All", base="#301a1a",
                                     border="#5d2d2d", hover="#ef4444")
        self.clear_btn.setToolTip("Clear the STL surface and the phi result")
        hl.addWidget(self.clear_btn)
        return bar

    def _on_view2d_toggled(self, checked: bool):
        """Checked = 3D orbit view; unchecked = 2D top-down view."""
        two_d = not checked
        self.view2d_btn.setText("3D" if checked else "2D")
        self.view.set_2d(two_d)
        # Re-frame in the new mode (top-down for 2D, default orbit for 3D).
        self.fit_view()

    # ------------------------------------------------------------------ #
    # Display controls (own the visibility / z-slice state)
    # ------------------------------------------------------------------ #
    def visibility(self) -> dict:
        return {"stl": self.show_stl_cb.isChecked(),
                "box": self.show_box_cb.isChecked(),
                "solid": self.show_solid_cb.isChecked(),
                "fluid": self.show_fluid_cb.isChecked(),
                "dev": self.show_dev_cb.isChecked()}

    def slice_k(self) -> int | None:
        return None if self.slice_all_cb.isChecked() else self.slice_spin.value()

    def set_slice_max(self, n_levels: int):
        """Configure the z-slice spin range after a run produced ``n_levels``."""
        self.slice_spin.blockSignals(True)
        self.slice_spin.setRange(0, max(0, n_levels - 1))
        self.slice_spin.setValue(0)
        self.slice_spin.blockSignals(False)

    def apply_display(self, *_):
        """Push the current toggle/slice state into the 3D scene."""
        self.slice_spin.setEnabled(not self.slice_all_cb.isChecked())
        self.set_visibility(**self.visibility())
        self.set_slice(self.slice_k())

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
    # Domain box (live overlay)
    # ------------------------------------------------------------------ #
    def set_domain(self, bounds):
        """Update the Cartesian domain box outline."""
        self._bbox = tuple(float(v) for v in bounds)
        box = _box_edge_segments(self._bbox)
        if self._box_item is None:
            self._box_item = gl.GLLinePlotItem(
                pos=box, color=_C_BOX, width=2.0, mode="lines", antialias=True)
            self._box_item.setVisible(self._show["box"])
            self.view.addItem(self._box_item)
        else:
            self._box_item.setData(pos=box, color=_C_BOX, width=2.0, mode="lines")

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
        self.clear_fit_deviation()        # any prior fit heatmap is now stale
        self._refresh_phi()

    def clear_phi(self):
        self._phi_pts = self._phi_val = None
        self._z_levels = None
        self.clear_fit_deviation()
        for attr in ("_solid_item", "_fluid_item"):
            item = getattr(self, attr)
            if item is not None:
                self.view.removeItem(item)
                setattr(self, attr, None)

    # ------------------------------------------------------------------ #
    # Fit-deviation heatmap (STL ↔ phi surface agreement)
    # ------------------------------------------------------------------ #
    def set_fit_deviation(self, points: np.ndarray, dev: np.ndarray, h_cell: float):
        """Render the reconstructed boundary coloured by deviation from the STL.

        ``dev`` is the per-point distance to the STL surface (model units);
        ``h_cell`` the in-plane cell size used to scale the colour ramp.
        """
        self._dev_pts = np.asarray(points, dtype=np.float64)
        self._dev_val = np.asarray(dev, dtype=np.float64)
        self._dev_h = float(h_cell) if h_cell and h_cell > 0 else 1.0
        self._refresh_dev()

    def clear_fit_deviation(self):
        self._dev_pts = self._dev_val = None
        if self._dev_item is not None:
            self.view.removeItem(self._dev_item)
            self._dev_item = None
        # Keep the toggle honest: with no heatmap, the "Fit Δ" box must read off
        # rather than show as enabled over an empty layer.
        cb = getattr(self, "show_dev_cb", None)
        if cb is not None and cb.isChecked():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
            self._show["dev"] = False     # keep the visibility state in sync

    def _refresh_dev(self):
        if self._dev_item is not None:
            self.view.removeItem(self._dev_item)
            self._dev_item = None
        if self._dev_pts is None or len(self._dev_pts) == 0:
            return
        # Map deviation (in cell counts) onto a green→red ramp via the cached
        # colormap (Normalize inlined as a clipped 0..1 scale to avoid the extra
        # matplotlib.colors import).
        cells = self._dev_val / self._dev_h
        t = np.clip(cells / _DEV_VMAX_CELLS, 0.0, 1.0)
        rgba = _dev_cmap()(t)
        self._dev_item = gl.GLScatterPlotItem(
            pos=self._dev_pts.astype(np.float32),
            color=rgba.astype(np.float32), size=7.0, pxMode=True)
        self._dev_item.setVisible(self._show["dev"])
        self.view.addItem(self._dev_item)

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
                 ("solid", self._solid_item), ("fluid", self._fluid_item),
                 ("dev", self._dev_item)]
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
        # 2D locks the camera straight down +Z (XY plane facing the viewer);
        # 3D uses the default orbit angle.
        if getattr(self.view, "_mode_2d", False):
            self.view.setCameraPosition(distance=span * 2.2, elevation=90, azimuth=-90)
        else:
            self.view.setCameraPosition(distance=span * 2.2, elevation=28, azimuth=-60)
