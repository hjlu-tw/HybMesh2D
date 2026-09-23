"""The O-grid family: a ring of blocks around a body the user DREW (issue #137).

A PURE FUNCTION of ``(model, context)``, like the H-grid beside it — no Qt, no mesher,
no canvas, and no filesystem: everything it needs to know about the user's CAD arrives
as a :class:`~app.services.topology_binding.BindingContext`, which is also what the
panel's read-out and the canvas overlay resolve against. What it adds to the H-grid is
the half that ticket deliberately left out: BINDING.

THE WALLS FOLLOW THE GEOMETRY, THEY DO NOT CUT CHORDS ACROSS IT. Every arc edge below
declares ``binding``, so the mesher walks that source segment's own polyline between the
edge's two corners. On a quarter circle the chord sits 0.293 r off the body at its
midpoint, so this is not a refinement — without it a "circle" is a square.

WHICH EDGES BIND IS THE TEMPLATE'S DECISION, NOT THE USER'S (#133). The user names two
geometries; the family knows that the inner ring is the body wall, that the outer one is
the far field, and which source segment each side lies on. No normalized arc-length
position is ever shown.

ONE WALL EDGE PER SOURCE SEGMENT, OR AN EQUAL SPLIT OF ONE. A bound edge declares ONE
``seg``, so an edge spanning two segments could not say which condition it carries —
which is the whole reason the boundary conditions come off the geometry at all. The
block ring therefore REFINES the segment partition and never cuts across it, and
``ogrid_splits`` is how many equal-arc blocks each source segment becomes.

THE FAR FIELD IS DRAWN, NOT GENERATED. #133 decided the template writes no geometry, and
a far field synthesised from a radius would be a straight-sided polygon with as many
sides as there are blocks — a square far field on the four-block case. So the far-field
outline is a geometry from the CAD stage, its segments pair ONE TO ONE with the body's,
and a mismatch is refused by name rather than resolved by guessing which segment goes
with which.

THE BLOCK WINDING IS MEASURED, NOT ASSUMED. The mesher requires each block's corner ring
to close counter-clockwise. Walking body -> outward -> along the far field -> back is CCW
for a body drawn anticlockwise and CW for one drawn clockwise, so a clockwise body needs
the mirrored assignment: the radials become the block's east/west instead of its
south/north. Both tuples pair the SAME edges as opposite sides ((0, 2) and (1, 3) are the
arc pair and the radial pair either way), so the count classes — and therefore the
seeding — are identical, which is what makes the mirror two lines rather than a second
builder.

THE FIRST CELL HEIGHT IS THE RUN'S ``BL_INITIAL_THICKNESS``, under the name it already
has (#133, #137). No ``ds_start`` is declared: each radial edge marks its body end a wall
end and the mesher's tanh law solves for the clustering that delivers that height. The
derivation below READS the value, so the read-out can say what the choice costs, but the
value itself still has exactly one home.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.topology_binding import BindingError
from app.services.topology_ogrid_binding import (
    BINDING_LISTS, cover_problem, order_problem, parse_binding,
)

#: The template's own name for the family, as stored in the project file.
FAMILY = "ogrid"

#: The smallest ring the mesher will accept, MEASURED rather than reasoned. Its
#: block-orientation test takes the signed area of the corner CHORD ring, and with
#: only two corners on each outline all four corners of every block are collinear —
#: so the second block comes back as "its corners wind clockwise (signed area
#: -0.000000)" and the run is refused with the topology exit code. Two was this
#: family's first floor; the gate's winding check caught it.
MIN_BLOCKS = 3

#: The node count the radial derivation will not exceed however small a first cell is
#: asked for. A refusal would be worse — the number is a DEFAULT and overridable — but
#: so would silently seeding a count that allocates gigabytes.
MAX_RADIAL = 5000


@dataclass
class Plan:
    """What the parameters derive, and why — the ONE owner, shared with the panel.

    Every number the read-out displays is computed here, so the panel cannot show a
    figure the generated document does not use. ``problem`` is non-empty exactly when
    :func:`build` would refuse, and carries the same sentence, so the user reads the
    refusal while typing rather than after pressing Generate.
    """

    problem: str = ""
    #: The edge id a binding refusal is about, so the panel that repairs it (#138)
    #: flags that edge rather than re-parsing the sentence.
    broken_edge: str = ""
    blocks: int = 0
    #: Node count of each wall edge, in ring order.
    wall_counts: tuple[int, ...] = ()
    #: Total circumferential CELLS around the body — the N_theta of the radial law.
    n_theta: int = 0
    #: The geometric ratio that gives unit aspect ratio: 1 + 2*pi/N_theta.
    ratio: float = 0.0
    #: The wall first cell that ratio implies, and the one the run actually asks for.
    first_cell_11: float = 0.0
    first_cell: float = 0.0
    radius: float = 0.0
    far_radius: float = 0.0
    radial_derived: int = 0
    radial: int = 0
    overridden: bool = False
    #: True when the derivation hit ``MAX_RADIAL``. A silent clamp on a DISPLAYED
    #: derived count is a number the panel presents as the derivation's answer and
    #: is not; review named it, and the read-out now says so.
    clamped: bool = False
    body_segs: tuple[int, ...] = ()
    far_segs: tuple[int, ...] = ()
    ccw: bool = True

    @property
    def aspect(self) -> float:
        """How many times longer than tall the cells at the wall are.

        The number the ticket is written around: a 1e-3 first cell where the 1:1
        criterion implies 0.0327 means about 33, and saying "33x" is what tells the
        user their choice has a cost that no single count will remove.
        """
        if self.first_cell <= 0.0:
            return 0.0
        return self.first_cell_11 / self.first_cell

    def lines(self) -> list:
        """The derivation, as the read-out shows it — RESULT AND WORKING, not result.

        #137's central claim is that displaying the derivation is the single most
        useful thing the panel does, so each line carries the quantity it was computed
        from rather than only its answer.
        """
        if self.problem:
            return [f"—  {self.problem}"]
        return [
            f"ring: {self.blocks} blocks, {self.n_theta} circumferential cells "
            f"(counts {', '.join(str(c) for c in self.wall_counts[:8])}"
            f"{'…' if len(self.wall_counts) > 8 else ''})",
            f"1:1 law: q = 1 + 2π/{self.n_theta} = {self.ratio:.5f}  →  first "
            f"cell {self.first_cell_11:.3e} at r = {self.radius:.4g}",
            f"yours: BL_INITIAL_THICKNESS {self.first_cell:.3e}  →  wall cells "
            f"{self.aspect:.3g}x longer than tall",
            f"radial: {self.radial} nodes"
            + (" (overridden)" if self.overridden
               else f" (derived: q from {self.first_cell:.3e} spans "
                    f"{self.far_radius - self.radius:.4g})")
            + (f" — CLAMPED at {MAX_RADIAL}, so the first cell you asked for is "
               f"not reachable at this ratio" if self.clamped else ""),
        ]


def radial_law(n_theta: int) -> float:
    """The geometric ratio giving unit aspect ratio on a circular O-grid.

    ``1 + 2*pi/N_theta``, which is #133's stated derivation and is what it is because
    a circumferential cell at radius r is ``2*pi*r/N_theta`` long, so a radial step
    equal to it is ``dr = r * 2*pi/N_theta`` — a geometric law in r with exactly that
    ratio. AN IDEALISATION, and labelled as one: it is stated for a CIRCULAR O-grid,
    so on a body that is not a circle the radius it uses is a mean.
    """
    return 1.0 + 2.0 * math.pi / max(1, int(n_theta))


def radial_count(n_theta: int, span: float, first_cell: float) -> int:
    """How many radial NODES close the gap between the first cell and the far field.

    A geometric law starting at ``first_cell`` and growing at the 1:1 ratio covers
    ``first_cell * (q**n - 1) / (q - 1)``; the count is the ``n`` at which that
    reaches ``span``, plus one for the node the intervals end on. This is the second
    half of #137's "how many radial points would close the gap": the first half says
    the wall cells are N times flatter than 1:1, and this says what it costs to grow
    from there without ever exceeding the 1:1 ratio.
    """
    q = radial_law(n_theta)
    if span <= 0.0 or first_cell <= 0.0 or q <= 1.0:
        return 2
    n = math.log1p(span * (q - 1.0) / first_cell) / math.log(q)
    return max(2, min(MAX_RADIAL, int(math.ceil(n)) + 1))


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


def _ring(segs, splits: int) -> list:
    """``[(seg id, t), ...]`` around the whole loop, in declaration order."""
    return [(s, j / float(splits)) for s in segs for j in range(splits)]


def plan(model, ctx) -> Plan:
    """Everything the O-grid derives from ``model`` against ``ctx``.

    Returns a :class:`Plan` whose ``problem`` is set rather than raising, because the
    panel asks this on every keystroke and a half-typed geometry name is not an error
    yet. :func:`build` asks the same question and turns a problem into the refusal.
    """
    p = Plan()
    if ctx is None:
        p.problem = ("this family binds to the geometry you drew, so it needs the "
                     "mesh's geometry list; none was supplied.")
        return p

    body = ctx.geometry(model.ogrid_body_geom)
    far = ctx.geometry(model.ogrid_far_geom)
    for role, name, g in (("body", model.ogrid_body_geom, body),
                          ("far field", model.ogrid_far_geom, far)):
        if not str(name or "").strip():
            p.problem = (f"name the {role} geometry — this family binds to a shape "
                         f"from the CAD stage and writes none of its own.")
            return p
        if g is None:
            p.problem = (f"the {role} geometry '{name}' is not one of this mesh's "
                         f"geometries. It loads: "
                         f"{', '.join(ctx.names()) or '(nothing)'}.")
            return p
        if not g.spans:
            p.problem = (f"the {role} geometry '{g.spelling}' carries no per-segment "
                         f"data, so there is nothing to bind to. That comes from the "
                         f"'.meta' sidecar the PreProcessor writes beside the .dat; "
                         f"re-export it from the CAD stage.")
            return p
        if not g.closed:
            p.problem = (f"the {role} geometry '{g.spelling}' is not a closed loop, "
                         f"and an O-grid is a ring around a closed body.")
            return p

    # `BINDING_LISTS` names each list's ROLE, and it is the only spelling: this
    # function used to say "far-field" where that table says "far field", so one
    # refusal hyphenated the far field and the next did not. Review found it under
    # the comment claiming the pairing was "named once so a future third reader
    # cannot spell it differently" — the third reader was this one.
    _BODY_ROLE, _FAR_ROLE = (row[0] for row in BINDING_LISTS)
    p.body_segs, why = parse_binding(model.ogrid_body_segs, body.seg_ids, _BODY_ROLE)
    if not why:
        p.far_segs, why = parse_binding(model.ogrid_far_segs, far.seg_ids, _FAR_ROLE)
    if why:
        p.problem = why
        return p
    splits = max(1, int(model.ogrid_splits))

    # EVERY BINDING RESOLVED, AND NAMED BY ITS EDGE — BEFORE any question about
    # counts. Through `ctx.resolve` rather than through a second `s in g.spans` test
    # here, so the refusal has ONE author: the sentence the panel shows while the
    # user types, the message `build` raises and the `edge` the repair panel (#138)
    # flags are all that one call's. The edge id is spelled the same way `build`
    # spells it below — the wall of ring position k is `w{k}`, and the stored
    # position i is ring position i*splits — which is what makes "the broken edge is
    # named" name something the user can find.
    #
    # BEFORE the one-to-one pairing check, which #138 moved it in front of: after
    # repairing one list a CAD split had lengthened, the two lists differ in length
    # BECAUSE of the binding still broken in the other, and answering "these counts
    # do not match" there names no edge and sends the user to look at the wrong
    # geometry. Each list is walked against its own ring, so neither depends on the
    # other's length.
    # ONE list of the two lists, built from `BINDING_LISTS` so the role word and the
    # edge prefix travel together rather than being retyped per loop.
    lists = tuple((row[0], g, segs, row[3]) for row, g, segs in
                  zip(BINDING_LISTS, (body, far), (p.body_segs, p.far_segs)))
    for _who, g, segs, prefix in lists:
        try:
            for i, sid in enumerate(segs):
                ctx.resolve(f"{prefix}{i * splits}", g.spelling, sid)
        except BindingError as exc:
            p.problem = str(exc)
            p.broken_edge = exc.edge
            return p

    # ...in the ORDER the geometry runs them, which resolving each id one at a time
    # cannot see (every id in a swapped list still resolves), and COVERING it, which
    # the order check cannot see either (every id in a subset walks the right way).
    # Both ANSWER with the edge, rather than this loop recovering it from the
    # sentence they wrote — the shape `BindingError` above already uses.
    for who, g, segs, prefix in lists:
        edge, why = order_problem(who, g, segs, splits, prefix)
        if not why:
            edge, why = cover_problem(who, g, segs, splits, prefix)
        if why:
            p.problem = why
            p.broken_edge = edge
            return p

    if len(p.body_segs) != len(p.far_segs):
        p.problem = (f"the body binds {len(p.body_segs)} source segment(s) and the "
                     f"far field {len(p.far_segs)}. An O-grid pairs them one to one, "
                     f"so segment the far field the same way you segmented the body.")
        return p

    p.blocks = len(p.body_segs) * splits
    if p.blocks < MIN_BLOCKS:
        p.problem = (f"{len(p.body_segs)} source segment(s) x {splits} split(s) is "
                     f"{p.blocks} block(s) — a ring needs at least {MIN_BLOCKS}. "
                     f"Raise 'Splits Per Segment', or cut the body into more "
                     f"segments in the CAD stage.")
        return p

    body_ring = _ring(p.body_segs, splits)
    far_ring = _ring(p.far_segs, splits)

    cell = float(model.ogrid_cell)
    if cell <= 0.0:
        p.problem = "the target cell edge length must be greater than zero."
        return p
    counts = []
    for s in p.body_segs:
        edge_len = body.spans[s].length / splits
        counts += [wall_count(edge_len, cell)] * splits
    p.wall_counts = tuple(counts)
    p.n_theta = sum(c - 1 for c in counts)

    p.radius = body.equivalent_radius()
    p.far_radius = far.equivalent_radius()
    # BEFORE the derivation, not after it: a far field inside the body gives a
    # negative span, and `radial_count` would then answer on it rather than refuse.
    if p.far_radius <= p.radius:
        p.problem = (f"the far-field geometry's equivalent radius "
                     f"({p.far_radius:.4g}) is not outside the body's "
                     f"({p.radius:.4g}), so there is no ring between them.")
        return p
    p.ratio = radial_law(p.n_theta)
    p.first_cell_11 = p.radius * (p.ratio - 1.0)
    p.first_cell = ctx.first_cell if ctx.first_cell > 0.0 else p.first_cell_11
    p.radial_derived = radial_count(p.n_theta, p.far_radius - p.radius, p.first_cell)
    p.clamped = p.radial_derived >= MAX_RADIAL
    want = int(model.ogrid_radial_count)
    p.overridden = want >= 2
    p.radial = want if p.overridden else p.radial_derived

    # The RING's own winding, not the outline's: a binding list given in reverse
    # order walks the outline backwards, and only the ring can see that. Reachable
    # for every legal ring because MIN_BLOCKS is three.
    a_body = body.signed_area([s for s, _ in body_ring], [t for _, t in body_ring])
    a_far = far.signed_area([s for s, _ in far_ring], [t for _, t in far_ring])
    if a_body == 0.0 or a_far == 0.0:
        p.problem = ("the corner ring has no area — check that the two geometries "
                     "are the closed outlines they look like.")
        return p
    if (a_body > 0.0) != (a_far > 0.0):
        p.problem = ("the body and the far field are wound in opposite directions, "
                     "so every radial edge would cross the ring. Redraw one of them "
                     "in the other direction.")
        return p
    p.ccw = a_body > 0.0
    return p


def build(model, ctx=None) -> dict:
    """The O-grid topology document for ``model``, bound to ``ctx``'s geometries."""
    p = plan(model, ctx)
    if p.problem:
        raise BindingError(
            f"the O-grid template cannot build a document: {p.problem}",
            edge=p.broken_edge)

    body = ctx.geometry(model.ogrid_body_geom)
    far = ctx.geometry(model.ogrid_far_geom)
    splits = max(1, int(model.ogrid_splits))
    body_ring = _ring(p.body_segs, splits)
    far_ring = _ring(p.far_segs, splits)
    n = len(body_ring)

    corners, edges, blocks = [], [], []
    for k in range(n):
        bs, bt = body_ring[k]
        fs, ft = far_ring[k]
        corners.append({"id": f"b{k}", "kind": "on_geometry",
                        "geom": body.spelling, "seg": bs, "t": bt})
        corners.append({"id": f"f{k}", "kind": "on_geometry",
                        "geom": far.spelling, "seg": fs, "t": ft})

    for k in range(n):
        # The radials are ONE equivalence class that wraps around and closes, so only
        # the first declares a count; the other n-1 arrive by propagation. Every one
        # marks its body end a wall end, because spacing does not propagate — only
        # counts do.
        e = {"id": f"r{k}", "corners": [f"b{k}", f"f{k}"], "kind": "interface",
             "spacing": {"wall_ends": "start"}}
        if k == 0:
            e["count"] = p.radial
        edges.append(e)
    for k in range(n):
        bs, _ = body_ring[k]
        fs, _ = far_ring[k]
        nxt = (k + 1) % n
        # One seed per (wall, far arc) class, declared on the WALL — the side whose
        # length the user asked for in physical units.
        # `ctx.resolve` again rather than `bs` directly: the value a binding carries
        # is whatever the resolver says it is, so nothing here can start writing a
        # position by looking convenient. `plan` has already run the same call, so
        # this cannot raise on a plan that passed — it is the same rule asked at the
        # point of use, not a second one.
        edges.append({"id": f"w{k}", "corners": [f"b{k}", f"b{nxt}"], "kind": "wall",
                      "count": p.wall_counts[k],
                      "binding": {"geom": body.spelling,
                                  "seg": ctx.resolve(f"w{k}", body.spelling, bs)}})
        edges.append({"id": f"o{k}", "corners": [f"f{k}", f"f{nxt}"], "kind": "wall",
                      "binding": {"geom": far.spelling,
                                  "seg": ctx.resolve(f"o{k}", far.spelling, fs)}})
    for k in range(n):
        nxt = (k + 1) % n
        # [south, east, north, west]. CCW body: i runs OUTWARD and j anticlockwise.
        # CW body: the mirror, i anticlockwise and j outward. Either way the opposite
        # pairs are (arc, arc) and (radial, radial), so the count classes are the same.
        blocks.append({"id": f"q{k}",
                       "edges": ([f"r{k}", f"o{k}", f"r{nxt}", f"w{k}"] if p.ccw
                                 else [f"w{k}", f"r{nxt}", f"o{k}", f"r{k}"])})

    return {"format_version": 1, "corners": corners, "edges": edges, "blocks": blocks}
