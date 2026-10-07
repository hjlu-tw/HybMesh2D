"""What a SET of reference meshes says, and whether a document follows from it.

Issue #168, parent #158. #161 gave a case type ONE reference mesh and derived
every bound from it. That is a thin basis: it has an opinion about what that one
mesh happened to exercise and none about anything else, so sooner or later a
verdict judges wrong — a mesh called usable that was not, or the reverse. The
correction is to ADD the offending mesh and let the thresholds move, never to
edit the number: hand-editing would work and would throw away the one thing the
measurement bought, a threshold whose origin is still visible six months later
(ADR-0002's first consequence, user stories 38 and 39).

**THIS IS THE THIRD CUT THROUGH ONE ARTEFACT, AND IT IS THE ~500-LINE STANDARD
AGAIN.** `case_type.py` is the document, `case_type_reference.py` the figures and
the provenance it holds, and what is here needs BOTH halves together — a
`Threshold`'s factor and a `ReferenceMesh`'s figure — so it could live in either
and fits in neither. The dependency still runs one way: document -> evidence ->
figures. A THRESHOLD is declared in `case_type.py` and nowhere else; what is
declared here is the ARITHMETIC that turns a set of meshes into one bound, and
the invariant that says a document really obeys it.

**THE DERIVATION.** For one figure key:

* `base` is the WORST figure any exemplar published. Every exemplar must stay
  accepted, so no bound may sit below it.
* `cap` is the BEST figure any counter-example published. Every counter-example
  must be rejected, so the `unusable` bound must sit strictly below it.
* A bound is `base * factor`, held down to the SEPARATING BOUND
  `sqrt(base * cap)` when a counter-example would otherwise sit under it. The
  geometric midpoint is strictly between the two, so it accepts every exemplar
  and rejects every counter-example — and it is a BAND rather than a knife edge
  against either, which is the same reason #161 multiplies by a factor at all.
  Pulling the bound to just under `cap` would reject the counter-example by a
  hair and pretend to know where the boundary is.

**A KEY THAT SEPARATES NOTHING PLACES NO BOUND.** When `cap <= base` the two
meshes are indistinguishable on that figure — the bad mesh is no worse there
than the good one — and asking a bound to accept one and reject the other is
asking for a number that does not exist. That is not a contradiction in the case
type: a C-grid whose `max` is 96x the O-grid's is correctly rejected on `max`
while its `bulk.median` says nothing. The contradiction is only when NO key
separates them, and it is caught where it is visible: `check_standing` asks
whether every exemplar is in fact accepted and every counter-example in fact
rejected, through the same `exceeds` the verdict uses.

**A HAND-SET BOUND IS NEVER RECOMPUTED** (acceptance criterion 5). `Evidence`
derives only what carries a tolerance factor, and `add_reference` leaves the rest
exactly as the maintainer typed it. Where that override is what makes the case
type unable to honour a new reference mesh, the ADDITION is refused and the
override is NAMED as the obstacle — which is the only way both rules hold at
once: silently recomputing breaks criterion 5, and silently accepting would
leave the maintainer with a counter-example the thresholds do not reject.
"""
from __future__ import annotations

import math

from app.services.case_type_reference import BOUNDS
from app.services.case_type_reference import COUNTER
from app.services.case_type_reference import CaseTypeError
from app.services.case_type_reference import EXEMPLAR
from app.services.case_type_reference import MANUAL
from app.services.case_type_reference import exceeds


