#!/usr/bin/env python3
"""A THRESHOLD IS MEASURED FROM A REFERENCE MESH (issue #161, parent #158).

#160 gave a case type thresholds and a four-state verdict, and left the numbers
hand-written round figures above a measurement — which that gate named as its
first blind spot. This ticket is what closes it: the maintainer builds a case
they are happy with, saves it as a case type in ONE action, and the tool MEASURES
that mesh and bakes its figures into bounds by applying a tolerance factor,
recording which mesh every bound came from.

WHY THAT IS THE WHOLE POINT. The maintainer knows which mesh is good; they do
not necessarily know what its p95 is. A threshold derived from a mesh is a
DEMONSTRATION — six months later it is still traceable to the mesh it came from,
which is `docs/adr/0002-thresholds-live-in-case-types.md`'s first consequence
and the reason a misjudged verdict is corrected by adding evidence (#168) rather
than by editing a number.

What this pins down:

  1. ONE ACTION, AND IT IS A REAL ONE. `tools/PreProcessor/save_case_type.py` is
     driven as a SUBPROCESS over a mesh and its sidecar: exit 0, a file on disk,
     and that file loads as a case type whose thresholds are the ones asked for.
  2. MEASURED, NOT TYPED, PER KEY. Every derived bound is its reference mesh's
     own published figure times the stated factor, asserted over all NINE figure
     keys and both bounds — and the FILE states the factor, so the derivation is
     re-checkable rather than a claim about how the number was produced.
  3. THE PROVENANCE SURVIVES THE FILE. The reference mesh — its id, the mesh, the
     sidecar, the date and all nine figures — comes back identical through
     save -> load, and every threshold still names it.
  4. AN OVERRIDE IS DISTINGUISHABLE FROM A MEASUREMENT, and it is the file's
     SHAPE that distinguishes it: a bound with a factor beside it reads
     `measured`, one without reads `manual`. An override keeps the reference, so
     what it overrode is still on the record, and an empty override removes the
     bound rather than setting it to nothing.
  5. ADVICE IS THE SELECTION AND IS REQUIRED. A figure nobody wrote advice for
     gets no threshold; no advice at all is refused; an override naming a figure
     with no advice is refused rather than silently doing nothing.
  6. A FIGURE THE REFERENCE MESH COULD NOT MEASURE PRODUCES NO THRESHOLD, and
     the skip is REPORTED. Asserted for an unmeasured half, for an absent half
     and for a whole mesh that measured nothing — never a bound derived from the
     negative number the mesher writes for exactly this case.
  7. THE REFERENCE MESH IS `usable` UNDER THE CASE TYPE IT AUTHORED, which is
     what a tolerance factor of at least 1.0 MEANS, and a factor below 1.0 is
     refused because it would make the mesh the maintainer judged good fail the
     case type they authored from it. The authored file is loaded by #160's
     verdict service unchanged and reaches `needs attention` and `unusable` too.
  8. A FILE THAT DISAGREES WITH ITSELF IS REFUSED, NOT PARTLY READ. Seven
     documents: a bound that is not its own derivation, a factor below 1.0, an
     origin naming a reference the case type does not declare, one naming a
     figure that reference never published, a reference measured with the other
     path's metric, two references sharing an id, and a reference recording a
     NEGATIVE figure.
  9. A HAND-WRITTEN CASE TYPE IS STILL LEGAL. A v1 document loads, declares no
     reference and reads `manual` on every bound — the artefact GREW rather than
     being replaced. The SHIPPED case type is the other side: v2, measured from
     a declared reference, with exactly one bound overridden by hand.
 10. QT-FREE, in a subprocess: importing the authoring service leaves PyQt6
     unimported. In-process the answer is always "loaded" once anything else
     imported it.

Known blind spots, named rather than papered over:
  - Nothing here judges whether a TOLERANCE FACTOR is right. 1.5 and 3.0 are
    defaults a maintainer overrides; what is gated is that the bound really is
    the product, not that the product is a good place for a bound. #168 is what
    corrects a misjudged one with evidence.
  - The reference mesh's FIGURES are taken from the sidecar reader, which has
    its own gate. Nothing here re-measures a mesh, by design: a threshold
    derived from one reading and judged against another would be the defect.
  - Check 1 drives the CLI, not a GUI action. Saving a case type from the window
    is #162's, which owns the picker this ticket's hosts do without.

INJECTIONS — AUTOMATED, by exec'ing a mutated copy of the three service sources
and re-running the same check functions against the mutant. Each asserts the
mutation is well-formed and really differs, then that the named check fails AND
that no other check moves (`others_green`):

  A. `Origin.REL_TOL` widened to 1e9, so a bound need no longer BE its own
     derivation -> check 8 fails. The invariant that makes "measured" a fact.
  B. the factor-below-1.0 refusal removed -> check 7 fails: a case type its own
     reference mesh does not pass.
  C. `measured_figures` stops asking `figures.measured`, so the mesher's
     negative sentinel is recorded as a figure -> check 6 fails. The
     negative-measurement rule, spent one layer further out than #160 spent it.
  D. `origin_of` answers `measured` for every set bound -> check 4 fails: an
     override indistinguishable from a measurement.
  E. the undeclared-reference refusal removed -> check 8 fails: provenance
     pointing at nothing.
  F. `Threshold.to_dict` drops `measured_from` -> checks 2, 3, 4 AND 8 fail,
     all four asserted to move: a threshold that cannot say where it came from,
     and check 8 builds its documents by writing an authored one out.
  G. the stray-override refusal removed -> check 5 fails: an override the
     maintainer believes they set and that changes nothing.
  H. `ReferenceMesh.to_dict` stops writing the mesh, the sidecar and the date ->
     check 3 fails: a reference recording its numbers and not which mesh they
     came from, which is a threshold traceable to nothing.
  I. negative control: the unmutated trio passes every check.

Two injections were RETARGETED after they passed for the wrong reason, which is
what `others_green` is for and is recorded rather than quietly fixed: A's
document first raised its bound to a round 99.0, which the band rule refused
before the derivation was ever compared; and H first emptied `figures`, which
`ReferenceMesh` refuses outright, so it reddened every check that loads a file
instead of the one it was written for.

Run:  python3 tools/PreProcessor/tests/test_case_type_author.py
Needs no build tree, no Qt and no network.
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

_HOST = os.path.join("tools", "PreProcessor", "save_case_type.py")
_SHIPPED = os.path.join("examples", "case_types", "ogrid_circle.casetype.json")

#: name -> repo-relative source, in DEPENDENCY order: the figures and the
#: provenance, then the document, then the authoring step.
_RELS = [
    ("app.services.case_type_reference",
     "tools/PreProcessor/gui/app/services/case_type_reference.py"),
    ("app.services.case_type",
     "tools/PreProcessor/gui/app/services/case_type.py"),
    ("app.services.case_type_author",
     "tools/PreProcessor/gui/app/services/case_type_author.py"),
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


# --- the world: a FRESH trio of service modules, optionally mutated -----------
# Every check is a pure function of this trio, which is what makes the
# injections cheap: exec a mutated copy, ask the same function. The real world
# is loaded through the same path as a mutant, so the negative control and the
# injections are symmetric rather than one going through `import`.
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
    """A `(case_type, case_type_author)` pair built from the given source.

    `mutated` is keyed by the LAST segment of a module name, so a caller writes
    `world(case_type_author=src)` rather than spelling the package out.
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
        return built["case_type"], built["case_type_author"]
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


