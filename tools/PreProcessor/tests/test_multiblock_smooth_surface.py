#!/usr/bin/env python3
"""The multi-block smoothing pass, end to end through the real binary (issue #81).

The kernel itself is pinned next door in ``tests/cpp/test_multiblock.cpp`` checks
40-46, which link the pure layer alone and drive ``buildMultiBlock`` with a
topology STRING: which nodes move, which are frozen, that the kernel is the mean
of a node's four logical neighbours, and that N sweeps are N Jacobi applications
of it. What can only be checked out here is the half that reaches a user: that
``MB_SMOOTH_ITERS`` travels from a ``.dat`` into the seam at all, that the run
REPORTS what smoothing bought, and that the reporting is unchanged when nothing
was smoothed.

Driven on the SHIPPED C-grid (``config/multiblock_cgrid.dat``), read from disk
through ``test_multiblock_cgrid_surface.base_config()`` rather than composed
here — the same rule the golden comparator follows: these files are documentation
a user runs, and an edit to one has to be visible from a gate.

What this pins down:

  1. At the default (no ``MB_SMOOTH_ITERS`` line at all) the output is what it was
     before this parameter existed: ONE quality block, ONE machine-readable
     ``HYBMESH_MB_QUALITY`` line, and NO ``_BEFORE`` line anywhere.
  2. With sweeps on, the run reports the mesh BEFORE and AFTER — two banners and
     two machine-readable lines — and the BEFORE line is bit-identical to the
     figures the same case prints at the default. So the pair really is one mesh
     measured twice, not two runs that happened to agree.
  3. THE UNSUFFIXED LINE ALWAYS DESCRIBES THE MESH AS EXPORTED. A gate grepping
     ``HYBMESH_MB_QUALITY`` keeps getting the answer about the file on disk,
     smoothed or not, and never has to know which run it is reading.
  4. THE WALL FIRST CELL GETS WORSE. This kernel equalises spacing, so it spends
     the wall resolution the declaration exists to deliver. Measured on the
     shipped case and asserted as a direction with a floor, because the point of
     shipping a Laplacian first is to put that cost on the ruler rather than to
     argue about it. Non-orthogonality — the metric #80 is aimed at — gets worse
     too, which is what makes the case for the Winslow kernel and the wall
     control functions rather than for more sweeps of this one.
  5. A smoothing pass that FOLDS a cell exits with the inverted-cell code (9),
     exactly as an unsmoothed fold does, and exports the mesh anyway. No new
     failure mode and no second code: a fold is a fold.
  6. A NEGATIVE sweep count is refused BY NAME with the CONFIG code and exports
     nothing — never clamped to 0, which would run no smoothing for someone who
     asked for some.
  7. The parameter reaches the run's own provenance record, so a smoothed mesh
     carries the number that reproduces it.

MEASURED 2026-09-04 on the shipped C-grid (11520 cells, 4 blocks), by this file's
own runs:

    MB_SMOOTH_ITERS   inverted  nonortho max  nonortho mean  wall first cell
    0 (default)              0        32.044°         4.562°           0.44%
    1                        0        89.399°         6.230°          36.61%
    5                        4        89.786°        10.004°         126.45%
    20                      26        89.864°        16.288°         372.84%

    and the O-grid, #80's negative control (9216 cells, already good at 2.25° /
    1.875° / 0.08%):

    1                        0         4.344°         1.882°          53.36%
    5                      184        17.443°         2.111°          87.36%

EVERY COLUMN GETS WORSE, including the two this arc exists to improve. That is
the expected result and it is the deliverable: a plain Laplacian has no way to
trade interior positions for orthogonality AT THE WALL, because it does not know
where the wall is. #80's tickets 2 and 3 are what fix it, and this table is the
baseline they have to beat.

BLIND SPOTS, named rather than papered over:

  * Nothing here runs the solver or the grid converter on a smoothed mesh. At this
    kernel that would be a strange thing to want — the 36.61% wall figure at one
    sweep is a boundary layer this repo would not ask a viscous solver to
    integrate. The acceptance run belongs to the ticket that makes the numbers
    better (#80's own acceptance), and the unsmoothed C-grid's dated run is in
    test_multiblock_cgrid_surface.py.
  * The figures in the table above are a record of one dated run, not something
    this file re-measures. What it asserts is the DIRECTION and a floor, so a
    kernel that quietly stopped moving anything would be caught while a kernel
    that moves things differently is free to.
  * The banner is checked for its two headings and the numbers are read out of the
    machine-readable lines, exactly as the quality gate next door does it: the two
    are built from one report object, and the C++ test pins the report.

Run:  python3 tools/PreProcessor/tests/test_multiblock_smooth_surface.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
sys.path.insert(0, _HERE)
# Imported, not copied: the shipped C-grid config is retargeted by the gate that
# owns it, which also fails loudly if the file stops containing what it rewrites.
from test_multiblock_cgrid_surface import base_config  # noqa: E402
# The ONE parser for the machine-readable quality line, in the gate that owns it.
# The token is matched WITH its trailing space, which is what keeps the unsuffixed
# line and the `_BEFORE` one apart — the whole reason the before line wears a
# suffix rather than an extra field on the existing one.
from test_multiblock_quality_surface import qlines  # noqa: E402
from mesher_bin import mesher_env as _mesher_env  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, name, extra=""):
    stem = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".dat")
    with open(conf, "w", encoding="utf-8") as f:
        f.write(base_config().replace("@STEM@", stem) + extra)
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=900)
    return p.returncode, (p.stdout or "") + (p.stderr or ""), stem


def wrote(stem):
    return [e for e in (".vtk", ".vrt", ".cel", ".bnd")
            if os.path.exists(stem + e)]


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # ── 1. the default is silence ───────────────────────────────────────
        rc0, out0, _ = run(tmp, "plain")
        check("1. the shipped C-grid still meshes at the default (rc=0)", rc0 == 0)
        check("1. ...printing exactly ONE machine-readable quality line",
              len(qlines(out0)) == 1)
        check("1. ...and NO before/after pair, because nothing was smoothed",
              "_BEFORE" not in out0)
        check("1. ...under the heading a gate written before this ticket greps for",
              "[ Multi-block Mesh Quality ]" in out0)
        check("1. ...while the run's provenance record still names the parameter, so "
              "'we ran no sweeps' is recorded rather than assumed",
              "Smoothing Sweeps" in out0 and "(none)" in out0)
        base = qlines(out0)[0] if qlines(out0) else {}

        # ── 2/3/4. one sweep: the pair, and what it cost ────────────────────
        rc1, out1, stem1 = run(tmp, "smooth1", "\nMB_SMOOTH_ITERS 1\n")
        check("2. the same case with one sweep meshes (rc=0)", rc1 == 0)
        before, after = qlines(out1, "_BEFORE"), qlines(out1)
        check("2. ...reporting the mesh BEFORE smoothing", len(before) == 1)
        check("2. ...and the mesh AFTER it", len(after) == 1)
        check("2. ...as two banners a reader can tell apart",
              "[ Multi-block Mesh Quality — before smoothing ]" in out1
              and "— after 1 Laplacian sweep(s) ]" in out1)
        check("2. ...and the BEFORE figures ARE the default run's, number for "
              "number — so the pair is one mesh measured twice, not two runs that "
              f"happen to agree ({before[0] if before else None})",
              bool(before) and before[0] == base)
        if before and after:
            b, a = before[0], after[0]
            check("3. the UNSUFFIXED line describes the mesh AS EXPORTED, so it is "
                  "the one that moved", a != b)
            check(f"3. ...over the same cells ({a.get('cells')})",
                  a.get("cells") == b.get("cells") == 11520)
            check(f"4. THE WALL FIRST CELL GETS WORSE — the known cost of this "
                  f"kernel ({100 * b['wall_first_cell_worst_rel']:.2f}% -> "
                  f"{100 * a['wall_first_cell_worst_rel']:.2f}%)",
                  a["wall_first_cell_worst_rel"] > 10 * b["wall_first_cell_worst_rel"])
            check(f"4. ...and so does non-orthogonality, which is the metric this "
                  f"arc exists to improve ({b['nonortho_max_deg']:.3f} deg -> "
                  f"{a['nonortho_max_deg']:.3f} deg max, "
                  f"{b['nonortho_mean_deg']:.3f} -> {a['nonortho_mean_deg']:.3f} "
                  f"mean)",
                  a["nonortho_max_deg"] > b["nonortho_max_deg"]
                  and a["nonortho_mean_deg"] > b["nonortho_mean_deg"])
            check("4. ...while one sweep still folds NOTHING, so check 5's exit code "
                  "belongs to the sweep count and not to smoothing as such",
                  a["inverted"] == 0)
        check(f"4. ...and the mesh is exported ({wrote(stem1)})",
              wrote(stem1) == [".vtk", ".vrt", ".cel", ".bnd"])
        check("4. ...with the sweep count in the run's provenance record",
              "Smoothing Sweeps     : 1" in out1)

        # ── 5. enough sweeps fold a cell: an ORDINARY inverted mesh ─────────
        rc5, out5, stem5 = run(tmp, "smooth5", "\nMB_SMOOTH_ITERS 5\n")
        check(f"5. a smoothing pass that folds a cell exits with the INVERTED code "
              f"(9), exactly as an unsmoothed fold does, got {rc5}", rc5 == 9)
        check("5. ...with the stable token a script branches on",
              "HYBMESH_ERROR 9 INVERTED" in out5)
        a5 = qlines(out5)
        check(f"5. ...counting the folded cells ({a5[0].get('inverted') if a5 else None})",
              bool(a5) and a5[0]["inverted"] > 0)
        check("5. ...counted on the SMOOTHED mesh, while the before half still "
              "reports the sound one it started from",
              bool(qlines(out5, "_BEFORE"))
              and qlines(out5, "_BEFORE")[0]["inverted"] == 0)
        check(f"5. ...and EXPORTING the mesh anyway, under its ordinary name "
              f"({wrote(stem5)})",
              wrote(stem5) == [".vtk", ".vrt", ".cel", ".bnd"])

        # ── 6. a negative count is refused BY NAME ──────────────────────────
        rcn, outn, stemn = run(tmp, "smoothneg", "\nMB_SMOOTH_ITERS -1\n")
        check(f"6. a negative sweep count is REFUSED, not clamped to 0, got {rcn}",
              rcn != 0)
        check("6. ...naming the key the user has to fix",
              "MB_SMOOTH_ITERS" in outn)
        check(f"6. ...and exporting nothing ({wrote(stemn)})", wrote(stemn) == [])
        check("6. ...as a CONFIG refusal, not a topology one — the .dat is what is "
              "wrong", "HYBMESH_ERROR 2 CONFIG" in outn)

    print()
    if failures:
        print("%d check(s) failed:" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
