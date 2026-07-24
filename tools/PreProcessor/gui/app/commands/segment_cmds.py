import copy
import logging
import numpy as np
from app.commands.base import BaseCommand
from app.services.index_helpers import remove_points_and_adjust_indices
from app.services.geometry_service import GeometryService

_log = logging.getLogger(__name__)


def _snapshot_full_state(session) -> dict:
    """Capture the full undoable geometry state of a session.

    Paired with :func:`_restore_full_state`. Used by every command that mutates
    the segment list / point array wholesale (add, remove, split, bake,
    duplicate). Restoring deep-copies the captured segment list so that a later
    *redo* which mutates ``project_model.segments`` in place can never corrupt
    this snapshot — allowing repeated undo↔redo cycles to stay faithful.
    """
    pm = session.project_model
    return {
        "points": (session.original_points.copy()
                   if session.original_points is not None else None),
        "split_indices": list(session.split_indices),
        "segments": copy.deepcopy(pm.segments),
        "next_curve_id": pm._next_curve_id,
        "modified": session.is_geometry_modified,
    }


def _restore_full_state(session, snap: dict):
    """Restore a snapshot produced by :func:`_snapshot_full_state`.

    The segment list is deep-copied on the way out so the snapshot itself is
    never aliased by the live model (see the note in ``_snapshot_full_state``).
    """
    pm = session.project_model
    session.original_points = (snap["points"].copy()
                               if snap["points"] is not None else None)
    session.split_indices = list(snap["split_indices"])
    pm.segments = copy.deepcopy(snap["segments"])
    pm._next_curve_id = snap["next_curve_id"]
    session.is_geometry_modified = snap["modified"]


def _apply_segment_state(seg, state: dict):
    """Restore a SegmentModel from a dict produced by ``SegmentModel.to_dict()``.

    Shared by the single- and multi-segment state commands so undo/redo behaves
    identically. Note the curve t-range lives inside ``parameters["range"]`` (not
    as ``t_min``/``t_max`` keys), so it must be unpacked from there.
    """
    seg.type = state.get("type", "file")
    seg.start_index = state.get("start_index", -1)
    seg.end_index = state.get("end_index", -1)
    seg.strategy = state.get("strategy", "uniform")
    seg.parameters = copy.deepcopy(state.get("parameters", {}))
    seg.match_previous = state.get("match_previous", False)
    seg.closed = state.get("closed", True)
    # Per-segment boundary condition. to_dict() only emits "bc" when non-empty,
    # so the "" default correctly restores a segment back to inheriting BC_GEOM.
    seg.bc = state.get("bc", "")

    # Curve specific
    seg.curve_type = state.get("curve_type", "custom")
    seg.curve_mode = state.get("curve_mode", "parametric")
    seg.x_formula = state.get("x_formula", "cos(t)")
    seg.y_formula = state.get("y_formula", "sin(t)")
    seg.formula = state.get("formula", "sin(x)")

    # Unpack the t-range (stored inside parameters by to_dict).
    r = seg.parameters.pop("range", [0.0, 6.283185307])
    seg.t_min = float(r[0])
    seg.t_max = float(r[1])


