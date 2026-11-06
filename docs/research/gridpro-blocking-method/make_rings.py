#!/usr/bin/env python3
"""The same GridPro blocking as ``make_tworing.py``, generalised to N CONCENTRIC
RINGS x 2K CIRCUMFERENTIAL SECTORS -- which is the arrangement the figures in
*Grid Generation: an Art or Science?* actually show.

A RESEARCH HARNESS beside ``docs/research/gridpro-blocking-method.md``, section 9.
Nothing shipped reads it; nothing in ``config/`` or ``examples/`` is written by it.
``make_tworing.py`` beside it is NOT superseded: it is the case section 8 measures
and it stays as it is.

WHY A THIRD GENERATOR. ``make_tworing.py`` hard-codes TWO rings -- body to wrap,
wrap to far field -- and refines only circumferentially. Section 9 reads the two
single-body figures in that post (`fig6.webp`, an aerofoil with icing, and
`fig5.webp`, the MDA 3-element section) and both are refined in BOTH directions:
a thin body-hugging ring cut into a dozen or more blocks chordwise, then further
rings outward, each cut the same way. So the radial direction gets a knob too.

WHAT IS STILL GRIDPRO'S, unchanged from section 8:
  * the far field is a CIRCLE OF RADIUS 3 CENTRED ON THE TRAILING EDGE, so the
    three internal surfaces are RADII of it;
  * THREE straight internal surfaces radiate from the trailing edge, BISECTING
    THE EXTERIOR ANGLE EQUALLY;
  * the ring between the body and the outer region is the Wrap step;
  * and the answer to a badly shaped region is MORE BLOCKS, not more nodes.

WHAT IS OURS: the body (GridPro's S830 is behind a sign-in wall, so the
bisection rule is run on the aerofoil this repo ships and the three angles are
DERIVED from its own trailing-edge tangents); the ring curves, which are
analytic ellipses morphing geometrically into the circle rather than a relaxed
wrap, because nothing here moves a corner; and every node count.

    python3 docs/research/gridpro-blocking-method/make_rings.py [--split K] [--rings N]
    ./run.sh -conf docs/research/gridpro-blocking-method/gridpro_rings.dat
"""

import argparse
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BODY = "examples/geometries/naca0012_cgrid.dat"
BODY_NAME = "naca0012_cgrid.dat"

FAR_R = 3.0                     # GridPro's "circle of radius 3 with center 1 0"
WRAP_C, WRAP_A, WRAP_B = (0.5, 0.0), 0.9, 0.30   # ring 1, the wrap
DS_SURF = 0.005                 # the shipped C-grid's surface clustering
N_AROUND = 96                   # intervals around the whole body
N_WALL = 33                     # nodes across the WALL ring (body -> ring 1)
N_OUT_TOTAL = 24                # intervals from ring 1 out to the circle, in all
N_WAKE = 17                     # nodes along the trailing-edge fan's angular side

FAR_C = None
BOX = False                     # a RECTANGULAR far field instead of the circle
BOX_XU, BOX_XD, BOX_Y = 3.0, 6.0, 3.0
BLEND, TAIL, FREE, FREE_WRAP = 0.5, True, False, False
CURVED = True                   # radials as arcs rather than chords
SMOOTH = True                   # ... and chained C1 instead of per-ring normal
CURVED_TAIL = True              # the tail as the ring's own curve continued
PER_LAYER = 0                   # radial intervals PER ring layer; 0 = share N_OUT_TOTAL


# -- the body --------------------------------------------------------------

def read_body(path):
    pts = [tuple(map(float, ln.split()))
           for ln in open(path, encoding="utf-8") if ln.strip()]
    i = min(range(len(pts)), key=lambda k: pts[k][0])
    return pts, pts[:i + 1], pts[i:]


