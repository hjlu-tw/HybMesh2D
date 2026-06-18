from __future__ import annotations
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QCheckBox, QLabel,
    QPushButton, QFileDialog,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg, NavigationToolbar2QT,
)
from matplotlib.figure import Figure
import matplotlib.tri as mtri

from app.models.result_data import TecplotResult

_BG = "#0c0d16"
_FG = "#a0a8c0"
_COMBO_QSS = (
    "QComboBox{background:#181b30;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:2px 6px;font-size:11px;min-width:90px;}")
_COLORMAPS = ["viridis", "turbo", "inferno", "plasma", "coolwarm", "jet", "RdBu_r"]


class ResultCanvasView(QWidget):
    """Matplotlib-embedded 2D result viewer.

    Renders a cell-centered scalar field as a filled contour (tripcolor) or a
    smooth contour (tricontourf on node-averaged data), with optional mesh
    wireframe, velocity streamlines and vector glyphs. Streamlines use
    TecplotResult.cell_to_node + LinearTriInterpolator sampled onto a regular
    grid, then matplotlib streamplot (R6).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {_BG};")
        self._result: TecplotResult | None = None
        self._triang: mtri.Triangulation | None = None
        self._building = False  # guard against re-entrant renders during setup

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Control bar ────────────────────────────────────────────────────
        bar = QWidget()
        bar.setStyleSheet("background: #06070d; border-bottom: 1px solid #1c1e36;")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(8, 4, 8, 4)
        hl.setSpacing(6)

        self.load_btn = QPushButton("Load Result")
        self.load_btn.setStyleSheet(
            "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
            "border-radius:4px;padding:3px 10px;font-weight:bold;font-size:11px;}"
            "QPushButton:hover{border-color:#5a9ad4;}")
        hl.addWidget(self.load_btn)

        self.var_combo = QComboBox(); self.var_combo.setStyleSheet(_COMBO_QSS)
        self.zone_combo = QComboBox(); self.zone_combo.setStyleSheet(_COMBO_QSS)
        self.cmap_combo = QComboBox(); self.cmap_combo.addItems(_COLORMAPS)
        self.cmap_combo.setStyleSheet(_COMBO_QSS)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Filled (cells)", "Smooth contour"])
        self.mode_combo.setStyleSheet(_COMBO_QSS)

        for lbl, w in [("Var:", self.var_combo), ("Zone:", self.zone_combo),
                       ("Map:", self.cmap_combo), ("Mode:", self.mode_combo)]:
            t = QLabel(lbl); t.setStyleSheet(f"color:{_FG};font-size:11px;")
            hl.addWidget(t); hl.addWidget(w)

        self.mesh_cb = QCheckBox("Mesh")
        self.stream_cb = QCheckBox("Streamlines")
        self.vector_cb = QCheckBox("Vectors")
        for cb in (self.mesh_cb, self.stream_cb, self.vector_cb):
            cb.setStyleSheet(f"color:{_FG};font-size:11px;")
            hl.addWidget(cb)

        hl.addStretch()
        self.save_btn = QPushButton("Save PNG")
        self.save_btn.setStyleSheet(self.load_btn.styleSheet())
        hl.addWidget(self.save_btn)
        root.addWidget(bar)

        # ── Matplotlib figure ──────────────────────────────────────────────
        self.figure = Figure(facecolor=_BG, tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111)
        self._cbar = None
        self.nav = NavigationToolbar2QT(self.canvas, self)
        self.nav.setStyleSheet(f"background:{_BG};color:{_FG};")
        root.addWidget(self.nav)
        root.addWidget(self.canvas, stretch=1)

        self._style_axes()
        self._empty_message("No result loaded.")

        # Signals
        self.var_combo.currentIndexChanged.connect(self._on_control_changed)
        self.cmap_combo.currentIndexChanged.connect(self._on_control_changed)
        self.mode_combo.currentIndexChanged.connect(self._on_control_changed)
        self.mesh_cb.toggled.connect(self._on_control_changed)
        self.stream_cb.toggled.connect(self._on_control_changed)
        self.vector_cb.toggled.connect(self._on_control_changed)
        self.zone_combo.currentIndexChanged.connect(self._on_zone_changed)
        self.save_btn.clicked.connect(self._save_png)

    # ------------------------------------------------------------------ #
    def _style_axes(self):
        self.ax.set_facecolor(_BG)
        for spine in self.ax.spines.values():
            spine.set_color("#2c2e43")
        self.ax.tick_params(colors=_FG, labelsize=8)
        self.ax.set_aspect("equal", adjustable="box")

    def _empty_message(self, text: str):
        self.ax.clear()
        self._style_axes()
        self.ax.text(0.5, 0.5, text, color="#4a4e69", ha="center", va="center",
                     transform=self.ax.transAxes, fontsize=12)
        self.canvas.draw_idle()

    # ------------------------------------------------------------------ #
    # Public API (driven by postprocess_ctrl in Phase 3.2)
    # ------------------------------------------------------------------ #
    def list_zones(self, path: str):
        return TecplotResult.list_zones(path)

    def load_result_path(self, path: str, zone: int = -1):
        """Populate the zone selector from the file, then load the chosen zone."""
        self._building = True
        try:
            zones = TecplotResult.list_zones(path)
            self._result_path = path
            self.zone_combo.clear()
            for z in zones:
                self.zone_combo.addItem(f"{z.index}: {z.title}", z.index)
            if zones:
                self.zone_combo.setCurrentIndex(len(zones) - 1 if zone < 0 else zone)
        finally:
            self._building = False
        self.set_result(TecplotResult.from_file(path, zone=zone))

    def set_result(self, result: TecplotResult):
        self._result = result
        self._triang = mtri.Triangulation(
            result.nodes[:, 0], result.nodes[:, 1], result.elements)
        self._node_cache: dict[str, np.ndarray] = {}

        self._building = True
        try:
            prev = self.var_combo.currentText()
            self.var_combo.clear()
            self.var_combo.addItems(result.scalar_variables())
            if prev and prev in result.scalar_variables():
                self.var_combo.setCurrentText(prev)
        finally:
            self._building = False
        self.render()

    # ------------------------------------------------------------------ #
    def _node_field(self, var: str) -> np.ndarray:
        if var not in self._node_cache:
            self._node_cache[var] = self._result.cell_to_node(var)
        return self._node_cache[var]

    def _on_zone_changed(self):
        if self._building or self._result is None:
            return
        path = getattr(self, "_result_path", "")
        if path:
            z = self.zone_combo.currentData()
            self.set_result(TecplotResult.from_file(path, zone=z if z is not None else -1))

    def _on_control_changed(self):
        if not self._building:
            self.render()

    def render(self):
        if self._result is None or self._triang is None:
            return
        var = self.var_combo.currentText()
        if not var:
            return
        cmap = self.cmap_combo.currentText()
        r = self._result

        self.ax.clear()
        if self._cbar is not None:
            try:
                self._cbar.remove()
            except Exception:
                pass
            self._cbar = None
        self._style_axes()

        try:
            if self.mode_combo.currentText().startswith("Filled"):
                vals = r.get_cell_field(var)
                mappable = self.ax.tripcolor(
                    self._triang, facecolors=vals, cmap=cmap, shading="flat")
            else:
                node_vals = self._node_field(var)
                mappable = self.ax.tricontourf(
                    self._triang, node_vals, levels=24, cmap=cmap)

            self._cbar = self.figure.colorbar(mappable, ax=self.ax, fraction=0.046, pad=0.02)
            self._cbar.ax.tick_params(colors=_FG, labelsize=8)
            self._cbar.set_label(var, color=_FG)

            if self.mesh_cb.isChecked():
                self.ax.triplot(self._triang, color="#5a607a", lw=0.2, alpha=0.5)
            if self.stream_cb.isChecked():
                self._draw_streamlines()
            if self.vector_cb.isChecked():
                self._draw_vectors()

            self.ax.set_title(
                f"{var}  —  {r.zone.title if r.zone else ''}", color=_FG, fontsize=10)
        except Exception as e:  # pragma: no cover - defensive against bad data
            self._empty_message(f"Render error: {e}")
            return

        self.canvas.draw_idle()

    # ------------------------------------------------------------------ #
    def _velocity_nodes(self):
        """Return (u_node, v_node) or None if no velocity variables present."""
        names = self._result.variables
        u = "u" if "u" in names else None
        v = "v" if "v" in names else None
        if not (u and v):
            return None
        return self._node_field(u), self._node_field(v)

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
        lw = 0.5 + 1.5 * (speed / (speed.max() + 1e-30))
        self.ax.streamplot(gx, gy, U, V, color="#e2e8f0", density=1.2,
                           linewidth=lw, arrowsize=0.7)

    def _draw_vectors(self, target: int = 40):
        vel = self._velocity_nodes()
        if vel is None:
            return
        u_node, v_node = vel
        x, y = self._result.nodes[:, 0], self._result.nodes[:, 1]
        step = max(1, x.size // (target * target))
        self.ax.quiver(x[::step], y[::step], u_node[::step], v_node[::step],
                       color="#dde2ff", scale_units="xy", angles="xy", width=0.0025)

    # ------------------------------------------------------------------ #
    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Plot", "", "PNG (*.png);;PDF (*.pdf);;All Files (*)")
        if path:
            self.figure.savefig(path, dpi=200, facecolor=_BG)
