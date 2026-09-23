---
paths:
  - tools/PreProcessor/gui/**
---

# GUI seam rules, and the four repo-wide standards in full

Loaded on demand when **any** file under `tools/PreProcessor/gui/` is read — deliberately the
widest glob of any rule file, because these rules bind every GUI file rather than one area's, so
no narrower glob keeps their reach. **The COUNT of rule files is not spelled here on purpose**:
this sentence carried it as an English word, `--sync` could not reach it, and #89's ninth file
left it false while the identical wording in the root's tripwire row was rewritten from the tree.
A count that need not be stated is better deleted than gated — #88's lesson, applied by removal. **Rules only** — the rationale (the measurements, the dated user
reports, the injections and the named blind spots) is `docs/design_notes/gui.md`. Read that note
before overruling a rule here; when a rule changes, update BOTH. **One rule's rationale is here
instead, so that pointer is true only in part**: the parity block came out of the root file's
`## Build & Run` section, which the 2026-08-28 extraction (`3a2e096`) never touched, so these
lines ARE its whole story and the note carries only its blind spot. Stated here rather than fixed
by moving text into a note, which #59 puts out of scope.

**Four of these rules are ALSO pinned in `CLAUDE.md`, one line each, and that duplication is the
point.** The GUI↔C++ config parity gate, the GUI file-length limit, `never a broad except that
discards` and `never a raw blockSignals pair` belong to no area, and a glob cannot bind an edit that happens
outside every glob — measured in #61, a rule file does not arrive for an `Edit` without a prior
`Read`, nor for a `Write` creating a new file. The root carries the rule and its gate; this file
carries the whole of it. When one changes, both change.

**Two of the four reach files no glob here covers**, which is the other half of why they are
pinned in the root:
- **Parity** rules on `include/BLParams.hpp` and `include/Config.hpp` as much as on the GUI key
  map. Those two are matched by `.claude/rules/mesher.md`'s `include/**`, and that file carries no
  parity rule — it only mentions the gate in passing (its `MESH_MODE` initialiser note). An agent
  editing the C++ half is reached by the root one-liner, not by this file.
- **The broad-`except` rule and the signal guards** are repo-wide by intent; their gates
  (`tests/test_silent_exceptions.py`, `tests/test_signal_guards.py`) sweep the GUI tree, so the
  glob covers what is gated and the root line covers what is not.

**The Qt-free seam also governs two files OUTSIDE this glob**, which cannot hand a reader the
text: `tools/PreProcessor/run_pipeline.py` and `run_batch.py` — the headless entry points, and the
ones the deferred-import defect actually killed. The two are NOT equally reachable, measured
rather than assumed: `run_pipeline.py` is matched by `.claude/rules/pipeline-case.md` (which
carries the stage rules and not this one), while `run_batch.py` is matched by **no glob in any
rule file** — the same reachability gap #66 recorded for `services/phi_quality.py`. For that one
file the tripwire table in `CLAUDE.md` is not a convenience on top of a glob; it is the only thing
that reaches its reader.

**One block travels here that #59 does not assign to any area**: the one-line scroll-wheel rule.
Its only file is `main.py`, which no other rule file's globs reach, and this file's glob is the
whole GUI subtree — so this is the only rule file that can hand a `main.py` reader anything.
Recorded rather than left as silent precedent, per #66.

---

**GUI↔C++ config parity: every mesh key must agree in KEY, TYPE and DEFAULT, in both directions.**
Gated by `tests/test_gui_cpp_config_parity.py`. Key presence alone is blind to the two divergences
that produce a wrong mesh instead of an error. Both sides are read as declarations: the C++ from
`include/BLParams.hpp`'s rows plus `Config.hpp`'s `key == "..."` branch → member → struct
initialiser (a key that stops resolving fails check 0, so a blind extractor cannot turn the
comparison into a no-op), the GUI from the derived key map + `field_spec.model_types` +
`MeshConfig()` — whose own rules moved to `.claude/rules/gui-panels-config.md` in #64. New
C++-only keys must be justified in `KNOWN_CPP_ONLY`; structural multi-token lines in `_STRUCTURAL`.
- **`PINNED_TYPE_DIVERGENCE` is empty and must stay empty.** A type mismatch means one side cannot
  represent what the other stores, so there is no intended version of it. The gate found one —
  `BL_AUTO_FAN_NODES` — and it was FIXED, not pinned.
- **`PINNED_DEFAULT_DIVERGENCE` pins BOTH values and a reason**, because the two defaults answer
  *different questions*: the C++ one is what an unspecified key in a hand-written `.dat` means
  (neutral and safe), the GUI one is what a fresh editing session suggests before the user changes
  it. Forcing them equal would make a new GUI case default to an all-`wall` box with no inlet, or
  make the mesher stop writing a VTK for a CLI user who asked for nothing. Measured 2026-09-03: 8
  of the 52 shared keys diverge, and all 8 are correct. Pinning both values means a *change* to
  either side fails the gate again, so an entry cannot absorb a new drift.
- **Check 6 machine-checks the pinning's precondition**: the GUI must write that key
  **unconditionally**, so the mesher's differing default is never the one in force for a GUI run.
  Not a formality — 7 of the writer's keys really are conditional.

**Keep each file under `tools/PreProcessor/gui/` at ~500 lines; split it when it grows past.**
Gate: `tests/test_file_length.py` (#97) — a static scan of line counts off disk, importing no
application module, so it runs in CI's **lint** job as well as in `run_all.sh`. It names every
offender's file, length and overage in ONE run. The `~` is still doing real work as an instruction
to split, but it is no longer only that: the failure is now the build's, not a reviewer's. The
files that were already over when the gate landed are pinned in its `PINS` at their measured
sizes, and a pin is self-invalidating in BOTH directions — the file growing FURTHER fails
(already over is not a licence), and the file dropping back under the limit fails as an obsolete
pin. That is `test_instruction_budget.py`'s `KNOWN_RESIDUE` shape, reused rather than reinvented.
A standing instruction from the user, named among the four repo-wide
standards by #59 and #67, but ADDED by #67 rather than relocated — it has never appeared in
`CLAUDE.md` in this repo's git history (`git log -S`, back past `854f53e`), while
`docs/architecture_overview.md:928` asserted that it had, which is how the belief survived
unmeasured; as of #67 that sentence is true, which is the fix and not the evidence.

**`app/utils.py` is the Qt side of a seam, and the pure helpers live on the other side**
(`services/paths.py`, Qt-free — `repo_root`, `find_binary_executable`, `find_solver_executables`,
`find_stl3d_binary`, `find_mpi_launcher`, `is_mpi_binary`). `app/utils.py` re-exports the moved
names, so the ~16 Qt-side call sites are untouched. `is_headless` deliberately **stayed** with the
Qt helpers. Two things the gate (`tests/test_qt_free_seam.py`) had to learn the hard way:
- **The check must be a subprocess** — in-process the answer is always "PyQt6 is loaded" once any
  other test imported it.
- **A deferred import is still a dependency.** With the import-time sweep green, `run_pipeline.sh`
  on a PyQt6-less machine still died in stage 2: three call sites did
  `from app.utils import repo_root` *inside a function body*. The gate reads the AST for a moved
  name at **any** nesting depth, and separately refuses PyQt6 in a subprocess and drives the
  writers that failed.

**A new service is assumed Qt-free, so the `services/` sweep is a DENY-list** (`QT_SERVICES`, each
entry carrying its reason); stale entries fail too.

**Scroll-wheel on QSpinBox/QDoubleSpinBox is intentionally disabled** (overridden in `main.py`).

**The user-facing log is a service, not a widget**: say things with `AppController.log()`
(controllers) or `app/services/user_log.py` (views) — never `main_window.log_panel.log(...)`,
which is how 255 reach-throughs accumulated. `LogPanel` is a registered sink; sinks get the RAW
message and classify for themselves, and the durable file mirror happens in the service ONLY (a
second one in the panel writes every line twice). `user_log.log()` attaches the file handler
itself, so a process that never ran the GUI's `main()` still leaves its log on disk. Gated by
`tests/test_user_log_seam.py`. This is a different log from `get_logger(__name__)`, which is
developer diagnostics.

**The solver BC table is DERIVED by a service, not by the panel that shows it**
(`services/solver_bc_table.py`, Qt-free, #90). Everything else in the chain from a meshed patch
to the solver's `.bc.def` already was: `bnd_io.read_bnd_segments` reads the `(segment id, patch
name)` pairs, `bnd_io.default_bc_flag_for_name` mirrors getPGrid's `getBCType` name→flag mapping,
`SolverConfig.bc_definitions` is a plain model field and `services/solver_case.py` writes it for
BOTH hosts — only the rule that USES them was a widget. The same seam as the pipeline stage set
and the IB hand-off.
- **The precedence rule is stated ONCE**, in `bc_flag_for_patch`: an explicit Mesh-Generator
  assignment (`group_bc[name]`) beats the guess from the patch name, and BOTH go through
  `default_bc_flag_for_name` — so an assignment naming a token getPGrid does not know takes the
  same wall fallback instead of quietly reverting to the patch's own name. An empty or missing
  assignment is not an assignment. The name is kept on the row either way, as the grouping label.
- **`default_bc_flag_for_name` keeps ONE caller**, the service; no view may call it. Gated
  statically, because a second copy of the rule is wrong only once it drifts.
- **A name NOTHING can resolve is audible, not refused** (#92). `bnd_io.is_known_bc_name` says
  whether a token was looked up or fell through; `unresolved_patches` pairs that with the flag
  the run really uses, and `unresolved_patch_warnings` builds the ONE line both hosts log —
  naming the patch, the flag (number and label) and the fix. The fallback itself is unchanged:
  refusing to solve because a patch is named something unexpected would be worse than a wall.
  Silent when every patch resolves, which is what makes it mean something when it appears.
  **One line per distinct NAME, carrying its segment ids** — a mesh names several segments the
  same on purpose (the shipped C-grid has four `farfield`), and four identical lines is the
  burial this rule exists to undo. **A caller that knows the flag really in force passes it as
  `in_force`** (the GUI does, from the table): a segment whose flag the user picked by hand is
  ANSWERED, and reporting it would name a flag the table does not carry and would not stop when
  the user did the fix the message names.
  **Named blind spots.** (i) A run with NO `.bnd`, or one with no patches, derives nothing and so
  warns nothing, while `stage_bc_def_companion` copies getPGrid's table with the same silent
  fallback in it — there are no patch names to inspect on that path, so this is recorded, not
  fixed. (ii) The headless route has no `in_force`, because nothing there can override the
  derivation; if a script ever gains a per-patch override, it must pass one.
  `is_known_bc_name` keeps ONE caller, like the flag it qualifies. It grades WARNING through `user_log.classify` — but by the
  KEYWORD heuristic, not by its `[WARNING]` tag: that classifier's level prefix is anchored at the
  start of the line, so every `[Component] [LEVEL]` line in this repo (the dominant shape, ~20 of
  them) falls through to keywords. So the wording must avoid "error" and "failed", which would
  grade it ERROR. Gated by `tests/test_bc_name_unresolved.py`, whose check 2 measures the level
  through the real classifier.
- **The token choice is `bc_token_for_patch`, and only there.** #92 split it out of
  `bc_flag_for_patch` so that "was it resolved?" and "what flag?" cannot answer about different
  tokens; nothing else may re-derive `assigned if assigned else name`.
- `bc_flag_overrides` answers a *different* question from the row builder — which already-built
  rows should ADOPT a changed assignment — and returns only the rows carrying one, so a manual
  tweak on an unassigned row survives. `None` in its names is a row with no name cell, skipped
  without a lookup; `""` is a row whose patch really is unnamed.
Gated by `tests/test_solver_bc_table.py`, whose checks 10 and 11 hold the "no behaviour change"
claim against the pre-#90 inline code rather than against the service itself — and
`tests/test_bc_name_unresolved.py`, whose check 5 does the same for #92 against the pre-#92
`bc_flag_for_patch`, over the same 96 combinations. **Both oracles call the LIVE
`default_bc_flag_for_name`, so both pin the PRECEDENCE and neither pins the MAPPING** — that is
`tests/test_pipeline_bc_from_mesh.py` check 10's job, against getPGrid's own C++.

**User messages go through `app/utils.py`'s graded helpers, never a raw `QMessageBox`** — with
**two recorded exemptions, and no third without a helper**: `views/case_dir_dialog.py` (the
case-dir question, four mutually exclusive dispositions) and `controllers/curve_join_ctrl.py`
(keep / merge). Neither is a yes/no, and both make the headless early-return themselves. A third
multi-way prompt is the point at which `app/utils.py` grows a `choose()` rather than the exemption
list growing again. The graded set:
- `report_error` (failed write, data at risk → Critical), `report_warning` (failed read →
  Warning), `report_info` (a precondition, nothing broke → Information),
  `confirm(..., headless_default=)` (Yes/No).
- `confirm_destructive(..., action_label=, option_label=)` — an irreversible action: a **named**
  button, Cancel as the default, an optional extra tick, and **no `headless_default` at all**,
  because a destructive prompt has no safe default and making it an argument would let an
  unattended path opt into deleting files. Returns `None` when declined and the tick's state
  otherwise.
- All of them no-op or return the default on a headless platform.

**Any new dock widget needs `setObjectName()`**, or `QMainWindow.restoreState()` silently skips it.

**Signal guards: never write a raw `blockSignals(True)`/`blockSignals(False)` pair** — an exception
between them leaves the widget permanently unable to emit. Use `with block_signals(w1, w2, ...)`
(`app/utils.py`). Likewise, never assign `_is_populating`: use `with controller.populating():`, a
re-entrant depth counter (a bare bool let a nested populate clear the outer guard).
`tests/test_signal_guards.py` statically fails the build on either.

**Error handling: never a BROAD `except` that discards.** The rule is about the HANDLER, not about
one keyword (#118). A catch wide enough to swallow an error nobody predicted — `except Exception:`,
`except BaseException:`, a bare `except:`, or a tuple holding either — whose WHOLE body is `pass`,
`continue`, `break`, `return`, `return <fallback>` or a bare string literal neither records the
failure nor re-raises it, and all six spell the same defect. Matching only `pass` is the back door
#117 went through: a refactor changed what REACHED a handler spelled `continue`, a correct skip
became a swallowed diagnostic, and every gate stayed green. A NARROW handler is a different thing
and is deliberately out of scope — `except ValueError: continue` inside a line parser is the right
idiom, this tree holds over a hundred such, and a gate that flagged them would need an allowlist
longer than the rule.

Use `services/logging_setup.py::get_logger(__name__)` and log at `debug(..., exc_info=True)` for a
step allowed to fail, or `warning` when the failure silently degrades what the user asked for.
`HYBMESH_LOG_LEVEL=DEBUG` surfaces the debug tier. Those two tiers settle most sites on their own —
a transform handle that still draws at a fallback length loses nothing the user asked for, so it is
`debug` (`views/canvas_transform_mixin.py`). FOUR shapes cover the ones they do not, each visible
in the tree:
- **A probe whose negative answer is legitimate still records, at `debug`.** "Not installed" and
  "installed and broken" arrive at the caller identically, and only the exception separates them
  (`services/env_setup.py`, the gmsh library probe).
- **A handler that RECOVERS by another route records at `debug`**: nothing is lost, so what is
  worth knowing is that the fast path failed at all — an O(n) fallback that is always taken is a
  silent slow path (`services/geometry_formula.py::_eval_formula_array`, whose vectorised
  evaluation falls back to per-sample; the scalar `_eval_formula` beside it is the shape below, not
  this one).
- **A site called PER SAMPLE or per repaint is `debug` even when the outcome matters**, where the
  same failure is already visible to the user as it happens. `_eval_formula` runs once per point of
  a curve: a bad expression would write one `warning` per point, and the user is looking at the
  curve not drawing while they type. Call rate is a real criterion, not an excuse — it does NOT
  apply where the failure is invisible until someone asks why a number is wrong.
- **Where one failure can mean "not there yet" or "there and unreadable", RESOLVE first and the
  question answers itself.** `readable_geom_path` returns `""` for the first, so there is nothing
  to record; everything that reaches the open is the second, and the reader `warning`s it
  (`views/panels/mesh_sizing_mixin.py::_hint_points`, #117's distinction). Grading on a raw
  `os.path.exists` instead LOOKS like the same rule and is not: the stored entry is repo-relative,
  so from another cwd a geometry that is really there grades as one the user has not made yet.

`tests/test_silent_exceptions.py` check 2 walks every `.py` file under `tools/PreProcessor/gui/`
with `ast` — the GUI ROOT, not just `app/`, so `main.py` is inside it — and fails the build if a
new undocumented silent broad handler appears. `ALLOWED_SILENT` names the files that may hold one,
each handler must still explain itself in a comment at the site, and an entry whose file stops
holding one FAILS as obsolete rather than quietly outliving its reason.

---

**The GUI module map** (#77) lives behind the widest glob because it is a map rather than a rule:
every GUI reader is served by it, and the one hard rule inside it — every worker `cancel()` routes
through `stop_process` / `stop_process_async`, never a bare `terminate()` — binds every worker.
Layered PyQt6 application, `tools/PreProcessor/gui/app/`:

- **`controller.py`**: top-level orchestrator; command pattern for undo/redo, delegates to specialized controllers
- **`controllers/`**: business logic split by concern — `segment_ctrl.py` (CRUD, properties), `session_ctrl.py` (save/load), `session_io_ctrl.py` (`.hws` workspace read/write + `WORKSPACE_FORMAT_VERSION` migration), `project_state_ctrl.py` (the workspace's `project` section: Mesh/Solver/IB config + baseline-snapshot dirty detection), `backend_ctrl.py` (runs `surface_resampler` in QThread), `mesh_gen_ctrl.py` (runs `HybMesh2D` in QThread), `mesh_config_io_ctrl.py` (the mesher's own `.dat`, read and written through a file dialog), `lifecycle_ctrl.py` (autosave, crash recovery, bounded worker shutdown), `curve_ctrl.py`, `transform_ctrl.py`
- **`models/`**: `segment.py` (`type`, `strategy`, `parameters` incl. `spacing`, curve fields, plus the two per-segment facts the MESH stage edits — `bc` and `grow_bl`; serialized via `to_dict()`/`from_dict()`, the ONE serialiser behind the resample config, the workspace and the pipeline script), `project.py`, `mesh_config.py` (+ `mesh_config_keys.py`, `mesh_config_io.py`, `mesh_output_names.py`, `mesh_config_geoms.py`), `session.py`, `vtk_mesh.py`, `result_data.py` / `tecplot_index.py` / `result_series.py`. Auto-split is computed in the GUI (producing explicit `split_indices`); the per-segment `auto_split`/`split_threshold` keys are read by `src/cli.cpp` for hand-written configs but are not emitted by the GUI. Exported JSON carries `format_version` (`CONFIG_FORMAT_VERSION`).
- **`views/`**: `canvas.py` (pyqtgraph interactive geometry canvas, dark theme), `mesh_canvas.py`, `main_window.py` (tab layout), `sidebar.py` (segment property editor), `panels/` (tab panels per workflow)
- **`commands/`**: `segment_cmds.py` (`UpdateSegmentStateCmd` snapshots full state dict), `split_cmds.py`, `vertex_cmds.py`, `config_cmds.py` (`UpdateProjectStateCmd`)
- **`workers/`**: `backend_run.py`, `mesh_gen_run.py` (QThread wrappers for CLI
  subprocesses), `proc_util.py` (shared `popen_kwargs()` with `start_new_session`, plus
  `stop_process`/`stop_process_async` SIGTERM→SIGKILL escalation over the child's process
  group — every worker `cancel()` must route through these, never a bare `terminate()`)

## Named blind spots

- **`tests/test_silent_exceptions.py` check 2 reads CONTROL FLOW, not intent.** A broad handler
  whose body does anything else — `self._x = None`, a UI reset — is not reached and can discard
  just as completely; `_reset_project_baseline` was fixed by hand rather than by widening the
  scan, because deciding whether a body "records the failure" means recognising logging by name,
  which is the fragile version of this gate. Two smaller ones beside it: the walk is scoped to the
  GUI tree, which is what the standard binds (`tools/scripts/` and the test suite are outside it);
  and a broad handler aliased past the name match (`Err = Exception`, then `except Err:`) is not
  recognised — nothing in this tree does it, and a name match is what keeps the scan readable.
- **`tests/test_file_length.py`'s pin is a CEILING, not a measurement**: a pinned file that
  shrinks while STAYING over the limit passes, and may grow back to its pin without the gate
  speaking. Deliberate — #102 and #103 split two of these files rather than living inside their
  pins (both are done: `mesh_gen_ctrl.py` and `pipeline_runner.py` LEFT the list rather than
  shrinking within it, the latter by moving its case-staging collector into
  `services/pipeline_case_sources.py`), and an
  exact-match pin would go red on every intermediate commit of the work it exists to provoke. The hole is bounded by
  the pin, which never rises. Two smaller ones beside it: the gate counts LINES, so a 400-line file
  can be far worse than a 510-line one and nothing here can tell; and it reaches `.py` files only.
  Re-measured 2026-09-23: 272 GUI `.py` files, of which 5 exceed 500 lines —
  `app/models/pipeline_config.py` 524, `app/controllers/session_io_ctrl.py` 508,
  `app/services/case_run_note.py` 508, `app/models/solver_config.py` 501,
  `app/services/result_legs.py` 501. Every figure in that sentence is DERIVED, never remembered —
  the count, the total, the standard and each offender by name and size — off
  `test_file_length.py`'s own walk, so `--sync` rewrites this list and a stale one goes red. Two
  same-size offenders are ordered by NAME, so a swap here goes red too (#101). What the ungated
  years cost is MEASURED (2026-09-09, one walk of each GUI `.py` file's own history comparing
  every blob with its predecessor): **44 commits
  across 35 files** took a GUI file past 500 lines, and **four of them landed in the six days after
  #67 wrote the standard down** — `98003f1` (#85) took `app/models/mesh_config.py` 499 -> 505,
  `306d6a1` (#91) took `app/services/pipeline_runner.py` 490 -> 537 by a 40-line function, and the #47
  merge `8bdc36a` did it twice in one commit (`app/controllers/mesh_gen_ctrl.py` 490 -> 512,
  `app/services/pipeline_runner.py` 498 -> 506). A review caught three of the four; nothing caught
  `98003f1`, whose own ticket was about something else, and the same merge that broke two files
  split `app/models/mesh_config.py` back to 426 for exactly this budget. The count decays on every commit and
  is a dated fact, not a gated one — `test_instruction_budget.py` blind spot (g) says why a
  git-history figure is left out of `--sync`.
- **`tests/test_gui_cpp_config_parity.py` cannot see a spec's `key=` being removed**: both sides
  then agree with the parameter gone from each, while the writer keeps emitting the line — the
  writer's f-strings are independent of the map. Why: `docs/design_notes/gui.md`, "removing a spec's `key=` left both sides agreeing".
- **`solver_bc_table` looks a `group_bc` assignment up by the `.bnd` PATCH NAME**, while a
  `group_bc` key is the per-segment grouping LABEL and a patch name is the physical BC TYPE the
  mesher resolved that label to (`src/Mesh.cpp`, `Config::resolveGroupBc`; the same two namespaces
  `.claude/rules/gui-handoff.md` records the audit confusing once). The precedence rule therefore
  only fires where a label happens to be named after its own type. #90 PRESERVED that, being a
  prefactor with no behaviour change; it is not an endorsement of it.
- **`tests/test_qt_free_seam.py` records one pre-existing defect the sweep surfaced and did *not*
  fix**, in `CANNOT_IMPORT_STANDALONE`: `services/index_helpers.py` cannot be imported first, a
  cycle enabled by eager re-exports in two `__init__.py` files.
