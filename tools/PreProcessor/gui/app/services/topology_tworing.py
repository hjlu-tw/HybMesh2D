"""The TWO-RING O-grid family: the O-grid's ring split at a seam the user drew (#155).

A PURE FUNCTION of ``(model, context)``, like the three families beside it — no Qt, no
mesher, no canvas, no filesystem. It emits nothing the mesher did not already accept:
#153 and #154 shipped this shape twice as a hand-written document and neither needed a
new key, a new spacing law or a C++ change.

IT REUSES THE O-GRID'S DECISIONS RATHER THAN RE-MAKING THEM. The walls bind one edge
per source segment (or an equal split of one), the far field is DRAWN and pairs one to
one with the body, the block winding is MEASURED from the corner ring rather than
assumed, the wall's first cell is the run's ``BL_INITIAL_THICKNESS`` under the name it
already has, and the radial law is ``radial_law``'s — imported, not restated.

WHAT IT ADDS IS A THIRD GEOMETRY AND ONE DERIVED NUMBER.

  * THE SEAM. A geometry paired segment-for-segment with the body, whose edges are
    ``interface`` + ``follows`` (#151) and carry NO boundary condition: an interior
    line is not a boundary, so whatever its segments are labelled reaches nothing and
    no face of it appears in the ``.bnd``.
  * TWO RADIAL EQUIVALENCE CLASSES instead of one, so the law that holds the wall's
    first cell answers to the wall and the one that reaches the far field answers to
    the far field. No block has an inner radial and an outer radial as its two
    i-sides — that separation is the whole point of the split.
  * ``ds_start`` ON THE OUTER RADIALS, DERIVED. This is the deliverable. Both shipped
    documents declare it as a literal read off a run and both warn that changing the
    inner count, the seam position or the wall height makes it wrong — a stale number
    nothing errors on, which is the same failure class as every binding-by-index
    defect this repo has tickets about. Here it is computed from the inner ring's own
    chord, count and first cell (``topology_spacing.last_interval``), so the seam
    cannot go stale.

THIS FAMILY WRITES NO GEOMETRY, AND THE SEAM IS THEREFORE THE USER'S (#133, #137,
#150). #150 asked what happens when a later family wants an offset the user never
sees; this is that family and the answer is that the rule HOLDS, at a cost of one user
action. A ``follows`` edge cannot attach to a generated corner — it needs a real
geometry with a segment id and a polyline, which is what carries the curve — so a
generated seam would have to be a written FILE, with no stable-id scheme, no sidecar
and no place in the project round trip. The refusal names ``CAD ▸ Offset Geometry…``
instead, which is where #152 put the tool that makes one.

THE SEAM MAY NOT BE ASSUMED TO BE AN OFFSET. On an offset-derived one the pairing
holds by construction (#152 returns one point per source point), which is why #154's
case needed no re-segmenting step — but a user may legitimately draw the middle ring
by hand, as #153's circle is, so the pairing is CHECKED and refused by name.
"""
from __future__ import annotations

from app.services.topology_binding import BindingError, outline_problem
from app.services.topology_preflight import (
    Refusal, nesting_refusal, no_context_refusal, outline_refusal,
    plan_refusal,
)
from app.services import topology_genfar as genfar
from app.services.topology_counts import (
    MAX_COUNT, circularity, nodes_for_growth, wall_count,
)
from app.services.topology_ogrid import MIN_BLOCKS, radial_law
from app.services.topology_ogrid_binding import (
    broken_in_ring_lists, parse_binding, ring_binding_problem,
)
from app.services.topology_spacing import last_interval
from app.services.topology_tworing_plan import (  # noqa: F401
    INERT_WHEN_BOUND, Plan,
)

#: The template's own name for the family, as stored in the project file.
FAMILY = "tworing"

#: The CAD action that makes a seam, named in the refusal rather than described. The
#: ONE spelling of it, for the reason ``BINDING_LISTS`` names each role once: two
#: refusals about the same missing geometry sending the user to two differently-worded
#: menus is the defect #138 fixed for "far field".
OFFSET_ACTION = "CAD ▸ Offset Geometry…"

