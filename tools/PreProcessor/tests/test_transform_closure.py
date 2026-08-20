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

USER-REQUESTED follow-up (2026-08-12): "duplicate 之後可以不要直接轉成 polygon,
而是保留原本的類型及參數嗎" — an arc is a similarity-invariant shape like the
circle beside it, so it now duplicates AS AN ARC (section 6): the centre moves
like a point, the radius scales, and the sweep is re-derived from the geometry,
which is what makes a MIRROR come back reversed (theta1 < theta0) instead of
inside out. Only the two kinds with no closed form under a transform — discrete
edges and formula curves — still bake, plus a circle/arc under a NON-uniform
scale, which is an ellipse the model cannot hold.

Checks (each: transform the edge, inspect the produced segment):
 1. an open arc duplicates OPEN (the reported bug), a full-circle arc closed
 2. an open formula curve duplicates open; a closed one (parametric circle) closed
 3. one sub-edge of a CLOSED imported geometry duplicates open...
 4. ...while the edge that spans the whole loop duplicates closed
 5. the type-preserving branches still inherit the flag (open polyline stays
    open, closed polygon stays closed) and keep their analytic type
 6. an arc keeps its type AND its parameters under every similarity transform
    (compared against the transformed sample points, i.e. the copy IS the
    source moved), and falls back to a polygon only under a non-uniform scale

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
from app.models.transform_spec import TransformSpec             # noqa: E402

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


# ── minimal stand-ins: the transform reads plain values off the sidebar ──────
def _sidebar(spec):
    """A stub sidebar that answers one question: what transform is set up?

    It used to have to fake the individual spin boxes and combo the controller
    read by name. The controller asks for a TransformSpec now, so the stub is
    the spec — which is the testability this seam was cut for.
    """
    return type("_Sidebar", (), {"transform_spec": staticmethod(lambda: spec)})()


def _Sidebar():
    """Translate by (10, 0) — a rigid motion, so closure cannot change."""
    return _sidebar(TransformSpec("translate", delta=(10.0, 0.0)))


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
check(out is not None and out.curve_type == "arc",
      "1. ...as an arc — the flag has to be right whether or not it is baked")
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

# ── 6. an arc duplicates as an ARC, parameters and all ─────────────────────
from app.services.geometry_service import GeometryService        # noqa: E402


def _Rotate90():
    """Rotate +90° about the origin."""
    return _sidebar(TransformSpec("rotate", angle_deg=90.0))


def _MirrorVertical():
    """Flip x about x = 0 — the orientation-REVERSING case."""
    return _sidebar(TransformSpec("mirror_v", axis_x=0.0))


def _ScaleUniform():
    return _sidebar(TransformSpec("scale", factors=(2.0, 2.0),
                                  scale_pivot=(0.0, 0.0)))


def _ScaleNonUniform():
    """Affine but not a similarity — a circle's image is an ellipse."""
    return _sidebar(TransformSpec("scale", factors=(2.0, 1.0),
                                  scale_pivot=(0.0, 0.0)))


def moved_points(seg):
    """The source arc's own samples, put through the active transform."""
    xs, ys = GeometryService.compute_curve_preview_pts(
        seg, seg.parameters.get("n_points", 50), session.original_points)
    return ctrl._apply_transform(np.asarray(xs, float), np.asarray(ys, float))


def copy_points(out):
    xs, ys = GeometryService.compute_curve_preview_pts(
        out, out.parameters.get("n_points", 50), session.original_points)
    return np.asarray(xs, float), np.asarray(ys, float)


src = curve("arc", {"cx": 0.3, "cy": -0.2, "r": 1.5,
                    "theta0": 0.4, "theta1": 0.4 + 1.9, "n_points": 60})
