"""A GENERATED far field for a ring family: one ellipse, and the ray onto it (#197).

Qt-free, mesher-free, canvas-free, like every module in this package. What lives here
is the arithmetic the O-grid needs when the user has drawn NO far-field outline, kept
out of ``topology_ogrid.py`` because that file is near the 500-line standard and
because this is a different question: that one asks what a ring IS, this one asks
where its outer boundary goes when nobody drew it.

WHY A FAMILY MAY GENERATE THIS AND MAY NOT GENERATE A SEAM. `.claude/rules/gui-topology.md`
states the rule a `follows` or a `binding` edge is held to: it resolves to a stretch of
a stored POLYLINE, so a generated one would have to be a written FILE with no stable-id
scheme and no place in the project round trip — which is why the two-ring family REFUSES
rather than offsetting the body for you. An outer boundary is not that. Since #175 an
edge may declare the CURVE IT IS, with no file anywhere, and its nodes are placed on
that curve at exact arc length. So the line the rule draws is not "generated geometry is
forbidden" but "a generated thing cannot be a stored polyline", and an analytic outer
boundary falls on the legal side of it. THE C-GRID WAS ALREADY THERE: #149 made its far
field optional and generates six free corners when it is blank. This is that decision
applied to the family next door.

WHAT IT COSTS, AND IT IS SAID RATHER THAN DISCOVERED. A generated side belongs to no
geometry, so it carries the run's ``BC_GEOM`` instead of a per-segment condition — the
same trade the C-grid's generated hexagon makes, and the reason the drawn path stays.
A mesh wanting an inlet and an outlet on different parts of its outer boundary still
has to draw one.

WHERE THE CORNERS GO IS ARC LENGTH, NOT A RAY FAN, and that is this module's one
measured decision -- see :func:`ring_corners`.

WHY AN ELLIPSE AND NOT A RECTANGLE. A rectangle has four corners, and a ring's outer
corners are placed one per block: unless the blocking happens to put a corner at each
of the four, some block side would cut across one and the far field would be a polygon
with the corners rounded off. An ellipse has none, so any block count lands on it
exactly. It is also the better mesh — `docs/research/gridpro-blocking-method.md` §12b
measured a ring taken straight to a rectangle at 89.2 degrees of worst
non-orthogonality against a circle's 48.1 — and the rectangular far field a reader may
be expecting is not this shape at all: it wants an H between the ring and the box,
which is a different family and is not this one.
"""
from __future__ import annotations

import math

#: The smallest far field this will build, as a multiple of the body's own equivalent
#: radius. NOT 1.0: at a ratio of exactly 1 the generated ellipse has the body's area
#: and every radial edge has zero length somewhere, and a hair above it the ring is a
#: sliver the mesher fills with inverted cells rather than refusing. 1.5 is the floor
#: a refusal names; the DEFAULT is far larger and is the field-spec row's business.
MIN_RATIO = 1.5


def centroid(g) -> tuple[float, float]:
    """The AREA centroid of a closed outline, from its own sampled points.

    The area centroid and not the mean of the points, for the reason
    ``GeomBinding.equivalent_radius`` gives for using the enclosed area: a mean over
    the samples moves with the POINT COUNT, so re-sampling a geometry would move the
    generated far field and therefore the mesh. The area centroid is exact at any
    sampling of a straight-sided outline.

    Falls back to the mean of the points when the enclosed area is zero, which the
    caller has already refused for other reasons — returning something finite here
    keeps this function total rather than making every caller test for it.
    """
    pts = [p for s in g.spans.values() for p in s.points]
    if len(pts) < 3:
        return (0.0, 0.0) if not pts else (pts[0][0], pts[0][1])
    a2 = cx = cy = 0.0
    for k in range(len(pts)):
        x0, y0 = pts[k]
        x1, y1 = pts[(k + 1) % len(pts)]
        cross = x0 * y1 - x1 * y0
        a2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(a2) < 1e-300:
        return (sum(p[0] for p in pts) / len(pts),
                sum(p[1] for p in pts) / len(pts))
    return (cx / (3.0 * a2), cy / (3.0 * a2))


