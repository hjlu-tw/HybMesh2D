from __future__ import annotations
import copy
import numpy as np

from app.commands.base import BaseCommand


class StitchCmd(BaseCommand):
    """Close / snap open boundary endpoints in one undoable step.

    A stitch may touch project-level closure (``is_closed``), the imported file
    polyline (``original_points``), and individual segments' ``closed`` flag and
    ``parameters`` (e.g. a polygon's ``vertices_str``). The full before/after of
    exactly those fields is snapshotted so undo restores the prior geometry.
    """

    def __init__(self, session, old_state: dict, new_state: dict, refresh_cb=None):
        self.session = session
        self.old_state = self._clone(old_state)
        self.new_state = self._clone(new_state)
        self.refresh_cb = refresh_cb
        self._old_modified = session.is_geometry_modified

    @staticmethod
    def _clone(state: dict) -> dict:
        s = {
            "is_closed": state.get("is_closed"),
            "segments": copy.deepcopy(state.get("segments", {})),
        }
        op = state.get("original_points")
        s["original_points"] = None if op is None else np.array(op, copy=True)
        return s

    def description(self) -> str:
        return "Stitch open endpoints"

    def _apply(self, state: dict):
        pm = self.session.project_model
        if state.get("is_closed") is not None:
            pm.is_closed = state["is_closed"]
        op = state.get("original_points")
        if op is not None:
            self.session.original_points = np.array(op, copy=True)
        for idx, seg_state in state.get("segments", {}).items():
            seg = pm.get_segment(idx)
            if seg is None:
                continue
            if "closed" in seg_state:
                seg.closed = seg_state["closed"]
            if "parameters" in seg_state:
                seg.parameters = copy.deepcopy(seg_state["parameters"])

    def execute(self):
        self._apply(self.new_state)
        self.session.is_geometry_modified = True
        if self.refresh_cb:
            self.refresh_cb()

    def undo(self):
        self._apply(self.old_state)
        self.session.is_geometry_modified = self._old_modified
        if self.refresh_cb:
            self.refresh_cb()