from app.services import case_type_verdict as verdict  # noqa: E402
from app.services import mesh_shape_stats  # noqa: E402

#: The shipped O-grid's published figures, read off its sidecar on 2026-09-30 —
#: the same numbers `test_case_type_verdict.py` uses, so the two gates cannot
#: describe two different meshes.
OGRID = dict(cells=4608, median=1.845977, p95=23.662285, maximum=32.767868)
OGRID_LAYER = dict(cells=2304, median=5.184358, p95=28.507718, maximum=32.767868)
OGRID_BULK = dict(cells=2304, median=1.692763, p95=1.877756, maximum=1.881891)
#: What the mesher writes for a set it looked at and could not measure: the
#: count 0 and the three figures NEGATIVE together (include/CellShape.hpp).
UNMEASURED = dict(cells=0, median=-1.0, p95=-1.0, maximum=-1.0)

ADVICE = {"median": "Put more points round the body.",
          "max": "Ask for a less aggressive first cell.",
          "bulk.p95": "Spread the radial spacing law out."}


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


def _reference(w, summ=None, ident="ogrid", measured_on="2026-09-30"):
    """The shipped O-grid as a `ReferenceMesh`, through the real measuring step.

    `w` rather than a module read out of `sys.modules`: `world()` restores both
    on the way out, so a helper that looked the module up would build against
    the REAL code while the check holds the mutant — and every injection would
    quietly measure nothing.
    """
    ct, au = w
    summ = split_summary() if summ is None else summ
    return ct.ReferenceMesh(ident=ident, metric=summ.metric,
                            figures=au.measured_figures(summ),
                            mesh="results/meshes/ogrid.vtk",
                            provenance="results/meshes/ogrid.provenance.json",
                            measured_on=measured_on)


