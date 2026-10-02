#!/usr/bin/env python3
"""ROLES BIND A CASE TYPE TO THE OPERATOR'S OWN CAD (issue #164, parent #158).

#162 gave a case type the config fields that produced its reference mesh and
#163 fitted those fields to another drawing's scale. Both stopped at the same
wall, and #163's own gate named it: "AN OVERLAY NAMING A FAMILY CANNOT BE
WRITTEN TO A `.dat` ON ITS OWN", because every family but the H-grid refuses to
build a document with no geometry to bind to. This ticket is that wall.

WHY A BINDING CANNOT SIMPLY BE COPIED. A binding is a stable `SegmentModel.id`
into the MAINTAINER's geometry. The operator's segments have entirely different
ids, so applying a case type is a binding problem from the first moment rather
than an error case — which is why `case_type_fields.EXCLUDED` already rules
every `*_geom` / `*_segs` parameter unownable BY SUFFIX. What travels is the
ROLE, and the binding is DERIVED against the operator's own segments.

WHY A GUESS IS CONFIRMED RATHER THAN USED. A wrong guess that reaches the
mesher silently produces a mesh that generates, exports and looks right while
carrying the far field's conditions on the body — the same failure class that
once exported an entire mesh as `wall`. So the refusal lives in the service,
not in a dialog: a prompt can be skipped by a second host, a raise cannot.

WHY THE GUESS IS GEOMETRIC AND NEVER POSITIONAL. Drawing-order conventions are
excluded by decision in #158, and this repo has a USER-REPORTED defect where
drawing order rather than click order decided a result. Candidates are ranked by
ENCLOSED AREA: the body is inside the seam is inside the far field however they
were drawn.

What this pins down:

  1. WHICH ROLES A FAMILY NEEDS IS DERIVED FROM THE MODEL, and is SHOWN before
     anything is assigned: the O-grid's two, the two-ring's three, the C-grid's
     required one and optional one, the H-grid's none. Each line names the role,
     what it is, and whether it must be answered.
  2. BINDINGS ARE DERIVED FROM ROLES, and NO ID FROM THE AUTHORING GEOMETRY
     SURVIVES. Asserted on a case type that could not carry one even if it tried
     (the suffix exclusion) applied to a drawing whose ids are nothing like the
     authoring ones.
  3. ENTIRELY DIFFERENT IDS BIND CORRECTLY: the derived model builds a real
     topology document whose every corner names one of the OPERATOR's segments.
  4. A PRE-SELECTED ROLE IS CONFIRMED BEFORE USE. `bind` raises while one is
     unanswered and names every one; a bare confirmation takes the guess; and
     the guess does not move when the geometry list is REVERSED, because it
     ranks by enclosed area and not by drawing order. BOTH of its sources are
     driven: the drawing's own `geom_roles` evidence, which survives a count
     the ranking cannot use, and a refinement SEED, which is not an outline a
     topology binds and so must not shift the ranking by one.
  5. AN UNASSIGNED REQUIRED ROLE BLOCKS AND SAYS WHICH. The two-ring family
     without its seam refuses and names `seam`; the C-grid without its OPTIONAL
     far field does not refuse, and leaves that list blank for the family to
     generate from.
  6. RE-RESAMPLING A BOUND GEOMETRY DOES NOT MOVE A BINDING. The binding is
     derived ONCE, the outlines are then rewritten at a different point density
     with the same segment ids, and the binding already HELD still names the
     same places — which is the question, re-deriving at both densities being
     true by construction. What is compared is the corners AND the half-way
     point of every bound segment: every O-grid corner sits at t = 0, so
     corners alone compare a segment's first point, while t = 0.5 is the
     arc-length guarantee itself. A guard fails the check if the resample was
     not picked up, so it cannot pass by comparing one reading twice.
  7. EVERY BROKEN POSITION AT ONCE, not the first: two unresolvable ids on one
     role and one on another are all three named by a single refusal, the way
     `topology_model.broken_bindings` lists every stored one. And the FOUR
     QUESTIONS are asked by their owner — `topology_binding.outline_problem` —
     so a geometry this mesh does not load, one with no sidecar and an OPEN
     polyline are all refused in that helper's words rather than in a fourth
     copy of them.
  8. A ROLE IS PER SEGMENT. A subset of a geometry's segments binds exactly that
     subset, in the GEOMETRY's own order whatever order they were typed in —
     because the ring walks the stored list as written.
  9. THE DECLARATION IS COMPLETE IN BOTH DIRECTIONS. Every binding list of every
     registered family maps to exactly one declared role; every declared slot
     token is used by a family and has a meaning; every optional entry names a
     real family and role.
 10. THE HOST REALLY ANSWERS, driven as a SUBPROCESS: `apply_case_type.py`
     prints the roles before assignment, exits 1 naming the unconfirmed one, and
     with `--role` writes a `.dat` AND the block topology document beside it,
     holding the operator's own ids.
 11. QT-FREE, in a subprocess.
 12. END TO END THROUGH THE REAL BINARY: a case type naming the `ogrid` family,
     applied to a drawing whose segment ids are 17-20 and 31-34, meshes.

Known blind spots, named rather than papered over:
  - THE RULER IS STILL READ OFF WHOLE GEOMETRIES. `case_type_scale.measure_role`
    measures the geometries bearing a `geom_roles` role, which is per FILE; the
    per-SEGMENT role here is what a family BINDS to. A drawing whose body and
    far field are two files measures the same ruler either way, and narrowing
    the ruler to the role-bearing segments is not done here.
  - NOTHING JUDGES WHETHER THE ROLE IS THE RIGHT CURVE. The guess is ranked and
    the operator confirms; a confirmed assignment naming the far field as the
    body binds exactly that, and only the family's own refusal (#165) will
    notice.
  - NO GUI. There is no role panel — #166 owns the picker and the Trial/Generate
    actions — so "the operator assigns and confirms" is measured at the service
    and at the headless host.
  - THE FAMILIES ARE NOT MODIFIED. Their preconditions are #165's; what is
    asserted here is that a derived binding is one they ACCEPT. ONE of their
    preconditions is asked early and deliberately: `_resolve_one` goes through
    `topology_binding.outline_problem`, whose fourth question is "is this a
    closed loop". That is the cascade's owner rather than a fourth copy of it
    (the Standards axis asked for the reuse), and the question comes with the
    helper; it is a generic one — every family that binds binds a ring — and
    does not pre-empt a family's own.
  - CHECKS 2, 3 AND 6 CARRY NO INJECTION, which is stated rather than left to
    be counted. Check 2's property is structural — this module reads no id
    from the case type because a case type carries none, so there is nothing
    to mutate into reading one — and check 3 builds on it. Check 6's subject
    is `topology_binding`'s arc-length resolution, which this ticket does not
    modify; what it shows is that a role-derived binding does not break a
    guarantee that was already there. Checks 10, 11 and 12 carry none either,
    being subprocesses no in-memory mutant reaches, which is why they are
    excluded from `others_green` — except through injection G, which mutates
    the host on disk.

INJECTIONS — AUTOMATED, by exec'ing a mutated copy of the service sources and
re-running the same check functions against the mutant. BOTH files of the seam
are mutable — the roles and the pre-selection split off it at the ~500-line
standard — so an injection does not stop being able to redden a check the day
its subject moves next door. Each asserts the
mutation is well-formed and really differs, then that the named check fails AND
that no other check moves (`others_green`):

  A. `bind` stops refusing an unconfirmed guess -> check 4 fails: somebody
     else's idea of which curve is the body reaches the mesher silently.
  B. `_resolve_one` returns at the FIRST unresolvable id -> check 7 fails: the
     operator repairs their drawing one refusal at a time.
  C. `resolve` stops reporting a missing REQUIRED role -> check 5 fails: the run
     proceeds with a list nobody bound.
  D. `_resolve_one` keeps the TYPED order instead of the geometry's -> check 8
     fails: every wall after the first binds to a different stretch of curve
     with every id still resolving.
  E. `SLOT_ROLE` loses an entry -> check 9 fails, and check 1 with it: a family
     whose slot nobody named has a role nobody can assign.
  F. `guess_roles` ranks by the GEOMETRY LIST's order instead of enclosed area
     -> check 4 fails: the drawing-order convention #158 excluded, reintroduced
     inside the guess.
  G0. the guess stops reading the drawing's OWN `geom_roles` evidence -> check
     4 fails: a curve the operator already called the far field is demoted to
     "the biggest outline", and on a drawing the ranking cannot order it is
     offered nothing.
  G1. a refinement SEED is ranked as an outline -> check 4 fails: every slot
     shifts by one.
  G. the applying HOST -- a subprocess, so no in-memory mutant reaches it --
     writes the guess straight into the model instead of asking the service to
     bind it, and check 10 fails: the confirmation is bypassed by the one caller
     that has to ask.
  H. negative control: the unmutated service passes every check.

Run:  python3 tools/PreProcessor/tests/test_case_type_roles.py
Needs no Qt and no network. Check 12 self-skips without ./build/HybMesh2D.
"""
import importlib.util
import json
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
from topology_outline_fixture import write_outline  # noqa: E402

