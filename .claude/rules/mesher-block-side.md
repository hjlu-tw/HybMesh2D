---
paths:
  - include/MultiBlock.hpp
  - src/MultiBlock.cpp
  - tests/cpp/test_multiblock.cpp
  - examples/topology/*.json
---

# Mesher rules — WHAT A BLOCK SIDE IS (the ring, the frame, the four shared corner NODES)

Loaded on demand when the multi-block header, the one module that validates and fills a block,
the C++ gate, or **a topology document itself** is read. **The EIGHTEENTH rule file, and the
NINTH taken because another was FULL** — `.claude/rules/mesher-multiblock.md` left #188 with
883 characters of slack against a feature whose whole subject is the thing these rules define,
and `docs/agents/rule-file-style.md` answers a full rule file with a SPLIT rather than a harder
compression. Its last glob also reaches a tree no rule file had covered, which is #177's shape
with one difference: that hole was NAMED in a blind-spot list and this one was not — it was
measured while taking the split. (#177's own "FIRST rule file whose globs reach `tools/`" is
FALSE, measured at #189: `gui-canvas-edit.md` globbed `tools/PreProcessor/include/NacaAirfoil*`
at #147 and `gui-lifecycle.md` globbed `tools/scripts/gmsh_*` at #77. The claim below rests on
its own measurement and not on that one.)

> **NO RULE FILE'S GLOBS REACH `examples/`.** The shipped topology documents under
> `examples/topology/` are the place where a block's four sides are actually WRITTEN, and seven
> of the nine are named in `.claude/rules/mesher-multiblock.md` (`hgrid_blocks`,
> `ogrid_circle`, `cgrid_naca0012`, `tworing_ogrid`, `tworing_offset`, `tworing_curve`,
> `curved_seam_blocks`), and a session opening one of them to add a block is handed no rules
> at all.

A session that opens one of those nine is handed THIS file now. The other three globs are
`mesher-multiblock.md`'s as well, so a session editing `src/MultiBlock.cpp` or
`tests/cpp/test_multiblock.cpp` loads BOTH — the intended overlap (#85's, #89's, #153's and
#177's precedent). The seam between them is a question, not a package: **this file answers
"what IS one of a block's four sides, and what makes four of them a block"**, that one answers
"what does the document declare, and how is the block filled". So the edge KIND, the arity rule
(`wall` 1, `interface`/`cut` 2), count propagation, the split rules, the BC binding and the
self-weld refusal all stay there; what is here is the four-sides-close-a-ring refusal, the frame
the south edge fixes, and the four shared corner nodes.
Rules only: the rationale — the measurements, the dated acceptance runs, the injections, the
reversals and the named blind spots — is `docs/design_notes/mesher.md`, the SAME note the other
five mesher rule files point at. Read that note before overruling a rule here, and when a rule
changes update BOTH.

**A SIDE IS ONE EDGE OR A CHAIN OF THEM, and these rules say so from four directions.** The ring
refusal says four sides must close; the frame rule says which one of the four fixes the
block's i/j; the corner-node check says the four shared endpoints are shared NODES and not four
coordinates that agree; and the chain rule says what a side may be made of. None of them is a
statement about how many nodes an EDGE carries, which is `.claude/rules/mesher-spacing.md`'s
question — but the chain's SUM rule below is a statement about how many a SIDE carries, which
is this file's.

- **A block's orientation is the corner order of its own four edges**, `[south, east, north, west]`,
  south/north running i-min→i-max and west/east j-min→j-max. A **clockwise** corner ring is refused
  under the TOPOLOGY code, never silently re-wound. SUPERSEDED IN PART by #53: a DIRECTION
  deviation is no longer refused, only a set of four edges that does not CLOSE a ring.
  Why: `docs/design_notes/mesher.md`, "A block's orientation is the corner order".
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
- **A SIDE MAY BE A CHAIN OF EDGES JOINED END TO END, AND COUNTS PROPAGATE OUT OF ONE AND NEVER
  INTO IT** (`SideSpec` + `resolveSide` + `resolveEdgeCounts`'s second pass, `src/MultiBlock.cpp`;
  #190). A block's `edges` array still has exactly four entries; an entry is an edge id as before,
  or an ORDERED LIST of ids. The one-way rule is the feature, not a limitation of it — a symmetric
  relation is what the mesher already had, and it is why refining a feature refines the far field
  (measured on the shipped C-grid: of the 3840 cells a 49 -> 97 aerofoil count adds, 13.2% land
  beyond five chords). **Do not "fix" it into a symmetric relation.**
  Why: `docs/design_notes/mesher.md`, "A BLOCK SIDE MAY BE A CHAIN"; the decision and the three
  rejected alternatives are `docs/adr/0003-a-block-side-may-be-a-chain-and-counts-propagate-out-of-it-never-into-it.md`.
  - **A LIST OF ONE IS REFUSED**, so the bare edge id is the ONLY spelling of an ordinary side and
    the two cannot drift apart. A document that names one edge per side is unchanged BIT FOR BIT —
    22/22 golden SAME at exactly 0.000e+00, captured from a separately built binary.
  - **THE MEMBERS ARE RESOLVED BY THE ORDINARY CLASS RELATION and their SUM decides the opposite
    side.** A chain of M members carries `sum(n_m - 1) + 1` nodes, the M-1 junctions being ONE
    declared corner each. The pass is a FIXED-POINT iteration, not a sort: a chain's members must
    be resolved before its total exists, and one chain's total can resolve another's member. A
    cycle simply leaves its classes unresolved, which is already a refusal with an actionable
    message. **A seeded opposite side that CONTRADICTS the sum is refused, naming both numbers and
    both edges** — never back-propagated, and never "whichever side was seeded wins".
  - **TWO CHAINS FACING EACH OTHER PROPAGATE NEITHER WAY**: each is decided by its own members, so
    all that is left is a CHECK that the two totals agree. Without it the user is handed the
    internal "opposite sides came out with different node counts" message, which names no fix.
  - **CHAINS ARE INTERIOR ONLY — every member must be an `interface` or a `cut`.** A wall side is
    exactly one edge, which leaves the wall spacing publication, its readers, the wall-band walk
    and the spacing laws untouched. The canonical use needs nothing more: in a termination the
    chain is the upper block's side while the wall below is two separate blocks' sides. Strict now
    is relaxable later.
  - **THE ARITY RULE SURVIVES VERBATIM AND A CHAIN MEMBER SATISFIES IT** — a side of the carrying
    block AND of the block beneath, so two blocks, like any other interior line. **Do not widen it
    for chains**: it is what makes welding ALLOCATION rather than comparison, the property that
    lets a 1e-7 wall spacing and a 1e-1 far-field one share one mesh with no tolerance anywhere.
    The self-weld refusal and "a kind is DECLARED, never inferred from a binding" are untouched;
    the ring refusal GENERALISES, a chain's two ends taking the place of its single edge's.
  - **THE FILL NEEDS NO CHANGE AND NO TOLERANCE IS INTRODUCED.** A side already reached the
    transfinite fill as a list of node positions and a chain CONCATENATES into exactly that; the
    junction node is dropped from the second member because it is the SAME allocated id, not
    because two positions were found to agree. **TWO reversals compose and each has ONE home** —
    `SideSpec::rev` (a member against its own declared direction, so the joins meet) and
    `Frame::rev` (the whole side against the ring). Nothing reads a position.
  - **SEVEN NEW REFUSAL BRANCHES, each naming what it saw, and the count is ENUMERATED here
    because a review found three documents saying "four" and meaning different fours**: (1) a
    chain of one member, or none; (2) a member declared `wall`; (3) the first two members sharing
    NO corner, where no direction is known yet; (4) a member mid-chain that does not start where
    the chain had REACHED, which can name that corner; (5) the first two members spanning ONE
    corner pair — a loop, not a line, and the branch that shipped UNGATED until #190's review;
    (6) a seeded opposite side contradicting the chain's total; (7) two facing chains whose
    totals differ. #190 names four of the seven; the other three are shapes the implementation
    needed.
  - **ONE SHIPPED CASE CARRIES A CHAIN, AND IT IS THE ONLY ONE** (#191):
    `config/multiblock_cgrid_chain.dat` + `examples/topology/cgrid_chain_naca0012.json`, a
    TEN-block C-grid beside the four-block one, whose aerofoil carries 97 nodes per surface
    against that case's 49 while every far-field edge still declares a number that case
    declares. It is a SECOND case, never a replacement — the comparison needs both sides.
    `i_upper`'s east is `["m1", "m2"]` and `i_lower`'s is `["m3", "m4"]`; `r_mid_up` and
    `r_mid_lo` are the block boundaries that TERMINATE at the junctions.
    - **WHAT A CHAIN DOES NOT BUY, and the gate states it as a number beside what it does.**
      The far field over each nose carries 97 NODES, not 49: opposite sides hold the same
      number, a chain's side holds its members' sum, and no interior node in this model has a
      valence other than four — so the body's node count and the far field's are EQUAL at
      every radius, in a chain-bearing document exactly as in any other. A chain moves which
      EDGES carry the total and where the boundaries between them may stop. **Do not write
      "refine the body and the far field keeps its mesh" anywhere**; #188's user story 14 and
      #191's criterion 2 read that way and the measurement does not support it.
    - **WHAT PUT THE ADDED CELLS NEAR THE BODY IS THE SECOND RADIAL CLASS, NOT THE CHAIN.**
      Both this case and the control — the four-block document with its two aerofoil counts
      raised to 97 and nothing else touched — add the SAME 3840 quads. 79.2% of this case's
      land within one chord against the control's 64.6%, and 0.7% beyond five chords against
      12.5%, because 29 + 13 - 1 = 41 spends 28 intervals inside one chord where the single
      class spends 22. The chain is what lets that split be declared with the far-field
      edges unchanged. Gated separately — check 5 the counts, check 9 the distribution, and
      check 11 the A/B that attributes it: the SAME document with its chains collapsed gives
      79.3% / 20.1% / 0.7%, so the chain moves no cell anywhere.
    - Gated by `tests/test_multiblock_cgrid_chain_surface.py` (10 groups), whose docstring
      carries the dated gate-2 run — mesher, `getPGrid`, `unicones`, cfl 0.6, 100
      iterations, no NaN — and its four-block control run the same day at the same operating
      point. `tools/scripts/golden_mesh.py`'s `mb_cgrid_chain` covers the `.vtk` and both
      STAR-CD files; 23/23 SAME at exactly 0.000e+00 against a baseline captured from a
      separately built `c66da1f` binary. The case is also pinned in
      `tests/test_multiblock_shape_surface.py` and driven by
      `tests/test_multiblock_smooth_surface.py` group 13, whose completeness guards are what
      refuse a shipped config with no pin and no gate.
  - **NO TOPOLOGY FAMILY EMITS A CHAIN, and that is a decision rather than a gap.**
    `services/topology_*` can once the schema accepts one, and which family should and with what
    parameter is a separate question that must bring its own evidence (`.claude/rules/gui-topology.md`
    is eight characters from its budget). Until then a chain is reachable only by hand-writing a
    document.
  - **A SIDE READS AS A SIDE IN EVERY REFUSAL**, through `SideSpec::label()` — `edge 'x'` or
    `the chain ['x', 'y']`. A ring failure that named one member would send the reader to the
    wrong declaration.
- **A CORNER SHARED BY THREE BLOCKS IS ACCEPTED, AND IT IS THE ONLY DEVICE IN THIS MODEL THAT
  ENDS A GRID LINE** (#192 step 1). Three quads around one point — a hexagon and its centre,
  each of the three radials a side of exactly two blocks — meshes with zero inverted cells and
  needs NO mesher change: the arity rule is satisfied, each block's four edges close a
  counter-clockwise ring, and the four-corner check passes. The resulting node has **valence 3**
  and sits in three cells, which is what a chain junction is NOT: that one is valence 4, which
  is why a chain moves no cell (`.claude/rules/mesher-block-side.md` above, and #191's own A/B).
  - **N BLOCKS AT A CORNER MAKE N COUNT CLASSES, NOT ONE.** Each block's two i-sides are one
    radial and one wall, so nothing propagates AROUND such a corner: the hexagon needs THREE
    seeds and the four-block square FOUR. A document seeding one of three is refused, naming
    the size of the group with no count. This is the only thing about the arrangement an
    author has to learn, and it is the thing a change to the propagation would break first.
  - **A COUNT REDUCTION COSTS TWICE THE RING'S RADIAL DEPTH PER CORNER BLOCK, NOT ONE LINE PER
    IRREGULAR NODE** (#192 steps 2-4). A CORNER BLOCK has two sides on a ring's inner boundary
    and none on its outer, so both of its radials end at one apex — the three-block corner above
    — and a ring of K of them with `a` radial intervals turns `K(2a + qm)` inner intervals into
    `Kqm` outer ones. Measured at four depths on the smallest such ring: the reduction is `2Ka`
    exactly. So 96 lines is TWO corner blocks at depth 24, not 96 of anything. **K corner blocks
    make K RADIAL classes**, because each links a radial to one of its own inner arcs rather than
    to the other radial; a ring seeded once is refused.
    - **THE SMALLEST REDUCING ANNULUS HAS NO INTERIOR IRREGULAR NODE AT ALL.** Its apex is a
      valence-4 BOUNDARY node and its FOLD — between the corner block's two inner arcs — is a
      valence-**2** one, whose single cell spans the boundary's own 180 degrees. No smoothing and
      no embedding removes that; only NOTCHING the fold inward so the boundary turns does, which
      a ring whose inner boundary is the WALL cannot do.
    - **ONE REDUCING MESH PASSES GATE 2 AND ONE DOES NOT.** The reducing O-grid (shipped circle
      geometries, body 192 intervals, far field 96, 0 inverted) runs the solver at the C-grid's
      operating point with no NaN; the reducing C-grid goes to `Average norm is a nan` — and so
      does its own no-corner-block CONTROL at the same iteration, so that is the construction and
      not the device. On the C-grid the reduction adds 2688 quads where every other way of putting
      97 nodes on that aerofoil adds 3840.
    - **NOTHING IS SHIPPED.** No shipped case carries a corner block, no topology family emits
      one, and the best worst cell measured anywhere is 53.6 degrees off orthogonal against a
      plain O-grid's 2.02. The documents and the generators are
      `docs/research/gridpro-blocking-method/make_reducing_annulus.py`, `make_reducing_cgrid.py`
      and `bin_added_cells.py`; each committed document carries the command that wrote it in its
      own header. **Do not read "the device exists" as "the capability is available."**
    - **SUPERSEDES #192 step 1's cost model**, which this file carried until this rule replaced
      it: a reduction is not one line per irregular node, because the lines a corner block removes
      TURN inside it rather than ending at its nodes.
      Why: `docs/design_notes/mesher.md`, "THE PRICE, MEASURED — #192 steps 2 to 4".
  - **A VALENCE-5 CORNER IS THE SAME DEVICE RUN THE OTHER WAY** and this repo already ships
    one: the C-grid's `te`, where five edges end and four blocks meet. It ADDS a line.
  - Gated by check 66 (with 66b for the seeds and 66c, a four-block corner, as the negative
    control), with its injections dated in that file's docstring. **No shipped case carries a
    three-block corner**, so check 66 is the whole of its coverage.
  Why: `docs/design_notes/mesher.md`, "THE ONLY DEVICE THAT ENDS A GRID LINE".
- Gated by `tests/cpp/test_multiblock.cpp` — check 9 for the accepted against-convention side and
  the refusals, checks 17-23 for the welded pair whose shared edge is one side of each — and by
  `tests/test_multiblock_weld_surface.py`, which measures CONFORMITY on the exported files. The
  surface gate is what makes "the four sides meet at four shared corner nodes" an observable
  property of a `.vtk` rather than an assertion about a pointer. **Checks 61-65 are the chain's**
  (#190), with ten HAND injections dated in that file: 61 is the red-to-green — the document
  `docs/research/gridpro-blocking-method/make_merge_refusal.py` writes, refused as one edge and
  meshed as a chain with ZERO inverted cells, welded by NODE IDENTITY rather than by position;
  62 the sum and the one-way direction; 63 the four new refusals; 64 the old refusals still
  firing with a chain in the document; 65 two facing chains.

## Named blind spots

- **NOTHING GATES THE COUNT-REDUCTION RULES ABOVE.** Every figure in them — `2Ka`, the valences,
  the gate-2 verdicts, the 2688 quads — is measured in research documents under `docs/research/`
  that no C++ check and no surface gate reads, so they decay exactly as §11 of the nesting note's
  two figures did. The three-block corner ITSELF is gated (check 66); what a ring of them COSTS
  is not. #192's step 4 is why: it decided no reduction leaves `docs/research/`, so there is no
  shipped case for a gate to pin.

- **The `examples/topology/*.json` glob is the first of its kind and is UNMEASURED on this
  build.** #61 measured that a rule file arrives on a `Read` of a matching file, but no glob
  anywhere in `.claude/rules/` had ever pointed at a `.json` document before this one.
  Nothing here establishes that the loader treats one differently, and nothing establishes
  that it does not; the blind spot the budget gate already carries — that it can prove a rule file is
  reachable IN THE TABLE and not that a session ever received it — covers this one too, and the
  tripwire row is what reaches a reader either way.
- **The three rules here were moved for a BUDGET and the seam was chosen afterwards.** That is
  #177's order exactly and it is recorded rather than smoothed over: a reader looking for "what
  happens to a block" will find most of it next door, and the overlap is the mitigation. If the
  question ever stops being load bearing, the right move is back into `mesher-multiblock.md`,
  not a third file.
- ~~**Nothing here rules on a side that is a CHAIN of edges.**~~ **CLOSED by #190**, and kept as a
  specimen: the rule above is what landed, and the prediction that it would be the thing to add
  was #188's rather than this file's.
- **A CHAIN-BEARING SIDE IS FROZEN BY THE SMOOTHER, and that FALLS OUT rather than being
  decided.** `mbSmoothPlan` (`src/MbShared.cpp`) builds a ghost layer only where two welded sides
  match station for station; a chain side and the shorter side beneath it do not, so `addGhosts`
  returns false and every node on that line keeps its position at any `MB_SMOOTH_ITERS`. It is
  the honest answer for this release — the solve has no frame in which to move a node whose two
  blocks disagree about how many stations the line has — but it is a CONSEQUENCE nothing asserts,
  and a future change to `addGhosts` could free those nodes without any gate noticing. The rules
  for what moves are `.claude/rules/mesher-smoothing.md`'s and this is not written there, because
  nothing there was changed.
- ~~**NO SHIPPED CASE AND NO GOLDEN CASE CARRIES A CHAIN.**~~ **CLOSED by #191**, which shipped
  the case named in the rules above and put it through the quality instrument, the `.cel`
  writer, `golden_mesh.py` and the solver. Kept as a specimen for what the closing MEASURED:
  the demonstrator's own gate found that `#188`'s framing of the win — refine the body and the
  far field keeps its counts — is unachievable in this model, and that the cell locality it
  asks for comes from a second radial class rather than from the chain. **A capability's
  demonstrator is where its claim gets tested, and this one failed half of it.**
- ~~**THE CHAIN'S OWN CONTRIBUTION TO THE CELL DISTRIBUTION IS ZERO, AND NOTHING MEASURES THAT
  DIRECTLY** ... because that document cannot be written.~~ **FALSE, and corrected by #191's own
  review before the ticket closed.** The chain-free document IS writable — it is the shipped one
  with its two chains collapsed, which merely fails criterion 2 — and check 11 now runs it: 79.3%
  of its added cells inside one chord against the shipped case's 79.2%, every bin within two cells.
  So the attribution is a MEASUREMENT. Kept as a specimen because the sentence had the shape of a
  proof and was an assumption: **an impossibility argued from the model is a hypothesis until
  something tries to write the thing.**
- **THE LOOP BRANCH SHIPPED UNGATED, AND WHAT FOUND IT WAS A REVIEW READING THE SPEC'S OWN LIST.**
  Refusal (5) above — two members over one corner pair — was in the code, reachable through the
  real binary, named in no document and exercised by no check, because #190's spec enumerates four
  refusals and the implementation needed seven. Check 63 holds it now and injection CK is dated
  with the rest. The general shape is the hole: a branch an implementation adds beyond the
  ticket's list is one nothing counts.
