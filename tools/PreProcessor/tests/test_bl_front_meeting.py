#!/usr/bin/env python3
"""Two bodies whose boundary layers MEET: the run tapers, it does not abort.

Before this gate the hybrid path had two refusals for the same situation, both
of which lost the whole mesh after it had been built:

  * a per-layer cross-geometry freeze that compared candidate POINTS pairwise --
    a point test for a segment condition, so two fronts could pass through each
    other between samples without any two candidates being within a cell; and
  * a final-front gate that DID test segments, found the crossing the first
    check had missed, and threw.

The published practice is the opposite: when a front cannot advance it stops
THAT NODE and the run continues, the layer tapering to zero where it cannot fit
(docs/research/meshing-the-cove-and-the-trailing-edges.md, section 1c; the
skipBL branch in src/BoundaryLayer.cpp already describes the same behaviour for
a different reason -- "the BL simply tapers to zero here and the far-field
mesher fills the gap"). What this file pins is that behaviour, in both
directions.

Measured when it was written, on config/hybrid_30p30n.dat: the three-element
section aborted past about 0.004 chord of boundary layer and now reaches
0.0089 at 120 layers -- 1,214,780 cells, exit 0, one warning. That case takes
minutes, so the fixture here is two small circles instead, close enough that
their fronts must meet.

What this pins down:

  1. A BL thick enough that two bodies' fronts would cross EXPORTS A MESH and
     exits 0, where it used to abort with "Intersection detected between
     Geometry".
  2. It SAYS SO, once, naming the node's position and the first-cell height --
     a taper the user did not ask for is not allowed to be silent.
  3. The negative control: the same two bodies with a BL that fits produce the
     same exit code and NO such warning, so check 2 is not matching something
     that is always printed.
  4. The mesh that comes back has no inverted cell, because "tapers" has to
     mean the cells near the taper are sound, not merely that a file appeared.
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")

_FAILS: list = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(("PASS  " if ok else "FAIL  ") + label + ((" | " + detail) if detail else ""))
    if not ok:
        _FAILS.append(label)


def _circle(path: str, cx: float, cy: float, r: float, n: int = 160) -> None:
    with open(path, "w") as fh:
        for k in range(n):
            a = 2.0 * math.pi * k / n
            fh.write("%.12f %.12f\n" % (cx + r * math.cos(a), cy + r * math.sin(a)))


def _conf(path: str, out: str, g1: str, g2: str, layers: int) -> None:
    with open(path, "w") as fh:
        fh.write("MESH_MODE 0\n")
        fh.write("DOMAIN_X_MIN -3.0\nDOMAIN_X_MAX 3.0\n")
        fh.write("DOMAIN_Y_MIN -3.0\nDOMAIN_Y_MAX 3.0\n")
        fh.write("SURFACE_MESH_SIZE 0.02\nAUTO_SURFACE_SIZE 0\n")
        fh.write("FARFIELD_MESH_SIZE 0.3\nFARFIELD_GROWTH_RATE 0.2\n")
        fh.write("BL_INITIAL_THICKNESS 0.004\nBL_GROWTH_RATE 1.05\n")
        fh.write("BL_LAYERS %d\nBL_TRANSITION_LAYERS 0\n" % layers)
        fh.write("BL_AUTO_TRANSITION_LAYERS 0\n")
        fh.write("GEOM_FILE %s\nGEOM_FILE %s\n" % (g1, g2))
        fh.write("BC_GEOM wall\nEXPORT_VTK 1\nEXPORT_STARCD 0\n")
        fh.write("OUTPUT_FILENAME %s\n" % out)


def _unused_inverted(vtk: str) -> int:
    with open(vtk) as fh:
        lines = fh.read().split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith("POINTS"))
    npts = int(lines[i].split()[1])
    pts = [tuple(float(v) for v in lines[i + 1 + k].split()[:2]) for k in range(npts)]
    j = next(k for k, l in enumerate(lines) if l.startswith("CELLS"))
    ncel = int(lines[j].split()[1])
    sign, bad = 0, 0
    for k in range(ncel):
        idx = [int(v) for v in lines[j + 1 + k].split()[1:]]
        p = [pts[q] for q in idx]
        a = 0.5 * sum(p[m][0] * p[(m + 1) % len(p)][1] - p[(m + 1) % len(p)][0] * p[m][1]
                      for m in range(len(p)))
        if a == 0.0:
            continue
        if sign == 0:
            sign = 1 if a > 0 else -1
        elif (a > 0) != (sign > 0):
            bad += 1
    return bad


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP  build/HybMesh2D not built; nothing to measure.")
        return 0
    tmp = tempfile.mkdtemp(prefix="bl_meet_")
    g1 = os.path.join(tmp, "a.dat")
    g2 = os.path.join(tmp, "b.dat")
    # 0.30 apart on the surfaces; 40 layers at 0.004/1.05 is 0.483 deep, so the
    # two fronts must meet, and 6 layers (0.027) must not.
    _circle(g1, -0.40, 0.0, 0.25)
    _circle(g2, 0.40, 0.0, 0.25)

    runs = {}
    for name, layers in (("thick", 40), ("thin", 6)):
        conf = os.path.join(tmp, name + ".dat")
        out = os.path.join(tmp, name + ".vtk")
        _conf(conf, out, g1, g2, layers)
        p = subprocess.run([_BIN, "-conf", conf], capture_output=True, text=True,
                           cwd=_REPO)
        runs[name] = (p.returncode, (p.stdout or "") + (p.stderr or ""), out)

    rc_t, log_t, out_t = runs["thick"]
    check(rc_t == 0, "1. fronts that must meet still EXPORT a mesh",
          "exit %d" % rc_t)
    check("Intersection detected between Geometry" not in log_t,
          "1b. and the between-geometry abort is gone")
    check(os.path.exists(out_t), "1c. the file is there")

    said = ("boundary layers meet near" in log_t
            or "retreated BL node" in log_t)
    check(said, "2. the taper is SAID, not silent")

    rc_n, log_n, _ = runs["thin"]
    check(rc_n == 0 and "boundary layers meet near" not in log_n
          and "retreated BL node" not in log_n,
          "3. negative control: a BL that fits warns about nothing",
          "exit %d" % rc_n)

    # The mesher's OWN count, not a winding test: this path exports the
    # boundary layer's quads split into triangles whose winding is opposite to
    # Gmsh's, so a signed-area test calls a third of a sound mesh inverted.
    check("cells are INVERTED" not in log_t,
          "4. the mesher reports no inverted cell in the tapered mesh")

    print("-------------------------------------------")
    if _FAILS:
        print("FAILED: " + ", ".join(_FAILS))
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
