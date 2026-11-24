#!/usr/bin/env python3
"""GridPro's aerofoil blocking, rebuilt the way GridPro builds it: a WRAPPED
INNER RING around the body, an outer ring out to the circle, and the trailing
edge's own fan between the three internal surfaces.

A RESEARCH HARNESS beside ``docs/research/gridpro-blocking-method.md``. Nothing
shipped reads it; nothing in ``config/`` or ``examples/`` is written by it.

WHY A SECOND SHAPE, when ``make_topology.py`` already meshes. That one puts the
body and the far-field circle on OPPOSITE SIDES OF ONE BLOCK, and the circle is
centred ON THE TRAILING EDGE -- so seen from the centre the whole body is a thin
wedge of directions, and no distribution of nodes along those two sides makes
the grid line between them normal to the body. Measured: 87.0 deg worst
non-orthogonality taking the far field proportional to the body's arc length,
and the body's own normals cast outward land 94 deg of the upper surface into
10 deg of circle. That is not a tuning failure, it is the mapping; GridPro's
answer to it is the step its tutorial calls WRAP (O Grid), and this file is that
step.

WHAT IS GRIDPRO'S HERE:
  * the far field is a CIRCLE OF RADIUS 3 CENTRED ON THE TRAILING EDGE;
  * THREE straight internal surfaces radiate from the trailing edge, BISECTING
    THE EXTERIOR ANGLE EQUALLY -- four regions meet there, each near 90 deg;
  * a WRAPPED RING between the body and the outer region;
  * FOUR corners on the aerofoil and EIGHT on the circle, against the
    tutorial's four and "about nine";
  * and it comes out at FOURTEEN BLOCKS, which is the tutorial's own count.

WHAT IS OURS: the body (GridPro's S830 is behind a sign-in wall, so the rule is
run on the aerofoil this repo ships, and the three ray directions are DERIVED
from its own trailing-edge tangents); the ring curve, which is an analytic
ellipse rather than a relaxed wrap, because nothing here moves a corner; and
every node count.

    python3 docs/research/gridpro-blocking-method/make_tworing.py
    ./run.sh -conf docs/research/gridpro-blocking-method/gridpro_tworing.dat
"""

import argparse
import sys
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BODY = "examples/geometries/naca0012_cgrid.dat"
BODY_NAME = "naca0012_cgrid.dat"

FAR_C, FAR_R = None, 3.0        # GridPro's "circle of radius 3 with center 1 0"
RING_C, RING_A, RING_B = (0.5, 0.0), 0.9, 0.30
TAIL = True                     # see the m2/m3 note in build()
BLEND = 0.5                     # weight on the ring normal for a circle corner
DS_SURF = 0.005                 # the shipped C-grid's surface clustering
N_BODY = 25                     # nodes along one quarter of the body
N_INNER = 33                    # nodes across the inner ring (the wall-normal class)
N_OUTER = 25                    # nodes across the outer ring
N_WAKE = 17                     # nodes along the trailing-edge fan's angular side


# -- geometry helpers ------------------------------------------------------

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


def te_rays(pts):
    """GridPro's rule: the exterior angle at the sharp trailing edge, in four."""
    te = pts[0]
    up = math.degrees(math.atan2(pts[1][1] - te[1], pts[1][0] - te[0]))
    lo = math.degrees(math.atan2(pts[-2][1] - te[1], pts[-2][0] - te[0]))
    ext = (up - lo) % 360.0
    q = ext / 4.0
    return te, [up - q, up - 2 * q, up - 3 * q], q


def hit_ellipse(p, d):
    """Where the ray ``p + t d`` (t > 0) meets the ring ellipse."""
    px, py = p[0] - RING_C[0], p[1] - RING_C[1]
    A = (d[0] / RING_A) ** 2 + (d[1] / RING_B) ** 2
    B = 2 * (px * d[0] / RING_A ** 2 + py * d[1] / RING_B ** 2)
    C = (px / RING_A) ** 2 + (py / RING_B) ** 2 - 1.0
    t = (-B + math.sqrt(B * B - 4 * A * C)) / (2 * A)
    return (p[0] + t * d[0], p[1] + t * d[1])


def on_circle_pt(deg):
    r = math.radians(deg)
    return (FAR_C[0] + FAR_R * math.cos(r), FAR_C[1] + FAR_R * math.sin(r))


