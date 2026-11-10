import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC","PingFang HK","Arial Unicode MS","DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Polygon as MplPoly
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
pts, cells, blk = read(sys.argv[1])
WINS = [((-2.1, 7.1, -3.1, 3.1), "全域：遠場是 9×6 弦長的矩形，下游開口"),
        ((-0.35, 1.45, -0.55, 0.55), "近場：C 環包住物體與尾流"),
        ((-0.06, 0.22, -0.13, 0.13), "前緣")]
fig = plt.figure(figsize=(15.6, 6.4), facecolor="#fcfcfb")
for i, (win, title) in enumerate(WINS):
    ax = fig.add_axes([0.024 + i*0.325, 0.075, 0.303, 0.690]); ax.set_facecolor("#fcfcfb")
    by = {}
    for ci, c in enumerate(cells):
        by.setdefault(blk[ci], []).append(MplPoly([pts[v] for v in c], closed=True))
    for bb in sorted(by):
        ax.add_collection(PatchCollection(by[bb], facecolor=BC[bb % 8], edgecolor="none", alpha=0.95, zorder=1))
    own = {}
    for ci, c in enumerate(cells):
        for q in range(len(c)):
            e = (c[q], c[(q+1) % len(c)]); e = (min(e), max(e)); own.setdefault(e, []).append(blk[ci])
    ax.add_collection(LineCollection([[pts[a], pts[b]] for a, b in own], colors="#33393f", linewidths=0.28, zorder=2))
    ax.add_collection(LineCollection([[pts[a], pts[b]] for (a,b), o in own.items() if len(o)==1 or o[0]!=o[-1]],
                                     colors="#0b0b0b", linewidths=1.5, zorder=3))
    ax.set_aspect("equal"); ax.set_xlim(win[0], win[1]); ax.set_ylim(win[2], win[3])
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_color(GRID)
    ax.text(0.0, 1.022, title, transform=ax.transAxes, color=INK, fontsize=12.5, va="bottom")
fig.text(0.024, 0.925, "照影片的尺度做的網格：乾淨 NACA 0012 的 C/H", color=INK, fontsize=20, va="bottom")
for i, ln in enumerate([
    "56 塊 / 3638 個四邊形 cell / 0 個反轉。max 非正交 58.5°、mean 3.81°。對照 GridPro 自己 C-grid 影片狀態列寫的 57 塊 / 3648 cell — cell 數差 0.3%。",
    "塊數是 56 不是 57：本產生器的塊數恆為 2×層數×(split+wake)，18 組實測全中，所以它只能產生偶數；它的拓樸對尾流線鏡像對稱，GridPro 的 57 是奇數，所以不是。",
    "那支影片沒有可用的廠商品質數字：同一張影格上的 Grid Quality 對話框屬於另一個教學案例（筆記 §2a），所以這裡不引用任何廠商 skew。",
]):
    fig.text(0.024, 0.885 - i*0.027, ln, color=SEC, fontsize=10.6, va="bottom")
fig.savefig(sys.argv[2], dpi=100, facecolor="#fcfcfb"); print("wrote", sys.argv[2])
