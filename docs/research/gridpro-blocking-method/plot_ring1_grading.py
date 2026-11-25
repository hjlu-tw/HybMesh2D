#!/usr/bin/env python3
"""Section 29h's figure: the SIZE STEP across ring 1, with and without --match-ring1.

    python3 docs/research/gridpro-blocking-method/plot_ring1_grading.py \
        <without_quads.vtk> <with_quads.vtk> <out.png>

This draws the GRID, not the block partition, because what 29h changes is a cell
size and the partition is identical between the two meshes -- a block figure
would show nothing at all. Ring 1, the wrap ellipse the step sits on, is drawn
over the grid so the eye has the seam the numbers are measured on.

The caption's ratios are DERIVED here, over the pairs whose BOTH endpoints lie
on that ellipse, which is the same selection 29h's table uses -- a mesh-wide
adjacent_area_ratio_max does not move between these two meshes and would
report the fix as having done nothing.
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
from matplotlib.collections import LineCollection                  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_block_partition import read_vtk                       # noqa: E402

INK, SEC, GRID = "#0b0b0b", "#52514e", "#b9b7ae"
# The wrap ellipse (cx, cy, a, b) that ring 1 IS. make_rings.py prints it as
# "ring 1: centre (x, y)  a A  b B", so --ring1 takes it rather than trusting
# this default: a different --rings or --blend moves it and the default then
# selects NOTHING, which the first version of this reported as a crash in
# r.max() rather than as the wrong seam.
RING1 = (0.5, 0.0, 0.9, 0.3)
# A TIGHT window ON the seam, not the whole body: what --match-ring1 changes is
# the LAST row of cells inside ring 1, which at body scale is one thin line and
# the first draft of this figure showed two panels that looked identical.
WIN = (0.02, 0.92, 0.10, 0.46)


def on_ring1(p, tol=0.04):
    cx, cy, a, b = RING1
    return abs(((p[0] - cx) / a) ** 2 + ((p[1] - cy) / b) ** 2 - 1.0) < tol


def ratios(pts, cells, blocks):
    def area(ids):
        P = pts[list(ids)]
        x, y = P[:, 0], P[:, 1]
        return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    A = [area(c) for c in cells]
    own = {}
    for ci, c in enumerate(cells):
        for k in range(len(c)):
            own.setdefault(tuple(sorted((c[k], c[(k + 1) % len(c)]))), []).append(ci)
    out = []
    for e, o in own.items():
        if len(o) != 2 or blocks[o[0]] == blocks[o[1]]:
            continue
        if on_ring1(pts[e[0]]) and on_ring1(pts[e[1]]):
            out.append(max(A[o[0]], A[o[1]]) / max(1e-30, min(A[o[0]], A[o[1]])))
    return np.sort(np.array(out))


def main():
    global RING1
    argv = sys.argv[1:]
    if "--ring1" in argv:
        i = argv.index("--ring1")
        RING1 = tuple(float(v) for v in argv[i + 1:i + 5])
        del argv[i:i + 5]
    if len(argv) != 3:
        raise SystemExit("usage: plot_ring1_grading.py [--ring1 cx cy a b] "
                         "<without_quads.vtk> <with_quads.vtk> <out.png>")
    a_path, b_path, out = argv
    fig = plt.figure(figsize=(13.2, 5.6), facecolor="#fcfcfb")
    fig.text(0.024, 0.968, "§29h：ring 1 交界的尺寸台階，--match-ring1 之前與之後",
             color=INK, fontsize=15, va="top")
    fig.text(0.024, 0.916,
             "畫的是網格不是 block 分區——兩張網格的分區完全相同，分區圖會什麼都看不出來。"
             "紅線是 ring 1（包覆橢圓），台階就在它上面。",
             color=SEC, fontsize=10.6, va="top")
    t = np.linspace(0, 2 * np.pi, 400)
    cx, cy, ea, eb = RING1
    ring = np.column_stack([cx + ea * np.cos(t), cy + eb * np.sin(t)])
    for col, (path, title) in enumerate(((a_path, "沒有 --match-ring1"),
                                         (b_path, "有 --match-ring1"))):
        pts, cells, blocks = read_vtk(path)
        edges = set()
        for c in cells:
            for k in range(len(c)):
                edges.add(tuple(sorted((c[k], c[(k + 1) % len(c)]))))
        ax = fig.add_axes([0.028 + col * 0.492, 0.165, 0.452, 0.70])
        ax.add_collection(LineCollection([[pts[x], pts[y]] for x, y in edges],
                                         colors=GRID, linewidths=0.75, zorder=1))
        ax.plot(ring[:, 0], ring[:, 1], color="#c0392b", lw=1.8, zorder=3)
        ax.set_xlim(WIN[0], WIN[1]); ax.set_ylim(WIN[2], WIN[3])
        ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color(GRID)
        r = ratios(pts, cells, blocks)
        if len(r) == 0:
            raise SystemExit("%s: no block-boundary pair has BOTH ends on the "
                             "ellipse (%g, %g, %g, %g). That is the wrong ring 1 "
                             "for this mesh -- pass --ring1 cx cy a b, which "
                             "make_rings.py prints." % ((path,) + RING1))
        ax.text(0.0, 1.03, title, transform=ax.transAxes, color=INK,
                fontsize=12.5, va="bottom")
        fig.text(0.028 + col * 0.492, 0.075,
                 "跨 ring 1 的 %d 個相鄰面積對：中位 %.2f、p95 %.2f、最大 %.2f"
                 % (len(r), np.median(r), np.percentile(r, 95), r.max()),
                 color=SEC, fontsize=11.4, va="bottom")
    fig.savefig(out, dpi=112, facecolor="#fcfcfb")
    print("wrote", out)


if __name__ == "__main__":
    main()
