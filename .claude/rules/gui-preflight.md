---
paths:
  - tools/PreProcessor/gui/app/services/topology_preflight*
  - tools/PreProcessor/gui/app/services/topology_hgrid*
  - tools/PreProcessor/gui/app/services/topology_ogrid*
  - tools/PreProcessor/gui/app/services/topology_cgrid*
  - tools/PreProcessor/gui/app/services/topology_tworing*
  - tools/PreProcessor/gui/app/services/topology_model*
  - tools/PreProcessor/gui/app/controllers/mesh_gen_diag_ctrl*
---

# The per-family pre-flight refusal

Loaded on demand when the refusal service, a topology FAMILY module, the family registry or the
mesh stage's diagnostics controller is read. Rules only — the rationale (the measurements, the
injections and the named blind spots) is `docs/design_notes/gui.md`, section "A FAMILY STATES
WHETHER IT CAN WORK WITH WHAT IT WAS GIVEN". Read that section before overruling a rule here; when
a rule changes, update BOTH.

**THE THIRTEENTH RULE FILE, AND THE FOURTH TAKEN BECAUSE ONE WAS FULL.** These rules belong beside
`.claude/rules/gui-topology.md`'s — same families, same registry — and that file says in its own
header that it is full and that "the next block here is a new rule file, not a squeeze". #85, #137
and #153 are the precedent — a rule file at its budget takes a new file rather than a squeeze,
because compressing rules to fit a number is how a rule quietly loses the clause that made it a
rule — and `docs/agents/rule-file-style.md` refuses the compression outright. No figure for that
file's remaining room is quoted here: it would be a number about another file that nothing
re-measures, which is the staleness `test_instruction_budget.py` check 7 exists against.

**THIS FILE OVERLAPS `gui-topology.md` RATHER THAN PARTITIONING IT**, which is the shape #85, #89
and #153 all took. Six of its seven globs are that file's as well, so a session reading
`services/topology_ogrid.py` loads BOTH and needs both: what the family BUILDS is there, what it
REFUSES is here. The seventh, `controllers/mesh_gen_diag_ctrl*`, is reached by no rule file's globs
but `gui-seams.md`'s tree-wide one, which carries no rule about it.

