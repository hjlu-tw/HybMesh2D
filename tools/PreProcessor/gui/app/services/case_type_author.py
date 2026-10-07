"""AUTHORING a case type from the meshes the maintainer judged. Qt-free.

The authoring file of the case-type seam (#161 and #168, parent #158):
`case_type.py` is the document, `case_type_reference.py` the figures and the
provenance it holds, `case_type_evidence.py` the arithmetic that turns a set of
reference meshes into one bound, `case_type_fields.py` the config overlay, and
this module is the one step that PRODUCES a case type — `author` from the first
reference mesh, `add_reference` from every one after it. The verdict half
(`case_type_verdict.py`) is not involved and is not imported — a case type is
authored, then judged with, and running the two together would make the gate's
"the reference mesh is usable under the case type it authored" circular.

**WHY A THRESHOLD IS MEASURED AND NOT TYPED.** #158's user story 32 states the
problem exactly: "I want the thresholds measured from the reference mesh rather
than typed, so that I do not have to invent numbers I do not know". The
maintainer knows which mesh is good; they do not necessarily know what its p95
is. So the tool reads the figures that mesh published, multiplies each by a
TOLERANCE FACTOR — a band rather than a knife edge, user story 33 — and records
which mesh each bound came from. Six months later the number is still traceable
to the mesh it was demonstrated on, which is ADR-0002's first consequence.

**ADVICE IS THE SELECTION.** The caller supplies one sentence or two per figure
it wants an opinion about, and those keys ARE the case type's thresholds: a
figure nobody wrote advice for gets no bound, because a missed threshold with
nothing to try is the dead end user story 13 exists against and `Threshold`
refuses an empty one anyway. There is deliberately no "all nine keys" default —
a case type that bounds every figure the sidecar publishes has an opinion it was
never asked for.

**A FIGURE THE REFERENCE MESH COULD NOT MEASURE PRODUCES NO THRESHOLD.** The
mesher writes a set's three figures NEGATIVE together with its count 0, so
"we did not measure" cannot read as a value; deriving a bound from one would
produce a number nothing can mean, and silently skipping it would leave the
maintainer believing they bounded a figure they did not. So the key is SKIPPED
and the skip is REPORTED — `AuthorResult.skipped` carries it, and the host says
it out loud.

**A MISJUDGED THRESHOLD IS CORRECTED WITH EVIDENCE, NOT BY EDITING THE NUMBER**
(#168, user story 38). `add_reference` adds a mesh to a case type that already
exists and re-derives every MEASURED bound from the whole set — as a further
EXEMPLAR the thresholds must keep accepting, or as a COUNTER-EXAMPLE they must
now reject. Hand-editing the number would work and would throw away the thing
the measurement bought: a threshold whose origin is still visible six months
later. Three rules make that an addition rather than an overwrite:

* **A hand-set bound is never recomputed.** It carries no tolerance factor, so
  there is nothing to re-derive, and `Evidence` is only ever asked for the
  bounds that do. Where that override is what stops the case type honouring the
  new mesh, the ADDITION is refused and the override is NAMED — the only way
  both halves hold, since recomputing it silently breaks this rule and accepting
  it silently leaves a counter-example the thresholds do not reject.
* **No threshold is INVENTED.** Advice is still the selection: a figure the case
  type had no opinion about does not acquire one because a mesh published it.
  The skip is reported, like an unmeasurable figure's is.
* **Already-finished cases are untouched.** A committed case carries the WHOLE
  case type and a frozen verdict beside its mesh (`services/mesh_commit.py`,
  #166), so editing the file an operator borrowed from rewrites nothing that has
  already been judged. That is user story 43, and it is a property of how a case
  is committed rather than of anything this module does — which is exactly why
  this module may rewrite the case type freely.

**AN OVERRIDE DROPS THE FACTOR, NOT THE REFERENCE.** A hand-set bound keeps the
reference mesh on the record and loses only the claim to have been derived from
it, which is what makes an overridden bound distinguishable from a measured one
by the file's own shape (`Threshold.origin_of`). A factor and a bound that
disagree is refused on load rather than being a third state. **The exception is
a threshold whose bounds are BOTH overridden**: nothing was derived, `Origin`
refuses to exist with no factor, and the threshold is written as the hand-written
one it has become. That loss is named in `docs/design_notes/gui.md`'s blind spots
rather than bought with a third state.
"""
from __future__ import annotations

