# Can a flow solution decide a block topology

**A RESEARCH NOTE, like the others beside it.** Not `.claude/rules/*.md` (what the rule is), not
`docs/design_notes/` (why a shipped rule was chosen). It records what the solver source code, the
vendor manuals, the NASA reports and the papers' own bodies say about whether a computed flow
field is ever allowed to decide a BLOCK TOPOLOGY, so that a feature proposal can be argued from
sources rather than from plausibility. Nothing here is binding; no rule, gate, test or source file
was changed to write it. 2026-11-05.

**Subject.** A maintainer proposed a subprogram that would help a novice author a `MESH_MODE 1`
topology document: mesh coarsely, run the solver, read the DENSITY GRADIENT off the resulting
field, partition the domain into blocks where that gradient says to, and write the `.json`. This
repo already has the two ends of that chain — four geometry-driven topology families
(`services/topology_{hgrid,ogrid,cgrid,tworing}.py`, each a pure function of curves plus
parameters) and a headless pipeline whose solver stage writes a Tecplot field — so the question
is only whether the middle link is a thing the field does. The suspicion to be tested was that a
solution field conventionally drives SIZING, while block TOPOLOGY is driven by GEOMETRY. It is
right, and it is more interesting than a flat "no": there is a published chain that gets from a
solve to a block topology, it was published in 2023, and the step that makes it work is one the
proposal leaves out.

## How to read the markers

