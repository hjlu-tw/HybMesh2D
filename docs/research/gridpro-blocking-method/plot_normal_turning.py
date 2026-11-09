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
    body = [e for e in bnd if all(-0.05 <= pts[v][0] <= 1.05 and abs(pts[v][1]) < 0.12 for v in e)]
    bodynodes = {v for e in body for v in e}
    out = []
    for f in sorted(bodynodes):
        cands = [v for v in adj[f] if v not in bodynodes]
        if not cands: continue
        cur, prev = min(cands, key=lambda v: np.linalg.norm(pts[v]-pts[f])), f
        d = pts[cur]-pts[prev]; d = d/np.linalg.norm(d)
        poly, total, n = [pts[prev], pts[cur]], 0.0, 0
        while n < 400:
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
        out.append((np.array(poly), total))
    return pts, out, body

CASES = [(sys.argv[1], "本次 §25 的 C/H（遠場是矩形）", (-0.25, 1.6, -0.75, 0.75)),
         (sys.argv[2], "本倉庫 shipped C-grid（遠場是同心 C 形弧）", (-0.25, 1.6, -0.75, 0.75))]
fig = plt.figure(figsize=(14.6, 8.4), facecolor="#fcfcfb")
norm = Normalize(0, 130)
cm = plt.get_cmap("inferno_r")
for i, (path, title, win) in enumerate(CASES):
    ax = fig.add_axes([0.028 + i*0.487, 0.115, 0.455, 0.655]); ax.set_facecolor("#fcfcfb")
    pts, lines, body = lines_with_turning(path)
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
    ax.text(0.0, 1.018, "每條線的總轉角：中位數 %.1f°、p95 %.1f°、最大 %.1f°"
            % (np.median(t), np.percentile(t, 95), t.max()),
            transform=ax.transAxes, color=SEC, fontsize=11, va="bottom")

cax = fig.add_axes([0.30, 0.062, 0.40, 0.016])
cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cm), cax=cax, orientation="horizontal")
cb.set_label("一條垂直於物面的格線，從物面走到外邊界的總轉角（度）", color=SEC, fontsize=10.6)
cb.ax.tick_params(colors=MUT, labelsize=9); cb.outline.set_edgecolor(GRID)

fig.text(0.028, 0.930, "「垂直於幾何的曲度」— 量出來了", color=INK, fontsize=21, va="bottom")
for i, ln in enumerate([
    "把每條從物面出發、垂直於物面的格線一路追到外邊界，累計它轉了幾度。左圖最糟的線轉了 130.5°，右圖最糟的只有 2.8°。",
    "原因是遠場的「形狀」，不是平滑器：MB_SMOOTH_ITERS 設 0 時最大轉角幾乎不變（且非正交反而更差，53.0° 對 48.4°）。",
    "右圖的遠場是跟物體同心的 C 形弧，所以一條徑向線從頭到尾都還是徑向；左圖要從圓鼻端接到直的入口邊界，方向非得轉過去不可。",
]):
    fig.text(0.028, 0.890 - i*0.0255, ln, color=SEC, fontsize=10.8, va="bottom")
fig.savefig(sys.argv[3], dpi=100, facecolor="#fcfcfb")
print("wrote", sys.argv[3])
