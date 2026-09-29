#!/usr/bin/env python3
"""The offset generator, tested as a pure function on what it returns.

#152. ``app/services/geometry_offset.py`` is the ONE owner of the offset law, so
this gate drives it directly and asserts on the points that come back, never on
how it walks an array. Qt-free and binary-free: no display, no build tree.

What is checked, and why each is shaped this way:

  1. THE ARRAY IS THE SOURCE'S SHAPE. Same length, same order, one offset point
     per source point — which is what makes the source's split indices index the
     offset and mean the same thing. Checked as the index LIST, not as a count,
     because a count is equal for two different segmentations. A closed source
     that repeats its first vertex still comes back repeating it.
  2. A CIRCLE OFFSET BY d IS A CIRCLE OF r + d, MEASURED. Both numbers are
     stated: the exact miter radius ``r + d/cos(pi/n)``, which the law owes the
     polygon, and ``r + d`` to a tolerance that the discretisation explains. A
     test that only asserted the second would pass on a law that is wrong by less
     than the tolerance.
  3. A POLYGON'S CORNER LANDS ON THE BISECTOR. The square's corner, exactly.
  4. THE CLOSURE FLAG DECIDES THE TWO ENDS. The same points offset closed and
     open differ at the first and last vertex and nowhere else.
  5. THE SIDE IS SIGNED, AND "OUTWARD" COMES FROM THE WINDING. The same circle
     stored clockwise offsets outward for the same positive distance.
  6. A FOLD IS REFUSED AND THE REFUSAL CARRIES A NUMBER THAT WORKS. Both kinds:
     the concave-radius overrun (analytic bound) and the global crossing
     (bisected). In both the named distance is fed straight back in and must
     succeed — the check that makes the number advice rather than decoration.
  7. DEGENERACIES DO NOT PRODUCE NaN. A duplicated point in an imported outline
     has no edge direction of its own; the offset must still be finite
     everywhere, because one NaN poisons the whole geometry downstream.

NAMED BLIND SPOTS.

  * **The global crossing sweep is skipped above ``CROSSING_MAX_POINTS``**, so on
    a geometry larger than that only the local bound applies and a self-crossing
    offset would be produced. Check 6d pins the cap's value so the exemption
    cannot be widened silently, but nothing here drives a geometry that big.
  * **Nothing here offsets an analytic edge.** The service takes a point array;
    which points a session hands it is `test_offset_geometry_gui.py`'s.
  * **The refusal message's wording is not asserted**, only that it names the
    number it carries. Pinning the sentence would make this gate the thing a
    rewording has to edit.

INJECTIONS, run by hand 2026-09-29 against a copy of the tree; the exit code was
read as well as the FAIL lines, because a mutation that crashes the gate prints no
FAIL line at all.

  A  the miter denominator ``1 + na.nb`` becomes ``2``     -> 2a, 2c, 3a (9), exit 1
  B  the winding flip is dropped                           -> 5a, 5b, exit 1
  C  the open ends take a wrapped bisector                 -> 4c, exit 1
  D  ``_local_limit`` returns ``inf`` always               -> 6e, exit 1
  E  ``_crosses`` returns False always                     -> 6c (x3), exit 1
  F  ``largest_offset`` reports the bracket's MIDPOINT     -> 6c, exit 1
  G  the zero-length-edge carry-forward is removed         -> 7, exit 1
  H  the duplicated end point is not re-created            -> 1c, exit 1
  Q  `geometry_primitives.signed_area`'s sign is flipped   -> 2a, 2c, 5a (15), exit 1
  I  NEGATIVE CONTROL: a docstring edit                    -> inert, rightly

F AND G FIRST BIT BY CRASHING — exit 1 with ZERO FAIL lines, because the refusal
they provoked was raised through a check instead of reported by it. That is the
shape a FAIL-line count reads as silence, and it is why every expected success here
goes through ``try_offset``; the bite locations above are from the re-run, where
both print the check they break.

Run: python3 tools/PreProcessor/tests/test_geometry_offset.py
"""
import functools
import math
import os
import sys

import builtins

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

print = functools.partial(builtins.print, flush=True)
_FAILS = []
_RUN = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    _RUN.append(msg)
    if not cond:
        _FAILS.append(msg)


import numpy as np                                                 # noqa: E402
from app.services.geometry_offset import (                         # noqa: E402
    CROSSING_MAX_POINTS, OffsetRefused, largest_offset, offset_points,
)


