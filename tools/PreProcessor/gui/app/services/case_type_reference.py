"""WHAT a case type's numbers are about, and WHERE they were measured. Qt-free.

The lower half of the case-type artefact (#160's figures and errors, #161's
provenance); `services/case_type.py` is the document that holds them — its name,
its metric, its thresholds and their advice — and this module is imported by it
and re-exported from it, so every existing `case_type.FIGURE_KEYS` /
`case_type.CaseTypeError` reader is untouched. The dependency runs ONE way,
document -> figures, and the cut is the ~500-line GUI file-length standard
rather than a second home for the knowledge: a THRESHOLD is declared in
`case_type.py` and nowhere else, and what is here is the vocabulary it is
declared in. Same shape as `mesh_config.py` / `mesh_config_validate.py` (#159)
and as the `case_type.py` / `case_type_verdict.py` split beside it.

WHAT A THRESHOLD IS ABOUT. The figures are the ones the mesher already publishes
in `<mesh>.provenance.json`, read by `services/mesh_shape_stats.py` — the
whole-mesh `median` / `p95` / `max` of the cell-shape metric, and since #143/#144
the same three over each half of the wall/bulk split. Every one of them is a
ratio whose floor is 1.0 and whose larger values are worse, so a threshold is an
UPPER BOUND and nothing here needs a direction flag. The nine keys are
`FIGURE_KEYS`; a file naming anything else is refused on load rather than
silently ignored, because a threshold nobody evaluates is worse than none.

WHERE THE NUMBERS CAME FROM is #161's half, and it is what makes a threshold a
DEMONSTRATION rather than an invented number: a `ReferenceMesh` is a mesh the
maintainer judged good, recorded with the figures it published, and an `Origin`
is one threshold's claim to have been derived from one of them times a tolerance
factor. ADR-0002's first consequence states the rule this implements — "a
misjudged verdict is corrected by adding a reference mesh, not by hand-editing
the number (which would throw the traceability away)".
"""
from __future__ import annotations

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


def opt_float(value) -> float | None:
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


#: What `Threshold.origin_of` answers. STRINGS for the same reason the verdict
#: states are: they are written into a report and read by a person, and
#: "measured" has to survive the trip to mean anything.
MEASURED = "measured"
MANUAL = "manual"

#: The two bound names, in the order a threshold is read. One declaration, so a
#: third band could not reach `Origin` and miss `Threshold`.
BOUNDS = ("attention", "unusable")


def split_key(key: str) -> tuple:
    """A figure key as `(set name, field)` — `("", "p95")`, `("bulk", "p95")`.

    ONE owner for the shape of a key, because two readers that disagree about
    where the dot falls would read two different numbers out of one sidecar.
    """
    set_name, _, field = key.rpartition(".")
    return set_name, field


def figures_for(summary, set_name: str):
    """The `ShapeFigures` a key's set names, or ``None`` when it is absent.

    Only a HALF is ever absent, and only on a sidecar from a path that did not
    split — the whole-mesh set IS the summary. Duck-typed on purpose: this module
    knows the shape of `mesh_shape_stats.ShapeSummary` and imports nothing from
    it, so the figure vocabulary stays free of the sidecar reader.
    """
    if not set_name:
        return summary
    return getattr(summary, set_name, None)


class Origin:
    """WHICH reference mesh a threshold's bounds were measured from, and times what.

    This is what makes a threshold a DEMONSTRATION rather than an invented
    number (#161, ADR-0002's first consequence): the maintainer knows which mesh
    is good, and does not necessarily know what its p95 is. A bound is that
    mesh's own published figure times a TOLERANCE FACTOR, so it is a band rather
    than a knife edge, and six months later the number is still traceable to the
    mesh it came from.

    IT HOLDS NO FIGURE. The measured value lives once, in the named
    `ReferenceMesh`'s own `figures`, and the bound is re-derived from it — so the
    file cannot disagree with itself about what the reference mesh measured. That
    check needs the case type's reference list, which is why it is
    `CaseType.__init__` that performs it and not this class.

    A FACTOR IS WHAT MAKES A BOUND MEASURED. Present for a bound, that bound was
    derived; absent while the bound is set, the maintainer typed it — which is
    how "an overridden threshold is distinguishable from a measured one" is held
    by the file's SHAPE rather than by a flag that can disagree with the number
    beside it. An override keeps the reference, so what it overrode is still on
    the record.

    A FACTOR BELOW 1.0 IS REFUSED. It would put the bound UNDER the figure the
    reference mesh published, so the mesh the maintainer judged good would fail
    the case type it authored — which is not a tight threshold but an incoherent
    one.
    """

    __slots__ = ("reference", "attention_factor", "unusable_factor")

    #: How far a stated bound may sit from `value * factor` and still be read as
    #: that product. Machine-written files round-trip exactly through JSON, so
    #: this is tight on purpose: a maintainer who ROUNDS a derived bound for
    #: readability has hand-set it, and the honest spelling of that is to drop
    #: the factor and let it read as an override.
    REL_TOL = 1e-9

    def __init__(self, reference: str, attention_factor: float | None = None,
                 unusable_factor: float | None = None):
        if not str(reference).strip():
            raise CaseTypeError(
                "a threshold's origin names no reference mesh; provenance that "
                "does not say which mesh is not provenance")
        # Parsed BEFORE being compared, so a factor that is not a number raises
        # `CaseTypeError` like every other malformed field rather than a bare
        # `ValueError` out of the comparison, which no caller is catching.
        factors = {"attention": opt_float(attention_factor),
                   "unusable": opt_float(unusable_factor)}
        if all(f is None for f in factors.values()):
            raise CaseTypeError(
                "a threshold's origin names reference mesh %r but no tolerance "
                "factor, so no bound was derived from it" % (reference,))
        for name, factor in factors.items():
            if factor is not None and factor < 1.0:
                raise CaseTypeError(
                    "%s_factor is %g, below 1.0: the bound would sit under the "
                    "figure the reference mesh published, so the mesh the "
                    "maintainer judged good would fail the case type it "
                    "authored" % (name, factor))
        self.reference = str(reference).strip()
        self.attention_factor = factors["attention"]
        self.unusable_factor = factors["unusable"]

    def factor_for(self, bound: str) -> float | None:
        """The tolerance factor for `bound`, or ``None`` when it was hand-set."""
        if bound not in BOUNDS:
            raise CaseTypeError("%r is not a bound; expected one of %s"
                                % (bound, ", ".join(BOUNDS)))
        return getattr(self, bound + "_factor")

    @classmethod
    def from_dict(cls, raw: dict, key: str) -> "Origin":
        if not isinstance(raw, dict):
            raise CaseTypeError(
                "threshold %r: `measured_from` must be an object, got %r"
                % (key, raw))
        unknown = set(raw) - {"reference", "attention_factor", "unusable_factor"}
        if unknown:
            raise CaseTypeError(
                "threshold %r: unknown key(s) in `measured_from`: %s"
                % (key, ", ".join(sorted(unknown))))
        return cls(reference=str(raw.get("reference", "")),
                   attention_factor=opt_float(raw.get("attention_factor")),
                   unusable_factor=opt_float(raw.get("unusable_factor")))

    def to_dict(self) -> dict:
        out = {"reference": self.reference}
        for bound in BOUNDS:
            factor = self.factor_for(bound)
            if factor is not None:
                out[bound + "_factor"] = factor
        return out

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("Origin(reference=%r, attention_factor=%r, unusable_factor=%r)"
                % (self.reference, self.attention_factor, self.unusable_factor))


