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
| `docs/design_notes/pipeline.md` | Full pipeline, solver case, archive/clean/restart, bDecompose, STL3d, portable case export |

Nothing was rewritten in the move. **Read the matching design note before overruling a rule
here**: most of these rules were bought by shipping the opposite first, and the rule alone
does not carry the argument for itself. When a rule changes, update BOTH — the rule here, and
its entry there.

**What that split cost, and what it did not.** There is no truncation threshold anywhere near
this file's size: Claude Code loads a `CLAUDE.md` of up to **4 MiB in full** and **skips** a larger
one — no longer a figure carried in from documentation, but measured on this build in #61, where
the loader's own `4194304`-byte limit and its `skipping <path>: … exceeds <N> byte limit` line were
observed. The cost is therefore not truncation but **always-loaded context** — **32,519
characters (32,706 bytes, 2026-09-03) ≈ 8k tokens**, paid by every session before it reads a line of
source, down from **149,141 characters (≈37k tokens)** before #62, the first relocation. That
number decays on the next commit, so re-measure before quoting it; what stops it decaying
*silently* is `tools/PreProcessor/tests/test_instruction_budget.py`, whose `ROOT_BUDGET` is
**33,000**, leaving 481 characters of slack — derived by a rule the gate states at that
constant's own definition, and stated there only (#78). **That shape is the rule, not the number**: never so
tight that a typo fix must also edit the gate, never so loose that a feature can add 3k in
silence, which is #59's user story 12 and is now held by an INJECTION in that gate rather than by
this sentence. #75 had locked it at 40,000 while this
file was 32,043, so two such additions COULD have landed unnoticed. None did, and the stronger fact
is not the size of the drift but who made it: every commit under the lock was #75's own, no
feature commit ever ran against it, and the file drifted 110 characters in total. The defect was
the missing guard, not damage done; #78 closed it. Before #75 it was a
ratchet that TRACKED this file rather than only descending — over every commit touching the gate
it fell 7 times and ROSE 8, the largest **+789** in #62's own review. **The unit is CHARACTERS**: the budget #59 states is in
characters while `wc -c` reports bytes, and the two differ by 187 today because of the CJK in this
repo's own prose, so both numbers are given rather than one silently replacing the other. The 4 MiB loader
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
| Full pipeline and solver case (case directory, archive, clean, restart point, bDecompose, STL3d, the immersed-boundary hand-off, the pipeline schema and stage set, the portable case export and its `.hws` re-import) | `.claude/rules/pipeline-case.md` | the case / solver-case / restart / pipeline / STL3d / IB / contour services, `models/pipeline_config.py`, `run_pipeline.py` — the exact globs are that file's own `paths:` list, and its header names the controllers, workers and views it also governs from outside them. |
| GUI panel configuration (the field-spec tables, the one-directional panel↔model data flow, the derived `.dat` key map, the Edit-BL dialog's grouping, length units and `Linf`, the physical-length spin box) | `.claude/rules/gui-panels-config.md` | `views/panels/**`, `views/clean_double_spin_box.py`, the field-spec / units / config-ownership services, `models/mesh_config*` — the exact globs are that file's own `paths:` list, and its header names the controllers it also governs from outside them. Two of its globs are WIDER than the area: a results panel's rules are in `gui-results.md`, `views/panels/restart_chooser.py`'s are in `pipeline-case.md`, and `MeshConfig.output_base`'s Output-`.*` rule is in `gui-handoff.md` with `models/mesh_output_names.py`, where #77 moved it. |
| GUI canvas and editing (the owner of the edge being edited, the outline re-fit, global undo, duplicate/transform closure, the one-polyline discrete geometry, pop-up stacking) | `.claude/rules/gui-canvas-edit.md` | `views/canvas*`, `services/edge_edit*`, `services/shape_refit*`, `commands/**`, `app/popup_stack.py` — the exact globs are that file's own `paths:` list, and its header names the controllers, views and dialogs it also governs from outside them — pop-up stacking reaches every module that shows a modeless pop-up, none of them under a glob of that file, and the header carries the count so this row cannot disagree with it. One glob is WIDER than the area: `commands/config_cmds.py`'s other half is in `gui-panels-config.md`. |
| GUI results (transient playback and the byte-offset zone index, the per-variable colour range, the legs of a restarted solve, the surface source) | `.claude/rules/gui-results.md` | `views/result*`, `views/surface_source_dialog.py`, `views/panels/result_panel*`, `models/result*`, `models/tecplot*`, `services/result*`, `services/surface*`, `services/analytic_shape*` — the exact globs are that file's own `paths:` list, and its header names the two controllers and the one service it also governs from outside them. Its boundaries run BOTH ways and the header measures each, so this row carries neither count: a leg's span and stem are owned by `pipeline-case.md`'s `services/case_*`, while some of this repo's `keep_on_top` calls sit in files these globs reach, whose pop-up rule is in `gui-canvas-edit.md`. |
| GUI seams and the four repo-wide standards (the Qt-free seam, the user-log service, the graded message helpers, signal guards, error handling, the scroll-wheel rule, the GUI module map — plus the FULL text of the four standards pinned one line each below) | `.claude/rules/gui-seams.md` | `tools/PreProcessor/gui/**` — deliberately the widest glob of the eight, because these rules bind every GUI file rather than one area's. Two of the four standards reach files it does NOT cover, which is why they are pinned below as well: parity rules on `include/BLParams.hpp` and `Config.hpp`, matched by `mesher.md`, which carries no parity rule; and the Qt-free seam governs `tools/PreProcessor/run_pipeline.py`, matched by `pipeline-case.md`, which carries no seam rule — and `run_batch.py`, which NO glob in ANY rule file reaches, so this row is the only thing that reaches its reader. |
| GUI lifecycle (the app as a PROCESS: subprocess environment and the Gmsh loader path, window-layout persistence and the startup-state reversal, the ⟳ Restart ordering) | `.claude/rules/gui-lifecycle.md` | `services/env_setup*`, `services/ui_state*`, `services/gui_restart*`, `controllers/lifecycle_ctrl*`, `views/main_window*`, `gui/main.py`, `workers/**`, `tools/scripts/gmsh_*` — 24 files, verified. Two globs go beyond #77's list, recorded in that file's header. It rules directly on `CMakeLists.txt`, which NO glob in any rule file reaches, so this row is the only thing that reaches its reader. |
| GUI file hand-off (is the file this session leaves on disk still correct when the NEXT stage reads it: the `.bnd` BCs, the project file's kind, the mesh output name, which grid a reopened case uses, the `.meta` sidecar) | `.claude/rules/gui-handoff.md` | `services/mesh_bc_audit*`, `services/project_file_kind*`, `services/mesh_grid_lookup*`, `models/mesh_output_names*`, `controllers/mesh_export_ctrl*`, `controllers/mesh_layers_ctrl*`, `controllers/solver_ctrl*`, `models/segment.py` — 8 files, verified. Three owners sit under OTHER rule files' globs (`models/mesh_config.py`, `services/pipeline_runner.py`, and the rest of what `solver_ctrl.py` does); its header names them. |

**The table is load bearing, not a convenience.** Measured on Claude Code 2.1.250 (#61): a rule
file arrives with `load_reason: path_glob_match` when a matching file is **read**, and does NOT
arrive for an `Edit` without a prior `Read`, nor for a `Write` creating a new file — both of those
went through with the rule unloaded. The glob alone therefore cannot make "I did not know there was
a rule" unreachable; this table is what does. **Read the row's rule file before editing or creating
a file in its area.**

**Eight rule files now, and NO area of residue is left.** #59 planned six, derived from this
file's section HEADINGS; deriving them from the text instead needed eight, and the two extra
(#77's `gui-lifecycle.md` and `gui-handoff.md`) hold 13,894 characters this file used to carry
for areas the original partition assigned to nobody. The last residue went with #76: the two
portable case-export blocks, 3,878 characters, into `pipeline-case.md` — the rule file whose
globs ALREADY reached their four modules, which is what made them a defect rather than a gap —
and their rationale from `docs/design_notes/gui.md` into `pipeline.md`, so that rule file's one
rationale pointer is true for every rule in it. Two checks in
`tools/PreProcessor/tests/test_instruction_budget.py` keep that shape from recurring: check 6
fires when a rule in THIS file names a module some rule file's globs already reach (its
`KNOWN_RESIDUE` pin list is empty, and a pin that stops being a violation fails too), and check 5
fires in the other direction — when a rule file's own globs claim a module BY FILENAME and the
design note that rule file points at never names it while another note does, which is what "the
rules moved but the rationale did not" looks like from inside.
That gate also enforces: a per-file size budget (the root file and each rule file measured
against their own, never a total, so moving text between rule files is not a legal evasion),
the table against the rule files in **both** directions, the existence of every gate test a
rule file names, and a `paths:` list that is present, non-empty and not only `**`.

## Important: four standards that bind BEFORE any file is opened

These four belong to no area, so no glob can carry them: a rule file does not arrive for an
`Edit` without a prior `Read`, nor for a `Write` creating a new file (measured, #61). Rule and
gate here; the full text of all four is `.claude/rules/gui-seams.md`.

- **GUI↔C++ config parity.** Every mesh key must agree in **key, TYPE and DEFAULT, in both
  directions**; a type divergence is never pinned, a default divergence pins both values plus a
  reason. Gate: `tests/test_gui_cpp_config_parity.py`.
- **GUI file length.** Keep each file under `tools/PreProcessor/gui/` at **~500 lines**; split it
  when it grows past. The only one of the four with **no gate** — measured 2026-09-03, 5 of 258
  files exceed it (worst 523).
- **Never `except Exception: pass`.** Use `services/logging_setup.py::get_logger(__name__)` and
  log at `debug(..., exc_info=True)`, or `warning` when the failure silently degrades what the
  user asked for. Gate: `tests/test_silent_exceptions.py`.
- **Never a raw `blockSignals(True)`/`blockSignals(False)` pair, and never an `_is_populating`
  assignment.** Use `with block_signals(...)` and `with controller.populating():`. Gate:
  `tests/test_signal_guards.py`.

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
The module map and every GUI rule have moved to the six `gui-*` rule files the tripwire table
names; the portable case export — the last block this section held — moved to
`.claude/rules/pipeline-case.md` (#76), the rule file whose globs already reach its four modules,
and its rationale with it. Nothing is ruled on here. The rationale for the GUI areas is
`docs/design_notes/gui.md`; for the export, `docs/design_notes/pipeline.md`.

### PreProcessor CLI (`tools/PreProcessor/src/main.cpp`)
- Reads JSON config via `nlohmann/json.hpp` (header-only, bundled)
- `detectFeaturePoints()` → `splitPolyline()` → `alignEndpoints()` → `distributePointsProportionally()`
- Spacing strategies: `uniform`, `curvature`, `cosine` (double-end dense), `geometric` (exponential), `tanh`
- Supporting headers in `tools/PreProcessor/include/`: `Spline.hpp` (cubic spline), `Spacing.hpp`, `Quality.hpp`

### Visualization (`tools/scripts/`)
- **`visualize_dat.py`**: Matplotlib visualization for `.dat` files; `--quality` flag adds expansion-ratio heatmap. Handed a MESH it names the file and points at `view_mesh_vtk.py`, rather than failing inside `np.loadtxt` (#58)
- **`view_mesh_vtk.py`**: `<mesh.vtk> <out.png> [xmin xmax ymin ymax]` — draws a legacy-VTK mesh
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

### Rule-file entry style

The style the `.claude/rules/*.md` files are written in, fixed on one block by #68: claim first,
every identifier kept, gate filenames and `USER-*` markers verbatim, a reversal reduced to one line
plus a **grep-verified** anchor, blind spots in one list per file. See `docs/agents/rule-file-style.md`.

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
