#!/usr/bin/env python3
"""Offscreen AppController test for "Join / Close Edges -> Polygon".

Builds four hand-drawn-style line edges forming a box, joins them, and checks:
  - the four line edges collapse into ONE closed polygon (4 vertices)
  - the "boundary not closed" red endpoint markers clear after the join
  - undo restores the four line edges (and re-flags them open)

Run: python3 tools/PreProcessor/tests/test_join_edges_gui.py
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

sess = c.active_session()
pm = sess.project_model


def line(cid, x0, y0, x1, y1):
    s = SegmentModel(cid, -1, -1)
    s.type = "curve"
    s.curve_type = "line"
    s.curve_mode = "parametric"
    s.parameters = {"n_points": 12, "x0": x0, "y0": y0, "x1": x1, "y1": y1}
    return s


# Four edges of a unit box, corners coincident.
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

check(len([s for s in pm.segments if s.type == "curve"]) == 4, "start: 4 line edges")
check(_n(mw.canvas_view._open_endpoint_markers) > 0,
      "start: open endpoints flagged red (boundary not closed)")

# Enable/disable follows selection (like "Remove Edge").
sb = mw.sidebar_view
tree = sb.geometry_tree
check(not sb.join_edges_btn.isEnabled(), "join btn disabled with nothing selected")
items = tree.edge_items(sess.session_id)


def _select(item_slice):
    tree.blockSignals(True)
    tree.clear_edge_selection()
    for it in item_slice:
        it.setSelected(True)
    tree.blockSignals(False)
    c.highlight_selected_segments()
    app.processEvents()


_select(items[:2])
check(sb.join_edges_btn.isEnabled(), "join btn enabled with 2 curve edges selected")
_select(items[:1])
check(not sb.join_edges_btn.isEnabled(), "join btn disabled with only 1 selected")
_select([])
check(not sb.join_edges_btn.isEnabled(), "join btn disabled after deselect")

# Join (nothing selected -> falls back to all open curve edges).
c.join_selected_edges_to_polygon()
app.processEvents()

polys = [s for s in pm.segments if s.type == "curve" and s.curve_type == "polygon"]
check(len(pm.segments) == 1 and len(polys) == 1,
      f"after join: single polygon edge (got {len(pm.segments)} segs)")
if polys:
    from app.models import shape_spec
    verts = shape_spec.polygon_vertices(polys[0].parameters)
    check(polys[0].closed is True, "polygon is closed")
    check(len(verts) == 4, f"polygon has 4 corner vertices (got {len(verts)})")
check(_n(mw.canvas_view._open_endpoint_markers) == 0,
      "after join: open-endpoint markers cleared (boundary closed)")
check(not sb.join_edges_btn.isEnabled(),
      "join btn disabled after join (single polygon selected)")

# Undo restores the four line edges.
sess.command_history.undo()
c.detect_open_endpoints(sess)
app.processEvents()
lines_back = [s for s in pm.segments if s.type == "curve" and s.curve_type == "line"]
check(len(lines_back) == 4, f"undo restores 4 line edges (got {len(lines_back)})")

# Redo joins again.
sess.command_history.redo()
app.processEvents()
check(len([s for s in pm.segments if s.curve_type == "polygon"]) == 1,
      "redo re-joins into the polygon")

# Broken chain aborts cleanly (a disconnected extra edge).
sess.command_history.undo()   # back to 4 lines
app.processEvents()
pm.segments = pm.segments + [line(10010, 5, 5, 6, 5)]  # detached edge
pm._next_curve_id = 10011
c._refresh_segment_list()
n_before = len(pm.segments)
c.join_selected_edges_to_polygon()   # should abort (not one connected chain)
check(len(pm.segments) == n_before,
      "disconnected edges: join aborts without mutating segments")

# ── Force-close checkbox on an OPEN chain (no natural loop) ────────────────
c.new_blank_tab()
s2 = c.active_session()
p2 = s2.project_model
p2.segments = [line(10001, 0, 0, 1, 0),
               line(10002, 1, 0, 1, 1),
               line(10003, 1, 1, 0, 1)]      # open "U": ends (0,0)..(0,1)
p2._next_curve_id = 10004
c._refresh_segment_list()
sb.join_force_close_cb.setChecked(False)
c.join_selected_edges_to_polygon()
app.processEvents()
polys2 = [x for x in p2.segments if getattr(x, "curve_type", "") == "polygon"]
check(len(p2.segments) == 1 and polys2, "open chain: joined into one polygon")
check(bool(polys2) and polys2[0].closed is False,
      "checkbox OFF → OPEN polygon (closed False)")
check(_n(mw.canvas_view._open_endpoint_markers) > 0,
      "open polygon still flags its open endpoints")
s2.command_history.undo()
app.processEvents()
sb.join_force_close_cb.setChecked(True)
c.join_selected_edges_to_polygon()
app.processEvents()
polys2 = [x for x in p2.segments if getattr(x, "curve_type", "") == "polygon"]
check(bool(polys2) and polys2[0].closed is True, "checkbox ON → CLOSED polygon")
check(_n(mw.canvas_view._open_endpoint_markers) == 0,
      "forced-closed polygon clears open markers")
sb.join_force_close_cb.setChecked(False)
check(sb.join_force_close_cb.isEnabled(), "force-close checkbox is always enabled")

# ── Discrete arc + line: shape preserved, arc points consumed ─────────────
c.new_blank_tab()
s3 = c.active_session()
p3 = s3.project_model
N = 21
th = np.linspace(0.0, np.pi, N)
arc = np.column_stack([np.cos(th), np.sin(th)])     # (1,0)->(0,1)->(-1,0)
s3.original_points = arc.copy()
s3.split_indices = [0, N - 1]
fseg = SegmentModel(1, 0, N - 1)
fseg.type = "file"
fseg.parameters = {"n_points": N}
p3.segments = [fseg, line(10001, -1.0, 0.0, 1.0, 0.0)]   # diameter closes the loop
p3._next_curve_id = 10002
c._refresh_segment_list()
c.join_selected_edges_to_polygon()       # nothing selected -> all edges
app.processEvents()
polys3 = [x for x in p3.segments if getattr(x, "curve_type", "") == "polygon"]
check(len(p3.segments) == 1 and polys3, "arc+line: joined into one polygon")
check(bool(polys3) and polys3[0].closed is True, "arc+line natural loop → closed")
from app.models import shape_spec as _ss
nv = len(_ss.polygon_vertices(polys3[0].parameters)) if polys3 else 0
check(nv >= N, f"arc shape preserved (>= {N} vertices, got {nv})")
check(len(s3.original_points) == 0, "consumed arc removed from original_points")
s3.command_history.undo()
app.processEvents()
check(len(s3.original_points) == N
      and len([x for x in p3.segments if x.type == "file"]) == 1,
      "undo restores the discrete arc file segment")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
