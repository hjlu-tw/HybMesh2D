#!/usr/bin/env python3
"""This repo's reducing stack beside the one PUBLISHED mesh that does the same
thing -- and the first measurement of a GridPro mesh's own line count anywhere
in these notes.

The published figure is Figure 4 of Stern, Barnhardt, Venkatapathy, Candler &
Prabhu, *Investigation of transonic wake dynamics for mechanically deployable
entry systems*, IEEE Aerospace 2012, NTRS 20120011649 -- the one third-party
GridPro case in ``docs/research/gridpro-meshes-in-published-cfd.md`` whose
blocking visibly REDUCES outward, and whose authors call it a "nested
topological refinement strategy".

THE SOURCE IMAGE IS NOT COMMITTED and is passed in as a path, which is the
convention ``plot_vs_fig5.py`` and ``plot_vs_video_frame.py`` beside this file
already follow and that ``gridpro-blocking-method.md``'s Sources states. Get it
with::

    curl -sSL -o /tmp/stern.pdf \
      https://ntrs.nasa.gov/api/citations/20120011649/downloads/20120011649.pdf
    pdfimages -f 3 -l 3 -png /tmp/stern.pdf /tmp/stern   # figure 4 is -001

WHAT IS MEASURED, and why it is a NEW quantity for these notes. Section 15g of
``nesting-blocks-at-a-complicated-leading-edge.md`` names as a blind spot that
"GridPro's own N(r) is NOT plotted anywhere here", because their meshes reach us
as pictures. A picture can still be counted: along a horizontal cut through
Figure 4, each near-vertical grid line is one short dark run, so the lines
crossing that cut can be counted off the raster.

**BUT ONLY WHERE THE RASTER RESOLVES THEM.** Over the lower ~39% of that figure
the median white gap between lines is 2 px and the row is 50-66% ink: adjacent
lines merge and the count is a severe UNDERCOUNT (row 544 returns 229 where row
384 returns 428, which is the saturation and not the mesh). The saturation line
is computed here, drawn on panel (a), and everything below it is excluded.

TWO ARTEFACTS ARE LEFT IN PANEL (c) RATHER THAN SMOOTHED AWAY, because both are
the instrument and not the mesh: the blue curve spikes a little above 1.0 where
the sampling circle happens to lie along one of the scalloped interfaces (the
same coincidence ``plot_reduction.py`` blanks at a ring interface, but here it
is 1.17 against 1.0 and no threshold separates it), and the red curve is rough
because it is a count off a raster. Neither is thresholded, because a threshold
that cannot be stated is a smoothing.

AND THE TWO X-AXES CANNOT BE PUT ON ONE PHYSICAL SCALE. Theirs is height above a
wake behind an 8.6 m capsule; ours is radius about a unit circle. Section 8b of
the nesting note already settled the honest move for exactly this -- compare the
SHAPE, say the scale cannot be matched -- so panel (c) plots each curve against
the fraction of its own countable span, normalised to 1.0 at its innermost
countable cut. **It is a comparison of shape and nothing else.**

    python3 docs/research/gridpro-blocking-method/plot_vs_stern_fig4.py \
        /tmp/stern-001.png /tmp/rsd.vtk vs_stern_fig4.png
"""

import os
import sys

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402
from matplotlib.collections import LineCollection                 # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_block_partition import read_vtk                      # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
DARK, MAX_RUN, MIN_GAP = 150, 6, 2.5


def row_lines(dark, y):
    """Near-vertical grid lines crossing row `y`, and the median white gap."""
    d, W = dark[y], dark.shape[1]
    n, i, gaps = 0, 0, []
    while i < W:
        j = i
        if d[i]:
            while j < W and d[j]:
                j += 1
            if j - i <= MAX_RUN:
                n += 1
        else:
            while j < W and not d[j]:
                j += 1
            gaps.append(j - i)
        i = j
    return n, (float(np.median(gaps)) if gaps else 0.0)


