#!/usr/bin/env python3
"""Capture / compare a golden mesh set, to prove a refactor moved no mesh.

Pure code motion must produce the SAME MESH. The test suite proves behaviour;
this proves nothing moved at all, which is the stronger claim for a refactor.

"The same mesh" cannot mean "the same bytes": the mesher is not reproducible to
the byte (see `sha` below for the measurement), so the comparison is
canonicalised by coordinates instead. Same points, same cells, whatever the
numbering.

  python3 tools/scripts/mesh_golden.py capture <dir>     # before the change
  python3 tools/scripts/mesh_golden.py compare <dir>     # after it

Covers all four BL/no-BL junction bins, a curved no-BL wall (the case whose
slide column drifts off the wall polyline), one closed body and a 3-body case.

It reuses the duct writers in tools/PreProcessor/tests/test_nobl_junction_acute.py
rather than copying them, so the geometries under test cannot drift apart.
"""
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TESTS = os.path.join(REPO, "tools/PreProcessor/tests")

spec = importlib.util.spec_from_file_location(
    "junc", os.path.join(TESTS, "test_nobl_junction_acute.py"))
junc = importlib.util.module_from_spec(spec)
# The test module runs its own suite at import; keep only the helpers by
# stopping at the first top-level call. Simplest: exec its source up to "def main"
src = open(spec.origin).read()
cut = src.index("\n# ==")if "\n# ==" in src else len(src)
_ns = {"__name__": "junc_helpers", "__file__": spec.origin}
exec(compile(src[:cut], spec.origin, "exec"), _ns)
write_duct = _ns["write_duct"]
write_curved_duct = _ns["write_curved_duct"]
run_duct = _ns["run"]
LIB = _ns["_LIB"]
BIN = _ns["_BIN"]


_TS = re.compile(r"\d{4}-\d{2}-\d{2}T[\d:]+Z")
_TSB = re.compile(rb"\d{4}-\d{2}-\d{2}T[\d:]+Z")


