#!/usr/bin/env python3
"""TARGET: entry 17, Figures 5.1, 5.3 (NACA 0012) and 5.17 (NACA 64A010).

A RESEARCH HARNESS. Nothing shipped reads it; nothing in ``config/``,
``examples/``, ``src/`` or ``include/`` is written or changed by it.

WHAT THE TARGETS ARE, measured off the figures rather than guessed.

  * ``fig5-1`` is the whole NACA 0012 domain. Its axes calibrate from the tick
    labels (y = +-10 at 77 px per 5 units, x = 0/10/20 at 155 px per 10), which
    puts the mesh at x in [-10, 24.06] and y in [-10.13, 10.13]. The BLOCKING
    it shows is a CARTESIAN H -- long block boundaries at x = -3.2, -1.5, 1.9
    and 6.5 and at y = +-2.3 -- with a rosette of small blocks around the
    aerofoil inside [-1.5, 1.9] x [-2.3, 2.3], and the middle band downstream
    of the aerofoil cut into eight horizontal strips (the wake).
  * ``fig5-3`` is the same grid at x in [-0.16, 1.12], y in [-0.57, 0.58]
    (calibrated off the aerofoil's own chord, 406 px). It shows the rosette:
    rings hugging the surface, and fans at the leading and trailing edges.
  * ``fig5-17`` is a NACA 64A010 at x in [-0.42, 1.49], y in [-0.82, 0.91]
    (chord 271 px). The same family, near-field window only, so its far field
    is this file's own choice and nothing in the figure constrains it.

THE CONSTRUCTION, and what each half is.

  THE ROSETTE is this repo's O-grid taken to 16 sectors and four shells. Each
  shell is a true OFFSET of the aerofoil -- the surface normal offset, with an
  ARC of the offset radius spliced in at the sharp trailing edge, which is what
  the offset of a convex corner IS -- written as its own geometry and reached
  with `follows` (#151), so a shell boundary lies on the offset curve rather
  than cutting chords between its corners.
  ``examples/geometries/ellipse_offset.dat`` is the shipped precedent for a
  ring nobody drew.

  THE SHELLS ARE ONE GEOMETRIC SEQUENCE CUT IN THREE. The growth ratio is
  SOLVED for from the distance the last shell has to reach, so the cell size
  does not jump at a shell boundary and each shell's `ds_start` is the previous
  shell's own last interval -- the rule `config/multiblock_tworing.dat` states
  about its own seam, applied three times.

  THE FAR FIELD is an H: five columns by a per-column list of rows. It is NOT
  a product grid -- the columns left of the aerofoil carry four rows and the
  two downstream carry ten, which is what puts the wake strips only in the
  wake -- and that is legal here because the two groups never touch: the
  rosette's own rectangle is between them.

  WHAT JOINS THEM is a 16-point correspondence between the body and that
  rectangle, counter-clockwise from the trailing edge. Every ray is one
  `interface` edge per shell, and the rectangle's four corners are four of the
  sixteen points, so no far-field block spans a corner.

  EVERY EDGE OF A COUNT CLASS CARRIES THE SAME SPACING LAW. A count propagates
  across a block and a spacing law does not, so a graded side facing a uniform
  one tilts every line between them. Measured on this directory's flat-plate
  case: worst wall first cell 531.17% off and mean non-orthogonality 13.621
  deg, against 6.99% and 5.990 once the law was declared on both sides.

    python3 docs/research/allampalli-2010-reproductions/make_airfoil.py \
        [--case naca0012|naca64a010] [--run]
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mblib                                            # noqa: E402

HERE = mblib.HERE
REL = os.path.relpath(HERE, mblib.ROOT)

# ── the two cases ─────────────────────────────────────────────────────────
# `shell_n` is radial INTERVALS per shell, `shell_d` how far the last one
# reaches, `outer_n` the intervals from it to the rectangle. `col_n` is the
# streamwise node count of H columns A, B, D and E; `row_n` the wall-normal
# count of the top and bottom rows; the `*_ds` entries the first or last cell
# each of those is graded to, chosen to match the cell size on the other side
# of the seam it is graded towards.
CASES = {
    "naca0012": dict(
        law="naca4", thick=0.12,
        wall_ds=0.0015, shell_n=[14, 10, 10], shell_d=0.42, outer_n=25,
        # `rin_r[0]` IS WHERE THE FIRST RAY OFF THE TRAILING EDGE LANDS, and
        # it is the one number here that the mesh is sensitive to: the sector
        # between it and the wake line is the one carrying the 163-degree
        # trailing-edge arc, so giving it a bigger share of the rectangle's
        # right edge un-twists it. Measured: 1.0 against 0.35 takes the worst
        # non-orthogonality from 88.598 to 81.738 deg and the mean from 6.248
        # to 5.802. 1.0 is also what the figure shows.
        #
        # EVERY ONE OF THESE SEVEN NUMBERS IS READ OFF FIG. 5.1, by scanning
        # the figure's own block colours along four horizontal and four
        # vertical lines (the readings are in the note beside this file): the
        # rectangle at x in [-1.5, 1.7] and y = +-2.55, its right edge cut at
        # y = +-1.0 and +-1.71, its left edge at +-1.30, its top at x = 1.19
        # and -0.22, and the far-field columns at x = -3.0 and 6.1.
        rin=(-1.5, 1.7, -2.55, 2.55),
        rin_r=[1.0, 1.71], rin_t=[1.19, -0.22], rin_l=[1.30],
        xs=[-10.0, -3.0, -1.5, 1.7, 6.1, 24.06],
        k_nodes=48,
        col_n=[23, 15, 23, 27], col_ds=[0.14, None, 0.10, 0.34],
        row_n=[29, 29], row_ds=0.26,
        ybox=10.0, window=(-10.0, 24.06, -10.13, 10.13)),
    "naca64a010": dict(
        law="64a010", thick=0.10,
        wall_ds=0.0015, shell_n=[14, 10, 10], shell_d=0.30, outer_n=19,
        rin=(-0.9, 1.6, -1.25, 1.25),
        rin_r=[0.55, 0.95], rin_t=[0.75, 0.0], rin_l=[0.55],
        xs=[-5.0, -2.0, -0.9, 1.6, 4.0, 12.0],
        k_nodes=48,
        col_n=[21, 17, 23, 25], col_ds=[0.08, None, 0.06, 0.20],
        row_n=[27, 27], row_ds=0.16,
        ybox=5.0, window=(-0.421, 1.494, -0.823, 0.911)),
}


def rows_ab(cfg):
    """The row cuts of the two columns UPSTREAM of the rosette: the box, the
    rectangle, and the rectangle's own left-edge divisions mirrored."""
    x0, x1, y0, y1 = cfg["rin"]
    L = cfg["rin_l"]
    return ([-abs(cfg["ybox"]), y0] + [-v for v in reversed(L)] +
            [0.0] + list(L) + [y1, abs(cfg["ybox"])])


