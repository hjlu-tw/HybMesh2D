# Three reference cases from the solver's own grids

**A RESEARCH NOTE, and three EXEMPLARS.** Companion to
`jaxa-30p30n-reference-mesh.md`, which took one externally-produced mesh apart. This one does
the same for the three cases in `Mesh_Gary/` (outside this repo, alongside it), because they
are what this group's solver is actually fed and so they are what "a good mesh" has to mean
here. Nothing is binding; no rule, gate or source file was changed to write it. 2026-10-15.

The three are not one standard. **They are three different ones**, and the first useful thing
they say is that a single quality target would be wrong for all three.

## The `.grid` format, deduced

No reader existed. The layout below is the only one whose arithmetic closes **to the byte** on
both files, and `tools/scripts/read_solver_grid.py` reads it:

```
int32   version (1), ncell, nvert, nbface
ncell  x (int32 k, int32 node[k])     k = 3 in both cases; nodes are 0-based
nvert  x (double x, double y)
nbface x (int32 nodeA, nodeB, cell)   the third int names the OWNER CELL --
                                      verified on 200 of 200 sampled faces
```

The companion `.bc` is ASCII: its first line names the `.bc.def`, then one line per boundary
face giving `face_index segment_no`. `.bc.def` maps `segm_no` to a `bc_flag`, and a flag may
carry a parameter (`4    3  4.622` in the cone's).

## Case 1 — `schardin`: an ISOTROPIC mesh, and no boundary layer at all

461,858 triangles, 232,375 vertices, 2,890 boundary faces, over x ∈ [−5, 9.232], y ∈ [0, 5]
(the half plane; y = 0 is the symmetry line).

| | |
|---|---|
| body | a 30° wedge: (0, 0) → (1.7321, 0) → (1.7321, 1), apex upstream |
| boundary segments | 0: the symmetry line, 1,270 faces · 1: the outer boundary, 810 · 2: the wedge, 810 |
| **edge ratio** | **median 1.170, p95 1.454, max 4.218** |
| cell edge | median 0.0167, p95 0.0330, max 0.0481 |
| near the wedge | 66,895 cells at a mean edge of 0.0073 |
| downstream (x > 5) | 86,469 cells at 0.0238 |
| wedge surface | face length 0.0036, first cell 0.0015 |
| **wall layers** | **2, first height 0.00150, growth 1.010, stack 0.00302** |

**The indicator: a THIN boundary layer — two cells — under an otherwise near-equilateral mesh
whose size varies by about 3× over the whole domain.** The layer's own aspect ratio is about
2.4, not the 40 of a viscous mesh, and it is about 0.2 % of the wedge's length: enough to put
a cell face on the wall and no more.

> **A WRONG CLAIM, CORRECTED, AND THE REASON IT GOT PAST ME.** The first version of this note
> said "there is no boundary layer and no anisotropy", and a reader who knows the case said
> flatly that it has one. It does. **Aggregate statistics over a whole mesh cannot see a layer
> that is 1–2 % of its cells**: 810 wall faces × 2 layers is 1,620 of 461,858, so the p95 edge
> ratio of 1.454 is untouched by it. Binned against distance from the wedge the layer is
> obvious — aspect 2.17 in the first 0.005, 1.79, 1.60, 1.22, then the 1.18 background — and
> the node distances fall in three sharp shells at 0, 0.00150, 0.00302. I had even measured
> the first cell at 0.0015 against a 0.0036 face and written "a ratio of 2.4, not 40", reading
> a thin layer's own aspect ratio as evidence that there was no layer.

## Case 2 — `vki-cone`: wall-resolved, strongly graded

528,000 triangles, 265,341 vertices, 2,680 boundary faces, over x ∈ [−10, 159.11],
y ∈ [0, 50].

| | |
|---|---|
| body | the cone, segment 4: (0, 0) → (159.11, 37.5), with a blunt nose (points at x = 0 up to y = 0.013) |
| boundary segments | 1: inflow x = −10, 170 faces · 2: outer, 1,170 · 3: the axis ahead of the cone, 240 · 4: the cone, 1,100 |
| **edge ratio** | **median 3.376, p95 34.205, max 80.589** |
| cell edge | median 0.136, p95 0.310, max 0.571 |
| wall first cell | 0.0020 at the nose, 0.0031–0.0042 along the cone |
| wall surface spacing | 0.0040 at the nose, 0.074–0.195 along the cone |
| wall cell aspect | 2 at the nose, 18–80 along the cone |
| **wall layers** | **44 at x ≈ 40, first height 0.00432, growth 1.020, stack 0.2998** |

**The indicator: a first cell of 2–4 × 10⁻³ against a body 159 long — about 2 × 10⁻⁵ of the
body — carried by triangles whose aspect ratio reaches 80.** The nose is the exception and it
is deliberate: there the surface spacing collapses to the first-cell height, so the cells are
isotropic exactly where the stagnation gradients are.

## Case 3 — `30P30N_jaxa`

Taken apart in `jaxa-30p30n-reference-mesh.md`: 20 structured body-fitted ribbons about 1.5 %
chord deep inside 1.01 M unstructured triangles, the far field capped and nested.

## What the three together say

1. **The quality target is a property of the PHYSICS, not of the mesher.** Edge ratio median
   1.17 is right for `schardin` and would be unreachable (and pointless) for `vki-cone`, whose
   median is 3.38 and whose p95 is 34.
2. **All three carry a wall layer, and what differs is its DEPTH**: 2 cells on the inviscid
   wedge, 44 on the viscous cone, about 95 in the 30P30N's ribbons. "Does it have a boundary
   layer" is the wrong question; "how many cells deep, at what growth" is the right one.

**How a layer is measured, since getting this wrong is what the correction above was about.**
A layer's nodes sit at ONE distance from the wall, so clustering node distances finds the
shells — but that distance varies along a curved or graded wall, so the stretch of wall has to
be short enough that the layer is flat. Over ten units of the cone the clusters smear into one
and the method reports "no layers"; over ONE unit it reports 44 at growth 1.020.
`wallstack.py` in the scratchpad does it.
3. **All three are triangles in the end.** Whatever the construction, the solver is fed an
   unstructured triangular grid with an explicit boundary-face list naming the owner cell —
   which is the shape this repo's STAR-CD export already has, under other names.

## Every case rebuilt to this standard

`redraw.py` in the scratchpad rebuilds all fifteen benchmark geometries the same way, with
ONE choice per case — how deep the wall layer is — and everything else derived:

| | shallow (the wedge's) | deep (the cone's) |
|---|---|---|
| layers | 2 | 44 |
| growth | 1.010 | 1.020 |
| first cell | face spacing / 2.4 | face spacing / 40 |

plus, for every case, a surface size of 0.002 L, a far-field **cap** at 0.05 L and a linear
growth of 0.02 from the layer front — the three things all three references do.

**The first cell is set against the FACE SPACING, not against L, and the first version of the
driver got that wrong.** Taking the cone's first cell as a fraction of its LENGTH (2.7 × 10⁻⁵ L)
and applying it to a body whose own points are 1.7 % of L apart gives a wall cell of aspect
ratio 600 against the reference's 38, and the overall median edge ratio came out at 105 to
1,085 against the cone's 3.38. What the two references hold constant is the ratio of the face
to the first cell: 38 viscous, 2.4 inviscid.

**The table below is the FIRST rebuild and is kept as it was measured.** What replaced it, and
why, is "The seam, and the surface" at the end of this note; the numbers there are the current
ones.

| case | layer | cells | all med | bulk med | bulk p95 |
|---|---|---|---|---|---|
| bump | shallow | 13,198 | 1.165 | 1.064 | 1.560 |
| nozzle | shallow | 23,894 | 1.120 | 1.064 | 1.397 |
| wedge | shallow | 11,722 | 1.138 | 1.072 | 1.386 |
| diamond | shallow | 167,888 | 1.000 | 1.000 | 1.230 |
| bfs | deep | 71,988 | 4.214 | 1.000 | 1.648 |
| cavity | deep | 29,144 | 21.249 | 1.059 | 1.332 |
| diffuser | deep | 34,930 | 17.620 | 1.079 | 1.649 |
| turek | deep | 72,262 | 13.893 | 1.076 | 1.709 |
| sqcyl | deep | 380,240 | 1.000 | 1.000 | 1.111 |
| dcyl | deep | 433,616 | 1.000 | 1.000 | 1.151 |
| tricyl | deep | 393,728 | 1.000 | 1.000 | 1.131 |
| naca0015 | deep | 189,862 | 1.000 | 1.000 | 1.243 |
| naca4412 | deep | 189,696 | 1.000 | 1.000 | 1.233 |
| tandem | deep | 456,278 | 1.000 | 1.000 | 1.175 |
| twoelem | deep | 326,742 | 1.096 | 1.044 | 1.320 |
| **schardin (ref)** | 2 | 461,858 | **1.170** | — | 1.454 |
| **vki-cone (ref)** | 44 | 528,000 | **3.376** | — | 34.2 |

**The bulk is isotropic in all fifteen** — median 1.00–1.08, p95 1.11–1.71 against the
reference wedge's 1.454. The whole-mesh median is the figure that moves, and it moves with the
layer's SHARE of the mesh rather than with its quality: on the external cases the far field is
large so the layer is a few per cent and the median is 1.00, while on the small internal
domains (cavity, diffuser, turek) the layer is most of the mesh and the median is 14–21. The
cone sits between at 3.38 because its layer is 18 % of its cells. A whole-mesh median is
therefore not a quality figure at all; it is a mixture ratio, and the **bulk** split is the one
to read — which is the same lesson, from the other side, as the layer this note first said
`schardin` did not have.

Verified on two of them by clustering node distances: `rd_wedge` reports first 0.020833 at
growth 1.010, `rd_cavity` first 0.000417 at growth 1.020 — the two recipes exactly. The shell
counts come out 5 and 47 rather than 2 and 44 because `BL_TRANSITION_LAYERS 3` adds three more
above the stack, which is the mesher's own doing and is worth knowing when a layer count is
being compared with a reference's.


## The seam, and the surface

The gallery of the fifteen showed one thing the quality figures above do not: a hard line where
the layer ends and the triangles begin. **The bulk figure cannot see it** — it is a ratio within
each cell, and a cell can be perfectly equilateral while its neighbour across the seam is ten
times its size. The two changes below are a reply to that, and both land in `redraw.py` and the
new `curvsample.py` in the scratchpad rather than in the mesher.

### The transition count is SOLVED FOR, not declared

`BL_TRANSITION_LAYERS 3` at growth 1.15 multiplies the last base layer by 1.52. On `naca0015`
that leaves the outermost layer 1.04 × 10⁻³ thick against a surface step of 1.15 × 10⁻², so the
first triangle is **11.3 times** the last structured cell — and because both ends of that ratio
are fixed fractions of the surface step, **every deep case had the same 11.3 and every shallow
case the same 1.55**, whatever its geometry. The count is now

    nTrans = log(surface step / last base layer) / log(rate),   rate = 1.20

which is the arithmetic of the mesher's own `BL_AUTO_TRANSITION_LAYERS 2`, done in the driver so
that the number lands in the `.dat` and the case states it. All fifteen now end the layer
within **0.95–1.09×** of their own surface step.

**It must be clamped, and finding the right clamp took two wrong ones.** Left to the mesher,
`bfs` and `diffuser` asked for total layer heights of 0.50 and 0.91 inside ducts 1.00 across and
both died on a self-intersecting front (`HYBMESH_ERROR 5`). The height is therefore bounded by
the room the geometry has: the nearest approach of two walls, counted inward for an `int` case
and only between separate bodies for an `ext` one — measuring an external body's self-clearance
would have strangled every aerofoil on its own thickness (naca0015: 0.033). Two readings of
"nearest approach" were wrong before that:

- **An arc-length window.** Skipping same-body pairs within 8 % of the perimeter called two
  points 0.026 apart on Turek's 0.1 cylinder a gap, and that one pair clamped the whole case
  from 15 transition layers to 5. The test that works is the **chord against the walk**: a real
  gap is one you cross in much less than it takes to walk round, so a pair whose straight-line
  distance exceeds 0.6 of its arc distance is two points on one stretch of wall.
- **Accepting the clamp.** `bfs` and `diffuser` cannot bridge at any count because their walls
  are coarse against their own ducts — the surface step is a twelfth and a seventh of the duct
  width. Refining the wall lowers the target and the first cell together, so the room the layer
  needs falls faster than the gap it must cross: at 2× and 4× both bridge. `curvsample.densify`
  does it, rebuilding the `.meta` segment ids and corner flags at the new count.

### The surface points are distributed by CURVATURE

Most of these bodies were drawn at uniform arc length, which spends the same resolution on a
NACA leading edge as on its flat middle. `curvsample.py` redistributes each segment, keeping its
point count and both endpoints so the `.meta` survives, under the sagitta rule

    ds ∝ 1 / sqrt(k)

which is a property of the curve and converges in one pass. **This is deliberately NOT the
repo's own `Spacing::generateCurvature`**, which weights a node by its TURNING ANGLE — that is
curvature times the spacing the node already has, so the answer depends on the input
distribution and a second pass moves the points again.

Two rules the first version lacked, both found by running it:

- **A polygon is left alone.** Its curvature is all on isolated corner nodes, which are already
  segment boundaries; what the straight sides report is floating-point noise, 4 × 10⁻⁶ against a
  corner's 120 on `tricyl` and 9 × 10⁻¹⁴ against 158 on `diamond`. Testing `p95 > 0` called both
  of those curved and clustered their flat sides around nothing. The test is the RATIO to the
  corner.
- **The coarsening is capped against the INPUT, not against uniform.** Uniform is the wrong
  reference for a segment that was graded on purpose: against it the three curved ducts still
  reached 16–23× step ratios, because a long wall carrying few points is coarse to begin with.
  A step may not exceed 1.3× the segment's own coarsest step, and the blend to the full rule is
  solved by bisection per segment.

`naca0015` and `naca4412` each closed on **three copies of (1, 0)**, which left a sliver pair at
the trailing edge whose neighbours differ in area by **393×** — a bigger jump than the seam this
round is about, in the same picture. Coincident points are now dropped. The remaining trailing
edge fan still has ~0.036 % of its edges above a 4× area ratio, which is what the innermost ring
of a fan at a cusp is, and nothing was done about it.

### A corner is a step, not a cliff

The outlines were drawn with a FLAT POINT COUNT PER SEGMENT — 40 a side, whatever the side
measured — so every corner was a step-length cliff: 2.07× across the wedge ramp's x = 1.0,
and 20×, 19×, 10× and 60× on bfs, Turek's channel, the diffuser and the two aerofoils. Each
segment now takes a share of the points proportional to its own arc length. Two further rules
were needed before that was actually continuous, and both were found by measuring the result:

- **A segment runs to the NEXT segment's first point.** These outlines leave the corner itself
  to the segment that starts there — the wedge's floor stops at x = 0.975 and the ramp begins at
  x = 1.000 — so resampling a run between its own two ends leaves that last 0.025 as a short step
  at every corner. The span now ends on the next corner and the points go at
  `linspace(0, L, n+1)[:-1]`.
- **The point budget is shared over the WHOLE outline, in the curvature pass too.** Normalising
  two neighbouring segments separately put the cliff straight back: the wedge's floor came out at
  0.0276 against the ramp's 0.0417, a 1.5× jump where there is no feature.

The curvature density is also **scaled and clamped against the outline's own uniform step**. The
sagitta rule gives a shape, not a size, and letting it spend the full 10× spread put a 0.143 face
next to a 0.0145 one on a wedge whose uniform step is 0.042. The coarse end is now capped at 1.5×
uniform and the profile is rescaled until it spends exactly the point budget — clamping changes
the spend, so the two converge together. **All eighteen outlines now have a worst adjacent step
ratio of 1.20×.** The per-segment blend-back-to-uniform that the first version used is gone: it
could not have fixed this, because a segment given too few points has too few however they are
placed.

### A boundary that is not a wall does not grow a layer

The wedge ramp's side and upper boundaries are drawn as `wall` because the outline is one closed
loop, but the case is a ramp in a free stream and only the floor is viscous. The sidecar is
written at **version 3** for this: version 2 has no `grow_bl` column and the mesher reads a
missing one as 1.

**Doing the same for every inlet and outlet was tried and REVERSED.** Marking them from the BC
breaks bump, nozzle, diffuser and Turek: Gmsh returns an empty far field ("the domain loop likely
failed to close", `HYBMESH_ERROR 6`) while the boundary layer itself is drawn correctly. Measured
on the nozzle one end at a time — the two ends of a symmetric duct, both straight, both vertical:

| nozzle | result |
|---|---|
| outlet no-BL, inlet grows | 24,863 cells |
| inlet no-BL, outlet grows | **empty far field** |
| both no-BL | **empty far field** |

It is not the closing duplicate point and not where the run sits in the point list: dropping the
duplicate and rotating the outline by half its length both reproduce it, and the junction scheme
reports `2 handled` with no warning either way. So the no-BL table carries only what was measured
to work — the wedge, and bfs's two outlets and inlet — and **the asymmetry is a mesher defect
still to chase**.

### The fifteen, rebuilt again

| case | layer | base + trans | cells | bulk med | bulk p95 | last layer ÷ face |
|---|---|---|---|---|---|---|
| bump | shallow | 2 + 5 | 13,002 | 1.079 | 1.608 | 0.95 |
| nozzle | shallow | 2 + 5 | 25,049 | 1.069 | 1.382 | 0.95 |
| wedge | shallow | 2 + 5 | 12,407 | 1.065 | 1.379 | 0.95 |
| diamond | shallow | 2 + 5 | 168,504 | 1.000 | 1.218 | 0.95 |
| bfs | deep | 44 + 15 | 289,804 | 1.056 | 1.325 | 1.09 |
| cavity | deep | 44 + 15 | 34,950 | 1.062 | 1.376 | 1.09 |
| diffuser | deep | 44 + 15 | 192,980 | 1.061 | 1.335 | 1.09 |
| turek | deep | 44 + 15 | 189,682 | 1.062 | 1.407 | 1.09 |
| sqcyl | deep | 44 + 15 | 386,494 | 1.000 | 1.100 | 1.09 |
| dcyl | deep | 44 + 15 | 442,614 | 1.000 | 1.188 | 1.09 |
| tricyl | deep | 44 + 15 | 401,944 | 1.000 | 1.122 | 1.09 |
| naca0015 | deep | 44 + 15 | 194,732 | 1.000 | 1.223 | 1.09 |
| naca4412 | deep | 44 + 15 | 195,530 | 1.000 | 1.235 | 1.09 |
| tandem | deep | 44 + 15 | 460,222 | 1.000 | 1.169 | 1.09 |
| twoelem | deep | 44 + 15 | 352,280 | 1.044 | 1.322 | 1.09 |

The bulk stays isotropic (1.00–1.08 median, 1.10–1.73 p95), so the extra layers bought the seam
without costing cell shape. `bfs` and `diffuser` grew most — 72k to 140k and 35k to 187k — and
that is the wall refinement, not the transition: the layers themselves REPLACE triangles the far
field would otherwise have put there, which is why `naca0015` moved only 189,862 → 194,690.

**Measured on the meshes, not on the recipe.** Adjacent-cell area ratios over every internal
edge, against the first rebuild: `cavity` 240 edges above 4× → **0**, max 11.8 → 3.0; `naca0015`
228 → 95 (the survivors are the trailing-edge fan); `wedge` 1 → 25 → **3**, the 25 being the
intermediate state before the corners were made continuous, and the 3 that remain sitting on the
outlet where the layer meets a boundary that does not grow one. `bump` is the worst of the
fifteen at 111 edges (0.575 %) above 4× with a p99 of 2.95, and nothing has been done about it.


## Reviewed case by case, and the mesher bug that review found

The fifteen were read one at a time, and most of what came back was about the
LOOK of the layer rather than its quality figures. Three recipe changes and one
real defect.

### The deep recipe departs from its reference ON PURPOSE

44 layers at 1.020 off ds/40 give a wall cell 40 times longer than it is tall,
and a band that reads as one black mass at any zoom that also shows the body:
on naca0015 the layer's own triangle edge ratio had a **median of 16.1**. The
deep class is now **25 layers, growth 1.08, first cell = ds/12**, where that
median is **3.55** and the cells are individually legible. The last base layer
then sits close enough to the face that the bridge needs **3** transition layers
rather than 15. The viscous argument for ds/40 is untouched; these are
demonstration meshes and the look won.

### A boundary that is not a wall does not grow a layer

`wedge` and `bump` grow one on the floor only, `nozzle` not on its inlet or
outlet, `turek` only on the cylinder. **Previously every one of those grew a
layer into the flow it was meant to admit**, because sidecar version 2 has no
`grow_bl` column and the mesher reads a missing one as 1.

### A sharp tip takes a parallelogram, not a fan

`BL_CONVEX_METHOD 2` on the diamond's two tips and both aerofoils' leading and
trailing edges, with `BL_PARA_FALLBACK_ANGLE` raised to 359 — at the default 300
the parallelogram falls back to a fan on exactly the cusps it is wanted for. The
cost is visible and is geometric, not a bug: a miter at a 6-degree tip leaves a
thin wedge pointing upstream.

### D_total was wrong by r/g, and that is what broke the no-BL cases

The previous section of this note recorded four cases dying with an empty far
field when their inlets stopped growing a layer, and called the inlet/outlet
asymmetry a mesher defect to chase. It was not an asymmetry.

The growth loop multiplies by `BL_GROWTH_RATE` after every base layer EXCEPT the
last, which it multiplies by `BL_TRANSITION_GROWTH_RATE` instead. The closed form
beside it used `h0*g^L` as the first transition thickness where the loop uses
`h0*g^(L-1)*r`, so **`D_total` came out r/g too small** — 1.19x at the shallow
recipe's g = 1.01 against r = 1.2. `D_total` is what a case-1 slide absorbs along
the no-BL wall, so the lateral column reached 0.2094 while absorption stopped at
0.1823, and **a wall node landing between the two survived**. The far-field ring
then ran up to the column top, back down to that node, and up again: two
collinear edges in opposite directions, which Gmsh answers with "2 intersections
in the 1D mesh" and an empty far field. Whether a node falls inside that window
is an accident of the wall's point spacing, which is the entire reason it looked
like one end of a duct behaving differently from the other.

Both sums now replay the growth loop's rule instead of predicting it (`#ed3e460`).
**154/154 tests pass and 20 of the golden comparator's 21 cases are
bit-identical**; `multi_30p30n` moves because its fan arcs are now measured over
the height the layers really reach (56,341 -> 56,473 cells, edge-ratio median
1.2099 -> 1.2081, max unchanged).

**Three diagnostics went in with it, because every one was missing while this was
being chased**: a stalled domain-loop walk now names the node it stopped at
instead of dropping its edges silently; an empty far field reports the curve
loops it handed Gmsh with their areas, which separates "nothing closed" from
"closed, nested wrong"; and `HYBMESH_GMSH_VERBOSE` restores Gmsh's own terminal
output and dumps the segments it was handed to `farfield_edges.txt`, because
Gmsh names a self-intersection by curve tag and that says nothing about where.

### The diamond's topology, redrawn (USER-REQUESTED)

The six-block C-grid ran its radials from the body's corners straight to the far
field, so the two leaving the maximum-thickness kink were slanted the whole way
out. The replacement, `diamond2.py`, keeps the body's radials **normal to the
chord** by ending them all on an inner BOX — eight blocks of H-grid over the body
and its wake — and moves the slant outside into a **twelve-block ring** where the
radial at each box corner is a diagonal to the matching far-field corner.

| | six-block | twenty-block |
|---|---|---|
| cells | 21,504 | 41,600 |
| inverted | 0 | 0 |
| non-orthogonality max | 84.29° | **64.36°** |
| non-orthogonality mean | 17.14° | 20.20° |
| adjacent area ratio | **1.65×** | 3.63× |

Two things it took measuring to get right:

- **The far field must be the inner box BLOWN UP, not a rectangle of its own.**
  Dividing it at the same x as the box put a 19-long far piece beside a 0.5-long
  one carrying counts 41 and 25, and the cells either side of that one radial
  differed by **21x** — out at y = 9.3, where nothing is happening. Scaling every
  box corner by S about the body makes far piece k exactly S times box piece k,
  and the figure falls to 3.63.
- **This topology must NOT be smoothed.** At `MB_SMOOTH_ITERS 20` the Winslow
  pass folds **256 cells**; at 0 there are none. It buys 1.5° of mean
  non-orthogonality and costs 24° of max.

## The outermost layer, measured against the face under it

USER-REPORTED on the channel bump ("over the bump it becomes a very long
rectangle, away from it an acceptable square") and on Schäfer–Turek ("the size
change where the layer meets the triangles is too big"). They are the same
defect, and it was in four more cases nobody had pointed at yet.

The transition grows until the layer's thickness reaches **the surface step**,
and that step was the MEDIAN over the whole case. Wherever the wall is finer
than the median, the outermost cell is taller than the face it stands on — the
one shape a boundary-layer cell should never have. Measured as thickness ÷
local face:

| | before | after |
|---|---|---|
| bump, over the crest | 4.30 | 1.05 |
| NACA 0015, leading edge | 2.94 | 0.91 |
| Turek, the cylinder | **10.85** | 0.91 |
| diamond | 1.05 | 1.05 |

Turek is the extreme because its ruler was the median over the CHANNEL and the
cylinder together: a layer growing on 0.00031 faces was sized for 0.00363 ones,
and the channel does not even grow a layer any more.

Two changes, both in `spacing()`:

- **Per geometry, and only the ones that grow.** A geometry whose sidecar marks
  every segment `grow_bl = 0` is not a ruler. Where a case has more than one
  wall, each gets its own `BL_INITIAL_THICKNESS` and `BL_TRANSITION_LAYERS` as
  `KEY=VALUE` tokens on its own `GEOM_FILE` / `DOMAIN_FILE` line.
- **The finest face, not the median** — the 5th percentile, so one short face
  cannot set it. Against the finest face the last cell is square there and FLAT
  everywhere else, which is the right way round.

### BL_PARA_FALLBACK_ANGLE is not a fallback to a fan

The previous round raised it to 359 to "keep the parallelogram" on the sharp
tips. Above that threshold the code takes the **split** parallelogram, which
bisects the corner and is exactly what a very sharp tip wants; raising it forced
the diamond's 11-degree tip through the SINGLE one, whose centre ray is scaled
by `1/(1+cos)` and so shot a spike **0.105 ahead of a body 1.0 long**, with
slivers converging on it. The default 300 is right and is left alone.

### A wake that leaves along the trailing edge

USER-REQUESTED on NACA 4412's structured topology. The direction is the bisector
of the two surface tangents at the trailing edge — 0 on a symmetric section, so
**naca0015 is bit-identical** — and on 4412 it is **-0.1333**, its camber slope
there. Finding it needs the first neighbour that is a DIFFERENT point: the
generator closes the loop on repeated copies of the trailing edge, so a plain
difference gives the zero vector, which read as a 9.8-degree wake on a symmetric
section and inverted 353 cells.

**Tilting the wake alone is not enough.** With the far field's top and bottom
left horizontal, the wake block's first cell — a few thousandths tall, because
the radial is wall-clustered — had to cross a line falling 0.13 per unit x, and
**315 cells folded** between x = 11 and 19. Shearing every far-field point
downstream of the trailing edge by the same slope keeps the block's two long
sides parallel; the nose arc is upstream and untouched, so the halves still meet.
0 inverted, max non-orthogonality 42.55° unchanged, mean 4.85° -> 7.17°.

### Both duct walls, not just the floor

`nozzle` and `diffuser` wrote `ds_start` on their cross edges, which is the first
cell at the edge's START end — the floor on every one of them — so the roof was
left at whatever the law gave it. Both ends now. Non-orthogonality mean 1.08° ->
2.01° on the diffuser and 5.98° -> 6.57° on the nozzle, which is what clustering
against a sloped roof costs.

### One file, two topologies

`diamond2.py` wrote its twelve-segment far field over `diamond_far.dat` and the
six-block case next door stopped loading ("edge e_out_lo binds to segment 7").
It writes `diamond2_far.dat` now. The body is identical and is still shared.

## The redistribution was eating the drawings' own grading

USER-REPORTED: the two NACA sections needed more points at the trailing edge.
They already had them. The sections are drawn COSINE-SPACED and their last faces
run 0.0024 down to 0.0003; after the pipeline they were a flat **0.0159**.

The curvature pass was not the culprit. `rebalance` — the step that fixes the
flat-point-count-per-segment artefact — re-laid every span's points at **equal
arc length**, which is a redistribution of its own and threw the cosine away
before the curvature rule ever saw it. Two changes:

- **`rebalance` walks the INPUT INDEX, not arc length.** It still changes how
  many points each segment gets; it no longer changes how they are graded.
- **The curvature pass takes the FINER of two densities** — its own, and the
  input's — each normalised by its own 95th percentile so they are comparable.
  A drawing with grading keeps it; a drawing without gets curvature refinement;
  a uniformly drawn body is untouched, because there the two are the same
  constant.

With `n_surface` raised from 97 to 145 the trailing-edge face is now **0.0018**
against a 0.0079 median.

### The spread of the surface IS the spread of the layer's aspect ratio

The two-element sections carry a cusp at each trailing edge and came out at a
6x spacing spread. The ruler is the 5th-percentile face, so it sat six times
below their median and the layer band was **0.35 % of chord** (USER-REPORTED:
too thin). Capping those two geometries' spread at 3x lifts the ruler and the
band goes 0.0022 -> **0.0063**. That is the trade in one line: a thicker band
wants a more even surface, because the layer ends at ONE thickness while the
faces under it vary.

### Three more bodies take the parallelogram

`sqcyl`, `dcyl` and `tricyl` join the no-fan list. Their corners are 90 and 60
degrees, so the default `BL_PARA_FALLBACK_ANGLE` of 300 puts them through the
SINGLE parallelogram and the corner is a clean miter.

### Every case has two close-ups, framed to one rule

The first is a corner or tip, the second the place where the spacing changes
most, and **both frame the whole layer band plus a few rows of triangles** so
the last structured cell and the first triangle can be compared by eye. The
second windows: the bump's crest, the step's reattachment, the cavity floor, the
diffuser's second corner, the gap between Turek's cylinder and its wall, the gap
between the tandem cylinders, and the two-element slot exit.

## A polygon's corners, and the floor that was eating them

USER-REQUESTED: the square, D-shape and triangular cylinders want their surface
points denser near the corners. The rule in place said the opposite — a polygon
carries all its curvature on isolated corner nodes, which are already segment
boundaries, so leave it alone. That is right about the curvature rule and wrong
about the mesh: the corner is where the flow turns, and an evenly cut side puts
the same face there as in the middle.

A polygon is now graded toward its corners, `CORNER_RATIO` at a corner falling
to 1 at mid-side, measured in **each span's own half-length** so a short side is
graded as hard as a long one. Measured: **2.6x** finer at a corner.

**It did nothing at first, and the reason is the floor added last round.** "Never
coarsen below what the drawing had" normalised each density by its own **95th**
percentile — its FINE end. A uniformly drawn body's input density is then the
constant 1, which is also the ceiling, so the corner profile could not lift
anything above it and all three polygons came back unchanged. Normalising by the
**5th** percentile instead — the coarse end — starts both shapes at 1 and lets
them rise, and the finer wins pointwise. The floor is then only a floor.

### The spread cap came down from 10 to 3

With the normalisation fixed, `ratio` binds on everything for the first time.
The band is sized by the FINEST face, so **the spread of the surface is also how
much thinner the band is than an even surface would give**, and 10 thinned every
one of them. The two aerofoils are the exception, at 6: what was asked for there
is a finer TRAILING EDGE, and 3 caps it at 1.8x against the leading edge it
shares a budget with.

**What that exception costs, measured against each wall's very finest face**:
13 of 15 walls have an outermost layer at 1.39 or below; the two aerofoils are
**3.89** and **3.45**, at the trailing-edge cusp. That is "finer trailing edge"
and "outermost cell not standing up" competing inside one point budget, and the
user's side was taken. A layer is converging at a cusp anyway, which is not true
of a whole bump.

`twoelem` joins the no-fan list, so seven cases now take the parallelogram.
