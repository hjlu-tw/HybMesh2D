#!/usr/bin/env python3
"""EACH FAMILY SAYS WHETHER IT CAN WORK WITH WHAT IT WAS GIVEN (issue #165, parent #158).

#164 bound a case type to the operator's own curves by ROLE and left this exactly
here, in as many words: "NOTHING JUDGES WHETHER THE ROLE IS THE RIGHT CURVE. The
guess is ranked and the operator confirms; a confirmed assignment naming the far
field as the body binds exactly that, and only the family's own refusal (#165)
will notice." This ticket is that refusal.

WHY IT IS NOT AN EXIT CODE. `EXIT_ERR_TOPOLOGY` (8) fires after the operator has
committed — picked a case type, assigned roles, pressed Generate and waited — and
its message is written for a developer. MEASURED on the drawing check 6 builds,
the mesher says:

    block 'q0': its corners 'b0', 'f0', 'f1', 'b1' wind clockwise (signed area
    -0.403553), so every cell in it would be inverted. Reverse its south edge's
    own corner pair, or swap the block's south and north edges.

Every noun in it is an id of a document the operator never opened. What they can
act on is "the body you drew as 'body.dat' reaches (2, -0.1), which is outside
the far field 'far.dat'" — and which curve on the canvas that is.

WHY FOUR REFUSALS AND NOT ONE TABLE. The preconditions genuinely differ: the
O-grid needs a closed loop, the C-grid a sharp trailing edge, the H-grid a
rectangle with four distinct corners, the two-ring a seam strictly between two
other closed loops. A shared rule table could hold only what all four agree on,
which is nearly nothing — so each family declares its own beside its build
function, and the REGISTRY is where "a family with no refusal" is caught:
`Family.preflight` has no default, so such a family does not construct.

What this pins down:

  1. EVERY FAMILY ANSWERS, BOTH WAYS. All four accept a drawing they can fill
     and refuse one they cannot, driven through the registry dispatch rather
     than by calling a family by name — so a family the registry forgot is
     invisible to no check here. 1a adds the criterion's own word — a family
     whose row is a PARAMETER refusal is also handed a GEOMETRY it cannot fill
     (the other three rows already are one, and the H-grid cannot have one: it
     binds to nothing). And the MODE is the other half of the question: the
     drawing check 6 proves the multi-block path must refuse is NOT refused on
     the hybrid path, where a named family drives nothing.
  2. THE REFUSAL IS REACHED BEFORE ANY MESHER PROCESS. Driven, not read: the
     headless runner's own `_run_mesh` is called with the subprocess launcher
     replaced by a recorder, and the recorder is never called. The GUI's order
     is read off its `ast` — the guard must sit above `MeshGenWorker(` — because
     a QThread is not startable in this process.
  3. IT SPEAKS IN THE OPERATOR'S TERMS. No refusal this gate can produce names a
     family identifier, an exit code, a `TopologyModel` field, a document id or
     the JSON the operator never opened; every one of them names an action; and
     every one names its curve EXACTLY ONCE — the conditional prefix's whole
     job, and the property neither of the two needles review weighed was gated
     on until it was written down here.
  4. IT IDENTIFIES THE OFFENDING CURVE, AND THE GUI POINTS AT IT. The structured
     half is checked here (the geometry is one of the drawing's, the marked
     point really is outside the far field, and `refusal_points` returns that
     curve's own polyline); the canvas half is DRIVEN in a subprocess through a
     real `AppController`, whose mesh canvas is left holding the highlight.
  5. THE REGISTRY ENFORCES THAT A FAMILY HAS ONE. Constructing a `Family`
     without a refusal raises; every registered family's refusal is callable,
     returns `Refusal` rows, and REALLY REFUSES something — a family that
     always answered `()` would pass every other check in this file.
  6. THE GAP THAT BOUGHT CONTAINMENT, as a regression. A 4.0 x 0.2 body inside a
     unit-circle far field satisfies the equivalent-radius nesting both ring
     families used (0.505 < 0.9999) and pokes out to x = +-2. Asserted in three
     steps: the old ruler accepts it, the new refusal names it, and the REAL
     MESHER refuses the document it would have produced. 6e is the same gap in
     the TWO-RING family, whose three outlines nest by the same ruler: a long
     thin seam whose equivalent radius sits neatly between the other two while
     it crosses the body.
  7. QT-FREE, in a subprocess.
  8. EVERY PROBLEM AT ONCE, never the first — the rule `case_type_roles` and
     `topology_model.broken_bindings` already follow, because repairing a
     drawing one refusal at a time is a generate, a refusal and a return per
     wrong curve.
  9. #164's NAMED BLIND SPOT, CLOSED. `apply_case_type.py` is driven as a
     subprocess with the two roles SWAPPED and both CONFIRMED — every id
     resolves, both questions are answered, and nothing before this ticket had
     anything to say about it. The host exits 1 with the family's own sentence
     and writes nothing.

Known blind spots, named rather than papered over:
  - THE C-GRID'S FAR FIELD KEEPS ITS REFUSAL IN `plan`, because that family may
    GENERATE one from two lengths, so the ring it tests is not always a curve
    the operator drew and a refusal carrying a geometry would name one that does
    not exist. Its section cascade is the half that gains a curve here.
  - CONTAINMENT IS CONTAINMENT, NOT USEFULNESS — `gui-topology.md` already
    records this for the C-grid and it is unchanged: a far field one body-length
    out contains the body and is refused by nothing. The check exists to stop
    blocks folding, not to judge a domain.
  - A TANGENT TOUCH IS NOT RESOLVED. `outside_point` uses a crossing test, so a
    body whose point lies exactly ON the far-field polyline may read either way.
    Inherited from #149's check rather than introduced, and no shipped case is
    within a rounding of it.
  - THE H-GRID'S REFUSALS NAME NO CURVE, correctly: it binds to nothing and its
    region is four numbers in the template rows. So acceptance criterion "the
    GUI points at the offending curve" is vacuous for one family of four, and
    check 4 says so by excluding it rather than by passing on it.
  - THE CANVAS POINTED AT IS THE MESH TAB'S, not the CAD tab's, which is what
    #165's wording says. It is where the operator is when they press Generate
    and where the geometries are previewed; the substitution is named rather
    than made silently.
  - ONE OF GridPro's FOUR CLASSES IS ACTUALLY CHECKED. Containment is the
    coarsest half of "cutting on the concave side"; face mismatch CANNOT ARISE
    on this path (one edge, named by both blocks, welded by id), which is not
    the same as being checked; singular edges and the singularity-count rule
    are not checked at all and would need a counter over the document a family
    produces. Nothing here ties a check to a taxonomy class, and the accounting
    lives in `topology_preflight`'s own header.
  - NOTHING HERE RE-ASKS WHAT THE MESHER ASKS. The two sides are held at
    opposite ends — check 6c proves the mesher refuses the one document this
    ticket's new check catches — and nothing asserts the two refuse the SAME
    set. A drawing both accept that still folds is the next gap, and it would
    arrive as a regression test here by this ticket's own rule.

INJECTIONS — AUTOMATED, by exec'ing a mutated copy of the service sources and
re-running the same check functions against the mutant. All five service files
are mutable (the shared module and the four families), so an injection does not
stop being able to redden a check the day its subject moves. Each asserts the
mutation is well-formed and really differs, then that the named check fails AND
that no other check moves (`others_green`):

  A. `enclosure_refusal` stops looking -> check 6 fails: the drawing that folds
     the mesher is accepted again, which is the whole ticket.
  B. `outline_refusal` drops the geometry from the refusal -> check 4 fails: the
     sentence survives and the canvas has nothing to point at.
  C. the H-grid's refusal returns `()` -> check 5 fails: a family that answers
     "nothing is wrong" to every drawing, which is the shape a family with no
     refusal at all would have if the registry allowed one.
  D. `refusal_text` reports only the first row -> check 8 fails: the operator
     repairs their drawing one run at a time.
  E. `Refusal.text` prepends the family name -> check 3 fails: an internal
     identifier in a sentence written for an operator.
  F. negative control: the unmutated service passes every check.

Run:  python3 tools/PreProcessor/tests/test_topology_preflight.py
Needs no Qt and no network. Checks 4c, 7 and 9 are subprocesses — 4c builds a
real `AppController` off-screen — and 6c/6d self-skip without
./build/HybMesh2D. Checks 7 and 9 are excluded from `others_green`, being
child processes over the real sources that no in-memory mutant reaches; 4c is
the same and is stated at its own call site, where 4a and 4b are what an
injection moves.
"""
import ast
import copy
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

