---
paths:
  - include/MbControl.hpp
  - src/MbControl.cpp
  - include/MbShared.hpp
  - src/MbShared.cpp
  - include/MultiBlock.hpp
  - src/MultiBlock.cpp
  - include/Config.hpp
  - src/cli.cpp
  - tests/cpp/test_multiblock.cpp
  - tools/PreProcessor/tests/test_multiblock_smooth_surface.py
  - tools/PreProcessor/tests/test_multiblock_quality_gate.py
---

# Mesher rules — the `MESH_MODE 1` smoother (`MB_SMOOTH_ITERS`)

Loaded on demand when a smoothing module, the seam it runs inside, the key's two doors or either
of its two gates is read. **The TENTH rule file, and the second taken for CONTEXT rather than for
coverage** (#89 took the ninth): every glob here is also in
`.claude/rules/mesher-multiblock.md`'s list, so this file OVERLAPS rather than partitions, and a
session editing `src/MbControl.cpp` or `src/MultiBlock.cpp` loads BOTH. That is the intended
shape — this file answers "what MOVES after the fill", that one "what does the document declare
and how is it filled" — and it is why #85 could take it without widening any coverage.
**WHY IT EXISTS AT ALL is a budget fact and worth stating plainly**: `mesher-multiblock.md` came
out of #84 at 121 characters under `RULE_BUDGET`, its design note recorded that #85 would inherit
the problem, and #85 did — the rules below would not fit. The alternative was a third compression
pass over other tickets' text, which both of #84's review axes had already called the wrong shape.
Two of the globs are NOT smoothing modules and carry these rules from outside them —
`include/Config.hpp`, where the key and its DEFAULT live and where a negative count is refused by
name, and `src/cli.cpp`, which prints the before/after banners and the two machine-readable lines.
Rules only: the rationale — the measurements, the dated acceptance runs, the injections, the
reversals and the named blind spots — is `docs/design_notes/mesher.md`, the SAME note the other two
mesher rule files point at. Read that note before overruling a rule here, and when a rule changes
update BOTH.

**SMOOTHING is a STAGE inside the seam, its kernel is WINSLOW, that kernel is CONTROLLED (#83), and
since #84 it runs ACROSS the shared edges** (`MB_SMOOTH_ITERS`, **default 20 since #85** —
`Config::mbSmoothIters`, see the default's own block below; `src/MultiBlock.cpp`'s `mbSmoothBlocks`
between the fill and the split; #81 built the stage with a Laplacian, #82 replaced the kernel and
DELETED that one, #83 gave it source terms, #84 unfroze the interfaces and cuts). An elliptic solve
over each block's movable nodes under a cap. **Through #81-#84 the default was 0 and all eighteen
pre-existing golden cases were unchanged at every step** (18/18 SAME at 0.000e+00, `mb_cgrid_smooth`
the only one that moved any of the four times) — the property that made each kernel change
attributable, and the one #85 deliberately spent.
**Every measurement, table and reversal below: `docs/design_notes/mesher.md`.**
- **WHICH NODES MOVE IS `mbSmoothPlan`'s ANSWER, stated rather than read off a loop**
  (`include/MbShared.hpp` + `src/MbShared.cpp` in `hybmesh_pure`; #84). FROZEN: a node on an edge
  whose declared KIND is `wall` (the outer boundary is the DOMAIN, not the discretisation, and a
  bound node would leave the geometry it was attached to by arc length), and every DECLARED CORNER.
  MOVES: everything else — interior to a block, or interior to an `interface` or a `cut`. The wall
  gate is `MbResult::wallSpecs`, the list `measureMbQuality` and `mbWallTargets` walk; no kind
  string is compared and NO POSITION is compared anywhere in that module.
- **REVERSES #81: a node interior to an interface or a cut MOVES, and the objection that froze it
  is ANSWERED rather than dropped — the node is moved ONCE, in ONE frame, from ONE stencil.**
  Why: `docs/design_notes/mesher.md`, "#81's OBJECTION WAS REAL AND IS ANSWERED". A node on a
  block's south side has no `j - 1` row inside it; the row that IS its `j - 1` is the NEIGHBOUR's
  own first interior line, and `MbGhostFrame` is that continuation, matched station for station by
  node ID and never by distance. Nine real nodes, nothing averaged, no tolerance needed between a
  1e-7 wall spacing and a 1e-1 far-field one. **The four DIAGONAL corners of that frame have no
  answer and are not given one** (`at()` returns -1, not a clamp).
- **THE FOUR-WAY CORNER DOES NOT MOVE**: a corner is a declared POSITION, and the one node with no
  frame to be moved in — up to four blocks and five edges, needing exactly those absent diagonal
  ghosts. **ONE test, not two**: "on two of this block's sides at once" IS the declared-corner set
  here (an edge runs corner to corner, and the fill refuses a block whose sides do not meet at four
  shared corner nodes), so a separate corner-id set was written first and REMOVED — two sufficient
  conditions for one rule mask each other, and each injection came back inert. `hgrid()` makes it
  falsifiable: a corner on four interfaces and NO wall, where the C-grid's trailing edge is on the
  airfoil and the wall half would freeze it anyway.
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
  frame rather than on an index — and the guard names EVERY line the station reads, cross term
  included, because a guard needing an argument stops holding when the argument moves.
- **`MbResult::sharedEdges` IS PUBLISHED BEFORE THE SMOOTHER, not after the split.** One line too
  late until #84: the freeze rule reads that list, so with it empty every shared node stayed frozen
  and the ticket was a silent NO-OP behind 106 green tests. A PUBLICATION moved, not a decision —
  nothing there reads a cell or a position, and fill-then-smooth-then-split is unchanged.
- **`MbSideWalk` / `mbSideWalk` LIVE IN `include/MultiBlock.hpp`**, beside `mbSideAxis` and for its
  reason: three readers in two files, having been written out three times inside `MbControl.cpp`
  alone. Its `tt` may be -1 or `m` — one step OUTSIDE the block — and `MbBlock::nodeAt` is never
  handed those. `MbControl.cpp` keeps a SECOND, in-block accessor: the control's differences read
  the ghost frame, while `mbWallTargets` and `mbWallResidual` stay the RULER's measure.
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
  a wall": the module walks the seam's own published list, the same one `measureMbQuality` walks.
  The NAMES `MbControl.cpp` and `MbShared.cpp` are load bearing — this file's globs cover `Mb*` as
  patterns, so a `MultiBlockControl.cpp` or `MultiBlockShared.cpp` would have arrived ruleless.
- **THE TARGET IS THE RULER'S OWN BLEND, NOT ARC LENGTH.** `MbWallSpec` carries the height at a
  side's two corners; between them `measureMbQuality` blends LINEARLY IN THE LOGICAL COORDINATE, so
  the control aims at exactly that. Arc length along the wall is the tempting answer and is WRONG:
  it drives the mesh at one number while the acceptance gate measures another — the
  second-answer-to-one-question defect, which the edge-distribution warning made in mirror image by
  comparing a CHORD against a request in arc length. **The measure of the request and the measure of
  the achievement must be the SAME measure.**
- **THE OFF-WALL SOURCE IS SOLVED, EXACTLY, FOR THE DISTANCE THE RULER MEASURES
  (`|update - p_wall| = requested`), at the FIRST INTERIOR ROW ONLY** — one quadratic in one scalar,
  the root taken landing nearer `p_wall + requested * inward_normal`, **which is where the 90-degree
  half of the declaration enters**: the tie-break between two points at the same distance.
- **THE TWO HALVES ARE NOT DRIVEN EQUALLY, and the name "control functions" overstates one.** The
  HEIGHT is solved for exactly. The 90 DEGREES has NO term stating it — that tie-break, the elliptic
  operator's tendency, and the along-wall source keeping the first interior line matched to the wall
  so the two do not shear. A DIRECT condition on the angle (Steger-Sorenson projected onto `r_s`)
  goes as `1/h²`, clips and destabilises, and is one of **three weaker versions measured and
  rejected** with the near-wall 1-D limit and a least-squares solve for the target POSITION; figures
  in `docs/design_notes/mesher.md`'s "least squares for the target position".
  Under #83 the angle therefore IMPROVED AND THEN TURNED (32.04° -> 29.90° at twenty, 31.55° at
  thirty, 34.78° at forty). **SUPERSEDED by #84:** that turn is gone and was never the angle
  condition's doing — it was the interior shearing against a frozen seam, and the max now falls
  monotonically to 26.49° at a cap of 100, turning only past 150.
  Why: `docs/design_notes/mesher.md`, "THE MAX IS IDENTICAL TO THREE DECIMALS".
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
  other. **#84's own contribution is SEPARABLE and is in the MEAN and in the CAP**, not in the worst
  cell, whose location is set by the wall row #83 froze: at twenty #83 was at 4.301° mean against
  #84's 3.821° with the max identical to three decimals, and at forty 34.78° against 28.55°. The
  full four-kernel table, both cases, every cap: `docs/design_notes/mesher.md`.
- **THE RUN REPORTS WHICH NODES IT WAS FREE TO MOVE** (`MbResult::smoothMoved` /
  `smoothMovedShared`, a `Movable nodes` banner row, `moved=` / `moved_shared=` on
  `HYBMESH_MB_SMOOTH`; NEGATIVE when no sweep ran, on `smoothResidual`'s rule). The freeze rule is a
  decision about the DECLARATION, so a run must SHOW it. C-grid 5600 of 5920 with 140 shared,
  exactly the interior of its four shared edges (23+39+39+39); O-grid 4512 of 4704 with 188.
- **THE NEAR-LEADING-EDGE CELLS ARE MEASURED ON THEIR OWN, because a mesh-wide average can improve
  while the region the solver diverged in does not.** #57's worst corner is at (0.0134, 0.0196);
  over the ten quad cells touching the airfoil between x = 0.005 and 0.030 the region goes
  **32.04° / 26.90° -> 29.90° / 24.91°** at twenty sweeps. The instrument is a quad reader in the
  surface gate, not a new metric: the METRIC is the ruler's and the gate adds a SELECTION, validated
  by reproducing the ruler's whole-mesh figures off the same code first.
- **#80's O-GRID NEGATIVE CONTROL IS STILL NOT MET — BY 1.2%, AND THE RESIDUE IS THE FACETED WALL's
  RATHER THAN THE INTERFACE's.** All three clauses: the first alone reads worse than the truth, and
  dropping it reads better. A case already at 2.250° comes out at **2.276°** at EVERY cap from 1 to
  150, against #83's 3.632° at one sweep and **12.036° at twenty** — so #83's "no single
  `MB_SMOOTH_ITERS` satisfies both of #80's bullets" is **GONE**. The mean is exactly #55's 1.875°,
  which is STRUCTURAL rather than a strong result (a **96-gon's** every quad corner deviates by half
  the sector angle whatever the radial distribution is — 360/96/2, and the ring IS 96 nodes) but
  does say the grid is POLAR again. **WHERE THE KINK WENT, measured**: #83's worst corners sat
  MID-BLOCK on the four declared radials, #84's sit one line in from the faceted outer circle, and
  the mid-block band's own cells come out BETTER than the fill left them.
  **SUPERSEDED by #93:** what that wall is faceted BY is a polyline COARSER than the mesh reading it
  — 80 facets under 96 nodes — so the cause is the sampling ratio, and #83's "wall nodes do not
  slide" is untouched rather than the thing to revisit.
  Why: `docs/design_notes/mesher.md`, "THE O-GRID's RESIDUE IS A SAMPLING RATIO, NOT A FROZEN WALL".
- **A fold from smoothing is an ORDINARY inverted mesh**: counted after the sweeps, exported, exit
  9, no new code. **And it is REACHABLE on the shipped files**, reversing #82's blind spot — the
  C-grid folds 184 cells by a cap of 400, so the surface gate asserts exit 9 on a real file. **The
  O-GRID's FOLD IS INVISIBLE TO NON-ORTHOGONALITY**, a limit of the RULER: at a cap of 300 it folds
  192 cells while max non-orthogonality reads 2.274°, because two adjacent radial lines have swapped
  order and the folded cells stay nearly rectangular. Only the inverted count sees it.
- Gated by `tests/cpp/test_multiblock.cpp` 40-56 (7 injections from #81, 13 from #82, 14 from #83,
  11 from #84, dated in that file), `tools/PreProcessor/tests/test_multiblock_smooth_surface.py`
  (11 groups on the SHIPPED C-grid AND O-grid, importing #53's own conformity measure rather than
  re-inventing it) and the `mb_cgrid_smooth` golden case, recaptured deliberately by #82, #83 and
  #84 — **the only one of the nineteen that moved any of the three times.**
  **AN INERT INJECTION IS ANSWERED WITH A CHECK OR A FIXTURE**: four of #83's needed a check, one
  needed `wallSquareTwoEnds` (the first declaring DIFFERENT heights at a wall's two ends), and #84
  needed `hgrid()` (a corner on NO wall) and `wallTwoBlocks()` (the only fixture where a wall's END
  station is a shared edge). THREE ACROSS THE WHOLE GATE stay INERT, named there — one of #82's
  thirteen and TWO of #84's eleven: the weld match (unfalsifiable on a correct document) and the
  declared-corner freeze ALONE (held twice).
  **The DIVERGED ending came BACK to the shipped files with #84** — #82 reached it there, #83's
  residual plateaued instead, #84's C-grid diverges at sweep 1111 and hands back that iterate. The
  CONVERGED ending is reachable only on the C++ test's notched box (0.50 converges in 290 sweeps,
  0.35 diverges at 9); the stability limit only on the shipped files.

**SMOOTHING IS ON BY DEFAULT, AT A CAP OF 20, AND THAT IS A DECISION (#85).** It was 0 through
#81-#84 so every increment landed with the golden family untouched and each kernel change was
attributable — a build-time convenience, which expires once the last thing that moves the numbers
has landed.
- **TWO DECLARATIONS AND THEY MUST AGREE: `Config::mbSmoothIters` and
  `MeshConfig.mb_smooth_iters`, both 20.** The parity gate
  (`tests/test_gui_cpp_config_parity.py`) compares key, TYPE and DEFAULT in both directions, so a
  default that disagrees is a mesher and a GUI producing different meshes from one document.
- **`MbParams::smoothIters` STAYS 0, and the difference is deliberate rather than missed.** That is
  the SEAM's answer to a caller who says nothing, and "say nothing, get the fill and the split and
  nothing else" is the contract the pure layer's own checks need: about forty of them are about
  parsing, filling, welding, splitting or BCs, and a smoother underneath would move the positions
  they assert on for unrelated reasons. **"What is the default" therefore has two answers** — the
  PRODUCT's and the SEAM's — and which one is meant is named at both declarations rather than
  inferred. Check 40 says `MbParams{}` and no longer says "the default".
- **20 IS THE SAFE CAP, NOT THE BEST ONE MEASURED**, and the derivation is stability rather than
  quality: the C-grid's worst angle keeps improving to a cap of 100 (26.49° against 29.90° at
  twenty), but this iteration eventually folds cells and that limit is a property of the TOPOLOGY,
  so a default has to leave room on a topology nobody has measured. **THE MARGIN IS EXACTLY TEN AND
  IT WAS BISECTED** (2026-09-08): the O-grid is sound through a cap of 200 and folds 192 cells by
  225, the C-grid sound through 300 and 184 by 400. An earlier draft claimed "an order of magnitude"
  off a 150/300 bracket, which a review read as 7.5× — the claim survives, but only because it was
  then measured. 20 is also where #83's and #84's tables are densest, so a regression names a figure
  the record already holds. **An expert on a known topology should raise it — that is what a cap is
  for.**
- **A RECTANGLE IS A FIXED POINT, WHICH IS WHY THE FLIP MOVED THREE GOLDEN CASES AND NOT NINE.**
  Measured at 20 on all five shipped multi-block configs: `cavity` is IDENTICAL bit for bit and
  `square` unchanged to 3.5e-16 over 255 of its 441 nodes — **not the same claim, and this file said
  "both identical" until a review checked it** — then `hgrid` 3.099/0.445/0.146% ->
  2.859/0.435/0.081%, `ogrid` 2.250/1.875/0.081% -> 2.276/1.875/0.044%, `cgrid` 32.044/4.562/0.437%
  -> 29.895/3.821/0.097%. Zero inverted everywhere. Golden: **16 of 19 SAME, 3 DIFF** —
  `mb_hgrid`, `mb_ogrid`, `mb_cgrid`, recaptured deliberately; `mb_cgrid_smooth` unchanged because
  an explicit `MB_SMOOTH_ITERS 1` beats the default, and the nine hybrid-path cases are `MESH_MODE
  0` and untouched. Real node movement 0.8% / 1.3% / 2.1% of each case's extent.
- **THE RUNTIME COST IS NIL** — 0.26 s either way on both shipped cases, so there is no performance
  argument on either side of the decision.
- **A FOLD IS NOT SMOOTHED INTO A PASS.** The quality gate's dart declaration folds 16 cells
  unsmoothed and 8 at the default — the solve genuinely repairs half of it — and still exits 9 and
  still exports. Pinned by `test_multiblock_quality_surface.py` check 4b, because a default that
  quietly turned a bad declaration into a good mesh is the one way this flip could hide something.
- **EVERY GATE THAT MEANS "UNSMOOTHED" NOW SAYS `MB_SMOOTH_ITERS 0`**, and four had to be changed:
  `test_multiblock_quality_surface.py` (the whole file — its subject is the RULER on the algebraic
  fill), `test_multiblock_ogrid_surface.py` check 7 (the spacing law's invariance across a
  propagated count), `test_multiblock_smooth_surface.py` group 1 (whose claim was "the default is
  silence" and is now "zero sweeps is silence", plus a new check that the default is NOT zero) and
  `test_multiblock_cgrid_surface.py` check 3, whose printed figure was labelled BASELINE and had
  silently become the smoothed mesh. **A stale label on a live number is the failure mode of a
  default flip**, and that one shipped for a commit before the label was read.

**THE BASELINE IS A GATE (`tools/PreProcessor/tests/test_multiblock_quality_gate.py`; #85).**
- **ONE OWNER FOR THE THRESHOLDS, each stated with the run that produced it**, so a regression
  names the figure it broke rather than reporting that quality got worse. The two case gates keep
  printing their figures and keep asserting the report's "a negative means not measured" rule;
  neither carries a second copy of a bar.
- **MEASURED AT THE DEFAULT, and the gate pins the default itself** (check 1 reads `cap=` off a
  run), so it cannot come back green because someone turned smoothing off.
- **C-grid bars, all four met**: inverted 0, max < 32.044°, mean < 4.562°, wall <= 0.4368% — #57's
  own recorded baseline, which check 3 of the C-grid gate re-derives at zero sweeps so the bars
  cannot drift away from the mesh they were written against. Achieved 29.895 / 3.821 / 0.0968%.
- **#80's O-GRID BULLET IS NOT MET AND THE GATE DOES NOT PRETEND IT IS.** It asks for nothing worse
  than 2.250° / 1.875° / 0.0812% and the worst angle is **2.276°**, 1.2% worse. The bar is therefore
  #85's own measurement rather than #55's — the honest way to hold a number that is not the one the
  epic asked for — and check 4 asserts the GAP stays under 2% so it cannot grow in silence.
  **SUPERSEDED by #93:** #55's 2.250° bar is itself a SAMPLING artefact of the shipped 80-facet far
  field, the case's floor is 1.875° with no code change, and closing it is #95's geometry work
  rather than a sliding wall or a tighter threshold. The bar and check 4 are unchanged, because the
  shipped geometry is.
  Why: `docs/design_notes/mesher.md`, "THE O-GRID's RESIDUE IS A SAMPLING RATIO, NOT A FROZEN WALL".
- **AN UPPER BOUND CANNOT CATCH A SMOOTHER THAT STOPPED WORKING**, since a mesh that never moved
  sits under three of the four bars. So check 3 drives each case at 0 as well and asserts the
  DIRECTION — the wall first cell strictly better on BOTH cases, and both angles strictly better on
  the C-grid.

**GATE 2 ON A SMOOTHED MESH: RUN, DATED, AND IT PASSES (#85).** Four hand-built
mesher -> getPGrid -> unicones runs on 2026-09-07, C-grid and O-grid at 0 and 20 sweeps, all
EXIT 0 / 0 / 0 at `cfl 0.6` with 100 iterations and no NaN. The full record, the operating point
and what it does NOT exercise are `tools/PreProcessor/tests/test_multiblock_cgrid_surface.py`'s
docstring, beside #57's. **THIS CHECKOUT HAS A SOLVER TREE** — `solver/execute/unicones.eqn6.mac`
and `solver/preprocess/getPGrid/work/getPGrid` — which corrects a "no solver tree" claim that had
survived a review in `test_multiblock_weld_surface.py`. CI still has neither, so every recorded run
is a dated quotation.
- ~~**THE `.bnd` NAME -> SOLVER FLAG MAPPING IS STILL NOT EXERCISED.**~~ **CLOSED BY #91**, and
  kept here as a specimen rather than deleted. #85 measured why the pipeline route did not close
  it: getPGrid writes the `<case>.bc.def` segment table ITSELF, does not know `farfield`, and
  defaulted those patches to a no-slip wall while no Python rewrote it — so driving
  `config/pipeline/multiblock_cgrid_demo.json` solved a body in a CLOSED VISCOUS BOX (exit 0, 100
  iterations, no NaN, but NOT the recorded operating point), and the flag-1 in every recorded run
  was written into the `.bc.def` BY HAND, as #55's and #57's were. #91 made the headless runner
  derive the table from the mesh's own patches (`pipeline_runner.derive_bc_definitions`, using
  #90's service), so the PIPELINE now reproduces that operating point instead of approximating it
  — dated run 2026-09-08 in `tools/PreProcessor/tests/test_pipeline_bc_from_mesh.py`'s docstring.
  The mapping itself is now gated token-by-token against getPGrid's own `getBCType` C++ by that
  file's check 10, with one case-fold collision pinned (`nozzle`). **A declaration still wins**: a
  script that states `bc_definitions` is never overwritten, which is why a GUI-authored `.hws` is
  unaffected.

## Named blind spots

Consolidated here rather than trailing each rule, so a coverage claim can be checked against
one list — the habit `.claude/rules/mesher-multiblock.md` set and #85 carried across with the
rules. **One of that file's own blind spots still covers this arc**: nothing runs the solver or the
grid converter on a FOLDED mesh, which is `MbQuality`'s sharpest and is not duplicated here.

- ~~**Non-orthogonality is a BASELINE here, never a gate.**~~ **SUPERSEDED by #85:** it is a GATE
  (`tools/PreProcessor/tests/test_multiblock_quality_gate.py`), because #80's arc exists to move
  exactly these numbers and a quality feature nothing enforces is a claim. #57's reason — that
  transfinite interpolation was not expected to beat the BL path, and that a binary gate stops "not
  pretty enough yet" blocking a release — held until the last kernel landed. Kept here as a
  specimen rather than deleted.
  Why: `docs/design_notes/mesher.md`, "THE BASELINE BECOMES A GATE".
- **NOTHING CAN SEE THE SMOOTHING STAGE'S POSITION.** Injection Y — the whole sweep block moved
  past the split — is INERT, because every reader downstream of it is id-only today. The
  fill-then-smooth-then-split ordering is a design rule held by a comment, not by a gate. **Nor is
  the position of a PUBLICATION relative to its reader**, which #84 found the hard way — see the
  `sharedEdges` rule above.
- ~~**The smoothed mesh is never given to the solver or the grid converter.**~~ **RESOLVED by #85**,
  which ran four of them and recorded the figures. What remains is narrower and is #57's own limit,
  not this arc's: gate 2 is ONE operating point (M 0.2, Re 200, zero incidence, 100 iterations,
  `cfl 0.6`), "the solver runs" is the whole claim, and nothing compares a pressure distribution
  with anything — not even the smoothed run against its own control, which is the obvious next
  question and is not answered.
- **THE LOSING BLOCK'S PERPENDICULAR WALL REACHES A SHARED LINE AT ZERO WEIGHT.** Ownership picks
  ONE frame and `mbControlField` walks only that block's targets, so a wall the OTHER block declares
  perpendicular to the line contributes nothing. The perpendicular-wall score REDUCES this but
  cannot remove it, and on a TIE one set of two is dropped. Harmless on the shipped cases, whose
  ties are symmetric; the residue of moving the node once rather than reconciling.
- **NOTHING MEASURES THE C-GRID's FREED INTERFACES ON THEIR OWN TERMS.** The O-grid's four radials
  lie at four known angles so a surface gate can select the band; the C-grid's three have no such
  handle from outside a `.vtk`, so what is read there is the WAKE and the whole-mesh figures. The
  C++ test reaches those lines by node id and pins the MECHANISM, not the quality.
- **#84's OWN WAKE-CUT CRITERION IS UNREACHABLE HERE and the PREMISE is what is wrong**: the fill
  already leaves all 48 cells against that straight, on-axis line EXACTLY orthogonal, so freeing it
  COSTS 0.018° mean. The worst lines were the radial interfaces, which improve. Figures: the note.
- **NOTHING BOUNDS THE CAP AUTOMATICALLY.** The stability limit is real — bisected 2026-09-08, the
  C-grid is sound through a cap of 300 and folds 184 cells by 400, the O-grid sound through 200 and
  192 by 225 — and it is reported after the fact by the inverted-cell count and exit 9; nothing
  stops the solve at the last sound iterate the way the DIVERGED path stops it at the best residual.
  The two are different signals and only one of them is acted on. **This bullet said "folds past
  about forty sweeps" until #85**, which was #83's figure and had been superseded by #84 two tickets
  earlier without this line moving — the shape a blind-spot list is supposed to prevent.
- **The before/after tables are dated quotations**, not re-measured: the gates assert a DIRECTION
  with a floor, so a kernel that stopped moving anything is caught while one that moves things
  differently is free to.
- **NOTHING RELATES THE SMOOTHER's OWN EXCESS TO THE GEOMETRY UNDER IT.** #93 measured that the
  O-grid excess over the unsmoothed baseline is FACETING-driven — exactly zero wherever the
  polyline's facet count divides the mesh's node count, +0.026° at the shipped 0.833 ratio — and
  none of that is gated: the quality gate reads ONE geometry, so a case whose excess is really its
  far field's sampling reports as the kernel's. It replaces no rule: the claim it corrects — that
  the residue was the frozen wall's — was never a coverage limit.
  Why: `docs/design_notes/mesher.md`, "THE O-GRID's RESIDUE IS A SAMPLING RATIO, NOT A FROZEN WALL".