- **[V]** verified in a primary source I read myself (source code, official docs, a NASA report,
  or the paper's own body), or measured by me.
- **[I]** my own inference from a **[V]** fact. Stated as reasoning, not as fact.
- **[2nd]** I could only find this secondhand. Treat as unconfirmed.

A note on the Ansys citations: `ansyshelp.ansys.com`'s *public* views answered a non-browser
request today and are quoted as the vendor's own text. The Fluent pages are the ANSYS FLUENT 12.0
User's Guide and Theory Guide on ENEA's long-standing mirror, which is the vendor's text on a
third party's server, not a summary of it; that is stated rather than hidden.

---

## Lead: the six answers a reader needs first

### L1 — A solution field drives SIZE, SHAPE and ORIENTATION. The block structure is driven by geometry, and both vocabularies say so in their own words, in the same sentence shape. **[V] on each side; [I] on the absence**

The adaptation side names its output as a *field of tensors*, not a topology. NASA's `refine`,
the metric-conforming mesher behind the AIAA workshops' adaptive submissions, builds its metric in
five steps and every one of them is a per-node quantity:

```c
REF_FCN REF_STATUS ref_metric_lp(REF_DBL *metric, REF_GRID ref_grid,
                                 REF_DBL *scalar, ...) {
  RSS(ref_recon_hessian(ref_grid, scalar, metric, reconstruction), "recon");
  RSS(ref_recon_roundoff_limit(metric, ref_grid), "floor metric eigenvalues ...");
  RSS(ref_metric_local_scale(metric, ref_grid, p_norm), "local scale lp norm");
  RSS(ref_metric_limit_aspect_ratio(metric, ref_grid, aspect_ratio), "aspect ratio");
  RSS(ref_metric_gradation_at_complexity(metric, ref_grid, gradation,
                                         target_complexity), "gradation at complexity");
```

(`nasa/refine@master`, `src/ref_metric.c:2239`.) **[V]** The thing produced is `REF_DBL *metric`,
six doubles per node. Where to put nodes, how big, how stretched, which way. Nothing in that
signature can say "and here is a new corner".

The blocking side names its input as *geometry*, equally plainly. ICEM CFD's own help on
Initialize Blocks: "**geometry connectivity translates into blocking connectivity**", and for 2-D
surface blocking "geometry topology information is required to establish connectivity between
blocks" — the user is told to check for double versus single edges and to build diagnostic
topology before initializing. **[V]** Gmsh's quasi-structured quad pipeline (Algorithm 11) takes
"**a valid CAD model**" and computes its cross field "with crosses aligned with the CAD curves
bounding the face"; the only field it will accept from outside is a *size map*, and the option
that admits one says exactly what it is for: `Mesh.QuadqsSizemapMethod` — "0: default, 1:
cross-field, 2: cross-field + CAD small features adaptation, **3: from background mesh (e.g.
sizes in current triangulation)**, 4: cross-field + CAD small features adaptation (clamped by
background mesh)" **[V]**. A background field, and it carries *sizes*.

**[I] The absence.** I read ICEM CFD's blocking help, Gmsh's full option list and quasi-structured
paper, GridPro's v10 FAQ, and CubeCover's frame-field pipeline, and found no input slot anywhere
that takes a flow solution. I did not read ANSA's HEXABLOCK manual or GridPro's own TIL/GUI
manuals (see "Gaps"), so this is an inference from four tools, not a survey of all of them.

### L2 — A bare density gradient is the one sensor the field does NOT ship. Every shipped shock sensor I read is a pressure switch, a dilatation-over-vorticity ratio, a normal Mach number, or a normalised SECOND derivative with a noise filter. **[V]**

Four implementations, read in their own source or their own manual:

| where | what the sensor actually is | variable |
|---|---|---|
| SU2, centred schemes | `sensor_i = \|Σ_j (p_j − p_i)\| / Σ_j (p_j + p_i)` — the code's own comment: "Jameson dissipation sensor, add variable difference and variable sum" | **pressure** |
| SU2, `FD_DUCROS` | `−(∇·u) / (\|∇·u\| + \|ω\| + 1e−20)` | dilatation vs **vorticity** |
| SU2, `NTS_DUCROS` | `(∇·u)² / ((∇·u)² + \|ω\|² + 1e−20)` | same pair, squared |
| FLASH / PARAMESH | "adapted from Löhner (1987) … a modified second derivative, normalized by the average of the gradient over one computational cell", with "the last term in the denominator … a filter, preventing refinement of small ripples" | **any**, and FLASH4 "does not define any refinement variables by default" |
| Ansys Fluent | `\|e_i1\| = (A_cell)^(r/2) \|∇f\|` (Gradient) or `(A_cell)^(r/2) \|∇²f\|` (Curvature), then Standard / Scale (`\|e\|/average\|e\|`) / Normalize (`\|e\|/max\|e\|`) | **user's choice**, never defaulted to density |

**[V]** on every row (`su2code/SU2@master`, `SU2_CFD/src/solvers/CEulerSolver.cpp:2432` and `:2446`,
`SU2_CFD/include/solvers/CFVMFlowSolverBase.hpp:773`; FLASH4 User's Guide §8.6.3.1; ANSYS FLUENT
12.0 Theory Guide §19.3.1 and User's Guide §27.3.1).

Two things follow from the Fluent row alone. A raw `|∇f|` is **dimensional and mesh-dependent**,
which is why it is multiplied by `(cell volume)^(r/2)` before it is compared with anything, and
why the manual says that "using either scaling or normalization makes the setting of the refine
and coarsen thresholds much simpler, and almost independent of the current solution and specific
problem" **[V]**. And the one place a raw first gradient IS recommended is the narrowest:
"**Gradient** specifies the use of the first gradient of a field variable for adaption. This
approach is recommended for problems with strong shocks (e.g., supersonic inviscid flows)" — with
Curvature, the second gradient, "recommended for problems with smooth solutions" **[V]**.

### L3 — `|∇ρ|` does fire at contact discontinuities, and the published answer to "which variable avoids that" is pressure or `∇·u`, in as many words. **[V]**

Samtaney (NASA Ames / MRJ), *Visualization, extraction and quantification of discontinuities in
compressible flows*, NTRS 20000068998, recommending variables after applying edge detectors to
several fields:

> - Magnitude of gradient and Laplacian of the **density** to visualize shocks **and
>   discontinuities**,
> - Gradient magnitude and Laplacian of the **pressure**, as well as the divergence of the
>   velocity field to visualize **shocks** … **Contact discontinuities do not show up in these
>   variables because, in theory, the pressure and normal velocity are both continuous across
>   contact discontinuities.** … Note that entropy is also discontinuous across contacts.

**[V]** That is the question answered directly: density sees everything a schlieren image sees;
pressure and dilatation see shocks only.

### L4 — There IS a published method that does what the maintainer described, it is 2023, and the step that makes it work is the one the proposal leaves out: the solution is turned into GEOMETRY first, and the blocker stays geometry-driven. **[V]**

Deng, Wang & Qin, *Cross-field structured adaptive mesh using medial axis flow feature
extraction*, AIAA Journal 2023 (doi 10.2514/1.j063346), author-accepted version, CC-BY:

> The initial structured meshes are produced and implemented to solve the flow problem studied as
> initial solution, and then regenerated with flow features being extracted and embedded as
> geometric entities using a medial axis method.

and, at the seam that matters:

> **The flow feature curves are inserted into the initial geometry to regenerate the background
> mesh.** The cross-field and blocks are generated with different approaches to flow feature
> curves. … **The block topology is created by connecting the cross-field streamlines to the
> singularities and corners in the domain.**

**[V]** The solution reaches the block topology — but only after it has become a *curve in the
geometry*, at which point the blocker is doing what blockers have always done. §4 below walks the
whole chain, including the error estimate that marks the feature nodes (a **Hessian**, not a
gradient) and the convergence test on the number of critical nodes.

The same paper states the state of the art it is pushing against, which is the honest answer to
"is this already a solved button somewhere": **[V]**

> The main hurdle restricting the widespread application of feature aligned structured grid is
> that it is often necessary to **divide the structured blocks manually** for complex geometries
> and/or flow features, which requires considerable experience and skills, and requires a lot of
> time and labor cost.

### L5 — The one place a solution DOES move a block boundary in shipped production CFD is the hypersonic shock fit, and it moves a boundary that already existed, on a Mach iso-surface, not on `|∇ρ|`. **[V]**

McCloud, *Best Practices for Unstructured Grid Shock Fitting* (NASA/ERC-Inc, NTRS 20160009327),
describing what DPLR and the structured hypersonic codes do:

> Once a solution is obtained on the initial grid, the shock fitting process is started. The user
> typically specifies a percentage of the free stream Mach number. **For DPLR, this is typically
> 95%.** The adaptation algorithm analyzes the k-lines and determines where the Mach number
> reaches the specified value. This location then represents the shock location. … Finally, **the
> k-lines are then modified such that the kmax point lies just outside of the shock** with a
> minimal margin for maximum computational efficiency.

**[V]** The block count, the block connectivity and the index ranges are untouched; one
already-declared outer boundary is re-placed onto a solution-derived surface. The same report
gives the method's published failure mode, which is a warning about any single-threshold detector:

> The drawback to this methodology is that it does not allow for the existence of internal shocks
> or the presence of plumes in the flow field. As the algorithm follows the k-lines and encounters
> a location where the Mach number meets the criteria, **even if not the bow shock, it will treat
> that feature as the bow shock and the process will fail.**

### L6 — "Coarse run first" for grid GENERATION is real and shipped, but it is a LOOP that keeps re-solving, not a one-shot configuration writer — and it is a different thing from grid sequencing, which is a solver convergence device on a fixed grid. **[V]**

Shipped loops I verified: NASA `refine`'s own `ref loop` subcommand ("**Multiscale metric, adapt,
and interpolation**") **[V]**; Cart3D's "fully automated adjoint-driven mesh adaptation for steady
simulations" over "topologically unstructured, adaptively refined, Cartesian meshes" **[V]**;
Ansys FENSAP-ICE's OptiGrid adaptation sequences **[V]**; Fluent's gradient adaption **[V]**. The
HLPW-4 adaptive submission ran **eighteen** adapted meshes — "the first ten automatically adapted
meshes are intended to control interpolation error of the Mach number field and the following
eight meshes controlled the error in the drag coefficient" **[V]** (Wood & Park, NTRS 20220007063).
One solve is never the end of one of these.

And the thing it must not be confused with, in the vendor's own words. NASA WIND-US, `SEQUENCE`
keyword: "This option allows the user to, in effect, **thin the computational grid**, thus reducing
CPU requirements. It can be used to obtain quick starting solutions for the fine grid." **[V]** The
grid is not changed; coarse *levels of the same grid* are iterated on to start the fine solve.
Grid sequencing and multigrid take a grid as given; adaptation produces one.

---

## 1. The division of labour, in full

### 1a. What the adaptation side takes in, and what it hands back

`refine`'s README states its own scope in the first sentence: "`refine` is a 2D and 3D mesh
adaptation tool implemented in the C language. **Mesh adaptation mechanics are provided where the
primary target is linear and curved simplex (triangle and tetrahedra) meshes.** A limited
capability to store, modify, and insert mixed-element types is also provided." **[V]**

The working group that defines the benchmarks for this class of tool names itself after the mesh
type: the **Unstructured** Grid Adaptation Working Group, whose members develop "tools to modify
unstructured grids to conform to a metric (anisotropic size request)" **[V]**. The parenthesis is
the whole story: a metric *is* an anisotropic size request.

The scalar whose Hessian becomes that metric is the user's choice, and `refine`'s own help
enumerates it:

```
   --interpolant <type or file.solb> multiscale scalar field.
       Type is mach (default), incomp (incompressible vel magnitude),
       htot, ptot, pressure, density, or temperature.
       Read from file.solb, if not a recognized type.
```

(`nasa/refine@master`, `src/ref_subcommand.c:234`.) **[V]** Density is on the list. It is not the
default, and what is taken of it is the **second** derivative — `ref_recon_hessian(ref_grid,
scalar, metric, reconstruction)` — never the first.

Two further operations in that pipeline are worth naming because they are what makes a Hessian
usable and have no analogue in "read the gradient and cut there":

- **`ref_metric_local_scale`** multiplies the metric by `det(M)^(−1/(2p+d))` — the `Lp` local
  scaling. `refine`'s own help: "`--norm-power <power> multiscale metric norm power (default 2)`".
  **[V]** Wood & Park say what it buys: "The multiscale metric aims to control the `L_p`-norm of
  the interpolation error of a solution scalar field to target both smooth and unsmooth error
  contributions. **Classic Hessian-based adaptation methods control quadratic interpolation error
  estimates in the `L_∞`-norm, which results in excessive refinement of unsmooth regions.**" **[V]**
- **`ref_metric_hessian_filter`** exists specifically to stop a discontinuity from poisoning the
  whole field. Its own comment: "find the largest valid eigenvalue that is **not in a
  discontinuity**" and then "limit hessian eigenvalues **everywhere** based on what is considered
  valid outside a discontinuity". **[V]**

**[I]** Both of those are corrections for the fact that a raw second derivative at a captured
shock is a number set by the mesh that captured it, not by the physics. A raw *first* derivative
has the same disease with nothing in the published pipeline correcting it.

### 1b. What the blocking side takes in

| tool | input to the block topology | is a field accepted? what does it control? |
|---|---|---|
| ICEM CFD Hexa | geometry; "geometry connectivity translates into blocking connectivity"; 3-D Multizone needs "body information" **[V]** | no field; mesh sizes are set per edge/curve (see the sibling note `cell-size-range-within-a-block.md` §2a) |
| Gmsh `Quadqs` | "a valid CAD model"; cross field from the triangulation with crosses aligned to the bounding CAD curves **[V]** | yes — a **size map**, `Mesh.QuadqsSizemapMethod` option 3 "from background mesh" **[V]** |
| GridPro | a coarse wireframe the user builds over the geometry, then automatic grid generation **[2nd]**; adaptive refinement is "possible in topology level using the tools like `nest`, `reverse_nest` and different topology strategies" (FAQ G54) **[V]** | the FAQ's "density" questions (T31, G19, G29, G41) are all **edge division counts**, not a field **[V]** |
| CubeCover / polycube | "The input of CUBECOVER is a tetrahedral volume mesh. First, a frame field is designed with **manual input from** [the designer]" **[V]** | the frame field — directions, and it is authored, not solved for |
| medial axis (Price & Armstrong line) | the geometry's own medial axis / medial surface **[2nd]** | — |
| cross/frame field (Fogg, Kowalski, Bunin) | geometry + a target element size and shape **[V]**, see §1c | the target metric — size *and* anisotropy |

**[I]** Every row that accepts a field accepts the SAME KIND of field: a per-point statement of how
big and how stretched. None of them accepts a per-point statement of where a corner goes. The
field's own interface for "a solution influences a mesh" is the metric, and the metric has no slot
for topology.

### 1c. The one paper that proposes the link, and the tense it proposes it in

Armstrong, Fogg, Tierney & Robinson, *Common themes in multi-block structured quad/hex mesh
generation*, Procedia Engineering (24th International Meshing Roundtable, 2015), is the survey
that sets up everything in §5 and is the closest thing to a position statement on the maintainer's
question. It opens with the problem: "The automatic generation of structured multi-block
quadrilateral (quad) and hexahedral (hex) meshes has been researched for many years **without
definitive success**. The core problem in quad / hex mesh generation is **the placement of mesh
singularities** to give the desired mesh orientation and distribution." **[V]**

It states the *goal* in solution terms:

> An effective multi-block topology maximises the proportion of the mesh that is structured and
> **allows the mesh to align with the main anisotropic features of the solution field**.

**[V]** — and then states the mechanism in the conditional, which is the sentence to read closely:

> Fogg et al. have shown that cross field methods for multi-block decomposition can be sensitive
> to both target element size and shape. **It should therefore be possible to** a) utilize
> solution error analysis to derive a mesh metric size and shape distribution based on the results
> of an initial analysis and then b) utilize that local size and shape information to produce a
> quad mesh and multi-block distribution that respects those metrics to adaptively refine the mesh
> geometry and topology to capture the solution to a prescribed error tolerance.

