from __future__ import annotations
import numpy as np
from PyQt6.QtWidgets import (
    QFileDialog,
)

import matplotlib
matplotlib.use("QtAgg")

from app.models.result_data import TecplotResult
from app.utils import block_signals
from app.services.logging_setup import get_logger

_log = get_logger(__name__)

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
        with block_signals(self.iso_cb):
            self.iso_cb.setChecked(self._iso_on)
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
        """Auto color scale = use the field's data min/max each render.

        The MODE is global — one checkbox with one meaning — so this does not
        forget the per-variable numbers; switching back to Custom brings them
        back.
        """
        self._clim_auto = bool(auto)
        self.render()

    def set_clim(self, vmin: float, vmax: float):
        """Set a manual color-scale range for the DISPLAYED variable, and switch
        off auto.

        The range belongs to one variable (issue #24): a pressure range must not
        colour vorticity. Same fact and same shape as the playback lock's
        ``_range_lock`` / ``_range_lock_var`` pair, so the two cannot drift.
        """
        var = self._current_var()
        if not var:
            # Nothing is displayed, so there is no variable to own the range.
            # Flipping the mode alone would half-apply the call; render() bails on
            # an empty variable anyway, so this is a no-op rather than a state.
            _log.debug("set_clim(%r, %r) ignored: no variable is displayed",
                       vmin, vmax)
            return
        self._clim_auto = False
        self.remember_clim(var, vmin, vmax)
        self.render()

    def manual_clim(self, var: str | None = None):
        """The manual (vmin, vmax) remembered for ``var``, or None.

        None in auto mode, and None for a variable that has never been given one
        — ``render`` seeds that case from the field's own data range.
        """
        if self._clim_auto:
            return None
        return self._clim_by_var.get(var or self._current_var())

    def remember_clim(self, var: str, vmin: float, vmax: float):
        """Record ``var``'s manual range WITHOUT touching the mode.

        The store is written only through here — `render`'s seed path included —
        so "which variable does this range belong to?" is answered in one file
        rather than by every caller keying the dict by hand.
        """
        rng = (float(vmin), float(vmax))
        self._clim_by_var[var] = rng
        return rng

    def reset_clim_store(self):
        """Forget every variable's manual range.

        View state for the loaded result: a NEW result file must not be coloured
        with the previous run's numbers. Frames of one run deliberately keep it.
        """
        self._clim_by_var = {}

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
        allowed = self._series_variables()
        if allowed is None:
            self._base_vars = list(result.base_scalar_variables())
            self._derived_vars = list(result.derived_scalar_variables())
        else:
            # A restarted solve's legs may not carry the same variables (#32), and a
            # variable only some frames have would blank — or change meaning — at
            # every boundary that lacks it. The list is therefore the INTERSECTION,
            # and the derived quantities are recomputed from THAT set rather than
            # from this frame's, so a derived field cannot outlive its inputs either.
            self._base_vars = [v for v in result.base_scalar_variables()
                               if v in allowed]
            self._derived_vars = [d for d in result.derived_from_names(allowed)
                                  if d not in self._base_vars]
        has_d = bool(self._derived_vars)
        self.kind_combo.setVisible(has_d)
        self.kind_label.setVisible(has_d)
        if not has_d and self.kind_combo.currentIndex() != 0:
            with block_signals(self.kind_combo):
                self.kind_combo.setCurrentIndex(0)
        self._fill_var_combo_for_kind()

    def _series_variables(self):
        """The variables every frame of the loaded series can render, or None.

        None for a single-file series — its intersection is its own variable list,
        so filtering would be a no-op, and saying so here is what keeps the
        one-file path provably unchanged by #32.
        """
        series = getattr(self, "_series", None)
        if series is None or series.n_files < 2:
            return None
        return set(series.variables)

    def _fill_var_combo_for_kind(self):
        """Repopulate `var_combo` with the variables of the currently selected
        kind (#5). Signals are blocked so the caller controls re-rendering."""
        result = self._result
        if result is None:
            return
        derived = self.kind_combo.currentIndex() == 1 and bool(self._derived_vars)
        with block_signals(self.var_combo):
            self.var_combo.clear()
            if derived:
                for code in self._derived_vars:
                    self.var_combo.addItem(result.variable_label(code), code)
            else:
                for code in self._base_vars:
                    self.var_combo.addItem(result.variable_short_label(code), code)

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
        z = self.zone_combo.currentData()
        # Picking a zone by hand goes through show_frame, i.e. the same cached path, the
        # same frame counter AND the same pinned colour scale as Prev/Next — the scale
        # being the one this used to miss, which made the two routes render differently.
        if self._series is not None and z is not None:
            self.stop_playback()
            self.show_frame(int(z))
            return
        path = getattr(self, "_result_path", "")
        if path:
            self.set_result(TecplotResult.from_file(path, zone=z if z is not None else -1))

    def _on_control_changed(self):
        # The pinned playback range belongs to ONE variable; switching variables
        # must not colour the new field with the old field's range.
        self._invalidate_range_lock()
        if not self._building:
            self.render()
