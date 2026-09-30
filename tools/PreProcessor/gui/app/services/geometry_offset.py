"""A curve offset from one the user already drew. Qt-free, and the ONE owner.

#152, parent #150. A ring of cells between a body and its far field needs a curve
partway between them for the ring's outer edge to attach to. For a circle a user
could draw a second circle; for an aerofoil, or for anything drawn by hand, there
was no way to get that curve short of computing it outside the tool.

THE OFFSET IS A PURE FUNCTION OF (points, distance, closed), AND NOTHING ELSE.
#150's developer story asks for ONE owner "so that the canvas preview and the
thing that writes the geometry cannot produce different curves". THERE ARE TWO
CALLERS SINCE #154, and neither is the preview: the CAD-stage creation path
(`controllers/offset_geom_ctrl`) and `services/derived_geoms`, which produces a
curve a pipeline script describes by its RECORD rather than by a file. That
second one is what makes the story's own comparison real for the first time —
the headless runner and the GUI's script loader both reach the law through it,
so the two hosts cannot open different curves. A canvas preview is still not
among them, and when one is drawn it calls this and nothing else. Stated this
way round, and re-counted rather than carried forward, because #152's draft of
this paragraph asserted a second caller that did not exist and had to be
reversed; a count that is merely old is the same defect with the sign flipped.
It is the reason this is a service rather than a method on the controller that
happens to need it. It is numpy-only: no Qt, gated by
``tests/test_qt_free_seam.py``'s ``services/`` sweep.

WHAT COMES BACK IS AN ORDINARY POINT ARRAY OF THE SAME LENGTH. One offset point
per source point, in the same order, so the caller's segment boundaries — which
are INDICES into that array — mean the same thing on the offset as they do on the
source. That is what makes "segmented exactly as its source" true by construction
rather than by re-segmenting, and it is why this function refuses to drop, insert
or merge a point under any circumstances.

THE VERTEX DIRECTION IS THE MITER, WHICH IS THE ANGLE BISECTOR. At a vertex whose
two adjacent edge normals are ``na`` and ``nb``, the point that lies on BOTH
offset lines is ``p + d * (na + nb) / (1 + na.nb)``. Its direction is the bisector
and its length is ``1 / cos(half the turn)``, so the offset of a polygon inscribed
in a circle of radius ``r`` comes back inscribed in ``r + d / cos(pi/n)`` — the
polygon's own discretisation, not an error in the law, which is why the circle
check in ``tests/test_geometry_offset.py`` states both numbers. Moving each vertex
``d`` along the UNIT bisector would give ``r + d`` exactly and put every offset
EDGE closer than ``d`` to its source edge, which is not what a physical distance
from a wall means.

THE CLOSURE FLAG DECIDES THE TWO ENDS. A closed outline wraps, so its first and
last vertices are ordinary interior vertices and get a bisector. An open one has
no edge before its first vertex or after its last, so those two take the end
edge's own normal. The flag is the caller's — ``ProjectModel.is_closed``, already
resolved from ``closed_mode`` and the geometry — never re-derived here.

THE SIDE IS A SIGNED DISTANCE, AND FOR A CLOSED OUTLINE "OUTWARD" COMES FROM THE
WINDING. Positive is outward for a closed curve whatever order its points are
stored in: the shoelace area is measured and the normals are flipped when it is
clockwise, so a body imported one way round and a duct imported the other both
answer to the same sign. An open polyline has no inside, so positive is the RIGHT
of travel (``(ey, -ex)``), stated rather than inferred.

AN OFFSET THAT WOULD FOLD IS REFUSED, NOT TRIMMED, AND THE REFUSAL CARRIES A
NUMBER. Trimming returns a different curve from the one asked for, and — the part
that matters here — a trimmed curve has fewer points than its source, which breaks
the one property this object exists for. So :class:`OffsetRefused` is raised, and
it carries ``max_distance``: the largest distance on the SAME side that does work,
signed, so feeding it straight back into :func:`offset_points` succeeds. That
round trip is checked, because a number nobody re-fed is decoration.

Two things count as folding, and they are found differently:

* **A local fold**, where an offset edge reverses relative to its source edge —
  the concave radius overrun. Its limit is ANALYTIC: the offset edge vector is
  ``L*u + d*(mb - ma)``, so it reverses at ``d = L / -((mb - ma).u)`` for every
  edge whose projection term is negative, and the smallest such ``d`` is the
  bound. O(N), exact, and no search.
* **A global crossing**, where two non-adjacent offset edges cross while every
  edge kept its direction — offsetting a channel inward past half its gap. Found
  by an all-pairs proper-segment-intersection sweep, chunked so its memory is
  bounded, and only up to ``CROSSING_MAX_POINTS`` points. NAMED BLIND SPOT: above
  that count the sweep is skipped and only the local bound applies, because the
  sweep is O(N^2) and a refusal path that takes a minute is its own defect.
  Measured on a circle, 2026-09-29: 0.001 s at 240 points, 0.011 s at 1000,
  0.172 s at the cap — so the cap is where the cost starts to be felt, not where
  it becomes impossible.
"""
from __future__ import annotations

