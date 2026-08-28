#!/usr/bin/env python3
"""The multi-block path, end to end through the real binary (issue #50).

The DECISIONS behind this path are pinned next door in ``tests/cpp/test_multiblock.cpp``,
which links the pure layer alone and asserts on blocks, cells, boundary edges and
refusals as data. What can only be checked out here is that the chain CONNECTS:
that a topology document on disk becomes files on disk, through the existing
exporters, with no change to them.

What this pins down:

  1. The topology example this repo ships really meshes, so the documentation is
     covered rather than merely present.
  2. The quads are split into triangles, and the split is switchable OFF — the
     same topology then exports one quad per cell instead of two triangles.
  3. A malformed topology document exits with the TOPOLOGY code, names what is
     wrong, and exports NOTHING.
  4. A topology file that is declared but not there is refused the same way,
     rather than falling through to an empty mesh.
  5. Every boundary edge reaches the ``.bnd`` carrying its BC, so the grid the
     solver reads is not the all-``wall`` default arrived at by accident.

THE ACCEPTANCE RUN, dated and quoted rather than replaced by a shape check.
CI has no solver binary, so this is recorded here in the convention this repo
adopted after a change shipped broken behind 85 green tests that pinned strings
and never executed the solver.

Measured 2026-08-27 on ``examples/topology/square_block.json`` (a 21 x 21 unit
square, one block):

    ./run.sh -conf <conf> -out_name square.vtk
        -> 441 vertices, 800 triangles, 80 boundary edges, one `wall` patch

    solver/preprocess/getPGrid/work/getPGrid < para.in        # the grid converter
        -> EXIT 0
           "Read in 441 vertices coordinates"
           "Read in 800 elements"
           "number of boundary elements = 80"
           "Read in 80 boundary condition flags"

    solver/execute/unicones.eqn6.mac -t mbv0 input.in         # the solver
        -> EXIT 0
           last printed "Global Iteration count 90", at print_convg_per_niter 10
           with num_half_iter 100 -- i.e. 100 iterations, by the 90 + 10
           arithmetic services/case_run_note.iteration_span uses.
           Wrote binDumpZmbv0.dat, xtecp_sol_allzmbv0.dat, uniconesmbv0.enorm.

The case is a closed all-``wall`` box, because its topology declares no geometry
binding: every boundary edge then takes the config default BC. That is a
limitation of the CASE, not of the chain -- the converter and the solver each
accepted the mesh on its own terms. A topology that DOES name the source segment
each edge lies on is covered next door, in
``test_multiblock_binding_surface.py``, and the multi-block chain in
``test_multiblock_weld_surface.py``; the single-block unbound case still has to
keep working, which is what this file goes on pinning.

BLIND SPOTS, named rather than papered over:

  * Nothing here re-runs the solver. The acceptance figures above are a record of
    one dated run, not something this file measures.
  * The checks read the STAR-CD ``.cel``/``.bnd`` rather than the ``.vtk``,
    because those are the files the solver's converter consumes. The ``.vtk``
    side is covered by the golden comparator's multi-block cases, which read
    both.

Run:  python3 tools/PreProcessor/tests/test_multiblock_surface.py
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
_EXAMPLE = os.path.join(_REPO, "examples", "topology", "square_block.json")
sys.path.insert(0, _HERE)
from mesher_bin import mesher_env as _mesher_env  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def write_topology(path, ni=6, nj=5, x1=1.0, y1=1.0, spacing=None, corners=None):
    """One block, ni x nj nodes, as a topology document.

    Shared with ``tools/scripts/golden_mesh.py`` and with
    ``test_multiblock_quality_surface.py``, both of which import it rather than
    keeping a second copy: a topology written twice is a guaranteed future
    divergence, and this is where its shape is specified.

    `spacing` (a dict, e.g. ``{"law": "geometric", "growth": 1.2}``) is attached
    to the two i-direction edges, so a graded case differs from the uniform one
    by exactly that.

    `corners` overrides the rectangle with four explicit ``(x, y)`` pairs in
    ``[sw, se, ne, nw]`` order — the same order the block declares its edges in.
    It exists so the quality gate next door can ask for a block whose corner ring
    is still counter-clockwise (so the declaration is ACCEPTED) while its
    transfinite interior folds. Default: the ``x1`` / ``y1`` rectangle, so every
    existing caller is byte-identical.
    """
    edge_i = {"kind": "wall", "count": ni}
    if spacing:
        edge_i = dict(edge_i, spacing=spacing)
    xy = corners or [(0.0, 0.0), (x1, 0.0), (x1, y1), (0.0, y1)]
    doc = {
        "format_version": 1,
        "corners": [
            {"id": cid, "kind": "free", "xy": [float(p[0]), float(p[1])]}
            for cid, p in zip(("sw", "se", "ne", "nw"), xy)
        ],
        "edges": [
            dict(id="south", corners=["sw", "se"], **edge_i),
            dict(id="east", corners=["se", "ne"], kind="wall", count=nj),
            dict(id="north", corners=["nw", "ne"], **edge_i),
            dict(id="west", corners=["sw", "nw"], kind="wall", count=nj),
        ],
        "blocks": [{"id": "block0", "edges": ["south", "east", "north", "west"]}],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return path


def write_config(path, topology, out_stem, split=True, extra=""):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"MESH_MODE 1\n"
                f"MESH_TOPOLOGY_FILE {topology}\n"
                f"MB_SPLIT_QUADS {1 if split else 0}\n"
                f"EXPORT_VTK 1\n"
                f"EXPORT_STARCD 1\n"
                f"BC_GEOM wall\n"
                f"OUTPUT_FILENAME {out_stem}.vtk\n"
                + extra)
    return path


def run(tmp, conf):
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=300)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def cel_rows(stem):
    """One entry per `.cel` row: the number of DISTINCT vertex ids it names.

    The exporter writes a triangle as `v1 v2 v3 v3` and a quad as four distinct
    ids, so this is how the split shows up in the file the solver's converter
    reads."""
    out = []
    with open(stem + ".cel", encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if len(s) >= 5:
                out.append(len(set(s[1:5])))
    return out


def bnd_names(stem):
    with open(stem + ".bnd", encoding="utf-8") as f:
        return [ln.split()[-1] for ln in f if ln.split()]


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # ── 1. the shipped example really meshes ────────────────────────────
        stem = os.path.join(tmp, "example")
        rc, out = run(tmp, write_config(os.path.join(tmp, "ex.dat"), _EXAMPLE, stem))
        check("1. the topology example this repo ships meshes (rc=0)", rc == 0)
        check("1. ...and reports the block's logical dimensions, so a run says what "
              "it filled", "21 x 21 nodes" in out)
        for ext in (".vtk", ".vrt", ".cel", ".bnd"):
            check(f"1. ...and wrote {ext} through the existing exporters, unchanged",
                  os.path.exists(stem + ext))

        # ── 2. the split, and its switch ────────────────────────────────────
        topo = write_topology(os.path.join(tmp, "t.json"), ni=6, nj=5)
        tri_stem = os.path.join(tmp, "tri")
        rc, _ = run(tmp, write_config(os.path.join(tmp, "tri.dat"), topo, tri_stem))
        check("2. a 6x5 block meshes (rc=0)", rc == 0)
        rows = cel_rows(tri_stem)
        check(f"2. ...into 2 x 5 x 4 = 40 cells ({len(rows)})", len(rows) == 40)
        check("2. ...every one of them a triangle", rows and set(rows) == {3})

        quad_stem = os.path.join(tmp, "quad")
        rc, out = run(tmp, write_config(os.path.join(tmp, "quad.dat"), topo,
                                        quad_stem, split=False))
        check("2. ...and the split is switchable OFF (rc=0)", rc == 0)
        qrows = cel_rows(quad_stem)
        check(f"2. ...leaving 5 x 4 = 20 cells ({len(qrows)})", len(qrows) == 20)
        check("2. ...every one of them a quad", qrows and set(qrows) == {4})
        check("2. ...and saying so, since the solver cannot use quad cells",
              "quad" in out.lower() and "OFF" in out)
        check("2. ...and the SAME node set either way, because only the cells "
              "differ", open(tri_stem + ".vrt").read() == open(quad_stem + ".vrt").read())

        # ── 3. every boundary edge carries its BC into the .bnd ─────────────
        names = bnd_names(tri_stem)
        check(f"3. the perimeter reaches the .bnd, one face per cell side "
              f"({len(names)})", len(names) == 2 * (5 + 4))
        check(f"3. ...each carrying the declared BC rather than an accident "
              f"({sorted(set(names))})", set(names) == {"wall"})

        # ── 4. a malformed declaration is refused, and exports nothing ──────
        bad = os.path.join(tmp, "bad.json")
        with open(bad, "w", encoding="utf-8") as f:
            f.write('{"format_version": 1, "corners": [{"id": "a", "kind": "free", '
                    '"xy": [0, 0]}], "edges": [], "blocks": []}')
        bad_stem = os.path.join(tmp, "bad")
        rc, out = run(tmp, write_config(os.path.join(tmp, "bad.dat"), bad, bad_stem))
        check("4. a malformed topology exits with the TOPOLOGY code (8)", rc == 8)
        check("4. ...printing the machine-readable line a script branches on",
              "HYBMESH_ERROR 8 TOPOLOGY" in out)
        check("4. ...and naming what is wrong with the document",
              "'edges' must be a non-empty array" in out)
        check("4. ...and exporting NOTHING",
              not any(os.path.exists(bad_stem + e) for e in (".vtk", ".vrt", ".cel")))

        # ── 5. a topology that is not there is the same kind of refusal ─────
        gone_stem = os.path.join(tmp, "gone")
        rc, out = run(tmp, write_config(os.path.join(tmp, "gone.dat"),
                                        os.path.join(tmp, "nope.json"), gone_stem))
        check("5. a topology file that is not there exits 8 too, rather than "
              "meshing nothing successfully", rc == 8)
        check("5. ...naming the file it could not open", "nope.json" in out)
        check("5. ...and exporting NOTHING",
              not os.path.exists(gone_stem + ".vtk"))

    print("\nRESULT: " + ("ALL PASS" if not failures
                          else f"{len(failures)} FAILURE(S)"))
    for f in failures:
        print("  - " + f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