**[V]** This is the maintainer's idea, written down by the people who built the cross-field
blockers, in 2015, as *a thing that should be possible*. And in the same paper, the status quo:
"**The conventional approach to multi-blocking hex meshing is to manually define a block
topology.** Vertices, edges and faces of the block topology are then associated with real
geometry. … An extensive set of block topology recipes is available in various packages, though it
appears that **these recipes usually have to be hand coded**." **[V]**

**[I]** The mechanism the 2015 paper proposes is still *metric in, topology out* — the solution
enters as a size-and-shape field and the cross field's singularity placement responds to it. That
is a real and different route from the one §4's 2023 paper took (solution → curve → geometry), and
I found no implementation of it on a CFD case. It is named in "Gaps".

---

## 2. Metric-based adaptation, and the one time it meets a structured grid

### 2a. The input is a Hessian of a scalar; the default scalar is Mach

Established verbatim in §1a. The workshop practice confirms the default is not decorative: HLPW-4's
adaptive submission used "the multiscale metric … to concentrate mesh nodes so that **large
gradients in the Mach field** are resolved" for ten meshes, then switched to a drag-adjoint
goal-oriented metric for eight more **[V]**.

The goal-oriented metric is worth naming because it is the other half of the field's answer to
"which variable?": "The resulting metric field essentially consists of **the sum of Hessians of
the RANS fluxes, weighted by the gradient components of the adjoint fields**." **[V]** The
question the mature end of this literature asks is not "where is the gradient big" but "where does
the error in *the number I care about* come from".

### 2b. The element types are simplices, in every adaptive submission I read

HLPW-4 Case 1a: "The Sketch-to-Solution process is used to generate meshes **comprised completely
of tetrahedra**." **[V]** `refine`: "the primary target is linear and curved simplex (triangle and
tetrahedra) meshes" **[V]**. The working group is the *Unstructured* Grid Adaptation Working
Group **[V]**.

### 2c. Where it does meet a structured grid, the shipped rule is: move nodes, never change connectivity

Ansys FENSAP-ICE's OptiGrid offers three adaptation strategies, and the restriction is stated as a
rule rather than a preference: **[V]**

1. "Full" mesh optimization including adding/removing nodes, edge swapping and node movement;
2. "Full - no swapping";
3. "Node movement only" — which "**should only be used with hexahedral grids where nodes cannot be
   added nor deleted**."

Its theory page gives the error estimate ("the error is a direct function of the second derivative
of the solution"; the Hessian's eigenvectors supply the directions) and the node-movement
mechanism: edges at a node are "a network of springs, with stiffness constants proportional to the
edge-based error", solved as an energy minimisation **[V]**.

That page's own publication list cites the paper this lineage rests on, verbatim: **[V]**

> D. Ait-Ali-Yahia et al., "Anisotropic Mesh Adaptation: Towards User-Independent,
> Mesh-Independent and Solver-Independent CFD Solutions: Part II: Structured Grids,"
> *International Journal for Numerical Methods in Fluids*, Vol. 39, pp. 657-674, June 2002.

**[2nd]** The abstract-level claim I could not confirm from the paper's own body is that "the
adaptation operations are restricted to mesh movement in order to avoid the creation of hanging
nodes" and that the method is "sensitive to directional features like shock waves, leading to the
automatic construction of adapted grids where the element edge(s) are strongly aligned with such
flow phenomena". That matches the Ansys manual's restriction exactly, but I read the restriction
in the manual, not the reason in the paper.

**[I]** Put the three facts together — metric in, hexahedral grids get node movement only, nodes
cannot be added or deleted — and the shipped answer for a structured grid is **r-adaptation**: the
same number of nodes, the same connectivity, the same blocks, differently placed. Which is the
sibling of what this repo's `MB_SMOOTH_ITERS` stage already does, with a solution-derived weight
instead of a wall-control function.

### 2d. The variational ancestor, and why it is the same answer

Brackbill & Saltzman, *Adaptive zoning for singular problems in two dimensions*, J. Comput. Phys.
46(3):342–368, 1982 (doi 10.1016/0021-9991(82)90020-1), is the origin of weight-function
r-adaptation in elliptic grid generation: the mesh is generated "by the solution of potential
equations derived by minimizing an integral", and "by choosing `w(x,y)` appropriately, zone size
variation and skewness can be controlled" **[2nd]** — I could not read the paper's body (see
"Gaps"; the NTRS scan is image-only and the JCP text is paywalled). **[I]** The structure of the
method is nonetheless the same as §2c's: a solution-derived scalar enters as a *weight* in a
functional whose unknowns are node POSITIONS. The zoning — how many zones, which is adjacent to
which — is the problem's input, which is what "adaptive zoning" means in the 1982 sense and is not
what "zoning" means in a blocking tool.

---

## 3. Feature detection from a flow field: what each sensor actually uses

### 3a. The four families, and the quantity each one is built on

§L2's table gives the implementations. The design intent behind them is worth stating because it
explains why nobody ships `|∇ρ|`:

