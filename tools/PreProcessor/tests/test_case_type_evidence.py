#!/usr/bin/env python3
"""A MISJUDGED THRESHOLD IS CORRECTED WITH EVIDENCE (issue #168, parent #158).

#161 gave a case type one reference mesh and derived every bound from it. That
is a thin basis: it has an opinion about what that mesh happened to exercise and
no opinion about anything else, so sooner or later a verdict judges wrong — a
mesh called usable that was not, or one refused that was fine. This ticket is
the correction, and the whole point is HOW it is made: the maintainer adds the
offending mesh and the thresholds move. Hand-editing the number would work and
would throw away the thing the measurement bought — a threshold whose origin is
still visible six months later, which is ADR-0002's first consequence and user
stories 38 and 39.

What this pins down:

  1. A FURTHER REFERENCE MESH CAN BE ADDED, AND THE THRESHOLDS ADJUST. Driven as
     a SUBPROCESS through `tools/PreProcessor/add_reference_mesh.py`: exit 0, the
     case type rewritten, the bound moved to the new evidence's derivation, and
     the file still loads. `--dry-run` moves nothing on disk.
  2. A REFERENCE MESH CAN BE ADDED AS A COUNTER-EXAMPLE, and the thresholds then
     REJECT IT — measured through #160's verdict service, not by reading the
     numbers back out of the file. Every exemplar stays `usable` in the same
     breath, which is the half that makes the rejection mean something. A
     correction that CLOSES a figure's needs-attention band says so, in both
     directions: said when it happens, silent when it does not.
  3. EVERY THRESHOLD REPORTS WHICH REFERENCE MESHES IT RESTS ON, in the FILE
     (`measured_from.references`, the set that bears on the figure) and in what
     both inspecting hosts print. A stored support that does not match the
     evidence is refused on load, so the two cannot drift.
  4. ADDING A REFERENCE MESH DOES NOT ALTER AN ALREADY-FINISHED CASE'S VERDICT.
     A case is committed through the real `services/mesh_commit.py`, the case
     type it borrowed is then corrected, and both sidecars come back
     BYTE-IDENTICAL — and the embedded copy still judges that mesh the way it
     was judged. The leg that makes this non-vacuous is the other one: the
     CORRECTED case type judges the same mesh differently, so the freeze is
     carrying weight rather than describing a change that never happened.
  5. A HAND-OVERRIDDEN THRESHOLD IS NOT SILENTLY RECOMPUTED. It carries no
     tolerance factor, so there is nothing to re-derive; it comes through the
     addition bit-for-bit and still reads `manual` beside a measured bound that
     moved.
  6. A SELF-CONTRADICTORY ADDITION IS REFUSED, NAMING THE CONFLICT. Six shapes:
     a counter-example no figure separates from the exemplars, one a HAND-SET
     bound accepts (where naming the override is the only way criteria 5 and 6
     both hold), one publishing nothing any threshold bounds, an exemplar a
     hand-set bound rejects, a duplicate id, and a mesh measured with the other
     path's metric. Nothing is written on a refusal.
  7. A DOCUMENT THAT CONTRADICTS ITS OWN EVIDENCE IS REFUSED ON LOAD, not partly
     read: a bound hand-edited away from its derivation, a support with a mesh
     taken out of it, and an `unusable` bound raised until it accepts the
     counter-example the file declares. That is what gives a counter-example
     teeth in the ARTEFACT and not only in the step that added it.
  8. ONE COMPARISON, TWO ASKERS. `case_type_verdict.judge_threshold` spells no
     `>` of its own: it and `case_type_evidence` both go through
     `case_type_reference.exceeds`, so "every exemplar is accepted and every
     counter-example rejected" is a statement about the rule the verdict applies
     rather than a second opinion free to drift from it.
  9. QT-FREE, in a subprocess: importing the evidence service leaves PyQt6
     unimported.
 11. A COUNTER-EXAMPLE NEVER WIDENS A BOUND ANOTHER ONE PLACED. Adding a mesh
     that is worse than the exemplars on one figure and BETTER on another
     tightens the first and leaves the second exactly where it was. Added after
     review found the opposite shipping.
 10. THE SHIPPED CASE TYPE DEMONSTRATES IT. `examples/case_types/ogrid_circle`
     rests on an exemplar and a counter-example, every threshold names both, the
     real verdict service calls the first `usable` and the second `unusable`,
     and its one hand-set bound is still hand-set.

Known blind spots, named rather than papered over:
  - NOTHING JUDGES WHETHER A REFERENCE MESH DESERVES ITS KIND. That the C-grid
    is a mesh this case type should reject is the maintainer's judgement, and
    the whole mechanism is built to record a judgement rather than to form one.
    This is #161's "nothing judges whether a tolerance factor is right", moved
    one layer out: what is gated is that the bound really follows from the
    evidence, not that the evidence is the right evidence.
  - THE SEPARATING BOUND IS A CHOICE. `sqrt(base * cap)` puts the boundary
    halfway in log space between the worst exemplar and the best
    counter-example. What is gated is that it lies strictly between them — so
    every exemplar passes and every counter-example fails — not that halfway is
    the right place. A maintainer who disagrees overrides the bound by hand,
    and check 5 is what keeps that override standing.
  - A COUNTER-EXAMPLE CAN LEAVE A FIGURE WITH NO NEEDS-ATTENTION BAND. When the
    bad mesh is barely worse than the good one, both bounds land on the same
    separating value and that figure can only answer `usable` or `unusable`.
    It is honest — the evidence leaves no room for a middle — and it is why the
    shipped example adds one counter-example rather than every mesh to hand.
  - Check 4 proves the FREEZE, not the UI. That Generate is the only writer of a
    case's mesh is #166's gate's, and nothing here re-presses a button.

INJECTIONS — AUTOMATED, by exec'ing mutated copies of the six service sources
and re-running the same check functions against the mutant. Each asserts the
mutation is well-formed and really differs, then that the named check fails AND
that no other check moves (`others_green`):

  A. `Evidence.bound` stops holding a derived bound down to the separating
     bound -> checks 2, 4, 7, 10 and 11 fail: a counter-example nothing can
     reject, and a shipped file whose median bound no longer IS its derivation.
  B. `add_reference` re-derives a bound with no tolerance factor -> checks 5
     and 6 fail: the maintainer's override silently recomputed.
  C. `standing_failures` always answers "nothing wrong" -> checks 6 and 7 fail:
     every self-contradictory addition accepted, including the one a hand-set
     bound makes impossible.
  D. `Origin.to_dict` writes only the FIRST id of the support -> checks 3 and 7
     fail: a threshold that can no longer say which meshes it rests on.
  E. `cap` goes back to the minimum over EVERY counter-example -> check 11
     fails: a correction that LOOSENS a threshold. The defect review found,
     kept as the injection that proves it stays fixed.
  F. `measure_reference` ignores the kind it is handed -> checks 2, 3, 4, 6, 7
     and 11 fail: a counter-example recorded as an exemplar WIDENS the bounds it
     was added to tighten. Six of eleven, named rather than narrowed.
  G. `judge_threshold` spells its own `>` -> check 8 fails.
  H. `mesh_commit.commit` stops embedding the case type -> check 4 fails: a
     finished case whose verdict can only be re-derived from a file that has
     since moved on.
  I. the HOST — which runs as a subprocess and so cannot see an in-memory
     mutant — writes beside the case type instead of over it, and check 1 fails.
     It runs a mutated COPY of the script, with the real unmutated host asserted
     green beside it.
  J. negative control: the unmutated six pass every check.

TWO injections were REMOVED or RETARGETED after they came back INERT or too
broad, recorded rather than quietly fixed, because what they found is the
lesson. **F was inert**: every reference mesh in this gate was constructed by
hand, so `measure_reference` — the step that is handed the kind — was reached by
nothing here. The fixtures now go through the real measuring step off a real
sidecar, which is what makes the mutation reachable at all. **G was inert** for
the mirror reason: check 8 parsed the source off DISK, so no mutant could change
what it read; the world now carries the source it was built from. And one was
removed outright: a mutation making `_rederived` keep the threshold's OLD
support reddened SIX of the ten checks, because the file's own coherence check
then refuses every addition — a mutation that reddens the file proves nothing
about the check it was written for, and injection D holds that property from the
writing side instead.

Run:  python3 tools/PreProcessor/tests/test_case_type_evidence.py
Needs no build tree, no Qt and no network.
"""
import ast
import atexit
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_HOST = os.path.join("tools", "PreProcessor", "add_reference_mesh.py")
_SHOW = os.path.join("tools", "PreProcessor", "show_case_type.py")
_SHIPPED = os.path.join("examples", "case_types", "ogrid_circle.casetype.json")

