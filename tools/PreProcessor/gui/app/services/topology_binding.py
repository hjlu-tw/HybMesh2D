"""What a template's bindings RESOLVE AGAINST, and the refusal when one cannot (#137).

Qt-free, and gated as such by ``tests/test_qt_free_seam.py``'s ``services/`` sweep: a
family function is pure, so everything it needs to know about the user's CAD — which
segments a geometry has right now, how long each one is, and where a point at a given
arc fraction lies — is gathered HERE and handed in. The GUI, the headless pipeline and
the gate all build the same context from the same :class:`MeshConfig`.

A BINDING IS A SEGMENT'S STABLE ID, NEVER ITS POSITION IN A LIST. The id is the
``SegmentModel.id`` the PreProcessor stamps into the ``.meta`` sidecar's ``NSEGMENTS``
rows and into its per-point ``POINTS`` column (``tools/PreProcessor/src/main.cpp``:
``const int segId = sj.value("id", segIndex)``), and it is the number the mesher matches
on (``src/MultiBlock.cpp``: ``if (g.segId[k] != seg) continue``). So the sidecar column
IS the stable id — "resolution" here is a LOOKUP that proves the id is still on disk, not
index arithmetic — and the positional alternative is the failure this module exists to
make unreachable: inserting, deleting or reordering a segment shifts every binding after
it, producing a mesh whose walls are bound to the wrong segments with NO ERROR AT ALL.
That is the same failure class that once exported an entire mesh as ``wall``.

WHEN AN ID CANNOT BE RESOLVED THE PROJECTION IS REFUSED AND THE EDGE IS NAMED. It never
falls back to the configured default boundary condition, which would be a mesh that runs,
exports and looks right while carrying the wrong conditions — the one outcome worse than
a refusal. :class:`BindingError` carries the edge id so the panel (#138) can flag it
without parsing a message.

AND THE REPAIR IS MADE IN THE PANEL, NOT IN THE FILE (#138). A refusal alone hands the
user an error message and a JSON document they were never meant to open, at the one
moment they already know the answer — they just made the CAD edit that broke it. So a
family also reports :class:`BrokenBinding` rows, which are what the panel flags and
what its dropdown repairs; the refusal is unchanged and is still what an unrepaired
binding gets.

READS ARE CACHED BY (path, mtime, size). The skeleton overlay and the derived read-out
both ask for a context on every keystroke; without the cache that is a ``.dat`` and a
``.meta`` parse per character typed. The key is the file's own stamp rather than a
timer, so an edit made by the resampler in between is picked up on the next ask.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

from app.services import meta_io
from app.services.geom_path_identity import canonical_geom_path
from app.services.logging_setup import get_logger

_log = get_logger(__name__)

#: Fraction of the LOCAL point spacing within which the two ends of a polyline count
#: as the same point, so the loop is CLOSED and its trailing duplicate is dropped.
#: The mesher's own number and the mesher's own rule (``include/PointTolerance.hpp``
#: ``POINT_COINCIDENCE_FRACTION``, applied in ``src/cli.cpp::loadGeometry``), mirrored
#: rather than re-invented: a context that disagreed with the loader about whether a
#: body closes would put the last segment's t = 1 one resampling interval away from
#: where the run puts it. Gated against the C++ by ``tests/test_topology_ogrid.py``.
POINT_COINCIDENCE_FRACTION = 0.05

#: The floor the mesher's own tolerance keeps under that fraction.
CLOSE_TOL_FLOOR = 1e-6


class BindingError(ValueError):
    """A binding that names something the geometry no longer has.

    Carries the EDGE as a field rather than only inside the message, because the
    panel that repairs it (#138) needs to flag that edge rather than re-parse prose.
    """

    def __init__(self, message: str, edge: str = "", geom: str = "", seg: int = -1):
        super().__init__(message)
        self.edge = edge
        self.geom = geom
        self.seg = seg


@dataclass(frozen=True)
class BrokenBinding:
    """One stored binding that no longer names a segment its geometry carries.

    THE REPAIR IS MADE IN THE PANEL, NOT IN THE FILE (#138). :class:`BindingError`
    is the refusal, and the refusal alone leaves the user holding an error message
    and a JSON document they were never meant to open — while the moment a binding
    breaks is precisely the moment they know the answer, because they are the one
    who just cut the segment. So a family reports its broken bindings as these
    rows, each carrying everything the panel needs to flag one and to offer the
    repair: which stored list holds it (``field``, a :class:`TopologyModel` field
    name rather than a widget, so this stays Qt-free), WHERE in that list
    (``pos``), which EDGES go dark because of it, what it was bound to, and the
    segments that geometry has right now.

    ``choices`` is the geometry's CURRENT segment list, whole and in its own order.
    Every one of them is a legal answer, because a valid binding is a rotation of
    that list (``topology_ogrid_binding.cover_problem``) and naming the segment one
    flagged edge should lie on picks the rotation.

    ``edges`` is a tuple rather than one id because a source segment becomes
    ``ogrid_splits`` block edges: one broken id darkens all of them, and naming
    only the first would under-report what the user is looking at.
    """

    #: The ``TopologyModel`` field holding the list this row is a position in.
    field: str
    #: The role the family gives this list, for the sentence ("body", "far field").
    who: str
    #: The geometry spelling the binding is against.
    geom: str
    #: The stored id the geometry no longer carries.
    seg: int
    #: Its index in the stored list — what a repair replaces.
    pos: int
    #: Every edge id that binds through this position.
    edges: tuple[str, ...] = ()
    #: The geometry's current segment ids, in its own order.
    choices: tuple[int, ...] = ()

    def label(self) -> str:
        """The flag, naming the edges, the geometry and what they were bound to."""
        word = "edge" if len(self.edges) == 1 else "edges"
        named = ", ".join(self.edges) or "(none)"
        return (f"{word} {named}: the {self.who} binds segment {self.seg} of "
                f"'{os.path.basename(self.geom) or self.geom}', which it no longer "
                f"carries")


@dataclass(frozen=True)
class SegmentSpan:
    """One source segment's polyline, as the mesher walks it.

    ``points`` runs from the segment's own first point to the JOINT where the next
    segment begins — one point past its last, exactly as ``src/MultiBlock.cpp``'s
    ``spanFor`` extends it, wrapping to index 0 for the last segment of a closed
    loop. Without that extension a segment's arc length stops one spacing short and
    every ``t`` computed from it is off by that much.
    """

    seg_id: int
    points: tuple[tuple[float, float], ...]
    #: Cumulative arc length at each point; ``cum[-1]`` is the segment's length.
    cum: tuple[float, ...]

    @property
    def length(self) -> float:
        return self.cum[-1] if self.cum else 0.0

    def point_at(self, t: float) -> tuple[float, float] | None:
        """The point at normalized arc length ``t`` along this segment.

        The same quantity ``pointAtArc`` computes in the mesher, and it is what puts
        a bound corner on the canvas. ``None`` for a degenerate span, so a caller
        reports "bound but unplaced" rather than drawing (0, 0).
        """
        if len(self.points) < 2 or self.length <= 0.0:
            return None
        want = max(0.0, min(1.0, float(t))) * self.length
        for k in range(1, len(self.cum)):
            if self.cum[k] >= want:
                seg = self.cum[k] - self.cum[k - 1]
                f = 0.0 if seg <= 0.0 else (want - self.cum[k - 1]) / seg
                (x0, y0), (x1, y1) = self.points[k - 1], self.points[k]
                return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)
        return self.points[-1]


@dataclass(frozen=True)
class GeomBinding:
    """One geometry, as everything a family may ask about it.

    ``spelling`` is the string the mesher config's ``GEOM_FILE`` line carries, and
    therefore the string a document's ``geom`` key must repeat: the mesher matches by
    exact name first and by a UNIQUE basename second (``findGeometry``), so repeating
    the config's own spelling is the one form that cannot become ambiguous.
    """

    spelling: str
    path: str
    #: The sidecar's segment ids, in the order the points run. Ids, not indices.
    seg_ids: tuple[int, ...]
    spans: dict
    closed: bool

    @property
    def perimeter(self) -> float:
        return sum(s.length for s in self.spans.values())

    def equivalent_radius(self) -> float:
        """The radius of the circle with this outline's enclosed area.

        The O-grid's radial law is stated for a CIRCULAR O-grid, so the radius it
        needs is ONE number for the whole loop. Area-equivalent rather than a mean
        distance from the centroid, and the difference is not cosmetic: a mean over
        the sampled points moves with the POINT COUNT — on a square outline it fell
        from one resampling to the next — so the derived radial count moved with it
        and re-sampling a geometry became a topology edit. The enclosed area does
        not: it is exact at any sampling of a straight-sided outline, and on the
        shipped 160-point circle it gives 0.4999971 against a true 0.5.

        Exact for the circle the law is written for; an equivalent radius, labelled
        as one, for anything else.
        """
        pts = [p for s in self.spans.values() for p in s.points]
        if len(pts) < 3:
            return 0.0
        a2 = sum(pts[k][0] * pts[(k + 1) % len(pts)][1]
                 - pts[(k + 1) % len(pts)][0] * pts[k][1]
                 for k in range(len(pts)))
        return math.sqrt(abs(a2) / (2.0 * math.pi))

    def signed_area(self, seg_ids, ts) -> float:
        """Twice the signed area of the corner ring at ``(seg, t)``, or 0.0.

        Positive is counter-clockwise. What the O-grid asks in order to wind its
        blocks the way the mesher's orientation rule requires, instead of assuming
        the user drew their body anticlockwise.

        0.0 when the ring encloses nothing or a corner could not be placed, which
        the caller reports as a refusal rather than treating as a direction.
        """
        ring = []
        for sid, t in zip(seg_ids, ts):
            sp = self.spans.get(sid)
            p = sp.point_at(t) if sp is not None else None
            if p is None:
                return 0.0
            ring.append(p)
        if len(ring) < 3:
            return 0.0
        a = 0.0
        for k in range(len(ring)):
            x0, y0 = ring[k]
            x1, y1 = ring[(k + 1) % len(ring)]
            a += x0 * y1 - x1 * y0
        return a



@dataclass(frozen=True)
class BindingContext:
    """Every geometry the mesh loads, plus the run parameters a family may read.

    ``first_cell`` is the run's ``BL_INITIAL_THICKNESS`` and is passed rather than
    duplicated as a template parameter: #133's decision is that a template uses the
    EXISTING boundary-layer parameter name rather than an alias, because the physical
    quantity is identical. It is read here so a family can DERIVE from it (the
    O-grid's radial count) while the value itself still has exactly one home.
    """

    geoms: tuple[GeomBinding, ...]
    first_cell: float = 0.0

    def names(self) -> list[str]:
        return [g.spelling for g in self.geoms]

    def geometry(self, name: str) -> GeomBinding | None:
        """The geometry ``name`` refers to, by FILE identity then by basename.

        Matched the way the mesher matches (``findGeometry``): the exact spelling
        first, then a unique basename — so a user who typed ``circle_body.dat`` and
        a config holding ``examples/geometries/circle_body.dat`` agree, and an
        ambiguous basename resolves to nothing rather than to a guess.
        """
        want = (name or "").strip()
        if not want:
            return None
        canon = canonical_geom_path(want)
        for g in self.geoms:
            if g.spelling == want or (canon and canonical_geom_path(g.path) == canon):
                return g
        base = os.path.basename(want)
        hits = [g for g in self.geoms if os.path.basename(g.path) == base]
        return hits[0] if len(hits) == 1 else None

    def resolve(self, edge: str, geom: str, seg: int) -> int:
        """``seg`` itself, once proven still present on ``geom``. Otherwise refuse.

        The whole of the id-versus-index decision lands here: the value returned is
        the sidecar's own segment id, so nothing downstream ever holds a position.
        """
        g = self.geometry(geom)
        if g is None:
            raise BindingError(
                f"edge '{edge}' binds to geometry '{geom}', which this mesh does not "
                f"load. It loads: {', '.join(self.names()) or '(nothing)'}.",
                edge=edge, geom=geom, seg=seg)
        if seg not in g.spans:
            raise BindingError(
                f"edge '{edge}' binds to segment {seg} of '{g.spelling}', which that "
                f"geometry no longer has. It carries segment(s) "
                f"{', '.join(str(s) for s in g.seg_ids) or '(none)'}. A binding is a "
                f"segment's stable id: re-point the edge at a segment that exists "
                f"rather than letting it fall back to the default condition.",
                edge=edge, geom=g.spelling, seg=seg)
        return seg


# ── building one from a mesh configuration ──────────────────────────────────

#: canonical path -> (stamp, GeomBinding). CAPPED, because the geometry rows are
#: ``path`` widgets that emit on every keystroke, so a typed path leaves an entry per
#: PREFIX — a module global that only ever grows is a leak however small each entry
#: is. Dropped whole rather than by age: the working set is one or two geometries, so
#: an LRU would be machinery for a case that does not arise, and re-reading two files
#: once in a while is cheaper than keeping one.
_CACHE: dict = {}
_CACHE_CAP = 32


def _stamp(path: str) -> tuple:
    def one(p):
        try:
            st = os.stat(p)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return (0, 0)
    return one(path) + one(meta_io.meta_path_for(path))


def _load_points(path: str) -> list[tuple[float, float]]:
    from app.services.geometry_service import GeometryLoadError, load_points_dat
    try:
        arr = load_points_dat(path)
    except (GeometryLoadError, OSError, ValueError):
        _log.debug("topology binding: %s could not be read as a geometry", path,
                   exc_info=True)
        return []
    return [(float(r[0]), float(r[1])) for r in arr]


def _close_loop(pts: list, ids: list) -> tuple[list, list, bool]:
    """``(points, seg ids, closed)`` after the loader's own seam weld.

    THE TRAILING DUPLICATE IS DROPPED FROM BOTH, which is the whole reason this
    function exists rather than a bare "is it closed" predicate. A shipped closed
    circle's sidecar assigns its final point back to segment 0, so leaving it in
    makes segment 0 look non-contiguous (indices 0..39 and 160) and this module
    would report a body with three segments where the mesher sees four — measured
    on ``examples/geometries/circle_body.dat``. ``src/cli.cpp::loadGeometry`` pops
    the point and ``reconcileMeta`` pops the sidecar entry beside it; both are
    mirrored here.
    """
    if len(pts) > 1:
        gap = math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
        tol = CLOSE_TOL_FLOOR
        if len(pts) > 2:
            span = min(math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]),
                       math.hypot(pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]))
            if span > 0.0:
                tol = max(tol, POINT_COINCIDENCE_FRACTION * span)
        if gap <= tol:
            pts = pts[:-1]
            if len(ids) == len(pts) + 1:
                ids = ids[:-1]
            return pts, ids, True
    return pts, ids, False


def _spans(pts: list, ids: list, closed: bool) -> tuple[tuple, dict]:
    """``(seg ids in point order, {id: SegmentSpan})``.

    A segment whose points are NOT one contiguous run is dropped rather than
    stitched: the mesher refuses such a segment by name ("is not one contiguous run
    of points, so an arc length along it is not a length of anything"), and a
    context that quietly answered for it would let a family seed a count for an edge
    the run then refuses.
    """
    n = min(len(pts), len(ids))
    order: list[int] = []
    first: dict = {}
    last: dict = {}
    for k in range(n):
        s = ids[k]
        if s not in first:
            first[s] = k
            order.append(s)
        last[s] = k
    out: dict = {}
    keep: list[int] = []
    for s in order:
        lo, hi = first[s], last[s]
        if any(ids[k] != s for k in range(lo, hi + 1)):
            continue
        run = list(pts[lo:hi + 1])
        if hi + 1 < n:
            run.append(pts[hi + 1])
        elif closed and pts:
            run.append(pts[0])
        if len(run) < 2:
            continue
        cum = [0.0]
        for k in range(1, len(run)):
            cum.append(cum[-1] + math.hypot(run[k][0] - run[k - 1][0],
                                            run[k][1] - run[k - 1][1]))
        out[s] = SegmentSpan(seg_id=s, points=tuple(run), cum=tuple(cum))
        keep.append(s)
    return tuple(keep), out


def geometry_binding(spelling: str) -> GeomBinding:
    """Everything resolvable about the geometry ``spelling`` names, cached by stamp."""
    path = canonical_geom_path(spelling) or spelling
    stamp = _stamp(path)
    hit = _CACHE.get(path)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    pts = _load_points(path)
    ids = meta_io.read_meta_point_segids(path)
    pts, ids, closed = _close_loop(pts, ids)
    seg_ids, spans = _spans(pts, ids, closed)
    g = GeomBinding(spelling=spelling, path=path, seg_ids=seg_ids, spans=spans,
                    closed=closed)
    if len(_CACHE) >= _CACHE_CAP:
        _CACHE.clear()
    _CACHE[path] = (stamp, g)
    return g


def context_for_config(cfg) -> BindingContext:
    """The context the mesh ``cfg`` describes: its geometries, and its first cell.

    Duck-typed like the rest of this package: the caller holds a ``MeshConfig``, but
    what is read is a geometry list and one length, and the gate builds neither.
    """
    files = list(getattr(cfg, "geom_files", None) or [])
    try:
        first_cell = float(getattr(cfg, "bl_initial_thickness", 0.0) or 0.0)
    except (TypeError, ValueError):
        first_cell = 0.0
    return BindingContext(geoms=tuple(geometry_binding(f) for f in files),
                          first_cell=first_cell)


def locator(ctx: BindingContext):
    """A ``topology_skeleton.skeleton`` ``locate`` callback backed by ``ctx``.

    The parameter that module reserved for this ticket, filled in from here rather
    than from the canvas: where a bound corner IS is a question about the geometry,
    and the overlay decides nothing about the geometry.
    """
    def place(corner: dict):
        g = ctx.geometry(str(corner.get("geom", "")))
        if g is None:
            return None
        try:
            sid = int(corner.get("seg", -1))
            t = float(corner.get("t", 0.0))
        except (TypeError, ValueError):
            return None
        sp = g.spans.get(sid)
        return None if sp is None else sp.point_at(t)
    return place