- **Jameson pressure switch** — a *normalised second difference*: numerator `Σ(p_j − p_i)`,
  denominator `Σ(p_j + p_i)`. The quantity is dimensionless by construction, bounded, and zero in
  a linear pressure field. **[V]**
- **Ducros** — the point is to *reject* turbulence, not to find gradients. Both SU2 forms put
  vorticity magnitude in the denominator so the sensor collapses wherever `|ω|` dominates `|∇·u|`.
  **[V]** The `FD_DUCROS` form carries the sign: `−(∇·u)/(|∇·u| + |ω|)` fires on COMPRESSION only.
- **Löhner** — "a modified second derivative, normalized by the average of the gradient over one
  computational cell", with an `ε` filter term "preventing refinement of small ripples". **[V]**
- **Lovely & Haimes normal Mach number** — a *physical* criterion rather than a numerical one.
  Harris's thesis states it: "it can be shown that the direction of the shock surface is aligned
  with the **pressure gradient** vector. The normal Mach number is defined as the Mach number in
  the direction of this vector. Since the normal Mach number has a value of at least one just
  before the shock, it can be tested for". **[V]**

### 3b. What `|∇ρ|` fires on, from sources that use it

Harris, *Flow Feature Aligned Mesh Generation and Adaptation*, University of Sheffield PhD thesis
(2013, supervised by Qin, with ARA as the industrial partner), §3.6, is the most useful single
source here because it uses the density gradient **twice**, and both uses are instructive. **[V]**

For supersonic shocks it uses Marcum & Gaither's directed compression sensor —
`f = (V/|V|)·∇ρ`, "the dot product of the normalised velocity vector with the density gradient" —
and then immediately says why that is not enough on its own:

> Note that the extracted data set will also include **any regions of compression that may be
> present at the leading edge of the geometry.** Therefore, to extract only the shock waves, the
> **normal Mach number filter is applied on the reduced data set** to obtain the points
> corresponding to the shock fronts only.

**[V]** The density-gradient filter is a *pre-filter* whose output is handed to a physics-based
filter before anyone believes it.

For **wakes**, the same thesis uses the same quantity, resolved the other way:

> Another method which can be used to extract wakes is to compute the magnitude of some flow
> property **in all directions normal to the velocity vector** … where **the density gradient is
> again chosen as the suitable flow property.**

**[V]** **[I] This is the cleanest available proof that a bare `|∇ρ|` cannot separate the feature
classes:** in one document, by one author, the same field is the shock detector when projected
ALONG the velocity and the wake/shear-layer detector when projected ACROSS it. Strip the
projection and you have a quantity that fires on both.

Contact discontinuities are §L3, from Samtaney, verbatim. **[V]**

Vortices get their own criterion entirely — "the λ2 criterion of Jeong and Hussain is used … found
to be successful for clean extraction of the vortex **even when the farfield mesh is particularly
coarse and not aligned with the vortex core**. Application of this technique will extract **only
the vortex and not the shear layers**" **[V]** — which is a fifth quantity (eigenvalues of
`S² + Ω²`), built because pressure minima alone misidentify vortices: "well-defined pressure
minima can exist in unsteady irrotational motion, which may not correspond to a vortex" **[V]**.

### 3c. Boundary layers and walls

**[2nd]** The most-cited statement that a detector fires inside a boundary layer belongs to
Lovely's own MIT thesis (*Boundary layer and shock detection in CFD solutions*, S.M., MIT Aero &
Astro, 2000): boundary layers can be tagged as a shock because the velocity goes from zero at the
wall to free stream, hence passing through normal Mach number = 1. I could not open that thesis
(see "Gaps"), so I mark the quotation secondhand — note that it is a failure mode of the *normal
Mach* criterion, not of `|∇ρ|`.

**[I] For `|∇ρ|` the boundary-layer response follows from the gas law and standard boundary-layer
structure, not from a source I read.** Across a boundary layer the normal pressure gradient is
negligible, so with `p = ρRT` roughly constant across the layer, `ρ ∝ 1/T`, and a hot wall or an
adiabatic wall at any appreciable Mach number gives a temperature ratio of order unity across a
layer whose thickness is orders of magnitude smaller than the body. The density gradient there is
therefore large by construction. I state this as reasoning; I did not find a primary source that
says it in those words, and it is in "Gaps".

### 3d. Scale and mesh dependence, measured by the tools that correct for it

Fluent multiplies by `(A_cell)^(r/2)` with `r` the "gradient volume weight", default unity, and
documents what the length scale is for: "The length scale is the square (2D) or cube (3D) root of
the cell volume. **Introducing the length scale allows resolution of both strong and weak
disturbances**" **[V]**. FLASH's Löhner estimator divides by a first-difference sum and adds an
`ε` floor, giving a quantity "bounded by [0,1]" **[V]**. `refine` floors the metric eigenvalues
"based on grid size and solution jitter" and clips Hessian eigenvalues to what is valid outside a
discontinuity **[V]**.

**[I]** Three independent codes, three different normalisations, all solving the same problem: the
raw derivative's magnitude is set partly by the mesh that produced it, so a threshold on the raw
value transfers neither between meshes nor between cases. A subprogram that reads `|∇ρ|` off a
*coarse* mesh and thresholds it is reading the quantity at its most mesh-dependent.

---

## 4. Grid alignment to flow features: the line of work that goes from a solve to a block

This is the strand the maintainer's idea actually belongs to. It has a traceable lineage, four
papers long, and it ends at block topology.

### 4a. Marcum & Gaither (1997): features become geometry, the mesh is regenerated

Harris's thesis describes the ancestor: **[V]**

> The earliest form of geometric-representation techniques for aerospace applications was
> described by Marcum and Gaither. A pseudo-pattern recognition technique allowed for extracted
> regions to be **reduced to groups of simple geometric entities**. For example, shock waves and
> wakes are reduced to **lines**, whereas expansion or stagnation regions are reduced to
> **points**. … **Singular points are treated as adaptive sources** which allow for localised
> isotropic refinement … The **lines are embedded dual-sided boundaries** which allow high-aspect
> ratio cells to be generated aligned with the anisotropic features.

and names the general shape of the class:

> Since the flow feature geometry is computed from an initial solution, these techniques usually
> require that **the mesh is regenerated** to obtain the feature-alignment. The solution may then
> continue on this new mesh.

**[V]** (Primary citation: Marcum, D. & Gaither, K., "Solution adaptive unstructured grid
generation using pseudo-pattern recognition techniques", 13th Computational Fluid Dynamics
Conference, 1997, paper 1860 — recorded in two bibliographies I read, not read by me.)

### 4b. Qin & Liu (2006): structured blocks placed around the features, triangles elsewhere

Deng et al. describe it: "Qin and Liu proposed a method to extract flow features based on the
**Hessian matrix** and **high-quality structured quadrilateral mesh blocks are placed around
them**. Employing the Hessian matrix of flow variables, the elements' size, stretching and
orientation is determined. The remainder of the domain is then filled with triangular elements"
**[V]**. Its own abstract describes three stages: "extraction of the flow features; generation of
the **embedded flow feature aligned structured blocks** combined with unstructured grid generation
for the rest of the flowfield; and adaptation of the hybrid grid" **[2nd]** — I read the abstract,
not the IJNME body.

Deng et al. also record its limit: "the method poses a challenge that the extraction of features
is hard to achieve when the flow structures become complex" **[V]**.

### 4c. Harris & Qin (2013–14): the medial axis makes a point cloud into a curve