def rows_de(cfg):
    """And of the two DOWNSTREAM columns, whose extra rows are the wake
    strips -- the rectangle's right-edge divisions, which are where the
    rosette's own shells reach it."""
    x0, x1, y0, y1 = cfg["rin"]
    R = cfg["rin_r"]
    return ([-abs(cfg["ybox"]), y0] + [-v for v in reversed(R)] + [0.0] +
            list(R) + [y1, abs(cfg["ybox"])])

# The sixteen stations, as a chordwise parameter s in [0, 2): 0 is the trailing
# edge, 1 the leading edge, 2 the trailing edge again, walking the body
# COUNTER-CLOCKWISE. Each one points at the rectangle point beside it in
# `rin_pts`.
STATIONS = [0.00, 0.02, 0.06, 0.14, 0.30, 0.55, 0.80, 0.95,
            1.00, 1.05, 1.20, 1.45, 1.70, 1.86, 1.94, 1.98]


def half_thickness(cfg, x):
    if cfg["law"] == "naca4":
        return mblib.naca_half_thickness(x, cfg["thick"])
    return mblib.naca64a010_half_thickness(x)


def surface(cfg, s):
    """The body at ``s`` in [0, 2]: 0..1 is the UPPER surface from the trailing
    edge forward to the leading edge, 1..2 the LOWER surface back to it."""
    if s <= 1.0:
        x = 1.0 - s
        return (x, half_thickness(cfg, x))
    x = s - 1.0
    return (x, -half_thickness(cfg, x))


