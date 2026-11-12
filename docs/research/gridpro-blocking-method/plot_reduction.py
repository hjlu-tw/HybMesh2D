#!/usr/bin/env python3
"""N(r) for the count-reducing blockings of issue #192, beside a shipped one.

Section 15a defined N(r) -- block-partition lines crossing a circle of radius r
-- and 15b measured every blocking in this repo FLAT. This plots the two
#192 step 2 documents against the shipped four-block O-grid, and the point of
the figure is that the two REDUCING documents disagree with each other:

  * the SMALLEST reducing annulus is FLAT, at 4, while its node count falls from
    72 to 48 -- so N(r) does not register a reduction that happens INSIDE a
    block rather than by a block boundary ending;
  * the embedded reducing O-grid FALLS, 16 to 8 -- and the full shape is 16,
    then 20 over the notched folds, then 12, then 8, so it RISES once before it
    falls. The first draft of this figure sampled 40 points and missed that.

AND N(r) SPIKES WHERE A BLOCK BOUNDARY *IS* THE CIRCLE: 109 at exactly r = 1 and
105 at exactly r = 1.8, the two ring interfaces, because every edge lying on the
circle counts as crossing it. That is the instrument's own artefact and not a
property of the blocking, so those radii are drawn as dotted lines and their
values are excluded from the curve rather than quietly missed by a coarse grid.

    ./run.sh -conf docs/research/gridpro-blocking-method/reducing_annulus.dat \\
        -out_name /tmp/ra
    ./run.sh -conf docs/research/gridpro-blocking-method/reducing_ogrid.dat \\
        -out_name /tmp/ro
    ./run.sh -conf config/multiblock_ogrid.dat -out_name /tmp/og
    python3 docs/research/gridpro-blocking-method/plot_reduction.py \\
        /tmp/ra.vtk /tmp/ro.vtk /tmp/og.vtk
"""

import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                 # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_block_partition import crossings, read_vtk, seam_edges  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


# The two radii at which a ring interface of `reducing_ogrid` is itself a circle
# about the origin, where N(r) counts the whole interface and means nothing.
INTERFACE_R = (1.0, 1.8)
SPIKE = 40          # above this, the circle is lying along a block boundary


def curve(path, radii):
    pts, cells, blocks = read_vtk(path)
    seam = seam_edges(pts, cells, blocks)
    c = np.array([0.0, 0.0])
    out = [crossings(pts, seam, c, r) for r in radii]
    return [np.nan if n > SPIKE else n for n in out]


def main():
    ra, ro, og = sys.argv[1], sys.argv[2], sys.argv[3]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for path, label, lo, hi, style in (
            (og, "shipped 4-block O-grid (96 -> 96 nodes)", 0.55, 9.5, "k--"),
            (ra, "smallest reducing annulus (72 -> 48)", 1.02, 2.95, "C1-o"),
            (ro, "reducing O-grid, 4 folds (192 -> 96)", 0.55, 9.5, "C0-o")):
        # Dense, and deliberately INCLUDING the two interface radii rather than
        # stepping over them: `curve` blanks them and the dotted lines say why.
        radii = np.unique(np.r_[np.geomspace(lo, hi, 400), INTERFACE_R])
        radii = radii[(radii >= lo) & (radii <= hi)]
        ax.plot(radii, curve(path, radii), style, ms=2, lw=1.1, label=label)
    for r in INTERFACE_R:
        ax.axvline(r, color="0.6", ls=":", lw=1)
    ax.text(0.015, 0.06, "dotted: the two ring interfaces, where N(r) counts "
            "the whole circle (109 and 105) and means nothing",
            transform=ax.transAxes, fontsize=7, color="0.4")
    ax.set_xscale("log")
    ax.set_xlabel("radius r (the body is at 0.5, the far field at 10)")
    ax.set_ylabel("N(r): block-partition lines crossing the circle")
    ax.set_title("A terminating blocking FALLS — and rises once first. #192 step 2")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    out = os.path.join(HERE, "reduction_termination.png")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
