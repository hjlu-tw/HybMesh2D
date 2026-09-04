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

**The multi-block path is ONE pure entry point, and the adapter deliberately has no seam**
(`include/MultiBlock.hpp` + `src/MultiBlock.cpp` in `hybmesh_pure`; adapter `buildMultiBlockMesh` in
`src/cli.cpp`; #50). `hybmesh::buildMultiBlock(topologyJson, geoms, params)` parses, resolves, fills
every block with structured quads, splits them, and returns nodes, blocks (with logical i/j), flat
cells, already-resolved boundary edges, warnings as data and an optional error. It never throws.
- **Parsing lives INSIDE the seam**, so schema errors, count resolution, node positions, the split
  and the resolved BCs are external behaviour of one function. `tests/cpp/test_multiblock.cpp` drives
  it with a topology STRING and no mesh, linking `hybmesh_pure` alone (`otool -L`) — reach for `Mesh`
  or gmsh and it stops linking.
- **The adapter gets no seam, because it has no decisions.** Each boundary edge returns as (node
  pair, BC name, source segment) and is recorded through `recordBoundaryEdge` with a **synthetic
  carrier `Node`**. Position-based classification is not used on this path at all — re-deriving by
  proximity is how a curved inlet exported partly as wall.
- **The split is ALTERNATING BY INDEX PARITY `(i + j)` and it is the default** — a fixed diagonal
  imprints its direction on a uniform region, and parity needs no seed. `MB_SPLIT_QUADS 0` exports
  quads for diagnosis and **says so** (the solver's incenter reconstruction is undefined on quads;
  the grid converter refuses a mixed mesh). The split happens in the MESHER, so VTK shows the mesh
  the solver integrates.
- **Four split rules, and the randomized one hashes the cell's OWN IDENTITY** (`MbSplitRule` in
  `include/MultiBlock.hpp`; `MB_SPLIT_RULE` 0=alternating, the default and what shipped first,
  1=fixed forward, 2=fixed backward, 3=randomized; `MB_SPLIT_SEED`; #54). Rule 3 is
  `hash(block ID string, i, j, seed)` — **never a sequential generator and never the block INDEX**.
  A stream makes a diagonal a function of traversal order and an index moves when a block is
  declared ahead of it, so either would reshuffle the whole mesh when one block is added, and the
  golden comparator (which compares exported connectivity, exactly what a diagonal decides) would
  lose its baseline on every topology edit. Pinned by `test_multiblock.cpp` check 26, whose fixture
  declares the extra block **FIRST** — appending one cannot tell an index hash from an id hash.
  - **Written out, not taken from `<random>`**: `std::mt19937` is specified bit for bit but every
    `<random>` DISTRIBUTION is implementation-defined, so a seed that reproduces a mesh only on the
    machine that made it is worse than no seed. Fixed-width unsigned arithmetic only.
  - **An unknown rule is REFUSED twice**: by `Config::validate()` with `EXIT_ERR_CONFIG` (fix the
    `.dat`) and by `buildMultiBlock` for any other caller — never clamped, as with `MESH_MODE`.
  - **A seed no rule reads is NAMED**, in a seam warning: it still reaches the provenance record,
    where it implies a reproducibility it had no part in.
  - **`MB_SPLIT_*`, never `SEED_*`** — that prefix is the refinement-seed namespace, an unrelated
    concept. The GUI's `mb_split_rule` / `mb_split_seed` sit beside its `seed_size` / `seed_radius`
    for the same reason.
  - **The enum lives in its own header** (`include/MbSplitRule.hpp`), not in `MultiBlock.hpp`:
    `Config.hpp` must refuse an unknown rule and is itself included by `Mesh.hpp` and
    `BoundaryLayer.hpp`, so reaching the enum through the seam header would drag `MbResult` and
    `GeomUtils.hpp` into all of them and invert the coupling that header states as a rule.
    `MeshMode.hpp` is the precedent. One `mbSplitRuleList()` builds BOTH refusal messages, and one
    `mbSplitRuleReadsSeed()` answers the seed question at all four sites.
  - Gated by `tests/cpp/test_multiblock.cpp` 24-29 (9 hand injections, dated in that file),
    `tests/cpp/test_mesh_mode.cpp` 5b, `tests/test_multiblock_surface.py` check 6 and the
    `mb_random` golden case — the only one that compares across two BUILDS.
- **Logical i/j is retained rather than flattened** (only the diagonal rule reads it);
  `MbCell::block` is carried for the same reason.
- **Every declared id is UNIQUE — corner, edge and block.** The block half arrived with #54 and is
  not symmetry: the randomized rule hashes the block's declared id, so two blocks sharing one are
  cut identically, which is the correlated pattern that rule exists to break. The edge half had been
  unguarded since #50 and was found by a mis-aimed injection (the three loops are textually
  identical); both are check 29.