class UpdateStrategyCmd(BaseCommand):
    """Change the resampling strategy of a segment."""

    def __init__(self, session, seg_idx: int, new_strategy: str,
                 repopulate_cb):
        self.session = session
        self.seg_idx = seg_idx
        self.new_strategy = new_strategy
        self.repopulate_cb = repopulate_cb  # callback(strategy_name)

        seg = session.project_model.get_segment(seg_idx)
        self.old_strategy = seg.strategy if seg else "uniform"
        self.old_params = copy.deepcopy(seg.parameters) if seg else {}
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        return f"Change Distribution to {self.new_strategy}"

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.update_strategy(self.new_strategy)
        self.session.is_geometry_modified = True
        self.repopulate_cb(self.new_strategy)

    def undo(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.strategy = self.old_strategy
            seg.parameters = copy.deepcopy(self.old_params)
        self.session.is_geometry_modified = self._old_modified
        self.repopulate_cb(self.old_strategy)


class UpdateParamsCmd(BaseCommand):
    """Record a parameter change on a segment (used for undo/redo of form edits)."""

    def __init__(self, session, seg_idx: int, old_params: dict, new_params: dict, refresh_cb=None):
        self.session = session
        self.seg_idx = seg_idx
        self.old_params = copy.deepcopy(old_params)
        self.new_params = copy.deepcopy(new_params)
        self.refresh_cb = refresh_cb
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        return "Update Edge Parameters"

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.parameters = copy.deepcopy(self.new_params)
        self.session.is_geometry_modified = True
        if self.refresh_cb:
            self.refresh_cb()

    def undo(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.parameters = copy.deepcopy(self.old_params)
        self.session.is_geometry_modified = self._old_modified
        if self.refresh_cb:
            self.refresh_cb()


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


class SetClosedModeCmd(BaseCommand):
    """Set the project closure mode (auto / closed / open).

    Stores the user *intent* (the mode); the effective is_closed is re-derived
    via resolve_closure() so an "auto" choice tracks the geometry."""

    def __init__(self, session, mode: str, refresh_cb):
        self.session = session
        self.new_mode = mode
        self.old_mode = session.project_model.closed_mode
        self.refresh_cb = refresh_cb
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        return "Set Closure Mode"

    def _apply(self, mode: str):
        pm = self.session.project_model
        pm.closed_mode = mode
        pm.resolve_closure(self.session.original_points)

    def execute(self):
        self._apply(self.new_mode)
        self.session.is_geometry_modified = True
        self.refresh_cb()

    def undo(self):
        self._apply(self.old_mode)
        self.session.is_geometry_modified = self._old_modified
        self.refresh_cb()


class ToggleGlobalSplineCmd(BaseCommand):
    """Toggle global_spline setting for the project."""

    def __init__(self, session, global_spline: bool, refresh_cb):
        self.session = session
        self.new_val = global_spline
        self.old_val = session.project_model.global_spline
        self.refresh_cb = refresh_cb
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        return "Toggle Global Spline"

    def execute(self):
        self.session.project_model.global_spline = self.new_val
        self.session.is_geometry_modified = True
        self.refresh_cb()

    def undo(self):
        self.session.project_model.global_spline = self.old_val
        self.session.is_geometry_modified = self._old_modified
        self.refresh_cb()


class ToggleMatchPreviousCmd(BaseCommand):
    """Toggle match_previous setting for a segment."""

    def __init__(self, session, seg_idx: int, match_previous: bool, update_ui_cb):
        self.session = session
        self.seg_idx = seg_idx
        self.new_val = match_previous
        seg = session.project_model.get_segment(seg_idx)
        self.old_val = seg.match_previous if seg else False
        self.update_ui_cb = update_ui_cb
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        return "Toggle Match Previous"

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.match_previous = self.new_val
            self.update_ui_cb(self.new_val)
            self.session.is_geometry_modified = True

    def undo(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.match_previous = self.old_val
            self.update_ui_cb(self.old_val)
        self.session.is_geometry_modified = self._old_modified


class UpdateSegmentStateCmd(BaseCommand):
    """Record a complete state change on a segment (parameters + fields)."""

    def __init__(self, session, seg_idx: int, old_state: dict, new_state: dict, refresh_cb=None):
        self.session = session
        self.seg_idx = seg_idx
        self.old_state = copy.deepcopy(old_state)
        self.new_state = copy.deepcopy(new_state)
        self.refresh_cb = refresh_cb
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        seg = self.session.project_model.get_segment(self.seg_idx)
        seg_id = seg.id if seg else self.seg_idx
        return f"Update Edge {seg_id}"

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            self._apply_state(seg, self.new_state)
        self.session.is_geometry_modified = True
        if self.refresh_cb:
            self.refresh_cb()

    def undo(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            self._apply_state(seg, self.old_state)
        self.session.is_geometry_modified = self._old_modified
        if self.refresh_cb:
            self.refresh_cb()

    def _apply_state(self, seg, state):
        _apply_segment_state(seg, state)


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
            # Append a free-standing curve. If its NEAR endpoint touches the
            # existing geometry's tail (two edges drawn to chain into one open
            # boundary), WELD them — orient so the near end joins the tail and
            # drop the duplicated joint point — so we get ONE connected polyline
            # sharing that boundary index, not a disjoint piece plus a phantom
            # bridge (and never a spurious line to the FAR endpoint). When the
            # ends are far apart it stays a separate piece (the adjacency bridge
            # is dropped in update_file_segments_from_indices).
            allp = np.vstack([gp, new_points])
            diag = float(np.hypot(np.ptp(allp[:, 0]), np.ptp(allp[:, 1])))
            tol = max(1e-9, 0.01 * diag)
            last = gp[-1]
            if (np.hypot(*(last - new_points[-1]))
                    < np.hypot(*(last - new_points[0]))):
                new_points = new_points[::-1]        # near end joins the tail
            weld = float(np.hypot(*(last - new_points[0]))) <= tol
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

    def undo(self):
        _restore_full_state(self.session, self._snap)
        self.refresh_cb()


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


class UpdateMultipleSegmentsStateCmd(BaseCommand):
    """Record a complete state change on multiple segments simultaneously."""

    def __init__(self, session, states_dict: dict[int, tuple[dict, dict]], refresh_cb=None):
        """
        states_dict: map of seg_idx -> (old_state, new_state)
        """
        self.session = session
        self.states = copy.deepcopy(states_dict)
        self.refresh_cb = refresh_cb
        self._old_modified = session.is_geometry_modified

    def description(self) -> str:
        seg_ids = []
        for idx in self.states.keys():
            seg = self.session.project_model.get_segment(idx)
            if seg:
                seg_ids.append(str(seg.id))
        return f"Update Edges: {', '.join(seg_ids)}"

    def execute(self):
        for seg_idx, (_, new_state) in self.states.items():
            seg = self.session.project_model.get_segment(seg_idx)
            if seg:
                self._apply_state(seg, new_state)
        self.session.is_geometry_modified = True
        if self.refresh_cb:
            self.refresh_cb()

    def undo(self):
        for seg_idx, (old_state, _) in self.states.items():
            seg = self.session.project_model.get_segment(seg_idx)
            if seg:
                self._apply_state(seg, old_state)
        self.session.is_geometry_modified = self._old_modified
        if self.refresh_cb:
            self.refresh_cb()

    def _apply_state(self, seg, state):
        _apply_segment_state(seg, state)


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
