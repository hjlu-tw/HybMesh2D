#!/usr/bin/env python3
"""APPLYING a case type to the operator's own drawing, from the window (issue #170).

#164 built the roles, #163 the ruler, #169 the picker — and #169's own docstring
had to say that picking SELECTS WHAT JUDGES and applies nothing, "because every
part of applying needs ROLES, and roles are #170". That was literally true:
`case_type_roles`, `case_type_guess`, `case_type_scale` and `case_type_fields`
had no GUI caller whatsoever, their only non-test host being
`tools/PreProcessor/apply_case_type.py`. This gate is the act those modules exist
for, reached from the window.

WHAT IT IS FOR. Three failures are worth more than the feature:

  * a case type applied to the LIVE configuration and then refused, which
    overwrites the operator's own numbers at the exact moment they most need
    them back;
  * an unassigned role silently reading as a confirmed one, which is the wrong
    guess reaching the mesher — a mesh that generates, exports and looks right
    while carrying the far field's conditions on the body;
  * three refusals reached one at a time, which is three runs to clear what is
    one screen of edits.

The fifteen checks, in the order the operator meets them:

  1.  The assignment is a `MeshConfig` field: it round-trips through
      `to_dict`/`load_from_dict`, survives a real `.hws` through two live
      `AppController`s, is KEY-LESS (so the `.dat` parity gate is structurally
      blind to it) and is UNOWNABLE by a case type — not by an exclusion list
      but because an overlay admits only scalars, and these are the operator's
      own curves.
  2.  `(not assigned)` writes NO entry, and the pre-selection is a ROW whose
      text carries the reason it is offered. Absent is what `RolePlan.bind`
      refuses on, so selecting nothing cannot become confirming something.
  3.  The table round-trips an assignment through the panel, and a role the
      table does not SHOW is KEPT — looking at a second case type does not throw
      away the assignment made for the first.
  4.  The table rebuilds on SHAPE and never on a keystroke: the same widgets
      survive a value-only refresh, with the caret where the operator left it.
  5.  EVERY problem at once, across all three services: an unconfirmed role, a
      segment that does not resolve and an unconfirmed first cell height arrive
      in ONE refusal.
  6.  NOTHING IS WRITTEN WHEN ANYTHING REFUSES — including the pre-flight, which
      is the one refusal that can only be reached after the bindings exist. The
      live configuration is compared field by field before and after.
  7.  The pre-flight refusal carries the family's own `Refusal` ROWS, so the
      window points at the offending curve instead of re-parsing prose; and the
      live controller really draws them.
  8.  A successful apply SCALES the geometry-driven sizes by the characteristic
      length measured on THIS drawing, does NOT scale the physical parameter,
      and binds the family to the OPERATOR's own segment ids — with no id from
      the authoring drawing anywhere in the result.
  9.  A confirmation that CORRECTS the offered value is what gets applied AND
      what the report describes, so the dialog cannot describe a different apply
      from the one it performs.
  10. ONE UNDO STEP: Ctrl+Z after an apply restores every moved field at once.
  11. A role this case type does not need is KEPT and NOT bound, and is named —
      rather than becoming a refusal, which would make having looked at another
      case type an error.
  13. The confirmation dialog answers CANCEL headless rather than blocking, and
      Cancel is the safe default: the service then refuses the unconfirmed
      physical parameter instead of writing somebody else's Reynolds number.
  14. A RULER THAT CANNOT BE READ REFUSES. A case type whose characteristic
      length cannot be measured on this drawing is an error, never a silent
      fall back to the authored numbers — which would put a 1 m body's surface
      size on a 10 mm one.
  15. THE TWO ORDERS ARE THE SAME. Picking the case type before drawing and
      drawing before picking produce the identical roles table — #158's story 5,
      and an asymmetry #170 shipped until review: the role combos were built
      against an empty drawing and nothing rebuilt them when the curves arrived.
  12. THE WHOLE ACT THROUGH THE LIVE WINDOW: picker -> table -> the button's
      signal -> the controller -> the panel holds the fitted configuration. Its
      first half is the one property no in-process check above can see — a table
      row BUILT AFTER CONSTRUCTION reaching the model through the composite's own
      `panel_edited`, which is what `undo_ctrl._wire_widget_edits` connects
      because its traversal of children runs once and cannot reach a later one.

EIGHT INJECTIONS, run in-process at the end of this file so they run on every CI
run rather than by hand. Each builds a MUTATED copy of the service (and, for the
widget's own, of the table), asserts the mutation is well-formed and really
differs, then requires the named check to go red and every other in-process check
to stay green:

  A. `apply` writes into the LIVE config instead of a deep copy -> check 6
     fails: a refused apply leaves the operator's drawing overwritten.
  B. `apply` raises at the FIRST refusal instead of collecting -> check 5 fails:
     three round trips for one screen of edits.
  C. `plan` passes the WHOLE stored dict as the assignment instead of filtering
     to the roles this case type needs -> check 11 fails: a leftover from
     another case type becomes a refusal.
  D. the table reads `(not assigned)` as the EMPTY spec -> check 2 fails:
     assigning nothing silently confirms the guess.
  E. the table's shape key includes the VALUES -> check 4 fails: every
     selection rebuilds the row that made it, and the caret dies mid-type.
  F. `ApplyPlan.changes` ignores the confirmations -> check 9 fails: the dialog
     describes the offered value and applies the corrected one.
  G. negative control: the unmutated world passes every check.
  H. a DISCONNECT rather than a source mutation, because the subject is a WIRE
     with no module attribute to swap: the geometry list's `rowsInserted` /
     `rowsRemoved` are unhooked and pick-then-draw goes back to offering
     nothing, so check 15 is measuring that wire and not something else.

Checks 1 (the `.hws` half), 10 and 12 drive live `AppController`s, which hold
their own already-imported modules and no in-memory mutant reaches — so they are
excluded from the others-stay-green comparison and carry no injection. That is
stated rather than left to be counted.

Run:  QT_QPA_PLATFORM=offscreen python3 tools/PreProcessor/tests/test_case_type_apply.py
Needs Qt (offscreen). Needs no build tree and no network.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Like `test_case_type_picker.py`: the picker is the channel, and a gate that
# left the old environment channel lying around would be measuring it instead.
os.environ.pop("HYBMESH_CASE_TYPE", None)

from PyQt6.QtWidgets import QApplication                         # noqa: E402

from topology_outline_fixture import write_outline               # noqa: E402

from app.models.mesh_config import MeshConfig                    # noqa: E402
from app.models.mesh_config_keys import _KEY_MAP                 # noqa: E402
from app.services import case_type as case_type_mod              # noqa: E402
from app.services import case_type_fields, case_type_scale       # noqa: E402
from app.services.case_type import CaseTypeError                 # noqa: E402

_APP = QApplication.instance() or QApplication([])

#: The OPERATOR's segment ids — nothing like the 0..3 an authoring drawing
#: carries, so an id that leaked from the maintainer's side is visible as itself.
BODY_IDS = (17, 18, 19, 20)
FAR_IDS = (31, 32, 33, 34)
AUTHORING_IDS = (0, 1, 2, 3)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)
    return bool(cond)


# --- the world: fresh copies of the two files, optionally mutated -------------
#: name -> repo-relative source, in DEPENDENCY order. BOTH halves are mutable:
#: the act is the service and the assignment is the widget, and an injection that
#: could only reach one of them would stop being able to redden a check the day
#: its subject moved across that line.
_RELS = [
    ("app.services.case_type_apply",
     "tools/PreProcessor/gui/app/services/case_type_apply.py"),
    ("app.views.panels.case_type_roles_table",
     "tools/PreProcessor/gui/app/views/panels/case_type_roles_table.py"),
]


def _read(rel):
    with open(os.path.join(_REPO, rel), encoding="utf-8") as fh:
        return fh.read()


_SRC = {name: _read(rel) for name, rel in _RELS}


def world(**mutated):
    """Fresh copies of both files, optionally mutated. Returns `(service, table)`.

    A mutant left only in `sys.modules` is shadowed by the PACKAGE attribute that
    `from app.services import x` resolves through first (#160), so both are set —
    the harness `test_case_type_roles.py` and `test_case_type_fields.py` use.
    """
    import app.services            # noqa: F401
    import app.views.panels        # noqa: F401
    pkgs = {"app.services.case_type_apply": sys.modules["app.services"],
            "app.views.panels.case_type_roles_table":
                sys.modules["app.views.panels"]}
    saved_mods = {n: sys.modules.get(n) for n, _ in _RELS}
    saved_attrs = {n: getattr(pkgs[n], n.rsplit(".", 1)[1], None)
                   for n, _ in _RELS}
    try:
        built = {}
        for name, rel in _RELS:
            short = name.rsplit(".", 1)[1]
            spec = importlib.util.spec_from_loader(name, loader=None)
            mod = importlib.util.module_from_spec(spec)
            mod.__file__ = os.path.join(_REPO, rel)
            sys.modules[name] = mod
            setattr(pkgs[name], short, mod)
            exec(compile(mutated.get(short, _SRC[name]), mod.__file__, "exec"),
                 mod.__dict__)
            built[short] = mod
        return built["case_type_apply"], built["case_type_roles_table"]
    finally:
        for name, mod in saved_mods.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod
        for name, mod in saved_attrs.items():
            short = name.rsplit(".", 1)[1]
            pkg = pkgs[name]
            if mod is None:
                if hasattr(pkg, short):
                    delattr(pkg, short)
            else:
                setattr(pkg, short, mod)


def mutate(old, new, src):
    """`src` with `old` replaced by `new`, refusing a no-op or a miss."""
    assert src.count(old) == 1, "injection anchor matched %d times" % src.count(old)
    out = src.replace(old, new, 1)
    assert out != src
    return out


# --- the drawing and the case type -------------------------------------------
_TMP = tempfile.mkdtemp(prefix="ct_apply_")
BODY = write_outline(os.path.join(_TMP, "body"), 0.5, list(BODY_IDS), 40,
                     "wall", square=False)
FAR = write_outline(os.path.join(_TMP, "far"), 5.0, list(FAR_IDS), 40,
                    "farfield", square=False)


def case_type_file(name="demo", characteristic=None, **extra):
    """A case type that owns a family, a geometric size and a physical one.

    It CANNOT own a binding (`case_type_fields` refuses every `*_geom`/`*_segs`
    by suffix) nor the role assignment (an overlay admits only scalars), which
    is the premise this whole ticket rests on.
    """
    fields = {"mesh_mode": 1, "bl_initial_thickness": 0.001,
              "surface_mesh_size": 0.02, "topology.family": "ogrid",
              "topology.ogrid_cell": 0.05}
    fields.update(extra)
    ct = case_type_mod.CaseType(name, "quad_midline_ratio", fields=fields,
                                characteristic=characteristic)
    path = os.path.join(_TMP, name + ".casetype.json")
    case_type_mod.save(ct, path)
    return path


_CT = case_type_file()


def drawing(roles=None, ct=None, geoms=None, geom_roles=None):
    """The operator's own configuration: their curves, their ids, their choice.

    `geom_roles` defaults to the drawing already calling FAR the far field,
    which is the EVIDENCE branch of `guess_roles`. Check 15 passes `{}` instead,
    deliberately: with an empty geometry list that entry is pruned, so the two
    orders it compares would otherwise start from different drawings and differ
    in their guess REASON — a difference in input, not the asymmetry it is
    looking for.
    """
    cfg = MeshConfig()
    cfg.set_geom_files(list(geoms if geoms is not None else [BODY, FAR]))
    cfg.geom_roles = ({FAR: {"role": "farfield"}} if geom_roles is None
                      else dict(geom_roles))
    cfg.case_type_file = ct or _CT
    cfg.case_type_roles = dict(roles or {})
    return cfg


BOTH = {"body": "", "farfield": ""}


def refusal(fn, *a, **kw):
    """The message `fn` refuses with, or `""` when it does not refuse."""
    try:
        fn(*a, **kw)
    except CaseTypeError as exc:
        return str(exc)
    return ""


def snapshot(cfg):
    """Every field of a configuration, as a comparable value."""
    return json.dumps(cfg.to_dict(), sort_keys=True, default=str)


# ══ the checks ════════════════════════════════════════════════════════════

def check_1(w, _t):
    """The assignment is a model field: key-less, unownable, round-tripping."""
    mc = MeshConfig()
    mc.case_type_roles = {"body": "a.dat:1,2"}
    back = MeshConfig()
    back.load_from_dict(mc.to_dict())
    ok = check(back.case_type_roles == {"body": "a.dat:1,2"},
               "1. the role assignment round-trips through "
               "MeshConfig.to_dict/load_from_dict (%r)" % (back.case_type_roles,))
    blank = MeshConfig()
    blank.load_from_dict({"case_type_roles": None})
    ok &= check(blank.case_type_roles == {},
                "1. ...and an explicit JSON null lands as an empty container "
                "rather than as None, which every reader would then have to "
                "defend against (%r)" % (blank.case_type_roles,))
    keyed = [k for k, (attr, _c) in _KEY_MAP.items()
             if attr == "case_type_roles"]
    ok &= check(not keyed,
                "1. ...and it has NO `.dat` key, so the GUI<->C++ parity gate is "
                "structurally blind to it: the mesher is handed the bindings "
                "this produces, never the roles that produced them (%r)" % keyed)
    ok &= check("case_type_roles" not in case_type_fields.ownable_names(),
                "1. ...and a case type may NOT own it — not by an exclusion "
                "entry but because an overlay admits only scalars, and these "
                "are the operator's own curves, the one thing that cannot "
                "carry over from the authoring drawing")
    return ok


def check_2(w, t):
    """`(not assigned)` writes no entry; the pre-selection is a row with its reason."""
    cfg = drawing()
    plan = w.plan(cfg)
    table = t.CaseTypeRolesTable()
    table.set_plan(plan, {})
    read = table.read()
    ok = check(read == {},
               "2. with every row on `(not assigned)` the table writes NO entry "
               "— absent is what `RolePlan.bind` refuses on, so selecting "
               "nothing cannot become confirming something (%r)" % (read,))
    combo = table._rows["body"][0]
    texts = [combo.itemText(i) for i in range(combo.count())]
    guess = plan.roles.guesses.get("body")
    pre = [x for x in texts if x.startswith("pre-selected")]
    ok &= check(len(pre) == 1 and guess is not None and guess.why in pre[0],
                "2. ...and the pre-selection is a ROW whose own text carries the "
                "reason the tool offers it, so confirming it is not a control "
                "somebody learns to click (%r)" % (pre[0] if pre else None,))
    combo.setCurrentIndex(combo.findData(t.ACCEPT_GUESS))
    ok &= check(table.read() == {"body": ""},
                "2. ...and selecting that row IS the confirmation, written as "
                "`--role body`'s own empty spec (%r)" % (table.read(),))
    return ok


def check_3(w, t):
    """The panel round-trips an assignment, and keeps a role it does not show."""
    from app.views.panels.mesh_config_panel import MeshConfigPanel
    panel = MeshConfigPanel()
    cfg = drawing(roles={"body": BODY, "farfield": "", "seam": "kept.dat"})
    panel.set_config(cfg)
    back = panel.get_config()
    ok = check(back.case_type_roles.get("body") == BODY
               and back.case_type_roles.get("farfield") == "",
               "3. an assignment survives the panel round trip, both spellings "
               "— a named geometry and the confirmed pre-selection (%r)"
               % (back.case_type_roles,))
    ok &= check(back.case_type_roles.get("seam") == "kept.dat",
                "3. ...and a role this case type does not need, so the table "
                "shows no row for it, is KEPT: looking at a second case type "
                "must not throw away the assignment made for the first (%r)"
                % (back.case_type_roles,))
    table = panel.case_type_roles_table
    ok &= check(table.shown_roles() == frozenset({"body", "farfield"}),
                "3. ...and the table shows exactly the roles the O-grid needs "
                "(%r)" % (sorted(table.shown_roles()),))
    segs = table._rows["body"][1]
    segs.setText("19, 17")
    got = panel.get_config().case_type_roles.get("body")
    ok &= check(got == "%s:19, 17" % BODY,
                "3. ...and the segment box writes a per-segment spec, which the "
                "service then binds in the GEOMETRY's own order (%r)" % (got,))
    return ok


def check_4(w, t):
    """The table rebuilds on SHAPE, never on a keystroke."""
    cfg = drawing()
    plan = w.plan(cfg)
    table = t.CaseTypeRolesTable()
    table.set_plan(plan, {})
    combo, segs = table._rows["body"]
    combo.setCurrentIndex(combo.findData(BODY))
    segs.setText("17,18")
    segs.setCursorPosition(3)
    # A VALUE-ONLY refresh, which is what every keystroke on the panel causes.
    table.set_plan(w.plan(cfg), {"body": "%s:17,18" % BODY})
    same = table._rows["body"][1] is segs and table._rows["body"][0] is combo
    ok = check(same,
               "4. a value-only refresh keeps the very same widgets, so a "
               "per-keystroke read-out cannot tear the row down under the "
               "operator (same widgets=%r)" % same)
    ok &= check(same and segs.cursorPosition() == 3 and segs.text() == "17,18",
                "4. ...and the caret stays where they left it (pos=%r, text=%r)"
                % (segs.cursorPosition() if same else None,
                   segs.text() if same else None))
    # ...while a SHAPE change does rebuild: a second case type, a second family.
    other = drawing(ct=case_type_file("tworing", **{
        "topology.family": "tworing", "topology.tworing_cell": 0.05}))
    table.set_plan(w.plan(other), {})
    ok &= check(set(table.shown_roles()) == {"body", "seam", "farfield"},
                "4. ...and a family change DOES rebuild, because the roles it "
                "needs are part of the shape (%r)"
                % (sorted(table.shown_roles()),))
    return ok


def check_5(w, _t):
    """Every problem at once, across all three services."""
    # One role confirmed onto a segment the geometry does not carry, one left
    # unconfirmed, and nothing said about the first cell height.
    cfg = drawing(roles={"farfield": "%s:999" % FAR})
    why = refusal(w.apply, w.plan(cfg), cfg)
    ok = check("body" in why and "999" in why
               and "bl_initial_thickness" in why,
               "5. an unconfirmed role, a segment that does not resolve and an "
               "unconfirmed physical parameter arrive in ONE refusal, not three "
               "round trips (%r)" % (why[:110] + "…",))
    ok &= check(why.count("must be confirmed") == 2
                and "cannot be bound to this drawing" in why,
                "5. ...and all three are NAMED, each in its own service's own "
                "words rather than collapsed into one sentence")
    return ok


def check_6(w, _t):
    """Nothing is written when anything refuses — the pre-flight included."""
    cfg = drawing(roles=BOTH)
    before = snapshot(cfg)
    refusal(w.apply, w.plan(cfg), cfg)          # no confirmation: refused
    ok = check(snapshot(cfg) == before,
               "6. a refused apply writes NOTHING: the live configuration is "
               "field for field what it was")
    # ...and the refusal that can only be reached after the bindings exist.
    swapped = drawing(roles={"body": FAR, "farfield": BODY})
    before = snapshot(swapped)
    why = refusal(w.apply, w.plan(swapped), swapped,
                  {"bl_initial_thickness": 0.001})
    ok &= check(why and snapshot(swapped) == before,
                "6. ...including the PRE-FLIGHT refusal, which is reached only "
                "after the overlay has been written and the family bound — so "
                "it is the one that would overwrite the drawing at the exact "
                "moment the operator needs it back (refused=%r)" % bool(why))
    return ok


def check_7(w, _t):
    """The refusal carries the rows, and the window draws them."""
    swapped = drawing(roles={"body": FAR, "farfield": BODY})
    rows, text = (), ""
    try:
        w.apply(w.plan(swapped), swapped, {"bl_initial_thickness": 0.001})
    except w.PreflightRefused as exc:
        rows, text = exc.refusals, str(exc)
    ok = check(len(rows) == 1 and rows[0].geom and rows[0].at is not None,
               "7. the pre-flight refusal carries the family's own `Refusal` "
               "ROWS — the curve and the coordinate — so a window points at it "
               "rather than re-parsing prose (%r)"
               % ([(r.curve(), r.at) for r in rows],))
    ok &= check("far.dat" in text and "exit" not in text.lower(),
                "7. ...and the sentence is in the OPERATOR's terms, naming "
                "their own file rather than a block id or an exit code (%r)"
                % (text[:90] + "…",))
    return ok


def check_8(w, _t):
    """A successful apply: sizes scale, physics does not, ids are the operator's."""
    # AUTHORED ON A BODY TWICE THIS ONE'S SIZE: the drawing's body is a circle of
    # r=0.5, so its x extent is 1.0 against the declared 2.0 and every
    # geometry-driven size must halve. A factor of exactly 1 would let a
    # no-op pass for scaling.
    ct = case_type_file("scaled", characteristic=case_type_scale.
                        CharacteristicLength("body", "x_extent", 2.0))
    cfg = drawing(roles=BOTH, ct=ct)
    applied = w.apply(w.plan(cfg), cfg, {"bl_initial_thickness": 0.001})
    out = applied.config
    ok = check(abs(out.surface_mesh_size - 0.01) < 1e-12 and out.mesh_mode == 1,
               "8. the geometry-driven sizes are SCALED by the characteristic "
               "length measured on THIS drawing — 0.02 authored on a 2.0 body "
               "lands as 0.01 on a 1.0 one (surface_mesh_size=%r, mesh_mode=%r)"
               % (out.surface_mesh_size, out.mesh_mode))
    ok &= check(abs(out.topology.ogrid_cell - 0.025) < 1e-12,
                "8. ...and so is the family's own cell size (%r)"
                % out.topology.ogrid_cell)
    ok &= check(out.bl_initial_thickness == 0.001,
                "8. ...while the physical parameter is carried through UNSCALED "
                "and exactly as confirmed — a smaller body does not have a "
                "thinner boundary layer (%r)" % out.bl_initial_thickness)
    segs = (out.topology.ogrid_body_segs, out.topology.ogrid_far_segs)
    ok &= check(all(str(i) in segs[0] for i in BODY_IDS)
                and all(str(i) in segs[1] for i in FAR_IDS),
                "8. ...and the bindings hold the OPERATOR's own segment ids "
                "(%r)" % (segs,))
    # PARSED, never substring-matched. The first draft of this check searched the
    # serialised topology for each authoring id as text, and `"0` matched the
    # scaled cell size `0.025` — a detector that fails on a correct result is
    # worse than none, because it is read as the defect it is looking for.
    bound = set()
    for text in segs:
        bound.update(int(t) for t in str(text).replace(",", " ").split())
    leaked = sorted(bound & set(AUTHORING_IDS))
    ok &= check(out.topology.ogrid_body_geom == BODY,
                "8. ...naming the operator's own geometry (%r)"
                % out.topology.ogrid_body_geom)
    ok &= check(not leaked and bound == set(BODY_IDS) | set(FAR_IDS),
                "8. ...and the bound ids are EXACTLY the operator's, with none "
                "from an authoring drawing, because a case type carries none "
                "(bound=%r, leaked=%r)" % (sorted(bound), leaked))
    return ok


def check_9(w, _t):
    """A corrected confirmation is what is applied AND what is described."""
    cfg = drawing(roles=BOTH)
    plan = w.plan(cfg)
    mine = {"bl_initial_thickness": 2e-6}
    said = [c for c in plan.changes(cfg, mine)
            if c.name == "bl_initial_thickness"]
    applied = w.apply(plan, cfg, mine)
    ok = check(len(said) == 1 and said[0].now == 2e-6,
               "9. a confirmation that CORRECTS the offered value is what the "
               "report describes (%r)" % (said[0].now if said else None,))
    ok &= check(applied.config.bl_initial_thickness == 2e-6,
                "9. ...and what is applied, so the dialog cannot describe a "
                "different apply from the one it performs (%r)"
                % applied.config.bl_initial_thickness)
    ok &= check(said and said[0].confirmed,
                "9. ...and the row says it is a CONFIRMED value rather than one "
                "the ruler produced")
    return ok


def check_11(w, _t):
    """A role this case type does not need is kept, not bound, and named."""
    cfg = drawing(roles=dict(BOTH, seam="%s" % BODY))
    plan = w.plan(cfg)
    ok = check(plan.ignored == ("seam",) and plan.ready(),
               "11. a role left over from another case type is IGNORED rather "
               "than refused — having looked at a second case type is not an "
               "error (ignored=%r, ready=%r)" % (plan.ignored, plan.ready()))
    said = "\n".join(plan.describe(cfg))
    ok &= check("'seam' is assigned" in said and "kept and not used" in said,
                "11. ...and it is said out loud rather than dropped in silence")
    applied = w.apply(plan, cfg, {"bl_initial_thickness": 0.001})
    ok &= check(sorted(b.role for b in applied.bindings) == ["body", "farfield"],
                "11. ...and nothing binds it (%r)"
                % ([b.role for b in applied.bindings],))
    ok &= check(cfg.case_type_roles.get("seam") == BODY,
                "11. ...and it is still on the operator's configuration "
                "afterwards (%r)" % (cfg.case_type_roles,))
    return ok


def check_13(w, _t):
    """The confirmation dialog answers Cancel on a platform with no display."""
    from app.views.case_type_apply_dialog import CaseTypeApplyDialog
    cfg = drawing(roles=BOTH)
    plan = w.plan(cfg)
    dlg = CaseTypeApplyDialog(None, plan, cfg)
    ok = check(dlg.exec() == 0,
               "13. the REAL dialog answers Cancel headless rather than "
               "blocking on an event loop — `gui-seams.md`'s rule that a "
               "bespoke dialog makes its own early return, and the one property "
               "the checks above cannot see because they swap the class out")
    # ...and Cancel is the SAFE default here, which is the half that matters:
    # the unattended path then gets a refusal, never somebody else's first cell
    # height applied in silence.
    ok &= check(bool(refusal(w.apply, plan, cfg)),
                "13. ...and answering Cancel leaves the physical parameter "
                "unconfirmed, so the service refuses — an unattended apply "
                "cannot write somebody else's Reynolds number")
    return ok


def check_14(w, _t):
    """A ruler that cannot be read REFUSES; it never falls back to the authored numbers."""
    ct = case_type_file("unmeasurable", characteristic=case_type_scale.
                        CharacteristicLength("body", "x_extent", 2.0))
    # EVERY geometry bears `farfield`, so NOTHING bears the `body` role the
    # ruler names — `case_type_scale.measure_role`'s own refusal.
    cfg = drawing(roles=BOTH, ct=ct)
    cfg.geom_roles = {BODY: {"role": "farfield"}, FAR: {"role": "farfield"}}
    why = refusal(w.plan, cfg)
    ok = check("body" in why,
               "14. a case type whose characteristic length cannot be measured "
               "on this drawing REFUSES, naming the role nothing bears (%r)"
               % (why[:90] + "…" if why else "",))
    # The first cut called `case_type_scale.fit` beside `plan` and carried its
    # reason into the report. `fit` is non-empty ONLY when it catches what
    # `plan` has already let escape, so that branch was dead on arrival — and
    # had it worked it would have been WRONG here: falling back to the authored
    # numbers puts a 1 m body's 0.02 surface size on a 10 mm one.
    ok &= check(not hasattr(w.ApplyPlan, "why_not")
                and "why_not" not in str(getattr(w.ApplyPlan, "__slots__", ())),
                "14. ...and there is no 'applied AS AUTHORED' fallback to carry "
                "a reason about, which is `case_type_scale`'s own rule: A RULER "
                "THAT CANNOT BE READ REFUSES")
    return ok


#: Every check an in-memory mutant can reach, by name. Checks 1's `.hws` half,
#: 10 and 12 drive live `AppController`s built from the already-imported modules,
#: so no mutant reaches them; they run once, below, outside this map.
CHECKS = {
    "1": check_1, "2": check_2, "3": check_3, "4": check_4, "5": check_5,
    "6": check_6, "7": check_7, "8": check_8, "9": check_9, "11": check_11,
    "13": check_13, "14": check_14,
}


def run_all(w, t, only=None):
    """Run the in-memory checks against one world; return `{name: passed}`."""
    out = {}
    for name, fn in CHECKS.items():
        if only and name != only:
            continue
        before = len(_FAILS)
        try:
            fn(w, t)
        except Exception as exc:                       # noqa: BLE001
            # A mutant that CRASHES is a failure of that check, not of the
            # harness — scoring a crash as silence is how an injection comes
            # back inert.
            print("     (check %s raised %s: %s)" % (name, type(exc).__name__,
                                                     exc))
            _FAILS.append("check %s raised" % name)
        out[name] = len(_FAILS) == before
    return out


print("══ the real, unmutated world ═════════════════════════════════════════")
_W, _T = world()
_REAL = run_all(_W, _T)


# ══ 1 (second half), 10, 12: the live window ══════════════════════════════
from app.controller import AppController                         # noqa: E402

with tempfile.TemporaryDirectory() as _tmp:
    _c = AppController()
    _c.global_mesh_config.load_from_dict(drawing(roles=BOTH).to_dict())
    _c.push_panel_config(_c.main_window.mesh_config_panel,
                         _c.global_mesh_config)
    _hws = os.path.join(_tmp, "case.hws")
    with open(_hws, "w", encoding="utf-8") as _f:
        json.dump(_c.workspace_dict(), _f, indent=2)
    _c2 = AppController()
    _c2.open_workspace_path(_hws)
    _reopened = _c2.global_mesh_config.case_type_roles
    _shown = _c2.main_window.mesh_config_panel.case_type_roles_table.read()
    check(_reopened == BOTH and _shown == BOTH,
          "1. ...and the assignment survives saving and reopening a real `.hws` "
          "through two live AppControllers, in the model AND in the table the "
          "operator is looking at (model=%r, table=%r)" % (_reopened, _shown))

    # ══ 12. the whole act, through the window ══════════════════════════════
    _ctl = AppController()
    _ctl.global_mesh_config.load_from_dict(drawing(roles=BOTH).to_dict())
    _ctl.push_panel_config(_ctl.main_window.mesh_config_panel,
                           _ctl.global_mesh_config)
    _panel = _ctl.main_window.mesh_config_panel
    _before_size = _panel.get_config().surface_mesh_size

    # A ROW CREATED AFTER CONSTRUCTION REACHES THE MODEL. This is the one
    # property the `panel_edited` protocol exists for and the only one no
    # in-memory check above can see: `_read_case_type_roles` is driven through
    # `panel.get_config()` there, which is the panel's own read and not the
    # route a click takes. `undo_ctrl._wire_widget_edits` traverses children
    # ONCE at construction, so a combo built by a later `set_plan` is invisible
    # to it — the restart chooser's defect (#31) — and only the composite's own
    # signal carries the edit to `on_panel_edited`.
    # A DIFFERENT ROW from the one it is on. The drawing was pushed with both
    # roles confirmed, so the body combo already sits on the pre-selection and
    # `setCurrentIndex` to the CURRENT index emits nothing — the trap
    # `test_case_type_picker.py` records its own first draft falling into, where
    # a working leg is reported broken.
    _tbl = _panel.case_type_roles_table
    _combo = _tbl._rows["body"][0]
    _combo.setCurrentIndex(_combo.findData(BODY))
    check(_ctl.global_mesh_config.case_type_roles == dict(BOTH, body=BODY),
          "12. a row BUILT AFTER CONSTRUCTION reaches the model by the route a "
          "click takes — the table's own `panel_edited`, which is what "
          "`undo_ctrl._wire_widget_edits` connects for a composite that rebuilds "
          "its children (%r)" % (_ctl.global_mesh_config.case_type_roles,))
    _ctl.push_panel_config(_panel, _ctl.global_mesh_config)

    # The confirmation dialog is the one interrupt, and a gate cannot press OK
    # in a modal: its two methods are what the controller calls, so the dialog
    # CLASS is swapped for one that answers them. The controller's own code is
    # untouched, which is the point — what is being driven is the wiring and the
    # commit, not Qt's event loop.
    import app.controllers.case_type_apply_ctrl as _ctrl_mod

    class _AutoDialog:
        def __init__(self, _parent, plan, _config):
            self._plan = plan

        def exec(self):
            return 1

        def confirmed(self):
            return {c.name: c.offered for c in self._plan.confirmations}

    _real_dialog = _ctrl_mod.CaseTypeApplyDialog
    _ctrl_mod.CaseTypeApplyDialog = _AutoDialog
    try:
        _panel.apply_case_type_requested.emit()
    finally:
        _ctrl_mod.CaseTypeApplyDialog = _real_dialog
    _after = _panel.get_config()
    check(_before_size != 0.02 and _after.surface_mesh_size == 0.02
          and _after.mesh_mode == 1,
          "12. the button's signal reaches the controller and the PANEL ends up "
          "holding the fitted configuration — picker, table, apply, all through "
          "the window (before=%r, after=%r)"
          % (_before_size, _after.surface_mesh_size))
    check(all(str(i) in (_after.topology.ogrid_body_segs or "")
              for i in BODY_IDS),
          "12. ...with the family bound to the operator's own segments (%r)"
          % _after.topology.ogrid_body_segs)

    # ══ 12b. the refusal overlay goes with the refusal ════════════════════
    # A previous attempt's pre-flight mark must not survive a successful apply:
    # an overlay pointing at a curve that is now fine is what
    # `mesh_gen_diag_ctrl` calls worse than no overlay. Driven by setting the
    # mixin's own flag and re-applying, because the FLAG is what decides whether
    # the clear is ours to make.
    _ctl._preflight_highlight = True
    _ctrl_mod.CaseTypeApplyDialog = _AutoDialog
    try:
        _panel.apply_case_type_requested.emit()
    finally:
        _ctrl_mod.CaseTypeApplyDialog = _real_dialog
    check(not getattr(_ctl, "_preflight_highlight", False),
          "12. a successful apply CLEARS a previous attempt's pre-flight "
          "overlay, so the canvas stops pointing at a curve that is now fine "
          "(flag=%r)" % getattr(_ctl, "_preflight_highlight", None))

    # ══ 15. the two orders are the same (story 5) ═════════════════════════
    # "Pick the case type before I draw, or draw before I pick, so that I am not
    # forced into an order that does not match how I think." Measured as an
    # EQUALITY between the two orders rather than as a property of one, because
    # the defect was precisely an asymmetry: drawing first worked, picking first
    # left every row on `(not assigned)` with no candidate and no pre-selection,
    # the role combos having been built against an empty drawing with nothing to
    # rebuild them when the curves arrived.
    def _role_rows(tbl):
        return {r: [c.itemText(i) for i in range(c.count())]
                for r, (c, _s) in tbl._rows.items()}

    from PyQt6.QtWidgets import QFileDialog

    # ORDER A: pick FIRST, then draw through the REAL Browse handler — the
    # action a user performs, and the one that actually inserts list rows.
    # Emitting `geom_files_changed` is NOT this test: that signal is the panel
    # telling the controller, and a probe that emitted it would pass with the
    # wire removed.
    _a = AppController()
    _a.global_mesh_config.load_from_dict(
        drawing(roles={}, geoms=[], geom_roles={}).to_dict())
    _a.push_panel_config(_a.main_window.mesh_config_panel, _a.global_mesh_config)
    _ap = _a.main_window.mesh_config_panel
    _empty = _role_rows(_ap.case_type_roles_table)
    _real_browse = QFileDialog.getOpenFileNames
    QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([BODY, FAR], ""))
    try:
        _ap._on_browse_geom()
    finally:
        QFileDialog.getOpenFileNames = _real_browse
    _first_pick = _role_rows(_ap.case_type_roles_table)

    # ORDER B: draw first, then pick.
    _b = AppController()
    _b.global_mesh_config.load_from_dict(
        drawing(roles={}, geom_roles={}).to_dict())
    _b.push_panel_config(_b.main_window.mesh_config_panel, _b.global_mesh_config)
    _bp = _b.main_window.mesh_config_panel
    _first_draw = _role_rows(_bp.case_type_roles_table)

    check(_empty and all(len(v) == 1 for v in _empty.values()),
          "15. with a case type picked and nothing drawn, the roles are SHOWN "
          "with nothing to offer — the question is asked before the answer "
          "exists (%r)" % ({k: len(v) for k, v in _empty.items()},))
    check(_first_pick == _first_draw and _first_pick != _empty,
          "15. ...and PICK-THEN-DRAW ends up identical to DRAW-THEN-PICK, "
          "pre-selections and candidates alike, so neither order is the "
          "privileged one (#158 story 5) (pick-first=%r, draw-first=%r)"
          % ({k: len(v) for k, v in _first_pick.items()},
             {k: len(v) for k, v in _first_draw.items()}))
    check(any("pre-selected" in t for v in _first_pick.values() for t in v),
          "15. ...and the pre-selection really is offered on the pick-first "
          "route, which is the half that was missing: the combos were built "
          "against an empty drawing and nothing rebuilt them")

    # INJECTION H: a DISCONNECT, not a source mutation. The subject is a WIRE —
    # there is no module attribute to swap for one — which is the shape
    # `test_case_type_picker.py`'s injection D already has. The panel is live and
    # already imported, so `world()` cannot reach it either way.
    _m = _ap.geom_list_widget.model()
    _m.rowsInserted.disconnect(_ap._on_field_edited)
    _m.rowsRemoved.disconnect(_ap._on_field_edited)
    try:
        _c = AppController()
        _c.global_mesh_config.load_from_dict(
            drawing(roles={}, geoms=[], geom_roles={}).to_dict())
        _c.push_panel_config(_c.main_window.mesh_config_panel,
                             _c.global_mesh_config)
        _cp = _c.main_window.mesh_config_panel
        # The NEW panel's own wire has to go too: the disconnect above is on
        # `_ap`, and every AppController builds its own.
        _cm = _cp.geom_list_widget.model()
        _cm.rowsInserted.disconnect(_cp._on_field_edited)
        _cm.rowsRemoved.disconnect(_cp._on_field_edited)
        QFileDialog.getOpenFileNames = staticmethod(
            lambda *a, **k: ([BODY, FAR], ""))
        try:
            _cp._on_browse_geom()
        finally:
            QFileDialog.getOpenFileNames = _real_browse
        _broken = _role_rows(_cp.case_type_roles_table)
        check(_broken != _first_pick
              and all(len(v) == 1 for v in _broken.values()),
              "injection H. with the geometry-list wire disconnected, "
              "pick-then-draw goes back to offering NOTHING — so check 15 is "
              "measuring that wire and not something else (%r)"
              % ({k: len(v) for k, v in _broken.items()},))
    finally:
        _m.rowsInserted.connect(_ap._on_field_edited)
        _m.rowsRemoved.connect(_ap._on_field_edited)

    # ══ 10. one undo step ═════════════════════════════════════════════════
    _ctl.flush_project_snapshot()
    _undone = None
    if hasattr(_ctl, "undo"):
        _ctl.undo()
        _undone = _panel.get_config()
    check(_undone is not None and _undone.surface_mesh_size == _before_size
          and _undone.mesh_mode != 1,
          "10. Ctrl+Z after an apply restores EVERY moved field at once, so an "
          "operator who dislikes a case type is one keystroke from their own "
          "numbers rather than twenty edits (surface_mesh_size=%r, mesh_mode=%r)"
          % (getattr(_undone, "surface_mesh_size", None),
             getattr(_undone, "mesh_mode", None)))


