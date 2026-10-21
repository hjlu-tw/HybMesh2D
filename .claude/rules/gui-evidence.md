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

**THE FIGURE VOCABULARY IS A PRODUCT, AND A NEW SET JOINS EVERY CONSUMER AT ONCE**
(`FIGURE_KEYS` in `services/case_type_reference.py`; #160, widened by the size-jump
sidecar work, `3b71c21`, 2026-10-13).
- **`("", "layer", "bulk", "size_jump") x ("median", "p95", "max")`, built by PRODUCT rather than
  written out twelve times.** That work added the fourth SET by adding one string, and
  `size_jump.median|p95|max` reached the authoring step, the evidence derivation, the verdict and
  the document validator with no edit in any of them — the property the product exists for, and
  the reason a figure cannot arrive in one list and be missing from another.
- **`figures_for` is a `getattr` and is DUCK-TYPED, which is what makes a differently-shaped set
  free.** The size jump's own class counts **`pairs`**, not `cells` — it counts PAIRS of structured
  quads, and on a mesh of N quads that is neither N nor a fixed multiple of it, so the mesher's
  struct, the sidecar key and this class all refuse the rename together. Both consumers
  (`case_type_author.measured_figures`, `case_type_verdict.judge_threshold`) read only `.measured`
  and the three fields, so neither noticed.
