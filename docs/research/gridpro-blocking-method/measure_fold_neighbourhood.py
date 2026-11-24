"""Every INTERIOR irregular node of a QUAD mesh, with the shape of its neighbourhood.

    python3 docs/research/gridpro-blocking-method/measure_fold_neighbourhood.py <mesh.vtk>...

For each node it reports the worst angle subtended there, the area ratio between
the cells meeting there and their worst aspect ratio, grouped by valence: 3 is a
fold, 5 an apex. #194 uses it to ask whether a fold's own neighbourhood decides
whether the solve diverges, and §16o of
`docs/research/nesting-blocks-at-a-complicated-leading-edge.md` records that it
does not.

TWO things the caller must get right, both of which cost a measurement here:

- **Interior means every incident edge is shared by two cells.** A node on a
  block side has three edges and is perfectly regular; counting it as valence 3
  put the fold beside #194's divergence 370th of 400-odd instead of 9th of 12.
- **Measure the QUADS** (`MB_SPLIT_QUADS 0`). Splitting to triangles adds a
  diagonal at every node, so the valence this reads is the triangulation's and
  no node comes back irregular.
"""
import os, sys, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_block_partition import read_vtk


def irregular(path):
    pts, cells, blocks = read_vtk(path)
    use, at = {}, {}
    for ci, ids in enumerate(cells):
        n = len(ids)
        for k in range(n):
            e = tuple(sorted((ids[k], ids[(k + 1) % n])))
            use[e] = use.get(e, 0) + 1
            at.setdefault(ids[k], set()).add(ci)
    inc = {}
    for (i, j), c in use.items():
        for n in (i, j):
            a, b = inc.get(n, (0, 0))
            inc[n] = (a + 1, b + (c == 1))
    out = []
    for n, (deg, bnd) in inc.items():
        if bnd or deg == 4:
            continue                      # boundary node, or regular
        rows = []
        for ci in at[n]:
            P = pts[cells[ci]]
            k = list(cells[ci]).index(n)
            a = P[(k - 1) % len(P)] - P[k]
            b = P[(k + 1) % len(P)] - P[k]
            ang = math.degrees(math.atan2(abs(a[0]*b[1] - a[1]*b[0]), float(a @ b)))
            x, y = P[:, 0], P[:, 1]
            area = 0.5*abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
            e = [np.linalg.norm(P[(i + 1) % len(P)] - P[i]) for i in range(len(P))]
            rows.append((ang, area, max(e)/min(e)))
        ar = [r[1] for r in rows]
        out.append(dict(node=n, xy=tuple(pts[n]), deg=deg,
                        ang=max(r[0] for r in rows),
                        ratio=max(ar)/min(ar),
                        aspect=max(r[2] for r in rows)))
    return out


if __name__ == "__main__":
    for path in sys.argv[1:]:
        name = path.rsplit("/", 1)[-1].replace(".vtk", "")
        rows = irregular(path)
        print("%s: %d interior irregular nodes" % (name, len(rows)))
        for deg in sorted({r["deg"] for r in rows}):
            g = [r for r in rows if r["deg"] == deg]
            print("  valence %d x%-3d  angle %5.1f-%5.1f  area ratio %5.1f-%5.1f"
                  "  aspect %5.1f-%5.1f"
                  % (deg, len(g),
                     min(r["ang"] for r in g), max(r["ang"] for r in g),
                     min(r["ratio"] for r in g), max(r["ratio"] for r in g),
                     min(r["aspect"] for r in g), max(r["aspect"] for r in g)))
