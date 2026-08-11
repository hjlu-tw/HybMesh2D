#!/usr/bin/env python3
"""Regression test: STL3d must trace a flat 2D profile across its FULL x extent.

Reported symptom: exporting a CAD profile to a flat 2D STL and running the IB
stage from the GUI died with `[STL3d] exited with code -11` (SIGSEGV) right after
"ray tracing", on an STL that had loaded and reported its bounding box fine.

The crash is a mismatch between two different x extents inside `STLobject`:

  * `xloc_db` — the candidate-lookup index — is keyed by element **centre** x;
  * `xmin`/`xmax` — the ray culling window — come from the **vertices**, and must,
    because a centroid sits strictly inside the surface and a centre-based box
    clips whole regions off a coarse or fan-shaped tessellation.

So for any ray in the strip between the largest centre x and `xmax`,
`xloc_db.lower_bound(x)` has nothing to return: it yields `end()`, and
`trace_ray` dereferenced that (`->second->second`). On the reported profile the
strip was 5.856 → 6.070, i.e. the last ~30 of 128 x-slices, and the run died on
the first of them. A fan/ear-clipped triangulation of a 2D outline is the worst
case, because every centroid is dragged toward the fan apex.

The shape below reproduces that deliberately: a regular polygon fanned from its
LEFTMOST vertex, which leaves the rightmost third of the x extent free of any
centroid. The test asserts, for both the all-element search (`y`) and the
close-x-range search (`n`):

  1. the run exits 0 — not a signal — over a domain wider than the STL;
  2. the far-x strip past the last centroid is actually MARKED, so the fix is a
     real trace and not a silent clip (which is what a centre-based box did, and
     the reason the vertex box exists);
  3. phi agrees with point-in-polygon containment away from the boundary, and
  4. the two search modes agree node for node.

Compiles `stl3d.cpp` itself, so it runs in CI (which does not build STL3d) and
can never pass against a stale binary. Skips cleanly if no C++ compiler is found.

Run:  python3 tools/PreProcessor/tests/test_stl3d_flat_profile_trace.py
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_SRC = os.path.join(_REPO, "solver", "preprocess", "STL3d", "src")
_CPP = os.path.join(_SRC, "stl3d.cpp")

# A 24-gon, off the origin so a sign slip cannot pass by accident.
CX, CY, R, NSIDES = 5.5, 1.8, 0.6, 24
# Domain deliberately wider than the STL, so out-of-range slices are exercised too.
DOM = (CX - 1.5 * R, CX + 1.5 * R, CY - 1.5 * R, CY + 1.5 * R, 0.0, 0.0)
NX, NY, NZ = 64, 64, 2

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def polygon():
    """Regular polygon vertices, vertex 0 at the LEFTMOST point (the fan apex)."""
    return [(CX + R * math.cos(math.pi + 2 * math.pi * k / NSIDES),
             CY + R * math.sin(math.pi + 2 * math.pi * k / NSIDES))
            for k in range(NSIDES)]


def fan_triangles(poly):
    """Fan-triangulate from vertex 0 — the tessellation shape that broke."""
    return [(poly[0], poly[k], poly[k + 1]) for k in range(1, len(poly) - 1)]


def write_stl(path, tris):
    with open(path, "w") as f:
        f.write("solid test_flat_profile\n")
        for t in tris:
            f.write("facet normal 0.000000e+00 0.000000e+00 -1.000000e+00\n")
            f.write("  outer loop\n")
            for (x, y) in t:
                f.write(f"    vertex {x:.6e} {y:.6e} 0.000000e+00\n")
            f.write("  endloop\n")
            f.write("endfacet\n")
        f.write("endsolid test_flat_profile\n")


def read_phi(path):
    """{(i, j, k) index-free} -> list of (x, y, z, phi) from the Tecplot point file."""
    out = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) != 4:
                continue
            try:
                out.append(tuple(float(p) for p in parts))
            except ValueError:
                pass
    return out


def inside_polygon(px, py, poly):
    """Signed even-odd containment test (the polygon is convex, but keep it general)."""
    n = len(poly)
    hit = False
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xc = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < xc:
                hit = not hit
    return hit


def dist_to_boundary(px, py, poly):
    """Distance from (px, py) to the polygon outline — used to skip boundary nodes."""
    best = float("inf")
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
        best = min(best, math.hypot(px - (x1 + t * dx), py - (y1 + t * dy)))
    return best


def compile_stl3d(workdir):
    """Build stl3d.cpp with whatever C++ compiler is around; None if we can't."""
    cxx = os.environ.get("CXX") or shutil.which("c++") or shutil.which("g++")
    if not cxx:
        return None
    exe = os.path.join(workdir, "stl3d")
    cmd = [cxx, "-std=c++17", "-O1", "-D_INCLUDE_TEMPLATE_IMPLEMENTATION",
           f"-I{_SRC}", _CPP, "-o", exe, "-lm"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("compile failed:\n" + proc.stderr[-2000:])
        return None
    return exe


def run_case(exe, workdir, stl_name, case, all_search):
    stdin = "{}\n{}\n{} {} {} {} {} {}\n{} {} {}\n{}\n".format(
        stl_name, case, *DOM, NX, NY, NZ, all_search)
    proc = subprocess.run([exe], input=stdin, cwd=workdir, capture_output=True,
                          text=True, timeout=300)
    return proc


def main():
    if not os.path.exists(_CPP):
        print(f"SKIP: {_CPP} not found")
        return 0

    poly = polygon()
    tris = fan_triangles(poly)
    max_vertex_x = max(v[0] for v in poly)
    max_centre_x = max(sum(v[0] for v in t) / 3.0 for t in tris)
    dx_grid = (DOM[1] - DOM[0]) / (NX - 1)

    # If the fan did not leave a centroid-free strip, the test is vacuous.
    strip = max_vertex_x - max_centre_x
    check(f"fan tessellation leaves a centroid-free strip of {strip:.3f} "
          f"({strip / dx_grid:.0f} x-slices wide)", strip > 3 * dx_grid)

    with tempfile.TemporaryDirectory() as wd:
        exe = compile_stl3d(wd)
        if exe is None:
            print("SKIP: no C++ compiler available to build stl3d.cpp")
            return 0
        write_stl(os.path.join(wd, "flat.stl"), tris)

        phis = {}
        for mode, case in (("y", "allsearch"), ("n", "closex")):
            proc = run_case(exe, wd, "flat.stl", case, mode)
            check(f"all-search '{mode}': exits 0, not a signal "
                  f"(got {proc.returncode}; the bug gave -11)",
                  proc.returncode == 0)
            if proc.returncode != 0:
                print("    stdout tail: " + proc.stdout[-300:].replace("\n", " | "))
                continue
            check(f"all-search '{mode}': flat STL detected (column-fill path)",
                  "flat (planar-in-z) STL" in proc.stdout)
            out = os.path.join(wd, f"{case}_phi_tec.dat")
            if not os.path.exists(out):
                check(f"all-search '{mode}': wrote {case}_phi_tec.dat", False)
                continue
            phis[mode] = read_phi(out)

        for mode, rows in phis.items():
            solid = [r for r in rows if r[3] == 1.0]
            check(f"all-search '{mode}': marked something solid", bool(solid))
            if not solid:
                continue
            # The strip past the last centroid must be marked, not silently clipped.
            far = [r for r in solid if r[0] > max_centre_x]
            check(f"all-search '{mode}': the strip past the last centroid "
                  f"(x > {max_centre_x:.3f}) is marked — {len(far)} node(s)", bool(far))

            tol = 1.5 * dx_grid          # skip nodes straddling the outline
            wrong_in = wrong_out = 0
            for x, y, _z, phi in rows:
                if dist_to_boundary(x, y, poly) < tol:
                    continue
                ref = inside_polygon(x, y, poly)
                if ref and phi != 1.0:
                    wrong_in += 1
                elif not ref and phi != 0.0:
                    wrong_out += 1
            check(f"all-search '{mode}': phi matches containment away from the "
                  f"outline ({wrong_in} missed inside, {wrong_out} false solid)",
                  wrong_in == 0 and wrong_out == 0)

        if len(phis) == 2:
            a, b = phis["y"], phis["n"]
            same = len(a) == len(b) and all(p[3] == q[3] for p, q in zip(a, b))
            check("both search modes produce the same phi field", same)

    print()
    if failures:
        print(f"RESULT: {len(failures)} FAILED")
        for f in failures:
            print("  - " + f)
        return 1
    print("RESULT: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
