from __future__ import annotations
import os

from PyQt6.QtWidgets import QFileDialog

from app.models.stl3d_config import (
    stl_bounding_box, detect_stl_ascii, parse_phi_tecplot,
)
from app.services.stl_loader import load_stl_triangles
from app.workers.exit_codes import RC_CANCELLED
from app.services import ib_handoff, stl3d_case
from app.workers.stl3d_run import Stl3dWorker
from app.utils import repo_root, report_warning


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
        log = self.log
        panel = self.main_window.stl3d_config_panel
        canvas = self.main_window.stl3d_canvas
        log(f"Reading STL {os.path.basename(path)} … (parsing triangles)")
        try:
            tris = load_stl_triangles(path)
            bbox = stl_bounding_box(path)
        except Exception as e:
            log(f"[STL3d] Failed to read STL: {e}")
            report_warning(self.main_window, "STL Load Failed",
                           "The STL surface could not be read.", detail=str(e))
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
            self.log("[STL3d] Load an STL surface first.")
            return
        panel = self.main_window.stl3d_config_panel
        cfg = panel.get_config()
        cfg.fit_to_bbox(self._stl3d_bbox, margin=panel.margin_spin.value() / 100.0)
        panel.set_config(cfg)
        self.on_stl3d_config_changed()
        self.main_window.stl3d_canvas.fit_view()   # re-frame on the resized box

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
        self.log("[STL3d] Cleared STL surface and phi result.")

    def clear_stl3d_phi(self):
        """Clear only the phi result (keep the STL surface and domain box)."""
        canvas = self.main_window.stl3d_canvas
        panel = self.main_window.stl3d_config_panel
        canvas.clear_phi()
        self._stl3d_phi_path = ""
        self._stl3d_phi_pts = self._stl3d_phi_val = None
        panel.send_solver_btn.setEnabled(False)
        panel.clear_fit_result()
        self.log("[STL3d] Cleared phi result (STL kept).")

    # ------------------------------------------------------------------ #
    # Run / cancel
    # ------------------------------------------------------------------ #
    def run_stl3d(self):
        log = self.log
        if getattr(self, "_stl3d_worker", None) is not None and self._stl3d_worker.isRunning():
            log("STL3d is already running. Please wait.")
            return

        panel = self.main_window.stl3d_config_panel
        cfg = panel.get_config()
        self.global_stl3d_config = cfg

        # Validation + staging live in services/stl3d_case.py so the GUI and the
        # headless pipeline refuse the same cases for the same reasons and lay the
        # work dir out identically.
        try:
            case = stl3d_case.prepare_case_dir(cfg)
        except stl3d_case.Stl3dError as e:
            log(f"[ERROR] {e}")
            return

        work_dir = case["work_dir"]
        para_path = case["para_path"]
        binary = case["binary"]
        self._stl3d_phi_path = case["phi_path"]

        panel.run_btn.setEnabled(False)
        panel.cancel_btn.setEnabled(True)
        panel.send_solver_btn.setEnabled(False)   # pending fresh result
        # The previous phi result is now stale: drop the cache so a late fit-check
        # callback can't pair a new run with the old field.
        self._stl3d_phi_pts = self._stl3d_phi_val = None
        panel.clear_fit_result()
        self.main_window.stl3d_canvas.clear_fit_deviation()
        self.main_window.claim_progress("stl3d", determinate=True)
        self.main_window.mode_combo.setCurrentIndex(5)

        omp = case["threads"]
        log(f"--- Starting STL3d ({stl3d_case.describe(cfg)}) in {work_dir} ---")

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
            self.log("Cancelling STL3d...")
            w.cancel()

    # ------------------------------------------------------------------ #
    # Worker callbacks
    # ------------------------------------------------------------------ #
    def _on_stl3d_progress(self, pct: int):
        self.main_window.set_progress("stl3d", pct)

    def _on_stl3d_finished(self, rc: int):
        self.main_window.release_progress("stl3d")
        panel = self.main_window.stl3d_config_panel
        panel.run_btn.setEnabled(True)
        panel.cancel_btn.setEnabled(False)
        log = self.log

        if rc == RC_CANCELLED:
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
            # Nothing to draw → the "Solid"/"Fluid" toggles look broken even though
            # rendering is fine. Surface the domain box so the user can compare it
            # to the STL extents (the usual cause is a domain/units mismatch).
            cfg0 = getattr(self, "global_stl3d_config", None)
            dom = ""
            if cfg0 is not None:
                try:
                    zr = f", z∈[{pts[:,2].min():.4g},{pts[:,2].max():.4g}]" if n else ""
                    dom = (f" Domain x∈[{cfg0.xmin:.4g},{cfg0.xmax:.4g}], "
                           f"y∈[{cfg0.ymin:.4g},{cfg0.ymax:.4g}]{zr}.")
                except Exception:
                    dom = ""
            log("[WARNING] No solid cells were marked, so both overlays are empty. "
                "Check that the domain bounds (and units) enclose the STL, or switch "
                "to the all-elements search." + dom)
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


    # ------------------------------------------------------------------ #
    # One-click hand-off to the Solver
    # ------------------------------------------------------------------ #
    def send_stl3d_to_solver(self):
        """Stage the phi field, generate the immersed-solid init DLL (grid spec
        baked in), enable IBM in the solver config, and switch to the Solver tab.

        The conversion and the wiring are :mod:`app.services.ib_handoff`, shared
        with Run All and the headless pipeline so all three hand off identically.
        What stays here is this button's own opinion — an STL3d field is a
        STATIONARY solid — and the jump to the Solver tab.
        """
        log = self.log
        cfg = self.global_stl3d_config          # the config the phi result was run with
        phi_tec = getattr(self, "_stl3d_phi_path", "")
        if not phi_tec or not os.path.exists(phi_tec):
            log("[STL3d] Run STL3d successfully before sending to the solver.")
            return

        sc = self.global_solver_config
        try:
            out = ib_handoff.link_phi_to_solver(sc, phi_tec, cfg, repo_root(),
                                                log=log)
        except ib_handoff.IbHandoffError as e:
            log(f"[STL3d] {e}")
            return

        # This button's preset — and the declaration the hand-off deliberately
        # leaves to its caller: pressing "Send to Solver" IS the user saying this
        # solve has an immersed solid, and that it is a solid which does not move.
        sc.immersed_solid = True
        sc.stationary_solid = True
        sc.rigid_moving_body = False
        sc.motion_dll = ""
        # Programmatic push, so it must not be recorded as a user edit; the
        # panel's own _set_config_body refreshes the IBM rows.
        self.push_panel_config(self.main_window.solver_config_panel, sc)
        self.main_window.mode_combo.setCurrentIndex(3)   # Solver

        log("--- Sent STL3d phi field to the Solver ---")
        log(f"  phi data : {out['phi_dat']}")
        log(f"  init DLL : {out['init_dll']}")
        log("  Solver: immersed_solid ON; the init DLL reads phi.dat (staged into "
            "the work dir at run time). Set the mesh (.vrt/.cel/.bnd) and Run Solver.")
