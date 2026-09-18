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

**The `MESH_MODE 1` multi-block path's rules are `.claude/rules/mesher-multiblock.md`**
(#89), which points at the same design note and loads on top of this file for a
multi-block header, source, config or C++ test — and for `src/cli.cpp` and
`include/Config.hpp`, which both files' globs reach. What stays here is `MESH_MODE`
the SELECTOR with its exit codes, the single `.dat` key table, the BL parameters, the
pure layer and the core C++ modules.

## Configuration

### .dat Config Format (`config/Background_para.dat`)
Key-value text file, command-line args override file values. Parameters grouped by function:

| Group | Key examples |
|-------|-------------|
| Mode | `MESH_MODE` (0=hybrid BL+Gmsh, default; 1=multi-block structured), `MESH_TOPOLOGY_FILE`, `MB_SPLIT_QUADS`, `MB_SPLIT_RULE`, `MB_SPLIT_SEED`, `MB_SMOOTH_ITERS` |
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
(`X(KEY, type, field, default)` per row). The struct, the `.dat` reader, the per-geometry override
parser and `isBLParam` are GENERATED from it; `Config` holds one `BLParams`, not a second copy with
a second set of defaults. `Config::print()` is deliberately NOT generated (the banner is a grouped
report reused verbatim as the provenance sidecar), so `tests/cpp/test_bl_params_decl.cpp` check 6
gates it: every parameter must be reachable from the banner, and where the banner renders it as a
number its own value must appear there.

**`MESH_MODE` selects the generation path, and a parameter the active mode never reads is NAMED**
(`include/MeshMode.hpp` + `src/MeshMode.cpp`, in `hybmesh_pure`; #49). Mode 0 is the hybrid path and
the DEFAULT, so the feature's effect on an existing case is zero — measured, 9/9 golden SAME.
- **"Which parameters does this mode read?" is DATA, in one place.** Two macros declare the inert
  non-BL keys and the four BL parameters that SURVIVE; the 18 casualties are `BLParams.hpp` minus
  those four, so a new BL parameter is covered with no edit and gets the right answer by default.
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

**The implementation is a LIBRARY and the executable is a shim.** `hybmesh_core` (STATIC) holds
`cli.cpp` + `Mesh.cpp` + `BoundaryLayer.cpp`; `add_executable(HybMesh2D src/main.cpp)` compiles
**only** the twelve-line shim calling `hybmesh::runCli` (`include/Cli.hpp`). The executable compiles
no implementation, so there is nowhere to put logic a test cannot reach — before this the process
boundary was the mesher's only seam and `classifyJunctions` sat unreachable. Two consequences: **the provenance macros are defined on the
LIBRARY, not the executable** (on `HybMesh2D` they would apply to the shim alone and degrade every
banner and sidecar to `git unknown`), and the **CGNS-before-Gmsh link order** is `PUBLIC` on the
library so it propagates — load bearing, see the `cgsize_t` note in `CMakeLists.txt`.

**The tests live in `tests/cpp/`** — one executable per file, registered with ctest, `check.hpp`
for assertions (**record-and-continue**, not abort-on-first; `report()` reprints the FIRST failure
last so the cause is not buried under its consequences). A test **links a library target, never a
list of sources**: compiling `src/*.cpp` into a test executable works and quietly builds a second
copy of the implementation, testable but not the one the binary runs. Gated by
`tests/test_cpp_linkable_seam.py` (7 checks), because this property decays in silence — four holes
past "the shim is the only source", each of which *looks* satisfied: `#include "cli.cpp"`; a test
listing `../../src/Mesh.cpp`; a new `add_executable`; a `tests/cpp/test_*.cpp` CMake never
registered. All verified by injection.

**`hybmesh_pure` is the decision layer, and the BUILD is what keeps it honest** — the C++ analogue
of the GUI's "`services/*.py` must be Qt-free" rule. **The pure tests link `hybmesh_pure` alone and
are not linked against libgmsh at all** (verified with `otool -L`), so the moment such a module
*uses* `Mesh` or gmsh those executables stop linking (measured: `JunctionScheme.cpp` constructing a
`Mesh` gives `Undefined symbols for architecture arm64`). The grep and the linker cover different
halves — an *include* not yet used is invisible to the linker, a *use* invisible to a grep — so
`test_cpp_pure_layer.py` also computes each file's **transitive** include closure
(`BoundaryLayer.cpp` reaches `Mesh.hpp` only through its own header, so a direct-include check would
call it pure). The list is a **deny**-list (`HEAVY_SOURCES` / `HEAVY_HEADERS`, each entry carrying
its reason): a new `src/*.cpp` is assumed pure, since an allow-list exempts whatever nobody
enrolled.

`hybmesh::classifyJunctions` (`include/JunctionScheme.hpp`, `src/JunctionScheme.cpp`) is its first
member and the argument for the layer. It takes `vector<JunctionNode>` + `JunctionParams` (AoS, not
six parallel arrays) — never the 22-field mutable `FrontState` + `Mesh&` it was extracted with,
whose width hid how narrow the real dependency is (three positions/normals per node, one `skipBL`
bool, three config scalars) — and returns decisions **and warnings as data**: the
very-sharp-wedge message is user-facing prose about config keys and stays at the call site, while
the threshold (`tan θ × influence < 1.15`) is testable at three influence values without generating
a mesh (`tests/cpp/test_junction_scheme.cpp`). `thetaDeg` travels in the decision because
`HYBMESH_JUNC_DEBUG`'s trace format is parsed by `test_nobl_junction_acute.py`; a negative value
means no angle was measured. **This covered junction cases 3 and 4 for the first time** (θ > 270°,
which no geometry writer in the repo produces). `hybmesh::inertParamsSet` (`include/MeshMode.hpp`)
joined for the same reason: `tests/cpp/test_mesh_mode.cpp` can prove the four surviving BL
parameters SILENT, a negative a log-scraping test would have to establish by absence.

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
  (x, y)` — advisory only, nothing auto-corrected. An **isolated BL corner** (BOTH neighbours No-BL,
  issue #2) gets `[WARN] Isolated BL corner at (x, y)` pointing at the **`.meta` sidecar**, and that
  is PERMANENT: issue #4 (the two lateral columns such a corner needs) was closed **wontfix**
  2026-08-20 because the configuration is unreachable from this toolchain — the resampler flags every
  segment boundary `corner = 1`, `cli.cpp`'s `prevBL || nextBL` rescue promotes any such corner back
  to BL growth, and the GUI's `meta_io` copies the POINTS block through verbatim. Only a hand-written
  or foreign sidecar reaches it. **A case-1 slide REPLACES a stretch of the no-BL wall, so its own edges must carry
  that wall's BC by construction** (`slideColumns`/`slideWallRun` → `Mesh::recordBoundaryEdge`),
  matched to the wall edge each replacing edge covers by arc length: the column
  is a straight ray, so on a *curved* no-BL wall it drifts off the polyline by ~a chord sagitta while
  `pointOnSegment` accepts 1e-6 of a chord (measured 6e-8..1.8e-6 vs a 2.0e-8 tolerance), and every
  column edge past the first fell through to `BC_GEOM` — a No-BL inlet/outlet exporting a `wall` band
  exactly D_total long at each junction. A straight wall has no drift, which is why straight-duct
  coverage missed it. Gated by `tests/test_nobl_junction_acute.py` (`write_curved_duct`; the
  curvature is the point). `=0` restores the legacy taper-to-zero (~12% floor ramping back over arc
  length).
- **`Mesh.cpp`**: mesh data structure (Nodes/Elements/Edges), Gmsh far-field integration,
  VTK and STAR-CD export. **A boundary edge's BC and its source segment are ONE fact and are private**:
  write with `recordBoundaryEdge(v1, v2, srcNode, overwrite)`, read with
  `boundaryEdgeInfo(v1, v2)`. Two public parallel maps keyed by hand made "wrote the BC, forgot the
  segment key" a defect the interface could not prevent, and half an identity reaching the exporter
  exports as the wall default. The compiler now rejects outside access, which is why nothing tests
  *that*; the paired SEMANTICS are tested in `tests/cpp/test_mesh_boundary_edge.cpp` (a refused
  overwrite must not half-apply; the key is the unordered node pair; a BC with no resolvable segment
  still records). **`FARFIELD_MESH_SIZE` is a `Min()` cap on the size field, not a target**: the
  field grows from the wall (`FARFIELD_GROWTH_RATE`) and/or inward from the bounding box
  (`FARFIELD_GROWTH_RATE_OUTER`), so in a small domain it tops out below the cap and every
  larger cap gives a byte-identical mesh. Every run prints a `[ Mesh Size Field ]` block reporting how high growth
  reaches, the effective ceiling and whether the cap is dead/marginal/active — computed by
  re-evaluating the field expressions at the generated nodes, **not** by measuring cell edges (those
  run ~15% long on stretched triangles and would report a dead cap as live). Gated by
  `tests/test_size_field_ceiling.py`. Caveat: a
  custom domain outline is added with `geomId = -1`, so for a pure internal-flow case
  (`DOMAIN_FILE … nobl`, no `GEOM_FILE`) the wall-distance field is never built and
  `FARFIELD_GROWTH_RATE` is inert — only `FARFIELD_GROWTH_RATE_OUTER` grades the mesh.
- **`MultiBlock.cpp`**: the whole multi-block path behind one pure entry point — parse,
  resolve, fill (transfinite interpolation), split, and the already-resolved boundary edges
  the adapter records. Never throws; a malformed document comes back as an error string.
- **`MbQuality.cpp`**: the multi-block quality instrument. Pure, total, never throws.
- **`CellShape.cpp`**: the per-cell SHAPE metric and its median/p95/max reducer, shared by BOTH
  generation paths since #130 — the quad branch by `measureMbQuality` (#129), the triangle branch
  and `measureCellShapes` by `measureHybridCellShapes` (#130 wired them from
  `printHybridQuality` in `src/cli.cpp`; #141 moved that half into the file below). Pure, total,
  never throws; see the rule below.
- **`HybridQuality.cpp`**: WHICH cells the HYBRID path offers that metric, the two counts beside
  the figures, and which of the two reported sets each cell lands in (#143). Pure, total, never
  throws; see the rules below.
- **`MbControl.cpp`**: the multi-block WALL CONTROL FUNCTIONS — the elliptic smoother's
  source terms. Pure, total, never throws; rules in `.claude/rules/mesher-multiblock.md`.
- **`MbShared.cpp`**: WHICH nodes the multi-block smoother may move, and in whose logical
  frame a node two blocks share is moved. Pure, total, never throws; rules there too.
- **`Config.hpp`**: single-header; parses `.dat` files into ~50 typed parameters.
- **`GeomUtils.hpp`**: `Vector2D`/`Point2D`, segment intersection, normals, dot/cross.

**CELL SHAPE HAS ONE DEFINITION, AND IT IS A PURE FUNCTION OF CORNER COORDINATES**
(`include/CellShape.hpp` + `src/CellShape.cpp` in `hybmesh_pure`; #129, parent #128). A cell
arrives as its corner coordinates and leaves as one number; `reduceCellShapes` turns a set of
those into median / p95 / max. It knows nothing about `MbResult`, `Mesh` or gmsh, and
`tests/cpp/test_cell_shape.cpp` never builds an `MbResult` — that executable failing to link is
the signal the one definition has grown a dependency.
- **The metric depends on the CELL KIND and the two carry DIFFERENT NAMES.** A quad is the ratio
  of the distances between the midpoints of OPPOSITE edges (`quad_midline_ratio`); a triangle is
  longest edge / shortest edge (`tri_edge_ratio`). BOTH branches have a production caller since
  #130. A square is exactly 1.0 as a quad and exactly
  sqrt(2) as either of its split triangles, so a shared label would invite a comparison that
  means nothing. The arithmetic is shared because writing it twice guarantees drift; the two
  entry points, the two output lines and the two names stay separate.
- **NOT the edge-length ratio, and the sheared-parallelogram argument for that is FALSE** — on
  any parallelogram the two definitions agree exactly. What tells them apart is TAPER: on the
  trapezoid `(0,0) (4,0) (3,2) (1,2)` the longest and shortest edges are both the i-direction,
  so an edge ratio says 2.0 where the cell is 3:2. Checks 4 and 4b pin both halves.
- **Unmeasurable is NEGATIVE, never 0 and never infinity** — fewer than 3 corners, more than 4,
  or a zero midline. The reducer DROPS a non-positive entry rather than sorting it in, and
  `cells` counts what was MEASURED, not what was offered. On this metric 0.0 is not merely
  flattering but impossible: its floor is 1.0.
- **The two percentile rules are stated at the declaration**, because a percentile with no rule
  is a number nobody can reproduce: median = middle value, or the MEAN of the two middle ones on
  an even count; p95 = NEAREST RANK `ceil(0.95n)` from 1, no interpolation.
- Gated by `tests/cpp/test_cell_shape.cpp` (11 groups, 41 checks). **Its injections are HAND
  runs, dated 2026-09-17 in that file's docstring** — a C++ test cannot mutate the implementation
  it linked against. Permanent instead are two NEGATIVE CONTROLS computing an injection's own
  premise: check 2 derives its sqrt(2) from the split triangle's own edge lengths, and check 4
  computes the tapered cell's edge lengths and asserts WHICH edges the extremes are.
  Why: `docs/design_notes/mesher.md`, "CELL SHAPE: three numbers, one definition".

**THE HYBRID PATH REPORTS THE SHAPE OF THE CELLS IT EXPORTS, under its OWN name**
(`printHybridQuality` in `src/cli.cpp`; #130, parent #128). It has no structured layer to
measure — no `(i,j)` quad exists anywhere on it — so it measures what it exports, and what it
exports is triangles: the boundary layer's quad strip is already emitted as two triangles per
column in `src/BoundaryLayer.cpp`, so no four-cornered cell survives to the exporter on any case
that meshes a geometry.
- **The name is `tri_edge_ratio` and the line is `HYBMESH_HYBRID_QUALITY`**, neither of which a
  grep or the shared parser can confuse with the multi-block path's `quad_midline_ratio` on
  `HYBMESH_MB_QUALITY`. Same rule as there: every token is `key=<float>`, so the metric's name is
  in the KEY and never in a value of its own.
- **THE DISTINCTION IS ON BOTH BANNERS, not only the one that arrived second.** Each path's
  `Cell shape` row names the other's metric as NOT comparable; a warning on one report only
  reaches the reader who already had the other open.
- **ONLY THREE-CORNERED CELLS ARE OFFERED TO THE METRIC**, and that is a reachable case rather
  than a defensive habit: with no geometry, no seed and no domain file this path builds a
  CARTESIAN QUAD fallback (`Mesh::generateCartesianMesh`), and a quad handed to `cellShapeRatio`
  comes back as a MIDLINE ratio — a correct number under the wrong name. Such a cell is left out
  and COUNTED, with its own banner row, so the figure never describes a mesh by a fraction of
  itself.
- **WHICH CELLS ARE OFFERED IS DECIDED IN `hybmesh_pure`, NOT IN THE CLI** (`measureHybridCellShapes`
  in `include/HybridQuality.hpp` + `src/HybridQuality.cpp`; #141). It takes the mesh as IDS AND
  COORDINATES, never a `Mesh&` — `tests/cpp/test_hybrid_quality.cpp` linking `hybmesh_pure` alone
  is what proves it, the same build property `test_cell_shape.cpp` carries. `printHybridQuality`
  keeps the OUTPUT half only: the two banner rows, the machine line and the sidecar hand-off.
  Three rules live behind that seam and each can be wrong on its own — the corner-count FLOOR (an
  entry with fewer than 3 ids is not a cell, and a two-node one is a visualisation segment
  `addTaggedLoop` recorded), the corner-count CEILING (the bullet above), and an
  UNRESOLVED id (dropped as unmeasurable, never passed on SHORT).
- Gated by `tests/cpp/test_hybrid_quality.cpp` (13 groups, 45 checks). **Its injections are HAND
  runs, dated 2026-09-18 in that file's docstring**, and two of the eight are **INERT** and recorded
  as such: passing an unresolved cell on short cannot bite on THIS path, because only three-id
  cells reach the resolve loop and a prefix of at most two corners is refused by the metric
  anyway. The shape that rule exists to stop needs a four-corner cell with three resolving ids,
  which is the multi-block path's case (`test_mb_quality.cpp` check 9e). Do not write a check
  here for it: there is no fixture that reaches it until a longer cell is offered. The second
  (N, #143) is inert for a different measured reason: a half that SKIPS the unresolved cells it
  is handed reduces identically to one that passes the empty corner list on, because
  `reduceCellShapes` drops the one and never saw the other.
- **THREE SURFACES, ONE `ShapeStats`** — the `[ Mesh Statistics ]` banner row, the machine line
  and the sidecar's `mesh.quality` — handed out of the reporter rather than measured a second
  time at the export, so the three cannot disagree about one mesh. Unmeasurable is NEGATIVE and
  the banner says `not measured`; unlike the multi-block path, that state is REACHABLE through
  the binary by TWO different inputs — the quad fallback above, and a domain smaller than one
  far-field cell, which leaves 0 nodes and 0 elements and still reports.
- **`cells=` ON THAT LINE IS WHAT WAS OFFERED TO THE METRIC, never "what the exporters write".**
  The entries with at least 3 corners: `Mesh::exportStarCD` does skip the shorter ones, but
  `Mesh::exportVTK` writes EVERY element, so on the shipped demo it emits 15237 where this
  counts 15233. The gap to `tri_edge_ratio_cells` has three ways in — a cell this metric is not
  defined for, a degenerate one, and one whose ids did not resolve — which is why both counts
  are on the line and neither is inferred.
- Gated by `tests/test_hybrid_shape_surface.py`, which drives the shipped
  `config/Background_para.dat` + `examples/geometries/naca0012.dat` pair BY PATH (no retarget is
  needed: that config declares no path key and no `OUTPUT_FILENAME`, so `-out_name` is the whole
  of it, which is how `tools/scripts/golden_mesh.py` already drives the same pair). Its check 9
  is a computed negative control: the same config and geometry through `-geom_nobl` reports the
  same median and a p95 and max an order of magnitude smaller, so "the spread IS the boundary
  layer" is measured rather than claimed.
  Why: `docs/design_notes/mesher.md`, "CELL SHAPE: three numbers, one definition".

**THE HYBRID REPORT SEPARATES THE BOUNDARY LAYER'S CELLS FROM THE REST, BESIDE THE WHOLE-MESH
FIGURES AND NEVER INSTEAD OF THEM** (`measureHybridCellShapes` in `src/HybridQuality.cpp`,
`printHybridQuality` in `src/cli.cpp`; #143, parent #128). On the shipped NACA case the whole-mesh
p95 is 52.186 against a median of 1.158 because 3215 of the 15233 measured triangles (21.1%) are
BL cells — so that percentile describes the LAYER, and "what shape is the rest of my mesh" was
answerable from the median alone. Measured after the split: bulk median 1.112 / p95 1.412, layer
median 35.282 / p95 70.542.
- **ONE NAMING SHAPE FOR BOTH GENERATION PATHS: `<metric>_layer_*` and `<metric>_bulk_*`.** This
  path ships `tri_edge_ratio_layer_cells|median|p95|max` and `tri_edge_ratio_bulk_*`; the
  multi-block path's wall band takes `quad_midline_ratio_layer_*` when #144 splits it, and that
  ticket's change is where the two are made to match. **The word is `layer`, NOT `bl` and NOT
  `wall`**: it names the band of cells a mesher clusters against a surface, in either path's own
  vocabulary, and makes no claim about the BC on that surface — a boundary layer here grows from a
  geometry whatever its tag says, so `wall` would be the claim that is not true. **The shape is
  the KEYS', not the BANNER ROW's**: the row is labelled `boundary layer` here and will be the
  multi-block path's own word there, which is the rule `shapePhrase` already states one level up —
  what the two paths share is the FORMATTING of three numbers, while the metric name, the count's
  units and the sentence beside them stay each path's own.
- **EVERY TOKEN AND EVERY SIDECAR KEY THAT EXISTED BEFORE #143 KEEPS ITS SPELLING AND ITS
  MEANING.** The new tokens are APPENDED to `HYBMESH_HYBRID_QUALITY`; `cells`,
  `tri_edge_ratio_cells|median|p95|max` still carry the WHOLE mesh, and `mesh.quality` still holds
  `metric`, `cells`, `median`, `p95` and `max` at its top level with `layer` and `bulk` as two
  nested objects beside them. A reader that knows only #129's keys is unaffected.
- **THE SPLIT COMES FROM THE GENERATOR'S OWN RECORD, NEVER FROM A DISTANCE TO A WALL.**
  `Element::fromBoundaryLayer` (`include/Mesh.hpp`) is set where the cell is made, by
  `Mesh::addBoundaryLayerElement` — whose ONLY caller is `src/BoundaryLayer.cpp`, at four sites.
  A plain `bool`, not an `optional` like `blockId` beside it: absent is not a third state, every
  other producer's cells are bulk by construction, and it is exported to no mesh file. A geometric
  cut-off would have to be chosen, would then decide the figures, and could not tell a fan cell
  three layers out from the far-field triangle beside it.
- **THE TWO HALVES ARE TWO REDUCTIONS OF ONE COLLECTION.** A cell is offered, counted and resolved
  once, and its corner list goes to `measureCellShapes` in the whole-mesh set AND in its half, so
  `shape.cells == layer.cells + bulk.cells` holds by construction and no rule about measurability
  can hold in one set and not another. The per-cell ratio is computed twice rather than computed
  once and partitioned, because the alternative is this module reducing the metric itself and
  `measureCellShapes` losing its only production caller.
- **AN EMPTY HALF IS `not measured` WITH THREE NEGATIVE FIGURES, and on this path that is ORDINARY
  rather than an error**: a geometry meshed through `-geom_nobl` grows no layer, so its layer half
  is empty and its bulk half is the whole mesh. Same `shapePhrase` as the headline, so the words
  cannot drift — and **the parenthetical NAMES NO CAUSE**, for the headline row's reason: `cells 0`
  has two ways in, and on the Cartesian fallback 400 quads DO sit outside the boundary layer and
  merely cannot be measured, so `(no cells outside the boundary layer)` would be a false claim
  about the mesh. `tests/test_hybrid_shape_surface.py` check 10 reads the parenthetical, not only
  the state.
- **A PATH THAT DOES NOT SPLIT WRITES NEITHER SIDECAR KEY.** `MeshQuality::split`
  (`include/Provenance.hpp`) is a state of its own: false writes no `layer` and no `bulk`, rather
  than two objects full of negatives a reader would take for "we looked and found nothing". The
  hybrid path sets it unconditionally — it always splits, and both halves empty is a mesh nothing
  could be measured on.
- **NO THRESHOLD, NO COLOUR, NO GRADE on either new set**, the same rule #128 set for the figures
  they sit beside.
- Gated by `tests/cpp/test_hybrid_quality.cpp` checks 10-13 (the arithmetic) and
  `tests/test_hybrid_shape_surface.py` checks 13-16 (the three surfaces, through the binary).
  Check 13 carries **the one numeric bar in that file** and the ticket asks for it by name: the
  bulk p95 below 2 while the whole-mesh p95 is above 40, two-sided so that a split measuring
  nothing cannot pass it. It is a bar on the split DOING something, not a quality threshold.
  Why: `docs/design_notes/mesher.md`, "CELL SHAPE: three numbers, one definition".

**THE TWO CELL-SHAPE FIGURES ARE NEVER COMPARED, NEVER MERGED AND NEVER GIVEN ONE SHARED LABEL**
(`quad_midline_ratio` on `HYBMESH_MB_QUALITY`, `tri_edge_ratio` on `HYBMESH_HYBRID_QUALITY`; #142,
parent #128). Half of #128's story 5 was REFUSED to keep it that way. **Do not close the gap.**
- **No shared name, key, row, column or ratio.** Not one `cell_shape` key in the sidecar (the two
  `quality.metric` labels are two), not a `shape_metric=` token, not a "both paths" column in a
  panel, a README or a pipeline summary, and never one figure derived from the two.
- **THE BANNER SENTENCE IS THE ENFORCEMENT**, not this file: the `NOT comparable` clause each
  `Cell shape` row carries (`printMbQuality` and `printHybridQuality` in `src/cli.cpp` — the rule
  that BOTH rows carry it is stated above) is quoted VERBATIM in the design note and held against
  the source, mode number included, so rewording it in one home reddens a gate.
- Gated by `tests/test_comparability_refusal.py` (7 checks, 9 automated injections and a negative
  control — both banner sentences against `src/cli.cpp`, the record and its anchor, the pointer
  below, and the two metric names never crossing between the two emitters; no build tree needed)
  and by `tests/test_hybrid_shape_surface.py` check 5 through the real binary.
  Why: `docs/design_notes/mesher.md`, "THE TWO FIGURES ARE NOT COMPARABLE, BY CONSTRUCTION".

**`exportVTK` writes the block-id `CELL_DATA` field ONLY when EVERY element carries one**
(`Element::blockId`, an `std::optional<int>`, in `include/Mesh.hpp`; `src/Mesh.cpp`; #106).
Absent means absent: the hybrid path has no blocks, so a defaulted `0` would make every hybrid
`.vtk` claim its cells came from block 0, and a `-1` would be a field every reader has to know
to ignore. A VTK scalar array has one value per cell and no way to spell "this one has none",
which is what makes all-or-nothing the only way to express the optional in the format. **Stated
here AS WELL AS in `.claude/rules/mesher-multiblock.md`**, deliberately: that file's globs reach
`src/cli.cpp` but NOT `src/Mesh.cpp` or `include/Mesh.hpp`, so a session editing the exporter is
handed only this file. The rest of the rule is there — that the value is the INDEX into
`MbResult::blocks` and never the declared `id` string, that the array is named `block`, and that
no other exporter gains it. Gated by `tests/test_multiblock_block_field.py` from the outside, on
the shipped configs — and the PARTIALLY tagged refusal, which no run can produce, by
`tests/cpp/test_mesh_vtk_block_field.cpp`, which links `Mesh` and builds that state directly
(#113) -- the branch is unreachable from production, not untestable, so that file is where the
PARTIAL half of the rule is held.
Why: `docs/design_notes/mesher.md`, "THE BLOCK ID AS A VTK CELL FIELD".

## Named blind spots

Consolidated here rather than trailing each rule, so a coverage claim can be checked against
one list. #68 moved the first; #69 moved the rest; #89 took the multi-block fourteen to
`.claude/rules/mesher-multiblock.md`, so this list covers the core-C++ half only.

- **A SWAPPED PAIR in the banner is invisible** to `tests/cpp/test_bl_params_decl.cpp` check 6: it
  proves every parameter is reachable and that a number's own value appears, but the pairing of
  value to meaning IS the label prose.
- **`tests/test_cpp_linkable_seam.py` names two of its own** in its docstring.
- **`tests/test_comparability_refusal.py` holds the SENTENCES and the RECORD, never the practice.**
  Two shape figures put side by side by a GUI panel, a pipeline summary or a README table is the
  defect that rule exists to prevent and passes every check in it; so does swapping the two
  `quality.metric` labels, which it counts file-wide. That file's own docstring names the rest.
- **`golden_mesh.py` does not compare the `.bnd` `segm_no` column**, so a defect confined to a
  boundary edge's source-segment key is invisible to it — measured; the C++ unit test caught one in
  0.5 s while all 68 other tests and the 9-case golden set passed.
