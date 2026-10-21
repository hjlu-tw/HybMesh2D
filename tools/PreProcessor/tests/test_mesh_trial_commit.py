#!/usr/bin/env python3
"""TRIAL and GENERATE: one generation, two dispositions (issue #166, parent #158).

Trial generates a mesh for the operator to look at, carrying its verdict, and
commits nothing — they can run it as often as they like. Generate produces THE
SAME mesh and commits it: into the case under its own name, with the whole case
type that judged it, the frozen verdict and a runnable pipeline script beside it.
It does not recompute, and it refuses a mesh the verdict calls unusable.

THE CENTRAL CLAIM IS AN IDENTITY, SO IT IS CHECKED AS ONE. "Generate produces
the same mesh" is not asserted by reading the code that is supposed to copy it:
check 4 drives a real Generate over a real mesher output and compares the bytes
in the case with the bytes of the trial, having first instrumented the host so
that launching a second generation would be recorded. If Trial showed mesh A and
Generate shipped mesh B the operator approved one thing and the solver reads
another — and folds and wall-spacing error are exactly the defects that move
with density, so "it would come out the same" is the claim least worth trusting.

What this pins down:

  1. BOTH ACTIONS ARE REACHABLE FROM THE MESH TAB AND ARE THREE DISTINCT THINGS.
     A Trial button and a Generate button on the mesh toolbar and in the Mesh
     menu, wired to `trial_mesh` and `generate_mesh`; Run All wired to neither;
     and `run_mesh_generator` — which takes the disposition — wired to no
     `clicked` signal at all, because Qt hands a slot the checked state as a
     positional argument and a button wired straight to it would have committed
     on every press.
  2. PREVIEW IS UNCHANGED AND IS STILL NAMED PREVIEW. The menu still says "BC
     Preview", the toolbar button still says it, both still reach
     `preview_mesh_generator`, and that method still meshes nothing.
  3. TRIAL WRITES NOTHING THE CASE CONSUMES. A real mesher output judged through
     the real `_on_mesh_gen_finished` with no disposition leaves the case
     directory EMPTY — not "leaves the mesh alone", empty, because a Trial that
     wrote a verdict file into the case would already have broken the rule.
  4. GENERATE COMMITS THE MESH TRIAL PRODUCED, WITHOUT REGENERATING IT. Byte
     identity between the trial and the committed `.vtk`, `.vrt`, `.cel`, `.bnd`
     and provenance sidecar, with the host's own generator instrumented to
     record a launch that never happens.
  5. TRIAL NEVER OVERWRITES THE CASE'S MESH. Generate, then a SECOND trial whose
     mesh is deliberately different, then the case re-read: every committed byte
     and every mtime unchanged.
  6. THE WHOLE CASE TYPE IS EMBEDDED, NOT A NAME AND NOT A HASH. The committed
     copy loads through `case_type.load` and round-trips to the source's own
     `to_dict()` — thresholds, bounds, advice, reference meshes and field
     overlay — and the advice TEXT really is in the file.
  7. AN EDIT TO A CASE TYPE DOES NOT CHANGE A FINISHED CASE'S VERDICT. The
     source case type is rewritten with bounds that would flip the state; the
     committed record and the embedded document are re-read byte for byte.
  8. GENERATE REFUSES AN UNUSABLE MESH AND SAYS WHY — WITH OR WITHOUT A CASE
     TYPE. `EXIT_ERR_INVERTED` raises `CommitRefused` naming the exit code, and
     NOTHING is written. The no-case-type leg is the one that shipped broken:
     with `HYBMESH_CASE_TYPE` unset — the ordinary state, nothing having
     replaced that channel — there is no verdict to be `unusable`, and reading
     that as "nobody to refuse" committed the folded mesh ADR-0002 exists
     against. `needs attention` still commits, so the verdict stays a judgement
     rather than a gate.
  9. THE FINGERPRINT DECIDES WHETHER A TRIAL IS STILL CURRENT. The same config
     matches; a changed config, an edited geometry file and a deleted one each
     do not. A fingerprint nobody took never matches, so "we did not check"
     cannot read as "it is current".
 10. THE COMMITTED PIPELINE SCRIPT IS RUNNABLE AND REGENERATES THE MESH, end to
     end through `run_pipeline.sh --no-solver` on a shipped `MESH_MODE 1` case.
     Skipped without a build tree.
 11. ONE BUILDER FOR THAT SCRIPT. `_commit_pipeline` goes through
     `build_pipeline_config`, the same verb the Pipeline menu's Save uses, and
     the disposition constructs no `PipelineConfig` of its own — two builders is
     how a case ends up carrying a script that reproduces something else.
 12. THE TWO HALVES OF THE FINGERPRINT AGREE. The real `run_mesh_generator` is
     driven with only its worker class replaced, and the value it RECORDS is
     compared with the one the next Generate TAKES. They were derived from
     different documents until #166's review — the mesher's config against the
     panel's, differing by `EXPORT_VTK` alone — so no trial ever read as current
     and Generate re-meshed every time while a branch logged that it had not.
     Nothing saw it because no check put the producer and the consumer on one
     path: the host stand-in overrides the generator and check 4 sets the
     disposition by hand.
 13. `services/mesh_commit` IS QT-FREE, in a subprocess. In-process the answer is
     always "loaded" once anything else imported PyQt6.
 14. A COMMIT IS AUDIBLE AND LEAVES THE SESSION HOLDING WHAT IT APPROVED. A case
     that gets no pipeline script SAYS so — the commonest cause is not an
     exception but an empty GUI, which a `MESH_MODE 1` case declaring its own
     corners legitimately is — and `global_vtk_path` moves to the committed mesh,
     so Export and Send to Solver reach the file Generate approved rather than
     the scratch copy it was made from.
 15. THE COMMITTED SCRIPT NAMES THE FROZEN COPY, NOT THE FILE THE OPERATOR
     PICKED (#172). Three dispositions, three answers, because a rule that only
     ever re-points would be as wrong as one that never does: a JUDGED commit's
     script names `<stem>.casetype.json` beside the mesh and that file is really
     there; a FALLBACK commit's names none, the exemption #167 put in
     `as_hybrid` and which must stay; and a commit whose chosen case type would
     not LOAD keeps the operator's own spelling, because nothing was frozen and
     there is nothing to point at. The panel's own configuration is unchanged in
     all three — the re-pointing belongs to the script.
 16. AND RE-RUNNING IT REPRODUCES THE FROZEN VERDICT AFTER THE SOURCE HAS MOVED
     — OR SAYS PLAINLY THAT IT CANNOT. #172's acceptance, both branches, end to
     end. Commit; rewrite the SOURCE case type with bounds that really do flip
     this mesh to `unusable` — MEASURED here rather than assumed, so a premise
     that quietly stopped holding cannot leave the rest vacuous; run
     `./run_pipeline.sh <script> --no-solver` and read what it printed. The
     verdict is the frozen state, it names the frozen copy as the file that
     issued it, and the flipped state appears nowhere. Then STORY 43's own
     bullet, which was prose until now: the frozen copy is byte-identical after
     the re-run. Then the OTHER branch — the frozen copy moved aside, which is a
     script carried off without its case directory — where the mesh is still
     regenerated, the run says `No verdict`, NAMES the file it could not read,
     and issues none. Skipped without a build tree.

Known blind spots, named rather than papered over:
  - Checks 3-9 drive the REAL controller methods against a recording stand-in
    for the main window, not a real one. That the buttons are on screen and
    enabled is `smoke_headless_appcontroller.py`'s territory; check 1 reads the
    wiring statically, which is what makes "reachable" a fact about the source
    rather than about a window nobody opened.
  - Check 10 builds its `PipelineConfig` directly rather than through a live
    `AppController` with a loaded CAD session, which would need a mesher run
    inside a Qt event loop. It therefore proves the committed ARTEFACT runs;
    that the GUI builds the right one is check 11's structural claim.
  - Checks 15 and 16 drive the REAL `_commit_pipeline` but hand it a stand-in
    `build_pipeline_config` that honours the `mesh_cfg` override, for the same
    reason: the live builder needs a CAD session. What the stand-in cannot fake
    is the override itself — it is what the disposition passes — so the claim
    under test travels through the real code. That the live builder uses the
    argument at all is check 11's, and `pipeline_io_ctrl` has exactly one
    `mesh_cfg` parameter for both callers.
  - Nothing here re-freezes anything on a RE-RUN. Check 16's `run_pipeline.sh`
    overwrites the committed mesh and leaves the frozen copy and the verdict
    record standing, so a case whose script was re-run holds a record of the
    first run beside a mesh from the second. That is the standing blind spot in
    `.claude/rules/gui-dispositions.md` ("nothing checks that a committed case
    is still consistent later") and #172 does not widen it.
  - Nothing here judges whether a case type's thresholds are RIGHT, or whether
    the verdict is a good verdict. That is `test_case_type_verdict.py`'s
    subject, and #168's.
  - The fingerprint hashes the mesher config and the files it names. A change
    that reaches the mesh through neither — a different BINARY, say — is
    invisible to it, and Generate would then commit a trial built by the old
    one. Recorded rather than fixed: the trial lives only for the session that
    made it, and hashing the binary on every keystroke is not worth that.

INJECTIONS — AUTOMATED, by exec'ing a mutated copy of `services/mesh_commit.py`
and re-running the same check functions against it. Each asserts the mutation is
well-formed and really differs, then that the named check fails AND that no
other check moves:

  A. the case type written as its NAME instead of its document -> check 6 fails.
     The "not a name and not a hash" the ticket asks for, spent.
  B. `commit` copying only the `.vtk` -> check 4 fails: the STAR-CD triple the
     solver actually reads would be left in a temp dir that is wiped on exit.
  C. the refusal dropped from `commit` -> check 8 fails, and the folded mesh
     ADR-0002 exists against lands in the case looking entirely normal.
  C2. the exit code no longer reaching `commit_refusal` -> check 8 fails on its
     no-case-type leg ALONE, which is the defect as it shipped: a fold refused
     while a case type is named and committed while none is.
  D. the frozen report emptied out of the verdict record -> check 7 fails: a
     record that carries no judgement cannot survive the case type moving on.
  E. `inputs_fingerprint` ignoring the files the config names -> check 9 fails,
     so an edited geometry would read as "still current" and Generate would
     commit a mesh for the previous drawing.
  F. a Trial launched with GENERATE's disposition -> check 3 fails. Not a
     source mutation: checks 3 and 5 are claims about the controller, and no
     edit to `mesh_commit` can make a Trial write into the case, so the defect
     is committed directly instead of being argued about.
  G. negative control: the unmutated module passes every check.
  H. the Generate half fingerprinting the PANEL's config rather than the one the
     mesher is handed -> check 12 fails. Not a source mutation either, and for
     the same reason as F: the two halves live in two mixins and no edit to
     `mesh_commit` can pull them apart, so the pre-fix consumer is handed in.
  J. `as_frozen` handing back the configuration unchanged -> check 15 fails, and
     the committed script goes back to naming the maintained file: the mesh
     reproduces and the verdict is recomputed against whatever that file says on
     the day, which is #172 exactly. Check 16 cannot see it — it runs
     `run_pipeline.sh` in a child process, which loads the real module from disk
     — so the in-process check is the one that scores the mutation and the
     end-to-end one is what proves the fix is worth having.
  K. `as_frozen` re-pointing the configuration IN PLACE instead of a copy ->
     check 15 fails on its third leg. The script would be right and the
     operator's own case-type choice would silently become the frozen copy,
     so their next Trial — and the workspace they then save — would be judged
     by a historical document they were never asked about.

  Check 5 has no injection of its own. Its defect is the same one F commits —
  a disposition reaching a run that was not a Generate — and it is not vacuous
  by construction: it FAILS outright if the Generate before it committed
  nothing, so there is always something there for a Trial to have damaged.

Run:  python3 tools/PreProcessor/tests/test_mesh_trial_commit.py
Needs a build tree for checks 3-8 (a real mesher output) and 10; the rest run
without one.
"""
import ast
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# A real QApplication, offscreen. Not decoration: `app/utils.is_headless` asks
# the LIVE application for its platform name, so with none running it answers
# False and the graded message helpers really build a QMessageBox — which is how
# the refusal check first died, three frames away from what it was measuring.
from PyQt6.QtWidgets import QApplication            # noqa: E402
_APP = QApplication.instance() or QApplication([])

