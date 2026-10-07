#!/usr/bin/env python3
"""A CASE TYPE CARRIES CONFIG FIELDS AS A SPARSE OVERLAY (issue #162, parent #158).

#160 gave a case type thresholds and a four-state verdict; #161 made every
threshold a measurement off a reference mesh. Both grade a mesh after the fact
and neither says how to PRODUCE one — so an operator still configured 104 fields
to mesh a problem class they recognise. This ticket is the other half: the case
type starts carrying the settings that produced its reference mesh, and the tool
starts noticing when the operator moves away from them.

WHY SPARSE IS THE WHOLE DESIGN. A case type records only the fields it actually
takes a position on. The alternative — a full snapshot — means every case type in
the tree disagrees with the model the day a mesher parameter is added, and nobody
can tell which of those disagreements was an opinion. User story 36 states it:
"a case type should record only the fields it has an opinion about, so that it
does not go stale every time a new field is added to the mesher".

WHY A DEVIATION IS MARKED RATHER THAN REFUSED. The thresholds were measured on a
mesh the case type's own settings produced. An operator who changes one of those
settings has moved the ground under the measurement, so presenting the verdict
unqualified would be a lie — and withholding it would teach operators not to
touch anything, which is the opposite of user story 21. So the state is
unchanged, the verdict is marked, the moved fields are named, and the standing
drops by exactly one audible notch.

What this pins down:

  1. CAPTURE IS SPARSE AND IS A SUBTRACTION. The fields recorded off a working
     case are exactly the ones it moved OFF THE DEFAULT — three of 74 for the
     shipped O-grid `.dat` — and a field sitting at its default is recorded only
     when the maintainer names it.
  2. A ROUND TRIP PRESERVES EXACTLY THAT SET. Save -> load gives back the same
     names with the same values and NO others; a case type that owns nothing
     writes no `fields` section at all and comes back owning nothing; a v2
     document (every case type authored before this ticket) loads as one of
     those rather than failing.
  3. APPLYING SETS THOSE FIELDS AND LEAVES EVERY OTHER AT ITS ORDINARY DEFAULT,
     asserted over every field of both models rather than over the ones the
     overlay names — including the family and its topology parameters.
  4. A MESHER FIELD NO CASE TYPE MENTIONS INVALIDATES NOTHING. Measured against
     a model class carrying a field this build does not have: the shipped case
     type still loads, still applies to the same values, and still deviates on
     nothing. The new field becomes OWNABLE and is not OWNED.
  5. DEVIATION NAMES THE OWNED FIELDS AND ONLY THOSE. Moving an owned field
     reports it; moving a field the case type has no opinion about reports
     nothing; putting one back clears it; a config written to a `.dat` and read
     back is NOT a deviation, because both sides are compared AS THE WRITER
     WOULD WRITE THEM; and the smallest edit that writer CAN carry — one `%.6g`
     step on a 1e-3 first-cell height — IS one. Both ends, because a comparison
     that is wrong at either is wrong, and the first version of this service was
     wrong at the coarse one. The `%.10g` half of that rule LEFT in #163 with
     the one field it named, and this check now holds the condition it left
     under rather than the rule.
  6. A DEVIATED VERDICT IS STILL ISSUED, IS MARKED, AND NAMES THE FIELDS. The
     STATE is identical to the undeviated one — deviation is not a downgrade of
     the answer — and the report says which fields moved rather than how many.
  7. WHAT DEVIATION COSTS IS STANDING, AND IT IS ONE NOTCH. A deviated `usable`
     is logged at WARNING where an undeviated one is INFO; every other state is
     already at least that and is unmoved. Asserted over all four states.
  8. A FIELD A CASE TYPE MAY NOT OWN IS REFUSED, AND THE REFUSAL SAYS WHY. A
     BINDING is refused because the operator's segment ids are not the
     maintainer's (#164 is roles); a per-project field is refused with its own
     declared reason; an unknown name is refused as unknown. Asserted at all
     three doors — the overlay's constructor, a FILE naming a binding, and
     `capture`, which must refuse BEFORE it reads the name off a config. The
     FOURTEEN bindings today's four families declare are pinned, against the
     models' own fields.
  9. THE THREE QUESTIONS ARE REALLY ANSWERABLE, through the two headless hosts
     driven as SUBPROCESSES: `save_case_type.py --fields-from` captures an
     overlay off a `.dat`, a `.hws` and a pipeline script alike;
     `show_case_type.py` prints the fields a case type owns; `--against` diffs
     two case types; `--config` reports a case's deviation.
 10. QT-FREE, in a subprocess: importing the fields service leaves PyQt6
     unimported. In-process the answer is always "loaded" once anything else
     imported it.
 11. THE HEADLESS HOST JUDGES THE CONFIG THE OPERATOR WROTE, not the one its own
     stage overrode. `_run_mesh` forces `export_vtk` on and both export flags
     are ownable, so handing the verdict that object would report a deviation on
     every headless run of a case type owning one. Read from the SOURCE, like
     `test_case_type_verdict.py`'s "neither host grades" check and with that
     technique's blind spot.

Known blind spots, named rather than papered over:
  - NOTHING HERE SCALES ANYTHING, and since #163 that is a statement about this
    FILE rather than about the tree. The characteristic length, the four kinds
    of length and the physical parameters that must not move with the body are
    `tests/test_case_type_scale.py`'s; every overlay here is applied at 1:1,
    which is what a case type declaring no ruler still does.
  - NOTHING HERE BINDS TO A DRAWING. Bindings are excluded from the vocabulary
    and that exclusion is gated; deriving a binding from a role is #164.
  - NO GUI. There is no picker, no Trial and no Generate — #166 — so "the
    operator can see which fields the case type owns" is measured at the
    headless host, which is where #161 deliberately left the authoring action
    too.
  - AN OVERLAY NAMING A FAMILY CANNOT BE WRITTEN TO A `.dat` ON ITS OWN, which
    check 5's round-trip leg works around rather than fixes: `save_to_file`
    PROJECTS a named family's topology document, and every family but the H-grid
    refuses to build one without a geometry to bind to. That is the gap #164
    closes by deriving bindings from roles, and it is why check 5's precision leg
    carries no family.
  - THE EXCLUSION LIST IS A JUDGEMENT. That `output_filename` is per-case and
    `bl_growth_rate` is not is argued in the service's docstring and pinned
    here; nothing measures that the line is in the right place.

INJECTIONS — AUTOMATED, by exec'ing a mutated copy of the service sources and
re-running the same check functions against the mutant. Each asserts the
mutation is well-formed and really differs, then that the named check fails AND
that no other check moves (`others_green`):

  A. `_binding` stops recognising a binding suffix -> check 8 fails: a case type
     could own `topology.ogrid_body_segs`, which is a stable segment id into the
     MAINTAINER's geometry.
  B. `DAT_PRECISION` raised to `%.17g` -> check 5 fails at the ROUNDED end: a
     config written to a `.dat` and read back reports a deviation nobody made.
  B2. `DAT_PRECISION` dropped to `%.2g` -> check 5 fails at the COARSE end: a
     real edit to a first-cell height disappears. The two together are why the
     constant is the writer's own format and not a tolerance beside it.
  C. `capture_differences` stops subtracting the default -> check 1 fails: the
     overlay is a full snapshot, which is the design this ticket exists against.
  D. `judge` stops carrying the deviations onto the verdict -> check 6 ALONE
     fails. Check 7 builds its verdicts directly and does not move, which is
     what makes it a statement about the GRADE rather than about this plumbing.
  E. `DEVIATED_FLOOR` lowered to `INFO` -> check 7 ALONE fails: the caveat is
     still printed and nothing raises the grade, so an unattended log shows a
     deviated pass as an ordinary one. The check declares its own grade
     ordering (`_LOUDNESS`), or lowering that constant would move the
     expectation along with the answer.
  F. `CaseType.to_dict` drops the `fields` section -> check 2 fails: a case
     type whose opinion never reaches the file anybody else reads.
  G. `_set` ignores the `topology.` prefix -> checks 3 and 5 fail: a family and
     its parameters are written onto the mesh config as flat attributes nothing
     reads.
  H. the HOST -- which runs as a subprocess and so cannot see an in-memory
     mutant -- stops printing the owned fields, and check 9 fails. It runs a
     mutated COPY of `show_case_type.py`, with the real unmutated host asserted
     green beside it.
  J. the RUNNER -- read off disk by check 11, so no in-memory mutant reaches it
     -- judges the config its own stage overrode, and check 11 fails.
  I. negative control: the unmutated services pass every check.

Run:  python3 tools/PreProcessor/tests/test_case_type_fields.py
Needs no build tree, no Qt and no network.
"""
import ast
import dataclasses
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_SAVE_HOST = os.path.join("tools", "PreProcessor", "save_case_type.py")
_SHOW_HOST = os.path.join("tools", "PreProcessor", "show_case_type.py")
_RUNNER = os.path.join("tools", "PreProcessor", "gui", "app", "services",
                       "pipeline_runner.py")
