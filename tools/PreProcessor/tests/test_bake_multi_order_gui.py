#!/usr/bin/env python3
"""Convert to Discrete on a multi-edge selection: order it, and draw no diagonal.

USER-REPORTED (2026-08-12): "if I build a quadrilateral out of four line edges
and convert them to discrete WITHOUT going round in CW/CCW order, a diagonal
appears. Could selecting the whole closed shape and pressing Convert to Discrete
detect the order automatically?"

Two independent things were wrong, and both are fixed here:

 1. **The bake order was the click order.** Each bake welds its points onto
    whichever END of the existing polyline it actually touches; an edge that
    touches neither end is appended as a separate piece. Converting 1, 3, 2, 4 of
    a quad therefore produced two disjoint runs where 1, 2, 3, 4 produces one
    boundary. ``bake_selected_curve`` now chains the selection by endpoint
    coincidence (the same ``_chain_edges`` that Join uses) and bakes head to
    tail, so the click order stops mattering. It is also ONE undo step.

 2. **The canvas joined the pieces anyway.** The base geometry is a single
    pyqtgraph polyline, so two pieces that merely sit next to each other in
    ``original_points`` were drawn connected — that straight line across the gap
    IS the reported diagonal. It belongs to no edge, so no amount of selecting or
    removing could get rid of it. The polyline is now given a ``connect`` array
    derived from the model: an index interval covered by no file segment is a
    real discontinuity, and the rebuild already drops the bridging pair.

Checks:
 1. Baking the four sides in the WORST order (1, 3, 2, 4) yields ONE connected
    boundary — the same point count and the same closed loop as the natural order.
 2. ... and the model agrees: four file edges, and the geometry resolves closed.
 3. It is a single undo step, and undoing restores all four analytic edges.
 4. Disjoint pieces (two separate shapes) still convert, and the canvas BREAKS
    the polyline between them instead of drawing a bridge.
 5. A fully connected geometry gets no connect array at all (the fast path).

Run:  python3 tools/PreProcessor/tests/test_bake_multi_order_gui.py
"""
import functools
import os
import sys
import threading

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

import builtins                                                    # noqa: E402
print = functools.partial(builtins.print, flush=True)
_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        _FAILS.append(msg)


threading.Timer(120, lambda: (print("FAIL watchdog >120s"), os._exit(99))).start()

from PyQt6.QtWidgets import QApplication                           # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController                           # noqa: E402
from app.models.segment import SegmentModel                        # noqa: E402
from app.commands.segment_cmds import AddCurveSegmentCmd           # noqa: E402

c = AppController()
mw = c.main_window
mw.show()
app.processEvents()

# The four sides of the unit square, as analytic line edges, in the order they
# were DRAWN — which is the order the edge list (and therefore the selection,
# which is index-sorted) hands them to the bake. This one is deliberately not
# the order they connect in: bottom, top, right, left. Directions are mixed too,
# because a drawing session produces whatever direction the user drew in and the
# chain has to orient each edge itself.
SIDES = [((0.0, 0.0), (1.0, 0.0)),      # 0 bottom, left→right
         ((1.0, 1.0), (0.0, 1.0)),      # 1 top,    right→left  (not adjacent!)
         ((1.0, 0.0), (1.0, 1.0)),      # 2 right,  up
         ((0.0, 0.0), (0.0, 1.0))]      # 3 left,   drawn UPWARD (against the loop)

# The same square drawn the tidy way round, as the reference geometry.
SIDES_IN_ORDER = [((0.0, 0.0), (1.0, 0.0)),
                  ((1.0, 0.0), (1.0, 1.0)),
                  ((1.0, 1.0), (0.0, 1.0)),
                  ((0.0, 1.0), (0.0, 0.0))]


def add_line(session, p0, p1, n=11):
    seg = SegmentModel(session.project_model._next_curve_id, -1, -1)
    seg.type = "curve"
    seg.curve_type = "line"
    seg.curve_mode = "parametric"
    seg.parameters = {"n_points": n, "x0": p0[0], "y0": p0[1],
                      "x1": p1[0], "y1": p1[1]}
    cmd = AddCurveSegmentCmd(session, refresh_cb=c._refresh_segment_list,
                             select_cb=lambda i: None,
                             preconfigured_seg=seg)
    session.command_history.execute(cmd)
    return seg


def build_square(sides=SIDES):
    c.new_blank_tab()
    s = c.active_session()
    for p0, p1 in sides:
        add_line(s, p0, p1)
    c._refresh_segment_list()
    app.processEvents()
    return s


