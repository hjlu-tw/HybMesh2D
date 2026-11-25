#!/usr/bin/env python3
"""Section 29i's figure: the sliver on the far-field boundary, before and after.

    python3 docs/research/gridpro-blocking-method/plot_farfield_sliver.py \
        <before_quads.vtk> <after_quads.vtk> <out.png>

Draws the GRID at the outer boundary where the trailing-edge ray lands, and
fills the WORST adjacent pair in each mesh so the thing the number is about is
visible rather than asserted. The window is derived from the worst pair's own
position in the FIRST mesh, so the two panels show the same place and the
"after" panel is not quietly recentred on its own worst pair somewhere else --
which is the whole point, since 29i's result is that the worst pair MOVES.

The caption's ratio is computed here over block-boundary pairs, the same
quantity the quality line calls adjacent_area_ratio_seam_max.
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
from measure_block_partition import read_vtk                       # noqa: E402

INK, SEC, GRID, HOT = "#0b0b0b", "#52514e", "#b9b7ae", "#c0392b"


def areas(pts, cells):
    out = []
    for ids in cells:
        P = pts[list(ids)]
        x, y = P[:, 0], P[:, 1]
        out.append(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))
    return out


def worst_seam_pair(pts, cells, blocks):
    """(ratio, the two cell indices, the midpoint of their shared edge)."""
    A = areas(pts, cells)
    own = {}
    for ci, c in enumerate(cells):
        for k in range(len(c)):
            own.setdefault(tuple(sorted((c[k], c[(k + 1) % len(c)]))), []).append(ci)
    best = (0.0, None, None)
    for e, o in own.items():
        if len(o) != 2 or blocks[o[0]] == blocks[o[1]]:
            continue
        r = max(A[o[0]], A[o[1]]) / max(1e-30, min(A[o[0]], A[o[1]]))
        if r > best[0]:
            best = (r, o, (pts[e[0]] + pts[e[1]]) / 2.0)
    return best


def panel(ax, pts, cells, blocks, win, hot):
    edges = set()
    for c in cells:
        for k in range(len(c)):
            edges.add(tuple(sorted((c[k], c[(k + 1) % len(c)]))))
    ax.add_collection(LineCollection([[pts[a], pts[b]] for a, b in edges],
                                     colors=GRID, linewidths=0.9, zorder=1))
    if hot:
        ax.add_collection(PolyCollection([pts[list(cells[ci])] for ci in hot],
                                         facecolors=HOT, alpha=0.5,
                                         edgecolors=HOT, linewidths=1.3, zorder=3))
    ax.set_xlim(win[0], win[1]); ax.set_ylim(win[2], win[3])
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(GRID)


def main():
    before, after, out = sys.argv[1], sys.argv[2], sys.argv[3]
    data = [read_vtk(before), read_vtk(after)]
    r0, o0, c0 = worst_seam_pair(*data[0])
    # the window is the FIRST mesh's worst pair, used for both panels
    h = 0.42
    win = (c0[0] - h, c0[0] + h, c0[1] - h, c0[1] + h)

    fig = plt.figure(figsize=(11.6, 6.4), facecolor="#fcfcfb")
    fig.text(0.024, 0.965, "§29i：外邊界上的 sliver，--far-uniform 之前與之後",
             color=INK, fontsize=15, va="top")
    fig.text(0.024, 0.918,
             "兩格畫的是同一個位置——第一張網格最差相鄰對的所在，不是各自的最差對，"
             "因為 29i 的結果正是最差對會「移走」。紅色是該網格的最差相鄰對。",
             color=SEC, fontsize=10.5, va="top")
    for col, ((pts, cells, blocks), title) in enumerate(
            ((data[0], "沒有 --far-uniform"), (data[1], "有 --far-uniform（＋--match-ring1）"))):
        r, o, c = worst_seam_pair(pts, cells, blocks)
        inside = abs(c[0] - c0[0]) < h and abs(c[1] - c0[1]) < h
        ax = fig.add_axes([0.028 + col * 0.492, 0.165, 0.452, 0.68])
        panel(ax, pts, cells, blocks, win, o if inside else None)
        ax.text(0.0, 1.03, title, transform=ax.transAxes, color=INK,
                fontsize=12.5, va="bottom")
        where = ("在本格內" if inside
                 else "不在本格內 —— 已移到 r = %.2f" % np.hypot(c[0] - 1.0, c[1]))
        fig.text(0.028 + col * 0.492, 0.075,
                 "最差相鄰面積比 %.2f，%s" % (r, where),
                 color=SEC, fontsize=11.4, va="bottom")
    fig.savefig(out, dpi=112, facecolor="#fcfcfb")
    print("wrote", out)


if __name__ == "__main__":
    main()
