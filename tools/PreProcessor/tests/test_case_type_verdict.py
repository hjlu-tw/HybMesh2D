#!/usr/bin/env python3
"""A CASE TYPE holds thresholds; the VERDICT is four states (issue #160, parent #158).

The tracer bullet for the case-type workflow. `services/case_type.py` is the
artefact — a name, the metric its numbers are about, its thresholds and the
advice for missing each one — and `services/case_type_verdict.py` grades one
finished mesh from the figures the mesher published, the mesher's exit code and
those thresholds. The mesher itself is NOT touched: per
`docs/adr/0002-thresholds-live-in-case-types.md` it keeps measuring and keeps
refusing to grade, and the thresholds live one layer up where they can be scoped
to a class of problem.

THE FOURTH STATE IS THE POINT OF THE GATE. The mesher returns NEGATIVE — never
0.0 — for anything it could not measure and prints `not measured`, precisely so
that "we did not measure" never reads as "it came out perfect". A verdict layer
that collapsed an unmeasured figure into a pass would spend that rule for
nothing, so check 4 asserts `not determinable` for EVERY ONE of the nine figure
keys a threshold can name, and check 7 asserts it OUTRANKS `needs attention`
rather than being averaged away by two good figures beside it.

What this pins down:

  1. THE EXIT CODE IS NOT A SECOND SPELLING. `EXIT_ERR_INVERTED` is read out of
     `include/ExitCodes.hpp`'s own enum and compared with the Python mirror, so
     the number cannot drift the way a hand-copied constant does.
  2. THE ARTEFACT IS A FILE, and the round trip is exact over all nine keys,
     both bounds and the advice. The SHIPPED case type loads and is not vacuous.
  3. ALL FOUR STATES ARE REACHABLE, each from a constructed input, and they are
     four distinct strings — three states plus an error would be the shape this
     ticket exists to refuse.
  4. A NEGATIVE FIGURE IS `not determinable`, NEVER `usable`, PER KEY. All nine,
     plus the six split keys read against a sidecar that carries no split: an
     absent half and an unmeasured one are both "cannot judge", and neither is
     a pass.
  5. `EXIT_ERR_INVERTED` IS `unusable` REGARDLESS. Asserted against figures that
     would otherwise be usable, against no published figures at all, and against
     a case type with no thresholds — the mesher exports a folded mesh under its
     ordinary filename by design, so nothing downstream may out-vote the code.
  6. A VERDICT IS CHECKABLE. It names the key, the measurement, the bound it
     crossed, the absolute gap AND the ratio, and quotes the case type's own
     advice verbatim — "needs attention" with no advice is the dead end user
     story 13 exists against.
  7. WORST WINS, IN THE RIGHT ORDER: unusable > not determinable > needs
     attention > usable, each asserted against a mix that contains the ones
     below it.
  8. A MALFORMED CASE TYPE IS REFUSED, NOT PARTLY READ. Eight documents, each
     raising with a message that names what is wrong. A threshold key nobody
     evaluates, or a bound misspelled into a key nobody reads, is a threshold
     that silently stops biting.
  9. NEITHER HOST GRADES ANYTHING ITSELF. Both the GUI's mesh controller and
     `services/pipeline_runner` call `case_type_verdict.run_report`, and neither
     file spells a verdict state, a threshold comparison or a log grade of its
     own — which is what makes "the same service" a fact rather than a claim.
 10. QT-FREE, in a subprocess: importing either service leaves PyQt6 unimported.
     In-process the answer is always "loaded" once anything else imported it.
 11. THE GUI REALLY EMITS IT, driven through `_on_mesh_gen_finished` with a
     recording host: the verdict reaches `log_report` as ONE graded message at
     the service's own grade, and a cancelled run (an out-of-band sentinel, not
     a mesher exit code) emits none.
 12. THE HEADLESS HOST REALLY EMITS IT, end to end through `run_pipeline.sh` on
     a shipped `MESH_MODE 1` script with `HYBMESH_CASE_TYPE` set — skipped
     without a build tree — plus, with no binary, the structural half: the call
     sits ABOVE the guard that raises on a non-zero exit, so exit 9's `unusable`
     is said rather than only raised on.
 13. THE SHIPPED CASE TYPE IS NOT VACUOUS: `examples/case_types/ogrid_circle.casetype.json`
     reads the shipped O-grid's published figures (median 1.845977, p95
     23.662285, max 32.767868; bulk 1.692763 / 1.877756 / 1.881891, measured
     2026-09-30) as `usable`, and one bound tightened by hand moves it off that.
 14. A VERDICT NAMES THE FILE THAT ISSUED IT when the case type came from one,
     and claims no file when it did not — `CaseType.source` is kept for
     traceability and a field nobody prints cannot provide it. It is also the
     only record of WHICH case type a run used, the interim environment-variable
     channel leaving none.

Known blind spots, named rather than papered over:
  - Nothing here judges whether a THRESHOLD IS RIGHT. The shipped one's numbers
    are hand-authored round figures above the shipped O-grid's measurements;
    #161 is what makes a threshold a measurement times a tolerance, and #168
    what corrects one with evidence. This gate holds the machinery, not the
    numbers.
  - Check 9 reads the hosts' SOURCE. A third host that grew its own grading
    would be invisible to it; the deny-list shape that would catch one belongs
    with the picker #162 builds.
  - The GUI check drives the controller method with a recording stand-in for the
    main window, not a real one. That it is wired to a button, and that the log
    panel renders it, is `smoke_headless_appcontroller.py`'s territory.
  - `HYBMESH_CASE_TYPE` is an INTERIM channel owned by #160 and replaced by
    #162's picker; check 12 pins the plumbing, not the way a user will choose.

INJECTIONS — AUTOMATED, by exec'ing a mutated copy of the service source and
re-running the same check functions against it. Each asserts the mutation is
well-formed and really differs, then that the named check fails AND that no
other check moves (`others_green`), so a mutation that reddens everything cannot
be scored as proof about one check:

  A. the Python mirror of `EXIT_ERR_INVERTED` changed to 99 -> check 1 fails.
  B. the exit-9 short circuit deleted, so a folded run falls through to the
     figures -> check 5 fails. The defect ADR-0002 exists against.
  C. `if not figures.measured` turned off, so a negative figure is compared as a
     number -> checks 4 AND 7 fail, the second because its mixture feeds an
     unmeasured half on purpose. Both are asserted to move; nothing else does.
     The negative-measurement rule, spent.
  D. `not determinable` ranked BELOW `needs attention` -> check 7 fails: one
     unmeasurable figure beside two good ones reported as the milder state.
  E. the advice line dropped from `report_lines` -> check 6 fails.
  F. the empty-advice refusal removed from `Threshold` -> check 8 fails.
  G. the metric-mismatch short circuit deleted, so a `tri_edge_ratio` mesh is
     read against `quad_midline_ratio` thresholds -> check 3 fails (that input
     is how `not determinable` is reached there) — #130's "comparing nothing".
  H. negative control: the unmutated pair passes every check, so the failures
     above are the mutations and not the checker.
  I. the `from <file>` line dropped from `report_lines` -> check 14 fails: a
     `source` nobody prints is not the traceability it is kept for.
  J. one state removed from `_LEVELS` -> check 3 fails. `STATES` is DERIVED from
     `_RANK` and so cannot drift from it; `_LEVELS` is the map that can, and a
     state missing from it reaches a host as a KeyError off `Verdict.level`.

Run:  python3 tools/PreProcessor/tests/test_case_type_verdict.py
Needs no build tree for checks 1-11 and 13; check 12's end-to-end half skips
without one.
"""
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_CT_REL = "tools/PreProcessor/gui/app/services/case_type.py"
_V_REL = "tools/PreProcessor/gui/app/services/case_type_verdict.py"
_HOSTS = {
    "pipeline_runner": "tools/PreProcessor/gui/app/services/pipeline_runner.py",
    "mesh_gen_ctrl": "tools/PreProcessor/gui/app/controllers/mesh_gen_ctrl.py",
}
_SHIPPED = "examples/case_types/ogrid_circle.casetype.json"
_EXITCODES = "include/ExitCodes.hpp"

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _read(rel):
    with open(os.path.join(_REPO, rel), encoding="utf-8") as fh:
        return fh.read()


