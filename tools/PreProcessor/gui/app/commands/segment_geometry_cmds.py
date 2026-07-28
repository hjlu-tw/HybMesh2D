import logging
import numpy as np
from app.commands.base import BaseCommand
from app.services.geometry_service import GeometryService
from app.commands.segment_cmds_core import (
    _snapshot_full_state, _restore_full_state,
)

_log = logging.getLogger(__name__)


class CreateSegmentsFromIndicesCmd(BaseCommand):
    """Create new segments from split indices for a selected segment.

    For file segments: updates split indices within the segment range.
    For curve segments: generates points, adds them to original_points,
    and creates file segments referencing the new points.
    """

    def __init__(self, session, seg_idx: int, split_indices: list[int], refresh_cb):
        self.session = session
        self.seg_idx = seg_idx
        self.split_indices = split_indices
        self.refresh_cb = refresh_cb

        self.old_seg = session.project_model.get_segment(seg_idx)
        self._snap = _snapshot_full_state(session)

        # Store old segment index range for file segments
        self._old_start = None
        self._old_end = None
        self._old_seg_id = None
        if self.old_seg and self.old_seg.type == "file":
            self._old_start = self.old_seg.start_index
            self._old_end = self.old_seg.end_index
            self._old_seg_id = self.old_seg.id

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if not seg:
            return

        if seg.type == "file":
            self._execute_file_segment(seg)
        else:
            self._execute_curve_segment(seg)

        self.session.is_geometry_modified = True

        # Sync file segments to rebuild the segments list from split_indices
        self.session.project_model.update_file_segments_from_indices(
            self.session.split_indices, points=self.session.original_points)
        self.refresh_cb()

    def _execute_file_segment(self, seg):
        """Update split indices for a file segment."""
        start, end = seg.start_index, seg.end_index

        # Filter split indices to only those within this segment's range
        valid_indices = [i for i in self.split_indices if start <= i <= end]

        # Ensure endpoints are included
        if not valid_indices or valid_indices[0] != start:
            valid_indices.insert(0, start)
        if valid_indices and valid_indices[-1] != end:
            valid_indices.append(end)

        # Remove old split indices for this segment and add new ones
        self.session.split_indices = [
            i for i in self.session.split_indices if i < start or i > end
        ] + valid_indices
        self.session.split_indices.sort()

    def _execute_curve_segment(self, seg):
        """Convert a curve segment to file segments via auto-detection."""
        n = seg.parameters.get("n_points", 100)
        try:
            xs, ys = GeometryService.compute_curve_preview_pts(seg, n, self.session.original_points)
        except Exception as e:
            # Don't silently keep a broken curve: surface why the split aborted.
            _log.warning("Split edge %s: curve evaluation failed: %s",
                         getattr(seg, "id", "?"), e)
            return

        if xs is None or len(xs) < 2:
            return

        new_points = np.column_stack([xs, ys])

        # Add new points to original_points
        if self.session.original_points is None or len(self.session.original_points) == 0:
            start_idx = 0
            self.session.original_points = new_points
        else:
            start_idx = len(self.session.original_points)
            self.session.original_points = np.vstack([self.session.original_points, new_points])

        # Map split indices to new point indices
        new_split_indices = [start_idx + i for i in self.split_indices]
        self.session.split_indices.extend(new_split_indices)
        self.session.split_indices = sorted(list(set(self.session.split_indices)))

        # Remove the split curve segment from project segments
        if seg in self.session.project_model.segments:
            self.session.project_model.segments.remove(seg)

    def description(self) -> str:
        return f"Split Edge {self.old_seg.id if self.old_seg else '?'}"

    def undo(self):
        _restore_full_state(self.session, self._snap)
        self.refresh_cb()


