---
paths:
  - tools/PreProcessor/gui/app/services/case_type_evidence*
  - tools/PreProcessor/gui/app/services/case_type_reference*
  - tools/PreProcessor/gui/app/services/case_type_author*
  - tools/PreProcessor/gui/app/services/case_type.py
---

# What a case type's thresholds rest on, and how a wrong one is corrected

Loaded on demand when the evidence service, the figures-and-provenance module, the authoring
step or the case-type document is read — **four files**, verified to match, and EVERY ONE of
them is also under `.claude/rules/gui-handoff.md`'s `services/case_type*`. This file OVERLAPS
rather than partitions, and it is the FIFTEENTH rule file and the SIXTH taken because another
was FULL: `gui-handoff.md` said in its own header that #164 left it 1,598 characters of slack,
that the next block there would be a new rule file, and that #165 and #166 should expect to
take one — both did, and #168 is the third addition since that sentence was written. A session
editing any of these four loads BOTH: what a case type IS, what it grades and what it owns is
there; what its numbers REST ON, and what happens when one of them judged wrong, is here.
**Rules only** — the rationale (the measurements, the reversals and the named blind spots) is
`docs/design_notes/gui.md`. Read that note before overruling a rule here; when a rule changes,
update BOTH.

**This file rules on TWO modules no glob in any rule file reaches**:
`tools/PreProcessor/add_reference_mesh.py`, #168's correcting host, and
`tools/PreProcessor/save_case_type.py`, #161's authoring one — both outside `gui-seams.md`'s
tree-wide `tools/PreProcessor/gui/**` as well, so the tripwire row in `CLAUDE.md` is the only
thing that reaches their reader. Both are outside `tests/test_silent_exceptions.py`'s swept
tree for the same reason, and both carry the narrow handler that file's absence argues for.
**`save_case_type.py` is `gui-handoff.md`'s as well, and that overlap is declared in both
headers** — what it AUTHORS is there, what it PRINTS about a threshold's support is here. The
first draft of this file claimed the host for itself and said so in the same breath as "no glob
in any rule file reaches", which was true of the globs and false of the governance; a reader
following only one of the two would have believed they had the whole rule.

**A MISJUDGED THRESHOLD IS CORRECTED WITH EVIDENCE, NEVER BY EDITING THE NUMBER**
(`services/case_type_evidence.py` = the derivation over a SET of reference meshes and the
invariants a document must obey, `services/case_type_author.py::add_reference` = the step,
`tools/PreProcessor/add_reference_mesh.py` = the one command; #168, parent #158, user stories
38 and 39). A case type starts from ONE reference mesh, which is a thin basis: it has an
opinion about what that mesh happened to exercise and none about anything else. Hand-editing a
bound would work and would throw away what the measurement bought — a threshold whose origin is
still visible six months later, which is ADR-0002's first consequence.

- **A REFERENCE MESH HAS A KIND, and it is recorded on the MESH.** An `EXEMPLAR` is a mesh the
  thresholds must ACCEPT; a `COUNTER-EXAMPLE` is one they must REJECT. The kind is a fact about
  the mesh — the maintainer judged it good or judged it bad — so one mesh cannot be good
  evidence for one figure and bad for another. `EXEMPLAR` is the DEFAULT and is written only
  when it is not in force, which is what keeps a v1-v4 document meaning exactly what it said.
- **THE DERIVATION IS ONE FUNCTION, `Evidence.bound`.** For one figure key, `base` is the WORST
  figure any exemplar published and `cap` the BEST any counter-example did; a bound is
  `base * factor`, held down to the SEPARATING BOUND `sqrt(base * cap)` when a counter-example
  would otherwise sit under it. The geometric midpoint is strictly between the two by
  construction, so every exemplar stays accepted and every counter-example is rejected — and it
  is a BAND against both, which is the same reason #161 multiplies by a factor at all. Pulling
  the bound to just under `cap` would reject by a hair and pretend to know where the boundary
  is. **Both bounds are held down, not only `unusable`**, or `attention` could rise above it and
  `Threshold` would refuse the pair.
- **AN ADDITION NEVER WIDENS A BOUND, and `cap` is what makes that true.** `cap` is the best
  figure published by a counter-example THIS FIGURE CAN TELL APART from the exemplars — the
  minimum over the counters above `base`, never over all of them. Taking the plain minimum lets
  a counter-example that sits BELOW the exemplars on a figure drop that figure's cap under
  `base`, which switches the hold-down off wholesale and springs the bound back to
  `base * factor`, discarding the restraint a genuinely separating counter-example had placed.
  **That shipped once and was found by review**, by adding a mesh separable on `bulk.p95` and
  not on `median`: `median`'s unusable bound went from 2.9866 back to 5.53793 without a word,
  and the only visible sign was a refusal message quoting a bound the file did not contain. A
  correction that LOOSENS a threshold is the opposite of what the maintainer asked for. Held by
  `tests/test_case_type_evidence.py` check 11, whose injection is that defect restored.
- **A KEY THAT SEPARATES NOTHING PLACES NO BOUND.** When `cap <= base` the bad mesh is no worse
  there than the good one, and a bound that accepts one and rejects the other does not exist.
  That is NOT a contradiction in the case type — the C-grid whose `max` is 96x the O-grid's is
  correctly rejected on `max` while its `bulk.median` says nothing. **The contradiction is only
  when NO key separates them**, and it is caught by asking the question rather than by reasoning
  about it: `standing_failures` tests every exemplar and every counter-example against the
  thresholds as they now stand.
