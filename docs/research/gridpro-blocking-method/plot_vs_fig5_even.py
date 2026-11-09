import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK", "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Polygon as MplPoly
from PIL import Image

INK, SEC, MUT, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BC = ["#f4a742", "#7fb2d9", "#8fc98f", "#d99797", "#b9a0d4", "#e3c766", "#8fc9c3", "#c9a98f"]
GP, M1, M2, OUT = sys.argv[1:5]
CH, CX, CY = 100.0, 621.0, 388.0
img = np.asarray(Image.open(GP).convert("RGB")); H, W, _ = img.shape
EXT = [(0-CX)/CH, (W-CX)/CH, -(H-CY)/CH, (CY-0)/CH]
WIN = (-2.12, 4.12, -3.12, 3.12)

def read(p):
    tok = open(p).read().split()
    i = tok.index("POINTS"); n = int(tok[i+1])
    pts = np.array(tok[i+3:i+3+3*n], float).reshape(n,3)[:,:2]
    j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells=[]
    for _ in range(nc):
        m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
    b = tok.index("LOOKUP_TABLE"); blk=[int(x) for x in tok[b+2:b+2+nc]]
    return pts, cells, blk

def draw(ax, path):
    pts, cells, blk = read(path)
    by = {}
    for i, c in enumerate(cells):
        by.setdefault(blk[i], []).append(MplPoly([pts[v] for v in c], closed=True))
    for b in sorted(by):
        ax.add_collection(PatchCollection(by[b], facecolor=BC[b % 8], edgecolor="none",
                                          alpha=0.95, zorder=1))
    e = set()
    for c in cells:
        for i in range(len(c)):
            k = (c[i], c[(i+1) % len(c)]); e.add((min(k), max(k)))
    ax.add_collection(LineCollection([[pts[a], pts[b]] for a, b in e],
                                     colors="#33393f", linewidths=0.22, zorder=2))

fig = plt.figure(figsize=(16.2, 7.6), facecolor="#fcfcfb")
axes = [fig.add_axes([0.031 + i*0.3235, 0.035, 0.300, 0.665]) for i in range(3)]
titles = [
    ("GridPro — fig5 上圖", "裁到下面兩張的同一個物理視窗", None),
    ("原本的 §11 O-ring", "分站＝沿物面等弧長，每段節點數相同", M1),
    ("改成 fig5 的分區方式", "分站＝ring 1 上等角度，節點數隨段長", M2),
]
mets = ["", "38 blk · 17408 cell · max 48.095° · mean 7.137° · jump 14.149",
        "38 blk · 18528 cell · max 47.550° · mean 5.958° · jump 15.282"]
for ax, (t1, t2, mp), met in zip(axes, titles, mets):
    ax.set_facecolor("#fcfcfb")
    if mp is None:
        ax.imshow(img, extent=EXT, origin="upper", interpolation="lanczos", zorder=1)
    else:
        draw(ax, mp)
    ax.set_aspect("equal"); ax.set_xlim(WIN[0], WIN[1]); ax.set_ylim(WIN[2], WIN[3])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color(GRID)
    ax.text(0.0, 1.075, t1, transform=ax.transAxes, color=INK, fontsize=13.5, va="bottom")
    ax.text(0.0, 1.022, t2, transform=ax.transAxes, color=SEC, fontsize=10.3, va="bottom")
    if met:
        ax.text(0.0, -0.038, met, transform=ax.transAxes, color=SEC, fontsize=9.8,
                va="top", family="monospace")

fig.text(0.031, 0.935, "以 fig5 的分區方式改寫 O-ring", color=INK, fontsize=21, va="bottom")
for i, ln in enumerate([
    "能照做的那一半：扇形改成「在 ring 1 上等角度」，前緣那十幾條窄條因此散開得比較均勻。mean 7.137° → 5.958°，max 48.095° → 47.550°，面積跳變 14.149 → 15.282。",
    "照不了的那一半：fig5 的扇形「全部都窄」，沒有四個大楔形 — 那四個是尾緣扇，要把它分細就得加 --te-rays，而 5 支在這個物體上被拒絕（§21c）。",
    "面積跳變在改寫前後都不在遠場：原本在距尾緣 0.44 弦長處，改寫後在 2.94 處的尾緣扇與第一段物面之間。§20b 第 4 點把它歸因於遠場格子外長，是歸錯了。",
]):
    fig.text(0.031, 0.893 - i*0.0295, ln, color=SEC, fontsize=10.6, va="bottom")
fig.savefig(OUT, dpi=96, facecolor="#fcfcfb")
print("wrote", OUT)
