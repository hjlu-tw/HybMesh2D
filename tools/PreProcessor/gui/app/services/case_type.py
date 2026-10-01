"""A CASE TYPE: the artefact a maintainer authors and an operator applies. Qt-free.

The first artefact of issue #158's workflow (issue #160, the tracer bullet). A
**case type** is the unit in which meshing expertise is stored and reused: a
named bundle the maintainer authors once and an operator applies. At this stage
it holds its name, the metric its numbers are about, its THRESHOLDS, the ADVICE
to show when each one is missed, and — since #161 — the REFERENCE MESHES those
thresholds were measured from. It does not yet carry config fields, a family or
bindings; those arrive in #162. The file format is a versioned document so that
it GROWS rather than being replaced, which #161 is the first test of:
`SCHEMA_VERSION` is 2 and `READABLE_VERSIONS` still holds 1, because a v1
document is a v2 document with no reference meshes and every bound hand-set.

**Why thresholds live here and not in the mesher** is
`docs/adr/0002-thresholds-live-in-case-types.md`. The mesher measures and
refuses to grade, because whether 30 degrees of non-orthogonality is bad depends
on the problem; a case type's threshold is explicitly NOT universal — it is
scoped to one class of problem, authored by someone who knows that class. A
future reader who finds thresholds in this tree should read that ADR before
concluding the mesher's rule was violated.

WHAT A THRESHOLD IS ABOUT. The figures are the ones the mesher already publishes
in `<mesh>.provenance.json`, read by `services/mesh_shape_stats.py` — the
whole-mesh `median` / `p95` / `max` of the cell-shape metric, and since #143/#144
the same three over each half of the wall/bulk split. Every one of them is a
ratio whose floor is 1.0 and whose larger values are worse, so a threshold is an
UPPER BOUND and nothing here needs a direction flag. The nine keys are
`FIGURE_KEYS`; a file naming anything else is refused on load rather than
silently ignored, because a threshold nobody evaluates is worse than none.

THE METRIC NAME TRAVELS WITH THE NUMBERS. The two generation paths measure two
different quantities (`quad_midline_ratio` on `MESH_MODE 1`'s structured quads,
`tri_edge_ratio` on the hybrid path's triangles) and a reader that compares one
against the other is comparing nothing (#130). So a case type NAMES its metric,
and `case_type_verdict.judge` refuses a mesh measured with a different one
rather than reading it against numbers that do not describe it.

WHICH CASE TYPE IS IN PLAY is deliberately NOT decided here. Applying a case
type — picking one, assigning roles, overlaying its config fields — is #162's
whole subject. Until then the active case type is named by the
`HYBMESH_CASE_TYPE` environment variable, which both hosts reach through
`case_type_verdict.run_report`: one channel, no GUI chrome for #162 to unpick,
and a run with the variable unset says nothing at all rather than inventing a
default. A default case type would be a universal threshold wearing a different
hat, which is the one thing ADR-0002 rules out.

ONE SEAM, FOUR FILES, AND EVERY CUT IS THE ~500-LINE STANDARD rather than a
second home for the knowledge. The grading half is
`services/case_type_verdict.py`; the figure vocabulary and the provenance are
`services/case_type_reference.py`, re-exported from here so no caller learns a
new name; the one step that PRODUCES a case type is
`services/case_type_author.py`. A THRESHOLD is declared HERE and nowhere else,
and every dependency runs one way — author -> document -> figures, and
verdict -> document — so there is no cycle to unpick. The same shape #159 gave
`mesh_config.py` and `mesh_config_validate.py`, in the prefactor for this very
feature.
"""
from __future__ import annotations

import json
import os

# RE-EXPORTED, not merely used: `case_type.FIGURE_KEYS` and
# `case_type.CaseTypeError` are what the verdict service, both hosts and the
# gates already name, and the split below them is a file-length cut rather than
# a new seam for a caller to learn.
from app.services.case_type_reference import BOUNDS
from app.services.case_type_reference import FIGURE_KEYS
from app.services.case_type_reference import figures_for  # noqa: F401
from app.services.case_type_reference import MANUAL
from app.services.case_type_reference import MEASURED
from app.services.case_type_reference import CaseTypeError
from app.services.case_type_reference import Origin
from app.services.case_type_reference import ReferenceMesh
from app.services.case_type_reference import opt_float
from app.services.case_type_reference import split_key  # noqa: F401

