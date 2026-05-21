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
