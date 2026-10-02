"""ROLES, not ids: how a case type attaches to the OPERATOR's own CAD. Qt-free.

The seventh file of the case-type seam (#164, parent #158). `case_type.py` is
the document, `case_type_reference.py` the figures and provenance it holds,
`case_type_fields.py` the sparse config overlay, `case_type_scale.py` the
characteristic length that fits that overlay to another drawing,
`case_type_author.py` the step that produces one, `case_type_verdict.py` the
grading. This one closes the gap all six of them left: #162's overlay may carry
`topology.family` and its parameters, but a family that BINDS needs the segments
of the operator's geometry, and #163's gate named the hole in as many words —
"an overlay naming a family cannot be written to a `.dat` on its own", because
every family but the H-grid refuses to build a document with no geometry to
bind to.

**A BINDING CANNOT CARRY OVER, SO IT IS NOT CARRIED.** A binding is a stable
`SegmentModel.id` into the MAINTAINER's geometry (`services/topology_binding.py`
states why it is an id and never a position). The operator's segments have
entirely different ids, so applying a case type is a binding problem from the
first moment rather than an error case — which is why `case_type_fields.EXCLUDED`
rules every `*_geom` / `*_segs` parameter unownable BY SUFFIX. What travels is
the ROLE: the operator says which of their curves is the body and which is the
far field, and the binding is DERIVED against their own segments. No id from the
authoring drawing can survive into the applied case, because none is ever read.

**THE ROLE IS PER SEGMENT, NOT PER GEOMETRY.** `MeshConfig.geom_roles` is keyed
by geometry FILE and answers a different question — does this curve grow a
boundary layer, is it a seed — and a family binds to a LIST of segments in the
geometry's own order. So an assignment here is a set of `(geometry, segment id)`
pairs, and naming a whole geometry is the convenience spelling of "every segment
it carries". A geometry cut into four and a geometry cut into one are then the
same kind of answer.

**THE TOOL MAY GUESS; THE OPERATOR CONFIRMS.** A pre-selected role is offered
with the reason it was offered, and `RolePlan.bind` REFUSES while one is
unconfirmed — structural, rather than a dialog somebody can forget to show, for
the reason `case_type_scale.Application.apply` refuses an unconfirmed physical
parameter. A wrong guess that reaches the mesher silently is the worst failure
available here: the mesh comes out, exports, and has the far field's conditions
on the body.

**DRAWING ORDER IS NOT A CONVENTION ANYBODY MAY USE.** Excluded by decision in
#158, and this repo has a USER-REPORTED defect where drawing order rather than
click order decided a result. The guess ranks candidates by ENCLOSED AREA — the
body is inside the far field whatever order they were drawn in — and refuses to
guess at all when the counts do not line up.

**EVERY PROBLEM AT ONCE.** `problems` lists every role that is missing and every
position that does not resolve, the way `topology_model.broken_bindings` lists
every broken binding rather than the first: repairing them one refusal at a time
is a generate, a refusal and a return per wrong segment. The family's own `plan`
still stops at the first, because it answers "can this run?".

**WHICH ROLES A FAMILY NEEDS IS DERIVED FROM THE MODEL, NOT LISTED.** The slots
are read off `TopologyModel`'s own binding fields by the family's prefix, so a
fifth family's roles exist the day its parameters do. What is DECLARED is the
two things no field name carries: the role word a slot token means
(:data:`SLOT_ROLE`) and the one slot that is optional (:data:`OPTIONAL`), each
with its reason. `tests/test_case_type_roles.py` checks both directions, so a
slot token nobody classified fails rather than defaulting to anything.

ONE SEAM, EIGHT FILES, AND EVERY CUT IS THE ~500-LINE STANDARD rather than a
second home for the knowledge — the shape the six files before this one
already have. The PRE-SELECTION is `services/case_type_guess.py`, re-exported
from here so no caller learns a new name; what stayed is everything that ACTS
on a guess, because the confirmation and the thing confirmed must not be able
to drift apart.
"""
from __future__ import annotations

from dataclasses import fields as dataclass_fields

