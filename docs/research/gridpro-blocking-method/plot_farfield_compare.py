import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK", "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
from matplotlib.collections import LineCollection
from matplotlib.gridspec import GridSpec

INK, SEC, MUT, GRID, MESH = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#b9b8ae"
C = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"]
AR = 1.45

def read(p):
    tok = open(p).read().split()
    i = tok.index("POINTS"); n = int(tok[i+1])
    pts = np.array(tok[i+3:i+3+3*n], float).reshape(n, 3)[:, :2]
    j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells = []
    for _ in range(nc):
        m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
    return pts, cells

def edges(cells):
    seen, own = {}, {}
    for c in cells:
        for a in range(len(c)):
            e = (c[a], c[(a+1) % len(c)]); key = (min(e), max(e))
            own[key] = own.get(key, 0) + 1; seen[key] = e
    return seen, own

def loops(bnd):
    adj = {}
    for a, b in bnd:
        adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    out, done = [], set()
    for s in adj:
        if s in done: continue
        cur, prev, lp = s, None, [s]; done.add(s)
        while True:
            nxt = [x for x in adj[cur] if x != prev]
            if not nxt: break
            nxt = nxt[0]
            if nxt == s: break
            lp.append(nxt); done.add(nxt); prev, cur = cur, nxt
        out.append(lp)
    return out

def fit(cx, cy, w, h):
    if w / h < AR: w = h * AR
    else:          h = w / AR
    return (cx - w/2, cx + w/2, cy - h/2, cy + h/2)

CASES = [
    ("results/meshes/ff_rings/m.vtk", "§8–11  圓形遠場", "r = 3 @ (1,0)",
     "GridPro tutorial 文字自己寫明的遠場；唯一有來源的一個",
     "38 blk · 8704 cell", "max 48.1°  mean 7.14°  jump 14.1",
     fit(1.0, 0.0, 6.4, 6.4), C[0], "圓  r=3"),
    ("results/meshes/ff_17/m.vtk", "§13/§17  矩形遠場", "9 × 6 chord",
     "fig6 的形狀：上下遠場是直線，不是弧",
     "120 blk · 12992 cell", "max 42.9°  mean 2.09°  jump 4.55",
     fit(2.5, 0.0, 9.4, 6.4), C[1], "矩形  9×6"),
    ("results/meshes/ff_18/m.vtk", "§18  H 型遠場", "9 × 6 chord + 出口開口的盒",
     "GridPro 文章講的「一層一層的盒子」；代價最大",
     "160 blk · 16704 cell", "max 57.8°  mean 4.87°  jump 10.2",
     fit(2.5, 0.0, 9.4, 6.4), C[2], "H 型  9×6"),
    ("results/meshes/ff_cg/m.vtk", "本倉庫 shipped C-grid", "30 × 20 chord",
     "只有 4 塊，遠場是一條 C 形弧；每一項都最好",
     "4 blk · 5760 cell", "max 31.4°  mean 4.34°  jump 1.48",
     fit(5.0, 0.0, 31.0, 21.0), C[3], "C 形弧  30×20"),
]

data = []
for path, *rest in CASES:
    pts, cells = read(path)
    seen, own = edges(cells)
    segs = [[pts[a], pts[b]] for (a, b) in seen.values()]
    bnd = [seen[k] for k, v in own.items() if v == 1]
    ls = loops(bnd)
    ls.sort(key=lambda l: -(np.ptp(pts[l][:, 0]) * np.ptp(pts[l][:, 1])))
    data.append((pts, segs, ls, rest))

fig = plt.figure(figsize=(16.4, 10.9), facecolor="#fcfcfb")
gs = GridSpec(2, 4, figure=fig, height_ratios=[0.93, 1.0],
              hspace=0.17, wspace=0.085, left=0.034, right=0.979, top=0.855, bottom=0.035)

ax = fig.add_subplot(gs[0, 0:2]); ax.set_facecolor("#fcfcfb")
for (pts, segs, ls, rest) in data:
    col, short = rest[6], rest[7]
    o = pts[ls[0] + [ls[0][0]]]
    ax.plot(o[:, 0], o[:, 1], lw=2.0, color=col, label=short, zorder=3)
p0, _, l0, _ = data[0]
body = p0[l0[1] + [l0[1][0]]]
ax.fill(body[:, 0], body[:, 1], color=INK, zorder=4)
ax.annotate("翼型 (1 chord)", xy=(1.0, 0.0), xytext=(-5.2, 5.6), fontsize=9.8, color=SEC,
            arrowprops=dict(arrowstyle="-", color=MUT, lw=0.9, shrinkB=3), zorder=5)
ax.set_aspect("equal"); ax.set_xlim(-11.5, 21.5); ax.set_ylim(-11.0, 11.0)
ax.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
ax.tick_params(colors=MUT, labelsize=9)
for s in ax.spines.values(): s.set_color(GRID)
ax.set_title("四個遠場邊界疊在同一個比例尺上（單位：弦長）",
             color=INK, fontsize=13.5, pad=7, loc="left")
