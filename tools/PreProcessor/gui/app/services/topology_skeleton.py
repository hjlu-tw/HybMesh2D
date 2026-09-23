"""The block skeleton a topology document describes, resolved for DRAWING (issue #136).

Qt-free, and gated as such by ``tests/test_qt_free_seam.py``'s ``services/`` sweep: the
canvas overlay is one caller of this module, not its home, so "what does the skeleton
look like" is answerable from a headless process and the drawing code is left with
nothing to decide.

THE NODE COUNT IS THE POINT, NOT THE OUTLINE. A count in the document is a SEED, not a
per-edge setting: opposite sides of a block carry equal counts and a shared edge is ONE
edge two blocks name, so one declaration fixes a whole chain of edges the user never
touched. An outline alone would show the shape and hide the thing that is actually hard
to predict, which is why :func:`resolve_counts` below mirrors the mesher's own
propagation rather than reading `count` off each edge.

IT MIRRORS `resolveEdgeCounts` (`src/MultiBlock.cpp`) AND THAT IS A SECOND HOME FOR ONE
RULE — said out loud rather than left to be discovered. The alternative was asking the
mesher, which means writing a document to disk, launching a process and parsing its
report for every keystroke in a parameter box; a live overlay cannot pay that. What
keeps the two from drifting is not discipline but a gate: `tests/test_topology_skeleton.py`
check 2 reads the pairing out of `src/MultiBlock.cpp` itself and FAILS rather than
answering when it cannot find it, and check 12 runs the REAL mesher on a shipped topology
and compares its per-edge report against what this module resolved. A divergence is a red
gate, not a wrong number on a canvas.

WHAT IT REFUSES TO DO is guess. A class with no seed, or one with two seeds that
disagree, is a document the mesher REFUSES — so those edges resolve to ``None`` here and
the overlay says so, rather than picking one of the two counts and drawing a mesh the run
will never produce. The same rule covers a corner this module cannot place: a bound
corner with no locator has ``xy = None`` and is reported as bound-but-unplaced, never at
(0, 0).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services import topology_model
from app.services.mesh_modes import MESH_MODE_MULTIBLOCK

#: The corner kind that attaches to a geometry by normalized arc length. The other
#: kind, ``free``, carries its own ``xy``. Spelled once here because two questions
#: below ask it — how to place the corner, and how to DRAW it.
KIND_ON_GEOMETRY = "on_geometry"

#: The edge kind that bounds exactly one block. The other two (``interface`` and
#: ``cut``) bound two and are interior lines. Spelled here rather than at the canvas
#: because which edges are a BOUNDARY is a fact about the topology, and the overlay
#: decides nothing about the topology.
KIND_WALL = "wall"


@dataclass(frozen=True)
class SkeletonCorner:
    """One declared corner: where it is, and whether it is attached to geometry."""

    id: str
    bound: bool
    #: ``None`` when the corner is attached to a geometry and nothing placed it.
    xy: tuple[float, float] | None


@dataclass(frozen=True)
class SkeletonEdge:
    """One declared edge, with the node count PROPAGATION gave it."""

    id: str
    kind: str
    corners: tuple[str, str]
    #: Both endpoints, or ``None`` when either corner could not be placed.
    xy: tuple[tuple[float, float], tuple[float, float]] | None
    #: The resolved node count, or ``None`` when its class has no seed or two.
    count: int | None
    #: True when THIS edge is where the count was declared; False when it arrived
    #: by propagation. The mesher reports the same two states per edge.
    declared: bool

    @property
    def is_boundary(self) -> bool:
        """True for an edge that bounds exactly one block — a ``wall``."""
        return self.kind == KIND_WALL

    @property
    def label(self) -> str:
        """What to write beside the edge.

        ``"?"`` rather than a blank for an unresolved count: this is exactly the
        state the mesher refuses the run over, so the overlay showing nothing there
        would hide the one thing the user needs to see. One owner for the text, so
        the canvas formats nothing.
        """
        return "?" if self.count is None else str(self.count)

    @property
    def midpoint(self) -> tuple[float, float] | None:
        """Where the label goes — the chord midpoint, or ``None`` if unplaced."""
        if self.xy is None:
            return None
        (x0, y0), (x1, y1) = self.xy
        return (0.5 * (x0 + x1), 0.5 * (y0 + y1))


@dataclass(frozen=True)
class Skeleton:
    """Everything the overlay draws, and nothing about how it is drawn."""

    corners: tuple[SkeletonCorner, ...]
    edges: tuple[SkeletonEdge, ...]

    def bounds(self) -> tuple[float, float, float, float] | None:
        """``(xmin, xmax, ymin, ymax)`` over every PLACED corner, or ``None``.

        The view needs this because a template case may legally have no geometry at
        all — an empty ``cads`` is legal in ``MESH_MODE 1`` — and a canvas that fits
        only to geometry previews would then fit to nothing and show the user an
        empty frame with their skeleton somewhere off screen.
        """
        pts = [c.xy for c in self.corners if c.xy is not None]
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), max(xs), min(ys), max(ys))


def resolve_counts(doc: dict) -> dict[str, tuple[int | None, bool]]:
    """``{edge id: (resolved count or None, was it declared here)}`` for ``doc``.

    THE MESHER'S OWN RULE, restated (`src/MultiBlock.cpp::resolveEdgeCounts`): two
    edges are forced to carry the same node count when they are OPPOSITE SIDES of one
    block — a structured block is ni x nj nodes — and because a shared edge is one
    declared edge that two blocks both name, that single relation propagates ACROSS
    blocks by itself. There is no second rule for an interface. A block declares its
    edges ``[south, east, north, west]``, so the pairs are (0, 2) and (1, 3).

    A class with exactly one distinct seed resolves to it. A class with NO seed, or
    with two seeds that disagree, resolves to ``None`` for every edge in it: both are
    documents the mesher refuses by name, and answering with one of the two counts
    would draw a mesh no run will produce.

    Tolerant of a malformed document, because it is fed by a panel the user is still
    typing into: an unknown edge id or a block that does not name four edges
    contributes no relation instead of raising.
    """
    edges = [e for e in (doc.get("edges") or []) if isinstance(e, dict)]
    ids = [str(e.get("id", "")) for e in edges]
    index = {eid: k for k, eid in enumerate(ids)}

    parent = list(range(len(edges)))

    def root(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for blk in (doc.get("blocks") or []):
        if not isinstance(blk, dict):
            continue
        sides = blk.get("edges") or []
        if len(sides) != 4:
            continue
        for a, b in ((0, 2), (1, 3)):
            ia, ib = index.get(str(sides[a])), index.get(str(sides[b]))
            if ia is None or ib is None:
                continue
            parent[root(ia)] = root(ib)

    #: The declarations, kept apart from the resolved counts so each edge can report
    #: which of the two it got — the same split the mesher's report carries. A `count`
    #: that is PRESENT but not an integer >= 2 is recorded as an INVALID seed, not as
    #: an absent one: the mesher refuses such a document by name (`src/MultiBlock.cpp`,
    #: "count >= 2"), so treating it as "no declaration here" would let a sibling seed
    #: label a number for a run that never happens. Narrower than the mesher, which
    #: refuses the whole document — here it is the CLASS that goes unresolved, so the
    #: `?` lands on the edges the user has to go and fix.
    seeded: list[int | None] = []
    invalid: list[bool] = []
    for e in edges:
        v = e.get("count")
        ok = isinstance(v, int) and not isinstance(v, bool) and v >= 2
        seeded.append(int(v) if ok else None)
        invalid.append(v is not None and not ok)

    classes: dict[int, list[int]] = {}
    for k in range(len(edges)):
        classes.setdefault(root(k), []).append(k)

    out: dict[str, tuple[int | None, bool]] = {}
    for members in classes.values():
        found = {seeded[k] for k in members if seeded[k] is not None}
        resolved = (None if any(invalid[k] for k in members)
                    else (found.pop() if len(found) == 1 else None))
        for k in members:
            out[ids[k]] = (resolved, seeded[k] is not None)
    return out


def skeleton(doc: dict, locate=None) -> Skeleton:
    """The drawable skeleton of ``doc``.

    ``locate`` places a corner of kind ``on_geometry``: it is called with that
    corner's own dict and returns ``(x, y)`` or ``None``. Optional, and ``None`` in
    every shipped path today — no family generates a bound corner until the O-grid
    (#137) — so a bound corner is reported as bound-but-unplaced rather than placed
    somewhere convenient. The parameter exists so that arrives as a caller passing a
    resolver, not as a second walk over the document.
    """
    corners: list[SkeletonCorner] = []
    at: dict[str, tuple[float, float]] = {}
    for c in (doc.get("corners") or []):
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id", ""))
        bound = str(c.get("kind", "")) == KIND_ON_GEOMETRY
        xy = None
        if bound:
            if locate is not None:
                xy = locate(c)
        else:
            raw = c.get("xy")
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                try:
                    xy = (float(raw[0]), float(raw[1]))
                except (TypeError, ValueError):
                    xy = None
        if xy is not None:
            xy = (float(xy[0]), float(xy[1]))
            at[cid] = xy
        corners.append(SkeletonCorner(id=cid, bound=bound, xy=xy))

    counts = resolve_counts(doc)
    edges: list[SkeletonEdge] = []
    for e in (doc.get("edges") or []):
        if not isinstance(e, dict):
            continue
        eid = str(e.get("id", ""))
        ends = e.get("corners") or []
        pair = (str(ends[0]), str(ends[1])) if len(ends) == 2 else ("", "")
        xy = None
        if pair[0] in at and pair[1] in at:
            xy = (at[pair[0]], at[pair[1]])
        count, declared = counts.get(eid, (None, False))
        edges.append(SkeletonEdge(id=eid, kind=str(e.get("kind", "")),
                                  corners=pair, xy=xy, count=count,
                                  declared=declared))
    return Skeleton(corners=tuple(corners), edges=tuple(edges))


def skeleton_for_config(cfg) -> Skeleton | None:
    """The skeleton ``cfg``'s TEMPLATE describes, or ``None`` when there is none.

    THE ONE OWNER of "is there a skeleton to draw", so the canvas holds no predicate
    of its own and cannot come to a different answer than the panel does about what a
    template case is. Both halves are asked here for the reason
    ``mesh_modes.topology_file`` asks both of its own: a family named while the mode
    is hybrid drives nothing — the panel hides the whole section — and an overlay
    drawn for a mesh the run will not produce is worse than no overlay.

    ``None`` is also what a case with no topology model gets, which is what makes the
    overlay clear on the way INTO such a case rather than surviving from the last one.

    Duck-typed like the rest of this package: the caller has a ``MeshConfig``, but
    this module is Qt-free and about a CONFIG, not about the class.
    """
    if cfg is None:
        return None
    if int(getattr(cfg, "mesh_mode", 0) or 0) != MESH_MODE_MULTIBLOCK:
        return None
    model = getattr(cfg, "topology", None)
    if model is None or not model.names_a_family():
        return None
    return skeleton(topology_model.build_document(model))
