"""The prompt for "this case name already has results — now what?".

**A restart no longer reaches here** (#31, CONFIRMED 2026-08-21). #26 gave this
dialog a third answer for one: a restart continues a solution and therefore
belongs in the folder it is resuming, and the only option that stayed in that
folder used to be ``Overwrite`` — which wrote over the previous run's outputs as
the new run produced its own, the dump being resumed from included
(USER-REPORTED 2026-08-20). Now that the start point is picked from that case's
own history (``views/panels/restart_chooser``), "same directory, archive the
previous outputs" is the only coherent answer to a question the user has already
answered, so ``solver_ctrl._resolve_case_disposition`` decides it instead of
asking. The archive step is legible in the user log on its own, which is what
that confirmation used to provide; an explicit overwrite-in-place escape belongs
somewhere non-default (#33).

What is left is the genuinely ambiguous non-restart case: overwrite, or keep the
results and run in a new auto-versioned directory. ``CASE_ARCHIVE`` is therefore
not offered here — a branch nothing can reach reads as a working feature, so it
is gone rather than left as an answer the dialog can no longer give.

A view, not a decision: this asks and reports the answer. What the answer means
mechanically is ``solver_case.case_dir_flags``, and the logging is the
controller's, which owns the user log.
"""
from __future__ import annotations

from app.services.case_clean import ApprovedClean
from app.services.case_files import human_size
from app.services.solver_case import (
    CASE_ARCHIVE,
    CASE_CLEAN,
    CASE_IN_PLACE,
    CASE_NEW_VERSION,
)
from app.utils import confirm_destructive, is_headless


