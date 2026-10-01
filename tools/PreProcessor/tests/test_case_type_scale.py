#!/usr/bin/env python3
"""ONE CASE TYPE FITS A GEOMETRY AT ANY SCALE (issue #163, parent #158).

#162 gave a case type the config fields that produced its reference mesh, and
#162's own gate named what it could not do: "NOTHING HERE SCALES ANYTHING. A case
type applied to a geometry at another scale produces the same numbers." That is
this ticket, and the whole of it turns on a distinction a single number cannot
carry — which of a case type's lengths belong to the SIZE of the body and which
belong to the FLOW over it.

WHY THE RULER IS DERIVED AND NOT TYPED. A case type names a ROLE and a MEASURE,
and the characteristic length is read off the role-bearing geometries of whatever
drawing it meets — the maintainer's at authoring, the operator's at application.
The same reason #161 measures a threshold off a reference mesh rather than asking
for a number: a figure somebody typed is a figure nobody can trace, and a
maintainer who has to type their own chord will type the one they remember.

WHY A PHYSICAL PARAMETER IS CONFIRMED RATHER THAN APPLIED. The boundary-layer
first cell height is fixed by the Reynolds number and the target y+. Scaling it
with the body would claim that smaller aerofoils have thinner boundary layers;
carrying it silently would hand the operator somebody else's flow conditions
wearing their own geometry. So it is carried unscaled AND refused until the
operator answers for it, and the refusal lives in the service rather than in a
dialog — a prompt can be skipped by a second host, a raise cannot.

What this pins down:

  1. THE RULER IS DERIVED, NEVER TYPED. Each of the four measures is read off a
     real geometry file, with its centre, and the authoring HOST records what it
     measured rather than anything a flag supplied.
  2. GEOMETRY-DRIVEN SIZES SCALE, AND A COORDINATE IS NOT A SIZE. At 100x every
     SIZE field is multiplied and every X/Y field is mapped AFFINELY about the
     role-bearing geometry's own centre — asserted over an overlay carrying all
     four length kinds plus four fields that are not lengths at all, which must
     not move.
  3. A PHYSICAL PARAMETER DOES NOT SCALE. Asserted over every field
     `LENGTH_KIND` marks `PHYSICAL`, not over one name, and at a changed scale
     rather than at 1:1 where every rule agrees.
  4. CONFIRMATION IS STRUCTURAL. `apply` RAISES while any physical parameter is
     unanswered and names it; the offered value confirms; the operator's own
     value wins over the offered one; confirming a field the case type does not
     own is refused.
  5. A RULER THAT CANNOT BE READ REFUSES. No geometry bearing the role, a
     geometry file that will not load, a role-bearing set with no extent, an
     unknown role or measure, a recorded length of zero — six refusals, each
     naming what is wrong in the operator's terms rather than falling back to
     the whole drawing or to 1:1.
  6. THE LENGTH-UNIT SYSTEM IS USED, NOT DUPLICATED. The three `length_unit*`
     fields are not ownable and the refusal says why; a physical parameter
     carried to a drawing in another unit keeps its value IN METRES; a geometric
     size does NOT convert, the factor being a ratio of two lengths each in its
     own project's units.
  7. EVERY LENGTH IS CLASSIFIED, both directions. `LENGTH_KIND`'s keys are
     exactly the `sci` fields the field-spec tables declare, so a new length
     cannot ship unclassified and default to "scale it".
  8. A v4 DOCUMENT ROUND-TRIPS AND A v3 ONE STILL LOADS, carrying no ruler and
     fitting every drawing at 1:1 — which is the behaviour it has always had.
  9. DEVIATION IS MEASURED AGAINST THE FITTED NUMBERS. A run of the fitted
     config deviates on nothing; comparing against the AUTHORED numbers would
     mark every geometric field of every rescaled run.
 10. THE HOSTS REALLY ANSWER, driven as SUBPROCESSES: `save_case_type.py
     --characteristic` records a measured ruler, `apply_case_type.py` refuses
     with exit 1 and names the unconfirmed parameter, and with `--confirm`
     writes a `.dat` holding the fitted numbers.
 11. QT-FREE, in a subprocess.
 12. END TO END THROUGH THE REAL BINARY: the same case type meshed at 1x and at
     100x, plus a CONTROL run that scales the physical parameter too. The
     control's published figures match the 1x run's to within 1% — a
     geometrically similar mesh — while the correctly fitted run's differ by
     more than 10x, because its boundary layer stayed at its absolute height
     while the body grew. That control is what makes check 12 falsifiable
     without an injection: an implementation that scaled the first cell height
     would make the fitted run match the 1x one and the check would fail.

Known blind spots, named rather than papered over:
  - A ROLE IS PER GEOMETRY HERE, NOT PER SEGMENT. #163's acceptance says "the
    role-bearing segments"; what exists today is `MeshConfig.geom_roles`, keyed
    by geometry FILE, and that is what the ruler is read from. The measure is a
    pure function of a point set either way, so a per-segment assignment narrows
    which points are handed in and changes nothing here — but it does not exist
    yet. The panel that lets an operator assign a role, and deriving a BINDING
    from one, are both #164's.
  - NOTHING JUDGES WHETHER THE DECLARED RULER IS THE RIGHT CURVE. A case type
    naming `body` on a drawing whose far field also bears that role measures the
    far field, consistently at both ends. The refusal is for a role NOBODY
    bears, not for one borne by something the maintainer did not mean.
  - THE CLASSIFICATION IS A JUDGEMENT. That `bl_initial_thickness` is physical
    and `surface_mesh_size` is not is argued in the service's docstring and
    pinned here; what check 7 measures is that every length HAS a judgement, not
    that each one is right.
  - NO GUI. There is no picker and no Trial — #166 — so "the operator is asked
    to confirm" is measured at the service and at the headless host.
  - CHECK 12 MEASURES THE MESHER'S PUBLISHED FIGURES, not the first cell height
    itself: the hybrid path's sidecar does not publish one. The figures move for
    the right reason, and the control run is what shows the movement is this
    parameter's.

INJECTIONS — AUTOMATED, by exec'ing a mutated copy of the service sources and
re-running the same check functions against the mutant. Each asserts the
mutation is well-formed and really differs, then that the named check fails AND
that no other check moves (`others_green`):

  A. `Scale.size` stops multiplying -> check 2 fails: a case type authored on a
     1 m body hands a 100 m one the same 0.02 surface size.
  B. `bl_initial_thickness` is reclassified `SIZE` -> check 3 fails. THE
     injection this ticket asks for by name: a physical parameter scaled with
     the body is the claim that a bigger aerofoil has a thicker boundary layer.
  C. `Application.apply` drops the unconfirmed guard -> check 4 fails: somebody
     else's Reynolds number applied silently.
  D. `measure_role` falls back to the whole drawing when no geometry bears the
     role -> check 5 fails: a guessed ruler meshes something that looks right
     and is the wrong size.
  E. `Scale.physical` drops the unit ratio -> check 6 fails: a first cell height
     authored in metres carried literally into a millimetre drawing is the 1000x
     error this repo has already lost a run to.
  F. `LENGTH_KIND` loses an entry -> check 7 fails: a length nobody classified
     is a length nobody scales.
  G. `Scale.coord` multiplies instead of mapping about the centre -> check 2
     fails: a far-field box correct only for a body at the origin.
  H. `fitted_fields` compares against the AUTHORED overlay -> check 9 fails:
     every geometric field of every rescaled run reported as deviated.
  I. the apply HOST -- a subprocess, so no in-memory mutant reaches it -- stops
     asking the service to apply and writes the plan directly, and check 10
     fails.
  J. negative control: the unmutated services pass every check.

Run:  python3 tools/PreProcessor/tests/test_case_type_scale.py
Needs no Qt and no network. Check 12 self-skips without ./build/HybMesh2D.
"""
import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

