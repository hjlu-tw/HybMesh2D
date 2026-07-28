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


class ResultCanvasControlsMixin:
    def set_cmap(self, name: str):
        self._cmap = name
        self.render()

    def set_iso(self, levels: list, on: bool):
        """Set iso levels from the sidebar; syncs the top-bar 'Iso' checkbox."""
        self._iso_levels = list(levels)
        self._iso_on = bool(on)
        self.iso_cb.blockSignals(True)
        self.iso_cb.setChecked(self._iso_on)
        self.iso_cb.blockSignals(False)
        self.render()

    def _on_iso_toggled(self, on: bool):
        self._iso_on = bool(on)
        self.render()

    def set_color_norm(self, log: bool, symmetric: bool):
        self._log_scale = bool(log)
        self._symmetric = bool(symmetric)
        self.render()

    def set_levels(self, mode: str, n_levels: int = None, delta: float = None):
        """Contour level mode: 'smooth' (continuous), 'count' (band count) or
        'delta' (fixed band spacing)."""
        if mode in ("smooth", "count", "delta"):
            self._level_mode = mode
        if n_levels is not None:
            self._n_levels = max(2, int(n_levels))
        if delta is not None:
            self._level_delta = max(0.0, float(delta))
        self.render()

    def set_clim_auto(self, auto: bool):
        """Auto color scale = use the field's data min/max each render."""
        self._clim_auto = bool(auto)
        self.render()

    def set_clim(self, vmin: float, vmax: float):
        """Set a manual color-scale range and switch off auto."""
        self._clim_auto = False
        self._clim = (float(vmin), float(vmax))
        self.render()

    def mark_extrema(self, which: str):
        """Mark the min and/or max of the current field's nodal values."""
        if self._result is None:
            return
        var = self._current_var()
        if not var:
            return
        node_vals = self._node_field(var)
        finite = np.isfinite(node_vals)
        if not finite.any():
            return
        x, y = self._result.nodes[:, 0], self._result.nodes[:, 1]
        self._extrema = []
        wants = ("min", "max") if which == "both" else (which,)
        for w in wants:
            idx = (np.where(finite, node_vals, np.inf).argmin() if w == "min"
                   else np.where(finite, node_vals, -np.inf).argmax())
            e = {"which": w, "var": var, "x": float(x[idx]),
                 "y": float(y[idx]), "value": float(node_vals[idx])}
            self._extrema.append(e)
            self.extrema_found.emit(e)
        self.render()

    def clear_extrema(self):
        self._extrema = []
        self.render()

    def integral_stats(self, var: str | None = None) -> dict:
        """Area-weighted integral / mean / std / min / max of the current field."""
        if self._result is None:
            return {}
        var = var or self._current_var()
        if not var:
            return {}
        cell = np.asarray(self._result.get_cell_field(var), dtype=float)
        n = self._result.nodes
        tri = self._result.elements
        # Triangle areas via the cross product of two edges.
        x = n[:, 0][tri]; y = n[:, 1][tri]
        area = 0.5 * np.abs((x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0])
                            - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0]))
        m = np.isfinite(cell) & np.isfinite(area)
        cell, area = cell[m], area[m]
        tot_area = float(area.sum())
        if tot_area <= 0 or cell.size == 0:
            return {}
        integral = float((cell * area).sum())
        wmean = integral / tot_area
        var_w = float((area * (cell - wmean) ** 2).sum() / tot_area)
        return {"var": var, "integral": integral, "area": tot_area,
                "mean": wmean, "std": var_w ** 0.5,
                "min": float(cell.min()), "max": float(cell.max())}

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Plot", "", "PNG (*.png);;PDF (*.pdf);;All Files (*)")
        if path:
            self.figure.savefig(path, dpi=200, facecolor=_BG)

    def _populate_var_combo(self, result):
        """#5: fill the two-level variable picker. `kind_combo` chooses the KIND
        (Variable = raw fields, Derived = post-processing quantities); `var_combo`
        lists ONLY the chosen kind. Item data is the variable CODE. Raw fields
        show their symbol only (no '— description'); derived keep the full label
        to stay discoverable. The Kind selector is hidden when nothing derived."""
        self._base_vars = list(result.base_scalar_variables())
        self._derived_vars = list(result.derived_scalar_variables())
        has_d = bool(self._derived_vars)
        self.kind_combo.setVisible(has_d)
        self.kind_label.setVisible(has_d)
        if not has_d and self.kind_combo.currentIndex() != 0:
            self.kind_combo.blockSignals(True)
            self.kind_combo.setCurrentIndex(0)
            self.kind_combo.blockSignals(False)
        self._fill_var_combo_for_kind()

    def _fill_var_combo_for_kind(self):
        """Repopulate `var_combo` with the variables of the currently selected
        kind (#5). Signals are blocked so the caller controls re-rendering."""
        result = self._result
        if result is None:
            return
        derived = self.kind_combo.currentIndex() == 1 and bool(self._derived_vars)
        self.var_combo.blockSignals(True)
        self.var_combo.clear()
        if derived:
            for code in self._derived_vars:
                self.var_combo.addItem(result.variable_label(code), code)
        else:
            for code in self._base_vars:
                self.var_combo.addItem(result.variable_short_label(code), code)
        self.var_combo.blockSignals(False)

    def _on_var_kind_changed(self, _idx=None):
        """Kind switched (#5): repopulate the variable list for the new kind and
        re-render with its first entry."""
        if getattr(self, "_building", False):
            return
        self._fill_var_combo_for_kind()
        self._on_control_changed()

    def list_zones(self, path: str):
        return TecplotResult.list_zones(path)

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