#: Why this family needs three closed outlines, for the shared four-question cascade
#: (`topology_binding.outline_problem`). The one clause of it that is this family's own.
CLOSED_NOTE = "and every ring of a two-ring O-grid is a loop around a closed body."

#: The middle ring's role word, spelled once because the one refusal that names
#: :data:`OFFSET_ACTION` has to know which of the three lists it is about.
SEAM_ROLE = "seam"

#: Which stored list is which, as ``(role, model field, geometry field, edge prefix)``
#: — ``topology_ogrid_binding.BINDING_LISTS``'s own shape with a THIRD entry. The role
#: word is what every refusal and every repair row names, so a user with two broken
#: rings can tell which geometry each is about.
BINDING_LISTS = (("body", "tworing_body_segs", "tworing_body_geom", "w"),
                 (SEAM_ROLE, "tworing_seam_segs", "tworing_seam_geom", "s"),
                 ("far field", "tworing_far_segs", "tworing_far_geom", "o"))


def far_is_bound(model) -> bool:
    """Did the user NAME a far-field geometry? THE ONE PLACE that is decided.

    The stored NAME and never whether the lookup found anything: a name that
    resolves to nothing is a REFUSAL, because silently generating a far field
    there would hide a geometry the user deleted (#197's rule). It was spelled
    out at three call sites while a comment next door claimed `required_lists`
    was "the one place that decision is made" — it consumes the answer, it does
    not make it.
    """
    return bool(str(model.tworing_far_geom).strip())


def required_lists(far_bound: bool) -> tuple:
    """:data:`BINDING_LISTS`, or its first two when the far field is GENERATED.

    A truncated list rather than a skipped row inside each loop: every walk over the
    three outlines then asks its question of exactly the geometries that exist, and
    `zip` against the three names truncates with it. The SEAM is never dropped —
    `BINDING_LISTS[1]` — which is the rule this family is built on.
    """
    return BINDING_LISTS if far_bound else BINDING_LISTS[:2]


def _ring(segs, splits: int) -> list:
    """``[(seg id, t), ...]`` around the whole loop, in declaration order."""
    return [(s, j / float(splits)) for s in segs for j in range(splits)]


def _corner(g, seg: int, t: float):
    sp = g.spans.get(seg)
    return None if sp is None else sp.point_at(t)


