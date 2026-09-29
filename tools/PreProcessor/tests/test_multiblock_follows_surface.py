#!/usr/bin/env python3
"""An interior line that FOLLOWS a curve, end to end through the real binary (#151).

The DECISIONS are pinned next door in ``tests/cpp/test_multiblock.cpp`` check 58,
which links the pure layer alone and asserts on node positions, refusals and the
smoother's plan as data — including the one claim this file cannot make, that a
following edge's nodes equal a bound wall's BIT FOR BIT. What can only be checked
out here is that the chain CONNECTS: that a topology declaring a curved seam on
disk becomes one conforming grid on disk, with the seam ON the curve in the
exported file and no patch for it in the ``.bnd``.

THE FIXTURE IS CHECKED IN, and it is the smallest thing that says something the
five shipped documents cannot: ``examples/topology/curved_seam_blocks.json``, two
blocks stacked on one shared line, with ``examples/geometries/arc_seam.dat`` — a
40-facet circular arc from (0, 0) to (2, 0) bulging to (1, 0.5), so the curve sits
0.5 off the chord between the seam's two corners. That is not a refinement: with
no ``follows`` the two blocks meet along a straight line.

NO ``config/multiblock_*.dat`` SHIPS WITH IT, deliberately, and this gate writes
its own. The command-line demo of this capability is #153's two-ring O-grid; a
sixth shipped config here would trip ``test_multiblock_smooth_surface.py`` check
13 — which exists to stop a shipped config arriving un-gated — and would buy a
second demo of the same two blocks.

What this pins down:

  1. The checked-in fixture meshes (rc = 0) with zero inverted cells, and the run
     NAMES the seam as an interface following segment 0 of its geometry — the
     shared-edge report's new half, which is how a user sees that the seam they
     declared is the seam they got.
  2. The seam's 41 nodes lie ON the polyline, to 1e-7, and up to 0.5 off the chord
     between its two corners. The chord control is the same topology with the
     ``follows`` removed: there every seam node sits on y = 0, and the run says "a
     straight chord". Without that pair the first half is a description of a
     fixture rather than a measurement of a feature.
  3. The seam SURVIVES the default 20 Winslow sweeps. Measured before the freeze
     rule was extended: those sweeps pulled all 39 interior seam nodes off the arc,
     the worst by 4.961e-02 against a radius of 1.25 — a declared curve silently
     replaced by one nobody wrote down. The run now reports 0 movable shared nodes
     and the nodes are still on the polyline in the exported file.
  4. The grid is CONFORMING, on the exported files rather than argued: every
     interior edge of the triangulation belongs to exactly two cells, the boundary
     edge set is exactly the ``.bnd``, and it is one connected component.
  5. The following edge is NOT a boundary: no ``.bnd`` face lies on the curve, and
     no patch carries its segment's label ``seam`` — which is unmapped on purpose,
     so a condition that leaked would arrive under its own name rather than hiding
     inside ``wall``.
  6. The sample-rate advice reaches a following edge. 40 facets under 26 intervals
     is 1.538 facets to a node on a curve turning 106 deg, so a seam sampled at a
     rate its polyline cannot carry says so exactly as a bound wall does.
  7. Every refusal this ticket adds, end to end: ``follows`` on a wall naming
     ``binding``, ``binding`` on an interior line naming ``follows``, both keys at
     once naming both, and a following edge whose corner is not on the segment.
     All exit 8 with the machine-readable line, and all export NOTHING.

BLIND SPOTS, named:

  * Nothing here drives the SOLVER. This fixture is a synthetic two-block box with
    no flow question behind it; #153 is the ticket that owns an acceptance run, on
    a case that has one. Recorded because #26 shipped a change behind 85 green
    tests that pinned strings and never executed the solver.
  * The seam is measured against the ARC it was generated from, which is a circle
    this file recomputes. That is a check against the POLYLINE only because the
    polyline's vertices are on the circle by construction; a geometry whose facets
    were not would need the point-to-segment distance instead.

Run:  python3 tools/PreProcessor/tests/test_multiblock_follows_surface.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import json
import math
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_TOPO = os.path.join(_REPO, "examples", "topology", "curved_seam_blocks.json")
_GEOM = os.path.join(_REPO, "examples", "geometries", "arc_seam.dat")
sys.path.insert(0, _HERE)
from mesher_bin import mesher_env as _mesher_env  # noqa: E402

# The circle the fixture's arc is a discretisation of: centre and radius derived
# from the chord and sagitta the geometry was generated with, not copied out of
# it, so an edit to the geometry that changed its shape fails here rather than
# being measured against itself.
_CHORD, _SAG = 2.0, 0.5
_R = (_CHORD * _CHORD / 4.0 + _SAG * _SAG) / (2.0 * _SAG)
_CX, _CY = _CHORD / 2.0, _SAG - _R

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, conf):
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=300)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def fixture():
    """The checked-in topology as data, so a variant differs from it by one key.

    Read from disk rather than rebuilt here: a document a user runs is the thing
    under test, and a gate that composed an equivalent one would leave an edit to
    the shipped file invisible. The shipped documents carry ``//`` comments, which
    the mesher's parser accepts and Python's does not."""
    text = "\n".join(ln for ln in open(_TOPO, encoding="utf-8").read().splitlines()
                     if not ln.lstrip().startswith("//"))
    return json.loads(text)


def edge(doc, eid):
    for e in doc["edges"]:
        if e["id"] == eid:
            return e
    raise AssertionError("no edge %r in the shipped topology" % eid)


def write_topo(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return path


def write_config(path, topology, out_stem, extra=""):
    with open(path, "w", encoding="utf-8") as f:
        f.write("MESH_MODE 1\n"
                "MESH_TOPOLOGY_FILE %s\n"
                "GEOM_FILE %s\n"
                "MB_SPLIT_QUADS 1\n"
                "EXPORT_VTK 1\n"
                "EXPORT_STARCD 1\n"
                "BC_GEOM wall\n"
                "OUTPUT_FILENAME %s.vtk\n" % (topology, _GEOM, out_stem) + extra)
    return path


def vrt_nodes(stem):
    out = []
    with open(stem + ".vrt", encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if len(s) >= 4:
                out.append((float(s[1]), float(s[2])))
    return out


def cel_cells(stem):
    """One tuple of DISTINCT vertex ids per `.cel` row (a triangle is `v1 v2 v3 v3`)."""
    out = []
    with open(stem + ".cel", encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if len(s) >= 5:
                ids, seen = [], []
                for v in s[1:5]:
                    if v not in seen:
                        seen.append(v)
                        ids.append(int(v))
                out.append(tuple(ids))
    return out


def bnd_faces(stem):
    """(frozenset of the face's two vertex ids, patch name) per `.bnd` row."""
    out = []
    with open(stem + ".bnd", encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if len(s) >= 8:
                out.append((frozenset((int(s[1]), int(s[2]))), s[-1]))
    return out


def off_arc(p):
    """How far a point is from the circle the seam's polyline discretises."""
    return abs(math.hypot(p[0] - _CX, p[1] - _CY) - _R)


def edge_use(cells):
    use = {}
    for ids in cells:
        n = len(ids)
        for k in range(n):
            key = frozenset((ids[k], ids[(k + 1) % n]))
            use[key] = use.get(key, 0) + 1
    return use


def components(cells, n_nodes):
    parent = list(range(n_nodes + 1))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    used = set()
    for ids in cells:
        used.update(ids)
        for v in ids[1:]:
            parent[find(ids[0])] = find(v)
    return len({find(v) for v in used})


def refused(tmp, name, doc, needles):
    """One topology the mesher must refuse, exporting nothing."""
    stem = os.path.join(tmp, name)
    conf = write_config(os.path.join(tmp, name + ".dat"),
                        write_topo(os.path.join(tmp, name + ".json"), doc), stem)
    rc, out = run(tmp, conf)
    ok = rc == 8 and "HYBMESH_ERROR 8 TOPOLOGY" in out and all(n in out for n in needles)
    check("7. %s is refused with the TOPOLOGY code, naming %s (rc=%d)"
          % (name, " and ".join(needles), rc), ok)
    if not ok:
        print("       got: %s" % out.strip().splitlines()[-3:])
    check("7. ...and exports NOTHING",
          not any(os.path.exists(stem + e) for e in (".vtk", ".vrt", ".cel")))


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0
    for f in (_TOPO, _GEOM, _GEOM + ".meta"):
        if not os.path.exists(f):
            print("FAIL: the checked-in fixture is missing: " + f)
            return 1

    with tempfile.TemporaryDirectory() as tmp:
        # -- 1. the checked-in fixture meshes, and names its curved seam --------
        stem = os.path.join(tmp, "seam")
        rc, out = run(tmp, write_config(os.path.join(tmp, "seam.dat"), _TOPO, stem))
        check("1. the checked-in two-block fixture meshes (rc=%d)" % rc, rc == 0)
        check("1. ...with zero inverted cells",
              "Inverted cells       : 0 of" in out)
        check("1. ...and the shared-edge report names the seam, its two block sides "
              "AND the segment it FOLLOWS",
              "Interface 'seam'" in out
              and "the south of block 'up' and the north of block 'lo'" in out
              and "following segment 0 of 'arc_seam.dat'" in out)

        nodes = vrt_nodes(stem)
        cells = cel_cells(stem)
        faces = bnd_faces(stem)

        # -- 2. the seam is the CURVE, not the chord --------------------------
        seam = [p for p in nodes if off_arc(p) < 1e-7]
        check("2. the exported grid holds the seam's 41 nodes ON the polyline, to "
              "1e-7 (%d)" % len(seam), len(seam) == 41)
        worst_chord = max((abs(p[1]) for p in seam), default=0.0)
        check("2. ...and the furthest of them is %.4f off the CHORD between its two "
              "corners, which at a sagitta of 0.5 is the curve and not a straight "
              "line" % worst_chord, worst_chord > 0.49)

        chord_doc = fixture()
        del edge(chord_doc, "seam")["follows"]
        c_stem = os.path.join(tmp, "chord")
        rc_c, out_c = run(tmp, write_config(
            os.path.join(tmp, "chord.dat"),
            write_topo(os.path.join(tmp, "chord.json"), chord_doc), c_stem))
        check("2. the SAME topology without the 'follows' meshes (rc=%d)" % rc_c,
              rc_c == 0)
        check("2. ...and the run says the seam is a straight chord",
              "Interface 'seam'" in out_c and "a straight chord" in out_c
              and "following segment" not in out_c)
        c_nodes = vrt_nodes(c_stem)
        on_chord = [p for p in c_nodes if abs(p[1]) < 1e-7 and 0.0 <= p[0] <= 2.0]
        check("2. ...and its 41 seam nodes are on y = 0, so the 0.5 above is the "
              "KEY's doing and not the fixture's (%d)" % len(on_chord),
              len(on_chord) == 41)

        # -- 3. the declared curve survives the default smoothing --------------
        check("3. the default run reports 0 movable nodes on a shared edge, because "
              "a following seam is a declared position exactly as a wall is",
              "of which 0 on a shared edge" in out)
        check("3. ...and the exported seam is still on the polyline AFTER 20 "
              "Winslow sweeps (measured at 4.961e-02 off before the freeze rule "
              "was extended)",
              "Sweeps               : 20 of 20" in out and len(seam) == 41)
        rc_u, out_u = run(tmp, write_config(os.path.join(tmp, "unsm.dat"), _TOPO,
                                            os.path.join(tmp, "unsm"),
                                            extra="MB_SMOOTH_ITERS 0\n"))
        u_seam = [p for p in vrt_nodes(os.path.join(tmp, "unsm")) if off_arc(p) < 1e-7]
        check("3. ...and the UNSMOOTHED run puts the same 41 there, so the freeze is "
              "holding a position the fill already produced (rc=%d, %d)"
              % (rc_u, len(u_seam)), rc_u == 0 and len(u_seam) == 41)

        # -- 4. the exported grid is CONFORMING -------------------------------
        use = edge_use(cells)
        boundary = [k for k, v in use.items() if v == 1]
        odd = {tuple(sorted(k)): v for k, v in use.items() if v not in (1, 2)}
        check("4. no cell edge belongs to more than two cells (%s)" % odd, not odd)
        check("4. ...the triangulation is ONE connected component, so the two blocks "
              "are welded along the curve rather than touching along it",
              components(cells, len(nodes)) == 1)
        check("4. ...and its boundary is exactly the .bnd, face for face (%d vs %d)"
              % (len(boundary), len(faces)),
              set(boundary) == {f[0] for f in faces})

        # -- 5. a following edge is not a boundary ----------------------------
        on_seam = [f for f in faces
                   if all(off_arc(nodes[v - 1]) < 1e-7 for v in f[0])]
        check("5. no .bnd face lies on the curved seam — both blocks have cells "
              "against it, so a face there is a wall through the middle of the fluid "
              "(%d)" % len(on_seam), not on_seam)
        check("5. ...and no patch carries the segment's own label 'seam', which is "
              "unmapped on purpose so a condition that leaked would arrive under its "
              "own name (%s)" % sorted({f[1] for f in faces}),
              {f[1] for f in faces} == {"wall"})
        check("5. ...and the mesher's own boundary-edge count is the outer perimeter "
              "alone: 12 + 12 + 40 + 10 + 10 + 40 = 124",
              "Boundary Edges (BND) : 124" in out)

        # -- 6. the sample-rate advice reaches a following edge ----------------
        rate_doc = fixture()
        edge(rate_doc, "seam")["count"] = 27
        r_stem = os.path.join(tmp, "rate")
        rc_r, out_r = run(tmp, write_config(
            os.path.join(tmp, "rate.dat"),
            write_topo(os.path.join(tmp, "rate.json"), rate_doc), r_stem))
        check("6. a following seam sampled at 40 facets over 26 intervals meshes "
              "(rc=%d)" % rc_r, rc_r == 0)
        check("6. ...and the run SAYS the polyline cannot carry that rate, naming the "
              "edge, both counts and the resampling fix — the same advice a bound "
              "wall gets, because the measurement is about a polyline and this edge "
              "has one",
              "edge 'seam'" in out_r
              and "sample the source stretch it lies on" in out_r
              and "40 polyline facets" in out_r)
        check("6. ...while the shipped count of 41 over 40 facets says nothing, so "
              "the warning is keyed on the rate and not on the key",
              "sample the source stretch it lies on" not in out)

        # -- 7. every refusal, end to end -------------------------------------
        wall_doc = fixture()
        e = edge(wall_doc, "seam")
        e["kind"] = "wall"
        refused(tmp, "follows_on_wall", wall_doc, ["'follows'", "binding"])

        bind_doc = fixture()
        e = edge(bind_doc, "seam")
        e["binding"] = e.pop("follows")
        refused(tmp, "binding_on_interface", bind_doc, ["'binding'", "follows"])

        both_doc = fixture()
        e = edge(both_doc, "seam")
        e["binding"] = dict(e["follows"])
        refused(tmp, "both_keys", both_doc, ["'binding'", "'follows'"])

        off_doc = fixture()
        for c in off_doc["corners"]:
            if c["id"] == "se":
                c.clear()
                c.update({"id": "se", "kind": "free", "xy": [2.0, 0.0]})
        refused(tmp, "corner_off_segment", off_doc,
                ["'se'", "follows segment 0", "free coordinate"])

    print("\nRESULT: " + ("ALL PASS" if not failures
                          else "%d FAILURE(S)" % len(failures)))
    for f in failures:
        print("  - " + f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
