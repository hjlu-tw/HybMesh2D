"""Empty a case's ``work/`` before a run — as a LIST first, then as deletions.

``Overwrite in Place`` reuses a case directory and writes over its files as the
run produces them, so a case ends up a mixture of this run's output and whatever
the last one left. That mixture is a recurring defect class here rather than a
theoretical one: ``solver_case.report_stale_ibm_artifacts`` exists because a
leftover ``work/phi.dat`` is read by the init DLL and converges to a believable
answer for the PREVIOUS geometry's solid, and ``case_export_usage`` exists
because a reused case dir still holds the last IBM run's ``phi.dat`` and
``dll/`` (USER-REPORTED: "I didn't configure IBM, why is there a phi.dat?").

``Clean and Run`` (#33, DECIDED 2026-08-21) retires that class at the source. It
is a **separate answer**, never a redefinition of ``Overwrite in Place`` —
someone who picks Overwrite means "reuse this folder", and folding a deletion
into that button would break them.

Four rules, and every one of them is a decision recorded in #33 rather than a
detail:

* **Look before deleting, in a separate step from deleting.** :func:`plan_case_clean`
  MEASURES and :func:`apply_case_clean` acts on what it measured — it never
  re-reads the directory. This repo has the scar: an ``ls`` and an ``rm -rf`` in
  one command destroyed ~40 gitignored resampler artifacts. A plan is also the
  only way the prompt can name what is about to go.
* **Reuse the classification, do not glob.** ``case_files.is_run_output`` already
  decides what a run PRODUCES and ``case_files.WORK_STAGED`` /
  ``staged_bare_names`` what ``prepare_case_dir`` stages INTO the work dir. A
  file neither recognises is **kept and named**, exactly as ``case_archive``
  does — a clean slate is not a licence to remove what nobody classified.
* **The scope is the TOP LEVEL of ``work/``.** ``grid/`` and ``dll/`` are
  re-staged from the model on every run and ``grid/cad/`` holds copies of the
  user's own geometry, so neither is this function's business.
* **``work/prev_*/`` is NOT deleted by default.** It is the largest thing in a
  restarted case and also the only record of the earlier legs, which #32 exists
  to play back. It is measured into its own list so the prompt can offer it as a
  separate opt-in tick — a second deliberate act, not a consequence of pressing
  Clean and Run.

Qt-free, like the case services around it.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from app.services.case_files import (
    ARCHIVE_DIR_PREFIX,
    WORK_STAGED,
    human_size,
    is_inside,
    is_run_output,
    keep_matches,
    size,
    staged_bare_names,
    tree_size,
)


def _noop(_msg: str) -> None:
    """Default log sink."""


@dataclass(frozen=True)
class CleanEntry:
    """One thing the plan can delete: its work-dir-relative name, its absolute
    path and its size in bytes.

    The name is what the prompt shows and the path is what the deletion uses —
    both recorded at PLAN time, so the two cannot describe different files.
    """
    name: str
    path: str
    bytes: int


@dataclass(frozen=True)
class CleanPlan:
    """What a ``Clean and Run`` would remove from one work dir, and what it would
    leave. A measurement: building one changes nothing on disk."""

    work_dir: str
    outputs: tuple[CleanEntry, ...] = ()
    archives: tuple[CleanEntry, ...] = ()
    kept_inputs: tuple[str, ...] = ()
    unclassified: tuple[str, ...] = ()

    @property
    def outputs_bytes(self) -> int:
        return sum(e.bytes for e in self.outputs)

    @property
    def archives_bytes(self) -> int:
        return sum(e.bytes for e in self.archives)

    def is_empty(self) -> bool:
        """Whether there is nothing here to offer removing — no outputs AND no
        archives.

        Deliberately NOT parameterised by the archives tick. It had that
        parameter and one caller, which passed False and then re-checked
        ``and not plan.archives`` by hand — i.e. spelled out the answer the
        parameter was hiding. One question, one answer.
        """
        return not self.outputs and not self.archives

    def summary(self, include_archives: bool = False) -> str:
        """``"7 files, 5.1 MB"`` — the counts and total size about to go.

        The ONE rendering of that measurement: the prompt and the log line both
        read it here, so what the user approves and what the log records cannot
        disagree. They differed in the first version, and on the very thing the
        tick decides.
        """
        n = len(self.outputs) + (len(self.archives) if include_archives else 0)
        total = self.outputs_bytes + (self.archives_bytes if include_archives
                                      else 0)
        return f"{n} item{'' if n == 1 else 's'}, {human_size(total)}"

    def archive_names(self) -> str:
        """``"prev_001/, prev_002/"`` — the archived runs BY NAME.

        Point 3 of #33 asks the prompt to name "the folders by name", so this
        belongs in text the user sees without opening a details pane.
        """
        return ", ".join(e.name for e in self.archives)


@dataclass(frozen=True)
class ApprovedClean:
    """A plan the user approved, together with the one decision they made about
    it. ONE value, because the two travel together everywhere — through the
    controller, the worker's constructor and ``prepare_case_dir`` — and a pair
    lets a caller carry half an answer.

    It is also what keeps the confirmation's outcome out of a bool: the prompt
    has three endings (delete, delete-with-archives, cancel), and ``None`` for
    cancel against a value for the rest says that plainly, the way
    ``EditOutcome`` does for the edge-edit session.
    """

    plan: CleanPlan
    include_archives: bool = False


def plan_case_clean(work_dir: str, stale=()) -> CleanPlan:
    """Measure what a ``Clean and Run`` would remove from ``work_dir``.

    ``stale`` names basenames the CALLER has established are leftovers of an
    earlier run rather than inputs of this one — today exactly
    ``solver_case.stale_phi_name``'s answer. They are deleted even though the
    fixed-name allow-list recognises them, because #33 exists to retire that
    file: its problem statement is the stale ``work/phi.dat`` the init DLL reads
    by a fixed name, and point 3 lists ``phi.dat`` among what the prompt should
    offer to remove.

    Why the caller decides and not this module: whether a staged input is a
    leftover or the run's own only copy is a question about the CONFIG (a phi
    path resolving to ``work/phi.dat`` itself has no second copy), and this
    module deliberately knows nothing about ``SolverConfig``. Keeping the
    default empty also keeps the safe direction the default — a name nobody
    declared stale is kept.

    Nothing is deleted, opened or created here. The loop is deliberately the
    same shape as ``case_archive.archive_previous_outputs``' — one pass over the
    top level, each entry put into exactly one bucket by the shared
    classification — because the two answer the same question about the same
    directory and a second, differently-shaped reading of it is how the two
    would come to disagree about what a run produced.

    A directory that is not an archive is **unclassified**, not skipped: an
    ``isfile`` guard that silently passes over a folder is how one becomes
    invisible, which is the bug ``case_export.plan_export`` had.
    """
    work_dir = os.path.abspath(work_dir)
    if not os.path.isdir(work_dir):
        return CleanPlan(work_dir=work_dir)

    outputs, archives, kept, unknown = [], [], [], []
    # What THIS work dir's own input.in quotes as a file sitting in it — the
    # user-named tables of #29, which no list can hold.
    staged = staged_bare_names(work_dir)

    for name in sorted(os.listdir(work_dir)):
        path = os.path.join(work_dir, name)
        if os.path.isdir(path):
            if name.startswith(ARCHIVE_DIR_PREFIX):
                archives.append(CleanEntry(name + "/", path, tree_size(path)))
            else:
                unknown.append(name + "/")
            continue
        if not os.path.isfile(path):
            # A broken symlink or a socket: not ours to classify, so not ours to
            # remove either.
            unknown.append(name)
        elif is_run_output(name) or name in stale:
            outputs.append(CleanEntry(name, path, size(path)))
        elif keep_matches(name, WORK_STAGED) or name in staged:
            kept.append(name)
        else:
            unknown.append(name)

    return CleanPlan(work_dir=work_dir, outputs=tuple(outputs),
                     archives=tuple(archives), kept_inputs=tuple(kept),
                     unclassified=tuple(unknown))


def apply_case_clean(approved: ApprovedClean, work_dir: str,
                     log=_noop) -> int:
    """Delete what the approved plan measured. Returns how many entries went.

    ``work_dir`` is passed again ON PURPOSE and the plan is refused when it does
    not match. A plan is built on the GUI thread, against the directory the
    prompt named, and applied later on the worker thread, after
    ``resolve_case_root`` has had its say — so "the directory this plan is about"
    and "the directory this run is using" are two facts, and a run that ended up
    somewhere else must not delete files in the folder the user was shown.

    Every path is re-checked to be INSIDE that work dir before it is unlinked.
    The plan is data that travelled between threads; a deletion is not the place
    to assume it arrived describing what it described when it was built.

    Failures are reported and do not abort the rest: a file the user has open
    elsewhere should cost its own line, not the whole clean.
    """
    plan, include_archives = approved.plan, approved.include_archives
    if os.path.abspath(plan.work_dir) != os.path.abspath(work_dir):
        log("[WARNING] the clean-and-run list was measured for "
            f"'{plan.work_dir}' but this run uses '{os.path.abspath(work_dir)}' "
            "— nothing was deleted.")
        return 0

    for name in plan.unclassified:
        log(f"[case] work/{name} is not a recognised solver input or output — "
            "kept, not deleted.")

    targets = list(plan.outputs)
    if include_archives:
        targets += list(plan.archives)
    elif plan.archives:
        log(f"[case] {len(plan.archives)} archived previous run(s) kept "
            f"({human_size(plan.archives_bytes)}); tick 'also delete archived "
            "previous runs' to remove them.")

    removed = 0
    for entry in targets:
        if not is_inside(entry.path, work_dir):
            log(f"[WARNING] '{entry.name}' is not inside this case's work dir "
                "— not deleted.")
            continue
        try:
            if os.path.isdir(entry.path):
                shutil.rmtree(entry.path)
            elif os.path.exists(entry.path):
                os.remove(entry.path)
            else:
                # Gone between the plan and now. Nothing to do and nothing
                # wrong: the outcome the caller asked for already holds.
                continue
        except OSError as exc:
            log(f"[WARNING] could not delete work/{entry.name}: {exc}")
            continue
        removed += 1

    if removed:
        total = sum(e.bytes for e in targets)
        log(f"[case] cleaned work/: removed {removed} item"
            f"{'' if removed == 1 else 's'} ({human_size(total)}).")
    return removed
