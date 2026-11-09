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
    b = tok.index("LOOKUP_TABLE")
    return pts, cells, [int(x) for x in tok[b+2:b+2+nc]]

ROWS = [
    ("1", "尾緣扇的細密度", "細，扇形全部都窄",
     "4 個 85.87° 大楔形", "拒絕", NO,
     "§21c：--te-rays 5/7/9 → 816/1810/2616 個反轉 cell。徑向在遠場圓上交叉"),
    ("2", "扇形角寬是否均勻", "繞一圈大致均勻",
     "原本前緣擠十幾條窄的", "已照做", OK,
     "§21a：mean 7.137° → 5.958°，max 48.095° → 47.550°，cell +6.4%"),
    ("3", "徑向線的形狀", "外擴時彎曲、成螺旋狀",
     "離開物面法線後幾乎直走", "未做", PART,
     "外觀；本檔 CURVED 已是弧，但弧度小到看不出來。沒有量化"),
    ("4", "遠場範圍", "畫面就已到 ±6.4 弦長，且是裁切圖",
     "圓 r=3（tutorial 自己寫的）", "可改，有代價", PART,
     "§19c：同一份 C/H 改矩形 max 42.9°→57.8°、跳變 4.55→10.2"),
    ("5", "同心環的數量", "放大後看不到同心縫，等於 1 層外環",
     "2 環（物面環 + 1 層）", "一致", OK,
     "§11b 的修正；§21a 實測加到 3/4 環 max 變 54.3/62.0"),
    ("6", "遠場格子大小", "看起來大致維持均勻",
     "往外長大", "未做", PART,
     "只是外觀。§21d：14.149 的面積跳變在距尾緣 0.44，不在遠場"),
    ("7", "物面貼體環（Wrap）", "有，廠商文字也寫明",
     "有，ring 1 即是", "一致", OK,
     "§3 引的 Wrap step；兩邊都有"),
]

fig = plt.figure(figsize=(15.6, 12.6), facecolor="#fcfcfb")
ax1 = fig.add_axes([0.031, 0.455, 0.448, 0.352])
ax2 = fig.add_axes([0.521, 0.455, 0.448, 0.352])
for ax, kind, t1, t2 in ((ax1, "gp", "GridPro — fig5 上圖",
                          "裁到右圖的同一個物理視窗"),
                         (ax2, "me", "本次 §21 改寫後的 O-ring",
                          "38 塊 · 18528 cell · max 47.550° · mean 5.958°")):
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
                                        colors="#33393f", linewidths=0.22, zorder=2))
    ax.set_aspect("equal"); ax.set_xlim(WIN[0], WIN[1]); ax.set_ylim(WIN[2], WIN[3])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color(GRID)
    ax.text(0.0, 1.055, t1, transform=ax.transAxes, color=INK, fontsize=13.5, va="bottom")
    ax.text(0.0, 1.008, t2, transform=ax.transAxes, color=SEC, fontsize=10.2, va="bottom")

tb = fig.add_axes([0.031, 0.035, 0.938, 0.375]); tb.axis("off")
COL = [0.000, 0.022, 0.150, 0.360, 0.545, 0.640]
for c, h in zip(COL, ["", "項目", "GridPro（fig5）", "本次的 O-ring", "狀態", "證據"]):
    tb.text(c, 0.955, h, transform=tb.transAxes, color=MUT, fontsize=10.6, va="bottom")
tb.plot([0, 1], [0.940, 0.940], transform=tb.transAxes, color=GRID, lw=1.0, clip_on=False)
for r, (num, item, gp, me, st, col, ev) in enumerate(ROWS):
    y = 0.845 - r * 0.126
    tb.text(COL[0], y, num, transform=tb.transAxes, color=MUT, fontsize=11, va="bottom")
    tb.text(COL[1], y, item, transform=tb.transAxes, color=INK, fontsize=11.4, va="bottom")
    tb.text(COL[2], y, gp, transform=tb.transAxes, color=SEC, fontsize=11, va="bottom")
    tb.text(COL[3], y, me, transform=tb.transAxes, color=SEC, fontsize=11, va="bottom")
    tb.plot([COL[4], COL[4] + 0.016], [y + 0.028, y + 0.028], transform=tb.transAxes,
            color=col, lw=3.2, solid_capstyle="butt", clip_on=False)
    tb.text(COL[4] + 0.022, y, st, transform=tb.transAxes, color=col, fontsize=11, va="bottom")
    tb.text(COL[5], y, ev, transform=tb.transAxes, color=SEC, fontsize=10.2, va="bottom")
    tb.plot([0, 1], [y - 0.030, y - 0.030], transform=tb.transAxes,
            color=GRID, lw=0.6, clip_on=False)

fig.text(0.031, 0.952, "跟 GridPro 的差異清單 — 七項，標明每一項靠什麼證據",
         color=INK, fontsize=21, va="bottom")
for i, ln in enumerate([
    "「狀態」五種：一致、已照做、可改有代價、未做、拒絕。第 3 和第 6 項的「未做」是因為它們到目前為止只是外觀、沒有任何數字支撐，不是因為做不到。",
    "兩次影像量測失敗，列在這裡以免這張表被讀成比它實際更確定：(a) 沿圓周數顏色段來數 fig5 的扇形數，隨半徑在 7 到 21 之間跳；",
    "(b) 沿圓周數格線交點來比網格密度，拿我自己真值為 96 的網格校準，偵測器回報 157–204（約 2 倍高估，把環向線也數進去了）。兩個數字都因此沒有引用。",
]):
    fig.text(0.031, 0.912 - i * 0.0245, ln, color=SEC, fontsize=10.5, va="bottom")
fig.savefig(OUT, dpi=96, facecolor="#fcfcfb")
print("wrote", OUT)
