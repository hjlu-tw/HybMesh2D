#!/usr/bin/env python3
"""The smallest topology that asks for a 2-into-1 TERMINATION, and is refused.

WHY THIS FILE EXISTS. Section 15 claims the declaration model cannot express the
nest the icing video teaches -- GridPro's manual says "for each layer THREE
corners are substituted for each corner on the previous layer", i.e. three lines
becoming one. A claim of inexpressibility is worth nothing as prose: this writes
the minimal document that asks for it and hands it to the real mesher, so the
refusal is the mesher's own text rather than an argument.

THE SHAPE. Two blocks side by side; one block above spanning both; the radial
between the lower two TERMINATES at their shared top corner.

        t0 ------------------- t2        <- one block, T
        |          T          |
        m0 ------- m1 ------- m2         <- `n0` and `n1`, two edges
        |    L     |     R    |
        b0 ------- b1 ------- b2

T's south must be ONE edge, so it can name `n0` or `n1` and not both -- and the
one it does not name is then a side of a single block, which the arity rule
refuses by name. That is the whole of it: a block has four sides, each exactly
one edge, so a circumferential line cannot be split below and whole above, and a
radial can therefore never terminate without a replacement line.

NOT A BUG, and do not "fix" it. The arity rule is what makes welding allocation
rather than comparison (`.claude/rules/mesher-multiblock.md`). What section 15
concludes is that a terminating nest needs a DIFFERENT expressiveness -- a side
that is a CHAIN of edges -- not that this refusal is wrong.

    python3 docs/research/gridpro-blocking-method/make_merge_refusal.py
    ./run.sh -conf docs/research/gridpro-blocking-method/merge_refusal.dat
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

DOC = {
    "format_version": 1,
    "corners": [
        {"id": "b0", "kind": "free", "xy": [0, 0]},
        {"id": "b1", "kind": "free", "xy": [1, 0]},
        {"id": "b2", "kind": "free", "xy": [2, 0]},
        {"id": "m0", "kind": "free", "xy": [0, 1]},
        {"id": "m1", "kind": "free", "xy": [1, 1]},
        {"id": "m2", "kind": "free", "xy": [2, 1]},
        {"id": "t0", "kind": "free", "xy": [0, 2]},
        {"id": "t2", "kind": "free", "xy": [2, 2]},
    ],
    "edges": [
        {"id": "s0", "corners": ["b0", "b1"], "kind": "wall", "count": 5},
        {"id": "s1", "corners": ["b1", "b2"], "kind": "wall", "count": 5},
        {"id": "w0", "corners": ["b0", "m0"], "kind": "wall", "count": 4},
        {"id": "r1", "corners": ["b1", "m1"], "kind": "interface"},
        {"id": "e0", "corners": ["b2", "m2"], "kind": "wall"},
        {"id": "n0", "corners": ["m0", "m1"], "kind": "interface"},
        {"id": "n1", "corners": ["m1", "m2"], "kind": "interface"},
        {"id": "wT", "corners": ["m0", "t0"], "kind": "wall"},
        {"id": "eT", "corners": ["m2", "t2"], "kind": "wall"},
        {"id": "tT", "corners": ["t0", "t2"], "kind": "wall"},
    ],
    # T names `n0` as its south. `n1` is then a side of ONE block, and that is
    # what the mesher names. Naming `n1` instead moves the refusal to `n0`.
    "blocks": [
        {"id": "L", "edges": ["s0", "r1", "n0", "w0"]},
        {"id": "R", "edges": ["s1", "e0", "n1", "r1"]},
        {"id": "T", "edges": ["n0", "eT", "tT", "wT"]},
    ],
}

CONF = """MESH_MODE 1
MESH_TOPOLOGY_FILE docs/research/gridpro-blocking-method/merge_refusal.json
MB_SPLIT_QUADS 0
MB_SMOOTH_ITERS 0
EXPORT_VTK 1
EXPORT_STARCD 0
"""

if __name__ == "__main__":
    j = os.path.join(HERE, "merge_refusal.json")
    d = os.path.join(HERE, "merge_refusal.dat")
    json.dump(DOC, open(j, "w", encoding="utf-8"), indent=1)
    open(d, "w", encoding="utf-8").write(CONF)
    for p in (j, d):
        print("wrote %s" % os.path.relpath(p, ROOT))
    print("\nExpected: EXIT 8, HYBMESH_ERROR 8 TOPOLOGY, naming edge 'n1'.")
