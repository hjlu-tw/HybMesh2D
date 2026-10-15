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