_COMMIT_REL = "tools/PreProcessor/gui/app/services/mesh_commit.py"
_SOURCES = {
    "toolbar_build": "tools/PreProcessor/gui/app/views/main_window_toolbar_build_mixin.py",
    "menu": "tools/PreProcessor/gui/app/views/main_window_menu_mixin.py",
    "wiring": "tools/PreProcessor/gui/app/controllers/signal_wiring_ctrl.py",
    "panel": "tools/PreProcessor/gui/app/views/panels/mesh_config_panel.py",
    "dispose": "tools/PreProcessor/gui/app/controllers/mesh_dispose_ctrl.py",
    "gen": "tools/PreProcessor/gui/app/controllers/mesh_gen_ctrl.py",
}

_FAILS = []
_MESHER = os.path.join(_REPO, "build", "HybMesh2D")


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _read(rel):
    with open(os.path.join(_REPO, rel), encoding="utf-8") as fh:
        return fh.read()


_COMMIT_SRC = _read(_COMMIT_REL)
_SRC = {k: _read(v) for k, v in _SOURCES.items()}

from app.models.mesh_config import MeshConfig            # noqa: E402
from app.services import case_type as case_type_mod      # noqa: E402

# --- the world: a fresh `mesh_commit`, optionally mutated --------------------
# Every check that touches the service is a pure function of this module, which
# is what makes the injections cheap. The real module is loaded through the same
# path as a mutant, so the negative control and the injections are symmetric.
_NAME = "app.services.mesh_commit"


def world(src=None):
    """A `mesh_commit` module built from the given source."""
    import app.services                                    # noqa: F401
    pkg = sys.modules["app.services"]
    saved_mod = sys.modules.get(_NAME)
    saved_attr = getattr(pkg, "mesh_commit", None)
    try:
        spec = importlib.util.spec_from_loader(_NAME, loader=None)
        mod = importlib.util.module_from_spec(spec)
        mod.__file__ = os.path.join(_REPO, _COMMIT_REL)
        sys.modules[_NAME] = mod
        # The PACKAGE attribute too: `from app.services import mesh_commit`
        # resolves through `getattr(app.services, ...)` first, so a mutant left
        # only in sys.modules would be shadowed by the real module and the
        # injection would silently test the real code.
        setattr(pkg, "mesh_commit", mod)
        exec(compile(src or _COMMIT_SRC, mod.__file__, "exec"), mod.__dict__)
        return mod
    finally:
        if saved_mod is None:
            sys.modules.pop(_NAME, None)
        else:
            sys.modules[_NAME] = saved_mod
        if saved_attr is None:
            if hasattr(pkg, "mesh_commit"):
                delattr(pkg, "mesh_commit")
        else:
            setattr(pkg, "mesh_commit", saved_attr)


# --- a case type with real thresholds ----------------------------------------
ADVICE_MAX = "Ask for a less aggressive first cell."
ADVICE_MEDIAN = "Add a ring, or raise the far-field spacing."


