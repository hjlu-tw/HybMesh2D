"""Full-pipeline orchestration for the GUI: one action runs CAD resample ->
mesh generation -> solver -> results contour, by chaining the existing
per-stage workers on their finished signals.

Each stage already runs in its own QThread with a ``finished_signal``; this
mixin sequences them without blocking the UI and suppresses the per-stage
dialogs (output path, unclosed prompt) so a single click runs to the contour.

Also owns save/load of the unified pipeline JSON (a shareable, human-editable
script consumed identically by ``tools/PreProcessor/run_pipeline.py``).
"""
from __future__ import annotations
import os

import numpy as np
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from app.models.pipeline_config import PipelineConfig, PIPELINE_FORMAT_VERSION
from app.utils import repo_root


class PipelineControllerMixin:

    # ------------------------------------------------------------------ #
    # Run All
    # ------------------------------------------------------------------ #
    def run_full_pipeline(self):
        """Chain resample -> mesh -> solver -> results for the active geometry."""
        if getattr(self, "_pipeline_running", False):
            self.main_window.log_panel.log("Pipeline is already running. Please wait.")
            return

        session = self.active_session()
        if session is None or (session.original_points is None
                               and not session.project_model.segments):
            self.main_window.log_panel.log(
                "[Pipeline] No active geometry. Load or draw a geometry first.")
            return
        if not self._find_executable():
            self.main_window.log_panel.log(
                "[Pipeline] surface_resampler not found — run ./build.sh.")
            return

        self._pipeline_running = True
        self._set_run_all_enabled(False)
        # Remember the result variable to show at the end (set via a saved
        # pipeline file, otherwise the canvas default).
        self._pipeline_result_var = getattr(self, "_pipeline_result_var", "")
        self.main_window.log_panel.log(
            "=== Run Full Pipeline: CAD -> Mesh -> Solver -> Results ===")
        self._pipe_resample(session)

    def _set_run_all_enabled(self, enabled: bool):
        btn = getattr(self.main_window, "run_all_btn", None)
        if btn is not None:
            btn.setEnabled(enabled)

    def _pipeline_abort(self, msg: str):
        self.main_window.log_panel.log(f"[Pipeline] Aborted: {msg}")
        self._pipeline_running = False
        self._set_run_all_enabled(True)

    # ---- Stage 1: CAD resample (batch: no output dialog) --------------- #
    def _pipe_resample(self, session):
        # A freshly-loaded (or pipeline-loaded) raw geometry may carry no edge
        # segments yet; auto-detect features so the resampler has something to
        # distribute (mirrors the interactive load path).
        pm = session.project_model
        has_file_seg = any(s.type == "file" for s in pm.segments)
        if (not has_file_seg and session.original_points is not None
                and len(session.original_points) >= 2):
            pts = session.original_points.copy()
            if pm.is_closed and not np.allclose(pts[0], pts[-1]):
                pts = np.vstack((pts, pts[0]))
            session.split_indices = self._auto_detect_features(pts)
            self._sync_file_segments(session)
            self.main_window.log_panel.log(
                f"[Pipeline] auto-detected {max(0, len(session.split_indices) - 1)} "
                "edge(s) for resampling.")

        # Write the resampled geometry to the generated-artifacts area
        # (results/resampled/), not next to the source geometry.
        stem = "output"
        if session.file_path:
            stem = os.path.splitext(os.path.basename(session.file_path))[0]
        elif session.display_name:
            stem = session.display_name.lstrip("*")
        out = os.path.join(repo_root(), "results", "resampled",
                           f"{stem}_resampled.dat")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        session.project_model.output_file = out

        self.main_window.mode_combo.setCurrentIndex(0)  # show CAD while resampling
        cfg_path, created = self._write_temp_config(session, out)
        self.main_window.log_panel.log("[Pipeline] Stage 1/3: resampling geometry...")
        self._run_backend(
            self._find_executable(), cfg_path, session,
            on_finish=lambda rc: self._pipe_after_resample(rc, out, created, session))

    def _pipe_after_resample(self, rc, out, created, session):
        for p in created:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        if rc != 0 or not os.path.exists(out):
            self._pipeline_abort(f"resample failed (code {rc}).")
            return
        try:
            if session in self.sessions:
                session.resampled_points = np.loadtxt(out)
        except Exception:
            pass

        abs_out = os.path.abspath(out)
        if abs_out not in self.global_mesh_config.geom_files:
            self.global_mesh_config.geom_files.append(abs_out)
        self.main_window.mesh_config_panel.set_config(self.global_mesh_config)
        self.sync_mesh_layers_panel()
        self.main_window.log_panel.log(f"[Pipeline] resampled -> {out}")
        self._pipe_mesh()

    # ---- Stage 2: mesh generation ------------------------------------- #
    def _pipe_mesh(self):
        self.main_window.mode_combo.setCurrentIndex(1)  # Mesh Generator view
        self.main_window.log_panel.log("[Pipeline] Stage 2/3: generating mesh...")
        # run_mesh_generator already forces STAR-CD export on the temp mesh, so
        # the solver's auto-link finds the .vrt/.cel/.bnd next to the temp VTK.
        self.run_mesh_generator()
        w = getattr(self, "_mesh_worker", None)
        if w is None or not w.isRunning():
            self._pipeline_abort("mesh generation did not start "
                                 "(check geometry / domain / binary).")
            return
        w.finished_signal.connect(self._pipe_after_mesh)

    def _pipe_after_mesh(self, rc):
        if rc != 0 or not (self.global_vtk_path and os.path.exists(self.global_vtk_path)):
            self._pipeline_abort(f"mesh generation failed (code {rc}).")
            return
        self._pipe_solver()

    # ---- Stage 3: solver ---------------------------------------------- #
    def _pipe_solver(self):
        self.main_window.log_panel.log("[Pipeline] Stage 3/3: running solver...")
        # Ensure the solver pulls the mesh we just generated.
        self.main_window.solver_config_panel.auto_link_mesh.setChecked(True)
        self.run_solver_pipeline()
        w = getattr(self, "_solver_worker", None)
        if w is None or not w.isRunning():
            self._pipeline_abort("solver did not start (check config / binaries).")
            return
        w.finished_signal.connect(self._pipe_after_solver)

    def _pipe_after_solver(self, rc):
        self._pipeline_running = False
        self._set_run_all_enabled(True)
        if rc != 0:
            self.main_window.log_panel.log(
                f"[Pipeline] solver stage failed (code {rc}).")
            return
        # _on_solver_finished already auto-loaded the result and switched to the
        # Results view; just apply the preferred contour variable if we have one.
        var = getattr(self, "_pipeline_result_var", "")
        if var:
            try:
                self.main_window.result_canvas_view.var_combo.setCurrentText(var)
            except Exception:
                pass
        self.main_window.log_panel.log(
            "=== Pipeline complete — result contour shown in the Results tab. ===")

    # ------------------------------------------------------------------ #
    # Save / load the unified pipeline JSON
    # ------------------------------------------------------------------ #
    def save_pipeline_file(self):
        session = self.active_session()
        if session is None:
            self.main_window.log_panel.log("[Pipeline] No active geometry to save.")
            return
        # Freshen the active analytic edge and transform from the sidebar so the
        # saved CAD section matches what is on screen.
        try:
            self._sync_active_curve_segment_from_ui()
            session.project_model.transform = \
                self.main_window.sidebar_view.get_transform_dict()
        except Exception:
            pass

        mesh_cfg = self.main_window.mesh_config_panel.get_config()
        solver_cfg = self.main_window.solver_config_panel.get_config()
        results = {}
        try:
            var = self.main_window.result_canvas_view.var_combo.currentText()
            if var:
                results["variable"] = var
        except Exception:
            pass

        name = os.path.splitext(session.display_name.lstrip("*"))[0] or "pipeline"
        pcfg = PipelineConfig.from_configs(
            name, session.project_model, mesh_cfg, solver_cfg, results)

        default = os.path.join(repo_root(), "config", "pipeline", f"{name}.json")
        path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Save Pipeline Script", default,
            "Pipeline JSON (*.json);;All Files (*)")
        if not path:
            return
        try:
            pcfg.save_to_file(path)
            self.main_window.log_panel.log(f"[Pipeline] Saved script to {path}")
        except Exception as e:
            self.main_window.log_panel.log(f"[Pipeline] Failed to save script: {e}")

    def load_pipeline_file(self):
        start = os.path.join(repo_root(), "config", "pipeline")
        if not os.path.isdir(start):
            start = repo_root()
        path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Load Pipeline Script", start,
            "Pipeline JSON (*.json);;All Files (*)")
        if not path:
            return
        try:
            ver = PipelineConfig.file_version(path)
            if ver > PIPELINE_FORMAT_VERSION:
                self.main_window.log_panel.log(
                    f"[Pipeline] [WARNING] script version {ver} newer than "
                    f"supported ({PIPELINE_FORMAT_VERSION}); loading best-effort.")
            pcfg = PipelineConfig.load_from_file(path)
        except Exception as e:
            self.main_window.log_panel.log(f"[Pipeline] Failed to load script: {e}")
            return
        self._apply_pipeline_config(pcfg, path)

    def _apply_pipeline_config(self, pcfg: PipelineConfig, path: str):
        # CAD: the cad section is a PreProcessor config — reuse the JSON loader.
        if pcfg.cad.get("input_file"):
            self._apply_json_config(dict(pcfg.cad), path)

        # Mesh: apply onto the shared mesh config + panel, wiring the CAD output
        # as the boundary if the section did not name its own geometry.
        if pcfg.mesh:
            self.global_mesh_config.load_from_dict(dict(pcfg.mesh))
            session = self.active_session()
            if not self.global_mesh_config.geom_files and session is not None:
                out = session.project_model.output_file
                if out:
                    self.global_mesh_config.geom_files = [os.path.abspath(out)]
            self.main_window.mesh_config_panel.set_config(self.global_mesh_config)
            self.sync_mesh_layers_panel()

        # Solver: apply preset first, then the explicit fields.
        if pcfg.solver:
            preset = pcfg.solver.get("preset")
            if preset:
                self.global_solver_config.apply_preset(preset)
            payload = {k: v for k, v in pcfg.solver.items()
                       if k not in ("preset", "skip")}
            self.global_solver_config.load_from_dict(payload)
            self.global_solver_config.ensure_default_binaries()
            self.main_window.solver_config_panel.set_config(self.global_solver_config)

        # Results: remember the preferred contour variable for after the solve.
        self._pipeline_result_var = pcfg.results.get("variable", "")
        self.main_window.log_panel.log(
            f"[Pipeline] Loaded script '{os.path.basename(path)}'. "
            "Click Run All to execute.")
