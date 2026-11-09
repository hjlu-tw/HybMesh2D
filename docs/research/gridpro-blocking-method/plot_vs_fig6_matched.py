import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK", "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Polygon as MplPoly
from PIL import Image

INK, SEC, MUT, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
OK, NO, PART = "#0ca30c", "#d03b3b", "#fab219"
BC = ["#f4a742","#7fb2d9","#8fc98f","#d99797","#b9a0d4","#e3c766","#8fc9c3","#c9a98f"]
GP, MINE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

# fig6_top.png: body blob x 79..1077 (chord 999 px), y 302..386 (centre 344)
CH, X0, YC = 999.0, 79.0, 344.0
img = np.asarray(Image.open(GP).convert("RGB")); H, W, _ = img.shape
EXT = [(0-X0)/CH, (W-X0)/CH, -(H-YC)/CH, YC/CH]
WIN = (EXT[0], EXT[1], EXT[2], EXT[3])

def read(p):
    tok = open(p).read().split()
    i = tok.index("POINTS"); n = int(tok[i+1])
    pts = np.array(tok[i+3:i+3+3*n], float).reshape(n,3)[:,:2]
    j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells=[]
    for _ in range(nc):
        m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
    b = tok.index("LOOKUP_TABLE")
    return pts, cells, [int(x) for x in tok[b+2:b+2+nc]]

ROWS = [
    ("1", "物體本身", "結冰翼型，前緣有冰角（alt 文字寫明）",
     "乾淨的 NACA 0012", "不同", NO,
     "alt：“Airfoil with Icing”；量到它厚 8.5%，NACA 0012 是 12%。幾何差異，非分區差異"),
    ("2", "貼體薄環的層數", "2–3 層，各自沿弦向切塊",
     "3 層（--layers 3）", "已照做", OK,
     "§17b；§17 就是以 fig6 為目標建的"),
    ("3", "每側表面的塊數", "此視窗內每側約 15–20 塊",
     "每側 5–6 塊", "未達", PART,
     "§18e 讀自對照圖；沒有量化（§23a 三種數法都沒過對照組）"),
    ("4", "環往前繞過鼻端", "是，薄環連續繞過前緣",
     "是", "一致", OK,
     "§17f"),
    ("5", "整體密度", "明顯更密",
     "25984 cell", "未達", PART,
     "§17f、§18e 的外觀讀數；密度沒有可用的量測（§23a）"),
    ("6", "尾緣", "多於三條連線的扇",
     "一條 cut 邊，上下尾流塊共用", "不同策略", PART,
     "§3 的 fig6 讀數 vs §13c；兩者都能網格化，形狀不同"),
    ("7", "每塊的 cell 數", "tutorial 報 329（fig6 自己沒有數字）",
     "217", "已超過", OK,
     "§23b：§17 比廠商自己的 tutorial 更倚賴分區"),
]

fig = plt.figure(figsize=(15.4, 11.4), facecolor="#fcfcfb")
ax1 = fig.add_axes([0.031, 0.455, 0.456, 0.335])
ax2 = fig.add_axes([0.513, 0.455, 0.456, 0.335])
for ax, kind, t1, t2 in (
        (ax1, "gp", "GridPro — fig6 上圖（Airfoil with Icing），原圖未裁",
         "量到：弦長 999 px、厚 85 px（8.5%）。整張只有 1.26 弦長寬 — 近場圖，不是遠場圖"),
        (ax2, "me", "本次 §17 — 以 fig6 為目標建的 C/H，120 塊 / 25984 cell",
         "裁到左圖「同一個」視窗：x ∈ [−0.08, +1.18]、y ∈ [−0.38, +0.34] 弦長")):
    ax.set_facecolor("#fcfcfb")
    if kind == "gp":
        ax.imshow(img, extent=EXT, origin="upper", interpolation="lanczos")
    else:
        pts, cells, blk = read(MINE)
        by = {}
        for i, c in enumerate(cells):
            by.setdefault(blk[i], []).append(MplPoly([pts[v] for v in c], closed=True))
        for b in sorted(by):
            ax.add_collection(PatchCollection(by[b], facecolor=BC[b % 8],
                                              edgecolor="none", alpha=0.95, zorder=1))
        e = set()
        for c in cells:
            for i in range(len(c)):
                k = (c[i], c[(i+1) % len(c)]); e.add((min(k), max(k)))
        ax.add_collection(LineCollection([[pts[a], pts[b]] for a, b in e],
                                        colors="#33393f", linewidths=0.3, zorder=2))
    ax.set_aspect("equal"); ax.set_xlim(WIN[0], WIN[1]); ax.set_ylim(WIN[2], WIN[3])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color(GRID)
    ax.text(0.0, 1.075, t1, transform=ax.transAxes, color=INK, fontsize=13.5, va="bottom")
    ax.text(0.0, 1.015, t2, transform=ax.transAxes, color=SEC, fontsize=10.3, va="bottom")

