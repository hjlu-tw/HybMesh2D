#!/usr/bin/env python3
"""This repo's aerofoil stack beside GridPro's OWN aerofoil, block for block.

``vs_stern_fig4.py`` beside this file compares against the one THIRD-PARTY
published GridPro mesh whose blocking visibly reduces outward -- and that case is
an entry capsule's wake, not an aerofoil. Among the ten third-party papers in
``docs/research/gridpro-meshes-in-published-cfd.md`` the only aerofoil-like
bodies are turbine blades and a propeller, and none of them shows a far field.
**The aerofoil GridPro figures this repo can compare against are the VENDOR's**,
from *The Art and Science of Meshing Airfoil*, and they are already the subject
of ``gridpro-blocking-method.md`` sections 7 and 8.

AND THE VENDOR'S OWN FIGURE BREAKS THAT SURVEY'S PRESENTATION FINDING. Section
14b of the third-party note measured "colour by block: ZERO of ten" -- of ten
third-party papers. GridPro's own aerofoil figure is coloured by block, in three
panels from the far field in to the nose. So the convention this repo adopted in
``plot_two_panel.py`` (grid only, no colour) is what PRACTITIONERS publish, and
colouring by block is what the VENDOR publishes. They are different audiences and
the note should not be read as one rule.

THE SOURCE IMAGE IS NOT COMMITTED and is passed in as a path, the convention
``plot_vs_fig5.py`` and ``plot_vs_video_frame.py`` follow and that
``gridpro-blocking-method.md``'s Sources states::

    curl -sSL -o /tmp/img12.webp \
      https://media.gridpro.com/wp-content/uploads/2017/10/img12.webp

THE PANEL ROWS WERE MEASURED, not guessed: the three panels of that image are
separated by near-white rows at y = 350..359 and 706..717 of its 1064, found by
row brightness rather than by eye.

    python3 docs/research/gridpro-blocking-method/plot_vs_gridpro_airfoil.py \
        /tmp/img12.webp /tmp/cgs.vtk vs_gridpro_airfoil.png
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib.collections import LineCollection, PatchCollection  # noqa: E402
from matplotlib.patches import Polygon as MplPoly                  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_block_partition import read_vtk, seam_edges           # noqa: E402

# view_mesh_vtk.py's palette, so our block colours read the same in every figure
BLOCK_COLORS = ["#f4a742", "#7fb2d9", "#8fc98f", "#d99797",
                "#b9a0d4", "#e3c766", "#8fc9c3", "#c9a98f"]
PANELS = ((3, 349), (360, 705), (718, 1063))     # measured, see the docstring


def ours(ax, pts, cells, blocks, seam, half, centre, lw, slw):
    by = {}
    for ids, b in zip(cells, blocks):
        by.setdefault(b, []).append(MplPoly([pts[v] for v in ids], closed=True))
    for b in sorted(by):
        ax.add_collection(PatchCollection(
            by[b], facecolor=BLOCK_COLORS[b % len(BLOCK_COLORS)],
            edgecolor="none", alpha=0.9))
    allseg = []
    for ids in cells:
        for k in range(len(ids)):
            allseg.append([pts[ids[k]], pts[ids[(k + 1) % len(ids)]]])
    ax.add_collection(LineCollection(np.array(allseg), colors="#33393f",
                                     linewidths=lw))
    ax.add_collection(LineCollection(np.array([[pts[i], pts[j]]
                                               for i, j in seam]),
                                     colors="#0b0b0b", linewidths=slw))
    # THE SAME 2:1 FRAME THE VENDOR PANELS HAVE (700 x 347 px). A square panel
    # beside a 2:1 one compares the crop and not the mesh.
    ax.set_xlim(centre[0] - 2.0 * half, centre[0] + 2.0 * half)
    ax.set_ylim(centre[1] - half, centre[1] + half)
    ax.set_aspect("equal")
    ax.set_axis_off()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("vtk")
    ap.add_argument("out")
    ap.add_argument("--wide", type=float, default=3.4,
                    help="HALF-HEIGHT of the far-field panel; the width is 2x")
    ap.add_argument("--near", type=float, default=0.26,
                    help="HALF-HEIGHT of the nose panel; the width is 2x")
    ap.add_argument("--near-centre", type=float, nargs=2, default=[0.08, 0.0])
    a = ap.parse_args()

    img = np.asarray(Image.open(a.src).convert("RGB"))
    pts, cells, blocks = read_vtk(a.vtk)
    seam = seam_edges(pts, cells, blocks)

    fig, ax = plt.subplots(2, 2, figsize=(13.0, 7.2), facecolor="white")
    for col, (lo, hi), tag in ((0, PANELS[0], "far field"),
                               (1, PANELS[2], "nose")):
        ax[0][col].imshow(img[lo:hi + 1])
        ax[0][col].set_axis_off()
        ax[0][col].set_title("(a%d)  GridPro's own aerofoil, %s — vendor "
                             "figure, source not committed" % (col + 1, tag),
                             fontsize=8.5, loc="left")
    ours(ax[1][0], pts, cells, blocks, seam, a.wide, (0.5, 0.0), 0.12, 0.6)
    ours(ax[1][1], pts, cells, blocks, seam, a.near, a.near_centre, 0.35, 1.6)
    for col, tag in ((0, "far field"), (1, "nose")):
        ax[1][col].set_title("(b%d)  this repo, %s, %s" %
                             (col + 1, os.path.basename(a.vtk), tag),
                             fontsize=8.5, loc="left")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.01,
                        wspace=0.03, hspace=0.10)
    fig.savefig(a.out, dpi=175)
    print("wrote %s" % a.out)
    print("  %d blocks, %d cells; heavy lines are BLOCK boundaries in (b), as "
          "they are colour boundaries in (a)" % (len(set(blocks)), len(cells)))


if __name__ == "__main__":
    main()
