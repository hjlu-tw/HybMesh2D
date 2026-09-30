"""The C-grid family: a wake CUT and a four-way trailing-edge corner (issue #148).

A PURE FUNCTION of ``(model, context)``, like the H-grid and the O-grid beside it — no
Qt, no mesher, no canvas, no filesystem. What it adds to the O-grid is not a mechanism
(it reuses the registry, the stable-id bindings, the projection funnel and the canvas
skeleton unchanged) but the two STRUCTURES that made
``examples/topology/cgrid_naca0012.json`` the hardest of the shipped documents to
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
import os
from dataclasses import dataclass, field

from app.services.topology_binding import BindingError
from app.services.topology_cgrid_section import (
    FAR_CORNERS, FAR_EDGES, FAR_ROLE, SECTION_ROLE, SURFACE_EDGES, Section,
    drawn_ring, far_corners, far_edge_at, generated_ring, outside_point,
    resolve_far, resolve_section,
)
from app.services.topology_counts import MAX_COUNT, nodes_for_growth, wall_count
from app.services.topology_ogrid_binding import broken_in_lists

#: The template's own name for the family, as stored in the project file.
FAMILY = "cgrid"

#: The field-spec rows the BOUND far field makes inert — the two physical lengths
#: the GENERATED one is placed from. Spelled once, here, because the read-out names
#: them in prose and the panel greys them out, and two spellings of "which controls
#: stopped deciding" is how one of them comes to name a row the other does not.
INERT_WHEN_BOUND = ("topo_cgrid_wake_length", "topo_cgrid_far_radius")

#: The cell-to-cell expansion the wake and radial derivations grow at. NOT a tuned
#: constant: it is the red line of this repo's own quality ruler
#: (``tools/scripts/visualize_dat.py --quality``: green < 1.05, orange 1.05-1.2, red
#: > 1.2), so a count derived from it is "the fewest nodes that never exceed the
#: expansion this project already calls bad". The shipped hand-written document's
#: own radial count, 41, comes out of it at 43 — which is the closest thing to a
#: check on the number that exists.
GROWTH = 1.2

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
    section: Section | None = None
    up_nodes: int = 0
    lo_nodes: int = 0
    wake_span: float = 0.0
    radial_span: float = 0.0
    first_cell: float = 0.0
    #: True when ``first_cell`` came from the RUN's ``BL_INITIAL_THICKNESS``. The
    #: read-out asks, because on the fallback path below it would otherwise print
    #: the trailing-edge cell under another parameter's name — which is the
    #: derivation-with-its-working rule broken in the one line that states it.
    first_cell_from_run: bool = False
    te_cell: float = 0.0
    wake_derived: int = 0
    wake_nodes: int = 0
    wake_overridden: bool = False
    radial_derived: int = 0
    radial_nodes: int = 0
    radial_overridden: bool = False
    #: True when a derivation hit :data:`~app.services.topology_counts.MAX_COUNT`.
    #: A silent clamp on a DISPLAYED
    #: derived count is a number the panel presents as the derivation's answer and is
    #: not; the O-grid's review named it, and this read-out says so too.
    clamped: bool = False
    #: The six far-field corners, ``{id: (x, y)}`` — GENERATED from the two
    #: lengths or read off the drawn geometry, whichever path this plan is on.
    #: Empty until the parameters are good enough to place them, never ``None``,
    #: so a caller that asks a refused plan for them gets nothing rather than an
    #: AttributeError.
    far: dict = field(default_factory=dict)
    #: True when the far field is DRAWN and bound rather than generated (#149).
    #: The two paths differ in ONE thing the user can see — a bound side carries
    #: the condition on its own CAD segment, a generated one carries the run's
    #: ``BC_GEOM`` — so the read-out says which of the two it is describing.
    far_bound: bool = False
    #: The far field's spelling and its six bound segment ids, in ring order.
    #: Empty on the generated path.
    far_geom: str = ""
    far_segs: tuple = ()
    #: Field-spec rows this plan's own configuration has made INERT (#149). On the
    #: BOUND path the two lengths decide nothing, and the panel greys them out:
    #: saying so in the read-out is necessary and was measured not to be
    #: sufficient — a live-looking spin box that changes no mesh is the
    #: control-that-does-nothing `tests/test_topology_param_specs.py` exists for,
    #: reached by another route. The names are FIELD-SPEC ROW attributes rather
    #: than model fields, because it is the widget that has to go grey, and they
    #: are declared HERE rather than in the panel so a third family needs no view
    #: edit. Held against the table by `tests/test_topology_param_specs.py`.
    inert_rows: tuple = ()

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
               else (f" (derived: "
                     f"{'BL_INITIAL_THICKNESS' if self.first_cell_from_run else 'the trailing-edge cell'}"
                     f" {self.first_cell:.3e} growing at {GROWTH:g} spans "
                     f"{self.radial_span:.4g}"
                     + ("" if self.first_cell_from_run
                        else " — this run declares no BL_INITIAL_THICKNESS") + ")"))
            + (f" — CLAMPED at {MAX_COUNT}, so the first cell you asked for is not "
               f"reachable at this growth" if self.clamped else ""),
            (f"far field: BOUND to "
             f"'{os.path.basename(self.far_geom) or self.far_geom}' over its "
             f"{len(self.far_segs)} "
             f"segments ({', '.join(str(s) for s in self.far_segs)}), so each of "
             f"its sides carries that geometry's own condition — the outlet halves "
             f"an outlet, the D a far field. The wake length and far-field radius "
             f"above are INERT on this path: the wake spans "
             f"{self.wake_span:.4g} and the radial {self.radial_span:.4g} because "
             f"that is where you drew them — so 'Wake Length' and 'Far-Field "
             f"Radius' above are greyed out"
             if self.far_bound else
             "far field: GENERATED from the two lengths, so its six sides carry the "
             "run's BC_GEOM; the section's two carry the conditions on its own CAD "
             "segments"),
        ]


def plan(model, ctx) -> Plan:
    """Everything the C-grid derives from ``model`` against ``ctx``.

    Returns a :class:`Plan` whose ``problem`` is set rather than raising, because the
    panel asks this on every keystroke and a half-typed geometry name is not an error
    yet. :func:`build` asks the same question and turns a problem into the refusal.
    """
    p = Plan()
    if ctx is None:
        p.problem = ("this family binds to the section you drew, so it needs the "
                     "mesh's geometry list; none was supplied.")
        return p
    g, p.section, p.problem, p.broken_edge = resolve_section(
        ctx, model.cgrid_body_geom, model.cgrid_body_segs)
    if g is None:
        return p

    fg, p.far_segs, p.problem, p.broken_edge = resolve_far(
        ctx, model.cgrid_far_geom, model.cgrid_far_segs)
    if p.problem:
        return p
    p.far_bound = fg is not None
    if p.far_bound:
        p.far_geom = fg.spelling
        p.inert_rows = INERT_WHEN_BOUND

    cell = float(model.cgrid_cell)
    p.te_cell = float(model.cgrid_te_cell)
    checks = [("target cell edge", cell), ("trailing-edge cell length", p.te_cell)]
    if not p.far_bound:
        # THE TWO LENGTHS ARE ONLY A QUESTION ON THE GENERATED PATH. Once a far
        # field is drawn they decide nothing, so refusing a zero in one of them
        # would be a refusal the user cannot act on and cannot see the point of —
        # the read-out's last line says they are inert instead.
        checks += [("wake length", float(model.cgrid_wake_length)),
                   ("far-field radius", float(model.cgrid_far_radius))]
    for what, value in checks:
        if value <= 0.0:
            p.problem = f"the {what} must be greater than zero."
            return p

    if p.far_bound:
        p.far = {cid: fg.spans[sid].point_at(0.0)
                 for cid, sid in zip(FAR_CORNERS, p.far_segs)}
        ring = drawn_ring(fg)
        where = f"the far field you drew as '{p.far_geom}'"
    else:
        p.far = far_corners(p.section.te_xy, p.section.le_xy[0],
                            float(model.cgrid_wake_length),
                            float(model.cgrid_far_radius))
        ring = generated_ring(p.far)
        where = (f"the far field a wake length of "
                 f"{float(model.cgrid_wake_length):.4g} and a radius of "
                 f"{float(model.cgrid_far_radius):.4g} generate")
    out = outside_point(ring, g)
    if out is not None:
        p.problem = (f"the section reaches ({out[0]:.4g}, {out[1]:.4g}), which is "
                     f"outside {where}. "
                     + ("Draw the far field larger, or clear its row to generate "
                        "one from the two lengths above." if p.far_bound
                        else "Raise the far-field radius."))
        return p

    # THE TWO SPANS ARE MEASURED OFF THE PLACED CORNERS, on BOTH paths, so the wake
    # and radial derivations read the distance the grid actually has to cross rather
    # than a parameter that may no longer decide it. On the generated path the two
    # are the parameters by construction — `far_corners` puts `wk` a wake length
    # downstream of the trailing edge and `f1` a radius above it — which is what
    # makes this one owner rather than a second derivation.
    te = p.section.te_xy
    p.wake_span = math.dist(te, p.far["wk"])
    p.radial_span = math.dist(te, p.far["f1"])

    p.up_nodes = wall_count(p.section.up_len, cell)
    p.lo_nodes = wall_count(p.section.lo_len, cell)
    # THE RUN'S OWN NUMBER, under the name it already has (#133) — and the fallback
    # is RECORDED rather than silent, because the read-out names the source.
    p.first_cell_from_run = ctx.first_cell > 0.0
    p.first_cell = ctx.first_cell if p.first_cell_from_run else p.te_cell
    p.wake_derived = nodes_for_growth(p.wake_span, p.te_cell, GROWTH)
    p.radial_derived = nodes_for_growth(p.radial_span, p.first_cell, GROWTH)
    p.clamped = (p.wake_derived >= MAX_COUNT or p.radial_derived >= MAX_COUNT)
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
    # ONE lookup for the two places the far field is written — the corners and the
    # six bindings — so they cannot end up describing different geometries.
    fg = ctx.geometry(model.cgrid_far_geom) if p.far_bound else None
    ds = p.te_cell

    corners = [
        # A corner is the t = 0 of the segment that STARTS there, so both edges
        # meeting on it may name it — the rule the shipped hand-written document
        # states and the mesher's own joint resolution implements.
        {"id": "te", "kind": "on_geometry", "geom": g.spelling,
         "seg": p.section.te_seg, "t": 0.0},
        {"id": "le", "kind": "on_geometry", "geom": g.spelling,
         "seg": p.section.le_seg, "t": 0.0},
    ]
    # THE FAR FIELD IS EITHER DRAWN OR GENERATED, and that is the ONE branch #149
    # adds: a bound corner is the t = 0 of its own source segment (so the side
    # leaving it carries that segment's condition) where a generated one is a free
    # coordinate belonging to no geometry (so every side carries the run's
    # BC_GEOM). Nothing else about the document changes — same six ids, same six
    # edges, same four blocks, same spacing.
    if p.far_bound:
        corners += [{"id": cid, "kind": "on_geometry", "geom": fg.spelling,
                     "seg": ctx.resolve(far_edge_at(k), fg.spelling, sid),
                     "t": 0.0}
                    for k, (cid, sid) in enumerate(zip(FAR_CORNERS, p.far_segs))]
    else:
        corners += [{"id": k, "kind": "free", "xy": [xy[0], xy[1]]}
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
        {"id": SURFACE_EDGES[0],
         "corners": ["te", "le"] if up_first else ["le", "te"],
         "kind": "wall", "count": p.up_nodes,
         "binding": {"geom": g.spelling,
                     "seg": ctx.resolve(SURFACE_EDGES[0], g.spelling,
                                        p.section.up_seg)},
         "spacing": {"ds_start": ds, "ds_end": ds}},
        {"id": SURFACE_EDGES[1],
         "corners": ["le", "te"] if up_first else ["te", "le"],
         "kind": "wall", "count": p.lo_nodes,
         "binding": {"geom": g.spelling,
                     "seg": ctx.resolve(SURFACE_EDGES[1], g.spelling,
                                        p.section.lo_seg)},
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
    if p.far_bound:
        # ONE side per source segment, in the order `FAR_EDGES` declares — which is
        # the order `resolve_far` has already proved the drawn outline runs them in,
        # so this is a write of what was measured rather than a second reading of it.
        _seg = dict(zip(FAR_EDGES, p.far_segs))
        for e in edges:
            if e["id"] in _seg:
                e["binding"] = {"geom": fg.spelling,
                                "seg": ctx.resolve(e["id"], fg.spelling,
                                                   _seg[e["id"]])}

    # [south, east, north, west] = [radial in, far-field side, radial out, body
    # side]. The wake cut is the WEST of both wake blocks.
    blocks = [
        {"id": "b_wake_up", "edges": ["e_out_up", "e_ff_up", "r_te_up", "wake"]},
        {"id": "b_upper",
         "edges": ["r_te_up", "e_ff_nose_up", "r_le", SURFACE_EDGES[0]]},
        {"id": "b_lower",
         "edges": ["r_le", "e_ff_nose_lo", "r_te_lo", SURFACE_EDGES[1]]},
        {"id": "b_wake_lo", "edges": ["r_te_lo", "e_ff_lo", "e_out_lo", "wake"]},
    ]
    return {"format_version": 1, "corners": corners, "edges": edges,
            "blocks": blocks}


def _section_edges(_pos: int) -> tuple:
    """BOTH surface edges, whichever position broke — and that is not over-reporting.

    Which bound segment is the upper surface is measured from the two spans, so with
    one of them missing the family cannot say which of ``af_up`` and ``af_lo`` the
    broken id would have become. Repairing the position repairs both. Named rather
    than written inline as a lambda that ignores its argument, so the table below
    reads as two answers to one question.
    """
    return SURFACE_EDGES


def _far_edges(pos: int) -> tuple:
    """The ONE side that lies on the far-field segment bound at ``pos``.

    On the far field the position IS the side, where on the section it is not.
    """
    return (far_edge_at(pos),)


#: Which stored list is which, as ``(model field, geometry field, role, position ->
#: the edges that position darkens)``. `topology_ogrid_binding.BINDING_LISTS`'s own
#: shape, carrying an edge answer instead of an edge PREFIX because this family's
#: two lists number their edges differently — and declared here rather than written
#: inline at the one loop that walks it, so a reader asking "which lists does the
#: C-grid bind?" has one place to look, as they do next door.
BINDING_LISTS = (
    ("cgrid_body_segs", "cgrid_body_geom", SECTION_ROLE, _section_edges),
    ("cgrid_far_segs", "cgrid_far_geom", FAR_ROLE, _far_edges),
)


def broken_bindings(model, ctx) -> tuple:
    """This family's two lists, walked by ``broken_in_lists`` (#155).

    THE COMPLEMENT OF `plan`'s REFUSAL, NOT A SECOND COPY OF IT — the O-grid's rule,
    and the panel asks the registry rather than asking a family by name. What stays
    here is which two lists this family binds and how each one names its edges
    (:data:`BINDING_LISTS`); the walk is shared, because a third family arrived
    needing exactly it.

    A blank far-field row is the GENERATED path, which binds nothing and so can break
    nothing — the same sentence `parse_binding` already writes for a blank list,
    reached one step earlier.
    """
    return broken_in_lists(model, ctx, BINDING_LISTS)
