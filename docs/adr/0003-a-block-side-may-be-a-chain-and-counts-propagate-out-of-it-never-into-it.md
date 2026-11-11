# A block side may be a CHAIN of edges, and counts propagate OUT of a chain, never INTO it

In a `MESH_MODE 1` topology a **count** is a seed, not a requirement: opposite sides of a block
hold the same number of nodes, a shared edge is one edge two blocks name, and that single
relation partitions every edge into equivalence classes. The operator seeds a few and the mesher
resolves the rest. That is what makes the model coherent — and it means **there is no way to say
"more nodes here"**. Measured on the shipped C-grid: doubling the aerofoil's count (49 → 97) and
changing nothing else adds 3840 cells, of which 63.1% land within one chord of the body, 23.8%
one to five chords out and **13.2% beyond five chords**, where nobody asked for anything.

The model could not express the fix either. A line between two blocks cannot TERMINATE, because
a block has four sides and each was exactly one edge: the block above a termination can name one
half of the line below or the other and never both, and the half it does not name is then a side
of one block, which the arity rule refuses by name. `docs/research/gridpro-blocking-method/`
`make_merge_refusal.py` writes that minimal document and the mesher answers
`HYBMESH_ERROR 8 TOPOLOGY`.

**A side may now be a chain: one edge, as before, or an ordered list of edges joined end to end.
A chain's members are resolved by the ordinary class relation, and their SUM then decides the
opposite side of the block carrying the chain. Propagation runs members → total → opposite side
and NEVER the reverse.** A seeded opposite side that contradicts the sum is refused, not
back-propagated.

That asymmetry is the decision, and it is what the title carries, because it is the thing a
future reader is most likely to mistake for a bug. A symmetric relation is what the mesher had;
it is coherent, and it is exactly why a coarse far field drags a fine feature coarse. Making the
new relation symmetric again would restore the problem while leaving the syntax in place.

## Consequences

- **A document that names one edge per side is unchanged, bit for bit.** A list of ONE is
  refused, so the bare edge id stays the only spelling of an ordinary side and the two cannot
  drift apart. Measured: 22/22 golden cases SAME at exactly 0.000e+00, captured from a
  separately built binary.
- **The arity rule is untouched, and a chain member satisfies it.** A member is a side of the
  block carrying the chain AND of the block beneath it — two blocks, like any other interior
  line. Do not "fix" the arity rule for chains: it is what makes welding **allocation** rather
  than comparison, which is the property that lets a 1e-7 wall spacing and a 1e-1 far-field one
  share one mesh with no tolerance anywhere.
- **The fill needs no change.** Each side already reached the transfinite fill as a list of node
  positions, and a chain concatenates into exactly that. The junction between two members is ONE
  declared corner allocated once, so the concatenation drops a repeated id rather than
  reconciling two positions — no hanging node, and no tolerance introduced.
- **Chains are interior only.** Every member must be an `interface` or a `cut`. That leaves the
  wall spacing publication, its readers, the wall-band walk and the spacing laws untouched, and
  the canonical use needs nothing more: in a termination the chain is the upper block's side
  while the wall below is two separate blocks' sides, each one edge. Strict now is relaxable
  later; the reverse is a breaking change.
- **Four sides still close a ring**, with a chain's two ends taking the place of its single
  edge's — generalised, not removed. The self-weld refusal and "a kind is declared and never
  inferred from a binding" survive verbatim.
- **Four refusals are added, each naming what it saw**: members that do not join end to end
  (two shapes — the first two sharing no corner, and a break mid-chain naming the corner the
  chain had reached); a seeded opposite side contradicting the sum, naming both numbers and both
  edges; a chain of length one; and a chain with a wall member.
- **A chain-bearing side is FROZEN by the elliptic smoother, and that falls out rather than being
  decided.** `mbSmoothPlan` builds a ghost layer only where two welded sides match station for
  station; a chain side and the shorter side beneath it do not, so no ghost layer is built and
  every node on that line keeps its position. It is the honest answer for this release — the
  smoother has no frame in which to move a node whose two blocks disagree about how many
  stations the line has — and it is recorded as a named blind spot rather than as a property.

## Rejected alternatives

- **A T-junction corner.** Let a corner lie mid-edge and have the mesher split that edge. It is
  the same topology in a friendlier spelling, and it requires deciding "this point lies on that
  line" — which needs a **tolerance**. This path has none anywhere, deliberately, because
  welding is allocation; one tolerance here would be the first, between a 1e-7 wall spacing and
  a 1e-1 far-field one, where no single value exists.
- **An n-sided block.** The transfinite fill is a map over FOUR logical sides. An n-sided block
  is a different fill, a different quality instrument and a different split rule, for a
  capability a chain already gives.
- **A count override that simply breaks the class.** Letting one edge declare a count that does
  not propagate produces a NON-CONFORMAL mesh — two blocks with different node counts along one
  shared line, i.e. hanging nodes the solver, the grid converter and the `.cel` writer are none
  of them built for.
- **A general linear system over the counts** was also considered and rejected: it is more than
  the capability needs, and it makes the under- and over-determined cases — which the mesher
  must refuse WELL — much harder to state. The one-way sum pass iterates to a fixed point
  instead, and an unresolved class is already a refusal with an actionable message.

## Where the rest lives

Rules: `.claude/rules/mesher-block-side.md`. Rationale, measurements and the hand injections:
`docs/design_notes/mesher.md`, "A BLOCK SIDE MAY BE A CHAIN". Vocabulary: `CONTEXT.md`
(**Side**, **Chain**). Gate: `tests/cpp/test_multiblock.cpp` checks 61-65.