# ══ the injections ════════════════════════════════════════════════════════
print("══ injections ════════════════════════════════════════════════════════")


def injected(name, target, src, red):
    """Build the mutant, prove it differs, require `red` to fail and the rest green."""
    kw = {target: src}
    before = len(_FAILS)
    w, t = world(**kw)
    got = run_all(w, t)
    reddened = not got.get(red, True)
    others = [k for k, ok in got.items() if not ok and k != red]
    # The harness's own failures are the mutant's, not the tree's: they are
    # dropped so an injection cannot leave a red mark on a green world.
    del _FAILS[before:]
    check(reddened, "injection %s. check %s goes RED under the mutation" % (name, red))
    check(not others,
          "injection %s. ...and NO other check moves, so the mutation is "
          "localised to the property it is about (%r)" % (name, others))


_S = _SRC["app.services.case_type_apply"]
_TS = _SRC["app.views.panels.case_type_roles_table"]

injected("A", "case_type_apply",
         mutate("    fitted = copy.deepcopy(config)", "    fitted = config", _S),
         "6")
injected("B", "case_type_apply",
         mutate("""    problems = plan_.problems()""",
                """    if parts:
        raise CaseTypeError("\\n".join(parts))
    problems = plan_.problems()""", _S),
         "5")
injected("C", "case_type_apply",
         mutate("    assigned = {r: v for r, v in stored.items() if r in wanted}",
                "    assigned = dict(stored)", _S),
         "11")
