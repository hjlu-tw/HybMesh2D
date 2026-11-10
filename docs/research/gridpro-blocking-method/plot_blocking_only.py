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
frame, out = sys.argv[1], sys.argv[-1]
spec = sys.argv[2:-1]            # path|title|subtitle triples
img = np.asarray(Image.open(frame).convert("RGB"))[155:600, 52:1018]
H, W, _ = img.shape
CH, CX, CY = 406.0, 156.0, (231 + 278) / 2.0
EXT = [-CX/CH, (W-CX)/CH, -(H-CY)/CH, CY/CH]
def read(p):
    tok = open(p).read().split()
    i = tok.index("POINTS"); n = int(tok[i+1])
    pts = np.array(tok[i+3:i+3+3*n], float).reshape(n,3)[:,:2]
    j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells=[]
    for _ in range(nc):
        m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
    b = tok.index("LOOKUP_TABLE"); return pts, cells, [int(x) for x in tok[b+2:b+2+nc]]
def draw_blocking(ax, path):
    """Block fills and block BOUNDARIES only -- no interior grid lines."""
    pts, cells, blk = read(path)
    by = {}
    for ci, c in enumerate(cells):
        by.setdefault(blk[ci], []).append(MplPoly([pts[v] for v in c], closed=True))
    for bb in sorted(by):
        ax.add_collection(PatchCollection(by[bb], facecolor=BC[bb % 8], edgecolor="none",
                                          alpha=1.0, zorder=1))
    own = {}
    for ci, c in enumerate(cells):
        for q in range(len(c)):
            e = (c[q], c[(q+1) % len(c)]); e = (min(e), max(e)); own.setdefault(e, []).append(blk[ci])
    seam = [[pts[a], pts[b]] for (a, b), o in own.items() if len(o) == 1 or o[0] != o[-1]]
    ax.add_collection(LineCollection(seam, colors="#0b0b0b", linewidths=1.6, zorder=3))
    vis = {blk[ci] for ci, c in enumerate(cells)
           if EXT[0] <= np.mean([pts[v][0] for v in c]) <= EXT[1]
           and EXT[2] <= np.mean([pts[v][1] for v in c]) <= EXT[3]}
    return len(by), len(vis)
n = 1 + len(spec)
fig = plt.figure(figsize=(13.6, 4.0 + 3.05 * n), facecolor="#fcfcfb")
top = 0.895
items = [(None, "GridPro — C-Grid 影片畫面，顏色即區塊",
          "狀態列：57 塊。右側對話框遮住右半（它屬於另一個案例，§2a）")]
for t in spec:
    path, title, sub = t.split("|")
    items.append((path, title, sub))
hgt = 0.80 / n
for i, (path, t, sub) in enumerate(items):
    ax = fig.add_axes([0.030, top - (i + 1) * hgt - i * 0.045, 0.940, hgt * 0.90])
    ax.set_facecolor("#fcfcfb")
    if path is None:
        ax.imshow(img, extent=EXT, origin="upper")
        extra = ""
    else:
        tot, vis = draw_blocking(ax, path)
        extra = "   共 %d 塊，此視窗內 %d 塊" % (tot, vis)
    ax.set_aspect("equal"); ax.set_xlim(EXT[0], EXT[1]); ax.set_ylim(EXT[2], EXT[3])
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_color(GRID)
    ax.text(0.0, 1.065, t, transform=ax.transAxes, color=INK, fontsize=13, va="bottom")
    ax.text(0.0, 1.010, sub + extra, transform=ax.transAxes, color=SEC, fontsize=9.8, va="bottom")
fig.text(0.030, 0.958, "只比分區 — 同一個視窗，我的只畫區塊邊界", color=INK, fontsize=20, va="bottom")
fig.text(0.030, 0.932, "下面幾張把內部格線整個拿掉，只留區塊的填色與邊界，所以和上圖（顏色本來就是區塊）可以直接對看。三張都是 56 塊、3692 個 cell、0 反轉。",
         color=SEC, fontsize=10.6, va="bottom")
fig.savefig(out, dpi=100, facecolor="#fcfcfb"); print("wrote", out)