def authored(w, advice=None, **kw):
    """The ordinary authoring action, as every check below starts from it."""
    ct, au = w
    ref = _reference(w)
    return ref, au.author("O-grid", ref, dict(ADVICE if advice is None else advice), **kw)


# --- checks -------------------------------------------------------------------
def check_one_action(w):
    """The CLI really turns a finished mesh into a case type, in one command."""
    ct, au = w
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        mesh = os.path.join(tmp, "mesh_demo.vtk")
        with open(mesh, "w", encoding="utf-8") as fh:
            fh.write("# vtk DataFile Version 3.0\n")
        _write_sidecar(mesh)
        dest = os.path.join(tmp, "demo.casetype.json")
        advice_file = os.path.join(tmp, "advice.json")
        with open(advice_file, "w", encoding="utf-8") as fh:
            json.dump(ADVICE, fh)
        proc = subprocess.run(
            [sys.executable, os.path.join(_REPO, _HOST), mesh,
             "--name", "Demo type", "--out", dest,
             "--advice-from", advice_file,
             "--reference-id", "demo", "--measured-on", "2026-09-30"],
            capture_output=True, text=True, cwd=_REPO)
        if proc.returncode != 0:
            return ["%s exited %d: %s" % (_HOST, proc.returncode, proc.stderr)]
        if not os.path.isfile(dest):
            return ["%s exited 0 and wrote no case type" % _HOST]
        saved = ct.load(dest)
        if saved.name != "Demo type":
            out.append("the case type is named %r, not the name asked for"
                       % saved.name)
        if sorted(t.key for t in saved.thresholds) != sorted(ADVICE):
            out.append("the saved thresholds are %s, not the figures advice was "
                       "supplied for" % [t.key for t in saved.thresholds])
        if [r.ident for r in saved.references] != ["demo"]:
            out.append("the saved case type declares references %s"
                       % [r.ident for r in saved.references])
        for key, text in ADVICE.items():
            got = [t.advice for t in saved.thresholds if t.key == key]
            if got != [text]:
                out.append("the advice for %s did not reach the file: %r"
                           % (key, got))
    return out


def check_bounds_are_measured(w):
    """Every derived bound IS the reference figure times its stated factor."""
    ct, au = w
    out = []
    every = {k: "advice for %s" % k for k in ct.FIGURE_KEYS}
    ref, result = authored(w, advice=every, attention_factor=1.25,
                           unusable_factor=2.5)
    case_type = result.case_type
    if sorted(t.key for t in case_type.thresholds) != sorted(ct.FIGURE_KEYS):
        return ["a fully measured reference mesh did not bound all %d figures: %s"
                % (len(ct.FIGURE_KEYS), [t.key for t in case_type.thresholds])]
    for th in case_type.thresholds:
        value = ref.figure(th.key)
        for bound, factor in (("attention", 1.25), ("unusable", 2.5)):
            stated = getattr(th, bound)
            if abs(stated - value * factor) > 1e-12 * max(value * factor, 1.0):
                out.append("%s's %s bound is %r, not its measurement %r x %r"
                           % (th.key, bound, stated, value, factor))
            if th.measured_from.factor_for(bound) != factor:
                out.append("%s's %s bound does not state the factor it used"
                           % (th.key, bound))
    # The FILE carries the factor, so the derivation is re-checkable off disk
    # rather than being a claim about how the number was produced.
    doc = case_type.to_dict()
    for raw in doc["thresholds"]:
        if "attention_factor" not in raw.get("measured_from", {}):
            out.append("%s is written without the factor it was derived with"
                       % raw["key"])
    return out


