# The JAXA 30P30N reference mesh, taken apart

**A RESEARCH NOTE, and an EXEMPLAR.** Not `.claude/rules/*.md` (what the rule is), not
`docs/design_notes/` (why a shipped rule was chosen). It records what one real,
externally-produced multi-element mesh actually IS — measured out of its own files rather
than described — so that "a mesh of the same standard" is a set of numbers this repo can be
held to instead of a feeling. Companion to `multi-element-airfoil-blocking.md`, which asked
what the FIELD does; this one measures what ONE mesh does. 2026-10-14.

**Subject.** `30P30N_jaxa/` (outside this repo, alongside it) holds a Fidelity Pointwise
2022.1.2 project `30p30n-2d8.pw` (59 MB) for the 30P30N three-element high-lift section, two
further `.pw` projects for the elements as SOLIDS, and a STAR-CD export of the latter. The
three element outlines in `examples/geometries/30p30n_jaxa_{slat,main,flap}.dat` came from
that case and are the same curves: re-extracting them from the STAR-CD `.bnd` by chaining its
1,958 WALL faces reproduces all three point sets EXACTLY (432 / 1046 / 480 points), which is
how both are known to be sound.

## How it was read

`.pw` is an undocumented tagged binary and no Pointwise is installed here, so
`tools/scripts/read_pointwise.py` reads it directly; the record grammar it relies on is in
that file's docstring. Everything below is read off the ARRAYS: a domain's points are a
double array of dims `(3, I, J)` when structured and `(3, N)` when not, its cells an int32
array of 3-tuples, and every domain is stored twice — once XYZ, once parametric UV, the
latter recognisable by every Y being exactly 0.

> **A WRONG CLAIM, KEPT AS A SPECIMEN.** Before reading the arrays I counted STRINGS — in the
> two SOLID projects (`Structured` ×0, `Unstructured` ×1, `TRex` ×41 and ×51) and in the flow
> file (`TRex` ×403) — and published "the reference uses no structured blocks at all; it is
> unstructured + TRex". The two
> `*solid.pw` files really do have 0 structured domains — they are the elements' solid
> interiors, for an immersed-boundary φ — but the FLOW mesh has **20**. Counting a word is
> not measuring a topology, and the flow mesh was the 59 MB file I had not opened.

## What it is, measured

| | count | cells |
|---|---|---|
| structured domains | 20 | 206,370 quads (211,155 points) |
| unstructured domains | 8 | 1,011,462 triangles (511,228 points) |
| **total** | | **~1.22 M** |

Each structured domain is ALSO stored as a triangulated copy whose point count is exactly
`I*J`; those are the CAE export's and are not counted twice above.

**The structured part is a set of thin, body-fitted RIBBONS — it never reaches a far field.**

| where | I × J | points | normal thickness | first cell |
|---|---|---|---|---|
| main, upper | 391 × 95 | 37,145 | 0.0152 | 1.07e−4 |
| main, upper (outer) | 391 × 61 | 23,851 | 0.0136 | 1.68e−4 |
| main, lower | 391 × 25 | 9,775 | 0.0075 | 6.13e−4 |
| flap | 181 × 155 | 28,055 | 0.0264 | 1.22e−4 |
| flap (inner) | 181 × 89 | 16,109 | 0.0240 | 1.92e−4 |
| slat | 201 × 61 | 12,261 | 0.0101 | 3.25e−4 |
| slat cove | 61 × 157 | 9,577 | 0.0712 | 1.54e−4 |
| main cove, cavity | 79 × 40 | 3,160 | 0.0119 | 4.53e−4 |
| main cove, blunt face | 16 × 71 | 1,136 | 0.0302 | 1.72e−4 |
| flap wake | 31 × 251 | 7,781 | 0.0384 | 1.26e−4 |

Lengths are in chords (the stowed chord is 1). Median ribbon thickness over all 20 is about
**0.015, i.e. 1.5 % chord**, and the normal distribution inside a ribbon is nearly UNIFORM:
the last interval over the first is 0.2 to 2.2, not the 50–100× of a stretched boundary
layer. First cells run 8e−5 to 1.5e−3 chord.

