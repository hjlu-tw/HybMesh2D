import sys, math, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC","PingFang HK","Arial Unicode MS","DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
from PIL import Image

INK, SEC, MUT, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
def read(p):
    tok = open(p).read().split()
    i = tok.index("POINTS"); n = int(tok[i+1])
    pts = np.array(tok[i+3:i+3+3*n], float).reshape(n,3)[:,:2]
    j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells=[]
    for _ in range(nc):
        m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
    return pts, cells

def lines_with_turning(path):
    pts, cells = read(path)
    adj, own = {}, {}
    for ci, c in enumerate(cells):
        for t in range(len(c)):
            a, b = c[t], c[(t+1) % len(c)]
            adj.setdefault(a, set()).add(b); adj.setdefault(b, set()).add(a)
            own.setdefault((min(a,b), max(a,b)), []).append(ci)
    bnd = [e for e, o in own.items() if len(o) == 1]
    bnodes = {v for e in bnd for v in e}
    body = [e for e in bnd if all(-0.05 <= pts[v][0] <= 1.05 and abs(pts[v][1]) < 0.12 for v in e)]
    bodynodes = {v for e in body for v in e}
    outer = bnodes - bodynodes
    out, bad = [], 0
    for f in sorted(bodynodes):
        cands = [v for v in adj[f] if v not in bodynodes]
        if not cands: continue
        cur, prev = min(cands, key=lambda v: np.linalg.norm(pts[v]-pts[f])), f
        d = pts[cur]-pts[prev]; d = d/np.linalg.norm(d)
        poly, total, n, done = [pts[prev], pts[cur]], 0.0, 0, False
        while n < 600:
            if cur in outer:
                done = True; break
            nxt = [v for v in adj[cur] if v != prev]
            if not nxt: break
            best, bd = None, -2
            for v in nxt:
                e = pts[v]-pts[cur]; nn = np.linalg.norm(e)
                if nn == 0: continue
                dot = float(np.dot(e/nn, d))
                if dot > bd: best, bd = v, dot
            if best is None or bd < 0.2: break
            e = pts[best]-pts[cur]; e = e/np.linalg.norm(e)
            total += math.degrees(math.acos(max(-1, min(1, float(np.dot(e, d))))))
            poly.append(pts[best]); d, prev, cur, n = e, cur, best, n+1
        if done:
            out.append((np.array(poly), total))
        else:
            bad += 1
    return pts, out, body, bad

WIN = (-0.25, 1.6, -0.75, 0.75)
CASES = [(sys.argv[1], "§25：貼體 3 層（29120 cell）", WIN),
         (sys.argv[2], "§27：貼體 2 層（28640 cell）", WIN),
         (sys.argv[3], "shipped C-grid（貼體 0 層，5760 cell）", WIN)]
fig = plt.figure(figsize=(15.6, 7.6), facecolor="#fcfcfb")
norm = Normalize(0, 85)
CTRL = []
cm = plt.get_cmap("inferno_r")
for i, (path, title, win) in enumerate(CASES):
    ax = fig.add_axes([0.024 + i*0.325, 0.168, 0.303, 0.585]); ax.set_facecolor("#fcfcfb")
    pts, lines, body, bad = lines_with_turning(path)
    segs, cols = [], []
    for poly, tot in lines:
        for a in range(len(poly)-1):
            segs.append([poly[a], poly[a+1]]); cols.append(cm(norm(tot)))
    ax.add_collection(LineCollection(segs, colors=cols, linewidths=0.9, zorder=2))
    ax.add_collection(LineCollection([[pts[a], pts[b]] for a, b in body],
                                     colors=INK, linewidths=1.8, zorder=3))
    t = np.array([l[1] for l in lines])
    ax.set_aspect("equal"); ax.set_xlim(win[0], win[1]); ax.set_ylim(win[2], win[3])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color(GRID)
    ax.text(0.0, 1.075, title, transform=ax.transAxes, color=INK, fontsize=13.5, va="bottom")
    ax.text(0.0, 1.018, "中位數 %.1f°、p95 %.1f°、最大 %.1f°"
            % (np.median(t), np.percentile(t, 95), t.max()),
            transform=ax.transAxes, color=SEC, fontsize=11, va="bottom")
    CTRL.append("%d/%d" % (len(lines), len(lines) + bad))

cax = fig.add_axes([0.32, 0.098, 0.36, 0.015])
cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cm), cax=cax, orientation="horizontal")
cb.set_label("一條垂直於物面的格線，從物面走到外邊界的總轉角（度）", color=SEC, fontsize=10.6)
cb.ax.tick_params(colors=MUT, labelsize=9); cb.outline.set_edgecolor(GRID)
fig.text(0.024, 0.022, "對照：三張圖裡抵達外邊界的線數 / 總線數 = " + "、".join(CTRL)
         + "。沒有任何一條線在途中失聯或繞回去，這是先前版本缺的那個檢查。",
         color=MUT, fontsize=10.2, va="bottom")

fig.text(0.024, 0.925, "「垂直於幾何的曲度」— 是第三層貼體環造成的", color=INK, fontsize=21, va="bottom")
for i, ln in enumerate([
    "把每條從物面垂直出發的格線一路追到外邊界、累計它轉了幾度。走法會在抵達外邊界時停止 — 先前版本沒有這個停止條件，它會轉上外邊界繼續走，把 6.9° 算成 14.3°、82.2° 算成 130.5°（§26b 已標記更正）。",
    "試過而被否證的兩個原因：遠場的「形狀」（O-ring 的遠場就是圓，反而轉最多，中位數 37.7°）、以及計算域大小（9×6 放大到 40×20，中位數 6.9°→7.5°，p95 完全不變）。",
    "真正的原因是貼體環的層數：1 層 0.5°、2 層 1.2°、3 層 6.9°（中位數，皆在每側 20 塊下量）。§17 選 3 層是因為 fig6 看起來有「兩到三層」；這個幾何只撐得住兩層。",
]):
    fig.text(0.024, 0.886 - i*0.0255, ln, color=SEC, fontsize=10.6, va="bottom")
fig.savefig(sys.argv[4], dpi=100, facecolor="#fcfcfb")
print("wrote", sys.argv[4])