from mesher_bin import mesher_env  # noqa: E402

_SAVE_HOST = os.path.join(_REPO, "tools", "PreProcessor", "save_case_type.py")
_SHOW_HOST = os.path.join(_REPO, "tools", "PreProcessor", "show_case_type.py")
_APPLY_HOST = os.path.join(_REPO, "tools", "PreProcessor", "apply_case_type.py")
_MESHER = os.path.join(_REPO, "build", "HybMesh2D")
_NACA = os.path.join(_REPO, "examples", "geometries", "naca0012.dat")

#: name -> repo-relative source, in DEPENDENCY order.
_RELS = [
    ("app.services.case_type_reference",
     "tools/PreProcessor/gui/app/services/case_type_reference.py"),
    ("app.services.case_type_fields",
     "tools/PreProcessor/gui/app/services/case_type_fields.py"),
    ("app.services.case_type_scale",
     "tools/PreProcessor/gui/app/services/case_type_scale.py"),
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
# The same harness `test_case_type_fields.py` uses, and for the same reason: a
# mutant left only in `sys.modules` is shadowed by the PACKAGE attribute that
# `from app.services import x` resolves through first (#160), so both are set.
def _exec_module(name, rel, source):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = os.path.join(_REPO, rel)
    sys.modules[name] = mod
    pkg = sys.modules.get("app.services")
    if pkg is not None:
        setattr(pkg, name.rsplit(".", 1)[1], mod)
    exec(compile(source, mod.__file__, "exec"), mod.__dict__)
    return mod


class World:
    def __init__(self, built):
        self.fields = built["case_type_fields"]
        self.scale = built["case_type_scale"]
        self.case_type = built["case_type"]
        self.verdict = built["case_type_verdict"]


def world(**mutated):
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

#: The authoring drawing: a 2 x 1 box with its centre at the origin, so each of
#: the four measures has a different answer and a mistake between them cannot
#: hide. extent 2, x_extent 2, y_extent 1, diagonal sqrt(5).
BOX = [(-1.0, -0.5), (1.0, -0.5), (1.0, 0.5), (-1.0, 0.5), (-1.0, -0.5)]

#: The operator's drawing: the same box at 100x, centred on (500, 300). The
#: offset is what separates a SIZE from a COORDINATE — scaling a domain bound
#: about the origin gets the right answer only when the body sits there.
FACTOR, CENTRE = 100.0, (500.0, 300.0)

#: An overlay carrying all FOUR length kinds and four fields that are not
#: lengths at all. The non-lengths are the control: whatever scaling does, it
#: must not touch a growth rate, a layer count, a BC name or an export flag.
AUTHORED = {
    "domain_x_min": -12.0, "domain_x_max": 20.0,
    "domain_y_min": -12.0, "domain_y_max": 12.0,
    "surface_mesh_size": 0.02, "farfield_mesh_size": 1.5,
    "bl_initial_thickness": 2.0e-4,
    "bl_growth_rate": 1.1, "bl_layers": 5,
    "bc_geom": "wall", "export_vtk": True,
}
NOT_LENGTHS = ("bl_growth_rate", "bl_layers", "bc_geom", "export_vtk")


def write_box(path, scale=1.0, centre=(0.0, 0.0)):
    with open(path, "w", encoding="utf-8") as fh:
        for x, y in BOX:
            fh.write("%.10f %.10f\n" % (centre[0] + x * scale,
                                        centre[1] + y * scale))
    return path


def drawing(paths, roles=None, unit="m", unit_metres=1.0):
    """A `MeshConfig` holding a geometry list and the roles on it."""
    cfg = MeshConfig()
    cfg.geom_files = list(paths)
    cfg.geom_roles = dict(roles or {})
    cfg.length_unit, cfg.length_unit_metres = unit, unit_metres
    return cfg


def case(w, fields=None, ruler=True, name="demo", **kw):
    """A case type whose ruler was MEASURED on the authoring box."""
    characteristic = None
    if ruler:
        tmp = kw.pop("author_config", None)
        characteristic = w.scale.CharacteristicLength.derive(
            tmp, kw.pop("role", "body"), kw.pop("measure", "extent"))
    return w.case_type.CaseType(name, "tri_edge_ratio",
                                fields=dict(AUTHORED if fields is None
                                            else fields),
                                characteristic=characteristic)


def confirm_all(app):
    """Every physical parameter answered with the value it offers.

    A helper rather than a literal, so a check that is not ABOUT the
    classification keeps working when an injection moves a field out of it —
    otherwise every injection would redden every check by raising.
    """
    return {c.name: c.offered for c in app.confirmations}


def _fitted(w, tmp, op_unit="m", op_metres=1.0, fields=None):
    """`(case type, operator drawing, application)` for the standard pair."""
    author = drawing([write_box(os.path.join(tmp, "author.dat"))])
    op = drawing([write_box(os.path.join(tmp, "op.dat"), FACTOR, CENTRE)],
                 unit=op_unit, unit_metres=op_metres)
    ct = case(w, fields=fields, author_config=author)
    return ct, op, w.scale.plan(ct, op)


# ── 1. the ruler is derived, never typed ───────────────────────────────────
def check_ruler_is_derived(w, save_host=_SAVE_HOST):
    bad = []
    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        author = drawing([write_box(os.path.join(tmp, "author.dat"))])
        want = {"extent": 2.0, "x_extent": 2.0, "y_extent": 1.0,
                "diagonal": math.sqrt(5.0)}
        for measure, value in want.items():
            cl = w.scale.CharacteristicLength.derive(author, "body", measure)
            if abs(cl.value - value) > 1e-9:
                bad.append("measure %s read %r off the box, expected %r"
                           % (measure, cl.value, value))
            if max(abs(c) for c in cl.centre) > 1e-9:
                bad.append("measure %s put the box's centre at %r, not (0, 0)"
                           % (measure, cl.centre))
        # The OPERATOR's box, 100x and off the origin: both halves of the ruler
        # must follow the drawing, or the affine map below has nothing to map
        # about.
        op = drawing([write_box(os.path.join(tmp, "op.dat"), FACTOR, CENTRE)])
        cl = w.scale.CharacteristicLength.derive(op, "body", "extent")
        if abs(cl.value - 2.0 * FACTOR) > 1e-6 or cl.centre != CENTRE:
            bad.append("the operator's box measured %r centred %r, expected "
                       "%r centred %r" % (cl.value, cl.centre,
                                          2.0 * FACTOR, CENTRE))
        # And the authoring HOST records what it measured, with no flag able to
        # supply a number: there is deliberately no --characteristic-value.
        cfg = MeshConfig()
        cfg.geom_files = [os.path.join(tmp, "author.dat")]
        cfg.surface_mesh_size = 0.02
        cfg.save_to_file(os.path.join(tmp, "author_case.dat"))
        out = os.path.join(tmp, "ct.json")
        rc = subprocess.run(
            [sys.executable, save_host, _reference_mesh(tmp),
             "--name", "box", "--out", out, "--advice", "max=More points.",
             "--fields-from", os.path.join(tmp, "author_case.dat"),
             "--characteristic", "body.x_extent"],
            capture_output=True, text=True, cwd=_REPO)
        if rc.returncode != 0:
            bad.append("save_case_type.py --characteristic failed: %s"
                       % rc.stderr.strip()[:200])
        else:
            doc = json.load(open(out, encoding="utf-8"))
            cl = doc.get("characteristic_length") or {}
            if (cl.get("role") != "body" or cl.get("measure") != "x_extent"
                    or abs(float(cl.get("value", 0)) - 2.0) > 1e-9):
                bad.append("the authored file records %r, not the x_extent of "
                           "2.0 it measured" % (cl,))
            if "x_extent of the body = 2" not in rc.stdout:
                bad.append("the host did not print what it measured: %r"
                           % rc.stdout[-200:])
    return bad


def _reference_mesh(tmp):
    """A mesh + sidecar the authoring step can measure thresholds from.

    Written rather than meshed: #161 already gates the reading of a sidecar, and
    this check is about the RULER, which comes off the geometry and not off the
    mesh.
    """
    vtk = os.path.join(tmp, "ref.vtk")
    with open(vtk, "w", encoding="utf-8") as fh:
        fh.write("# vtk DataFile Version 3.0\nref\nASCII\n")
    with open(os.path.join(tmp, "ref.provenance.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"mesh": {"quality": {"metric": "tri_edge_ratio",
                                        "cells": 10, "median": 1.1,
                                        "p95": 1.5, "max": 2.0}}}, fh)
    return vtk