from app.services.case_type_fields import TOPOLOGY_PREFIX
from app.services.case_type_reference import CaseTypeError
# RE-EXPORTED, not merely used, the way `case_type.py` re-exports the figure
# vocabulary beside it: `case_type_roles.Guess` and `case_type_roles.RANK` are
# what the hosts and the gate already name, and the split below them is a
# file-length cut rather than a second seam for a caller to learn.
from app.services.case_type_guess import Guess  # noqa: F401
from app.services.case_type_guess import NON_OUTLINE_ROLES  # noqa: F401
from app.services.case_type_guess import OUTER_ROLES  # noqa: F401
from app.services.case_type_guess import RANK  # noqa: F401
from app.services.case_type_guess import guess_roles
from app.services.topology_binding import outline_problem
from app.services.topology_ogrid_binding import format_binding
from app.services.topology_params import TopologyModel

#: Why every role here needs a CLOSED outline, for the shared four-question
#: cascade (`topology_binding.outline_problem`). The one clause of it that is
#: this module's own, the way each family supplies its own: every family that
#: binds to the CAD binds a ring, and a ring goes round a closed curve.
CLOSED_NOTE = ("and every family that binds to your CAD binds a ring, which "
               "goes round a closed curve.")

#: The suffixes a binding parameter pair wears. `case_type_fields`'s own
#: constant would do, but it is a TUPLE whose order is its own business; these
#: two are named apart because this module pairs them.
GEOM_SUFFIX, SEGS_SUFFIX = "_geom", "_segs"

#: What each binding slot token MEANS, as the word the operator assigns. The
#: families spell their own role words for their own refusal prose
#: (`topology_cgrid_section.SECTION_ROLE` is "aerofoil"); this is the one
#: vocabulary an operator picks from, and it is #158's own — body, far field,
#: seam. A slot token missing from here is refused rather than defaulting to
#: itself: a role nobody named is a role nobody can assign.
SLOT_ROLE = {
    "body": "body",
    "far": "farfield",
    "seam": "seam",
}

#: What each role is, printed before the operator assigns anything (acceptance:
#: "the roles a case type needs are shown before assignment").
ROLE_MEANING = {
    "body": "the curve the mesh is grown around — the one the boundary layer "
            "sits on",
    "farfield": "the outer boundary of the domain",
    "seam": "the curve the two rings meet on, between the body and the far "
            "field",
}

#: The slots that may be left unbound, with the reason. Keyed `family.role`.
#: Everything else is REQUIRED, so a family that gains a binding is required by
#: default — the safe direction, since an unbound required list is a refusal the
#: operator sees and an unbound optional one is silence.
OPTIONAL = {
    "cgrid.farfield":
        "the C-grid's far field is optionally drawn: left unbound it is "
        "GENERATED from cgrid_wake_length and cgrid_far_radius, which is what "
        "the family's own demo asks for",
}


class RoleSlot:
    """One binding list a family fills, as the role that fills it.

    `geom_field` and `segs_field` are `TopologyModel` attribute names rather
    than widgets, so this stays Qt-free the way `BrokenBinding.field` does.
    """

    __slots__ = ("family", "role", "geom_field", "segs_field", "required",
                 "why_optional")

    def __init__(self, family: str, role: str, geom_field: str,
                 segs_field: str, required: bool = True,
                 why_optional: str = ""):
        self.family = family
        self.role = role
        self.geom_field = geom_field
        self.segs_field = segs_field
        self.required = bool(required)
        self.why_optional = why_optional

    def describe(self) -> str:
        """The line shown before assignment: the role, what it is, and whether
        it must be answered."""
        tail = ("required" if self.required
                else "optional — %s" % self.why_optional)
        return "%s: %s (%s)" % (self.role,
                                ROLE_MEANING.get(self.role, "a bound curve"),
                                tail)

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("RoleSlot(family=%r, role=%r, required=%r)"
                % (self.family, self.role, self.required))