_SHIPPED = os.path.join("examples", "case_types", "ogrid_circle.casetype.json")
#: A real working case in each of the three shapes `read_config` classifies.
_OGRID_DAT = os.path.join("config", "multiblock_ogrid.dat")
_PIPELINE = os.path.join("config", "pipeline", "multiblock_cgrid_demo.json")
#: The mesh section the WORKSPACE leg of check 9 is built from. A source rather
#: than a workspace, because this repo ships no `.hws`: the only one it had was a
#: GUI session's default name that `.gitignore` excludes BY NAME, so the leg that
#: read it ran on the machine that happened to have the file and nowhere else.
#: The hybrid case is chosen because it moves 14 fields where the `.dat` leg
#: moves 3 — the `--against` diff needs the two to disagree about something.
_WS_SOURCE = os.path.join("config", "Background_para.dat")

#: name -> repo-relative source, in DEPENDENCY order: the figures, the overlay,
#: the document, the verdict.
_RELS = [
    ("app.services.case_type_reference",
     "tools/PreProcessor/gui/app/services/case_type_reference.py"),
    ("app.services.case_type_fields",
     "tools/PreProcessor/gui/app/services/case_type_fields.py"),
    ("app.services.case_type",
     "tools/PreProcessor/gui/app/services/case_type.py"),
    ("app.services.case_type_verdict",
     "tools/PreProcessor/gui/app/services/case_type_verdict.py"),
]

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _read(rel):
    with open(os.path.join(_REPO, rel), encoding="utf-8") as fh:
        return fh.read()


_SRC = {name: _read(rel) for name, rel in _RELS}


# --- the world: a FRESH set of service modules, optionally mutated ------------
# Every check is a pure function of this set, which is what makes the injections
# cheap: exec a mutated copy, ask the same function. The real world is loaded
# through the same path as a mutant, so the negative control and the injections
# are symmetric rather than one going through `import`.
def _exec_module(name, rel, source):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = os.path.join(_REPO, rel)
    sys.modules[name] = mod
    # The PACKAGE attribute too: `from app.services import case_type_fields`
    # resolves through `getattr(app.services, ...)` first, so a mutant left only
    # in sys.modules would be shadowed by the real module the package already
    # holds — and the injection would silently test the real code (#160).
    pkg = sys.modules.get("app.services")
    if pkg is not None:
        setattr(pkg, name.rsplit(".", 1)[1], mod)
    exec(compile(source, mod.__file__, "exec"), mod.__dict__)
    return mod


class World:
    """The four services under test, named rather than unpacked positionally."""

    def __init__(self, built):
        self.fields = built["case_type_fields"]
        self.case_type = built["case_type"]
        self.verdict = built["case_type_verdict"]


def world(**mutated):
    """A `World` built from the given source.

    `mutated` is keyed by the LAST segment of a module name, so a caller writes
    `world(case_type_fields=src)` rather than spelling the package out.
    """
    import app.services  # noqa: F401  - ensure the package exists to patch
    pkg = sys.modules["app.services"]
    saved_mods = {n: sys.modules.get(n) for n, _ in _RELS}
    saved_attrs = {n.rsplit(".", 1)[1]: getattr(pkg, n.rsplit(".", 1)[1], None)
                   for n, _ in _RELS}
    try:
        built = {}
        for name, rel in _RELS:
            short = name.rsplit(".", 1)[1]
            built[short] = _exec_module(name, rel,
                                        mutated.get(short, _SRC[name]))
        return World(built)
    finally:
        for name, mod in saved_mods.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod
        for attr, mod in saved_attrs.items():
            if mod is None:
                if hasattr(pkg, attr):
                    delattr(pkg, attr)
            else:
                setattr(pkg, attr, mod)


from app.models.mesh_config import MeshConfig  # noqa: E402
from app.services import mesh_shape_stats  # noqa: E402
from app.services.topology_params import TopologyModel  # noqa: E402

