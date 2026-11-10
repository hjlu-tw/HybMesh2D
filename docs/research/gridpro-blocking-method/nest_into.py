#!/usr/bin/env python3
"""Splice a locally nested row into a topology make_ch.py already produced.

WHY A POST-PROCESS. Section 11 built the nest on a purpose-made ring and the
mesh was poor -- 24 stations, straight radials, no clustering -- because that
generator has none of what makes a mesh good. make_ch.py has all of it, so the
nest is spliced into ITS output instead of reimplemented. make_ch.py is not
touched, which is why the eight cases beside this file cannot regress.

THE NEST GOES IN THE OUTER LAYER. Section 11a's rule is that each termination
station's corner on the ring ABOVE must be omitted; put the nest in the wall
layer and that omission falls on an interior ring and has to be merged through
every layer outside it. Put it in the outermost layer and the omission falls on
the FAR FIELD, where the two circumferential edges either side simply merge into
one and nothing propagates further -- there is nothing outside it.

    python3 nest_into.py <topology.json> --at 20 --band 0.45 --out nested.json
"""

import argparse
import json
import os
import re


def load(path):
    return json.loads(re.sub(r"^\s*//.*$", "", open(path).read(), flags=re.M))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topology")
    ap.add_argument("--at", type=int, required=True,
                    help="first station interval of the nest; it spans two")
    ap.add_argument("--band", type=float, default=0.45,
                    help="where the nested ring sits between L1 and the far field")
    ap.add_argument("--taper", type=float, default=0.0,
                    help="pull the two END stations of the nest back toward the "
                         "far field, 0..1, so the diagonals are shallower")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    d = load(args.topology)
    C = {c["id"]: c for c in d["corners"]}
    E = {e["id"]: e for e in d["edges"]}
    B = {b["id"]: b for b in d["blocks"]}
    A = args.at
    stations = [A, A + 1, A + 2]
    need = ["b1_%d" % i for i in (A - 1, A, A + 1, A + 2)] \
         + ["c2_%d" % i for i in (A - 1, A, A + 1, A + 2)] \
         + ["L1_%d" % i for i in stations] + ["F%d" % i for i in range(A - 1, A + 4)]
    missing = [k for k in need if k not in B and k not in E and k not in C]
    if missing:
        raise SystemExit("REFUSED: this topology does not have %s. --at must "
                         "leave two stations either side, and the file must be "
                         "a two-layer make_ch output." % ", ".join(missing[:4]))

    def xy(cid):
        return C[cid]["xy"]

    def mid(a, b, f):
        pa, pb = xy(a), xy(b)
        return [pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f]

    # the nested ring, between L1 and the far field, GRADED. A constant band
    # steps straight down from the far field at the termination and the
    # diagonal then meets it at a near-degenerate angle: measured, the worst
    # corner is 89.9 deg and it sits in the left transition block whatever the
    # band is -- so it is the step, not the depth. Grading the end stations back
    # toward the far field makes both diagonals shallower, which is what
    # GridPro's frame does by spreading each transition over several of them.
    depth = {stations[0]: args.band + (1.0 - args.band) * args.taper,
             stations[1]: args.band,
             stations[2]: args.band + (1.0 - args.band) * args.taper}
    for i in stations:
        d["corners"].append({"id": "X%d" % i, "kind": "free",
                             "xy": mid("L1_%d" % i, "F%d" % i, depth[i])})

    def edge(eid, u, v, kind):
        d["edges"].append({"id": eid, "corners": [u, v], "kind": kind})

    for i in stations:                                   # L1 -> X
        edge("nr%d" % i, "L1_%d" % i, "X%d" % i, "interface")
    edge("nu%d" % (A + 1), "X%d" % (A + 1), "F%d" % (A + 1), "interface")
    for i in (A, A + 1):                                 # along the nested ring
        edge("nx%d" % i, "X%d" % i, "X%d" % (i + 1), "interface")
    edge("dL", "F%d" % (A - 1), "X%d" % A, "interface")
    edge("dR", "X%d" % (A + 2), "F%d" % (A + 3), "interface")
    edge("fmL", "F%d" % (A - 1), "F%d" % (A + 1), "wall")
    edge("fmR", "F%d" % (A + 1), "F%d" % (A + 3), "wall")

    # all THREE station radials go: at A and A+2 the far corner is omitted so
    # the radial stops at X; at A+1 it is split into L1->X and X->far.
    drop_e = {"r1_%d" % i for i in stations} | {"c2_%d" % i for i in
                                                (A - 1, A, A + 1, A + 2)}
    drop_c = {"F%d" % A, "F%d" % (A + 2)}
    drop_b = {"b1_%d" % i for i in (A - 1, A, A + 1, A + 2)}

    d["blocks"] = [b for b in d["blocks"] if b["id"] not in drop_b]
    d["blocks"] += [
        {"id": "ntL", "edges": ["c1_%d" % (A - 1), "nr%d" % A, "dL", "r1_%d" % (A - 1)]},
        {"id": "nlo0", "edges": ["c1_%d" % A, "nr%d" % (A + 1), "nx%d" % A, "nr%d" % A]},
        {"id": "nlo1", "edges": ["c1_%d" % (A + 1), "nr%d" % (A + 2),
                                 "nx%d" % (A + 1), "nr%d" % (A + 1)]},
        {"id": "nup0", "edges": ["nx%d" % A, "nu%d" % (A + 1), "fmL", "dL"]},
        {"id": "nup1", "edges": ["nx%d" % (A + 1), "dR", "fmR", "nu%d" % (A + 1)]},
        {"id": "ntR", "edges": ["c1_%d" % (A + 2), "r1_%d" % (A + 3), "dR",
                                "nr%d" % (A + 2)]},
    ]
    d["edges"] = [e for e in d["edges"] if e["id"] not in drop_e]
    d["corners"] = [c for c in d["corners"] if c["id"] not in drop_c]

    json.dump(d, open(args.out, "w"), indent=1)
    print("wrote %s" % args.out)
    print("  %d corners, %d edges, %d blocks (+2 for the nest)"
          % (len(d["corners"]), len(d["edges"]), len(d["blocks"])))


if __name__ == "__main__":
    main()
