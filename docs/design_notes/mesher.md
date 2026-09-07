# Mesher design notes (C++ core)

Long-form rationale extracted verbatim from `CLAUDE.md` on 2026-08-28, when that
file was condensed to its rules. (The reason this line used to give — a 150k-char
context limit — is false; `CLAUDE.md`'s header block carries the measured behaviour
and keeps the superseded claim as a specimen. #60.) Nothing here was rewritten:
this is the original prose, with its measurements, dated
acceptance runs, injections and named blind spots. The RULES are in `.claude/rules/`
(moved there from `CLAUDE.md` by #62, loaded on demand): `mesher.md` for
configuration, the BL parameters, `MESH_MODE` the selector and the core C++, and
`mesher-multiblock.md` for the whole `MESH_MODE 1` path, which #89 split out of it.
Both point here, so this ONE note is the rationale for both. Which globs hand a
session which file is `CLAUDE.md`'s tripwire table, not an enumeration here — that
enumeration is what went stale four times in the files this note's own header used to
list. This file carries why it is the rule.

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

**Four diagonal rules, and why the randomized one is hash-based (#54).**
`MB_SPLIT_RULE` selects between alternating by `(i + j)` parity (0, the default and
what shipped first, so a case predating this key meshes exactly as it did), a fixed
forward diagonal (1), a fixed backward one (2) and a randomized rule (3) seeded by
`MB_SPLIT_SEED`. Both fixed directions exist rather than one, because "fixed" otherwise
means "whichever direction we happened to hard-code"; a region whose flow direction is
known has a right answer and it is not always the same one.

- **The randomized rule hashes the cell's OWN IDENTITY — block ID string, i, j, seed —
  and this is the property that is not optional.** A sequential generator makes every
  cell's diagonal a function of traversal order, so declaring one extra block anywhere
  reshuffles the diagonals of the entire mesh: "I moved one corner and the whole mesh
  changed" becomes the normal experience, and the golden comparator, which compares
  exported connectivity and therefore exactly what a diagonal decides, loses its
  baseline on every topology edit.
- **The block's declared ID, not its index in `MbResult::blocks`.** The ticket says
  "(block, i, j, seed)" and `MbCell::block` was already carried, which made the index
  the obvious reading — and the wrong one. An index moves when a block is declared
  AHEAD of an existing one, which is the same failure the sequential generator has, one
  step removed. `test_multiblock.cpp` check 26 therefore declares the extra block FIRST:
  an appended block leaves every existing index alone and so cannot tell the two hashes
  apart. Measured (injection H, 2026-09-03): hashing the index breaks that check and
  nothing else.
- **Written out rather than taken from `<random>`.** `std::mt19937` is specified bit for
  bit, but every DISTRIBUTION in `<random>` is implementation-defined, so
  `uniform_int_distribution<>(0,1)` may return different bits on libc++ and libstdc++
  from the same seed. A recorded seed that reproduces a mesh only on the machine that
  made it is worse than no seed, because it reproduces most of the time. The
  implementation is fixed-width unsigned arithmetic (FNV-1a over the id, then the
  lowbias32 finalizer), whose overflow is defined, so the answer is a function of the
  four inputs and of nothing else. Neither hash is cryptographic and neither needs to
  be: what is asked of them is that neighbouring cells do not correlate.
- **An unknown rule is refused twice, with different exit codes on purpose.**
  `Config::validate()` refuses it as a CONFIG error (fix the `.dat`), and
  `buildMultiBlock` refuses it for any other caller — never clamped, for the reason
  `MESH_MODE` records. That second door was very nearly the only one: injection N found
  that disabling the `.dat`-level refusal broke NOTHING, because every other gate for
  the rule went through the pure seam. `test_mesh_mode.cpp` check 5b exists because of
  that run.
- **A seed no rule reads is NAMED.** The seed is an ordinary config value, which is what
  carries it into the provenance sidecar with no wiring of its own — and is also why a
  seed set beside a rule that ignores it is a problem rather than a harmless spare: it
  lands in the record implying a reproducibility it had no part in. The seam warns.
- **`MB_SPLIT_*` and never `SEED_*`.** That prefix is already the refinement-seed
  namespace (`SEED_FILE`, `SEED_SIZE`, `SEED_RADIUS`, `SEED_MODE`), a local far-field
  sizing source with nothing to do with a random number. Two unrelated concepts under
  one prefix is how a user sets the wrong one.
- **The block's id had to BECOME unique.** `parseBlocks` refused a duplicate corner id and a
  duplicate edge id and had no check for a duplicate BLOCK id, which was harmless while nothing
  read one — and the moment the randomized rule hashed it, two blocks under one id were cut
  identically, a visible correlated pattern and exactly the bias the rule exists to break. Found by
  the SPEC review of this change, not by the implementation. Its injection (O) was first aimed at
  the wrong one of the three textually identical `prev.id == spec.id` loops, disabled the EDGE
  refusal instead, and the whole suite stayed green: that refusal had been unguarded since #50.
  Check 29 covers both, and the second one is a hole this ticket did not open and closed anyway,
  because three lines of test cost less than a ticket to remember it by.
- **The enum lives in `include/MbSplitRule.hpp`, not in `MultiBlock.hpp`.** The first version put it
  in the seam header and had `Config.hpp` include that — which the STANDARDS review flagged, rightly:
  `Config.hpp` is a header-only `.dat` parser included by `Mesh.hpp` and `BoundaryLayer.hpp`, so
  every one of those translation units would have gained `MbResult`, `MbBlock` and `GeomUtils.hpp`
  to reach four integers, and it inverts the coupling `MultiBlock.hpp` states as a rule two
  declarations further down (its parameters are a handful of values rather than a `Config&`,
  precisely so the decision layer does not know the file format). `MeshMode.hpp` already existed as
  that shape for `MESH_MODE` and is the precedent. The same review found the four-rule list written
  out by hand in BOTH refusal messages and the "is this the seeded rule" question asked at four
  sites; `mbSplitRuleList()` and `mbSplitRuleReadsSeed()` are one writer each.
- **What is NOT checked, named rather than implied**: the quality of the bit stream.
  Nothing asserts that the diagonals are well distributed — only that both appear, that
  the pattern is not parity's under another name, and that it is a function of the four
  declared inputs. A hash with a visible period would pass every check. That is
  deliberate: a distribution test over 12 cells asserts noise, and the property that
  actually matters — no direction imprinted on a uniform region — is what `MbQuality`
  measures on a real case.
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
  those two refusals are gone. **SUPERSEDED for two more**: the `interface`/`cut` kinds
  and a second block are implemented by #53 (see "Blocks are welded TOPOLOGICALLY").
  Only `blocks[].orientation` still stands.
- **A block's orientation is the corner order of its own four edges**, declared as
  `[south, east, north, west]` with south/north running i-min→i-max and west/east
  running j-min→j-max; a deviation is refused with the edge, what it declares and what
  the convention needs. Inferring it would turn a mistake into a mirrored block, i.e. a
  mesh rather than an error. **SUPERSEDED IN PART by #53**: a deviation in DIRECTION is no
  longer refused, because a shared edge carries one declared direction and serves two
  blocks whose frames need not agree — the south edge fixes the frame and the other three
  are traversed as the ring requires. A set of four edges that does not CLOSE a ring is
  still refused by name, which is the half of this argument that survives. A **clockwise** corner ring is a WARNING and not a repair —
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
  that guess into a gate. **#53's answer is NO**: a seed is a `count` on an edge, and a
  class with none is refused by name rather than falling back to a global mesh size. So
  the two remain read by neither path and declared inert by neither — recorded here
  rather than closed, because the argument for declaring them inert is now unblocked and
  is someone's call, not a leftover.
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
- **SUPERSEDED IN PART by #53**: the gate is the KIND, so an `interface`/`cut` side
  is not listed and a multi-block topology reports exactly its outer walls. Why the
  gate is `kind` rather than the BC label is unchanged.
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
- **SUPERSEDED IN PART by #53**, same as #51's version of this rule: the `kind` gate
  now bites, because an interior side is not a wall.
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

**Blocks are welded TOPOLOGICALLY, counts PROPAGATE, and an edge's kind is an
ENUM** (still the one pure entry point, `include/MultiBlock.hpp` +
`src/MultiBlock.cpp`; issue #53). A topology may declare any number of blocks. An
interior line is declared ONCE, as one edge of kind `interface` or `cut`, and both
blocks name it — so the k-th node on one side IS the k-th node on the other, and
node counts partition into equivalence classes the user seeds a few of.

- **Coordinate welding is not merely not preferred, it is UNAVAILABLE.** Wall
  spacing on a real case is around 1e-7 while far-field spacing is around 1e-1, and
  no single tolerance exists between those two scales — the same argument the
  iso-line tracer already rests on, which chains by mesh EDGE IDENTITY and never by
  welding coordinates. So welding here is allocation, not comparison: a corner gets
  one node because it is one declared corner, an edge gets its interior nodes once
  because it is one declared edge, and a block READS the node ids of its four sides
  instead of generating its own boundary. There is no distance in the chain to
  drift past, and check 23 of the C++ test is the negative control that says so at
  a separation of exactly zero: two corners declared at the SAME coordinates under
  different ids stay two nodes, and the run reports three coincident pairs.
- **Only the block INTERIOR is interpolated now, and that is a measured behaviour
  change.** Transfinite interpolation is exact on the boundary in the mathematical
  sense, but "exact" there means it reproduces the side to within the rounding of
  one subtraction — `coons` at u = 0 computes `(X + west[j]) - X`. A shared edge has
  to be ONE curve rather than two curves that agree, so the side's own
  discretisation is the definitive answer and the blend is asked only about the
  inside. **Measured**: `mb_graded` (14 of 221 nodes) and `mb_bound` (8 of 35) move
  by **1.11e-16**, one ULP, on the boundary nodes of their non-uniformly spaced
  edges; the other twelve golden cases are bit-identical. The new value is the exactly
  discretised one and the old was the ULP off. Recorded because the golden
  comparator reports that change as `worst 9.167e-01`, which is an ARTEFACT of how
  it pairs nodes: it sorts both node lists and zips them, so a 1-ULP shift that
  splits one x-column into two groups offsets the pairing by two and the reported
  magnitude becomes meaningless. The true figure above was measured by set
  difference. The comparator was left alone — it correctly said DIFF — but do not
  read its magnitude on a case whose node set changed membership.
- **Two edges are forced to carry the same count when they are OPPOSITE SIDES of
  one block, and there is no second rule for an interface.** A shared edge is one
  declared edge that two blocks both name, so that single relation propagates
  across blocks by itself. `count` therefore became a SEED rather than a
  requirement (a behaviour change to the schema: a document that declares every
  count still reads identically).
- **The COUNT propagates and the SPACING LAW does not.** They are different facts:
  a wall edge legitimately clusters toward the wall while the interface in its own
  count class stays uniform, and forcing the law across a class would silently
  redistribute an edge nobody edited. Pinned in C++ check 18, and demonstrated in
  the shipped example (`v00` is geometric at growth 1.3, `v10` and `v20` in its
  class are uniform).
- **A conflict is refused with both edges, both counts, AND the chain**, which is
  the acceptance criterion and not a nicety: on a topology with dozens of edges the
  two conflicting declarations need not be anywhere near each other. Each union is
  recorded as a link, and the report is a BFS path rendered a block at a time
  (`'w' and 'm' are opposite sides (west / east) of block 'b0'`). The C++ and Python
  cases both put the two seeds TWO blocks apart on purpose — a one-block conflict
  would let a report that names no chain at all pass the check.
- **A class with NO seed is refused naming every edge in it.** Picking a default
  would decide the whole mesh density from a number nobody wrote down.
- **The kind is a real `MbEdgeKind`, declared with its names beside it.** It shipped
  as a validated `std::string` for one commit — compared against a literal at six
  sites, and published out of the seam as a string a reader had to match by hand —
  which the code review caught against this note's own "enum" wording.
  `mbEdgeKindName` sits beside it in the same shape `mbSideAxis` already uses, so
  the parser, every refusal message and the banner read one set of four words.
- **The three kinds decide three things, and NOT any arithmetic.** How many block
  sides the edge may be (`wall` exactly one, `interface`/`cut` exactly two, refused
  by name with the offending blocks); whether it may declare a `binding` (a `wall`
  only — an interior line in the fluid has no source segment to lie on, and
  accepting one would make the kind and the binding two statements of one fact);
  and whether it is exported as a boundary face carrying a BC (a `wall` only, and
  it is also the gate on `MbWallSpec`). What the kind does not yet decide is any
  number: an `interface` and a `cut` weld identically, because with node identity
  shared there is nothing left for a second rule to do. **Said out loud rather than
  dressed up**: the distinction lives in the declaration, the validation and the
  report (`MbResult::sharedEdges`, and a `Cut '<id>'` row in the banner), and that
  is what makes a later divergence — a periodic cut, a non-matching interface — a
  change rather than a rewrite. The kind is still never INFERRED from whether a
  binding is present, which is the inference that would file a wake cut as an
  ordinary interface.
- **A block's frame comes from its own declaration, and this REVERSES #50's rule.**
  #50 refused any side not declared in the convention's direction, arguing that
  inferring one would produce a mirrored block. That rule cannot survive welding: a
  shared edge is ONE edge with ONE declared direction, named by two blocks whose
  logical frames need not agree about which way it runs, so requiring the
  convention in every block makes a whole class of topology undeclarable. What
  holds now: the block's i direction is its **SOUTH** edge's own declared
  direction, and the other three sides are traversed in whichever direction closes
  the ring. Nothing is inferred by that — the frame is fixed entirely by the south
  edge plus which corners the other three touch — and a set of four edges that does
  not CLOSE a ring is refused by name, which is where #50's argument still applies.
  The clockwise-ring refusal is unchanged. C++ check 9 is the **inverted** version
  of the one that pinned the old refusal, and it asserts the block is not MIRRORED
  as well as accepted.
- **A ring can also close onto three corners**, so the four corners are checked
  pairwise distinct AFTER the ring is matched and not instead of it. Reachable, not
  hypothetical: two distinct edges over the same corner pair make the block's j-max
  corner its own i-max corner and every match above succeeds. The first version of
  that check was unreachable through the obvious document, which is how the case
  was found.
- **The four sides meeting at four SHARED corner NODES is checked, not assumed**,
  and checked before the boundary writes overwrite one with the other. It looks like
  a tautology after the ring match and is not: it is the check that caught the
  injection that dropped the per-block reversal, in both the C++ and the Python
  gate.
- **The adapter's banner grew two more presentation rows** — which counts were
  propagated rather than declared, and one row per shared line naming its kind and
  the two block sides. Same argument #52's patch summary got: propagation is the one
  place on this path where the mesh is decided by something the user did not write
  down, so a run that cannot show it is a run in which a propagation defect reads as
  a design choice. The dent in #50's "the adapter has no decisions" is unchanged in
  kind, and is recorded there.
- **The gates.** `tests/cpp/test_multiblock.cpp` checks 17-23 (the decisions,
  through the pure seam: welding as node identity, propagation as data, the conflict
  chain, the three kinds, the rotated neighbour, and the coincident-but-separate
  negative control) and `tools/PreProcessor/tests/test_multiblock_weld_surface.py`
  (the chain, through the real binary), plus the `mb_hgrid` golden case on the
  shipped `examples/topology/hgrid_blocks.json`.
- **The Python gate measures CONFORMITY on the exported files** rather than arguing
  it: every interior edge of the triangulation shared by exactly two cells, every
  boundary edge by exactly one, the boundary set equal to the `.bnd` face for face,
  and one connected component by shared-node identity. That is the property the grid
  converter needs and the one a welding defect breaks.
- **The injections are HAND runs, dated 2026-08-28**, for the reason #51 and #52
  record — a C++ test cannot mutate the implementation it linked against. Each patch
  was applied to `src/MultiBlock.cpp` alone, rebuilt, and run against both gates,
  with a control run confirming a clean tree passes:
  - A: every side emitted as a boundary (the kind not honoured on export) -> 1 C++
    check. **The Python gate initially caught NOTHING**, and that is the useful
    finding: the `.bnd` writer derives its faces from cell connectivity ("used by
    exactly one cell"), so an interface wrongly RECORDED as a boundary edge never
    reaches that file. A check on the mesher's own `Boundary Edges (BND)` count —
    which is `mesh.edges` — was ADDED for it, and then bites. A check was added, not
    corrected: the gate never covered that side.
  - B: no welding, every block generating its own boundary nodes -> 5 Python checks
    (4 components, 187 nodes, 72 faces, coincident nodes, a boundary face on the
    shared line) and 8 C++ checks.
  - C: the per-block reversal dropped -> the shipped example REFUSED (10 Python
    checks) and 2 C++ checks, both through the shared-corner-node invariant.
  - D: the conflict reported without its chain -> 1 Python and 1 C++ check, i.e.
    exactly the acceptance criterion and nothing else, which is what a check with
    one job should do.
- **THE ACCEPTANCE RUN AGAINST THE SOLVER IS OUTSTANDING and the gate says so.**
  This checkout carries no solver tree, so neither `getPGrid` nor `unicones` has
  seen a four-block grid; #50's dated run covers the single-block case only. What
  the Python gate pins instead is the SHAPE the converter reads, which is not a
  substitute for the converter accepting the file. #26 is why that distinction is
  written down rather than softened.
  **SUPERSEDED 2026-09-04 by #55, and the PREMISE was wrong, not just the status.**
  This checkout does carry a solver tree — `solver/preprocess/getPGrid/work/getPGrid`
  and `solver/execute/unicones.eqn6.mac` are both present, and #55's four-block O-grid
  went through both (exit 0 / exit 0, 100 iterations). Kept rather than deleted, as a
  specimen: the claim was an assertion about the working tree that nothing in it ever
  checked, and it survived a review round and a rule-file compression in that form. The
  work it blocked was one `ls`.
- **Other blind spots, named**: nothing anywhere welds along a BOUND edge (one that
  follows a geometry), in either gate; nothing has more than four blocks; and a
  block welded to ITSELF is still not expressible — `parseBlocks` refuses an edge
  named twice in one block, which is right for this fill (a transfinite map over
  four sides has no answer for a self-adjacent block) but means an O-grid seam
  cannot be declared as one edge.
- **THE CODE REVIEW ROUND, 2026-08-28, recorded because three of its findings were
  real and one of them was about a rule this very note quotes.** Standards found a
  second copy of the four side names (`kSideName[4]` in `MultiBlock.cpp`) while
  #51's rule — restated a few hundred lines above — is *"the `[south, east, north,
  west]` convention is DATA, in one place (`mbSideAxis`)"*. The comment above the
  array ADMITTED the split ("the two are indexed identically"), which is the shape
  of a rule being talked around rather than followed; it is now a one-line
  `sideName(k)` reading `mbSideAxis`. It also found that "the edge kind is an ENUM"
  was false of the type — a `std::string` compared against a literal at six sites,
  and published out of the seam as a string a reader had to match by hand. Rather
  than weaken the prose, `MbEdgeKind` + `mbEdgeKindName` now exist in the header in
  the `mbSideAxis` shape, `MbSharedEdge::sideA/sideB` became `MbSide` (which
  removed a cast in `cli.cpp`), and the parse maps the four words once. Behaviour
  preserving, measured: 15/15 golden SAME at 0.000e+00. And it found four rules
  this change left stale in CLAUDE.md and here (*"All four sides are reported"*,
  *"`MbWallSpec` still reports all four sides"*, *"the other ten golden cases"* —
  it is twelve — and `golden_mesh.py`'s *"over 9 mesher cases"*, now 15) while the
  same diff correctly marked the orientation rule SUPERSEDED, so the omission was
  inconsistent with its own practice. All four are fixed.
- **The Spec axis's most valuable finding was a CONSEQUENCE, not a defect**:
  refusing a `binding` on an interface/cut makes an interior line a straight chord,
  so *"a curved interface — the natural BL/far-field seam for #55 — is
  undeclarable"*. Kept, because the alternative is a binding whose condition half is
  silently ignored, and the refusal message now names the cost and the work it waits
  for. Its other two scope notes (the two banner blocks, and `MbWallSpec` narrowing)
  are recorded as deliberate above.
- **Structural findings acted on and DECLINED, both stated so neither reads as an
  oversight.** Acted on: `buildMultiBlock` had grown to six inline phases over ~700
  lines, and the two that RESOLVE the parse are now file-local functions in the
  module's own idiom (`resolveBlockFrames`, `resolveEdgeCounts`), taking it to 571.
  Declined: cutting the per-block fill out too would mean handing it `r`, `edges`,
  `frames`, `eNodes`, `params` and `bc` — the wide-signature-over-a-narrow-dependency
  shape `classifyJunctions` was extracted to escape, so the length is recorded rather
  than traded for a worse interface. Also declined: `(block, side)` travelling as
  four fields on `MbSharedEdge` is a Data Clump whose type is already born privately
  as `Use`, and `MbWallSpec` carries the same pair — one shared `MbBlockSide` would
  ripple into `MbQuality.cpp` and its 53-check test for a naming win, and #51 already
  declined a related dedup on grounds of its own. And three id-to-thing linear scans
  coexist (`edgeIndexById`, `cornerById`, the string-keyed `uses`); they answer
  different questions and the topologies are small, so this is noted, not merged.

**A circular O-GRID: curved arcs, a ring that closes, and wall clustering SOLVED for**
(`include/MultiBlock.hpp` + `src/MultiBlock.cpp`, still the one pure entry point;
`tools/PreProcessor/include/Spacing.hpp` for the law; issue #55). The first mesh from this
path a CFD engineer would want, and the first multi-block grid of more than one block to
reach the solver.

- **ONE of the ticket's three capabilities had ALREADY SHIPPED, and saying so was the
  first thing this work did.** #55 lists curved projection, the wrap-around class and the
  distribution law as landing together. Curved projection for a WALL edge is #52's
  `binding` — a bound edge follows its segment's polyline and does not cut the chord —
  and it had been gated since 2026-08-28. What #55 actually added there is a geometry
  worth binding to: two circles, shipped with their sidecars. The remaining gap is a
  curved INTERFACE, which #53 refused by name and which this ticket did NOT need: a
  single-ring O-grid has no interior line that should be curved. It stays refused, and
  the refusal still names the work it waits for.
- **THE DEFAULT DISTRIBUTION LAW IS `tanh`, and the reason is structural rather than
  aesthetic.** An edge's node count can be decided FOR it by propagation from elsewhere
  in the topology, so the law must absorb a count it did not choose. `tanh` is written in
  the normalized parameter and takes the count as an argument, so re-seeding a class
  re-solves the clustering; a "first N layers geometric, then uniform" formulation
  changes MEANING when N is externally determined, which is exactly what propagation does
  to it. **The default could be changed at all because tanh at delta 0 evaluates the same
  expression as the uniform law** (`L * i / (n - 1)`), which C++ check 30 asserts as BIT
  equality against an explicitly-`uniform` document rather than as "roughly uniform".
- **The wall spacing is asked for as a LENGTH and SOLVED for, never approximated.**
  `wall_ends` names an end of an edge as a wall end and takes the run's
  `BL_INITIAL_THICKNESS`; `ds_start` / `ds_end` give a number and beat it. The existing
  boundary-layer parameter names rather than aliases, because the physical quantity is
  identical and two names for one quantity is worse than one name that reads oddly in a
  mode with no boundary-layer stage (#48's own decision, user story 13). `geometric` with
  no `growth` takes `BL_GROWTH_RATE` the same way.
  - **`Spacing::generateTanhStart` / `solveTanhStartDelta` are NEW; the symmetric pair
    was the wrong shape.** `generateTanh` clusters BOTH ends equally, and an O-grid
    radial runs from a viscous wall to the far field — spending the far-field end's
    points at the wall spacing buys nothing. The one-sided law is
    `u = 1 + tanh(d(xi - 1))/tanh(d)`, monotone in xi so the map cannot fold, and its
    delta is found by the same bisection `solveTanhDelta` already used, for the reason
    that function records: a boundary-layer distribution is specified BY its first cell
    size.
  - **HOW EXACT, measured rather than asserted: 1.000e-12 relative on a 1e-4 first cell,
    and the bound is DERIVED.** A node is placed as `p0 + (p1 - p0) * f` along an edge of
    length 1, so its rounding is ~eps of the EDGE, not of the first cell; a cell of
    relative size 1e-4 therefore lands within ~eps/1e-4 = 1e-12. C++ check 31 asserts
    1e-9, three orders looser so a different libm cannot flake it.
  - **What is REFUSED rather than half-honoured**, each by name: two DIFFERENT heights at
    the two ends (the two-sided stretching function this release does not have — refused
    rather than silently honouring one of the two numbers with the symmetric law); a wall
    spacing on `uniform` or `geometric`, which cannot solve for one; a raw `delta`
    beside a spacing, which is two answers to one question; a non-positive height; a
    `wall_ends` value that is not start/end/both; a `growth` on a non-geometric edge; and
    a wall end with no height anywhere, which names `BL_INITIAL_THICKNESS` as the config
    key that would supply it. Equal heights at BOTH ends are accepted, which is what
    makes the first refusal about the DIFFERENCE and not about declaring two ends.
  - **A request the edge could not honour is SAID.** The solver returns "uniform" when
    the requested cell is at or coarser than what the count already gives — right
    arithmetic, wrong silence — so the seam compares what the edge actually PRODUCED
    against what it asked for and warns. Measured against the produced nodes rather than
    re-derived from the law, so a future law that misses its target is caught by the same
    line.
- **THE BLENDING COORDINATE HAD TO CHANGE, and nothing asked for it — the acceptance
  criterion did.** The classic Coons map blends with the LOGICAL index `i/(ni-1)`. On a
  rectangle that IS the arc-length fraction and the map is exact either way, which is why
  the straight-sided release never noticed. On an annulus sector it is not: the
  south-to-north term walks from the wall to the far field linearly in the index while
  the radial edges cluster their nodes at the wall, so the first interior column sits
  where a UNIFORM grid would put it.
  - **Measured, out of tree, before a line was written** (90-degree sector, 41 radial
    nodes, wall spacing 1e-3, r = 0.5 to 10): achieved first cell **7.03e-2 against a
    requested 1.0e-3 — 6927% off**. More blocks do not fix it: 3168% at six sectors,
    1800% at eight, **806% at twelve**. So "declare more blocks" was ruled out by
    measurement rather than by taste.
  - **With the boundary's own normalized arc length as the blending coordinate the same
    sector reproduces the polar grid EXACTLY** (measured 0.000%), and the algebra says
    why: the two u-terms sum to `r0 + u*(R - r0)`, which is the radius the clustered
    radial edge has already put there, so the (1-v) and v terms cancel against the corner
    correction and the answer is `r_i * dir_j`.
  - **The two facing curves are AVERAGED**, the standard choice and the only one that
    treats the block symmetrically when its opposite sides carry different laws; a
    degenerate side falls back to the logical index rather than dividing by zero; and both
    ends are pinned to exactly 0 and 1 so a block corner blends as a corner.
  - **What it cost the existing set: nothing, measured.** Five multi-block cases were run
    against a binary built from HEAD by `git archive`, and the worst node MOVEMENT was
    **6.7e-16** (`mb_hgrid`), 4.5e-16 (`mb_graded`), 1.1e-16 (`mb_bound`), 0.0 on
    `mb_square` and `mb_cavity` — last-bit rounding, not behaviour. `golden_mesh.py`
    nevertheless reported three DIFFs, which is the node-SET-membership artefact this
    note already records under #53: two nearly-equal coordinates swapped rank in the
    lexicographic sort and every cell's canonical rank moved with them. The baseline was
    re-captured, and 17/17 are SAME against it.
- **`MbWallSpec` NOW PUBLISHES THE DECLARATION, which is the change #51 predicted.** That
  note said the request was DERIVED from the same law the fill reproduces, so a
  rectangle's 0.00% was a tautology, and that when an independent target arrived **only
  the PUBLISHER would change**. It did: the request is the perpendicular edge's own
  `ds_start`/`ds_end` at the end that touches the wall, read through `f.rev[]` because the
  block traverses the edge in its own frame. `MbQuality.hpp`, `MbQuality.cpp` and every
  reader are untouched. An edge that declares nothing still publishes the produced
  interval, so a topology that never asks for a height keeps the figure #51 defined —
  which is also C++ check 34's negative control.
- **The shipped case, and what it measures.** `examples/topology/ogrid_circle.json` +
  `config/multiblock_ogrid.dat`: four blocks, each 49 x 25, an r = 0.5 body inside an
  r = 10 far field. Each block's i runs OUTWARD (south and north are two consecutive
  radials) and its j runs anticlockwise (west the body arc, east the far-field arc) —
  the frame in which the corner ring winds counter-clockwise, which the orientation rule
  requires. **The four radials are ONE equivalence class that WRAPS**: q3's north is the
  edge q0 declares as its south, so one `count` is declared and three are propagated, and
  the last block welds back to the first by node identity with no tolerance. Measured on
  the shipped files: **0 inverted cells**, max non-orthogonality **2.25 deg**, mean 1.875,
  wall first cell **0.08% off** what was asked for.
  - **That 0.08% is the stored polyline's FACETING, not the law**, and the negative
    control is the measurement: the same case on a 10x finer pair of circles measures
    **0.0007%** (and max non-orthogonality falls to 1.881 deg). It is also scale-free —
    0.0812% at `BL_INITIAL_THICKNESS` 1e-3, 1e-5 AND 1e-7 alike — which is what an
    angular artefact looks like and a law error would not.
  - **Re-seeding the ring does not move the spacing**: radial count 25 / 49 / 97 all give
    0 inverted and the same 0.0812%. That is acceptance criterion 9 and the property the
    tanh default exists to protect, measured on the one class where three of the four
    edges never chose their own count.
- **THE SOLVER ACCEPTANCE RUN, 2026-09-04 — and it CORRECTS a fact this note recorded.**
  #53's entry says the four-block acceptance run is outstanding *"because this checkout
  carries no solver tree"*. It carries one: `solver/preprocess/getPGrid/work/getPGrid`
  and `solver/execute/unicones.eqn6.mac` are both present and both ran. getPGrid exit 0
  (4704 vertices, 9216 elements, 192 boundary flags); unicones exit 0, last printed
  `Global Iteration count 90` at `print_convg_per_niter 10` with `num_half_iter 100`,
  i.e. 100 iterations by the arithmetic `services/case_run_note.iteration_span` uses.
  Quoted in full in `tools/PreProcessor/tests/test_multiblock_ogrid_surface.py`.
  - **One finding from that run, recorded rather than fixed here**: getPGrid does not
    know the patch name `farfield` and defaults those eight patches to a no-slip wall,
    warning each time. That is getPGrid's own token list — the GUI maps the name in
    `services/bnd_io._NAME_TO_FLAG` and writes the flag into the `.bc.def`, which is what
    the acceptance run did by hand — so a GUI-driven run never sees it. Not chased,
    because the mesher's job ends at the patch NAME and the flag is the solver panel's.
- **BL_INITIAL_THICKNESS and BL_GROWTH_RATE leave `blSurvivorsUnread`.** #49 declared four
  survivors and v0 read none; two are now real inputs, so they must be SILENT — warning
  that a value does nothing while the mesh is being built from it is the one wrong answer
  that pair of lists can give. The other two stay unread and stay named: **BL_LAYERS**
  because node counts here are declared and propagated and a class with no seed is
  refused BY NAME (defaulting one from a BL parameter would undo that deliberately), and
  **BL_USE_ANALYTIC_GEOM** because a bound edge follows the resampled polyline rather than
  an analytic curve. A second macro `HYBMESH_MULTIBLOCK_BL_READ` carries the split rather
  than shortening the survivor list, because the two lists answer different questions: the
  GUI shows a row when a parameter SURVIVES, and the run stays quiet when it is READ.
- **THE CODE REVIEW ROUND, 2026-09-04, and BOTH AXES FOUND THE SAME DEFECT INDEPENDENTLY.** The
  "you asked for a spacing you did not get" warning compared the produced CHORD against an
  ARC-LENGTH request at `1e-9` relative. A bound edge follows a POLYLINE, so a first interval
  spanning several facets has a chord shorter than the arc: Standards reasoned it out from the two
  measures, Spec reproduced it (`ds_start: 0.03` on a bound arc reporting 0.029995), and both noted
  the message then blames the NODE COUNT for the geometry's own faceting — advice that would send a
  user to re-seed a class that was never the problem. Reproduced here at 0.05 -> 0.049978. Fixed by
  publishing the achieved end intervals from `discretise`, which is the only scope holding both the
  positions and the measure they are in, so the two sides of the comparison are the same quantity
  and the 1e-9 tolerance means something again. **Gated by check 36 WITH a negative control** (a
  genuinely coarser request must still warn, or the check passes on a dead warning), and the fix
  verified by re-injecting the chord measurement: check 36 goes red reproducing 0.049978 exactly,
  and the restore passes.
- **Three more findings acted on, none of them behaviour.** (1) `EdgeSpec::law` was a
  `std::string` compared at EIGHT sites — the exact shape `.claude/rules/mesher-multiblock.md`
  already refuses
  for `MbEdgeKind` ("not a string compared at six sites — it was the latter for one commit, and the
  review that caught it..."), so Standards was citing the repo against the diff. It is now a
  file-local `SpacingLaw` enum with `spacingLawName` / `spacingLawList` / `parseSpacingLaw` in the
  `mbSideAxis` shape, and every refusal builds its accepted list from that table. File-local rather
  than in its own header, which is where `MbSplitRule` had to go: this never leaves the seam.
  (2) `solveTanhStartDelta` was a verbatim copy of `solveTanhDelta`'s bisection, and each law's
  expression existed twice (generator and solver) — so a change to one would silently make the
  solver target a curve the generator does not draw. One `solveClusterDelta` over a position
  function now, with `tanhBothPos` / `tanhStartPos` as the single home of each expression.
  (3) The "which end" ternary was at three sites and the third INVERTS it against the block's
  frame; ends are now indexed by an `EdgeEnd` and the inversion is one XOR against `rev`.
- **Two findings ANSWERED rather than acted on, recorded so neither reads as an oversight.**
  Spec called `ROOT_BUDGET` 33,500 -> 34,000 unnecessary because "the gate still passed". It did
  pass — check 7 holds the VALUE, and blind spot (c2) of that gate says in as many words that the
  DERIVATION is deliberately unchecked and that the rule at the constant "asks whoever edits the
  root" to re-derive it. This work edited the root, which fell to 33,304 and left 196 of slack
  against a documented band of (500, 1000] — the shape where a typo fix must also edit the gate.
  #79 hit the same thing at 481 and re-derived by hand; this is that precedent, not a loosening.
  Spec also read "topology edges project onto curved geometry" as partly delivered because nothing
  projects onto an ANALYTIC curve. The acceptance criterion is "wall-adjacent edges follow the
  circle, not its chords", which is met at 8.6e-5 against the 1.46e-1 a chord gives; the analytic
  half is named as a blind spot in three places and is what `BL_USE_ANALYTIC_GEOM` waits for.
- **Departure from #48's schema sketch, now recorded.** That sketch wrote
  `"spacing": {"law", "initial", "growth"}`. `initial` does not exist here and is refused as an
  unknown key: a single `initial` cannot say WHICH end clusters, and one-sided clustering is the
  point — a wall-normal edge clusters at the wall, not at the far field. Hence `wall_ends` /
  `ds_start` / `ds_end`. Undeclared until the Spec axis asked for it, which is the same omission
  #53's review caught (a change that marked one rule superseded and left four others stale).
- **The gates.** `tests/cpp/test_multiblock.cpp` 30-36 (the default law as bit equality,
  the solved height at three counts, the global and its per-edge override, the wrap-around
  ring, the published request with its negative control, and seven refusals);
  `tools/PreProcessor/tests/test_multiblock_ogrid_surface.py` (8 groups on the SHIPPED
  files, including the conformity measure #53's gate defined); and the `mb_ogrid` golden
  case. The surface gate also checks the two shipped geometries against their ONE
  generator, `write_circle`, rather than trusting them — a hand-edited `.dat` whose
  `.meta` still describes the old point set is a mesh with corners on the wrong segments
  and no error at all.
- **Blind spots, named.** Nothing projects onto an ANALYTIC curve, so "follows the circle"
  is measured against the polyline's own vertices and the 0.08% residue is that faceting.
  A curved INTERFACE is still undeclarable, so the shipped O-grid is a single ring rather
  than a boundary-layer ring inside a far-field ring. The two-sided stretching function
  with different heights at each end does not exist. And the arc-length blending's
  magnitude was measured out of tree: no gate re-measures the 6927%, only its consequence.

**A four-block C-GRID around a NACA 0012: a cut, a four-way corner, and a gate that bit
where nobody was looking** (`examples/topology/cgrid_naca0012.json` +
`config/multiblock_cgrid.dat`, still the one pure entry point; issue #57). The v1 target of
the multi-block feature: the first mesh from this path that is a CFD grid rather than a
demonstration of one.

- **NOT ONE LINE OF `src/` OR `include/` CHANGED.** `git diff --stat src/ include/` was
  empty when this landed, and that is the strongest thing #57 has to say about #50-#55:
  the C-grid was already expressible. What it adds is a declaration, two geometries, three
  C++ checks, one surface gate, one golden case and one acceptance run. #55's rule that
  "a block welded to ITSELF is inexpressible" is why the wake is TWO blocks sharing one
  cut rather than one block wrapping onto itself, and that constraint turned out to cost
  nothing — a C-grid is four blocks either way.

- **The wake cut is one edge that is the WEST of BOTH blocks, which no earlier fixture
  produces.** Every shared edge before it (#53's H-grid, #55's ring) was one block's east
  and another's west, so the two frames ran the SAME way along it. Two blocks on opposite
  sides of a wake are mirror images: both declare it as their west, and the edge is
  traversed in opposite senses from the same side index. The reversal machinery #53 built
  ("the other three sides may be declared either way and are traversed as the ring
  requires") already covered it; injection Q, which drops the reversal for the west side
  only, is refused by the four-shared-corner check. What checks 37-39 add is not a new
  guard but a topology that REACHES the existing ones.

- **The four-way corner needed nothing either, and the arithmetic is worth writing down.**
  Corner `te` is one declaration and therefore one node; five edges end on it and all four
  blocks hold it. The four blocks own 3*4 + 3*6 + 3*6 + 3*4 = 60 node SLOTS in the C++
  fixture; the cut identifies 4 of them and each of the three radials 3, so 13
  identifications leave 47 nodes. Three of those 13 are the trailing edge's own — exactly
  what it takes to bring four occurrences of one point down to one — and they form a
  spanning tree over the four blocks, which is why the count does not need
  inclusion-exclusion.

- **GATE 1 PASSED ON THE FIRST RUN; GATE 2 IS THE ONE THAT BIT.** #57 agreed an escalation
  ladder for the case where transfinite interpolation could not clear zero inverted cells
  — Laplacian smoothing of block interiors, then shipping the O-grid as the release
  geometry, then pulling elliptic smoothing forward — and asked for a record of which step
  was needed. **None was reached.** The shipped declaration meshed with 0 inverted cells
  out of 11520 the first time it ran. The solver then went to NaN in 40 iterations, which
  is a failure mode the ladder does not have a rung for, because the ladder was written
  against the wrong gate.

- **The diagnosis, and where the ticket's own prediction was wrong.** #57 expected TFI to
  struggle "near the trailing edge" and made non-orthogonality a recorded baseline rather
  than a gate for that reason. Dumping the solution at iteration 30
  (`print_sol_per_niter 10`) and reading off the cells with `|rho| = inf` put the blow-up
  on the upper and lower surfaces from x = 0.01 to x = 0.28 — just aft of the **LEADING**
  edge, and the same place the worst angle was: 59.52°, in the FIRST CELL OFF THE WALL.
  The cause is a parametrisation mismatch, not the corner: the far field's two nose sides
  were left uniform, so the outer point lying opposite a body point sat nowhere near that
  body point's normal. At mid-chord the body's normal is nearly vertical and reaches the
  D's horizontal top at almost the same x; on a uniform 16.7-long outer side the point at
  the same normalized arc length is most of the way round the nose semicircle instead.

- **The fix is one number and it is DERIVED, not tuned.** Both nose sides now cluster at
  their trailing-edge end to 0.005, which is the airfoil edges' own `ds_start`. The
  chordwise part of the outer boundary then tracks the body's own spacing, and the whole
  nose semicircle belongs to the last few percent of the body, where the normals fan
  through 180°. Measured on the shipped files: max non-orthogonality 59.52° -> **32.04°**,
  mean 16.0° -> **4.56°**, wall first cell 3.46% -> **0.44%**, cell count unchanged at
  11520, inverted still 0 — and the solver runs to completion at the same `cfl 0.6` the
  O-grid acceptance run used. **Nothing enforces the relation between the two numbers**:
  they are two values in one document that happen to agree, and changing the airfoil's
  spacing means changing this by hand. Named as a blind spot in the surface gate.

- **TWO THINGS THAT WERE TRIED AND ARE RECORDED SO THEY ARE NOT RE-TRIED.** (1) Lowering
  `cfl` from 0.6 to 0.3 or 0.1 makes the ORIGINAL, bad mesh run to exit 0 as well. A "the
  solver runs" line was therefore available without improving the grid at all, which is
  why the recorded run states its CFL and why this paragraph exists. (2) The wake's
  3144:1 worst edge ratio was the obvious first suspect and is **measured not to be the
  cause**: giving the two outlet radials a coarser first cell (physically right — the wake
  spreads) cut it to 211:1 and left the solver diverging at the same iteration. It also
  pushed the reported wall first-cell figure to 47%, because the two ends of one
  equivalence class then ask for heights 50x apart; that variant was dropped.

- **A second airfoil file rather than a sidecar beside the shipped one.**
  `examples/geometries/naca0012.dat` is the hybrid path's airfoil, has no `.meta`, and has
  a golden baseline; giving it one would change what that path reads for a case #57
  requires to stay identical. `naca0012_cgrid.dat` is generated from the NACA 4-digit law
  in the closed-trailing-edge variant (-0.1036, so y(1) is exactly 0 — an open trailing
  edge would need a fifth block across it), cosine-spaced, in two segments split at the
  leading edge because that is where a block corner sits. `cgrid_farfield.dat` is the
  D-shape in six segments, one per outer block side, walked counter-clockwise from the
  wake's own outlet point so the two outlet halves are segments 0 and 5. Both are checked
  against their ONE generator in the surface gate, for the reason #55 gives.

- **The outlet plane is split by the wake, and that is what makes the far field six
  segments and not five.** The C is open at the outlet; its two open ends are ordinary
  bound boundary edges carrying `outlet`, and getPGrid knows that name (it does not know
  `farfield`). So the six far-field segments are exactly the six outer block sides and
  nothing falls back to `BC_GEOM`.

- **The gates.** `tests/cpp/test_multiblock.cpp` 37-39 (the cut as both blocks' west with
  its reversal and a palindrome control, no boundary face on it, the four-way corner as
  one id in four blocks with the 60-slots-to-47-nodes count, and the five-radial chain);
  `tools/PreProcessor/tests/test_multiblock_cgrid_surface.py` (9 groups on the SHIPPED
  files, reusing #53's conformity measure, with the wake-as-`wall` refusal as check 4's
  negative control); and the `mb_cgrid` golden case. Four hand injections, dated
  2026-09-04 in the C++ test's docstring.

- **An injection scored ZERO TWICE before it was scored at all.** Injection S (the
  four-way corner welding its first two users only) exited 139 in both of its first two
  forms — the first pushed onto `r.nodes` while holding a reference into it, the second
  de-welded every corner with three or more users, so an O-grid fixture refused and an
  older check indexed `r.blocks[0]` on an empty vector. A run scored by counting FAIL
  lines reads a SIGSEGV as "no effect". Read the exit code first; this repo has recorded
  that lesson before and it still cost two rounds here.

- **"The nine original cases remain identical" — the honest argument is STRUCTURAL.**
  `git diff --stat src/ include/` against `02ed550` is empty, so no code the mesher runs
  changed and nothing could have moved. The measurement agrees rather than carries the
  claim: a baseline captured from this tree before the work and compared after gives
  17/17 SAME at worst coordinate deviation 0.000e+00 (2026-09-04; 18/18 once `mb_cgrid`
  was captured). The word is "SAME" and not "bit-identical": `golden_mesh.py`'s own
  docstring records `wedge_45` returning a coordinate ~1.2e-13 different in roughly 1 run
  in 12, which is why the comparator has a 1e-10 tolerance at all, and a commit message
  that said "bit-identical" was claiming more than the comparator can promise on a rerun.

- **Blind spots, named.** Gate 2 is ONE operating point (M 0.2, Re 200, zero incidence,
  100 iterations, `cfl 0.6`, every non-wall patch flag 1) and nothing re-runs it — CI has
  no solver binary, so it is a dated quotation like #55's — and nothing from it is
  committed, so re-doing it means rebuilding the case by hand. It also does NOT exercise
  the `.bnd` name -> solver flag mapping: getPGrid does not know `farfield`, so the flag
  the run used was written into `cgrid.bc.def` by hand, exactly as #55's was. Non-orthogonality remains a
  baseline and not a gate, and 32.04° in the first wall cell is still what the
  elliptic-smoothing increment exists to move. The 0.005 relation is unenforced. And the
  surface gate measures conformity on the EXPORTED files, so it cannot separate "welded
  correctly" from "welded correctly and then exported correctly".

**A SMOOTHING STAGE in the seam, with a kernel chosen because it is WRONG**
(`MB_SMOOTH_ITERS`, default 0; #81, ticket 1 of #80's five). The rules are
`.claude/rules/mesher-multiblock.md`, "SMOOTHING is a STAGE inside the seam".

> **THE KERNEL THIS BLOCK DESCRIBES WAS DELETED BY #82**, which is what the block was
> written to make possible. Everything below is about the LAPLACIAN and is kept as
> history and as the baseline #82 is measured against — its numbers are quoted, never
> re-measured, because there is nothing left to measure them on. The stage, the freeze,
> the Jacobi rule, `preSmoothNodes`, the two machine-readable lines and the golden case
> all survive unchanged; the arithmetic in the middle of them does not. **The current
> kernel is the next block, "THE WINSLOW KERNEL".** Where a claim below is now false of
> the shipped code — that five sweeps fold four cells on the C-grid, that a fold is
> reachable at all on a shipped file — it is false because the kernel changed, and that
> is the finding rather than a stale sentence.

- **Why ship a kernel that loses.** #48 already agreed Laplacian smoothing of block
  interiors as the FIRST escalation step if transfinite interpolation could not clear the
  inverted-cell gate; #57 cleared that gate on the first run of the shipped C-grid, so it
  was never built. Building it now buys three things a better kernel would have had to
  buy anyway — the STAGE, the before/after REPORTING, and one honest measurement — and it
  buys them against a kernel whose failure mode is known in advance. A plain Laplacian
  equalises spacing. It has no way to know where a wall is, so it cannot trade an interior
  node's position for orthogonality at one; what it does instead is drag the first interior
  line away from the wall and spend the clustering the whole declaration exists to deliver.
  Ticket 3 of #80 is what fixes that, and the argument for it is now a table rather than a
  prediction.

- **THE TABLE, measured 2026-09-04 on the SHIPPED files** (the C-grid, 11520 cells, and
  the O-grid, 9216 — #80's own negative control, a case already good enough that smoothing
  "must not make it worse"):

  | case | sweeps | inverted | non-ortho max | non-ortho mean | wall first cell |
  |------|--------|----------|---------------|----------------|-----------------|
  | C-grid | 0 | 0 | 32.044° | 4.562° | 0.44% |
  | C-grid | 1 | 0 | 89.399° | 6.230° | **36.61%** |
  | C-grid | 5 | **4** | 89.786° | 10.004° | 126.45% |
  | C-grid | 20 | **26** | 89.864° | 16.288° | 372.84% |
  | O-grid | 0 | 0 | 2.250° | 1.875° | 0.08% |
  | O-grid | 1 | 0 | 4.344° | 1.882° | 53.36% |
  | O-grid | 5 | **184** | 17.443° | 2.111° | 87.36% |

  **Every column gets worse, including the two this arc exists to improve.** The wall
  figure was the predicted casualty and it is an 84x regression at one sweep; the
  non-orthogonality regression was NOT predicted by the ticket and is the more interesting
  half — a kernel aimed at the metric #80 names makes that metric worse, because equalising
  spacing across a boundary-layer-scale grading shears the cells next to the frozen wall
  line. The negative control fails on the same terms, so "turn it on where the mesh is
  already good" is not a workaround either. Nothing here is papered over: the run PRINTS
  both halves, and the ticket's whole value is that this is a measurement.

- **The stage sits between the FILL and the SPLIT, and that ordering is currently
  unfalsifiable.** Injection Y moved the entire sweep block past the split loop and
  NOTHING failed — every reader downstream (the split, the boundary-edge walk) reads node
  IDS and the sides' own positions, never the interior coordinates. The ordering is
  therefore a design rule held by a comment rather than by a gate, and it is recorded as a
  named blind spot rather than as a claim the tests support. It is still the right
  ordering: it is what makes "no downstream reader can tell a smoothed result from an
  unsmoothed one by its shape" true by construction instead of by inspection of each
  reader, one at a time, forever.

- **Which nodes move was a decision, not an implementation detail.** #80 says so, and the
  three candidate answers — interior only, shared-edge nodes too, bound wall nodes too —
  are three different tickets. Ticket 1 takes the first, and the reason it is the first is
  not caution: a block-boundary node is written by the EDGE, an edge is SHARED by
  construction, and welding on this path is by ALLOCATION rather than by comparison. Moving
  such a node means moving it in two blocks at once, and moving a node on a BOUND edge
  takes it off the geometry it was attached to by arc length — the one chain in this module
  that has no tolerance in it anywhere. So interior-only is the answer that needs no new
  machinery, and it has the useful side effect that one block's interior never neighbours
  another's, which is why the sweep needs no ordering rule between blocks at all.

- **Jacobi rather than Gauss-Seidel.** Gauss-Seidel converges faster and is what most
  descriptions of "Laplacian smoothing" mean, but it makes the answer a function of the
  order the blocks and the (i, j) pairs are visited — an order nobody declared. That is the
  same objection this module already raises against a sequential generator for the
  randomized diagonal, and the answer is the same. Cost: more sweeps for the same
  relaxation, which does not matter for a kernel this arc is going to replace.

- **`preSmoothNodes` rather than running the build twice.** The seam publishes the node
  positions as they stood the instant before the first sweep, so the two quality reports
  are the same cells, the same blocks and the same node ids over two coordinate sets, and
  the difference between them is the smoother and nothing else. Two runs compared against
  each other would have proved nothing of the sort. It is EMPTY when no sweep ran — not a
  copy — because a run that did not smooth has no "before" distinct from what it returned,
  and printing two identical blocks in front of a reader who asked for no smoothing is a
  worse answer than printing one.

- **The machine-readable line keeps its meaning.** `HYBMESH_MB_QUALITY` always describes
  the mesh AS EXPORTED; the before half is `HYBMESH_MB_QUALITY_BEFORE` and exists only on a
  smoothed run. So a gate that greps the token keeps getting the answer about the file on
  disk and never has to know which kind of run it is reading. Two existing readers matched
  the prefix WITHOUT its trailing space and would have parsed the before line as the real
  one; both were tightened in the same commit. The alternative — a `stage=` field on the
  existing line — was rejected because it changes the unsmoothed run's output, which is the
  one thing this ticket promised not to do.

- **A fold from smoothing is an ORDINARY inverted mesh.** Counted after the sweeps,
  exported, exit 9, no new code and no second exit code: the declaration is valid and its
  interpolated-then-relaxed interior came out folded, which is exactly what
  `EXIT_ERR_INVERTED` already means. The shipped C-grid reaches it at 5 sweeps and the
  O-grid at 5 as well, so this is not a theoretical branch.

- **"The eighteen are unchanged" is a MEASUREMENT, and here is how to repeat it.**
  `golden_mesh.py capture <dir>` from the tree at `507881d` (before the work), then
  `golden_mesh.py compare <dir>` after: 18/18 SAME at worst coordinate deviation 0.000e+00.
  Nothing is committed, so it is a dated run like the solver acceptance runs — and the
  structural half of the argument is weaker here than #57's, because this commit DOES change
  code the mesher runs (the fill loop was split in two). The measurement is what carries it.

- **The golden case is ONE sweep, and that is a measurement rather than a taste.**
  `mb_cgrid_smooth` runs the shipped C-grid config with `MB_SMOOTH_ITERS 1`. At 5 it exits
  9, and `golden_mesh.py` records a non-zero run as "no mesh produced" and compares
  nothing — so a heavier case would have been a baseline of one line. One sweep still moves
  every interior node, which is what a kernel change (every remaining ticket of #80) has to
  move past a 1e-10 tolerance.

- **A FOLD IS NOT REACHABLE WITHOUT CLUSTERING, and that had to be measured.** The spec
  review found check 46 titled "enough sweeps FOLD a cell" while asserting only that the
  seam returned `ok`. Made to assert the fold, it FAILED: the C-grid fixture checks 37-39
  use gives each block ONE interior row, and a Laplacian over one row between frozen
  boundaries relaxes toward a straight line and folds nothing at any sweep count. Making it
  denser was still not enough — 60 sweeps on a uniform 25-node version fold nothing either.
  What makes a fold reachable is the WALL CLUSTERING: 0 folded quads before, 26 after, once
  the three radials ask for a first cell of 0.002. That is the same mechanism the shipped
  grid folds by, and it is worth stating because it means "smoothing can fold a cell" is a
  claim about clustered grids specifically — i.e. about exactly the grids this path exists
  to make.

- **The gates, and seven hand injections dated 2026-09-04** in
  `tests/cpp/test_multiblock.cpp`'s docstring. Two are worth repeating here. **X (the
  before list never published) exited 139 with ZERO FAIL lines** — checks 42 and 43 indexed
  an empty vector — which a run scored by counting FAIL lines reads as "the injection did
  nothing". This repo has recorded that lesson twice before (#54's H, #57's S) and it still
  cost a round; the two checks are now guarded so the same injection reports 7 failures
  instead of a segfault. **AA (the `.dat`-level refusal of a negative count removed) left
  the C++ suite entirely green** and was caught only by the surface gate, and only by the
  line that asserts WHICH exit code the refusal carries — the seam's own door still refused
  it, with the topology code instead of the config one. That is exactly what the
  two-doors-two-codes convention is for, and it is the same shape as #54's injection N.

**THE WINSLOW KERNEL, and the Laplacian deleted rather than kept beside it**
(`MB_SMOOTH_ITERS` unchanged in key, type and default; `hybmesh::mbWinslowUpdate` in
`include/MultiBlock.hpp` + `src/MultiBlock.cpp`; #82, ticket 2 of #80's five). The rules
are `.claude/rules/mesher-multiblock.md`, "SMOOTHING is a STAGE inside the seam, and its
kernel is WINSLOW".

- **What the kernel is.** The elliptic system for the COMPUTATIONAL coordinates,
  transformed so the physical ones are the unknowns:
  `a x_ii - 2b x_ij + g x_jj = 0` with `a = x_j^2 + y_j^2`, `b = x_i x_j + y_i y_j`,
  `g = x_i^2 + y_i^2`, on unit spacing in (i, j) — which is what makes `MbBlock`'s
  retained logical indexing arithmetic rather than a parity bit, the second reader #80
  predicted it would acquire. The node goes to a weighted mean of its four logical
  neighbours plus a cross term over its four diagonals. The whole of the difference from
  #81's kernel is that the STRETCHING sits in `a` and `g` instead of in the answer.

- **THE TABLE, measured 2026-09-04 on the SHIPPED files**, beside #81's Laplacian at the
  same cap (quoted from that ticket; the kernel is deleted):

  | case | cap | kernel | inverted | non-ortho max | non-ortho mean | wall first cell |
  |------|-----|--------|----------|---------------|----------------|-----------------|
  | C-grid | 0 | — | 0 | 32.044° | 4.562° | 0.44% |
  | C-grid | 1 | Laplacian | 0 | 89.399° | 6.230° | 36.61% |
  | C-grid | 1 | **Winslow** | 0 | **31.438°** | 4.778° | **11.65%** |
  | C-grid | 5 | Laplacian | 4 | 89.786° | 10.004° | 126.45% |
  | C-grid | 5 | **Winslow** | **0** | **29.844°** | 5.627° | 39.15% |
  | C-grid | 20 | Laplacian | 26 | 89.864° | 16.288° | 372.84% |
  | C-grid | 20 | **Winslow** | **0** | 33.759° | 8.517° | 130.77% |
  | O-grid | 0 | — | 0 | 2.250° | 1.875° | 0.08% |
  | O-grid | 1 | Laplacian | 0 | 4.344° | 1.882° | 53.36% |
  | O-grid | 1 | **Winslow** | 0 | **3.312°** | 1.875° | **9.13%** |
  | O-grid | 5 | Laplacian | 184 | 17.443° | 2.111° | 87.36% |
  | O-grid | 5 | **Winslow** | **0** | **8.061°** | 1.978° | 29.13% |

  **Every Winslow row beats the Laplacian row beside it, on every column, on both cases.**
  Max non-orthogonality on the C-grid also beats the UNSMOOTHED fill — 32.044° -> 31.438°
  at one sweep, 29.844° at five — which is the metric #80 exists for and the first time in
  this arc that a number moved the right way.

- **What it does NOT fix, both measured rather than argued.** The WALL FIRST CELL is still
  worse (0.44% -> 11.65%), because plain Winslow relaxes toward each block's harmonic map
  and a harmonic map has no memory of a declared first-cell height. #82 says so in advance
  and #83's control functions are what hold it; what this ticket owes is the number, which
  is 26x rather than #81's 84x. And **#80's O-GRID NEGATIVE CONTROL IS NOT MET**: a case
  already at 2.250° comes out at 3.312°.

- **WHY the negative control fails, localised out of the run's own report rather than with a
  second instrument.** Unsmoothed, the O-grid's wall first cell is 9.992e-04 .. 1.000e-03
  all the way round — uniform. After one sweep it is 1.000e-03 .. 1.091e-03: the declared
  height EXACTLY, and only, where a frozen radial interface pins it, drifting 9.13% in the
  middle of each block. A wall row pinned at four points and lifted between them is a KINK,
  and the kink is what the max non-orthogonality is reporting. So the regression is the
  FREEZE, not the kernel — it is #80's ticket 4 (#84, "smoothing across shared edges", also
  its user story 3) arriving as a measurement instead of as a plan. Recorded as unmet and
  owned; the surface gate asserts it in that direction, with a note to delete the check and
  amend #80 if it ever starts passing.

- **The Laplacian was DELETED, which #82 required a decision on.** Nothing read it. It
  loses on every column above. An inert alternative kept "for completeness" is the mechanism
  this repo has a rule against, and a kernel-selection enum over one surviving kernel is the
  abstraction that rule exists to prevent — so there is no `MB_SMOOTH_KERNEL`, no string
  compared at several sites, and no second entry point. It survives only as
  `laplacianByHand` inside `tests/cpp/test_multiblock.cpp`, because three checks claim the
  two kernels give different answers and a claim like that needs both sides written down.

- **THE SOLVE IS BOUNDED, AND HAS THREE ENDINGS, WHICH IS NOT WHAT THE TICKET EXPECTED.**
  `MB_SMOOTH_ITERS` became a CAP: the solve stops when its residual — the largest node move
  in a sweep, over the STARTING mesh's bounding-box diagonal — falls under `MB_SMOOTH_TOL`
  (1e-8). Relative and not absolute so the same topology in mm and in m takes the same
  number of sweeps; not a config key, because the tolerance a solve is "done" at is not a
  per-case question while the cap is. The third ending was found by measuring rather than
  by design: **on the shipped C-grid the residual falls monotonically to 2.7e-08 by sweep
  3724 and then GROWS**, about 1.0018 per sweep, so that by sweep 10000 it is 1.3e-03 and
  88 cells have folded. The lagged-coefficient point iteration is only conditionally
  stable, and a grid equidistributed to 74.8° max non-orthogonality is where the condition
  fails. Under-relaxation does not repair it (a real eigenvalue above 1 stays above 1 under
  `(1-w)I + wM`), so the solve WATCHES ITS OWN RESIDUAL: at ten times its best it stops,
  restores the best iterate and reports `smoothDiverged` with that iterate's own sweep
  number. Rolling back is the honest answer and not a cover-up — both flags, the sweep
  count and the residual are published, and the alternative is handing back a mesh that got
  worse the longer it was asked to work. The factor is TEN and not two because every case
  measured falls monotonically until it turns, so two would be a tripwire on a wobble.

- **The exactness gate, and the premise it had to correct.** #82 asks for "a C++ check that
  the kernel reproduces an exactly-known answer on a grid where one exists — a stretched
  rectangle is smooth already, so the solve must return it unmoved". That is true of a
  rectangle stretched in ASPECT and false of one GRADED in its spacing: plain Winslow's
  fixed point is the harmonic map, whose interior spacing is uniform, so a graded rectangle
  is not returned unmoved and cannot be — which is why #80 has a ticket 3 at all. Check 47
  therefore does both halves: a UNIFORM grid on a 250:1 rectangle comes back within 2.8e-14
  (the transfinite fill's own rounding, not the solve's) and converges on its first sweep,
  and the same rectangle GRADED is measured to move. **And check 47 cannot be the gate the
  ticket wanted on its own**: every second difference of a bilinear map is zero, so its
  residual is zero for ANY metric coefficients and a swapped `a`/`g` passes it untouched.
  That is check 48's job — one stencil worked through on paper, `a = 10`, `b = 5`, `g = 5`,
  cross `(0.75, 1.5)`, answer `(42.5, 35)/30` — which also computes the four usual ways of
  getting it wrong and asserts they land somewhere else, because a gate whose passing value
  is also the wrong answer's value is not a gate.

- **THE KERNEL UNFOLDS WHAT THE FILL FOLDED, and that turned a gate over.** On a block with
  a re-entrant corner the transfinite fill lays 13 folded quads across the notch on a
  perfectly valid declaration; the elliptic solve converges to a mesh with none, and #81's
  Laplacian from the same start and the same sweep count does not (check 50). The other
  side of the same finding is that #81's fold gate STOPPED FIRING: the shipped C-grid folded
  4 cells at 5 sweeps and 26 at 20 under the Laplacian and folds NOTHING at any cap under
  this kernel, so the surface gate's group 5 now asserts the zero and says why it turned
  over, and the C++ fold check had to make its fixture harder — a declared first cell of
  0.0005 rather than 0.002. The exit-9 path itself is unchanged code and is still gated, on
  a folded DECLARATION in `test_multiblock_quality_surface.py` and on that clustered
  fixture in `test_multiblock.cpp` check 46.

- **The golden move was deliberate and is the reason `mb_cgrid_smooth` exists.** Baseline
  captured from the tree at `84deaf3` with `HYBMESH_GOLDEN_BIN`, compared after: **18 of 19
  SAME at 0.000e+00** (`wedge_45` at its usual 2.5e-13 wobble), and the nineteenth —
  `mb_cgrid_smooth`, the only case whose nodes come from the smoother — moved 1.999 units at
  its worst node with its connectivity redrawn. #81 wrote that case precisely so a kernel
  change would show up here as a number, and it did.

- **A CAP IS TWO SITUATIONS, which the review found and the code now says.** The first
  form of the capped warning told the reader to "raise MB_SMOOTH_ITERS to finish the
  solve" — advice this ticket's own tables contradict, since a CONVERGED plain Winslow
  solve is each block's harmonic map and is 3133% off the declared wall height on the
  C-grid and 1382% on the O-grid. Converging is the worse outcome at this kernel, and the
  only useful settings (a cap of 1 to about 5) are exactly the ones that print
  `Converged: NO`. Worse, that one sentence was given to two different situations: a solve
  still DESCENDING has more to give, while one whose residual is already above the best it
  reached has TURNED, and both wear `converged == false && diverged == false`. So
  `smoothBestSweep` / `smoothBestResidual` are published — recorded before either stop is
  tested, so a converged solve's best is the sweep it returned rather than the one before
  — and the advice branches on them. The mesh at a cap is still the LAST iterate: N sweeps
  has to mean N sweeps outside the diverged path, which is what check 43 rests on, so the
  difference is said rather than silently repaired.

- **Thirteen hand injections dated 2026-09-04** in `tests/cpp/test_multiblock.cpp`'s
  docstring — twelve that bite and one recorded inert — each applied alone with both the
  C++ test and the surface gate run and exit codes read before FAIL counts. Three are worth
  repeating. **G (the divergence rollback removed) and I
  (the reverse — the nodes rolled back but not the sweep count) were BOTH inert** against
  every check that existed, including the one asserting the diverged run exports a mesh with
  no folded cell, which is true of either iterate; what catches them is a ROUND TRIP that
  re-runs at the reported sweep count and requires both the same mesh AND that the re-run
  stop at its cap rather than diverge. Neither half alone is enough. **H (the residual made
  absolute instead of relative) is caught by the C++ test and by NOTHING in the surface
  gate**, because that gate's assertions are about which ending each case reaches and
  neither ending moves — the divergence test is a ratio and cancels the change entirely. A
  scale-free rule needs a fixture with a scale in it. And **E is INERT because it cannot be
  anything else**: the two off-diagonals of the cross stencil enter with the same sign, so
  swapping them changes nothing and no gate can catch it. That is a symmetry of the
  discretisation, not a hole — recorded rather than fixed, with E' (pp and mp, which have
  opposite signs) as the injection that does bite.

- **NAMED BLIND SPOTS.** The divergence path and the rollback are gated by the SURFACE gate
  alone: 26 synthetic fixtures were tried in the C++ test — the clustered C-grid at four
  wall spacings x two wall resolutions, a non-convex dart at three depths x three gradings x
  two resolutions — and every one converged. The case that diverges is the shipped C-grid,
  so a change that broke the rollback while nobody ran the shipped file would go unnoticed.
  And the smoothed mesh is STILL never given to the solver or the grid converter: 11.65% off
  the requested wall height is not a boundary layer worth integrating, so the acceptance run
  remains #80's own (#85), not this ticket's.

**WALL CONTROL FUNCTIONS: the source terms that tell the solve what a wall is**
(`include/MbControl.hpp` + `src/MbControl.cpp` in `hybmesh_pure`; `MbControl` and
`MB_CONTROL_CLIP` in `include/MultiBlock.hpp`; #83, ticket 3 of #80's five). The rules
are `.claude/rules/mesher-multiblock.md`, "SMOOTHING is a STAGE inside the seam, its
kernel is WINSLOW, and since #83 that kernel is CONTROLLED".

- **What the increment is for, in #82's own words.** That ticket's honest advice was
  "use a small cap", because a CONVERGED plain Winslow solve is each block's harmonic
  map and is 3133% off the declared wall height on the C-grid and 1382% on the O-grid.
  That is a workaround for a missing input, not a setting. The system gains two source
  terms — `a(x_ii + phi x_i) - 2b x_ij + g(x_jj + psi x_j) = 0` — and **both zero is
  #82's update term for term**, which is asserted (check 52) rather than left to the
  algebra, because it is what lets #82's exactness gate keep measuring the same kernel.

- **THE TARGET IS A POSITION, NOT A DERIVATIVE, and that is worth 8.7%.** The textbook
  Steger-Sorenson wall condition specifies `r_n`, the derivative of the map at the wall.
  What the declaration asks for and what `measureMbQuality` measures is `|p_1 - p_0|`,
  the first INTERVAL. On a geometrically graded line of ratio q the two differ by
  `(q-1)/ln q`: at the shipped C-grid's q of about 1.18 a control aimed at the derivative
  converges neatly onto an interval 8.7% larger than anybody asked for. This was found on
  paper before it was measured, and it is the reason the condition here is stated on the
  position.

- **AND THE INTERPOLATION IS THE RULER'S, which is the same lesson from the other side.**
  `MbWallSpec` publishes the height at a side's two corners; `measureMbQuality` blends
  them LINEARLY IN THE LOGICAL COORDINATE. Arc length along the wall is the answer this
  repo's habits point at — the arc-length-not-chord rule is elsewhere in this note — and
  it is wrong here, because it would drive the mesh at one number while the acceptance
  gate measured it against another. The rule that covers both is that the measure of the
  request and the measure of the achievement must be the SAME measure; the
  edge-distribution warning learned it by comparing a CHORD against a request expressed
  in arc length and firing on an edge that had honoured the request exactly.

- **FOUR FORMULATIONS, MEASURED IN ORDER, on the shipped C-grid at one sweep.** This is
  the whole of the ticket's engineering and none of it was derivable in advance:

  | attempt | wall first cell | max | mean | clipped | why it failed |
  |---------|-----------------|-----|------|---------|----------------|
  | Steger-Sorenson on the DERIVATIVE at the frozen wall row | 19.86% | 32.50° | 3.675° | ~3182 | both projections divide by `a = h²`, so a 32°-skewed first cell asks for a `phi` of about **-21**; it clips, and the clipped value carried outward destabilises |
  | exact 2x2 solve for the target POSITION at the first interior row | 121.17% | 39.78° | 4.082° | 3182 | the same blow-up: one exact vector equation in two unknowns still asks for a `phi` no kernel can take |
  | the near-wall 1-D limit, `psi = 4h/span - 2` | 2.96% | 31.86° | 4.651° | 0 | well conditioned at last, but it ignores the along-wall weights and the cross term, and the 2-D miss it leaves never feeds back — so the figure got WORSE with more sweeps (5.9% at five) |
  | least squares for the target position, projected onto `dir` | 11.75% | 31.84° | 4.650° | 36 | one scalar cannot place a node in a plane; projecting spends it on both components instead of nailing the one that is measured |
  | **the quadratic solved for the DISTANCE** | **0.29%** | **31.86°** | 4.649° | 36 | — |

  The last one is the ticket. The kernel's update of the first interior node is linear in
  both sources, so writing it as `base + s * dir` measured from the wall node makes
  `|base + s * dir| = requested` **one quadratic in one scalar**; both roots are written
  down and the root taken is the one landing nearer `p_wall + requested * n̂`. **That is
  where the 90-degree half of the declaration enters** — as the tie-break between two
  points at the same correct distance on opposite sides — and it is why nothing here
  trades orthogonality against spacing: they are one vector, not two knobs. NO REAL ROOT
  is the control meeting a request it cannot honour; it takes the closest approach and the
  wall-residual warning is what says so.

- **THE SECOND HALF WAS THE ONE THAT MOVED THE MEAN, and it is a SCOPE rule.** With the
  off-wall source written at the first row and nowhere else, the rest of each radial line
  relaxes toward uniform and the MEAN non-orthogonality rises with every sweep — 4.65° at
  one, 6.14° at twenty, against the fill's 4.562° — because equidistributing a graded grid
  skews every cell it touches a little. Fitting an ideal GEOMETRIC line to the declared
  height and the line's length instead imposes a distribution nobody declared: these
  radial edges declare a **TANH** law, so the ideal and the actual diverge with distance,
  and it saturated 2120 nodes and folded 432 cells. What works is **Thomas-Middlecoff on
  the line's own current spacing** beyond the first row: it HOLDS whatever the fill
  produced there and asks for nothing. The declaration owns the first cell, the fill owns
  the rest of the line, and the solve is left to move the LINES rather than the spacing
  along them. All three of #80's figures then improve together.

- **THE CLIP IS THE KERNEL'S BOUND, NOT A TASTE.** The update weights a neighbour by
  `a(1 ± phi/2)`, so at `|phi| = 2` one weight reaches zero and past it the node stops
  being a convex combination of the nine positions it reads — no maximum principle, and a
  node can leave their hull, which is a fold rather than a smoother. `MB_CONTROL_CLIP` is
  that 2, `MbControlField::clipped` counts the nodes that hit it, and `smoothClipped`
  carries it to `HYBMESH_MB_SMOOTH` as `clipped=`.

- **AND READING THAT COUNT AS A THRESHOLD WAS THIS TICKET'S OWN MISTAKE, caught by its own
  gate.** The plausible advice — "lower the cap until nothing is clipped" — was written
  into the capped warning and into a C++ check, and the surface gate refused it: on the
  shipped C-grid the count is **36 at a cap of one**, on a mesh with 0 inverted cells and
  every figure better than the fill's. It runs 36, 28, 8, 0 over the first ten sweeps —
  the control CATCHING UP with a target the algebraic fill starts far from — and only then
  climbs back off zero, 4 at sweep 100 and 212 at 500, alongside the folds. So it means
  "the solve is working" on the way down and "the iteration is going" on the way up. A
  number with two opposite meanings cannot gate an `if`: it is reported with a sentence
  saying which way to read it, and the advice points at the inverted-cell count, which is
  machinery that already existed.

- **THE TABLE, measured 2026-09-07 on the SHIPPED files**, beside #82's plain Winslow at
  the same cap (quoted from that ticket):

  | case | cap | kernel | inverted | max | mean | wall first cell | clipped |
  |------|-----|--------|----------|-----|------|-----------------|---------|
  | C-grid | 0 | fill | 0 | 32.044° | 4.562° | 0.4368% | — |
  | C-grid | 1 | Winslow (#82) | 0 | 31.438° | 4.778° | 11.65% | — |
  | C-grid | 1 | **+control** | 0 | **31.861°** | **4.527°** | **0.1222%** | 36 |
  | C-grid | 5 | Winslow (#82) | 0 | 29.844° | 5.627° | 39.15% | — |
  | C-grid | 5 | **+control** | 0 | **31.382°** | **4.454°** | **0.0805%** | 8 |
  | C-grid | 20 | Winslow (#82) | 0 | 33.759° | 8.517° | 130.77% | — |
  | C-grid | 20 | **+control** | **0** | **29.895°** | **4.301°** | **0.0893%** | 0 |
  | C-grid | 30 | +control | 0 | 31.550° | 4.252° | 0.0943% | 0 |
  | C-grid | 40 | +control | 0 | 34.784° | 4.214° | 0.0980% | 0 |
  | C-grid | 100 | +control | **4** | 86.606° | 4.710° | 19.06% | 4 |
  | C-grid | 500 | +control | **288** | 84.927° | 10.860° | 99.99% | 212 |
  | O-grid | 0 | fill | 0 | 2.250° | 1.875° | 0.0812% | — |
  | O-grid | 1 | Winslow (#82) | 0 | 3.312° | 1.875° | 9.13% | — |
  | O-grid | 1 | **+control** | 0 | 3.632° | 1.875° | **0.0390%** | 0 |
  | O-grid | 5 | Winslow (#82) | 0 | 8.061° | 1.978° | 29.13% | — |
  | O-grid | 5 | **+control** | 0 | **6.418°** | 1.980° | **0.0412%** | 0 |
  | O-grid | 20 | +control | 0 | 12.036° | 2.571° | 0.0442% | 0 |

  **#80's acceptance for this ticket is MET on the C-grid**: at a cap of 20 the max is
  better than #57's 32.044°, the mean is better than its 4.562° AT THE SAME TIME, the wall
  first cell is better than its 0.4368% rather than merely no worse, and inverted is still
  0. "Both improving at once is the whole claim" — that is the row.

- **THE NEAR-LEADING-EDGE REGION, measured on its own because the ticket asks for it.**
  #57 localised the cells that drove the solver to NaN: the first cell off the wall just
  aft of the leading edge, worst corner at (0.0134, 0.0196). Over the ten quad cells
  touching the airfoil between x = 0.005 and 0.030 the region reads **32.044° max /
  26.895° mean unsmoothed -> 31.861° / 26.734° at one sweep -> 29.895° / 24.909° at
  twenty**. It improves monotonically, and both figures move — a mesh-wide average could
  have improved while this did not, which is exactly the criterion's point. On this case
  the whole-mesh maximum IS this region's maximum, which is worth knowing: the C-grid's
  headline max number has been a statement about the leading edge all along.

  The instrument is a QUAD READER in the surface gate, not a new metric. #80 says no new
  metric is invented and `MbQuality` owns the ruler; what the gate adds is a SELECTION of
  which corners to report, and "which cells are near the leading edge of the shipped NACA
  0012" is a fact about a shipped FILE that a pure function of any `MbResult` has no
  business knowing. What keeps it from becoming a second answer is that group 10 first
  reproduces the C++ ruler's WHOLE-MESH max and mean off the same code, to 1e-4, before
  reading the region it cannot check.

- **THE TWO HALVES ARE NOT DRIVEN EQUALLY, which the review made explicit and the
  module's name overstates.** The HEIGHT is solved for: one scalar, one equation,
  exactly. The 90 DEGREES has no term that states it — it enters as the tie-break
  between the quadratic's two roots, then as the elliptic operator's own tendency,
  helped by the along-wall source keeping the first interior line from shearing
  against the wall. The direct condition is the Steger-Sorenson projection onto
  `r_s` and it is the first rejected row in the table above: it goes as `1/h²`,
  asks for about -21 here, clips, and destabilises. **The measured consequence is
  that the angle improves and then TURNS** — 32.04° -> 29.90° at twenty sweeps,
  31.55° at thirty, 34.78° at forty — while the height does NOT turn with it
  (0.089% / 0.094% / 0.098%). So the useful cap is set by the angle, and the phrase
  "control functions drive wall-normal orthogonality" is true only in that indirect
  sense. Recorded because the alternative is a reader inferring a term that is not
  there; the header of `src/MbControl.cpp` says the same thing at the arithmetic.

- **THE O-GRID NEGATIVE CONTROL IS STILL UNMET, is WORSE THAN #82's, and NO SINGLE
  CAP MEETS BOTH OF #80's BULLETS.** All three, because the first alone reads better
  than the truth. 2.250° -> 3.632° at one sweep, where #82 got 3.312° — so this
  ticket moved that number the wrong way — and at the cap where the C-grid criterion
  is met (20) the O-grid sits at 12.036°, 5.3x #55's. There is no one
  `MB_SMOOTH_ITERS` satisfying #80's C-grid bullet and its O-grid bullet together,
  and whoever closes #80 has to name the cap its acceptance is claimed at rather
  than quoting one figure from each case's best setting. The wall first cell,
  though, goes the other way and is now BETTER than #55's: 0.0812% -> 0.0390%. #82
  attributed the regression to the frozen radial interfaces through the run's own wall
  table — the row pinned at the declared height where an interface held it and 9.13% off
  mid-block. **That localisation no longer works, because this ticket fixed the thing it
  was reading**: the wall table now says 0.00% all the way round. So it was measured
  directly instead, on the exported quads: the worst corners of the smoothed O-grid sit at
  **theta = 0, 90, 180 and -90 degrees at radius ~3.43**, which is mid-block on the four
  DECLARED RADIAL INTERFACES (`r0`..`r3`, corners `b0`..`b3` to `f0`..`f3`), while the
  UNSMOOTHED mesh's worst corners sit at radius 10.0 on the faceted outer circle. The cost
  is a kink along a frozen shared edge; #84 unfreezes them. Recorded as unmet and owned,
  on the same terms #82 recorded it.

  Why the control cannot rescue it: for a polar map the controlled equation is not
  satisfied even with exact 1-D sources. Working it through, `b = 0` and the `psi` term
  cancels against `R''/R'`, leaving a residual `-a R Δθ²` that would need
  `psi_extra = R'/R` — a genuine 2-D curvature term that no 1-D Thomas-Middlecoff source
  carries. That is a property of the formulation, not of the freeze, and it is why the
  O-grid moves at all before the interfaces get in the way.

- **WHAT #83 COST, in three places, none of them papered over.**
  1. **A fold from smoothing is REACHABLE on the shipped files again**, reversing #82's
     blind spot. That kernel folded nothing at any cap either case was driven at; this one
     folds 4 cells on the C-grid by a cap of 100 and 288 by 500. Holding a graded wall
     through a conditionally stable iteration is what costs it, the run reports it through
     the inverted-cell count and exit 9, and the surface gate now asserts that path on a
     real file rather than only on a folded declaration.
  2. **A deep re-entrant notch is no longer fully repaired.** `notchedBox(11, 9, "0.35")`
     folds 8 cells in the fill; #82's kernel converged and repaired all 8, and this one
     diverges at sweep 9 with 1 left. The control HOLDS the declared boundary distribution,
     and on a re-entrant notch that distribution is part of what folds the fill — so the
     solve has less room. Check 50 pins the direction with a floor rather than quietly
     weakening its claim, and moved its full-repair half to the 0.45 notch, which converges
     in 347 sweeps and repairs its 1 fold.
  3. **Neither shipped case converges OR diverges any more** — the residual PLATEAUS
     (6.8e-05 at a cap of 50000 on the C-grid against a best of 2.5e-05 at sweep 415, a
     factor of 2.7 and so short of `MB_SMOOTH_DIVERGE_FACTOR`; 1.2e-04 on the O-grid at
     20000). Both endings therefore moved house, which is a SWAP in coverage rather than a
     loss: #82 could reach them only on the shipped files, having tried 26 synthetic
     fixtures that all converged, and #83 found that the notched box's DEPTH picks the
     ending — 0.50 converges in 290 sweeps, 0.35 diverges at 9 — so check 49 drives both in
     milliseconds, with the rollback checked the same round-trip way the surface gate
     checked it. The surface gate keeps the stability limit, which only a real file reaches.

- **THREE #82 CHECKS HAD TO BE REVERSED, and each was written to be.** They pinned the
  defect this ticket removes, so they are reversed rather than deleted — the same treatment
  #43's iteration-count reversal got.
  - **Check 45** asserted the first cell off the wall gets **1.5x taller** within four
    sweeps. It is now held to 1.6e-16 relative, and the same sweeps run by hand with both
    sources zero still lose it — so the check proves the CONTROL holds the wall and not the
    operator.
  - **Check 47** asserted a GRADED rectangle is NOT a fixed point, and said why: plain
    Winslow's fixed point is the harmonic map, whose interior spacing is uniform, "holding
    it is #80's ticket 3, not this kernel". It is ticket 3 now: the graded square is held
    to rounding over 500 sweeps and the solve **converges on its first sweep**. That is
    #83's headline, and it came out of #82's own check rather than out of a new one.
  - **Surface group 4** asserted the wall figure gets at least 10x worse and that the MEAN
    does not improve. Both flipped.

- **A DUPLICATE WARNING, caught by an existing check.** Rewriting the capped advice left
  #82's block in place beside the new one, so every capped run pushed the warning TWICE.
  Nothing about the text was wrong and the mesh was unaffected; what failed was check 49's
  `w1.size() == 1`, which exists for exactly this and had looked like a formality. Worth
  recording because the review axis that would have caught it by reading is the one this
  repo keeps finding things with.

- **THE `.dat` READER, THE GUI AND THE PARITY GATE ARE UNTOUCHED**, because the control
  functions add no key. #80 requires every mesh key to land in the C++ config and the GUI
  field-spec table together, and the way to satisfy that requirement is to need no key: a
  selector over one answer is the abstraction the no-inert-alternatives rule exists to
  prevent, which is the same call #82 made when it deleted the Laplacian instead of keeping
  it behind an enum.

- **WALL NODES DO NOT SLIDE, and the ticket required that decision to be taken and stated.**
  Sliding is the stronger tool and is expressible — a bound edge's polyline is known — and
  it is refused because on this path the DECLARATION is the authority: a corner attaches at
  a declared arc-length position and an edge's spacing comes from a declared law, so a
  smoother that redistributed a wall would overwrite the document it was asked to honour.
  The concrete contradiction is with this ticket's own deliverable: `MbWallSpec`'s requested
  height is derived from the perpendicular edge's declared `ds`, so sliding would move the
  along-wall distribution while the request stayed put, and nothing could then say which of
  the two was right. **So `BL_USE_ANALYTIC_GEOM` gains NO reader**, the read and unread
  survivor lists are unchanged and stay disjoint, and it is still a declared survivor
  nothing reads — kept that way by a decision rather than by omission. #48's "survives as
  the projection basis" is a claim about a projection this path does not perform.

- **GOLDEN: 18 of 19 SAME at 0.000e+00, and the nineteenth recaptured.** `mb_cgrid_smooth`
  — the only case whose nodes come from the smoother — moved 2.000 units at its worst node
  with all 11520 `.cel` cells' connectivity redrawn. #81 wrote that case so a kernel change
  would show up here as a number; it has now done so twice, and both times it was the only
  one of the nineteen that moved.

- **NAMED BLIND SPOTS.** The smoothed mesh is STILL never given to the solver or the grid
  converter — and unlike #82, that is now a GAP rather than a non-question, because 0.09%
  off the requested wall height is exactly the boundary layer #80's acceptance asks for. It
  belongs to #85. **Nothing bounds the cap automatically**: the stability limit is reported
  after the fact by the inverted-cell count, while the DIVERGED path stops at its best
  residual — two signals, one acted on. And the saturating-AND-descending regime is reached
  by no synthetic fixture, only by the shipped C-grid at a cap of 100, so that branch of the
  advice has one gate.

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

