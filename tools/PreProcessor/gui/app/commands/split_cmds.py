import numpy as np
from app.commands.base import BaseCommand


class AddSplitCmd(BaseCommand):
    """Add a split point at the given index."""

    def __init__(self, session, idx: int, sync_cb, refresh_cb):
        self.session = session
        self.idx = idx
        self.sync_cb = sync_cb        # lightweight: update list + canvas markers
        self.refresh_cb = refresh_cb  # full: re-draw geometry

    def description(self) -> str:
        return f"Add Breakpoint at index {self.idx}"

    def execute(self):
        if self.idx not in self.session.split_indices:
            self.session.split_indices.append(self.idx)
            self.session.split_indices.sort()
        self.sync_cb()

    def undo(self):
        if self.idx in self.session.split_indices:
            self.session.split_indices.remove(self.idx)
        self.sync_cb()


class RemoveSplitCmd(BaseCommand):
    """Remove a split point, optionally deleting the vertex from the geometry."""

    def __init__(self, session, idx: int, keep_vertex: bool, sync_cb, refresh_cb):
        self.session = session
        self.idx = idx
        self.keep_vertex = keep_vertex
        self.sync_cb = sync_cb
        self.refresh_cb = refresh_cb

        # Snapshot state for undo
        self._old_split = list(session.split_indices)
        self._old_pts = (session.original_points.copy()
                         if session.original_points is not None else None)
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        return f"Remove Breakpoint at index {self.idx}"

    def execute(self):
        if self.keep_vertex:
            if self.idx in self.session.split_indices:
                self.session.split_indices.remove(self.idx)
            self.sync_cb()
        else:
            if self.idx in self.session.split_indices:
                self.session.split_indices.remove(self.idx)
            # Shift indices above the removed vertex
            self.session.split_indices = [
                s - 1 if s > self.idx else s
                for s in self.session.split_indices
            ]
            self.session.original_points = np.delete(
                self.session.original_points, self.idx, axis=0)
            self.session.is_geometry_modified = True
            self.refresh_cb()

    def undo(self):
        self.session.split_indices = list(self._old_split)
        if not self.keep_vertex and self._old_pts is not None:
            self.session.original_points = self._old_pts.copy()
        self.session.is_geometry_modified = self._old_modified
        self.refresh_cb()


class AutoDetectSplitCmd(BaseCommand):
    """Auto detect split points and replace the current split indices."""

    def __init__(self, session, new_indices: list[int], refresh_cb):
        self.session = session
        self.new_indices = new_indices
        self.refresh_cb = refresh_cb
        self._old_split = list(session.split_indices)
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        return "Auto Detect Breakpoints"

    def execute(self):
        self.session.split_indices = list(self.new_indices)
        self.session.is_geometry_modified = True
        self.refresh_cb()

    def undo(self):
        self.session.split_indices = list(self._old_split)
        self.session.is_geometry_modified = self._old_modified
        self.refresh_cb()
