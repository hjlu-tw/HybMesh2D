# Meshing the cove and the trailing edges of a 30P30N-class section

**A RESEARCH NOTE.** Not `.claude/rules/*.md` (what the rule is), not `docs/design_notes/`
(why a shipped rule was chosen). It records what the people who publish 30P30N-class high-lift
meshes actually do, end to end, with the weight on the two places this repo has found hardest:
the main element's **COVE** (a concave pocket an outward offset cannot be wrapped through) and
the **TRAILING EDGES** (where a wake band helps at one tail and ruins the mesh at another).
Nothing here is binding; no rule, gate, test or source file was changed to write it. 2026-10-22.

**Filename.** `how-a-high-lift-mesh-is-built.md` was suggested; I chose
`meshing-the-cove-and-the-trailing-edges.md` instead, because the architecture question is
already half-answered by the two notes below and the only parts that are genuinely open are
the cove and the tails.

**Subject.** Two notes in this repo already cover the ground around this question:
`docs/research/multi-element-airfoil-blocking.md` (what the FIELD does about topology families,
the slot, block corners, the outer boundary, the wake cut, element-to-element interfaces, and
the published sizing rules of thumb) and `docs/research/jaxa-30p30n-reference-mesh.md` (ONE
real externally-produced mesh taken apart by measurement). **This note states up front what
those answer, then adds only what is new**, and says where a source contradicts them.

## How to read the markers

