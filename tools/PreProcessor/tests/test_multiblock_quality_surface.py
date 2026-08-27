#!/usr/bin/env python3
"""The multi-block quality report and the inverted-cell gate, through the real
binary (issue #51).

The instrument itself is pinned next door in ``tests/cpp/test_mb_quality.cpp``,
which links the pure layer alone and drives ``measureMbQuality`` on meshes nobody
parsed. What can only be checked out here is the half that IS the ticket: that
the four numbers reach a run's output, that a folded mesh is EXPORTED and exits
with its own code, and that an invalid declaration exports nothing and exits with
a different one — so a caller can tell "look at the mesh" from "fix your JSON"
without reading a word of prose.

What this pins down:

  1. Every multi-block run prints the inverted cell count, maximum and mean
     non-orthogonality, the wall first-cell height accuracy and the cell count,
     on a mesh that is FINE. A report that only appears when something is wrong
     is not the baseline the later elliptic-smoothing increment needs.
  2. One machine-readable ``HYBMESH_MB_QUALITY`` line carries the same numbers as
     ``key=value``, so the acceptance gate this instrument exists for is a grep.
  3. STRETCH IS NOT NON-ORTHOGONALITY. A strongly graded but axis-aligned block
     reports exactly 0 degrees while asking for a first cell ~6x finer than
     uniform. This is the acceptance criterion "computed from cell geometry
     directly, not inferred from a proxy that runs long on stretched cells",
     measured on the real binary rather than argued.
  4. A mesh holding inverted cells is EXPORTED — all four files, under the
     ordinary name and not the ``_er`` partial-mesh name — and exits 9 with the
     stable token ``INVERTED``.
  5. That mesh comes from a declaration the mesher ACCEPTS: no topology refusal is
     printed. Otherwise check 4 would be pinning a refusal wearing a second code.
  6. An invalid declaration exits 8 with the token ``TOPOLOGY`` and writes
     nothing.
  7. The two are distinguishable BY EXIT CODE ALONE.
  8. The inverted count follows the cells that are actually exported: the same
     folded topology with ``MB_SPLIT_QUADS 0`` reports a different, quad-sized
     number.

THE DELIBERATELY FOLDED TOPOLOGY is a dart -- corners (0,0), (1,0), (0.1,0.1),
(0,1). Its ring winds counter-clockwise (signed area +0.1), so
``buildMultiBlock``'s clockwise-ring refusal does not fire; the fill folds anyway,
because the ring is strongly non-convex at ``ne``. That is the whole point of
there being two exit codes: a backwards-wound ring is a defect of the DOCUMENT and
is refused, while this is a valid document whose interpolated interior came out
folded, and there is something worth looking at.

MEASURED 2026-08-27, on the dart at 5 x 5 nodes:

    exit 9, HYBMESH_ERROR 9 INVERTED <topology>
    16 of 32 cells inverted
    non-orthogonality max 83.660 deg, mean 57.572 deg
    wall first cell worst 25.41% off the declared height
    dartout.vtk / .vrt / .cel / .bnd all written

BLIND SPOTS, named rather than papered over:

  * Nothing here runs the solver or the grid converter on the folded mesh. That it
    is written is the claim; that anything downstream accepts it is not, and would
    be a strange thing to want.
  * The numbers are read out of the machine-readable line, so the human-readable
    banner is checked for presence and not value-by-value. The two are built from
    one report object, and the C++ test pins the report.

Run:  python3 tools/PreProcessor/tests/test_multiblock_quality_surface.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
sys.path.insert(0, _HERE)
# Imported, not copied: the topology document's shape is specified once, in the
# gate that introduced it. `corners=` was added there for the dart below.
from test_multiblock_surface import (  # noqa: E402
    run, write_config, write_topology,
)

# The dart, in [sw, se, ne, nw] order. Accepted by the declaration checks; folds.
DART = [(0.0, 0.0), (1.0, 0.0), (0.1, 0.1), (0.0, 1.0)]

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def quality(out):
    """The HYBMESH_MB_QUALITY line as a dict of floats, or None if absent."""
    for line in out.splitlines():
        if line.startswith("HYBMESH_MB_QUALITY "):
            got = {}
            for tok in line.split()[1:]:
                k, _, v = tok.partition("=")
                got[k] = float(v)
            return got
    return None


def wrote(stem):
    return [e for e in (".vtk", ".vrt", ".cel", ".bnd")
            if os.path.exists(stem + e)]


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # ── 1/2. the report is on every run, including a good one ───────────
        good = write_topology(os.path.join(tmp, "good.json"), ni=6, nj=5)
        gstem = os.path.join(tmp, "good")
        rc, out = run(tmp, write_config(os.path.join(tmp, "good.dat"), good, gstem))
        check("1. a sound topology still meshes (rc=0)", rc == 0)
        check("1. ...and prints the quality report", "[ Multi-block Mesh Quality ]" in out)
        for label in ("Inverted cells", "Non-orthogonality", "Wall first cell"):
            check(f"1. ...naming '{label}' on a mesh that is FINE, so the numbers are "
                  f"a baseline and not only an alarm", label in out)
        q = quality(out)
        check("2. one machine-readable line carries the numbers", q is not None)
        if q:
            check(f"2. ...the cell count ({q.get('cells')})", q.get("cells") == 40)
            check("2. ...the inverted count", q.get("inverted") == 0)
            check("2. ...max and mean non-orthogonality",
                  "nonortho_max_deg" in q and "nonortho_mean_deg" in q)
            check("2. ...and the wall first-cell accuracy",
                  q.get("wall_first_cell_worst_rel") == 0.0)

        # ── 3. stretch is not non-orthogonality ─────────────────────────────
        grad = write_topology(os.path.join(tmp, "grad.json"), ni=9, nj=9,
                              spacing={"law": "geometric", "growth": 1.5})
        sstem = os.path.join(tmp, "grad")
        rc, out = run(tmp, write_config(os.path.join(tmp, "grad.dat"), grad, sstem))
        check("3. a strongly graded block meshes (rc=0)", rc == 0)
        q = quality(out)
        check("3. ...and measures EXACTLY zero non-orthogonality, which no "
              "size-or-edge-length proxy can report",
              bool(q) and q.get("nonortho_max_deg") == 0.0)
        # The grading is real, and read from the report's own asked-for value: the
        # first cell off the west wall is the first geometric interval (~0.0203),
        # against a uniform 1/8. Without this the zero above could be a flat mesh.
        west = [ln for ln in out.splitlines() if "west 'west'" in ln]
        check("3. ...on a mesh whose first cell really is far finer than uniform, "
              f"so the zero is not a flat-mesh artefact ({west})",
              bool(west) and "2.030e-02" in west[0])

        # ── 4/5. a folded mesh is exported, and exits 9 ─────────────────────
        dart = write_topology(os.path.join(tmp, "dart.json"), ni=5, nj=5, corners=DART)
        dstem = os.path.join(tmp, "dart")
        rc, out = run(tmp, write_config(os.path.join(tmp, "dart.dat"), dart, dstem))
        check(f"4. a folded mesh exits with the INVERTED code (9), got {rc}", rc == 9)
        check("4. ...printing the machine-readable line a script branches on",
              "HYBMESH_ERROR 9 INVERTED" in out)
        check(f"4. ...and EXPORTING the mesh anyway ({wrote(dstem)})",
              wrote(dstem) == [".vtk", ".vrt", ".cel", ".bnd"])
        check("4. ...under its ordinary name, not the '_er' partial-mesh name — the "
              "cells are wrong, the mesh is not truncated",
              not os.path.exists(dstem + "_er.vtk"))
        q = quality(out)
        check(f"4. ...counting the inverted cells ({q and q.get('inverted')})",
              bool(q) and q.get("inverted") == 16)
        check("4. ...with the other two numbers live on the same mesh",
              bool(q) and q.get("nonortho_max_deg") > 45.0
              and q.get("wall_first_cell_worst_rel") > 0.1)
        check("5. and that mesh came from a declaration the mesher ACCEPTED — no "
              "topology refusal, so this is not a refusal wearing a second code",
              "HYBMESH_ERROR 8" not in out and "TOPOLOGY" not in out)

        # ── 6/7. an invalid declaration is the OTHER failure kind ───────────
        bad = os.path.join(tmp, "bad.json")
        with open(bad, "w", encoding="utf-8") as f:
            f.write('{"format_version": 1, "corners": [{"id": "a", "kind": "free", '
                    '"xy": [0, 0]}], "edges": [], "blocks": []}')
        bstem = os.path.join(tmp, "bad")
        brc, bout = run(tmp, write_config(os.path.join(tmp, "bad.dat"), bad, bstem))
        check(f"6. an invalid declaration exits with the TOPOLOGY code (8), got {brc}",
              brc == 8)
        check("6. ...with its own stable token", "HYBMESH_ERROR 8 TOPOLOGY" in bout)
        check(f"6. ...and exports NOTHING ({wrote(bstem)})", wrote(bstem) == [])
        check("6. ...so there is no quality report to print either",
              quality(bout) is None)
        check("7. the two failure kinds are distinguishable BY EXIT CODE ALONE: "
              f"{rc} (look at the mesh) vs {brc} (fix the declaration)",
              rc == 9 and brc == 8 and rc != brc)

        # ── 8. the count follows the cells that are EXPORTED ────────────────
        qstem = os.path.join(tmp, "dartq")
        rc2, out2 = run(tmp, write_config(os.path.join(tmp, "dartq.dat"), dart,
                                          qstem, split=False))
        check(f"8. the same folded topology as quads exits 9 too, got {rc2}", rc2 == 9)
        q2 = quality(out2)
        check(f"8. ...over 16 quads rather than 32 triangles ({q2 and q2.get('cells')})",
              bool(q2) and q2.get("cells") == 16)
        check(f"8. ...so the inverted count differs from the triangle run's 16 "
              f"({q2 and q2.get('inverted')})",
              bool(q2) and q2.get("inverted") > 0 and q2.get("inverted") != 16)
        check("8. ...while non-orthogonality is IDENTICAL, being a property of the "
              "grid and not of how the quads were cut",
              bool(q) and bool(q2)
              and q.get("nonortho_max_deg") == q2.get("nonortho_max_deg"))

    print("\nRESULT: " + ("ALL PASS" if not failures
                          else f"{len(failures)} FAILURE(S)"))
    for f in failures:
        print("  - " + f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