from mesher_bin import NO_SMOOTH, mesher_env  # noqa: E402
from topology_outline_fixture import write_airfoil, write_outline  # noqa: E402

_MESHER = os.path.join(_REPO, "build", "HybMesh2D")

#: name -> repo-relative source, in DEPENDENCY order. The shared module first,
#: then the four families that import `Refusal` from it. Every one is mutable:
#: an injection that could only reach the shared file would stop being able to
#: redden a check the day a rule moved into a family, which is the direction
#: this ticket's own design pushes.
_RELS = [
    ("app.services.topology_preflight",
     "tools/PreProcessor/gui/app/services/topology_preflight.py"),
    ("app.services.topology_hgrid",
     "tools/PreProcessor/gui/app/services/topology_hgrid.py"),
    ("app.services.topology_ogrid",
     "tools/PreProcessor/gui/app/services/topology_ogrid.py"),
    ("app.services.topology_cgrid",
     "tools/PreProcessor/gui/app/services/topology_cgrid.py"),
    ("app.services.topology_tworing",
     "tools/PreProcessor/gui/app/services/topology_tworing.py"),
    ("app.services.topology_model",
     "tools/PreProcessor/gui/app/services/topology_model.py"),
]

_FAILS = []
#: True while a MUTANT is being scored. A sub-check failing then is the
#: injection working, not this gate failing, so it is shown (diagnosing a stray
#: needs to see which one moved) and NOT counted — the verdict for an injected
#: run is the `injected()` pair below it.
_QUIET = False


def check(cond, msg):
    if _QUIET:
        print(("   . " if cond else "   x ") + msg, flush=True)
        return
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _read(rel):
    with open(os.path.join(_REPO, rel), encoding="utf-8") as fh:
        return fh.read()


_SRC = {name: _read(rel) for name, rel in _RELS}


def world(**mutated):
    """A fresh registry built over fresh sources, optionally mutated.

    Returns the `topology_model` module — the registry and the dispatch — so a
    check asks the same object every host asks. A mutant left only in
    `sys.modules` is shadowed by the PACKAGE attribute `from app.services import
    x` resolves through first (#160), so both are set; this is the harness
    `test_case_type_roles.py` and `test_case_type_fields.py` already use.
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
        return built["topology_model"]
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
from app.services import topology_binding  # noqa: E402

#: The operator's own segment ids — nothing like 0..3, so an id that leaked from
#: somewhere else is visible as itself rather than as a coincidence.
BODY_IDS = (17, 18, 19, 20)
SEAM_IDS = (51, 52, 53, 54)
FAR_IDS = (31, 32, 33, 34)
SECTION_IDS = (71, 72)
BLUNT_IDS = (71, 72, 73)

_TMP = tempfile.mkdtemp(prefix="preflight_")


# ── the drawings ────────────────────────────────────────────────────────────

def _outlines(tag, body_r=0.5, seam_r=1.5, far_r=5.0, square=True):
    """Concentric closed outlines with the operator's own segment ids."""
    out = []
    for name, r, ids, bc in (("body", body_r, BODY_IDS, "wall"),
                             ("seam", seam_r, SEAM_IDS, "wall"),
                             ("far", far_r, FAR_IDS, "farfield")):
        out.append(write_outline(os.path.join(_TMP, tag + "_" + name), r,
                                 list(ids), 40, bc, square=square))
    return out