#: The shipped O-grid's published figures, read off its sidecar on 2026-09-30 —
#: the same numbers the other two case-type gates use, so the three cannot
#: describe three different meshes.
OGRID = dict(cells=4608, median=1.845977, p95=23.662285, maximum=32.767868)
OGRID_LAYER = dict(cells=2304, median=5.184358, p95=28.507718, maximum=32.767868)
OGRID_BULK = dict(cells=2304, median=1.692763, p95=1.877756, maximum=1.881891)

#: What the shipped O-grid `.dat` has moved off the default, verified by hand
#: against the file on 2026-10-01. Pinned rather than re-derived, because "the
#: capture is a subtraction" is only a claim if the expected answer is itself
#: computed by the thing under test.
SHIPPED_FIELDS = {"mesh_mode": 1, "bl_initial_thickness": 0.001,
                  "export_vtk": True}

#: Every binding parameter today's four families declare. Pinned so that a fifth
#: family's bindings being excluded by SUFFIX is a measured property rather than
#: a hope — this list must grow when one lands, and the gate says so.
BINDINGS = (
    "topology.ogrid_body_geom", "topology.ogrid_body_segs",
    "topology.ogrid_far_geom", "topology.ogrid_far_segs",
    "topology.cgrid_body_geom", "topology.cgrid_body_segs",
    "topology.cgrid_far_geom", "topology.cgrid_far_segs",
    "topology.tworing_body_geom", "topology.tworing_body_segs",
    "topology.tworing_seam_geom", "topology.tworing_seam_segs",
    "topology.tworing_far_geom", "topology.tworing_far_segs",
)


@dataclasses.dataclass
class LaterMeshConfig(MeshConfig):
    """`MeshConfig` as a LATER build of the mesher might declare it.

    One scalar field this build does not have, which is the whole of what
    "a mesher field that no case type mentions" means. A subclass rather than a
    patched module, so the real `MeshConfig` every other check uses is untouched.
    """

    a_field_invented_after_this_case_type: float = 7.5


def summary(metric="quad_midline_ratio", whole=None, layer=None, bulk=None,
            source="<constructed>"):
    """A `ShapeSummary` as the sidecar reader would have produced one."""
    whole = dict(OGRID if whole is None else whole)
    return mesh_shape_stats.ShapeSummary(
        metric=metric, source=source,
        layer=None if layer is None else mesh_shape_stats.ShapeFigures(**layer),
        bulk=None if bulk is None else mesh_shape_stats.ShapeFigures(**bulk),
        **whole)


def split_summary(**kw):
    kw.setdefault("layer", OGRID_LAYER)
    kw.setdefault("bulk", OGRID_BULK)
    return summary(**kw)


def shipped(w):
    """The shipped case type, loaded through `w`'s own (possibly mutant) code."""
    return w.case_type.load(os.path.join(_REPO, _SHIPPED))


def overlay(w, values):
    return w.case_type.FieldOverlay(values)


#: An overlay exercising BOTH halves of the vocabulary — mesh fields and a
#: family with its parameters — since "including the family and its topology
#: parameters" is the acceptance criterion a mesh-only overlay cannot measure.
FAMILY_OVERLAY = {
    "mesh_mode": 1,
    "bl_initial_thickness": 0.0012345678901234,
    "export_vtk": True,
    "bc_xmin": "inlet",
    "topology.family": "ogrid",
    "topology.ogrid_splits": 3,
    "topology.ogrid_cell": 0.02,
    "topology.ogrid_radial_count": 48,
}


# --- checks -------------------------------------------------------------------
def check_capture_is_sparse(w):
    """What a working case records is what it MOVED, not what it holds."""
    out = []
    F = w.fields
    config = F.read_config(os.path.join(_REPO, _OGRID_DAT))
    captured = F.capture_differences(config)
    if dict(captured.values) != SHIPPED_FIELDS:
        out.append("capturing %s gave %s, not the fields it moved off the "
                   "default (%s)" % (_OGRID_DAT, dict(captured.values),
                                     SHIPPED_FIELDS))
    total = len(F.ownable_names())
    if len(captured) >= total:
        out.append("the capture recorded %d of %d ownable fields, which is a "
                   "snapshot rather than an opinion" % (len(captured), total))
    # A field sitting AT the default is not recorded...
    if captured.owns("bl_layers"):
        out.append("bl_layers is at its default in that case and was recorded "
                   "anyway")
    # ...unless the maintainer names it, which is the one way a default-valued
    # field becomes an opinion.
    named = F.capture_differences(config, ("bl_layers",))
    if not named.owns("bl_layers"):
        out.append("--field bl_layers did not reach the overlay")
    if named.values.get("bl_layers") != MeshConfig().bl_layers:
        out.append("the named field was recorded as %r, not the case's own "
                   "value" % (named.values.get("bl_layers"),))
    if dict(captured.values) != {k: v for k, v in named.values.items()
                                 if k != "bl_layers"}:
        out.append("naming a field changed what else was captured")
    return out