#: name -> repo-relative source, in DEPENDENCY order: the figures and the
#: provenance, the derivation over a set of them, the document, the verdict that
#: applies it, the step that authors and corrects one, and the disposition that
#: freezes a case around it.
_RELS = [
    ("app.services.case_type_reference",
     "tools/PreProcessor/gui/app/services/case_type_reference.py"),
    ("app.services.case_type_evidence",
     "tools/PreProcessor/gui/app/services/case_type_evidence.py"),
    ("app.services.case_type",
     "tools/PreProcessor/gui/app/services/case_type.py"),
    ("app.services.case_type_verdict",
     "tools/PreProcessor/gui/app/services/case_type_verdict.py"),
    ("app.services.case_type_author",
     "tools/PreProcessor/gui/app/services/case_type_author.py"),
    ("app.services.mesh_commit",
     "tools/PreProcessor/gui/app/services/mesh_commit.py"),
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


class World:
    """The six services, built fresh and optionally mutated.

    `src` is the SOURCE each was built from, because one check reads a module
    by AST rather than by calling it — and reading the source off disk instead
    would make that check blind to every mutation, which is how injection G
    first came back inert.
    """

    def __init__(self, mods, src):
        self.src = src
        self.reference = mods["case_type_reference"]
        self.evidence = mods["case_type_evidence"]
        self.case_type = mods["case_type"]
        self.verdict = mods["case_type_verdict"]
        self.author = mods["case_type_author"]
        self.commit = mods["mesh_commit"]


def _exec_module(name, rel, source):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = os.path.join(_REPO, rel)
    sys.modules[name] = mod
    # The PACKAGE attribute too: `from app.services import case_type` resolves
    # through `getattr(app.services, ...)` first, so a mutant left only in
    # sys.modules would be shadowed by the real module the package already
    # holds — and the injection would silently test the real code (#160).
    pkg = sys.modules.get("app.services")
    if pkg is not None:
        setattr(pkg, name.rsplit(".", 1)[1], mod)
    exec(compile(source, mod.__file__, "exec"), mod.__dict__)
    return mod


def world(**mutated):
    """A `World` built from the given source, keyed by module short name."""
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
        return World(built, {n.rsplit(".", 1)[1]: mutated.get(
            n.rsplit(".", 1)[1], _SRC[n]) for n, _ in _RELS})
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


from app.services import mesh_shape_stats  # noqa: E402

# ── the meshes, with the figures they really published ────────────────────────
# Read off their own sidecars on 2026-10-07. The O-grid's are the same numbers
# `test_case_type_author.py` and `test_case_type_verdict.py` use, so no two
# gates describe different meshes.
OGRID = dict(whole=dict(cells=4608, median=1.845977, p95=23.662285,
                        maximum=32.767868),
             layer=dict(cells=2304, median=5.184358, p95=28.507718,
                        maximum=32.767868),
             bulk=dict(cells=2304, median=1.692763, p95=1.877756,
                       maximum=1.881891))
#: The two-ring O-grid on an ellipse: WORSE than the O-grid on `median` and
#: `bulk.p95`, better on `max`. A further exemplar that really moves a bound.
TWORING = dict(whole=dict(cells=4608, median=2.226388, p95=17.18139,
                          maximum=25.274427),
               layer=dict(cells=2304, median=3.61655, p95=21.218629,
                          maximum=25.274427),
               bulk=dict(cells=2304, median=2.03434, p95=2.384981,
                         maximum=3.037934))
#: The C-grid: far worse on every figure. The shipped counter-example.
CGRID = dict(whole=dict(cells=5760, median=4.832007, p95=148.005672,
                        maximum=3147.957636),
             layer=dict(cells=2022, median=5.59829, p95=523.160759,
                        maximum=3147.957636),
             bulk=dict(cells=3738, median=4.403685, p95=103.819747,
                       maximum=909.360929))
#: The H-grid: BETTER than the exemplars everywhere, and published with no
#: wall/bulk split. Nothing can separate it from them, so it is the mesh a
#: counter-example may not be.
HGRID = dict(whole=dict(cells=1600, median=1.164421, p95=1.39141,
                        maximum=1.504321))
#: Constructed, not measured: a mesh whose `median` is just worse than the
#: two-ring's and whose every other figure is the O-grid's exactly. Adding it as
#: a counter-example therefore moves ONE bound, which is what makes check 4's
#: "the corrected case type judges it differently" leg about one number.
NEAR = dict(whole=dict(cells=4608, median=2.4, p95=23.662285,
                       maximum=32.767868),
            layer=dict(OGRID["layer"]), bulk=dict(OGRID["bulk"]))

#: Constructed: a mesh far worse than the exemplars on `bulk.p95` and BETTER
#: than them on `median`. As a counter-example it is separable on one figure and
#: says nothing on the other, which is the shape that made a counter-example
#: WIDEN a bound — found by review, held by check 11.
LOPSIDED = dict(whole=dict(cells=4608, median=1.0, p95=23.662285,
                           maximum=32.767868),
                layer=dict(OGRID["layer"]),
                bulk=dict(cells=2304, median=2.0, p95=4.0, maximum=5.0))

ADVICE = {"median": "Put more points round the body.",
          "max": "Ask for a less aggressive first cell.",
          "bulk.p95": "Spread the radial spacing law out."}


def summary(figs, metric="quad_midline_ratio", source="<constructed>"):
    """A `ShapeSummary` as the sidecar reader would have produced one."""
    half = {k: (None if figs.get(k) is None
                else mesh_shape_stats.ShapeFigures(**figs[k]))
            for k in ("layer", "bulk")}
    return mesh_shape_stats.ShapeSummary(metric=metric, source=source,
                                         layer=half["layer"],
                                         bulk=half["bulk"], **figs["whole"])


def write_mesh(tmp, name, figs, metric="quad_midline_ratio"):
    """A mesh file and the `.provenance.json` the mesher leaves beside it."""
    mesh = os.path.join(tmp, name + ".vtk")
    with open(mesh, "w", encoding="utf-8") as fh:
        fh.write("# vtk DataFile Version 3.0\n")
    quality = {"metric": metric}
    for part, block in figs.items():
        row = {"cells": block["cells"], "median": block["median"],
               "p95": block["p95"], "max": block["maximum"]}
        if part == "whole":
            quality.update(row)
        else:
            quality[part] = row
    with open(os.path.join(tmp, name + ".provenance.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"tool": "HybMesh2D",
                   "mesh": {"nodes": 1, "elements": 1, "quality": quality}}, fh)
    return mesh


#: One directory for every fixture mesh, written once. The references below go
#: through the REAL `measure_reference` — reading a mesh's own
#: `.provenance.json` — rather than being constructed: a helper that built a
#: `ReferenceMesh` directly would make the whole measuring step, the kind it is
#: handed included, unreachable by any injection here. That is exactly how
#: injection F first came back inert.
_FIXDIR = tempfile.mkdtemp(prefix="case_type_evidence_")
atexit.register(shutil.rmtree, _FIXDIR, True)
_WRITTEN = {}


def reference(w, figs, ident, kind=None, metric="quad_midline_ratio"):
    """A `ReferenceMesh` measured off a real sidecar, through the real step."""
    key = (ident, metric)
    if key not in _WRITTEN:
        _WRITTEN[key] = write_mesh(_FIXDIR, "%s_%s" % (ident, metric), figs,
                                   metric=metric)
    return w.author.measure_reference(
        _WRITTEN[key], ident=ident, measured_on="2026-10-07",
        kind=kind or w.case_type.EXEMPLAR)


def authored(w, advice=None, overrides=None, figs=None, name="O-grid"):
    """The ordinary #161 authoring action, as every check below starts from it."""
    ref = reference(w, figs or OGRID, "ogrid_circle")
    return w.author.author(name, ref, dict(ADVICE if advice is None else advice),
                           overrides=overrides).case_type


def corrected(w, case_type, ref):
    """`add_reference`, with a refusal RETURNED rather than raised.

    Every check below is a function that returns its failures, and a mutation
    that turns an ordinary addition into a refusal would otherwise escape as an
    exception and take the whole run down instead of reddening one check —
    which would make an injection's `others_green` unmeasurable rather than
    False.
    """
    try:
        return w.author.add_reference(case_type, ref), ""
    except w.case_type.CaseTypeError as exc:
        return None, ("adding reference mesh %r was refused: %s"
                      % (ref.ident, exc))


# ── 1. a further reference mesh can be added, and the thresholds adjust ───────
def check_addition_moves_the_thresholds(w, host=""):
    """The CLI really corrects a case type, in one command.

    `host` lets injection I run a MUTATED COPY of the script, which is the only
    way this check can be shown able to go red: it launches a subprocess against
    the real files on disk and so cannot see the in-memory mutants every other
    injection uses.
    """
    out = []
    before = authored(w)
    want = w.evidence.Evidence.over(
        list(before.references) + [reference(w, TWORING, "tworing")],
        "median").bound(w.author.DEFAULT_ATTENTION_FACTOR)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ct.casetype.json")
        w.case_type.save(before, path)
        was = open(path, "rb").read()
        mesh = write_mesh(tmp, "tworing", TWORING)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [_GUI] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))

        def run(*extra):
            return subprocess.run(
                [sys.executable, host or os.path.join(_REPO, _HOST), path,
                 mesh, "--reference-id", "tworing",
                 "--measured-on", "2026-10-07"] + list(extra),
                capture_output=True, text=True, cwd=_REPO, env=env)

        dry = run("--dry-run")
        if dry.returncode != 0:
            return ["%s --dry-run exited %d: %s"
                    % (_HOST, dry.returncode, dry.stderr)]
        if open(path, "rb").read() != was:
            out.append("--dry-run rewrote the case type anyway")
        if "median" not in dry.stdout:
            out.append("--dry-run did not say which bound would move: %r"
                       % dry.stdout)
        proc = run()
        if proc.returncode != 0:
            return out + ["%s exited %d: %s"
                          % (_HOST, proc.returncode, proc.stderr)]
        try:
            after = w.case_type.load(path)
        except w.case_type.CaseTypeError as exc:
            return out + ["the corrected case type does not load: %s" % exc]
    if [r.ident for r in after.references] != ["ogrid_circle", "tworing"]:
        out.append("the corrected case type declares %s"
                   % [r.ident for r in after.references])
    got = {t.key: t for t in after.thresholds}
    old = {t.key: t for t in before.thresholds}
    if got["median"].attention == old["median"].attention:
        out.append("the median bound did not move: still %r"
                   % got["median"].attention)
    if abs(got["median"].attention - want) > 1e-9 * max(want, 1.0):
        out.append("the median bound is %r, not the %r its evidence derives"
                   % (got["median"].attention, want))
    if sorted(got) != sorted(old):
        out.append("the correction changed which figures are bounded: %s"
                   % sorted(got))
    for key in got:
        if got[key].advice != old[key].advice:
            out.append("the advice for %s did not survive the correction" % key)
    return out