def check_provenance_round_trip(w):
    """The reference mesh, whole, survives save -> load, and is still named."""
    ct, au = w
    out = []
    ref, result = authored(w)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "rt.casetype.json")
        ct.save(result.case_type, path)
        try:
            back = ct.load(path)
        except ct.CaseTypeError as exc:
            # A document this build WROTE and cannot read back is the roundest
            # failure of this check there is, not an error to propagate.
            return ["an authored case type does not load back: %s" % exc]
    if back.to_dict() != result.case_type.to_dict():
        out.append("an authored case type does not survive save -> load")
    if len(back.references) != 1:
        return out + ["the reference mesh did not survive the file: %s"
                      % back.references]
    got = back.references[0]
    for field in ("ident", "metric", "mesh", "provenance", "measured_on"):
        if getattr(got, field) != getattr(ref, field):
            out.append("the reference mesh's %s did not survive: %r vs %r"
                       % (field, getattr(got, field), getattr(ref, field)))
    if got.figures != ref.figures:
        out.append("the reference mesh's figures did not survive: %r vs %r"
                   % (got.figures, ref.figures))
    if len(got.figures) != len(ct.FIGURE_KEYS):
        out.append("a fully measured reference recorded %d of %d figures"
                   % (len(got.figures), len(ct.FIGURE_KEYS)))
    for th in back.thresholds:
        if th.measured_from is None or th.measured_from.reference != ref.ident:
            out.append("threshold %s no longer names the mesh it came from"
                       % th.key)
        elif back.reference(th.measured_from.reference) is None:
            out.append("threshold %s names a reference the file does not carry"
                       % th.key)
    return out


def check_override_is_distinguishable(w):
    """A hand-set bound reads `manual`; a derived one reads `measured`."""
    ct, au = w
    out = []
    ref, result = authored(w, overrides={"max": {"unusable": 200.0},
                                         "median": {"attention": None}})
    by_key = {t.key: t for t in result.case_type.thresholds}
    if by_key["max"].unusable != 200.0:
        out.append("the override did not set the bound: %r"
                   % by_key["max"].unusable)
    if by_key["max"].origin_of("unusable") != ct.MANUAL:
        out.append("an overridden bound reads %r, not %r"
                   % (by_key["max"].origin_of("unusable"), ct.MANUAL))
    if by_key["max"].origin_of("attention") != ct.MEASURED:
        out.append("the UNtouched bound of an overridden threshold reads %r"
                   % by_key["max"].origin_of("attention"))
    if by_key["max"].measured_from.reference != ref.ident:
        out.append("an override threw the reference away")
    if by_key["median"].attention is not None:
        out.append("an empty override did not REMOVE the bound: %r"
                   % by_key["median"].attention)
    if by_key["median"].origin_of("attention") is not None:
        out.append("a bound that is not set reads %r rather than nothing"
                   % by_key["median"].origin_of("attention"))
    # And it survives the file, which is where a flag could drift from the
    # number beside it: the factor is simply absent for the overridden bound.
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ov.casetype.json")
        ct.save(result.case_type, path)
        raw = json.load(open(path, encoding="utf-8"))
        back = {t["key"]: t for t in raw["thresholds"]}
        if "unusable_factor" in back["max"].get("measured_from", {}):
            out.append("an overridden bound is written with a factor anyway")
        if "attention_factor" not in back["max"].get("measured_from", {}):
            out.append("the measured bound beside an override lost its factor")
        try:
            loaded = ct.load(path)
        except ct.CaseTypeError as exc:
            return out + ["an authored case type does not load back: %s" % exc]
        got = {t.key: t for t in loaded.thresholds}
        if got["max"].origin_of("unusable") != ct.MANUAL:
            out.append("the override is not distinguishable after a round trip")
        if got["max"].origin_of("attention") != ct.MEASURED:
            out.append("the measurement is not distinguishable after a round trip")
    return out