tb = fig.add_axes([0.031, 0.030, 0.938, 0.355]); tb.axis("off")
COL = [0.000, 0.022, 0.155, 0.360, 0.520, 0.625]
for c, hh in zip(COL, ["", "項目", "GridPro（fig6）", "本次 §17 的 C/H", "狀態", "證據"]):
    tb.text(c, 0.955, hh, transform=tb.transAxes, color=MUT, fontsize=10.6, va="bottom")
tb.plot([0, 1], [0.940, 0.940], transform=tb.transAxes, color=GRID, lw=1.0, clip_on=False)
for r, (num, item, gp, me, st, col, ev) in enumerate(ROWS):
    y = 0.845 - r * 0.126
    tb.text(COL[0], y, num, transform=tb.transAxes, color=MUT, fontsize=11, va="bottom")
    tb.text(COL[1], y, item, transform=tb.transAxes, color=INK, fontsize=11.4, va="bottom")
    tb.text(COL[2], y, gp, transform=tb.transAxes, color=SEC, fontsize=11, va="bottom")
    tb.text(COL[3], y, me, transform=tb.transAxes, color=SEC, fontsize=11, va="bottom")
    tb.plot([COL[4], COL[4]+0.016], [y+0.028, y+0.028], transform=tb.transAxes,
            color=col, lw=3.2, solid_capstyle="butt", clip_on=False)
    tb.text(COL[4]+0.022, y, st, transform=tb.transAxes, color=col, fontsize=11, va="bottom")
    tb.text(COL[5], y, ev, transform=tb.transAxes, color=SEC, fontsize=10.2, va="bottom")
    tb.plot([0, 1], [y-0.030, y-0.030], transform=tb.transAxes, color=GRID, lw=0.6, clip_on=False)

fig.text(0.031, 0.955, "GridPro 的網格，和我最像的那一份，放在同一個比例尺上",
         color=INK, fontsize=21, va="bottom")
for i, ln in enumerate([
    "「最像」是 fig6 配 §17，不是 fig5 配 O-ring：fig5 的 alt 文字是 “MDA-3 Element Configuration”，是三段翼，而我沒有任何多段翼案例 — 放大也看得到主翼後面另有一片。",
    "fig6 的 alt 是 “Airfoil with Icing”，單一物體，而 §17 本來就是以它為目標建的。所以這一對是唯一「同一類幾何、同一個目標」的配對。",
    "附帶更正：§20a 說 fig5「中央一個物體」是錯的，而我拿來定標的 100 px 裡，那個「尾端碎片」其實是後面那一片 — 主翼弦長是 86 px，fig5 的視窗因此是 ±7.4 而非 ±6.4 弦長（方向不變，只是更寬）。",
]):
    fig.text(0.031, 0.918 - i * 0.0235, ln, color=SEC, fontsize=10.5, va="bottom")
fig.savefig(OUT, dpi=96, facecolor="#fcfcfb")
print("wrote", OUT)
