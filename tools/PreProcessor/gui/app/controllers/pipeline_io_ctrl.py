"""Save / load the unified pipeline JSON (and open a ``.hws`` as a script).

Split out of ``pipeline_ctrl.py``, which had grown past this project's GUI file
budget once Run All gained its immersed-solid stage. The cut is the one the old
file's own docstring already described: **running** the pipeline is one concern,
**reading and writing the script that describes it** is another, and they share
nothing but the config classes.
"""
from __future__ import annotations
import os

from PyQt6.QtWidgets import QFileDialog

from app.models.pipeline_config import PipelineConfig, PIPELINE_FORMAT_VERSION
from app.utils import repo_root

from app.services.logging_setup import get_logger

_log = get_logger(__name__)


class PipelineIoControllerMixin:
    """Read/write the pipeline script; apply a loaded one onto the GUI state."""

    def save_pipeline_file(self):
        session = self.active_session()
        if session is None:
            self.log("[Pipeline] No active geometry to save.")
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
            self.log(
                "[Pipeline] [WARNING] could not read the latest on-screen CAD "
                f"edits ({e}); the saved script may not match the canvas.")

        # The MODEL is the truth and the panel is a view of it (CLAUDE.md,
        # "Stage config data flow is one-directional"): panel_sync_ctrl runs on
        # every user edit, so these are never stale, and reading the widgets back
        # would be the one direction the data flow does not have. Note the stl3d
        # section below has always read its model.
        mesh_cfg = self.global_mesh_config
        solver_cfg = self.global_solver_config
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
            self.log(
                f"[Pipeline] script describes {len(ordered)} CAD geometries "
                f"(tab order: {', '.join(s.display_name.lstrip('*') for s in ordered)}).")

        # A drawn/in-memory geometry has no source file on disk, so its per-edge
        # segments can't be re-resampled from a reload. Flag it per entry: the
        # script still meshes the already-exported geometry files, but that CAD
        # entry is inert.
        for sess, cad in zip(ordered, pcfg.cads):
            if cad.get("segments") and not cad.get("input_file"):
                self.log(
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
            self.log(f"[Pipeline] Saved script to {path}")
        except Exception as e:
            self.log(f"[Pipeline] [ERROR] Failed to save script: {e}")
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
            self.log(
                f"[Pipeline] '{os.path.basename(path)}' is a HybMesh workspace — "
                "loading it as a workspace (full state), not as a script.")
            return self.open_workspace_path(path)
        try:
            # Missing version = legacy v0 (explicit). Older scripts are migrated
            # by PipelineConfig.from_dict; a NEWER one is read-only best-effort.
            ver = PipelineConfig.file_version(path)
            if ver > PIPELINE_FORMAT_VERSION:
                self.log(
                    f"[Pipeline] [WARNING] script version {ver} is newer than "
                    f"supported ({PIPELINE_FORMAT_VERSION}); loading read-only, "
                    "best-effort — some settings may be ignored.")
            elif ver < PIPELINE_FORMAT_VERSION:
                self.log(
                    f"[Pipeline] [INFO] migrating script from v{ver} to "
                    f"v{PIPELINE_FORMAT_VERSION}.")
            pcfg = PipelineConfig.load_from_file(path)
        except Exception as e:
            self.log(f"[Pipeline] [ERROR] Failed to load script: {e}")
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
                self.log(
                    f"[Pipeline] [WARNING] CAD entry {i + 1} has no source "
                    "geometry file; its resample stage will be skipped and the "
                    "mesh will use its configured geometry files.")
        if loaded > 1:
            self.log(
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
            self.global_stl3d_config = pcfg.build_stl3d_config(repo_root())
            self.push_panel_config(self.main_window.stl3d_config_panel, self.global_stl3d_config)
            self.log(
                "[Pipeline] applied the immersed-solid (IB) section; Run All "
                "traces phi before meshing (or run the Immersed Solid stage "
                "on its own).")

        # Results: remember the preferred contour variable for after the solve.
        self._pipeline_result_var = pcfg.results.get("variable", "")
        # The freshly-loaded script IS the current state, so re-baseline: without
        # this, loading a script would leave the project looking unsaved and the
        # exit prompt would ask about changes the user never made.
        self._reset_project_baseline()
        self.log(
            f"[Pipeline] Loaded script '{os.path.basename(path)}'. "
            "Click Run All to execute.")