# ── 2. a counter-example is REJECTED, and the exemplars stay accepted ─────────
def check_counter_example_is_rejected(w):
    """The thresholds must now reject it — asked of the verdict service."""
    out = []
    base = authored(w)
    # `NEAR` and not the C-grid, deliberately: the C-grid is already `unusable`
    # under the case type #161 wrote, so adding it would measure that file
    # rather than this ticket. `NEAR` is a mesh the thresholds PASSED and the
    # maintainer says they should not have, which is the misjudged verdict the
    # whole ticket exists to correct.
    if w.verdict.judge(base, summary(NEAR), 0).state != w.verdict.USABLE:
        return ["the counter-example is already rejected before it is added, "
                "so nothing here measures the correction"]
    try:
        added = w.author.add_reference(
            base, reference(w, NEAR, "near", kind=w.case_type.COUNTER))
    except w.case_type.CaseTypeError as exc:
        return ["a mesh the exemplars are separable from was refused as a "
                "counter-example: %s" % exc]
    fixed = added.case_type
    if not added.moves:
        out.append("adding a counter-example moved no bound at all")
    for ref, figs, want in (("near", NEAR, w.verdict.UNUSABLE),
                            ("ogrid_circle", OGRID, w.verdict.USABLE)):
        got = w.verdict.judge(fixed, summary(figs), 0)
        if got.state != want:
            out.append("%s is %r under the corrected case type, not %r: %s"
                       % (ref, got.state, want,
                          " / ".join(w.verdict.report_lines(got))))
    # A band that CLOSED is said out loud. The evidence here leaves no room
    # between the worst exemplar and the counter-example, so `median` can only
    # answer `usable` or `unusable` from now on — honest, and useless if the
    # maintainer is not told, since the verdict still answers.
    closed = [t.key for t in fixed.thresholds
              if t.attention is not None and t.attention == t.unusable]
    for key in closed:
        if not any(key in note for note in added.notes):
            out.append("%s can no longer answer `needs attention` and the "
                       "addition said nothing about it: %s"
                       % (key, added.notes))
    if not closed and added.notes:
        out.append("a cost was reported for a correction that closed no band: "
                   "%s" % added.notes)
    # Two counter-examples: the NEARER one decides, and both stay rejected.
    try:
        both = w.author.add_reference(
            fixed, reference(w, CGRID, "cgrid",
                             kind=w.case_type.COUNTER)).case_type
    except w.case_type.CaseTypeError as exc:
        return out + ["a second counter-example, further from the exemplars "
                      "than the first, was refused: %s" % exc]
    for ident, figs in (("cgrid", CGRID), ("near", NEAR)):
        if w.verdict.judge(both, summary(figs), 0).state != w.verdict.UNUSABLE:
            out.append("counter-example %s stopped being rejected once a "
                       "second one was added" % ident)
    if w.verdict.judge(both, summary(OGRID), 0).state != w.verdict.USABLE:
        out.append("the exemplar stopped being accepted once two "
                   "counter-examples were added")
    return out


