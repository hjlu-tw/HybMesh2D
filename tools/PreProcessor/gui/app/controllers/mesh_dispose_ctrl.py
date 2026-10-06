"""What happens to the mesh a run just produced: Trial, or Generate (#166).

The two Mesh-tab actions ride ONE generation. `mesh_gen_ctrl` launches the
mesher and loads what came back; this mixin decides what becomes of it.

* **Trial** generates and judges, and commits nothing. It is the generation with
  no disposition at all, so the operator can run it as often as they like — it
  costs about a second — and what sits in the case stays whatever Generate last
  approved.
* **Generate** commits the mesh Trial produced: into the case under its own
  name, with the whole case type that judged it, the frozen verdict and a
  runnable pipeline script beside it. **It does not recompute.** If a current
  trial is in hand it is copied; otherwise one generation runs and THAT is what
  is committed. Nothing re-meshes between the verdict and the files on disk.

Both are distinct from **Run All**, which is the whole chain through the solver,
and from **Preview** / "BC Preview", which draws the far-field box and the
boundaries on the canvas and meshes nothing. The new action is named Trial for
exactly that reason.

ITS OWN FILE, like `mesh_gen_diag_ctrl` next door (#159): running the mesher is
one concern and disposing of its output is another, and `mesh_gen_ctrl` is near
the ~500-line GUI file-length standard. Nothing here starts a worker and nothing
here reads a mesh.

NOTHING HERE SPELLS A VERDICT. Whether a verdict refuses the write is
`case_type_verdict.commit_refusal`'s answer, raised by `services/mesh_commit` as
`CommitRefused` and shown here verbatim — `.claude/rules/gui-handoff.md` holds
the hosts to spelling no state, no comparison and no grade of their own, and a
disposition is a host like any other.
"""
from __future__ import annotations

import os

from app.services import case_sources, mesh_commit
from app.services.geom_path_identity import keyed_geom_paths
from app.services.logging_setup import get_logger
from app.services.paths import repo_root
from app.utils import report_error

_log = get_logger(__name__)


class MeshDispositionMixin:
    """Trial and Generate, over the generation `mesh_gen_ctrl` performs."""

    def trial_mesh(self):
        """Generate a mesh to look at, and commit nothing."""
        self.log("--- Trial mesh: nothing will be written into the case ---")
        self.run_mesh_generator(commit=False)

    def generate_mesh(self):
        """Commit the trial mesh into the case, generating one first if needed.

        THE ORDER IS THE POINT. A trial still current for this configuration is
        committed as it stands; only when there is none does a generation run,
        and the disposition then rides that run's own finish. Either way the
        mesh that is judged is the mesh that lands.
        """
        worker = getattr(self, "_mesh_worker", None)
        if worker is not None and worker.isRunning():
            # The guard `run_mesh_generator` already has, said BEFORE the trial
            # in hand is consulted: the run in flight is about to replace it,
            # and committing the previous one here would put the older mesh in
            # the case while the newer one is still being made.
            self.log("Mesh generation is already running. Please wait.")
            return
        trial = self._current_trial()
        if trial is not None:
            self.log("[Mesh] committing the trial mesh already in hand; "
                     "nothing is re-meshed.")
            self._commit_trial(trial)
            return
        self.run_mesh_generator(commit=True)

    # --- what a trial was made from ------------------------------------------
    def _mesh_input_paths(self, cfg) -> list:
        """The files whose CONTENT decides this mesh, beside the config itself.

        The geometry, through `keyed_geom_paths` so the entries' `KEY=VALUE`
        tokens and spellings are resolved the one way this repo resolves them,
        plus the block topology document in `MESH_MODE 1`, through the same
        `case_sources` call the case export stages it with. Two existing owners,
        no third rule here.
        """
        paths = [key for key, _spelling in keyed_geom_paths(cfg.geom_files)]
        paths += case_sources.mesh_input_paths(cfg, repo_root())
        return paths

    def _current_trial(self):
        """The trial mesh still valid for the config on screen, or ``None``.

        Three ways to be None, and each is a real state: no trial has been run,
        its mesh is gone (the session temp dir, or a failed run that produced
        none), or the configuration has moved since. The last is why the
        fingerprint exists at all — committing a mesh the current settings would
        no longer produce is the same lie as regenerating one.
        """
        trial = self._mesh_trial
        if trial is None or not trial.usable:
            return None
        cfg = self.config_from_panel("mesh_config_panel")
        return trial if trial.matches(self._fingerprint_of(cfg)) else None

    def _fingerprint_of(self, cfg) -> str:
        """`cfg` as the mesher would read it, plus its inputs, as one digest.

        Serialised through the model's own writer into the session temp dir —
        the same `save_to_file` the run itself uses — rather than through a
        second spelling of the `.dat` format that could agree with the mesher
        today and not tomorrow.
        """
        probe = os.path.join(self.temp_dir, "fingerprint_para.dat")
        try:
            cfg.save_to_file(probe)
            with open(probe, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            # A fingerprint that cannot be taken must read as "not current", and
            # the empty string is what `TrialMesh.matches` refuses. Generate
            # then re-meshes, which is the safe direction.
            _log.warning("could not serialise the mesh config to fingerprint "
                         "it; the trial will read as stale", exc_info=True)
            self.log("[Mesh] [WARNING] could not check whether the trial mesh "
                     f"is still current ({exc}); generating a fresh one.")
            return ""
        return mesh_commit.inputs_fingerprint(text, self._mesh_input_paths(cfg))

    # --- the commit ----------------------------------------------------------
    def _commit_trial(self, trial):
        """Write `trial` into the case, and say what landed where."""
        dest = self._get_expected_vtk_path(self.global_mesh_config)
        try:
            written = mesh_commit.commit(trial, dest,
                                         pipeline=self._commit_pipeline())
        except mesh_commit.CommitRefused as exc:
            # The service's own sentence, not a second wording of it: it names
            # the measurement, the bound and the case type's advice.
            # `log_report`'s own default grade — the refusal is a failure of the
            # action the operator asked for, and naming a grade here would be
            # this file deciding one, which is the thing it must not do.
            self.log_report(str(exc))
            report_error(self.main_window, "Mesh Not Committed", str(exc))
            return
        except OSError as exc:
            _log.warning("committing the mesh into the case failed",
                         exc_info=True)
            self.log(f"[Mesh] [ERROR] could not write the mesh into the case: {exc}")
            report_error(self.main_window, "Mesh Not Committed",
                         "The mesh could not be written into the case.",
                         detail=str(exc))
            return
        root = repo_root()
        self.log("[Mesh] committed into the case:\n"
                 + "\n".join("  " + os.path.relpath(p, root) for p in written))
        if trial.verdict is None:
            # SAID, not left to be noticed. A case with no verdict file was
            # judged by nobody, and the operator should learn that here rather
            # than from an absent file six months later.
            self.log("[Mesh] [WARNING] no case type is in play, so this case "
                     "carries no verdict and no embedded case type.")

    def _commit_pipeline(self):
        """The pipeline script to leave beside the mesh, or ``None``.

        Built by the same verb the Pipeline menu's Save uses, so the script a
        committed case carries and the one a user saves by hand are the same
        document — and a failure to build one costs the operator the script,
        never the mesh they just approved.
        """
        try:
            return self.build_pipeline_config()
        except Exception as exc:        # noqa: BLE001 - reported, not discarded
            _log.warning("could not build the pipeline script for the "
                         "committed case", exc_info=True)
            self.log("[Mesh] [WARNING] the mesh was committed, but no runnable "
                     f"pipeline script could be built for it ({exc}).")
            return None
