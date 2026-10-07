"""The table where the operator says WHICH of their curves is the body (#170).

One row per role the case type's family needs, under the picker in the Mesh
panel. #158's user stories 2, 3 and 4 — assign a role to each segment I drew,
have them pre-selected where they can be guessed, confirm every pre-selection
before it is used — are this widget plus the service behind it.

**A TABLE, NOT THE CANVAS.** Assigning by clicking a curve was the other
candidate and was declined: this repo has a USER-REPORTED defect in which
drawing order rather than click order decided a result, and #158 excludes
drawing-order conventions by name. A row that NAMES the geometry it binds, and
says which segments, cannot be read two ways.

**ASSIGNING AND CONFIRMING ARE ONE ACT.** There is no confirm checkbox. The
combo's first real row IS the pre-selection, carrying the reason the tool offers
it, and selecting it is the confirmation — exactly what `--role body` means to
`apply_case_type.py`, where confirming and correcting are deliberately one
grammar so neither is a button people learn to click. `(not assigned)` writes no
entry, which is what `RolePlan.bind` refuses on, so the structural refusal is
untouched by anything here.

**IT REBUILDS ON SHAPE, NEVER ON A KEYSTROKE.** The read-out above it re-renders
per edit (#169), and this widget is refreshed from the same place; rebuilding its
rows on every keystroke would take the caret out of the segment box mid-type.
:meth:`set_plan` therefore compares a SHAPE KEY — the roles, the candidate
geometries, the pre-selections — and returns without touching a widget when
nothing structural moved. The values are not part of that key: they are what the
operator is editing.

``panel_edited`` is the protocol `undo_ctrl._wire_widget_edits` connects for a
composite control that rebuilds its own children — the restart chooser's (#31),
and the reason it exists: a one-shot traversal of children at construction cannot
reach a combo created later, so a row made after a family change would edit the
panel and never reach the model.

The rules are `.claude/rules/gui-apply.md`; what this file owns is only the
widgets. Every sentence the operator reads here comes from the Qt-free services
(`case_type_roles.ROLE_MEANING`, `Guess.describe`, `RoleSlot.describe`), for
`gui-seams.md`'s reason.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QGridLayout, QLabel, QLineEdit, QWidget,
)

from app.services import case_type_roles
from app.utils import block_signals

#: What the combo carries for "this role is not assigned". A string no stored
#: spelling can be, like `case_type_picker.BROWSE`, so it cannot collide with a
#: real geometry — and it is the row that leaves the entry OUT of the model,
#: which is the state `RolePlan.bind` refuses on.
UNASSIGNED = "\x00none"

#: What the combo carries for "the one the tool pre-selected, confirmed". The
#: EMPTY string, because that is already what `--role body` (bare) writes into
#: an assignment and what `RolePlan.resolve` reads as "take the guess" — a second
#: spelling here would be a second meaning to keep in step.
ACCEPT_GUESS = ""

_HINT = "color:#8a93ad; font-size:10px;"
_HEAD = "color:#c8cee0; font-size:11px;"


def _sync_segs(combo, segs) -> None:
    """Keep the segment box live only for a geometry chosen BY NAME.

    Accepting the pre-selection takes the guess's own segments and
    `(not assigned)` binds nothing, so an editable box for either offers an edit
    that is read nowhere. ONE function rather than the same condition at the two
    places that need it — a rule spelled twice is a rule that drifts once.
    """
    segs.setEnabled(combo.currentData() not in (UNASSIGNED, ACCEPT_GUESS))


def _same_spec(left, right) -> bool:
    """True when two assignment specs name the same curve and the same segments.

    By VALUE rather than by string: `"g.dat:17,18"` and `"g.dat:17, 18"` are one
    assignment written two ways, and treating them as different is what makes a
    refresh rewrite a row the operator is typing into.
    """
    if left is None or right is None:
        return left is None and right is None
    l_geom, l_ids = case_type_roles.parse_spec(left)
    r_geom, r_ids = case_type_roles.parse_spec(right)
    return l_geom == r_geom and (l_ids or ()) == (r_ids or ())


class CaseTypeRolesTable(QWidget):
    """One row per role, rebuilt when the family or the drawing changes."""

    panel_edited = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setVerticalSpacing(2)
        self._rows = {}          # role -> (combo, segs line edit)
        self._shape = None
        self._empty = QLabel("")
        self._empty.setWordWrap(True)
        self._empty.setStyleSheet(_HINT)
        self._grid.addWidget(self._empty, 0, 0, 1, 3)
        self._empty.hide()

    # ── building ──────────────────────────────────────────────────────────
    def set_plan(self, plan, values=None) -> None:
        """Show the roles `plan` needs, selecting `values`.

        `plan` is an `case_type_apply.ApplyPlan`, or ``None`` for "no case type
        is chosen / it will not load" — in which case the table says so in one
        line rather than disappearing, so the section does not change height
        under the operator as they pick.
        """
        shape = self._shape_key(plan)
        if shape != self._shape:
            self._rebuild(plan)
            self._shape = shape
        self._select(dict(values or {}))

    @staticmethod
    def _shape_key(plan):
        """What a rebuild depends on — never the assigned values.

        The values are what the operator is editing; including them would make
        every selection rebuild the row that made it, which is how a composite
        control loses a caret and a focus ring.
        """
        if plan is None or not plan.roles.slots:
            return ("none", plan is not None)
        ctx = plan.roles.ctx
        return ("rows",
                tuple((s.role, s.required) for s in plan.roles.slots),
                tuple(g.spelling for g in (ctx.geoms if ctx else ())),
                tuple(sorted((r, g.geom, g.segs, g.why)
                             for r, g in plan.roles.guesses.items())))

    def _rebuild(self, plan) -> None:
        for i in reversed(range(self._grid.count())):
            w = self._grid.itemAt(i).widget()
            if w is not None and w is not self._empty:
                self._grid.removeWidget(w)
                w.deleteLater()
        self._rows = {}
        if plan is None:
            self._say("Pick a case type above to see which of your curves it "
                      "needs, and to apply it.")
            return
        if not plan.roles.slots:
            self._say("This case type names no topology family that binds to "
                      "your CAD, so there are no roles to assign. Applying it "
                      "writes its settings and binds nothing.")
            return
        self._empty.hide()
        head = QLabel("Roles this case type needs on your own geometry")
        head.setStyleSheet(_HEAD)
        self._grid.addWidget(head, 0, 0, 1, 3)
        geoms = plan.candidates()
        for row, slot in enumerate(plan.roles.slots, start=1):
            self._add_row(row * 2 - 1, slot, plan.roles.guesses.get(slot.role),
                          geoms)

    def _say(self, text: str) -> None:
        self._empty.setText(text)
        self._empty.show()

    def _add_row(self, at: int, slot, guess, geoms) -> None:
        label = QLabel(slot.role + ("" if slot.required else "  (optional)"))
        label.setToolTip(slot.describe())
        combo = QComboBox()
        combo.addItem("(not assigned)", UNASSIGNED)
        if guess is not None:
            # THE PRE-SELECTION IS A ROW, and selecting it is the confirmation.
            # Its reason rides the item text and its tooltip, because "confirm
            # this" with no reason is a control people learn to click.
            combo.addItem("pre-selected: %s — %s"
                          % (os.path.basename(guess.geom) or guess.geom,
                             guess.why), ACCEPT_GUESS)
            combo.setItemData(combo.count() - 1, guess.describe(),
                              Qt.ItemDataRole.ToolTipRole)
        for g in geoms:
            combo.addItem(os.path.basename(g.path) or g.spelling, g.spelling)
            combo.setItemData(combo.count() - 1, g.spelling,
                              Qt.ItemDataRole.ToolTipRole)
        segs = QLineEdit()
        segs.setPlaceholderText("all segments")
        segs.setToolTip(
            "Leave blank to bind every segment this geometry carries, or give "
            "the segment ids as 1,2,3 — they are bound in the geometry's own "
            "order whatever order you type them in.")
        segs.setMaximumWidth(120)
        meaning = QLabel(case_type_roles.ROLE_MEANING.get(slot.role, ""))
        meaning.setWordWrap(True)
        meaning.setStyleSheet(_HINT)
        self._grid.addWidget(label, at, 0)
        self._grid.addWidget(combo, at, 1)
        self._grid.addWidget(segs, at, 2)
        self._grid.addWidget(meaning, at + 1, 1, 1, 2)
        combo.currentIndexChanged.connect(self._on_edited)
        segs.textEdited.connect(self._on_edited)
        self._rows[slot.role] = (combo, segs)

    # ── the operator's edits ──────────────────────────────────────────────
    def _on_edited(self, *_args) -> None:
        """One edit: keep the segment box honest, then report for the panel.

        The box is only meaningful for a geometry chosen BY NAME: accepting the
        pre-selection takes the guess's own segments, and `(not assigned)` binds
        nothing, so leaving it live for either would offer an edit that is read
        nowhere.
        """
        for combo, segs in self._rows.values():
            _sync_segs(combo, segs)
        self.panel_edited.emit()

    # ── the value ─────────────────────────────────────────────────────────
    def shown_roles(self) -> frozenset:
        """The roles this table currently has a row for.

        What :meth:`read` can speak for, and so what a host may safely REPLACE
        in a stored assignment. Public because the alternative is the panel
        reaching into `_rows`, and a private read across a module boundary is a
        rule with nothing holding its two readings in step.
        """
        return frozenset(self._rows)

    def read(self) -> dict:
        """`{role: spec}` for every role the operator HAS answered for.

        A role on `(not assigned)` is absent rather than empty, which is the
        whole mechanism: absent is what `RolePlan.bind` refuses on, and `""`
        means "the pre-selection, confirmed".
        """
        out = {}
        for role, (combo, segs) in self._rows.items():
            data = combo.currentData()
            if data == UNASSIGNED:
                continue
            if data == ACCEPT_GUESS:
                out[role] = ACCEPT_GUESS
                continue
            ids = segs.text().strip()
            out[role] = "%s:%s" % (data, ids) if ids else str(data)
        return out

    def _select(self, values: dict) -> None:
        """Show `values`, leaving every role it does not name unassigned.

        A ROW THAT ALREADY SAYS THIS IS LEFT ALONE. The read-out above refreshes
        per keystroke and hands this the configuration it just read back OUT of
        these very widgets, so writing it in again would be a no-op with one
        visible consequence: `QLineEdit.setText` resets the caret to the end,
        and the spec is NORMALISED on the way through (`17,18` comes back as
        `17, 18`), so the text genuinely differs and the caret jumps on every
        character typed. Comparing what the row would READ against what it is
        being asked to show is the exact test, because `read` is the only thing
        that defines a row's value.
        """
        current = self.read()
        for role, (combo, segs) in self._rows.items():
            spec = values.get(role)
            if role in current and _same_spec(current[role], spec):
                continue
            if role not in current and spec is None:
                continue
            with block_signals(combo, segs):
                if spec is None:
                    combo.setCurrentIndex(max(combo.findData(UNASSIGNED), 0))
                    segs.setText("")
                elif str(spec).strip() == "":
                    combo.setCurrentIndex(max(combo.findData(ACCEPT_GUESS), 0))
                    segs.setText("")
                else:
                    geom, ids = case_type_roles.parse_spec(spec)
                    at = combo.findData(geom)
                    if at < 0:
                        # A geometry the drawing no longer carries. ADDED rather
                        # than silently reset to unassigned, by the picker's own
                        # rule for a case type whose file has gone: turning "your
                        # curve has moved" into "you never assigned one" is the
                        # silence this seam exists against.
                        combo.addItem("%s — not in this drawing"
                                      % (os.path.basename(geom) or geom), geom)
                        at = combo.count() - 1
                    combo.setCurrentIndex(at)
                    segs.setText(", ".join(str(i) for i in ids) if ids else "")
            _sync_segs(combo, segs)