def axes(radius: float, ratio: float, aspect: float) -> tuple[float, float]:
    """The ellipse's two semi-axes, from the body's equivalent radius.

    ``ratio`` is how many body radii out the far field sits and ``aspect`` is its
    height over its width, so the pair is pinned by requiring the ellipse's OWN
    equivalent radius — ``sqrt(a*b)``, the radius of the circle with its area — to be
    ``ratio * radius``. Stating the size as an equivalent radius rather than as a
    semi-axis is what makes ``ratio`` mean the same thing at every aspect: the derived
    radial count reads that figure, so a user who stretches the far field and finds the
    count moving would be watching an accident.
    """
    far_r = max(0.0, radius) * max(0.0, ratio)
    asp = aspect if aspect > 0.0 else 1.0
    return far_r / math.sqrt(asp), far_r * math.sqrt(asp)


def _arc_table(a: float, b: float, n: int = 20000):
    """``(parameters, cumulative arc length)`` around the ellipse, for inverting it.

    An ellipse's arc length has no elementary inverse, so it is tabulated and
    bisected. ``n`` is fixed rather than adaptive because the table is only used to
    pick a PARAMETER: the point itself is then computed from that parameter exactly
    (see :func:`ring_corners`), so the sampling decides where a corner sits along
    the curve and never whether it is ON it. An earlier draft interpolated between
    two samples instead and put a corner 1.07e-8 off the ellipse, which the
    mesher's own 1e-9-relative bar refused — correctly.
    """
    th = [2.0 * math.pi * k / n for k in range(n + 1)]
    cum = [0.0]
    for k in range(n):
        x0, y0 = a * math.cos(th[k]), b * math.sin(th[k])
        x1, y1 = a * math.cos(th[k + 1]), b * math.sin(th[k + 1])
        cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
    return th, cum


def _theta_at(th, cum, f: float) -> float:
    """The ellipse parameter at arc-length fraction ``f`` of its perimeter."""
    s = (f % 1.0) * cum[-1]
    lo, hi = 0, len(cum) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if cum[mid] <= s:
            lo = mid
        else:
            hi = mid
    d = cum[hi] - cum[lo]
    u = 0.0 if d <= 0.0 else (s - cum[lo]) / d
    return th[lo] + u * (th[hi] - th[lo])


def ring_corners(centre, a: float, b: float, body_xy, ccw: bool) -> list:
    """Where the generated far field's corners go, one per body corner.

    **BY ARC LENGTH, PAIRED WITH THE BODY's OWN**, which is the rule the DRAWN path
    has always used: there a far-field outline is cut into equal-arc splits that
    pair one to one with the body's, and the generated path now says the same thing
    about a curve instead of about a polyline. The ring is anchored by the ray
    through body corner 0, so the fan still "starts" where the body does, and then
    advances by arc length in the ring's own direction.

    **THIS REPLACED A RAY FAN FROM THE CENTROID, AND THE MEASUREMENT IS WHY.** Ray
    casting is right on a round body — where the two rules agree — and wrong on a
    thin one, because most of an aerofoil's surface is nearly parallel to the rays
    through it: on a NACA 0012 at 24 blocks the first SEVEN outer corners landed in
    the first 10% of the ellipse while their body partners were evenly spaced 4.2%
    apart. Mean non-orthogonality **33.58 deg** against a drawn far field's 14.76 on
    the same circle at the same counts; by arc length it is **14.84**, which is that
    drawn number to the drawn circle's own faceting. The first version of this
    module shipped the ray rule and claimed "not drawing the far field costs
    nothing" on the evidence of a CIRCLE, where the claim cannot fail.

    **AND IT RETIRES A REFUSAL RATHER THAN NEEDING ONE.** A ray fan can cross itself
    on a body that is not star-shaped about its centroid, which cost a check and a
    sentence the user could not act on. Two monotone orderings around two nested
    closed curves cannot cross, so there is nothing left to refuse here.
    """
    th, cum = _arc_table(a, b)
    acc, total = [0.0], 0.0
    for k in range(len(body_xy)):
        x0, y0 = body_xy[k]
        x1, y1 = body_xy[(k + 1) % len(body_xy)]
        total += math.hypot(x1 - x0, y1 - y0)
        acc.append(total)
    if total <= 0.0:
        return []
    f0 = (math.atan2((body_xy[0][1] - centre[1]) / b,
                     (body_xy[0][0] - centre[0]) / a) % (2.0 * math.pi)) \
        / (2.0 * math.pi)
    sgn = 1.0 if ccw else -1.0
    out = []
    for k in range(len(body_xy)):
        t = _theta_at(th, cum, f0 + sgn * acc[k] / total)
        out.append((centre[0] + a * math.cos(t), centre[1] + b * math.sin(t)))
    return out