def published(path):
    g = np.asarray(Image.open(path).convert("L"))
    dark = g < DARK
    H = g.shape[0]
    rows = list(range(H - 1, 0, -4))
    cnt = [row_lines(dark, y) for y in rows]
    # The saturation line: the LOWEST row from which every row above resolves.
    ok = [i for i, (_, gap) in enumerate(cnt) if gap >= MIN_GAP]
    first = min(ok) if ok else 0
    for i in range(first, len(cnt)):
        if cnt[i][1] < MIN_GAP:
            first = i + 1
    sat = rows[first]
    d = np.array([(H - 1 - rows[i]) for i in range(first, len(rows))], float)
    n = np.array([cnt[i][0] for i in range(first, len(rows))], float)
    # Over the COUNTABLE span and not the whole figure, which is what panel
    # (c)'s axis label claims. A first draft divided by the full height and the
    # curve started at 0.39, disagreeing with the label beside it.
    return g, sat, (d - d[0]) / (d[-1] - d[0]), n / n[0]


def body_polyline():
    """The shipped aerofoil, as the polyline this repo's walls bind to."""
    out = []
    with open(os.path.join(ROOT, "examples/geometries/naca0012_cgrid.dat"),
              encoding="utf-8") as f:
        for ln in f:
            t = ln.split()
            if len(t) >= 2:
                try:
                    out.append((float(t[0]), float(t[1])))
                except ValueError:
                    pass
    return np.array(out)


def dist_to_body(P, body):
    """Distance from each point to the aerofoil POLYLINE, by segment."""
    A, B = body[:-1], body[1:]
    d = B - A
    L2 = (d * d).sum(1)
    L2[L2 == 0] = 1e-30
    t = ((P[:, None, 0] - A[None, :, 0]) * d[None, :, 0]
         + (P[:, None, 1] - A[None, :, 1]) * d[None, :, 1]) / L2[None, :]
    t = np.clip(t, 0.0, 1.0)
    cx = A[None, :, 0] + t * d[None, :, 0]
    cy = A[None, :, 1] + t * d[None, :, 1]
    return np.hypot(P[:, None, 0] - cx, P[:, None, 1] - cy).min(1)


def ours(path, body=None):
    pts, cells, _ = read_vtk(path)
    seen, seg = set(), []
    for ids in cells:
        for k in range(len(ids)):
            a, b = ids[k], ids[(k + 1) % len(ids)]
            key = (a, b) if a < b else (b, a)
            if key not in seen:
                seen.add(key)
                seg.append((a, b))
    e = np.array(seg)
    if body is None:                      # a RING: distance from its centre
        ra = np.linalg.norm(pts[e[:, 0]], axis=1)
        rb = np.linalg.norm(pts[e[:, 1]], axis=1)
        radii = np.geomspace(0.52, 9.8, 200)
    else:
        # AN AEROFOIL IS NOT A RING. Circles about the origin are not iso-lines
        # of anything here, and counting edges that cross them reported this
        # repo's own aerofoil stack as NOT FALLING (1.06 of its innermost cut)
        # when its station counts halve twice. The quantity that means the same
        # thing on both shapes is the distance to the BODY, so the cut is the
        # iso-distance contour and not a circle.
        dd = dist_to_body(pts, body)
        ra, rb = dd[e[:, 0]], dd[e[:, 1]]
        radii = np.geomspace(0.02, 8.0, 200)
    lo, hi = np.minimum(ra, rb), np.maximum(ra, rb)
    # STRICTLY straddling, so an edge lying exactly ON the circle is not
    # counted: that is the artefact plot_reduction.py blanks at a ring
    # interface, and here it showed as spikes above 1.0 near the body.
    n = np.array([int(((lo < r) & (hi > r)).sum()) for r in radii], float)
    return pts, cells, (radii - radii[0]) / (radii[-1] - radii[0]), n / n[0]


