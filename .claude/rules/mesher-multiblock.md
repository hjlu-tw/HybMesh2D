---
paths:
  - include/MultiBlock.hpp
  - include/Mb*.hpp
  - src/MultiBlock.cpp
  - src/Mb*.cpp
  - src/cli.cpp
  - include/Config.hpp
  - config/multiblock_*.dat
  - tests/cpp/test_multiblock*.cpp
  - tests/cpp/test_mb_*.cpp
---

# Mesher rules — the `MESH_MODE 1` multi-block path

Loaded on demand when a multi-block header, source, `.dat` config or C++ test is read. The
globs are PATTERNS rather than an enumeration, deliberately: an allow-list exempts whatever
nobody enrolled, so a future `src/Mb*.cpp` or `include/Mb*.hpp` starts life covered instead of
silently ruleless. **The coverage that buys is exactly those prefixes, not "any multi-block
module"** — 4 of the 9 entries are literal filenames, so a `src/MultiBlockSmoother.cpp` would
arrive with no rules. Name a new module `Mb*` or add the glob.
Two of them are NOT multi-block modules and carry this path's rules from outside it —
`src/cli.cpp`, which prints the quality banner and the two machine-readable lines, and
`include/Config.hpp`, one of the two doors a negative sweep count is refused by name at.
Rules only: the rationale — the measurements, the dated acceptance runs, the injections, the
reversals and the named blind spots — is `docs/design_notes/mesher.md`, the SAME note
`.claude/rules/mesher.md` points at. Read that note before overruling a rule here, and when a
rule changes update BOTH.

