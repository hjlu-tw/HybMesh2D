#!/usr/bin/env python3
"""TARGET: entry 17, Figures 6.15 and 6.16 -- the 2-D cylinder case.

A RESEARCH HARNESS. Nothing shipped reads it; nothing in ``config/``,
``examples/``, ``src/`` or ``include/`` is written or changed by it.

WHAT THE TARGET IS. ``entry17-allampalli2010-fig6-15-complete-grid-2d-cylinder-case.png``
is a circular far field of radius 25 about a cylinder of radius 0.5, cut into
FOUR blocks by the two axes -- green upper-left, cyan upper-right, red
lower-left, blue lower-right -- and ``...fig6-16-close-up-view-grid-near-cylinder.png``
is the same grid at |x|, |y| < 2.4. It is a four-block O-grid and nothing else.

WHY THIS ONE IS FIRST. It is the one target of the eight that this repo already
ships a case for: ``config/multiblock_ogrid.dat`` +
``examples/topology/ogrid_circle.json`` is the SAME topology on the SAME body
radius. Only three numbers differ -- the far-field radius (25 against 10) and
the two node counts -- so this file is a density change to a shipped
declaration, and that is the honest way to report it.

DENSITY, MEASURED OFF THE FIGURE rather than guessed. ``measure_target.py``
counts grid lines crossing a circle drawn on the image: 430 at r = 18.8 on
fig6-15, still rising with radius, and the ink fraction says the image is at the
limit of what it can resolve rather than that the count has stopped. So the
target carries AT LEAST 430 radial lines and the picture cannot say how many
more. 480 is what this file declares -- 120 per quadrant -- which reproduces
the figure's moire at the published pixel size.

    python3 docs/research/allampalli-2010-reproductions/make_cylinder.py [--run]
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mblib                                            # noqa: E402

HERE = mblib.HERE
REL = os.path.relpath(HERE, mblib.ROOT)

BODY_R = 0.5
FAR_R = 25.0
PER_QUARTER = 120          # circumferential INTERVALS per block -> 480 around
RADIAL = 257               # nodes along each radial -> 256 intervals
FACET_MULT = 4             # facets per interval on both circles (#94: a whole
                           # number, so no node lands mid-facet)
WALL_DS = 0.005            # 1% of the radius; the circumferential spacing at
                           # the wall is 2*pi*0.5/480 = 0.00654, so the first
                           # cell is very nearly square


def circle_segs(r, per_quarter_facets):
    """Four quarter arcs of a circle, each INCLUDING both endpoints."""
    n = 4 * per_quarter_facets

    def at(k):
        a = 2.0 * math.pi * k / n
        return (r * math.cos(a), r * math.sin(a))

    return [[at(k) for k in range(s * per_quarter_facets,
                                  (s + 1) * per_quarter_facets + 1)]
            for s in range(4)]


def build():
    facets = PER_QUARTER * FACET_MULT
    body = mblib.write_geom("cyl_body", circle_segs(BODY_R, facets),
                            ["wall"] * 4)
    far = mblib.write_geom("cyl_far", circle_segs(FAR_R, facets),
                           ["farfield"] * 4)

    t = mblib.Topo()
    for s in range(4):
        a = math.radians(90 * s)
        t.onbody("b%d" % s, body, s, 0.0,
                 (BODY_R * math.cos(a), BODY_R * math.sin(a)))
        t.onbody("f%d" % s, far, s, 0.0,
                 (FAR_R * math.cos(a), FAR_R * math.sin(a)))

    # The four radials are ONE equivalence class that wraps around and closes:
    # only r0 seeds the count, the other three are propagated by the blocks.
    for s in range(4):
        t.edge("r%d" % s, "b%d" % s, "f%d" % s, "interface",
               count=(RADIAL if s == 0 else None),
               spacing={"wall_ends": "start"})
    for s in range(4):
        t.edge("w%d" % s, "b%d" % s, "b%d" % ((s + 1) % 4), "wall",
               count=PER_QUARTER + 1,   # one class PER QUADRANT: a block's two
               # j-sides are its body arc and its far arc, so nothing
               # propagates AROUND the ring and all four must be seeded
               binding={"geom": body, "seg": s})
        t.edge("o%d" % s, "f%d" % s, "f%d" % ((s + 1) % 4), "wall",
               binding={"geom": far, "seg": s})
    for s in range(4):
        t.block("q%d" % s, ["b%d" % s, "f%d" % s,
                            "f%d" % ((s + 1) % 4), "b%d" % ((s + 1) % 4)])

    t.write("cylinder.json", header="""
TARGET: entry 17 (Allampalli 2010), Figures 6.15 and 6.16 -- the 2-D cylinder.

WRITTEN BY docs/research/allampalli-2010-reproductions/make_cylinder.py.
Do not hand-edit: the two circles' .meta sidecars are written by the same run
and a corner here is an arc-length position on one of them.

A four-block O-grid, topologically identical to the shipped
examples/topology/ogrid_circle.json. Only the far-field radius and the two node
counts differ, and both counts are read off the published figure rather than
chosen (see the generator's docstring).
""")

    confs = mblib.write_pair(
        "cylinder", "cylinder.json",
        ["GEOM_FILE %s/%s" % (REL, body),
         "DOMAIN_FILE %s/%s nobl" % (REL, far)],
        WALL_DS,
        title="TARGET: entry 17, Figures 6.15 and 6.16 -- the 2-D cylinder case.")
    print("cylinder: %s" % t.stats())
    print("  %d quads = 4 x %d x %d" %
          (4 * PER_QUARTER * (RADIAL - 1), PER_QUARTER, RADIAL - 1))
    return confs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    confs = build()
    ok = True
    if a.run:
        for c in confs:
            ok = mblib.summarise(mblib.run(c), os.path.basename(c)) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
