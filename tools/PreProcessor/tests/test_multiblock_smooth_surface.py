#!/usr/bin/env python3
"""The multi-block smoothing pass, end to end through the real binary (#81-#83).

The kernel and the control functions are pinned next door in
``tests/cpp/test_multiblock.cpp`` checks 40-55, which link the pure layer alone
and drive ``buildMultiBlock`` with a topology STRING: which nodes move, which are
frozen, that the kernel is the WINSLOW update of a node's nine logical
neighbours with its two source terms (against hand-worked numbers, checks 48 and
52), that a grid whose answer is known comes back unmoved (check 47), that the
wall gate is the DECLARED KIND and the target is the ruler's own blend (51), that
a grid already holding what the declaration asks for is asked for nothing (53),
and that the solve reaches all three of its endings (49). What can only be
checked out here is the half that reaches a user: that ``MB_SMOOTH_ITERS`` travels
from a ``.dat`` into the seam at all, that the run REPORTS what smoothing bought
and whether its solve finished, that the reporting is unchanged when nothing was
smoothed, and #83's acceptance figures on the shipped files.

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
  4. THE WALL FIRST CELL IS HELD, and #82's own check here asserted the opposite
     because it had no control functions to hold it with. All three of #80's
     figures now move the right way at once.
  5. EVERY COLUMN BEATS THE KERNEL #81 SHIPPED, on both shipped cases and at every
     sweep count either ticket measured.
  6. A NEGATIVE sweep count is refused BY NAME with the CONFIG code and exports
     nothing — never clamped to 0, which would run no smoothing for someone who
     asked for some.
  7. THE SOLVE IS BOUNDED AND SAYS WHICH ENDING IT REACHED, and since #83 the two
     shipped cases reach only ONE of the three: they neither converge nor diverge,
     their residual PLATEAUS, and both other endings moved to fixtures next door
     (see group 7's own note — this is a swap in coverage, not a loss of it).
     What is measured here instead is the STABILITY limit, which is #83's, and the
     correction this ticket had to make to its own first reading of the clip count.
  8. The parameter reaches the run's own provenance record, so a smoothed mesh
     carries the number that reproduces it.
  9. WHERE THE O-GRID REGRESSION COMES FROM, measured rather than asserted: the
     four frozen radial interfaces.
 10. #83's ACCEPTANCE on the shipped C-grid, including the near-leading-edge cells
     the ticket asks for specifically.

MEASURED 2026-09-07 by this file's own runs, #83's CONTROLLED Winslow beside #82's
plain one (quoted from that ticket) and #81's Laplacian (quoted from that one):

  shipped C-grid, 11520 cells, unsmoothed 0 inverted / 32.044 deg max /
  4.562 deg mean / 0.4368% wall:

    cap    kernel              inverted  max      mean    wall      clipped
    1      Laplacian (#81)            0  89.399   6.230   36.61%      --
    1      Winslow   (#82)            0  31.438   4.778   11.65%      --
    1      +control  (#83)            0  31.861   4.527    0.1222%    36
    5      Laplacian (#81)            4  89.786  10.004  126.45%      --
    5      Winslow   (#82)            0  29.844   5.627   39.15%      --
    5      +control  (#83)            0  31.382   4.454    0.0805%     8
    20     Laplacian (#81)           26  89.864  16.288  372.84%      --
    20     Winslow   (#82)            0  33.759   8.517  130.77%      --
    20     +control  (#83)            0  29.895   4.301    0.0893%     0
    30     +control  (#83)            0  31.550   4.252    0.0943%     0
    40     +control  (#83)            0  34.784   4.214    0.0980%     0
    100    +control  (#83)            4  86.606   4.710   19.06%       4
    500    +control  (#83)          288  84.927  10.860   99.99%     212
    50000  Winslow   (#82)            0  74.830  29.613  3133.40%     --
           (#82 DIVERGED at ~4900 and returned its best iterate, 3724; #83's
            residual plateaus there instead and the cap runs out)

  shipped O-grid, 9216 cells, unsmoothed 0 inverted / 2.250 / 1.875 / 0.0812%:

    1      Laplacian (#81)            0   4.344   1.882   53.36%      --
    1      Winslow   (#82)            0   3.312   1.875    9.13%      --
    1      +control  (#83)            0   3.632   1.875    0.0390%     0
    5      Laplacian (#81)          184  17.443   2.111   87.36%      --
    5      Winslow   (#82)            0   8.061   1.978   29.13%      --
    5      +control  (#83)            0   6.418   1.980    0.0412%     0
    20     +control  (#83)            0  12.036   2.571    0.0442%     0

  the near-leading-edge region of the shipped C-grid — the ten quad cells touching
  the airfoil between x = 0.005 and 0.030, which is where #57 localised the corner
  that drove the solver to NaN, at (0.0134, 0.0196):

    cap 0   max 32.044 deg   mean 26.895 deg
    cap 1   max 31.861       mean 26.734
    cap 5   max 31.382       mean 26.308
    cap 20  max 29.895       mean 24.909

#80'S ACCEPTANCE FOR THIS TICKET IS MET ON THE C-GRID AND NOT ON THE O-GRID, and
both are asserted rather than summarised:

  * C-grid: max, mean AND wall all better than #57's baseline at the same time,
    inverted still 0, and the near-LE region improving on its own figures rather
    than only through the mesh-wide maximum. Group 10.
  * O-grid: the wall first cell is now BETTER than #55's 0.0812% (0.0390%), and
    max non-orthogonality is still WORSE (2.250 -> 3.632). Recorded as unmet and
    owned by #84, exactly as #82 recorded it — and now LOCALISED rather than
    attributed: the worst corners of the smoothed mesh sit at theta = 0, 90, 180
    and -90 degrees at radius ~3.43, which is mid-block on the four DECLARED
    RADIAL INTERFACES, while the unsmoothed mesh's worst sit at radius 10 on the
    faceted outer circle. The kink is along a frozen shared edge. Group 9.

BLIND SPOTS, named rather than papered over:

  * Nothing here runs the solver or the grid converter on a smoothed mesh. That is
    #80's own acceptance rather than this ticket's, and the unsmoothed C-grid's
    dated run is in test_multiblock_cgrid_surface.py. Unlike #82, a smoothed mesh
    would now be a reasonable thing to hand a viscous solver — 0.09% off the
    requested wall height at twenty sweeps — so this is a gap rather than a
    non-question.
  * The figures in the tables above are a record of one dated run, not something
    this file re-measures. What it asserts is the DIRECTION and a floor, so a
    kernel that quietly stopped moving anything would be caught while a kernel
    that moves things differently is free to.
  * A FOLD FROM SMOOTHING IS REACHABLE ON THESE FILES AGAIN, which reverses #82's
    blind spot here. Under that kernel the shipped cases folded nothing at any cap
    they were driven at; under #83's the C-grid folds 4 cells by a cap of 100 and
    288 by 500, and group 7 asserts the exit-9 path on the real file rather than
    only on a folded declaration elsewhere. That is the cost of holding a graded
    wall through a conditionally stable iteration, and it is measured rather than
    discovered later.
  * NO SYNTHETIC FIXTURE REACHES THE SATURATING-AND-DESCENDING regime that the
    stability limit lives in; the shipped C-grid at a cap of 100 is the only case
    that does, which is why that check is here and not next door.
  * The banner is checked for its headings and the numbers are read out of the
    machine-readable lines, exactly as the quality gate next door does it: the two
    are built from one report object, and the C++ test pins the report. The ONE
    exception is group 9 and 10's own quad reader, and group 10 validates it
    against the C++ ruler's line before trusting it anywhere the ruler does not
    look.

Run:  python3 tools/PreProcessor/tests/test_multiblock_smooth_surface.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import math
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


def quad_corners(vtk_path):
    """Every corner-angle deviation from 90 degrees in a legacy-VTK QUAD mesh.

    THE METRIC IS THE RULER'S, not a new one. `MbQuality` measures
    non-orthogonality as the deviation of a STRUCTURED cell's corner angle from
    90 degrees, and with ``MB_SPLIT_QUADS 0`` the exported cells ARE those cells,
    so this computes the same quantity over the same corners. What it adds is a
    SELECTION — which corners to report — and #80's "no new metric is invented"
    rule is about the metric, not about the filter.

    It lives out here rather than in `MbQuality` because the question it answers
    is about a shipped FILE: "the first cell off the wall around x = 0.017 on the
    NACA 0012". `measureMbQuality` is a pure function of any `MbResult` and has no
    business knowing an airfoil's leading edge. What keeps this from becoming a
    second answer to the same question is that group 10 first checks the
    WHOLE-MESH figures out of this reader against the C++ ruler's own line: an
    instrument that agrees with the ruler everywhere can be trusted where the
    ruler does not look.
    """
    lines = open(vtk_path, encoding="utf-8").read().split("\n")
    i, pts, cells = 0, [], []
    while i < len(lines):
        if lines[i].startswith("POINTS"):
            n = int(lines[i].split()[1])
            i += 1
            vals = []
            while len(vals) < 3 * n:
                vals += lines[i].split()
                i += 1
            pts = [(float(vals[3 * k]), float(vals[3 * k + 1])) for k in range(n)]
            continue
        if lines[i].startswith("CELLS"):
            n = int(lines[i].split()[1])
            i += 1
            for _ in range(n):
                cells.append([int(x) for x in lines[i].split()][1:])
                i += 1
            break
        i += 1
    return pts, [c for c in cells if len(c) == 4]


def devs_of(pts, cells, keep=None):
    """The deviations of the corners of `cells`, optionally only cells touching `keep`."""
    out = []
    for c in cells:
        if keep is not None and not (set(c) & keep):
            continue
        for a in range(4):
            p, q, r = pts[c[a]], pts[c[(a + 1) % 4]], pts[c[(a - 1) % 4]]
            u = (q[0] - p[0], q[1] - p[1])
            v = (r[0] - p[0], r[1] - p[1])
            lu = math.hypot(*u)
            lv = math.hypot(*v)
            if lu == 0 or lv == 0:
                continue
            cs = max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / (lu * lv)))
            out.append(abs(90.0 - math.degrees(math.acos(cs))))
    return out


def on_polyline(pts, poly, tol=1e-9):
    """Which of `pts` lie ON `poly` — a wall node, by distance and not by identity.

    Distance to the SEGMENTS and not to the vertices, because a wall node is
    placed by arc length along the bound polyline and is generally not one of its
    points. Matching vertices instead found 0 of them, which is how this was
    written the first time.
    """
    hit = set()
    for k, p in enumerate(pts):
        best = 1e30
        for a, b in zip(poly, poly[1:]):
            vx, vy = b[0] - a[0], b[1] - a[1]
            l2 = vx * vx + vy * vy
            t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * vx
                                                       + (p[1] - a[1]) * vy) / l2))
            best = min(best, math.hypot(p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy)))
            if best < tol:
                break
        if best < tol:
            hit.add(k)
    return hit


def read_poly(path):
    poly = []
    for ln in open(path, encoding="utf-8"):
        f = ln.split()
        if len(f) >= 2:
            try:
                poly.append((float(f[0]), float(f[1])))
            except ValueError:
                pass
    return poly


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
            check(f"4. THE WALL FIRST CELL IS HELD, and #82's miss is REVERSED — "
                  f"its own text called the control functions ticket 3's job "
                  f"({100 * b['wall_first_cell_worst_rel']:.2f}%"
                  f" -> {100 * a['wall_first_cell_worst_rel']:.2f}%)",
                  a["wall_first_cell_worst_rel"] < b["wall_first_cell_worst_rel"])
            check(f"4. ...while MAX NON-ORTHOGONALITY, the metric #80 exists for, "
                  f"still comes out BELOW the unsmoothed fill's "
                  f"({b['nonortho_max_deg']:.3f} deg -> {a['nonortho_max_deg']:.3f} deg)",
                  a["nonortho_max_deg"] < b["nonortho_max_deg"])
            check(f"4. ...and so does the MEAN, which #82 recorded as the one figure "
                  f"that got worse "
                  f"({b['nonortho_mean_deg']:.3f} -> {a['nonortho_mean_deg']:.3f})",
                  a["nonortho_mean_deg"] < b["nonortho_mean_deg"])
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
              "warning naming the key — and the ADVICE is #83's, not #82's: the "
              "declared wall height is held while the cap rises, so the sentence "
              "about a converged solve relaxing to the harmonic map is gone",
              s1.get("converged") == 0 and s1.get("diverged") == 0
              and "MB_SMOOTH_ITERS" in out1
              and "the declared wall height is held" in out1
              and "a CONVERGED solve is not the goal at this kernel" not in out1)
        check("7. ...bounded by STABILITY rather than by the kernel's limit, which "
              "is what replaced that sentence: raise it only while the "
              "inverted-cell count stays 0",
              "inverted-cell count stays 0" in out1)
        check(f"7. ...and it names the BEST iterate beside the exported one, which "
              f"at a small cap is the same sweep ({s1.get('best_sweep')})",
              s1.get("best_sweep") == s1.get("sweeps")
              and s1.get("best_residual") == s1.get("residual"))
        # THE CLIP COUNT IS A DIRECTION, NOT A THRESHOLD, and this file is where
        # that was found. The obvious reading — clipping means trouble — is wrong on
        # this very case: at a cap of one the control is clipped at 36 nodes and the
        # mesh is sound, because the algebraic fill starts far from the wall
        # condition and the count FALLS as the solve catches up (36, 28, 8, 0 over
        # the first ten sweeps, measured 2026-09-07). It is the climb back off zero
        # that goes with the folds. So what is asserted is the DIRECTION and the
        # sentence that tells the reader which way to read it.
        s5 = smooth_line(run(tmp, "c5b", "\nMB_SMOOTH_ITERS 5\n")[1])
        s10 = smooth_line(run(tmp, "c10b", "\nMB_SMOOTH_ITERS 10\n")[1])
        check(f"7. ...and the SATURATION COUNT falls as the solve catches up with "
              f"the wall it was told to hold, from a mesh that is sound at every "
              f"step ({s1.get('clipped')} -> {s5.get('clipped')} -> "
              f"{s10.get('clipped')})",
              s1.get("clipped", -1) > s5.get("clipped", -1) > s10.get("clipped", -1)
              == 0)
        check("7. ...which is why the advice gives it as a direction rather than as "
              "a threshold to clear",
              "a direction rather than a threshold" in out1)
        check("7. ...with the banner saying so in words, not only in the token",
              "[ Multi-block Elliptic Smoothing ]" in out1
              and re.search(r"Converged\s+: NO", out1) is not None)
        # A CAP REACHED PAST THE TURN is a different answer from a cap reached on
        # the way down, and #82's review is the reason it is told apart: the flags
        # alone cannot distinguish them — both are `converged=0 diverged=0`.
        _, outt, _ = run(tmp, "turned", "\nMB_SMOOTH_ITERS 4000\n")
        st = smooth_line(outt)
        check(f"7. a cap reached PAST the solve's best iterate is reported as such, "
              f"not as a solve with more to give ({st})",
              st.get("converged") == 0 and st.get("diverged") == 0
              and st.get("best_sweep", 0) < st.get("sweeps", 0)
              and st.get("best_residual", 1) < st.get("residual", 0))
        check("7. ...and the advice turns over with it: the iteration has TURNED, so "
              "raising the cap makes the mesh worse rather than more converged",
              "the iteration has turned" in outt
              and "PAST ITS BEST" in outt)
        check("7. ...while the mesh returned is still the LAST iterate, because N "
              "sweeps has to mean N sweeps outside the diverged path",
              st.get("sweeps") == 4000)

        # #83's STABILITY LIMIT, and this file is the only place it is measured.
        # The control functions hold the wall, but the lagged-coefficient iteration
        # is only conditionally stable and holding a graded wall is what it
        # eventually loses the condition on. Measured 2026-09-07 on this file: 0
        # folded cells at every cap through 40, then 4 at 100 and 288 at 500, with
        # the clip count climbing back off zero alongside them (0 at 40, 4 at 100,
        # 212 at 500). The run reports it through machinery that already exists —
        # the inverted-cell count and exit 9 — which is why the capped warning
        # points at that rather than at a second signal.
        rcs, outs, _ = run(tmp, "satur", "\nMB_SMOOTH_ITERS 100\n")
        ss = smooth_line(outs)
        aq = qlines(outs)
        check(f"7. the shipped C-grid at a cap of 100 is still DESCENDING and yet "
              f"has FOLDED cells — the stability limit, not a turn ({ss})",
              ss.get("converged") == 0 and ss.get("diverged") == 0
              and ss.get("best_sweep") == ss.get("sweeps") == 100)
        check(f"7. ...reported by the machinery that already exists: the inverted "
              f"count and exit 9 (inverted {aq[0]['inverted'] if aq else None}, "
              f"rc={rcs})",
              bool(aq) and aq[0]["inverted"] > 0 and rcs == 9)
        check(f"7. ...with the clip count climbing back off the zero it reached by "
              f"sweep 10, which is the direction the warning tells the reader to "
              f"watch ({ss.get('clipped')})",
              ss.get("clipped", 0) > 0)

        # THE OTHER TWO ENDINGS MOVED HOUSE, and that is a swap in coverage rather
        # than a loss of it. Under #82's kernel the shipped C-grid DIVERGED at a cap
        # of 50000 and the shipped O-grid CONVERGED at 20000, so this file was the
        # only gate on both — that ticket tried 26 synthetic fixtures and every one
        # converged. Since #83 neither shipped case does either: the residual
        # plateaus instead, at 6.8e-05 on the C-grid at 50000 (best 2.5e-05 at sweep
        # 415, a factor of 2.7 and so short of MB_SMOOTH_DIVERGE_FACTOR) and at
        # 1.2e-04 on the O-grid at 20000. Both endings are now driven in
        # tests/cpp/test_multiblock.cpp check 49, in milliseconds, on a notched box
        # whose depth picks the ending — 0.50 converges in 290 sweeps, 0.35 diverges
        # at 9 — and the ROLLBACK is checked there the same way it was checked here:
        # a run capped at the reported sweep must give the same mesh, bit for bit.
        # What stays here is the plateau, because it is a property of the real files.
        _, outp, _ = run(tmp, "plateau", "\nMB_SMOOTH_ITERS 50000\n")
        sp = smooth_line(outp)
        check(f"7. the shipped C-grid neither converges nor diverges at a cap of "
              f"50000 — its residual PLATEAUS, which is why the two endings are now "
              f"gated on fixtures next door ({sp})",
              sp.get("converged") == 0 and sp.get("diverged") == 0
              and sp.get("sweeps") == 50000
              and 1.0 < sp.get("residual", 0) / max(sp.get("best_residual", 1), 1e-30)
                      < 10.0)

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
        # #82 localised this through the run's own wall table: the wall row was
        # pinned at the declared height where a frozen radial interface held it and
        # drifted 9.13% in between, so the kink was ON the wall. Since #83 the wall
        # row is held ALL the way round — that table now reads 0.00% everywhere,
        # which is the ticket working — so the kink has moved off the wall and the
        # table can no longer find it. This group therefore measures the corners
        # directly, with the reader group 10 validates against the C++ ruler.
        #
        # MEASURED 2026-09-07, and it is not a guess: the worst corners of the
        # smoothed O-grid sit at theta = 0, 90, 180 and -90 degrees and at radius
        # ~3.43, while the UNSMOOTHED mesh's worst sit at radius 10.0. Those four
        # angles are exactly where the topology declares its four radial interfaces
        # (r0..r3, corners b0..b3 to f0..f3), and the radius is mid-block rather
        # than at either boundary. So the smoother's cost is a kink along a FROZEN
        # SHARED EDGE, which is #84's ticket and #80's user story 3.
        oq = "\nMB_SPLIT_QUADS 0\n"
        _, _, oqs0 = run(tmp, "oq0", oq, config=ogrid_config)
        _, _, oqs1 = run(tmp, "oq1", oq + "\nMB_SMOOTH_ITERS 1\n", config=ogrid_config)
        wall_tab = [l for l in outo1.splitlines() if "west 'w0'" in l]
        check(f"9. the O-grid's wall row is now held at its declared height ALL the "
              f"way round, so #82's own localisation no longer works "
              f"({wall_tab[-1].strip() if wall_tab else None})",
              len(wall_tab) == 2 and "(0.0" in wall_tab[-1])
        for stem, label, want_r in ((oqs0, "unsmoothed", 10.0), (oqs1, "smoothed", 3.43)):
            pts, cells = quad_corners(stem + ".vtk")
            worst, at = 0.0, None
            for c in cells:
                for k in range(4):
                    p, q, r = pts[c[k]], pts[c[(k + 1) % 4]], pts[c[(k - 1) % 4]]
                    u = (q[0] - p[0], q[1] - p[1])
                    v = (r[0] - p[0], r[1] - p[1])
                    lu, lv = math.hypot(*u), math.hypot(*v)
                    if lu == 0 or lv == 0:
                        continue
                    cs = max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / (lu * lv)))
                    d = abs(90.0 - math.degrees(math.acos(cs)))
                    if d > worst:
                        worst, at = d, p
            rad = math.hypot(*at) if at else -1.0
            ang = math.degrees(math.atan2(at[1], at[0])) if at else 999.0
            onradial = min(abs(ang - t) for t in (-180, -90, 0, 90, 180))
            check(f"9. ...the {label} O-grid's worst corner is {worst:.3f} deg at "
                  f"r={rad:.3f}, theta={ang:.2f} (expected r near {want_r})",
                  abs(rad - want_r) < 0.05)
            if label == "smoothed":
                check(f"9. ...and that theta is one of the four DECLARED RADIAL "
                      f"INTERFACES, to {onradial:.4f} deg — the kink is along a "
                      f"frozen shared edge and #84 is the ticket that unfreezes it",
                      onradial < 1e-6)

        # ── 10. #83's OWN ACCEPTANCE, on the shipped C-grid ─────────────────
        #
        # #80's criterion for this ticket: max and mean non-orthogonality BETTER
        # than #57's recorded 32.04 / 4.56, wall first-cell accuracy NO WORSE than
        # its 0.44%, inverted still 0 — "both improving at once is the whole claim;
        # one at the cost of the other is not". Measured at the cap where the
        # combination is best.
        #
        # AND THE NEAR-LEADING-EDGE CELLS SPECIFICALLY, which the ticket asks for in
        # as many words: "the first cell off the wall around x = 0.017 on the
        # shipped C-grid are measured specifically, not only through the whole-mesh
        # maximum. That is the region the solver diverged in, and a mesh-wide
        # average can improve while it does not." So the region's own max AND mean
        # are read, over the ten quad cells that touch the airfoil between x = 0.005
        # and x = 0.030 — #57's worst corner is at (0.0134, 0.0196), inside it.
        #
        # THE INSTRUMENT IS VALIDATED FIRST. The whole-mesh figures out of this
        # reader are compared against the C++ ruler's own machine-readable line, so
        # the region figure is trusted because the same code agrees with the ruler
        # where the ruler looks.
        CAP83 = 20
        base_q, outq0, qs0 = run(tmp, "q0", "\nMB_SPLIT_QUADS 0\n")
        _, out83, qs1 = run(tmp, "q83",
                            "\nMB_SPLIT_QUADS 0\nMB_SMOOTH_ITERS %d\n" % CAP83)
        u83 = qlines(out83, "_BEFORE")
        a83 = qlines(out83)
        check(f"10. the shipped C-grid at a cap of {CAP83} meshes as quads "
              f"(rc={base_q})", base_q == 0 and bool(a83))
        if u83 and a83:
            check(f"10. MAX non-orthogonality is BETTER than #57's baseline "
                  f"({u83[0]['nonortho_max_deg']:.3f} -> "
                  f"{a83[0]['nonortho_max_deg']:.3f} deg)",
                  a83[0]["nonortho_max_deg"] < u83[0]["nonortho_max_deg"] < 32.05)
            check(f"10. ...the MEAN is better AT THE SAME TIME, which is the whole "
                  f"claim ({u83[0]['nonortho_mean_deg']:.3f} -> "
                  f"{a83[0]['nonortho_mean_deg']:.3f} deg)",
                  a83[0]["nonortho_mean_deg"] < u83[0]["nonortho_mean_deg"] < 4.57)
            check(f"10. ...the wall first cell is NO WORSE than its 0.44%, and is in "
                  f"fact better ({100 * u83[0]['wall_first_cell_worst_rel']:.4f}% -> "
                  f"{100 * a83[0]['wall_first_cell_worst_rel']:.4f}%)",
                  a83[0]["wall_first_cell_worst_rel"]
                  <= u83[0]["wall_first_cell_worst_rel"])
            check(f"10. ...and inverted cells are still 0 "
                  f"({a83[0]['inverted']})", a83[0]["inverted"] == 0)
        pts0, cells0 = quad_corners(qs0 + ".vtk")
        pts1, cells1 = quad_corners(qs1 + ".vtk")
        all0, all1 = devs_of(pts0, cells0), devs_of(pts1, cells1)
        # ON BOTH MESHES, because the regional comparison below reads both and an
        # instrument validated on one of them is validated on neither. It also pins
        # the claim MB_SPLIT_QUADS rests on: non-orthogonality is measured on the
        # STRUCTURED cells either way, so the quad run must report the figure the
        # triangle run does.
        q0line = qlines(outq0)
        for label, devs, line in (("unsmoothed", all0, q0line[0] if q0line else {}),
                                  ("smoothed", all1, a83[0] if a83 else {})):
            check(f"10. THE INSTRUMENT AGREES WITH THE RULER on the whole "
                  f"{label} mesh, which is what makes its regional figure worth "
                  f"reading (reader max {max(devs) if devs else -1:.6f} deg vs line "
                  f"{line.get('nonortho_max_deg', -1):.6f})",
                  bool(devs) and bool(line)
                  and abs(max(devs) - line["nonortho_max_deg"]) < 1e-4
                  and abs(sum(devs) / len(devs) - line["nonortho_mean_deg"]) < 1e-4)
        check(f"10. ...and the QUAD run reports the same non-orthogonality as the "
              f"triangle run, so measuring on quads is not a different question "
              f"({q0line[0]['nonortho_max_deg'] if q0line else None} vs "
              f"{base.get('nonortho_max_deg')})",
              bool(q0line) and bool(base)
              and q0line[0]["nonortho_max_deg"] == base["nonortho_max_deg"]
              and q0line[0]["nonortho_mean_deg"] == base["nonortho_mean_deg"])
        poly = read_poly(os.path.join(_REPO, "examples", "geometries",
                                      "naca0012_cgrid.dat"))
        le0 = on_polyline(pts0, poly)
        le1 = on_polyline(pts1, poly)
        le0 = {k for k in le0 if 0.005 <= pts0[k][0] <= 0.030}
        le1 = {k for k in le1 if 0.005 <= pts1[k][0] <= 0.030}
        r0, r1 = devs_of(pts0, cells0, le0), devs_of(pts1, cells1, le1)
        check(f"10. the near-leading-edge region is found on both meshes and is the "
              f"same region ({len(le0)} wall nodes, {len(r0)} corners)",
              len(le0) == len(le1) > 0 and len(r0) == len(r1) > 0)
        if r0 and r1:
            check(f"10. ...and #57's OWN REGION improves, not just the mesh-wide "
                  f"maximum: max {max(r0):.3f} -> {max(r1):.3f} deg",
                  max(r1) < max(r0))
            check(f"10. ...including its MEAN, which a whole-mesh average could have "
                  f"hidden: {sum(r0)/len(r0):.3f} -> {sum(r1)/len(r1):.3f} deg",
                  sum(r1) / len(r1) < sum(r0) / len(r0))

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