**`MESH_MODE` itself is the SELECTOR and its rule stays in `.claude/rules/mesher.md`**, with
the exit codes this path exits by and the single `.dat` key table; this file cross-references
them rather than carrying a second copy. A session editing a multi-block file loads BOTH rule
files, and that overlap is the point of the split (#89): a session under
`src/BoundaryLayer.cpp` loads none of it.

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
  declared ahead of it, so either reshuffles the whole mesh when one block is added, and the golden
  comparator (which compares exported connectivity, exactly what a diagonal decides) loses its
  baseline on every topology edit. Pinned by `test_multiblock.cpp` check 26, whose fixture declares
  the extra block **FIRST** — appending one cannot tell an index hash from an id hash.
  - **Written out, not taken from `<random>`**: `std::mt19937` is specified bit for bit but every
    `<random>` DISTRIBUTION is implementation-defined, so a seed reproducing a mesh only on the
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
  node distribution with no symptom, and strict now is relaxable later. So is **a declaration
  reaching nothing**: an edge in no block, a corner on no edge.
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
  CHAINING, since a per-side emitter with one direction wrong emits the right SET of edges.
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
  elliptic smoothing is judged against.
- **Its own module rather than more of `MultiBlock.cpp`**: a different question ("is this mesh
  usable?" vs "what does this document declare?"), and a pure function of a finished mesh.
- **Inverted is counted over the EXPORTED cells, and the test is PER CORNER, not the signed area**:
  a bow-tie quad can self-intersect with a POSITIVE shoelace area (`(0,0) (3,0) (0,1) (2,1)` is +0.5
  and crosses itself). For a triangle the per-corner rule reduces to the signed area, so it is one
  rule for both cell kinds.
- **Non-orthogonality is measured on the STRUCTURED grid cells** — each corner angle's deviation
  from 90° — **and NOT on the split triangles.** From corner positions, so a strongly stretched but
  axis-aligned block measures *exactly* zero (no edge-length proxy can), and independent of
  `MB_SPLIT_QUADS`. An ANGLE with a closed form, not a badness score. **It is BLIND to a fold that
  preserves angles** — see the O-grid entry under smoothing.
- **A folded mesh is EXPORTED and exits 9; an invalid declaration exports nothing and exits 8**,
  both through the same `failExit` mechanism. `blSuccess` stays TRUE so the VTK keeps its ordinary
  name — `_er` marks a PARTIAL mesh and this one is complete.
- **The wall request is published from the SEAM, never re-derived downstream** (`MbWallSpec` on
  `MbResult`): only `buildMultiBlock` knows the spacing laws. The height is a distance ALONG the
  grid line, not perpendicular to the wall — they differ by cos(non-orthogonality), which is why the
  two figures are reported together.
- **"ASKED FOR" IS NOT AN INDEPENDENT TARGET YET; do not over-read the figure.** The request is
  DERIVED from the same law the fill reproduces and the blend is exact on the boundary, so **a
  rectangle's 0.00% is a tautology, not evidence**; what it measures is interior drift from what the
  two ends declare (trapezoid 7.38%, folded dart 25.41%). **SUPERSEDED by #55, exactly as
  predicted**: a perpendicular edge that DECLARES a wall height publishes that number, so the figure
  compares the mesh against the document, with `MbQuality.*` and every reader untouched. An edge
  declaring nothing still publishes the produced interval, so the sentence above still holds for
  such a topology — the negative control in `test_multiblock.cpp` 34.
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
  distinction must not be blurred. Permanent instead are two **negative controls** computing an
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
  a shared edge must be the side's OWN discretisation, not two curves that agree. Golden nodes move
  by **1.11e-16**, the new value being the exact one, which `golden_mesh.py` renders as
  `worst 9.167e-01` — an ARTEFACT of zipping two sorted node lists whose x-groups split; **do not
  read its magnitude on a case whose node SET changed membership**.
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
  fired the warning on a law that had honoured the request exactly, blaming the node count for the
  geometry's own faceting. Gated with a negative control by `test_multiblock.cpp` 36.
- **`coons` blends by the boundary's own NORMALIZED ARC LENGTH, not by the logical index**, and this
  is load bearing rather than a refinement: the index blend put an O-grid's first interior ring
  **6927% above** the requested wall height (806% even at twelve sectors), the arc-length blend
  reproduces a polar annulus EXACTLY. Facing curves are averaged; a degenerate side falls back to the
  index; both ends pinned to 0 and 1. **Behaviour-preserving on the existing set, measured against a
  HEAD binary**: worst node movement 6.7e-16, with `golden_mesh.py`'s 3 DIFFs the node-SET-membership
  artefact above.
- **The O-grid is FOUR BLOCKS IN A RING** (`examples/topology/ogrid_circle.json`,
  `config/multiblock_ogrid.dat`): i runs outward, j anticlockwise, so the four radials are ONE
  equivalence class that WRAPS — one declared count, three propagated, the last block welded back to
  the first by node identity. Measured on the shipped files: 0 inverted, non-orthogonality max
  2.25°, wall first cell **0.08%** off — a residue that is the stored polyline's FACETING, not the
  law (10× finer circles measure 0.0007%; it does not move with `BL_INITIAL_THICKNESS` or the ring
  seeding).
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
  shared edge was one block's east and another's west; here the two frames are mirror images and the
  edge is traversed in OPPOSITE senses from the same side index. No face of it reaches the `.bnd` —
  the whole difference between a cut and a wall, and `test_multiblock.cpp` 37 is the second thing
  that looks (the kind gate is the first). **Its 23 interior nodes MOVE since #84**, and it still
  exports no face smoothed.
- **The trailing edge is ONE declared corner, on FIVE edges, where FOUR blocks meet.** One node, by
  declaration. In `test_multiblock.cpp` 38's own fixture 60 node slots resolve to 47 nodes (the
  shipped grid is 5920 nodes / 11520 cells); three of the thirteen identifications are the trailing
  edge's own. **It is FROZEN by the smoother** (#84's declared-corner rule). The C's five radials
  are one equivalence class with ONE seed (check 39) — the O-grid's ring closes on itself, this
  chain does not, and its open ends are the two halves the cut splits the outlet plane into.
- **The gate that bit was GATE 2, not gate 1, and the fix was in the DOCUMENT.** Zero inverted
  cells on the first run of the shipped declaration; the solver then went to NaN in 40 iterations.
- **The far field's two nose sides cluster at their TRAILING-EDGE end to the AIRFOIL's own
  `ds_start`.** Over the chordwise surface the body's normals are nearly vertical and that boundary
  is horizontal, so the outer point opposite a body point sits at nearly the same x and the outer
  distribution must TRACK the body's. Left uniform: 59.52° / 16.0° / 3.46%, blowing up just aft of
  the **LEADING** edge. With it: **32.04° / 4.56° / 0.44%**, at the same `cfl 0.6` the O-grid used.
  **DERIVED, not tuned**: change the airfoil edges' spacing and this must follow.
- **A recorded acceptance run must state its CFL**: lowering `cfl` to 0.3 also makes the BAD mesh
  run, so "the solver runs" is quotable without improving the grid. The wake's 3144:1 worst edge
  ratio is **measured NOT to be the cause**.
- **A second airfoil file, not a sidecar beside `examples/geometries/naca0012.dat`.** That one is
  the hybrid path's geometry and has a golden baseline; a `.meta` beside it would change what that
  path reads. `naca0012_cgrid.dat` (two segments, split at the leading edge) and
  `cgrid_farfield.dat` (six, one per outer block side) are both checked against their ONE generator
  in the surface gate, never trusted.