_CT_SRC = _read(_CT_REL)
_V_SRC = _read(_V_REL)
_HOST_SRC = {k: _read(v) for k, v in _HOSTS.items()}

# --- the world: a FRESH pair of service modules, optionally mutated ----------
# Every check below is a pure function of this pair, which is what makes the
# injections cheap: exec a mutated copy, ask the same function. The real world
# is loaded through the same path as a mutant, so the negative control and the
# injections are symmetric rather than one going through `import`.
_SERVICE_NAMES = ("app.services.case_type", "app.services.case_type_verdict")


def _exec_module(name, rel, source):
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = os.path.join(_REPO, rel)
    sys.modules[name] = mod
    # The PACKAGE attribute too: `from app.services import case_type` resolves
    # through `getattr(app.services, ...)` first, so a mutant left only in
    # sys.modules would be shadowed by the real module the package already
    # holds — and the injection would silently test the real code.
    pkg = sys.modules.get("app.services")
    if pkg is not None:
        setattr(pkg, name.rsplit(".", 1)[1], mod)
    exec(compile(source, mod.__file__, "exec"), mod.__dict__)
    return mod


def world(ct_src=None, v_src=None):
    """A `(case_type, case_type_verdict)` pair built from the given source."""
    import app.services  # noqa: F401  - ensure the package exists to patch
    saved_mods = {n: sys.modules.get(n) for n in _SERVICE_NAMES}
    pkg = sys.modules["app.services"]
    saved_attrs = {n.rsplit(".", 1)[1]: getattr(pkg, n.rsplit(".", 1)[1], None)
                   for n in _SERVICE_NAMES}
    try:
        ct = _exec_module(_SERVICE_NAMES[0], _CT_REL, ct_src or _CT_SRC)
        vd = _exec_module(_SERVICE_NAMES[1], _V_REL, v_src or _V_SRC)
        return ct, vd
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

