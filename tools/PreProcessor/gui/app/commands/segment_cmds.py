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

    def __init__(self, session, seg_idx: int, old_params: dict, new_params: dict):
        self.session = session
        self.seg_idx = seg_idx
        self.old_params = copy.deepcopy(old_params)
        self.new_params = copy.deepcopy(new_params)

    def execute(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.parameters = copy.deepcopy(self.new_params)

    def undo(self):
        seg = self.session.project_model.get_segment(self.seg_idx)
        if seg:
            seg.parameters = copy.deepcopy(self.old_params)