- **ONE COMPARISON, TWO ASKERS.** `case_type_reference.exceeds` is the only `>` in play:
  `case_type_verdict.judge_threshold` asks it of a finished mesh and `case_type_evidence` asks it
  of every reference mesh a case type declares, so "every exemplar is accepted and every
  counter-example rejected" is a statement about the rule the VERDICT applies rather than a
  second opinion free to drift. It is STRICTLY greater, which is why a derivation that wants to
  reject a mesh must put the bound strictly BELOW its figure.
- **A HAND-SET BOUND IS NEVER RECOMPUTED.** It carries no tolerance factor, so there is nothing
  to re-derive, and `_rederived` asks `Evidence` only for the bounds that do. **Where that
  override is what stops the case type honouring the new mesh, the ADDITION is refused and the
  override is NAMED as the obstacle** — the only way both rules hold at once, since recomputing
  it silently breaks the first and accepting it silently leaves a counter-example the thresholds
  do not reject. That naming is not decoration: the maintainer's only moves are to drop the
  override or to leave the mesh out, and a refusal that does not say which bound is theirs
  leaves them with neither.
- **A THRESHOLD'S SUPPORT IS THE SET THAT BEARS ON ITS FIGURE**, exemplars and counter-examples
  alike, and it is both DERIVED (`CaseType.evidence_for`) and STORED
  (`measured_from.references`). The redundancy is safe because `check_derivations` holds the
  stored list to the derived one in BOTH directions — a named mesh that publishes nothing, and a
  mesh that publishes the figure and is not named, are one refusal with one message. `Origin`
  reads the older singular `reference` spelling and writes `references`; **a document spelling
  both is refused**, because a reader cannot be asked to guess which one is read.
- **NO THRESHOLD IS INVENTED BY AN ADDITION.** Advice is still the selection (#161): a figure
  the case type had no opinion about does not acquire one because a mesh published it. The skip
  is REPORTED, like an unmeasurable figure's is.
- **AN ALREADY-FINISHED CASE DOES NOT MOVE.** A committed case carries the WHOLE case type and a
  frozen verdict beside its mesh (`services/mesh_commit.py`, #166), so correcting the file an
  operator borrowed rewrites nothing that has already been judged — user story 43. That is a
  property of how a case is COMMITTED, not of anything the authoring step does, which is exactly
  why the authoring step may rewrite a case type freely.
- **A BAND THAT CLOSED IS SAID OUT LOUD.** When the evidence leaves no room between the worst
  exemplar and the nearest counter-example, both bounds land on the separating value and that
  figure can only answer `usable` or `unusable` from then on. `AddResult.notes` carries the
  sentence and the host prints it as a `cost:` line, because the verdict still ANSWERS — a
  maintainer who is not told reads a two-state answer as the full four. The decision is the
  SERVICE's, not the report's: it is a fact about the derivation. Silent when no band closed,
  which is what makes it mean something when it appears.
- **THE HOST REWRITES IN PLACE, AND `--dry-run` IS HOW A MAINTAINER SEES THE CONSEQUENCE FIRST.**
  `add_reference_mesh.py` prints every bound that moved, with its before and after, and says so
  out loud when NONE did: a maintainer who adds a mesh expecting a correction and gets none has
  learnt something, and a silent exit would read as the thresholds having moved.
Gated by `tests/test_case_type_evidence.py` (10 checks and nine automated injections, each
asserting the mutation is well-formed, that the named checks redden and that no other does; the
counts are that file's own docstring's and are not restated here). Two of its injections came
back INERT and are recorded there rather than quietly fixed — a gate that constructs its
fixtures by hand cannot reach the step that measures them, and a check that reads a module's
source off DISK cannot see any mutant at all.
  Why: `docs/design_notes/gui.md`, "A MISJUDGED THRESHOLD IS CORRECTED WITH EVIDENCE".

## Named blind spots

One list per rule file (`docs/agents/rule-file-style.md` rule 5). These are this file's coverage
limits — what a gate does NOT check — as distinct from the caveats stated with the rules above,
which are capability refusals.

- **NOTHING JUDGES WHETHER A REFERENCE MESH DESERVES ITS KIND.** That the C-grid is a mesh the
  shipped O-grid case type should reject is the maintainer's judgement, and the whole mechanism
  exists to RECORD a judgement rather than to form one. This is #161's "nothing judges whether a
  tolerance factor is right", moved one layer out.
- **THE SEPARATING BOUND IS A CHOICE, not a measurement.** What is gated is that it lies strictly
  between the worst exemplar and the best counter-example; that halfway in log space is the right
  place is argued in `case_type_evidence.py`'s docstring and nowhere measured. A maintainer who
  disagrees overrides the bound by hand, and the rule above is what keeps that override standing.
- **A COUNTER-EXAMPLE CAN LEAVE A FIGURE WITH NO NEEDS-ATTENTION BAND.** When the bad mesh is
  barely worse than the good one, both bounds land on the same separating value and that figure
  can only answer `usable` or `unusable`. It is honest — the evidence leaves no room for a middle
  — and it is why the shipped example adds ONE counter-example rather than every mesh to hand.
  Since review it is REPORTED rather than merely true, which is as far as this goes: nothing
  stops a maintainer from closing every band, and no gate measures how many are left open.
- **THE FLOATING-POINT EDGE IS REFUSED, NOT HANDLED.** `Evidence.separates` answers False when
  `sqrt(base * cap)` does not round to a value strictly between them, so two meshes that close
  place no bound at all and the addition is refused as inseparable. Nothing constructs that case
  in the gate; it is reasoned from the arithmetic.
- **NO GUI ACTION AUTHORS OR CORRECTS A CASE TYPE.** `add_reference_mesh.py` is headless, like
  `save_case_type.py` and `show_case_type.py` beside it. The GUI has Trial and Generate (#166)
  and no author and no picker, and no open ticket owns one.