# ── 3. every threshold reports which reference meshes it rests on ─────────────
def check_support_is_reported(w):
    """In the file, in the object, and in what the inspecting host prints."""
    out = []
    first, why = corrected(w, authored(w), reference(w, TWORING, "tworing"))
    if first is None:
        return [why]
    second, why = corrected(w, first.case_type,
                            reference(w, CGRID, "cgrid",
                                      kind=w.case_type.COUNTER))
    if second is None:
        return [why]
    fixed = second.case_type
    want = ["ogrid_circle", "tworing", "cgrid"]
    for th in fixed.thresholds:
        if list(th.measured_from.references) != want:
            out.append("threshold %s rests on %s, not on every mesh that "
                       "published it (%s)"
                       % (th.key, list(th.measured_from.references), want))
        line = fixed.describe_support(th)
        for ident in want:
            if ident not in line:
                out.append("%s is missing from %s's support line: %r"
                           % (ident, th.key, line))
        if w.case_type.COUNTER not in line:
            out.append("%s's support line does not say which mesh is the "
                       "counter-example: %r" % (th.key, line))
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ct.casetype.json")
        w.case_type.save(fixed, path)
        raw = json.load(open(path, encoding="utf-8"))
        for th in raw["thresholds"]:
            if th["measured_from"]["references"] != want:
                out.append("the FILE records %s's support as %s"
                           % (th["key"], th["measured_from"]["references"]))
        kinds = {r["id"]: r.get("kind", w.case_type.EXEMPLAR)
                 for r in raw["reference_meshes"]}
        if kinds.get("cgrid") != w.case_type.COUNTER:
            out.append("the FILE does not record the counter-example's kind: %s"
                       % kinds)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [_GUI] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        proc = subprocess.run(
            [sys.executable, os.path.join(_REPO, _SHOW), path],
            capture_output=True, text=True, cwd=_REPO, env=env)
        if proc.returncode != 0:
            out.append("%s exited %d: %s" % (_SHOW, proc.returncode,
                                             proc.stderr))
        for ident in want:
            if proc.stdout.count(ident) < 2:
                out.append("%s names %s once or not at all, so a reader cannot "
                           "tell which thresholds rest on it" % (_SHOW, ident))
    return out


