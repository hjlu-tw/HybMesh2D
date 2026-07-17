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

        # #7: make sure the BC rows reflect the latest Mesh-Generator patch
        # assignments before we snapshot the config for the run.
        self.resync_solver_bc_from_group()
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

        pb = self.main_window.progress_bar
        pb.setRange(0, 100)
        pb.setValue(0)
        pb.setVisible(True)

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
            cfg, tag=self.SOLVER_TAG, prepare=True, overwrite=overwrite)
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

    def resync_solver_bc_from_group(self):
        """#2/#7: make the solver BC rows reflect the CURRENT mesh + the latest
        Mesh-Generator per-patch BC assignments, on entering Solver mode / before
        a run — WITHOUT the user having to click 'Detect from Mesh'.

        The earlier version only patched EXISTING rows by matching the patch NAME
        against ``group_bc``. That silently did nothing when the table was empty,
        default (XMin…/geom), or stale from an older mesh — the patch names didn't
        match, so a BC set in the Mesh Generator reached the solver as the WRONG
        BC (the reported bug). Now: if a mesh .bnd exists and its patch NAMES no
        longer match the table, RE-DETECT from that .bnd (real names + segment
        ids + group_bc). When the table already matches the mesh, only refresh
        the BC types (preserving a manual tweak on an unassigned patch). Also
        warns when a Mesh-Generator assignment isn't present in the current mesh
        (the mesh predates it), since only a regenerate can carry it through."""
        panel = self.main_window.solver_config_panel
        log = self.main_window.log_panel.log
        group_bc = getattr(getattr(self, "global_mesh_config", None), "group_bc", {}) or {}
        euler = panel.flow_solu_type.currentText() == "euler_sol"

        from app.services.bnd_io import read_bnd_segments
        bnd = self._locate_mesh_bnd()
        mesh_names: list[str] = []
        if bnd:
            segs = read_bnd_segments(bnd)
            mesh_names = [nm for _sid, nm in segs]
            table_names = [panel.bc_table.item(r, 1).text().strip()
                           for r in range(panel.bc_table.rowCount())
                           if panel.bc_table.item(r, 1) is not None]
            if segs and mesh_names != table_names:
                # Table is stale vs the mesh — seed it fresh (this applies
                # group_bc too, via detect_bc_from_mesh -> populate_bc_from_segments).
                self.detect_bc_from_mesh()
            elif group_bc and panel.bc_table.rowCount():
                n = panel.resync_bc_types_from_group(group_bc, euler=euler)
                if n:
                    log(f"[Solver] Updated {n} BC row(s) from the current "
                        f"Mesh-Generator patch assignments.")
        elif group_bc and panel.bc_table.rowCount():
            n = panel.resync_bc_types_from_group(group_bc, euler=euler)
            if n:
                log(f"[Solver] Updated {n} BC row(s) from the current "
                    f"Mesh-Generator patch assignments.")

        # Warn about assignments the current mesh can't carry (it predates them):
        # their patch name is not in the mesh .bnd, so the user must regenerate.
        if group_bc and mesh_names:
            missing = [nm for nm in group_bc if nm not in mesh_names]
            if missing:
                log("[Solver] WARNING: Mesh-Generator BC assignment(s) for "
                    f"{', '.join(missing)} are not in the current mesh — "
                    "regenerate the mesh so they reach the solver.")

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

    def open_probe_coords_dialog(self):
        """Enter probe-point coordinates in the GUI, write them to a file and
        link it into the solver config's probe field (#10)."""
        import os
        from PyQt6.QtWidgets import QFileDialog
        from app.views.probe_points_dialog import ProbePointsDialog
        from app.utils import repo_root
        sp = self.main_window.solver_config_panel
        cur = sp.probe_points_def_fn.text().strip()
        initial = ""
        if cur and os.path.exists(cur):
            try:
                with open(cur) as f:
                    initial = f.read()
            except OSError:
                pass
        dlg = ProbePointsDialog(self.main_window, initial)
        if not dlg.exec() or not dlg.points():
            return
        # Reuse the existing path when set, otherwise ask where to save.
        path = cur
        if not path:
            default_dir = os.path.join(repo_root(), "results", "solver")
            os.makedirs(default_dir, exist_ok=True)
            path, _ = QFileDialog.getSaveFileName(
                self.main_window, "Save probe-point file",
                os.path.join(default_dir, "probe_points.dat"),
                "Probe points (*.dat *.txt);;All Files (*)")
            if not path:
                return
        try:
            with open(path, "w") as f:
                f.write(dlg.as_file_text())
        except OSError as e:
            self.main_window.log_panel.log(f"[probe] write failed: {e}")
            return
        sp.probe_points_def_fn.setText(path)
        self.main_window.log_panel.log(
            f"[probe] wrote {len(dlg.points())} point(s) → {path}")
        # Visualise the probe locations on the Results canvas (#5): they persist
        # across variable changes / result reloads, so they overlay the contour
        # once a result is loaded (run the solver, then Load Result).
        try:
            self.main_window.result_canvas_view.set_solver_probe_points(dlg.points())
            self.main_window.log_panel.log(
                "[probe] locations overlaid on the Results canvas "
                "(visible once a result is loaded).")
        except Exception:
            pass

    def refresh_solver_probe_overlay(self):
        """#4: parse the configured probe-point file and overlay its markers on
        the Results canvas, so the probe locations stay visible after a config /
        session reload (the file link survives, so the markers should too). A
        no-op when no probe file is set. Called on entering Solver mode."""
        import os
        from app.views.probe_points_dialog import parse_probe_points
        sp = self.main_window.solver_config_panel
        path = sp.probe_points_def_fn.text().strip()
        if not path or not os.path.exists(path):
            return
        try:
            with open(path) as f:
                pts = parse_probe_points(f.read())
        except OSError:
            return
        try:
            self.main_window.result_canvas_view.set_solver_probe_points(pts)
        except Exception:
            pass

    def open_bc_dll_builder(self):
        """Open the DLL builder for a BC type-11 getQ_inst_dll source (#12) and
        drop the saved path into the selected BC row's Extra values (column 3).
        Falls back to logging the path when no row is selected."""
        from PyQt6.QtWidgets import QTableWidgetItem
        from app.views.dll_builder_dialog import DllBuilderDialog
        from app.services.dll_templates import BC_INFLOW
        sp = self.main_window.solver_config_panel
        row = sp.bc_table.currentRow()
        seed = ""
        if row >= 0 and sp.bc_table.item(row, 3) is not None:
            seed = sp.bc_table.item(row, 3).text().strip()
        dlg = DllBuilderDialog(self.main_window, BC_INFLOW, seed)
        if dlg.exec() and dlg.result_path:
            if row >= 0:
                item = sp.bc_table.item(row, 3) or QTableWidgetItem()
                item.setText(dlg.result_path)
                sp.bc_table.setItem(row, 3, item)
                self.main_window.log_panel.log(
                    f"[BC] type-11 DLL source set on row {row}: {dlg.result_path}")
            else:
                self.main_window.log_panel.log(
                    f"[BC] type-11 DLL source saved (select a BC row to attach): "
                    f"{dlg.result_path}")