def write_box(stem, half_w, half_h, seg_ids, bc="wall", per_side=20):
    """A closed rectangle, so a body can be LONG AND THIN.

    `write_outline`'s square is the one shape it draws and its two half-widths
    are the same number; check 6 needs them apart, because an equivalent radius
    is area-derived and only a shape far from round separates it from "is this
    inside that".
    """
    c = [(half_w, -half_h), (half_w, half_h), (-half_w, half_h),
         (-half_w, -half_h)]
    runs = []
    for k in range(4):
        a, b = c[k], c[(k + 1) % 4]
        runs.append([(a[0] + (b[0] - a[0]) * j / per_side,
                      a[1] + (b[1] - a[1]) * j / per_side)
                     for j in range(per_side)])
    pts, ids = [], []
    for sid, run in zip(seg_ids, runs):
        pts += run
        ids += [sid] * len(run)
    pts.append(pts[0])
    ids.append(seg_ids[0])
    with open(stem + ".dat", "w", encoding="utf-8") as fh:
        for x, y in pts:
            fh.write("%.12f %.12f\n" % (x, y))
    with open(stem + ".dat.meta", "w", encoding="utf-8") as fh:
        fh.write("HYBMESH_META 2\n")
        fh.write("COUNT %d\n" % len(pts))
        fh.write("NPIECES 0\n")
        fh.write("NSEGMENTS %d\n" % len(seg_ids))
        for sid in seg_ids:
            fh.write("%d %s line\n" % (sid, bc))
        fh.write("POINTS %d\n" % len(pts))
        prev = object()
        for sid in ids:
            fh.write("%d %d\n" % (sid, 1 if sid != prev else 0))
            prev = sid
    return stem + ".dat"


def write_open(stem, seg_id=61):
    """An OPEN polyline — a curve no ring can go round."""
    pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
    with open(stem + ".dat", "w", encoding="utf-8") as fh:
        for x, y in pts:
            fh.write("%.12f %.12f\n" % (x, y))
    with open(stem + ".dat.meta", "w", encoding="utf-8") as fh:
        fh.write("HYBMESH_META 2\nCOUNT %d\nNPIECES 0\nNSEGMENTS 1\n"
                 % len(pts))
        fh.write("%d wall line\n" % seg_id)
        fh.write("POINTS %d\n" % len(pts))
        for k in range(len(pts)):
            fh.write("%d %d\n" % (seg_id, 1 if k == 0 else 0))
    return stem + ".dat"


def drawing(paths, family, **params):
    """A `MeshConfig` holding a geometry list, a family and its parameters."""
    cfg = MeshConfig()
    cfg.set_geom_files(list(paths))
    cfg.mesh_mode = 1
    cfg.bl_initial_thickness = 0.001
    cfg.topology.family = family
    for name, value in params.items():
        setattr(cfg.topology, name, value)
    return cfg


def _ids(seq):
    return ",".join(str(s) for s in seq)


_BODY, _SEAM, _FAR = _outlines("ok")
_SHARP = write_airfoil(os.path.join(_TMP, "sharp"), list(SECTION_IDS),
                       ["wall", "wall"])
_BLUNT = write_airfoil(os.path.join(_TMP, "blunt"), list(BLUNT_IDS),
                       ["wall"] * 3, sharp_te=False)
_OPEN = write_open(os.path.join(_TMP, "open"))
#: The drawing check 6 is about: a 4.0 x 0.2 body inside a unit far field.
_POKE_BODY = write_box(os.path.join(_TMP, "poke_body"), 2.0, 0.1,
                       list(BODY_IDS))
_POKE_FAR = write_outline(os.path.join(_TMP, "poke_far"), 1.0, list(FAR_IDS),
                          40, "farfield")


def ogrid(body=_BODY, far=_FAR, **extra):
    params = dict(ogrid_body_geom=body, ogrid_body_segs=_ids(BODY_IDS),
                  ogrid_far_geom=far, ogrid_far_segs=_ids(FAR_IDS),
                  ogrid_splits=1, ogrid_cell=0.2)
    params.update(extra)
    return drawing([body, far], "ogrid", **params)


def tworing(body=_BODY, seam=_SEAM, far=_FAR, **extra):
    params = dict(tworing_body_geom=body, tworing_body_segs=_ids(BODY_IDS),
                  tworing_seam_geom=seam, tworing_seam_segs=_ids(SEAM_IDS),
                  tworing_far_geom=far, tworing_far_segs=_ids(FAR_IDS),
                  tworing_splits=1, tworing_cell=0.2)
    params.update(extra)
    return drawing([body, seam, far], "tworing", **params)


def cgrid(section=_SHARP, segs=SECTION_IDS, **extra):
    params = dict(cgrid_body_geom=section, cgrid_body_segs=_ids(segs))
    params.update(extra)
    return drawing([section], "cgrid", **params)


def hgrid(**extra):
    return drawing([], "hgrid", **extra)


