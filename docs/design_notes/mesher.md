# Mesher design notes (C++ core)

Long-form rationale extracted verbatim from `CLAUDE.md` on 2026-08-28, when that
file passed the 150k-char context limit and was condensed to its rules. Nothing
here was rewritten: this is the original prose, with its measurements, dated
acceptance runs, injections and named blind spots. `CLAUDE.md` carries the rule;
this file carries why it is the rule.

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

**`MESH_MODE` selects the generation path, and a parameter the active mode never
reads is NAMED** (`include/MeshMode.hpp` + `src/MeshMode.cpp`, in `hybmesh_pure`;
issue #49, the configuration surface of #48's multi-block path). Mode 0 is the
existing hybrid path and the DEFAULT, so the correct effect of the whole feature on
an existing case is zero — measured, not asserted: the nine golden cases were
captured from the pre-change binary (`git archive 25bd1cf` → build → capture with
`HYBMESH_GOLDEN_BIN`) and compare **9/9 SAME, worst deviation 0.000e+00**, with the
procedure recorded in `tests/test_mesh_mode_surface.py`'s docstring. Rules:
- **"Which parameters does this mode read?" is DATA, in one place.** Two macros
  declare it — the inert non-BL keys as `(KEY, Config member)` rows, and the four BL
  parameters that SURVIVE — and the 18 casualties are the declaration in
  `BLParams.hpp` minus those four, so a parameter added there is covered with no edit.
  Declaring the survivors rather than the casualties is deliberate: the next BL
  parameter is far likelier to be another corner knob than another wall-spacing one,
  so a new row gets the right answer by default.
- **"Set" means "differs from a default-constructed Config", never "the key appeared
  in the file".** The GUI writes nearly every key on every save, so the file-based
  reading would warn about all of them at once and mean nothing.
- **The GUI's half is `modes=` on each field's own spec**, not a second table — the
  same argument the `.dat` KEY already carries — and `test_field_spec_tables.py`
  check 14 compares the two **in both directions**, reading the C++ macros as text so
  its five injections can mutate them. One direction alone has a hole each way: a key
  the mesher warns about but the panel still shows is a control the user can set and
  watch do nothing, and a field the panel hides but the mesher still reads is a value
  silently frozen. Rows the mode does not read are hidden in the mesh panel AND in the
  **Edit-BL dialog**, which is where 17 of them actually live — hidden, never dropped,
  so switching the mode is not a silent edit of 17 values.
- **An invalid topology declaration refuses with `EXIT_ERR_TOPOLOGY` (8, token
  `TOPOLOGY`)** and exports nothing; `EXIT_ERR_INVERTED` (9, token `INVERTED`) is
  declared beside it for a mesh that generates but holds inverted cells, which will
  EXPORT anyway. Two codes rather than one because the caller's response differs: fix
  the declaration, versus look at the mesh. An **unknown** mode is refused by
  `validate()` rather than clamped to 0 — every other repair there has an obviously
  right fallback and a mode does not, so clamping would mesh the hybrid path for
  someone who asked for something else. (Until #50 that same code meant "the mode is
  not implemented yet"; `test_mesh_mode_surface.py` check 2 is now the **inverted**
  version of the one that pinned that sentence, and pins the parts the ticket
  actually promised — code 8, the machine-readable line, nothing written.)
- Three departures from #49's acceptance text, all recorded in `MeshMode.hpp`:
  `GMSH_NUM_THREADS` is warned about too (this path uses Gmsh nowhere, so the same
  argument covers it); so are `BL_MERGE_CONCAVE` and `BL_SMOOTHING_ITERS`, which are
  global-only settings outside the 22-row declaration and inert for the same reason,
  making **20** BL-ish names against the ticket's 18; and `SURFACE_MESH_SIZE` /
  `AUTO_SURFACE_SIZE` are deliberately NOT declared inert — #49 does not name them, and whether a surface size seeds
  default edge counts is a question the later tickets answer. `Config::meshMode`'s
  initialiser is the literal `0` rather than `MESH_MODE_HYBRID` because the parity
  gate resolves that initialiser to compare it with the GUI default and reads a
  literal; an enum name there would make one of the two sides stop being compared.

**The multi-block path is ONE pure entry point, and the adapter deliberately has no
seam** (`include/MultiBlock.hpp` + `src/MultiBlock.cpp`, in `hybmesh_pure`; the adapter
is `buildMultiBlockMesh` in `src/cli.cpp`; issue #50, the bring-up slice of #48's
second generation path). `hybmesh::buildMultiBlock(topologyJson, geoms, params)` parses
the topology document, resolves it, fills every block with structured quads, splits
them and returns nodes, blocks (with their logical i/j), flat cells, already-resolved
boundary edges, warnings as data and an optional error. Rules:
- **Parsing lives INSIDE the seam.** A separate "parse the document" entry point would
  have made half the behaviour internal; as it is, schema errors, count resolution,
  node positions, the diagonal split and the resolved BCs are all external behaviour of
  one function, which `tests/cpp/test_multiblock.cpp` drives with a topology STRING and
  no mesh at all. That test links `hybmesh_pure` and nothing else — measured with
  `otool -L`: only libc++ and libSystem — so the moment the module reaches for `Mesh` or
  gmsh it stops linking.
- **The adapter gets no seam, because it has no decisions.** Every boundary edge comes
  back as (node pair, BC name, source segment), and the adapter records each through
  the existing `recordBoundaryEdge` with a **synthetic carrier `Node`**: that write
  takes the whole source node because its convention is "an edge belongs to the segment
  of its starting point", and here the seam already resolved BC and segment per EDGE,
  so there is no starting point left to consult. Position-based classification is not
  used in this path at all — the declaration already contains the answer, and
  re-deriving it by proximity is how a curved inlet came to export partly as wall.
- **The split is ALTERNATING BY INDEX PARITY and it is the default**, correct from the
  first mesh rather than a later refinement: a single fixed diagonal imprints its own
  direction on a uniform structured region, and flipping with `(i + j)` needs no seed,
  so this path stays comparable run to run. `MB_SPLIT_QUADS 0` exports the quads for
  diagnosis and **says so**, because the solver's incenter reconstruction is undefined
  on quad cells and the grid converter's own slicer refuses a mixed mesh. The split
  happens in the MESHER, not the converter, so the mesh inspected in VTK is the mesh
  the solver integrates.
- **Logical i/j is retained rather than flattened**, because the diagonal rules are the
  only thing that reads it and flattening first would destroy it. `MbCell::block` is
  carried for the same reason: once the cells are a flat list there is nothing left to
  ask which block one came from.
- **Unknown JSON keys are REFUSED, not skipped.** A typo'd `"spacng"` that is ignored
  produces a mesh with the wrong node distribution and no symptom — the same failure
  class the inert-parameter warning exists to close. Strict now is relaxable later; the
  reverse is a breaking change. So is **a declaration that reaches nothing**: an edge in
  no block and a corner on no edge are refused by name.
- **What v0 does not do is refused BY NAME, never approximated**: an `on_geometry`
  corner, an edge `binding`, an `interface`/`cut` edge kind, a `blocks[].orientation`,
  and a second block. A corner placed *near* a geometry feature instead of on it is a
  slightly wrong mesh with no error, which is worse than no mesh. Each refusal names
  the later work it is waiting for. **SUPERSEDED for the first two**: `on_geometry`
  and `binding` are implemented by #52 (see "Boundary conditions are DECLARED"), so
  those two refusals are gone. The other three stand.
- **A block's orientation is the corner order of its own four edges**, declared as
  `[south, east, north, west]` with south/north running i-min→i-max and west/east
  running j-min→j-max; a deviation is refused with the edge, what it declares and what
  the convention needs. Inferring it would turn a mistake into a mirrored block, i.e. a
  mesh rather than an error. A **clockwise** corner ring is a WARNING and not a repair —
  silently re-winding would mean the mesh no longer matches the document that declared
  it. It is **refused** with the topology code, not exported under the inverted-cell
  one: that code is for a valid declaration whose GEOMETRY came out folded, which is
  worth looking at, while a backwards-wound ring is worth fixing and nobody wants the
  mesh either way. #51's gate is unaffected.
- **The boundary edges are ONE counter-clockwise walk**, matching `addTaggedLoop` and
  `buildDomainBoundary`. Measured, and recorded so nobody re-derives it: the direction
  does **not** reach the `.bnd` — `exportStarCD` takes a boundary face's node order
  from the cell that owns it, not from `edges` — so this is consistency for a reader,
  not a fix. The C++ test pins the CHAINING (each edge starting where the last ended,
  closing on the first), because a per-side emitter with one direction wrong still
  emits the right SET of edges and only the chain catches it.
- **Two departures from the ticket's literal scope, both deliberate and measured.**
  #50 asks only that the spacing-law header be on the include path; the schema
  accepts `uniform` / `geometric` / `tanh`, because a header on a path that nothing
  uses is the dead declaration this repo refuses elsewhere — what #55 owns is the
  RESOLUTION of wall spacing from `BL_INITIAL_THICKNESS` and friends, which is not
  here. And `Mesh::addTaggedEdge` touches three call sites on the EXISTING path,
  which #48 lists as out of scope; it is behaviour-preserving and that is measured
  rather than asserted (9/9 golden cases SAME at 0.000e+00, `.cel` and `.bnd`
  included).
- **The geometries argument is wired up although nothing binds to one yet**, so the
  geometry-binding work fills a parameter rather than changing the signature. (It
  did: #52 added fields to `MbGeometry` and changed no signature.)
- The decision layer gains `tools/PreProcessor/include` on its include path
  (**PRIVATE**: `MultiBlock.hpp` includes neither, so a test linking `hybmesh_pure`
  does not inherit it) for the bundled `json.hpp` and the existing `Spacing.hpp` — both
  pure arithmetic, and sharing the spacing laws avoids a second growth-rate solver.
  `generateGeometric` at ratio 1 IS the uniform law, so "uniform" is not a special case.
- **SURVIVING is not the same as READ, and the gap is a whole release long.** #49
  declares four BL parameters (`BL_INITIAL_THICKNESS`, `BL_GROWTH_RATE`, `BL_LAYERS`,
  `BL_USE_ANALYTIC_GEOM`) as surviving into this mode — and v0 reads **none** of them,
  because every topology edge declares its own count and spacing law. Declared
  survivors are exempt from the inert warning, so without a second list they would be
  the exact silent no-op the first list exists to prevent, wearing a declaration that
  says they work. `hybmesh::blSurvivorsUnread` names them in their **own** sentence
  (`does not read 'X' yet`), never the inert one (`never reads 'X'`): an inert value
  should be deleted and one of these should be kept, so a caller must be able to say
  them differently and the two lists must stay **disjoint** — pinned in
  `test_mesh_mode.cpp` check 6b and `test_mesh_mode_surface.py` check 4. Delete the
  function when the clustering law lands; `MeshMode.hpp` says so at the declaration.
- **The asymmetry #49 shipped is unchanged and is worth knowing**: `inertParamsSet`
  answers only for the multi-block mode, so `MESH_TOPOLOGY_FILE` and `MB_SPLIT_QUADS`
  set while `MESH_MODE 0` produce no warning. The GUI hides both rows in hybrid mode,
  so only a hand-written `.dat` reaches that gap. `SURFACE_MESH_SIZE` /
  `AUTO_SURFACE_SIZE` sit in a third position, recorded rather than closed: measured
  unread by this path (an explicit per-edge `count` is required), but whether count
  propagation seeds from them is #53's answer, so declaring them inert now would write
  that guess into a gate.
- **A geometry that will not load is a WARNING here, not a refusal** — the opposite of
  the hybrid path's answer and right for the same reason: there the geometry IS the
  mesh, here nothing in a topology can refer to one yet, so refusing would stop a mesh
  that does not depend on the file. Named, because an edge binding to it changes that.
- **`Mesh::addTaggedEdge(v1, v2, bc, segKey)` replaced the `addEdge` + two writes to
  `edges.back()` idiom** at all four call sites (the domain box, `addTaggedLoop`, the
  BL front, the multi-block adapter). Same argument as `recordBoundaryEdge` one level
  down: a BC and its source segment are one fact, and an idiom that writes them in two
  statements is two chances to write half an identity. Behaviour-preserving, measured:
  9/9 golden cases SAME at 0.000e+00 after the change.
- Gated by `tests/cpp/test_multiblock.cpp` (the decisions, through the seam),
  `tests/test_multiblock_surface.py` (the chain, through the real binary — and where
  the dated acceptance run is recorded), and **three new golden cases**
  (`mb_square`, `mb_square_quads`, `mb_graded`), whose topology writer
  `golden_mesh.py` IMPORTS from the surface test for the reason it already imports the
  duct geometries. Measured 2026-08-27: the nine existing cases **9/9 SAME, worst
  deviation 0.000e+00** against a baseline captured from the pre-change binary
  (`HYBMESH_GOLDEN_BIN`, `git archive cd29bb8`-style procedure recorded in
  `test_mesh_mode_surface.py`). **Acceptance run, same date**: `getPGrid` exit 0 on the
  21x21 example (441 vertices, 800 elements, 80 boundary faces, 80 BC flags), then
  `unicones.eqn6.mac -t mbv0 input.in` **exit 0**, last printed
  `Global Iteration count 90` at interval 10 with `num_half_iter 100` — i.e. 100
  iterations. Not a shape check written up as one.

**The quality report is the RULER, and it is built before the thing it measures**
(`include/MbQuality.hpp` + `src/MbQuality.cpp`, in `hybmesh_pure`; the banner and
the exit code are in `src/cli.cpp`; issue #51). Every multi-block run prints the
inverted cell count, maximum and mean non-orthogonality, the wall first-cell height
accuracy and the cell count, plus ONE machine-readable `HYBMESH_MB_QUALITY
cells=… inverted=… nonortho_max_deg=… nonortho_mean_deg=…
wall_first_cell_worst_rel=…` line — so the acceptance gate this instrument exists
for is a grep and not a prose parse. Rules:
- **Printed on every run, including a good one.** Three of the four numbers are the
  baseline the later elliptic-smoothing increment is judged against, and a baseline
  recorded only when something went wrong is not a baseline.
- **Its own module rather than more of `MultiBlock.cpp`.** It answers a different
  question — "is this mesh usable?" against "what does this document declare?" —
  and it is a pure function of a finished mesh, so half its checks hand
  `measureMbQuality` a mesh nobody parsed. Measuring a mesh must not require the
  mesh container, which is why it is on the pure side of the line.
- **Inverted is counted over the EXPORTED cells, and the test is PER CORNER, not
  the signed area.** A bow-tie quad can self-intersect with a POSITIVE shoelace
  area — measured: `(0,0) (3,0) (0,1) (2,1)` has area +0.5 and crosses itself, and
  the obvious area-based implementation calls it fine (injected, and it fails
  exactly that one check). For a triangle the per-corner rule REDUCES to the signed
  area, so it is one rule for both cell kinds. Counted over the exported cells
  because those are what the solver reads: the same folded topology reports 16 of
  32 triangles or 10 of 16 quads.
- **Non-orthogonality is measured on the STRUCTURED grid cells — each corner
  angle's deviation from 90° — and NOT on the split triangles.** Three reasons, the
  first being the ticket's own criterion. It comes from the corner positions
  directly, so a block that is strongly stretched but axis-aligned measures
  *exactly* zero, which no size-or-edge-length proxy can report — measured, through
  the real binary: a square graded geometrically at 1.5 asks for a first cell of
  2.030e-02 against a uniform 1.25e-01 and reports `0.000 deg` (the same trap the
  `[ Mesh Size Field ]` report had to avoid, where cell edges run ~15% long on
  stretched triangles). Second, it is the quantity elliptic smoothing moves;
  measuring the triangles instead would let the fixed diagonal — an artefact of the
  split that no smoother touches — dominate the number, so a grid that got worse in
  the way that matters could report an unchanged figure. Third, it is therefore
  independent of `MB_SPLIT_QUADS`, so the quads-for-diagnosis mode and the shipped
  triangles report the same grid quality. It is an ANGLE with a closed form, not a
  badness score: a parallelogram sheared by 1/2 reports atan(1/2) = 26.565° with
  max == mean. The blind spot is named rather than papered over — it says nothing
  about the shape of the split triangles, and a solver-facing skewness metric for
  those is a different instrument, not this one wearing another name.
- **A folded mesh is EXPORTED and exits 9; an invalid declaration exports nothing
  and exits 8.** It goes through the same `failExit` mechanism a failed boundary
  layer uses, so the difference between the two failure kinds is *where the code is
  set* and not a second way of stopping. `blSuccess` is deliberately left TRUE, so
  the VTK keeps its ordinary name: the `_er` suffix marks a PARTIAL mesh, and this
  one is complete — it is the cell shapes that are wrong, which is the thing the
  export exists to let you look at.
- **The wall request is published from the SEAM, never re-derived downstream**
  (`MbWallSpec` on `MbResult`). Only `buildMultiBlock` still knows the spacing
  laws: the requested first-cell height off a side is the FIRST INTERVAL of the
  edge running away from it, taken from the perpendicular edge at each of that
  side's two corners, and once the block is a grid of positions those laws are
  gone. Between the corners the request is the same linear blend in the logical
  coordinate that the transfinite fill itself uses. The height is a distance ALONG
  the grid line, not perpendicular to the wall; the two differ by
  cos(non-orthogonality), which is why this number and the angle are always
  reported together.
- **"ASKED FOR" IS NOT AN INDEPENDENT TARGET YET, and the figure must not be
  over-read** — the same class of gap #50 wrote down as "SURVIVING is not the same
  as READ", and it is recorded here for the same reason. #51's criterion asks "how
  closely the wall first-cell height matched what was asked for", and nothing in a
  v0 topology asks for a wall-normal height independently of the edge counts: the
  request is DERIVED from the same spacing law the fill reproduces, and the
  transfinite blend is exact on the boundary, so at a side's two END COLUMNS the
  achieved height IS the requested one identically. **A rectangle's 0.00% is
  therefore a tautology, not evidence the instrument works** — the first write-up
  of this entry presented it as evidence, and the test asserted it as "the first
  cell off each of them is what was asked for", which is the overclaim habit this
  file records against #25/#29/#37. What the number honestly measures is how far
  the INTERIOR drifted from what the two ends declare, which is exactly the
  quantity elliptic smoothing moves — so it is the right baseline under a narrower
  claim. The discriminating evidence is a block the blend distorts: a trapezoid
  measures 7.38%, the folded dart 25.41%. The independent target (a wall spacing
  asked for by `BL_INITIAL_THICKNESS` and friends) arrives with the wall-spacing
  resolution work; when it does, only the PUBLISHER in `buildMultiBlock` changes
  source and no reader of the report changes at all. Both halves are pinned rather
  than described: the test names the rectangle's zero AS a tautology, and check 7
  asserts that the trapezoid's two end columns reproduce their request exactly, so
  the whole deviation is interior.
- **"We did not measure" must not read as "it came out perfect", and that holds
  for ALL THREE measured figures.** `maxNonOrthoDeg`, `meanNonOrthoDeg` and every
  `worstRelError` (per wall, and the headline) are NEGATIVE when they could not be
  measured, never 0.0 — the same distinction `case_run_note` keeps between an
  unreadable convergence history and a genuine cold start, and the banner prints
  `not measured` rather than a percentage or `0.000 deg`. Two things worth knowing.
  The first version got this **right at the report level and wrong at the row
  level**: a wall whose request was not a positive length anywhere on it (a
  degenerate perpendicular edge) was still pushed with `worstRelError == 0.0` and
  dragged the headline to a flawless-looking 0.00% — found independently by BOTH
  review axes, which is the strongest signal either gives. And the row-level rule
  was then still **unguarded**, because the only test with no measurable wall
  declares no wall at all and so exercised the report's default instead: injecting
  the 0.0 default broke NOTHING until check 6b was written for it. Whether
  `buildMultiBlock` can currently reach a zero request is a separate question
  (a fully collapsed side is refused by the ring check), and the answer does not
  matter — `measureMbQuality` is a public pure function that accepts any
  `MbResult`, so a guarantee its header states must hold for every input it
  accepts.
- **The detector is proven to bite by a topology that folds, and that topology is
  ACCEPTED.** A dart — corners `(0,0) (1,0) (0.1,0.1) (0,1)` — winds
  counter-clockwise (signed area +0.1), so the clockwise-ring refusal does not
  fire; the ring is strongly non-convex at `ne` and the fill folds anyway. That is
  the whole reason there are two codes: a backwards-wound ring is a defect of the
  DOCUMENT and is refused, while this is a valid document whose interpolated
  interior came out folded and there is something worth looking at. The gate checks
  that no topology refusal is printed on that run, or its check 4 would be pinning
  a refusal wearing a second code.
- **All four sides are reported, because v0 cannot say which boundary is a viscous
  wall.** Every boundary edge is kind `wall` (interface and cut are refused by
  name), so a body surface is not distinguishable from a far field until boundary
  conditions come from the declaration. The publisher is gated on `kind` anyway, so
  that list gets shorter and no reader has to change.
- **The `[south, east, north, west]` convention is DATA, in one place**
  (`mbSideAxis` in `MultiBlock.hpp`). It was on its way to three encodings — which
  perpendicular edge a wall's request comes from, how to walk a side and step one
  line inward, and what to call it in a report — two of them `switch (side)`
  cascades over the same four values, which is the shape that lets one disagree
  with the others. Two facts derive all three: south and north run along i, and
  north and east sit at the transverse index maximum. One dedup was considered and
  DECLINED: `MbWallSpec` and `MbWallHeight` share `edgeId`/`requestedLo`/
  `requestedHi`, but they face opposite directions (one is the seam's declaration,
  the other a report row), the shared part is three fields copied adjacently rather
  than a fact that can be written HALF — which is what made `recordBoundaryEdge`
  and `JunctionDecision` worth merging — and nesting them would make a printed row
  read `w.asked.lo`.
- The folded topology is written by #50's OWN `write_topology`, extended with a
  `corners=` argument, rather than by a second writer — the reason that helper
  already gives for `golden_mesh.py` importing it. Its default is the `x1`/`y1`
  rectangle, so every existing caller is byte-identical.
- Measured behaviour preservation: the **12 golden cases 12/12 SAME, worst
  deviation 0.000e+00**, against a baseline captured from the pre-change binary
  (`HYBMESH_GOLDEN_BIN`, `git archive 050f2af` → build → capture there). No mesh
  moved; what is new is a report and an exit code.
- Gated by `tests/cpp/test_mb_quality.cpp` (9 groups, 53 checks, through the pure
  seam) and `tools/PreProcessor/tests/test_multiblock_quality_surface.py`
  (8 properties, 29 assertions, through the real binary, where the export-anyway
  and the two exit codes live). **The six injections are HAND runs, dated and recorded
  in the C++ test's own docstring with the checks each one broke — deliberately NOT
  written up as in-test injections**, because a C++ test cannot mutate the
  implementation it linked against the way the Python gates next door do; #37's
  entry above says that distinction must not be blurred, and the first write-up of
  this entry blurred it. What IS permanent is two **negative controls** that
  measure an injection's own premise inside the test: check 6 computes its
  bow-tie's shoelace area (`+0.5`, so an area test really would pass it) and check
  2 computes its own stretch ratio (~17x, so the zero angle really is a
  measurement). An argument in a comment decays; those two do not. Blind spots are
  named in each file's docstring; the sharpest is that nothing runs the solver or
  the grid converter on the folded mesh — that it is written is the claim, that
  anything downstream accepts it is not.

**Boundary conditions are DECLARED, and geometry is attached by ARC LENGTH**
(`include/MultiBlock.hpp` + `src/MultiBlock.cpp`, still the one pure entry point;
issue #52). A topology corner attaches to a source segment at a normalized
arc-length position (`kind: "on_geometry"`, `geom` / `seg` / `t`), a wall edge
declares the segment it lies on (`binding`), and every boundary edge generated
along that edge carries that segment's own condition and its (geometry, segment)
key into the export. The answer is in the declaration before a single node
exists, so **there is no tolerance anywhere in this chain** — which is the whole
point: the hybrid path resolves a boundary edge's condition by testing whether it
lies on a reference segment within one, and on a curved wall the drift off the
chord exceeded it and an inlet exported a band of wall at every junction. Rules:
- **Arc length, NEVER a point index.** The workflow is edit CAD, re-resample,
  re-mesh, and re-resampling changes the point count — so an index would silently
  relocate every attachment on each resample and produce a slightly wrong mesh
  with no error at all. Measured through the real binaries: one topology meshed
  against two real resamplings of one geometry (21 and 41 points) gives **identical
  `.vrt` node COORDINATES** (parsed and compared exactly — not bytes, since the file
  also carries node ids this path is free to number differently), and the negative
  control is what makes that a measurement rather than a coincidence: the point
  counts are chosen so **neither** resampling has a sample at **any of the four**
  attached positions, so no implementation that snapped a corner to a geometry point
  could have produced them.
- **`t = 1` means "where this segment ENDS", which is the next segment's first
  point only when there IS a next one.** On the last segment of an open polyline it
  is that segment's own final point, and that is stable under resampling for a
  different reason: the resampler pins every segment's endpoints, so a segment's
  last sample is a DECLARED endpoint and not a floating one. Measured 2026-08-28
  through the real binary — an open two-segment polyline resampled at 6 and at 11
  points per segment ends at `(1.0, 1.0)` both times — because a review read the
  unextended case as a place that moves with the point count, which would have been
  the "slightly wrong mesh with no error" this feature exists to refuse. It is not,
  and the semantics are now pinned rather than argued.
- **A segment's own points stop ONE POINT SHORT of where it ends, and the run is
  extended by one.** Measured against the real `surface_resampler`, not assumed: a
  joint shared by two segments is assigned to the **later** of them
  (`resSegId.back() = segId` in `tools/PreProcessor/src/main.cpp`). Without the
  extension, `t = 1` lands one resampling interval short of the segment's real
  end — i.e. at a place that MOVES under exactly the re-resampling this feature
  exists to survive. For the LAST segment of a **closed** loop the point to reach
  for is index 0, because `loadGeometry` has already dropped the duplicate closing
  point. Both are pinned, and injecting either breaks 12/13/15.
- **A trivial piece break at index 0 is not a second piece**, and reading it as
  one silently switched the closed-loop wrap off. Found by pointing the feature at
  a shipped geometry rather than only at fixtures: sidecars in this repo disagree
  about whether to record the break every polyline has at its first point (a
  resampled square writes `NPIECES 0`; `examples/geometries/square_cavity.dat.meta`
  writes `NPIECES 1 0`), so `pieceBreaks.empty()` was the wrong question and
  `multiPiece()` asks whether any break falls strictly inside.
- **A corner at `t = 0` or `t = 1` sits on a JOINT, which two segments both own,
  so a bound edge accepts it from either side** (`tOnSegment`). This is not a
  nicety and it was not in the first design: on a closed body **every** block
  corner is a joint whose two edges bind to *different* segments, so without it
  the canonical declaration — one block side per source segment — cannot be
  written at all, which the shipped cavity example is what surfaced. The
  equivalence compares the sidecar's own point INDICES, never two coordinates, so
  this is not a tolerance creeping back in through the corner; a position strictly
  inside a neighbouring segment is still refused.
- **A bound edge FOLLOWS the segment's polyline; it does not cut the chord.** Wider
  than the ticket's literal wording, and deliberate: "this edge lies on that
  segment" is false for a chord across a curved wall, which sits a sagitta off the
  body everywhere between its ends — the same drift, one layer up. One code path
  serves both, because an unbound edge's "polyline" is just its two corners, and
  that reduction is **bit-identical** rather than merely equivalent (the golden set
  measures it).
- **A geometry is named BY NAME** — exact match on the declared path, then a
  *unique* basename — and never by position in the loaded list. Same argument as
  the point index one level down: a binding that moves when `GEOM_FILE` lines are
  reordered is a silent relocation. An ambiguous basename is refused rather than
  resolved by order.
- **A label stays a LABEL.** The seam emits the sidecar's per-segment grouping
  label and `Config::resolveGroupBc` turns it into the physical BC type, exactly as
  on the hybrid path; the adapter merges the sidecar's `GROUP_BC` trailer into the
  config for it. Resolving inside the seam would put a second resolver in the
  chain, which is how the two came to disagree the last time. Gated end to end: the
  `.bnd` patch names are `inlet`/`outlet`/`wall` and never `g_bot`.
- **Position-based classification is still not used, and that is structural rather
  than asserted.** The adapter records every boundary edge through
  `recordBoundaryEdge` (unchanged from #50), and `classifyBoundaryBc` returns at
  its step 0 per-edge lookup, so `pointOnSegment` is never reached on this path.
- **A geometry that will not load is still a WARNING, and a declaration REFERRING
  to one is now an error** — the change #50 predicted at the exact line it
  predicted it. Same for a geometry with no readable `.meta`: it has no segments to
  attach to and is refused by name rather than falling back to "the whole polyline
  is segment 0".
- **Two warnings, both about getting the fallback when you asked for something
  else**: a document where no edge declares a binding (so every edge is on
  `BC_GEOM`), and a bound edge whose segment carries no label in its sidecar. The
  banner then prints one row per patch naming the segment it was read off, so
  "declared, not discovered" is visible in a run rather than only claimed.
- **`MbWallSpec` still reports all four sides, and the #51 note predicting it would
  shrink is NOT yet due.** Conditions do now come from the declaration, but "this
  side is labelled inlet" and "this side is a viscous surface whose first-cell
  height matters" are different questions; the gate stays `kind`, which is the
  declaration's own word for it.
- Gated by `tests/cpp/test_multiblock.cpp` checks 12-16 (through the pure seam,
  with geometry fixtures reproducing both sidecar conventions) and
  `tools/PreProcessor/tests/test_multiblock_binding_surface.py` (through the real
  `surface_resampler` AND the real mesher, which is where the sidecar format and
  the label resolution are really proven). **The seven injections are HAND runs,
  dated 2026-08-28 and recorded in the C++ test's own docstring with the checks
  each one broke** — the same split #51 established, because a C++ test cannot
  mutate the implementation it linked against. Two of them are recorded *because
  the first attempt did not bite*, and in both cases the fault was the injection:
  one picked an index and then interpolated by arc length within that span, which
  self-corrects to the right answer, and a build race (a rewritten source against a
  same-second object file) scored an injection that breaks seven checks as inert
  until the compiler output was checked for a recompile. Both are recorded as what
  HAPPENED during a hand run; **neither is a standing guard, because there is
  none** — a scratch script that rewrites `src/` and rebuilds is not something this
  repo ships, which is the same reason these injections are hand runs at all. Same
  family as scoring a crash as zero failures.
- **Two new golden cases, `mb_bound` and `mb_cavity`**, which is where acceptance
  criterion 8 lives: `mb_bound` is a block with three *differing* conditions built
  through the real resampler, and `mb_cavity` is the shipped example on the shipped
  geometry (documentation a user runs must be covered, per `_multiblock_example`'s
  own reasoning). Proven to bite rather than assumed: injecting "every boundary
  edge takes the config default" reports `{'inlet': 6, 'wall': 8, 'outlet': 6} ->
  {'wall': 20}` plus the grouping change, and reverting restores SAME. The existing
  **12 golden cases are 12/12 SAME, worst deviation 0.000e+00** against a baseline
  captured from the pre-change binary (`HYBMESH_GOLDEN_BIN`, `git archive 97905a8`).
- **Four things here are wider than the ticket's literal text, and each is a
  deliberate call rather than drift.** (1) The `[ Multi-block Topology ]` banner
  grows a row per boundary patch naming the source segment it was read off — the
  claim of this whole path is that a condition is declared rather than discovered,
  and a claim a run cannot show is one nobody can check. (2) `findGeometry` accepts
  a **unique basename** as well as the full declared path, so a topology need not
  repeat the config's path string; it fails SAFE, since two geometries sharing a
  basename make the short form ambiguous and that is refused rather than resolved
  by order. (3) The shipped example, its config and the `mb_cavity` golden case go
  beyond criterion 8's one differing-conditions case, because a new schema with no
  runnable example is not documented — and `examples/topology` being documentation
  a user runs is exactly why `_multiblock_example` exists. (4) Extra refusals (a
  `free` corner wearing `geom`/`seg`/`t`, a zero-length bound edge), which are the
  repo's own refuse-rather-than-approximate rule applied to new keys.
- **The adapter gained a summary, which is a real if small dent in #50's "the
  adapter has no decisions".** Grouping the boundary edges by (bc, geometry,
  segment) for the banner is ~15 lines of presentation in `src/cli.cpp`, reachable
  only through the Python surface test. It is PRESENTATION, not classification —
  it computes nothing the seam has not already resolved, and it changes no mesh —
  but the honest reading is that the adapter is no longer literally decision-free,
  and if it grows a second such block the grouping belongs on the pure side beside
  `measureMbQuality`. Recorded rather than argued away.
- **The blind spot, named rather than papered over**: the end-to-end
  re-resampling check uses a straight-sided geometry, where an arc-length position
  is EXACT under resampling and the node sets can be compared byte for byte. On a
  *curved* segment the polyline itself changes with the point count, so an attached
  corner moves by a chord sagitta — a discretisation limit of the geometry, not of
  the binding, and no check here claims otherwise. The curve-following half is
  pinned in the C++ test, where the geometry can be stated exactly.
- **What the shipped example cannot do, said out loud in the example itself**:
  `examples/geometries/square_cavity.dat` is an OPEN polyline whose last point
  stops one sample short of the seam, so its segment 3 does not reach the corner
  the block's south-west sits on and the west edge is deliberately left unbound
  (a straight chord, geometrically the same wall, carrying `BC_GEOM`). Binding it
  would be claiming something false.

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
its first member, and its history is the argument for the layer. `hybmesh::inertParamsSet` (`include/MeshMode.hpp`) joined it for the same reason: "which parameters does this mode never read?" is a decision over declarations, so `tests/cpp/test_mesh_mode.cpp` can prove the four surviving BL parameters SILENT — a negative that a test scraping the mesher's log would have to establish by absence. It was extracted from
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
- **`MultiBlock.cpp`**: The whole multi-block path behind one pure entry point — parse, resolve, fill (transfinite interpolation), split, and the already-resolved boundary edges the adapter records. Never throws; a malformed document comes back as an error string. See Configuration above.
- **`MbQuality.cpp`**: The multi-block quality instrument — inverted cells (per corner, over the exported cells), non-orthogonality (the corner angles of the structured cells), and the wall first-cell height against what the declaration asked for. Pure, total, never throws: an empty or half-built result is measured as what it is rather than refused. See Configuration above.
- **`Config.hpp`**: Single-header; parses `.dat` files into ~50 typed parameters
- **`GeomUtils.hpp`**: `Vector2D`/`Point2D`, segment intersection, normals, dot/cross products

