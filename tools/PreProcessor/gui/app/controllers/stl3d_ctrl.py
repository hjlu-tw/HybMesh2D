from __future__ import annotations
import os
import re
import shutil

import numpy as np
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from app.models.stl3d_config import (
    Stl3dConfig, stl_bounding_box, detect_stl_ascii, parse_phi_tecplot,
)
from app.services.stl_loader import load_stl_triangles
from app.services.dll_templates import render_phi_field_init
from app.services.phi_quality import FIT_WELL_CELLS, FIT_OK_CELLS
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
        canvas.set_stl(tris)
        canvas.clear_phi()
        panel.send_solver_btn.setEnabled(False)   # result is now stale
        panel.check_fit_btn.setEnabled(False)

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
        """Push the current domain to the 3D overlay (live box/grid update)."""
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

    def fit_stl3d_view(self):
        self.main_window.stl3d_canvas.fit_view()

    def clear_stl3d(self):
        """Clear everything: the loaded STL surface and the phi result."""
        canvas = self.main_window.stl3d_canvas
        panel = self.main_window.stl3d_config_panel
        canvas.set_stl(None)
        canvas.clear_phi()
        self._stl3d_bbox = None
        self._stl3d_tris = None
        self._stl3d_phi_path = ""
        self._stl3d_phi_pts = self._stl3d_phi_val = None
        panel.stl_path.setText("")
        self.global_stl3d_config.stl_path = ""
        panel.send_solver_btn.setEnabled(False)
        panel.check_fit_btn.setEnabled(False)
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
        panel.check_fit_btn.setEnabled(False)
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
            stl_dst = os.path.join(work_dir, os.path.basename(cfg.stl_path))
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
        # The previous phi result is now stale: disable the fit check and drop the
        # cache so it cannot be measured against the new (already-applied) config.
        panel.check_fit_btn.setEnabled(False)
        self._stl3d_phi_pts = self._stl3d_phi_val = None
        self.main_window.stl3d_canvas.clear_fit_deviation()
        pb = self.main_window.progress_bar
        pb.setRange(0, 100)
        pb.setValue(0)
        pb.setVisible(True)
        self.main_window.mode_combo.setCurrentIndex(5)

        omp = max(int(getattr(cfg, "omp_threads", 1) or 1), 1)
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
        panel.check_fit_btn.setEnabled(n_solid > 0)

        log(f"--- STL3d done: {n_solid:,} / {n:,} cells solid ({pct:.1f}%) ---")
        log(f"phi field written to {path}")
        if n_solid == 0:
            log("[WARNING] No solid cells were marked. Check that the domain bounds "
                "(and units) enclose the STL, or switch to the all-elements search.")
        panel.status_lbl.setText(
            f"phi: {n_solid:,}/{n:,} solid ({pct:.1f}%)  →  {os.path.basename(path)}")

    # ------------------------------------------------------------------ #
    # Fit check: how well does phi reproduce the original STL?
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
        panel = self.main_window.stl3d_config_panel
        panel.check_fit_btn.setEnabled(False)
        self._fit_worker = FitCheckWorker(tris, pts, phi, cfg.nx, cfg.ny, cfg.nz, dx, dy, dz)
        self._fit_worker.result_signal.connect(self._on_stl3d_fit_done)
        self._fit_worker.start()

    def _on_stl3d_fit_done(self, m: dict):
        """Render the fit report + deviation heatmap from the worker result."""
        log = self.main_window.log_panel.log
        panel = self.main_window.stl3d_config_panel
        # Re-enable only if a phi result is still present (a clear/run may have
        # invalidated it while the worker was running).
        panel.check_fit_btn.setEnabled(getattr(self, "_stl3d_phi_val", None) is not None)
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
        log(f"  {what}:  φ {m['v_phi']:.6g}   STL {m['v_stl']:.6g}   (Δ {rel_txt})")
        log(f"  surface deviation φ→STL:  mean {m['meanA']:.4g} ({m['meanA'] / h:.2f}h)"
            f"   rms {m['rmsA']:.4g} ({m['rmsA'] / h:.2f}h)"
            f"   max {m['maxA']:.4g} ({m['maxA'] / h:.2f}h)")
        log(f"  symmetric Hausdorff:  {m['hausdorff']:.4g}  ({hd_cells:.2f}h)")
        log(f"  interface cells: {m['n_interface']:,}")
        if hd_cells <= FIT_WELL_CELLS:
            verdict = f"well resolved (max deviation ≤ {FIT_WELL_CELLS:g} cell)."
        elif hd_cells <= FIT_OK_CELLS:
            verdict = "acceptable; raise Nx/Ny/Nz to sharpen the surface."
        else:
            verdict = (f"coarse — under-resolved by ~{hd_cells:.1f} cells; "
                       "increase the grid resolution.")
        log(f"  → {verdict}")

        canvas = self.main_window.stl3d_canvas
        canvas.set_fit_deviation(m["dev_points"], m["dev_values"], h)
        canvas.show_dev_cb.setChecked(True)      # reveal the heatmap
        panel.status_lbl.setText(
            f"Fit: {what} Δ {rel_txt}, Hausdorff {hd_cells:.2f} cells. "
            "Heatmap on (Fit Δ).")

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
