#!/usr/bin/env python3
"""R4-2: converting two open edges (drawn to chain) to discrete must WELD their
nearby endpoints into ONE connected polyline — not leave a gap / phantom bridge,
and never a spurious line to the FAR endpoint. Far-apart edges stay separate
pieces with no phantom.

Run: python3 tools/PreProcessor/tests/test_bake_weld_gui.py
"""
import os
import sys
import threading
import functools


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


def line(cid, x0, y0, x1, y1):
    s = SegmentModel(cid, -1, -1)
    s.type = "curve"; s.curve_type = "line"; s.curve_mode = "parametric"
    s.parameters = {"n_points": 11, "x0": x0, "y0": y0, "x1": x1, "y1": y1}
    return s


def files(pm):
    return [s for s in pm.segments if s.type == "file"]


def bake_two(bx0):
    """Two line edges; second starts at (bx0, 0). Bake both to discrete."""
    c = AppController()
    sess = c.active_session()
    pm = sess.project_model
    pm.segments = [line(1, 0, 0, 1, 0), line(2, bx0, 0.0, 2.0, 0.0)]
    sess.current_segment_idx = 0
    c.bake_selected_curve()
    app.processEvents()
    # after baking edge 1, edge 2 (curve) is still at index 1
    sess.current_segment_idx = [i for i, s in enumerate(pm.segments)
                                if s.type == "curve"][0]
    c.bake_selected_curve()
    app.processEvents()
    return sess, pm


# ── Nearby endpoints (0.001 apart) → WELD into one connected chain ────────────
sess, pm = bake_two(1.001)
fs = files(pm)
check(len(fs) == 2, f"near case: 2 discrete edges, no phantom (got {len(fs)})")
if len(fs) == 2:
    fs = sorted(fs, key=lambda s: s.start_index)
    check(fs[0].end_index == fs[1].start_index,
          f"near case: edges WELDED (share boundary {fs[0].end_index}/{fs[1].start_index})")
check(len(sess.original_points) == 21,
      f"near case: joint point de-duplicated (21 pts, got {len(sess.original_points)})")

# ── Far endpoints (4 apart) → separate pieces, still NO phantom ───────────────
sess, pm = bake_two(5.0)
fs = files(pm)
check(len(fs) == 2, f"far case: 2 discrete edges, no phantom bridge (got {len(fs)})")
if len(fs) == 2:
    fs = sorted(fs, key=lambda s: s.start_index)
    check(fs[0].end_index != fs[1].start_index,
          "far case: edges stay disjoint (not welded)")
check(len(sess.original_points) == 22,
      f"far case: both edges kept whole (22 pts, got {len(sess.original_points)})")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
