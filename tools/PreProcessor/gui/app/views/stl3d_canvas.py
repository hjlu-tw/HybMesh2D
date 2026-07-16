"""3D viewport for the STL3d immersed-solid preprocessor.

Renders the loaded STL surface together with a live overlay of the Cartesian
domain box, so the user can see the box enclosing the geometry while editing
the domain/resolution. After a run it shows the phi field's solid cells
(optionally a single z-slice) for validation.
"""
from __future__ import annotations

import math

import numpy as np
import pyqtgraph.opengl as gl
from OpenGL.GL import (GL_DEPTH_TEST, GL_BLEND, GL_ALPHA_TEST, GL_CULL_FACE,
                       GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QCheckBox, QLabel,
    QPushButton, QSpinBox,
)

from app.services.phi_quality import FIT_OK_CELLS
from app.utils import block_signals, make_button

_C_STL = (0.62, 0.71, 0.92, 1.0)
_C_STL_EDGE = (0.20, 0.30, 0.62, 1.0)  # STL triangle wireframe lines (reads on
#                                        the pale fill AND the dark background)
_C_BOX = (0.36, 0.78, 0.92, 1.0)     # bright cyan box edges

# Wireframe overlay GL state: depth-test OFF so the triangle lines always draw
# over the (coplanar) opaque faces instead of z-fighting and vanishing on a
# flat, face-on sheet; alpha-blended otherwise like the 'translucent' preset.
_EDGE_GLOPTS = {
    GL_DEPTH_TEST: False,
    GL_BLEND: True,
    GL_ALPHA_TEST: False,
    GL_CULL_FACE: False,
    'glBlendFunc': (GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA),
}
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
    """A compact display-bar toolbar button (2D/3D, Fit View, Clear φ, Clear All).

    Thin adapter over the shared ``make_button`` bar variant so the toolbar QSS is
    defined in one place (utils) rather than a parallel factory here.
    """
    return make_button(text, base, border=border, hover_border=hover,
                       padding=padding, checked_bg=checked_bg, font_size="11px")


def _nice_step(extent: float, target: int = 10) -> float:
    """A round grid spacing (1/2/5 × 10ⁿ) giving roughly ``target`` divisions."""
    if extent <= 0:
        return 1.0
    raw = extent / max(target, 1)
    mag = 10.0 ** math.floor(math.log10(raw))
    for m in (1.0, 2.0, 5.0):
        if raw <= m * mag:
            return m * mag
    return 10.0 * mag


def _axis_ticks(lo: float, hi: float, step: float) -> list[float]:
    """Tick coordinates at multiples of ``step`` within [lo, hi]."""
    if step <= 0:
        return []
    n0, n1 = math.ceil(lo / step), math.floor(hi / step)
    return [round(k * step, 10) for k in range(n0, n1 + 1)] if n1 >= n0 else []


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
        self._sync_widgets = []        # repainted whenever the camera changes

    def add_sync(self, w):
        """Register a widget (e.g. an axis ruler) to repaint on every GL frame."""
        self._sync_widgets.append(w)

    def paintGL(self, *args, **kwargs):
        super().paintGL(*args, **kwargs)
        # Keep the external rulers in lock-step with pan/zoom/orbit (setCameraPosition
        # and our pan/wheel handlers all funnel through a GL repaint).
        for w in self._sync_widgets:
            if w.isVisible():
                w.update()

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


