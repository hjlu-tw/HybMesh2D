#!/usr/bin/env python3
"""THE HYBRID FALLBACK: a shape no family covers is a downgrade, not a dead end.

Issue #167, parent #158. #165 gave every topology family a pre-flight refusal in
the operator's own terms, which closed one hole and opened another: an operator
whose drawing no family can fill was left holding a sentence and nothing to
press. This ticket offers them the HYBRID path instead — boundary-layer quads
grown off their curves, Gmsh triangles filling the far field — explicitly, never
silently, and carrying no verdict from a case type whose thresholds were
measured on structured quads.

THE DRAWING THIS GATE IS BUILT ON IS THE MOTIVATING ONE, not a contrivance: a
NACA 0012 section drawn with a BLUNT trailing edge. The CAD stage emits it as
three segments — upper surface, lower surface and the base between them — so its
two surfaces never meet and there is no single trailing-edge corner for four
C-grid blocks to share. MEASURED here: the structured run cannot even be
WRITTEN (the document cannot be built, so `save_to_file` raises before any
mesher starts), while the fallback meshes it to completion. That is the ticket's
whole claim in one drawing.

WHY THE TRIGGER IS THE FAMILY IN FORCE AND NOT A SURVEY OF ALL FOUR. The
criterion says "when every family refuses" and the first design read it
literally. It cannot work, and the reason is measured rather than argued: the
H-GRID BINDS TO NOTHING (`Family.binds` is False for it), its refusals are about
its own parameter rows, and it therefore ACCEPTS every drawing in this repo —
including one it would mesh as a bare rectangle of blocks ignoring the body
entirely. A survey would have found an accepting family every time, "every
family refuses" would never have been true, and the fallback would never have
been offered at all. Check 1d measures that acceptance rather than asserting it.
The other three are no better as witnesses: an unconfigured family refuses
because its bindings are empty, which is a fact about the configuration and not
about the shape. The operator picked one case type naming one family; that
family refusing IS "no family applies" in the world they are in.

What this pins down:

  1. THE OFFER IS MADE, AND IT CARRIES ITS REASON. The real pre-flight is driven
     on the blunt section with `confirm` replaced by a recorder: it is asked
     exactly once, the question quotes the refusal VERBATIM, and it says both
     that the mesh will not be structured and that no verdict will be issued.
     1b: a drawing the family accepts asks nothing. 1c: a refusal the hybrid
     path could not mesh either (`MESH_MODE 1` with an empty geometry list,
     which is legal there) asks nothing and still blocks, naming why. 1d: the
     H-grid accepts the blunt section, which is why there is no survey.
  2. IT RUNS ONLY AFTER THE OPERATOR ACCEPTS. Declining blocks the run and
     leaves no fallback. With the REAL `confirm` — headless, nobody to ask — the
     answer is no, so an unattended GUI refuses rather than substituting a mesh
     of a different kind. The headless pipeline is untouched: its one question,
     `topology_model.mesh_preflight`, still refuses, and `pipeline_runner.py`
     names this service nowhere.
  3. THE RUN THE MESHER IS HANDED IS THE HYBRID ONE, through `mesher_config` —
     the one transformation the fingerprint is taken over, so a fallback run and
     a structured run of the same panel configuration cannot read as the same
     generation. 3b measures why the FAMILY is cleared and not only the mode:
     `save_config_to_file` projects a named family's document whatever the mode
     is, so a mode-only downgrade raises in the config WRITER, before the mesher
     it is downgrading to is ever launched.
  4. THE DOWNGRADE REALLY PRODUCES A MESH. The structured run of this drawing
     cannot be written at all; the fallback runs the real binary to completion
     and leaves the `.vtk`, the STAR-CD triple and a `.provenance.json`. Needs a
     build tree.
  5. NO VERDICT IS ISSUED FROM THE CASE TYPE'S THRESHOLDS, AND THE REASON IS
     STATED. With a case type in play whose bound this mesh would miss,
     `judge_run` on a fallback returns no verdict, says why at WARNING, and
     never reaches `case_type_verdict.run_verdict` at all — instrumented, not
     inferred. 5b is the same call without the fallback, which DOES judge, so 5
     is not vacuously true.
  6. THE COMMITTED CASE IS LABELLED AND CARRIES ITS OWN PROVENANCE. A real
     commit leaves `<stem>.fallback.json` saying `structured: false`, naming the
     family and quoting the refusal, beside a byte-identical copy of every mesh
     format and the mesher's own provenance sidecar — and NO `.casetype.json`
     and NO `.verdict.json`. 6b: the three slots are RECONCILED in both
     directions, so neither kind of record can outlive the mesh it describes.
  7. A FOLDED FALLBACK MESH IS STILL REFUSED. `EXIT_ERR_INVERTED` needs no case
     type behind it (ADR-0002), and a downgrade does not buy an exemption:
     nothing is written.
  8. THE COMMITTED SCRIPT DESCRIBES THE RUN THAT HAPPENED. `_commit_trial` hands
     the ONE builder a hybrid mesh configuration, so the script beside a
     fallback mesh reproduces it instead of being refused by the family the
     moment anyone runs it.
  9. THE ACCEPTANCE IS KEYED ON ITS REASON. The same unchanged refusal is not
     re-asked but IS said again every run; a different refusal is re-asked; the
     family coming to accept the drawing drops the fallback; and so does
     switching the panel to the hybrid path, which `_settle_fallback` catches
     on a Generate that runs no pre-flight of its own.
 10. THE ORDINARY PATHS ARE UNCHANGED. A hybrid-mode configuration reaches no
     offer, `mesher_config` leaves it alone, `judge_run` with no fallback still
     judges, and an unjudged commit leaves NO sidecar — checked over a case
     that already holds a fallback record, because over a fresh directory it
     passed on nothing (a review axis measured exactly that: deleting the
     `.fallback.json` argument from the unjudged `_remove_stale` reddened
     nothing at all).
 11. `services/mesh_fallback` IS QT-FREE, in a subprocess.

Known blind spots, named rather than papered over:
  - "The existing hybrid path's behaviour is unchanged" is held here at the GUI
    level (check 10) and NOT by `golden_mesh.py`, which belongs to the mesher.
    No C++ was touched by this ticket; the comparator was run by hand for the
    record and the result is in `docs/design_notes/gui.md`. A gate that ran it
    would be timing 21 mesher cases to prove something no edit here can reach.
  - Checks 1-3 and 6-10 drive the REAL controller methods against a recording
    stand-in for the main window. That the question is a real modal box on a
    real screen is nobody's check here; `confirm` is `app/utils.py`'s and is
    the same helper every other prompt in this tree goes through.
  - Nothing here judges the QUALITY of a fallback mesh. That is the point: the
    thresholds do not apply to it, and the mesher's own figures are
    `test_mb_quality` / the hybrid banner's subject.
  - The acceptance lives for the session. A fallback mesh committed yesterday
    and a Trial today are two separate acceptances, and nothing reads the
    `<stem>.fallback.json` of a case being reopened.

INJECTIONS — AUTOMATED, by exec'ing a mutated copy of `services/mesh_fallback.py`
and re-running the same check functions against it. Each asserts the named check
fails AND that no other check moves:

  A. `as_hybrid` leaving the FAMILY in place -> checks 3, 4 and 8 fail: the
     config writer projects the family's document whatever the MODE says, so
     the run dies before the mesher it was downgrading to. Three, measured
     rather than narrowed to one — 3b names the writer, 4 is the mesh that
     never arrives, 8 is the script the committed case would carry.
  B. `as_hybrid` leaving the MODE at multi-block -> checks 1, 2, 3, 4, 8 and 9
     fail. IT CASCADES, and the cascade is the design: `unavailable_because` asks
     `missing_mesh_input` about the configuration `as_hybrid` produces, so one
     definition of what the fallback run IS serves both the offer and the run.
     Check 3a is the one that names the mode itself.
  C. `unavailable_because` always answering "" -> check 1 fails: a downgrade offered for
     a configuration the hybrid path cannot mesh either, spending the
     operator's acceptance on a run that cannot succeed.
  D. the not-structured CLAUSE reworded out of the sentence -> checks 1, 2, 5,
     6 and 9 fail — the label's four homes, which is the enumerated list in
     `services/mesh_fallback.py` doing its job. A FIRST ATTEMPT emptied the
     constant instead and reddened NOTHING: every check asked
     `w.NOT_STRUCTURED in text`, and the empty string is a substring of
     everything. `says_not_structured` is what closed that, by asking for the
     criterion's own words as well as the module's sentence.
  E. `fallback_record` claiming the mesh IS structured -> check 6 fails.
  F. `accepted` dropping the reason -> checks 2 and 9 fail: an acceptance keyed
     on nothing is an acceptance that never expires.
  G. negative control: the unmutated module passes every check.
  H. the offer ACCEPTED WITHOUT ASKING -> check 2 fails, ALONE. Not a source
     mutation: the rule lives in the controller, and the defect is a `confirm`
     whose answer is recorded and then ignored — which is exactly what
     "silently substituted" looks like from inside the host. It reddens one
     check because check 1 deliberately asks only whether the question was put
     and what it said, never what the answer then decided.
  I. `_remove_stale` never reaching the `.fallback.json` slot -> checks 6 and
     10 fail: a committed case keeps the record of a mesh it no longer holds.
     A LEVER on the real `mesh_commit` rather than a source mutation, because
     that file's mutant harness is `test_mesh_trial_commit.py`'s and a second
     copy of it here would be the duplication this repo's own rules refuse.
  J. `commit_refusal` reading "no verdict" as "nobody to refuse" -> check 7
     fails, alone. #166's own shipped defect arriving in the fallback's shape:
     a fallback mesh has NO verdict by construction, so this is precisely
     where that reading would come back and let a folded one into the case.

Run:  python3 tools/PreProcessor/tests/test_mesh_fallback.py
Needs a build tree for check 4 alone. Checks 6-8 drive the real commit over
SYNTHETIC trial bytes — `commit` copies and never reads a mesh — so the one
check that needs a real mesher is the one whose claim is that a real mesher
produces a mesh here.
"""
import ast
import importlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _p in (_GUI, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# A real QApplication, offscreen. `app/utils.is_headless` asks the LIVE
# application for its platform name, so with none running it answers False and
# `confirm` really builds a QMessageBox — which would block check 2 forever.
from PyQt6.QtWidgets import QApplication            # noqa: E402
_APP = QApplication.instance() or QApplication([])

from topology_outline_fixture import write_airfoil   # noqa: E402
from app.models.mesh_config import MeshConfig        # noqa: E402
from app.services import case_type as case_type_mod  # noqa: E402
from app.services import topology_model              # noqa: E402

_FALLBACK_REL = "tools/PreProcessor/gui/app/services/mesh_fallback.py"
_NAME = "app.services.mesh_fallback"
#: Every module that did `from app.services import mesh_fallback` and so holds
#: the module OBJECT rather than a lookup. `sys.modules` alone does not reach
#: them, which is the shadowing #160 measured.
_BINDERS = ("app.services.mesh_commit",
            "app.controllers.mesh_gen_diag_ctrl",
            "app.controllers.mesh_dispose_ctrl")

_MESHER = os.path.join(_REPO, "build", "HybMesh2D")
_HAVE_BIN = os.path.isfile(_MESHER)

_FAILS = []
#: True while a MUTANT is being scored: a sub-check failing then is the
#: injection working, so it is shown and not counted.
_QUIET = False


def check(cond, msg):
    if _QUIET:
        print(("   . " if cond else "   x ") + msg, flush=True)
        return bool(cond)
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)
    return bool(cond)


