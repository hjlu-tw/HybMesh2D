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
wall first-cell height accuracy, CELL SHAPE and cell count, plus one machine-readable
`HYBMESH_MB_QUALITY cells=… inverted=… nonortho_max_deg=… nonortho_mean_deg=…
wall_first_cell_worst_rel=… quad_midline_ratio_cells=… quad_midline_ratio_median=…
quad_midline_ratio_p95=… quad_midline_ratio_max=…` line, so the acceptance gate is a grep.
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
- **CELL SHAPE is measured on the STRUCTURED quads too, by the shared pure metric** (#129,
  parent #128; `include/CellShape.hpp` — its own rules are in `.claude/rules/mesher.md`, whose
  globs reach it and this file's do not). Median / p95 / max of the opposite-edge midline ratio,
  so a square reads **1.0** and not the 1.414 the split triangles would give, and the figure is
  **independent of `MB_SPLIT_QUADS`** — measured on the shipped O-grid: `cells=` 9216 → 4608 while
  all four `quad_midline_ratio_*` are bitwise identical.
  - **The metric's name is in the KEY, never as a value.** Every token of `HYBMESH_MB_QUALITY` is
    `key=<float>` and `qlines` — the ONE parser, imported by SIX gates from the one that owns
    it — floats all of them, so a `shape_metric=…` token would break all seven files. The
    hybrid path's different quantity is `tri_edge_ratio_*` on its own `HYBMESH_HYBRID_QUALITY`
    line (#130), so neither a grep nor the parser's own prefix can confuse the two.
  - **A QUAD WHOSE IDS DO NOT ALL RESOLVE IS UNMEASURABLE, said HERE** — passing the
    resolved corners on short would reach the metric as a TRIANGLE and come back with an
    ordinary edge ratio for a cell nobody could measure (check 9e).
  - **ONE ROW PER BLOCK under the headline**, the way each wall gets a row under the wall
    headline, named with the id the DOCUMENT gave the block. A block that yields nothing
    measurable is LISTED with `not measured`, never dropped — the row-level half of the negative
    rule, check 9d, written because 6b's history says it has to be.
  - **NO COLOUR AND NO THRESHOLD, anywhere, by decision.** The shipped O-grid's max is 32.77 =
    0.0327 azimuthal spacing / 0.001 requested `BL_INITIAL_THICKNESS` — what the user asked for,
    not a defect. `test_multiblock_quality_gate.py` gains no bar on these three figures.
  - **The `.provenance.json` sidecar gains `mesh.quality`** — `metric`, `cells`, `median`, `p95`,
    `max` — fed by the SAME report object the banner and the machine line read, so the three
    cannot disagree. It is the contract #131 and #132 read instead of recomputing.
  Why: `docs/design_notes/mesher.md`, "CELL SHAPE: three numbers, one definition".
- Gated by `tests/cpp/test_mb_quality.cpp` (14 groups, 79 checks),
  `tests/test_multiblock_quality_surface.py` and `tests/test_multiblock_shape_surface.py` (the
  shape figures on the shipped O-grid and H-grid, through the real binary). **Its injections are
  HAND runs, dated in the C++ test's docstring** — a C++ test cannot mutate the implementation it
  linked against, and that distinction must not be blurred. Permanent instead are two **negative
  controls** computing an injection's own premise (check 6 the bow-tie's +0.5 area, check 2 its
  ~17x stretch). One injection, `I`, is recorded as **INERT** and kept: the rule it attacks is
  guarded one level down, in the pure gate.

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
- **A SAMPLE RATE THE SOURCE POLYLINE CANNOT CARRY IS SAID, AND THE WARNING IS KEYED ON THE COST
  RATHER THAN ON THE RATIO** (`sampleRate` in `src/MultiBlock.cpp`; `MB_SAMPLE_RATE_TOL_DEG`, 0.1
  deg of TURN; #94). A bound edge places its nodes by arc length, so when its interval count and
  its stretch's facet count are not commensurate, consecutive nodes span different numbers of
  facets and the polygon it meshes has IRREGULAR corners — nothing is wrong with the declaration
  and nothing errors, the mesh is simply worse than the same declaration on a better-resolved
  geometry. The warning names the EDGE, both counts, the ratio, both angles and BOTH fixes with the
  arithmetic done: resample so the stretch carries a MULTIPLE of the interval count, or declare the
  count whose intervals divide the facets — saying that the count PROPAGATES, so it moves the
  opposite side of every block on the chain.
  - **THE COST IS AN ANGLE AND THAT IS THE DECISION.** A non-dividing ratio on a STRAIGHT stretch
    costs exactly nothing, so keying on the ratio fires on **14 of the 19 shipped bound edges** and
    is read by nobody, while keying on the cost fires on **8**, every one of them one of the
    O-grid's two circles. Measured as the worst turn the mesh nodes make against the worst an EVEN
    sampling of the same curve at the same density would make, both maxima over the edge's interior
    nodes the way `MbQuality` takes its worst corner.
  - **THE POLYLINE's TURN MUST BE SMEARED over each vertex's two half-facets**, and that is
    required rather than tidy: read as a STEP at the vertex, a window shorter than one facet — the
    shipped far field, at 0.833 facets per interval — returns the whole vertex turn, `even` comes
    back equal to `worst`, and the whole measurement reads zero on the case that motivated it.
  - **The DIVISIBILITY test is kept although no injection can make it fire**, because on a dividing
    ratio the estimator's bias is toward silence. It is what makes the MESSAGE's own advice true
    whenever the message is printed, and check 57 reads those numbers back out of the message.
  - **THE COUNT FIX IS THE EQUIVALENCE CLASS's, NEVER THE EDGE's**, and it is
    `gcd(facet counts of the chain's BOUND edges) + 1` — an interval count divides a stretch
    exactly when it divides that stretch's facet count. #94's review found the per-edge version,
    which advised 41 on the shipped O-grid's body arcs and 21 on its far-field ones with `w0` and
    `o0` in ONE class: two contradictory instructions, one of which (41) puts the far field at the
    1/n worst case and costs 2.250° against the 0.750 it started from. **Unbound edges are excluded
    from that gcd** — a chord is one facet and would drag every chain it touches to 1 — and **a
    chain of coprime stretches is told it has no count**, rather than being handed the useless 2.
  - **AND IT IS ONE-DIRECTIONAL: a ratio of 1/n is the WORST sampling, not an exempt one.** #94's
    review asked for `intervals % facets` as well, reasoning that n equal intervals to a facet is
    even sampling. Measured, every n-th node lands on a vertex and takes its WHOLE turn while the
    rest take none: 0.500 costs 2.250° of turn against the shipped 0.833's 0.750°. Widening it
    would silence the worst cases, and check 57's `ogrid("", 7, 11)` row is what stops that.
    The MESSAGE is what the review got right — at an exact 1/n the nodes do span the same number
    of facets — so it states the ratio as "not a WHOLE number of facets to a node".
  - Gated by `tests/cpp/test_multiblock.cpp` 57, whose fixture is non-commensurate BY DECLARATION
    so that #95 cannot take the coverage away with the shipped geometry (14 hand injections, 3
    inert and named); `tests/test_multiblock_ogrid_surface.py` group 9, which asserts the warned
    figure ACCOUNTS FOR that mesh's own max-minus-mean gap (0.375 deg, exactly half the worst
    warned excess) rather than asserting that a warning appeared; and
    `tests/test_multiblock_cgrid_surface.py` group 10, the SILENCE. Neither surface half is worth
    much alone.
    Why: `docs/design_notes/mesher.md`, "A SAMPLE RATE THE POLYLINE CANNOT CARRY IS NOW SAID".
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
  shape), not a string compared at six sites — it shipped as the latter, and the review that
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
  the first by node identity. **Its far field is stored at 320 facets since #95** — the density past
  which it stops binding the 96-node ring, not a convergence point. Measured on the shipped files at
  the default: 0 inverted, non-orthogonality max **2.025°**, wall first cell **0.037%** (0.0036%
  unsmoothed). The angle is the stored polyline's FACETING, not the law, and is now the BODY's 160
  facets under the same ring. **The wall figure is NOT**, and that is new: 0.0036% is what the
  faceting leaves, and the default's 20 sweeps take it to 0.037% — so at the default the SMOOTHER's
  own perturbation of the second row is the larger of the two effects, and #55's "10× finer circles
  measure 0.0007%" is a statement about the unsmoothed number. #55's 2.25° / 0.08% were the FAR
  FIELD's 80 facets and are what #80's last unmet bullet was written against. **Do not make the far field commensurate with the
  ring** (96, 192, 288 all reach the 1.875° floor): the ring's count is one declared number the
  equivalence class propagates, so that would couple a geometry file to a count nothing enforces.
  A robust 2.025 over a fragile 1.875 — the reasoning is #57's far-field-clustering blind spot.
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
  that looks (the kind gate is the first). **Its 23 interior nodes MOVE since #84**, still exporting
  no face.
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

