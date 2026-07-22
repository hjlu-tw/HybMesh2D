import numpy as np
from app.commands.base import BaseCommand
from app.commands.segment_cmds import _snapshot_full_state, _restore_full_state


class JoinEdgesToPolygonCmd(BaseCommand):
    """Merge several edges (curve and/or discrete file) into one polygon edge
    (atomic, undoable).

    The controller validated connectivity and built the polygon (its vertices
    already capture the joined points). This command drops the joined segments,
    removes any consumed file-segment points from original_points — preserving
    boundary indices still shared with UNSELECTED file segments — then
    regenerates the remaining file segments. Undo restores the whole state
    wholesale (mirroring AddCurveSegmentCmd)."""

    def __init__(self, session, remove_indices, polygon_seg, refresh_cb, select_cb):
        self.session = session
        self.remove_indices = set(remove_indices)
        self.polygon_seg = polygon_seg
        self.refresh_cb = refresh_cb
        self.select_cb = select_cb
        self._snap = _snapshot_full_state(session)
        self._added_idx = -1

    def description(self) -> str:
        return "Join Edges into Polygon"

    def execute(self):
        pm = self.session.project_model
        segs = pm.segments
        remove_segs = [s for i, s in enumerate(segs) if i in self.remove_indices]

        # Drop the joined file segments' points from original_points, keeping any
        # boundary index an UNSELECTED file segment still needs (shared split).
        gp = self.session.original_points
        file_removed = [s for s in remove_segs if s.type == "file"]
        if gp is not None and len(gp) and file_removed:
            keep_needed = {i for s in segs if s.type == "file" and s not in remove_segs
                           for i in (s.start_index, s.end_index)}
            consumed = set()
            for s in file_removed:
                a, b = sorted((s.start_index, s.end_index))
                consumed.update(range(a, b + 1))
            consumed -= keep_needed
            keep = [i for i in range(len(gp)) if i not in consumed]
            remap = {old: new for new, old in enumerate(keep)}
            self.session.original_points = (gp[keep] if keep
                                            else np.empty((0, 2), dtype=float))
            self.session.split_indices = sorted(
                {remap[i] for i in self.session.split_indices if i in remap})
            # Surviving (unselected) file segments still carry their PRE-removal
            # start/end indices. Remap them to the new numbering too, so
            # update_file_segments_from_indices can match them by (start, end) and
            # preserve their per-segment settings (strategy / BC / spacing) —
            # otherwise an untouched edge silently reverts to defaults.
            for s in segs:
                if (s.type == "file" and s not in remove_segs
                        and s.start_index in remap and s.end_index in remap):
                    s.start_index = remap[s.start_index]
                    s.end_index = remap[s.end_index]

        # Swap the joined segments for the polygon, then regenerate the remaining
        # file segments from the (remapped) split indices — this preserves every
        # curve segment (including the new polygon).
        pm.segments = [s for i, s in enumerate(segs)
                       if i not in self.remove_indices] + [self.polygon_seg]
        pm.update_file_segments_from_indices(
            self.session.split_indices, points=self.session.original_points)
        if self.polygon_seg.id >= pm._next_curve_id:
            pm._next_curve_id = self.polygon_seg.id + 1
        self.session.is_geometry_modified = True
        self.refresh_cb()
        try:
            self._added_idx = pm.segments.index(self.polygon_seg)
            self.select_cb(self._added_idx)
        except ValueError:
            self._added_idx = -1

    def undo(self):
        _restore_full_state(self.session, self._snap)
        self.refresh_cb()
        segs = self.session.project_model.segments
        self.select_cb(max(0, min(self._added_idx - 1, len(segs) - 1)) if segs else -1)