class _AxisStrip(QWidget):
    """A screen-space numeric ruler along the GL view's left or bottom edge,
    mirroring the CAD page's plot axes (the numbers sit *outside* the viewport,
    fixed to the border, not floating in the 3D scene).

    Exact in 2D top-down mode: with the camera looking straight down, every point
    on the z=const plane is at the same depth, so the perspective projection is
    uniform and world↔screen is linear. Blank in 3D orbit (no fixed axes there).
    """

    LEFT_W = 46
    BOTTOM_H = 20

    def __init__(self, glview: _GLView, side: str, parent=None):
        super().__init__(parent)
        self._gl = glview
        self._side = side                      # "left" or "bottom"
        self.setStyleSheet("background:#06070d;")
        if side == "left":
            self.setFixedWidth(self.LEFT_W)
        else:
            self.setFixedHeight(self.BOTTOM_H)

    def _edge_world(self, sx, sy):
        return self._gl._world_on_z(sx, sy, self._gl.opts["center"].z())

    def paintEvent(self, ev):
        from PyQt6.QtGui import QPainter, QPen, QColor, QFont
        p = QPainter(self)
        if not getattr(self._gl, "_mode_2d", False):
            return                             # 3D orbit: no fixed edge ruler
        gW, gH = self._gl.width(), self._gl.height()
        if gW <= 0 or gH <= 0:
            return
        p.setPen(QPen(QColor(120, 130, 160)))
        f = QFont(); f.setPointSize(8); p.setFont(f)
        W, H = self.width(), self.height()

        if self._side == "bottom":
            a, b = self._edge_world(0, gH), self._edge_world(gW, gH)
            if not (a and b) or a[0] == b[0]:
                return
            x0v, x1v = a[0], b[0]
            step = _nice_step(abs(x1v - x0v), target=8)
            for xt in _axis_ticks(min(x0v, x1v), max(x0v, x1v), step):
                sx = gW * (xt - x0v) / (x1v - x0v)
                if 0 <= sx <= gW:
                    p.drawLine(int(sx), 0, int(sx), 4)
                    p.drawText(int(sx) - 24, 5, 48, H - 6,
                               Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                               f"{xt:g}")
        else:                                  # left
            bot, top = self._edge_world(0, gH), self._edge_world(0, 0)
            if not (bot and top) or bot[1] == top[1]:
                return
            y0v, y1v = bot[1], top[1]
            step = _nice_step(abs(y1v - y0v), target=8)
            for yt in _axis_ticks(min(y0v, y1v), max(y0v, y1v), step):
                sy = gH * (1.0 - (yt - y0v) / (y1v - y0v))
                if 0 <= sy <= gH:
                    p.drawLine(W - 4, int(sy), W, int(sy))
                    p.drawText(2, int(sy) - 8, W - 8, 16,
                               Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                               f"{yt:g}")