def slots_for(family: str) -> tuple:
    """The roles `family` needs, in the order its own binding lists run.

    Derived from `TopologyModel`'s fields by the family's prefix, so a fifth
    family's roles arrive with its parameters. A family that binds to nothing
    (the H-grid) and a configuration naming no family both return `()`.
    """
    name = str(family or "").strip()
    if not name:
        return ()
    prefix = name + "_"
    declared = {f.name for f in dataclass_fields(TopologyModel)}
    out = []
    for field in dataclass_fields(TopologyModel):
        if not (field.name.startswith(prefix)
                and field.name.endswith(SEGS_SUFFIX)):
            continue
        token = field.name[len(prefix):-len(SEGS_SUFFIX)]
        geom_field = prefix + token + GEOM_SUFFIX
        if geom_field not in declared:
            raise CaseTypeError(
                "topology parameter %r has no %r beside it, so there is no "
                "geometry for a role to bind to" % (field.name, geom_field))
        role = SLOT_ROLE.get(token)
        if role is None:
            raise CaseTypeError(
                "the %s family binds a list called %r and no role word is "
                "declared for %r. Add it to case_type_roles.SLOT_ROLE — a slot "
                "nobody named is a role nobody can assign; the declared ones "
                "are %s" % (name, field.name, token, ", ".join(sorted(SLOT_ROLE))))
        key = "%s.%s" % (name, role)
        out.append(RoleSlot(name, role, geom_field, field.name,
                            required=key not in OPTIONAL,
                            why_optional=OPTIONAL.get(key, "")))
    return tuple(out)


def family_of(config) -> str:
    """The family `config` names, `""` for a configuration that names none.

    Through `names_a_family` rather than the raw attribute: a DETACHED model
    names a family that drives nothing, and deriving bindings for it would write
    parameters no run reads (#139).
    """
    model = getattr(config, "topology", None)
    if model is None or not model.names_a_family():
        return ""
    return str(model.family)


# ── the assignment the operator makes ───────────────────────────────────────

def parse_spec(spec: str) -> tuple:
    """`"geom"` or `"geom:1,2,3"` as `(geometry, segment ids or None)`.

    `None` for the ids means "every segment that geometry carries", which is the
    convenience spelling of the per-segment assignment rather than a second kind
    of answer: it is expanded against the operator's own geometry, in the
    geometry's own order, by :meth:`RolePlan.resolve`.
    """
    text = str(spec or "").strip()
    geom, sep, segs = text.rpartition(":")
    if not sep:
        return text, None
    # A Windows drive letter or a bare `C:` is not a segment list; anything that
    # does not parse WHOLE as a comma-separated run of integers is part of the
    # path. Parsed rather than pattern-matched, so a token that merely LOOKS
    # numeric (`+-5`) cannot raise out of here as a bare `ValueError` no host
    # catches.
    tokens = [t.strip() for t in segs.split(",") if t.strip()]
    if not tokens:
        return text, None
    try:
        ids = tuple(int(t) for t in tokens)
    except ValueError:
        return text, None
    return geom.strip(), ids


class Binding:
    """One role resolved against the operator's drawing: a geometry and its ids."""

    __slots__ = ("role", "geom", "segs")

    def __init__(self, role: str, geom: str, segs):
        self.role = role
        self.geom = geom
        self.segs = tuple(int(s) for s in segs)

    def describe(self) -> str:
        return ("%s -> '%s' segment(s) %s"
                % (self.role, self.geom, format_binding(self.segs) or "(none)"))

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "Binding(role=%r, geom=%r, segs=%r)" % (self.role, self.geom,
                                                       self.segs)


