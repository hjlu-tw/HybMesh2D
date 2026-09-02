---
paths:
  - src/**
  - include/**
  - config/**
  - tests/cpp/**
---

# Mesher rules — configuration and core C++

Loaded on demand when a file under `src/`, `include/`, `config/` or `tests/cpp/`
is read. Rules only: the rationale — the measurements, the dated acceptance runs,
the injections, the reversals and the named blind spots — is
`docs/design_notes/mesher.md`. Read that note before overruling a rule here, and
when a rule changes update BOTH.

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
  waits for: a `blocks[].orientation`. (`on_geometry` and `binding` were on this list and are
  implemented by #52; the `interface`/`cut` kinds and a second block by #53.)
- **A block's orientation is the corner order of its own four edges**, `[south, east, north, west]`,
  south/north running i-min→i-max and west/east j-min→j-max. A **clockwise** corner ring is refused
  under the TOPOLOGY code, never silently re-wound. **SUPERSEDED IN PART by #53**: a deviation in
  DIRECTION is no longer refused — the south edge fixes the frame and the other three are traversed
  as the ring requires, because a shared edge has one declared direction and two blocks. A set of
  four edges that does not CLOSE a ring is still refused by name, which is the half of the original
  argument that survives.
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
  from the surface test rather than copying it. (#52 added `mb_bound` / `mb_cavity`, #53 `mb_hgrid`.)

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
  **SUPERSEDED by #53**: the gate is the KIND, so an `interface`/`cut` side is not reported and a
  multi-block topology lists exactly its outer walls.
- **The `[south, east, north, west]` convention is DATA, in one place** (`mbSideAxis`). A dedup of
  `MbWallSpec`/`MbWallHeight` was considered and DECLINED: they face opposite directions and the
  shared part cannot be written HALF.
- Gated by `tests/cpp/test_mb_quality.cpp` (9 groups, 53 checks) and
  `tests/test_multiblock_quality_surface.py`. **Its injections are HAND runs, dated in the C++
  test's docstring** — a C++ test cannot mutate the implementation it linked against, and that
  distinction must not be blurred. What IS permanent is two **negative controls** computing an
  injection's own premise (check 6 the bow-tie's +0.5 area, check 2 its ~17x stretch). Sharpest
  blind spot: nothing runs the solver or grid converter on the folded mesh.

**Boundary conditions are DECLARED; geometry attaches by ARC LENGTH** (#52; still the one pure
entry point). A corner attaches to a source segment at a normalized arc-length position
(`kind: "on_geometry"`, `geom` / `seg` / `t`), a wall edge declares the segment it lies on
(`binding`), and every generated boundary edge carries that segment's condition and its (geometry,
segment) key into the export. **No tolerance anywhere in this chain**, because the answer is in the
declaration before a node exists. (The hybrid path resolves by proximity instead, and on a curved
wall that drift exported a band of wall at every junction.)
- **Arc length, NEVER a point index**: re-resampling changes the point count. Measured through the
  real binaries — one topology against 21- and 41-point resamplings gives identical `.vrt` node
  COORDINATES, with the negative control that neither has a sample at any of the four attached
  positions.
- **`t = 1` means "where this segment ENDS"** — the next segment's first point only when there IS a
  next one; on the last segment of an open polyline, that segment's own final point, stable because
  the resampler pins every segment's endpoints.
- **A segment's own points stop ONE POINT SHORT of where it ends, and the run is extended by one.**
  A shared joint is assigned to the LATER segment (`resSegId.back() = segId`). For the last segment
  of a CLOSED loop the point to reach for is index 0 (`loadGeometry` dropped the duplicate closing
  point).
- **A trivial piece break at index 0 is not a second piece** — sidecars in this repo disagree about
  recording it (`NPIECES 0` vs `NPIECES 1 0`), so `multiPiece()` asks whether any break falls
  strictly inside, never `pieceBreaks.empty()`.
- **A corner at `t = 0` or `t = 1` sits on a JOINT that two segments both own, so a bound edge
  accepts it from either side** (`tOnSegment`) — without it the canonical declaration, one block
  side per source segment on a closed body, cannot be written at all. The equivalence compares the
  sidecar's own point INDICES, never coordinates.
- **A bound edge FOLLOWS the segment's polyline; it does not cut the chord.** One code path serves
  both (an unbound edge's "polyline" is its two corners), and that reduction is bit-identical.
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
  row per patch naming the segment it was read off.
- **`MbWallSpec` reports all four sides and the gate stays `kind`**, since "labelled inlet" and
  "viscous surface whose first-cell height matters" are different questions. SUPERSEDED by #53: the
  `kind` gate now bites — an interior side is not a wall — so the list is the outer walls. Why:
  `docs/design_notes/mesher.md`, "`MbWallSpec` still reports all four sides, and the #51 note".
- The adapter's ~15-line boundary-patch summary is PRESENTATION, not classification, so the pure
  side is no longer literally decision-free; a second such block belongs beside `measureMbQuality`.
- **The shipped example states its own limit**: `examples/geometries/square_cavity.dat` is an OPEN
  polyline stopping one sample short of the seam, so its segment 3 does not reach the block's
  south-west corner and the west edge is deliberately left unbound (a straight chord carrying
  `BC_GEOM`).
- Gated by `tests/cpp/test_multiblock.cpp` checks 12-16 and
  `tests/test_multiblock_binding_surface.py` (real resampler AND real mesher), plus golden cases
  `mb_bound` and `mb_cavity` — the shipped example on the shipped geometry, since documentation a
  user runs must be covered. Injections are HAND runs, dated 2026-08-28.
**Blocks are welded TOPOLOGICALLY, counts PROPAGATE, and the edge KIND is an enum** (still the one
pure entry point; #53). Any number of blocks; an interior line is declared ONCE, as one edge of kind
`interface` or `cut`, and both blocks name it. **Full rationale, measurements, the declined review
findings and the dated injection log: `docs/design_notes/mesher.md`.**
- **Coordinate welding is UNAVAILABLE, not just unpreferred**: wall spacing ~1e-7 beside far-field
  ~1e-1 leaves no tolerance in between (the iso-line tracer's own argument). Welding is ALLOCATION,
  not comparison — one node per declared corner, an edge's interior nodes once per declared edge, and
  a block READS its four sides' node ids. There is no tolerance literal in the module. Negative
  control: two corners at the SAME coordinates under different ids stay TWO nodes.
- **Only the block INTERIOR is interpolated now** — `coons` at u = 0 computes `(X + west[j]) - X`, so
  a shared edge must be the side's OWN discretisation, not two curves that agree. Measured: 14/221
  and 8/35 golden nodes move by **1.11e-16**, the new value being the exact one. `golden_mesh.py`
  renders that as `worst 9.167e-01` — an ARTEFACT of zipping two sorted node lists whose x-groups
  split; **do not read its magnitude on a case whose node SET changed membership**.
- **The relation is "opposite sides of one block", and there is NO second rule for an interface** — a
  shared edge is one edge two blocks name, so it propagates across blocks by itself. `count` is now a
  SEED. The COUNT propagates; the **SPACING LAW does not**.
- **A conflict names both edges, both counts AND the chain**, a block at a time from a BFS over the
  recorded links; both gates put the two seeds TWO blocks apart, since a one-block conflict lets a
  chain-free report pass. A class with **no** seed is refused naming every edge in it — never
  defaulted, and **not** seeded from `SURFACE_MESH_SIZE`.
- **The kind is a real `MbEdgeKind` with its names beside it** (`mbEdgeKindName`, the `mbSideAxis`
  shape), not a string compared at six sites — it was the latter for one commit, and the review that
  caught it also caught a second copy of the four SIDE names in the `.cpp`.
- **It decides three things and NO arithmetic**: how many block sides the edge may be (`wall` 1,
  `interface`/`cut` 2); whether a `binding` is allowed (`wall` only); and whether it exports as a
  boundary face (`wall` only, also the `MbWallSpec` gate). An interface and a cut weld identically —
  **said out loud**: the distinction lives in the declaration, the validation and the report
  (`MbResult::sharedEdges`, a `Cut '<id>'` banner row), which is what makes a later divergence a
  change rather than a rewrite. Still never INFERRED from the binding.
- **Refusing a `binding` on an interface/cut costs a CURVED interface, and the refusal says so.** A
  binding both makes the edge FOLLOW the geometry and supplies the BC; only the second is meaningless
  on an interior line. So an interior line is a straight CHORD and the BL/far-field seam #55 wants is
  undeclarable. Refused rather than half-honoured — a binding whose BC half is silently ignored is a
  setting that does nothing — and it needs its OWN key, not a reused one.
- **A block's frame comes from its SOUTH edge, and this REVERSES #50's rule.** The other three sides
  may be declared either way and are traversed as the ring requires: a shared edge has ONE direction
  and two blocks whose frames need not agree. Nothing is inferred — four edges that do not CLOSE a
  ring are still refused by name, and a ring closing onto THREE corners is refused too (reachable:
  two distinct edges over one corner pair). The clockwise-ring refusal is unchanged. C++ check 9 is
  the **inverted** version of the one that pinned the old refusal.
- **"The four sides meet at four shared corner NODES" is checked, before the writes overwrite one
  with the other.** It looks tautological after the ring match and is not: it caught the
  dropped-reversal injection in both gates.
- Gated by `tests/cpp/test_multiblock.cpp` 17-23, `tests/test_multiblock_weld_surface.py` (which
  measures CONFORMITY on the exported files — interior edges shared by exactly two cells, the
  boundary set equal to the `.bnd`, one connected component) and the `mb_hgrid` golden case on the
  shipped `examples/topology/hgrid_blocks.json`.
- **THE SOLVER ACCEPTANCE RUN IS OUTSTANDING and the gate says so**: no four-block grid has been
  through `getPGrid` or `unicones` (this checkout has no solver tree). Other blind spots: nothing
  welds along a BOUND edge, nothing exceeds four blocks, and a block welded to ITSELF is still
  inexpressible (right for a transfinite fill, but an O-grid seam cannot be one edge).

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

## Named blind spots

Consolidated here rather than trailing each rule, so a coverage claim can be checked against
one list. #68 moved the first entry; #69 moves the rest of this file's.

- **The end-to-end re-resampling check uses a straight-sided geometry**, where an arc-length
  position is EXACT under resampling. On a *curved* segment an attached corner moves by a chord
  sagitta — a limit of the geometry, not of the binding. The curve-following half is pinned in
  the C++ test (`tests/cpp/test_multiblock.cpp`).
