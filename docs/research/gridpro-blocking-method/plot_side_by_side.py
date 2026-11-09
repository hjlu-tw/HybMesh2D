import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK", "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Polygon as MplPoly
from PIL import Image

INK, SEC, MUT, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BC = ["#f4a742","#7fb2d9","#8fc98f","#d99797","#b9a0d4","#e3c766","#8fc9c3","#c9a98f"]
GP, MINE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
CH, X0, YC = 999.0, 79.0, 344.0          # fig6_top.png, measured (section 24b)
img = np.asarray(Image.open(GP).convert("RGB")); H, W, _ = img.shape
EXT = [(0-X0)/CH, (W-X0)/CH, -(H-YC)/CH, YC/CH]

tok = open(MINE).read().split()
i = tok.index("POINTS"); n = int(tok[i+1])
pts = np.array(tok[i+3:i+3+3*n], float).reshape(n,3)[:,:2]
j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells = []
for _ in range(nc):
    m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
b = tok.index("LOOKUP_TABLE"); blk = [int(x) for x in tok[b+2:b+2+nc]]

fig = plt.figure(figsize=(13.4, 17.2), facecolor="#fcfcfb")
ax1 = fig.add_axes([0.022, 0.503, 0.956, 0.427])
ax2 = fig.add_axes([0.022, 0.062, 0.956, 0.427])

ax1.imshow(img, extent=EXT, origin="upper", interpolation="lanczos")

by = {}
for ci, c in enumerate(cells):
    by.setdefault(blk[ci], []).append(MplPoly([pts[v] for v in c], closed=True))
for bb in sorted(by):
    ax2.add_collection(PatchCollection(by[bb], facecolor=BC[bb % 8],
                                      edgecolor="none", alpha=0.95, zorder=1))
own = {}
for ci, c in enumerate(cells):
    for i2 in range(len(c)):
        e = (c[i2], c[(i2+1) % len(c)]); e = (min(e), max(e))
        own.setdefault(e, []).append(blk[ci])
ax2.add_collection(LineCollection([[pts[a], pts[b2]] for a, b2 in own],
                                  colors="#33393f", linewidths=0.32, zorder=2))
ax2.add_collection(LineCollection([[pts[a], pts[b2]] for (a, b2), o in own.items()
                                   if len(o) == 1 or o[0] != o[-1]],
                                  colors="#0b0b0b", linewidths=1.6, zorder=3))

for ax, t in ((ax1, "GridPro — fig6 上圖（Airfoil with Icing），原圖未裁"),
              (ax2, "本次 §27 — 拉直後的 C/H，176 塊 / 28640 cell，每側表面 32 塊，貼體 2 層")):
    ax.set_aspect("equal"); ax.set_xlim(EXT[0], EXT[1]); ax.set_ylim(EXT[2], EXT[3])
    ax.set_xticks([]); ax.set_yticks([]); ax.set_facecolor("#fcfcfb")
    for sp in ax.spines.values(): sp.set_color(GRID)
    ax.text(0.008, 0.975, t, transform=ax.transAxes, color=INK, fontsize=14,
            va="top", ha="left", zorder=9,
            bbox=dict(fc="#fcfcfb", ec=GRID, lw=0.7, pad=5.5, alpha=0.94))

fig.text(0.022, 0.966, "GridPro 的網格 vs 本次最像的那一份", color=INK, fontsize=22, va="bottom")
fig.text(0.022, 0.945,
         "同一個物理視窗：x ∈ [−0.08, +1.18]、y ∈ [−0.38, +0.34] 弦長（量自 fig6 的物體，弦長 999 px / 1261 px 畫面寬）。",
         color=SEC, fontsize=11.4, va="bottom")

for i, ln in enumerate([
    "下圖黑色粗線＝區塊邊界，可直接數。這一版是 §27 修掉「垂直方向曲度」之後的：貼體環 3 層改 2 層，法線格線總轉角中位數 6.9° → 0.4°。",
    "注意 GridPro 的是結冰翼型（厚 8.5%、前緣有冰角），我的是乾淨 NACA 0012（厚 12%）— 幾何不同，不是分區不同。",
]):
    fig.text(0.022, 0.030 - i * 0.0145, ln, color=MUT, fontsize=10.6, va="bottom")
fig.savefig(OUT, dpi=110, facecolor="#fcfcfb")
print("wrote", OUT)
