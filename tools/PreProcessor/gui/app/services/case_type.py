"""A CASE TYPE: the artefact a maintainer authors and an operator applies. Qt-free.

The first artefact of issue #158's workflow (issue #160, the tracer bullet). A
**case type** is the unit in which meshing expertise is stored and reused: a
named bundle the maintainer authors once and an operator applies. It holds its
name, the metric its numbers are about, its THRESHOLDS, the ADVICE to show when
each one is missed, the REFERENCE MESHES those thresholds rest on (#161, and
since #168 a SET of them with a KIND each), and — since #162 — the config FIELDS
it has an opinion about, as a sparse overlay. It does not yet carry bindings;
those are #164's, and are deliberately NOT ownable fields, since the ids in them
point at the maintainer's geometry. The file format is a versioned document so
that it GROWS rather than being replaced, which #161, #162, #163 and #168 are
the four tests of so far: `SCHEMA_VERSION` is 5 and `READABLE_VERSIONS` still
holds every one before it, because a v1 document is a v5 document with no
reference meshes, no fields, no characteristic length and every bound hand-set.
Each of those four WIDENED the artefact; none replaced it.

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

WHICH CASE TYPE IS IN PLAY is deliberately NOT decided here. The actions that
ACT on the choice are #166's and have landed; picking one in the window has not,
and no open ticket owns it — the forecast named #162 and then #166 and both
shipped without a picker, so `HYBMESH_CASE_TYPE` is the channel rather than a
placeholder for one. Every host reaches it through this module, and a run with
the variable unset says nothing at all rather than inventing a default. A default case type would be a universal threshold wearing a different
hat, which is the one thing ADR-0002 rules out.

ONE SEAM, AND EVERY CUT IS THE ~500-LINE STANDARD rather than a second home for
the knowledge. The grading half is `services/case_type_verdict.py`; the figure
vocabulary and the provenance are `services/case_type_reference.py`, re-exported
from here so no caller learns a new name; what a SET of reference meshes derives,
and whether a document obeys it, is `services/case_type_evidence.py` (#168); the
config overlay, what it may own and what deviates from it are
`services/case_type_fields.py`, re-exported the same way; the one step that
PRODUCES or CORRECTS a case type is `services/case_type_author.py`. A THRESHOLD
is declared HERE and nowhere else, the set of OWNABLE fields in the overlay and
nowhere else, and the DERIVATION in the evidence module and nowhere else — so
every dependency runs one way, author -> document -> evidence -> figures, with
verdict -> document beside it, and there is no cycle to unpick. The same shape #159 gave
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
from app.services import case_type_evidence
from app.services.case_type_reference import BOUNDS
from app.services.case_type_reference import COUNTER  # noqa: F401
from app.services.case_type_reference import EXEMPLAR  # noqa: F401
from app.services.case_type_reference import KINDS  # noqa: F401
from app.services.case_type_reference import exceeds  # noqa: F401
from app.services.case_type_reference import FIGURE_KEYS
from app.services.case_type_reference import figures_for  # noqa: F401
from app.services.case_type_reference import MANUAL
from app.services.case_type_reference import MEASURED
from app.services.case_type_reference import CaseTypeError
from app.services.case_type_reference import check_bound
from app.services.case_type_reference import Origin
from app.services.case_type_reference import ReferenceMesh
from app.services.case_type_reference import opt_float
from app.services.case_type_reference import split_key  # noqa: F401
from app.services.case_type_fields import FieldOverlay
from app.services.case_type_scale import CharacteristicLength
from app.services.case_type_scale import Application  # noqa: F401
from app.services.case_type_scale import plan  # noqa: F401
from app.services.case_type_fields import apply  # noqa: F401
from app.services.case_type_fields import deviations  # noqa: F401
from app.services.case_type_fields import diff  # noqa: F401
from app.services.case_type_fields import ownable_names  # noqa: F401

#: The document's own name and version, written into every file and required on
#: load. A case type is expected to GROW fields (a family, bindings, a config
#: overlay, reference-mesh provenance), so the version is what lets a later
#: reader tell a file it understands from one it does not.
SCHEMA = "hybmesh-case-type"
SCHEMA_VERSION = 5

#: Every version this build can READ; `SCHEMA_VERSION` is the only one it
#: WRITES. A v1 document is a v2 document carrying no reference meshes and no
#: measured bounds — which is exactly what a hand-written case type is — and a
#: v2 document is a v3 document that takes a position on no config field, which
#: is what every case type authored before #162 is. So the artefact has now been
#: WIDENED twice rather than replaced, and the version is still what makes a
#: document from a LATER build fail loudly instead of being partly read.
READABLE_VERSIONS = (1, 2, 3, 4, 5)

#: The environment variable naming the active case type file, and — until some
#: ticket owns a picker, which neither #162 nor #166 turned out to — the only
#: channel there is. See the module docstring for why that is not a defect.
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
        if getattr(self, check_bound(bound)) is None:
            return None
        if self.measured_from is None:
            return MANUAL
        return (MEASURED if self.measured_from.factor_for(bound) is not None
                else MANUAL)

    def describe_bounds(self) -> str:
        """The bounds this threshold sets, each with whether it was measured.

        WHICH meshes it rests on is `CaseType.describe_support`, not this: the
        support is derived from the case type's reference list and a threshold
        does not hold one.

        ONE owner because BOTH hosts print it — `save_case_type.py` after
        authoring and `show_case_type.py` when inspecting — and two copies of
        the same line are free to render one file's thresholds two ways. The
        figures are quality RATIOS and go out at `%.6g`, which is their own
        precision and deliberately not the config overlay's `_show`: that one
        renders mesh sizes, where six significant figures is the `.dat` writer's
        limit rather than a reading convenience.
        """
        return ", ".join("%s %.6g (%s)"
                         % (bound, getattr(self, bound), self.origin_of(bound))
                         for bound in BOUNDS if getattr(self, bound) is not None)

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

    `fields` is the SPARSE overlay of settings this case type takes a position
    on — including the family and its parameters. Sparse is the design and not an
    optimisation: a field it does not mention takes the ordinary default, so
    adding a mesher field does not stale every case type in the tree. What may be
    owned, and why bindings may not, is `services/case_type_fields.py`.
    """

    __slots__ = ("name", "metric", "thresholds", "source", "references",
                 "fields", "characteristic")

    def __init__(self, name: str, metric: str,
                 thresholds: "list[Threshold] | None" = None,
                 source: str = "",
                 references: "list[ReferenceMesh] | None" = None,
                 fields: "FieldOverlay | dict | None" = None,
                 characteristic: "CharacteristicLength | None" = None):
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
        # Accepts either, because every caller that builds one by hand has a
        # plain dict and every caller that copies one has an overlay — and a
        # rebuild that silently dropped the overlay is how `save_authored`
        # would have written a case type with no opinion about anything.
        self.fields = (fields if isinstance(fields, FieldOverlay)
                       else FieldOverlay(fields))
        #: The ruler this case type's geometry-driven sizes are expressed
        #: against, or ``None`` for one authored before #163 — which fits every
        #: drawing at 1:1, the behaviour it has always had.
        self.characteristic = characteristic
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
        """Every bound follows from the evidence, and the evidence is coherent.

        THREE invariants, and `services/case_type_evidence.py` owns the
        arithmetic behind all three: every measured bound really IS what its
        reference meshes derive, every exemplar is accepted by the case type
        measured from it, and every counter-example is rejected by it (#168).
        They are checked HERE because this is the only scope holding both halves
        — a `Threshold` knows its factor, a `ReferenceMesh` knows its figure —
        and they are not WRITTEN here because the derivation needs neither this
        document's name nor anything else it holds.
        """
        for ref in self.references:
            if ref.metric != self.metric:
                raise CaseTypeError(
                    "reference mesh %r was measured with %s and case type %r is "
                    "about %s, which are different quantities"
                    % (ref.ident, ref.metric, self.name, self.metric))
        case_type_evidence.check_derivations(self.name, self.references,
                                             self.thresholds)
        case_type_evidence.check_standing(self.name, self.references,
                                          self.thresholds)

    def reference(self, ident: str) -> "ReferenceMesh | None":
        """The declared reference mesh with this id, or ``None``."""
        for ref in self.references:
            if ref.ident == ident:
                return ref
        return None

    def evidence_for(self, key: str):
        """What this case type's reference meshes say about one figure.

        The answer to "which reference meshes does this threshold rest on"
        (#168, user story 39) — DERIVED from the references rather than read off
        the threshold, so the two cannot disagree. `check_derivations` is what
        holds the stored support to this same answer.
        """
        return case_type_evidence.Evidence.over(self.references, key)

    def describe_support(self, threshold: "Threshold") -> str:
        """One line naming the meshes a threshold rests on, and their kinds.

        ONE owner because BOTH inspecting hosts print it — `show_case_type.py`
        and `add_reference_mesh.py` — and a second copy would be free to render
        one file's provenance two ways. The kind is shown because it reverses
        the sentence: a mesh this threshold must ACCEPT and one it must REJECT
        are both support, and reading one as the other inverts what the number
        means.
        """
        seen = self.evidence_for(threshold.key)
        if not seen.idents:
            return "rests on no reference mesh: hand-written"
        by_id = {r.ident: r for r in self.references}
        return "rests on " + ", ".join(
            "%s (%s)" % (i, by_id[i].kind) for i in seen.idents)

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
                              "thresholds", "reference_meshes", "fields",
                              "characteristic_length"}
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
                   references=[ReferenceMesh.from_dict(r) for r in refs],
                   fields=FieldOverlay.from_dict(doc.get("fields")),
                   characteristic=CharacteristicLength.from_dict(
                       doc.get("characteristic_length")))

    def to_dict(self) -> dict:
        out = {"schema": SCHEMA, "version": SCHEMA_VERSION,
               "name": self.name, "metric": self.metric}
        if self.characteristic is not None:
            # Written only when declared, for the reason `fields` below is: a
            # case type that names no ruler must come back out of a round trip
            # as the document it was.
            out["characteristic_length"] = self.characteristic.to_dict()
        if self.fields:
            # Written only when there is an opinion, for the reason
            # `reference_meshes` is: a case type that takes no position on any
            # field must come back out of a round trip as the document it was,
            # not as one carrying an empty section it never had. That is also
            # what makes "a round trip preserves exactly that set" a statement
            # about the SET rather than about a dict that happens to be empty.
            out["fields"] = self.fields.to_dict()
        if self.references:
            # Written only when there are any, so a hand-authored case type is
            # still the short document it was: a v1 document read by this build
            # comes back out with its thresholds unchanged and no empty list it
            # never had. Its `version` IS rewritten to 2 — writing is always the
            # current version — so what round-trips is the CONTENT, not the file.
            out["reference_meshes"] = [r.to_dict() for r in self.references]
        out["thresholds"] = [t.to_dict() for t in self.thresholds]
        return out

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("CaseType(name=%r, metric=%r, thresholds=%d, references=%d, "
                "fields=%d, characteristic=%r)"
                % (self.name, self.metric, len(self.thresholds),
                   len(self.references), len(self.fields),
                   self.characteristic))


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
