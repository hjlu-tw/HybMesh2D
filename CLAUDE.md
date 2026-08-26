# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important: Git and Commit Policy

**Still never run a mutating git command on your own** — `add`, `commit`, `push`,
`checkout`, `reset`, `rebase`, `merge`, branch creation or deletion all wait for
an explicit instruction. Read-only inspection (`git status`, `git diff`,
`git log`) is free: you need it to do the job below.

**What changed (2026-08-14, USER-REQUESTED): you must now raise the subject
yourself instead of staying silent.** The old rule made the assistant wait to be
asked, so work piled up uncommitted and unreviewed.

**Prompt for a commit** once the working tree holds a *coherent, finished* unit
of work — a feature that runs, a bug fixed with its test, a refactor that
builds. Say what you'd commit and propose a message; do not run it. Signals that
one has accumulated, any of which is enough:

- a task the user framed as one job is done and verified;
- roughly **200+ changed lines** or **5+ touched files** since the last commit;
- the next step would start an unrelated concern (mixing them makes a commit
  that cannot be reverted cleanly);
- something risky comes next (a large refactor, a dependency bump, a migration)
  — a checkpoint before it is worth more than one after.

Raise it **once per threshold crossing**, in a sentence or two at a natural
pause, never mid-edit and never repeatedly for the same pile. "No" ends it for
that unit of work.

**Ask about a code review** when the uncommitted-or-unpushed body of work grows
past what a commit prompt covers — about **3+ commits' worth**, **500+ changed
lines**, or a whole stage of a feature landing. Offer `/code-review` (Standards
+ Spec) and let the user decline. Prefer asking *before* a branch is pushed or a
PR opened, since that is when a review is cheapest to act on.

These numbers are defaults, not gates — a 30-line change to `BoundaryLayer.cpp`
can deserve both prompts, and 400 lines of new test data can deserve neither.
Judge by whether a reviewer would want a boundary there.

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
`run_pipeline.sh` sets `DYLD_LIBRARY_PATH` (like `run.sh`) and calls `tools/PreProcessor/run_pipeline.py`. In the GUI, the same end-to-end run is the **Run All** button (top-right, all modes) / **Pipeline** menu (Run / Load / Save script). See the "Full Pipeline" section under Architecture.

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
the GUI from the derived key map + `field_spec.model_types` + `MeshConfig()`. New
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

## Configuration

### .dat Config Format (`config/Background_para.dat`)
Key-value text file, command-line args override file values. Parameters grouped by function:

| Group | Key examples |
|-------|-------------|
| Domain | `DOMAIN_X_MIN/MAX`, `DOMAIN_Y_MIN/MAX` |
| Surface | `SURFACE_MESH_SIZE`, `AUTO_SURFACE_SIZE` |
| BL Core | `BL_INITIAL_THICKNESS`, `BL_GROWTH_RATE`, `BL_LAYERS` |
| Corners | `BL_FAN_NODES`, `BL_AUTO_FAN_NODES`, `BL_FAN_ANGLE_THRESHOLD`, `BL_CONVEX_METHOD` |
| Concave | `BL_CONCAVE_METHOD`, `BL_CONCAVE_ANGLE_THRESHOLD`, `BL_SMOOTHING_ITERS` |
| BL/no-BL Junction | `BL_JUNCTION_METHOD` (0=taper-to-zero legacy, 1=4-case angle-driven, default), `BL_JUNCTION_ANGLE_C1/C2/C3` (°) |
| Transition | `BL_TRANSITION_LAYERS`, `BL_TRANSITION_GROWTH_RATE`, `BL_TRANSITION_BUFFER` |
| Gmsh | `GMSH_ALGORITHM` (6=Frontal-Delaunay), `GMSH_OPTIMIZE`, `FARFIELD_GROWTH_RATE`, `FARFIELD_MESH_SIZE` |
| Output | `EXPORT_VTK`, `EXPORT_STARCD`, `BC_XMIN/XMAX/YMIN/YMAX/GEOM` |
| Units | `LENGTH_UNIT` (m/cm/mm/um/in/ft/custom), `LENGTH_UNIT_METRES`, `LENGTH_UNIT_NAME` |

**The 22 boundary-layer parameters are declared ONCE, in `include/BLParams.hpp`**
(`X(KEY, type, field, default)` per row). The struct, the `.dat` reader, the
per-geometry override parser and `isBLParam` are all GENERATED from that list, so
there is no parse branch left to forget; `Config` holds one `BLParams` rather than a
second copy with a second set of defaults. `Config::print()` is deliberately NOT
generated — the banner is a grouped report reused verbatim as the provenance sidecar —
so `tests/cpp/test_bl_params_decl.cpp` check 6 gates it instead: every parameter must
be reachable from the banner AND (where the banner renders it as a number) its own
value must appear there. That check's blind spot is named in its own docstring: it
cannot see a SWAPPED PAIR, because the pairing of a value to its meaning IS the label
prose.

**Two parse behaviours CHANGED when the two parsers were unified** (2026-08-19), both
measured on the old and new trees:
- **`BL_AUTO_FAN_NODES` is an int on both paths.** It is 0 OFF / 1 Global Avg /
  2 Local Avg and `BoundaryLayer.cpp` really branches on 2, but the `.dat` reader used
  to collapse it with `(val != 0)`, so a global `BL_AUTO_FAN_NODES 2` ran as 1 while
  the same token on a `GEOM_FILE` line reached 2. It now means Local Avg everywhere.
  No config in this repo sets 2, so no existing mesh moved (golden 9/9 SAME).
  **The GUI could not express it until 2026-08-19**: `MeshConfig.bl_auto_fan_nodes` was
  a `bool` while a three-item combo (OFF/GLOBAL/LOCAL) edited it, so its LOCAL item was
  squashed to `1` on the way into the `.dat` and had *always* run GLOBAL. The parity
  gate's type check is what found it; the field is now an `int`, matching `Config.hpp`,
  and picking LOCAL really runs Local Avg. **That is a behaviour change golden meshes
  cannot cover** — none of the 9 cases picks LOCAL — so it is recorded here instead.
- **A `bool` key is read through a double**, so `BL_USE_ANALYTIC_GEOM 0.5` is now true
  where it used to read 0 and be false. Integral values — everything the GUI or any
  config here writes — are unaffected. Kept, because reinstating a per-row parse rule
  to preserve it would put back exactly what let the two parsers disagree.

**An unrecognised per-geometry `KEY=VALUE` override is now NAMED, not dropped.**
`parseBLOverrideToken` asks `isBLParam` and warns; it used to store the token and let
the applier silently skip it, which is the same "the setting does nothing" failure
class as the above.

### PreProcessor JSON Config
JSON format; supports multi-element definitions with transforms (scale/rotate/translate), per-segment spacing strategy, and auto-split threshold. See `tools/PreProcessor/config/` for examples.

## Architecture

### Core C++ (`src/`, `include/`)

**The implementation is a LIBRARY and the executable is a shim.** `hybmesh_core`
(STATIC) holds `cli.cpp` + `Mesh.cpp` + `BoundaryLayer.cpp`; `add_executable(HybMesh2D
src/main.cpp)` compiles **only** the twelve-line shim that calls `hybmesh::runCli`
(`include/Cli.hpp`). Before this, the three `.cpp` files were compiled straight into
the executable and there was no library target at all, so **no test could link them**
— the process boundary was the mesher's only seam, and `classifyJunctions`, extracted
specifically so the junction binning could be reasoned about and tested, sat private
and unreachable for exactly that reason. The shim is what keeps the seam honest: the
executable compiles no implementation, so there is nowhere to add logic a test cannot
reach. Two consequences worth knowing: **the provenance macros are defined on the
LIBRARY, not the executable** (`cli.cpp` reads them via `Provenance.hpp`, so a
definition left on `HybMesh2D` would apply to the shim alone and silently degrade
every banner and sidecar to `git unknown`), and the **CGNS-before-Gmsh link order**
is `PUBLIC` on the library so it propagates unchanged to everything that links it —
that ordering is load bearing (see the `cgsize_t` note in `CMakeLists.txt`).

**The tests live in `tests/cpp/`** — one executable per file, registered with ctest,
`check.hpp` for assertions (**record-and-continue**, not abort-on-first: ctest runs one
executable per file, so seeing every failing case from a single CI run beats bisecting
them, and `report()` reprints the FIRST failure last so the cause is not buried under
its consequences). A test **links a library target, never a list of sources** —
compiling `src/*.cpp` into a test executable works and quietly reintroduces what the
seam removed: a second build of the implementation, testable but not the one the binary
runs. `tests/test_cpp_linkable_seam.py` gates it, because this property decays
in silence — adding a `.cpp` to `add_executable` builds and runs perfectly well, and
the loss surfaces only as a test nobody can write. Its seven checks (the decision-layer rule is four more, in `test_cpp_pure_layer.py`; they were one file until a review pointed out they are two invariants with disjoint machinery) go past "the shim
is the only source", because that alone has holes and each hole *looks* satisfied:
`#include "cli.cpp"` links fine and puts the implementation where no library holds it;
a test listing `../../src/Mesh.cpp` recompiles the implementation; a new
`add_executable` becomes a second home for logic; a `tests/cpp/test_*.cpp` that CMake
never registered passes by never running. All four were verified by injection, and the
two blind spots that remain are named in the test's own docstring rather than papered
over. One caveat on the neighbouring instrument: `golden_mesh.py` does **not** compare
the `.bnd` `segm_no` column, so a defect confined to a boundary edge's source-segment
key is still invisible to it (`segm_no` is a `.bnd` column and the `.cel` carries no BC at all) — measured, by mutating `recordBoundaryEdge` to write the
segment key before the overwrite refusal: the C++ unit test caught it in 0.5 s while
all 68 other tests and the 9-case golden set passed.

**`hybmesh_pure` is the decision layer, and the BUILD is what keeps it honest.** It is
the C++ analogue of the GUI's "`services/*.py` must be Qt-free" rule, for the same
reason: testing a decision should not require a heavy environment. What makes it more
than a slogan is that **the pure tests link `hybmesh_pure` alone and are not linked
against libgmsh at all** (verified with `otool -L`: only libc++ and libSystem), so the
moment such a module *uses* `Mesh` or gmsh those executables stop linking — measured, by
making `JunctionScheme.cpp` construct a `Mesh`: `Undefined symbols for architecture
arm64`. The grep and the linker cover different halves — an *include* that is not yet
used is invisible to the linker, a *use* is invisible to a grep — so
`test_cpp_pure_layer.py` also computes each file's **transitive** include closure.
Transitive matters concretely: `BoundaryLayer.cpp` includes only `BoundaryLayer.hpp` and
reaches `Mesh.hpp` through it, so a direct-include check would call it pure and would let
any new module launder its dependency the same way. The list is a **deny**-list
(`HEAVY_SOURCES` / `HEAVY_HEADERS`, each entry carrying its reason): a new `src/*.cpp` is
assumed pure and making it heavy costs an entry, because an allow-list would have the
failure mode backwards — forgetting to enrol a new pure module would silently exempt it.

`hybmesh::classifyJunctions` (`include/JunctionScheme.hpp`, `src/JunctionScheme.cpp`) is
its first member, and its history is the argument for the layer. It was extracted from
`generate()` specifically so the junction binning could be reasoned about and tested, and
then could not be tested at all: it was private, and it took a 22-field mutable
`FrontState` plus `Mesh&` while actually reading three positions/normals per node, one
`skipBL` bool per node, and three config scalars. The wide signature hid how narrow the
dependency was. It now takes `vector<JunctionNode>` + `JunctionParams` (AoS, not six
parallel arrays — the same reasoning that made `JunctionDecision` one struct) and returns
decisions **and warnings as data**: the very-sharp-wedge message is user-facing prose
about config keys and stays at the call site, while the threshold
(`tan θ × influence < 1.15`) becomes testable — `tests/cpp/test_junction_scheme.cpp` pins
it at three different influence values without generating a mesh. The computed `thetaDeg`
travels in the decision because `HYBMESH_JUNC_DEBUG`'s trace format is parsed by
`test_nobl_junction_acute.py`; a negative value means no angle was measured (an isolated
BL corner), which is how the caller reproduces the old trace exactly. **This covered
junction cases 3 and 4 for the first time** — θ > 270°, a strongly convex junction, which
no geometry writer in the repo produces, so no mesh-level test has ever reached them.