def write_case_type(path, attention=1e9, unusable=1e9):
    doc = {
        "schema": case_type_mod.SCHEMA, "version": case_type_mod.SCHEMA_VERSION,
        "name": "Trial and Generate test type",
        "metric": "quad_midline_ratio",
        "thresholds": [
            {"key": "max", "advice": ADVICE_MAX,
             "attention": attention, "unusable": unusable},
            {"key": "median", "advice": ADVICE_MEDIAN, "attention": 1e9},
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    return path


# --- a real mesh, from the shipped O-grid -------------------------------------
def make_mesh(dest_stem, config_overrides=None):
    """Run the shipped O-grid into `dest_stem`.<ext>. Returns the `.vtk` path.

    The SHIPPED config, read from disk through `mb_shipped_config` — a mesh this
    gate composed itself would leave an edit to the shipped case invisible from
    the gate that is supposed to cover it.
    """
    import mb_shipped_config
    from mesher_bin import mesher_env
    text = mb_shipped_config.shipped_config(
        "multiblock_ogrid", overrides=config_overrides or {})
    text = text.replace(mb_shipped_config.PLACEHOLDER, dest_stem)
    cfg_path = dest_stem + "_para.dat"
    with open(cfg_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    proc = subprocess.run([_MESHER, "-conf", cfg_path], cwd=_REPO,
                          env=mesher_env(), capture_output=True, text=True,
                          timeout=600)
    vtk = dest_stem + ".vtk"
    if not os.path.isfile(vtk):
        raise AssertionError("the shipped O-grid produced no mesh at %s "
                             "(rc=%d)\n%s" % (vtk, proc.returncode,
                                              proc.stdout[-2000:]))
    return vtk


def snapshot(directory):
    """Every file under `directory` as `{relpath: (bytes, mtime_ns)}`."""
    out = {}
    for root, _dirs, files in os.walk(directory):
        for name in files:
            full = os.path.join(root, name)
            with open(full, "rb") as fh:
                out[os.path.relpath(full, directory)] = (
                    fh.read(), os.stat(full).st_mtime_ns)
    return out


# --- the host: the REAL controller, with a recording main window -------------
class _Any:
    """A main window that answers every call and records nothing.

    One exception: the post-mortem that highlights a self-intersection reads the
    log panel's TEXT and feeds it to `re.search`, so that one accessor answers
    with a string. A stand-in that returned itself there turned a check about
    the refusal into a TypeError three frames away.
    """

    def __getattr__(self, name):
        if name == "get_log_text":
            return lambda: ""
        return _Any()

    def __call__(self, *_a, **_k):
        return _Any()


class _Pipeline:
    """Stands in for the host's `PipelineConfig`: one method, which is the seam."""

    def __init__(self):
        self.saved = []

    def save_to_file(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"name": "stub"}, fh)
        self.saved.append(path)


def make_host(commit_mod, cfg, temp_dir, pipeline=None):
    """The real `MeshGenControllerMixin`, with everything else recorded.

    Built per check rather than shared, because every check that uses it drives
    a DISPOSITION and a host that carried a previous one's trial would make the
    next check's answer depend on its neighbour.
    """
    from app.controllers.mesh_gen_ctrl import MeshGenControllerMixin

    class _Host(MeshGenControllerMixin):
        def __init__(self):
            self.main_window = _Any()
            self.global_mesh_config = cfg
            self.global_vtk_mesh = None
            self.global_vtk_path = ""
            self.temp_dir = temp_dir
            self._pending_after_mesh = None
            self._mesh_trial = None
            self._trial_fingerprint = ""
            self._commit_after_mesh = False
            # The hybrid-fallback state the composed controller declares in its
            # own `__init__` (#167). Set here for the same reason the three
            # above are: these are read directly, never with a default, so that
            # a renamed one fails loudly instead of disabling a disposition.
            self._mesh_fallback = None
            self._trial_fallback = None
            self.lines = []
            self.reports = []
            #: Every launch of the generator. Check 4's whole point is that this
            #: stays empty while a Generate commits a mesh.
            self.generations = []

        def log(self, message, level=None):
            self.lines.append(str(message))

        def log_report(self, message, level="ERROR"):
            self.reports.append((str(message), level))

        def config_from_panel(self, _name):
            return self.global_mesh_config

        def build_pipeline_config(self, mesh_cfg=None):
            return pipeline

        def run_mesh_generator(self, *, commit=False):
            self.generations.append(commit)

    host = _Host()
    # The module under test, injected into the two files that reach it by name.
    # `sys.modules` alone does not: both did `from app.services import
    # mesh_commit`, which binds the module OBJECT at import time.
    import app.controllers.mesh_dispose_ctrl as dispose
    import app.controllers.mesh_gen_ctrl as gen
    host._restore = (dispose.mesh_commit, gen.mesh_commit)
    dispose.mesh_commit = commit_mod
    gen.mesh_commit = commit_mod
    return host


def release(host):
    import app.controllers.mesh_dispose_ctrl as dispose
    import app.controllers.mesh_gen_ctrl as gen
    dispose.mesh_commit, gen.mesh_commit = host._restore


# --- checks -------------------------------------------------------------------
def _clicked_targets(src, widget):
    """Every `<widget>.clicked.connect(self.X)` target in `src`, as names."""
    out = []
    for node in ast.walk(ast.parse(src)):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "connect"):
            continue
        chain = node.func.value
        if not (isinstance(chain, ast.Attribute) and chain.attr == "clicked"):
            continue
        target = chain.value
        if not (isinstance(target, ast.Attribute) and target.attr == widget):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Attribute):
                out.append(arg.attr)
    return out


def check_both_actions_reachable(_w):
    out = []
    trial = _clicked_targets(_SRC["wiring"], "mesh_trial_btn")
    gen = _clicked_targets(_SRC["wiring"], "mesh_generate_btn")
    if trial != ["trial_mesh"]:
        out.append("the toolbar Trial button is wired to %r" % trial)
    if gen != ["generate_mesh"]:
        out.append("the toolbar Generate button is wired to %r" % gen)
    if _clicked_targets(_SRC["wiring"], "trial_mesh_btn") != ["trial_mesh"]:
        out.append("the panel's Trial button is not wired to trial_mesh")
    if _clicked_targets(_SRC["wiring"], "run_mesh_btn") != ["generate_mesh"]:
        out.append("the panel's Generate button is not wired to generate_mesh")
    # The disposition-taking method must reach NO clicked signal: Qt hands a
    # slot the checked state positionally, so a button wired straight to it
    # would have decided the disposition by accident.
    for node in ast.walk(ast.parse(_SRC["wiring"])):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "connect"):
            for arg in node.args:
                if isinstance(arg, ast.Attribute) and arg.attr == "run_mesh_generator":
                    out.append("run_mesh_generator is connected to a signal; "
                               "the disposition would come from the widget")
    if "self.mesh_trial_btn = create_tb_btn(" not in _SRC["toolbar_build"]:
        out.append("the mesh toolbar builds no Trial button")
    if "self.mesh_trial_btn," not in _SRC["toolbar_build"]:
        out.append("the Trial button is not in mesh_tb_widgets, so it never "
                   "becomes visible in a mesh mode")
    if 'self.tr("Trial Mesh")' not in _SRC["menu"]:
        out.append("the Mesh menu carries no Trial entry")
    for entry, verb in (("Trial Mesh", "controller.trial_mesh"),
                        ("Generate Mesh", "controller.generate_mesh")):
        idx = _SRC["menu"].find('self.tr("%s")' % entry)
        if idx < 0 or verb not in _SRC["menu"][idx:idx + 200]:
            out.append("the Mesh menu's %r does not reach %s" % (entry, verb))
    # Run All is a third thing and reaches neither.
    if "run_all" in _SRC["dispose"] or "run_pipeline" in _SRC["dispose"]:
        out.append("the disposition reaches Run All, which is the whole chain "
                   "through the solver and a different action")
    return out


