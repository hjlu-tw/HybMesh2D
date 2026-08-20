#!/usr/bin/env python3
"""Regression test: the mesher must report how high the size field actually grows.

Reported symptom: FARFIELD_MESH_SIZE was swept over 0.5 / 1.0 / 2.0 on an
internal-flow case and every value produced a byte-identical mesh, with nothing
in the log saying why.

FARFIELD_MESH_SIZE is a Min() CAP on the size field, not a target. The field is
grown from the wall (FARFIELD_GROWTH_RATE) and/or inward from the domain bounding
box (FARFIELD_GROWTH_RATE_OUTER); in a domain that is small relative to the growth
rate the field tops out well below the cap, so the cap never enters the
computation and every value above the top-out point is equivalent. That is
invisible without a read-out, and the user's only recourse is trial and error.

So `generateFarFieldGmsh` now prints a `[ Mesh Size Field ]` block ending in an
INFO line that states whether the cap is reached, and if not, the value it must
go below to matter. The ceiling is computed by re-evaluating the 3.1/3.1b field
expressions at the generated mesh nodes -- NOT by measuring cell edge lengths,
which run ~15% long on stretched triangles and would report a dead cap as live.

What this pins down:
  * the reported ceiling predicts the mesh: two caps ABOVE it give an identical
    triangle count, and a cap BELOW it changes the count;
  * the "never reached" INFO fires exactly when the cap is above the ceiling;
  * a case whose cap IS reached reports it as active instead.

Run:  python3 tools/PreProcessor/tests/test_size_field_ceiling.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import math
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
# The gmsh loader path comes from the ONE resolver, never from
# <repo>/build, which has never held libgmsh. Why that matters,
# and what it cost in CI, is in tests/mesher_bin.py.
from mesher_bin import mesher_env as _mesher_env  # noqa: E402

DUCT_W, DUCT_H = 4.0, 3.0
SPACING = 0.1
failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def write_duct(path, grow=0):
    """A closed CCW rectangular duct discretised at ~SPACING.

    `grow` is the per-segment BL flag written into the .meta trailer. It has to
    match the DOMAIN_FILE role: the meta flag WINS, so a duct written with grow=0
    grows no layer even when the config says `bl`, and the "BL" run would silently
    be a second copy of the no-BL run.
    """
    verts = [(0.0, 0.0), (DUCT_W, 0.0), (DUCT_W, DUCT_H), (0.0, DUCT_H)]
    pts, seg, corner = [], [], []
    for j in range(4):
        ax, ay = verts[j]
        bx, by = verts[(j + 1) % 4]
        n = max(6, int(round(math.hypot(bx - ax, by - ay) / SPACING)))
        for m in range(n):
            t = m / n
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
            seg.append(j + 1)
            corner.append(1 if m == 0 else 0)
    with open(path, "w") as f:
        f.write("".join(f"{x:.10f} {y:.10f}\n" for x, y in pts))
        f.write(f"{pts[0][0]:.10f} {pts[0][1]:.10f}\n")
    with open(path + ".meta", "w") as f:
        f.write(f"HYBMESH_META 3\nCOUNT {len(pts)}\nNPIECES 0\nNSEGMENTS 4\n")
        for j in range(4):
            f.write(f"{j + 1} wall polyline {grow}\n")
        f.write(f"POINTS {len(pts)}\n")
        for i in range(len(pts)):
            f.write(f"{seg[i]} {corner[i]}\n")


def run(tmp, dat, name, far_size, role="nobl", timeout=300):
    """Run HybMesh2D at a given FARFIELD_MESH_SIZE; returns (rc, log)."""
    out = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".conf")
    with open(conf, "w") as f:
        f.write(
            f"DOMAIN_FILE {dat} {role}\n"
            "AUTO_SURFACE_SIZE 1\nSURFACE_MESH_SIZE 0.1\n"
            f"FARFIELD_MESH_SIZE {far_size}\nAUTO_FARFIELD_SIZE 0\n"
            "FARFIELD_GROWTH_RATE 0.1\nFARFIELD_BIDIRECTIONAL 1\n"
            "FARFIELD_GROWTH_RATE_OUTER 0.1\n"
            "BL_INITIAL_THICKNESS 0.01\nBL_GROWTH_RATE 1.2\nBL_LAYERS 5\n"
            "BL_TRANSITION_LAYERS 3\nBL_AUTO_TRANSITION_LAYERS 2\n"
            "BL_TRANSITION_GROWTH_RATE 1.2\nBL_TRANSITION_BUFFER 2\n"
            "GMSH_ALGORITHM 6\nGMSH_OPTIMIZE 1\n"
            "BL_CONVEX_METHOD 2\nBL_CONCAVE_METHOD 5\nBL_JUNCTION_METHOD 1\n"
            f"EXPORT_VTK 1\nEXPORT_STARCD 0\nOUTPUT_FILENAME {out}.vtk\n"
        )
    env = _mesher_env()
    try:
        p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=env,
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return None, f"<timed out after {timeout}s>"


def ceiling_of(log):
    """The reported uncapped size-field maximum, or None."""
    m = re.search(r"Growth reaches\s*:\s*([0-9.eE+-]+)", log)
    return float(m.group(1)) if m else None


def tri_count(log):
    m = re.search(r"\((\d+) far-field triangles\)", log)
    return int(m.group(1)) if m else None


def main():
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        dat = os.path.join(tmp, "duct.dat")
        write_duct(dat)

        # --- no-BL internal flow: the reported symptom -----------------------
        rc_hi, log_hi = run(tmp, dat, "hi", 5.0)
        check("no-BL duct meshes at cap 5.0", rc_hi == 0)
        if rc_hi != 0:
            print(log_hi[-2000:])
            return 1

        check("a [ Mesh Size Field ] block is printed",
              "[ Mesh Size Field ]" in log_hi)
        ceil_hi = ceiling_of(log_hi)
        check("the block reports the uncapped growth ceiling", ceil_hi is not None)
        check("an effective ceiling is reported", "Effective ceiling" in log_hi)
        if ceil_hi is None:
            return 1

        # The duct is 4 x 3 at spacing 0.1, so hEnd ~ 0.1, buffer = 2 x hEnd,
        # and the deepest interior point is 1.5 from the bounding box:
        #   0.1 + (1.5 - 0.2) x 0.1 = 0.23
        check(f"the ceiling matches the field algebra (~0.23, got {ceil_hi:.4f})",
              abs(ceil_hi - 0.23) < 0.02)
        check("a cap far above the ceiling is reported as never reached",
              "is never reached" in log_hi)
        check("the INFO names the value the cap must go below",
              re.search(r"Lower it below\s+[0-9.]+", log_hi) is not None)

        # The claim the read-out makes: above the ceiling, the cap does nothing.
        rc_hi2, log_hi2 = run(tmp, dat, "hi2", 2.0)
        check("no-BL duct meshes at cap 2.0", rc_hi2 == 0)
        n_hi, n_hi2 = tri_count(log_hi), tri_count(log_hi2)
        check("two caps above the ceiling give an identical mesh "
              f"({n_hi} vs {n_hi2} triangles)",
              n_hi is not None and n_hi == n_hi2)

        # ...and below it, the cap does bite.
        below = round(ceil_hi * 0.5, 4)
        rc_lo, log_lo = run(tmp, dat, "lo", below)
        check(f"no-BL duct meshes at cap {below}", rc_lo == 0)
        n_lo = tri_count(log_lo)
        check(f"a cap below the ceiling changes the mesh "
              f"({n_hi} -> {n_lo} triangles)",
              n_lo is not None and n_lo != n_hi)
        check("a cap below the ceiling is reported as active",
              "is active over" in log_lo)
        check("the never-reached INFO does NOT fire when the cap bites",
              "is never reached" not in log_lo)

        # --- BL case: the wall-distance field (3.1) must feed the ceiling too -
        # Self-calibrating: read the ceiling from a run whose cap cannot bind,
        # then re-run below it. Hardcoding a cap here would only re-assert what
        # the duct's dimensions happen to give.
        dat_bl = os.path.join(tmp, "duct_bl.dat")
        write_duct(dat_bl, grow=1)
        rc_bl, log_bl = run(tmp, dat_bl, "bl", 5.0, role="bl")
        check("BL duct meshes", rc_bl == 0)
        if rc_bl == 0:
            ceil_bl = ceiling_of(log_bl)
            check("the BL run also reports a ceiling", ceil_bl is not None)
            # Growth starts at the BL front here, so field 3.1 must be in play
            # and the advice must name its rate, not only the outer one.
            check("the BL run's advice names FARFIELD_GROWTH_RATE (field 3.1 active)",
                  "FARFIELD_GROWTH_RATE=" in log_bl)
            check("the BL run generated layers",
                  re.search(r"Generating [1-9]\d* boundary layers", log_bl) is not None)
            if ceil_bl is not None:
                below_bl = round(ceil_bl * 0.5, 4)
                rc_bl2, log_bl2 = run(tmp, dat_bl, "bl2", below_bl, role="bl")
                check(f"BL duct meshes at cap {below_bl}", rc_bl2 == 0)
                check("a BL-case cap below the ceiling is reported as active",
                      "is active over" in log_bl2)
                check("a BL-case cap below the ceiling changes the mesh "
                      f"({tri_count(log_bl)} -> {tri_count(log_bl2)} triangles)",
                      tri_count(log_bl2) != tri_count(log_bl))

    print("-------------------------------------------")
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print("  - " + f)
        return 1
    print("All size-field ceiling checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
