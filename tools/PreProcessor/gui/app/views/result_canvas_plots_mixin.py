"""External line-plot dialog openers for ResultCanvasView, split out as a mixin
to keep result_canvas.py under the file-length budget (behaviour unchanged).

Owns the buttons that pop up the WallQuantityDialog with different data:
wall-quantity columnar outputs, surface (perimeter) quantities, and the solver's
recorded probe time-history. Lands on the ResultCanvasView instance, so all
``self.*`` state (_result, _result_path, _current_var, the cached dialogs)
resolves normally."""
from __future__ import annotations
import os
import numpy as np
from PyQt6.QtCore import Qt


class ResultCanvasPlotsMixin:
    """WallQuantity / Surface / Probe-history dialog openers."""

    # ------------------------------------------------------------------ #
    def _open_wall_qty(self):
        """Open the wall-quantity line plot, pre-pointed at the current result's
        directory and auto-loading a known wall file if one sits beside it."""
        from app.views.wall_qty_view import WallQuantityDialog
        if self._wall_dialog is None:
            self._wall_dialog = WallQuantityDialog(self)
            self._wall_dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)  # (#2/#8)
        dlg = self._wall_dialog
        result_dir = os.path.dirname(getattr(self, "_result_path", "") or "")
        # #10: auto-discover ALL of the solver's columnar outputs (vsurface*,
        # WallForce*, tWall*, turb_solu*) and list them in the File selector.
        dlg.set_result_dir(result_dir)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _open_surface_plot(self):
        """#11/#8: sample surface quantities along the geometry perimeter (arc
        length) and open them in the line-plot viewer, so Cp / p / the active
        field are all pickable in the plot's Y selector. Cp is always offered
        when the result can derive it (not only when it is the active variable)."""
        from app.views.wall_qty_view import WallQuantityDialog
        if self._result is None:
            return
        avail = set(self._result.scalar_variables())
        # Cp first so it is the default Y; then the active variable, then raw p.
        wanted = [q for q in ("Cp", self._current_var(), "p") if q and q in avail]
        wanted = list(dict.fromkeys(wanted))     # de-dup, preserve order
        s_ref = xc_ref = yc_ref = None
        vals_by_var: dict = {}
        for q in wanted:
            try:
                series = self._result.perimeter_series(q)
            except Exception:
                continue
            if not series:
                continue
            # Use the longest loop as the main surface (multi-element: biggest).
            s, xc, yc, vals = max(series, key=lambda t: len(t[0]))
            if s_ref is None:
                s_ref, xc_ref, yc_ref = s, xc, yc
            vals_by_var[q] = vals
        if s_ref is None:
            return
        ys = {q: np.asarray(v) for q, v in vals_by_var.items()}
        # Offer x/y coords as alternative abscissae (Cp-vs-x is conventional).
        ys["x"] = np.asarray(xc_ref); ys["y"] = np.asarray(yc_ref)
        if self._surf_dialog is None:
            self._surf_dialog = WallQuantityDialog(self)
            self._surf_dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        dlg = self._surf_dialog
        dlg.plot_series(np.asarray(s_ref), ys, xlabel="s (arc length)")
        primary = next(iter(vals_by_var), "")
        dlg.setWindowTitle(f"Surface {primary} vs arc length")
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _open_probe_history(self):
        """#4: open the solver's RECORDED probe time-history (probe_data.gui)
        found beside the loaded result — the actual values the solver logged at
        each probe over the run, not an interpolation of the current field."""
        from PyQt6.QtWidgets import QMessageBox
        from app.views.wall_qty_view import WallQuantityDialog
        from app.services.probe_history import (
            read_probe_history, PROBE_VARS, PROBE_VAR_LABELS)
        work = os.path.dirname(getattr(self, "_result_path", "") or "")
        hist = read_probe_history(work) if work else None
        if not hist:
            QMessageBox.information(
                self, "Probe History",
                "No recorded probe history (probe_data.gui) was found next to "
                "this result.\n\nSet a probe-point file in the Solver config and "
                "re-run the solver, then Load the result from that case.")
            return
        # One shared iteration axis (all probes use the same output cadence); one
        # y-series per probe × flow variable (x/y are the sample location, not
        # useful as a time series, so they are skipped).
        multi = len(hist.series) > 1
        x = hist.steps(0)
        ys: dict = {}
        for k, s in enumerate(hist.series):
            for var in PROBE_VARS:
                if var in ("x", "y"):
                    continue
                lbl = PROBE_VAR_LABELS.get(var, var)
                key = f"{lbl} @P{s['idx']}" if multi else lbl
                ys[key] = hist.column(k, var)
        if self._hist_dialog is None:
            self._hist_dialog = WallQuantityDialog(self)
            self._hist_dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        dlg = self._hist_dialog
        dlg.plot_series(x, ys, xlabel="probe output step")
        dlg.setWindowTitle("Solver probe history")
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
