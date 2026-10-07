#!/usr/bin/env python3
"""Correct a case type's thresholds with EVIDENCE: add a reference mesh.

Issue #168 (parent #158). A case type starts from one reference mesh, which is a
thin basis: it has an opinion about what that mesh happened to exercise and none
about anything else. When a verdict turns out to be wrong — a mesh it called
usable that was not, or one it refused that was fine — the maintainer adds the
offending mesh here and the thresholds move.

Hand-editing the number would work and would throw away the thing the
measurement bought: a threshold whose origin is still visible six months later.
So this command never edits a bound. It measures the mesh, records it beside the
ones already there, and RE-DERIVES every bound that carries a tolerance factor
from the whole set — which is what makes the new number as traceable as the old
one. A bound the maintainer set by hand is left exactly as they typed it.

Two kinds of evidence:

* an **exemplar** (the default) is a mesh the thresholds must ACCEPT. Add one
  when a verdict refused a mesh that was fine: the bounds widen to cover it.
* a **counter-example** (`--counter-example`) is a mesh they must REJECT. Add
  one when a verdict passed a mesh that was not: the bounds come down until some
  figure tells the two apart.

A mesh that would make the case type self-contradictory — required to both
accept and reject the same figures — is REFUSED, naming which figures and, when
a hand-set bound is the obstacle, saying so. Nothing is written on a refusal.

Usage:
    python3 tools/PreProcessor/add_reference_mesh.py \
        examples/case_types/ogrid_circle.casetype.json \
        results/meshes/multiblock_tworing/mesh_multiblock_tworing.vtk \
        --reference-id tworing_circle

    python3 tools/PreProcessor/add_reference_mesh.py <case.casetype.json> \
        <bad_mesh.vtk> --counter-example --out corrected.casetype.json

The case type is rewritten IN PLACE unless `--out` names somewhere else.
`--dry-run` prints what would move and writes nothing, which is how a maintainer
sees the consequence before committing to it.

Headless, like `save_case_type.py` and `show_case_type.py` beside it, and for the
same reason: the GUI has Trial and Generate (#166) but no case-type author.

Needs no build tree and no display: it reads a mesh's `.provenance.json` and
rewrites a JSON document.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Make the GUI's ``app`` package importable (services/ is Qt-free).
_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI_DIR = os.path.join(_HERE, "gui")
if _GUI_DIR not in sys.path:
    sys.path.insert(0, _GUI_DIR)

from app.services import case_type as case_type_mod
from app.services import case_type_author
from app.services.case_type import CaseTypeError


def _report(result, case_type) -> None:
    """What the addition did, bound by bound. Printed by this host only."""
    ref = result.reference
    print("Added %s '%s': %s (%s), measured %s"
          % (ref.kind, ref.ident, ref.mesh or "(no mesh recorded)", ref.metric,
             ref.measured_on or "(no date recorded)"))
    if not result.moves:
        # Said out loud: a maintainer who adds a mesh expecting a correction and
        # gets none has learnt something — the evidence already covered it — and
        # a silent exit would read as the thresholds having moved.
        print("  no bound moved: the thresholds already covered this mesh")
    for key, bound, before, after in result.moves:
        print("  %-13s %s %.6g -> %.6g" % (key, bound, before, after))
    for note in result.notes:
        # What the correction COST, printed with what it changed: a figure that
        # can no longer answer `needs attention` still answers, so the only
        # moment a maintainer can weigh that is now.
        print("  cost: %s" % note)
    for th in case_type.thresholds:
        print("  %-13s %s" % (th.key, th.describe_bounds()))
        print("  %-13s %s" % ("", case_type.describe_support(th)))
    if result.skipped:
        # ONE line for the lot: the interesting fact is that the mesh published
        # figures this case type has no opinion about, not each of their names
        # on a line of its own.
        print("  no threshold for %s: this case type bounds none of them, and "
              "adding a reference mesh does not invent one"
              % ", ".join(key for key, _ in result.skipped))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Add a reference mesh to an existing case type and let its "
                    "thresholds move.")
    ap.add_argument("case_type", help="the case type file to correct")
    ap.add_argument("mesh", help="the mesh to add (its .provenance.json is "
                                 "what is read)")
    ap.add_argument("--counter-example", action="store_true",
                    help="add it as a mesh the thresholds must REJECT "
                         "(default: one they must accept)")
    ap.add_argument("--reference-id", default="",
                    help="the id this mesh is recorded under "
                         "(default: the mesh's filename stem)")
    ap.add_argument("--measured-on", default="",
                    help="the date the figures were read (default: today)")
    ap.add_argument("--out", metavar="FILE",
                    help="write the corrected case type here instead of over "
                         "the one given")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would move and write nothing")
    args = ap.parse_args()

    try:
        case_type = case_type_mod.load(args.case_type)
        reference = case_type_author.measure_reference(
            args.mesh, ident=args.reference_id,
            measured_on=args.measured_on,
            kind=(case_type_mod.COUNTER if args.counter_example
                  else case_type_mod.EXEMPLAR))
        result = case_type_author.add_reference(case_type, reference)
        dest = args.out or args.case_type
        if not args.dry_run:
            case_type_mod.save(result.case_type, dest)
    except (CaseTypeError, OSError, json.JSONDecodeError) as exc:
        # NARROW, by `save_case_type.py`'s own reasoning: `CaseTypeError` IS a
        # `ValueError`, so naming `ValueError` beside it would render an
        # unrelated conversion bug as one tidy stderr line.
        print("add_reference_mesh: %s" % exc, file=sys.stderr)
        return 1

    print("%s case type '%s'%s"
          % ("Would rewrite" if args.dry_run else "Wrote",
             result.case_type.name, "" if args.dry_run else " to " + dest))
    _report(result, result.case_type)
    return 0


if __name__ == "__main__":
    sys.exit(main())
