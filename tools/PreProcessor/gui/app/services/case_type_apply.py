"""APPLYING a case type to the operator's own drawing, as ONE act. Qt-free.

The ninth file of the case-type seam (#170, parent #158). `case_type.py` is the
document, `case_type_reference.py` the figures and provenance it holds,
`case_type_fields.py` the sparse config overlay, `case_type_scale.py` the
characteristic length that fits that overlay to another drawing,
`case_type_roles.py` and `case_type_guess.py` the roles that bind its family to
the operator's curves, `case_type_author.py` the step that produces one,
`case_type_verdict.py` the grading, `case_type_picker.py` WHICH one is in play.
This one is the act those eight exist for, and until #170 it existed only as
`apply_case_type.py`'s `main()` — a hundred lines of host, reachable from no
window, which is why #169's picker had to say in its own docstring that it
SELECTS WHAT JUDGES and applies nothing.

**IT IS ONE ACT, WITH ONE INTERRUPT.** Fields, roles and the family's own
pre-flight are three questions about one decision, and a host that applied the
fields and left the family unbound would create a state nothing records and the
deviation marking cannot describe: a run whose numbers came from a case type and
whose topology did not. So :func:`apply` writes everything or nothing. The one
thing that must interrupt is the PHYSICAL parameter (#158 story 23), and it
interrupts by being REFUSED here rather than by a dialog the host remembers to
show — `case_type_scale.Application.apply`'s rule, reached rather than restated.

**NOTHING IS WRITTEN UNTIL EVERYTHING PASSES.** The overlay is applied to a DEEP
COPY, the roles are bound into that copy and the pre-flight is asked of it; the
caller is handed the copy only if all three succeed. `case_type_fields.apply`
mutates in place, so applying to the live configuration and then discovering the
family cannot fill the drawing would leave the operator's own numbers overwritten
by a case type that was refused — the half-applied state in its worst form, since
the refusal is the moment they most need their drawing back as it was.

**EVERY PROBLEM AT ONCE, ACROSS ALL THREE KINDS.** An unconfirmed role, a segment
that does not resolve and an unconfirmed first cell height are collected into ONE
refusal. `apply_case_type.py` reaches them in three separate raises and so costs
three runs to clear; `case_type_roles.RolePlan` already states the rule — "every
problem, never the first" — and this is it applied one level up, across the
services rather than within one. The PRE-FLIGHT is the exception and cannot be
otherwise: a family can only be asked whether it can fill a drawing once the
bindings exist, so it is a second round by construction, not by choice.

**THE REFUSAL CARRIES THE CURVES, NOT ONLY THE SENTENCE.**
:class:`PreflightRefused` holds the `Refusal` rows verbatim so a window can point
at the offending curve on the canvas — which is what makes #158's stories 25-27
("told in my terms, with the curve pointed at") reachable at APPLY time and not
only when Generate is pressed. `topology_preflight.Refusal` is a dataclass for
exactly this reason, and `mesh_gen_diag_ctrl._draw_preflight_refusal` is the
drawing of it; this module re-words nothing.

**WHAT THE OPERATOR ALREADY EDITED IS OVERWRITTEN, AND SAID FIRST.** The overlay
is sparse, so only the fields the case type has an opinion about move; every one
is reported as `was -> now` by :meth:`ApplyPlan.changes` BEFORE anything is
written, and the whole apply is one undo step. The alternative — keeping a field
the operator had moved — makes a third state the deviation marking has no word
for, where some owned fields are the case type's and some are not and nothing
records which. #158's story 21 (a case type is a starting point, not a cage) is
answered the other way round: after applying, any field can be moved again, and
the read-out marks it MOVED the moment it is.

**A ROLE THIS CASE TYPE DOES NOT NEED IS KEPT AND NOT USED.** Switching case
types changes which roles exist, and dropping the assignments for the old one
would lose the operator's work the moment they looked at a second case type.
They stay in `MeshConfig.case_type_roles`, they are EXCLUDED from what is bound,
and :attr:`ApplyPlan.ignored` names them out loud — `RolePlan.resolve` would
otherwise report each as a problem, which would make merely having looked at
another case type a refusal.
"""
from __future__ import annotations

import copy

from app.services import case_type_fields, case_type_picker, case_type_roles
from app.services import case_type_scale, topology_binding, topology_model
from app.services import topology_preflight
from app.services.case_type_reference import CaseTypeError
from app.services.logging_setup import get_logger

logger = get_logger(__name__)


class PreflightRefused(CaseTypeError):
    """The family cannot fill this drawing, with the rows a host can point at.

    A `CaseTypeError` so every existing host — `apply_case_type.py` included —
    catches it as it always did, and a subclass so the ONE host that can draw on
    a canvas gets the curves without re-parsing the prose it was handed.
    """

    def __init__(self, message: str, refusals=()):
        super().__init__(message)
        self.refusals = tuple(refusals)


