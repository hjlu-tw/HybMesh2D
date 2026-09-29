---
paths:
  - include/MbQuality.hpp
  - src/MbQuality.cpp
  - src/cli.cpp
  - tests/cpp/test_mb_quality.cpp
---

# Mesher rules — what a `MESH_MODE 1` run MEASURES and PRINTS

Loaded on demand when the quality module, the banner that prints it or its C++ gate is read.
The TWELFTH rule file, and the third taken because one was FULL rather than for coverage
(#85 and #137 are the other two): `.claude/rules/mesher-multiblock.md` had 197 characters of
slack when #153 arrived, and `docs/agents/rule-file-style.md` says in as many words that when a
rule file runs out of budget the answer is a SPLIT and not a harder compression. #153's first
attempt WAS the harder compression — it funded a 1.6k block by trimming thirteen passages and
left 3 characters of slack — and a review axis is what sent it back. The text here is that
compression reverted and then RELOCATED: the two sections moved verbatim, zero identifiers lost.

**It is a different QUESTION, not just a smaller file.** `mesher-multiblock.md` answers "what
does this document declare, and how is it filled"; this file answers "and what does the run then
MEASURE and PRINT about the mesh". That distinction is not invented by the split — it is written
inside the text that moved, as the reason `MbQuality` is its own module at all ("a different
question ('is this mesh usable?' vs 'what does this document declare?'), and a pure function of a
finished mesh").

**All four globs are ALSO other rule files' and the overlap is intended.** `src/cli.cpp` is
`mesher-multiblock.md`'s and `mesher.md`'s, because it prints this banner AND carries that path's
adapter; every one of the four is under `mesher.md`'s `src/**` / `include/**` / `tests/cpp/**`.
A session editing `src/MbQuality.cpp` therefore loads THREE mesher rule files, which is #89's
precedent and not an accident. **The CELL-SHAPE METRIC ITSELF is `mesher.md`'s**
(`include/CellShape.hpp`, one definition shared with the hybrid path); what is here is what the
multi-block report does with it.

Rules only: the rationale — the measurements, the dated acceptance runs, the injections, the
reversals and the named blind spots — is `docs/design_notes/mesher.md`, the SAME note the other
two mesher rule files point at. Read that note before overruling a rule here, and when a rule
changes update BOTH.

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
  all four `quad_midline_ratio_*` are identical to every digit the line prints (#129 wrote
  "bitwise"; both sides are read off a six-decimal line, so the check cannot see a
  difference under 5e-7 and no surface carries more precision to read).
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
  - **THE SHIPPED C-GRID'S max 3147.958 IS THE SAME QUOTIENT, and it is ARITHMETIC** (#140). Its
    worst cell is the LAST cell on the wake cut, at the outlet: **3.143570** — the last of the
    wake's 24 intervals, `count` 25 with `ds_start` 0.005 over a 19-chord span — over **0.000998606**,
    the first radial interval the two outlet-plane edges declare as a wall end and
    `BL_INITIAL_THICKNESS 0.001` sizes. Both numbers are spacings the DOCUMENT asks for, so a fix
    would change the TOPOLOGY's wake count and not the mesher; the negative control is that a 26th
    wake node moves the max to 3003.344 and moves no other case.
  - **EVERY SHIPPED CASE'S THREE FIGURES ARE PINNED, AND A PIN IS NOT A THRESHOLD** (#140). All
    five shipped multi-block configs run in `test_multiblock_shape_surface.py`, and each one's
    median / p95 / max is held against the day it was measured by a check whose label names the
    case. A threshold says a number is BAD; a pin says it MOVED, and its fix is either "re-measure"
    or "this is the regression". The band is DERIVED from the pin: a case at the metric's floor
    (square, cavity — all three exactly 1.0) is exact, every other is `PIN_TOL` 1e-6 relative, and
    the toleranced ones carry a negative control proving the band is narrower than a real change
    (the same case at `MB_SMOOTH_ITERS 0`; the thinnest margin is the O-grid's max at 7.6x the
    band, which is the number to quote rather than the C-grid's comfortable 1.4e-3). The two at
    the floor run that control too and assert the sweeps move them NOT AT ALL — the branch's own
    premise measured rather than restated as the condition it was selected by.
  Why: `docs/design_notes/mesher.md`, "THE SHIPPED C-GRID'S 3147.958 IS THE SAME ARITHMETIC".
  - **The `.provenance.json` sidecar gains `mesh.quality`** — `metric`, `cells`, `median`, `p95`,
    `max` — fed by the SAME report object the banner and the machine line read, so the three
    cannot disagree. It is the contract #131 and #132 read instead of recomputing.
  Why: `docs/design_notes/mesher.md`, "CELL SHAPE: three numbers, one definition".

**THE REPORT SEPARATES THE WALL-CLUSTERED QUADS FROM THE REST, BESIDE THE WHOLE-MESH FIGURES AND
NEVER INSTEAD OF THEM** (`wallBandMask` in `src/MbQuality.cpp`, `printMbQuality` in `src/cli.cpp`;
#144, parent #128). The shipped O-grid's whole-mesh p95 is 23.662 against a median of 1.846: its
radial rows run 32.77, 28.49, 23.66 down to 1.01 twenty-four rows out, so that percentile
describes the wall band. **The per-block rows do not rescue it** — each of the four blocks spans
the wall to the far field, so every block's own p95 has the same defect the whole mesh's does.
Measured after the split: band 2304 quads at median 5.184 / p95 28.508 / max 32.768, bulk 2304 at
1.693 / 1.878 / 1.882.
- **A CELL IS IN THE BAND WHILE ITS EXTENT ACROSS A DECLARED WALL SIDE IS SHORTER THAN ITS EXTENT
  ALONG IT**, walking outward from that side and stopping at the first cell where it is not, **per
  station along the side**. No radius, no layer count, no multiple of the first-cell height —
  nothing that would make the figures a knob. It reads `quadExtents` (`include/CellShape.hpp`) and
  NOT `cellShapeRatio`, whose ratio is orientation-free on purpose and cannot say which direction
  is the short one.
- **THE INDEXING CHOOSES THE DIRECTION; THE CELL'S OWN TWO EXTENTS DECIDE THE STOP.** #144's
  criterion 1 asks for a set "identified from the structured grid's own indexing, not from a
  geometric distance guess", and the honest reading of what shipped is the sentence above rather
  than the criterion's: `mbSideWalk` and `wallSpecs` say WHICH index runs across the wall and where
  to start, and a per-cell comparison of two lengths says where to stop. It is not a distance test
  and picks no cut-off, so the criterion's actual prohibition holds — but "from the indexing" alone
  would be wider than the code, and the Spec review said so.
- **"WALL-ADJACENT" IS NOT THE RULE, and the ticket's own two criteria could not both hold.** #144
  asked for the wall-ADJACENT cells AND for a bulk p95 below 3. Measured: a band of one row is 2.1%
  of the O-grid and leaves the bulk p95 at **20.05**, still a wall figure, so that split would have
  changed nothing about the number it exists to fix; it takes 15 of the 48 rows to get under 3. The
  user chose the clustered band with that measurement in hand. Injection V of
  `tests/test_multiblock_shape_surface.py` is the one-row variant, kept as the measurement.
- **A UNIFORM GRID CLUSTERS NOTHING, and a bare `across < along` did not say so.** The shipped
  square is 400 geometrically identical 0.05-by-0.05 cells and it banded **72** of them: two
  midlines of a square come out of a `hypot` a last bit apart and the sign of that bit is noise. The
  comparison carries a **1e-12 relative tie rule** — a floating-point EQUALITY tolerance, never a
  cut-off: it empties the square's and the cavity's bands and moves no other shipped case by a cell.
  The C++ gate's fixture for it has to be that 0.05 grid; on INTEGER coordinates the midlines come
  out exactly equal and the injection is inert.
- **A BLOCK WITH NO DECLARED WALL SIDE IS ALL BULK, by construction** — it has no side to walk
  from. **TWO SIDES OF ONE BLOCK MAY BOTH BE WALLS** (the O-grid's body arc and its far-field arc
  are), so the mask is a UNION and a cell reached from either is banded once; that is what keeps
  `structuredShape.cells == structuredLayerShape.cells + structuredBulkShape.cells` true.
- **`MB_EDGE_WALL` IS "A BOUNDARY EDGE", NOT "A NO-SLIP WALL", so the band's name over-claims by
  exactly that much.** The O-grid's far-field arcs are `kind: "wall"` and ARE walked; here they band
  nothing, because the outermost radial interval is longer than the arc it spans (≈1.2 against
  0.654). A topology that clustered against its far field would put those cells in
  "wall-clustered quads" — correct under the rule, surprising under the word. Named by the Spec
  review; not fixed, because the alternative is reading a BC out of the sidecar to decide a shape
  figure's set, which is the coupling #128 spent the batch avoiding.
- **ONE NAMING SHAPE FOR BOTH GENERATION PATHS: `<metric>_layer_*` and `<metric>_bulk_*`.** This
  path ships `quad_midline_ratio_layer_cells|median|p95|max` and `_bulk_*`, and `quality.layer` /
  `quality.bulk` in the sidecar; the hybrid path shipped `tri_edge_ratio_layer_*` first (#143) and
  this is where the two were made to match. **The BANNER label is this path's own word** — `wall
  band` — which is the half of the shape the two deliberately do not share. **EVERY TOKEN AND
  SIDECAR KEY THAT EXISTED BEFORE #144 KEEPS ITS SPELLING AND ITS MEANING**, and still describes the
  WHOLE mesh.
- **BOTH HALVES ARE INDEPENDENT OF `MB_SPLIT_QUADS`**, for the reason `structuredShape` is: they
  are measured on the structured quads. **NO THRESHOLD, NO COLOUR, NO GRADE on either new set.**
- **AN EMPTY BAND IS `not measured` WITH THREE NEGATIVE FIGURES**, and here that is ORDINARY: the
  shipped square and cavity have no band at all. The parenthetical NAMES NO CAUSE, the rule the
  headline row has carried since #130.
- **`MeshQuality::split` BEING FALSE NOW HAS NO PRODUCER.** Both paths split, so the writer's other
  branch in `include/Provenance.hpp` is reachable only by a path nobody has written. The flag is
  KEPT — deleting it makes the next path write two objects full of negatives, the state #143 argued
  against — and `tests/test_hybrid_shape_surface.py` check 16, which used to be that state's
  witness, now asserts the cross-path naming shape instead.
- Gated by `tests/cpp/test_mb_quality.cpp` checks 10 and 10b-10g (the walk, on hand-built meshes)
  and `tests/test_multiblock_shape_surface.py` checks 14-18, whose **18 carries the ticket's one
  numeric bar** — the bulk p95 below 3 while the whole-mesh p95 is above 20, two-sided so a band
  that swallowed the mesh cannot pass it — and whose `BAND_PINS` pins each case's two COUNTS, a
  pin added because injection M2 moved the H-grid's and the C-grid's band and reddened nothing.
  Why: `docs/design_notes/mesher.md`, "THE WALL BAND: what the O-grid's p95 was describing".
- Gated by `tests/cpp/test_mb_quality.cpp` (21 groups, 105 checks),
  `tests/test_multiblock_quality_surface.py` and `tests/test_multiblock_shape_surface.py` (the
  shape figures on ALL FIVE shipped multi-block cases, pinned, through the real binary — 18
  properties and thirteen hand injections, both enumerated in its own docstring; the assertion
  count is deliberately NOT restated here, being a live figure about another file that no
  `--sync` derivation keeps true). **The C++ gate's
  injections are HAND runs, dated in that test's own docstring** — a C++ test cannot mutate the
  implementation it linked against, and that distinction must not be blurred. Permanent instead are two **negative
  controls** computing an injection's own premise (check 6 the bow-tie's +0.5 area, check 2 its
  ~17x stretch). One injection, `I`, is recorded as **INERT** and kept: the rule it attacks is
  guarded one level down, in the pure gate.

## Named blind spots

The two that came with the sections above, kept as one list per rule file
(`docs/agents/rule-file-style.md` rule 5). The rest of this path's are in
`.claude/rules/mesher-multiblock.md`'s own list, including one that reaches this file's
subject from the other side: `golden_mesh.py` does not compare the VTK cell field.

- **Non-orthogonality says nothing about the shape of the SPLIT TRIANGLES** — it is measured on the
  structured grid cells only.
- **Nothing runs the solver or the grid converter on the folded mesh** (`MbQuality`'s sharpest).
