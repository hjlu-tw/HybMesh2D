#!/usr/bin/env python3
"""Item 2: "Join / Close Edges" KEEP mode must keep the selected edges as
SEPARATE, individually selectable & vertex-editable segments (each with its own
BC), welding shared endpoints and closing the loop — NOT collapse them into one
polygon.

Guards the complaint: after KEEP the model tree showed only ONE edge and its
vertices could no longer be selected. KEEP must now leave N edges in place, the
project marked closed, and (for a discrete edge) its points still in
original_points so the canvas can hit-test them.

Run: python3 tools/PreProcessor/tests/test_join_keep_separate_gui.py
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


def _n(item):
    xd, _ = item.getData()
    return 0 if xd is None else len(xd)


threading.Timer(40, lambda: (print("FAIL watchdog >40s"), os._exit(99))).start()

from PyQt6.QtWidgets import QApplication  # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402
from app.models.segment import SegmentModel  # noqa: E402

c = AppController()
mw = c.main_window
mw.show()
app.processEvents()
c._ask_join_keep_separate = lambda: True     # choose KEEP


def line(cid, x0, y0, x1, y1):
    s = SegmentModel(cid, -1, -1)
    s.type = "curve"
    s.curve_type = "line"
    s.curve_mode = "parametric"
    s.parameters = {"n_points": 12, "x0": x0, "y0": y0, "x1": x1, "y1": y1}
    return s


# ── Box of 4 line edges → KEEP keeps 4 separate line edges + closes ───────────
sess = c.active_session()
pm = sess.project_model
pm.segments = [
    line(10001, 0, 0, 1, 0),
    line(10002, 1, 0, 1, 1),
    line(10003, 1, 1, 0, 1),
    line(10004, 0, 1, 0, 0),
]
pm._next_curve_id = 10005
c._refresh_segment_list()
c._update_canvas_curve_segments()
c.detect_open_endpoints(sess)
app.processEvents()
check(_n(mw.canvas_view._open_endpoint_markers) > 0, "start: open endpoints flagged")

c.join_selected_edges_to_polygon()           # nothing selected -> all edges
app.processEvents()

lines_after = [s for s in pm.segments if getattr(s, "curve_type", "") == "line"]
polys_after = [s for s in pm.segments if getattr(s, "curve_type", "") == "polygon"]
check(len(polys_after) == 0, "KEEP creates NO polygon")
check(len(pm.segments) == 4 and len(lines_after) == 4,
      f"KEEP keeps 4 separate line edges (got {len(pm.segments)} segs)")
check(pm.is_closed is True, "KEEP closes the loop at project level")
check(_n(mw.canvas_view._open_endpoint_markers) == 0,
      "KEEP clears the open-endpoint markers")

# Undo restores the pre-join open state.
sess.command_history.undo()
c.detect_open_endpoints(sess)
app.processEvents()
check(len([s for s in pm.segments if getattr(s, "curve_type", "") == "line"]) == 4,
      "undo keeps the 4 line edges")
check(pm.closed_mode != "closed", "undo restores the closure mode")
sess.command_history.redo()
app.processEvents()
check(pm.is_closed is True, "redo re-closes")

# ── Discrete arc + line → KEEP keeps BOTH edges (arc points preserved) ────────
c.new_blank_tab()
s3 = c.active_session()
p3 = s3.project_model
N = 21
th = np.linspace(0.0, np.pi, N)
arc = np.column_stack([np.cos(th), np.sin(th)])     # (1,0)->(-1,0) upper semicircle
s3.original_points = arc.copy()
s3.split_indices = [0, N - 1]
fseg = SegmentModel(1, 0, N - 1)
fseg.type = "file"
fseg.parameters = {"n_points": N}
p3.segments = [fseg, line(10001, -1.0, 0.0, 1.0, 0.0)]   # diameter closes the loop
p3._next_curve_id = 10002
c._refresh_segment_list()
c.join_selected_edges_to_polygon()
app.processEvents()

polys3 = [s for s in p3.segments if getattr(s, "curve_type", "") == "polygon"]
files3 = [s for s in p3.segments if s.type == "file"]
check(len(polys3) == 0, "arc+line KEEP creates no polygon")
check(len(p3.segments) == 2 and len(files3) == 1,
      f"arc+line KEEP keeps 2 separate edges incl the discrete arc (got {len(p3.segments)})")
check(len(s3.original_points) == N,
      "discrete arc points PRESERVED (still click-selectable), not consumed")
check(p3.is_closed is True, "arc+line KEEP closes the loop")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
