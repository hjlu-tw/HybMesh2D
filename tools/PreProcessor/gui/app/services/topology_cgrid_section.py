"""What a C-grid reads off the SECTION the user drew, and its refusals (issue #148).

Split out of ``topology_cgrid.py`` for the reason ``topology_ogrid_binding.py`` was
split out of ``topology_ogrid.py``: the two halves answer different questions, and
together they pass the repo's ~500-line standard. Everything here is about the
AEROFOIL — is the named geometry a closed, two-surface section, do its stored bindings
still resolve, which joint is the trailing edge, which surface is the upper one — plus
the far field those answers place. Nothing here knows what a block is. What is left
next door is the family: the derivation, the plan and the document.

Qt-free, like every module in this package. It reads no field of ``TopologyModel``:
the values arrive as arguments, so the parameters-to-families gate
(``tests/test_topology_param_specs.py``) still sees every ``cgrid_*`` read in the
family's own module, where it attributes rows to families by prefix.

A BLUNT TRAILING EDGE IS REFUSED HERE. A C-grid puts all four of its blocks on one
declared trailing-edge corner, and an open trailing edge has no such point; a section
drawn blunt arrives from the CAD stage as THREE segments — upper, lower and the base
between them (``naca_airfoil.segment_parts``) — which is what the count below names.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.topology_binding import BindingError
from app.services.topology_ogrid_binding import order_problem, parse_binding

#: How many surface segments a section the C-grid can wrap is split into: the upper
#: and the lower, meeting at the trailing edge. THREE is the blunt section, whose
#: base is a segment of its own and whose two surfaces never meet.
SHARP_SEGMENTS = 2
BLUNT_SEGMENTS = 3

#: The role word this family gives its one binding list, and the two edge ids its two
#: stored positions become. Spelled ONCE, because #138 bought that rule the hard way:
#: the O-grid's ``plan`` said "far-field" where ``BINDING_LISTS`` said "far field", so
#: two refusals about one list hyphenated it differently. Every refusal here, the
#: repair rows the family reports and the ids ``build`` emits all read them from here.
SECTION_ROLE = "aerofoil"
SURFACE_EDGES = ("af_up", "af_lo")

#: The same rule for the OPTIONALLY DRAWN far field (#149): its role word, its six
#: corner ids and its six edge ids, in the order the six block sides run — counter-
#: clockwise from the outlet point level with the wake. ONE spelling, and it is the
#: shipped hand-written document's own (``examples/topology/cgrid_naca0012.json``),
#: so "the template reproduces the target" stays a comparison of like with like.
#: ``FAR_CORNERS[k]`` is the t = 0 of the bound segment at position k and
#: ``FAR_EDGES[k]`` is the side that lies on it.
FAR_ROLE = "far field"
FAR_CORNERS = ("wk", "fu", "f1", "f2", "f3", "fl")
FAR_EDGES = ("e_out_up", "e_ff_up", "e_ff_nose_up", "e_ff_nose_lo", "e_ff_lo",
             "e_out_lo")
#: How many segments a far field the C-grid can bind is cut into — one per block
#: side, which is what makes each side's boundary condition readable off its own.
FAR_SEGMENTS = len(FAR_EDGES)
#: Which corner is dead ahead of the nose, and therefore the furthest UPSTREAM.
#: What :func:`resolve_far` measures the ring's starting joint against.
FAR_NOSE_POS = FAR_CORNERS.index("f2")


@dataclass(frozen=True)
class Section:
    """One resolved aerofoil: which segment is which, and where its ends are."""

    #: The bound segment ids, in the order the binding holds them.
    segs: tuple[int, ...]
    #: The segment whose t = 0 is the trailing edge, and the other one.
    te_seg: int
    le_seg: int
    #: The segment lying on the +y side of the chord, and the other one.
    up_seg: int
    lo_seg: int
    te_xy: tuple[float, float]
    le_xy: tuple[float, float]
    chord: float
    up_len: float
    lo_len: float

    @property
    def up_first(self) -> bool:
        """True when the upper surface is the one that LEAVES the trailing edge.

        Which is the only thing a section drawn clockwise changes: its two surface
        edges are then declared in the other direction, which a block's west may be.
        """
        return self.up_seg == self.te_seg


def held_bindings(ctx, g, segs_text: str, who: str, edge_at) -> tuple:
    """``(ids, problem, broken edge)`` — the stored list, parsed AND resolved.

    The ONE owner of "parse the string, then resolve every id against the geometry,
    IN THAT ORDER, naming the edge" for this family's two lists. Both readers had
    their own copy of those six lines and the order within them is #138's rule, not
    a convenience: a list that is short because one id stopped resolving must be
    answered with the EDGE that stopped resolving, not with a sentence about how
    many ids there are — which names no edge and sends the user to the wrong
    geometry. Two copies of an ordering rule is two chances to get the order wrong.

    ``edge_at`` maps a POSITION in the stored list to the ONE edge id a refusal
    about that position names, which is the only thing the two lists differ in:
    :func:`far_edge_at` and :func:`section_edge_at`.
    """
    held, why = parse_binding(segs_text, g.seg_ids, who)
    if why:
        return (), why, ""
    for pos, sid in enumerate(held):
        try:
            ctx.resolve(edge_at(pos), g.spelling, sid)
        except BindingError as exc:
            return (), str(exc), exc.edge
    return tuple(held), "", ""


def resolve_section(ctx, geom_name: str, segs_text: str) -> tuple:
    """``(geometry, Section, problem, broken edge)`` for the named, bound section.

    The refusals are in the order the user can act on them: is there a geometry, is
    it a closed outline with per-segment data, is it split into the two surfaces a
    C-grid wraps, do the stored ids still resolve, and can the trailing edge be told
    from the leading one.
    """
    name = str(geom_name or "").strip()
    if not name:
        return None, None, ("name the aerofoil geometry — this family binds to a "
                            "section from the CAD stage and writes none of its "
                            "own."), ""
    g = ctx.geometry(name)
    if g is None:
        return None, None, (f"the aerofoil geometry '{name}' is not one of this "
                            f"mesh's geometries. It loads: "
                            f"{', '.join(ctx.names()) or '(nothing)'}."), ""
    if not g.spans:
        return None, None, (f"the aerofoil geometry '{g.spelling}' carries no "
                            f"per-segment data, so there is nothing to bind to. That "
                            f"comes from the '.meta' sidecar the PreProcessor writes "
                            f"beside the .dat; re-export it from the CAD stage."), ""
    if not g.closed:
        return None, None, (f"the aerofoil geometry '{g.spelling}' is not a closed "
                            f"loop, so its upper and lower surfaces do not meet at a "
                            f"trailing edge."), ""
    if len(g.seg_ids) == BLUNT_SEGMENTS:
        return None, None, (
            f"'{g.spelling}' carries {BLUNT_SEGMENTS} segments. A section drawn with "
            f"a BLUNT trailing edge arrives as three — the upper surface, the lower "
            f"surface and the base between them — and its two surfaces never meet, "
            f"so there is no single trailing-edge corner for the four blocks to "
            f"share. A C-grid needs a SHARP trailing edge: redraw the section with "
            f"'Sharp trailing edge' on."), ""
    if len(g.seg_ids) != SHARP_SEGMENTS:
        return None, None, (
            f"a C-grid wraps a section split into exactly {SHARP_SEGMENTS} surfaces, "
            f"upper and lower, meeting at the trailing edge — '{g.spelling}' carries "
            f"{len(g.seg_ids)} "
            f"({', '.join(str(s) for s in g.seg_ids) or 'none'})."), ""

    # The edge a resolve refusal names is the one the stored POSITION would become on
    # a section drawn the way the CAD stage draws one (upper surface first). Which
    # bound segment IS the upper is decided below, from coordinates — and that
    # decision needs both spans, which is exactly what a broken binding does not
    # have. `topology_cgrid.broken_bindings` reports both surface edges for the same
    # reason.
    held, why, edge = held_bindings(ctx, g, segs_text, SECTION_ROLE, section_edge_at)
    if why:
        return None, None, why, edge
    if set(held) != set(g.seg_ids) or len(held) != SHARP_SEGMENTS:
        return None, None, (
            f"the stored binding names segment(s) "
            f"{', '.join(str(s) for s in held) or 'none'} while '{g.spelling}' "
            f"carries {', '.join(str(s) for s in g.seg_ids)}. A C-grid binds BOTH "
            f"surfaces of the section — every segment of it is one block side."), ""

    a, b = held
    pa, pb = g.spans[a].point_at(0.0), g.spans[b].point_at(0.0)
    if pa is None or pb is None:
        return None, None, (f"'{g.spelling}' has a segment with no length, so its "
                            f"trailing edge cannot be placed."), ""
    if pa[0] == pb[0]:
        return None, None, (
            f"'{g.spelling}' joins its two surfaces at two points the same distance "
            f"downstream (x = {pa[0]:.4g}), so there is no telling the trailing edge "
            f"from the leading edge. A C-grid puts the wake behind the trailing "
            f"edge, which is the downstream one."), ""
    te_seg, le_seg = (a, b) if pa[0] > pb[0] else (b, a)
    te_xy, le_xy = ((pa, pb) if pa[0] > pb[0] else (pb, pa))

    # WHICH SURFACE IS THE UPPER ONE IS MEASURED, not taken from the order the CAD
    # happened to write the segments in: the cross product of the chord with the
    # midpoint of the segment that leaves the trailing edge is positive exactly when
    # that segment runs along the +y side.
    mid = g.spans[te_seg].point_at(0.5)
    cx, cy = te_xy[0] - le_xy[0], te_xy[1] - le_xy[1]
    side = (0.0 if mid is None
            else cx * (mid[1] - le_xy[1]) - cy * (mid[0] - le_xy[0]))
    if side == 0.0:
        return None, None, (f"segment {te_seg} of '{g.spelling}' lies on the chord "
                            f"line (or has no length), so the upper surface cannot "
                            f"be told from the lower."), ""
    up_seg, lo_seg = (te_seg, le_seg) if side > 0.0 else (le_seg, te_seg)
    return g, Section(segs=tuple(held), te_seg=te_seg, le_seg=le_seg, up_seg=up_seg,
                      lo_seg=lo_seg, te_xy=te_xy, le_xy=le_xy,
                      chord=math.hypot(cx, cy), up_len=g.spans[up_seg].length,
                      lo_len=g.spans[lo_seg].length), "", ""


def far_corners(te_xy, x_le: float, wake_len: float, radius: float) -> dict:
    """The six free far-field corners, in WORLD axes with the flow along +x.

    Named the shipped hand-written document's own names, and placed so that with a
    unit chord, a wake of 19 and a radius of 10 they land exactly on its six corners
    — which is what makes "the template reproduces the target" a comparison rather
    than a resemblance (``tests/test_topology_cgrid.py`` check 13).

    ``y0`` is the TRAILING edge's height, not the leading edge's, so the wake leaves
    the section horizontally and the far field is symmetric about the line it runs
    down. On a section with camber or incidence those two heights differ, and the
    wake is the one that has to be straight.
    """
    x_te, y0 = te_xy
    x_out = x_te + wake_len
    return {"wk": (x_out, y0), "fu": (x_out, y0 + radius),
            "f1": (x_te, y0 + radius), "f2": (x_le - radius, y0),
            "f3": (x_te, y0 - radius), "fl": (x_out, y0 - radius)}


def generated_ring(far: dict) -> list:
    """The GENERATED far field's outline, as the polygon :func:`outside_point` tests.

    ``wk`` is left out because it lies ON the outlet plane between ``fu`` and
    ``fl``; the five remaining corners bound exactly the same region.
    """
    return [far[k] for k in ("fu", "f1", "f2", "f3", "fl")]


def drawn_ring(g) -> list:
    """A DRAWN far field's outline, as the polygon :func:`outside_point` tests (#149).

    Its own POLYLINES rather than the six corner chords, which is the whole
    difference between the two paths: a drawn D curves OUTWARD between its joints,
    so a chord ring would refuse a section that sits comfortably inside the shape
    the user actually drew. The generated hexagon has no such gap — its sides ARE
    the chords — which is why :func:`generated_ring` above is the corners.
    """
    return [pt for sid in g.seg_ids for pt in g.spans[sid].points[:-1]]


def outside_point(ring, g):
    """The first point of ``g`` the outline ``ring`` does not contain, or ``None``.

    THE SECTION HAS TO BE INSIDE ITS FAR FIELD, and it is checked by walking the
    section's own points rather than by a rule of thumb about chords: a radius that is
    generous for a thin aerofoil at zero incidence is not for a thick one at 15
    degrees, and a section poking through its own far field produces blocks that fold
    rather than a refusal the user can read.

    ``ring`` is a closed polygon as a list of points, so the same containment test
    serves the generated hexagon and the drawn D — the two differ in what the ring
    IS, which is :func:`generated_ring`'s and :func:`drawn_ring`'s answer, not in
    how it is tested.
    """
    ring = list(ring)
    # NO short-ring guard. One that returned None would report a degenerate outline
    # as CONTAINING the section, which is the one direction this check must not fail
    # in; with none, a ring of fewer than three points contains nothing and the
    # caller refuses. Unreachable from either caller today (five corners and six
    # polylines), and shaped so that it staying unreachable is not load bearing.
    for sp in g.spans.values():
        for pt in sp.points:
            x, y = pt
            hit = False
            for k in range(len(ring)):
                x0, y0 = ring[k]
                x1, y1 = ring[(k + 1) % len(ring)]
                if (y0 > y) != (y1 > y):
                    if x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                        hit = not hit
            if not hit:
                return pt
    return None


def section_edge_at(pos: int) -> str:
    """The edge a stored SECTION position names, for a refusal about that position.

    The section is drawn the way the CAD stage draws one — upper surface first — so
    position 0 is ``af_up`` and position 1 ``af_lo``; anything past the end clamps,
    because a list longer than the section has is refused on its length one line
    later and the refusal still has to name something. NOT the same question as
    `topology_cgrid.broken_bindings`, which reports BOTH edges for one broken
    position: there the two spans are missing, so which is the upper cannot be
    measured. Here the position is all that is being described.
    """
    return SURFACE_EDGES[min(pos, len(SURFACE_EDGES) - 1)]


def far_edge_at(i: int) -> str:
    """``ring position -> edge id`` for the far field, :func:`edges_by_prefix`'s peer.

    The far-field ring's six edges have six NAMES rather than a prefix and an index,
    which is the whole reason ``order_problem`` and ``cover_problem`` take a callable
    since #149: the mesher's cover rule is one rule and a second copy of it differing
    only in an f-string is how two refusals about one list come to disagree.
    """
    return FAR_EDGES[i % len(FAR_EDGES)]


def resolve_far(ctx, geom_name: str, segs_text: str) -> tuple:
    """``(geometry, segment ids, problem, broken edge)`` for a DRAWN far field (#149).

    ``(None, (), "", "")`` for a blank name, which is not a refusal: the far field is
    then GENERATED from the two lengths, which is #148's default and stays it. The
    caller tells the two apart by the geometry, not by the sentence.

    THE REFUSALS ARE THE O-GRID'S, ASKED ABOUT SIX NAMED EDGES. Everything here that
    is not the segment COUNT is ``parse_binding``, ``ctx.resolve``, ``order_problem``
    and ``cover_problem`` — the same four this package already has, which is what
    makes a drawn far field a branch rather than a mechanism. What is this family's
    own is the last pair: the six block sides run from the outlet point level with
    the wake, counter-clockwise, so the ring's WINDING and WHERE IT STARTS are both
    binding information and both are MEASURED rather than trusted. Without them a
    far field drawn the other way round, or drawn starting at another joint, binds a
    rotation in which every id still resolves and every side still lies on its own
    segment — and the mesher then folds the four blocks instead of refusing them,
    which is this package's own worst outcome (a mesh that runs and is wrong).
    """
    name = str(geom_name or "").strip()
    if not name:
        return None, (), "", ""
    g = ctx.geometry(name)
    if g is None:
        return None, (), (f"the far-field geometry '{name}' is not one of this "
                          f"mesh's geometries. It loads: "
                          f"{', '.join(ctx.names()) or '(nothing)'}. Clear the row "
                          f"to generate the far field from the two lengths "
                          f"instead."), ""
    if not g.spans:
        return None, (), (f"the far-field geometry '{g.spelling}' carries no "
                          f"per-segment data, so there is nothing to bind to. That "
                          f"comes from the '.meta' sidecar the PreProcessor writes "
                          f"beside the .dat; re-export it from the CAD stage."), ""
    if not g.closed:
        return None, (), (f"the far-field geometry '{g.spelling}' is not a closed "
                          f"loop, and a C-grid's outer boundary closes: the two "
                          f"outlet halves and the D between them."), ""
    if len(g.seg_ids) != FAR_SEGMENTS:
        return None, (), (
            f"a C-grid's far field is cut into exactly {FAR_SEGMENTS} segments, one "
            f"per block side — the two outlet halves either side of the wake and "
            f"the four of the D ({', '.join(FAR_EDGES)}) — and '{g.spelling}' "
            f"carries {len(g.seg_ids)} "
            f"({', '.join(str(s) for s in g.seg_ids) or 'none'}). Split it into "
            f"{FAR_SEGMENTS}, or clear the row to generate the far field from the "
            f"two lengths instead."), ""

    held, why, edge = held_bindings(ctx, g, segs_text, FAR_ROLE, far_edge_at)
    if why:
        return None, (), why, edge
    if len(held) != FAR_SEGMENTS or set(held) != set(g.seg_ids):
        return None, (), (
            f"the stored binding names segment(s) "
            f"{', '.join(str(s) for s in held) or 'none'} while '{g.spelling}' "
            f"carries {', '.join(str(s) for s in g.seg_ids)}. A C-grid binds ALL "
            f"{FAR_SEGMENTS} sides of its far field — every segment of it is one "
            f"block side."), ""
    # ORDER ONLY, and `cover_problem` is NOT asked here — which is stated rather
    # than left to be discovered. The check above forces the binding to be a whole
    # PERMUTATION of the outline's six segments, and `order_problem` then leaves
    # only its six ROTATIONS; every rotation of a full permutation covers the
    # outline by construction, so the cover check cannot fire. Measured over all
    # 720 permutations of a six-segment outline: 714 refused on order, 6 accepted,
    # 0 reaching cover. The O-grid needs it because its binding may legally be a
    # SUBSET of a longer list; this one may not.
    edge, why = order_problem(FAR_ROLE, g, held, 1, far_edge_at)
    if why:
        return None, (), why, edge

    # THE CORNERS ARE PLACED BEFORE THE RING IS MEASURED, because `signed_area`
    # answers 0.0 both for a ring that encloses nothing and for one whose corners
    # could not be placed — its own docstring says the caller must report that as a
    # refusal rather than reading it as a direction. Asking about the direction
    # first told the user to redraw a degenerate outline backwards, and left the
    # no-length refusal below it unreachable.
    xs = []
    for sid in held:
        pt = g.spans[sid].point_at(0.0)
        if pt is None:
            return None, (), (f"'{g.spelling}' has a segment with no length, so its "
                              f"corners cannot be placed."), ""
        xs.append(pt[0])
    area = g.signed_area(held, [0.0] * FAR_SEGMENTS)
    if area == 0.0:
        return None, (), (f"the six corners of '{g.spelling}' enclose no area — "
                          f"check that it is the closed outline it looks like."), ""
    if area < 0.0:
        return None, (), (
            f"'{g.spelling}' runs its six segments CLOCKWISE, and the C's blocks are "
            f"declared counter-clockwise — every radial edge would cross its own "
            f"block. Redraw the far field in the other direction."), ""

    # WHERE THE RING STARTS IS BINDING INFORMATION HERE, unlike the O-grid's, whose
    # ring has no first segment. Corner `wk` is the outlet point level with the
    # wake and is position 0 by construction, so the joint dead ahead of the nose
    # — the far field's furthest-UPSTREAM one, which is what `f2` is — has to be
    # position FAR_NOSE_POS. Measured rather than assumed, and a TIE is refused
    # rather than resolved: two joints the same distance upstream cannot say which
    # of them is the nose.
    lo = min(xs)
    if xs.count(lo) > 1:
        return None, (), (
            f"'{g.spelling}' has two corners the same distance upstream "
            f"(x = {lo:.4g}), so there is no telling which one is dead ahead of the "
            f"nose. A C-grid's far field has ONE furthest-upstream corner, and it is "
            f"where the two halves of the D meet."), ""
    at = xs.index(lo)
    if at != FAR_NOSE_POS:
        return None, (), (
            f"'{g.spelling}' puts its furthest-upstream corner (x = {lo:.4g}) at "
            f"segment {held[at]}, position {at} of its outline, where a C-grid needs "
            f"it at position {FAR_NOSE_POS}. The six sides run counter-clockwise "
            f"from the OUTLET POINT LEVEL WITH THE WAKE: "
            f"{', '.join(FAR_EDGES)}. Redraw the far field starting there, or "
            f"re-point the binding so segment {held[at]} lands at position "
            f"{FAR_NOSE_POS}."), ""
    return g, tuple(held), "", ""