# ── 4. an already-finished case keeps the verdict it was given ───────────────
def check_finished_case_is_frozen(w):
    """Correct the case type an operator borrowed; their case does not move."""
    out = []
    base = authored(w)
    with tempfile.TemporaryDirectory() as tmp:
        shared = os.path.join(tmp, "shared.casetype.json")
        w.case_type.save(base, shared)
        borrowed = w.case_type.load(shared)
        mesh = write_mesh(tmp, "global_mesh", TWORING)
        judged = w.verdict.judge(borrowed, summary(TWORING), 0)
        if judged.state != w.verdict.USABLE:
            return ["the case being committed is %r, so this check would not "
                    "notice a changed verdict" % judged.state]
        trial = w.commit.TrialMesh(mesh, 0, fingerprint="abc", verdict=judged,
                                   report=w.verdict.report_text(judged))
        dest = os.path.join(tmp, "case", "mesh_case.vtk")
        w.commit.commit(trial, dest, when="2026-10-07T00:00:00Z")
        sidecars = w.commit.sidecar_paths(dest)
        missing = [role for role in ("case_type", "verdict")
                   if not os.path.isfile(sidecars[role])]
        if missing:
            return ["a committed case carries no %s file, so there is nothing "
                    "frozen for a later correction to leave alone"
                    % " or ".join(missing)]
        frozen = {role: open(sidecars[role], "rb").read()
                  for role in ("case_type", "verdict")}

        # The correction: a counter-example that pulls the median bound BELOW
        # the figure the committed mesh published.
        added, why = corrected(w, borrowed,
                               reference(w, NEAR, "near",
                                         kind=w.case_type.COUNTER))
        if added is None:
            return out + [why]
        fixed = added.case_type
        w.case_type.save(fixed, shared)
        if w.verdict.judge(fixed, summary(TWORING), 0).state == judged.state:
            out.append("the corrected case type judges the committed mesh the "
                       "same way, so nothing here measures the freeze")
        for role, was in frozen.items():
            if open(sidecars[role], "rb").read() != was:
                out.append("the committed %s changed when the case type it "
                           "came from was corrected" % role)
        record = json.load(open(sidecars["verdict"], encoding="utf-8"))
        if record["state"] != judged.state:
            out.append("the frozen verdict reads %r, not the %r it was given"
                       % (record["state"], judged.state))
        embedded = w.case_type.load(sidecars["case_type"])
        again = w.verdict.judge(embedded, summary(TWORING), 0)
        if again.state != judged.state:
            out.append("re-judging through the EMBEDDED case type gives %r, "
                       "not the %r the case carries" % (again.state,
                                                        judged.state))
        if [r.ident for r in embedded.references] != ["ogrid_circle"]:
            out.append("the embedded case type picked up the correction: %s"
                       % [r.ident for r in embedded.references])
    return out


# ── 5. a hand-overridden threshold is not silently recomputed ────────────────
def check_override_survives_the_addition(w):
    """The one bound nothing here may touch, and the one that must move."""
    out = []
    base = authored(w, overrides={"max": {"unusable": 200.0}})
    added, why = corrected(w, base, reference(w, TWORING, "tworing"))
    if added is None:
        return [why]
    got = {t.key: t for t in added.case_type.thresholds}
    if got["max"].unusable != 200.0:
        out.append("the hand-set bound was recomputed to %r"
                   % got["max"].unusable)
    if got["max"].origin_of("unusable") != w.case_type.MANUAL:
        out.append("the hand-set bound reads %r after the addition"
                   % got["max"].origin_of("unusable"))
    if got["median"].origin_of("attention") != w.case_type.MEASURED:
        out.append("the measured bound beside it stopped reading measured")
    if not any(key == "median" for key, _, _, _ in added.moves):
        out.append("the measured bound did not move, so this check cannot tell "
                   "'not recomputed' from 'nothing was recomputed at all'")
    if any(key == "max" and bound == "unusable"
           for key, bound, _, _ in added.moves):
        out.append("the hand-set bound is reported as having moved")
    # The support still grows: an override loses the claim to be derived, not
    # the record of what bears on it.
    if list(got["max"].measured_from.references) != ["ogrid_circle", "tworing"]:
        out.append("the overridden threshold's support did not grow: %s"
                   % list(got["max"].measured_from.references))
    return out


# ── 6. a self-contradictory addition is refused, naming the conflict ─────────
def check_contradiction_is_refused(w):
    """Six additions that cannot be honoured, each refused with a reason."""
    out = []
    base = authored(w)
    overridden = authored(w, overrides={"max": {"unusable": 200.0}})
    only_bulk = authored(w, advice={"bulk.p95": ADVICE["bulk.p95"]})
    cases = (
        ("a counter-example no figure separates from the exemplars", base,
         reference(w, HGRID, "hgrid", kind=w.case_type.COUNTER), "hgrid"),
        # Every figure the O-grid's EXCEPT `max`, so the only figure that
        # could separate it is the one whose `unusable` bound is hand-set —
        # and that bound is the one thing this ticket may not recompute.
        ("a counter-example a HAND-SET bound accepts", overridden,
         reference(w, dict(whole=dict(cells=9,
                                      median=OGRID["whole"]["median"],
                                      p95=OGRID["whole"]["p95"],
                                      maximum=150.0)),
                   "loose", kind=w.case_type.COUNTER), "HAND-SET"),
        ("a counter-example publishing nothing any threshold bounds", only_bulk,
         reference(w, HGRID, "nosplit", kind=w.case_type.COUNTER), "nosplit"),
        ("an exemplar a HAND-SET bound rejects", overridden,
         reference(w, dict(whole=dict(cells=9, median=1.9, p95=24.0,
                                      maximum=900.0)), "huge"), "HAND-SET"),
        ("a reference mesh whose id is already taken", base,
         reference(w, TWORING, "ogrid_circle"), "ogrid_circle"),
        ("a reference measured with the other path's metric", base,
         reference(w, HGRID, "tri", metric="tri_edge_ratio"), "tri_edge_ratio"),
    )
    for what, case_type, ref, must_name in cases:
        try:
            w.author.add_reference(case_type, ref)
        except w.case_type.CaseTypeError as exc:
            if must_name not in str(exc):
                out.append("%s was refused without naming %r: %s"
                           % (what, must_name, exc))
            continue
        out.append("%s was accepted" % what)
    # The negative control for this check: an addition that CAN be honoured.
    ok, why = corrected(w, base, reference(w, TWORING, "tworing"))
    if ok is None:
        out.append("an ordinary further exemplar was refused: %s" % why)
    return out