- **Unknown JSON keys are REFUSED, not skipped** — a typo'd `"spacng"` silently ignored is a wrong
  node distribution with no symptom, and strict now is relaxable later. So is **a declaration that
  reaches nothing**: an edge in no block, a corner on no edge.
- **What v0 does not do is refused BY NAME, never approximated**, each refusal naming the work it
  waits for: a `blocks[].orientation`. (`on_geometry` and `binding` were on this list and are
  implemented by #52; the `interface`/`cut` kinds and a second block by #53.)
- **A block's orientation is the corner order of its own four edges**, `[south, east, north, west]`,
  south/north running i-min→i-max and west/east j-min→j-max. A **clockwise** corner ring is refused
  under the TOPOLOGY code, never silently re-wound. SUPERSEDED IN PART by #53: a DIRECTION
  deviation is no longer refused, only a set of four edges that does not CLOSE a ring.
  Why: `docs/design_notes/mesher.md`, "A block's orientation is the corner order".
- **The boundary edges are ONE counter-clockwise walk**, matching `addTaggedLoop` /
  `buildDomainBoundary`. Measured: the direction does **not** reach the `.bnd` (`exportStarCD` takes
  face node order from the owning cell), so this is consistency for a reader. The C++ test pins the
  CHAINING, since a per-side emitter with one direction wrong still emits the right SET of edges.
- The spacing schema accepts `uniform` / `geometric` / `tanh`; **`tanh` is the DEFAULT** and #55
  resolves wall spacing from `BL_INITIAL_THICKNESS`. The decision layer gains
  `tools/PreProcessor/include` **PRIVATE** on its include path, so a test linking `hybmesh_pure`
  does not inherit it.
- **SURVIVING is not the same as READ.** #49 declares four BL parameters as surviving into this
  mode. #55 made **two** of them real inputs (`HYBMESH_MULTIBLOCK_BL_READ`:
  `BL_INITIAL_THICKNESS`, `BL_GROWTH_RATE`), which must therefore be SILENT.
  `hybmesh::blSurvivorsUnread` names the other two in their **own** sentence
  (`does not read 'X' yet`), never the inert one (`never reads 'X'`) — an inert value should be
  deleted and one of these should be kept, so the two lists must stay **disjoint** (pinned in
  `test_mesh_mode.cpp` 6b, `test_mesh_mode_surface.py` 4). `BL_LAYERS` stays unread because a count
  class with no seed is refused BY NAME rather than defaulted, `BL_USE_ANALYTIC_GEOM` because a
  bound edge follows the resampled polyline. A **second** macro rather than a shorter survivor list:
  the GUI shows a row when a parameter SURVIVES. Delete both when the list empties.
- Known asymmetry: `inertParamsSet` answers only for multi-block, so `MESH_TOPOLOGY_FILE`,
  `MB_SPLIT_QUADS`, `MB_SPLIT_RULE`, `MB_SPLIT_SEED` and `MB_SMOOTH_ITERS` set under `MESH_MODE 0`
  warn about nothing (the GUI hides all five rows, so only a hand-written `.dat` reaches it). #54
  widened this from two keys to four and #81 to five, without widening the machinery; an unknown
  `MB_SPLIT_RULE` and a negative `MB_SMOOTH_ITERS` are still refused there, because `validate()` is
  mode-blind.
- **A geometry that will not load is a WARNING here, not a refusal** — the opposite of the hybrid
  path's answer, and right because nothing in a topology had to refer to one.
- **`Mesh::addTaggedEdge(v1, v2, bc, segKey)`** replaced the `addEdge` + two writes to
  `edges.back()` idiom at all four call sites: a BC and its source segment are one fact.
