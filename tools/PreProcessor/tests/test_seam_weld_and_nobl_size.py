#!/usr/bin/env python3
"""Regression test: a resampled closed outline must mesh in every geometry role.

Reported symptom: one resampled .dat worked as a refinement SEED but, set as BL /
no-BL / DOMAIN, either raised an error or hung with no output. Three independent
defects, all exercised here against the real HybMesh2D binary.

1. Seam sliver (error + hang).
   Resampling walks each segment independently, so the wrap-around — the last
   segment's end back onto the first segment's start — could land a hair apart
   (measured: 3.8e-5 against a 0.05 point spacing). ``loadGeometry`` only welded
   a seam below a FIXED 1e-6, so that hair survived as an edge ~1000x shorter
   than its neighbours and the outline SELF-INTERSECTED there. Downstream:
     * internal flow (DOMAIN_FILE ... bl) -> "Self-intersection detected in the
       final front", exit 5, only a partial mesh;
     * no-BL (either role) -> Gmsh spinning indefinitely on the crossing.
   The closure tolerance is now relative to the local point spacing, and the
   weld is reported rather than silent.

2. No-BL auto surface size (hang).
   With AUTO_SURFACE_SIZE on and no boundary layer to measure, the surface size
   fell through to BL_INITIAL_THICKNESS — a first-cell height, typically 100-1000x
   below the point spacing. Gmsh was then asked to resolve the whole boundary at
   ~1e-4 and appeared to hang. It now measures the surface's own spacing (and the
   custom domain outline's, when the outline is the only boundary).

3. Partial-export path mangling.
   The "_er" debug suffix was spliced at ``find_last_of('.')`` without the
   directory guard the neighbouring stripExt already had, so an output path under
   a dotted directory (~/.claude/..., any versioned dir) had the suffix injected
   into the DIRECTORY name and the export failed to open.

Run:  python3 tools/PreProcessor/tests/test_seam_weld_and_nobl_size.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import math
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_LIB = os.path.join(_REPO, "build")

# Point spacing of the synthetic outline below, and the seam gap left open.
SPACING = 0.5
SEAM_GAP = 5.0e-4          # ~0.1% of the spacing: invisible, but fatal before the fix

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def _seam_crossing(pts):
    """True if the closing edge crosses the first edge (what the sliver caused)."""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    p1, p2 = pts[0], pts[1]
    p3, p4 = pts[-2], pts[-1]
    d1, d2 = cross(p3, p4, p1), cross(p3, p4, p2)
    d3, d4 = cross(p1, p2, p3), cross(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _write_outline(dat_path):
    """A 10x10 square walked CCW at SPACING, whose last point misses the start by
    SEAM_GAP *across* the first edge — the exact defect a per-segment resampler
    leaves behind. Returns the point list."""
    corners = [(-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)]
    pts = []
    for i in range(4):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % 4]
        n = int(round(math.hypot(bx - ax, by - ay) / SPACING))
        for k in range(n):
            t = k / n
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    # Close it *badly*: a hair past the start and below the bottom edge (y = -5),
    # so the closing edge crosses the first edge instead of just touching it.
    off = SEAM_GAP / math.sqrt(2.0)
    pts.append((-5.0 + off, -5.0 - off))
    with open(dat_path, "w") as f:
        f.write("\n".join(f"{x:.10f} {y:.10f}" for x, y in pts) + "\n")
    return pts


def _run(tmp, geom_line, out_name="out", extra="", timeout=180):
    """Run HybMesh2D; returns (exit code or None on timeout, stdout+stderr, out path)."""
    out = os.path.join(tmp, out_name)
    conf = os.path.join(tmp, "case.conf")
    with open(conf, "w") as f:
        f.write(
            "DOMAIN_X_MIN -20\nDOMAIN_X_MAX 20\nDOMAIN_Y_MIN -20\nDOMAIN_Y_MAX 20\n"
            "AUTO_SURFACE_SIZE 1\nSURFACE_MESH_SIZE 0.5\n"
            "FARFIELD_MESH_SIZE 2\nFARFIELD_GROWTH_RATE 0.2\n"
            # Deliberately 1000x below the point spacing: this is the value the
            # no-BL path used to adopt as the SURFACE size.
            "BL_INITIAL_THICKNESS 0.0005\nBL_GROWTH_RATE 1.2\nBL_LAYERS 3\n"
            "BL_TRANSITION_LAYERS 2\nEXPORT_VTK 1\nEXPORT_STARCD 0\n"
            f"{extra}OUTPUT_FILENAME {out}\n{geom_line}\n"
        )
    env = dict(os.environ, DYLD_LIBRARY_PATH=_LIB, LD_LIBRARY_PATH=_LIB)
    try:
        p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=env,
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr, out
    except subprocess.TimeoutExpired:
        return None, f"<timed out after {timeout}s>", out


def _surface_size(log):
    """(reported line, parsed size) for the resolved surface mesh size."""
    for line in log.splitlines():
        if "Final Surface Mesh Size" in line:
            try:
                return line.strip(), float(line.rsplit(":", 1)[1])
            except ValueError:
                return line.strip(), None
    return "", None


def main():
    if not os.path.exists(_BIN):
        print(f"SKIP HybMesh2D not built ({_BIN})")
        return 0

    tmp = tempfile.mkdtemp(prefix="hybmesh_seam_")
    dat = os.path.join(tmp, "outline.dat")
    pts = _write_outline(dat)

    # The fixture must actually be broken, or the rest proves nothing.
    gap = math.dist(pts[0], pts[-1])
    check(f"fixture seam is open by {gap:.2e} (<< spacing {SPACING})",
          0 < gap < 0.01 * SPACING)
    check("fixture outline self-intersects at the seam", _seam_crossing(pts))

    # --- 1. internal flow: the BL used to self-intersect on the sliver ---------
    rc, log, out = _run(tmp, f"DOMAIN_FILE {dat} bl", "dom_bl")
    check("DOMAIN_FILE ... bl exits 0 (was: self-intersection, exit 5)", rc == 0)
    check("no self-intersection reported", "Self-intersection" not in log)
    check("the welded seam is reported, not silent", "is not exactly closed" in log)
    check("a mesh was written", os.path.exists(out + ".vtk"))

    # --- 2. no-BL surface size: the point spacing, never BL_INITIAL_THICKNESS --
    for role, line, expect in (
        ("GEOM_FILE ... nobl", f"GEOM_FILE {dat} nobl", "no-BL surface spacing"),
        ("DOMAIN_FILE ... nobl", f"DOMAIN_FILE {dat} nobl", "domain outline spacing"),
    ):
        rc, log, out = _run(tmp, line, "nobl_" + expect.split()[0])
        shown, size = _surface_size(log)
        check(f"{role} completes (was: Gmsh hang)", rc == 0)
        check(f"{role} sizes the surface from {expect} (got: {shown})",
              expect in shown)
        check(f"{role} surface size tracks the point spacing, not "
              f"BL_INITIAL_THICKNESS (got {size})",
              size is not None and 0.5 * SPACING <= size <= 2.0 * SPACING)

    # --- 3. partial export into a DOTTED directory ----------------------------
    dotted = os.path.join(tmp, ".hidden", "v1.2")
    os.makedirs(dotted, exist_ok=True)
    # A BL far thicker than the domain fails validation, forcing the "_er" path.
    rc, log, out = _run(tmp, f"DOMAIN_FILE {dat} bl", os.path.join(dotted, "partial"),
                        extra="BL_INITIAL_THICKNESS 2\nBL_LAYERS 20\n")
    check("a failed BL still exports its partial mesh under a dotted directory",
          os.path.exists(out + "_er.vtk"))
    check("the '_er' suffix did not land in the directory name",
          "Could not open file" not in log)

    print()
    print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