**The geometry it is built on** (measured off the same curves): slat gap 2.94 % chord,
overlap −2.50 %; flap gap **1.27 %**, overlap **+0.27 %**; chords 0.1492 / 0.8316 / 0.2982;
chord-line angles −46.01° / −3.24° / +29.56°. Those match the published 30P30N numbers
(2.95 % / −2.5 %, 1.27 % / 0.25 %), so this is the standard configuration.

## The recipe, in one paragraph

Wrap every surface — including inside both coves — in a thin structured ribbon about 1.5 %
chord deep with near-uniform normal spacing; where ribbons meet, meet them POINT TO POINT
(six blocks share the line x = 0.8555 through the flap slot); stop there and hand the outer
boundary to an unstructured field, which carries ~5× more cells than the ribbons do and is
refined in boxes over the slot and the wake. No ring is wrapped to a far-field box, and no
structured block is asked to span from a body to the domain boundary.

## What that costs us, and what it buys

This repo's `MESH_MODE 1` rings run from the body to an axis-aligned CARTESIAN BOX, and every
hard limit the two-element experiments hit is a consequence of that one assumption:

- two boxes must be disjoint, so two elements whose bounding boxes intersect cannot both be
  wrapped — and the real 30P30N's +0.27 % flap overlap makes them intersect, which is a
  PROOF, not a quality problem;
- the gap between two elements is bounded below by TWO ring thicknesses, measured at 3.7 %
  chord on NACA 4412 sections against the real 1.27 %;
- a hooked element (the slat) needs a star centre for the angular correspondence, and even
  the best one leaves the division 1.6 %–46 % uneven against a circular far field.

**None of these exist for a ribbon**, because a ribbon's outer boundary is wherever the
author stops. The reference does not solve these problems; it never has them.

## Targets this sets

A mesh "of the same standard" on the same geometry is one that meets these, measured the
same way:

1. every wall carried by structured/quad cells to a depth of ~1.5 % chord, both coves included;
2. first cell at the wall ~1e−4 chord, normal spacing within an order of magnitude of uniform;
3. the 1.27 % slot resolved with cells on both sides, no collapse at the main's thin tail;
4. the near field (x ∈ [−0.2, 1.4], y ∈ [−0.5, 0.5]) carrying ~460 k cells, of which the
   unstructured part has a median triangle edge of ~0.0039 chord;
5. ~1.2 M cells in total over a domain of x ∈ [−5, 4], y ∈ [−5, 3];
6. no inverted or degenerate cell anywhere.

## Where this repo stands against them, measured

`config/hybrid_30p30n.dat` — the hybrid path (`MESH_MODE 0`: boundary-layer quads off every
wall, Gmsh triangles outside), on the same three curves, over the same domain. Measured the
same way, by the same scripts:

| target | reference | this repo | |
|---|---|---|---|
| 1 structured depth on every wall | 0.015 chord (median) | **0.0038** | **not met** |
| 2 first cell / normal distribution | 1.07e−4, near-uniform | 5.4e−5, growth 1.005 | met |
| 3 the 1.27 % slot | resolved both sides | resolved both sides | met |
| 4 near field (x −0.2…1.4, y −0.5…0.5) | 463,722 cells, triangle edge 0.0039 | 571,681 cells, edge 0.0034 | met |
| 5 total cells | ~1.22 M | 790,197 (1,063,840 at rate 0.010) | met |
| 6 inverted or degenerate cells | 0 | 0 | met |

Triangle quality outside the layer: median edge ratio 1.050, p95 1.321 (1.0 is equilateral).
Every figure in that column is read off ONE run of that config, because this mesher is not
bit-reproducible: two runs of it differ by about 0.05 % in cell count (790,197 against
789,769), which is the same wobble `tools/scripts/golden_mesh.py` exists to see past.
The four zero-area cells a naive shoelace finds are the domain's four boundary LINE elements,
not degenerate triangles — worth saying, because that is how the first count of them read.

**Target 1 is the one that is not met, and the reason is structural rather than a setting.**
The boundary layer is capped at 0.0038 chord by the main element's aft tongue, which is about
0.003 thick: two fronts grown from its two sides meet. Measured, not assumed — it builds at
0.0038 and refuses at 0.0042 with `Critical proximity detected after retreat`, and the same
cap applies before the 1.27 % slot is reached, so the slot is not what binds. The reference
does not grow two fronts into each other there: it lays structured blocks that SHARE the
region, which a front-marching layer cannot do. **What this repo would need is a front that
stops at a medial axis and matches its neighbour, rather than one that retreats and fails** —
and that is a feature, not a parameter. Until then this geometry carries a structured ribbon
a quarter as deep as the reference's, with everything else at or beyond the same standard.

