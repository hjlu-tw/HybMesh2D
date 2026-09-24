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
from app.services.topology_ogrid_binding import parse_binding

#: How many surface segments a section the C-grid can wrap is split into: the upper
#: and the lower, meeting at the trailing edge. THREE is the blunt section, whose
#: base is a segment of its own and whose two surfaces never meet.
SHARP_SEGMENTS = 2
BLUNT_SEGMENTS = 3


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

    held, why = parse_binding(segs_text, g.seg_ids, "aerofoil")
    if why:
        return None, None, why, ""
    # The edge a resolve refusal names is the one the stored POSITION would become on
    # a section drawn the way the CAD stage draws one (upper surface first). Which
    # bound segment IS the upper is decided below, from coordinates — and that
    # decision needs both spans, which is exactly what a broken binding does not
    # have. `topology_cgrid.broken_bindings` reports both surface edges for the same
    # reason.
    for pos, sid in enumerate(held):
        try:
            ctx.resolve("af_up" if pos == 0 else "af_lo", g.spelling, sid)
        except BindingError as exc:
            return None, None, str(exc), exc.edge
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


def outside_point(far: dict, g):
    """The first point of ``g`` the far field ``far`` does not contain, or ``None``.

    THE SECTION HAS TO BE INSIDE ITS FAR FIELD, and it is checked by walking the
    section's own points rather than by a rule of thumb about chords: a radius that is
    generous for a thin aerofoil at zero incidence is not for a thick one at 15
    degrees, and a section poking through its own far field produces blocks that fold
    rather than a refusal the user can read.

    ``wk`` is left out of the ring because it lies ON the outlet plane between ``fu``
    and ``fl``; the five remaining corners bound exactly the same region.
    """
    ring = [far[k] for k in ("fu", "f1", "f2", "f3", "fl")]
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
