#!/usr/bin/env python3
"""A C/H topology for a single aerofoil: a C-ring around the body AND ITS WAKE,
opening downstream onto a RECTANGULAR far field.

A RESEARCH HARNESS beside ``docs/research/gridpro-blocking-method.md``, section
13. Nothing shipped reads it; nothing in ``config/`` or ``examples/`` is written
by it. It does not replace ``make_rings.py`` -- that one is the O-ring family
sections 9-11 measure, and section 12 is why this file exists instead of a
further knob on it.

WHY A C AND NOT A RING. Section 12a read GridPro's own `fig6.webp` (an aerofoil
with icing) and found its far field is not a radial fan against a circle: the
lines wrap the nose in a C and then run PARALLEL AND STREAMWISE, the wake leaves
the trailing edge as a straight horizontal band, and the outer boundary is a
RECTANGLE the grid becomes a Cartesian lattice against. Section 12b made the far
field a rectangle inside the ring family and measured it much WORSE (89.2 deg
worst non-orthogonality against the circle's 48.1), because a ring is a ring:
naming the outer boundary a rectangle does not make the lines ahead of the nose
horizontal.

A C-grid does, by construction. Its xi direction runs along the wake, around the
body and back along the wake, so the lines LEAVING the nose point at the inlet
and the lines leaving the wake point at the top and bottom boundaries. There is
no fan ahead of the nose because nothing wraps round the front.

WHAT IS GRIDPRO'S HERE: the C/H arrangement itself, read off fig6; the trailing
edge's internal surfaces bisecting the exterior angle equally (section 3c), which
here fixes where the two trailing-edge radials land; and the rule that the answer
to a badly shaped region is more blocks.

WHAT IS OURS: the body, the domain extents, every node count, and the fact that
every block boundary is a straight chord or a bound polyline rather than the
output of a converged elliptic solve (section 10b).

    python3 docs/research/gridpro-blocking-method/make_ch.py [--split K] [--wake M]
    ./run.sh -conf docs/research/gridpro-blocking-method/gridpro_ch.dat
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
from make_rings import (read_body, arc_table, at_fraction, te_rays,   # noqa: E402
                        arc_tangent_at, arc_exit_tangent)

BODY = "examples/geometries/naca0012_cgrid.dat"
BODY_NAME = "naca0012_cgrid.dat"
# --body re-points both. The binding carries the BASENAME, which is what the
# mesher matches its GEOM_FILE against, so the two must move together.

# The far-field rectangle, in chords. 9 x 6 is the DEFAULT because it is the
# extent the O-ring cases of sections 9-11 are closest to -- their far field is
# GridPro's tutorial circle of radius 3 -- so section 13e's comparison is at a
# comparable domain. It is NOT the right size to solve on: section 14c measured
# that at Re 200 it cuts through the viscous region and the residual sits four
# times higher than at the shipped C-grid case's own 30 x 20. For a solver run
# pass --domain -10 20 10, which is what section 14's figures were taken at.
XI, XO, YF = -2.0, 7.0, 3.0
DS_SURF = 0.005                 # the shipped C-grid's surface clustering
WAKE_GROWTH = 1.9
CURVED = True                   # radials as the arc that leaves perpendicular
ARC_OUT = False                 # ... and KEEP curving on the layers outside it
ARC_OUT_W = 1.0                 # how far toward perpendicular-at-the-far-field
ARC_OUT_C = (0.25, 0.0)         # the centre those arcs aim radially out from
FAR_BY_ARC = 0.0                # blend the far-field map toward ARC LENGTH
FAR_MONO = False                # ... or repair the cast where it reverses
PIN_TIPS = 0                    # snap stations onto the sharpest features
PIN_CONCAVE = False             # ... including the concave ones
LAYERS = 1                      # radial layers from the body out to the far field
LAYER_GROWTH = 5.0              # how fast those bands thicken outward
WALL_BAND = 0.05                # the innermost band's thickness, in chords
BL_FIRST = 0.001                # BL_INITIAL_THICKNESS, as the .dat declares it
H_OUTER = False                 # a Cartesian H lattice outside an inner box
BOX_L, BOX_Y = -0.8, 1.0        # that box: open at the outlet, in chords
H_STRETCH = True                # spread the inlet side over the whole far inlet
TURN_BLEND = 1.0                # 1 = equal normal turn, 0 = equal arc length               # how fast the wake's own stations spread aft
N_RADIAL = 49                   # nodes from the body/wake out to the far field
N_SURF = 40                   # intervals along ONE surface
N_WAKE = 34                   # intervals along the wake, per side
N_WALL_LAYER = 25             # nodes across the innermost layer, when LAYERS > 1
N_OUTER_LAYER = 17            # ... and across each layer outside it
# --node-scale multiplies the five counts above together, so a case can be
# built at ANOTHER GRID'S SIZE without changing its blocking. It exists to
# compare against GridPro's own stated 3648 cells, which is far coarser than
# anything else in this directory (section 7).


# -- the far-field C, as one arc-length-parametrised polyline ---------------

def far_path():
    """The rectangle walked as the body's own C is: from the outlet BELOW the
    wake, along the bottom, up the inlet, along the top, back to the outlet
    ABOVE it. Open at the outlet, exactly as the body+wake line is."""
    return [(XO, -YF), (XI, -YF), (XI, YF), (XO, YF)]


def path_table(poly):
    s = [0.0]
    for a, b in zip(poly, poly[1:]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return s


def path_at(poly, s_tab, s):
    s = max(0.0, min(s_tab[-1], s))
    i = max(k for k in range(len(s_tab) - 1) if s_tab[k] <= s)
    a, b = poly[i], poly[i + 1]
    seg = s_tab[i + 1] - s_tab[i]
    u = 0.0 if seg == 0.0 else (s - s_tab[i]) / seg
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def path_s_of(poly, s_tab, p):
    """Arc position of a point known to lie ON the path."""
    for i in range(len(poly) - 1):
        a, b = poly[i], poly[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (L * L)
        if -1e-9 <= t <= 1 + 1e-9:
            off = math.hypot(p[0] - (a[0] + dx * t), p[1] - (a[1] + dy * t))
            if off < 1e-7:
                return s_tab[i] + t * L
    raise SystemExit("point %s is not on the far-field path" % (p,))


def ray_to_boxc(p, deg):
    """Where the ray from ``p`` at ``deg`` meets the INNER BOX -- a rectangle
    OPEN AT THE OUTLET, the same C shape the far field is.

    This is what section 12d could not build on the O-ring family: there the
    inner box had to clear a CLOSED ellipse upstream while keeping the far
    field's aspect, and the two could not both hold. Here the inner object is a
    thin band hugging the body, and the box is open downstream, so there is no
    downstream extent to match and the conflict is gone. Section 18.
    """
    r = math.radians(deg)
    cx, cy = math.cos(r), math.sin(r)
    ts = []
    if cx < -1e-12:
        ts.append((BOX_L - p[0]) / cx)
    if abs(cy) > 1e-12:
        ts.append(((BOX_Y if cy > 0 else -BOX_Y) - p[1]) / cy)
    t = min([x for x in ts if x > 1e-12] or [0.0])
    return (p[0] + t * cx, p[1] + t * cy)


def boxc_to_far(q):
    """A point on the inner box, projected AXIS-ALIGNED onto the far field.

    Top and bottom go straight out at the same x; the inlet side goes straight
    forward at the same y; the two corners go to the far field's own corners.
    That is what makes the outer region a CARTESIAN LATTICE -- vertical lines
    above the box, horizontal ones ahead of it -- instead of the fan a radial
    mapping leaves, which is the one structural difference section 17f still
    had against fig6.
    """
    on_left = abs(q[0] - BOX_L) < 1e-9
    on_top = abs(abs(q[1]) - BOX_Y) < 1e-9
    if on_left and on_top:
        return (XI, YF if q[1] > 0 else -YF)
    if on_left:
        return (XI, q[1] * (YF / BOX_Y) if H_STRETCH else q[1])
    return (q[0], YF if q[1] > 0 else -YF)


def ray_to_rect(p, deg):
    """Where the ray from ``p`` at ``deg`` meets the far-field rectangle."""
    r = math.radians(deg)
    cx, cy = math.cos(r), math.sin(r)
    ts = []
    if abs(cx) > 1e-12:
        ts += [((XO if cx > 0 else XI) - p[0]) / cx]
    if abs(cy) > 1e-12:
        ts += [((YF if cy > 0 else -YF) - p[1]) / cy]
    t = min(x for x in ts if x > 0)
    return (p[0] + t * cx, p[1] + t * cy)


# -- the document -----------------------------------------------------------

class Topo(object):
    def __init__(self):
        self.pos, self.corners, self.edges, self.blocks, self.ends = \
            {}, [], [], [], {}

    def free(self, cid, xy):
        if cid in self.pos:
            return cid
        self.pos[cid] = (xy[0], xy[1])
        self.corners.append({"id": cid, "kind": "free", "xy": [xy[0], xy[1]]})
        return cid

    def onbody(self, cid, seg, t, xy):
        if cid in self.pos:
            return cid
        self.pos[cid] = (xy[0], xy[1])
        self.corners.append({"id": cid, "kind": "on_geometry",
                             "geom": BODY_NAME, "seg": seg, "t": t})
        return cid

    def edge(self, eid, a, b, kind, **kw):
        e = {"id": eid, "corners": [a, b], "kind": kind}
        e.update({k: v for k, v in kw.items() if v})
        self.edges.append(e)
        self.ends[eid] = (a, b)
        return eid

    def block(self, bid, ring):
        p = [self.pos[c] for c in ring]
        area = sum(p[i][0] * p[(i + 1) % 4][1] - p[(i + 1) % 4][0] * p[i][1]
                   for i in range(4))
        if area < 0:
            ring = list(reversed(ring))
        fwd = {v: k for k, v in self.ends.items()}
        for r in range(4):
            c = ring[r:] + ring[:r]
            if (c[0], c[1]) not in fwd:
                continue
            self.blocks.append({"id": bid, "edges": [
                fwd[(c[0], c[1])], self._side(c[1], c[2]),
                self._side(c[3], c[2]), self._side(c[0], c[3])]})
            return
        raise SystemExit("block %s: no side is declared along its ccw ring" % bid)

    def _side(self, a, b):
        for eid, (x, y) in self.ends.items():
            if (x, y) == (a, b) or (x, y) == (b, a):
                return eid
        raise SystemExit("no edge between %s and %s" % (a, b))


def by_normal_turn(poly, n):
    """``n - 1`` interior arc-length fractions along ``poly`` at EQUAL
    increments of the surface normal's own direction.

    Equal ARC LENGTH is the wrong law here. A body station's far-field point is
    where its normal arrives (see the map below), so what spaces the far field
    evenly is spacing the NORMAL evenly -- and on an aerofoil that is also what
    puts the stations where the surface turns. Measured with equal arc instead:
    the last stretch before the leading edge faced a far-field stretch 36 times
    its own length, 12 cells inverted and a worst adjacent area ratio of 2132.
    """
    s_tab, total = arc_table(poly)
    m = 400
    fr = [k / m for k in range(m + 1)]
    ang, prev = [], None
    for f in fr:
        a = math.degrees(math.atan2(*reversed(at_fraction(poly, min(f, 1.0))[1])))
        if prev is not None:
            while a - prev > 180.0:
                a -= 360.0
            while prev - a > 180.0:
                a += 360.0
        ang.append(a)
        prev = a
    out = []
    for j in range(1, n):
        target = ang[0] + (ang[-1] - ang[0]) * j / n
        i = max(k for k in range(m) if (ang[k] - target) * (ang[-1] - ang[0]) <= 0)
        d = ang[i + 1] - ang[i]
        u = 0.0 if d == 0 else (target - ang[i]) / d
        out.append(fr[i] + (fr[i + 1] - fr[i]) * u)
    return out


def layer_last_interval(span, n_nodes, first):
    """The last interval of a ``span`` filled by ``n_nodes`` whose first is
    ``first``, assuming geometric growth -- the estimate used to hand one
    layer's trailing cell size to the next as its leading one."""
    m = max(1, n_nodes - 1)
    if first <= 0 or first * m >= span:
        return span / m
    lo, hi = 1.0 + 1e-12, 4.0
    for _ in range(80):                       # solve first*(G^m - 1)/(G-1) = span
        g = 0.5 * (lo + hi)
        if first * (g ** m - 1.0) / (g - 1.0) < span:
            lo = g
        else:
            hi = g
    g = 0.5 * (lo + hi)
    return first * g ** (m - 1)


