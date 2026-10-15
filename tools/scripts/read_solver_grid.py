# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""Read the solver's own `.grid`: a flat binary, deduced from its own sizes.

Usage:
    read_solver_grid.py <file.grid> [...]        print what each one holds
    read_solver_grid.py <file.grid> --vtk <out>  write it as legacy VTK

The companion `.bc` is ASCII (first line names the `.bc.def`, then one line per
boundary face: `face_index segment_no`), and `.bc.def` maps a segment number to
a bc flag, optionally with a parameter. Measured on three cases in
`docs/research/solver-grid-reference-cases.md`.

    int32  version (1), ncell, nvert, nbface
    ncell  x (int32 k, int32 node[k])        -- k is 3 on both cases here
    nvert  x (double x, double y)
    nbface x (int32 a, b, c)

Nothing documented this; the layout is the only one whose arithmetic closes on
both files to the byte (cells 16 B each, vertices 16 B, boundary faces 12 B).
"""
import array, struct, sys


def read(path):
    d = open(path, "rb").read()
    ver, ncell, nvert, nbf = struct.unpack_from("<4i", d, 0)
    off = 16
    k = struct.unpack_from("<i", d, off)[0]
    cells = array.array("i")
    cells.frombytes(d[off:off + ncell * 4 * (1 + k)])
    off += ncell * 4 * (1 + k)
    xy = array.array("d")
    xy.frombytes(d[off:off + nvert * 16])
    off += nvert * 16
    bf = array.array("i")
    bf.frombytes(d[off:off + nbf * 12])
    off += nbf * 12
    assert off == len(d), "layout does not close: %d of %d" % (off, len(d))
    conn = [tuple(cells[i * 4 + 1:i * 4 + 4]) for i in range(ncell)]
    pts = [(xy[2 * i], xy[2 * i + 1]) for i in range(nvert)]
    faces = [tuple(bf[3 * i:3 * i + 3]) for i in range(nbf)]
    return pts, conn, faces


def write_vtk(path, pts, conn, out):
    with open(out, "w") as f:
        f.write("# vtk DataFile Version 3.0\n%s\nASCII\nDATASET UNSTRUCTURED_GRID\n"
                % path)
        f.write("POINTS %d float\n" % len(pts))
        for x, y in pts:
            f.write("%.9g %.9g 0\n" % (x, y))
        f.write("CELLS %d %d\n" % (len(conn), 4 * len(conn)))
        for t in conn:
            f.write("3 %d %d %d\n" % t)
        f.write("CELL_TYPES %d\n" % len(conn))
        for _ in conn:
            f.write("5\n")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--vtk" in sys.argv:
        out = sys.argv[sys.argv.index("--vtk") + 1]
        args = [a for a in args if a != out]
        pts, conn, _ = read(args[0])
        write_vtk(args[0], pts, conn, out)
        print("wrote %s: %d cells" % (out, len(conn)))
        raise SystemExit(0)
    for p in args:
        pts, conn, faces = read(p)
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        lo = min(min(c) for c in conn)
        hi = max(max(c) for c in conn)
        print("%s: %d cells, %d vertices, %d boundary faces" % (p, len(conn), len(pts), len(faces)))
        print("   node ids %d..%d (%d-based)" % (lo, hi, 0 if lo == 0 else 1))
        print("   extent x %.5f..%.5f  y %.5f..%.5f" % (min(xs), max(xs), min(ys), max(ys)))
        print("   first face record %s" % (faces[0],))