# ── 2. sizes scale; a coordinate maps about the centre ─────────────────────
def check_sizes_scale_and_coords_map(w):
    bad = []
    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        ct, op, app = _fitted(w, tmp)
        if abs(app.scale.factor - FACTOR) > 1e-9:
            bad.append("the scale factor came out %r, not %r"
                       % (app.scale.factor, FACTOR))
        fitted = app.apply(op, confirm_all(app))
        for name, authored in AUTHORED.items():
            kind = w.scale.LENGTH_KIND.get(name)
            got = (getattr(fitted, name) if not name.startswith("topology.")
                   else getattr(fitted.topology, name[9:]))
            if kind == w.scale.SIZE:
                want = authored * FACTOR
            elif kind == w.scale.X:
                want = CENTRE[0] + authored * FACTOR
            elif kind == w.scale.Y:
                want = CENTRE[1] + authored * FACTOR
            else:
                want = authored
            if isinstance(want, float):
                ok = abs(got - want) <= 1e-6 * max(abs(want), 1.0)
            else:
                ok = got == want
            if not ok:
                bad.append("%s (%s) came out %r, expected %r"
                           % (name, kind or "not a length", got, want))
        for name in NOT_LENGTHS:
            if w.scale.LENGTH_KIND.get(name) is not None:
                bad.append("%s is classified a length; this check's control "
                           "depends on it not being one" % name)
    return bad