def check_advice_selects_and_is_required(w):
    """Advice picks the figures bounded, and nothing is bounded without it."""
    ct, au = w
    out = []
    _, result = authored(w, advice={"max": "only this one"})
    keys = [t.key for t in result.case_type.thresholds]
    if keys != ["max"]:
        out.append("advice for one figure produced thresholds on %s" % keys)
    for advice, overrides, what in (
            ({}, None, "no advice at all"),
            ({"max": "   "}, None, "advice that is only whitespace"),
            ({"max": "ok"}, {"median": {"attention": 2.0}},
             "an override for a figure with no advice"),
            ({"max": "ok"}, {"max": {"atention": 2.0}},
             "an override naming a bound that does not exist"),
            ({"nonesuch": "ok"}, None, "advice for a figure nobody publishes")):
        try:
            authored(w, advice=advice, overrides=overrides)
        except ct.CaseTypeError:
            continue
        out.append("%s was accepted" % what)
    return out


def check_unmeasured_figure_has_no_threshold(w):
    """A figure the reference could not measure produces NO bound, and says so."""
    ct, au = w
    out = []
    every = {k: "advice for %s" % k for k in ct.FIGURE_KEYS}
    cases = (
        ("an unmeasured layer", split_summary(layer=UNMEASURED),
         [k for k in ct.FIGURE_KEYS if k.startswith("layer.")]),
        ("a sidecar with no split", summary(),
         [k for k in ct.FIGURE_KEYS if "." in k]),
    )
    for what, summ, absent in cases:
        try:
            ref = _reference(w, summ=summ)
            result = au.author("O-grid", ref, dict(every))
        except ct.CaseTypeError as exc:
            # A refusal is not "produces no threshold" either: the other eight
            # figures were measured, and a case type must still come out of them.
            out.append("%s: authoring raised rather than leaving the "
                       "unmeasured figures unbounded: %s" % (what, exc))
            continue
        for key in absent:
            if ref.figure(key) is not None:
                out.append("%s: the reference recorded %s as %r"
                           % (what, key, ref.figure(key)))
        bounded = {t.key for t in result.case_type.thresholds}
        leaked = sorted(bounded & set(absent))
        if leaked:
            out.append("%s: %s got a threshold anyway" % (what, leaked))
        for th in result.case_type.thresholds:
            for bound in ct.BOUNDS:
                value = getattr(th, bound)
                if value is not None and value <= 0.0:
                    out.append("%s: %s's %s bound is %r, derived from a "
                               "negative measurement" % (what, th.key, bound, value))
        if sorted(k for k, _ in result.skipped) != sorted(absent):
            out.append("%s: the skips reported were %s, not %s"
                       % (what, [k for k, _ in result.skipped], absent))
        for key, why in result.skipped:
            if not str(why).strip():
                out.append("%s: the skip of %s says nothing" % (what, key))
    # A mesh that measured NOTHING is not a reference mesh at all, and the
    # refusal is where it is noticed — not an empty case type nobody can use.
    nothing = summary(whole=UNMEASURED)
    try:
        _reference(w, summ=nothing)
        out.append("a mesh that measured nothing was accepted as a reference")
    except ct.CaseTypeError:
        pass
    return out


def check_authored_type_produces_verdicts(w):
    """#160's verdict service loads it, and the reference mesh passes it."""
    ct, au = w
    out = []
    ref, result = authored(w, attention_factor=1.5, unusable_factor=3.0)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "v.casetype.json")
        saved = au.save_case_type(result, path)
        try:
            loaded = ct.load(path)
        except ct.CaseTypeError as exc:
            return ["an authored case type does not load back: %s" % exc]
    if saved.case_type.source != path:
        out.append("a saved case type does not know the file it was written to")
    # The property a factor of at least 1.0 MEANS: the mesh the maintainer
    # judged good is usable under the case type measured from it.
    v = verdict.judge(loaded, split_summary(), 0)
    if v.state != verdict.USABLE:
        out.append("the reference mesh is %r under the case type it authored: %s"
                   % (v.state, verdict.report_text(v)))
    if v.checked != len(loaded.thresholds):
        out.append("the verdict evaluated %d of %d thresholds"
                   % (v.checked, len(loaded.thresholds)))
    # ...and the bounds are not decoration: past attention, then past unusable.
    worse = dict(OGRID_BULK)
    worse["p95"] = ref.figure("bulk.p95") * 2.0
    v2 = verdict.judge(loaded, split_summary(bulk=worse), 0)
    if v2.state != verdict.NEEDS_ATTENTION:
        out.append("a figure at 2x its measurement reads %r" % v2.state)
    worse["p95"] = ref.figure("bulk.p95") * 10.0
    v3 = verdict.judge(loaded, split_summary(bulk=worse), 0)
    if v3.state != verdict.UNUSABLE:
        out.append("a figure at 10x its measurement reads %r" % v3.state)
    if not any(ADVICE["bulk.p95"] in line for line in verdict.report_lines(v3)):
        out.append("the authored advice does not reach the verdict's report")
    # A factor BELOW 1.0 is the same statement from the other side.
    for factor in ({"attention_factor": 0.9}, {"unusable_factor": 0.5}):
        try:
            authored(w, **factor)
            out.append("a tolerance factor below 1.0 (%s) was accepted, so the "
                       "reference mesh would fail its own case type" % factor)
        except ct.CaseTypeError:
            pass
    return out