def _read(rel):
    with open(os.path.join(_REPO, rel), encoding="utf-8") as fh:
        return fh.read()


_SRC = _read(_FALLBACK_REL)
_RUNNER_SRC = _read("tools/PreProcessor/gui/app/services/pipeline_runner.py")
_DISPOSE_SRC = _read("tools/PreProcessor/gui/app/controllers/mesh_dispose_ctrl.py")


def world(src=None):
    """A `mesh_fallback` module built from the given source, BOUND everywhere.

    Returns `(module, restore)`. The binding is what makes an injection real:
    the service is reached by three modules that hold the object, plus the
    package attribute `from app.services import mesh_fallback` resolves through
    first, and a mutant left only in `sys.modules` would be shadowed by the
    module the gate is supposed to be replacing.
    """
    import app.services                                    # noqa: F401
    pkg = sys.modules["app.services"]
    for name in _BINDERS:
        importlib.import_module(name)
    saved = {name: sys.modules[name].mesh_fallback for name in _BINDERS}
    saved_pkg = getattr(pkg, "mesh_fallback", None)
    saved_mod = sys.modules.get(_NAME)

    spec = importlib.util.spec_from_loader(_NAME, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = os.path.join(_REPO, _FALLBACK_REL)
    sys.modules[_NAME] = mod
    setattr(pkg, "mesh_fallback", mod)
    try:
        exec(compile(src or _SRC, mod.__file__, "exec"), mod.__dict__)
    finally:
        sys.modules[_NAME] = saved_mod if saved_mod is not None else mod
    for name in _BINDERS:
        sys.modules[name].mesh_fallback = mod

    def restore():
        for name, old in saved.items():
            sys.modules[name].mesh_fallback = old
        if saved_pkg is None:
            if hasattr(pkg, "mesh_fallback"):
                delattr(pkg, "mesh_fallback")
        else:
            setattr(pkg, "mesh_fallback", saved_pkg)
        if saved_mod is None:
            sys.modules.pop(_NAME, None)
        else:
            sys.modules[_NAME] = saved_mod

    return mod, restore


# --- the drawings -------------------------------------------------------------
_TMP = tempfile.mkdtemp(prefix="fallback_")
SHARP_IDS = (71, 72)
BLUNT_IDS = (71, 72, 73)

#: A section a C-grid CANNOT fill: drawn blunt, so the CAD emits three segments
#: and the two surfaces never meet at a shared trailing-edge corner.
_BLUNT = write_airfoil(os.path.join(_TMP, "blunt"), list(BLUNT_IDS),
                       ["wall"] * 3, sharp_te=False)
#: The same section drawn SHARP, which the same family accepts — so check 1b is
#: a property of the drawing rather than of the gate.
_SHARP = write_airfoil(os.path.join(_TMP, "sharp"), list(SHARP_IDS),
                       ["wall"] * 2, sharp_te=True)


def drawing(section, segs):
    """A `MeshConfig` for `section`, on the SHIPPED hybrid parameters.

    `config/Background_para.dat` rather than a bare `MeshConfig()`: the fallback
    has to produce a real mesh, which needs a domain box and boundary-layer
    parameters somebody has actually run. A gate that invented them would be
    proving the hybrid path works on numbers nobody ships.
    """
    cfg = MeshConfig()
    cfg.load_from_file(os.path.join(_REPO, "config", "Background_para.dat"))
    cfg.set_geom_files([section])
    cfg.mesh_mode = 1
    cfg.topology.family = "cgrid"
    cfg.topology.cgrid_body_geom = section
    cfg.topology.cgrid_body_segs = ",".join(str(s) for s in segs)
    return cfg


def no_geometry():
    """`MESH_MODE 1` with an EMPTY geometry list, which is legal there.

    A topology may declare every one of its own corners, so this is a real
    configuration and not a broken one — and it is the state in which a hybrid
    fallback has nothing to grow a boundary layer from.
    """
    cfg = MeshConfig()
    cfg.mesh_mode = 1
    cfg.topology.family = "hgrid"
    cfg.topology.hgrid_x_max = -1.0      # inside out: the H-grid refuses it
    return cfg


def hybrid_drawing():
    cfg = drawing(_SHARP, SHARP_IDS)
    cfg.mesh_mode = 0
    return cfg


# --- the host: the REAL controller, with a recording main window --------------
class _Any:
    def __getattr__(self, name):
        if name == "get_log_text":
            return lambda: ""
        return _Any()

    def __call__(self, *_a, **_k):
        return _Any()


class _Canvas:
    def __init__(self):
        self.highlights = []
        self.marks = []
        self.cleared = 0

    def highlight_segment(self, pts):
        self.highlights.append(pts)

    def clear_error_highlights(self):
        self.cleared += 1

    def highlight_self_intersection_point(self, x, y):
        self.marks.append((x, y))

    def __getattr__(self, _name):
        return lambda *a, **k: None


class _Win(_Any):
    def __init__(self):
        self.mesh_canvas_view = _Canvas()


class _Pipeline:
    def __init__(self):
        self.saved = []

    def save_to_file(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"name": "stub"}, fh)
        self.saved.append(path)


