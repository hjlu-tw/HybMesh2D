"""Which directory a solver run writes into, and what happens to what is
already there.

One question with four possible answers (``solver_case.CASE_*``), asked at most
once per run and never on an unattended path. It is its own module for the
reason ``views/case_dir_dialog`` is: the question grew a second step in #33 —
measure, show the list, then delete — and ``solver_ctrl`` is at the GUI
file-length budget. The split is along a concept, not just a line count: nothing
here knows how to run a solver, and everything here is about a directory.

The DIALOGS are ``views/case_dir_dialog``; the mechanics are
``services/solver_case.case_dir_flags`` and ``services/case_clean``. This mixin
is what decides whether to ask at all, and it owns the user-log line that says
what came back — which for the two answers that do not ask (a restart, and Run
All) is the only trace the decision leaves.
"""
from __future__ import annotations

from app.models.solver_config import SolverConfig
from app.services import restart_points, solver_case
from app.services.case_archive import archive_notice
from app.services.case_clean import plan_case_clean
from app.services.solver_case import sanitize_case_name as _sanitize
from app.views.case_dir_dialog import (
    ask_case_disposition,
    confirm_case_clean,
)


class CaseDispositionControllerMixin:
    """Resolve "this case name already has results" into one ``CASE_*`` answer.

    The approved clean (:class:`~app.services.case_clean.ApprovedClean`) is held
    here rather than returned beside the disposition, and read back through
    :meth:`pending_clean` — a verb, not an attribute another mixin reaches into.
    ``solver_ctrl`` used to fetch it with ``getattr(self, "_case_clean_plan",
    None)``, which is the cross-mixin private reach #43's story 45 asks to be
    rid of, and whose default would have made an uncomposed mixin degrade
    silently instead of failing.
    """

    def pending_clean(self):
        """The ``ApprovedClean`` this run may carry, or None.

        Public because the solver run has to hand it to its worker; a method
        rather than an attribute so the answer exists even before a disposition
        has been resolved.
        """
        return getattr(self, "_approved_clean", None)

    def _resolve_case_disposition(self, cfg: SolverConfig):
        """One of ``solver_case.CASE_*`` — which directory this run writes into
        and what happens to what is already there — or None if the user
        cancelled.

        Only asks when a case dir of this name already holds prior results AND
        this run is not a restart; otherwise the answer is decided here — a
        restart archives and continues in place (#31), and a fresh case uses its
        default dir as-is. The dialog itself is ``views/case_dir_dialog``; this
        decides whether to ask at all and says what came back.
        """
        # A plan is approved for ONE run. Clearing it here means a run that was
        # cancelled after the confirmation (or one that then answered
        # differently) cannot hand the worker a deletion list the user approved
        # for something else.
        self._approved_clean = None

        case = _sanitize(cfg.case_name)
        # One spelling of "where this case lives", shared with the panel that
        # lists its restart points and the validator that resolves a relative
        # reference against its work dir.
        case_root = restart_points.case_root_for(cfg.case_name)
        if not solver_case.dir_has_content(case_root):
            return solver_case.CASE_NEW_VERSION

        # Run All (pipeline batch) must run unattended: never pop a modal.
        # Preserve prior results by auto-versioning a new dir instead of blocking.
        # The worker reports the real (versioned) work dir via prepared_signal, so
        # the Results stage still finds the output.
        if getattr(self, "_pipeline_running", False):
            self.log(
                f"[case] '{case}' already has results; Run All auto-versions a new "
                "directory to preserve them.")
            return solver_case.CASE_NEW_VERSION

        # A RESTART is no longer an ambiguous question (#31): the start point was
        # chosen from this case's own history, so the prompt is dropped rather
        # than answered — see views/case_dir_dialog for why, and archive_notice
        # for what the log has to say in its place.
        if cfg.restart:
            self.log(archive_notice(case, case_root))
            return solver_case.CASE_ARCHIVE

        choice = ask_case_disposition(self.main_window, case, case_root)
        if choice is None:
            self.log("Solver run cancelled (case exists).")
        elif choice == solver_case.CASE_IN_PLACE:
            self.log(f"[case] overwriting existing results for '{case}'.")
        elif choice == solver_case.CASE_CLEAN:
            return self._resolve_case_clean(cfg, case, case_root)
        return choice

    def _resolve_case_clean(self, cfg: SolverConfig, case: str,
                            case_root: str):
        """The second half of a ``Clean and Run``: measure, show the list, and
        come back with a disposition — or None if the user backed out.

        MEASURE THEN ASK THEN DELETE, in three separate steps, and the deletion
        is not one of them: the approved plan is handed to the worker and applied
        by ``prepare_case_dir`` before it stages anything. This repo has the scar
        that argues for the separation — an ``ls`` and an ``rm -rf`` in one
        command destroyed ~40 gitignored resampler artifacts — and the split also
        keeps the (possibly large) deletion off the GUI thread.

        An empty work dir degrades to ``CASE_IN_PLACE`` rather than showing a
        prompt listing nothing: with nothing to delete the two answers are the
        same run, and a modal that asks about no files is a click the user cannot
        act on.
        """
        work_dir = solver_case.work_dir_of(case_root)
        # A phase field this run will not write is the PREVIOUS geometry's solid
        # — #33's problem statement, and the one staged input a clean has to be
        # able to remove. Asked of the module that owns the question, so the
        # warning and the deletion cannot disagree about which files are stale.
        stale = [n for n in (solver_case.stale_phi_name(cfg, work_dir),) if n]
        plan = plan_case_clean(work_dir, stale=stale)
        if plan.is_empty():
            self.log(f"[case] nothing to clean in '{case}' work dir; "
                     "reusing it as-is.")
            return solver_case.CASE_IN_PLACE

        approved = confirm_case_clean(self.main_window, case, plan)
        if approved is None:
            self.log("Solver run cancelled (clean not confirmed).")
            return None

        self._approved_clean = approved
        kept = ("" if approved.include_archives or not plan.archives else
                f", keeping {plan.archive_names()}")
        self.log(f"[case] cleaning '{case}' work dir before this run: "
                 f"{plan.summary(approved.include_archives)}{kept}.")
        return solver_case.CASE_CLEAN
