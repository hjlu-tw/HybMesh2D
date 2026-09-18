#!/usr/bin/env python3
"""The HYBRID path's CELL SHAPE figures, through the real binary on the shipped
case (issue #130, parent #128).

The arithmetic is pinned next door in ``tests/cpp/test_cell_shape.cpp`` — a square
is 1.0 and each of its split triangles sqrt(2), a degenerate cell does not divide
by zero, how p95 is ranked, and an empty input reduces to NEGATIVE figures rather
than zeros. WHICH CELLS THIS PATH OFFERS to that metric — the corner-count floor,
the corner-count ceiling, the unresolved id, and what the two counts on the line
mean — is pinned in ``tests/cpp/test_hybrid_quality.cpp`` since #141, which lifted
that half out of a ``static`` function in ``src/cli.cpp`` where nothing could link
to it and this file was its only cover. What can only be checked out here is the
half that IS the ticket: that THREE SURFACES agree about one mesh — the banner a user reads, the machine-readable
line a script greps, and the ``.provenance.json`` sidecar every later reader
consumes — and that this path's figure can never be mistaken for the multi-block
path's, which measures a different quantity.

Run on the SHIPPED config, handed to the binary BY PATH, because the demo in the
ticket is ``./run.sh -conf config/Background_para.dat -geom
examples/geometries/naca0012.dat`` and a composed equivalent would leave an edit to
that file invisible from here. It is not read or rewritten by this file at all --
that config declares no path and no ``OUTPUT_FILENAME``, so the only retargeting it
needs is ``-out_name`` on the command line, which is how ``tools/scripts/
golden_mesh.py`` already drives the same pair. There is therefore no second
implementation of ``mb_shipped_config.shipped_config`` here, and nothing for
``test_shipped_config_seam.py`` check 1 to find.

What this pins down:

  1. The ``[ Mesh Statistics ]`` block — the one a user already reads for the size
     of the mesh — gains a ``Cell shape`` row carrying median, p95 and max, and
     says over how many EXPORTED TRIANGLES.
  2. The machine-readable line carries those figures as ``key=value`` in the
     existing ``HYBMESH_*`` shape, so an acceptance check stays a grep. It is read
     with the ONE parser the multi-block quality gate owns, which floats every
     token — so a string-valued token on that line would fail here rather than
     silently breaking six gates.
  3. THE METRIC'S NAME IS IN THE KEY (``tri_edge_ratio_*``) and the LINE'S PREFIX
     is this path's own, so neither a grep for the multi-block figure nor the
     parser reading its prefix can match this one.
  4. THE TWO PATHS CANNOT BE CONFUSED, MEASURED IN BOTH DIRECTIONS: nothing in a
     hybrid run names ``quad_midline_ratio`` or prints a ``HYBMESH_MB_QUALITY``
     line, and nothing in a multi-block run names ``tri_edge_ratio`` or prints a
     ``HYBMESH_HYBRID_QUALITY`` one.
  5. THE DISTINCTION IS STATED WHERE A READER OF EITHER WILL SEE IT: each path's
     own ``Cell shape`` row names the other path's metric as not comparable. One
     banner carrying the warning would only reach the reader who already had the
     other one open.
  6. The sidecar's ``mesh.quality`` object holds the same numbers under a
     ``metric`` that names the quantity, in the schema #129 established. Parsed as
     JSON out of a file a real run produced, never asserted against a writer.
  7. THE SAME NUMBERS, to the digit, in all three places. This is what "one owner"
     means operationally.
  8. Every figure is at or above 1.0 and ordered median <= p95 <= max. 1.0 is the
     metric's floor, so this is what stops an absent measurement reaching a user
     as a number.
  9. THE BOUNDARY LAYER DOMINATES THE MAX WHILE THE MEDIAN SITS NEAR 1.0, which is
     the ticket's own headline and the whole reason three numbers are reported
     rather than one. Measured against a NEGATIVE CONTROL rather than claimed: the
     same config and the same geometry loaded through ``-geom_nobl``, so no layer
     is grown, reports a median within a few percent of the BL run's and a p95 and
     max an order of magnitude smaller. The spread is the boundary layer.
 10. ``not measured``, REACHED THROUGH THE BINARY. With no geometry, no seed and no
     domain file this path builds a CARTESIAN QUAD fallback, and a quad carries no
     triangle edge ratio — so the banner prints ``not measured``, the three figures
     come back NEGATIVE (never 0.0, which on a metric whose floor is 1.0 could only
     ever be an absent measurement wearing a number), and the sidecar carries the
     same. That state is UNREACHABLE on the multi-block path, whose own gate names
     it as a blind spot; here it is a shipped case away.
 12. A MESH WITH NO CELLS AT ALL reports `not measured` too, and it is REACHED
     THROUGH THE BINARY: a domain smaller than one far-field cell makes the
     Cartesian fallback refuse by name, and the run goes on to print a banner and
     write a sidecar over 0 nodes and 0 elements. That is the criterion's literal
     wording, and it is a DIFFERENT input from check 10's — which exports 400 cells
     none of which could be measured. Both reach the same `cells == 0` branch, and
     the point of having both is that neither one's input is the other's.
 11. NO THRESHOLD AND NO COLOUR on the row. The shipped case's max is ~79 and the
     run exits 0: that number is the wall's first cell height against the surface
     spacing the user asked for, and a tool that coloured it red would be training
     them to ignore colour. #128 rules out a pass/fail bar on these figures, so
     this file asserts none. The two rows #143 adds are held to the same rule, by
     the same scan.
 13. THE SPLIT (#143): the cells the BOUNDARY LAYER emitted, reported apart from
     the rest, on all three surfaces and agreeing there. Check 9 makes the same
     point with two MESHES — one grown, one not — which is evidence about where
     the spread comes from; this is the TOOL making the split, on the one mesh a
     user actually has. It carries THE ONE NUMERIC BAR IN THIS FILE, which the
     ticket asks for by name: the bulk p95 below 2 while the whole-mesh p95 is
     above 40. Two sides on purpose — a bulk p95 under 2 alone would also pass if
     the split silently measured nothing, and a whole-mesh p95 over 40 alone is
     check 9's fact. It is a bar on THE SPLIT DOING SOMETHING, not a quality
     threshold: nothing here passes or fails a mesh (see check 11).
 14. AN EMPTY HALF IS `not measured`, NOT 0.0, and it is an ORDINARY case on this
     path rather than an error: check 9's own `-geom_nobl` run grows no layer at
     all, so its layer half is empty and its bulk half is the whole mesh. Driven
     off that same run. What the row says about WHY is check 10's, because the two
     cases differ there: here the cells really are absent, and on the Cartesian
     fallback 400 of them exist and cannot be measured. The row must be true of
     BOTH, so it names no cause — and this file's first version asserted a wording
     that was false on the second, having been written from the same wrong premise
     as the code (#143 review).
 15. TODAY'S SPELLINGS STILL READ THE WHOLE MESH. Every token the line carried
     before the split is still on it, and the sidecar still carries #129's keys at
     the top of `mesh.quality` — asserted against LITERAL names, because a list
     rebuilt from the same constants the new tokens come from could not see a
     rename that moved both together. What makes it more than a presence test is
     that the old figures are shown to describe the WHOLE mesh and not a half: the
     count is both halves', the max is the larger half's, and the p95 is NEITHER
     half's.
 16. A PATH THAT DOES NOT SPLIT WRITES NEITHER KEY — a state of its own, separate
     from a half that was measured and came back empty. The multi-block path is
     today's only witness, and #144 will stop it being one; THIS CHECK IS THEN THE
     ONE TO UPDATE, and the naming shape it must match is `<metric>_layer_*` /
     `<metric>_bulk_*`, settled here because this ticket landed first.

MEASURED 2026-09-17, on the shipped config at its shipped values; the two halves
added 2026-09-18 (#143), on the same runs:

    naca0012, BL on     15233 exported triangles, all measured
                        median 1.158103, p95 52.185741, max 78.703074
                        layer  3215 cells (21.1%), median 35.281749,
                               p95 70.541670, max 78.703074
                        bulk  12018 cells, median 1.112154, p95 1.411765,
                               max 11.901852
    naca0012, -geom_nobl 12293 exported triangles
                        median 1.114486, p95 1.420814, max 7.388082
                        layer  0 cells, all three figures -1.0
                        bulk  12293 cells, the same figures as the whole mesh
    no geometry at all    400 exported quads, 0 measured
                        median/p95/max all -1.0, banner "not measured"
                        both halves 0 cells, all figures -1.0
    domain 1e-3 wide      0 nodes, 0 elements, 0 offered, 0 measured
                        median/p95/max all -1.0, banner "not measured"

The WHOLE-MESH figures are byte for byte what #141 recorded, which is the evidence
that the split landed BESIDE them and not over them. Those figures are a RECORD of
these dated runs; the bars this file asserts are structural (ordering, agreement,
the BL/no-BL contrast) rather than numeric, with check 13's the single exception
and its own reason stated there.

INJECTIONS, run 2026-09-17 against `src/cli.cpp` with a rebuild per mutation, and
recorded here because a C++ defect cannot be injected from inside a Python gate.
THE CODE INJECTION B MUTATES HAS MOVED, AND ONLY B'S: #141 lifted the cell
collection into `src/HybridQuality.cpp`, so B's corner-count guard is edited there
now. Every other site is where it was — A, D, E and F (the names, the prefix and
the two banner sentences) are `src/cli.cpp`'s, and C's three figures were never in
the collection loop at all: they come from `reduceCellShapes` in
`src/CellShape.cpp`, and the `ShapeStats` an injector forces to 0.0 is still the
one `printHybridQuality` holds.
Each names the checks it reddened, so a later reader can tell a check that bites
from one that merely passes:

  A. the hybrid line's four tokens renamed to the multi-block metric's
     (`quad_midline_ratio_*`) -> 3 failures, checks 2, 3 and 4. IT REDDENED CHECK 2
     ALONE ON THE FIRST RUN, because that defect also empties the parsed figures and
     the gate bailed out before reaching the two checks WRITTEN for it. Checks 3 and
     4 were moved above the bail-out; the shape is #127's "isolate the labelled
     check", found here by injecting rather than by reading.
  B. the corner-count guard widened to accept quads (`> 4` instead of `!= 3`)
     -> 4 failures, all of check 10: the Cartesian fallback then reports
     `median 1.000, p95 1.000, max 1.000` over 400 cells, which is the MIDLINE ratio
     of 400 squares wearing the name `tri_edge_ratio`. A correct number under the
     wrong name is exactly what two names exist to prevent, and this is the check
     that sees it.
  C. the three figures forced to 0.0 when nothing was measured -> 4 failures, the
     machine line and the sidecar in BOTH check 10 and check 12. The banner is not
     among them at either: it branches on `cells`, not on the figures, so this rule
     is guarded at two surfaces and not three. Named rather than left to look like
     coverage.
     Injection B is the contrast that shows 10 and 12 are two inputs and not two
     names for one: widening the corner guard reddens all four of check 10 and NONE
     of check 12, whose mesh has no cells for a guard to admit.
  D. the hybrid row's `NOT comparable with MESH_MODE 1's quad midline ratio` dropped
     -> 1 failure, check 5's first half.
  E. the same sentence dropped from the MULTI-BLOCK row, restoring what that banner
     said before this ticket -> 1 failure, check 5's second half. The two halves are
     separately guarded, which is what "a reader of EITHER" needs.
  F. the hybrid line emitted under `HYBMESH_MB_QUALITY` -> 4 failures, checks 2
     (both halves), 3 and 4. Like A, it reddened only check 2 until checks 3 and 4
     moved above the bail-out — the SECOND time one mutation's own checks sat behind
     an early return, which is why both are recorded rather than the fix alone.

INJECTIONS FOR THE SPLIT, run 2026-09-18 the same way, a rebuild per mutation:

  G. the two halves swapped in `src/HybridQuality.cpp` (`fromBoundaryLayer ? bulk
     : layer`) -> 7 failures, three in check 13 and all four of check 14. The two
     that do NOT move are the finding: the partition still holds and the layer
     half is still over 5% of the cells, because both are true of either labelling.
     A check that counts cannot tell you which cells they were.
  H. ONE boundary-layer emission site in `src/BoundaryLayer.cpp` reverted to the
     unmarked `addElement` — the main stitch, `{activeFront[i], activeFront[i_next],
     n_next_first}` -> 3 failures in check 13: the bulk p95 goes to 39.610 with the
     layer's median barely moving, which is exactly the number the bar exists to
     catch. Measured on the way there: the SAME mutation at the collapsed-wedge
     site one branch up (`n_curr_last == n_next_first`) is **INERT, 0 failures**,
     and it is inert for a reason worth writing down rather than a gap — that
     branch emits NO cell at all on the NACA case (both counts come back 3215 and
     12018, unchanged to the cell), so there was nothing for it to mismark. A
     geometry with a merged BL column would reach it; this one does not.
  I. an empty half zero-filled instead of left negative -> 3 failures: check 14's
     line and sidecar, and check 10's both-halves assertion. Check 14's BANNER
     assertion does not move, for injection C's reason one level up — the row
     branches on `cells`, not on the figures — so this rule is guarded at two
     surfaces and not three.
  J. the sidecar's `if (quality.split)` forced true, so a path that made no split
     writes two halves full of negatives -> 1 failure, check 16. Nothing else
     moves: the hybrid path sets `split`, so its own three surfaces are unaffected,
     which is what makes check 16 worth having separately.
  K. `quality.split` left false on the hybrid path, so its sidecar carries no
     halves while its banner and line do -> 2 failures, the sidecar assertion in
     check 13 and in check 14. The banner and the line are untouched: this is the
     "three surfaces disagree" defect, and only the sidecar's two checks see it.
  L. the whole-mesh figures REPLACED by the bulk half (`const ShapeStats st =
     rep.bulk`), the defect the compatibility criterion exists to stop -> 5
     failures: check 9's contrast, three in check 13 and check 15's second. It
     found a REAL DEFECT IN THIS FILE rather than only in the code — check 15's
     second assertion was `line[...] == got[...]`, which is that dict compared with
     itself (`got` is built from those keys) and passed under the mutation. It now
     states something independent: the old tokens describe the WHOLE mesh, with the
     count being both halves', the max the larger half's and the p95 NEITHER half's.

BLIND SPOTS, named rather than papered over:

  * The counts and the collection rules are covered HERE only through one shipped
    mesh each: this file asserts ``cells=15233`` on a real run, not that a
    four-cornered cell is what the non-triangle row counts. Each rule separately
    is ``tests/cpp/test_hybrid_quality.cpp``'s subject since #141.
  * Checks 10 and 12 both land in the ``cells == 0`` branch, so a defect INSIDE it
    reddens both and neither is the other's control. What they separate is the two
    ways in — cells that exist and cannot be measured, and no cells at all — which
    a single fixture would have conflated. The zero-length reduction itself is
    ``tests/cpp/test_cell_shape.cpp`` check 7, with injection D under it.
  * Check 12's config is COMPOSED, not shipped, and deliberately: no shipped config
    declares a domain too small to mesh, and adding one to document a refusal would
    be a case a user could run by accident.
  * Nothing here asserts a bar on any of the three numbers, on purpose (see check
    11). A regression that made every mesh twice as stretched would pass this file
    and would be caught by nobody, because #128 declined to create that gate.
  * The sidecar is parsed for the ``mesh.quality`` object only. Whether every other
    key in it is still right is ``test_provenance_sidecar``'s subject.
  * Check 9's negative control shares this run's config and geometry but NOT its
    cell count (12293 against 15233): the two meshes are different meshes, which is
    the point. It is evidence about where the spread comes from, not a comparison
    of one mesh against itself.
  * Nothing here follows a figure into the GUI or the pipeline. The sidecar is the
    contract; who reads it is another gate's subject — #145's, for the split as
    much as for the whole.
  * WHICH cells carry the boundary layer's mark is not this file's subject and
    cannot be: it asserts that 3215 of 15233 do on one shipped mesh, not that
    every cell `BoundaryLayer::generate` emits is marked and no other cell is.
    That is a property of `src/BoundaryLayer.cpp`'s four call sites, and injection
    H is the measurement that says a missed one is visible here — through the
    figures, at the main stitch site, and NOT at the collapsed-wedge site, which
    this geometry never reaches.
  * The split's arithmetic — that the two halves are two reductions of one
    collection, and that an unmeasurable cell is lost from its own half only — is
    `tests/cpp/test_hybrid_quality.cpp` checks 10 to 13. Here it is visible only as
    the counts adding up on one mesh.
  * The banner's two rows are labelled `boundary layer` and `bulk` while the tokens
    and the sidecar keys say `layer` and `bulk`, so `HALVES` above cannot serve the
    row patterns and both spellings are carried. That is deliberate, not drift: the
    KEYS are what both generation paths share, and the row's words are each path's
    own — the rule `shapePhrase` states in `src/cli.cpp`. Nothing here would catch
    the banner and the keys naming two different SETS under those two spellings;
    what it does catch is the numbers disagreeing, which is check 13.

Run:  python3 tools/PreProcessor/tests/test_hybrid_shape_surface.py
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
# The shipped pair the ticket's demo names, by path. Read by the BINARY, not by
# this file: an edit to either is visible here because the mesher reads it.
_CONF = os.path.join(_REPO, "config", "Background_para.dat")
_GEOM = os.path.join(_REPO, "examples", "geometries", "naca0012.dat")
sys.path.insert(0, _HERE)
# The ONE parser for a quality line, imported from the gate that owns it rather
# than written again here — `.claude/rules/mesher-smoothing.md` forbids the next
# near-copy in as many words. `prefix=` is what #130 added to it, and floating
# EVERY token is check 2's point.
from test_multiblock_quality_surface import qlines  # noqa: E402
from test_multiblock_shape_surface import sidecar  # noqa: E402
from test_multiblock_surface import run as run_conf, write_config, write_topology  # noqa: E402
from mesher_bin import mesher_env as _mesher_env  # noqa: E402

# The keys the figure travels under. Spelled once: every check below builds its
# token names from these, so a rename shows up as one edit here rather than as a
# gate that quietly stopped looking.
PREFIX = "HYBMESH_HYBRID_QUALITY"
METRIC = "tri_edge_ratio"
FIELDS = ("cells", "median", "p95", "max")
# The two halves #143 added, under the naming shape BOTH generation paths use:
# `<metric>_<half>_<field>`. Spelled here once, for the same reason `METRIC` is.
HALVES = ("layer", "bulk")
# Every token the line carried BEFORE #143, spelled as a literal rather than
# rebuilt from `METRIC`: the criterion is that today's greps keep working
# unchanged, and a list derived from the same constants the new tokens are built
# from could not see a rename that moved both together.
LEGACY_TOKENS = ("cells", "tri_edge_ratio_cells", "tri_edge_ratio_median",
                 "tri_edge_ratio_p95", "tri_edge_ratio_max")
# ...and the sidecar keys a reader written before #143 knows, likewise literal.
LEGACY_SIDECAR_KEYS = ("metric", "cells", "median", "p95", "max")
# The other path's, named here so checks 3 and 4 can say what must NOT appear.
MB_PREFIX = "HYBMESH_MB_QUALITY"
MB_METRIC = "quad_midline_ratio"

_HEAD = re.compile(
    r"^  - Cell shape\s+: median ([\d.]+), p95 ([\d.]+), max ([\d.]+) "
    r"\(triangle edge ratio over (\d+) exported triangles")
_NOTMEAS = re.compile(r"^  - Cell shape\s+: not measured\b")
# The two sub-rows #143 puts under that headline. Two patterns rather than one
# with an optional half, because "printed three numbers" and "printed `not
# measured`" are the two states a check has to tell apart.
_SUB = re.compile(
    r"^      (boundary layer|bulk)\s+: median ([\d.]+), p95 ([\d.]+), "
    r"max ([\d.]+) \(over (\d+) ")
_SUB_NM = re.compile(r"^      (boundary layer|bulk)\s+: not measured \((.*)\)$")

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, name, args):
    """One hybrid run on the shipped config. Returns (rc, output, output stem)."""
    stem = os.path.join(tmp, name)
    p = subprocess.run([_BIN, "-conf", _CONF] + list(args)
                       + ["-out_name", stem + ".vtk"],
                       cwd=tmp, env=_mesher_env(), capture_output=True,
                       text=True, timeout=1800)
    return p.returncode, (p.stdout or "") + (p.stderr or ""), stem


def banner(out):
    """The ``Cell shape`` row's numbers, or None when it said ``not measured``.

    Returns (numbers or None, the whole row text or None). The row text is what
    check 5 reads, because the distinction between the two metrics is a SENTENCE
    and not a number.
    """
    for line in out.splitlines():
        if not line.startswith("  - Cell shape"):
            continue
        m = _HEAD.match(line)
        if m:
            return ({"median": float(m.group(1)), "p95": float(m.group(2)),
                     "max": float(m.group(3)), "cells": float(m.group(4))}, line)
        return None, line
    return None, None


def shape_of(q):
    """The four shape figures off a parsed machine line, or None if absent."""
    if q is None or any(METRIC + "_" + f not in q for f in FIELDS):
        return None
    return {f: q[METRIC + "_" + f] for f in FIELDS}


def line_of(out):
    got = qlines(out, prefix=PREFIX)
    return got[0] if got else None


def half_of(q, half):
    """One half's four figures off a parsed machine line, or None if absent."""
    if q is None or any(f"{METRIC}_{half}_{f}" not in q for f in FIELDS):
        return None
    return {f: q[f"{METRIC}_{half}_{f}"] for f in FIELDS}


