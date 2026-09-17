#!/usr/bin/env python3
"""The multi-block CELL SHAPE figures, through the real binary on the shipped cases
(issue #129, parent #128).

The arithmetic is pinned next door in ``tests/cpp/test_cell_shape.cpp`` (a square
is 1.0, a degenerate cell does not divide by zero, how p95 is ranked) and which
cells feed it in ``tests/cpp/test_mb_quality.cpp`` check 9. What can only be
checked out here is the half that IS the ticket: that THREE SURFACES agree about
one mesh — the banner a user reads, the machine-readable line a script greps, and
the ``.provenance.json`` sidecar every later reader consumes — and that the figure
does not move when ``MB_SPLIT_QUADS`` does.

Run on the SHIPPED configs, read from disk through the one retargeter, because
the demo in the ticket is ``./run.sh -conf config/multiblock_ogrid.dat`` and a
composed equivalent would leave an edit to that file invisible from here.

What this pins down:

  1. The banner gains a ``Cell shape`` row carrying median, p95 and max, and says
     over how many STRUCTURED quads — a different count from the ``Inverted
     cells`` row's, which counts what was exported.
  2. One row PER BLOCK under it, named with the id the topology document gave the
     block, the way each wall gets a row under the wall headline. The H-grid is
     what makes that worth having: its four blocks report four different medians.
  3. The machine-readable line carries the four figures as ``key=value`` in the
     existing shape, so an acceptance check stays a grep. It is read with the ONE
     parser the quality gate owns, which floats every token — so a string-valued
     token on that line would fail here rather than silently breaking five gates.
  4. The METRIC'S NAME IS IN THE KEY (``quad_midline_ratio_*``). The hybrid path's
     figure is a different quantity under a different name, and a grep must not be
     able to confuse them.
  5. The sidecar's ``mesh.quality`` object holds the same numbers, under a
     ``metric`` that names the quantity. Parsed as JSON out of a file a real run
     produced, never asserted against a writer.
  6. THE SAME NUMBERS, to the digit, in all three places. This is what "one owner"
     means operationally.
  7. INDEPENDENT OF ``MB_SPLIT_QUADS``: the same shipped case at 0 exports half as
     many cells and reports the four figures BITWISE unchanged.
  8. Every figure is at or above 1.0 and ordered median <= p95 <= max, on both
     cases. 1.0 is the metric's floor, so this is what stops an absent measurement
     reaching a user as a number.
  9. NO THRESHOLD AND NO FAILURE: the shipped O-grid's max is ~32.8 and the run
     exits 0. That number is the azimuthal spacing over the requested
     ``BL_INITIAL_THICKNESS``, i.e. what the user asked for, and a tool that
     coloured it red would be training them to ignore colour.
 10. Shape is not inversion: the deliberately folded dart exits 9 with inverted
     cells AND still reports shape figures, so neither figure is the other wearing
     a different name.

MEASURED 2026-09-17, at the shipped defaults (``MB_SMOOTH_ITERS`` 20):

    shipped O-grid  4608 structured quads, 9216 exported triangles
                    median 1.845977, p95 23.662285, max 32.767868
    shipped H-grid    80 structured quads,  160 exported triangles
                    median 1.164421, p95 1.391410, max 1.504321
                    per block: bl 1.156, br 1.249, tl 1.080, tr 1.389 (medians)

The O-grid's spread is the ticket's own headline number and its arithmetic is in
#128: 0.0327 azimuthal spacing / 0.001 requested first-cell height = 32.7. Those
figures are a RECORD of this dated run; the bars this file asserts are structural
(ordering, agreement, independence) rather than numeric, so the record is not a
threshold in disguise. ``test_multiblock_quality_gate.py`` owns the numeric bars
for this path, and deliberately gains none here: #128 rules out a pass/fail
threshold on the shape figures.

CHECK 6 IS KNOWN TO BITE, by accident and on the day it was written: its first
draft read the FIRST ``Cell shape`` row out of the output, which on a smoothed run
(the shipped default since #85) is the report for the mesh BEFORE the sweeps — a
mesh that was never exported. It compared that against the after-smoothing machine
line and went red on both cases, naming the disagreement. The fix is in
``last_report`` and is the same trailing-space rule ``qlines`` carries for its own
prefix.

BLIND SPOTS, named rather than papered over:

  * ``not measured`` IS NOT REACHED HERE, and not for want of trying: every
    declaration this path ACCEPTS produces at least one structured quad — an edge
    with ``count`` 1 is refused by name ("an edge needs at least 2 nodes"), so
    there is no valid document that fills no measurable cell. The row-level and
    headline-level halves of that rule are therefore pinned where a mesh can be
    built by hand, in ``tests/cpp/test_mb_quality.cpp`` checks 8 and 9d; what is
    NOT covered anywhere is the banner STRING for that state, in ``src/cli.cpp``.
  * Nothing here asserts a bar on any of the three numbers, on purpose (see
    above). A regression that made every mesh twice as stretched would pass this
    file and would be caught by nobody, because #128 declined to create that gate.
  * The sidecar is parsed for the ``mesh.quality`` object only. Whether every
    other key in it is still right is ``test_provenance_sidecar``'s subject, not
    this file's.
  * The per-block rows are checked for presence, naming and count, and their
    numbers are checked for ordering — not against the per-block cells, which no
    machine-readable line carries. A row that reported the WRONG block's figures
    would pass here; ``tests/cpp/test_mb_quality.cpp`` check 9d is where a row is
    tied to its block.

Run:  python3 tools/PreProcessor/tests/test_multiblock_shape_surface.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
sys.path.insert(0, _HERE)
# The ONE shipped-config retargeter (#126) and, for the O-grid, the wrapper that
# knows that case's own share of the retargeting. `test_shipped_config_seam.py`
# derives the set of retargeters from the tree and fails on a second, so this file
# defines none.
from mb_shipped_config import shipped_config  # noqa: E402
from test_multiblock_ogrid_surface import base_config as ogrid_config  # noqa: E402
# The ONE parser for the quality line, imported from the gate that owns it rather
# than written again here — `.claude/rules/mesher-smoothing.md` forbids the fourth
# near-copy in as many words. It floats EVERY token, which is check 3's point.
from test_multiblock_quality_surface import qlines  # noqa: E402
from test_multiblock_quality_surface import DART  # noqa: E402
from test_multiblock_surface import run as run_conf, write_config, write_topology  # noqa: E402
from mesher_bin import mesher_env as _mesher_env  # noqa: E402

# The four keys the figure travels under on the machine-readable line. Spelled
# once: every check below builds its token names from these, so a rename shows up
# as one edit here rather than as a gate that quietly stopped looking.
METRIC = "quad_midline_ratio"
FIELDS = ("cells", "median", "p95", "max")

# The banner's headline row and its per-block rows.
_HEAD = re.compile(
    r"^  - Cell shape\s+: median ([\d.]+), p95 ([\d.]+), max ([\d.]+) "
    r"\(quad midline ratio over (\d+) structured quads")
_ROW = re.compile(r"^      block '([^']+)'\s+: (.+)$")
_ROWNUM = re.compile(r"^median ([\d.]+), p95 ([\d.]+), max ([\d.]+)$")

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, name, config_text):
    """Run one config, returning (exit code, output, output stem)."""
    stem = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".dat")
    with open(conf, "w", encoding="utf-8") as f:
        f.write(config_text.replace("@STEM@", stem))
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=900)
    return p.returncode, (p.stdout or "") + (p.stderr or ""), stem


def last_report(out):
    """The LAST ``Cell shape`` block: ``(headline numbers or None, {block: text})``.

    ONE WALK, because both halves need the same answer to the same question — which
    of the report's two copies describes the mesh on disk — and two walks is two
    places for that answer to drift. THE LAST ONE, and the trailing-space rule
    ``qlines`` follows is why this has to be said: a smoothed run prints the whole
    quality block TWICE, and the first is the mesh BEFORE the sweeps, a mesh that
    was never exported. The first draft took the first match and compared the
    before-banner against the after-machine-line, which reddened check 6 on both
    cases — which is how this gate is known to bite.

    The headline is None when the row said ``not measured`` (or is absent); the rows
    are whatever text each block carried, parsed by the caller.
    """
    head, rows = None, {}
    seen = False
    for line in out.splitlines():
        if line.startswith("  - Cell shape"):
            m = _HEAD.match(line)
            head = ({"median": float(m.group(1)), "p95": float(m.group(2)),
                     "max": float(m.group(3)), "cells": float(m.group(4))}
                    if m else None)
            rows, seen = {}, True
            continue
        if not seen:
            continue
        m = _ROW.match(line)
        if m:
            rows[m.group(1)] = m.group(2).strip()
        elif line.strip() and not line.startswith("      "):
            seen = False
    return head, rows


def sidecar(stem):
    """The ``mesh.quality`` object beside a run's output, or None."""
    path = stem + ".provenance.json"
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("mesh", {}).get("quality")