class _Asked:
    """A `confirm` that records what it was asked and answers a fixed way."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def __call__(self, parent, title, question, detail=None,
                 headless_default=True):
        self.calls.append((title, question, headless_default))
        return self.answer


def make_host(cfg, temp_dir, pipeline=None):
    from app.controllers.mesh_gen_ctrl import MeshGenControllerMixin

    class _Host(MeshGenControllerMixin):
        def __init__(self):
            self.main_window = _Win()
            self.global_mesh_config = cfg
            self.global_vtk_mesh = None
            self.global_vtk_path = ""
            self.temp_dir = temp_dir
            self._pending_after_mesh = None
            self._mesh_trial = None
            self._trial_fingerprint = ""
            self._commit_after_mesh = False
            self._mesh_fallback = None
            self._trial_fallback = None
            self.lines = []
            self.reports = []
            self.generations = []
            #: Every `mesh_cfg` the ONE pipeline builder was handed.
            self.pipeline_cfgs = []

        def log(self, message, level=None):
            self.lines.append(str(message))

        def log_report(self, message, level="ERROR"):
            self.reports.append((str(message), level))
            self.lines.append(str(message))

        def config_from_panel(self, _name):
            return self.global_mesh_config

        def build_pipeline_config(self, mesh_cfg=None):
            self.pipeline_cfgs.append(mesh_cfg)
            return pipeline

        def run_mesh_generator(self, *, commit=False):
            self.generations.append(commit)

    return _Host()


# --- a case type with a bound this mesh would miss ----------------------------
ADVICE = "Ask for a less aggressive first cell."


def write_case_type(path):
    doc = {"schema": case_type_mod.SCHEMA,
           "version": case_type_mod.SCHEMA_VERSION,
           "name": "Fallback test type", "metric": "quad_midline_ratio",
           "thresholds": [{"key": "max", "advice": ADVICE,
                           "attention": 0.0, "unusable": 1e9}]}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    return path


# --- a real fallback mesh -----------------------------------------------------
def make_fallback_mesh(w, stem):
    """Run the fallback configuration for the blunt section into `stem`.vtk."""
    from mesher_bin import mesher_env
    cfg = w.as_hybrid(drawing(_BLUNT, BLUNT_IDS))
    cfg.output_filename = stem + ".vtk"
    cfg.export_vtk = True
    cfg.export_starcd = True
    conf = stem + "_para.dat"
    cfg.save_to_file(conf)
    proc = subprocess.run([_MESHER, "-conf", conf], cwd=_REPO,
                          env=mesher_env(), capture_output=True, text=True,
                          timeout=600)
    return stem + ".vtk", proc


def snapshot(directory):
    out = {}
    for root, _dirs, files in os.walk(directory):
        for name in files:
            full = os.path.join(root, name)
            with open(full, "rb") as fh:
                out[os.path.relpath(full, directory)] = fh.read()
    return out


# ── injection H's lever ───────────────────────────────────────────────────────
#: When set, every offer is ACCEPTED whatever the operator answered — still
#: recorded, so only the checks about the ANSWER move. That is what "silently
#: substituted" looks like from inside the host.
_IGNORE_THE_ANSWER = False

#: THREE OF THE RULES LIVE IN `mesh_commit`, NOT IN `mesh_fallback`, so no
#: mutation of the module `world()` rebuilds can reach them. Rather than carry
#: a second mutant harness for a file `test_mesh_trial_commit.py` already owns,
#: each is injected as a LEVER on the real `mesh_commit` — which is how
#: `_IGNORE_THE_ANSWER` already handles the one rule that lives in the
#: controller. Set by `injected(..., lever=...)` and cleared in its `finally`.
_LEVERS = {}


def ask(host, cfg, answer, real=False):
    """Drive the real pre-flight with `confirm` answering `answer`.

    Returns `(blocked, recorder)`. The patch is on the controller module's own
    name, which is where the call actually resolves — `from app.utils import
    confirm` binds the function object at import time.
    """
    import app.controllers.mesh_gen_diag_ctrl as diag
    recorder = _Asked(answer)
    use = diag.confirm if real else recorder

    if _IGNORE_THE_ANSWER:
        inner = use

        def use(*a, **k):                                    # noqa: F811
            inner(*a, **k)
            return True

    saved, diag.confirm = diag.confirm, use
    try:
        return host._topology_preflight_refused(cfg), recorder
    finally:
        diag.confirm = saved


def _tmpdir():
    return tempfile.mkdtemp(dir=_TMP)


def pull_lever(name):
    """Install one `mesh_commit` lever; return the function that removes it.

    `"stale"` -- `_remove_stale` that never reaches the `.fallback.json` slot,
    so a commit of the other kind leaves the previous record standing beside a
    mesh it does not describe.
    `"norefuse"` -- `commit_refusal` reading "no verdict" as "nobody to refuse",
    which is #166's own shipped defect arriving in the fallback's shape: a
    fallback mesh HAS no verdict by construction, so this is where it would
    come back.
    """
    import app.services.mesh_commit as commit_mod
    if name == "stale":
        real = commit_mod._remove_stale

        def blind(*paths):
            return real(*[p for p in paths
                          if not p.endswith(".fallback.json")])

        commit_mod._remove_stale = blind
        return lambda: setattr(commit_mod, "_remove_stale", real)
    if name == "norefuse":
        verdict_mod = commit_mod.case_type_verdict
        real = verdict_mod.commit_refusal

        def lenient(verdict, exit_code=0):
            return "" if verdict is None else real(verdict, exit_code)

        verdict_mod.commit_refusal = lenient
        return lambda: setattr(verdict_mod, "commit_refusal", real)
    raise AssertionError("no such lever: %r" % (name,))


def says_not_structured(w, text):
    """True when `text` really carries the not-structured label.

    BOTH the module's own sentence AND the criterion's own words. The constant
    alone is not enough: emptied out it is a substring of everything, so a
    check written as `w.NOT_STRUCTURED in text` passes on a record that says
    nothing — measured, by an injection that reddened nothing. The phrase is
    the acceptance criterion's ("labelled as not structured"), so pinning it
    pins the criterion rather than this repo's prose.
    """
    return (bool(w.NOT_STRUCTURED) and w.NOT_STRUCTURED in text
            and "not structured" in text.lower())


def says_no_verdict(w, text):
    """The same, for "no verdict is issued ... and the reason is stated"."""
    return (bool(w.NO_VERDICT) and w.NO_VERDICT in text
            and "no verdict" in text.lower())


# ── checks ────────────────────────────────────────────────────────────────────
def check_1(w):
    """The offer is made, and it carries its reason."""
    out = []
    cfg = drawing(_BLUNT, BLUNT_IDS)
    from app.services.topology_preflight import refusal_text
    reason = refusal_text(topology_model.preflight_for_config(cfg))
    host = make_host(cfg, _tmpdir())
    blocked, asked = ask(host, cfg, False)
    if len(asked.calls) != 1:
        out.append("the offer was put %d time(s), not once" % len(asked.calls))
    else:
        title, question, default = asked.calls[0]
        if reason not in question:
            out.append("the question does not quote the refusal verbatim: %r"
                       % question[:160])
        if not says_not_structured(w, question):
            out.append("the question does not say the mesh is not structured")
        if not says_no_verdict(w, question):
            out.append("the question does not say no verdict will be issued")
        if default is not False:
            out.append("the offer's headless default is %r, so a host with "
                       "nobody to ask would substitute a mesh" % (default,))
        if "cgrid" in question or "cgrid" in title:
            out.append("the question names the family IDENTIFIER, which #165 "
                       "rules out of anything an operator reads")
    # What the ANSWER then decides is check 2's subject, deliberately: an
    # offer accepted without being consulted must redden exactly one check.
    # 1b. a drawing the family can fill is never asked about.
    ok_cfg = drawing(_SHARP, SHARP_IDS)
    ok_host = make_host(ok_cfg, _tmpdir())
    ok_blocked, ok_asked = ask(ok_host, ok_cfg, True)
    if ok_blocked or ok_asked.calls or ok_host._mesh_fallback is not None:
        out.append("1b: a drawing the C-grid accepts was offered a fallback "
                   "(blocked=%r asked=%d)" % (ok_blocked, len(ok_asked.calls)))
    # 1c. a refusal the hybrid path could not mesh either is NOT offered one.
    none_cfg = no_geometry()
    none_host = make_host(none_cfg, _tmpdir())
    none_blocked, none_asked = ask(none_host, none_cfg, True)
    if not w.unavailable_because(none_cfg):
        out.append("1c: `unavailable_because` says the hybrid path could mesh a "
                   "case "
                   "with no geometry at all")
    if none_asked.calls:
        out.append("1c: a fallback was offered for a case the hybrid path "
                   "cannot mesh either")
    if not none_blocked:
        out.append("1c: the run was not blocked")
    if not any("H-grid" in m or "Blocks in X" in m or "X Max" in m
               for m, _lvl in none_host.reports):
        out.append("1c: the operator was not told why, reports=%r"
                   % (none_host.reports,))
    # 1d. the measurement behind "no survey": the H-grid accepts this drawing.
    h_cfg = drawing(_BLUNT, BLUNT_IDS)
    h_cfg.topology.family = "hgrid"
    if topology_model.preflight_for_config(h_cfg):
        out.append("1d: the H-grid refused the blunt section, so the "
                   "no-survey argument in this gate's docstring is stale")
    return out


def check_2(w):
    """The fallback runs only after the operator accepts it."""
    out = []
    cfg = drawing(_BLUNT, BLUNT_IDS)
    from app.services.topology_preflight import refusal_text
    reason = refusal_text(topology_model.preflight_for_config(cfg))
    # 2a. declined.
    host = make_host(cfg, _tmpdir())
    blocked, _asked = ask(host, cfg, False)
    if not blocked:
        out.append("2a: the operator declined and the run went ahead anyway")
    if host._mesh_fallback is not None:
        out.append("2a: a declined offer left a fallback in force")
    if not any(w.DECLINED in line for line in host.lines):
        out.append("2a: a declined offer said nothing")
    # 2b. nobody to ask: the REAL confirm, headless.
    h2 = make_host(cfg, _tmpdir())
    blocked2, _ = ask(h2, cfg, None, real=True)
    if not blocked2 or h2._mesh_fallback is not None:
        out.append("2b: with nobody to ask, the run was not refused "
                   "(blocked=%r)" % (blocked2,))
    # 2c. the headless pipeline host is untouched.
    if topology_model.mesh_preflight(cfg) != reason:
        out.append("2c: the headless host's one question stopped refusing this "
                   "drawing")
    if "mesh_fallback" in _RUNNER_SRC:
        out.append("2c: `pipeline_runner.py` reaches the fallback service, so "
                   "an unattended run could substitute a mesh")
    # 2d. accepted.
    h3 = make_host(cfg, _tmpdir())
    blocked3, asked3 = ask(h3, cfg, True)
    if blocked3:
        out.append("2d: the operator accepted and the run was still blocked")
    fb = h3._mesh_fallback
    if fb is None:
        out.append("2d: an accepted offer recorded no fallback")
    else:
        if fb.reason != reason:
            out.append("2d: the acceptance records %r, not the refusal the "
                       "operator read" % (fb.reason[:80],))
        if fb.family != "cgrid":
            out.append("2d: the record names family %r" % (fb.family,))
        if not says_not_structured(w, fb.note()):
            out.append("2d: the per-run note does not say the mesh is not "
                       "structured")
    if not any(says_not_structured(w, m) and lvl == "WARNING"
               for m, lvl in h3.reports):
        out.append("2d: accepting was not reported at WARNING")
    if asked3.calls and asked3.calls[0][2] is not False:
        out.append("2d: the offer's headless default is not False")
    return out


def check_3(w):
    """The configuration the mesher is handed is the hybrid one."""
    out = []
    cfg = drawing(_BLUNT, BLUNT_IDS)
    host = make_host(cfg, _tmpdir())
    before = host.mesher_config(cfg)
    if int(before.mesh_mode) != 1 or before.topology.family != "cgrid":
        out.append("3a: the transformation touched a run with no fallback "
                   "(mode=%r family=%r)"
                   % (before.mesh_mode, before.topology.family))
    ask(host, cfg, True)
    after = host.mesher_config(cfg)
    if int(after.mesh_mode) != 0:
        out.append("3a: the mesher is still handed MESH_MODE %r"
                   % (after.mesh_mode,))
    if after.topology.family:
        out.append("3a: the mesher is still handed family %r"
                   % (after.topology.family,))
    if int(cfg.mesh_mode) != 1 or cfg.topology.family != "cgrid":
        out.append("3a: the PANEL's own configuration was mutated")
    # 3b. WHY the family is cleared and not only the mode, measured.
    probe = _tmpdir()
    mode_only = drawing(_BLUNT, BLUNT_IDS)
    mode_only.mesh_mode = 0
    raised = ""
    try:
        mode_only.save_to_file(os.path.join(probe, "mode_only.dat"))
    except Exception as exc:                    # noqa: BLE001 - measured
        raised = type(exc).__name__
    if not raised:
        out.append("3b: a mode-only downgrade wrote its config, so the reason "
                   "`as_hybrid` clears the family is no longer true")
    try:
        w.as_hybrid(drawing(_BLUNT, BLUNT_IDS)).save_to_file(
            os.path.join(probe, "hybrid.dat"))
    except Exception as exc:                    # noqa: BLE001 - measured
        out.append("3b: the fallback configuration could not be written: %r"
                   % (exc,))
    # 3c. the fingerprint tells the two runs apart. On the SHARP section, where
    # BOTH configurations are writable, so the difference is the downgrade and
    # not one of them failing.
    s_cfg = drawing(_SHARP, SHARP_IDS)
    s_host = make_host(s_cfg, _tmpdir())
    plain = s_host._fingerprint_of(s_cfg)
    s_host._mesh_fallback = w.Fallback("because.", "cgrid")
    downgraded = s_host._fingerprint_of(s_cfg)
    if not plain or not downgraded:
        out.append("3c: a fingerprint could not be taken at all")
    elif plain == downgraded:
        out.append("3c: a fallback run and a structured run of the same panel "
                   "configuration read as the same generation")
    return out


def check_4(w):
    """The downgrade really produces a mesh where the structured run cannot."""
    out = []
    # 4a. the structured run of this drawing is a DEAD END: its document cannot
    # be built, so the config is never even written and no mesher starts.
    raised = ""
    try:
        drawing(_BLUNT, BLUNT_IDS).save_to_file(
            os.path.join(_tmpdir(), "structured.dat"))
    except Exception as exc:                    # noqa: BLE001 - measured
        raised = str(exc)
    if not raised:
        out.append("4a: the structured run wrote a config, so this drawing is "
                   "not the dead end the fallback exists for")
    if not _HAVE_BIN:
        print("   (check 4b skipped: no build tree)", flush=True)
        return out
    vtk, proc = make_fallback_mesh(w, os.path.join(_tmpdir(), "fb"))
    if proc.returncode != 0:
        out.append("4b: the fallback run exited %d (%s)"
                   % (proc.returncode,
                      " ".join(proc.stdout.split())[-200:]))
    stem = os.path.splitext(vtk)[0]
    for ext in (".vtk", ".vrt", ".cel", ".bnd", ".provenance.json"):
        if not os.path.isfile(stem + ext):
            out.append("4b: the fallback left no %s" % ext)
    return out


def check_5(w):
    """No verdict from the case type's thresholds, and the reason is stated."""
    out = []
    import app.services.mesh_commit as commit_mod
    from app.services import case_type_verdict
    ct = write_case_type(os.path.join(_tmpdir(), "t.casetype.json"))
    calls = []
    real = case_type_verdict.run_verdict

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    cfg = drawing(_BLUNT, BLUNT_IDS)
    mesh = os.path.join(_tmpdir(), "m.vtk")
    with open(mesh, "w", encoding="utf-8") as fh:
        fh.write("# not a real mesh; nothing here reads it\n")
    saved_env = os.environ.get(case_type_mod.CASE_TYPE_ENV)
    case_type_verdict.run_verdict = counting
    os.environ[case_type_mod.CASE_TYPE_ENV] = ct
    try:
        fb = w.Fallback("the family refused.", "cgrid")
        trial = commit_mod.judge_run(mesh, 0, config=cfg, fallback=fb)
        if trial.verdict is not None:
            out.append("a fallback mesh was given a verdict")
        if calls:
            out.append("the thresholds were read at all (%d pass(es)) — they "
                       "are not merely ignored, they are never consulted"
                       % len(calls))
        if not says_not_structured(w, trial.report):
            out.append("the report does not say the mesh is not structured")
        if not says_no_verdict(w, trial.report):
            out.append("the report does not say why there is no verdict")
        if trial.level != "WARNING":
            out.append("the absent verdict is reported at %r" % (trial.level,))
        if trial.fallback is not fb:
            out.append("the trial does not carry its fallback")
        # 5b. the same call WITHOUT a fallback does judge, so 5 is not vacuous.
        del calls[:]
        plain = commit_mod.judge_run(mesh, 0, config=cfg)
        if plain.verdict is None or len(calls) != 1:
            out.append("5b: an ordinary run stopped being judged "
                       "(verdict=%r passes=%d)" % (plain.verdict, len(calls)))
        if plain.fallback is not None:
            out.append("5b: an ordinary run carries a fallback")
    finally:
        case_type_verdict.run_verdict = real
        if saved_env is None:
            os.environ.pop(case_type_mod.CASE_TYPE_ENV, None)
        else:
            os.environ[case_type_mod.CASE_TYPE_ENV] = saved_env
    return out