class BakeCurveToGeometryCmd(BaseCommand):
    """Convert a curve segment to a geometry segment by evaluating its points
    and baking them into the session's original_points.
    """

    def __init__(self, session, seg_idx: int, refresh_cb):
        self.session = session
        self.seg_idx = seg_idx
        self.refresh_cb = refresh_cb

        # Save old state for undo
        self._snap = _snapshot_full_state(session)

        seg = self.session.project_model.get_segment(self.seg_idx)
        self.seg_id = seg.id if seg else None

    def description(self) -> str:
        return f"Convert Edge {self.seg_id} to Discrete"

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if not seg or seg.type != "curve":
            return

        n = seg.parameters.get("n_points", 100)
        try:
            xs, ys = GeometryService.compute_curve_preview_pts(seg, n, self.session.original_points)
        except Exception as e:
            # Don't silently keep a broken curve: surface why the bake aborted.
            _log.warning("Convert edge %s to discrete: curve evaluation "
                         "failed: %s", self.seg_id, e)
            return

        if xs is None or len(xs) < 2:
            return

        new_points = np.column_stack([xs, ys])

        start_idx = seg.start_index
        end_idx = seg.end_index
        gp = self.session.original_points

        # Determine if we replace or append
        is_connected = (gp is not None and len(gp) > 0 and
                        start_idx >= 0 and start_idx < len(gp) and
                        end_idx >= 0 and end_idx < len(gp))

        if is_connected:
            s = min(start_idx, end_idx)
            e = max(start_idx, end_idx)
            num_old_pts = e - s + 1
            num_new_pts = len(new_points)
            diff = num_new_pts - num_old_pts

            pts_to_insert = new_points if start_idx < end_idx else new_points[::-1]

            # Replace the slice
            self.session.original_points = np.vstack([
                gp[:s],
                pts_to_insert,
                gp[e + 1:]
            ])

            # Adjust indices of all other segments
            for other_seg in self.session.project_model.segments:
                if other_seg is not seg and other_seg.type == "file":
                    # Adjust start_index
                    if other_seg.start_index > e:
                        other_seg.start_index += diff
                    elif other_seg.start_index == s:
                        pass
                    elif s < other_seg.start_index <= e:
                        other_seg.start_index = s + num_new_pts - 1

                    # Adjust end_index
                    if other_seg.end_index > e:
                        other_seg.end_index += diff
                    elif other_seg.end_index == s:
                        pass
                    elif s < other_seg.end_index <= e:
                        other_seg.end_index = s + num_new_pts - 1

            # Adjust split indices
            new_splits = []
            for idx in self.session.split_indices:
                if idx < s:
                    new_splits.append(idx)
                elif idx > e:
                    new_splits.append(idx + diff)
            new_splits.append(s)
            new_splits.append(s + num_new_pts - 1)
            self.session.split_indices = sorted(list(set(new_splits)))

            # Update this segment's indices
            if start_idx < end_idx:
                seg.start_index = start_idx
                seg.end_index = start_idx + num_new_pts - 1
            else:
                seg.start_index = end_idx + num_new_pts - 1
                seg.end_index = end_idx
        elif gp is None or len(gp) == 0:
            self.session.original_points = new_points
            seg.start_index = 0
            seg.end_index = len(new_points) - 1
            self.session.split_indices += [0, len(new_points) - 1]
            self.session.split_indices = sorted(set(self.session.split_indices))
        else:
            # Append a free-standing curve, welding onto whichever END of the
            # existing geometry it actually touches. We test all FOUR endpoint
            # pairings (existing head/tail × new first/last) and pick the closest,
            # reversing the new piece and/or the existing array so the two touching
            # ends meet. The old code only ever anchored to the existing TAIL, so a
            # piece adjacent at the HEAD was blindly appended and the single
            # base-polyline renderer drew a phantom bridge across the far gap. This
            # mirrors controllers.curve_ctrl._chain_edges. When the closest pair is
            # still far apart it stays a separate piece (the adjacency bridge is
            # dropped in update_file_segments_from_indices).
            allp = np.vstack([gp, new_points])
            diag = float(np.hypot(np.ptp(allp[:, 0]), np.ptp(allp[:, 1])))
            tol = max(1e-9, 0.01 * diag)
            gp0, gp1 = gp[0], gp[-1]
            np0, np1 = new_points[0], new_points[-1]
            # (gap, reverse_gp, reverse_new) — after reversals we concatenate
            # A + B joining A[-1] to B[0], A=gp(/reversed), B=new(/reversed).
            cands = [
                (float(np.hypot(*(gp1 - np0))), False, False),  # tail ↔ new head
                (float(np.hypot(*(gp1 - np1))), False, True),   # tail ↔ new tail
                (float(np.hypot(*(gp0 - np0))), True,  False),  # head ↔ new head
                (float(np.hypot(*(gp0 - np1))), True,  True),   # head ↔ new tail
            ]
            gap, rev_gp, rev_new = min(cands, key=lambda c: c[0])
            weld = gap <= tol
            # Reversals exist only to bring the two joining endpoints together for
            # a weld. When the closest pair is too far apart the new piece stays
            # separate, so flipping the existing polyline (and mirroring every
            # segment index) would needlessly mangle its orientation and drop its
            # per-segment BC/spacing. Only reverse when we actually weld.
            if weld and rev_new:
                new_points = new_points[::-1]
            if weld and rev_gp:
                # Flip the existing polyline so its touching end becomes the tail;
                # every other file segment / split index mirrors accordingly.
                self._reverse_geometry_indices(seg, len(gp))
                gp = gp[::-1]
            add = new_points[1:] if weld else new_points
            base = len(gp)
            self.session.original_points = np.vstack([gp, add])
            seg.start_index = base - 1 if weld else base
            seg.end_index = len(self.session.original_points) - 1
            self.session.split_indices += [seg.start_index, seg.end_index]
            self.session.split_indices = sorted(set(self.session.split_indices))

        # Convert type to file.
        seg.type = "file"
        # #1: keep the point-distribution intent across the discrete conversion.
        # A By-Spacing edge (identified by a 'spacing' key) must RETAIN its
        # spacing, otherwise the very next Preview silently reverts it to
        # By-Node-Count (every consumer decides the mode purely by the presence
        # of 'spacing'). Node-count edges reset to the freshly baked count.
        if "spacing" in seg.parameters:
            # By-Spacing rides on strategy == "uniform"; keep it and refresh the
            # derived node count so the sidebar shows a sane value.
            seg.parameters = {"spacing": seg.parameters["spacing"],
                              "n_points": len(new_points)}
        else:
            seg.strategy = "uniform"
            seg.parameters = {"n_points": len(new_points)}
        seg.match_previous = False

        self.session.is_geometry_modified = True

        # Rebuild file segments
        self.session.project_model.update_file_segments_from_indices(
            self.session.split_indices, points=self.session.original_points)
        self.refresh_cb()

    def _reverse_geometry_indices(self, baked_seg, length):
        """Mirror every existing file segment's and split's index under a reversal
        of ``original_points`` (idx → length-1-idx), so a free-standing piece can
        be welded onto the geometry's HEAD by flipping the array. ``baked_seg`` is
        skipped — its indices are (re)assigned by the caller after the flip."""
        last = length - 1
        for other in self.session.project_model.segments:
            if other is baked_seg or other.type != "file":
                continue
            if other.start_index is not None and 0 <= other.start_index < length:
                other.start_index = last - other.start_index
            if other.end_index is not None and 0 <= other.end_index < length:
                other.end_index = last - other.end_index
            # Mirroring flips ascending (start<end) spans into descending ones;
            # restore start<=end so the ascending-keyed match in
            # update_file_segments_from_indices still finds the segment (else its
            # BC/spacing are lost).
            if (other.start_index is not None and other.end_index is not None
                    and other.start_index > other.end_index):
                other.start_index, other.end_index = (
                    other.end_index, other.start_index)
        self.session.split_indices = sorted(
            {last - i for i in self.session.split_indices if 0 <= i < length})

    def undo(self):
        _restore_full_state(self.session, self._snap)
        self.refresh_cb()
