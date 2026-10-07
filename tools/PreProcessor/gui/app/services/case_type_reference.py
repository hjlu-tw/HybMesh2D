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
is one threshold's claim to have been derived from them times a tolerance
factor. ADR-0002's first consequence states the rule this implements — "a
misjudged verdict is corrected by adding a reference mesh, not by hand-editing
the number (which would throw the traceability away)".

A CASE TYPE RESTS ON MORE THAN ONE MESH (#168). A case type starts from one
reference mesh, which is a thin basis: it has an opinion about what that mesh
happened to exercise and none about anything else. When a verdict judges wrong,
the maintainer adds the offending mesh — as a further EXEMPLAR, a mesh the
thresholds must keep accepting, or as a COUNTER-EXAMPLE, one they must now
reject — and the bounds move. What a SET of them derives, and whether a document
obeys that derivation, is `services/case_type_evidence.py` — `Evidence` and
`check_derivations` / `check_standing` — and NOT this module: that arithmetic
needs a `Threshold`'s factor and a `ReferenceMesh`'s figure together, so it fits
neither the document nor the vocabulary and was given a file of its own. What is
here is the vocabulary that derivation is expressed in: the figure keys, the two
KINDS a reference mesh can be, the `Origin` that records which meshes a bound
rests on and times what, and `exceeds` — the one comparison both that module and
`case_type_verdict` ask.
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

#: What a reference mesh is EVIDENCE OF (#168). An EXEMPLAR is a mesh the
#: thresholds must accept — the only kind there was before this ticket, which is
#: why it is the default and why no v1-v4 document has to say so. A
#: COUNTER-EXAMPLE is a mesh they must REJECT: the maintainer saw a verdict judge
#: it wrongly usable, and the correction is to add the mesh rather than to edit
#: the number it got wrong.
EXEMPLAR = "exemplar"
COUNTER = "counter-example"
KINDS = (EXEMPLAR, COUNTER)


def exceeds(value, bound) -> bool:
    """Does `value` cross `bound`? THE comparison, written once (#168).

    `case_type_verdict.judge_threshold` asks it of a finished mesh, and
    `case_type_evidence` asks it of every reference mesh a case type declares —
    which is what makes "every exemplar is accepted and every counter-example is
    rejected" a statement about the SAME rule the verdict applies, rather than a
    second opinion that is free to drift from it. STRICTLY greater: a figure
    sitting exactly ON its bound has not crossed it, and a derivation that wants
    to reject a mesh must therefore put the bound strictly below its figure.
    """
    return bound is not None and value is not None and value > bound


def check_bound(bound: str) -> str:
    """`bound` if it names one, else raise. One owner, two askers.

    `Origin.factor_for` and `Threshold.origin_of` both take a bound name from a
    caller, and the same three lines in two files is where one of them acquires
    a different message — or a different answer — by edit.
    """
    if bound not in BOUNDS:
        raise CaseTypeError("%r is not a bound; expected one of %s"
                            % (bound, ", ".join(BOUNDS)))
    return bound


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
    """WHICH reference meshes a threshold's bounds rest on, and times what.

    This is what makes a threshold a DEMONSTRATION rather than an invented
    number (#161, ADR-0002's first consequence): the maintainer knows which mesh
    is good, and does not necessarily know what its p95 is. A bound is those
    meshes' own published figures times a TOLERANCE FACTOR, so it is a band
    rather than a knife edge, and six months later the number is still traceable
    to the meshes it came from.

    `references` IS THE SUPPORT, AND IT IS A LIST (#168). A case type that rests
    on one mesh has an opinion about what that mesh happened to exercise and none
    about anything else, so a misjudged verdict is corrected by ADDING a mesh —
    and from then on the threshold rests on every reference that published its
    figure, exemplars and counter-examples alike. That is user story 39 held by
    the file rather than by a memory: the ids are written down beside the number.
    A v1-v4 document spells one id as `reference`, which is read as a support of
    one; this build writes `references` and nothing else.

    IT HOLDS NO FIGURE. The measured values live once, in the named
    `ReferenceMesh`'s own `figures`, and the bound is re-derived from them — so
    the file cannot disagree with itself about what a reference mesh measured.
    That check needs the case type's reference list, which is why it is
    `case_type_evidence.check_derivations` that performs it and not this class.

    A FACTOR IS WHAT MAKES A BOUND MEASURED. Present for a bound, that bound was
    derived; absent while the bound is set, the maintainer typed it — which is
    how "an overridden threshold is distinguishable from a measured one" is held
    by the file's SHAPE rather than by a flag that can disagree with the number
    beside it. An override of ONE bound keeps the reference, so what it overrode
    is still on the record; a threshold whose bounds are BOTH hand-set carries no
    origin at all, since an origin that derived nothing is not provenance.

    A FACTOR BELOW 1.0 IS REFUSED. It would put the bound UNDER the figure the
    reference mesh published, so the mesh the maintainer judged good would fail
    the case type it authored — which is not a tight threshold but an incoherent
    one.
    """

    __slots__ = ("references", "attention_factor", "unusable_factor")

    #: How far a stated bound may sit from `value * factor` and still be read as
    #: that product. Machine-written files round-trip exactly through JSON, so
    #: this is tight on purpose: a maintainer who ROUNDS a derived bound for
    #: readability has hand-set it, and the honest spelling of that is to drop
    #: the factor and let it read as an override.
    REL_TOL = 1e-9

    def __init__(self, references, attention_factor: float | None = None,
                 unusable_factor: float | None = None):
        # A bare string is a support of ONE, which is what every call site that
        # derives a bound from a single mesh writes and what a v1-v4 document
        # spells. Accepted here rather than normalised by each caller, so there
        # is one answer to "what is a support" and not one per reader.
        if isinstance(references, str):
            references = [references]
        idents = tuple(str(r).strip() for r in references or ())
        if not idents or not all(idents):
            raise CaseTypeError(
                "a threshold's origin names no reference mesh; provenance that "
                "does not say which mesh is not provenance")
        if len(set(idents)) != len(idents):
            raise CaseTypeError(
                "a threshold's origin names %s twice; a support that counts one "
                "mesh as two is not a support" % (idents,))
        # Parsed BEFORE being compared, so a factor that is not a number raises
        # `CaseTypeError` like every other malformed field rather than a bare
        # `ValueError` out of the comparison, which no caller is catching.
        factors = {"attention": opt_float(attention_factor),
                   "unusable": opt_float(unusable_factor)}
        if all(f is None for f in factors.values()):
            raise CaseTypeError(
                "a threshold's origin names reference mesh(es) %s but no "
                "tolerance factor, so no bound was derived from them"
                % ", ".join(idents))
        for name, factor in factors.items():
            if factor is not None and factor < 1.0:
                raise CaseTypeError(
                    "%s_factor is %g, below 1.0: the bound would sit under the "
                    "figure the reference mesh published, so the mesh the "
                    "maintainer judged good would fail the case type it "
                    "authored" % (name, factor))
        self.references = idents
        self.attention_factor = factors["attention"]
        self.unusable_factor = factors["unusable"]

    def factor_for(self, bound: str) -> float | None:
        """The tolerance factor for `bound`, or ``None`` when it was hand-set."""
        return getattr(self, check_bound(bound) + "_factor")

    @classmethod
    def from_dict(cls, raw: dict, key: str) -> "Origin":
        if not isinstance(raw, dict):
            raise CaseTypeError(
                "threshold %r: `measured_from` must be an object, got %r"
                % (key, raw))
        unknown = set(raw) - {"reference", "references", "attention_factor",
                              "unusable_factor"}
        if unknown:
            raise CaseTypeError(
                "threshold %r: unknown key(s) in `measured_from`: %s"
                % (key, ", ".join(sorted(unknown))))
        if "reference" in raw and "references" in raw:
            # Both spellings at once is a document that may disagree with
            # itself about its own provenance, which is the one thing this
            # class exists to make impossible.
            raise CaseTypeError(
                "threshold %r: `measured_from` spells its support both as "
                "`reference` and as `references`; one of the two is the one "
                "that is read, and a reader cannot be asked to guess which"
                % key)
        raw_refs = raw.get("references", raw.get("reference", ""))
        if isinstance(raw_refs, list):
            raw_refs = [str(r) for r in raw_refs]
        return cls(references=raw_refs,
                   attention_factor=opt_float(raw.get("attention_factor")),
                   unusable_factor=opt_float(raw.get("unusable_factor")))

    def to_dict(self) -> dict:
        out = {"references": list(self.references)}
        for bound in BOUNDS:
            factor = self.factor_for(bound)
            if factor is not None:
                out[bound + "_factor"] = factor
        return out

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("Origin(references=%r, attention_factor=%r, unusable_factor=%r)"
                % (self.references, self.attention_factor,
                   self.unusable_factor))


class ReferenceMesh:
    """A mesh the maintainer judged good, and the figures it published.

    The EVIDENCE behind a case type's thresholds (#161). It is recorded rather
    than merely consulted because the point is traceability: six months later a
    threshold must still name the mesh it came from, which means the file has to
    hold the mesh, the sidecar the numbers were read out of, the date they were
    read, and the figures themselves. A reference recorded as a path alone would
    say nothing once that mesh is regenerated.

    `kind` is what the mesh is evidence OF (#168): an `EXEMPLAR` the thresholds
    must accept, or a `COUNTER-EXAMPLE` they must reject. It is recorded on the
    MESH rather than on the threshold because it is a fact about the mesh — the
    maintainer judged it good or judged it bad — and one mesh cannot be good
    evidence for one figure and bad evidence for another. Every case type
    authored before #168 declares exemplars only, which is why `EXEMPLAR` is the
    default and why a v1-v4 document needs no new key to keep meaning what it
    said.

    `figures` holds ONLY what the reference mesh actually measured. A figure the
    mesher could not measure is ABSENT, never a negative number carried forward
    — `include/CellShape.hpp` writes a set's three figures negative together with
    its count 0 precisely so "we did not measure" cannot read as a value, and a
    threshold derived from one of those would be a bound nothing can mean. That
    absence is what makes "a figure the reference mesh could not measure produces
    no threshold" a property of the artefact and not only of the authoring step.
    """

    __slots__ = ("ident", "mesh", "provenance", "metric", "measured_on",
                 "figures", "kind")

    def __init__(self, ident: str, metric: str, figures: dict,
                 mesh: str = "", provenance: str = "", measured_on: str = "",
                 kind: str = EXEMPLAR):
        if kind not in KINDS:
            raise CaseTypeError(
                "reference mesh %r is a %r, which is not a kind of evidence; "
                "expected one of %s" % (ident, kind, ", ".join(KINDS)))
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
        self.kind = kind
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
                              "measured_on", "figures", "kind"}
        if unknown:
            raise CaseTypeError("reference mesh %r carries unknown key(s): %s"
                                % (raw.get("id"), ", ".join(sorted(unknown))))
        return cls(ident=str(raw.get("id", "")),
                   metric=str(raw.get("metric", "")),
                   figures=raw.get("figures", {}),
                   mesh=str(raw.get("mesh", "")),
                   provenance=str(raw.get("provenance", "")),
                   measured_on=str(raw.get("measured_on", "")),
                   kind=str(raw.get("kind", EXEMPLAR)))

    def to_dict(self) -> dict:
        out = {"id": self.ident, "metric": self.metric}
        if self.kind != EXEMPLAR:
            # Written only when it is NOT the default, so a case type that
            # declares exemplars only comes back out of a round trip as the
            # document it was — the same rule `fields` and `reference_meshes`
            # already follow in `CaseType.to_dict`.
            out["kind"] = self.kind
        for name in ("mesh", "provenance", "measured_on"):
            if getattr(self, name):
                out[name] = getattr(self, name)
        out["figures"] = {k: self.figures[k] for k in FIGURE_KEYS
                          if k in self.figures}
        return out

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("ReferenceMesh(ident=%r, kind=%r, metric=%r, figures=%d)"
                % (self.ident, self.kind, self.metric, len(self.figures)))