def check_incoherent_file_is_refused(w):
    """Seven documents that disagree with themselves, each refused on load."""
    ct, au = w
    out = []
    _, result = authored(w)
    base = result.case_type.to_dict()

    def mutate(fn):
        """The authored document with one thing about it made incoherent.

        A `KeyError` here is not a crash to be caught quietly: it means the
        authored document does not carry the field this check is about, which is
        a failure of this check and not of the one that writes it.
        """
        doc = json.loads(json.dumps(base))
        fn(doc)
        return doc

    def set_bound(doc):
        # Nudged by 10%, not replaced with a round number: a bound raised past
        # its own `unusable` would be refused by the band rule instead, and the
        # check would pass for a reason that is nothing to do with provenance.
        doc["thresholds"][0]["attention"] *= 1.1

    def low_factor(doc):
        doc["thresholds"][0]["measured_from"]["attention_factor"] = 0.5

    def stray_reference(doc):
        doc["thresholds"][0]["measured_from"]["reference"] = "nosuch"

    def unpublished_figure(doc):
        doc["reference_meshes"][0]["figures"].pop(doc["thresholds"][0]["key"])

    def other_metric(doc):
        doc["reference_meshes"][0]["metric"] = "tri_edge_ratio"

    def duplicate_id(doc):
        doc["reference_meshes"].append(json.loads(
            json.dumps(doc["reference_meshes"][0])))

    def negative_figure(doc):
        doc["reference_meshes"][0]["figures"]["p95"] = -1.0

    for fn, what in ((set_bound, "a bound that is not its own derivation"),
                     (low_factor, "a tolerance factor below 1.0"),
                     (stray_reference, "an origin naming an undeclared reference"),
                     (unpublished_figure,
                      "an origin naming a figure its reference never published"),
                     (other_metric, "a reference measured with another metric"),
                     (duplicate_id, "two reference meshes sharing an id"),
                     (negative_figure, "a reference recording a negative figure")):
        try:
            doc = mutate(fn)
        except KeyError as exc:
            out.append("%s cannot be built: the authored document carries no %s"
                       % (what, exc))
            continue
        try:
            ct.CaseType.from_dict(doc)
        except ct.CaseTypeError as exc:
            if not str(exc).strip():
                out.append("%s was refused with an empty message" % what)
            continue
        out.append("%s was accepted" % what)
    # The negative control for this check: the UNmutated document still loads.
    try:
        ct.CaseType.from_dict(base)
    except ct.CaseTypeError as exc:
        out.append("the authored document itself does not load: %s" % exc)
    return out


