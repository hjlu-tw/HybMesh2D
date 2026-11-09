import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK", "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Polygon as MplPoly
from matplotlib.gridspec import GridSpec
from PIL import Image

INK, SEC, MUT, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BLOCK_COLORS = ["#f4a742", "#7fb2d9", "#8fc98f", "#d99797",
                "#b9a0d4", "#e3c766", "#8fc9c3", "#c9a98f"]

GP, MESH, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
CHORD, CX, CY = 100.0, 621.0, 388.0          # measured on fig5_top.png, see 20a

img = np.asarray(Image.open(GP).convert("RGB"))
H, W, _ = img.shape
EXT = [(0 - CX)/CHORD, (W - CX)/CHORD, -(H - CY)/CHORD, (CY - 0)/CHORD]

def read(p):
    tok = open(p).read().split()
    i = tok.index("POINTS"); n = int(tok[i+1])
    pts = np.array(tok[i+3:i+3+3*n], float).reshape(n, 3)[:, :2]
    j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells = []
    for _ in range(nc):
        m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
    b = tok.index("LOOKUP_TABLE"); blocks = [int(x) for x in tok[b+2:b+2+nc]]
    return pts, cells, blocks

pts, cells, blocks = read(MESH)
by_block = {}
for idx, c in enumerate(cells):
    by_block.setdefault(blocks[idx], []).append(MplPoly([pts[v] for v in c], closed=True))
seg = set()
for c in cells:
    for a in range(len(c)):
        e = (c[a], c[(a+1) % len(c)]); seg.add((min(e), max(e)))
segs = [[pts[a], pts[b]] for a, b in seg]

def draw_mine(ax, lw):
    for b in sorted(by_block):
        ax.add_collection(PatchCollection(by_block[b], facecolor=BLOCK_COLORS[b % 8],
                                          edgecolor="none", alpha=0.95, zorder=1))
    ax.add_collection(LineCollection(segs, colors="#33393f", linewidths=lw, zorder=2))

WIN_WIDE = (EXT[0], EXT[1], EXT[2], EXT[3])
WIN_NEAR = (-2.12, 4.12, -3.12, 3.12)

fig = plt.figure(figsize=(15.2, 12.3), facecolor="#fcfcfb")
gs = GridSpec(2, 2, figure=fig, height_ratios=[1.0, 1.30], hspace=0.20,
              wspace=0.045, left=0.030, right=0.982, top=0.787, bottom=0.028)

panels = [
    (gs[0, 0], WIN_WIDE, "gp", "GridPro — fig5 上圖，原圖未裁",
     "文章裡唯一一張二維翼型的遠場分區", 0.0),
    (gs[0, 1], WIN_WIDE, "me", "本次 §11 O-ring，放在同一個視窗裡",
     "同一個弦長比例：我的整個計算域只佔左圖中間那一塊", 0.35),
    (gs[1, 0], WIN_NEAR, "gp", "GridPro — 同一張圖，裁到右邊那個視窗",
     "x ∈ [−2.1, 4.1]、y ∈ [−3.1, 3.1]（弦長）", 0.0),
    (gs[1, 1], WIN_NEAR, "me", "本次 §11 O-ring — 2 環 × 16 扇，38 塊",
     "同一個物理視窗，同一個比例，逐塊上色", 0.22),
]
for cell, win, kind, title, sub, lw in panels:
    a = fig.add_subplot(cell); a.set_facecolor("#fcfcfb")
    if kind == "gp":
        a.imshow(img, extent=EXT, origin="upper", interpolation="lanczos", zorder=1)
    else:
        draw_mine(a, lw)
    a.set_aspect("equal"); a.set_xlim(win[0], win[1]); a.set_ylim(win[2], win[3])
    a.set_xticks([]); a.set_yticks([])
    for s in a.spines.values(): s.set_color(GRID)
    a.text(0.0, 1.062, title, transform=a.transAxes, color=INK, fontsize=13, va="bottom")
    a.text(0.0, 1.014, sub, transform=a.transAxes, color=SEC, fontsize=10.2, va="bottom")

fig.text(0.030, 0.956, "跟 GridPro 的遠場比較 — fig5 上圖 vs 本次的 O-ring",
         color=INK, fontsize=21, va="bottom")
for i, line in enumerate([
    "上排＝同一個「螢幕上弦長一樣長」的視窗。左邊 GridPro 的網格鋪滿整個畫面；右邊我的整個遠場（圓 r=3）只佔中間一塊。",
    "也就是說 fig5 看得到的範圍，已經比我的整個計算域寬兩倍 — 而它本身還是裁切圖，真正的外邊界比這更遠（§19a）。",
    "下排把 GridPro 裁到跟我一樣的物理視窗，那才是同尺度對照。",
    "量尺：fig5 翼型弦長量到 100 px（白色連通區塊 86、含尾端碎片 127，取中值，±15%），上排視窗＝x ∈ [−6.2, +6.4]、y ∈ [−3.3, +3.9]。",
]):
    fig.text(0.030, 0.921 - i * 0.0222, line, color=SEC, fontsize=10.4, va="bottom")
fig.savefig(OUT, dpi=96, facecolor="#fcfcfb")
print("wrote", OUT)
