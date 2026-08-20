"""Headless (no-Qt) regression tests for the undo/redo command layer.

Exercises the command classes and models directly against a lightweight fake
session, so it needs no display and is safe for CI. Run with:

    python3 tools/PreProcessor/tests/test_undo_redo.py

Covers the fixes from the undo/redo code review: identity-loss phantom
segment, is_geometry_modified restoration, BC restore, split keep-vertex dirty
flag, ToggleMatchPrevious on a missing segment, the shared ReplacePointsCmd
base, and faithful repeated undo/redo cycles.
"""
import os
import sys
import types

import numpy as np

# Resolve paths relative to this file so the test runs from any cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI_DIR = os.path.normpath(os.path.join(_HERE, "..", "gui"))
sys.path.insert(0, _GUI_DIR)

from app.models.project import ProjectModel
from app.models.segment import SegmentModel
from app.commands.base import CommandHistory
from app.commands.segment_cmds import (
    AddCurveSegmentCmd, RemoveSegmentCmd, UpdateMultipleSegmentsStateCmd,
    ToggleMatchPreviousCmd,
)
from app.commands.split_cmds import RemoveSplitCmd
from app.commands.vertex_cmds import ReplaceGeometryPointsCmd, ReplacePointsCmd
from app.commands.stitch_cmds import StitchCmd

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def make_session(points=None, splits=None):
    s = types.SimpleNamespace()
    s.project_model = ProjectModel()
    s.original_points = points
    s.split_indices = list(splits) if splits else []
    s.is_geometry_modified = False
    return s


def curve_seg(sid, ct="line"):
    seg = SegmentModel(sid, -1, -1)
    seg.type = "curve"
    seg.curve_type = ct
    return seg


refresh = lambda *a, **k: None
select = lambda *a, **k: None


def refresh_renumber(sess):
    return lambda: sess.project_model.renumber_segments()


def test_phantom_segment_and_modified_flag():
    s = make_session()
    B = curve_seg(1)
    s.project_model.segments = [B]
    s.is_geometry_modified = False
    h = CommandHistory()

    addA = AddCurveSegmentCmd(s, refresh_cb=refresh_renumber(s), select_cb=select,
                              preconfigured_seg=curve_seg(2))
    h.execute(addA)
    check("add: A present after add", len(s.project_model.segments) == 2)
    check("add: modified True after add", s.is_geometry_modified is True)

    rmB = RemoveSegmentCmd(s, 0, refresh_cb=refresh_renumber(s))
    h.execute(rmB)
    check("remove: 1 seg after remove", len(s.project_model.segments) == 1)

    h.undo()   # undo remove
    check("undo remove: 2 segs", len(s.project_model.segments) == 2)
    h.undo()   # undo add -> A must be gone (identity-loss fix)
    check("undo add: 1 seg, no phantom", len(s.project_model.segments) == 1)
    check("undo add: modified restored to False", s.is_geometry_modified is False)

    h.redo(); h.redo()
    check("redo both: 1 seg (B removed, A added)", len(s.project_model.segments) == 1)
    h.undo(); h.undo()
    check("undo-again after redo: clean", len(s.project_model.segments) == 1
          and s.is_geometry_modified is False)
    h.redo(); h.undo(); h.redo(); h.undo()
    check("repeated undo/redo cycles stay faithful", len(s.project_model.segments) == 1
          and s.is_geometry_modified is False)


def test_blank_add():
    s = make_session()
    s.project_model.segments = []
    h = CommandHistory()
    add = AddCurveSegmentCmd(s, refresh_cb=refresh_renumber(s), select_cb=select)
    h.execute(add)
    check("blank add: 1 seg, modified True",
          len(s.project_model.segments) == 1 and s.is_geometry_modified is True)
    h.undo()
    check("blank add: 0 segs, modified False after undo",
          len(s.project_model.segments) == 0 and s.is_geometry_modified is False)
    h.redo()
    check("blank add: 1 seg after redo", len(s.project_model.segments) == 1)


def test_bc_restore():
    s = make_session()
    seg = curve_seg(1)
    seg.bc = ""
    s.project_model.segments = [seg]
    h = CommandHistory()
    old_state = seg.to_dict()
    seg.bc = "wall"
    new_state = seg.to_dict()
    cmd = UpdateMultipleSegmentsStateCmd(s, {0: (old_state, new_state)}, refresh_cb=refresh)
    h.execute(cmd)
    check("bc: wall after execute", s.project_model.get_segment(0).bc == "wall")
    h.undo()
    check("bc: restored to '' after undo", s.project_model.get_segment(0).bc == "")
    h.redo()
    check("bc: wall again after redo", s.project_model.get_segment(0).bc == "wall")


def test_split_keep_vertex_dirty():
    s = make_session(points=np.arange(22).reshape(11, 2).astype(float), splits=[0, 5, 10])
    h = CommandHistory()
    rs = RemoveSplitCmd(s, 5, keep_vertex=True, sync_cb=refresh, refresh_cb=refresh)
    h.execute(rs)
    check("split keep-vertex: 5 removed", 5 not in s.split_indices)
    check("split keep-vertex: modified True", s.is_geometry_modified is True)
    h.undo()
    check("split keep-vertex: 5 restored on undo", 5 in s.split_indices)
    check("split keep-vertex: modified restored False", s.is_geometry_modified is False)


def test_toggle_match_previous_missing_seg():
    s = make_session()
    s.project_model.segments = [curve_seg(1)]
    h = CommandHistory()
    tmp = ToggleMatchPreviousCmd(s, 999, True, update_ui_cb=lambda *_: None)
    h.execute(tmp)
    check("toggle match-prev: missing seg leaves modified False",
          s.is_geometry_modified is False)


def test_replace_points_base():
    check("StitchCmd subclasses ReplacePointsCmd", issubclass(StitchCmd, ReplacePointsCmd))
    check("ReplaceGeometryPointsCmd subclasses ReplacePointsCmd",
          issubclass(ReplaceGeometryPointsCmd, ReplacePointsCmd))
    s = make_session(points=np.zeros((3, 2)))
    h = CommandHistory()
    newp = np.ones((3, 2))
    st = StitchCmd(s, old_points=s.original_points, new_points=newp, refresh_cb=refresh)
    h.execute(st)
    check("stitch: applies new points", np.array_equal(s.original_points, newp))
    check("stitch: description label", st.description() == "Stitch unclosed points")
    h.undo()
    check("stitch: undo restores old points", np.array_equal(s.original_points, np.zeros((3, 2))))


def main():
    test_phantom_segment_and_modified_flag()
    test_blank_add()
    test_bc_restore()
    test_split_keep_vertex_dirty()
    test_toggle_match_previous_missing_seg()
    test_replace_points_base()
    print()
    print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
