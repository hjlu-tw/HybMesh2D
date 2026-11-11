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

> **NO RULE FILE'S GLOBS REACH `examples/`.** The nine shipped topology documents under
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
  - **FOUR NEW REFUSALS, each naming what it saw**: a chain of length one (or none); a chain with a
    wall member; members that do not join end to end, in TWO shapes — the first two sharing no
    corner, and a break mid-chain naming the corner the chain had REACHED; and two facing chains
    whose totals differ.
  - **A SIDE READS AS A SIDE IN EVERY REFUSAL**, through `SideSpec::label()` — `edge 'x'` or
    `the chain ['x', 'y']`. A ring failure that named one member would send the reader to the
    wrong declaration.
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
- **NO SHIPPED CASE AND NO GOLDEN CASE CARRIES A CHAIN.** The capability is gated through the pure
  entry point on documents built in `tests/cpp/test_multiblock.cpp` and nowhere else: nothing
  exports a chain-bearing mesh, hands one to the quality instrument, the `.cel` writer or the
  solver, or runs one through `tools/scripts/golden_mesh.py`. The 22/22 SAME above is evidence
  that the feature is ADDITIVE and says nothing about a chain-bearing mesh being good. A
  demonstrator is #191.
- **NO TOPOLOGY FAMILY EMITS A CHAIN.** `services/topology_*` can once the schema accepts one, and
  which family should and with what parameter is a separate question that must bring its own
  evidence (`.claude/rules/gui-topology.md` is eight characters from its budget). Until then a
  chain is reachable only by hand-writing a document.
