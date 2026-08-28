# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Where the reasoning lives.** This file carries the RULES. The long-form rationale behind
them — the measurements, the dated acceptance runs, the injections, the reversals and the
named blind spots — was extracted verbatim on 2026-08-28, when this file passed the 150k-char
context limit, into `docs/design_notes/`:

| File | Covers |
|------|--------|
| `docs/design_notes/mesher.md` | Configuration (`.dat`, BL params, MESH_MODE, multi-block, quality, BC binding) + Core C++ |
| `docs/design_notes/gui.md` | The whole PreProcessor GUI section |
| `docs/design_notes/pipeline.md` | Full pipeline, solver case, archive/clean/restart, bDecompose, STL3d |

Nothing was rewritten in the move. **Read the matching design note before overruling a rule
here**: most of these rules were bought by shipping the opposite first, and the rule alone
does not carry the argument for itself. When a rule changes, update BOTH — the rule here, and
its entry there.

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
`MESH_MODE 1` fills a DECLARED block topology with structured quads and splits them
to triangles; it uses Gmsh nowhere. See "The multi-block path is ONE pure entry point"
under Configuration. The second case attaches its corners to a geometry by arc length
and reads each wall's boundary condition off that geometry's source segments — see
"Boundary conditions are DECLARED".

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
| Mode | `MESH_MODE` (0=hybrid BL+Gmsh, default; 1=multi-block structured), `MESH_TOPOLOGY_FILE`, `MB_SPLIT_QUADS` |
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

> **Full rationale for everything below — measurements, dated acceptance runs, injections and named
> blind spots — is `docs/design_notes/mesher.md`.** Read it before overruling a rule; the rule alone
> does not carry the argument for itself.

**The 22 boundary-layer parameters are declared ONCE, in `include/BLParams.hpp`**
(`X(KEY, type, field, default)` per row). The struct, the `.dat` reader, the per-geometry override
parser and `isBLParam` are GENERATED from it; `Config` holds one `BLParams`, not a second copy with
a second set of defaults. `Config::print()` is deliberately NOT generated (the banner is a grouped
report reused verbatim as the provenance sidecar), so `tests/cpp/test_bl_params_decl.cpp` check 6
gates it: every parameter must be reachable from the banner, and where the banner renders it as a
number its own value must appear there. Named blind spot: a SWAPPED PAIR is invisible, because the
pairing of value to meaning IS the label prose.

