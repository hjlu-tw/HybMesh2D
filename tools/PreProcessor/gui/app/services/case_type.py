"""A CASE TYPE: the artefact a maintainer authors and an operator applies. Qt-free.

The first artefact of issue #158's workflow (issue #160, the tracer bullet). A
**case type** is the unit in which meshing expertise is stored and reused: a
named bundle the maintainer authors once and an operator applies. At this stage
it holds only its name, the metric its numbers are about, its THRESHOLDS and the
ADVICE to show when each one is missed. It does not yet carry config fields, a
family or bindings — those arrive in #161/#162 — and the file format is a
versioned document so that it GROWS rather than being replaced.

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

ONE SEAM, TWO FILES. The grading half is `services/case_type_verdict.py` and the
split is the ~500-line GUI file-length standard, not a second home for the
knowledge: the thresholds and their advice are declared HERE and nowhere else,
and that module only applies them — the same shape #159 gave `mesh_config.py`
and `mesh_config_validate.py`, in the prefactor for this very feature. The
dependency runs one way, verdict -> artefact, so there is no cycle to unpick.
"""
from __future__ import annotations

import json
import os

#: The document's own name and version, written into every file and required on
#: load. A case type is expected to GROW fields (a family, bindings, a config
#: overlay, reference-mesh provenance), so the version is what lets a later
#: reader tell a file it understands from one it does not.
SCHEMA = "hybmesh-case-type"
SCHEMA_VERSION = 1

#: The environment variable naming the active case type file. INTERIM, and owned
#: by this ticket: #162 builds the picker that replaces it.
CASE_TYPE_ENV = "HYBMESH_CASE_TYPE"

#: The three figures the mesher publishes, over the whole mesh and over each half
#: of the split. Built by product rather than written out nine times, so a fourth
#: figure or a third half cannot reach one list and miss another.
_SETS = ("", "layer", "bulk")
_FIELDS = ("median", "p95", "max")
FIGURE_KEYS = tuple(f"{s}.{f}" if s else f for s in _SETS for f in _FIELDS)


class CaseTypeError(ValueError):
    """A case type file that cannot be read, or that says something invalid.

    One exception for both, because the caller does the same thing with either:
    tell the user which file and what is wrong with it. It is raised rather than
    swallowed — a case type the operator named and the tool quietly ignored is
    how a verdict goes missing without anybody noticing.
    """


def _opt_float(value) -> float | None:
    """`value` as a float, or ``None`` when the file omitted it.

    A JSON `null` and an absent key mean the same thing — this bound is not set
    — and a string that does not parse is an error rather than a silent absence.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise CaseTypeError("%r is not a number" % (value,)) from exc


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

    __slots__ = ("key", "attention", "unusable", "advice")

    def __init__(self, key: str, advice: str, attention: float | None = None,
                 unusable: float | None = None):
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

    @classmethod
    def from_dict(cls, raw: dict) -> "Threshold":
        if not isinstance(raw, dict):
            raise CaseTypeError("a threshold must be an object, got %r" % (raw,))
        unknown = set(raw) - {"key", "advice", "attention", "unusable"}
        if unknown:
            # Refused rather than ignored: a bound misspelled into a key nobody
            # reads is a threshold that silently stops biting, which is the
            # failure this whole module exists to make impossible.
            raise CaseTypeError("threshold %r carries unknown key(s): %s"
                                % (raw.get("key"), ", ".join(sorted(unknown))))
        if "key" not in raw:
            raise CaseTypeError("a threshold is missing 'key'")
        return cls(key=str(raw["key"]), advice=str(raw.get("advice", "")),
                   attention=_opt_float(raw.get("attention")),
                   unusable=_opt_float(raw.get("unusable")))

    def to_dict(self) -> dict:
        out = {"key": self.key}
        if self.attention is not None:
            out["attention"] = self.attention
        if self.unusable is not None:
            out["unusable"] = self.unusable
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

    __slots__ = ("name", "metric", "thresholds", "source")

    def __init__(self, name: str, metric: str,
                 thresholds: "list[Threshold] | None" = None,
                 source: str = ""):
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
        seen = set()
        for th in self.thresholds:
            if th.key in seen:
                raise CaseTypeError(
                    "case type %r sets two thresholds on %r; one figure has one "
                    "bound pair, or the second would silently win"
                    % (self.name, th.key))
            seen.add(th.key)

    @classmethod
    def from_dict(cls, doc: dict, source: str = "") -> "CaseType":
        if not isinstance(doc, dict):
            raise CaseTypeError("a case type must be a JSON object")
        if doc.get("schema") != SCHEMA:
            raise CaseTypeError(
                "not a case type: expected schema %r, got %r"
                % (SCHEMA, doc.get("schema")))
        version = doc.get("version")
        if version != SCHEMA_VERSION:
            raise CaseTypeError(
                "case type schema version %r is not %d, which is the only one "
                "this build reads" % (version, SCHEMA_VERSION))
        unknown = set(doc) - {"schema", "version", "name", "metric", "thresholds"}
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
        return cls(name=str(doc.get("name", "")),
                   metric=str(doc.get("metric", "")),
                   thresholds=[Threshold.from_dict(t) for t in raw],
                   source=source)

    def to_dict(self) -> dict:
        return {"schema": SCHEMA, "version": SCHEMA_VERSION,
                "name": self.name, "metric": self.metric,
                "thresholds": [t.to_dict() for t in self.thresholds]}

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("CaseType(name=%r, metric=%r, thresholds=%d)"
                % (self.name, self.metric, len(self.thresholds)))


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