def arc_table(poly):
    s = [0.0]
    for a, b in zip(poly, poly[1:]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return s, s[-1]


def at_fraction(poly, t):
    """``(point, outward unit normal)`` at normalized arc length ``t``."""
    s, total = arc_table(poly)
    target = t * total
    i = max(k for k in range(len(s) - 1) if s[k] <= target)
    a, b = poly[i], poly[i + 1]
    seg = s[i + 1] - s[i]
    u = 0.0 if seg == 0.0 else (target - s[i]) / seg
    tx, ty = b[0] - a[0], b[1] - a[1]
    n = math.hypot(tx, ty)
    return (a[0] + tx * u, a[1] + ty * u), (ty / n, -tx / n)


def te_rays(pts, nrays):
    """GridPro's rule, generalised: the exterior angle at the sharp trailing
    edge divided EQUALLY into ``nrays + 1`` sectors by ``nrays`` internal
    surfaces, returned from the upper surface round to the lower.

    The tutorial uses THREE, which is what gives its four sectors of about 90
    degrees. The figures in 'Grid Generation: an Art or Science?' show a fan of
    more links than that at the trailing edge, so the count is a knob -- but
    note that raising it makes each sector NARROWER than 90, which is the
    opposite of what the three were chosen for. Section 9 measures it.
    """
    te = pts[0]
    up = math.degrees(math.atan2(pts[1][1] - te[1], pts[1][0] - te[0]))
    lo = math.degrees(math.atan2(pts[-2][1] - te[1], pts[-2][0] - te[0]))
    ext = (up - lo) % 360.0
    q = ext / (nrays + 1)
    return te, [up - q * (k + 1) for k in range(nrays)], q


# -- the ring family -------------------------------------------------------

def ring_geom(k, nrings):
    """``(centre, a, b)`` of ring ``k`` (1 = the wrap, ``nrings`` = the circle).

    The centre moves LINEARLY and the two semi-axes GEOMETRICALLY, so the rings
    grow the way a boundary layer does rather than jumping from a thin wrap to a
    fat blob in one step. At ``k == nrings`` it is EXACTLY the far-field circle,
    so the outer boundary is not an approximation of GridPro's -- it is it.
    """
    t = 0.0 if nrings == 1 else (k - 1) / (nrings - 1)
    c = (WRAP_C[0] + (FAR_C[0] - WRAP_C[0]) * t,
         WRAP_C[1] + (FAR_C[1] - WRAP_C[1]) * t)
    return c, WRAP_A * (FAR_R / WRAP_A) ** t, WRAP_B * (FAR_R / WRAP_B) ** t


def ell_point(g, deg):
    c, a, b = g
    r = math.radians(deg)
    return (c[0] + a * math.cos(r), c[1] + b * math.sin(r))


def ell_param(g, q):
    c, a, b = g
    return math.degrees(math.atan2((q[1] - c[1]) / b, (q[0] - c[0]) / a)) % 360.0


def ell_normal(g, deg):
    c, a, b = g
    r = math.radians(deg)
    nx, ny = math.cos(r) / a, math.sin(r) / b
    n = math.hypot(nx, ny)
    return (nx / n, ny / n)


def ell_arc(g, d0, d1, n=400):
    span = (d1 - d0) % 360.0
    tot, prev = 0.0, ell_point(g, d0)
    for k in range(1, n + 1):
        cur = ell_point(g, d0 + span * k / n)
        tot += math.hypot(cur[0] - prev[0], cur[1] - prev[1])
        prev = cur
    return tot


def hit_ellipse(g, p, d):
    c, a, b = g
    px, py = p[0] - c[0], p[1] - c[1]
    A = (d[0] / a) ** 2 + (d[1] / b) ** 2
    B = 2 * (px * d[0] / a ** 2 + py * d[1] / b ** 2)
    C = (px / a) ** 2 + (py / b) ** 2 - 1.0
    t = (-B + math.sqrt(B * B - 4 * A * C)) / (2 * A)
    return (p[0] + t * d[0], p[1] + t * d[1])


def hit_circle(p, d):
    px, py = p[0] - FAR_C[0], p[1] - FAR_C[1]
    b = d[0] * px + d[1] * py
    t = -b + math.sqrt(b * b - (px * px + py * py) + FAR_R * FAR_R)
    return (p[0] + t * d[0], p[1] + t * d[1])


def _free(k, nrings):
    """Is ring ``k`` left as straight chords between its own corners?

    A DECLARED SHAPE -- an edge that follows a curve or IS one -- is FROZEN by
    the Winslow smoother (`.claude/rules/mesher-smoothing.md`), so every
    intermediate ring declared as an ellipse pins a whole circle of interior
    nodes that GridPro's own relaxation would be free to move. ``--free-rings``
    drops the declaration on rings 2 .. N-1 and ``--free-wrap`` on ring 1 as
    well, so the measurement can be made rather than argued. Ring N is the
    domain boundary and always keeps its declaration.

    A freed ring starts life as the POLYGON of straight chords between its own
    corners and is then free to be relaxed into whatever shape the elliptic
    solve wants -- which is the nearest this repo gets to GridPro's own
    "straight links in, curved block boundaries out"."""
    if k >= nrings:
        return False                 # the far field is the domain boundary
    return (FREE and k > 1) or (FREE_WRAP and k >= 1)


def arc_exit_tangent(cv, p, q):
    """The unit tangent at ``q`` of the edge ``p -> q`` declared with ``cv``.

    This is what makes a station's radials ONE SMOOTH CURVE instead of a stack
    of arcs with a kink at every ring: the next layer is built to LEAVE along
    the tangent the previous layer ARRIVED with, so the chain is C1 by
    construction. Launching every layer along its own ring's normal instead --
    which is what shipped first -- guarantees a kink unless the two happen to
    agree, and section 11 shows what that looked like.
    """
    if cv is None:
        d = (q[0] - p[0], q[1] - p[1])
        n = math.hypot(*d)
        return (d[0] / n, d[1] / n)
    c = cv["centre"]
    rx, ry = q[0] - c[0], q[1] - c[1]
    n = math.hypot(rx, ry)
    if cv.get("sweep", "ccw") == "ccw":
        return (-ry / n, rx / n)
    return (ry / n, -rx / n)


def box_point(deg):
    """Where the ray from the far-field centre at ``deg`` meets the BOX.

    GridPro's two single-body figures do NOT put a radial fan out to a circle:
    their far field is a RECTANGLE and the grid becomes a streamwise-aligned
    lattice against it -- horizontal lines upstream and above, a straight wake
    band downstream. A ring that IS the rectangle produces that by itself: its
    "circumferential" lines are nested boxes, so near the top they are
    horizontal and near the outlet they are vertical.
    """
    r = math.radians(deg)
    cx, cy = math.cos(r), math.sin(r)
    xs = (BOX_XD if cx > 0 else BOX_XU) / abs(cx) if abs(cx) > 1e-12 else 1e30
    ys = BOX_Y / abs(cy) if abs(cy) > 1e-12 else 1e30
    t = min(xs, ys)
    return (FAR_C[0] + t * cx, FAR_C[1] + t * cy)


def far_point(deg):
    return box_point(deg) if BOX else on_circle_pt(deg)


def box_corner_angles():
    """The four corner directions of the box, as angles about its centre."""
    return [math.degrees(math.atan2(sy * BOX_Y, sx * (BOX_XD if sx > 0 else BOX_XU)))
            for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]


def ell_tangent(g, deg):
    """The ellipse's own COUNTER-CLOCKWISE unit tangent at parameter ``deg``."""
    c, a, b = g
    r = math.radians(deg)
    tx, ty = -a * math.sin(r), b * math.cos(r)
    n = math.hypot(tx, ty)
    return (tx / n, ty / n)


def arc_tangent_at(p, tdir, q):
    """The `curve` for an edge ``p -> q`` that LEAVES ``p`` along ``tdir``.

    A circular arc through two points with a prescribed tangent at one of them
    is unique, so this is DERIVED and not a chosen curvature: the centre sits on
    the normal at ``p``, at ``r = |d|^2 / (2 d.n)``. When ``q`` already lies
    along ``tdir`` the radius runs away and the honest answer is the straight
    chord, which is what ``None`` asks for.

    This is the only way a block boundary can be CURVED in this repo. GridPro
    gets its curved boundaries from a converged elliptic solve over straight
    wireframe links (section 1a); here a boundary is either a straight chord, a
    declared shape, or whatever the smoother leaves it -- and section 10
    measures that the smoother diverges long before it curves anything.
    """
    d = (q[0] - p[0], q[1] - p[1])
    n = (-tdir[1], tdir[0])
    dn = d[0] * n[0] + d[1] * n[1]
    dd = d[0] * d[0] + d[1] * d[1]
    if abs(dn) < 1e-12 or dd == 0.0:
        return None
    r = dd / (2.0 * dn)
    c = (p[0] + r * n[0], p[1] + r * n[1])
    if abs(r) > 1e4 * math.sqrt(dd):
        return None                     # indistinguishable from the chord
    a0 = math.atan2(p[1] - c[1], p[0] - c[0])
    a1 = math.atan2(q[1] - c[1], q[0] - c[0])
    ccw = (a1 - a0) % (2 * math.pi) <= math.pi
    return {"kind": "arc", "centre": [c[0], c[1]], "r": abs(r),
            "sweep": "ccw" if ccw else "cw"}


def curve_of(g):
    """A ring's own `curve` declaration. A circle is the a == b case and is
    written as an `arc`, which is the same shape through the same code path."""
    c, a, b = g
    if abs(a - b) < 1e-12:
        return {"kind": "arc", "centre": [c[0], c[1]], "r": a}
    return {"kind": "ellipse", "centre": [c[0], c[1]], "a": a, "b": b}


# -- the document ----------------------------------------------------------

class Topo(object):
    def __init__(self):
        self.pos, self.corners, self.edges, self.blocks, self.ends = \
            {}, [], [], [], {}

    def free(self, cid, xy):
        self.pos[cid] = (xy[0], xy[1])
        self.corners.append({"id": cid, "kind": "free", "xy": [xy[0], xy[1]]})

    def onbody(self, cid, seg, t, xy):
        self.pos[cid] = (xy[0], xy[1])
        self.corners.append({"id": cid, "kind": "on_geometry",
                             "geom": BODY_NAME, "seg": seg, "t": t})

    def edge(self, eid, a, b, kind, **kw):
        e = {"id": eid, "corners": [a, b], "kind": kind}
        e.update({k: v for k, v in kw.items() if v})
        self.edges.append(e)
        self.ends[eid] = (a, b)
        return eid

    def block(self, bid, ring):
        """``ring`` is the four corners in any rotation; the walk is made
        counter-clockwise here and then rotated until its first side is an edge
        DECLARED in that direction, which is what a block's south must be."""
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


def build(split, nrings, nrays):
    global FAR_C
    pts, seg_up, seg_lo = read_body(os.path.join(ROOT, BODY))
    te, rays, sector = te_rays(pts, nrays)
    wake_i = nrays // 2                     # the middle ray is the wake cut
    FAR_C = te                   # the circle is centred ON the trailing edge
    g1 = ring_geom(1, nrings)
    t = Topo()

    # ---- the body corners ------------------------------------------------
    fr = [k / split for k in range(1, split)]
    t.onbody("te", 0, 0.0, te)
    t.onbody("le", 1, 0.0, at_fraction(seg_lo, 0.0)[0])
    rd = {}
    ray_ids = ["R%d" % k for k in range(nrays)]
    for k, a in enumerate(rays):
        rd[ray_ids[k]] = (te, (math.cos(math.radians(a)),
                               math.sin(math.radians(a))))
    for k, f in enumerate(fr):
        for seg, poly, nm in ((0, seg_up, "u%d" % k), (1, seg_lo, "l%d" % k)):
            p, n = at_fraction(poly, f)
            t.onbody(nm, seg, f, p)
            rd[nm] = (p, n)
    rd["le"] = (t.pos["le"], (-1.0, 0.0))

    # ---- ring 1: where the body's own outward NORMAL arrives -------------
    nom = {}
    for key, (p, d) in rd.items():
        nom[key] = ell_param(g1, hit_ellipse(g1, p, d))
    tail_ids = ["M%d" % k for k in range(nrays - 1)]
    for k, key in enumerate(tail_ids):      # one per pair of consecutive rays
        a, b = ray_ids[k + 1], ray_ids[k]   # ccw: the lower ray comes first
        nom[key] = (nom[a] + ((nom[b] - nom[a]) % 360.0) / 2.0) % 360.0

    # ---- the walks -------------------------------------------------------
    up_body = ["te"] + ["u%d" % k for k in range(split - 1)] + ["le"]
    lo_body = ["le"] + ["l%d" % k for k in range(split - 1)] + ["te"]
    # THE WALK IS A SORT, not a hand-built list: every station sits on ring 1
    # and its own parameter there is its position round the ring, so ordering
    # them by that parameter IS the counter-clockwise walk, whatever the ray
    # count. Started at the wake so the aft sectors read first.
    stations = ray_ids + tail_ids + up_body[1:-1] + ["le"] \
        + ["l%d" % k for k in range(split - 1)]
    base = nom[ray_ids[wake_i]]
    walk = sorted(stations, key=lambda s: (nom[s] - base) % 360.0)
    nwalk = len(walk)

    # AND THE SORT IS ALSO THE CHECK THAT THE FAN FITS. A trailing-edge ray and
    # a body station both land on ring 1, and the fan only works while every ray
    # lands AFT of every body station. Equal bisection of a 343-degree exterior
    # angle puts the 4th and 5th rays at +-114 deg, pointing back OVER the body,
    # and their ring landings then interleave with the body's own -- which is
    # not a worse mesh, it is not a mesh: the block between two interleaved
    # stations has no edge. Refused by name rather than discovered as a missing
    # edge three functions later.
    fanset = set(ray_ids) | set(tail_ids)
    runs = []
    for s in walk:
        tag = s in fanset
        if not runs or runs[-1][0] != tag:
            runs.append([tag, []])
        runs[-1][1].append(s)
    if len(runs) > 1 and runs[0][0] == runs[-1][0]:     # the walk is CYCLIC
        runs[0][1] = runs[-1][1] + runs[0][1]
        runs.pop()
    if len(runs) != 2:
        raise SystemExit(
            "--te-rays %d does not fit this body: dividing its %.3f deg exterior "
            "angle equally puts a ray at %.3f deg, which lands on the ring "
            "INTERLEAVED with the body's own stations (%s). GridPro's rule is "
            "equal bisection, and on a thin section that caps the fan -- the "
            "tutorial's THREE is not a small number, it is the largest that "
            "fits. Use --te-rays 3."
            % (len(rays), (len(rays) + 1) * sector, rays[0],
               " ".join(walk)))

    # ---- the circle: anchored, evenly shared, then blended ---------------
    anchor = {"le": 180.0}
    for k, a in enumerate(rays):
        anchor[ray_ids[k]] = a + (360.0 if a < rays[wake_i] else 0.0)
    far = {}
    idx = [i for i, k in enumerate(walk) if k in anchor]
    for a, b in zip(idx, idx[1:] + [idx[0] + nwalk]):
        lo = anchor[walk[a]]
        hi = anchor[walk[b % nwalk]] + (360.0 if b >= nwalk else 0.0)
        for j in range(b - a):
            far[walk[(a + j) % nwalk]] = lo + (hi - lo) * j / (b - a)
    if BOX:
        # THE BOX'S FOUR CORNERS MUST BE STATIONS, or the ring side spanning one
        # is a chord that chamfers it off. Rather than add stations -- which the
        # wall layer could not pair with a body stretch -- the four nearest
        # existing ones are PINNED to the corner directions and the rest spread
        # evenly between all eight anchors.
        for ca in box_corner_angles():
            free = [k for k in walk if k not in anchor]
            best = min(free, key=lambda k: abs((far[k] - ca + 180.0) % 360.0 - 180.0))
            anchor[best] = ca + 360.0 * round((far[best] - ca) / 360.0)
        idx = [i for i, k in enumerate(walk) if k in anchor]
        for a, b in zip(idx, idx[1:] + [idx[0] + nwalk]):
            lo = anchor[walk[a]]
            hi = anchor[walk[b % nwalk]] + (360.0 if b >= nwalk else 0.0)
            for j in range(b - a):
                far[walk[(a + j) % nwalk]] = lo + (hi - lo) * j / (b - a)
    # ... and then BLENDED toward where the ring's own outward normal lands.
    # ONLY ON THE CIRCLE. With a box the blend is measured against a boundary
    # that is not there, and it reorders the stations: it moved one of them
    # past its two neighbours, crossing their radials, and the run came back
    # with 216 inverted cells. On a box the even share between anchors is also
    # the right answer, because a box side wants its stations spread along it.
    for key in (() if BOX else list(far)):
        if key in anchor:
            continue
        q = hit_circle(ell_point(g1, nom[key]), ell_normal(g1, nom[key]))
        nat = math.degrees(math.atan2(q[1] - FAR_C[1], q[0] - FAR_C[0]))
        while nat - far[key] > 180.0:
            nat -= 360.0
        while far[key] - nat > 180.0:
            nat += 360.0
        far[key] = far[key] + BLEND * (nat - far[key])

    # ---- every ring's parameter at every station -------------------------
    # Unwrapped monotonically along the walk, so interpolating between ring 1's
    # parameter and the circle's angle can never reorder the stations.
    def unwrap(d):
        out, prev = {}, None
        for key in walk:
            v = d[key]
            while prev is not None and v < prev:
                v += 360.0
            out[key], prev = v, v
        return out
    nom, far = unwrap(nom), unwrap(far)
    par = {1: dict(nom), nrings: dict(far)}
    for k in range(2, nrings):
        w = (k - 1) / (nrings - 1)
        par[k] = {s: nom[s] + (far[s] - nom[s]) * w for s in walk}

    # ---- the corners on every ring ---------------------------------------
    # THE TWO TAIL CORNERS, AND WHY THEY ARE NOT ON RING 1's CURVE. Put on the
    # ellipse they are a corner declared in the middle of a SMOOTH curve, so the
    # trailing-edge wedge meets itself there at 178.5 degrees -- GridPro's own
    # rule "two sides of one block cannot be on one surface", hit from inside
    # (section 8e). Ring 1 therefore gets a TAIL: each tail corner is where the
    # perpendicular to the wake meets the perpendicular to that sector's own
    # internal surface. On rings 2 and out the station is an ordinary one, since
    # there the two arcs meeting at it belong to DIFFERENT blocks.
    tail = {}
    if TAIL:
        for k, key in enumerate(tail_ids):
            pw = ell_point(g1, nom[ray_ids[k + 1]])
            po = ell_point(g1, nom[ray_ids[k]])
            n1 = (-math.sin(math.radians(rays[k + 1])),
                  math.cos(math.radians(rays[k + 1])))
            n2 = (-math.sin(math.radians(rays[k])), math.cos(math.radians(rays[k])))
            det = n1[0] * (-n2[1]) - n1[1] * (-n2[0])
            rhs = (po[0] - pw[0], po[1] - pw[1])
            u = (rhs[0] * (-n2[1]) - rhs[1] * (-n2[0])) / det
            tail[key] = (pw[0] + u * n1[0], pw[1] + u * n1[1])
    def ring_pt(k, st):
        if k == 1 and st in tail:
            return tail[st]
        if not BOX:
            return ell_point(ring_geom(k, nrings), par[k][st])
        if k == 1:
            return ell_point(g1, nom[st])
        if k == nrings:
            return far_point(far[st])
        # Between the wrap and the box, blended geometrically. NOT a nested box
        # with an axis-aligned mapping, which is what a Cartesian H field would
        # need and which section 12 records as attempted and abandoned: the
        # inner box has to clear the wrap ellipse upstream AND keep the far
        # field's aspect, and on this body those two cannot both hold -- the box
        # cuts inside the ellipse ahead of the nose and the layer folds.
        w = (3.0 ** (k - 1) - 1.0) / (3.0 ** (nrings - 1) - 1.0)
        a, b = ring_pt(1, st), far_point(far[st])
        return (a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w)
    for k in range(1, nrings + 1):
        for s in walk:
            t.free("R%d_%s" % (k, s), ring_pt(k, s))

    # ---- the radials ------------------------------------------------------
    # Layer 0 is the WALL layer and every one of its radials clusters at the
    # body. The three at the trailing edge are GridPro's internal surfaces.
    wall = {"wall_ends": "start"}
    for k, rid in enumerate(ray_ids):
        if k == wake_i:
            t.edge("r0_" + rid, "te", "R1_" + rid, "cut", count=N_WAKE,
                   spacing={"ds_start": DS_SURF})
        else:
            t.edge("r0_" + rid, "te", "R1_" + rid, "interface",
                   count=N_WALL if k == 0 else None, spacing=wall)
    for cid in ["le"] + ["u%d" % k for k in range(split - 1)] \
            + ["l%d" % k for k in range(split - 1)]:
        t.edge("r0_" + cid, cid, "R1_" + cid, "interface", spacing=wall)
    nout = PER_LAYER if PER_LAYER else max(1, N_OUT_TOTAL // max(1, nrings - 1))
    # The chain is walked OUTWARD per station so each layer can be launched
    # along the tangent the one inside it arrived with (see arc_exit_tangent).
    tin = {}
    for st in walk:
        inner = "te" if st in ray_ids else (st if st in rd else None)
        if inner is not None:
            tin[st] = arc_exit_tangent(None, t.pos[inner], t.pos["R1_" + st])
    for k in range(1, nrings):
        g = ring_geom(k, nrings)
        for i, st in enumerate(walk):
            a, b = "R%d_%s" % (k, st), "R%d_%s" % (k + 1, st)
            cv = None
            if CURVED and not (k == 1 and st in tail):
                lead = tin[st] if (SMOOTH and st in tin) \
                    else ell_normal(g, par[k][st])
                cv = arc_tangent_at(t.pos[a], lead, t.pos[b])
            if st in tin:
                tin[st] = arc_exit_tangent(cv, t.pos[a], t.pos[b])
            t.edge("r%d_%s" % (k, st), a, b, "interface",
                   count=(nout + 1) if i == 0 else None, curve=cv)

    # ---- the body sides, and the arc on every ring facing them -----------
    nb = N_AROUND // (2 * split)
    def surface(bodylist, seg, poly, side):
        for i in range(split):
            a, b = bodylist[i], bodylist[i + 1]
            ka = ray_ids[0] if a == "te" else a
            kb = ray_ids[-1] if b == "te" else b
            sp = {}
            if a in ("te", "le"):
                sp["ds_start"] = DS_SURF
            if b in ("te", "le"):
                sp["ds_end"] = DS_SURF
            blen = arc_table(poly)[1] / split
            t.edge("af_%s_%d" % (side, i), a, b, "wall", count=nb + 1,
                   binding={"geom": BODY_NAME, "seg": seg}, spacing=sp)
            # Every ring's arc carries the body stretch's clustering SCALED by
            # its own arc length, so the whole radial family shares one
            # normalized distribution. DERIVED, not tuned.
            for k in range(1, nrings + 1):
                g = ring_geom(k, nrings)
                rl = ell_arc(g, par[k][ka], par[k][kb]) if not BOX else \
                    math.hypot(*(x - y for x, y in
                                 zip(t.pos["R%d_%s" % (k, kb)],
                                     t.pos["R%d_%s" % (k, ka)])))
                t.edge("c%d_%s_%d" % (k, side, i), "R%d_%s" % (k, ka),
                       "R%d_%s" % (k, kb),
                       "wall" if k == nrings else "interface",
                       curve=None if (_free(k, nrings) or (BOX and k > 1))
                       else curve_of(g),
                       spacing={q: v * rl / blen for q, v in sp.items()})

    surface(up_body, 0, seg_up, "up")
    surface(lo_body, 1, seg_lo, "lo")

    # ---- the trailing-edge fan's own arc on every ring -------------------
    fan = []
    for j, mid in enumerate(tail_ids):
        fan += [("f%d_i" % j, ray_ids[j + 1], mid, mid, ray_ids[j + 1]),
                ("f%d_o" % j, mid, ray_ids[j], mid, ray_ids[j])]
    for nm, lo, hi, mid, ringend in fan:
        for k in range(1, nrings + 1):
            g = ring_geom(k, nrings)
            cv = None if (_free(k, nrings) or (BOX and k > 1)) else curve_of(g)
            if k == 1 and TAIL:
                # THE TAIL IS THE RING'S OWN CURVE CONTINUED, not a chord.
                # Each of its two sides leaves ring 1 along the ELLIPSE's own
                # tangent and ends at the tail corner, so the ring stays smooth
                # where the tail joins it and the only corner left is the one
                # the wedge needs for its fourth side. Straight chords were
                # what shipped first; section 10 measures what the curve buys.
                cv = None
                if CURVED_TAIL:
                    pe = ell_point(g, nom[ringend])
                    tg = ell_tangent(g, nom[ringend])
                    if ringend == hi:            # the edge runs INTO the ring
                        tg = (-tg[0], -tg[1])
                    cv = arc_tangent_at(pe, tg, tail[mid])
                    if cv and ringend == hi:     # ... so it is declared reversed
                        cv["sweep"] = "cw" if cv["sweep"] == "ccw" else "ccw"
            t.edge("c%d_%s" % (k, nm), "R%d_%s" % (k, lo), "R%d_%s" % (k, hi),
                   "wall" if k == nrings else "interface", curve=cv)

    # ---- the blocks -------------------------------------------------------
    for i in range(split):                       # the wall layer
        a, b = up_body[i], up_body[i + 1]
        t.block("b_w_up_%d" % i, [a, b, "R1_" + ("le" if b == "le" else b),
                                  "R1_" + (ray_ids[0] if a == "te" else a)])
        a, b = lo_body[i], lo_body[i + 1]
        t.block("b_w_lo_%d" % i, [a, b, "R1_" + (ray_ids[-1] if b == "te" else b),
                                  "R1_" + ("le" if a == "le" else a)])
    for j, mid in enumerate(tail_ids):          # the trailing-edge fan
        t.block("b_w_fan_%d" % j, ["te", "R1_" + ray_ids[j + 1], "R1_" + mid,
                                   "R1_" + ray_ids[j]])
    for k in range(1, nrings):                   # every ring layer outward
        for i, s in enumerate(walk):
            nx = walk[(i + 1) % nwalk]
            t.block("b_r%d_%d" % (k, i),
                    ["R%d_%s" % (k, s), "R%d_%s" % (k, nx),
                     "R%d_%s" % (k + 1, nx), "R%d_%s" % (k + 1, s)])

    return te, rays, sector, nom, far, \
        {"format_version": 1, "corners": t.corners, "edges": t.edges,
         "blocks": t.blocks}


def main():
    global BLEND, TAIL, FREE, FREE_WRAP, PER_LAYER, CURVED, CURVED_TAIL, SMOOTH, BOX
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", type=int, default=8,
                    help="body sides per surface; 2K sectors around the body")
    ap.add_argument("--rings", type=int, default=2,
                    help="concentric rings. TWO is what GridPro's own fig5 "
                         "shows once it is zoomed: a dense near-body rosette "
                         "and ONE layer of sectors spanning out to the far "
                         "field, with no concentric seam cutting across them.")
    ap.add_argument("--te-rays", type=int, default=3,
                    help="internal surfaces at the trailing edge; must be ODD "
                         "so one of them is the wake. 3 is the tutorial's.")
    ap.add_argument("--blend", type=float, default=0.5,
                    help="0 = circle corners evenly spread, 1 = where the "
                         "ring's own outward normal lands")
    ap.add_argument("--no-tail", action="store_true",
                    help="put the two tail corners ON ring 1 instead -- the "
                         "placement section 8e rejected, kept re-runnable")
    ap.add_argument("--box", action="store_true",
                    help="a RECTANGULAR far field, with the rings morphing from "
                         "the wrap ellipse out to it, instead of GridPro's "
                         "tutorial circle. This is what its two single-body "
                         "FIGURES show: a streamwise-aligned lattice against a "
                         "rectangle, not a radial fan against a circle.")
    ap.add_argument("--ring-normal-radials", action="store_true",
                    help="launch EVERY layer's radial along its own ring's "
                         "normal, which kinks the partition at each ring. The "
                         "default chains them C1 -- a layer leaves along the "
                         "tangent the one inside it arrived with -- so the "
                         "partition is ONE curve from body to far field.")
    ap.add_argument("--chord-radials", action="store_true",
                    help="outer radials as STRAIGHT CHORDS between their two "
                         "corners. The default is the arc that leaves the "
                         "inner ring along that ring's own normal; section 10 "
                         "measures what the chord costs.")
    ap.add_argument("--chord-tail", action="store_true",
                    help="the trailing-edge tail as two STRAIGHT CHORDS. The "
                         "default is the ring's own curve continued -- each "
                         "side leaves ring 1 along the ellipse's tangent.")
    ap.add_argument("--free-wrap", action="store_true",
                    help="as --free-rings, and free ring 1 (the wrap) too")
    ap.add_argument("--per-layer", type=int, default=0,
                    help="radial intervals in EACH ring layer; the default "
                         "shares one budget over them, so more rings cost "
                         "nothing in cells")
    ap.add_argument("--free-rings", action="store_true",
                    help="declare rings 2..N-1 as straight chords, so the "
                         "smoother may move them -- see _free()")
    ap.add_argument("--out", default="gridpro_rings.json")
    args = ap.parse_args()
    BLEND, TAIL, FREE = args.blend, not args.no_tail, args.free_rings
    FREE_WRAP = args.free_wrap
    CURVED, CURVED_TAIL = not args.chord_radials, not args.chord_tail
    SMOOTH = not args.ring_normal_radials
    BOX = args.box
    PER_LAYER = args.per_layer
    if args.rings < 2 or args.split < 1:
        raise SystemExit("--rings must be >= 2 and --split >= 1")
    if args.te_rays < 3 or args.te_rays % 2 == 0:
        raise SystemExit("--te-rays must be odd and >= 3, so one is the wake")

    te, rays, sector, nom, far, topo = build(args.split, args.rings,
                                             args.te_rays)
    nb = len(topo["blocks"])
    hdr = [
        "// GridPro's aerofoil blocking as its own figures arrange it:",
        "// %d CONCENTRIC RINGS x %d CIRCUMFERENTIAL SECTORS, %d blocks."
        % (args.rings, 2 * args.split, nb),
        "// See docs/research/gridpro-blocking-method.md, section 9.",
        "//",
        "// GENERATED by make_rings.py --split %d --rings %d beside this file."
        % (args.split, args.rings),
        "// Edit that, not this.",
        "//",
        "// GRIDPRO'S, and unchanged from section 8: a far-field CIRCLE of radius",
        "// %g centred ON THE TRAILING EDGE, so the %d straight internal"
        % (FAR_R, args.te_rays),
        "// surfaces radiating from the trailing edge are RADII of it; and those",
        "// %d BISECT THE EXTERIOR ANGLE EQUALLY -- here %.4f deg each,"
        % (args.te_rays, sector),
        "// from a wedge of %.4f deg, DERIVED from this body's own two" % (360 - 4 * sector),
        "// trailing-edge tangents rather than written down.",
        "//",
        "// GRIDPRO'S, and what this file adds over make_tworing.py: the two",
        "// single-body figures in 'Grid Generation: an Art or Science?' are",
        "// refined in BOTH directions -- a thin body-hugging ring cut into a",
        "// dozen or more blocks chordwise, then further rings outward, each cut",
        "// the same way. Section 8f measured that circumferential subdivision",
        "// alone halves the MEAN and does not move the WORST corner at all.",
        "//",
        "// OURS: the body, because GridPro's S830 is behind a sign-in wall; the",
        "// ring curves, which are analytic ellipses morphing GEOMETRICALLY into",
        "// the circle (at the last ring it IS the circle, exactly) rather than a",
        "// relaxed wrap, because nothing in this repo moves a corner once it is",
        "// declared; and every node count. Every radial but the three at the",
        "// trailing edge leaves along the BODY'S OWN OUTWARD NORMAL, and each",
        "// ring's arc carries its body stretch's clustering scaled by its own",
        "// arc length.",
    ]
    out = os.path.join(HERE, args.out)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(hdr) + "\n" + json.dumps(topo, indent=2) + "\n")
    print("wrote %s" % os.path.relpath(out, ROOT))
    print("  %d rings x %d sectors -> %d blocks, %d corners, %d edges"
          % (args.rings, 2 * args.split, nb, len(topo["corners"]),
             len(topo["edges"])))
    print("  %d rays at %s deg, %d sectors of %.4f deg"
          % (len(rays), " / ".join("%.3f" % a for a in rays),
             len(rays) + 1, sector))
    for k in range(1, args.rings + 1):
        c, a, b = ring_geom(k, args.rings)
        print("  ring %d: centre (%.4f, %.4f)  a %.4f  b %.4f" % (k, c[0], c[1], a, b))


if __name__ == "__main__":
    main()