def rin_pts(cfg):
    """The sixteen points of the rosette's rectangle, counter-clockwise from
    the point directly behind the trailing edge.

    THE RIGHT EDGE CARRIES MORE DIVISIONS THAN THE LEFT, and that is the whole
    shape of the thing: the sixteen rays leave the aerofoil evenly and have to
    arrive somewhere, and downstream is where the figure puts its strips. The
    four corners of the rectangle are four of the sixteen, so no far-field
    block spans one.
    """
    x0, x1, y0, y1 = cfg["rin"]
    R, T, L = cfg["rin_r"], cfg["rin_t"], cfg["rin_l"]
    pts = ([(x1, 0.0)] + [(x1, v) for v in R] + [(x1, y1)] +
           [(v, y1) for v in T] + [(x0, y1)] +
           [(x0, v) for v in reversed(L)] + [(x0, 0.0)] +
           [(x0, -v) for v in L] + [(x0, y0)] +
           [(v, y0) for v in reversed(T)] + [(x1, y0)] +
           [(x1, -v) for v in reversed(R)])
    if len(pts) != 16:
        raise SystemExit("rin_pts: %d points, need 16 -- len(rin_r) + "
                         "len(rin_t) + len(rin_l) must be 5" % len(pts))
    return pts


def body_poly(cfg, s_a, s_b, n):
    return [surface(cfg, s_a + (s_b - s_a) * k / n) for k in range(n + 1)]


def normal_at(cfg, s, h=2e-4):
    a = surface(cfg, max(0.0, s - h))
    b = surface(cfg, min(2.0, s + h))
    tx, ty = b[0] - a[0], b[1] - a[1]
    m = math.hypot(tx, ty) or 1.0
    return (ty / m, -tx / m)           # the body is walked CCW: this is OUTWARD


def offset_pt(cfg, s, d):
    p, n = surface(cfg, s), normal_at(cfg, s)
    return (p[0] + d * n[0], p[1] + d * n[1])


def te_angles(cfg):
    """The two ends of the trailing edge's offset arc, in degrees: where the
    upper surface's own normal points, and where the lower's does."""
    nu = normal_at(cfg, 1e-4)
    nl = normal_at(cfg, 2.0 - 1e-4)
    return (math.degrees(math.atan2(nu[1], nu[0])),
            math.degrees(math.atan2(nl[1], nl[0])) % 360.0)