def plan(model, ctx) -> Plan:
    """Everything this family derives from ``model`` against ``ctx``.

    Returns a :class:`Plan` whose ``problem`` is set rather than raising, because the
    panel asks this on every keystroke and a half-typed geometry name is not an error
    yet. :func:`build` asks the same question and turns a problem into the refusal.
    """
    p = Plan()
    if ctx is None:
        p.problem = ("this family binds to the geometry you drew, so it needs the "
                     "mesh's geometry list; none was supplied.")
        return p

    # THE FAR FIELD IS OPTIONAL AND THE SEAM IS NOT, which is this family's own
    # shape rather than the O-grid's copied twice. A generated outer boundary is an
    # analytic CURVE and legal (#197); a generated seam would have to be a stored
    # POLYLINE for a `follows` edge to attach to, which is the rule that holds.
    p.far_bound = far_is_bound(model)
    names = (model.tworing_body_geom, model.tworing_seam_geom, model.tworing_far_geom)
    gs = [ctx.geometry(n) for n in names]
    for (role, _f, _gf, _pre), name, g in zip(required_lists(p.far_bound), names, gs):
        why = outline_problem(ctx, role, name, g, closed_note=CLOSED_NOTE)
        # THE SEAM'S BLANK CASE IS THIS FAMILY'S OWN, and is the only one of the
        # twelve refusals in that cascade that is: it is the geometry a user is most
        # likely not to have, and the answer is a CAD action rather than a correction.
        if why and role == SEAM_ROLE and not str(name or "").strip():
            why = (f"name the seam geometry — the middle ring the two rings meet on. "
                   f"This family writes no geometry of its own, so draw one or make "
                   f"it with {OFFSET_ACTION}, which offsets the body by a distance "
                   f"and pairs segment for segment with it.")
        if why:
            p.problem = why
            return p
    body, seam, far = gs
    p.seam_geom = seam.spelling
    if p.far_bound:
        p.inert_rows = INERT_WHEN_BOUND

    # Read by NAME rather than through `getattr(model, field)`: the parameter gate
    # derives what a family reads by walking this module for `<x>.<model field>`, so
    # a read spelled as a lookup is invisible to it and the row goes down as a
    # control nothing reads (`tests/test_topology_param_specs.py` check 3).
    stored = (model.tworing_body_segs, model.tworing_seam_segs,
              model.tworing_far_segs)
    held = []
    for (role, _f, _gf, _pre), g, text in zip(required_lists(p.far_bound), gs, stored):
        ids, why = parse_binding(text, g.seg_ids, role)
        if why:
            p.problem = why
            return p
        held.append(ids)
    p.body_segs, p.seam_segs = held[0], held[1]
    p.far_segs = held[2] if p.far_bound else ()
    splits = max(1, int(model.tworing_splits))

    # Resolve, then order, then cover — every list before any question about counts.
    # `ring_binding_problem` is the ONE owner of that walk and of the reason it is in
    # that order, which matters more here than on the O-grid: with THREE lists, a
    # length complaint raised before the resolve would name no edge and point at any
    # of three geometries.
    lists = tuple((row[0], g, segs, row[3])
                  for row, g, segs in zip(required_lists(p.far_bound), gs, held))
    p.broken_edge, p.problem = ring_binding_problem(ctx, lists, splits)
    if p.problem:
        return p

    # PAIRED SEGMENT FOR SEGMENT, all three, and the SEAM's mismatch names the action
    # that makes one that pairs — which is this family's whole answer to #150's "a
    # template writes no geometry".
    nb = len(p.body_segs)
    if len(p.seam_segs) != nb:
        p.problem = (f"the body binds {nb} source segment(s) and the seam "
                     f"{len(p.seam_segs)}. The seam pairs with the body one to one, "
                     f"so segment it the same way you segmented the body — or make it "
                     f"with {OFFSET_ACTION}, which pairs by construction.")
        return p
    if p.far_bound and len(p.far_segs) != nb:
        p.problem = (f"the body binds {nb} source segment(s) and the far field "
                     f"{len(p.far_segs)}. Both rings pair one to one, so segment the "
                     f"far field the same way you segmented the body.")
        return p

    p.blocks = nb * splits
    if p.blocks < MIN_BLOCKS:
        p.problem = (f"{nb} source segment(s) x {splits} split(s) is {p.blocks} "
                     f"block(s) per ring — a ring needs at least {MIN_BLOCKS}. Raise "
                     f"'Splits Per Segment', or cut the body into more segments in "
                     f"the CAD stage.")
        return p

    cell = float(model.tworing_cell)
    if cell <= 0.0:
        p.problem = "the target cell edge length must be greater than zero."
        return p
    counts = []
    for s in p.body_segs:
        counts += [wall_count(body.spans[s].length / splits, cell)] * splits
    p.wall_counts = tuple(counts)
    p.n_theta = sum(c - 1 for c in counts)

    p.radius = body.equivalent_radius()
    p.seam_radius = seam.equivalent_radius()
    p.circularity = circularity(p.radius, body.perimeter)
    if p.far_bound:
        p.far_radius = far.equivalent_radius()
    else:
        # THE GENERATED ELLIPSE, derived before anything reads its radius, and sized
        # off the BODY's equivalent radius rather than the seam's so that the number
        # in the row means what it means on the O-grid — and so that moving the seam
        # does not move the far field.
        p.problem = genfar.derive(p, float(model.tworing_far_ratio),
                                  float(model.tworing_far_aspect), body)
        if p.problem:
            return p
        # CONTAINMENT IS WALKED OVER THE SEAM's OWN POINTS, not the body's and never
        # against an equivalent radius (#165's ruler mistake): the seam is the outer
        # ring's inner side, so an ellipse that contains the body and crosses the
        # seam is a far field with no ring outside it in places.
        p.problem = genfar.outside_body(p.far_centre, p.far_a, p.far_b, seam,
                                        what="seam")
        if p.problem:
            return p
    # BEFORE either derivation: a seam outside the far field or inside the body gives a
    # negative span, and `nodes_for_growth` would answer on it rather than refuse.
    if not p.radius < p.seam_radius < p.far_radius:
        p.problem = (f"the three outlines' equivalent radii are body {p.radius:.4g}, "
                     f"seam {p.seam_radius:.4g}, far field {p.far_radius:.4g} — the "
                     f"seam has to lie strictly between the other two, or there is no "
                     f"ring on one side of it.")
        return p

    p.ratio = radial_law(p.n_theta)
    p.first_cell = (ctx.first_cell if ctx.first_cell > 0.0
                    else p.radius * (p.ratio - 1.0))
    p.inner_derived = nodes_for_growth(p.seam_radius - p.radius, p.first_cell, p.ratio)
    p.inner_clamped = p.inner_derived >= MAX_COUNT
    want = int(model.tworing_radial_inner)
    p.inner_overridden = want >= 2
    p.inner = want if p.inner_overridden else p.inner_derived

    # ── THE ONE NUMBER THIS FAMILY EXISTS FOR ────────────────────────────────
    # The chord of `ri0`, because that is the length the mesher distributes the inner
    # ring's nodes along — NOT `seam_radius - radius`, which is an area-equivalent
    # idealisation good enough to pick a COUNT and not good enough to match a cell. On
    # the shipped ellipse the two are 0.2500509 and 0.2630905 — 5% apart, which would
    # be 5% of visible seam.
    #
    # ONE ds_start FOR THE WHOLE RING, taken at ring position 0, which is what both
    # shipped documents declare. The inner radials of a non-circular body are NOT all
    # the same length (0.250051 and 0.250001 on the shipped ellipse), so a per-edge
    # `ds_start` would be strictly more continuous — and would stop this family
    # reproducing the two documents it exists to replace. Recorded as a blind spot in
    # the gate rather than taken.
    b0, m0 = p.body_segs[0], p.seam_segs[0]
    pb, pm = _corner(body, b0, 0.0), _corner(seam, m0, 0.0)
    if pb is None or pm is None:
        p.problem = ("the first corner of the body or of the seam could not be placed "
                     "on its own segment, so there is no radial to measure.")
        return p
    p.inner_chord = ((pb[0] - pm[0]) ** 2 + (pb[1] - pm[1]) ** 2) ** 0.5
    p.ds_start = last_interval(p.inner_chord, p.inner, p.first_cell)
    if p.ds_start <= 0.0:
        p.problem = (f"the inner ring's first radial has no length (body segment "
                     f"{b0} and seam segment {m0} start at the same point), so the "
                     f"spacing the outer ring must continue from cannot be derived.")
        return p

    p.outer_derived = nodes_for_growth(p.far_radius - p.seam_radius, p.ds_start,
                                       p.ratio)
    p.outer_clamped = p.outer_derived >= MAX_COUNT
    want = int(model.tworing_radial_outer)
    p.outer_overridden = want >= 2
    p.outer = want if p.outer_overridden else p.outer_derived

    # The RINGS' own winding, not the outlines': a binding list given in reverse walks
    # the outline backwards, and only the ring can see that. All THREE, because a seam
    # wound against the body is as fatal as a far field wound against it.
    areas = []
    for _who, g, segs, _prefix in lists:
        r = _ring(segs, splits)
        areas.append(g.signed_area([s for s, _ in r], [t for _, t in r]))
    if any(a == 0.0 for a in areas):
        p.problem = ("a corner ring has no area — check that the three geometries are "
                     "the closed outlines they look like.")
        return p
    if len({a > 0.0 for a in areas}) != 1:
        p.problem = ("the body, the seam and the far field are not all wound the same "
                     "way, so radial edges would cross the rings. Redraw the odd one "
                     "out in the other direction.")
        return p
    p.ccw = areas[0] > 0.0
    return p