def check_round_trip_preserves_the_set(w):
    """Save -> load gives back exactly the fields, and nothing else."""
    out = []
    ct = w.case_type
    with tempfile.TemporaryDirectory() as tmp:
        base = shipped(w)
        case = ct.CaseType(base.name, base.metric, base.thresholds,
                           references=base.references, fields=FAMILY_OVERLAY)
        path = os.path.join(tmp, "round.casetype.json")
        ct.save(case, path)
        back = ct.load(path)
        if dict(back.fields.values) != dict(case.fields.values):
            out.append("the overlay came back as %s, not %s"
                       % (dict(back.fields.values), dict(case.fields.values)))
        if back.fields.names != case.fields.names:
            out.append("the overlay came back in a different order: %s vs %s"
                       % (list(back.fields.names), list(case.fields.names)))
        # A case type with NO opinion writes no section at all, so a document
        # that never had one is not given an empty one by a round trip.
        bare = ct.CaseType(base.name, base.metric, base.thresholds,
                           references=base.references)
        bare_path = os.path.join(tmp, "bare.casetype.json")
        ct.save(bare, bare_path)
        with open(bare_path, encoding="utf-8") as fh:
            doc = json.load(fh)
        if "fields" in doc:
            out.append("a case type owning no field wrote a `fields` section: %r"
                       % (doc["fields"],))
        if len(ct.load(bare_path).fields):
            out.append("a case type owning no field loaded as owning some")
        # A v2 document — every case type authored before this ticket — is a v3
        # one that owns nothing, rather than a file this build refuses.
        doc["version"] = 2
        v2_path = os.path.join(tmp, "v2.casetype.json")
        with open(v2_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        try:
            if len(ct.load(v2_path).fields):
                out.append("a v2 document loaded as owning fields")
        except ct.CaseTypeError as exc:
            out.append("a v2 document no longer loads: %s" % exc)
    return out


def check_apply_leaves_the_rest_at_default(w):
    """The overlay's fields are set; EVERY other field is the ordinary default."""
    out = []
    F = w.fields
    applied = F.apply(overlay(w, FAMILY_OVERLAY))
    default = MeshConfig()
    for name, wanted in FAMILY_OVERLAY.items():
        got = (getattr(applied.topology, name.split(".", 1)[1])
               if name.startswith("topology.") else getattr(applied, name))
        if not F.same(wanted, got):
            out.append("applying set %s to %r, not %r" % (name, got, wanted))
    # The claim is about EVERY other field, so it is asked of every field of
    # both models rather than of the ones the overlay happens to name.
    for model, prefix, base in ((applied, "", default),
                                (applied.topology, "topology.",
                                 default.topology)):
        for f in dataclasses.fields(base):
            full = prefix + f.name
            if full in FAMILY_OVERLAY or f.name == "topology":
                continue
            got, want = getattr(model, f.name), getattr(base, f.name)
            if got != want:
                out.append("applying moved %s to %r; the ordinary default is %r"
                           % (full, got, want))
    # Handed a live config it overlays rather than replaces: the operator's own
    # geometry list is not a case type's opinion and must survive.
    live = MeshConfig()
    live.set_geom_files(["a.dat", "b.dat"])
    F.apply(overlay(w, FAMILY_OVERLAY), live)
    if live.geom_files != ["a.dat", "b.dat"]:
        out.append("applying over a live config changed its geometry list to %s"
                   % (live.geom_files,))
    if live.mesh_mode != 1:
        out.append("applying over a live config did not set mesh_mode")
    return out


def check_a_new_mesher_field_changes_nothing(w):
    """A field this build does not have invalidates no existing case type."""
    out = []
    F = w.fields
    new = "a_field_invented_after_this_case_type"
    later = F.ownable_names(LaterMeshConfig)
    if new not in later:
        out.append("a new scalar mesh field did not become ownable at all")
    if set(F.ownable_names()) - set(later):
        out.append("adding a field REMOVED ownable fields: %s"
                   % sorted(set(F.ownable_names()) - set(later)))
    case = shipped(w)
    if dict(case.fields.values) != SHIPPED_FIELDS:
        out.append("the shipped case type owns %s, not %s"
                   % (dict(case.fields.values), SHIPPED_FIELDS))
    if case.fields.owns(new):
        out.append("the shipped case type acquired an opinion about a field "
                   "invented after it")
    applied = F.apply(case.fields, LaterMeshConfig())
    if getattr(applied, new) != LaterMeshConfig().a_field_invented_after_this_case_type:
        out.append("applying an older case type moved the new field to %r"
                   % (getattr(applied, new),))
    moved = F.deviations(case.fields, applied)
    if moved:
        out.append("a case type that mentions none of the new fields deviates "
                   "on %s" % [d.name for d in moved])
    return out


def check_deviation_names_owned_fields_only(w):
    """Owned fields moved are reported; everything else is not a deviation."""
    out = []
    F = w.fields
    ov = overlay(w, FAMILY_OVERLAY)
    config = F.apply(ov)
    if F.deviations(ov, config):
        out.append("the config the case type itself produced reads as deviated")
    # One owned mesh field and one owned topology parameter.
    config.bl_initial_thickness = 0.005
    config.topology.ogrid_splits = 9
    # ...and two fields the case type has NO opinion about, which must not be.
    config.bl_layers = 11
    config.topology.hgrid_nx = 7
    moved = F.deviations(ov, config)
    if [d.name for d in moved] != ["bl_initial_thickness",
                                   "topology.ogrid_splits"]:
        out.append("the deviation named %s, not the two owned fields that moved"
                   % [d.name for d in moved])
    for dev in moved:
        # BOTH values, read back out of the sentence rather than compared
        # against the formatter that wrote it: a check that re-rendered them the
        # same way would pass however wrong the rendering was. Numbers only,
        # which is what both deviated fields carry.
        said = [float(tok) for tok in re.findall(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?",
                                                 dev.describe())]
        for value in (dev.wanted, dev.actual):
            if not any(F.same(value, s) for s in said):
                out.append("the deviation for %s does not say %r: %r"
                           % (dev.name, value, dev.describe()))
    # Putting one back clears it: a deviation is a COMPARISON, not a history.
    config.bl_initial_thickness = FAMILY_OVERLAY["bl_initial_thickness"]
    if [d.name for d in F.deviations(ov, config)] != ["topology.ogrid_splits"]:
        out.append("putting a field back did not clear its deviation")
    # A config written to a `.dat` and read back is not a deviation: the writer
    # formats at `%.6g`, so bit-exact equality would report edits nobody made.
    # NO FAMILY in this overlay, and that is not an oversight: writing a `.dat`
    # PROJECTS a named family's topology document, and a family binds to the
    # operator's own CAD — which a case type cannot carry and #164 is what
    # supplies. The precision claim is about the mesh fields either way.
    with tempfile.TemporaryDirectory() as tmp:
        mesh_only = overlay(w, {k: v for k, v in FAMILY_OVERLAY.items()
                                if not k.startswith("topology.")})
        clean = F.apply(mesh_only)
        path = os.path.join(tmp, "round.dat")
        clean.save_to_file(path)
        reread = F.read_config(path)
        again = F.deviations(mesh_only, reread)
        if again:
            out.append("a config round-tripped through a .dat reads as deviated "
                       "on %s" % [d.describe() for d in again])
        if not isinstance(mesh_only.values["bl_initial_thickness"], float):
            out.append("the round-trip leg no longer carries a float, so it is "
                       "measuring nothing")
        # ...and the OTHER end of the same question: the smallest edit the
        # writer can carry must still read as one. One `%.6g` step on a 1e-3
        # first cell is 1e-8, and a comparison lenient enough to miss it would
        # hide a change the mesher acts on. The first version of this service
        # floored its tolerance at 1.0 and did exactly that.
        nudged = F.read_config(path)
        nudged.bl_initial_thickness = float(
            "%.6g" % (nudged.bl_initial_thickness * 1.00001))
        if nudged.bl_initial_thickness == reread.bl_initial_thickness:
            out.append("the nudge the leg uses is not representable in a .dat, "
                       "so it is measuring nothing")
        elif [d.name for d in F.deviations(mesh_only, nudged)] != \
                ["bl_initial_thickness"]:
            out.append("a one-step edit to bl_initial_thickness (%r -> %r) is "
                       "not reported as a deviation"
                       % (reread.bl_initial_thickness,
                          nudged.bl_initial_thickness))
    # THE `%.10g` LEG LEFT WITH ITS SUBJECT (#163). It compared
    # `length_unit_metres`, the one field `mesh_config_io` writes finer than
    # `%.6g`; #163 made the three `length_unit*` fields unownable — the unit
    # belongs to the operator's drawing, not to a case type — so there is no
    # overlay that can hold one, and `FINER_PRECISION` went with it. That the
    # three really are refused is `tests/test_case_type_scale.py` check 6.
    unownable = [n for n in ("length_unit", "length_unit_metres",
                             "length_unit_name") if n in F.ownable_names()]
    if unownable:
        out.append("%s became ownable again; the `%%.10g` leg this check used "
                   "to carry has to come back with it" % ", ".join(unownable))
    return out


def check_deviated_verdict_is_issued_and_marked(w):
    """Still a verdict, same state, marked, and naming the fields that moved."""
    out = []
    V, F = w.verdict, w.fields
    case = shipped(w)
    config = F.apply(case.fields)
    config.bl_initial_thickness = 0.005
    moved = F.deviations(case.fields, config)
    if [d.name for d in moved] != ["bl_initial_thickness"]:
        out.append("the fixture did not produce the one deviation it meant to")
    plain = V.judge(case, split_summary(), 0)
    marked = V.judge(case, split_summary(), 0, moved)
    if marked.state != plain.state:
        out.append("deviation changed the STATE from %r to %r; it downgrades "
                   "standing, not the answer" % (plain.state, marked.state))
    if not marked.deviated or plain.deviated:
        out.append("deviated=%r / %r is not the distinction the acceptance asks "
                   "for" % (marked.deviated, plain.deviated))
    if marked.headline == plain.headline:
        out.append("a deviated verdict's headline is identical to an "
                   "undeviated one: %r" % marked.headline)
    text = V.report_text(marked)
    if "bl_initial_thickness" not in text:
        out.append("the report does not name the field that moved: %r" % text)
    if "bl_initial_thickness" in V.report_text(plain):
        out.append("the UNdeviated report names a deviated field")
    # Every path carries it, including the ones settled before a figure is read.
    folded = V.judge(case, split_summary(), V.EXIT_ERR_INVERTED, moved)
    if folded.state != V.UNUSABLE or not folded.deviated:
        out.append("a folded mesh judged with deviations came back %r / "
                   "deviated=%r" % (folded.state, folded.deviated))
    if "bl_initial_thickness" not in V.report_text(folded):
        out.append("the exit-9 report does not name the fields that moved")
    return out


#: How loud each grade is, DECLARED HERE rather than read off the service. The
#: expectation has to be independent of the thing under test, or lowering
#: `DEVIATED_FLOOR` would move the answer and the assertion together and the
#: check would pass having measured nothing.
_LOUDNESS = {"INFO": 0, "WARNING": 1, "ERROR": 2}


def check_deviation_costs_standing_only(w):
    """The grade is lifted where it was the quietest, and nowhere else."""
    out = []
    V = w.verdict
    case = shipped(w)
    fake = [type("D", (), {"name": "bl_initial_thickness",
                           "describe": lambda self: "moved"})()]
    for state in V.STATES:
        plain = V.Verdict(state, case)
        marked = V.Verdict(state, case, deviations=tuple(fake))
        if marked.state != plain.state:
            out.append("marking %r changed the state" % state)
        quiet, loud = _LOUDNESS[plain.level], _LOUDNESS[marked.level]
        if plain.level == "INFO":
            if loud <= quiet:
                out.append("a deviated %r is logged at %r, no louder than the "
                           "undeviated %r — the caveat is inaudible"
                           % (state, marked.level, plain.level))
        elif loud != quiet:
            out.append("a deviated %r moved from %r to %r; deviation costs one "
                       "notch and %r was already above it"
                       % (state, plain.level, marked.level, state))
    if V.Verdict(V.USABLE, case).level != "INFO":
        out.append("an undeviated `usable` is no longer INFO, so this check is "
                   "measuring nothing")
    return out


def check_unownable_fields_are_refused(w):
    """A binding, a per-project field and an unknown name, each with its reason."""
    out = []
    F, ct = w.fields, w.case_type
    names = set(F.ownable_names())
    for name in BINDINGS:
        if name in names:
            out.append("%s is ownable; it is a stable segment id into the "
                       "MAINTAINER's geometry" % name)
    # The pin runs BOTH ways: a family added without its bindings reaching this
    # list is what the suffix rule is supposed to cover, and the list is how we
    # find out it did.
    declared = tuple("topology." + f.name for f in dataclasses.fields(TopologyModel)
                     if f.name.endswith(("_geom", "_segs")))
    if declared != BINDINGS:
        out.append("the families declare bindings %s; this gate pins %s — a "
                   "family landed and the pin did not move"
                   % (list(declared), list(BINDINGS)))
    for name, must_say in (("topology.ogrid_body_segs", "BINDING"),
                           ("output_filename", "case name"),
                           ("bc_configured", "GUI state"),
                           ("topology.detached", "one project"),
                           ("mesh_topology_file", "maintainer's tree"),
                           ("geom_files", "not a mesh field"),
                           ("no_such_knob", "not a mesh field")):
        try:
            F.FieldOverlay({name: 1})
        except ct.CaseTypeError as exc:
            if must_say not in str(exc):
                out.append("refusing %s said %r, which does not say why"
                           % (name, str(exc)))
        else:
            out.append("a case type was allowed to own %s" % name)
    # ...and it reaches `capture` BEFORE the name is read off a config, which
    # is the door `--field` comes through: an unchecked read raises a bare
    # AttributeError that no host catches, so the maintainer got a traceback
    # where this message was written for them.
    try:
        F.capture(MeshConfig(), ["mesh_mode", "no_such_knob"])
    except ct.CaseTypeError as exc:
        if "not a mesh field" not in str(exc):
            out.append("capture refused a bad name with %r" % str(exc))
    except Exception as exc:  # deliberately broad: the DEFECT is a bare
        # AttributeError reaching a host, so the check has to catch whatever
        # arrives and name it rather than let the harness die on it.
        out.append("capture raised %s for an unknown field, not CaseTypeError: "
                   "%s" % (type(exc).__name__, exc))
    else:
        out.append("capture read an unknown field off a config without "
                   "refusing it")
    # ...and the refusal reaches a FILE, not only the constructor.
    with tempfile.TemporaryDirectory() as tmp:
        base = shipped(w)
        doc = base.to_dict()
        doc["fields"] = {"topology.ogrid_body_segs": "3,4,5"}
        path = os.path.join(tmp, "bad.casetype.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        try:
            ct.load(path)
        except ct.CaseTypeError:
            pass
        else:
            out.append("a case type file owning a binding loaded")
    return out


def check_the_hosts_answer(w, show_host=""):
    """The three questions, through the two headless hosts, as subprocesses.

    `show_host` lets injection H run a MUTATED COPY of the inspecting script,
    which is the only way this check can be shown able to go red: it launches a
    subprocess against the real files on disk and so cannot see the in-memory
    mutants every other injection uses.
    """
    out = []
    ct = w.case_type
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [_GUI] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))

    def run(host, *args):
        return subprocess.run([sys.executable, host, *args],
                              capture_output=True, text=True, cwd=_REPO, env=env)

    with tempfile.TemporaryDirectory() as tmp:
        mesh = os.path.join(tmp, "mesh_demo.vtk")
        with open(mesh, "w", encoding="utf-8") as fh:
            fh.write("# vtk DataFile Version 3.0\n")
        _write_sidecar(mesh)
        advice_file = os.path.join(tmp, "advice.json")
        with open(advice_file, "w", encoding="utf-8") as fh:
            json.dump({"median": "Put more points round the body."}, fh)

        # THE WORKSPACE KIND, BUILT HERE rather than read off a shipped file —
        # see `_WS_SOURCE`. The container is the shape `project_state_ctrl`
        # writes (`format_version` / `sessions` / `project.mesh_config`, which
        # is what `project_file_kind.looks_like_workspace` answers on), and the
        # section inside it comes through the model's own `to_dict`, so this is
        # the document the GUI saves and not a hand-typed lookalike.
        ws_file = os.path.join(tmp, "case.hws")
        with open(ws_file, "w", encoding="utf-8") as fh:
            json.dump({"format_version": 2, "sessions": [], "project": {
                "mesh_config": w.fields.read_config(
                    os.path.join(_REPO, _WS_SOURCE)).to_dict()}}, fh)

        written = {}
        # ONE capture per file KIND, because `read_config` classifies by content
        # and a host that only ever saw a `.dat` would be a host that works for
        # one third of this repo's own working cases.
        for label, source, expect in (
                ("dat", os.path.join(_REPO, _OGRID_DAT), SHIPPED_FIELDS),
                ("pipeline", os.path.join(_REPO, _PIPELINE), None),
                ("workspace", ws_file, None)):
            dest = os.path.join(tmp, "%s.casetype.json" % label)
            proc = run(os.path.join(_REPO, _SAVE_HOST), mesh,
                       "--name", "From a %s" % label, "--out", dest,
                       "--advice-from", advice_file,
                       "--reference-id", "demo", "--measured-on", "2026-09-30",
                       "--fields-from", source)
            if proc.returncode != 0:
                out.append("%s --fields-from %s exited %d: %s"
                           % (_SAVE_HOST, source, proc.returncode, proc.stderr))
                continue
            saved = ct.load(dest)
            written[label] = (dest, saved)
            if not saved.fields:
                out.append("capturing from the %s recorded no field at all"
                           % label)
            if expect is not None and dict(saved.fields.values) != expect:
                out.append("capturing from the %s recorded %s, not %s"
                           % (label, dict(saved.fields.values), expect))
            for name in saved.fields.names:
                if name not in proc.stdout:
                    out.append("%s did not print the owned field %s"
                               % (_SAVE_HOST, name))
        if len(written) != 3:
            return out

        show = show_host or os.path.join(_REPO, _SHOW_HOST)
        dat_path, dat_case = written["dat"]
        # (a) WHICH FIELDS DOES IT OWN — user story 24.
        proc = run(show, dat_path)
        if proc.returncode != 0:
            out.append("%s exited %d: %s" % (_SHOW_HOST, proc.returncode,
                                             proc.stderr))
        for name in dat_case.fields.names:
            if name not in proc.stdout:
                out.append("%s did not name the owned field %s: %r"
                           % (_SHOW_HOST, name, proc.stdout))
        if "median" not in proc.stdout:
            out.append("%s stopped printing the thresholds" % _SHOW_HOST)
        # (b) WHAT DIFFERS BETWEEN TWO — user story 37.
        ws_path, ws_case = written["workspace"]
        proc = run(show, dat_path, "--against", ws_path)
        if proc.returncode != 0:
            out.append("%s --against exited %d: %s"
                       % (_SHOW_HOST, proc.returncode, proc.stderr))
        differing = {d.name for d in
                     w.fields.diff(dat_case.fields, ws_case.fields)}
        if not differing:
            out.append("the two captured case types differ in nothing, so this "
                       "leg is measuring nothing")
        for name in differing:
            if name not in proc.stdout:
                out.append("%s --against did not name %s" % (_SHOW_HOST, name))
        # (c) HAVE I MOVED ANYTHING — the same comparison the verdict marks.
        moved_dat = os.path.join(tmp, "moved.dat")
        config = w.fields.read_config(os.path.join(_REPO, _OGRID_DAT))
        config.bl_initial_thickness = 0.004
        config.save_to_file(moved_dat)
        proc = run(show, dat_path, "--config", moved_dat)
        if proc.returncode != 0:
            out.append("%s --config exited %d: %s"
                       % (_SHOW_HOST, proc.returncode, proc.stderr))
        if "bl_initial_thickness" not in proc.stdout.split("Deviation")[-1]:
            out.append("%s --config did not report the moved field: %r"
                       % (_SHOW_HOST, proc.stdout))
        if "mesh_mode" in proc.stdout.split("Deviation")[-1]:
            out.append("%s --config reported a field that did not move"
                       % _SHOW_HOST)
    return out