The thesis's abstract: "A method involving **the medial axis** has been studied to provide a
geometric representation of two-dimensional flow features … These curves are **embedded into the
domain as virtual geometries to force alignment** of unstructured quad-dominant surface mesh
elements. The mesh locally **mimics the attributes of a structured grid**." In 3-D it extrudes
quad surface meshes along the extracted feature direction, "yielding feature-aligned
semi-structured **hex-dominant mesh blocks which can be embedded into the hybrid volume mesh**."
**[V]**

The double-wedge case shows what the medial axis buys: "the medial axis process identifies three
separate branches around a single junction point. **The junction point appears where the shock
waves have intersected.** Three termination points are also identified." **[V]** The topology of
the feature — branches, junctions, terminations — is what comes out, and that is the vocabulary a
blocker can consume.

The thesis also records the cost of running the detector on an unsteady field: "This case actually
highlights one of the issues with using the normal Mach number in that **it can occasionally pick
up structures which are not true shocks.** … the extraction has picked up the **expansion region**
around the corner." **[V]**

### 4d. Deng, Wang & Qin (2023): the feature curves become geometry and a cross field blocks it

The whole chain, as the paper states it, in order: **[V]**

1. An initial structured mesh is produced and solved — "the mesh adaption is not required for
   solving the original flow field".
2. Feature nodes are marked by an edge error estimate `E = ∫₀¹ √((x₂−x₁)ᵀ M(t) (x₂−x₁)) dt`, "where
   `x₁` and `x₂` are two nodes of an edge, and `M` is a symmetric and positive-definite matrix
   obtained from the **Hessian matrix H**. Flow feature nodes are marked when `E` exceeds a
   pre-specified threshold ([0.05, 0.15])" — the test cases use 0.1, and "the threshold value is
   determined by the balance of the feature identification and the numerical noise."
3. The variable in `H` is chosen by regime: "**For this inviscid flow problem, the pressure is used
   as the physical quantity to compute H** to capture the shock feature. **For viscous flows,
   density or the Mach number is used** as a quantity in `H` to capture both inviscid and viscous
   flow features."
4. The marked node set gets a boundary by the **α-shape** technique, a constrained Delaunay
   triangulation, then a medial axis, then branch splitting, recombination and smoothing, giving
   clean feature CURVES.
5. "The flow feature curves are inserted into the initial geometry to regenerate the background
   mesh." Crosses on the feature curves are set tangent to the curve; a crossing node "is divided
   into three corners" so the fast-marching propagation treats it as geometry would.
6. Crosses propagate inward by fast marching, are smoothed, singularities are found by Bunin's
   index formula `k = round(−(2/π)(Δθ₁₂ + Δθ₂₃ + Δθ₃₁))`, and "**the block topology is created by
   connecting the cross-field streamlines to the singularities and corners in the domain**",
   traced by a two-stage Runge-Kutta integration with a collision test between advancing fronts.
7. Convergence: "the number of critical nodes on the flow feature curves, namely the **terminal
   nodes and the crossing nodes**, are measured to determine whether the flow features have
   converged." The loop repeats.

**[V]** on all seven. Note what is and is not in step 6: the blocker's input is *geometry plus
feature curves*. It never sees ρ.

### 4e. Shock fitting: the limit case where the feature IS a boundary

Two shapes, both verified:

- **Structured**: §L5. A solution-derived surface re-places an existing block boundary. The number
  of blocks never changes. **[V]**
- **Unstructured** (Paciorri & Bonfiglioli's shock-fitting): "Each fitted discontinuity is a
  **double-sided internal boundary of zero thickness**", with "a **local re-meshing technique**
  that constructs a time-dependent mesh in which the fitted discontinuities are internal
  boundaries of zero thickness" plus a Rankine-Hugoniot solve for the discontinuity's Lagrangian
  velocity. **[2nd]** — assembled from abstracts and repository landing pages, not from a paper
  body I read; named in "Gaps".

**[I]** The unstructured form is the only published thing I found in which a solution adds a
*boundary that was not previously declared*. It does so by local remeshing of a simplex mesh every
time step, with the jump relations supplying the boundary's motion — not by writing a topology
document, and not on a conforming multiblock grid.

---

## 5. Automatic block decomposition and its inputs

### 5a. What the problem is, in the survey's own words

"The core problem in quad / hex mesh generation is **the placement of mesh singularities** to give
the desired mesh orientation and distribution." **[V]** A singularity is "a node whose adjacent
edges are not four in a quadrilateral grid" (Deng et al.) **[V]**. The survey's thesis is that the
approaches are the same idea in different clothes: "existing approaches (**medial axis, paving /
plastering, cross / frame fields**) are actually alternative views of the same concept" **[V]**,
and "the medial axis is where layers of elements advancing from the boundary collide" **[V]**.

### 5b. Where the field a tool DOES accept gets used

The cross-field route is where a size-and-shape field reaches the topology, and the survey says so
explicitly in the two directions that matter here:

> Note that using midpoint subdivision and IP [integer programming] allows adjustment of **mesh
> size and orientation within a limited range without re-doing the singularity calculation**. …
> Of course the variation in target element size may eventually become so large that the
> singularity is attempting to move out of the primitive, **which could be interpreted as a signal
> that additional singularity pairs are needed**. Using IP on an existing decomposition
> **minimizes changes in mesh topology**, which is important in optimization scenarios.

**[V]** **[I] This is the field's own account of how far a size field is allowed to reach into a
topology, and it is a two-tier answer**: inside a band, the field changes only the division
numbers on the existing blocks' edges; past that band, the mechanism *signals* that the block
structure must change, and the signal is a singularity leaving its primitive — a topological event,
not a threshold on a flow quantity. A reader looking for "how would a field legitimately change a
block count" has here the only published criterion I found, and it is phrased in cross-field terms,
not in solution terms.

QUB's own research page describes the Fogg et al. method's steps — cross field solved on a tri mesh
by fast marching from the boundaries, singularities identified per triangle, "critical cross-field
streamlines are traced from singularities and geometry corners thus partitioning the geometry into
rectangular blocks", with "recent progress … the incorporation of **target input mesh sizes and
directions** in the algorithm" **[2nd]** (the page returned HTTP 403 to my fetch; the wording is
from a search excerpt and the mechanism is independently verified from Deng §4d and the IMR24
paper, both **[V]**).

### 5c. Gmsh specifically, since this repo links it

Gmsh's quasi-structured quad algorithm (`Mesh.Algorithm = 11`) takes a CAD model, computes the
cross field from an initial triangulation with boundary-tangency from the CAD curves, and then does
*topology optimization* in the sense of reducing irregular vertices: "the topology of the mesh is
modified to reduce the number of irregular vertices. The idea is to **preserve the irregular
vertices matching cross-field singularities and to eliminate the others**" **[V]**. Its stated
position on block layouts is a refusal: "we do not have such quadrilateral layout" when discussing
CAD faces of arbitrary topology **[V]**.

**[I]** Gmsh is therefore not a source of a block topology document at all, and the size map it
accepts is used to pick cell sizes and to resolve small CAD features — never to decide where a
singularity belongs beyond what the cross field already says.

### 5d. The summary line

**[I]** Across ICEM, GridPro, Gmsh, CubeCover and the medial-axis/cross-field literature, the
inputs to a block topology are: the geometry; a target element size and shape field; and, in the
dominant interactive route, a human. The solution appears in none of them, and the one proposal to
put it there (§1c) is conditional and 2015.

---

## 6. Two-pass "coarse run first" workflows, and the two things they are not

### 6a. What is shipped

