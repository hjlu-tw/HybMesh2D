#!/usr/bin/env python3
"""Duplicating an OPEN edge must not hand back a closed one.

USER-REPORTED (2026-08-11): "把開放線段 duplicate 之後不要自動變成密閉線段"
— duplicate an open edge and the copy comes back closed.

Why it happened: ``SegmentModel.closed`` defaults to True and is only ever
consulted for ``curve_type == "polygon"`` (GeometryService.compute_curve_preview_pts
appends the first vertex again when it is set). Every other kind of edge —
an arc, a formula curve, one sub-edge of an imported outline — therefore carries
``closed=True`` while drawing perfectly open, because nothing reads the flag.
The transform bakes exactly those kinds into a Polygon (they have no closed-form
image under the transform), at which point the inherited flag suddenly MEANS
something and adds a closing chord. The discrete-edge branch was wrong in the
same direction for a different reason: it took the closure of the whole
PROJECT, so one segment of a closed imported loop copied as a closed polygon.

The copy's closure is now derived from the source edge's own points
(``detect_closed``, the same spacing-relative rule the CAD tab uses), except for
an arc, which is decided by its sweep — a nearly-full arc's endpoint gap can sit
inside the spacing tolerance, and for an arc "closed" means 'goes all the way
round'.

Checks (each: transform the edge, inspect the produced segment):
 1. an open arc duplicates OPEN (the reported bug), a full-circle arc closed
 2. an open formula curve duplicates open; a closed one (parametric circle) closed
 3. one sub-edge of a CLOSED imported geometry duplicates open...
 4. ...while the edge that spans the whole loop duplicates closed
 5. the type-preserving branches still inherit the flag (open polyline stays
    open, closed polygon stays closed) and keep their analytic type

Run:  python3 tools/PreProcessor/tests/test_transform_closure.py
"""
import math
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

import numpy as np                                              # noqa: E402

from app.controllers.transform_apply_ctrl import (              # noqa: E402
    TransformApplyControllerMixin)
from app.models.segment import SegmentModel                     # noqa: E402

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


# ── minimal stand-ins: the transform reads plain values off the sidebar ──────
class _Spin:
    def __init__(self, v):
        self._v = v

    def value(self):
        return self._v


class _Combo:
    def __init__(self, i):
        self._i = i

    def currentIndex(self):
        return self._i


class _Sidebar:
    """Translate by (10, 0) — a rigid motion, so closure cannot change."""
    dup_type_combo = _Combo(5)
    dup_trans_dx = _Spin(10.0)
    dup_trans_dy = _Spin(0.0)


class _MainWindow:
    sidebar_view = _Sidebar()


class _ProjectModel:
    def __init__(self, is_closed=True):
        self.is_closed = is_closed
        self._next_curve_id = 99


class _Session:
    def __init__(self, points, is_closed=True):
        self.original_points = points
        self.project_model = _ProjectModel(is_closed)


class _Ctrl(TransformApplyControllerMixin):
    def __init__(self):
        self.main_window = _MainWindow()


ctrl = _Ctrl()

# A closed square outline, resampled the way an imported .dat is (no repeated
# last point — the closure shows up as one edge-length gap).
side = np.linspace(0.0, 1.0, 11)[:-1]
loop = np.vstack([
    np.column_stack([side, np.zeros_like(side)]),
    np.column_stack([np.ones_like(side), side]),
    np.column_stack([1.0 - side, np.ones_like(side)]),
    np.column_stack([np.zeros_like(side), 1.0 - side]),
])
session = _Session(loop, is_closed=True)


def curve(curve_type, params, **kw):
    seg = SegmentModel(1, -1, -1)
    seg.type = "curve"
    seg.curve_type = curve_type
    seg.curve_mode = kw.pop("curve_mode", "parametric")
    seg.parameters = dict(params)
    for k, v in kw.items():
        setattr(seg, k, v)
    return seg