import datetime
import os

from app.services import case_type as case_type_mod
from app.services import case_type_evidence
from app.services import mesh_shape_stats
from app.services import paths
from app.services.case_type import BOUNDS
from app.services.case_type import CaseTypeError

#: The factors a maintainer gets when they name none. A bound at 1.5x the
#: reference mesh's own figure is the band user story 33 asks for; `unusable` at
#: 3x is where the case type stops passing the mesh at all. They are DEFAULTS
#: and nothing more — the whole point of the authoring step is that the
#: maintainer can say otherwise per case type, and per bound through an override.
DEFAULT_ATTENTION_FACTOR = 1.5
DEFAULT_UNUSABLE_FACTOR = 3.0


class AuthorResult:
    """What one authoring action produced, and what it declined to produce.

    The skips are returned rather than logged here because this module is
    Qt-free and host-free: the CLI prints them, and a future GUI action would
    show them. A skip that only reached a log file would let a maintainer
    believe they had bounded a figure nobody bounded.
    """

    __slots__ = ("case_type", "skipped")

    def __init__(self, case_type: case_type_mod.CaseType,
                 skipped: "list | None" = None):
        self.case_type = case_type
        #: `(key, reason)` pairs, in `FIGURE_KEYS` order.
        self.skipped = list(skipped or [])

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("AuthorResult(case_type=%r, skipped=%d)"
                % (self.case_type.name, len(self.skipped)))


def _repo_relative(path: str) -> str:
    """`path` relative to the repo root when it is inside it, else unchanged.

    A case type is a file other people read, and an absolute path out of one
    maintainer's home directory is provenance nobody else can follow. Outside
    the repo the absolute path is the only true answer and is kept as given.
    """
    if not path:
        return ""
    full = os.path.abspath(path)
    root = os.path.abspath(paths.repo_root())
    rel = os.path.relpath(full, root)
    return full if rel.startswith(os.pardir) else rel.replace(os.sep, "/")


def measured_figures(summary) -> dict:
    """Every figure key `summary` really measured, mapped to its value.

    A key whose SET is absent (a sidecar from a path that did not split) or
    whose set the mesher looked at and could not measure is left out, never
    carried in as the negative number the producer wrote. `ShapeFigures.measured`
    is asked of the SET, which is the honest unit: `include/CellShape.hpp` writes
    a set's count 0 exactly when its three figures are negative.
    """
    out = {}
    for key in case_type_mod.FIGURE_KEYS:
        set_name, field = case_type_mod.split_key(key)
        figures = case_type_mod.figures_for(summary, set_name)
        if figures is None or not figures.measured:
            continue
        out[key] = float(getattr(figures, field))
    return out


def measure_reference(mesh_path: str, ident: str = "", measured_on: str = "",
                      kind: str = case_type_mod.EXEMPLAR
                      ) -> case_type_mod.ReferenceMesh:
    """Read a finished mesh's published figures as a `ReferenceMesh`.

    Nothing is computed here and nothing is re-measured: the figures are the
    ones the mesher already wrote to `<mesh>.provenance.json`, read through the
    single owner `mesh_shape_stats.read_shape_summary` — the same reader the
    verdict consumes, so a threshold cannot be derived from one reading of a
    mesh and judged against another.

    Raises rather than returning an empty reference, because a mesh with no
    figures is not a mesh anyone can demonstrate a threshold on.
    """
    summary = mesh_shape_stats.read_shape_summary(mesh_path)
    if summary is None:
        raise CaseTypeError(
            "'%s' publishes no quality figures, so there is nothing to measure "
            "a threshold from. A reference mesh is one the mesher measured and "
            "left a .provenance.json beside." % mesh_path)
    figures = measured_figures(summary)
    if not figures:
        raise CaseTypeError(
            "'%s' carries a quality block the mesher could not measure, so "
            "every figure in it is absent rather than a number" % mesh_path)
    return case_type_mod.ReferenceMesh(
        ident=ident or os.path.splitext(os.path.basename(mesh_path))[0],
        metric=summary.metric,
        figures=figures,
        kind=kind,
        mesh=_repo_relative(mesh_path),
        provenance=_repo_relative(summary.source),
        measured_on=measured_on or datetime.date.today().isoformat())


