from __future__ import annotations
import os
import numpy as np
from PyQt6.QtCore import pyqtSignal, Qt
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
import matplotlib.colors as mcolors

from app.models.result_data import TecplotResult
from app.views.result_canvas_interaction_mixin import ResultCanvasInteractionMixin
from app.views.result_canvas_plots_mixin import ResultCanvasPlotsMixin

_BG = "#0c0d16"
_FG = "#a0a8c0"
_COMBO_QSS = (
    "QComboBox{background:#181b30;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:2px 6px;font-size:11px;min-width:90px;}")
_COLORMAPS = ["turbo", "viridis", "inferno", "plasma", "coolwarm", "jet", "RdBu_r"]


class ResultCanvasSetupMixin:
    def _style_axes(self):
        self.ax.set_facecolor(_BG)
        for spine in self.ax.spines.values():
            spine.set_color("#2c2e43")
        self.ax.tick_params(colors=_FG, labelsize=8)
        # 'datalim' keeps the axes box at its fixed rect (adjusting data limits
        # to preserve aspect) so the plot area never shrinks between renders;
        # 'box' would resize the box per render.
        self.ax.set_aspect("equal", adjustable="datalim")

    def _empty_message(self, text: str):
        self.ax.clear()
        self._style_axes()
        self.ax.text(0.5, 0.5, text, color="#4a4e69", ha="center", va="center",
                     transform=self.ax.transAxes, fontsize=12)
        self.canvas.draw_idle()

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
        self._interp_cache = {}
        # Probes/line/extrema reference the previous mesh; drop them on reload.
        self._probes = []
        self._line_pts = []
        self._line_seg = None
        self._extrema = []
        # Preserve the current zoom/pan across reloads and zone switches (no
        # auto-fit). The first-ever load has no saved view, so it still fits;
        # 'Fit View' or Clear re-fits on demand.

        self._building = True
        try:
            prev = self._current_var()
            self._populate_var_combo(result)
            if prev:
                self.select_variable(prev)
        finally:
            self._building = False
        self.render()

    def clear(self):
        """Clear the loaded result and reset to the empty placeholder."""
        self._building = True
        try:
            self._result = None
            self._triang = None
            self.var_combo.clear()
            self._base_vars = []
            self._derived_vars = []
            self.zone_combo.clear()
        finally:
            self._building = False
        self._interp_cache = {}
        self._probes = []
        self._line_pts = []
        self._line_seg = None
        self._extrema = []
        self._cad_polylines = []
        self._cad_on = False
        self._user_view = None   # Clear re-fits the next load
        if self._cbar is not None:
            try:
                self._cbar.remove()
            except Exception:
                pass
            self._cbar = None
        self._empty_message("No result loaded.")

    def select_variable(self, code: str) -> bool:
        """Select ``code`` (#5): switch the Kind selector to whichever group owns
        it, repopulate, then select it in ``var_combo``."""
        if code in self._derived_vars:
            target_kind = 1
        elif code in self._base_vars:
            target_kind = 0
        else:
            target_kind = self.kind_combo.currentIndex()   # unknown: search live list
        if self.kind_combo.currentIndex() != target_kind:
            self.kind_combo.blockSignals(True)
            self.kind_combo.setCurrentIndex(target_kind)
            self.kind_combo.blockSignals(False)
            self._fill_var_combo_for_kind()
        idx = self.var_combo.findData(code)
        if idx < 0:
            idx = self.var_combo.findText(code)
        if idx >= 0:
            self.var_combo.blockSignals(True)
            self.var_combo.setCurrentIndex(idx)
            self.var_combo.blockSignals(False)
            return True
        return False

    def _current_var(self) -> str:
        """The active variable CODE (item data), falling back to its text."""
        data = self.var_combo.currentData()
        return data if data else self.var_combo.currentText()
