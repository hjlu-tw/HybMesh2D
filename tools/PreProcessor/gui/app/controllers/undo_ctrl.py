"""Global undo/redo for AppController, plus the recorder that brings project-level
(Mesh / Solver / Immersed Solid) edits into it.

Two problems this fixes:

1. **Undo was per-CAD-tab.** The stack lived on ``GeometrySession``, so switching
   tabs silently switched history, and Ctrl+Z could not reach the edit the user had
   just made in another tab. Histories stay per-session (that is what makes closing
   a tab drop exactly its own commands, with no dangling references), but every
   command now carries a global sequence number and undo/redo pick the genuinely
   most recent action across ALL histories. When that action belongs to another
   tab, the tab is brought to the front first — undoing something the user cannot
   see is worse than not undoing at all.

2. **Mesh/Solver/IB edits were not undoable at all.** They are recorded by
   snapshot diffing (:class:`UpdateProjectStateCmd`) on a short debounce, so a
   burst of typing in the mesh panel becomes ONE undo step rather than one per
   keystroke — "undo my last change", not "undo one digit". Diffing also means a
   spurious change signal (Qt fires ``valueChanged`` on programmatic
   ``set_config`` too) costs nothing: with no real difference, nothing is recorded.
"""
from __future__ import annotations

from contextlib import contextmanager

from PyQt6.QtCore import QTimer

from app.commands.config_cmds import UpdateProjectStateCmd
from app.models.session import GeometrySession
from app.services.logging_setup import get_logger

_log = get_logger(__name__)

# Debounce for coalescing a burst of panel edits into one undo step. Long enough
# to cover typing a number and tabbing on, short enough that Ctrl+Z right after an
# edit already sees it.
_SNAPSHOT_DEBOUNCE_MS = 600

# The project-state sections that are user *input* and therefore undoable.
# Deliberately excludes the artefact paths that _collect_project_state() also
# carries (vtk_path / result_path): those are outputs of running a stage, and
# "undoing" a mesh generation is not a thing.
_UNDOABLE_SECTIONS = ("mesh_config", "solver_config", "stl3d_config")

_SECTION_LABELS = {
    "mesh_config": "Mesh settings",
    "solver_config": "Solver settings",
    "stl3d_config": "Immersed-solid settings",
}