#: The shipped O-grid's published figures, read off its sidecar on 2026-09-30.
OGRID = dict(cells=4608, median=1.845977, p95=23.662285, maximum=32.767868)
OGRID_LAYER = dict(cells=2304, median=5.184358, p95=28.507718, maximum=32.767868)
OGRID_BULK = dict(cells=2304, median=1.692763, p95=1.877756, maximum=1.881891)
#: What the mesher writes for a set it looked at and could not measure: the
#: count 0 and the three figures NEGATIVE together (include/CellShape.hpp).
UNMEASURED = dict(cells=0, median=-1.0, p95=-1.0, maximum=-1.0)


def summary(metric="quad_midline_ratio", whole=None, layer=None, bulk=None):
    """A `ShapeSummary` as the sidecar reader would have produced one."""
    whole = dict(OGRID if whole is None else whole)
    return mesh_shape_stats.ShapeSummary(
        metric=metric, source="<constructed>",
        layer=None if layer is None else mesh_shape_stats.ShapeFigures(**layer),
        bulk=None if bulk is None else mesh_shape_stats.ShapeFigures(**bulk),
        **whole)


def split_summary(metric="quad_midline_ratio", whole=None, layer=None, bulk=None):
    return summary(metric,
                   OGRID if whole is None else whole,
                   OGRID_LAYER if layer is None else layer,
                   OGRID_BULK if bulk is None else bulk)


def case_type_with(ct, *thresholds, name="Test type", metric="quad_midline_ratio"):
    return ct.CaseType(name, metric, list(thresholds))


def all_key_type(ct, **bounds):
    """A case type carrying one threshold on EVERY figure key."""
    return ct.CaseType("Every key", "quad_midline_ratio", [
        ct.Threshold(k, "advice for %s" % k, **bounds) for k in ct.FIGURE_KEYS])


# --- checks -------------------------------------------------------------------
def check_exit_code_parity(w):
    ct, vd = w
    hpp = _read(_EXITCODES)
    m = re.search(r"EXIT_ERR_INVERTED\s*=\s*(\d+)", hpp)
    if not m:
        return ["%s declares no EXIT_ERR_INVERTED to compare against" % _EXITCODES]
    if int(m.group(1)) != vd.EXIT_ERR_INVERTED:
        return ["EXIT_ERR_INVERTED is %d in %s and %d in %s"
                % (int(m.group(1)), _EXITCODES, vd.EXIT_ERR_INVERTED, _V_REL)]
    return []


def check_file_round_trip(w):
    ct, vd = w
    out = []
    original = all_key_type(ct, attention=2.0, unusable=4.0)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "rt.casetype.json")
        ct.save(original, path)
        back = ct.load(path)
        if back.to_dict() != original.to_dict():
            out.append("a case type does not survive save -> load unchanged")
        if back.source != path:
            out.append("a loaded case type does not record where it came from")
        if [t.advice for t in back.thresholds] != [t.advice for t in original.thresholds]:
            out.append("the per-threshold advice did not survive the round trip")
    shipped = ct.load(os.path.join(_REPO, _SHIPPED))
    if not shipped.thresholds:
        out.append("%s carries no thresholds" % _SHIPPED)
    if not shipped.metric:
        out.append("%s names no metric" % _SHIPPED)
    if any(not t.advice for t in shipped.thresholds):
        out.append("%s has a threshold with no advice" % _SHIPPED)
    return out


def check_verdict_names_its_file(w):
    """A verdict says WHICH case type file judged, when it came from one."""
    ct, vd = w
    out = []
    shipped_path = os.path.join(_REPO, _SHIPPED)
    v = vd.judge(ct.load(shipped_path), split_summary(), 0)
    if shipped_path not in vd.report_text(v):
        out.append("a verdict from a LOADED case type does not name its file")
    # A case type built in memory has no file, and the line is then absent
    # rather than present and empty.
    v2 = vd.judge(all_key_type(ct, attention=1e9), split_summary(), 0)
    if "from " in vd.report_text(v2):
        out.append("a verdict from a case type with no file claims one anyway")
    return out