- Gated by `tests/cpp/test_multiblock.cpp` 37-39 (4 hand injections, dated in that file),
  `tests/test_multiblock_cgrid_surface.py` (9 groups on the SHIPPED files, reusing #53's conformity
  measure) and the `mb_cgrid` golden case. The dated solver acceptance run is in that file's
  docstring.

**SMOOTHING is a STAGE inside the seam, its kernel is WINSLOW, that kernel is CONTROLLED (#83), and
since #84 it runs ACROSS the shared edges** (`MB_SMOOTH_ITERS`, default 0; `src/MultiBlock.cpp`'s
`mbSmoothBlocks` between the fill and the split; #81 built the stage with a Laplacian, #82 replaced
the kernel and DELETED that one, #83 gave it source terms, #84 unfroze the interfaces and cuts). An
elliptic solve over each block's movable nodes under a cap; at the default nothing runs and all
eighteen pre-existing golden cases are unchanged (all four tickets, 18/18 SAME at 0.000e+00,
`mb_cgrid_smooth` the only one that moved each time).
**Every measurement, table and reversal below: `docs/design_notes/mesher.md`.**
- **WHICH NODES MOVE IS `mbSmoothPlan`'s ANSWER, stated rather than read off a loop**
  (`include/MbShared.hpp` + `src/MbShared.cpp` in `hybmesh_pure`; #84). FROZEN: a node on an edge
  whose declared KIND is `wall` (the outer boundary is the DOMAIN, not the discretisation, and a
  bound node would leave the geometry it was attached to by arc length), and every DECLARED CORNER.
  MOVES: everything else — strictly interior to a block, or interior to an `interface` or a `cut`.
  The wall gate is `MbResult::wallSpecs`, the list `measureMbQuality` and `mbWallTargets` walk; no
  kind string is compared and NO POSITION is compared anywhere in that module.
- **#81's "every block boundary is frozen" IS REVERSED, and its objection is ANSWERED rather than
  dropped: the node is moved ONCE, in ONE frame, from ONE stencil.** A node on a block's south side
  has no `j - 1` row inside it; the row that IS its `j - 1` is the NEIGHBOUR's own first interior
  line, and `MbGhostFrame` is that continuation, matched station for station by node ID and never by
  distance. Nine real nodes, nothing averaged, no position computed twice, no tolerance needed
  between a 1e-7 wall spacing and a 1e-1 far-field one. **The four DIAGONAL corners of that frame
  have no answer and are not given one** (`at()` returns -1, never a clamp).
- **THE FOUR-WAY CORNER DOES NOT MOVE**: a corner is a declared POSITION, and the one node with no
  frame to be moved in — up to four blocks and five edges, needing exactly those absent diagonal
  ghosts. **ONE test, not two**: "on two of this block's sides at once" IS the declared-corner set
  here (an edge runs corner to corner, and the fill refuses a block whose sides do not meet at four
  shared corner nodes), so a separate corner-id set was written first and REMOVED — two sufficient
  conditions for one rule mask each other, and each injection came back inert. `hgrid()` makes it
  falsifiable: a four-way corner on four interfaces and NO wall, where the C-grid's trailing edge is
  on the airfoil and the wall half would freeze it anyway.
- **WHICH BLOCK MOVES A SHARED NODE: the one declaring MORE WALL SIDES PERPENDICULAR to the line**,
  ties to the lower block index — **not the lower index, which is what #84 wrote first.** The kernel
  does not care (the Winslow update is INVARIANT under the frame change between two blocks meeting
  at a shared edge, which check 56 measures rather than assumes); the CONTROL does, because a wall's
  control reaches a shared line only as the `k = 0` or `k = n - 1` station of that wall's own walk.
  On the C-grid `r_te_up` is the wake block's north (one such wall) and the upper airfoil block's
  south (two), and the wake block is the lower index.
- **THE CONTROL FIELD COVERS A WALL'S TWO END STATIONS, and it had to**: those are the block's
  perpendicular SIDES, exactly what a shared edge frees, so a field stopping at `k = 1` frees a node
  and holds nothing on it. Skipped where that side is a `wall`, gated on AVAILABILITY in the ghost
  frame rather than on an index, so the freeze rule lives in one module.
- **`MbResult::sharedEdges` IS PUBLISHED BEFORE THE SMOOTHER, not after the split.** One line too
  late until #84: the freeze rule reads that list, so with it empty every shared node stayed frozen
  and the ticket was a silent NO-OP behind 106 green tests. A PUBLICATION moved, not a decision —
  nothing in that loop reads a cell or a position, and fill-then-smooth-then-split is unchanged.
- **`MbSideWalk` / `mbSideWalk` LIVE IN `include/MultiBlock.hpp`**, beside `mbSideAxis` and for its
  reason: three readers in two files, having been written out three times inside `MbControl.cpp`
  alone. Its `tt` may be -1 or `m` — one step OUTSIDE the block — and `MbBlock::nodeAt` is never
  handed those. `MbControl.cpp` keeps a SECOND, in-block accessor on purpose: the control's
  differences read the ghost frame, while `mbWallTargets` and `mbWallResidual` stay one-sided at a
  wall's ends, being the RULER's measure.
- **WALL NODES DO NOT SLIDE ALONG THEIR BOUND EDGE, and #83 decided that rather than inheriting
  it.** The alternative was live and is the stronger tool — a bound edge's polyline is known, so a
  node could be moved along it and let the surface distribution answer to the interior. Refused
  because on THIS path the declaration is the authority: a corner attaches at a declared arc-length
  position and an edge's spacing comes from a declared law, so redistributing a wall overwrites the
  document. The concrete contradiction is with #83's own deliverable — `MbWallSpec`'s requested
  height comes from the perpendicular edge's declared `ds`, so sliding moves the along-wall
  distribution while the request stays put, with no gate able to say which is right.
  **The consequence for `BL_USE_ANALYTIC_GEOM` is therefore NONE**: no reader here, the read and
  unread survivor lists in `.claude/rules/mesher.md` unchanged, still a declared survivor nothing
  reads. #48's "survives as the projection basis" is about a projection this path does not do.
- **Node identity is untouched**: the sweep writes coordinates and allocates nothing, so a welded
  node stays ONE node. No comparison, therefore no tolerance — `MB_SMOOTH_TOL` is a STOPPING rule on
  how far a node moved, never a rule about two nodes being one.
- **JACOBI, not Gauss-Seidel**, with the metric coefficients AND the control field LAGGED — every
  sweep reads what the previous one left, so the answer is not a function of a traversal nobody
  declared. Same objection the randomized split rule raises against a sequential stream. **Between
  the FILL and the SPLIT**; both readers there are id-only today, so injection Y (the block moved
  past the split) is INERT, and the ordering keeps that from being re-checked per reader.
- **`MB_SMOOTH_ITERS`, never `BL_SMOOTHING_ITERS`-with-a-prefix and never `SEED_*`.** The BL key is
  the OTHER path's collision remedy; these two share a verb and nothing else. **The control
  functions (#83) and the freed seams (#84) add NO KEY**: neither is an alternative behind a switch
  — one is the kernel's missing input, the other the freeze rule corrected — and a selector over one
  answer is the abstraction the no-inert-alternatives rule exists to prevent, the same call #82 made
  when it deleted the Laplacian.
- **A NEGATIVE count is refused BY NAME through both doors** — `Config::validate()` with
  `EXIT_ERR_CONFIG` and `buildMultiBlock` for any other caller — never clamped. The parameter is a
  signed `int` so the refusal is writable: widening -1 to an unsigned count is four billion sweeps,
  a hang rather than a mesh. **A FRACTIONAL value TRUNCATES and is not refused**
  (`MB_SMOOTH_ITERS 1.9` runs one sweep): the `.dat` reader takes every int key through a `double`,
  and diverging for one key would put back the per-row parse rule that let the parsers disagree.
- **THE LAPLACIAN #81 SHIPPED IS DELETED, not kept behind a selector.** Nothing read it and it
  loses on every column of both shipped cases at every cap (C-grid at 1 sweep: max 89.40° vs
  31.44°, wall 36.61% vs 11.65%). A kernel-selection enum over one surviving kernel is the
  abstraction the no-inert-alternatives rule exists to prevent. It survives ONLY as
  `laplacianByHand` in `tests/cpp/test_multiblock.cpp`, so checks claiming the two kernels differ
  have both sides written down. **#83 and #84 both restated that rule rather than replacing it** —
  neither adds a selector — and #83's own rewrite of this block DELETED this bullet by accident,
  caught by a review running `docs/agents/rule-file-style.md`'s ruler rather than by a gate, because
  check 3 pins gate FILENAMES and an identifier can vanish from prose unnoticed.
- **THE CONTROL FUNCTIONS ARE TWO SOURCE TERMS, and their WALL GATE IS `MbResult::wallSpecs`**
  (`include/MbControl.hpp` + `src/MbControl.cpp` in `hybmesh_pure`; #83). The system solved becomes
  `a(x_ii + phi x_i) - 2b x_ij + g(x_jj + psi x_j) = 0`, and **both zero is the plain #82 update,
  term for term** — the property #82's exactness gate keeps measuring. NO second answer to "is this
  a wall": the module walks the seam's own published list, the same one `measureMbQuality` walks,
  and an `interface` or a `cut` is not in it. The module NAMES `MbControl.cpp` and `MbShared.cpp`
  are load bearing — this file's globs cover `Mb*` as patterns, so a `MultiBlockControl.cpp` or a
  `MultiBlockShared.cpp` would have arrived ruleless.
- **THE TARGET IS THE RULER'S OWN BLEND, NOT ARC LENGTH.** `MbWallSpec` carries the height at a
  side's two corners; between them `measureMbQuality` blends LINEARLY IN THE LOGICAL COORDINATE, so
  the control aims at exactly that. Arc length along the wall is the tempting answer and is WRONG:
  it drives the mesh at one number while the acceptance gate measures another — the
  second-answer-to-one-question defect, which the edge-distribution warning made in mirror image by
  comparing a CHORD against a request in arc length. **The measure of the request and the measure of
  the achievement must be the SAME measure.**
- **THE OFF-WALL SOURCE IS SOLVED, EXACTLY, FOR THE DISTANCE THE RULER MEASURES, at the FIRST
  INTERIOR ROW ONLY** — one quadratic in one scalar, the root taken landing nearer
  `p_wall + requested * inward_normal`, **which is where the 90-degree half of the declaration
  enters**: the tie-break between two points at the same correct distance. Derivation: the note.
- **THE TWO HALVES ARE NOT DRIVEN EQUALLY, and the name "control functions" overstates one.** The
  HEIGHT is solved for exactly. The 90 DEGREES has NO term stating it — that tie-break, the elliptic
  operator's tendency, and the along-wall source keeping the first interior line matched to the wall
  so the two do not shear. A DIRECT condition on the angle (Steger-Sorenson projected onto `r_s`)
  goes as `1/h²`, clips and destabilises, and is one of **three weaker versions measured and
  rejected** with the near-wall 1-D limit and a least-squares solve for the target POSITION; their
  figures are the table at `docs/design_notes/mesher.md`'s "least squares for the target position".
  Under #83 the angle therefore IMPROVED AND THEN TURNED (32.04° -> 29.90° at twenty, 31.55° at
  thirty, 34.78° at forty). **#84 REMOVED THAT TURN, and it was never the angle condition's doing**
  — it was the interior shearing against a frozen seam: with the seams free the max falls
  monotonically to 26.49° at a cap of 100 and turns only past 150.
- **BEYOND THE FIRST ROW THE OFF-WALL SOURCE IS THOMAS-MIDDLECOFF ON THE LINE'S OWN SPACING**, and
  the along-wall source is Thomas-Middlecoff at BOTH ends of the off-wall direction, blended
  LINEARLY in the normalized logical coordinate. **That second half is what makes all three of #80's
  figures improve at once**, and it is a scope rule: the declaration asks for ONE height and says
  nothing about the rest of the line, so the first row is the declaration's and the rest the fill's.
  Sourcing nothing out there lets the grading relax and the MEAN rises; an ideal GEOMETRIC line
  imposes a distribution nobody declared, since these radial edges declare a TANH law. Both
  measured, both in the note. The blend is LINEAR because a decay rate is a constant with no
  derivation behind it.
- **A SOURCE TERM LARGER THAN `MB_CONTROL_CLIP` (2.0) IS CLIPPED AND COUNTED, and the bound is the
  KERNEL'S, not a taste.** The update weights a neighbour by `a(1 +/- phi/2)`, so at `|phi| = 2` one
  weight reaches zero and past it the node stops being a convex combination of the nine positions it
  reads — no maximum principle, so a node can leave their hull, which is a fold. **`smoothClipped`
  is published and reaches `HYBMESH_MB_SMOOTH` as `clipped=`.**
- **THAT COUNT IS A DIRECTION, NOT A THRESHOLD**, and reading it as one was #83's own first
  mistake. On the shipped C-grid it runs **40, 28, 22, 8, 0** over the first ten sweeps with a sound
  mesh throughout — the control CATCHING UP with a target the fill starts far from — then climbs
  back off zero, 156 at sweep 400 and 428 at 500, alongside the folds. Falling is the solve working;
  rising after it has reached zero is the iteration going. **A number with two opposite meanings
  cannot gate an `if`**, so it is reported with a sentence saying which way to read it, and the
  advice points at the inverted-cell count instead.
- **THE NUMBER IS A CAP, AND THE SOLVE HAS THREE ENDINGS: converged, capped, DIVERGED.** It stops
  when its residual — the largest node move, over the STARTING mesh's bounding-box diagonal — falls
  under `MB_SMOOTH_TOL` (1e-8; relative so mm and m take the same sweeps, and NOT a config key,
  because the knob a user has is the cap); still moving at the cap comes back
  `smoothConverged == false` with a warning. On divergence the solve stops at
  `MB_SMOOTH_DIVERGE_FACTOR` (10x) its best residual and **returns the BEST iterate, not the last**,
  publishing `smoothConverged`, `smoothDiverged` and that iterate's sweep. **Never hand back a
  truncated solve as though it had finished.**
- **A CAP IS TWO SITUATIONS AND THE ADVICE MUST TELL THEM APART.** `smoothBestSweep` /
  `smoothBestResidual` publish the smallest residual reached and when, recorded BEFORE either stop
  is tested. Still FALLING has more to give; already ABOVE its best has TURNED, and both wear
  `converged == false && diverged == false`. **The mesh at a cap is still the LAST iterate** — N
  sweeps means N sweeps outside the diverged path — so the difference is SAID, not repaired.
- **"RAISE IT UNTIL IT CONVERGES" IS NO LONGER BAD ADVICE FOR #82's REASON, AND THE SENTENCE IS
  GONE.** That kernel's fixed point was each block's harmonic map, holding no declared height at all
  (3133% off on the C-grid); the controlled solve holds that wall to 0.10% at twenty sweeps and **a
  graded rectangle is a fixed point of it**. What bounds the cap now is STABILITY — and **#84 moved
  that bound out by an order of magnitude**, because a grid whose seams can move has somewhere to go
  instead of shearing against them: the C-grid folds 0 cells through a cap of **300** (#83 folded 4
  by 100) and 184 by 400, the O-grid 0 through 150 and 192 by 300. **Raise it only while the
  inverted-cell count stays 0** — machinery that already exists rather than a second signal.
- **EACH MACHINE-READABLE LINE KEEPS ONE MEANING, and the prefix is matched WITH its trailing
  space.** `HYBMESH_MB_QUALITY` always describes the mesh AS EXPORTED; the before half is
  `HYBMESH_MB_QUALITY_BEFORE` and appears only when a sweep ran, so an unsmoothed run's QUALITY
  REPORT is byte for byte what it was — not its whole output, which gains one unconditional
  `Smoothing Sweeps` provenance row on purpose. The trailing space keeps the suffixed line from
  being read as the real one, in the ONE parser (`test_multiblock_quality_surface.qlines`) every
  gate imports rather than in four near-copies. `HYBMESH_MB_SMOOTH` is the SECOND such line (#82)
  and describes the SOLVE: only when a sweep ran, carrying `sweeps cap converged diverged residual
  best_sweep best_residual tol clipped moved moved_shared` (the last two #84's), no suffix because
  it has no before/after half. Its parser is `test_multiblock_smooth_surface.smooth_line`.
- **THE REPORT IS BEFORE AND AFTER.** `MbResult::preSmoothNodes` publishes the mesh as it stood
  before the first sweep, so the two reports are the same cells and blocks over two coordinate sets
  and their difference is the smoother alone. **Shipped C-grid, ONE sweep, all three moving the
  right way: max non-orthogonality 32.04° -> 31.86°, mean 4.562° -> 4.516°, wall first cell
  0.4368% -> 0.1222%. At twenty sweeps 29.90° / 3.821° / 0.0968%, inverted 0** — #80's acceptance
  for the control functions, met with both metrics improving at once rather than one traded for the
  other. **#84's own contribution is SEPARABLE and is in the MEAN and in the CAP**: at twenty #83
  was at 29.90° / 4.301° / 0.0893% (max identical to three decimals, mean 0.48° worse), and at forty
  34.78° / 4.214° / 0.0980% against #84's 28.55° / 3.388° / 0.1111%. #82's were 31.44° / 4.78° /
  11.65%.
- **THE RUN REPORTS WHICH NODES IT WAS FREE TO MOVE** (`MbResult::smoothMoved` /
  `smoothMovedShared`, a `Movable nodes` banner row, `moved=` / `moved_shared=` on
  `HYBMESH_MB_SMOOTH`; NEGATIVE when no sweep ran, on `smoothResidual`'s rule). The freeze rule is a
  decision about the DECLARATION, so a run must SHOW it — the argument the propagated counts and the
  welded shared edges rest on. C-grid 5600 of 5920 with 140 shared, exactly the interior of its four
  shared edges (23+39+39+39); O-grid 4512 of 4704 with 188.
- **THE NEAR-LEADING-EDGE CELLS ARE MEASURED ON THEIR OWN, because a mesh-wide average can improve
  while the region the solver diverged in does not.** #57's worst corner is at (0.0134, 0.0196);
  over the ten quad cells touching the airfoil between x = 0.005 and 0.030 the region goes
  **32.04° / 26.90° -> 29.90° / 24.91°** at twenty sweeps. The instrument is a quad reader in the
  surface gate, not a new metric: the METRIC is the ruler's and the gate adds a SELECTION, validated
  by reproducing the ruler's whole-mesh figures off the same code first.
- **#80's O-GRID NEGATIVE CONTROL IS STILL NOT MET — BY 1.2%, AND THE RESIDUE IS THE FACETED WALL's
  RATHER THAN THE INTERFACE's.** All three clauses: the first alone reads worse than the truth, and
  dropping it reads better. A case already at 2.250° comes out at **2.276°** at EVERY cap from 1 to
  150, against #83's 3.632° at one sweep and **12.036° at twenty**. So #83's "no single
  `MB_SMOOTH_ITERS` satisfies both of #80's bullets" is **GONE**: the gap no longer grows with the
  cap, the mean is exactly #55's 1.875°, the wall first cell is still BETTER (0.0390%).
  **THE 1.875° MEAN IS STRUCTURAL, not a strong result** — a 48-gon's every quad corner deviates by
  half the sector angle whatever the radial distribution is — but it does say the grid is POLAR
  again, where #83's 2.571° at twenty was the interior pulled off it by frozen radials.
  **WHERE THE KINK WENT, measured**: #83's worst corners sat MID-BLOCK on the four declared radials
  at r ~ 3.43, #84's sit at r = **9.19**, one line in from the faceted outer circle whose own
  corners are 2.250° at r = 10 — and the mid-block band's cells now come out BETTER than the fill
  left them (2.2477° -> 1.8794° at twenty). **So the bullet fails on the frozen WALL's faceting, and
  closing it needs #83's "wall nodes do not slide" revisited rather than more sweeps.**
- **A fold from smoothing is an ORDINARY inverted mesh**: counted after the sweeps, exported, exit
  9, no new code. **And it is REACHABLE on the shipped files**, reversing #82's blind spot — the
  C-grid folds 184 cells by a cap of 400, so the surface gate asserts exit 9 on a real file. **The
  O-GRID's FOLD IS INVISIBLE TO NON-ORTHOGONALITY**, a limit of the RULER recorded as one: at a cap
  of 300 it folds 192 cells while max non-orthogonality reads 2.274°, because two adjacent radial
  lines have swapped order and the folded cells stay nearly rectangular. Only the inverted count
  sees it.
- Gated by `tests/cpp/test_multiblock.cpp` 40-56 (7 injections from #81, 13 from #82, 14 from #83,
  11 from #84, dated in that file), `tools/PreProcessor/tests/test_multiblock_smooth_surface.py`
  (11 groups on the SHIPPED C-grid AND O-grid, importing #53's own conformity measure rather than
  re-inventing it) and the `mb_cgrid_smooth` golden case, recaptured deliberately by #82, #83 and
  #84 — **the only one of the nineteen that moved any of the three times.**
  **AN INERT INJECTION IS ANSWERED WITH A CHECK OR A FIXTURE**: four of #83's needed a check, one
  needed `wallSquareTwoEnds` (the first case declaring DIFFERENT heights at a wall's two ends), and
  #84 needed `hgrid()` (a four-way corner on NO wall) and `wallTwoBlocks()` (the only fixture where
  a wall's END station is a shared edge). Three stay INERT and are named there: #82's thirteenth,
  #84's station-by-station weld match (unfalsifiable on a correct document) and #84's
  declared-corner freeze ALONE (held twice).
  **The DIVERGED ending came BACK to the shipped files with #84** — #82 reached it there, #83's
  residual plateaued instead, #84's C-grid diverges at sweep 1111 and hands back that iterate. The
  CONVERGED ending is reachable only on the C++ test's notched box (0.50 converges in 290 sweeps,
  0.35 diverges at 9); the stability limit only on the shipped files.

## Named blind spots

Consolidated here rather than trailing each rule, so a coverage claim can be checked against
one list. #68 moved the first; #69 moved the rest; #89 split the list with the rules.
**One blind spot that also covers this path is in `.claude/rules/mesher.md`'s list instead** —
`golden_mesh.py` does not compare the `.bnd` `segm_no` column, and six of that comparator's
nineteen cases are multi-block. It is not duplicated here, because a blind spot living in two
places is one that will only ever be updated in one; a reader of this file alone would not
otherwise learn the hole exists.

- **Non-orthogonality says nothing about the shape of the SPLIT TRIANGLES** — it is measured on the
  structured grid cells only.
- **Nothing runs the solver or the grid converter on the folded mesh** (`MbQuality`'s sharpest).
- **Nothing projects onto an ANALYTIC curve.** A bound edge follows the stored POLYLINE, so
  "follows the circle" is measured against that polyline's vertices and #55's 0.08% wall-height
  residue is its faceting. `BL_USE_ANALYTIC_GEOM` is a declared survivor nothing reads — and #83
  KEPT it that way on purpose rather than by omission, by deciding that wall nodes do not slide;
  the rule above carries the reason.
- **A curved INTERFACE is still undeclarable** (a `binding` is wall-only), so #55's O-grid is a
  single ring rather than a boundary-layer ring inside a far-field one, and no two-sided stretching
  function with DIFFERENT heights at each end exists.
- **The arc-length blending's magnitude is measured OUT OF TREE**: no gate re-measures the 6927%
  the logical-index blend cost, only its consequence through `test_multiblock.cpp` 33/34 and the
  surface gate's quality line.
- **The end-to-end re-resampling check uses a straight-sided geometry**, where an arc-length
  position is EXACT under resampling. On a *curved* segment an attached corner moves by a chord
  sagitta — a limit of the geometry, not of the binding. The curve-following half is pinned in the
  C++ test (`tests/cpp/test_multiblock.cpp`).
- **Nothing measures the QUALITY of the randomized rule's bit stream.** Checks 24-26 assert that
  both diagonals appear, that the pattern is not parity's, and that it is a function of the four
  declared inputs — a hash with a visible period would pass all of them. Deliberate: a distribution
  test over 12 cells asserts noise, and the property that matters (no direction imprinted on a
  uniform region) is what `MbQuality` measures on a real case.
- **The C-grid's 0.005 far-field clustering is UNENFORCED**: derived from the airfoil edges' own
  `ds_start`, but two numbers in one document that happen to agree; only the acceptance run would
  notice them diverging.
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
  fill-then-smooth-then-split ordering is a design rule held by a comment, not by a gate. **Nor is
  the position of a PUBLICATION relative to its reader**, which #84 found the hard way — see the
  `sharedEdges` rule above.
- **The smoothed mesh is never given to the solver or the grid converter, and since #83 that is a
  GAP rather than a non-question.** Under #82's kernel it would have been a strange thing to want —
  11.65% off the requested wall height is not a boundary layer worth integrating — but at 0.10% it
  is exactly what #80's own acceptance asks for, and nothing here runs it. It belongs to #85.
- **NOTHING MEASURES THE C-GRID's FREED INTERFACES ON THEIR OWN TERMS.** The O-grid's four radials
  lie at four known angles so a surface gate can select the band; the C-grid's three have no such
  handle from outside a `.vtk`, so what is read there is the WAKE and the whole-mesh figures. The
  C++ test reaches those lines by node id and pins the MECHANISM, not the quality.
- **#84's OWN WAKE-CUT CRITERION IS UNREACHABLE ON THE SHIPPED GEOMETRY, and the PREMISE is wrong
  rather than the mesh**: the fill already leaves all 48 cells against that straight, on-axis line
  EXACTLY orthogonal, so freeing it COSTS 0.018° mean. The lines that were actually the worst are
  the radial interfaces, and those improve. Figures: the design note.
- **NOTHING BOUNDS THE CAP AUTOMATICALLY.** #83's stability limit is real (the shipped C-grid folds
  past about forty sweeps) and is reported after the fact by the inverted-cell count and exit 9;
  nothing stops the solve at the last sound iterate the way the DIVERGED path stops it at the best
  residual. The two are different signals and only one of them is acted on.
- **The before/after tables are dated quotations**, not re-measured: the gates assert a DIRECTION
  with a floor, so a kernel that stopped moving anything is caught while one that moves things
  differently is free to.
- **NO RULE FILE'S GLOBS REACH `tools/`**, so the O-grid rule's own spacing law —
  `tools/PreProcessor/include/Spacing.hpp`, named in that rule — is unreachable from the tripwire
  table: a session that opens it is handed no rules at all. Pre-existing and NOT created by #89's
  split, which neither widened nor repaired it; recorded here rather than fixed, because that
  commit had to stay a move. It is the fourth instance of the shape the budget gate's own blind
  spot (c) tracks (`phi_quality.py`, `run_batch.py`, `CMakeLists.txt`), and the same one: the
  unreachable file is always the one OUTSIDE the package the rule's other modules live in.
