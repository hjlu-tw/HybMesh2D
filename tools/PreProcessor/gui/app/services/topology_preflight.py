"""WHAT A FAMILY SAYS BEFORE ANYTHING RUNS, and the curve it says it about (#165).

Qt-free, and gated as such by ``tests/test_qt_free_seam.py``'s ``services/`` sweep:
a refusal is a fact about a drawing, so the GUI, the headless pipeline, the
case-type host and the gate all reach the same one.

**A PRE-FLIGHT REFUSAL IS NOT AN EXIT CODE.** ``EXIT_ERR_TOPOLOGY`` (8) fires
after the operator has committed — they picked a case type, assigned roles,
pressed Generate and waited — and its message is written for a developer:
measured on a body poking out of its far field, the mesher says *block 'q0': its
corners 'b0', 'f0', 'f1', 'b1' wind clockwise (signed area -0.403553), so every
cell in it would be inverted. Reverse its south edge's own corner pair.* Every
noun in that sentence is an id of a document the operator never opened. What
they can act on is "the body you drew reaches (2, 0.1), which is outside the far
field" — and which curve that is.

**SO A REFUSAL CARRIES THE CURVE, NOT ONLY THE SENTENCE.** :class:`Refusal` holds
the geometry spelling and, where the family knows it, the segments and the point
— so a host can point at it rather than re-parse prose. That is the same rule
:class:`~app.services.topology_binding.BrokenBinding` already follows for a
binding the panel repairs, and it is why this is a dataclass and not a string.

**EVERY FAMILY ANSWERS FOR ITSELF, and the registry is where that is enforced.**
``Family.preflight`` has NO DEFAULT (``topology_model``), so a fifth family that
declares no refusal does not construct. Their preconditions genuinely differ —
the O-grid needs a closed loop, the C-grid a sharp trailing edge, the H-grid a
rectangle with four distinct corners — and a shared rule table could hold only
what all four agree on, which is nearly nothing. What IS shared is here: the
four questions every bound outline answers (``outline_problem``'s, re-used and
never re-spelled) and the containment test below.

**WHAT CONTAINMENT IS FOR, MEASURED.** The O-grid and the two-ring family nest
their outlines by EQUIVALENT RADIUS — one number for a whole loop, area-derived.
That is the right ruler for the radial law and the wrong one for "is this inside
that": a 4.0 x 0.2 body has an equivalent radius of 0.505 and a unit circle
0.9999, so a body reaching x = +-2 passed every check this repo had and the
mesher answered with the sentence quoted above (exit 8, nothing exported). The
C-grid already walked the section's own points against its far field for exactly
this reason (#149); :func:`outside_point` and :func:`drawn_ring` MOVED here from
``topology_cgrid_section`` so the other two families use that walk rather than a
second copy of it, and the C-grid still imports them under the names it had.

**GridPro's "Causes of Bad Grids" IS THE SOURCE MATERIAL, AND ONE OF ITS FOUR
CLASSES IS ACTUALLY CHECKED HERE.** Said plainly because the first draft of this
docstring claimed two and a review axis read it against the code:

* *topology cutting a surface on the concave side* — the containment walk is the
  reachable half of it. An outline that leaves the one around it has nowhere for
  its ring to go, which is that failure at its coarsest; a body that stays inside
  while turning hard enough for neighbouring radials to cross before they arrive
  is NOT detected, and is the next thing to build here.
* *face mismatch* — CANNOT ARISE on this path, which is a different statement
  from "is checked". A family emits one edge named by both blocks and welds by
  id (`.claude/rules/mesher-multiblock.md`), so there is no second declaration to
  mismatch. Nothing here looks for it because nothing can produce it.
* *singular edges on surfaces* and *the singularity-count rule* — NOT checked,
  and not dismissed as positional either, which is what the first draft did.
  They are structural facts about a declared topology; what is missing is a
  counter over the document the family produces, which no family computes today.

Positional forgiveness is not available to us either way (ADR-0001: positions are
computed, not relaxed), so a refusal is the only move for any of them.

NOT a second reading of ``build``'s refusal, and not a replacement for it. A
family's ``plan`` stops at the first problem because it answers "can this run?";
this lists what the operator has to fix and names the curve for each, the way
``topology_model.broken_bindings`` lists every broken binding rather than the
first.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, replace

from app.services.topology_binding import outline_problem

__all__ = ["Refusal", "outline_refusal", "enclosure_refusal", "nesting_refusal",
           "no_context_refusal", "plan_refusal", "drawn_ring", "outside_point",
           "refusal_text", "refusal_points", "stamp_family"]


@dataclass(frozen=True)
class Refusal:
    """One reason a family cannot work with the geometry it has been handed.

    ``what`` is the sentence in the OPERATOR's terms — it names the curve by the
    spelling they see in the geometry list, never by a document id and never by
    an exit code. ``fix`` is the action, kept apart so a host may show it on its
    own line without splitting prose.

    ``geom`` and ``at`` are what a host POINTS at: the geometry spelling and a
    single coordinate worth marking. Both are optional because one family's
    refusals are about no curve at all — the H-grid declares its own corners and
    binds to nothing — and saying so by leaving them empty is better than
    inventing a curve for it.

    THERE IS NO PER-SEGMENT FIELD, and the first cut had one. Nothing ever set
    it: every refusal here is about a whole curve, because WHICH segment is
    wrong is the question `topology_binding.BrokenBinding` already answers for
    the panel that repairs one. A field no caller fills is an untested branch in
    `refusal_points` and a promise in the rule file, so it was deleted rather
    than left for a fifth family to discover empty.

    ``family`` is filled in by the registry dispatch (:func:`stamp_family`), not
    by the family itself: a function that had to name itself could name another.
    """

    what: str
    fix: str = ""
    geom: str = ""
    at: tuple[float, float] | None = None
    family: str = ""

    def curve(self) -> str:
        """The offending curve as a SHORT label — its basename, never its path.

        Not "what the operator sees in the geometry list", which this once
        claimed and is not true: that list holds `cfg.geom_files` verbatim, so a
        geometry browsed from outside the repo is an absolute path there and in
        the families' own sentences. What this is for is a label a host can put
        in front of one — and the long form stays inside the sentence, which is
        `topology_binding.outline_problem`'s wording and three families' own
        rather than this ticket's to change.
        """
        return os.path.basename(self.geom) if self.geom else ""

    def text(self) -> str:
        """The whole refusal as one sentence, the curve named in it.

        The prefix is CONDITIONAL, and that is not cosmetic: most of these
        sentences already name the curve — they were written by the families
        that own them, for users — and an unconditional prefix printed the
        geometry twice in one line. So it is added only where the sentence does
        not carry the name.

        THE NEEDLE IS THE BASENAME, AND IT HAS TO BE. The sentences name the
        curve in BOTH forms — `outline_problem` embeds ``g.spelling`` (which may
        be an absolute path) while `enclosure_refusal` embeds the basename — and
        the basename is a substring of both, so it is the one needle that finds
        either. Spelling-as-needle was tried and reverted in review: it suppresses
        nothing for the second shape and prints *'body.dat': the body you drew as
        'body.dat' reaches…*, which is the duplication this rule exists to stop.

        The family's name is NOT in it. The operator picked a case type, not a
        family; `ogrid` is an internal identifier and this ticket rules one out
        of the refusal text. It stays on the dataclass because a gate and a log
        line may want it.
        """
        named = self.curve()
        where = f"'{named}': " if named and named not in self.what else ""
        tail = f" {self.fix}" if self.fix else ""
        return f"{where}{self.what}{tail}"


def stamp_family(name: str, refusals) -> tuple:
    """``refusals`` with ``family`` set to ``name`` — the dispatch's own stamp."""
    return tuple(replace(r, family=str(name or "")) for r in refusals)


