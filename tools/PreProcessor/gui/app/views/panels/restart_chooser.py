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
* **The iteration count is the count the SOLVER PRINTED**, and this file does
  not compute it: ``point.span`` comes from ``case_run_note.iteration_span``, so
  this window and the Results leg list cannot describe one archive differently.
  A row reads ``iteration 2000``.

  **That is a REVERSAL** (#43). The first version of this file rendered it as the
  bound ``1990+``, on the argument that naming 2000 would be a fabrication, and
  recorded that as a deliberate departure from #31's own specification — which
  had asked for a bare ``iteration 2000``. The specification was right: the
  solver writes a row every ``print_convg_per_niter`` iterations and none for the
  final one, so ``1990 + 10`` recovers 2000 exactly (measured against the real
  binary for both #26 and #30). What survives of the caveat is that an
  INTERRUPTED run got no further than the printed count, which makes the figure
  an upper bound — that, and whether it was recorded or recomputed, is what the
  tooltip is for.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics
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
    """``"iteration 2000"`` — the count the solver printed (see the module
    docstring), and "iteration unknown" only when neither the archive's record nor
    its convergence history can supply one."""
    if not point.span.known:
        return "iteration unknown"
    return f"iteration {point.span.end}"


def _short_stamp(stamp: str) -> str:
    """``"2026-08-27 09:32:31"`` -> ``"08-27 09:32"``.

    The rows are compared with EACH OTHER, so the year and the seconds are
    what a row can afford to lose first — both remain in the tooltip, which is
    where a reader who wants the exact moment goes. This is width the row has
    to find: see :func:`_row_text`.
    """
    parts = stamp.split()
    if len(parts) != 2:
        return stamp
    date, clock = parts
    return f"{date[5:]} {clock[:5]}" if len(date) >= 10 else stamp


def _row_text(point) -> str:
    """The row, kept SHORT enough to fit the panel it lives in.

    USER-REPORTED (2026-08-27): the text ran past the field with no way to
    scroll to the rest. That is structural rather than a matter of taste —
    ``SolverConfigPanel`` caps its content at 430px and sets
    ``setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)`` with
    ``setWidgetResizable(True)``, so a row wider than the viewport is CLIPPED and
    unreachable. Measured before this change, the marked row wanted **494px**
    against a ceiling of ~390px usable, so it could not fit at any window size.

    Two things buy the width back, and neither drops a fact — the full text
    lives in the tooltip either way:

    * the timestamp loses its year and seconds (:func:`_short_stamp`);
    * the marker is ``← last run`` rather than ``← the last run started here``,
      which alone was ~150px.

    Measured after: 321px for the worst row. :class:`_Row` then elides whatever
    a genuinely narrow sidebar still cannot fit, so text is never silently cut
    mid-glyph — an ellipsis at least SAYS there is more.
    """
    bits = [_TITLES.get(point.kind, point.key)]
    # Cold start has no iteration count to show, and "Other file…" has no row of
    # its own to describe — its numbers, if any, are in a file nobody has read.
    if point.kind in (rp.LATEST, rp.ARCHIVE):
        bits.append(_iteration_text(point))
        if point.stamp:
            bits.append(_short_stamp(point.stamp))
        if not point.selectable:
            bits.append("— no dump")
    if point.resumed_by_last:
        bits.append("← last run")
    return "   ".join(bits)


def _span_tip(span) -> str:
    """Where the row's iteration count came from, and what it is not.

    Both caveats, because they are different questions and a user is entitled to
    each (#43): whether the figure was RECORDED in the archive's ``RUN.txt`` or
    RECOMPUTED from its convergence history, and that an interrupted run makes it
    an upper bound rather than an exact count. The arithmetic is spelled out
    because it is the thing #30 and #31 got wrong, and a reader meeting a
    suspiciously round number should be able to check it.
    """
    if not span.known:
        return ("Neither a RUN.txt record nor a readable convergence history, so "
                "how far that run got cannot be told.")
    source = ("recorded in this archive's RUN.txt" if span.recorded
              else "recomputed from this archive's own convergence history")
    return (f"That run reached iteration {span.end} — its last convergence row is "
            f"{span.last_row} and the solver prints one every {span.interval} "
            f"iterations, writing none for the final one ({span.last_row} + "
            f"{span.interval} = {span.end}; last row {source}).\n"
            "An upper bound: a run interrupted part-way through an interval got "
            "no further than this.")


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
    if point.stamp:
        # SAY which event the row's time is. The row shows one timestamp and an
        # archive folder has two candidates; leaving that implicit is what let
        # "the same run" appear to change its time when it was archived
        # (USER-REPORTED 2026-08-27).
        lines.append(f"That run finished {point.stamp}.")
    if point.archived_at and point.archived_at != point.stamp:
        lines.append(f"Its outputs were archived into {point.key}/ later, at "
                     f"{point.archived_at}, by the run that followed it — which "
                     "is when the FOLDER was made, not when the run ended.")
    lines.append(_span_tip(point.span))
    if point.tag:
        # The run tag is the one thing #30's rename discards and RUN.txt keeps:
        # which HOST produced that leg, .gui for the GUI and .cli for the
        # headless pipeline.
        lines.append(f"Produced by a {point.tag.lstrip('.')} run.")
    if point.resumed_by_last:
        lines.append("The previous run in this case started from here — pick it "
                     "to run the same leg again.")
    return "\n".join(lines)


class _Row(QRadioButton):
    """A chooser row that ELIDES instead of being clipped.

    A ``QRadioButton`` neither wraps nor elides: text past its width simply is
    not drawn, and the panel that hosts these has horizontal scrolling off
    (``solver_config_panel.py``), so the remainder is unreachable — the reported
    defect. :func:`_row_text` buys back enough width for the normal case; this
    is the backstop for a sidebar dragged narrower still.

    Two overrides, and both are needed for a different reason:

    * ``minimumSizeHint`` stops advertising the full text's width. Without it
      the row would force the enclosing ``QScrollArea``'s content wider than the
      viewport, which is the very state that produces unreachable text — the
      widget must be willing to be narrow before eliding it means anything.
    * ``resizeEvent`` re-elides to the width actually granted. The FULL text
      stays in ``full_text`` and in the tooltip, so nothing is lost — an
      ellipsis says there is more, where a clip pretends the row ended.
    """

    #: Room for the indicator, its spacing and the focus rect. Measured rather
    #: than guessed: it is the widget's own hint for empty text.
    def __init__(self, text: str, parent=None, marked: bool = False):
        super().__init__("", parent)
        self.full_text = text
        self._chrome = super().sizeHint().width()
        self.setText(text)
        # The mark is WEIGHT as well as words, and that is not decoration. The
        # words "← last run" sit at the END of the row, so they are the first
        # thing elided on a narrow sidebar — i.e. the one signal #31 exists to
        # give ("re-run the same leg") would be the first casualty of the fix
        # for the row being too wide. Bold survives any width.
        if marked:
            font = self.font()
            font.setBold(True)
            self.setFont(font)

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        # Enough for the indicator plus a few characters, so the row stays
        # recognisable as a row; the rest is the elide's business.
        fm = QFontMetrics(self.font())
        hint.setWidth(self._chrome + fm.horizontalAdvance("mmmmmmmm"))
        return hint

    def resizeEvent(self, event):
        super().resizeEvent(event)
        fm = QFontMetrics(self.font())
        room = max(0, self.width() - self._chrome)
        shown = fm.elidedText(self.full_text, Qt.TextElideMode.ElideRight, room)
        if shown != self.text():
            self.setText(shown)


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
            btn = _Row(_row_text(point), marked=point.resumed_by_last)
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
