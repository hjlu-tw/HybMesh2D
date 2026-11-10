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
frame, mesh, out = sys.argv[1], sys.argv[2], sys.argv[3]
img = np.asarray(Image.open(frame).convert("RGB"))[155:600, 52:1018]
H, W, _ = img.shape
CH, CX, CY = 406.0, 156.0, (231 + 278) / 2.0          # measured: body 406 px, t/c 0.118
EXT = [-CX/CH, (W-CX)/CH, -(H-CY)/CH, CY/CH]
def read(p):
    tok = open(p).read().split()
    i = tok.index("POINTS"); n = int(tok[i+1])
    pts = np.array(tok[i+3:i+3+3*n], float).reshape(n,3)[:,:2]
    j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells=[]
    for _ in range(nc):
        m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
    b = tok.index("LOOKUP_TABLE"); return pts, cells, [int(x) for x in tok[b+2:b+2+nc]]
fig = plt.figure(figsize=(14.2, 9.6), facecolor="#fcfcfb")
a1 = fig.add_axes([0.028, 0.545, 0.944, 0.300])
a2 = fig.add_axes([0.028, 0.075, 0.944, 0.300])
a1.imshow(img, extent=EXT, origin="upper")
pts, cells, blk = read(mesh)
by = {}
for ci, c in enumerate(cells):
    by.setdefault(blk[ci], []).append(MplPoly([pts[v] for v in c], closed=True))
for bb in sorted(by):
    a2.add_collection(PatchCollection(by[bb], facecolor=BC[bb % 8], edgecolor="none", alpha=0.95, zorder=1))
own = {}
for ci, c in enumerate(cells):
    for q in range(len(c)):
        e = (c[q], c[(q+1) % len(c)]); e = (min(e), max(e)); own.setdefault(e, []).append(blk[ci])
a2.add_collection(LineCollection([[pts[a], pts[b]] for a, b in own], colors="#33393f", linewidths=0.5, zorder=2))
a2.add_collection(LineCollection([[pts[a], pts[b]] for (a,b), o in own.items() if len(o)==1 or o[0]!=o[-1]],
                                 colors="#0b0b0b", linewidths=1.8, zorder=3))
for ax, t, sub in ((a1, "GridPro — C-Grid 影片的畫面（4Jeu-EUXXmo），原圖未裁",
                    "狀態列：Num Blocks 57 / Num Cells 3648。右側的 Grid Quality 對話框屬於另一個教學案例（§2a），它遮住了網格的右半"),
                   (a2, "本次 §7 — 56 塊 / 3692 個四邊形，--layers 2 --split 8",
                    "同一個視窗，量自畫面中翼型的 406 px 弦長（厚弦比 0.118 = NACA 0012）。max 非正交 52.3°、mean 3.10°；上圖那個案子沒有可比的廠商品質數字（§2a）")):
    ax.set_aspect("equal"); ax.set_xlim(EXT[0], EXT[1]); ax.set_ylim(EXT[2], EXT[3])
    ax.set_xticks([]); ax.set_yticks([]); ax.set_facecolor("#fcfcfb")
    for sp in ax.spines.values(): sp.set_color(GRID)
    ax.text(0.0, 1.075, t, transform=ax.transAxes, color=INK, fontsize=13, va="bottom")
    ax.text(0.0, 1.016, sub, transform=ax.transAxes, color=SEC, fontsize=9.8, va="bottom")
fig.text(0.028, 0.952, "跟影片畫出來的網格像嗎 — 同一個視窗", color=INK, fontsize=20, va="bottom")
fig.text(0.028, 0.918, "數量對上了（56 對 57 塊、3692 對 3648 cell），但「怎麼花」要另外對：第一版把 56 塊花成每面 22 條細長切片，和影片明顯不同；改成 2 層×每面 8 塊才接近。",
         color=SEC, fontsize=10.6, va="bottom")
fig.savefig(out, dpi=100, facecolor="#fcfcfb"); print("wrote", out)
