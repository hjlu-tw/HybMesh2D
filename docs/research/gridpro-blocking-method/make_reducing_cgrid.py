#!/usr/bin/env python3
"""THE SHIPPED C-GRID WITH THE COUNT REDUCTION IN IT — issue #192, step 3.

A RESEARCH HARNESS beside ``docs/research/nesting-blocks-at-a-complicated-leading-edge.md``
section 16, which carries the full record. Nothing shipped reads it; nothing in
``config/``, ``examples/``, ``src/`` or ``include/`` is written or changed by it.
It reads the two geometry files the shipped C-grid reads and adds none.

WHAT IT BUILDS, and why this is the case #188 asked for. The ten-block chain
C-grid (#191) put 97 nodes on each aerofoil surface and measured that the far
field inherits every one of them: a chain junction is valence 4, so the body's
node count and the far field's are equal at every radius. This document keeps
that aerofoil and gives the far field back the FOUR-BLOCK case's own counts, by
putting #192's corner block into the outer band:

    aerofoil       97 nodes per surface   (the chain case's)
    the seam       192 intervals over the two surfaces
    the far field   96 intervals over the two nose segments (the four-block
                    case's 48 + 48), 24 per outlet (unchanged)

The reduction is 96 intervals and a corner block ends twice its band's radial
depth, so the default is SIX corner blocks in a band 8 intervals deep. The
radial budget is the shipped cases' own 40, split 24 / 8 / 8 over three bands.

THE GEOMETRY IS THE CHAIN CASE'S. The seam is the same declared ellipse, centre
(1, 0), a = 2, b = 1, cut at 4K stations evenly spaced in ARC LENGTH rather than
at that case's four. The far field is the same six-segment D. The only curve this
file introduces is the MID ellipse below, where the reducing band ends. Nothing
else is drawn here that is not derived from those two files and that one conic.

THE FOLD STATIONS ARE PULLED OFF THE ELLIPSE, inward, by ``--notch``. A fold is
a corner of the corner block and of nothing else, so if the seam ran smoothly
through it the single cell there would have to span the seam's own 180 degrees.
Pulled in, the seam TURNS there and that cell is an ordinary one; the two arcs
either side stop being ellipse arcs and are declared as the chords they are.

MEASURED 2026-11-12, at the defaults — which are the committed documents', and
the two commands that write them are in those files' own headers:

    python3 .../make_reducing_cgrid.py --stem reducing_cgrid
    python3 .../make_reducing_cgrid.py --control --stem reducing_cgrid_control

Against #191's three-row table, in the same bins and with that gate's own ruler
(`bin_added_cells.py` beside this file prints the table and imports those
helpers rather than re-implementing them):

    the REDUCING document    8448 quads, 0 inverted, nonortho max 69.0 mean 24.4
                             2688 added over the shipped four-block C-grid, of
                             which 89.4% land within one chord
    --control, the SAME      9600 quads, 0 inverted, nonortho max 69.0 mean 22.1
    three bands with no      3840 added, 62.5% within one chord
    corner block

So the reduction buys 1152 quads, 30% of what the refinement costs. GATE 1 passes
only at ``MB_SMOOTH_ITERS 0``; at the shipped default of 20 the reducing document
has 120 inverted cells. GATE 2 FAILS — ``Average norm is a nan`` at iteration 20
— **and so does the control, at the same iteration**, so what that measures is
this three-band construction and not the reduction. Section 16e names the two
figures behind it that were not chased.

    python3 docs/research/gridpro-blocking-method/make_reducing_cgrid.py
    ./run.sh -conf docs/research/gridpro-blocking-method/reducing_cgrid.dat
    ./run_pipeline.sh docs/research/gridpro-blocking-method/reducing_cgrid_demo.json
"""

import argparse
import itertools
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BODY = "naca0012_cgrid.dat"
FAR = "cgrid_farfield.dat"
SEAM = {"kind": "ellipse", "centre": [1.0, 0.0], "a": 2.0, "b": 1.0}


