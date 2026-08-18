"""Full-pipeline orchestration for the GUI: one action runs CAD resample ->
immersed solid -> mesh generation -> solver -> results contour, by chaining the
existing per-stage workers on their finished signals.

Each stage already runs in its own QThread with a ``finished_signal``; this
mixin sequences them without blocking the UI and suppresses the per-stage
dialogs (output path, unclosed prompt) so a single click runs to the contour.

Save/load of the unified pipeline JSON lives in ``pipeline_io_ctrl.py``.
"""
from __future__ import annotations
import os

import numpy as np

from app.services import ib_handoff
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
            self.log("Pipeline is already running. Please wait.")
            return
        log = self.log

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
        log("=== Run Full Pipeline: CAD -> [immersed solid] -> Mesh -> Solver -> Results ===")
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
            self._pipe_stl3d()

    def _pipe_resample_next(self):
        """Resample the next queued session, or move on to meshing when done."""
        queue = getattr(self, "_pipe_cad_queue", None) or []
        if not queue:
            self._pipe_stl3d()
            return
        self._pipe_resample(queue.pop(0))

    def _set_run_all_enabled(self, enabled: bool):
        btn = getattr(self.main_window, "run_all_btn", None)
        if btn is not None:
            btn.setEnabled(enabled)

    def _pipeline_abort(self, msg: str):
        self.log(f"[Pipeline] Aborted: {msg}")
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
            self.log(
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
        self.log("[Pipeline] Stage 1/3: resampling geometry...")
        self._run_backend(
            self._find_executable(), cfg_path, session,
            on_finish=lambda rc: self._pipe_after_resample(rc, out, created,
                                                           session))

    def _pipe_after_resample(self, rc, out, created, session):
        # No per-segment snapshot/restore around the resampler: the BC label and
        # the No-BL flag are SegmentModel fields, so _write_temp_config carried
        # them into the resampler's config and the sidecar came back correct.
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
                from app.services.geometry_service import load_points_dat
                session.resampled_points = load_points_dat(out)
        except Exception as e:
            # Loading the resampled overlay is non-fatal (the file is on disk and
            # the pipeline continues to meshing), but log it so a malformed
            # resampler output is not silently indistinguishable from "did
            # nothing".
            self.log(
                f"[Pipeline] [WARNING] could not load resampled preview: {e}")

        abs_out = os.path.abspath(out)
        if abs_out not in self.global_mesh_config.geom_files:
            self.global_mesh_config.geom_files.append(abs_out)
        self.push_panel_config(self.main_window.mesh_config_panel, self.global_mesh_config)
        self.sync_mesh_layers_panel()
        self.log(f"[Pipeline] resampled -> {out}")
        # Continue down the CAD queue; _pipe_resample_next() meshes once empty.
        self._pipe_resample_next()

    def _pipe_chain(self, worker_attr: str, slot, not_started: str) -> bool:
        """Continue the pipeline when the named worker finishes. False = stop.

        Every stage needs the same three things and each wrote them out itself:
        refuse to go on if the worker never started (the stage has already logged
        why), drop a connection a PREVIOUS pipeline run left on a reused worker
        object — otherwise the continuation fires twice — and only then connect.
        """
        w = getattr(self, worker_attr, None)
        if w is None or not w.isRunning():
            self._pipeline_abort(not_started)
            return False
        try:
            w.finished_signal.disconnect(slot)
        except TypeError:
            pass  # not previously connected
        w.finished_signal.connect(slot)
        return True

    # ---- Immersed solid (optional): STL -> phi ------------------------- #
    def _pipe_stl3d(self):
        """Trace the phi field before meshing, then wire it into the solver.

        Run All had no IB stage at all, so a case with an immersed solid was
        meshed and solved against whatever ``work/phi.dat`` the case directory
        still held — the previous geometry's solid (see services/ib_handoff).
        Ordered where the headless runner orders it, IB before mesh, so a script
        and this button build the same case.

        Optional, and only ever skipped out loud: a case with no STL says so and
        moves straight on to meshing.
        """
        w0 = getattr(self, "_stl3d_worker", None)
        if w0 is not None and w0.isRunning():
            self._pipeline_abort("STL3d is already running; wait for it to finish.")
            return
        cfg = getattr(self, "global_stl3d_config", None)
        if cfg is None or not getattr(cfg, "stl_path", ""):
            self.log("[Pipeline] Immersed solid: skipped (no STL configured).")
            self._pipe_mesh()
            return

        self.log("[Pipeline] Immersed solid: tracing the phi field...")
        # run_stl3d() validates + stages through services/stl3d_case and logs its
        # own reason if it refuses, so a failure to start is reported twice: once
        # in the stage's vocabulary, once as the pipeline aborting.
        self.run_stl3d()
        if not self._pipe_chain("_stl3d_worker", self._pipe_after_stl3d,
                                "STL3d did not start (check the STL / binary)."):
            return

    def _pipe_after_stl3d(self, rc):
        if rc != 0:
            # _on_stl3d_finished has already said whether this was a cancel or a
            # failure; this line is the pipeline's own half.
            self._pipeline_abort(f"STL3d stage ended (code {rc}).")
            return
        sc = self.global_solver_config
        if not sc.immersed_solid:
            # The stage ran because an STL is configured. Whether the SOLVE has
            # an immersed body is the Solver stage's own declaration, and a
            # pipeline stage may not overrule it — so say what was traced, what
            # will ignore it, and which box turns it on.
            self.log(
                "[Pipeline] [WARNING] phi was traced but the Solver stage has "
                "Immersed Solid OFF, so the solve will not read it (tick "
                "Immersed Solid in the Solver stage to include it).")
            self._pipe_mesh()
            return
        try:
            ib_handoff.link_phi_to_solver(
                sc, getattr(self, "_stl3d_phi_path", ""),
                self.global_stl3d_config, repo_root(), log=self.log)
        except ib_handoff.IbHandoffError as e:
            self._pipeline_abort(f"immersed-solid hand-off: {e}")
            return
        # The panel is a view of the config the hand-off just changed, and this
        # is a programmatic push, not a user edit.
        # set_config -> _set_config_body already refreshes the IBM rows, so a
        # controller reaching for the panel's private helper adds nothing.
        self.push_panel_config(self.main_window.solver_config_panel, sc)
        self._pipe_mesh()

    # ---- Stage 2: mesh generation ------------------------------------- #
    def _pipe_mesh(self):
        self.main_window.mode_combo.setCurrentIndex(1)  # Mesh Generator view
        self.log("[Pipeline] Stage 2/3: generating mesh...")
        # run_mesh_generator already forces STAR-CD export on the temp mesh, so
        # the solver's auto-link finds the .vrt/.cel/.bnd next to the temp VTK.
        self.run_mesh_generator()
        if not self._pipe_chain("_mesh_worker", self._pipe_after_mesh,
                                "mesh generation did not start (check geometry / domain / binary)."):
            return

    def _pipe_after_mesh(self, rc):
        if rc != 0 or not (self.global_vtk_path and os.path.exists(self.global_vtk_path)):
            self._pipeline_abort(f"mesh generation failed (code {rc}).")
            return
        self._pipe_solver()

    # ---- Stage 3: solver ---------------------------------------------- #
    def _pipe_solver(self):
        self.log("[Pipeline] Stage 3/3: running solver...")
        # Ensure the solver pulls the mesh we just generated.
        self.main_window.solver_config_panel.auto_link_mesh.setChecked(True)
        self.run_solver_pipeline()
        if not self._pipe_chain("_solver_worker", self._pipe_after_solver,
                                "solver did not start (check config / binaries)."):
            return

    def _pipe_after_solver(self, rc):
        self._pipeline_running = False
        self._set_run_all_enabled(True)
        if rc != 0:
            self.log(
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
        self.log(
            "=== Pipeline complete — result contour shown in the Results tab. ===")
