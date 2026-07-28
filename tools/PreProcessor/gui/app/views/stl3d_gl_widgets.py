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
_C_FLUID = (0.40, 0.70, 1.0, 0.70)   # phi = 0 (was dark/near-invisible)

# phi scatter GL state: depth-test OFF so the marked cells always draw OVER the
# opaque STL surface instead of being hidden inside/behind it (that occlusion
# made "Solid"/"Fluid" look empty even when cells were marked). Alpha-blended.
_PHI_GLOPTS = {
    GL_DEPTH_TEST: False,
    GL_BLEND: True,
    GL_ALPHA_TEST: False,
    GL_CULL_FACE: False,
    'glBlendFunc': (GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA),
}

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