class Change:
    """One owned field moving: what this drawing holds now, and what it will hold.

    `confirmed` marks a PHYSICAL parameter — a value the operator answered for
    rather than one the ruler produced — so a report can say which of the two
    kinds each row is without the reader having to know `LENGTH_KIND`.
    """

    __slots__ = ("name", "was", "now", "confirmed")

    def __init__(self, name: str, was, now, confirmed: bool = False):
        self.name, self.was, self.now = name, was, now
        self.confirmed = bool(confirmed)

    @property
    def moves(self) -> bool:
        """True when applying actually changes this field's value."""
        return not case_type_fields.same(self.was, self.now)

    def describe(self) -> str:
        show = case_type_fields.show_value
        if not self.moves:
            return "%s = %s (unchanged)" % (self.name, show(self.now))
        return ("%s: %s -> %s%s"
                % (self.name, show(self.was), show(self.now),
                   "   (confirmed)" if self.confirmed else ""))

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "Change(name=%r, was=%r, now=%r)" % (self.name, self.was, self.now)


class ApplyPlan:
    """Everything applying this case type to this drawing would do, and what it needs.

    Produced by :func:`plan`, and deliberately readable BEFORE the operator
    presses anything: the roles it needs, what it pre-selected and why, which
    fields would move and which values it will ask them to confirm. #158's
    stories 24 ("see which fields the case type had an opinion about") and 3-4
    are answered by reading one of these, not by running it.
    """

    __slots__ = ("case_type", "application", "roles", "assigned", "ignored")

    def __init__(self, case_type, application, roles, assigned: dict,
                 ignored: tuple):
        self.case_type = case_type
        self.application = application
        self.roles = roles
        self.assigned = dict(assigned)
        self.ignored = tuple(ignored)

    # -- what it needs answered -------------------------------------------
    @property
    def confirmations(self) -> tuple:
        """The physical parameters, which are asked on EVERY application."""
        return self.application.confirmations

    def unconfirmed_roles(self) -> tuple:
        """Every pre-selected role the operator has not answered for."""
        return self.roles.unconfirmed(self.assigned)

    def problems(self) -> tuple:
        """Every role that is missing and every position that does not resolve."""
        return self.roles.resolve(self.assigned)[1]

    def bindings(self) -> tuple:
        """What each role binds on this drawing, as far as it resolves.

        The read-only half of what :func:`apply` would write, so a view can show
        it without walking `plan.roles.resolve(plan.assigned)[0]` — three levels
        into another object's data for a question this one can answer.
        """
        return self.roles.resolve(self.assigned)[0]

    def candidates(self) -> tuple:
        """The geometries of this drawing a role may be assigned to.

        `()` when the family binds to nothing, or when the drawing's geometries
        were never read. The table offers EVERY one rather than only the closed
        outlines a ring can bind: a curve missing from the list with no reason
        given is the silence this seam exists against, and
        `topology_binding.outline_problem` is where the reason lives.
        """
        ctx = self.roles.ctx
        return tuple(ctx.geoms) if ctx is not None else ()

    def ready(self) -> bool:
        """True when only the physical confirmations stand between this and a run."""
        return not self.unconfirmed_roles() and not self.problems()

    # -- what it would do --------------------------------------------------
    def changes(self, config, confirmed=None) -> tuple:
        """One :class:`Change` per owned field: what this drawing holds, and what it will.

        `confirmed` is folded in so the report the operator approves is the
        report of what they approved — a confirmation that CORRECTED the offered
        value (`--confirm name=2e-6`'s own case) must not be shown as the offered
        one, or the dialog would describe a different apply from the one it
        performs.
        """
        answered = dict(confirmed or {})
        asked = {c.name for c in self.confirmations}
        out = []
        for name, value in self.application.values.items():
            now = answered.get(name, value)
            out.append(Change(name, case_type_fields.value_of(config, name),
                              now, name in asked))
        return tuple(out)

    def describe(self, config, confirmed=None) -> list:
        """The whole act in prose: the ruler, the fields, the roles, the residue."""
        ct = self.case_type
        out = ["Apply %r — thresholds on %s." % (ct.name, ct.metric)]
        if ct.characteristic is not None and self.application.scale.factor != 1.0:
            s = self.application.scale
            out.append("Authored against %s; on this drawing every "
                       "geometry-driven size x %.6g, positions mapped about "
                       "(%.6g, %.6g)."
                       % (ct.characteristic.describe(), s.factor,
                          s.centre[0], s.centre[1]))
        out += ["    " + c.describe() for c in self.changes(config, confirmed)]
        if self.roles.slots:
            out.append("Roles this case type needs on your own geometry:")
            out += ["    " + line for line in self.roles.describe()]
        for role in self.ignored:
            out.append("'%s' is assigned on this drawing and this case type does "
                       "not need it; the assignment is kept and not used." % role)
        return out