def _bounds_for(evidence, attention_factor: float, unusable_factor: float,
                override: dict):
    """One threshold's two bounds, and the factors that survive the overrides.

    Returns `(bounds, factors)`, both keyed by BOUND NAME. `factors` holds only
    the bounds still derived — which is what an `Origin` is built from, and what
    makes an overridden bound read as hand-set rather than as a measurement
    whose arithmetic went wrong.

    The arithmetic itself is `Evidence.bound` and is not repeated here: the same
    derivation is re-checked on every load (`case_type_evidence.check_derivations`),
    and a second spelling of it is how an authored file comes to fail the check
    that was supposed to prove it was authored correctly.
    """
    wanted = {"attention": attention_factor, "unusable": unusable_factor}
    bounds, factors = {}, {}
    for bound in BOUNDS:
        if bound in override:
            bounds[bound] = case_type_mod.opt_float(override[bound])
            continue
        bounds[bound] = evidence.bound(wanted[bound])
        factors[bound] = wanted[bound]
    return bounds, factors


def author(name: str, reference: case_type_mod.ReferenceMesh, advice: dict,
           attention_factor: float = DEFAULT_ATTENTION_FACTOR,
           unusable_factor: float = DEFAULT_UNUSABLE_FACTOR,
           overrides: "dict | None" = None,
           fields=None, characteristic=None) -> AuthorResult:
    """Build a case type from one reference mesh, its advice and its factors.

    `advice` maps a figure key to the sentence shown when that threshold is
    missed, and selects the figures the case type has an opinion about.
    `overrides` maps a figure key to `{bound: value}`; a value replaces the
    derived bound by hand, and ``None`` removes that bound altogether.

    `fields` is the SPARSE config overlay the case type carries (#162) — a
    `FieldOverlay` or a plain dict, and ``None`` for a case type that grades a
    mesh without saying how to produce one. It is a separate argument rather
    than something derived here, because the settings come from the maintainer's
    CASE and the thresholds come from the MESH it produced: deriving one from the
    other would make a case type claim an opinion about fields nobody chose.

    `characteristic` is the CHARACTERISTIC LENGTH the geometry-driven half of
    that overlay is expressed relative to (#163), and is a separate argument for
    the same reason: it is MEASURED off the maintainer's own drawing, which is a
    third artefact beside the case and the mesh.

    Nothing here is lenient about a key it was handed and cannot act on: an
    override naming a figure with no advice, or either naming a figure the
    mesher does not publish, raises. Both are a maintainer believing they said
    something the case type does not say.
    """
    overrides = dict(overrides or {})
    if not advice:
        raise CaseTypeError(
            "no advice was supplied, so case type '%s' would carry no "
            "thresholds and have no opinion about any mesh" % name)
    for key in sorted(set(advice) | set(overrides)):
        if key not in case_type_mod.FIGURE_KEYS:
            raise CaseTypeError(
                "%r is not a figure the mesher publishes; expected one of %s"
                % (key, ", ".join(case_type_mod.FIGURE_KEYS)))
    stray = sorted(set(overrides) - set(advice))
    if stray:
        raise CaseTypeError(
            "override(s) for %s name no threshold, because no advice was "
            "supplied for them; an override that changes nothing is a bound "
            "the maintainer thinks they set" % ", ".join(stray))
    for key, bounds in overrides.items():
        unknown = sorted(set(bounds) - set(BOUNDS))
        if unknown:
            raise CaseTypeError(
                "override for %r names %s, which is not a bound; expected %s"
                % (key, ", ".join(unknown), " or ".join(BOUNDS)))

    thresholds, skipped = [], []
    for key in case_type_mod.FIGURE_KEYS:
        if key not in advice:
            continue
        if reference.figure(key) is None:
            skipped.append((key, "reference mesh '%s' could not measure it"
                            % reference.ident))
            continue
        bounds, factors = _bounds_for(
            case_type_evidence.Evidence.over([reference], key),
            attention_factor, unusable_factor, overrides.get(key, {}))
        # Both constructors are called with their parameters SPELLED OUT rather
        # than splatted from a dict keyed by `bound + "_factor"`: a renamed
        # `Origin` parameter would otherwise break only at run time, in the one
        # place nothing names it.
        origin = None if not factors else case_type_mod.Origin(
            [reference.ident], attention_factor=factors.get("attention"),
            unusable_factor=factors.get("unusable"))
        thresholds.append(case_type_mod.Threshold(
            key, advice[key], attention=bounds["attention"],
            unusable=bounds["unusable"], measured_from=origin))
    if not thresholds:
        raise CaseTypeError(
            "case type '%s' would carry no thresholds: reference mesh '%s' "
            "measured none of the %d figure(s) advice was supplied for"
            % (name, reference.ident, len(advice)))
    return AuthorResult(
        case_type_mod.CaseType(name, reference.metric, thresholds,
                               references=[reference], fields=fields,
                               characteristic=characteristic),
        skipped)