def check_runner_judges_what_the_operator_wrote(w, source=""):
    """The headless host judges a config its OWN stage did not overwrite.

    `_run_mesh` forces `export_vtk` (and `export_starcd`) on, because the
    pipeline needs the files; both are ownable fields. Handing the verdict THAT
    object makes a case type owning `export_starcd` report a deviation on every
    headless run — a field the operator never touched and cannot put back.

    Read from the SOURCE, like `test_case_type_verdict.py`'s "neither host
    grades" check, because running this leg for real needs the mesher binary and
    the defect is structural: the object passed is one the function wrote to.
    The blind spot that technique carries is named in the docstring above.
    """
    out = []
    src = source or _read(_RUNNER)
    tree = ast.parse(src)
    func = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_run_mesh"),
                None)
    if func is None:
        return ["services/pipeline_runner.py declares no _run_mesh, so this "
                "check is measuring nothing"]
    # Every local name this function writes an ATTRIBUTE of — `mc.export_vtk`
    # and friends. A name in here is a config the stage has edited.
    written = set()
    for node in ast.walk(func):
        if not isinstance(node, (ast.Assign, ast.AugAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value,
                                                               ast.Name):
                written.add(target.value.id)
    calls = [n for n in ast.walk(func)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "run_report"]
    if len(calls) != 1:
        return ["_run_mesh makes %d run_report call(s), expected exactly one"
                % len(calls)]
    passed = [kw.value for kw in calls[0].keywords if kw.arg == "config"]
    if not passed:
        out.append("_run_mesh passes no `config=` to run_report, so no "
                   "deviation can ever be reported headlessly")
    elif not isinstance(passed[0], ast.Name):
        out.append("_run_mesh passes a `config=` this check cannot resolve to a "
                   "name; re-read it by hand")
    elif passed[0].id in written:
        out.append("_run_mesh judges `%s`, which it writes attributes of (%s) — "
                   "this stage's own overrides would be reported as the "
                   "operator's deviations"
                   % (passed[0].id, ", ".join(sorted(written))))
    if not written:
        out.append("_run_mesh writes no config attribute at all, so this check "
                   "is measuring nothing")
    return out


def check_qt_free(w):
    """The overlay service imports no Qt, measured where the answer is honest.

    A subprocess, because in-process the answer is always "PyQt6 is loaded" once
    any other test imported it — the same reason `test_qt_free_seam.py` forks.
    """
    code = ("import sys; sys.path.insert(0, %r);\n"
            "from app.services import case_type_fields;\n"
            "print('PyQt6' in sys.modules)" % _GUI)
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=_REPO)
    if proc.returncode != 0:
        return ["importing the fields service standalone failed: %s"
                % proc.stderr]
    if proc.stdout.strip() != "False":
        return ["importing the fields service loaded PyQt6"]
    return []


