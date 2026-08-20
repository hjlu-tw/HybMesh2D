#!/usr/bin/env python3
"""Regression test: per-group BC types reach the exported mesh's .bnd, per EDGE.

Guards two related fixes for the "custom-domain boundaries all come out wall" bug:

1. A per-segment .meta tag is a grouping LABEL only; the physical BC type is
   chosen per group in the GUI (GROUP_BC lines). The downstream solver (getPGrid)
   name-guesses the .bnd patch name, so an unresolved label ("g0", any CAD label)
   defaults to a no-slip wall. HybMesh2D must resolve label -> BC type via
   GROUP_BC and write the TYPE as the .bnd patch name.

2. A .bnd BC is a per-EDGE quantity. A boundary edge belongs to the segment of
   its starting point; the edge that ends at a segment junction must still take
   that segment's BC (it used to fall back to the wall default because its two
   endpoint nodes carried different segment tags). So a domain with NO wall side
   must produce NO "wall" edges.

Runs the real HybMesh2D binary on a tiny square internal-flow domain whose four
sides carry distinct group labels + GROUP_BC types.

Run:  python3 tools/PreProcessor/tests/test_group_bc_resolution.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import os
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

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def _write_square(dat_path):
    """A 10x10 square, 10 points per side, each side its own group label g0..g3;
    the junction vertices (first point of each side) are flagged as corners."""
    n = 10
    corners = [(-5, -5), (5, -5), (5, 5), (-5, 5)]
    pts, segids = [], []
    for i in range(4):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % 4]
        for k in range(n):
            t = k / n
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
            segids.append(i + 1)
    with open(dat_path, "w") as f:
        f.write("\n".join(f"{x} {y}" for x, y in pts) + "\n")
    meta = ["HYBMESH_META 3", f"COUNT {len(pts)}", "NPIECES 0", "NSEGMENTS 4"]
    for s, lab in ((1, "g0"), (2, "g1"), (3, "g2"), (4, "g3")):
        meta.append(f"{s} {lab} line 1")
    meta.append(f"POINTS {len(pts)}")
    meta += [f"{s} {1 if i % n == 0 else 0}" for i, s in enumerate(segids)]
    with open(dat_path + ".meta", "w") as f:
        f.write("\n".join(meta) + "\n")


def _run(tmp, group_bc_lines):
    dat = os.path.join(tmp, "sq.dat")
    out = os.path.join(tmp, "sq_out")
    _write_square(dat)
    conf = os.path.join(tmp, "sq.conf")
    with open(conf, "w") as f:
        f.write(
            "SURFACE_MESH_SIZE 0.8\nBL_INITIAL_THICKNESS 0.05\nBL_GROWTH_RATE 1.2\n"
            "BL_LAYERS 2\nEXPORT_VTK 0\nEXPORT_STARCD 1\nBC_GEOM wall\n"
            f"OUTPUT_FILENAME {out}\n" + group_bc_lines + f"DOMAIN_FILE {dat} bl\n"
        )
    env = _mesher_env()
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=env,
                       capture_output=True, text=True, timeout=120)
    # The mesher's own words when it did not produce a mesh. Without this the
    # only symptom is "patch names: []", which is what a wrong BC resolution
    # and a mesher that never started look like from here — and they are not
    # remotely the same problem. Measured: a whole CI round-trip was spent
    # discovering that [] meant `error while loading shared libraries:
    # libgmsh.so.4.15` and exit 127.
    if p.returncode != 0:
        tail = (p.stdout + p.stderr).strip().splitlines()[-4:]
        print(f"  mesher exited {p.returncode}: " + " | ".join(tail))
    bnd = out + ".bnd"
    names = set()
    if os.path.exists(bnd):
        with open(bnd) as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 8:
                    names.add(parts[7])
    return bnd, names


def main():
    if not os.path.exists(_BIN):
        print(f"SKIP HybMesh2D not built ({_BIN})")
        return 0

    # (1) label -> BC-type resolution + raw labels must NOT leak into the .bnd.
    tmp = tempfile.mkdtemp(prefix="hybmesh_groupbc_")
    bnd, names = _run(tmp, "GROUP_BC g0 inlet\nGROUP_BC g1 wall\n"
                           "GROUP_BC g2 outlet\nGROUP_BC g3 SYMP\n")
    check("mesh produced a .bnd", os.path.exists(bnd))
    print("  .bnd patch names:", sorted(names))
    for t in ("inlet", "outlet", "SYMP", "wall"):
        check(f"resolved BC type '{t}' present in .bnd", t in names)
    for label in ("g0", "g1", "g2", "g3"):
        check(f"raw group label '{label}' NOT in .bnd", label not in names)

    # (2) per-EDGE tagging: with NO wall side, NO edge may fall back to wall
    #     (guards the segment-junction corner-edge fix).
    tmp2 = tempfile.mkdtemp(prefix="hybmesh_groupbc_nowall_")
    _bnd2, names2 = _run(tmp2, "GROUP_BC g0 inlet\nGROUP_BC g1 outlet\n"
                               "GROUP_BC g2 free\nGROUP_BC g3 SYMP\n")
    print("  no-wall-side .bnd patch names:", sorted(names2))
    for t in ("inlet", "outlet", "free", "SYMP"):
        check(f"'{t}' present with no wall side", t in names2)
    check("no spurious 'wall' edges at segment junctions", "wall" not in names2)

    print()
    print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
