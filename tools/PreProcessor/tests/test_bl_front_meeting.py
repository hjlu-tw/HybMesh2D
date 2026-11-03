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
  5. ENABLE_COLLISION_DETECTION still switches the whole cross-geometry phase
     off. The per-layer segment test added with this behaviour was written
     OUTSIDE that guard, so the key stopped meaning what three documents say it
     means; 5b keeps 5 from passing on a run that never got that far.
  6. The SEGMENT test does something no point test does. Checks 1-4 do not
     reach it -- 6c measures that, rather than asserting it -- because two
     circles meet tangentially and a point test always wins there. An end
     meeting a flank meets transversally and only the segment test catches it:
     delete that block and check 6 goes to exit 5 while 1-4 stay green. The
     shipped three-element case agrees: point_freezes=5, segment_freezes=56.
  7. A front that folds onto ITSELF tapers too (#179), with no second geometry
     in the run. This is decided on the FINAL ring rather than per layer, and
     7d is the control that says a layer which fits is left alone -- a per-layer
     self test was built first and cost `curved_duct` 26% of its cells by
     pre-empting machinery that was already resolving those folds.
  8. The same taper covers two rings that cross, which is the gate 178b2c1 left
     as a backstop -- reached in practice at BL_LAYERS 180 on the shipped
     three-element case. 8c pins that this half obeys the collision-detection
     key and the self half does not.
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


def _sliver(path: str, x0: float, y0: float, x1: float, y1: float,
            half: float, n: int = 24) -> None:
    """A thin closed body along (x0,y0)-(x1,y1), sampled coarsely on purpose.

    Coarse is the point: the segment test only earns its keep where the node
    spacing is larger than a layer's thickness, so that two fronts can pass
    through each other between samples.
    """
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    pts = [(x0 + ux * length * k / n + nx * half, y0 + uy * length * k / n + ny * half)
           for k in range(n + 1)]
    pts += [(x0 + ux * length * k / n - nx * half, y0 + uy * length * k / n - ny * half)
            for k in range(n, -1, -1)]
    with open(path, "w") as fh:
        for x, y in pts:
            fh.write("%.12f %.12f\n" % (x, y))


def _u_shape(path: str, n: int = 18) -> None:
    """A U, as ONE body. The layer grows outward, so the inside of the U is
    where the two arms' fronts converge -- a front folding onto ITSELF, with no
    second geometry anywhere in the run."""
    w, h, t = 0.5, 1.0, 0.18
    outer = [(-w, 0.0), (-w, h), (-w + t, h), (-w + t, t),
             (w - t, t), (w - t, h), (w, h), (w, 0.0)]
    pts = []
    for a, b in zip(outer, outer[1:] + outer[:1]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        m = max(2, int(length * n))
        pts += [(a[0] + (b[0] - a[0]) * k / m, a[1] + (b[1] - a[1]) * k / m)
                for k in range(m)]
    with open(path, "w") as fh:
        for x, y in pts:
            fh.write("%.12f %.12f\n" % (x, y))


def _conf_one(path: str, out: str, g: str, layers: int) -> None:
    """The same configuration as `_conf`, with a single geometry."""
    _conf(path, out, g, g, layers)
    with open(path) as fh:
        text = fh.read()
    first = text.index("GEOM_FILE")
    second = text.index("GEOM_FILE", first + 1)
    end = text.index("\n", second) + 1
    with open(path, "w") as fh:
        fh.write(text[:second] + text[end:])


def _conf(path: str, out: str, g1: str, g2: str, layers: int,
          collision: int = 1) -> None:
    with open(path, "w") as fh:
        fh.write("MESH_MODE 0\n")
        fh.write("DOMAIN_X_MIN -3.0\nDOMAIN_X_MAX 3.0\n")
        fh.write("DOMAIN_Y_MIN -3.0\nDOMAIN_Y_MAX 3.0\n")
        fh.write("SURFACE_MESH_SIZE 0.02\nAUTO_SURFACE_SIZE 0\n")
        fh.write("FARFIELD_MESH_SIZE 0.3\nFARFIELD_GROWTH_RATE 0.2\n")
        fh.write("BL_INITIAL_THICKNESS 0.004\nBL_GROWTH_RATE 1.05\n")
        fh.write("BL_LAYERS %d\nBL_TRANSITION_LAYERS 0\n" % layers)
        fh.write("BL_AUTO_TRANSITION_LAYERS 0\n")
        fh.write("ENABLE_COLLISION_DETECTION %d\n" % collision)
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
    for name, layers, collision in (("thick", 40, 1), ("thin", 6, 1),
                                    ("off", 40, 0)):
        conf = os.path.join(tmp, name + ".dat")
        out = os.path.join(tmp, name + ".vtk")
        _conf(conf, out, g1, g2, layers, collision)
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

    # ENABLE_COLLISION_DETECTION gates the WHOLE cross-geometry phase, B2
    # included. When this was written B2 sat outside that guard, so a user who
    # had switched collision detection off still got frozen nodes and this
    # warning; measured on two circles 0.1 apart, the warning fired with the
    # key at 0. Both halves are asserted on purpose: the first is the knob
    # being honoured, and the second is what stops the first passing on a run
    # that died before it got there -- "no warning" is true of a segfault too.
    rc_o, log_o, _ = runs["off"]
    check("boundary layers meet near" not in log_o
          and "retreated BL node" not in log_o,
          "5. the knob is honoured: nothing freezes with collision detection OFF",
          "exit %d" % rc_o)
    check("Intersection detected between Geometry" in log_o,
          "5b. and that run really reached the final-front gate, so 5 is not "
          "vacuous")

    # 6. A scenario the POINT tests cannot catch, which is the whole reason the
    # segment test exists. Two circles meeting head-on touch TANGENTIALLY, so
    # the region where the fronts are within one cell of each other is long and
    # some pair of nodes always lands in it -- measured on the fixture above:
    # point_freezes=27, segment_freezes=0 at n=160, and still 0 at n=8, 10, 12,
    # 16, 24 and 40. Checks 1-4 therefore pass with the whole segment block
    # deleted, which is how it shipped unmeasured.
    #
    # An END pointing at a FLANK crosses TRANSVERSALLY instead: the fronts meet
    # at an angle, so they are within a cell of each other over a span of about
    # one cell, and at this sampling no two nodes land in it. Measured: with
    # the segment test, exit 0 and point_freezes=2 / segment_freezes=32; with
    # the block deleted, exit 5, "Intersection detected between Geometry", and
    # point_freezes=24 / segment_freezes=0.
    #
    # This is not a fixture-only effect. config/hybrid_30p30n.dat at
    # BL_LAYERS 120 reports point_freezes=5 segment_freezes=56: on the shipped
    # case the segment test does almost all of the work, and the one warning
    # that case prints is the one the point test would never have raised.
    ga = os.path.join(tmp, "end.dat")
    gb = os.path.join(tmp, "flank.dat")
    _sliver(ga, -1.0, 0.0, -0.20, 0.0, 0.03)
    _sliver(gb, 0.10, -1.0, 0.10, 1.0, 0.03)
    conf_x = os.path.join(tmp, "cross.dat")
    out_x = os.path.join(tmp, "cross.vtk")
    _conf(conf_x, out_x, ga, gb, 40)
    p_x = subprocess.run([_BIN, "-conf", conf_x], capture_output=True, text=True,
                         cwd=_REPO)
    log_x = (p_x.stdout or "") + (p_x.stderr or "")
    check(p_x.returncode == 0
          and "Intersection detected between Geometry" not in log_x,
          "6. an END meeting a FLANK transversally also exports, not aborts",
          "exit %d" % p_x.returncode)

    marks = [l for l in log_x.split("\n") if l.startswith("HYBMESH_BL_TAPER")]
    seg = pnt = -1
    if marks:
        f = dict(kv.split("=") for kv in marks[0].split()[1:])
        seg, pnt = int(f.get("segment_freezes", -1)), int(f.get("point_freezes", -1))
    check(seg > 0, "6b. and the SEGMENT test is what did it",
          "segment_freezes=%d point_freezes=%d" % (seg, pnt))

    marks_t = [l for l in log_t.split("\n") if l.startswith("HYBMESH_BL_TAPER")]
    seg_t = -1
    if marks_t:
        f = dict(kv.split("=") for kv in marks_t[0].split()[1:])
        seg_t = int(f.get("segment_freezes", -1))
    check(seg_t == 0,
          "6c. negative control: the two-circle fixture never reaches it, so "
          "checks 1-4 cannot see the segment test at all",
          "segment_freezes=%d" % seg_t)

    # 7. ONE body, folding onto ITSELF (#179). Until this landed, 178b2c1's
    # taper covered two geometries and a single geometry whose own front crossed
    # still threw away a mesh it had already built -- measured on
    # config/hybrid_30p30n.dat at BL_LAYERS 160: exit 5, the slat's front
    # crossing itself at (-0.0280, -0.0950). It now exits 0 with 2,017,055 cells.
    #
    # The U grows its layer OUTWARD, so the inside of the U is where its two
    # arms' fronts converge. There is no second geometry in the run at all, so
    # nothing the cross-geometry tests do can be what resolves it.
    gu = os.path.join(tmp, "u.dat")
    _u_shape(gu)
    runs_u = {}
    for name, layers in (("deep", 40), ("shallow", 5)):
        conf_u = os.path.join(tmp, "u_" + name + ".dat")
        out_u = os.path.join(tmp, "u_" + name + ".vtk")
        _conf_one(conf_u, out_u, gu, layers)
        pu = subprocess.run([_BIN, "-conf", conf_u], capture_output=True,
                            text=True, cwd=_REPO)
        runs_u[name] = (pu.returncode, (pu.stdout or "") + (pu.stderr or ""), out_u)

    rc_u, log_u, out_u = runs_u["deep"]
    check(rc_u == 0 and "Self-intersection detected in the final front" not in log_u,
          "7. one body whose own front folds EXPORTS a mesh, not an exit code",
          "exit %d" % rc_u)
    check(os.path.exists(out_u) and "cells are INVERTED" not in log_u,
          "7b. and that mesh is there with no inverted cell")

    marks_u = [l for l in log_u.split("\n") if l.startswith("HYBMESH_BL_RING_TAPER")]
    nodes_u = -1
    if marks_u:
        f = dict(kv.split("=") for kv in marks_u[0].split()[1:])
        nodes_u = int(f.get("nodes", -1))
    check(nodes_u > 0, "7c. and the SELF taper is what did it, said out loud",
          "nodes=%d" % nodes_u)

    rc_s, log_s, _ = runs_u["shallow"]
    check(rc_s == 0 and "HYBMESH_BL_RING_TAPER" not in log_s
          and "folds onto ITSELF" not in log_s,
          "7d. negative control: the same body with a layer that fits tapers "
          "nothing and says nothing", "exit %d" % rc_s)

    # 8. TWO rings crossing is the same defect and gets the same remedy. The
    # per-layer cross-geometry freeze (check 1) is not always enough: these two
    # slivers cross at 90 degrees and used to die on the final-front gate with
    # "Intersection detected between Geometry". Measured on the shipped case
    # too -- config/hybrid_30p30n.dat at BL_LAYERS 180 resolves its own folds
    # and then died here, which is what sent this half of the change in.
    #
    # 8c is the knob, and it is not a copy of 5b: 5 and 5b reach the gate by a
    # per-layer route, this one by the final-front taper. The SELF half (7) is
    # deliberately NOT under the key -- one body folding is not multi-geometry
    # collision -- and nothing but a check says which half is which.
    ga2 = os.path.join(tmp, "cross_a.dat")
    gb2 = os.path.join(tmp, "cross_b.dat")
    _sliver(ga2, -1.0, -1.0, 0.1, 0.1, 0.03)
    _sliver(gb2, -1.0, 1.2, 0.1, 0.1 + 0.30 * math.sqrt(2.0), 0.03)
    runs_x = {}
    for name, coll in (("on", 1), ("off", 0)):
        conf_c = os.path.join(tmp, "cross_" + name + ".dat")
        out_c = os.path.join(tmp, "cross_" + name + ".vtk")
        _conf(conf_c, out_c, ga2, gb2, 40, coll)
        pc = subprocess.run([_BIN, "-conf", conf_c], capture_output=True,
                            text=True, cwd=_REPO)
        runs_x[name] = (pc.returncode, (pc.stdout or "") + (pc.stderr or ""))

    rc_c, log_c = runs_x["on"]
    check(rc_c == 0 and "Intersection detected between Geometry" not in log_c,
          "8. two rings that cross taper as well, instead of ending the run",
          "exit %d" % rc_c)
    check("HYBMESH_BL_RING_TAPER" in log_c,
          "8b. and the FINAL-FRONT taper is what did it, not the per-layer freeze")

    rc_co, log_co = runs_x["off"]
    check("Intersection detected between Geometry" in log_co,
          "8c. and the CROSS half obeys ENABLE_COLLISION_DETECTION, while the "
          "self half (7) does not", "exit %d" % rc_co)

    print("-------------------------------------------")
    if _FAILS:
        print("FAILED: " + ", ".join(_FAILS))
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
