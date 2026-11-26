#!/usr/bin/env python3
"""Draw a ``MESH_MODE 1`` mesh the way the target figures are drawn, and put it
beside its target.

A RESEARCH HARNESS. Nothing shipped reads it.

WHY NOT ``tools/scripts/view_mesh_vtk.py``. That one FILLS each cell with a
pastel colour and draws the block boundaries heavy, which is the right picture
for "which block is this cell in". The eight target figures are Tecplot's
"mesh, coloured by zone": the grid LINES carry the block's colour on a white
page, there is no fill, and no boundary is drawn heavy. Comparing a fill to a
wireframe by eye is comparing two renderings and not two meshes, so this file
reproduces the target's own rendering instead.

TWO CONSEQUENCES, both deliberate. The palette here is Tecplot's saturated one
rather than the viewer's qualitative pastels, and it is given PER CASE so that
a block can be drawn in the colour the published figure gave the same region --
otherwise every comparison starts with the reader matching colours. And the
mesh drawn is the UNSPLIT one (``MB_SPLIT_QUADS 0``): the targets are
structured grids with no diagonals, so drawing the split export would put a
diagonal through every cell that is in neither the target nor the structured
mesh this repo's quality instrument measures.

    python3 docs/research/allampalli-2010-reproductions/plot.py <mesh.vtk> <out.png> \
        [--window x0 x1 y0 y1] [--palette red,green,...] [--target <fig.png>] \
        [--title ...] [--lw 0.3]
"""

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from matplotlib.collections import LineCollection            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "..", "gridpro-mesh-samples")

# Tecplot's own zone colours, in the order it assigns them. The targets use
# exactly these, which is why a reproduction can be made to match colour for
# colour rather than only shape for shape.
TECPLOT = {
    "red": "#ff0000", "green": "#00c000", "blue": "#0000ff",
    "cyan": "#00c0c0", "magenta": "#ff00ff", "yellow": "#e0d000",
    "black": "#000000", "orange": "#ff8000", "purple": "#8000ff",
    "grey": "#808080", "pink": "#ff80c0", "olive": "#808000",
    "teal": "#008080", "navy": "#000080", "lime": "#80ff00",
    "brown": "#a05000",
}
DEFAULT = ["red", "green", "blue", "cyan", "magenta", "yellow", "black",
           "orange", "purple", "grey", "pink", "olive", "teal", "navy",
           "lime", "brown"]


def read_vtk(path):
    """``(points, cells, block_index_per_cell)`` from a legacy VTK file."""
    pts, cells, blocks = [], [], None
    with open(path) as f:
        toks = f.read().split()
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        if t == "POINTS":
            npts = int(toks[i + 1])
            i += 3
            for _ in range(npts):
                pts.append((float(toks[i]), float(toks[i + 1])))
                i += 3
            continue
        if t == "CELLS":
            total = int(toks[i + 2])
            i += 3
            end = i + total
            while i < end:
                c = int(toks[i])
                i += 1
                cells.append([int(toks[i + j]) for j in range(c)])
                i += c
            continue
        if t == "SCALARS" and i + 1 < n and toks[i + 1] == "block":
            j = i + 4
            if j < n and toks[j] == "LOOKUP_TABLE":
                j += 2
            blocks = [int(toks[j + k]) for k in range(len(cells))]
            i = j + len(cells)
            continue
        i += 1
    return pts, cells, blocks


def edges_by_block(pts, cells, blocks):
    """Unique undirected cell edges, grouped by block index."""
    seen = {}
    for k, c in enumerate(cells):
        b = 0 if blocks is None else blocks[k]
        for j in range(len(c)):
            a, z = c[j], c[(j + 1) % len(c)]
            key = (a, z) if a < z else (z, a)
            # A seam edge belongs to two blocks; the lower index draws it, so
            # nothing is drawn twice and no seam goes missing.
            if key not in seen or b < seen[key]:
                seen[key] = b
    out = {}
    for (a, z), b in seen.items():
        out.setdefault(b, []).append((pts[a], pts[z]))
    return out


def draw(ax, path, palette, lw, window=None):
    pts, cells, blocks = read_vtk(path)
    groups = edges_by_block(pts, cells, blocks)
    for b in sorted(groups):
        name = palette[b % len(palette)]
        ax.add_collection(LineCollection(
            groups[b], colors=TECPLOT.get(name, name), linewidths=lw))
    if window:
        ax.set_xlim(window[0], window[1])
        ax.set_ylim(window[2], window[3])
    else:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        mx, my = 0.02 * (max(xs) - min(xs)), 0.02 * (max(ys) - min(ys))
        ax.set_xlim(min(xs) - mx, max(xs) + mx)
        ax.set_ylim(min(ys) - my, max(ys) + my)
    ax.set_aspect("equal")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    return len(cells), (max(blocks) + 1 if blocks else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh")
    ap.add_argument("out")
    ap.add_argument("--window", nargs=4, type=float)
    ap.add_argument("--palette", default=",".join(DEFAULT))
    ap.add_argument("--target")
    ap.add_argument("--title", default="")
    ap.add_argument("--target-title", default="")
    ap.add_argument("--lw", type=float, default=0.3)
    ap.add_argument("--size", type=float, default=7.0)
    a = ap.parse_args()

    pal = [s.strip() for s in a.palette.split(",") if s.strip()]
    if a.target:
        import matplotlib.image as mpimg
        img = mpimg.imread(a.target if os.path.isabs(a.target)
                           else os.path.join(SAMPLES, a.target))
        fig, axes = plt.subplots(1, 2, figsize=(2 * a.size, a.size))
        axes[0].imshow(img)
        axes[0].set_axis_off()
        axes[0].set_title(a.target_title or "GridPro (published figure)",
                          fontsize=11)
        ncell, nblk = draw(axes[1], a.mesh, pal, a.lw, a.window)
        axes[1].set_title(a.title or "this repo, MESH_MODE 1 — %d blocks, %d quads"
                          % (nblk, ncell), fontsize=11)
    else:
        fig, ax = plt.subplots(figsize=(a.size, a.size))
        ncell, nblk = draw(ax, a.mesh, pal, a.lw, a.window)
        ax.set_title(a.title or "%d blocks, %d quads" % (nblk, ncell),
                     fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(a.out, dpi=150, facecolor="white")
    print("wrote %s  (%d blocks, %d cells)" % (a.out, nblk, ncell))
    return 0


if __name__ == "__main__":
    sys.exit(main())
