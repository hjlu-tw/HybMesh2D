"""How a physical length becomes a node count — the arithmetic BOTH families share.

Qt-free, like every module in this package. Extracted by #148's review, which found
:func:`nodes_for_growth` written twice: the O-grid's ``radial_count`` and the C-grid's
own copy were the same five lines with the growth ratio arriving from different
places, and the two caps (``MAX_RADIAL``, ``MAX_NODES``) were the same 5000 spelled
twice. A second copy of an arithmetic rule is wrong only once it drifts, which is this
package's own standing argument for one owner.

What is NOT here is the LAW each family derives its ratio from. Those are genuinely
different questions and they stay with the family that answers them: the O-grid's is
``1 + 2*pi/N_theta``, the ring's unit-aspect criterion, derived from how many cells go
round; the C-grid's is a fixed :data:`~app.services.topology_cgrid.GROWTH`, because a
wake and an outward direction have no ring to take a ratio from. This module takes the
ratio as an argument and has no default for it, so neither family can silently inherit
the other's.
"""
from __future__ import annotations

import math

#: The node count a derivation will not exceed however small a first cell is asked
#: for. A refusal would be worse — the number is a DEFAULT and overridable — but so
#: would silently seeding a count that allocates gigabytes. A family that hits it says
#: so in its read-out rather than presenting a clamped number as the derivation's
#: answer; the O-grid's review named that, and both families' plans carry the flag.
MAX_COUNT = 5000


def wall_count(edge_len: float, cell: float) -> int:
    """The node count for a wall edge of ``edge_len`` at a target ``cell``.

    Intervals + 1, because the mesher's ``count`` includes both end corners, and its
    floor is 2. Nearest rather than ceiling keeps the delivered cell size closest to
    the one asked for.

    ROUNDED HALF UP WITH A TOLERANCE, and both halves are load-bearing. The length is
    a SUM OVER A POLYLINE, so re-sampling the same geometry to a different point
    count moves its last bits — 2.4999999999999996 against 2.5000000000000004 for one
    of this repo's own fixtures. Python's ``round`` is half-to-EVEN, so those two land
    on 2 and 3, and the count of a wall edge changed because the user re-sampled a
    geometry they had not otherwise touched. The tolerance snaps a tie back together
    and the half-up floor then resolves it the same way every time. Measured, not
    guessed: it is what ``test_topology_ogrid.py`` check 10 fails on without it.
    """
    if cell <= 0.0 or edge_len <= 0.0:
        return 2
    return max(2, int(math.floor(edge_len / cell + 0.5 + 1e-9)) + 1)


def nodes_for_growth(span: float, first_cell: float, ratio: float) -> int:
    """Nodes to cross ``span`` starting at ``first_cell`` and growing at ``ratio``.

    A geometric series of ``n`` intervals covers ``ds * (q**n - 1) / (q - 1)``; the
    count is the ``n`` at which that reaches ``span``, plus one for the node the
    intervals end on.

    ``ratio`` has NO DEFAULT on purpose. The two families derive it from different
    arguments (see the module docstring), and a default here would let one of them
    quietly take the other's.
    """
    q = float(ratio)
    if span <= 0.0 or first_cell <= 0.0 or q <= 1.0:
        return 2
    n = math.log1p(span * (q - 1.0) / first_cell) / math.log(q)
    return max(2, min(MAX_COUNT, int(math.ceil(n)) + 1))


def circularity(equivalent_radius: float, perimeter: float) -> float:
    """``4*pi*A/P^2`` of a closed outline: 1 for a circle, less for anything else.

    Taken from the EQUIVALENT RADIUS rather than from an area computed here, because
    `GeomBinding.equivalent_radius` already owns that integral and states why it is
    area-derived: a figure taken from the sampled points moves with the POINT COUNT,
    so re-sampling a geometry would move it. ``A = pi * R^2`` by that definition, so
    this is ``4 * pi^2 * R^2 / P^2`` and inherits the same stability.

    THE PERIMETER DOES NOT INHERIT IT, and that is the limit of this number: a
    polyline inscribed in a curve is shorter than the curve, so a coarsely sampled
    circle reads slightly OVER 1. Measured on the shipped 160-point circle: 0.9999.
    It is used for a sentence, not for a decision, which is the accuracy that buys.
    """
    if not (perimeter > 0.0):
        return 0.0
    return 4.0 * math.pi * (math.pi * equivalent_radius * equivalent_radius) \
        / (perimeter * perimeter)


def ring_advice(circ: float, below: float) -> list:
    """The read-out's one line about a body a RING is the wrong construction for.

    A SENTENCE AND NOT A REFUSAL. A ring around a thin body is legal, meshes, and is
    what somebody may actually want; it is simply not the best construction this tool
    has for that shape, and the family that is lives next door. Measured on a NACA
    0012 at 24 blocks: mean non-orthogonality 14.84 deg from a ring against 5.07 from
    the rosette-and-H arrangement the C-grid family builds toward, with the same worst
    cell (81.8 deg, the sharp trailing edge) in both.

    Returned as a LIST so the caller concatenates rather than branching, and empty
    for a body the advice is not about -- which is most of them.
    """
    if not (0.0 < circ < below):
        return []
    return [f"shape: this body's circularity is {circ:.3f} (a circle is 1.000), so a "
            f"RING is a poor fit — its radial lines leave a long flat surface at a "
            f"shallow angle. Measured on a NACA 0012: mean non-orthogonality 14.8 deg "
            f"from a ring against 5.1 from a C-grid's arrangement. The C-grid family "
            f"is the one for a sharp-tailed section."]
