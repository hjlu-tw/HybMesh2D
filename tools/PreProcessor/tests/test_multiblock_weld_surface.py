#!/usr/bin/env python3
"""Multi-block welding, end to end through the real binary (issue #53).

The DECISIONS are pinned next door in ``tests/cpp/test_multiblock.cpp``, which
links the pure layer alone and asserts on blocks, welded node ids, resolved
counts and refusals as data. What can only be checked out here is that the chain
CONNECTS: that a multi-block topology on disk becomes ONE conforming grid on
disk, through the existing exporters, with no change to them.

What this pins down:

  1. The four-block H-grid this repo ships really meshes, and the run reports what
     it filled: four blocks, the counts it PROPAGATED rather than read, and the
     four interior lines it welded.
  2. The grid is CONFORMING, measured on the exported files rather than argued:
     every interior edge of the triangulation is shared by exactly two cells,
     every boundary edge by exactly one, and the boundary-edge set is exactly the
     ``.bnd``. That is the property the grid converter needs, and it is the one a
     welding defect breaks -- an unwelded seam turns every edge along it into two
     boundary edges the ``.bnd`` never mentions.
  3. Welding is TOPOLOGICAL: the file holds 99 nodes and not the 120 four
     unwelded blocks would need, and no two of them sit at the same coordinates.
  4. An interface does NOT reach the ``.bnd``. It is an interior line with cells
     on both sides, so exporting it as a boundary face would hand the solver a
     wall through the middle of the fluid.
  5. A 'cut' edge is honoured as a cut: the run names it as one, and the mesh is
     identical to the same topology declaring an interface. That pair is the whole
     claim -- the kind is carried into the report, and it changes no arithmetic,
     which is what the seam's header says and all it says.
  6. Two conflicting seeds exit with the TOPOLOGY code, naming both edges, both
     counts and the chain that propagated between them; a class with no seed at
     all is refused the same way. Both export NOTHING.

THE ACCEPTANCE RUN AGAINST THE SOLVER IS OUTSTANDING, and this file says so
rather than implying otherwise. ``test_multiblock_surface.py`` records a dated
getPGrid + unicones run on the single-block case; the four-block grid has NOT
been through either, because this checkout carries no solver tree. What check 2
does instead is pin the SHAPE the converter reads -- conforming interior edges
and a boundary set that matches the ``.bnd`` -- which is the property a welding
defect would break, not a substitute for the converter accepting the file. #26 is
why that distinction is written down: a change shipped broken behind 85 green
tests that pinned strings and never executed the solver.

OTHER BLIND SPOTS, named:

  * Nothing here has more than four blocks, and nothing here welds along a BOUND
    edge (one that follows a geometry). The C++ test covers the bound single-block
    case; a bound shared edge is untested in both places.
  * The checks read the STAR-CD ``.vrt``/``.cel``/``.bnd``, because those are the
    files the converter consumes. The ``.vtk`` side is covered by the golden
    comparator's ``mb_hgrid`` case, which reads both.

Run:  python3 tools/PreProcessor/tests/test_multiblock_weld_surface.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_EXAMPLE = os.path.join(_REPO, "examples", "topology", "hgrid_blocks.json")
sys.path.insert(0, _HERE)
from mesher_bin import mesher_env as _mesher_env  # noqa: E402
from test_multiblock_surface import write_config  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, conf):
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=300)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def write_two_blocks(path, shared_kind="interface", w_count=3, ee_extra=None):
    """Two blocks sharing one declared line, as a topology document.

    The same layout the C++ test uses, so a case can be reasoned about in one
    place: 'w' seeds the j count of BOTH blocks, through the shared edge 'm' and
    on to 'ee', which is what makes a conflict between 'w' and 'ee' need a chain
    two blocks long to explain.
    """
    edges = [
        {"id": "s0", "corners": ["a", "b"], "kind": "wall", "count": 3},
        {"id": "s1", "corners": ["b", "c"], "kind": "wall", "count": 4},
        {"id": "w", "corners": ["a", "d"], "kind": "wall"},
        {"id": "m", "corners": ["b", "e"], "kind": shared_kind},
        {"id": "n0", "corners": ["d", "e"], "kind": "wall"},
        {"id": "n1", "corners": ["e", "f"], "kind": "wall"},
        {"id": "ee", "corners": ["c", "f"], "kind": "wall"},
    ]
    if w_count:
        edges[2]["count"] = w_count
    if ee_extra:
        edges[6].update(ee_extra)
    doc = {
        "format_version": 1,
        "corners": [
            {"id": cid, "kind": "free", "xy": list(xy)}
            for cid, xy in (("a", (0.0, 0.0)), ("b", (1.0, 0.0)), ("c", (2.0, 0.0)),
                            ("d", (0.0, 1.0)), ("e", (1.0, 1.0)), ("f", (2.0, 1.0)))
        ],
        "edges": edges,
        "blocks": [
            {"id": "b0", "edges": ["s0", "m", "n0", "w"]},
            {"id": "b1", "edges": ["s1", "ee", "n1", "m"]},
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
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
    """One tuple of DISTINCT vertex ids per `.cel` row, in file order.

    The exporter writes a triangle as `v1 v2 v3 v3`, so the duplicate is dropped
    while the order -- which is the winding -- is kept."""
    out = []
    with open(stem + ".cel", encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if len(s) >= 5:
                ids, seen = [], set()
                for v in s[1:5]:
                    if v not in seen:
                        seen.add(v)
                        ids.append(int(v))
                out.append(tuple(ids))
    return out


def bnd_faces(stem):
    """(frozenset of the face's two vertex ids, patch name) per row.

    The `.bnd` row is `id v1 v2 0 0 group 0 name`, so the two ids are columns 1-2
    and the two zeros that follow are NOT vertices. Both files number vertices the
    same way here (`.vrt` writes `i + 1` over `nodes` and `.cel` writes
    `nodeId + 1`), which is what lets check 2 compare the two by id."""
    out = []
    with open(stem + ".bnd", encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if len(s) >= 8:
                out.append((frozenset((int(s[1]), int(s[2]))), s[-1]))
    return out


def edge_use(cells):
    """How many cells each undirected cell edge belongs to."""
    use = {}
    for ids in cells:
        n = len(ids)
        for k in range(n):
            key = frozenset((ids[k], ids[(k + 1) % n]))
            use[key] = use.get(key, 0) + 1
    return use


def components(cells, n_nodes):
    """How many connected components the cells form, by SHARED NODE identity.

    Node identity and nothing else: two blocks that merely touch would come back
    as two components here, which is the failure this whole path is about."""
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


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # -- 1. the shipped H-grid meshes, and says what it filled -----------
        stem = os.path.join(tmp, "hgrid")
        rc, out = run(tmp, write_config(os.path.join(tmp, "h.dat"), _EXAMPLE, stem))
        check("1. the four-block H-grid this repo ships meshes (rc=0)", rc == 0)
        for bid, dims in (("bl", "7 x 4"), ("br", "5 x 4"),
                          ("tl", "7 x 6"), ("tr", "6 x 5")):
            check(f"1. ...reporting block '{bid}' as {dims} nodes",
                  f"Block '{bid}'" in out and dims in out)
        check("1. ...and which counts it PROPAGATED rather than read, since a "
              "propagation defect otherwise reads as a design choice",
              "4 declared, 8 propagated" in out)
        for eid in ("h01", "h11", "v10", "v11"):
            check(f"1. ...and the interior line '{eid}' it welded, with the two "
                  f"block sides", f"Interface '{eid}'" in out)

        nodes = vrt_nodes(stem)
        cells = cel_cells(stem)
        faces = bnd_faces(stem)

        # -- 2. the exported grid is CONFORMING ------------------------------
        use = edge_use(cells)
        interior = [k for k, v in use.items() if v == 2]
        boundary = [k for k, v in use.items() if v == 1]
        odd = {tuple(sorted(k)): v for k, v in use.items() if v not in (1, 2)}
        check(f"2. no cell edge belongs to more than two cells ({odd})", not odd)
        check(f"2. ...the triangulation is ONE connected component "
              f"({components(cells, len(nodes))})",
              components(cells, len(nodes)) == 1)
        check(f"2. ...and its boundary is exactly the .bnd, face for face "
              f"({len(boundary)} vs {len(faces)})",
              set(boundary) == {f[0] for f in faces})
        check(f"2. ...which is 36 faces, the outer perimeter and nothing else "
              f"({len(faces)})", len(faces) == 36)
        check(f"2. ...leaving {len(interior)} interior edges, every one of them "
              f"shared", len(interior) == len(use) - len(boundary))

        # -- 3. welding is topological, not a coordinate match ---------------
        check(f"3. the grid holds 99 nodes, not the 120 four unwelded blocks "
              f"would need ({len(nodes)})", len(nodes) == 99)
        check("3. ...and no two of them sit at the same coordinates, so it is ONE "
              "mesh rather than four meshes touching",
              len(set(nodes)) == len(nodes))
        check(f"3. ...over 160 triangles ({len(cells)})", len(cells) == 160)
        check("3. ...every one of them a triangle",
              bool(cells) and {len(c) for c in cells} == {3})

        # -- 4. an interface is not a boundary -------------------------------
        # The interface 'v10' runs from (1, 0) to (1, 0.6) with four nodes, so
        # three faces per side. If it reached the .bnd at all it would arrive as a
        # `wall` band down the middle of the fluid.
        mid = [f for f in faces
               if all(nodes[v - 1][0] == 1.0 and nodes[v - 1][1] <= 0.6 for v in f[0])]
        check(f"4. no boundary face lies on the interior line the blocks share "
              f"({len(mid)})", not mid)
        check("4. ...and every face that IS there carries the declared BC",
              {f[1] for f in faces} == {"wall"})
        # ...and the count the MESHER reports, which is `mesh.edges` rather than
        # the `.bnd`. The two are different instruments and only this one sees the
        # defect: the `.bnd` writer derives its faces from cell connectivity ("used
        # by exactly one cell"), so an interface wrongly RECORDED as a boundary
        # edge never reaches that file and every check above passes. Measured, by
        # injection -- see the note at the top of this docstring's blind spots.
        check("4. ...and the mesher's own boundary-edge count is those 36 and not "
              "the interfaces as well",
              "Boundary Edges (BND) : 36" in out)

        # -- 5. a 'cut' is honoured as a cut ---------------------------------
        i_stem = os.path.join(tmp, "iface")
        c_stem = os.path.join(tmp, "cut")
        topo_i = write_two_blocks(os.path.join(tmp, "i.json"), "interface")
        topo_c = write_two_blocks(os.path.join(tmp, "c.json"), "cut")
        rc_i, out_i = run(tmp, write_config(os.path.join(tmp, "i.dat"), topo_i, i_stem))
        rc_c, out_c = run(tmp, write_config(os.path.join(tmp, "c.dat"), topo_c, c_stem))
        check("5. a topology whose shared line is a 'cut' meshes (rc=0)", rc_c == 0)
        check("5. ...and the run names it a CUT, not an ordinary interface",
              "Cut 'm'" in out_c and "Interface 'm'" not in out_c)
        check("5. ...while the interface version names it an interface",
              "Interface 'm'" in out_i and "Cut 'm'" not in out_i)
        check("5. ...and the two weld identically, which is what the kinds share "
              "and all they share (rc=0)", rc_i == 0)
        for ext in (".vrt", ".cel", ".bnd"):
            check(f"5. ...identical {ext} (the header line carries a timestamp and "
                  f"is not compared)",
                  open(i_stem + ext, encoding="utf-8").read().split("\n")[1:]
                  == open(c_stem + ext, encoding="utf-8").read().split("\n")[1:])

        # -- 6. the two propagation refusals, end to end ---------------------
        bad_stem = os.path.join(tmp, "clash")
        topo = write_two_blocks(os.path.join(tmp, "clash.json"),
                                ee_extra={"count": 9})
        rc, out = run(tmp, write_config(os.path.join(tmp, "clash.dat"), topo, bad_stem))
        check("6. two conflicting seeds exit with the TOPOLOGY code (8)", rc == 8)
        check("6. ...printing the machine-readable line a script branches on",
              "HYBMESH_ERROR 8 TOPOLOGY" in out)
        check("6. ...naming both edges and both counts",
              "'w'" in out and "'ee'" in out and " 3 " in out and " 9" in out)
        check("6. ...and the chain that propagated between them, block by block",
              "'b0'" in out and "'b1'" in out and "west / east" in out)
        check("6. ...and exporting NOTHING",
              not any(os.path.exists(bad_stem + e) for e in (".vtk", ".vrt", ".cel")))

        none_stem = os.path.join(tmp, "noseed")
        topo = write_two_blocks(os.path.join(tmp, "noseed.json"), w_count=None)
        rc, out = run(tmp, write_config(os.path.join(tmp, "noseed.dat"), topo,
                                        none_stem))
        check("6. a class with no seed at all exits 8 too, rather than picking a "
              "count nobody wrote down", rc == 8)
        check("6. ...naming every edge it could not resolve",
              "'w'" in out and "'m'" in out and "'ee'" in out)
        check("6. ...and exporting NOTHING", not os.path.exists(none_stem + ".vtk"))

    print("\nRESULT: " + ("ALL PASS" if not failures
                          else f"{len(failures)} FAILURE(S)"))
    for f in failures:
        print("  - " + f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