- Gated by `tests/cpp/test_multiblock.cpp`, `tests/test_multiblock_surface.py` and three golden
  cases (`mb_square`, `mb_square_quads`, `mb_graded`); `golden_mesh.py` IMPORTS the topology writer
  from the surface test rather than copying it. (#52 added `mb_bound` / `mb_cavity`, #53 `mb_hgrid`,
  #55 `mb_ogrid`.)

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
  checks hand `measureMbQuality` a mesh nobody parsed.
- **Inverted is counted over the EXPORTED cells, and the test is PER CORNER, not the signed area**:
  a bow-tie quad can self-intersect with a POSITIVE shoelace area (`(0,0) (3,0) (0,1) (2,1)` is +0.5
  and crosses itself). For a triangle the per-corner rule reduces to the signed area, so it is one
  rule for both cell kinds.
- **Non-orthogonality is measured on the STRUCTURED grid cells** — each corner angle's deviation
  from 90° — **and NOT on the split triangles.** From corner positions, so a strongly stretched but
  axis-aligned block measures *exactly* zero (no edge-length proxy can), it is the quantity elliptic
  smoothing moves, and it is independent of `MB_SPLIT_QUADS`. An ANGLE with a closed form, not a
  badness score.
- **A folded mesh is EXPORTED and exits 9; an invalid declaration exports nothing and exits 8**,
  both through the same `failExit` mechanism. `blSuccess` stays TRUE so the VTK keeps its ordinary
  name — `_er` marks a PARTIAL mesh and this one is complete.
- **The wall request is published from the SEAM, never re-derived downstream** (`MbWallSpec` on
  `MbResult`): only `buildMultiBlock` knows the spacing laws. The height is a distance ALONG the
  grid line, not perpendicular to the wall — they differ by cos(non-orthogonality), which is why the
  two figures are always reported together.
- **"ASKED FOR" IS NOT AN INDEPENDENT TARGET YET; do not over-read the figure.** The request is
  DERIVED from the same law the fill reproduces and the blend is exact on the boundary, so **a
  rectangle's 0.00% is a tautology, not evidence**; what it measures is interior drift from what the
  two ends declare (trapezoid 7.38%, folded dart 25.41%). When the independent target arrives only
  the PUBLISHER changes. **SUPERSEDED by #55, exactly as predicted**: a perpendicular edge that
  DECLARES a wall height publishes that number, so the figure now compares the mesh against the
  document. `MbQuality.*` and every reader are untouched. An edge that declares nothing still
  publishes the produced interval, so the sentence above still holds for such a topology — which is
  also the negative control in `test_multiblock.cpp` 34.
  Why: `docs/design_notes/mesher.md`, "`MbWallSpec` NOW PUBLISHES THE DECLARATION".
- **"We did not measure" must not read as "it came out perfect", for ALL THREE figures.**
  `maxNonOrthoDeg`, `meanNonOrthoDeg` and every `worstRelError` (per wall AND headline) are NEGATIVE
  when unmeasurable, never 0.0, and the banner prints `not measured`. The rule holds at the ROW
  level too (check 6b) — `measureMbQuality` is a public pure function accepting any `MbResult`, so
  its header's guarantee must hold for every input.
- **The detector is proven to bite by a topology that folds and is ACCEPTED**: the dart
  `(0,0) (1,0) (0.1,0.1) (0,1)` winds counter-clockwise (+0.1), so the ring refusal does not fire and
  the fill folds anyway. The gate checks no topology refusal prints on that run.
- **All four sides are reported**, because v0 cannot say which boundary is a viscous wall.
  SUPERSEDED by #53: the gate is the KIND, so an `interface`/`cut` side is not reported and the list
  is exactly the outer walls.
  Why: `docs/design_notes/mesher.md`, "All four sides are reported, because v0".
- **The `[south, east, north, west]` convention is DATA, in one place** (`mbSideAxis`). A dedup of
  `MbWallSpec`/`MbWallHeight` was considered and DECLINED: they face opposite directions and the
  shared part cannot be written HALF.
- Gated by `tests/cpp/test_mb_quality.cpp` (9 groups, 53 checks) and
  `tests/test_multiblock_quality_surface.py`. **Its injections are HAND runs, dated in the C++
  test's docstring** — a C++ test cannot mutate the implementation it linked against, and that
  distinction must not be blurred. What IS permanent is two **negative controls** computing an
  injection's own premise (check 6 the bow-tie's +0.5 area, check 2 its ~17x stretch).

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
  `kind` gate now bites — an interior side is not a wall — so the list is the outer walls.
  Why: `docs/design_notes/mesher.md`, "still reports all four sides, and the #51 note".
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
- **A block's frame comes from its SOUTH edge; this REVERSES #50's rule.** The other three sides may
  be declared either way and are traversed as the ring requires — a shared edge has ONE direction and
  two blocks whose frames need not agree. Nothing is inferred: four edges that do not CLOSE a ring
  are refused by name, a ring closing onto THREE corners is refused too (reachable: two distinct
  edges over one corner pair), and the clockwise-ring refusal is unchanged. C++ check 9 is the
  **inverted** version of the one that pinned the old refusal.
  Why: `docs/design_notes/mesher.md`, "The clockwise-ring refusal is unchanged".
- **"The four sides meet at four shared corner NODES" is checked, before the writes overwrite one
  with the other.** It looks tautological after the ring match and is not: it caught the
  dropped-reversal injection in both gates.