def check_preview_is_unchanged(_w):
    out = []
    if _clicked_targets(_SRC["wiring"], "mesh_preview_btn") != ["preview_mesh_generator"]:
        out.append("the toolbar BC Preview button no longer reaches "
                   "preview_mesh_generator")
    if _clicked_targets(_SRC["wiring"], "preview_btn") != ["preview_mesh_generator"]:
        out.append("the panel's BC Preview button no longer reaches "
                   "preview_mesh_generator")
    if 'self.tr("BC Preview")' not in _SRC["menu"]:
        out.append("the Mesh menu no longer says BC Preview")
    if 'create_tb_btn("BC Preview"' not in _SRC["toolbar_build"]:
        out.append("the toolbar button is no longer labelled BC Preview")
    if 'make_button("BC Preview"' not in _SRC["panel"]:
        out.append("the panel button is no longer labelled BC Preview")
    # It still meshes nothing: the body launches no worker and starts no run.
    tree = ast.parse(_SRC["gen"])
    body = [n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "preview_mesh_generator"]
    if not body:
        out.append("preview_mesh_generator is gone")
    else:
        names = {n.attr for n in ast.walk(body[0]) if isinstance(n, ast.Attribute)}
        names |= {n.id for n in ast.walk(body[0]) if isinstance(n, ast.Name)}
        if names & {"run_mesh_generator", "MeshGenWorker", "trial_mesh",
                    "generate_mesh"}:
            out.append("Preview now meshes something; it draws the domain box "
                       "and the boundaries and nothing else")
    return out


def check_trial_writes_nothing(w, disposition=False):
    """A judged trial leaves the case directory EMPTY.

    `disposition` is the flag the run was launched with, and it is a parameter
    only so injection F can set it: a Trial that carried Generate's disposition
    is the defect this check exists for, and the cheapest honest way to show the
    check can go red is to commit that defect rather than to mutate a service
    whose code cannot cause it.
    """
    if not os.path.isfile(_MESHER):
        return []
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        vtk = make_mesh(os.path.join(tmp, "trial"))
        case = os.path.join(tmp, "case")
        os.makedirs(case)
        cfg = MeshConfig()
        cfg.output_filename = os.path.join(case, "mesh_probe.vtk")
        host = make_host(w, cfg, tmp)
        try:
            host._commit_after_mesh = disposition
            host._on_mesh_gen_finished(0, os.path.join(tmp, "absent.dat"), vtk)
        finally:
            release(host)
        left = sorted(snapshot(case))
        if left:
            out.append("a Trial wrote %d file(s) into the case: %s"
                       % (len(left), ", ".join(left)))
        if host._mesh_trial is None:
            out.append("a Trial left no trial mesh for Generate to commit")
    return out


def _generate(w, tmp, case, vtk, case_type_path=None, exit_code=0,
              pipeline=None):
    """Drive a real Generate over `vtk` and return the host."""
    cfg = MeshConfig()
    cfg.output_filename = os.path.join(case, "mesh_probe.vtk")
    host = make_host(w, cfg, tmp, pipeline=pipeline)
    if case_type_path:
        os.environ["HYBMESH_CASE_TYPE"] = case_type_path
    try:
        host._commit_after_mesh = True
        host._on_mesh_gen_finished(exit_code, os.path.join(tmp, "absent.dat"), vtk)
    finally:
        release(host)
        os.environ.pop("HYBMESH_CASE_TYPE", None)
    return host


def check_generate_commits_the_same_mesh(w):
    if not os.path.isfile(_MESHER):
        return []
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        vtk = make_mesh(os.path.join(tmp, "trial"))
        case = os.path.join(tmp, "case")
        os.makedirs(case)
        host = _generate(w, tmp, case, vtk)
        if host.generations:
            out.append("Generate launched the mesher %d more time(s): %r"
                       % (len(host.generations), host.generations))
        for ext in (".vtk", ".vrt", ".cel", ".bnd"):
            src, dest = (os.path.splitext(vtk)[0] + ext,
                         os.path.join(case, "mesh_probe" + ext))
            if not os.path.isfile(src):
                out.append("the trial produced no %s to compare" % ext)
                continue
            if not os.path.isfile(dest):
                out.append("the case carries no %s" % ext)
                continue
            with open(src, "rb") as a, open(dest, "rb") as b:
                if a.read() != b.read():
                    out.append("the committed %s is NOT the mesh Trial "
                               "produced" % ext)
        prov = os.path.join(case, "mesh_probe.provenance.json")
        if not os.path.isfile(prov):
            out.append("the case carries no provenance sidecar, so nothing in "
                       "it records what measured the mesh")
    return out


def check_trial_never_overwrites_the_case(w):
    if not os.path.isfile(_MESHER):
        return []
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        vtk = make_mesh(os.path.join(tmp, "trial"))
        case = os.path.join(tmp, "case")
        os.makedirs(case)
        _generate(w, tmp, case, vtk)
        before = snapshot(case)
        if not before:
            return ["Generate committed nothing, so this check would pass "
                    "vacuously"]
        # A SECOND trial, deliberately a different mesh: a coarser wall layer
        # changes every coordinate, so an overwrite could not go unnoticed.
        other = make_mesh(os.path.join(tmp, "trial2"),
                          {"BL_INITIAL_THICKNESS": "5e-3"})
        with open(other, "rb") as a, open(vtk, "rb") as b:
            if a.read() == b.read():
                return ["the second trial produced the same mesh, so this "
                        "check could not see an overwrite"]
        cfg = MeshConfig()
        cfg.output_filename = os.path.join(case, "mesh_probe.vtk")
        host = make_host(w, cfg, tmp)
        try:
            host._on_mesh_gen_finished(0, os.path.join(tmp, "absent.dat"), other)
        finally:
            release(host)
        after = snapshot(case)
        if after != before:
            moved = sorted(set(before) ^ set(after)) or sorted(
                k for k in before if before[k] != after.get(k))
            out.append("a Trial after a Generate changed the case: %s"
                       % ", ".join(moved))
    return out


def check_whole_case_type_is_embedded(w):
    if not os.path.isfile(_MESHER):
        return []
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        vtk = make_mesh(os.path.join(tmp, "trial"))
        case = os.path.join(tmp, "case")
        os.makedirs(case)
        ct_path = write_case_type(os.path.join(tmp, "t.casetype.json"))
        _generate(w, tmp, case, vtk, case_type_path=ct_path)
        embedded = os.path.join(case, "mesh_probe.casetype.json")
        if not os.path.isfile(embedded):
            return ["the case carries no embedded case type"]
        source = case_type_mod.load(ct_path)
        try:
            # A REFUSAL IS A FAILURE, NOT A CRASH. Whatever the embedded file
            # turns out to be, this check has to report on it — a mutant that
            # writes something `load` rejects is exactly the defect being
            # looked for, and letting it raise out of here would stop the
            # injection run instead of scoring it.
            copy = case_type_mod.load(embedded)
        except case_type_mod.CaseTypeError as exc:
            return ["the embedded file is not a loadable case type: %s" % exc]
        if copy.to_dict() != source.to_dict():
            out.append("the embedded case type is not the source document")
        with open(embedded, encoding="utf-8") as fh:
            text = fh.read()
        for advice in (ADVICE_MAX, ADVICE_MEDIAN):
            if advice not in text:
                out.append("the embedded copy does not carry the advice %r, so "
                           "it is a reference rather than the document" % advice)
    return out