## The PARTITIONING, which is the part worth copying

Cell counts were the wrong thing to match. What the reference has that this repo's structured
path did not is a **decomposition**, and it is readable off the 20 domains' own sides:

- **P1 — one band per stretch of wall, cut end to end at the body's features.** The main's
  upper surface is one band from x = 0.03 to 0.856; the lower is a separate band that stops
  at the cove's mouth (x = 0.7364). Features end bands; they are never crossed.
- **P2 — bands are STACKED in the normal direction.** Main upper: 391×95 inside, 391×61
  outside, sharing a full-length interface. Flap: 181×89 inside, 181×155 outside. Main lower:
  391×25 and 331×25. This repo already has the shape — `config/multiblock_tworing*.dat`.
- **P3 — the outer boundary of the outermost band FOLLOWS THE BODY.** It is not a box, not a
  circle. This is the whole difference.
- **P4 — a sharp tip ends its bands and starts a WAKE band**: the flap's 31×81 and 31×251 run
  downstream from its trailing edge rather than wrapping round it.
- **P5 — a concave pocket gets its own patch**: the main's cove is 16×71 on the blunt face,
  79×16 and 79×40 in the cavity, plus 83×95 and 161×25 around the tail. The ribbon does not
  continue through a cove.
- **P6 — every band carries its own normal count** (the reference runs 16, 25, 40, 61, 71,
  81, 89, 95, 155, 251), so a thin stretch of wall and a thick one never have to agree.

### Reproduced, and what it is worth

`ribbon.py` in the scratchpad builds P1–P3 and P6 in `MESH_MODE 1`: the body, then its offset
by d1, then that curve's offset by d2, all cut at the SAME indices, filled by two stacked
rings. The offsets come from `app/services/geometry_offset.offset_points`, which returns one
point per source point in the same order — so **the correspondence is the identity**. There is
no angle to cross, no star centre to find, no box node to aim at. Measured on the three
elements, against the box-anchored O-ring the same scratchpad built for the slat:

| element | wrapped to a circle/box | wrapped to its own offset |
|---|---|---|
| slat (the hook) | 2,165 inverted, mean 45.95°, jump 1,527× | **36 inverted, mean 9.38°, jump 67×** |
| flap | — | 73 inverted, mean 3.82°, jump 57× |
| main | — | 56 inverted, mean 10.49°, jump 10.4× |

Two further things it measured, both of which are P4 and P5 arriving from the other direction:

- **The remaining folds are all at sharp tips**, in the two blocks either side of them — and
  that is not a tuning miss. Offsetting a cusp puts its vertex at `d / cos(half the turn)`, a
  spike; clamping that displacement to 1.6 d was tried and made it WORSE (36 → 73 folds, jump
  67× → 6,397×), because pulling the outer edge back pinches the band where it is thinnest.
  **A band must not close around a cusp** — which is why the reference ends it there (P4).
- **The main's second band caps itself at 2e−5.** `geometry_offset.largest_offset` refuses
  anything more, because the cove's concave corner makes an outward offset self-intersect
  almost immediately. The ribbon cannot pass through a cove — which is P5, derived here
  rather than copied.

### The two-element case, rebuilt under these rules

The main + flap pair this repo's structured path had fought over — NACA 4412 chord 0.85 and a
0.32 flap deflected 30° — was rebuilt with P1–P3 and P6 and nothing else. Each element carries
two stacked bands on its own offsets; the two elements **share nothing at all**: no box, no
grid line, no count, no corner. The flap's position is solved for so that the surface gap is an
input, and the band depth is then bisected down until the two outermost band edges do not meet:

| surface gap | band depth | inverted | non-orthogonality (mean) | neighbour area ratio |
|---|---|---|---|---|
| 11.8 % chord | 0.0369 | 0 | 5.98° | 10.08× |
| 4.7 % | 0.0139 | 0 | 6.31° | 4.55× |
| 2.9 % | 0.0082 | 0 | 6.48° | 3.12× |
| 1.8 % | 0.0044 | 0 | 6.61° | 2.16× |
| **1.3 % (the real 30P30N flap gap)** | 0.0028 | **0** | **6.65°** | **1.75×** |
| 0.7 % | 0.0012 | 0 | 6.68° | 1.35× |