class Evidence:
    """Everything a case type's reference meshes say about ONE figure key.

    Built by :meth:`over`, which is the only way the three parts can be kept in
    step: the ids a threshold rests on are exactly the meshes that published the
    figure, `base` is the worst exemplar among them and `cap` the best
    counter-example. A caller that assembled those separately could record a
    support that does not match the numbers derived from it.
    """

    __slots__ = ("key", "base", "cap", "idents")

    def __init__(self, key: str, base=None, cap=None, idents=()):
        self.key = key
        #: The WORST figure any exemplar published for `key`, or ``None`` when
        #: no exemplar measured it. A bound may never sit below this.
        self.base = base
        #: The BEST figure published by a counter-example this figure can tell
        #: apart from the exemplars, or ``None``. The `unusable` bound must sit
        #: strictly below it. A counter-example at or below `base` is NOT in
        #: here — see :meth:`over`.
        self.cap = cap
        #: Every reference that published `key`, in the case type's own order
        #: and of BOTH kinds — what the threshold rests on, which is the
        #: question user story 39 asks. A counter-example that places no bound
        #: on this figure is still in the list: the case type must go on
        #: rejecting it somewhere, and a support that shifted as other meshes
        #: were added would be a worse record than one that is merely wide.
        self.idents = tuple(idents)

    @classmethod
    def over(cls, references, key: str) -> "Evidence":
        base = None
        counters = []
        idents = []
        for ref in references:
            value = ref.figure(key)
            if value is None:
                continue
            idents.append(ref.ident)
            if ref.kind == COUNTER:
                counters.append(value)
            else:
                base = value if base is None else max(base, value)
        # `cap` is the best of the counter-examples THIS FIGURE CAN TELL APART
        # from the exemplars, not the best of all of them. A counter-example
        # sitting at or below `base` says nothing here — the bad mesh is no
        # worse on this figure than the good one — and taking the plain minimum
        # would let it ERASE the hold-down a genuinely separating
        # counter-example placed, widening the bound instead of tightening it.
        # Found by review, by adding a mesh that separates on `bulk.p95` and
        # not on `median`: `median`'s unusable bound jumped from 2.9866 back to
        # 5.53793, discarding the C-grid's restraint without a word.
        separating = ([c for c in counters if base is not None and c > base])
        cap = min(separating) if separating else None
        return cls(key, base=base, cap=cap, idents=idents)

    @property
    def separates(self) -> bool:
        """Can this figure tell the exemplars from the counter-examples?

        False when either side published nothing, when no counter-example is
        worse here than the worst exemplar (`over` has already dropped those
        from `cap`), and — the arithmetic edge — when the two are so close that
        the separating bound does not round to a value strictly between them.
        All three mean the same thing to a caller: this figure places no bound
        derived from a counter-example.
        """
        if self.base is None or self.cap is None or self.cap <= self.base:
            return False
        middle = math.sqrt(self.base * self.cap)
        return self.base < middle < self.cap

    @property
    def limit(self):
        """The SEPARATING BOUND, or ``None`` when this figure separates nothing."""
        if not self.separates:
            return None
        return math.sqrt(self.base * self.cap)

    def bound(self, factor: float) -> float:
        """`base * factor`, held down to the separating bound.

        Raises when no exemplar published the figure: a measured bound with no
        measurement under it is the one thing a tolerance factor cannot produce.
        """
        if self.base is None:
            raise CaseTypeError(
                "no exemplar published %s, so no bound can be derived from it"
                % self.key)
        want = self.base * float(factor)
        limit = self.limit
        return want if limit is None or want <= limit else limit

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("Evidence(key=%r, base=%r, cap=%r, idents=%r)"
                % (self.key, self.base, self.cap, self.idents))


def support(references, thresholds) -> dict:
    """`Evidence` per threshold key. One walk, so two readers cannot disagree."""
    return {th.key: Evidence.over(references, th.key) for th in thresholds}


def check_derivations(name: str, references, thresholds) -> None:
    """Every measured bound really IS what the evidence derives. Raises or not.

    The one invariant that makes "derived, not typed" a fact about the FILE
    rather than a claim about how it was produced, and #168 is where it stopped
    being a multiplication: a bound now follows from a SET of meshes, and the
    file states the set beside the factor so the derivation is still re-checkable
    off disk by anyone holding the document.
    """
    declared = {}
    for ref in references:
        if ref.ident in declared:
            raise CaseTypeError(
                "case type %r declares two reference meshes called %r; a "
                "threshold naming it could not say which" % (name, ref.ident))
        declared[ref.ident] = ref
    evidence = support(references, thresholds)
    for th in thresholds:
        origin = th.measured_from
        if origin is None:
            continue
        seen = evidence[th.key]
        named = tuple(origin.references)
        if named != seen.idents:
            # ONE comparison, three ways a support can be wrong, and the
            # message says which. Written as one check rather than three
            # because any two of them would cover the third between them: an
            # earlier draft refused an undeclared reference in its own loop,
            # and removing that loop reddened nothing, since this comparison
            # caught the same document a line later.
            undeclared = [i for i in named if i not in declared]
            silent = [i for i in named
                      if i in declared and i not in seen.idents]
            unnamed = [i for i in seen.idents if i not in named]
            why = []
            if undeclared:
                why.append("%s, which this case type does not declare — "
                           "provenance pointing at nothing is not provenance"
                           % ", ".join(undeclared))
            if silent:
                why.append("%s, which published no %s — a figure a mesh could "
                           "not measure cannot have a bound derived from it"
                           % (", ".join(silent), th.key))
            if unnamed:
                why.append("and not %s, which published %s. The support is the "
                           "set that bears on the figure, not a subset "
                           "somebody chose" % (", ".join(unnamed), th.key))
            raise CaseTypeError(
                "threshold %r says it rests on %s: %s"
                % (th.key, ", ".join(named) or "(nothing)", "; ".join(why)))
        for bound in BOUNDS:
            factor = origin.factor_for(bound)
            if factor is None:
                continue
            want = seen.bound(factor)
            stated = getattr(th, bound)
            if abs(stated - want) > origin.REL_TOL * max(abs(want), 1.0):
                raise CaseTypeError(
                    "threshold %r states a %s bound of %r, but its reference "
                    "meshes derive %r (worst exemplar %r x the %s_factor %r%s). "
                    "A bound that is not its own derivation is a hand-set one: "
                    "drop the factor and it reads as the override it is"
                    % (th.key, bound, stated, want, seen.base, bound, factor,
                       "" if seen.limit is None
                       else ", held down to the separating bound %r" % seen.limit))


