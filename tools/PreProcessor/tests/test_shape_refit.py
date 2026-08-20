#!/usr/bin/env python3
"""Re-fitting an imported outline from its moving corners — the arithmetic alone.

Architecture backlog candidate 7, ticket 2 (issue #16), included prefactor.
Double-clicking an imported (discrete) edge opens the WHOLE connected outline for
editing by its corner vertices; each edge re-fits between its own two corners, so
dragging a corner two edges share redistributes both. That is a similarity
transform per edge, computed from the edge's ORIGINAL layout.

It lived inside ``FileEditControllerMixin._refit_geom``, read three ``self.``
attributes on the god object, mutated the live session's point array in place —
and had **no test at all**. ``services/shape_refit.py`` is the same arithmetic
over values. What this pins:

1. A RIGID EDGE STAYS RIGID. Interior points ride the rotation + uniform scale
   that carries the original corner pair onto the current one, so a straight
   edge stays straight and an edge's own shape is preserved under the drag. Two
   independent transforms are checked (a pure translation, and a rotate+scale)
   rather than only a translation, which the degenerate branch would also pass.

2. A SHARED CORNER MOVES BOTH ITS EDGES. This is the whole feature: the corner
   is one entry in the position map and both specs read it, so a single drag
   re-fits two edges. Testing one edge in isolation cannot see it.

3. THE ZERO-LENGTH EDGE FALLS BACK TO A PURE TRANSLATION. Two coincident corners
   define no direction and the transform's divisor is the squared length, so
   without the fallback the interior points are scaled by a division by ~zero
   and leave the canvas.

4. THE CLOSING EDGE WRAPS TO INDEX 0 RATHER THAN BEING SKIPPED. An outline's
   last edge runs from its final corner back to the first point and says so with
   an ``end_index`` one past the end of the array. Read as out-of-range and
   dropped, the closing run of points stays frozen while the corners either side
   of it move — a gap that opens only on a CLOSED outline, which is most of them.

5. THE FUNCTION IS PURE. The pristine array is not written to, so every re-fit
   recomputes from the same basis: dragging never accumulates transform onto
   transform, and the revert on Cancel is exact rather than approximate.

6. HANDLE ORDER IS STABLE. The corners come back sorted, not in a set's
   iteration order — the canvas shows one handle per corner in that order.
   Measured: the obvious small-index outline (corners 0, 2, 4) CANNOT show this,
   because a CPython set of small ints happens to iterate in sorted order, so
   dropping the ``sorted()`` passes. Check 6b uses corners 1/8/17/24, whose set
   iterates ``[8, 1, 17, 24]``.

Note on check 3: removing the degenerate-edge fallback makes this test RAISE
(``ZeroDivisionError`` on the transform's divisor) rather than report a failure.
That is a catch, not a gap — but the assertion after it, "no NaN or infinity",
never gets to run, so do not read it as the thing holding the fallback in place.

Run:  python3 tools/PreProcessor/tests/test_shape_refit.py
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "gui"))

import numpy as np  # noqa: E402

from app.services.shape_refit import (  # noqa: E402
    EdgeSpec, build_edge_specs, refit_shape)

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def close(a, b, tol=1e-9):
    return np.allclose(np.asarray(a, float), np.asarray(b, float), atol=tol)


class _Seg:
    def __init__(self, start_index, end_index, type="file"):
        self.type = type
        self.start_index = start_index
        self.end_index = end_index


# ══ Spec building ═══════════════════════════════════════════════════════════
# A 6-point closed outline cut into 3 edges: 0-2, 2-4, and 4-back-to-0 (whose
# end_index is 6 == len, the "wraps to the first point" spelling).
segs = [_Seg(0, 2), _Seg(2, 4), _Seg(4, 6)]
specs, corners = build_edge_specs(segs, 6)
check("6 corners come back sorted (= stable handle order)", corners == [0, 2, 4])
check("4a the closing edge is kept, with i1 == 0",
      len(specs) == 3 and specs[2].i0 == 4 and specs[2].i1 == 0)
check("4b …and its interior is the whole tail, not empty",
      specs[2].interior == (5,))
check("spec interiors are the points strictly between the corners",
      specs[0].interior == (1,) and specs[1].interior == (3,))

# The order must be SORTED, not the corner set's iteration order. Finding a case
# that can SHOW that took searching: a CPython set of small ints iterates sorted
# anyway, and the order also depends on the insertion history rather than the
# values, so a set literal is not a usable oracle either — set([1,8,17,24,0])
# iterates [0,1,17,8,24] while the same members ADDED in the builder's order come
# out [0,1,8,17,24]. This layout is one the builder really orders wrongly without
# the sort, found by search over 200k random cuts.
wide = [_Seg(4, 5), _Seg(5, 7), _Seg(7, 26), _Seg(26, 35), _Seg(35, 39)]
_specs_w, corners_w = build_edge_specs(wide, 39)
check("6b corners are sorted even where the builder's own set is not "
      "(unsorted there: [0, 35, 4, 5, 7, 26])",
      corners_w == [0, 4, 5, 7, 26, 35])

mixed = build_edge_specs([_Seg(0, 2), _Seg(2, 4, type="curve"),
                          _Seg(3, 3), _Seg(9, 11)], 6)[0]
check("an analytic edge, a zero-span segment and an out-of-range one are dropped",
      len(mixed) == 1 and mixed[0].i0 == 0)

# ══ 1a: a pure translation of one corner pair ═══════════════════════════════
orig = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]])
spec = [EdgeSpec(0, 2, (1,))]
out = refit_shape(orig, spec, {0: [10.0, 5.0], 2: [12.0, 5.0]})
check("1a a translated edge translates its interior point rigidly",
      close(out[1], [11.0, 6.0]) and close(out[0], [10.0, 5.0])
      and close(out[2], [12.0, 5.0]))

# ══ 1b: rotate 90° CCW about the first corner, and scale ×2 ═════════════════
# Original edge (0,0)→(2,0); move it to (0,0)→(0,4): a ×2 scale and a +90° turn.
# The interior point (1,1) must land at 2·R90·(1,1) = (-2, 2).
out = refit_shape(orig, spec, {0: [0.0, 0.0], 2: [0.0, 4.0]})
check("1b interior points ride the edge's rotation AND uniform scale",
      close(out[1], [-2.0, 2.0]))

# The transform is a similarity, so the interior point's angle to the edge and
# its fractional distance along it are both preserved — checked independently of
# the expected coordinate above, so a sign slip in B cannot pass both.
def _shape_of(pts, i0, i1, i):
    v = np.asarray(pts[i1], float) - np.asarray(pts[i0], float)
    w = np.asarray(pts[i], float) - np.asarray(pts[i0], float)
    return (np.linalg.norm(w) / np.linalg.norm(v),
            math.atan2(v[0] * w[1] - v[1] * w[0], v[0] * w[0] + v[1] * w[1]))


check("1c …so the interior point's angle and relative distance are preserved",
      close(_shape_of(orig, 0, 2, 1), _shape_of(out, 0, 2, 1)))

# ══ 2: a corner two edges share moves BOTH ══════════════════════════════════
# Square-ish outline, corners at 0, 2, 4; one interior point per edge.
orig2 = np.array([[0.0, 0.0], [0.5, 0.5],      # edge A: 0 → 2
                  [1.0, 0.0], [1.5, -0.5],     # edge B: 2 → 4
                  [2.0, 0.0], [1.0, -1.0]])    # edge C (closing): 4 → 0
specs2 = [EdgeSpec(0, 2, (1,)), EdgeSpec(2, 4, (3,)), EdgeSpec(4, 0, (5,))]
pos = {0: [0.0, 0.0], 2: [1.0, 1.0], 4: [2.0, 0.0]}   # corner 2 dragged up
out2 = refit_shape(orig2, specs2, pos)
check("2a the shared corner itself lands where it was dragged",
      close(out2[2], [1.0, 1.0]))
check("2b the edge BEFORE it re-fitted", not close(out2[1], orig2[1]))
check("2c the edge AFTER it re-fitted too", not close(out2[3], orig2[3]))
check("2d the edge touching neither moved corner is untouched",
      close(out2[5], orig2[5]))
check("2e both re-fits are similarities of their own edge",
      close(_shape_of(orig2, 0, 2, 1), _shape_of(out2, 0, 2, 1))
      and close(_shape_of(orig2, 2, 4, 3), _shape_of(out2, 2, 4, 3)))

# ══ 3: a zero-length edge translates instead of exploding ═══════════════════
degen = np.array([[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]])   # all three coincide
out3 = refit_shape(degen, [EdgeSpec(0, 2, (1,))],
                   {0: [5.0, 5.0], 2: [5.0, 5.0]})
check("3a a zero-length edge translates its interior rigidly",
      close(out3[1], [5.0, 5.0]))
check("3b …and produces no NaN or infinity", np.all(np.isfinite(out3)))

# An interior point offset from a zero-length edge keeps its offset.
degen2 = np.array([[1.0, 1.0], [1.0, 3.0], [1.0, 1.0]])
out3b = refit_shape(degen2, [EdgeSpec(0, 2, (1,))],
                    {0: [5.0, 0.0], 2: [5.0, 0.0]})
check("3c …carrying its offset from the collapsed corner with it",
      close(out3b[1], [5.0, 2.0]))

# ══ 4c: the closing edge really re-fits (the whole-outline check) ═══════════
pos4 = {0: [0.0, 0.0], 2: [1.0, 0.0], 4: [2.0, 2.0]}   # move the LAST corner
out4 = refit_shape(orig2, specs2, pos4)
check("4c moving the last corner re-fits the CLOSING edge's interior",
      not close(out4[5], orig2[5]))
check("4d …as a similarity of the closing edge (corner 4 → corner 0)",
      close(_shape_of(orig2, 4, 0, 5), _shape_of(out4, 4, 0, 5)))

# ══ 5: purity ═══════════════════════════════════════════════════════════════
before = orig2.copy()
_ = refit_shape(orig2, specs2, pos)
check("5a the pristine array is not mutated", close(orig2, before))
again = refit_shape(orig2, specs2, pos)
check("5b re-fitting twice from the same basis gives the same answer",
      close(again, out2))
check("5c the result is a new array, not the input", again is not orig2)

# Dragging a corner out and back must land exactly on the original — the
# property that makes Cancel exact, and the one an accumulating re-fit loses.
far = refit_shape(orig2, specs2, {0: [0.0, 0.0], 2: [7.0, -3.0], 4: [2.0, 0.0]})
back = refit_shape(orig2, specs2, {0: [0.0, 0.0], 2: [1.0, 0.0], 4: [2.0, 0.0]})
check("5d a corner dragged away and back reproduces the original exactly: "
      f"max |Δ| = {float(np.max(np.abs(back - orig2))):g}",
      np.array_equal(back, orig2) and not close(far, orig2))

# A point in no edge's interior and no corner keeps its position.
loose = np.array([[0.0, 0.0], [0.5, 0.5], [1.0, 0.0], [9.0, 9.0]])
out5 = refit_shape(loose, [EdgeSpec(0, 2, (1,))],
                   {0: [0.0, 0.0], 2: [2.0, 0.0]})
check("5e a point belonging to no edge keeps its original position",
      close(out5[3], [9.0, 9.0]))

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All shape re-fit checks passed.")
