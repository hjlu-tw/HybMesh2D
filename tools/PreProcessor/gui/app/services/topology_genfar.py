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


def ray_point(centre, a: float, b: float, through) -> tuple[float, float] | None:
    """Where the ray from ``centre`` through ``through`` meets the ellipse.

    EXACTLY on the ellipse, which is the requirement and not a nicety: the mesher
    inverse-maps a curve edge's two corners onto the curve and REFUSES one that is off
    it by more than 1e-9 of the larger semi-axis (`MB_CURVE_ON_TOL`). Solving the ray
    rather than sampling a parameter is what makes that exact — the scale factor below
    is the positive root of ``(s*dx/a)^2 + (s*dy/b)^2 = 1``.

    ``None`` when the point IS the centre, which carries no direction. The caller
    refuses that as a body whose outline passes through its own centroid.
    """
    dx, dy = through[0] - centre[0], through[1] - centre[1]
    q = (dx / a) ** 2 + (dy / b) ** 2 if a > 0.0 and b > 0.0 else 0.0
    if q <= 0.0:
        return None
    s = 1.0 / math.sqrt(q)
    return (centre[0] + s * dx, centre[1] + s * dy)


def star_problem(centre, ring, ccw: bool) -> str:
    """Why a ray fan from ``centre`` through ``ring`` would cross itself, or "".

    THE ONE THING A GENERATED FAR FIELD CANNOT DO FOR THE USER. Every outer corner is
    placed along the ray from the body's centroid through its own body corner, so the
    radial edges cannot cross exactly when those rays leave the centre in the order the
    ring runs — which is to say when the body is STAR-SHAPED about its own centroid at
    the corners it was cut at. A body with a deep enough notch is not, and the mesher's
    answer to the mesh that results is a fold, reported as an inverted cell count with
    no sentence about why.

    MEASURED AT THE CORNERS AND NOT OVER THE WHOLE OUTLINE, deliberately: what the fan
    is made of is the corners, so an outline that dips back between two of them still
    produces a legal fan. Over-refusing here would turn a working aerofoil into an
    error, since a cambered section's lower surface is not star-shaped about the area
    centroid everywhere while its block corners are.

    The sentence names the two corners that are out of order and their ring positions,
    because "your body is not star-shaped" is a property the user cannot see and "the
    outer corner for block 7 would land behind block 6's" is a place they can look.
    """
    if len(ring) < 3:
        return ""
    angs = []
    for x, y in ring:
        dx, dy = x - centre[0], y - centre[1]
        if dx == 0.0 and dy == 0.0:
            return ("the body's outline passes through its own centroid, so the ray "
                    "that would place one of the generated far-field corners has no "
                    "direction. Draw the far field yourself, or cut the body "
                    "elsewhere.")
        angs.append(math.atan2(dy, dx))
    # Unwrap in the ring's OWN direction, so one full turn is the whole loop. A corner
    # that does not advance has fallen behind the one before it.
    step = 1.0 if ccw else -1.0
    total = 0.0
    for k in range(len(angs)):
        d = angs[(k + 1) % len(angs)] - angs[k]
        while d * step <= -math.pi:
            d += step * 2.0 * math.pi
        while d * step > math.pi:
            d -= step * 2.0 * math.pi
        if d * step <= 0.0:
            return (f"the generated far field places each outer corner along the ray "
                    f"from the body's centroid through its own corner, and ring "
                    f"position {k} does not advance past position "
                    f"{(k + 1) % len(angs)} — so those two radial edges would cross. "
                    f"The body is not star-shaped about its centroid at the corners "
                    f"it is cut at. Cut it into more segments, or draw the far field "
                    f"yourself.")
        total += d
    return ""


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
    """The two questions only the GENERATED path has to ask, in one call.

    Containment first and the fan second, because a body poking through its far
    field is the one the user is more likely to have made and the one whose fix
    (raise the size) is a number they can see.
    """
    why = outside_body(plan.far_centre, plan.far_a, plan.far_b, body)
    return why or star_problem(plan.far_centre, ring_points, plan.ccw)


def corner(plan, cid: str, through) -> dict:
    """One generated far-field corner, as a FREE corner on the ellipse."""
    xy = ray_point(plan.far_centre, plan.far_a, plan.far_b, through)
    return {"id": cid, "kind": "free", "xy": [xy[0], xy[1]]}


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