def layer_fracs(n):
    """``n + 1`` fractions 0 .. 1 down each radial, growing GEOMETRICALLY.

    ``n = 1`` is the single layer sections 13-16 measure and returns [0, 1]
    exactly, so that case is untouched. Past that, the first fraction is small
    and the band it makes HUGS THE BODY -- which is what GridPro's fig6 has and
    section 13 did not: a thin surface ring cut into blocks chordwise, then
    further rings outward. Section 17.
    """
    if n == 1:
        return [0.0, 1.0]
    g = LAYER_GROWTH
    return [0.0] + [(g ** k - 1.0) / (g ** n - 1.0) for k in range(1, n + 1)]


def node(cid):
    """The CORNER a walk entry names. ``te_lo`` and ``te_up`` are two walk
    entries -- the trailing edge is visited once on each side of the cut -- and
    ONE node, which is what makes four blocks meet there on a single corner."""
    return "te" if cid.startswith("te") else cid


def rect_outward(q, tol=1e-6):
    """The outward unit normal of the RECTANGULAR far field at a point on it."""
    best, d = (0.0, 1.0), abs(q[1] - YF)
    for cand, dist in (((0.0, -1.0), abs(q[1] + YF)),
                       ((-1.0, 0.0), abs(q[0] - XI)),
                       ((1.0, 0.0), abs(q[0] - XO))):
        if dist < d:
            best, d = cand, dist
    return best