def try_offset(points, distance, closed):
    """The offset, or ``None`` when it was refused.

    Every call that is only EXPECTED to succeed goes through this. A mutation that
    makes an expected success refuse would otherwise raise out of the check and end
    the run with no FAIL line printed at all — a real bite scoring as silence, which
    is the trap this repo reads exit codes for. Injections F and G both landed here.
    """
    try:
        return offset_points(points, distance, closed)
    except (OffsetRefused, ValueError):
        return None


def circle(n, r=1.0, ccw=True, repeat_first=False):
    t = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    if not ccw:
        t = -t
    p = np.column_stack((r * np.cos(t), r * np.sin(t)))
    if repeat_first:
        p = np.vstack((p, p[0]))
    return p


# ── 1. the array is the source's shape ────────────────────────────────────── #

N = 720
src = circle(N)
out = offset_points(src, 0.1, True)
check(out.shape == src.shape,
      "1a. the offset has the source's shape (%r vs %r)" % (out.shape, src.shape))

splits = [0, 137, 400, N - 1]
check(all(0 <= i < len(out) for i in splits)
      and [int(i) for i in splits] == [0, 137, 400, N - 1],
      "1b. the source's split index LIST still indexes the offset array (%r)"
      % (splits,))

rep = circle(24, repeat_first=True)
rep_out = offset_points(rep, 0.1, True)
check(len(rep_out) == len(rep)
      and float(np.hypot(*(rep_out[0] - rep_out[-1]))) < 1e-12,
      "1c. a closed source that repeats its first vertex comes back the same "
      "length and still repeating (%d vs %d)" % (len(rep_out), len(rep)))

check(float(np.hypot(*(offset_points(src, 0.0, True)[5] - src[5]))) == 0.0,
      "1d. a zero offset is the source itself")


# ── 2. a circle offset by d is a circle of r + d ──────────────────────────── #

D = 0.1
rad = np.hypot(out[:, 0], out[:, 1])
exact = 1.0 + D / math.cos(math.pi / N)
check(float(np.abs(rad - exact).max()) < 1e-12,
      "2a. the outward offset is the miter radius r + d/cos(pi/n) exactly "
      "(worst %.3e)" % float(np.abs(rad - exact).max()))
check(float(np.abs(rad - (1.0 + D)).max()) < 1e-6,
      "2b. ...which IS r + d to 1e-6; the residue is the polygon's own "
      "discretisation (worst %.3e)" % float(np.abs(rad - (1.0 + D)).max()))

inn = np.hypot(*offset_points(src, -0.3, True).T)
check(float(np.abs(inn - (1.0 - 0.3 / math.cos(math.pi / N))).max()) < 1e-12,
      "2c. a NEGATIVE distance goes inward by the same law (%.9f)"
      % float(inn.mean()))


# ── 3. a polygon's corner lands on the bisector ───────────────────────────── #

square = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
sq = offset_points(square, 0.1, True)
want = np.array([[-0.1, -0.1], [1.1, -0.1], [1.1, 1.1], [-0.1, 1.1]])
check(float(np.abs(sq - want).max()) < 1e-15,
      "3a. every corner of a square lands on its own bisector, d*sqrt(2) out "
      "(worst %.3e)" % float(np.abs(sq - want).max()))
diag = (sq[1] - square[1]) / np.hypot(*(sq[1] - square[1]))
check(abs(diag[0] - 1 / math.sqrt(2)) < 1e-12 and abs(diag[1] + 1 / math.sqrt(2)) < 1e-12,
      "3b. ...and the direction is the angle bisector, not the edge normal (%r)"
      % (diag.round(9).tolist(),))


# ── 4. the closure flag decides the two ends ──────────────────────────────── #

ell = np.array([[0.0, 1.0], [0.0, 0.0], [1.0, 0.0]])
op = offset_points(ell, 0.2, False)
cl = offset_points(ell, 0.2, True)
check(float(np.hypot(*(op[1] - cl[1]))) < 1e-15,
      "4a. the interior vertex is the same whether the curve closes or not")
check(float(np.hypot(*(op[0] - cl[0]))) > 1e-9
      and float(np.hypot(*(op[2] - cl[2]))) > 1e-9,
      "4b. ...while BOTH ends differ: open takes the end normal, closed a "
      "bisector (%.4f / %.4f)"
      % (float(np.hypot(*(op[0] - cl[0]))), float(np.hypot(*(op[2] - cl[2])))))
