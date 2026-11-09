import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC","PingFang HK","Arial Unicode MS","DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Polygon as MplPoly
from PIL import Image
INK, SEC, MUT, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BC = ["#f4a742","#7fb2d9","#8fc98f","#d99797","#b9a0d4","#e3c766","#8fc9c3","#c9a98f"]
def read(p):
    tok = open(p).read().split()
    i = tok.index("POINTS"); n = int(tok[i+1])
    pts = np.array(tok[i+3:i+3+3*n], float).reshape(n,3)[:,:2]
    j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells=[]
    for _ in range(nc):
        m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
    b = tok.index("LOOKUP_TABLE"); return pts, cells, [int(x) for x in tok[b+2:b+2+nc]]
GPI = np.asarray(Image.open(sys.argv[1]).convert("RGB")); H, W, _ = GPI.shape
CH, X0, YC = 999.0, 79.0, 344.0
EXT = [(0-X0)/CH, (W-X0)/CH, -(H-YC)/CH, YC/CH]
WIN = (-1.6, 3.4, -1.6, 1.6)
items = [(t, p, sub) for t, p, sub in zip(sys.argv[2::3], sys.argv[3::3], sys.argv[4::3])]
fig = plt.figure(figsize=(15.6, 6.6), facecolor="#fcfcfb")
for i, (title, path, sub) in enumerate(items):
    ax = fig.add_axes([0.024 + i*0.325, 0.085, 0.303, 0.700]); ax.set_facecolor("#fcfcfb")
    if path is None:
        ax.imshow(GPI, extent=EXT, origin="upper", interpolation="lanczos")
    else:
        pts, cells, blk = read(path)
        by = {}
        for ci, cc in enumerate(cells):
            by.setdefault(blk[ci], []).append(MplPoly([pts[v] for v in cc], closed=True))
        for bb in sorted(by):
            ax.add_collection(PatchCollection(by[bb], facecolor=BC[bb % 8], edgecolor="none", alpha=0.95, zorder=1))
        own = {}
        for ci, cc in enumerate(cells):
            for q in range(len(cc)):
                e = (cc[q], cc[(q+1) % len(cc)]); e = (min(e), max(e)); own.setdefault(e, []).append(blk[ci])
        ax.add_collection(LineCollection([[pts[a], pts[b]] for a, b in own], colors="#33393f", linewidths=0.3, zorder=2))
        ax.add_collection(LineCollection([[pts[a], pts[b]] for (a, b), o in own.items() if len(o)==1 or o[0]!=o[-1]],
                                         colors="#0b0b0b", linewidths=1.5, zorder=3))
    ax.set_aspect("equal"); ax.set_xlim(WIN[0], WIN[1]); ax.set_ylim(WIN[2], WIN[3])
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_color(GRID)
    ax.text(0.0, 1.055, title, transform=ax.transAxes, color=INK, fontsize=12.5, va="bottom")
    ax.text(0.0, 1.008, sub, transform=ax.transAxes, color=SEC, fontsize=10, va="bottom")
fig.text(0.024, 0.930, "往外彎成弧的程度 — 三個 blend 值", color=INK, fontsize=20, va="bottom")
fig.text(0.024, 0.893, "視窗 x ∈ [−1.6, 3.4]、y ∈ [±1.6] 弦長 — 比 fig6 的 1.26 弦長畫面寬得多，因為弧就長在那個範圍，廠商圖根本看不到那裡（§24b）。三張都是 0 個反轉 cell。",
         color=SEC, fontsize=10.6, va="bottom")
fig.text(0.024, 0.868, "外層徑向邊改成「朝 (0.25, 0) 徑向外彎」的弧；blend 0 就是原本的直弦。數字是法線總轉角依線長四等分的中位數，和非正交平均。",
         color=SEC, fontsize=10.6, va="bottom")
fig.savefig(sys.argv[-1], dpi=100, facecolor="#fcfcfb"); print("wrote", sys.argv[-1])
