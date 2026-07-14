from __future__ import annotations
import os

from PyQt6.QtWidgets import QFileDialog

from app.models.solver_config import SolverConfig, BC_FLAGS_NEEDING_EXTRA
from app.workers.solver_run import SolverPipelineWorker
from app.services import solver_case
from app.services.solver_case import sanitize_case_name as _sanitize
from app.utils import (
    find_solver_executables, repo_root, find_mpi_launcher, is_mpi_binary,
)


class SolverControllerMixin:
    """Solver pipeline execution + case directory orchestration (D6).

    Owns building case/<name>/{work,grid,dll}, renaming getPGrid output, rewriting
    input.in paths, compiling IBM DLLs, and driving SolverPipelineWorker.
    """

    SOLVER_TAG = ".gui"

    # ------------------------------------------------------------------ #
    def init_solver(self):
        """Populate the solver panel with the global config once at startup."""
        self.main_window.solver_config_panel.set_config(self.global_solver_config)

    # ------------------------------------------------------------------ #
    # Config save / load
    # ------------------------------------------------------------------ #
    def load_solver_config(self):
        root = repo_root()
        path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Load Solver Config",
            os.path.join(root, "config"), "JSON (*.json);;All Files (*)")
        if not path:
            return
        try:
            self.global_solver_config.load_from_file(path)
            self.main_window.solver_config_panel.set_config(self.global_solver_config)
            self.main_window.log_panel.log(f"Loaded solver config from {path}")
        except Exception as e:
            self.main_window.log_panel.log(f"Failed to load solver config: {e}")

    def save_solver_config(self):
        root = repo_root()
        cfg = self.main_window.solver_config_panel.get_config()
        default = os.path.join(root, "config", f"{_sanitize(cfg.case_name)}_solver.json")
        path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Save Solver Config", default, "JSON (*.json);;All Files (*)")
        if not path:
            return
        try:
            cfg.save_to_file(path)
            self.global_solver_config = cfg
            self.main_window.log_panel.log(f"Saved solver config to {path}")
        except Exception as e:
            self.main_window.log_panel.log(f"Failed to save solver config: {e}")

    # ------------------------------------------------------------------ #
    # Run / cancel
    # ------------------------------------------------------------------ #
    def run_solver_pipeline(self):
        if getattr(self, "_solver_worker", None) is not None and self._solver_worker.isRunning():
            self.main_window.log_panel.log("Solver is already running. Please wait.")
            return

        cfg = self.main_window.solver_config_panel.get_config()
        self.global_solver_config = cfg
        log = self.main_window.log_panel.log

        # Auto-link the STAR-CD output of the last mesh generation (D6).
        if self.main_window.solver_config_panel.auto_link_mesh.isChecked():
            if not self._auto_link_mesh_output(cfg):
                return

        for f, label in [(cfg.input_vrt_file, ".vrt"),
                         (cfg.input_cel_file, ".cel"),
                         (cfg.input_bnd_file, ".bnd")]:
            if not f or not os.path.exists(f):
                log(f"[ERROR] getPGrid input {label} not found: {f or '(empty)'}")
                return
        if not cfg.solver_binary or not os.path.exists(cfg.solver_binary):
            log("[ERROR] Solver binary not found. Check the Pipeline Binaries section.")
            return
        if not cfg.getpgrid_binary or not os.path.exists(cfg.getpgrid_binary):
            log("[ERROR] getPGrid binary not found. Check the Pipeline Binaries section.")
            return

        problems = self._validate_solver_config(cfg)
        if problems:
            for p in problems:
                log(f"[ERROR] {p}")
            log("Fix the issues above and run again.")
            return

        try:
            work_dir, grid_dir, input_in_path = self._prepare_case_dir(cfg)
        except Exception as e:
            log(f"[ERROR] Failed to prepare case directory: {e}")
            return

        panel = self.main_window.solver_config_panel
        panel.run_solver_btn.setEnabled(False)
        panel.cancel_solver_btn.setEnabled(True)

        pb = self.main_window.progress_bar
        pb.setRange(0, 100)
        pb.setValue(0)
        pb.setVisible(True)

        self._solver_residuals = []
        self._solver_result_path = os.path.join(
            work_dir, f"xtecp_sol_allz.dat{self.SOLVER_TAG}")

        # Reset the live monitor and show the Solver mode (its canvas is the
        # residual monitor, idx 3).
        monitor = self.main_window.solver_monitor_panel
        monitor.reset()
        self.main_window.mode_combo.setCurrentIndex(3)

        log("--- Starting Solver Pipeline (getPGrid -> "
            + ("bDecompose -> " if cfg.enable_decompose else "")
            + "unicones) ---")

        self._solver_worker = SolverPipelineWorker(
            cfg, getpgrid_dir=grid_dir, solver_work_dir=work_dir,
            input_in_path=input_in_path, tag=self.SOLVER_TAG)
        self._solver_worker.log_signal.connect(log)
        self._solver_worker.stage_signal.connect(self._on_solver_stage)
        self._solver_worker.progress_signal.connect(self._on_solver_progress)
        self._solver_worker.residual_signal.connect(self._on_solver_residual)
        self._solver_worker.finished_signal.connect(self._on_solver_finished)
        self._solver_worker.start()

    def cancel_solver(self):
        w = getattr(self, "_solver_worker", None)
        if w is not None and w.isRunning():
            self.main_window.log_panel.log("Cancelling solver...")
            w.cancel()

    # ------------------------------------------------------------------ #
    # Pre-run validation (D): catch the manual's documented "blow up" setups
    # before launching, instead of failing mid-run.
    # ------------------------------------------------------------------ #
    def _validate_solver_config(self, cfg: SolverConfig) -> list[str]:
        errs: list[str] = []

        # CFL / dt: with constant_cfl=false the solver needs cfl, or dt_const, or
        # a cfl schedule — otherwise the manual says the code blows up.
        has_cfl = cfg.cfl > 0.0
        has_dt = bool(cfg.dt_const.strip())
        has_sched = bool(cfg.cfl_schedule_fn.strip())
        if not cfg.constant_cfl and not (has_cfl or has_dt or has_sched):
            errs.append("Constant CFL is off but neither CFL (>0), dt_const, nor a "
                        "CFL schedule is set — the solver would blow up. Set one.")
        if cfg.unsteady_lstep and not has_cfl:
            errs.append("Unsteady local time stepping (TALTS) needs a positive CFL.")

        # Boundary conditions: segment numbers must be positive and unique.
        segs = [bc.get("segment_no") for bc in cfg.bc_definitions]
        if any((s is None or s <= 0) for s in segs):
            errs.append("Boundary-condition table has a non-positive segment number.")
        dupes = {s for s in segs if segs.count(s) > 1}
        if dupes:
            errs.append(f"Boundary-condition table has duplicate segment(s): "
                        f"{sorted(dupes)}.")
        # Types that carry an extra value must have one filled.
        for bc in cfg.bc_definitions:
            if bc.get("bc_type") in BC_FLAGS_NEEDING_EXTRA and not str(bc.get("values", "")).strip():
                errs.append(f"Segment {bc.get('segment_no')} uses BC type "
                            f"{bc.get('bc_type')} which requires an extra value "
                            f"(wall T / dep-vars / DLL path).")

        # IBM: a moving rigid body needs a motion DLL source.
        if cfg.immersed_solid:
            if cfg.rigid_moving_body and not cfg.motion_dll.strip():
                errs.append("IBM rigid moving body is on but no motion DLL source is set.")
            if not cfg.init_cond_dll.strip():
                self.main_window.log_panel.log(
                    "[WARNING] IBM is on without an init-condition DLL; the solid "
                    "phase will start from freestream init.")

        # Restart needs a zone dump to continue from.
        if cfg.restart and not cfg.zdump_fn_restart.strip():
            errs.append("Restart is on but no restart zone-dump file is set. A "
                        "previous run writes it to results/solver/"
                        f"{_sanitize(cfg.case_name)}/work/binDumpZ.dat.gui "
                        "— point the 'Zone dump' field at it (or Browse).")

        # Domain decomposition implies a real MPI run. Refuse rather than silently
        # partition the grid and then run a serial solver on the un-partitioned mesh.
        if cfg.enable_decompose:
            if find_mpi_launcher() is None:
                errs.append("Domain decomposition (MPI) is enabled but no mpirun/"
                            "mpiexec was found on PATH. Install an MPI runtime or "
                            "turn off decomposition.")
            if not is_mpi_binary(cfg.solver_binary):
                errs.append("Domain decomposition (MPI) is enabled but the solver "
                            "binary is not MPI-capable (no MPI symbols — likely the "
                            "pthread build). Point to an MPI build of unicones or "
                            "turn off decomposition.")

        return errs

    # ------------------------------------------------------------------ #
    # Case directory orchestration (D6)
    # ------------------------------------------------------------------ #
    def _prepare_case_dir(self, cfg: SolverConfig):
        """Build case/<name>/{work,grid,dll}, stage inputs, rename outputs, write
        input.in / .def, and compile IBM DLLs. Returns (work_dir, grid_dir,
        input_in_path). Delegates to the shared, Qt-free solver_case service so
        the GUI and the headless pipeline runner lay out cases identically."""
        return solver_case.prepare_case_dir(cfg, log=self.main_window.log_panel.log)

    def _auto_link_mesh_output(self, cfg: SolverConfig) -> bool:
        """Fill cfg's getPGrid inputs from the last mesh generation's STAR-CD output."""
        log = self.main_window.log_panel.log
        vtk_path = getattr(self, "global_vtk_path", "")
        if not vtk_path:
            log("[ERROR] No mesh generated yet. Generate a mesh (with STAR-CD export) "
                "or uncheck auto-link and pick .vrt/.cel/.bnd manually.")
            return False
        base = os.path.splitext(vtk_path)[0]
        vrt, cel, bnd = base + ".vrt", base + ".cel", base + ".bnd"
        missing = [p for p in (vrt, cel, bnd) if not os.path.exists(p)]
        if missing:
            log("[ERROR] Mesh STAR-CD files missing: "
                + ", ".join(os.path.basename(m) for m in missing)
                + ". Enable 'Export STAR-CD' and regenerate the mesh.")
            return False
        cfg.input_vrt_file, cfg.input_cel_file, cfg.input_bnd_file = vrt, cel, bnd
        log(f"[Solver] Auto-linked mesh output: {os.path.basename(base)}.{{vrt,cel,bnd}}")
        return True

    # ------------------------------------------------------------------ #
    # Bridge mesh boundary patches -> solver BC table (D)
    # ------------------------------------------------------------------ #
    def _locate_mesh_bnd(self) -> str:
        """Find the STAR-CD .bnd of the mesh to assign BCs to: an explicitly set
        .bnd in the Grid Conversion section, else the last generated mesh's .bnd."""
        from app.services.bnd_io import bnd_path_for
        panel = self.main_window.solver_config_panel
        p = panel.input_bnd_file.text().strip()
        if p and os.path.exists(p):
            return p
        vtk = getattr(self, "global_vtk_path", "")
        if vtk:
            b = bnd_path_for(vtk)
            if os.path.exists(b):
                return b
        return ""

    def detect_bc_from_mesh(self):
        """Read the actual boundary patches (segment number + name) from the last
        generated mesh's .bnd and fill the solver BC table, pre-selecting a BC
        type per patch name. This is what carries the per-segment patch names set
        in CAD / 'Edit segment BCs…' through to the solver with the CORRECT
        segment numbers (the mesher numbers segments per patch, not 1-4=box/5=geom)."""
        from app.services.bnd_io import read_bnd_segments
        log = self.main_window.log_panel.log
        bnd = self._locate_mesh_bnd()
        if not bnd:
            log("[ERROR] No mesh .bnd found. Generate a mesh with 'Write STAR-CD' "
                "enabled first, or set the .bnd path in Grid Conversion.")
            return
        segs = read_bnd_segments(bnd)
        if not segs:
            log(f"[WARNING] No boundary patches found in {os.path.basename(bnd)}.")
            return
        panel = self.main_window.solver_config_panel
        euler = panel.flow_solu_type.currentText() == "euler_sol"
        # #4: honour BC types assigned per group/patch NAME in the Mesh Generator
        # (they win over the name-based guess; the name stays as the display label).
        group_bc = getattr(getattr(self, "global_mesh_config", None), "group_bc", {}) or {}
        n = panel.populate_bc_from_segments(segs, euler=euler, group_bc=group_bc)
        listing = ", ".join(f"{sid}={nm or '(unnamed)'}" for sid, nm in segs)
        log(f"[Solver] Detected {n} boundary patch(es) from "
            f"{os.path.basename(bnd)}: {listing}. Review the BC types, then Run.")

    # ------------------------------------------------------------------ #
    # Worker callbacks
    # ------------------------------------------------------------------ #
    def _on_solver_stage(self, stage: str):
        self.main_window.log_panel.log(f"[Stage] {stage}")
        self.main_window.solver_monitor_panel.on_stage(stage)

    def _on_solver_progress(self, pct: int):
        self.main_window.progress_bar.setValue(pct)

    def _on_solver_residual(self, data: dict):
        self._solver_residuals.append(data)
        self.main_window.solver_monitor_panel.on_residual(data)
        l2 = data.get("L2") or []
        l2s = " ".join(f"{v:.2e}" for v in l2[:5])
        self.main_window.log_panel.log(
            f"[convg] iter={data.get('iter')} cfl={data.get('cfl')} L2: {l2s}")

    def _on_solver_finished(self, rc: int):
        self.main_window.progress_bar.setVisible(False)
        self.main_window.solver_monitor_panel.on_finished(rc)
        panel = self.main_window.solver_config_panel
        panel.run_solver_btn.setEnabled(True)
        panel.cancel_solver_btn.setEnabled(False)

        if rc == 0:
            self.main_window.log_panel.log("--- Solver Pipeline Success ---")
            path = getattr(self, "_solver_result_path", "")
            if path and os.path.exists(path):
                self.global_result_path = path
                self.main_window.log_panel.log(f"Result available: {path}")
                # Auto-load into the Results view (PostprocessControllerMixin).
                if hasattr(self, "auto_load_solver_result"):
                    self.auto_load_solver_result()
            else:
                self.main_window.log_panel.log(
                    "[INFO] No Tecplot result file yet (check print_sol_per_niter "
                    "vs the iterations actually run).")
        elif rc == -2:
            self.main_window.log_panel.log("--- Solver Cancelled by User ---")
        else:
            self.main_window.log_panel.log(f"--- Solver Pipeline Failed (code {rc}) ---")

    def _find_solver_executables(self) -> dict:
        return find_solver_executables()

    # ------------------------------------------------------------------ #
    # IBM DLL builder (D7): generate / edit / compile a .cc, then point the
    # solver config's init / motion field at the saved source.
    # ------------------------------------------------------------------ #
    def open_dll_builder(self, dll_type: str):
        from app.views.dll_builder_dialog import DllBuilderDialog
        sp = self.main_window.solver_config_panel
        target = sp.init_cond_dll if dll_type == "init_cond" else sp.motion_dll
        dlg = DllBuilderDialog(self.main_window, dll_type, target.text().strip())
        if dlg.exec() and dlg.result_path:
            target.setText(dlg.result_path)
            self.main_window.log_panel.log(
                f"[IBM] {dll_type} DLL source set: {dlg.result_path}")