def outside_body(centre, a: float, b: float, g) -> str:
    """Why the generated ellipse does not contain the body, or "".

    THE RATIO IS NOT THE CHECK. ``ratio`` scales an EQUIVALENT RADIUS, an
    area-derived figure, and a long thin body has a small one: a 4.0 x 0.2 body has an
    equivalent radius of 0.505, so a far field at ratio 1.5 is an ellipse of radius
    0.76 and the body reaches x = +-2 straight through it. That is the same ruler
    mistake ``topology_preflight.enclosure_refusal`` exists for on the drawn path,
    measured there on the same body, and it is why this walks the body's own points.
    """
    worst = None
    for s in g.spans.values():
        for x, y in s.points:
            q = ((x - centre[0]) / a) ** 2 + ((y - centre[1]) / b) ** 2 if a > 0.0 and b > 0.0 else 2.0
            if worst is None or q > worst[0]:
                worst = (q, x, y)
    if worst is None or worst[0] <= 1.0:
        return ""
    return (f"the generated far field (an ellipse {2 * a:.4g} by {2 * b:.4g} about the "
            f"body's centroid) does not contain the body: its point "
            f"({worst[1]:.4g}, {worst[2]:.4g}) is outside it. Raise 'Generated Far "
            f"Field Size', or draw a far-field outline.")


def derive(plan, ratio: float, aspect: float, body) -> str:
    """Put the generated ellipse on ``plan``, or return why it cannot be.

    THE TWO NUMBERS ARRIVE AS ARGUMENTS AND NOT AS A MODEL, which is not style: the
    parameters-to-families gate derives WHICH family reads a field-spec row by
    walking the family modules' own attribute accesses with ``ast``, so a parameter
    read here through ``getattr`` on a model would be a control the gate reports as
    reading nothing. The family reads its own parameters; this does the arithmetic.

    THE FAMILY'S PLAN OBJECT IS WRITTEN THROUGH, not returned from — the same shape
    ``topology_ogrid.plan`` already uses for every other derivation, so the generated
    path is a branch of one function rather than a second planner whose answer could
    differ. What is here rather than there is only the arithmetic, and it is here
    because ``topology_ogrid.py`` is at the 500-line standard.
    """
    if not ratio >= MIN_RATIO:
        return (f"'Generated Far Field Size' is {ratio:g}, and a generated far "
                f"field must be at least {MIN_RATIO:g} body radii out — below that "
                f"the ring is a sliver the mesher fills with folded cells rather "
                f"than refusing. Raise it, or draw a far-field outline.")
    if not aspect > 0.0:
        return "'Generated Far Field Aspect' must be greater than zero."
    plan.far_centre = centroid(body)
    plan.far_a, plan.far_b = axes(plan.radius, ratio, aspect)
    plan.far_radius = plan.radius * ratio
    return ""


def fan_problem(plan, body, ring_points) -> str:
    """The ONE question only the GENERATED path has to ask: does the ellipse
    contain the body.

    It was two until the corner placement became arc length rather than a ray fan
    (see :func:`ring_corners`): a fan could cross itself on a body that is not
    star-shaped about its centroid, and two monotone orderings cannot. The
    signature keeps ``ring_points`` so the caller is unchanged and so a future
    question about the ring has somewhere to go.
    """
    del ring_points
    return outside_body(plan.far_centre, plan.far_a, plan.far_b, body)


def corners(plan, ids, body_xy) -> list:
    """The generated far field's corners, as FREE corners on the ellipse.

    ALL OF THEM AT ONCE, because where one goes is a property of the RING and not
    of its own body corner -- which is the whole content of the change
    :func:`ring_corners` records.
    """
    xy = ring_corners(plan.far_centre, plan.far_a, plan.far_b, body_xy, plan.ccw)
    return [{"id": i, "kind": "free", "xy": [p[0], p[1]]} for i, p in zip(ids, xy)]


def edge(plan, eid: str, a: str, b: str) -> dict:
    """One generated far-field side: an edge that IS the ellipse (#175).

    No file and no segment, so no per-segment condition either — this side carries
    the run's ``BC_GEOM``, which is the whole cost of not drawing a far field and
    is said in the field-spec row that offers it. The SPAN is not declared: the
    mesher derives it from the edge's own two corners, and ``sweep`` is the one
    thing those two cannot say.
    """
    return {"id": eid, "corners": [a, b], "kind": "wall",
            "curve": {"kind": "ellipse",
                      "centre": [plan.far_centre[0], plan.far_centre[1]],
                      "a": plan.far_a, "b": plan.far_b, "rot_deg": 0.0,
                      "sweep": "ccw" if plan.ccw else "cw"}}