def ask_case_disposition(parent, case: str, case_root: str) -> str | None:
    """``CASE_IN_PLACE``, ``CASE_CLEAN`` or ``CASE_NEW_VERSION``, or None when
    the user cancelled. Never ``CASE_ARCHIVE`` — see the module docstring.

    ``CASE_CLEAN`` is a SEPARATE answer from ``CASE_IN_PLACE`` and not a
    redefinition of it (#33, DECIDED 2026-08-21): someone who picks Overwrite
    means "reuse this folder", so folding a deletion into that button would break
    them. It is also only half an answer here — the caller must then show the
    list (:func:`confirm_case_clean`) and may still come away with nothing.

    ``CASE_ARCHIVE`` is offered again, which #33 asks for as "the honest framing
    may be 'archive these, or delete these?'". #31 removed it from THIS prompt
    because a restart no longer reaches the prompt at all and the branch was
    then unreachable — but a non-restart run in an occupied directory is a
    different question, and for it "keep the previous outputs, in this folder"
    is a real answer that #26's machinery already implements. That takes the
    prompt to four answers plus Cancel, which #33 names as the ceiling: the next
    one to want a button is the point at which this stops being a message box.

    Headless returns ``CASE_NEW_VERSION`` without showing anything: prior results
    are preserved and nothing blocks, which is the same answer the unattended
    Run All path gives itself before ever reaching here.
    """
    if is_headless():
        return CASE_NEW_VERSION
    from PyQt6.QtWidgets import QMessageBox

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Case already exists")
    box.setText(f"Solver results for case '{case}' already exist at\n{case_root}")
    box.setInformativeText(
        "Reuse that directory and write over its files as the run produces "
        "them; empty it first (you will see what would be deleted); archive the "
        "previous run's output into work/prev_NNN/ and continue in the same "
        "directory; or keep it and run into a new auto-versioned directory "
        f"(e.g. '{case}_002')?")
    overwrite_btn = box.addButton("Overwrite in Place",
                                  QMessageBox.ButtonRole.DestructiveRole)
    clean_btn = box.addButton("Clean and Run…",
                              QMessageBox.ButtonRole.DestructiveRole)
    archive_btn = box.addButton("Archive Previous",
                                QMessageBox.ButtonRole.AcceptRole)
    new_btn = box.addButton("New Versioned Dir",
                            QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(new_btn)
    box.addButton(QMessageBox.StandardButton.Cancel)

    box.exec()
    clicked = box.clickedButton()
    if clicked is overwrite_btn:
        return CASE_IN_PLACE
    if clicked is clean_btn:
        return CASE_CLEAN
    if clicked is archive_btn:
        return CASE_ARCHIVE
    if clicked is new_btn:
        return CASE_NEW_VERSION
    # Cancel, or the window dismissed with its close button / Esc, where
    # clickedButton() can be None. Falling through to a disposition would START A
    # SOLVER RUN nobody asked for — the same "an unknown value must not resolve to
    # a plausible answer" rule solver_case.case_dir_flags enforces from the other
    # side. Every non-cancelling answer is matched explicitly above.
    return None


def confirm_case_clean(parent, case: str, plan) -> ApprovedClean | None:
    """Show what a ``Clean and Run`` would delete and ask. Returns the approved
    plan, or None when the user backed out.

    The second half of the case-dir question, so it lives beside the first —
    but it goes through ``app.utils.confirm_destructive`` rather than building
    its own ``QMessageBox``. It is a yes/no with a named button, a details pane
    and one extra tick, which is a graded HELPER's job: this module's recorded
    exemption from the never-a-raw-QMessageBox rule is for the multi-way
    disposition question above, and a yes/no is exactly what the rule says must
    not become a third exemption.

    Three rules, all of them #33's:

    * **The list comes before the deletion, and from a plan built earlier.**
      Nothing here reads the directory. What is shown is exactly what
      ``case_clean.apply_case_clean`` will act on, so the prompt cannot describe
      one set of files and the run remove another. The counts and total come
      from ``plan.summary`` — the same call the controller logs — so the two
      cannot disagree.
    * **The archives are named where they can be SEEN.** Point 3 asks for "the
      folders by name", and a details pane is collapsed by default, so
      ``prev_001/, prev_002/`` goes in the informative text and the per-file
      list stays in the details.
    * **The tick is off every time this opens**, because the helper rebuilds it
      per call and nothing persists it. Deleting the only record of a solve's
      earlier legs (#32) is a second deliberate act, not a remembered
      preference.

    Headless declines, and the helper has no way to be told otherwise: a clean
    must never happen on an unattended path. Run All / batch does not reach here
    at all (it auto-versions before the question is asked), so this is the
    backstop and not the mechanism.
    """
    lines = [f"Will be DELETED from work/ ({len(plan.outputs)}):"]
    lines += [f"    {e.name}  ({human_size(e.bytes)})" for e in plan.outputs]
    if plan.kept_inputs:
        lines += ["", f"Kept — this run's own inputs ({len(plan.kept_inputs)}):"]
        lines += [f"    {n}" for n in plan.kept_inputs]
    if plan.unclassified:
        lines += ["", f"Kept — not recognised ({len(plan.unclassified)}):"]
        lines += [f"    {n}" for n in plan.unclassified]
    if plan.archives:
        lines += ["", f"Archived previous runs ({len(plan.archives)}, kept "
                      "unless the box below is ticked):"]
        lines += [f"    {e.name}  ({human_size(e.bytes)})"
                  for e in plan.archives]

    informative = [
        f"{plan.summary()} will be deleted from work/. This cannot be undone.",
        "grid/ and dll/ are not touched, and anything not recognised as solver "
        "output is kept.",
    ]
    option = None
    if plan.archives:
        informative.insert(1, f"Archived previous runs in work/ — "
                              f"{plan.archive_names()} "
                              f"({human_size(plan.archives_bytes)}) — are kept.")
        option = (f"Also delete {len(plan.archives)} archived previous run(s), "
                  f"{plan.archive_names()} — the Results tab can no longer play "
                  "them back")

    answer = confirm_destructive(
        parent,
        "Clean and Run",
        f"Delete the previous run's output from case '{case}'?",
        "Delete and Run",
        informative="\n\n".join(informative),
        detail="\n".join(lines),
        option_label=option)
    if answer is None:
        return None
    return ApprovedClean(plan=plan, include_archives=answer)
