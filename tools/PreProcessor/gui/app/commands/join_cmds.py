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


class KeepSeparateAndCloseCmd(BaseCommand):
    """KEEP-mode join: keep the selected edges as SEPARATE, individually
    selectable and vertex-editable segments (each retaining its own per-segment
    BC), only welding their near-coincident shared endpoints so the chain is
    watertight, and marking the project boundary closed so the gold dashed
    closing edge is drawn and the open-endpoint warnings clear.

    Contrast :class:`JoinEdgesToPolygonCmd`, which collapses every selected edge
    into ONE polygon curve (a single BC, no per-vertex selection). This command
    changes no segment membership — only the welded curve endpoints and the
    project-level closure — so a discrete edge keeps its clickable points and a
    line/arc keeps its own identity in the model tree."""

    def __init__(self, session, edge_indices, closed, tol, refresh_cb):
        self.session = session
        self.edge_indices = list(edge_indices)
        self.closed = bool(closed)
        self.tol = tol
        self.refresh_cb = refresh_cb
        self._snap = _snapshot_full_state(session)   # captures welded params for undo
        pm = session.project_model
        self._old_mode = pm.closed_mode
        self._old_is_closed = pm.is_closed

    def description(self) -> str:
        return "Join / Close Edges (keep separate)"

    def execute(self):
        from app.services.geometry_service import GeometryService
        pm = self.session.project_model
        curve_segs = [pm.get_segment(i) for i in self.edge_indices]
        curve_segs = [s for s in curve_segs if s is not None and s.type == "curve"]
        if curve_segs:
            GeometryService.weld_boundary_endpoints(curve_segs, self.tol)
        pm.closed_mode = "closed" if self.closed else "open"
        pm.resolve_closure(self.session.original_points)
        self.session.is_geometry_modified = True
        self.refresh_cb()

    def undo(self):
        _restore_full_state(self.session, self._snap)
        pm = self.session.project_model
        pm.closed_mode = self._old_mode
        pm.is_closed = self._old_is_closed
        self.refresh_cb()
