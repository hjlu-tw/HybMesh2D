#!/usr/bin/env python3
"""Item 3: the interactive endpoint weld tool. Picking a red open endpoint and a
target must MOVE the endpoint's underlying datum onto the target (weld), and be
undoable. Covers the file-polyline endpoint and an analytic (line) endpoint.

Run: python3 tools/PreProcessor/tests/test_endpoint_weld_gui.py
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


threading.Timer(60, lambda: (print("FAIL watchdog >60s"), os._exit(99))).start()

from PyQt6.QtWidgets import QApplication  # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402
from app.models.segment import SegmentModel  # noqa: E402

# ── File-polyline endpoint weld: start (0,0) → end (2,2), then undo ───────────
c = AppController()
sess = c.active_session()
pm = sess.project_model
pm.closed_mode = "open"
sess.original_points = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 2.0]], dtype=float)
sess.split_indices = [0, 2]
pm.update_file_segments_from_indices(sess.split_indices, points=sess.original_points)

c.handle_endpoint_weld(0.0, 0.0, 2.0, 2.0, True)   # weld start onto end
app.processEvents()
check(np.allclose(sess.original_points[0], [2.0, 2.0]),
      f"file: start welded onto end (got {sess.original_points[0]})")
c.undo(); app.processEvents()
check(np.allclose(sess.original_points[0], [0.0, 0.0]),
      f"file: undo restores start (got {sess.original_points[0]})")

# ── Analytic (line) endpoint weld: move its end p1 to (5,5), then undo ────────
c2 = AppController()
sess2 = c2.active_session()
pm2 = sess2.project_model
pm2.closed_mode = "open"
sess2.original_points = np.empty((0, 2), dtype=float)
ln = SegmentModel(1, -1, -1)
ln.type = "curve"; ln.curve_type = "line"; ln.curve_mode = "parametric"
ln.parameters = {"n_points": 11, "x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0}
pm2.segments = [ln]

c2.handle_endpoint_weld(1.0, 1.0, 5.0, 5.0, True)  # weld the line's END (1,1) → (5,5)
app.processEvents()
check(np.allclose([ln.parameters["x1"], ln.parameters["y1"]], [5.0, 5.0]),
      f"line: end welded to (5,5) (got {ln.parameters['x1']},{ln.parameters['y1']})")
c2.undo(); app.processEvents()
# undo deep-copies pm.segments, so read the restored object from the model
# (the local `ln` ref is the now-detached mutated copy).
lnr = pm2.segments[0]
check(np.allclose([lnr.parameters["x1"], lnr.parameters["y1"]], [1.0, 1.0]),
      f"line: undo restores end (got {lnr.parameters['x1']},{lnr.parameters['y1']})")

# ── Weld an arbitrary INTERIOR vertex (no open endpoints): pick middle point
#    (1,0) and weld it onto (9,9); then undo. Covers item: weld two specified
#    points even when the geometry is closed and shows no red warnings. ───────
c3 = AppController()
sess3 = c3.active_session()
pm3 = sess3.project_model
pm3.closed_mode = "closed"          # closed -> no open-endpoint warnings at all
sess3.original_points = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 2.0]], dtype=float)
sess3.split_indices = [0, 2]
pm3.update_file_segments_from_indices(sess3.split_indices, points=sess3.original_points)

# source (1,0) is an interior vertex, not an endpoint; target (9,9) is a free pt.
c3.handle_endpoint_weld(1.0, 0.0, 9.0, 9.0, True)
app.processEvents()
check(np.allclose(sess3.original_points[1], [9.0, 9.0]),
      f"vertex: interior point welded onto target (got {sess3.original_points[1]})")
check(np.allclose(sess3.original_points[0], [0.0, 0.0]),
      "vertex: other points untouched")
c3.undo(); app.processEvents()
check(np.allclose(sess3.original_points[1], [1.0, 0.0]),
      f"vertex: undo restores interior point (got {sess3.original_points[1]})")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