_APPLY_HOST = os.path.join(_REPO, "tools", "PreProcessor", "apply_case_type.py")
_MESHER = os.path.join(_REPO, "build", "HybMesh2D")
#: name -> repo-relative source, in DEPENDENCY order. Two files since the
#: pre-selection was split off at the ~500-line standard, and the gate mutates
#: either: an injection that could only reach one of them would stop being able
#: to redden a check the day its subject moved next door.
_RELS = [
    ("app.services.case_type_guess",
     "tools/PreProcessor/gui/app/services/case_type_guess.py"),
    ("app.services.case_type_roles",
     "tools/PreProcessor/gui/app/services/case_type_roles.py"),
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


# --- the world: a FRESH copy of the service, optionally mutated ---------------
# A mutant left only in `sys.modules` is shadowed by the PACKAGE attribute that
# `from app.services import x` resolves through first (#160), so both are set —
# the same harness `test_case_type_fields.py` and `test_case_type_scale.py` use.
def world(**mutated):
    """A fresh `case_type_roles`, built over fresh sources, optionally mutated.

    Returns the ROLES module: it re-exports the pre-selection, so a check
    reading `w.RANK` reaches whichever copy this world built.
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
            spec = importlib.util.spec_from_loader(name, loader=None)
            mod = importlib.util.module_from_spec(spec)
            mod.__file__ = os.path.join(_REPO, rel)
            sys.modules[name] = mod
            setattr(pkg, short, mod)
            exec(compile(mutated.get(short, _SRC[name]), mod.__file__, "exec"),
                 mod.__dict__)
            built[short] = mod
        return built["case_type_roles"]
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
from app.services import case_type as case_type_mod  # noqa: E402
from app.services import topology_binding, topology_model  # noqa: E402
from app.services.case_type import CaseTypeError  # noqa: E402

#: The OPERATOR's segment ids. Nothing like 0..3, which is what every geometry
#: this repo ships carries and therefore what an authoring drawing's binding
#: would hold — so an id that leaked from the maintainer's side is visible as
#: itself rather than as a coincidence.
BODY_IDS = (17, 18, 19, 20)
SEAM_IDS = (51, 52, 53, 54)
FAR_IDS = (31, 32, 33, 34)

#: The ids an authoring geometry would carry, asserted ABSENT from everything
#: the derivation writes.
AUTHORING_IDS = (0, 1, 2, 3)


def outlines(tmp, per_seg=40, seam=False, square=True):
    """The operator's drawing: concentric outlines with their own segment ids.

    Square by default, because a square's segment arc length is EXACT under
    resampling, which is what lets check 6 compare positions rather than
    tolerances — `topology_outline_fixture` states the same reason. Check 12
    asks for ROUND ones instead: an O-grid ring between two squares folds at
    this cell size, and a folded mesh is a quality outcome rather than
    anything a binding decides, so meshing one would measure the wrong thing.
    """
    body = write_outline(os.path.join(tmp, "body"), 0.5, list(BODY_IDS),
                         per_seg, "wall", square=square)
    far = write_outline(os.path.join(tmp, "far"), 5.0, list(FAR_IDS),
                        per_seg, "farfield", square=square)
    if not seam:
        return [body, far]
    mid = write_outline(os.path.join(tmp, "seam"), 1.5, list(SEAM_IDS),
                        per_seg, "wall", square=square)
    return [body, mid, far]


def write_open(stem, seg_id=61):
    """An OPEN polyline with its own segment id — a curve no ring can bind.

    `write_outline` always closes its loop, and the four-question cascade's
    last question is about exactly the geometry it cannot build.
    """
    pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
    with open(stem + ".dat", "w", encoding="utf-8") as fh:
        for x, y in pts:
            fh.write("%.12f %.12f\n" % (x, y))
    with open(stem + ".dat.meta", "w", encoding="utf-8") as fh:
        fh.write("HYBMESH_META 2\n")
        fh.write("COUNT %d\n" % len(pts))
        fh.write("NPIECES 0\n")
        fh.write("NSEGMENTS 1\n")
        fh.write("%d wall line\n" % seg_id)
        fh.write("POINTS %d\n" % len(pts))
        for k in range(len(pts)):
            fh.write("%d %d\n" % (seg_id, 1 if k == 0 else 0))
    return stem + ".dat"


def drawing(paths, family="ogrid", roles=None, **params):
    """A `MeshConfig` holding the operator's geometry list and a family."""
    cfg = MeshConfig()
    cfg.set_geom_files(list(paths))
    cfg.geom_roles = dict(roles or {})
    cfg.mesh_mode = 1
    cfg.bl_initial_thickness = 0.001
    cfg.topology.family = family
    for name, value in params.items():
        setattr(cfg.topology, name, value)
    return cfg


def case(family="ogrid", extra=None):
    """A case type that owns a family and its parameters, and nothing else.

    It CANNOT own a binding — `case_type_fields` refuses every `*_geom` /
    `*_segs` by suffix — which is the premise the whole ticket rests on, and is
    gated next door by `test_case_type_fields.py`.
    """
    fields = {"mesh_mode": 1, "bl_initial_thickness": 0.001,
              "export_vtk": True, "topology.family": family}
    fields.update(extra or {})
    return case_type_mod.CaseType("demo", "quad_midline_ratio", fields=fields)


def planned(w, cfg):
    ctx = topology_binding.context_for_config(cfg)
    return ctx, w.plan_roles(cfg, ctx)


def refusal(fn, *a, **kw):
    """The message `fn` refuses with, or `""` when it does not refuse."""
    try:
        fn(*a, **kw)
    except CaseTypeError as exc:
        return str(exc)
    return ""


# ── 1. which roles a family needs, shown before assignment ──────────────────
def check_roles_are_declared(w):
    bad = []
    want = {"ogrid": ("body", "farfield"),
            "cgrid": ("body", "farfield"),
            "tworing": ("body", "seam", "farfield"),
            "hgrid": (),
            "": ()}
    for family, roles in want.items():
        got = tuple(s.role for s in w.slots_for(family))
        if got != roles:
            bad.append("the %r family needs %r and the derivation says %r"
                       % (family or "(none)", roles, got))
    required = {(s.family, s.role): s.required
                for family in want for s in w.slots_for(family)}
    if required.get(("cgrid", "farfield")) is not False:
        bad.append("the C-grid's far field is OPTIONALLY drawn and the "
                   "derivation calls it required")
    for key, is_required in required.items():
        if key != ("cgrid", "farfield") and not is_required:
            bad.append("%s.%s is optional and nothing says why" % key)
    with tempfile.TemporaryDirectory() as tmp:
        cfg = drawing(outlines(tmp, seam=True), family="tworing")
        _ctx, plan = planned(w, cfg)
        shown = "\n".join(plan.describe())
        for role in ("body", "seam", "farfield"):
            if role not in shown:
                bad.append("the roles shown before assignment do not name %r: "
                           "%s" % (role, shown))
        if "required" not in shown:
            bad.append("nothing shown before assignment says a role must be "
                       "answered: %s" % shown)
        cfg = drawing(outlines(tmp), family="cgrid")
        _ctx, plan = planned(w, cfg)
        shown = "\n".join(plan.describe())
        if "optional" not in shown or "GENERATED" not in shown:
            bad.append("the C-grid's optional far field is not shown as "
                       "optional with its reason: %s" % shown)
        cfg = drawing(outlines(tmp), family="hgrid")
        _ctx, plan = planned(w, cfg)
        if plan.slots or "no roles" not in " ".join(plan.describe()):
            bad.append("a family that binds to nothing asks for a role: %s"
                       % plan.describe())
    return bad


# ── 2. derived from roles; no authoring id survives ─────────────────────────
def check_bindings_are_derived(w):
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        cfg = drawing(outlines(tmp))
        ct = case()
        if any(n.endswith(("_geom", "_segs")) for n in ct.fields.names):
            bad.append("the case type carries a binding, which is the premise "
                       "this whole ticket rests on: %r" % (ct.fields.names,))
        _ctx, plan = planned(w, cfg)
        plan.bind(cfg, {"body": "", "farfield": ""})
        got = (cfg.topology.ogrid_body_segs, cfg.topology.ogrid_far_segs)
        if got != ("17, 18, 19, 20", "31, 32, 33, 34"):
            bad.append("the derived bindings are %r, not the operator's own "
                       "segment ids" % (got,))
        if (os.path.basename(cfg.topology.ogrid_body_geom) != "body.dat"
                or os.path.basename(cfg.topology.ogrid_far_geom) != "far.dat"):
            bad.append("the derived geometries are %r / %r, not the operator's"
                       % (cfg.topology.ogrid_body_geom,
                          cfg.topology.ogrid_far_geom))
        written = " ".join(str(v) for v in cfg.topology.to_dict().values())
        for stale in AUTHORING_IDS:
            for field in (cfg.topology.ogrid_body_segs,
                          cfg.topology.ogrid_far_segs):
                if str(stale) in [t.strip() for t in field.split(",")]:
                    bad.append("segment %d — an id from the authoring geometry "
                               "— survived into %r" % (stale, field))
        if "0, 1, 2, 3" in written:
            bad.append("the applied model carries the authoring drawing's own "
                       "binding list: %s" % written)
    return bad


# ── 3. entirely different ids bind correctly ────────────────────────────────
def check_different_ids_bind(w):
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        cfg = drawing(outlines(tmp), ogrid_cell=0.05)
        ctx, plan = planned(w, cfg)
        plan.bind(cfg, {"body": "", "farfield": ""})
        try:
            doc = topology_model.build_document(cfg.topology, ctx)
        except ValueError as exc:
            return ["the derived binding does not build a document: %s" % exc]
        corners = [c for c in doc.get("corners", [])
                   if c.get("kind") == "on_geometry"]
        if not corners:
            bad.append("the document binds no corner to the geometry at all")
        mine = set(BODY_IDS) | set(FAR_IDS)
        for c in corners:
            if c.get("seg") not in mine:
                bad.append("a corner binds segment %r, which is none of the "
                           "operator's %r" % (c.get("seg"), sorted(mine)))
        if len(doc.get("blocks", [])) != 4:
            bad.append("the O-grid built %d block(s) from four bound segments"
                       % len(doc.get("blocks", [])))
    return bad


# ── 4. a pre-selected role is confirmed before use ──────────────────────────
def check_guess_is_confirmed(w):
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        paths = outlines(tmp)
        cfg = drawing(paths)
        _ctx, plan = planned(w, cfg)
        if set(plan.guesses) != {"body", "farfield"}:
            bad.append("the tool pre-selected %r, not both roles"
                       % sorted(plan.guesses))
        why = refusal(plan.bind, cfg, {})
        if not why:
            bad.append("an unconfirmed pre-selection was used without a word")
        for role in ("body", "farfield"):
            if role not in why:
                bad.append("the refusal does not name the unconfirmed %r role: "
                           "%s" % (role, why))
        if cfg.topology.ogrid_body_segs or cfg.topology.ogrid_far_segs:
            bad.append("the refused bind wrote a binding anyway: %r"
                       % cfg.topology.ogrid_body_segs)
        half = refusal(plan.bind, cfg, {"body": ""})
        if "farfield" not in half or "body.dat" in half:
            bad.append("confirming one role did not leave the OTHER as the "
                       "only thing unconfirmed: %s" % half)
        plan.bind(cfg, {"body": "", "farfield": ""})
        if os.path.basename(cfg.topology.ogrid_body_geom) != "body.dat":
            bad.append("a bare confirmation did not take the pre-selection: %r"
                       % cfg.topology.ogrid_body_geom)
        # THE GUESS IS GEOMETRIC, NOT POSITIONAL: reversing the geometry list
        # must not move it. Drawing-order conventions are excluded by decision.
        flipped = drawing(list(reversed(paths)))
        _ctx2, plan2 = planned(w, flipped)
        for role in ("body", "farfield"):
            a = plan.guesses[role].geom if role in plan.guesses else None
            b = plan2.guesses[role].geom if role in plan2.guesses else None
            if a != b:
                bad.append("reversing the geometry list moved the %r guess "
                           "from %r to %r — the drawing-order convention #158 "
                           "excluded" % (role, a, b))
        for g in plan.guesses.values():
            if not g.why.strip():
                bad.append("the %r pre-selection is offered with no reason"
                           % g.role)
        # THE DRAWING'S OWN EVIDENCE IS READ, and it is a different source from
        # the ranking: a geometry this drawing ALREADY calls the far field
        # takes that slot, and it survives a count the RANKING cannot use.
        seam = outlines(tmp, seam=True)
        tagged = drawing(seam, roles={seam[2]: {"role": "farfield"}})
        _ctx3, plan3 = planned(w, tagged)
        far = plan3.guesses.get("farfield")
        if far is None or os.path.basename(far.geom) != "far.dat":
            bad.append("a geometry the drawing already gives the far-field "
                       "role was not pre-selected for it: %r"
                       % sorted(plan3.guesses))
        elif "far-field role" not in far.why:
            bad.append("the evidence-based pre-selection does not say it came "
                       "from the drawing's own role: %s" % far.why)
        if "body" in plan3.guesses:
            bad.append("three outlines and an O-grid's two slots still ranked "
                       "a body: %r" % plan3.guesses["body"].why)
        # ...and a SEED is not an outline a topology binds, so it must not
        # shift the ranking by one.
        seeded = drawing(seam, roles={seam[1]: {"role": "seed"}})
        _ctx4, plan4 = planned(w, seeded)
        for role, want in (("body", "body.dat"), ("farfield", "far.dat")):
            got = plan4.guesses.get(role)
            if got is None or os.path.basename(got.geom) != want:
                bad.append("a refinement seed in the drawing moved the %r "
                           "pre-selection to %r" % (role, got and got.geom))
    return bad


# ── 5. an unassigned required role blocks and says which ────────────────────
def check_missing_required_role_blocks(w):
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        # TWO outlines for a family that needs THREE, so nothing is
        # pre-selected at all (the counts do not line up) and this check is
        # about the MISSING role rather than about an unconfirmed guess —
        # which is check 4's subject and would otherwise refuse first and
        # leave this one measuring that instead.
        paths = outlines(tmp)
        cfg = drawing(paths, family="tworing")
        _ctx, plan = planned(w, cfg)
        if plan.guesses:
            bad.append("a drawing with 2 outlines and 3 roles pre-selected "
                       "%r, so this check is no longer about a MISSING role"
                       % sorted(plan.guesses))
        # Assign the two the operator did think of, and nothing for the seam.
        why = refusal(plan.bind, cfg,
                      {"body": paths[0], "farfield": paths[1]})
        if "seam" not in why:
            bad.append("a two-ring O-grid with no seam assigned does not name "
                       "the missing role: %s" % why)
        if cfg.topology.tworing_body_segs:
            bad.append("the blocked run wrote a binding anyway")
        # ...and the OPTIONAL one does not block.
        cfg2 = drawing(outlines(tmp), family="cgrid")
        _ctx2, plan2 = planned(w, cfg2)
        why2 = refusal(plan2.bind, cfg2, {"body": ""})
        if why2:
            bad.append("the C-grid's OPTIONALLY drawn far field blocked the "
                       "run: %s" % why2)
        if cfg2.topology.cgrid_far_segs or cfg2.topology.cgrid_far_geom:
            bad.append("an unassigned optional role was bound to something "
                       "anyway: %r" % cfg2.topology.cgrid_far_geom)
        if not cfg2.topology.cgrid_body_segs:
            bad.append("the C-grid's required aerofoil did not bind")
    return bad


# ── 6. re-resampling does not move a binding ────────────────────────────────
def check_resampling_does_not_move_a_binding(w):
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        cfg = drawing(outlines(tmp, per_seg=40), ogrid_cell=0.05)
        ctx, plan = planned(w, cfg)
        plan.bind(cfg, {"body": "", "farfield": ""})
        held = (cfg.topology.ogrid_body_segs, cfg.topology.ogrid_far_segs)

        def placed(context):
            """The bound corners, and the MIDPOINT of every bound segment.

            The midpoints are the point: every O-grid corner sits at t = 0, so
            comparing corners alone compares a segment's FIRST POINT, which a
            resample leaves where it was whatever arc length does. t = 0.5 is
            the arc-length guarantee itself — the quantity `pointAtArc`
            computes — measured through a role-derived binding.
            """
            doc = topology_model.build_document(cfg.topology, context)
            at = topology_binding.locator(context)
            corners = {c["id"]: at(c) for c in doc["corners"]
                       if c.get("kind") == "on_geometry"}
            mids = {(os.path.basename(g.path), sid): span.point_at(0.5)
                    for g in context.geoms for sid, span in g.spans.items()}
            return corners, mids

        before, mids_before = placed(ctx)
        # The SAME files, rewritten at a different point density with the same
        # segment ids — a re-resample from the CAD stage. The binding above is
        # NOT re-derived: what is asked is whether the one already held still
        # names the same places.
        outlines(tmp, per_seg=97)
        after_ctx = topology_binding.context_for_config(cfg)
        if (cfg.topology.ogrid_body_segs, cfg.topology.ogrid_far_segs) != held:
            bad.append("the stored binding changed under the resample, which "
                       "nothing but this check touched")
        counts = {len(g.spans[s].points)
                  for g in after_ctx.geoms for s in g.spans}
        if counts == {41}:
            bad.append("the resample was not picked up at all (spans still "
                       "41 points), so this check compares one reading twice")
        after, mids_after = placed(after_ctx)
        if set(before) != set(after) or not before:
            bad.append("resampling changed which corners are bound: %r vs %r"
                       % (sorted(before), sorted(after)))
        for cid, point in before.items():
            q = after.get(cid)
            if point is None or q is None:
                bad.append("corner %s is bound but unplaced" % cid)
                continue
            if max(abs(point[0] - q[0]), abs(point[1] - q[1])) > 1e-9:
                bad.append("corner %s moved from %r to %r when the geometry "
                           "was resampled" % (cid, point, q))
        if set(mids_before) != set(mids_after) or not mids_before:
            bad.append("resampling changed which segments exist: %r vs %r"
                       % (sorted(mids_before), sorted(mids_after)))
        for key, point in mids_before.items():
            q = mids_after.get(key)
            if point is None or q is None:
                bad.append("segment %r has no midpoint" % (key,))
                continue
            if max(abs(point[0] - q[0]), abs(point[1] - q[1])) > 1e-9:
                bad.append("the half-way point of segment %r moved from %r to "
                           "%r when the geometry was resampled — the "
                           "arc-length guarantee a binding rests on"
                           % (key, point, q))
        # ...and deriving again on the resampled drawing reaches the same
        # answer, so a re-run after a CAD edit is not a different binding.
        again = drawing(outlines(tmp, per_seg=97), ogrid_cell=0.05)
        _ctx2, plan2 = planned(w, again)
        plan2.bind(again, {"body": "", "farfield": ""})
        if (again.topology.ogrid_body_segs,
                again.topology.ogrid_far_segs) != held:
            bad.append("re-deriving on the resampled drawing gave %r, not the "
                       "binding held before it"
                       % (again.topology.ogrid_body_segs,))
    return bad


# ── 7. every broken position at once ────────────────────────────────────────
def check_every_broken_position(w):
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        paths = outlines(tmp)
        cfg = drawing(paths)
        _ctx, plan = planned(w, cfg)
        why = refusal(plan.bind, cfg,
                      {"body": "%s:17,98,99" % paths[0],
                       "farfield": "%s:31,77" % paths[1]})
        for missing in (98, 99, 77):
            if ("segment %d" % missing) not in why:
                bad.append("the refusal does not name unresolvable segment %d, "
                           "so the operator repairs one per round trip: %s"
                           % (missing, why))
        if "17, 18, 19, 20" not in why:
            bad.append("the refusal does not say which segments the geometry "
                       "DOES carry: %s" % why)
        # ...and a role pointing at a geometry this mesh does not load is named
        # in the same breath rather than in the next refusal.
        why2 = refusal(plan.bind, cfg,
                       {"body": os.path.join(tmp, "nope.dat"),
                        "farfield": "%s:77" % paths[1]})
        if "nope.dat" not in why2 or "segment 77" not in why2:
            bad.append("two different kinds of problem are not reported "
                       "together: %s" % why2)
        # ...and the cascade's FOURTH question is asked, not only the first
        # three: a ring family binds a ring, so an OPEN polyline is refused
        # here rather than meshed into a refusal the family issues later.
        openp = write_open(os.path.join(tmp, "open"))
        cfg2 = drawing(paths + [openp])
        _ctx2, plan2 = planned(w, cfg2)
        why3 = refusal(plan2.bind, cfg2,
                       {"body": openp, "farfield": paths[1]})
        if "closed" not in why3:
            bad.append("a role bound to an OPEN polyline is not refused as "
                       "one: %s" % why3)
        if cfg2.topology.ogrid_body_segs:
            bad.append("an open polyline was bound anyway: %r"
                       % cfg2.topology.ogrid_body_segs)
    return bad


# ── 8. a role is per SEGMENT ────────────────────────────────────────────────
def check_role_is_per_segment(w):
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        paths = outlines(tmp)
        cfg = drawing(paths)
        _ctx, plan = planned(w, cfg)
        # Typed out of the geometry's own order on purpose.
        plan.bind(cfg, {"body": "%s:19,17,18" % paths[0],
                        "farfield": "%s:34,31,32,33" % paths[1]})
        if cfg.topology.ogrid_body_segs != "17, 18, 19":
            bad.append("a per-segment assignment bound %r rather than the "
                       "three segments named, in the geometry's own order"
                       % cfg.topology.ogrid_body_segs)
        if cfg.topology.ogrid_far_segs != "31, 32, 33, 34":
            bad.append("a list typed out of order was stored out of order "
                       "(%r), which binds every wall after the first to a "
                       "different stretch of curve"
                       % cfg.topology.ogrid_far_segs)
        # Naming the geometry alone is the convenience spelling of all of them.
        cfg2 = drawing(paths)
        _ctx2, plan2 = planned(w, cfg2)
        plan2.bind(cfg2, {"body": paths[0], "farfield": paths[1]})
        if cfg2.topology.ogrid_body_segs != "17, 18, 19, 20":
            bad.append("naming a geometry did not bind every segment it "
                       "carries: %r" % cfg2.topology.ogrid_body_segs)
        dup = refusal(plan2.bind, cfg2, {"body": "%s:17,17" % paths[0],
                                         "farfield": ""})
        if "twice" not in dup:
            bad.append("one segment at two ring positions was accepted: %s"
                       % dup)
    return bad


# ── 9. the declaration is complete in both directions ───────────────────────
def check_declaration_both_directions(w):
    bad = []
    from dataclasses import fields as dataclass_fields
    from app.services.topology_params import TopologyModel
    declared = {f.name for f in dataclass_fields(TopologyModel)}
    seen_tokens = set()
    for fam in topology_model.FAMILIES:
        try:
            slots = w.slots_for(fam.name)
        except CaseTypeError as exc:
            bad.append("the %s family's roles cannot be derived: %s"
                       % (fam.name, exc))
            continue
        fields = {n for n in declared
                  if n.startswith(fam.prefix) and n.endswith("_segs")}
        covered = {s.segs_field for s in slots}
        if fields != covered:
            bad.append("the %s family binds %r and the roles cover %r"
                       % (fam.name, sorted(fields), sorted(covered)))
        for s in slots:
            seen_tokens.add(s.segs_field[len(fam.prefix):-len("_segs")])
            if s.geom_field not in declared:
                bad.append("role %s.%s names %r, which the model does not "
                           "declare" % (fam.name, s.role, s.geom_field))
            if s.role not in w.ROLE_MEANING:
                bad.append("role %r has no meaning to show the operator"
                           % s.role)
            if s.role not in w.RANK:
                bad.append("role %r has no rank, so the guess cannot place it"
                           % s.role)
        if bool(slots) != fam.binds:
            bad.append("the %s family binds=%r and declares %d role(s)"
                       % (fam.name, fam.binds, len(slots)))
    unused = set(w.SLOT_ROLE) - seen_tokens
    if unused:
        bad.append("declared slot token(s) %r are used by no family, so the "
                   "declaration describes something that is not there"
                   % sorted(unused))
    names = {f.name for f in topology_model.FAMILIES}
    for key in w.OPTIONAL:
        fam, _dot, role = key.partition(".")
        if fam not in names:
            bad.append("the optional entry %r names no registered family" % key)
        elif role not in {s.role for s in w.slots_for(fam)}:
            bad.append("the optional entry %r names no role of that family"
                       % key)
        elif not w.OPTIONAL[key].strip():
            bad.append("the optional entry %r states no reason" % key)
    return bad


# ── 10. the host really answers ─────────────────────────────────────────────
def check_the_host_answers(_w, apply_host=_APPLY_HOST):
    bad = []
    env = dict(os.environ)
    env["PYTHONPATH"] = _GUI + os.pathsep + env.get("PYTHONPATH", "")
    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        paths = outlines(tmp)
        ct_path = os.path.join(tmp, "ct.casetype.json")
        case_type_mod.save(case(extra={"topology.ogrid_cell": 0.05}), ct_path)
        op = drawing(paths, family="")
        op_case = os.path.join(tmp, "op_case.dat")
        op.save_to_file(op_case)
        out = os.path.join(tmp, "fitted.dat")

        def run(*args):
            return subprocess.run(
                [sys.executable, apply_host, ct_path, "--to", op_case]
                + list(args), capture_output=True, text=True, cwd=_REPO,
                env=env)

        bare = run()
        if "body" not in bare.stdout or "farfield" not in bare.stdout:
            bad.append("the host does not show the roles before assignment:\n"
                       "%s\n%s" % (bare.stdout, bare.stderr))
        unconfirmed = run("--confirm", "bl_initial_thickness", "--out", out)
        if unconfirmed.returncode == 0:
            bad.append("the host applied a case type with its pre-selected "
                       "roles unconfirmed and exited 0")
        if "body" not in unconfirmed.stderr:
            bad.append("the host's refusal does not name the unconfirmed role:"
                       " %s" % unconfirmed.stderr)
        if os.path.exists(out):
            bad.append("the refused run wrote %s anyway" % out)
        ok = run("--confirm", "bl_initial_thickness", "--role", "body",
                 "--role", "farfield", "--out", out)
        if ok.returncode != 0:
            bad.append("the host refused a fully answered application: %s"
                       % ok.stderr)
        doc = os.path.join(tmp, "fitted_topology.json")
        if not os.path.exists(out) or not os.path.exists(doc):
            bad.append("a case type naming a family did not write a `.dat` "
                       "and its topology document: %s" % sorted(os.listdir(tmp)))
            return bad
        with open(doc, encoding="utf-8") as fh:
            text = fh.read()
        segs = {c.get("seg") for c in json.loads(text).get("corners", [])
                if c.get("kind") == "on_geometry"}
        if segs != set(BODY_IDS) | set(FAR_IDS):
            bad.append("the written document binds %r, not the operator's own "
                       "segments" % sorted(s for s in segs if s is not None))
        typo = run("--confirm", "bl_initial_thickness", "--role", "boddy")
        if typo.returncode == 0 or "boddy" not in typo.stderr:
            bad.append("a misspelled role did not name the roles that exist: "
                       "%s" % typo.stderr)
    return bad


# ── 11. Qt-free ─────────────────────────────────────────────────────────────
def check_qt_free(_w):
    code = ("import sys; sys.path.insert(0, %r);"
            "from app.services import case_type_roles;"
            "mods=[m for m in sys.modules if m.startswith(('PyQt','PySide'))];"
            "print(mods)" % _GUI)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=_REPO)
    if out.returncode != 0:
        return ["importing the service failed: %s" % out.stderr]
    return ([] if out.stdout.strip() == "[]"
            else ["importing the service pulled in Qt: %s" % out.stdout])