def offset_seg(cfg, s_a, s_b, d, n):
    """One segment of a shell: the normal offset of the body stretch, with the
    TRAILING-EDGE ARC spliced in where the stretch touches s = 0 or s = 2.

    Without the arc the two surface offsets simply cross at the sharp corner
    and the first sector's outer side doubles back on itself.
    """
    te = surface(cfg, 0.0)
    a_up, a_lo = te_angles(cfg)
    pts, tail = [], None
    if s_a == 0.0:
        m = max(2, n // 3)
        pts += mblib.arc_pts(te, d, 0.0, a_up, m)[:-1]
        n -= m
    if s_b == 2.0:
        m = max(2, n // 3)
        tail = mblib.arc_pts(te, d, a_lo, 360.0, m)[1:]
        n -= m
    lo = s_a + (1e-4 if s_a == 0.0 else 0.0)
    hi = s_b - (1e-4 if s_b == 2.0 else 0.0)
    pts += [offset_pt(cfg, lo + (hi - lo) * k / max(1, n), d)
            for k in range(max(1, n) + 1)]
    if tail:
        pts += tail
    return pts


def shell_plan(cfg):
    """``(radii, first_cells, outer_first)``: where each shell sits, what its
    first radial interval is, and the first interval of the outer shell. ONE
    geometric sequence, with its ratio solved for by bisection."""
    w, ns, d = cfg["wall_ds"], cfg["shell_n"], cfg["shell_d"]
    n = sum(ns)
    lo, hi = 1.0 + 1e-12, 4.0
    for _ in range(200):
        g = 0.5 * (lo + hi)
        s = n * w if abs(g - 1.0) < 1e-12 else w * (g ** n - 1.0) / (g - 1.0)
        if s < d:
            lo = g
        else:
            hi = g
    g = 0.5 * (lo + hi)
    radii, firsts, acc, k = [], [], 0.0, 0
    for m in ns:
        firsts.append(w * g ** k)
        for _ in range(m):
            acc += w * g ** k
            k += 1
        radii.append(acc)
    return radii, firsts, w * g ** k, g


def build(name):
    cfg = CASES[name]
    rin = rin_pts(cfg)
    x0, x1, y0, y1 = cfg["rin"]
    shells, firsts, outer_ds, g = shell_plan(cfg)
    radii = [0.0] + shells

    # ── node counts, one per sector ───────────────────────────────────────
    # The geometric mean of what the sector spans on the BODY and on the
    # rectangle. A count serves both sides of its class, so neither end can
    # have it to itself: keyed to the body alone the far field comes out with
    # 20:1 cells, keyed to the rectangle the surface is under-resolved.
    counts = []
    for i in range(16):
        sa = STATIONS[i]
        sb = STATIONS[i + 1] if i < 15 else 2.0
        poly = body_poly(cfg, sa, sb, 60)
        bl = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                 for a, b in zip(poly, poly[1:]))
        rl = math.hypot(rin[(i + 1) % 16][0] - rin[i][0],
                        rin[(i + 1) % 16][1] - rin[i][1])
        # THE TWO SECTORS THAT TOUCH THE TRAILING EDGE GET A FLOOR, because
        # their body stretch is 2% of chord while their shell stretch is most
        # of a 163-degree arc, so the geometric mean sizes them for the body
        # and leaves the arc under-resolved. IT IS NOT LOAD BEARING and the
        # measurement says so: at this ray assignment nothing folds at any
        # floor from 6 to 20, and the worst angle moves 81.745 -> 81.735 deg
        # while the mean moves 5.755 -> 5.863. What DOES move the angle is
        # where the first ray lands (see `rin_r`).
        floor = 13 if i in (0, 15) else 6
        counts.append(max(floor,
                          int(round(cfg["k_nodes"] * math.sqrt(bl * rl)))) + 1)

    # ── geometries: the body, then one per shell ──────────────────────────
    geoms = []
    for k, d in enumerate(radii):
        segs = []
        for i in range(16):
            sa = STATIONS[i]
            sb = STATIONS[i + 1] if i < 15 else 2.0
            n = (counts[i] - 1) * 4
            segs.append(body_poly(cfg, sa, sb, n) if k == 0
                        else offset_seg(cfg, sa, sb, d, n))
        geoms.append(mblib.write_geom("%s_r%d" % (name, k), segs, ["wall"] * 16))

    t = mblib.Topo()
    for k, d in enumerate(radii):
        for i in range(16):
            p = surface(cfg, STATIONS[i]) if k == 0 \
                else offset_pt(cfg, STATIONS[i], d)
            cid = "b%02d" % i if k == 0 else "s%d_%02d" % (k, i)
            t.onbody(cid, geoms[k], i, 0.0, p)
    for i in range(16):
        t.free("n%02d" % i, rin[i])

    def ring(k, i):
        return "b%02d" % i if k == 0 else "s%d_%02d" % (k, i)

    for i in range(16):
        j = (i + 1) % 16
        t.edge("w%02d" % i, "b%02d" % i, "b%02d" % j, "wall", count=counts[i],
               binding={"geom": geoms[0], "seg": i})
        for k in range(1, len(radii)):
            t.edge("c%d_%02d" % (k, i), ring(k, i), ring(k, j), "interface",
                   follows={"geom": geoms[k], "seg": i})
        t.edge("n%02d" % i, "n%02d" % i, "n%02d" % j, "interface")

    # the radials: one wrapping class per shell, one seed each, and the
    # spacing of shell k+1 starts where shell k's last interval ended
    for k in range(1, len(radii) + 1):
        if k == 1:
            sp, cnt = {"wall_ends": "start"}, cfg["shell_n"][0] + 1
        elif k < len(radii):
            sp, cnt = {"ds_start": firsts[k - 1]}, cfg["shell_n"][k - 1] + 1
        else:
            sp, cnt = {"ds_start": outer_ds}, cfg["outer_n"] + 1
        inner = (lambda i, k=k: ring(k - 1, i))
        outer = ((lambda i, k=k: ring(k, i)) if k < len(radii)
                 else (lambda i: "n%02d" % i))
        for i in range(16):
            t.edge("r%d_%02d" % (k, i), inner(i), outer(i), "interface",
                   count=(cnt if i == 0 else None), spacing=sp)
        for i in range(16):
            t.block("q%d_%02d" % (k, i),
                    [inner(i), inner((i + 1) % 16),
                     outer((i + 1) % 16), outer(i)])

    # ── the H far field ───────────────────────────────────────────────────
    XS, YAB, YDE = cfg["xs"], rows_ab(cfg), rows_de(cfg)
    col_ds, row_ds = cfg["col_ds"], cfg["row_ds"]
    seen = {}

    def g_(x, y):
        key = (round(x, 9), round(y, 9))
        if key in seen:
            return seen[key]
        for cid, p in t.pos.items():
            if abs(p[0] - x) < 1e-9 and abs(p[1] - y) < 1e-9:
                seen[key] = cid
                return cid
        cid = "g%d" % len(seen)
        while cid in t.pos:
            cid += "_"
        t.free(cid, (x, y))
        seen[key] = cid
        return cid

    def hlaw(x_lo, x_hi):
        """The streamwise law of the column between two x cuts. Columns are
        graded TOWARDS the aerofoil, and both of a column's horizontal edges
        get the same law because they are one count class."""
        for ci in range(4):
            a, b = XS[ci if ci < 2 else ci + 1], XS[(ci if ci < 2 else ci + 1) + 1]
            if abs(a - x_lo) < 1e-9 and abs(b - x_hi) < 1e-9:
                if col_ds[ci] is None:
                    return None
                return ({"ds_end": col_ds[ci]} if ci < 2
                        else {"ds_start": col_ds[ci]})
        return None

    def vlaw(y_lo, y_hi):
        if abs(y_hi - YAB[-1]) < 1e-9:
            return {"ds_start": row_ds}
        if abs(y_lo - YAB[0]) < 1e-9:
            return {"ds_end": row_ds}
        return None

    def line(a, b, kind_seed=None, sp=None):
        try:
            return t._side(a, b)
        except SystemExit:
            pa, pb = t.pos[a], t.pos[b]
            on_box = any(abs(pa[0] - v) < 1e-9 and abs(pb[0] - v) < 1e-9
                         for v in (XS[0], XS[-1])) or \
                     any(abs(pa[1] - v) < 1e-9 and abs(pb[1] - v) < 1e-9
                         for v in (YAB[0], YAB[-1]))
            return t.edge("h%d" % len(t.edges), a, b,
                          "wall" if on_box else "interface",
                          count=kind_seed, spacing=sp)

    def cell(bid, xa, xb, ya, yb, hseed=None, vseed=None):
        c = [g_(xa, ya), g_(xb, ya), g_(xb, yb), g_(xa, yb)]
        hl, vl = hlaw(xa, xb), vlaw(ya, yb)
        line(c[0], c[1], hseed, hl)
        line(c[1], c[2], vseed, vl)
        line(c[3], c[2], None, hl)
        line(c[0], c[3], None, vl)
        t.block(bid, c)

    for ci in (0, 1):                       # the two columns left of the rosette
        for ri in range(len(YAB) - 1):
            cell("hL%d%d" % (ci, ri), XS[ci], XS[ci + 1], YAB[ri], YAB[ri + 1],
                 hseed=(cfg["col_n"][ci] if ri == 0 else None),
                 vseed=(cfg["row_n"][0] if ri == 0 else
                        cfg["row_n"][1] if ri == len(YAB) - 2 else None))
    for ci in (3, 4):                       # the two downstream columns
        for ri in range(len(YDE) - 1):
            cell("hR%d%d" % (ci, ri), XS[ci], XS[ci + 1], YDE[ri], YDE[ri + 1],
                 hseed=(cfg["col_n"][ci - 1] if ri == 0 else None))
    xa = [x0] + list(reversed(cfg["rin_t"])) + [x1]
    for k in range(3):                      # above and below the rosette
        cell("hT%d" % k, xa[k], xa[k + 1], y1, YAB[-1])
        cell("hB%d" % k, xa[k], xa[k + 1], YAB[0], y0)

    t.write("%s.json" % name, header="""
TARGET: entry 17 (Allampalli 2010), Figures 5.1 and 5.3 (NACA 0012) or 5.17
(NACA 64A010).

WRITTEN BY docs/research/allampalli-2010-reproductions/make_airfoil.py.
Do not hand-edit: the body and the three shells are four geometries written by
the same run, and every b* and s* corner is an arc-length position on one of
them.

A sixteen-sector rosette of four shells around the aerofoil, inside a
Cartesian H far field whose two upstream columns carry four rows and whose two
downstream columns carry ten -- the extra six being the wake strips, which
exist only downstream because the rosette's rectangle separates the two groups.
""")

    confs = mblib.write_pair(
        name, "%s.json" % name,
        ["GEOM_FILE %s/%s" % (REL, geoms[0])] +
        ["GEOM_FILE %s/%s nobl" % (REL, gg) for gg in geoms[1:]],
        cfg["wall_ds"],
        extra=["",
               "# ZERO SWEEPS. The shipped default is 20 and both of these",
               "# cases are measurably worse with it. Worst wall first cell",
               "# against sweeps, measured on these declarations:",
               "#   NACA 0012   0 -> 12.58%  5 -> 59.00%  10 -> 72.36%",
               "#               20 -> 92.38%  40 -> 86.96%, with 2 cells",
               "#               folded at 5 and 6 from 10 on, none at 0.",
               "#   NACA 64A010 0 -> 14.10%  5 -> 61.40%  10 -> 74.06%",
               "#               20 -> 93.18%  40 -> 86.19%, with 2 folded",
               "#               from 10 on, none below.",
               "# Mean non-orthogonality moves the other way and barely",
               "# (5.802 -> 5.446 deg on the 0012 over 0 to 20 sweeps) and",
               "# the max does not improve: it is the sharp trailing edge at",
               "# every count, and on the 0012 it gets worse, 81.738 ->",
               "# 84.991 deg.",
               "# The shipped cases the default was tuned on have a smooth",
               "# convex body and a single ring; these have a 163-degree",
               "# corner and a rectangular outer boundary.",
               "MB_SMOOTH_ITERS 0"],
        title="TARGET: entry 17, %s." % name)
    print("%s: %s" % (name, t.stats()))
    print("  growth %.5f, shells at d = %s, outer first cell %.5f"
          % (g, ", ".join("%.4f" % d for d in shells), outer_ds))
    print("  sector counts %s" % counts)
    return confs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="naca0012", choices=sorted(CASES))
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    confs = build(a.case)
    ok = True
    if a.run:
        for c in confs:
            ok = mblib.summarise(mblib.run(c), os.path.basename(c)) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
