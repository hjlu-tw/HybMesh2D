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

        Read from the *panels*, not from ``global_mesh_config`` and friends: the
        globals are only refreshed when a stage actually runs (Generate Mesh,
        Run Solver, ...), so a user who configures a case and saves without
        running would otherwise checkpoint stale defaults. The global is the
        fallback for a panel that cannot be read (partially-built UI).

        Unlike a pipeline script — which strips machine-specific derived paths to
        stay portable — a workspace is local working state, so staged case paths
        and binary locations are kept: reopening it should put the engineer back
        exactly where they left off.
        """
        mw = self.main_window
        out: dict = {}

        def grab(panel_attr: str, global_attr: str, key: str):
            panel = getattr(mw, panel_attr, None)
            cfg = None
            if panel is not None and hasattr(panel, "get_config"):
                try:
                    cfg = panel.get_config()
                except Exception as e:
                    self.main_window.log_panel.log(
                        f"[WARNING] Could not read the {key} panel state; saving "
                        f"the last applied configuration instead ({e}).")
            if cfg is None:
                cfg = getattr(self, global_attr, None)
            if cfg is not None and hasattr(cfg, "to_dict"):
                out[key] = cfg.to_dict()

        grab("mesh_config_panel", "global_mesh_config", "mesh_config")
        grab("solver_config_panel", "global_solver_config", "solver_config")
        grab("stl3d_config_panel", "global_stl3d_config", "stl3d_config")

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
                self.main_window.log_panel.log(
                    f"[INFO] Saved {key} '{os.path.basename(p)}' no longer exists; "
                    "re-run the stage to regenerate it.")