class AddResult:
    """What adding one reference mesh did to a case type, bound by bound.

    `moves` is the record a maintainer reads to decide whether the correction
    did what they meant: `(key, bound, before, after)` for every bound that
    changed, and the hosts print it. It is RETURNED rather than logged for the
    same reason `AuthorResult.skipped` is — this module is Qt-free and
    host-free — and it is the whole of what "the thresholds adjust" means, so a
    maintainer who adds a mesh that moves nothing is told that too.
    """

    __slots__ = ("case_type", "reference", "moves", "skipped", "notes")

    def __init__(self, case_type, reference, moves=None, skipped=None,
                 notes=None):
        self.case_type = case_type
        self.reference = reference
        #: `(key, bound, before, after)`, in the case type's threshold order.
        self.moves = list(moves or [])
        #: `(key, reason)` for every figure the new mesh published that this
        #: case type has no opinion about, or that it could not re-derive.
        self.skipped = list(skipped or [])
        #: Sentences about what the correction COST, as distinct from what it
        #: changed. Today there is one: a figure whose two bounds landed on the
        #: same separating value can no longer answer `needs attention` at all,
        #: and a maintainer who is not told reads the verdict it does give as
        #: the full four-state answer. Decided here rather than in the host
        #: because it is a fact about the derivation, not about a report.
        self.notes = list(notes or [])

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("AddResult(case_type=%r, reference=%r, moves=%d)"
                % (self.case_type.name, self.reference.ident, len(self.moves)))


def _rederived(references, threshold):
    """One threshold re-derived against `references`, or itself unchanged.

    Only the bounds carrying a TOLERANCE FACTOR move. A hand-set bound has no
    factor to re-derive from and is carried through exactly as the maintainer
    typed it (acceptance criterion 5), and a threshold with no origin at all is
    returned as-is rather than rebuilt — rebuilding it would be a no-op that
    could still change a value by rounding.
    """
    origin = threshold.measured_from
    seen = case_type_evidence.Evidence.over(references, threshold.key)
    if origin is None:
        return threshold, ()
    bounds, factors = {}, {}
    for bound in BOUNDS:
        factor = origin.factor_for(bound)
        if factor is None:
            bounds[bound] = getattr(threshold, bound)
            continue
        bounds[bound] = seen.bound(factor)
        factors[bound] = factor
    try:
        fresh = case_type_mod.Threshold(
            threshold.key, threshold.advice, attention=bounds["attention"],
            unusable=bounds["unusable"],
            measured_from=case_type_mod.Origin(
                seen.idents, attention_factor=factors.get("attention"),
                unusable_factor=factors.get("unusable")))
    except CaseTypeError as exc:
        # A recomputed bound that cannot sit beside a HAND-SET one — the new
        # evidence puts `attention` above an `unusable` the maintainer typed.
        # `Threshold` refuses it correctly and says nothing about WHY the two
        # disagree, and the why is the whole answer here: criterion 5 forbids
        # recomputing the override, so the maintainer has to drop it or leave
        # the mesh out, and a message that does not say which bound is theirs
        # leaves them with no move to make.
        held = [b for b in BOUNDS if b not in factors
                and getattr(threshold, b) is not None]
        raise CaseTypeError(
            "threshold %r cannot take the new evidence: %s. Its %s bound is "
            "the obstacle%s"
            % (threshold.key, exc, " and ".join(held) or "(none)",
               case_type_evidence.HAND_SET_NOTE)) from exc
    moves = tuple((threshold.key, b, getattr(threshold, b), getattr(fresh, b))
                  for b in BOUNDS
                  if getattr(threshold, b) != getattr(fresh, b))
    return fresh, moves