def quality(out):
    got = qlines(out)
    return got[0] if got else None


def shape_of(q):
    """The four shape figures off a parsed machine line, or None if absent."""
    if q is None or any(METRIC + "_" + f not in q for f in FIELDS):
        return None
    return {f: q[METRIC + "_" + f] for f in FIELDS}


def one_case(tmp, name, config_text, blocks):
    """Checks 1-8 for one shipped case."""
    rc, out, stem = run(tmp, name, config_text)
    check(f"{name}: the shipped case runs and exits 0 (got {rc})", rc == 0)

    # --- 1. the banner row ---------------------------------------------------
    head, rows = last_report(out)
    check(f"{name}: 1. the banner carries a Cell shape row with median, p95, max "
          f"and the count of structured quads", head is not None)
    if head is None:
        return
    line = quality(out)
    check(f"{name}: 1. ...and the machine line is present", line is not None)
    if line is None:
        return
    check(f"{name}: 1. ...over FEWER cells than were exported ({head['cells']:.0f} "
          f"structured quads against {line['cells']:.0f} exported cells), because "
          f"the figure is measured on the cell the DOCUMENT declares",
          head["cells"] < line["cells"])

    # --- 2. one row per block ------------------------------------------------
    check(f"{name}: 2. one row per block, named by the document's own block ids "
          f"({sorted(rows)})", sorted(rows) == sorted(blocks))
    parsed = {b: _ROWNUM.match(t) for b, t in rows.items()}
    check(f"{name}: 2. ...each carrying its own three figures",
          all(m is not None for m in parsed.values()))

    # --- 3/4. the machine line -----------------------------------------------
    got = shape_of(line)
    check(f"{name}: 3. the machine line carries every {METRIC}_* field as a "
          f"key=value float", got is not None)
    if got is None:
        return
    check(f"{name}: 4. ...and the metric's name is IN THE KEY, so a grep for the "
          f"hybrid path's tri_edge_ratio cannot match this line",
          not any(k.startswith("tri_edge_ratio") for k in line))

    # --- 5/6. the sidecar, and all three agreeing ----------------------------
    side = sidecar(stem)
    check(f"{name}: 5. the sidecar beside the mesh carries mesh.quality",
          side is not None)
    if side is not None:
        check(f"{name}: 5. ...naming the metric ({side.get('metric')!r})",
              side.get("metric") == METRIC)
        check(f"{name}: 6. ...with the SAME four numbers as the machine line",
              all(float(side.get(f, -99)) == got[f] for f in FIELDS))
    check(f"{name}: 6. ...and the banner prints those same numbers to the three "
          f"decimals it shows",
          all(abs(head[f] - got[f]) < 5e-4 for f in ("median", "p95", "max"))
          and head["cells"] == got["cells"])

    # --- 8. the figures are orderly, and above the metric's floor ------------
    check(f"{name}: 8. median <= p95 <= max "
          f"({got['median']:.3f} <= {got['p95']:.3f} <= {got['max']:.3f})",
          got["median"] <= got["p95"] <= got["max"])
    check(f"{name}: 8. ...and the median is at or above 1.0, the metric's floor, "
          f"so an absent measurement cannot reach a user as a number",
          got["median"] >= 1.0)
    for b, m in parsed.items():
        if m is None:
            continue
        lo, mid, hi = float(m.group(1)), float(m.group(2)), float(m.group(3))
        check(f"{name}: 8. ...and block {b!r}'s own row is ordered and above 1.0",
              1.0 <= lo <= mid <= hi)

    # --- 7. independent of MB_SPLIT_QUADS ------------------------------------
    off = config_text.replace("MB_SPLIT_QUADS 1", "MB_SPLIT_QUADS 0")
    check(f"{name}: 7. the shipped config really declares MB_SPLIT_QUADS 1, so "
          f"turning it off is a change", off != config_text)
    rc2, out2, _ = run(tmp, name + "_quads", off)
    check(f"{name}: 7. ...and the run with quads exits 0 (got {rc2})", rc2 == 0)
    line2 = quality(out2)
    got2 = shape_of(line2)
    check(f"{name}: 7. ...reporting its figures too", got2 is not None)
    if got2 is None or line2 is None:
        return
    # NEGATIVE CONTROL, computed rather than claimed: the split really did change
    # what was exported, so "unchanged" below is a measurement and not two runs of
    # the same thing.
    check(f"{name}: 7. ...off EXACTLY HALF the exported cells ({line2['cells']:.0f} "
          f"quads against {line['cells']:.0f} triangles), so the two runs really "
          f"did export different meshes", line["cells"] == 2 * line2["cells"])
    check(f"{name}: 7. ...and the four shape figures are BITWISE identical, so "
          f"turning the split off to diagnose a mesh does not change the number "
          f"being diagnosed", got == got2)


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP  build/HybMesh2D not built; nothing to measure.")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # The two shipped cases the ticket names, each read from disk.
        one_case(tmp, "ogrid", ogrid_config(), ["q0", "q1", "q2", "q3"])
        one_case(tmp, "hgrid", shipped_config("multiblock_hgrid"),
                 ["bl", "br", "tl", "tr"])

        # --- 9. a correct large number is not a failure ----------------------
        rc, out, _ = run(tmp, "ogrid_again", ogrid_config())
        got = shape_of(quality(out))
        check("9. the shipped O-grid's max is the ~32.8 #128 measured — the "
              "azimuthal spacing over the requested BL_INITIAL_THICKNESS — and "
              f"the run still exits 0 (max {got['max'] if got else '?'}, rc {rc})",
              rc == 0 and got is not None and 30.0 < got["max"] < 35.0)
        # EVERY WORD IN THE MESSAGE IS IN THE TUPLE, and that is not pedantry: a
        # check whose prose is wider than its assert is inert in exactly the gap
        # between them, which is the shape #114 recorded. The first draft named
        # PASS in the sentence and left it out of the tuple.
        _GRADED = ("PASS", "WARN", "FAIL", "too ", "threshold", "exceeds")
        check("9. ...and nothing in the report colours or grades it: none of "
              + ", ".join(repr(w) for w in _GRADED)
              + " sits on the Cell shape rows",
              not any(w in ln for ln in out.splitlines()
                      if "Cell shape" in ln or _ROW.match(ln)
                      for w in _GRADED))

        # --- 10. shape is not inversion --------------------------------------
        # The deliberately folded dart the quality gate owns. It exits 9 with
        # inverted cells and IS still measured for shape, so neither figure is the
        # other wearing a different name.
        topo = write_topology(os.path.join(tmp, "dart.json"), ni=5, nj=5,
                              corners=DART)
        stem = os.path.join(tmp, "dartout")
        conf = write_config(os.path.join(tmp, "dart.dat"), topo, stem)
        rc, out = run_conf(tmp, conf)
        line = quality(out)
        got = shape_of(line)
        check(f"10. the folded dart still exits 9 with inverted cells (rc {rc})",
              rc == 9 and line is not None and line["inverted"] > 0)
        check("10. ...and its shape figures are reported anyway, so a mesh can be "
              "folded and ordinarily shaped at the same time and the report says "
              "both", got is not None and got["cells"] > 0)
        side = sidecar(stem)
        check("10. ...and the sidecar beside the EXPORTED folded mesh carries them "
              "too, so a mesh that failed is still described",
              side is not None and side.get("metric") == METRIC)

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