def arc_perp_at_far(p_inner, p_outer):
    """The `curve` for an edge ``p_inner -> p_outer`` that ARRIVES at the far
    field PERPENDICULAR to it.

    ``arc_tangent_at`` prescribes the tangent at the edge's START; this
    prescribes it at the END, by building the same arc from the other end and
    reversing the sweep. It is what gives the outer layer a visible curvature
    instead of a chord: the line leaves the body along the body's normal, and
    arrives at the rectangle along the rectangle's.

    THIS IS NOT GRIDPRO'S MECHANISM and the difference is recorded rather than
    glossed: GridPro's arcs are what a converged elliptic solve leaves over
    straight wireframe links (section 1a), and section 10 -- confirmed again in
    section 28 by sweeping MB_SMOOTH_ITERS to 60 and folding 1000 cells -- shows
    this repo's smoother diverges long before it curves anything. So the same
    APPEARANCE is reached by declaring the arc. The shape agrees; the provenance
    does not.
    """
    # SMOOTHLY VARYING, not the rectangle's own normal. A rectangle has corners,
    # so "perpendicular to the far field" is DISCONTINUOUS across them: two
    # neighbouring radials off the nose land one on the inlet and one on the top,
    # get target tangents 90 degrees apart, and their arcs bend opposite ways and
    # cross. Measured: 16 inverted cells at a blend of only 0.15, in exactly two
    # mirrored blocks at x = -0.27, |y| = 0.47 -- the nose (section 28c). Aiming
    # the arc radially OUTWARD FROM A CENTRE near the body instead varies
    # smoothly everywhere and is what "perpendicular to a circle" would give,
    # which is the far field GridPro's own tutorial text states (section 3a).
    rx, ry = p_outer[0] - ARC_OUT_C[0], p_outer[1] - ARC_OUT_C[1]
    rn = math.hypot(rx, ry)
    if rn == 0.0:
        return None
    outward = (rx / rn, ry / rn)
    # BLENDED, because the full 90 degrees does not fit. Arriving exactly
    # perpendicular to the top of the rectangle means arriving vertically, and a
    # line that left the nose horizontally cannot do that through one arc
    # between two fixed corners without looping: measured at w = 1.0, 112
    # inverted cells and the worst corner 50.06 -> 73.08 (section 28c). The
    # blend is between the chord (w = 0, the old straight edge) and that
    # perpendicular, and the shipped value is the largest that still meshes.
    ch = (p_inner[0] - p_outer[0], p_inner[1] - p_outer[1])
    n = math.hypot(*ch)
    if n == 0.0:
        return None
    ch = (ch[0] / n, ch[1] / n)
    tgt = (ch[0] * (1.0 - ARC_OUT_W) - outward[0] * ARC_OUT_W,
           ch[1] * (1.0 - ARC_OUT_W) - outward[1] * ARC_OUT_W)
    m = math.hypot(*tgt)
    if m < 1e-12:
        return None
    cv = arc_tangent_at(p_outer, (tgt[0] / m, tgt[1] / m), p_inner)
    if cv is None:
        return None
    cv = dict(cv)
    cv["sweep"] = "cw" if cv.get("sweep", "ccw") == "ccw" else "ccw"
    return cv


def curvature_peaks(poly, k_max):
    """Arc-length fractions of the ``k_max`` sharpest convex features of ``poly``.

    THE METHOD'S OWN MOVE, and the one a station LAW cannot make. Every station
    law in this file -- equal arc, equal normal turn, the lerp between them --
    spaces stations by a rule and so lands a block corner ON a salient feature
    only by luck. GridPro's method is the opposite way round: the complicated
    part of the geometry gets block corners BECAUSE it is complicated. On the
    iced section beside this file the single remaining fold sits at (0.016,
    0.074), which is the upper horn's tip -- measured -- so the block edge was
    cutting across the tip instead of meeting it.

    Convex only: a concave valley wants a station too, but a corner declared in
    a concave feature folds the block inside it, and the ice valley is exactly
    that. Measured sign convention: this polyline is traversed with the body on
    the left, so a convex tip turns one way and the valley the other.
    """
    n = len(poly)
    s_tab, total = arc_table(poly)
    turn = [0.0] * n
    for i in range(1, n - 1):
        ax, ay = poly[i][0] - poly[i - 1][0], poly[i][1] - poly[i - 1][1]
        bx, by = poly[i + 1][0] - poly[i][0], poly[i + 1][1] - poly[i][1]
        la, lb = math.hypot(ax, ay), math.hypot(bx, by)
        if la == 0.0 or lb == 0.0:
            continue
        cross = (ax * by - ay * bx) / (la * lb)
        dot = (ax * bx + ay * by) / (la * lb)
        ang = math.degrees(math.atan2(cross, dot))
        turn[i] = ang / max(1e-12, 0.5 * (la + lb))     # degrees per unit arc
    sign = 1.0 if sum(turn) >= 0.0 else -1.0
    cand = []
    for i in range(2, n - 2):
        v = sign * turn[i]
        if v > 0.0 and v >= sign * turn[i - 1] and v >= sign * turn[i + 1]:
            cand.append((v, s_tab[i] / total))
        elif PIN_CONCAVE and v < 0.0 and v <= sign * turn[i - 1] \
                and v <= sign * turn[i + 1]:
            cand.append((-v, s_tab[i] / total))
    cand.sort(reverse=True)
    out, kept = [], []
    for v, f in cand:
        if all(abs(f - g) > 0.02 for g in kept):          # one station per feature
            kept.append(f); out.append((v, f))
        if len(kept) >= k_max:
            break
    return sorted(f for _, f in out)


