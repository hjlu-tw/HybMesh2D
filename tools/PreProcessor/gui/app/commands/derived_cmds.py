"""Undo for a geometry that was RE-DERIVED from its source (#152).

Regenerating an offset replaces three things at once — the point array, the split
indices and the file segments — because the offset mirrors its source's
segmentation and the source may have gained or lost points since. Three separate
edits would be three undo steps for one action the user took once, so this
snapshots all three and puts them back together.

It does NOT snapshot the derived-geometry record itself: regeneration never
changes where a geometry came from, only what it currently is.
"""
from __future__ import annotations

import copy

from app.commands.base import BaseCommand


class RegenerateOffsetCmd(BaseCommand):
    """Replace a derived geometry's points and segmentation, undoably."""

    def __init__(self, session, points, split_indices, segments, refresh_cb):
        self.session = session
        self._new_points = points
        self._new_splits = list(split_indices)
        self._new_segments = segments
        self._refresh = refresh_cb
        self._old_points = None
        self._old_splits: list = []
        self._old_segments: list = []

    def execute(self):
        pm = self.session.project_model
        self._old_points = (None if self.session.original_points is None
                            else self.session.original_points.copy())
        self._old_splits = list(self.session.split_indices)
        self._old_segments = copy.deepcopy(pm.segments)
        self.session.original_points = self._new_points
        self.session.split_indices = list(self._new_splits)
        pm.segments = copy.deepcopy(self._new_segments)
        pm.renumber_segments()
        self.session.mark_modified()
        if self._refresh:
            self._refresh()

    def undo(self):
        pm = self.session.project_model
        self.session.original_points = self._old_points
        self.session.split_indices = list(self._old_splits)
        pm.segments = copy.deepcopy(self._old_segments)
        if self._refresh:
            self._refresh()

    def description(self) -> str:
        return "Regenerate offset geometry"
