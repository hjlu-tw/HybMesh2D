from __future__ import annotations
import numpy as np

from app.commands.base import BaseCommand


class StitchCmd(BaseCommand):
    """Close detected open gaps by replacing the file polyline points.

    Dialog-driven (from the Preview unclosed-points prompt): the chosen stitch
    method has already produced ``new_points``; this command just swaps them in
    and restores ``old_points`` on undo.
    """

    def __init__(self, session, old_points: np.ndarray, new_points: np.ndarray,
                 refresh_cb=None):
        self.session = session
        self.old_points = np.array(old_points, copy=True)
        self.new_points = np.array(new_points, copy=True)
        self.refresh_cb = refresh_cb
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        return "Stitch unclosed points"

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
