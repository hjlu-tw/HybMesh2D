from __future__ import annotations
import numpy as np

from app.commands.vertex_cmds import ReplacePointsCmd


class StitchCmd(ReplacePointsCmd):
    """Close detected open gaps by replacing the file polyline points.

    Dialog-driven (from the Preview unclosed-points prompt): the chosen stitch
    method has already produced ``new_points``; this command just swaps them in
    and restores ``old_points`` on undo (see :class:`ReplacePointsCmd`).
    """

    def __init__(self, session, old_points: np.ndarray, new_points: np.ndarray,
                 refresh_cb=None):
        super().__init__(session, old_points, new_points, refresh_cb,
                         label="Stitch unclosed points")