# ── 12. end to end through the real binary ──────────────────────────────────
def check_end_to_end(_w):
    if not os.path.exists(_MESHER):
        print("      (skipped: no ./build/HybMesh2D)", flush=True)
        return []
    bad = []
    env = dict(os.environ)
    env["PYTHONPATH"] = _GUI + os.pathsep + env.get("PYTHONPATH", "")
    with tempfile.TemporaryDirectory() as _raw:
        tmp = os.path.realpath(_raw)
        paths = outlines(tmp, square=False)
        ct_path = os.path.join(tmp, "ct.casetype.json")
        case_type_mod.save(case(extra={"topology.ogrid_cell": 0.05}), ct_path)
        op = drawing(paths, family="")
        op.output_filename = os.path.join(tmp, "out", "m.vtk")
        op_case = os.path.join(tmp, "op_case.dat")
        op.save_to_file(op_case)
        out = os.path.join(tmp, "fitted.dat")
        applied = subprocess.run(
            [sys.executable, _APPLY_HOST, ct_path, "--to", op_case,
             "--confirm", "bl_initial_thickness", "--role", "body",
             "--role", "farfield", "--out", out],
            capture_output=True, text=True, cwd=_REPO, env=env)
        if applied.returncode != 0:
            return ["the case type could not be applied: %s" % applied.stderr]
        # FROM THE CONFIG'S OWN DIRECTORY: the writer spells a geometry
        # outside the repo relative to the config beside it, and the mesher
        # opens what the line says relative to its OWN working directory.
        run = subprocess.run([_MESHER, "-conf", out], capture_output=True,
                             text=True, cwd=tmp, env=mesher_env())
        if run.returncode != 0:
            bad.append("the mesher exited %d on a role-derived topology:\n%s"
                       % (run.returncode, run.stdout[-1500:]))
        mesh = os.path.join(tmp, "out", "m.vtk")
        if not os.path.exists(mesh):
            bad.append("no mesh at %s" % mesh)
    return bad


