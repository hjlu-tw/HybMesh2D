#!/usr/bin/env python3
"""COUNT-REDUCING ANNULI, parameterised, so the cost of a reduction can be
MEASURED instead of estimated.

A RESEARCH HARNESS beside ``docs/research/nesting-blocks-at-a-complicated-leading-edge.md``
section 16, which carries the full record. Nothing shipped reads it; nothing in
``config/``, ``examples/``, ``src/`` or ``include/`` is written or changed by it.

WHAT IS BEING ASKED. Section 15a defined N(r) -- how many block-partition lines
cross a circle of radius r -- and 15b measured every blocking in this repo FLAT.
#191 then measured that a CHAIN cannot bend that curve either, because a chain
junction is an ordinary valence-4 node. #192 step 1 wrote down the one device
that can: a corner shared by THREE blocks rather than four. This file builds the
smallest ring out of that device, and then K of them, so that the price can be
stated in blocks, in cells and in degrees.

THE CONSTRUCTION, derived from the count algebra rather than drawn by eye. The
ring is K repeats of one unit, and each unit is two blocks:

    the CORNER BLOCK   two of its four sides are on the INNER circle and NONE is
                       on the outer, so both of its radials end at one apex X;
    the ORDINARY BLOCK one inner side, one outer side, two radials.

Opposite sides of a block carry equal counts, so for the corner block the two
inner arcs equal the two radials, and for the ordinary block the inner side
equals the outer side. Writing a for the radial interval count and m for the
ordinary side's:

    inner = K * (2a + m)     outer = K * m     REDUCTION = 2 * K * a

THE REDUCTION IS TWICE THE RING'S OWN RADIAL DEPTH, PER CORNER BLOCK. It is not
a number the author picks independently of the blocking, and it is not one line
per irregular node: ONE corner block at depth 25 ends 48 lines.

WHERE THE PRICE IS. Each unit has one apex X, where three blocks meet, and one
FOLD NODE between the corner block's two inner arcs, which is a corner of that
block and of nothing else. On a SMOOTH inner circle the single cell at the fold
has to span the boundary's own 180 degrees, which is a 90-degree
non-orthogonality and the mesher reports it as inverted. ``--notch`` dips the
fold node inward so the boundary turns there and that cell becomes an ordinary
one; ``--embed`` wraps the ring in two ordinary rings so that both off-valence
nodes become INTERIOR (valence 3 at the fold, valence 5 at the apex), which is
the arrangement a real case would use. Both are measured rather than argued.

THE TWO DOCUMENTS THIS WRITES, measured 2026-11-12 through the real binary:

    reducing_annulus   the SMALLEST one. 4 blocks, inner 72 intervals, outer 48,
                       720 quads, 3 inverted, nonortho max 89.5 — the fold cell,
                       which no smoothing and no embedding removes. Its N(r) is
                       FLAT at 4: the count falls inside the corner block.
    reducing_ogrid     --embed, on the shipped circle geometries. 36 blocks,
                       body 192 intervals against the shipped O-grid's 96 and far
                       field 96, 7872 quads, 0 inverted, nonortho max 53.6 mean
                       4.70, 8 interior irregular nodes (four valence 3 at the
                       folds, four valence 5 at the apexes). Its N(r) FALLS, 16
                       to 8, and it is the first blocking in this repo that does.
                       GATE 2 PASSES on it: mesher, getPGrid and unicones at
                       M 0.2, Re 200, cfl 0.6, 100 iterations, no NaN.

THE TWO COMMITTED DOCUMENTS ARE WRITTEN BY THESE TWO COMMANDS, and each one
is repeated in the header of the file it writes:

    python3 .../make_reducing_annulus.py --folds 1 --per-unit 3 \
        --depth 13 --ordinary 17 --stem reducing_annulus
    python3 .../make_reducing_annulus.py --folds 4 --per-unit 2 \
        --depth 13 --ordinary 13 --notch 0.2 --embed --r-out 1.8 \
        --smooth 20 --stem reducing_ogrid

    ./run.sh -conf docs/research/gridpro-blocking-method/reducing_annulus.dat
    ./run.sh -conf docs/research/gridpro-blocking-method/reducing_annulus.dat
    python3 docs/research/gridpro-blocking-method/measure_block_partition.py \
        /tmp/ra.vtk --centre 0 0
    ./run_pipeline.sh docs/research/gridpro-blocking-method/reducing_ogrid_demo.json
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

R_IN, R_OUT_DEFAULT = 1.0, 3.0

# --embed only. A body ring inside and a far ring outside, both ordinary, and
# both on the SHIPPED circle geometries rather than on circles invented here --
# which is what gives the embedded case real boundary conditions (wall on the
# body, farfield on the outer circle) and therefore a mesh the solver can be
# asked to run. Each file is four quarter segments starting at angle 0 and
# running anticlockwise, which is what `on_geometry` below converts an angle to.
BODY_GEOM, R_BODY = "circle_body.dat", 0.5
FAR_GEOM, R_FAR = "circle_farfield.dat", 10.0


def polar(r, deg):
    t = math.radians(deg)
    return [round(r * math.cos(t), 12), round(r * math.sin(t), 12)]


def on_geometry(cid, geom, deg):
    """A corner at angle `deg` on a four-quarter circle, as (segment, t)."""
    phi = deg % 360.0
    seg = int(phi // 90.0) % 4
    return {"id": cid, "kind": "on_geometry", "geom": geom, "seg": seg,
            "t": round((phi - 90.0 * seg) / 90.0, 12)}


def binding(geom, deg_from, deg_to):
    """The segment an arc lies on, named by its own MIDPOINT going anticlockwise.

    Anticlockwise and not by the smaller of the two numbers: the last arc of the
    ring runs from 360 back to the first corner, and halving the two angles
    as written puts its midpoint on the far side of the circle.
    """
    if deg_to <= deg_from:
        deg_to += 360.0
    phi = (0.5 * (deg_from + deg_to)) % 360.0
    return {"geom": geom, "seg": int(phi // 90.0) % 4}


def build(folds, depth, ordinary, notch=0.0, embed=False, smooth_iters=0,
          per_unit=1, body_depth=25, far_depth=17, offset=None,
          r_out=R_OUT_DEFAULT):
    """`depth` and `ordinary` are NODE counts; the reduction is 2*K*(depth-1).

    One UNIT is a corner block plus `per_unit` ordinary blocks, repeated `folds`
    times. `per_unit` exists because the outer circle has to be cut into at
    least two arcs to be edges at all, and three for none of them to be a half
    turn: K = 1 is the SMALLEST ring and it needs three ordinary blocks beside
    its one corner block.
    """
    a, m = depth - 1, ordinary - 1
    unit = 360.0 / folds
    # WHY THE RING IS OFFSET BY HALF A UNIT when it is embedded: the body and
    # far-field circles are four quarter SEGMENTS and an edge bound to one may
    # not cross into the next, so every corner angle has to fall strictly inside
    # a quarter or exactly on its join. With the fold centred half a unit along,
    # K a multiple of four and two ordinary blocks per unit, every arc does --
    # the intermediate corners land exactly on multiples of the unit, and those
    # include 0, 90, 180 and 270.
    if offset is None:
        offset = 0.5 * unit if embed else 0.0
    if embed and (folds % 4 or per_unit != 2):
        raise SystemExit("--embed needs --folds a multiple of 4 and --per-unit 2; "
                         "see the segment-crossing note in build().")
    q = per_unit
    # The corner block's share of the unit's arc is its share of the unit's
    # NODES, so the inner boundary keeps one spacing all the way round rather
    # than crowding 2a intervals into whatever angle happened to be left.
    half = 0.5 * unit * (2.0 * a) / (2.0 * a + q * m)
    R_OUT = r_out
    inner = {"kind": "ellipse", "centre": [0.0, 0.0], "a": R_IN, "b": R_IN}
    outer = {"kind": "ellipse", "centre": [0.0, 0.0], "a": R_OUT, "b": R_OUT}
    kinked = (notch != 0.0)
    ring_kind = "interface" if embed else "wall"

    def arc(eid, c0, c1, curve, kind, count=None):
        e = {"id": eid, "corners": [c0, c1], "kind": kind}
        if count is not None:
            e["count"] = count
        if curve is not None:
            # Every arc is declared COUNTER-CLOCKWISE with its corners in that
            # order, so no edge is the long way round its circle.
            e["curve"] = dict(curve, sweep="ccw")
        return e

    corners, edges, blocks = [], [], []
    ang = {}

    def corner(name, deg, rad):
        corners.append({"id": name, "kind": "free", "xy": polar(rad, deg)})
        ang[name] = deg
        return name

    # The inner ring, in order: per unit, the corner block's three corners and
    # then the q-1 that divide its ordinary blocks.
    inner_ring, outer_ring = [], []
    for j in range(folds):
        th = unit * j + offset
        inner_ring.append(corner("a%d" % j, th - half, R_IN))
        inner_ring.append(corner("c%d" % j, th, R_IN * (1.0 - notch)))
        inner_ring.append(corner("p%d" % j, th + half, R_IN))
        span = unit - 2.0 * half
        for i in range(1, q):
            inner_ring.append(corner("d%d_%d" % (j, i),
                                     th + half + span * i / q, R_IN))
        outer_ring.append(corner("X%d" % j, th, R_OUT))
        for i in range(1, q):
            outer_ring.append(corner("Y%d_%d" % (j, i), th + unit * i / q, R_OUT))

    def radial(name, c_in, c_out):
        edges.append({"id": name, "corners": [c_in, c_out], "kind": "interface"})
        return name

    inner_edge_of = {}      # inner corner -> the inner edge that STARTS there
    for j in range(folds):
        k = (j + 1) % folds
        edges.append(arc("wL%d" % j, "a%d" % j, "c%d" % j,
                         None if kinked else inner, ring_kind))
        edges.append(arc("wR%d" % j, "c%d" % j, "p%d" % j,
                         None if kinked else inner, ring_kind))
        inner_edge_of["a%d" % j] = "wL%d" % j
        inner_edge_of["c%d" % j] = "wR%d" % j
        # The ordinary blocks of this unit, outward from the apex.
        ins = ["p%d" % j] + ["d%d_%d" % (j, i) for i in range(1, q)] + ["a%d" % k]
        outs = ["X%d" % j] + ["Y%d_%d" % (j, i) for i in range(1, q)] + ["X%d" % k]
        radial("rA%d" % j, "a%d" % j, "X%d" % j)
        radial("rB%d" % j, "p%d" % j, "X%d" % j)
        for i in range(1, q):
            radial("rD%d_%d" % (j, i), ins[i], outs[i])
        rads = ["rB%d" % j] + ["rD%d_%d" % (j, i) for i in range(1, q)] \
            + ["rA%d" % k]
        for i in range(q):
            edges.append(arc("wo%d_%d" % (j, i), ins[i], ins[i + 1], inner,
                             ring_kind, ordinary))
            edges.append(arc("o%d_%d" % (j, i), outs[i], outs[i + 1], outer,
                             ring_kind))
            inner_edge_of[ins[i]] = "wo%d_%d" % (j, i)
            blocks.append({"id": "Q%d_%d" % (j, i),
                           "edges": [rads[i], "o%d_%d" % (j, i), rads[i + 1],
                                     "wo%d_%d" % (j, i)]})
        # THE CORNER BLOCK. Its ring is a -> X -> p -> c: out along one radial,
        # back in along the other, then the two inner arcs in reverse. 'X' is a
        # corner of this block and of both its neighbours.
        blocks.append({"id": "C%d" % j,
                       "edges": ["rA%d" % j, "rB%d" % j, "wR%d" % j, "wL%d" % j]})
    # ONE SEED PER UNIT, not one for the ring. The corner block links each of
    # its radials to one of its INNER ARCS rather than to the other radial, so
    # the relation does not pass through it and K corner blocks make K radial
    # classes -- which is #192 step 1's "N blocks at a corner make N count
    # classes" showing up a second time. Seeding only the first is refused,
    # naming the group with no count.
    for j in range(folds):
        next(e for e in edges if e["id"] == "rA%d" % j)["count"] = depth

    if embed:
        for n in inner_ring:
            corners.append(on_geometry("b_" + n, BODY_GEOM, ang[n]))
        for n in outer_ring:
            corners.append(on_geometry("f_" + n, FAR_GEOM, ang[n]))
        for i, n in enumerate(inner_ring):
            nxt = inner_ring[(i + 1) % len(inner_ring)]
            e = arc("wb%d" % i, "b_" + n, "b_" + nxt, None, "wall")
            # The body is a DRAWN polyline, so its edges bind to the source
            # segment they lie on rather than declaring a circle: that is what
            # carries the 'wall' boundary condition out of the .meta sidecar.
            e["binding"] = binding(BODY_GEOM, ang[n], ang[nxt])
            edges.append(e)
            edges.append({"id": "s%d" % i, "corners": ["b_" + n, n],
                          "kind": "interface",
                          "spacing": {"wall_ends": "start"}})
        for i, n in enumerate(inner_ring):
            blocks.append({"id": "B%d" % i,
                           "edges": ["s%d" % i, inner_edge_of[n],
                                     "s%d" % ((i + 1) % len(inner_ring)),
                                     "wb%d" % i]})
        next(e for e in edges if e["id"] == "s0")["count"] = body_depth
        outer_edge_of = {}
        for j in range(folds):
            k = (j + 1) % folds
            outs = ["X%d" % j] + ["Y%d_%d" % (j, i) for i in range(1, q)] \
                + ["X%d" % k]
            for i in range(q):
                outer_edge_of[outs[i]] = "o%d_%d" % (j, i)
        for i, n in enumerate(outer_ring):
            nxt = outer_ring[(i + 1) % len(outer_ring)]
            e = arc("wf%d" % i, "f_" + n, "f_" + nxt, None, "wall")
            e["binding"] = binding(FAR_GEOM, ang[n], ang[nxt])
            edges.append(e)
            edges.append({"id": "t%d" % i, "corners": [n, "f_" + n],
                          "kind": "interface"})
        for i, n in enumerate(outer_ring):
            blocks.append({"id": "F%d" % i,
                           "edges": ["t%d" % i, "wf%d" % i,
                                     "t%d" % ((i + 1) % len(outer_ring)),
                                     outer_edge_of[n]]})
        next(e for e in edges if e["id"] == "t0")["count"] = far_depth

    doc = {"format_version": 1, "corners": corners, "edges": edges,
           "blocks": blocks}
    inner_n, outer_n = folds * (2 * a + q * m), folds * q * m
    # THE GENERATING COMMAND GOES IN THE FILE, the way `gridpro_rings.json`
    # beside it does. Without it "re-run the generator" names no run: these
    # documents differ from the generator's defaults in up to seven flags, and
    # a figure recorded against one of them cannot be checked against the other.
    header = (
        "// A COUNT-REDUCING ANNULUS (issue #192 step 2) — GENERATED by\n"
        "// make_reducing_annulus.py %s\n"
        "// beside this file. Do not hand-edit; re-run that command.\n"
        "//\n"
        "// %d corner block(s) and %d ordinary one(s) between two circles. A corner\n"
        "// block has two sides on the inner circle and none on the outer, so its\n"
        "// apex is a corner of three blocks and the count FALLS across the ring:\n"
        "// inner = %d intervals, outer = %d, reduction = %d.\n"
        % (" ".join(sys.argv[1:]), folds, folds * q, inner_n, outer_n,
           inner_n - outer_n))
    geom = ("GEOM_FILE examples/geometries/%s\n"
            "DOMAIN_FILE examples/geometries/%s nobl\n"
            "BL_INITIAL_THICKNESS 0.001\n" % (BODY_GEOM, FAR_GEOM)) if embed else ""
    cfg = (
        "# GENERATED by make_reducing_annulus.py "
        + " ".join(sys.argv[1:]) + " — #192 step 2.\n" + (
        "MESH_MODE 1\n" + geom + (
        "MESH_TOPOLOGY_FILE docs/research/gridpro-blocking-method/STEM.json\n"
        "MB_SPLIT_QUADS 0\n"
        "MB_SMOOTH_ITERS %d\n"
        "EXPORT_VTK 1\n"
        "EXPORT_STARCD 0\n" % smooth_iters)))
    return header, doc, cfg, inner_n, outer_n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=1,
                    help="corner blocks around the ring; reduction is 2*K*(depth-1)")
    ap.add_argument("--depth", type=int, default=13,
                    help="NODE count on each radial")
    ap.add_argument("--ordinary", type=int, default=17,
                    help="NODE count on each ordinary block's inner and outer arc")
    ap.add_argument("--notch", type=float, default=0.0,
                    help="dip the fold node inward by this fraction of the inner "
                         "radius, so the boundary TURNS there")
    ap.add_argument("--embed", action="store_true",
                    help="wrap the ring in an ordinary body ring and far ring, so "
                         "both off-valence nodes become INTERIOR")
    ap.add_argument("--per-unit", type=int, default=3,
                    help="ordinary blocks per corner block; the outer circle "
                         "needs at least 2 arcs and 3 for none to be a half turn")
    ap.add_argument("--r-out", type=float, default=R_OUT_DEFAULT,
                    help="the ring's outer radius; THE RING'S THICKNESS IS A "
                         "QUALITY KNOB, because the corner block tapers from two "
                         "inner arcs to one point across it")
    ap.add_argument("--offset", type=float, default=None,
                    help="rotate the fold centres, degrees; default half a unit "
                         "when --embed and 0 otherwise")
    ap.add_argument("--body-depth", type=int, default=25,
                    help="--embed: NODE count across the body ring")
    ap.add_argument("--far-depth", type=int, default=17,
                    help="--embed: NODE count across the far ring")
    ap.add_argument("--smooth", type=int, default=0)
    ap.add_argument("--stem", default="reducing_annulus")
    a = ap.parse_args()

    header, doc, cfg, inner_n, outer_n = build(
        folds=a.folds, depth=a.depth, ordinary=a.ordinary, notch=a.notch,
        embed=a.embed, smooth_iters=a.smooth, per_unit=a.per_unit,
        body_depth=a.body_depth, far_depth=a.far_depth, offset=a.offset,
        r_out=a.r_out)
    jp = os.path.join(HERE, a.stem + ".json")
    dp = os.path.join(HERE, a.stem + ".dat")
    with open(jp, "w", encoding="utf-8") as f:
        f.write(header + json.dumps(doc, indent=2) + "\n")
    with open(dp, "w", encoding="utf-8") as f:
        f.write(cfg.replace("STEM", a.stem))
    print("wrote %s" % os.path.relpath(jp, ROOT))
    print("wrote %s" % os.path.relpath(dp, ROOT))
    print("inner %d intervals, outer %d, reduction %d, %d blocks in the ring"
          % (inner_n, outer_n, inner_n - outer_n,
             a.folds * (1 + a.per_unit)))


if __name__ == "__main__":
    main()