def seg_table(name):
    """[(seg, cumulative arc length array, points)] for a .dat + .meta pair."""
    import numpy as np
    pts = np.loadtxt(os.path.join(ROOT, "examples/geometries", name))
    rows = [l.split() for l in
            open(os.path.join(ROOT, "examples/geometries", name + ".meta"),
                 encoding="utf-8").read().splitlines()]
    i = next(k for k, r in enumerate(rows) if r and r[0] == "POINTS")
    seg = [int(r[0]) for r in rows[i + 1:i + 1 + len(pts)]]
    out, start = [], 0
    for key, grp in itertools.groupby(seg):
        n = len(list(grp))
        if out and key == out[0][0]:            # the closing wrap point
            break
        sl = pts[start:start + n + 1] if start + n < len(pts) else pts[start:]
        d = np.r_[0.0, np.cumsum(np.hypot(*(sl[1:] - sl[:-1]).T))]
        out.append((key, d, sl))
        start += n
    return out


def station_at_fraction(table, segs, frac):
    """(seg, t) at `frac` of the TOTAL arc length over the listed segments."""
    lens = [table[s][1][-1] for s in segs]
    target = frac * sum(lens)
    for s, L in zip(segs, lens):
        if target <= L or s == segs[-1]:
            return {"seg": s, "t": min(1.0, max(0.0, target / L))}
        target -= L
    raise AssertionError


# The MID curve, where the reducing band ends and the ordinary far band starts.
# The same family as the seam, scaled: putting the reduction in a band of its own
# rather than letting the corner block run all the way to the far field is not a
# refinement, it is the difference between a mesh and one whose apex cells are 86
# degrees off orthogonal -- measured, on the two-band version this replaced.
def mid_curve(gap):
    return {"kind": "ellipse", "centre": [1.0, 0.0],
            "a": SEAM["a"] + gap, "b": SEAM["b"] + gap}


def ellipse_point_on(c, t):
    return [round(c["centre"][0] + c["a"] * math.cos(t), 12),
            round(c["centre"][1] + c["b"] * math.sin(t), 12)]


def ellipse_point(t):
    return ellipse_point_on(SEAM, t)


def ellipse_even(n, t0, t1, samples=20001):
    """`n`+1 parameters from t0 to t1, evenly spaced in ARC LENGTH."""
    ts = [t0 + (t1 - t0) * k / (samples - 1) for k in range(samples)]
    cum, acc = [0.0], 0.0
    for k in range(1, samples):
        p, q = ellipse_point(ts[k - 1]), ellipse_point(ts[k])
        acc += math.hypot(q[0] - p[0], q[1] - p[1])
        cum.append(acc)
    out, j = [], 0
    for k in range(n + 1):
        target = acc * k / n
        while j + 1 < samples and cum[j + 1] < target:
            j += 1
        out.append(ts[min(j, samples - 1)] if k else t0)
    out[-1] = t1
    return out


# The wake cut's node count, the shipped C-grid's own, which this document does
# not vary: the reduction is over the AEROFOIL and the wake is carried through.
WAKE_NODES = 25


