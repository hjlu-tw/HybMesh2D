#!/usr/bin/env python3
"""The shipped C-grid's BLOCK PARTITION, drawn in section 29's quilt convention.

    # the solver's mesh is triangles; the partition reads on quads
    sed 's/^MB_SPLIT_QUADS.*//' config/multiblock_cgrid.dat > /tmp/cg_quads.dat
    printf '\nMB_SPLIT_QUADS 0\n' >> /tmp/cg_quads.dat
    ./run.sh -conf /tmp/cg_quads.dat          # OVERWRITES results/meshes/multiblock_cgrid/
    cp results/meshes/multiblock_cgrid/mesh_multiblock_cgrid.vtk /tmp/cgrid_quads.vtk
    ./run.sh -conf config/multiblock_cgrid.dat    # restore the shipped mesh
    python3 docs/research/our-cgrid-vs-gridpro/plot_cgrid_partition.py \
        /tmp/cgrid_quads.vtk docs/research/our-cgrid-vs-gridpro/partition.png

WHY A SECOND RUN. ``MB_SPLIT_QUADS 0`` is the diagnostic the config banner names
("the solver cannot use quads"), and it is needed here because the convention
this script borrows measures the partition with ``seam_edges``, which skips any
cell that is not a quad -- by its own contract, since a split quad's diagonal is
not a block boundary. Run against the shipped triangles it returns ZERO seam
edges and would draw a mesh with no partition at all. The restore line is not
optional: the output base comes from the case, so the diagnostic run lands on
top of the shipped mesh that the surface gate and the golden comparator read.

THE CONVENTION IS BORROWED, NOT INVENTED. Block fill by colour, the grid pale,
the partition heavy -- ``plot_quilt_vs_gridpro.py``'s own words for it are that
this is "GridPro's own convention here and the opposite of what practitioners
publish". Same three colours and the same line weights, so the two figures can
be put side by side without the eye having to re-calibrate. The sibling census
measured colour-by-block in 12 of 50 documents, so "the opposite of what
practitioners publish" is now a narrower claim than when it was written; the
convention is kept because the COMPARISON is with GridPro's own figures.

EVERY NUMBER IN A CAPTION IS DERIVED FROM THE MESH. Block count and cells per
block come from the `block` cell field, the quad count from the cell list, the
seam length from ``seam_edges``, and each panel's span from the point bounds.
Nothing is written in. That rule is this repo's, bought in the script this one
borrows from: its first cut wrote "2 rings x 24 sectors, 54 blocks" into the
caption as a literal and drew the THREE-ring mesh under it unchanged.

WHAT IS NOT HERE. No GridPro panel is placed beside ours. Matching a scale is a
READING with an error bar -- the quilt script read a chord at 140 +- 15 px of a
700 px panel and said so -- and no such reading has been taken for the aerofoil
figures in ``gridpro-mesh-samples/``. Putting the two at unmatched scale would
be the kind of comparison this repo keeps finding and deleting.
"""
import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                     # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection   # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "gridpro-blocking-method"))
from measure_block_partition import read_vtk, seam_edges            # noqa: E402

INK, SEC, GRID = "#0b0b0b", "#52514e", "#e1e0d9"
# tab20, STRIDED BY TWO, and the stride is the one deliberate deviation from the
# borrowed convention. tab20 is built as ten colour PAIRS, a saturated member
# then a pale one; the quilt it was chosen for has 54 to 82 blocks, so adjacent
# declaration indices land on different hues anyway. A FOUR-block mesh lands on
# indices 0..3, i.e. two hues in two shades each, and the upper and lower wall
# blocks then read as one block lit differently -- which is the exact thing this
# figure exists to show. Striding takes the saturated member of four pairs.
PALETTE = plt.get_cmap("tab20").colors[::2]


def draw(ax, pts, cells, blocks, seam, box, grid_lw):
    ids = sorted(set(blocks))
    ax.add_collection(PolyCollection(
        [pts[list(c)] for c in cells],
        facecolors=[PALETTE[ids.index(b) % len(PALETTE)] for b in blocks],
        edgecolors="none", alpha=0.46, zorder=1))
    edges = set()
    for c in cells:
        for k in range(len(c)):
            edges.add(tuple(sorted((c[k], c[(k + 1) % len(c)]))))
    ax.add_collection(LineCollection([[pts[x], pts[y]] for x, y in edges],
                                     colors=GRID, linewidths=grid_lw, zorder=2))
    ax.add_collection(LineCollection([[pts[x], pts[y]] for x, y in seam],
                                     colors=INK, linewidths=1.15, zorder=3))
    ax.set_xlim(box[0], box[1]); ax.set_ylim(box[2], box[3])
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(GRID)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vtk"); ap.add_argument("out")
    a = ap.parse_args()
    pts, cells, blocks = read_vtk(a.vtk)
    if any(len(c) != 4 for c in cells):
        raise SystemExit(
            "REFUSED: %s carries cells that are not quads, so the partition "
            "cannot be measured from it. Re-run the case with MB_SPLIT_QUADS 0 "
            "-- see this script's docstring." % a.vtk)
    seam = seam_edges(pts, cells, blocks)
    if len(seam) == 0:
        raise SystemExit("REFUSED: no seam edge found, so there is no partition "
                         "to draw. A single-block mesh is not this figure.")
    ids = sorted(set(blocks))
    per = {b: sum(1 for x in blocks if x == b) for b in ids}
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    # Each view is an explicit box, and each row of the figure is sized to that
    # box's own aspect. Deriving the row height instead of fixing it is what
    # stops `set_aspect("equal")` letterboxing a wide view and cropping a square
    # one -- the first cut of this script fixed the half-height at 0.30 of the
    # half-width for all four and cut the nose off the leading-edge panel.
    x0, x1, y0, y1 = float(lo[0]), float(hi[0]), float(lo[1]), float(hi[1])
    views = [("whole domain", (x0, x1, y0, y1)),
             ("body and near wake", (-0.6, 3.0, -0.95, 0.95)),
             ("leading edge", (-0.09, 0.17, -0.085, 0.085)),
             ("far wake, to the outlet", (1.0, x1, -1.5, 1.5))]
    WIDTH = 11.0
    heights = [WIDTH * (b[3] - b[2]) / (b[1] - b[0]) + 0.42 for _, b in views]
    fig, axes = plt.subplots(len(views), 1, figsize=(WIDTH, sum(heights)),
                             gridspec_kw={"height_ratios": heights})
    for ax, (name, box) in zip(np.atleast_1d(axes), views):
        span = box[1] - box[0]
        draw(ax, pts, cells, blocks, seam, box, 0.16 if span > 8 else 0.34)
        ax.set_title("%s   —   x %.4g‥%.4g,  y %.4g‥%.4g" %
                     (name, box[0], box[1], box[2], box[3]),
                     fontsize=9, color=SEC, loc="left", pad=4)
    caption = ("%d blocks, %d quads (%s), %d seam edges   ·   domain "
               "x %.4g‥%.4g, y %.4g‥%.4g   ·   block fill by declaration index, "
               "grid pale, partition heavy" %
               (len(ids), len(cells),
                " + ".join(str(per[b]) for b in ids), len(seam),
                lo[0], hi[0], lo[1], hi[1]))
    fig.suptitle(caption, fontsize=9, color=SEC, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.988))
    fig.savefig(a.out, dpi=170)
    print("wrote", a.out)
    print(caption)


if __name__ == "__main__":
    main()
