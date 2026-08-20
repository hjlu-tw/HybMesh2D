"""External line-plot dialog openers for ResultCanvasView, split out as a mixin
to keep result_canvas.py under the file-length budget (behaviour unchanged).

Owns the buttons that pop up the WallQuantityDialog with different data: the
solver's wall-quantity columnar outputs and its recorded probe time-history. Lands
on the ResultCanvasView instance, so all ``self.*`` state (_result, _result_path,
_current_var, the cached dialogs) resolves normally.

The surface (arc-length) plot used to live here too; it moved to
``result_canvas_surface_mixin`` when "the surface" stopped being a single implied
curve — the mesh boundary — and became a choice the user makes."""
from __future__ import annotations
import os


class ResultCanvasPlotsMixin:
    """WallQuantity / Probe-history dialog openers."""

    # ------------------------------------------------------------------ #
    def _open_wall_qty(self):
        """Open the wall-quantity line plot, pre-pointed at the current result's
        directory and auto-loading a known wall file if one sits beside it."""
        from app.views.wall_qty_view import WallQuantityDialog
        if self._wall_dialog is None:
            self._wall_dialog = WallQuantityDialog(self)
            from app.utils import keep_on_top, offset_popup
            keep_on_top(self._wall_dialog)                    # above app, not other apps
            offset_popup(self._wall_dialog, self.window())    # off centre (#2/#8)
        dlg = self._wall_dialog
        result_dir = os.path.dirname(getattr(self, "_result_path", "") or "")
        # #10: auto-discover ALL of the solver's columnar outputs (vsurface*,
        # WallForce*, tWall*, turb_solu*) and list them in the File selector.
        dlg.set_result_dir(result_dir)
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
            from app.utils import keep_on_top, offset_popup
            keep_on_top(self._hist_dialog)
            offset_popup(self._hist_dialog, self.window())
        dlg = self._hist_dialog
        dlg.plot_series(x, ys, xlabel="probe output step")
        dlg.setWindowTitle("Solver probe history")
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
