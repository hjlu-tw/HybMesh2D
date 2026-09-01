# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Where the reasoning lives.** This file and the on-demand rule files in `.claude/rules/`
carry the RULES (see the tripwire table below). The long-form rationale behind
them — the measurements, the dated acceptance runs, the injections, the reversals and the
named blind spots — was extracted verbatim on 2026-08-28 into `docs/design_notes/`:

| File | Covers |
|------|--------|
| `docs/design_notes/mesher.md` | Configuration (`.dat`, BL params, MESH_MODE, multi-block, quality, BC binding) + Core C++ |
| `docs/design_notes/gui.md` | The whole PreProcessor GUI section |
| `docs/design_notes/pipeline.md` | Full pipeline, solver case, archive/clean/restart, bDecompose, STL3d |

Nothing was rewritten in the move. **Read the matching design note before overruling a rule
here**: most of these rules were bought by shipping the opposite first, and the rule alone
does not carry the argument for itself. When a rule changes, update BOTH — the rule here, and
its entry there.

**What that split cost, and what it did not.** There is no truncation threshold anywhere near
this file's size: Claude Code loads a `CLAUDE.md` of up to **4 MiB in full** and **skips** a larger
one — no longer a figure carried in from documentation, but measured on this build in #61, where
the loader's own `4194304`-byte limit and its `skipping <path>: … exceeds <N> byte limit` line were
observed. The cost is therefore not truncation but **always-loaded context** — **65,242
characters (65,631 bytes, 2026-09-02, after #65 moved the GUI canvas and editing rules out to
`.claude/rules/gui-canvas-edit.md`) ≈ 16k tokens**, paid by every session before it reads a line
of source. That number decays on the next commit, so re-measure before quoting it; what stops it
decaying *silently* is `tools/PreProcessor/tests/test_instruction_budget.py`, whose root budget is
set to exactly this size. **The unit is CHARACTERS**: the budget #59 states is in characters while
`wc -c` reports bytes, and the two differ by 389 today because of the CJK in this repo's own
prose, so both numbers are given rather than one silently replacing the other. The 4 MiB loader
limit above is in BYTES; a character budget is conservative against it either way, since a
character is never fewer than one byte. The token count is characters/4 and is named rather than
implied. `MEMORY.md`'s far smaller budget (24.4KB, measured 2026-08-27) is a different loader's
and is not this file's.

