"""Which legs of a restarted solve play as one animation.

USER-REQUESTED (2026-08-27). A restarted solve is several files (#32), and
until now the choice between them was binary: every leg, or — via
``This leg only`` — just the file that was opened. There was no way to say
"these three, not that one", which is what someone comparing a re-run leg
against the one it replaced actually wants; #43's own measurement of this repo's
``results/solver/case`` found two legs that both ran iterations 0-1000, i.e. one
segment solved twice, and playing them in sequence shows the same iterations
twice with no way to drop either.

**This reverses half of #43, deliberately and on the user's instruction.** #43
removed #32's per-load modal, on the ground that it "made the common case cost a
click and made an unattended run behave differently from an interactive one".
Both halves of that reasoning are respected rather than discarded:

* the dialog is **never shown on an unattended path** — :func:`ask_legs` returns
  ``None`` when headless, which means "every leg", exactly what a batch or CI run
  did before and does now;
* it is shown **once per load**, not once per rebuild, and the same dialog is
  reachable afterwards from the transport row — so the answer stays a control the
  user can see and reverse, which is the property #43 was protecting.

What is NOT preserved is "opening any leg opens the solve, and nothing is asked"
for the interactive case. That was #43's call and this is the user's; it is
recorded here as a reversal rather than quietly re-litigated, because the
argument #43 made was a good one and a future reader is entitled to see that it
was overruled on purpose rather than forgotten.

Qt-side by nature — it is a dialog — but it decides nothing: it is handed legs
and returns keys.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.utils import is_headless

_FG = "#c8cee0"
_HINT = "color:#6b7290; font-size:10px;"


def _leg_line(leg, opened: bool) -> str:
    """One row's label: which leg, how far it got, when it ran.

    The same three facts the restart chooser puts on its rows, and deliberately
    in the same order — a user meets these two lists about the same folders and
    should not have to re-learn them. The iteration count comes from
    ``case_run_note.iteration_span`` in both, so the two windows cannot describe
    one archive differently.
    """
    bits = [leg.key or "this file"]
    if leg.span.known:
        bits.append(f"iteration {leg.span.end}")
    if leg.stamp:
        bits.append(leg.stamp)
    if opened:
        bits.append("← the file you opened")
    return "   ".join(bits)


class LegPickerDialog(QDialog):
    """Tick the legs to play. Returns their keys, or None for "all of them"."""

    def __init__(self, parent, legs, opened_path: str, warnings=()):
        super().__init__(parent)
        self.setWindowTitle("Legs to play")
        self._boxes: list = []

        outer = QVBoxLayout(self)
        head = QLabel(
            f"This solve was restarted — it is {len(legs)} files. "
            "Tick the legs to play as one continuous animation.")
        head.setWordWrap(True)
        head.setStyleSheet(f"color:{_FG};")
        outer.addWidget(head)

        body = QWidget()
        rows = QVBoxLayout(body)
        rows.setContentsMargins(4, 2, 4, 2)
        rows.setSpacing(2)
        for leg in legs:
            box = QCheckBox(_leg_line(leg, leg.path == opened_path))
            box.setChecked(True)
            box.setStyleSheet(f"color:{_FG};")
            box.setProperty("leg_key", leg.key)
            rows.addWidget(box)
            self._boxes.append(box)
        rows.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setMinimumHeight(min(320, 40 + 24 * len(legs)))
        outer.addWidget(scroll)

        for msg in warnings:
            # An overlap ("these legs both ran iterations 0-1000") is the whole
            # reason a user would untick one, so it belongs beside the ticks
            # rather than only in the log they would have to scroll back through.
            lab = QLabel(msg)
            lab.setWordWrap(True)
            lab.setStyleSheet(_HINT)
            outer.addWidget(lab)

        picks = QHBoxLayout()
        for text, on in (("All", True), ("None", False)):
            btn = QPushButton(text)
            btn.setFixedWidth(56)
            btn.clicked.connect(lambda _c, v=on: self._set_all(v))
            picks.addWidget(btn)
        picks.addStretch()
        outer.addLayout(picks)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _set_all(self, on: bool) -> None:
        for box in self._boxes:
            box.setChecked(on)

    def selection(self) -> set:
        return {b.property("leg_key") for b in self._boxes if b.isChecked()}


def ask_legs(parent, legs, opened_path: str, warnings=(),
             preselect=None) -> set | None:
    """The picked leg keys, or ``None`` for "every leg".

    ``None`` rather than "the full set" is the answer for both *unattended* and
    *cancelled*, and that is one meaning rather than two: it is the state the
    view already has for "no restriction", so a cancel leaves the animation
    exactly as it would have been and an unattended run is unchanged from #43.

    An empty tick-list is also returned as ``None`` — a series with no legs is
    not a thing the transport can show, and refusing to build one is better than
    a picture that silently disappears.
    """
    if is_headless() or len(legs) < 2:
        return None
    dlg = LegPickerDialog(parent, legs, opened_path, warnings)
    if preselect is not None:
        for box in dlg._boxes:
            box.setChecked(box.property("leg_key") in preselect)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    picked = dlg.selection()
    return picked or None
