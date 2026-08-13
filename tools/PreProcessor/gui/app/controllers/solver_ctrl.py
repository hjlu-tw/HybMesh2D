from __future__ import annotations
import os

from PyQt6.QtWidgets import QFileDialog

from app.models.solver_config import SolverConfig, BC_FLAGS_NEEDING_EXTRA
from app.workers.solver_run import SolverPipelineWorker
from app.workers.exit_codes import RC_CANCELLED, RC_TIMEOUT
from app.services import solver_case
from app.services.case_sources import mesh_provenance_paths
from app.services.logging_setup import get_logger
from app.services.solver_case import sanitize_case_name as _sanitize
from app.utils import (
    find_solver_executables, repo_root, find_mpi_launcher, is_mpi_binary,
)

_log = get_logger(__name__)


class SolverControllerMixin:
    """Solver pipeline execution + case directory orchestration (D6).

    Owns building case/<name>/{work,grid,dll}, renaming getPGrid output, rewriting
    input.in paths, compiling IBM DLLs, and driving SolverPipelineWorker.
    """

    SOLVER_TAG = ".gui"

    # ------------------------------------------------------------------ #
    def _case_source_files(self) -> list:
        """The CAD/STL this case is built from, for staging into grid/cad/.

        Three things per case, and each answers a different question. The
        session's ``file_path`` is what the user IMPORTED (the drawing of
        record); ``output_file`` is the resampled ``.dat`` the mesher actually
        read, which is a different curve and the one the grid corresponds to;
        and the STL3d ``stl_path`` is the immersed body, which never touches the
        mesh at all and would otherwise be recorded nowhere in the case.

        Order is import-then-resampled per tab so the folder reads in pipeline
        order. Sidecars (``.dat.meta``, carrying the per-segment BCs) are pulled
        in by the staging service, not listed here.

        The mesh run's ``.provenance.json`` joins them: it is written beside the
        mesh output and records the git sha, the gmsh version and the full config
        as text, which is the difference between "which body?" and "which run?".
        """
        out: list = []
        for session in getattr(self, "sessions", []) or []:
            pm = getattr(session, "project_model", None)
            for path in (getattr(session, "file_path", ""),
                         getattr(pm, "input_file", "") if pm else "",
                         getattr(pm, "output_file", "") if pm else ""):
                if path:
                    out.append(path)
        stl = getattr(getattr(self, "global_stl3d_config", None), "stl_path", "")
        if stl:
            out.append(stl)
        # ``global_vtk_path`` is where the mesh REALLY landed (set by the mesh
        # worker, so it already reflects any auto-named output); the config's
        # ``output_filename`` covers a case whose mesh was generated in an
        # earlier session. The field is ``output_filename``, not ``output_file``
        # — a getattr on the wrong name silently returns the default and stages
        # nothing, which is invisible because a missing provenance file is a
        # legal outcome anyway.
        out.extend(mesh_provenance_paths(
            getattr(self, "global_vtk_path", ""),
            getattr(getattr(self, "global_mesh_config", None),
                    "output_filename", "")))
        return out

    def _case_generated_files(self) -> list:
        """``(name, text)`` the case can only reconstruct, not copy.

        Just the mesh parameter file: the GUI never writes a persistent one — a
        run serialises the live config into ``temp_dir/*_mesh_para.dat`` and that
        directory is removed on exit — so without regenerating it here, the case
        would record every input except the one that shaped its grid.
        """
        from app.models.mesh_config_io import config_to_text
        cfg = getattr(self, "global_mesh_config", None)
        if cfg is None:
            return []
        case = _sanitize(getattr(self, "global_solver_config", None)
                         and self.global_solver_config.case_name or "case")
        try:
            return [(f"Background_para_{case}.dat", config_to_text(cfg))]
        except Exception:
            # A case that stages its geometry but not its settings is still worth
            # having; a run that dies here is not.
            _log.warning("could not serialise the mesh config for the case's "
                         "cad/ folder", exc_info=True)
            return []

    # ------------------------------------------------------------------ #
    def init_solver(self):
        """Populate the solver panel with the global config once at startup."""
        self.push_panel_config(self.main_window.solver_config_panel, self.global_solver_config)

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
            self.push_panel_config(self.main_window.solver_config_panel, self.global_solver_config)
            self.main_window.log_panel.log(f"Loaded solver config from {path}")
        except Exception as e:
            self.main_window.log_panel.log(f"[ERROR] Failed to load solver config: {e}")
            from app.utils import report_warning
            report_warning(self.main_window, "Load Solver Config Failed",
                           "The solver configuration could not be loaded.",
                           detail=str(e))

    def save_solver_config(self):
        root = repo_root()
        # Via the model: a fresh panel-built config carries the DEFAULT length_unit, and
        # the saved JSON would then pair "m" with the mm-derived Linf it also writes —
        # reloading it re-derives Linf from "m" and silently multiplies the case's
        # Reynolds number by 1000.
        cfg = self.config_from_panel("solver_config_panel")
        default = os.path.join(root, "config", f"{_sanitize(cfg.case_name)}_solver.json")
        path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Save Solver Config", default, "JSON (*.json);;All Files (*)")
        if not path:
            return
        try:
            cfg.save_to_file(path)
            self.main_window.log_panel.log(f"Saved solver config to {path}")
        except Exception as e:
            self.main_window.log_panel.log(f"[ERROR] Failed to save solver config: {e}")
            from app.utils import report_error
            report_error(self.main_window, "Save Solver Config Failed",
                         "The solver configuration could not be saved to disk.",
                         detail=str(e))

    # ------------------------------------------------------------------ #
    # Run / cancel
    # ------------------------------------------------------------------ #
    def run_solver_pipeline(self):
        if getattr(self, "_solver_worker", None) is not None and self._solver_worker.isRunning():
            self.main_window.log_panel.log("Solver is already running. Please wait.")
            return

        cfg = self.config_from_panel("solver_config_panel")
        log = self.main_window.log_panel.log

        # Auto-link the STAR-CD output of the last mesh generation (D6).
        if self.main_window.solver_config_panel.auto_link_mesh.isChecked():
            if not self._auto_link_mesh_output(cfg):
                return

        # #7: make sure the BC rows reflect the latest Mesh-Generator patch
        # assignments. AFTER the auto-link, not before: the rows are seeded from
        # the mesh .bnd, and with auto-link on that file is only decided above —
        # resyncing first read whatever stale path the panel still displayed, so
        # the table could describe one grid while the run used another.
        self.resync_solver_bc_from_group()
        # ...and pick the refreshed rows back up. The grid paths are the one thing the
        # auto-link above owns right now — it wrote them onto cfg and not onto the panel,
        # which still shows whatever an earlier "Send to Solver" left there — so they are
        # preserved while everything else is re-read. That is exactly what extra_preserve
        # is for; building a second throwaway config to copy one field out of it was the
        # older way of saying the same thing.
        self.sync_panel_to_model(
            "solver_config_panel",
            extra_preserve=("input_vrt_file", "input_cel_file", "input_bnd_file"))

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

        # Everything else about this run is valid — but does the grid actually
        # carry the boundary conditions the Mesh stage assigned? A mesh generated
        # before the per-segment BCs were applied exports every patch as `wall`,
        # and the run then looks exactly like a converged, unchanged answer.
        # Asked last, so the user is never prompted about a run that then aborts
        # on a missing binary.
        if not self._confirm_mesh_bc_state(cfg.input_bnd_file):
            log("Solver run cancelled — regenerate the mesh to carry the BCs in.")
            return

        # Overwrite protection: a re-run of the same case name must not silently
        # clobber prior results. Decide here (on the GUI thread, where we can
        # prompt) whether to reuse the existing dir or auto-version a new one;
        # the actual (blocking) staging + DLL compile happens in the worker.
        overwrite = self._resolve_case_overwrite(cfg)
        if overwrite is None:
            return  # user cancelled

        panel = self.main_window.solver_config_panel
        panel.run_solver_btn.setEnabled(False)
        panel.cancel_solver_btn.setEnabled(True)

        self.main_window.claim_progress("solver", determinate=True)

        self._solver_residuals = []
        # Set once the worker reports the real (possibly auto-versioned) work dir.
        self._solver_result_path = ""

        # Reset the live monitor and show the Solver mode (its canvas is the
        # residual monitor, idx 3).
        monitor = self.main_window.solver_monitor_panel
        monitor.reset()
        self.main_window.mode_combo.setCurrentIndex(3)

        log("--- Starting Solver Pipeline (getPGrid -> "
            + ("bDecompose -> " if cfg.enable_decompose else "")
            + "unicones) ---")

        self._solver_worker = SolverPipelineWorker(
            cfg, tag=self.SOLVER_TAG, prepare=True, overwrite=overwrite,
            sources=self._case_source_files(),
            generated_sources=self._case_generated_files())
        self._solver_worker.log_signal.connect(log)
        self._solver_worker.prepared_signal.connect(self._on_solver_prepared)
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
        the GUI and the headless pipeline runner lay out cases identically.

        Note: the interactive Run path no longer calls this on the GUI thread
        (it would freeze the window during the g++ DLL compile); the solver
        worker runs prepare_case_dir itself. Kept for completeness / callers
        that want a synchronous prepare."""
        return solver_case.prepare_case_dir(cfg, log=self.main_window.log_panel.log)

    def _resolve_case_overwrite(self, cfg: SolverConfig):
        """Return True to overwrite the existing case dir, False to auto-version
        a new one, or None if the user cancelled.

        Only prompts when a case dir of this name already holds prior results;
        otherwise returns False (nothing to preserve, so the default dir is used
        as-is by the worker)."""
        from PyQt6.QtWidgets import QMessageBox
        root = repo_root()
        case = _sanitize(cfg.case_name)
        case_root = os.path.join(root, "results", "solver", case)
        if not solver_case._dir_has_content(case_root):
            return False

        # Run All (pipeline batch) must run unattended: never pop a modal. Preserve
        # prior results by auto-versioning a new dir (overwrite=False) instead of
        # blocking. The worker reports the real (versioned) work dir via
        # prepared_signal, so the Results stage still finds the output.
        if getattr(self, "_pipeline_running", False):
            self.main_window.log_panel.log(
                f"[case] '{case}' already has results; Run All auto-versions a new "
                "directory to preserve them.")
            return False

        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Case already exists")
        box.setText(
            f"Solver results for case '{case}' already exist at\n{case_root}")
        box.setInformativeText(
            "Overwrite the existing results, or keep them and run into a new "
            f"auto-versioned directory (e.g. '{case}_002')?")
        overwrite_btn = box.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
        new_btn = box.addButton("New Versioned Dir", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(new_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_btn:
            self.main_window.log_panel.log("Solver run cancelled (case exists).")
            return None
        if clicked is overwrite_btn:
            self.main_window.log_panel.log(
                f"[case] overwriting existing results for '{case}'.")
            return True
        return False

    def _on_solver_prepared(self, work_dir: str):
        """The worker finished staging the (possibly auto-versioned) case dir;
        record where the Tecplot result will land."""
        self._solver_result_path = os.path.join(
            work_dir, f"xtecp_sol_allz.dat{self.SOLVER_TAG}")

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

    def _confirm_mesh_bc_state(self, bnd_path: str) -> bool:
        """True to go ahead with this grid.

        USER-REPORTED: "I updated the STAR-CD boundary conditions and the solver
        still gives the same result." The grid it ran was all-`wall` — the BCs
        had been re-applied after that mesh was generated, and every step from
        there (export, send, run) simply passed the stale file along. The mesher
        does warn, but at mesh time, several clicks earlier. So the last step
        before the solve looks at the grid itself and makes the user choose;
        `headless_default=True` keeps batch/CI runs (which regenerate the mesh in
        the same pass) moving. The lines are not logged here — the resync a few
        lines up already did that for the same grid."""
        problems = self.mesh_bc_problems(bnd_path)
        if not problems:
            return True
        from app.utils import confirm
        return confirm(
            self.main_window, "Boundary conditions may not be in this grid",
            problems[0] + "\n\nRun the solver on it anyway?",
            detail="\n\n".join(problems[1:]), headless_default=True)

    # ------------------------------------------------------------------ #
    # Bridge mesh boundary patches -> solver BC table (D)
    # ------------------------------------------------------------------ #


    # ------------------------------------------------------------------ #
    # Worker callbacks
    # ------------------------------------------------------------------ #
    def _on_solver_stage(self, stage: str):
        self.main_window.log_panel.log(f"[Stage] {stage}")
        self.main_window.solver_monitor_panel.on_stage(stage)

    def _on_solver_progress(self, pct: int):
        self.main_window.set_progress("solver", pct)

    def _on_solver_residual(self, data: dict):
        self._solver_residuals.append(data)
        self.main_window.solver_monitor_panel.on_residual(data)
        l2 = data.get("L2") or []
        l2s = " ".join(f"{v:.2e}" for v in l2[:5])
        self.main_window.log_panel.log(
            f"[convg] iter={data.get('iter')} cfl={data.get('cfl')} L2: {l2s}")

    def _on_solver_finished(self, rc: int):
        self.main_window.release_progress("solver")
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
        elif rc == RC_CANCELLED:
            self.main_window.log_panel.log("--- Solver Cancelled by User ---")
        elif rc == RC_TIMEOUT:
            self.main_window.log_panel.log("--- Solver Pipeline Timed Out ---")
        else:
            self.main_window.log_panel.log(f"--- Solver Pipeline Failed (code {rc}) ---")

    def _find_solver_executables(self) -> dict:
        return find_solver_executables()

    # ------------------------------------------------------------------ #
    # IBM DLL builder (D7): generate / edit / compile a .cc, then point the
    # solver config's init / motion field at the saved source.
    # ------------------------------------------------------------------ #