- Gated by `tests/cpp/test_multiblock.cpp` 17-23, `tests/test_multiblock_weld_surface.py` (which
  measures CONFORMITY on the exported files — interior edges shared by exactly two cells, the
  boundary set equal to the `.bnd`, one connected component) and the `mb_hgrid` golden case on the
  shipped `examples/topology/hgrid_blocks.json`.
- **THE SOLVER ACCEPTANCE RUN LANDED with #55**, and the claim that blocked it — "this checkout has
  no solver tree" — was FALSE, not merely stale. The four-block O-grid went through `getPGrid`
  (exit 0) and `unicones` (exit 0, 100 iterations) on 2026-09-04; quoted in
  `test_multiblock_ogrid_surface.py`.
  Why: `docs/design_notes/mesher.md`, "SUPERSEDED 2026-09-04 by #55, and the PREMISE was wrong".
- **What welding cannot express, refused rather than approximated**: nothing welds along a BOUND
  edge, nothing exceeds four blocks, and a block welded to ITSELF is inexpressible — right for a
  transfinite fill, but an O-grid seam cannot be one edge. (#55's O-grid is four blocks in a RING
  for that reason; its wrap-around class is `test_multiblock.cpp` 33.)

**A circular O-GRID: curved arcs, a ring that CLOSES, and a wall spacing SOLVED for** (still the
one pure entry point; the law is `tools/PreProcessor/include/Spacing.hpp`; #55). **Full rationale,
the measurements that forced the blending change, the acceptance run and the blind spots:
`docs/design_notes/mesher.md`.**
- **`tanh` is the DEFAULT distribution law, and the reason is structural**: a count can be decided
  FOR an edge by propagation, so the law must absorb one it did not choose. Tanh at delta 0 is the
  SAME EXPRESSION as uniform, which is what let the default change at all — pinned as BIT equality
  (`test_multiblock.cpp` 30), not as "roughly uniform".
- **Wall spacing is a LENGTH, solved for by bisection, never approximated.** `wall_ends`
  (`start`/`end`/`both`) takes the run's `BL_INITIAL_THICKNESS`; `ds_start`/`ds_end` give a number
  and beat it; `geometric` with no `growth` takes `BL_GROWTH_RATE`. **The existing BL names, never
  aliases** — the physical quantity is identical. `Spacing::generateTanhStart` /
  `solveTanhStartDelta` are the ONE-SIDED law, new because the symmetric one spends the far-field
  end's points at the wall spacing. Accuracy is 1e-12 relative on a 1e-4 first cell and the bound is
  DERIVED (eps of the EDGE length ÷ the cell's relative size), not picked.
- **Refused BY NAME, never half-honoured**: two DIFFERENT heights at the two ends (equal ones are
  accepted, so the refusal is about the difference); a wall spacing on `uniform`/`geometric`; a raw
  `delta` beside a spacing; a non-positive height; an unknown `wall_ends`; a `growth` on a
  non-geometric edge; a wall end with no height anywhere, naming `BL_INITIAL_THICKNESS`. A request
  the edge could not honour (coarser than its count allows) is a WARNING measured on the produced
  nodes, not re-derived from the law — and **in ARC LENGTH, never the chord**: a bound edge follows
  a polyline, so a first interval spanning several facets has a shorter chord, and comparing that
  fired the warning on a law that had honoured the request exactly (a 0.05 request reported as
  0.049978) while blaming the node count for the geometry's own faceting. Found by BOTH review axes
  independently; gated with a negative control by `test_multiblock.cpp` 36.
- **`coons` blends by the boundary's own NORMALIZED ARC LENGTH, not by the logical index**, and this
  is load bearing rather than a refinement: the index blend put an O-grid's first interior ring
  **6927% above** the requested wall height (806% even at twelve sectors), the arc-length blend
  reproduces a polar annulus EXACTLY. Facing curves are averaged; a degenerate side falls back to the
  index; both ends pinned to 0 and 1. **Behaviour-preserving on the existing set, measured against a
  HEAD binary**: worst node movement 6.7e-16. `golden_mesh.py` still showed 3 DIFFs — the
  node-SET-membership artefact — so the baseline was re-captured, 17/17 SAME.
- **The O-grid is FOUR BLOCKS IN A RING** (`examples/topology/ogrid_circle.json`,
  `config/multiblock_ogrid.dat`): i runs outward, j anticlockwise, so the four radials are ONE
  equivalence class that WRAPS — one declared count, three propagated, the last block welded back to
  the first by node identity. Measured on the shipped files: 0 inverted, non-orthogonality max
  2.25°, wall first cell **0.08%** off. That residue is the stored polyline's FACETING, not the law
  — the same case on 10× finer circles measures 0.0007%, and the figure is identical at
  `BL_INITIAL_THICKNESS` 1e-3, 1e-5 and 1e-7. Re-seeding the ring (25 / 49 / 97) does not move it.
- **The shipped circles are checked against their ONE generator** (`write_circle` in the surface
  gate), never trusted: a hand-edited `.dat` whose `.meta` still describes the old point set is a
  mesh with corners on the wrong segments and no error at all.
- Gated by `tests/cpp/test_multiblock.cpp` 30-36, `tests/test_multiblock_ogrid_surface.py` (8 groups
  on the SHIPPED files, reusing #53's conformity measure) and the `mb_ogrid` golden case. The
  dated solver acceptance run is in that file's docstring.

**A four-block C-GRID around a NACA 0012, and the gate that bit was the SOLVER** (still the one
pure entry point; `examples/topology/cgrid_naca0012.json` + `config/multiblock_cgrid.dat`; #57).
**NOT ONE LINE OF `src/` OR `include/` CHANGED for this ticket** — the C-grid was already
expressible by #50-#55, and what #57 adds is a declaration, two geometries, three C++ checks and
one acceptance run. **Full rationale, the diagnosis, what was tried and rejected, and the
acceptance run: `docs/design_notes/mesher.md`.**
- **The wake is ONE edge of kind `cut`, and it is the WEST of BOTH wake blocks.** Every earlier
  shared edge was one block's east and another's west; here the two frames are mirror images and
  the edge is traversed in OPPOSITE senses from the same side index. No face of it reaches the
  `.bnd` — that is the whole difference between a cut and a wall, and `test_multiblock.cpp` 37 is
  the second thing that looks (the kind gate is the first).
- **The trailing edge is ONE declared corner, on FIVE edges, where FOUR blocks meet.** One node, by
  declaration. In `test_multiblock.cpp` 38's own fixture 60 node slots resolve to 47 nodes (the
  shipped grid is 5920 nodes / 11520 cells); three of the thirteen identifications are the
  trailing edge's own, which is what it takes to bring four occurrences down to one. The C's five radials are one equivalence class with ONE seed
  (check 39) — the O-grid's ring closes on itself, this chain does not, and its open ends are the
  two halves the cut splits the outlet plane into.
- **The gate that bit was GATE 2, not gate 1, and the fix was in the DOCUMENT.** Zero inverted
  cells came on the first run of the shipped declaration, so **none of #57's three escalation steps
  (Laplacian smoothing, shipping the O-grid instead, pulling elliptic smoothing forward) was
  reached**. The solver then went to NaN in 40 iterations.
- **The far field's two nose sides cluster at their TRAILING-EDGE end to the AIRFOIL's own
  `ds_start`.** Over the chordwise surface the body's normals are nearly vertical and that boundary
  is horizontal, so the outer point opposite a body point sits at very nearly the same x and the
  outer distribution must TRACK the body's. Left uniform: max non-orthogonality 59.52°, mean
  16.0°, wall first cell 3.46%, and the blow-up was on the surface just aft of the **LEADING** edge
  — #57 predicted the trailing edge. With it: **32.04° / 4.56° / 0.44%**, and the solver runs at
  the same `cfl 0.6` the O-grid used. **It is DERIVED, not tuned**: change the airfoil edges'
  spacing and this must follow.
- **Lowering `cfl` to 0.3 also makes the BAD mesh run**, so "the solver runs" is quotable without
  improving the grid at all — which is why the recorded run states its CFL. And the wake's 3144:1
  worst edge ratio is **measured NOT to be the cause**: cutting it to 211 left the solver diverging
  at the same iteration.
- **A second airfoil file, not a sidecar beside `examples/geometries/naca0012.dat`.** That one is
  the hybrid path's geometry and has a golden baseline; a `.meta` beside it would change what that
  path reads. `naca0012_cgrid.dat` (two segments, split at the leading edge) and
  `cgrid_farfield.dat` (six, one per outer block side) are both checked against their ONE generator
  in the surface gate, never trusted.
- Gated by `tests/cpp/test_multiblock.cpp` 37-39 (4 hand injections, dated in that file),
  `tests/test_multiblock_cgrid_surface.py` (9 groups on the SHIPPED files, reusing #53's conformity
  measure) and the `mb_cgrid` golden case. The dated solver acceptance run is in that file's
  docstring.

**SMOOTHING is a STAGE inside the seam, and its kernel is WINSLOW** (`MB_SMOOTH_ITERS`, default
0; `src/MultiBlock.cpp` between the fill and the split; #81 built the stage with a Laplacian,
#82 replaced the kernel and DELETED that one). An elliptic solve over each block's interior
nodes, iterated to convergence under a cap; at the default nothing runs and all eighteen
pre-existing golden cases are unchanged (measured twice: 18/18 SAME at 0.000e+00 for #81, and
again for #82, where the nineteenth — `mb_cgrid_smooth` — moved 1.999 units and was recaptured
on purpose). **Full rationale, the before/after tables and the reversals:
`docs/design_notes/mesher.md`.**
- **WHICH NODES MOVE, stated here rather than read off the loop: exactly the nodes strictly
  interior to a block** (`0 < i < ni-1`, `0 < j < nj-1`). **Every node on ANY block boundary is
  FROZEN — outer walls, bound edges, interfaces and cuts alike** — because such a node is written
  by the EDGE, and an edge is SHARED: moving it would move it in two blocks at once, and a node on
  a bound edge would leave the geometry it was attached to by arc length. So one block's interior
  never neighbours another's, which is why the sweep needs no ordering rule between blocks.
  Smoothing ACROSS a shared edge is #80's ticket 4 (#84), **and that freeze is now a measured
  cost, not just a scope line** — see the O-grid entry below.
- **Node identity is untouched**: the sweep writes coordinates and allocates nothing, so a welded
  node stays ONE node. No comparison, therefore no tolerance — `MB_SMOOTH_TOL` is a STOPPING rule
  on how far a node moved, never a rule about two nodes being the same node.
- **JACOBI, not Gauss-Seidel** — every sweep reads what the previous one left, so the answer is not
  a function of a traversal nobody declared. Same objection the randomized split rule raises
  against a sequential stream. The metric coefficients are LAGGED with it, which is what makes each
  sweep linear and the solve a fixed-point iteration.
- **Between the FILL and the SPLIT.** Both readers below are id-only today, so the sweeps would
  give the same answer after them — measured: injection Y (the block moved past the split) is
  INERT. The ordering is what keeps that from having to be re-checked every time a reader is added.
- **`MB_SMOOTH_ITERS`, never `BL_SMOOTHING_ITERS`-with-a-prefix and never `SEED_*`.** The BL key is
  the OTHER path's collision remedy (it relaxes nodes around a frozen boundary-layer front and
  returns immediately when nothing is frozen); these two share a verb and nothing else.
- **A NEGATIVE count is refused BY NAME through both doors** — `Config::validate()` with
  `EXIT_ERR_CONFIG` and `buildMultiBlock` for any other caller — never clamped. The parameter is a
  signed `int` precisely so the refusal is writable: widening -1 to an unsigned count is four
  billion sweeps, a hang rather than a mesh. **A FRACTIONAL value TRUNCATES and is not refused**
  (`MB_SMOOTH_ITERS 1.9` runs one sweep): the `.dat` reader takes every int key through a `double`,
  and diverging for this one key would put back a per-row parse rule of exactly the kind that let
  the two parsers disagree. Recorded as a limit, not left silent.
- **THE NUMBER IS A CAP, AND THE SOLVE HAS THREE ENDINGS.** It stops the sweep its residual — the
  largest node move, over the STARTING mesh's bounding-box diagonal — falls under
  `MB_SMOOTH_TOL` (1e-8, relative so a topology in mm and the same one in m take the same number
  of sweeps; not a config key, because the knob a user has is the cap). A solve still moving at
  the cap comes back `smoothConverged == false` with a warning naming the key to raise. **And it
  can DIVERGE**: measured on the shipped C-grid, the residual falls to 2.7e-08 by sweep 3724 and
  then GROWS about 1.0018 per sweep, reaching 1.3e-03 by sweep 10000 with 88 folded cells — the
  lagged-coefficient point iteration is only conditionally stable and a grid that equidistributed
  is where the condition fails. So the solve stops at `MB_SMOOTH_DIVERGE_FACTOR` (10x) its best
  residual and **returns the BEST ITERATE, not the last**, with `smoothDiverged` and that
  iterate's own sweep number published. **Never hand back a truncated solve as though it had
  finished** — that is the whole of #82's third criterion, and the banner, the warning and the
  `HYBMESH_MB_SMOOTH` line all say which ending it was.
- **A CAP IS TWO SITUATIONS, AND THE ADVICE MUST TELL THEM APART.** `smoothBestSweep` /
  `smoothBestResidual` publish the smallest residual the solve reached and when — recorded
  BEFORE either stop is tested, so a converged solve's best is the sweep it returned. A capped
  run whose residual is still FALLING has more to give; one already ABOVE its best has TURNED,
  and telling that user to raise the cap points them at a worse mesh. Both wear
  `converged == false && diverged == false`, so the flags cannot distinguish them. **And in
  neither case is "raise it until it converges" the advice**: a converged plain Winslow solve is
  each block's harmonic map and holds no declared first-cell height at all (3133% off on the
  shipped C-grid, 1382% on the O-grid), so at this kernel "not converged" is a statement of fact
  and not a to-do. A small cap is the useful setting until #83 lands. **The mesh returned at a
  cap is still the LAST iterate, never the best** — N sweeps has to mean N sweeps outside the
  diverged path — so the difference is SAID, not silently repaired.
- **THE REPORT IS BEFORE AND AFTER.** `MbResult::preSmoothNodes` publishes the mesh as it stood
  before the first sweep, so the two reports are the same cells and blocks over two coordinate
  sets and their difference is the smoother alone. On the shipped C-grid, ONE sweep: max
  non-orthogonality **32.04° -> 31.44°** (BETTER — the metric #80 exists for), mean **4.56° ->
  4.78°**, wall first cell **0.44% -> 11.65%**. At five sweeps max reaches **29.84°**.
- **EACH MACHINE-READABLE LINE KEEPS ONE MEANING, and the prefix is matched WITH its
  trailing space.** `HYBMESH_MB_QUALITY` always describes the mesh AS EXPORTED; the before half
  is `HYBMESH_MB_QUALITY_BEFORE` and appears only when a sweep ran, so an unsmoothed run's
  QUALITY REPORT is byte for byte what it was — not its whole output, which gains one
  unconditional `Smoothing Sweeps` provenance row on purpose. The trailing space is what keeps
  the suffixed line from being read as the real one, and it is matched in the ONE parser
  (`test_multiblock_quality_surface.qlines`) every gate imports rather than in four near-copies.
  `HYBMESH_MB_SMOOTH` is the SECOND such line (#82) and describes the SOLVE, not the mesh: it
  appears only when a sweep ran, carries
  `sweeps cap converged diverged residual best_sweep best_residual tol`, and wears
  no suffix because it has no before/after half — a run either solved or did not. Its parser is
  `test_multiblock_smooth_surface.smooth_line`, and it lives beside that gate rather than beside
  `qlines` because a run can report a mesh without reporting a solve.
- **THE WALL FIRST CELL IS STILL WORSE, and that is #83's, not a defect to paper over.** Plain
  Winslow relaxes toward each block's harmonic map, which has no memory of the declared first-cell
  height; the control functions that hold it are #80's ticket 3. Record the miss as a number.
- **THE LAPLACIAN #81 SHIPPED IS DELETED, not kept behind a selector.** Nothing read it, it loses
  on every column of both shipped cases at every cap either ticket measured (C-grid at 1 sweep:
  max 89.40° vs 31.44°, wall 36.61% vs 11.65%; at 5 sweeps it folds 4 cells where Winslow folds
  0), and a kernel-selection enum over one surviving kernel is the abstraction this repo's
  no-inert-alternatives rule exists to prevent. It survives ONLY inside
  `tests/cpp/test_multiblock.cpp` as `laplacianByHand`, so checks that claim the two kernels differ
  have both sides written down.
- **#80's O-GRID NEGATIVE CONTROL IS NOT MET BY THIS TICKET, and the reason is the freeze.** A case
  already at 2.250° max comes out at **3.312°** after one sweep. The run's own wall table localises
  it without a second instrument: the first cell is the declared height EXACTLY where a frozen
  radial interface pins it and 9.13% off in the middle of each block, so what the smoother adds is
  a KINK AT THE INTERFACE. Unfreezing those is #84. Recorded as unmet and owned, not asserted away.
- **A fold from smoothing is an ORDINARY inverted mesh**: counted after the sweeps, exported, exit
  9. No new code. **But it is no longer reachable on the shipped files** — the Winslow kernel folds
  nothing the Laplacian folded (4 at 5 sweeps, 26 at 20) and REPAIRS folds the algebraic fill makes
  (13 of 13 on a re-entrant block). Reaching one now needs a wall first cell of 0.0005 on the
  C-grid fixture.
- Gated by `tests/cpp/test_multiblock.cpp` 40-50 (7 injections from #81 plus 13 more from #82, all
  dated in that file — twelve bit, and a thirteenth is recorded INERT because the two off-diagonals
  of the cross stencil enter with the same sign, which no gate can catch and nothing should try
  to), 
  `tests/test_multiblock_smooth_surface.py` (9 groups on the SHIPPED C-grid AND O-grid) and the
  `mb_cgrid_smooth` golden case. The divergence path and the rollback are gated by that surface
  gate ALONE: 26 synthetic fixtures were tried in the C++ test and every one converged.

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
- **`Config.hpp`**: single-header; parses `.dat` files into ~50 typed parameters.
- **`GeomUtils.hpp`**: `Vector2D`/`Point2D`, segment intersection, normals, dot/cross.

## Named blind spots

Consolidated here rather than trailing each rule, so a coverage claim can be checked against
one list. #68 moved the first; #69 moved the rest.

- **A SWAPPED PAIR in the banner is invisible** to `tests/cpp/test_bl_params_decl.cpp` check 6: it
  proves every parameter is reachable and that a number's own value appears, but the pairing of
  value to meaning IS the label prose.
- **Non-orthogonality says nothing about the shape of the SPLIT TRIANGLES** — it is measured on the
  structured grid cells only.
- **Nothing runs the solver or the grid converter on the folded mesh** (`MbQuality`'s sharpest).
- **Nothing projects onto an ANALYTIC curve.** A bound edge follows the stored POLYLINE, so
  "follows the circle" is measured against that polyline's vertices and #55's 0.08% wall-height
  residue is its faceting. `BL_USE_ANALYTIC_GEOM` is a declared survivor nothing reads.
- **A curved INTERFACE is still undeclarable** (a `binding` is wall-only), so #55's O-grid is a
  single ring rather than a boundary-layer ring inside a far-field one, and no two-sided stretching
  function with DIFFERENT heights at each end exists.
- **The arc-length blending's magnitude is measured OUT OF TREE.** No gate re-measures the 6927%
  the logical-index blend cost — only its consequence, through `test_multiblock.cpp` 33/34 and the
  surface gate's quality line.
- **The end-to-end re-resampling check uses a straight-sided geometry**, where an arc-length
  position is EXACT under resampling. On a *curved* segment an attached corner moves by a chord
  sagitta — a limit of the geometry, not of the binding. The curve-following half is pinned in
  the C++ test (`tests/cpp/test_multiblock.cpp`).
- **`tests/test_cpp_linkable_seam.py` names two of its own** in its docstring.
- **Nothing measures the QUALITY of the randomized rule's bit stream.** Checks 24-26 assert that
  both diagonals appear, that the pattern is not parity's, and that it is a function of the four
  declared inputs — a hash with a visible period would pass all of them. Deliberate: a distribution
  test over 12 cells asserts noise, and the property that matters (no direction imprinted on a
  uniform region) is what `MbQuality` measures on a real case.
- **The C-grid's 0.005 far-field clustering is UNENFORCED.** It is derived from the airfoil
  edges' own `ds_start`, but they are two numbers in one document that happen to agree; only the
  acceptance run would notice them diverging.
- **GATE 2 DOES NOT EXERCISE THE `.bnd` NAME -> SOLVER FLAG MAPPING.** `getPGrid` does not know
  `farfield` and defaults those faces to a no-slip wall, so both recorded runs wrote the flag into
  a `.bc.def` BY HAND — what the GUI's `services/bnd_io._NAME_TO_FLAG` does automatically. Nothing
  from either run is committed, so each is a quotation and not a reproduction.
- **GATE 2 IS ONE OPERATING POINT, AND NOTHING RE-RUNS IT.** #57's acceptance run is M 0.2, Re 200,
  zero incidence, 100 iterations, `cfl 0.6`, every non-wall patch flag 1. "The solver runs" is all
  it claims — not convergence, not accuracy, and no pressure distribution is compared with
  anything. CI has no solver binary, so both recorded runs are dated quotations.
- **Non-orthogonality is a BASELINE here, never a gate.** #57 made that explicit, and the C-grid's
  32.04° max is still the first cell off the wall just aft of the leading edge — the quantity the
  elliptic-smoothing increment exists to move.
- **NOTHING CAN SEE THE SMOOTHING STAGE'S POSITION.** Injection Y — the whole sweep block moved
  past the split — is INERT, because every reader downstream of it is id-only today. The
  fill-then-smooth-then-split ordering is a design rule held by a comment, not by a gate.
- **The smoothed mesh is never given to the solver or the grid converter.** At this kernel that
  would be a strange thing to want — 36.61% off the requested wall height is not a boundary layer
  worth integrating — but it means "smoothing produces a mesh a solver accepts" is unproven, and
  belongs to the #80 ticket that makes the numbers better.
- **The before/after tables are dated quotations**, not re-measured. The gates assert a DIRECTION
  with a floor, so a kernel that quietly stopped moving anything is caught while one that moves
  things differently is free to.
- **`golden_mesh.py` does not compare the `.bnd` `segm_no` column**, so a defect confined to a
  boundary edge's source-segment key is invisible to it — measured; the C++ unit test caught one in
  0.5 s while all 68 other tests and the 9-case golden set passed.