# ── 3. a physical parameter does not scale ─────────────────────────────────
def check_physical_does_not_scale(w):
    bad = []
    physical = [n for n, k in w.scale.LENGTH_KIND.items()
                if k == w.scale.PHYSICAL]
    if not physical:
        return ["no field is classified PHYSICAL, so this check measures "
                "nothing"]
    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        fields = dict(AUTHORED)
        for i, name in enumerate(physical):
            fields[name] = 2.0e-4 * (i + 1)
        ct, op, app = _fitted(w, tmp, fields=fields)
        if abs(app.scale.factor - FACTOR) > 1e-9:
            bad.append("the drawing is not at a changed scale, so a carried "
                       "value and a scaled one would be the same number")
        fitted = app.apply(op, confirm_all(app))
        for name in physical:
            got = getattr(fitted, name)
            if abs(got - fields[name]) > 1e-15:
                bad.append("%s is physical and came out %r at %gx, not the %r "
                           "it was authored at"
                           % (name, got, FACTOR, fields[name]))
    return bad


# ── 4. confirmation is structural ──────────────────────────────────────────
def check_confirmation_is_structural(w):
    bad = []
    err = w.case_type.CaseTypeError
    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        ct, op, app = _fitted(w, tmp)
        names = [c.name for c in app.confirmations]
        if names != ["bl_initial_thickness"]:
            bad.append("the application asks about %r, expected the one "
                       "physical parameter in the overlay" % (names,))
        if not app.confirmations:
            # Returned rather than carried on: a check that RAISES under an
            # injection takes every check below it down with it, and the
            # failure then reads as the harness rather than as the mutation.
            return bad
        try:
            app.apply(op)
            bad.append("applying with nothing confirmed went through — a case "
                       "type's physical parameters applied silently")
        except err as exc:
            if "bl_initial_thickness" not in str(exc):
                bad.append("the refusal does not name the parameter: %s" % exc)
        offered = app.confirmations[0].offered
        got = app.apply(op, {"bl_initial_thickness": offered})
        if got.bl_initial_thickness != offered:
            bad.append("confirming the offered value did not apply it")
        own = app.apply(op, {"bl_initial_thickness": 7.5e-6})
        if own.bl_initial_thickness != 7.5e-6:
            bad.append("the operator's own value did not win over the offered "
                       "one, so confirming is not also adjusting")
        try:
            app.apply(op, {"bl_initial_thickness": offered,
                           "surface_mesh_size": 1.0})
            bad.append("confirming a field the case type does not treat as "
                       "physical was accepted")
        except err:
            pass
    return bad


# ── 5. a ruler that cannot be read refuses ─────────────────────────────────
def check_underivable_ruler_refuses(w):
    bad = []
    err = w.case_type.CaseTypeError

    def refuses(what, fn, *words):
        try:
            fn()
        except err as exc:
            missing = [t for t in words if t not in str(exc)]
            if missing:
                bad.append("%s refused without naming %s: %s"
                           % (what, ", ".join(missing), exc))
            return
        bad.append("%s was NOT refused — a guessed ruler meshes something that "
                   "looks right and is the wrong size" % what)

    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        author = drawing([write_box(os.path.join(tmp, "author.dat"))])
        ct = case(w, author_config=author)
        far = write_box(os.path.join(tmp, "far.dat"), 10.0)
        # (a) nothing bears the role: every geometry here is a far field.
        only_far = drawing([far], {far: {"role": "farfield"}})
        refuses("a drawing whose geometries all bear another role",
                lambda: w.scale.plan(ct, only_far), "body", "farfield")
        # (b) a geometry file that will not load.
        gone = os.path.join(tmp, "not_written.dat")
        refuses("a geometry file that is not there",
                lambda: w.scale.plan(ct, drawing([gone])), gone)
        # (b2) a file that EXISTS and is not a geometry. `np.loadtxt` raises
        # before `load_points_dat` validates anything, and raises a BARE
        # ValueError — this repo's own USER-REPORTED "could not convert string
        # '{' to float64", which a handler naming only `GeometryLoadError`
        # would have let through to a traceback in both hosts.
        notdat = os.path.join(tmp, "project.json")
        with open(notdat, "w", encoding="utf-8") as fh:
            fh.write('{"cads": []}\n')
        refuses("a geometry entry pointing at a JSON project file",
                lambda: w.scale.plan(ct, drawing([notdat])), notdat)
        # (c) a role-bearing set with no extent: one point repeated.
        flat = os.path.join(tmp, "flat.dat")
        with open(flat, "w", encoding="utf-8") as fh:
            fh.write("1.0 2.0\n1.0 2.0\n")
        refuses("a body with no extent",
                lambda: w.scale.plan(ct, drawing([flat])), "extent")
        # (d) and (e): a role and a measure nothing can act on.
        refuses("an unknown role",
                lambda: w.scale.CharacteristicLength.derive(
                    author, "fuselage", "extent"), "fuselage")
        refuses("an unknown measure",
                lambda: w.scale.CharacteristicLength.derive(
                    author, "body", "span"), "span")
        # (f) a DOCUMENT recording a ruler of zero divides every size by it.
        refuses("a recorded length of zero",
                lambda: w.scale.CharacteristicLength.from_dict(
                    {"role": "body", "measure": "extent", "value": 0.0}),
                "0")
    return bad