- **[V]** verified in a primary source I read myself (the document's own text, a NASA page, a
  vendor manual, a paper's body).
- **[I]** my own inference or derivation from a **[V]** fact. Stated as reasoning, not fact.
- **[2nd]** I could only find this secondhand. Treat as unconfirmed.

Several sources below are NASA PDFs whose text layer squashes spaces
(`Whengeneratingastructuredmesh…`). Where that happened I have **restored the word spacing and
say so at the quote**; nothing else is altered.

---

## 0. What the two existing notes already answer — do not re-derive these

**`multi-element-airfoil-blocking.md` already establishes:** that nobody wraps an element's
ring to a rectangle inside a conforming Cartesian H grid (L1); that the rectangle is
nevertheless what ICEM's block algebra produces (L2); that the field left point-matched
multi-block for this geometry class, with GMGW-1's "circuitous paths" sentence and the 27–36×
block-count ratios as the evidence (L3); that a conforming 2-D three-element grid takes 26
blocks (Kim/Alonso/Jameson) (L4); the four named topology families and that structured overset
is the standard (§1); that **the gap/slot gets its own zone in every 2-D system found**, with
the HiLiftPW constant-spacing wake band (GR2 = 1.0, length ≈ 2× the gap) and MSES's
facing-surface spacing fudge (§2); that the ring's outer boundary is a marched, outward-splayed
curve and not an input (§3a); that the wake cut need not be straight (§3b); **Chan's 0.2 %-chord
trailing-edge threshold** and its two remedies (§3c); that nobody terminates the main's wake cut
on the flap (§3d); that the workshops permit all three interface types and require none (§4);
and the sizing tables — first-cell spacing, growth rate, surface clustering, far field (§5).

**`jaxa-30p30n-reference-mesh.md` already establishes**, by measurement of the mesh itself: the
20 structured domains / 9 unstructured domains / ~1.22 M cells split; the ribbon table (median
1.5 % chord deep, near-uniform normal spacing); the partitioning rules P1–P6 and the outer rules
O1–O5; that the cove's blunt face gets its own 16×71 ribbon plus 79×16 / 79×40 cavity patches
and 83×95 / 161×25 around the tail; that the flap's tip starts 31×81 and 31×251 wake bands;
and that `geometry_offset.largest_offset` caps the main's second band at 2e−5 because an outward
offset self-intersects at the cove's concave corner.

**Everything below is additional.** Where I restate one of the above it is only to attach a new
source to it, and I say so.

---

## Lead: the five answers that change what this repo should do

### L1 — There is no workshop rule for a cove. There is a **generator-level** rule, it is forty years old, and it says the opposite of "offset the wall". **[V]**

I counted the words in all four AIAA High Lift Prediction Workshop gridding-guideline documents
(the same four `multi-element-airfoil-blocking.md` §4 read end to end). The strings **`cove`,
`cavity` and `concave` occur ZERO times in all four**; `block` occurs zero times; `topolog`
occurs once each in HiLiftPW-1 and -2 and zero times in HiLiftPW-3 and HLPW-4. **[V]**

What exists instead is a rule in the manual of the hyperbolic marcher that NASA's overset
practice is built on — **HYPGEN** (Chan, Chiu & Buning, NASA TM-108791), §2.3.5 "Basic Rules on
the Construction of a Good Surface Grid", rule (3), verbatim (one OCR artefact removed):

> "The sharper the angle of a convex corner, the more important it is to cluster points towards
> the corner which helps the volume grid to achieve good resolution in this region. **On the
> other hand, the sharper the angle of a concave corner, the more important it is to NOT cluster
> into the corner. A uniform or declustered surface grid spacing at the concave corner can
> significantly ease the generation of the volume grid.**"

and rule (2): "**The grid spacings on each side of a convex or concave corner should be about
equal.** The sharper the corner, the more important it is to have equal grid spacings on each
side." **[V]**

And §2.4.1(3), the remedy when a concave region folds the volume grid:

> "If there are negative cell volumes and/or Jacobians present in the 3-D grid, first try to
> adjust SMU2 and/or ITSVOL. … **A highly concave region often needs large SMU2 (greater than
> ~2) and large ITSVOL (greater than ~50). However, large values of SMU2 and/or ITSVOL can ruin
> the grid smoothness at sharp convex corners such as an O-grid wing trailing edge.**" **[V]**

SMU2 is the second-order smoothing coefficient and ITSVOL the number of volume-smoothing passes;
the manual's §2.3.4 says the spatially-variable scheme "ensures that the smoothing is small near
the body surface to preserve orthogonality. **Smoothing is increased locally by detecting
whether grid lines are converging as in concave regions**", and TIMJ/TIMK are Barth implicitness
factors "to help spread out grid lines that might converge as the grid is marched out … up to
about 4.0 for very severe concave corners". **[V]**

**The consequence for this repo is immediate and it is the single most useful thing in this
note.** A pure outward offset is the **zero-smoothing limit** of hyperbolic marching. The field
does not march a band through a cove with zero smoothing either — it would fold too. It marches
with dissipation that is *switched on by the detection of converging grid lines*, i.e. by the
very condition that makes the offset self-intersect. "A band cannot be wrapped through a cove"
is therefore a true statement about **this repo's offset construction** and a false statement
about coves. **[I]** on the application; **[V]** on every quotation.

### L2 — And the field DOES march a band straight through the cove. Measured and published, on a three-element section, with the price named. **[V]**

Chuen & Chan, *Mesh Effects on Flow Solutions for a 2-D Multi-Element Airfoil Using Structured
Overset Methods* (NASA Ames, NTRS 20205002818) — a 2-D section of the HL-CRM, slat 30°, flap
37°, c_ref = 1 m, i.e. a 30P30N-class three-element section, meshed with CGT + OVERFLOW:

> "The regions of extreme stretching in the tangential direction are **due to the concavity in
> the cove regions and the local grid lines being forced together**. **The spacing close to the
> wall is largely unaffected.**" **[V]**

There is **no separate cove grid in that system at all**. The slat's near-body mesh is an O-mesh
that wraps through its own cove, and the cove is resolved by thickening that mesh rather than by
partitioning it:

> "The uniform band of spacing is also applied to the slat to **refine the cove region and
> improve the resolution of the shear layer in the cove**." **[V]**

That **contradicts the "a cove gets its own zone" reading** that both of this repo's notes take
from Liou & Liu (a main-element-cove H grid) and from LAVA/CGT (a purpose-built slat-cove
H-grid). Both readings are right about their own sources; what is wrong is treating either as
the field's rule. The honest summary is: **a cove is gridded by its own zone when the cove flow
is the subject (aeroacoustics), and by letting the element's own mesh crowd through it when it
is not (aerodynamic force prediction)**. **[I]**

The one cove-specific instruction Chuen & Chan do give is about where NOT to put a seam:

> "Another such location is aft of the cove region in the bottom of the configuration. **Care is
> taken to not place the overlap too close to the cove regions to avoid having the overlap
> protrude into the shear layer.**" **[V]**

### L3 — "Wake band at the flap, tail patch at the main" is NOT a stated distinction. The stated practice is that **every** blunt tail gets a wake grid — and, in C topology, a cap grid **as well**. **[V]**

Same paper, Summary section, verbatim:

> "The parameter variations were performed on a baseline overset mesh with **O mesh topology for
> the near-body grids**. A priori refinement was also included in the mesh in regions where wakes
> and shear layers are expected to develop. **A wake grid is also added to each O mesh to provide
> a similar resolution to a C mesh.**" (word spacing restored) **[V]**

"each O mesh" is all three elements — slat, main and flap — on a configuration where the main's
tail sits a few percent of chord ahead of the flap, exactly this repo's case. So the reference's
asymmetry (31×81 and 31×251 wake bands at the flap's tip, an 83×95 patch at the main's tail) is
**one mesh's choice, not a rule**. **[I]**

The cap grid is the other half, and it is not an alternative to the wake grid but an addition to
it, in the C variant:

> "To avoid the issue of the explicit update along the wake line, the C mesh is split into three
> grids with an OVERFLOW tool called Ctop2. This combines the wake region into a single grid, and
> splits the grid on the geometry surface into upper and lower grids. **Finally, to improve the
> viscous resolution at the finite-thickness trailing edge, a small cap grid is added to ensure
> wall spacing at the trailing edge.**" (word spacing restored) **[V]**

**Why the distinction never has to be made there, and must be made here.** In an overset
framework the main's wake grid is simply laid over the flap's grid and hole-cut; "the majority of
the O mesh past the trailing edge is entirely cut except for the necessary overlap at the
boundaries of the wake grid". A conforming topology has no such move: a wake band at the main's
tail must be *filled*, in the 1.27 %-chord slot, against the flap. **This repo's 12 → 87 inverted
cells is the cost of the conformity, not of the wake band.** **[I]**

### L4 — The architecture (thin ribbons → unstructured field) is nobody's named method. The two named architectures it sits between are both overset, and both are named. **[V] on the names; [I] on the placement.**

- **Near-body / off-body "dual mesh"**: Wissink, *An Overset Dual-Mesh Solver for Computational
  Fluid Dynamics*, ICCFD7-1206 (2012) — "A dual-mesh unstructured/adaptive Cartesian approach …
  **An unstructured RANS solver is applied near the body surface to capture near-wall viscous
  boundary layer effects. Away from the wall a high-order adaptive Cartesian solver resolves the
  wake.**" **[V]** This is the reference mesh's shape exactly — thin body-fitted near field, box
  far field — with an **overset** hand-off instead of a conformal one.
- **HLPW's own family names.** `multi-element-airfoil-blocking.md` §L3 already lists the HLPW-4
  committee RANS families as *Tet, Prism-Tet, **Hex-Tet**, Overset*. "Hex-Tet" is the 3-D name
  for "structured hexahedral near-wall layer handing off conformally to tetrahedra" — the
  reference mesh is its 2-D instance (quad ribbons → triangles). **[I]**

What makes the reference distinctive is not the architecture but that the near-wall layer is
**hand-decomposed into 20 structured domains** rather than extruded by an advancing-layers
mesher. I found **no source that recommends that**, and no source that argues against it.

Two real teams' own stated near-body topology rules, for contrast — both new here:

- **JAXA, structured** (Murayama, Ito, Tanaka & Yamamoto, AIAA 2012-2844, HiLiftPW-1 Trap Wing,
  grids by Gridgen): "**O-O grid topology near the model surface** — To guarantee better
  orthogonality within the boundary layer; **C-O grid topology at outward**; **O-H grid topology
  at wing-body junction**"; **441 blocks**. **[V]** A *nested* topology — one topology hugging the
  wall for orthogonality, a different one outside it — which is P2 (stacked bands) stated as a
  rule by the same organisation that produced this repo's reference mesh.
- **JAXA, unstructured** (same talk): "**Advancing-layers type method w/ special treatment at
  concave corners**" for the surface grid and "**Advancing-layers type method w/ suppressed
  marching direction method**" for the volume grid, in MEGG3D, citing Ito et al., AIAA 2011-3539,
  whose stated purpose is that advancing-layers methods "**can produce poor-quality elements in
  convex and concave corners**". **[V]** on the talk's own slides; **[2nd]** on AIAA 2011-3539's
  contents, which I could not obtain — see Gaps.

### L5 — The published fix for a convex cusp is **shorten the march AND rotate the normal**. This repo tried the first alone and it got worse; that is now explained. **[V] on the rule; [I] on the diagnosis.**

Ye, Liu, Chen, Liu, Zheng, Pang & Chen, *Hybrid grid generation for viscous flow simulations in
complex geometries*, **Advances in Aerodynamics 2:17 (2020)**, open access — a survey plus their
own implementation, and the clearest published statement of the corner rules:

> "Most existing algorithms support **increasing marching distances slightly at concave corners
> and vice versa at convex corners** in order to smear concave and convex corners and facilitate
> the marching process." **[V]**

> "**wave-frontal motion may be more desirable than advective motion because it would smooth out
> convex or concave corners, whereas the advective motion would preserve them.** To implement the
> effect of a wave-frontal motion, a coefficient α can be added such that **the distances at the
> convex corners need to be shortened and the marching distances at the concave corners need to
> be lengthened**", with `h_i = α μ^(m−1) h_0`, `α = 1 + |cos β_i|` for β < 180° and
> `α = 1 − |cos β_i|` for β ≥ 180°. **[V]**

And separately, on the normals (their Eq. 1–2): "**it is beneficial to let normals at convex
corners be closer to their neighbours, and vice versa for concave corners**", implemented by a
weight `w_ij = k_ij²` at a convex point and `1/k_ij²` at a concave point. **[V]**

`jaxa-30p30n-reference-mesh.md` records that clamping the cusp displacement to 1.6 d took the
slat from 36 folds / 67× to 73 folds / 6397×. The published rule says the clamp is only half the
move: **the normals either side of the cusp must be pulled toward their neighbours at the same
time**, or shortening the march simply pinches the band where it is already thinnest — which is
exactly what that measurement reports. **[I]**

---

## 1. The cove, assembled

### 1a. BANC — the workshop where cove flow IS the subject — published no grids and no cove topology rule. It published two cove METRICS and disclaimed them. **[V]**

Choudhari & Lockard, *Assessment of Slat Noise Predictions for 30P30N High-Lift Configuration
from BANC-III Workshop* (NTRS 20160006011). This is the document `multi-element-airfoil-blocking.md`
§1 cites for the list of meshing techniques; these passages are new.

> "Given that a number of participants were starting with little to modest prior experience and
> that a sufficient knowledge base concerning the optimal grids required for the CFD methods of
> interest was not available, **computational grids for coordinated investigations were not
> provided ahead of the BANC-III Workshop. The only exceptions were that two sets of block
> structured grids were made available to interested participants. One set of grids was generated
> by JAXA** on the basis of their extensive experience with prior simulations of this type and
> involved two different meshes with nominally the same grid distribution, but with factor of 1.5
> difference between the respective cell sizes. The medium (i.e., level-1) grid was used by JAXA
> in their computations (Submission 11) and the fine (level 0) grid was used by the University of
> Manchester (Submission 12) and by ONERA (Submission 17)." **[V]**

Two things follow. First, **BANC is not a source of gridding guidelines** the way HiLiftPW is —
there is no BANC equivalent of the gridding-guidelines PDF. Second, **the nearest thing BANC has
to a committee grid for 30P30N is a JAXA block-structured mesh**, which is a different artefact
from the Pointwise hybrid mesh `jaxa-30p30n-reference-mesh.md` measures; I could not establish
any relation between them (Gaps).

On metrics, the paper is explicit that it is proposing, not prescribing:

> "For the slat noise problem, grid resolution within the regions of separated flow also becomes
> important for accurate predictions of noise producing flow structures. However, **due to the
> scale disparity in the structures from different parts of the flow field and insufficient
> knowledge of which metrics are most important for the slat cove aeroacoustics, no single grid
> metric for the separated regions would be sufficiently meaningful. For convenience, a small set
> of grid metrics is proposed in Table 2** and their values, wherever available, have been
> listed." **[V]**

The two cove metrics, from the paper's own Nomenclature: **[V]**

| symbol | definition |
|---|---|
| Δ_SL,C | planar grid spacing in slat cove **shear layer near the slat cusp** (mm) |
| Δ_SL,R | planar grid spacing in slat cove shear layer **near the reattachment location** (mm) |
| Δ_BL,S | representative boundary layer spacing over slat suction surface (mm) |
| n_TE,S | number of points across slat trailing edge |

Values actually reported in Table 2, on the 457.2 mm stowed chord (M = 0.17, Re_c = 1.71 × 10⁶,
all **[V]** from the paper):

| submission | Δ_SL,C / Δ_SL,R (mm) | in chords |
|---|---|---|
| 08 (TU Berlin) | 0.38 / 0.38 "(slat cove)" | 8.3e−4 |
| 10 | 0.17 / 0.17 | 3.7e−4 |
| 11 (JAXA, level-1) | 0.28 / 0.28 | 6.1e−4 |
| 12 (Manchester, JAXA level-0) | 0.19 | 4.2e−4 |

Submissions 13 and 14 (NASA Ames) report a range rather than a value, and their Table-2 column
alignment could not be resolved from the PDF's text layer, so they are omitted rather than
guessed. Rows 08, 10, 11 and 12 are unambiguous because enough neighbouring columns are filled
to anchor them. **[V]** on the four rows; the omission is deliberate.

**The cove's published resolution target is a SHEAR-LAYER spacing, not a wall band.** It is
measured along the free shear layer from the cusp to reattachment, and the same number is used at
both ends — i.e. the cove is asked for a *uniform* interior spacing, not a graded one. **[V]**
That is a different quantity from anything either existing note records, and it is the one number
a cove mesh in this repo could be held to. **[I]**

### 1b. In the overset practice the cove IS a named geometric feature with its own grids — and the published reason for splitting it is a double concave corner. **[V]**

Chan, *Overset Mesh Generation for the High-Lift Common Research Model* (NTRS 20170009859, AMS
Seminar, March 2017, the deck behind AIAA 2017-0362). Its surface-grid slide lists the wing's
features as "L.E., T.E., Root Intersection, Tip, **Slat Cove, Flap Cove, Cove Side Walls**" — 65
initial curves and 22 surface grids on the wing alone — and the flap-seal slide carries the rule
verbatim:

> "**Back and side wall cap split into two grids to avoid double concave corner => easier for
> hyperbolic volume mesh generation**" **[V]**

That is the field's own statement of P5 ("a concave pocket gets its own patch"), with a stated
*mechanism*: the split exists so that no single grid has to march out of two concavities at once.
**[V]** on the quote; **[I]** on tying it to P5.

LAVA/CGT's slat cove H-grid and its splaying boundaries are already in
`multi-element-airfoil-blocking.md` §1/§2; the new detail from the same paper (Housman, Stich &
Kiris, NTRS 20190030756) is that the cove grid is treated as a **specialized shear-layer grid**
for the turbulence model too — "a new Mode 4 (LES) is introduced in this work … This mode is
useful for **specialized shear layer grids such as the ones used in the slat cove region**".
**[V]** The cove grid is not just a filler; it is a zone with its own physics setting.

### 1c. What a hybrid/unstructured mesher does when a front cannot advance: it stops THAT NODE. **[V]**

Ye et al. 2020 again, §4.4–4.5, which is the closest published thing to the "front that stops at
a medial axis" that `jaxa-30p30n-reference-mesh.md` says this repo would need:

> "**Low-quality elements may be created in this step, in particular in the vicinity of concave
> corners.** … After creating a layer of elements, **we pick those elements whose quality values
> are below 0.1 for removal. Meanwhile, we stop propagating the front faces that carry those
> elements.**" **[V]**

Four stopping criteria, applied per front node: layer count reached; scaled aspect ratio ρ(p) < 0
(an inverted element); "**The new front faces starting from the front node are involved in global
intersections**"; and (3-D only) a neighbour has stopped. **[V]**

And the narrow-gap rule, which is the published answer to this repo's measured BL cap at the
main's aft tongue:

> Let `d_G` be the minimum distance from a front node to the opposing viscous wall and
> `l = Σ α μ^(m−1) h_0` the total layer height. "**If d_G > 2 l, no further modification is
> required** on the marching distance at p_i; otherwise, the height of the first viscous layer at
> p_i is computed by `h_0 = ε_1 · d_G / Σ μ^(m−1)`, where **ε_1 ∈ [0, 0.5] is a user parameter
> that determines how large the space is left for unstructured elements (less is more)**."
> **[V]**

So the published practice in a gap narrower than twice the layer height is **to rescale the first
cell locally and keep going**, never to refuse. `jaxa-30p30n-reference-mesh.md` records this
repo's mesher doing the opposite: "it builds at 0.0038 and refuses at 0.0042 with `Critical
proximity detected after retreat`". **[I]** on the comparison; **[V]** on the rule.

### 1d. Geometry modification is sanctioned, routine, and reported. **[V]**

Three independent primary instances, all new here:

- HYPGEN §2.4.1(4): when no smoothing parameters work, "The problem can sometimes be solved by
  modifying the surface grid through redistribution of points or refinement of difficult regions,
  e.g., **rounding a very sharp convex or concave corner**." **[V]**
- Lockard & Choudhari, *Noise Radiation From a Leading-Edge Slat*, AIAA 2009-3101 (NTRS
  20090020437), on 30P30N: "**all of the trailing edges (including the cusp or first edge of the
  slat) were artificially sharpened while preserving the camber of the respective sections.** …
  Sharpening the first edge on the slat has little effect on the cove shear layer because **the
  cusp is merely serving as a fixed separation point like the corner of a backward facing step**.
  … removing points around the edges allowed additional grid points to resolve the slat cove
  dynamics." **[V]**
- Zhang, Lin, Liu et al., *Comprehensive Study on the Slat Noise of 30P30N … Wall-Resolved LES*,
  arXiv 2411.05686 (2024), on the same geometry: "**Due to the JAXA modified 30P30N has a sharp
  slat cusp, a cut is made to reduce mesh quantity and improve mesh quality.**" **[V]**

**The field treats the hard corner as negotiable and the mesh as expensive.** That is the exact
inverse of this repo's posture, where the `.dat` outline is an input and the mesher must cope.
**[I]**

---

## 2. The trailing edges, assembled

### 2a. The complete published construction of a wake grid behind a blunt tail. **[V]**

Chuen & Chan (NTRS 20205002818), §III.A.2, the O-mesh wake grid, quoted with word spacing
restored:

> "At the trailing edge, **a line tangent to the trailing edge is defined from the center of the
> trailing edge to an endpoint with a distance of approximately 2.5 times the expected shear-layer
> thickness**. The point distribution exhibits a mix of uniform and stretched distributions to
> mimic the normal growth of the volume mesh with shear layer resolution. At the trailing edge,
> however, **a uniform spacing is used**. The C mesh in this region typically has wall normal
> spacing. For the O mesh wake grid, however, **a uniform spacing of Δs_wgt = 5 Δs_w provides
> comparable resolution for the region**. **A second curve at the far end of the wake-line is
> defined with a length of twice the hyperbolic marching distance and uniform spacing.** The two
> curves are combined to form a mesh using **transfinite interpolation**, and the spacing is
> redistributed like that of the C mesh. **An additional rectangular grid is added forward of the
> first curve to improve connectivity** between the O mesh and the wake grid." **[V]**

Five decisions this repo has had to make, each with a published answer: the band starts at the
**centre** of the blunt base, not at a corner; its direction is the **tangent at the trailing
edge**, not the chord and not the wall normal; its length is **2.5 × the shear-layer thickness**,
not a fraction of chord; its spacing **at the tail is uniform at 5× the wall spacing**, not the
wall spacing; and it is filled by **TFI between two curves**, the far one being twice the marching
distance long and uniform — which is what produces the outward fan. **[V]**

For the C variant, the same paper: the wake line's near-wall spacing is "the grid spacing at the
finite-thickness trailing edge" and the far-end spacing is Δs_max; "**variable normal spacing is
used in the wake. The points at the trailing edge start at viscous wall spacing, while the points
at the far end start with Δs_SL, with linear variation in between.** The grid at the trailing edge
grows normally, while the grid at the far end grows with constant spacing… The final grid exhibits
**a slight fanning** due to the constant spacing at the far end of the wake." **[V]**

### 2b. What O-versus-C is worth on a three-element section, measured. **[V]**

Same paper, Table 4 — the identical configuration meshed O and C, OVERFLOW/SA:

| | O mesh | C mesh | diff (×10⁴) |
|---|---|---|---|
| Total C_l | 3.22486 | 3.22499 | **1.23** |
| Total C_d | 0.04002 | 0.03960 | **−4.22** |
| Total C_m | −0.52188 | −0.52175 | 1.27 |

> "While solutions for airfoils computed solely with O or C meshes can differ by 5%, the results
> show that **the discrepancy between the two solutions can be reduced to a few counts with the
> addition of a wake grid**." (word spacing restored) **[V]**

`multi-element-airfoil-blocking.md` §6.5 already declines to over-read a 14 % mean
non-orthogonality gain bought with a fold, on the strength of Chan's 5 % NACA 0015 figure. **This
is a stronger version of the same point, on a three-element section**: with a wake band present,
the topology choice at the tail is worth about **four drag counts**. **[V]**

### 2c. How many points across the base, and whether it matters. **[V]**

- Chuen & Chan baseline `n_pT = 9`, swept over **3, 5, 9, 11, 17, 21**. Node count moves only
  222,625 → 241,173 across that whole sweep — "the grid growth is relatively mild, since only the
  resolutions at the trailing edge and one grid-spacing at the end of each curve connected to the
  trailing edge are changed". **[V]**
- The effect is not negligible: "**the resolution of the trailing edge affects the momentum of the
  immediate downstream element**"; refining it lowers lift and "causes the inflection point where
  the separation occurs on the flap to occur further upstream"; and in the Summary, trailing-edge
  resolution is named as one of the three parameters exhibiting "some of the largest variations in
  the solution". **[V]**
- Chan's HL-CRM deck gives the workshop-prescribed ladder as **5 / 9 / 13 / 17** points on the
  trailing edge for Coarse / Medium / Fine / Extra Fine. **[V]** (`multi-element-airfoil-blocking.md`
  §5 records HiLiftPW-1/-2's 4/6/9/14 and HLPW-4's 4/6/9/12/18/27 — Chan's 5/9/13/17 is a third
  ladder, from the HL-CRM campaign, and the three do not agree. Noted, not resolved.)

### 2d. Which tails are kept blunt, and who decides. **[V]**

- **Khorrami, Lockard et al.**, *Effects of Geometric Details on Slat Noise Generation and
  Propagation* (NTRS 20060013478), on a Boeing 777 section (NOT 30P30N): "we have taken the
  liberty of **making the main element and flap trailing edges sharp while maintaining their
  respective cambers. On the other hand, the finite thickness of the slat trailing edge was
  maintained for all of our simulations.**" **[V]**
- **JAXA's modified 30P30N went the other way**: Housman et al. record that fitting unsteady
  pressure transducers "**required increasing the thickness of the slat trailing edge**". **[V]**
  The Beihang LES measures that slat TE at **1.11 % of slat chord**, against **0.28 %** for the
  "real aircraft" scaling they also ran. **[V]**

So the rule in practice is: **keep the bluntness where its shedding is the quantity being
predicted, sharpen it everywhere else, and say which you did.** No source I read keeps a blunt
tail for mesh-quality reasons. **[I]**

**Against this repo's main tail.** `multi-element-airfoil-blocking.md` §3c already quotes Chan's
0.2 %-chord threshold. The main element's tail measured here is **9.3e−5 chord = 0.0093 % chord**,
a factor of 21 below that threshold, so the published recommendation for it is unambiguous: "it is
recommended that **the grid be continued aft of the trailing edge and the gap closed in the first
point in the wake**" — a deliberate degenerate cell. A wake band *with* a collapsed first point is
a different construction from the wake band that took this repo from 12 to 87 inverted cells.
**[I]** on the connection; **[V]** on the threshold.

---

## 3. Resolution standards: only what §5 of the other note lacks

`multi-element-airfoil-blocking.md` §5 already carries first-cell spacing, growth rate, surface
clustering, far field, block counts and the constant-spacing wake band for all four HiLiftPW
documents and the TMR. **New here:**

**A complete 2-D three-element parameter set, as actually used** (Chuen & Chan Table 2, HL-CRM 2-D
section, c_ref = 1 m, OVERFLOW/SA, "based on the current best-practices in an engineering setting,
which come from the medium mesh from prior Geometry and Mesh Generation Workshops"): **[V]**

| parameter | value |
|---|---|
| Δθ_L — max turning angle per spacing at the LE | **1.0°** (swept 0.125–2.0°) |
| n_pT — points on the trailing edge | **9** |
| stretching ratio | **1.2** |
| Δs_max — max spacing on the geometry surface | **3.0 % c_ref** |
| Δs_w — wall spacing | 4.323e−6 c_ref (for y⁺ ≈ 1) |
| Δs_SL — shear-layer spacing | **100 Δs_w** |
| Δs_wgt — wake-grid spacing at the blunt TE | **5 Δs_w** |
| h_SL — shear-layer band centre offset | ~0.028 c_ref |
| near-body topology | **O-mesh** |
| far field | **1000 c_ref** |
| near-body mesh outer-boundary distance | 0.089–0.6 c_ref |
| total node count | ~232,000 |

Three further rules from the same paper, each new: **[V]**

- **The LE spacing is set by turning angle, not by chord fraction**, deliberately: the 0.1 %-chord
  best practice "does not account for the local geometry and may not be sufficient for leading
  edges with extremely small radius of curvature". The slat's LE spacing is applied out to where
  "the radius of curvature of the leading edge curve drops below 30 % of the reference chord".
- **At a convex corner — explicitly "the corner that joins the lower surface of the main element
  and the cove" — the spacing on each leg is 0.5 % Δs_max**, i.e. 1/200 of the global maximum, a
  factor-200 local refinement at the cove's mouth.
- **Wake refinement block**: 0.25 Δs_max, sized so that "there are approximately **twenty points
  across thickness of the wake**"; a sweep of resolved-wake length over 1, 2, 5, 10, 20, 50, 100
  chords shows the solution insensitive "**after approximately 10 chords downstream**", with much
  the largest change between one and two chords.

**And the implementation of HiLiftPW's GR2 = 1.0 band, with numbers** (Chan, HL-CRM deck): for the
wing and flaps — not for the fuselage and slat — the wall-normal distribution has **four** regions:
"1. Uniform spacing first two cells (Δs_wall); 2. Stretched region; 3. **Shear layer region —
Uniform spacing = 100 × Δs_wall, Thickness = 3 in., Distance from wall = 1.5 in.**; 4. Stretched
region to outer boundary." **[V]** With Δs_ref = 3 % MAC and the HL-CRM's C_REF of 275.8 in, a
3-inch band is about 1.1 % of reference chord — compare the reference mesh's median ribbon depth of
1.5 % chord. **[I]**

**Grid quality checks that are automated, and what they check** (Chan, HL-CRM deck): "All volume
meshes are automatically checked for — **Positive Jacobians as computed by target flow solver
(OVERFLOW)**; **Self intersections with surface mesh**." **[V]** HYPGEN itself runs two checks per
grid: "a cell volume computation by tetrahedron decomposition" and "a Jacobian computation using
the same definition as that of the flow solver OVERFLOW. **If a cell passes the second test, it
will definitely run through the flow solver.** However, if a cell passes the second test but not
the first, it is probably distorted in some way". **[V]**

That second bullet is the direct answer to the defect `jaxa-30p30n-reference-mesh.md` found in
itself — "a band of one can run straight THROUGH a band of the other and still be reported as 0
inverted cells". **The published practice checks intersection against the SURFACE mesh as a
standing, automated gate**, and Ye et al. check global front intersection *during* generation.
Neither is a per-block quality report. **[I]**

**Two further 2-D block counts for `multi-element-airfoil-blocking.md` §5's table** — it says "I
found no published block count for a TWO-element 2-D section" and lists 26 / 33 / 7 / 5 for three
elements. Add: **[V]**

| system | geometry | blocks | points |
|---|---|---|---|
| Lockard & Choudhari, AIAA 2009-3101 (CFL3D) | 30P30N, 2-D planar | **77** | 563,741 |
| Khorrami et al., NTRS 20060013478 (CFL3D) | B777 section, 2-D | **24** (slat region only) | 1,318,000 |
| Chuen & Chan, NTRS 20205002818 (OVERFLOW) | HL-CRM 2-D, overset | 3 near-body O + 3 wake + forward + off-body | ~232,000 |
| Murayama et al., AIAA 2012-2844 (Gridgen) | Trap Wing, **3-D** point-matched | **441** | 12/37/124 M |

Lockard & Choudhari also state the one interface rule I found for a 2-D patched grid: "**Patched
interfaces were employed but restricted to regions away from the slat.**" **[V]**

---

## 4. A procedure, as one procedure

The only ordered recipe I found is NASA Ames', stated as such on Chan's slide "OVERSET STRUCTURED
GRID GENERATION PROCESS AND SCRIPTING FRAMEWORK". Verbatim main steps, then the parameterisation:
**[V]**

1. **Geometry processing.** Take CAD/STEP/IGES. Produce (a) an unstructured surface triangulation
   with "sufficient resolution at high curvature regions" and (b) **surface curves … CAD edges
   including all surface features**. Then "**Identify configuration characteristic lengths —
   component length scale, smallest feature size, gap size between components**" (the slide
   annotates this with "cusp / t.e. thickness", "chord", "gap size").
2. **Surface grid generation: feature-based domain decomposition, grid point distribution, mesh
   fill.** Features for the wing are "L.E., T.E., Root Intersection, Tip, Slat Cove, Flap Cove,
   Cove Side Walls" — 65 curves, 22 surface grids. Split a cap that would otherwise own a double
   concave corner.
3. **Volume grid generation: hyperbolic near-body, Cartesian off-body.** "One box grid around
   fuselage volume grids; **three staggered box grids around slat, wing, flaps**; large stretched
   box grid encloses all smaller box grids and goes to far field."
4. **Domain connectivity: grid point blanking, donor stencil search.**
5. **Input parameters preparation for flow solver**: boundary conditions, grid indices for
   component loads.

And the framework rule: "**Develop script that reproduces entire process** — Chimera Grid Tools
Script Library (Tcl-based, 200+ macros), component scripts (fuselage, slat, flaps, wing), master
script, **parameterized inputs**: max stretching ratio (surface and volume), surface grid spacing
(max interior, at surface features), volume grid wall normal spacing, **min number of points on
smallest feature**." **[V]**

Chuen & Chan's §III.A.1 is the 2-D instantiation of step 2–4, in order: discretise the blunt TE
uniformly with n_pT points → use that spacing as the end spacing for every curve meeting the TE →
divide the LE by max turning angle → set 0.5 % Δs_max at convex corners including the cove's mouth
→ stretched distribution elsewhere with the maximum spacing in the middle of each curve → march
hyperbolically from Δs_w until the normal spacing reaches Δs_max → insert the uniform shear-layer
band at h_SL → add the wake grid → embed in a uniform-Δs_max off-body Cartesian region → hole-cut
so the overlap falls at the midpoint of the shortest distance between two bodies, away from the
cove and away from high-gradient regions. **[V]**

---

## 5. What this repo would do differently tomorrow

Stated as inference, because none of the sources was written about this tool. **[I]** throughout;
the facts each rests on are **[V]** above.

1. **Stop treating "an offset self-intersects in the cove" as a property of coves.** It is the
   zero-smoothing limit of the marching every one of these systems uses. The cheapest experiment
   that would settle it here is to re-run the main element's second band with a Laplacian or
   angle-bisecting smoothing pass applied *per layer* and weighted by local grid-line convergence
   (HYPGEN's IMETH > 1), instead of `geometry_offset.offset_points` alone. The published switch is
   "detect converging grid lines, raise the dissipation there"; `largest_offset`'s 2e−5 refusal is
   the detector already — it just refuses instead of damping. (L1, §1c.)
2. **Reverse the sign of the corner correction.** The published wave-frontal rule is *lengthen* at
   concave, *shorten* at convex, with `α = 1 ± |cos β|` — and shortening at a convex cusp must be
   paired with pulling the two normals toward their neighbours. This repo clamped the convex
   displacement alone and measured it getting worse (36 → 73 folds). That is now a predicted
   outcome, not a mystery. (L5.)
3. **Make the narrow gap rescale rather than refuse.** `Critical proximity detected after retreat`
   at 0.0042 on the main's aft tongue is the one target `jaxa-30p30n-reference-mesh.md` says is
   not met. The published rule is: measure `d_G` to the opposing wall; if `d_G ≤ 2 l`, set
   `h_0 = ε_1 d_G / Σ μ^(m−1)` with `ε_1 ≤ 0.5` *at that node*, and keep going. Local rescaling,
   not a global cap and not a refusal. (§1c.)
4. **Add a between-body intersection gate, and run it during generation, not after.** The two
   independent published practices are Chan's automated "self intersections with surface mesh"
   check on every volume mesh, and Ye et al.'s per-node stop when "the new front faces … are
   involved in global intersections". This repo's bisection-against-a-crossing-check is the right
   idea arrived at from the defect; the field runs it as a standing gate. (§3.)
5. **Expect to put a wake band at the main's tail, and expect it to need the collapse.** The
   stated practice is a wake grid at *every* blunt tail, and the stated remedy below 0.2 % chord —
   which the main's 0.0093 % is far below — is to close the base at the first wake point. The
   repo's 87 inverted cells came from a band with no collapse, in a conforming topology where the
   band cannot simply overlap the flap. If the collapse is not acceptable in `MESH_MODE 1`, the
   reference's tail patch is a legitimate second answer — but it should be recorded as a
   *conformity workaround*, not as the field's rule, because it isn't. (L3, §2d.)
6. **Take the reference as a TOPOLOGY standard, not a resolution standard.** At the JAXA
   condition (c = 0.4572 m, M = 0.17, Re_c = 1.71 × 10⁶, all **[V]**), the reference's measured
   first cell of 1.07e−4 chord on the main gives, with a flat-plate c_f = 0.026/Re^(1/7) = 0.00335
   and u_τ/U = √(c_f/2) = 0.0409, **y⁺ = 1.07e−4 × 1.71e6 × 0.0409 ≈ 7**. That is not the y⁺ ≈ 1
   every workshop document asks for, and `jaxa-30p30n-reference-mesh.md`'s target 2 ("first cell at
   the wall ~1e−4 chord") therefore encodes one mesh's operating point rather than a standard. This
   repo's hybrid path already sits at 5.4e−5 → y⁺ ≈ 4. The arithmetic is mine and approximate; the
   conclusion — *do not treat the reference's spacings as a bar* — is not sensitive to it.
7. **Adopt the two sizing parameters this repo has no equivalent of.** (a) `Δs_SL` as a
   *multiple of the wall spacing* (100×) placed at an *offset* `h_SL`, which is HiLiftPW's GR2 = 1.0
   band expressed in two numbers a declared topology can carry on an edge; and (b) a **turning-angle**
   leading-edge spacing rather than a chord fraction. Both are per-edge spacing laws, which is
   exactly what `tools/PreProcessor/include/Spacing.hpp` and `.claude/rules/mesher-spacing.md`
   already own.
8. **Allow the geometry to be modified, and record it.** Every primary source here that met a hard
   corner modified it — sharpened a tail, cut a cusp, rounded a corner — and said so in the paper.
   This repo's `.dat` is an input the mesher must survive. A declared, recorded "sharpen this tail
   / round this corner" operation is both sanctioned practice and, on the evidence of §1d, cheaper
   than every alternative. (§1d.)

---

## 6. Where a source contradicts this repo's existing notes

1. **"The ribbon cannot pass through a cove" is too strong.** `jaxa-30p30n-reference-mesh.md`
   derives it from `largest_offset`'s 2e−5 cap and states it as a general rule (P5's derivation).
   Chuen & Chan's slat O-mesh marches straight through the cove with "the spacing close to the wall
   largely unaffected"; HYPGEN documents how. The rule is true of offsets, not of coves. **[V]**
2. **"The main gets a patch, the flap gets wake bands" is one mesh, not a practice.** NASA Ames'
   2-D best-practice adds "a wake grid … to **each** O mesh". **[V]**
3. **"None of [the four gridding guidelines] mentions block topology" is very slightly off.**
   HiLiftPW-1 §(d) and HiLiftPW-2 §(f) both say "Grid convergence cases must maintain the same
   grid family between grid levels, i.e. maintain the same stretching factors, **same topology**,
   etc." That is a *constancy across refinement* requirement, not a prescription of which topology
   — so `multi-element-airfoil-blocking.md` §4's conclusion stands, but its "none of them mentions"
   should read "none of them prescribes". HiLiftPW-3 and HLPW-4 contain the string zero times.
   **[V]**
4. **The cove's published resolution target is not a depth.** Both existing notes reason about the
   cove in terms of how deep a structured band reaches. BANC's two cove metrics are spacings
   *along the shear layer*, at the cusp and at reattachment, and they are the same number at both.
   Nothing in BANC asks for a wall band in the cove at all. **[V]**
5. **A third trailing-edge point ladder exists.** `multi-element-airfoil-blocking.md` §5 records
   HiLiftPW-1/-2's 4/6/9/14 and HLPW-4's 4/6/9/12/18/27. Chan's HL-CRM deck states the
   "workshop prescribed" ladder as **5/9/13/17**. Three ladders, not reconciled here. **[V]**
6. **Not a contradiction but a correction of emphasis**: `multi-element-airfoil-blocking.md` §L1
   reads Liou & Liu and LAVA as agreeing that the cove gets its own zone. They do — and the two
   systems that do it are both *aeroacoustic*. The two systems here that do not (Chuen & Chan,
   and the slat O-mesh generally) are both *force-prediction*. The split follows the question being
   asked, not the geometry. **[I]**

---

## Gaps I could not close, by name

1. **AIAA 2017-0362** (Chan, *Best Practices on Overset Structured Mesh Generation for the
   High-Lift CRM Geometry*) — the paper behind the HL-CRM deck I did read. Not on NTRS and not
   located in open access; everything I quote from that campaign is from the seminar slides
   (NTRS 20170009859), which are terse by nature.
2. **Ito et al., AIAA 2011-3539** — the defining paper for the **suppressed marching direction
   method**, i.e. JAXA's own published answer to concave corners, and the single most on-point
   missing document for this repo's cove problem. I have it only through Murayama's slide and a
   secondhand description; the JAXA repository copy (`jaxa.repo.nii.ac.jp/record/22356/files/
   PA2012074.pdf`) returned **HTTP 502** on every attempt. Marked **[2nd]** throughout.
3. **The BANC-III JAXA block-structured grids.** The assessment says two JAXA grid levels were
   distributed to participants; I found no description of their topology, no download location,
   and **no evidence either way that they are related to the Pointwise project
   `jaxa-30p30n-reference-mesh.md` measures**. Whether this repo's reference mesh *is* the BANC
   artefact, a descendant of it, or unrelated, I cannot say.
4. **No BANC gridding-guidelines document exists, as far as I can tell.** I searched for a BANC
   analogue of HiLiftPW's gridding guidelines and found none; the assessment paper's own statement
   that grids "were not provided" is consistent with that, but absence of a document is weaker
   evidence than its text would be.
5. **Ito & Nakahashi, IJNMF 45(1) 2004** and **Nakahashi, Ito & Togashi, IJNMF 43(6–7) 2003** —
   MEGG3D's defining papers, cited on JAXA's own slide. Paywalled (Wiley); not read.
6. **Tam & Armstrong, "2D finite element mesh generation by medial axis subdivision"**, *Advances
   in Engineering Software* 13 (1991) — the primary source for medial-axis block decomposition,
   which is the named technique closest to "a front that stops at a medial axis". Paywalled
   (Elsevier); not read. I did read **US patent 10,956,625 B2** (Siemens Industry Software,
   Makem & Mukherjee, filed 2015-09-01, granted 2021-03-23), which names medial-axis, Cartesian
   slabbing and Art Gallery decomposition and states "**Concavities may be identified by the vertex
   included angle θ … When θ about equals 270° or more this will identify a concavity at a vertex
   which will be removed**" — a commercial blocker's concavity rule, but a general FEA one, not
   aerodynamic. **[V]** on the patent; its relevance here is **[I]**.
7. **DLR.** I found DLR's hybrid high-lift practice only through other people's grid inventories
   (Solar/CENTAUR, prism layers) and through BANC-III submission 18's one-line description. No DLR
   technical report documenting its cove gridding was located. The brief asked for one by name;
   I could not supply it.
8. **I did not open the LAVA 2-D grids** hosted on the TMR, which
   `multi-element-airfoil-blocking.md` gap 2 also leaves open; the slat-cove H-grid's actual shape
   is still described rather than measured.
9. **Nothing here is measured in this repo.** No mesh was generated and no quality figure
   re-derived. The 12 → 87 inverted cells, the 9.3e−5 tail, the 1.07e−4 first cell, the 36 → 73
   fold count and the 0.0038 BL cap are quoted from the brief and from
   `jaxa-30p30n-reference-mesh.md`, not reproduced. The one piece of arithmetic I performed is the
   y⁺ ≈ 7 estimate in §5.6, and it is flagged as an estimate.

---

## Sources

Primary, read by me:

- Chuen & Chan, ***Mesh Effects on Flow Solutions for a 2-D Multi-Element Airfoil Using Structured
  Overset Methods***, NASA Ames (NTRS 20205002818), §III, §IV, §V, §VII.
  `https://ntrs.nasa.gov/api/citations/20205002818/downloads/Mesh_Effects_on_Overset_Flow_Solutions_Final-19.pdf`
- Chan, ***Overset Mesh Generation for the High-Lift Common Research Model***, AMS Seminar Series,
  9 March 2017 (NTRS 20170009859), slides 5–16.
  `https://ntrs.nasa.gov/api/citations/20170009859/downloads/20170009859.pdf`
- Chan, Chiu & Buning, ***User's Manual for the HYPGEN Hyperbolic Grid Generator and the HGUI
  Graphical User Interface***, NASA TM-108791 (NTRS 19940011311), §2.3.4, §2.3.5, §2.4.1, §2.4.2.
  `https://ntrs.nasa.gov/api/citations/19940011311/downloads/19940011311.pdf`
- Choudhari & Lockard, ***Assessment of Slat Noise Predictions for 30P30N High-Lift Configuration
  from BANC-III Workshop*** (NTRS 20160006011), Nomenclature, §II, §III and Table 2.
  `https://ntrs.nasa.gov/api/citations/20160006011/downloads/20160006011.pdf`
- Lockard & Choudhari, ***Noise Radiation From a Leading-Edge Slat***, AIAA 2009-3101
  (NTRS 20090020437), §II.A.
  `https://ntrs.nasa.gov/api/citations/20090020437/downloads/20090020437.pdf`
- Khorrami, Lockard et al., ***Effects of Geometric Details on Slat Noise Generation and
  Propagation*** (NTRS 20060013478), §2.3.
  `https://ntrs.nasa.gov/api/citations/20060013478/downloads/20060013478.pdf`
- Housman, Stich & Kiris, ***Predictions of Slat Noise from the 30P30N at High Angles of Attack
  using Zonal Hybrid RANS-LES*** (BANC-V, NTRS 20190030756), §III and §IV.A.
  `https://ntrs.nasa.gov/api/citations/20190030756/downloads/20190030756.pdf`
- Murayama, Ito, Tanaka & Yamamoto, ***Computational Studies of the NASA High-Lift Trap Wing Using
  Structured and Unstructured Grid Solvers***, AIAA 2012-2844 — HiLiftPW-1 participant talk,
  slides 6, 10–14. `https://web.archive.org/web/2016id_/http://hiliftpw.larc.nasa.gov/Workshop1/
  ParticipantTalks/SS2012/2-Murayama-hilift.pdf`
- Ye, Liu, Chen, Liu, Zheng, Pang & Chen, ***Hybrid grid generation for viscous flow simulations in
  complex geometries***, **Advances in Aerodynamics 2:17 (2020)**, open access, §2.2, §4.2–4.5.
  `https://aia.springeropen.com/counter/pdf/10.1186/s42774-020-00042-x.pdf`
- Wissink, ***An Overset Dual-Mesh Solver for Computational Fluid Dynamics***, ICCFD7-1206 (2012),
  abstract and §2. `https://www.iccfd.org/iccfd7/assets/pdf/papers/ICCFD7-1206_paper.pdf`
- Zhang, Lin, Liu, Liu & Liu, ***Comprehensive Study on the Slat Noise of 30P30N High-Lift Airfoil
  Based on High-Order Wall-Resolved Large-Eddy Simulation***, arXiv:2411.05686, §III.B.
  `https://arxiv.org/pdf/2411.05686`
- **AIAA CFD High Lift Prediction Workshop gridding guidelines**, all four, re-read here only to
  count `cove`/`cavity`/`concave`/`block`/`topolog`; URLs as listed in
  `docs/research/multi-element-airfoil-blocking.md`.
- **US Patent 10,956,625 B2**, *Mesh generation system and method*, Siemens Industry Software Inc.,
  Makem & Mukherjee. `https://patents.google.com/patent/US10956625B2/en`

Cited but not read in full:

- Chan, *Best Practices on Overset Structured Mesh Generation for the High-Lift CRM Geometry*,
  **AIAA 2017-0362** — not located in open access.
- Ito et al., **AIAA 2011-3539** (the suppressed marching direction method) — not located; the
  JAXA repository copy returned HTTP 502.
- Ito & Nakahashi, **IJNMF 45(1) 79–108 (2004)**; Nakahashi, Ito & Togashi, **IJNMF 43(6–7)
  769–783 (2003)** — paywalled.
- Tam & Armstrong, *2D finite element mesh generation by medial axis subdivision*, **Advances in
  Engineering Software 13 (1991)** — paywalled.

In this repo:

- `docs/research/multi-element-airfoil-blocking.md` — what the field does about topology families,
  the slot, block corners, the outer boundary, the wake cut and interfaces; §0 above says what it
  already answers and §6 lists where this note corrects it.
- `docs/research/jaxa-30p30n-reference-mesh.md` — the one reference mesh taken apart by
  measurement; P1–P6 and O1–O5, and the measurements §5 above reasons against.
- `.claude/rules/mesher-multiblock.md`, `.claude/rules/mesher-spacing.md`,
  `.claude/rules/mesher-quality.md`, `.claude/rules/mesher-smoothing.md` — the rules this note
  bears on. **Nothing in them was changed.**