def check_hand_written_still_legal(w):
    """A v1 document loads as all-manual; the shipped v2 is measured."""
    ct, au = w
    out = []
    v1 = {"schema": ct.SCHEMA, "version": 1, "name": "Hand written",
          "metric": "quad_midline_ratio",
          "thresholds": [{"key": "max", "attention": 50.0, "unusable": 200.0,
                          "advice": "Put more points round the body."}]}
    try:
        hand = ct.CaseType.from_dict(v1)
    except ct.CaseTypeError as exc:
        return ["a v1 case type no longer loads: %s" % exc]
    if hand.references:
        out.append("a v1 case type came back declaring references")
    for bound in ct.BOUNDS:
        if hand.thresholds[0].origin_of(bound) != ct.MANUAL:
            out.append("a hand-written bound reads %r, not %r"
                       % (hand.thresholds[0].origin_of(bound), ct.MANUAL))
    shipped = ct.load(os.path.join(_REPO, _SHIPPED))
    if len(shipped.references) != 1:
        return out + ["%s declares %d reference meshes, not 1"
                      % (_SHIPPED, len(shipped.references))]
    origins = [(t.key, b, t.origin_of(b)) for t in shipped.thresholds
               for b in ct.BOUNDS if getattr(t, b) is not None]
    measured = [o for o in origins if o[2] == ct.MEASURED]
    manual = [o for o in origins if o[2] == ct.MANUAL]
    if not measured:
        out.append("%s carries no MEASURED bound, so #161 did not reach it"
                   % _SHIPPED)
    if len(manual) != 1:
        out.append("%s carries %d hand-set bound(s); the shipped example is "
                   "meant to demonstrate exactly one override: %s"
                   % (_SHIPPED, len(manual), manual))
    ref = shipped.references[0]
    for th in shipped.thresholds:
        if ref.figure(th.key) is None:
            out.append("%s bounds %s, which its reference mesh never published"
                       % (_SHIPPED, th.key))
    if not ref.mesh or not ref.measured_on:
        out.append("%s's reference mesh does not say which mesh, or when"
                   % _SHIPPED)
    return out


def check_qt_free(w):
    """Importing the authoring service leaves PyQt6 unimported."""
    code = ("import sys; sys.path.insert(0, %r);"
            "import app.services.case_type_author;"
            "sys.exit(1 if 'PyQt6' in sys.modules else 0)" % _GUI)
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=_REPO)
    if proc.returncode == 0:
        return []
    return ["services/case_type_author.py pulls in PyQt6: %s%s"
            % (proc.stdout, proc.stderr)]


# --- fixtures -----------------------------------------------------------------
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
    1: check_one_action, 2: check_bounds_are_measured,
    3: check_provenance_round_trip, 4: check_override_is_distinguishable,
    5: check_advice_selects_and_is_required,
    6: check_unmeasured_figure_has_no_threshold,
    7: check_authored_type_produces_verdicts,
    8: check_incoherent_file_is_refused, 9: check_hand_written_still_legal,
    10: check_qt_free,
}

_LABELS = {
    1: "check 1. the CLI saves a working case as a named case type, in one action",
    2: "check 2. every derived bound IS its reference's figure x the stated factor",
    3: "check 3. the reference mesh survives the file whole, and is still named",
    4: "check 4. an overridden bound is distinguishable from a measured one",
    5: "check 5. advice selects the thresholds, and nothing is bounded without it",
    6: "check 6. a figure the reference could not measure gets NO threshold, and says so",
    7: "check 7. the authored type produces verdicts, and its reference mesh passes it",
    8: "check 8. a case type that disagrees with itself is refused, not partly read",
    9: "check 9. a hand-written v1 still loads; the shipped case type is measured",
    10: "check 10. the authoring service is Qt-free, measured in a subprocess",
}

_REAL = world()

for num in sorted(_ALL):
    fails = _ALL[num](_REAL)
    check(not fails, _LABELS[num])
    for f in fails:
        print("      " + f.replace("\n", "\n      "), flush=True)


# --- injections ---------------------------------------------------------------
# Checks 1 and 10 launch a SUBPROCESS against the real files on disk and so
# cannot see an in-memory mutant at all; including them in `others_green` would
# score them as evidence when they are measuring something else.
_SKIP_UNDER_MUTATION = (1, 10)


def others_green(w, *reddened):
    """True when every check BUT the named ones still passes on the mutant.

    #127's "isolate the labelled check", asserted ACROSS checks: a mutation that
    reddens the whole file proves nothing about the one it was written for.
    """
    return not any(fn(w) for num, fn in _ALL.items()
                   if num not in reddened and num not in _SKIP_UNDER_MUTATION)


def mutate(which, old, new, count=1):
    name = "app.services." + which
    src = _SRC[name]
    assert old in src, "injection anchor not found in %s: %r" % (which, old)
    mutated = src.replace(old, new, count)
    assert mutated != src
    return world(**{which: mutated})


inj = mutate("case_type_reference", "    REL_TOL = 1e-9", "    REL_TOL = 1e9")
check(inj[0].Origin.REL_TOL == 1e9,
      "injection A. injection is well-formed: a bound may now sit anywhere "
      "relative to its own derivation")
