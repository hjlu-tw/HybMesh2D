"""The PRE-SELECTED role: what the tool offers, and why it may offer it. Qt-free.

The eighth file of the case-type seam and the second half of #164 (parent
#158). `case_type_roles.py` next door is the whole of what a role DOES — which
roles a family needs, how an assignment resolves against the operator's own
segments, and the refusals. This is the part that offers one before they are
asked, and the cut is the ~500-line standard rather than a second home for the
knowledge: `RolePlan` holds the guesses and is the only thing that ever acts on
one, which is why the confirmation lives there and not here.

**A GUESS IS AN OFFER, NEVER A DEFAULT.** Nothing here is used until
`RolePlan.bind` is given a confirmation for it. The two are deliberately
separated that way: a module that could both guess and apply its own guess
would make "the operator confirms" a convention rather than a mechanism, and a
wrong guess reaching the mesher silently is a mesh that generates, exports and
looks right while carrying the far field's conditions on the body.

**IT RANKS BY ENCLOSED AREA AND NEVER BY DRAWING ORDER.** Drawing-order
conventions are excluded by decision in #158, and this repo has a
USER-REPORTED defect in which drawing order rather than click order decided a
result. The body is inside the seam is inside the far field however the curves
were drawn, so the ranking is a geometric fact about the drawing.

**AND IT REFUSES TO RANK RATHER THAN RANK BADLY.** With more candidate
outlines than slots there is no unambiguous ordering, and the one offered
anyway is precisely the wrong guess the confirmation exists against — so the
RANKING is abandoned whole. **What survives that is the EVIDENCE**: a role the
drawing itself already records (`geom_roles`) is still offered, because it was
never a ranking and a count the ranking cannot use says nothing about it. The
distinction is stated this precisely because the first draft of this paragraph
said "nothing is guessed when the counts do not line up", which the code does
not do and `guess_roles` was never written to do; the offer is confirmed either
way, so what was wrong was the sentence and not the behaviour.

Nothing is offered for an OPTIONAL slot either: a list the family documents as
generated is not a question, and guessing one would block a run for a curve the
operator never asked to bind.
"""
from __future__ import annotations

from app.services.logging_setup import get_logger
from app.services.topology_ogrid_binding import format_binding

logger = get_logger(__name__)

#: How a guess ranks candidate outlines, smallest enclosed area first. The body
#: is inside the seam is inside the far field, whatever order they were drawn
#: in — which is the whole reason the ranking is geometric and not positional.
RANK = {"body": 0, "seam": 1, "farfield": 2}

#: Roles a geometry may bear in `MeshConfig.geom_roles` that mean "this is the
#: outer boundary". Both are the outer-domain outline — `farfield` for external
#: flow, `wall` for internal — and a drawing that already says so is better
#: evidence than any ranking.
OUTER_ROLES = ("farfield", "wall")

#: Roles a geometry may bear that make it NOT an outline a topology binds: a
#: refinement seed is a point cloud and a no-BL obstacle is an island inside the
#: domain. Excluded from the candidate pool rather than ranked with the rest,
#: which would shift every slot by one on a drawing carrying a seed.
NON_OUTLINE_ROLES = ("seed", "nobl")


class Guess:
    """One role the tool pre-selected, and why. Confirmed before it is used."""

    __slots__ = ("role", "geom", "segs", "why")

    def __init__(self, role: str, geom: str, segs, why: str):
        self.role = role
        self.geom = geom
        self.segs = tuple(int(s) for s in segs)
        self.why = why

    def describe(self) -> str:
        return ("%s -> '%s' segment(s) %s — %s. Confirm it before it is used."
                % (self.role, self.geom, format_binding(self.segs) or "(none)",
                   self.why))

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "Guess(role=%r, geom=%r)" % (self.role, self.geom)


def _role_word(config, path: str) -> str:
    """The `geom_roles` word `path` bears, `"body"` when it records none."""
    if config is None:
        return "body"
    try:
        return str((config.role_of(path) or {}).get("role") or "body")
    except AttributeError:
        return "body"


def guess_roles(slots, ctx, config=None) -> dict:
    """`role -> Guess` for the roles this drawing lets us pre-select.

    TWO SOURCES, in this order, and neither is the drawing ORDER:

      1. a geometry the drawing ALREADY calls the outer boundary
         (`MeshConfig.geom_roles`, `farfield` or `wall`) takes the far-field
         slot when exactly one does — the operator has said it in another
         panel, and a ranking that ignored them would be guessing against
         evidence;
      2. the rest are ranked by ENCLOSED AREA and matched to the remaining
         slots smallest-first, because the body is inside the seam is inside
         the far field however they were drawn.

    THE RANKING IS ABANDONED WHOLE WHEN THE COUNTS DO NOT LINE UP. A drawing
    with three closed outlines and an O-grid's two slots has no unambiguous
    ordering, and a guess made anyway is the wrong guess reaching the mesher
    that this whole confirmation exists against. A role found by EVIDENCE in
    step 1 survives that, because it was not ranked — the drawing says so
    itself, and it is offered for confirmation like any other.
    Guesses are emitted only for REQUIRED slots:
    an optional list left unbound is a family doing what it documents, while an
    optional list guessed and unconfirmed would block a run for a curve the
    operator never asked to bind.
    """
    if ctx is None or not slots:
        return {}
    pool = [g for g in ctx.geoms
            if g.spans and g.closed
            and _role_word(config, g.path) not in NON_OUTLINE_ROLES]
    by_role = {s.role: s for s in slots}
    out = {}
    if "farfield" in by_role:
        outer = [g for g in pool if _role_word(config, g.path) in OUTER_ROLES]
        if len(outer) == 1:
            g = outer[0]
            out["farfield"] = Guess(
                "farfield", g.spelling, g.seg_ids,
                "it is the only geometry this drawing already gives the "
                "far-field role")
            pool = [p for p in pool if p is not g]
    rest = sorted((s for s in slots if s.role not in out),
                  key=lambda s: RANK.get(s.role, len(RANK)))
    if len(pool) != len(rest):
        if pool and rest:
            logger.debug("no role guessed: %d candidate outline(s) for %d "
                         "slot(s)", len(pool), len(rest))
        return {r: g for r, g in out.items() if by_role[r].required}
    ranked = sorted(pool, key=lambda g: g.equivalent_radius())
    words = {0: "the smallest", 1: "the middle", 2: "the largest"}
    for slot, g in zip(rest, ranked):
        # "the smallest of the 1 closed outlines" is what the general wording
        # degrades to once step 1 has taken one out of the pool, and a reason
        # that reads as a mistake is a reason nobody weighs.
        why = ("the only closed outline left to rank in this drawing"
               if len(ranked) == 1 else
               "%s of the %d closed outlines left to rank in this drawing"
               % (words.get(RANK.get(slot.role, 0), "one"), len(ranked)))
        out[slot.role] = Guess(slot.role, g.spelling, g.seg_ids, why)
    return {r: g for r, g in out.items() if by_role[r].required}