ax.text(0.014, 0.028, "色鍵＝右表", transform=ax.transAxes, color=MUT,
        fontsize=10, ha="left", va="bottom")


tb = fig.add_subplot(gs[0, 2:4]); tb.set_facecolor("#fcfcfb"); tb.axis("off")
tb.set_title("同一個翼型、同一套 BL 起始高度，四種遠場量到的代價",
             color=INK, fontsize=13.5, pad=7, loc="left")
COL = [0.015, 0.44, 0.565, 0.695, 0.825, 0.945]
HEAD = ["遠場", "blocks", "cells", "max°", "mean°", "area jump"]
for c, h in zip(COL, HEAD):
    tb.text(c, 0.885, h, transform=tb.transAxes, color=MUT, fontsize=10.2,
            ha="left" if c < 0.2 else "right", va="bottom")
tb.plot([0.0, 1.0], [0.868, 0.868], transform=tb.transAxes, color=GRID, lw=1.0, clip_on=False)
ORDER = [3, 1, 0, 2]
for r, k in enumerate(ORDER):
    lab, ext, sub, size, met, win, col, short = data[k][3]
    nb, nc = size.split(" · ")
    mx, mn, jp = [x.split()[-1] for x in met.replace("°", "").split("  ")]
    y = 0.775 - r * 0.145
    tb.plot([0.0, 0.022], [y + 0.028, y + 0.028], transform=tb.transAxes,
            color=col, lw=3.0, solid_capstyle="butt", clip_on=False)
    tb.text(COL[0] + 0.022, y, short, transform=tb.transAxes, color=INK, fontsize=11.2, va="bottom")
    for c, v in zip(COL[1:], [nb.split()[0], nc.split()[0], mx, mn, jp]):
        tb.text(c, y, v, transform=tb.transAxes, color=SEC, fontsize=11.2,
                ha="right", va="bottom", family="monospace")
tb.text(0.0, 0.03,
        "四例都在 BL_INITIAL_THICKNESS 0.001、MB_SMOOTH_ITERS 5 下量 — shipped C-grid 的預設其實是 20，\n"
        "在 20 下它是 max 29.9°／mean 3.82°／jump 2.28：角度更好、面積跳變更差。\n"
        "排序＝非正交 max。最小的遠場（圓 r=3）不是最好的；最好的是最大的那個，而且只用 4 塊、5760 個 cell。\n"
        "遠場形狀換掉的代價比塊數大：同一份 C/H 拓樸從矩形改成 H 型盒，max 42.9°→57.8°、area jump 4.55→10.2。",
        transform=tb.transAxes, color=SEC, fontsize=10.2, va="bottom", linespacing=1.6)

for i, (pts, segs, ls, rest) in enumerate(data):
    lab, ext, sub, size, met, win, col, _ = rest
    a = fig.add_subplot(gs[1, i]); a.set_facecolor("#fcfcfb")
    a.add_collection(LineCollection(segs, colors=MESH, linewidths=0.4, zorder=1))
    for j, lp in enumerate(ls):
        o = pts[lp + [lp[0]]]
        a.plot(o[:, 0], o[:, 1], lw=1.8 if j == 0 else 1.1,
               color=col if j == 0 else INK, zorder=3)
    a.set_aspect("equal"); a.set_xlim(win[0], win[1]); a.set_ylim(win[2], win[3])
    a.set_xticks([]); a.set_yticks([])
    for s in a.spines.values(): s.set_color(GRID)
    a.text(0.0, 1.135, lab, transform=a.transAxes, color=INK, fontsize=12.5, va="bottom")
    a.text(0.0, 1.075, ext, transform=a.transAxes, color=col, fontsize=10.4, va="bottom")
    a.text(0.0, 1.016, sub, transform=a.transAxes, color=SEC, fontsize=9.5, va="bottom")
    a.text(0.0, -0.045, size + "\n" + met, transform=a.transAxes,
           color=SEC, fontsize=9.6, va="top", family="monospace", linespacing=1.55)

fig.text(0.034, 0.952, "遠場分區對照 — 四種遠場，同一個 NACA 0012", color=INK, fontsize=20, va="bottom")
fig.text(0.034, 0.916,
         "GridPro 那兩篇文章裡沒有任何一張圖含翼型的遠場邊界：六張圖的上下左右四邊都還有網格，全部是裁切圖，所以這張圖沒有可比的廠商側。",
         color=SEC, fontsize=10.8, va="bottom")
fig.text(0.034, 0.893,
         "唯一由廠商「文字」陳述過的遠場，是 tutorial 寫的 “a circle of radius 3 units with center 1 0” — 下排左一。其餘三種是本次自建，各自列出量到的代價。",
         color=SEC, fontsize=10.8, va="bottom")
fig.savefig(sys.argv[1], dpi=96, facecolor="#fcfcfb")
print("wrote", sys.argv[1])
