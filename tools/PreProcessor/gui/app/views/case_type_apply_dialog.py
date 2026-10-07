"""The one interrupt applying a case type is allowed (#170): confirm, then apply.

#158's user story 23 reads "be asked to confirm the boundary-layer first cell
height on EVERY application", and `case_type_scale.Application.apply` already
makes that structural by refusing until it is answered. This dialog is the
window's way of answering it — and, because it has to stop the operator anyway,
it is also where what is about to change is SHOWN rather than discovered
afterwards.

**IT SHOWS THE WHOLE ACT, NOT ONLY THE QUESTION.** The `was -> now` list is every
field the case type has an opinion about (story 24), the scale line says what the
ruler did to the geometric ones, and the roles line says which of the operator's
curves each slot binds. A confirmation dialog that asked for a number and said
nothing about the twenty other fields being overwritten would be the half-informed
"OK" this whole seam exists against.

**CONFIRMING AND CORRECTING ARE ONE ACT.** The spin box is pre-filled with the
value the case type offers and is EDITABLE, which is `--confirm NAME=VALUE`'s own
grammar: a question whose only answer is "yes" is a button people learn to click.
The reason the parameter is physical rides beside it (`Confirmation.describe`),
and so does what the value MEANS in the operator's own unit — a first cell height
that crossed a unit change shows up as the absurd length it is rather than as the
number it was authored as.

**A SCI SPIN BOX, NEVER A PLAIN ONE.** A y+~1 first cell on a chord-normalised
body is routinely 1e-7, and this repo's standing rule is that a physical length
is a `SciDoubleSpinBox` (`views/clean_double_spin_box.py` records what a
fixed-notation box silently clamps). Getting that wrong here would change the
mesh the engineer asked for in the one dialog whose whole subject is that number.

Cancel writes nothing: the service applies to a deep copy and the host only keeps
it on acceptance, so there is no half-applied state to undo.

**HEADLESS IT ANSWERS CANCEL, and it answers for ITSELF.** `gui-seams.md` grants
two bespoke-dialog exemptions from the graded helpers and records that "both make
the headless early-return themselves"; this is the third and follows that rule
rather than leaving the guard in its caller, where a second caller would have to
remember it. Cancel is the only safe default here: the question is a physical
parameter nobody answered, and the service refuses an unanswered one — so the
unattended path gets a refusal, never somebody else's Reynolds number applied in
silence.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QPlainTextEdit, QVBoxLayout,
)

from app.utils import is_headless
from app.views.clean_double_spin_box import SciDoubleSpinBox

#: The range the confirmation box accepts. Deliberately wider than any mesh
#: field's: it is the operator's own flow being answered for, and a bound that
#: clamped their y+ would be this dialog committing the error it exists against.
_LO, _HI = 1e-12, 1e6


class CaseTypeApplyDialog(QDialog):
    """What applying will do, and the physical parameters it will not assume."""

    def __init__(self, parent, plan, config):
        super().__init__(parent)
        self._plan = plan
        self.setWindowTitle("Apply case type")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)

        head = QLabel("\n".join(plan.describe(config)[:3]))
        head.setWordWrap(True)
        lay.addWidget(head)

        # READ-ONLY and selectable rather than a QLabel: the field list is as
        # long as the case type's overlay, and a wall of text in a label cannot
        # be scrolled or copied into a bug report.
        body = QPlainTextEdit()
        body.setReadOnly(True)
        body.setPlainText("\n".join(
            c.describe() for c in plan.changes(config)))
        body.setMaximumHeight(170)
        lay.addWidget(body)

        self._boxes = {}
        if plan.confirmations:
            why = QLabel(
                "Confirm for your own flow — these are set by physics rather "
                "than by the size of the body, so they are never scaled and "
                "never applied unasked:")
            why.setWordWrap(True)
            lay.addWidget(why)
            form = QFormLayout()
            for c in plan.confirmations:
                box = SciDoubleSpinBox()
                box.setRange(_LO, _HI)
                box.setValue(float(c.offered))
                box.setToolTip(c.describe())
                form.addRow(QLabel(c.name), box)
                note = QLabel("%.6g m — %s" % (c.metres, c.why))
                note.setWordWrap(True)
                note.setStyleSheet("color:#8a93ad; font-size:10px;")
                form.addRow(QLabel(""), note)
                self._boxes[c.name] = box
            lay.addLayout(form)

        if plan.roles.slots:
            roles = QLabel("\n".join(
                "    " + b.describe() for b in plan.bindings()))
            roles.setWordWrap(True)
            roles.setStyleSheet("color:#8a93ad; font-size:10px;")
            lay.addWidget(QLabel("It will bind:"))
            lay.addWidget(roles)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Apply")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def exec(self) -> int:
        """Show it, or answer Cancel on a platform with no display.

        Overridden rather than guarded at the call site: see the module
        docstring. `QDialog.DialogCode.Rejected` is 0, which is what the host
        already reads as "cancelled, nothing was changed".
        """
        if is_headless():
            return int(QDialog.DialogCode.Rejected)
        return super().exec()

    def confirmed(self) -> dict:
        """`{name: value}` for every physical parameter, as the operator left it.

        EVERY one, never only the ones they touched: a confirmation is an answer
        and leaving the offered value in place IS the answer, which is what the
        bare `--confirm NAME` spelling means on the other host.
        """
        return {name: box.value() for name, box in self._boxes.items()}