def check_four_states(w):
    """Each state from a constructed input, and the four are distinct."""
    ct, vd = w
    good = ct.Threshold("max", "loosen the first cell", attention=50.0, unusable=200.0)
    tight = ct.Threshold("max", "loosen the first cell", attention=10.0, unusable=20.0)
    warn = ct.Threshold("max", "loosen the first cell", attention=10.0, unusable=200.0)
    reached = {
        vd.USABLE: vd.judge(case_type_with(ct, good), summary(), 0),
        vd.NEEDS_ATTENTION: vd.judge(case_type_with(ct, warn), summary(), 0),
        vd.UNUSABLE: vd.judge(case_type_with(ct, tight), summary(), 0),
        # Reached by the input #130 says is nonsense: a mesh measured with the
        # OTHER path's metric, which these thresholds do not describe.
        vd.NOT_DETERMINABLE: vd.judge(case_type_with(ct, good),
                                      summary(metric="tri_edge_ratio"), 0),
    }
    out = []
    for want, got in reached.items():
        if got.state != want:
            out.append("expected %r, got %r" % (want, got.state))
    if len(set(vd.STATES)) != 4:
        out.append("STATES does not hold four distinct names: %r" % (vd.STATES,))
    if set(reached) != set(vd.STATES):
        out.append("the four reachable states are not the four declared ones")
    # `STATES` is DERIVED from `_RANK`, so those two cannot disagree; `_LEVELS`
    # is a separate map over the same keys and is the one that can go stale —
    # a state missing from it reaches a host as a KeyError off `Verdict.level`.
    if set(vd._LEVELS) != set(vd.STATES):
        out.append("_LEVELS does not grade every state: %r vs %r"
                   % (sorted(vd._LEVELS), sorted(vd.STATES)))
    return out


def check_negative_is_not_determinable(w):
    """Per figure key: unmeasurable -> not determinable, and never usable."""
    ct, vd = w
    out = []
    unmeasured_all = summary(whole=UNMEASURED, layer=UNMEASURED, bulk=UNMEASURED)
    for key in ct.FIGURE_KEYS:
        th = ct.Threshold(key, "advice", attention=2.0, unusable=4.0)
        v = vd.judge(case_type_with(ct, th), unmeasured_all, 0)
        if v.state != vd.NOT_DETERMINABLE:
            out.append("an unmeasured %s gives %r, not %r"
                       % (key, v.state, vd.NOT_DETERMINABLE))
        if not v.reasons or "could not be judged" not in v.reasons[0].describe():
            out.append("an unmeasured %s does not SAY it could not be judged" % key)
    # The same per key when ONE set is unmeasured and the others are good: the
    # verdict must not be rescued by the figures beside it.
    for set_name, kwargs in (("layer", dict(layer=UNMEASURED)),
                             ("bulk", dict(bulk=UNMEASURED)),
                             ("", dict(whole=UNMEASURED))):
        s = split_summary(**kwargs)
        for field in ("median", "p95", "max"):
            key = ("%s.%s" % (set_name, field)) if set_name else field
            th = ct.Threshold(key, "advice", attention=1000.0)
            v = vd.judge(case_type_with(ct, th), s, 0)
            if v.state == vd.USABLE:
                out.append("an unmeasured %s read as USABLE against a loose bound" % key)
    # A sidecar with NO split at all: the six half keys cannot be judged either,
    # and that is not the same answer as a measured half that met its bound.
    no_split = summary()
    for key in [k for k in ct.FIGURE_KEYS if "." in k]:
        th = ct.Threshold(key, "advice", attention=1000.0)
        v = vd.judge(case_type_with(ct, th), no_split, 0)
        if v.state != vd.NOT_DETERMINABLE:
            out.append("%s on a sidecar with no split gives %r" % (key, v.state))
    return out