def build(model, ctx=None) -> dict:
    """The two-ring O-grid document for ``model``, bound to ``ctx``'s geometries."""
    p = plan(model, ctx)
    if p.problem:
        raise BindingError(
            f"the two-ring O-grid template cannot build a document: {p.problem}",
            edge=p.broken_edge)

    body = ctx.geometry(model.tworing_body_geom)
    seam = ctx.geometry(model.tworing_seam_geom)
    far = ctx.geometry(model.tworing_far_geom) if p.far_bound else None
    splits = max(1, int(model.tworing_splits))
    rings = (_ring(p.body_segs, splits), _ring(p.seam_segs, splits),
             _ring(p.far_segs, splits) if p.far_bound else ())
    n = len(rings[0])

    corners, edges, blocks = [], [], []
    # THE GENERATED CORNERS PAIR WITH THE SEAM's, not with the body's, and that is
    # this family's one decision the O-grid does not have to make. The outer blocks
    # run from the seam to the far field, so it is the SEAM they have to stay normal
    # to; pairing with the body would hand the outer ring the inner ring's own
    # arc-length distribution, which the seam has already departed from.
    gen_far = [] if p.far_bound else genfar.corners(
        p, [f"f{k}" for k in range(n)],
        [seam.spans[s].point_at(t) for s, t in rings[1]])
    for k in range(n):
        for pre, g, ring in zip("bm", (body, seam), rings):
            s, t = ring[k]
            corners.append({"id": f"{pre}{k}", "kind": "on_geometry",
                            "geom": g.spelling, "seg": s, "t": t})
        if p.far_bound:
            s, t = rings[2][k]
            corners.append({"id": f"f{k}", "kind": "on_geometry",
                            "geom": far.spelling, "seg": s, "t": t})
        else:
            corners.append(gen_far[k])

    for k in range(n):
        # TWO equivalence classes, each wrapping around and closing, so each declares
        # its count ONCE. The inner radials mark their body end a wall end, so the
        # mesher's tanh law solves for BL_INITIAL_THICKNESS there; the outer ones
        # declare `ds_start` instead — that end is not a wall and the number is not
        # BL_INITIAL_THICKNESS, it is the interval the inner ring finished on. EVERY
        # outer radial carries it, because spacing does not propagate along a class,
        # only counts do.
        ri = {"id": f"ri{k}", "corners": [f"b{k}", f"m{k}"], "kind": "interface",
              "spacing": {"wall_ends": "start"}}
        ro = {"id": f"ro{k}", "corners": [f"m{k}", f"f{k}"], "kind": "interface",
              "spacing": {"ds_start": p.ds_start}}
        if k == 0:
            ri["count"], ro["count"] = p.inner, p.outer
        edges += [ri, ro]
    for k in range(n):
        nxt = (k + 1) % n
        bs, ms = rings[0][k][0], rings[1][k][0]
        # One seed per circumferential class, declared on the WALL — the side whose
        # length the user asked for in physical units. The seam edge and the far arc
        # arrive by propagation through the two blocks that share this position.
        edges.append({"id": f"w{k}", "corners": [f"b{k}", f"b{nxt}"], "kind": "wall",
                      "count": p.wall_counts[k],
                      "binding": {"geom": body.spelling,
                                  "seg": ctx.resolve(f"w{k}", body.spelling, bs)}})
        # `follows`, not `binding` (#151): the same object with the boundary-condition
        # half removed, because an interior line is not a boundary. The edge lies on
        # the seam's own polyline by arc length and does nothing else — it exports no
        # face and carries no condition, whatever the sidecar labels that segment.
        edges.append({"id": f"s{k}", "corners": [f"m{k}", f"m{nxt}"],
                      "kind": "interface",
                      "follows": {"geom": seam.spelling,
                                  "seg": ctx.resolve(f"s{k}", seam.spelling, ms)}})
        if p.far_bound:
            edges.append({"id": f"o{k}", "corners": [f"f{k}", f"f{nxt}"],
                          "kind": "wall",
                          "binding": {"geom": far.spelling,
                                      "seg": ctx.resolve(f"o{k}", far.spelling,
                                                         rings[2][k][0])}})
        else:
            edges.append(genfar.edge(p, f"o{k}", f"f{k}", f"f{nxt}"))
    for k in range(n):
        nxt = (k + 1) % n
        # [south, east, north, west]. CCW: i runs OUTWARD and j anticlockwise, so the
        # inner block's EAST is the seam and the outer block's WEST is that SAME
        # declared edge — which is where the two rings are welded, by node identity.
        # CW: the mirror, which is the same four ids reversed; either way the opposite
        # pairs are (radial, radial) and (arc, arc), so the classes are unchanged and
        # the mirror is one expression rather than a second builder.
        inner = [f"ri{k}", f"s{k}", f"ri{nxt}", f"w{k}"]
        outer = [f"ro{k}", f"o{k}", f"ro{nxt}", f"s{k}"]
        blocks.append({"id": f"q{k}", "edges": inner if p.ccw else inner[::-1]})
        blocks.append({"id": f"p{k}", "edges": outer if p.ccw else outer[::-1]})

    return {"format_version": 1, "corners": corners, "edges": edges, "blocks": blocks}


