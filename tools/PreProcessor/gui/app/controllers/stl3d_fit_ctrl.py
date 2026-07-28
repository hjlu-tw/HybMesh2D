from __future__ import annotations
import os
import shutil

import numpy as np
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from app.models.stl3d_config import (
    stl_bounding_box, detect_stl_ascii, parse_phi_tecplot,
)
from app.services.stl_loader import load_stl_triangles
from app.services.dll_templates import render_phi_field_init
from app.services.phi_quality import (
    FIT_OK_CELLS, FIT_FRAC_GREEN, FIT_FRAC_AMBER, FIT_TAIL_CELLS, FIT_TAIL_FRAC,
)
from app.workers.stl3d_run import Stl3dWorker
from app.workers.fit_check_run import FitCheckWorker
from app.services.solver_case import sanitize_case_name
from app.utils import repo_root, find_stl3d_binary


def _sanitize(name: str) -> str:
    # Shared sanitizer; STL3d uses "phi" as the empty-name fallback.
    return sanitize_case_name(name, default="phi")


class Stl3dFitControllerMixin:
    def check_stl3d_fit(self):
        """Measure volume/area + surface deviation between the STL and the phi
        field in a background thread, then log a report and paint a deviation
        heatmap (see ``_on_stl3d_fit_done``)."""
        log = self.main_window.log_panel.log
        if getattr(self, "_fit_worker", None) is not None and self._fit_worker.isRunning():
            log("[STL3d] Fit check already running. Please wait.")
            return
        tris = getattr(self, "_stl3d_tris", None)
        pts = getattr(self, "_stl3d_phi_pts", None)
        phi = getattr(self, "_stl3d_phi_val", None)
        if tris is None or pts is None or phi is None or len(phi) == 0:
            log("[STL3d] Run STL3d successfully before checking the fit.")
            return

        cfg = self.global_stl3d_config
        dx, dy, dz = cfg.spacings()
        log("Computing STL ↔ φ fit (volume/area + surface deviation) … (background)")
        # Heavy geometry: run off the GUI thread so the window stays responsive.
        self._fit_worker = FitCheckWorker(tris, pts, phi, cfg.nx, cfg.ny, cfg.nz, dx, dy, dz)
        # Tag the worker with the exact phi field it measures. parse_phi_tecplot
        # returns a fresh array per run (and clears set it to None), so an identity
        # check at result time tells us whether this result still describes the
        # displayed field or was superseded by a later run.
        self._fit_worker._phi_ref = phi
        self._fit_worker.result_signal.connect(self._on_stl3d_fit_done)
        self._fit_worker.start()

    def _on_stl3d_fit_done(self, m: dict):
        """Render the fit report + deviation heatmap from the worker result."""
        log = self.main_window.log_panel.log
        panel = self.main_window.stl3d_config_panel
        # The worker has delivered its result; note which phi field it measured,
        # then drop the reference.
        worker = self._fit_worker
        launched_for = getattr(worker, "_phi_ref", None) if worker is not None else None
        # Free the slot for the next fit, but keep the finished worker alive until
        # its finished() signal fires — dropping the last reference to a QThread
        # whose run() is still unwinding can abort the process.
        self._fit_worker = None
        if worker is not None:
            self._retiring_workers.add(worker)
            worker.finished.connect(lambda w=worker: self._retiring_workers.discard(w))
        current = getattr(self, "_stl3d_phi_val", None)
        # If a clear/run invalidated the phi field while the worker was running,
        # the result describes geometry that is no longer on the canvas — discard
        # it rather than painting a stale heatmap over the cleared scene.
        if current is None:
            log("[STL3d] Fit check result discarded (the phi result was cleared).")
            return
        # A newer run finished while this fit was still computing (its result is
        # for a superseded field). Discarding alone would leave the current field
        # with no verdict — the running-worker guard blocked its own fit check —
        # so kick off a fresh fit for the field now on screen.
        if launched_for is not None and current is not launched_for:
            log("[STL3d] Fit check superseded by a newer run; re-checking the "
                "current φ field.")
            self.check_stl3d_fit()
            return
        if not m or m.get("error"):
            log(f"[STL3d] Fit check: {(m or {}).get('error', 'no result')}.")
            return

        h, dx, dy, dz = m["h"], m["dx"], m["dy"], m["dz"]
        kind = "quasi-2D (in-plane)" if m["quasi2d"] else "3D"
        spc = f"dx={dx:.4g} dy={dy:.4g}" + ("" if m["quasi2d"] else f" dz={dz:.4g}")
        rel = m["v_rel"]
        rel_txt = f"{rel * 100:+.2f}%" if not np.isnan(rel) else "n/a"
        what = "cross-section area" if m["mode"] == "area" else "volume"
        hd_cells = m["hausdorff"] / h if h else 0.0

        log(f"--- STL ↔ φ fit [{kind}] ---")
        log(f"  cell size h = {h:.4g}  ({spc})")
        if np.isnan(m.get("v_phi", float("nan"))):
            log(f"  {what}:  n/a — {m.get('note', 'not comparable for this geometry')}")
        else:
            log(f"  {what}:  φ {m['v_phi']:.6g}   STL {m['v_stl']:.6g}   (Δ {rel_txt})")
        log(f"  surface deviation φ→STL:  mean {m['meanA']:.4g} ({m['meanA'] / h:.2f}h)"
            f"   rms {m['rmsA']:.4g} ({m['rmsA'] / h:.2f}h)"
            f"   max {m['maxA']:.4g} ({m['maxA'] / h:.2f}h)")
        log(f"  symmetric Hausdorff:  {m['hausdorff']:.4g}  ({hd_cells:.2f}h)")
        log(f"  interface cells: {m['n_interface']:,}")

        # Verdict is driven by frac_over_1 — the fraction of the reconstructed
        # surface more than one cell from the STL. It folds in geometry complexity
        # AND slope (a wiggly/steep surface at a coarse grid strands a large share
        # of cells far from the STL) and shrinks as the grid is refined, unlike the
        # average gap. An axis-aligned shape sits exactly on the grid (frac ≈ 0) and
        # so reads "good" at any resolution. A few cusp cells can't move it, so the
        # single worst gap stays a "localized" reference only.
        mean_cells = m["meanA"] / h if h else 0.0
        frac = float(m.get("frac_over_1", 0.0))
        frac_tail = float(m.get("frac_over_tail", 0.0))
        pct_well = (1.0 - frac) * 100.0          # % of surface within 1 cell
        # The size match is a coarse "does the domain (and its units) enclose the
        # STL?" sanity check. A grid-counted area/volume carries an inherent
        # staircase (discretisation) error that scales like ~1/N and can reach a
        # few percent on a coarse grid, so a fixed 5% gate paints good geometry
        # red at low Nx/Ny. Scale the gate with resolution: tight when refined
        # (still catches gross errors — wrong units / a clipped domain are tens of
        # percent to orders of magnitude) and forgiving of the staircase when coarse.
        axes = [m.get("nx", 0), m.get("ny", 0)]
        if not m.get("quasi2d", True):
            axes.append(m.get("nz", 0))
        n_min = max(2, min([int(a) for a in axes if a] or [2]))
        area_tol = min(0.25, max(0.05, 3.0 / n_min))
        area_bad = (not np.isnan(rel)) and abs(rel) > area_tol
        # Tail gate: GREEN needs the bulk within 1 cell AND a clean tail (almost
        # nothing beyond FIT_TAIL_CELLS). "Broadly fine but a minority is loose"
        # then reads amber instead of sneaking to green.
        tail_loose = frac_tail > FIT_TAIL_FRAC

        if area_bad:
            color = "#f85149"      # red
            headline = "✗  Off — φ size doesn't match the STL"
            verdict = (f"{what} off by {rel_txt}; check the domain bounds/units "
                       "enclose the STL.")
        elif frac <= FIT_FRAC_GREEN and not tail_loose:
            color = "#3fb950"      # green
            headline = "✓  Good fit — surface well resolved"
            verdict = f"well resolved ({pct_well:.0f}% of the surface within 1 cell)."
        elif frac <= FIT_FRAC_GREEN:
            # Bulk is fine but the tail gate tripped: a loose minority region.
            color = "#eab308"      # amber
            headline = "≈  Acceptable — a few regions are loose"
            verdict = (f"{pct_well:.0f}% within 1 cell, but {frac_tail * 100:.0f}% is "
                       f">{FIT_TAIL_CELLS:g} cells off; raise Nx/Ny to tighten those "
                       "regions.")
        elif frac <= FIT_FRAC_AMBER:
            color = "#eab308"      # amber
            headline = "≈  Acceptable — surface a little coarse"
            verdict = (f"acceptable ({pct_well:.0f}% within 1 cell); raise Nx/Ny to "
                       "sharpen curved / angled regions.")
        else:
            color = "#f85149"      # red
            headline = "✗  Coarse — surface poorly resolved"
            verdict = (f"only {pct_well:.0f}% of the surface within 1 cell; raise "
                       "Nx/Ny (or check the domain bounds/units enclose the STL).")

        # Worst gap is a reference: large worst + good bulk = a localized sharp
        # feature, not overall under-resolution.
        localized = hd_cells > FIT_OK_CELLS and color != "#f85149"
        log(f"  beyond 1 cell:  {frac * 100:.0f}%   beyond {FIT_TAIL_CELLS:g} cells:  "
            f"{frac_tail * 100:.0f}%  (drive the verdict)")
        log(f"  → {verdict}")
        if localized:
            log(f"     (worst point {hd_cells:.1f} cells is a localized sharp "
                "corner/edge — refining further barely changes it.)")

        canvas = self.main_window.stl3d_canvas
        canvas.set_fit_deviation(m["dev_points"], m["dev_values"], h)
        canvas.show_dev_cb.setChecked(True)      # reveal the heatmap

        # Plain-language card: "% within 1 cell" (the verdict driver) leads, then
        # the average gap + size match; the worst gap follows as a reference (with a
        # sharp-corner note when it is a localized outlier).
        match_label = "Area match" if m["mode"] == "area" else "Volume match"
        match_txt = "n/a" if np.isnan(m.get("v_phi", float("nan"))) else rel_txt
        worst_line = f"Worst gap:  {hd_cells:.1f} cells" + (
            "  (localized sharp corner)" if localized else "")
        within_line = f"Surface within 1 cell:  {pct_well:.0f}%"
        if frac_tail > 0:
            within_line += f"   (>{FIT_TAIL_CELLS:g} cells: {frac_tail * 100:.0f}%)"
        metrics = (
            f"{within_line}\n"
            f"Average gap:  {mean_cells:.1f} cells\n"
            f"{match_label} (φ vs STL):  {match_txt}\n"
            f"{worst_line}"
        )
        panel.set_fit_result(headline, color, metrics)
        panel.status_lbl.setText("Deviation heatmap shown on the canvas (Fit Δ toggle).")