def check_inverted_is_unusable(w):
    """Exit 9 outranks every figure, every threshold and an absent sidecar."""
    ct, vd = w
    out = []
    loose = ct.Threshold("max", "advice", attention=1e9, unusable=1e9)
    cases = {
        "figures that would otherwise pass": (case_type_with(ct, loose), split_summary()),
        "no published figures at all": (case_type_with(ct, loose), None),
        "a case type with no thresholds": (ct.CaseType("Bare", "quad_midline_ratio"), split_summary()),
        "the wrong metric": (case_type_with(ct, loose), summary(metric="tri_edge_ratio")),
        "an unmeasured mesh": (case_type_with(ct, loose), summary(whole=UNMEASURED)),
    }
    for what, (c, s) in cases.items():
        v = vd.judge(c, s, vd.EXIT_ERR_INVERTED)
        if v.state != vd.UNUSABLE:
            out.append("exit %d with %s gives %r, not %r"
                       % (vd.EXIT_ERR_INVERTED, what, v.state, vd.UNUSABLE))
    v = vd.judge(case_type_with(ct, loose), split_summary(), vd.EXIT_ERR_INVERTED)
    if v.level != "ERROR":
        out.append("an unusable verdict is not logged at ERROR (got %r)" % v.level)
    if "inverted" not in vd.report_text(v):
        out.append("the unusable verdict does not say the mesh holds inverted cells")
    return out


def check_verdict_is_checkable(w):
    """It names the key, the measurement, the bound, the gap and the advice."""
    ct, vd = w
    advice = "Put more points round the body."
    th = ct.Threshold("max", advice, attention=10.0, unusable=200.0)
    v = vd.judge(case_type_with(ct, th), summary(), 0)
    text = vd.report_text(v)
    out = []
    for token in ("max", "32.768", "10.000", "22.768", "x3.277", advice):
        if token not in text:
            out.append("the verdict does not carry %r: %r" % (token, text))
    if "needs-attention" not in text:
        out.append("the verdict does not name WHICH bound was crossed")
    if "0 of 1 thresholds met" not in text:
        out.append("the headline does not count the thresholds that were met: %r"
                   % text.splitlines()[0])
    return out


def check_worst_wins(w):
    """unusable > not determinable > needs attention > usable, on mixtures."""
    ct, vd = w
    out = []
    ok = ct.Threshold("median", "advice", attention=1000.0)
    warn = ct.Threshold("max", "advice", attention=10.0)
    bad = ct.Threshold("p95", "advice", unusable=10.0)
    nd = ct.Threshold("bulk.p95", "advice", attention=1000.0)
    s = split_summary(bulk=UNMEASURED)
    ladder = [
        ([ok], vd.USABLE),
        ([ok, warn], vd.NEEDS_ATTENTION),
        ([ok, warn, nd], vd.NOT_DETERMINABLE),
        ([ok, warn, nd, bad], vd.UNUSABLE),
    ]
    for ths, want in ladder:
        got = vd.judge(case_type_with(ct, *ths), s, 0).state
        if got != want:
            out.append("%s -> %r, expected %r" % ([t.key for t in ths], got, want))
    if vd._RANK[vd.NOT_DETERMINABLE] <= vd._RANK[vd.NEEDS_ATTENTION]:
        out.append("`not determinable` does not outrank `needs attention`")
    return out


def check_malformed_is_refused(w):
    """Eight bad documents, each refused with a message naming the problem."""
    ct, _vd = w
    base = {"schema": ct.SCHEMA, "version": ct.SCHEMA_VERSION,
            "name": "T", "metric": "quad_midline_ratio", "thresholds": []}
    good_th = {"key": "max", "attention": 2.0, "advice": "a"}

    def doc(**over):
        d = dict(base)
        d.update(over)
        return d

    bad = {
        "an unknown figure key": doc(thresholds=[dict(good_th, key="nonortho_max")]),
        "a threshold with no advice": doc(thresholds=[dict(good_th, advice="  ")]),
        "a threshold with neither bound": doc(thresholds=[{"key": "max", "advice": "a"}]),
        "an unusable bound below the attention one":
            doc(thresholds=[{"key": "max", "attention": 5.0, "unusable": 2.0, "advice": "a"}]),
        "two thresholds on one figure": doc(thresholds=[good_th, dict(good_th)]),
        "a misspelled bound": doc(thresholds=[{"key": "max", "atention": 2.0, "advice": "a"}]),
        "a document that is not a case type": doc(schema="something-else"),
        "a schema version this build does not read": doc(version=ct.SCHEMA_VERSION + 1),
    }
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for what, document in bad.items():
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(document, fh)
            try:
                ct.load(path)
            except ct.CaseTypeError:
                continue
            out.append("%s was accepted" % what)
        path = os.path.join(tmp, "broken.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        try:
            ct.load(path)
            out.append("a file that is not JSON was accepted")
        except ct.CaseTypeError:
            pass
    return out


def _calls(tree, module, func):
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == func and isinstance(n.func.value, ast.Name)
            and n.func.value.id == module]


