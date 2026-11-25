#!/usr/bin/env python3
"""Section 29's figure: the radial-fan QUILT beside the C/H, at matched cells.

    python3 docs/research/gridpro-blocking-method/plot_quilt_vs_control.py \
        "<label>=<left_quads.vtk>" "<label>=<right_quads.vtk>" <out.png>

Labels follow ``plot_reduction.py``'s ``label=path`` convention, and the BLOCK
COUNT is appended from each mesh's own block field rather than typed into the
label -- the first cut of this script wrote "54 blocks" into the caption as a
literal and a later run drew an 82-block mesh under it unchanged.

Each case gets a near-field panel and a whole-domain panel, with the BLOCKS
filled by colour and the block boundaries drawn heavy over a greyed grid --
because the complaint section 29 answers is about the PARTITION, not the grid,
and section 24 of the sibling note records that copying a published figure's
grid-only convention is how that question got dropped once already.

The caption carries the sector-width ratio, which is the complaint measured:
a far field cut into 24 EVEN sectors and one cut into 4 wide wedges plus 20
narrow ones have the SAME N(r), and only this figure separates them.
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK",
                                          "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt                                   # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_block_partition import (read_vtk, seam_edges,          # noqa: E402
                                     sector_gaps)

INK, SEC, MUT, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
NEAR = (-0.55, 1.75, -0.65, 0.65)
WHOLE = (-2.3, 4.3, -3.3, 3.3)
PALETTE = plt.get_cmap("tab20").colors


def panel(ax, pts, cells, blocks, seam, win, grid_lw):
    ids = sorted(set(blocks))
    ax.add_collection(PolyCollection(
        [pts[list(c)] for c in cells],
        facecolors=[PALETTE[ids.index(b) % len(PALETTE)] for b in blocks],
        edgecolors="none", alpha=0.42, zorder=1))
    edges = set()
    for c in cells:
        for k in range(len(c)):
            edges.add(tuple(sorted((c[k], c[(k + 1) % len(c)]))))
    ax.add_collection(LineCollection([[pts[a], pts[b]] for a, b in edges],
                                     colors=GRID, linewidths=grid_lw, zorder=2))
    ax.add_collection(LineCollection([[pts[a], pts[b]] for a, b in seam],
                                     colors=INK, linewidths=1.25, zorder=3))
    ax.set_xlim(win[0], win[1]); ax.set_ylim(win[2], win[3])
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(GRID)


def main():
    left, right, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pair = []
    for spec in (left, right):
        # rpartition on a bare path returns ("", "", spec), so taking `label`
        # as the name gave an EMPTY caption and made this fallback unreachable
        if "=" in spec:
            label, _, path = spec.rpartition("=")
        else:
            label, path = os.path.basename(spec).replace(".vtk", ""), spec
        pair.append((path, label))
    fig = plt.figure(figsize=(13.4, 7.4), facecolor="#fcfcfb")
    fig.text(0.024, 0.962, "§29：兩個 block 分區並排，格數配對",
             color=INK, fontsize=15.5, va="top")
    fig.text(0.024, 0.925,
             "填色＝block，粗線＝block 邊界，淡線＝網格。抱怨的是分區不是網格，所以兩者都畫。",
             color=SEC, fontsize=11, va="top")
    for col, (path, name) in enumerate(pair):
        pts, cells, blocks = read_vtk(path)
        seam = seam_edges(pts, cells, blocks)
        name = "%s（%d blocks，%d cells）" % (name, len(set(blocks)), len(cells))
        g = sector_gaps(pts, seam, np.array([0.5, 0.0]), 2.0)
        if len(g) < 2:
            raise SystemExit("%s: a circle of r = 2 about (0.5, 0) crosses fewer "
                             "than two block boundaries, so there are no sector "
                             "widths to report -- is this a block-field mesh?" % path)
        for row, (win, lw) in enumerate(((NEAR, 0.35), (WHOLE, 0.16))):
            ax = fig.add_axes([0.024 + col * 0.495, 0.455 - row * 0.405,
                               0.455, 0.345])
            panel(ax, pts, cells, blocks, seam, win, lw)
            if row == 0:
                ax.text(0.0, 1.045, name, transform=ax.transAxes, color=INK,
                        fontsize=12.5, va="bottom")
        fig.text(0.024 + col * 0.495, 0.038,
                 "r = 2 的扇段角寬：最窄 %.1f°、中位 %.1f°、最寬 %.1f°，最寬/最窄 = %.2f"
                 % (g[0], float(np.median(g)), g[-1], g[-1] / g[0]),
                 color=SEC, fontsize=11.2, va="bottom")
    fig.savefig(out, dpi=104, facecolor="#fcfcfb")
    print("wrote", out)


if __name__ == "__main__":
    main()
