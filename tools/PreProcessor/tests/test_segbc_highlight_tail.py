#!/usr/bin/env python3
"""R4-3: the edit-segment-BC highlight must cover the WHOLE edge. A segment's
shared END corner belongs (per the resampler) to the NEXT segment, so the
highlight used to stop one point short ("少一小段"). The highlighter now appends
the next boundary point so the polyline reaches the corner.

Run: python3 tools/PreProcessor/tests/test_segbc_highlight_tail.py
"""
import os
import sys
import tempfile
import functools
import threading

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

# Closed square, 2 points per side (corner + mid); loop closes back to point 0.
pts = [(0, 0), (0.5, 0),       # seg1: corner A, mid   (end vertex = corner B below)
       (1, 0), (1, 0.5),       # seg2: corner B, mid
       (1, 1), (0.5, 1),       # seg3: corner C, mid
       (0, 1), (0, 0.5)]       # seg4: corner D, mid   (end vertex wraps to corner A)
segids = [1, 1, 2, 2, 3, 3, 4, 4]

tmp = tempfile.mkdtemp()
dat = os.path.join(tmp, "sq.dat")
with open(dat, "w") as f:
    f.write("\n".join(f"{x} {y}" for x, y in pts) + "\n")
with open(dat + ".meta", "w") as f:
    f.write("HYBMESH_META 3\nCOUNT 8\nNPIECES 0\nNSEGMENTS 4\n")
    f.write("1 wall line 1\n2 wall line 1\n3 wall line 1\n4 wall line 1\n")
    f.write("POINTS 8\n" + "\n".join(f"{s} 0" for s in segids) + "\n")

from PyQt6.QtWidgets import QApplication  # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402

c = AppController()
panel = c.main_window.mesh_config_panel
hl = panel._segment_highlighter(dat)

captured = {}
panel.segment_highlight_requested.connect(lambda a: captured.__setitem__("a", a))

# seg1: own points are corner A (0,0) + mid (0.5,0); its END vertex is corner B
# (1,0), which belongs to seg2. The highlight must reach (1,0).
hl([1])
app.processEvents()
a = captured.get("a")
check(a is not None and len(a) == 3, f"seg1 highlight includes the end corner (got {0 if a is None else len(a)} pts)")
check(a is not None and np.allclose(a[-1], [1.0, 0.0]),
      f"seg1 highlight reaches corner B (1,0) — no missing tail (last={None if a is None else a[-1]})")

# seg4: wraps — its end vertex is corner A (0,0) at index 0.
hl([4])
app.processEvents()
a = captured.get("a")
check(a is not None and np.allclose(a[-1], [0.0, 0.0]),
      f"seg4 (wrap) highlight reaches corner A (0,0) (last={None if a is None else a[-1]})")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