#: The document's own name and version, written into every file and required on
#: load. A case type is expected to GROW fields (a family, bindings, a config
#: overlay, reference-mesh provenance), so the version is what lets a later
#: reader tell a file it understands from one it does not.
SCHEMA = "hybmesh-case-type"
SCHEMA_VERSION = 2

#: Every version this build can READ; `SCHEMA_VERSION` is the only one it
#: WRITES. A v1 document is a v2 document carrying no reference meshes and no
#: measured bounds — which is exactly what a hand-written case type is — so #161
#: widened the artefact rather than replacing it, and the version is still what
#: makes a document from a LATER build fail loudly instead of being partly read.
READABLE_VERSIONS = (1, 2)

#: The environment variable naming the active case type file. INTERIM, and owned
#: by this ticket: #162 builds the picker that replaces it.
CASE_TYPE_ENV = "HYBMESH_CASE_TYPE"

class Threshold:
    """One bound on one published figure, with the advice for missing it.

    Two bounds rather than one, because four states need two bands: `attention`
    is where the mesh stops being one the case type is happy with, `unusable` is
    where it stops being one the case type will pass. Either may be omitted — a
    threshold with only `attention` can never make a mesh unusable on its own,
    which is the ordinary shape for a figure whose large values are a nuisance
    rather than a defect, and one with only `unusable` is a pure refusal.

    `advice` is REQUIRED and may not be empty. A missed threshold with nothing to
    try is the dead end user story 13 exists against, and an empty string here
    would make every case type silently able to produce one.
    """

    __slots__ = ("key", "attention", "unusable", "advice", "measured_from")

    def __init__(self, key: str, advice: str, attention: float | None = None,
                 unusable: float | None = None,
                 measured_from: "Origin | None" = None):
        if key not in FIGURE_KEYS:
            raise CaseTypeError(
                "threshold key %r is not a figure the mesher publishes; "
                "expected one of %s" % (key, ", ".join(FIGURE_KEYS)))
        if not str(advice).strip():
            raise CaseTypeError(
                "threshold %r carries no advice; a missed threshold must say "
                "what to try" % key)
        if attention is None and unusable is None:
            raise CaseTypeError(
                "threshold %r sets neither an attention nor an unusable bound, "
                "so nothing can miss it" % key)
        if (attention is not None and unusable is not None
                and unusable < attention):
            raise CaseTypeError(
                "threshold %r has its unusable bound (%g) below its attention "
                "bound (%g), which leaves no needs-attention band at all"
                % (key, unusable, attention))
        self.key = key
        self.advice = str(advice).strip()
        self.attention = None if attention is None else float(attention)
        self.unusable = None if unusable is None else float(unusable)
        #: The reference mesh these bounds were measured from, or ``None`` for a
        #: hand-written threshold. The ARITHMETIC is checked by
        #: `CaseType.__init__`, which is the only scope that holds the figures.
        self.measured_from = measured_from
        if measured_from is not None:
            for bound in BOUNDS:
                if (measured_from.factor_for(bound) is not None
                        and getattr(self, bound) is None):
                    raise CaseTypeError(
                        "threshold %r names a %s_factor but sets no %s bound, "
                        "so the factor derives nothing" % (key, bound, bound))

    def origin_of(self, bound: str) -> str | None:
        """`"measured"`, `"manual"`, or ``None`` when that bound is not set.

        The distinction acceptance asks for, and it is read off the file's SHAPE
        rather than off a flag: a bound with a tolerance factor beside it was
        derived from the reference mesh, and a bound without one was typed. A
        flag could disagree with the number next to it; this cannot.
        """
        if bound not in BOUNDS:
            raise CaseTypeError("%r is not a bound; expected one of %s"
                                % (bound, ", ".join(BOUNDS)))
        if getattr(self, bound) is None:
            return None
        if self.measured_from is None:
            return MANUAL
        return (MEASURED if self.measured_from.factor_for(bound) is not None
                else MANUAL)

    @classmethod
    def from_dict(cls, raw: dict) -> "Threshold":
        if not isinstance(raw, dict):
            raise CaseTypeError("a threshold must be an object, got %r" % (raw,))
        unknown = set(raw) - {"key", "advice", "attention", "unusable",
                              "measured_from"}
        if unknown:
            # Refused rather than ignored: a bound misspelled into a key nobody
            # reads is a threshold that silently stops biting, which is the
            # failure this whole module exists to make impossible.
            raise CaseTypeError("threshold %r carries unknown key(s): %s"
                                % (raw.get("key"), ", ".join(sorted(unknown))))
        if "key" not in raw:
            raise CaseTypeError("a threshold is missing 'key'")
        key = str(raw["key"])
        origin = raw.get("measured_from")
        return cls(key=key, advice=str(raw.get("advice", "")),
                   attention=opt_float(raw.get("attention")),
                   unusable=opt_float(raw.get("unusable")),
                   measured_from=(None if origin is None
                                  else Origin.from_dict(origin, key)))

    def to_dict(self) -> dict:
        out = {"key": self.key}
        if self.attention is not None:
            out["attention"] = self.attention
        if self.unusable is not None:
            out["unusable"] = self.unusable
        if self.measured_from is not None:
            out["measured_from"] = self.measured_from.to_dict()
        out["advice"] = self.advice
        return out

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("Threshold(key=%r, attention=%r, unusable=%r)"
                % (self.key, self.attention, self.unusable))