**The BLOCK ID is written to the VTK as a cell field, and it is OPTIONAL** (`Element::blockId`
in `include/Mesh.hpp`, the `CELL_DATA` section in `src/Mesh.cpp::exportVTK`, filled by the
adapter in `src/cli.cpp`; #106). #48's user story 39, the one item of that issue never built and
never reversed — it is #48's ONLY concession to blocks surviving the flattening step, so without
it "blocks are internal scaffolding, not an output format" is the whole story.
- **The value is the INDEX into `MbResult::blocks`, never the block's declared `id` string.** The
  randomized split rule hashes the id for the reason `MultiBlock.hpp` states — an index moves when
  a block is declared ahead of it — and both properties are wanted, in different places. The
  declared id, if ever wanted in the file, is a SECOND string-valued field and not a substitute.
- **PRESENT OR ABSENT, never a defaulted 0 and never a `-1`.** The hybrid path has no blocks: a
  field claiming every one of its cells is in block 0 is a confidently wrong answer, and a
  sentinel is a field every reader has to know to ignore. So the section is written **only when
  EVERY cell carries a tag** — a VTK scalar array has one value per cell and no way to spell
  "this one has none", so a partially tagged mesh could only be written with that sentinel.
- **The exporter is the ONLY place it lands, and there is NO config flag.** No `.vrt` / `.cel` /
  `.bnd` change: the solver's grid converter is unstructured and has nowhere to put it, which is
  #48's own reasoning for blocks not being an output format. A switch to turn off a debug aid that
  costs one integer per cell is a knob to maintain and a second state to test.
- **`addElement(ids, blockId)` is an OVERLOAD, not a write to `elements.back()`** — the same
  reason `addTaggedEdge` exists: the assign-to-`back()` idiom is a second chance to record the
  cell and forget the tag.
- **The array is named `block`, and that name is part of the interface** — it is what a reader
  selects in ParaView, so renaming it is a user-visible change and not a tidy-up. Pinned by name
  in `tests/test_multiblock_block_field.py`.
- Gated by `tests/test_multiblock_block_field.py` (41 checks over the three shipped configs plus a
  hybrid run; 6 injections dated in that file). Its per-block counts are compared against the
  RUN'S OWN reported block dimensions, never a written-down number, so a re-seeded topology moves
  both sides together. **The PARTIALLY tagged state is gated separately**, in
  `tests/cpp/test_mesh_vtk_block_field.cpp`: no run can produce it, so a gate over the binary
  cannot construct it, and a test that links `Mesh` can (#113).
  Why: `docs/design_notes/mesher.md`, "THE BLOCK ID AS A VTK CELL FIELD".

**SMOOTHING (`MB_SMOOTH_ITERS`) HAS ITS OWN RULE FILE: `.claude/rules/mesher-smoothing.md`**
(#85). The whole of #80's five-ticket arc lives there — the stage inside the seam, the Winslow
kernel, the wall control functions, which nodes may move and in whose frame, the two
machine-readable report lines, the default and the quality gate — because it had outgrown this
file's budget and because it is a different question: this file answers "what does this document
declare and how is it filled", that one answers "and then what MOVES". A session editing
`src/MbControl.cpp`, `src/MbShared.cpp` or `src/MultiBlock.cpp` loads BOTH, which is the intended
overlap (#89's precedent); a session editing only the split rules or the BC binding loads neither
of the other's rules. **SMOOTHING IS ON BY DEFAULT since #85** (`MB_SMOOTH_ITERS` 20), so a change
to the fill below changes a mesh that is then relaxed — the golden family's multi-block cases are
captured with it on.

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
- **`golden_mesh.py` DOES NOT COMPARE THE VTK CELL FIELD**, so a defect confined to #106's block
  id is invisible to all ten multi-block cases: it reads the `.vtk` through `VTKMesh`, whose parser
  stops at `CELL_TYPES`. Measured — 19/19 SAME across the commit that ADDED the field. The same
  shape as the `.bnd` `segm_no` hole in `.claude/rules/mesher.md`'s list, and stated here because
  it is this path's field; `tests/test_multiblock_block_field.py` is the whole of its coverage.
- **NOTHING CHECKS THAT EVERY MULTI-BLOCK CELL IS TAGGED.** `exportVTK` writes the section only
  when ALL cells carry a tag, and today the adapter's one loop guarantees that. A future
  `MESH_MODE 1` change adding a single untagged element would make the whole field disappear
  rather than half-appear; that is the right FAILURE, but it is a silent one, caught by the
  warning at run time and by no gate. **PARTLY CLOSED by #113**, which gates the failure but not
  this precondition — the rule above names the gate.
- **Nothing runs the solver or the grid converter on the folded mesh** (`MbQuality`'s sharpest).
- **Nothing projects onto an ANALYTIC curve.** A bound edge follows the stored POLYLINE, so
  "follows the circle" is measured against that polyline's vertices and the wall-height residue is
  its faceting. `BL_USE_ANALYTIC_GEOM` is a declared survivor nothing reads — and #83
  KEPT it that way on purpose rather than by omission, by deciding that wall nodes do not slide;
  the rule above carries the reason. The same faceting owns the O-grid's NON-ORTHOGONALITY too
  (#93), not only the wall height: a facets-per-interval ratio that does not divide costs up to
  0.375° at the worst ratio.
  ~~**Nothing checks a bound edge's sample rate against its polyline.**~~ **CLOSED by #94**, which
  measures the cost and WARNS. **#95 then fixed the shipped geometry** — the far field at 320 facets
  — so 4 of that case's 8 edges stopped warning and the other 4, the body's, still do; nothing
  ENFORCES the ratio, and the warning is what speaks when a declared count moves off it. Two narrower holes
  replace it, both in the estimator rather than in the coverage: on a dividing ratio it
  over-predicts the even sampling (0.663° at 16.9° of turn on the C-grid airfoil), so a real cost
  on a STRONGLY CURVED non-dividing stretch can be masked by about 4% of the local turn and nothing
  shipped exercises that; and the facet count is the SUBPATH's, whose two end facets would be
  PARTIAL for a corner declared mid-facet — every shipped and fixture corner sits on a vertex, so
  the count is exact everywhere it has been measured.
  Why: `docs/design_notes/mesher.md`, "THE O-GRID's RESIDUE IS A SAMPLING RATIO, NOT A FROZEN WALL"
  and "A SAMPLE RATE THE POLYLINE CANNOT CARRY IS NOW SAID".
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
- **GATE 2 DOES NOT EXERCISE THE `.bnd` NAME -> SOLVER FLAG MAPPING.** Still true of GATE 2, and
  no longer true of the repo: `getPGrid` does not know `farfield` and defaults those faces to a
  no-slip wall, so both recorded runs wrote the flag into a `.bc.def` BY HAND. **#91 closed the
  "only the GUI does this automatically" half** — `services/pipeline_bc_derive.py` derives the
  table from the mesh's own patches for the HEADLESS hosts too, and
  `tests/test_pipeline_bc_from_mesh.py` gates the mapping token-by-token against getPGrid's own
  `getBCType`, which is the first automated coverage it has ever had. What is still hand-built is
  gate 2's own runs, and nothing from either is committed, so each remains a quotation and not a
  reproduction.
- **GATE 2 IS ONE OPERATING POINT, AND NOTHING RE-RUNS IT.** #57's acceptance run is M 0.2, Re 200,
  zero incidence, 100 iterations, `cfl 0.6`, every non-wall patch flag 1. "The solver runs" is all
  it claims — not convergence, not accuracy, and no pressure distribution is compared with
  anything. CI has no solver binary, so every recorded run is a dated quotation — but **this
  CHECKOUT does have one** (`solver/execute/unicones.eqn6.mac`,
  `solver/preprocess/getPGrid/work/getPGrid`), which #85 used and which corrects a "no solver tree"
  claim that had survived a review in `test_multiblock_weld_surface.py`.
- **NO RULE FILE'S GLOBS REACH `tools/`**, so the O-grid rule's own spacing law —
  `tools/PreProcessor/include/Spacing.hpp`, named in that rule — is unreachable from the tripwire
  table: a session that opens it is handed no rules at all. Pre-existing and NOT created by #89's
  split, which neither widened nor repaired it; recorded here rather than fixed, because that
  commit had to stay a move. It is the fourth instance of the shape the budget gate's own blind
  spot (c) tracks (`phi_quality.py`, `run_batch.py`, `CMakeLists.txt`), and the same one: the
  unreachable file is always the one OUTSIDE the package the rule's other modules live in.