#: Per family: the drawing it accepts, the drawing it refuses, and the word a
#: reader should see in the refusal. Declared as a table so check 1 cannot
#: quietly cover three families — and so the FAMILIES it names can be compared
#: with the registry's own list in both directions (check 5c).
CASES = {
    "hgrid": (hgrid(),
              hgrid(hgrid_x_max=-1.0),
              "inside out"),
    "ogrid": (ogrid(),
              ogrid(body=_OPEN, ogrid_body_segs="61"),
              "closed loop"),
    "cgrid": (cgrid(),
              cgrid(section=_BLUNT, segs=BLUNT_IDS),
              "SHARP trailing edge"),
    "tworing": (tworing(),
                tworing(seam=""),
                "seam"),
}

#: The one family whose row above refuses a PARAMETER rather than a geometry and
#: that CAN be handed a geometry it cannot fill. The O-grid's row is an open
#: outline and the C-grid's a blunt section — both already geometries — and the
#: H-grid has no such case by construction: it binds to nothing, so every drawing
#: is one it can fill and its refusals are about the four numbers it declares.
#: The seam here NESTS correctly and is cut into THREE segments where the body
#: has four, so it is refused for its shape rather than for its position — which
#: also keeps this check clear of the containment gap check 6 owns.
_ODD_SEAM = write_outline(os.path.join(_TMP, "odd_seam"), 1.5,
                          list(SEAM_IDS[:3]), 40, "wall", square=True)
GEOMETRY_CASES = {
    "tworing": (tworing(seam=_ODD_SEAM,
                        tworing_seam_segs=_ids(SEAM_IDS[:3])),
                "one to one"),
}


# ── 1. every family answers, both ways ──────────────────────────────────────

def check_1(w):
    bad = []
    for name, (good, poor, word) in CASES.items():
        accepted = w.preflight_for_config(good)
        refused = w.preflight_for_config(poor)
        if accepted:
            bad.append("%s refused a drawing it can fill: %s"
                       % (name, accepted[0].text()[:90]))
        if not refused:
            bad.append("%s accepted a drawing it cannot fill" % name)
        elif word not in " ".join(r.text() for r in refused):
            bad.append("%s refused without saying %r: %s"
                       % (name, word, refused[0].text()[:90]))
    check(not bad, "1. all four families accept what they can fill and refuse "
                   "what they cannot, each saying what is wrong%s"
                   % ("" if not bad else " -- " + "; ".join(bad)))

    # THE MODE IS THE OTHER HALF OF THE QUESTION. A family named while the mode
    # is HYBRID drives nothing — the panel hides the whole section and the run
    # reads none of it — so refusing a hybrid run over it would be this ticket's
    # own worst outcome pointed the other way: a mesh the operator can have,
    # withheld over a template nothing reads. The drawing is the one check 6
    # proves the multi-block path must refuse.
    # THE CRITERION IS ABOUT GEOMETRIES, and one row above refuses a blank name
    # instead. That family gets a drawing it cannot fill as well; the other three
    # rows already are one (an open outline, a blunt section) or cannot have one
    # (the H-grid binds to nothing).
    for name, (poor, word) in GEOMETRY_CASES.items():
        rows = w.preflight_for_config(poor)
        if not rows:
            bad.append("%s accepted a GEOMETRY it cannot fill" % name)
        elif word not in " ".join(r.text() for r in rows):
            bad.append("%s refused a geometry without saying %r: %s"
                       % (name, word, rows[0].text()[:90]))
    check(not bad, "1a. and a family whose row above refuses a parameter "
                   "refuses a GEOMETRY it cannot fill too%s"
                   % ("" if not bad else " -- " + "; ".join(bad)))

    hybrid = ogrid(body=_POKE_BODY, far=_POKE_FAR)
    hybrid.mesh_mode = 0
    ok_b = not w.preflight_for_config(hybrid) and not w.mesh_preflight(hybrid)
    check(ok_b, "1b. the same drawing is NOT refused on the HYBRID path, where "
                "a named family drives nothing")
    return not bad and ok_b


# ── 2. before any mesher process ────────────────────────────────────────────

def check_2(w):
    """The headless runner refuses without launching anything, and the GUI's
    guard sits above the worker."""
    import app.services.pipeline_runner as pr
    launched = []

    class _Pcfg:
        name = "preflight_demo"

        def build_mesh_config(self, geom_files):
            cfg = copy.deepcopy(CASES["ogrid"][1])
            cfg.output_filename = os.path.join(_TMP, "never.vtk")
            return cfg

    saved = (pr.find_binary_executable, pr._stream, pr.mesh_preflight)
    pr.find_binary_executable = lambda name: os.path.join(_TMP, "fake_mesher")
    pr._stream = lambda *a, **k: launched.append(a) or 0
    # The runner imported `mesh_preflight` by NAME, so the mutant registry has
    # to be routed in by rebinding that name -- otherwise every injection below
    # would leave this check green against the real service.
    pr.mesh_preflight = w.mesh_preflight
    try:
        raised = ""
        try:
            pr._run_mesh(_Pcfg(), _REPO, [], False, lambda m: None)
        except pr.PipelineError as exc:
            raised = str(exc)
        except Exception as exc:                      # pragma: no cover
            raised = "UNEXPECTED %r" % (exc,)
    finally:
        pr.find_binary_executable, pr._stream, pr.mesh_preflight = saved
    ok_a = bool(raised) and "closed loop" in raised and not launched
    check(ok_a, "2a. the headless runner refuses the drawing and launches NO "
                "process (launched=%d, said %r)"
                % (len(launched), raised[:80]))

    src = _read("tools/PreProcessor/gui/app/controllers/mesh_gen_ctrl.py")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef)
               and n.name == "run_mesh_generator"), None)
    guard = worker = None
    for node in ast.walk(fn) if fn is not None else ():
        if (isinstance(node, ast.Attribute)
                and node.attr == "_topology_preflight_refused"):
            guard = node.lineno if guard is None else min(guard, node.lineno)
        if isinstance(node, ast.Name) and node.id == "MeshGenWorker":
            worker = node.lineno if worker is None else min(worker, node.lineno)
    ok_b = guard is not None and worker is not None and guard < worker
    check(ok_b, "2b. the GUI asks the families BEFORE it builds the worker "
                "(guard line %s, worker line %s)" % (guard, worker))
    return ok_a and ok_b