# ── 1. arcs ─────────────────────────────────────────────────────────────────
arc = curve("arc", {"cx": 0.0, "cy": 0.0, "r": 1.0,
                    "theta0": 0.0, "theta1": math.pi / 2, "n_points": 40})
out = ctrl._build_transformed_segment(session, arc, 5)
check(out is not None and out.closed is False,
      f"1. a quarter arc duplicates OPEN (closed={getattr(out, 'closed', None)})")
check(out is not None and getattr(arc, "closed", True) is True,
      "1. ...even though the source arc carries the closed=True default")

nearly = curve("arc", {"cx": 0.0, "cy": 0.0, "r": 1.0,
                       "theta0": 0.0, "theta1": math.radians(350), "n_points": 40})
out = ctrl._build_transformed_segment(session, nearly, 5)
check(out is not None and out.closed is False,
      "1. a 350° arc is still OPEN — sweep decides, not the endpoint gap")

full = curve("arc", {"cx": 0.0, "cy": 0.0, "r": 1.0,
                     "theta0": 0.0, "theta1": 2.0 * math.pi, "n_points": 40})
out = ctrl._build_transformed_segment(session, full, 5)
check(out is not None and out.closed is True,
      "1. a full-turn arc duplicates CLOSED")

# ── 2. custom formula curves ────────────────────────────────────────────────
open_formula = curve("custom", {"n_points": 40})
open_formula.x_formula, open_formula.y_formula = "t", "t*t"
open_formula.t_min, open_formula.t_max = 0.0, 1.0
out = ctrl._build_transformed_segment(session, open_formula, 5)
check(out is not None and out.closed is False,
      "2. an open formula curve duplicates open")

closed_formula = curve("custom", {"n_points": 60})
closed_formula.x_formula, closed_formula.y_formula = "cos(t)", "sin(t)"
closed_formula.t_min, closed_formula.t_max = 0.0, 2.0 * math.pi
out = ctrl._build_transformed_segment(session, closed_formula, 5)
check(out is not None and out.closed is True,
      "2. a formula curve whose ends meet duplicates closed")

# ── 3/4. discrete (file) edges of a CLOSED imported geometry ────────────────
part = SegmentModel(2, 0, 9)            # one side of the square
part.type = "file"
out = ctrl._build_transformed_segment(session, part, 5)
check(out is not None and out.closed is False,
      "3. one sub-edge of a closed imported outline duplicates OPEN")

whole = SegmentModel(3, 0, len(loop))   # spans the loop (end index wraps)
whole.type = "file"
out = ctrl._build_transformed_segment(session, whole, 5)
check(out is not None and out.closed is True,
      "4. the edge spanning the whole closed loop duplicates closed")

# ── 5. the type-preserving branches are untouched ───────────────────────────
polyline = curve("polygon", {"vertices_str": "0,0; 1,0; 1,1", "n_points": 30},
                 closed=False)
out = ctrl._build_transformed_segment(session, polyline, 5)
check(out is not None and out.curve_type == "polygon" and out.closed is False,
      "5. an open polyline keeps its type AND stays open")

poly = curve("polygon", {"vertices_str": "0,0; 1,0; 1,1", "n_points": 30},
             closed=True)
out = ctrl._build_transformed_segment(session, poly, 5)
check(out is not None and out.curve_type == "polygon" and out.closed is True,
      "5. a closed polygon stays closed")

line = curve("line", {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0, "n_points": 20})
out = ctrl._build_transformed_segment(session, line, 5)
check(out is not None and out.curve_type == "line",
      "5. a line still duplicates as a line (analytic, not baked)")

circle = curve("circle", {"cx": 0.0, "cy": 0.0, "r": 1.0, "n_points": 40})
out = ctrl._build_transformed_segment(session, circle, 5)
check(out is not None and out.curve_type == "circle" and out.closed is True,
      "5. a circle still duplicates as a circle")

print(("\nRESULT: " + ("ALL PASS" if not _FAILS else f"{len(_FAILS)} FAIL")), flush=True)
sys.exit(1 if _FAILS else 0)
