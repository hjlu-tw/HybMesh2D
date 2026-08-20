from __future__ import annotations
import itertools
from abc import ABC, abstractmethod
from collections import deque

# Monotonic stamp applied to every command as it is pushed. Undo/redo spans
# SEVERAL histories — one per CAD session plus one for project-level settings —
# and the user's mental model is a single chronological Ctrl+Z, not "whatever the
# focused tab did last". The stamp is what lets the controller pop the genuinely
# most recent action across all of them (see controllers/undo_ctrl.py).
_seq_counter = itertools.count(1)


def next_seq() -> int:
    """The next global command sequence number."""
    return next(_seq_counter)


class BaseCommand(ABC):
    """Abstract base for all undoable operations."""

    #: Global push order, assigned by CommandHistory._push. Compared across
    #: histories so undo/redo follow real chronology rather than tab focus.
    seq: int = 0

    @abstractmethod
    def execute(self):
        ...

    @abstractmethod
    def undo(self):
        ...

    def description(self) -> str:
        """Return a human-readable description of this command."""
        return self.__class__.__name__


class CommandHistory:
    """Manages undo/redo stacks for a single GeometrySession."""

    MAX_DEPTH = 50

    def __init__(self):
        self._undo_stack: deque[BaseCommand] = deque(maxlen=self.MAX_DEPTH)
        self._redo_stack: deque[BaseCommand] = deque(maxlen=self.MAX_DEPTH)
        # Optional callback fired whenever the stacks change, so the UI can keep
        # the undo/redo buttons in sync no matter which dispatch path ran.
        self.on_change = None

    def _notify(self):
        if self.on_change is not None:
            self.on_change()

    def execute(self, cmd: BaseCommand):
        """Execute a command and push it onto the undo stack."""
        cmd.execute()
        self._push(cmd)

    def record(self, cmd: BaseCommand):
        """Record a command without executing it (already applied)."""
        self._push(cmd)

    def _push(self, cmd: BaseCommand):
        # Stamp on push, not on construction: a command may be built and then
        # discarded (a no-op edit), and only the ones that actually enter a
        # history take part in the cross-history ordering.
        cmd.seq = next_seq()
        self._undo_stack.append(cmd)
        self._redo_stack.clear()
        self._notify()

    def peek_undo_seq(self) -> int | None:
        """Sequence number of the command undo() would pop, else None."""
        return getattr(self._undo_stack[-1], "seq", None) if self._undo_stack else None

    def peek_redo_seq(self) -> int | None:
        """Sequence number of the command redo() would re-apply, else None."""
        return getattr(self._redo_stack[-1], "seq", None) if self._redo_stack else None

    def undo(self) -> BaseCommand | None:
        if not self._undo_stack:
            return None
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        self._notify()
        return cmd

    def redo(self) -> BaseCommand | None:
        if not self._redo_stack:
            return None
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
        self._notify()
        return cmd

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._notify()

