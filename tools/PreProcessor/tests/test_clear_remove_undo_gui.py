#!/usr/bin/env python3
"""CAD-tab canvas/tree hygiene (offscreen AppController):

  item 2  Undo of an add leaves NO stray edge highlight on the canvas.
  item 3  'Clear All' removes every edge + points (undoable); plain 'Clear'
          keeps the geometry.
  item 4  'Remove Edge' on a MIDDLE discrete edge does not resurrect it in the
          model tree, and clears its selection highlight from the canvas.

Run: python3 tools/PreProcessor/tests/test_clear_remove_undo_gui.py
"""
import os
import sys
import threading
import functools

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

import builtins
print = functools.partial(builtins.print, flush=True)
_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        _FAILS.append(msg)


def n_multi(cv):
    """Number of drawn selection-highlight polylines (_multi_segment_curves)."""
    return len(getattr(cv, "_multi_segment_curves", []) or [])


def n_file(pm):
    return len([s for s in pm.segments if s.type == "file"])


threading.Timer(60, lambda: (print("FAIL watchdog >60s"), os._exit(99))).start()

from PyQt6.QtWidgets import QApplication  # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402
from app.models.segment import SegmentModel  # noqa: E402

c = AppController()
mw = c.main_window
mw.show()
app.processEvents()


def square():
    """41-pt closed unit square, corners at 0/10/20/30/40."""
    seg = []
    for i in range(10):
        seg.append((i / 10.0, 0.0))          # bottom 0..9
    for i in range(10):
        seg.append((1.0, i / 10.0))          # right  10..19
    for i in range(10):
        seg.append((1.0 - i / 10.0, 1.0))    # top    20..29
    for i in range(10):
        seg.append((0.0, 1.0 - i / 10.0))    # left   30..39
    seg.append((0.0, 0.0))                   # close  40
    return np.array(seg, dtype=float)


# ── Discrete quad with 4 file edges ───────────────────────────────────────────
sess = c.active_session()
pm = sess.project_model
sess.original_points = square()
sess.split_indices = [0, 10, 20, 30, 40]
pm.update_file_segments_from_indices(sess.split_indices, points=sess.original_points)
c._refresh_segment_list()
c._apply_geometry_update(sess)
app.processEvents()
check(n_file(pm) == 4, f"start: 4 discrete edges (got {n_file(pm)})")

# ── item 4: remove the MIDDLE (right) edge -> 3 edges, no phantom, no residual ─
sess.current_segment_idx = 1                 # the (10,20) right side
c.remove_selected_segment()
app.processEvents()
check(n_file(pm) == 3,
      f"remove-middle leaves 3 edges, no phantom resurrection (got {n_file(pm)})")
# rebuild again (mirrors a later Convert/loads) — still no phantom
c._apply_geometry_update(sess)
app.processEvents()
check(n_file(pm) == 3, f"phantom stays gone after a second rebuild (got {n_file(pm)})")
check(n_multi(mw.canvas_view) == 0,
      f"remove clears the selection highlight (got {n_multi(mw.canvas_view)})")

# ── item 3: Clear All wipes everything; undo restores ─────────────────────────
n_before = n_file(pm)
c.clear_all_geometry()
app.processEvents()
check(n_file(pm) == 0 and sess.original_points is None,
      f"Clear All removes all geometry (got {n_file(pm)} edges)")
check(n_multi(mw.canvas_view) == 0, "Clear All leaves no selection highlight")

# ── item 5 (USER-REPORTED): Redraw after Clear All must leave a BLANK canvas ──
# _apply_geometry_update returned on its first line when original_points was
# None, so every rebuild path agreed the model was empty while the pyqtgraph
# items kept the last geometry pushed into them — the residue the user saw.
c.redraw_canvas(announce=False)
app.processEvents()
gx, gy = mw.canvas_view._geometries[sess.session_id].getData()
check(gx is None or len(gx) == 0,
      f"Redraw after Clear All wipes the base geometry from the canvas "
      f"(got {0 if gx is None else len(gx)} points)")
check(mw.canvas_view._active_points is None,
      "...and drops the hit-test points with it, so a click cannot select a "
      "vertex of geometry that no longer exists")
sx, _sy = mw.canvas_view.split_scatter.getData()
check(sx is None or len(sx) == 0,
      f"...and the split markers go too (got {0 if sx is None else len(sx)})")
cx, _cy = mw.canvas_view._closing_edge.getData()
check(cx is None or len(cx) == 0,
      "...and the gold closing edge, which described a loop that is gone")

c.undo()
app.processEvents()
check(n_file(pm) == n_before and sess.original_points is not None,
      f"undo restores the cleared geometry ({n_before} edges; got {n_file(pm)})")
tree = mw.sidebar_view.geometry_tree
n_rows = len(tree.edge_items(sess.session_id))
check(n_rows == n_before,
      f"undo Clear All also refreshes the model tree ({n_before} rows; got {n_rows})")

# ── item 3: plain Clear keeps the geometry ────────────────────────────────────
c.clear_cad_canvas()
app.processEvents()
check(n_file(pm) == n_before, "plain Clear keeps the geometry (overlay-only)")

# ── item 2: undo of an added analytic edge leaves no highlight residual ───────
c.new_blank_tab()
s2 = c.active_session()
p2 = s2.project_model
line = SegmentModel(10001, -1, -1)
line.type = "curve"; line.curve_type = "line"; line.curve_mode = "parametric"
line.parameters = {"n_points": 12, "x0": 0, "y0": 0, "x1": 1, "y1": 0}
from app.commands.segment_cmds import AddCurveSegmentCmd
cmd = AddCurveSegmentCmd(s2, refresh_cb=c._refresh_segment_list,
                         select_cb=lambda i: setattr(s2, "current_segment_idx", i),
                         preconfigured_seg=line)
s2.command_history.execute(cmd)
c._refresh_segment_list()
c.highlight_selected_segments()
app.processEvents()
check(len([s for s in p2.segments if s.type == "curve"]) == 1, "added 1 curve edge")
c.undo()
app.processEvents()
check(len([s for s in p2.segments if s.type == "curve"]) == 0, "undo removes the curve edge")
check(n_multi(mw.canvas_view) == 0,
      f"undo leaves NO stray edge highlight (got {n_multi(mw.canvas_view)})")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
