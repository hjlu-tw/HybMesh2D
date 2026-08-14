"""Project-level (non-CAD) state for AppController: the Mesh / Solver /
Immersed-Solid configuration that a workspace must carry, plus the dirty
detection that decides whether it needs saving.

Split out of session_ctrl/session_io_ctrl so each file stays inside the ~500-line
GUI budget, and because this is a distinct concern: session_io_ctrl owns the .hws
container and its versioning, this module owns what goes in the "project" section.
Methods run on the composed AppController instance.
"""
from __future__ import annotations
import os


class ProjectStateControllerMixin:
    # ── Project-level (non-CAD) state ────────────────────────────────────
    def _collect_project_state(self) -> dict:
        """Serialize the Mesh / Solver / Immersed-Solid configuration.

        Refresh each model from its panel first, then serialize the MODELS. This used
        to serialize ``panel.get_config()`` directly, because the models were only
        refreshed when a stage actually ran and a user who configured a case and saved
        without running would have checkpointed stale defaults.

        That workaround lost data of its own, and it was not hypothetical: a fresh
        ``get_config()`` leaves every field the panel does not author at its dataclass
        default, so saving a workspace turned ``bc_geom = symmetry`` back into ``wall``
        and (once units existed) a millimetre solver config back into metres — taking
        Linf's meaning with it. The panel is not a complete description of the model and
        never was.

        With the panel->model sync running on every edit (controllers/panel_sync_ctrl.py)
        the models are already current, so this is belt-and-braces rather than the thing
        keeping the save fresh.

        Unlike a pipeline script — which strips machine-specific derived paths to
        stay portable — a workspace is local working state, so staged case paths
        and binary locations are kept: reopening it should put the engineer back
        exactly where they left off.
        """
        out: dict = {}
        if hasattr(self, "sync_panels_to_models"):
            self.sync_panels_to_models()

        def grab(global_attr: str, key: str):
            cfg = getattr(self, global_attr, None)
            if cfg is not None and hasattr(cfg, "to_dict"):
                out[key] = cfg.to_dict()

        grab("global_mesh_config", "mesh_config")
        grab("global_solver_config", "solver_config")
        grab("global_stl3d_config", "stl3d_config")

        # Generated artefacts, so a reopened workspace can re-display them.
        out["vtk_path"] = getattr(self, "global_vtk_path", "") or ""
        out["result_path"] = getattr(self, "global_result_path", "") or ""
        return out

    def _reset_project_baseline(self):
        """Record the current project state as "saved", clearing dirtiness.

        Called at startup and after every successful workspace save/load. Taking
        the snapshot *from the panels* (via :meth:`_collect_project_state`) right
        after a load is what keeps the comparison honest: if a spin box clamps a
        saved value on the way in, the baseline records the clamped value the user
        can actually see, instead of leaving the project permanently "dirty"
        against a number the UI cannot represent.
        """
        try:
            self._project_baseline = self._collect_project_state()
        except Exception:
            # Never let baseline bookkeeping break a save/load; an unset baseline
            # only means project_is_dirty() stays conservative (see below).
            self._project_baseline = None

    def project_is_dirty(self) -> bool:
        """True if the Mesh / Solver / IB configuration differs from the baseline.

        Compared against a snapshot rather than tracked with a signal because the
        solver panel has no ``config_changed`` signal, and because
        ``valueChanged`` fires on programmatic ``set_config()`` too — a
        signal-driven flag would report dirt every time a panel was merely
        repopulated. A structural comparison has no such false positives.
        """
        baseline = getattr(self, "_project_baseline", None)
        if baseline is None:
            return False      # baseline unknown: don't nag about unsaved changes
        try:
            return self._collect_project_state() != baseline
        except Exception:
            return False

    def has_unsaved_work(self) -> bool:
        """True if replacing the whole project would discard something authored.

        The GUI always opens with one pristine blank session, so "this will close
        all current tabs — proceed?" fired even for `main.py case.hws`: a modal in
        front of an empty canvas, before the user has done anything. A session
        counts as authored once it has a source file, points or an edge.
        """
        for s in getattr(self, "sessions", []) or []:
            pm = getattr(s, "project_model", None)
            if (getattr(s, "file_path", "")
                    or getattr(s, "original_points", None) is not None
                    or (pm is not None and pm.segments)):
                return True
        return bool(self.project_is_dirty())

    def _apply_project_state(self, project: dict):
        """Restore the Mesh / Solver / IB configuration written by
        :meth:`_collect_project_state`, and push it to the panels.

        Absent for a pre-v2 workspace, in which case every panel keeps the
        defaults that were just reset — the old behaviour, but now explicit."""
        from app.models.stl3d_config import Stl3dConfig

        if not project:
            return
        mw = self.main_window

        mconf = project.get("mesh_config")
        if isinstance(mconf, dict):
            self.global_mesh_config.load_from_dict(mconf)
            self.push_panel_config(mw.mesh_config_panel, self.global_mesh_config)

        sconf = project.get("solver_config")
        if isinstance(sconf, dict):
            self.global_solver_config.load_from_dict(sconf)
            # Re-resolve the prebuilt binaries: the saved paths may come from
            # another checkout, and ensure_default_binaries only fills blanks.
            self.global_solver_config.ensure_default_binaries()
            self.push_panel_config(mw.solver_config_panel, self.global_solver_config)

        s3conf = project.get("stl3d_config")
        if isinstance(s3conf, dict):
            self.global_stl3d_config = Stl3dConfig.from_dict(s3conf)
            self.push_panel_config(mw.stl3d_config_panel, self.global_stl3d_config)

        # Only adopt artefact paths that still exist, so a moved/cleaned results
        # directory doesn't leave the Results panel pointing at nothing.
        for key, attr in (("vtk_path", "global_vtk_path"),
                          ("result_path", "global_result_path")):
            p = project.get(key, "") or ""
            if p and os.path.exists(p):
                setattr(self, attr, p)
            elif p:
                self.log(
                    f"[INFO] Saved {key} '{os.path.basename(p)}' no longer exists; "
                    "re-run the stage to regenerate it.")

