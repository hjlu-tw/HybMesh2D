from __future__ import annotations
import os
import re
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
from app.utils import repo_root, find_stl3d_binary


def _sanitize(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    return s or "phi"


class Stl3dControllerMixin:
    """STL3d immersed-solid preprocessor: load STL, edit the Cartesian domain
    with a live 3D overlay, run ``stl3d < para.in``, and visualise the phi field.

    Owns the STL3d work dir (results/stl3d/<case>/), para.in staging, and the
    Stl3dWorker lifecycle. Wired in controller.py alongside the other mixins.
    """

    # ------------------------------------------------------------------ #
    def init_stl3d(self):
        panel = self.main_window.stl3d_config_panel
        panel.set_config(self.global_stl3d_config)
        self.main_window.stl3d_canvas.set_domain(self.global_stl3d_config.domain)

    # ------------------------------------------------------------------ #
    # STL loading + live overlay
    # ------------------------------------------------------------------ #
    def browse_stl3d(self):
        path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Select STL Surface",
            os.path.join(repo_root(), "examples", "geometries"),
            "STL Files (*.stl);;All Files (*)")
        if path:
            self._load_stl3d(path, auto_fit=True)

    def _load_stl3d(self, path: str, auto_fit: bool):
        log = self.main_window.log_panel.log
        panel = self.main_window.stl3d_config_panel
        canvas = self.main_window.stl3d_canvas
        log(f"Reading STL {os.path.basename(path)} … (parsing triangles)")
        try:
            tris = load_stl_triangles(path)
            bbox = stl_bounding_box(path)
        except Exception as e:
            log(f"[STL3d] Failed to read STL: {e}")
            QMessageBox.warning(self.main_window, "STL Error", str(e))
            return

        self._stl3d_bbox = bbox
        self._stl3d_tris = tris                   # cached for the fit check
        # A new STL invalidates any prior run's phi result: drop the cache so the
        # fit check can never pair the new triangles with a stale phi field.
        self._stl3d_phi_path = ""
        self._stl3d_phi_pts = self._stl3d_phi_val = None
        canvas.set_stl(tris)
        canvas.clear_phi()
        panel.send_solver_btn.setEnabled(False)   # result is now stale
        panel.clear_fit_result()

        cfg = panel.get_config()
        cfg.stl_path = path
        cfg.ascii = detect_stl_ascii(path)
        if auto_fit:
            cfg.fit_to_bbox(bbox, margin=panel.margin_spin.value() / 100.0)
        panel.set_config(cfg)
        self.global_stl3d_config = cfg

        self.on_stl3d_config_changed()
        canvas.fit_view()

        x0, x1, y0, y1, z0, z1 = bbox
        log(f"[STL3d] Loaded {os.path.basename(path)}: {len(tris)} triangles, "
            f"bbox x[{x0:.4g}, {x1:.4g}] y[{y0:.4g}, {y1:.4g}] z[{z0:.4g}, {z1:.4g}]")
        panel.status_lbl.setText(
            f"{os.path.basename(path)} — {len(tris):,} triangles. Edit the domain, then Generate phi.")

    def on_stl3d_config_changed(self):
        """Push the current domain to the 3D overlay (live box update)."""
        cfg = self.main_window.stl3d_config_panel.get_config()
        self.main_window.stl3d_canvas.set_domain(cfg.domain)

    def on_stl3d_display_changed(self):
        # The display toggles / z-slice now live on the 3D canvas's own top bar;
        # just re-apply its current state to the scene.
        self.main_window.stl3d_canvas.apply_display()

    def fit_stl3d_domain(self):
        if getattr(self, "_stl3d_bbox", None) is None:
            self.main_window.log_panel.log("[STL3d] Load an STL surface first.")
            return
        panel = self.main_window.stl3d_config_panel
        cfg = panel.get_config()
        cfg.fit_to_bbox(self._stl3d_bbox, margin=panel.margin_spin.value() / 100.0)
        panel.set_config(cfg)
        self.on_stl3d_config_changed()
        self.main_window.stl3d_canvas.fit_view()   # re-frame on the resized box

    def fit_stl3d_view(self):
        self.main_window.stl3d_canvas.fit_view()

    def clear_stl3d(self):
        """Clear everything: the loaded STL surface and the phi result."""
        canvas = self.main_window.stl3d_canvas
        panel = self.main_window.stl3d_config_panel
        canvas.set_stl(None)
        canvas.clear_phi()
        canvas.clear_domain()                     # also drop the cyan domain box
        self._stl3d_bbox = None
        self._stl3d_tris = None
        self._stl3d_phi_path = ""
        self._stl3d_phi_pts = self._stl3d_phi_val = None
        panel.stl_path.setText("")
        self.global_stl3d_config.stl_path = ""
        panel.send_solver_btn.setEnabled(False)
        panel.clear_fit_result()
        panel.status_lbl.setText("Load an STL surface to begin.")
        self.main_window.log_panel.log("[STL3d] Cleared STL surface and phi result.")

    def clear_stl3d_phi(self):
        """Clear only the phi result (keep the STL surface and domain box)."""
        canvas = self.main_window.stl3d_canvas
        panel = self.main_window.stl3d_config_panel
        canvas.clear_phi()
        self._stl3d_phi_path = ""
        self._stl3d_phi_pts = self._stl3d_phi_val = None
        panel.send_solver_btn.setEnabled(False)
        panel.clear_fit_result()
        self.main_window.log_panel.log("[STL3d] Cleared phi result (STL kept).")

    # ------------------------------------------------------------------ #
    # Run / cancel
    # ------------------------------------------------------------------ #
    def run_stl3d(self):
        log = self.main_window.log_panel.log
        if getattr(self, "_stl3d_worker", None) is not None and self._stl3d_worker.isRunning():
            log("STL3d is already running. Please wait.")
            return

        panel = self.main_window.stl3d_config_panel
        cfg = panel.get_config()
        self.global_stl3d_config = cfg

        if not cfg.stl_path or not os.path.exists(cfg.stl_path):
            log("[ERROR] No STL file selected. Use the STL Input browse button.")
            return
        binary = find_stl3d_binary()
        if not binary:
            log("[ERROR] STL3d binary not found under solver/preprocess/STL3d/.")
            return
        if cfg.xmax <= cfg.xmin or cfg.ymax <= cfg.ymin:
            log("[ERROR] Domain X and Y ranges must have max > min.")
            return

        try:
            work_dir = os.path.join(repo_root(), "results", "stl3d", _sanitize(cfg.case_name))
            os.makedirs(work_dir, exist_ok=True)
            # Stage under a whitespace-safe basename matching para.in line 1: STL3d
            # reads the filename with cin>>, so a space in the source name (e.g. a
            # CAD profile "my model" → "my model_2d.stl") would otherwise misalign
            # the whole para.in and crash/hang the binary.
            stl_dst = os.path.join(work_dir, cfg.stl_run_basename())
            if os.path.abspath(cfg.stl_path) != os.path.abspath(stl_dst):
                shutil.copy2(cfg.stl_path, stl_dst)
            para_path = os.path.join(work_dir, "para.in")
            with open(para_path, "w") as f:
                f.write(cfg.para_in_text())
        except OSError as e:
            log(f"[ERROR] Failed to stage STL3d work dir: {e}")
            return

        _, phi_name = cfg.output_basenames()
        self._stl3d_phi_path = os.path.join(work_dir, phi_name)

        panel.run_btn.setEnabled(False)
        panel.cancel_btn.setEnabled(True)
        panel.send_solver_btn.setEnabled(False)   # pending fresh result
        # The previous phi result is now stale: drop the cache so a late fit-check
        # callback can't pair a new run with the old field.
        self._stl3d_phi_pts = self._stl3d_phi_val = None
        panel.clear_fit_result()
        self.main_window.stl3d_canvas.clear_fit_deviation()
        pb = self.main_window.progress_bar
        pb.setRange(0, 100)
        pb.setValue(0)
        pb.setVisible(True)
        self.main_window.mode_combo.setCurrentIndex(5)

        omp = (max(int(getattr(cfg, "omp_threads", 1) or 1), 1)
               if getattr(cfg, "omp_enabled", False) else 1)
        log(f"--- Starting STL3d ({cfg.nx}x{cfg.ny}x{cfg.nz} grid, "
            f"{'all-element' if cfg.all_search else 'close x-range'} search, "
            f"{'serial' if omp == 1 else f'OpenMP {omp} threads'}) in {work_dir} ---")

        log("[STL3d] Working… loading STL and building the search structure, then "
            "ray tracing (a large STL / all-element search can take a while).")
        self._stl3d_worker = Stl3dWorker(binary, work_dir, para_path, cfg.nx, threads=omp)
        self._stl3d_worker.log_signal.connect(log)
        self._stl3d_worker.progress_signal.connect(self._on_stl3d_progress)
        self._stl3d_worker.finished_signal.connect(self._on_stl3d_finished)
        self._stl3d_worker.start()

    def cancel_stl3d(self):
        w = getattr(self, "_stl3d_worker", None)
        if w is not None and w.isRunning():
            self.main_window.log_panel.log("Cancelling STL3d...")
            w.cancel()

    # ------------------------------------------------------------------ #
    # Worker callbacks
    # ------------------------------------------------------------------ #
    def _on_stl3d_progress(self, pct: int):
        self.main_window.progress_bar.setValue(pct)

    def _on_stl3d_finished(self, rc: int):
        self.main_window.progress_bar.setVisible(False)
        panel = self.main_window.stl3d_config_panel
        panel.run_btn.setEnabled(True)
        panel.cancel_btn.setEnabled(False)
        log = self.main_window.log_panel.log

        if rc == -2:
            log("--- STL3d Cancelled by User ---")
            return
        if rc != 0:
            log(f"--- STL3d Failed (code {rc}) ---")
            return

        path = getattr(self, "_stl3d_phi_path", "")
        if not path or not os.path.exists(path):
            log("[ERROR] STL3d finished but the phi output file was not found.")
            return
        log("Parsing phi output … (reading the Tecplot field)")
        try:
            pts, phi = parse_phi_tecplot(path)
        except Exception as e:
            log(f"[ERROR] Failed to parse phi output: {e}")
            return

        n = len(phi)
        n_solid = int((phi > 0.5).sum())
        pct = (100.0 * n_solid / n) if n else 0.0

        # Cache the parsed field so Check Fit doesn't re-read the file.
        self._stl3d_phi_pts = pts
        self._stl3d_phi_val = phi

        canvas = self.main_window.stl3d_canvas
        log(f"Rendering phi field … ({n:,} cells)")
        canvas.set_phi(pts, phi)
        canvas.set_slice_max(canvas.n_z_levels)
        self.on_stl3d_display_changed()
        # A fresh phi result exists: enable the one-click hand-off + fit check.
        panel.send_solver_btn.setEnabled(n_solid > 0)

        log(f"--- STL3d done: {n_solid:,} / {n:,} cells solid ({pct:.1f}%) ---")
        log(f"phi field written to {path}")
        if n_solid == 0:
            log("[WARNING] No solid cells were marked. Check that the domain bounds "
                "(and units) enclose the STL, or switch to the all-elements search.")
        panel.status_lbl.setText(
            f"phi: {n_solid:,}/{n:,} solid ({pct:.1f}%)  →  {os.path.basename(path)}")

        # Auto-run the fit check so the STL↔φ agreement appears without an extra
        # click. It runs in a background thread (see check_stl3d_fit); only when
        # there is a solid to measure against the STL.
        if n_solid > 0:
            self.check_stl3d_fit()

    # ------------------------------------------------------------------ #
    # Fit check: how well does phi reproduce the original STL?
    # Runs automatically after a successful Generate phi (_on_stl3d_finished).
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # One-click hand-off to the Solver
    # ------------------------------------------------------------------ #
    def send_stl3d_to_solver(self):
        """Stage the phi field, generate the immersed-solid init DLL (grid spec
        baked in), enable IBM in the solver config, and switch to the Solver tab."""
        log = self.main_window.log_panel.log
        cfg = self.global_stl3d_config          # the config the phi result was run with
        phi_tec = getattr(self, "_stl3d_phi_path", "")
        if not phi_tec or not os.path.exists(phi_tec):
            log("[STL3d] Run STL3d successfully before sending to the solver.")
            return

        case = _sanitize(cfg.case_name)
        work_dir = os.path.dirname(phi_tec)

        # 1. Headerless phi.dat (x y z phi) — what the generated DLL reads.
        phi_dat = os.path.join(work_dir, f"{case}_phi.dat")
        try:
            with open(phi_tec) as fin, open(phi_dat, "w") as fout:
                for n, line in enumerate(fin):
                    if n >= 3:                  # strip the 3 Tecplot header lines
                        fout.write(line)
        except OSError as e:
            log(f"[STL3d] Failed to write phi data: {e}")
            return

        # 2. Init-condition DLL with the STL3d grid spec baked in.
        dx, dy, dz = cfg.spacings()
        src = render_phi_field_init(
            xmin=cfg.xmin, ymin=cfg.ymin, zmin=cfg.zmin,
            dx=dx, dy=dy, dz=dz, nx=cfg.nx, ny=cfg.ny, nz=cfg.nz)
        dll_dir = os.path.join(repo_root(), "results", "solver", "dll_src")
        try:
            os.makedirs(dll_dir, exist_ok=True)
            dll_cc = os.path.join(dll_dir, f"ibm_init_{case}.cc")
            with open(dll_cc, "w") as f:
                f.write(src)
        except OSError as e:
            log(f"[STL3d] Failed to write init DLL source: {e}")
            return

        # 3. Wire the solver config + panel, then jump to the Solver tab.
        sc = self.global_solver_config
        sc.immersed_solid = True
        sc.stationary_solid = True
        sc.rigid_moving_body = False
        sc.motion_dll = ""
        sc.init_cond_dll = dll_cc
        sc.ibm_phi_file = phi_dat
        panel = self.main_window.solver_config_panel
        panel.set_config(sc)
        if hasattr(panel, "_update_ibm_visibility"):
            panel._update_ibm_visibility()
        self.main_window.mode_combo.setCurrentIndex(3)   # Solver

        log("--- Sent STL3d phi field to the Solver ---")
        log(f"  phi data : {phi_dat}")
        log(f"  init DLL : {dll_cc}")
        log("  Solver: immersed_solid ON; the init DLL reads phi.dat (staged into "
            "the work dir at run time). Set the mesh (.vrt/.cel/.bnd) and Run Solver.")
