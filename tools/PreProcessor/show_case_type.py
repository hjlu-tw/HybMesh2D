#!/usr/bin/env python3
"""Show what a CASE TYPE says, diff two of them, or check a case against one.

The inspecting half of issue #162 (parent #158). A case type is a bundle of
expertise somebody else authored, and three questions have to be answerable
before anybody can sensibly apply one:

* **What does it have an opinion about?** `show_case_type.py <file>` prints the
  thresholds, their provenance, and the config FIELDS the case type owns. #158's
  out-of-scope list says operators do not AUTHOR case types and in the same
  breath says they may INSPECT one, "because the deviation marking is meaningless
  otherwise" — this is that. User story 24.
* **How do two problem classes differ?** `--against <other>` prints the fields
  the two disagree about, including the ones only one of them has an opinion
  about. User story 37.
* **What would it do to MY drawing?** A case type declares a CHARACTERISTIC
  LENGTH (#163) and `--config` measures it on the case given, so the deviation
  below is reported against the FITTED numbers rather than the authored ones.
* **Have I moved anything?** `--config <case>` reads a case's own mesh
  configuration — a `.dat`, a `.hws` or a pipeline script — and reports every
  owned field it has moved. That is the same comparison the verdict marks a run
  DEVIATED by, so an operator can ask the question before spending a run.

Headless, like `save_case_type.py` beside it, and for the same reason: #166 owns
the picker and the Trial/Generate actions, and a dialog authored here would be
chrome for that ticket to unpick.

Usage:
    python3 tools/PreProcessor/show_case_type.py examples/case_types/ogrid_circle.casetype.json
    python3 tools/PreProcessor/show_case_type.py A.casetype.json --against B.casetype.json
    python3 tools/PreProcessor/show_case_type.py A.casetype.json --config config/multiblock_ogrid.dat

Exit code is 0 for a question answered, 1 for a file that will not load. A
deviation that is FOUND is not an error: it is the answer.
"""
from __future__ import annotations

import argparse
import os
import sys

# Make the GUI's ``app`` package importable (services/ is Qt-free).
_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI_DIR = os.path.join(_HERE, "gui")
if _GUI_DIR not in sys.path:
    sys.path.insert(0, _GUI_DIR)

from app.services import case_type as case_type_mod
from app.services import case_type_fields
from app.services import case_type_scale
from app.services.case_type import CaseTypeError


def _show(case_type) -> None:
    print("Case type '%s' — %s" % (case_type.name, case_type.metric))
    if case_type.source:
        print("  from %s" % case_type.source)
    for ref in case_type.references:
        print("  reference mesh '%s': %s, measured %s (%d figure(s))"
              % (ref.ident, ref.mesh or "(no mesh recorded)",
                 ref.measured_on or "(no date recorded)", len(ref.figures)))
    for th in case_type.thresholds:
        print("  threshold    %-13s %s" % (th.key, th.describe_bounds()))
    if case_type.characteristic is not None:
        print("  characteristic length: %s"
              % case_type.characteristic.describe())
    else:
        print("  no characteristic length: its sizes fit the geometry it was "
              "authored on and are carried through unscaled")
    # The FIELDS, which is what this command exists for. Said even when there
    # are none: "this case type takes no position on any setting" is an answer
    # an operator needs, and an empty section that printed nothing would read as
    # a command that failed.
    if case_type.fields:
        print("  owns %d of %d mesh field(s):"
              % (len(case_type.fields), len(case_type_fields.ownable_names())))
        for line in case_type.fields.describe():
            print("    " + line)
    else:
        print("  owns no mesh fields: this case type grades a mesh and says "
              "nothing about how to produce one")


def _diff(left, right) -> None:
    rows = case_type_fields.diff(left.fields, right.fields)
    print("Fields: '%s' | '%s'" % (left.name, right.name))
    if not rows:
        print("  the two case types take the same position on every field")
        return
    for row in rows:
        print("  " + row.describe())


def _deviation(case_type, path) -> None:
    config = case_type_fields.read_config(path)
    print("Deviation of %s from case type '%s'" % (path, case_type.name))
    if not case_type.fields:
        # Asked BEFORE the ruler is measured: a case type that owns nothing has
        # nothing for a ruler to scale, so measuring one would be work whose
        # only possible output is a line about a comparison there is none of.
        print("  nothing to deviate from: this case type owns no mesh fields")
        return
    # ONE derivation, through the same `fit` `case_type_verdict.run_report`
    # marks a run with — the value a case type wants on THIS drawing is the one
    # its characteristic length scaled to, so the two reports cannot disagree,
    # and the ruler is not measured a second time to print it. `fit` also hands
    # back WHY it could not be measured, which that verdict only logs: somebody
    # who came here to ask the question is owed the sentence.
    wanted, scale, why_not = case_type_scale.fit(case_type, config)
    if scale is not None:
        print("  measured here: %s %.6g, so its geometry-driven sizes are "
              "compared at x %.6g"
              % (case_type.characteristic.measure,
                 case_type.characteristic.value * scale.factor, scale.factor))
    elif why_not:
        print("  the characteristic length could not be measured here (%s), so "
              "the fields below are compared AS AUTHORED" % why_not)
    moved = case_type_fields.deviations(wanted, config)
    if not moved:
        print("  none — all %d owned field(s) match" % len(case_type.fields))
        return
    for dev in moved:
        print("  " + dev.describe())


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Show a case type, diff two of them, or report how far a "
                    "case has moved from one.")
    ap.add_argument("case_type", help="the case type file to read")
    ap.add_argument("--against", metavar="FILE",
                    help="a second case type: print what the two disagree about")
    ap.add_argument("--config", metavar="FILE",
                    help="a case's mesh configuration (.dat / .hws / pipeline "
                         "script): print the owned fields it has moved")
    args = ap.parse_args()

    try:
        case_type = case_type_mod.load(args.case_type)
        other = case_type_mod.load(args.against) if args.against else None
        _show(case_type)
        if other is not None:
            print("")
            _show(other)
            print("")
            _diff(case_type, other)
        if args.config:
            print("")
            _deviation(case_type, args.config)
    except (CaseTypeError, OSError) as exc:
        # NARROW, by `save_case_type.py`'s own reasoning: `CaseTypeError` IS a
        # `ValueError`, so naming `ValueError` beside it would render an
        # unrelated conversion bug as one tidy stderr line.
        print("show_case_type: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