class CaseType:
    """A named bundle of thresholds and advice, as one file holds it.

    `metric` names the quantity the thresholds are about and is matched against
    the mesh's own before anything is judged, so a case type authored on
    structured quads cannot be read against a triangle edge ratio.

    `source` is where it was loaded from, kept for the same reason
    `ShapeSummary.source` is: a verdict a user questions must be traceable to the
    file that issued it.
    """

    __slots__ = ("name", "metric", "thresholds", "source", "references")

    def __init__(self, name: str, metric: str,
                 thresholds: "list[Threshold] | None" = None,
                 source: str = "",
                 references: "list[ReferenceMesh] | None" = None):
        if not str(name).strip():
            raise CaseTypeError("a case type must have a name")
        if not str(metric).strip():
            raise CaseTypeError(
                "case type %r names no metric; thresholds that do not say what "
                "they measure cannot be matched against a mesh" % name)
        self.name = str(name).strip()
        self.metric = str(metric).strip()
        self.thresholds = list(thresholds or [])
        self.source = source
        self.references = list(references or [])
        seen = set()
        for th in self.thresholds:
            if th.key in seen:
                raise CaseTypeError(
                    "case type %r sets two thresholds on %r; one figure has one "
                    "bound pair, or the second would silently win"
                    % (self.name, th.key))
            seen.add(th.key)
        self._check_references()

    def _check_references(self) -> None:
        """Every measured bound really IS its reference's figure times its factor.

        The one invariant that makes "derived, not typed" a fact about the FILE
        rather than a claim about how it was produced. It lives here because it
        is the only scope holding both halves: a `Threshold` knows its factor, a
        `ReferenceMesh` knows its figure, and neither alone can multiply them.
        """
        by_id = {}
        for ref in self.references:
            if ref.ident in by_id:
                raise CaseTypeError(
                    "case type %r declares two reference meshes called %r; a "
                    "threshold naming it could not say which"
                    % (self.name, ref.ident))
            if ref.metric != self.metric:
                raise CaseTypeError(
                    "reference mesh %r was measured with %s and case type %r is "
                    "about %s, which are different quantities"
                    % (ref.ident, ref.metric, self.name, self.metric))
            by_id[ref.ident] = ref
        for th in self.thresholds:
            origin = th.measured_from
            if origin is None:
                continue
            ref = by_id.get(origin.reference)
            if ref is None:
                raise CaseTypeError(
                    "threshold %r was measured from reference mesh %r, which "
                    "this case type does not declare; provenance pointing at "
                    "nothing is not provenance" % (th.key, origin.reference))
            value = ref.figure(th.key)
            if value is None:
                raise CaseTypeError(
                    "threshold %r was measured from reference mesh %r, which "
                    "published no %s — a figure that mesh could not measure "
                    "cannot have a bound derived from it"
                    % (th.key, ref.ident, th.key))
            for bound in BOUNDS:
                factor = origin.factor_for(bound)
                if factor is None:
                    continue
                want = value * factor
                stated = getattr(th, bound)
                if abs(stated - want) > Origin.REL_TOL * max(abs(want), 1.0):
                    raise CaseTypeError(
                        "threshold %r states a %s bound of %r, but reference "
                        "mesh %r measured %r and the %s_factor is %r, which "
                        "gives %r. A bound that is not its own derivation is a "
                        "hand-set one: drop the factor and it reads as the "
                        "override it is"
                        % (th.key, bound, stated, ref.ident, value, bound,
                           factor, want))

    def reference(self, ident: str) -> "ReferenceMesh | None":
        """The declared reference mesh with this id, or ``None``."""
        for ref in self.references:
            if ref.ident == ident:
                return ref
        return None

    @classmethod
    def from_dict(cls, doc: dict, source: str = "") -> "CaseType":
        if not isinstance(doc, dict):
            raise CaseTypeError("a case type must be a JSON object")
        if doc.get("schema") != SCHEMA:
            raise CaseTypeError(
                "not a case type: expected schema %r, got %r"
                % (SCHEMA, doc.get("schema")))
        version = doc.get("version")
        if version not in READABLE_VERSIONS:
            raise CaseTypeError(
                "case type schema version %r is none of %s, which are the ones "
                "this build reads"
                % (version, ", ".join(str(v) for v in READABLE_VERSIONS)))
        unknown = set(doc) - {"schema", "version", "name", "metric",
                              "thresholds", "reference_meshes"}
        if unknown:
            # Refused for the same reason an unknown THRESHOLD key is: a case
            # type is expected to grow fields, so a key this build does not read
            # is either a typo or a document from a later version, and silently
            # dropping either is how an opinion goes missing.
            raise CaseTypeError("unknown key(s) in case type: %s"
                                % ", ".join(sorted(unknown)))
        raw = doc.get("thresholds", [])
        if not isinstance(raw, list):
            raise CaseTypeError("`thresholds` must be a list")
        refs = doc.get("reference_meshes", [])
        if not isinstance(refs, list):
            raise CaseTypeError("`reference_meshes` must be a list")
        return cls(name=str(doc.get("name", "")),
                   metric=str(doc.get("metric", "")),
                   thresholds=[Threshold.from_dict(t) for t in raw],
                   source=source,
                   references=[ReferenceMesh.from_dict(r) for r in refs])

    def to_dict(self) -> dict:
        out = {"schema": SCHEMA, "version": SCHEMA_VERSION,
               "name": self.name, "metric": self.metric}
        if self.references:
            # Written only when there are any, so a hand-authored case type is
            # still the short document it was and a v1 file round-trips through
            # this build without growing an empty list it never had.
            out["reference_meshes"] = [r.to_dict() for r in self.references]
        out["thresholds"] = [t.to_dict() for t in self.thresholds]
        return out

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("CaseType(name=%r, metric=%r, thresholds=%d, references=%d)"
                % (self.name, self.metric, len(self.thresholds),
                   len(self.references)))


def load(path: str) -> CaseType:
    """Read a case type file. Raises `CaseTypeError` on anything wrong with it."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except OSError as exc:
        raise CaseTypeError("could not read case type '%s': %s" % (path, exc)) from exc
    except ValueError as exc:
        raise CaseTypeError("'%s' is not valid JSON: %s" % (path, exc)) from exc
    try:
        return CaseType.from_dict(doc, source=path)
    except CaseTypeError as exc:
        raise CaseTypeError("'%s': %s" % (path, exc)) from exc


def save(case_type: CaseType, path: str) -> None:
    """Write `case_type` as JSON. The round trip through `load` is exact."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(case_type.to_dict(), fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def active_case_type() -> CaseType | None:
    """The case type `CASE_TYPE_ENV` names, or ``None`` when it names none.

    ``None`` is the ordinary state — no case type is in play and no verdict is
    issued — and is a different answer from a named file that will not load,
    which raises so the operator is told rather than left wondering where their
    verdict went.
    """
    path = os.environ.get(CASE_TYPE_ENV, "").strip()
    if not path:
        return None
    return load(path)