class Stl3dCanvasView(QWidget):
    """OpenGL canvas: STL surface + live domain box/grid + phi solid points."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stl_item: gl.GLMeshItem | None = None
        self._stl_edge_item: gl.GLLinePlotItem | None = None
        self._box_item: gl.GLLinePlotItem | None = None
        self._solid_item: gl.GLScatterPlotItem | None = None
        self._fluid_item: gl.GLScatterPlotItem | None = None
        self._dev_item: gl.GLScatterPlotItem | None = None

        self._bbox = None              # last domain bbox (camera fallback)
        self._stl_bbox = None          # STL surface bbox — preferred fit target
        self._phi_pts: np.ndarray | None = None
        self._phi_val: np.ndarray | None = None
        self._z_levels: np.ndarray | None = None
        self._slice_k: int | None = None   # None => show all z-layers

        self._dev_pts: np.ndarray | None = None   # fit-deviation heatmap
        self._dev_val: np.ndarray | None = None
        self._dev_h: float = 1.0

        self._grid_items: list = []    # faint in-scene XY grid (graph paper)

        self._show = {"stl": True, "stl_edges": True, "box": True, "solid": True,
                      "fluid": False, "dev": False, "grid": True}

        # ── Top display bar (moved here from the sidebar) ──────────────────
        layout.addWidget(self._build_display_bar())

        self.view = _GLView()
        self.view.setBackgroundColor(12, 13, 22)        # match app dark theme
        self.view.setCameraPosition(elevation=90, azimuth=-90)  # default 2D top-down

        # ── GL view framed by left + bottom numeric rulers (like the CAD page:
        #    the scale numbers sit outside the viewport, fixed to the border). ──
        self._left_axis = _AxisStrip(self.view, "left")
        self._bottom_axis = _AxisStrip(self.view, "bottom")
        self._axis_corner = QWidget()
        self._axis_corner.setFixedSize(_AxisStrip.LEFT_W, _AxisStrip.BOTTOM_H)
        self._axis_corner.setStyleSheet("background:#06070d;")
        self.view.add_sync(self._left_axis)
        self.view.add_sync(self._bottom_axis)

        grid_w = QWidget()
        g = QGridLayout(grid_w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(0)
        g.addWidget(self._left_axis, 0, 0)
        g.addWidget(self.view, 0, 1)
        g.addWidget(self._axis_corner, 1, 0)
        g.addWidget(self._bottom_axis, 1, 1)
        layout.addWidget(grid_w, stretch=1)

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
        self.show_stl_edges_cb = _check(
            "STL edges", "Show the STL triangle edges (wireframe grid lines)", True)
        self.show_box_cb = _check("Domain box", "Show the Cartesian domain box", True)
        self.show_grid_cb = _check(
            "Ruler", "Show the edge axis rulers (x/y scale at the border) + the "
            "faint in-scene grid", True)
        self.show_solid_cb = _check("Solid (φ=1)", "Show marked solid cells from the last run", True)
        self.show_fluid_cb = _check("Fluid (φ=0)", "Show fluid cells (faint) from the last run", False)
        self.show_dev_cb = _check(
            "Fit Δ", "Show the STL↔φ surface-deviation heatmap from Check Fit "
            f"(green = within a cell, red ≥ {FIT_OK_CELLS:g} cells off)", False)
        for cb in (self.show_stl_cb, self.show_stl_edges_cb, self.show_box_cb,
                   self.show_grid_cb, self.show_solid_cb, self.show_fluid_cb,
                   self.show_dev_cb):
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
        self.fit_btn.setToolTip("Frame the camera on the geometry (STL surface)")
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
                "stl_edges": self.show_stl_edges_cb.isChecked(),
                "box": self.show_box_cb.isChecked(),
                "grid": self.show_grid_cb.isChecked(),
                "solid": self.show_solid_cb.isChecked(),
                "fluid": self.show_fluid_cb.isChecked(),
                "dev": self.show_dev_cb.isChecked()}

    def slice_k(self) -> int | None:
        return None if self.slice_all_cb.isChecked() else self.slice_spin.value()

    def set_slice_max(self, n_levels: int):
        """Reset the z-slice controls after a run produced ``n_levels`` layers.

        Resets the 'All z-layers' toggle too (not just the spin value) so a stale
        isolate-layer selection from a previous result never carries over and
        renders only one layer of the fresh field.
        """
        self._reset_slice_controls(n_levels)

    def _reset_slice_controls(self, n_levels: int = 0):
        """Set the z-slice toggle back to 'all layers' and the spin to its range."""
        with block_signals(self.slice_all_cb, self.slice_spin):
            self.slice_all_cb.setChecked(True)
            self.slice_spin.setRange(0, max(0, n_levels - 1))
            self.slice_spin.setValue(0)
            self.slice_spin.setEnabled(False)
        self._slice_k = None

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
        for it in (self._stl_item, self._stl_edge_item):
            if it is not None:
                self.view.removeItem(it)
        self._stl_item = None
        self._stl_edge_item = None
        if tris is None or len(tris) == 0:
            self._stl_bbox = None
            return
        v = tris.reshape(-1, 3)
        self._stl_bbox = (float(v[:, 0].min()), float(v[:, 0].max()),
                          float(v[:, 1].min()), float(v[:, 1].max()),
                          float(v[:, 2].min()), float(v[:, 2].max()))
        verts = tris.reshape(-1, 3).astype(np.float32)
        faces = np.arange(len(verts), dtype=np.uint32).reshape(-1, 3)
        md = gl.MeshData(vertexes=verts, faces=faces)
        # Faces only. GLMeshItem's own drawEdges draws the wireframe at the SAME
        # depth as the faces (no polygon offset), so on a flat sheet viewed
        # face-on the opaque faces z-fight over the coplanar edges and they
        # vanish — which is exactly the "can't see the edges" case. Draw the
        # triangle grid as a separate line item with depth-testing OFF instead,
        # so it always sits on top of the surface regardless of orientation.
        self._stl_item = gl.GLMeshItem(
            meshdata=md, smooth=False, drawEdges=False, color=_C_STL,
            shader="shaded", glOptions="opaque")
        self._stl_item.setVisible(self._show["stl"])
        self.view.addItem(self._stl_item)

        # Triangle edges as a DEDUPED line set (mode="lines" pairs consecutive
        # vertices). A shared edge is drawn once instead of once per adjacent
        # triangle — ~halves the line vertices on a closed mesh. np.unique maps
        # the per-face-duplicated vertices (``verts``) to canonical ids by exact
        # coordinate; vertices that don't match bit-for-bit simply stay distinct,
        # degrading gracefully to the naive per-triangle edge set.
        uniq, inv = np.unique(verts, axis=0, return_inverse=True)
        tri_ids = np.asarray(inv).reshape(-1, 3)
        e = np.concatenate([tri_ids[:, [0, 1]], tri_ids[:, [1, 2]], tri_ids[:, [2, 0]]])
        e = np.unique(np.sort(e, axis=1), axis=0)          # undirected, deduped
        seg = uniq[e].reshape(-1, 3).astype(np.float32)
        self._stl_edge_item = gl.GLLinePlotItem(
            pos=seg, color=_C_STL_EDGE, width=1.0, mode="lines", antialias=True,
            glOptions=_EDGE_GLOPTS)
        self._stl_edge_item.setVisible(self._show["stl_edges"])
        self.view.addItem(self._stl_edge_item)

    # ------------------------------------------------------------------ #
    # Domain box (live overlay)
    # ------------------------------------------------------------------ #
    def set_domain(self, bounds):
        """Update the Cartesian domain box outline and the XY scale ruler."""
        self._bbox = tuple(float(v) for v in bounds)
        box = _box_edge_segments(self._bbox)
        if self._box_item is None:
            self._box_item = gl.GLLinePlotItem(
                pos=box, color=_C_BOX, width=2.0, mode="lines", antialias=True)
            self._box_item.setVisible(self._show["box"])
            self.view.addItem(self._box_item)
        else:
            self._box_item.setData(pos=box, color=_C_BOX, width=2.0, mode="lines")
        self._rebuild_grid()

    def clear_domain(self):
        """Remove the Cartesian domain box outline + ruler (used by Clear All)."""
        if self._box_item is not None:
            self.view.removeItem(self._box_item)
            self._box_item = None
        for it in self._grid_items:
            self.view.removeItem(it)
        self._grid_items = []
        self._bbox = None

    # ------------------------------------------------------------------ #
    # XY scale ruler (graph-paper grid + numeric axis ticks)
    # ------------------------------------------------------------------ #
    def _rebuild_grid(self):
        """(Re)draw a faint graph-paper grid under the geometry, aligned to round
        world coordinates so its lines coincide with the external rulers' ticks.
        The numeric scale itself lives on the left/bottom ruler strips."""
        for it in self._grid_items:
            self.view.removeItem(it)
        self._grid_items = []
        if self._bbox is None:
            return
        x0, x1, y0, y1, z0, z1 = self._bbox
        sx, sy = x1 - x0, y1 - y0
        if sx <= 0 or sy <= 0:
            return
        step = _nice_step(max(sx, sy))
        grid = gl.GLGridItem()
        # Pad by a step and centre on a multiple of step so grid lines fall on
        # round coordinates (matching the ruler ticks) rather than the box centre.
        grid.setSize(x=sx + 2 * step, y=sy + 2 * step)
        grid.setSpacing(x=step, y=step)
        ax = round((x0 + x1) / 2.0 / step) * step
        ay = round((y0 + y1) / 2.0 / step) * step
        grid.translate(ax, ay, z0)
        try:
            grid.setColor((70, 80, 115, 45))      # very faint, like the CAD grid
        except Exception:
            pass
        self._grid_items.append(grid)
        self.view.addItem(grid)
        grid.setVisible(self._show.get("grid", True))

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
        self._reset_slice_controls()      # drop any stale isolate-layer selection
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
            with block_signals(cb):
                cb.setChecked(False)
            self._show["dev"] = False     # keep the visibility state in sync

    def _refresh_dev(self):
        if self._dev_item is not None:
            self.view.removeItem(self._dev_item)
            self._dev_item = None
        if self._dev_pts is None or len(self._dev_pts) == 0:
            return
        # Honour the z-slice selection so isolating a layer hides deviation points
        # from the other layers — otherwise the heatmap contradicts the solid/fluid
        # view, which _refresh_phi already filters the same way.
        mask = np.ones(len(self._dev_pts), dtype=bool)
        if (self._slice_k is not None and self._z_levels is not None
                and 0 <= self._slice_k < len(self._z_levels)):
            zsel = self._z_levels[self._slice_k]
            mask = np.isclose(np.round(self._dev_pts[:, 2], 9), zsel)
        pts = self._dev_pts[mask]
        if len(pts) == 0:
            return
        # Map deviation (in cell counts) onto a green→red ramp via the cached
        # colormap (Normalize inlined as a clipped 0..1 scale to avoid the extra
        # matplotlib.colors import).
        cells = self._dev_val[mask] / self._dev_h
        t = np.clip(cells / _DEV_VMAX_CELLS, 0.0, 1.0)
        rgba = _dev_cmap()(t)
        self._dev_item = gl.GLScatterPlotItem(
            pos=pts.astype(np.float32),
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
        self._refresh_dev()      # keep the deviation heatmap on the same layer

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
        pairs = [("stl", self._stl_item), ("stl_edges", self._stl_edge_item),
                 ("box", self._box_item), ("solid", self._solid_item),
                 ("fluid", self._fluid_item), ("dev", self._dev_item)]
        for key, item in pairs:
            if item is not None:
                item.setVisible(self._show[key])
        # "Ruler" toggles the in-scene grid AND the external left/bottom rulers.
        gvis = self._show.get("grid", True)
        for it in self._grid_items:
            it.setVisible(gvis)
        for w in (getattr(self, "_left_axis", None), getattr(self, "_bottom_axis", None),
                  getattr(self, "_axis_corner", None)):
            if w is not None:
                w.setVisible(gvis)

    def fit_view(self):
        """Frame the camera on the geometry (STL surface), falling back to the
        domain box only when no STL is loaded. Auto Domain therefore keeps the
        view locked on the solid rather than zooming out to the padded box."""
        b = self._stl_bbox or self._bbox
        if b is None:
            return
        x0, x1, y0, y1, z0, z1 = b
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
