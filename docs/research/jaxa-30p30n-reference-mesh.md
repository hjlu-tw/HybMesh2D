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
