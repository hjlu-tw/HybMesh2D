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