def build(folds=6, notch=0.12, total_iv=40, gap=0.6, control=False):
    MID = mid_curve(gap)
    far_t = seg_table(FAR)
    K = folds
    stations = 4 * K                      # seam and aerofoil arcs over the body
    per_arc = 192 // stations             # intervals on each of them
    red_iv = 48 // K                      # the reducing band's radial depth
    far_iv = red_iv                       # the ordinary band beyond it
    inner_iv = total_iv - red_iv - far_iv
    assert per_arc * stations == 192 and 2 * K * red_iv == 96 and inner_iv > 0

    corners, edges, blocks = [], [], []
    seen = set()

    def add(c):
        if c["id"] not in seen:
            seen.add(c["id"])
            corners.append(c)
        return c["id"]

    # ---- ring 0, the body: te, 2 * (stations/2 - 1) stations, te -----------
    body = []
    for k in range(stations + 1):
        if k in (0, stations):
            cid = "te"
            add({"id": cid, "kind": "on_geometry", "geom": BODY, "seg": 0,
                 "t": 0.0})
        elif k == stations // 2:
            cid = "le"
            add({"id": cid, "kind": "on_geometry", "geom": BODY, "seg": 1,
                 "t": 0.0})
        else:
            cid = "b%d" % k
            seg = 0 if k < stations // 2 else 1
            loc = (k if seg == 0 else k - stations // 2) / (stations / 2.0)
            add({"id": cid, "kind": "on_geometry", "geom": BODY, "seg": seg,
                 "t": round(loc, 12)})
        body.append(cid)

    # ---- ring 1, the seam: the chain case's ellipse, cut evenly by arc -----
    folds_at = {4 * j + 2 for j in range(K)}     # centred, so they mirror
    tt = ellipse_even(stations, 0.5 * math.pi, 1.5 * math.pi)
    seam = []
    for k in range(stations + 1):
        p = ellipse_point(tt[k])
        if k in folds_at:
            cx, cy = SEAM["centre"]
            p = [round(cx + (p[0] - cx) * (1.0 - notch), 12),
                 round(cy + (p[1] - cy) * (1.0 - notch), 12)]
        seam.append(add({"id": "s%d" % k, "kind": "free", "xy": p}))

    # ---- ring 2, the MID curve, where the reducing band ends ---------------
    # THE CONTROL is this document with its corner blocks replaced by ordinary
    # ones and nothing else changed: the same three bands, the same radial
    # counts, the same curves, the same station placement -- and therefore 4K
    # arcs on the mid curve and on the far field instead of 2K, which is the far
    # field inheriting all 192 of the aerofoil's intervals. It exists so that a
    # quality figure on the reducing document can be read as the REDUCTION's
    # rather than as this construction's.
    outer_arcs = (4 if control else 2) * K
    ut = ellipse_even(outer_arcs, 0.5 * math.pi, 1.5 * math.pi)
    mid = [add({"id": "u%d" % k, "kind": "free",
                "xy": ellipse_point_on(MID, ut[k])})
           for k in range(outer_arcs + 1)]

    # ---- ring 3, the far field ---------------------------------------------
    for cid, seg, t in (("wk", 0, 0.0), ("fu", 1, 0.0), ("f1", 2, 0.0),
                        ("f2", 3, 0.0), ("f3", 4, 0.0), ("fl", 5, 0.0),
                        ("sw1_up", 0, 0.1), ("sw1_lo", 5, 0.9),
                        ("sw2_up", 0, 0.4), ("sw2_lo", 5, 0.6)):
        add({"id": cid, "kind": "on_geometry", "geom": FAR, "seg": seg, "t": t})
    far = []
    for k in range(outer_arcs + 1):
        if k == 0:
            far.append("f1")
        elif k == outer_arcs:
            far.append("f3")
        elif k == outer_arcs // 2:
            far.append("f2")
        else:
            loc = station_at_fraction(far_t, [2, 3], k / float(outer_arcs))
            far.append(add({"id": "x%d" % k, "kind": "on_geometry",
                            "geom": FAR, "seg": loc["seg"],
                            "t": round(loc["t"], 12)}))

    def edge(eid, a, b, kind, count=None, curve=None, bind=None, spacing=None):
        e = {"id": eid, "corners": [a, b], "kind": kind}
        if count:
            e["count"] = count
        if curve:
            e["curve"] = dict(curve)
        if bind is not None:
            e["binding"] = {"geom": bind[0], "seg": bind[1]}
        if spacing:
            e["spacing"] = spacing
        edges.append(e)
        return eid

    # ---- band A: body -> seam ----------------------------------------------
    for k in range(stations):
        seg = 0 if k < stations // 2 else 1
        edge("af%d" % k, body[k], body[k + 1], "wall", per_arc + 1,
             bind=(BODY, seg))
        edge("m%d" % k, seam[k], seam[k + 1], "interface",
             curve=None if (k in folds_at or k + 1 in folds_at) else SEAM)
    for k in range(stations + 1):
        edge("rA%d" % k, body[k], seam[k], "interface",
             inner_iv + 1 if k == 0 else None,
             spacing={"wall_ends": "start"})
    for k in range(stations):
        blocks.append({"id": "A%d" % k,
                       "edges": ["rA%d" % k, "m%d" % k, "rA%d" % (k + 1),
                                 "af%d" % k]})

    # ---- band B: seam -> mid, the REDUCING band ----------------------------
    for k in range(outer_arcs):
        edge("n%d" % k, mid[k], mid[k + 1], "interface", curve=MID)
    if control:
        for k in range(stations + 1):
            edge("rB%d" % k, seam[k], mid[k], "interface",
                 red_iv + 1 if k == 0 else None)
        for k in range(stations):
            blocks.append({"id": "B%d" % k,
                           "edges": ["rB%d" % k, "n%d" % k, "rB%d" % (k + 1),
                                     "m%d" % k]})
    for j in range(0 if not control else K, K):
        s0, s1, s3, s4 = 4 * j, 4 * j + 1, 4 * j + 3, 4 * j + 4
        edge("rB%d_a" % j, seam[s0], mid[2 * j], "interface",
             red_iv + 1 if j == 0 else None)
        edge("rB%d_b" % j, seam[s1], mid[2 * j + 1], "interface")
        edge("rB%d_c" % j, seam[s3], mid[2 * j + 1], "interface")
        if j == K - 1:
            edge("rB%d_d" % j, seam[s4], mid[2 * j + 2], "interface")
        nxt = ("rB%d_d" % j) if j == K - 1 else ("rB%d_a" % (j + 1))
        blocks.append({"id": "B%d_0" % j,
                       "edges": ["rB%d_a" % j, "n%d" % (2 * j), "rB%d_b" % j,
                                 "m%d" % s0]})
        # THE CORNER BLOCK. Both of its radials end at mid[2j+1], so that point
        # is a corner of it and of both its neighbours, and its two seam arcs
        # reach the mid curve nowhere.
        blocks.append({"id": "C%d" % j,
                       "edges": ["rB%d_b" % j, "rB%d_c" % j,
                                 "m%d" % (4 * j + 2), "m%d" % s1]})
        blocks.append({"id": "B%d_1" % j,
                       "edges": ["rB%d_c" % j, "n%d" % (2 * j + 1), nxt,
                                 "m%d" % s3]})

    # ---- band C: mid -> far field, ordinary --------------------------------
    for k in range(outer_arcs):
        edge("ff%d" % k, far[k], far[k + 1], "wall",
             bind=(FAR, 2 if k < outer_arcs // 2 else 3))
    for k in range(outer_arcs + 1):
        edge("rC%d" % k, mid[k], far[k], "interface",
             far_iv + 1 if k == 0 else None)
    for k in range(outer_arcs):
        blocks.append({"id": "D%d" % k,
                       "edges": ["rC%d" % k, "ff%d" % k, "rC%d" % (k + 1),
                                 "n%d" % k]})

    # ---- the wake column, three bands deep ---------------------------------
    edge("wake", "te", "wk", "cut", WAKE_NODES,
         spacing={"ds_start": 0.005})
    edge("w1_up", seam[0], "sw1_up", "interface", spacing={"ds_start": 0.005})
    edge("w1_lo", seam[stations], "sw1_lo", "interface",
         spacing={"ds_start": 0.005})
    edge("w2_up", mid[0], "sw2_up", "interface", spacing={"ds_start": 0.005})
    edge("w2_lo", mid[outer_arcs], "sw2_lo", "interface",
         spacing={"ds_start": 0.005})
    edge("o1_up", "wk", "sw1_up", "wall", bind=(FAR, 0),
         spacing={"wall_ends": "start"})
    edge("o2_up", "sw1_up", "sw2_up", "wall", bind=(FAR, 0))
    edge("o3_up", "sw2_up", "fu", "wall", bind=(FAR, 0))
    edge("o1_lo", "wk", "sw1_lo", "wall", bind=(FAR, 5),
         spacing={"wall_ends": "start"})
    edge("o2_lo", "sw1_lo", "sw2_lo", "wall", bind=(FAR, 5))
    edge("o3_lo", "sw2_lo", "fl", "wall", bind=(FAR, 5))
    edge("e_ff_up", "fu", "f1", "wall", bind=(FAR, 1))
    edge("e_ff_lo", "f3", "fl", "wall", bind=(FAR, 4))
    blocks.append({"id": "WA_up", "edges": ["o1_up", "w1_up", "rA0", "wake"]})
    blocks.append({"id": "WA_lo",
                   "edges": ["rA%d" % stations, "w1_lo", "o1_lo", "wake"]})
    blocks.append({"id": "WB_up",
                   "edges": ["o2_up", "w2_up",
                             "rB0" if control else "rB0_a", "w1_up"]})
    blocks.append({"id": "WB_lo",
                   "edges": ["rB%d" % stations if control
                             else "rB%d_d" % (K - 1), "w2_lo", "o2_lo",
                             "w1_lo"]})
    blocks.append({"id": "WC_up", "edges": ["o3_up", "e_ff_up", "rC0", "w2_up"]})
    blocks.append({"id": "WC_lo",
                   "edges": ["rC%d" % outer_arcs, "e_ff_lo", "o3_lo",
                             "w2_lo"]})

    return {"format_version": 1, "corners": corners, "edges": edges,
            "blocks": blocks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notch", type=float, default=0.12)
    ap.add_argument("--folds", type=int, default=6)
    ap.add_argument("--total-iv", type=int, default=40,
                    help="radial intervals from the body to the far field; the "
                         "shipped C-grid spends 40 and so does this by default")
    ap.add_argument("--control", action="store_true",
                    help="the same three bands with NO corner block, so the far "
                         "field inherits all 192 intervals")
    ap.add_argument("--gap", type=float, default=0.6,
                    help="how far the MID curve stands outside the seam; the "
                         "reducing band's whole radial span")
    ap.add_argument("--smooth", type=int, default=0,
                    help="MB_SMOOTH_ITERS for the written config. ZERO is the "
                         "default here and not the shipped 20 because at 20 this "
                         "document has 120 inverted cells and the shipped one "
                         "has none — see the docstring")
    ap.add_argument("--stem", default="reducing_cgrid")
    a = ap.parse_args()
    doc = build(folds=a.folds, notch=a.notch, total_iv=a.total_iv, gap=a.gap,
                control=a.control)
    # The generating command goes in the file, as in make_reducing_annulus.py.
    header = (
        "// THE SHIPPED C-GRID WITH A COUNT REDUCTION IN IT (issue #192 step 3)\n"
        "// — GENERATED by make_reducing_cgrid.py %s\n"
        "// beside this file. Do not hand-edit; re-run that command.\n"
        % " ".join(sys.argv[1:]))
    with open(os.path.join(HERE, a.stem + ".json"), "w", encoding="utf-8") as f:
        f.write(header + json.dumps(doc, indent=2) + "\n")
    cfg = ("# GENERATED by make_reducing_cgrid.py "
           + " ".join(sys.argv[1:]) + " — #192 step 3.\n"
           
           "MESH_MODE 1\n"
           "MESH_TOPOLOGY_FILE docs/research/gridpro-blocking-method/%s.json\n"
           "GEOM_FILE examples/geometries/%s\n"
           "DOMAIN_FILE examples/geometries/%s nobl\n"
           "BL_INITIAL_THICKNESS 0.001\n"
           "MB_SPLIT_QUADS 0\n"
           "MB_SMOOTH_ITERS %d\n"
           "BC_GEOM wall\n"
           "EXPORT_VTK 1\n"
           "EXPORT_STARCD 0\n" % (a.stem, BODY, FAR, a.smooth))
    with open(os.path.join(HERE, a.stem + ".dat"), "w", encoding="utf-8") as f:
        f.write(cfg)
    print("wrote %s.json / %s.dat with %d blocks"
          % (a.stem, a.stem, len(doc["blocks"])))


if __name__ == "__main__":
    main()