def hit_circle(p, d):
    px, py = p[0] - FAR_C[0], p[1] - FAR_C[1]
    b = d[0] * px + d[1] * py
    t = -b + math.sqrt(b * b - (px * px + py * py) + FAR_R * FAR_R)
    return (p[0] + t * d[0], p[1] + t * d[1])


def ell_param(q):
    """The ellipse's own parameter at a point on it, in degrees."""
    return math.degrees(math.atan2((q[1] - RING_C[1]) / RING_B,
                                   (q[0] - RING_C[0]) / RING_A)) % 360.0


def ell_point(deg):
    r = math.radians(deg)
    return (RING_C[0] + RING_A * math.cos(r), RING_C[1] + RING_B * math.sin(r))


def ell_normal(deg):
    """The ellipse's outward unit normal at its own parameter ``deg``."""
    r = math.radians(deg)
    nx, ny = math.cos(r) / RING_A, math.sin(r) / RING_B
    n = math.hypot(nx, ny)
    return (nx / n, ny / n)


def ell_arc(d0, d1, n=400):
    """Arc length of the ellipse from parameter ``d0`` ccw to ``d1``."""
    span = (d1 - d0) % 360.0
    tot, prev = 0.0, ell_point(d0)
    for k in range(1, n + 1):
        cur = ell_point(d0 + span * k / n)
        tot += math.hypot(cur[0] - prev[0], cur[1] - prev[1])
        prev = cur
    return tot


def circ_arc(a0, a1):
    return FAR_R * math.radians((a1 - a0) % 360.0)


def body_arc(poly, t0, t1):
    return abs(t1 - t0) * arc_table(poly)[1]


# -- the document ----------------------------------------------------------

class Topo(object):
    def __init__(self):
        self.pos, self.corners, self.edges, self.blocks = {}, [], [], []
        self.ends = {}

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
            sides = [fwd[(c[0], c[1])],
                     self._side(c[1], c[2]), self._side(c[3], c[2]),
                     self._side(c[0], c[3])]
            self.blocks.append({"id": bid, "edges": sides})
            return
        raise SystemExit("block %s: no side is declared along its ccw ring" % bid)

    def _side(self, a, b):
        for eid, (x, y) in self.ends.items():
            if (x, y) == (a, b) or (x, y) == (b, a):
                return eid
        raise SystemExit("no edge between %s and %s" % (a, b))