def check_hosts_do_not_grade(w):
    """Both hosts call the service; neither spells a rule of its own."""
    _ct, vd = w
    out = []
    banned = set(vd.STATES) | {"attention", "unusable"}
    for host, src in _HOST_SRC.items():
        tree = ast.parse(src)
        if not _calls(tree, "case_type_verdict", "run_report"):
            out.append("%s does not call case_type_verdict.run_report" % host)
        literals = {n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        spelled = sorted(literals & banned)
        if spelled:
            out.append("%s spells a verdict word of its own: %s"
                       % (host, ", ".join(spelled)))
        for name in ("judge", "judge_threshold", "report_lines", "report_text"):
            if _calls(tree, "case_type_verdict", name):
                out.append("%s reaches past run_report to %s" % (host, name))
    return out


def check_qt_free(w):
    _ct, _vd = w
    out = []
    for mod in ("app.services.case_type", "app.services.case_type_verdict"):
        p = subprocess.run(
            [sys.executable, "-c",
             "import sys; __import__(%r); print('PyQt6' in sys.modules)" % mod],
            cwd=_GUI, capture_output=True, text=True)
        if p.returncode != 0 or p.stdout.strip() != "False":
            out.append("%s is not Qt-free (rc=%d, said %r)"
                       % (mod, p.returncode, p.stdout.strip()))
    return out


def check_gui_emits_verdict(w):
    """Drive the controller's finish handler and read what it logged."""
    _ct, vd = w
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from app.controllers.mesh_gen_ctrl import MeshGenControllerMixin

    class _Any:
        """A main window that answers every call and records nothing."""
        def __getattr__(self, _name):
            return _Any()

        def __call__(self, *_a, **_k):
            return _Any()

    class _Host(MeshGenControllerMixin):
        def __init__(self):
            self.main_window = _Any()
            self.global_vtk_mesh = None
            self.global_vtk_path = ""
            self._pending_after_mesh = None
            self.reports = []
            self.lines = []

        def log(self, message, level=None):
            self.lines.append(str(message))

        def log_report(self, message, level="ERROR"):
            self.reports.append((str(message), level))

    out = []
    with tempfile.TemporaryDirectory() as tmp:
        mesh = os.path.join(tmp, "m.vtk")
        open(mesh, "w").close()
        _write_sidecar(mesh, metric="quad_midline_ratio")
        ct_path = os.path.join(tmp, "t.casetype.json")
        _write_case_type(ct_path, attention=10.0, unusable=200.0)
        os.environ["HYBMESH_CASE_TYPE"] = ct_path
        try:
            host = _Host()
            host._on_mesh_gen_finished(0, os.path.join(tmp, "absent.dat"), mesh)
            verdicts = [r for r in host.reports if r[0].startswith("Verdict:")]
            if len(verdicts) != 1:
                out.append("the GUI logged %d verdicts, expected exactly one (%r)"
                           % (len(verdicts), host.reports))
            else:
                text, level = verdicts[0]
                if vd.NEEDS_ATTENTION not in text:
                    out.append("the GUI's verdict is not the service's: %r" % text)
                if level != "WARNING":
                    out.append("the GUI graded it %r, not the service's WARNING" % level)
                if "\n" not in text:
                    out.append("the GUI's verdict carries no advice line")
            # A cancelled run is not a mesher exit code and must be judged by
            # nothing: a verdict about a run the user stopped is an answer
            # about nothing.
            from app.workers.exit_codes import RC_CANCELLED
            host2 = _Host()
            host2._on_mesh_gen_finished(RC_CANCELLED, os.path.join(tmp, "absent.dat"), mesh)
            if any(r[0].startswith("Verdict:") for r in host2.reports):
                out.append("a cancelled run produced a verdict")
        finally:
            os.environ.pop("HYBMESH_CASE_TYPE", None)
    return out


def check_headless_emits_verdict(w):
    """The call sits above the guard that raises, and a real run says it."""
    _ct, vd = w
    out = []
    src = _HOST_SRC["pipeline_runner"]
    call = src.find("case_type_verdict.run_report")
    guard = src.find('raise PipelineError(f"HybMesh2D failed')
    if call < 0 or guard < 0 or call > guard:
        out.append("the verdict is not reported BEFORE the non-zero-exit guard, "
                   "so exit 9's `unusable` would only ever be raised on")
    exe = os.path.join(_REPO, "build", "HybMesh2D")
    if not os.path.isfile(exe):
        print("      (skipping the end-to-end half: no build tree)", flush=True)
        return out
    with tempfile.TemporaryDirectory() as tmp:
        ct_path = os.path.join(tmp, "t.casetype.json")
        _write_case_type(ct_path, attention=10.0, unusable=1e9)
        env = dict(os.environ, HYBMESH_CASE_TYPE=ct_path)
        p = subprocess.run(
            ["./run_pipeline.sh", "config/pipeline/multiblock_cgrid_demo.json",
             "--no-solver"],
            cwd=_REPO, env=env, capture_output=True, text=True, timeout=600)
        if "Verdict: " not in p.stdout:
            out.append("a real headless run reported no verdict (rc=%d)" % p.returncode)
        elif vd.NEEDS_ATTENTION not in p.stdout:
            out.append("the headless verdict is not the service's wording")
    return out


def check_shipped_case_type(w):
    """The shipped case type reads the shipped O-grid as usable, and can move."""
    ct, vd = w
    shipped = ct.load(os.path.join(_REPO, _SHIPPED))
    out = []
    v = vd.judge(shipped, split_summary(metric=shipped.metric), 0)
    if v.state != vd.USABLE:
        out.append("the shipped case type calls the shipped O-grid %r: %s"
                   % (v.state, vd.report_text(v)))
    if v.checked != len(shipped.thresholds):
        out.append("the shipped case type evaluated %d of its %d thresholds"
                   % (v.checked, len(shipped.thresholds)))
    # Not vacuous: one bound tightened by hand moves the verdict off `usable`,
    # so the three thresholds are bounds and not decoration.
    tightened = ct.CaseType(shipped.name, shipped.metric, [
        ct.Threshold(t.key, t.advice, attention=1.0, unusable=t.unusable)
        for t in shipped.thresholds])
    if vd.judge(tightened, split_summary(), 0).state == vd.USABLE:
        out.append("tightening every bound to 1.0 still reads as usable")
    return out


# --- fixtures used by the host checks -----------------------------------------
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


def _write_case_type(path, attention, unusable):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"schema": "hybmesh-case-type", "version": 1,
                   "name": "Gate type", "metric": "quad_midline_ratio",
                   "thresholds": [{"key": "max", "attention": attention,
                                   "unusable": unusable,
                                   "advice": "Put more points round the body."}]},
                  fh)