_ALL = {
    1: check_roles_are_declared,
    2: check_bindings_are_derived,
    3: check_different_ids_bind,
    4: check_guess_is_confirmed,
    5: check_missing_required_role_blocks,
    6: check_resampling_does_not_move_a_binding,
    7: check_every_broken_position,
    8: check_role_is_per_segment,
    9: check_declaration_both_directions,
    10: check_the_host_answers,
    11: check_qt_free,
    12: check_end_to_end,
}

_LABELS = {
    1: "check 1. the roles a family needs are DERIVED from the model and shown "
       "before assignment, with what each one is and whether it is required",
    2: "check 2. bindings are derived from roles against the operator's own "
       "segments, and no id from the authoring geometry survives",
    3: "check 3. a drawing whose segment ids are nothing like the authoring "
       "one builds a real topology document, every corner on the operator's "
       "own segments",
    4: "check 4. a pre-selected role is REFUSED until confirmed, naming every "
       "unconfirmed one — and the pre-selection is ranked by enclosed area, so "
       "reversing the geometry list does not move it",
    5: "check 5. an unassigned REQUIRED role blocks and names itself; an "
       "unassigned OPTIONAL one does not",
    6: "check 6. re-resampling a bound geometry moves no binding and no corner",
    7: "check 7. EVERY unresolvable position is named by one refusal, not the "
       "first",
    8: "check 8. a role is per SEGMENT: a subset binds exactly that subset, in "
       "the GEOMETRY's own order whatever order it was typed in",
    9: "check 9. every family's binding lists map to exactly one declared role, "
       "and every declaration is used — both directions",
    10: "check 10. the applying HOST shows the roles, exits 1 on an "
        "unconfirmed one, and writes the `.dat` and the topology document "
        "holding the operator's ids",
    11: "check 11. the service is Qt-free",
    12: "check 12. END TO END: a case type naming `ogrid`, applied to a drawing "
        "with foreign segment ids, meshes through the real binary",
}