class ReferenceMesh:
    """A mesh the maintainer judged good, and the figures it published.

    The EVIDENCE behind a case type's thresholds (#161). It is recorded rather
    than merely consulted because the point is traceability: six months later a
    threshold must still name the mesh it came from, which means the file has to
    hold the mesh, the sidecar the numbers were read out of, the date they were
    read, and the figures themselves. A reference recorded as a path alone would
    say nothing once that mesh is regenerated.

    `figures` holds ONLY what the reference mesh actually measured. A figure the
    mesher could not measure is ABSENT, never a negative number carried forward
    — `include/CellShape.hpp` writes a set's three figures negative together with
    its count 0 precisely so "we did not measure" cannot read as a value, and a
    threshold derived from one of those would be a bound nothing can mean. That
    absence is what makes "a figure the reference mesh could not measure produces
    no threshold" a property of the artefact and not only of the authoring step.
    """

    __slots__ = ("ident", "mesh", "provenance", "metric", "measured_on",
                 "figures")

    def __init__(self, ident: str, metric: str, figures: dict,
                 mesh: str = "", provenance: str = "", measured_on: str = ""):
        if not str(ident).strip():
            raise CaseTypeError(
                "a reference mesh must have an id; thresholds name it to say "
                "where their numbers came from")
        if not str(metric).strip():
            raise CaseTypeError(
                "reference mesh %r names no metric" % (ident,))
        if not isinstance(figures, dict):
            raise CaseTypeError(
                "reference mesh %r: `figures` must be an object" % (ident,))
        unknown = set(figures) - set(FIGURE_KEYS)
        if unknown:
            raise CaseTypeError(
                "reference mesh %r publishes figure(s) the mesher does not: %s"
                % (ident, ", ".join(sorted(unknown))))
        clean = {}
        for key, value in figures.items():
            number = opt_float(value)
            if number is None or number <= 0.0:
                raise CaseTypeError(
                    "reference mesh %r records %r for %s; the mesher writes a "
                    "figure NEGATIVE when it could not measure it, and an "
                    "unmeasured figure must be ABSENT rather than carried"
                    % (ident, value, key))
            clean[key] = number
        if not clean:
            raise CaseTypeError(
                "reference mesh %r publishes no figures at all; a mesh nothing "
                "could be measured on can demonstrate no threshold" % (ident,))
        self.ident = str(ident).strip()
        self.metric = str(metric).strip()
        self.figures = clean
        self.mesh = str(mesh)
        self.provenance = str(provenance)
        self.measured_on = str(measured_on)

    def figure(self, key: str) -> float | None:
        """What this mesh published for `key`, or ``None`` when it measured none."""
        return self.figures.get(key)

    @classmethod
    def from_dict(cls, raw: dict) -> "ReferenceMesh":
        if not isinstance(raw, dict):
            raise CaseTypeError("a reference mesh must be an object, got %r"
                                % (raw,))
        unknown = set(raw) - {"id", "mesh", "provenance", "metric",
                              "measured_on", "figures"}
        if unknown:
            raise CaseTypeError("reference mesh %r carries unknown key(s): %s"
                                % (raw.get("id"), ", ".join(sorted(unknown))))
        return cls(ident=str(raw.get("id", "")),
                   metric=str(raw.get("metric", "")),
                   figures=raw.get("figures", {}),
                   mesh=str(raw.get("mesh", "")),
                   provenance=str(raw.get("provenance", "")),
                   measured_on=str(raw.get("measured_on", "")))

    def to_dict(self) -> dict:
        out = {"id": self.ident, "metric": self.metric}
        for name in ("mesh", "provenance", "measured_on"):
            if getattr(self, name):
                out[name] = getattr(self, name)
        out["figures"] = {k: self.figures[k] for k in FIGURE_KEYS
                          if k in self.figures}
        return out

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("ReferenceMesh(ident=%r, metric=%r, figures=%d)"
                % (self.ident, self.metric, len(self.figures)))