#: A SECOND blunt section, so check 9 can produce a DIFFERENT refusal without
#: changing what is wrong with the drawing: the sentence names the curve, so two
#: curves with the same defect are two distinct reasons to accept a downgrade.
_BLUNT2 = write_airfoil(os.path.join(_TMP, "blunt2"), list(BLUNT_IDS),
                        ["wall"] * 3, sharp_te=False)


def fake_trial(directory):
    """A generation's output files, with CONTENT nothing here parses.

    `commit` copies; it never reads a mesh. So checks 6-8 drive the real commit
    over synthetic bytes and stay runnable with no build tree, while check 4 is
    the one that proves a real mesher really produces a mesh for this drawing.
    """
    from app.services import case_sources
    stem = os.path.join(directory, "global_mesh")
    for ext in (".vtk", ".vrt", ".cel", ".bnd"):
        with open(stem + ext, "w", encoding="utf-8") as fh:
            fh.write("trial bytes for %s\n" % ext)
    prov = case_sources.mesh_provenance_paths(stem + ".vtk")[0]
    with open(prov, "w", encoding="utf-8") as fh:
        json.dump({"metric": "tri_edge_ratio"}, fh)
    return stem + ".vtk"


def a_verdict():
    """A real `Verdict` that does NOT refuse, for the reconciliation check."""
    from app.services import case_type_verdict
    ct = case_type_mod.load(write_case_type(
        os.path.join(_tmpdir(), "v.casetype.json")))
    return case_type_verdict.judge(ct, None, 0)


