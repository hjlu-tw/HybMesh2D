# Cell-size dynamic range inside one block

**A RESEARCH NOTE, like the three beside it.** Not `.claude/rules/*.md` (what the rule is), not
`docs/design_notes/` (why a shipped rule was chosen). It records what an outside literature
check and a fresh measurement say about a question this repo is currently deciding by feel, so
the decision can be argued from sources rather than from a table of my own numbers. Nothing
here is binding; no rule, gate, test or source file was changed to write it. 2026-10-20.

**Subject.** A week of measurements on a NACA 4412 found that the per-block ratio
`max cell area / min cell area` falls from 1,291,495x (4-block C-grid, median block) to 8.4x
(6 offset rings x 14 columns, median block) as the blocking is subdivided, while mean
non-orthogonality stays in the 3–9 degree band. The residual bad blocks are the leading-edge
columns of the OUTERMOST ring, where the body's 0.004 surface clustering is 1/40 of that
edge's own mean spacing. Three fixes were tried; each broke something else, and the one that
looked right — making the clustering a property of the radial STATION rather than of the edge
— is refused by this mesher, because an edge distribution here is one of `uniform` /
`geometric` / `tanh` and a `tanh` edge takes one first-cell height, not one per end.

The questions this note answers: is within-block size RANGE a metric anyone uses; how do
production generators let an edge's distribution be set; what GridPro specifically does; what
the field uses INSTEAD of blocking; and whether anyone states a block count for a 2-D
single-element C-grid.

## How to read the markers

- **[V]** verified in a primary source I read myself (source code, official docs, standards
  text, or the paper), or measured by me.
- **[I]** my own inference from a **[V]** fact. Stated as reasoning, not as fact.
- **[2nd]** I could only find this secondhand. Treat as unconfirmed.

A note on the Pointwise citations: `cadence.com` and `pointwise.com` both answer **HTTP 403**
to a non-browser request today. Every Pointwise page quoted below I read in the Internet
Archive's capture of the official manual (snapshot `20231202`, Fidelity Pointwise V18.x,
"© 2021 Cadence Design Systems"). It is the vendor's own text, not a summary of it, so I mark
it **[V]**; it is an archived copy, and that is stated rather than hidden.

---

## Lead: the five answers a reader needs first

### L1 — Nobody measures cell-size range within a block. The field's size metric is the ratio between NEIGHBOURS, in every vocabulary I read. **[V]**

Three vocabularies, read end to end:

- **Fidelity Pointwise's Examine** ships **37** diagnostic functions. Every one that concerns
  size is either per-cell (Area, Volume, Edge Length, Length I/J/K, Aspect Ratio, X/Y/Z-ish
  extents) or a ratio **to an adjacent cell** (Area and Volume Ratio, Length Ratio I/J/K,
  Smoothness I/J/K, Expansion Ratio (Fidelity), Volume Ratio (Fidelity), Donor Volume Ratio,
  Vertex-Centered Expansion Factor). There is **no** function whose value is a property of a
  domain or block as a whole. **[V]**
