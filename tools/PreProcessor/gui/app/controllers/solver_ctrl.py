from __future__ import annotations
import os
import re
import shutil
import subprocess

from PyQt6.QtWidgets import QFileDialog

from app.models.solver_config import SolverConfig
from app.workers.solver_run import SolverPipelineWorker
from app.utils import find_solver_executables


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))


def _sanitize(name: str) -> str:
    """Make a filesystem-safe case name."""
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    return s or "case"


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
        root = _repo_root()
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
        root = _repo_root()
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
    # Case directory orchestration (D6)
    # ------------------------------------------------------------------ #
    def _prepare_case_dir(self, cfg: SolverConfig):
        """Build case/<name>/{work,grid,dll}, stage inputs, rename outputs, write
        input.in / .def, and compile IBM DLLs. Returns (work_dir, grid_dir,
        input_in_path)."""
        root = _repo_root()
        case = _sanitize(cfg.case_name)
        case_root = os.path.join(root, "results", "solver", case)
        work_dir = os.path.join(case_root, "work")
        grid_dir = os.path.join(case_root, "grid")
        dll_dir = os.path.join(case_root, "dll")
        for d in (work_dir, grid_dir, dll_dir):
            os.makedirs(d, exist_ok=True)
        cfg.work_dir = work_dir

        # getPGrid runs in grid_dir: stage the STAR-CD inputs there with the
        # basenames para.in will reference, and have it write <case>.grid/.bc there.
        stem = case
        cfg.output_grid_file = f"{stem}.grid"
        cfg.output_bc_file = f"{stem}.bc"
        for src, base in [(cfg.input_vrt_file, "input.vrt"),
                          (cfg.input_cel_file, "input.cel"),
                          (cfg.input_bnd_file, "input.bnd")]:
            dst = os.path.join(grid_dir, base)
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copy2(src, dst)
        # Point the config at the staged basenames (para.in uses basenames).
        cfg.input_vrt_file = os.path.join(grid_dir, "input.vrt")
        cfg.input_cel_file = os.path.join(grid_dir, "input.cel")
        cfg.input_bnd_file = os.path.join(grid_dir, "input.bnd")

        # Solver boundary-condition table. The solver reads "<bc>.def" from its
        # cwd; by default it uses getPGrid's own companion verbatim (the worker
        # copies grid/<bc>.def -> work/<bc>.def). Only when the user explicitly
        # fills the BC table do we write an override here (the worker then leaves
        # it in place instead of copying getPGrid's).
        if cfg.bc_definitions:
            def_name = os.path.basename(cfg.output_bc_file) + ".def"
            cfg.generate_bc_def(os.path.join(work_dir, def_name))

        # IBM DLLs (D7): compile .cc sources into dll/, reference as ../dll/*.so.
        if cfg.immersed_solid:
            cfg.init_cond_dll = self._stage_dll(cfg.init_cond_dll, dll_dir)
            cfg.motion_dll = self._stage_dll(cfg.motion_dll, dll_dir)

        # input.in with paths relative to the work dir.
        input_in_path = os.path.join(work_dir, "input.in")
        cfg.generate_input_in(
            input_in_path,
            grid_rel=f"../grid/{stem}.grid",
            bc_rel=f"../grid/{stem}.bc")

        return work_dir, grid_dir, input_in_path

    def _stage_dll(self, src: str, dll_dir: str) -> str:
        """Compile a .cc/.cpp DLL source into dll_dir (or copy a prebuilt .so).

        Returns the path relative to the work dir ("../dll/<name>.so") or "" if
        no source given.
        """
        if not src:
            return ""
        log = self.main_window.log_panel.log
        base = os.path.splitext(os.path.basename(src))[0]
        out_so = os.path.join(dll_dir, f"{base}.so")
        if src.endswith(".so"):
            if os.path.abspath(src) != os.path.abspath(out_so):
                shutil.copy2(src, out_so)
        else:
            if not os.path.exists(src):
                log(f"[WARNING] DLL source not found, skipping: {src}")
                return ""
            cmd = ["g++", "-D_INCLUDE_TEMPLATE_IMPLEMENTATION", "-fPIC",
                   "-shared", "-O3", "-o", out_so, src]
            log(f"[IBM] compiling {os.path.basename(src)} -> {base}.so")
            try:
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode != 0:
                    log(f"[WARNING] DLL compile failed: {r.stderr.strip()}")
                    return ""
            except OSError as e:
                log(f"[WARNING] g++ unavailable, cannot compile DLL: {e}")
                return ""
        return f"../dll/{base}.so"

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