def check_6(w):
    """The committed case is labelled, and the three record slots reconcile."""
    out = []
    import app.services.mesh_commit as commit_mod
    src = fake_trial(_tmpdir())
    case = _tmpdir()
    dest = os.path.join(case, "mesh_case.vtk")
    reason = "this case cannot be meshed as it is drawn — the section is blunt."
    fb = w.Fallback(reason, "cgrid")
    trial = commit_mod.TrialMesh(src, 0, fallback=fb)
    written = commit_mod.commit(trial, dest, pipeline=_Pipeline(),
                                when="2026-10-07T00:00:00Z")
    stem = os.path.splitext(dest)[0]
    rec_path = stem + ".fallback.json"
    if not os.path.isfile(rec_path):
        out.append("the committed case carries no fallback record")
    else:
        rec = json.load(open(rec_path, encoding="utf-8"))
        if rec.get("structured") is not False:
            out.append("the record says structured=%r" % (rec.get("structured"),))
        if rec.get("refused_by", {}).get("family") != "cgrid":
            out.append("the record does not name the family that refused")
        if rec.get("refused_by", {}).get("reason") != reason:
            out.append("the record does not quote the refusal verbatim")
        # `ensure_ascii=False`: these sentences carry em dashes, and the
        # escaped form of one is not the sentence. A substring test against
        # `json.dumps`'s default found neither and said so, which is the check
        # failing rather than the record.
        flat = json.dumps(rec, ensure_ascii=False)
        if not says_not_structured(w, flat):
            out.append("the record never says the mesh is not structured")
        if not says_no_verdict(w, flat):
            out.append("the record never says why there is no verdict")
    for ext in (".casetype.json", ".verdict.json"):
        if os.path.isfile(stem + ext):
            out.append("a fallback case was given a %s" % ext)
    # the mesh itself, byte for byte, plus the mesher's own provenance.
    src_stem = os.path.splitext(src)[0]
    for ext in (".vtk", ".vrt", ".cel", ".bnd", ".provenance.json"):
        a, b = src_stem + ext, stem + ext
        if not os.path.isfile(b):
            out.append("the committed case is missing %s" % ext)
        elif open(a, "rb").read() != open(b, "rb").read():
            out.append("%s is not the trial's bytes" % ext)
    if stem + ".pipeline.json" not in written:
        out.append("no runnable script was left beside the fallback mesh")
    # 6b. reconciliation, BOTH directions.
    judged = commit_mod.TrialMesh(src, 0, verdict=a_verdict(),
                                  report="rendered verdict")
    commit_mod.commit(judged, dest, when="2026-10-07T00:00:01Z")
    if os.path.isfile(rec_path):
        out.append("6b: a verdict-bearing commit left the previous fallback "
                   "record standing beside a mesh it does not describe")
    for ext in (".casetype.json", ".verdict.json"):
        if not os.path.isfile(stem + ext):
            out.append("6b: an ordinary commit stopped writing %s" % ext)
    commit_mod.commit(commit_mod.TrialMesh(src, 0, fallback=fb), dest,
                      when="2026-10-07T00:00:02Z")
    for ext in (".casetype.json", ".verdict.json"):
        if os.path.isfile(stem + ext):
            out.append("6b: a fallback commit left the previous %s standing"
                       % ext)
    if not os.path.isfile(rec_path):
        out.append("6b: the fallback record did not come back")
    return out