# --- run ----------------------------------------------------------------------
_ALL = {
    1: check_exit_code_parity, 2: check_file_round_trip, 3: check_four_states,
    4: check_negative_is_not_determinable, 5: check_inverted_is_unusable,
    6: check_verdict_is_checkable, 7: check_worst_wins,
    8: check_malformed_is_refused, 9: check_hosts_do_not_grade,
    10: check_qt_free, 11: check_gui_emits_verdict,
    12: check_headless_emits_verdict, 13: check_shipped_case_type,
    14: check_verdict_names_its_file,
}

_LABELS = {
    1: "check 1. EXIT_ERR_INVERTED agrees with include/ExitCodes.hpp",
    2: "check 2. a case type round-trips through a file, and the shipped one loads",
    3: "check 3. all FOUR verdict states are reachable from constructed inputs",
    4: "check 4. an unmeasurable figure is `not determinable`, never usable — per key",
    5: "check 5. EXIT_ERR_INVERTED (9) is `unusable` regardless of every other figure",
    6: "check 6. a verdict names the measurement, the bound, the gap and the advice",
    7: "check 7. worst wins: unusable > not determinable > needs attention > usable",
    8: "check 8. a malformed case type is refused, not partly read",
    9: "check 9. neither host grades anything itself; both call run_report",
    10: "check 10. both service modules are Qt-free, measured in a subprocess",
    11: "check 11. the GUI really emits the verdict, at the service's own grade",
    12: "check 12. the headless host really emits it, before the guard that raises",
    13: "check 13. the shipped case type reads the shipped O-grid as usable",
    14: "check 14. a verdict names the case type FILE that issued it, when there is one",
}

_REAL = world()

for num in sorted(_ALL):
    fails = _ALL[num](_REAL)
    check(not fails, _LABELS[num])
    for f in fails:
        print("      " + f.replace("\n", "\n      "), flush=True)


# --- injections ---------------------------------------------------------------
# Every check is a pure function of the module pair, so an injection is a
# mutated copy of the source exec'd into a fresh pair. The structural checks (9
# and 12) read the HOSTS rather than the services and so do not move under a
# service mutation; they are excluded from `others_green` only when a mutation
# genuinely reaches them, which none of these do.
_SKIP_UNDER_MUTATION = (10, 11, 12)  # subprocess / real-import / real-run checks


def others_green(w, *reddened):
    """True when every check BUT the named ones still passes on the mutant.

    #127's "isolate the labelled check", asserted ACROSS checks: a mutation that
    reddens the whole file proves nothing about the one it was written for. The
    three excluded checks import or run the REAL module from disk and so cannot
    see an in-memory mutant at all — including them would score them as
    evidence when they are measuring something else.
    """
    return not any(fn(w) for num, fn in _ALL.items()
                   if num not in reddened and num not in _SKIP_UNDER_MUTATION)


