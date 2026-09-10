#!/usr/bin/env python3
"""The multi-block BLOCK ID as a VTK cell field, through the real binary (#106).

#48's user story 39 -- "a block id available as a cell field in the VTK output,
so that when something is wrong I can see which block it is in" -- is the one
item of that issue that was never built and never reversed. It is not decoration:
two of #48's Implementation Decisions name it as the design's ONLY concession to
blocks surviving the flattening step, so without it "blocks are internal
scaffolding, not an output format" is the whole story and the debug affordance
that paid for that decision does not exist.

THE VALUE IS THE INDEX INTO ``MbResult::blocks``, which is what ``MbCell::block``
holds, and NOT the block's declared ``id`` string -- the thing the randomized
split rule hashes. ``include/MultiBlock.hpp`` explains why the two must not be
conflated: an index moves when a block is declared ahead of it, the declared id
does not. This gate reads the index and binds it back to the declaration by
POSITION, which is the relation the exporter actually promises.

What this pins down:

  1. A multi-block run writes a well-formed ``CELL_DATA`` section -- the count
     agreeing with the exported cell count the run itself reports, one value per
     cell, and every value a real block index rather than a sentinel.
  2. THE PER-BLOCK CELL COUNTS AGREE WITH THE RUN'S OWN REPORTED BLOCK
     DIMENSIONS, never with a number written down here: block k of an ni x nj
     block splits into (ni-1)(nj-1) quads, doubled when the quads are split. A
     re-seeded topology therefore changes both sides together and the check
     survives it, which a hardcoded 3840 would not.
  3. On all three shipped multi-block cases the ticket names: the one-block
     square, the four-block O-grid (four EQUAL blocks) and the four-block C-grid
     (1920 / 3840 / 3840 / 1920, so the per-index comparison has something to
     get wrong).
  4. The index is the position in the DECLARATION. Counts alone cannot tell the
     C-grid's two 3840-cell blocks apart, so this is checked geometrically as
     well: index 1 is ``b_upper`` and its cells really are above the chord line,
     index 2 is ``b_lower`` and its cells are below.
  5. The field follows the cells that are EXPORTED, not the blocks that were
     filled: the same topology at ``MB_SPLIT_QUADS 0`` halves every count.
  6. THE FIELD IS ABSENT FROM A HYBRID-PATH RUN. This is the half a positive-only
     check would miss and it is the reason ``Element::blockId`` is an
     ``std::optional`` rather than a defaulted 0: the hybrid path has no blocks,
     and a ``.vtk`` claiming every cell is in block 0 is a worse answer than no
     field at all. Not "the values are -1" -- no ``CELL_DATA`` and no ``SCALARS``
     anywhere in the file.
  7. The readers this repo ships still parse a file that HAS the section --
     ``models/vtk_mesh.VTKMesh`` (which ``golden_mesh.py`` compares through) and
     ``tools/scripts/view_mesh_vtk.py`` -- and see the same cells they saw before.

VERIFIED BY INJECTION, 2026-09-10, each one restored and REBUILT before the next
(the exit code is read first: a gate that crashes reports zero FAIL lines and
would look inert). Counts are FAIL lines out of 37 checks:

  * ``src/Mesh.cpp``: delete the whole ``if (allTagged)`` block.  -> exit 1,
    23 FAIL across groups 1, 2, 4 and 5. Group 6 stays green, which is correct:
    it asserts an ABSENCE. So does group 7 — ``VTKMesh`` and the viewer never
    read the section, which is the blind spot below stated as a measurement.
  * ``src/Mesh.cpp``: keep writing it but drop the guard —
    ``if (true || allTagged)`` with ``el.blockId ? *el.blockId : 0``.  -> exit 1,
    2 FAIL, BOTH in group 6: the hybrid file grows a section of zeros. Groups
    1-5 stay green, which is the whole reason group 6 exists.
  * ``src/cli.cpp``: write a constant, ``mesh.addElement(c.nodeIds, 0)``.
    -> exit 1, 6 FAIL, in groups 1 (four blocks no longer all present), 2 (the
    counts) and 4 (the identity). The square cases stay green, because on a
    ONE-block topology a constant 0 is the right answer — which is why the
    four-block shipped cases are here and not only a synthetic block.
  * ``src/cli.cpp``: write ``c.block % 2``.  -> exit 1, 6 FAIL. Named because it
    is the injection the SIZE comparison is weakest against on the O-grid, whose
    four blocks are all 2304 cells: there it merges four buckets into two and is
    caught by which indices are present, not by their sizes.
  * ``src/cli.cpp``: SWAP indices 1 and 2 (``c.block == 1 ? 2 : ...``).  -> exit
    1, 2 FAIL, both of them check 4's geometric half. Every count check passes,
    because the two blocks are the same size. This is the injection that earns
    check 4 its place: without it the gate would accept a field that says
    ``b_lower`` for every cell above the airfoil.

BLIND SPOTS, named rather than papered over:

  * ``golden_mesh.py`` IS BLIND TO THIS FIELD. It compares the ``.vtk`` through
    ``VTKMesh``, which ignores every section after ``CELL_TYPES``, so all ten
    multi-block golden cases compare SAME across this change. That is what made
    the hybrid half of #106's acceptance measurable at all (19/19 SAME against a
    pre-change binary), and it means the golden set contributes NOTHING to
    covering the field itself. This file is the only thing that does.
  * Counts cannot distinguish the C-grid's index 0 from index 3 (both 1920) nor
    the O-grid's four 2304s from each other. Check 4 closes the 1-vs-2 case
    geometrically; 0-vs-3 (the two wake blocks) is left open, and a swap of just
    those two would pass everything here.
  * The value is read as an integer, so nothing here would notice the exporter
    writing it as a float that happens to round-trip.

Run:  python3 tools/PreProcessor/tests/test_multiblock_block_field.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_VIEWER = os.path.join(_REPO, "tools", "scripts", "view_mesh_vtk.py")
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_REPO, "tools", "PreProcessor", "gui"))

# Imported, never copied. Each shipped case's config is retargeted by the gate
# that owns it, so an edit to config/multiblock_*.dat is visible here through the
# same assertion that keeps that gate honest.
from test_multiblock_surface import (  # noqa: E402
    _EXAMPLE, run as run_conf, write_config,
)
from test_multiblock_cgrid_surface import (  # noqa: E402
    base_config as cgrid_config, run_case as run_shipped, topology as cgrid_topology,
)
from test_multiblock_ogrid_surface import base_config as ogrid_config  # noqa: E402
from test_mesh_mode_surface import run as run_body, write_square  # noqa: E402
from mesher_bin import NO_SMOOTH  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


# ── Reading the file ────────────────────────────────────────────────────────
def read_vtk(path):
    """``(points, cells, field)`` from a legacy-VTK file; ``field`` is None when
    the file carries no ``CELL_DATA`` section.

    A parser of its own, rather than ``VTKMesh``, precisely because ``VTKMesh``
    stops at ``CELL_TYPES`` -- the thing check 7 relies on and the thing that
    makes it useless for reading the new section. It also keeps the cells in
    FILE order, which is the order the field indexes; ``VTKMesh`` re-groups them
    into triangles/quads/polygons and that correspondence is lost.
    """
    with open(path, encoding="utf-8") as f:
        toks = f.read().split()
    pts, cells, field = [], [], None
    i, n = 0, len(toks)
    while i < n:
        if toks[i] == "POINTS":
            npts = int(toks[i + 1])
            i += 3                                   # skip the dtype
            for _ in range(npts):
                pts.append((float(toks[i]), float(toks[i + 1])))
                i += 3
            continue
        if toks[i] == "CELLS":
            ncells, total = int(toks[i + 1]), int(toks[i + 2])
            i += 3
            end = i + total
            while i < end:
                cnt = int(toks[i]); i += 1
                cells.append([int(toks[i + j]) for j in range(cnt)])
                i += cnt
            assert len(cells) == ncells
            continue
        if toks[i] == "CELL_DATA":
            ncells = int(toks[i + 1])
            # SCALARS <name> <type> <ncomp>, then LOOKUP_TABLE <name>.
            assert toks[i + 2] == "SCALARS", toks[i + 2:i + 8]
            assert toks[i + 6] == "LOOKUP_TABLE", toks[i + 2:i + 10]
            i += 8
            field = [int(v) for v in toks[i:i + ncells]]
            i += ncells
            continue
        i += 1
    return pts, cells, field


def has_cell_data(path):
    """True if the file mentions the section AT ALL.

    Deliberately a dumb text search and not ``read_vtk``: check 6's claim is that
    nothing was written, and a parser that skips what it does not understand is
    the wrong instrument for proving an absence.
    """
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return "CELL_DATA" in text or "SCALARS" in text


def reported_blocks(out):
    """``[(id, ni, nj), ...]`` from the run's own ``[ Multi-block Topology ]``
    banner, IN REPORTED ORDER -- which is declaration order, which is the index
    the cell field carries."""
    return [(m.group(1), int(m.group(2)), int(m.group(3)))
            for m in re.finditer(r"Block '([^']+)'\s*:\s*(\d+) x (\d+) nodes", out)]


def expected_counts(out, split=True):
    """Cells per block index, derived from the RUN'S OWN report."""
    per = 2 if split else 1
    return {k: (ni - 1) * (nj - 1) * per
            for k, (_, ni, nj) in enumerate(reported_blocks(out))}