def sub_rows(out, reasons=None):
    """The two split rows under the `Cell shape` headline, by label.

    Maps the label to its four figures, or to None where the row said
    ``not measured``. A label that is absent altogether is absent from the map,
    which is what lets a check tell "printed nothing" from "printed nothing
    measurable". Pass a dict as ``reasons`` to collect the PARENTHETICAL of each
    unmeasured row — what the banner says about WHY, which check 10 reads because
    a row can print the right state and the wrong reason for it.
    """
    if reasons is None:
        reasons = {}
    rows = {}
    for line in out.splitlines():
        m = _SUB.match(line)
        if m:
            rows[m.group(1)] = {"median": float(m.group(2)),
                                "p95": float(m.group(3)),
                                "max": float(m.group(4)),
                                "cells": float(m.group(5))}
            continue
        m = _SUB_NM.match(line)
        if m:
            rows[m.group(1)] = None
            reasons[m.group(1)] = m.group(2)
    return rows


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP  build/HybMesh2D not built; nothing to measure.")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # ── the ticket's own demo ────────────────────────────────────────────
        rc, out, stem = run(tmp, "naca", ["-geom", _GEOM])
        check(f"the shipped hybrid case runs and exits 0 (got {rc})", rc == 0)

        # --- 1. the banner row, inside the Mesh Statistics block -------------
        head, row = banner(out)
        check("1. the Mesh Statistics block carries a Cell shape row with median, "
              "p95, max and the count of exported triangles", head is not None)
        stats = [i for i, ln in enumerate(out.splitlines())
                 if ln.startswith("[ Mesh Statistics ]")]
        rows = [i for i, ln in enumerate(out.splitlines())
                if ln.startswith("  - Cell shape")]
        check("1. ...and it is IN that block, under the vertex and element counts, "
              "rather than in a report of its own",
              len(stats) == 1 and len(rows) == 1 and rows[0] > stats[0])
        if head is None:
            return 1

        # --- 2/3. the machine line ------------------------------------------
        line = line_of(out)
        check(f"2. one {PREFIX} line is emitted, and every token on it is "
              f"key=<float> — the shape the ONE parser reads", line is not None)
        got = shape_of(line)
        check(f"2. ...carrying every {METRIC}_* field", got is not None)
        # CHECKS 3 AND 4 RUN BEFORE ANY BAIL-OUT, and that is not tidiness: the
        # defect they are labelled for — this line wearing the OTHER path's metric
        # name — also empties `got`, so behind an early return the one check written
        # for it never ran and check 2 reported the bite instead. Measured: injection
        # A reddened check 2 alone until this moved.
        # THE MESSAGE NAMES BOTH CONDITIONS THE ASSERT TESTS (#114): with no line at
        # all this cannot confirm the property, and saying only "no such token" would
        # read as a pass-shaped failure. Presence is check 2's subject; this one
        # fails on it too rather than asserting something about nothing.
        check(f"3. a {PREFIX} line exists and the metric's name is IN THE KEY: no "
              f"{MB_METRIC}* token is on it", line is not None
              and not any(k.startswith(MB_METRIC) for k in line))
        check(f"4. a hybrid run prints no {MB_PREFIX} line and never names "
              f"{MB_METRIC}",
              not qlines(out) and MB_METRIC not in out)
        if got is None or line is None:
            return 1
        check("2. ...beside the count of cells EXPORTED, so the gap between what "
              "was offered and what was measured is on the line rather than "
              f"inferred (cells={line.get('cells')}, measured={got['cells']})",
              "cells" in line and line["cells"] >= got["cells"])

        # --- 4. the other direction ------------------------------------------
        topo = write_topology(os.path.join(tmp, "sq.json"), ni=5, nj=4)
        mstem = os.path.join(tmp, "mbout")
        mconf = write_config(os.path.join(tmp, "mb.dat"), topo, mstem)
        mrc, mout = run_conf(tmp, mconf)
        check(f"4. ...and a multi-block run prints no {PREFIX} line and never "
              f"names {METRIC} (rc {mrc})",
              mrc == 0 and not qlines(mout, prefix=PREFIX) and METRIC not in mout)

        # --- 16. A PATH THAT DOES NOT SPLIT WRITES NEITHER KEY ---------------
        # `MeshQuality::split` is a state of its own, separate from a half that
        # was measured and came back empty: a sidecar from a path that never made
        # the split must carry no `layer` and no `bulk`, not two objects full of
        # negatives that a reader would take for "we looked and found nothing".
        # The multi-block path is today's only witness to that state, and it stops
        # being one the moment #144 splits its wall band — THIS CHECK IS THEN THE
        # ONE TO UPDATE, deliberately, and the naming shape it must match is
        # `<metric>_layer_*` / `<metric>_bulk_*`, settled here because this ticket
        # landed first.
        mside = sidecar(mstem)
        check("16. the multi-block sidecar carries its whole-mesh quality and "
              "NEITHER split key, because that path does not split yet — a path "
              "that does not split writes no half rather than an empty one "
              f"({sorted(mside or {})})",
              mside is not None and mside.get("metric") == MB_METRIC
              and not any(h in mside for h in HALVES))
        check("16. ...and its machine line carries no half's tokens either, so "
              "the two paths' reports cannot be told one story by a reader "
              "greping for a half",
              not any(f"{MB_METRIC}_{h}_" in mout for h in HALVES))

        # --- 5. the distinction, on BOTH banners -----------------------------
        _, mrow = banner(mout)
        check("5. the hybrid Cell shape row names the multi-block metric as not "
              f"comparable ({row!r})",
              row is not None and "NOT comparable" in row
              and "quad midline ratio" in row)
        check("5. ...and the multi-block Cell shape row names this one, so the "
              "warning reaches a reader of EITHER report",
              mrow is not None and "NOT comparable" in mrow
              and "triangle edge ratio" in mrow)

        # --- 6/7. the sidecar, and all three agreeing ------------------------
        side = sidecar(stem)
        check("6. the sidecar beside the mesh carries mesh.quality", side is not None)
        if side is not None:
            check(f"6. ...naming the metric ({side.get('metric')!r})",
                  side.get("metric") == METRIC)
            check("7. ...with the SAME four numbers as the machine line",
                  all(float(side.get(f, -99)) == got[f] for f in FIELDS))
        check("7. ...and the banner prints those same numbers to the three "
              "decimals it shows",
              all(abs(head[f] - got[f]) < 5e-4 for f in ("median", "p95", "max"))
              and head["cells"] == got["cells"])

        # --- 8. orderly, and above the metric's floor ------------------------
        check(f"8. median <= p95 <= max ({got['median']:.3f} <= {got['p95']:.3f} "
              f"<= {got['max']:.3f})", got["median"] <= got["p95"] <= got["max"])
        check("8. ...and the median is at or above 1.0, the metric's floor, so an "
              "absent measurement cannot reach a user as a number",
              got["median"] >= 1.0)

        # --- 9. the boundary layer is what the spread is ---------------------
        rc2, out2, stem2 = run(tmp, "nobl", ["-geom_nobl", _GEOM])
        flat = shape_of(line_of(out2))
        check(f"9. the same config and geometry with NO layer grown also reports "
              f"its figures (rc {rc2})", rc2 == 0 and flat is not None)
        if flat is not None:
            check("9. ...with a median within 10% of the BL run's "
                  f"({flat['median']:.3f} against {got['median']:.3f}), so the two "
                  "meshes are ordinarily shaped in the bulk",
                  abs(flat["median"] - got["median"]) / got["median"] < 0.10)
            check("9. ...and a p95 and a max an order of magnitude smaller "
                  f"(p95 {flat['p95']:.3f} against {got['p95']:.3f}, max "
                  f"{flat['max']:.3f} against {got['max']:.3f}) — so the spread the "
                  "median and p95 exist to separate IS the boundary layer, measured "
                  "rather than claimed",
                  flat["p95"] * 10 < got["p95"] and flat["max"] * 10 < got["max"])

        # --- 13. THE SPLIT: the boundary layer's cells apart from the rest ----
        # #143's subject. Check 9 above measures the same fact with two MESHES —
        # one grown, one not — which is evidence about where the spread comes
        # from. This is the tool making the split itself, on the one mesh a user
        # actually has.
        lay = half_of(line, "layer")
        blk = half_of(line, "bulk")
        check("13. the machine line carries both halves as key=<float> tokens "
              f"under {METRIC}_layer_* and {METRIC}_bulk_*",
              lay is not None and blk is not None)
        subs = sub_rows(out)
        check("13. ...and the banner prints them as two rows under the headline, "
              f"under distinct labels ({sorted(subs)})",
              set(subs) == {"boundary layer", "bulk"})
        if lay is None or blk is None:
            return 1
        check("13. ...the two halves partition what the whole set measured, so "
              "no cell is counted twice and none is lost between them "
              f"({lay['cells']:.0f} + {blk['cells']:.0f} = {got['cells']:.0f})",
              lay["cells"] + blk["cells"] == got["cells"])
        check("13. ...and the boundary layer is MORE THAN 5% of the measured "
              f"cells ({100.0 * lay['cells'] / got['cells']:.1f}%), which is why "
              "the whole-mesh p95 is a boundary-layer figure on this mesh",
              lay["cells"] > 0.05 * got["cells"])
        # THE BAR THE TICKET ASKS FOR, and the only numeric one in this file: it
        # proves the split DOES something rather than merely exists. Two sides on
        # purpose — a bulk p95 under 2 alone would also pass if the split silently
        # measured nothing, and a whole-mesh p95 over 40 alone is check 9's fact.
        check("13. ...the BULK p95 is below 2 while the WHOLE-MESH p95 is above "
              f"40 (bulk {blk['p95']:.3f}, whole {got['p95']:.3f}) — the number "
              "that answers \"what shape is the rest of my mesh\" is now reported "
              "rather than left to be inferred from the median",
              blk["p95"] < 2.0 and got["p95"] > 40.0)
        check("13. ...and the layer half is where the stretch went, ordered and "
              f"above the metric's floor (median {lay['median']:.3f}, p95 "
              f"{lay['p95']:.3f}, max {lay['max']:.3f})",
              1.0 <= lay["median"] <= lay["p95"] <= lay["max"]
              and lay["median"] > blk["p95"])
        check("13. ...the banner's two rows print the machine line's numbers to "
              "the three decimals they show, over the same two counts",
              all(subs[lbl] is not None
                  and abs(subs[lbl][f] - h[f]) < 5e-4
                  for lbl, h in (("boundary layer", lay), ("bulk", blk))
                  for f in ("median", "p95", "max"))
              and subs["boundary layer"]["cells"] == lay["cells"]
              and subs["bulk"]["cells"] == blk["cells"])
        check("13. ...and the sidecar carries both halves under mesh.quality, to "
              "the digit, so the three surfaces tell one story about the split "
              "as they already do about the whole",
              side is not None
              and all(isinstance(side.get(h), dict)
                      and all(float(side[h][f]) == ({"layer": lay,
                                                     "bulk": blk}[h])[f]
                              for f in FIELDS)
                      for h in HALVES))
        check("13. ...the whole-mesh figures are UNTOUCHED by the split: the max "
              f"is still the layer's ({got['max']:.3f})",
              got["max"] == lay["max"] and got["max"] > blk["max"])

        # --- 14. AN EMPTY HALF IS `not measured`, NOT 0.0 --------------------
        # An ordinary case on this path, not an error: check 9's own `-geom_nobl`
        # run grows no layer at all. Driven off that same run rather than a
        # second one.
        nsubs = sub_rows(out2)
        nlay = half_of(line_of(out2), "layer")
        nblk = half_of(line_of(out2), "bulk")
        check("14. a geometry meshed with NO boundary layer prints `not "
              f"measured` for that half rather than 0.0 ({nsubs})",
              nsubs.get("boundary layer", "missing") is None)
        check("14. ...and the half's four tokens are on the line with 0 cells "
              "and three NEGATIVE figures — on a metric whose floor is 1.0 a 0.0 "
              "could only ever be an absent measurement wearing a number",
              nlay is not None and nlay["cells"] == 0
              and all(nlay[f] < 0.0 for f in ("median", "p95", "max")))
        check("14. ...while the bulk half is the whole mesh, reporting the same "
              "figures rather than a blank",
              nblk is not None and flat is not None
              and all(nblk[f] == flat[f] for f in FIELDS))
        nside = sidecar(stem2)
        check("14. ...and the sidecar says the same, so a later reader cannot "
              "read an empty half as a measured 0",
              nside is not None and isinstance(nside.get("layer"), dict)
              and nside["layer"].get("cells") == 0
              and all(float(nside["layer"][f]) < 0.0
                      for f in ("median", "p95", "max")))

        # --- 15. TODAY'S SPELLINGS STILL READ THE WHOLE MESH -----------------
        # The compatibility half of the criteria, asserted against LITERAL names
        # rather than names rebuilt from the constants the new tokens are built
        # from — a rename that moved both together would be invisible to those.
        check("15. every token the line carried before the split is still on it, "
              f"spelled as it was ({', '.join(LEGACY_TOKENS)})",
              all(k in line for k in LEGACY_TOKENS))
        # NOT `line[...] == got[...]`, which is that dict compared with itself:
        # `got` IS built from those keys. The independent statement is that the
        # old tokens describe the WHOLE mesh and not one half — the count is both
        # halves' and the max is the larger half's, while the p95 is NEITHER
        # half's, which is the defect this criterion exists to stop (the split
        # quietly replacing the figures instead of landing beside them).
        check("15. ...and they still carry the WHOLE-MESH figures rather than a "
              "half's, so a grep written against the old line reads the mesh it "
              f"always read (p95 {line['tri_edge_ratio_p95']:.3f}, against "
              f"{lay['p95']:.3f} and {blk['p95']:.3f})",
              line["tri_edge_ratio_cells"] == lay["cells"] + blk["cells"]
              and line["tri_edge_ratio_max"] == max(lay["max"], blk["max"])
              and line["tri_edge_ratio_p95"] not in (lay["p95"], blk["p95"]))
        check("15. ...the sidecar's mesh.quality still carries every key a reader "
              "written before the split knows, at the top of the object "
              f"({', '.join(LEGACY_SIDECAR_KEYS)})",
              side is not None and all(k in side for k in LEGACY_SIDECAR_KEYS))
        check("15. ...holding the whole-mesh figures there, not one half's",
              side is not None
              and all(float(side[f]) == got[f] for f in ("median", "p95", "max")))

        # --- 10. not measured, through the binary ----------------------------
        # No geometry, no seed, no domain file: this path falls back to a Cartesian
        # QUAD mesh, and a quad carries no triangle edge ratio.
        rc3, out3, stem3 = run(tmp, "cart", [])
        head3, row3 = banner(out3)
        line3 = line_of(out3)
        got3 = shape_of(line3)
        check(f"10. the quad fallback still runs and exits 0 (rc {rc3})", rc3 == 0)
        check(f"10. ...the banner prints `not measured` ({row3!r})",
              head3 is None and row3 is not None and _NOTMEAS.match(row3))
        check("10. ...naming how many exported cells this metric is not defined "
              "for, rather than describing the mesh by a fraction of itself",
              "not triangles" in out3)
        check("10. ...the machine line reports 0 measured cells and every figure "
              "NEGATIVE, never 0.0 — which on a metric whose floor is 1.0 could "
              "only ever be an absent measurement wearing a number",
              got3 is not None and got3["cells"] == 0
              and all(got3[f] < 0.0 for f in ("median", "p95", "max")))
        check("10. ...and it did export cells, so this is a mesh nothing could be "
              "measured on and not an empty one",
              line3 is not None and line3.get("cells", 0) > 0)
        why3 = {}
        check("10. ...BOTH halves read `not measured` too: a mesh whose cells "
              "none could be measured has no measurable layer and no measurable "
              "bulk, and the split must not turn either into a 0.0",
              set(sub_rows(out3, why3)) == {"boundary layer", "bulk"}
              and all(v is None for v in sub_rows(out3).values())
              and all(half_of(line3, h) is not None
                      and half_of(line3, h)["cells"] == 0
                      and all(half_of(line3, h)[f] < 0.0
                              for f in ("median", "p95", "max"))
                      for h in HALVES))
        # AND SAYS SOMETHING TRUE ABOUT WHY. `cells 0` on a half has two ways in —
        # no such cell existed, or none of them could be measured — and this mesh
        # is the second: 400 quads DO sit outside the boundary layer. A row
        # reading `(no cells outside the boundary layer)` would be a false claim
        # about the mesh, which is the defect this assertion exists for; the
        # headline row one line up has always been careful in the same way.
        check(f"10. ...and NEITHER row claims the cells are absent ({why3})",
              set(why3) == {"boundary layer", "bulk"}
              and all(w.endswith("could be measured") and "none of the" in w
                      for w in why3.values()))
        side3 = sidecar(stem3)
        check("10. ...and the sidecar carries the same unmeasured state, so a "
              "later reader cannot tell a different story from the banner's",
              side3 is not None and side3.get("metric") == METRIC
              and side3.get("cells") == 0
              and all(float(side3.get(f, 0.0)) < 0.0
                      for f in ("median", "p95", "max")))

        # --- 12. a mesh with NO CELLS AT ALL ---------------------------------
        # A domain smaller than one far-field cell: the Cartesian fallback refuses
        # by name and the run goes on with an empty mesh. A DIFFERENT input from
        # check 10's, reaching the same branch — which is the criterion's literal
        # wording ("a mesh with no cells"), not a mesh whose cells went unmeasured.
        empty_conf = os.path.join(tmp, "empty.dat")
        with open(empty_conf, "w", encoding="utf-8") as f:
            f.write("DOMAIN_X_MIN 0.0\nDOMAIN_X_MAX 0.001\n"
                    "DOMAIN_Y_MIN 0.0\nDOMAIN_Y_MAX 0.001\n"
                    "FARFIELD_MESH_SIZE 1.0\nEXPORT_VTK 1\nEXPORT_STARCD 0\n")
        estem = os.path.join(tmp, "empty")
        pe = subprocess.run([_BIN, "-conf", empty_conf, "-out_name", estem + ".vtk"],
                            cwd=tmp, env=_mesher_env(), capture_output=True,
                            text=True, timeout=600)
        eout = (pe.stdout or "") + (pe.stderr or "")
        ehead, erow = banner(eout)
        eline = line_of(eout)
        egot = shape_of(eline)
        check("12. a domain too small to mesh really does leave NO cells "
              f"(rc {pe.returncode})",
              pe.returncode == 0 and "  - Elements (CEL)       : 0" in eout)
        check(f"12. ...and the banner still prints `not measured` ({erow!r})",
              ehead is None and erow is not None and _NOTMEAS.match(erow))
        check("12. ...over 0 offered and 0 measured cells, every figure negative — "
              "a figure computed off nothing is what the negatives exist to refuse",
              egot is not None and eline is not None and eline.get("cells") == 0
              and egot["cells"] == 0
              and all(egot[f] < 0.0 for f in ("median", "p95", "max")))
        eside = sidecar(estem)
        check("12. ...and the sidecar beside the empty export says the same",
              eside is not None and eside.get("metric") == METRIC
              and eside.get("cells") == 0
              and all(float(eside.get(f, 0.0)) < 0.0
                      for f in ("median", "p95", "max")))

        # --- 11. no colour, no threshold -------------------------------------
        # EVERY WORD IN THE MESSAGE IS IN THE TUPLE: a check whose prose is wider
        # than its assert is inert in exactly the gap between them (#114).
        _GRADED = ("PASS", "WARN", "FAIL", "too ", "threshold", "exceeds")
        check("11. the shipped case's max is what the wall spacing asks for and "
              f"the run exits 0 (max {got['max']:.3f}, rc {rc}); nothing in the "
              "report colours or grades it: none of "
              + ", ".join(repr(w) for w in _GRADED)
              + " sits on the Cell shape rows",
              rc == 0 and not any(w in ln for ln in out.splitlines()
                                  if ln.startswith("  - Cell shape")
                                  or ln.lstrip().startswith("not triangles")
                                  or _SUB.match(ln) or _SUB_NM.match(ln)
                                  for w in _GRADED))

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print("  - " + f)
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