def refusal_text(refusals) -> str:
    """Every refusal as the one message a host logs or raises, or ``""``.

    EVERY one, never the first, for the reason ``case_type_roles.RolePlan``
    reports every problem: repairing a drawing one refusal at a time is a
    generate, a refusal and a return per wrong curve.
    """
    rows = list(refusals or ())
    if not rows:
        return ""
    head = ("this case cannot be meshed as it is drawn:" if len(rows) > 1
            else "this case cannot be meshed as it is drawn —")
    if len(rows) == 1:
        return f"{head} {rows[0].text()}"
    return head + "\n" + "\n".join("  - " + r.text() for r in rows)


def refusal_points(ctx, refusal) -> list:
    """The polyline a host draws over the offending curve, or ``[]``.

    Rows of ``nan`` separate disjoint runs, which is the contract the mesh
    canvas's ``highlight_segment`` already reads — so pointing at a refusal is
    the same call that points at a per-segment boundary condition, and this
    function stays Qt-free by returning the points rather than drawing them.

    THE WHOLE CURVE, always: a refusal here is about a geometry (not a closed
    loop, not inside its far field), never about one segment of it — which is
    `BrokenBinding`'s question and the repair panel's.
    """
    if ctx is None or refusal is None or not refusal.geom:
        return []
    g = ctx.geometry(refusal.geom)
    if g is None or not g.spans:
        return []
    out: list = []
    for sid in g.seg_ids:
        if out:
            out.append((math.nan, math.nan))
        out += [(float(x), float(y)) for x, y in g.spans[sid].points]
    return out


# ── the checks the families share ───────────────────────────────────────────

def no_context_refusal(noun: str, curves: str) -> tuple:
    """A binding family asked about a drawing nobody read.

    Written here rather than three times because all three binding families
    reach it and it is one sentence: what differs is the NOUN the family binds
    (the O-grid's geometry, the C-grid's section) and WHICH curves the operator
    is being asked to add. That is this module's own rule — what is shared lives
    here and what is the family's own stays with it — applied to the shape a
    review found copied verbatim.
    """
    return (Refusal(
        f"this family binds to the {noun} you drew, so it needs the mesh's "
        f"geometry list; none was supplied.",
        fix=f"Add {curves} in Geometry Layers."),)


