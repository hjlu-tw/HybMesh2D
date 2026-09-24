"""The C-grid family: a wake CUT and a four-way trailing-edge corner (issue #148).

A PURE FUNCTION of ``(model, context)``, like the H-grid and the O-grid beside it — no
Qt, no mesher, no canvas, no filesystem. What it adds to the O-grid is not a mechanism
(it reuses the registry, the stable-id bindings, the projection funnel and the canvas
skeleton unchanged) but the two STRUCTURES that made
``examples/topology/cgrid_naca0012.json`` the hardest of the five shipped documents to
have typed by hand:

  1. THE WAKE IS ONE ``cut`` EDGE, and it is the WEST of BOTH wake blocks. It is not a
     boundary of anything: no face of it reaches the ``.bnd``, and the two blocks share
     its nodes by identity, so the wake is continuous rather than two surfaces that
     happen to coincide.
  2. THE TRAILING EDGE IS ONE DECLARED CORNER where all four blocks meet. Five edges
     end on it — the cut, the two trailing-edge radials and the two aerofoil surfaces —
     and because it is ONE declaration it is one node, welded by identity with no
     tolerance anywhere.

A BLUNT TRAILING EDGE IS REFUSED, NOT REPAIRED. Structure 2 needs the two surfaces to
meet at a point; an open trailing edge has no such point, and inventing one would put
four blocks on a geometry the user did not draw. A section drawn blunt arrives from the
CAD stage as THREE segments (upper, lower and the base between them, see
``naca_airfoil.segment_parts``), and that is what this family refuses by name.

THE FAR FIELD IS GENERATED FROM TWO LENGTHS, WHICH IS THE ONE PLACE THIS FAMILY DEPARTS
FROM THE O-GRID. #133 decided a template writes no geometry, and the O-grid therefore
asks the user to DRAW its far field — a radius alone would have made it a polygon with
as many sides as there are blocks, i.e. a square. Here the ticket's own demo is "fill in
wake length, far-field radius and target cell edge", so the six far-field corners are
FREE coordinates and their six edges are the straight lines between them. Two consequences,
stated rather than discovered:

  * the outer boundary is a hexagon where the shipped hand-written document has a curved
    D, which costs non-orthogonality at the one corner where they differ and nothing at
    the wall (measured in ``tests/test_topology_cgrid.py`` check 14);
  * a free corner belongs to no geometry, so those six sides carry the config's
    ``BC_GEOM`` and cannot carry an ``outlet`` of their own. The section's own walls DO
    read their conditions off its CAD segments, which is what the aerofoil is bound for.

THE SECTION IS READ, NOT ASSUMED. Which joint is the trailing edge (the one further
downstream), which surface is the upper one (the side of the chord its midpoint lies on)
and therefore which way round the two bound segments go are all MEASURED from the
geometry. That is what lets one document shape serve a section drawn clockwise as well as
one drawn anticlockwise, with no mirrored block tuple: the far field is laid out in world
axes either way, and only the two surface edges change the direction they are declared in
— which the mesher's ring rule allows for a block's east, north and west.

THE FIRST CELL HEIGHT IS THE RUN'S ``BL_INITIAL_THICKNESS``, under the name it already
has (#133), declared in ``Family.reads_context`` so the detached provenance summary names
it (#139).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.topology_binding import BindingError, BrokenBinding
from app.services.topology_cgrid_section import (
    far_corners, outside_point, resolve_section,
)
from app.services.topology_ogrid import wall_count
from app.services.topology_ogrid_binding import parse_binding

#: The template's own name for the family, as stored in the project file.
FAMILY = "cgrid"

#: The cell-to-cell expansion the wake and radial derivations grow at. NOT a tuned
#: constant: it is the red line of this repo's own quality ruler
#: (``tools/scripts/visualize_dat.py --quality``: green < 1.05, orange 1.05-1.2, red
#: > 1.2), so a count derived from it is "the fewest nodes that never exceed the
#: expansion this project already calls bad". The shipped hand-written document's
#: own radial count, 41, comes out of it at 43 — which is the closest thing to a
#: check on the number that exists.
GROWTH = 1.2

#: The node count a derivation will not exceed however small a first cell is asked
#: for. A refusal would be worse — the number is a DEFAULT and overridable — but so
#: would silently seeding a count that allocates gigabytes. The O-grid's own floor,
#: for the same reason.
MAX_NODES = 5000


def nodes_for_growth(span: float, first_cell: float, ratio: float = GROWTH) -> int:
    """Nodes to cross ``span`` starting at ``first_cell`` and growing at ``ratio``.

    A geometric series of ``n`` intervals covers ``ds * (q**n - 1) / (q - 1)``; the
    count is the ``n`` at which that reaches ``span``, plus one for the node the
    intervals end on. The same shape as the O-grid's ``radial_count`` and a different
    question: there the ratio is DERIVED from the circumferential cell count (the 1:1
    criterion on a ring), here it is the fixed expansion above, because a wake and a
    C-grid's outward direction have no ring to take a ratio from.
    """
    q = float(ratio)
    if span <= 0.0 or first_cell <= 0.0 or q <= 1.0:
        return 2
    n = math.log1p(span * (q - 1.0) / first_cell) / math.log(q)
    return max(2, min(MAX_NODES, int(math.ceil(n)) + 1))


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
    #: The resolved aerofoil, or ``None`` when one of the refusals above fired.
    #: Held whole rather than copied field by field, so "what did we read off the
    #: section" has one owner and the read-out cannot describe a different one.
    section: object = None
    up_nodes: int = 0
    lo_nodes: int = 0
    wake_span: float = 0.0
    radial_span: float = 0.0
    first_cell: float = 0.0
    te_cell: float = 0.0
    wake_derived: int = 0
    wake_nodes: int = 0
    wake_overridden: bool = False
    radial_derived: int = 0
    radial_nodes: int = 0
    radial_overridden: bool = False
    #: True when a derivation hit :data:`MAX_NODES`. A silent clamp on a DISPLAYED
    #: derived count is a number the panel presents as the derivation's answer and is
    #: not; the O-grid's review named it, and this read-out says so too.
    clamped: bool = False
    #: The six generated far-field corners, ``{id: (x, y)}``.
    far: dict = None

    def lines(self) -> list:
        """The derivation, as the read-out shows it — RESULT AND WORKING, not result.

        #137's central claim, inherited: displaying the derivation is the single most
        useful thing the panel does, so each line carries the quantity it was computed
        from rather than only its answer.
        """
        if self.problem:
            return [f"—  {self.problem}"]
        return [
            f"section: chord {self.section.chord:.4g}, trailing edge at "
            f"({self.section.te_xy[0]:.4g}, {self.section.te_xy[1]:.4g}), upper "
            f"surface {self.section.up_len:.4g} long and lower "
            f"{self.section.lo_len:.4g}",
            f"surfaces: {self.up_nodes} / {self.lo_nodes} nodes at a "
            f"{self.te_cell:.3e} trailing-edge cell and a target cell edge",
            f"wake: {self.wake_nodes} nodes"
            + (" (overridden)" if self.wake_overridden
               else f" (derived: {self.te_cell:.3e} growing at {GROWTH:g} spans "
                    f"{self.wake_span:.4g})"),
            f"radial: {self.radial_nodes} nodes"
            + (" (overridden)" if self.radial_overridden
               else f" (derived: BL_INITIAL_THICKNESS {self.first_cell:.3e} growing "
                    f"at {GROWTH:g} spans {self.radial_span:.4g})")
            + (f" — CLAMPED at {MAX_NODES}, so the first cell you asked for is not "
               f"reachable at this growth" if self.clamped else ""),
            "far field: GENERATED from the two lengths, so its six sides carry the "
            "run's BC_GEOM; the section's two carry the conditions on its own CAD "
            "segments",
        ]


def plan(model, ctx) -> Plan:
    """Everything the C-grid derives from ``model`` against ``ctx``.

    Returns a :class:`Plan` whose ``problem`` is set rather than raising, because the
    panel asks this on every keystroke and a half-typed geometry name is not an error
    yet. :func:`build` asks the same question and turns a problem into the refusal.
    """
    p = Plan()
    p.far = {}
    if ctx is None:
        p.problem = ("this family binds to the section you drew, so it needs the "
                     "mesh's geometry list; none was supplied.")
        return p
    g, p.section, p.problem, p.broken_edge = resolve_section(
        ctx, model.cgrid_body_geom, model.cgrid_body_segs)
    if g is None:
        return p

    cell = float(model.cgrid_cell)
    p.te_cell = float(model.cgrid_te_cell)
    p.wake_span = float(model.cgrid_wake_length)
    p.radial_span = float(model.cgrid_far_radius)
    for what, value in (("target cell edge", cell),
                        ("trailing-edge cell length", p.te_cell),
                        ("wake length", p.wake_span),
                        ("far-field radius", p.radial_span)):
        if value <= 0.0:
            p.problem = f"the {what} must be greater than zero."
            return p

    p.far = far_corners(p.section.te_xy, p.section.le_xy[0], p.wake_span,
                        p.radial_span)
    out = outside_point(p.far, g)
    if out is not None:
        p.problem = (f"the section reaches ({out[0]:.4g}, {out[1]:.4g}), which is "
                     f"outside the far field a wake length of {p.wake_span:.4g} and "
                     f"a radius of {p.radial_span:.4g} generate. Raise the far-field "
                     f"radius.")
        return p

    p.up_nodes = wall_count(p.section.up_len, cell)
    p.lo_nodes = wall_count(p.section.lo_len, cell)
    p.first_cell = ctx.first_cell if ctx.first_cell > 0.0 else p.te_cell
    p.wake_derived = nodes_for_growth(p.wake_span, p.te_cell)
    p.radial_derived = nodes_for_growth(p.radial_span, p.first_cell)
    p.clamped = (p.wake_derived >= MAX_NODES or p.radial_derived >= MAX_NODES)
    want = int(model.cgrid_wake_count)
    p.wake_overridden = want >= 2
    p.wake_nodes = want if p.wake_overridden else p.wake_derived
    want = int(model.cgrid_radial_count)
    p.radial_overridden = want >= 2
    p.radial_nodes = want if p.radial_overridden else p.radial_derived
    return p


def build(model, ctx=None) -> dict:
    """The C-grid topology document for ``model``, bound to ``ctx``'s section.

    THE FRAME, per block: i runs OUTWARD from the body to the far field (its south
    and north are the two radials) and j runs from the body side to the far-field
    side (its west is the body side, its east the far-field side). The four blocks
    are declared walking the section anticlockwise — wake block above, upper surface,
    lower surface, wake block below — which is what makes every corner ring wind
    counter-clockwise, on a section drawn either way round.
    """
    p = plan(model, ctx)
    if p.problem:
        raise BindingError(
            f"the C-grid template cannot build a document: {p.problem}",
            edge=p.broken_edge)
    g = ctx.geometry(model.cgrid_body_geom)
    ds = p.te_cell

    corners = [
        # A corner is the t = 0 of the segment that STARTS there, so both edges
        # meeting on it may name it — the rule the shipped hand-written document
        # states and the mesher's own joint resolution implements.
        {"id": "te", "kind": "on_geometry", "geom": g.spelling,
         "seg": p.section.te_seg, "t": 0.0},
        {"id": "le", "kind": "on_geometry", "geom": g.spelling,
         "seg": p.section.le_seg, "t": 0.0},
    ] + [{"id": k, "kind": "free", "xy": [xy[0], xy[1]]}
         for k, xy in p.far.items()]

    # The surface edges are declared in their OWN segment's direction: the one
    # leaving the trailing edge runs te -> le, the other le -> te. Which of the two
    # is the upper surface is `plan`'s measurement, and it is the only thing a
    # section drawn clockwise changes.
    up_first = p.section.up_first
    edges = [
        # ONE edge, and the WEST of both wake blocks: that is the C's cut. It carries
        # no binding (an interior line has no boundary condition to read, and the
        # wake is straight anyway) and no face of it is exported. Its clustering at
        # the trailing-edge end matches the surfaces', because the wake shear layer
        # is the continuation of the boundary layer that fed it.
        {"id": "wake", "corners": ["te", "wk"], "kind": "cut",
         "count": p.wake_nodes, "spacing": {"ds_start": ds}},
        # The radials: ONE equivalence class of five, so only the first declares a
        # count and the other four arrive by propagation. Every one of them marks its
        # BODY end a wall end — including the two on the outlet plane, whose body end
        # is the wake cut rather than a surface.
        {"id": "r_te_up", "corners": ["te", "f1"], "kind": "interface",
         "count": p.radial_nodes, "spacing": {"wall_ends": "start"}},
        {"id": "r_le", "corners": ["le", "f2"], "kind": "interface",
         "spacing": {"wall_ends": "start"}},
        {"id": "r_te_lo", "corners": ["te", "f3"], "kind": "interface",
         "spacing": {"wall_ends": "start"}},
        {"id": "af_up", "corners": ["te", "le"] if up_first else ["le", "te"],
         "kind": "wall", "count": p.up_nodes,
         "binding": {"geom": g.spelling,
                     "seg": ctx.resolve("af_up", g.spelling, p.section.up_seg)},
         "spacing": {"ds_start": ds, "ds_end": ds}},
        {"id": "af_lo", "corners": ["le", "te"] if up_first else ["te", "le"],
         "kind": "wall", "count": p.lo_nodes,
         "binding": {"geom": g.spelling,
                     "seg": ctx.resolve("af_lo", g.spelling, p.section.lo_seg)},
         "spacing": {"ds_start": ds, "ds_end": ds}},
        {"id": "e_out_up", "corners": ["wk", "fu"], "kind": "wall",
         "spacing": {"wall_ends": "start"}},
        {"id": "e_ff_up", "corners": ["fu", "f1"], "kind": "wall",
         "spacing": {"ds_end": ds}},
        # THE TWO NOSE SIDES CLUSTER AT THEIR TRAILING-EDGE END, to the section's own
        # surface spacing and not to a tuned number. Over the chordwise surface the
        # body's normals are nearly vertical while this boundary runs away from the
        # nose, so the outer point opposite a body point has to track the body's own
        # distribution or the grid line leaving the wall is not normal to it. Left
        # uniform, the shipped hand-written case meshed with zero inverted cells and
        # then drove the solver to NaN in 40 iterations; the same declaration is what
        # this family inherits. Clustering the OTHER end as well was measured and is
        # worse (test_topology_cgrid.py's own note): 82 degrees of peak
        # non-orthogonality against 49.
        {"id": "e_ff_nose_up", "corners": ["f1", "f2"], "kind": "wall",
         "spacing": {"ds_start": ds}},
        {"id": "e_ff_nose_lo", "corners": ["f2", "f3"], "kind": "wall",
         "spacing": {"ds_end": ds}},
        {"id": "e_ff_lo", "corners": ["f3", "fl"], "kind": "wall",
         "spacing": {"ds_start": ds}},
        {"id": "e_out_lo", "corners": ["wk", "fl"], "kind": "wall",
         "spacing": {"wall_ends": "start"}},
    ]
    # [south, east, north, west] = [radial in, far-field side, radial out, body
    # side]. The wake cut is the WEST of both wake blocks.
    blocks = [
        {"id": "b_wake_up", "edges": ["e_out_up", "e_ff_up", "r_te_up", "wake"]},
        {"id": "b_upper", "edges": ["r_te_up", "e_ff_nose_up", "r_le", "af_up"]},
        {"id": "b_lower", "edges": ["r_le", "e_ff_nose_lo", "r_te_lo", "af_lo"]},
        {"id": "b_wake_lo", "edges": ["r_te_lo", "e_ff_lo", "e_out_lo", "wake"]},
    ]
    return {"format_version": 1, "corners": corners, "edges": edges,
            "blocks": blocks}


def broken_bindings(model, ctx) -> tuple:
    """Every stored id this family holds that its section no longer carries (#138).

    THE COMPLEMENT OF `plan`'s REFUSAL, NOT A SECOND COPY OF IT — the O-grid's rule,
    and the panel asks the registry rather than asking a family by name.

    BOTH surface edges are named for one broken position, and that is not
    over-reporting: which bound segment is the upper surface is measured from the two
    spans, so with one of them missing the family cannot say which of `af_up` and
    `af_lo` the broken id would have become. Repairing the position repairs both.
    """
    if ctx is None:
        return ()
    g = ctx.geometry(getattr(model, "cgrid_body_geom", ""))
    if g is None or not g.seg_ids:
        return ()
    held, why = parse_binding(getattr(model, "cgrid_body_segs", ""), (), "aerofoil")
    if why or not held:
        # A blank list adopts the section's own segments and so cannot be broken; a
        # malformed one is refused as a whole string and is not a position a dropdown
        # could re-point.
        return ()
    return tuple(BrokenBinding(field="cgrid_body_segs", who="aerofoil",
                               geom=g.spelling, seg=s, pos=pos,
                               edges=("af_up", "af_lo"),
                               choices=tuple(g.seg_ids))
                 for pos, s in enumerate(held) if s not in g.spans)
