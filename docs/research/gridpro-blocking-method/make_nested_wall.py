#!/usr/bin/env python3
"""An aerofoil O-ring with a LOCALLY NESTED near-wall row.

Section 10 built a terminating row on a flat strip and section 10c said the
obvious next step -- putting one on an aerofoil -- had not been taken. This is
that step.

THE BOOKKEEPING THAT MAKES IT CONFORMAL. A row terminates at a VALENCE-3 corner:
three blocks share one point and each edge leaving it is still a side of exactly
two. Getting there on a ring needs one non-obvious thing: at each termination
station the FAR-FIELD corner is OMITTED. Keep it and the three edges round it
bound a triangular region that no quad can fill -- worked through four
arrangements before this one, and every other left that triangle somewhere.

    python3 docs/research/gridpro-blocking-method/make_nested_wall.py
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_rings import arc_tangent_at                    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BODY = "examples/geometries/naca0012_cgrid.dat"


def read_body(path):
    pts = [tuple(map(float, ln.split()))
           for ln in open(path, encoding="utf-8") if ln.strip()]
    return pts[:-1] if pts[0] == pts[-1] else pts


def resample(poly, n):
    s = [0.0]
    for a, b in zip(poly, poly[1:] + [poly[0]]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    tot = s[-1]
    out = []
    for k in range(n):
        t = tot * k / n
        i = max(j for j in range(len(s) - 1) if s[j] <= t)
        a, b = poly[i], poly[(i + 1) % len(poly)]
        seg = s[i + 1] - s[i]
        u = 0.0 if seg == 0 else (t - s[i]) / seg
        out.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", type=int, default=24)
    ap.add_argument("--nest-at", type=int, default=5,
                    help="first body station of the nest; it spans three")
    ap.add_argument("--far-r", type=float, default=3.0)
    ap.add_argument("--band", type=float, default=0.35,
                    help="where the nested ring sits, as a fraction of the gap")
    ap.add_argument("--wall-ds", type=float, default=0.0,
                    help="first cell height at the wall; 0 leaves the radial "
                         "uniform, which is what the section 11 demonstrator did")
    ap.add_argument("--perp", action="store_true",
                    help="radials leave the body PERPENDICULAR, as an arc "
                         "through their two corners")
    ap.add_argument("--out", default="nested_wall.json")
    args = ap.parse_args()

    N, a = args.stations, args.nest_at
    body = resample(read_body(os.path.join(ROOT, BODY)), N)
    # REVERSED. The shipped polyline starts at the trailing edge and runs over
    # the UPPER surface first, so walking it forward puts the far field on the
    # right and every block winds clockwise -- the mesher refuses by name
    # ("its corners wind clockwise, so every cell in it would be inverted").
    body = body[::-1]
    cx, cy = 0.5, 0.0
    far = []
    for p in body:
        th = math.atan2(p[1] - cy, p[0] - cx)
        far.append((cx + args.far_r * math.cos(th), cy + args.far_r * math.sin(th)))
    nest = [a, (a + 1) % N, (a + 2) % N]          # X lives on these three
    X = {}
    for i in nest:
        X[i] = (body[i][0] + (far[i][0] - body[i][0]) * args.band,
                body[i][1] + (far[i][1] - body[i][1]) * args.band)

    C, E, B = [], [], []
    pos = {}
    def corner(cid, xy):
        C.append({"id": cid, "kind": "free", "xy": list(xy)}); pos[cid] = tuple(xy)
    def edge(eid, u, v, kind="interface", **kw):
        d = {"id": eid, "corners": [u, v], "kind": kind}
        d.update({k: v2 for k, v2 in kw.items() if v2 is not None})
        E.append(d)

    for i in range(N):
        corner("b%d" % i, body[i])
        if i not in (nest[0], nest[2]):           # the OMITTED far corners
            corner("f%d" % i, far[i])
    for i in nest:
        corner("x%d" % i, X[i])

    def fprev(i): return "f%d" % ((i - 1) % N)
    def fnext(i): return "f%d" % ((i + 1) % N)

    # body edges, one per station pair, all wall
    for i in range(N):
        # EVERY station pair is its own circumferential class -- a block's
        # opposite sides are (body, far) and (radial, radial), so the radials
        # chain round the ring as one class while the circumferential ones do
        # not chain at all. Each therefore needs its own seed; the mesher names
        # the first unseeded pair, which is how this was found.
        edge("bs%d" % i, "b%d" % i, "b%d" % ((i + 1) % N), "wall", count=7)
    # far edges: skip the two omitted corners by spanning them
    skip = {nest[0], nest[2]}
    i = 0
    far_edges = []
    while i < N:
        j = (i + 1) % N
        while j in skip:
            j = (j + 1) % N
        far_edges.append((i, j)); i = (j if j > i else N)
    for k, (u, v) in enumerate(far_edges):
        edge("fs%d" % k, "f%d" % u, "f%d" % v, "wall")
    fe = {u: "fs%d" % k for k, (u, v) in enumerate(far_edges)}

    # radials. The WALL clustering and the PERPENDICULAR launch are what turn
    # the section 11 demonstrator into a mesh worth looking at; both are the
    # same mechanisms make_ch.py uses, reached through the same declarations.
    def nrm(i):
        a, b = body[(i - 1) % N], body[(i + 1) % N]
        tx, ty = b[0] - a[0], b[1] - a[1]
        m = math.hypot(tx, ty)
        return (ty / m, -tx / m)

    def radial(eid, i, u, v, **kw):
        sp = {"wall_ends": "start", "ds_start": args.wall_ds} if args.wall_ds else {}
        cv = arc_tangent_at(pos[u], nrm(i), pos[v]) if args.perp else None
        if sp: kw["spacing"] = sp
        if cv: kw["curve"] = cv
        edge(eid, u, v, **kw)

    for i in range(N):
        if i in skip:
            # NO seed here. The transition block's west is a full radial and
            # its east is this short one, so they are OPPOSITE sides of one
            # block and therefore the same equivalence class: body->X and
            # body->far carry the same node count whether that is wanted or
            # not. Seeding both is refused ("two different node counts for
            # edges that are structurally forced to carry one"), which is how
            # this was found.
            radial("r%d" % i, i, "b%d" % i, "x%d" % i)
        elif i == nest[1]:
            radial("r%d" % i, i, "b%d" % i, "x%d" % i)
            edge("ru%d" % i, "x%d" % i, "f%d" % i)
        else:
            radial("r%d" % i, i, "b%d" % i, "f%d" % i,
                   **({"count": 25} if i == 0 else {}))
    for i, j in ((nest[0], nest[1]), (nest[1], nest[2])):
        edge("xs%d" % i, "x%d" % i, "x%d" % j)
    edge("tL", "f%d" % ((nest[0] - 1) % N), "x%d" % nest[0])      # left diagonal
    edge("tR", "x%d" % nest[2], "f%d" % ((nest[2] + 1) % N))      # right diagonal

    for i in range(N):
        j = (i + 1) % N
        if i == (nest[0] - 1) % N:
            B.append({"id": "tl", "edges": ["bs%d" % i, "r%d" % nest[0], "tL", "r%d" % i]})
        elif i == nest[0]:
            B.append({"id": "nl0", "edges": ["bs%d" % i, "r%d" % nest[1], "xs%d" % i, "r%d" % i]})
            B.append({"id": "nu0", "edges": ["xs%d" % i, "ru%d" % nest[1],
                                             fe[(nest[0] - 1) % N], "tL"]})
        elif i == nest[1]:
            B.append({"id": "nl1", "edges": ["bs%d" % i, "r%d" % nest[2], "xs%d" % i, "r%d" % i]})
            B.append({"id": "nu1", "edges": ["xs%d" % i, "tR", fe[nest[1]], "ru%d" % i]})
        elif i == nest[2]:
            B.append({"id": "tr", "edges": ["bs%d" % i, "r%d" % j, "tR", "r%d" % i]})
        else:
            B.append({"id": "c%d" % i, "edges": ["bs%d" % i, "r%d" % j, fe[i], "r%d" % i]})

    out = os.path.join(HERE, args.out)
    json.dump({"format_version": 1, "corners": C, "edges": E, "blocks": B},
              open(out, "w"), indent=1)
    print("wrote %s" % os.path.relpath(out, ROOT))
    print("  %d corners, %d edges, %d blocks; nest on body stations %s"
          % (len(C), len(E), len(B), nest))


if __name__ == "__main__":
    main()
