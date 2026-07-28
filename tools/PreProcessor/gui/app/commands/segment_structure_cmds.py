import copy
from app.commands.base import BaseCommand
from app.services.index_helpers import remove_points_and_adjust_indices
from app.commands.segment_cmds_core import (
    _snapshot_full_state, _restore_full_state,
)


class RemoveSegmentCmd(BaseCommand):
    """Remove a segment (file or curve) from the project, deleting points if discrete."""

    def __init__(self, session, seg_idx: int, refresh_cb):
        self.session = session
        self.seg_idx = seg_idx
        self.refresh_cb = refresh_cb

        seg = session.project_model.get_segment(seg_idx)
        self.removed_seg = copy.deepcopy(seg) if seg else None
        self._snap = _snapshot_full_state(session)

    def description(self) -> str:
        seg_id = self.removed_seg.id if self.removed_seg else "?"
        return f"Remove Edge {seg_id}"

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if not seg:
            return

        if seg.type == "file":
            remove_points_and_adjust_indices(self.session, seg)

        # Remove segment from project
        self.session.project_model.remove_segment(self.seg_idx)
        self.session.is_geometry_modified = True
        self.refresh_cb()

    def undo(self):
        _restore_full_state(self.session, self._snap)
        self.refresh_cb()


class AddCurveSegmentCmd(BaseCommand):
    """Add a new curve segment (either blank or pre-configured/duplicated)."""

    def __init__(self, session, refresh_cb, select_cb, preconfigured_seg=None):
        self.session = session
        self.refresh_cb = refresh_cb
        self.select_cb = select_cb
        self.added_seg = preconfigured_seg
        # Full pre-add snapshot so undo restores the whole state wholesale rather
        # than removing the segment by object identity — the latter silently
        # no-ops once any *other* command's undo has deep-copied the segment
        # list (leaving an undeletable phantom edge behind).
        self._snap = _snapshot_full_state(session)
        self._added_idx = -1

    def description(self) -> str:
        seg_id = self.added_seg.id if self.added_seg else "?"
        return f"Add Analytic Edge {seg_id}"

    def execute(self):
        pm = self.session.project_model
        if self.added_seg is None:
            # Create a new blank curve segment
            self.added_seg = pm.add_curve_segment()
        else:
            # Re-add the existing preconfigured/duplicated segment. Rebuild the
            # list (rather than append in place) so a redo can never mutate the
            # deep-copied snapshot a sibling command may be holding.
            pm.segments = pm.segments + [self.added_seg]
            if self.added_seg.id >= pm._next_curve_id:
                pm._next_curve_id = self.added_seg.id + 1

        self.session.is_geometry_modified = True
        self.refresh_cb()
        try:
            self._added_idx = pm.segments.index(self.added_seg)
            self.select_cb(self._added_idx)
        except ValueError:
            self._added_idx = -1

    def undo(self):
        _restore_full_state(self.session, self._snap)
        self.refresh_cb()
        segs = self.session.project_model.segments
        if segs:
            self.select_cb(max(0, min(self._added_idx - 1, len(segs) - 1)))
        else:
            self.select_cb(-1)


class DuplicateTransformCmd(BaseCommand):
    """Command to duplicate a segment with transform, optionally deleting the original segment."""
    def __init__(self, session, seg_idx: int, new_seg, delete_original: bool, refresh_cb, select_cb):
        self.session = session
        self.seg_idx = seg_idx
        self.new_seg = new_seg
        self.delete_original = delete_original
        self.refresh_cb = refresh_cb
        self.select_cb = select_cb

        # Snapshot state for undo
        self._snap = _snapshot_full_state(session)

    def description(self) -> str:
        snap_segs = self._snap["segments"]
        seg_id = (snap_segs[self.seg_idx].id
                  if 0 <= self.seg_idx < len(snap_segs) else "?")
        verb = "Transform" if self.delete_original else "Duplicate"
        return f"{verb} Edge {seg_id}"

    def execute(self):
        if self.delete_original:
            # 1. Remove original segment
            seg = self.session.project_model.segments[self.seg_idx]
            # If original segment is file/discrete, we must remove its unshared points from original_points
            if seg.type == "file":
                remove_points_and_adjust_indices(self.session, seg)
            # Remove segment from list
            self.session.project_model.segments.pop(self.seg_idx)

        # 2. Append new segment
        self.session.project_model.segments.append(self.new_seg)
        pm = self.session.project_model
        if self.new_seg.id >= pm._next_curve_id:
            pm._next_curve_id = self.new_seg.id + 1

        self.refresh_cb()
        try:
            idx = self.session.project_model.segments.index(self.new_seg)
            self.select_cb(idx)
        except ValueError:
            pass

    def undo(self):
        _restore_full_state(self.session, self._snap)
        self.refresh_cb()


