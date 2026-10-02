#!/usr/bin/env python3
"""Apply a CASE TYPE to your own geometry, at your own scale.

The third of the case-type hosts (#163, parent #158): `save_case_type.py`
AUTHORS one, `show_case_type.py` INSPECTS one, and this one FITS one to a drawing
that is not the maintainer's. It answers #158's user stories 22 and 23 together,
because they are two halves of the same question — which of a case type's numbers
belong to the body's SIZE and which belong to the FLOW:

* **Geometry-driven sizes scale.** The case type declares a CHARACTERISTIC
  LENGTH — "the extent of the geometries bearing `body`" — and that length is
  MEASURED on the drawing you give it, never typed. A surface size, a far-field
  radius or a wake length is multiplied by the ratio of the two; a domain bound
  is a POSITION and is mapped about the body's own centre instead. So a case type
  authored on a 1 m body fits a 10 mm one.
* **Physical parameters do not.** The boundary-layer first cell height is set by
  the Reynolds number and the target y+, not by how big the body is. It is
  carried through unscaled, converted only where the two drawings declare
  DIFFERENT length units (so the height in metres is the same height), and it is
  REFUSED until you confirm it: `--confirm bl_initial_thickness` accepts the
  value the case type offers, `--confirm bl_initial_thickness=2e-6` gives your
  own. There is no flag that confirms everything, because a case type's whole
  risk is that somebody else's Reynolds number is not yours.

A case type whose characteristic length cannot be measured on your drawing —
nothing bearing the role it names, a geometry file that will not load — REFUSES
and says which. It does not fall back to the whole drawing or to 1:1, because a
guessed ruler produces a mesh that looks right and is the wrong size.

And since #164 it also attaches the case type to YOUR OWN CURVES. A case type
naming a topology family needs to know which of your segments is the body and
which is the far field; its own bindings are stable segment ids into the
MAINTAINER's geometry and cannot carry over, so what travels is the ROLE:

    --role body=my_body.dat           every segment that geometry carries
    --role farfield=my_far.dat:3,4,5  those segments, in the geometry's order
    --role body                       accept the role this tool pre-selected

The roles the case type needs are PRINTED before any of them is assigned, with
the pre-selection and the reason for it. A pre-selected role is REFUSED until
you confirm it, for the same reason the first cell height is: a wrong guess that
reaches the mesher silently produces a mesh that exports, looks right, and has
the far field's conditions on the body.

Usage:
    python3 tools/PreProcessor/apply_case_type.py <case.casetype.json> \
        --to my_case.dat --out fitted.dat \
        --confirm bl_initial_thickness --role body --role farfield

`--to` is your own case — a `.dat`, a `.hws` workspace or a pipeline script. Its
geometry list and the ROLES on it are what the ruler is read from, and everything
the case type has no opinion about is left exactly as it is. `--out` writes the
fitted configuration as a mesher `.dat` — and, for a case type naming a family,
the block topology document beside it; without it nothing is written and this
is a dry run.

Headless, like the two hosts beside it: #166 owns the picker and the
Trial/Generate actions, and a dialog authored here would be chrome to unpick.

Exit code is 0 when the case type was applied, 1 when it was refused — including
the refusal that a physical parameter is unconfirmed, which is the one this
command exists to make unavoidable.
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
from app.services import case_type_roles
from app.services import case_type_scale
from app.services import topology_binding
from app.services.case_type import CaseTypeError


def _parse_confirmations(entries, application):
    """`--confirm NAME[=VALUE]` entries as `{name: value}`.

    A bare name accepts the value the case type offers; `NAME=VALUE` supplies
    the operator's own. Confirming and adjusting are therefore one act, which is
    what keeps the question from being a button people learn to click.
    """
    offered = {c.name: c.offered for c in application.confirmations}
    out = {}
    for raw in entries or []:
        name, sep, value = str(raw).partition("=")
        name = name.strip()
        if name not in offered:
            raise CaseTypeError(
                "--confirm %r names no physical parameter of this case type; "
                "it asks about %s" % (raw, ", ".join(offered) or "none"))
        if not sep:
            out[name] = offered[name]
            continue
        if not value.strip():
            # REFUSED rather than read as a bare name: `--confirm x=$VAL` with
            # the variable unset is the shape this catches, and silently
            # accepting somebody else's first cell height is the one thing this
            # command exists to prevent.
            raise CaseTypeError(
                "--confirm %r gives an empty value; use the bare name %r to "
                "accept the offered one" % (raw, name))
        try:
            out[name] = float(value)
        except ValueError as exc:
            raise CaseTypeError(
                "--confirm %r: %s is not a number" % (raw, value)) from exc
    return out


def _parse_roles(entries, plan):
    """`--role NAME[=GEOM[:SEGS]]` entries as `{role: spec}`.

    A bare name accepts the role this tool pre-selected; `NAME=GEOM` binds every
    segment that geometry carries and `NAME=GEOM:1,2,3` binds those. The same
    shape `--confirm` has, deliberately: both are the operator ANSWERING a
    question the tool asked, and two grammars for one act is two things to
    learn.

    A role the case type does not need is refused HERE as well as in the
    service, so a typo is a sentence naming the roles it does need rather than a
    binding that silently does nothing.
    """
    out = {}
    for raw in entries or []:
        name, sep, spec = str(raw).partition("=")
        name = name.strip()
        if plan.slot(name) is None:
            raise CaseTypeError(
                "--role %r names no role this case type needs; it needs %s"
                % (raw, ", ".join(plan.roles) or "none"))
        if sep and not spec.strip():
            # REFUSED rather than read as a bare name, by `--confirm`'s own
            # reasoning: `--role body=$GEOM` with the variable unset is the
            # shape this catches, and silently accepting a guess for it is the
            # one thing the confirmation exists to prevent.
            raise CaseTypeError(
                "--role %r gives an empty geometry; use the bare name %r to "
                "accept the pre-selected one" % (raw, name))
        out[name] = spec.strip()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fit a case type to your own geometry: geometry-driven "
                    "sizes scale with its characteristic length, physical "
                    "parameters do not and must be confirmed.")
    ap.add_argument("case_type", help="the case type file to apply")
    ap.add_argument("--to", required=True, metavar="FILE",
                    help="your own case (.dat / .hws / pipeline script): its "
                         "geometry and roles are what the characteristic "
                         "length is measured on")
    ap.add_argument("--out", metavar="FILE",
                    help="write the fitted configuration here as a mesher "
                         ".dat. Omitted, nothing is written.")
    ap.add_argument("--confirm", action="append", metavar="NAME[=VALUE]",
                    help="confirm one physical parameter; repeatable. A bare "
                         "name accepts the offered value, NAME=VALUE gives "
                         "your own.")
    ap.add_argument("--role", action="append",
                    metavar="ROLE[=GEOM[:SEGS]]",
                    help="assign one role on YOUR geometry; repeatable. A bare "
                         "name accepts the pre-selected curve, ROLE=GEOM binds "
                         "every segment it carries, ROLE=GEOM:1,2,3 binds "
                         "those.")
    args = ap.parse_args()

    try:
        case_type = case_type_mod.load(args.case_type)
        config = case_type_fields.read_config(args.to)
        application = case_type_scale.plan(case_type, config)
        confirmed = _parse_confirmations(args.confirm, application)
        print("Case type '%s' applied to %s" % (case_type.name, args.to))
        if case_type.characteristic is not None:
            print("  authored against: %s"
                  % case_type.characteristic.describe())
            # Read OFF THE SCALE rather than measured a second time: the
            # application already derived this, and a second derivation beside
            # it is a second answer waiting to disagree with the one applied.
            scale = application.scale
            print("  this drawing:     %s %.6g, centred (%.6g, %.6g), so every "
                  "geometry-driven size x %.6g%s"
                  % (case_type.characteristic.measure,
                     case_type.characteristic.value * scale.factor,
                     scale.centre[0], scale.centre[1], scale.factor,
                     "" if scale.unit_ratio == 1.0
                     else " (and every physical one x %.6g, for the unit "
                          "change alone)" % scale.unit_ratio))
        else:
            print("  this case type declares no characteristic length, so its "
                  "sizes are carried through unscaled")
        for line in application.describe():
            print("    " + line)
        # THE ROLES ARE SHOWN BEFORE ANYTHING IS ASSIGNED, and before `apply`
        # refuses an unconfirmed physical parameter: an operator who runs this
        # bare must see which of their curves they are being asked for, not a
        # refusal about a first cell height and nothing else.
        roles = case_type_roles.plan_for(
            case_type, config, topology_binding.context_for_config(config))
        if roles.slots:
            print("  roles this case type needs on your own geometry:")
            for line in roles.describe():
                print("    " + line)
        assigned = _parse_roles(args.role, roles)
        # The refusal goes through `apply`, not through a check beside it: the
        # service is what makes "never applied silently" structural, and a host
        # that asked the question itself could answer it differently.
        fitted = application.apply(config, confirmed)
        for name in sorted(confirmed):
            print("  confirmed %s = %s"
                  % (name, case_type_fields.show_value(confirmed[name])))
        # And the bindings are DERIVED from those roles against the operator's
        # own segments, after the family has been written in: no id from the
        # authoring geometry is read, because a case type carries none.
        for binding in roles.bind(fitted, assigned):
            print("  bound %s" % binding.describe())
        if args.out:
            fitted.save_to_file(args.out)
            print("  wrote %s" % args.out)
        else:
            print("  nothing written (no --out)")
    except (CaseTypeError, OSError) as exc:
        # NARROW, by `save_case_type.py`'s own reasoning: `CaseTypeError` IS a
        # `ValueError`, so naming `ValueError` beside it would render an
        # unrelated conversion bug as one tidy stderr line.
        print("apply_case_type: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
