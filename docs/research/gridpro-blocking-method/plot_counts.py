import sys, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK", "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

INK, SEC, MUT, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
GPC, MEC = "#2a78d6", "#eb6834"

# (label, blocks, cells, is_gridpro)
CASES = [
    ("GridPro 翼型 tutorial（廠商對話框報的）", 14, 4608, True),
    ("§8 我對它的重現（同樣 14 塊）", 14, 17408, False),
    ("§11 O-ring", 38, 17408, False),
    ("§21 照 fig5 改寫的 O-ring", 38, 18528, False),
    ("§13 C/H 單層", 24, 18240, False),
    ("§17 C/H 三層（fig6 形狀）", 120, 25984, False),
    ("§18 C/H + H 型遠場", 160, 33408, False),
    ("本倉庫 shipped C-grid", 4, 11520, False),
]
rows = sorted(CASES, key=lambda c: c[2] / c[1])
gp = next(c[2] / c[1] for c in CASES if c[3])

fig = plt.figure(figsize=(15.0, 11.0), facecolor="#fcfcfb")
ax = fig.add_axes([0.335, 0.432, 0.635, 0.292])
ax.set_facecolor("#fcfcfb")
ys = range(len(rows))
for y, (lab, nb, nc, isgp) in zip(ys, rows):
    v = nc / nb
    col = GPC if isgp else MEC
    ax.barh(y, v, height=0.52, color=col, zorder=3)
    ax.text(v + 28, y, "%d" % round(v), va="center", ha="left",
            color=INK, fontsize=11.2, zorder=4)
    ax.text(-38, y, lab, va="center", ha="right", color=INK if isgp else SEC,
            fontsize=11.2, zorder=4)
    ax.text(-38, y - 0.33, "%d 塊 · %d cell" % (nb, nc), va="center", ha="right",
            color=MUT, fontsize=9.4, zorder=4)
ax.axvline(gp, color=GPC, lw=1.4, ls=(0, (5, 4)), zorder=2)
ax.text(gp + 10, len(rows) - 0.42, "GridPro 的 %d" % round(gp), color=GPC,
        fontsize=10.6, va="bottom")
ax.set_ylim(-0.75, len(rows) - 0.25); ax.set_xlim(0, 3250)
ax.set_yticks([]); ax.tick_params(colors=MUT, labelsize=10)
ax.grid(True, axis="x", color=GRID, lw=0.7); ax.set_axisbelow(True)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(AXIS)
ax.set_xlabel("每塊的 cell 數（越小＝越倚賴分區、越少倚賴加密節點）",
              color=SEC, fontsize=11, labelpad=9)
ax.set_title("分區數量：唯一有廠商數字的那一個，和我做過的七個", color=INK,
             fontsize=14, pad=12, loc="left")

tb = fig.add_axes([0.031, 0.035, 0.938, 0.355]); tb.axis("off")
PAIRS = [
    ("角點的位置", "一個「猜測」，DBC 把它鬆弛到曲面上",
     "一個「宣告」，沒有任何東西會移動它"),
    ("區塊形狀不好時", "加更多區塊（廠商文字明寫的規則）",
     "同左，但加區塊要先通過拒絕檢查"),
    ("尾緣處理", "外角等分，3 支內部曲面（tutorial）",
     "同左，而且角度是從本倉庫翼型自己的切線導出"),
    ("節點數怎麼定", "逐邊的 point wise distribution",
     "`count` 是等價類的「種子」，對邊自動跟隨"),
    ("平滑器", "鬆弛會移動角點與界面",
     "宣告過形狀的邊被凍結，只有普通界面可動"),
]
tb.text(0.0, 0.925, "分區策略：同一欄的兩邊不是風格差異，是「誰能移動東西」的差異",
        transform=tb.transAxes, color=INK, fontsize=14, va="bottom")
tb.plot([0, 1], [0.905, 0.905], transform=tb.transAxes, color=GRID, lw=1.0, clip_on=False)
for c, h, col in ((0.0, "", MUT), (0.175, "GridPro", GPC), (0.575, "本倉庫 MESH_MODE 1", MEC)):
    if h:
        tb.text(c, 0.845, h, transform=tb.transAxes, color=col, fontsize=11.4, va="bottom")
for i, (k, a, b) in enumerate(PAIRS):
    y = 0.715 - i * 0.145
    tb.text(0.0, y, k, transform=tb.transAxes, color=INK, fontsize=11.4, va="bottom")
    tb.text(0.175, y, a, transform=tb.transAxes, color=SEC, fontsize=11, va="bottom")
    tb.text(0.575, y, b, transform=tb.transAxes, color=SEC, fontsize=11, va="bottom")
    tb.plot([0, 1], [y - 0.038, y - 0.038], transform=tb.transAxes,
            color=GRID, lw=0.6, clip_on=False)
tb.text(0.0, 0.015,
        "最後一列是前面每一次拒絕的根源：GridPro 的角點會自己讓開，所以外角等分在更多射線下仍然可行；"
        "這裡沒有東西會讓開，所以同一條規則在 --te-rays 5 就把徑向推到交叉（§21c）。",
        transform=tb.transAxes, color=SEC, fontsize=10.5, va="bottom")

fig.text(0.031, 0.950, "分區數量與策略的比較", color=INK, fontsize=21, va="bottom")
for i, ln in enumerate([
    "數量只有一個數字有廠商來源：tutorial 自己的對話框報的 14 塊 / 4608 cell（§L2，[V]）。fig5 的塊數「量不出來」——三種方法都沒過對照組，見下方。",
    "所以比得了的是「每塊幾個 cell」：這正是廠商自己那條規則（「區塊形狀不好就加區塊，不是加節點」）可以被量化的方式。",
    "我在同樣 14 塊上用了 3.8 倍的 cell（1243 對 329）；O-ring 家族落在 458–488；而 §17 / §18 的 C/H 以 217 / 209 比 GridPro 還更倚賴分區。",
]):
    fig.text(0.031, 0.912 - i * 0.0245, ln, color=SEC, fontsize=10.6, va="bottom")
for i, ln in enumerate([
    "三種想數 fig5 塊數的方法，全部沒過對照組：沿圓周數顏色段（隨半徑在 7–21 之間跳）；沿圓周數格線交點（我真值 96 的網格被回報成 157–204）；",
    "逐色連通區塊（我真值 38 的網格被回報成 96）。三個數字都沒有被引用。",
]):
    fig.text(0.031, 0.822 - i * 0.0235, ln, color=MUT, fontsize=10.2, va="bottom")
fig.savefig(sys.argv[1], dpi=96, facecolor="#fcfcfb")
print("wrote", sys.argv[1])