def plan_refusal(problem: str) -> tuple:
    """A family's own ``plan`` problem as a refusal, with NO curve attached.

    The fall-through every binding family ends with, so the reason for the
    missing curve is stated ONCE rather than in three comments free to disagree:
    ``plan`` reports one sentence and not which of its two or three outlines it
    blames, and attributing it would point the canvas at the wrong one. Its own
    sentences name the geometry where they are about it.
    """
    return (Refusal(problem),) if problem else ()


def outline_refusal(ctx, role: str, name, g, what: str = "shape",
                    closed_note: str = "") -> Refusal | None:
    """The four questions every bound outline answers, as a refusal naming it.

    The cascade itself is :func:`~app.services.topology_binding.outline_problem`
    and is NOT re-spelled here — #155's review found a third hand-written copy
    that had silently dropped the one clause a user can act on. What this adds
    is the CURVE: the same sentence, plus which geometry on the canvas it is
    about, so the host can point at it.
    """
    why = outline_problem(ctx, role, name, g, what=what, closed_note=closed_note)
    if not why:
        return None
    return Refusal(why, geom=(g.spelling if g is not None else str(name or "")))


def drawn_ring(g) -> list:
    """A drawn outline's own polyline, as the polygon :func:`outside_point` tests.

    Its POLYLINES rather than the chords between its joints, which is the whole
    difference between a drawn far field and a generated one: a drawn D curves
    OUTWARD between its joints, so a chord ring would refuse a body that sits
    comfortably inside the shape the user actually drew. A generated hexagon has
    no such gap — its sides ARE the chords — which is why
    ``topology_cgrid_section.generated_ring`` is the corners.
    """
    return [pt for sid in g.seg_ids for pt in g.spans[sid].points[:-1]]


def outside_point(ring, g):
    """The first point of ``g`` the outline ``ring`` does not contain, or ``None``.

    THE INNER CURVE HAS TO BE INSIDE THE OUTER ONE, and it is checked by walking
    the inner one's own points rather than by a rule of thumb about radii: a
    radius that is generous for a thin aerofoil at zero incidence is not for a
    thick one at 15 degrees, and a body poking through its far field produces
    blocks that fold rather than a refusal the user can read.

    ``ring`` is a closed polygon as a list of points, so the same containment
    test serves the C-grid's generated hexagon, its drawn D and the O-grid's
    far field — the three differ in what the ring IS, not in how it is tested.
    """
    ring = list(ring)
    # NO short-ring guard. One that returned None would report a degenerate
    # outline as CONTAINING the inner curve, which is the one direction this
    # check must not fail in; with none, a ring of fewer than three points
    # contains nothing and the caller refuses.
    for sp in g.spans.values():
        for pt in sp.points:
            x, y = pt
            hit = False
            for k in range(len(ring)):
                x0, y0 = ring[k]
                x1, y1 = ring[(k + 1) % len(ring)]
                if (y0 > y) != (y1 > y):
                    if x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                        hit = not hit
            if not hit:
                return pt
    return None


def enclosure_refusal(inner, outer, inner_role: str,
                      outer_role: str) -> Refusal | None:
    """``inner`` must lie inside ``outer``, point by point — or the ring folds.

    The refusal names the point that is outside, because "your body is too big"
    is not actionable on a shape with one spur and "it reaches (2, 0.1)" is.
    """
    if inner is None or outer is None or not inner.spans or not outer.spans:
        return None
    out = outside_point(drawn_ring(outer), inner)
    if out is None:
        return None
    return Refusal(
        f"the {inner_role} you drew as '{os.path.basename(inner.spelling)}' "
        f"reaches ({out[0]:.4g}, {out[1]:.4g}), which is outside the "
        f"{outer_role} '{os.path.basename(outer.spelling)}'. There is no ring "
        f"between them there, so the blocks that should fill it would fold "
        f"inside out.",
        fix=f"Draw the {outer_role} out past the {inner_role}, or scale the "
            f"{inner_role} down.",
        geom=inner.spelling, at=(float(out[0]), float(out[1])))


def nesting_refusal(outlines) -> tuple:
    """Every neighbouring pair of ``[(role, GeomBinding), ...]`` that does not nest.

    Given innermost first, so the body is inside the seam is inside the far
    field. EVERY pair, not the first: a drawing whose seam is outside the far
    field AND whose body is outside the seam costs two edits, not two runs.
    """
    rows = [(role, g) for role, g in outlines if g is not None]
    out = []
    for (ir, ig), (orole, og) in zip(rows, rows[1:]):
        r = enclosure_refusal(ig, og, ir, orole)
        if r is not None:
            out.append(r)
    return tuple(out)
