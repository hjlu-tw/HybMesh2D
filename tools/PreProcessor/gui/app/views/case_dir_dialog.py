"""The prompt for "this case name already has results — now what?".

Three answers, and until #26 only two of them existed. A **restart** continues a
solution and therefore belongs in the case folder it is resuming; the only option
that stayed in that folder was ``Overwrite``, which wrote over the previous run's
outputs as the new run produced its own — the dump being resumed from included.
So the destructive option was the only one that did what the user asked for, and
the dialog said nothing about restart at all. USER-REPORTED (2026-08-20).

With a restart on, the same-directory option is now the ARCHIVING one
(``services/case_archive`` moves the previous outputs to ``work/prev_NNN/``
first), the dialog says so, and that is the default button. Overwriting in place
survives as an explicit escape and stays labelled destructive.

A view, not a decision: this asks and reports the answer. What the answer means
mechanically is ``solver_case.case_dir_flags``, and the logging is the
controller's, which owns the user log.
"""
from __future__ import annotations

from app.services.case_archive import next_archive_name
from app.services.solver_case import (
    CASE_ARCHIVE,
    CASE_IN_PLACE,
    CASE_NEW_VERSION,
)
from app.utils import is_headless


def ask_case_disposition(parent, case: str, case_root: str,
                         restart: bool) -> str | None:
    """One of the ``CASE_*`` values, or None when the user cancelled.

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
    archive_btn = None
    if restart:
        # Name the concrete directory rather than a placeholder: the counter is
        # cheap to read and "prev_003" tells the user this has happened twice.
        prev = next_archive_name(case_root) or "prev_NNN"
        box.setInformativeText(
            "This run RESTARTS from a previous dump, so it belongs in this same "
            "directory.\n\n"
            f"Continuing here first moves the previous run's outputs into "
            f"work/{prev}/, and renames the dump this run resumes from to "
            f"….{prev} beside them — the solver can only read a restart source "
            "from its own directory. Nothing is overwritten, and the restart "
            "reference is updated to match.\n\n"
            "Overwriting in place writes over them instead — including the dump "
            "being resumed from, which the solver's own output dump is named "
            "after.")
        archive_btn = box.addButton(f"Continue Here (archive to {prev})",
                                    QMessageBox.ButtonRole.AcceptRole)
        new_btn = box.addButton("New Versioned Dir",
                                QMessageBox.ButtonRole.ActionRole)
        overwrite_btn = box.addButton("Overwrite in Place",
                                      QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(archive_btn)
    else:
        box.setInformativeText(
            "Overwrite the existing results, or keep them and run into a new "
            f"auto-versioned directory (e.g. '{case}_002')?")
        overwrite_btn = box.addButton("Overwrite",
                                      QMessageBox.ButtonRole.DestructiveRole)
        new_btn = box.addButton("New Versioned Dir",
                                QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(new_btn)
    box.addButton(QMessageBox.StandardButton.Cancel)

    box.exec()
    clicked = box.clickedButton()
    if clicked is overwrite_btn:
        return CASE_IN_PLACE
    # `archive_btn is None` in the non-restart branch, and `clicked` is None when
    # the window was dismissed — so the identity test alone would match them to
    # each other and answer ARCHIVE for a dialog that offered no such button.
    if archive_btn is not None and clicked is archive_btn:
        return CASE_ARCHIVE
    if clicked is new_btn:
        return CASE_NEW_VERSION
    # Cancel, or the window dismissed with its close button / Esc, where
    # clickedButton() can be None. Falling through to a disposition would START A
    # SOLVER RUN nobody asked for — the same "an unknown value must not resolve to
    # a plausible answer" rule solver_case.case_dir_flags enforces from the other
    # side. Every non-cancelling answer is matched explicitly above.
    return None