# ── 3. the operator's terms ─────────────────────────────────────────────────

#: Words a refusal written for an operator must never contain. The four family
#: identifiers are here as themselves: "C-grid" is the label the combo shows and
#: is welcome, `cgrid` is the registry key and is not.
BANNED = ("ogrid", "cgrid", "hgrid", "tworing", "HYBMESH_ERROR", "EXIT_ERR",
          "_geom", "_segs", "TopologyModel", "format_version", "signed area",
          ".json", "BindingError", "traceback")


def _every_refusal(w):
    out = []
    for _good, poor, _word in CASES.values():
        out += list(w.preflight_for_config(poor))
    out += list(w.preflight_for_config(ogrid(body=_POKE_BODY, far=_POKE_FAR)))
    out += list(w.preflight_for_config(ogrid(body=_OPEN, ogrid_body_segs="61",
                                             far=_OPEN)))
    out += list(w.preflight_for_config(hgrid(hgrid_nx=0, hgrid_cell=0.0)))
    return out


def check_3(w):
    rows = _every_refusal(w)
    bad = []
    for r in rows:
        text = r.text()
        for token in BANNED:
            if token in text:
                bad.append("%r in %r" % (token, text[:80]))
        if "'" not in text and not r.fix:
            bad.append("nothing named and nothing to do in %r" % text[:80])
        # NEVER THE CURVE TWICE, and never the curve not at all: the prefix is
        # conditional for exactly this, and review tried the other needle --
        # the SPELLING -- which suppresses nothing for a sentence that embeds
        # the basename and prints "'body.dat': the body you drew as
        # 'body.dat' reaches...". Both sentence shapes are in `rows`:
        # `outline_problem` embeds `g.spelling`, `enclosure_refusal` the
        # basename, and the two are the same curve named two ways.
        if r.curve():
            if text.count(r.curve()) != 1:
                bad.append("the curve is named %d time(s) in %r"
                           % (text.count(r.curve()), text[:80]))
    ok = bool(rows) and not bad
    check(ok, "3. all %d refusals speak in the operator's terms -- no family "
              "identifier, exit code, model field or document id, each quotes "
              "something the operator can point at or change, and none names "
              "its curve twice or not at all%s"
              % (len(rows), "" if not bad else " -- " + "; ".join(bad[:3])))
    return ok


# ── 4. the offending curve, and the canvas ──────────────────────────────────

def check_4(w):
    """The curve a refusal is about, and the canvas pointing at it.

    Its subject is `outline_refusal` — the shared cascade every binding family
    asks — rather than the containment refusal check 6 owns, so the two
    injections stay apart: A kills containment and B kills the curve, and each
    reddens exactly one of these two checks.
    """
    cfg = ogrid(body=_OPEN, ogrid_body_segs="61")
    rows = w.preflight_for_config(cfg)
    ctx = topology_binding.context_for_config(cfg)
    ok_a = len(rows) == 1 and rows[0].geom == _OPEN
    check(ok_a, "4a. the refusal names the offending curve as one of the "
                "drawing's own geometries (%r)"
                % (os.path.basename(rows[0].geom) if rows else None))

    pts = w.topology_preflight.refusal_points(ctx, rows[0]) if rows else []
    g = ctx.geometry(_OPEN)
    want = sum(len(g.spans[s].points) for s in g.seg_ids) if g else -1
    ok_b = bool(pts) and len(pts) == want + max(0, len(g.seg_ids) - 1)
    check(ok_b, "4b. the points a host draws are that curve's own polyline, "
                "one nan row per joint (%d points for %d segment(s))"
                % (len(pts), len(g.seg_ids) if g else 0))

    # 4c. the GUI really points at it, driven through a real AppController. A
    # SUBPROCESS over the real sources, so no in-memory mutant reaches it --
    # which is why the two checks above exist rather than this one alone.
    script = os.path.join(_TMP, "canvas_drive.py")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(_CANVAS_DRIVER % {"gui": _GUI, "body": _OPEN, "far": _FAR,
                                   "segs_body": "61",
                                   "segs_far": _ids(FAR_IDS),
                                   "said": "not a closed loop"})
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run([sys.executable, script], capture_output=True,
                          text=True, env=env, timeout=300)
    ok_c = proc.returncode == 0 and "CANVAS-OK" in proc.stdout
    check(ok_c, "4c. a real headless AppController refuses the run, leaves the "
                "offending curve highlighted on the mesh canvas, and takes the "
                "highlight back off once the drawing is fixed (%s)"
                % " | ".join(proc.stdout.strip().splitlines()[-2:])
                or proc.stderr[-120:])
    return ok_a and ok_b and ok_c