def build(split):
    global FAR_C
    pts, seg_up, seg_lo = read_body(os.path.join(ROOT, BODY))
    te, rays, sector = te_rays(pts)
    FAR_C = te                      # the circle is centred ON the trailing edge
    t = Topo()

    # ---- the body corners, and the ring/circle corners their normals reach ---
    fr = [k / split for k in range(1, split)]
    t.onbody("te", 0, 0.0, te)
    t.onbody("le", 1, 0.0, at_fraction(seg_lo, 0.0)[0])
    body = {"te": None, "le": None}
    for k, f in enumerate(fr):
        p, n = at_fraction(seg_up, f)
        t.onbody("u%d" % k, 0, f, p)
        body["u%d" % k] = (p, n)
        p, n = at_fraction(seg_lo, f)
        t.onbody("l%d" % k, 1, f, p)
        body["l%d" % k] = (p, n)
    body["le"] = (t.pos["le"], (-1.0, 0.0))

    # The three internal surfaces leave the trailing edge at GridPro's angles;
    # every other radial leaves along the body's OWN outward normal. Each is one
    # straight line crossing the ring, so its two pieces stay collinear.
    rd = {}
    for cid, a in (("A", rays[0]), ("W", rays[1]), ("C", rays[2])):
        rd["te" + cid] = (te, (math.cos(math.radians(a)), math.sin(math.radians(a))))
    for cid, v in body.items():
        if cid != "te" and v is not None:
            rd[cid] = v

    # WHERE A RING CORNER SITS, at the two ends of the blend this repo already
    # uses (docs/research/where-a-block-corner-sits-on-its-ring.md): on the RING
    # it is where the body's own outward NORMAL arrives, because that is what
    # makes the first cell off the wall orthogonal; on the CIRCLE it is an even
    # share of the arc between the fixed rays, because the normals do not spread
    # out there -- the circle is centred ON the trailing edge, so seen from it
    # the whole body is a thin wedge of directions and a normal cast from
    # mid-chord lands 10 deg from one cast at the trailing edge. Carrying the
    # normals all the way out is what this file measured at 88.5 deg worst
    # non-orthogonality and one outer block 1/8 the width of its neighbour.
    ring_of = {}
    for key, (p, d) in rd.items():
        q = hit_ellipse(p, d)
        t.free("E_" + key, q)
        ring_of[key] = ell_param(q)
    # THE TWO EXTRA CORNERS THAT GIVE EACH TRAILING-EDGE WEDGE ITS FOURTH SIDE,
    # AND WHY THEY ARE NOT ON THE RING CURVE. Placed on the ellipse they are a
    # corner declared in the middle of a SMOOTH curve, so the wedge block meets
    # itself there at 178.5 degrees -- measured, and the worst corner in the
    # whole mesh. That is GridPro's own rule "two sides of one block cannot be
    # on one surface", hit from the inside. So the ring is given a TAIL instead:
    # each is where the perpendicular to the wake at E_teW meets the
    # perpendicular to that sector's internal surface at its own ring corner, so
    # all four of the wedge's corners come out near 90 degrees.
    ring_tail = {}
    if not TAIL:
        # The REJECTED placement, kept reachable so the comparison in section 8e
        # of the note can be re-run rather than quoted: m2/m3 ON the ring curve,
        # which makes each a corner declared in the middle of a SMOOTH ellipse.
        for key, lo, hi in (("m2", "teW", "teA"), ("m3", "teC", "teW")):
            mid = ring_of[lo] + ((ring_of[hi] - ring_of[lo]) % 360.0) / 2.0
            t.free("E_" + key, ell_point(mid))
            ring_of[key] = mid % 360.0
    for key, ray, other in () if not TAIL else (("m2", rays[0], "teA"), ("m3", rays[2], "teC")):
        pw, dw = t.pos["E_teW"], math.radians(rays[1])
        po, do = t.pos["E_" + other], math.radians(ray)
        # line 1: through pw, direction perpendicular to the wake
        # line 2: through po, direction perpendicular to that ray
        n1 = (-math.sin(dw), math.cos(dw))
        n2 = (-math.sin(do), math.cos(do))
        det = n1[0] * (-n2[1]) - n1[1] * (-n2[0])
        rhs = (po[0] - pw[0], po[1] - pw[1])
        u = (rhs[0] * (-n2[1]) - rhs[1] * (-n2[0])) / det
        q = (pw[0] + u * n1[0], pw[1] + u * n1[1])
        t.free("E_" + key, q)
        ring_tail[key] = q

    # ---- the walks ------------------------------------------------------
    up_body = ["te"] + ["u%d" % k for k in range(split - 1)] + ["le"]
    lo_body = ["le"] + ["l%d" % k for k in range(split - 1)] + ["te"]
    # The ring, counter-clockwise from the wake: the upper wedge, the upper
    # surface's stretches, the nose, the lower surface's, the lower wedge.
    ring_walk = (["teW", "m2", "teA"] + up_body[1:-1] + ["le"]
                 + ["l%d" % k for k in range(split - 1)]
                 + ["teC", "m3"])

    # The circle's corners: four are ANCHORED -- the three internal surfaces at
    # GridPro's own angles, and the nose radial dead ahead -- and the rest take
    # an even share of the arc between the anchors they fall between.
    anchor = {"teW": rays[1], "teA": rays[0], "le": 180.0, "teC": rays[2] + 360.0}
    far_of, n = {}, len(ring_walk)
    idx = [i for i, k in enumerate(ring_walk) if k in anchor]
    for a, b in zip(idx, idx[1:] + [idx[0] + n]):
        lo = anchor[ring_walk[a]]
        hi = anchor[ring_walk[b % n]] + (360.0 if b >= n else 0.0)
        for j in range(b - a):
            far_of[ring_walk[(a + j) % n]] = lo + (hi - lo) * j / (b - a)
    # ... and then BLENDED toward where the ring's own outward normal lands,
    # which is the other end of the same trade: the normal keeps the outer
    # ring's radial perpendicular to the ring, the even share keeps the outer
    # blocks the same width. ``--blend`` is the weight on the normal.
    for key in list(far_of):
        if key in anchor:
            continue
        p = t.pos["E_" + key]
        d = ell_normal(ring_of[key]) if key in ring_of else \
            (lambda v: (v[0] / math.hypot(*v), v[1] / math.hypot(*v)))(
                (p[0] - RING_C[0], p[1] - RING_C[1]))
        q = hit_circle(p, d)
        nat = math.degrees(math.atan2(q[1] - FAR_C[1], q[0] - FAR_C[0]))
        even = far_of[key]
        while nat - even > 180.0:
            nat -= 360.0
        while even - nat > 180.0:
            nat += 360.0
        far_of[key] = even + BLEND * (nat - even)
    for key, a in far_of.items():
        t.free("F_" + key, on_circle_pt(a))

    # ---- the radials ----------------------------------------------------
    wall = {"wall_ends": "start"}
    t.edge("r_teA", "te", "E_teA", "interface", count=N_INNER, spacing=wall)
    t.edge("r_wake", "te", "E_teW", "cut", count=N_WAKE, spacing={"ds_start": DS_SURF})
    t.edge("r_teC", "te", "E_teC", "interface", spacing=wall)
    for cid in ["le"] + ["u%d" % k for k in range(split - 1)] \
            + ["l%d" % k for k in range(split - 1)]:
        t.edge("r_" + cid, cid, "E_" + cid, "interface", spacing=wall)
    for i, key in enumerate(ring_walk):
        t.edge("o_" + key, "E_" + key, "F_" + key, "interface",
               count=N_OUTER if i == 0 else None)

    # ---- the body sides, and the ring and circle arcs facing them -------
    def surface(bodylist, seg, poly, side):
        for i in range(split):
            a, b = bodylist[i], bodylist[i + 1]
            ka = "teA" if a == "te" else a
            kb = "teC" if b == "te" else b
            sp = {}
            if a in ("te", "le"):
                sp["ds_start"] = DS_SURF
            if b in ("te", "le"):
                sp["ds_end"] = DS_SURF
            blen = body_arc(poly, i / split, (i + 1) / split)
            t.edge("af_%s_%d" % (side, i), a, b, "wall", count=N_BODY,
                   binding={"geom": BODY_NAME, "seg": seg}, spacing=sp)
            # the ring arc and the circle arc facing it, each carrying the
            # body's clustering SCALED by its own length, so all three share
            # one normalized distribution
            # Both surfaces are walked in the ring's own counter-clockwise
            # sense -- the upper from the trailing edge forward, the lower from
            # the nose aft -- so the facing arc is always the forward one.
            lo, hi = ka, kb
            rl = ell_arc(ring_of[lo], ring_of[hi])
            cl = circ_arc(far_of[lo], far_of[hi])
            t.edge("rr_%s_%d" % (side, i), "E_" + lo, "E_" + hi, "interface",
                   curve={"kind": "ellipse", "centre": list(RING_C),
                          "a": RING_A, "b": RING_B},
                   spacing=_scaled(sp, rl / blen))
            t.edge("cc_%s_%d" % (side, i), "F_" + lo, "F_" + hi, "wall",
                   curve={"kind": "arc", "centre": list(FAR_C), "r": FAR_R},
                   spacing=_scaled(sp, cl / blen))

    surface(up_body, 0, seg_up, "up")
    surface(lo_body, 1, seg_lo, "lo")

    # ---- the trailing-edge fan's own ring and circle arcs ---------------
    # The ring's TAIL is four STRAIGHT sides, not ellipse arcs -- see the note
    # at the m2/m3 corners above.
    for nm, lo, hi in (("w_up_i", "teW", "m2"), ("w_up_o", "m2", "teA"),
                       ("w_lo_o", "teC", "m3"), ("w_lo_i", "m3", "teW")):
        t.edge("rr_" + nm, "E_" + lo, "E_" + hi, "interface",
               curve=None if TAIL else {"kind": "ellipse", "centre": list(RING_C),
                                        "a": RING_A, "b": RING_B})
        t.edge("cc_" + nm, "F_" + lo, "F_" + hi, "wall",
               curve={"kind": "arc", "centre": list(FAR_C), "r": FAR_R})

    # ---- the blocks -----------------------------------------------------
    for i in range(split):                      # the inner ring, body to ellipse
        a, b = up_body[i], up_body[i + 1]
        t.block("b_in_up_%d" % i, [a, b, "E_" + ("le" if b == "le" else b),
                                   "E_" + ("teA" if a == "te" else a)])
        a, b = lo_body[i], lo_body[i + 1]
        t.block("b_in_lo_%d" % i, [a, b, "E_" + ("teC" if b == "te" else b),
                                   "E_" + ("le" if a == "le" else a)])
    t.block("b_in_wake_up", ["te", "E_teW", "E_m2", "E_teA"])
    t.block("b_in_wake_lo", ["te", "E_teC", "E_m3", "E_teW"])
    for i, key in enumerate(ring_walk):         # the outer ring, ellipse to circle
        nxt = ring_walk[(i + 1) % len(ring_walk)]
        t.block("b_out_%d" % i, ["E_" + key, "E_" + nxt, "F_" + nxt, "F_" + key])

    return te, rays, sector, ring_of, far_of, \
        {"format_version": 1, "corners": t.corners, "edges": t.edges,
         "blocks": t.blocks}


