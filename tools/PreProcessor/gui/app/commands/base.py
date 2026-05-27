from __future__ import annotations
from abc import ABC, abstractmethod
from collections import deque


class BaseCommand(ABC):
    """Abstract base for all undoable operations."""

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
        self._redo_stack: deque[BaseCommand] = deque()

    def execute(self, cmd: BaseCommand):
        """Execute a command and push it onto the undo stack."""
        cmd.execute()
        self._undo_stack.append(cmd)
        self._redo_stack.clear()

    def undo(self) -> BaseCommand | None:
        if not self._undo_stack:
            return None
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        return cmd

    def redo(self) -> BaseCommand | None:
        if not self._redo_stack:
            return None
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
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

