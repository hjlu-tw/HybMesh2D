import copy
from app.commands.base import BaseCommand


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

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.update_strategy(self.new_strategy)
        self.repopulate_cb(self.new_strategy)

    def undo(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.strategy = self.old_strategy
            seg.parameters = copy.deepcopy(self.old_params)
        self.repopulate_cb(self.old_strategy)


class UpdateParamsCmd(BaseCommand):
    """Record a parameter change on a segment (used for undo/redo of form edits)."""

    def __init__(self, session, seg_idx: int, old_params: dict, new_params: dict, refresh_cb=None):
        self.session = session
        self.seg_idx = seg_idx
        self.old_params = copy.deepcopy(old_params)
        self.new_params = copy.deepcopy(new_params)
        self.refresh_cb = refresh_cb

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.parameters = copy.deepcopy(self.new_params)
        if self.refresh_cb:
            self.refresh_cb()

    def undo(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.parameters = copy.deepcopy(self.old_params)
        if self.refresh_cb:
            self.refresh_cb()


class RemoveSegmentCmd(BaseCommand):
    """Remove a curve segment from the project."""

    def __init__(self, session, seg_idx: int, refresh_cb):
        self.session = session
        self.seg_idx = seg_idx
        self.refresh_cb = refresh_cb  # callback to refresh list and UI

        seg = session.project_model.get_segment(seg_idx)
        self.removed_seg = copy.deepcopy(seg) if seg else None

    def execute(self):
        if self.removed_seg:
            self.session.project_model.remove_segment(self.seg_idx)
            self.refresh_cb()

    def undo(self):
        if self.removed_seg:
            self.session.project_model.segments.insert(self.seg_idx, copy.deepcopy(self.removed_seg))
            # Renumber only file segments
            file_idx = 1
            for s in self.session.project_model.segments:
                if s.type == "file":
                    s.id = file_idx
                    file_idx += 1
            self.refresh_cb()


class AddCurveSegmentCmd(BaseCommand):
    """Add a new curve segment (either blank or pre-configured/duplicated)."""

    def __init__(self, session, refresh_cb, select_cb, preconfigured_seg=None):
        self.session = session
        self.refresh_cb = refresh_cb
        self.select_cb = select_cb
        self.added_seg = preconfigured_seg

    def execute(self):
        if self.added_seg is None:
            # Create a new blank curve segment
            self.added_seg = self.session.project_model.add_curve_segment()
        else:
            # Re-add the existing preconfigured/duplicated segment
            self.session.project_model.segments.append(self.added_seg)
            # Ensure the next curve ID is higher
            pm = self.session.project_model
            if self.added_seg.id >= pm._next_curve_id:
                pm._next_curve_id = self.added_seg.id + 1

        self.refresh_cb()
        try:
            idx = self.session.project_model.segments.index(self.added_seg)
            self.select_cb(idx)
        except ValueError:
            pass

    def undo(self):
        if self.added_seg in self.session.project_model.segments:
            idx = self.session.project_model.segments.index(self.added_seg)
            self.session.project_model.segments.pop(idx)
            self.refresh_cb()
            new_idx = max(0, idx - 1)
            if self.session.project_model.segments:
                self.select_cb(new_idx)
            else:
                self.select_cb(-1)


class ToggleIsClosedCmd(BaseCommand):
    """Toggle is_closed setting for the project."""

    def __init__(self, session, is_closed: bool, refresh_cb):
        self.session = session
        self.new_val = is_closed
        self.old_val = session.project_model.is_closed
        self.refresh_cb = refresh_cb

    def execute(self):
        self.session.project_model.is_closed = self.new_val
        self.refresh_cb()

    def undo(self):
        self.session.project_model.is_closed = self.old_val
        self.refresh_cb()


class ToggleGlobalSplineCmd(BaseCommand):
    """Toggle global_spline setting for the project."""

    def __init__(self, session, global_spline: bool, refresh_cb):
        self.session = session
        self.new_val = global_spline
        self.old_val = session.project_model.global_spline
        self.refresh_cb = refresh_cb

    def execute(self):
        self.session.project_model.global_spline = self.new_val
        self.refresh_cb()

    def undo(self):
        self.session.project_model.global_spline = self.old_val
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

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.match_previous = self.new_val
            self.update_ui_cb(self.new_val)

    def undo(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.match_previous = self.old_val
            self.update_ui_cb(self.old_val)


class UpdateSegmentStateCmd(BaseCommand):
    """Record a complete state change on a segment (parameters + fields)."""

    def __init__(self, session, seg_idx: int, old_state: dict, new_state: dict, refresh_cb=None):
        self.session = session
        self.seg_idx = seg_idx
        self.old_state = copy.deepcopy(old_state)
        self.new_state = copy.deepcopy(new_state)
        self.refresh_cb = refresh_cb

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            self._apply_state(seg, self.new_state)
        if self.refresh_cb:
            self.refresh_cb()

    def undo(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            self._apply_state(seg, self.old_state)
        if self.refresh_cb:
            self.refresh_cb()

    def _apply_state(self, seg, state):
        seg.type = state.get("type", "file")
        seg.start_index = state.get("start_index", -1)
        seg.end_index = state.get("end_index", -1)
        seg.strategy = state.get("strategy", "uniform")
        seg.parameters = copy.deepcopy(state.get("parameters", {}))
        seg.match_previous = state.get("match_previous", False)
        
        # Curve specific
        seg.curve_type = state.get("curve_type", "custom")
        seg.curve_mode = state.get("curve_mode", "parametric")
        seg.x_formula = state.get("x_formula", "cos(t)")
        seg.y_formula = state.get("y_formula", "sin(t)")
        seg.formula = state.get("formula", "sin(x)")
        
        # Unpack range
        r = seg.parameters.pop("range", [0.0, 6.283185307])
        seg.t_min = float(r[0])
        seg.t_max = float(r[1])

