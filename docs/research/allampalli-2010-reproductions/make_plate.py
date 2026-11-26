#!/usr/bin/env python3
"""TARGET: entry 17, Figures 6.1, 6.2 and 6.3 -- flow over a flat plate.

A RESEARCH HARNESS. Nothing shipped reads it; nothing in ``config/``,
``examples/``, ``src/`` or ``include/`` is written or changed by it.

WHAT THE TARGET IS, read off the three figures with ``measure_target.py`` and
the block maps it writes.

  * ``fig6-1`` is the whole domain: a RECTANGLE, x in [-2, 3] and y in
    [-1.5, 1.5], with the plate on y = 0 from x = 0 to x = 1.
  * ``fig6-2`` is |x - 0.5| < 0.73, |y| < 0.65. Measured on it: about 70 to 100
    cells along the plate, and about 28 wall-normal lines from the plate out to
    |y| = 0.6, the first of them 0.0056 off the wall -- which is ONE PIXEL, so
    the real first cell is at most that and the figure cannot say less.
  * ``fig6-3`` is |x|, |y| < 0.13 at the leading edge, and it is the one that
    fixes the TOPOLOGY: the plate's nose is a tiny CIRCLE with a full ring of
    small blocks around it, and EIGHT OR MORE block boundaries radiate from
    that ring -- up, up-left, left along y = 0, down-left, down, and the two
    plate surfaces. The plate downstream of the nose is a white sliver two
    pixels tall: it is ZERO THICKNESS to the resolution of the figure.

WHAT IS BEING REPRODUCED, AND THE ONE THING THAT IS NOT.

  REPRODUCED: the rectangular far field at the published extents; the ring
  around the nose and the rays leaving it; the block boundary along y = 0 ahead
  of the plate (the stagnation line) and behind it (the wake line); concentric
  shells around the plate that the chordwise block boundaries live on; the cell
  counts above.

  NOT REPRODUCED, AND IT IS A MODEL LIMIT RATHER THAN A CHOICE: a plate of
  ZERO thickness. In this repo a body is a CLOSED polyline that blocks are
  filled around, and the wall edges on it are sides of exactly one block each
  (`.claude/rules/mesher-block-side.md`, the arity rule). A zero-thickness
  plate needs the upper and lower surface to be two wall edges at the SAME
  coordinates -- which the model would actually ALLOW, since welding is
  allocation and two corners at one coordinate stay two nodes -- but it also
  needs the two of them to MEET at the leading edge in a block with no width,
  and a transfinite fill of a side of zero length is a degenerate block. So the
  plate here is a STADIUM: two flats at y = +-PLATE_H joined by semicircular
  ends of radius PLATE_H. PLATE_H is 0.002, which is 0.7 of a pixel at fig6-2's
  scale and 4 pixels at fig6-3's -- the same two readings the target gives.
  The note beside this file states what a zero-thickness declaration would
  need.

THE BLOCKING, derived rather than drawn. The body is cut into FOURTEEN sides:
the two flats, and six 30-degree sub-arcs on each semicircular end. Every shell
outward is the same fourteen, offset: the offset of a flat is a flat and the
offset of a circular arc is a concentric arc, so a shell needs no geometry file
at all -- its arcs are declared with `curve` (#175) and its flats are straight
chords. FOURTEEN is what the far field asks for: the four corners of the
rectangle must each be a block corner, and so must the stagnation point, the
wake point, and the four stations above and below the plate's two ends.

    python3 docs/research/allampalli-2010-reproductions/make_plate.py [--run]
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mblib                                            # noqa: E402

HERE = mblib.HERE
REL = os.path.relpath(HERE, mblib.ROOT)

PLATE_H = 0.005            # see the docstring: the model cannot take 0
XI, XO, YF = -2.0, 3.0, 1.5
XA, XA2 = -0.25, -1.10     # where the two upstream top/bottom rays land
XB, XB2 = 1.25, 2.00       # and the two downstream ones

WALL_DS = 0.001            # first cell off the plate
SHELL_N = [12, 8, 8, 10]   # radial INTERVALS in each shell around the body
OUTER_N = 20               # radial intervals from the last shell to the box
SHELL_D = 0.60             # where the last shell sits. The growth rate is
                           # SOLVED for from it rather than declared, so the
                           # four shells are ONE geometric sequence cut in four
                           # and the cell size does not jump at a shell
                           # boundary. fig6-2 shows its shells at |y| about
                           # 0.09, 0.13, 0.25 and 0.6; this lands them at the
                           # values the run prints.
FLAT_NODES = 97            # 96 intervals along the plate; measured 70..100
ARC_NODES = 13             # 12 per 30-degree sub-arc. It is the OUTER shell
                           # this number has to suit, not the nose: a count
                           # propagates outward unchanged, so 12 intervals on
                           # an arc 0.0026 long at the plate are the same 12 on
                           # an arc 0.29 long at |y| = 0.55. Raising it to
                           # resolve the far field makes the cells at the nose
                           # 24:1 slivers and the declared wall height
                           # unreachable -- measured, and in the note.
FLAT_DS = 0.0015           # chordwise first cell at each end of a flat
FACET_MULT = 4             # facets per interval on the body polyline


def growth():
    """The ratio g with ``WALL_DS * (g^N - 1)/(g - 1) == SHELL_D``, by
    bisection -- the same shape as the wall-height solve the mesher itself
    does, and for the same reason: the number that matters is the DISTANCE the
    shells reach, not the ratio that gets there."""
    n = sum(SHELL_N)
    lo, hi = 1.0 + 1e-12, 4.0
    for _ in range(200):
        g = 0.5 * (lo + hi)
        s = n * WALL_DS if abs(g - 1.0) < 1e-12 else WALL_DS * (g ** n - 1.0) / (g - 1.0)
        if s < SHELL_D:
            lo = g
        else:
            hi = g
    return 0.5 * (lo + hi)


GROWTH = None              # set by build(); see growth()


def shell_radii():
    """One distance per shell, as the partial sums of ONE geometric radial
    distribution, plus the first cell of the shell AFTER the last."""
    g, out, acc = GROWTH, [], 0.0
    k = 0
    for n in SHELL_N:
        for _ in range(n):
            acc += WALL_DS * g ** k
            k += 1
        out.append(acc)
    return out, WALL_DS * g ** k          # and the first cell of the OUTER shell


# ── the fourteen stations, as angles on the two end circles ───────────────
# Walking the body COUNTER-CLOCKWISE from (0, -R): the bottom flat, the tail
# semicircle in six 30-degree steps, the top flat, the nose semicircle in six.
NOSE = [90, 120, 150, 180, 210, 240, 270]      # about (0, 0)
TAIL = [270, 300, 330, 360, 390, 420, 450]     # about (1, 0)


def station(i, r):
    """Corner ``i`` of the shell at offset radius ``r`` from the plate axis."""
    if i == 0:
        return (0.0, -r)
    if 1 <= i <= 6:
        a = math.radians(TAIL[i - 1])
        return (1.0 + r * math.cos(a), r * math.sin(a))
    if i == 7:
        return (1.0, r)
    a = math.radians(NOSE[i - 8])
    return (r * math.cos(a), r * math.sin(a))


def seg_curve(i, r):
    """The ``curve`` declaration for side ``i`` of a shell, or None when the
    side is a straight flat (an offset of a straight line is a straight line,
    and a chord IS that line)."""
    if i == 0 or i == 7:
        return None
    if 1 <= i <= 6:
        return {"kind": "arc", "centre": [1.0, 0.0], "r": r, "sweep": "ccw"}
    return {"kind": "arc", "centre": [0.0, 0.0], "r": r, "sweep": "ccw"}


BOX = [(XA, -YF), (XB, -YF), (XB2, -YF), (XO, -YF), (XO, 0.0), (XO, YF),
       (XB2, YF), (XB, YF), (XA, YF), (XA2, YF), (XI, YF), (XI, 0.0),
       (XI, -YF), (XA2, -YF)]


def body_segs():
    """The plate itself, as fourteen polyline segments."""
    r = PLATE_H
    segs = []
    for i in range(14):
        a, b = station(i, r), station((i + 1) % 14, r)
        if i == 0 or i == 7:
            n = (FLAT_NODES - 1) * FACET_MULT
            segs.append([(a[0] + (b[0] - a[0]) * k / n,
                          a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)])
        else:
            n = (ARC_NODES - 1) * FACET_MULT
            if 1 <= i <= 6:
                c, d0, d1 = (1.0, 0.0), TAIL[i - 1], TAIL[i]
            else:
                c, d0, d1 = (0.0, 0.0), NOSE[i - 8], NOSE[i - 7]
            segs.append(mblib.arc_pts(c, r, d0, d1, n))
    return segs


def build():
    global GROWTH
    GROWTH = growth()
    ds, outer_ds = shell_radii()
    body = mblib.write_geom("plate_body", body_segs(), ["wall"] * 14)

    t = mblib.Topo()
    radii = [PLATE_H] + [PLATE_H + d for d in ds]

    # corners: the body's fourteen, then each shell's fourteen, then the box's
    for i in range(14):
        t.onbody("b%02d" % i, body, i, 0.0, station(i, PLATE_H))
    for k, r in enumerate(radii[1:], start=1):
        for i in range(14):
            t.free("s%d_%02d" % (k, i), station(i, r))
    for i in range(14):
        t.free("x%02d" % i, BOX[i])

    def ring(k, i):
        return "b%02d" % i if k == 0 else "s%d_%02d" % (k, i)

    # the fourteen sides of every shell
    for i in range(14):
        n = FLAT_NODES if i in (0, 7) else ARC_NODES
        # The two flats cluster at BOTH ends: fig6-2 and fig6-3 both show the
        # chordwise cells bunched at the leading and trailing edges, which is
        # where the boundary layer starts and where it leaves the plate.
        sp = ({"ds_start": FLAT_DS, "ds_end": FLAT_DS} if i in (0, 7) else None)
        t.edge("w%02d" % i, "b%02d" % i, "b%02d" % ((i + 1) % 14), "wall",
               count=n, binding={"geom": body, "seg": i}, spacing=sp)
        for k in range(1, len(radii)):
            # THE SAME clustering on every shell's flat. A count propagates
            # across a block, a SPACING LAW does not, so a clustered wall
            # facing a uniform shell tilts every radial line between them.
            # Measured on this declaration by deleting this argument and the
            # box edges' below: worst wall first cell 531.17% off and mean
            # non-orthogonality 13.621 deg, against 6.99% and 5.990 with it.
            t.edge("c%d_%02d" % (k, i), ring(k, i), ring(k, (i + 1) % 14),
                   "interface", curve=seg_curve(i, radii[k]), spacing=sp)
        bl = math.hypot(BOX[(i + 1) % 14][0] - BOX[i][0],
                        BOX[(i + 1) % 14][1] - BOX[i][1])
        t.edge("f%02d" % i, "x%02d" % i, "x%02d" % ((i + 1) % 14), "wall",
               spacing=(None if sp is None else
                        {"ds_start": FLAT_DS * bl, "ds_end": FLAT_DS * bl}))

    # the radials: one wrapping equivalence class per shell, one seed each
    for k in range(1, len(radii)):
        sp = ({"wall_ends": "start"} if k == 1
              else {"ds_start": WALL_DS * GROWTH ** sum(SHELL_N[:k - 1])})
        for i in range(14):
            t.edge("r%d_%02d" % (k, i), ring(k - 1, i), ring(k, i), "interface",
                   count=(SHELL_N[k - 1] + 1 if i == 0 else None), spacing=sp)
    for i in range(14):
        t.edge("r%d_%02d" % (len(radii), i), ring(len(radii) - 1, i), "x%02d" % i,
               "interface", count=(OUTER_N + 1 if i == 0 else None))
    # NO ds_start on the outer shell. The inner shell's last cell is
    # 0.0699 and the rays are 0.98 to 1.45 long, so 20 intervals are
    # already that coarse: asking for it produced the "a tanh law cannot
    # cluster COARSER than uniform" warning on 8 of the 14 rays and moved
    # nothing. The size step across that seam is measured in the note.

    # the blocks: shell k sector i
    for k in range(1, len(radii) + 1):
        inner = (lambda i, k=k: ring(k - 1, i))
        outer = ((lambda i, k=k: ring(k, i)) if k < len(radii)
                 else (lambda i: "x%02d" % i))
        for i in range(14):
            j = (i + 1) % 14
            t.block("k%d_%02d" % (k, i), [inner(i), inner(j), outer(j), outer(i)])

    t.write("plate.json", header="""
