#!/usr/bin/env python3
"""Section 29's quilt beside GridPro's OWN ring-fan figure, at a matched scale.

    curl -sSL -A Mozilla/5.0 -o /tmp/img12.webp \
      https://media.gridpro.com/wp-content/uploads/2017/10/img12.webp
    python3 docs/research/gridpro-blocking-method/plot_quilt_vs_gridpro.py \
        /tmp/img12.webp <quilt quads>.vtk out.png

WHICH PANEL, AND WHY. `img12.webp` is three stacked panels, separated by bright
rows at y = 350..358 and 706..713 of its 1064 -- re-derived here by row
brightness, and the committed reading of 350..359 / 706..717 reproduces. The
MIDDLE one is the figure this section is about: it is the only published GridPro
figure showing a single aerofoil inside a RADIAL FAN CUT INTO CONCENTRIC BANDS,
which is what section 29's quilt is. The top panel is a mid-field zoom at 2.3
chords and the bottom is the nose.

THE SCALE IS A READING, not a measurement, and the frames are matched on it.
Segmenting the body automatically does not work on this image -- it is heavily
compressed with the blocks painted over the grid, and three attempts returned
runs that are plainly not the body -- so the chord was read off a 2x crop by eye
at 140 +- 15 px of the panel's 700, i.e. the panel spans 5.0 +- 0.5 chords. That
is the same kind of reading, with the same kind of error bar, as section 24's;
section 20b's "an automated count bounced between 7 and 21, which is not a
measurement" is why it is stated this way rather than dressed up.

WHAT THE COMPARISON IS FOR. Not the grid -- the PARTITION. Our side fills the
blocks by colour and draws the partition heavy, which is GridPro's own
convention here and the opposite of what practitioners publish (the sibling
note's section 14b measured colour-by-block at zero of ten papers).

EVERY COUNT IN THE CAPTION IS DERIVED, none is written in. The block count comes
from the mesh's own block field and the ring and sector counts from the topology
document's header, passed as --topo. The first cut of this script wrote "2 rings
x 24 sectors, 54 blocks" into the caption as a literal and then drew the
THREE-ring mesh under it unchanged -- which is the figure class this repo keeps
finding, a caption that does not read its own input.
"""
import argparse
import os
import re
import sys

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK",
                                          "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection   # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_block_partition import read_vtk, seam_edges            # noqa: E402

INK, SEC, GRID = "#0b0b0b", "#52514e", "#e1e0d9"
PALETTE = plt.get_cmap("tab20").colors
CHORDS_WIDE = 5.0          # the middle panel's own span, read off it
NOSE_WIDE = 0.95           # ours; the vendor nose panel's scale is NOT readable


def panels(src):
    """The three panels of img12, split at the bright rows, re-derived."""
    im = Image.open(src).convert("RGB")
    rows = np.asarray(im).astype(float).mean(axis=(1, 2))
    hot = np.where(rows > np.percentile(rows, 98.5))[0]
    hot = hot[(hot > 20) & (hot < im.height - 20)]
    cuts, cur = [], [hot[0]]
    for v in hot[1:]:
        if v <= cur[-1] + 8:
            cur.append(v)
        else:
            cuts.append((cur[0], cur[-1])); cur = [v]
    cuts.append((cur[0], cur[-1]))
    print("panel separators re-derived at", cuts)
    a = [2] + [c[1] + 1 for c in cuts] + [im.height - 8]
    panes = [im.crop((0, a[i], im.width, a[i + 1])) for i in range(len(a) - 1)]
    if len(panes) < 3:
        raise SystemExit("%s split into %d panels, not the 3 img12.webp has: the "
                         "separator rows were not found, so this is a different "
                         "image or a different crop of it" % (src, len(panes)))
    return panes


def ours(ax, pts, cells, blocks, seam, half, centre, grid_lw, aspect_h):
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
    ax.set_xlim(centre[0] - half, centre[0] + half)
    ax.set_ylim(centre[1] - half * aspect_h, centre[1] + half * aspect_h)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(GRID)


