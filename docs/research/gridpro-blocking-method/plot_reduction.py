#!/usr/bin/env python3
"""N(r) for the count-reducing blockings of issue #192, beside a shipped one.

Section 15a defined N(r) -- block-partition lines crossing a circle of radius r
-- and 15b measured every blocking in this repo FLAT. This plots the two
#192 step 2 documents against the shipped four-block O-grid, and the point of
the figure is that the two REDUCING documents disagree with each other:

  * the SMALLEST reducing annulus is FLAT, at 4, while its node count falls from
    72 to 48 -- so N(r) does not register a reduction that happens INSIDE a
    block rather than by a block boundary ending;
  * the embedded reducing O-grid FALLS, 16 to 8, and is the first blocking in
    this repo that does.

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


def curve(path, radii):
    pts, cells, blocks = read_vtk(path)
    seam = seam_edges(pts, cells, blocks)
    c = np.array([0.0, 0.0])
    return [crossings(pts, seam, c, r) for r in radii]


def main():
    ra, ro, og = sys.argv[1], sys.argv[2], sys.argv[3]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for path, label, lo, hi, style in (
            (og, "shipped 4-block O-grid (96 -> 96 nodes)", 0.55, 9.5, "k--"),
            (ra, "smallest reducing annulus (72 -> 48)", 1.02, 2.95, "C1-o"),
            (ro, "reducing O-grid, 4 folds (192 -> 96)", 0.55, 9.5, "C0-o")):
        radii = np.linspace(lo, hi, 40)
        ax.plot(radii, curve(path, radii), style, ms=3, label=label)
    ax.set_xscale("log")
    ax.set_xlabel("radius r (the body is at 0.5, the far field at 10)")
    ax.set_ylabel("N(r): block-partition lines crossing the circle")
    ax.set_title("A terminating blocking FALLS. Issue #192, step 2.")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    out = os.path.join(HERE, "reduction_termination.png")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
