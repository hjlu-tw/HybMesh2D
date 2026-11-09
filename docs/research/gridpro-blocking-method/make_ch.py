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
                        arc_tangent_at)

BODY = "examples/geometries/naca0012_cgrid.dat"
BODY_NAME = "naca0012_cgrid.dat"

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
LAYERS = 1                      # radial layers from the body out to the far field
LAYER_GROWTH = 5.0              # how fast those bands thicken outward
WALL_BAND = 0.05                # the innermost band's thickness, in chords
BL_FIRST = 0.001                # BL_INITIAL_THICKNESS, as the .dat declares it
TURN_BLEND = 1.0                # 1 = equal normal turn, 0 = equal arc length               # how fast the wake's own stations spread aft
N_RADIAL = 49                   # nodes from the body/wake out to the far field
N_SURF = 40                   # intervals along ONE surface
N_WAKE = 34                   # intervals along the wake, per side
N_WALL_LAYER = 25             # nodes across the innermost layer, when LAYERS > 1
N_OUTER_LAYER = 17            # ... and across each layer outside it


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
    fu = mix(seg_up)                            # te -> le along seg 0
    fl = mix(seg_lo)                            # le -> te along seg 1
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
    for i in range(len(walk) - 1):                       # it must stay increasing
        if far_s[i + 1] <= far_s[i]:
            raise SystemExit("the far-field map is not monotone at walk entry "
                             "%d; two radials would cross" % i)
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
        for k in range(LAYERS):
            n0 = N_RADIAL if LAYERS == 1 else (N_WALL_LAYER if k == 0 else
                                               N_OUTER_LAYER)
            spk = sp if k == 0 else ({"ds_start": prev_last} if prev_last else None)
            t.edge("r%d_%d" % (k, i), lay(k, i), lay(k + 1, i),
                   "wall" if last else "interface",   # every layer of the
                   # end radials lies ON the outlet plane, so every one of them
                   # bounds a single block
                   count=n0 if i == 0 else None,
                   spacing=spk,
                   curve=cv if k == 0 else None)
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
    ap.add_argument("--chord-radials", action="store_true",
                    help="radials as straight chords between their two corners "
                         "instead of the arc that leaves perpendicular")
    ap.add_argument("--layers", type=int, default=1,
                    help="radial layers from the body out to the far field. 1 "
                         "is the single layer sections 13-16 measure; 3 is "
                         "GridPro's fig6 shape, a thin ring hugging the body "
                         "and further rings outward.")
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
    global CURVED, XI, XO, YF, TURN_BLEND, LAYERS, WALL_BAND, LAYER_GROWTH
    CURVED = not args.chord_radials
    TURN_BLEND = args.turn_blend
    LAYERS = args.layers
    WALL_BAND, LAYER_GROWTH = args.wall_band, args.layer_growth
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
