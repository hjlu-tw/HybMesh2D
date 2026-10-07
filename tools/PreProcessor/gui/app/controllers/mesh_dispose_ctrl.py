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

NOR DOES IT SPELL THE FALLBACK. A mesh produced on the hybrid FALLBACK path
(#167) is committable like any other — it carries its own provenance and its own
record — and it carries NO verdict, because a case type's thresholds were
measured on structured quads. Every sentence about that is
`services/mesh_fallback.py`'s and is quoted from there; what is decided here is
only that the run's own disposition reaches it.
"""
from __future__ import annotations

import os

from app.services import (case_sources, mesh_commit, mesh_fallback,
                          topology_model)
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
        self._settle_fallback(cfg)
        return trial if trial.matches(self._fingerprint_of(cfg)) else None

    def _say_fallback(self, fb) -> None:
        """The ONE line that says a mesh is not structured, at the ONE grade.

        Three call sites reach it — the run that accepts the downgrade, every
        later run under the same acceptance, and the commit — and all three say
        the same thing at the same grade, because it is one fact and the first
        of three copies to drift would be the one an operator happened to read.
        The SENTENCE is `mesh_fallback`'s; what is here is the component prefix
        and the grade, which is the caller's to own (`.claude/rules/gui-seams.md`).
        """
        self.log_report("[Mesh] " + fb.note(), level="WARNING")

    def _settle_fallback(self, cfg) -> None:
        """Drop an accepted hybrid fallback the configuration no longer needs.

        NON-INTERACTIVE, and that is the whole of it: the OFFER belongs to the
        pre-flight, which only a generation reaches, while Generate may commit a
        trial without running one.

        WHAT IT CLOSES, stated precisely because the first wording overclaimed
        and a review axis measured it: an acceptance no longer justified must
        not keep TRANSFORMING the configuration. `mesher_config` applies the
        downgrade off this flag, so a stale one would hand the mesher a
        family-less config for a drawing the operator has since fixed or moved
        to the hybrid path deliberately — changing the next run, not merely the
        bookkeeping. Asking `preflight_for_config` is the same question the
        pre-flight asks, minus the dialog: no refusal, no fallback.

        WHAT IT DOES NOT CLOSE, and must not: a TRIAL already generated as a
        fallback keeps `TrialMesh.fallback`, so committing it still writes the
        record. That is correct rather than stale — the mesh in hand really was
        produced on the hybrid path and really is not structured, and clearing
        the flag here would be the lie pointed the other way.
        """
        if self._mesh_fallback is None:
            return
        if not topology_model.preflight_for_config(cfg):
            self._mesh_fallback = None

    def _fingerprint_of(self, cfg) -> str:
        """`cfg` as the mesher would read it, plus its inputs, as one digest.

        Through `mesher_config` and the model's own writer, which is what the RUN
        does — not through `cfg` as the panel holds it. The two are not the same
        document: the run forces both export formats on and retargets the output
        into the temp dir, so fingerprinting the panel's copy differed by
        `EXPORT_VTK` alone, no trial ever read as current, and Generate re-meshed
        every time while the branch above said it had not. #166's review found it;
        `test_mesh_trial_commit.py` check 12 is what would have.
        """
        probe = os.path.join(self.temp_dir, "fingerprint_para.dat")
        try:
            self.mesher_config(cfg).save_to_file(probe)
            with open(probe, "r", encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, ValueError) as exc:
            # A fingerprint that cannot be taken must read as "not current", and
            # the empty string is what `TrialMesh.matches` refuses. Generate
            # then re-meshes, which is the safe direction.
            # `ValueError` joined `OSError` with #167: `save_to_file` PROJECTS a
            # named family's document, which raises `BindingError` (a
            # `ValueError`) for a binding the geometry no longer resolves — and
            # a trial in hand while the configuration has become unbuildable is
            # a state a fallback makes reachable. Both answers are the same one:
            # we could not check, so the trial is stale.
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
        pipeline = self._commit_pipeline(trial)
        try:
            written = mesh_commit.commit(trial, dest, pipeline=pipeline)
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
        # The case's mesh is now the one in hand, so every later action that
        # reads "the last generated mesh" — Export, Send to Solver — reaches the
        # file Generate approved rather than the scratch copy it was made from.
        self.global_vtk_path = dest
        root = repo_root()
        self.log("[Mesh] committed into the case:\n"
                 + "\n".join("  " + os.path.relpath(p, root) for p in written))
        if pipeline is None:
            # SAID. "Generate leaves a runnable pipeline script" is an acceptance
            # criterion, and the commonest way to leave none is not an exception
            # but an empty GUI — no CAD session to describe, which a `MESH_MODE 1`
            # case declaring its own corners legitimately is.
            self.log("[Mesh] [WARNING] no pipeline script was left beside this "
                     "mesh: there is no CAD session to describe. Load or draw "
                     "the geometry and press Generate again to get one.")
        if trial.fallback is not None:
            # SAID AT THE COMMIT TOO, not only at the generation. This is the
            # moment the mesh becomes the case's, and a committed case whose
            # mesh is not structured is the one fact its owner must not have to
            # reconstruct from a sidecar they did not know to open.
            self._say_fallback(trial.fallback)
        elif trial.verdict is None:
            # SAID, not left to be noticed. A case with no verdict file was
            # judged by nobody, and the operator should learn that here rather
            # than from an absent file six months later.
            self.log("[Mesh] [WARNING] no case type is in play, so this case "
                     "carries no verdict and no embedded case type.")

    def _commit_pipeline(self, trial):
        """The pipeline script to leave beside `trial`'s mesh, or ``None``.

        Built by the same verb the Pipeline menu's Save uses, so the script a
        committed case carries and the one a user saves by hand are the same
        document — and a failure to build one costs the operator the script,
        never the mesh they just approved.

        THE SCRIPT DESCRIBES THE RUN THAT HAPPENED, not the panel. For a
        fallback mesh that means the HYBRID configuration the mesher was handed
        (#167): a script carrying the panel's `MESH_MODE 1` would be refused by
        the family the moment anyone ran it, so the committed case would hold a
        mesh beside a script that cannot reproduce it. The override is handed to
        the one builder rather than applied after it, because a second
        `PipelineConfig` assembled here is exactly what that rule forbids.

        ``None`` has two causes and the CALLER says so for both: an exception,
        and the builder's own answer when there is no active CAD session to
        describe. The second is not an error — a `MESH_MODE 1` case whose
        topology declares its own corners legitimately has no CAD at all — but a
        committed case silently missing its script is the acceptance criterion
        going quiet, which is what #166's Spec review found.
        """
        mesh_cfg = (mesh_fallback.as_hybrid(self.global_mesh_config)
                    if trial.fallback is not None else None)
        try:
            return self.build_pipeline_config(mesh_cfg=mesh_cfg)
        except Exception as exc:        # noqa: BLE001 - reported, not discarded
            _log.warning("could not build the pipeline script for the "
                         "committed case", exc_info=True)
            self.log("[Mesh] [WARNING] the mesh was committed, but no runnable "
                     f"pipeline script could be built for it ({exc}).")
            return None