# ── 6. the length-unit system is used, not duplicated ──────────────────────
def check_unit_system_is_used(w):
    bad = []
    err = w.case_type.CaseTypeError
    for name in ("length_unit", "length_unit_metres", "length_unit_name"):
        if name in w.fields.ownable_names():
            bad.append("%s is ownable; a case type that set it would RELABEL "
                       "the operator's drawing rather than fit it" % name)
        try:
            w.case_type.FieldOverlay({name: 1.0 if "metres" in name else "mm"})
            bad.append("a case type naming %s was accepted" % name)
        except err as exc:
            if "drawing" not in str(exc):
                bad.append("the refusal for %s does not say whose the unit is: "
                           "%s" % (name, exc))
    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        # The SAME case type, authored in metres, applied to a drawing declared
        # in millimetres. Its box is 100x in ITS OWN units, so the geometric
        # factor is still 100 and nothing about it converts.
        ct, op, app = _fitted(w, tmp, op_unit="mm")
        if abs(app.scale.factor - FACTOR) > 1e-9:
            bad.append("the geometric factor converted with the unit (%r); it "
                       "is a ratio of two lengths each in its own project's "
                       "units and must not" % app.scale.factor)
        _, op_m, app_m = _fitted(w, tmp)
        if (app.values["surface_mesh_size"]
                != app_m.values["surface_mesh_size"]):
            bad.append("a geometric size came out differently for a drawing in "
                       "millimetres (%r) and one in metres (%r); the unit "
                       "cancels out of a ratio and must not reach a size"
                       % (app.values["surface_mesh_size"],
                          app_m.values["surface_mesh_size"]))
        if not app.confirmations or not app_m.confirmations:
            bad.append("neither drawing was asked about a physical parameter, "
                       "so the unit carry below measures nothing")
            return bad
        offered = app.confirmations[0].offered
        want_metres = AUTHORED["bl_initial_thickness"] * 1.0
        if abs(offered - want_metres / 1.0e-3) > 1e-12:
            bad.append("the first cell height offered to a millimetre drawing "
                       "is %r; %r m is %r mm, and carrying the number "
                       "literally is the 1000x error"
                       % (offered, want_metres, want_metres / 1.0e-3))
        if abs(app.confirmations[0].metres - want_metres) > 1e-15:
            bad.append("the confirmation reports %r m, not the %r m the case "
                       "type was authored at"
                       % (app.confirmations[0].metres, want_metres))
        # And with the units AGREEING the value is carried literally, which is
        # what "unscaled" means in the ordinary case.
        if app_m.confirmations[0].offered != AUTHORED["bl_initial_thickness"]:
            bad.append("with both drawings in metres the first cell height was "
                       "not carried through literally")
    return bad


# ── 7. every length is classified, both directions ─────────────────────────
def check_every_length_is_classified(w):
    bad = []
    declared = set(w.scale.length_fields())
    classified = set(w.scale.LENGTH_KIND)
    for name in sorted(declared - classified):
        bad.append("%s is a `sci` field — a LENGTH — and LENGTH_KIND does not "
                   "say what kind, so applying a case type would carry it "
                   "through unscaled by accident" % name)
    for name in sorted(classified - declared):
        bad.append("LENGTH_KIND classifies %s, which no field-spec table "
                   "declares a length any more" % name)
    for name, kind in w.scale.LENGTH_KIND.items():
        if kind not in (w.scale.SIZE, w.scale.X, w.scale.Y, w.scale.PHYSICAL):
            bad.append("%s is classified %r, which is not one of the four "
                       "kinds" % (name, kind))
    missing = [n for n, k in w.scale.LENGTH_KIND.items()
               if k == w.scale.PHYSICAL and n not in w.scale.PHYSICAL_WHY]
    for name in missing:
        bad.append("%s is physical and PHYSICAL_WHY gives no reason; "
                   "'confirm this number' with no reason is a dialog people "
                   "learn to dismiss" % name)
    return bad


