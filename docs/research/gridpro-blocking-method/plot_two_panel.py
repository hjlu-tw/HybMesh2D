#!/usr/bin/env python3
"""A mesh drawn the way the one on-point published GridPro figure draws it.

``docs/research/gridpro-meshes-in-published-cfd.md`` section 1 found the single
most on-point presentation in that whole search, and it is a PAIR:

    Figure 4  a near-field zoom, which is where you can see the lines STOP
    Figure 5  the whole domain, which is what SURVIVES to the boundary

Stern, Barnhardt, Venkatapathy, Candler & Prabhu, IEEE Aerospace 2012. This
script draws a ``MESH_MODE 1`` mesh in that format, and the format is as much
about what it LEAVES OUT as what it shows -- section 14b of that note measured
the conventions and they are narrow:

  * NO COLOUR BY BLOCK. Zero of the ten papers coloured a mesh figure by block;
    the only coloured mesh figure in the set marks boundary conditions. So this
    draws black cell edges on white and nothing else, which is deliberately the
    opposite of ``tools/scripts/view_mesh_vtk.py`` -- that one answers "which
    block is this cell in", this one answers "where does the line stop".
  * NO AXES, NO FRAME, NO LEGEND, NO TITLE INSIDE THE PANEL. The published
    figures carry their numbers in a caption, so the caption is printed to
    stdout for pasting rather than burnt into the image.
  * THE ZOOM AND THE WHOLE DOMAIN ARE ONE DELIVERABLE. Either alone is what the
    other eight papers did, and section 14b records that it answers less.

    ./run.sh -conf docs/research/gridpro-blocking-method/reducing_stack_deep.dat \
        -out_name /tmp/rsd              # needs MB_SPLIT_QUADS 0
    python3 docs/research/gridpro-blocking-method/plot_two_panel.py \
        /tmp/rsd.vtk --zoom 3.2 --out /tmp/two_panel.png
"""

import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                  # noqa: E402
from matplotlib.collections import LineCollection                # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_block_partition import read_vtk                     # noqa: E402


def cell_edges(pts, cells):
    """Every distinct cell edge, once, as a segment array."""
    seen = set()
    seg = []
    for ids in cells:
        n = len(ids)
        for k in range(n):
            a, b = ids[k], ids[(k + 1) % n]
            key = (a, b) if a < b else (b, a)
            if key in seen:
                continue
            seen.add(key)
            seg.append([pts[a], pts[b]])
    return np.array(seg)


def panel(ax, seg, half, lw):
    ax.add_collection(LineCollection(seg, colors="k", linewidths=lw))
    ax.set_xlim(-half, half)
    ax.set_ylim(-half, half)
    ax.set_aspect("equal")
    ax.set_axis_off()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vtk")
    ap.add_argument("--zoom", type=float, default=3.2,
                    help="half-width of the near-field panel")
    ap.add_argument("--full", type=float, default=10.2,
                    help="half-width of the whole-domain panel")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    pts, cells, blocks = read_vtk(a.vtk)
    seg = cell_edges(pts, cells)
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 6.3))
    panel(axes[0], seg, a.zoom, 0.35)
    panel(axes[1], seg, a.full, 0.18)
    for ax, tag in zip(axes, ("(a)", "(b)")):
        ax.text(0.02, 0.02, tag, transform=ax.transAxes, fontsize=11)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01,
                        wspace=0.02)
    out = a.out or os.path.splitext(a.vtk)[0] + "_two_panel.png"
    fig.savefig(out, dpi=200)
    print("wrote %s" % out)
    print()
    print("CAPTION, in the published figures' own voice — the numbers are this")
    print("mesh's and are printed rather than burnt into the image:")
    print("  (a) Near field. The grid is refined at the body while being")
    print("      comparatively coarse away from it; the lines leaving each")
    print("      refined band END on the seam above it.")
    print("  (b) Wide view of the same mesh. %d blocks, %d cells."
          % (len(set(blocks)), len(cells)))


if __name__ == "__main__":
    main()