- **THE SIZE JUMP IS NOT GATED BY THE CASE TYPE'S `metric`.** That field names which CELL SHAPE was
  measured, and `quad_midline_ratio` against `tri_edge_ratio` is `not determinable` because those
  two are incomparable (#130). The size jump is NEITHER path's cell shape; its PRESENCE alone
  answers whether it can be judged, and it is absent exactly where it is not measured.
- **TWO SETS CAN BE ABSENT AND THEY MUST NOT SHARE A SENTENCE** (`absence_detail`, one owner). A
  HALF is absent on a sidecar from a path that did not SPLIT — the operator can ask for it. The
  SIZE JUMP is absent on a path that does not MEASURE it, having no structured quad, which is the
  hybrid path — asking again will not help. The hardcoded sentence it replaced ("this run published
  no layer/bulk split") would have been said to a hybrid-path operator, where it is false AND
  unactionable. Gated by `tests/test_case_type_verdict.py` check 15, which asserts the two strings
  DIFFER rather than only that each contains its own words — a single sentence containing both
  would pass the weaker form. Reverting `absence_detail` to one string reddens that check alone.
- **A FULLY MEASURED REFERENCE BOUNDS ALL TWELVE**, which is what `tests/test_case_type_author.py`
  checks 2, 3 and 6 ask. Its `split_summary` fixture therefore carries the size jump BY DEFAULT;
  the verdict gate's same-named fixture makes it OPT-IN instead, because that file's checks are
  about what a verdict says when a figure is ABSENT. Two fixtures, two defaults, each matching the
  question its file asks.

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

**A SHIPPED CASE TYPE HAS TO BE AUTHORED FROM A CASE THAT CARRIES ITS FAMILY**
(`examples/case_types/ogrid_circle.casetype.json`, authored from
`config/pipeline/ogrid_family_demo.json`; #171, parent #158). The mechanism #164/#165/#170 built
was complete and gated, and for six tickets NO shipped artefact exercised it: the tree's one case
type owned three mesh fields, named no `topology.family` and declared no `characteristic_length`,
so picking it told the operator "this case type names no topology family that binds to your CAD,
there are no roles to assign" and every geometric size was carried at 1:1. Five of #158's own
user stories (2, 3, 4, 22, 40) were true of the gates' fixtures and unreachable from the window.
Shipping content is a separate act from building the mechanism, and this is the rule that act
produced.

- **A `.dat` CANNOT BE THE `--fields-from` SOURCE OF A CASE TYPE THAT NAMES A FAMILY.** When
  `cfg.topology` names one, `models/mesh_config_io.py::save_config_to_file` PROJECTS the family's
  document and writes the path to it as `MESH_TOPOLOGY_FILE` — so in a `.dat` the family is an
  OUTPUT and the document is the input, and `mesh_topology_file` is a field no case type may own
  (`case_type_fields.EXCLUDED`). The authoring source must therefore be the shape that holds a
  `topology` section: a `.hws` workspace or a pipeline script, both of which
  `MeshConfig.to_dict()` writes it into.
- **AND THE FAR FIELD HAS TO BEAR `farfield`, OR THE RULER IS THE DOMAIN.** `measure_role` selects
  the geometries bearing a `MeshConfig.geom_roles` role and spells the DEFAULT role as the absence
  of an entry, so a far field on a plain `GEOM_FILE` line reads back as `body`: `body.x_extent`
  measured **20** on the O-grid where the maintainer means 1, and **30** on the C-grid where they
  mean the chord. It would have gone on working — consistently, at both ends — which is why
  nothing had noticed. The one-line fix is `DOMAIN_FILE … nobl`, and it REQUIRED a mesher change
  to be legal at all (`.claude/rules/mesher.md`): that path did not load the domain outline, so
  the role an operator assigns to say what the curve IS made it invisible to the document bound
  to it.
- **THE SHIPPED CASE TYPE'S OVERLAY AND ITS EVIDENCE ARE ONE CASE, and that is checkable rather
  than asserted.** The O-grid family at `ogrid_cell 0.033` and `ogrid_radial_count 49` projects a
  document IDENTICAL to the hand-written `examples/topology/ogrid_circle.json` — corner for
  corner, count for count — and so a canonically identical mesh (`golden_mesh.py`'s comparison,
  worst deviation 0.0, and the same nine published figures). So the family could be added to the
  overlay with NO threshold re-derived and none re-defended, which is what made #171 content
  rather than a second case type with new numbers to argue about. `test_case_type_apply.py`
  check 16 asserts the identity in both directions — from the case type through the roles, and
  from the authoring script — because "the file's opinion describes the mesh its own thresholds
  were measured from" is the whole claim a reference mesh makes.
- **THE DATES MOVED AND THE FIGURES DID NOT.** Re-authoring re-read both provenance sidecars, so
  both references are `measured_on` 2026-10-21; every figure and every threshold came back
  identical, and the exemplar gained the three `size_jump.*` its sidecar has published since
  `3b71c21`. A date that says when the figures were read is the only thing a re-read may change.
Gated by `tests/test_case_type_apply.py` check 16 (outside that file's mutant comparison on
purpose — its subject is the ARTEFACT, not the service) and `tests/test_case_type_fields.py`
checks 1, 4 and 9, which pin the overlay the script captures and the three fields a `.dat` cannot.
  Why: `docs/design_notes/gui.md`, "A SHIPPED CASE TYPE HAS TO BE AUTHORED FROM A CASE THAT
  CARRIES ITS FAMILY".

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
- **NOTHING SWEEPS `examples/case_types/` FOR THE PROPERTIES #171 SHIPPED.** Check 16 names the
  one file; a SECOND shipped case type that named no family would be covered by nothing. Left as
  it is because the tree holds one, and a sweep over one file is a sweep that cannot fail for the
  reason it was written.
- **AND NOTHING RUNS `config/pipeline/ogrid_family_demo.json`.** Its `topology` section is pinned
  (check 16) and its captured scalars are (`test_case_type_fields.py` check 1), so the half that
  decides the mesh is covered; a typo in its `cads`, `solver` or `results` sections is not. That
  is every shipped script's exposure but `naca_demo.json`'s, which is the one CI runs end to end.
  It was run by hand on 2026-10-21 and produced the reference mesh's own figures exactly.
- **NO GUI ACTION AUTHORS OR CORRECTS A CASE TYPE.** `add_reference_mesh.py` is headless, like
  `save_case_type.py` and `show_case_type.py` beside it. #169 gave the window a PICKER — which
  selects what judges and writes nothing — and authoring stays #158's own Out of Scope.