def check_7(w):
    """A FOLDED fallback mesh is refused like any other."""
    out = []
    import app.services.mesh_commit as commit_mod
    from app.services.case_type_verdict import EXIT_ERR_INVERTED
    src = fake_trial(_tmpdir())
    case = _tmpdir()
    dest = os.path.join(case, "mesh_case.vtk")
    before = snapshot(case)
    fb = w.Fallback("the section is blunt.", "cgrid")
    trial = commit_mod.TrialMesh(src, EXIT_ERR_INVERTED, fallback=fb)
    try:
        commit_mod.commit(trial, dest, pipeline=_Pipeline())
        out.append("a folded fallback mesh was written into the case")
    except commit_mod.CommitRefused as exc:
        if str(EXIT_ERR_INVERTED) not in str(exc):
            out.append("the refusal does not name the exit code: %r" % str(exc))
    if snapshot(case) != before:
        out.append("the refused commit still wrote into the case")
    return out


def check_8(w):
    """The committed script describes the run that happened."""
    out = []
    src = fake_trial(_tmpdir())
    case = _tmpdir()
    cfg = drawing(_BLUNT, BLUNT_IDS)
    cfg.output_filename = os.path.join(case, "mesh_case.vtk")
    host = make_host(cfg, _tmpdir(), pipeline=_Pipeline())
    import app.services.mesh_commit as commit_mod
    fb = w.Fallback("the section is blunt.", "cgrid")
    host._commit_trial(commit_mod.TrialMesh(src, 0, fallback=fb))
    if len(host.pipeline_cfgs) != 1:
        out.append("the one builder was called %d time(s)"
                   % len(host.pipeline_cfgs))
    else:
        given = host.pipeline_cfgs[0]
        if given is None:
            out.append("the committed script describes the PANEL, so it would "
                       "be refused by the family the moment anyone ran it")
        else:
            if int(given.mesh_mode) != 0 or given.topology.family:
                out.append("the script's mesh section is mode=%r family=%r"
                           % (given.mesh_mode, given.topology.family))
    # an ordinary commit hands the builder no override at all: the parameter has
    # exactly one caller, which is what keeps it from becoming a second builder.
    h2 = make_host(cfg, _tmpdir(), pipeline=_Pipeline())
    h2._commit_trial(commit_mod.TrialMesh(src, 0))
    if h2.pipeline_cfgs != [None]:
        out.append("an ordinary commit overrode the script's mesh section: %r"
                   % (h2.pipeline_cfgs,))
    # ONE BUILDER, read off the source: no `PipelineConfig(` of its own.
    tree = ast.parse(_DISPOSE_SRC)
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_commit_pipeline"), None)
    if fn is None:
        out.append("`_commit_pipeline` is gone; this check names a method that "
                   "no longer exists")
    else:
        names = {n.func.attr for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        if "build_pipeline_config" not in names:
            out.append("the commit no longer goes through the one builder")
        # CALLS, never the source text: this method's own docstring names
        # `PipelineConfig` to say it must not build one, and a text search
        # therefore failed on the code that obeys the rule.
        built = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and ((isinstance(n.func, ast.Name)
                       and n.func.id == "PipelineConfig")
                      or (isinstance(n.func, ast.Attribute)
                          and isinstance(n.func.value, ast.Name)
                          and n.func.value.id == "PipelineConfig"))]
        if built:
            out.append("the disposition builds a PipelineConfig of its own")
    return out