def _write_sidecar(mesh_path, metric="quad_midline_ratio"):
    base = os.path.splitext(mesh_path)[0]
    doc = {"tool": "HybMesh2D", "mesh": {"nodes": 1, "elements": 1, "quality": {
        "metric": metric, "cells": OGRID["cells"], "median": OGRID["median"],
        "p95": OGRID["p95"], "max": OGRID["maximum"],
        "layer": {"cells": OGRID_LAYER["cells"], "median": OGRID_LAYER["median"],
                  "p95": OGRID_LAYER["p95"], "max": OGRID_LAYER["maximum"]},
        "bulk": {"cells": OGRID_BULK["cells"], "median": OGRID_BULK["median"],
                 "p95": OGRID_BULK["p95"], "max": OGRID_BULK["maximum"]}}}}
    with open(base + ".provenance.json", "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


# --- run ----------------------------------------------------------------------
_ALL = {
    1: check_capture_is_sparse,
    2: check_round_trip_preserves_the_set,
    3: check_apply_leaves_the_rest_at_default,
    4: check_a_new_mesher_field_changes_nothing,
    5: check_deviation_names_owned_fields_only,
    6: check_deviated_verdict_is_issued_and_marked,
    7: check_deviation_costs_standing_only,
    8: check_unownable_fields_are_refused,
    9: check_the_hosts_answer,
    10: check_qt_free,
    11: check_runner_judges_what_the_operator_wrote,
}

_LABELS = {
    1: "check 1. the capture is a SUBTRACTION: only the fields the case moved",
    2: "check 2. a round trip preserves exactly that set, and no section when empty",
    3: "check 3. applying sets those fields and leaves every other at its default",
    4: "check 4. a mesher field no case type mentions invalidates nothing",
    5: "check 5. deviation names the owned fields that moved, and only those",
    6: "check 6. a deviated verdict is still issued, marked, and names the fields",
    7: "check 7. deviation costs STANDING — one notch of grade, no state change",
    8: "check 8. a field a case type may not own is refused, and says why",
    9: "check 9. the two headless hosts answer all three questions",
    10: "check 10. the fields service is Qt-free, measured in a subprocess",
    11: "check 11. the headless host judges the config the OPERATOR wrote",
}

_REAL = world()

for num in sorted(_ALL):
    fails = _ALL[num](_REAL)
    check(not fails, _LABELS[num])
    for f in fails:
        print("      " + f.replace("\n", "\n      "), flush=True)


# --- injections ---------------------------------------------------------------
# Checks 9 and 10 launch a SUBPROCESS against the real files on disk, and check
# 11 reads a source file off it; none can see an in-memory mutant at all, so
# including them in `others_green` would score them as evidence when they are
# measuring something else. Each carries its own injection instead.
_SKIP_UNDER_MUTATION = (9, 10, 11)


def others_green(w, *reddened):
    """True when every check BUT the named ones still passes on the mutant."""
    return not any(fn(w) for num, fn in _ALL.items()
                   if num not in reddened and num not in _SKIP_UNDER_MUTATION)


def mutate(which, old, new, count=1):
    name = "app.services." + which
    src = _SRC[name]
    assert old in src, "injection anchor not found in %s: %r" % (which, old)
    mutated = src.replace(old, new, count)
    assert mutated != src
    return world(**{which: mutated})


inj = mutate("case_type_fields",
             '''    return (name.startswith(TOPOLOGY_PREFIX)
            and name.endswith(BINDING_SUFFIXES))''',
             "    return False")
check("topology.ogrid_body_segs" in inj.fields.ownable_names(),
      "injection A. injection is well-formed: a binding is now an ownable field")
check(check_unownable_fields_are_refused(inj) and others_green(inj, 8),
      "injection A. check 8 ALONE fails when a case type may own a BINDING — a "
      "stable segment id into the maintainer's geometry, which the operator's "
      "drawing does not have")

inj = mutate("case_type_fields", 'DAT_PRECISION = "%.6g"',
             'DAT_PRECISION = "%.17g"')
check(inj.fields.DAT_PRECISION == "%.17g",
      "injection B. injection is well-formed: two floats must now be bit-equal")
check(check_deviation_names_owned_fields_only(inj) and others_green(inj, 5),
      "injection B. check 5 ALONE fails at the ROUNDED end — the writer formats "
      "at %.6g, so an operator who changed nothing and saved their config would "
      "be told they had moved a field")

inj = mutate("case_type_fields", 'DAT_PRECISION = "%.6g"',
             'DAT_PRECISION = "%.2g"')
check(inj.fields.same(0.001, 0.0010008),
      "injection B2. injection is well-formed: a real edit to a first-cell "
      "height now reads as the same value")
check(check_deviation_names_owned_fields_only(inj) and others_green(inj, 5),
      "injection B2. check 5 ALONE fails at the COARSE end too, which is what "
      "makes the constant the WRITER'S OWN FORMAT rather than a tolerance "
      "beside it: the first version floored a relative tolerance at 1.0, and "
      "0.001 -> 0.0010008 read as no deviation at all")

inj = mutate("case_type_fields",
             '''    names = [n for n in ownable_names()
             if not same(_get(config, n), _get(default, n))]''',
             "    names = list(ownable_names())")
check(len(inj.fields.capture_differences(MeshConfig())) == len(
          inj.fields.ownable_names()),
      "injection C. injection is well-formed: capture is now a full snapshot")
check(check_capture_is_sparse(inj) and others_green(inj, 1),
      "injection C. check 1 ALONE fails when the capture stops subtracting the "
      "default — a case type that records all 74 fields goes stale the day a "
      "75th is added, which is the design this ticket exists against")

inj = mutate("case_type_verdict",
             "                   checked=len(reasons), deviations=deviations)",
             "                   checked=len(reasons))")
check(check_deviated_verdict_is_issued_and_marked(inj) and others_green(inj, 6),
      "injection D. check 6 ALONE fails when `judge` stops carrying the "
      "deviations the host worked out — the mark and the names go with them, "
      "and the operator is told their mesh passed thresholds measured on "
      "settings they have since changed. Check 7 does NOT move and is not "
      "claimed to: it builds its verdicts directly, which is what makes it a "
      "statement about the GRADE rather than about this plumbing")

inj = mutate("case_type_verdict", 'DEVIATED_FLOOR = "WARNING"',
             'DEVIATED_FLOOR = "INFO"')
check(check_deviation_costs_standing_only(inj) and others_green(inj, 7),
      "injection E. check 7 ALONE fails when a deviated pass is logged at the "
      "same grade as an undeviated one: the caveat is printed and nothing makes "
      "an unattended log raise its voice")

inj = mutate("case_type", '''        if self.fields:''', "        if False:")
check("fields" not in inj.case_type.CaseType(
          "n", "m", fields={"mesh_mode": 1}).to_dict(),
      "injection F. injection is well-formed: a written case type no longer "
      "carries its overlay")
check(check_round_trip_preserves_the_set(inj) and others_green(inj, 2),
      "injection F. check 2 ALONE fails when a case type cannot write its own "
      "overlay down — every opinion survives in memory and none of it reaches "
      "the file anybody else would read")

inj = mutate("case_type_fields",
             '''    if name.startswith(TOPOLOGY_PREFIX):
        setattr(config.topology, name[len(TOPOLOGY_PREFIX):], value)
    else:
        setattr(config, name, value)''',
             "    setattr(config, name.replace(TOPOLOGY_PREFIX, ''), value)")
check(check_apply_leaves_the_rest_at_default(inj)
      and check_deviation_names_owned_fields_only(inj)
      and others_green(inj, 3, 5),
      "injection G. checks 3 and 5 fail when a topology parameter is written "
      "onto the mesh config as a flat attribute nothing reads — the family and "
      "its parameters are half of what a case type carries")

# H reaches the one file the in-memory mutants cannot: the inspecting HOST,
# which runs as a subprocess. Without it check 9 — the acceptance criterion that
# the operator can SEE which fields a case type owns — would be the only check
# here never shown able to go red.
_show_src = _read(_SHOW_HOST)
_anchor = '''        for line in case_type.fields.describe():
            print("    " + line)'''
assert _anchor in _show_src, "host injection anchor not found: %r" % _anchor
with tempfile.TemporaryDirectory() as _tmp:
    _mutant = os.path.join(_tmp, "show_case_type_mutant.py")
    with open(_mutant, "w", encoding="utf-8") as _fh:
        _fh.write(_show_src.replace(_anchor, "        pass", 1))
    check(check_the_hosts_answer(_REAL, show_host=_mutant),
          "injection H. check 9 fails when the inspecting HOST stops printing "
          "the fields a case type owns — the one check here an in-memory mutant "
          "cannot reach, now shown able to go red")
    check(not check_the_hosts_answer(_REAL),
          "injection H. ...and the UNmutated host still passes it, so the "
          "failure above is the mutation and not the copy or its PYTHONPATH")

# J reaches the headless HOST, which check 11 reads off disk. It is the other
# half of H: the two checks an in-memory mutant cannot touch each carry their
# own, so no acceptance criterion here rests on a check never shown able to fail.
_runner_src = _read(_RUNNER)
_runner_anchor = "run_report(vtk, rc, config=judged)"
assert _runner_anchor in _runner_src, ("runner injection anchor not found: %r"
                                       % _runner_anchor)
check(check_runner_judges_what_the_operator_wrote(
          _REAL, source=_runner_src.replace(
              _runner_anchor, "run_report(vtk, rc, config=mc)", 1)),
      "injection J. check 11 fails when the headless host judges the config its "
      "OWN stage forced `export_vtk` on — a case type owning an export flag "
      "would be reported DEVIATED on every run, naming a field the operator "
      "never touched")
check(not check_runner_judges_what_the_operator_wrote(_REAL),
      "injection J. ...and the UNmutated runner still passes it, so the failure "
      "above is the mutation and not the reader")

check(not any(fn(_REAL) for num, fn in _ALL.items()),
      "injection I. negative control: the unmutated services pass every check, "
      "so the failures above are the mutations and not the checker")


print("\n%s: %d check(s) failed" % (os.path.basename(__file__), len(_FAILS))
      if _FAILS else "\nAll checks passed.", flush=True)
sys.exit(1 if _FAILS else 0)
