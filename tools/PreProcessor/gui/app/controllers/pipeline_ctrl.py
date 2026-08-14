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
from PyQt6.QtWidgets import QFileDialog

from app.models.pipeline_config import PipelineConfig, PIPELINE_FORMAT_VERSION
from app.services import meta_io
from app.utils import repo_root

from app.services.logging_setup import get_logger

_log = get_logger(__name__)


class PipelineControllerMixin:

    # ------------------------------------------------------------------ #
    # Run All
    # ------------------------------------------------------------------ #
    def run_full_pipeline(self):
        """Chain resample -> mesh -> solver -> results for the active geometry.

        The CAD/resample stage is skipped when there is no active CAD geometry to
        resample but the mesh config already points at existing geometry files
        (e.g. a pipeline script whose CAD section had no source file, or a mesh
        built straight from .dat files) — mirroring the headless runner's
        ``cad_skip()``. The pipeline then starts at meshing those files.
        """
        if getattr(self, "_pipeline_running", False):
            self.main_window.log_panel.log("Pipeline is already running. Please wait.")
            return
        log = self.main_window.log_panel.log

        session = self.active_session()
        has_cad = session is not None and (
            session.original_points is not None or session.project_model.segments)
        mesh_files_ready = any(
            os.path.exists(gf) for gf in self.global_mesh_config.geom_files)
        if not has_cad and not mesh_files_ready:
            log("[Pipeline] No active geometry. Load or draw a geometry first "
                "(or add a geometry file in the Mesh Generator).")
            return
        if has_cad and not self._find_executable():
            log("[Pipeline] surface_resampler not found — run ./build.sh.")
            return

        self._pipeline_running = True
        self._set_run_all_enabled(False)
        # The result variable to show at the end is set by a loaded pipeline
        # script (_apply_pipeline_config); it stays "" otherwise, and
        # _pipe_after_solver leaves the canvas on its default variable.
        log("=== Run Full Pipeline: CAD -> Mesh -> Solver -> Results ===")
        # Resample EVERY session that has geometry, in tab order, then mesh them
        # together. Running only the active tab meant the other geometries of a
        # multi-body case were meshed from whatever stale .dat happened to be on
        # disk (or not at all).
        self._pipe_cad_queue = [
            s for s in self.sessions
            if s.original_points is not None or s.project_model.segments]
        if self._pipe_cad_queue:
            n = len(self._pipe_cad_queue)
            if n > 1:
                log(f"[Pipeline] Stage 1/3: resampling {n} geometries in tab order.")
            self._pipe_resample_next()
        else:
            log("[Pipeline] Stage 1/3: CAD resample skipped "
                "(no source geometry; meshing existing geometry files).")
            self._pipe_mesh()

    def _pipe_resample_next(self):
        """Resample the next queued session, or move on to meshing when done."""
        queue = getattr(self, "_pipe_cad_queue", None) or []
        if not queue:
            self._pipe_mesh()
            return
        self._pipe_resample(queue.pop(0))

    def _set_run_all_enabled(self, enabled: bool):
        btn = getattr(self.main_window, "run_all_btn", None)
        if btn is not None:
            btn.setEnabled(enabled)

    def _pipeline_abort(self, msg: str):
        self.main_window.log_panel.log(f"[Pipeline] Aborted: {msg}")
        self._pipeline_running = False
        # Drop any geometries still queued for resampling, so a later stray
        # continuation cannot resume half of an aborted run.
        self._pipe_cad_queue = []
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
        # Same as the interactive Save: the resampler rewrites <out>.meta from the
        # CAD config, so the Mesh-stage per-segment edits (BC label, No BL) have to
        # be carried across or Run All meshes with every patch on the wall default.
        # `out` is derived from THIS session, so the snapshot is its own geometry.
        snap = meta_io.snapshot_seg_edits(out) if os.path.exists(out) else None

        self.main_window.mode_combo.setCurrentIndex(0)  # show CAD while resampling
        cfg_path, created = self._write_temp_config(session, out)
        self.main_window.log_panel.log("[Pipeline] Stage 1/3: resampling geometry...")
        self._run_backend(
            self._find_executable(), cfg_path, session,
            on_finish=lambda rc: self._pipe_after_resample(rc, out, created,
                                                           session, snap))

    def _pipe_after_resample(self, rc, out, created, session, seg_edits=None):
        for p in created:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        if rc != 0 or not os.path.exists(out):
            self._pipeline_abort(f"resample failed (code {rc}).")
            return
        for line in meta_io.describe_seg_edit_restore(
                meta_io.restore_seg_edits(out, seg_edits),
                (seg_edits or {}).get("group_bc")):
            self.main_window.log_panel.log(f"[Pipeline] {line}")
        try:
            if session in self.sessions:
                from app.services.geometry_service import load_points_dat
                session.resampled_points = load_points_dat(out)
        except Exception as e:
            # Loading the resampled overlay is non-fatal (the file is on disk and
            # the pipeline continues to meshing), but log it so a malformed
            # resampler output is not silently indistinguishable from "did
            # nothing".
            self.main_window.log_panel.log(
                f"[Pipeline] [WARNING] could not load resampled preview: {e}")

        abs_out = os.path.abspath(out)
        if abs_out not in self.global_mesh_config.geom_files:
            self.global_mesh_config.geom_files.append(abs_out)
        self.push_panel_config(self.main_window.mesh_config_panel, self.global_mesh_config)
        self.sync_mesh_layers_panel()
        self.main_window.log_panel.log(f"[Pipeline] resampled -> {out}")
        # Continue down the CAD queue; _pipe_resample_next() meshes once empty.
        self._pipe_resample_next()

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
        # A reused worker object keeps its old connections; disconnect our slot
        # first so a second pipeline run doesn't fire _pipe_after_mesh twice.
        try:
            w.finished_signal.disconnect(self._pipe_after_mesh)
        except TypeError:
            pass  # not previously connected
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
        # A reused worker object keeps its old connections; disconnect our slot
        # first so a second pipeline run doesn't fire _pipe_after_solver twice.
        try:
            w.finished_signal.disconnect(self._pipe_after_solver)
        except TypeError:
            pass  # not previously connected
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
                _log.warning(
                    "could not select the preferred contour "
                    "variable", exc_info=True)
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
        except Exception as e:
            # Tell the user, not just the log file: the script they are about to
            # save may not match what is on their screen, and a silently-stale
            # script is exactly the kind of thing that wastes a whole re-run.
            _log.warning(
                "could not sync the on-screen CAD state into the pipeline "
                "script; the saved script may not match the canvas", exc_info=True)
            self.main_window.log_panel.log(
                "[Pipeline] [WARNING] could not read the latest on-screen CAD "
                f"edits ({e}); the saved script may not match the canvas.")

        mesh_cfg = self.main_window.mesh_config_panel.get_config()
        solver_cfg = self.main_window.solver_config_panel.get_config()
        results = {}
        try:
            var = self.main_window.result_canvas_view.var_combo.currentText()
            if var:
                results["variable"] = var
        except Exception:
            _log.warning(
                "could not read the current contour variable for the "
                "script", exc_info=True)

        name = os.path.splitext(session.display_name.lstrip("*"))[0] or "pipeline"
        # EVERY open session, in TAB order: a script built from only the active tab
        # silently dropped the rest of a multi-geometry case (airfoil + ground
        # plane, multi-element wing), and the dropped geometries were unrecoverable
        # from the script alone. Tab order (not active-first) because the mesher
        # keys per-geometry roles and BL overrides by path and names the mesh after
        # the first boundary — a stable order is what makes a re-run reproducible.
        ordered = list(self.sessions) or [session]
        pcfg = PipelineConfig.from_configs(
            name, [s.project_model for s in ordered], mesh_cfg, solver_cfg,
            results, stl3d_config=getattr(self, "global_stl3d_config", None))
        if len(ordered) > 1:
            self.main_window.log_panel.log(
                f"[Pipeline] script describes {len(ordered)} CAD geometries "
                f"(tab order: {', '.join(s.display_name.lstrip('*') for s in ordered)}).")

        # A drawn/in-memory geometry has no source file on disk, so its per-edge
        # segments can't be re-resampled from a reload. Flag it per entry: the
        # script still meshes the already-exported geometry files, but that CAD
        # entry is inert.
        for sess, cad in zip(ordered, pcfg.cads):
            if cad.get("segments") and not cad.get("input_file"):
                self.main_window.log_panel.log(
                    f"[Pipeline] [WARNING] '{sess.display_name.lstrip('*')}' has no "
                    "source .dat file; the saved script cannot re-run its CAD "
                    "resample. Meshing will use the exported geometry files. Run "
                    "'Save & Export' to persist a source.")

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
            self.main_window.log_panel.log(f"[Pipeline] [ERROR] Failed to save script: {e}")
            from app.utils import report_error
            report_error(self.main_window, "Save Pipeline Script Failed",
                         "The pipeline script could not be saved to disk.",
                         detail=str(e))

    def load_pipeline_file(self):
        start = os.path.join(repo_root(), "config", "pipeline")
        if not os.path.isdir(start):
            start = repo_root()
        path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Load Pipeline Script", start,
            "Pipeline script or workspace (*.json *.hws);;All Files (*)")
        if not path:
            return
        self.open_pipeline_path(path)

    def open_pipeline_path(self, path: str) -> bool:
        """Load a pipeline script — or a ``.hws`` workspace — from a known path.

        A workspace is routed to the WORKSPACE loader rather than through
        ``PipelineConfig.from_workspace_dict``: that conversion exists so the
        headless runner can *run* a ``.hws``, and it deliberately drops working
        state (cached resampled points, the generated mesh/result paths, the
        active tab). Inside the GUI the full loader is available and strictly
        better, so opening a workspace here must not silently downgrade it.
        """
        if PipelineConfig.classify_file(path) == "workspace":
            self.main_window.log_panel.log(
                f"[Pipeline] '{os.path.basename(path)}' is a HybMesh workspace — "
                "loading it as a workspace (full state), not as a script.")
            return self.open_workspace_path(path)
        try:
            # Missing version = legacy v0 (explicit). Older scripts are migrated
            # by PipelineConfig.from_dict; a NEWER one is read-only best-effort.
            ver = PipelineConfig.file_version(path)
            if ver > PIPELINE_FORMAT_VERSION:
                self.main_window.log_panel.log(
                    f"[Pipeline] [WARNING] script version {ver} is newer than "
                    f"supported ({PIPELINE_FORMAT_VERSION}); loading read-only, "
                    "best-effort — some settings may be ignored.")
            elif ver < PIPELINE_FORMAT_VERSION:
                self.main_window.log_panel.log(
                    f"[Pipeline] [INFO] migrating script from v{ver} to "
                    f"v{PIPELINE_FORMAT_VERSION}.")
            pcfg = PipelineConfig.load_from_file(path)
        except Exception as e:
            self.main_window.log_panel.log(f"[Pipeline] [ERROR] Failed to load script: {e}")
            from app.utils import report_warning
            report_warning(self.main_window, "Load Pipeline Script Failed",
                           "The pipeline script could not be loaded.",
                           detail=str(e))
            return False
        self._apply_pipeline_config(pcfg, path)
        return True

    def _apply_pipeline_config(self, pcfg: PipelineConfig, path: str):
        # A pipeline script fully defines the CAD/mesh/solver state, so start
        # from a clean slate: clear all open sessions, the mesh + solver config,
        # any generated mesh and loaded results. Otherwise a partial script would
        # silently inherit leftover settings from whatever was already open.
        self.reset_all_state()

        # CAD: each cads entry is a PreProcessor config — reuse the JSON loader,
        # which opens one session (tab) per entry.
        loaded = 0
        for i, cad in enumerate(pcfg.cads):
            if cad.get("input_file"):
                self._apply_json_config(dict(cad), path)
                loaded += 1
            elif cad.get("segments"):
                # Segments reference a source geometry by index, but none was
                # saved (the entry came from a drawn/in-memory geometry). Warn so
                # the missing tab isn't a surprise; Run All skips its resample and
                # meshes the configured geometry files directly.
                self.main_window.log_panel.log(
                    f"[Pipeline] [WARNING] CAD entry {i + 1} has no source "
                    "geometry file; its resample stage will be skipped and the "
                    "mesh will use its configured geometry files.")
        if loaded > 1:
            self.main_window.log_panel.log(
                f"[Pipeline] opened {loaded} CAD geometries from the script.")

        # Mesh: apply onto the shared mesh config + panel, wiring the CAD output
        # as the boundary if the section did not name its own geometry.
        if pcfg.mesh:
            self.global_mesh_config.load_from_dict(dict(pcfg.mesh))
            session = self.active_session()
            if not self.global_mesh_config.geom_files and session is not None:
                out = session.project_model.output_file
                if out:
                    self.global_mesh_config.geom_files = [os.path.abspath(out)]
            self.push_panel_config(self.main_window.mesh_config_panel, self.global_mesh_config)
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
            self.push_panel_config(self.main_window.solver_config_panel, self.global_solver_config)

        # Immersed solid (IB): apply the section to the panel so an IB case
        # described by a script is ready to run from the GUI.
        if pcfg.stl3d:
            self.global_stl3d_config = pcfg.build_stl3d_config()
            self.push_panel_config(self.main_window.stl3d_config_panel, self.global_stl3d_config)
            self.main_window.log_panel.log(
                "[Pipeline] applied the immersed-solid (IB) section; run the "
                "Immersed Solid stage to generate phi.")

        # Results: remember the preferred contour variable for after the solve.
        self._pipeline_result_var = pcfg.results.get("variable", "")
        # The freshly-loaded script IS the current state, so re-baseline: without
        # this, loading a script would leave the project looking unsaved and the
        # exit prompt would ask about changes the user never made.
        self._reset_project_baseline()
        self.main_window.log_panel.log(
            f"[Pipeline] Loaded script '{os.path.basename(path)}'. "
            "Click Run All to execute.")