def centroid_y(pts, cell):
    return sum(pts[v][1] for v in cell) / len(cell)


# ── One case, checked the same way every time ───────────────────────────────
def check_case(label, out, stem, split=True):
    """Groups 1-3 for one multi-block run. Returns ``(pts, cells, field)``."""
    pts, cells, field = read_vtk(stem + ".vtk")
    blocks = reported_blocks(out)
    check(f"1. [{label}] the run reports its blocks, so there is something to "
          f"check the field against ({len(blocks)} block(s))", bool(blocks))
    check(f"1. [{label}] the .vtk carries a CELL_DATA block field", field is not None)
    # NO EARLY RETURN on an absent field. Every check below is a claim about the
    # field's CONTENT, and an absent field fails each of them on its merits --
    # `vals` is empty, so the counts do not match and no block is present. The
    # first version of this function returned here, which turned "the exporter
    # writes nothing" into ONE red line per case and silently skipped the
    # per-block counts that are the ticket's actual subject.
    vals = field if field is not None else []
    check(f"1. [{label}] ...with exactly one value per exported cell "
          f"({len(vals)} values, {len(cells)} cells)", len(vals) == len(cells))
    check(f"1. [{label}] ...every value a real block index and not a sentinel "
          f"({sorted(set(vals))})",
          bool(vals) and all(0 <= v < len(blocks) for v in vals))
    check(f"1. [{label}] ...and every declared block present, so the field names "
          f"all {len(blocks)} of them", set(vals) == set(range(len(blocks))))

    want = expected_counts(out, split)
    got = dict(Counter(vals))
    check(f"2. [{label}] the per-block cell counts equal the run's OWN reported "
          f"block dimensions: {[(b[0], b[1], b[2]) for b in blocks]} -> {want}, "
          f"got {got}", got == want)
    return pts, cells, field


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # ── 3a. the shipped one-block square ────────────────────────────────
        sq_stem = os.path.join(tmp, "square")
        rc, out = run_conf(tmp, write_config(os.path.join(tmp, "square.dat"),
                                             _EXAMPLE, sq_stem, extra=NO_SMOOTH))
        check(f"3a. the shipped square topology meshes (rc={rc})", rc == 0)
        if rc == 0:
            check_case("square", out, sq_stem)

        # ── 3b. the shipped four-block O-grid ───────────────────────────────
        p, og_stem = run_shipped(tmp, "ogrid", ogrid_config())
        check(f"3b. the shipped O-grid config exits 0 (rc={p.returncode})",
              p.returncode == 0)
        if p.returncode == 0:
            check_case("ogrid", p.stdout + p.stderr, og_stem)

        # ── 3c/4. the shipped four-block C-grid, and WHICH block is which ───
        p, cg_stem = run_shipped(tmp, "cgrid", cgrid_config())
        cg_out = p.stdout + p.stderr
        check(f"3c. the shipped C-grid config exits 0 (rc={p.returncode})",
              p.returncode == 0)
        if p.returncode == 0:
            pts, cells, field = check_case("cgrid", cg_out, cg_stem)

            # The index is a POSITION in the declaration, so the k-th reported
            # block must be the k-th block the document declares. Read from the
            # parsed document rather than from a list written down here.
            declared = [b["id"] for b in cgrid_topology()["blocks"]]
            check(f"4. the run reports its blocks in DECLARATION order, which is "
                  f"the order the field indexes ({declared})",
                  [b[0] for b in reported_blocks(cg_out)] == declared)

            # Counts cannot separate b_upper from b_lower -- both are 3840. The
            # geometry can: one is above the chord line and one below. An absent
            # or wrong field leaves `sel` empty for one of them, which is why
            # the emptiness is part of the assertion and not a guard around it.
            up, lo = declared.index("b_upper"), declared.index("b_lower")
            for k, want_above in ((up, True), (lo, False)):
                sel = [c for c, b in zip(cells, field or []) if b == k]
                ys = [centroid_y(pts, c) for c in sel]
                ok = bool(ys) and (min(ys) > 0.0 if want_above else max(ys) < 0.0)
                side = "above" if want_above else "below"
                check(f"4. ...and index {k} really is "
                      f"'{'b_upper' if want_above else 'b_lower'}': all "
                      f"{len(sel)} of its cells sit {side} the chord line "
                      f"(y range {(min(ys), max(ys)) if ys else 'no cells'})", ok)

        # ── 5. the field follows the EXPORTED cells, not the filled blocks ──
        q_stem = os.path.join(tmp, "squareq")
        rc, qout = run_conf(tmp, write_config(os.path.join(tmp, "squareq.dat"),
                                              _EXAMPLE, q_stem, split=False,
                                              extra=NO_SMOOTH))
        check(f"5. the same topology as QUADS meshes (rc={rc})", rc == 0)
        if rc == 0:
            check_case("square/quads", qout, q_stem, split=False)
            _, qcells, qfield = read_vtk(q_stem + ".vtk")
            _, scells, _ = read_vtk(sq_stem + ".vtk")
            check(f"5. ...over HALF as many cells as the split run "
                  f"({len(qcells)} vs {len(scells)}), so the field counts what "
                  f"was exported and not what was filled",
                  bool(qfield) and len(qcells) * 2 == len(scells))

        # ── 6. ABSENT on the hybrid path ────────────────────────────────────
        geom = os.path.join(tmp, "sq_geom.dat")
        write_square(geom)
        hyb = os.path.join(tmp, "hybrid")
        rc, hout = run_body(tmp, f"""
GEOM_FILE {geom}
DOMAIN_X_MIN -6
DOMAIN_X_MAX 6
DOMAIN_Y_MIN -6
DOMAIN_Y_MAX 6
BL_LAYERS 3
EXPORT_VTK 1
OUTPUT_FILENAME {hyb}
""")
        check(f"6. a hybrid-path run meshes (rc={rc})",
              rc == 0 and os.path.exists(hyb + ".vtk"))
        if os.path.exists(hyb + ".vtk"):
            _, hcells, hfield = read_vtk(hyb + ".vtk")
            check(f"6. ...and its .vtk carries NO cell field at all — not a field "
                  f"of zeros, not one of -1 ({len(hcells)} cells)", hfield is None)
            check("6. ...with neither 'CELL_DATA' nor 'SCALARS' anywhere in the "
                  "file, checked as text so a tolerant parser cannot hide it",
                  not has_cell_data(hyb + ".vtk"))

        # ── 7. the readers this repo ships still parse the new section ──────
        if os.path.exists(cg_stem + ".vtk"):
            from app.models.vtk_mesh import VTKMesh
            m = VTKMesh.from_file(cg_stem + ".vtk")
            _, cells, _ = read_vtk(cg_stem + ".vtk")
            check(f"7. VTKMesh — which golden_mesh.py compares through — still "
                  f"reads the mesh, and sees the same cells "
                  f"({len(m.triangles) + len(m.quads) + len(m.polygons)} vs "
                  f"{len(cells)})",
                  len(m.triangles) + len(m.quads) + len(m.polygons) == len(cells)
                  and len(m.points) > 0)
            png = os.path.join(tmp, "cgrid.png")
            v = subprocess.run([sys.executable, _VIEWER, cg_stem + ".vtk", png],
                               capture_output=True, text=True, timeout=600)
            if v.returncode != 0 and "matplotlib" in (v.stderr or ""):
                # The viewer is the only thing here that needs matplotlib. A
                # machine without it is not evidence about the exporter.
                print("SKIP  7. view_mesh_vtk.py (matplotlib not installed)")
            else:
                check(f"7. view_mesh_vtk.py still renders a multi-block mesh "
                      f"rather than tripping over the new section "
                      f"(rc={v.returncode})",
                      v.returncode == 0 and os.path.exists(png))

    print("\nRESULT: " + ("ALL PASS" if not failures
                          else f"{len(failures)} FAILURE(S)"))
    for f in failures:
        print("  - " + f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