def build(split, wake_n):
    pts, seg_up, seg_lo = read_body(os.path.join(ROOT, BODY))
    te, rays, sector = te_rays(pts, 3)
    a_up, a_wake, a_lo = rays
    t = Topo()
    fp = far_path()
    fs = path_table(fp)

    # ---- the wake's own stations, spreading aft geometrically ------------
    # WHERE THE FIRST WAKE STATION GOES IS DERIVED FROM THE TRAILING-EDGE
    # RADIAL, not chosen. That radial leaves along the surface's own normal and
    # so lands on the far field a little AFT of the trailing edge; a wake
    # station closer in than that lands in front of it and the two radials
    # pinch. Measured at the first attempt: the two landed 0.013 apart and four
    # cells inverted between them. The first station is therefore put at half
    # as far again as that landing, and the rest grow geometrically from it.
    wdir = (math.cos(math.radians(a_wake)), math.sin(math.radians(a_wake)))
    wend = ray_to_rect(te, a_wake)
    n_lo = at_fraction(seg_lo, 1.0)[1]
    te_land = ray_to_rect(te, math.degrees(math.atan2(n_lo[1], n_lo[0])))
    # HOW FAR AFT: the first wake block's far side is its body side MINUS that
    # landing, so its taper ratio is (f - 1) / f and the other wake blocks' is
    # 1. At f = 1.5 the ratio is 0.33 and the block tapers 3:1 into the
    # boundary; that corner WAS this mesh's worst, at 54.79 deg. f = 4 puts the
    # ratio at 0.75, and is where the defect stops being the binding one -- the
    # worst corner moves to the far-field rectangle's own corner region and
    # stops responding (44.74 deg at f = 4 and at f = 6 alike). That is the
    # criterion: pushed until it is no longer what decides, not tuned to a
    # number. Section 15.
    x1 = te[0] + 4.0 * abs(te_land[0] - te[0])
    g = WAKE_GROWTH
    span = wend[0] - x1
    wake_pt = [te] + [(x1 + span * (g ** j - 1.0) / (g ** (wake_n - 1) - 1.0), te[1])
                      for j in range(wake_n)]

    # ---- the xi walk, from the outlet BELOW the wake round to ABOVE it ----
    # Each entry is (corner id, far-field anchor or None). The wake's nodes and
    # the trailing edge appear TWICE -- once on each side of the cut -- and are
    # the SAME node both times, which is what makes it a cut rather than two
    # coincident walls.
    # ``gap[i]`` is what lies between walk entries i and i+1: the wake, or a
    # stretch of a numbered body segment. Recorded HERE rather than deduced from
    # the two corner names later, which is where the first version put the lower
    # surface's stations in reverse and folded a quarter of the mesh.
    walk, gap = [], []
    for j in range(wake_n, 0, -1):                       # lower wake, aft -> fwd
        walk.append(("wk%d" % j, (wake_pt[j][0], -YF)))
        gap.append(None)
    walk.append(("te_lo", "normal"))                     # the lower TE radial
    for i in range(1, split):                            # lower surface, te -> le
        gap.append(1)
        walk.append(("l%d" % i, "normal"))
    gap.append(1)
    walk.append(("le", (XI, 0.0)))
    for i in range(split - 1, 0, -1):                    # upper surface, le -> te
        gap.append(0)
        walk.append(("u%d" % i, "normal"))
    gap.append(0)
    walk.append(("te_up", "normal"))                     # the upper TE radial
    for j in range(1, wake_n + 1):                       # upper wake, fwd -> aft
        gap.append(None)
        walk.append(("wk%d" % j, (wake_pt[j][0], YF)))

    te_lo_i = [i for i, (c, _) in enumerate(walk) if c == "te_lo"][0]
    # AND GRIDPRO'S EQUAL BISECTION CANNOT BE USED AT THE TRAILING EDGE HERE.
    # Its lower ray leaves at a_lo deg and lands on the rectangle at x = 1.217,
    # while the normal of the very next station on the lower surface lands at
    # x = 1.2425 -- BEHIND it -- so the two radials cross and the map refuses.
    # The bisection ray is steeper than the surface normal it sits next to, and
    # on a thin trailing edge that is enough. What is used instead is the
    # surface's OWN one-sided normal at the trailing edge, which makes the four
    # sectors there 90.0 / 81.7 / 81.7 / 90.0 degrees rather than 85.87 each --
    # a departure from section 3c, and the first thing in this note that
    # GridPro's rule and a C-grid disagree about.
    normals = {}

    # ---- the corners -----------------------------------------------------
    t.onbody("te", 0, 0.0, te)
    t.onbody("le", 1, 0.0, at_fraction(seg_lo, 0.0)[0])
    normals["le"] = (-1.0, 0.0)
    normals["te_lo"] = at_fraction(seg_lo, 1.0)[1]
    normals["te_up"] = at_fraction(seg_up, 0.0)[1]
    # TURN_BLEND 1 is equal increments of the surface normal; 0 is equal arc
    # length; in between is the lerp. The law decides how hard the nose is
    # clustered, which decides the smallest cell in the mesh -- section 16.
    def mix(poly):
        t = by_normal_turn(poly, split)
        if TURN_BLEND == 1.0:
            return t          # BIT FOR BIT, not e + (t - e) * 1.0, which is not
        e = [k / split for k in range(1, split)]
        return [e[i] + (t[i] - e[i]) * TURN_BLEND for i in range(split - 1)]
    def pin(fr, poly):
        """Snap the nearest station onto each sharp convex feature."""
        if PIN_TIPS <= 0:
            return fr
        fr = list(fr)
        for f in curvature_peaks(poly, PIN_TIPS):
            j = min(range(len(fr)), key=lambda k: abs(fr[k] - f))
            fr[j] = f
        fr.sort()
        for i in range(1, len(fr)):                       # keep it strictly increasing
            if fr[i] <= fr[i - 1]:
                fr[i] = fr[i - 1] + 1e-6
        return fr

    fu = pin(mix(seg_up), seg_up)               # te -> le along seg 0
    fl = pin(mix(seg_lo), seg_lo)               # le -> te along seg 1
    tpar = {}
    for i in range(1, split):
        pu, nu = at_fraction(seg_up, fu[i - 1])
        pl, nl = at_fraction(seg_lo, fl[split - 1 - i])
        t.onbody("u%d" % i, 0, fu[i - 1], pu)
        t.onbody("l%d" % i, 1, fl[split - 1 - i], pl)
        normals["u%d" % i], normals["l%d" % i] = nu, nl
        tpar["u%d" % i], tpar["l%d" % i] = fu[i - 1], fl[split - 1 - i]
    for j in range(1, wake_n + 1):
        t.free("wk%d" % j, wake_pt[j])

    # ---- the far-field corner of every walk entry ------------------------
    # The anchored ones are pinned; the rest take an even share of the
    # far-field path between the anchors either side of them, which is what
    # makes a body stretch face a far-field stretch of the same proportion.
    # WHERE A BODY STATION'S FAR-FIELD POINT GOES: where its own OUTWARD NORMAL
    # arrives on the rectangle. That is what makes the far field streamwise --
    # a normal at mid-chord is vertical, so it lands on the top or bottom at
    # the SAME x -- and what gives the nose the big share it needs, since the
    # normals fan through 180 degrees there and sweep the whole corner. The
    # first version spread the body's stretches by ARC LENGTH instead and put
    # mid-chord opposite x = -1.89, so every grid line leaving the body had to
    # swing forward to reach it: measured, 18.2 deg mean non-orthogonality with
    # straight radials and a set of near-concentric arcs with curved ones.
    for i, (cid, a) in enumerate(walk):
        if a == "normal":
            p, n = t.pos[node(cid)], normals[cid]
            walk[i] = (cid, ray_to_rect(p, math.degrees(math.atan2(n[1], n[0]))))
    if H_OUTER:
        # TWO STAGES instead of one. A station's direction is cast onto the
        # INNER BOX, and its far-field point is that box point projected
        # AXIS-ALIGNED. Every station, including the ones already anchored --
        # the trailing-edge rays and the nose radial land on the box too.
        boxpt = {}
        for i, (cid, a) in enumerate(walk):
            p = t.pos[node(cid)]
            if cid.startswith("wk"):
                d = -90.0 if i < te_lo_i else 90.0
            elif cid in normals:
                n = normals[cid]
                d = math.degrees(math.atan2(n[1], n[0]))
            else:
                q = a if isinstance(a, tuple) else t.pos[node(cid)]
                d = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))
            boxpt[i] = ray_to_boxc(p, d)
            walk[i] = (cid, boxc_to_far(boxpt[i]))
    anchor = {i: path_s_of(fp, fs, a) for i, (_, a) in enumerate(walk)
              if a is not None}
    anchor[0] = 0.0
    anchor[len(walk) - 1] = fs[-1]
    # The map is from arc length along the BODY+WAKE line, not from the walk
    # index, so a stretch's far-field counterpart is proportional to its own
    # length rather than to how many stations happen to be beside it.
    # Every station is anchored, so there is nothing to interpolate. An
    # earlier version anchored only the trailing edges, the nose and the two
    # ends and ran a monotone cubic through them by body arc length; the normal
    # cast below made it unreachable and it was deleted rather than left in.
    far_s = dict(anchor)

    # --far-by-arc BLENDS THAT MAP TOWARD ARC LENGTH, and exists because the
    # normal cast above is not monotone on a COMPLICATED leading edge. A glaze
    # ice double horn has a concave valley at the stagnation point, so two
    # neighbouring stations' normals converge and their far-field landings swap
    # order; the check below then refuses, as it should. Measured on the iced
    # section beside this file: refused at EVERY --turn-blend from 0.0 to 1.0,
    # so it is the map and not the station law.
    #
    # Arc length is monotone BY CONSTRUCTION, and the block comment above
    # records why it is not simply used: on a clean section it put mid-chord
    # opposite x = -1.89 and measured 18.2 deg mean non-orthogonality. So this
    # is a blend with both ends known to be wrong in opposite ways, and the
    # shipped value is the smallest that makes the iced case monotone.
    if FAR_BY_ARC > 0.0:
        run = [0.0]
        for i in range(1, len(walk)):
            a, b = t.pos[node(walk[i - 1][0])], t.pos[node(walk[i][0])]
            run.append(run[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        if run[-1] > 0.0:
            for i in range(len(walk)):
                by_arc = fs[-1] * run[i] / run[-1]
                far_s[i] = far_s[i] * (1.0 - FAR_BY_ARC) + by_arc * FAR_BY_ARC

    # --far-monotone KEEPS THE CAST AND REPAIRS ONLY WHERE IT REVERSES. Both
    # maps available before this one are unusable on a complicated leading edge,
    # and the measurement says which half each fails:
    #   * the normal cast is what a usable mesh needs -- clean section, 0
    #     inverted, 1.840 deg mean -- and it is NOT monotone on an iced nose,
    #     so it is refused outright;
    #   * arc length is monotone by construction and FOLDS, and it folds the
    #     CLEAN section too: 1786 inverted of 14320, 42.4 deg mean. That control
    #     is what shows the folding is the map and not the ice (section 29b).
    # So neither end is right, and a blend of two unusable things was not going
    # to be either -- measured, every blend from 0.2 to 0.8 still refused.
    # Isotonic regression is the minimum-change repair: it is the nearest
    # non-decreasing sequence in least squares, so every entry the cast already
    # ordered correctly is left EXACTLY where the cast put it, and only a
    # violating run is averaged. How many entries move is REPORTED, not hidden.
    if FAR_MONO:
        v = [far_s[i] for i in range(len(walk))]
        before = list(v)
        lvl, wt = [], []                                  # pool adjacent violators
        for x in v:
            lvl.append(x); wt.append(1.0)
            while len(lvl) > 1 and lvl[-2] > lvl[-1]:
                x2, w2 = lvl.pop(), wt.pop()
                x1, w1 = lvl.pop(), wt.pop()
                lvl.append((x1 * w1 + x2 * w2) / (w1 + w2)); wt.append(w1 + w2)
        v, k = [], 0
        for x, w in zip(lvl, wt):
            v.extend([x] * int(round(w)))
        # PAVA pools a violating run to ONE value, so the stations in it sit on
        # top of each other and their blocks come out epsilon-wide. That IS
        # visible in the mesh -- several block boundaries collapse onto one line
        # and the far field carries slivers (section 6h). SPREADING each pooled
        # run evenly across the gap its neighbours leave was tried as the fix
        # and is much WORSE: 0 inverted cells become 106, and the worst adjacent
        # area ratio 4.5 becomes 939. The pooled value is the least-squares
        # answer and moving a station off it costs more than the sliver does, so
        # the bare separation below is kept and the slivers are a known cost.
        eps = 1e-9 * max(1.0, fs[-1])
        for i in range(1, len(v)):                        # nothing may still tie
            if v[i] <= v[i - 1]:
                v[i] = v[i - 1] + eps
        moved = [i for i in range(len(v)) if abs(v[i] - before[i]) > eps]
        if moved:
            worst = max(abs(v[i] - before[i]) for i in moved)
            print("  --far-monotone repaired %d of %d far-field stations "
                  "(worst move %.4g, %.2f%% of the far-field path)"
                  % (len(moved), len(v), worst, 100.0 * worst / fs[-1]))
        for i in range(len(v)):
            far_s[i] = v[i]

    for i in range(len(walk) - 1):                       # it must stay increasing
        if far_s[i + 1] <= far_s[i]:
            raise SystemExit("the far-field map is not monotone at walk entry "
                             "%d; two radials would cross%s" % (i,
                             "" if FAR_BY_ARC > 0 else
                             " (--far-by-arc blends this map toward arc length, "
                             "which is monotone by construction -- section 29)"))
    for i in range(len(walk)):
        t.free("F%d" % i, path_at(fp, fs, far_s[i]))

    # ---- the radials, one per walk entry ---------------------------------
    # The two at the very ends lie ON the outlet plane and are the only ones
    # that bound a single block, so they are the only walls among them.
    # ---- the intermediate rings, if there is more than one layer ---------
    fr_l = layer_fracs(LAYERS)
    def lay(k, i):
        """The corner id of walk entry ``i`` on layer ``k`` (0 = the body)."""
        if k == 0:
            return node(walk[i][0])
        return "F%d" % i if k == LAYERS else "L%d_%d" % (k, i)
    # AT A CONSTANT DISTANCE FROM THE BODY, NOT A CONSTANT FRACTION OF THE
    # RADIAL. The radials here run from 2.0 chords at the nose to 6.0 down the
    # wake, so a fixed fraction makes a band three times thicker at one end
    # than the other -- not a ring hugging the body, which is what fig6 has.
    # Measured with the fraction: worst corner 59.2 deg and a worst area ratio
    # of 9.0 at three layers, against 44.7 and 3.0 for the single layer.
    for k in range(1, LAYERS):
        if H_OUTER and k == LAYERS - 1:
            for i in range(len(walk)):          # this ring IS the inner box
                t.free(lay(k, i), boxpt[i])
            continue
        if H_OUTER:
            # THE BANDS MUST ALL FIT INSIDE THE BOX, or one of them crosses it
            # and the layer folds -- measured, 727 inverted cells at five
            # layers, because the geometric growth put the third band at 1.25
            # against a box at 1.0. So when there is a box the bands run
            # geometrically from WALL_BAND up to HALF the box's own inset
            # rather than by a fixed ratio.
            nb = LAYERS - 2                   # bands, excluding body and box
            top = 0.5 * min(abs(BOX_L), BOX_Y)
            d = WALL_BAND if nb <= 1 else \
                WALL_BAND * (top / WALL_BAND) ** ((k - 1) / (nb - 1))
        else:
            d = WALL_BAND * LAYER_GROWTH ** (k - 1)
        for i in range(len(walk)):
            a, b = t.pos[node(walk[i][0])], t.pos["F%d" % i]
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            f = min(d / L, 0.6)
            t.free(lay(k, i), (a[0] + (b[0] - a[0]) * f,
                               a[1] + (b[1] - a[1]) * f))

    for i, (wid, _) in enumerate(walk):
        cid = node(wid)
        last = (i == 0 or i == len(walk) - 1)
        sp = {"ds_start": DS_SURF} if cid.startswith("wk") or last \
            else {"wall_ends": "start"}
        # EVERY RADIAL LEAVES ITS INNER END PERPENDICULAR TO WHAT IT LEAVES, and
        # the arc that does so through its two corners is unique (section 10c).
        # Off the body that is the body's own outward normal; off the wake it is
        # the perpendicular to the cut; the two at the trailing edge already
        # point along GridPro's bisection rays, so for them it is the chord.
        cv = None
        if not last and CURVED:
            d = (0.0, -1.0) if i < te_lo_i else (0.0, 1.0)
            if not cid.startswith("wk"):
                d = normals[wid]
            cv = arc_tangent_at(t.pos[cid], d, t.pos[lay(1, i)])
        # One radial edge PER LAYER. Only the innermost carries the wall
        # clustering; the ones outside it are uniform, and each layer is its own
        # equivalence class so each needs its own seed.
        # EACH LAYER'S FIRST CELL IS THE PREVIOUS LAYER'S LAST, which is what
        # makes a ring seam invisible as a jump in cell size -- the idiom
        # `.claude/rules/mesher-multiblock.md` records for the shipped two-ring
        # O-grid ("the outer ring's ds_start IS the inner ring's last
        # interval"). DERIVED: change a layer's thickness or its node count and
        # the one outside it follows. Without it the three layers' radial cells
        # here are 0.002 / 0.013 / 0.17 and the seams are 6x and 14x jumps.
        rad_len = math.hypot(t.pos["F%d" % i][0] - t.pos[cid][0],
                             t.pos["F%d" % i][1] - t.pos[cid][1])
        prev_last = None
        # WHERE THE OUTER LAYERS' CURVATURE COMES FROM. Only layer 0 carried an
        # arc; every layer outside it was a straight CHORD, and that is visible
        # in the measurement rather than inferred: following each wall-normal
        # line out and splitting its turning into quarters of its own length
        # gives 0.34 / 0.00 / 0.00 / 0.01 degrees -- all of it against the wall,
        # then dead straight (section 28). The maintainer read GridPro's fig6 the
        # other way round: perpendicular NEAR the body, arcs further out.
        #
        # --arc-out continues the arc outward instead, each layer launched along
        # the tangent the one inside it ARRIVED with, so the chain is C1 across
        # every ring seam. The smoother cannot do this: a declared edge is
        # FROZEN, so the block interiors are transfinite between frozen sides --
        # measured, MB_SMOOTH_ITERS 0/5/20 move the first quarter 0.00 -> 0.34 ->
        # 1.26 and leave the other three at zero, and 60 folds the mesh (1000
        # inverted cells).
        tin = None
        if cv is not None:
            tin = arc_exit_tangent(cv, t.pos[lay(0, i)], t.pos[lay(1, i)])
        for k in range(LAYERS):
            n0 = N_RADIAL if LAYERS == 1 else (N_WALL_LAYER if k == 0 else
                                               N_OUTER_LAYER)
            spk = sp if k == 0 else ({"ds_start": prev_last} if prev_last else None)
            if k == 0:
                cvk = cv
            elif ARC_OUT and k == LAYERS - 1 and not last:
                # The OUTERMOST layer arrives perpendicular to the far field.
                # C1-continuing the inner arc instead was implemented first and
                # is INERT: layer 0's arc over a 0.05-chord wall band is already
                # within 1e-4 of its own chord, so continuing its tangent
                # produces a radius `arc_tangent_at` rejects as
                # "indistinguishable from the chord" -- measured, byte-identical
                # output and an unchanged turning profile (section 28b).
                cvk = arc_perp_at_far(t.pos[lay(k, i)], t.pos[lay(k + 1, i)])
            elif ARC_OUT and tin is not None:
                cvk = arc_tangent_at(t.pos[lay(k, i)], tin, t.pos[lay(k + 1, i)])
            else:
                cvk = None
            t.edge("r%d_%d" % (k, i), lay(k, i), lay(k + 1, i),
                   "wall" if last else "interface",   # every layer of the
                   # end radials lies ON the outlet plane, so every one of them
                   # bounds a single block
                   count=n0 if i == 0 else None,
                   spacing=spk,
                   curve=cvk)
            if cvk is not None:
                tin = arc_exit_tangent(cvk, t.pos[lay(k, i)], t.pos[lay(k + 1, i)])
            if LAYERS > 1:
                span = rad_len * (fr_l[k + 1] - fr_l[k]) if False else \
                    math.hypot(t.pos[lay(k + 1, i)][0] - t.pos[lay(k, i)][0],
                               t.pos[lay(k + 1, i)][1] - t.pos[lay(k, i)][1])
                first = BL_FIRST if k == 0 else prev_last
                prev_last = layer_last_interval(span, n0, first)

    # ---- the xi edges, on the body/wake line and on the far field --------
    body_len = arc_table(seg_up)[1]
    seen = {}
    for i in range(len(walk) - 1):
        a, b = node(walk[i][0]), node(walk[i + 1][0])
        pa, pb = t.pos[a], t.pos[b]
        key = frozenset((a, b))
        if key in seen:                                  # the wake, second pass
            inner, decl = seen[key]
        else:
            if gap[i] is None:
                n = max(3, int(round(N_WAKE * abs(pb[0] - pa[0])
                                     / (wend[0] - te[0]))) + 1)
                sp = {"ds_start" if a == "te" else "ds_end": DS_SURF} \
                    if "te" in (a, b) else {}
                inner = t.edge("c%d" % i, a, b, "cut", count=n, spacing=sp)
            else:
                seg = gap[i]
                sp = {}
                if a in ("te", "le"):
                    sp["ds_start"] = DS_SURF
                if b in ("te", "le"):
                    sp["ds_end"] = DS_SURF
                frac = {"te": 0.0 if seg == 0 else 1.0, "le": 1.0 if seg == 0 else 0.0}
                fa = frac.get(a, tpar.get(a))
                fb = frac.get(b, tpar.get(b))
                n = max(4, int(round(N_SURF * abs(fb - fa)))) + 1
                inner = t.edge("c%d" % i, a, b, "wall", count=n,
                               binding={"geom": BODY_NAME, "seg": seg},
                               spacing=sp)
            decl = (a, b)
            seen[key] = (inner, decl)
        ratio = abs(far_s[i + 1] - far_s[i]) / max(1e-9, math.hypot(
            pb[0] - pa[0], pb[1] - pa[1]))
        # AND ON THE WAKE'S SECOND PASS THE CLUSTERING HAS TO TURN ROUND WITH
        # IT. The cut is ONE edge walked twice, in opposite senses, so the
        # far-field edge facing it the second time must carry the mirrored
        # spacing -- otherwise its fine end sits opposite the inner edge's
        # coarse one, the two xi sides of that block cluster against each
        # other, and the fill twists. Measured: two inverted cells just aft of
        # the trailing edge and a 177.9 degree corner between them.
        flip = decl != (a, b)
        swap = {"ds_start": "ds_end", "ds_end": "ds_start"}
        osp0 = {(swap[k] if flip else k): v for k, v in
               (t.edges[[e["id"] for e in t.edges].index(inner)]
                .get("spacing", {}) or {}).items()}
        # One ring edge per layer above the body, and one block per layer.
        for k in range(1, LAYERS + 1):
            w = fr_l[k]
            t.edge("c%d_%d" % (k, i), lay(k, i), lay(k, i + 1),
                   "wall" if k == LAYERS else "interface",
                   spacing={q: v * (1.0 + (ratio - 1.0) * w)
                            for q, v in osp0.items()} if osp0 else None)
        for k in range(LAYERS):
            t.block("b%d_%d" % (k, i),
                    [lay(k, i), lay(k, i + 1), lay(k + 1, i + 1), lay(k + 1, i)])

    return te, rays, sector, body_len, \
        {"format_version": 1, "corners": t.corners, "edges": t.edges,
         "blocks": t.blocks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", type=int, default=8,
                    help="body stretches per surface")
    ap.add_argument("--wake", type=int, default=4,
                    help="stretches along the wake, each side of the cut")
    ap.add_argument("--pin-tips", type=int, default=0,
                    help="snap a station onto each of the N sharpest CONVEX "
                         "features of each surface, so a block corner meets the "
                         "feature instead of a block edge cutting across it "
                         "(section 29d)")
    ap.add_argument("--pin-concave", action="store_true",
                    help="let --pin-tips also pin CONCAVE features. Excluded at "
                         "first on the assumption that a corner declared inside "
                         "a concave feature folds the block there; section 29d "
                         "tested that and it is the opposite")
    ap.add_argument("--far-monotone", action="store_true",
                    help="keep the normal cast and repair only the stations "
                         "where it reverses, by isotonic regression -- the "
                         "minimum change that restores order (section 29c)")
    ap.add_argument("--far-by-arc", type=float, default=0.0,
                    help="blend the far-field map from the body's own NORMAL "
                         "cast (0, the default) toward ARC LENGTH (1), which is "
                         "monotone by construction; needed on a leading edge "
                         "with a concave feature (section 29)")
    ap.add_argument("--node-scale", type=float, default=1.0,
                    help="multiply every node count by this, so the SAME "
                         "blocking can be built at another grid's size; 1.0 is "
                         "what every other case here uses")
    ap.add_argument("--body", default="",
                    help="a different section to block around, as a path "
                         "relative to the repo root; the default is the clean "
                         "NACA 0012 every other case here uses")
    ap.add_argument("--arc-out", action="store_true",
                    help="keep the radial CURVING on the layers outside the "
                         "first, each launched along the tangent the one inside "
                         "it arrived with -- perpendicular at the body, arcs "
                         "further out, which is how fig6 reads (section 28)")
    ap.add_argument("--arc-out-blend", type=float, default=1.0,
                    help="how far --arc-out aims toward perpendicular at the "
                         "far field: 0 is the straight chord it replaces, 1 is "
                         "fully perpendicular and does not mesh (section 28c)")
    ap.add_argument("--chord-radials", action="store_true",
                    help="radials as straight chords between their two corners "
                         "instead of the arc that leaves perpendicular")
    ap.add_argument("--layers", type=int, default=1,
                    help="radial layers from the body out to the far field. 1 "
                         "is the single layer sections 13-16 measure; 3 is "
                         "GridPro's fig6 shape, a thin ring hugging the body "
                         "and further rings outward.")
    ap.add_argument("--h-outer", action="store_true",
                    help="make the outermost region a CARTESIAN H lattice: the "
                         "second-to-last ring becomes a box open at the outlet "
                         "and the step beyond it is axis-aligned. Needs "
                         "--layers 4 or more to keep two body-conforming rings.")
    ap.add_argument("--h-parallel", action="store_true",
                    help="with --h-outer, carry the box's inlet side STRAIGHT "
                         "forward at the same y, so the lines ahead of it are "
                         "parallel as fig6's are, instead of fanning out to "
                         "cover the whole far inlet")
    ap.add_argument("--box", nargs=2, type=float, metavar=("XLEFT", "YHALF"),
                    default=None, help="that box's extents, in chords")
    ap.add_argument("--wall-band", type=float, default=0.05,
                    help="thickness of the innermost ring, in chords; the ones "
                         "outside it grow by --layer-growth from it")
    ap.add_argument("--layer-growth", type=float, default=5.0)
    ap.add_argument("--turn-blend", type=float, default=1.0,
                    help="1 = stations at equal increments of the surface "
                         "normal (the default), 0 = at equal arc length")
    ap.add_argument("--domain", nargs=3, type=float, metavar=("XI", "XO", "YF"),
                    help="the far-field rectangle, in chords")
    ap.add_argument("--out", default="gridpro_ch.json")
    args = ap.parse_args()
    global CURVED, XI, XO, YF, TURN_BLEND, LAYERS, WALL_BAND, LAYER_GROWTH, ARC_OUT, ARC_OUT_W, FAR_BY_ARC, FAR_MONO, PIN_TIPS, PIN_CONCAVE
    global BODY, BODY_NAME, N_RADIAL, N_SURF, N_WAKE, N_WALL_LAYER, N_OUTER_LAYER
    global H_OUTER, BOX_L, BOX_Y
    CURVED = not args.chord_radials
    ARC_OUT = args.arc_out
    if args.body:
        BODY = args.body
        BODY_NAME = os.path.basename(args.body)
    ARC_OUT_W = args.arc_out_blend
    if args.node_scale != 1.0:
        k = args.node_scale
        N_RADIAL = max(3, int(round(N_RADIAL * k)))
        N_SURF = max(2, int(round(N_SURF * k)))
        N_WAKE = max(2, int(round(N_WAKE * k)))
        N_WALL_LAYER = max(3, int(round(N_WALL_LAYER * k)))
        N_OUTER_LAYER = max(3, int(round(N_OUTER_LAYER * k)))
    FAR_BY_ARC = args.far_by_arc
    FAR_MONO = args.far_monotone
    PIN_TIPS = args.pin_tips
    PIN_CONCAVE = args.pin_concave
    TURN_BLEND = args.turn_blend
    LAYERS = args.layers
    WALL_BAND, LAYER_GROWTH = args.wall_band, args.layer_growth
    global H_STRETCH
    H_OUTER = args.h_outer
    H_STRETCH = not args.h_parallel
    if args.box:
        BOX_L, BOX_Y = args.box
    if args.domain:
        XI, XO, YF = args.domain
    te, rays, sector, blen, topo = build(args.split, args.wake)
    nb = len(topo["blocks"])
    hdr = [
        "// A C/H topology for a single aerofoil -- a C-ring around the body AND",
        "// ITS WAKE, opening downstream onto a RECTANGULAR far field.",
        "// See docs/research/gridpro-blocking-method.md, section 13.",
        "//",
        "// GENERATED by make_ch.py --split %d --wake %d beside this file."
        % (args.split, args.wake),
        "// Edit that, not this.",
        "//",
        "// WHY A C AND NOT A RING. Section 12a read GridPro's own fig6 and found",
        "// its far field is NOT a radial fan against a circle: the lines wrap the",
        "// nose in a C and then run PARALLEL AND STREAMWISE, the wake leaves the",
        "// trailing edge as a straight horizontal band, and the outer boundary is",
        "// a RECTANGLE. Section 12b put a rectangle on the ring family and",
        "// measured it much WORSE, because a ring is a ring. A C-grid gives it by",
        "// construction: nothing wraps round the front, so the lines leaving the",
        "// nose point AT THE INLET.",
        "//",
        "// GRIDPRO'S: the C/H arrangement, read off fig6; and the trailing edge's",
        "// internal surfaces BISECTING THE EXTERIOR ANGLE EQUALLY -- %.4f deg" % sector,
        "// each here, from a wedge of %.4f deg, DERIVED from this body's own" % (360 - 4 * sector),
        "// two trailing-edge tangents -- which is what fixes where the two",
        "// trailing-edge radials land on the rectangle.",
        "//",
        "// OURS: the body, the domain (x %g .. %g, y +-%g in chords -- see --domain,"
        % (XI, XO, YF),
        "// count, and the fact that every block boundary here is a straight chord",
        "// or a bound polyline rather than a converged elliptic solve (10b).",
        "//",
        "// THE WAKE IS ONE CUT, WALKED TWICE. The xi walk runs from the outlet",
        "// BELOW the wake, forward along it to the trailing edge, round the body,",
        "// and back along the wake to the outlet ABOVE it -- so every wake edge is",
        "// met twice and is ONE edge both times, which is what makes it a cut and",
        "// not two coincident walls. The trailing edge is one node on five edges.",
    ]
    out = os.path.join(HERE, args.out)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(hdr) + "\n" + json.dumps(topo, indent=2) + "\n")
    print("wrote %s" % os.path.relpath(out, ROOT))
    print("  %d blocks, %d corners, %d edges"
          % (nb, len(topo["corners"]), len(topo["edges"])))
    print("  rays %.4f / %.4f / %.4f deg, four sectors of %.4f deg"
          % (rays[0], rays[1], rays[2], sector))


if __name__ == "__main__":
    main()