for name, sb in (("translate", _Sidebar()), ("rotate", _Rotate90()),
                 ("mirror", _MirrorVertical()), ("uniform scale", _ScaleUniform())):
    ctrl.main_window.sidebar_view = sb
    out = ctrl._build_transformed_segment(session, src, 7)
    ok_type = out is not None and out.curve_type == "arc"
    check(ok_type, f"6. an arc survives a {name} as an arc, not a polygon "
                   f"(got {getattr(out, 'curve_type', None)})")
    if not ok_type:
        continue
    check(abs(abs(out.parameters["theta1"] - out.parameters["theta0"])
              - 1.9) < 1e-9,
          f"6. ... keeping its 1.9 rad sweep under {name} "
          f"({out.parameters['theta1'] - out.parameters['theta0']:.6f})")
    ex, ey = moved_points(src)
    gx, gy = copy_points(out)
    err = float(max(np.max(np.abs(gx - ex)), np.max(np.abs(gy - ey))))
    check(err < 1e-9,
          f"6. ... and drawing exactly where the moved source does under "
          f"{name} (max error {err:.2e})")

ctrl.main_window.sidebar_view = _MirrorVertical()
out = ctrl._build_transformed_segment(session, src, 7)
check(out.parameters["theta1"] < out.parameters["theta0"],
      "6. a MIRRORED arc comes back with a reversed sweep (theta1 < theta0) — "
      "a reflection cannot preserve the direction of travel")

ctrl.main_window.sidebar_view = _ScaleUniform()
out = ctrl._build_transformed_segment(session, src, 7)
check(abs(out.parameters["r"] - 3.0) < 1e-9,
      f"6. a 2x uniform scale doubles the radius ({out.parameters['r']})")

# The cosmetic radius-grab handle is an angle on the same circle and has to
# travel with it; copied verbatim it lands somewhere the user never put it.
with_m = curve("arc", {"cx": 0.0, "cy": 0.0, "r": 1.0, "theta0": 0.0,
                       "theta1": math.pi / 2, "theta_m": math.pi / 4,
                       "n_points": 40})
ctrl.main_window.sidebar_view = _Rotate90()
out = ctrl._build_transformed_segment(session, with_m, 7)
check(abs(out.parameters["theta_m"] - 3.0 * math.pi / 4) < 1e-9,
      f"6. the radius-grab handle rotates with the arc "
      f"({math.degrees(out.parameters['theta_m']):.1f}°, expected 135°)")
plain = curve("arc", {"cx": 0.0, "cy": 0.0, "r": 1.0, "theta0": 0.0,
                      "theta1": math.pi / 2, "n_points": 40})
out = ctrl._build_transformed_segment(session, plain, 7)
check("theta_m" not in out.parameters,
      "6. ...and an arc that never had one does not acquire one (it would pin "
      "the handle instead of leaving it at the sweep midpoint)")

ctrl.main_window.sidebar_view = _ScaleNonUniform()
out = ctrl._build_transformed_segment(session, src, 7)
check(out is not None and out.curve_type == "polygon",
      "6. a NON-uniform scale still bakes: the image is an ellipse arc, which "
      "the arc model (one radius) cannot hold")
ctrl.main_window.sidebar_view = _Sidebar()

full = curve("arc", {"cx": 0.0, "cy": 0.0, "r": 1.0,
                     "theta0": 0.0, "theta1": 2.0 * math.pi, "n_points": 40})
ctrl.main_window.sidebar_view = _MirrorVertical()
out = ctrl._build_transformed_segment(session, full, 7)
check(out is not None and out.curve_type == "arc"
      and abs(abs(out.parameters["theta1"] - out.parameters["theta0"])
              - 2.0 * math.pi) < 1e-9 and out.closed is True,
      "6. a mirrored FULL-turn arc keeps a full turn and stays closed — the "
      "sweep sign is read off a QUARTER point, because the midpoint's cross "
      "product vanishes at exactly this sweep")
ctrl.main_window.sidebar_view = _Sidebar()

print(("\nRESULT: " + ("ALL PASS" if not _FAILS else f"{len(_FAILS)} FAIL")), flush=True)
sys.exit(1 if _FAILS else 0)
