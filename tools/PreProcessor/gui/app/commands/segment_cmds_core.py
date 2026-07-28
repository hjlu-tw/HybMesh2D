import copy
from app.commands.base import BaseCommand


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
