# Arc-length correspondence on an offset ring

**This file establishes `docs/research/` — a RESEARCH NOTE, not a rule and not a rationale.**
Not `.claude/rules/*.md` (what the rule is), not `docs/design_notes/` (why a shipped rule was
chosen). It records what an outside literature check and a fresh measurement say about a
question the repo has already answered once, so a future decision can be argued from sources
rather than memory. Nothing here is binding; no rule, gate, test or source file was changed to
write it. 2026-09-30, against #154.

**Subject.** `docs/design_notes/mesher.md:4176` ("AN OFFSET-DERIVED MIDDLE RING, AND WHAT ARC
LENGTH COSTS") records that the two-ring O-grid on a 2:1 ellipse achieves a worst relative
wall first-cell error of **0.070625 unsmoothed**, against **0.003779** for a single ring at an
identical budget, and diagnoses it as a consequence of `follows` placing nodes by arc length
on a constant-distance offset. This note checks that diagnosis, the "cannot be fixed by
resampling" conclusion beside it, and what the grid-generation literature does instead.

## How to read the markers

- **[V]** verified in a primary source I read myself (source code, official docs, or the text
  of the book/paper), or measured by me in this repo.
- **[I]** my own inference or derivation from a **[V]** fact. Stated as reasoning, not as fact.
- **[2nd]** I could only find this secondhand. Treat as unconfirmed.

---

## Lead: the two answers a reader needs first

### Q1 — The diagnosis holds, and it is sharper than the note states.

**[V]** The relation is the standard *parallel curve* (offset curve) arc-length relation. For a
regular plane curve `p(s)` with unit tangent `t`, unit normal `n` and signed curvature `κ(s)`,
the offset at distance `d` is `q(s) = p(s) + d·n(s)`; by the Frenet equations `dq/ds =
(1 + d·κ)·t`, so `ds_offset = (1 + d·κ)·ds`. Integrating, the offset arc length from the
common start to the normal foot of body arc `s` is

```
    s_offset(s) = s + d · θ(s)          θ(s) = ∫₀ˢ κ(σ) dσ  = the tangent's turning angle
```

and for a closed convex generator `θ_total = 2π`, giving `L_offset = L_body + 2π·d` — Steiner's
formula. Equal *normalized* arc fraction on the two curves therefore equals normal
correspondence **iff `s_offset(s)` is linear in `s`, iff `κ` is constant, iff the generator is a
circle (or a straight line)**. That is exactly what the design note says.

I verified the relation numerically on the shipped files rather than trusting it: the ellipse
quadrant in `examples/geometries/ellipse_body.dat` has arc length 0.605521 and
`examples/geometries/ellipse_offset.dat` has 0.998240, against `L_body + 2π·d/4 = 0.998220`
— agreement to 2.0e-05, which is the miter's own excess that
`tools/PreProcessor/gui/app/services/geometry_offset.py` derives in its docstring. **[V]**

Primary sources: the offset-curve literature's own survey, Farouki & Neff, *Analytic
properties of plane offset curves*, **Computer Aided Geometric Design 7 (1990) 83–99**, whose
abstract states that "in the absence of irregular points, simple relations between certain
global properties of the generator and offset curves, such as their arc length … may be
derived" and that a one-to-one correspondence between characteristic points on the generator
and its offsets exists at each distance `d`
(https://research.ibm.com/publications/analytic-properties-of-plane-offset-curves). **I read
the abstract, not the body — the explicit `(1 + d·κ)` formula is [2nd] from that paper and
[V] from my own Frenet derivation plus the numeric check above.**

**Sharpening.** The note says the error is "the first cell measured normal to the wall". That
is not what the repo's ruler measures: `src/MbQuality.cpp:257-320` steps **one grid line
inward** and measures `|node(k,1) − node(k,0)|`, the length of the first radial *step*, not its
perpendicular component. The mechanism is therefore simpler than tilting: node `k` of the seam
is not the normal foot of node `k` of the body, so the chord from wall node `k` to seam node
`k` is **longer than the ring thickness**, and the first interior row — at a fixed fraction of
that chord — is proportionally too far out. Measured by me on the shipped quadrant:
`|seam_k − wall_k|` runs 0.250001 … 0.267691 against `d = 0.25`, a **maximum stretch of
0.070766** against the report's 0.070625. **[V]** They agree to 1.4e-04, so the stretch of the
chord *is* the error, to within the tanh law's own nonlinearity.

**What this is called.** I could not find a standard name for this failure mode in the
grid-generation literature (see "Gaps"). The nearest named things are all one level up:
Thompson, Warsi & Mastin call the governing obstruction **over-specification of the boundary
point distribution** (below), and the *curve* relation is the **parallel/offset curve** arc
relation. "Arc-length correspondence" is my own phrase, not a term of art.

### Q5 — Yes, a small change exists. Two of them, and they are different sizes.

**The smallest change that needs no new subsystem and no new key** is not in the path
resolution at all — it is in the **fill**. `src/MultiBlock.cpp:1483` interpolates the
wall-to-seam direction with the **linear** term `west[j]·(1−u) + east[j]·u`. Thompson, Warsi &
Mastin's Chapter VIII, §1.B, states the alternative in as many words: replacing the linear
Lagrange blend with a **Hermite** blend whose boundary derivative is set along the wall normal
makes the grid orthogonal at the boundary with a declared off-wall spacing, and "since all the
quantities … can be evaluated from the points on the boundary, it remains only to specify the
spacing, Δsᵢ, off the boundary and to use Eq. (7) for r_ξᵢ on the boundary in the Hermite
expressions." **[V]** (text below). Everything that needs is already in hand: the wall
polyline gives `n̂`, and `MbWallSpec` already carries the requested height. `follows`,
`binding` and #151's shared path resolution are untouched — the seam still supplies the
outer curve; it just stops dictating the near-wall direction.

Cost, stated honestly: the Hermite condition is exact only to first order in the first
interval **[I]** (the first interior node is `w + u₁·T₀ + O(u₁²)`), it changes every existing
`MESH_MODE 1` mesh and so moves the whole golden set, and it adds a second answer to "what
does the fill do at a wall" beside the smoother's control functions, which already answer it
exactly.

**The change that is smaller still, and is the one the evidence points at, is to do nothing.**
This repo already implements the canonical repair, in the canonical place. TWM Chapter VI §2F
describes iteratively adjusting elliptic control functions "until not only a specified line
slope but also the spacing of the first coordinate surface off the boundary is achieved, with
the point locations on the boundary specified", after which "the coordinate lines
[intersect] the boundary normally at fixed locations and with the specified spacing"; and the
same chapter says the algebraic/transfinite grid is the *initial guess* for that solve, not
the deliverable. **[V]** `.claude/rules/mesher-smoothing.md:163` is that mechanism, solved
exactly for `|update − p_wall| = requested` at the first interior row. It takes 0.070625 to
**0.000000** at the shipped default. By the textbook's own framing, the unsmoothed number is
a property of an initial guess.

**A third option costs no code at all and is worth knowing:** the error is interior to each
declared edge, because the `m*` corners sit at the same point indices as the `b*` corners and
so **are** normal-correspondent by construction (`examples/topology/tworing_offset.json`, and
`geometry_offset.py`'s one-point-per-source-point rule). Declaring more corners around the
ring shrinks it quadratically. Measured by me at a fixed 96 nodes around: 4 edges per ring
0.070625, 6 → 0.035103, 8 → 0.018242, 12 → 0.005694, 16 → 0.002102, 24 → 0.000264. **[V]**

**What no small change can do** is make the *declared* seam distribution and the *declared*
wall distribution both arc-uniform and the radials normal. That is over-determined, and the
primary source says so (§4 below).

---

## 1. The mechanism, reproduced independently

I re-implemented `discretise` → `spacingAlong` → `arcFraction` → `coons`
(`src/MultiBlock.cpp:828`, `:881`, `:1456`, `:1483`) and `Spacing::generateTanhStart` /
`solveTanhStartDelta` (`tools/PreProcessor/include/Spacing.hpp:130`, `:143`) in ~90 lines of
Python, fed it the *shipped* geometry files, and measured `|p(k,1) − p(k,0)|` the way
`src/MbQuality.cpp:289` does. Offsets at other distances came from the real service,
`app.services.geometry_offset.offset_points`. **[V]**

| ring thickness `d` | repo's figure (design note) | my replication | with the normal-foot remap of §4 |
|---|---|---|---|
| 0.05 | 0.103051 | **0.103051** | 0.000198 |
| 0.10 | 0.092325 | **0.092325** | 0.000198 |
| 0.15 | 0.083931 | **0.083931** | 0.000198 |
| 0.25 | 0.070625 | **0.070625** | 0.000198 |

All four reproduce to six decimals, so the effect is fully explained by the fill and the two
edge distributions — no other stage contributes. The remapped residue is **constant in `d`**
and sits at the same order as #153's circle (0.000171), i.e. it is the body's 120-facet
faceting and nothing else — which is what `.claude/rules/mesher-multiblock.md:555` ("Nothing
projects onto an ANALYTIC curve") predicts. **[V]**

The tangential slip that causes it is large: on the shipped quadrant the equal-arc-fraction
seam node is up to **0.1172 of arc** away from the normal foot, on a 0.9982-long seam edge —
**11.7% of the edge**. **[V]**

---

## 2. What other structured generators actually do

### Gmsh — the same scheme as this repo, and it does not correct it. **[V]**

`src/mesh/meshGFaceTransfinite.cpp` (read at `live-clones/gmsh@master`) computes the blending
coordinates as accumulated node spacing along the boundary, **averaged over the two opposing
sides**:

```c
// use the average of the node spacing on the two opposing sides, so that we
// generate the same u, v coordinates whatever the ordering of the sides
    L_i += 0.5 * (d1 + d2);
    ...
    double u = lengths_i[i] / L_i;
```

That is `arcFraction` at `src/MultiBlock.cpp:1456`, rule for rule — including the averaging of
the facing curves. The *correspondence* between a node on one side and a node on the opposite
side is purely by **index** (`tab[i][0] = m_vertices[i]`, `tab[i][H] = m_vertices[2L+H−i]`).
So the answer to "does anyone solve this by arc-length correspondence between two given
curves" is **yes — Gmsh, in its main structured mesher, and it applies no correction.** The
official manual's own description is "a transfinite interpolation algorithm in the parametric
plane of the surface to connect the nodes on the boundary using a structured grid"
(https://gmsh.info/doc/texinfo/gmsh.html, tutorial `t6`). **[V]**

Gmsh's answer for a boundary layer is a different mechanism entirely: `src/mesh/BoundaryLayers.cpp`
builds it by **extrusion along accumulated/Gouraud-averaged node normals**
(`ExtrudeParams::normals[...]->add(...)`), not by interpolating to a given outer curve. **[V]**

### pyHyp / Chan & Steger — the outer boundary is a result, not an input. **[V]**

pyHyp's own docs (`doc/index.rst`, read from `mdolab/pyhyp@main`): "start with an initial
surface (or curve) … and then *grow* or *extrude* the mesh in successive layers until it
reaches a sufficient distance". Theory: "Most of the theory for pyHyp was taken from Chan and
Steger" — R. L. Chan & J. L. Steger, *Enhancements of a three-dimensional hyperbolic grid
generation scheme*, **Applied Mathematics and Computation 51 (1992) 181–205** (the pyHyp docs
link https://www.sciencedirect.com/science/article/pii/009630039290073A; I could not read the
paper body — ScienceDirect returned 403 — so its equations are **[2nd]** via pyHyp and TWM).

What it takes (`doc/options.yaml`): `s0` "Initial off-wall (normal) spacing of grid. This is
taken to be constant across the entire geometry", `N` levels, `marchDist`. **There is no outer
curve input at all.** What it costs: a PETSc Krylov solve per step (`KSPRelTol`, `KSPMaxIts`,
`KSPSubspaceSize`), a CFL-type step limiter `cMax`, explicit/implicit smoothing `epsE`/`epsI`,
a Kinsey–Barth term `theta`, and point-Jacobi volume smoothing. What it refuses: an outer
boundary you specify. And it states the tension directly — **`epsE`: "Increasing the explicit
smoothing may result in a smoother grid, at the expense of orthogonality"**, with `slExp`
scaling that smoothing "low near the wall to maintain orthogonality and high away from the
wall to prevent crossing of grid lines in concave regions". **[V]**

### construct2d — both engines, and both **re-impose** the wall spacing afterwards. **[V]**

From the user manual (`doc/user_manual.pdf`, `cpraveen/construct2d@master`, text extracted by
me): "**In hyperbolic grid generation, the airfoil surface is marched outwards and the
farfield boundary cannot be specified beforehand.** In elliptic grid generation, both the
airfoil surface and farfield boundary are specified ahead of time, an initial algebraic grid
is generated, and then the elliptic solver smooths this grid iteratively." Hyperbolic is the
default, "orders of magnitude faster and tends to be able to generate grids with lower skew".

Its elliptic path is the most directly relevant thing I found:

- `src/elliptic_surface_grid.f90:26-30` — "Generates algebraic grid. Surface and farfield
  points connected by splines **that are tangent to the surface normals, ensuring
  orthogonality at the surface**. Spacings not yet applied in eta-direction; done after
  smoothing." The body (`:69-73`) builds a quadratic B-spline per `i` whose middle control
  point is `p(i,1) + 0.5·n̂(i)` — i.e. the line **leaves along the wall normal** regardless of
  where the outer curve's node `i` sits.
- Then `surface_util.f90:404-454` `apply_normal_spacing` re-distributes nodes **along each
  existing eta-line** by cumulative arc length with a geometric growth solved for `y0`.
- Then more smoothing, and (manual) "then the point spacings are **reinforced again**".

Its hyperbolic path does the same: "Finally, point spacings are **reapplied** to the grid to
ensure the correct value of YPLS is present everywhere." So neither engine trusts its solver
to hold the wall spacing; both impose it as a 1-D redistribution afterwards. And its
`NRMT`/`NRMB` options record the other side of the tension: "Generally, a grid that is normal
to the surface is desirable, but sometimes enforcing this normal condition near the trailing
edge results in higher skew elsewhere." **[V]**

### OpenFOAM — displacement, not interpolation. **[V as documentation, [2nd] as implementation]**

`snappyHexMesh` layer addition shrinks the existing mesh (`displacementMedialAxis` by default,
or a `displacementMotionSolver` using a Laplacian/stress solve) and inserts layers into the gap
(https://doc.openfoam.com/2312/tools/pre-processing/mesh/generation/snappyhexmesh/layers/). Of
`expansionRatio`, `finalLayerThickness`, `firstLayerThickness`, `thickness`, exactly two may be
given; `minThickness` causes layers to be **dropped** rather than distorted where they will not
fit. There is no second surface to correspond to at all. I read the docs page, not the source.

### Thompson, Warsi & Mastin — the family that actually matches this case is **parabolic**. **[V]**

The book is freely readable as PostScript at
https://polyakov.imamod.ru/arc/books/MESH_GEN_1/index.html; I extracted and read Chapters VI,
VII, VIII and IX. Chapter VII opens:

> "In neither case can the entire boundaries of a general region be specified — only the
> elliptic equations allow that. **The parabolic system can be applied to generate the grid
> between the two boundaries of a doubly-connected region with each of these boundaries
> specified.** The hyperbolic case, however, allows only one boundary to be specified, and is
> therefore of interest only for use in calculation on physically unbounded regions where the
> precise location of a computational outer boundary is not important."

A body, a seam, and a ring between them **is** a doubly-connected region with both boundaries
specified. Parabolic generation is the named family for it: it marches from the wall (so the
near-wall lines are near-orthogonal by construction) while retaining "some influence of the
other boundary toward which the marching progresses". Its cost, per the same chapter: "The
forms of the forward value specification, and of the control functions, have not yet been
well-developed" (1985), and "Orthogonality is not achieved as directly as with the hyperbolic
system."

Chapter VII also names hyperbolic marching's price: "it is only the volume, and not the
spacing in the two separate coordinate directions, that is controlled", "boundary slope
discontinuities are propagated into the field", and "it is possible for very unsuitable grids
to result", against "faster than the elliptic generation systems by one or two orders of
magnitude".

### CGNS, HYPGEN / Chimera Grid Tools — not reached. See "Gaps".

---

## 3. The families of fix, and what each costs

**(a) Hyperbolic / normal marching — generate the seam instead of being given it.**
Cost: **[V]** you lose the ability to specify the outer boundary (TWM Ch. VII; construct2d
`SLVR`; pyHyp has no outer-curve input) — which in this repo means the seam stops being a
declared `follows` edge, so #151's whole mechanism has nothing to do and the ring thickness
stops being a number a user wrote down. It also imports a marching stability budget (`cMax`,
`epsE`, `epsI`, `theta`, volume smoothing in pyHyp; `ALFA`, `EPSI`, `EPSE`, `ASMT` in
construct2d). It buys orthogonality and the exact off-wall spacing directly. **Refused here on
its own terms**: a two-ring O-grid exists so that the seam is *declared*.

**(b) Explicit point-to-point correspondence — distribute one edge, place the other at the
normal feet.** This is construct2d's `algebraic_grid` in spirit and it is exactly the remap of
§4. Cost: **[V]** the second edge's own declared spacing law stops being honoured (it becomes
a function of the first edge's), and the two edges must be told which is which — a new
relation between edges that #151's document format does not have. In this repo the seam is
also FROZEN during smoothing (`.claude/rules/mesher-smoothing.md:58`), so a remapped seam
would be the final one.

**(c) Elliptic smoothing with boundary control functions — what this repo already does.**
**A repair, not a crutch, and the primary source is unambiguous.** TWM Chapter VI:

> "The second-order systems allow the specification of either the point distribution on the
> boundary (Dirichlet problem) or the coordinate line slope at the boundary (Neumann problem)
> **but not both**. Thus it is not possible with such systems to generate grids which are
> orthogonal at the boundary with specified point distribution thereon. (This assumes that the
> control functions are specified. **It is possible to adjust the control functions to achieve
> orthogonality at the boundary** as is discussed in Section 2.)"

and §2F, on the iterative determination that GRAPE (Sorenson) implements:

> "It is possible … to iteratively adjust the control functions … until not only a specified
> line slope but also the spacing of the first coordinate surface off the boundary is achieved,
> with the point locations on the boundary specified. … Upon convergence, the coordinate system
> then will have the coordinate lines intersecting the boundary normally at fixed locations and
> with the specified spacing on these lines off the boundary."

and, on where the algebraic grid belongs in that picture:

> "Since the system is nonlinear, convergence depends on the initial guess in iterative
> solutions. The algebraic grid generation procedures discussed in Chapter VIII can serve to
> generate this initial guess, and transfinite interpolation generally produces a more reliable
> initial guess."

**The named cost is convergence, and it scales with how hard you drive the control:** "The
optimum acceleration parameters and the convergence rate decrease as the control functions
increase in magnitude." **[V]** That is the same quantity `MB_CONTROL_CLIP` bounds
(`.claude/rules/mesher-smoothing.md:188`) and the same reason `MB_SMOOTH_ITERS` is capped at
20 for stability. The repo's tension is the literature's tension, not a local defect.

**(d) A deliberately non-constant-distance seam, chosen so equal arc = the normals.** Such a
curve exists: write `q(s) = p(s) + h(s)·n(s)`; the radials are then normal *by construction*,
and equal arc fraction matches iff `|dq/ds| = sqrt((1+hκ)² + h'²)` is constant. **[I]** But
that constant must be at least `1 + h·κ_max`, and on this ellipse `κ` runs from `b/a² = 1` to
`a/b² = 8` **[V]**, so at `h ≈ 0.25` the seam would have to be at least **3× the body's
perimeter** (against 1.65× for the true offset) and `h` would swing wildly. **[I]** On a body
of this curvature ratio the construction is degenerate — and it throws away the constant ring
thickness that #152 exists to provide, which the design note measures as worth 3.39% of the
ring at the nose.

---

## 4. "Cannot be fixed by resampling" — right, and the required map is closed-form

**The resampling half is right, for the reason the note gives.** `discretise`
(`src/MultiBlock.cpp:881`) converts each law position to an **absolute arc length** and calls
`lerpAtArc` (`:761`), which walks the polyline by cumulative length. The polyline's vertex
distribution therefore cannot move a node — only the curve's *shape* can. **[V]**

**The spacing-law half is right too, and for a stronger reason than "the laws cannot express
it".** `enum SpacingLaw { LAW_UNIFORM, LAW_GEOMETRIC, LAW_TANH }` (`:116`) and `spacingAlong`
(`:828`) are one-parameter monotone families in `(L, count)` alone. The map that is needed is
not merely outside that family — **it is not a function of this edge at all.** It depends on
the *other* curve's turning function. **[V]**

In closed form, for a seam that is the offset of the body at distance `d`, the arc position on
the seam that corresponds to body arc `s` is

```
    s_seam(s) = s + d·θ(s)      normalized:   t_seam = (s + d·θ(s)) / (L_body + d·θ_total)
```

with `θ(s)` the accumulated turning angle of the body polyline (`Σ` of the signed angles
between consecutive facets up to `s`). On a polyline this is the *exact* map, because the
offset's facets are parallel to the body's and all the extra length is the per-vertex miter.
**[V]**, and demonstrated: substituting it for the seam's `t` in my replication drops the
error to 0.000198 at every ring thickness tested (§1 table).

That is eight lines of arithmetic and needs nothing the mesher does not already compute. What
it needs that the mesher does **not** have is a declared relationship between two edges — an
answer to "which wall edge is this seam edge opposite?". The `d` would not even have to be
declared: it is `|q(0) − p(0)|` at the matched corners, or the map can be written as "the arc
position of the foot of the perpendicular from wall node `k`", which needs no `d` and works on
a seam that is not an exact offset. **[I]**

**One correction to the note's phrasing.** "It cannot be fixed by resampling either geometry"
is true. "It is a property of the pair and not of this case's numbers" is also true. But the
text reads as though nothing short of a new subsystem could help, and that is not what the
measurements say: four extra declared corners per ring take it from 0.070625 to 0.018242 with
no code at all (§Q5), and the seam being an offset is not required by the remap above.

---

## 5. Does ~7% in the first cell matter?

**The primary evidence says a uniform 7% error in wall spacing is far below the noise floor of
the wall-spacing sensitivity that turbulence models themselves show.** NASA's Turbulence
Modeling Resource ran the 2-D zero-pressure-gradient flat plate over seven grids with minimum
normal spacings from 0.5e-6 to 32e-6 — average minimum `y+` from **0.09 to 5.9**, a factor of
64 — and reports that "with the omega-based models, use of a grid with average minimum `y+` of
0.8 produced a drag coefficient between 2–3% low compared to use of a grid with average
minimum `y+` of 0.1", while SA and k-kL-MEAH2015 showed less sensitivity. Its guideline is
"Grids for turbulent flow RANS (when integrating to the wall …) should be constructed so that
the average minimum `y+` is less than 1."
(https://tmbwg.github.io/turbmodels/flatplate_val_ypluseffect.html) **[V]**

**[I]** A factor of **8** in wall spacing moves drag 2–3% for the most sensitive model class
there; a factor of **1.07** is two orders of magnitude smaller a perturbation. Nothing in that
study supports a claim that 7% is visible. **But the study does not cover this case**: its
spacing perturbation is *uniform over the wall*, while the 7% here is **spatially varying
around the body** (0.250001 at the axes, 0.267691 at the worst station). A varying first-cell
height also varies the local expansion ratio and the wall-normal line direction, and the TMR
study says nothing about either. So the honest statement is: **the evidence supports "a 7%
uniform wall-spacing error is negligible for RANS outputs"; it does not support "this
particular 7% is harmless", and no run in this repo has measured it** — the design note's own
blind-spot list records that #154 has no acceptance run with a varied operating point.

**And the practical question is smaller than that**, because `MB_SMOOTH_ITERS` defaults to 20
and takes the figure to 0.000000 — better than the single ring's 0.000389. A user reaches
0.070625 only by turning the smoother off.

---

## Gaps I could not close, by name

1. **Chan & Steger (1992) itself.** ScienceDirect returned HTTP 403. The governing
   orthogonality and cell-volume conditions are **[2nd]** via pyHyp's docs and via TWM
   Chapter VII's own presentation of the same system (Eq. 1, 2a/2b, 3a/3b there).
2. **Secco et al., AIAA J. 59(4) 2021, Section II.A** — pyHyp's own modern write-up. Paywalled
   at arc.aiaa.org; no open preprint found.
3. **Farouki & Neff's body text.** Abstract only; the `(1 + d·κ)` relation is my derivation
   plus my numeric check, not a quotation.
4. **A name for the failure mode.** I searched TWM Ch. VI–IX, pyHyp, construct2d and Gmsh and
   found no term of art for "equal arc-length correspondence between two curves yields
   non-normal connecting lines". If one exists I did not find it. Do not invent one.
5. **NASA HYPGEN / Chimera Grid Tools documentation.** Not reached in the time available; the
   TWM Chapter VII treatment is the closest primary substitute I have.
6. **CGNS.** Not investigated: it is a *file format* standard with no position on how a grid
   is generated, so it was the wrong candidate in the brief.
7. **Sorenson's GRAPE user manual (TWM Ref. [24])** — cited by TWM as the reference
   implementation of the iterative control-function determination, not located.
8. **Whether the Hermite-blend fill of §Q5 actually works here.** I derived it from TWM
   Ch. VIII Eq. (7) and observed construct2d doing the equivalent, but I did **not** prototype
   it against this repo's blocks, so its interaction with `arcFraction`'s facing-curve average
   and with the declared radial edges is unmeasured.
9. **Whether TWM Ch. VIII Eq. (66)–(67) is the same map as §4's.** The book records "a
   procedure for incorporating the effect of curvature into the distribution function … where
   the arc length distribution is given in the inverse form by (66) … K(ξ) is the curvature",
   citing its Ref. [38]. The equation images did not survive my text extraction, so I could
   not compare it with `s + d·θ(s)`. It is the most likely place for a prior statement of the
   same idea. **[V]** that the passage exists; **[2nd]** on what it says.

---

## Sources

Primary, read by me:

- Thompson, Warsi & Mastin, *Numerical Grid Generation: Foundations and Applications*,
  North-Holland 1985 — Ch. VI (elliptic systems; §2F iterative control functions), Ch. VII
  (parabolic and hyperbolic), Ch. VIII (algebraic systems; §1.B orthogonality via Hermite,
  §1.H uniformity + redistribution, §2.A transfinite interpolation), Ch. IX (orthogonal
  systems). Full text: https://polyakov.imamod.ru/arc/books/MESH_GEN_1/index.html
- Gmsh source, `live-clones/gmsh@master`: `src/mesh/meshGFaceTransfinite.cpp`,
  `src/mesh/BoundaryLayers.cpp`. Manual: https://gmsh.info/doc/texinfo/gmsh.html
- pyHyp, `mdolab/pyhyp@main`: `doc/index.rst`, `doc/options.yaml`, `src/3D/3D_code.F90`.
  Docs: https://mdolab-pyhyp.readthedocs-hosted.com/
- Construct2D 2.1 (Daniel Prosser), `cpraveen/construct2d@master`: `doc/user_manual.pdf`,
  `src/elliptic_surface_grid.f90`, `src/surface_util.f90`.
- NASA Turbulence Modeling Resource, flat-plate `y+` effect:
  https://tmbwg.github.io/turbmodels/flatplate_val_ypluseffect.html
- OpenFOAM layer addition (docs only):
  https://doc.openfoam.com/2312/tools/pre-processing/mesh/generation/snappyhexmesh/layers/

Cited but not read in full:

- Farouki & Neff, *Analytic properties of plane offset curves*, CAGD 7 (1990) 83–99 — abstract
  only, https://research.ibm.com/publications/analytic-properties-of-plane-offset-curves
- Chan & Steger, *Enhancements of a three-dimensional hyperbolic grid generation scheme*,
  Appl. Math. Comput. 51 (1992) 181–205 — https://doi.org/10.1016/0096-3003(92)90073-A
- Secco, Kenway, He, Mader & Martins, *Efficient Mesh Generation and Deformation for
  Aerodynamic Shape Optimization*, AIAA J. 59(4) 2021 — https://doi.org/10.2514/1.J059491

In this repo:

- `docs/design_notes/mesher.md:4176` — the write-up under test.
- `.claude/rules/mesher-multiblock.md:172` (`follows` is `binding` minus the BC half), `:438`
  (the computed middle ring), `:555` (nothing projects onto an analytic curve).
- `.claude/rules/mesher-smoothing.md:58` (following seam frozen), `:156` (the target is the
  ruler's own blend), `:163` (off-wall source solved exactly), `:188` (`MB_CONTROL_CLIP`).
- `src/MultiBlock.cpp:116` `SpacingLaw`, `:747` `arcLengths`, `:761` `lerpAtArc`, `:828`
  `spacingAlong`, `:881` `discretise`, `:1456` `arcFraction`, `:1483` `coons`;
  `src/MbQuality.cpp:257-320` the wall first-cell ruler;
  `tools/PreProcessor/include/Spacing.hpp:130`, `:143`.
- `tools/PreProcessor/gui/app/services/geometry_offset.py`;
  `examples/topology/tworing_offset.json`; `examples/geometries/ellipse_{body,offset}.dat`.