def main():
    src, vtk, out = sys.argv[1], sys.argv[2], sys.argv[3]
    aero = "--aerofoil" in sys.argv
    g, sat, xd, yd = published(src)
    pts, cells, xo, yo = ours(vtk, body_polyline() if aero else None)

    fig = plt.figure(figsize=(13.2, 8.4), facecolor="white")
    # (a) the published figure, cropped — a QUOTATION of part of it, which is
    # what the composites beside this file do.
    a1 = fig.add_axes([0.035, 0.555, 0.93, 0.40])
    crop = g[:, :int(0.62 * g.shape[1])]
    a1.imshow(crop, cmap="gray", vmin=0, vmax=255)
    a1.axhline(sat, color="C3", lw=1.2, ls="--")
    a1.text(12, sat - 14, "saturation line — BELOW THIS the raster cannot "
            "resolve the lines and the count is a severe undercount",
            color="C3", fontsize=8, va="bottom",
            bbox=dict(facecolor="white", edgecolor="C3", pad=2.0, alpha=0.92))
    a1.set_axis_off()
    a1.set_title("(a)  Stern et al. 2012, Figure 4 (crop) — \"nested topological "
                 "refinement\", GridPro.  Source image not committed.",
                 fontsize=9, loc="left")

    # (b) ours, in the same ink
    a2 = fig.add_axes([0.035, 0.085, 0.42, 0.40])
    sg = []
    for ids in cells:
        for k in range(len(ids)):
            sg.append([pts[ids[k]], pts[ids[(k + 1) % len(ids)]]])
    a2.add_collection(LineCollection(np.array(sg), colors="k", linewidths=0.3))
    a2.set_xlim(-2.4, 3.0) if aero else a2.set_xlim(-3.2, 3.2)
    a2.set_ylim(-2.7, 2.7) if aero else a2.set_ylim(-3.2, 3.2)
    a2.set_aspect("equal"); a2.set_axis_off()
    a2.set_title("(b)  this repo, %s" % os.path.basename(vtk), fontsize=9,
                 loc="left")

    # (c) the shapes, each against its own span
    a3 = fig.add_axes([0.545, 0.115, 0.42, 0.355])
    a3.plot(xd, yd, "C3-", lw=1.4, label="Stern Fig. 4, counted off the raster")
    a3.plot(xo, yo, "C0-", lw=1.4,
            label="this repo, exact (%s)" % ("distance to the body" if aero
                                             else "radius"))
    a3.set_xlabel("distance from the refined band, as a fraction of each\n"
                  "figure's OWN countable span (the scales are NOT matched)",
                  fontsize=8)
    a3.set_ylabel("grid lines crossing the cut,\nnormalised to its innermost cut",
                  fontsize=8)
    a3.tick_params(labelsize=8)
    a3.grid(alpha=0.3)
    a3.legend(fontsize=7.5)
    a3.set_title("(c)  both FALL; only the shape is compared", fontsize=9,
                 loc="left")
    note = ("the blue curve RISES first because an iso-distance contour about an "
            "aerofoil grows to\ntake in the wake, where the mesh stays fine — "
            "that is the measure and not an artefact"
            if aero else
            "the blue spikes above 1.0 near the body are the sampling circle "
            "lying along a\nscalloped interface — the same coincidence "
            "plot_reduction.py blanks")
    a3.text(0.015, 0.03, note + ";\nthe red curve's roughness is the raster "
            "count, not the mesh",
            transform=a3.transAxes, fontsize=6.5, color="0.35")
    fig.savefig(out, dpi=170)
    print("wrote %s" % out)
    print("  published: saturation line at row %d of %d; countable span falls "
          "to %.2f of its innermost cut" % (sat, g.shape[0], yd[-1]))
    print("  ours:      falls to %.2f of its innermost cut (%s)"
          % (yo[-1], "distance to the body" if aero else "radius"))


if __name__ == "__main__":
    main()
