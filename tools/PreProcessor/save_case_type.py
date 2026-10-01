#!/usr/bin/env python3
"""Save a working case as a CASE TYPE, with thresholds measured from its mesh.

The maintainer builds a case they are happy with, as they do today, and runs
this once against the mesh it produced. That mesh becomes the case type's
REFERENCE MESH: the tool reads the figures the mesher already published beside
it, multiplies each by a tolerance factor, records which mesh every bound came
from, and writes the result as a case type the verdict service can load.

This is the "one action" half of issue #161 (parent #158). It is deliberately a
headless host and not a GUI dialog: #162 builds the picker and the apply flow,
and a dialog authored here would be chrome for that ticket to unpick. What this
command owns is the AUTHORING step, which has no UI of its own to speak of —
a mesh, a name, a sentence of advice per figure.

Usage:
    python3 tools/PreProcessor/save_case_type.py <mesh.vtk> \
        --name "Circular body, O-grid" \
        --out examples/case_types/ogrid_circle.casetype.json \
        --advice "max=Put more points round the body." \
        --advice-from advice.json \
        --attention-factor 1.5 --unusable-factor 3.0 \
        --override "max.attention=50.0" \
        --reference-id ogrid_circle --measured-on 2026-10-01

`--advice` selects the figures the case type has an opinion about: a figure with
no advice gets no threshold. `--override` replaces one derived bound by hand and
drops that bound's tolerance factor, so the file itself shows which bounds were
measured and which were typed; `--override max.unusable=` (an empty value)
removes that bound altogether.

The figure keys are the nine the mesher publishes: `median`, `p95`, `max`, and
the same three under `layer.` and `bulk.` for each half of the wall/bulk split.
A figure the reference mesh could not measure is REPORTED and produces no
threshold rather than a bound derived from a negative number.

Needs no build tree and no display: it reads a mesh's `.provenance.json` and
writes a JSON document.
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

from app.services import case_type_author
from app.services.case_type import BOUNDS, CaseTypeError


def _parse_advice(pairs, files):
    """`--advice key=text` entries plus `--advice-from` JSON objects, merged.

    A later entry wins over an earlier one, which is what lets a file carry the
    bulk of the advice and one flag amend a single line of it.
    """
    advice = {}
    for path in files or []:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        if not isinstance(doc, dict):
            raise CaseTypeError(
                "'%s' must hold a JSON object mapping a figure key to its "
                "advice" % path)
        advice.update({str(k): str(v) for k, v in doc.items()})
    for raw in pairs or []:
        key, sep, text = raw.partition("=")
        if not sep:
            raise CaseTypeError(
                "--advice %r is not `key=text`; the advice is what a figure's "
                "threshold says to try when it is missed" % raw)
        advice[key.strip()] = text
    return advice


def _parse_overrides(entries):
    """`--override key.bound=value` entries as `{key: {bound: value}}`.

    An empty value removes the bound; anything else sets it by hand. The bound
    is split off the RIGHT, because a figure key may itself carry a dot
    (`bulk.p95`) and the bound name never does.
    """
    out = {}
    for raw in entries or []:
        target, sep, value = raw.partition("=")
        if not sep:
            raise CaseTypeError(
                "--override %r is not `key.bound=value`" % raw)
        key, _, bound = target.strip().rpartition(".")
        if not key or bound not in BOUNDS:
            raise CaseTypeError(
                "--override %r does not name a bound; expected `<figure>.%s`"
                % (raw, "` or `<figure>.".join(BOUNDS)))
        out.setdefault(key, {})[bound] = None if not value.strip() else value
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Save a working case as a case type, with thresholds "
                    "measured from the mesh it produced.")
    ap.add_argument("mesh", help="the reference mesh (its .provenance.json is "
                                 "what is read)")
    ap.add_argument("--name", required=True, help="the case type's name")
    ap.add_argument("--out", required=True, help="where to write it")
    ap.add_argument("--advice", action="append", metavar="KEY=TEXT",
                    help="advice for one figure; repeatable. Selects the "
                         "figures the case type has an opinion about.")
    ap.add_argument("--advice-from", action="append", metavar="FILE",
                    help="a JSON object of key -> advice; repeatable")
    ap.add_argument("--attention-factor", type=float,
                    default=case_type_author.DEFAULT_ATTENTION_FACTOR,
                    help="measured figure x this = the needs-attention bound "
                         "(default %(default)s)")
    ap.add_argument("--unusable-factor", type=float,
                    default=case_type_author.DEFAULT_UNUSABLE_FACTOR,
                    help="measured figure x this = the unusable bound "
                         "(default %(default)s)")
    ap.add_argument("--override", action="append", metavar="KEY.BOUND=VALUE",
                    help="set one bound by hand; repeatable. An empty value "
                         "removes the bound.")
    ap.add_argument("--reference-id", default="",
                    help="the id thresholds name the reference mesh by "
                         "(default: the mesh's filename stem)")
    ap.add_argument("--measured-on", default="",
                    help="the date the figures were read (default: today)")
    args = ap.parse_args()

    try:
        reference = case_type_author.measure_reference(
            args.mesh, ident=args.reference_id, measured_on=args.measured_on)
        result = case_type_author.author(
            args.name, reference,
            _parse_advice(args.advice, args.advice_from),
            attention_factor=args.attention_factor,
            unusable_factor=args.unusable_factor,
            overrides=_parse_overrides(args.override))
        result = case_type_author.save_case_type(result, args.out)
    except (CaseTypeError, OSError, ValueError) as exc:
        print("save_case_type: %s" % exc, file=sys.stderr)
        return 1

    case_type = result.case_type
    print("Wrote case type '%s' to %s" % (case_type.name, args.out))
    print("  reference mesh '%s': %s (%s), measured %s"
          % (reference.ident, reference.mesh, reference.metric,
             reference.measured_on))
    for th in case_type.thresholds:
        parts = []
        for bound in BOUNDS:
            value = getattr(th, bound)
            if value is not None:
                parts.append("%s %.6g (%s)"
                             % (bound, value, th.origin_of(bound)))
        print("  %-13s %s" % (th.key, ", ".join(parts)))
    for key, why in result.skipped:
        # Said out loud, never only logged: a maintainer who asked for a bound
        # on a figure and silently did not get one would believe they had it.
        print("  no threshold for %s: %s" % (key, why))
    return 0


if __name__ == "__main__":
    sys.exit(main())
