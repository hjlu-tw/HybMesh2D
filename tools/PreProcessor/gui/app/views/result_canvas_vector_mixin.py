from __future__ import annotations
import numpy as np

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.tri as mtri


_BG = "#0c0d16"
_FG = "#a0a8c0"
_COMBO_QSS = (
    "QComboBox{background:#181b30;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:2px 6px;font-size:11px;min-width:90px;}")
_COLORMAPS = ["turbo", "viridis", "inferno", "plasma", "coolwarm", "jet", "RdBu_r"]


class ResultCanvasVectorMixin:
    def _velocity_nodes(self):
        """Return (u_node, v_node) or None if no velocity variables present."""
        # Velocity components are named differently across solver outputs;
        # match common pairs case-insensitively rather than only literal "u"/"v".
        lower = {n.lower(): n for n in self._result.variables}
        for ux, vy in (("u", "v"), ("vx", "vy"), ("u-velocity", "v-velocity"),
                       ("x-velocity", "y-velocity"), ("velocity-x", "velocity-y"),
                       ("velocityx", "velocityy")):
            if ux in lower and vy in lower:
                return self._node_field(lower[ux]), self._node_field(lower[vy])
        return None

    def _stream_grid(self, n: int = 220):
        x, y = self._result.nodes[:, 0], self._result.nodes[:, 1]
        x0, x1, y0, y1 = x.min(), x.max(), y.min(), y.max()
        ar = (y1 - y0) / (x1 - x0) if x1 > x0 else 1.0
        nx, ny = n, max(8, int(n * ar))
        gx = np.linspace(x0, x1, nx)
        gy = np.linspace(y0, y1, ny)
        return np.meshgrid(gx, gy)

    def _draw_streamlines(self):
        vel = self._velocity_nodes()
        if vel is None:
            return
        u_node, v_node = vel
        iu = mtri.LinearTriInterpolator(self._triang, u_node)
        iv = mtri.LinearTriInterpolator(self._triang, v_node)
        gx, gy = self._stream_grid()
        # Masked (outside triangulation / holes) -> 0 so streamplot stays finite.
        U = np.asarray(iu(gx, gy).filled(0.0))
        V = np.asarray(iv(gx, gy).filled(0.0))
        speed = np.hypot(U, V)
        lw = (0.5 + 1.5 * (speed / (speed.max() + 1e-30))
              if self._stream_lw_speed else 0.8)
        self.ax.streamplot(gx, gy, U, V, color="#e2e8f0", density=self._stream_density,
                           linewidth=lw, arrowsize=0.7)

    def _draw_vectors(self):
        vel = self._velocity_nodes()
        if vel is None:
            return
        u_node, v_node = vel
        x, y = self._result.nodes[:, 0], self._result.nodes[:, 1]
        target = max(4, int(self._vec_target))
        step = max(1, x.size // (target * target))
        # scale_units/xy with a user scale: larger _vec_scale -> longer arrows.
        self.ax.quiver(x[::step], y[::step],
                       u_node[::step] * self._vec_scale, v_node[::step] * self._vec_scale,
                       color="#dde2ff", scale_units="xy", angles="xy", width=0.0025)

    def set_vector_params(self, target: int, scale: float):
        self._vec_target = int(target)
        self._vec_scale = float(scale)
        if self.vector_cb.isChecked():
            self.render()

    def set_stream_params(self, density: float, lw_by_speed: bool):
        self._stream_density = float(density)
        self._stream_lw_speed = bool(lw_by_speed)
        if self.stream_cb.isChecked():
            self.render()