TARGET: entry 17 (Allampalli 2010), Figures 6.1, 6.2 and 6.3 -- the flat plate.

WRITTEN BY docs/research/allampalli-2010-reproductions/make_plate.py.
Do not hand-edit: the plate's .meta sidecar is written by the same run and
every b* corner is an arc-length position on it.

Fourteen sides per shell, four shells, 56 blocks. Every shell outward of the
plate needs NO geometry file: the offset of a flat is a flat (a straight chord
IS it) and the offset of a circular end is a concentric arc, declared with
'curve' so its nodes sit on the exact circle rather than on a stored polyline.
""")

    confs = mblib.write_pair(
        "plate", "plate.json",
        ["GEOM_FILE %s/%s" % (REL, body)],
        WALL_DS,
        extra=["",
               "# ZERO SWEEPS. The nose is a circle of radius 0.005 and the",
               "# first cell off it is 0.001, so the wall's radius of",
               "# curvature is five first-cells and the smoother's control",
               "# functions cannot hold that height. Measured on THIS",
               "# declaration, worst wall first cell against sweeps:",
               "#   0 -> 6.99%   5 -> 31.45%   10 -> 41.32%   20 -> 60.61%",
               "#   40 -> 90.71%",
               "# 20 is the shipped default. At 40 sweeps 28 cells FOLD,",
               "# against none at any lower count. Non-orthogonality barely",
               "# moves either way over that range: max 50.948 -> 56.067 deg",
               "# at 20, mean 5.990 -> 6.097.",
               "MB_SMOOTH_ITERS 0"],
        title="TARGET: entry 17, Figures 6.1-6.3 -- flow over a flat plate.")
    print("plate: %s" % t.stats())
    print("  growth %.5f, shells at d = %s, last inner cell %.5f"
          % (GROWTH, ", ".join("%.4f" % d for d in ds), outer_ds))
    return confs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    confs = build()
    ok = True
    if a.run:
        for c in confs:
            ok = mblib.summarise(mblib.run(c), os.path.basename(c)) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