def check_an_edit_cannot_rewrite_history(w):
    if not os.path.isfile(_MESHER):
        return []
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        vtk = make_mesh(os.path.join(tmp, "trial"))
        case = os.path.join(tmp, "case")
        os.makedirs(case)
        ct_path = write_case_type(os.path.join(tmp, "t.casetype.json"))
        _generate(w, tmp, case, vtk, case_type_path=ct_path)
        record = os.path.join(case, "mesh_probe.verdict.json")
        embedded = os.path.join(case, "mesh_probe.casetype.json")
        if not os.path.isfile(record):
            return ["the case carries no verdict record"]
        before = snapshot(case)
        doc = json.load(open(record, encoding="utf-8"))
        if not doc.get("report"):
            out.append("the record carries no rendered verdict, so there is "
                       "nothing in it an edit could fail to change")
        # The case type the operator borrowed moves on: bounds that would make
        # this very mesh `unusable`.
        write_case_type(ct_path, attention=1.0, unusable=1.0001)
        if snapshot(case) != before:
            out.append("editing the case type changed the finished case")
        again = json.load(open(record, encoding="utf-8"))
        if again != doc:
            out.append("the recorded verdict changed under an edit")
        # Read as TEXT, not through `load`: whether the embedded file is a
        # loadable case type is check 6's question, and asking it here would
        # make this check fail for a reason that is not its own.
        with open(embedded, encoding="utf-8") as fh:
            if "1.0001" in fh.read():
                out.append("the embedded copy followed the source's edit")
    return out


def check_unusable_is_refused(w):
    if not os.path.isfile(_MESHER):
        return []
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        vtk = make_mesh(os.path.join(tmp, "trial"))
        case = os.path.join(tmp, "case")
        os.makedirs(case)
        ct_path = write_case_type(os.path.join(tmp, "t.casetype.json"))
        # EXIT_ERR_INVERTED: the mesher exports a folded mesh under its ordinary
        # name by design (ADR-0002), and this layer is where it is stopped.
        from app.services import case_type_verdict
        host = _generate(w, tmp, case, vtk, case_type_path=ct_path,
                         exit_code=case_type_verdict.EXIT_ERR_INVERTED)
        left = sorted(snapshot(case))
        if left:
            out.append("an unusable mesh was committed anyway: %s"
                       % ", ".join(left))
        said = "\n".join(text for text, _lvl in host.reports)
        if "not written into the case" not in said:
            out.append("the refusal does not say the mesh was not committed: %r"
                       % said)
        if str(case_type_verdict.EXIT_ERR_INVERTED) not in said:
            out.append("the refusal does not say WHY — it names no exit code")
        if ADVICE_MAX in said or ADVICE_MEDIAN in said:
            pass        # advice is welcome; its absence is the thing checked
        # AND WITH NO CASE TYPE AT ALL, which is the ordinary state: nothing has
        # replaced `HYBMESH_CASE_TYPE` and no ticket owns a picker. There is no
        # verdict to be `unusable` then, and reading that as "nobody to refuse"
        # committed the folded mesh ADR-0002 states must never get through —
        # "the verdict layer, not the mesher, is what refuses to let it
        # through", with no case type named in the sentence.
        bare = os.path.join(tmp, "bare")
        os.makedirs(bare)
        host3 = _generate(w, tmp, bare, vtk,
                          exit_code=case_type_verdict.EXIT_ERR_INVERTED)
        left3 = sorted(snapshot(bare))
        if left3:
            out.append("with no case type in play, a folded mesh was committed: "
                       "%s" % ", ".join(left3))
        if not any("not written into the case" in text
                   for text, _lvl in host3.reports):
            out.append("with no case type in play, nothing refused the folded "
                       "mesh out loud")

        # A `needs attention` mesh is NOT refused: the operator is allowed to
        # keep one, and refusing it would make the verdict a gate rather than a
        # judgement.
        case2 = os.path.join(tmp, "case2")
        os.makedirs(case2)
        soft = write_case_type(os.path.join(tmp, "soft.casetype.json"),
                               attention=1.0)
        _generate(w, tmp, case2, vtk, case_type_path=soft)
        if not os.path.isfile(os.path.join(case2, "mesh_probe.vtk")):
            out.append("a `needs attention` mesh was refused, which would make "
                       "every verdict but `usable` a refusal")
    return out


def check_fingerprint_decides_currency(w):
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        geom = os.path.join(tmp, "body.dat")
        with open(geom, "w", encoding="utf-8") as fh:
            fh.write("0 0\n1 0\n1 1\n")
        base = w.inputs_fingerprint("MESH_MODE 1\n", [geom])
        if w.inputs_fingerprint("MESH_MODE 1\n", [geom]) != base:
            out.append("the same config and the same inputs hash differently")
        if w.inputs_fingerprint("MESH_MODE 0\n", [geom]) == base:
            out.append("a changed config hashes the same")
        with open(geom, "a", encoding="utf-8") as fh:
            fh.write("0 1\n")
        if w.inputs_fingerprint("MESH_MODE 1\n", [geom]) == base:
            out.append("an EDITED geometry hashes the same, so a trial for the "
                       "previous drawing would read as current")
        os.remove(geom)
        if w.inputs_fingerprint("MESH_MODE 1\n", [geom]) == base:
            out.append("a DELETED geometry hashes the same")
        # "We did not check" must never read as "it is current".
        trial = w.TrialMesh("m.vtk", 0, fingerprint="")
        if trial.matches("") or trial.matches(base):
            out.append("a trial with no fingerprint claims to match")
        if not w.TrialMesh("m.vtk", 0, fingerprint=base).matches(base):
            out.append("a trial does not match its own fingerprint")
    return out


def check_pipeline_script_runs(w):
    """The committed script really regenerates the mesh."""
    if not os.path.isfile(_MESHER):
        print("      (skipping: no build tree)", flush=True)
        return []
    out = []
    from app.models.pipeline_config import PipelineConfig
    with tempfile.TemporaryDirectory() as tmp:
        vtk = make_mesh(os.path.join(tmp, "trial"))
        case = os.path.join(tmp, "case")
        os.makedirs(case)
        mesh_cfg = MeshConfig()
        mesh_cfg.load_from_file(os.path.join(tmp, "trial_para.dat"))
        mesh_cfg.output_filename = os.path.join(case, "mesh_probe.vtk")
        pcfg = PipelineConfig.from_configs("trial_commit", [], mesh_cfg, None, {})
        trial = w.judge_run(vtk, 0, config=mesh_cfg)
        w.commit(trial, os.path.join(case, "mesh_probe.vtk"), pipeline=pcfg)
        script = os.path.join(case, "mesh_probe.pipeline.json")
        if not os.path.isfile(script):
            return ["Generate left no pipeline script"]
        os.remove(os.path.join(case, "mesh_probe.vtk"))
        proc = subprocess.run(["./run_pipeline.sh", script, "--no-solver"],
                              cwd=_REPO, capture_output=True, text=True,
                              timeout=900)
        if not os.path.isfile(os.path.join(case, "mesh_probe.vtk")):
            out.append("the committed script did not regenerate the mesh "
                       "(rc=%d)\n%s" % (proc.returncode, proc.stdout[-2000:]))
    return out


class _NoWorker:
    """A `MeshGenWorker` that connects, starts and never launches anything.

    Check 12 has to run `run_mesh_generator` for real — the fingerprint it
    records is the thing under test — and everything after the config is written
    is a QThread and a subprocess. Replacing the worker CLASS is the smallest cut
    that leaves the whole config-and-fingerprint half untouched.
    """

    def __init__(self, *_a, **_k):
        self.log_signal = self.progress_signal = self.finished_signal = _Any()

    def start(self):
        pass

    def isRunning(self):
        return False