def _scaled(sp, ratio):
    return {k: v * ratio for k, v in sp.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", type=int, default=2,
                    help="body sides per surface (2 -> 4 corners on the body, "
                         "GridPro's own count, and 14 blocks)")
    ap.add_argument("--blend", type=float, default=0.5,
                    help="0 = circle corners evenly spread, 1 = where the "
                         "ring's own outward normal lands")
    ap.add_argument("--no-tail", action="store_true",
                    help="put m2/m3 ON the ring curve instead -- the placement "
                         "section 8e of the note rejected, kept re-runnable")
    ap.add_argument("--out", default="gridpro_tworing.json")
    args = ap.parse_args()
    global BLEND, TAIL
    BLEND, TAIL = args.blend, not args.no_tail
    te, rays, sector, ring_of, far_of, topo = build(args.split)
    nb = len(topo["blocks"])
    hdr = [
        "// GridPro's aerofoil blocking, rebuilt the way GridPro builds it.",
        "// See docs/research/gridpro-blocking-method.md, sections 3 and 6.",
        "//",
        "// GENERATED by make_tworing.py %s beside this file."
        % (" ".join(sys.argv[1:]) or "(no flags: every default)"),
        "// Edit that, not this.",
        "//",
        "// GRIDPRO'S, measured out of its own 2-D aerofoil tutorial:",
        "//   * a far-field CIRCLE of radius %g centred ON THE TRAILING EDGE;" % FAR_R,
        "//   * THREE straight internal surfaces radiating from the trailing edge,",
        "//     BISECTING THE EXTERIOR ANGLE EQUALLY -- here %.4f deg each," % sector,
        "//     from a wedge of %.4f deg, DERIVED from this body's own two" % (360 - 4 * sector),
        "//     trailing-edge tangents rather than written down;",
        "//   * a WRAPPED RING between the body and the outer region, which is the",
        "//     step its tutorial calls Wrap (O Grid) at 200%;",
        "//   * FOUR corners on the aerofoil and EIGHT on the circle, against the",
        "//     tutorial's four and \"about nine\";",
        "//   * and %d BLOCKS, which is the tutorial's own count." % nb,
        "//",
        "// On GridPro's S830 the same bisection gives +78.09 / -18.10 / -101.63",
        "// and sectors of 84.3 / 96.2 / 83.5 / 92.3. Here the body is symmetric,",
        "// so the middle ray is the x axis exactly and the wake is straight BY",
        "// DERIVATION; here they are %.4f / %.4f / %.4f." % tuple(rays),
        "//",
        "// OURS: the ring curve is an analytic ellipse (centre %g %g, a %g, b %g)"
        % (RING_C[0], RING_C[1], RING_A, RING_B),
        "// rather than a relaxed wrap, because nothing in this repo moves a corner",
        "// once it is declared; and every node count. Every other radial leaves",
        "// along the BODY'S OWN OUTWARD NORMAL, and each ring and circle arc",
        "// carries its body stretch's clustering scaled by its own arc length, so",
        "// the three curves facing each other share one normalized distribution.",
    ]
    out = os.path.join(HERE, args.out)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(hdr) + "\n" + json.dumps(topo, indent=2) + "\n")
    print("wrote %s" % os.path.relpath(out, ROOT))
    print("  %d blocks, %d corners, %d edges"
          % (nb, len(topo["corners"]), len(topo["edges"])))
    print("  rays %.4f / %.4f / %.4f deg, four sectors of %.4f deg"
          % (rays[0], rays[1], rays[2], sector))
    print("  ring tail       : m2/m3 off the ellipse, see the m2/m3 note")
    print("  ring parameters : " + ", ".join(
        "%s %.1f" % (k, v) for k, v in sorted(ring_of.items(), key=lambda kv: kv[1])))
    print("  circle angles   : " + ", ".join(
        "%s %.1f" % (k, v) for k, v in sorted(far_of.items(),
                                              key=lambda kv: kv[1] % 360)))


if __name__ == "__main__":
    main()
