#!/usr/bin/env python3
"""The golden comparator never reports a deviation it did not measure (#48 re-audit).

``tools/scripts/golden_mesh.py`` is the instrument every "this refactor changed
nothing" claim in this repo is made with, and its report deliberately keeps an
exact ``0.000e+00`` distinguishable from a match that merely fits ``TOL`` — the
design note calls that distinction load bearing. So the one line that must never
be fabricated is that number.

IT WAS. ``_diff`` returns early when either record is ``{"rc": N, "error": ...}``
— a case that produces no mesh is a legitimate golden value, one junction shape
being expected to refuse — and it used to return ``worst = 0.0`` from that path,
which the caller printed as ``SAME <case>  (worst coordinate deviation
0.000e+00)``. Identical to a case that really did match every coordinate, and
strictly stronger-looking than one that matched within tolerance. ``capture``
never had this defect: it prints ``rc=6: no mesh produced``.

WHAT IT COST, which is why this gate exists rather than a comment. Re-auditing
#48 on 2026-09-10, the nine hybrid golden cases came back "9/9 SAME, 0.000e+00"
against a pre-#48 binary and that is what got written down — of EIGHT meshes and
one matched refusal (``isolated_corner``, rc=6 both sides). The overclaim was in
the instrument's own output, so re-reading it could not catch it.

WHAT IS CHECKED, and why through ``_diff`` rather than a real run: the deviation
is a pure function of two records, so this gate needs no mesher and no build tree
and runs in milliseconds. Checks 4-6 drive ``main("compare", ...)`` with
``_run_case`` stubbed, because the fabricated number was in the PRINTER and a
check on ``_diff`` alone would have passed throughout.

  1. a matched refusal returns None, not 0.0 — "not measured" is its own answer
  2. a real match still returns a float, so None cannot mean "matched"
  3. a CHANGED outcome is still a DIFF, naming both sides
  4. the printed line for a matched refusal says NO MESH and prints no deviation
  5. the summary says how many of its SAMEs were not meshes, so the total cannot
     be quoted as all-mesh (which is exactly how it was misquoted)
  6. a real match still prints its deviation

INJECTIONS, run 2026-09-10 (each reverted, and each confirmed to have really
changed the file before its score was read):

  A. ``return out, None`` -> ``return out, 0.0`` (the original defect)      4 FAIL
  B. printer's ``elif worst is None`` branch prints the deviation again     2 FAIL
  C. the "OF THOSE, N matched a NO-MESH outcome" summary line deleted       1 FAIL
  D. the MEASURED path returns None too ("None means matched")              3 FAIL

D IS THE SECOND ATTEMPT, AND THE FIRST ONE IS WHY THE EXIT CODE IS READ AND NOT
THE FAIL COUNT. Injecting ``worst = None`` at the assignment inside the
coordinate block does not score 3 — it scores **0**, because ``_diff``'s own
``if worst > TOL`` then raises ``TypeError`` and the run dies at check 2 with no
FAIL line printed at all. A crash and an inert check are indistinguishable by
count; they are not by exit code, which was 1. D therefore returns None from the
measured path's ``return`` instead, which reaches every check it should.

BLIND SPOTS, named rather than papered over:
  * Nothing here runs the mesher, so this gate cannot see a change in what
    ``_canonical`` measures — that is ``golden_mesh.py``'s own job and the
    surface gates'. It covers the REPORT, not the comparison.
  * The stub returns the reference record verbatim, so no check here exercises a
    real deviation between two meshes; check 6's float comes from comparing a
    record with itself. A near-``TOL`` deviation is the case the design note
    already names as uncovered, and this file does not change that.
  * Only the ref side carries the error record in checks 1/4/5. The
    error-in-new-only direction is covered by check 3 as a DIFF, which is the
    only outcome that side can legitimately produce.
"""

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_TOOL = os.path.join(_REPO, "tools", "scripts", "golden_mesh.py")

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def _load():
    spec = importlib.util.spec_from_file_location("golden_mesh", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _real_record():
    """A minimal record of the shape ``_canonical`` returns."""
    return {
        "rc": 0,
        "n_nodes": 2,
        "n_cells": 1,
        "n_cel_cells": 1,
        "coincident_nodes": 0,
        "malformed_rows": 0,
        "nodes": [[0.0, 0.0], [1.0, 0.0]],
        "cells": [[0, 1, 1]],
        "cel_cells": [[0, 1, 1, 1]],
        "patch_counts": {"wall": 1},
        "patch_faces": [["wall", 0.0, 0.0, 1.0, 0.0]],
        "patch_groups": [["wall", 0, 0, 1]],
    }


def _no_mesh_record(rc=6):
    return {"rc": rc, "error": "no mesh produced"}


def main():
    g = _load()

    # ── 1-3. the deviation is a pure function of two records ───────────────
    diffs, worst = g._diff(_no_mesh_record(), _no_mesh_record())
    check("1. a refusal matching a refusal is a SAME (no diffs reported)", not diffs)
    check(f"1. ...and reports NO deviation rather than a zero one (got {worst!r})",
          worst is None)

    diffs, worst = g._diff(_real_record(), _real_record())
    check("2. a real match is still a SAME", not diffs)
    check(f"2. ...and reports a measured deviation, so None cannot be read as "
          f"'matched' (got {worst!r})",
          isinstance(worst, float) and worst == 0.0)

    diffs, worst = g._diff(_no_mesh_record(rc=6), _real_record())
    check("3. a refusal that starts producing a mesh is a DIFF", bool(diffs))
    check(f"3. ...naming the outcome that changed (got {diffs})",
          any("run outcome changed" in d for d in diffs))

    # ── 4-6. the printed report, which is where the number was fabricated ──
    with tempfile.TemporaryDirectory(prefix="golden_report_") as tmp:
        records = {"isolated_corner": _no_mesh_record(), "duct_90": _real_record()}
        for name, rec in records.items():
            with open(os.path.join(tmp, name + ".json"), "w") as f:
                json.dump(rec, f)
        # The mesher is never run: the report is what is under test, and the two
        # records above are both sides of it.
        g._run_case = lambda name: records[name]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = g.main(["compare", tmp, "--only", "isolated_corner", "duct_90"])
        out = buf.getvalue()
    print(out.rstrip())
    check(f"4. both cases compare SAME, so the report is the only thing "
          f"differing (rc {rc})", rc == 0)

    lines = {ln.split()[1]: ln for ln in out.splitlines() if ln.startswith("SAME")}
    ic = lines.get("isolated_corner", "")
    check(f"4. the matched refusal's line says NO MESH (got {ic!r})",
          "NO MESH" in ic)
    check("4. ...and prints no coordinate deviation at all, the number having "
          "been measured off nothing",
          "coordinate deviation" not in ic)
    check("5. the summary says how many SAMEs were not meshes, so 'N/N SAME' "
          "cannot be quoted as N meshes",
          "matched a NO-MESH outcome" in out and "['isolated_corner']" in out)
    check(f"6. a real match still prints its deviation "
          f"(got {lines.get('duct_90', '')!r})",
          "worst coordinate deviation 0.000e+00" in lines.get("duct_90", ""))

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