def check_fingerprint_halves_agree(w, consumer=None):
    """The run RECORDS a fingerprint; the next Generate TAKES one. One value.

    The producer and the consumer are in different mixins and were derived from
    different documents until #166's review: the run fingerprinted the config as
    the MESHER is handed it (output retargeted, both formats forced on) and the
    disposition fingerprinted the panel's own, so they differed by `EXPORT_VTK`
    alone. Every comparison failed, `_current_trial` always answered None, and
    Generate silently re-meshed every time — failing safe, and making the whole
    fingerprint dead weight while a log line claimed otherwise.

    Nothing could see it, because no check put the two on one path: the host
    stand-in OVERRIDES `run_mesh_generator`, and check 4 sets the disposition by
    hand. This one runs the real method with only the worker replaced.

    `consumer` is the half that TAKES the fingerprint, a parameter only so
    injection H can supply the pre-fix one: no edit to `mesh_commit` can put the
    two halves back out of step, so the defect is committed directly rather than
    argued about — injection F's shape.
    """
    if not os.path.isfile(_MESHER):
        return []
    out = []
    import app.controllers.mesh_gen_ctrl as gen
    with tempfile.TemporaryDirectory() as tmp:
        cfg = MeshConfig()
        cfg.output_filename = os.path.join(tmp, "case", "mesh_probe.*")
        # A config the panel has moved off the run's own defaults, so the two
        # halves have something to disagree about.
        cfg.export_vtk = False
        cfg.export_starcd = False
        host = make_host(w, cfg, tmp)
        real_worker = gen.MeshGenWorker
        gen.MeshGenWorker = _NoWorker
        try:
            # NOT the stand-in's recorder: the real method, off the mixin.
            gen.MeshGenControllerMixin.run_mesh_generator(host, commit=False)
            recorded = host._trial_fingerprint
            taken = (consumer or host._fingerprint_of)(cfg)
        finally:
            gen.MeshGenWorker = real_worker
            release(host)
        if not recorded:
            out.append("the run recorded no fingerprint at all, so this check "
                       "would pass vacuously")
        elif recorded != taken:
            out.append("the run recorded %s and the next Generate takes %s — no "
                       "trial can ever read as current, and Generate re-meshes "
                       "every time" % (recorded[:12], taken[:12]))
    return out


def check_commit_service_is_qt_free(_w):
    """`services/mesh_commit` imports no Qt, measured in a subprocess.

    In-process the answer is always "loaded" once anything else imported PyQt6,
    which is why this is a child process rather than a `sys.modules` test. The
    module is claimed Qt-free by `.claude/rules/gui-dispositions.md`; until #166's
    review nothing held it, `test_case_type_verdict.py` check 10 covering only the
    two case-type services.
    """
    mod = "app.services.mesh_commit"
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; __import__(%r); print('PyQt6' in sys.modules)" % mod],
        cwd=_GUI, capture_output=True, text=True)
    if proc.returncode != 0 or proc.stdout.strip() != "False":
        return ["%s is not Qt-free (rc=%d, said %r)"
                % (mod, proc.returncode, proc.stdout.strip())]
    return []


def check_commit_is_audible_and_in_hand(w):
    """A commit SAYS what it could not leave, and repoints the session at it.

    Two things #166's Spec review found quiet. `build_pipeline_config` answers
    ``None`` whenever there is no active CAD session — which a `MESH_MODE 1`
    case declaring its own corners legitimately has none of — and the commit
    then left no script and said nothing, while "Generate leaves a runnable
    pipeline script" is an acceptance criterion. And `global_vtk_path` still
    pointed at the scratch mesh the commit was made FROM, so every later action
    that reads "the last generated mesh" reached the temp copy rather than the
    file Generate approved.
    """
    if not os.path.isfile(_MESHER):
        return []
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        vtk = make_mesh(os.path.join(tmp, "trial"))
        case = os.path.join(tmp, "case")
        os.makedirs(case)
        # pipeline=None is what the real builder returns with no CAD session.
        host = _generate(w, tmp, case, vtk, pipeline=None)
        if os.path.isfile(os.path.join(case, "mesh_probe.pipeline.json")):
            out.append("a script was written although none was built")
        said = "\n".join(host.lines)
        if "no pipeline script was left" not in said:
            out.append("the commit left no pipeline script and did not say so")
        dest = os.path.join(case, "mesh_probe.vtk")
        if os.path.abspath(host.global_vtk_path) != os.path.abspath(dest):
            out.append("after a Generate the session's mesh path is %r, not the "
                       "committed %r — Export and Send to Solver would reach the "
                       "scratch copy" % (host.global_vtk_path, dest))
    return out


def _commit_for_script(w, tmp, case, vtk, mesh_cfg, fallback=None):
    """Drive a real Generate and return `(host, the script as a dict or None)`.

    The host's `build_pipeline_config` is a stand-in that HONOURS the `mesh_cfg`
    override, because the live one needs a CAD session (see the blind spots).
    The override itself is the real disposition's, which is the claim under test.
    """
    from app.models.pipeline_config import PipelineConfig

    host = make_host(w, mesh_cfg, tmp)
    def _build(mesh_cfg=None):
        return PipelineConfig.from_configs(
            "frozen_probe", [],
            host.global_mesh_config if mesh_cfg is None else mesh_cfg,
            None, {})
    host.build_pipeline_config = _build
    try:
        host._commit_after_mesh = True
        host._trial_fallback = fallback
        host._on_mesh_gen_finished(0, os.path.join(tmp, "absent.dat"), vtk)
    finally:
        release(host)
    script = os.path.join(case, "mesh_probe.pipeline.json")
    if not os.path.isfile(script):
        return host, None
    with open(script, encoding="utf-8") as fh:
        return host, json.load(fh)


def _probe_config(tmp, case, case_type_file=""):
    """The O-grid's own mesher config, pointed at the case. `None` if unmeshed."""
    cfg = MeshConfig()
    cfg.load_from_file(os.path.join(tmp, "trial_para.dat"))
    cfg.output_filename = os.path.join(case, "mesh_probe.vtk")
    cfg.case_type_file = case_type_file
    return cfg


def check_script_names_the_frozen_copy(w):
    """#172: the script a commit leaves is judged by the copy frozen beside it."""
    if not os.path.isfile(_MESHER):
        return []
    from app.services import case_type_picker, mesh_fallback
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        vtk = make_mesh(os.path.join(tmp, "trial"))
        ct_path = write_case_type(os.path.join(tmp, "t.casetype.json"))

        # (a) A JUDGED commit re-points at the frozen copy, and that copy is
        #     really the file the script now names — a spelling nothing can
        #     resolve would be this fix with its own failure mode.
        case = os.path.join(tmp, "judged")
        os.makedirs(case)
        cfg = _probe_config(tmp, case, case_type_file=ct_path)
        _host, doc = _commit_for_script(w, tmp, case, vtk, cfg)
        frozen = os.path.join(case, "mesh_probe" + case_type_picker.SUFFIX)
        if doc is None:
            return ["a judged Generate left no pipeline script"]
        named = str(doc.get("mesh", {}).get("case_type_file", ""))
        want = case_type_picker.stored_spelling(os.path.abspath(frozen))
        if named != want:
            out.append("the committed script names %r, not the frozen copy %r"
                       % (named, want))
        if not os.path.isfile(case_type_picker.resolve(named)):
            out.append("the script names a case type that is not on disk: %r"
                       % named)
        if os.path.abspath(case_type_picker.resolve(named)) == \
                os.path.abspath(ct_path):
            out.append("the script still names the source case type, which "
                       "goes on being maintained")
        # (c) and the operator's own configuration is untouched by the commit.
        if cfg.case_type_file != ct_path:
            out.append("the commit changed the operator's own case type choice "
                       "to %r" % cfg.case_type_file)

        # (b) A FALLBACK commit names NO case type. #167's exemption, which #172
        #     must leave exactly as it found it: an unstructured mesh freezes no
        #     case type, so there is nothing beside it to point at.
        case = os.path.join(tmp, "fallback")
        os.makedirs(case)
        cfg = _probe_config(tmp, case, case_type_file=ct_path)
        fb = mesh_fallback.Fallback(reason="The C-grid family refuses this "
                                           "drawing.", family="cgrid")
        _host, doc = _commit_for_script(w, tmp, case, vtk, cfg, fallback=fb)
        if doc is None:
            out.append("a fallback Generate left no pipeline script")
        elif str(doc.get("mesh", {}).get("case_type_file", "")):
            out.append("a fallback commit's script names a case type (%r); an "
                       "unstructured mesh is judged by none"
                       % doc["mesh"]["case_type_file"])

        # (d) NOTHING FROZEN, NOTHING TO POINT AT. A chosen case type that will
        #     not load issues no verdict and embeds no copy, so the script keeps
        #     the operator's own spelling rather than naming a sidecar that was
        #     never written.
        case = os.path.join(tmp, "broken")
        os.makedirs(case)
        gone = os.path.join(tmp, "gone.casetype.json")
        cfg = _probe_config(tmp, case, case_type_file=gone)
        _host, doc = _commit_for_script(w, tmp, case, vtk, cfg)
        if doc is None:
            out.append("a commit with an unloadable case type left no script")
        elif str(doc.get("mesh", {}).get("case_type_file", "")) != gone:
            out.append("a commit that froze nothing re-pointed the script "
                       "anyway: %r" % doc.get("mesh", {}).get("case_type_file"))
        if os.path.isfile(os.path.join(case, "mesh_probe" + case_type_picker.SUFFIX)):
            out.append("a case type that would not load was embedded anyway")
    return out


