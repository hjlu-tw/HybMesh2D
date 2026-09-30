"""The mesher's own ONE-SIDED TANH spacing law, in Python (issue #155).

Qt-free, like every module in this package, and pure arithmetic: no mesher, no
filesystem, no model.

A SECOND HOME FOR ONE RULE, AND IT SAYS SO — the shape
``topology_skeleton.resolve_counts`` already takes for ``resolveEdgeCounts``. The law
itself lives in ``tools/PreProcessor/include/Spacing.hpp`` (``tanhStartPos``,
``solveClusterDelta``, ``generateTanhStart``) and is what the mesher runs; what is
here is the same three expressions, because the two-ring family has to know the size
of the LAST cell the inner ring produces in order to declare it as the FIRST cell of
the outer one. The alternative is a mesher key meaning "start where the edge before
you ended", which is a C++ change #155 rules out, or leaving the number for the user
to type, which is the stale-number defect #155 exists to remove.

WHAT KEEPS THE TWO TOGETHER IS A MEASUREMENT ON A MESH, NOT A DIFF OF TWO FORMULAE.
``tests/test_topology_tworing.py`` runs the REAL mesher on the family's own output
and requires the first cell out of the seam to equal the last cell into it, with the
key removed as the negative control — so what is gated is the behaviour this module
exists to produce rather than the text of the law. It is also pinned against the two
shipped hand-written documents, whose ``ds_start`` values were read off real runs
(``examples/topology/tworing_ogrid.json``: 0.05813418;
``examples/topology/tworing_offset.json``: 0.02474095).

ONLY THE ONE-SIDED LAW IS MIRRORED. The symmetric ``generateTanh`` and the geometric
and uniform laws are not here, because no family needs to predict an interval of one:
a template that declared them would be declaring a spacing it did not derive
anything from.
"""
from __future__ import annotations

import math

#: The bracket growth cap and the iteration count of ``Spacing.hpp``'s
#: ``solveClusterDelta``, mirrored rather than re-chosen — a bisection that stopped
#: somewhere else would answer a slightly different delta than the run does, and the
#: seam continuity this module exists for is exactly the digits that would move.
_DELTA_CAP = 60.0
_ITERATIONS = 200


def tanh_start_pos(span: float, count: int, delta: float, i: int) -> float:
    """Where node ``i`` of ``count`` lands on an edge of ``span`` clustered at its start.

    ``Spacing.hpp::tanhStartPos``: ``L * (1 + tanh(d*(xi-1)) / tanh(d))``, which is 0
    at ``xi = 0``, ``L`` at ``xi = 1`` and monotonically increasing between, so the
    map cannot fold.
    """
    if count < 2:
        return 0.0
    if abs(delta) < 1e-9:
        return span * i / (count - 1)
    xi = float(i) / (count - 1)
    return span * (1.0 + math.tanh(delta * (xi - 1.0)) / math.tanh(delta))


def solve_tanh_start_delta(span: float, count: int, first_cell: float) -> float:
    """The clustering that makes the FIRST interval equal ``first_cell``.

    ``Spacing.hpp::solveClusterDelta`` over ``tanhStartPos``: the first interval is
    monotonically decreasing in delta, which is what makes plain bisection safe.

    RETURNS 0 WHEN THE REQUEST IS AT OR COARSER THAN UNIFORM, exactly as the C++
    does, so a caller falls back to the uniform distribution rather than to a delta
    that misrepresents what happened. That case is reachable from the panel — a wall
    height larger than the ring divided by its radial count — and it is not an error:
    the mesher meshes it, uniformly, and the interval this module then predicts is
    the uniform one, which is still the truth about the last cell.
    """
    if count < 3 or span <= 0.0 or first_cell <= 0.0:
        return 0.0
    if first_cell >= span / (count - 1):
        return 0.0
    lo, hi = 1e-6, 1.0
    while tanh_start_pos(span, count, hi, 1) > first_cell and hi < _DELTA_CAP:
        hi *= 2.0
    if tanh_start_pos(span, count, hi, 1) > first_cell:
        return hi          # unreachable request: the finest this law can do
    for _ in range(_ITERATIONS):
        mid = 0.5 * (lo + hi)
        if tanh_start_pos(span, count, mid, 1) > first_cell:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def last_interval(span: float, count: int, first_cell: float) -> float:
    """The size of the LAST cell of an edge clustered at its start.

    THE ONE NUMBER #155 IS WRITTEN AROUND. An edge of ``span`` with ``count`` nodes
    whose start end is a wall at ``first_cell`` finishes on an interval this size,
    and the ring continuing outward from that end must start there or the seam shows
    as a jump in cell size. Derived from the same delta the run solves for rather
    than approximated, because a spacing that is nearly right is a seam that is
    nearly invisible.

    0.0 for a degenerate edge, which the caller reports rather than declares: a
    ``ds_start`` of zero is a document the mesher refuses.
    """
    if count < 2 or span <= 0.0:
        return 0.0
    delta = solve_tanh_start_delta(span, count, first_cell)
    return span - tanh_start_pos(span, count, delta, count - 2)