def check_9(w):
    """The acceptance is keyed on the reason it was given for."""
    out = []
    cfg = drawing(_BLUNT, BLUNT_IDS)
    host = make_host(cfg, _tmpdir())
    ask(host, cfg, True)
    accepted = host._mesh_fallback
    if accepted is None:
        return ["the first offer was not accepted at all"]
    # 9a. the same refusal, unchanged: not re-asked, but SAID again.
    del host.reports[:]
    blocked, again = ask(host, cfg, False)
    if again.calls:
        out.append("9a: an unchanged refusal was put to the operator twice")
    if blocked:
        out.append("9a: the accepted fallback stopped letting the run through")
    if not any(says_not_structured(w, m) and lvl == "WARNING"
               for m, lvl in host.reports):
        out.append("9a: a fallback run said nothing about not being structured")
    # 9b. a DIFFERENT refusal is a different thing to accept.
    other = drawing(_BLUNT2, BLUNT_IDS)
    _blocked, asked2 = ask(host, other, False)
    if len(asked2.calls) != 1:
        out.append("9b: a refusal about a different curve was not put to the "
                   "operator (%d call(s))" % len(asked2.calls))
    # 9c. the family coming to accept the drawing drops the fallback.
    host._mesh_fallback = accepted
    ok = drawing(_SHARP, SHARP_IDS)
    ask(host, ok, False)
    if host._mesh_fallback is not None:
        out.append("9c: a fallback survived the family accepting the drawing")
    # 9d. and so does switching the panel to the hybrid path, which a Generate
    # over a trial already in hand reaches without running a pre-flight.
    host._mesh_fallback = accepted
    moved = hybrid_drawing()
    host._settle_fallback(moved)
    if host._mesh_fallback is not None:
        out.append("9d: a fallback survived the panel moving to the hybrid "
                   "path")
    # The CONSEQUENCE, which is what `_settle_fallback` is actually for: a
    # stale acceptance would keep TRANSFORMING the configuration, handing the
    # mesher a family-less run for a drawing the operator deliberately moved.
    # Asserting the flag alone would not have said so.
    if host.mesher_config(moved).topology.family != "cgrid":
        out.append("9d: the stale acceptance was still rewriting the "
                   "configuration the mesher is handed")
    host._mesh_fallback = accepted
    host._settle_fallback(cfg)
    if host._mesh_fallback is None:
        out.append("9d: the acceptance was dropped while its refusal still "
                   "stands")
    return out


def check_10(w):
    """The ordinary paths are untouched."""
    out = []
    import app.services.mesh_commit as commit_mod
    cfg = hybrid_drawing()
    host = make_host(cfg, _tmpdir())
    blocked, asked = ask(host, cfg, True)
    if blocked or asked.calls or host._mesh_fallback is not None:
        out.append("a hybrid-mode configuration reached the offer "
                   "(blocked=%r asked=%d)" % (blocked, len(asked.calls)))
    handed = host.mesher_config(cfg)
    if int(handed.mesh_mode) != 0 or handed.topology.family != "cgrid":
        out.append("the transformation changed a run that is not a fallback "
                   "(mode=%r family=%r)"
                   % (handed.mesh_mode, handed.topology.family))
    # A run with no case type and no fallback carries no sidecar at all — and
    # that is checked over a case that ALREADY HOLDS a fallback record, not
    # over a fresh directory. A review axis measured the fresh-directory
    # version: deleting the `.fallback.json` argument from `commit`'s unjudged
    # `_remove_stale` reddened NOTHING here, because there was never a record
    # for it to fail to remove. The third slot needs the same both-directions
    # treatment as check 6b's first two.
    src = fake_trial(_tmpdir())
    dest = os.path.join(_tmpdir(), "mesh_case.vtk")
    stem = os.path.splitext(dest)[0]
    commit_mod.commit(commit_mod.TrialMesh(
        src, 0, fallback=w.Fallback("the section is blunt.", "cgrid")), dest)
    if not os.path.isfile(stem + ".fallback.json"):
        out.append("the fallback commit this leg is built on wrote no record, "
                   "so the stale check below would pass on nothing")
    commit_mod.commit(commit_mod.TrialMesh(src, 0), dest)
    for ext in (".casetype.json", ".verdict.json", ".fallback.json"):
        if os.path.isfile(stem + ext):
            out.append("an unjudged ordinary commit left a %s standing beside "
                       "a mesh it does not describe" % ext)
    return out