_REAL = world()

for num in sorted(_ALL):
    fails = _ALL[num](_REAL)
    check(not fails, _LABELS[num])
    for f in fails:
        print("      " + f.replace("\n", "\n      "), flush=True)


# --- injections ---------------------------------------------------------------
# Checks 10, 11 and 12 launch SUBPROCESSES against the real files on disk; none
# can see an in-memory mutant, so scoring them under `others_green` would count
# them as evidence of something they are not measuring.
_SKIP_UNDER_MUTATION = (10, 11, 12)


def others_green(w, *reddened):
    """True when every check BUT the named ones still passes on the mutant."""
    return not any(fn(w) for num, fn in _ALL.items()
                   if num not in reddened and num not in _SKIP_UNDER_MUTATION)


def mutate(which, old, new, count=1):
    src = _SRC["app.services." + which]
    assert old in src, "injection anchor not found in %s: %r" % (which, old)
    mutated = src.replace(old, new, count)
    assert mutated != src
    return world(**{which: mutated})


inj = mutate("case_type_roles", "        if waiting:\n",
             "        if False:\n")
check(inj.RolePlan(
          "ogrid", inj.slots_for("ogrid"),
          {"body": inj.Guess("body", "x.dat", (1,), "why")}, None)
      .unconfirmed({}),
      "injection A. injection is well-formed: the plan still REPORTS an "
      "unconfirmed pre-selection, so only the refusal was removed")
