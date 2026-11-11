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

**A SIDE IS ONE EDGE, and three of these rules say so from a different direction.** The ring
refusal says four of them must close; the frame rule says which one of the four fixes the
block's i/j; the corner-node check says the four shared endpoints are shared NODES and not four
coordinates that agree. None of them is a statement about how many nodes an edge carries, which
is `.claude/rules/mesher-spacing.md`'s question.

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
- Gated by `tests/cpp/test_multiblock.cpp` — check 9 for the accepted against-convention side and
  the refusals, checks 17-23 for the welded pair whose shared edge is one side of each — and by
  `tests/test_multiblock_weld_surface.py`, which measures CONFORMITY on the exported files. The
  surface gate is what makes "the four sides meet at four shared corner nodes" an observable
  property of a `.vtk` rather than an assertion about a pointer.

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
- **Nothing here rules on a side that is a CHAIN of edges.** #188 is the ticket that adds one,
  and until it lands a side is exactly one edge everywhere in this repo. A reader who finds a
  chain in a document before then is reading a document this mesher refuses by name.