def mutate(which, old, new, count=1):
    src = _V_SRC if which == "v" else _CT_SRC
    assert old in src, "injection anchor not found: %r" % old
    mutated = src.replace(old, new, count)
    assert mutated != src
    return world(v_src=mutated) if which == "v" else world(ct_src=mutated)


inj = mutate("v", "EXIT_ERR_INVERTED = 9", "EXIT_ERR_INVERTED = 99")
check(inj[1].EXIT_ERR_INVERTED == 99,
      "injection A. injection is well-formed: the Python mirror really reads 99")
check(check_exit_code_parity(inj) and others_green(inj, 1),
      "injection A. check 1 fails when the Python mirror drifts off "
      "include/ExitCodes.hpp, and no other check moves")

inj = mutate("v", "    if exit_code == EXIT_ERR_INVERTED:", "    if False:")
check(inj[1].judge(case_type_with(inj[0], inj[0].Threshold("max", "a", attention=1e9)),
                   split_summary(), 9).state != inj[1].UNUSABLE,
      "injection B. injection is well-formed: a folded run now falls through to "
      "the figures instead of short-circuiting")
check(check_inverted_is_unusable(inj) and others_green(inj, 5),
      "injection B. check 5 ALONE fails when the exit-9 refusal is gone — the "
      "folded mesh ADR-0002 says must never reach an operator looking normal")

inj = mutate("v", "    if not figures.measured:", "    if False:")
check(check_negative_is_not_determinable(inj),
      "injection C. check 4 fails when a negative figure is compared as a number: "
      "the negative-measurement rule the mesher paid for, spent at this layer")
check(check_worst_wins(inj) and others_green(inj, 4, 7),
      "injection C. and the ONE other check it moves is 7, which feeds it an "
      "unmeasured set on purpose — asserted to move rather than merely excused")

inj = mutate("v", "_RANK = {USABLE: 0, NEEDS_ATTENTION: 1, NOT_DETERMINABLE: 2, UNUSABLE: 3}",
             "_RANK = {USABLE: 0, NOT_DETERMINABLE: 1, NEEDS_ATTENTION: 2, UNUSABLE: 3}")
check(inj[1]._RANK[inj[1].NOT_DETERMINABLE] < inj[1]._RANK[inj[1].NEEDS_ATTENTION],
      "injection D. injection is well-formed: `not determinable` now ranks below "
      "`needs attention`")
check(check_worst_wins(inj) and others_green(inj, 7),
      "injection D. check 7 ALONE fails: one unmeasurable figure beside two good "
      "ones would be reported as the milder state")

inj = mutate("v", '            lines.append("    try: " + reason.advice)',
             "            pass")
check(check_verdict_is_checkable(inj) and others_green(inj, 6),
      "injection E. check 6 ALONE fails when the advice is dropped from the "
      "report — `needs attention` with nothing to try is user story 13's dead end")

inj = mutate("ct", '        if not str(advice).strip():', '        if False:')
check(check_malformed_is_refused(inj) and others_green(inj, 8),
      "injection F. check 8 ALONE fails when a threshold may carry no advice")

inj = mutate("v", "    if summary.metric != case_type.metric:", "    if False:")
check(check_four_states(inj) and others_green(inj, 3),
      "injection G. check 3 ALONE fails when a tri_edge_ratio mesh is read "
      "against quad_midline_ratio thresholds — #130's comparing nothing")

inj = mutate("v", '        lines.append("  from " + verdict.case_type.source)',
             "        pass")
check(check_verdict_names_its_file(inj) and others_green(inj, 14),
      "injection I. check 14 ALONE fails when the verdict stops naming the file "
      "that issued it — a `source` nobody prints cannot be the traceability it "
      "is kept for")

inj = mutate("v", '_LEVELS = {USABLE: "INFO", NEEDS_ATTENTION: "WARNING",',
             '_LEVELS = {NEEDS_ATTENTION: "WARNING",')
check(set(inj[1]._LEVELS) != set(inj[1].STATES),
      "injection J. injection is well-formed: one state really has no grade now")
check(check_four_states(inj) and others_green(inj, 3, 5, 13, 14),
      "injection J. check 3 fails when `_LEVELS` stops grading every state — the "
      "map `STATES` is NOT derived from, so it is the one that can go stale; the "
      "other three that move are the ones that read `Verdict.level`")

check(not any(fn(_REAL) for num, fn in _ALL.items()),
      "injection H. negative control: the unmutated pair passes every check, so "
      "the failures above are the mutations and not the checker")


print("\n%s: %d check(s) failed" % (os.path.basename(__file__), len(_FAILS))
      if _FAILS else "\nAll checks passed.", flush=True)
sys.exit(1 if _FAILS else 0)