def check_rerun_reproduces_the_frozen_verdict(w):
    """#172's acceptance, end to end through `run_pipeline.sh`."""
    if not os.path.isfile(_MESHER):
        print("      (skipping: no build tree)", flush=True)
        return []
    from app.services import case_type as ct_mod
    from app.services import case_type_verdict
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        vtk = make_mesh(os.path.join(tmp, "trial"))
        case = os.path.join(tmp, "case")
        os.makedirs(case)
        ct_path = write_case_type(os.path.join(tmp, "t.casetype.json"))
        cfg = _probe_config(tmp, case, case_type_file=ct_path)
        _host, doc = _commit_for_script(w, tmp, case, vtk, cfg)
        if doc is None:
            return ["the commit left no pipeline script to re-run"]
        record = os.path.join(case, "mesh_probe.verdict.json")
        if not os.path.isfile(record):
            return ["the commit left no frozen verdict to reproduce"]
        with open(record, encoding="utf-8") as fh:
            frozen_state = json.load(fh)["state"]

        # THE SOURCE MOVES, the way `add_reference_mesh.py` moves one: bounds
        # that really do flip THIS mesh. Measured, not assumed — a premise that
        # silently stopped flipping would make the rest of this check vacuous.
        write_case_type(ct_path, attention=1.0, unusable=1.0001)
        moved, _text, _lvl = case_type_verdict.run_verdict(
            vtk, 0, case_type=ct_mod.load(ct_path))
        if moved.state == frozen_state:
            return ["the edited source case type still grades this mesh %r, so "
                    "there is no disagreement left for the re-run to resolve"
                    % frozen_state]

        script = os.path.join(case, "mesh_probe.pipeline.json")
        frozen_copy = os.path.join(case, "mesh_probe.casetype.json")
        with open(frozen_copy, "rb") as fh:
            copy_before = fh.read()
        os.remove(os.path.join(case, "mesh_probe.vtk"))
        proc = subprocess.run(["./run_pipeline.sh", script, "--no-solver"],
                              cwd=_REPO, capture_output=True, text=True,
                              timeout=900)
        said = proc.stdout
        if not os.path.isfile(os.path.join(case, "mesh_probe.vtk")):
            return ["the committed script did not regenerate the mesh "
                    "(rc=%d)\n%s" % (proc.returncode, said[-2000:])]
        if "Verdict: %s" % frozen_state not in said:
            out.append("the re-run did not reproduce the frozen verdict %r:\n%s"
                       % (frozen_state, said[-2000:]))
        if "Verdict: %s" % moved.state in said:
            out.append("the re-run was graded by the EDITED source: it says "
                       "%r, which the frozen record does not" % moved.state)
        if "from " + frozen_copy not in said:
            out.append("the re-run does not name the frozen copy as the file "
                       "that issued its verdict")
        # STORY 43 IS THE THIRD ACCEPTANCE BULLET AND IS NOW ASSERTED, not
        # reasoned about. #172 is the ticket that makes a script NAME this file,
        # which is a new reason for something to touch it; "the frozen copy is
        # still never rewritten" was covered by prose alone until here.
        with open(frozen_copy, "rb") as fh:
            if fh.read() != copy_before:
                out.append("the re-run REWROTE the frozen copy; an old case's "
                           "verdict must not change under a later run")

        # AND THE OTHER BRANCH OF THE ACCEPTANCE: "or says plainly that it
        # cannot". It is the one new failure mode this option buys — a script
        # carried off without its case directory — and it was asserted in three
        # documents and tested nowhere. Moved rather than deleted, so the
        # teardown still has a file and the mesh is the only thing re-made.
        os.rename(frozen_copy, frozen_copy + ".away")
        os.remove(os.path.join(case, "mesh_probe.vtk"))
        proc = subprocess.run(["./run_pipeline.sh", script, "--no-solver"],
                              cwd=_REPO, capture_output=True, text=True,
                              timeout=900)
        said = proc.stdout
        if not os.path.isfile(os.path.join(case, "mesh_probe.vtk")):
            out.append("a script whose frozen case type is gone did not "
                       "regenerate the mesh; losing the verdict must not cost "
                       "the mesh (rc=%d)\n%s" % (proc.returncode, said[-2000:]))
        if "No verdict" not in said:
            out.append("the re-run neither judged nor said it could not:\n%s"
                       % said[-2000:])
        if os.path.basename(frozen_copy) not in said:
            out.append("the re-run does not NAME the case type it could not "
                       "read, so 'says plainly' is not met")
        if "Verdict: " in said:
            out.append("a verdict was issued with no case type to issue it")
    return out