| workflow | first pass | what the second pass produces | mesh kind |
|---|---|---|---|
| `refine` + FUN3D (`ref loop`: "Multiscale metric, adapt, and interpolation") **[V]** | a solve on the current mesh | a metric, then a conforming remesh, then interpolated fields | simplex |
| Cart3D: "fully automated adjoint-driven mesh adaptation for steady simulations" **[V]** | a solve + an adjoint solve | a refined Cartesian cut-cell tree | "topologically unstructured, adaptively refined, Cartesian" |
| Ansys FENSAP-ICE OptiGrid **[V]** | a solve | refine/coarsen + swap + node movement, or node movement only on hex | tet or hex |
| Ansys Fluent gradient adaption **[V]** | a solve | hanging-node refine/coarsen on the existing cells | any |
| Deng/Wang/Qin 2023 **[V]** | a solve on an initial structured mesh | feature curves → new block topology → new structured mesh | multiblock structured |
| DPLR / structured shock fit **[V]** | a solve on the initial grid | the same blocks with `kmax` re-placed | multiblock structured |

HLPW-4's run is the measured example of how many passes "two-pass" really means: eighteen **[V]**.

### 6b. What it is NOT, (i): grid sequencing and multigrid

WIND-US `SEQUENCE`, verbatim: "This option allows the user to, in effect, thin the computational
grid, thus reducing CPU requirements. It can be used to obtain quick starting solutions for the
fine grid. … For one sequencing level, every other grid point is used in the calculation. … at the
end of the run, the solution is interpolated back onto the entire grid." **[V]** The grid is a
given; coarse *levels of it* are a convergence device. Armstrong et al. name the same thing from
the mesh side as a reason to want structured grids at all: "They are eminently suitable for
multigrid acceleration methods, which are more or less obligatory for the efficient solution of
Computational Fluid Dynamics simulations." **[V]**

### 6c. What it is NOT, (ii): a one-shot configuration writer

**[I]** Every row of §6a's table is a loop with a termination test. Deng et al.'s test is the
convergence of the count of terminal and crossing nodes on the feature curves **[V]**; `refine`'s
is a target complexity per level **[V]**; Fluent's is a refine/coarsen threshold pair on a
normalised indicator **[V]**. I found no published or shipped workflow in which one coarse solve
is read once and a final mesh configuration is emitted without a further solve. That absence is an
inference from the six workflows above, not a survey.

---

## 7. What this bears on, for this repo

Stated as inference, because none of these sources was written about this tool. **[I]**

1. **The premise is half right, and the half that is wrong is the output, not the input.** A
   solution field driving a mesh is completely orthodox — it is the whole adaptation literature.
   What no source supports is a solution field driving a *block decomposition directly*. The one
   published chain that reaches a block topology (§4d) inserts a step the proposal skips: the
   solution is first reduced to **CURVES**, and the curves are handed to an ordinary
   geometry-driven blocker. For this repo that step is not an inconvenience — it is the thing that
   makes the idea implementable here at all, because `services/topology_*.py` already takes curves
   and refuses on curves (`topology_preflight.py`). A feature curve is an input those four families
   already understand. A density field is not.

2. **The variable is the wrong one, and the right ones are already in the file.** This repo's
   solver writes `variables = "x", "y", "`r", "u", "v", "T", "p", "M", "vort"` (measured in
   `results/solver/multiblock_tworing_demo/work/xtecp_sol_allztworing.dat`, 2026-11-05) — density,
   **pressure**, **Mach**, and **vorticity**, all of them. Every shipped sensor in §L2 and every
   extractor in §3 is computable from that line without adding a solver output: the Jameson switch
   needs `p` alone; Ducros needs `∇·u` and `vort`; Lovely & Haimes needs `M` and `∇p`; Deng's
   marker needs the Hessian of `p` (inviscid) or `M` (viscous). The proposal selects the one
   variable in that list with published confusers — contacts (§L3), leading-edge compression
   (§3b), wakes and shear layers when resolved across the velocity rather than along it (§3b) —
   and uses it bare, without the normalisation that Fluent, FLASH and `refine` each add for
   different reasons (§3d). **If one line of the design changes, make it this one**: take a
   Hessian of pressure or Mach, not a gradient of density.

3. **A one-shot "solve once, emit the config" is a novel claim, not a reproduction.** §6c: every
   workflow I found loops, and the two with a published termination test terminate on something
   measured about the *features* (critical-node count) or about the *mesh* (target complexity),
   never on "the first solve finished". A novice-facing subprogram that writes a topology from one
   coarse solve would be claiming something the literature does not. If it ships, the claim it
   makes to the user should be "a starting topology, to be looked at", and the design note should
   say which published workflow it is NOT.

4. **The conservative version is production practice, it fits a family this repo already has, and
   it is probably the right first increment.** DPLR's structured shock fit (§L5) moves one
   already-declared boundary onto a Mach iso-surface, changing no block count and no connectivity.
   This repo's two-ring O-grid already has a middle ring that **nobody drew** — it is the body
   offset through `services/geometry_offset.py`, carrying a `models/derived_geometry.py` record of
   where it came from (`examples/topology/tworing_offset.json`,
   `config/pipeline/tworing_offset_demo.json`). A solution-derived seam curve would enter at
   exactly that seam, as another kind of derived geometry with a provenance record, and the family
   would not need to know it came from a solve. That is a strictly smaller change than a new
   solution-to-topology subsystem and it reuses the one mechanism in this repo that already
   answers "where did this curve come from".