check(check_guess_is_confirmed(inj) and others_green(inj, 4),
      "injection A. check 4 fails when `bind` stops refusing an unconfirmed "
      "pre-selection — somebody else's idea of which curve is the body reaches "
      "the mesher, and the mesh exports looking right with the far field's "
      "conditions on it")

inj = mutate("case_type_roles",
             "        if missing:\n            return None, problems",
             "        if missing:\n            return None, problems[:1]")
check(check_every_broken_position(inj) and others_green(inj, 7),
      "injection B. check 7 fails when only the FIRST unresolvable position is "
      "reported, which is a generate, a refusal and a return to the drawing "
      "per wrong segment")

inj = mutate(
    "case_type_roles",
    "            elif slot.required:\n                problems.append(",
    "            elif slot.required and False:\n                problems.append(")
check(check_missing_required_role_blocks(inj) and others_green(inj, 5),
      "injection C. check 5 fails when a missing REQUIRED role stops blocking: "
      "the run proceeds with a list nobody bound, and the family's own refusal "
      "is the first anyone hears of it")

inj = mutate("case_type_roles",
             "        ordered = [s for s in g.seg_ids if s in want]",
             "        ordered = list(segs)")
check(check_role_is_per_segment(inj) and others_green(inj, 8),
      "injection D. check 8 fails when a typed order is stored instead of the "
      "GEOMETRY's — every id still resolves and every wall after the first "
      "binds to a different stretch of curve, with nothing to say so")

