#!/usr/bin/env python3
"""Read the GRIDS out of a Fidelity Pointwise `.pw` project, without Pointwise.

Why this exists: a reference mesh handed over as a `.pw` is otherwise opaque on
a machine with no Pointwise licence, and "how many times does the string
'Structured' appear" is NOT a measurement of a mesh's topology -- that mistake
is recorded in `docs/research/jaxa-30p30n-reference-mesh.md`.

THE FORMAT, as far as this needs it. The file opens with an ASCII banner, then
`PWI0` and a stream of tagged records:

    01 01 <id:8> <len:8> <bytes>     an interned string (the id is referenced later)
    02 02 <type> <payload>           a scalar: 0x09 double, 0x08 int64, 0x01 byte
    02 02 <0x80|type> <ndims:8> <dims:8*ndims> <data>    an array
    03 03 <id:8>                     a key, naming the value that follows
    04 04 <id:8>                     an object

Everything below is read off the ARRAYS alone, which is enough: a grid domain
stores its points as a double array of dims (3, I, J) when it is structured and
(3, N) when it is not, and its cells as an int32 array of 3-tuples. Each domain
is stored TWICE -- once in XYZ and once in parametric UV -- and the parametric
copy is recognised by every Y being exactly 0.

Usage:
    read_pointwise.py <file.pw>                    list every domain
    read_pointwise.py <file.pw> --dump <dir>       write each domain as .dat
"""
import array
import os
import struct
import sys

ELEM_SIZE = {0x01: 1, 0x05: 4, 0x06: 4, 0x08: 8, 0x09: 8}


def arrays(path, min_bytes=2000):
    """Every typed array in the file: (offset, elem_type, dims, data_offset, bytes)."""
    data = open(path, "rb").read()
    n = len(data)
    out = []
    i = 0
    while True:
        i = data.find(b"\x02\x02", i)
        if i < 0 or i + 3 >= n:
            break
        tag = data[i + 2]
        if tag & 0x80 and (tag & 0x7F) in ELEM_SIZE:
            et = tag & 0x7F
            try:
                nd = struct.unpack_from("<q", data, i + 3)[0]
                if 1 <= nd <= 3:
                    dims = struct.unpack_from("<" + "q" * nd, data, i + 11)
                    if all(1 <= x < 10 ** 8 for x in dims):
                        count = 1
                        for x in dims:
                            count *= x
                        size = count * ELEM_SIZE[et]
                        if size >= min_bytes and i + 11 + 8 * nd + size <= n:
                            out.append((i, et, dims, i + 11 + 8 * nd, size))
            except (struct.error, IndexError):
                pass
        i += 1
    return data, sorted(out)


def grids(path):
    """(data, arrays, structured, unstructured) with the parametric copies dropped."""
    data, arrs = arrays(path)
    structured, unstructured = [], []
    for off_rec, et, dims, off, size in arrs:
        if et != 0x09 or dims[0] != 3:
            continue
        xyz = array.array("d")
        xyz.frombytes(data[off:off + size])
        xs, ys = xyz[0::3], xyz[1::3]
        if max(ys) == min(ys) == 0.0:
            continue                       # the parametric (UV) copy
        if len(dims) == 3:
            structured.append((off_rec, dims[1], dims[2], xs, ys))
        else:
            unstructured.append((off_rec, dims[1], xs, ys))
    return data, arrs, structured, unstructured


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    data, arrs, st, un = grids(path)
    print("%s" % os.path.basename(path))
    print("structured domains: %d, %d points, %d cells"
          % (len(st), sum(i * j for _, i, j, _, _ in st),
             sum((i - 1) * (j - 1) for _, i, j, _, _ in st)))
    for off, I, J, xs, ys in st:
        print("  %9d  %4d x %-4d  x %9.4f..%9.4f  y %9.4f..%9.4f"
              % (off, I, J, min(xs), max(xs), min(ys), max(ys)))
    sizes = {i * j for _, i, j, _, _ in st}
    print("unstructured domains: %d  (those whose point count equals a structured "
          "domain's I*J are that domain's triangulated copy)" % len(un))
    for off, N, xs, ys in un:
        if N < 5000:
            continue
        print("  %9d  %7d points%s  x %8.3f..%8.3f  y %8.3f..%8.3f"
              % (off, N, "  [copy]" if N in sizes else "        ",
                 min(xs), max(xs), min(ys), max(ys)))
    if "--dump" in argv:
        out = argv[argv.index("--dump") + 1]
        os.makedirs(out, exist_ok=True)
        for off, I, J, xs, ys in st:
            with open(os.path.join(out, "struct_%d_%dx%d.dat" % (off, I, J)), "w") as f:
                for k in range(I * J):
                    f.write("%.9f %.9f\n" % (xs[k], ys[k]))
        print("dumped %d structured domains to %s" % (len(st), out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