class DuplicateMultipleTransformCmd(BaseCommand):
    """Duplicate/transform several segments at once, optionally deleting the
    originals. Each entry in ``new_segs`` is the transformed polygon curve for
    the corresponding index in ``seg_indices``."""

    def __init__(self, session, seg_indices, new_segs, delete_original,
                 refresh_cb, select_cb):
        self.session = session
        self.seg_indices = list(seg_indices)
        self.new_segs = list(new_segs)
        self.delete_original = delete_original
        self.refresh_cb = refresh_cb
        self.select_cb = select_cb

        # Snapshot full state for undo
        self._snap = _snapshot_full_state(session)

        # Capture original ids up-front for a stable description
        self._orig_ids = []
        for idx in self.seg_indices:
            seg = session.project_model.get_segment(idx)
            if seg:
                self._orig_ids.append(seg.id)

    def description(self) -> str:
        verb = "Transform" if self.delete_original else "Duplicate"
        ids = ", ".join(str(i) for i in self._orig_ids)
        return f"{verb} Edges {ids}"

    def execute(self):
        pm = self.session.project_model
        if self.delete_original:
            # Remove originals high-index-first so earlier indices stay valid.
            for idx in sorted(self.seg_indices, reverse=True):
                if idx < 0 or idx >= len(pm.segments):
                    continue
                seg = pm.segments[idx]
                if seg.type == "file":
                    remove_points_and_adjust_indices(self.session, seg)
                pm.segments.pop(idx)

        for new_seg in self.new_segs:
            pm.segments.append(new_seg)
            if new_seg.id >= pm._next_curve_id:
                pm._next_curve_id = new_seg.id + 1

        self.session.is_geometry_modified = True
        self.refresh_cb()

        # Select the last created segment so its properties are shown.
        if self.new_segs:
            try:
                idx = pm.segments.index(self.new_segs[-1])
                self.select_cb(idx)
            except ValueError:
                pass

    def undo(self):
        _restore_full_state(self.session, self._snap)
        self.refresh_cb()


class ClearGeometryCmd(BaseCommand):
    """CAD 'Clear All': drop every edge (file + curve), all points and split
    boundaries from a session, leaving a blank canvas. Fully undoable — restores
    the whole prior geometry including the closure mode/state."""

    def __init__(self, session, refresh_cb):
        self.session = session
        self.refresh_cb = refresh_cb
        pm = session.project_model
        self._snap = _snapshot_full_state(session)
        self._closed_mode = getattr(pm, "closed_mode", "auto")
        self._is_closed = getattr(pm, "is_closed", False)

    def execute(self):
        pm = self.session.project_model
        self.session.original_points = None
        self.session.split_indices = []
        self.session.selected_point_idx = None
        self.session.current_segment_idx = -1
        self.session.resampled_points = None
        pm.segments = []
        pm._next_curve_id = 1
        self.session.is_geometry_modified = True
        self.refresh_cb()

    def undo(self):
        _restore_full_state(self.session, self._snap)
        pm = self.session.project_model
        pm.closed_mode = self._closed_mode
        pm.is_closed = self._is_closed
        self.refresh_cb()

    def description(self) -> str:
        return "Clear all geometry"