class Applied:
    """What an application produced: the fitted configuration and its bindings."""

    __slots__ = ("config", "bindings", "changes")

    def __init__(self, config, bindings, changes):
        self.config = config
        self.bindings = tuple(bindings)
        self.changes = tuple(changes)

    def describe(self) -> list:
        return ([c.describe() for c in self.changes if c.moves]
                + ["bound " + b.describe() for b in self.bindings])


def plan(config) -> ApplyPlan:
    """What applying the case type `config` NAMES would do to this drawing.

    Raises `CaseTypeError` when the configuration names no case type, or names
    one that will not load — the operator asked to apply something, and "there
    is nothing to apply" and "the thing you picked is broken" are different
    answers they are owed separately.

    `case_type_picker.for_config` is what reads the choice, so the precedence
    rule (the document in hand beats `HYBMESH_CASE_TYPE`) is this module's by
    reference and not by a second copy.
    """
    ct = case_type_picker.for_config(config)
    if ct is None:
        raise CaseTypeError(
            "no case type is chosen, so there is nothing to apply. Pick one in "
            "the Mesh panel's Case Type row first.")
    # `plan`, NOT `fit`. The two differ in exactly one way and it is the one
    # that matters here: `fit` CATCHES the ruler's refusal and falls back to the
    # authored numbers, which is right for a read-out comparing fields and wrong
    # for an act that writes them — a case type authored on a 1 m body would put
    # its 0.02 surface size on a 10 mm one, giving a mesh that looks right and is
    # the wrong size. `apply_case_type.py` lets the same refusal through, and
    # `case_type_scale`'s own rule is "A RULER THAT CANNOT BE READ REFUSES".
    #
    # The first cut called BOTH, and `fit`'s reason was dead on arrival: it is
    # non-empty only when it catches what the line above had already let escape.
    # It also doubled the per-keystroke cost, `fit` re-running `plan` internally.
    application = case_type_scale.plan(ct, config)
    ctx = topology_binding.context_for_config(config)
    roles = case_type_roles.plan_for(ct, config, ctx)
    wanted = set(roles.roles)
    stored = dict(getattr(config, "case_type_roles", None) or {})
    assigned = {r: v for r, v in stored.items() if r in wanted}
    ignored = tuple(sorted(r for r in stored if r not in wanted))
    return ApplyPlan(ct, application, roles, assigned, ignored)


def apply(plan_, config, confirmed=None) -> Applied:
    """Apply `plan_` to a COPY of `config`; return it, or refuse naming everything.

    `confirmed` maps a physical parameter to the value the operator actually
    wants — the offered one to accept it, their own to correct it, which is
    `--confirm NAME[=VALUE]`'s grammar and `Application.apply`'s contract.

    Three refusals, and the first two arrive TOGETHER (see the module docstring):
    an unconfirmed role or an unresolvable segment, and an unconfirmed physical
    parameter. The third is :class:`PreflightRefused`, which can only be reached
    once the bindings exist.
    """
    parts = []
    waiting = plan_.unconfirmed_roles()
    if waiting:
        parts.append(
            "%d role(s) must be confirmed before anything is applied, because a "
            "wrong guess reaching the mesher is a mesh with the far field's "
            "conditions on the body:\n%s"
            % (len(waiting), "\n".join("  - " + g.describe() for g in waiting)))
    problems = plan_.problems()
    if problems:
        parts.append("this case type cannot be bound to this drawing:\n"
                     + "\n".join("  - " + p for p in problems))
    missing = plan_.application.unconfirmed(confirmed)
    if missing:
        parts.append(
            "%d physical parameter(s) must be confirmed, because they are set "
            "by physics rather than by the size of the body:\n%s"
            % (len(missing), "\n".join("  - " + c.describe() for c in missing)))
    if parts:
        raise CaseTypeError("\n".join(parts))

    # A DEEP COPY, so a pre-flight refusal below leaves the operator's own
    # configuration exactly as it was. `case_type_fields.apply` writes in place
    # and `RolePlan.bind` mutates `config.topology`, so there is no version of
    # this that touches the live object and is still all-or-nothing.
    fitted = copy.deepcopy(config)
    changes = plan_.changes(config, confirmed)
    plan_.application.apply(fitted, confirmed)
    # The bindings are derived against the OPERATOR's own segments, from the
    # context `plan` built on their configuration — the copy carries the same
    # geometry list, so the two cannot disagree, and no id from the authoring
    # drawing is read because a case type carries none.
    bindings = plan_.roles.bind(fitted, plan_.assigned)
    refusals = topology_model.preflight_for_config(fitted)
    if refusals:
        # The family's own words, and its own rows: the sentence is
        # `refusal_text`'s verbatim (`mesh_fallback` takes it the same way) and
        # the rows ride along so a window can point at the curve.
        raise PreflightRefused(topology_preflight.refusal_text(refusals),
                               refusals)
    logger.debug("applied case type %r: %d field(s), %d binding(s)",
                 plan_.case_type.name, len(changes), len(bindings))
    return Applied(fitted, bindings, changes)
