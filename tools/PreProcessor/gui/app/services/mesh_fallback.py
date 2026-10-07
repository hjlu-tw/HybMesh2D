"""THE HYBRID FALLBACK: a shape no family covers is a downgrade, not a dead end.

Issue #167, parent #158. Qt-free, and gated as such by
``tests/test_qt_free_seam.py``'s ``services/`` sweep: whether a fallback is
available, what the operator is asked, what the run is then handed and what the
committed case records are facts about a configuration, so the GUI, the gate and
any later host reach the same ones.

#165 gave every family a PRE-FLIGHT REFUSAL in the operator's terms. That closed
one hole and opened another: an operator whose drawing no family can fill was
left with a sentence and nothing to press. This module is the other half — the
tool offers to mesh it on the HYBRID path instead (boundary-layer quads grown off
the curves, Gmsh triangles filling the far field), which will mesh nearly
anything.

**THE TRIGGER IS THE FAMILY IN FORCE REFUSING, NOT A SURVEY OF ALL FOUR**, and
the first cut was the survey. It cannot work: the H-GRID BINDS TO NOTHING —
`Family.binds` is False for it and its refusals are about its own parameter rows
("X Max", "Blocks in X"), never about a curve — so it ACCEPTS every drawing ever
handed to it, including one with a body poking through its far field, which it
would then mesh as a bare rectangle of blocks that ignores the body entirely.
A survey would therefore have found "the H-grid would accept this" for every
drawing in the repo, "every family refuses" would never have been true, and the
fallback would never have been offered at all. The other three are no better as
witnesses: a family the operator never configured refuses because its bindings
are empty, which is a fact about the CONFIGURATION and not about the shape, so
counting it as "this family cannot cover your geometry" would be an overclaim
printed to the operator. The operator picked ONE case type, which names ONE
family; that family refusing IS "no family applies" in the world they are in.

**IT IS NEVER SUBSTITUTED SILENTLY, AND THAT IS THE WHOLE RULE.** Someone who
does not know whether their mesh is structured cannot reason about anything
downstream of it — not the verdict, not the solver settings, not a comparison
with a previous run. So the offer is a question the operator answers, and the
acceptance is keyed on the REASON it was given for (:class:`Fallback.reason` is
the refusal text verbatim): a repeated Trial over the same unchanged refusal does
not re-ask, and any change to what the family objects to does. A host with nobody
to ask — `services/pipeline_runner.py`, `run_pipeline.py`, `run_batch.py` — gets
no offer and keeps refusing exactly as it does today, which is this same rule
applied where there is no operator rather than an omission.

**THE FALLBACK CONFIG CLEARS THE FAMILY AS WELL AS THE MODE**, and the second
half is not tidiness. `mesh_config_io.save_config_to_file` PROJECTS a named
family's document on the way to disk whenever `names_a_family()` is true —
asking the MODE nowhere — and a family whose binding no longer resolves raises
`BindingError` from inside that call, so nothing is written. A fallback config
that kept the family would therefore die in the config WRITER, before the mesher
it is downgrading to was ever launched, on precisely the drawings this module
exists for. Clearing it also makes the committed pipeline script honest: it
describes a hybrid run, because that is the run that produced the mesh beside it.

**WHERE A FALLBACK MESH IS LABELLED — the complete list, enumerated rather than
promised.** (1) the question that offers it; (2) the GUI log, on EVERY generation
that runs as one, Trial and Generate alike; (3) the verdict slot, where
:data:`NO_VERDICT` stands in place of a judgement; (4) the committed case's
``<stem>.fallback.json``; (5) the committed ``<stem>.pipeline.json``, which is a
`MESH_MODE 0` script and so reproduces the fallback rather than a structured
mesh. The Mesh Statistics panel is deliberately NOT on that list: it is handed a
mesh and its `.provenance.json` and nothing else, so it cannot tell a fallback
from an ordinary hybrid run — and labelling every hybrid mesh in the tree
"fallback" would be the same lie pointed the other way. Its shape-metric tip
already says the two paths measure different quantities.

**NO VERDICT IS ISSUED, AND THE REASON IS STATED.** A case type's thresholds were
measured on a reference mesh of structured quads; the mesher's own report says in
as many words that the two paths' cell-shape metrics are different quantities and
are not comparable (`quad_midline_ratio` against `tri_edge_ratio` —
`.claude/rules/mesher-quality.md`). Applying them to a fallback mesh would
produce a number-shaped answer about nothing. A FOLD is still refused: that
refusal is `case_type_verdict.commit_refusal`'s and needs no case type behind it
(ADR-0002), so a fallback mesh with inverted cells does not reach the case either.
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass

from app.services.mesh_modes import MESH_MODE_HYBRID, missing_mesh_input
from app.services.topology_params import FAMILY_NONE

__all__ = ["Fallback", "NOT_STRUCTURED", "NO_VERDICT", "OFFER_TITLE",
           "FALLBACK_SCHEMA", "FALLBACK_SCHEMA_VERSION", "accepted",
           "as_hybrid", "fallback_record", "offer_question", "unavailable"]

FALLBACK_SCHEMA = "hybmesh-mesh-fallback"
FALLBACK_SCHEMA_VERSION = 1

#: The title of the question, and of nothing else.
OFFER_TITLE = "No Structured Mesh For This Drawing"

#: THE ONE SENTENCE, written once and quoted everywhere a fallback is shown or
#: recorded. "not structured" is spelled out rather than left to be inferred
#: from "hybrid", which is a word about the generator and not about the mesh.
NOT_STRUCTURED = (
    "This mesh is NOT structured. It was generated on the hybrid path — "
    "boundary-layer quads grown off the curves, with Gmsh triangles filling the "
    "far field — because no structured block topology could be built from this "
    "drawing.")

#: Why a fallback mesh carries no verdict. Stated wherever the verdict would
#: have been, so its absence is never left to be noticed.
NO_VERDICT = (
    "No verdict: a case type's thresholds are measured on a reference mesh of "
    "structured quads, and the two paths measure different quantities "
    "(quad_midline_ratio against tri_edge_ratio), so none of them is applied to "
    "a fallback mesh. Judge this one on the mesher's own figures.")


@dataclass(frozen=True)
class Fallback:
    """One accepted downgrade: why it was offered, and by which family.

    ``reason`` is `topology_preflight.refusal_text`'s output VERBATIM — the
    words the operator read before they accepted — because an acceptance is only
    meaningful against the thing accepted, and a paraphrase stored beside the
    mesh would be a second account of it free to disagree.

    ``family`` is the registry key of the family that refused. It is NOT in any
    sentence the operator reads: #165 rules a family identifier out of a
    refusal's text (they picked a case type, not a family), and that rule is
    unchanged here. It is on the record for the same reason `Refusal.family`
    exists — a gate, a log line, and somebody reading the committed case later.
    """

    reason: str
    family: str = ""

    def note(self) -> str:
        """What the log says on EVERY generation that runs as this fallback.

        Repeated per run rather than once at acceptance: a Trial costs about a
        second and an operator iterating on one would otherwise scroll the one
        line that says their mesh is not structured off the top of the log.
        """
        return "%s\n%s\nIt was offered because %s" % (
            NOT_STRUCTURED, NO_VERDICT, _lowered(self.reason))


def _lowered(reason: str) -> str:
    """``reason`` as a clause inside a sentence — its first letter only."""
    text = str(reason or "").strip()
    return (text[:1].lower() + text[1:]) if text else "the family refused."


def accepted(refusals) -> Fallback:
    """The :class:`Fallback` for a set of refusals the operator has accepted.

    The family is taken off the refusals rather than passed in beside them:
    `topology_model.preflight` stamps every row with the family the registry
    dispatched to (`topology_preflight.stamp_family`), so there is one answer to
    "which family refused" and a caller cannot supply a different one.
    """
    from app.services.topology_preflight import refusal_text
    rows = list(refusals or ())
    family = next((r.family for r in rows if r.family), "")
    return Fallback(reason=refusal_text(rows), family=family)


def offer_question(reason: str) -> str:
    """The question put to the operator, with the refusal that prompted it.

    The refusal is quoted IN the question rather than shown first in a dialog of
    its own: two modal boxes for one event is how an operator learns to dismiss
    the first, and the reason is what the acceptance is being given for.
    """
    return ("%s\n\n%s\n\n%s\n\nGenerate the hybrid fallback mesh instead?"
            % (reason, NOT_STRUCTURED, NO_VERDICT))


def as_hybrid(cfg):
    """``cfg`` as the FALLBACK runs it: the hybrid path, and no family.

    A copy, never a mutation — the panel's configuration is the operator's and
    still says what they asked for; the downgrade belongs to the run.

    Both halves are needed and the second is the subtle one: see the module
    docstring. Duck-typed on the config for the reason the rest of
    `services/mesh_modes.py` is.
    """
    out = copy.deepcopy(cfg)
    out.mesh_mode = MESH_MODE_HYBRID
    model = getattr(out, "topology", None)
    if model is not None:
        model.family = FAMILY_NONE
        model.detached = False
    return out


def unavailable(cfg) -> str:
    """Why no fallback can be offered for ``cfg`` either, or ``""``.

    Asked through `missing_mesh_input` on the config the fallback would actually
    run, so "can the hybrid path run at all" has one owner rather than a second
    spelling here. The live case is a `MESH_MODE 1` configuration with an EMPTY
    geometry list — legal there, where a topology may declare every one of its
    own corners, and nothing at all for a boundary layer to grow from. Offering
    a downgrade that produces no mesh would waste the operator's acceptance on
    a run that cannot succeed.
    """
    return missing_mesh_input(as_hybrid(cfg))


def fallback_record(fb: Fallback, dest_mesh: str, when: str) -> dict:
    """What a committed fallback case carries instead of a verdict.

    Machine-readable (``structured``) AND in words (``note``), because the two
    readers are a later tool and a person, and a flag nobody can read is how a
    case ends up being quoted as structured by someone skimming it.
    """
    return {
        "schema": FALLBACK_SCHEMA,
        "version": FALLBACK_SCHEMA_VERSION,
        "recorded": when,
        "mesh": os.path.basename(dest_mesh),
        "structured": False,
        "path": "hybrid",
        "note": NOT_STRUCTURED,
        "no_verdict": NO_VERDICT,
        "refused_by": {"family": fb.family, "reason": fb.reason},
    }
