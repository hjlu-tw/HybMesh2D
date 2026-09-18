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
     this file asserts none.

MEASURED 2026-09-17, on the shipped config at its shipped values:

    naca0012, BL on     15233 exported triangles, all measured
                        median 1.158103, p95 52.185741, max 78.703074
    naca0012, -geom_nobl 12293 exported triangles
                        median 1.114486, p95 1.420814, max 7.388082
    no geometry at all    400 exported quads, 0 measured
                        median/p95/max all -1.0, banner "not measured"
    domain 1e-3 wide      0 nodes, 0 elements, 0 offered, 0 measured
                        median/p95/max all -1.0, banner "not measured"

Those figures are a RECORD of this dated run; the bars this file asserts are
structural (ordering, agreement, the BL/no-BL contrast) rather than numeric, so the
record is not a threshold in disguise.

INJECTIONS, run 2026-09-17 against `src/cli.cpp` with a rebuild per mutation, and
recorded here because a C++ defect cannot be injected from inside a Python gate.
THE CODE B AND C MUTATE HAS MOVED: #141 lifted the cell collection into
`src/HybridQuality.cpp`, so an injector repeating them edits that file now — B's
corner-count guard and C's negative figures both live there, while A, D, E and F
(the names, the prefix and the two banner sentences) are still `src/cli.cpp`'s.
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
    contract; who reads it is another gate's subject.

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
# The other path's, named here so checks 3 and 4 can say what must NOT appear.
MB_PREFIX = "HYBMESH_MB_QUALITY"
MB_METRIC = "quad_midline_ratio"

_HEAD = re.compile(
    r"^  - Cell shape\s+: median ([\d.]+), p95 ([\d.]+), max ([\d.]+) "
    r"\(triangle edge ratio over (\d+) exported triangles")
_NOTMEAS = re.compile(r"^  - Cell shape\s+: not measured\b")

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
        rc2, out2, _ = run(tmp, "nobl", ["-geom_nobl", _GEOM])
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
