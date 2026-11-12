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


# label -> (lo, hi, style). A curve not listed here is drawn over the whole
# domain in the next free colour.
KNOWN = {
    "shipped 4-block O-grid (96 -> 96 nodes)": (0.55, 9.5, "k--"),
    "smallest reducing annulus (72 -> 48)": (1.02, 2.95, "C1-"),
    "reducing O-grid, 4 folds (192 -> 96)": (0.55, 9.5, "C0-"),
    "reducing STACK, 2 stages (192 -> 48)": (0.55, 9.5, "C2-"),
    "reducing STACK, 3 stages (192 -> 24)": (0.55, 9.5, "C3-"),
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--out=")]
    out = next((a[6:] for a in sys.argv[1:] if a.startswith("--out=")),
               os.path.join(HERE, "reduction_termination.png"))
    pairs = []
    for a in args:
        label, _, path = a.rpartition("=")
        pairs.append((path, label or path))
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for i, (path, label) in enumerate(pairs):
        lo, hi, style = KNOWN.get(label, (0.55, 9.5, "C%d-" % (4 + i)))
        # Dense, and deliberately INCLUDING the two interface radii rather than
        # stepping over them: `curve` blanks them and the dotted lines say why.
        radii = np.unique(np.r_[np.geomspace(lo, hi, 400), INTERFACE_R])
        radii = radii[(radii >= lo) & (radii <= hi)]
        ax.plot(radii, curve(path, radii), style, lw=1.2, label=label)
    for r in INTERFACE_R:
        ax.axvline(r, color="0.6", ls=":", lw=1)
    ax.text(0.015, 0.05, "dotted: the SINGLE-RING case's two interfaces, where "
            "N(r) counts the whole circle (109, 105) and means nothing. Every "
            "stack has its own such radii, not drawn.",
            transform=ax.transAxes, fontsize=7, color="0.4")
    ax.set_xscale("log")
    ax.set_xlabel("radius r (the body is at 0.5, the far field at 10)")
    ax.set_ylabel("N(r): block-partition lines crossing the circle")
    ax.set_yscale("log"); ax.set_yticks([4, 8, 16, 32, 64])
    ax.set_yticklabels(["4", "8", "16", "32", "64"])
    ax.set_title("A terminating blocking FALLS. One ring is a step; a STACK is "
                 "a staircase")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
