#!/usr/bin/env python3
"""Read node counts and extents OFF the target figures, instead of guessing.

A RESEARCH HARNESS. Nothing shipped reads it.

WHY THIS EXISTS. Four reproductions are being drawn against eight published
screenshots (entry 17 of ``docs/research/gridpro-mesh-samples/``), and the one
thing a reproduction can get wrong without anybody noticing is the DENSITY: a
blocking that is right and a node count that is three times out still does not
look like the target. The thesis prints no per-block counts on any of these
eight figures -- ``gridpro-mesh-samples/FIGURE-INDEX.md`` records the whole
entry as "95 (Grid 3), 51,465 points", which is a figure for a DIFFERENT case in
the same document -- so every count here is measured off the picture.

THE TWO MEASUREMENTS, and the limits of each.

``rings`` counts how many grid lines cross a circle drawn on the image. It
samples the circle at sub-pixel steps, calls a pixel INKED when it is far enough
from white, and counts runs of inked pixels. It is reliable where the lines are
separated by more than about two pixels and under-counts where they are not, so
it is run at SEVERAL radii and the largest reading is the one to quote: a
smaller reading further in is the image running out of resolution, not the grid
running out of lines.

``axes`` finds the plot frame (the outermost long black rows and columns) so a
pixel radius can be turned into a data radius. It needs the caller to say what
data value each frame edge is at, which is read off the printed tick labels by
eye -- that is the one input here that is not measured by the machine.

    python3 docs/research/allampalli-2010-reproductions/measure_target.py
"""

import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "..", "gridpro-mesh-samples")


def load(name):
    im = Image.open(os.path.join(SAMPLES, name)).convert("RGB")
    return np.asarray(im).astype(np.int16)


def inked(a, thresh=120):
    """True where the pixel is far enough from white to be a drawn line."""
    return (765 - a.sum(axis=2)) > thresh


def frame(a):
    """``(x0, x1, y0, y1)`` of the plot frame, in pixels.

    The Tecplot frame these figures carry is a long black rectangle. Rows and
    columns whose DARK fraction is over 80% are its edges; the outermost such
    pair in each direction is the frame.
    """
    dark = (a.sum(axis=2) < 200)
    rows = np.where(dark.mean(axis=1) > 0.8)[0]
    cols = np.where(dark.mean(axis=0) > 0.8)[0]
    if len(rows) < 2 or len(cols) < 2:
        return None
    return int(cols[0]), int(cols[-1]), int(rows[0]), int(rows[-1])


def rings(name, cx, cy, radii, thresh=120):
    """Lines crossing each circle of pixel radius r about ``(cx, cy)``."""
    a = load(name)
    ink = inked(a, thresh)
    h, w = ink.shape
    out = []
    for r in radii:
        n = max(2000, int(16 * math.pi * r))
        hits = []
        for k in range(n):
            th = 2.0 * math.pi * k / n
            x, y = int(round(cx + r * math.cos(th))), int(round(cy - r * math.sin(th)))
            hits.append(bool(ink[y, x]) if 0 <= x < w and 0 <= y < h else False)
        runs = sum(1 for k in range(n) if hits[k] and not hits[k - 1])
        out.append((r, runs))
    return out


def scan(name, x0, x1, y, thresh=120):
    """Lines crossed by the horizontal pixel row ``y`` between x0 and x1."""
    a = load(name)
    ink = inked(a, thresh)
    row = ink[y, x0:x1]
    return int(np.sum(row[1:] & ~row[:-1])) + (1 if row[0] else 0)


def white_blob(name, box):
    """The bounding box of the largest white region inside ``box`` -- the hole
    a body leaves in the mesh. ``box`` is ``(x0, x1, y0, y1)`` in pixels."""
    a = load(name)
    ink = inked(a, 60)
    x0, x1, y0, y1 = box
    sub = ~ink[y0:y1, x0:x1]
    cols = np.where(sub.sum(axis=0) > 0.5 * sub.shape[0] * 0)[0]
    rows = np.where(sub.all(axis=1))[0]
    del cols, rows
    # Largest axis-aligned all-white run per row / per column.
    best_r = max(((int(np.sum(sub[j])), j) for j in range(sub.shape[0])),
                 default=(0, 0))
    best_c = max(((int(np.sum(sub[:, i])), i) for i in range(sub.shape[1])),
                 default=(0, 0))
    return best_r, best_c


def main():
    print("=" * 72)
    print("fig6-16  close-up, cylinder")
    a = load("entry17-allampalli2010-fig6-16-close-up-view-grid-near-cylinder.png")
    fr = frame(a)
    print("  frame px %s   image %s" % (fr, a.shape[:2]))
    # The cylinder is the white hole. Find its widest all-white row/column.
    h, w = a.shape[:2]
    ink = inked(a, 60)
    best = None
    for j in range(fr[2] + 2, fr[3] - 2):
        row = ~ink[j, fr[0] + 2:fr[1] - 2]
        run = cur = 0
        start = s0 = 0
        for i, v in enumerate(row):
            if v:
                if cur == 0:
                    s0 = i
                cur += 1
                if cur > run:
                    run, start = cur, s0
            else:
                cur = 0
        if best is None or run > best[0]:
            best = (run, j, start + fr[0] + 2)
    print("  widest white row: %d px at y=%d starting x=%d" % best)
    cx = best[2] + best[0] / 2.0
    cy = best[1]
    print("  cylinder centre px (%.1f, %.1f), radius px %.1f" % (cx, cy, best[0] / 2.0))
    rpx = best[0] / 2.0
    for r, n in rings("entry17-allampalli2010-fig6-16-close-up-view-grid-near-cylinder.png",
                      cx, cy, [rpx * 1.15, rpx * 1.4, rpx * 1.8, rpx * 2.4,
                               rpx * 3.2]):
        print("    r/a = %.2f : %3d line crossings  -> %d around" %
              (r / rpx, n, n))
    print()
    print("=" * 72)
    print("fig6-3  flat-plate leading edge")
    nm = "entry17-allampalli2010-fig6-3-grid-near-leading-edge-flat-plate.png"
    a = load(nm)
    fr = frame(a)
    print("  frame px %s   image %s" % (fr, a.shape[:2]))
    print()
    print("=" * 72)
    print("fig5-1  NACA0012 complete grid")
    nm = "entry17-allampalli2010-fig5-1-complete-grid-naca0012-airfoil.png"
    a = load(nm)
    fr = frame(a)
    print("  frame px %s   image %s" % (fr, a.shape[:2]))


if __name__ == "__main__":
    sys.exit(main())
