import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC","PingFang HK","Arial Unicode MS","DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
from matplotlib.collections import LineCollection
from PIL import Image
INK, SEC, MUT, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
frame, mesh, out = sys.argv[1], sys.argv[2], sys.argv[3]
img = np.asarray(Image.open(frame).convert("RGB"))[250:450, 280:560]
def read(p):
    tok = open(p).read().split()
    i = tok.index("POINTS"); n = int(tok[i+1])
    pts = np.array(tok[i+3:i+3+3*n], float).reshape(n,3)[:,:2]
    j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells=[]
    for _ in range(nc):
        m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
    b = tok.index("LOOKUP_TABLE"); return pts, cells, [int(x) for x in tok[b+2:b+2+nc]]
fig = plt.figure(figsize=(14.0, 10.4), facecolor="#fcfcfb")
a1 = fig.add_axes([0.035, 0.470, 0.930, 0.330])
a2 = fig.add_axes([0.035, 0.055, 0.930, 0.330])
a1.imshow(img, aspect="equal")
a1.set_xticks([]); a1.set_yticks([])
pts, cells, blk = read(mesh)
own = {}
for ci, c in enumerate(cells):
    for q in range(len(c)):
        e = (c[q], c[(q+1) % len(c)]); e = (min(e), max(e)); own.setdefault(e, []).append(blk[ci])
seam = [[pts[a], pts[b]] for (a, b), o in own.items() if len(o) == 1 or o[0] != o[-1]]
a2.add_collection(LineCollection(seam, colors="#eb6834", linewidths=1.4, zorder=2))
corner = {}
for (a, b), o in own.items():
    if len(o) == 1 or o[0] != o[-1]:
        for v in (a, b): corner[v] = corner.get(v, 0) + 1
cn = np.array([pts[v] for v, k in corner.items() if k >= 6])
if len(cn): a2.plot(cn[:,0], cn[:,1], "s", ms=4, color="#eb6834", zorder=3)
body = [[pts[a], pts[b]] for (a, b), o in own.items() if len(o) == 1
        and -0.05 <= pts[a][0] <= 1.05 and abs(pts[a][1]) < 0.15]
a2.add_collection(LineCollection(body, colors="#1bd4d4", linewidths=2.2, zorder=4))
a2.set_facecolor("black"); a2.set_aspect("equal")
a2.set_xlim(-0.055, 0.33); a2.set_ylim(-0.14, 0.14)
a2.set_xticks([]); a2.set_yticks([])
for ax in (a1, a2):
    for sp in ax.spines.values(): sp.set_color(GRID)
a1.text(0.0, 1.035, "GridPro — 結冰影片的 WIREFRAME 畫面（2FYLCyg8VSA）", transform=a1.transAxes,
        color=INK, fontsize=13, va="bottom")
a1.text(0.0, 1.005, "黃線＝區塊邊，橘方塊＝區塊角點，青線＝結冰物面。字幕：“The forward nest creates a local nesting (loopback structure)”",
        transform=a1.transAxes, color=SEC, fontsize=9.6, va="bottom")
a2.text(0.0, 1.035, "本次 §6 的結冰案例（gridpro_ch_iced，128 塊）", transform=a2.transAxes,
        color=INK, fontsize=13, va="bottom")
a2.text(0.0, 1.005, "同樣只畫區塊邊界與角點。比例尺「沒有」對齊 — 見下方說明",
        transform=a2.transAxes, color=SEC, fontsize=9.6, va="bottom")
fig.text(0.035, 0.955, "跟結冰影片比分區", color=INK, fontsize=20, va="bottom")
for i, ln in enumerate([
    "這一張和 C-grid 那支不同：它的畫面裡翼型弦長「量不到」（物面跑出內嵌面板右緣），而廠商自己的冰形也拿不到（筆記 §5），所以沒有已知尺寸可以定標。",
    "因此這是「結構」的比較，不是同比例的比較 — 跟 C-grid 那張（弦長 406 px、厚弦比 0.118 確認是 NACA 0012）不一樣，那張是可以對齊的。",
    "另外：它的冰是不對稱的單角（上面一個前伸的角、下面平順），我的是對稱雙角 — 那是我自己造的形狀，不是它的。",
]):
    fig.text(0.035, 0.918 - i*0.0245, ln, color=SEC, fontsize=10.4, va="bottom")
fig.savefig(out, dpi=100, facecolor="#fcfcfb"); print("wrote", out)
