from __future__ import annotations
import csv
from PyQt6.QtWidgets import (
    QTableWidgetItem,
    QFileDialog,
)

from app.utils import (
    block_signals,
)

_TABLE_QSS = (
    "QTableWidget{background:#181b2a;color:#a0a8c0;border:1px solid #333852;"
    "gridline-color:#2c2e43;} QHeaderView::section{background:#1e2235;"
    "color:#a0a8c0;border:none;padding:3px;}")
_SCROLLBAR_QSS = """
    QScrollBar:vertical { border: none; background: #0c0d16; width: 10px; margin: 0px; }
    QScrollBar::handle:vertical { background: #2c2e43; min-height: 20px; border-radius: 5px; }
    QScrollBar::handle:vertical:hover { background: #3e415e; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""
_COLORMAPS = ["turbo", "viridis", "inferno", "plasma", "coolwarm", "jet", "RdBu_r"]


class ResultPanelHandlersMixin:
    def bind(self, canvas, controller=None):
        """Connect to the result canvas (called by the controller)."""
        self._canvas = canvas
        self._controller = controller
        # The canvas needs the controller too: the surface sources that are not
        # the mesh boundary (STL3d φ, the analytic φ shape, the CAD outlines) all
        # live outside the result file, and the Surface… dialog is opened from the
        # canvas's own toolbar rather than from this panel.
        if hasattr(canvas, "set_controller"):
            canvas.set_controller(controller)
        canvas.result_rendered.connect(self._on_rendered)
        canvas.probe_added.connect(self._on_probe_added)
        canvas.extrema_found.connect(self._on_extrema_found)
        # Reflect the canvas's current colormap in the sidebar selector.
        with block_signals(self.cmap_combo):
            self.cmap_combo.setCurrentText(getattr(canvas, "_cmap", _COLORMAPS[0]))

    def _set_mode(self, mode):
        if self._canvas is None:
            return
        self._canvas.set_interact_mode(mode)
        # Off doubles as a clear: drop probes & line from the canvas and tables.
        if mode is None:
            self._canvas.clear_probes()
            self._canvas.clear_line()
            self.probe_table.setRowCount(0)
            self.probe_detail.setRowCount(0)

    def _on_probe_added(self, p: dict):
        r = self.probe_table.rowCount()
        self.probe_table.insertRow(r)
        self.probe_table.setItem(r, 0, QTableWidgetItem(f"P{r+1}"))
        self.probe_table.setItem(r, 1, QTableWidgetItem(f"{p['x']:.4g}"))
        self.probe_table.setItem(r, 2, QTableWidgetItem(f"{p['y']:.4g}"))
        self.probe_table.selectRow(r)  # -> _show_selected_probe_detail

    def _show_selected_probe_detail(self):
        if self._canvas is None:
            return
        probes = getattr(self._canvas, "_probes", [])
        r = self.probe_table.currentRow()
        self.probe_detail.setRowCount(0)
        if not (0 <= r < len(probes)):
            return
        for var, val in probes[r]["vals"].items():
            i = self.probe_detail.rowCount()
            self.probe_detail.insertRow(i)
            self.probe_detail.setItem(i, 0, QTableWidgetItem(str(var)))
            txt = f"{val:.6g}" if val == val else "—"  # val==val rejects nan
            self.probe_detail.setItem(i, 1, QTableWidgetItem(txt))

    def _on_probe_undo(self):
        if self._canvas is not None:
            self._canvas.remove_last_probe()
        if self.probe_table.rowCount():
            self.probe_table.removeRow(self.probe_table.rowCount() - 1)
        self._show_selected_probe_detail()

    def _on_probe_clear(self):
        if self._canvas is not None:
            self._canvas.clear_probes()
        self.probe_table.setRowCount(0)
        self.probe_detail.setRowCount(0)

    def _on_probe_add_coord(self):
        if self._canvas is not None:
            self._canvas.add_probe_at(self.probe_x.value(), self.probe_y.value())

    def _export_probes(self):
        if self._canvas is None or not getattr(self._canvas, "_probes", []):
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Probes", "probes.csv",
                                              "CSV (*.csv);;All Files (*)")
        if not path:
            return
        probes = self._canvas._probes
        variables = list(probes[0]["vals"].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["#", "x", "y"] + variables)
            for i, p in enumerate(probes):
                w.writerow([f"P{i+1}", p["x"], p["y"]]
                           + [p["vals"].get(v, "") for v in variables])

    def _on_line_plot_coord(self):
        if self._canvas is not None:
            self._canvas.add_line_segment(
                (self.line_x0.value(), self.line_y0.value()),
                (self.line_x1.value(), self.line_y1.value()))

    def _on_line_clear(self):
        if self._canvas is not None:
            self._canvas.clear_line()

    def _on_iso_mode(self, *_):
        is_range = self.iso_mode.currentIndex() == 1
        self._iso_values_row.setVisible(not is_range)
        self._iso_range_row.setVisible(is_range)

    def _apply_iso(self, *_):
        if self._canvas is None:
            return
        levels = []
        if self.iso_mode.currentIndex() == 0:  # explicit values
            for tok in self.iso_values.text().replace(";", ",").split(","):
                tok = tok.strip()
                if not tok:
                    continue
                try:
                    levels.append(float(tok))
                except ValueError:
                    pass
        else:  # range from..to inclusive, stepping by step (capped count)
            step = self.iso_step.value()
            if step > 0:
                a, b = self.iso_from.value(), self.iso_to.value()
                if b >= a:
                    v, n = a, 0
                    while v <= b + step * 1e-6 and n < 1000:
                        levels.append(round(v, 10)); v += step; n += 1
        # Applying turns the overlay on (top-bar 'Iso' box is synced by the canvas).
        self._canvas.set_iso(sorted(set(levels)), True)

    def _on_iso_clear(self):
        self.iso_values.clear()
        self.iso_step.setValue(0.0)
        if self._canvas is not None:
            self._canvas.set_iso([], False)

    def _mark(self, which: str):
        # Canvas replaces its marked set each call; reset both readouts first.
        self.lbl_minval.setText("—"); self.lbl_maxval.setText("—")
        if self._canvas is not None:
            self._canvas.mark_extrema(which)

    def _on_extrema_found(self, e: dict):
        txt = f"{e['value']:.4g} @ ({e['x']:.3g}, {e['y']:.3g})"
        (self.lbl_minval if e.get("which") == "min" else self.lbl_maxval).setText(txt)

    def _clear_extrema(self):
        self.lbl_minval.setText("—"); self.lbl_maxval.setText("—")
        if self._canvas is not None:
            self._canvas.clear_extrema()

    def _on_cmap_changed(self, name: str):
        if self._canvas is not None and name:
            self._canvas.set_cmap(name)

    def _apply_levels(self, *_):
        mode = ("smooth", "count", "delta")[self.level_mode.currentIndex()]
        # Show only the input relevant to the chosen shading mode.
        self._count_row.setVisible(mode == "count")
        self._delta_row.setVisible(mode == "delta")
        if self._canvas is not None:
            self._canvas.set_levels(mode, self.n_levels.value(), self.level_delta.value())

    def _on_auto_toggled(self, checked: bool):
        # Reveal the Min/Max/Apply box only in custom-range mode.
        self._range_box.setVisible(not checked)
        if self._canvas is not None:
            # The checkbox IS the mode, in both directions. Unticking used to tell
            # the canvas nothing until Apply, so the panel showed the Custom box
            # while the canvas kept auto-scaling every frame to its own min/max —
            # and the Min/Max boxes, no longer refreshed by the Auto branch, froze
            # on the frame the untick happened on. Found in review of issue #24;
            # it is that issue's own symptom (boxes describing a range that is not
            # on screen) reached by the other route.
            self._canvas.set_clim_auto(checked)

    def _on_apply(self):
        if self._canvas is not None:
            self._canvas.set_clim(self.vmin.value(), self.vmax.value())

    def _apply_norm(self, *_):
        if self._canvas is not None:
            self._canvas.set_color_norm(self.log_cb.isChecked(), self.sym_cb.isChecked())

    def _apply_vec_stream(self, *_):
        if self._canvas is not None:
            self._canvas.set_vector_params(self.vec_density.value(), self.vec_scale.value())
            self._canvas.set_stream_params(self.stream_density.value(),
                                           self.stream_lw_cb.isChecked())

    def _on_rendered(self, info: dict):
        self.lbl_var.setText(str(info.get("var", "—")))
        self.lbl_min.setText(f"{info.get('dmin', 0.0):.6g}")
        self.lbl_max.setText(f"{info.get('dmax', 0.0):.6g}")
        stats = self._canvas.integral_stats() if self._canvas is not None else {}
        if stats:
            self.lbl_mean.setText(f"{stats['mean']:.6g}")
            self.lbl_std.setText(f"{stats['std']:.6g}")
            self.lbl_integral.setText(f"{stats['integral']:.6g}")
        else:
            self.lbl_mean.setText(f"{info.get('mean', 0.0):.6g}")
            self.lbl_std.setText("—")
            self.lbl_integral.setText("—")
        # The boxes must describe the range in force for the field ON SCREEN
        # (issue #24). In Auto they follow every render. In Custom they are an
        # INPUT the user may be halfway through typing, so they are refreshed on
        # the two events that make them wrong: the VARIABLE moved, or the canvas
        # SEEDED the range (i.e. it is not a number the user typed — which is also
        # how a newly loaded result, whose store was cleared, gets here even
        # though the variable name did not change).
        var = str(info.get("var", ""))
        # Where a whole-series range is available, and when it is scanned, is
        # stated on the fields it applies to rather than logged on every variable
        # change (#43 moved the scan out of the paint path, so it happens at one
        # moment and that moment has to be findable).
        hint = (self._canvas.series_range_hint()
                if self._canvas is not None else "")
        for w in (self.vmin, self.vmax):
            w.setToolTip(hint)
        if (self.auto_cb.isChecked() or var != self._clim_box_var
                or info.get("clim_seeded")):
            with block_signals(self.vmin, self.vmax):
                self.vmin.setValue(info.get("vmin", 0.0))
                self.vmax.setValue(info.get("vmax", 1.0))
        self._clim_box_var = var
        # A new result drops the canvas's probes -> clear the tables.
        if self._canvas is not None and not getattr(self._canvas, "_probes", []):
            self.probe_table.setRowCount(0)
            self.probe_detail.setRowCount(0)
