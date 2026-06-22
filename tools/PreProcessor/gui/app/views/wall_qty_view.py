from __future__ import annotations
import os
import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton, QFileDialog,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg, NavigationToolbar2QT,
)
from matplotlib.figure import Figure

_BG = "#0c0d16"
_FG = "#a0a8c0"
_COMBO_QSS = (
    "QComboBox{background:#181b30;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:2px 6px;font-size:11px;min-width:90px;}")
_BTN_QSS = (
    "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:3px 10px;font-weight:bold;font-size:11px;}"
    "QPushButton:hover{border-color:#5a9ad4;}")

# Column names documented in the manual for vsurface_qty.dat. The file has no
# header, so we label by column count: 5 = adiabatic wall, 13 = isothermal wall.
_VSURFACE_5 = ["x", "y", "p", "T", "Cf"]
_VSURFACE_13 = ["x", "y", "x1", "y1", "p", "T1", "dy", "qw",
                "dtdy2", "dtdy", "Ch", "qf2", "Cf"]


def parse_columnar(path: str) -> tuple[list[str], np.ndarray]:
    """Parse a whitespace-delimited numeric .dat file into (labels, data NxC).

    Skips non-numeric header/comment lines. If a Tecplot-style `VARIABLES = ...`
    line is present its names are used; otherwise vsurface_qty.dat is labelled by
    column count and anything else gets generic col0..colN names.
    """
    names: list[str] = []
    rows: list[list[float]] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            up = s.upper()
            if up.startswith("VARIABLES"):
                # VARIABLES = "x" "y" "Cf"  ->  ['x', 'y', 'Cf']
                rhs = s.split("=", 1)[1] if "=" in s else s
                import re
                quoted = re.findall(r'"([^"]*)"', rhs)
                names = quoted if quoted else [t for t in re.split(r"[\s,]+", rhs) if t]
                continue
            if up.startswith(("ZONE", "TITLE", "#", "//", "DATAPACKING", "VARLOCATION")):
                continue
            parts = s.replace(",", " ").split()
            try:
                vals = [float(p) for p in parts]
            except ValueError:
                continue
            if vals:
                rows.append(vals)
    if not rows:
        return [], np.empty((0, 0))
    width = min(len(r) for r in rows)
    data = np.array([r[:width] for r in rows], dtype=float)

    base = os.path.basename(path).lower()
    if not names or len(names) != width:
        if "vsurface" in base and width == len(_VSURFACE_5):
            names = list(_VSURFACE_5)
        elif "vsurface" in base and width == len(_VSURFACE_13):
            names = list(_VSURFACE_13)
        else:
            names = [f"col{i}" for i in range(width)]
    return names, data