def topo_counts(path):
    """``(rings, sectors)`` off a make_rings.py document's own header, or None."""
    if not path:
        return None
    head = open(path).read(4000)
    m = re.search(r"(\d+)\s+CONCENTRIC RINGS x (\d+)\s+CIRCUMFERENTIAL SECTORS", head)
    return (int(m.group(1)), int(m.group(2))) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="the vendor image (img12.webp), NOT committed")
    ap.add_argument("vtk", help="our mesh, exported as QUADS")
    ap.add_argument("out")
    ap.add_argument("--topo", help="that case's topology .json; its header is where "
                                   "the caption's ring and sector counts come from")
    a = ap.parse_args()
    src, vtk, out, topo = a.src, a.vtk, a.out, a.topo
    pan = panels(src)
    ring, nose = pan[1], pan[2]
    pts, cells, blocks = read_vtk(vtk)
    seam = seam_edges(pts, cells, blocks)
    ar = ring.height / ring.width
    nb = len(set(blocks))
    rs = topo_counts(topo)
    ours_label = "%s：%s%d blocks" % (
        os.path.basename(vtk).replace(".vtk", ""),
        ("%d 環 × %d 等角扇段，" % rs) if rs else "", nb)
    ring_note = ("我們是 %d 圈 %d 段。" % rs) if rs else "我們的圈數未傳入（--topo）。"

    fig = plt.figure(figsize=(13.6, 8.6), facecolor="#fcfcfb")
    fig.text(0.024, 0.972, "§29：被子對 GridPro 自己的徑向扇圖（img12 中間格），框以弦長對齊",
             color=INK, fontsize=15.5, va="top")
    fig.text(0.024, 0.940,
             "廠商原圖不提交進 repo，以路徑傳入。尺度是「讀」出來的，不是量的：弦長 140±15 px / 該格 700 px。",
             color=SEC, fontsize=10.8, va="top")

    for col, (img, title) in enumerate(
            ((ring, "(a1) GridPro：單翼型，徑向扇切成同心階層"),
             (nose, "(a2) GridPro：鼻端"))):
        ax = fig.add_axes([0.024 + col * 0.492, 0.545, 0.452, 0.345])
        ax.imshow(np.asarray(img), aspect="auto")
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color(GRID)
        ax.text(0.0, 1.035, title, transform=ax.transAxes, color=INK,
                fontsize=12.2, va="bottom")

    for col, (half, centre, glw, title) in enumerate(
            ((CHORDS_WIDE / 2.0, (0.5, 0.0), 0.22,
              "(b1) 本 repo：" + ours_label),
             (NOSE_WIDE / 2.0, (0.06, 0.0), 0.5,
              "(b2) 本 repo：鼻端（此格尺度未對齊，見下）"))):
        ax = fig.add_axes([0.024 + col * 0.492, 0.128, 0.452, 0.345])
        ours(ax, pts, cells, blocks, seam, half, centre, glw, ar)
        ax.text(0.0, 1.035, title, transform=ax.transAxes, color=INK,
                fontsize=12.2, va="bottom")

    fig.text(0.024, 0.074,
             "(a1) 讀到三到五圈同心帶、每圈約 20–24 個扇段，外緣在離體約 1.5 個弦長處接上較粗的外場。"
             + ring_note + "圈數與扇段數取自拓撲文件自己的檔頭，block 數取自網格自己的 block 欄位，都不是寫死的。",
             color=SEC, fontsize=10.6, va="top", wrap=True)
    fig.text(0.024, 0.030,
             "(a2) 的尺度在圖上讀不出來（機身在該格斜向出框，無法定弦長），所以 (b2) 標為未對齊；"
             "(b1) 則以 5.0±0.5 個弦長對齊。計數為肉眼讀值，§20b 記過自動計數在此類圖上不成立。",
             color=SEC, fontsize=10.6, va="top", wrap=True)
    fig.savefig(out, dpi=104, facecolor="#fcfcfb")
    print("wrote", out)


if __name__ == "__main__":
    main()