def broken_bindings(model, ctx) -> tuple:
    """This family's THREE lists, walked by :func:`broken_in_ring_lists`.

    All three, and each row NAMING which — a user whose CAD edit broke the body and
    the seam at once cannot tell two unlabelled rows apart. The role words are
    :data:`BINDING_LISTS`'s, which is also where every refusal above takes its noun.
    """
    # THE FAR FIELD's ROW GOES WITH IT when it is generated: there is no binding to
    # be broken, and a repair row for a geometry the user never named would be the
    # panel inventing work. `far_is_bound` is where that is decided, once.
    return broken_in_ring_lists(model, ctx,
                                required_lists(far_is_bound(model)),
                                model.tworing_splits)


def preflight(model, ctx=None) -> tuple:
    """Why this family cannot split its ring on the seam it has been given,
    before anything runs (#165).

    The O-grid's three layers over THREE outlines rather than two, and the one
    that earns its keep here is the middle: :func:`plan` nests body, seam and far
    field by EQUIVALENT RADIUS, so a seam that crosses the body on one side and
    the far field on the other has an equivalent radius neatly between the two
    and is accepted. A ring that crosses is exactly what this family cannot fill,
    and :func:`nesting_refusal` walks both neighbouring pairs rather than the
    first, because a drawing with both wrong costs two edits and not two runs.

    The SEAM's blank case keeps the family's own sentence — it names
    :data:`OFFSET_ACTION`, which is a CAD action and not a correction, and is the
    one geometry an operator is most likely not to have drawn.
    """
    if ctx is None:
        return no_context_refusal(
            "geometry", "the body, the seam and the far field")
    far_bound = far_is_bound(model)
    names = (model.tworing_body_geom, model.tworing_seam_geom,
             model.tworing_far_geom)
    gs = [ctx.geometry(n) for n in names]
    out = []
    for (role, _f, _gf, _pre), name, g in zip(required_lists(far_bound), names, gs):
        r = outline_refusal(ctx, role, name, g, closed_note=CLOSED_NOTE)
        if r is not None and role == SEAM_ROLE and not str(name or "").strip():
            r = Refusal(
                "name the seam geometry — the middle ring the two rings meet "
                "on. This family writes no geometry of its own.",
                fix=f"Draw one, or make it with {OFFSET_ACTION}, which offsets "
                    f"the body by a distance and pairs segment for segment "
                    f"with it.")
        if r is not None:
            out.append(r)
    if out:
        return tuple(out)
    nested = nesting_refusal(tuple((row[0], g)
                                   for row, g in zip(required_lists(far_bound), gs)))
    if nested:
        return nested
    return plan_refusal(plan(model, ctx).problem)