def sha(path):
    """Hash the mesh GEOMETRY, independent of node numbering.

    MEASURED (8 runs of the identical command on naca0012): the mesher produces
    2 distinct byte outputs. The difference is confined to the ORDER of a few
    far-field boundary nodes — the same coordinates, permuted, plus the cell
    indices that follow them. So a byte hash reports a false difference roughly
    a third of the time and cannot gate a refactor.

    The canonical form below is order-insensitive but content-exact: the multiset
    of point coordinates, and the multiset of cells expressed as their sorted
    COORDINATES rather than their indices. Two meshes match iff they have the
    same points and the same cells, whatever the numbering.
    """
    if path.endswith(".vtk"):
        return hashlib.sha256(_canon_vtk(path).encode()).hexdigest()
    if path.endswith((".vrt", ".cel", ".bnd")):
        return _canon_starcd(path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for line in f:
            h.update(_TSB.sub(b"<TS>", line))
    return h.hexdigest()


def _canon_vtk(path):
    lines = open(path).read().split("\n")
    pts, cells, i = [], [], 0
    while i < len(lines):
        w = lines[i].split()
        if w and w[0] == "POINTS":
            n = int(w[1])
            for j in range(i + 1, i + 1 + n):
                pts.append(tuple(lines[j].split()))
            i += n + 1
            continue
        if w and w[0] == "CELLS":
            n = int(w[1])
            for j in range(i + 1, i + 1 + n):
                v = lines[j].split()
                if not v:
                    continue
                ids = [int(x) for x in v[1:]]
                cells.append(tuple(sorted({pts[k] for k in ids})))
            i += n + 1
            continue
        i += 1
    return ("P\n" + "\n".join(sorted(map(str, pts)))
            + "\nC\n" + "\n".join(sorted(map(str, cells))))


def _canon_starcd(path):
    """Canonicalise a STAR-CD file by content, resolving ids through the .vrt.

    The .bnd is the one that matters (it carries the BCs), and a permuted node
    numbering changes every id in it while describing the same boundary.
    """
    stem = path[:-4]
    coord = {}
    if os.path.exists(stem + ".vrt"):
        for ln in open(stem + ".vrt"):
            w = ln.split()
            if len(w) >= 4:
                coord[w[0]] = (w[1], w[2], w[3])
    rows = []
    for ln in open(path):
        w = ln.split()
        if not w:
            continue
        if path.endswith(".vrt"):
            rows.append(tuple(w[1:]))                  # drop the id itself
        elif path.endswith(".cel"):
            # "id v1 v2 v3 v4 a b" (7 fields) — v4 repeats v3 for a triangle, so
            # slicing the ids as w[1:-3] dropped it and made two distinct cells
            # canonicalise the same.
            # A TRIANGLE is written as a quad with one vertex repeated, and
            # WHICH one is repeated varies run to run (the cell's rotation), so
            # {P,Q,R,R} and {Q,R,P,P} are the same triangle. Dedupe before
            # sorting or the canonical form is still order-dependent.
            ids = {str(coord.get(x, x)) for x in w[1:5]}
            rows.append(tuple(sorted(ids)) + tuple(w[5:]))
        else:                                          # .bnd: ids + patch + name
            # A TRIANGLE is written as a quad with one vertex repeated, and
            # WHICH one is repeated varies run to run (the cell's rotation), so
            # {P,Q,R,R} and {Q,R,P,P} are the same triangle. Dedupe before
            # sorting or the canonical form is still order-dependent.
            ids = {str(coord.get(x, x)) for x in w[1:5]}
            rows.append(tuple(sorted(ids)) + tuple(w[5:]))
    return hashlib.sha256("\n".join(sorted(map(str, rows))).encode()).hexdigest()


def norm_log(txt):
    """Drop the run-to-run varying parts (paths, timings, temp dirs)."""
    txt = _TS.sub("<TS>", txt)
    txt = re.sub(r"/[^\s]*/(golden|hybmesh)_\w+", "/TMP", txt)
    txt = re.sub(r"/var/folders/\S+", "/TMP", txt)
    txt = re.sub(r"\d+(\.\d+)? ?(s|ms|sec|seconds)\b", "<T>", txt)
    return txt


def cases(tmp):
    """(name, vtk_path, log) for each covered path."""
    out = []
    # the four junction bins + the curved-wall slide-BC path
    for name, theta in (("duct_t85", 85.0), ("duct_t90", 90.0),
                        ("duct_t120", 120.0), ("duct_t150", 150.0)):
        dat = os.path.join(tmp, name + ".dat")
        write_duct(dat, theta)
        rc, log, stem = run_duct(tmp, dat, name, starcd=True)
        out.append((name, stem + ".vtk", log, rc))
    dat = os.path.join(tmp, "curved.dat")
    write_curved_duct(dat)
    rc, log, stem = run_duct(tmp, dat, "curved", starcd=True)
    out.append(("curved_duct", stem + ".vtk", log, rc))

    # closed bodies: convex fans, concave blend, transition layers, multi-front
    for name, geoms in (
            ("naca0012", ["examples/geometries/naca0012.dat"]),
            ("multi_30p30n", ["examples/geometries/30p30n_jaxa_main.dat",
                              "examples/geometries/30p30n_jaxa_slat.dat",
                              "examples/geometries/30p30n_jaxa_flap.dat"]),
    ):
        stem = os.path.join(tmp, name)
        cmd = [BIN, "-conf", os.path.join(REPO, "config/Background_para.dat")]
        for g in geoms:
            cmd += ["-geom", os.path.join(REPO, g)]
        cmd += ["-out_name", stem]
        env = dict(os.environ, DYLD_LIBRARY_PATH=LIB, LD_LIBRARY_PATH=LIB)
        p = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True,
                           text=True, timeout=900)
        out.append((name, stem + ".vtk", p.stdout + p.stderr, p.returncode))
    return out


def main():
    mode, dest = sys.argv[1], sys.argv[2]
    tmp = tempfile.mkdtemp(prefix="golden_")
    rows = cases(tmp)
    if mode == "capture":
        os.makedirs(dest, exist_ok=True)
        for name, vtk, log, rc in rows:
            ok = os.path.exists(vtk)
            print(f"{name:16s} rc={rc} vtk={'yes' if ok else 'MISSING'}")
            if ok:
                shutil.copy(vtk, os.path.join(dest, name + ".vtk"))
                for ext in (".vrt", ".cel", ".bnd"):
                    s = vtk[:-4] + ext
                    if os.path.exists(s):
                        shutil.copy(s, os.path.join(dest, name + ext))
            open(os.path.join(dest, name + ".log"), "w").write(norm_log(log))
        print(f"\ncaptured -> {dest}")
    else:
        bad = []
        for name, vtk, log, rc in rows:
            for ext in (".vtk", ".vrt", ".cel", ".bnd"):
                ref = os.path.join(dest, name + ext)
                cur = vtk[:-4] + ext
                if not os.path.exists(ref):
                    continue
                if not os.path.exists(cur):
                    bad.append(f"{name}{ext}: MISSING now")
                elif sha(ref) != sha(cur):
                    bad.append(f"{name}{ext}: CONTENT CHANGED")
                else:
                    print(f"  identical  {name}{ext}")
            refl = os.path.join(dest, name + ".log")
            if os.path.exists(refl):
                if open(refl).read() != norm_log(log):
                    bad.append(f"{name}.log: banner/warnings differ")
                else:
                    print(f"  identical  {name}.log")
        print()
        if bad:
            print(f"{len(bad)} DIFFERENCE(S):")
            for b in bad:
                print("   ! " + b)
            sys.exit(1)
        print("GOLDEN MATCH: same points and same cells in every artifact.")
    shutil.rmtree(tmp, ignore_errors=True)


main()