def check_11(_w):
    """`services/mesh_fallback` is Qt-free, measured in a subprocess."""
    code = ("import sys; sys.path.insert(0, %r);"
            "import app.services.mesh_fallback as m;"
            "print('PyQt6' in sys.modules)" % _GUI)
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=_REPO)
    if proc.returncode != 0:
        return ["the service does not import on its own: %s"
                % proc.stderr.strip()[-300:]]
    return [] if proc.stdout.strip() == "False" else ["PyQt6 is loaded by it"]


_ALL = {
    1: ("the offer is made when the family refuses, and carries its reason",
        check_1),
    2: ("the fallback runs ONLY after the operator accepts it", check_2),
    3: ("the mesher is handed the hybrid configuration, mode and family both",
        check_3),
    4: ("the downgrade really meshes a drawing the structured run cannot even "
        "write", check_4),
    5: ("no verdict is issued from the case type's thresholds, and the reason "
        "is stated", check_5),
    6: ("the committed case is labelled not structured, and the record slots "
        "reconcile", check_6),
    7: ("a folded fallback mesh is still refused", check_7),
    8: ("the committed script describes the hybrid run, through the one "
        "builder", check_8),
    9: ("the acceptance is keyed on the reason it was given for", check_9),
    10: ("the ordinary paths are unchanged", check_10),
    11: ("services/mesh_fallback is Qt-free", check_11),
}


def run_all(w, quiet=False):
    global _QUIET
    _QUIET, saved = quiet, _QUIET
    try:
        result = {}
        for num in sorted(_ALL):
            label, fn = _ALL[num]
            try:
                problems = fn(w)
            except Exception as exc:                # noqa: BLE001 - reported
                import traceback
                problems = ["raised: %s" % traceback.format_exc()[-700:]
                            if not quiet else "raised: %r" % (exc,)]
            result[num] = check(not problems, "check %d. %s%s"
                                % (num, label,
                                   "" if not problems
                                   else " -- " + "; ".join(problems)))
        return result
    finally:
        _QUIET = saved


def mutate(old, new):
    assert _SRC.count(old) == 1, "mutation anchor is not unique: %r" % old[:60]
    return _SRC.replace(old, new)


def injected(label, src, reddens, note, lever=None):
    """Run every check against a mutant; the named ones must go red, alone."""
    global _IGNORE_THE_ANSWER
    print("--- injection %s: %s ---" % (label, note), flush=True)
    if src is not None:
        mod, restore = world(src)
    else:
        mod, restore = world()
    undo = None
    if lever == "accept":
        _IGNORE_THE_ANSWER = True
    elif lever is not None:
        undo = pull_lever(lever)
    try:
        res = run_all(mod, quiet=True)
    finally:
        _IGNORE_THE_ANSWER = False
        if undo is not None:
            undo()
        restore()
    red = sorted(n for n, ok in res.items() if not ok)
    check(red == sorted(reddens),
          "injection %s. the named check(s) %s go RED and no others (red: %s)"
          % (label, sorted(reddens), red))


# ── run ───────────────────────────────────────────────────────────────────────
_REAL, _RESTORE = world()
print("=== the real service ===", flush=True)
_BASE = run_all(_REAL)
_RESTORE()

injected("A", mutate('        model.family = FAMILY_NONE\n',
                     '        model.family = model.family\n'),
         [3, 4, 8],
         "`as_hybrid` leaves the FAMILY in place, so the config writer still "
         "projects its document and the run dies before the mesher it was "
         "downgrading to. THREE checks, measured rather than narrowed: 3b "
         "names the writer, 4 is the mesh that never arrives, and 8 is the "
         "script a committed case would carry")
injected("B", mutate("    out.mesh_mode = MESH_MODE_HYBRID\n",
                     "    out.mesh_mode = out.mesh_mode\n"),
         [1, 2, 3, 4, 8, 9],
         "`as_hybrid` leaves the MODE at multi-block, so the downgrade is the "
         "same run that was just refused. IT CASCADES, and the cascade is the "
         "design rather than a weakness of the injection: `unavailable_because` asks "
         "`missing_mesh_input` about the configuration `as_hybrid` produces, "
         "so one definition of what the fallback run IS serves both the offer "
         "and the run -- break it and the offer closes too. Check 3a is the "
         "one that names the mode itself")
injected("C", mutate("    return missing_mesh_input(as_hybrid(cfg))",
                     "    return \"\""),
         [1],
         "`unavailable_because` always says the hybrid path can run, so a "
         "case with no "
         "geometry at all is offered a mesh it cannot produce")
injected("D", mutate(
    '    "This mesh is NOT structured. It was generated on the hybrid path — "',
    '    "This mesh was generated on the hybrid path — "'),
         [1, 2, 5, 6, 9],
         "the not-structured CLAUSE reworded out of the sentence -- the "
         "realistic shape of this defect, and the one thing an operator must "
         "not have to infer. A first attempt emptied the constant instead and "
         "reddened NOTHING, because the empty string is a substring of every "
         "text the checks searched. FIVE checks, which is the enumerated "
         "label list of `services/mesh_fallback.py` doing its job: the "
         "question, the per-run log, the verdict slot and the committed "
         "record all quote the one sentence")
injected("E", mutate('        "structured": False,', '        "structured": True,'),
         [6],
         "the committed record claims the mesh IS structured")
injected("F", mutate('    return Fallback(reason=refusal_text(rows), family=family)',
                     '    return Fallback(reason="", family=family)'),
         [2, 9],
         "the acceptance records no reason, so it is keyed on nothing and "
         "never expires")
injected("H", None, [2],
         "the offer is ACCEPTED WITHOUT ASKING -- what a silent substitution "
         "looks like from inside the host", lever="accept")
injected("I", None, [6, 10],
         "`_remove_stale` never reaching the `.fallback.json` slot, so a "
         "committed case keeps a record of a mesh it no longer holds. A "
         "review axis MEASURED this one going green before check 10 grew its "
         "stale leg", lever="stale")
injected("J", None, [7],
         "`commit_refusal` reading 'no verdict' as 'nobody to refuse' -- "
         "#166's own shipped defect arriving in the fallback's shape, since a "
         "fallback mesh has no verdict by construction", lever="norefuse")

print("--- injection G: negative control ---", flush=True)
_CTRL, _CTRL_RESTORE = world()
_CTRL_RESULT = run_all(_CTRL)
_CTRL_RESTORE()
check(all(_CTRL_RESULT.values()) and all(_BASE.values()),
      "injection G. negative control: the unmutated service passes every "
      "check, so the failures above are the mutations and not the checker")

# ENDS IN `os._exit`, like every script here whose SOURCE mentions a
# QApplication (`test_qt_teardown_exit.py` reads source text, not imports): Qt's
# offscreen teardown can abort after the last check has already printed PASS.
if _FAILS:
    print("\nRESULT: %d FAILED" % len(_FAILS), flush=True)
    sys.stdout.flush()
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
sys.stdout.flush()
os._exit(0)