- **ANSYS ICEM CFD's Pre-Mesh Quality** ships **39** criteria. The only ones that compare
  sizes are `Max Ratio` ("the maximum ratio of the lengths of any two edges that are adjacent
  to a vertex **in an element**"), `Volume Change` ("finding the maximum volume of **all its
  neighboring elements** and dividing it by the volume of the element itself"), `Opp Face Area
  Ratio`, and `Aspect Ratio` (per element). Same shape: per-element, or element-versus-neighbour.
  **[V]**
- **CGNS** has **no mesh-quality vocabulary at all.** Reading the SIDS chapters, the word
  "quality" appears once, in the Introduction, about the quality of *archived data*; "skew"
  appears once, in a caveat about computing interpolants on skewed cells. There is no quality
  metric, no aspect ratio, no volume ratio, nothing. **[V]** (This closes a gap the
  offset-ring note left open by guess: it recorded CGNS as "the wrong candidate, a file format
  with no position on how a grid is generated". That guess was right, and is now checked.)

And the vendor says, in as many words, what the ratio is FOR. Both Pointwise ratio functions
carry the same tip: "The Volume Ratio and Area Ratio functions are excellent diagnostics for
finding **cell size discontinuities at block and domain interfaces**." **[V]** The question
the field asks about cell size is *does it jump where two blocks meet*, not *how far does it
travel inside one*.

**The nearest thing to a size-range metric that exists is Sandia's Verdict library**, and it
is not a range: `quad_relative_size_squared(num_nodes, coordinates, average_quad_area)` —
"Min( J, 1/J ), where J is determinant of weighted Jacobian matrix" — compares one quad's area
with an **average** area the caller supplies. **[V]** **[I]** The scope of that average is the
caller's choice, so a per-block relative size is expressible in the field's existing vocabulary
with no new idea; what nobody ships is the max/min RANGE as a criterion.

### L2 — The reference grid for this exact geometry class is ONE block with a measured area range of 3.4e12, and that grid is the community's yardstick. **[V], measured by me**

NASA's Turbulence Modeling Resource publishes the 2-D NACA 0012 validation grids as a family
of five nested C-grids, "the topology is a so-called 'C-grid' … the grid connects to itself in
a 1-to-1 fashion in the wake", far field ~500 chords, finest 1793x513 with wall spacing
4e-7 c. The PLOT3D header of every one of them reads `nbl = 1`. **[V]**

I downloaded two levels and measured the quantity this repo has been tracking:

| TMR grid | blocks | cells | max area / min area | max ADJACENT area ratio (i / j) |
|---|---|---|---|---|
| `n0012_113-33.p2dfmt` | 1 | 3,584 | **1.379e12** | 3.838 / 4.067 |
| `n0012_225-65.p2dfmt` | 1 | 14,336 | **3.424e12** | 2.635 / 2.838 |

**[V]** (my measurement; script logic is the shoelace area per structured cell, then the max
over i-neighbours and j-neighbours separately).

Set beside the brief's own table, the 225x65 reference grid is **2.6 million times worse** than
this repo's worst C-grid block (3.424e12 against 1,312,567) on the within-block range — and it
is the grid that the entire RANS turbulence-modelling literature calibrates against. Whatever
the repo's 1.3e6 is evidence of, it is not evidence of a mesh the field would reject.

**[I] Why the number is structurally uninformative.** In a transfinite block the cell area is
approximately the product of the two directions' local spacings, so the block's area range is
approximately the PRODUCT of its two edge distributions' own ranges. A single block that holds
both an 8e-6 wall step and a 500-chord outer boundary cannot have a range below about 1e12
no matter how good it is. The within-block range therefore measures **how much of the domain
one block spans** — a property of the topology — far more than it measures mesh fitness. That
is exactly what the brief's table shows: the number tracks the block count, and the
non-orthogonality column, which is a genuine quality measure, does not follow it (6.11 deg at
48 blocks is better than 9.32 at 24 and worse than 3.05 at 84).

The second column is the one the field bounds, and the reference grid is bounded on it: 2.6–4.1
at these coarse levels, falling with refinement. The repo's existing note
`multi-element-airfoil-blocking.md` §5 already collects the published bounds on that quantity
(HiLiftPW "GR1 < 1.25 for all grids", HLPW-4's 1.25/1.16/1.10/1.07/1.05/1.03 by level, Chan's
"1.2 for surface grids and 1.3 for volume grids") — not repeated here.

### L3 — The expressiveness gap is real, it is this repo's actual defect, and every production generator but Gmsh closes it four different ways. **[V]**

| capability | ICEM CFD | Pointwise | HYPGEN | Gmsh | this repo |
|---|---|---|---|---|---|
| explicit node list / parameters on an edge | **yes** (`FromGraphs`, `FromEdgeSplits`, `OnScreen`) | stored, not settable (`General`) | **yes** (`IZSTRT = -1`) | no | no |
| distribution copied FROM another edge | **yes** (`Copy Parameters > From Edge`, `ReferenceMesh`) | **yes** (`pw::DistributionGeneral create <subcons>`) | n/a | no | no |
| spacings MATCHED at a shared vertex | **yes** (`Match Edges`, incl. `Automatic` min/max/average) | **yes** (`SpacingSync` mode) | n/a | no | no |
| two DIFFERENT end spacings on one edge | **yes** (`Spacing1`+`Spacing2`, `Hyperbolic`/`BiGeometric`) | **yes** (`Tanh` with both ends constrained) | **yes** (`DZ0`, `DZ1`) | no | **no** |

The last row is the one that matters most here, because the brief records the mesher
*refusing* it as if it were a law of the subject: "a tanh edge cannot take a different
first-cell height at each end". In this repo it is a written rule —
`.claude/rules/mesher-multiblock.md:378` lists among the things "**Refused BY NAME, never
half-honoured**" exactly "**two DIFFERENT heights at the two ends** (equal ones are accepted,
so the refusal is about the difference)" — and it is true of the implementation, since
`Spacing.hpp` offers `solveTanhDelta` (clusters BOTH ends equally) and `solveTanhStartDelta`
(clusters the START only), and nothing in between. **[V]** It is not true of the law. ICEM's
`Hyperbolic` law is documented as "You can set Spacing1 and Spacing2, and the growth ratios are
determined internally" **[V]**; Pointwise's `Tanh` is the two-sided Vinokur-style function and
falls back to a *different*, one-sided function only "if the spacing is unconstrained at only
one end" **[V]**. The asymmetric two-ended tanh is the industry DEFAULT, not an exotic request.

### L4 — Where the blocking does carry the transition, it has published names, and they are topological operations rather than distributions. **[V]**

- **GridPro** refines by adding blocks: `nest` "helps in refining the grid by creating more
  blocks near the geometry **without affecting the far field**"; `reverse_nest` "will reduce
  the number of blocks and thereby reducing the cell count" in the far field; "compact
  enrichment" (`Enrich`) refines "near the geometry which will not affect the far field".
  **[V]** Eiseman's own paper names the 2-D aerofoil structures: loops of blocks around the
  leading and trailing edge, "We often call such loop structures 'clamps' or as in the case of
  the trailing edge structure 'a collar'." **[V]**
- **CFL3D** — a production NASA structured solver — ships a single-element NACA 0012 example
  on a **seven-zone patched grid**, with the rationale stated in the manual: "An advantage of
  using patched grids is that **finer grids can be placed in high gradient regions while
  relatively coarser grids can be placed elsewhere**". Its interfaces do not have to match
  point for point: `ninter` is the "patched-grid flag (zonal interface along a common surface
  **where points need not match**)". **[V]**

### L5 — Nobody states a block-count rule of thumb for a 2-D single-element aerofoil. The published counts span 1 to "ten thousand", and they are set by what the topology must express. **[V] on each count; [I] on the absence**

| source | geometry | blocks |
|---|---|---|
| NASA TMR NACA 0012 validation grids | 1 element, C-grid | **1** (`nbl = 1`) **[V]** |
| CFL3D §9.1.3 example | 1 element, patched | **7 zones**, 4,949 points **[V]** |
| GridPro (Eiseman 1995) | arbitrary | "The count can go to a thousand, ten thousand, or more" **[V]** |
| Kim, Alonso & Jameson (via this repo's own blocking note) | 3 elements, conforming C | 26 **[V]** |

I searched for a stated rule ("a single-element C-grid should have N blocks") in the Pointwise
and ICEM manuals, the HYPGEN manual, Eiseman's paper, the GridPro FAQ, and the TMR pages, and
found none. **[I]** The reason is visible in the spread above: in the point-matched world the
count is decided by what the topology has to express (one C-wrap needs one block; placing a
fine zone where a shock sits needs seven), and in the GridPro world the count is not a user
input at all. A rule of thumb would have to be about the geometry, and nobody writes one.

---

## 1. The metric question, in full

### 1a. Pointwise Examine — the complete function list, and what it rules on

The Examine menu's Functions page lists, verbatim: Cell Type; Jacobian; Volume; Component
Volume; Donor Volume Ratio; Donor Edge Length Ratio; Area; Edge Length; Length I, J, or K;
Area and Volume Ratio; Length Ratio I, J, or K; Aspect Ratio; Smoothness I, J, or K; Minimum
Included Angle; Maximum Included Angle; Equiangle Skewness; Equiarea, Equivolume Skewness;
Centroid Skewness; Warp; Cell Non-Orthogonality; Wall Spacing; Wall Orthogonality;
Intersection; Equi-Angular Skewness (Fidelity); Expansion Ratio (Fidelity); Volume Ratio
(Fidelity); Database Associativity; DB, Relative DB Deviation; Assemble Tolerance; Boundary
Proximity; Surface Proximity; U,V; Size Field; Size Field Gradient; Vertex-Centered
Orthogonality; Vertex-Centered Expansion Factor; Vertex-Centered Volume. **[V]**

The three size-ratio definitions, verbatim:

```
Area and Volume Ratio:   max [ Size_i / minSize_j , maxSize_j / Size_i ]
    Size_i    = Area or volume of the cell i
    minSize_j = Minimum area or volume of the adjacent cell j
    maxSize_j = Maximum area or volume of the adjacent cell j

Volume Ratio (Fidelity): ACVR_j = max [ V_i / V_j , V_j / V_i ] ;  ACVR = max_j [ ACVR_j ]

Expansion Ratio (Fidelity): ER_i,j = max [ D_i,f / D_j,f , D_j,f / D_i,f ] ;  ER_i = max_j
    D_i,f = distance between the centroid of the shared face f and the centroid of the
            opposite face of cell i      (hex)   / of the volume cell i   (non-hex)
```

**[V]** `Length Ratio I, J, or K` is the same idea one dimension down: "the ratio between the
distance from the current IJK coordinate to the index+1 point and the distance from the current
IJK to the index-1 point … The larger of the two distances is always divided into the smaller,
so all values range between 0 and 1." **[V]** `Smoothness I, J, or K` is not a size measure at
all — it is the normalized turning angle through three consecutive points. **[V]**

**[I] The range IS computable in Pointwise, and nobody named it.** `pw::Examine` returns
`getMinimum` / `getMaximum` / `getAverage` over the entities added to the examine object, so
`domainArea` on a single domain plus a division gives exactly the brief's metric in two lines
of Glyph. The tool's authors made the pieces available and shipped no criterion built from
them; Pointwise's proactive quality mechanism, `Examine > Rules`, is described as letting you
"create new rules for quality criteria pertaining to **your specific CAE solver**" — i.e. the
threshold set is the solver's, not the mesher's. **[V]**

### 1b. ICEM CFD — the same answer, with a per-block histogram as the user-facing form

The 39 criteria, verbatim from Pre-Mesh Quality Options: Angle; Aspect Ratio; Constant Radius;
Custom Quality; Determinant (2x2x2 stencil); Determinant (3x3x3 stencil); Distortion; Equiangle
Skewness; Eriksson Skewness; Ford; Hex. Face Aspect Ratio; Hex. Face Distortion; Max Angle; Max
Dihedral Angle; Max Length; Max Ortho; Max Ortho 4.3v; Max Ratio; Max Sector Volume; Max Side;
Max Warp; Max Warp 4.3v; Mid Node; Mid Node Angle; Min Angle; Min Ortho; Min Sector Volume; Min
Side; Opp Face Area Ratio; Opp. Face Parallelism; Orientation; Quality; Taper; Volume; Volume
Change; Warpage; X Size; Y Size; Z Size. **[V]**

`Volume Change` is the closest relative of the brief's metric and is still a neighbour ratio:
"calculated for a specific element by finding the maximum volume of all its neighboring
elements and dividing it by the volume of the element itself. The default range is 0–20". **[V]**

**[I]** What an ICEM user actually looks at is a HISTOGRAM of a per-element criterion over a
selected set of blocks, with a default display range (0–20 for the ratios, 1–20 for aspect
ratio). That is a per-block *distribution* of a per-element metric, which is a different
object from a per-block scalar, and it is the closest the two commercial tools come to the
brief's question.

### 1c. AIAA / NASA guidance

I did not find a published guideline bounding within-block size range, and I looked in the
places where such a bound would live. The workshop gridding guidelines bound the quantities
this repo's own `multi-element-airfoil-blocking.md` §5 already quotes — first-cell spacing by
`y+`, viscous-layer growth rate `GR1 < 1.25` and its per-level refinement, a constant-spacing
band at the wall, surface clustering as a fraction of local chord, far-field distance — and
nothing about the size spread inside a zone. **[V] that those are the bounds they state;
[I] on the absence, since both workshop sites (`aiaa-dpw.larc.nasa.gov`,
`hiliftpw.larc.nasa.gov`) now redirect to a NASA landing page and I re-read the guidelines only
through the quotations already verified in that note, not from the originals this week.**

---

## 2. How production generators let a distribution be set

### 2a. ICEM CFD — fifteen laws, three explicit mechanisms, and four ways to not state one

The predefined `Mesh law` list, verbatim: Bi-Geometric (default), Bi-Exponential, Curvature,
Exponential 1, Exponential 2, FullCosinus, Geometric 1, Geometric 2, HalfCosinus1,
HalfCosinus2, Hyperbolic, Linear, Poisson, Spline, Uniform. **[V]**

Beyond them, "there are several interactive or **user-defined** Mesh laws": **[V]**

- **`FromGraphs`** — "Opens the Relative Point Density vs Edge Distance DEZ where you can
  graphically create a bunching law… **File allows you to save or recall a distribution
  function.** … Control points may be moved (click and drag), added (click) or removed
  (double-click)." A saved distribution function is a file, i.e. an explicit, reusable,
  non-parametric distribution. **[V]**
- **`FromEdgeSplits`** — "Use this law to **seed the bunching using edge splits** … The number
  of nodes equal the number of splits + 2." The node positions are the split positions. **[V]**
- **`OnScreen`** — "manually adjust node placement by dragging along the selected edge". **[V]**
- **`ReferenceMesh`** — "The node spacing is **derived from an existing mesh edge
  distribution** … Nodes Locked is enabled when this law is applied." **[V]**

And four propagation mechanisms, which is the half of the problem this repo hit when scaling
clustering by each edge's own length broke the match at the shared radial: **[V]**

- `Copy Parameters > From Edge`: "copy a node distribution from another edge to the selected
  edge", with `Reverse` and `Copy Absolute` ("the exact spacing from one edge will be copied to
  the specified edges, **regardless of edge length**" — i.e. relative-by-default, absolute on
  request; by default "the bunching parameters of the parallel edges are based upon the
  relative lengths of the selected edge and destination edges").
- `Copy bunching > All Parallel Edges`: parallel means "edges that start and end with the same
  index value".
- `Linked bunching`: "allows the distribution of nodes on a single edge to be identical to the
  distribution of nodes on a series of smaller, parallel edges… a permanent relationship,
  called links".
- `Match Edges`: "allows you to match the edge spacing of a reference edge to a connecting
  target edge… **Matching is done around a connected node** … a quick way to ease edge bunching
  size transitions between connected edges and adjacent blocks", with `Link spacing` (the match
  persists) and `Automatic`, which at a selected VERTEX picks the reference as the edge with
  `Minimum` spacing, `Maximum` spacing, or the `Average` of the spacings there.

**[I] `Match Edges / Automatic / Average` is the published form of the repo's rejected fix.**
The brief's third attempt — "making it a property of the radial station" — is, in ICEM's
vocabulary, choosing the end spacing at a vertex once and matching every edge that meets there
to it. It is not refused in ICEM; it is a named button with three tie-break policies. The piece
this repo lacks is not the idea but the two-ended law the matched spacings would be written
into (L3's last row).

### 2b. Pointwise — a general distribution exists, is not authorable by hand, and IS copyable by script

The Functions tab lists seven distribution function types: **Tanh** (default; "If the spacing
is unconstrained at both ends, grid points will be distributed uniformly… If the spacing is
unconstrained at only one end, an alternative one-sided hyperbolic tangent distribution
function is used"), **MRQS** ("Monotonic Rational Quadratic Spline… It forces a grid point to
be fixed to a break point"), **Geometric**, **Growth** (geometric on the T-Rex portion, tanh on
the rest), **Shape** (deviation + turning-angle driven), **Automatic** (a size field)
and **General**, plus an `Equal` shortcut that unconstrains both ends and sets the function to
Tanh. **[V]**

The `General` entry is the direct answer to the brief's question, and the answer is "the state
exists, the authoring does not": **[V]**

> "**General**: A general distribution results from other operations and **cannot be set
> explicitly on any connector or subconnector**. General distributions represent **discrete
> point locations stored rather than points being located along a connector by a formula**.
> These distributions will result from, for example, connectors being projected onto database
> surface entities or from connectors imported from a nonnative file format, such as Plot3D.
> This radio button choice is shown only for reference to indicate when such a distribution
> exists on a selected subconnector."

In Glyph it *is* constructible, from other connectors: `pw::DistributionGeneral create
subcon_list` — "creates a new general distribution function object **from a list of
subconnectors** … The direction of the chain of subconnectors can be specified by using either
the word 'Forward' or the word 'Reverse'". **[V]** So Pointwise supports copy-from-edge, not
author-from-array. There is also a whole application mode for the matching half:
`pw::Application begin SpacingSync` (`pw::SpacingSynchronizer`). **[V]** Spacing constraints
themselves are objects (`pw::SpacingExplicit`, whose `Value` is "the explicit value for this
spacing object. A value of 0 is a special value that means that the spacing is **not
constrained**") — i.e. per-END, not per-node. **[V]**

A detail worth keeping: opening an older project file prompts "whether to preserve the grid
points **locations** or their **distribution function** … in case the software cannot compute a
distribution that matches exactly the grid points locations". **[V]** **[I]** The two
representations are not interchangeable even inside the tool that owns both, and the vendor
treats "which one is authoritative" as a question only the user can answer — the same question
this repo would face the day it stored node arrays beside laws.

### 2c. Gmsh — the one that genuinely cannot, with a documented escape through the API

The manual's syntax line is `Transfinite Curve { … } = <expr> < Using Progression | Bump
<expr> >;` **[V]** The API header is one law wider and no more: "Currently supported types are
`Progression` (geometrical progression with power `coef`), `Bump` (refinement toward both
extremities of the curve) and `Beta` (beta law)." **[V]** The kernel confirms the set — a
`switch` on `atype` with case 1 geometric progression, case 2 bump, case 3 beta, case 4 a
`// standard boundary layer progression: TODO` — plus three *input conversions* (types 5, 6, 7)
that solve a requested **wall height** back into the law's coefficient by bisection/Newton
before meshing. **[V]** No case takes an array; one scalar `coeffTransfinite` is all an edge
carries.

**[I] But a transfinite SURFACE in Gmsh consumes whatever nodes are already on its boundary
curves.** `meshGFaceTransfinite.cpp` builds its boundary list by concatenating each bounding
curve's existing `mesh_vertices` (forward or reversed), and `meshGEdge.cpp` returns early for a
curve whose `meshAttributes.method == MESH_NONE`. So an explicit per-node distribution reaches
a transfinite patch through the API by placing the curve's nodes yourself, even though no
`Using` clause can express it. **[V]** on both code facts; **[I]** that the combination works,
since I did not run it.

### 2d. HYPGEN — the explicit list, and the per-station spacing, both shipped in 1993

NASA TM 108791 (Chan, Chiu & Buning), the HYPGEN user's manual, is the primary source the
offset-ring note listed as a gap. It closes two questions at once.

**An explicit node list, option `IZSTRT = -1`:** **[V]**

> "There are certain situations where a special stretching function, other than exponential or
> hyperbolic tangent, is required. By specifying IZSTRT = -1, a user-defined stretching
> function is read in from the file `zetastr.i` with dimensions jzs x kzs x lmax. … A
> stretching function for point (J,K) is defined by a **monotonically increasing
> one-dimensional array of numbers** with index running from 1 to lmax. The approximate
> distance of the Lth layer of the volume grid from the body surface is specified by the Lth
> element of the array; i.e., the first element has the value zero, the last element is
> assigned the far field distance, and the grid spacing between consecutive L-shells is given
> by the difference between the corresponding consecutive elements in the array."

and the four scopes it can have: `jzs=1,kzs=1` same for all; `jzs=jmax,kzs=1` copy the J
variation to every K; `jzs=1,kzs=kmax` the mirror; `jzs=jmax,kzs=kmax` "**different stretching
for each J and K**". **[V]**

**A spacing that is a property of the STATION, with this repo's exact motivating example:** **[V]**

> "In certain applications, it is desirable to have different far field distances at different
> locations… Similarly, **a variable initial grid spacing may be desirable along the wake cut
> of an airfoil C-mesh to fan out the points at the downstream boundary**. For each point on
> the surface grid, HYPGEN allows the user to specify the following three quantities: a far
> field distance (ZREG), an initial and an end grid spacing (DZ0 and DZ1)."

with a helper tool (`SETZETA`) that fills that field by piecewise-linear interpolation between
named stations, and the explicit expectation that for anything harder "the user can write a
separate program … to generate the file `zetavar.i` that is tailored to his/her specific
requirements". **[V]** The two mechanisms are mutually exclusive: "If a user-defined stretching
function is used, then the variable far field distance and initial/end grid spacings option
cannot be activated, and vice versa." **[V]**

**[I]** The repo's "a tanh edge cannot take a different first-cell height at each end, and the
mesher refuses a per-station height" is, line for line, the capability HYPGEN shipped as two
separate options thirty-three years ago. Neither needs a new mesh algorithm; both are input
plumbing.

---

## 3. GridPro specifically

Primary sources read: Eiseman, *Multiblock Grid Generation with Automatic Zoning* (NASA CP,
1995; Program Development Corporation), the GridPro v10 FAQ PDF published on gridpro.com, and
the GridPro HiOCFD5 presentation by Sudharshanam, Ebenezer & Eiseman (2015). The *User's Guide
for TIL* and the *WS GUI Manual*, which the FAQ cites by section for almost every answer, are
behind a registration form — see Gaps.

**Why the blocks are irregular.** The topology is authored as a pattern of POINTS with LINKS
between them, in a language (TIL) whose basic unit is a `COMPONENT`; the blocks are what that
wireframe implies, and their shapes are a RESULT: **[V]**

> "The multiblock template provides zones for the various coordinate grid blocks to reside…
> It is, in fact, **a coarse unstructured dissection of space into chunks**. In distinction
> from what is typically called an unstructured grid, the cells define macro regions in space
> that are called zones and **which generally have curved boundaries**."

and the user never places a zonal edge:

> "In the traditional approach … the user must not only insert rather large amounts of data but
> also must make judgments about that data… from something as basic as placing one zonal corner
> in space to more detailed matters such as determining both the shape and location of zonal
> edges… **There is no longer the rather manual construction and assembly of multiblock
> grids**… Instead, the amount of input data is enormously reduced, the detailed human judgment
> is gone."

**What the smoother does.** The grid is relaxed to the equilibrium of a variational scheme,
with projection onto the geometry as part of the same solve rather than a post-step: **[V]**

> "the run could be started with a fairly modest number of grid points which are then increased
> in stages as the grid is relaxed towards its equilibrium that **progressively satisfies the
> underlying variational scheme**."

> "Grid generator **automatically projects and moves grid points to optimal locations** to
> create a smooth orthogonal grid." (HiOCFD5 slide 5, same authorship.) **[V]**

> "Basic grid quality appears in the form of near orthogonality, smoothness, low warpage, and
> **curvature clustering for both concave and convex boundaries**… Upon activation, the
> volumetric grid points distribute themselves about the boundaries **in proportion to the
> boundary curvature**." **[V]**

**What that does to the distribution — the part that bears on this note.** In GridPro the
spacing is not an edge property at all. It is attached to a SURFACE, and reaches a block face
when that face's corners are assigned to the surface; there is even a surface type that exists
for no other purpose: **[V]**

> "a **floating surface** can also be defined. It is abstract since there is no defined
> position or condition for this surface. This type of surface is used to **define clustering
> to any block face regardless of where it is**… the flag `-float` is used in the surface
> definition line; next, there is a cluster group flag (either `-c` or `+c`); and then there is
> **the desired spacing for the first grid point on either side**."

and in v10 the boundary-layer clustering is a command over the finished grid, parameterised by
first-layer spacing, growth ratio, off-wall cell count and an equal-spacing option: `clu` /
`mildclu` with `-s <surface id> <spacing>`, `-r <ratio>`, `-ns` ("the no. of cells in off-wall
layer for a surface"), `-fix` ("we can have equal spacing between the cells in the off-wall
layer"). `Ggrid euler` runs the same topology "**without any clustering parameters**". **[V]**

**How many blocks.** Not a design target, and not small: "Because of the automation, massive
complexity is efficiently handled with a large number of blocks. **The count can go to a
thousand, ten thousand, or more** depending upon the scope of the analysis." **[V]** The
published workflow also MERGES afterwards: GridPro distinguishes *elementary blocks* from
*superblocks*, with command-line tools to go each way (`hex2emb`, `segb`), to limit how many
blocks merge (`-maxb`), and to merge by density, property or label. **[V]** **[I]** So in
GridPro the block count is an artefact of the topology plus a post-hoc merge policy, which is
why asking "how many blocks should a 2-D aerofoil have" gets no answer from this tool's
documentation: the question is not posed to the user.

**For the 2-D aerofoil specifically**, the only published figure I reached is a description,
not a count: **[V]**

> "Figure 4: An airfoil close to the ground… it is clear that there are **no undesirable
> clusters of points on the boundaries either above or upstream of the airfoil**. While a
> cluster appears for the full length of wake branch cut, it too could have been limited to
> some distance before the downstream boundary if desired… In the vicinity of both the leading
> and trailing edge, the coordinate curve density is at its highest… the chosen pattern of
> points sends curves **looping from the bottom of the airfoil to the top about both leading
> and trailing edges**… We often call such loop structures '**clamps**' or as in the case of
> the trailing edge structure '**a collar**.' The TIL code for this case was a little over one
> page."

**[I] This is the answer to the brief's second question, from the tool that prompted it.**
GridPro's handling of "the leading edge needs cells 40x smaller than this ring's mean" is not a
distribution at all: it is extra blocks, looped around the feature (a clamp), plus `nest` /
`Enrich` to add more blocks near the geometry without touching the far field, plus
`reverse_nest` to take blocks away in the far field. The fine-to-coarse transition is carried
by the BLOCKING, and the per-edge distribution stays simple because no single edge has to span
both scales. The repo's own measured trend — median block range 1.29e6 → 130 → 23.1 → 8.4 as
blocks go 4 → 24 → 48 → 84 — is the same mechanism observed from the outside.

One caution GridPro states about pushing this too far in the other direction: "Sometimes, you
may see wavy lines on the grid instead of straight lines. It is because of the **aspect ratio of
the cells**; in such cases, increase the density of the edges to reduce the aspect ratio."
**[V]**

---

## 4. The alternatives, and what each one costs

**Hyperbolic / parabolic marching (HYPGEN, pyHyp, Chan & Steger).** The generator solves "two
orthogonality relations and **one cell volume constraint**" and marches away from the surface;
the outer boundary is wherever the march ends. **[V]** The within-block range problem does not
arise in the brief's form, because the cell SIZE is an equation of the generator rather than a
consequence of two edge distributions meeting: the user hands it a normal-direction stretching
(exponential, tanh, or the explicit array of §2d) and the marching distributes the rest.
**Costs, all stated in the manual**: the outer boundary shape is not yours to specify (only a
far-field distance, per point if you want); the method needs smoothing coefficients tuned per
geometry ("Guidelines on the Choice of Grid Smoothing Parameters" is a whole section, with
constant / spatially varying / implicitly averaged / angle-bisecting variants); concave
geometry needs the splay boundary condition; and the tanh spacings you ask for "are only the
**asymptotic values**, i.e. the actual grid spacings computed for the 1-D stretching are
usually slightly different from the ones specified". **[V]** It also cannot, by construction,
produce a point-matched multi-block decomposition — one march, one block.

**Patched / non-matching interfaces in structured solvers.** CGNS has the vocabulary:
`GridConnectivityType_t := Enumeration ( GridConnectivityTypeNull,
GridConnectivityTypeUserDefined, Overset, Abutting, Abutting1to1 )` — `Abutting` being the
non-1-to-1 case, carried by `PointList` / `PointListDonor` / `CellListDonor` and optional
`InterpolantsDonor`. **[V]** CFL3D implements it: `ninter` counts "patched-grid interfaces
(zonal interface along a common surface where points need not match)", and the interpolation
coefficients for static interfaces are built by a **separate preprocessor** (`ronnie`) and read
from a binary file at run time; dynamic (sliding) interfaces are computed inside the solver.
**[V]** **Cost**: it removes the problem completely — each block's point count is independent,
so no edge has to span two scales — and in exchange you give up conservation and accuracy at
the interface to an interpolation, you add a preprocessing step with its own input file, and
your solver has to support it. **[I]** on the first clause of that trade; the manual states the
mechanism, not an error estimate.

**Overset / Chimera.** Same escape at the level of whole grids rather than faces: CGNS's
`Overset` connectivity "identifies the fringe points of a given zone that lie in one and only
one other zone", and CFL3D's overlapped-grid coefficients come from `MaGGiE`, the sibling
preprocessor to `ronnie`. **[V]** This repo's `multi-element-airfoil-blocking.md` already
records what the aerodynamics community does with it (5–7 zones in 2-D for three elements,
against 26 conforming) and why — not repeated. **Cost**: hole cutting, donor search,
interpolation, and a solver that does all three.

**[I] Ranking these for the repo's question.** Only the patched/overset family removes the
within-block range problem outright, and both put the cost in the SOLVER, which this repo does
not own. Marching removes it for a one-block mesh, which is not what `MESH_MODE 1` is for.
Subdividing the blocking — GridPro's `nest`/clamp answer — keeps the whole cost inside the
mesher and is what the brief's own table already shows working.

---

## 5. What this bears on, for this repo

Stated as inference, because none of these sources was written about this tool. **[I]**

1. **Stop reporting within-block area range as a quality number, or report it beside the
   neighbour ratio and say which one is the criterion.** The reference grid of this exact
   geometry class scores 3.4e12 on it. A figure on which the field's own yardstick is 2.6
   million times worse than the thing under test is not measuring fitness; §L2 derives what it
   does measure (how much of the domain one block spans). The metric the whole field bounds —
   `max(A_i/A_j)` over face-adjacent cells, and its one-dimensional cousin — is cheap to
   compute on this mesher's output, has published thresholds already collected in
   `multi-element-airfoil-blocking.md` §5, and is the one `MbQuality` does not yet have.
2. **The two-ended tanh is the single highest-value missing primitive.** Four of the five
   generators read here let one edge take a different first-cell height at each end; this repo
   is the exception, and the brief records that refusal as the reason the right fix was
   abandoned. It is a solver change in `Spacing.hpp` (a two-parameter tanh beside
   `solveTanhStartDelta`), not a new subsystem.
3. **The missing propagation rule has a published name and three published tie-breaks.** ICEM's
   `Match Edges > Automatic` takes a VERTEX and matches every edge meeting there to the
   `Minimum`, `Maximum` or `Average` spacing at that vertex. That is the repo's third rejected
   fix, shipped, with the ambiguity the repo hit ("which of the meeting edges wins?") resolved
   by making the policy an explicit choice rather than a derivation.
4. **If an exact offset-image distribution is ever wanted, the precedent is an explicit array,
   not a better law.** HYPGEN's `IZSTRT = -1` reads a monotone array of distances per surface
   point; Pointwise stores the same thing as a `General` distribution and refuses to let a
   human author one; ICEM authors it through a graph with saveable control points. The
   offset-ring note's "out of reach because this mesher's edge distributions are only uniform /
   geometric / tanh" is therefore a statement about the schema, and every tool that solved it
   solved it by adding a fourth kind of edge whose content is data.

---

## Gaps I could not close, by name

1. **GridPro's own manuals.** `User_Guide_for_TIL` and `WS_GUI_Manual` — cited by section
   number in nearly every FAQ answer, including §4.9.2 (`nest` / `reverse_nest`), §4.9.3
   (`Enrich`), §5.3.4 (surface clustering) and §5.5 (bad-block location) — are behind a
   HubSpot registration form on gridpro.com. Everything I state about those features comes from
   the FAQ's one-paragraph answers, not from the manuals.
2. **A GridPro 2-D aerofoil block count.** `sp.gridpro.com/docs/WS_10.0_Tutorials.zip` (linked
   from the documentation page) returns **404**, so I could not open a TIL file and count. The
   figure-4 caption describes the clamp/collar structure without a number.
3. **Eiseman's earlier papers.** `Multiblock Grid Generation with Automatic Zoning` cites
   Eiseman, Cheng & Häuser (Swansea 1994) and the GridPro/az3000 User's Guide (1994) for the
   mathematics; neither is online. DTIC `ADA259958`, which search suggested is a PDC/Eiseman
   report, answers **HTTP 403** to a non-browser request. The "variational scheme" is therefore
   named but not characterised: **I never saw the functional GridPro minimises.**
4. **Numeca / Cadence AutoGrid.** The AutoGrid5 User Guide is not published openly; the only
   copies reachable are on Scribd, which is secondhand and which I did not use. Its
   distribution-law vocabulary is unknown to me — this is the one tool in the brief I could not
   answer at all.
5. **Pointwise's live documentation.** Every `cadence.com` and `pointwise.com` URL returns
   **HTTP 403** to a non-browser fetch. All Pointwise quotations are from the Internet
   Archive's `20231202` capture of the official manual and the Glyph 3.18.6 reference. If a
   newer release changed a definition, I would not know.
6. **The DPW and HiLiftPW gridding-guideline originals.** `aiaa-dpw.larc.nasa.gov` no longer
   resolves and `hiliftpw.larc.nasa.gov` redirects to a NASA landing page. §1c's statement that
   the guidelines contain no within-block range bound rests on the quotations already verified
   in `docs/research/multi-element-airfoil-blocking.md` §5, not on a fresh read this week.
7. **The finer TMR grids.** `n0012_897-257` and above are stored as `.gz` through a GitHub LFS
   path that returned **404**; §L2's measurements are the two levels distributed as plain text.
   The trend across them (1.379e12 at 113x33, 3.424e12 at 225x65) is two points, not a curve.
8. **Whether Gmsh's explicit-node route actually meshes.** §2c's conclusion combines two
   verified code facts; I did not build Gmsh and run it, so the claim that an API-placed node
   set survives into a transfinite surface is **[I]**, not a test result.
9. **An error estimate for patched interfaces.** CFL3D documents the mechanism and `ronnie`'s
   role; it does not quantify what the interpolation costs in accuracy, and I found no primary
   number. §4's "you give up conservation and accuracy at the interface" is **[I]**.

---

## Sources

Primary, read by me:

- Fidelity Pointwise User Manual (Cadence, © 2021), via the Internet Archive capture
  `web.archive.org/web/20231202…` of: `examine/index.html`, `examine/functions/index.html` and
  its per-function pages `area-volume-ratio`, `length-ratio-i-j-k`, `smoothness-ijk`,
  `expansion-ratio-fidelity`, `volume-ratio-fidelity`, `aspect-ratio`; `examine/rules/index.html`;
  `grid/distribute/index.html` and `grid/distribute/functions.html`.
  Live URLs (403 today): https://www.pointwise.com/doc/user-manual/
- Glyph 3.18.6 reference (Cadence), same archive: `GlyphDistributionGeneral-cxx.html`,
  `GlyphSpacingExplicit-cxx.html`, `GlyphSpacingSynchronizer-cxx.html`, `GlyphExamine-cxx.html`.
- Ansys ICEM CFD Help Manual / User's Manual, Release 2025 R1:
  https://ansyshelp.ansys.com/public/Views/Secured/corp/v251/en/icm_help/iblock_premeshqualoptions.html
  (and `iblock_maxratio`, `iblock_volumechange`, `iblock_aspectratio`, `iblock_xsize`,
  `iblock_edgeparams`, `iblock_bunching`, `iblock_matchedges`), plus
  `.../icm_user/iuser_edgemeshparams.html`.
- CGNS SIDS: https://cgns.github.io/standard/SIDS/ — `intro.html`, `design.html`, `grid.html`,
  `multizone.html`, `misc.html` (`GridConnectivityType_t` at `multizone.html`).
- Verdict (Sandia), `sandialabs/verdict@master`: `V_QuadMetric.cpp`
  (`quad_relative_size_squared`, `quad_shape_and_size`, `quad_shear_and_size`).
- Gmsh, `live-clones/gmsh@master`: `doc/texinfo/gmsh.texi` (Transfinite Curve syntax),
  `api/gmsh.h` (`setTransfiniteCurve`), `src/mesh/meshGEdge.cpp` (the law switch and the
  type 5/6/7 wall-height conversions), `src/mesh/meshGFaceTransfinite.cpp` (boundary
  `mesh_vertices` consumption).
- Chan, W. M., Chiu, I.-T. & Buning, P. G., *User's Manual for the HYPGEN Hyperbolic Grid
  Generator and the HGUI Graphical User Interface*, NASA TM 108791, October 1993 —
  https://ntrs.nasa.gov/citations/19940011311 (§2.1, §2.2.1, §2.3.1–2.3.4, §2.6).
- Krist, S. L., Biedron, R. T. & Rumsey, C. L., *CFL3D User's Manual (Version 5.0)*,
  NASA TM-1998-208444, June 1998 — https://ntrs.nasa.gov/citations/19980218172
  (§2.4, §3.27 LT27, §9.1.3).
- Eiseman, P. R., *Multiblock Grid Generation with Automatic Zoning*, Program Development
  Corporation, NASA conference paper 1995 — https://ntrs.nasa.gov/citations/19950022314.
- GridPro, *Frequently Asked Questions* (v10), gridpro.com documentation page →
  `https://22821077.fs1.hubspotusercontent-na1.net/hubfs/22821077/Version 10 documents/FAQs.pdf`
  (T37, G25–G34, G40, G44–G53).
- Sudharshanam, V., Ebenezer, S. & Eiseman, P., *GridPro — Higher order meshes*, 5th
  International Workshop on High-Order CFD Methods (HiOCFD5), 2015 —
  https://acdl.mit.edu/HOW5/WorkshopPresentations/GridPro_HO_Meshes.pdf.
- NASA Turbulence Modeling Resource, 2-D NACA 0012 validation case and grids —
  https://tmbwg.github.io/turbmodels/naca0012_val.html and `naca0012_grids.html`; grid files
  `n0012_113-33.p2dfmt`, `n0012_225-65.p2dfmt` from `TMBWG/turbmodels@main`.

Measured by me: the two TMR grids above (cell areas by shoelace; max/min ratio; max adjacent
area ratio in each index direction), 2026-10-20.

In this repo:

- `docs/research/arc-length-correspondence-on-an-offset-ring.md` — the offset relation, and the
  gaps on CGNS and HYPGEN that §1a and §2d close.
- `docs/research/multi-element-airfoil-blocking.md` §5 — the published growth-rate, spacing and
  block-count figures this note deliberately does not restate.
- `.claude/rules/mesher-multiblock.md:104` (the three spacing laws), `:367` (`tanh` as the
  default and why), `:378` ("two DIFFERENT heights at the two ends" refused by name).
- `tools/PreProcessor/include/Spacing.hpp:107` `solveTanhDelta` (both ends, equally),
  `:125` `tanhStartPos` / `:143` `solveTanhStartDelta` (the start only) — the pair that makes
  §L3's last row read "no".