#: Driven in a subprocess: this gate is Qt-free and an `AppController` is not.
#: It asserts the three things a host owes a refusal — the run does not start,
#: the message reaches the user log, and the canvas is left holding the curve.
#: Driven in a subprocess: this gate is Qt-free and an `AppController` is
#: not. It asserts the three things a host owes a refusal -- the run does
#: not start, the message reaches the user log, and the canvas is left
#: holding the curve.
_CANVAS_DRIVER = r'''
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, %(gui)r)
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController
c = AppController()
mw = c.main_window
cfg = mw.mesh_config_panel.get_config()
cfg.mesh_mode = 1
cfg.set_geom_files([%(body)r, %(far)r])
cfg.bl_initial_thickness = 0.001
t = cfg.topology
t.family = "ogrid"
t.ogrid_body_geom = %(body)r; t.ogrid_body_segs = %(segs_body)r
t.ogrid_far_geom = %(far)r;   t.ogrid_far_segs = %(segs_far)r
t.ogrid_splits = 1; t.ogrid_cell = 0.2
# The config is handed to the controller directly rather than through the panel:
# what is under test is the ORDER of the mesh stage's own pre-flight, not the
# panel's round trip, which `test_topology_persistence.py` owns.
c.config_from_panel = lambda name: cfg
c._find_mesh_gen_executable = lambda: os.path.abspath(__file__)
started = []
import app.controllers.mesh_gen_ctrl as mg
class _Boom:
    def __init__(self, *a, **k):
        started.append(a)
        raise AssertionError("the mesher worker was built")
mg.MeshGenWorker = _Boom
said = []
c.log_report = lambda m: said.append(m)
c.run_mesh_generator()
mc = mw.mesh_canvas_view
item = getattr(mc, "_seg_highlight_item", None)
pts = item.getData() if item is not None else (None, None)
drawn = item is not None and pts[0] is not None and len(pts[0]) >= 3
# AND IT COMES BACK OFF once the drawing is fixed: a refusal left on the canvas
# points at a curve that is now fine, which is worse than no overlay. Asked at
# the guard rather than through `run_mesh_generator`, which would go on to build
# a worker -- the ordering above is what that entry point is here to show.
good = cfg.__class__()
good.mesh_mode = 0
good.set_geom_files([%(far)r])
cleared = (c._topology_preflight_refused(good) is False
           and getattr(mc, "_seg_highlight_item", None) is None)
ok = (not started and any(%(said)r in s for s in said) and drawn and cleared)
print("started=%%d said=%%d highlighted=%%s cleared=%%s"
      %% (len(started), len(said), None if pts[0] is None else len(pts[0]),
         cleared), flush=True)
print("CANVAS-OK" if ok else "CANVAS-BAD " + repr(said[:1]), flush=True)
sys.stdout.flush()
os._exit(0 if ok else 1)
'''


# ── 5. the registry enforces that a family HAS a refusal ────────────────────

def check_5(w):
    try:
        w.Family("x", "X", lambda m, c: {}, "x_")
        ok_a = False
    except TypeError:
        ok_a = True
    check(ok_a, "5a. a Family built with a build function and NO refusal does "
                "not construct")

    bad = []
    for fam in w.FAMILIES:
        if not callable(getattr(fam, "preflight", None)):
            bad.append("%s has no callable refusal" % fam.name)
            continue
        rows = fam.preflight(MeshConfig().topology, None)
        if not isinstance(rows, tuple) or any(
                not isinstance(r, w.topology_preflight.Refusal) for r in rows):
            bad.append("%s's refusal does not answer in Refusal rows" % fam.name)
    check(not bad, "5b. every registered family's refusal is callable and "
                   "answers in Refusal rows%s"
                   % ("" if not bad else " -- " + "; ".join(bad)))

    #: A family whose refusal always answers `()` passes 5a and 5b and is
    #: exactly the hole the acceptance criterion names, so the table above is
    #: compared with the registry in BOTH directions and every entry is driven.
    registered = {f.name for f in w.FAMILIES}
    silent = {name for name in registered
              if not w.preflight_for_config(CASES[name][1])} if (
        registered <= set(CASES)) else set()
    ok_c = registered == set(CASES) and not silent
    check(ok_c, "5c. every registered family -- and only those -- is driven "
                "here, and every one really refuses something (registry %s, "
                "table %s, silent %s)"
                % (sorted(registered), sorted(CASES), sorted(silent)))
    return ok_a and not bad and ok_c


# ── 6. the gap that bought containment ─────────────────────────────────────