class UndoControllerMixin:
    # ── project-state snapshots ───────────────────────────────────────────
    def _project_config_state(self) -> dict:
        """The undoable subset of the project state (no generated artefacts)."""
        full = self._collect_project_state()
        return {k: full[k] for k in _UNDOABLE_SECTIONS if k in full}

    def _apply_project_state_for_history(self, state: dict):
        """Apply a snapshot from undo/redo, without re-recording it."""
        with self.suppress_project_undo():
            self._apply_project_state(state)

    @contextmanager
    def suppress_project_undo(self):
        """Push configuration into the panels WITHOUT recording an undo step.

        Every programmatic push — undo/redo itself, entering the Mesh stage,
        loading a workspace or pipeline script, resetting state — calls
        ``set_config`` on the panels, which fires the very signals the recorder
        listens to. Un-suppressed, an undo would immediately re-record itself, and
        loading a file would look like a user edit.

        On exit the pending burst is dropped, so nothing from inside the block can
        be attributed to the user.
        """
        prev = getattr(self, "_suppress_project_undo", False)
        self._suppress_project_undo = True
        try:
            yield
        finally:
            self._suppress_project_undo = prev
            if not prev:
                timer = getattr(self, "_snapshot_timer", None)
                if timer is not None:
                    timer.stop()
                self._project_undo_before = None
                # What we just pushed IS the new reference, so the next user edit
                # is measured from it rather than from a pre-push state.
                self.note_project_state_committed()

    def push_panel_config(self, panel, cfg):
        """``panel.set_config(cfg)`` as a programmatic push, not a user edit.

        The single funnel for pushing configuration into the Mesh / Solver / IB
        panels. Only the IB panel blocks its own signals during population; the
        other two let ``valueChanged`` through, so without this every stage entry
        and file load would land on the undo stack as if the user had typed it.

        Going through one helper (rather than 17 hand-written ``with`` blocks) also
        means a future call site that forgets it merely records a spurious step —
        it cannot corrupt the baseline.
        """
        if panel is None:
            return
        with self.suppress_project_undo():
            panel.set_config(cfg)

    # ── recording ────────────────────────────────────────────────────────
    def init_project_undo(self):
        """Start tracking project-level edits. Called once, after the panels exist."""
        self._suppress_project_undo = False
        # `before` is captured at the START of an editing burst, not held from
        # startup: any programmatic set_config in between would otherwise leave a
        # stale snapshot, and undo would jump back to a state the user never saw
        # (e.g. the panel's un-populated widget defaults).
        self._project_undo_before = None
        self._snapshot_timer = QTimer(self.main_window)
        self._snapshot_timer.setSingleShot(True)
        self._snapshot_timer.timeout.connect(self.flush_project_snapshot)

    def _wire_project_undo_signals(self):
        """Route every project-panel edit into the snapshot recorder.

        All three panels get their input widgets wired generically. Their own
        panel-level signals are NOT sufficient: ``mesh_config_changed`` fires for
        structural actions (geometry list, roles, BC) but not for a plain spin-box
        edit, and the solver panel has no such signal at all — so a domain box or
        an iteration count typed by the user would silently escape undo. Widget
        introspection also keeps new fields covered automatically.

        The panel signals are connected too, because they cover structural changes
        that no single input widget represents.

        Over-triggering is harmless: the recorder diffs, so a signal with no real
        change records nothing, and programmatic pushes go through
        :meth:`push_panel_config`, which suppresses recording outright.
        """
        mw = self.main_window
        for panel_attr, signal_name in (("mesh_config_panel", "mesh_config_changed"),
                                        ("stl3d_config_panel", "config_changed")):
            panel = getattr(mw, panel_attr, None)
            sig = getattr(panel, signal_name, None) if panel is not None else None
            if sig is not None:
                sig.connect(lambda *_a: self.schedule_project_snapshot())

        for panel_attr in ("mesh_config_panel", "solver_config_panel",
                           "stl3d_config_panel"):
            panel = getattr(mw, panel_attr, None)
            if panel is not None:
                self._wire_widget_edits(panel)

    def _wire_widget_edits(self, root):
        """Connect the 'user changed me' signal of every input widget under root."""
        from PyQt6.QtWidgets import (
            QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit, QPlainTextEdit,
        )
        slot = lambda *_a: self.schedule_project_snapshot()  # noqa: E731
        for w in root.findChildren(QAbstractSpinBox):
            sig = getattr(w, "valueChanged", None)
            if sig is not None:
                sig.connect(slot)
        for w in root.findChildren(QComboBox):
            w.currentIndexChanged.connect(slot)
        for w in root.findChildren(QAbstractButton):
            # Fires only for checkable buttons (checkbox / radio); a plain
            # QPushButton simply never emits it.
            w.toggled.connect(slot)
        for w in root.findChildren(QLineEdit):
            # textEdited, not textChanged: only user typing, never set_config().
            w.textEdited.connect(slot)
        for w in root.findChildren(QPlainTextEdit):
            w.textChanged.connect(slot)

    def schedule_project_snapshot(self):
        """Note that a project panel changed; record it once the burst settles."""
        if getattr(self, "_suppress_project_undo", False):
            return
        timer = getattr(self, "_snapshot_timer", None)
        if timer is None:
            return
        if self._project_undo_before is None:
            # Start of a burst. The baseline must be the state BEFORE this edit,
            # and by the time Qt delivers the signal the edited widget already
            # holds its new value — so read the last committed reference (updated
            # after every programmatic push and after every flush) rather than the
            # panels. The fresh read is only a fallback for the very first edit of
            # a session, where nothing has been committed yet.
            self._project_undo_before = getattr(
                self, "_project_undo_committed", None) or self._project_config_state()
        timer.start(_SNAPSHOT_DEBOUNCE_MS)

    def note_project_state_committed(self):
        """Record the current panel state as the reference for the next edit.

        Called after every programmatic push (stage entry, file load, undo) so the
        next user edit is measured from what is actually on screen.
        """
        try:
            self._project_undo_committed = self._project_config_state()
        except Exception:
            _log.debug("could not capture the project-state reference",
                       exc_info=True)
            self._project_undo_committed = None

    def flush_project_snapshot(self) -> bool:
        """Record one command if the project config changed. True if recorded.

        Called by the debounce timer, and directly before anything that must not
        lose a pending edit (undo/redo, saving, running a stage).
        """
        if getattr(self, "_suppress_project_undo", False):
            return False
        before = getattr(self, "_project_undo_before", None)
        self._project_undo_before = None
        if before is None:
            return False
        try:
            after = self._project_config_state()
        except Exception:
            _log.warning("could not snapshot the project state for undo",
                         exc_info=True)
            return False
        self._project_undo_committed = after
        if after == before:
            return False

        changed = [_SECTION_LABELS[k] for k in _UNDOABLE_SECTIONS
                   if before.get(k) != after.get(k)]
        label = " + ".join(changed) if changed else "Project settings"
        # record(), not execute(): the panels already hold `after`.
        self.project_history.record(
            UpdateProjectStateCmd(self, before, after, label))
        return True

    # ── the participating histories ──────────────────────────────────────
    def _all_histories(self) -> list:
        """``(label, history, session_or_None)`` for every undo stack in play."""
        out = [(f"'{s.display_name.lstrip('*')}'", s.command_history, s)
               for s in self.sessions]
        out.append(("project settings", self.project_history, None))
        return out

    # ── undo / redo ──────────────────────────────────────────────────────
    def undo(self):
        # A still-pending panel edit has to become a command before we pop, or
        # Ctrl+Z right after typing would skip past it to an older action.
        self.flush_project_snapshot()
        best = None
        for label, hist, session in self._all_histories():
            seq = hist.peek_undo_seq()
            if seq is not None and (best is None or seq > best[0]):
                best = (seq, label, hist, session)
        self._run_history_step(best, "Undo")

    def redo(self):
        self.flush_project_snapshot()
        best = None
        for label, hist, session in self._all_histories():
            seq = hist.peek_redo_seq()
            # Redo must mirror undo: the LAST thing undone is the first thing
            # redone, and undo always took the highest sequence — so the next
            # redo is the LOWEST sequence waiting on any redo stack.
            if seq is not None and (best is None or seq < best[0]):
                best = (seq, label, hist, session)
        self._run_history_step(best, "Redo")

    def _run_history_step(self, best, verb: str):
        if best is None:
            self.main_window.log_panel.log(f"Nothing to {verb.lower()}.")
            self._update_undo_redo_buttons()
            return
        _seq, label, hist, session = best
        # Show the user what is about to change: a CAD edit in a background tab
        # gets that tab raised first.
        if session is not None and session is not self.active_session():
            idx = self.sessions.index(session)
            self.main_window.tab_widget.setCurrentIndex(idx)
            self.switch_tab(idx)
        cmd = hist.undo() if verb == "Undo" else hist.redo()
        if cmd is None:                     # raced away; nothing applied
            self._update_undo_redo_buttons()
            return
        self.main_window.log_panel.log(f"{verb} ({cmd.description()}) — {label}")
        if session is not None:
            self._after_session_history_change(session)
        self._update_undo_redo_buttons()

    def _after_session_history_change(self, session: GeometrySession):
        """Post-command bookkeeping for a CAD-scope undo/redo."""
        self._sync_geometry_list()
        self.redraw_canvas(announce=False)   # leave no stray highlight/handle
        # Reseed the edit baseline so the next in-place form edit diffs against
        # the restored state. to_dict() already returns a fresh dict.
        if session.current_segment_idx >= 0:
            seg = session.project_model.get_segment(session.current_segment_idx)
            if seg:
                session.segment_state_snapshot = seg.to_dict()

    def _update_undo_redo_buttons(self, session: GeometrySession = None):
        """Enable/disable the toolbar buttons from ALL histories.

        ``session`` is accepted and ignored: it is what ``CommandHistory.on_change``
        passes, and with a global stack the answer no longer depends on which
        session changed.
        """
        can_undo = can_redo = False
        for _label, hist, _s in self._all_histories():
            can_undo = can_undo or hist.can_undo
            can_redo = can_redo or hist.can_redo
        self.main_window.undo_btn.setEnabled(can_undo)
        self.main_window.redo_btn.setEnabled(can_redo)