5. **If the ambitious version is wanted anyway, the published recipe is specific and the gap in
   this repo is nameable.** Steps 1–3 of §4d (solve, mark nodes by a Hessian-based edge error,
   threshold) are a small amount of code over data this repo already has. Step 4 (α-shape →
   constrained Delaunay → medial axis → branch split/recombine/smooth) is the substantial piece and
   is where Harris's thesis and Deng's paper both put their effort. Step 6 (cross field → fast
   marching → singularity index → streamline tracing) is an **automatic blocker this repo does not
   have and has never needed**, because its four families are hand-written topology generators
   rather than a general solver. **[I]** Without step 6, the extracted curves have nowhere to go
   except into a hand-written family — which is a real and much cheaper option (a curve becomes an
   `interface` edge in an existing family's declaration), and is a different, smaller feature than
   the one proposed.

6. **A warning the sources make specific.** `|∇ρ|` is largest exactly where this mesher's wall
   clustering is already finest. §3c's reasoning puts a large density gradient across every
   boundary layer at any appreciable Mach number; §3b shows the same quantity is the published
   *wake* detector. **[I]** A partitioner driven by `|∇ρ|` on an aerofoil case would therefore
   propose its densest partitioning along the wall and through the wake — which is where this
   repo's families already put their blocks, from geometry, for free. The novice would be told the
   flow discovered a structure the geometry had already determined, which is worse than no feature
   at all.

---

## Gaps I could not close, by name

1. **Ait-Ali-Yahia et al., IJNMF Part II: Structured Grids (2002), the paper body.** Paywalled at
   Wiley; the McGill eScholarship copy I located was a different document. §2c's claims about that
   paper are **[2nd]** from abstract text; the *restriction* they describe I verified independently
   in Ansys's own OptiGrid manual, but the *reason* ("to avoid the creation of hanging nodes") I
   did not read in the source that owns it.
2. **Qin & Liu, IJNME 67(6):787–814 (2006), the paper body.** Paywalled. Everything §4b says about
   it comes from Deng et al.'s and Armstrong et al.'s descriptions plus the published abstract. In
   particular I could not check **what shape its "embedded structured blocks" actually are** —
   whether they conform to the surrounding unstructured mesh or overlap it — which is the single
   most load-bearing unknown for this note's subject.
3. **Brackbill & Saltzman, JCP 46(3):342–368 (1982).** The NTRS copy (19810006187) is a JBIG2 scan
   with no text layer and the JCP text is paywalled. §2d's description of the weight function is
   **[2nd]**; I never saw the functional. Brackbill's 1993 "An adaptive grid with directional
   control" (JCP 108:38–50) — the one that would bear directly on "a density gradient supplies a
   direction as well as a magnitude" — I did not reach at all.
4. **Lovely's MIT thesis (1721.1/80619) and Lovely & Haimes, AIAA 99-3285.** The DSpace bitstream
   URL I extracted returned HTML rather than the PDF, and the AIAA paper is paywalled. §3c's
   boundary-layer statement is therefore **[2nd]**; the normal-Mach definition itself I verified
   from Harris's thesis instead, which is a user of the method rather than its author.
5. **A primary source saying `|∇ρ|` fires inside a boundary layer.** I reasoned it from the gas law
   in §3c and marked it **[I]**. If this matters to a decision, it is cheap to MEASURE on this
   repo's own output: `xtecp_sol_all*.dat` carries `` `r `` and `p` on the same nodes, so the
   claim is one script away from being **[V]**, measured.
6. **Paciorri & Bonfiglioli's shock-fitting papers' bodies.** §4e's unstructured row is **[2nd]**
   from abstracts and repository landing pages. The specific thing I could not check is whether any
   of their work has ever been done on a *block-structured* grid rather than a simplex one.
7. **GridPro's `User_Guide_for_TIL` and `WS_GUI_Manual`, and ANSA's HEXABLOCK manual.** Both behind
   registration (GridPro: a HubSpot form; BETA CAE: a customer account). GridPro's FAQ answers my
   question only indirectly, and ANSA I could not answer at all — it is the one automatic blocker
   in the brief's list on which I have nothing. This gap is inherited from
   `cell-size-range-within-a-block.md` gap 1, unchanged.
8. **Fidelity Pointwise on this question.** `cadence.com` and `pointwise.com` still answer HTTP 403
   to a non-browser request, and the 2023 archive capture used by the sibling note does not cover
   adaptation. Whether Pointwise accepts a solution file at all is unknown to me.
9. **Whether anyone implemented Armstrong et al.'s §1c proposal.** I found the proposal (2015,
   conditional) and I found a different route to the same destination (2023, §4d). I did not find
   the straight line between them — a cross-field blocker whose target metric is a solution-derived
   Hessian metric on a CFD case. Fogg's 2014 QUB thesis and Fogg/Armstrong/Robinson IJNME 101(13)
   are the two places it would be, and I read neither body.
10. **The AIAA Mesh Adaptation Workshop as a standalone entity.** I could not find one. What exists
    and what I read is the **Mesh Adaptation Technical Focus Group** inside HLPW-4/GMGW-3 and
    HLPW-5; the HLPW-5 one-page summaries now 302-redirect to a NASA landing page. §2b's "every
    adaptive submission is simplex" therefore rests on HLPW-4's Case 1a paper and on `refine`'s own
    scope statement, not on a complete participant roster.
11. **Whether metric-based adaptation has ever been run on a point-matched MULTIBLOCK grid.** I
    found it on hexahedral grids as node movement only (§2c) and I found the simplex practice. The
    specific combination — a metric field conformed to by a *multiblock* grid with its interface
    constraints — I found nowhere, and that absence is **[I]**, from not finding it rather than
    from anyone saying it does not exist.

---

## Sources

Primary, read by me:

- NASA `refine`, `nasa/refine@master`: `README.md` (scope, `ref multiscale`, `ref loop`),
  `src/ref_metric.c` (`ref_metric_lp:2239`, `ref_metric_local_scale:2583`,
  `ref_metric_hessian_filter:909`, `ref_metric_interpolation_error:992` with its
  "Corollary 3.4 CONTINUOUS MESH FRAMEWORK PART I DOI:10.1137/090754078" comment,
  `ref_metric_gradation_at_complexity:1067`), `src/ref_subcommand.c` (the `--interpolant` help at
  `:234`, the scalar computation at `:2405`). https://github.com/nasa/refine
- Unstructured Grid Adaptation Working Group — https://ugawg.github.io/
- Wood, S. L. & Park, M. A., *FUN3D Mesh Adaptation Simulations of 4th AIAA High-Lift Prediction
  Workshop Case 1a*, NTRS 20220007063 —
  https://ntrs.nasa.gov/api/citations/20220007063/downloads/hlpw4_aviation_2022_strives_3.pdf
- McCloud, P. L., *Best Practices for Unstructured Grid Shock Fitting*, NTRS 20160009327, §II and
  §III.A — https://ntrs.nasa.gov/api/citations/20160009327/downloads/20160009327.pdf
- Samtaney, R., *Visualization, extraction and quantification of discontinuities in compressible
  flows*, NTRS 20000068998, §2 variable recommendations —
  https://ntrs.nasa.gov/api/citations/20000068998/downloads/20000068998.pdf
- SU2, `su2code/SU2@master`: `SU2_CFD/src/solvers/CEulerSolver.cpp`
  (`SetCentered_Dissipation_Sensor:2432`, `SetUpwind_Ducros_Sensor:2446`),
  `SU2_CFD/include/solvers/CFVMFlowSolverBase.hpp` (`SetCentered_Dissipation_Sensor_impl:773`,
  the Jameson switch and the MSW variant). https://github.com/su2code/SU2
- FLASH4 User's Guide §8.6.3.1 "Refinement Criteria" (Löhner's estimator, the `ε` filter, "FLASH4
  does not define any refinement variables by default") —
  https://flash.rochester.edu/site/flashcode/user_support/flash4_ug_4p62/node59.html
- ANSYS FLUENT 12.0 Theory Guide §19.3.1 (the `(A_cell)^(r/2)|∇f|` / `(A_cell)^(r/2)|∇²f|`
  formulas, the volume weight, Standard/Scale/Normalize) and User's Guide §27.3.1 (Gradient vs
  Curvature vs Iso-Value, "Select the required solution variable in the Gradients of drop-down
  list"), on ENEA's mirror of the vendor text —
  https://www.afs.enea.it/project/neptunius/docs/fluent/html/th/node395.htm and
  https://www.afs.enea.it/project/neptunius/docs/fluent/html/ug/node848.htm ,
  https://www.afs.enea.it/project/neptunius/docs/fluent/html/ug/node1379.htm
