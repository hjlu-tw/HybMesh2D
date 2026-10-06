---
paths:
  - tools/PreProcessor/gui/app/services/mesh_commit*
  - tools/PreProcessor/gui/app/controllers/mesh_dispose_ctrl*
  - tools/PreProcessor/gui/app/controllers/mesh_gen_ctrl*
  - tools/PreProcessor/gui/app/controllers/pipeline_io_ctrl*
---

# Trial and Generate: one generation, two dispositions

Loaded on demand when the commit service, the disposition controller, the mesh-generation
controller or the pipeline-script reader/writer is read. Rules only — the rationale (the
measurements, the injections and the named blind spots) is `docs/design_notes/gui.md`, section
"TRIAL AND GENERATE: ONE GENERATION, TWO DISPOSITIONS".
Read that section before overruling a rule here; when a rule changes, update BOTH.

**THE FOURTEENTH RULE FILE, AND THE FIFTH TAKEN BECAUSE ONE WAS FULL.** These rules belong beside
`.claude/rules/gui-handoff.md`'s — same case type, same verdict, same question about what a file
on disk still means — and that file says in its own header that #164 left it under one block's
worth of slack and that "the next block here is a NEW RULE FILE, not a squeeze, and #165 and #166
should expect to take it". #165 took `gui-preflight.md`; this is #166's. The precedent is #85,
#137, #153 and #165, and `docs/agents/rule-file-style.md` refuses the compression outright. No
figure for that file's remaining room is quoted here: it would be a number about another file that
nothing re-measures, which is the staleness `test_instruction_budget.py` check 7 exists against.

**THIS FILE OVERLAPS RATHER THAN PARTITIONS.** `services/mesh_commit*` is reached by no other rule
file's globs, and `controllers/mesh_dispose_ctrl*` by none but `gui-seams.md`'s tree-wide one. The
other two are shared on purpose: `controllers/mesh_gen_ctrl*` is also `gui-preflight.md`'s call
site and `pipeline-case.md`'s mesh-stage host, and `controllers/pipeline_io_ctrl*` is
`pipeline-case.md`'s and `gui-panels-config.md`'s. A session editing either loads several rule
files and needs each: what the stage REFUSES before it runs is there, what becomes of the mesh
AFTER it runs is here.

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
  construction a mesh the operator is allowed to keep. A run with no case type has nobody to
  refuse, and the host SAYS so rather than leaving the missing verdict file to be noticed.
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
  is current" and Generate re-meshes instead.
- **ONE BUILDER FOR THE COMMITTED SCRIPT.** `pipeline_io_ctrl.build_pipeline_config` is what both
  the Pipeline menu's Save and the commit use; the disposition constructs no `PipelineConfig` of
  its own. Two builders is how a case ends up carrying a script that reproduces something else.
  A script that cannot be built costs the operator the script, never the mesh they just approved.
- **`Preview` IS STILL `Preview`.** The existing canvas drawing of the far-field box and the
  boundaries — "BC Preview" in the menu — meshes nothing and is untouched; the new action is named
  **Trial** for exactly that reason. Both are distinct from **Run All**, which remains the whole
  chain through the solver.
Gated by `tests/test_mesh_trial_commit.py` (11 checks and seven injections; the counts are that
file's own docstring's and are not restated here).
  Why: `docs/design_notes/gui.md`, "TRIAL AND GENERATE: ONE GENERATION, TWO DISPOSITIONS".

## Named blind spots

One list per rule file (`docs/agents/rule-file-style.md` rule 5). These are this file's coverage
limits — what a gate does NOT check — as distinct from the caveats stated with the rules above,
which are capability refusals.

- **THE FINGERPRINT IS BLIND TO ANYTHING THAT IS NOT THE CONFIG OR A FILE IT NAMES.** A different
  MESHER BINARY is the live instance: rebuild while a trial is in hand and Generate commits the old
  build's mesh. Recorded rather than fixed — a trial lives only for the session that made it, and
  hashing the binary on every currency check is not worth that.
- **THE COMMIT IS NOT ATOMIC.** The refusal happens before anything is written, so a refused mesh
  leaves nothing; but a copy that fails PART WAY — a full disk on the third format — leaves the
  case holding some of the new mesh and some of the old. The host reports the `OSError` and the
  operator can press Generate again; nothing stages into a temp directory and renames.
- **THE GATE DRIVES THE REAL CONTROLLER AGAINST A RECORDING STAND-IN FOR THE MAIN WINDOW.** That
  the two buttons are on screen, enabled and in the right row is read from SOURCE (check 1) rather
  than from a window anyone opened; `smoke_headless_appcontroller.py` is what builds a real one.
- **NOTHING CHECKS THAT A COMMITTED CASE IS STILL CONSISTENT LATER.** Whether the mesh beside a
  frozen verdict is still the mesh that verdict judged is nobody's question once Generate returns:
  a later Export, a hand-edit or a headless `run_pipeline.sh` over the same output path can replace
  the mesh and leave the record standing.