# ── 7. a document that contradicts its own evidence is refused on load ───────
def check_incoherent_document_is_refused(w):
    """Three hand edits to a corrected file, each refused rather than read."""
    out = []
    # `NEAR` and not the C-grid: it is separable on `median` and on nothing
    # else, so an edit that loosens the median bound really does leave the
    # document accepting the mesh it declares it must reject. With the C-grid
    # the hand-set `max` bound would still refuse it and the edit would be
    # refused for a reason that is nothing to do with this check.
    added, why = corrected(w, authored(w),
                           reference(w, NEAR, "near",
                                     kind=w.case_type.COUNTER))
    if added is None:
        return [why]
    base = added.case_type.to_dict()

    def mutate(fn):
        doc = json.loads(json.dumps(base))
        fn(doc)
        return doc

    def nudged_bound(doc):
        # Nudged by 10%, not replaced with a round number: a bound raised past
        # its own `unusable` would be refused by the band rule instead, and the
        # check would pass for a reason nothing to do with the evidence.
        doc["thresholds"][0]["attention"] *= 1.1

    def shrunken_support(doc):
        doc["thresholds"][0]["measured_from"]["references"] = ["ogrid_circle"]

    def loosened_bound(doc):
        # The `unusable` bound raised until it accepts the counter-example the
        # document itself declares, WITH its factor dropped so the derivation
        # check has nothing to say about it. This is the edit a maintainer who
        # disagreed with a correction would make by hand.
        row = [t for t in doc["thresholds"] if t["key"] == "median"][0]
        row["unusable"] = 99.0
        row["measured_from"].pop("unusable_factor", None)

    def exemplar_rejected(doc):
        row = [t for t in doc["thresholds"] if t["key"] == "median"][0]
        row["attention"] = 1.0
        row["unusable"] = 1.0
        row["measured_from"].pop("attention_factor", None)
        row["measured_from"].pop("unusable_factor", None)

    for fn, what in ((nudged_bound, "a bound that is not its own derivation"),
                     (shrunken_support,
                      "a support with a mesh taken out of it"),
                     (loosened_bound,
                      "an unusable bound that accepts the file's own "
                      "counter-example"),
                     (exemplar_rejected,
                      "a bound that rejects the file's own exemplar")):
        try:
            doc = mutate(fn)
        except (KeyError, IndexError) as exc:
            out.append("%s cannot be built: the corrected document carries no "
                       "%s" % (what, exc))
            continue
        try:
            w.case_type.CaseType.from_dict(doc)
        except w.case_type.CaseTypeError as exc:
            if not str(exc).strip():
                out.append("%s was refused with an empty message" % what)
            continue
        out.append("%s was accepted" % what)
    try:
        w.case_type.CaseType.from_dict(base)
    except w.case_type.CaseTypeError as exc:
        out.append("the corrected document itself does not load: %s" % exc)
    return out


# ── 8. one comparison, two askers ────────────────────────────────────────────
def check_one_comparison(w):
    """`judge_threshold` spells no `>` of its own; both sides call `exceeds`."""
    out = []
    tree = ast.parse(w.src["case_type_verdict"])
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef)
                and node.name == "judge_threshold"):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Compare) and any(
                    isinstance(op, (ast.Gt, ast.GtE, ast.Lt, ast.LtE))
                    for op in inner.ops):
                out.append("judge_threshold spells its own comparison at line "
                           "%d; `case_type_reference.exceeds` is the one owner, "
                           "and a second spelling is free to drift from the one "
                           "every reference mesh is checked with" % inner.lineno)
        break
    else:
        out.append("case_type_verdict.judge_threshold is gone; this check reads "
                   "it by name")
    # Behavioural, not only structural: the two really do agree about a mesh
    # sitting exactly ON its bound.
    th = w.case_type.Threshold("median", "a", attention=2.0, unusable=4.0)
    on_it = summary(dict(whole=dict(cells=1, median=2.0, p95=1.0, maximum=1.0)))
    if w.verdict.judge_threshold(th, on_it).state != w.verdict.USABLE:
        out.append("a figure exactly ON its bound is not accepted, so the "
                   "separating bound could place a boundary nothing honours")
    if w.reference.exceeds(2.0, 2.0) or not w.reference.exceeds(2.000001, 2.0):
        out.append("`exceeds` is not strictly greater")
    return out


# ── 9. Qt-free ───────────────────────────────────────────────────────────────
def check_qt_free(w):
    code = ("import sys; sys.path.insert(0, %r);"
            "import app.services.case_type_evidence;"
            "sys.exit(1 if 'PyQt6' in sys.modules else 0)" % _GUI)
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=_REPO)
    if proc.returncode == 0:
        return []
    return ["services/case_type_evidence.py pulls in PyQt6: %s%s"
            % (proc.stdout, proc.stderr)]