check(check_incoherent_file_is_refused(inj) and others_green(inj, 8),
      "injection A. check 8 ALONE fails when a bound need no longer BE the "
      "product it claims to be — the invariant that makes `measured` a fact "
      "about the file rather than a claim about how it was produced")

inj = mutate("case_type_reference",
             "            if factor is not None and factor < 1.0:",
             "            if False:")
check(check_authored_type_produces_verdicts(inj) and others_green(inj, 7, 8),
      "injection B. check 7 fails when a tolerance factor below 1.0 is allowed: "
      "the mesh the maintainer judged good would fail the case type measured "
      "from it. Check 8 moves with it and is asserted, that document being the "
      "same defect written down")

inj = mutate("case_type_author", "        if figures is None or not figures.measured:",
             "        if figures is None:")
check(check_unmeasured_figure_has_no_threshold(inj),
      "injection C. check 6 fails when the mesher's NEGATIVE sentinel is "
      "recorded as a figure — the negative-measurement rule, spent one layer "
      "further out than #160 spent it")
check(others_green(inj, 6),
      "injection C. ...and no other check moves")

inj = mutate("case_type", '''        return (MEASURED if self.measured_from.factor_for(bound) is not None
                else MANUAL)''', "        return MEASURED")
check(inj[0].Threshold("max", "a", attention=2.0, unusable=5.0,
                      measured_from=inj[0].Origin("r", attention_factor=1.0)
                      ).origin_of("unusable") == inj[0].MEASURED,
      "injection D. injection is well-formed: a bound with no factor beside it "
      "now claims to have been measured")
check(check_override_is_distinguishable(inj) and others_green(inj, 4, 9),
      "injection D. check 4 fails when an override is indistinguishable from a "
      "measurement. Check 9 moves with it and is asserted: it reads the same "
      "answer off the shipped file and off a v1 document")

inj = mutate("case_type", '''                    raise CaseTypeError(
                    "threshold %r was measured from reference mesh %r, which "
                    "this case type does not declare; provenance pointing at "
                    "nothing is not provenance" % (th.key, origin.reference))'''
             .replace("                    raise", "                raise"),
             "                continue")
check(check_incoherent_file_is_refused(inj) and others_green(inj, 8),
      "injection E. check 8 ALONE fails when a threshold may name a reference "
      "mesh the case type does not declare — provenance pointing at nothing")

inj = mutate("case_type", '''        if self.measured_from is not None:
            out["measured_from"] = self.measured_from.to_dict()''',
             "        if False:\n            pass")
check("measured_from" not in inj[0].Threshold(
          "max", "a", attention=2.0,
          measured_from=inj[0].Origin("r", attention_factor=1.0)).to_dict(),
      "injection F. injection is well-formed: a written threshold no longer "
      "carries where it came from")
check(check_bounds_are_measured(inj) and check_provenance_round_trip(inj)
      and check_override_is_distinguishable(inj)
      and check_incoherent_file_is_refused(inj)
      and others_green(inj, 2, 3, 4, 8),
      "injection F. checks 2, 3, 4 and 8 fail together when a threshold cannot "
      "say where it came from — all four asserted to move rather than three "
      "being excused; check 8 is there because it builds its documents by "
      "writing an authored one out")

inj = mutate("case_type_author", "    if stray:", "    if False:")
check(check_advice_selects_and_is_required(inj) and others_green(inj, 5),
      "injection G. check 5 ALONE fails when an override may name a figure with "
      "no advice — a bound the maintainer believes they set and that changes "
      "nothing")

inj = mutate("case_type_reference",
             '        for name in ("mesh", "provenance", "measured_on"):',
             "        for name in ():")
check(check_provenance_round_trip(inj) and others_green(inj, 3),
      "injection H. check 3 ALONE fails when a reference records its NUMBERS "
      "and not which mesh they came from or when — a threshold traceable to no "
      "mesh is the thing this ticket exists to make impossible")

check(not any(fn(_REAL) for num, fn in _ALL.items()),
      "injection I. negative control: the unmutated trio passes every check, so "
      "the failures above are the mutations and not the checker")


print("\n%s: %d check(s) failed" % (os.path.basename(__file__), len(_FAILS))
      if _FAILS else "\nAll checks passed.", flush=True)
sys.exit(1 if _FAILS else 0)