- **`main.cpp`**: HybMesh2D's entry point and deliberately nothing else — see above.
- **`cli.cpp`**: The whole command line (`hybmesh::runCli`); parses config, loads geometries, runs collision checks, orchestrates BL + Gmsh pipeline. **`OUTPUT_FILENAME` may end in the GUI's `.*` all-formats placeholder, which is a wildcard and not an extension** — stripped once, before `validate()`/`print()`, so the banner, the provenance sidecar and every writer share one basename. Taking it literally wrote the VTK into a file *named* `mesh_<case>.*` (the export block's `extPos()` finds that dot, so `.vtk` was never appended), and before `stripExt` it did the same to STAR-CD — which is where the `results/meshes/cartesian/mesh_cartesian.*.vrt` files on disk came from. See "The Output field's `.*`" below.
- **`BoundaryLayer.cpp`**: Quad layer growth — normals, fan/parallel corner handling, concave merging, transition layers, smoothing. BL/no-BL junctions (a BL edge meeting a `grow=0` neighbour) use the angle-driven cap scheme (`BL_JUNCTION_METHOD=1`, default); **the binning itself is not here** — it is `hybmesh::classifyJunctions` in the decision layer (see `hybmesh_pure` above), and `generate()` only assembles its narrow input, applies the returned decisions and logs the returned warnings. The flow-facing angle θ picks case 1 (slide along the neighbour edge + absorb the no-BL nodes it covers, θ ≤ 95°), case 2/4 (perpendicular cap, 95° < θ ≤ C2 or θ > C3) or case 3 (neighbour-edge extension cap, C2 < θ ≤ C3); every cap leaves a free full-height lateral column whose edges are emitted as far-field constraints so the wedge is triangulated, and the step is scaled by 1/cos(tilt) so the *perpendicular* height is what stays fixed. **The 95° slide bound is geometric, not a knob**: a cap must point into the fluid wedge (which spans θ) while the perpendicular sits at 90°, so at θ ≤ 90° it provably exits through the no-BL wall — θ < 90° self-intersects the front (exit 5) and θ = 90° (a rectangular duct with one wall No-BL) hands Gmsh a doubled-back hole (exit 6). `C1` used to be that bound at 135°, wide enough to slide where an honest cap fit; it now only bins method 0 and round-trips through config. A slide at a **very sharp wedge** (`tan θ × BL_CONCAVE_INFLUENCE_MULTIPLIER < 1`, i.e. the corner squeezes more wall than the concave blend can lean over — 21.8° at the default 2.5, measured break between 22° and 21°) still fails downstream, so it emits `[WARN] Very sharp BL/no-BL wedge at (x, y)` naming the corner; advisory only, nothing is auto-corrected. An **isolated BL corner** (BOTH neighbours No-BL) gets the same treatment for the same reason (issue #2): it grows a full-height column with no lateral one, so the front doubles back and Gmsh triangulates nothing — the run has always ended at `empty far-field mesh … the domain loop likely failed to close`, which names the symptom at the wrong layer. `classifyJunctions` reports the corner's position and the caller emits `[WARN] Isolated BL corner at (x, y)`, pointing at the **`.meta` sidecar** rather than at the geometry — and that is the PERMANENT behaviour, not a placeholder. Issue #4 asked for the two lateral columns such a corner needs and was closed **wontfix** (2026-08-20), because the configuration is not reachable from this toolchain: the resampler flags EVERY segment boundary `corner = 1` (`resCorner.push_back(isBoundaryPt ? 1 : 0)`, where `isBoundaryPt` is "the first or last sample of a task" — NOT "sharp"), `cli.cpp`'s `prevBL || nextBL` rescue then promotes any such corner with a BL neighbour back to BL growth, and the GUI's `meta_io` only rewrites the NSEGMENTS bc / grow columns while copying the POINTS block through verbatim. Only a hand-written or foreign sidecar gets here, so naming THAT is worth more than two columns whose per-wall BC assignment is this repo's most expensive bug class. Advisory rather than a refusal is still right (issue #2): exit 6 is an honest failure. Gated by `tests/test_nobl_junction_acute.py`, which pins the sidecar pointer along with the corner's coordinates. **A case-1 slide REPLACES a stretch of the no-BL wall, so its own edges must carry that wall's BC by construction** (`slideColumns`/`slideWallRun` → `Mesh::recordBoundaryEdge`), matched to the wall edge each replacing edge covers by arc length: the column is a straight ray along the first neighbour chord, so on a *curved* no-BL wall it drifts off the wall polyline by ~a chord sagitta while `classifyBoundaryBc`'s `pointOnSegment` accepts 1e-6 of a chord (measured 6e-8..1.8e-6 vs a 2.0e-8 tolerance) — every column edge past the first fell through to `BC_GEOM`, so a No-BL inlet/outlet exported a `wall` band exactly D_total long at each BL junction and the solver ran a wall across part of the inlet. A straight no-BL wall has no drift, which is why straight-duct coverage missed it. Gated by `tests/test_nobl_junction_acute.py` (`write_curved_duct` — the curvature is the point). `=0` restores the legacy taper-to-zero (~12% floor ramping back over arc length).
- **`Mesh.cpp`**: Mesh data structure (Nodes/Elements/Edges), Gmsh far-field integration, VTK and STAR-CD export. **A boundary edge's BC and its source segment are ONE fact and are private**: write with `recordBoundaryEdge(v1, v2, srcNode, overwrite)`, read with `boundaryEdgeInfo(v1, v2)`. They used to be two public parallel maps every caller keyed by hand, so "wrote the BC, forgot the segment key" was a defect the interface could not prevent — and half an identity reaching the exporter is exported as the wall default. The compiler now rejects outside access, which is why nothing tests *that* — a test would be weaker than the type system. Their paired SEMANTICS are tested, in `tests/cpp/test_mesh_boundary_edge.cpp`: a refused overwrite must not half-apply, the key is the unordered node pair, and a BC with no resolvable segment still records. **`FARFIELD_MESH_SIZE` is a `Min()` cap on the size field, not a target**: the field is grown from the wall (`FARFIELD_GROWTH_RATE`, from the BL front or — no BL — the geometry surface) and/or inward from the domain bounding box (`FARFIELD_GROWTH_RATE_OUTER`), so in a domain that is small relative to the growth rate it tops out below the cap and *every* larger cap gives a byte-identical mesh. Every run therefore prints a `[ Mesh Size Field ]` block reporting how high growth actually reaches, the effective ceiling, and whether the cap is dead / marginal / active — computed by re-evaluating the field expressions at the generated mesh nodes, **not** by measuring cell edges (those run ~15% long on stretched triangles and would report a dead cap as live). Gated by `tests/test_size_field_ceiling.py`. Caveat: a custom domain outline is added with `geomId = -1`, so for a pure internal-flow case (`DOMAIN_FILE … nobl`, no `GEOM_FILE`) the wall-distance field is never built and `FARFIELD_GROWTH_RATE` is inert — only `FARFIELD_GROWTH_RATE_OUTER` (distance to the *bounding box*) grades the mesh.
- **`Config.hpp`**: Single-header; parses `.dat` files into ~50 typed parameters
- **`GeomUtils.hpp`**: `Vector2D`/`Point2D`, segment intersection, normals, dot/cross products

### PreProcessor GUI (`tools/PreProcessor/gui/app/`)
Layered PyQt6 application:

- **`controller.py`**: Top-level orchestrator; command pattern for undo/redo, delegates to specialized controllers
- **`controllers/`**: Business logic split by concern — `segment_ctrl.py` (CRUD, properties), `session_ctrl.py` (save/load), `session_io_ctrl.py` (`.hws` workspace read/write + `WORKSPACE_FORMAT_VERSION` migration), `project_state_ctrl.py` (the workspace's `project` section: Mesh/Solver/IB config + baseline-snapshot dirty detection), `backend_ctrl.py` (runs `surface_resampler` in QThread), `mesh_gen_ctrl.py` (runs `HybMesh2D` in QThread), `lifecycle_ctrl.py` (autosave, crash recovery, bounded worker shutdown), `curve_ctrl.py`, `transform_ctrl.py`
- **`models/`**: `segment.py` (`type`, `strategy`, `parameters` incl. `spacing` for distance-based resampling, curve fields, plus the two per-segment facts the MESH stage edits — `bc` and `grow_bl`, see "A re-save of the geometry" below; serialized via `to_dict()`/`from_dict()`, which is the ONE serialiser behind the resample config, the workspace and the pipeline script), `project.py`, `mesh_config.py` (+ `mesh_config_keys.py`, `mesh_config_io.py`, `mesh_output_names.py` — see "The Output field's `.*`"), `session.py`, `vtk_mesh.py`, `result_data.py` / `tecplot_index.py` / `result_series.py` (see "Transient results" below). Note: auto-split is computed in the GUI (producing explicit `split_indices`); the per-segment `auto_split`/`split_threshold` keys are read by the C++ backend (`src/cli.cpp`) for hand-written/CLI configs but are not emitted by the GUI. Exported JSON carries a `format_version` field (`CONFIG_FORMAT_VERSION`).
- **`views/`**: `canvas.py` (pyqtgraph interactive geometry canvas, dark theme), `mesh_canvas.py` (mesh visualization), `main_window.py` (tab layout), `sidebar.py` (segment property editor), `panels/` (tab panels per workflow)
- **`commands/`**: `segment_cmds.py` (`UpdateSegmentStateCmd` snapshots full state dict), `split_cmds.py`, `vertex_cmds.py`, `config_cmds.py` (`UpdateProjectStateCmd` — snapshot of the Mesh/Solver/IB configuration)

**Stage config data flow is one-directional** (`controllers/panel_sync_ctrl.py`): the
**model is the truth, the panel is a view**.
- **panel → model**: `sync_panel_to_model(panel_attr)` runs on *every* user edit (the
  widget-introspection traversal in `undo_ctrl._wire_widget_edits` calls
  `on_panel_edited`, which syncs first and then schedules the undo snapshot). So
  `global_mesh_config` / `global_solver_config` / `global_stl3d_config` are never stale;
  nothing should read a panel widget to get a config value.
- **model → panel**: `push_panel_config(panel, cfg)` (undo-suppressed), as before.
- `PRESERVED_FIELDS` lists what each panel does **not** author and must never overwrite
  (e.g. the solver panel has no widget for `length_unit`, so a wholesale copy would wipe
  it and take `Linf` with it). `tests/test_panel_model_sync.py` proves each set equals
  what that panel's `get_config` actually assigns, **by AST** — so a model field added
  without a widget fails the build instead of silently going stale or being wiped.
- A model may define `normalize()` to restore its own invariants after a sync (SolverConfig
  re-derives `linf` from the preserved unit).
- **`set_config` sets the panel's own `_loading` flag under try/finally**, and the sync
  checks *that*, not the caller's discipline: a direct `set_config` that forgets
  `push_panel_config` must cost at most a spurious undo step, never a corrupted model.
  New panels must follow the same `set_config` / `_set_config_body` split.

**A config field is declared ONCE, in its panel's field-spec table**
(`app/services/field_spec.py` is the Qt-free record + the pure questions asked of a
table; `views/panels/field_widgets.py` is the one kind→widget mapping and the three
traversals; the tables are `services/mesh_field_specs.py` +
`services/mesh_bl_field_specs.py` and `views/panels/solver_field_specs.py`,
`views/panels/stl3d_field_specs.py` — the two MESH tables live in `services/` because
the `.dat` key map derives from them, see "The GUI's `.dat` key map is derived" below;
their old `views/panels/` paths survive as re-export shims so the ~11 Qt-side call
sites are unchanged). Each panel used to be cut in half —
one half BUILT widgets, the other read and wrote them against a model — with the whole
widget set as the implicit interface: **176 attributes across five build mixins, named
back by hand in 246 read/write lines**, agreeing only because both halves spelled the
same name. One BL knob (`BL_TRANSITION_BUFFER`) was named 16 times across 7 GUI files,
four of which were parallel lists over the same 21 fields. A spec carries `attr` ·
`kind` · `label` · `tip` · `model` · `key` · `group` · `opts`; the table is walked once
to build (`add_spec_rows`), once to write (`write_specs`) and once to read
(`read_specs`). Rules that are load bearing:
- **`get_config` / `set_config` / `_set_config_body` were NOT touched as verbs**, nor
  was `panel_sync_ctrl` — the frozen review lists both under *"Genuinely deep — leave
  these alone"*. The table sits BEHIND those three, and the panel-owned `_loading` flag
  and its `try/finally` are unchanged.
- **`PRESERVED_FIELDS` is a subtraction, not a list**: model fields − table − the
  residue each panel declares beside its table (`*_EXTRA_AUTHORED`, for facts one
  widget holds for many things — the geometry list, the BC-definition table). What is
  left to prove is that the declared residue equals the code still written by hand.
- **`LENGTH_FIELDS` is derived from `kind == "sci"`**, which IS the physical-length rule
  (`SciDoubleSpinBox`, no floor, decade steps), so the list and the widgets cannot
  disagree.
- **Widgets are seeded from the model's defaults**, not from literals repeated in build
  code. Measured: a fresh panel used to report BL layers 0, growth 1.001, Gmsh
  MeshAdapt, CFL 0, all-`inlet` outer BCs and a 0..0 STL3d domain; it now reports the
  dataclass values. That is the `_STARTUP_OK` bug class closed at its source.
- **A choice is matched by VALUE in Python, never `findData`** (QVariant comparison
  makes a bool `False` against an int `0` datum a coin toss), and a value the combo does
  not offer falls back to a *declared* one instead of landing on index 0.
- **Numeric and combo rows go into the form DIRECTLY, never wrapped**:
  `QFormLayout.labelForField` only finds a label for the widget that IS the field cell,
  and four visibility helpers use it to hide a row's label with its field.
- Three escape hatches exist and each is used by exactly one field, named with its
  reason in the gate: `read`/`write` on a spec (`ascii_combo` — three items behind a
  bool), `panel_choices` (`bl_concave_method` — the panel's backing combo offers only
  method 5 because method 0 is CLI-side), `host_writes` (`output_filename` — population
  is a heuristic that reads the widget's own text).
- **One spec means one tooltip**, so a form label's '?' now shows the field's full
  explanation rather than a shorter summary (~40 rows). The alternative — a second
  `label_tip` on every spec — is the duplication the candidate removes. The Edit-BL
  dialog's '?' shows that prose **plus the `.dat`/`Config.hpp` KEY**: the KEY used to be
  the ONLY help 20 of the 21 fields had, and giving every spec a tip silently killed the
  `spec.tip or key` fallback (found in review, now gate check 12).
- **`services/field_spec.py` is Qt-free and gated; `config_ownership` is Qt-free at
  IMPORT only.** The MESH tables are now genuinely reachable headlessly (they had to
  be — see below), but the SOLVER and IB tables still live under `views/panels/`,
  whose package `__init__` eagerly imports eight Qt panels, so a `preserved_fields()`
  call naming those two still loads PyQt6. Do not read the deferral as "answerable
  headlessly" for every panel; it keeps the `services/` sweep honest, and for the
  mesh panel it is now more than that.
Gated by `tests/test_field_spec_tables.py` (twelve properties, every static one verified
by injection, each injection asserting the mutated source still PARSES and really
changed).
Behaviour preservation was measured against `f97213a` via `git archive`: the solver and
IB panels' form structure is row-for-row identical (70/70 and 7/7), all 25 differing mesh
rows are inside the four `setVisible(False)` BL backing sections, and every panel's
`set_config` → `get_config` round-trip is byte-identical. `test_panel_model_sync.py`
stayed green throughout and lost only its check 1, which became a tautology once both
sides of that equality were the same declaration.

**The GUI's `.dat` key map is DERIVED from the field-spec tables**
(`models/mesh_config_keys.py`): 45 of its 49 `KEY -> (attribute, converter)` entries
come from the tables (`spec.key` + `spec.model`), the converter comes from the model
field's own dataclass type via `field_spec.model_types()`, and the 4-entry residue is
declared with a reason each. It used to be 49 hand-written entries restating both
facts, in a file with no way of knowing when a table changed.
- **The two mesh tables MOVED to `services/` for this, and the reason is the seam.**
  They are intrinsically Qt-free (they import only `dataclasses`, `MeshConfig` and
  `field_spec`), but any module under `views/panels/` drags in that package's
  `__init__` and its eight Qt panels — measured: importing either table with PyQt6
  blocked raised ImportError — while `mesh_config_keys` is on the HEADLESS path
  (`mesh_config_io.config_to_text` ← `run_pipeline.sh` / `run_batch.sh`). A spec
  import without the move would have made PyQt6 a requirement of a compute node that
  never draws a window.
- **The cost is recorded rather than hidden**: ~250 lines of UI text (labels,
  tooltips, one `_HINT_STYLE` CSS string) now sit in `services/`, which weakens the
  "the tables carry UI text so they live under `views/`" reasoning this file used to
  give for their location. The Qt-free RULE is unaffected and still gated; what
  changed is the rationale, and the trade was taken deliberately — deriving the map
  is worth more than the tidiness of where UI copy lives. The solver and IB tables
  did NOT move: nothing headless derives from them.
- **`_KEY_MAP` is anchored to the WRITER, not just to the tables** (gate check 13f,
  both directions, with the four structural keys — `GEOM_FILE` / `DOMAIN_FILE` /
  `SEED_FILE` / `GROUP_BC` — declared). Checking only "map agrees with tables" was
  measured BLIND: removing a spec's `key=` left both sides agreeing with the
  parameter gone from each, while the writer kept emitting the line and the reader
  could no longer read it back. `test_gui_cpp_config_parity.py` cannot see that
  either, since the writer's f-strings are independent of the map.
- Deriving the map made `mesh_config_keys` depend on `MeshConfig`, i.e. the cycle the
  module was split out to avoid, pointing the other way. `mesh_config.py` therefore
  imports the map inside the two methods that use it.

**The edge being edited has an OWNER, and there are TWO edit kinds in it**
(`services/edge_edit.py`, Qt-free — `EdgeEditSession` + `EditOutcome` +
`ShapeOutcome`). Drawing a new **analytic** edge or double-clicking an existing one,
and double-clicking an **imported (discrete)** edge to reshape its whole outline by
the corner vertices, both open a *modeless* session: a numeric dialog and draggable
canvas handles bound live to one segment, committed by **Create Edge** / **Apply**
and reverted by **Cancel**. Between them that was **twelve attributes on
`AppController`** — declared in `controller.py`, begun in `curve_draw_ctrl` /
`file_edit_ctrl`, committed or cancelled in `pending_edit_ctrl` / `file_edit_ctrl` —
with "an edit is live" enforced only by every reader remembering to test for `None`,
and the whole lifecycle unreachable without a canvas, a dialog and a QApplication.
**Both kinds live in one owner because they are alternatives**: at most one may be
live, so `_edit_in_progress()` is now one question with one answer instead of an
`or` repeated at every call site. Three rules:
- **The dialog is held OPAQUELY.** The owner stores it and hands it back; it never
  calls a method on it. What has to be *asked* of the dialog — a polygon's
  open/closed toggle, which is not part of the form's `params` — is read by the
  caller and passed into `update()` as a value. That is what keeps the module free
  of Qt without a wrapper interface.
- **`commit()` / `cancel()` end the session and return an `EditOutcome`; they do not
  decide what it becomes.** Whether that is an `AddCurveSegmentCmd` or a recorded
  `UpdateSegmentStateCmd` stays with the controller, which owns the undo stack. The
  *revert* does live in the owner, because it is the other half of the snapshot it
  took.
- **An edit BELONGS to the CAD session it began in, and leaving that session is a
  transition.** This is the half that was a *defect*, not a shape: nothing cancelled
  a live edit when a tab was switched or closed, while the commit path resolved its
  target through `active_session()` — the tab in front *now*. So committing an edit
  looked the segment up in the wrong session, failed, and fell back to matching by
  segment **id** (the fallback that exists to survive an intervening undo) — and ids
  are per-session, so it landed on **another tab's edge**, recording an undo entry
  whose before-state came from one geometry and whose after-state came from another;
  committing a *new* edge added it to whichever tab was in front. Measured, the id
  collision is worse than "possible": `ProjectModel.renumber_segments` assigns
  contiguous 1..N across both edge kinds, so every tab's Nth edge has id N. Every
  outcome now carries its session and the caller acts on **that** one, and the list /
  selection / window title — which describe the tab in FRONT — are only touched when
  the edit's session *is* that tab. Switching or closing away from a live edit
  **asks**, defaulting to cancelling it (`headless_default=True`, so a batch run
  never blocks and never comes out with an edit pointing at a tab that is gone); on
  close the edit question comes **first**, and declining it aborts the close so the
  unsaved-changes question is never reached. Declining a switch has to **put the tab
  bar back** — Qt moves it and then tells us. And **at most one edit is live** stopped
  being convention: `begin`/`begin_shape` REFUSE while another is live, so the Qt side
  must ask and end the first one deliberately. Refusing is the backstop, not the
  interaction — a module with no Qt cannot put up a prompt and should not decide to.
  `commit`/`cancel` with nothing live is a silent no-op (a dialog signal arriving
  after the state was cleared is a timing artefact, not something the user did):
  `get_logger(__name__).debug`, never a pop-up or a user-log line.
- **An ending the DIALOG did not initiate must close the dialog.** It tears itself
  down through `finished → deleteLater`, which fires only when it closes *itself*;
  a cancel driven by a tab switch, a tab close or a second edit beginning used to
  leave the window on screen with its Apply and Cancel pointing at an owner that had
  forgotten the edit. The dialog therefore travels back on the outcome (the owner
  holds it opaquely and may not call a method on it) and the caller closes it. That
  `close()` **re-emits `rejected`**, so the cancel handler runs again against an idle
  owner — which is exactly the silent-no-op case above, and is why the two rules have
  to land together. And **the canvas clear takes the EDIT's session**: the live
  preview is a canvas item keyed by `session_id`, so aiming it at the front tab
  leaves the preview drawn on the tab the edit belonged to.
- **Not every route out of a session is a prompt.** Switching and closing a tab ask,
  because both are cleanly abortable. Opening a new tab, `reset_all_state` and
  loading a workspace **end the edit unconditionally and say so in the log**: the
  first moves focus as an unavoidable consequence of an action already taken (making
  it abortable would mean `_new_session` — which four call sites dereference straight
  away — growing a failure mode), and the last two have already asked their own
  whole-session question. What the requirement actually demands is that no live edit
  survives pointing at a background or discarded session, which is what these
  guarantee.
- **The committed-edge DRAG is a transition, not a nullable field.** Dragging a
  handle of an already-committed edge (no dialog open — a third modality the other
  two deliberately route drags away from) must collapse one gesture into one undo
  step. That used to be `AppController._drag_orig_state`, filled by the drag handler
  and retired by the *selection/refresh chokepoint* as a side effect, because a
  snapshot left over from a gesture that ended abnormally would otherwise be recorded
  against whichever segment was selected next — and undoing THAT writes one edge's
  shape onto another. It is now `begin_drag` / `finish_drag`, and the rule is a
  property: **a drag belongs to the segment it began on and cannot be finished
  against another**. Two consequences worth knowing: the handler must not
  `begin_drag` on the `finished` event (a gesture cannot begin and end in one event;
  letting it would make a stray finish snapshot the *new* segment and record a
  one-event edit on it — the old code did exactly that), and **a drag is NOT
  `is_active()`**, because the callers that guard on that predicate must keep working
  during one.
- **A corner drag is a value in, an outline out.** The shape session holds the
  pristine points plus the corner POSITIONS, and `move_corner` returns a freshly
  re-fitted array instead of mutating the live one — so every re-fit recomputes from
  the same basis, dragging never accumulates transform onto transform, and Cancel
  restores the points *byte-for-byte* rather than to within a tolerance.
  Its one departure from symmetry is deliberate: the shape side has **`end_shape()`,
  not a commit/cancel pair**, because both endings need the same thing from the owner
  (the snapshot) and differ only in what the caller does with it.
The SHAPE of all this is gated by `tests/test_edge_edit_owner_seam.py` — five
properties, each a function over source so the nine in-test injections run the real
check against mutated text, and each injection asserting the mutation still PARSES
and really differed (a mutation that breaks the parse looks exactly like the check
working). It watches: no modal-edit attribute back on `AppController`; nobody
reaching past the verbs (resolving `self.edge_edit` **and** one-line aliases of it);
the owner Qt-free, proved by DRIVING the whole lifecycle in a **subprocess** with
PyQt6 blocked — in-process the answer is always "Qt is loaded" once another test
imported it — plus an AST read for a *deferred* import at any nesting depth; one
predicate; and both commit paths resolving their session from the outcome. Its blind
spots are named in its own docstring, the sharpest being that check 1 matches
attribute NAMES, so state smuggled back as `self._live` is invisible: it defends
against the cheap regression, not a determined one.

The BEHAVIOUR is gated by `tests/test_edge_edit_owner.py` (the owner's verbs, Qt-free),
`tests/test_committed_drag_undo.py` (the drag wiring) and
`tests/test_edit_session_binding.py` (the cross-tab defect and both prompts) — the
last two on the offscreen Qt platform with the real `AppController`, which is where
the old bugs lived. The session-binding test reaches the wrong-tab state by moving
`active_idx` **directly** rather than through `switch_tab`, on purpose: `switch_tab`
now ends the edit, so going through it would test the prompt instead of the binding,
and the binding is the half that must still hold when some other route changes the
front tab. The first refuses PyQt6 through a meta-path hook (so a *deferred* `import PyQt6` fails too) and then drives the REAL
`PendingEditControllerMixin` / `FileEditControllerMixin` — re-implementing the commit
branch in the test would prove only that a test can add a segment. (It loads both by
file path: `app/controllers/__init__.py` eagerly re-exports eight Qt mixins, the same
hazard `test_qt_free_seam.py` records for `models/` and `views/panels/`, and that is a
property of the package rather than of the module under test.) Every check is verified
by injection. One claim is deliberately narrowed rather than overstated: the params
snapshot is a deep copy, but **no shipped caller mutates a nested parameter in place**
(a polygon carries `vertices_str`, a *string*), so a shallow copy would pass every
live path — the test mutates one directly and says so, pinning the contract rather
than a reproducible bug.

**The outline re-fit is pure arithmetic and has its own module**
(`services/shape_refit.py`, Qt-free — `build_edge_specs` + `refit_shape`). Each edge
of an imported outline re-fits between its own two corners by the similarity transform
carrying its ORIGINAL corner pair onto the current one, so dragging a corner two edges
share redistributes both. It lived inside `FileEditControllerMixin._refit_geom`, read
three `self.` attributes and **had no test at all**; extracting it first is what made
moving the state around it small. Two behaviours it is careful about and which are now
pinned: a **zero-length edge** falls back to a pure translation (the transform's
divisor is the squared length, so without it the interior points divide by ~zero and
leave the canvas), and the **closing edge wraps to index 0** rather than being read as
out-of-range and skipped — a gap that only opens on a *closed* outline, which is most
of them. The extraction was measured, not asserted: 2000 randomised outlines through
both the new function and the pre-change in-place body recovered from git came out
**byte-identical, worst |Δ| = 0**. Gated by `tests/test_shape_refit.py`, whose sort-
order check needed searching for: a CPython set of small corner indices iterates
sorted anyway, *and* the order depends on insertion history rather than the values, so
neither a small outline nor a set literal is a usable oracle — the check uses a layout
found by search over 200k random cuts where the builder's own set really is unsorted.

**Undo is global, across every CAD session AND project settings** (`controllers/undo_ctrl.py`). Histories stay per-`GeometrySession` (plus `controller.project_history`) so closing a tab drops exactly its own commands; ordering across them is by the monotonic `seq` that `CommandHistory._push` stamps — undo takes the highest, redo the lowest waiting on a redo stack. Undo raises the tab owning the command before applying it. Mesh/Solver/IB edits are recorded by debounced snapshot diffing, so a burst of typing is one step. **Any code pushing config into those panels must go through `controller.push_panel_config(panel, cfg)`** (or `suppress_project_undo()`), or the push is recorded as a user edit.
- **`workers/`**: `backend_run.py`, `mesh_gen_run.py` (QThread wrappers for CLI subprocesses), `proc_util.py` (shared `popen_kwargs()` with `start_new_session`, plus `stop_process`/`stop_process_async` SIGTERM→SIGKILL escalation over the child's process group — every worker `cancel()` must route through these, never a bare `terminate()`)

**Subprocess environment**: `services/env_setup.py::mesher_env()` resolves the libgmsh directory (override: `HYBMESH_GMSH_LIB_DIR`) and must be passed as `env=` when launching `HybMesh2D`/`surface_resampler`. Inheriting it from a shell wrapper does **not** work — macOS SIP strips every `DYLD_*` variable when a protected `python3` starts, so `run.sh`'s export never reaches a Python-launched child. `tools/scripts/gmsh_lib_dir.sh` is the shell-side equivalent, sourced by `run.sh`/`run_pipeline.sh`. **Where Gmsh actually is has ONE answer: `tools/scripts/gmsh_sdk_dirs.py`** — the shell helper and `CMakeLists.txt` (which also needs `gmsh.h` at configure time) both resolve through it by asking the installed wheel. The CMake side used to carry a fixed HINTS list naming one developer's macOS pip prefix, and a pip prefix is per-machine: **CI installed gmsh and then failed at configure with "Gmsh SDK not found", and because the test job is `needs: build` the entire regression suite was SKIPPED rather than run — the workflow had never once been green.** A hardcoded absolute path in a discovery hint is worth treating as a defect on sight. The second half of the same bug was the LIBRARY name: the Linux wheel ships `lib/libgmsh.so.4.15` with no unversioned `libgmsh.so` symlink, so `find_library`'s `NAMES gmsh gmsh.4.15` (which become `libgmsh.so` / `libgmsh.4.15.so`) match nothing, while macOS's `libgmsh.4.15.dylib` matches — the build worked on the developer's machine and nowhere else. The resolver therefore reports `LIBFILE=` (the file it globbed) and CMake falls back to it, rather than teaching NAMES another platform's spelling and baking the version into a second place. The workflow first went green on 2026-08-17 (`4254c5d`), and what that covers is worth knowing: **69 Python tests + `ctest` 2/2 in the build job + the end-to-end `run_pipeline.sh`, none of which had ever executed in CI before**. Getting there took four unrelated environment defects and one flaky runner, and not one of them was a defect in the code under test — the lesson is that a workflow's *history* is the only evidence it gates anything.

**`app/utils.py` is the Qt side of a seam, and the pure helpers now live on the
other side** (`services/paths.py`, Qt-free — `repo_root`, `find_binary_executable`,
`find_solver_executables`, `find_stl3d_binary`, `find_mpi_launcher`, `is_mpi_binary`).
`app/utils.py` was a namespace rather than a module: message boxes, signal guards,
pop-up stacking and form builders, then a third of pure `os`/`shutil` path resolution,
one name, and that name sits on the Qt side. So **every headless module that needed a
path imported the whole GUI toolkit** — `import app.services.pipeline_runner` loaded five
`PyQt6` modules four lines below its own comment reading "no PyQt import, so this module
stays headless-safe", and `run_pipeline.sh` / `run_batch.sh` required PyQt6 on a compute
node that will never draw a window. `app/utils.py` **re-exports** the moved names, so the
~16 Qt-side call sites are untouched; only the Qt-free layers were migrated.
`is_headless` deliberately **stayed** with the Qt helpers — it asks which Qt platform
plugin is running, so it belongs there even though its own `QApplication` import is
deferred into the function body. Two things the gate
(`tests/test_qt_free_seam.py`) had to learn the hard way:
- **The check must be a subprocess.** In-process the answer is always "yes, PyQt6 is
  loaded" once any other test has imported it, so the assertion would pass for the wrong
  reason exactly when it matters.
- **A deferred import is still a dependency, and an import-time sweep cannot see it.**
  With the sweep green, `run_pipeline.sh` on a PyQt6-less machine still died in stage 2:
  `mesh_config_io.config_to_text` did `from app.utils import repo_root` *inside a function
  body*, loading no Qt at import time and needing the toolkit the moment a mesh config was
  written. Three such sites existed (`models/mesh_config_io.py` ×2,
  `models/solver_config.py`, `workers/solver_run.py`). The gate therefore reads the AST for
  a moved name imported from `app.utils` at **any** nesting depth, and separately refuses
  PyQt6 outright in a subprocess and drives the writers that failed.
The `services/` sweep is a **deny**-list (`QT_SERVICES`, each entry carrying its reason —
`i18n` wraps QTranslator, `ui_state` wraps QSettings): a new service is assumed Qt-free and
making one Qt-dependent costs an entry, since an allow-list would silently exempt whatever
nobody remembered to enrol. Stale entries fail too. One incidental correction: the moved
block held a **second, disagreeing depth count** — `find_binary_executable` walked five
levels from `gui/app` and so resolved to `<repo>/../build`, outside the repo, which is the
off-by-one `repo_root`'s own docstring warns about; it now goes through `repo_root()`, and
the gate pins the **resolved path** rather than the number of `..` segments. A separate
pre-existing defect the sweep surfaced and did *not* fix is recorded in the gate's
`CANNOT_IMPORT_STANDALONE`: `services/index_helpers.py` cannot be imported first
(`index_helpers` → `models/__init__` → `models.session` → `commands/__init__` →
`commands.segment_structure_cmds` → back), enabled by the eager re-exports in those two
`__init__.py` files.

Scroll-wheel on QSpinBox/QDoubleSpinBox is intentionally disabled (overridden in `main.py`).

**Numeric fields**: any field holding a *physical length* (BL initial thickness, mesh sizes, domain coordinates, resampling spacing, seed size/radius) must use `views/clean_double_spin_box.py::SciDoubleSpinBox`, not `CleanDoubleSpinBox`. It accepts/displays scientific notation, steps by decade, and has no hardcoded floor — a fixed-notation box silently clamps the 1e-7..1e-8 first-cell heights real CFD needs. Range lower bounds stay at 0 and invalid values are rejected by `MeshConfig.validate()` with a message, never by UI clamping.

**Length units** (`app/services/units.py`, Qt-free): the model declares ONE length unit
(Mesh panel, top row). It is **not cosmetic** — the solver is dimensional. Per the UNICONES
manual `fs_UnitRe` is *per metre* and `Linf` is *metres per grid unit* ("input 1 if
dimensional in meters"; its own sample uses `Linf 0.0254` for an inch grid), so
**Re = fs_UnitRe × Linf**. A mm mesh left at `Linf = 1` runs at 1000× the intended Reynolds
number with a mesh that looks perfect.

Rules:
- **`Linf` is derived from the declared unit**, not typed. `SolverConfig.linf_from_unit`
  is True for anything new; `load_from_dict` turns it **off** for a config that has a
  hand-set `linf` and no `length_unit`, so a pre-units case keeps its Reynolds number.
  `unit_check()` then reports the discrepancy naming the unit that `linf` implies.
- **Changing the unit relabels; it never rescales.** Only two things convert numbers:
  `Linf`, and coordinates at *import* (`views/import_unit_dialog.py`, asked once per
  import action, defaulting to no conversion, silent + no-op when headless).
- **Units are shown as the spin box's own `setSuffix`**, never baked into label text —
  the suffix rides on the widget owning the number and cannot be forgotten. Only
  physical lengths get one; growth rates, angles and counts must not.
  `views/panels/mesh_units_mixin.py::LENGTH_FIELDS` must equal the panel's
  `SciDoubleSpinBox` set — `tests/test_units.py` fails the build otherwise, which is how
  a field added later cannot silently lose its unit.
- The visible defence against a *plausible* wrong unit is the **reference Reynolds
  number** read-out on the Solver panel (`views/panels/solver_units_mixin.py`) and the
  `[INFO] reference Reynolds number` line in `run_pipeline.py`. The size-plausibility
  check only catches gross errors and says so.
- The mesher **records but never converts** `LENGTH_UNIT` (it only compares lengths with
  each other); it prints it in the banner, so it also lands in the provenance sidecar.

**The user-facing log is a service, not a widget**: say things with `AppController.log()` (controllers) or `app/services/user_log.py` (views) — never `main_window.log_panel.log(...)`, which is how 255 reach-throughs accumulated. `LogPanel` is a registered sink; sinks get the RAW message and classify for themselves, and the durable file mirror happens in the service ONLY (a second one in the panel writes every line twice). `user_log.log()` attaches the file handler itself, so a process that never ran the GUI's `main()` still leaves its log on disk. Gated by `tests/test_user_log_seam.py`, which fails the build on a new reach-through. This is a different log from `get_logger(__name__)`, which is developer diagnostics.

**User messages**: use `app/utils.py`'s graded helpers, never a raw `QMessageBox` call — with **two recorded exemptions, and no third without a helper**: `views/case_dir_dialog.py` (the case-dir question, 3-4 mutually exclusive dispositions) and `controllers/curve_join_ctrl.py` (keep / merge). The graded set is `report_*` plus a two-way `confirm`, and neither of these is a yes/no; both still make the headless early-return themselves, which is the part the helpers exist to centralise. A third multi-way prompt is the point at which `app/utils.py` grows a `choose()` rather than the list growing again — `report_error` (failed write, data at risk → Critical), `report_warning` (failed read → Warning), `report_info` (a precondition, nothing broke → Information), `confirm(..., headless_default=)` (Yes/No). All of them no-op or return the default on a headless platform, which is what keeps tests, CI and the headless pipeline from hanging on a modal. Any new dock widget needs `setObjectName()`, or `QMainWindow.restoreState()` silently skips it.

**Pop-up stacking** (`app/popup_stack.py`, re-exported from `app/utils.py`): every
modeless pop-up goes through `keep_on_top(w)` **before** `show()`, which re-parents it to
the **top-level** window, leaves it an ordinary normal-level `Qt.Dialog`, and installs the
three filters that put it back on top — `_PopupRaiser` (on the main window, for every
activation), `_ClickRaiser` (on the **QApplication**, for every mouse RELEASE) and
`_ShowRaiser` (on the pop-up, so a call site that only `show()`s is covered).
Activation alone is not enough and that is not a detail: it fires on the FIRST click of
the main window only, so every click after it reorders the window in front of the pop-up
with no Qt event to hear, and a raise deferred into the middle of a canvas *drag* is
undone when the drag ends. Releasing is the moment the platform has finished reordering.
The app-wide filter returns on its first line for anything that is not a release, and
`raise_later` keeps at most one raise in flight per widget. Both shortcuts on the window LEVEL are wrong and were each shipped once:
`WindowStaysOnTopHint` floats the pop-up above **every** application (intrusive), and
`Qt.Tool` — an NSPanel with `hidesOnDeactivate` — makes the pop-up **disappear** the
moment the user clicks another app while the main window stays visible (measured on
Qt 6.10: `isExposed()` → False). Disabling the auto-hide is not an escape: Qt6 ignores
`WA_MacAlwaysShowToolWindow` (the cocoa plugin reads the `_q_macAlwaysShowToolWindow`
*window property*) and a Tool window sits at NSFloatingWindowLevel, i.e. back to floating
over the other app. **Every raise goes through `raise_later()`** — a raise issued from
inside the event that reorders the windows is undone when the platform finishes that
event, which is why the arc/line editor (shown from the canvas press that completes the
shape) opened *underneath* the main window once the Tool level was gone. Re-parenting is
load bearing twice over — the raiser finds pop-ups in the top-level's direct child list,
and a pop-up parented to a panel is hidden with that panel. Gated by
`tests/test_popup_stacking.py`. `BatchDialog` opts out on purpose (it runs for minutes and
must be free to sit behind the main window).

**Duplicate/transform closure**: `transform_apply_ctrl` is type-preserving (a line stays a
line, an **arc stays an arc**…), and the copy inherits the source's `closed` flag — except
in the polygon-bake fallback (formula curves, discrete file edges, and a circle/arc under
a NON-uniform scale, which is an ellipse the model cannot hold), where the flag is
*re-derived from the points* by `_baked_edge_is_closed`. The arc's image is read off three
TRANSFORMED POINTS — centre, arc start, quarter-sweep point — so one code path serves
every similarity transform and a mirror's reversed sweep (`theta1 < theta0`, which both
samplers walk) comes out of the geometry rather than a per-transform sign rule; the
quarter point rather than the midpoint, because `sin(sweep/2)` vanishes at exactly
|sweep| = 2π. Whatever still bakes is NAMED in the log with the reason. `SegmentModel.closed` defaults True and is only
ever read for `curve_type == "polygon"`, so every other kind of edge carries True while
drawing open; copying that flag onto a baked polygon is what silently closed a duplicated
arc. Discrete edges must not take the PROJECT's closure either — one segment of a closed
imported outline is itself an open polyline. Gated by `tests/test_transform_closure.py`.

**The discrete geometry is ONE polyline, and both ends of that have to be handled.**
A session stores every discrete point in `original_points`, indexed by `split_indices`
into file segments, and the canvas draws it as a single pyqtgraph item.
- **Baking order matters.** `BakeCurveToGeometryCmd` welds a converted edge onto
  whichever END of the polyline it touches, so an edge touching neither lands as a
  separate piece. `bake_selected_curve` therefore chains a multi-edge selection with
  `_chain_edges` (the same one Join uses) and bakes head-to-tail as ONE undo step
  (`BakeCurvesToGeometryCmd`) — the selection is index-sorted, so the DRAWING order,
  which the user cannot fix by clicking differently, was deciding the result.
- **Where the polyline must NOT join comes from the model.** `_geometry_connect`
  (in `segment_canvas_ctrl`) breaks it at any index interval covered by no file
  segment — `update_file_segments_from_indices` already drops the bridging pair —
  and passes that as pyqtgraph's `connect` array. Without it two disjoint pieces are
  drawn joined: a "diagonal" that belongs to no edge and cannot be selected away.
  Deliberately not a spacing heuristic, which would also break a long straight edge
  beside a finely sampled arc.
- **An empty model still has to be drawn.** `_apply_geometry_update` returns early
  when `original_points is None`, so `_clear_geometry_canvas` does the wiping —
  layer, hit-test points, split markers, closing edge, stats — but never the
  analytic (curve) items, which a session can legitimately have on their own.

**Window layout** is persisted by `app/services/ui_state.py` — **window geometry and
dock state, and nothing else** — namespaced by `LAYOUT_VERSION` (now 2; bump it when
the layout changes so stale state is ignored rather than restored). It never touches
`QSettings` when headless. **The active stage and the sidebar sections are
deliberately NOT persisted, and that is a reversal, not an omission** (issue #27,
USER-REQUESTED): both used to be saved and restored here on the same
resume-where-you-stopped argument, and the user weighed that against landing
somewhere unpredictable — with no way to reset it — and chose predictability. Every
launch therefore starts on **CAD** with **every** sidebar section collapsed, and both
defaults come from code that was already there rather than from a new constant:
`mode_combo`'s own index 0 (`main_window.py`) and
`CollapsibleSection`'s own `start_collapsed=True` default — measured: of the 39
`start_collapsed` mentions under `app/`, **zero** pass `False`, so the default is the
guarantee and no call site overrides it. **The `LAYOUT_VERSION` bump orphans more than the keys this removed**, and
that is worth stating rather than discovering: `_section_key` is built from `_PREFIX`,
so moving to `ui/v2` drops every existing user's saved geometry, dock state and
*dialog*-accordion flags along with the stage and section keys. The bump was requested
in the issue and the one-time loss accepted there; what it buys is that no v1 key can
ever come back as a live value. `restore_active_stage` and the private `_sections` walker are **gone** —
the save half went with the restore half, because a value written and never read
reads as a working feature. The convenience removed was real; do not reinstate it as
a bug fix. `tests/test_ui_state_and_dialogs.py` checks 1/2/4 are the **inverted**
versions of the checks that used to pin the old behaviour (seeded with a previous
version's `ui/v1` stage + section keys, rebuilt in the old key format from the live
sidebar so the stale state is really the kind the deleted restore consumed), so
bringing either restore back fails the gate. A **dialog's** accordion is a separate,
still-wanted feature and its *code path* is untouched: it persists itself through
`save_section_states(scope, sections)` / `restore_section_states(...)` with an
explicit scope string, which never walked `sidebar_stack` — the Edit-BL dialog still
opens all-closed and reopens the groups the user left open. Its *stored* flags are
not exempt from the version bump, per the paragraph above.

**"⟳ Restart" closes THIS window first and spawns only if the close happened**
(`services/gui_restart.py`, Qt-free — `restart_command` / `preflight` / `launch`;
`lifecycle_ctrl.restart_gui`; the button sits beside `Run All` in the persistent tab
row, so it is present in every stage). USER-REQUESTED (2026-08-20, issue #28):
`Clear All` resets the model but leaves the process — its view state, temp dir, log
and worker threads — in place, so a truly fresh instance meant quitting and
relaunching by hand. Four rules:
- **The order IS the feature.** Spawning first and *then* asking "discard unsaved
  changes?" leaves **two** GUIs running when the answer is No, which is the opposite
  of the request. So `main_window.close()` goes first and the child is launched only
  if it returned True.
- **The outcome comes from `close()`'s return value, not from `isVisible()`.**
  Measured under the offscreen platform: a *cancelled* close on a window that was
  never shown reports `isVisible() == False` and `isHidden() == True` — identical to
  a successful one — while `close()` returns False exactly when the close event was
  ignored, shown or not. The issue's own text suggests `isVisible()`; it would have
  made the gate pass for the wrong reason.
- **There is no second copy of the unsaved-work prompt.** The close routes through
  `MainWindow.closeEvent` → `handle_close_event`, which already covers modified
  geometry sessions *and* a dirty Mesh/Solver/IB configuration, saves the layout
  before teardown, joins every worker within its bounded budget, and removes the
  autosave file — so the new instance does not offer to recover the session the user
  just chose to leave. A second prompt would be a second place to forget a
  dirty-state source.
- **`proc_util.popen_kwargs()` must NOT be reused here.** It sets `stdout=PIPE`
  (with `stderr` folded in) for the streaming workers; with the parent gone nobody
  drains that pipe and the child stalls once the buffer fills. The restart builds its
  own kwargs — `start_new_session=True` repeated deliberately rather than inherited,
  `stdin`/`stdout`/`stderr` all `DEVNULL` — and passes **no arguments**, because the
  request is a brand-new session and carrying the case over would be a different
  feature. The entry point resolves through `paths.repo_root()`, never by counting
  `..` segments.
`preflight()` exists because of that ordering: a bad interpreter or a missing
`main.py` has to be caught while there is still a window to report it in. The
residue is named rather than hidden — a `Popen` that fails *after* the window is
gone can only reach `user_log`'s file mirror, since there is no parent window left
to put a modal on and the app is already quitting; the gate pins that it is at
least *said*. The button's **caption is a measurement, and the measurement lives in
the gate rather than in a comment**: at the 900px minimum window the tab row is
540px, "⟳ Restart" (88px) leaves 31px of slack in the tightest stage and
"⟳ New Session" (119px) leaves 0 — but those numbers are re-derived per run by
`tests/test_gui_restart.py`, which sums what each visible widget asked for across
**every** stage, because a tab bar is visible in some stages and hidden in others
(measuring in the IB stage reports 171px of slack where CAD has 31). The two
tab-row buttons also share one QSS builder (`_tab_row_btn_qss`) for exactly that
reason: the fit is measured against padding and font size, so two copies of them
could drift apart. Gated by `tests/test_gui_restart.py` — 9 properties, the
source-reading ones AST-based and injection-verified, with a negative control on
`popen_kwargs` and its blind spots named in its own docstring — plus a one-off
acceptance run: the real spawn was reparented to init in its own session and
outlived the parent.

**Edit Boundary Layer dialog** (`views/panels/mesh_dialogs_bl.py`, tables in
`mesh_bl_field_specs.py`, accordion + window fitting in `mesh_bl_dialog_layout.py`):
the 21 BL parameters are collapsible groups (`_BL_FIELD_GROUPS`, mirroring the `.dat`
parameter groups), **all closed to start** (USER-REQUESTED — the dialog opens as a list
of headers and the window is only as tall as what was opened), plus Expand all /
Collapse all. Only two things open a group and neither is a default: the state the user
left it in (`ui_state.save/restore_section_states`), and an override (below).
**`_BL_FIELD_GROUPS` must partition
`_BL_FIELD_SPECS` exactly** — a key in no group is a parameter the user cannot reach
that is still written back on OK — gated by `tests/test_bl_dialog_sections.py`, with
stray keys falling into a trailing "Other" group as a backstop. A group holding a value
that differs from the global default expands itself, so a per-geometry override never
hides behind a collapsed header. The window follows the open groups
(`_relayout` → `_autofit_height`), bounded by the screen and never below a height the
user set by dragging. Two Qt facts that fit depends on, both learned the hard way:
`QScrollArea::sizeHint()` is **clamped to 24 font heights**, so the dialog's own
`sizeHint()` stops growing after a group or two (the fit measures the scroll's shortfall
against its cap and the leftover slack instead); and hiding a widget only *posts* the
layout request, so `CollapsibleSection._on_toggle` invalidates its own layout — without
that, every reader (including the sidebar) sizes itself from the state the section just
left. The leftover-space absorber (trailing spacer / per-segment list) is
**stretch 0 + Expanding**, never a stretched item, which would compete proportionally
with the capped scroll area and leave the groups short of their own cap.

**Transient results (Results tab playback)**: a transient run appends one Tecplot
zone per dumped step, so the Results view is a movie. `models/tecplot_index.py`
scans the file ONCE for the byte offset of every `zone` header and caches that
index by (path, mtime, size); `TecplotResult.from_file` then seeks to one zone's
byte range instead of `readlines()`-ing the whole file and rescanning it — 0.35 s
→ 0.07 s per frame on a 113 MB / 10-zone run, which is what makes playback
affordable at all. `models/result_series.py` adds the bounded (by BYTES, not
frame count) LRU frame cache and the per-variable global range.
`views/result_playback_mixin.py` owns the transport (First, Prev, Play/Pause,
Next, Last, speed, Loop, Lock scale). **Looping is opt-in**: by default a run plays
through once and stops on the last frame (the converged solution), and the same
checkbox governs the step buttons, which clamp at the ends — and grey themselves
out there — instead of wrapping to the far end of the run. Play at the end of a
finished non-looping run rewinds first. First/Last are jumps rather than steps, so
Loop does not apply to them; they grey out only on the frame they lead to. Two
further rules decide whether the animation is readable:
- **The colour scale can be pinned across the whole run** ("Lock scale", shown only
  for a multi-zone result), because auto-scaling each frame to its own min/max
  repaints the same colours onto a changing range — a vorticity field decaying
  0.089 → 0.019 looks *identical* frame to frame. Ticking it scans all frames for
  the current variable (cached, so it is paid once) and pins that range.
  **It is OFF by default (USER-REQUESTED)**: "Auto (fit to data)" has to mean the
  data on screen, i.e. the frame being shown. A **manual** clim always wins over
  both: the lock fixes auto-scaling, it does not overrule an explicit choice, and
  it is dropped when the displayed variable changes.
- **A colour range — pinned OR typed — belongs to ONE variable.** The lock always
  carried `_range_lock_var` beside `_range_lock`; the manual clim was one unkeyed
  tuple, so Auto off → Min/Max → Apply coloured *every* variable, and a pressure
  range rendered vorticity as one flat colour or one saturated blob with the
  Min/Max boxes still showing the old numbers as if they belonged to it —
  USER-REPORTED (2026-08-20, issue #24). It is now `_clim_by_var`
  (`dict[str, tuple]`), written by `set_clim` under the displayed variable and
  read by `render` for the variable it is about to draw; the same fact got the
  same shape rather than a second pattern. Four rules: **the MODE stays global**
  (one Auto/Custom checkbox with one meaning — making it per-variable would be a
  second hidden mode), so switching to Auto does not forget the numbers; **a
  variable with no remembered pair is SEEDED from its own data range on first
  render and remembered**, which is both what stops it inheriting another
  variable's numbers and what stops playback re-seeding (and so drifting) every
  frame; **precedence is untouched** — manual > lock > auto data range, enforced
  where it always was, in `playback_clim` returning None unless `_clim_auto`;
  and **the store is view state for the loaded result**, cleared by
  `load_result_path` / `clear` (a new run must not wear the old one's numbers)
  but deliberately kept across frames of one run. It is written ONLY through
  `remember_clim` / `set_clim` and read through `manual_clim`, `render`'s seed
  path included — the same reason `recordBoundaryEdge` is the only way to write
  a boundary edge's BC.
  The panel's Min/Max boxes follow the range in force through the existing
  `result_rendered` signal — never by reading canvas privates — and in Custom
  mode they are refreshed on exactly two events, because there they are an input
  the user may be halfway through typing: the variable MOVED, or the canvas
  reports `clim_seeded`, i.e. the range on screen is not one the user typed.
  **The seed flag is why the refresh is not keyed on the variable NAME**: a
  newly loaded run clears the store and re-seeds under the *same* variable name,
  so a name-keyed refresh left the boxes showing the previous run's numbers —
  verbatim the reported symptom, found in review of the first version of this
  fix and now its own check.
  And **the Auto checkbox IS the mode, in both directions**: unticking it used to
  tell the canvas nothing until Apply, so the panel showed the Custom box while
  the canvas kept auto-scaling every frame to its own min/max and the Min/Max
  boxes — no longer refreshed by the Auto branch — froze on the frame the untick
  happened on. That is the same "the boxes describe a range that is not on
  screen" symptom reached by the other route, and it needs a multi-frame run to
  see, which is why it is its own section in the gate. Unticking now seeds from
  the frame on screen, so nothing jumps at that moment.
  Gated by `tests/test_result_clim_per_variable.py` (8 properties, every one
  verified by injection — including both wrong versions found in review — with
  the one blind spot named in its docstring).
- **`set_result` reuses the triangulation when the incoming frame has the same
  nodes**, which also keeps probes/line/extrema alive across a step (they mark
  geometry, and the geometry did not move). Field caches are always dropped.
Frames are labelled by POSITION (`Frame 4 / 10`): the solver writes `t = "time 0"`
for *every* zone, so the file carries no real timestamp to show. Gated by
`tests/test_result_playback.py`, which pins the byte-range parse to be identical
to a whole-file scan, and `tests/test_result_clim_per_variable.py` for the
per-variable colour range.

**A restarted solve is ONE run split across several files, and it plays as one
animation** (`services/result_legs.py`, Qt-free — `list_result_legs` → a
`LegSeries` of `ResultLeg`s in playback order plus its warnings as data;
`ResultSeries` takes a LIST of paths). #32, USER-REQUESTED (2026-08-21), blocked
by #30 because it reads the `RUN.txt` #30 writes. #26 moves a finished run's
outputs into `work/prev_<NNN>/`, so the field output of a twice-restarted solve
is three files and the transport could only ever animate one of them — watching
the solve evolve meant opening each leg by hand and losing the animation at every
boundary. Rules that are load bearing:
- **A list, never a concatenated temp file.** The byte-offset index exists so a
  frame costs 0.07 s instead of 0.35 s; merging hundreds of MB would throw that
  away. So the per-file `tecplot_index` is untouched and a FLAT frame index sits
  above it — global frame *k* → `(file, zone)`. Three things become global with
  it: the numbering, the LRU **byte** budget (a solve restarted ten times must
  not hold ten caches) and every range `global_range` reports. A change in ANY
  file therefore drops EVERY cached frame and range, because the numbering shifts
  and a frame kept under its old global number would serve another leg's zone.
- **A leg is found by its STEM.** #30 renames an archived file's run tag to
  `.prev_<NNN>`, so one solver output is `xtecp_sol_allz.dat.gui` live and
  `xtecp_sol_allz.dat.prev_001` archived; `strip_archive_suffix` +
  `strip_run_tag` (the inverse of `archive_name`, and the reason `strip_run_tag`
  now exists in `case_files`) recovers the one name both carry. That also makes
  it work on **pre-#30 archives**, which kept `.gui` — measured on this repo's
  own `results/solver/case`.
- **Order by ITERATION COUNT; lineage answers a different question.** The first
  version of this said lineage was NOT recoverable and that was simply FALSE —
  found by the Spec axis. `case_archive.bare_link_for_archived_dump` links an
  archived dump into `work/` under its ARCHIVED name, so a `resumed_from` reading
  `binDumpZ.dat.prev_001` names that leg exactly, and #31's own
  `_last_resumed_basename` already relies on it. What lineage really gives is a
  PREDECESSOR relation, never a position: it says where a leg started, not how
  far it went, and two legs resumed from the same point are indistinguishable by
  it — which is exactly the re-run case. So `last_iteration` orders (creation
  order breaking ties) and lineage DETECTS the overlap.
- **A leg with no count is played WHERE IT RAN, not last** — a deliberate
  departure from the issue's "offered last", because that phrasing is right for a
  chooser LIST and wrong for a playback ORDER. Not academic: the FIRST version
  shipped the literal rule and the acceptance run against `results/solver/case`
  (two archives predating #30, so no note; only the live leg has a count) played
  the solve **backwards** — newest leg first, the two oldest after it. An unknown
  leg now inherits the last count recorded before it, which is creation order
  except where a recorded count says otherwise.
- **An overlap is REPORTED, never interleaved**, by TWO signals that catch
  different pairs. **Lineage**: two legs whose notes record the same start really
  did re-run one segment, and that holds when neither reports a count.
  **Non-monotonicity**: a leg that ran later reporting no higher a count, which
  is the only signal left when a note is missing. A blank start is deliberately
  not a key — "cold start" and "we have no record" must not match each other.
  Nothing is merged or spliced; both legs are named.
- **Ask, do not assume — and NOT asking means No.** The offer is a `confirm` with
  `headless_default=False`, and `load_result_path(..., ask_legs=False)` (passed by
  `postprocess_ctrl` when `_pipeline_running`) declines rather than opening
  everything silently: a caller that cannot put up a modal cannot consent for the
  user, and one file is what every caller got before #32. Declining yields a
  ONE-leg series rather than a second code path, so the cache, the labels and the
  ranges behave identically either way.
- **The variable selector is the INTERSECTION**, and the subtraction is logged
  naming the short leg. The derived quantities are recomputed from that
  intersection through the new `TecplotResult.derived_from_names` — a pure
  function of the variable NAMES, which is all the old availability test ever was
  — so a derived field cannot outlive its inputs either. Asking this from the leg
  with FEWER variables proves nothing (its own list is already the intersection),
  which is a hole the gate's own injections found.
- **The leg name prefixes a label only when the series has more than one file**
  (`prev_002 · Frame 3 / 10`), so a case that was never restarted reads exactly as
  it did. The transport's own read-out appends the SERIES position on top
  (`… (7 / 30)`) because every button here moves through the series; that is
  added in `_read_out`, not in `frame_label`, since the zone selector uses the
  label as a list entry where a second pair of numbers on every row is noise.
- **The per-variable seeded range is COMPUTED over the series, not just carried
  across it.** #24 seeds an untouched variable from the frame on screen so
  nothing jumps when Auto is unticked; across legs that basis is wrong — one
  leg's band saturates every other leg and the Min/Max boxes then describe a
  range that is not on screen, #24's own symptom one level up. So a MULTI-leg
  series seeds from the series and a single file keeps #24 exactly. The scan is
  the one "Lock scale" already pays (`scan_series_range`, now shared), and its
  `pump` argument is the difference between the two callers rather than a knob:
  the lock is ticked by a click and can pump the event loop to paint its message
  first, while the seed runs INSIDE `render`, where pumping would re-enter the
  paint in progress. The first version shipped persistence only and the Spec axis
  marked the acceptance item partial.
- `set_result`'s triangulation reuse and #24's clim precedence
  (manual > lock > auto) are unchanged and both are pinned across a leg boundary.
Three duplications this created were pushed to their owners rather than left:
`case_files.strip_run_tag` / `newest_first` and `case_run_note.mtime_stamp` /
`note_int` are each now read by both `restart_points` and `result_legs`.
Gated by `tests/test_result_legs_playback.py` — 13 injection-verified properties
over 3 groups, with its two blind spots and the acceptance run
(`results/solver/case`, a real twice-restarted solve) named in its own docstring.

**"The surface" of a surface plot is a CHOICE, and so is where s = 0 is**
(`services/surface_source.py` + `services/surface_sample.py`, both Qt-free;
`controllers/surface_source_ctrl.py` decides availability; `views/surface_source_dialog.py`
+ `views/result_canvas_surface_mixin.py` are the UI). Results ▸ **Surface…** used to
mean exactly one curve — the inner boundary loops of the solved triangulation —
which is the only honest answer for a body-fitted mesh and **no answer at all for
an immersed-boundary run**, where the solid never touches a mesh boundary. Six
sources are now offered, all listed even when unusable, each with the reason on the
row ("no STL3d φ field loaded (run the IB stage)"): `mesh` (unchanged, and the only
one whose points ARE mesh nodes, so it keeps `node_ids` and reads **exact** nodal
values), `field_iso` (φ = 0.5 on the solved mesh), `grid_iso` (the same on the
STL3d structured φ), `interface_cells` (**the Fit Δ points**, i.e.
`phi_quality.interface_points` — now public precisely so the plotted surface is the
one the fit report measured), `analytic` (the analytic φ shape itself, read through
`services/analytic_shape.py`, which the φ-DLL generator now shares so the plotted
body cannot drift from the solved one) and `cad`. Rules that are not cosmetic:
- **Iso-lines are chained by mesh EDGE identity, never by welding coordinates**:
  one crossing point per crossed edge, computed from the canonically sorted node
  pair so both owning triangles get the identical coordinate, then a walk
  triangle→triangle through shared edge keys. There is no distance tolerance
  anywhere — a tolerance on a fine mesh either fragments one contour or fuses two
  that merely pass close. Every crossing triangle has degree exactly 2, so a
  component is a cycle (closed) or a path (the iso-line left through the boundary),
  and `closed` is reported from *arriving back at the entry edge*, not guessed.
- **s = 0 is required, not defaulted (USER-REQUESTED)**: the old path inherited the
  origin from `next(iter(set))` inside the boundary tracer — reproducible for one
  file, but two runs of the same body could start their arc length in different
  places, which is exactly when you want to overlay the curves. Show/Plot stay
  disabled until a rule (x min / x max / y min / y max) is picked, traversal
  handedness is forced from the polygon's signed area, and the canvas marks the
  origin + direction while the plot's axis label repeats the coordinate.
- **Arc length of a closed curve now reaches the full perimeter.** The removed
  `TecplotResult.perimeter_series` computed the closing chord and then sliced it
  off, so its last sample was one chord short of where it started.
- **Off-node samples are interpolated, and δ = 0 by default.** For an immersed
  solid the interface holds the SOLID state, so an outward-normal offset δ (one
  cell is typical) is offered — but nothing is moved silently, and the title states
  `exact nodal` vs `interpolated, δ=…`. Outward comes from the polygon's own signed
  area, not from the requested handedness, or the offset would point *into* the
  body on exactly the curves that were reversed. Samples outside the mesh come back
  NaN (a visible gap), never a fabricated value.
- **The Fit Δ cloud is cell CENTRES with no connectivity**, so it is ordered by a
  greedy nearest-neighbour walk that can jump a thin waist or take the wrong
  branch; when a hop is >5× the typical one the curve says so in `note` instead of
  returning a plausible-looking arc length. Prefer the iso-line for measurement.
Nothing is extracted while the dialog is being edited — the widgets only build a
`SurfaceSpec`. Gated by `tests/test_surface_source.py` (geometry) and
`tests/test_surface_source_gui.py` (the dialog, the overlay and both result kinds).

**The grid must carry the BCs before it leaves the Mesh stage**
(`services/mesh_bc_audit.py`, Qt-free): a mesh generated BEFORE the per-segment
BCs were applied exports **every** patch as the wall default, and the solve then
looks exactly like a converged, unchanged answer — the reported "I updated the
STAR-CD boundary conditions and got the same result". The mesher's own
`NO boundary segment carries any of the GROUP_BC label(s)` warning fires at MESH
time, several clicks before the grid is exported, sent and run, so
`audit_mesh_bc()` re-checks the actual file at each of those three points
(`mesh_export_ctrl.mesh_bc_problems` / `warn_if_mesh_bc_stale`, and
`solver_ctrl._confirm_mesh_bc_state`, which *asks* rather than deciding —
`headless_default=True` so batch/CI, which regenerate in the same pass, are not
blocked). Two independent signals: an assigned BC **type** with no patch of that
name in the `.bnd`, and a geometry `.meta` **newer** than the mesh (the per-segment
BC and No-BL flags are projected there from the model on every edit, so its mtime
still moves when one changes — and changing one segment from inlet to outlet
leaves both names in the file, so content alone cannot see it). Note the two
namespaces this replaced a bug in: a `group_bc` key is a segment **label**, a
`.bnd` patch name is the **BC type** the mesher resolved it to — comparing them
directly (the old warning) marks every assignment missing on every run. Also:
BC detection resolves the .bnd the RUN will use (auto-link wins in
`_locate_mesh_bnd`, and `resync_solver_bc_from_group` runs *after* the auto-link),
or the table describes one grid while the solver reads another. Gated by
`tests/test_mesh_bc_audit.py`.

**A path is not a kind: project files are recognised by CONTENT**
(`services/project_file_kind.py`, Qt-free — `classify_project_file` → `"workspace"` /
`"pipeline"` / `""`; `PipelineConfig.classify_file` / `is_workspace_file` delegate to
it, so the extension never has to be right). `main.py` handed every positional
argument to the geometry loader, so `main.py case.hws` ran `np.loadtxt` over JSON and
reported `could not convert string '{' to float64` — a message naming neither the file
nor the problem. USER-REPORTED (2026-08-13). Every "open this path" entry point now
dispatches through the one classifier: the CLI's positional args,
`_load_geometry_file` (which the recent-files menu and the STL stager also reach), and
Pipeline ▸ Load, whose dialog accepts `*.hws` too. Rules: a **workspace opened in the
GUI goes to the workspace loader**, never through `PipelineConfig.from_workspace_dict`
— that conversion exists so the headless runner can *run* a `.hws` and deliberately
drops working state (cached resampled points, generated mesh/result paths, the active
tab); the CLI loads the **project first and geometry after**, because either project
load resets all state and closes every tab (geometry used to load at 100 ms and the
pipeline at 200 ms, so `--pipeline x.json geom.dat` silently discarded the geometry);
and only ONE project file is accepted per launch, the rest named and refused. The
"this will close all current tabs" prompt is gated on `has_unsaved_work()` — the GUI
always opens with one pristine blank session, so otherwise opening a workspace from
the command line put a modal in front of an empty canvas.

**The Output field's `.*` is a placeholder, and only one module may read it**
(`models/mesh_output_names.py`, Qt-free — `output_base` / `output_path_for` /
`FORMAT_PLACEHOLDER`, re-exported as `MeshConfig.*` so every existing call site is
unchanged; that module also owns `auto_case_name` / `auto_output_name` /
`is_auto_output_name`, whose `<case>` naming is mirrored in `src/cli.cpp`). The Mesh
panel's Output field holds ONE name for however many formats are enabled, so it is
filled in as `results/meshes/<case>/mesh_<case>.*` — and because the panel→model sync
runs on every edit, that string IS the model value and travels verbatim into the
workspace, the pipeline script and the mesher's config. Only the export dialog
understood it, in a private `endswith(".*")` branch, so: the **mesher** wrote a VTK
into a file literally named `mesh_<case>.*` (see `cli.cpp` above), and
**`pipeline_runner`** handed that name straight through and then `os.path.exists`-ed
it — which the glob-named file satisfied, so the run reported success and passed a
glob to the contour stage. Note the coupling: a C++-only fix turns that silent pass
into a hard failure, so both halves move together, and `_mesh_output_path` is split
out of `_run_mesh` to be testable without a mesh run. `tests/test_output_format_placeholder.py`
gates the resolver, the end-to-end `-out_name <dir>/probe.*` run (no file with a `*`
in its name, banner reports the resolved basename), and **statically fails the build
if any other GUI file grows its own `endswith(".*")`** — a second private copy is how
this diverged in the first place.

**The last generated mesh is not where a reopened case left it**
(`services/mesh_grid_lookup.py::resolve_case_grid`, Qt-free): Generate Mesh writes its
output into the GUI's **temp dir** on purpose (`<temp>/global_mesh.*`, so generating
does not litter the repo — the stable per-case files appear on Export / Send to
Solver), and that directory is removed on exit, so `global_vtk_path` is **always**
empty or dangling in a reopened workspace. Auto-link read only that and answered
`No mesh generated yet` for a case whose grid was on disk and whose own Grid
Conversion fields still pointed at it — USER-REPORTED (2026-08-13) together with the
`.hws` failure above. The resolver tries this session's mesh, then the triple the case
is **already wired to** (what the workspace restored, i.e. what the user last actually
sent to the solver — trusted over any guess), then the per-case exported mesh, and
takes the first whose `.vrt` + `.cel` + `.bnd` all exist; it names which one and why in
the log, and names every candidate when none works. `_locate_mesh_bnd` asks the SAME
resolver, or the BC table describes one grid while the run reads another. Whether that
grid is STALE stays the mesh-BC audit's job (`_confirm_mesh_bc_state`), not a refusal
to run. Both blocks gated by `tests/test_open_project_by_path.py`.

**A re-save of the geometry must not throw the Mesh-stage edits away, and the fix
is a MODEL FIELD rather than a wrapper around the subprocess.** Both halves of a
per-segment BC live in the `.meta` — the **label** in the NSEGMENTS bc column, the
label→type map in the trailer — and the resampler REWRITES that sidecar from the CAD
config on every save. It carries the trailer through verbatim but the bc column comes
back `-` and the v3 grow column comes back 1, so a CAD tweak + Save left the map
pointing at labels nothing carries: the mesher warns
(`NO boundary segment carries any of the … GROUP_BC label(s)`), every patch
exports as `wall`, and the GUI still shows the BCs it holds in memory. USER-REPORTED
(2026-08-12) as "I set the BCs in Edit Seg BC, why `no boundary patch named inlet,
outlet`?".

The fix is **not** in the resampler, which stopped preserving the prior sidecar
itself on purpose, because a NEW geometry written over an existing output name then
inherited the old geometry's flags (`tools/PreProcessor/src/main.cpp` says so in a
comment). It is also **no longer a caller-side snapshot/restore around the
subprocess** — that shipped first (`meta_io.snapshot_seg_edits` /
`restore_seg_edits`, three call sites) and is now **gone**, along with its
`describe_seg_edit_restore`. Both facts are `SegmentModel` **fields** instead: `bc`
already was one, and **`grow_bl` is new** (default True; `to_dict()` emits it only
when False, so every pre-existing config, workspace and script stays
byte-identical). The resampler has always read `sj["bc"]` and `sj["grow_bl"]` from
its own config, so `to_dict()` — the single serialiser behind the resample config
(`models/project.py`), the `.hws` workspace (`session_io_ctrl`) and the pipeline
script (`pipeline_config.cad_section`) — makes the sidecar come back **correct the
first time**. Measured against the real binary: `grow_bl: False` + `bc: "inlet"` in
the config survive a resample; the same config without them still comes back wiped
(so the mechanism is not redundant); and a *different* geometry over the same output
name inherits nothing, which is the reverted failure mode staying dead. The fact
moved **up**, not back down: the model knows which geometry it describes and the
resampler does not.

Three consequences worth knowing. **The `.meta` is now a PROJECTION of the model,
not a second home** — `mesh_layers_ctrl._write_sidecar_from_model` rewrites both
columns after every edit, and it is the command's `refresh_cb`, so an **undo rewrites
the file too**; reverting the model while the file kept the old column would leave the
mesher reading the un-undone value. Every existing reader (the BL dialog's seeding,
the mesher) therefore needs no change — the file still says what it always said, it
just no longer decides it.

**But a projection must be SEEDED first, and forgetting that broke the very thing
this work exists to fix.** The projection is total (every segment the model holds),
nothing ever seeded `SegmentModel.bc`/`grow_bl` from an existing `.meta`, and the BC
dialog reports only NEWLY MINTED labels — so on any geometry whose setup lived only in
its sidecar (i.e. every case predating the model field) one Mesh-stage BC edit reset
every *other* segment's label to `-` **and** re-enabled a No-BL wall it had never read.
Measured: four labels and one flag became one label and none — the same all-`wall`
export the model field exists to prevent. `_adopt_sidecar_facts` now takes the
sidecar's values into the model first, **fill-in only** (a fact the model holds wins; a
fact only the file holds is adopted — the same rule `ib_handoff` applies to a scripted
phi path), and it runs **BEFORE the undo snapshot**: adopting after it still fixes the
wipe but makes undo restore the *empty* value, re-wiping the sidecar it just protected.
Both the presence and the ordering are pinned separately in the gate, each verified by
injection. Adoption is a migration of the user's existing setup rather than an edit of
theirs, so it is not undoable and is **named in the log** instead — it also means
legacy labels start travelling in the workspace and the pipeline script, which is the
point of the candidate. A caveat that follows: the fill-in rule cannot distinguish
"the model holds `grow_bl = True`" from "the model is at its default", so a sidecar
`grow=0` is always adopted; that is right for the migration and would be wrong if the
file were ever allowed to lag the model, which the projection is what prevents. And **the id-set-changed refusal disappeared as a
concept**: the old restore had to drop everything when the segment id set moved,
because it re-applied by id after a subprocess had rewritten the file, and a label
bound to a segment object cannot be shifted onto its neighbour by inserting an edge.
The Mesh-stage dialogs consequently **emit** (`seg_grow_bl_changed` /
`seg_bc_labels_changed`) instead of writing the sidecar themselves — a view writing
that file is how the fact came to live only there. A geometry with **no CAD session
behind it** (an external `.dat` browsed in, or one left by a closed tab) has no model
to hold the fact, so the handler falls back to writing the sidecar directly; that is
correct for a geometry this app does not resample, and
`_session_for_geom_path` returning None is a normal outcome rather than an error. The
label→BC-**type** map (`GROUP_BC`) deliberately did **not** move: it is keyed by label
rather than by segment (one label covers many segments), so there is no segment field
for it to be a field of, and the resampler carries the trailer through verbatim, so it
never needed the rescue the label column did. Two knock-on effects of reusing
`UpdateMultipleSegmentsStateCmd`: a Mesh-stage No-BL toggle now sets
`is_geometry_modified`, so the CAD tab shows `*` and prompts on close — defensible,
since the flag is genuinely model state that must be saved to persist, and reverting it
would stop undo restoring the dirty flag.
Gated by `tests/test_seg_edit_carryover.py`, which drives the real
`surface_resampler` (so the wipe cannot quietly stop happening) and the real
controller handler (so undo, redo and the projection are proven, not asserted).

**Portable case export** (`services/case_export.py` + `case_export_docs.py`, both
Qt-free; Solver toolbar "Export Case ⇪" + Solver menu): copies a case's INPUTS into
a folder that reruns on another machine — `grid/` (mesh + `.def` + the getPGrid
sources, whose `para.in` travels as **`getPGrid.in`**: `_RENAMES` owns that mapping
so `run_case.sh --regrid` and the manifest cannot disagree), `work/` (`input.in`,
`.def`, `phi.dat`, and the restart dump **only when `input.in` restarts from it** —
`include_restart="auto"`, since `binDump*` is an output that only a restart run
reads back and is the largest file in the case), `dll/` (`.so` **and** the `.cc` it
was compiled from, pulled from `results/solver/dll_src` by basename), plus
`run_case.sh` and `MANIFEST.txt`. `run_case.sh` **suggests** a compiler rather than
choosing one (`CXX=${CXX:-g++}`, `CXXFLAGS`) — the package is for someone else's
machine, which may build with icpc. Selection is an **allow-list**, so a new output
file can never sneak in, and everything rejected is NAMED in the manifest (split
into known-output, not-used-by-this-run and unrecognised) — a skipped input is a
visible line, not a surprise on the far machine. **The allow-list matches on NAME,
so `work/phi.dat` and `dll/*` also have to ask whether the RUN uses them**
(`_unused_reason`): `prepare_case_dir` reuses a case directory in place, so a case
that once ran an immersed solid still holds both after being re-run without one —
USER-REPORTED (2026-08-12) as "I didn't configure IBM, why is there a phi.dat and a
dll/?". `input.in` decides, being the file the far machine actually runs: it
declares `immersed_solid` and it names every DLL it dlopens by quoted path (plus a
type-11 BC row in `work/*.def`, which is the one DLL `input.in` never mentions).
A `.so` that no longer travels also stops pulling its `.cc` out of `dll_src`.
`solver_case.report_stale_ibm_artifacts` names the same leftover at case-prep time
and never deletes it — with immersed solid ON but no phi field chosen, the init DLL
reads `phi.dat` by that fixed name, so the previous geometry's solid would converge
to a believable answer for the wrong shape. **Every quoted value in `input.in` is a file path**
(see `SolverConfig.generate_input_in`), and the GUI writes absolute ones for any
file the user browsed to; those are staged into `work/` and rewritten to
`./<name>`, which is the other half of portability. The solver binary is
deliberately excluded. Gated by `tests/test_case_export.py`; verified end-to-end
by regenerating the grid with getPGrid from the exported folder and running
unicones on it. Everything the export *writes* rather than copies lives in
`case_export_docs.py` (`run_case.sh`, `MANIFEST.txt`, the rewritten `input.in`,
and `write_extras`); the "is this file an input of THIS run or a fossil of the
last one?" reading of `input.in` lives in `case_export_usage.py`. Both splits
are the file-size budget, not new concepts.

**The package also reopens in the GUI, not just in a shell**
(`services/case_workspace.py`, Qt-free). `run_case.sh` reruns the SOLVER; there
is no importer for an exported case, so "load the case I exported" had no answer
— USER-REQUESTED (2026-08-13). Export Case now *asks* (a third prompt, after the
restart dump and the tarball) and writes `<folder>.hws` into the package via
`export_case(..., extra_files=...)`, so the manifest names it under its own
heading like everything else. Three rules decide whether the workspace is worth
shipping: **(1) re-point by file IDENTITY, never by string** — the map is keyed
by `(st_dev, st_ino)`, so `results/` vs `Results/` on a case-insensitive volume
or a symlinked scratch dir is still the same file, and a path the package does
NOT carry (the CAD `.dat`, the mesh, a declined restart dump) is left alone and
REPORTED in the log rather than rewritten to a name that resolves to nothing;
**(2) the caller's plan is the authority** — `export_case` now accepts `plan=`
because the workspace is derived from the plan, and a second plan built with
different arguments would describe a different package than the one on disk
(decline the restart dump and its path must stay put); **(3) the stamp survives
a move** — a package exists to be copied elsewhere, which strands absolute paths
a second time, so the exported workspace records `exported_case_root` and
`rebase_case_workspace` (called from `_read_workspace_file` on **every** load)
swaps that prefix for wherever the `.hws` is actually being opened from. Note
what does NOT travel: CAD/mesh sources are no part of a solver case, so the
geometry rides *inside* the `.hws` (`original_points` are stored verbatim) and
still draws, but re-resampling or re-meshing needs those files — the export log
and the manifest both say so. `Save Workspace` and the export share one builder
(`session_io_ctrl.workspace_dict()`), so an exported workspace can never
describe less than a saved one. Gated by `tests/test_case_workspace_export.py`,
which drives the real Export Case slot, moves the folder, and loads it back.

**Signal guards**: never write a raw `blockSignals(True)`/`blockSignals(False)` pair — an exception between them leaves the widget permanently unable to emit. Use `with block_signals(w1, w2, ...)` (`app/utils.py`). Likewise, never assign `_is_populating`: use `with controller.populating():`, which is a re-entrant depth counter (a bare bool let a nested populate clear the outer guard). `tests/test_signal_guards.py` statically fails the build on either.

**Error handling**: never `except Exception: pass`. Use `services/logging_setup.py::get_logger(__name__)` and log at `debug(..., exc_info=True)` for a step allowed to fail, or `warning` when the failure silently degrades what the user asked for. `HYBMESH_LOG_LEVEL=DEBUG` surfaces the debug tier. `tests/test_silent_exceptions.py` fails the build if a new undocumented silent handler appears.

### PreProcessor CLI (`tools/PreProcessor/src/main.cpp`)
- Reads JSON config via `nlohmann/json.hpp` (header-only, bundled)
- `detectFeaturePoints()` → `splitPolyline()` → `alignEndpoints()` → `distributePointsProportionally()`
- Spacing strategies: `uniform`, `curvature`, `cosine` (double-end dense), `geometric` (exponential), `tanh`
- Supporting headers in `tools/PreProcessor/include/`: `Spline.hpp` (cubic spline), `Spacing.hpp`, `Quality.hpp`

### Full Pipeline (CAD → mesh → solver → results, one action)
A single unified JSON script drives the whole chain; the GUI and the headless CLI share the same schema and stage logic.
- **`models/pipeline_config.py`** (`PipelineConfig`, Qt-free): the unified schema (`cads`/`mesh`/`solver`/`stl3d`/`results`, each mapping 1:1 onto `ProjectModel`/`MeshConfig`/`SolverConfig`/`Stl3dConfig`) + converters. `PIPELINE_FORMAT_VERSION` (v2). `cads` is a **list** — one entry per geometry, so a multi-body case round-trips; the singular `cad` key is still read and exposed as a property (first entry) for pre-v2 scripts. `from_workspace_dict()` turns a `.hws` workspace into a runnable script, so `run_pipeline.sh` accepts either. Examples: `config/pipeline/naca_demo.json` (single), `multi_element_demo.json` (multi-body).
- **`services/pipeline_stages.py`** (Qt-free, imports only the stdlib): **the stage set is declared once, and the two hosts are adapters.** The four stages — resample · immersed solid · mesh · solver — are implemented twice (`pipeline_runner` blocking and linear, `pipeline_ctrl` chained on QThread `finished_signal`), and until this module nothing knew the SET, so each host named, ordered and connected its own and the only thing comparing them was a reader. Two things followed. **An artefact could be produced for nobody** — the runner carried the comment *"before meshing, because the solver stage links the phi field it produces"* while `_run_solver` took no phi argument at all; that was candidate 6a, and the gate it left behind watches one artefact crossing one seam. **And the stage count was hand-written and already wrong**: `Stage 1/3`…`Stage 3/3` at 8 sites across the two hosts while four stages existed, because the immersed solid was logged outside the numbering in both — a literal denominator where the plan is a variable. Nobody typed a wrong number; there was no number to derive. It is deliberately **data, not a base class**: the one thing that legitimately differs between the hosts is how they WAIT, and a hierarchy would have to host that difference. It is **load-bearing rather than decorative** — both hosts build their run plan and their `Stage i/N` labels from it (`plan()` / `label()`), measured on the shipped scripts: `ib_demo.json --no-solver` now reports `Stage 1/2: immersed solid` / `Stage 2/2: mesh generation` where the IB stage used to be unnumbered and the mesh claimed `Stage 2/3`, and `naca_demo.json --no-solver` reports `Stage 1/1` for the one stage it runs; a table nobody reads goes stale exactly the way the prose comments did. `PipelineConfig.stl3d_skip()` joins `cad_skip`/`solver_skip` so "will this stage run?" has one shape for all four. Gated by `tests/test_pipeline_stages.py`, whose checks are shaped by two lessons: **both directions or it is not a gate** (checking only that every declared stage is implemented lets a `_pipe_foo` added to the GUI alone pass), and **order is recovered, not assumed** — the GUI's chain is read as a reachability graph over `self._pipe*` **references**, not calls, because `_pipe_chain("_mesh_worker", self._pipe_after_mesh, …)` hands the continuation over as an attribute and a call-only walk misses every second link. All ten failure modes are verified by injection in the test itself, permanently, rather than by hand at review time — and a review of the first version is why three of them exist: **"both hosts read the declaration" was a SUBSTRING check** (`"pipeline_stages" in src`), which was broken in one line by keeping the import and replacing the label calls with plain strings — all 27 checks passed while a host derived nothing, so 2a/2b now assert each host passes **every declared stage key** to its label adapter; **4d measured against the wrong "first stage"**, because `run_full_pipeline` never names the CAD stage (it goes through `_pipe_resample_next`), so the plan could be fixed *after* that stage started with 4d still green; and **`plan()` silently ignored an unknown key** — measured, `plan({"resamlpe": True, …})` dropped the resample stage and mis-numbered every label, this candidate's own defect returning without a wrong number being typed. Two smaller lessons from the same review: an injection that makes the source **fail to parse** looks exactly like the check working (every mutation now compiles its result or asserts the text changed), and a check with an **exemption marker** is an escape hatch for whoever next trips it.
- **`services/pipeline_runner.py`** (Qt-free, blocking): runs the 3 CLI stages via subprocess (surface_resampler → HybMesh2D → getPGrid→unicones); `run_pipeline()` returns the produced artifact paths.
- **`services/ib_handoff.py`** (Qt-free): **producing a phi field is not the same as wiring one up**, and the gap between them is where a whole immersed-solid run used to disappear. STL3d writes a *Tecplot* field (3 header lines, then `x y z phi`); the solver's init DLL reads a *headerless* `phi.dat` with the STL3d grid spec baked into the DLL source. That conversion existed only inside `stl3d_ctrl.send_stl3d_to_solver`, a Qt method no headless runner can call — so `run_pipeline` collected the stage's output into `out["phi"]` and passed it **nowhere** (`_run_solver` built its SolverConfig from the script alone), and GUI **Run All had no IB stage at all**. Either way the solve fell back to whatever `work/phi.dat` the reused case dir still held: the PREVIOUS geometry's solid, converging to a believable answer for the wrong shape — the same failure `solver_case.report_stale_ibm_artifacts` warns about from the other end. `link_phi_to_solver()` is now the one owner, called by all three hosts. Three rules, none of them cosmetic. **`PHI_HEADER_LINES` is checked against the `skiprows=` its own reader uses** — one number, not two guesses. **The phi field and the init DLL are ONE fact, so it takes over both or neither**: the DLL has this stage's origin/spacing/counts compiled in and can therefore only read the field this stage traced, so pairing a caller's phi with our DLL (or ours with theirs) hands the solve a field read on the wrong grid — a wrong answer rather than an error. A real case in `config/pipeline/` does exactly the thing that would have broken: an analytic-shape `init_cond_dll` with `ibm_phi_file` blank. Only when both are blank does the stage supply both; naming one keeps both and warns, because a phi with no DLL is never read. **`replace` is the difference between the callers** — the GUI hands over a field computed *now* so it overwrites, while the headless runner auto-links a *scripted* case so explicit wins and only blanks are filled, exactly the rule `_run_solver` already applies to `.vrt`/`.cel`/`.bnd`. What the hand-off deliberately does **not** decide is whether the solve has an immersed solid at all: `immersed_solid` stays the CALLER's declaration, for the same reason the motion preset is left alone — a script saying `immersed_solid: false` has as much standing as one that configured a moving body, and a stage may not overrule it. It is `send_stl3d_to_solver` that turns it on, because a button is allowed an opinion a pipeline stage is not; Run All and the headless runner obey what the Solver stage declares and log the field as traced-but-unused otherwise. Gated by `tests/test_pipeline_ib_handoff.py`, which drives the real conversion, proves the chain by AST, **compiles the generated DLL** (`stage_dll` returns `""` with a mere WARNING on a compile failure, so a source that does not build degrades silently to "no init DLL"), and loads `config/pipeline/ib_demo.json` — the first script to carry both an `stl3d` and a `solver` section, whose absence had left the section→config converter untested. Writing it found that a **relative `stl_path` was never resolved** (every other section takes a repo-relative path, but the IB stage validated this one against the process cwd), so `build_stl3d_config(repo)` now resolves it like a CAD input.
- **`services/solver_case.py`** (Qt-free): case-dir orchestration (`results/solver/<name>/{work,grid,dll}`), extracted so the GUI's solver worker and the headless runner share one source of truth. It also answers **where a case lives** (`case_root_for` / `work_dir_of`), which three callers used to join by hand. (`solver_ctrl._prepare_case_dir`, a synchronous wrapper this sentence used to name, was deleted in #31: the interactive Run path stopped calling it when the worker took over, and nothing else ever did.) **The grid stem is the RESOLVED case name, not the requested one**: auto-versioning renames the *directory* (`case` → `case_002`), and a stem left on the pre-version name writes `case.grid` into `case_002/`. That runs — `input.in` names the file it just wrote — so it stays invisible until the user later types the versioned name by hand and the same directory ends up holding `case.grid` *and* `case_002.grid`, two 1.3 MB grids distinguishable only by which one `input.in` references. USER-REPORTED (2026-08-13). **`prepare_case_dir` is the ONE place that makes a path in `input.in` relative to the work dir** — the grid/bc as `../grid/<case>.*` (`grid_rel`/`bc_rel`), the IBM DLLs as `../dll/*.so`, a BC type-11 DLL as `./x.so`, the phi field staged into `work/` under a fixed name. Of the paths it *knows about*, the **two restart references were the only ones nothing touched**, so `_autofill_restart_from_last_run`'s deliberately absolute path (it is what makes the field browsable) reached the solver verbatim and a GUI restart errored out — while an *exported* case ran, because `case_export` already relativises exactly these references. USER-REPORTED (2026-08-20, issue #25). `restart_refs_for_work_dir` rewrites an **absolute path to an existing file** — inside `work/` → its bare basename, elsewhere → a relative path out and back — and passes a blank, an already-relative or a non-resolving value straight through (`solver_ctrl._validate` already refuses a restart with no dump, and a wrong path must surface as the solver's own error rather than be rewritten into something that looks valid). Three things are load bearing. The dump is **referenced, never copied** — it is the largest file in a case, which is why `case_export` treats it specially, and a copy would leave two dumps whose relationship nothing records. The relative path really is **out and back** rather than a basename: the panel computes the dump's path from the case *name*, **before** `resolve_case_root` may auto-version the directory, so a run landing in `<case>_002/` genuinely restarts from `<case>/work/`. And the result is **returned into `generate_input_in` (`zdump_rel`/`convg_rel`, exactly like `grid_rel`) rather than written back onto `cfg`** — the one place this departs from the staging around it, because it is the one value `prepare_case_dir` cannot RE-derive (`output_grid_file` is rebuilt from `case_name` every run): `cfg` is the model the `.hws` and the pipeline script are saved from, and a work-dir-relative value stored there resolves to nothing from the next, auto-versioned work dir. Gated by `tests/test_restart_paths_relative.py`, which also pins that `case_export` still recognises the now-relative reference and that the package's own `input.in` resolves — the plan decides by which file a reference RESOLVES to, so the dump must not start looking like an unreferenced output and get dropped. **The last three of the nine quoted paths got the OPPOSITE answer, and the difference is SIZE** (#29, found in review of #25 rather than reported): `mpi_comm_map_fn`, `cfl_schedule_fn` and `probe_points_def_fn` were emitted with `.strip()` and nothing else, and two of the three are `"path"` field specs with a file dialog behind them, so the GUI routinely put an absolute path on this machine into them. `table_refs_for_work_dir` **copies** the file into `work/` and quotes the bare name, where the restart dump is referenced and never copied — a table is small, and a case that does not hold its own inputs is the problem; the dump is the largest file in a case. Three shapes, one of which copies: a **bare name** is emitted unchanged (already relative to the solver's cwd, and the intended form for a CFL schedule) but still **reserves its basename**, or a later field's absolute path with the same basename lands on the file it quotes and the run is handed one table twice; a **path to an existing file** is staged under a collision-safe basename; anything that does **not** resolve is emitted unchanged (#25's rule 4). Copy, never move and never hard-link, per `case_sources`. `cfg` is not mutated, for `restart_refs_for_work_dir`'s reason. The claim to make is narrower than the tempting one, and the tempting one is what created this ticket: **every quoted path that RESOLVES is now work-dir relative.** A value naming nothing is still emitted verbatim and absolute — deliberately, so it surfaces as the solver's own error — and so is a table named like a run output (`^binDump`, `.plt`), because numbering cannot escape a rule anchored to the name and a copy under that name would be archived aside or skipped as an output. Do not upgrade this sentence to "every quoted path" without re-reading `_stage_table`. Two neighbours had to keep up, because staging made a user-named file appear in `work/` for the first time: `case_export`'s planner would have listed the two with no allow-listed suffix under INCLUDED (via `_resolve_input_in`) *and* under a SKIPPED heading in one manifest, so a file `input.in` REFERENCES is no longer also reported as an unrecognised skip — the allow-list is deliberately **not** widened (a reference is a fact about this run; a suffix would be a glob over every future one); and `case_archive` would have called it "not a recognised solver input or output", a false statement about a file this toolchain staged, so `_staged_by_name` reads the previous `input.in` for the names no list can hold. The two facts about what a work dir already means live in `case_files` (`WORK_STAGED`, `staged_bare_names`) rather than being restated at each call site, because the restated version had **already drifted**: a type-11 BC `.so` was in the archive's list and not in the stager's. And the reservation asks whether the file EXISTS — which is both more precise (only `<case>.bc.def` is at risk, not every `.def`) and what makes the counter TERMINATE, `input.in` excepted because it is the one file written *after* staging. The resolvers moved to their own module, `services/case_input_paths.py`, when `solver_case.py` passed the size budget — the same split `case_archive` got, and for a concept rather than only a file: "what should `input.in` say here?" is one question with nine instances. Gated by `tests/test_input_in_staged_paths.py` (10 properties over 42 assertions, every one verified by injection). Four of them exist because a review or an injection found a real defect in the first version, which is the honest record of how this landed: a bare name did not reserve its basename; two checks would have passed on an absolute path because `os.path.join` with one returns it unchanged; the reservation missed the `.so` and every run output; and `case_export`'s new "a reference is an input" branch sat **ahead of** the output test, so a restart's convergence file — referenced by `input.in` and produced by a run — was silently packaged as an input and the "deliberately NOT exported" warning vanished with the `skipped_output` entry it is built from. That last one is a regression this change introduced in code the ticket only asked to leave working. What is **not** fixed is where bDecompose runs: it still writes the comm map next to its own binary, outside the case, so staging fixes the reference and not the production (#37). And no acceptance claim here is stronger than the evidence: `unicones` ships as a binary with no source and no case in this repo sets any of the three keys, so unlike #25/#26 nothing was measured on the solver — the justification is self-containment and one rule for all nine, and the target shape is already proven runnable by `case_export`'s own acceptance run.
- **`services/case_archive.py`** (Qt-free): **a restart continues in the SAME case dir, and must not write over what it resumed from.** The case-dir prompt had two answers and neither fit a restart (USER-REPORTED 2026-08-20, issue #26): *Overwrite* reused the directory and then wrote over the previous run's dumps and convergence history as the new run produced its own — **including the dump being resumed from**, so a crash part-way through a dump write could leave no usable restart point at all — while *New Versioned Dir* preserved them by splitting one continued solution across `<case>/` and `<case>_002/`. The destructive option was the only one that did what the user asked, and the dialog said nothing about restart. `archive_previous_outputs()` now puts the previous run's outputs beyond this run's reach before it writes anything. **Two facts about the solver decide the shape, and both were measured on the real binary rather than inferred** — the first version of this fix shipped without an acceptance run and was wrong. **(1) The restart reference must be a BARE name in the work dir.** Point `zdump_fn_restart` at `prev_001/binDumpZ.dat.gui` and the solver derives a per-zone path out of it — `binDumpZ.dat.prev_001/binDumpZ.0` — into a directory that does not exist, and the run dies with `Can't open file` (USER-REPORTED against the first fix). **(2) It must DIFFER from the solver's own output dump name**, which is `binDumpZ.dat` + the `-t` tag — i.e. exactly the file a GUI restart resumes from, so *every* same-folder restart was already rewriting its own restart point in place (measured: the source's checksum changes). The issue framed that as a crash-window risk; it was in fact happening on every run. So: every output moves into a fresh `work/prev_<NNN>/`, **the zone dump included, and `work/` keeps a bare-named HARD LINK to it** — bare, so no derivation happens, and differently named from the solver's own output dump, so this run cannot land on it. The convergence file has no such constraint (measured: a subdirectory path there runs clean) and just goes into the archive. **The link, not a rename in place, is #30's correction of #26** (2026-08-25): #26 had to leave the dump itself out in `work/`, so the archive was never complete and on the *next* restart that file was just another output — prev_001's dump filed inside `prev_002/`, a wart `tests/test_restart_archive.py` check 4 pinned as behaviour. One inode satisfies both halves at once: the archive holds the file, `work/` holds the name the solver requires, and the case grows by ~0 bytes (measured on the reported case: 24352 KB -> 24356 KB across an archive whose dump is 1597 KB). **This is the ONE place this repo's "a hard link is not the cheap version of a copy" rule (`case_sources`) flips, and for that rule's own reason** — there the hazard is that editing one path rewrites what the case holds, and a zone dump is never edited. A stale link is retired by INODE (`_archived_inodes`): a work-dir output whose bytes are already inside an archive is unlinked, never moved, so the archive it belongs to is never added to by a later run. A file that is already `.prev_NNN` and is *not* a link (a copied tree, or #26's own rename left on disk) is filed into the archive it is already named for — which is how a case that predates #30 upgrades, measured on the real `binDumpZ.dat.gui.prev_002` this repo still carried. **And every archived file ends in `.prev_<NNN>`** (`case_files.archive_name`): a trailing run tag is replaced (`unicones.enorm.gui` -> `unicones.enorm.prev_001`), a name without one is appended to (`fort.11` -> `fort.11.prev_001`), and a name that already carries a suffix is left alone rather than re-tagged onto a run it did not come from. Two consequences. The run tag is the information that rename discards, so **`RUN.txt` is where it survives** (below). And `is_run_output` now **strips the suffix before matching**, because two output patterns anchor on the END of the name (`\.plt$`, `^fort\.\d+$`) — without it an archived `fort.11.prev_001` would be reported as "not a recognised solver input or output", a false statement about a file this toolchain named itself; widening the patterns instead would loosen them for every future name, and seeing through a suffix this repo creates does not. Rules: **an allow-list decides, not a glob** — only what `case_files.is_run_output()` classifies as produced-by-a-run moves — **that list, and `ARCHIVE_DIR_PREFIX`, live in `services/case_files.py`**, a module both this and `case_export` import as peers, because they are facts about a case rather than about an export (putting them in `case_export` made the exporter the owner of a name the archiver creates, and forced a one-way import that then had to be apologised for in a comment), the inputs `prepare_case_dir` stages (`input.in`, `*.def`, `phi.dat`, a type-11 BC `*.so`) **stay** or the resumed run restarts into nothing, and a file **neither** list recognises stays put and is **named in the log**; **move, never copy** (the dump is the largest file in a case); **nothing is created when nothing moves**, which is what lets a caller pass `archive_prev` without first asking whether there is anything there; and `prev_<NNN>` **never clobbers either** — but where `resolve_case_root` gives up by overwriting the default dir (costing a re-run), an exhausted counter here archives **nothing** and says so, because giving up the other way would be the exact destruction the archive exists to prevent. **That refusal has a second instance, and the archiver used to commit the destruction it names** (#42): the rename REPLACES a run tag, so `xtecp_sol_allz.dat.cli` and `xtecp_sol_allz.dat.gui` — one output of one case run by the two hosts — both want `xtecp_sol_allz.dat.prev_001`, and the second `shutil.move` landed on the first with no warning, an entire run's field output and convergence history gone and the survivor decided by directory listing order. Reachable without misuse: the headless pipeline auto-versions and never lands on an occupied case dir, so the one route is headless first (`.cli`), then a GUI run answering *Overwrite* (`.gui` joins it), then a restart — every step an answer the toolchain offers. `case_files.archive_name_collisions` asks it ONCE over the set about to move, in the module that owns the mapping (a per-move check can only see a collision from one side, and by then the other file has moved), and it is asked **before the retire loop**, i.e. before ANY move, so a refusal is a no-op the user can retry rather than a half-archive. Refused wholesale, not pair-by-pair, and the message names both files, the name they both wanted and the *reason* — that archiving drops the run tag, which is invisible from the file names alone. Two details of that message are load bearing. It reports the **concrete** `prev_<NNN>`, which costs the counter a directory scan, so the counter is asked only once a refusal is certain — detection itself is a dict build, since a pair collides under every suffix or none (`ARCHIVE_SUFFIX_PLACEHOLDER` is the fallback when the counter is exhausted, and the same constant `archive_notice` uses). And it does **not** say the run continues "beside" the files it declined to move: the refusing run carries one of the two tags itself, so it writes over the half of every pair that shares it — the dump it resumes from included — which is #26's hazard returning through the door the Overwrite disposition leaves open (out of scope in #42, said out loud here rather than softened, the same rule that keeps `resumed_from`'s `None` and `""` apart). Renaming around it was rejected twice over: keeping the tag breaks #30's one-archive-one-scheme rule exactly where a reader most needs it, and numbering the second file invents a name that says nothing about which run it came from. **The restart reference follows the file** — `restart_refs_for_work_dir(..., moved=)` consults the move map *before* the existence check, since at its old path the dump is now gone and "does not resolve" would send the run's own restart point through the pass-through branch. The map is also the **one** thing that rewrites an already-*relative* reference: #25's rule 3 passes those through untouched, but a bare `binDumpZ.dat.gui` (hand-written, or reloaded from a `.hws` / pipeline script — the autofilled absolute path is not the only way that field is filled) names nothing once the file is in `prev_001/`, so the rule is narrowed by exactly the one file this run moved and by nothing else. That is why #26 was blocked by #25: the re-pointed reference is only usable because it is emitted work-dir relative (`prev_001/binDumpZ.dat.gui`). `cfg` still keeps its absolute path to `work/`, unchanged and right — the panel's field means "the dump in this case's work dir", which the *next* restart archives in its turn. The choice is one value, not a pair of booleans: `solver_case.CASE_ARCHIVE` / `CASE_IN_PLACE` / `CASE_NEW_VERSION`, mapped to `prepare_case_dir`'s two mechanical flags in one place (`case_dir_flags`), which **raises on an unknown value** rather than resolving it — `(False, False)` is a real disposition (auto-version), so a typo would otherwise run silently in a directory nobody chose. The prompt is `views/case_dir_dialog.py::ask_case_disposition` (extracted so `solver_ctrl` stays inside the file-size budget, and testable without a controller), and **a restart no longer reaches it** — #31 took that branch away, because once the start point is picked from the case's own history there is nothing left to ask, so `_resolve_case_disposition` returns `CASE_ARCHIVE` and says so in the log instead. What is left is the non-restart question, unchanged; headless returns `CASE_NEW_VERSION` without showing anything. `CASE_ARCHIVE` is deliberately not an answer the dialog can give any more: a branch nothing can reach reads as a working feature. **`case_export` had to learn to see the archive**: `plan_export` skipped every non-file entry silently, so a nested `work/prev_001/` was neither shipped nor named — the same bug class as `plan_export` once walking only one level deep. Each archive is now walked as its own subdirectory with **nothing** allow-listed (every file in it is an output by construction), so its contents are named as skipped except the dump `input.in` quotes, which ships for the same reason the one in `work/` does. That also forced the reference match from BASENAME to the resolved path: an archived restart legitimately leaves two files called `binDumpZ.dat.gui` in one case, and basename matching shipped both. **Each archive carries a `RUN.txt`** (`services/case_run_note.py`, Qt-free — writer *and* reader, so the format round-trips instead of being prose only a human can parse): the timestamp, the run tag, what that run itself resumed from, the zone dump's archived name, and how far it got. Two of those have to be RECOVERED rather than remembered, because the run is over: the tag is read off the file names *before* they are renamed, and the iteration count comes from the LAST ROW of the run's own convergence history — the solver prints `Global Iteration count` to stdout and by archive time that is gone. It is recorded as `last_iteration` with the print interval beside it (`convergence_interval`, read from the same `input.in`), and **the two together recover the count the solver printed**: it writes one row every `print_convg_per_niter` iterations and none for the final one, so `1990 + 10` is exactly the 2000 the acceptance run measured. **That arithmetic is a REVERSAL of what #30 and #31 recorded** (#43): both wrote down the argument that naming 2000 would be a *fabrication* and rendered the figure as the bound `1990+`, which overruled #31's own specification (a bare `iteration 2000`). The argument's own evidence contradicted it — the archive gate stated the bound as `[1990, 2000)`, a half-open interval that **excludes the value it claims to contain**, and that sentence sat in a gate for two issues. What survives of the caveat is that an *interrupted* run got no further than the printed count, i.e. the sum is an **upper** bound, and that belongs in a tooltip rather than in a refusal to name the number. The arithmetic now has exactly one home, `case_run_note.iteration_span` (below); the wrong reasoning is a useful specimen, because it was not a typo but a considered argument written down with its evidence, and it survived because the evidence was never checked against itself. An unreadable history reports **-1, never 0**, since 0 is a real answer the solver prints for a cold start — and `resumed_from` has the same three states for a sharper version of the same reason: a work dir with no `input.in` never ran a restart (`""` → "cold start"), while an `input.in` that exists and cannot be READ returns **None**, because "we could not tell" rendered as "cold start" would be a positive false claim in the one field #30 exists to provide, on a case whose history the reader cannot check any other way. `RUN_NOTE_NAME` lives in `case_files` beside `ARCHIVE_DIR_PREFIX` for that constant's own reason — the export has to know the name, and the module that writes it must not become the owner of a name the export reads. `RUN.txt` is the one file in an archive that does not end in `.prev_<NNN>` — deliberately: it is the archive's own record rather than something the run produced, and #30 asks for it by that name. `case_export` names it as a skipped OUTPUT rather than letting it fall through to "not recognised as a solver input"; it does not ship, because the package carries a case's inputs. The **run tags themselves are declared once**, in `case_files.RUN_TAGS` — `solver_ctrl.SOLVER_TAG` and `pipeline_runner.SOLVER_TAG` are now that constant and `restart_points` reads the same tuple, because a rename rule that strips a tag nobody writes silently does nothing. Gated by `tests/test_restart_archive.py` (9 properties against the real `prepare_case_dir`, the real export planner and the real dialog — property 9 is #42's, with the guard's absence INJECTED to measure the destruction it prevents and a negative control that a one-host work dir still archives unchanged) **and by `tests/test_case_export.py` check 16**, which is where the exporter's own gate has to see an archive — the archive's behaviour proven in the archive's test says nothing about a planner nobody re-pointed at it, with a negative control pinning that the move map is load bearing rather than redundant, plus the acceptance evidence the design was derived from, recorded in the test's own docstring: the real `prepare_case_dir` over the reported case and then the real `unicones` binary on its output — **exit 0, `Global Iteration count 1000`** (a cold start reports 0), restart source byte-identical afterwards, archive intact. #30 was accepted the same way and on the same case, twice in a row (`Global Iteration count 2000` then `4020`, source sha256-identical both times, `prev_003/` byte-for-byte untouched by the second restart and its dump back down to one link). One measured residue is named and left alone: #25's cross-case reference (`../../own/work/binDumpZ.dat.gui`, which auto-versioning produces) does resume correctly, but the same derivation leaves an empty `binDumpZ.dat.0` in the work dir.
- **`services/restart_points.py`** (Qt-free) + **`views/panels/restart_chooser.py`**: **the restart point is PICKED from the case's own history, not typed as a path.** USER-REQUESTED (2026-08-21, issue #31), blocked by #30 because it reads the `RUN.txt` #30 writes. After restarting once the next run is one of two intentions — **continue further** from the newest dump, or **re-run the same leg** from the dump the *last* run resumed from, having looked at the results and wanted that segment redone — and a `Restart` tick plus a free-text `zdump_fn_restart` expressed neither. The autofill (`_autofill_restart_from_last_run`, now gone) looked for a fixed `binDumpZ.dat` + `.gui`/`.cli` **in `work/` only**, so it knew nothing about the `work/prev_<NNN>/` archives #26 creates: "re-run the same leg" meant the user remembering which file that was and browsing to it, while the thing actually being decided is an **iteration count**. `list_restart_points(case_root)` now returns the rows — cold start, the newest un-archived dump in `work/`, then each archived leg newest-first with the iteration count, timestamp and run tag from its own `RUN.txt` — and the chooser is one column of radio buttons over them plus an "Other file…" escape. Rules that are load bearing:
  - **The MODEL still holds a path**, and an absolute one (#25): `SolverConfig.restart` / `zdump_fn_restart` / `convg_fn_restart` are unchanged, so `.hws`, pipeline scripts, `case_export` and `prepare_case_dir` are untouched and "Other file…" stays honest. What changed is that **one control authors all three** — the three `FieldSpec` rows are gone and the names are declared in `SOLVER_EXTRA_AUTHORED` with their reason, because three widgets for one decision is the duplication the field-spec tables removed, and a tick in a different place from the thing it restarts FROM is the interface the issue is about.
  - **Radio buttons, not a list widget, and the control reports its own edits.** `undo_ctrl._wire_widget_edits` is the ONE traversal that knows "the user touched this panel" (and therefore refreshes the model), and it connects spin boxes, combos, line edits and *checkable buttons* — a `QListWidget` selection is none of those. The rows are also **rebuilt whenever the case changes**, i.e. long after that one-shot traversal ran, so a composite control declares **`panel_edited`** and the traversal connects that. Measured: deleting that one loop leaves every panel-level check green and fails only `test_restart_chooser.py` check 12, which is why that check drives the real `AppController` instead of reading the panel.
  - **The list is derived on every call and cached nowhere** — the case dir is the truth, a `.hws` reopened after the case moved on must not offer rows that are gone, and it is re-listed on a case-name edit and after every run. The cost is stated rather than optimised away (one small `RUN.txt` per archived leg per keystroke); a cache is the thing this rule forbids.
  - **The marker is matched by BASENAME.** The last run's reference comes out of `work/input.in`, and for an archived dump it is the bare name of a hard link (#30) that the *next* archive retires — so the file that reference named is gone while the bytes keep that basename inside `prev_<NNN>/`. Matching by path or inode would lose the mark on exactly the row #31 exists to highlight. `resumed_from`'s three states are kept apart for its own reason: "we could not tell" must not render as the claim "cold start", which here would MARK the cold row.
  - **Every leg's count comes from one function, `case_run_note.iteration_span`** (#43), which prefers an archive's `RUN.txt` and falls back to the convergence history the archive holds. #31 shipped the opposite rule — an archive with no note got a row with the count "unknown", its history *deliberately not re-read*, on the argument that a second computation would be a second answer — and that rule cost exactly the legs it was meant to protect: an archive predating #30 read `iteration unknown` with every number needed sitting inside it, while `_latest_point` two functions below computed the live row's count from that same kind of file with that same reader. One module was applying a computation to one leg and refusing it for its siblings. There is still one answer; it is just no longer read from one place. A leg whose span cannot be computed at all still gets a row, unlabelled — hiding a restart point that exists is worse than showing it without a number. The count reads `iteration 1000`, not the bound `990+`; see the reversal recorded under `case_archive` above, and note that the *chooser* and the *Results leg list* now consume the same answer, so the two windows cannot describe one folder differently.
  - **A restart source inside an archive gets a bare-named hard link in `work/` on demand** (`case_archive.bare_link_for_archived_dump`, called by `prepare_case_dir` *before* the archive step and independently of `archive_prev`, feeding the same `moved` map). Without it the chooser's headline click produces `prev_001/binDumpZ.dat.prev_001` — the exact reference #26 measured the solver dying on — so offering older legs is not a view-only change. It refuses rather than guesses in two places: a name already taken by a different file is not overwritten, and a filesystem that cannot make the link gets a warning instead of a silent second copy of the largest file in the case.
  - **A restart whose source is not there is refused in the GUI.** `_validate_solver_config` used to check only that the field was non-empty, so a stale path reached the solver and died there with a message naming neither the field nor the file. Both references are now resolved (a relative one against this case's work dir) and named with their missing path. The chooser closes most routes to that state — it can only list files that exist — but "Other file…" and a restored workspace still reach it.
  - **The case-dir modal is dropped on the restart path** (CONFIRMED 2026-08-21) and Run All is untouched: `_pipeline_running` is still checked first, so batch keeps auto-versioning without a modal. One confirmation step fewer is the point, so the archive step has to be legible in the log on its own — `_resolve_case_disposition` names the concrete `work/prev_<NNN>/` and what happens to the dump. An explicit overwrite-in-place escape belongs somewhere non-default (#33).
  - **`case_root_for` / `work_dir_of` live in `solver_case`**, which already owns a case's layout, and `restart_points` re-exports them — the panel, the validator and `_resolve_case_disposition` all ask one function instead of joining `results/solver/<case>` themselves. The claim to make is exactly that narrow: the first write-up of this said "where a case lives has one spelling" and it was **false** — 11 `results/solver` joins exist and one full case-root construction was replaced. `resolve_case_root` takes its root as an argument (so a test can move a whole run) and builds the versioned siblings inline; `case_export_ctrl` asks the same question for its dialog's starting guess and is the one remaining candidate; `postprocess_ctrl`, `solver_tools_ctrl` and `dll_builder_dialog` ask for the PARENT dir or for `dll_src`, which are different questions. Found by the Standards axis, which enumerated the call sites the sentence claimed to cover — the same overclaim #25/#29 record.
  - **One departure from the issue's own text, and one REVERSED.** The rows first showed the count as a **bound** (`1990+`) where the issue's mock showed a bare `iteration 2000`, on the argument that printing the spec's number would be a fabrication. **#43 reverses that**: `1990 + 10` recovers 2000 exactly, the rows read `iteration 2000`, and the tooltip carries both surviving caveats (recorded vs recomputed, and that an interrupted run makes it an upper bound). The departure is recorded here rather than deleted, so "we deliberately departed from the spec" is not left standing as a validated precedent — it was overruled, and the spec was right. The remaining departure stands: the issue says this keeps "`prepare_case_dir` untouched", which it does not: `bare_link_for_archived_dump` is called from it, because without the link the chooser's headline click is unrunnable (test check 11 was RED before it existed).
  - One residue, named rather than fixed: **a case-name change keeps the previously picked absolute path**, so it can land on "Other file…" as a cross-case restart the user did not deliberately choose. It is visible in the row's own field, it is a configuration #25 supports, and `_validate` refuses it if the file is gone — no worse than the retired autofill, which pointed at whatever `work/` held.
  Gated by `tests/test_restart_chooser.py` (12 properties / 42 checks against the real `prepare_case_dir`, the real widget offscreen, the real `SolverControllerMixin` and the real `AppController`), and `test_restart_archive.py` check 7 is now the **inverted** version of the one that pinned the dialog's restart branch, so bringing that modal back fails the gate. Blind spot named in the test: nothing here runs `unicones`, so the bare-name reference is pinned against the SHAPE #30's acceptance run measured, not against the solver's acceptance of it.
- **`services/case_sources.py`** (Qt-free): copies the CAD/STL a case was cut from into **`grid/cad/`**, so the case describes its own geometry instead of only the mesh (the source otherwise lives in `examples/geometries/` or a Desktop, free to be edited or deleted while the case looks complete). Fed by `solver_ctrl._case_source_files` / `_case_generated_files` and `pipeline_runner._case_sources` — the imported source, the resampled `.dat` the mesher read, the immersed STL, the mesh `.provenance.json`, and the **mesh parameter file**, which is *generated* rather than copied because the GUI only ever materialises one in `temp_dir` and deletes it on exit (`mesh_config_io.config_to_text`, split out of `save_config_to_file` so the staged config is byte-identical to a hand-saved one; it takes the destination path because a geometry outside the repo is emitted relative to the config file). Rules: **copy, never move** (the mesher, the GUI session and other cases still point at the original — and a *move* is unimplementable anyway, since one resampled `.dat` legitimately feeds several cases and the pipeline is not one-directional); **a hard link is not the cheap version of a copy** — one inode means editing the CAD afterwards silently rewrites what the case holds, which is the property the copy exists to deny; **sidecars follow their file** (`<name>.dat.meta` carries the per-segment BC labels and No-BL flags, so the `.dat` without it is a different geometry); **collisions are renamed, not overwritten** (two bodies can both be `profile.dat`); generated files are staged **last** and marked `(generated)` in the index, because a reconstruction must not read as evidence. `SOURCES.txt` maps every staged name back to its absolute origin, rewritten in full each run so a body no longer in the case leaves no line — and it is the *only* index there is, so **`tools/scripts/case_sources_index.py`** reads them back to answer the question the case dir cannot ("if I change this CAD, which cases go stale?"), matching by `(st_dev, st_ino)` then path then substring, exit 1 on no match. `case_export` descends into `grid/cad/` with its own allow-list — a nested folder the exporter cannot see is neither shipped *nor named as skipped*.
- **`services/stl3d_case.py`** (Qt-free): the same for the immersed-solid stage — `validate()`, `work_dir_for()`, `prepare_case_dir()` (stages the STL under a whitespace-safe name + writes `para.in`). Both `stl3d_ctrl.run_stl3d` and the headless runner's IB stage go through it. **`Stl3dConfig.para_in_text()` must match `solver/preprocess/STL3d/src/stl3d.cpp`'s `cin >>` sequence line for line** — there are five reads and deliberately no ascii y/n line (the binary auto-detects); an extra line is consumed as the case name and the run silently produces an empty phi field with exit code 0. `tests/test_stl3d_case_parity.py` parses the C++ and gates this. **Inside `stl3d.cpp`, `STLobject` carries two different x extents and they must not be confused**: `xloc_db` (the candidate index `trace_ray` looks rays up in) is keyed by element **centre** x, while `xmin`/`xmax` (the ray culling window) come from the **vertices** — and have to, since a centroid sits strictly inside the surface and a centre-based box clips whole regions off a coarse or fan-shaped tessellation. Every ray in the strip between the last centre and `xmax` therefore passes the culling check with nothing at or after it in the index, so `lower_bound()` returns `end()`; dereferencing that (`->second->second`) is what killed a GUI IB run with `[STL3d] exited with code -11`. A **flat 2D profile is the worst case** — an ear-clipped/fan triangulation drags every centroid toward the apex, leaving the far ~20-30% of the x extent centroid-free (measured 5.856 vs 6.070, i.e. the last 41 of 128 slices). `ctr_strip_at_or_after()` clamps instead: a range *start* falls back to the last strip, a range *end* to `ctr_db_.end()`, so the far strip is really traced rather than silently clipped. Gated by `tests/test_stl3d_flat_profile_trace.py`, which compiles `stl3d.cpp` itself (CI does not build STL3d, and a stale binary must not be able to pass it).
- **`services/contour_render.py`** (Qt-free): renders a Tecplot result to a contour PNG (matplotlib Agg) for headless runs.
- **`controllers/pipeline_ctrl.py`** (`PipelineControllerMixin`): GUI **Run All** — chains the existing per-stage QThread workers on their `finished_signal` (batch mode: no per-stage dialogs), ending on the auto-loaded Results contour. The **immersed-solid stage sits where the headless runner puts it, before the mesh**, so a script and the button build the same case; it is optional and skipped *out loud* when no STL is configured. Save/Load of the script is **`controllers/pipeline_io_ctrl.py`** (`PipelineIoControllerMixin`) — running the pipeline and reading/writing the script that describes it share nothing but the config classes, and the split is what kept the file inside the GUI length budget.
- **`tools/PreProcessor/run_pipeline.py`** + **`run_pipeline.sh`**: headless entry point (`--no-solver`, `--no-contour`, `--png`).

### Visualization (`tools/scripts/`)
- **`visualize_dat.py`**: Matplotlib visualization for `.dat` files; `--quality` flag adds expansion-ratio heatmap
- **`generate_letters.py`**: Generates letter-shaped geometry files
- **`case_sources_index.py`**: which solver cases were built from which geometry (reads every `results/solver/*/grid/cad/SOURCES.txt`). No argument lists every case; an argument (path or partial name) answers "if I change this CAD, which cases go stale?" and exits 1 when nothing matches.
- **`golden_mesh.py`**: `capture <dir>` / `compare <dir>` over 9 mesher cases (~5 s), for proving that a refactor changed **nothing**. Byte comparison cannot make that claim — the mesher is not byte-reproducible, and node NUMBERING varies run to run — so it canonicalises by COORDINATE (nodes lexicographically sorted; each cell its node ranks, rotated to a fixed start and direction so winding cannot disagree; the cell list sorted) and reports the worst deviation, keeping an exact 0.0 distinguishable from a match that merely fits the tolerance. **That distinction is load bearing, and measuring it corrected a belief recorded here**: the nondeterminism is not confined to numbering — `wedge_45` returns a coordinate differing by ~1.2e-13 in roughly 1 run in 12 (worst seen 2.5e-13 over ~20 runs, when two wobbles compound), while the other eight cases were bit-identical every time. Exact equality would therefore flake, and the 1e-10 tolerance is set ~400× above that measured floor. It also compares **both** STAR-CD files: the `.bnd` patch names, their face counts and each face's own coordinates, and the `.cel` connectivity — which is the grid the SOLVER reads and is not the `.vtk`, since the `.cel` writer owns a winding normalisation, a degenerate-cell skip and a duplicate-cell dedupe that exist nowhere else (a review found the comparator could report SAME while that file had changed). A `.cel` triangle is written `v1 v2 v3 v3` and which vertex repeats follows the element's node order, so the duplicate is collapsed before comparing while the winding deliberately is not. Comparing the `.bnd` matters because because the two most expensive junction bugs this repo has had (see the `BoundaryLayer.cpp` notes above) produced a geometrically perfect mesh with the BCs on the wrong patches. Boundary faces are keyed by coordinate, not vertex id — `.bnd` ids index the `.vrt` numbering while cells index the `.vtk` numbering, and those are precisely the numbers free to move. Duct/wedge geometries are **imported** from `tools/PreProcessor/tests/test_nobl_junction_acute.py` rather than copied (a tool reaching into a test dir is unusual; a second copy of a geometry generator is guaranteed divergence). Two junction bins are NOT reachable this way — case 3/4 need θ > 270°, which no geometry writer produces — and `list` says so. **`HYBMESH_GOLDEN_BIN` points the capture at a different build**, which is what makes a behaviour-preserving claim checkable at all: `git archive <start-commit> | tar -x -C <dir>` (no git state touched), build there, capture the baseline from THAT binary, then compare with the working tree. Without it a baseline can only be captured from the tree that already contains the change it is meant to be evidence about.

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
