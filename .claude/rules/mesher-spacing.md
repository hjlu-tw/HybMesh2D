---
paths:
  - tools/PreProcessor/include/Spacing.hpp
  - src/MultiBlock.cpp
  - include/Config.hpp
  - tests/cpp/test_multiblock.cpp
---

# Mesher rules — WHERE AN EDGE's NODES GO ALONG IT (the spacing laws)

Loaded on demand when the spacing header, the one place that chooses between its laws, the
key the wall height comes from or the C++ gate is read. **The SEVENTEENTH rule file, and the
EIGHTH taken because another was FULL** (`mesher-multiblock.md` left #176 with 521 characters
of slack and #177's rules did not fit) — but unlike the seven before it, it is ALSO the first
whose globs reach `tools/`, which CLOSES a blind spot `.claude/rules/mesher-multiblock.md`
had named and could not fix:

> **NO RULE FILE'S GLOBS REACH `tools/`**, so the O-grid rule's own spacing law —
> `tools/PreProcessor/include/Spacing.hpp`, named in that rule — is unreachable from the
> tripwire table: a session that opens it is handed no rules at all.

A session that opens that header is handed THIS file now. The other three globs are not
spacing modules and carry these rules from outside them: `src/MultiBlock.cpp`, whose
`spacingAlong` is the ONE place the laws are chosen between and whose warning is what says a
request was not honoured; `include/Config.hpp`, where `BL_INITIAL_THICKNESS` and
`BL_GROWTH_RATE` live; and `tests/cpp/test_multiblock.cpp`, the gate. All three are
`mesher-multiblock.md`'s as well, so a session editing the dispatch loads BOTH — the intended
overlap (#85's, #89's and #153's precedent), this file answering "where do an edge's nodes go
along it" and that one "what does this document declare, and how is the block filled".
Rules only: the rationale — the measurements, the dated injections and the named blind
spots — is `docs/design_notes/mesher.md`, the SAME note the other three mesher rule files
point at. Read that note before overruling a rule here, and when a rule changes update BOTH.

**THE LAWS ARE SHARED WITH THE PREPROCESSOR CLI AND ARE NOT THIS PATH's PROPERTY.**
`Spacing.hpp` is on `surface_resampler`'s include path and on `hybmesh_pure`'s, the latter
**PRIVATE** so a test linking the pure layer does not inherit it. So a change here can move a
resampled geometry as well as a block fill, and the golden set covers both.

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
- **Refused BY NAME, never half-honoured**: a wall spacing on `uniform`/`geometric`; a raw
  `delta` beside a spacing; a non-positive height; an unknown `wall_ends`; a `growth` on a
  non-geometric edge; a wall end with no height anywhere, naming `BL_INITIAL_THICKNESS`. A request
  the edge could not honour (coarser than its count allows) is a WARNING measured on the produced
  nodes, not re-derived from the law — and **in ARC LENGTH, never the chord**: a bound edge follows
  a polyline, so a first interval spanning several facets has a shorter chord, and comparing that
  fired the warning on a law that had honoured the request exactly, blaming the node count for the
  geometry's own faceting. Gated with a negative control by `test_multiblock.cpp` 36.
  **TWO DIFFERENT HEIGHTS AT THE TWO ENDS LEFT THIS LIST IN #177** and is the rule below.
  **THE TEST THAT MOVED IT IS THE ONE TO APPLY BEFORE ADDING A ROW HERE**: this list means
  the SUBJECT cannot, and that refusal meant only that `Spacing.hpp` had no such solver —
  it said "the tanh law here is symmetric when both ends cluster", which was true of this
  repo's file and of no tanh anywhere else. A primitive three competing tools ship is not a
  property of the subject. Which three, with their own parameter names and where they were
  read: `docs/research/cell-size-range-within-a-block.md` section L3, and
  `docs/design_notes/mesher.md`.

**AN EDGE MAY CLUSTER TO A DIFFERENT HEIGHT AT EACH END, AND IT IS THE SAME FAMILY THE
SYMMETRIC LAW IS A MEMBER OF** (`Spacing::solveTanhTwoSided` / `generateTanhTwoSided`; the
dispatch is `spacingAlong` in `src/MultiBlock.cpp`; #177). **NO NEW KEY** — `ds_start` and
`ds_end` already existed and already parsed; only the refusal between them went.
- **THE STANDARD TWO-SIDED VINOKUR/THOMPSON CONSTRUCTION, NOT NEW MATHEMATICS**: the symmetric
  tanh composed with ONE Mobius map, `s = u / (A + (1 - A) u)`, where `u` carries the fineness
  (`dlt`) and `A` the ASYMMETRY. **At `A == 1` it is `tanhBothPos` BIT FOR BIT** — `A + (1 - A)u`
  is exactly 1.0 and halving is exact — so the one-parameter law is a MEMBER of this one and not
  a neighbour of it.
- **ONE BISECTION, NOT A TWO-DIMENSIONAL ROOT FIND.** Pinning the leading interval is one
  LINEAR equation in `A` once `dlt` is fixed, so `tanhTwoSidedA` inverts it in closed form and
  what is left is one bisection over one monotone function — the shape `solveClusterDelta`
  already has, and for its reason. `tanhTwoSidedTrail` is monotone DECREASING in `dlt`, measured
  over 101 samples from 0 to 64 on six configurations.
- **THE ONE-PARAMETER SOLVERS STAY, AND THE DISPATCH IS WHAT KEEPS THEM REACHED.** An EQUAL
  pair still goes to `solveTanhDelta` and a SINGLE clustered end still goes to
  `solveTanhStartDelta`, bit for bit, so no shipped document's nodes move — measured, 22/22
  golden cases SAME at 0.000e+00 across two builds.
- **THE REDUCTION IS GATED TWICE, BECAUSE THE DISPATCH PUTS IT OUT OF ONE GATE's REACH.**
  Through `buildMultiBlock` the two-sided law is never exercised AT an equal pair, so an
  equality asserted there would be asserted of nothing: `test_multiblock.cpp` 60(b) declares
  `0.01` against `0.01 * (1 + 1e-12)`, which routes through the NEW law, and holds its nodes
  to the symmetric law's. That is the shipped BEHAVIOUR's gate. The DECISION #177 states — "a
  two-parameter solver asked for a symmetric pair must reproduce it, and that equality is the
  gate rather than a claim" — needs the solver called directly, which no test linking
  `hybmesh_pure` can do, so `tests/cpp/test_spacing_two_sided.cpp` links NOTHING and is handed
  the header by name. Both are wanted; a review axis found the second missing.
- **AND THE ONE-SIDED LAW IS A MEMBER OF THIS FAMILY TOO, SO THE DISPATCH IS ABOUT
  DETERMINACY AND NOT CAPABILITY.** Handed the one-sided law's own two end intervals, the
  two-sided solver reproduces its WHOLE distribution — worst 7.7e-13 of the edge over 64
  combinations of length, count and cell size. This file said the opposite until the gate that
  was written to confirm it went red: "a single clustered end is not expressible here" came
  from Pointwise falling back to "a *different*, one-sided function ... if the spacing is
  unconstrained at only one end", which is an API fact about an UNDECLARED end, read as a
  mathematical one. **The same mistake as the refusal this ticket removed, made twice in one
  ticket.** What is true: one declared height is ONE equation and this family has TWO
  parameters, so with the far end undeclared there is nothing to solve `A` from, and
  `solveTanhStartDelta` is the rule that picks a member. The dispatch stays for that and for
  bit-for-bit compatibility.
- **THE FINER END LEADS, AND THE RESULT IS MIRRORED** when the document declared it trailing —
  the same reflection the one-sided branch uses, and for the same reason. Two things follow and
  both are rules. The solve PINS its leading height when the pair cannot be had, so **what
  survives a request the count cannot carry is the end a WALL would be at**, not whichever end
  the document named first. And the law COMMUTES with reversing the declaration, to one
  rounding of that reflection (1.0e-16 on a length-1 edge) — **not bit for bit, and the first
  draft of that check asserted 0 and went red**.
- **A PAIR THE COUNT CANNOT CARRY IS A WARNING, NEVER A REFUSAL, AND THE BOUND IS DERIVED:**
  `(L/ds_start - 1) * (L/ds_end - 1) >= (count - 2)^2`, symmetric in the two heights,
  `count - 1` being the interval count and the bound `(intervals - 1)^2`. **It is NOT branched
  on in the solver** — `dlt = 0` is the family's coarsest trailing interval, so past the bound
  the bisection simply stops there; an early return testing it was written and DELETED when its
  injection came back inert. What the bound IS used for is the MESSAGE, which states it with
  the arithmetic done, because each end alone may be perfectly reachable while the two together
  are not, and a reader told only "ask for a finer height" would refine an end that is already
  as fine as it asked to be. **The exponent was `(count - 1)^2` in this ticket's own first
  derivation**, and the gate reads the two printed figures back out rather than matching the
  words.
- **NEITHER END FINER THAN UNIFORM IS NOT A CLUSTERING REQUEST**, and the answer is the one
  `solveClusterDelta` gives the one-parameter laws: UNIFORM, bit for bit, reached by the same
  test rather than by a second rule. The degenerate end of that region — a declared height
  longer than the WHOLE EDGE — is the one place `A <= 0` is reachable, and `tanhTwoSidedPos`
  divides by it: the difference between that row and a NaN mesh is one guard.
- **ACCEPTANCE ITEM 6 IS NOT MET AND THE RULE IS NOT TO ARGUE IT AWAY.** #177 asks for the
  `turek` channel band as the first real use; that case is scratch and is NOT IN THIS TREE, so
  nothing here can falsify a claim about it either way. A first attempt measured its `h0_*`
  edges and concluded the ticket does not fix it — right arithmetic, wrong edges: those run
  streamwise while the issue's band is wall-normal, and they were picked because they were the
  ones WARNING. What is measured instead is user story 2 on the SHIPPED two-ring O-grid.
- Gated by `tests/cpp/test_multiblock.cpp` 60 (13 hand injections, dated in that file, 10
  biting and the 3 inert ones named with their reasons) and
  `tools/PreProcessor/tests/test_multiblock_two_sided_surface.py`, which drives the SHIPPED
  two-ring O-grid through the real binary and measures four declared heights on one radial
  line in the exported `.vtk`.
  Why: `docs/design_notes/mesher.md`, "A DIFFERENT HEIGHT AT EACH END".

## Named blind spots

Consolidated here rather than trailing each rule, so a coverage claim can be checked against
one list — the habit `.claude/rules/mesher-multiblock.md` set and this file carries across
with the rules.

- **THE LAWS' OTHER CONSUMER IS NOT GATED FROM HERE.** `surface_resampler` includes the same
  header, and nothing in either gate named above runs it: a change to `generateGeometric` or
  `generateTanh` that moved a RESAMPLED geometry would be caught by the golden set's hybrid
  cases and by nothing that knows it is about spacing. The two-sided law has no resampler
  caller today, so this is a hole the NEXT change here falls into rather than this one.
- **NOTHING MEASURES A TWO-ENDED EDGE WHOSE TWO BLOCKS DISAGREE ABOUT ITS DIRECTION.** A shared
  edge has ONE direction and two frames that need not agree, so `ds_start` is the START of the
  EDGE and not of either block. Every fixture and every shipped document declares its two-ended
  edges on one block's natural sense; the reversal rule above is measured on two separate
  documents rather than on one edge read from two sides.
- **THE SURFACE GATE MEASURES ONE RAY.** Every figure in
  `test_multiblock_two_sided_surface.py` is on the +x radial of the two-ring O-grid, the other
  three being its images under that topology's own symmetry; that file's own blind-spot list
  carries the rest, including that it runs no solver and reads the law at zero sweeps.
- **THE ACCURACY BOUND IS DERIVED, SO IT DEGRADES WITH THE CELL's RELATIVE SIZE AND NOTHING
  WARNS.** `eps * L / ds` passes 1e-9 — the bar the achieved-versus-requested warning uses — at
  about a first cell of 2e-7 of the edge. Past that a correct law reports itself as having
  missed. That is true of the one-parameter solvers since #55 and is not new here; no shipped
  case is within four orders of it.