#: What a bound the maintainer TYPED is called wherever a refusal names one.
#: ONE spelling, because three refusals quote it — an exemplar a hand-set bound
#: rejects, a counter-example one accepts, and `case_type_author._rederived`'s
#: band collision — and the word is the maintainer's only cue that the remedy is
#: theirs rather than the tool's.
HAND_SET = "HAND-SET"
HAND_SET_NOTE = ("; that bound is %s, so nothing here will recompute it — drop "
                 "that override, or leave this mesh out" % HAND_SET)


def hand_set_mark(threshold, bound: str) -> str:
    """`" (HAND-SET)"` when the maintainer typed that bound, else `""`."""
    return (" (%s)" % HAND_SET
            if threshold.origin_of(bound) == MANUAL else "")


def _bound_text(threshold, bound: str) -> str:
    """One bound as a refusal quotes it: the number, or that there is none.

    Pulled out of the sentence below rather than inlined: three conditionals
    nested inside a `join` inside a `%` is one re-read too many for the message
    a maintainer gets when their correction is refused.
    """
    value = getattr(threshold, bound)
    if value is None:
        return "none"
    return "%.6g%s" % (value, hand_set_mark(threshold, bound))


def standing_failures(references, thresholds) -> list:
    """Every reference mesh the thresholds do not treat as its kind says.

    Returns one sentence per failure rather than raising, because the two
    callers want it two ways: `check_standing` refuses a document with it, and
    `case_type_author.add_reference` refuses an ADDITION with it and has to say
    which mesh and which figure made the case type self-contradictory.

    An exemplar fails when any bound rejects it — it is a mesh the maintainer
    judged good, so a case type that will not pass its own evidence is
    incoherent. A counter-example fails when NO `unusable` bound rejects it: one
    figure is enough, because a figure on which the two kinds are
    indistinguishable is a figure that was never going to separate them.
    """
    by_key = {th.key: th for th in thresholds}
    out = []
    for ref in references:
        if ref.kind == EXEMPLAR:
            for key, th in by_key.items():
                value = ref.figure(key)
                for bound in BOUNDS:
                    if exceeds(value, getattr(th, bound)):
                        out.append(
                            "exemplar %r published %s %.6g, which its own case "
                            "type's %s bound of %.6g rejects — a case type "
                            "cannot refuse the mesh it was measured from%s"
                            % (ref.ident, key, value, bound,
                               getattr(th, bound),
                               HAND_SET_NOTE
                               if th.origin_of(bound) == MANUAL else ""))
            continue
        bounded = [key for key in by_key if ref.figure(key) is not None]
        if not bounded:
            out.append(
                "counter-example %r publishes no figure any threshold bounds, "
                "so no threshold can reject it" % ref.ident)
            continue
        if any(exceeds(ref.figure(key), by_key[key].unusable)
               for key in bounded):
            continue
        out.append(
            "counter-example %r is not rejected by any threshold: %s. No figure "
            "separates it from the exemplars, so the case type is being asked "
            "to both accept and reject the same figures"
            % (ref.ident, "; ".join(
                "%s %.6g against an unusable bound of %s"
                % (key, ref.figure(key), _bound_text(by_key[key], "unusable"))
                for key in sorted(bounded))))
    return out


def check_standing(name: str, references, thresholds) -> None:
    """Raise when a document does not treat its own reference meshes as it claims.

    This is what gives a COUNTER-EXAMPLE teeth in the FILE rather than only in
    the step that added it: a document hand-edited until it accepts a mesh it
    declares it must reject is refused on load, naming the conflict.
    """
    failures = standing_failures(references, thresholds)
    if failures:
        raise CaseTypeError("case type %r contradicts its own evidence: %s"
                            % (name, "; ".join(failures)))
