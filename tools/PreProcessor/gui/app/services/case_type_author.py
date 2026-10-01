"""AUTHORING a case type from a mesh the maintainer judged good. Qt-free.

The authoring file of the case-type seam (#161, parent #158): `case_type.py` is
the document, `case_type_reference.py` the figures and the provenance it holds,
`case_type_fields.py` the config overlay, and this module is the one step that
PRODUCES one. The verdict half
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


def measure_reference(mesh_path: str, ident: str = "",
                      measured_on: str = "") -> case_type_mod.ReferenceMesh:
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
        mesh=_repo_relative(mesh_path),
        provenance=_repo_relative(summary.source),
        measured_on=measured_on or datetime.date.today().isoformat())


def _bounds_for(reference, key: str, attention_factor: float,
                unusable_factor: float, override: dict):
    """One threshold's two bounds, and the factors that survive the overrides.

    Returns `(bounds, factors)`, both keyed by BOUND NAME. `factors` holds only
    the bounds still derived — which is what an `Origin` is built from, and what
    makes an overridden bound read as hand-set rather than as a measurement
    whose arithmetic went wrong.
    """
    value = reference.figure(key)
    wanted = {"attention": attention_factor, "unusable": unusable_factor}
    bounds, factors = {}, {}
    for bound in BOUNDS:
        if bound in override:
            bounds[bound] = case_type_mod.opt_float(override[bound])
            continue
        bounds[bound] = value * wanted[bound]
        factors[bound] = wanted[bound]
    return bounds, factors


def author(name: str, reference: case_type_mod.ReferenceMesh, advice: dict,
           attention_factor: float = DEFAULT_ATTENTION_FACTOR,
           unusable_factor: float = DEFAULT_UNUSABLE_FACTOR,
           overrides: "dict | None" = None,
           fields=None) -> AuthorResult:
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
            reference, key, attention_factor, unusable_factor,
            overrides.get(key, {}))
        # Both constructors are called with their parameters SPELLED OUT rather
        # than splatted from a dict keyed by `bound + "_factor"`: a renamed
        # `Origin` parameter would otherwise break only at run time, in the one
        # place nothing names it.
        origin = None if not factors else case_type_mod.Origin(
            reference.ident, attention_factor=factors.get("attention"),
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
                               references=[reference], fields=fields),
        skipped)


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
        fields=result.case_type.fields)
    return AuthorResult(written, result.skipped)
