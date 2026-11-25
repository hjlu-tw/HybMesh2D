#!/usr/bin/env python3
"""Do GridPro's radial block boundaries CONTINUE through its concentric bands?

    curl -sSL -A Mozilla/5.0 -o /tmp/img12.png \
      https://media.gridpro.com/wp-content/uploads/2017/10/img12.png
    python3 docs/research/gridpro-blocking-method/measure_vendor_bands.py /tmp/img12.png

Section 29g left this reading UNRESOLVED and out of its table: if the boundaries
stagger between bands, the count changes across them and that is #192's
count-reducing device appearing in the vendor's own figure -- which would be the
most important structural item in the whole comparison.

WHY IT IS MEASURABLE AT ALL. Two things, both found the hard way:

  * **This figure colours each block's GRID LINES in that block's own colour**,
    so a colour boundary is a block boundary and not a shading choice.
  * **The lossless PNG, not the WebP.** Both are 700x1064, but the WebP's lossy
    compression smears the panel into 81,346 distinct colours whose 24
    commonest cover 5.6% of it; the PNG has 11,129 whose 24 commonest cover
    57.4%. Section 29d's automated attempt, run on the WebP, returned 3, 4, 2
    and 4 colour changes at four radii where the eye sees about twenty -- and
    that was the SOURCE, not the method.

The method: quantise the panel to its own dominant palette, walk circles about
the body centre, take each angular sample as the modal palette index over a
short radial window, and report the RUNS. Two radii in the same band should give
the same run boundaries; two radii across a band seam should not, IF the
boundaries stagger.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

PANEL = (0, 358, 700, 706)        # img12's middle panel, separators re-derived
CENTRE = (348.0, 174.0)           # the body's own centre in panel coordinates
CHORD_PX = 140.0                  # read off a 2x crop, +-15 (section 29d)


def palette(A, k=24):
    """The k commonest colours, which this figure's own blocks mostly are."""
    cols, counts = np.unique(A.reshape(-1, 3), axis=0, return_counts=True)
    return cols[np.argsort(counts)[::-1][:k]].astype(float)


def ring_labels(A, pal, r, n=2880, window=3):
    """The modal palette index at each of n angles on the circle of radius r."""
    h, w, _ = A.shape
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    out = np.full(n, -1)
    for i, t in enumerate(th):
        votes = []
        for dr in range(-window, window + 1):
            x = int(round(CENTRE[0] + (r + dr) * np.cos(t)))
            y = int(round(CENTRE[1] + (r + dr) * np.sin(t)))
            if 0 <= x < w and 0 <= y < h:
                d = np.linalg.norm(pal - A[y, x].astype(float), axis=1)
                votes.append(int(np.argmin(d)))
        if votes:
            out[i] = np.bincount(votes).argmax()
    return out


def runs(lab, min_len=12):
    """(start_index, label) per run, runs shorter than min_len absorbed."""
    n = len(lab)
    edges = [i for i in range(n) if lab[i] != lab[i - 1]]
    if not edges:
        return []
    out = []
    for j, i in enumerate(edges):
        nxt = edges[(j + 1) % len(edges)]
        length = (nxt - i) % n or n
        if length >= min_len:
            out.append((i, int(lab[i])))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="img12.png -- the LOSSLESS one, see the docstring")
    ap.add_argument("--radii", nargs="*", type=float,
                    default=[55, 70, 85, 100, 115, 130, 145, 160])
    a = ap.parse_args()
    if a.src.lower().endswith(".webp"):
        print("WARNING: the WebP is lossy and section 29d measured that this "
              "method fails on it. Fetch the .png.", file=sys.stderr)
    A = np.asarray(Image.open(a.src).convert("RGB").crop(PANEL))
    pal = palette(A)
    print("panel %dx%d, centre (%.0f, %.0f), chord %.0f px"
          % (A.shape[1], A.shape[0], CENTRE[0], CENTRE[1], CHORD_PX))
    print("\n%-8s %-9s %-6s %s" % ("r (px)", "r (chord)", "runs", "run-boundary angles (deg)"))
    prev = None
    rows = []
    for r in a.radii:
        rr = runs(ring_labels(A, pal, r))
        deg = sorted(round(i * 360.0 / 2880.0, 1) for i, _ in rr)
        rows.append((r, deg))
        print("%-8.0f %-9.2f %-6d %s" % (r, r / CHORD_PX, len(deg),
                                         " ".join("%.0f" % d for d in deg[:18])
                                         + (" ..." if len(deg) > 18 else "")))
    print("\nHOW MANY OF ONE RADIUS'S BOUNDARIES THE NEXT ONE ALSO HAS (within 2 deg):")
    for (r1, d1), (r2, d2) in zip(rows, rows[1:]):
        if not d1:
            continue
        hit = sum(1 for x in d1 if any(min(abs(x - y), 360 - abs(x - y)) <= 2.0 for y in d2))
        print("   r = %-4.0f -> %-4.0f   %2d of %2d carried through (%.0f%%)"
              % (r1, r2, hit, len(d1), 100.0 * hit / len(d1)))
    print("\nA blocking whose radials CONTINUE carries nearly all of them through.")
    print("One that STAGGERS does not -- and that is #192's device in this figure.")


if __name__ == "__main__":
    main()
