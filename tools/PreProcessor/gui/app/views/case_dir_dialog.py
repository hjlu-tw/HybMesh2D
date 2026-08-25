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

from app.services.solver_case import (
    CASE_IN_PLACE,
    CASE_NEW_VERSION,
)
from app.utils import is_headless


def ask_case_disposition(parent, case: str, case_root: str) -> str | None:
    """``CASE_IN_PLACE`` or ``CASE_NEW_VERSION``, or None when the user
    cancelled. Never ``CASE_ARCHIVE`` — see the module docstring.

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
    if clicked is new_btn:
        return CASE_NEW_VERSION
    # Cancel, or the window dismissed with its close button / Esc, where
    # clickedButton() can be None. Falling through to a disposition would START A
    # SOLVER RUN nobody asked for — the same "an unknown value must not resolve to
    # a plausible answer" rule solver_case.case_dir_flags enforces from the other
    # side. Every non-cancelling answer is matched explicitly above.
    return None