inj = mutate("case_type_roles", '    "seam": "seam",\n', "")
check(check_declaration_both_directions(inj) and others_green(inj, 9, 1, 5),
      "injection E. check 9 fails when a family's slot has no declared role "
      "word — a list nobody named is a role nobody can assign. Checks 1 and 5 "
      "go with it and are not claimed as independent evidence: both ask the "
      "two-ring family for its three roles, and it now has two")

inj = mutate("case_type_guess",
             "    ranked = sorted(pool, key=lambda g: g.equivalent_radius())",
             "    ranked = list(pool)")
check(check_guess_is_confirmed(inj) and others_green(inj, 4),
      "injection F. check 4 fails when the pre-selection ranks by the GEOMETRY "
      "LIST's order instead of enclosed area — the drawing-order convention "
      "#158 excluded by decision, reintroduced inside the guess")

inj = mutate("case_type_guess",
             '    if "farfield" in by_role:', "    if False:")
check(check_guess_is_confirmed(inj) and others_green(inj, 4),
      "injection G0. check 4 fails when the guess stops reading the drawing's "
      "OWN evidence and ranks everything — a geometry the operator already "
      "called the far field in another panel is then just the biggest outline, "
      "and on a drawing the ranking cannot order it is offered nothing at all")

inj = mutate("case_type_guess",
             "            and _role_word(config, g.path) "
             "not in NON_OUTLINE_ROLES]",
             "]")