# ── 10. the shipped case type demonstrates the correction ────────────────────
def check_shipped_demonstrates_it(w):
    out = []
    try:
        shipped = w.case_type.load(os.path.join(_REPO, _SHIPPED))
    except w.case_type.CaseTypeError as exc:
        return ["%s does not load: %s" % (_SHIPPED, exc)]
    kinds = {r.kind for r in shipped.references}
    if kinds != set(w.case_type.KINDS):
        return out + ["%s declares %s; the shipped example is meant to "
                      "demonstrate both kinds of evidence" % (_SHIPPED, kinds)]
    for th in shipped.thresholds:
        if len(th.measured_from.references) < 2:
            out.append("%s's %s threshold rests on %s, so the shipped file "
                       "shows no correction"
                       % (_SHIPPED, th.key, list(th.measured_from.references)))
    manual = [(t.key, b) for t in shipped.thresholds for b in w.case_type.BOUNDS
              if t.origin_of(b) == w.case_type.MANUAL]
    if len(manual) != 1:
        out.append("%s carries %d hand-set bound(s); it is meant to show one "
                   "surviving a correction: %s" % (_SHIPPED, len(manual),
                                                   manual))
    for ref in shipped.references:
        figs = CGRID if ref.kind == w.case_type.COUNTER else OGRID
        want = (w.verdict.UNUSABLE if ref.kind == w.case_type.COUNTER
                else w.verdict.USABLE)
        got = w.verdict.judge(shipped, summary(figs), 0)
        if got.state != want:
            out.append("%s's %s '%s' is %r under it, not %r"
                       % (_SHIPPED, ref.kind, ref.ident, got.state, want))
        if ref.figure("median") != figs["whole"]["median"]:
            out.append("%s's '%s' records a median of %r; this gate's fixture "
                       "says %r, so the two no longer describe one mesh"
                       % (_SHIPPED, ref.ident, ref.figure("median"),
                          figs["whole"]["median"]))
    return out


# ── 11. a counter-example never WIDENS a bound ───────────────────────────────
def check_addition_never_widens(w):
    """A mesh that separates on one figure does not loosen another.

    FOUND BY REVIEW, and it was a real defect rather than a hypothetical: `cap`
    was the minimum over EVERY counter-example, so adding one that sits BELOW
    the exemplars on a figure dropped that figure's cap under `base`, the
    hold-down vanished wholesale, and the bound sprang back to `base * factor`
    — silently discarding the restraint an earlier counter-example had placed.
    A correction that loosens a threshold is the opposite of what the
    maintainer asked for, and the only visible sign was a refusal message
    quoting a bound the file did not contain.
    """
    out = []
    first, why = corrected(w, authored(w),
                           reference(w, CGRID, "cgrid",
                                     kind=w.case_type.COUNTER))
    if first is None:
        return [why]
    held = {t.key: (t.attention, t.unusable) for t in first.case_type.thresholds}
    second, why = corrected(w, first.case_type,
                            reference(w, LOPSIDED, "lopsided",
                                      kind=w.case_type.COUNTER))
    if second is None:
        return ["a counter-example separable on one figure was refused: %s" % why]
    for th in second.case_type.thresholds:
        was_a, was_u = held[th.key]
        for bound, was in (("attention", was_a), ("unusable", was_u)):
            now = getattr(th, bound)
            if was is not None and now is not None and now > was:
                out.append("%s's %s bound WIDENED from %.6g to %.6g when a "
                           "counter-example was added" % (th.key, bound, was, now))
    # ...and the mesh that placed the original restraint is still rejected.
    for ident, figs in (("cgrid", CGRID), ("lopsided", LOPSIDED)):
        if w.verdict.judge(second.case_type, summary(figs), 0).state \
                != w.verdict.UNUSABLE:
            out.append("counter-example %s is no longer rejected once a second "
                       "one was added" % ident)
    # The positive half, or this check would pass on a case type that simply
    # never moves: the figure the new mesh DOES separate on came down.
    narrowed = [k for k, (a, u) in held.items()
                for t in second.case_type.thresholds
                if t.key == k and t.unusable is not None and u is not None
                and t.unusable < u]
    if not narrowed:
        out.append("no bound narrowed either, so this check cannot tell "
                   "'never widens' from 'never moves'")
    return out


# ── run ──────────────────────────────────────────────────────────────────────
_ALL = {
    1: check_addition_moves_the_thresholds,
    2: check_counter_example_is_rejected,
    3: check_support_is_reported,
    4: check_finished_case_is_frozen,
    5: check_override_survives_the_addition,
    6: check_contradiction_is_refused,
    7: check_incoherent_document_is_refused,
    8: check_one_comparison,
    9: check_qt_free,
    10: check_shipped_demonstrates_it,
    11: check_addition_never_widens,
}

_LABELS = {
    1: "check 1. a further reference mesh is added in ONE command, and the thresholds adjust",
    2: "check 2. a counter-example is REJECTED by the thresholds, and the exemplars still pass",
    3: "check 3. every threshold reports which reference meshes it rests on",
    4: "check 4. correcting a case type does not alter an already-finished case's verdict",
    5: "check 5. a hand-overridden threshold is not silently recomputed",
    6: "check 6. a self-contradictory addition is refused, naming the conflict",
    7: "check 7. a document that contradicts its own evidence is refused on load",
    8: "check 8. one comparison, two askers: the verdict and the evidence agree by construction",
    9: "check 9. the evidence service is Qt-free, measured in a subprocess",
    10: "check 10. the shipped case type demonstrates a correction made with evidence",
    11: "check 11. a counter-example never WIDENS a bound another one placed",
}

_REAL = world()

for num in sorted(_ALL):
    fails = _ALL[num](_REAL)
    check(not fails, _LABELS[num])
    for f in fails:
        print("      " + str(f).replace("\n", "\n      "), flush=True)


# ── injections ───────────────────────────────────────────────────────────────
# Checks 1, 3 and 9 launch a SUBPROCESS against the real files on disk, so an
# in-memory mutant cannot reach part of what they measure; including them in
# `others_green` would score them as evidence when they are measuring something
# else. Check 1 is excused entirely, check 3 and 9 likewise.
_SKIP_UNDER_MUTATION = (1, 3, 9)


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


inj = mutate("case_type_evidence",
             "        return want if limit is None or want <= limit else limit",
             "        return want")
check(inj.evidence.Evidence(
          "median", base=1.0, cap=2.0, idents=("a", "b")).bound(3.0) == 3.0,
      "injection A. injection is well-formed: a derived bound may now sit above "
      "the counter-example it is supposed to reject")