import numpy as np

from app.services import geometry_primitives

__all__ = ["OffsetRefused", "offset_points", "largest_offset",
           "CROSSING_MAX_POINTS"]

#: Above this many points the all-pairs crossing sweep is skipped (see the blind
#: spot in the module docstring). A CAD outline this repo resamples is two or
#: three orders of magnitude below it.
CROSSING_MAX_POINTS = 4000

#: Rows of the crossing sweep evaluated at once. Bounds memory to a constant
#: instead of N^2, which at the cap above would be 800 MB of intermediates.
_CROSSING_CHUNK = 256

#: Bisection steps used when a CROSSING (not a local fold) set the limit. 24
#: halvings leave the answer within 6e-8 of the bracket, and the value returned
#: is always the feasible end of it, never the midpoint.
BISECTION_STEPS = 24

#: The reported largest-working distance is shrunk by this fraction. At the
#: analytic limit itself an edge collapses to zero length, which the feasibility
#: test rejects — so the number the refusal names has to sit just inside it, or
#: feeding it back would refuse again.
FEASIBLE_MARGIN = 1e-6


class OffsetRefused(ValueError):
    """An offset that would fold the curve onto itself.

    ``max_distance`` is the largest SIGNED distance on the same side that works,
    so ``offset_points(pts, err.max_distance, closed)`` succeeds. It is 0.0 when
    no offset on that side is possible at all.
    """

    def __init__(self, message: str, max_distance: float):
        super().__init__(message)
        self.max_distance = float(max_distance)


# ── the law ───────────────────────────────────────────────────────────────── #

def _as_loop(points, closed: bool):
    """Return (working points, whether the source repeated its first point).

    A closed ``.dat`` may or may not repeat its first vertex at the end (a NACA
    section does, a drawn polygon does not). The duplicate is dropped for the
    normal computation and re-created from the offset of the first vertex, so the
    returned array is the same length as the source either way.
    """
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError("an offset needs an (N, 2) point array, got %r"
                         % (pts.shape,))
    if not closed or len(pts) < 3:
        return pts, False
    span = float(np.hypot(*(pts.max(axis=0) - pts.min(axis=0))))
    tol = max(1e-12, 1e-9 * span)
    if float(np.hypot(*(pts[0] - pts[-1]))) <= tol:
        return pts[:-1], True
    return pts, False


def _edge_normals(loop: np.ndarray, closed: bool) -> np.ndarray:
    """Unit normals of each edge, ``(ey, -ex)`` — the right of travel.

    A zero-length edge has no direction of its own, so it inherits the nearest
    preceding one (and, for a leading run of them, the nearest following one).
    Without that a duplicated point in an imported outline would put a NaN into
    every vertex that touches it and the whole offset would come back empty.
    """
    a = loop
    b = np.roll(loop, -1, axis=0) if closed else loop[1:]
    if not closed:
        a = loop[:-1]
    e = b - a
    ln = np.hypot(e[:, 0], e[:, 1])
    good = ln > 0.0
    if not good.any():
        raise ValueError("every edge of this geometry has zero length")
    idx = np.where(good, np.arange(len(ln)), -1)
    idx = np.maximum.accumulate(idx)
    if idx[0] < 0:                       # leading run of zero-length edges
        first = int(np.argmax(good))
        idx[idx < 0] = first
    e = e[idx]
    ln = ln[idx]
    return np.column_stack((e[:, 1] / ln, -e[:, 0] / ln))


