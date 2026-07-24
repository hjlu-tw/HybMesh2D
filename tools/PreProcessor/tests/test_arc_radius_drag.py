#!/usr/bin/env python3
"""R4-1: dragging the arc RADIUS handle ('m', the mid/rim point) must change the
radius about the FIXED centre — it used to re-fit a circle through the endpoints
and shift the centre.

Run: python3 tools/PreProcessor/tests/test_arc_radius_drag.py
"""
import os
import sys
import math
import functools

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


from app.models import shape_spec

CX, CY = 1.0, 2.0
base = {"cx": CX, "cy": CY, "r": 1.0, "theta0": 0.0, "theta1": math.pi / 2}

# Drag the mid/radius handle to a point 2.0 from the centre (along 45°).
p = dict(base)
tm = 0.5 * (base["theta0"] + base["theta1"])
drag = (CX + 2.0 * math.cos(tm), CY + 2.0 * math.sin(tm))
shape_spec.apply_drag("arc", p, "m", drag[0], drag[1])
check(abs(p["cx"] - CX) < 1e-12 and abs(p["cy"] - CY) < 1e-12,
      f"radius drag keeps the centre fixed (got ({p['cx']}, {p['cy']}))")
check(abs(p["r"] - 2.0) < 1e-9, f"radius drag sets r to the new distance (got {p['r']})")
check(abs(p["theta0"] - 0.0) < 1e-12 and abs(p["theta1"] - math.pi / 2) < 1e-12,
      "radius drag keeps the sweep angles")

# Off-radial drag: r is the raw distance to the centre, centre still fixed.
p = dict(base)
shape_spec.apply_drag("arc", p, "m", CX + 3.0, CY + 4.0)
check(abs(p["cx"] - CX) < 1e-12 and abs(p["cy"] - CY) < 1e-12, "off-radial drag: centre fixed")
check(abs(p["r"] - 5.0) < 1e-9, f"off-radial drag: r = |drag-centre| (got {p['r']})")

# The centre handle still moves the centre; endpoints keep the centre fixed.
p = dict(base)
shape_spec.apply_drag("arc", p, "c", 7.0, 8.0)
check(abs(p["cx"] - 7.0) < 1e-12 and abs(p["cy"] - 8.0) < 1e-12, "'c' handle moves the centre")
p = dict(base)
shape_spec.apply_drag("arc", p, "p1", CX + 0.0, CY + 2.0)   # straight up, r=2
check(abs(p["cx"] - CX) < 1e-12 and abs(p["cy"] - CY) < 1e-12, "endpoint drag keeps the centre fixed")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    sys.exit(1)
print("RESULT: ALL PASS")
sys.exit(0)