> **Superseded claim, KEPT AS A SPECIMEN (#60).** `3a2e096` wrote "passed the 150k-char context
> limit" into this block and into all three design notes: `.agents/skills/ask-matt`'s **smart zone,
> ~150k _tokens_** (`SKILL.md:32`, `PHASE-BOUNDARIES.md:21`) — a reasoning-quality heuristic, not a
> limit — restated as a character hard limit that nothing ever measured. Kept rather than deleted,
> like #43's iteration-count reversal: a number carried in from a neighbouring document is not
> evidence until something here re-derives it.

## Important: read the area's rule file BEFORE touching that area

The domain rules live in `.claude/rules/*.md`, each declaring a `paths:` glob list, and are loaded
**on demand** — so a session changing one mesher file does not pay for the GUI's rules, and a
session editing a GUI file does not pay for the mesher's. Three layers, one question each: this
file = **does the rule exist**; `.claude/rules/*.md` = **what is the rule**; `docs/design_notes/`
= **why, and what was measured**. These three are written for agents; humans start at `README.md`,
`docs/architecture_overview.md` and `docs/design_notes/`.

<!-- TRIPWIRE TABLE: the rows below are parsed by tools/PreProcessor/tests/test_instruction_budget.py.
     Keep this marker directly above the table; the gate fails without it rather than falling back to
     scanning every table in this file, which would let a mention anywhere satisfy the check. -->

| Area | Read this rule file first | Before touching |
|------|---------------------------|-----------------|
| Mesher — configuration (`.dat`, BL params, `MESH_MODE`, multi-block, quality, BC binding) + core C++ | `.claude/rules/mesher.md` | `src/**`, `include/**`, `config/**`, `tests/cpp/**` |
| Full pipeline and solver case (case directory, archive, clean, restart point, bDecompose, STL3d, the immersed-boundary hand-off, the pipeline schema and stage set) | `.claude/rules/pipeline-case.md` | the case / solver-case / restart / pipeline / STL3d / IB / contour services, `models/pipeline_config.py`, `run_pipeline.py` — the exact globs are that file's own `paths:` list, and its header names the controllers, workers and views it also governs from outside them. NOT there yet: the portable case export (`services/case_export*.py`, `case_workspace.py`), whose rules are still in this file. |
| GUI panel configuration (the field-spec tables, the one-directional panel↔model data flow, the derived `.dat` key map, the Edit-BL dialog's grouping, length units and `Linf`, the physical-length spin box) | `.claude/rules/gui-panels-config.md` | `views/panels/**`, `views/clean_double_spin_box.py`, the field-spec / units / config-ownership services, `models/mesh_config*` — the exact globs are that file's own `paths:` list, and its header names the controllers it also governs from outside them. Two of its globs are WIDER than the area: a results panel's rules are still in this file, `views/panels/restart_chooser.py`'s are in `pipeline-case.md`, and `MeshConfig.output_base`'s Output-`.*` rule is still in this file. |
| GUI canvas and editing (the owner of the edge being edited, the outline re-fit, global undo, duplicate/transform closure, the one-polyline discrete geometry, pop-up stacking) | `.claude/rules/gui-canvas-edit.md` | `views/canvas*`, `services/edge_edit*`, `services/shape_refit*`, `commands/**`, `app/popup_stack.py` — the exact globs are that file's own `paths:` list, and its header names the controllers, views and dialogs it also governs from outside them — pop-up stacking reaches every module that shows a modeless pop-up, none of them under a glob of that file, and the header carries the count so this row cannot disagree with it. One glob is WIDER than the area: `commands/config_cmds.py`'s other half is in `gui-panels-config.md`. |

**The table is load bearing, not a convenience.** Measured on Claude Code 2.1.250 (#61): a rule
file arrives with `load_reason: path_glob_match` when a matching file is **read**, and does NOT
arrive for an `Edit` without a prior `Read`, nor for a `Write` creating a new file — both of those
went through with the rule unloaded. The glob alone therefore cannot make "I did not know there was
a rule" unreachable; this table is what does. **Read the row's rule file before editing or creating
a file in its area.**

**The move is staged (#59), so this table is deliberately incomplete.** Every area with no row
above still has its rules in this file. `tools/PreProcessor/tests/test_instruction_budget.py` gates
the arrangement: a per-file size budget (the root file and each rule file measured against their
own, never a total, so moving text between rule files is not a legal evasion), the table against
the rule files in **both** directions, and the existence of every gate test a rule file names.

## Important: Git and Commit Policy

**Commit freely; everything else waits for an explicit instruction.** `add` and
`commit` are yours to run when the work warrants one. `push`, `checkout`,
`reset`, `rebase`, `merge`, branch creation or deletion all still wait to be
asked for. Read-only inspection (`git status`, `git diff`, `git log`) is free:
you need it to do the job below.

**What changed (2026-08-26, USER-REQUESTED): committing no longer needs
permission.** The rule before this made every commit a round trip — propose a
message, wait to be told yes — which was the same stall the 2026-08-14 change
had already tried to remove by making the assistant raise the subject at all.

**Commits land on the current branch, `main` included.** Branch creation is one
of the commands that still waits, so there is no branching around that: if a
piece of work should not go onto the branch that is checked out, say so and it
waits.

**Commit** once the working tree holds a *coherent, finished* unit of work — a
feature that runs, a bug fixed with its test, a refactor that builds. Say what
you committed and the message you used; do not ask first. Signals that one has
accumulated, any of which is enough:

- a task the user framed as one job is done and verified;
- roughly **200+ changed lines** or **5+ touched files** since the last commit;
- the next step would start an unrelated concern (mixing them makes a commit
  that cannot be reverted cleanly);
- something risky comes next (a large refactor, a dependency bump, a migration)
  — a checkpoint before it is worth more than one after.

**Ask about a code review** when the uncommitted-or-unpushed body of work grows
past what a single commit covers — about **3+ commits' worth**, **500+ changed
lines**, or a whole stage of a feature landing. Offer `/code-review` (Standards
+ Spec) and let the user decline. Prefer asking *before* a branch is pushed or a
PR opened, since that is when a review is cheapest to act on.

These numbers are defaults, not gates — a 30-line change to `BoundaryLayer.cpp`
can deserve both a commit boundary and a review, and 400 lines of new test data
can deserve neither. Judge by whether a reviewer would want a boundary there.

## Important: Dispatch subagents ONE AT A TIME

**Never fan out subagents in parallel** — not even for work that is genuinely
independent, and not even when parallel would obviously be faster. Dispatch one,
wait for it, **write its result into the destination file**, and only then
dispatch the next. This overrides the default habit of parallelising independent
work, and overrides the tool documentation's advice to batch several Agent calls
into one message.

The reason is the failure mode, not the speed: a parallel fan-out lands several
agents' output in the main context at once, so hitting the token ceiling while
collecting them loses **every round's work at once**. Serial execution caps the
worst case at the round in flight.

Two rules that make serial rounds affordable: give each subagent an explicit
scope boundary plus "this area is already covered, do not re-read it", and ask
it to return a **finished section ready to paste** (with `file:line` citations
and a length cap) rather than raw notes. If a subagent dies to an API error,
resume that same agent with `SendMessage` — it recovers from its own transcript,
so nothing is re-investigated.

Worked example: `docs/architecture_overview.md` §3–§4 (four serial rounds,
955 lines, one round resumed after an API error with zero rework).

## Project Overview

HybMesh2D is a C++ tool for generating 2D hybrid meshes (boundary layer quads + far-field triangles) for CFD. It includes a Python GUI for pre-processing geometry via resampling and segmentation.

## Build & Run

**Compile both binaries:**
```bash
./build.sh
```
Outputs: `./build/HybMesh2D` and `./build/surface_resampler`

**Run the C++ unit tests:**
```bash
cd build && ctest --output-on-failure
```
Invoked by `cd`-ing in rather than with `--test-dir`, which needs CMake >= 3.20 while this project declares 3.10 — with the flag an older ctest rejects the argument, the listing comes back empty and `run_all.sh` contributes zero C++ tests while still reporting success. Registered by `tests/cpp/CMakeLists.txt` and built by default (`HYBMESH_BUILD_TESTS=ON` — off by default would mean the ctest hook silently skips for almost everyone, and a seam nobody exercises is theoretical). `bash tools/PreProcessor/tests/run_all.sh` runs them too, counted into its total, self-skipping when there is no build tree — so that stays the ONE command a developer runs.

**Run main mesh generator:**
```bash
./run.sh -conf config/Background_para.dat -geom examples/geometries/naca0012.dat
```
`run.sh` sets the Gmsh dylib path (`DYLD_LIBRARY_PATH`) before invoking `./build/HybMesh2D`.

**Run the multi-block (topology-driven) path:**
```bash
./run.sh -conf config/multiblock_square.dat      # -> examples/topology/square_block.json
```
```bash
./run.sh -conf config/multiblock_cavity.dat    # -> examples/topology/cavity_block.json
```
```bash
./run.sh -conf config/multiblock_hgrid.dat     # -> examples/topology/hgrid_blocks.json
```
`MESH_MODE 1` fills a DECLARED block topology with structured quads and splits them
to triangles; it uses Gmsh nowhere. The second case attaches its corners to a geometry by
arc length and reads each wall's boundary condition off that geometry's source segments.
The third is a four-block H-grid: four seeded counts propagate to twelve edges, four
interior lines are welded by node identity, and one block is turned a quarter turn. The
rules for all three — "The multi-block path is ONE pure entry point", "Boundary conditions
are DECLARED", "Blocks are welded TOPOLOGICALLY" — are in `.claude/rules/mesher.md`.

**Run preprocessor GUI:**
```bash
python3 tools/PreProcessor/gui/main.py [geometry.dat | case.hws | pipeline.json | @list.txt ...]
```
Positional arguments are recognised by **content**, not extension — see "A path is not
a kind" under Architecture. One project file (`.hws` / pipeline script) per launch,
plus any number of geometry files; `--run` then executes Run All.

**Run preprocessor CLI (after GUI exports a JSON config):**
```bash
./run_preprocessor.sh config/your_config.json
# or directly:
./build/surface_resampler config/your_config.json
```

**Run a batch of pipeline scripts (headless):**
```bash
./run_batch.sh case_a.json case_b.hws --no-solver     # or @manifest.txt (one path per line)
```
In the GUI the same queue is **Pipeline ▸ Batch Queue…** — a modeless dialog with per-case
status. Its **Cancel stops the case already running**, not just the queue: `run_batch`'s
`should_stop()` only fires between cases, so `pipeline_runner` threads an `on_process`
callback down to every stage subprocess and the worker kills the live one via
`proc_util.stop_process_async`. Case-name collisions (which would make two cases overwrite
each other's mesh) are shown as soon as scripts are queued, not at run time.

**Run full pipeline (CAD → mesh → solver → contour) headless from one JSON script:**
```bash
./run_pipeline.sh config/pipeline/naca_demo.json           # -> results/pipeline/*.png
./run_pipeline.sh config/pipeline/naca_demo.json --no-solver   # stop after meshing
```
`run_pipeline.sh` sets `DYLD_LIBRARY_PATH` (like `run.sh`) and calls `tools/PreProcessor/run_pipeline.py`. In the GUI, the same end-to-end run is the **Run All** button (top-right, all modes) / **Pipeline** menu (Run / Load / Save script). The rules for the whole chain — case directory, archive, clean, restart, export, bDecompose, STL3d and the immersed-boundary hand-off — are in `.claude/rules/pipeline-case.md`.

**Visualize .dat files:**
```bash
python3 tools/scripts/visualize_dat.py <path_to_dat_file> [--config <json_config>] [--quality]
```
`--quality` renders a heatmap of expansion ratio: green < 1.05, orange 1.05–1.2, red > 1.2.

**Lint (what CI enforces):**
```bash
cd tools/PreProcessor/gui && ruff check .            # config: ruff.toml
cd tools/PreProcessor/gui && ruff check --config ruff.toml ../tests
```
`ruff.toml` enforces only real-defect rules (`E9`, `F`); style rules are off with the reason stated in the file. Fix violations before adding a rule to `select` — a permanently-red gate is worse than none. CI (`.github/workflows/gui-tests.yml`) has three jobs: **lint**, **build C++ with `-Werror`** (which then runs `ctest` — the **test** job downloads two binaries and has no build tree, so there is no `CTestTestfile.cmake` for ctest to read there, and a failing unit test is a build-gate concern anyway; the loader path comes from `tools/scripts/gmsh_lib_dir.sh` rather than a hardcoded pip prefix, because the baked rpath is only reliably right on the machine that built the binary), and **test** (which `needs: build`, so the binary-dependent tests actually run instead of self-skipping, plus an end-to-end `run_pipeline.sh`).

**GUI↔C++ config parity** is gated by `tests/test_gui_cpp_config_parity.py`, and it
compares **key, TYPE and DEFAULT, in both directions** — not just key presence, which
is blind to the two divergences that produce a wrong mesh instead of an error. Both
sides are read as declarations: the C++ from `include/BLParams.hpp`'s rows plus
`Config.hpp`'s `key == "..."` branch → member → struct initialiser (a key that stops
resolving fails check 0, so a blind extractor cannot turn the comparison into a no-op),
the GUI from the derived key map + `field_spec.model_types` + `MeshConfig()` — whose own
rules moved to `.claude/rules/gui-panels-config.md` in #64. New
C++-only keys must be justified in `KNOWN_CPP_ONLY`; structural multi-token lines in
`_STRUCTURAL`. Two things about the divergence lists are load bearing:
- **`PINNED_TYPE_DIVERGENCE` is empty and must stay empty.** A type mismatch means one
  side cannot represent what the other stores, so there is no intended version of it.
  The gate found one — `BL_AUTO_FAN_NODES` — and it was FIXED, not pinned.
- **`PINNED_DEFAULT_DIVERGENCE` pins BOTH values and a reason**, because the two
  defaults answer *different questions*: the C++ one is what an unspecified key in a
  hand-written `.dat` means (neutral and safe), the GUI one is what a fresh editing
  session suggests before the user changes it. Forcing them equal would be wrong in
  both directions — it would make a new GUI case default to an all-`wall` box with no
  inlet, or make the mesher stop writing a VTK for a CLI user who asked for nothing.
  Measured: 8 of the 49 shared keys diverge, and all 8 are correct. Pinning both values
  means a *change* to either side fails the gate again, so an entry cannot absorb a new
  drift. And check 6 makes the pinning honest by machine-checking its precondition —
  the GUI must write that key **unconditionally**, so the mesher's differing default is
  never the one in force for a GUI run. That is not a formality: 7 of the writer's keys
  really are conditional.

**Example backend test configs:**
- `tools/PreProcessor/config/test_triangle_backend.json` — vertex snap verification
- `tools/PreProcessor/config/test_auto_split.json` — feature split verification

## Mesh Generation Pipeline

```
Input: .dat geometry file (space-separated x y coordinates per line)
  ↓
[Optional] PreProcessor (GUI or CLI)
  - Resamples surface points with chosen spacing strategy
  - Preserves predefined shape vertices (Triangle/Quad/Polygon vertex snap)
  - Auto-splits at sharp corners (direction change > threshold)
  - Output: resampled .dat geometry
  ↓
BoundaryLayer.cpp — grows structured quad layers outward from geometry
  - Computes outward normals per node
  - Fans at convex corners (angle > BL_FAN_ANGLE_THRESHOLD)
  - Merges or blends at concave corners (configurable method)
  - Transition layers with separate growth rate
  ↓
Mesh.cpp / Gmsh SDK — fills far-field with unstructured triangles
  - BL outer edge becomes inner boundary of Gmsh domain
  - Starting mesh size derived from last BL layer thickness
  ↓
Collision detection → Laplacian smoothing (BFS region around frozen nodes)
  ↓
Export: VTK (.vtk) and/or STAR-CD (.vrt / .cel / .bnd)
```

## Architecture

### PreProcessor GUI (`tools/PreProcessor/gui/app/`)
Layered PyQt6 application.

> **Full rationale for this whole section — measurements, dated user reports,
> injections, named blind spots — is `docs/design_notes/gui.md`.** A rule here is the
> conclusion; that file carries the evidence and the failure it was bought with.

- **`controller.py`**: top-level orchestrator; command pattern for undo/redo, delegates to specialized controllers
- **`controllers/`**: business logic split by concern — `segment_ctrl.py` (CRUD, properties), `session_ctrl.py` (save/load), `session_io_ctrl.py` (`.hws` workspace read/write + `WORKSPACE_FORMAT_VERSION` migration), `project_state_ctrl.py` (the workspace's `project` section: Mesh/Solver/IB config + baseline-snapshot dirty detection), `backend_ctrl.py` (runs `surface_resampler` in QThread), `mesh_gen_ctrl.py` (runs `HybMesh2D` in QThread), `lifecycle_ctrl.py` (autosave, crash recovery, bounded worker shutdown), `curve_ctrl.py`, `transform_ctrl.py`
- **`models/`**: `segment.py` (`type`, `strategy`, `parameters` incl. `spacing`, curve fields, plus the two per-segment facts the MESH stage edits — `bc` and `grow_bl`; serialized via `to_dict()`/`from_dict()`, the ONE serialiser behind the resample config, the workspace and the pipeline script), `project.py`, `mesh_config.py` (+ `mesh_config_keys.py`, `mesh_config_io.py`, `mesh_output_names.py`), `session.py`, `vtk_mesh.py`, `result_data.py` / `tecplot_index.py` / `result_series.py`. Auto-split is computed in the GUI (producing explicit `split_indices`); the per-segment `auto_split`/`split_threshold` keys are read by `src/cli.cpp` for hand-written configs but are not emitted by the GUI. Exported JSON carries `format_version` (`CONFIG_FORMAT_VERSION`).
- **`views/`**: `canvas.py` (pyqtgraph interactive geometry canvas, dark theme), `mesh_canvas.py`, `main_window.py` (tab layout), `sidebar.py` (segment property editor), `panels/` (tab panels per workflow)
- **`commands/`**: `segment_cmds.py` (`UpdateSegmentStateCmd` snapshots full state dict), `split_cmds.py`, `vertex_cmds.py`, `config_cmds.py` (`UpdateProjectStateCmd`)
- **`workers/`**: `backend_run.py`, `mesh_gen_run.py` (QThread wrappers for CLI
  subprocesses), `proc_util.py` (shared `popen_kwargs()` with `start_new_session`, plus
  `stop_process`/`stop_process_async` SIGTERM→SIGKILL escalation over the child's process
  group — every worker `cancel()` must route through these, never a bare `terminate()`)

**Subprocess environment**: `services/env_setup.py::mesher_env()` resolves the libgmsh
directory (override: `HYBMESH_GMSH_LIB_DIR`) and must be passed as `env=` when launching
`HybMesh2D`/`surface_resampler`. Inheriting it from a shell wrapper does **not** work —
macOS SIP strips every `DYLD_*` variable when a protected `python3` starts.
`tools/scripts/gmsh_lib_dir.sh` is the shell-side equivalent. **Where Gmsh actually is has
ONE answer: `tools/scripts/gmsh_sdk_dirs.py`** — the shell helper and `CMakeLists.txt` both
resolve through it by asking the installed wheel. The CMake side used to carry a fixed HINTS
list naming one developer's macOS pip prefix: **CI installed gmsh, failed at configure with
"Gmsh SDK not found", and because the test job is `needs: build` the entire regression suite
was SKIPPED rather than run — the workflow had never once been green.** A hardcoded absolute
path in a discovery hint is worth treating as a defect on sight. The second half was the
LIBRARY name: the Linux wheel ships `lib/libgmsh.so.4.15` with no unversioned symlink, so
`find_library`'s NAMES matched nothing there while macOS's `libgmsh.4.15.dylib` matched. The
resolver therefore reports `LIBFILE=` (the file it globbed) and CMake falls back to it. The
workflow first went green 2026-08-17 (`4254c5d`), covering **69 Python tests + `ctest` 2/2 +
the end-to-end `run_pipeline.sh`, none of which had ever executed in CI before**; four
unrelated environment defects and one flaky runner stood in the way, and not one was a defect
in the code under test. **A workflow's *history* is the only evidence it gates anything.**

**`app/utils.py` is the Qt side of a seam, and the pure helpers live on the other side**
(`services/paths.py`, Qt-free — `repo_root`, `find_binary_executable`,
`find_solver_executables`, `find_stl3d_binary`, `find_mpi_launcher`, `is_mpi_binary`).
`app/utils.py` re-exports the moved names, so the ~16 Qt-side call sites are untouched.
`is_headless` deliberately **stayed** with the Qt helpers. Two things the gate
(`tests/test_qt_free_seam.py`) had to learn the hard way:
- **The check must be a subprocess** — in-process the answer is always "PyQt6 is loaded"
  once any other test imported it.
- **A deferred import is still a dependency.** With the import-time sweep green,
  `run_pipeline.sh` on a PyQt6-less machine still died in stage 2: three call sites did
  `from app.utils import repo_root` *inside a function body*. The gate reads the AST for a
  moved name at **any** nesting depth, and separately refuses PyQt6 in a subprocess and
  drives the writers that failed.
The `services/` sweep is a **deny**-list (`QT_SERVICES`, each entry carrying its reason);
stale entries fail too. One pre-existing defect the sweep surfaced and did *not* fix is
recorded in `CANNOT_IMPORT_STANDALONE`: `services/index_helpers.py` cannot be imported first
(a cycle enabled by eager re-exports in two `__init__.py` files).

Scroll-wheel on QSpinBox/QDoubleSpinBox is intentionally disabled (overridden in `main.py`).

**The user-facing log is a service, not a widget**: say things with `AppController.log()`
(controllers) or `app/services/user_log.py` (views) — never `main_window.log_panel.log(...)`,
which is how 255 reach-throughs accumulated. `LogPanel` is a registered sink; sinks get the
RAW message and classify for themselves, and the durable file mirror happens in the service
ONLY (a second one in the panel writes every line twice). `user_log.log()` attaches the file
handler itself, so a process that never ran the GUI's `main()` still leaves its log on disk.
Gated by `tests/test_user_log_seam.py`. This is a different log from `get_logger(__name__)`,
which is developer diagnostics.

**User messages**: use `app/utils.py`'s graded helpers, never a raw `QMessageBox` — with
**two recorded exemptions, and no third without a helper**: `views/case_dir_dialog.py` (the
case-dir question, four mutually exclusive dispositions) and `controllers/curve_join_ctrl.py`
(keep / merge). Neither is a yes/no, and both make the headless early-return themselves. The
graded set is `report_error` (failed write, data at risk → Critical), `report_warning`
(failed read → Warning), `report_info` (a precondition, nothing broke → Information),
`confirm(..., headless_default=)` (Yes/No), and `confirm_destructive(..., action_label=,
option_label=)` (an irreversible action: a **named** button, Cancel as the default, an
optional extra tick, and **no `headless_default` at all** — a destructive prompt has no safe
default, and making it an argument would let an unattended path opt into deleting files; it
returns `None` when declined and the tick's state otherwise). A third multi-way prompt is the
point at which `app/utils.py` grows a `choose()` rather than the exemption list growing again.
All of them no-op or return the default on a headless platform. Any new dock widget needs
`setObjectName()`, or `QMainWindow.restoreState()` silently skips it.

**Window layout** is persisted by `app/services/ui_state.py` — **window geometry and dock state,
and nothing else** — namespaced by `LAYOUT_VERSION` (now 2; bump it when the layout changes so
stale state is ignored rather than restored). It never touches `QSettings` when headless. **The
active stage and the sidebar sections are deliberately NOT persisted, and that is a reversal, not
an omission** (#27, USER-REQUESTED): the user weighed resume-where-you-stopped against landing
somewhere unpredictable with no way to reset it, and chose predictability. Every launch starts on
**CAD** with **every** sidebar section collapsed, both from defaults already in the code
(`mode_combo` index 0; `CollapsibleSection`'s `start_collapsed=True`, which no call site
overrides). The version bump also orphans saved geometry, dock state and *dialog* accordion flags,
accepted in the issue; what it buys is that no v1 key can come back as a live value.
`restore_active_stage` and the private `_sections` walker are **gone**, save half with restore half.
**Do not reinstate the convenience as a bug fix** — `tests/test_ui_state_and_dialogs.py` checks
1/2/4 are the **inverted** versions of the ones that pinned the old behaviour. A **dialog's**
accordion is a separate, still-wanted feature with an untouched code path
(`save/restore_section_states(scope, sections)`, which never walked `sidebar_stack`).

**"⟳ Restart" closes THIS window first and spawns only if the close happened**
(`services/gui_restart.py`, Qt-free — `restart_command` / `preflight` / `launch`;
`lifecycle_ctrl.restart_gui`; the button sits beside `Run All` in the persistent tab row). #28,
USER-REQUESTED. Four rules:
- **The order IS the feature** — spawning first and *then* asking "discard unsaved changes?" leaves
  **two** GUIs running when the answer is No.
- **The outcome comes from `close()`'s return value, not from `isVisible()`.** Measured offscreen:
  a *cancelled* close on a never-shown window reports `isVisible() == False` / `isHidden() == True`,
  identical to a successful one, while `close()` returns False exactly when the event was ignored.
  The issue's own text suggests `isVisible()`; it would have made the gate pass for the wrong reason.
- **There is no second copy of the unsaved-work prompt** — the close routes through
  `MainWindow.closeEvent` → `handle_close_event`, which already covers modified sessions *and* a
  dirty Mesh/Solver/IB config, saves the layout, joins every worker, and removes the autosave file.
- **`proc_util.popen_kwargs()` must NOT be reused here** — it sets `stdout=PIPE`, and with the
  parent gone nobody drains that pipe, so the child stalls once the buffer fills. The restart builds
  its own kwargs (`start_new_session=True`, all three streams `DEVNULL`) and passes **no arguments**.
  The entry point resolves through `paths.repo_root()`, never by counting `..` segments.
`preflight()` exists because of that ordering: a bad interpreter or missing `main.py` must be caught
while there is still a window to report it in (a `Popen` failing after that can only reach
`user_log`'s file mirror). The button's **caption is a measurement living in the gate rather than a
comment** — at the 900px minimum "⟳ Restart" leaves 31px of slack in the tightest stage and
"⟳ New Session" leaves 0 — re-derived per run across **every** stage, because a tab bar is visible
in some and hidden in others. The two tab-row buttons share one QSS builder (`_tab_row_btn_qss`) for
that reason. Gated by `tests/test_gui_restart.py` (9 properties, AST-based, injection-verified).

**Transient results (Results tab playback)**: a transient run appends one Tecplot zone per dumped
step, so the Results view is a movie. `models/tecplot_index.py` scans the file ONCE for the byte
offset of every `zone` header and caches that index by (path, mtime, size);
`TecplotResult.from_file` then seeks to one zone's byte range instead of reading the whole file —
0.35 s → 0.07 s per frame on a 113 MB / 10-zone run, which is what makes playback affordable.
`models/result_series.py` adds the bounded (by BYTES, not frame count) LRU frame cache and the
per-variable global range; `views/result_playback_mixin.py` owns the transport. **Looping is
opt-in**: a run plays through once and stops on the last frame (the converged solution), and the
same checkbox governs the step buttons, which clamp at the ends — greying out there — instead of
wrapping. Play at the end of a finished non-looping run rewinds first; First/Last are jumps, so Loop
does not apply.
- **The colour scale can be pinned across the whole run** ("Lock scale", shown only for a
  multi-zone result), because auto-scaling each frame to its own min/max repaints the same colours
  onto a changing range — a vorticity field decaying 0.089 → 0.019 looks *identical* frame to frame.
  **OFF by default (USER-REQUESTED)**: "Auto (fit to data)" has to mean the frame on screen. A
  **manual** clim always wins, and the lock is dropped when the displayed variable changes.
- **A colour range — pinned OR typed — belongs to ONE variable** (`_clim_by_var`; #24,
  USER-REPORTED). Four rules: **the MODE stays global** (one Auto/Custom checkbox with one meaning),
  so switching to Auto does not forget the numbers; **a variable with no remembered pair is SEEDED
  from its own data range on first render and remembered**, which stops both inheritance and
  per-frame re-seeding drift; **precedence is manual > lock > auto**, enforced in `playback_clim`
  returning None unless `_clim_auto`; and **the store is view state for the loaded result**, cleared
  by `load_result_path` / `clear` but kept across frames. Written ONLY through `remember_clim` /
  `set_clim`, read through `manual_clim` / `render`'s seed path. The panel's Min/Max boxes follow the
  range in force through the `result_rendered` signal, never by reading canvas privates, and in
  Custom mode refresh on exactly two events: the variable MOVED, or the canvas reports
  `clim_seeded`. **The seed flag is why the refresh is not keyed on the variable NAME** — a newly
  loaded run re-seeds under the *same* name, so a name-keyed refresh left the previous run's numbers
  on screen, verbatim the reported symptom. **The Auto checkbox IS the mode, in both directions**:
  unticking seeds from the frame on screen, so nothing jumps and the boxes cannot freeze while the
  canvas keeps auto-scaling. Gated by `tests/test_result_clim_per_variable.py` (8 properties, all
  injection-verified).
- **`set_result` reuses the triangulation when the incoming frame has the same nodes**, keeping
  probes/line/extrema alive across a step. Field caches are always dropped.
Frames are labelled by POSITION (`Frame 4 / 10`): the solver writes `t = "time 0"` for *every* zone.
Gated by `tests/test_result_playback.py`, which pins the byte-range parse against a whole-file scan.

**A restarted solve is ONE run split across several files, and it plays as one animation**
(`services/result_legs.py`, Qt-free — `list_result_legs` → a `LegSeries` of `ResultLeg`s in playback
order plus warnings as data; `ResultSeries` takes a LIST of paths). #32, blocked by #30 because it
reads the `RUN.txt` #30 writes.
- **A list, never a concatenated temp file** — the byte-offset index exists so a frame costs 0.07 s.
  A FLAT frame index sits above the per-file `tecplot_index`: global frame *k* → (file, zone). Three
  things become global with it — the numbering, the LRU **byte** budget and every range
  `global_range` reports — so a change in ANY file drops EVERY cached frame and range.
- **A leg is found by its STEM** (`strip_archive_suffix` + `strip_run_tag`, the inverse of
  `archive_name`), which also works on **pre-#30 archives** that kept `.gui`.
- **Order by ITERATION COUNT; lineage answers a different question** — it gives a PREDECESSOR
  relation, never a position, and two legs resumed from the same point are indistinguishable by it,
  which is exactly the re-run case. Ordering is by the CORRECTED `end` (creation order breaking
  ties); lineage DETECTS the overlap a span cannot.
- **How far a leg got is NOT computed here** (#43): every span comes from
  `case_run_note.iteration_span`, which the restart chooser reads too, so the two windows cannot
  describe one archive differently.
- **A leg measurable NEITHER way is played WHERE IT RAN, not last** — a deliberate departure from
  the issue's "offered last", which is right for a chooser LIST and wrong for a playback ORDER; the
  literal rule shipped first and played this repo's real case **backwards**. Such a leg inherits the
  last count recorded before it.
- **An overlap is a MEASUREMENT** (#43), reported and never interleaved: a half-open span
  `(start, end]`, so the test is interval intersection and the message names the repeating
  iterations. Half-open is load bearing — consecutive legs MEET at a boundary iteration, and a
  closed range would report every ordinary restart as an overlap. **Lineage** is the fallback when
  both spans cannot be measured; a blank start is deliberately not a key, since "cold start" and
  "no record" must not match.
- **The legs are the legs of ONE run**: `…dat.gui` and `…dat.cli` side by side are two solves. The
  anchor is the opened file's run tag — from its name, or from its own `RUN.txt` — a differing leg
  is excluded and NAMED, an undeterminable one included.
- **Opening any leg opens the SOLVE. An INTERACTIVE load asks; a headless one does not**
  (USER-REQUESTED 2026-08-27, replacing #32's modal on every load, which made an unattended run
  behave differently from an interactive one). **`This leg only`** is the escape: shown only when
  the solve HAS more than one leg, never persisted, unticked on every load, and yielding a ONE-leg
  series rather than a second code path. **Its visibility asks how many LEGS the solve has and
  nothing else** — keying it on the `multi` frame-count flag hid the whole row *including the box
  that had just been ticked*. Residue named: `postprocess_ctrl` still reads `_pipeline_running`
  once, guarding the load-FAILED modal, which predates #32.
- **Which legs play is a CHOICE, and it is the user's** (`views/result_leg_picker.py` +
  `views/result_leg_select_mixin.py`): a tick-list offered on load and reopenable from `Legs…`.
  **`ask_legs` returns `None` — "every leg" — when headless, and `None` is also what a CANCEL and an
  empty tick-list return**, so batch and CI are byte-for-byte #43. **Precedence is stated, not
  raced**: `This leg only` wins while ticked, then the subset, then every leg — and unticking
  restores the SUBSET. **Both controls key on the LEG count, never the frame count.** Gated by
  `tests/test_result_leg_picker.py`; blind spot — offscreen the dialog is never shown, so what is
  gated is its verbs, the filter and the controls' visibility.
- **The landing frame is the last frame of the leg that was OPENED** (`last_frame_of`), not of the
  series. **`load_result_path`'s second argument is a `frame`, not a `zone`.**
- **The variable selector is the INTERSECTION**, the subtraction logged naming the short leg, with
  derived quantities recomputed from that intersection through `TecplotResult.derived_from_names`,
  so a derived field cannot outlive its inputs.
- **The leg name prefixes a label only when the series has more than one file** (`prev_002 · Frame
  3 / 10`); the transport's read-out appends the SERIES position in `_read_out`, not in
  `frame_label`, since the zone selector uses the label as a list entry.
- **The per-variable seeded range is COMPUTED over the series, not just carried across it** — one
  leg's band saturates every other, which is #24's symptom one level up. A MULTI-leg series seeds
  from the series; a single file keeps #24 exactly. **It no longer runs inside a paint** (#43):
  calling `scan_series_range` from `render` cannot pump the event loop, so switching variables in
  Custom mode froze the app with no way to say why. It runs in `seed_range_from_series()`, called by
  the handler that unticks Auto, where the "this will take a moment" line is painted first; where
  the whole-series range is available is stated in the Min/Max tooltip (`series_range_hint`). **A
  failed scan is not remembered** (`_series_seeded` records only successful scans). **A range the
  user TYPED is tracked separately (`_clim_typed`, written only by `set_clim`) and is never scanned
  away** — "already scanned" does not imply it. The colour-scale concern lives in
  `views/result_scale_lock_mixin.py`.
- **Each leg's iteration count is where the leg is NAMED** — the tooltips of the frame read-out and
  frame selector — carrying the SAME two caveats the restart chooser's tooltip does (recorded vs
  recomputed; an interrupted run makes it an upper bound). A load emits ONE summary line naming the
  legs opened; each warning stays a full line of its own.
- **A leg's timestamp is when its run FINISHED, never its `archived_at`**
  (`case_run_note.finished_stamp`; USER-REPORTED 2026-08-27) — an archive is made by the NEXT run at
  the moment it starts, so the two answer different questions and were rendered as one parenthesised
  time in one list. Recovered from the run's own outputs (`shutil.move` preserves mtime; #30's hard
  link shares the inode), preferring the ZONE DUMP then `RUN.txt`. **`restart_points` and
  `result_legs` had the defect independently**, so the answer has ONE owner; `archived_at` is kept
  as its own tooltip line.
Three duplications this created were pushed to their owners: `case_files.strip_run_tag` /
`newest_first` and `case_run_note.mtime_stamp` / `iteration_span`, read by both `restart_points` and
`result_legs`. Gated by `tests/test_result_legs_playback.py`, **two of whose injections are
PERMANENT** because the obvious construction of each passes with the code removed (the convergence
fallback injected on legs that HAVE a note; the run-tag filter in the direction that FAILS), each
with a negative control.

**"The surface" of a surface plot is a CHOICE, and so is where s = 0 is**
(`services/surface_source.py` + `services/surface_sample.py`, both Qt-free;
`controllers/surface_source_ctrl.py` decides availability; `views/surface_source_dialog.py` +
`views/result_canvas_surface_mixin.py` are the UI). Surface… used to mean the inner boundary loops
of the solved triangulation — the only honest answer for a body-fitted mesh and **no answer at all
for an immersed-boundary run**. Six sources are offered, all listed even when unusable with the
reason on the row: `mesh` (the only one whose points ARE mesh nodes, so it keeps `node_ids` and
reads **exact** nodal values), `field_iso` (φ = 0.5 on the solved mesh), `grid_iso` (the same on the
STL3d structured φ), `interface_cells` (the Fit Δ points, i.e. `phi_quality.interface_points` —
public precisely so the plotted surface is the one the fit report measured), `analytic` (through
`services/analytic_shape.py`, shared with the φ-DLL generator so the plotted body cannot drift from
the solved one) and `cad`. Rules that are not cosmetic:
- **Iso-lines are chained by mesh EDGE identity, never by welding coordinates**: one crossing point
  per crossed edge, computed from the canonically sorted node pair so both owning triangles get the
  identical coordinate, then a walk triangle→triangle through shared edge keys. No distance
  tolerance anywhere — on a fine mesh one either fragments a contour or fuses two that pass close.
  Every crossing triangle has degree exactly 2, so a component is a cycle or a path, and `closed` is
  reported from *arriving back at the entry edge*, not guessed.
- **s = 0 is required, not defaulted (USER-REQUESTED)**: the old path inherited the origin from
  `next(iter(set))` inside the boundary tracer, so two runs of the same body could start their arc
  length in different places — exactly when you want to overlay the curves. Show/Plot stay disabled
  until a rule (x min / x max / y min / y max) is picked, traversal handedness is forced from the
  polygon's signed area, and the canvas marks the origin + direction.
- **Arc length of a closed curve reaches the full perimeter** (the removed `perimeter_series`
  computed the closing chord and then sliced it off).
- **Off-node samples are interpolated, and δ = 0 by default.** For an immersed solid the interface
  holds the SOLID state, so an outward-normal offset δ is offered — but nothing is moved silently,
  and the title states `exact nodal` vs `interpolated, δ=…`. Outward comes from the polygon's own
  signed area, not the requested handedness, or it would point *into* the body on exactly the
  reversed curves. Samples outside the mesh come back NaN, never a fabricated value.
- **The Fit Δ cloud is cell CENTRES with no connectivity**, so it is ordered by a greedy
  nearest-neighbour walk that can jump a thin waist; a hop >5× the typical one is reported in `note`
  instead of returning a plausible-looking arc length. Prefer the iso-line for measurement.
Nothing is extracted while the dialog is being edited — the widgets only build a `SurfaceSpec`.
Gated by `tests/test_surface_source.py` and `tests/test_surface_source_gui.py`.

**The grid must carry the BCs before it leaves the Mesh stage** (`services/mesh_bc_audit.py`,
Qt-free): a mesh generated BEFORE the per-segment BCs were applied exports **every** patch as the
wall default, and the solve then looks exactly like a converged, unchanged answer — the reported "I
updated the STAR-CD boundary conditions and got the same result". The mesher's own warning fires at
MESH time, several clicks before the grid is exported, sent and run, so `audit_mesh_bc()` re-checks
the actual file at each of those three points (`mesh_export_ctrl.mesh_bc_problems` /
`warn_if_mesh_bc_stale`, and `solver_ctrl._confirm_mesh_bc_state`, which *asks* rather than deciding
— `headless_default=True`, since batch/CI regenerate in the same pass). Two independent signals: an
assigned BC **type** with no patch of that name in the `.bnd`, and a geometry `.meta` **newer** than
the mesh (changing one segment from inlet to outlet leaves both names in the file, so content alone
cannot see it). Note the two namespaces this replaced a bug in: a `group_bc` key is a segment
**label**, a `.bnd` patch name is the **BC type** the mesher resolved it to — comparing them
directly (the old warning) marks every assignment missing on every run. BC detection resolves the
`.bnd` the RUN will use (auto-link wins in `_locate_mesh_bnd`, and `resync_solver_bc_from_group`
runs *after* the auto-link), or the table describes one grid while the solver reads another. Gated
by `tests/test_mesh_bc_audit.py`.

**A path is not a kind: project files are recognised by CONTENT**
(`services/project_file_kind.py`, Qt-free — `classify_project_file` → `"workspace"` / `"pipeline"` /
`""`; `PipelineConfig.classify_file` / `is_workspace_file` delegate to it). `main.py` handed every
positional argument to the geometry loader, so `main.py case.hws` ran `np.loadtxt` over JSON and
reported `could not convert string '{' to float64` (USER-REPORTED 2026-08-13). Every "open this
path" entry point dispatches through the one classifier: the CLI's positional args,
`_load_geometry_file` (which the recent-files menu and STL stager reach), and Pipeline ▸ Load, whose
dialog accepts `*.hws` too. Rules: a **workspace opened in the GUI goes to the workspace loader**,
never through `PipelineConfig.from_workspace_dict` (that conversion exists so the headless runner
can *run* a `.hws` and deliberately drops working state); the CLI loads the **project first and
geometry after**, because either project load resets all state and closes every tab; and only ONE
project file is accepted per launch, the rest named and refused. The "this will close all current
tabs" prompt is gated on `has_unsaved_work()`, since the GUI always opens with one blank session.

**The Output field's `.*` is a placeholder, and only one module may read it**
(`models/mesh_output_names.py`, Qt-free — `output_base` / `output_path_for` / `FORMAT_PLACEHOLDER`,
re-exported as `MeshConfig.*`; it also owns `auto_case_name` / `auto_output_name` /
`is_auto_output_name`, whose `<case>` naming is mirrored in `src/cli.cpp`). The Mesh panel's Output
field holds ONE name for however many formats are enabled, filled in as
`results/meshes/<case>/mesh_<case>.*` — and because the panel→model sync runs on every edit, that
string IS the model value and travels verbatim into the workspace, the pipeline script and the
mesher's config. Only the export dialog understood it, so the **mesher** wrote a VTK into a file
literally named `mesh_<case>.*` and **`pipeline_runner`** handed that name through and then
`os.path.exists`-ed it — which the glob-named file satisfied, so the run reported success and passed
a glob to the contour stage. A C++-only fix turns that silent pass into a hard failure, so both
halves move together. `tests/test_output_format_placeholder.py` gates the resolver, the end-to-end
`-out_name <dir>/probe.*` run, and **statically fails the build if any other GUI file grows its own
`endswith(".*")`**.

**The last generated mesh is not where a reopened case left it**
(`services/mesh_grid_lookup.py::resolve_case_grid`, Qt-free): Generate Mesh writes into the GUI's
**temp dir** on purpose (`<temp>/global_mesh.*`; the stable per-case files appear on Export / Send
to Solver), and that directory is removed on exit, so `global_vtk_path` is **always** empty or
dangling in a reopened workspace — and auto-link, reading only that, answered `No mesh generated
yet` for a case whose grid was on disk (USER-REPORTED 2026-08-13). The resolver tries this session's
mesh, then the triple the case is **already wired to** (what the user last actually sent to the
solver — trusted over any guess), then the per-case exported mesh, and takes the first whose `.vrt`
+ `.cel` + `.bnd` all exist; it names which one and why in the log, and names every candidate when
none works. `_locate_mesh_bnd` asks the SAME resolver. Whether that grid is STALE stays the mesh-BC
audit's job, not a refusal to run. Gated by `tests/test_open_project_by_path.py`.

**A re-save of the geometry must not throw the Mesh-stage edits away, and the fix is a MODEL FIELD
rather than a wrapper around the subprocess.** Both halves of a per-segment BC live in the `.meta` —
the **label** in the NSEGMENTS bc column, the label→type map in the trailer — and the resampler
REWRITES that sidecar from the CAD config on every save, carrying the trailer through verbatim while
the bc column comes back `-` and the v3 grow column comes back 1. So a CAD tweak + Save left the map
pointing at labels nothing carries: the mesher warns, every patch exports as `wall`, and the GUI
still shows the BCs it holds in memory (USER-REPORTED 2026-08-12). The fix is **not** in the
resampler, which stopped preserving the prior sidecar on purpose (a NEW geometry written over an
existing output name inherited the old geometry's flags), and it is **no longer a caller-side
snapshot/restore around the subprocess**. Both facts are `SegmentModel` **fields**: `bc` already was
one, and **`grow_bl` is new** (default True; `to_dict()` emits it only when False, so every
pre-existing config, workspace and script stays byte-identical). The resampler has always read
`sj["bc"]` and `sj["grow_bl"]` from its own config, so `to_dict()` — the single serialiser behind
the resample config, the `.hws` and the pipeline script — makes the sidecar come back **correct the
first time**. The fact moved **up**, not down.
- **The `.meta` is now a PROJECTION of the model, not a second home** —
  `mesh_layers_ctrl._write_sidecar_from_model` rewrites both columns after every edit as the
  command's `refresh_cb`, so an **undo rewrites the file too**.
- **But a projection must be SEEDED first, and forgetting that broke the very thing this work exists
  to fix.** Nothing seeded `bc`/`grow_bl` from an existing `.meta`, and the BC dialog reports only
  NEWLY MINTED labels — so on any geometry whose setup lived only in its sidecar, one Mesh-stage BC
  edit reset every *other* segment's label to `-` and re-enabled a No-BL wall.
  `_adopt_sidecar_facts` takes the sidecar's values into the model first, **fill-in only** (a fact
  the model holds wins), and runs **BEFORE the undo snapshot** — adopting after it still fixes the
  wipe but makes undo restore the *empty* value, re-wiping the sidecar it just protected. Presence
  and ordering are pinned separately. Adoption is a migration rather than the user's edit, so it is
  not undoable and is **named in the log**. Caveat: the rule cannot distinguish "the model holds
  `grow_bl = True`" from "the model is at its default", so a sidecar `grow=0` is always adopted —
  right for the migration, wrong only if the file were allowed to lag the model.
- **The id-set-changed refusal disappeared as a concept**: the old restore re-applied by id after a
  subprocess had rewritten the file, and a label bound to a segment object cannot be shifted onto
  its neighbour.
- The Mesh-stage dialogs **emit** (`seg_grow_bl_changed` / `seg_bc_labels_changed`) instead of
  writing the sidecar — a view writing that file is how the fact came to live only there. A geometry
  with **no CAD session behind it** has no model to hold the fact, so the handler falls back to
  writing the sidecar directly; `_session_for_geom_path` returning None is a normal outcome.
- The label→BC-**type** map (`GROUP_BC`) deliberately did **not** move: it is keyed by label rather
  than by segment, so there is no segment field for it to be a field of.
- Knock-on: a Mesh-stage No-BL toggle now sets `is_geometry_modified`.
Gated by `tests/test_seg_edit_carryover.py`, which drives the real `surface_resampler` (so the wipe
cannot quietly stop happening) and the real controller handler.

**Portable case export** (`services/case_export.py` + `case_export_docs.py`, both Qt-free; Solver
toolbar "Export Case ⇪" + Solver menu): copies a case's INPUTS into a folder that reruns on another
machine — `grid/` (mesh + `.def` + the getPGrid sources, whose `para.in` travels as
**`getPGrid.in`**: `_RENAMES` owns that mapping so `run_case.sh --regrid` and the manifest cannot
disagree), `work/` (`input.in`, `.def`, `phi.dat`, and the restart dump **only when `input.in`
restarts from it** — `include_restart="auto"`), `dll/` (`.so` **and** the `.cc` it was compiled from,
pulled from `results/solver/dll_src` by basename), plus `run_case.sh` and `MANIFEST.txt`.
`run_case.sh` **suggests** a compiler rather than choosing one (`CXX=${CXX:-g++}`) — the package is
for someone else's machine. Selection is an **allow-list**, so a new output file can never sneak in,
and everything rejected is NAMED in the manifest (known-output / not-used-by-this-run /
unrecognised). **The allow-list matches on NAME, so `work/phi.dat` and `dll/*` also have to ask
whether the RUN uses them** (`_unused_reason`): `prepare_case_dir` reuses a case directory in place,
so a case that once ran an immersed solid still holds both — USER-REPORTED as "I didn't configure
IBM, why is there a phi.dat and a dll/?". `input.in` decides, being the file the far machine runs:
it declares `immersed_solid` and names every DLL it dlopens by quoted path (plus a type-11 BC row in
`work/*.def`, the one DLL `input.in` never mentions). A `.so` that no longer travels also stops
pulling its `.cc` out of `dll_src`. `solver_case.report_stale_ibm_artifacts` names the same leftover
at case-prep time and never deletes it. **Every quoted value in `input.in` is a file path**, and the
GUI writes absolute ones for browsed files; those are staged into `work/` and rewritten to
`./<name>`. The solver binary is deliberately excluded. Gated by `tests/test_case_export.py`;
verified end-to-end by regenerating the grid with getPGrid from the exported folder and running
unicones on it. What the export *writes* rather than copies lives in `case_export_docs.py`; the "is
this file an input of THIS run or a fossil of the last one?" reading of `input.in` lives in
`case_export_usage.py`.

**The package also reopens in the GUI, not just in a shell** (`services/case_workspace.py`,
Qt-free). `run_case.sh` reruns the SOLVER; there was no importer for an exported case
(USER-REQUESTED 2026-08-13). Export Case now *asks* (a third prompt, after the restart dump and the
tarball) and writes `<folder>.hws` into the package via `export_case(..., extra_files=...)`. Three
rules: **(1) re-point by file IDENTITY, never by string** — keyed by `(st_dev, st_ino)`, so
`results/` vs `Results/` on a case-insensitive volume or a symlinked scratch dir is still the same
file, and a path the package does NOT carry is left alone and REPORTED rather than rewritten to a
name that resolves to nothing; **(2) the caller's plan is the authority** — `export_case` accepts
`plan=`, because a second plan built with different arguments would describe a different package
than the one on disk; **(3) the stamp survives a move** — the workspace records
`exported_case_root`, and `rebase_case_workspace` (called from `_read_workspace_file` on **every**
load) swaps that prefix for wherever the `.hws` is being opened from. What does NOT travel: CAD/mesh
sources are no part of a solver case, so the geometry rides *inside* the `.hws` (`original_points`
verbatim) and still draws, but re-resampling or re-meshing needs those files — the export log and
the manifest both say so. `Save Workspace` and the export share one builder
(`session_io_ctrl.workspace_dict()`), so an exported workspace can never describe less than a saved
one. Gated by `tests/test_case_workspace_export.py`, which drives the real slot, moves the folder,
and loads it back.

**Signal guards**: never write a raw `blockSignals(True)`/`blockSignals(False)` pair — an exception
between them leaves the widget permanently unable to emit. Use `with block_signals(w1, w2, ...)`
(`app/utils.py`). Likewise, never assign `_is_populating`: use `with controller.populating():`, a
re-entrant depth counter (a bare bool let a nested populate clear the outer guard).
`tests/test_signal_guards.py` statically fails the build on either.

**Error handling**: never `except Exception: pass`. Use
`services/logging_setup.py::get_logger(__name__)` and log at `debug(..., exc_info=True)` for a step
allowed to fail, or `warning` when the failure silently degrades what the user asked for.
`HYBMESH_LOG_LEVEL=DEBUG` surfaces the debug tier. `tests/test_silent_exceptions.py` fails the build
if a new undocumented silent handler appears.

### PreProcessor CLI (`tools/PreProcessor/src/main.cpp`)
- Reads JSON config via `nlohmann/json.hpp` (header-only, bundled)
- `detectFeaturePoints()` → `splitPolyline()` → `alignEndpoints()` → `distributePointsProportionally()`
- Spacing strategies: `uniform`, `curvature`, `cosine` (double-end dense), `geometric` (exponential), `tanh`
- Supporting headers in `tools/PreProcessor/include/`: `Spline.hpp` (cubic spline), `Spacing.hpp`, `Quality.hpp`

### Visualization (`tools/scripts/`)
- **`visualize_dat.py`**: Matplotlib visualization for `.dat` files; `--quality` flag adds expansion-ratio heatmap
- **`generate_letters.py`**: Generates letter-shaped geometry files
- **`case_sources_index.py`**: which solver cases were built from which geometry (reads every `results/solver/*/grid/cad/SOURCES.txt`). No argument lists every case; an argument (path or partial name) answers "if I change this CAD, which cases go stale?" and exits 1 when nothing matches.
- **`golden_mesh.py`**: `capture <dir>` / `compare <dir>` over 15 mesher cases (~10 s), for proving that a refactor changed **nothing**. Byte comparison cannot make that claim — the mesher is not byte-reproducible, and node NUMBERING varies run to run — so it canonicalises by COORDINATE (nodes lexicographically sorted; each cell its node ranks, rotated to a fixed start and direction so winding cannot disagree; the cell list sorted) and reports the worst deviation, keeping an exact 0.0 distinguishable from a match that merely fits the tolerance. **That distinction is load bearing, and measuring it corrected a belief recorded here**: the nondeterminism is not confined to numbering — `wedge_45` returns a coordinate differing by ~1.2e-13 in roughly 1 run in 12 (worst seen 2.5e-13 over ~20 runs, when two wobbles compound), while the other eight cases *of the nine that existed when this was measured* were bit-identical every time. Exact equality would therefore flake, and the 1e-10 tolerance is set ~400× above that measured floor. It also compares **both** STAR-CD files: the `.bnd` patch names, their face counts and each face's own coordinates, and the `.cel` connectivity — which is the grid the SOLVER reads and is not the `.vtk`, since the `.cel` writer owns a winding normalisation, a degenerate-cell skip and a duplicate-cell dedupe that exist nowhere else (a review found the comparator could report SAME while that file had changed). A `.cel` triangle is written `v1 v2 v3 v3` and which vertex repeats follows the element's node order, so the duplicate is collapsed before comparing while the winding deliberately is not. Comparing the `.bnd` matters because because the two most expensive junction bugs this repo has had (see the `BoundaryLayer.cpp` notes above) produced a geometrically perfect mesh with the BCs on the wrong patches. Boundary faces are keyed by coordinate, not vertex id — `.bnd` ids index the `.vrt` numbering while cells index the `.vtk` numbering, and those are precisely the numbers free to move. Duct/wedge geometries are **imported** from `tools/PreProcessor/tests/test_nobl_junction_acute.py` rather than copied (a tool reaching into a test dir is unusual; a second copy of a geometry generator is guaranteed divergence). Two junction bins are NOT reachable this way — case 3/4 need θ > 270°, which no geometry writer produces — and `list` says so. **`HYBMESH_GOLDEN_BIN` points the capture at a different build**, which is what makes a behaviour-preserving claim checkable at all: `git archive <start-commit> | tar -x -C <dir>` (no git state touched), build there, capture the baseline from THAT binary, then compare with the working tree. Without it a baseline can only be captured from the tree that already contains the change it is meant to be evidence about.

## Common Tasks

- **Add a spacing strategy**: Edit `tools/PreProcessor/include/Spacing.hpp`
- **Modify BL generation**: Edit `src/BoundaryLayer.cpp`
- **Add a geometry/curve type**: Add `curve_type` handler in `tools/PreProcessor/src/main.cpp`
- **Change canvas colors**: Update color constants near the top of `tools/PreProcessor/gui/app/views/canvas.py`
- **Add a config parameter**: Add field to `include/Config.hpp` and parse it in the `loadConfig()` block
- **Add a GUI undo-able action**: Create a new `Command` subclass in `tools/PreProcessor/gui/app/commands/` and dispatch it through `controller.py`

## Agent skills

### Issue tracker

Issues live as GitHub issues in `hjlu-tw/HybMesh2D`, driven by the `gh` CLI (`gh issue` is not a git operation, so the Git and Commit Policy above does not cover it). See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles use their own names as label strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix` — the last already exists as a GitHub default and must be reused, not duplicated). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one root `CONTEXT.md` + `docs/adr/`, both created lazily by `/domain-modeling` rather than upfront. See `docs/agents/domain.md`.

## Architecture backlog: measure the status, never read it

**Do not re-derive the architecture backlog by reading source. Run
`python3 tools/PreProcessor/tests/arch_probes.py`.** It prints one line per
candidate — DONE / OPEN / the number that decides it — by re-deriving each from
the tree, and takes about a second. Reading `docs/architecture_review_2026-08-14.md`
to find out what is left is the expensive mistake this exists to prevent.

A **SessionStart hook** (`.claude/settings.json`) runs it with `--hook` and injects
the result, so the status is usually already in context and running it again is
waste. Run it by hand after landing work that changes an answer, or when no such
block appeared — the hook degrades to **silence** if anything goes wrong
(`|| true`, and `emit_hook` returns empty on any exception), because starting with
no status is recoverable and starting with a stale one is the failure being
designed out.

Three artefacts, three jobs, and mixing them up is how the last round went wrong:

- **`docs/architecture_review_2026-08-14.md` — the rationale, FROZEN.** Ten
  candidates with their `file:line` evidence, deletion test and wins, plus a
  "genuinely deep — leave these alone" list that is worth reading *before*
  improving anything in it. It is a snapshot of one day and is **never updated**,
  which is what keeps it honest. Its line numbers are from `854f53e`; re-measure
  before quoting one.
- **`arch_probes.py` — the status.** A candidate is DONE when its probe says so,
  not when a document says so. When one lands, its probe is superseded by the
  real gate test that the work leaves behind (`test_sidebar_seam.py`,
  `test_cpp_linkable_seam.py`, …), and the probe is retired to point at it.
- **A GitHub issue — the batch in flight.** One issue per batch, in the shape of
  issue #1: Problem Statement / Solution / User Stories / Implementation
  Decisions / Acceptance. `/code-review`'s Spec axis reads it, and closing it is
  the status update.

The reason for the split is measured, not theoretical. Reviewing the 2026-08-14
document on 2026-08-17 recommended a batch of three, and **two of the three were
already finished** — including the document's own top recommendation, which had
landed in six commits (`68d3945`..`23bbe34`) the document could not know about.
The wrong signal was read as noise: a hand-count of the leak the seam removed came
back at 148 where the document said 389, and that gap was explained away as a
narrow regex instead of read as evidence the work was done. A status written down
decays silently; a status computed cannot.