check(check_guess_is_confirmed(inj) and others_green(inj, 4),
      "injection G1. check 4 fails when a refinement SEED is ranked as an "
      "outline: it shifts every slot by one, so the body is pre-selected as "
      "whatever happens to be smaller than it")

# G reaches the one file an in-memory mutant cannot: the applying HOST, which
# runs as a subprocess. Without it check 10 — the acceptance criterion that the
# operator CONFIRMS — would be the only check here never shown able to redden.
_apply_src = _read(os.path.relpath(_APPLY_HOST, _REPO))
_anchor = "        for binding in roles.bind(fitted, assigned):"
assert _anchor in _apply_src, "host injection anchor not found: %r" % _anchor
with tempfile.TemporaryDirectory() as _tmp:
    _mutant = os.path.join(_tmp, "apply_case_type_mutant.py")
    with open(_mutant, "w", encoding="utf-8") as _fh:
        _fh.write(_apply_src.replace(
            _anchor,
            "        _guessed = {r: '' for r in roles.roles}\n"
            "        _guessed.update(assigned)\n"
            "        _bound = []\n"
            "        for _slot in roles.slots:\n"
            "            _g = roles.guesses.get(_slot.role)\n"
            "            if _g is None:\n"
            "                continue\n"
            "            setattr(fitted.topology, _slot.geom_field, _g.geom)\n"
            "            setattr(fitted.topology, _slot.segs_field,\n"
            "                    ', '.join(str(s) for s in _g.segs))\n"
            "            _bound.append(_g)\n"
            "        for binding in _bound:", 1))
    _mutant_ok = check_the_host_answers(_REAL, apply_host=_mutant)
    check(bool(_mutant_ok),
          "injection G. check 10 fails when the applying HOST writes the "
          "pre-selection straight into the model instead of asking the service "
          "to bind it — the confirmation is bypassed by the one caller that "
          "has to ask")
    check(not any("could not" in f or "Traceback" in f for f in _mutant_ok),
          "injection G. ...and the mutant host RAN rather than crashing, so "
          "the failure above is the bypass and not an import error wearing its "
          "name: %s" % ("; ".join(f.split("\n")[0] for f in _mutant_ok)[:200]))
    check(not check_the_host_answers(_REAL),
          "injection G. ...and the UNmutated host still passes it, so the "
          "failure above is the mutation and not the copy or its PYTHONPATH")

check(not any(fn(_REAL) for num, fn in _ALL.items()),
      "injection H. negative control: the unmutated service passes every "
      "check, so the failures above are the mutations and not the checker")


print("\n%s: %d check(s) failed" % (os.path.basename(__file__), len(_FAILS))
      if _FAILS else "\nAll checks passed.", flush=True)
sys.exit(1 if _FAILS else 0)