check(check_counter_example_is_rejected(inj)
      and check_finished_case_is_frozen(inj)
      and check_incoherent_document_is_refused(inj)
      and check_shipped_demonstrates_it(inj)
      and check_addition_never_widens(inj)
      and others_green(inj, 2, 4, 7, 10, 11),
      "injection A. checks 2, 4, 7, 10 and 11 fail together when a bound stops "
      "being held down to the separating bound — a counter-example nothing can "
      "reject, a correction that therefore cannot be made at all, a document "
      "that no longer follows from its own evidence, a shipped file whose "
      "median bound stops being its derivation, and every bound springing back "
      "to its unheld value. All five asserted to move rather than four being "
      "excused")

inj = mutate("case_type_author", '''        if factor is None:
            bounds[bound] = getattr(threshold, bound)
            continue''',
             '''        if factor is None:
            factor = DEFAULT_UNUSABLE_FACTOR''')
check(check_override_survives_the_addition(inj)
      and check_contradiction_is_refused(inj) and others_green(inj, 5, 6),
      "injection B. checks 5 and 6 fail together when a bound with no tolerance "
      "factor is re-derived anyway — the maintainer's own judgement silently "
      "replaced by the arithmetic it was written to overrule, and with it the "
      "two refusals that exist precisely because that judgement is untouchable")

inj = mutate("case_type_evidence",
             "    by_key = {th.key: th for th in thresholds}",
             "    return []\n    by_key = {th.key: th for th in thresholds}")
check(not inj.evidence.standing_failures([], []),
      "injection C. injection is well-formed: nothing is ever found wrong with "
      "a case type's standing")
check(check_contradiction_is_refused(inj)
      and check_incoherent_document_is_refused(inj)
      and others_green(inj, 6, 7),
      "injection C. checks 6 and 7 fail together when a case type may contradict "
      "its own evidence — every refusal in this ticket accepted, including the "
      "one a hand-set bound makes impossible, and the same document accepted on "
      "load. Both asserted to move")

inj = mutate("case_type_reference", '        out = {"references": list(self.references)}',
             '        out = {"references": list(self.references)[:1]}')
check(check_support_is_reported(inj)
      and check_incoherent_document_is_refused(inj) and others_green(inj, 7),
      "injection D. checks 3 and 7 fail when only the FIRST mesh of a support "
      "is written — a threshold that can no longer say what it rests on, which "
      "is the whole of user story 39, and a document this build writes and "
      "cannot read back")

inj = mutate("case_type_author", "        kind=kind,", "        kind=case_type_mod.EXEMPLAR,")
check(check_counter_example_is_rejected(inj)
      and check_support_is_reported(inj)
      and check_finished_case_is_frozen(inj)
      and check_contradiction_is_refused(inj)
      and check_incoherent_document_is_refused(inj)
      and check_addition_never_widens(inj)
      and others_green(inj, 2, 4, 6, 7, 11),
      "injection F. checks 2, 3, 4, 6, 7 and 11 fail when the kind a mesh was "
      "measured as is dropped: a counter-example recorded as an exemplar WIDENS "
      "the bounds it was added to tighten, which is a correction doing the "
      "opposite of what the maintainer asked for. Six of eleven, named rather "
      "than narrowed — the kind is what every rule in this ticket is about, so "
      "a mutation that loses it is not a mutation one check can isolate")

inj = mutate("case_type_evidence",
             "        separating = ([c for c in counters if base is not None and c > base])",
             "        separating = list(counters)")
check(check_addition_never_widens(inj) and others_green(inj, 11),
      "injection E. check 11 ALONE fails when `cap` goes back to the minimum "
      "over EVERY counter-example: one that sits below the exemplars on a "
      "figure drops that figure's cap under `base`, the hold-down vanishes and "
      "the bound springs back — a correction that LOOSENS a threshold. This is "
      "the defect the review found, kept as the injection that proves it stays "
      "fixed")

inj = mutate("case_type_verdict", "    if case_type_mod.exceeds(value, threshold.unusable):",
             "    if threshold.unusable is not None and value > threshold.unusable:")
check(check_one_comparison(inj) and others_green(inj, 8),
      "injection G. check 8 ALONE fails when the verdict spells its own "
      "comparison again — the drift this ticket's standing check cannot afford, "
      "since it is what makes `rejected` mean the same thing in both places")

inj = mutate("mesh_commit",
             '        case_type.save(trial.verdict.case_type, sidecars["case_type"])',
             "        pass")
check(check_finished_case_is_frozen(inj) and others_green(inj, 4),
      "injection H. check 4 ALONE fails when a committed case stops embedding "
      "the whole case type — a finished verdict that could only be explained "
      "from a file which has since moved on, which is user story 42 and the "
      "mechanism behind user story 43")

# I reaches the one file the in-memory mutants cannot: the HOST, which runs as a
# subprocess. Without it check 1 — the acceptance criterion that a reference
# mesh can be added to an existing case type — would be the only check here
# never shown able to go red.
_host_src = _read(_HOST)
_anchor = "        dest = args.out or args.case_type"
assert _anchor in _host_src, "host injection anchor not found: %r" % _anchor
with tempfile.TemporaryDirectory() as _tmp:
    _mutant = os.path.join(_tmp, "add_reference_mesh_mutant.py")
    with open(_mutant, "w", encoding="utf-8") as _fh:
        _fh.write(_host_src.replace(
            _anchor, '        dest = args.out or args.case_type + ".new"', 1))
    check(check_addition_moves_the_thresholds(_REAL, host=_mutant),
          "injection I. check 1 fails when the HOST writes the corrected case "
          "type BESIDE the one it was given instead of over it, so the "
          "maintainer's file is never corrected — the one check here an "
          "in-memory mutant cannot reach, now shown able to go red")
    check(not check_addition_moves_the_thresholds(_REAL),
          "injection I. ...and the UNmutated host still passes it, so the "
          "failure above is the mutation and not the copy or its PYTHONPATH")

check(not any(fn(_REAL) for num, fn in _ALL.items()),
      "injection J. negative control: the unmutated six pass every check, so "
      "the failures above are the mutations and not the checker")

print("\n%s: %d check(s) failed" % (os.path.basename(__file__), len(_FAILS))
      if _FAILS else "\nAll checks passed.", flush=True)
sys.exit(1 if _FAILS else 0)
