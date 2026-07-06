import numpy as np
from app.commands.base import BaseCommand


class InsertVertexCmd(BaseCommand):
    """Insert a new vertex into the geometry and auto-split at that index."""

    def __init__(self, session, insert_idx: int, point: np.ndarray,
                 old_split_indices: list, refresh_cb):
        self.session = session
        self.insert_idx = insert_idx
        self.point = point.copy()
        self.old_split = list(old_split_indices)
        self.refresh_cb = refresh_cb

        # Snapshot of original points before insertion (for undo/redo)
        self._base_pts = session.original_points.copy()
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        return f"Insert Vertex at index {self.insert_idx}"

    def execute(self):
        # Apply insertion to the snapshot so redo is idempotent
        self.session.original_points = np.insert(
            self._base_pts.copy(), self.insert_idx, self.point, axis=0)

        # Update split indices
        new_splits = []
        for s in self.old_split:
            new_splits.append(s + 1 if s >= self.insert_idx else s)
        if self.insert_idx not in new_splits:
            new_splits.append(self.insert_idx)
        self.session.split_indices = sorted(set(new_splits))
        self.session.is_geometry_modified = True
        self.refresh_cb()

    def undo(self):
        self.session.original_points = self._base_pts.copy()
        self.session.split_indices = list(self.old_split)
        self.session.is_geometry_modified = self._old_modified
        self.refresh_cb()


class ReplacePointsCmd(BaseCommand):
    """Undoably swap the session's ``original_points`` between two point arrays.

    Base for any edit that has already computed the full new point layout and
    just needs it made undoable (CAD corner-drag edits, endpoint stitching).
    Subclasses only differ by their ``description()`` label.
    """

    def __init__(self, session, old_points: np.ndarray, new_points: np.ndarray,
                 refresh_cb=None, label: str = "Edit geometry"):
        self.session = session
        self.old_points = np.array(old_points, copy=True)
        self.new_points = np.array(new_points, copy=True)
        self.refresh_cb = refresh_cb
        self._label = label
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        return self._label

    def execute(self):
        self.session.original_points = np.array(self.new_points, copy=True)
        self.session.is_geometry_modified = True
        if self.refresh_cb:
            self.refresh_cb()

    def undo(self):
        self.session.original_points = np.array(self.old_points, copy=True)
        self.session.is_geometry_modified = self._old_modified
        if self.refresh_cb:
            self.refresh_cb()


class ReplaceGeometryPointsCmd(ReplacePointsCmd):
    """Replace ``original_points`` wholesale for an in-place CAD-style edit
    (dragging a discrete edge's corner vertices)."""

    def __init__(self, session, old_points: np.ndarray, new_points: np.ndarray,
                 refresh_cb=None, label: str = "Edit geometry shape"):
        super().__init__(session, old_points, new_points, refresh_cb, label)