- Ansys FENSAP-ICE manual, 2024 R2 public views: §12.1 Theoretical Background (second-derivative
  error, the Hessian's eigenvectors, the spring-analogy node movement), §12.4 Adaptation Strategy
  ("Node movement only … should only be used with hexahedral grids where nodes cannot be added nor
  deleted"), §22.1 Journal Publications in Mesh Adaptation (the Ait-Ali-Yahia Part II citation) —
  https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/fensap_manual/section_ac5_f4f_2w.html ,
  `.../section_cd5_f4f_2w.html` , `.../section_q5v_j4f_2w.html`
- Ansys ICEM CFD Help Manual, 2025 R2 public view, Initialize Blocks ("geometry connectivity
  translates into blocking connectivity"; the 3D Bounding Box / 2D Planar / 2D Surface Blocking /
  3D Multizone types) —
  https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/icm_help/iblock_initblock.html
- Gmsh reference manual, texinfo build: `Mesh.Algorithm` ("11: Quasi-structured Quad"),
  `Mesh.QuadqsSizemapMethod`, `Mesh.QuadqsTopologyOptimizationMethods`,
  `Mesh.QuadqsRemeshingBoldness`, `Mesh.QuadqsScalingOnTriangulation` —
  https://gmsh.info/doc/texinfo/gmsh.txt
- Reberol, M., Georgiadis, C. & Remacle, J.-F., *Quasi-structured quadrilateral meshing in Gmsh —
  a robust pipeline for complex CAD models*, arXiv 2103.04652 (paper body: the CAD-only input, the
  cross field from the triangulation with CAD-curve boundary alignment, the size map, "we do not
  have such quadrilateral layout") — https://arxiv.org/abs/2103.04652 ,
  https://ar5iv.labs.arxiv.org/html/2103.04652
- Armstrong, C. G., Fogg, H. J., Tierney, C. M. & Robinson, T. T., *Common themes in multi-block
  structured quad/hex mesh generation*, Procedia Engineering (IMR24), 2015 — the singularity-
  placement thesis, the solution-alignment goal sentence, the "It should therefore be possible to
  …" proposal, "The conventional approach to multi-blocking hex meshing is to manually define a
  block topology", and the midpoint-subdivision/integer-programming passage on how far a size
  change reaches before a singularity leaves its primitive —
  https://www.sandia.gov/imr/2015%20IMR%20Papers/06.pdf
- Deng, S., Wang, Y. & Qin, N., *Cross-field structured adaptive mesh using medial axis flow
  feature extraction*, AIAA Journal, 2023, doi 10.2514/1.j063346 — accepted version, CC-BY:
  §I (prior art and the manual-blocking hurdle), §III.A (the flow chart and the five steps),
  §III.B (Eq. 2 and the pressure/density/Mach choice, Algorithm 1), §III.C (the cross-field
  propagation, Bunin's index Eq. 6, streamline tracing, "The flow feature curves are inserted into
  the initial geometry"), §V (conclusion and the 3-D extension) —
  https://eprints.whiterose.ac.uk/204784/1/AIAAJ_SDeng_YWang_NQin_7Sep2023.pdf
- Harris, M. J., *Flow Feature Aligned Mesh Generation and Adaptation*, PhD thesis, University of
  Sheffield, April 2013 (supervisor N. Qin) — Abstract; §2.4 (Marcum & Gaither, Ito et al., and
  "the mesh is regenerated to obtain the feature-alignment"); §3.6 (the transonic and supersonic
  shock extraction, `(V/|V|)·∇ρ`, the leading-edge compression caveat, the two wake extractors,
  λ₂); §4.4 (the double wedge, medial axis branches and junction points); §4.6 (the normal Mach
  number picking up an expansion region) —
  https://etheses.whiterose.ac.uk/id/eprint/4192/1/MJH_FlowFeatureAlignedMeshGen.pdf
- Nieser, M., Reitebuch, U. & Polthier, K., *CubeCover — Parameterization of 3D Volumes*, 2011 —
  "The input of CUBECOVER is a tetrahedral volume mesh. First, a frame field is designed with
  manual input from …" —
  https://opus4.kobv.de/opus4-matheon/files/831/2011_Nieser-Reitebuch-Polthier_CubeCover.pdf
- GridPro, *Frequently Asked Questions* (v10), answers T31, G19, G29, G41, G54 —
  `https://22821077.fs1.hubspotusercontent-na1.net/hubfs/22821077/Version 10 documents/FAQs.pdf`
- NASA Cart3D product page (adjoint-weighted-residual output-based adaptation; "topologically
  unstructured, adaptively refined, Cartesian meshes") —
  https://www.nas.nasa.gov/software/cart3d.html
- NASA WIND-US 3.0 keyword reference, `SEQUENCE` —
  https://www.grc.nasa.gov/WWW/winddocs/windus3.0/user/keywords/sequence.html

Cited but read only as abstract, bibliography entry or landing page (**[2nd]** in the text):

- Ait-Ali-Yahia, D., Baruzzi, G., Habashi, W. G., Fortin, M., Dompierre, J. & Vallet, M.-G.,
  *Anisotropic Mesh Adaptation … Part II: Structured Grids*, IJNMF 39:657–674, 2002,
  doi 10.1002/fld.356
- Qin, N. & Liu, X., *Flow feature aligned grid adaptation*, IJNME 67(6):787–814, 2006,
  doi 10.1002/nme.1648
- Brackbill, J. U. & Saltzman, J., *Adaptive zoning for singular problems in two dimensions*,
  JCP 46(3):342–368, 1982, doi 10.1016/0021-9991(82)90020-1
- Marcum, D. & Gaither, K., *Solution adaptive unstructured grid generation using pseudo-pattern
  recognition techniques*, AIAA 97-1860, 13th CFD Conference, 1997
- Lovely, D. & Haimes, R., *Shock detection from computational fluid dynamics results*,
  AIAA 99-3285; and Lovely, D., *Boundary layer and shock detection in CFD solutions*, S.M. thesis,
  MIT Aero & Astro, 2000 — https://dspace.mit.edu/handle/1721.1/80619
- Fogg, H. J., Armstrong, C. G. & Robinson, T. T., *Automatic generation of multiblock
  decompositions of surfaces*, IJNME 101(13):965–991, 2015; and Fogg, H. J., *Automatic generation
  of multiblock decompositions for meshing*, PhD thesis, Queen's University Belfast, 2014 —
  QUB Finite Element Modelling Group page (HTTP 403 to a non-browser fetch):
  https://www.qub.ac.uk/research-centres/FiniteElementModellingGroup/ResearchTopics/Meshgeneration/AutomaticMulti-BlockDecompositionusingCrossFields
- Price, M. A., Armstrong, C. G. & Sabin, M. A., *Hexahedral mesh generation by medial surface
  subdivision*, Parts I and II, IJNME 38(19):3335–3359 (1995) and 40(1):111–136 (1997)
- Ducros, F. et al., *Large-eddy simulation of the shock/turbulence interaction*, JCP, 1999
- Jeong, J. & Hussain, F., *On the identification of a vortex*, JFM, 1995
- Paciorri, R. & Bonfiglioli, A., unstructured shock-fitting (several papers, 2009–2021)
- BETA CAE ANSA v13.1 announcements (the existence of the HEXABLOCK module) —
  https://www.beta-cae.com/news/20100823_announcement_ansa_v13.1_for_CFD.pdf

In this repo:

- `docs/research/multi-element-airfoil-blocking.md` — named topology families, where block corners
  go, wake cuts, element-to-element interfaces, and the published growth-rate and block-count
  figures. Not restated here.
- `docs/research/cell-size-range-within-a-block.md` — within-block size range, how production
  generators let an edge distribution be set, GridPro's distribution behaviour, and the Pointwise
  403 that this note inherits. Not restated here.
- `tools/PreProcessor/gui/app/services/topology_model.py` (the four families and the registry that
  refuses a family with no pre-flight), `topology_preflight.py` (a refusal carries the curve),
  `topology_{hgrid,ogrid,cgrid,tworing}.py`.
- `tools/PreProcessor/gui/app/services/geometry_offset.py` and
  `tools/PreProcessor/gui/app/models/derived_geometry.py` — the existing mechanism for a curve
  nobody drew, with a record of where it came from. §7.4's proposed seam.
- `examples/topology/tworing_offset.json`, `config/pipeline/tworing_offset_demo.json` — the shipped
  case whose middle ring is computed rather than drawn.
- `results/solver/multiblock_tworing_demo/work/xtecp_sol_allztworing.dat` — the variables line
  measured in §7.2 (`"x", "y", "`r", "u", "v", "T", "p", "M", "vort"`), 2026-11-05.
