#!/usr/bin/env python3
"""The residual histories of section 16a's five runs, as one chart.

A RESEARCH HARNESS beside ``docs/research/gridpro-blocking-method.md``. The
numbers are TRANSCRIBED from the runs rather than read back out of
``results/solver/``, because those directories are not committed -- each row
names the pipeline script that reproduces it, and section 16c's table carries
the same figures in text.

    python3 docs/research/gridpro-blocking-method/plot_residuals.py
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                  # noqa: E402
from matplotlib.ticker import LogLocator, NullFormatter          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# The reference palette of the `dataviz` skill, categorical slots 1-4 in its
# fixed order. Validated for this chart: worst adjacent CVD dE 9.1, worst
# adjacent normal-vision dE 22.9, both above their floors; two slots are under
# 3:1 against the surface, which is why every series is DIRECT-LABELLED rather
# than carried by a legend box.
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"

IT = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]
SERIES = [
    ("C/H, --turn-blend 1.0  (shipped)", "#2a78d6",
     [1.458e-4, 1.299e-4, 1.413e-4, 1.780e-4, 1.648e-4,
      1.041e-4, 1.229e-4, 1.100e-4, 9.037e-5]),
    ("C/H, --turn-blend 0.6", "#eb6834",
     [8.012e-5, 2.706e-5, 8.833e-6, 1.150e-5, 3.720e-6,
      2.343e-6, 2.055e-6, 1.942e-6, 8.845e-7]),
    ("the repo's C-grid, same box, same cells", "#1baf7a",
     [1.382e-4, 1.414e-5, 6.726e-6, 4.728e-6, 3.035e-6,
      2.707e-6, 3.079e-6, 6.217e-6, 6.633e-6]),
    ("the repo's C-grid, as shipped (30x20 box)", "#eda100",
     [5.257e-5, 8.586e-6, 4.110e-6, 4.052e-6, 4.105e-6,
      1.608e-6, 5.376e-6, 2.996e-6, 2.913e-6]),
]


def main():
    fig, ax = plt.subplots(figsize=(12.6, 6.4), dpi=110)
    fig.patch.set_facecolor(SURF)
    ax.set_facecolor(SURF)
    for name, colour, y in SERIES:
        ax.plot(IT, y, color=colour, lw=2, marker="o", ms=5.5,
                mec=SURF, mew=1.4, zorder=3)
        ax.annotate(name, (IT[-1], y[-1]), xytext=(11, 0),
                    textcoords="offset points", va="center", ha="left",
                    fontsize=10, color=INK2)
    ax.set_yscale("log")
    ax.yaxis.set_minor_locator(
        LogLocator(base=10, subs=tuple(range(2, 10)), numticks=20))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.grid(True, which="major", color=GRID, lw=0.9, zorder=0)
    ax.grid(True, which="minor", color=GRID, lw=0.5, alpha=0.55, zorder=0)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=10)
    ax.set_xticks([1000, 3000, 5000, 7000, 9000])
    ax.set_xlabel("iteration", color=INK2, fontsize=11)
    ax.set_ylabel("residual   (worst of row, unicones.enorm.cli)",
                  color=INK2, fontsize=11)
    ax.set_xlim(600, 9000)
    ax.set_ylim(5e-7, 3e-4)
    fig.subplots_adjust(left=0.085, right=0.705, top=0.845, bottom=0.105)
    fig.text(0.085, 0.955,
             "Only the mesh with the tiny leading-edge cells fails to converge",
             color=INK, fontsize=14, ha="left")
    fig.text(0.085, 0.905,
             "laminar NS, M 0.2, Re 200, cfl 0.6 — identical boundary flags, "
             "so the mesh is the only difference",
             color=INK2, fontsize=10, ha="left")
    out = os.path.join(HERE, "residual_compare.png")
    fig.savefig(out, facecolor=SURF)
    print("wrote", os.path.relpath(out, os.path.join(HERE, "..", "..", "..")))


if __name__ == "__main__":
    main()