Against the box-anchored family on the same two sections: its floor was **3.7 % chord** (43
cells folded there, 0 at 4.0 %), its best mean non-orthogonality 10.12° and its best neighbour
area ratio 6.28×. The bands reach **0.7 %** with 0 inverted at 6.68° and 1.35×, and the figures
get BETTER as the elements close rather than worse, because a thinner band is a more uniform
one. What the mesh covers is different and the comparison must say so: the box family meshed
the whole domain, these bands mesh only themselves — the reference's structured region is the
same shape, and what lies outside it is the unstructured field's job.

> **A DEFECT THIS FOUND IN ITSELF.** Two bodies' band stacks share nothing, which is what frees
> them — and it is also why **a band of one can run straight THROUGH a band of the other and
> still be reported as 0 inverted cells**, since every block is sound in itself. The first run
> at the 1.3 % gap did exactly that: three proper crossings between the two outermost edges,
> and a quality banner with nothing to say about it. The depth is now bisected against that
> check, and the table above is measured with it on. **A per-block quality report cannot see a
> between-body overlap; nothing in the topology schema can either.**

## The partitioning OUTSIDE the bands

The bands are half of it. Outside them the reference stops following the body and follows the
FLOW, and that half is just as explicit — eight unstructured domains, measured:

| covers | triangles | median edge |
|---|---|---|
| x 0.856…1.213, y −0.234…0.157 — the slot and the flap's wake | 46,078 | **0.00223** |
| x −0.4…1.4, y −0.45…−0.014 — under the elements | 100,554 | 0.00390 |
| x −0.4…1.4, y 0.005…0.40 — over them | 68,698 | 0.00423 |
| x −0.4…0.011, y −0.45…0.40 — ahead of them | 27,072 | 0.00430 |
| x 1.213…1.4, y −0.45…0.40 — behind them | 14,040 | 0.00442 |
| x −5…4, y −5…3 and two strips — the far field | 754,820 | **0.01520** |

- **O1 — axis-aligned NESTED BOXES, not body-following shapes.** The box is the right tool
  here, and only here; it was wrong when wrapped to a body, which is the whole of the earlier
  argument in one sentence.
- **O2 — three levels, each about 2–4× the previous**: 0.0022 → 0.0041 → 0.0152. The jump
  across a box boundary is a real 2–4× in edge, 4–16× in area; the reference accepts it there.
- **O3 — each level is TILED into simply-connected pieces** (the inner box into under / over /
  ahead / behind), rather than being one domain with holes in it.
- **O4 — the far field is CAPPED, not grown without limit.** It holds 0.0152 all the way to
  5 chords, which is where 469,626 of the mesh's 1.01 M triangles are. A mesh is not "coarse
  far away"; it is coarse up to a ceiling and then constant.
- **O5 — the finest box is DOWNSTREAM**, over the slot and the wake, which no law in distance
  from the wall can produce: at the trailing edge that distance starts growing immediately.

### What this repo can express, and the thing I had misread

The hybrid path's size field is `s = min(hBase + max(0, d − dBuffer) · rate, farFieldSize)`
with `d` the distance from the boundary-layer front, plus one Threshold field per refinement
seed. Mapping O1–O5 onto it:

- **O4 is `FARFIELD_MESH_SIZE`** — exactly a cap, and the reference's own 0.0152 is what to
  put there;
- **the ramp between levels is `FARFIELD_GROWTH_RATE`**, linear in distance;
- **O5 is a seed, and the seed's `radius` is an inverse GRADIENT, not a box size.** The
  Threshold runs `size` at the seed to `farFieldSize` at `radius`, so the gradient is
  `(farFieldSize − size) / radius`. An earlier attempt here put a seed along the chord with
  size 0.004 and radius 0.45 **while `FARFIELD_MESH_SIZE` was 1.0** — a gradient of 2.2 per
  unit length — and concluded "the seed did nothing", which was true and the wrong lesson. With
  the cap at the reference's 0.0152, the radius for a 0.02-per-unit wake region is
  `(0.0152 − 0.0022) / 0.02 = 0.65`.
- **O3 has no counterpart and needs none here**: tiling is how Pointwise keeps each domain
  simply connected, not a property of the mesh.
