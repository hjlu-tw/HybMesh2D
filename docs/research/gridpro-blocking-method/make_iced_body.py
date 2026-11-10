#!/usr/bin/env python3
"""A NACA 0012 with a GLAZE-ICE DOUBLE HORN at the leading edge.

A RESEARCH HARNESS beside docs/research/nesting-blocks-at-a-complicated-leading-edge.md,
which records GridPro's "Meshing Airfoil with Icing" video. That note's section 5
says GridPro's own ice geometry is NOT obtainable -- the download is dead and the
application page names no section -- so this builds one rather than pretending to
have theirs. THE SHAPE HERE IS MINE. Nothing about it is claimed to match
GridPro's, and no figure of theirs was measured to produce it.

What IS taken from the literature, because the note's own sources carry it: a
glaze-ice accretion on an unswept section forms TWO horns, one above and one
below the stagnation point, rather than a single leading-edge cap. The horn
angles and heights below are round numbers chosen to make a leading edge that is
geometrically COMPLICATED -- two convex tips with a concave valley between them,
which is the feature the video's method exists to block around. They are not
measured from any source.

    python3 docs/research/gridpro-blocking-method/make_iced_body.py
"""

import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = "examples/geometries/naca0012_cgrid.dat"

# Parametrised by SIGNED SURFACE ARC LENGTH from the leading edge, positive on
# the upper surface. An angle about the leading edge was tried first and is
# wrong: the TRAILING edge also lies at angle 0 there, so the ice grew on the
# trailing edge too -- caught because the written file reached x = 1.0121.
HORN_S = 0.045         # where each horn sits, in chords of surface arc from the LE
HORN_H = 0.055         # horn height, in chords, along the local outward normal
HORN_W = 0.018         # arc-length half-width of one horn
REACH_S = 0.16         # beyond this arc length the ice is gone
REFINE = 6             # subdivisions per clean panel inside the iced band, so
                       # the horn tips are curves and not 6-point facets. The
                       # clean section carries only 47 of its 193 points inside
                       # |s| < 0.16 and 6 inside one horn -- measured, and
                       # visibly faceted before this was added.


def read(path):
    return [tuple(map(float, ln.split()))
            for ln in open(path, encoding="utf-8") if ln.strip()]


def bump(s):
    """Two horns plus the valley between them, by signed arc length from the LE."""
    if abs(s) > REACH_S:
        return 0.0
    h = 0.0
    for centre in (HORN_S, -HORN_S):
        d = (s - centre) / HORN_W
        if abs(d) < 3.5:
            h += HORN_H * math.exp(-d * d)
    taper = 0.5 * (1.0 + math.cos(math.pi * abs(s) / REACH_S))
    return (h + 0.010 * taper) * taper


def main():
    pts = read(os.path.join(ROOT, SRC))
    closed = pts[0] == pts[-1]
    body = pts[:-1] if closed else pts[:]
    i_le = min(range(len(body)), key=lambda k: body[k][0])
    le = body[i_le]
    # signed surface arc length from the leading edge, positive going UP the
    # upper surface. The polyline starts at the trailing edge and runs over the
    # upper surface first, so indices below i_le are upper.
    n = len(body)
    seg = [0.0] * n
    for k in range(1, n):
        a, b = body[k - 1], body[k]
        seg[k] = seg[k - 1] + math.hypot(b[0] - a[0], b[1] - a[1])
    arc = [seg[k] - seg[i_le] for k in range(n)]      # negative before the LE
    arc = [-v for v in arc]                            # upper surface positive
    # refine the clean polyline inside the iced band FIRST, so the horn is a
    # curve rather than a facet, then displace every point of the result
    fine, fine_arc = [], []
    for k in range(n):
        a0, a1 = arc[k], arc[(k + 1) % n]
        p0, p1 = body[k], body[(k + 1) % n]
        sub = REFINE if (abs(a0) < REACH_S or abs(a1) < REACH_S) else 1
        for j in range(sub):
            u = j / sub
            fine.append((p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u))
            fine_arc.append(a0 + (a1 - a0) * u)
    m_ = len(fine)
    out = []
    for k, p in enumerate(fine):
        a = fine_arc[k]
        # outward normal from the two neighbours, so it works on either surface
        q, r = fine[(k - 1) % m_], fine[(k + 1) % m_]
        tx, ty = r[0] - q[0], r[1] - q[1]
        m = math.hypot(tx, ty)
        nx, ny = ty / m, -tx / m
        h = bump(a)
        out.append((p[0] + nx * h, p[1] + ny * h))
    out.append(out[0])
    dst = os.path.join(HERE, "naca0012_iced.dat")
    with open(dst, "w", encoding="utf-8") as f:
        for x, y in out:
            f.write("%.12f %.12f\n" % (x, y))

    # The .meta sidecar, without which an `on_geometry` corner has nothing to
    # attach to -- the mesher refuses by name ("carries no per-point
    # source-segment data"). TWO segments split at the NOSE, which must be the
    # same point `read_body` splits at, and it splits at minimum x; on an iced
    # section that is the ice tip, not the clean leading edge. Column 2 flags a
    # segment boundary, as the clean section's own sidecar does at its points
    # 0, 96 and 192.
    i_nose = min(range(len(out)), key=lambda k: out[k][0])
    with open(dst + ".meta", "w", encoding="utf-8") as f:
        f.write("HYBMESH_META 2\nCOUNT %d\nNPIECES 0\nNSEGMENTS 2\n"
                "0 wall line\n1 wall line\nPOINTS %d\n" % (len(out), len(out)))
        for k in range(len(out)):
            seg = 0 if k < i_nose else 1
            if k == len(out) - 1:
                seg = 0
            f.write("%d %d\n" % (seg, 1 if k in (0, i_nose, len(out) - 1) else 0))
    xs = [p[0] for p in out]
    ys = [p[1] for p in out]
    print("wrote %s" % os.path.relpath(dst, ROOT))
    print("  %d points, x %.4f..%.4f, y %.4f..%.4f" % (len(out), min(xs), max(xs), min(ys), max(ys)))
    print("  leading edge was at x=%.4f; the iced nose now reaches x=%.4f" % (le[0], min(xs)))
    print("  max |y| %.4f against the clean section's 0.0600" % max(abs(v) for v in ys))
    print("  wrote the .meta sidecar too; the nose splits the two wall segments at index %d" % i_nose)


if __name__ == "__main__":
    main()