def check_6(w):
    cfg = ogrid(body=_POKE_BODY, far=_POKE_FAR)
    ctx = topology_binding.context_for_config(cfg)
    body_r = ctx.geometry(_POKE_BODY).equivalent_radius()
    far_r = ctx.geometry(_POKE_FAR).equivalent_radius()
    ok_a = body_r < far_r
    check(ok_a, "6a. the EQUIVALENT-RADIUS nesting both ring families use "
                "accepts this drawing (body %.4f < far field %.4f), so the "
                "refusal below is a gap it could not see" % (body_r, far_r))

    rows = w.preflight_for_config(cfg)
    ok_b = (len(rows) == 1 and rows[0].geom == _POKE_BODY
            and "outside the far field" in rows[0].text())
    check(ok_b, "6b. containment refuses it and names the body: %r"
                % (rows[0].text()[:100] if rows else None))

    # The MARKED point really is outside the far field, re-derived here rather
    # than trusted: a coordinate nobody measured is a label, not evidence.
    at = rows[0].at if rows else None
    ring = w.topology_preflight.drawn_ring(ctx.geometry(_POKE_FAR))
    inside = False
    if at is not None:
        x, y = at
        for k in range(len(ring)):
            x0, y0 = ring[k]
            x1, y1 = ring[(k + 1) % len(ring)]
            if ((y0 > y) != (y1 > y)
                    and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0)):
                inside = not inside
    ok_b2 = at is not None and not inside and abs(at[0]) > 1.0
    check(ok_b2, "6b2. the point it marks (%s) really lies outside the far "
                 "field, measured here rather than quoted" % (at,))

    # 6c. the mesher's own answer to the document this would have produced.
    if not os.path.exists(_MESHER):
        print("SKIP 6c (no %s -- run ./build.sh)" % _MESHER, flush=True)
        return ok_a and ok_b and ok_b2
    run_dir = os.path.join(_TMP, "mesher6c")
    os.makedirs(run_dir, exist_ok=True)
    doc = w.build_document(cfg.topology, ctx)
    doc_path = os.path.join(run_dir, "topo.json")
    with open(doc_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=2) + "\n")
    run_cfg = copy.deepcopy(cfg)
    run_cfg.topology.family = ""
    run_cfg.mesh_topology_file = doc_path
    run_cfg.output_filename = os.path.join(run_dir, "out.vtk")
    run_cfg.export_vtk = True
    dat = os.path.join(run_dir, "case.dat")
    run_cfg.save_to_file(dat)
    with open(dat, "a", encoding="utf-8") as fh:
        fh.write(NO_SMOOTH)
    # Run from the REPO ROOT: `save_to_file` writes a geometry entry relative to
    # it, and the mesher resolves one against its own working directory. From
    # anywhere else the two outlines do not load and the refusal that comes back
    # is about an unreadable file rather than about the block that folds --
    # which is the shape this check would have passed on while measuring
    # nothing.
    proc = subprocess.run([_MESHER, "-conf", dat], capture_output=True,
                          text=True, cwd=_REPO, env=mesher_env(), timeout=300)
    said = proc.stdout + proc.stderr
    ok_c = proc.returncode != 0 and "HYBMESH_ERROR" in said
    check(ok_c, "6c. the REAL mesher refuses the document this drawing would "
                "have produced (exit %d), which is what the refusal above "
                "moves forward" % proc.returncode)
    ok_d = ok_c and ("block" in said and "wind" in said)
    check(ok_d, "6d. ...and it says so for a DEVELOPER -- a block id and a "
                "winding -- which is why an exit code is not the answer the "
                "ticket asks for")
    # 6e. THE SAME GAP IN THE TWO-RING FAMILY, which nests THREE outlines by the
    # same area-derived ruler. The seam here is long and thin: its equivalent
    # radius sits neatly between the body's and the far field's, so the ordering
    # holds, while it crosses the body on two sides.
    thin = write_box(os.path.join(_TMP, "thin_seam"), 3.0, 0.15, list(SEAM_IDS))
    tr = tworing(seam=thin)
    tctx = topology_binding.context_for_config(tr)
    radii = [tctx.geometry(g).equivalent_radius()
             for g in (_BODY, thin, _FAR)]
    rows = w.preflight_for_config(tr)
    ok_e = (radii[0] < radii[1] < radii[2] and len(rows) == 1
            and "outside the seam" in rows[0].text())
    check(ok_e, "6e. the two-ring family's three outlines nest by the same "
                "ruler (%.4f < %.4f < %.4f, which holds) and containment "
                "catches the seam crossing the body: %r"
                % (radii[0], radii[1], radii[2],
                   rows[0].text()[:80] if rows else None))
    return ok_a and ok_b and ok_b2 and ok_c and ok_d and ok_e


# ── 8. every problem at once ───────────────────────────────────────────────

def check_8(w):
    cfg = ogrid(body=_OPEN, ogrid_body_segs="61", far=_OPEN)
    rows = w.preflight_for_config(cfg)
    text = w.topology_preflight.refusal_text(rows)
    ok = (len(rows) == 2
          and text.count("not a closed loop") == 2)
    check(ok, "8. a drawing with TWO curves wrong is refused for both in ONE "
              "message, never the first only (%d rows, %d named)"
              % (len(rows), text.count("not a closed loop")))
    return ok


# ── 9. the case-type host refuses a confirmed WRONG role ───────────────────

_APPLY_HOST = os.path.join(_REPO, "tools", "PreProcessor", "apply_case_type.py")


def check_9(_w):
    """#164's named blind spot, closed: a role the operator CONFIRMED can still
    be the wrong curve, and only the family notices.

    A SUBPROCESS, so no in-memory mutant reaches it — which is why it is scored
    but not counted under `others_green`. It swaps the two roles, confirms both
    guesses away by naming the curves outright, and requires the host to exit 1
    with the family's sentence and to write nothing.
    """
    from app.services import case_type as case_type_mod
    env = dict(os.environ)
    env["PYTHONPATH"] = _GUI + os.pathsep + env.get("PYTHONPATH", "")
    tmp = os.path.join(_TMP, "host9")
    os.makedirs(tmp, exist_ok=True)
    ct_path = os.path.join(tmp, "ct.casetype.json")
    case_type_mod.save(case_type_mod.CaseType(
        "demo", "quad_midline_ratio",
        fields={"mesh_mode": 1, "bl_initial_thickness": 0.001,
                "export_vtk": True, "topology.family": "ogrid",
                "topology.ogrid_splits": 1, "topology.ogrid_cell": 0.2}),
        ct_path)
    op = drawing([_BODY, _FAR], "")
    op_case = os.path.join(tmp, "op_case.dat")
    op.save_to_file(op_case)
    out = os.path.join(tmp, "fitted.dat")
    proc = subprocess.run(
        [sys.executable, _APPLY_HOST, ct_path, "--to", op_case,
         "--confirm", "bl_initial_thickness",
         # SWAPPED on purpose: the far field named as the body and the body as
         # the far field. Every id resolves, both roles are answered, and
         # nothing before #165 had anything to say about it.
         "--role", "body=%s" % _FAR, "--role", "farfield=%s" % _BODY,
         "--out", out],
        capture_output=True, text=True, cwd=_REPO, env=env, timeout=300)
    said = proc.stdout + proc.stderr
    ok = (proc.returncode == 1 and "outside the far field" in said
          and not os.path.exists(out))
    check(ok, "9. the case-type host refuses a CONFIRMED but swapped role "
              "assignment, naming the curve, and writes nothing (exit %d, "
              "wrote=%s)" % (proc.returncode, os.path.exists(out)))
    return ok


