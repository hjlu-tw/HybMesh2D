#!/usr/bin/env python3
"""How a BLOCK PARTITION spends its lines, measured from a finished mesh.

Section 8c read off GridPro's wireframe by eye that "their extra blocks stay near
the body; mine reach the far field by construction", and section 15 is that
sentence measured. The quantity is:

    N(r) = how many block-partition lines cross a circle of radius r about a
           chosen centre.

A TERMINATING (nested) blocking FALLS from left to right -- many lines at the
feature, few a block-width out. A blocking whose counts propagate is FLAT. That
shape is scale-free, which is what makes it the right instrument when the thing
being compared against is a video frame with no measurable chord (section 8b).

IT READS A MESH, NOT A TOPOLOGY, and that is deliberate: the block field in the
VTK (issue #106) is the only published record of which cells came from which
block, so a pair of quads straddling a block boundary is identifiable without
re-parsing the declaration. Run the case with ``MB_SPLIT_QUADS 0`` so the file
carries quads; the figure is independent of the split either way.

    ./run.sh -conf <case>.dat -out_name /tmp/m        # with MB_SPLIT_QUADS 0
    python3 docs/research/gridpro-blocking-method/measure_block_partition.py \
        /tmp/m.vtk --centre 0.5 0 --rays

``--rays`` additionally walks outward from the centre and reports only the lines
within 35 degrees of PERPENDICULAR to each ray -- a RING, i.e. a layer -- so that
"how many rows are stacked off the body" is answered without counting the radials
a ray also clips. Getting that wrong is how the first reading of section 15 said
"one row" about a picture whose outer rows its own crop had cut off.
"""

import argparse
import numpy as np


def read_vtk(path):
    """points, cells, per-cell block id. Legacy ASCII VTK with a `block` field."""
    toks = open(path, encoding="utf-8").read().split("\n")
    pts, cells, blocks, i = [], [], [], 0
    while i < len(toks):
        t = toks[i].split()
        if t[:1] == ["POINTS"]:
            n = int(t[1]); v = []; i += 1
            while len(v) < 3 * n:
                v += [float(x) for x in toks[i].split()]; i += 1
            pts = np.array(v).reshape(n, 3)[:, :2]; continue
        if t[:1] == ["CELLS"]:
            n = int(t[1]); i += 1
            for _ in range(n):
                r = [int(x) for x in toks[i].split()]; cells.append(r[1:]); i += 1
            continue
        if t[:1] == ["SCALARS"] and len(t) > 1 and t[1] == "block":
            i += 2                      # SCALARS line + LOOKUP_TABLE
            while len(blocks) < len(cells):
                blocks += [int(x) for x in toks[i].split()]; i += 1
            continue
        i += 1
    if not blocks:
        raise SystemExit("REFUSED: %s carries no `block` cell field. Re-run the "
                         "case in MESH_MODE 1; the field is written only when "
                         "EVERY cell has one." % path)
    return pts, cells, blocks


def seam_edges(pts, cells, blocks):
    """The node pairs that two quads from DIFFERENT blocks share.

    The same walk `measureMbQuality` does for the size jump (#183): key each
    quad edge by its node-id pair, keep the first owner's block, and compare when
    the second owner arrives. No tolerance anywhere, for welding's own reason.
    """
    first, out = {}, []
    for ids, blk in zip(cells, blocks):
        if len(ids) != 4:
            continue
        for k in range(4):
            key = tuple(sorted((ids[k], ids[(k + 1) % 4])))
            if key not in first:
                first[key] = blk
            elif first[key] != blk:
                out.append(key)
    return np.array(out, dtype=int) if out else np.zeros((0, 2), int)


def crossings(pts, seam, centre, r):
    a = np.linalg.norm(pts[seam[:, 0]] - centre, axis=1)
    b = np.linalg.norm(pts[seam[:, 1]] - centre, axis=1)
    return int(((np.minimum(a, b) <= r) & (np.maximum(a, b) >= r)).sum())


def rings_along(pts, seam, origin, theta, tol_deg=35.0):
    """Distances at which a RING (not a radial) crosses one ray from `origin`."""
    d = np.array([np.cos(theta), np.sin(theta)]); n = np.array([-d[1], d[0]])
    P1, P2 = pts[seam[:, 0]], pts[seam[:, 1]]
    a, b = (P1 - origin) @ n, (P2 - origin) @ n
    hit = (a * b) < 0
    if not hit.any():
        return np.zeros(0)
    t = a[hit] / (a[hit] - b[hit])
    X = P1[hit] + (P2[hit] - P1[hit]) * t[:, None]
    r = (X - origin) @ d
    e = P2[hit] - P1[hit]; e = e / np.linalg.norm(e, axis=1)[:, None]
    ang = np.degrees(np.arccos(np.clip(np.abs(e @ d), 0, 1)))
    keep = (r > 1e-9) & (ang > 90.0 - tol_deg)
    return np.sort(r[keep])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vtk")
    ap.add_argument("--centre", nargs=2, type=float, default=[0.5, 0.0])
    ap.add_argument("--radii", nargs="*", type=float,
                    default=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0])
    ap.add_argument("--rays", action="store_true",
                    help="also report RINGS along rays at 180/165/150/135/120 deg")
    ap.add_argument("--ray-origin", nargs=2, type=float, default=None,
                    help="default: --centre")
    args = ap.parse_args()

    pts, cells, blocks = read_vtk(args.vtk)
    seam = seam_edges(pts, cells, blocks)
    c = np.array(args.centre, float)
    print("%d blocks, %d cells, %d block-boundary edges"
          % (len(set(blocks)), len(cells), len(seam)))
    print("\nN(r) -- lines crossing a circle about (%g, %g):" % (c[0], c[1]))
    for r in args.radii:
        print("    r = %-7g %4d" % (r, crossings(pts, seam, c, r)))
    print("\nA terminating blocking FALLS here. A propagating one is FLAT.")

    if args.rays:
        o = np.array(args.ray_origin if args.ray_origin else args.centre, float)
        print("\nRINGS (layers) along rays from (%g, %g), within 35 deg of "
              "perpendicular:" % (o[0], o[1]))
        for deg in (180, 165, 150, 135, 120):
            r = rings_along(pts, seam, o, np.radians(deg))
            near = r[r < 0.30]
            print("    %3d deg   %d within 0.30   %s"
                  % (deg, len(near), np.array2string(near, precision=3)))


if __name__ == "__main__":
    main()