**`MESH_MODE` selects the generation path, and a parameter the active mode never reads is NAMED**
(`include/MeshMode.hpp` + `src/MeshMode.cpp`, in `hybmesh_pure`; #49). Mode 0 is the hybrid path and
the DEFAULT, so the feature's effect on an existing case is zero — measured, 9/9 golden SAME.
- **"Which parameters does this mode read?" is DATA, in one place.** Two macros declare the inert
  non-BL keys and the four BL parameters that SURVIVE; the 18 casualties are `BLParams.hpp` minus
  those four, so a new BL parameter is covered with no edit. Survivors rather than casualties, so a
  new corner knob gets the right answer by default.
- **"Set" means "differs from a default-constructed Config"**, never "the key appeared in the file"
  — the GUI writes nearly every key on every save.
- **The GUI's half is `modes=` on each field's own spec**, not a second table, compared **in both
  directions** by `test_field_spec_tables.py` check 14. Each direction alone has a hole: a
  warned-about key the panel still shows is a control that does nothing; a hidden field the mesher
  still reads is a value silently frozen. Rows the mode does not read are hidden in the mesh panel
  AND the Edit-BL dialog (where 17 of them live) — hidden, never dropped, so switching modes is not
  a silent edit of 17 values.
- **Exit codes**: `EXIT_ERR_TOPOLOGY` (8, token `TOPOLOGY`) — invalid declaration, exports nothing;
  `EXIT_ERR_INVERTED` (9, token `INVERTED`) — generates with inverted cells and EXPORTS anyway. Two
  codes because the response differs: fix the declaration vs look at the mesh. An **unknown** mode
  is refused by `validate()`, never clamped to 0.
- Departures from #49's text, recorded in `MeshMode.hpp`: `GMSH_NUM_THREADS`, `BL_MERGE_CONCAVE` and
  `BL_SMOOTHING_ITERS` are warned about too (**20** BL-ish names vs the ticket's 18);
  `SURFACE_MESH_SIZE` / `AUTO_SURFACE_SIZE` are deliberately NOT declared inert.
  **`Config::meshMode`'s initialiser must stay the literal `0`**, not `MESH_MODE_HYBRID` — the
  parity gate reads that initialiser as a literal, and an enum name drops the key out of the
  comparison.

**The multi-block path is ONE pure entry point, and the adapter deliberately has no seam**
(`include/MultiBlock.hpp` + `src/MultiBlock.cpp` in `hybmesh_pure`; adapter `buildMultiBlockMesh` in
`src/cli.cpp`; #50). `hybmesh::buildMultiBlock(topologyJson, geoms, params)` parses, resolves, fills
every block with structured quads, splits them, and returns nodes, blocks (with logical i/j), flat
cells, already-resolved boundary edges, warnings as data and an optional error. It never throws.
- **Parsing lives INSIDE the seam**, so schema errors, count resolution, node positions, the split
  and the resolved BCs are all external behaviour of one function. `tests/cpp/test_multiblock.cpp`
  drives it with a topology STRING and no mesh, linking `hybmesh_pure` alone (measured with
  `otool -L`) — reach for `Mesh` or gmsh and it stops linking.
- **The adapter gets no seam, because it has no decisions.** Each boundary edge returns as (node
  pair, BC name, source segment) and is recorded through `recordBoundaryEdge` with a **synthetic
  carrier `Node`**. Position-based classification is not used on this path at all — re-deriving by
  proximity is how a curved inlet exported partly as wall.
- **The split is ALTERNATING BY INDEX PARITY `(i + j)` and it is the default** — a fixed diagonal
  imprints its direction on a uniform region, and parity needs no seed. `MB_SPLIT_QUADS 0` exports
  quads for diagnosis and **says so** (the solver's incenter reconstruction is undefined on quads;
  the grid converter refuses a mixed mesh). The split happens in the MESHER, so VTK shows the mesh
  the solver integrates.
- **Logical i/j is retained rather than flattened** (only the diagonal rule reads it);
  `MbCell::block` is carried for the same reason.
- **Unknown JSON keys are REFUSED, not skipped** — a typo'd `"spacng"` silently ignored is a wrong
  node distribution with no symptom. Strict now is relaxable later. So is **a declaration that
  reaches nothing**: an edge in no block, a corner on no edge.
- **What v0 does not do is refused BY NAME, never approximated**, each refusal naming the work it
  waits for: an `interface`/`cut` edge kind, a `blocks[].orientation`, a second block.
  (`on_geometry` and `binding` were on this list and are implemented by #52.)
- **A block's orientation is the corner order of its own four edges**, `[south, east, north, west]`,
  south/north running i-min→i-max and west/east j-min→j-max; a deviation is refused naming the edge,
  what it declares and what the convention needs — inferring it would produce a mirrored block, i.e.
  a mesh rather than an error. A **clockwise** corner ring is refused under the TOPOLOGY code, never
  silently re-wound.
- **The boundary edges are ONE counter-clockwise walk**, matching `addTaggedLoop` /
  `buildDomainBoundary`. Measured: the direction does **not** reach the `.bnd` (`exportStarCD` takes
  face node order from the owning cell), so this is consistency for a reader. The C++ test pins the
  CHAINING, since a per-side emitter with one direction wrong still emits the right SET of edges.
- The spacing schema accepts `uniform` / `geometric` / `tanh` (`generateGeometric` at ratio 1 IS
  uniform); #55 owns resolving wall spacing from `BL_INITIAL_THICKNESS`. The decision layer gains
  `tools/PreProcessor/include` **PRIVATE** on its include path, so a test linking `hybmesh_pure`
  does not inherit it.
- **SURVIVING is not the same as READ.** #49 declares four BL parameters as surviving into this mode
  and v0 reads **none** of them. `hybmesh::blSurvivorsUnread` names them in their **own** sentence
  (`does not read 'X' yet`), never the inert one (`never reads 'X'`) — an inert value should be
  deleted and one of these should be kept, so the two lists must stay **disjoint** (pinned in
  `test_mesh_mode.cpp` 6b, `test_mesh_mode_surface.py` 4). Delete the function when the clustering
  law lands.
- Known asymmetry: `inertParamsSet` answers only for multi-block, so `MESH_TOPOLOGY_FILE` /
  `MB_SPLIT_QUADS` set under `MESH_MODE 0` warn about nothing (the GUI hides both rows, so only a
  hand-written `.dat` reaches it).
- **A geometry that will not load is a WARNING here, not a refusal** — the opposite of the hybrid
  path's answer, and right because nothing in a topology had to refer to one.
- **`Mesh::addTaggedEdge(v1, v2, bc, segKey)`** replaced the `addEdge` + two writes to
  `edges.back()` idiom at all four call sites: a BC and its source segment are one fact.
- Gated by `tests/cpp/test_multiblock.cpp`, `tests/test_multiblock_surface.py` and three golden
  cases (`mb_square`, `mb_square_quads`, `mb_graded`); `golden_mesh.py` IMPORTS the topology writer
  from the surface test rather than copying it.

**The quality report is the RULER, and it is built before the thing it measures**
(`include/MbQuality.hpp` + `src/MbQuality.cpp` in `hybmesh_pure`; banner and exit code in
`src/cli.cpp`; #51). Every multi-block run prints inverted cell count, max/mean non-orthogonality,
wall first-cell height accuracy and cell count, plus one machine-readable `HYBMESH_MB_QUALITY
cells=… inverted=… nonortho_max_deg=… nonortho_mean_deg=… wall_first_cell_worst_rel=…` line, so the
acceptance gate is a grep.
- **Printed on every run, including a good one** — three of the four numbers are the baseline
  elliptic smoothing will be judged against.
- **Its own module rather than more of `MultiBlock.cpp`**: a different question ("is this mesh
  usable?" vs "what does this document declare?"), and a pure function of a finished mesh — half its
  checks hand `measureMbQuality` a mesh nobody parsed. Pure, total, never throws.
- **Inverted is counted over the EXPORTED cells, and the test is PER CORNER, not the signed area.**
  A bow-tie quad can self-intersect with a POSITIVE shoelace area — `(0,0) (3,0) (0,1) (2,1)` is
  +0.5 and crosses itself. For a triangle the per-corner rule reduces to the signed area, so it is
  one rule for both cell kinds.
- **Non-orthogonality is measured on the STRUCTURED grid cells** — each corner angle's deviation
  from 90° — **and NOT on the split triangles.** It comes from corner positions, so a strongly
  stretched but axis-aligned block measures *exactly* zero (no edge-length proxy can report that);
  it is the quantity elliptic smoothing moves; and it is independent of `MB_SPLIT_QUADS`. An ANGLE
  with a closed form, not a badness score. Named blind spot: it says nothing about the shape of the
  split triangles.
- **A folded mesh is EXPORTED and exits 9; an invalid declaration exports nothing and exits 8**,
  both through the same `failExit` mechanism. `blSuccess` stays TRUE so the VTK keeps its ordinary
  name — `_er` marks a PARTIAL mesh and this one is complete.
- **The wall request is published from the SEAM, never re-derived downstream** (`MbWallSpec` on
  `MbResult`): only `buildMultiBlock` knows the spacing laws. The height is a distance ALONG the
  grid line, not perpendicular to the wall — they differ by cos(non-orthogonality), which is why the
  two figures are always reported together.
- **"ASKED FOR" IS NOT AN INDEPENDENT TARGET YET; do not over-read the figure.** The request is
  DERIVED from the same law the fill reproduces and the blend is exact on the boundary, so **a
  rectangle's 0.00% is a tautology, not evidence.** What it honestly measures is interior drift from
  what the two ends declare (trapezoid 7.38%, folded dart 25.41%). When the independent target
  arrives only the PUBLISHER changes.
- **"We did not measure" must not read as "it came out perfect", for ALL THREE figures.**
  `maxNonOrthoDeg`, `meanNonOrthoDeg` and every `worstRelError` (per wall AND headline) are NEGATIVE
  when unmeasurable, never 0.0, and the banner prints `not measured`. The rule holds at the ROW
  level too (check 6b) — `measureMbQuality` is a public pure function accepting any `MbResult`, so
  its header's guarantee must hold for every input.
- **The detector is proven to bite by a topology that folds, and that topology is ACCEPTED**: the
  dart `(0,0) (1,0) (0.1,0.1) (0,1)` winds counter-clockwise (+0.1), so the ring refusal does not
  fire and the fill folds anyway. The gate checks no topology refusal prints on that run.
- **All four sides are reported**, because v0 cannot say which boundary is a viscous wall.
- **The `[south, east, north, west]` convention is DATA, in one place** (`mbSideAxis`). A dedup of
  `MbWallSpec`/`MbWallHeight` was considered and DECLINED: they face opposite directions and the
  shared part cannot be written HALF.
- Gated by `tests/cpp/test_mb_quality.cpp` (9 groups, 53 checks) and
  `tests/test_multiblock_quality_surface.py`. **Its injections are HAND runs, dated in the C++
  test's docstring** — a C++ test cannot mutate the implementation it linked against, and that
  distinction must not be blurred. What IS permanent is two **negative controls** computing an
  injection's own premise (check 6 the bow-tie's +0.5 area, check 2 its ~17x stretch). Sharpest
  blind spot: nothing runs the solver or grid converter on the folded mesh.

**Boundary conditions are DECLARED, and geometry is attached by ARC LENGTH** (still the one pure
entry point; #52). A corner attaches to a source segment at a normalized arc-length position
(`kind: "on_geometry"`, `geom` / `seg` / `t`), a wall edge declares the segment it lies on
(`binding`), and every generated boundary edge carries that segment's condition and its (geometry,
segment) key into the export. The answer is in the declaration before a node exists, so **there is
no tolerance anywhere in this chain** — the hybrid path resolves by testing proximity to a reference
segment, and on a curved wall the drift off the chord exceeded it and an inlet exported a band of
wall at every junction.
- **Arc length, NEVER a point index.** Re-resampling changes the point count, so an index would
  silently relocate every attachment. Measured through the real binaries: one topology against two
  resamplings (21 and 41 points) gives identical `.vrt` node COORDINATES, with the negative control
  that **neither** resampling has a sample at **any of the four** attached positions.
- **`t = 1` means "where this segment ENDS"**, which is the next segment's first point only when
  there IS a next one; on the last segment of an open polyline it is that segment's own final point,
  stable because the resampler pins every segment's endpoints.
- **A segment's own points stop ONE POINT SHORT of where it ends, and the run is extended by one.**
  Measured against the real resampler: a shared joint is assigned to the **later** segment
  (`resSegId.back() = segId`). For the LAST segment of a **closed** loop the point to reach for is
  index 0 (`loadGeometry` dropped the duplicate closing point).
- **A trivial piece break at index 0 is not a second piece** — sidecars in this repo disagree about
  recording it (`NPIECES 0` vs `NPIECES 1 0`), so `multiPiece()` asks whether any break falls
  strictly inside, never `pieceBreaks.empty()`.
- **A corner at `t = 0` or `t = 1` sits on a JOINT that two segments both own, so a bound edge
  accepts it from either side** (`tOnSegment`). Without it the canonical declaration — one block
  side per source segment on a closed body — cannot be written at all. The equivalence compares the
  sidecar's own point INDICES, never coordinates.
- **A bound edge FOLLOWS the segment's polyline; it does not cut the chord.** One code path serves
  both (an unbound edge's "polyline" is its two corners), and that reduction is **bit-identical**.
- **A geometry is named BY NAME** — exact declared path, then a *unique* basename — never by
  position in the loaded list. An ambiguous basename is refused, not resolved by order.
- **A label stays a LABEL.** The seam emits the sidecar's grouping label and `Config::resolveGroupBc`
  turns it into the physical BC type, exactly as on the hybrid path; the adapter merges the
  sidecar's `GROUP_BC` trailer into the config for it. A second resolver in the chain is how the two
  came to disagree last time.
- **A geometry that will not load is still a WARNING; a declaration REFERRING to one is an error.**
  Same for a geometry with no readable `.meta` — refused by name rather than falling back to "the
  whole polyline is segment 0".
- **Two warnings, both about getting the fallback you did not ask for**: no edge declares a binding
  (everything on `BC_GEOM`), and a bound edge whose segment carries no label. The banner prints one
  row per patch naming the segment it was read off, so "declared, not discovered" is visible in a run.
- **`MbWallSpec` still reports all four sides**; the gate stays `kind`, since "labelled inlet" and
  "viscous surface whose first-cell height matters" are different questions.
- The adapter gained a ~15-line boundary-patch summary for the banner — PRESENTATION, not
  classification, but it is no longer literally decision-free; a second such block belongs on the
  pure side beside `measureMbQuality`.
- Gated by `tests/cpp/test_multiblock.cpp` checks 12-16 and
  `tests/test_multiblock_binding_surface.py` (real resampler AND real mesher), plus golden cases
  `mb_bound` and `mb_cavity` (the shipped example on the shipped geometry — documentation a user
  runs must be covered). Injections are HAND runs, dated 2026-08-28.
- **Named blind spot**: the end-to-end re-resampling check uses a straight-sided geometry, where an
  arc-length position is EXACT under resampling. On a *curved* segment an attached corner moves by a
  chord sagitta — a limit of the geometry, not the binding. The curve-following half is pinned in
  the C++ test.
- **What the shipped example cannot do, said out loud in the example**:
  `examples/geometries/square_cavity.dat` is an OPEN polyline stopping one sample short of the seam,
  so its segment 3 does not reach the block's south-west corner and the west edge is deliberately
  left unbound (a straight chord carrying `BC_GEOM`).

**Two parse behaviours CHANGED when the two parsers were unified** (2026-08-19), both measured on
the old and new trees:
- **`BL_AUTO_FAN_NODES` is an int on both paths** (0 OFF / 1 Global Avg / 2 Local Avg). The `.dat`
  reader used to collapse it with `(val != 0)`, so a global `2` ran as 1 while the same token on a
  `GEOM_FILE` line reached 2. The GUI could not express it either — the model field was a `bool`
  behind a three-item combo, so LOCAL had *always* run GLOBAL; found by the parity gate's type
  check. **A behaviour change golden meshes cannot cover.**
- **A `bool` key is read through a double**, so `BL_USE_ANALYTIC_GEOM 0.5` is now true. Integral
  values are unaffected; kept, because a per-row parse rule is what let the two parsers disagree.

**An unrecognised per-geometry `KEY=VALUE` override is NAMED, not dropped**
(`parseBLOverrideToken` asks `isBLParam` and warns) — same "the setting does nothing" failure class.

### PreProcessor JSON Config
JSON format; supports multi-element definitions with transforms (scale/rotate/translate), per-segment spacing strategy, and auto-split threshold. See `tools/PreProcessor/config/` for examples.

## Architecture

### Core C++ (`src/`, `include/`)

> Full rationale: `docs/design_notes/mesher.md`.

**The implementation is a LIBRARY and the executable is a shim.** `hybmesh_core`
(STATIC) holds `cli.cpp` + `Mesh.cpp` + `BoundaryLayer.cpp`; `add_executable(HybMesh2D
src/main.cpp)` compiles **only** the twelve-line shim calling `hybmesh::runCli`
(`include/Cli.hpp`). Before this the three `.cpp` files compiled straight into the
executable with no library target, so **no test could link them** — the process boundary
was the mesher's only seam, and `classifyJunctions`, extracted specifically to be
testable, sat private and unreachable. The shim keeps the seam honest: the executable
compiles no implementation, so there is nowhere to put logic a test cannot reach. Two
consequences: **the provenance macros are defined on the LIBRARY, not the executable**
(a definition left on `HybMesh2D` would apply to the shim alone and degrade every banner
and sidecar to `git unknown`), and the **CGNS-before-Gmsh link order** is `PUBLIC` on the
library so it propagates (that ordering is load bearing — see the `cgsize_t` note in
`CMakeLists.txt`).

**The tests live in `tests/cpp/`** — one executable per file, registered with ctest,
`check.hpp` for assertions (**record-and-continue**, not abort-on-first; `report()`
reprints the FIRST failure last so the cause is not buried under its consequences). A test
**links a library target, never a list of sources** — compiling `src/*.cpp` into a test
executable works and quietly reintroduces a second build of the implementation, testable
but not the one the binary runs. `tests/test_cpp_linkable_seam.py` gates it (7 checks),
because this property decays in silence. Four holes it covers past "the shim is the only
source", each of which *looks* satisfied: `#include "cli.cpp"`; a test listing
`../../src/Mesh.cpp`; a new `add_executable`; a `tests/cpp/test_*.cpp` CMake never
registered. All verified by injection; two remaining blind spots named in its docstring.
Caveat on the neighbouring instrument: `golden_mesh.py` does **not** compare the `.bnd`
`segm_no` column, so a defect confined to a boundary edge's source-segment key is
invisible to it — measured, and the C++ unit test caught it in 0.5 s while all 68 other
tests and the 9-case golden set passed.

**`hybmesh_pure` is the decision layer, and the BUILD is what keeps it honest** — the C++
analogue of the GUI's "`services/*.py` must be Qt-free" rule. **The pure tests link
`hybmesh_pure` alone and are not linked against libgmsh at all** (verified with `otool -L`),
so the moment such a module *uses* `Mesh` or gmsh those executables stop linking (measured:
making `JunctionScheme.cpp` construct a `Mesh` gives `Undefined symbols for architecture
arm64`). The grep and the linker cover different halves — an *include* not yet used is
invisible to the linker, a *use* invisible to a grep — so `test_cpp_pure_layer.py` also
computes each file's **transitive** include closure (`BoundaryLayer.cpp` reaches `Mesh.hpp`
only through its own header, so a direct-include check would call it pure). The list is a
**deny**-list (`HEAVY_SOURCES` / `HEAVY_HEADERS`, each entry carrying its reason): a new
`src/*.cpp` is assumed pure, because an allow-list would silently exempt whatever nobody
enrolled.

`hybmesh::classifyJunctions` (`include/JunctionScheme.hpp`, `src/JunctionScheme.cpp`) is its
first member and the argument for the layer: extracted from `generate()` to be testable, it
then took a 22-field mutable `FrontState` plus `Mesh&` while actually reading three
positions/normals per node, one `skipBL` bool, and three config scalars — the wide signature
hid how narrow the dependency was. It now takes `vector<JunctionNode>` + `JunctionParams`
(AoS, not six parallel arrays) and returns decisions **and warnings as data**: the
very-sharp-wedge message is user-facing prose about config keys and stays at the call site,
while the threshold (`tan θ × influence < 1.15`) becomes testable — `tests/cpp/test_junction_scheme.cpp`
pins it at three different influence values without generating a mesh. `thetaDeg` travels in the
decision because `HYBMESH_JUNC_DEBUG`'s trace format is parsed by
`test_nobl_junction_acute.py`; a negative value means no angle was measured. **This covered
junction cases 3 and 4 for the first time** (θ > 270°, which no geometry writer in the repo
produces). `hybmesh::inertParamsSet` (`include/MeshMode.hpp`) joined it for the same reason:
`tests/cpp/test_mesh_mode.cpp` can prove the four surviving BL parameters SILENT, a negative
a log-scraping test would have to establish by absence.

- **`main.cpp`**: the entry point and deliberately nothing else.
- **`cli.cpp`**: the whole command line (`hybmesh::runCli`) — parses config, loads
  geometries, runs collision checks, orchestrates BL + Gmsh. **`OUTPUT_FILENAME` may end in
  the GUI's `.*` all-formats placeholder, which is a wildcard and not an extension** —
  stripped once, before `validate()`/`print()`, so the banner, the sidecar and every writer
  share one basename. Taken literally it wrote the VTK into a file *named* `mesh_<case>.*`
  (`extPos()` finds that dot, so `.vtk` was never appended). See "The Output field's `.*`".
- **`BoundaryLayer.cpp`**: quad layer growth — normals, fan/parallel corners, concave
  merging, transition layers, smoothing. **The junction binning is NOT here** — it is
  `hybmesh::classifyJunctions` in the decision layer, and `generate()` only assembles its
  narrow input, applies the decisions and logs the warnings. BL/no-BL junctions (a BL edge
  meeting a `grow=0` neighbour) use the angle-driven cap scheme (`BL_JUNCTION_METHOD=1`,
  default): the flow-facing angle θ picks case 1 (slide along the neighbour edge + absorb
  the no-BL nodes it covers, θ ≤ 95°), case 2/4 (perpendicular cap, 95° < θ ≤ C2 or θ > C3)
  or case 3 (neighbour-edge extension cap, C2 < θ ≤ C3); every cap leaves a free full-height
  lateral column emitted as far-field constraints, and the step is scaled by 1/cos(tilt) so
  the *perpendicular* height stays fixed. **The 95° slide bound is geometric, not a knob**:
  a cap must point into the fluid wedge while the perpendicular sits at 90°, so at θ ≤ 90°
  it provably exits through the no-BL wall (θ < 90° self-intersects the front, exit 5;
  θ = 90° hands Gmsh a doubled-back hole, exit 6). `C1` now only bins method 0. A slide at a
  **very sharp wedge** (`tan θ × BL_CONCAVE_INFLUENCE_MULTIPLIER < 1`, i.e. 21.8° at the
  default 2.5) still fails downstream, so it emits `[WARN] Very sharp BL/no-BL wedge at
  (x, y)` — advisory only, nothing auto-corrected. An **isolated BL corner** (BOTH neighbours
  No-BL, issue #2) gets `[WARN] Isolated BL corner at (x, y)` pointing at the **`.meta`
  sidecar**, and that is PERMANENT, not a placeholder: issue #4 (the two lateral columns such
  a corner needs) was closed **wontfix** 2026-08-20 because the configuration is unreachable
  from this toolchain — the resampler flags every segment boundary `corner = 1`, `cli.cpp`'s
  `prevBL || nextBL` rescue promotes any such corner back to BL growth, and the GUI's
  `meta_io` copies the POINTS block through verbatim. Only a hand-written or foreign sidecar
  gets there. **A case-1 slide REPLACES a stretch of the no-BL wall, so its own edges must
  carry that wall's BC by construction** (`slideColumns`/`slideWallRun` →
  `Mesh::recordBoundaryEdge`), matched to the wall edge each replacing edge covers by arc
  length: the column is a straight ray, so on a *curved* no-BL wall it drifts off the
  polyline by ~a chord sagitta while `pointOnSegment` accepts 1e-6 of a chord (measured
  6e-8..1.8e-6 vs a 2.0e-8 tolerance) — so every column edge past the first fell through to
  `BC_GEOM` and a No-BL inlet/outlet exported a `wall` band exactly D_total long at each
  junction. A straight wall has no drift, which is why straight-duct coverage missed it.
  Gated by `tests/test_nobl_junction_acute.py` (`write_curved_duct` — the curvature is the
  point). `=0` restores the legacy taper-to-zero (~12% floor ramping back over arc length).
- **`Mesh.cpp`**: mesh data structure (Nodes/Elements/Edges), Gmsh far-field integration,
  VTK and STAR-CD export. **A boundary edge's BC and its source segment are ONE fact and are
  private**: write with `recordBoundaryEdge(v1, v2, srcNode, overwrite)`, read with
  `boundaryEdgeInfo(v1, v2)`. They used to be two public parallel maps every caller keyed by
  hand, so "wrote the BC, forgot the segment key" was a defect the interface could not
  prevent — and half an identity reaching the exporter exports as the wall default. The
  compiler now rejects outside access, which is why nothing tests *that*; their paired
  SEMANTICS are tested in `tests/cpp/test_mesh_boundary_edge.cpp` (a refused overwrite must
  not half-apply; the key is the unordered node pair; a BC with no resolvable segment still
  records). **`FARFIELD_MESH_SIZE` is a `Min()` cap on the size field, not a target**: the
  field grows from the wall (`FARFIELD_GROWTH_RATE`) and/or inward from the bounding box
  (`FARFIELD_GROWTH_RATE_OUTER`), so in a small domain it tops out below the cap and every
  larger cap gives a byte-identical mesh. Every run prints a `[ Mesh Size Field ]` block
  reporting how high growth reaches, the effective ceiling and whether the cap is
  dead/marginal/active — computed by re-evaluating the field expressions at the generated
  nodes, **not** by measuring cell edges (those run ~15% long on stretched triangles and
  would report a dead cap as live). Gated by `tests/test_size_field_ceiling.py`. Caveat: a
  custom domain outline is added with `geomId = -1`, so for a pure internal-flow case
  (`DOMAIN_FILE … nobl`, no `GEOM_FILE`) the wall-distance field is never built and
  `FARFIELD_GROWTH_RATE` is inert — only `FARFIELD_GROWTH_RATE_OUTER` grades the mesh.
- **`MultiBlock.cpp`**: the whole multi-block path behind one pure entry point — parse,
  resolve, fill (transfinite interpolation), split, and the already-resolved boundary edges
  the adapter records. Never throws; a malformed document comes back as an error string.
- **`MbQuality.cpp`**: the multi-block quality instrument. Pure, total, never throws.
- **`Config.hpp`**: single-header; parses `.dat` files into ~50 typed parameters.
- **`GeomUtils.hpp`**: `Vector2D`/`Point2D`, segment intersection, normals, dot/cross.

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

**Stage config data flow is one-directional** (`controllers/panel_sync_ctrl.py`): the
**model is the truth, the panel is a view**.
- **panel → model**: `sync_panel_to_model(panel_attr)` runs on *every* user edit (the
  widget-introspection traversal in `undo_ctrl._wire_widget_edits` calls `on_panel_edited`,
  which syncs first and then schedules the undo snapshot). So `global_mesh_config` /
  `global_solver_config` / `global_stl3d_config` are never stale; nothing should read a
  panel widget to get a config value.
- **model → panel**: `push_panel_config(panel, cfg)` (undo-suppressed).
- `PRESERVED_FIELDS` lists what each panel does **not** author and must never overwrite
  (the solver panel has no widget for `length_unit`, so a wholesale copy would wipe it and
  take `Linf` with it). `tests/test_panel_model_sync.py` proves each set equals what that
  panel's `get_config` actually assigns, **by AST**, so a model field added without a widget
  fails the build instead of silently going stale.
- A model may define `normalize()` to restore its own invariants after a sync.
- **`set_config` sets the panel's own `_loading` flag under try/finally**, and the sync
  checks *that*, not the caller's discipline: a direct `set_config` that forgets
  `push_panel_config` must cost at most a spurious undo step, never a corrupted model. New
  panels must follow the same `set_config` / `_set_config_body` split.

**A config field is declared ONCE, in its panel's field-spec table**
(`app/services/field_spec.py` is the Qt-free record + the pure questions asked of a table;
`views/panels/field_widgets.py` is the one kind→widget mapping and the three traversals;
the tables are `services/mesh_field_specs.py` + `services/mesh_bl_field_specs.py` and
`views/panels/solver_field_specs.py`, `views/panels/stl3d_field_specs.py` — the two MESH
tables live in `services/` because the `.dat` key map derives from them; their old
`views/panels/` paths survive as re-export shims). Each panel used to be cut in half — one
half BUILT widgets, the other read and wrote them — with the whole widget set as the
implicit interface: **176 attributes across five build mixins, named back by hand in 246
read/write lines**. A spec carries `attr` · `kind` · `label` · `tip` · `model` · `key` ·
`group` · `opts`; the table is walked once to build (`add_spec_rows`), once to write
(`write_specs`) and once to read (`read_specs`). Load-bearing rules:
- **`get_config` / `set_config` / `_set_config_body` were NOT touched as verbs**, nor was
  `panel_sync_ctrl` — the frozen review lists both under *"genuinely deep — leave alone"*.
  The table sits BEHIND those three; the panel-owned `_loading` flag is unchanged.
- **`PRESERVED_FIELDS` is a subtraction, not a list**: model fields − table − the residue
  each panel declares beside its table (`*_EXTRA_AUTHORED`, for facts one widget holds for
  many things).
- **`LENGTH_FIELDS` is derived from `kind == "sci"`**, which IS the physical-length rule, so
  the list and the widgets cannot disagree.
- **Widgets are seeded from the model's defaults**, not literals repeated in build code.
- **A choice is matched by VALUE in Python, never `findData`** (QVariant comparison makes a
  bool `False` against an int `0` a coin toss), and an unavailable value falls back to a
  *declared* one instead of index 0.
- **Numeric and combo rows go into the form DIRECTLY, never wrapped**:
  `QFormLayout.labelForField` only finds a label for the widget that IS the field cell.
- Three escape hatches exist, each used by exactly one field and named with its reason in
  the gate: `read`/`write` on a spec (`ascii_combo`), `panel_choices` (`bl_concave_method`),
  `host_writes` (`output_filename`).
- **One spec means one tooltip**; the Edit-BL dialog's '?' shows that prose **plus the
  `.dat`/`Config.hpp` KEY** (the KEY used to be the only help 20 of 21 fields had, and
  giving every spec a tip silently killed the `spec.tip or key` fallback — gate check 12).
- **`services/field_spec.py` is Qt-free and gated; `config_ownership` is Qt-free at IMPORT
  only.** The SOLVER and IB tables still live under `views/panels/`, whose package
  `__init__` eagerly imports eight Qt panels, so `preserved_fields()` naming those two still
  loads PyQt6.
Gated by `tests/test_field_spec_tables.py` (twelve properties, every static one verified by
injection, each injection asserting the mutated source still PARSES and really changed).

**The GUI's `.dat` key map is DERIVED from the field-spec tables**
(`models/mesh_config_keys.py`): 45 of its 49 `KEY -> (attribute, converter)` entries come
from the tables (`spec.key` + `spec.model`), the converter from the model field's own
dataclass type via `field_spec.model_types()`, and the 4-entry residue is declared with a
reason each.
- **The two mesh tables live in `services/` for this, and the reason is the seam.** Any
  module under `views/panels/` drags in that package's eight Qt panels, while
  `mesh_config_keys` is on the HEADLESS path (`mesh_config_io.config_to_text` ←
  `run_pipeline.sh` / `run_batch.sh`). The cost is recorded rather than hidden: ~250 lines
  of UI text now sit in `services/`. The solver and IB tables did NOT move — nothing
  headless derives from them.
- **`_KEY_MAP` is anchored to the WRITER, not just to the tables** (gate check 13f, both
  directions, with `GEOM_FILE` / `DOMAIN_FILE` / `SEED_FILE` / `GROUP_BC` declared).
  Checking only "map agrees with tables" was measured BLIND: removing a spec's `key=` left
  both sides agreeing while the writer kept emitting the line.
- `mesh_config.py` imports the map inside the two methods that use it, since deriving it
  made `mesh_config_keys` depend on `MeshConfig`.

**The edge being edited has an OWNER, and there are TWO edit kinds in it**
(`services/edge_edit.py`, Qt-free — `EdgeEditSession` + `EditOutcome` + `ShapeOutcome`).
Drawing/double-clicking an **analytic** edge, and double-clicking an **imported (discrete)**
edge to reshape its outline by corner vertices, both open a *modeless* session committed by
**Create Edge** / **Apply** and reverted by **Cancel**. Between them that was **twelve
attributes on `AppController`**, with "an edit is live" enforced only by every reader
remembering to test for `None`. **Both kinds live in one owner because they are
alternatives**: at most one may be live, so `_edit_in_progress()` is one question with one
answer.
- **The dialog is held OPAQUELY** — stored and handed back, never called into. What must be
  *asked* of it (a polygon's open/closed toggle) is read by the caller and passed into
  `update()` as a value.
- **`commit()` / `cancel()` end the session and return an `EditOutcome`; they do not decide
  what it becomes.** The *revert* does live in the owner, being the other half of its snapshot.
- **An edit BELONGS to the CAD session it began in, and leaving that session is a
  transition.** Nothing used to cancel a live edit on a tab switch or close, while commit
  resolved its target through `active_session()` — the tab in front *now* — then fell back
  to matching by segment **id**, and ids are per-session (`renumber_segments` assigns
  contiguous 1..N across both edge kinds, so every tab's Nth edge has id N), so it landed on
  **another tab's edge**. Every outcome now carries its session and the caller acts on
  **that** one; the list / selection / window title are touched only when the edit's session
  *is* the front tab. Switching or closing away **asks**, defaulting to cancelling
  (`headless_default=True`); on close the edit question comes **first**, and declining
  aborts the close. Declining a switch must **put the tab bar back**. `begin`/`begin_shape`
  REFUSE while another edit is live — the backstop, not the interaction, since a Qt-free
  module cannot prompt. `commit`/`cancel` with nothing live is a silent no-op
  (`get_logger(__name__).debug`, never a pop-up).
- **An ending the DIALOG did not initiate must close the dialog** — it tears itself down
  through `finished → deleteLater`, which fires only on a self-close. The dialog travels
  back on the outcome and the caller closes it; that `close()` **re-emits `rejected`**, so
  the cancel handler runs again against an idle owner, which is why the silent-no-op rule
  and this one had to land together. **The canvas clear takes the EDIT's session**, since
  the preview is keyed by `session_id`.
- **Not every route out is a prompt.** Switching and closing a tab ask (both cleanly
  abortable). Opening a new tab, `reset_all_state` and loading a workspace end the edit
  unconditionally and say so in the log.
- **The committed-edge DRAG is a transition, not a nullable field**: `begin_drag` /
  `finish_drag`, and **a drag belongs to the segment it began on and cannot be finished
  against another**. The handler must not `begin_drag` on the `finished` event, and **a drag
  is NOT `is_active()`** — callers guarding on that predicate must keep working during one.
- **A corner drag is a value in, an outline out**: `move_corner` returns a freshly re-fitted
  array instead of mutating the live one, so dragging never accumulates transform onto
  transform and Cancel restores points *byte-for-byte*. The shape side has **`end_shape()`,
  not a commit/cancel pair**, because both endings need the same thing from the owner.
Gated by `tests/test_edge_edit_owner_seam.py` (five properties, nine in-test injections),
`tests/test_edge_edit_owner.py` (the verbs, Qt-free, PyQt6 refused through a meta-path hook
so a *deferred* import fails too), `tests/test_committed_drag_undo.py` and
`tests/test_edit_session_binding.py` (offscreen Qt with the real `AppController`). The
binding test moves `active_idx` **directly** rather than through `switch_tab`, on purpose:
`switch_tab` now ends the edit, and the binding is the half that must hold when some other
route changes the front tab.

**The outline re-fit is pure arithmetic and has its own module**
(`services/shape_refit.py`, Qt-free — `build_edge_specs` + `refit_shape`). Each edge re-fits
between its own two corners by the similarity transform carrying its ORIGINAL corner pair
onto the current one, so dragging a shared corner redistributes both. Two behaviours it is
careful about: a **zero-length edge** falls back to a pure translation (the transform's
divisor is the squared length), and the **closing edge wraps to index 0** rather than being
read as out-of-range and skipped. The extraction was measured: 2000 randomised outlines
through both the new function and the pre-change in-place body came out **byte-identical,
worst |Δ| = 0**. Gated by `tests/test_shape_refit.py`.

**Undo is global, across every CAD session AND project settings** (`controllers/undo_ctrl.py`).
Histories stay per-`GeometrySession` (plus `controller.project_history`) so closing a tab
drops exactly its own commands; ordering across them is by the monotonic `seq` that
`CommandHistory._push` stamps. Undo raises the tab owning the command before applying it.
Mesh/Solver/IB edits are recorded by debounced snapshot diffing, so a burst of typing is one
step. **Any code pushing config into those panels must go through
`controller.push_panel_config(panel, cfg)`** (or `suppress_project_undo()`), or the push is
recorded as a user edit.

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

**Numeric fields**: any field holding a *physical length* (BL initial thickness, mesh sizes,
domain coordinates, resampling spacing, seed size/radius) must use
`views/clean_double_spin_box.py::SciDoubleSpinBox`, not `CleanDoubleSpinBox`. It
accepts/displays scientific notation, steps by decade, and has no hardcoded floor — a
fixed-notation box silently clamps the 1e-7..1e-8 first-cell heights real CFD needs. Range
lower bounds stay at 0 and invalid values are rejected by `MeshConfig.validate()` with a
message, never by UI clamping.

**Length units** (`app/services/units.py`, Qt-free): the model declares ONE length unit
(Mesh panel, top row). It is **not cosmetic** — the solver is dimensional. Per the UNICONES
manual `fs_UnitRe` is *per metre* and `Linf` is *metres per grid unit*, so
**Re = fs_UnitRe × Linf**. A mm mesh left at `Linf = 1` runs at 1000× the intended Reynolds
number with a mesh that looks perfect.
- **`Linf` is derived from the declared unit**, not typed. `SolverConfig.linf_from_unit` is
  True for anything new; `load_from_dict` turns it **off** for a config with a hand-set
  `linf` and no `length_unit`, so a pre-units case keeps its Reynolds number. `unit_check()`
  reports the discrepancy naming the unit that `linf` implies.
- **Changing the unit relabels; it never rescales.** Only two things convert numbers: `Linf`,
  and coordinates at *import* (`views/import_unit_dialog.py`, asked once per import action,
  defaulting to no conversion, silent + no-op when headless).
- **Units are shown as the spin box's own `setSuffix`**, never baked into label text. Only
  physical lengths get one; growth rates, angles and counts must not.
  `views/panels/mesh_units_mixin.py::LENGTH_FIELDS` must equal the panel's `SciDoubleSpinBox`
  set — `tests/test_units.py` fails the build otherwise.
- The visible defence against a *plausible* wrong unit is the **reference Reynolds number**
  read-out on the Solver panel (`views/panels/solver_units_mixin.py`) and the
`[INFO] reference Reynolds number` line in
  `run_pipeline.py`. The size-plausibility check only catches gross errors and says so.
- The mesher **records but never converts** `LENGTH_UNIT`; it prints it in the banner, so it
  lands in the provenance sidecar.

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

**Pop-up stacking** (`app/popup_stack.py`, re-exported from `app/utils.py`): every modeless
pop-up goes through `keep_on_top(w)` **before** `show()`, which re-parents it to the
**top-level** window, leaves it an ordinary normal-level `Qt.Dialog`, and installs three
filters — `_PopupRaiser` (on the main window, per activation), `_ClickRaiser` (on the
**QApplication**, per mouse RELEASE) and `_ShowRaiser` (on the pop-up). Activation alone is
not enough: it fires on the FIRST click of the main window only, so every later click
reorders the window in front with no Qt event to hear, and a raise deferred into the middle
of a canvas *drag* is undone when the drag ends. Releasing is when the platform has finished
reordering. Both window-LEVEL shortcuts are wrong and were each shipped once:
`WindowStaysOnTopHint` floats above **every** application, and `Qt.Tool` — an NSPanel with
`hidesOnDeactivate` — makes the pop-up **disappear** when the user clicks another app
(measured on Qt 6.10: `isExposed()` → False); disabling the auto-hide is not an escape (Qt6
ignores `WA_MacAlwaysShowToolWindow`, and a Tool window sits at NSFloatingWindowLevel).
**Every raise goes through `raise_later()`** — a raise issued from inside the event that
reorders the windows is undone when the platform finishes that event. Re-parenting is load
bearing twice: the raiser finds pop-ups in the top-level's direct child list, and a pop-up
parented to a panel is hidden with that panel. Gated by `tests/test_popup_stacking.py`.
`BatchDialog` opts out on purpose (it runs for minutes and must be free to sit behind).

**Duplicate/transform closure**: `transform_apply_ctrl` is type-preserving (a line stays a line, an
**arc stays an arc**…), and the copy inherits the source's `closed` flag — except in the
polygon-bake fallback (formula curves, discrete file edges, and a circle/arc under a NON-uniform
scale, which is an ellipse the model cannot hold), where the flag is *re-derived from the points*
by `_baked_edge_is_closed`. The arc's image is read off three TRANSFORMED POINTS — centre, arc
start, quarter-sweep point — so one code path serves every similarity transform and a mirror's
reversed sweep comes out of the geometry rather than a per-transform sign rule; the quarter point
rather than the midpoint, because `sin(sweep/2)` vanishes at |sweep| = 2π. Whatever still bakes is
NAMED in the log with the reason. `SegmentModel.closed` defaults True and is only ever read for
`curve_type == "polygon"`, so every other edge carries True while drawing open — copying that flag
onto a baked polygon is what silently closed a duplicated arc. Discrete edges must not take the
PROJECT's closure either: one segment of a closed imported outline is itself an open polyline.
Gated by `tests/test_transform_closure.py`.

**The discrete geometry is ONE polyline, and both ends of that have to be handled.** A session
stores every discrete point in `original_points`, indexed by `split_indices` into file segments,
drawn as a single pyqtgraph item.
- **Baking order matters.** `BakeCurveToGeometryCmd` welds a converted edge onto whichever END of
  the polyline it touches, so an edge touching neither lands as a separate piece.
  `bake_selected_curve` chains a multi-edge selection with `_chain_edges` (the same one Join uses)
  and bakes head-to-tail as ONE undo step, index-sorted — otherwise the DRAWING order, which the
  user cannot fix by clicking differently, decides the result.
- **Where the polyline must NOT join comes from the model.** `_geometry_connect` (in
  `segment_canvas_ctrl`) breaks it at any index interval covered by no file segment and passes that
  as pyqtgraph's `connect` array; without it two disjoint pieces are drawn joined by a "diagonal"
  belonging to no edge that cannot be selected away. Deliberately not a spacing heuristic, which
  would also break a long straight edge beside a finely sampled arc.
- **An empty model still has to be drawn**: `_apply_geometry_update` returns early when
  `original_points is None`, so `_clear_geometry_canvas` wipes layer, hit-test points, split
  markers, closing edge and stats — but never the analytic items, which a session can have alone.

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

**Edit Boundary Layer dialog** (`views/panels/mesh_dialogs_bl.py`, tables in
`mesh_bl_field_specs.py`, accordion + fitting in `mesh_bl_dialog_layout.py`): the 21 BL parameters
are collapsible groups (`_BL_FIELD_GROUPS`, mirroring the `.dat` groups), **all closed to start**
(USER-REQUESTED), plus Expand all / Collapse all. Only two things open a group and neither is a
default: the state the user left it in (`ui_state`), and a group holding a value differing from the
global default, so a per-geometry override never hides behind a collapsed header.
**`_BL_FIELD_GROUPS` must partition `_BL_FIELD_SPECS` exactly** — a key in no group is a parameter
the user cannot reach that is still written back on OK — gated by
`tests/test_bl_dialog_sections.py`, with stray keys falling into a trailing "Other" group as a
backstop. The window follows the open groups (`_relayout` → `_autofit_height`), bounded by the
screen and never below a height the user set by dragging. Two Qt facts the fit depends on:
`QScrollArea::sizeHint()` is **clamped to 24 font heights**, so the dialog's own `sizeHint()` stops
growing after a group or two (the fit measures the scroll's shortfall against its cap instead); and
hiding a widget only *posts* the layout request, so `CollapsibleSection._on_toggle` invalidates its
own layout. The leftover-space absorber is **stretch 0 + Expanding**, never a stretched item, which
would compete proportionally with the capped scroll area.

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

### Full Pipeline (CAD → mesh → solver → results, one action)
A single unified JSON script drives the whole chain; the GUI and the headless CLI share the
same schema and stage logic.

> **Full rationale for this section — the dated acceptance runs against the real `unicones`
> binary, the injections, the reversals and the named residues — is
> `docs/design_notes/pipeline.md`.** Several rules here were bought by shipping the opposite
> first; that file is where the evidence lives, and it is worth reading before overruling one.

- **`models/pipeline_config.py`** (`PipelineConfig`, Qt-free): the unified schema
  (`cads`/`mesh`/`solver`/`stl3d`/`results`, each mapping 1:1 onto
  `ProjectModel`/`MeshConfig`/`SolverConfig`/`Stl3dConfig`) + converters.
  `PIPELINE_FORMAT_VERSION` (v2). **`cads` is a list** — one entry per geometry, so a multi-body
  case round-trips; the singular `cad` key is still read and exposed as a property for pre-v2
  scripts. `from_workspace_dict()` turns a `.hws` into a runnable script, so `run_pipeline.sh`
  accepts either. Examples: `config/pipeline/naca_demo.json`, `multi_element_demo.json`.
- **`services/pipeline_stages.py`** (Qt-free, stdlib only): **the stage set is declared once,
  and the two hosts are adapters.** The four stages — resample · immersed solid · mesh · solver
  — are implemented twice (`pipeline_runner` blocking, `pipeline_ctrl` chained on QThread
  `finished_signal`), and until this module nothing knew the SET: an artefact could be produced
  for nobody (candidate 6a), and `Stage 1/3`…`3/3` was hand-written at 8 sites while four stages
  existed. Nobody typed a wrong number; there was no number to derive. Deliberately **data, not
  a base class** (the one thing that legitimately differs is how the hosts WAIT), and
  load-bearing: both hosts build their plan and their `Stage i/N` labels from `plan()` /
  `label()`. `PipelineConfig.stl3d_skip()` joins `cad_skip`/`solver_skip`, so "will this stage
  run?" has one shape for all four. Gated by `tests/test_pipeline_stages.py` (ten failure modes,
  all injection-verified in-test), shaped by two lessons: **both directions or it is not a gate**,
  and **order is recovered, not assumed** — the GUI's chain is read as a reachability graph over
  `self._pipe*` **references**, since a continuation handed over as an attribute is invisible to
  a call-only walk. Smaller lessons worth keeping: an injection that makes the source **fail to
  parse** looks exactly like the check working, and a check with an **exemption marker** is an
  escape hatch for whoever next trips it.
- **`services/pipeline_runner.py`** (Qt-free, blocking): runs the 3 CLI stages via subprocess
  (surface_resampler → HybMesh2D → getPGrid→unicones); `run_pipeline()` returns the artifact paths.
- **`services/ib_handoff.py`** (Qt-free): **producing a phi field is not the same as wiring one
  up.** STL3d writes a *Tecplot* field; the init DLL reads a *headerless* `phi.dat` with the
  STL3d grid spec compiled into it. That conversion lived in a Qt method no headless runner could
  call, so the runner collected the phi into `out["phi"]` and passed it **nowhere**, and Run All
  had no IB stage at all — both fell back to whatever `work/phi.dat` the reused case dir held,
  i.e. the previous geometry's solid converging to a believable answer for the wrong shape.
  `link_phi_to_solver()` is the one owner, called by all three hosts. Three rules:
  **`PHI_HEADER_LINES` is checked against the `skiprows=` its own reader uses** (one number, not
  two guesses); **the phi field and the init DLL are ONE fact, so it takes over both or neither**
  (the DLL can only read the field this stage traced, so a mixed pair is a wrong answer rather
  than an error — only when both are blank does the stage supply both, and naming one keeps both
  and warns); **`replace` is the difference between the callers** (the GUI overwrites a field
  computed *now*; the headless runner fills blanks only, as `_run_solver` already does for
  `.vrt`/`.cel`/`.bnd`). It deliberately does **not** decide whether the solve has an immersed
  solid: `immersed_solid` is the CALLER's declaration and a stage may not overrule it —
  `send_stl3d_to_solver` turns it on because a button is allowed an opinion a stage is not. Gated
  by `tests/test_pipeline_ib_handoff.py`, which drives the real conversion, proves the chain by
  AST, and **compiles the generated DLL** (`stage_dll` returns `""` with a mere WARNING on a
  compile failure, so a source that does not build degrades silently to "no init DLL").
- **`services/solver_case.py`** (Qt-free): case-dir orchestration
  (`results/solver/<name>/{work,grid,dll}`) shared by the GUI worker and the headless runner, and
  the answer to **where a case lives** (`case_root_for` / `work_dir_of`). **The grid stem is the
  RESOLVED case name, not the requested one** — auto-versioning renames the *directory*, and a
  stem left on the old name writes `case.grid` into `case_002/`, which runs, so it stays invisible
  until one directory holds two 1.3 MB grids distinguishable only by what `input.in` references
  (USER-REPORTED 2026-08-13). **`prepare_case_dir` is the ONE place that makes a path in
  `input.in` relative to the work dir**: grid/bc as `../grid/<case>.*`, IBM DLLs as `../dll/*.so`,
  a BC type-11 DLL as `./x.so`, the phi field staged under a fixed name.
  - **Restart references** (#25, USER-REPORTED 2026-08-20) were the only paths nothing touched, so
    the deliberately absolute autofilled path reached the solver verbatim and a GUI restart errored
    out while an *exported* case ran. `restart_refs_for_work_dir` rewrites an **absolute path to an
    existing file** (inside `work/` → bare basename; elsewhere → out and back) and passes a blank,
    an already-relative or a non-resolving value **straight through** — a wrong path must surface
    as the solver's own error. Three load-bearing details: the dump is **referenced, never copied**
    (largest file in a case); the relative form is **out and back**, because the panel computes it
    from the case *name* before auto-versioning may rename the directory; and the result is
    **returned into `generate_input_in` (`zdump_rel`/`convg_rel`), never written back onto `cfg`**,
    since `cfg` is what the `.hws` and pipeline script are saved from and a work-dir-relative value
    there resolves to nothing from the next work dir. Gated by `test_restart_paths_relative.py`.
  - **The last three of the nine quoted paths got the OPPOSITE answer, and the difference is SIZE**
    (#29): `mpi_comm_map_fn`, `cfl_schedule_fn`, `probe_points_def_fn`. `table_refs_for_work_dir`
    **copies** the file into `work/` and quotes the bare name — a table is small, and a case that
    does not hold its own inputs is the problem. Three shapes: a **bare name** is emitted unchanged
    but still **reserves its basename** (or a later field's absolute path with the same basename
    lands on the file it quotes); an **existing file** is staged under a collision-safe basename;
    anything that does **not** resolve is emitted unchanged. Copy, never move, never hard-link.
    **The claim is narrower than the tempting one, and the tempting one created this ticket: every
    quoted path that RESOLVES is work-dir relative.** A value naming nothing stays absolute
    deliberately, as does a table named like a run output (`^binDump`, `.plt`). Do not upgrade this
    to "every quoted path" without re-reading `_stage_table`. Two neighbours had to keep up:
    `case_export` no longer reports a file `input.in` REFERENCES as an unrecognised skip (the
    allow-list is deliberately **not** widened — a reference is a fact about this run, a suffix a
    glob over every future one), and `case_archive` reads the previous `input.in` for names no list
    can hold. What a work dir already means lives in `case_files` (`WORK_STAGED`,
    `staged_bare_names`), because the restated version had **already drifted**. The reservation
    asks whether the file EXISTS, which is both more precise and what makes the counter TERMINATE
    (`input.in` excepted, being written *after* staging). Resolvers live in
    `services/case_input_paths.py`; gated by `test_input_in_staged_paths.py` (10 properties, 42
    assertions, all injection-verified). **Nothing was measured on the solver here** — no case in
    this repo sets any of the three keys — so the justification is self-containment, not evidence.
- **`services/case_archive.py`** (Qt-free): **a restart continues in the SAME case dir, and must
  not write over what it resumed from** (#26, USER-REPORTED 2026-08-20). `archive_previous_outputs()`
  moves the previous run's outputs into a fresh `work/prev_<NNN>/` before this run writes anything.
  **Two facts about the solver decide the shape, both measured on the real binary — the first
  version shipped without an acceptance run and was wrong.** (1) The restart reference must be a
  **BARE name in the work dir**, or the solver derives a per-zone path into a directory that does
  not exist and dies with `Can't open file`. (2) It must **DIFFER from the solver's own output dump
  name** (`binDumpZ.dat` + the `-t` tag) — i.e. exactly the file a GUI restart resumes from, so
  *every* same-folder restart was already rewriting its own restart point in place.
  - **The zone dump moves too, and `work/` keeps a bare-named HARD LINK to it** — #30's correction
    of #26, which had to leave the dump out in `work/` so the archive was never complete. One inode
    satisfies both halves at ~0 bytes (measured 24352 → 24356 KB across a 1597 KB dump). **This is
    the ONE place this repo's "a hard link is not the cheap version of a copy" rule flips, and for
    that rule's own reason**: the hazard there is that editing one path rewrites what the case
    holds, and a zone dump is never edited. A stale link is retired **by INODE**
    (`_archived_inodes`) — unlinked, never moved. A file already named `.prev_NNN` that is *not* a
    link is filed into the archive it is named for, which is how a pre-#30 case upgrades.
  - **Every archived file ends in `.prev_<NNN>`** (`case_files.archive_name`): a trailing run tag is
    replaced, a name without one is appended to, a name already carrying a suffix is left alone. The
    tag is what the rename discards, so **`RUN.txt` is where it survives**. `is_run_output` **strips
    the suffix before matching**, because two patterns anchor on the END of the name (`\.plt$`,
    `^fort\.\d+$`); widening them would loosen them for every future name, seeing through our own
    suffix does not.
  - Rules: **an allow-list decides, not a glob**; that list and `ARCHIVE_DIR_PREFIX` live in
    `services/case_files.py`, which `case_archive` and `case_export` import **as peers** (facts
    about a case, not about an export); the inputs `prepare_case_dir` stages **stay**, or the
    resumed run restarts into nothing; a file **neither** list recognises stays put and is **named
    in the log**; **move, never copy**; **nothing is created when nothing moves**; and an exhausted
    counter archives **nothing** and says so, because giving up the other way is the exact
    destruction the archive exists to prevent.
  - **That refusal has a second instance, and the archiver used to commit the destruction it names**
    (#42): `…dat.cli` and `…dat.gui` — one output of one case run by the two hosts — both want
    `….prev_001`, and the second `shutil.move` landed on the first silently. Reachable without
    misuse (headless, then a GUI run answering *Overwrite*, then a restart).
    `case_files.archive_name_collisions` asks it ONCE over the set about to move, in the module that
    owns the mapping, and **before the retire loop** — before ANY move — so a refusal is a no-op the
    user can retry. Refused wholesale, naming both files, the name they both wanted and the *reason*
    (that archiving drops the run tag, which the file names alone do not show). It does **not** claim
    the run continues "beside" the files it declined to move: the refusing run carries one of the two
    tags itself, so it overwrites the half of every pair sharing it — out of scope in #42, said out
    loud rather than softened.
  - **The restart reference follows the file**: `restart_refs_for_work_dir(..., moved=)` consults the
    move map *before* the existence check, and it is the **one** thing that rewrites an
    already-*relative* reference. That is why #26 was blocked by #25.
  - The disposition is **one value, not a pair of booleans**: `solver_case.CASE_ARCHIVE` /
    `CASE_IN_PLACE` / `CASE_NEW_VERSION`, mapped to the two mechanical flags in one place
    (`case_dir_flags`), which **raises on an unknown value** — `(False, False)` is a real disposition,
    so a typo would otherwise run silently in a directory nobody chose.
  - **`case_export` had to learn to see the archive**: `plan_export` skipped every non-file entry
    silently. Each archive is walked as its own subdirectory with **nothing** allow-listed (every
    file in it is an output by construction), except the dump `input.in` quotes — which forced the
    reference match from BASENAME to the resolved path.
  - **Each archive carries a `RUN.txt`** (`services/case_run_note.py`, Qt-free — writer *and* reader,
    so the format round-trips): timestamp, run tag, what that run resumed from, the dump's archived
    name, and how far it got. Two must be RECOVERED rather than remembered — the tag is read off the
    file names *before* the rename, and the iteration count from the LAST ROW of the convergence
    history (the solver prints `Global Iteration count` to stdout, gone by archive time). Stored as
    `last_iteration` + `convergence_interval`, and **the two together recover the printed count**
    (`1990 + 10` = the 2000 the acceptance run measured). **That arithmetic REVERSES what #30 and
    #31 recorded** (#43): both argued naming 2000 would be a fabrication and printed the bound
    `1990+`, overruling #31's own spec — while the gate stated that bound as `[1990, 2000)`, a
    half-open interval **excluding the value it claims to contain**. What survives is that an
    *interrupted* run makes the sum an **upper** bound, which belongs in a tooltip, not in a refusal
    to name the number. One home: `case_run_note.iteration_span`. **Keep the specimen: it was not a
    typo but a considered argument written down with its evidence, and it survived two issues because
    the evidence was never checked against itself.** An unreadable history reports **-1, never 0** (0
    is a real cold-start answer), and `resumed_from` has three states for a sharper version of the
    same reason: `""` = cold start, **None** = "we could not tell", because rendering that as "cold
    start" would be a positive false claim. `RUN.txt` is the one archived file not ending in
    `.prev_<NNN>` (the archive's own record, not something a run produced); `case_export` names it as
    a skipped OUTPUT and does not ship it.
  - **The run tags are declared once**, in `case_files.RUN_TAGS` — a rename rule stripping a tag
    nobody writes silently does nothing.
  Gated by `tests/test_restart_archive.py` (10 properties against the real `prepare_case_dir`, export
  planner and dialog; #42's guard has its absence INJECTED with a negative control) **and by
  `test_case_export.py` check 16**, because the archive's behaviour proven in the archive's test says
  nothing about a planner nobody re-pointed at it. Acceptance: the real `prepare_case_dir` over the
  reported case, then the real `unicones` on its output — **exit 0, `Global Iteration count 1000`**
  (a cold start reports 0), restart source byte-identical afterwards, archive intact. Residue named:
  #25's cross-case reference resumes correctly but leaves an empty `binDumpZ.dat.0` in the work dir.
- **bDecompose runs IN THE CASE** (`workers/solver_run.py::_run_bdecompose`; classification in
  `services/case_files.py`; #37). It ran in the binary's own install dir, which was worse than "the
  output lands outside the case" in three ways: **the stage could not find its inputs, by
  construction** (the para file names the grid and bc as BARE BASENAMES, and getPGrid writes those
  into the case's `grid/`); **the install dir made that silent**, since it held a
  `mesh_cartesian.grid` from one hand run — so a case NAMED `mesh_cartesian` decomposed the STALE
  one and the solver ran MPI on a decomposition of a different mesh; and the answer file went into a
  **shared, possibly read-only** location two runs would race on. It now runs in `grid/`. Three rules:
  - **The answer file is NOT `para.in`** — a deliberate departure from the issue's proposed scope,
    because getPGrid owns `grid/para.in`, `case_export` ships it as `grid/getPGrid.in` and
    `run_case.sh --regrid` feeds it back, so sharing the name would silently replace getPGrid's
    answers. It is fed on **stdin**, so the name is ours: `case_files.BDECOMPOSE_INPUT`.
  - **`is_run_output` must NOT learn `mpi_*`, and this is measured rather than argued**: for the comm
    map the file bDecompose PRODUCES and the file the solver READS are the *same name*, and
    `case_input_paths._stage_table` asks `is_run_output` whether to stage a user-named table — so
    widening it silently undoes #29 for exactly the field #37 is about. The question is asked **per
    DIRECTORY**: `is_decompose_output` for `grid/`, `is_run_output` for `work/`. (An earlier write-up
    claimed the classifier reads `COMM_MAP_NAME`; it does **not**, it matches by pattern — the same
    every/all/only overclaim habit recorded against #25 and #29, copied into two files at once.)
  - **Filling `mpi_comm_map_fn` in is still the caller's**: the produced path is named in the log and
    nothing more, and #29's staging carries it. **`case_export` keeps shipping the comm map — and the
    first version of #37 BROKE exactly that**: the new `grid/` branch `continue`d *ahead of*
    `plan_export`'s `elif rel in referenced`, the branch whose own comment states the rule it was
    jumping. One condition fixed it (`rel not in referenced`), leaving `_is_output`'s precedence
    untouched. **The gate did not pin the wrong side, it never covered this side** — which decides
    the remedy: a check was ADDED, not corrected.
  Validation grew the other half: `_validate_solver_config` never checked `bdecompose_binary` at all.
  It now refuses a blank, a missing file, and a **wrong executable format**
  (`services/paths.wrong_executable_format`; the shipped binary is x86-64 **ELF**, this dev machine
  arm64 macOS). That test is narrow on purpose: an unrecognised format answers False, because "we
  cannot judge this" must not be reported as broken, and the MACHINE word is not compared (Rosetta).
  Gated by `tests/test_bdecompose_in_case.py` (14 properties). **A shared decomposition needs
  nothing**: because the stage only NAMES what it produced, pointing `mpi_comm_map_fn` at one gets
  precisely #29's behaviour. Evidence claim, narrowed in review: checks 1-11 are BEHAVIOURAL and were
  verified by injecting the defect **by hand**, which is not an in-test injection; exactly ONE
  injection is permanent (check 13 mutates `_OUTPUT_PATTERNS` live and asserts the CONSEQUENCE).
  Residues: the comm map is staged into `work/` only on the NEXT run (it still resolves, being
  relative); bDecompose's other outputs get no home in `work/`, because whether the solver wants them
  there is not knowable here; and a stale `grid/bDecompose.in` still ships as an input, the same
  fossil class as getPGrid's own `para.in`, recorded rather than fixed. **The acceptance run is
  OUTSTANDING and the gate says so** — the prebuilt binary cannot execute here, so the tests pin the
  SHAPE of the run, not the binary's acceptance of it. #26 is why that distinction is written down.
- **`services/case_clean.py`** (Qt-free) + the second half of `views/case_dir_dialog.py`:
  **"Overwrite" and "empty this folder first" are two different answers, and the destructive one
  shows its work** (#33, DECIDED 2026-08-21). Reuse-in-place leaves a case a mixture of this run's
  output and the last one's — a defect class with **two defences and no fix**
  (`report_stale_ibm_artifacts`, `case_export_usage.unused_reason`). Rules:
  - **A separate button, never a redefinition.** The non-restart prompt is `Overwrite in Place` /
    `Clean and Run…` / `Archive Previous` / `New Versioned Dir` + Cancel — **four plus Cancel, #33's
    stated ceiling**, so the next answer to want a button is where this stops being a message box.
    The restart path reaches none of it (#31).
  - **`Archive Previous` is a REVERSAL of #31, on a ground #31 did not rule on.** #31 removed it
    because a restart stopped reaching the prompt (*"a branch nothing can reach reads as a working
    feature"*), **not** because archiving is wrong for a non-resuming run. Once `Clean and Run`
    exists the alternative is needed, or keeping previous results *in this folder* has no answer but
    splitting the case across two directories.
  - **Measure, show, then delete — three steps, and the deletion is not one of them.**
    `plan_case_clean(work_dir)` builds a `CleanPlan` and touches nothing; the prompt renders THAT
    plan; `apply_case_clean` acts on the approved list and never re-reads the directory. This repo
    has the scar the separation is for — an `ls` and an `rm -rf` in one command destroyed ~40
    gitignored artifacts — and it also puts a possibly huge deletion on the worker thread.
  - **Reuse the classification, do not glob.** A file neither `is_run_output` nor `WORK_STAGED`
    recognises is **kept and named in the log**, and so is a directory that is not an archive (an
    `isfile` guard that silently passes over a folder is the bug `plan_export` had). Scope is the TOP
    LEVEL of `work/`.
  - **But the classification alone KEEPS the file #33 exists to remove**: `phi.dat` is in
    `WORK_STAGED`. The fix is **not** to delete that entry (a config whose `ibm_phi_file` resolves to
    `work/phi.dat` itself has no second copy, and the literal reading destroys it). The question
    asked is **"is it stale?"** — `solver_case.stale_phi_name` returns the name only when this run
    stages no phi at all, which is exactly what `report_stale_ibm_artifacts` warns about, so the
    warning and the deletion have ONE owner. `plan_case_clean(work_dir, stale=…)` takes those names
    from the caller, because whether a staged input is a leftover is a question about the *config*.
    `dll/` is out of scope, named rather than implied.
  - **`work/prev_*/` is NOT deleted by default**, and the tick that includes it is off every time the
    dialog opens (a fresh `QCheckBox` per call, never read back from `ui_state`).
  - **Two guards in `apply_case_clean`, and only one stops a deletion**: the plan's `work_dir` vs the
    run's, refused wholesale with one message naming both; then every entry re-checked to be
    `is_inside` that dir. Measured — remove the first and every entry is still refused individually;
    what is lost is the single legible refusal.
  - **A restart is refused even if handed a plan — and the guard CORRECTS the flags it invalidates.**
    Merely *skipping* the deletion shipped first and was wrong: a clean's flags are `(overwrite,
    no-archive)`, so declining left the run overwriting the previous outputs as it produced its own —
    #26's hazard, worse than either answer the user could have picked. It now sets `archive_prev`.
  - **Never unattended**: Run All / batch answers `CASE_NEW_VERSION` before any prompt;
    `confirm_case_clean` returns cancel when headless; an **empty** work dir degrades to
    `CASE_IN_PLACE` with a log line rather than prompting about nothing.
  - **One approved value, not a pair**: `ApprovedClean(plan, include_archives)`, exposed as
    `pending_clean()` — a verb, because a `getattr(self, "_case_clean_plan", None)` reach would make
    an uncomposed mixin degrade silently instead of failing.
  - **`_resolve_case_disposition` lives in `controllers/case_disposition_ctrl.py`** — moved there when
    the question grew its second step; a concept split, not just a line count.
  Gated by `tests/test_case_clean.py` (12 properties + 6 injections), which imports **no Qt at all**
  — the acceptance list asks for that in as many words, and the first version built a `QApplication`
  so `is_headless()` would answer True, making the deliverable literally false.
- **`services/restart_points.py`** (Qt-free) + **`views/panels/restart_chooser.py`**: **the restart
  point is PICKED from the case's own history, not typed as a path** (#31, USER-REQUESTED
  2026-08-21). The retired autofill looked for a fixed name **in `work/` only**, knowing nothing
  about #26's archives, while the thing being decided is an **iteration count**.
  `list_restart_points(case_root)` returns cold start, the newest un-archived dump, then each
  archived leg newest-first with its count, timestamp and run tag; the chooser is one column of
  radio buttons plus an "Other file…" escape.
  - **The MODEL still holds a path**, absolute (#25), so `.hws`, pipeline scripts, `case_export` and
    `prepare_case_dir` are untouched — but **one control authors all three** fields; the three
    `FieldSpec` rows are gone and the names are declared in `SOLVER_EXTRA_AUTHORED` with a reason.
  - **Radio buttons, not a list widget, and the control reports its own edits.**
    `undo_ctrl._wire_widget_edits` is the ONE traversal that knows "the user touched this panel", and
    it connects spin boxes, combos, line edits and *checkable buttons* — a `QListWidget` selection is
    none of those — and the rows are **rebuilt whenever the case changes**, long after that one-shot
    traversal ran, so a composite control declares **`panel_edited`**.
  - **The list is derived on every call and cached nowhere** — the case dir is the truth. The cost is
    stated rather than optimised away; a cache is the thing this rule forbids.
  - **The marker is matched by BASENAME**: for an archived dump the reference names a hard link (#30)
    that the *next* archive retires, so matching by path or inode would lose the mark on exactly the
    row #31 exists to highlight.
  - **Every leg's count comes from one function, `case_run_note.iteration_span`** (#43). #31 shipped
    the opposite — an archive with no note got "unknown", its history *deliberately not re-read* —
    which cost exactly the legs it meant to protect, while `_latest_point` two functions below
    computed the live row's count from that same kind of file with that same reader. A leg whose span
    cannot be computed still gets a row, unlabelled: hiding a restart point that exists is worse.
  - **A restart source inside an archive gets a bare-named hard link in `work/` on demand**
    (`case_archive.bare_link_for_archived_dump`, called by `prepare_case_dir` *before* the archive
    step and independently of `archive_prev`). Without it the chooser's headline click produces the
    exact reference #26 measured the solver dying on. It refuses rather than guesses twice: a name
    taken by a different file is not overwritten, and a filesystem that cannot link warns instead of
    silently copying the largest file in the case.
  - **A restart whose source is not there is refused in the GUI**, both references resolved (a
    relative one against this case's work dir) and named with their missing path.
  - **The case-dir modal is dropped on the restart path** (CONFIRMED 2026-08-21); Run All untouched.
    One confirmation fewer means the archive step must be legible in the log on its own.
  - **`case_root_for` / `work_dir_of` live in `solver_case`**; `restart_points` re-exports them. The
    claim is exactly that narrow — the first write-up said "where a case lives has one spelling" and
    it was **false**: 11 `results/solver` joins exist and one full construction was replaced.
  - **One departure from the issue's text, and one REVERSED**: the rows first showed the count as a
    bound (`1990+`); #43 reverses that to `iteration 2000` with both surviving caveats in the
    tooltip. The departure is recorded rather than deleted, so "we deliberately departed from the
    spec" is not left standing as a validated precedent. The remaining one: the issue says this keeps
    "`prepare_case_dir` untouched", which it does not.
  - Residue, named rather than fixed: **a case-name change keeps the previously picked absolute
    path**, so it can land on "Other file…" as a cross-case restart — visible in the row's own field,
    refused by `_validate` if the file is gone, and no worse than the retired autofill.
  - **A row has to FIT, and that is structural rather than cosmetic** (USER-REPORTED 2026-08-27).
    `SolverConfigPanel` caps content at 430px with `ScrollBarAlwaysOff` + `setWidgetResizable(True)`,
    so a row wider than the viewport is CLIPPED with no window size that rescues it (measured: 494px
    wanted against ~380px usable). The timestamp drops its year and seconds, the marker became
    `← last run` (321px), and `_Row` elides what a narrower sidebar cannot fit — an ellipsis says
    there is more, a clip pretends the row ended. Two consequences: `minimumSizeHint` must stop
    advertising the full width, or the row forces the content wider than the viewport again; and
    **the marker is BOLD as well as worded**, because the words sit at the END and are elided first.
    A check asked of a row built from the CURRENT (short) text proves nothing — measured, it passed
    with the mechanism deleted — so the gate uses a deliberately over-long row. **The panel itself
    now scrolls sideways** (`ScrollBarAsNeeded`, USER-REQUESTED 2026-08-27; the setting
    `mesh_config_panel` has had since 2026-07-28) — a safety net for the PANEL, deliberately not the
    mechanism for the rows. `stl3d_panel`, `result_panel` and `sidebar` still carry `AlwaysOff` and
    have the same latent gap.
  Gated by `tests/test_restart_chooser.py` (12 properties against the real `prepare_case_dir`, the
  real widget offscreen, the real `SolverControllerMixin` and the real `AppController`; checks 2-4
  and 8 are **inverted** versions of ones that asserted the raw last row, a blank count, a blank
  TIMESTAMP and the old marker wording), and `test_restart_archive.py` check 7 is the **inverted**
  version of the one that pinned the dialog's restart branch. Blind spot: nothing here runs
  `unicones`, so the bare-name reference is pinned against the SHAPE #30's acceptance run measured.
- **`services/case_sources.py`** (Qt-free): copies the CAD/STL a case was cut from into
  **`grid/cad/`**, so the case describes its own geometry and not only the mesh. Fed by
  `solver_ctrl._case_source_files` / `_case_generated_files` and `pipeline_runner._case_sources` —
  the imported source, the resampled `.dat` the mesher read, the immersed STL, the mesh
  `.provenance.json`, and the **mesh parameter file**, which is *generated* rather than copied
  because the GUI only materialises one in `temp_dir` and deletes it on exit
  (`mesh_config_io.config_to_text`, split out of `save_config_to_file` so the staged config is
  byte-identical to a hand-saved one; it takes the destination path because a geometry outside the
  repo is emitted relative to the config file). Rules: **copy, never move** (a *move* is
  unimplementable anyway — one resampled `.dat` legitimately feeds several cases); **a hard link is
  not the cheap version of a copy**, since one inode means editing the CAD afterwards silently
  rewrites what the case holds; **sidecars follow their file** (`<name>.dat.meta` carries the
  per-segment BC labels and No-BL flags); **collisions are renamed, not overwritten**; generated
  files are staged **last** and marked `(generated)`, because a reconstruction must not read as
  evidence. `SOURCES.txt` maps every staged name back to its absolute origin, rewritten in full each
  run — and it is the *only* index there is, so **`tools/scripts/case_sources_index.py`** reads them
  back to answer "if I change this CAD, which cases go stale?" (matching by `(st_dev, st_ino)`, then
  path, then substring; exit 1 on no match). `case_export` descends into `grid/cad/` with its own
  allow-list.
- **`services/stl3d_case.py`** (Qt-free): the same for the immersed-solid stage — `validate()`,
  `work_dir_for()`, `prepare_case_dir()`. Both `stl3d_ctrl.run_stl3d` and the headless IB stage go
  through it. **`Stl3dConfig.para_in_text()` must match `solver/preprocess/STL3d/src/stl3d.cpp`'s
  `cin >>` sequence line for line** — five reads and deliberately no ascii y/n line (the binary
  auto-detects); an extra line is consumed as the case name and the run silently produces an empty
  phi field with exit code 0. `tests/test_stl3d_case_parity.py` parses the C++ and gates it.
  **Inside `stl3d.cpp`, `STLobject` carries two different x extents and they must not be confused**:
  `xloc_db` (the index `trace_ray` looks rays up in) is keyed by element **centre** x, while the ray
  culling window `xmin`/`xmax` comes from the **vertices** — and has to, since a centroid sits
  strictly inside the surface. Every ray in the strip between the last centre and `xmax` passes the
  culling check with nothing at or after it in the index, so `lower_bound()` returns `end()` and
  dereferencing it killed a GUI IB run with `[STL3d] exited with code -11`. A **flat 2D profile is
  the worst case** — a fan triangulation drags every centroid toward the apex, leaving the far
  ~20-30% of the x extent centroid-free (measured 5.856 vs 6.070, the last 41 of 128 slices).
  `ctr_strip_at_or_after()` clamps instead. Gated by `tests/test_stl3d_flat_profile_trace.py`, which
  compiles `stl3d.cpp` itself (CI does not build STL3d, and a stale binary must not pass it).
- **`services/contour_render.py`** (Qt-free): renders a Tecplot result to a contour PNG
  (matplotlib Agg) for headless runs.
- **`controllers/pipeline_ctrl.py`** (`PipelineControllerMixin`): GUI **Run All** — chains the
  per-stage QThread workers on their `finished_signal` (batch mode: no per-stage dialogs), ending on
  the auto-loaded Results contour. The **immersed-solid stage sits where the headless runner puts
  it, before the mesh**, so a script and the button build the same case; it is optional and skipped
  *out loud*. Save/Load of the script is **`controllers/pipeline_io_ctrl.py`** — the two share
  nothing but the config classes, and the split kept the file inside the GUI length budget.
- **`tools/PreProcessor/run_pipeline.py`** + **`run_pipeline.sh`**: headless entry point
  (`--no-solver`, `--no-contour`, `--png`).

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