class RolePlan:
    """The roles one case type needs on one drawing, and what fills them.

    Produced by :func:`plan_roles`. Nothing is written until :meth:`bind`, and
    `bind` REFUSES while any pre-selected role is unconfirmed or any required
    one is unassigned — the same shape `case_type_scale.Application` gives the
    physical parameters, and for the same reason: a question a host can skip is
    a question that gets skipped.
    """

    __slots__ = ("family", "slots", "guesses", "ctx")

    def __init__(self, family: str, slots, guesses: dict, ctx=None):
        self.family = family
        self.slots = tuple(slots)
        self.guesses = dict(guesses or {})
        self.ctx = ctx

    @property
    def roles(self) -> tuple:
        return tuple(s.role for s in self.slots)

    def slot(self, role: str):
        for s in self.slots:
            if s.role == role:
                return s
        return None

    def describe(self) -> list:
        """What the operator is shown BEFORE they assign anything.

        One line per role the case type needs — what it is and whether it must
        be answered — and one more per pre-selected guess, which names the
        geometry and the reason rather than just appearing in a box.
        """
        if not self.slots:
            return ["this case type names no family that binds to your CAD, "
                    "so there are no roles to assign"]
        out = [s.describe() for s in self.slots]
        for role in self.roles:
            g = self.guesses.get(role)
            if g is not None:
                out.append("pre-selected %s" % g.describe())
        return out

    # -- resolution -------------------------------------------------------
    def unconfirmed(self, assigned=None) -> tuple:
        """Every pre-selected role the operator has not answered for."""
        answered = set(dict(assigned or {}))
        return tuple(self.guesses[r] for r in self.roles
                     if r in self.guesses and r not in answered)

    def resolve(self, assigned=None) -> tuple:
        """`(bindings, problems)` — what each role binds, and everything wrong.

        EVERY problem, never the first: a drawing with two roles pointing at
        segments that are not there costs two edits, not two round trips
        through a refusal. `topology_model.broken_bindings` is the same rule on
        the stored side, and this is its counterpart on the derived one.
        """
        bindings, problems = [], []
        assigned = dict(assigned or {})
        for role in assigned:
            if self.slot(role) is None:
                problems.append(
                    "%r is not a role this case type needs; it needs %s"
                    % (role, ", ".join(self.roles) or "none"))
        for slot in self.slots:
            role = slot.role
            if role in assigned:
                spec = str(assigned[role] or "").strip()
                if not spec:
                    g = self.guesses.get(role)
                    if g is None:
                        problems.append(
                            "the %s role was confirmed with no geometry, and "
                            "nothing was pre-selected for it. Name the curve: "
                            "%s=<geometry>[:<segment ids>]" % (role, role))
                        continue
                    want_geom, want_segs = g.geom, g.segs
                else:
                    want_geom, want_segs = parse_spec(spec)
            elif role in self.guesses:
                # Unconfirmed. Reported by `unconfirmed`, not as a problem, so
                # the two refusals stay distinguishable.
                continue
            elif slot.required:
                problems.append(
                    "this case type needs a %s and none is assigned — %s. "
                    "Assign it before the run: a family that binds cannot be "
                    "given a drawing with no %s."
                    % (role, ROLE_MEANING.get(role, "a bound curve"), role))
                continue
            else:
                continue
            binding, why = self._resolve_one(slot, want_geom, want_segs)
            if why:
                problems += why
            if binding is not None:
                bindings.append(binding)
        return tuple(bindings), tuple(problems)

    def _resolve_one(self, slot, geom: str, segs) -> tuple:
        """One role against the drawing: `(Binding | None, [problems])`."""
        role = slot.role
        if self.ctx is None:
            return None, ["the %s role cannot be bound: this drawing's "
                          "geometries were never read" % role]
        g = self.ctx.geometry(geom)
        # THE FOUR QUESTIONS ARE ASKED BY THEIR OWNER, never spelled again
        # here. `topology_binding.outline_problem` exists because three
        # families wrote that cascade themselves and the third copy silently
        # dropped the one clause a user can act on; a fourth copy would be the
        # same defect, and writing one is exactly how the CLOSED question — a
        # ring family's precondition, and absent from the first draft of this
        # derivation — goes missing.
        why = outline_problem(self.ctx, role, geom, g, what="curve",
                              closed_note=CLOSED_NOTE)
        if why:
            return None, [why]
        if segs is None:
            return Binding(role, g.spelling, g.seg_ids), []
        # EVERY position, not the first — the derived side of #138's rule that
        # a repair panel lists them all, and the reason this does NOT go
        # through `BindingContext.resolve`: that one raises on the first id it
        # cannot place, because it is answering for one EDGE of a document
        # rather than for a ROLE the operator is still assigning.
        missing = [s for s in segs if s not in g.spans]
        problems = [
            "the %s role binds segment %d of '%s', which it does not carry. It "
            "carries segment(s) %s."
            % (role, s, g.spelling, format_binding(g.seg_ids) or "(none)")
            for s in missing]
        if missing:
            return None, problems
        seen, dup = set(), []
        for s in segs:
            if s in seen:
                dup.append(s)
            else:
                seen.add(s)
        if dup:
            problems.append(
                "the %s role names segment %s twice; one segment cannot be two "
                "sides of the ring."
                % (role, ", ".join(str(d) for d in dup)))
            return None, problems
        # THE GEOMETRY'S OWN ORDER, never the order they were typed: the ring
        # walks the stored list as written, and a list out of the outline's
        # order binds every wall to a different stretch of curve with every id
        # still resolving (`topology_ogrid_binding.order_problem`).
        want = set(segs)
        ordered = [s for s in g.seg_ids if s in want]
        return Binding(role, g.spelling, ordered), problems

    # -- writing ----------------------------------------------------------
    def bind(self, config, assigned=None) -> tuple:
        """Write this drawing's bindings into `config.topology`; return them.

        `config` is mutated in place and the BINDINGS come back, because that is
        what a caller has to report — `case_type_scale.Application.apply`
        returns the config instead for the one reason that does not apply here:
        it may have to create one.

        Raises `CaseTypeError` while any pre-selected role is unconfirmed or
        anything is unresolvable, naming EVERY one. The ids written come only
        from the operator's own geometry — no id from the authoring drawing is
        ever read, because a case type carries none.
        """
        waiting = self.unconfirmed(assigned)
        bindings, problems = self.resolve(assigned)
        if waiting or problems:
            # BOTH halves in ONE refusal, by this module's own every-problem-at-
            # once rule: an operator holding an unconfirmed guess AND a segment
            # that does not resolve has two edits to make, not two round trips.
            parts = []
            if waiting:
                parts.append(
                    "%d role(s) must be confirmed before anything runs, "
                    "because a wrong guess reaching the mesher is a mesh with "
                    "the far field's conditions on the body:\n%s"
                    % (len(waiting),
                       "\n".join("  - " + g.describe() for g in waiting)))
            if problems:
                parts.append("this case type cannot be bound to this drawing:"
                             "\n" + "\n".join("  - " + p for p in problems))
            raise CaseTypeError("\n".join(parts))
        model = getattr(config, "topology", None)
        if model is None:
            raise CaseTypeError(
                "this configuration carries no topology model, so there is "
                "nothing to bind")
        for b in bindings:
            slot = self.slot(b.role)
            setattr(model, slot.geom_field, b.geom)
            setattr(model, slot.segs_field, format_binding(b.segs))
        return bindings


