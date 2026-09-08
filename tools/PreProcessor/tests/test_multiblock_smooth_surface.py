#!/usr/bin/env python3
"""The multi-block smoothing pass, end to end through the real binary (#81-#84).

The kernel, the control functions and the freeze rule are pinned next door in
``tests/cpp/test_multiblock.cpp`` checks 40-56, which link the pure layer alone
and drive ``buildMultiBlock`` with a topology STRING: which nodes move and which
are frozen (41), that the kernel is the WINSLOW update of a node's nine logical
neighbours with its two source terms (against hand-worked numbers, checks 48 and
52), that a grid whose answer is known comes back unmoved (47), that the wall gate
is the DECLARED KIND and the target is the ruler's own blend (51), that a grid
already holding what the declaration asks for is asked for nothing (53), that the
solve reaches all three of its endings (49), and — since #84 — that a shared node
is moved ONCE by IDENTITY, that the ghost layer IS the neighbour's own first
interior line, that either block would compute the same position from it, and that
the four-way corner does not move (56). What can only be checked out here is the
half that reaches a user: that ``MB_SMOOTH_ITERS`` travels from a ``.dat`` into the
seam at all, that the run REPORTS what smoothing bought, which nodes it was free to
move and whether its solve finished, that the reporting is unchanged when nothing
was smoothed, and #83's and #84's acceptance figures on the shipped files.

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
  7. THE SOLVE IS BOUNDED AND SAYS WHICH ENDING IT REACHED, and #84 moved which
     endings the shipped files reach: the C-grid DIVERGES again (at sweep 1111,
     returning that best iterate) where under #83 its residual merely plateaued,
     and its stability limit moved OUT — 0 folded cells at a cap of 100 and 150
     where #83 folded 4 at 100, first folds at 400.
  8. #80's O-GRID NEGATIVE CONTROL: still not met, and now by 1.2% instead of 5.3x.
  9. THE INTERFACES ARE NO LONGER THE KINK, measured on the mid-block radial band's
     own cells and on where the whole mesh's worst corner sits.
 10. #83's ACCEPTANCE on the shipped C-grid, including the near-leading-edge cells
     that ticket asks for specifically.
 11. #84's OWN DELIVERABLES: the freeze rule reported rather than inferred, node
     and cell counts unchanged, the mesh still CONFORMAL by #53's measure, and the
     wake cut measured on its own terms.

MEASURED 2026-09-07 by this file's own runs, #84's FREED SHARED EDGES beside #83's
frozen ones (re-measured the same day, from the commit before this one), #82's
plain Winslow and #81's Laplacian (both quoted from their tickets):

  shipped C-grid, 11520 cells, unsmoothed 0 inverted / 32.044 deg max /
  4.562 deg mean / 0.4368% wall:

    cap    kernel              inverted  max      mean    wall      clipped
    1      Laplacian (#81)            0  89.399   6.230   36.61%      --
    1      Winslow   (#82)            0  31.438   4.778   11.65%      --
    1      +control  (#83)            0  31.861   4.527    0.1222%    36
    1      +seams    (#84)            0  31.861   4.516    0.1222%    40
    5      Laplacian (#81)            4  89.786  10.004  126.45%      --
    5      Winslow   (#82)            0  29.844   5.627   39.15%      --
    5      +control  (#83)            0  31.382   4.454    0.0805%     8
    5      +seams    (#84)            0  31.382   4.340    0.0846%     8
    20     Laplacian (#81)           26  89.864  16.288  372.84%      --
    20     Winslow   (#82)            0  33.759   8.517  130.77%      --
    20     +control  (#83)            0  29.895   4.301    0.0893%     0
    20     +seams    (#84)            0  29.895   3.821    0.0968%     0
    40     +control  (#83)            0  34.784   4.214    0.0980%     0
    40     +seams    (#84)            0  28.551   3.388    0.1111%     0
    100    +control  (#83)            4  86.606   4.710   19.06%       4
    100    +seams    (#84)            0  26.493   3.381    0.1289%     0
    150    +seams    (#84)            0  28.890   4.316    0.1338%     0
    300    +seams    (#84)            0  47.765   8.218    0.1555%     0
    400    +seams    (#84)          184  80.872  10.854   27.37%     156
    500    +control  (#83)          288  84.927  10.860   99.99%     212
    500    +seams    (#84)          620  89.900  13.087   37.38%     428
    20000  +seams    (#84)         2262  89.944  17.854   99.99%     942
           (#84 DIVERGES at 1111 and returns that iterate; #83's residual
            plateaued there instead and #82's diverged at ~4900)

  THE ANGLE NO LONGER TURNS AT THIRTY, which is the clearest single reading of what
  this ticket bought: #83's max went 29.90 -> 31.55 -> 34.78 over caps 20, 30, 40
  because the interior was shearing against a frozen seam. #84's falls monotonically
  to 26.49 at a cap of 100 and turns only past 150.

  shipped O-grid, 9216 cells, unsmoothed 0 inverted / 2.250 / 1.875 / 0.0812%:

    1      Laplacian (#81)            0   4.344   1.882   53.36%      --
    1      Winslow   (#82)            0   3.312   1.875    9.13%      --
    1      +control  (#83)            0   3.632   1.875    0.0390%     0
    1      +seams    (#84)            0   2.276   1.875    0.0390%     0
    5      Laplacian (#81)          184  17.443   2.111   87.36%      --
    5      Winslow   (#82)            0   8.061   1.978   29.13%      --
    5      +control  (#83)            0   6.418   1.980    0.0412%     0
    5      +seams    (#84)            0   2.276   1.875    0.0412%     0
    20     +control  (#83)            0  12.036   2.571    0.0442%     0
    20     +seams    (#84)            0   2.276   1.875    0.0442%     0
    40     +seams    (#84)            0   2.276   1.875    0.0475%     0
    150    +seams    (#84)            0   2.274   1.875    0.0566%     0
    300    +seams    (#84)          192   2.274   1.875    0.0598%   200

  THE MEAN OF EXACTLY 1.875 IS STRUCTURAL, not a coincidence and not a strong
  result: a 48-gon's every quad corner deviates by half the sector angle whatever
  the radial distribution is, so this column measures the faceting and nothing
  else. What it DOES say is that the grid is polar again — #83's 2.571 at a cap of
  20 was the interior pulled off the polar structure by the frozen radials.

  the mid-block radial band of the shipped O-grid — the 48 interface nodes with
  2 < r < 8 and the 416 cell corners touching them, indexed on the unsmoothed mesh
  because a freed interface MOVES:

    cap 0    max 2.2477   mean 1.8752
    cap 1    max 1.9475   mean 1.8755
    cap 20   max 1.8794   mean 1.8757

  the near-leading-edge region of the shipped C-grid — the ten quad cells touching
  the airfoil between x = 0.005 and 0.030, which is where #57 localised the corner
  that drove the solver to NaN, at (0.0134, 0.0196):

    cap 0   max 32.044 deg   mean 26.895 deg
    cap 1   max 31.861       mean 26.734
    cap 5   max 31.382       mean 26.308
    cap 20  max 29.895       mean 24.915

  the wake cut of the shipped C-grid, over the 192 corners of the 48 cells touching
  it, at a cap of 20:

    unsmoothed   max 0.0000 deg   mean 0.0000 deg
    smoothed     max 0.6173       mean 0.0178

#80'S ACCEPTANCE IS MET ON THE C-GRID AND STILL NOT ON THE O-GRID, and both are
asserted rather than summarised:

  * C-grid: max, mean AND wall all better than #57's baseline at the same time,
    inverted still 0, and the near-LE region improving on its own figures rather
    than only through the mesh-wide maximum. Group 10.
  * O-grid: the wall first cell is BETTER than #55's 0.0812% (0.0390%) and max
    non-orthogonality is still WORSE (2.250 -> 2.276). Recorded as unmet — but the
    gap is 1.2% and no longer grows with the cap, so #83's "no single cap meets
    both of #80's bullets" is GONE. The residue is the FACETED OUTER WALL's rather
    than the interface's: the unsmoothed mesh's own worst corner is 2.250 ON that
    wall and the smoothed one's is 2.276 one grid line in from it. Groups 8 and 9.
    CORRECTED by #93 (2026-09-08): what that wall is faceted BY is a polyline
    coarser than the mesh reading it — 80 facets under 96 nodes — so the cause is
    the sampling ratio and NOT #83's frozen wall, whose decision this leaves
    untouched. Both figures above are still the shipped case's and still assert.

WHAT #84's OWN CRITERION ASKED FOR AND THIS FILE COULD NOT DELIVER, said plainly:
the ticket asks that the wake cut's "own cells improve rather than staying at their
unsmoothed values". They cannot. The wake is a straight line on the symmetry axis
and the algebraic fill already leaves all 48 cells against it EXACTLY orthogonal,
so the criterion's premise — that the wake was one of the worst lines — is false on
this geometry. The worst lines were the RADIAL interfaces, and those improve (group
9). Group 11 measures the wake on the terms that are true: one line both blocks
read, no boundary face, its 23 interior nodes moving, staying on the axis to 1.4e-18 (the check's
own bar is 1e-15), and a cost of 0.0178 deg mean where the mesh-wide mean gains 0.74.

BLIND SPOTS, named rather than papered over:

  * Nothing here runs the solver or the grid converter on a smoothed mesh. That is
    #80's own acceptance rather than this ticket's, and the unsmoothed C-grid's
    dated run is in test_multiblock_cgrid_surface.py. A smoothed mesh would now be
    a reasonable thing to hand a viscous solver — 0.10% off the requested wall
    height at twenty sweeps — so this is a gap rather than a non-question, and it
    belongs to #85.
  * The figures in the tables above are a record of one dated run, not something
    this file re-measures. What it asserts is the DIRECTION and a floor, so a
    kernel that quietly stopped moving anything would be caught while a kernel
    that moves things differently is free to.
  * NOTHING MEASURES THE FREED INTERFACES ON THE C-GRID's OWN TERMS. Group 9's
    band selection is polar and works because the O-grid's radials lie at four
    known angles; the C-grid's three radials and its wake have no such handle from
    outside, so what is read there is the wake (group 11) and the whole-mesh
    figures. The C++ test reaches those lines by node id and pins the mechanism,
    not the quality.
  * A FOLD FROM SMOOTHING IS STILL REACHABLE ON THESE FILES, at a cap of 400 on
    the C-grid and 300 on the O-grid rather than #83's 100 and (unmeasured). Group
    7 asserts exit 9 on the real file. THE O-GRID's FOLD IS INVISIBLE TO
    NON-ORTHOGONALITY, which is worth recording as a limit of the ruler rather
    than of this ticket: at a cap of 300 it folds 192 cells while max
    non-orthogonality reads 2.274 deg, because two adjacent radial lines have
    swapped order and the folded cells are still very nearly rectangular. The
    inverted-cell count is what sees it.
  * NO SYNTHETIC FIXTURE REACHES THE SATURATING-AND-DESCENDING regime that the
    stability limit lives in; the shipped C-grid at a cap of 400 is the only case
    that does, which is why that check is here and not next door.
  * The banner is checked for its headings and the numbers are read out of the
    machine-readable lines, exactly as the quality gate next door does it: the two
    are built from one report object, and the C++ test pins the report. The
    exceptions are groups 9, 10 and 11's own quad reader, and group 10 validates it
    against the C++ ruler's whole-mesh line before it is trusted anywhere the
    ruler does not look.

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
# #53's CONFORMITY MEASURE, imported and not re-invented: #84's acceptance names it
# as the property to reuse. `edge_use` counts how many cells each undirected cell
# edge belongs to, `components` counts connected components by SHARED NODE IDENTITY,
# and the three readers give the STAR-CD files the grid converter actually consumes.
from test_multiblock_weld_surface import (  # noqa: E402
    bnd_faces, cel_cells, components, edge_use, vrt_nodes)
from mesher_bin import NO_SMOOTH, mesher_env as _mesher_env  # noqa: E402

# "UNSMOOTHED" IS NO LONGER THE DEFAULT, and since #85 every run that means it has
# to say so. `MB_SMOOTH_ITERS` ships at 20, so a bare run is a SMOOTHED run — the
# five places below that need the algebraic fill's own mesh (group 1's silence, the
# O-grid's and the C-grid's before-figures, and group 11's control) pass
# `NO_SMOOTH` explicitly. It is imported rather than spelled here: `mesher_bin`
# owns the one spelling, because this file called it `OFF` while the gate next door
# called it `NO_SMOOTH` and three more used a raw literal. What the DEFAULT produces
# is gated in test_multiblock_quality_gate.py.

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
        # ── 1. ZERO SWEEPS is silence, and the DEFAULT is not zero ──────────
        #
        # #81 wrote this group as "the default is silence" and #85 took that half
        # away: the shipped default is 20 sweeps, so what still has to hold is the
        # narrower and more useful claim — a run that asks for NO smoothing gets
        # byte for byte the report this path printed before the parameter existed.
        # The second half is new and is the other direction: the default really
        # does smooth, so this group cannot pass on a build where the flip was lost.
        rc0, out0, _ = run(tmp, "plain", NO_SMOOTH)
        check("1. the shipped C-grid meshes at MB_SMOOTH_ITERS 0 (rc=0)", rc0 == 0)
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
        rcd, outd, _ = run(tmp, "dflt")
        sd = smooth_line(outd)
        check(f"1. ...while the DEFAULT is 20 sweeps and not 0 (#85), so none of "
              f"the above is a property of a bare run any more (rc={rcd}, "
              f"cap={sd.get('cap')})",
              rcd == 0 and sd.get("cap") == 20 and "_BEFORE" in outd)

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
        # alone cannot distinguish them — both are `converged=0 diverged=0`. The
        # cap moved with #84: the C-grid is still descending at 100 and 150 and
        # turns by 300 (best 281), where #83's turned by 30.
        _, outt, _ = run(tmp, "turned", "\nMB_SMOOTH_ITERS 300\n")
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
              st.get("sweeps") == 300)

        # THE STABILITY LIMIT, and #84 MOVED IT — which is one of the two ways this
        # ticket shows up in this group. The control functions hold the wall and the
        # lagged-coefficient iteration is only conditionally stable, but with the
        # shared edges free the grid has somewhere to go instead of shearing against
        # a frozen seam. Measured 2026-09-07 on this file, against #83's own figures
        # from the same runs:
        #
        #   cap    #83 inverted   #84 inverted
        #   40               0              0
        #   100              4              0
        #   150             --              0
        #   300             --              0
        #   400             --            184
        #   500            288            620
        #
        # So the fold is now reachable at 400 and not at 100, and the run still
        # reports it through the machinery that already exists — the inverted-cell
        # count and exit 9 — which is why the capped warning points at that rather
        # than at a second signal.
        rcok, outok, _ = run(tmp, "stable100", "\nMB_SMOOTH_ITERS 100\n")
        aok = qlines(outok)
        check(f"7. the shipped C-grid at a cap of 100 folds NOTHING and exits 0, "
              f"where #83's kernel folded 4 cells there — freeing the seams moved "
              f"the stability limit out (inverted "
              f"{aok[0]['inverted'] if aok else None}, rc={rcok})",
              bool(aok) and aok[0]["inverted"] == 0 and rcok == 0)
        rcs, outs, _ = run(tmp, "satur", "\nMB_SMOOTH_ITERS 400\n")
        ss = smooth_line(outs)
        aq = qlines(outs)
        check(f"7. ...and at 400 it HAS folded while still descending — the "
              f"stability limit, not a turn ({ss})",
              ss.get("converged") == 0 and ss.get("diverged") == 0)
        check(f"7. ...reported by the machinery that already exists: the inverted "
              f"count and exit 9 (inverted {aq[0]['inverted'] if aq else None}, "
              f"rc={rcs})",
              bool(aq) and aq[0]["inverted"] > 0 and rcs == 9)
        check(f"7. ...with the clip count climbing back off the zero it reached by "
              f"sweep 10, which is the direction the warning tells the reader to "
              f"watch ({s10.get('clipped')} at 10 -> {ss.get('clipped')} at 400)",
              ss.get("clipped", 0) > 0)

        # THE DIVERGED ENDING IS BACK ON A SHIPPED FILE, which is the other way #84
        # shows up here and is a reversal of #83's own record. Under that kernel
        # neither shipped case reached either of the two non-cap endings — the
        # residual PLATEAUED, at 6.8e-05 on the C-grid at a cap of 50000 — and both
        # endings had moved to fixtures next door (tests/cpp/test_multiblock.cpp
        # check 49, a notched box whose depth picks the ending). With the seams free
        # the C-grid's residual falls further and then GROWS: it diverges at sweep
        # 1111 and the solve hands back that best iterate rather than the last.
        # Measured 2026-09-07. The C++ fixtures stay — they run in milliseconds and
        # cover the CONVERGED ending, which no shipped case reaches.
        _, outd, _ = run(tmp, "diverge", "\nMB_SMOOTH_ITERS 20000\n")
        sd = smooth_line(outd)
        check(f"7. the shipped C-grid DIVERGES at a cap of 20000 and stops early, "
              f"which #83's kernel could not do on this file ({sd})",
              sd.get("diverged") == 1 and sd.get("converged") == 0
              and 0 < sd.get("sweeps", 0) < 20000)
        check("7. ...returning the BEST iterate rather than the last, and saying so",
              sd.get("best_sweep") == sd.get("sweeps")
              and "DIVERGED" in outd
              and "the BEST iterate" in outd)

        # ── 8. the O-grid: #80's negative control, and it is NOT met ────────
        rco0, outo0, _ = run(tmp, "o0", NO_SMOOTH, config=ogrid_config)
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
        # #80's NEGATIVE CONTROL: STILL NOT MET, AND NOW BY 1.2% RATHER THAN BY
        # 5.3x. All three facts, because the first alone reads better than the truth
        # and the third alone reads worse.
        #
        #   cap    #83 max    #84 max     #55 baseline 2.250
        #   1        3.632      2.276
        #   5        6.418      2.276
        #   20      12.036      2.276
        #   40      16.787      2.276
        #
        # The residue is the FACETED OUTER WALL's, not the interface's, and group 9
        # measures that rather than asserting it: the unsmoothed mesh's own worst
        # corner is 2.250 deg ON that wall, the smoothed one's is 2.276 one grid line
        # in from it.
        # CORRECTED by #93: the wall row IS frozen, but that is not why. The far
        # field is an 80-facet polyline under 96 mesh nodes, so the ratio does not
        # divide; at a ratio that does, the angle is exactly 1.875 and the smoother's
        # excess is exactly 0, with wall nodes still not sliding. #83's decision is
        # untouched — it was simply not the cause. Closing this is #95's geometry
        # work. See docs/design_notes/mesher.md, "THE O-GRID's RESIDUE IS A SAMPLING
        # RATIO, NOT A FROZEN WALL".
        check(f"8. #80's NEGATIVE CONTROL IS STILL NOT MET: a case already at 2.250 "
              f"deg max comes out at "
              f"{ao[0]['nonortho_max_deg'] if ao else None} deg. Recorded as unmet, "
              f"not asserted away — if this ever starts passing, delete the check "
              f"and say so in #80.",
              bool(ao) and ao[0]["nonortho_max_deg"] > bo[0]["nonortho_max_deg"])
        check(f"8. ...but the GAP is now under 2% of #55's figure rather than the "
              f"61% #83 left at the same cap of one (3.632 deg), and it no longer "
              f"grows with the cap — #84's whole deliverable on this case "
              f"({ao[0]['nonortho_max_deg'] if ao else -1:.4f} vs 2.250)",
              bool(ao) and bool(bo)
              and ao[0]["nonortho_max_deg"] < bo[0]["nonortho_max_deg"] * 1.02
              and ao[0]["nonortho_max_deg"] < 3.632)
        _, outo20, _ = run(tmp, "o20", "\nMB_SMOOTH_ITERS 20\n", config=ogrid_config)
        ao20 = qlines(outo20)
        check(f"8. ...at a cap of TWENTY too, where #83 was at 12.036 deg — 5.3x "
              f"#55's — so there is no longer a cap at which #80's C-grid bullet and "
              f"its O-grid bullet pull apart "
              f"({ao20[0]['nonortho_max_deg'] if ao20 else -1:.4f} deg)",
              bool(ao20) and ao20[0]["nonortho_max_deg"] < 2.30
              and ao20[0]["nonortho_mean_deg"] <= 1.876
              and ao20[0]["inverted"] == 0)
        check(f"8. ...and the wall first cell is BETTER than #55's 0.0812%, which "
              f"#83 already delivered and #84 must not give back "
              f"({100 * ao20[0]['wall_first_cell_worst_rel'] if ao20 else -1:.4f}%)",
              bool(ao20) and ao20[0]["wall_first_cell_worst_rel"] < 0.000812)

        # ── 9. WHERE the kink went: the interfaces are no longer it ────────
        #
        # #82 localised this regression through the run's own wall table; #83 held
        # the wall row all the way round, so the table could no longer find it, and
        # measured the corners directly instead: the smoothed O-grid's worst sat at
        # r = 3.43, MID-BLOCK on the four DECLARED RADIAL INTERFACES, while the
        # unsmoothed mesh's worst sat at r = 10 on the faceted outer circle. That
        # was the kink along a frozen shared edge, and #84 is the ticket that
        # unfroze them.
        #
        # WHAT THIS GROUP NOW ASSERTS, in two halves that answer different
        # questions. First, the mid-block radial band's OWN cells, selected on the
        # unsmoothed mesh and read on both — because the freed interfaces bend
        # slightly and a theta filter re-applied to the smoothed mesh silently
        # loses four of the 84 nodes. Measured 2026-09-07 over the 48 radial-
        # interface nodes with 2 < r < 8 and the 416 cell corners touching them:
        #
        #   cap 0    max 2.2477   mean 1.8752
        #   cap 1    max 1.9475   mean 1.8755
        #   cap 20   max 1.8794   mean 1.8757
        #
        # So the cells against a shared edge are now BETTER than the algebraic
        # fill left them, which is #80's user story 3 and #84's own acceptance
        # criterion about a shared edge's own cells improving.
        #
        # Second, the whole mesh's worst corner has MOVED: off the mid-block
        # interface and onto the line one in from the faceted outer wall (r = 9.19
        # against that wall's own 10.0), at the faceting's own magnitude. Both
        # halves are needed — the first alone would pass on a mesh whose worst had
        # merely moved somewhere else worse, and the second alone would not show
        # that the interface improved rather than being left alone.
        oq = "\nMB_SPLIT_QUADS 0\n"
        _, _, oqs0 = run(tmp, "oq0", oq + NO_SMOOTH, config=ogrid_config)
        _, _, oqs1 = run(tmp, "oq1", oq + "\nMB_SMOOTH_ITERS 20\n",
                         config=ogrid_config)
        wall_tab = [l for l in outo1.splitlines() if "west 'w0'" in l]
        check(f"9. the O-grid's wall row is still held at its declared height ALL "
              f"the way round, which is #83's and must survive this ticket "
              f"({wall_tab[-1].strip() if wall_tab else None})",
              len(wall_tab) == 2 and "(0.0" in wall_tab[-1])
        pts0, cells0 = quad_corners(oqs0 + ".vtk")
        pts1, cells1 = quad_corners(oqs1 + ".vtk")
        # THE MID-BLOCK RADIAL BAND, indexed on the UNSMOOTHED mesh and reused.
        # Node ids are what welding rests on and no sweep allocates one, so the same
        # index is the same node in both files — which is the only selection that
        # can compare a line that MOVED.
        mid = set()
        for k, (x, y) in enumerate(pts0):
            rad = math.hypot(x, y)
            if not (2.0 < rad < 8.0):
                continue
            ang = math.degrees(math.atan2(y, x))
            if min(abs(ang - t) for t in (-180, -90, 0, 90, 180)) < 1e-9:
                mid.add(k)
        b0, b1 = devs_of(pts0, cells0, mid), devs_of(pts1, cells1, mid)
        check(f"9. the four mid-block radial interfaces are found on both meshes "
              f"({len(mid)} nodes, {len(b0)} corners) and the same set is read on "
              f"each, because a freed interface MOVES",
              len(mid) > 0 and len(b0) == len(b1) > 0)
        if b0 and b1:
            check(f"9. ...and THEIR OWN CELLS IMPROVE rather than staying at the "
                  f"unsmoothed values: max {max(b0):.4f} -> {max(b1):.4f} deg",
                  max(b1) < max(b0))
            check("9. ...which is what #83 could not do at all — its whole-mesh "
                  "worst was 12.036 deg, localised on exactly these lines at "
                  "r = 3.43 (this band is now under 2.0 deg)",
                  max(b1) < 2.0)
        worst, at = 0.0, None
        for c in cells1:
            for k in range(4):
                p, q, r = pts1[c[k]], pts1[c[(k + 1) % 4]], pts1[c[(k - 1) % 4]]
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
        check(f"9. ...and the smoothed mesh's WORST corner has moved off the "
              f"mid-block interface to the line one in from the faceted outer wall "
              f"({worst:.4f} deg at r={rad:.3f}, that wall itself being r=10 and "
              f"2.250 deg) — the residue #80's O-grid bullet still fails on is the "
              f"WALL's faceting, which #93 measured to be its 80-facet polyline "
              f"under 96 mesh nodes rather than the fact that #83 froze it",
              rad > 9.0)

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
        base_q, outq0, qs0 = run(tmp, "q0", "\nMB_SPLIT_QUADS 0\n" + NO_SMOOTH)
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

        # ── 11. #84's OWN DELIVERABLES on the shipped C-grid ───────────────
        #
        # THE FREEZE RULE IS REPORTED, not inferred from a loop: a run says how many
        # nodes it was free to move and how many of those were on a shared edge, and
        # the second figure is checked against the run's OWN shared-edge report
        # rather than against a number typed here — an edge of n shared nodes frees
        # n - 2 of them, its two ends being declared corners.
        #
        # THE MESH STAYS CONFORMAL, measured with #53's own instrument on the
        # EXPORTED files: every interior edge in exactly two cells, the boundary
        # edge set exactly the `.bnd`, one connected component by node identity.
        # That is the property a per-block smoother would break — it is what tearing
        # a shared node into two looks like from outside — and it is the reason the
        # ticket asks for that measure rather than a new one.
        #
        # AND THE WAKE CUT SPECIFICALLY, where the ticket's own premise turned out
        # not to hold and the honest answer is the measurement. It asks that the
        # cut's "own cells improve rather than staying at their unsmoothed values".
        # On this geometry they CANNOT: the wake is a straight line on the symmetry
        # axis and the algebraic fill already leaves the cells against it EXACTLY
        # orthogonal — 0.0000 deg over all 48 of them — so there is nothing to
        # improve. What is asserted instead is what is true and what the criterion
        # was reaching for: the cut is one line both blocks read, it exports no
        # boundary face, its 23 interior nodes MOVE rather than being frozen, they
        # stay on the axis to 1.4e-18 by symmetry, and the cost of freeing them is
        # 0.0178 deg mean / 0.617 deg max at a cap of 20 against a mesh-wide gain of
        # 32.044 -> 29.895 max and 4.562 -> 3.821 mean. The lines that WERE the
        # worst ones — the radial interfaces — are group 9's, and they improve.
        rc84, out84, s84 = run(tmp, "m84", "\nMB_SMOOTH_ITERS 20\n")
        _, outu84, su84 = run(tmp, "m84u", NO_SMOOTH)
        a84 = qlines(out84)
        sm84 = smooth_line(out84)
        check(f"11. the shipped C-grid smooths and exports every file (rc={rc84}, "
              f"wrote {wrote(s84)})", rc84 == 0 and len(wrote(s84)) == 4)
        shared_nodes = [int(m) for m in re.findall(r"(\d+) shared nodes", out84)]
        want_shared = sum(n - 2 for n in shared_nodes)
        check(f"11. the run REPORTS which nodes it was free to move, and the shared "
              f"half is exactly the interior of the edges its own shared-edge report "
              f"names ({sm84.get('moved_shared')} vs {want_shared} from "
              f"{shared_nodes})",
              len(shared_nodes) == 4
              and sm84.get("moved_shared") == want_shared > 0)
        check("11. ...in the banner as well as in the token, saying which nodes are "
              "frozen and why",
              re.search(r"Movable nodes\s+: \d+ of \d+, of which \d+ on a shared "
                        r"edge \(walls and declared corners are frozen\)",
                        out84) is not None)
        check("11. ...and a run that smoothed NOTHING reports neither figure, "
              "because 0 movable nodes is a real answer and must not stand in for "
              "not having looked", "Movable nodes" not in outu84)
        # NODE COUNTS DO NOT CHANGE. Smoothing moves nodes; it never adds, removes
        # or re-identifies one — which is what "welding is by allocation" means on
        # the way out, and it is read off the exported files rather than the seam.
        nu, ns = vrt_nodes(su84), vrt_nodes(s84)
        cu, cs = cel_cells(su84), cel_cells(s84)
        check(f"11. node and cell counts are UNCHANGED by smoothing "
              f"({len(nu)}/{len(cu)} vs {len(ns)}/{len(cs)})",
              len(nu) == len(ns) > 0 and len(cu) == len(cs) > 0)
        check("11. ...and so is the CONNECTIVITY, id for id: the smoother writes "
              "coordinates and allocates nothing", cu == cs)
        # CONFORMITY, on the SMOOTHED files, with #53's measure.
        use = edge_use(cs)
        interior = [k for k, v in use.items() if v == 2]
        boundary = [k for k, v in use.items() if v == 1]
        overused = [k for k, v in use.items() if v > 2]
        bnd = bnd_faces(s84)
        check(f"11. the SMOOTHED mesh is still CONFORMING: every interior edge "
              f"belongs to exactly two cells ({len(interior)} interior, "
              f"{len(overused)} with more than two)", not overused)
        check(f"11. ...and its boundary edge set is EXACTLY the '.bnd' "
              f"({len(boundary)} vs {len(bnd)})",
              len(boundary) == len(bnd)
              and {f for f, _ in bnd} == set(boundary))
        check("11. ...and the whole mesh is ONE connected component, by node "
              "identity", components(cs, len(ns)) == 1)
        # THE WAKE CUT. Identified on the exported vertices: the segment of the
        # symmetry axis downstream of the trailing edge at x = 1.
        #
        # THE MOVEMENT IS READ OFF THE `.vtk` AND NOT THE `.vrt`, which cost this
        # check a false failure first: the STAR-CD vertex writer rounds, and the
        # wake's own displacement at a cap of 20 is 4.6e-06 at its finest station —
        # so 21 of the 24 nodes came back "unmoved" from a file that had simply not
        # written the digits. The `.bnd` half below stays on the STAR-CD files,
        # because there the question is about the patch list the converter reads.
        #
        # EACH SET IS INDEXED IN ITS OWN FILE'S NUMBERING. A `.vrt` id and a `.vtk`
        # id are the two numbers CLAUDE.md's `golden_mesh.py` note calls "precisely
        # the numbers free to move", so the first draft — a `.vrt`-indexed wake set
        # applied to the `.vtk` arrays — passed only by today's coincidence. There
        # are two sets now and they are checked against each other by SIZE.
        vp_u, _ = quad_corners(su84 + ".vtk")
        vp_s, _ = quad_corners(s84 + ".vtk")
        wake_vtk = [k for k, (x, y) in enumerate(vp_u) if y == 0.0 and x > 1.0]
        wake_u = [k for k, (x, y) in enumerate(nu) if y == 0.0 and x > 1.0]
        check(f"11. the wake cut is found on the exported mesh, in BOTH numberings "
              f"({len(wake_u)} '.vrt' nodes and {len(wake_vtk)} '.vtk' nodes on the "
              f"axis downstream of the trailing edge)",
              len(wake_u) > 2 and len(wake_vtk) == len(wake_u))
        on_axis = [f for f, _ in bnd
                   if all(ns[v - 1][1] == 0.0 and ns[v - 1][0] > 1.0 for v in f)]
        check(f"11. ...and it STILL exports no boundary face, smoothed: it is an "
              f"interior line with cells on both sides ({len(on_axis)} faces on it)",
              not on_axis)
        movedw = sum(1 for k in wake_vtk if vp_u[k] != vp_s[k])
        check(f"11. ...its interior nodes MOVE rather than staying frozen, which is "
              f"this ticket on the line #57 made the highest-risk one in the grid "
              f"({movedw} of {len(wake_vtk)} moved; the one that does not is the "
              f"declared corner at the outlet)",
              movedw == len(wake_vtk) - 1)
        check(f"11. ...and stays ONE line on the symmetry axis, to 1e-15 — the two "
              f"wake blocks are mirror images and the node is moved ONCE, so there "
              f"is no second answer to be pulled toward (worst |y| "
              f"{max(abs(vp_s[k][1]) for k in wake_vtk):.2e})",
              max(abs(vp_s[k][1]) for k in wake_vtk) < 1e-15)
        # AND WHAT FREEING IT COST, measured rather than claimed: the unsmoothed
        # cells against the wake are EXACTLY orthogonal, so the ticket's "its own
        # cells improve" is unreachable on this geometry and the honest figure is
        # the small price. Read on the quad runs group 10 already made, over the
        # cells touching the wake.
        # Group 10's own quad runs, named again rather than inherited: `pts0` is
        # rebound twice above (group 9's O-grid, then group 10's C-grid) and a
        # measurement that depends on which assignment ran last is one nobody can
        # check by reading it.
        cq0, cc0 = quad_corners(qs0 + ".vtk")
        cq1, cc1 = quad_corners(qs1 + ".vtk")
        wq = {k for k, (x, y) in enumerate(cq0) if y == 0.0 and x > 1.0}
        wd0, wd1 = devs_of(cq0, cc0, wq), devs_of(cq1, cc1, wq)
        check(f"11. the unsmoothed cells against the wake are EXACTLY orthogonal, "
              f"so 'its own cells improve' is unreachable here and the criterion's "
              f"premise does not hold on this geometry (max {max(wd0):.6f} deg over "
              f"{len(wd0)} corners)",
              bool(wd0) and max(wd0) < 1e-9)
        check(f"11. ...and freeing it costs {max(wd1):.4f} deg max / "
              f"{sum(wd1)/len(wd1):.4f} deg mean there, against a mesh-wide gain of "
              f"32.044 -> {a84[0]['nonortho_max_deg']:.3f} max and 4.562 -> "
              f"{a84[0]['nonortho_mean_deg']:.3f} mean — recorded, not hidden",
              bool(wd1) and max(wd1) < 1.0 and bool(a84)
              and a84[0]["nonortho_max_deg"] < 32.044
              and a84[0]["nonortho_mean_deg"] < 4.562)

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