# ── 7. Qt-free ─────────────────────────────────────────────────────────────

def check_7(_w):
    code = ("import sys; sys.path.insert(0, %r);"
            "from app.services import topology_preflight, topology_model;"
            "mods=[m for m in sys.modules if m.startswith(('PyQt','PySide'))];"
            "print(mods)" % _GUI)
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=_REPO, timeout=300)
    ok = proc.returncode == 0 and proc.stdout.strip() == "[]"
    check(ok, "7. the refusal service and the registry import with no Qt "
              "(%s)" % (proc.stdout.strip() or proc.stderr[-120:]))
    return ok


CHECKS = {1: check_1, 2: check_2, 3: check_3, 4: check_4, 5: check_5,
          6: check_6, 7: check_7, 8: check_8, 9: check_9}
#: Subprocess-only halves no in-memory mutant reaches, so a verdict about them
#: under mutation is evidence of nothing: check 7 and check 9 run child
#: processes over the REAL sources. They are still run (a stray there would be
#: a genuine breakage) and are simply never counted as a stray.
_NO_MUTANT = (7, 9)


def run_all(w, quiet=False):
    """Run every check against `w`; return {number: passed}."""
    global _QUIET
    was, _QUIET = _QUIET, quiet
    try:
        return {num: bool(fn(w)) for num, fn in CHECKS.items()}
    finally:
        _QUIET = was


# ── the real world ─────────────────────────────────────────────────────────

print("--- the committed service ---", flush=True)
_REAL = world()
_BASE = run_all(_REAL)


# ── injections ─────────────────────────────────────────────────────────────

def mutate(short, old, new):
    """One source with `old` replaced, asserting the replacement really bit."""
    name = next(n for n, _ in _RELS if n.endswith("." + short))
    src = _SRC[name]
    assert old in src, "injection anchor not found in %s: %r" % (short, old[:60])
    return src.replace(old, new, 1)


def injected(label, mutants, reddens, note):
    """Run every check against a mutant; the named ones must fail, others not.

    `others_green` is the half that makes an injection evidence rather than a
    coincidence: a mutation that reddens six checks has shown only that it broke
    something.
    """
    print("--- injection %s: %s ---" % (label, note), flush=True)
    w = world(**mutants)
    got = run_all(w, quiet=True)
    want = set(reddens)
    red = {n for n, ok in got.items() if not ok}
    skipped = {n for n in _NO_MUTANT}
    check(want <= red,
          "injection %s. the named check(s) %s go RED (red: %s)"
          % (label, sorted(want), sorted(red)))
    stray = (red - want) - skipped
    check(not stray,
          "injection %s. and no other check moves (stray: %s)"
          % (label, sorted(stray)))


injected(
    "A",
    {"topology_preflight": mutate(
        "topology_preflight",
        "    out = outside_point(drawn_ring(outer), inner)\n"
        "    if out is None:\n        return None",
        "    out = outside_point(drawn_ring(outer), inner)\n"
        "    if True:\n        return None")},
    [6],
    "containment stops looking, and the drawing that folds the mesher is "
    "accepted again")

injected(
    "B",
    {"topology_preflight": mutate(
        "topology_preflight",
        "    return Refusal(why, geom=(g.spelling if g is not None "
        "else str(name or \"\")))",
        "    return Refusal(why)")},
    [4],
    "the outline refusal drops the geometry, so the sentence survives and the "
    "canvas has nothing to point at")

injected(
    "C",
    {"topology_hgrid": mutate("topology_hgrid",
                              "    out = []\n    nx, ny = int(model.hgrid_nx)",
                              "    return ()\n    nx, ny = int(model.hgrid_nx)")},
    [1, 5],
    "the H-grid's refusal answers 'nothing is wrong' to every drawing, which "
    "is the shape a family with no refusal would have")

injected(
    "D",
    {"topology_preflight": mutate(
        "topology_preflight",
        '    return head + "\\n" + "\\n".join("  - " + r.text() for r in rows)',
        '    return head + "\\n" + "  - " + rows[0].text()')},
    [8],
    "the message reports only the first refusal, so the operator repairs their "
    "drawing one run at a time")

injected(
    "E",
    {"topology_preflight": mutate(
        "topology_preflight",
        '        return f"{where}{self.what}{tail}"',
        '        return f"[{self.family}] {where}{self.what}{tail}"')},
    [3],
    "the refusal names the family, putting an internal identifier in a "
    "sentence written for an operator")

print("--- injection F: negative control ---", flush=True)
_CTRL = world()
_CTRL_RESULT = run_all(_CTRL)
check(all(_CTRL_RESULT.values()) and all(_BASE.values()),
      "injection F. negative control: the real, unmutated service passes every "
      "check, so the failures above are the mutations and not the checker")

# ENDS IN `os._exit`, like every script here whose SOURCE mentions a QApplication.
# This one builds none — the canvas drive is a child process — but `_CANVAS_DRIVER`'s
# text does, and `test_qt_teardown_exit.py` reads source text rather than imports. An
# exemption there would be a hole in a gate that exists because five scripts quietly
# did not follow the house style; ending the same way costs nothing and keeps the
# population it counts honest. The flush is that gate's check 2: `os._exit` skips the
# one a normal exit does, and `run_all.sh` redirects stdout to a file.
if _FAILS:
    print("\nRESULT: %d FAILED" % len(_FAILS), flush=True)
    sys.stdout.flush()
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
sys.stdout.flush()
os._exit(0)
