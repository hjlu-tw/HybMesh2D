---
paths:
  - tools/PreProcessor/gui/app/services/mesh_commit*
  - tools/PreProcessor/gui/app/services/mesh_fallback*
  - tools/PreProcessor/gui/app/controllers/mesh_dispose_ctrl*
  - tools/PreProcessor/gui/app/controllers/mesh_gen_ctrl*
  - tools/PreProcessor/gui/app/controllers/mesh_gen_diag_ctrl*
  - tools/PreProcessor/gui/app/controllers/pipeline_io_ctrl*
---

# Trial and Generate: one generation, two dispositions — and the hybrid fallback

Loaded on demand when the commit service, the FALLBACK service, the disposition controller, the
mesh-generation controller, the mesh stage's diagnostics controller or the pipeline-script
reader/writer is read. Rules only — the rationale (the
measurements, the injections and the named blind spots) is `docs/design_notes/gui.md`, sections
"TRIAL AND GENERATE: ONE GENERATION, TWO DISPOSITIONS" and, for the second block below, "A SHAPE
NO FAMILY COVERS IS A DOWNGRADE, NOT A DEAD END".
Read the matching section before overruling a rule here; when a rule changes, update BOTH.

**THE FOURTEENTH RULE FILE, AND THE FIFTH TAKEN BECAUSE ONE WAS FULL.** These rules belong beside
`.claude/rules/gui-handoff.md`'s — same case type, same verdict, same question about what a file
on disk still means — and that file says in its own header that #164 left it under one block's
worth of slack and that "the next block here is a NEW RULE FILE, not a squeeze, and #165 and #166
should expect to take it". #165 took `gui-preflight.md`; this is #166's. The precedent is #85,
#137, #153 and #165, and `docs/agents/rule-file-style.md` refuses the compression outright. No
figure for that file's remaining room is quoted here: it would be a number about another file that
nothing re-measures, which is the staleness `test_instruction_budget.py` check 7 exists against.