def _miter(n_in: np.ndarray, n_out: np.ndarray) -> np.ndarray:
    """``(n_in + n_out) / (1 + n_in.n_out)`` — on both offset lines at once.

    The denominator vanishes only at a 180-degree reversal (a cusp), where no
    finite offset point lies on both lines; there the bisector is meaningless and
    the incoming normal is used, which the fold test then rejects for any
    distance that matters.
    """
    dot = (n_in * n_out).sum(axis=1)
    den = 1.0 + dot
    out = np.where((np.abs(den) > 1e-12)[:, None],
                   (n_in + n_out) / np.where(np.abs(den) > 1e-12, den, 1.0)[:, None],
                   n_in)
    return out


def _vertex_miters(points, closed: bool):
    """Per-vertex miter vectors for the working loop, oriented so +d is outward.

    Returns ``(loop, miters, duplicated_end)``.
    """
    loop, dup = _as_loop(points, closed)
    if len(loop) < 2:
        raise ValueError("an offset needs at least two distinct points")
    n = _edge_normals(loop, closed)
    if closed:
        m = _miter(np.roll(n, 1, axis=0), n)
        # The stored winding, not a guess: (ey, -ex) is outward for a
        # counter-clockwise loop and inward for a clockwise one. The shoelace is
        # `geometry_primitives`', not a fifth copy of it (#152 review).
        if geometry_primitives.signed_area(loop) < 0.0:
            m = -m
    else:
        m = np.empty_like(loop)
        m[0] = n[0]
        m[-1] = n[-1]
        if len(loop) > 2:
            m[1:-1] = _miter(n[:-1], n[1:])
    return loop, m, dup


def _local_limit(loop: np.ndarray, m: np.ndarray, closed: bool,
                 sign: float) -> float:
    """Largest |d| before an offset edge reverses relative to its source edge.

    ``inf`` when no edge's miters converge, which is the convex case: a convex
    outline offset outward never folds however far it goes.
    """
    a = np.arange(len(loop))
    b = (a + 1) % len(loop) if closed else a + 1
    if not closed:
        a, b = a[:-1], b[:-1]
    e = loop[b] - loop[a]
    ln = np.hypot(e[:, 0], e[:, 1])
    good = ln > 0.0
    if not good.any():
        return float("inf")
    u = e[good] / ln[good][:, None]
    c = ((m[b][good] - m[a][good]) * u).sum(axis=1) * sign
    shrink = c < 0.0
    if not shrink.any():
        return float("inf")
    return float(np.min(ln[good][shrink] / -c[shrink]))


def _reverses(loop: np.ndarray, q: np.ndarray, closed: bool) -> bool:
    """Does any offset edge point against its source edge (or collapse)?"""
    a = np.arange(len(loop))
    b = (a + 1) % len(loop) if closed else a + 1
    if not closed:
        a, b = a[:-1], b[:-1]
    src = loop[b] - loop[a]
    ln = np.hypot(src[:, 0], src[:, 1])
    good = ln > 0.0
    if not good.any():
        return False
    off = q[b][good] - q[a][good]
    return bool(((off * src[good]).sum(axis=1) <= 0.0).any())