injected("D", "case_type_roles_table",
         mutate("""            if data == UNASSIGNED:
                continue""",
                """            if data == UNASSIGNED:
                out[role] = ACCEPT_GUESS
                continue""", _TS),
         "2")
injected("E", "case_type_roles_table",
         mutate("""        if shape != self._shape:""",
                """        shape = (shape, tuple(sorted((values or {}).items())))
        if shape != self._shape:""", _TS),
         "4")
injected("F", "case_type_apply",
         mutate("            now = answered.get(name, value)",
                "            now = value", _S),
         "9")

print("══ negative control ══════════════════════════════════════════════════")
_W2, _T2 = world()
_AGAIN = run_all(_W2, _T2)
check(all(_AGAIN.values()) and all(_REAL.values()),
      "injection G. negative control: the real, unmutated world passes every "
      "check both before and after the mutations, so the failures above are the "
      "mutations and not the checker (%r)"
      % sorted(k for k, ok in _AGAIN.items() if not ok))


print()
if _FAILS:
    print("FAILURES (%d):" % len(_FAILS))
    for f in _FAILS:
        print("  - " + f)
# `os._exit` because Qt's offscreen teardown crashes on a machine with no GPU
# AFTER every check has printed, and `run_all.sh` reads that crash as a failing
# test — the house ending for every script here that builds a QApplication,
# gated by `test_qt_teardown_exit.py`. It skips stdout flushing, hence the flush.
print("All checks passed." if not _FAILS else "", flush=True)
sys.stdout.flush()
os._exit(1 if _FAILS else 0)
