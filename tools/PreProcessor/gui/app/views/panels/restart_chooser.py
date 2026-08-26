""""What does this run start from?" — one list over the case's own history.

#31, USER-REQUESTED (2026-08-21). The Solver panel used to ask this as a
``Restart`` tick plus a free-text ``zdump_fn_restart`` path, autofilled from a
fixed name in ``work/`` and blind to the ``work/prev_<NNN>/`` archives #26
creates. So "continue further" and "re-run the same leg" — the two intentions a
user actually has after looking at a result — were the same widget, and the
second one meant remembering which file the last run had resumed from and
browsing to it. The thing being decided is an ITERATION COUNT; a path field
cannot show one.

The rows come from ``services/restart_points`` (Qt-free, and the module that
reads ``RUN.txt``); this file is the control. Four things about it are deliberate:

* **Radio buttons, not a list widget.** The panel→model sync is driven by one
  traversal that connects the "user changed me" signal of every input widget
  (``controllers/undo_ctrl._wire_widget_edits``), and it knows spin boxes,
  combos, line edits and CHECKABLE BUTTONS. A ``QListWidget`` selection is none
  of those, so the model would silently lag the control — the exact staleness
  that single data-flow direction exists to remove. The rows are also rebuilt
  whenever the case changes, i.e. after that one-shot traversal has run, so this
  widget declares ``panel_edited`` and the traversal connects THAT; the rows
  report through their owner rather than being wired individually.
* **Cold start is the first row, not a separate tick.** Turning restart off used
  to be a control in another place from the one that chose what to restart from.
* **"Other file…" keeps the path honest.** An arbitrary dump — one in another
  case dir, which #25 supports — is still reachable, and a config restored from a
  ``.hws`` whose path is not in this case's history lands here rather than being
  silently rewritten to something that merely looks valid.
* **The iteration count is shown as a BOUND.** ``RUN.txt`` records the last ROW
  of a convergence history, and the solver writes one every
  ``print_convg_per_niter`` iterations, so a run that reached 2000 leaves 1990 in
  the file (#30, measured). Printing 1990 as the final count would be a small lie
  in the one field the user reads, so the row says ``1990+`` and the tooltip says
  what that means.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.services import restart_points as rp
from app.services.logging_setup import get_logger
from app.views.panels.field_widgets import browse_row

_log = get_logger(__name__)

_HINT = "color:#6b7290; font-size:10px;"
_ROW_QSS = "QRadioButton{color:#a0a8c0;} QRadioButton:disabled{color:#565b73;}"

#: The row prose. The service returns facts; the words are here.
_TITLES = {
    rp.COLD: "Cold start — initial conditions",
    rp.LATEST: "Latest result",
    rp.OTHER: "Other file…",
}


def _iteration_text(point) -> str:
    """``"iteration 1990+"`` — a bound, never a final count (see the module
    docstring), and "iteration unknown" when the archive predates ``RUN.txt``."""
    if point.iteration == rp.UNKNOWN_ITERATION:
        return "iteration unknown"
    return f"iteration {point.iteration}+"


def _row_text(point) -> str:
    bits = [_TITLES.get(point.kind, point.key)]
    # Cold start has no iteration count to show, and "Other file…" has no row of
    # its own to describe — its numbers, if any, are in a file nobody has read.
    if point.kind in (rp.LATEST, rp.ARCHIVE):
        bits.append(_iteration_text(point))
        if point.stamp:
            bits.append(f"({point.stamp})")
        if not point.selectable:
            bits.append("— no zone dump in this archive")
    if point.resumed_by_last:
        bits.append("← the last run started here")
    return "   ".join(bits)


def _row_tip(point) -> str:
    if point.kind == rp.OTHER:
        return ("Restart from a dump this case does not hold — one in another "
                "case directory, which the run stages a reference to (#25).")
    if point.kind == rp.COLD:
        return ("Start from the initial conditions — no restart. This is also "
                "what the previous run did, if it is the marked row.")
    lines = [point.zdump or "(this archive holds no zone dump)"]
    if point.convg:
        lines.append(point.convg)
    if point.iteration != rp.UNKNOWN_ITERATION:
        bound = (f" and fewer than {point.iteration + point.interval}"
                 if point.interval > 0 else "")
        lines.append(f"The convergence history's last row is "
                     f"{point.iteration}, so that run reached at least "
                     f"{point.iteration}{bound} iterations.")
    else:
        lines.append("This archive carries no RUN.txt (it predates one), so how "
                     "far that run got is not recorded.")
    if point.tag:
        # The run tag is the one thing #30's rename discards and RUN.txt keeps:
        # which HOST produced that leg, .gui for the GUI and .cli for the
        # headless pipeline.
        lines.append(f"Produced by a {point.tag.lstrip('.')} run.")
    if point.resumed_by_last:
        lines.append("The previous run in this case started from here — pick it "
                     "to run the same leg again.")
    return "\n".join(lines)


class RestartChooser(QWidget):
    """The rows plus the "Other file…" escape, bound to three model fields.

    ``panel_edited`` is the protocol ``undo_ctrl._wire_widget_edits`` connects: a
    composite control whose children are rebuilt at runtime cannot be covered by
    a one-shot traversal of its children.
    """

    panel_edited = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: tuple = ()
        self._buttons: list = []
        self._loading = False

        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        head = QLabel("Start from:")
        head.setStyleSheet("color:#8b93b0;")
        box.addWidget(head)

        self._rows = QVBoxLayout()
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(1)
        box.addLayout(self._rows)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        self._empty = QLabel("(this case has no results yet)")
        self._empty.setStyleSheet(_HINT)
        box.addWidget(self._empty)

        # The "Other file…" pair. Two fields, because the solver takes two
        # references and only the chooser's rows can pair them for the user.
        self.zdump_fn_restart = QLineEdit()
        self.zdump_fn_restart.setPlaceholderText("zone dump (binDumpZ.dat…)")
        self.convg_fn_restart = QLineEdit()
        self.convg_fn_restart.setPlaceholderText("convergence history (optional)")
        form = QFormLayout()
        form.setContentsMargins(14, 2, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Zone dump", browse_row(self, self.zdump_fn_restart,
                                            "Select zone-dump file"))
        form.addRow("Convg file", browse_row(self, self.convg_fn_restart,
                                             "Select convergence file"))
        self._other = QWidget()
        self._other.setLayout(form)
        box.addWidget(self._other)
        self._other.setVisible(False)
        # textEdited, not textChanged: only user typing, never set_selection's
        # own population — the same rule the panel traversal follows.
        for edit in (self.zdump_fn_restart, self.convg_fn_restart):
            edit.textEdited.connect(self._on_other_typed)

        self.refresh("")

    # ── model <-> view ────────────────────────────────────────────────────
    def selection(self) -> tuple:
        """``(restart, zdump, convg)`` for the picked row.

        Cold start is ``(False, "", "")`` — it clears both fields, so a config
        saved from it carries no stale path, and the mesher-side "restart is on
        but no source is set" error cannot be reached from here.
        """
        point = self._picked()
        if point is None or point.kind == rp.COLD:
            return False, "", ""
        if point.kind == rp.OTHER:
            return (True, self.zdump_fn_restart.text().strip(),
                    self.convg_fn_restart.text().strip())
        return True, point.zdump, point.convg

    def set_selection(self, restart: bool, zdump: str, convg: str) -> None:
        """Show what the MODEL says, without emitting an edit.

        A path this case's history does not offer is not an error and is not
        rewritten: it lands on "Other file…" with the path in the field, which is
        where a reopened workspace pointing at a case that has moved on belongs.
        ``solver_ctrl._validate`` is what refuses it, before the solver runs.
        """
        self._loading = True
        try:
            self.zdump_fn_restart.setText(zdump or "")
            self.convg_fn_restart.setText(convg or "")
            key = rp.COLD if not restart else self._key_for(zdump)
            self._select(key)
        finally:
            self._loading = False

    def refresh(self, case_root: str) -> None:
        """Rebuild the rows from the case dir, keeping the current answer.

        Derived every time, never cached: the case dir is the truth, and a
        workspace reopened after the case moved on must not offer rows that are
        gone.
        """
        restart, zdump, convg = self.selection() if self._buttons else (False, "", "")
        try:
            points = (rp.list_restart_points(case_root) if case_root else ())
        except OSError:
            # Listing a case dir is allowed to fail (a removed volume, a
            # permission change); the chooser then offers what it always can.
            _log.warning("could not list restart points under %s", case_root,
                         exc_info=True)
            points = ()
        self._points = tuple(points) + (rp.RestartPoint(kind=rp.OTHER,
                                                        key=rp.OTHER),)
        self._rebuild()
        self.set_selection(restart, zdump, convg)

    # ── rows ──────────────────────────────────────────────────────────────
    def _rebuild(self) -> None:
        for btn in self._buttons:
            self._group.removeButton(btn)
            self._rows.removeWidget(btn)
            # setParent(None) BEFORE deleteLater, which is deferred: a widget
            # merely removed from a layout keeps its parent, its geometry and its
            # visibility, so without this the previous case's rows stay drawn on
            # top of the new ones until the event loop gets round to them
            # (measured: a stale "Other file…" row survived the first refresh).
            btn.setParent(None)
            btn.deleteLater()
        self._buttons = []
        for point in self._points:
            btn = QRadioButton(_row_text(point))
            btn.setStyleSheet(_ROW_QSS)
            btn.setToolTip(_row_tip(point))
            btn.setEnabled(point.selectable)
            btn.setProperty("restart_key", point.key)
            btn.toggled.connect(self._on_row_toggled)
            self._group.addButton(btn)
            self._rows.addWidget(btn)
            self._buttons.append(btn)
        # Only the cold and "other" rows exist until a run has produced
        # something; say so rather than showing a list that looks broken.
        self._empty.setVisible(
            not any(p.kind in (rp.LATEST, rp.ARCHIVE) for p in self._points))

    def _picked(self):
        for btn, point in zip(self._buttons, self._points):
            if btn.isChecked():
                return point
        return None

    def _key_for(self, zdump: str) -> str:
        """The row that names ``zdump``, or ``OTHER``.

        By resolved path: the model holds an absolute one and so does every row,
        so a match is exact rather than a basename coincidence between two cases.
        """
        want = os.path.abspath((zdump or "").strip())
        if not want:
            return rp.COLD
        for point in self._points:
            if point.zdump and os.path.abspath(point.zdump) == want:
                return point.key
        return rp.OTHER

    def _select(self, key: str) -> None:
        for btn, point in zip(self._buttons, self._points):
            if point.key == key:
                btn.setChecked(True)
                self._other.setVisible(point.kind == rp.OTHER)
                return
        # The key is gone (an archive removed under us): fall back to cold
        # start rather than leaving nothing checked, which would read as
        # "restart, source unset".
        if self._buttons:
            self._buttons[0].setChecked(True)
        self._other.setVisible(False)

    # ── signals ───────────────────────────────────────────────────────────
    def _on_row_toggled(self, checked: bool) -> None:
        if not checked:
            return
        point = self._picked()
        self._other.setVisible(point is not None and point.kind == rp.OTHER)
        if not self._loading:
            self.panel_edited.emit()

    def _on_other_typed(self, _text: str) -> None:
        if not self._loading:
            self.panel_edited.emit()