def check_one_pipeline_builder(_w):
    out = []
    tree = ast.parse(_SRC["dispose"])
    calls = {n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    if "build_pipeline_config" not in calls:
        out.append("the disposition does not go through build_pipeline_config, "
                   "the verb the Pipeline menu's Save uses")
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    if "PipelineConfig" in names or "from_configs" in calls:
        out.append("the disposition builds a PipelineConfig of its own; two "
                   "builders is how a case carries a script that reproduces "
                   "something else")
    io_src = _read("tools/PreProcessor/gui/app/controllers/pipeline_io_ctrl.py")
    if "def build_pipeline_config" not in io_src:
        out.append("pipeline_io_ctrl declares no build_pipeline_config")
    if "self.build_pipeline_config()" not in io_src:
        out.append("save_pipeline_file no longer goes through the shared "
                   "builder, so the menu and the committed case can diverge")
    return out


_ALL = {
    1: check_both_actions_reachable,
    2: check_preview_is_unchanged,
    3: check_trial_writes_nothing,
    4: check_generate_commits_the_same_mesh,
    5: check_trial_never_overwrites_the_case,
    6: check_whole_case_type_is_embedded,
    7: check_an_edit_cannot_rewrite_history,
    8: check_unusable_is_refused,
    9: check_fingerprint_decides_currency,
    10: check_pipeline_script_runs,
    11: check_one_pipeline_builder,
    12: check_fingerprint_halves_agree,
    13: check_commit_service_is_qt_free,
    14: check_commit_is_audible_and_in_hand,
    15: check_script_names_the_frozen_copy,
    16: check_rerun_reproduces_the_frozen_verdict,
}

_LABELS = {
    1: "check 1. Trial and Generate are both on the Mesh tab, distinct, and the "
       "disposition-taking method is wired to no widget",
    2: "check 2. BC Preview is unchanged, still named Preview, and still meshes "
       "nothing",
    3: "check 3. a Trial leaves the case directory EMPTY",
    4: "check 4. Generate commits the mesh Trial produced, byte for byte, "
       "without launching a second generation",
    5: "check 5. a Trial after a Generate leaves every committed byte untouched",
    6: "check 6. the WHOLE case type is embedded — the document, not a name or "
       "a hash",
    7: "check 7. an edit to the case type does not change a finished case's "
       "verdict",
    8: "check 8. Generate refuses an unusable mesh and says why; `needs "
       "attention` still commits",
    9: "check 9. the fingerprint decides whether a trial is still current",
    10: "check 10. the committed pipeline script runs and regenerates the mesh",
    11: "check 11. one builder for the committed script, shared with the "
        "Pipeline menu",
    12: "check 12. the fingerprint the RUN records and the one the next Generate "
        "TAKES are the same value",
    13: "check 13. services/mesh_commit is Qt-free, measured in a subprocess",
    14: "check 14. a commit says what it could not leave, and repoints the "
        "session at the mesh it approved",
    15: "check 15. the committed script is judged by the copy FROZEN beside the "
        "mesh — and by none at all for a fallback, and by the operator's own "
        "spelling when nothing was frozen",
    16: "check 16. re-running that script after the SOURCE case type has been "
        "edited reproduces the frozen verdict, leaves the frozen copy byte-"
        "identical, and says plainly that it cannot judge when that copy is gone",
}

_REAL = world()

for num in sorted(_ALL):
    fails = _ALL[num](_REAL)
    check(not fails, _LABELS[num])
    for f in fails:
        print("      " + f.replace("\n", "\n      "), flush=True)


# --- injections ---------------------------------------------------------------
# The structural checks (1, 2, 11) read SOURCE rather than the module and so do
# not move under a mutation of it; check 10 runs the real binary through a real
# `run_pipeline.sh`, which cannot see an in-memory mutant at all. Excluding them
# from `others_green` keeps a check that is measuring something else from being
# scored as evidence about this one.
# 13 imports the REAL module from disk in a child process and cannot see an
# in-memory mutant at all; 12 drives the real controller, whose fingerprint
# comes from the injected module and so DOES move under one.
# 16 is skipped for check 10's reason and only that one: it runs
# `run_pipeline.sh` in a child process, which loads the REAL module from disk.
# Its in-process half is check 15, which is where injections J and K are scored.
_SKIP_UNDER_MUTATION = (1, 2, 10, 11, 13, 16)


def others_green(w, *reddened):
    return not any(fn(w) for num, fn in _ALL.items()
                   if num not in reddened and num not in _SKIP_UNDER_MUTATION)


def mutate(old, new, count=1):
    assert old in _COMMIT_SRC, "injection anchor not found: %r" % old
    mutated = _COMMIT_SRC.replace(old, new, count)
    assert mutated != _COMMIT_SRC
    return world(mutated)


if os.path.isfile(_MESHER):
    inj = mutate("        case_type.save(trial.verdict.case_type, "
                 "sidecars[\"case_type\"])",
                 "        _write_json(sidecars[\"case_type\"], "
                 "{\"name\": trial.verdict.case_type.name})")
    check(check_whole_case_type_is_embedded(inj) and others_green(inj, 6),
          "injection A. check 6 ALONE fails when the case carries the case "
          "type's NAME instead of its document — the thing #166 asks for by "
          "name, since a name points at a file that moves")

    inj = mutate('MESH_EXTS = (".vtk", ".vrt", ".cel", ".bnd")',
                 'MESH_EXTS = (".vtk",)')
    check(check_generate_commits_the_same_mesh(inj) and others_green(inj, 4),
          "injection B. check 4 ALONE fails when only the .vtk is committed — "
          "the STAR-CD triple the solver reads would stay in a temp dir wiped "
          "on exit")

    inj = mutate("    refusal = case_type_verdict.commit_refusal(trial.verdict, "
                 "trial.exit_code)", "    refusal = \"\"")
    check(check_unusable_is_refused(inj) and others_green(inj, 8),
          "injection C. check 8 ALONE fails when the refusal is dropped, and "
          "the folded mesh ADR-0002 exists against lands in the case looking "
          "entirely normal")

    inj = mutate("commit_refusal(trial.verdict, trial.exit_code)",
                 "commit_refusal(trial.verdict)")
    check(check_unusable_is_refused(inj) and others_green(inj, 8),
          "injection C2. check 8 ALONE fails when the exit code stops reaching "
          "the refusal — the defect as it shipped, a fold refused while a case "
          "type is named and committed while none is")

    inj = mutate('        "report": trial.report,', '        "report": "",')
    check(check_an_edit_cannot_rewrite_history(inj) and others_green(inj, 7),
          "injection D. check 7 ALONE fails when the record stops freezing the "
          "rendered verdict — a record carrying no judgement cannot survive the "
          "case type moving on")

    inj = mutate("    for path in sorted(set(input_paths)):",
                 "    for path in sorted(set()):")
    check(check_fingerprint_decides_currency(inj) and others_green(inj, 9),
          "injection E. check 9 ALONE fails when the fingerprint ignores the "
          "files the config names — an edited geometry would read as still "
          "current and Generate would commit a mesh for the previous drawing")

    # NOT a source mutation. Checks 3 and 5 are claims about the CONTROLLER's
    # disposition, and no edit to `mesh_commit` can make a Trial write into the
    # case — so the defect is committed directly: the same run, launched with
    # Generate's disposition. `others_green` is not consulted, because this
    # mutant is the argument to one check rather than a module every check sees.
    check(check_trial_writes_nothing(_REAL, disposition=True),
          "injection F. check 3 fails when a Trial carries Generate's "
          "disposition — the one way the case can be written behind the "
          "operator's back, and the one a service mutation cannot produce")

    # Injection H, like F, is not a source mutation: the halves are in two
    # mixins and `mesh_commit` cannot pull them apart. The PRE-FIX consumer is
    # handed in instead — the panel's own config rather than the one the mesher
    # is handed — which is literally the code this review replaced.
    def _pre_fix_consumer(cfg):
        import app.controllers.mesh_dispose_ctrl as dispose
        probe = os.path.join(tempfile.gettempdir(), "prefix_para.dat")
        cfg.save_to_file(probe)
        with open(probe, encoding="utf-8") as fh:
            text = fh.read()
        return dispose.mesh_commit.inputs_fingerprint(text, [])

    check(check_fingerprint_halves_agree(_REAL, consumer=_pre_fix_consumer),
          "injection H. check 12 fails when the Generate half fingerprints the "
          "PANEL's config instead of the one the mesher is handed — the defect "
          "that made every trial read as stale while a branch claimed otherwise")

    inj = mutate("    out.case_type_file = case_type_picker.stored_spelling(\n"
                 "        sidecar_paths(os.path.abspath(dest_mesh))[\"case_type\"])",
                 "    out.case_type_file = cfg.case_type_file")
    check(check_script_names_the_frozen_copy(inj) and others_green(inj, 15),
          "injection J. check 15 ALONE fails when the script stops being "
          "re-pointed — it names the maintained file again, so the mesh "
          "reproduces and the verdict is recomputed against bounds that moved")

    inj = mutate("    out = copy.deepcopy(cfg)\n    out.case_type_file = "
                 "case_type_picker.stored_spelling(",
                 "    out = cfg\n    out.case_type_file = "
                 "case_type_picker.stored_spelling(")
    check(check_script_names_the_frozen_copy(inj) and others_green(inj, 15),
          "injection K. check 15 ALONE fails when the re-pointing mutates the "
          "operator's own configuration instead of a copy — their next Trial "
          "would be judged by a historical document nobody asked them about")

    check(not any(fn(_REAL) for num, fn in _ALL.items()),
          "injection G. negative control: the unmutated module passes every "
          "check, so the failures above are the mutations and not the checker")
else:
    print("      (skipping the injections: no build tree)", flush=True)


print("\n%s: %d check(s) failed" % (os.path.basename(__file__), len(_FAILS))
      if _FAILS else "\nAll checks passed.", flush=True)
# os._exit, like every script here that builds a QApplication: Qt's offscreen
# teardown crashes on a machine with no GPU, and an exit 139 after a clean run
# reads as a failing assertion.
sys.stdout.flush()
os._exit(1 if _FAILS else 0)