**These rules also govern files OUTSIDE the globs above, which cannot hand a reader the text**:
`controllers/mesh_gen_ctrl.py` (the GUI call site, whose own stage rules are in `gui-seams.md`'s
module map), `services/pipeline_runner.py` (the headless call site, whose stage rules are
`.claude/rules/pipeline-case.md`'s) and `tools/PreProcessor/apply_case_type.py` (the case-type host,
whose own rules are `.claude/rules/gui-handoff.md`'s). The tripwire table in `CLAUDE.md` is what
makes each of those reachable.

**A FAMILY STATES WHETHER IT CAN WORK WITH WHAT IT WAS GIVEN, BEFORE ANYTHING RUNS** (#165, parent
#158; `services/topology_preflight.py`, `services/topology_model.py`, the four family modules,
`controllers/mesh_gen_diag_ctrl.py`)

- **THE REFUSAL IS NOT AN EXIT CODE, AND THAT IS THE WHOLE TICKET.** `EXIT_ERR_TOPOLOGY` (8) fires
  after the operator has committed and its message is written for a developer — MEASURED on the
  drawing the gate builds: *block 'q0': its corners 'b0', 'f0', 'f1', 'b1' wind clockwise (signed
  area -0.650000), so every cell in it would be inverted.* Every noun in it is an id of a document
  the operator never opened. The mesher is NOT modified (ADR-0002); the refusal moves forward.
- **`Family.preflight` HAS NO DEFAULT, and that IS the enforcement.** A fifth family that writes a
  build function and forgets its refusal does not CONSTRUCT, so there is no state in which one is
  silently exempt — the acceptance criterion "a family with no refusal is caught by the gate" held
  by the dataclass rather than by a scan. It sits beside `build` for the reason `broken` does:
  which geometry a family can fill is the family's decision, so which it cannot is too.
- **NO SHARED RULE TABLE, by decision.** The preconditions genuinely differ — a closed loop for the
  O-grid, a SHARP trailing edge for the C-grid, a rectangle with four distinct corners for the
  H-grid, a seam strictly between two closed loops for the two-ring — and a table could hold only
  what all four agree on, which is nearly nothing. What IS shared lives in `topology_preflight`:
  `outline_refusal` (which calls `topology_binding.outline_problem` and never re-spells it) and the
  containment walk.
- **A REFUSAL CARRIES THE CURVE, NOT ONLY THE SENTENCE** (`Refusal.geom` / `segs` / `at`), the rule
  `BrokenBinding` already follows for a binding the panel repairs: a host must be able to point at
  the offending curve without re-parsing prose. `refusal_points` turns one into the polyline the
  mesh canvas's `highlight_segment` reads — Qt-free, so what the canvas draws is gated headlessly.
  `Refusal.text`'s curve prefix is CONDITIONAL, because most of these sentences already name the
  curve and an unconditional one printed the geometry twice.
- **THE REFUSAL NAMES NO FAMILY, NO EXIT CODE, NO MODEL FIELD AND NO DOCUMENT ID.** The operator
  picked a case type, not a family; `ogrid` is a registry key and "O-grid" is the label the combo
  shows. `Refusal.family` exists for a gate and a log line and is NOT in `text()`. Gate:
  `tests/test_topology_preflight.py` check 3, injection E.
- **THE H-GRID'S REFUSALS NAME NO CURVE, correctly.** It binds to nothing and its region is four
  numbers in the template rows, so `geom` is empty and the refusal names the ROW ('X Max', 'Blocks
  in X'). That is why `Refusal`'s three pointing fields are optional rather than required: inventing
  a curve for a family that has none is worse than saying it has none.
- **CONTAINMENT, NOT EQUIVALENT RADIUS, IS WHAT ANSWERS "IS THIS INSIDE THAT".** Both ring families
  nest their outlines by `equivalent_radius()`, which is area-derived and is the right ruler for the
  radial law. MEASURED: a 4.0 x 0.2 body has an equivalent radius of 0.505 against a unit circle's
  0.9999, so a body reaching x = ±2 passed every check this repo had and the mesher answered exit 8.
  `outside_point` walks the inner curve's own points. Gate: check 6, which asserts all three steps —
  the old ruler accepts it, the refusal names it, the REAL MESHER refuses it — and injection A.
- **`drawn_ring` AND `outside_point` MOVED OUT OF `topology_cgrid_section.py` INTO
  `topology_preflight.py`**, and that file imports them back under the names it published (#149
  wrote them there for the C-grid's section). One owner, because a second copy of a polygon walk is
  the defect this ticket's own check exists to catch.
- **BOTH MESHER-LAUNCHING HOSTS ASK ONE QUESTION, `topology_model.mesh_preflight`** — the mode's
  missing input first, the family's refusal after it. `services/pipeline_runner.py` calls that
  instead of `missing_mesh_input`, which is what it called before; a host that kept calling one half
  would be the one that still ships a drawing the family cannot fill. The GUI's half is
  `mesh_gen_diag_ctrl._topology_preflight_refused`, called from `run_mesh_generator` LAST of the
  pre-flight and still before the worker: a config missing a geometry file has nothing for a family
  to judge, so answering "your body is outside your far field" about a file that is not on disk
  would send the user to the wrong place. Gate: checks 2a (the runner's own `_run_mesh`, driven with
  the subprocess launcher replaced by a recorder that is never called) and 2b (the GUI's order, read
  off its `ast`).
- **`preflight_for_config` IS THE ONE PAIRING OF A CONFIG WITH ITS CONTEXT**, so the GUI, the
  headless runner and the case-type host cannot build that context differently — and it builds none
  at all for a family that binds to nothing, a `.dat` and a `.meta` parse per geometry being what
  `Family.binds` already exists to avoid.
- **IT ASKS BOTH HALVES — THE MODE AND A FAMILY NAMED**, for the reason `mesh_modes.topology_file`
  and `topology_skeleton.skeleton_for_config` ask both of their own: a family named while the mode
  is HYBRID drives nothing, the panel hides the whole section, and none of it reaches the run.
  Refusing a hybrid run over it would be this ticket's own worst outcome pointed the other way — a
  mesh the operator can have, withheld over a template nothing reads. Gate: check 1b, on the very
  drawing check 6 proves the multi-block path must refuse.
- **EVERY PROBLEM AT ONCE, never the first.** `refusal_text` lists them all, the rule
  `topology_model.broken_bindings` and `case_type_roles.RolePlan` already follow: repairing a
  drawing one refusal at a time is a generate, a refusal and a return per wrong curve. A family's
  own `plan` still stops at the first, because it answers "can this run?". Gate: check 8,
  injection D.
- **A DETACHED MODEL AND A HAND-WRITTEN TOPOLOGY FILE ARE REFUSED BY NOBODY HERE**, through the
  same `names_a_family()` predicate the projection and `broken_bindings` ask (#139): nothing on
  those paths is built from a family, so a refusal would be about a document no run reads. A
  hand-written document is the mesher's to judge, which is what `EXIT_ERR_TOPOLOGY` is for.
- **#164's NAMED BLIND SPOT IS CLOSED HERE, and only here.** A role the operator CONFIRMED can
  still be the wrong curve — a confirmed assignment naming the far field as the body binds exactly
  that, every id resolving — and `tools/PreProcessor/apply_case_type.py` now asks the family before
  it writes anything. Gate: check 9, a subprocess with the two roles swapped and both confirmed.
- **THE HIGHLIGHT COMES BACK OFF, AND ONLY OURS DOES.** A refusal left on the canvas after the
  operator has fixed the drawing points at a curve that is now fine, which is worse than no
  overlay — so `_topology_preflight_refused` clears on the no-refusal path. It clears only what IT
  drew (`_preflight_highlight`), because `highlight_segment` is also the per-segment
  boundary-condition dialog's and wiping somebody else's selection is the same defect in the other
  direction. Gate: `tests/test_topology_preflight.py` check 4c, which drives both halves through a
  real `AppController`.
- **A DRAWING THAT PASSES PRE-FLIGHT AND THEN FAILS IN THE MESHER IS A GAP IN THE REFUSAL**, and
  closing it means a check in `tests/test_topology_preflight.py` beside check 6 — the shape that
  check already has: assert the old answer accepted it, assert the new refusal names it, and run the
  real binary to show what the operator would otherwise have been told.

## Named blind spots

- **NOTHING HERE RE-ASKS WHAT THE MESHER ASKS.** The two sides are held at opposite ends — check 6c
  proves the mesher refuses the one document this ticket's new check catches — and nothing asserts
  that the two refuse the SAME set of drawings. A drawing both accept that still folds is the next
  gap, and arrives as a regression test by the rule above.
- **CONTAINMENT IS CONTAINMENT, NOT USEFULNESS.** `gui-topology.md` already records this for the
  C-grid's far field and it is unchanged by the two families that now share the walk: a far field
  one body-length out contains the body and is refused by nothing. The check exists to stop blocks
  folding, not to judge a domain.
- **A TANGENT TOUCH IS NOT RESOLVED.** `outside_point` is a crossing test, so a point lying exactly
  ON the outer polyline may read either way. Inherited from #149 rather than introduced, and no
  shipped case is within a rounding of it.
- **THE CONTAINMENT WALK IS O(inner points x outer points), MEASURED**: 0.11 s at 1,000 x 1,000 and
  1.86 s at 4,000 x 4,000. Paid once per Generate and never per keystroke, which is why it is
  recorded rather than bucketed — but a drawing an order of magnitude denser than anything this
  repo ships would make the refusal slower than the mesher run it is saving.
- **THE C-GRID'S FAR FIELD KEEPS ITS REFUSAL IN `plan`, AND THAT REFUSAL CARRIES NO CURVE.** That
  family is alone in sometimes GENERATING a far field from two lengths rather than reading one off a
  drawing, and attaching the bound geometry would point the canvas at the far field for a refusal
  about the target cell size — while deciding which of `plan`'s problems are "about" it means reading
  prose back for structured data, the move `BindingError` carries its edge as a FIELD to avoid. Its
  SECTION cascade is the half that gains a curve here.
- **THE REFUSALS ARE STRUCTURAL, NEVER POSITIONAL.** GridPro's "Causes of Bad Grids" taxonomy is the
  source material and two of its classes are reachable from here — topology cutting a surface on the
  concave side, and face mismatch. Positional forgiveness is not available to us (ADR-0001:
  positions are computed, not relaxed), so a refusal is the only move and a near miss is not
  detected at all.
- **A FAMILY'S OWN `plan` PROBLEM REACHES THE OPERATOR WITH NO CURVE ATTACHED** (the O-grid's and
  the two-ring's fall-through `Refusal(p.problem)`). `plan` reports one sentence and not which of
  its two or three outlines it blames, and attributing it would point at the wrong curve on the
  canvas. So the pairing, block-floor and winding refusals are named but not pointed at.
