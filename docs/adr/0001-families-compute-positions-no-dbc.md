# Topology positions are computed by family functions, not relaxed onto the geometry

The multi-block path needs a block topology positioned against a CAD geometry, and there
are two established ways to get one. GridPro's is **Dynamic Boundary Conforming**: the
user sketches a coarse wireframe and a variationally-based iterative scheme pulls it onto
the true surface, so that "the topology for a region has to be precise but **does not have
to be positioned precisely**" and "the final grid (solution) is **independent of the initial
grid distribution**" (GridPro GUI Manual Ch. 4; TIL Reference Manual §1.1). Ours is the
opposite: a **family** is a pure function that *computes* exact corner positions from the
geometry, binding by stable segment id and normalised arc length. **We are keeping the
family approach and will not build DBC.**

## Considered Options

**GridPro-style DBC.** Rejected for two reasons, one about users and one about our own code.

*The generality is unspendable here.* DBC buys coverage of arbitrary geometry, but only a
user who can design a topology can redeem it — GridPro says so outright: "GridPro can only
work with your results, **not create those results**", and "**no set of rules can define how
all topologies could be constructed** … using **intuition rather than rules**" (GUI Manual
§4.1). Our operators do not know meshing (see `CONTEXT.md`), so DBC would hand them a
capability they cannot use, while taking away the thing families give them: covered shapes
need *zero* topology skill. GridPro's own answer for zero-skill users is the Xpress Series —
parametrised per-family topologies sold as separate vertical products, i.e. our families.

*Our smoother's measured behaviour contradicts DBC's premise.* DBC's whole claim is that
converging the relaxation yields the answer. This repo's Winslow kernel has a recorded
finding that **converging is worse** — the end of the progress bar is a mesh nobody wants
(see `docs/design_notes/mesher.md` and `.claude/rules/mesher-smoothing.md`). Building DBC
is therefore not a feature on top of the existing smoother; it is replacing the core
solver, which is a research project.

## Consequences

- **Coverage is bounded by the number of families.** A shape outside all of them has no
  structured path. We accept this, and answer it by adding families (a pure function per
  shape class) rather than by building an interactive topology editor.
- **A new shape class costs maintainer Python**, not operator time. That is a real
  bottleneck, but a bounded one. GridPro's own engineers spend 2–45 minutes hand-authoring
  a baseline topology per class; if a family function costs us materially more than a day,
  the family abstraction is wrong and we should stop and look at it, not keep adding.
- **Blind spot, named:** DBC's relaxation glides over messy CAD; exact computation does not.
  A family reads positions straight off the geometry, so geometry noise propagates into
  corner placement *silently*. This repo has already been bitten once by a 3.8e-5
  self-intersecting seam. Families have no mechanism that dilutes this.
- **Every family is new code with new bugs.** GridPro maintains one solver; we will
  maintain N families. This cost compounds, and is the main thing to watch.
- The hybrid path is retained as the **fallback mesh** for shapes no family covers — offered
  explicitly, never silently substituted (ADR-0003 territory if that ever changes).