check(abs(op[0][0] + 0.2) < 1e-15 and abs(op[0][1] - 1.0) < 1e-15
      and abs(op[2][0] - 1.0) < 1e-15 and abs(op[2][1] + 0.2) < 1e-15,
      "4c. BOTH open ends move exactly d along their own edge's normal "
      "(%r, %r)" % (op[0].round(12).tolist(), op[2].round(12).tolist()))


# ── 5. the side is signed, and outward comes from the winding ─────────────── #

cw = circle(N, ccw=False)
cw_out = offset_points(cw, D, True)
check(float(np.abs(np.hypot(*cw_out.T) - exact).max()) < 1e-12,
      "5a. a CLOCKWISE circle offsets OUTWARD for the same positive distance "
      "(%.9f)" % float(np.hypot(*cw_out.T).mean()))
check(float(np.abs(np.hypot(*offset_points(cw, -0.3, True).T)
                   - (1.0 - 0.3 / math.cos(math.pi / N))).max()) < 1e-12,
      "5b. ...and inward for the same negative one")
line = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
check(float(np.abs(offset_points(line, 0.2, False)[:, 1] + 0.2).max()) < 1e-15,
      "5c. an OPEN polyline has no inside, so positive is the right of travel")


# ── 6. a fold is refused, and the number it names works ───────────────────── #

refused = None
try:
    offset_points(src, -1.5, True)
except OffsetRefused as e:
    refused = e
check(refused is not None,
      "6a. an offset past the tightest concave radius is REFUSED")
check(refused is not None and ("%.6g" % refused.max_distance) in str(refused),
      "6a. ...and the refusal NAMES the largest distance that works (%r)"
      % (refused and str(refused),))
check(refused is not None and refused.max_distance < 0.0
      and abs(abs(refused.max_distance) - 1.0) < 1e-4,
      "6a. ...which is the circle's own radius, on the side asked for (%.8f)"
      % (refused.max_distance if refused else 0.0))
back = try_offset(src, refused.max_distance, True) if refused else None
check(back is not None and np.all(np.isfinite(back)),
      "6b. THE NAMED DISTANCE, FED BACK IN, SUCCEEDS — the check that makes it "
      "advice and not decoration")

# A horseshoe: every edge keeps its direction, yet the two tips cross.
t1 = np.radians(np.linspace(20.0, 340.0, 120))
t2 = np.radians(np.linspace(340.0, 20.0, 120))
horse = np.vstack((np.column_stack((np.cos(t1), np.sin(t1))),
                   np.column_stack((0.6 * np.cos(t2), 0.6 * np.sin(t2)))))
check(try_offset(horse, 0.1, True) is not None,
      "6c. (precondition) a horseshoe offsets fine well inside its mouth")
cross = None
try:
    offset_points(horse, 0.3, True)
except OffsetRefused as e:
    cross = e
check(cross is not None,
      "6c. a GLOBAL crossing is refused too, with no edge having reversed")
check(cross is not None and 0.0 < cross.max_distance < 0.3,
      "6c. ...and its bound is bisected below the requested distance (%.6f)"
      % (cross.max_distance if cross else -1))
_back2 = try_offset(horse, cross.max_distance, True) if cross else None
check(_back2 is not None and np.all(np.isfinite(_back2)),
      "6c. ...and that one, fed back in, succeeds as well")
check(CROSSING_MAX_POINTS == 4000,
      "6d. the crossing sweep's point cap is the value the blind spot names "
      "(%d)" % CROSSING_MAX_POINTS)
check(abs(largest_offset(src, True, -1.0) - refused.max_distance) < 1e-9
      if refused else False,
      "6e. largest_offset with no ceiling agrees with the refusal's number")


# ── 7. degeneracies stay finite ───────────────────────────────────────────── #

dup = np.vstack((square[:2], square[1:2], square[2:]))     # a repeated vertex
dup_out = try_offset(dup, 0.1, True)
check(dup_out is not None and np.all(np.isfinite(dup_out))
      and len(dup_out) == len(dup),
      "7. a duplicated point produces no NaN and costs no point (%r)"
      % (None if dup_out is None else len(dup_out),))


print("\n%d checks, %d failed" % (len(_RUN), len(_FAILS)))
if _FAILS:
    print("FAILED:")
    for f in _FAILS:
        print("  - " + f)
sys.exit(1 if _FAILS else 0)
