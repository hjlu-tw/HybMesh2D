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
     "alt：“Airfoil with Icing”；量到厚 8.5%，NACA 0012 為 12%。幾何差異"),
    ("2", "貼體薄環的層數", "2–3 層，各自沿弦向切塊",
     "3 層（--layers 3）", "已照做", OK,
     "§17b；§17 就是以 fig6 為目標建的"),
    ("3", "每側表面的塊數", "此視窗內每側約 15–20 塊",
     "每側 20 塊", "已進入該區間", OK,
     "§25：拓樸 40 條 wall 邊 / 40 塊。§18e 讀圖未量化；§17 本就已是 16，非 5–6"),
    ("4", "環往前繞過鼻端", "是，薄環連續繞過前緣",
     "是", "一致", OK,
     "§17f"),
    ("5", "整體密度", "明顯更密",
     "29120 cell", "未達", PART,
     "§17f、§18e 的外觀讀數；密度沒有可用的量測（§23a）"),
    ("6", "尾緣", "多於三條連線的扇",
     "一條 cut 邊，上下尾流塊共用", "不同策略", PART,
     "§3 的 fig6 讀數 vs §13c；兩者都能網格化，形狀不同"),
    ("7", "每塊的 cell 數", "tutorial 報 329（fig6 自己沒有數字）",
     "202", "已超過", OK,
     "§23b/§25：29120 cell / 144 塊。比廠商自己的 tutorial 更倚賴分區"),
]

fig = plt.figure(figsize=(15.4, 11.4), facecolor="#fcfcfb")
ax1 = fig.add_axes([0.031, 0.455, 0.456, 0.335])
ax2 = fig.add_axes([0.513, 0.455, 0.456, 0.335])
for ax, kind, t1, t2 in (
        (ax1, "gp", "GridPro — fig6 上圖（Airfoil with Icing），原圖未裁",
         "量到：弦長 999 px、厚 85 px（8.5%）。整張只有 1.26 弦長寬 — 近場圖，不是遠場圖"),
        (ax2, "me", "本次 §25 — 每側 20 塊的版本，144 塊 / 29120 cell",
         "同一個視窗。黑色粗線＝區塊邊界，可直接數：上下表面各 20 段")):
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
        own = {}
        for ci, c in enumerate(cells):
            for i in range(len(c)):
                k = (c[i], c[(i+1) % len(c)]); k = (min(k), max(k))
                own.setdefault(k, []).append(blk[ci])
        ax.add_collection(LineCollection([[pts[a], pts[b]] for a, b in own],
                                        colors="#33393f", linewidths=0.3, zorder=2))
        seam = [[pts[a], pts[b]] for (a, b), o in own.items()
                if len(o) == 1 or o[0] != o[-1]]
        ax.add_collection(LineCollection(seam, colors="#0b0b0b", linewidths=1.5, zorder=3))
    ax.set_aspect("equal"); ax.set_xlim(WIN[0], WIN[1]); ax.set_ylim(WIN[2], WIN[3])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color(GRID)
    ax.text(0.0, 1.075, t1, transform=ax.transAxes, color=INK, fontsize=13.5, va="bottom")
    ax.text(0.0, 1.015, t2, transform=ax.transAxes, color=SEC, fontsize=10.3, va="bottom")

tb = fig.add_axes([0.031, 0.030, 0.938, 0.355]); tb.axis("off")
COL = [0.000, 0.022, 0.155, 0.360, 0.520, 0.625]
for c, hh in zip(COL, ["", "項目", "GridPro（fig6）", "本次 §25（每側 20）", "狀態", "證據"]):
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
    "「最像」是 fig6 配 §17/§25，不是 fig5 配 O-ring：fig5 的 alt 是 “MDA-3 Element Configuration”，三段翼，我沒有多段翼案例（§24a）。",
    "這一版把每側表面塊數提到 20，也就是 §24c 第 3 列那個 15–20 區間的上緣。右圖的黑色粗線就是區塊邊界，可以自己數。",
    "更正：§18e 與 §24c 原本寫我「每側 5–6 塊」，那是錯的 — §17 的拓樸本來就有每側 16 塊（32 條 wall 邊 / 32 塊），已在區間內。見 §25a。",
]):
    fig.text(0.031, 0.918 - i * 0.0235, ln, color=SEC, fontsize=10.5, va="bottom")
fig.savefig(OUT, dpi=96, facecolor="#fcfcfb")
print("wrote", OUT)