def _crosses(q: np.ndarray, closed: bool) -> bool:
    """Do two non-adjacent offset edges PROPERLY cross?

    Strict sign tests, so two edges that merely share an endpoint (every adjacent
    pair does) are not a crossing and need no index mask. Skipped above
    ``CROSSING_MAX_POINTS`` — the named blind spot.
    """
    n = len(q)
    if n < 4 or n > CROSSING_MAX_POINTS:
        return False
    a = q
    b = np.roll(q, -1, axis=0) if closed else q[1:]
    if not closed:
        a = q[:-1]
    ns = len(a)
    for lo in range(0, ns, _CROSSING_CHUNK):
        hi = min(lo + _CROSSING_CHUNK, ns)
        a1 = a[lo:hi, None, :]
        b1 = b[lo:hi, None, :]
        a2 = a[None, :, :]
        b2 = b[None, :, :]
        r = b1 - a1
        s = b2 - a2
        d1 = s[..., 0] * (a1[..., 1] - a2[..., 1]) - s[..., 1] * (a1[..., 0] - a2[..., 0])
        d2 = s[..., 0] * (b1[..., 1] - a2[..., 1]) - s[..., 1] * (b1[..., 0] - a2[..., 0])
        d3 = r[..., 0] * (a2[..., 1] - a1[..., 1]) - r[..., 1] * (a2[..., 0] - a1[..., 0])
        d4 = r[..., 0] * (b2[..., 1] - a1[..., 1]) - r[..., 1] * (b2[..., 0] - a1[..., 0])
        if bool((((d1 * d2) < 0.0) & ((d3 * d4) < 0.0)).any()):
            return True
    return False


def _feasible(loop: np.ndarray, m: np.ndarray, closed: bool, d: float) -> bool:
    q = loop + d * m
    if not np.all(np.isfinite(q)):
        return False
    if _reverses(loop, q, closed):
        return False
    return not _crosses(q, closed)


def largest_offset(points, closed: bool, sign: float,
                   ceiling: float = float("inf")) -> float:
    """Largest SIGNED distance on ``sign``'s side that does not fold.

    ``ceiling`` bounds the search from above (the refused distance, when this is
    called to explain one). The value returned is always feasible: the bisection
    keeps the known-good end of the bracket and never reports its midpoint.

    When NOTHING bounds the offset — a convex outline offset outward never folds —
    the answer is ``ceiling`` itself, which is infinite if the caller gave no
    ceiling. That is the truthful answer, not a sentinel, and it is why the
    refusal path always passes the distance it refused.
    """
    sign = 1.0 if sign >= 0 else -1.0
    loop, m, _ = _vertex_miters(points, closed)
    cap = min(abs(ceiling), _local_limit(loop, m, closed, sign))
    if not np.isfinite(cap):
        return sign * abs(ceiling)
    cand = cap * (1.0 - FEASIBLE_MARGIN)
    if cand > 0.0 and _feasible(loop, m, closed, sign * cand):
        return sign * cand
    lo, hi = 0.0, cand
    for _ in range(BISECTION_STEPS):
        mid = 0.5 * (lo + hi)
        if mid <= 0.0:
            break
        if _feasible(loop, m, closed, sign * mid):
            lo = mid
        else:
            hi = mid
    return sign * lo


def offset_points(points, distance: float, closed: bool) -> np.ndarray:
    """The source's points moved ``distance`` along the local normal.

    ``distance`` is signed: positive is outward for a closed outline (from its
    stored winding) and the right of travel for an open one. The result has the
    SAME length and the same point order as ``points``.

    Raises :class:`OffsetRefused`, carrying the largest distance that would have
    worked, when the offset would fold the curve onto itself.
    """
    d = float(distance)
    loop, m, dup = _vertex_miters(points, closed)
    if d == 0.0:
        return np.asarray(points, dtype=float).copy()
    if not _feasible(loop, m, closed, d):
        best = largest_offset(points, closed, 1.0 if d >= 0 else -1.0, abs(d))
        if abs(best) <= 0.0:
            raise OffsetRefused(
                "this geometry cannot be offset on that side at all: the curve "
                "folds onto itself at any distance.", 0.0)
        raise OffsetRefused(
            "an offset of %.6g would fold the curve onto itself; the largest "
            "that works on that side is %.6g." % (d, best), best)
    q = loop + d * m
    if dup:
        q = np.vstack((q, q[0]))
    return q
