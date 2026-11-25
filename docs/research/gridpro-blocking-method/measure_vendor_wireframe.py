#!/usr/bin/env python3
"""N(r) off GridPro's OWN topology wireframe -- the vendor side §15g lacked.

    curl -sSL -A Mozilla/5.0 -o /tmp/img11_1.png \
      https://media.gridpro.com/wp-content/uploads/2017/11/img11_1.png
    python3 docs/research/gridpro-blocking-method/measure_vendor_wireframe.py /tmp/img11_1.png

Section 15a's instrument is N(r): how many block-partition lines cross a circle
of radius r. A terminating blocking FALLS; a propagating one is FLAT. Section
15g named the missing half -- no vendor side -- and §16j said in as many words
that it "takes no count off the vendor raster". This takes one.

WHY THIS FIGURE AND NOT img12. img12 is a MESH coloured by block, so a circle
crosses grid lines and block boundaries alike and telling them apart needs the
colour, which §29j measured as hopeless: on a mesh whose radials are DECLARED
continuous the same method carried only 55-68% of boundaries through, so it
could not have distinguished anything. `img11_1`'s first panel is a TOPOLOGY
WIREFRAME on black -- the drawing IS the partition, there is no grid to confuse
-- and the body spans about 380 px here against img12's 140, so every figure is
2.7x better resolved per chord.

The method: walk a circle, find the bright RUNS, and keep the short ones. A
RADIAL link crosses the circle and leaves a short blob; a CONCENTRIC link lies
along it and leaves a long arc, which is rejected by its own angular width --
the raster counterpart of `rings_along`'s 35-degree perpendicularity test.
"""
import argparse
import sys

import numpy as np
from PIL import Image

PANEL = (0, 2, 700, 356)          # the topology wireframe, separators re-derived


def crossings(A, centre, r, n=4320, max_run_deg=6.0, thresh=42):
    """(count, angles, fraction of the circle INSIDE the panel).

    The fraction is not decoration. This panel is a CROP -- the wireframe runs
    off its edges -- so clipping an off-frame sample to the edge pixel makes
    N(r) FALL for the crop's reasons and not the blocking's, which is exactly
    what §18d had to retract about fig6. A count whose circle is only part
    inside is reported as such and never compared with a whole one.
    """
    h, w = A.shape
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    xf = centre[0] + r * np.cos(th)
    yf = centre[1] + r * np.sin(th)
    inside = (xf >= 0) & (xf < w) & (yf >= 0) & (yf < h)
    frac = float(inside.mean())
    xs = np.clip(xf.astype(int), 0, w - 1)
    ys = np.clip(yf.astype(int), 0, h - 1)
    lit = (A[ys, xs] > thresh) & inside
    if not lit.any():
        return 0, [], frac
    edges = [i for i in range(n) if lit[i] and not lit[i - 1]]
    out = []
    for i in edges:
        j, L = i, 0
        while L < n and lit[(i + L) % n]:
            L += 1
        if L * 360.0 / n <= max_run_deg:
            out.append(round(((i + L / 2.0) % n) * 360.0 / n, 1))
    return len(out), sorted(out), frac


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="img11_1.png -- the LOSSLESS one")
    ap.add_argument("--centre", nargs=2, type=float, default=[290.0, 172.0],
                    help="the body's centre in panel pixels, read off the crop")
    ap.add_argument("--chord-px", type=float, default=380.0)
    ap.add_argument("--radii", nargs="*", type=float,
                    default=[55, 70, 90, 110, 130, 150, 175, 200, 230])
    a = ap.parse_args()
    if a.src.lower().endswith(".webp"):
        print("WARNING: fetch the .png; the WebP is lossy.", file=sys.stderr)
    img = np.asarray(Image.open(a.src).convert("L").crop(PANEL))
    print("panel %dx%d, centre (%.0f, %.0f), chord %.0f px"
          % (img.shape[1], img.shape[0], a.centre[0], a.centre[1], a.chord_px))
    print("\n%-8s %-10s %-6s %-9s %s"
          % ("r (px)", "r (chord)", "N(r)", "in frame", "per whole circle"))
    for r in a.radii:
        n, _, frac = crossings(img, a.centre, r)
        note = "" if frac > 0.999 else "  <-- PARTIAL, not comparable"
        print("%-8.0f %-10.2f %-6d %-9s %-6s%s"
              % (r, r / a.chord_px, n, "%.0f%%" % (100 * frac),
                 "%.0f" % (n / frac) if frac > 0.2 else "-", note))
    print("\nA TERMINATING blocking falls from left to right. A PROPAGATING one is FLAT.")
    print("Only the rows at 100%% in frame are a reading of the blocking; the rest")
    print("are a reading of the crop, which is §18d's retraction in one line.")


if __name__ == "__main__":
    main()