def plan_roles(config, ctx=None) -> RolePlan:
    """The roles `config`'s family needs on the drawing `ctx` describes.

    `config` is the OPERATOR's own, already carrying the case type's family —
    which is an ordinary overlay field (`case_type_fields`), so this module asks
    the configuration rather than the case type and works just as well for a
    project that picked its family by hand.
    """
    family = family_of(config)
    slots = slots_for(family)
    return RolePlan(family, slots, guess_roles(slots, ctx, config), ctx)


def plan_for(case_type, config, ctx=None) -> RolePlan:
    """The roles `case_type` will need on this drawing, BEFORE it is applied.

    The same plan :func:`plan_roles` makes, read off the case type's own overlay
    rather than off a configuration it has already been written into — so the
    roles can be SHOWN before assignment (and before the physical parameters are
    confirmed, which would otherwise refuse first and leave the operator never
    having seen which curves they are being asked for).

    A case type with no opinion about the family leaves the operator's own in
    force; a project that has DETACHED its template has no family that drives a
    run, so a case type naming one binds nothing until it is re-attached.
    """
    family = str((case_type.fields.values.get(TOPOLOGY_PREFIX + "family")
                  if case_type is not None else "") or "")
    model = getattr(config, "topology", None)
    if not family:
        family = family_of(config)
    elif model is not None and model.is_detached():
        family = ""
    slots = slots_for(family)
    return RolePlan(family, slots, guess_roles(slots, ctx, config), ctx)