def add_reference(case_type, reference) -> AddResult:
    """Add a further reference mesh and let the thresholds move (#168).

    `reference` is a `ReferenceMesh` — an EXEMPLAR the thresholds must keep
    accepting, or a COUNTER-EXAMPLE they must now reject. Every MEASURED bound
    is re-derived from the whole set through `Evidence`; a hand-set one is left
    alone.

    Raises `CaseTypeError` when the result would be self-contradictory — a case
    type asked to both accept and reject the same figures — naming which mesh,
    which figures and, where an override is the obstacle, that it is hand-set.
    The REFUSAL is what makes this an addition of evidence rather than of noise:
    a counter-example nothing rejects would sit in the file looking like a
    correction and changing nothing.
    """
    if reference.metric != case_type.metric:
        raise CaseTypeError(
            "reference mesh %r was measured with %s and case type %r is about "
            "%s, which are different quantities"
            % (reference.ident, reference.metric, case_type.name,
               case_type.metric))
    if case_type.reference(reference.ident) is not None:
        raise CaseTypeError(
            "case type %r already declares a reference mesh called %r; give "
            "the new one an id of its own, or the two could not be told apart"
            % (case_type.name, reference.ident))
    references = list(case_type.references) + [reference]
    thresholds, moves, skipped = [], [], []
    for th in case_type.thresholds:
        fresh, moved = _rederived(references, th)
        thresholds.append(fresh)
        moves.extend(moved)
    bounded = {th.key for th in case_type.thresholds}
    for key in sorted(set(reference.figures) - bounded,
                      key=case_type_mod.FIGURE_KEYS.index):
        # Said out loud rather than acted on: advice is still the selection, so
        # a figure the case type never had an opinion about does not acquire one
        # because a mesh published it. A maintainer who wanted that bound finds
        # out here rather than from its absence.
        skipped.append((key, "case type '%s' bounds no %s, and adding a "
                             "reference mesh does not invent a threshold"
                        % (case_type.name, key)))
    notes = [
        "%s can no longer answer `needs attention`: its two bounds both landed "
        "on the separating bound %.6g, because the evidence leaves no room "
        "between the worst exemplar and the nearest counter-example"
        % (th.key, th.attention)
        for th in thresholds
        if th.attention is not None and th.attention == th.unusable
        and any(key == th.key for key, _, _, _ in moves)]
    failures = case_type_evidence.standing_failures(references, thresholds)
    if failures:
        raise CaseTypeError(
            "adding reference mesh '%s' (%s) would make case type '%s' "
            "contradict itself: %s"
            % (reference.ident, reference.kind, case_type.name,
               "; ".join(failures)))
    return AddResult(
        case_type_mod.CaseType(
            case_type.name, case_type.metric, thresholds,
            source=case_type.source, references=references,
            fields=case_type.fields, characteristic=case_type.characteristic),
        reference, moves, skipped, notes)


def save_authored(result: AuthorResult, path: str) -> AuthorResult:
    """Write the authored case type and hand back one that knows its own file.

    `CaseType.source` is what a verdict prints to name the file that issued it,
    and a freshly authored one has none until it is written — so the result is
    rebuilt around the path rather than left claiming no source, which would
    make the in-memory case type and the one loaded back from disk disagree.
    """
    case_type_mod.save(result.case_type, path)
    written = case_type_mod.CaseType(
        result.case_type.name, result.case_type.metric,
        result.case_type.thresholds, source=path,
        references=result.case_type.references,
        fields=result.case_type.fields,
        characteristic=result.case_type.characteristic)
    return AuthorResult(written, result.skipped)