class WallQuantityDialog(QDialog):
    """Line-plot viewer for the solver's columnar wall-quantity outputs
    (WallForce.dat, vsurface_qty.dat, tWall_values.dat, ...).

    Pick any column as X and any as Y. Robust to unknown formats: anything that
    parses as numeric columns can be plotted.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wall Quantities")
        self.resize(720, 520)
        self.setStyleSheet(f"background:{_BG};color:{_FG};")
        self._labels: list[str] = []
        self._data = np.empty((0, 0))
        self._line_sampler = None   # set in line-probe mode: var -> (s, vals)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.load_btn = QPushButton("Load .dat")
        self.load_btn.setStyleSheet(_BTN_QSS)
        bar.addWidget(self.load_btn)

        # Variable selector (line-probe mode only): re-samples the segment.
        self.var_label = QLabel("Var:")
        self.var_label.setStyleSheet(f"color:{_FG};font-size:11px;")
        self.line_var_combo = QComboBox(); self.line_var_combo.setStyleSheet(_COMBO_QSS)
        self.var_label.setVisible(False); self.line_var_combo.setVisible(False)
        bar.addWidget(self.var_label); bar.addWidget(self.line_var_combo)

        self.x_combo = QComboBox(); self.x_combo.setStyleSheet(_COMBO_QSS)
        self.y_combo = QComboBox(); self.y_combo.setStyleSheet(_COMBO_QSS)
        for lbl, w in [("X:", self.x_combo), ("Y:", self.y_combo)]:
            t = QLabel(lbl); t.setStyleSheet(f"color:{_FG};font-size:11px;")
            bar.addWidget(t); bar.addWidget(w)
        bar.addStretch()
        self.save_btn = QPushButton("Save PNG")
        self.save_btn.setStyleSheet(_BTN_QSS)
        bar.addWidget(self.save_btn)
        root.addLayout(bar)

        self.figure = Figure(facecolor=_BG)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.nav = NavigationToolbar2QT(self.canvas, self)
        self.nav.setStyleSheet(f"background:{_BG};color:{_FG};")
        root.addWidget(self.nav)
        root.addWidget(self.canvas, stretch=1)

        self._style_axes()
        self._empty("No file loaded.")

        self.load_btn.clicked.connect(self._on_load)
        self.save_btn.clicked.connect(self._save_png)
        self.x_combo.currentIndexChanged.connect(self._render)
        self.y_combo.currentIndexChanged.connect(self._render)
        self.line_var_combo.currentTextChanged.connect(self._on_line_var_changed)

    # ------------------------------------------------------------------ #
    def _style_axes(self):
        self.ax.set_facecolor(_BG)
        for spine in self.ax.spines.values():
            spine.set_color("#2c2e43")
        self.ax.tick_params(colors=_FG, labelsize=8)
        self.ax.grid(True, color="#1c1e36", alpha=0.6)

    def _empty(self, text: str):
        self.ax.clear()
        self._style_axes()
        self.ax.text(0.5, 0.5, text, color="#4a4e69", ha="center", va="center",
                     transform=self.ax.transAxes, fontsize=12)
        self.canvas.draw_idle()

    # ------------------------------------------------------------------ #
    def load_path(self, path: str):
        try:
            labels, data = parse_columnar(path)
        except Exception as e:
            self._empty(f"Parse error: {e}")
            return
        if data.size == 0 or data.shape[1] == 0:
            self._empty(f"No numeric columns found in {os.path.basename(path)}.")
            return
        self._labels, self._data = labels, data
        # File mode: not a line probe -> hide the variable re-sampler.
        self._line_sampler = None
        self.var_label.setVisible(False)
        self.line_var_combo.setVisible(False)
        self.setWindowTitle(f"Wall Quantities — {os.path.basename(path)}")
        self._building = True
        try:
            for combo in (self.x_combo, self.y_combo):
                combo.clear()
                combo.addItems(labels)
            # Sensible defaults: X = first column, Y = last column.
            self.x_combo.setCurrentIndex(0)
            self.y_combo.setCurrentIndex(len(labels) - 1)
        finally:
            self._building = False
        self._render()

    def plot_over_line(self, variables: list, sampler, var: str):
        """Line-probe mode: show a variable selector that re-samples the segment.

        variables: selectable scalar names; sampler(var) -> (s_array, vals_array).
        """
        self._line_sampler = sampler
        self.setWindowTitle("Plot Over Line")
        self._building = True
        try:
            self.line_var_combo.clear()
            self.line_var_combo.addItems(list(variables))
            if var in variables:
                self.line_var_combo.setCurrentText(var)
        finally:
            self._building = False
        self.var_label.setVisible(True)
        self.line_var_combo.setVisible(True)
        self._resample_line(self.line_var_combo.currentText())

    def _on_line_var_changed(self, var: str):
        if getattr(self, "_building", False) or self._line_sampler is None or not var:
            return
        self._resample_line(var)

    def _resample_line(self, var: str):
        if self._line_sampler is None or not var:
            return
        s, vals = self._line_sampler(var)
        self.plot_series(np.asarray(s), {var: np.asarray(vals)},
                         xlabel="distance along line")

    def plot_series(self, x, ys: dict, xlabel: str = "x"):
        """Plot already-sampled data directly (no file), reusing the column UI.

        x: 1D array; ys: {label: 1D array}. Used by the canvas's line probe.
        """
        labels = [xlabel] + list(ys.keys())
        cols = [np.asarray(x, dtype=float)]
        cols += [np.asarray(v, dtype=float) for v in ys.values()]
        width = min(c.shape[0] for c in cols)
        self._labels = labels
        self._data = np.column_stack([c[:width] for c in cols])
        self._building = True
        try:
            for combo in (self.x_combo, self.y_combo):
                combo.clear()
                combo.addItems(labels)
            self.x_combo.setCurrentIndex(0)
            self.y_combo.setCurrentIndex(1 if len(labels) > 1 else 0)
        finally:
            self._building = False
        self._render()

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open wall-quantity file", self._start_dir(),
            "Data (*.dat *.dat.* WallForce* vsurface*);;All Files (*)")
        if path:
            self.load_path(path)

    def _start_dir(self) -> str:
        d = getattr(self, "_last_dir", "")
        return d if d and os.path.isdir(d) else ""

    def _render(self):
        if getattr(self, "_building", False):
            return
        if self._data.size == 0:
            return
        xi = self.x_combo.currentIndex()
        yi = self.y_combo.currentIndex()
        if xi < 0 or yi < 0:
            return
        self.ax.clear()
        self._style_axes()
        x = self._data[:, xi]
        y = self._data[:, yi]
        order = np.argsort(x)
        self.ax.plot(x[order], y[order], color="#5a9ad4", lw=1.4, marker=".", ms=3)
        self.ax.set_xlabel(self._labels[xi], color=_FG, fontsize=9)
        self.ax.set_ylabel(self._labels[yi], color=_FG, fontsize=9)
        self.ax.set_title(f"{self._labels[yi]} vs {self._labels[xi]}",
                          color=_FG, fontsize=10)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Plot", "", "PNG (*.png);;PDF (*.pdf);;All Files (*)")
        if path:
            self.figure.savefig(path, dpi=200, facecolor=_BG)
