"""Undoable project-level configuration edits (Mesh / Solver / Immersed Solid).

Before this existed, undo covered only CAD geometry: every Mesh, Solver, BC and IB
edit was unreachable by Ctrl+Z even though the user's mental model is one global
undo. A mis-set domain box or a wrong BC assignment had to be spotted and typed
back by hand.

Snapshot-based, like :class:`UpdateSegmentStateCmd`: the whole configuration state
is captured before and after, and undo/redo just re-applies the relevant side.
That is deliberate — the alternative (a command per field) would need one class
per knob across three config models, and could not represent an edit that touches
several fields at once, which is exactly what a burst of panel edits is.
"""
from __future__ import annotations

import copy

from app.commands.base import BaseCommand


class UpdateProjectStateCmd(BaseCommand):
    """Restore the Mesh / Solver / IB configuration to a captured snapshot.

    ``before``/``after`` are the dicts produced by
    ``AppController._project_config_state()``; both sides are deep-copied so a
    later panel edit cannot mutate a stored snapshot through a shared sub-dict
    (``geom_roles``/``group_bc``/``bc_definitions`` are all nested containers).

    ``label`` names the edit for the log and the undo tooltip. It is computed by
    the recorder from which sections actually differ, so the user reads "Mesh
    settings" rather than an opaque class name.
    """

    def __init__(self, controller, before: dict, after: dict, label: str):
        self.controller = controller
        self.before = copy.deepcopy(before)
        self.after = copy.deepcopy(after)
        self.label = label

    def _apply(self, state: dict):
        # Route through the controller so the panels are refreshed the same way a
        # workspace load refreshes them — an undo that changed the model but not
        # the visible form would be worse than no undo at all.
        self.controller._apply_project_state_for_history(state)

    def execute(self):
        self._apply(self.after)

    def undo(self):
        self._apply(self.before)

    def description(self) -> str:
        return self.label