**THIS FILE OVERLAPS RATHER THAN PARTITIONS.** `services/mesh_commit*` and
`services/mesh_fallback*` are reached by no other rule file's globs, and
`controllers/mesh_dispose_ctrl*` by none but `gui-seams.md`'s tree-wide one. The other three are
shared on purpose: `controllers/mesh_gen_ctrl*` is also `gui-preflight.md`'s call site and
`pipeline-case.md`'s mesh-stage host, `controllers/mesh_gen_diag_ctrl*` is `gui-preflight.md`'s
(added here by #167, which gave that file's refusal an OFFER), and
`controllers/pipeline_io_ctrl*` is `pipeline-case.md`'s and `gui-panels-config.md`'s. A session
editing any of them loads several rule files and needs each: what the stage REFUSES before it runs
is `gui-preflight.md`'s, what it OFFERS when it has refused and what becomes of the mesh AFTER it
runs are here.

**These rules also govern files OUTSIDE the globs above, which cannot hand a reader the text**:
`views/main_window_toolbar_build_mixin.py` and `views/main_window_toolbar_mixin.py` (the two
buttons and their row), `views/main_window_menu_mixin.py` (the two menu entries),
`views/panels/mesh_config_panel.py` (the panel's pair, whose own rules are
`gui-panels-config.md`'s) and `controllers/signal_wiring_ctrl.py` (the wiring). The tripwire table
in `CLAUDE.md` is what makes each of those reachable.

**TRIAL AND GENERATE ARE ONE GENERATION AND TWO DISPOSITIONS** (#166, parent #158;
`services/mesh_commit.py` = the commit, Qt-free; `controllers/mesh_dispose_ctrl.py` = the two
actions; `controllers/mesh_gen_ctrl.py` = the one generation).

- **THERE IS ONE GENERATOR AND GENERATE DOES NOT RECOMPUTE.** `run_mesh_generator` is the only
  thing in the GUI that launches the mesher. **Trial** runs it with no disposition; **Generate**
  commits a trial still current for the configuration on screen, and only when there is none does
  it run one — that run being what it then commits. If Trial showed mesh A and Generate shipped
  mesh B the operator approved one thing and the solver reads another, and folds and wall-spacing
  error are exactly the defects that move with density. The identity is checked as one: check 4 of
  the gate compares the committed bytes with the trial's over all four formats while the host's
  own generator is instrumented to record a second launch that never happens.
- **THE DISPOSITION IS A KEYWORD-ONLY ARGUMENT, and that is a defence, not a style.** Qt hands a
  `clicked` slot the checked state as a POSITIONAL argument, so a button wired straight to
  `run_mesh_generator` would have committed into the case on every press. The buttons are wired to
  `trial_mesh` / `generate_mesh`; check 1 refuses any `connect(...)` naming `run_mesh_generator`.
- **TRIAL WRITES NOTHING THE CASE CONSUMES.** It meshes into the session temp dir, as the GUI
  always has (`.claude/rules/gui-handoff.md`, "the last generated mesh is not where a reopened case
  left it"), and `mesh_commit.commit` is the ONLY writer of a case's mesh on this path — so a Trial
  after a Generate cannot touch what Generate approved. Checked as an EMPTY case directory, not as
  an unchanged mesh: a Trial that wrote a verdict file into the case would already have broken it.
- **WHAT A COMMITTED CASE CARRIES, four things under the mesh's own stem.** The mesh in every
  format the run produced plus its `.provenance.json`; `<stem>.casetype.json`, **the whole case
  type document** — not its name and not a hash, because a name points at a file that moves and a
  hash proves only that it moved, and the copy is a case type `case_type.load` reads back;
  `<stem>.verdict.json`, the verdict as TEXT already rendered plus its state, deviations and exit
  code, FROZEN so that editing a borrowed case type cannot rewrite a finished case's judgement;
  and `<stem>.pipeline.json`, a runnable script. The record holds no threshold numbers of its own —
  the bounds are in the embedded document beside it, and two copies of one number is how they come
  to disagree.
- **NO HOST SPELLS A VERDICT, AND A DISPOSITION IS A HOST.** The refusal is
  `case_type_verdict.commit_refusal`, spelled there beside the states it reads and nowhere else;
  `mesh_commit.commit` raises its SENTENCE as `CommitRefused` and the controller shows it verbatim,
  so "says why" cannot be satisfied by a caller inventing its own wording. **Only `unusable`
  refuses**: `not determinable` is the absence of evidence and refusing on it would stop a case
  type whose metric a mesh does not publish from ever committing, while `needs attention` is by
  construction a mesh the operator is allowed to keep. **`EXIT_ERR_INVERTED` refuses WITH OR
  WITHOUT A CASE TYPE**, which is why the exit code is a parameter beside the verdict: a threshold
  is scoped to a class of problem and a FOLD is not, and ADR-0002 states that refusal with no case
  type in the sentence. Shipped reading "no verdict" as "nobody to refuse", so a folded mesh
  committed whenever `HYBMESH_CASE_TYPE` was unset — the ordinary state. A run with no case type
  still gets no verdict FILE, and the host says so rather than leaving its absence to be noticed.
- **TWO ENTRY POINTS, ONE PASS THROUGH THE THRESHOLDS.** `case_type_verdict.run_verdict` judges and
  renders; `run_report` is that function with the judgement dropped. The headless host calls the
  second, the GUI's disposition the first — through `mesh_commit.judge_run`, which carries the
  rendering AND the judgement from one pass, because asking twice would be two answers about one
  mesh and the first to drift would be the one nobody is looking at. Neither may reach past its
  entry point; `test_case_type_verdict.py` check 9 reads all three hosts' ASTs for it.
- **THE FINGERPRINT ANSWERS "IS THIS STILL THE MESH THESE SETTINGS PRODUCE".** Taken over the
  mesher's own config TEXT — the bytes the binary read, through the model's own `save_to_file`, not
  a second spelling of the `.dat` format — plus the content of every input that text names
  (`geom_path_identity.keyed_geom_paths` for the geometry, `case_sources.mesh_input_paths` for the
  block topology document; two existing owners, no third rule). **It fails SAFE**: an unreadable
  input, or a fingerprint nobody took, reads as stale, so "we did not check" can never read as "it
  is current" and Generate re-meshes instead. **BOTH HALVES GO THROUGH
  `mesh_gen_ctrl.mesher_config`**, the one transformation that turns the panel's config into the
  one the mesher is handed (output into the temp dir, both formats forced on). Shipped with the
  halves apart and caught in review: they differed by `EXPORT_VTK` alone, so no trial ever read as
  current and Generate re-meshed every time while a branch logged that it had not — fail-safe, and
  the whole fingerprint dead weight. Check 12 is what puts the producer and the consumer on one
  path.
- **ONE BUILDER FOR THE COMMITTED SCRIPT.** `pipeline_io_ctrl.build_pipeline_config` is what both
  the Pipeline menu's Save and the commit use; the disposition constructs no `PipelineConfig` of
  its own. Two builders is how a case ends up carrying a script that reproduces something else.
  A script that cannot be built costs the operator the script, never the mesh they just approved.
- **`Preview` IS STILL `Preview`.** The existing canvas drawing of the far-field box and the
  boundaries — "BC Preview" in the menu — meshes nothing and is untouched; the new action is named
  **Trial** for exactly that reason. Both are distinct from **Run All**, which remains the whole
  chain through the solver.
Gated by `tests/test_mesh_trial_commit.py`; the check and injection counts are that file's own
docstring's and are not restated here.
  Why: `docs/design_notes/gui.md`, "TRIAL AND GENERATE: ONE GENERATION, TWO DISPOSITIONS".

**A SHAPE NO FAMILY COVERS IS A DOWNGRADE, NOT A DEAD END** (#167, parent #158;
`services/mesh_fallback.py` = every sentence and the config transformation, Qt-free;
`controllers/mesh_gen_diag_ctrl.py` = the offer; `services/mesh_commit.py` = the record)

- **THE TRIGGER IS THE FAMILY IN FORCE REFUSING, NOT A SURVEY OF ALL FOUR**, and the criterion's
  own words ("when every family refuses") are satisfied because exactly one family is ever in
  play. A survey CANNOT work and the reason is measured: the H-GRID BINDS TO NOTHING
  (`Family.binds` is False), its refusals are about its own parameter rows, and it therefore
  ACCEPTS every drawing in this repo — including one it would mesh as a bare rectangle of blocks
  ignoring the body. "Every family refuses" would never have been true and the fallback would
  never have been offered. The other three are no better as witnesses: an unconfigured family
  refuses because its bindings are empty, a fact about the configuration and not about the shape.
  **AND #158 EXCLUDES THE SURVEY BY NAME**: its Out of Scope list says "Automatic topology
  derivation. Nothing inspects a geometry and proposes a family or its parameters", and asking all
  four which could fill a drawing IS that derivation one answer short of proposing one. That is
  the stronger half and a review axis supplied it. Gate: `tests/test_mesh_fallback.py` check 1d,
  which MEASURES the H-grid accepting the drawing the C-grid refuses rather than asserting it.
- **IT IS NEVER SUBSTITUTED SILENTLY, AND THAT IS THE WHOLE RULE.** Someone who does not know
  whether their mesh is structured cannot reason about anything downstream of it. So the offer is
  a `confirm` the operator answers, with `headless_default=False`: a host with nobody to ask
  REFUSES. The headless pipeline never reaches the offer at all — it asks
  `topology_model.mesh_preflight` and still refuses, which is this same rule where there is no
  operator rather than an omission. Gate: check 2, and injection H, which records the answer and
  then ignores it.
- **THE ACCEPTANCE IS KEYED ON THE REASON IT WAS GIVEN FOR.** `Fallback.reason` is
  `topology_preflight.refusal_text`'s output VERBATIM, so an unchanged refusal is not re-asked
  (a Trial costs about a second) while any change to what the family objects to is. The label is
  said again on EVERY run regardless, because a line seen once and scrolled past is not a label.
  `_settle_fallback` drops an acceptance the configuration no longer needs on a Generate that
  runs no pre-flight of its own — and what that closes is the TRANSFORMATION, not the bookkeeping:
  a stale acceptance would hand the mesher a family-less run for a drawing the operator
  deliberately moved. A trial already GENERATED as a fallback keeps `TrialMesh.fallback` and still
  commits its record, which is correct rather than stale — that mesh really is the unstructured
  one. The first wording claimed otherwise and a review axis measured it. Gate: check 9, whose 9d
  asserts the consequence (`mesher_config` stops rewriting the config) and not only the flag;
  injection F.
- **THE DOWNGRADE CLEARS THE FAMILY AS WELL AS THE MODE**, and the second half is not tidiness:
  `mesh_config_io.save_config_to_file` PROJECTS a named family's document whenever
  `names_a_family()` is true, asking the MODE nowhere, and a family that cannot build raises from
  inside that call. A mode-only downgrade therefore dies in the config WRITER, before the mesher
  it is downgrading to is ever launched, on precisely the drawings this exists for. MEASURED:
  check 3b writes both and compares what each raises.
- **THE TRANSFORMATION LIVES IN `mesher_config`**, beside the output retarget and the forced
  export formats, for the reason those two are there: the fingerprint is taken over the resulting
  TEXT, so a fallback run and a structured run of the same panel configuration cannot read as the
  same generation. The PANEL is never mutated — the downgrade belongs to the run, and the
  operator's configuration still says what they asked for.
- **NO VERDICT IS ISSUED, AND THE THRESHOLDS ARE NEVER READ.** Not ignored — never consulted:
  `judge_run` short-circuits before `case_type_verdict.run_verdict`, because the bounds were
  measured on structured quads and the mesher's own banner says the two paths' cell-shape metrics
  are different quantities. `mesh_fallback.NO_VERDICT` stands where the verdict would be, at
  WARNING. A FOLD is still refused: `commit_refusal` needs no case type behind it (ADR-0002), and
  a downgrade buys no exemption. Gate: checks 5 and 7.
- **EVERY SENTENCE THE OPERATOR READS IS `services/mesh_fallback.py`'S, INCLUDING THE TWO THAT
  ARE NOT ABOUT THE DOWNGRADE ITSELF.** `DECLINED` (what a turned-down offer says) and
  `unavailable_text` (a refusal plus why no downgrade can answer it) were authored at the call
  site in the first cut while this very rule claimed otherwise — an `every`-claim the code
  contradicted, which is the staleness class this repo keeps a gate for. The host owns the
  component prefix and the GRADE and nothing else, which is `gui-seams.md`'s split; `_say_fallback`
  is the one place that pairs them, because three call sites said the same thing three times.
- **WHERE A FALLBACK MESH IS LABELLED — the complete list, enumerated and not promised.** The
  question that offers it; the GUI log on EVERY fallback generation, Trial and Generate alike;
  the verdict slot; the committed `<stem>.fallback.json`; and the committed `<stem>.pipeline.json`,
  which is a `MESH_MODE 0` script. The Mesh Statistics panel is deliberately NOT on it: it is
  handed a mesh and its `.provenance.json` and cannot tell a fallback from an ordinary hybrid run,
  and labelling every hybrid mesh in the tree "fallback" is the same lie pointed the other way.
- **THE COMMITTED RECORD SLOTS ARE RECONCILED, NEVER JUST WRITTEN.** `<stem>.fallback.json` is
  mutually exclusive with `<stem>.casetype.json` and `<stem>.verdict.json`, and `commit` removes
  whichever two do not apply — a verdict file beside a fallback mesh is a judgement of a mesh that
  no longer exists. ALL THREE directions, the third included: an UNJUDGED commit removes the
  fallback record too. Gate: check 6b and check 10's stale leg, plus injection I — check 10 used
  to commit into a fresh directory and so passed on nothing, measured by a review axis that
  deleted the argument and watched the whole gate stay green.
- **THE COMMITTED SCRIPT DESCRIBES THE RUN THAT HAPPENED.** `build_pipeline_config` gained a
  `mesh_cfg` override with exactly ONE caller, the fallback commit; a script carrying the panel's
  `MESH_MODE 1` would be refused by the family the moment anyone ran it, leaving a committed case
  holding a mesh beside a script that cannot reproduce it. An override rather than a second
  builder, which the rule above forbids. Gate: check 8, which also reads the AST for a
  `PipelineConfig` built on the spot.
Gated by `tests/test_mesh_fallback.py`; the check and injection counts are that file's own
docstring's and are not restated here.
  Why: `docs/design_notes/gui.md`, "A SHAPE NO FAMILY COVERS IS A DOWNGRADE, NOT A DEAD END".

## Named blind spots

One list per rule file (`docs/agents/rule-file-style.md` rule 5). These are this file's coverage
limits — what a gate does NOT check — as distinct from the caveats stated with the rules above,
which are capability refusals.

- **THE FINGERPRINT IS BLIND TO ANYTHING THAT IS NOT THE CONFIG OR A FILE IT NAMES.** A different
  MESHER BINARY is the live instance: rebuild while a trial is in hand and Generate commits the old
  build's mesh. Recorded rather than fixed — a trial lives only for the session that made it, and
  hashing the binary on every currency check is not worth that.
- **A TRIAL AFTER A GENERATE STILL REPOINTS THE SESSION AT ITSELF.** The commit moves
  `global_vtk_path` to the committed mesh, so Export and Send to Solver reach what Generate
  approved — until the next Trial, which is a generation like any other and sets it to its own
  scratch mesh. `mesh_grid_lookup.resolve_case_grid` prefers "this session's mesh" over the
  per-case one (`.claude/rules/gui-handoff.md`, from a user-reported defect), so a Generate, then a
  Trial, then Send to Solver hands the solver the un-approved mesh. #158's story 8 wants otherwise;
  #166's criterion is only that the COMMITTED mesh is untouched, which holds, so the precedence was
  left alone rather than widened into another rule file's subject.
- **THE COMMIT IS NOT ATOMIC.** The refusal happens before anything is written, so a refused mesh
  leaves nothing; but a copy that fails PART WAY — a full disk on the third format — leaves the
  case holding some of the new mesh and some of the old. The host reports the `OSError` and the
  operator can press Generate again; nothing stages into a temp directory and renames.
- **A DEFECT INSIDE A FAIL-SAFE DIRECTION IS SILENT BY CONSTRUCTION.** The fingerprint halves
  disagreeing cost nothing an operator could see: Generate re-meshed, and the mesh it then
  committed was the mesh its own run had judged. Every acceptance criterion still held; only the
  "without regenerating it" clause did not, and no log line or output differed. A check that
  compares the two halves is the only thing that speaks, which is why check 12 exists and why a
  fail-safe fallback is worth a check of its own rather than trust.
- **THE GATE DRIVES THE REAL CONTROLLER AGAINST A RECORDING STAND-IN FOR THE MAIN WINDOW.** That
  the two buttons are on screen, enabled and in the right row is read from SOURCE (check 1) rather
  than from a window anyone opened; `smoke_headless_appcontroller.py` is what builds a real one.
- **RUN ALL DOES NOT CARRY AN ACCEPTANCE GIVEN ON THE MESH TAB.** It reaches the mesher through
  `services/pipeline_runner.py`, which asks `topology_model.mesh_preflight` and refuses with no
  offer — correct for a headless host and surprising for an operator who has just meshed the same
  drawing as a fallback two clicks away, and nothing tells them why. #167's criteria are about
  Trial and Generate (its own "Blocked by" says so) and #166 holds Run All separate, so this is
  recorded rather than widened. Found by a review axis.
- **THE ACCEPTANCE LIVES FOR THE SESSION AND NOTHING READS IT BACK.** A case committed yesterday
  carries its `<stem>.fallback.json`, and reopening it tells the GUI nothing: the next Trial asks
  again from scratch. That is the safe direction (an acceptance is never inherited) and it is also
  why the record is a record rather than state.
- **"THE EXISTING HYBRID PATH IS UNCHANGED" IS HELD AT THE GUI LEVEL, NOT BY `golden_mesh.py`.**
  #167 touched no C++ at all, and the comparator was run by hand for the record (21 cases, 0 DIFF,
  worst coordinate deviation 0.000e+00, one of the 21 a NO-MESH outcome). `test_mesh_fallback.py`
  check 10 is what a gate can hold: a hybrid-mode configuration reaches no offer, `mesher_config`
  leaves it alone, and an unjudged commit still writes no sidecar.
- **NOTHING CHECKS THAT A COMMITTED CASE IS STILL CONSISTENT LATER.** Whether the mesh beside a
  frozen verdict is still the mesh that verdict judged is nobody's question once Generate returns:
  a later Export, a hand-edit or a headless `run_pipeline.sh` over the same output path can replace
  the mesh and leave the record standing.
