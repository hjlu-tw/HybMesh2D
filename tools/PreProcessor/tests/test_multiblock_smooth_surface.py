#!/usr/bin/env python3
"""The multi-block smoothing pass, end to end through the real binary (#81, #82).

The kernel itself is pinned next door in ``tests/cpp/test_multiblock.cpp`` checks
40-50, which link the pure layer alone and drive ``buildMultiBlock`` with a
topology STRING: which nodes move, which are frozen, that the kernel is the
WINSLOW update of a node's nine logical neighbours (against hand-worked numbers,
check 48), that a grid whose answer is known comes back unmoved (check 47), and
that the solve stops when it has converged (check 49). What can only be checked
out here is the half that reaches a user: that ``MB_SMOOTH_ITERS`` travels from a
``.dat`` into the seam at all, that the run REPORTS what smoothing bought and
whether its solve finished, and that the reporting is unchanged when nothing was
smoothed.

Driven on the SHIPPED C-grid (``config/multiblock_cgrid.dat``) and the SHIPPED
O-grid (``config/multiblock_ogrid.dat``), read from disk through the gates that
own them rather than composed here — the same rule the golden comparator follows:
these files are documentation a user runs, and an edit to one has to be visible
from a gate.

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
  4. THE WALL FIRST CELL IS STILL WORSE, and by how much is recorded rather than
     glossed. Plain Winslow relaxes toward the harmonic map of each block, which
     has no memory of the height the declaration asked for; the control functions
     that hold it are #80's ticket 3. What DID change is the metric #80 is aimed
     at: max non-orthogonality now comes out BELOW the unsmoothed fill's.
  5. EVERY COLUMN BEATS THE KERNEL #81 SHIPPED, on both shipped cases and at every
     sweep count either ticket measured. That is #82's deliverable and it is a
     table, not a prediction.
  6. A NEGATIVE sweep count is refused BY NAME with the CONFIG code and exports
     nothing — never clamped to 0, which would run no smoothing for someone who
     asked for some.
  7. THE SOLVE IS BOUNDED AND SAYS WHICH OF ITS THREE ENDINGS IT REACHED —
     converged, capped, or diverged — and a diverging one returns the BEST
     iterate rather than the last. This is the ONLY gate on the divergence path:
     no synthetic fixture in the C++ test reproduces it (26 were tried, see that
     file's check 49), and the case that does is the shipped C-grid.
  8. The parameter reaches the run's own provenance record, so a smoothed mesh
     carries the number that reproduces it.

MEASURED 2026-09-04 by this file's own runs, WINSLOW beside the #81 LAPLACIAN it
replaced (quoted from that ticket, not re-measured — the Laplacian is deleted):

  shipped C-grid, 11520 cells, unsmoothed 0 inverted / 32.044 deg max /
  4.562 deg mean / 0.44% wall:

    cap        kernel      inverted  nonortho max  nonortho mean  wall first cell
    1          Laplacian          0        89.399         6.230           36.61%
    1          Winslow            0        31.438         4.778           11.65%
    5          Laplacian          4        89.786        10.004          126.45%
    5          Winslow            0        29.844         5.627           39.15%
    20         Laplacian         26        89.864        16.288          372.84%
    20         Winslow            0        33.759         8.517          130.77%
    50000      Winslow            0        74.830        29.613         3133.40%
               (DIVERGED at sweep 4900-ish; the mesh is the best iterate, 3724)

  shipped O-grid, 9216 cells, unsmoothed 0 inverted / 2.250 / 1.875 / 0.08%:

    1          Laplacian          0         4.344         1.882           53.36%
    1          Winslow            0         3.312         1.875            9.13%
    5          Laplacian        184        17.443         2.111           87.36%
    5          Winslow            0         8.061         1.978           29.13%
    20000      Winslow            0        56.756        13.669         1382.50%
               (CONVERGED at sweep 2110)

EVERY WINSLOW ROW BEATS THE LAPLACIAN ROW BESIDE IT, on every column, on both
cases. Max non-orthogonality on the C-grid also beats the UNSMOOTHED fill, which
is the metric #80 exists for. Two things it does not fix, both #80's later
tickets and both measured above rather than argued:

  * the wall first cell, which is #83's control functions; and
  * #82's own negative control, which this work DOES NOT MEET: the O-grid's max
    non-orthogonality goes 2.250 -> 3.312 at one sweep. Where that comes from is
    visible in the run's own wall table and is localised in group 9 below: the
    wall row is pinned exactly where a frozen radial interface holds it and
    drifts 9.13% in the middle of each block, so what the smoother introduces is
    a KINK AT THE FROZEN INTERFACE. Unfreezing those is #80's ticket 4 (#84),
    which is also user story 3. Recorded as unmet, with the ticket that owns it.

BLIND SPOTS, named rather than papered over:

  * Nothing here runs the solver or the grid converter on a smoothed mesh. At this
    kernel that would still be a strange thing to want — 11.65% off the requested
    wall height at one sweep is not a boundary layer this repo would ask a viscous
    solver to integrate. The acceptance run belongs to #80's own acceptance, and
    the unsmoothed C-grid's dated run is in test_multiblock_cgrid_surface.py.
  * The figures in the tables above are a record of one dated run, not something
    this file re-measures. What it asserts is the DIRECTION and a floor, so a
    kernel that quietly stopped moving anything would be caught while a kernel
    that moves things differently is free to.
  * A FOLD FROM SMOOTHING IS NO LONGER REACHABLE ON THESE FILES. Under #81's
    Laplacian the shipped C-grid folded 4 cells at 5 sweeps and 26 at 20, and
    group 5 of this file used to assert exit 9 on it. Under Winslow it folds
    nothing at any cap either shipped case is driven at. The exit-9 path is
    unchanged code and is still gated — on a folded DECLARATION in
    test_multiblock_quality_surface.py group 4, and on a clustered C-grid the
    smoother does fold in tests/cpp/test_multiblock.cpp check 46 — but no longer
    from smoothing on a shipped file, which is why this file asserts the ZERO
    instead and says why the assertion turned over.
  * The banner is checked for its headings and the numbers are read out of the
    machine-readable lines, exactly as the quality gate next door does it: the two
    are built from one report object, and the C++ test pins the report.

Run:  python3 tools/PreProcessor/tests/test_multiblock_smooth_surface.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
sys.path.insert(0, _HERE)
# Imported, not copied: each shipped config is retargeted by the gate that owns
# it, which also fails loudly if the file stops containing what it rewrites.
from test_multiblock_cgrid_surface import base_config  # noqa: E402
from test_multiblock_ogrid_surface import base_config as ogrid_config  # noqa: E402
# The ONE parser for the machine-readable quality line, in the gate that owns it.
# The token is matched WITH its trailing space, which is what keeps the unsuffixed
# line and the `_BEFORE` one apart — the whole reason the before line wears a
# suffix rather than an extra field on the existing one.
from test_multiblock_quality_surface import qlines  # noqa: E402
from mesher_bin import mesher_env as _mesher_env  # noqa: E402

# The #81 LAPLACIAN figures, quoted from that ticket rather than re-measured: the
# kernel is deleted, so there is nothing left to measure them on. Keyed by
# (case, cap) -> (inverted, nonortho max, nonortho mean, wall first cell fraction).
LAPLACIAN_2026_09_04 = {
    ("cgrid", 1):  (0, 89.399, 6.230, 0.3661),
    ("cgrid", 5):  (4, 89.786, 10.004, 1.2645),
    ("cgrid", 20): (26, 89.864, 16.288, 3.7284),
    ("ogrid", 1):  (0, 4.344, 1.882, 0.5336),
    ("ogrid", 5):  (184, 17.443, 2.111, 0.8736),
}

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, name, extra="", config=None):
    stem = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".dat")
    text = (config or base_config)()
    with open(conf, "w", encoding="utf-8") as f:
        f.write(text.replace("@STEM@", stem) + extra)
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=900)
    return p.returncode, (p.stdout or "") + (p.stderr or ""), stem


def wrote(stem):
    return [e for e in (".vtk", ".vrt", ".cel", ".bnd")
            if os.path.exists(stem + e)]


def smooth_line(out):
    """The one HYBMESH_MB_SMOOTH line, as a dict, or {} when no sweep ran.

    Parsed here rather than beside `qlines` because it is a different line with a
    different owner: `qlines` reports the MESH and this reports the SOLVE, and a
    run can have the first without the second.
    """
    hit = [l for l in out.splitlines() if l.startswith("HYBMESH_MB_SMOOTH ")]
    if len(hit) != 1:
        return {}
    out_ = {}
    for tok in hit[0].split()[1:]:
        k, _, v = tok.partition("=")
        out_[k] = float(v) if ("." in v or "e" in v) else int(v)
    return out_


def beats_laplacian(case, cap, a):
    """Every column of `a` at least as good as #81's Laplacian on the same run."""
    inv, mx, mean, wall = LAPLACIAN_2026_09_04[(case, cap)]
    return (a["inverted"] <= inv and a["nonortho_max_deg"] < mx
            and a["nonortho_mean_deg"] < mean
            and a["wall_first_cell_worst_rel"] < wall)


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
        check("1. ...nor a line about a solve that never ran", smooth_line(out0) == {})
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
              and "— after 1 Winslow sweep(s) ]" in out1)
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
            check(f"4. THE WALL FIRST CELL IS STILL WORSE — the cost #83's control "
                  f"functions are what remove ({100 * b['wall_first_cell_worst_rel']:.2f}%"
                  f" -> {100 * a['wall_first_cell_worst_rel']:.2f}%)",
                  a["wall_first_cell_worst_rel"] > 10 * b["wall_first_cell_worst_rel"])
            check(f"4. ...while MAX NON-ORTHOGONALITY, the metric #80 exists for, "
                  f"now comes out BELOW the unsmoothed fill's "
                  f"({b['nonortho_max_deg']:.3f} deg -> {a['nonortho_max_deg']:.3f} deg)",
                  a["nonortho_max_deg"] < b["nonortho_max_deg"])
            check(f"4. ...and the MEAN does not, which is the wall region drifting "
                  f"and is recorded rather than glossed "
                  f"({b['nonortho_mean_deg']:.3f} -> {a['nonortho_mean_deg']:.3f})",
                  a["nonortho_mean_deg"] > b["nonortho_mean_deg"])
            check("4. ...while one sweep folds NOTHING", a["inverted"] == 0)
        check(f"4. ...and the mesh is exported ({wrote(stem1)})",
              wrote(stem1) == [".vtk", ".vrt", ".cel", ".bnd"])
        check("4. ...with the sweep count in the run's provenance record, naming the "
              "kernel and saying the number is a CAP",
              "Smoothing Sweeps     : 1" in out1 and "Winslow elliptic" in out1)

        # ── 5. every column beats the kernel #81 shipped ────────────────────
        for cap in (1, 5, 20):
            rcw, outw, stemw = run(tmp, "c%d" % cap, "\nMB_SMOOTH_ITERS %d\n" % cap)
            a = qlines(outw)
            lap = LAPLACIAN_2026_09_04[("cgrid", cap)]
            check(f"5. the shipped C-grid at {cap} sweep(s) meshes and exports "
                  f"(rc={rcw})", rcw == 0 and wrote(stemw) == [".vtk", ".vrt",
                                                              ".cel", ".bnd"])
            check(f"5. ...and beats #81's Laplacian on EVERY column at the same cap "
                  f"— Laplacian {lap}, Winslow "
                  f"({a[0]['inverted'] if a else None}, "
                  f"{a[0]['nonortho_max_deg'] if a else None}, "
                  f"{a[0]['nonortho_mean_deg'] if a else None}, "
                  f"{a[0]['wall_first_cell_worst_rel'] if a else None})",
                  bool(a) and beats_laplacian("cgrid", cap, a[0]))
            check(f"5. ...folding NOTHING where that kernel folded {lap[0]} — the "
                  f"reason group 5 no longer asserts exit 9 (got "
                  f"{a[0]['inverted'] if a else None})",
                  bool(a) and a[0]["inverted"] == 0)

        # ── 6. a negative count is refused BY NAME ──────────────────────────
        rcn, outn, stemn = run(tmp, "smoothneg", "\nMB_SMOOTH_ITERS -1\n")
        check(f"6. a negative sweep count is REFUSED, not clamped to 0, got {rcn}",
              rcn != 0)
        check("6. ...naming the key the user has to fix",
              "MB_SMOOTH_ITERS" in outn)
        check(f"6. ...and exporting nothing ({wrote(stemn)})", wrote(stemn) == [])
        check("6. ...as a CONFIG refusal, not a topology one — the .dat is what is "
              "wrong", "HYBMESH_ERROR 2 CONFIG" in outn)

        # ── 7. the solve is bounded, and says which ending it reached ───────
        s1 = smooth_line(out1)
        check(f"7. a solve reports its sweeps, its cap and its residual ({s1})",
              s1.get("sweeps") == 1 and s1.get("cap") == 1
              and s1.get("residual", 0) > 0)
        check("7. ...and a cap of one has NOT converged, in the line and in a "
              "warning naming the key to raise",
              s1.get("converged") == 0 and s1.get("diverged") == 0
              and "MB_SMOOTH_ITERS to finish the solve" in out1)
        check("7. ...with the banner saying so in words, not only in the token",
              "[ Multi-block Elliptic Smoothing ]" in out1
              and re.search(r"Converged\s+: NO", out1) is not None)
        # The DIVERGING ending, on the case that actually does it.
        rcd, outd, stemd = run(tmp, "diverge", "\nMB_SMOOTH_ITERS 50000\n")
        sd = smooth_line(outd)
        check(f"7. the shipped C-grid at a cap of 50000 DIVERGES rather than "
              f"converging — the lagged-coefficient point iteration is only "
              f"conditionally stable ({sd})",
              sd.get("diverged") == 1 and sd.get("converged") == 0)
        check(f"7. ...stopping at the BEST iterate instead of running the cap out "
              f"(sweeps {sd.get('sweeps')} of {sd.get('cap')})",
              0 < sd.get("sweeps", 0) < 50000)
        check("7. ...saying DIVERGED in as many words, because a mesh that got "
              "worse the longer it was worked on must not read as a converged one",
              "DIVERGED" in outd)
        ad = qlines(outd)
        check(f"7. ...and the mesh it kept has no folded cell, where running the cap "
              f"out had 136 (got {ad[0]['inverted'] if ad else None})",
              bool(ad) and ad[0]["inverted"] == 0)
        check(f"7. ...and is exported ({wrote(stemd)})",
              wrote(stemd) == [".vtk", ".vrt", ".cel", ".bnd"])
        # THE ROLLBACK IS REAL, and this is the only check that says so. Re-running
        # at exactly the sweep count the diverged run REPORTS must produce the same
        # mesh: if the rollback kept the sweep number but returned the last iterate
        # (or the other way round), these two disagree. Injections G and I, dated in
        # tests/cpp/test_multiblock.cpp, are both inert against every other check in
        # this file and are caught here.
        _, outr, _ = run(tmp, "rollback",
                         "\nMB_SMOOTH_ITERS %d\n" % int(sd.get("sweeps", 0)))
        ar = qlines(outr)
        check(f"7. ...and the mesh returned IS the iterate it names: re-running at "
              f"its reported {sd.get('sweeps')} sweeps gives the same mesh, number "
              f"for number", bool(ar) and bool(ad) and ar[0] == ad[0])
        sr = smooth_line(outr)
        check(f"7. ...and that re-run stops AT its cap without diverging, which is "
              f"what makes the reported number the best iterate's own sweep rather "
              f"than the sweep divergence was noticed on ({sr})",
              sr.get("diverged") == 0 and sr.get("sweeps") == sd.get("sweeps"))

        # ── 8. the O-grid: #80's negative control, and it is NOT met ────────
        rco0, outo0, _ = run(tmp, "o0", config=ogrid_config)
        rco1, outo1, _ = run(tmp, "o1", "\nMB_SMOOTH_ITERS 1\n", config=ogrid_config)
        bo, ao = qlines(outo1, "_BEFORE"), qlines(outo1)
        check(f"8. the shipped O-grid meshes with and without smoothing "
              f"(rc={rco0}/{rco1})", rco0 == 0 and rco1 == 0)
        check("8. ...over 9216 cells, unsmoothed at #55's recorded figures",
              bool(bo) and bo[0]["cells"] == 9216
              and abs(bo[0]["nonortho_max_deg"] - 2.250) < 0.01)
        check(f"8. ...and every column beats #81's Laplacian at the same cap "
              f"(Laplacian {LAPLACIAN_2026_09_04[('ogrid', 1)]})",
              bool(ao) and beats_laplacian("ogrid", 1, ao[0]))
        check(f"8. BUT #80's NEGATIVE CONTROL IS NOT MET: a case already at 2.250 "
              f"deg max comes out at "
              f"{ao[0]['nonortho_max_deg'] if ao else None} deg. Recorded as unmet "
              f"and owned by #84, not asserted away — if this ever starts passing, "
              f"delete the check and say so in #80.",
              bool(ao) and ao[0]["nonortho_max_deg"] > bo[0]["nonortho_max_deg"])

        # ── 9. WHERE that regression comes from: the frozen interface ───────
        #
        # The run's own wall table localises it without a second instrument. Each
        # of the four blocks' west sides is a quarter of the circular wall, and its
        # two ends are the frozen radial interfaces. Unsmoothed, the first cell is
        # the same height all the way round. After one sweep the MINIMUM is exactly
        # the declared height — held there by the frozen ends — while the MAXIMUM
        # has drifted. A wall row pinned at four points and lifted between them is
        # a kink, and a kink is what the max non-orthogonality above is reporting.
        west = [l for l in outo1.splitlines() if "west 'w0'" in l]
        check(f"9. the O-grid's wall row after smoothing is PINNED at its declared "
              f"height and drifts away from it in between — the frozen interface, "
              f"which is #84's ticket ({west[-1].strip() if west else None})",
              len(west) == 2
              and "got 1.000e-03 .. 1.09" in west[-1]
              and "got 9.992e-04 .. 1.000e-03" in west[0])
        # And the O-grid is the case that CONVERGES, so both endings are driven on
        # shipped files rather than one on a fixture.
        _, outoc, _ = run(tmp, "oc", "\nMB_SMOOTH_ITERS 20000\n", config=ogrid_config)
        so = smooth_line(outoc)
        check(f"9. ...and the same O-grid CONVERGES when it is allowed to, so this "
              f"gate drives all three endings on shipped files ({so})",
              so.get("converged") == 1 and so.get("diverged") == 0
              and 0 < so.get("sweeps", 0) < 20000)

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