# ── 8. the document grew; it was not replaced ──────────────────────────────
def check_document_round_trips(w):
    bad = []
    if w.case_type.SCHEMA_VERSION != 4 or 3 not in w.case_type.READABLE_VERSIONS:
        bad.append("the schema is at %r reading %r; #163 WIDENS the document "
                   "rather than replacing it"
                   % (w.case_type.SCHEMA_VERSION, w.case_type.READABLE_VERSIONS))
    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        author = drawing([write_box(os.path.join(tmp, "author.dat"))])
        ct = case(w, author_config=author, measure="x_extent")
        path = os.path.join(tmp, "ct.json")
        w.case_type.save(ct, path)
        back = w.case_type.load(path)
        a, b = ct.characteristic, back.characteristic
        if (b is None or (a.role, a.measure) != (b.role, b.measure)
                or abs(a.value - b.value) > 1e-12
                or tuple(a.centre) != tuple(b.centre)
                or a.unit_metres != b.unit_metres):
            bad.append("the ruler did not survive a round trip: %r -> %r"
                       % (a, b))
        # A v3 document — every case type authored before #163 — still loads,
        # carries no ruler and fits at 1:1.
        doc = back.to_dict()
        doc.pop("characteristic_length")
        doc["version"] = 3
        old = os.path.join(tmp, "v3.json")
        with open(old, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        v3 = w.case_type.load(old)
        if v3.characteristic is not None:
            bad.append("a v3 document came back carrying a ruler")
        op = drawing([write_box(os.path.join(tmp, "op.dat"), FACTOR, CENTRE)])
        app = w.scale.plan(v3, op)
        if app.scale.factor != 1.0:
            bad.append("a case type with no ruler fitted at %r, not 1:1"
                       % app.scale.factor)
        if not app.confirmations:
            bad.append("a case type with no ruler stopped asking about its "
                       "physical parameters; that question is about physics, "
                       "not about scale")
        if "characteristic_length" in w.case_type.CaseType(
                "n", "m", fields={"mesh_mode": 1}).to_dict():
            bad.append("a case type declaring no ruler writes an empty section "
                       "it never had")
    return bad


# ── 9. deviation is measured against the FITTED numbers ────────────────────
def check_deviation_is_against_the_fitted(w):
    bad = []
    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        ct, op, app = _fitted(w, tmp)
        fitted = app.apply(op, confirm_all(app))
        wanted = w.scale.fitted_fields(ct, fitted)
        moved = w.fields.deviations(wanted, fitted)
        if moved:
            bad.append("a run of the FITTED config deviates on %s — the "
                       "operator is told they moved fields the case type's own "
                       "scaling moved"
                       % ", ".join(d.name for d in moved))
        # The authored overlay is what the comparison must NOT use, and this
        # leg says so by measuring it: every geometric field differs at 100x.
        raw = w.fields.deviations(ct.fields, fitted)
        geometric = {n for n, k in w.scale.LENGTH_KIND.items()
                     if k != w.scale.PHYSICAL and n in AUTHORED}
        if {d.name for d in raw} != geometric:
            bad.append("this check's premise is wrong: comparing against the "
                       "authored numbers moved %r, expected every geometric "
                       "field %r" % ({d.name for d in raw}, geometric))
        # And the operator who really moved something is still told so.
        fitted.surface_mesh_size *= 2.0
        moved = w.fields.deviations(w.scale.fitted_fields(ct, fitted), fitted)
        if [d.name for d in moved] != ["surface_mesh_size"]:
            bad.append("a real edit to a fitted config reported %r"
                       % [d.name for d in moved])
    return bad


# ── 10. the hosts really answer ────────────────────────────────────────────
def check_the_hosts_answer(w, apply_host=_APPLY_HOST):
    bad = []
    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        author = drawing([write_box(os.path.join(tmp, "author.dat"))])
        ct = case(w, author_config=author)
        ct_path = os.path.join(tmp, "ct.json")
        w.case_type.save(ct, ct_path)
        op = MeshConfig()
        op.geom_files = [write_box(os.path.join(tmp, "op.dat"), FACTOR, CENTRE)]
        op.save_to_file(os.path.join(tmp, "op_case.dat"))
        op_case = os.path.join(tmp, "op_case.dat")
        out = os.path.join(tmp, "fitted.dat")

        def run(*args):
            return subprocess.run([sys.executable, apply_host, ct_path,
                                   "--to", op_case] + list(args),
                                  capture_output=True, text=True, cwd=_REPO)

        rc = run("--out", out)
        if rc.returncode == 0:
            bad.append("apply_case_type.py applied a case type with its "
                       "physical parameter unconfirmed and exited 0")
        if "bl_initial_thickness" not in rc.stderr:
            bad.append("the host's refusal does not name the parameter: %r"
                       % rc.stderr[-200:])
        if os.path.exists(out):
            bad.append("the host wrote a configuration it had refused to apply")
        rc = run("--out", out, "--confirm", "bl_initial_thickness")
        if rc.returncode != 0:
            bad.append("apply_case_type.py --confirm failed: %s"
                       % rc.stderr.strip()[-200:])
        elif not os.path.exists(out):
            bad.append("apply_case_type.py --confirm wrote nothing")
        else:
            got = MeshConfig()
            got.load_from_file(out)
            if abs(got.surface_mesh_size
                   - AUTHORED["surface_mesh_size"] * FACTOR) > 1e-9:
                bad.append("the written `.dat` holds surface_mesh_size %r, not "
                           "the fitted %r" % (got.surface_mesh_size,
                                              AUTHORED["surface_mesh_size"]
                                              * FACTOR))
            if got.bl_initial_thickness != AUTHORED["bl_initial_thickness"]:
                bad.append("the written `.dat` scaled the first cell height to "
                           "%r" % got.bl_initial_thickness)
        own = os.path.join(tmp, "own.dat")
        run("--confirm", "bl_initial_thickness=7.5e-6", "--out", own)
        if not os.path.exists(own):
            bad.append("--confirm NAME=VALUE wrote nothing")
        else:
            got = MeshConfig()
            got.load_from_file(own)
            if got.bl_initial_thickness != 7.5e-6:
                bad.append("--confirm NAME=VALUE did not carry the operator's "
                           "own value: %r" % got.bl_initial_thickness)
        # And the INSPECTING host says which ruler a case type declares, so an
        # operator can see what their sizes will be measured against.
        rc = subprocess.run([sys.executable, _SHOW_HOST, ct_path],
                            capture_output=True, text=True, cwd=_REPO)
        if "characteristic length" not in rc.stdout:
            bad.append("show_case_type.py does not report the ruler: %r"
                       % rc.stdout[-200:])
    return bad


# ── 11. Qt-free ────────────────────────────────────────────────────────────
_PROBE = (
    "import sys; sys.path.insert(0, %r);"
    "import app.services.case_type_scale as m;"
    "print('PyQt6' in sys.modules)" % _GUI)


def check_qt_free(w):
    rc = subprocess.run([sys.executable, "-c", _PROBE], capture_output=True,
                        text=True, cwd=_REPO)
    if rc.returncode != 0:
        return ["the scale service did not import standalone: %s"
                % rc.stderr.strip()[-300:]]
    if rc.stdout.strip() != "False":
        return ["importing the scale service loaded PyQt6"]
    return []


# ── 12. end to end, through the real binary ────────────────────────────────
def _mesh_figures(tmp, cfg, stem):
    """Run the mesher on `cfg` and return its published quality figures."""
    cfg.output_filename = os.path.join(tmp, stem + ".vtk")
    conf = os.path.join(tmp, stem + ".dat")
    cfg.save_to_file(conf)
    rc = subprocess.run([_MESHER, "-conf", os.path.basename(conf)],
                        capture_output=True, text=True, cwd=tmp,
                        env=mesher_env())
    sidecar = os.path.join(tmp, stem + ".provenance.json")
    if rc.returncode != 0 or not os.path.exists(sidecar):
        return None, "exit %d: %s" % (rc.returncode, rc.stdout[-300:])
    with open(sidecar, encoding="utf-8") as fh:
        return json.load(fh)["mesh"]["quality"], ""


def check_end_to_end(w):
    if not os.path.exists(_MESHER):
        print("      (skipped: ./build/HybMesh2D is not built)", flush=True)
        return []
    bad = []
    import numpy as np
    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        pts = np.loadtxt(_NACA)
        small = os.path.join(tmp, "naca1.dat")
        big = os.path.join(tmp, "naca100.dat")
        np.savetxt(small, pts, fmt="%.10f")
        np.savetxt(big, pts * FACTOR + np.array(CENTRE), fmt="%.10f")

        author = MeshConfig()
        author.geom_files = [small]
        author.auto_surface_size = False
        for name, value in AUTHORED.items():
            setattr(author, name, value)
        author.export_vtk, author.export_starcd = True, False
        base, why = _mesh_figures(tmp, author, "base")
        if base is None:
            return ["the 1x reference run did not mesh (%s)" % why]

        ct = case(w, author_config=drawing([small]), measure="x_extent")
        op = drawing([big])
        op.export_vtk, op.export_starcd = True, False
        op.auto_surface_size = False
        app = w.scale.plan(ct, op)
        fitted = app.apply(op, confirm_all(app))
        got, why = _mesh_figures(tmp, fitted, "fitted")
        if got is None:
            return ["the 100x fitted run did not mesh (%s)" % why]

        # THE CONTROL: the same application with the physical parameter scaled
        # too. That mesh is geometrically SIMILAR to the 1x one, so the mesher
        # publishes the same figures — which is what makes this check able to
        # fail rather than merely able to pass.
        wrong = MeshConfig()
        wrong.load_from_file(os.path.join(tmp, "fitted.dat"))
        wrong.bl_initial_thickness *= FACTOR
        ctrl, why = _mesh_figures(tmp, wrong, "wrong")
        if ctrl is None:
            return ["the control run did not mesh (%s)" % why]

        keys = ("median", "p95")
        for key in keys:
            if abs(ctrl[key] - base[key]) > 1e-2 * abs(base[key]):
                bad.append("the control run's %s is %r against the 1x run's "
                           "%r; scaling the first cell height with the body "
                           "should give a geometrically similar mesh, so this "
                           "check's own premise is broken"
                           % (key, ctrl[key], base[key]))
        if not got["p95"] > 10.0 * base["p95"]:
            bad.append("the fitted run's p95 is %r against the 1x run's %r — "
                       "indistinguishable from the control, which is what a "
                       "SCALED first cell height produces"
                       % (got["p95"], base["p95"]))
        box = _vtk_box(os.path.join(tmp, "fitted.vtk"))
        want = (CENTRE[0] + AUTHORED["domain_x_min"] * FACTOR,
                CENTRE[0] + AUTHORED["domain_x_max"] * FACTOR,
                CENTRE[1] + AUTHORED["domain_y_min"] * FACTOR,
                CENTRE[1] + AUTHORED["domain_y_max"] * FACTOR)
        if max(abs(a - b) for a, b in zip(box, want)) > 1e-3:
            bad.append("the 100x mesh spans %r, not the %r its case type's "
                       "far-field box maps to" % (box, want))
    return bad


def _vtk_box(path):
    """(xmin, xmax, ymin, ymax) of a legacy-VTK mesh's points."""
    import numpy as np
    lines = open(path, encoding="utf-8").read().splitlines()
    i = next(k for k, line in enumerate(lines) if line.startswith("POINTS"))
    n, vals = int(lines[i].split()[1]), []
    for line in lines[i + 1:]:
        vals += [float(x) for x in line.split()]
        if len(vals) >= 3 * n:
            break
    a = np.array(vals[:3 * n]).reshape(-1, 3)
    return (a[:, 0].min(), a[:, 0].max(), a[:, 1].min(), a[:, 1].max())


_ALL = {
    1: check_ruler_is_derived,
    2: check_sizes_scale_and_coords_map,
    3: check_physical_does_not_scale,
    4: check_confirmation_is_structural,
    5: check_underivable_ruler_refuses,
    6: check_unit_system_is_used,
    7: check_every_length_is_classified,
    8: check_document_round_trips,
    9: check_deviation_is_against_the_fitted,
    10: check_the_hosts_answer,
    11: check_qt_free,
    12: check_end_to_end,
}

_LABELS = {
    1: "check 1. the characteristic length is MEASURED off the role-bearing "
       "geometry, never typed — all four measures, and the authoring host",
    2: "check 2. at 100x every SIZE scales and every COORDINATE maps about the "
       "body's own centre, while nothing that is not a length moves",
    3: "check 3. every PHYSICAL parameter is carried through unscaled at a "
       "changed scale",
    4: "check 4. apply REFUSES until each physical parameter is confirmed, and "
       "confirming is also adjusting",
    5: "check 5. a ruler that cannot be read refuses and names what is wrong, "
       "seven ways",
    6: "check 6. the length-unit system is used, not duplicated: the unit is "
       "the drawing's, and a physical parameter keeps its value in metres",
    7: "check 7. every `sci` field is classified, both directions",
    8: "check 8. a v4 document round-trips and a v3 one still loads at 1:1",
    9: "check 9. deviation is measured against the FITTED numbers",
    10: "check 10. the headless hosts answer: authored, refused, applied",
    11: "check 11. the scale service is Qt-free, measured in a subprocess",
    12: "check 12. end to end through the real binary, with a control run that "
        "scales the first cell height",
}

_REAL = world()

for num in sorted(_ALL):
    fails = _ALL[num](_REAL)
    check(not fails, _LABELS[num])
    for f in fails:
        print("      " + f.replace("\n", "\n      "), flush=True)


# --- injections ---------------------------------------------------------------
# Checks 1, 10 and 11 launch SUBPROCESSES against the real files on disk and
# check 12 launches the mesher; none can see an in-memory mutant, so scoring
# them under `others_green` would count them as evidence of something they are
# not measuring. Check 1's in-process half still moves with a mutant, so it is
# named explicitly where it does.
_SKIP_UNDER_MUTATION = (10, 11, 12)


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


inj = mutate("case_type_scale",
             "        return float(value) * self.factor",
             "        return float(value)")
check(inj.scale.Scale(100.0).size(2.0) == 2.0,
      "injection A. injection is well-formed: a SIZE no longer scales")
check(check_sizes_scale_and_coords_map(inj) and others_green(inj, 2, 9),
      "injection A. check 2 fails when a geometry-driven size stops scaling — "
      "a case type authored on a 1 m body hands a 100 m one the same 0.02 "
      "surface size, and meshes it in two cells. Check 9 goes with it, and is "
      "not claimed as independent evidence: its premise is that the authored "
      "and fitted numbers DIFFER at 100x, which they no longer do")

inj = mutate("case_type_scale",
             '    "bl_initial_thickness": PHYSICAL,',
             '    "bl_initial_thickness": SIZE,')
check(inj.scale.LENGTH_KIND["bl_initial_thickness"] == inj.scale.SIZE,
      "injection B. injection is well-formed: the first cell height is now a "
      "geometric size")
check(check_physical_does_not_scale(inj) and others_green(inj, 3, 4, 6, 8),
      "injection B. check 3 fails when a PHYSICAL parameter is scaled with the "
      "body — the claim that a bigger aerofoil has a thicker boundary layer. "
      "Checks 4, 6 and 8 go with it and are NOT claimed as independent "
      "evidence: the confirmation list, the metres carried across a unit "
      "change and the question a rulerless case type still asks are all keyed "
      "off the SAME classification. Check 9 does NOT move, and is not claimed "
      "to: it compares a fitted config against the fitted ground, which agree "
      "whatever the classification says")

inj = mutate("case_type_scale",
             """        missing = self.unconfirmed(confirmed)
        if missing:""",
             """        missing = self.unconfirmed(confirmed)
        if False:""")
check(check_confirmation_is_structural(inj) and others_green(inj, 4),
      "injection C. check 4 ALONE fails when `apply` stops refusing — somebody "
      "else's Reynolds number applied silently, which is the one thing #158's "
      "user story 23 asks for by name")

inj = mutate("case_type_scale",
             "    paths = role_paths(config, role)\n    if not paths:",
             "    paths = role_paths(config, role) or list(config.geom_files)\n"
             "    if not paths:")
check(check_underivable_ruler_refuses(inj) and others_green(inj, 5),
      "injection D. check 5 ALONE fails when a ruler nobody can read falls "
      "back to the whole drawing — a guessed ruler produces a mesh that looks "
      "right and is the wrong size")

inj = mutate("case_type_scale",
             "        return float(value) * self.unit_ratio",
             "        return float(value)")
check(check_unit_system_is_used(inj) and others_green(inj, 6),
      "injection E. check 6 ALONE fails when a physical parameter is carried "
      "into another unit as a bare number — 0.0002 m written into a millimetre "
      "drawing is a first cell a thousand times too thin, the error this repo "
      "has already lost a run to")

inj = mutate("case_type_scale", '    "farfield_mesh_size": SIZE,\n', "")
check("farfield_mesh_size" not in inj.scale.LENGTH_KIND,
      "injection F. injection is well-formed: one length is now unclassified")
check(check_every_length_is_classified(inj) and others_green(inj, 7, 2),
      "injection F. check 7 fails when a `sci` field carries no judgement — it "
      "would be carried through unscaled by accident, which check 2 catches "
      "here only because that field happens to be in this overlay")

inj = mutate("case_type_scale",
             """        return (self.centre[axis]
                + (float(value) - self.ref_centre[axis]) * self.factor)""",
             "        return float(value) * self.factor")
check(check_sizes_scale_and_coords_map(inj) and others_green(inj, 2),
      "injection G. check 2 ALONE fails when a COORDINATE is multiplied "
      "instead of mapped about the body's centre — a far-field box that is "
      "right only for a body drawn at the origin")

inj = mutate("case_type_scale",
             "        return FieldOverlay(plan(case_type, config).values)",
             "        return case_type.fields")
check(check_deviation_is_against_the_fitted(inj) and others_green(inj, 9),
      "injection H. check 9 ALONE fails when deviation is measured against the "
      "AUTHORED numbers — every geometric field of every rescaled run reported "
      "as the operator's own edit")

# I reaches the one file an in-memory mutant cannot: the applying HOST, which
# runs as a subprocess. Without it check 10 — the acceptance criterion that the
# operator is ASKED — would be the only check here never shown able to redden.
_apply_src = _read(os.path.relpath(_APPLY_HOST, _REPO))
_anchor = "        fitted = application.apply(config, confirmed)"
assert _anchor in _apply_src, "host injection anchor not found: %r" % _anchor
with tempfile.TemporaryDirectory() as _tmp:
    _mutant = os.path.join(_tmp, "apply_case_type_mutant.py")
    with open(_mutant, "w", encoding="utf-8") as _fh:
        _fh.write(_apply_src.replace(
            _anchor,
            "        fitted = case_type_fields.apply(\n"
            "            case_type_fields.FieldOverlay(application.values),\n"
            "            config)", 1))
    check(check_the_hosts_answer(_REAL, apply_host=_mutant),
          "injection I. check 10 fails when the applying HOST writes the plan "
          "itself instead of asking the service to apply it — the refusal is "
          "bypassed and the `.dat` lands with nobody having confirmed anything")
    check(not check_the_hosts_answer(_REAL),
          "injection I. ...and the UNmutated host still passes it, so the "
          "failure above is the mutation and not the copy or its PYTHONPATH")

check(not any(fn(_REAL) for num, fn in _ALL.items()),
      "injection J. negative control: the unmutated services pass every check, "
      "so the failures above are the mutations and not the checker")


print("\n%s: %d check(s) failed" % (os.path.basename(__file__), len(_FAILS))
      if _FAILS else "\nAll checks passed.", flush=True)
sys.exit(1 if _FAILS else 0)