def select(session, indices):
    """Select edges by index in the model tree, as the user would."""
    tree = mw.sidebar_view.geometry_tree
    tree.clear_edge_selection()
    for i in indices:
        item = tree.edge_item_by_index(session.session_id, i)
        if item is not None:
            item.setSelected(True)
    session.current_segment_idx = indices[0]
    return sorted(c.get_selected_segment_indices())


def piece_count(points, tol):
    """How many disconnected runs the point array actually contains."""
    if points is None or len(points) < 2:
        return 0
    d = np.hypot(*(np.diff(points, axis=0).T))
    return 1 + int(np.count_nonzero(d > tol))


# ── 1/2. the WORST order converts to one connected boundary ────────────────
# Note the selection is index-sorted (get_selected_segment_indices), so the
# order that reaches the bake is the DRAWING order — bottom, top, right, left —
# and nothing the user does at selection time can improve on it.
sess = build_square()
picked = select(sess, [0, 1, 2, 3])
check(picked == [0, 1, 2, 3],
      f"(precondition) all four edges are selected ({picked})")
c.bake_selected_curve()
app.processEvents()

pts = sess.original_points
n_file = len([s for s in sess.project_model.segments if s.type == "file"])
n_curve = len([s for s in sess.project_model.segments if s.type == "curve"])
check(pts is not None and n_curve == 0,
      f"1. every selected analytic edge was converted ({n_curve} left)")
check(piece_count(pts, 0.5) == 1,
      f"1. the four sides bake into ONE connected run whatever order they were "
      f"DRAWN in ({piece_count(pts, 0.5)} pieces from bottom, top, right, left)")
check(n_file == 4, f"2. ...and the model still has one edge per side ({n_file})")
sess.project_model.resolve_closure(pts)
check(bool(sess.project_model.is_closed),
      "2. the baked boundary resolves CLOSED — the loop actually closed, it is "
      "not four pieces that happen to be near each other")

# The natural order must produce the same geometry, not merely a valid one.
ref = build_square(SIDES_IN_ORDER)
select(ref, [0, 1, 2, 3])
c.bake_selected_curve()
app.processEvents()
check(len(ref.original_points) == len(pts),
      f"1. the worst order and the natural order agree point for point "
      f"({len(pts)} vs {len(ref.original_points)})")

# ── 3. one action, one undo step ──────────────────────────────────────────
sess2 = build_square()
select(sess2, [0, 1, 2, 3])
before = len(sess2.command_history._undo_stack)
c.bake_selected_curve()
app.processEvents()
after = len(sess2.command_history._undo_stack)
check(after == before + 1,
      f"3. converting four edges is ONE undo step, not four (+{after - before})")
c.undo()
app.processEvents()
n_curve = len([s for s in sess2.project_model.segments if s.type == "curve"])
check(n_curve == 4 and sess2.original_points is None,
      f"3. one undo puts all four analytic edges back ({n_curve})")
c.redo()
app.processEvents()
check(len([s for s in sess2.project_model.segments if s.type == "file"]) == 4
      and piece_count(sess2.original_points, 0.5) == 1,
      "3. and redo re-bakes them in the same order (the indices are re-resolved "
      "to objects, so the second pass does not follow a stale list)")

# ── 4. two separate shapes: converted, but NOT bridged on the canvas ───────
FAR = [((0.0, 0.0), (1.0, 0.0)), ((1.0, 0.0), (1.0, 1.0)),      # near shape
       ((5.0, 0.0), (6.0, 0.0)), ((6.0, 0.0), (6.0, 1.0))]      # far shape
sep = build_square(FAR)
select(sep, [0, 1, 2, 3])
c.bake_selected_curve()
app.processEvents()
check(piece_count(sep.original_points, 0.5) == 2,
      f"4. two disjoint shapes stay two pieces "
      f"({piece_count(sep.original_points, 0.5)})")
conn = c._geometry_connect(sep.project_model, len(sep.original_points),
                           len(sep.original_points))
check(conn is not None and int(np.count_nonzero(conn == 0)) >= 2,
      "4. the canvas is told to BREAK the polyline at the gap (plus after the "
      "last point) instead of drawing a diagonal across it")
gap_at = int(np.argmax(np.hypot(*(np.diff(sep.original_points, axis=0).T))))
check(conn is not None and conn[gap_at] == 0,
      f"4. ...and the break is exactly at the gap (index {gap_at})")

# ── 5. a connected geometry keeps the plain fast path ─────────────────────
conn_ok = c._geometry_connect(sess.project_model, len(pts), len(pts))
check(conn_ok is None,
      "5. a fully connected boundary gets NO connect array — the break machinery "
      "must not touch the ordinary case")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
