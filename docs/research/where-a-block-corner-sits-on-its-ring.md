# Where a block corner sits on its ring

**A RESEARCH NOTE, like the six beside it.** Not `.claude/rules/*.md` (what the rule is), not
`docs/design_notes/` (why a shipped rule was chosen). It records what an outside literature
check says about a question this repo is currently deciding by feel, so the decision can be
argued from sources rather than from a table of our own numbers. Nothing here is binding; no
rule, gate, test or source file was changed to write it. 2026-10-22.

**The question, as asked.** In a structured multi-block grid of rings x columns around a body,
where should a block CORNER sit on its ring — and do production grid generators treat that
position as a user input or as something the generator SOLVES?

**Why it is being asked.** A NACA 4412 C-grid, 8 rings x 16 columns, 128 blocks, 179,520 cells,
0 inverted, every ring seam a declared conic. The ring a corner sits on is pinned to 6e-6. WHERE
ALONG the ring is a blend that was chosen rather than derived: the body's own outward normal
near the wall, the body's own arc-length fraction at the far field, weighted by the ring's
position between them. The measurements that followed are in §0 — **they are the requester's,
not this note's, and not a source's.**

## How to read the markers

- **[V]** verified in a primary source I read myself (source code, official docs, standards
  text, or the paper), or measured by me.
- **[I]** my own inference from a **[V]** fact. Stated as reasoning, not as fact.
- **[2nd]** I could only find this secondhand. Treat as unconfirmed.
- **[M]** a measurement supplied by the requester in the brief that commissioned this note.
  **I did not re-derive any of these**; the case is not in the tree (`grep -rl 4412` over the
  repo returns test fixtures and three other research notes, no 8x16 C-grid). They are quoted
  so the sources can be set against them, and they carry no more weight than that.

**A note on source access.** `cadence.com` and `pointwise.com` answer **HTTP 403** to any
non-browser request today — `pointwise.com` 301-redirects to `cadence.com`, which then serves a
Cloudflare interstitial. Every Pointwise fact below I read in the Internet Archive's capture of
the vendor's own *Glyph 3.18.x* reference (snapshots `20231202012148` and `20230529054117`),
fetched by `curl` with `id_` raw-content URLs. It is the vendor's text, not a summary of it, so
it is **[V]**; it is an archived copy, and that is stated rather than hidden. The one Pointwise
page I wanted most — the user manual's *Boundary Conditions* page under
`structured-domains-and-blocks/edge-attributes-tab/` — **has never been archived under either
host** (CDX returns nothing for it while returning its four siblings), so its prose is
**[2nd]** below and the Glyph reference carries the load. `apps.dtic.mil` returns an HTML stub
rather than `ADA259958.pdf`. NASA NTRS served every report quoted here as a PDF; several are
1980s scans and their OCR is poor, so any quotation reconstructed from OCR is **marked as
such** at the point of use.

---

## 0. The measurements this note starts from — the requester's, verbatim, not re-derived

**[M]** all six:

1. The ring seams are declared conics (`"curve": {"kind":"ellipse", ...}`), no offset geometry.
   Each corner is at its ring's distance to **6e-6**.
2. The radial block edges — straight chords between ring corners — met their rings **6.51 deg
   off perpendicular on average, 25.70 deg at worst**, over 256 block corners.
3. The gradient trajectory of the distance field, the family orthogonal to the level sets, is
   **dead straight off a convex surface** (bow 0.00% over 0.30 chords), because the nearest body
   point never changes along it. So "follow the normal" does not bend a radial at all.
4. Refitting every body radial as an ellipse arc perpendicular to the ring at BOTH ends improved
   corner perpendicularity (**13.18 -> 9.26 deg mean, 37.61 -> 25.76 deg worst**) but moved the
   mesh's own mean non-orthogonality by **0.06 deg** (10.12 -> 10.06), and seam ratios got
   slightly worse.
5. Following the normal alone made two adjacent columns' trajectories arrive **5.4 deg apart at
   9.6 chords**, which would have given one column 5 deg of the outer boundary and its neighbour
   170 deg. That is why the blend exists.
6. The conclusion drawn: *the angle error lives in the corner's POSITION, not the edge's shape.
   Bending the edge squares the corner and tilts its interior the other way; the two cancel. If
   the mean angle is the number to move, the thing to move is the blend.*

**[I] One of these is a theorem, not a measurement, and it is worth saying so.** Item 3 is not
a property of this geometry: for a smooth curve, the normal line *is* straight, and wherever the
nearest-point map is single-valued (i.e. inside the medial axis) the distance field's gradient
is the unit normal of that same nearest point all along the ray, so the integral curve is that
straight ray. The repo's own `arc-length-correspondence-on-an-offset-ring.md` already derives
the companion relation from the Frenet equations (`dq/ds = (1 + d*kappa)*t`) and checks it
numerically on the shipped ellipse files to 2.0e-05. Item 3 is that fact seen from the other
side, and it is exact rather than 0.00%-measured. It also means item 5 is forced: normal rays
off a convex body **diverge**, their angular spread set by the turning angle between the two
feet, and no amount of care in placing them removes that.

---

## Lead: the six answers a reader needs first

### L1 — The position of a boundary point along its boundary is a named BOUNDARY CONDITION on the generator, not a placement rule. Three regimes exist, all shipped. **[V]**

| regime | who decides the position along the boundary | shipped in |
|---|---|---|
| **Prescribed** (Dirichlet) | the user, entirely; orthogonality is bought elsewhere | Thompson–Thames–Mastin; GRAPE (Sorenson); Pointwise `EdgeConstraint Fixed` (**the default**); ICEM's structured smoother with boundaries frozen |
| **Solved / sliding** (Neumann-type) | the generator, by enforcing orthogonality at the boundary | Nakamura's UBGR and FBGR; Pointwise `EdgeConstraint Orthogonal` (2-D only); GridPro, where even the corner is only an initial guess |
| **Never declared at all** | the march; the outward positions are an OUTPUT | hyperbolic generation — Steger–Sorenson, Steger–Rizk, HYPGEN |

The vocabulary is the thing the brief was missing. A "blend" is not a term of art; **a fixed
versus a sliding (floating) boundary point is**, and both halves of the brief's instinct —
that the position along the ring is the free variable, and that it should not have been chosen
by a formula — are the literature's own position, arrived at forty years earlier and for a
reason the brief does not state. That reason is L2.

### L2 — You cannot prescribe both the boundary point distribution AND boundary orthogonality. It is a degrees-of-freedom argument, and it is written down. **[V]**

Thompson, Thames and Mastin, NASA CR-2729, in the paper that founded elliptic grid generation:

> "The coordinate system so generated is not necessarily orthogonal, but orthogonality is not
> required… **An orthogonal system cannot be achieved with arbitrary spacing of the coordinate
> lines**, and the capability for such concentration of coordinate lines is of more importance
> than orthogonality."

Nakamura, NASA CR-166523, states the same thing as an equation count at a single boundary node:

> "For a grid point on the boundary, the two equations in Eq.(20) can not be satisfied
> simultaneously because of the following additional constraints: (1) boundary grid must be on
> the specified boundary line, and (2) orthogonality of grid lines at the boundary is required.
> …the first constraint does not allow the two elliptic equations to be independent. **This means
> that only one of the two equations can be used**…"

and then names which coordinate survives:

> "**The coordinate t is in the normal direction from the boundary so t_ij on the boundary is not
> allowed to change. On the other hand, s is tangent to the boundary so s_ij has a freedom to
> change.**"

**[V]** That is the brief's conclusion, in the literature's own words, with the derivation the
brief did not have: at a boundary point there is exactly **one** free scalar — the tangential
coordinate — and orthogonality consumes it. The budget is global, too: Nakamura's abstract says
"with the UBGR scheme, the grid points on the flow boundaries are **automatically determined by
the algorithm**, while with the FBGR scheme **at most one half of the boundary grid points may
be prespecified** and the remainder of boundary grid points are determined automatically."
**[V]**

**[I] Read against this repo, that is a sharper statement than it looks.** A ring corner here is
constrained to its ring (pinned to 6e-6, item 1) *and* wanted perpendicular (item 2). Those are
Nakamura's constraints (1) and (2) exactly. The repo currently satisfies (1) exactly and spends
the one remaining freedom on a blend formula instead of on (2). Nothing is wrong with that
choice; what is wrong is calling the 6.51 deg a defect to be tuned away, because the two
demands cannot both be met and the literature says so in one line.

### L3 — The dominant shipped DEFAULT contradicts "move the blend": it keeps the boundary point where you put it and buys the angle by bending the interior lines. **[V]**

Fidelity Pointwise's structured elliptic solver, from the vendor's own Glyph reference:

```
$dom get/setEllipticSolverAttribute ?-edge index? EdgeConstraint < Fixed | Floating | Orthogonal >
    This attribute is the boundary constraints of the structured domain.
    Default  The default for this attribute is Fixed.

$dom get/setEllipticSolverAttribute ?-edge index? EdgeAngleCalculation < Orthogonal | Interpolate | Current | Adjacent >
    This attribute is the boundary control function angle calculation method.
    Default  The default for this attribute is Orthogonal.

$dom get/setEllipticSolverAttribute ?-edge index? EdgeControl < HilgenstockWhite | StegerSorenson | None >
    Default  The default value is HilgenstockWhite.

$dom get/setEllipticSolverAttribute InteriorControl < ThomasMiddlecoff | Laplace | Fixed >
    Default  The default value is ThomasMiddlecoff.
```

**[V]** Read the four defaults together: **the boundary points do not move** (`Fixed`), **the
target angle at the boundary is 90 degrees** (`EdgeAngleCalculation Orthogonal`), and the
instrument that delivers it is a **control function** (`HilgenstockWhite`) acting on the
interior. The shipped answer to "my radials meet the ring at 6.5 degrees off" is not *move the
corner*; it is *leave the corner and solve the interior so the lines arrive square*.

Sorenson's GRAPE is the same design, twelve years earlier and more explicit, because it exposes
the angle per station:

> "THETAI … If it is desired that a constant value be used for [theta at k=1], that is, the
> angles with which ξ = constant lines intersect the inner boundary, for every j in 1 ≤ j ≤
> jmax, then that value should be entered in THETAI. Alternatively, as indicated by THETAI = 0,
> **any set of values may be entered into array THETA(J)** … with THETAI = 90.0 indicating
> orthogonality."

and the same per-station array exists at the OUTER boundary as `THOBI` / `THETOB(J)`. **[V]**
Meanwhile the point positions stay the user's: "**Any distribution of points on boundaries is
acceptable.**" **[V]**

ICEM CFD ships the same two authors as named methods — `Sorenson/Laplace`,
`Sorenson/Thomas & Middlecoff`, `Hilgenstock/Laplace`, `Hilgenstock/Thomas & Middlecoff` — with
`Freeze > All Surface Boundaries` ("freezes all boundary node locations") as an option rather
than the default. **[V]**

### L4 — The vendor documentation also states, verbatim, the exact cancellation the brief measured — and names its cause. **[V]**

ICEM CFD, *Smooth Hexahedral Mesh Orthogonal*, on what happens when the control function is not
propagated inward:

> "If the grid expansion rate is set to 0.0 and the smooth type is set to **Orthogonality**, the
> first layer height and the orthogonality at the boundary are still achieved, but **the next
> layers tend towards Laplace approaching the middle of the mesh**. In case of a Navier-Stokes
> mesh you can see the effect near the boundary where **the first layer is orthogonal to the
> boundary but the next layers curve** as they equalize (Laplace) the distances of the layer
> nodes."

**[V]** And GRAPE says the same of its own mechanism (OCR-reconstructed from the 1980 scan; the
scanned glyphs for η are garbled and are rendered here as `eta`):

> "Although the four geometric effects are imbedded in p, q, r, and s, their use in equations (5)
> indicates that **their effect decays exponentially as one moves away from the eta = 0 and eta =
> eta_max boundaries**. Thus, some measurable decay in the geometric effects can occur between
> the boundary and the interior grid lines. … The four positive constants a, b, c, and d in
> equations (5) determine the rate of the exponential decay."

**[V, OCR-reconstructed]**

**[I] This is the brief's item 4 and item 6, written by the vendors.** "Bending the edge squares
the corner and tilts its interior the other way; the two cancel" is boundary orthogonality
decaying into the interior — a known, documented, *deliberate* property of every
control-function scheme, with an explicit knob for the decay rate (`a, b, c, d` in GRAPE,
`Grid Expansion` in ICEM, `EdgeAngleBlend < Exponential | Linear | value >` in Pointwise). The
brief treated the cancellation as evidence that bending the edge is the wrong lever. The sources
say it is the right lever **operated without its decay control**: squaring the corner is only the
boundary condition, and what carries it inward is an interior solve this repo does not run.

### L5 — The blend itself is not an invention. It is shipped, it is named, and in its shipped form it is a cell-volume source term in a march, not a geometric interpolation. **[V]**

HYPGEN, NASA TM 108791, parameter `IVSPEC` with `EPSSS`:

> "In some situations, using IVSPEC = 2 can bring in extra smoothing to the grid **by scaling
> with the volumes of a sphere**. … EPSSS is only used with IVSPEC = 2 and it controls **how
> rapidly the grid volumes are blended to become the grid volumes for a sphere as the grid
> marches out** in L. Increasing EPSSS exponentially increases the spherical volume blending.
> **This option tends to make the cell volumes more uniform in the far field and tends to make
> the shape of the far field boundary approach that of a sphere.**"

and the opposite end of the same dial, in the same paragraph:

> "A small or zero ITSVOL (< 5), together with a small SMU2 (≤ 0.5), should be used with IVSPEC
> = 1 **if it is desired to have the grid points maintain a similar distribution at each L-shell
> as that on the surface grid**. A higher ITSVOL will tend to spread out the grid points more."

**[V]** Steger and Sorenson had already described the same transition in 1980, in prose, for the
2-D case this repo is in:

> "The control volumes were specified about a circle whose arc length matches that of the
> fuselage. **Initially these control volumes are proportional to the grid-point arc-length
> spacing around the fuselage. Ultimately, however, control volumes that are uniformly spaced
> in the circumferential (i.e. theta) direction are specified. Thus in far field a polar
> coordinate system is formed.**"

**[V]** That is the brief's blend: body-determined near the wall, body-independent far away.
What differs is everything about how it is expressed. It is **not** a rule for placing a point;
it is a **source term** — the per-cell area the hyperbolic system is asked to produce — whose
only user-facing parameter is a decay rate (`EPSSS`), and the positions fall out of the march.
And it is available only because of L6's price.

### L6 — Hyperbolic marching gets orthogonality nearly for free and pays for it by giving up the outer boundary. The vendor says so in a bullet list. **[V]**

Steger and Sorenson's own summary slide, verbatim:

```
HYPERBOLIC GRID GENERATION ADVANTAGES
 • SMOOTHLY VARYING GRID IS FOUND
 • GOOD USER CONTROL OF CLUSTERING NEAR BOUNDARY
 • FAST GRID GENERATION
 • ORTHOGONAL OR NEARLY ORTHOGONAL
 • AUTOMATICALLY TREATS COMPLEX SHAPES

HYPERBOLIC GRID GENERATION DISADVANTAGES
 • OUTER BOUNDARY CANNOT BE SPECIFIED (UNLESS ITERATIVE SHOOTING METHOD DEVISED)
 • SCHEME TENDS TO PROPAGATE DISCONTINUOUS BOUNDARY DATA
 • POORLY SPECIFIED BOUNDARY DATA AND CONTROL VOLUMES CAN RESULT IN "SHOCK-WAVE" LIKE BREAKDOWN
```

**[V]** The first line of the paper says the same: "The location of the outer boundary is not
specified; it only need be far removed from the inner boundary." **[V]**

**[I]** This is the strongest candidate the brief named for "the blend should not exist at all",
and the sources say it is also the most expensive. A `MESH_MODE 1` topology declares its outer
boundary by construction — that is what a declared block topology *is* — so adopting marching
is not a change of spacing law, it is giving up the thing the mode exists for. §3.3 below
records what the brief could take from it without that.

---

## 1. Elliptic generation: who owns the boundary point

### 1a. Thompson–Thames–Mastin — the boundary distribution is arbitrary and orthogonality is not attempted **[V]**

NASA CR-2729 (Thompson, Thames & Mastin, 1977), the long-form NASA report behind the 1974 JCP
paper. Three statements, all verbatim:

> "The ξ=constant lines may be spaced as desired around the boundaries since **the assignment of
> the ξ-values to the [x,y] boundary points via the functions f1, f2, g1, and g2 in (11f,g) is
> arbitrary**. (Numerically the discrete boundary values [x_k, y_k] are transformed to
> equi-spaced discrete ξ_k-points on both boundaries.)"

> "Control of the radial spacing of the η=constant lines and of **the incidence angle of the
> ξ=constant lines at the boundaries** is accomplished by **varying the generating elliptic
> system** (i.e., the system of which ξ(x,y) and η(x,y) are solutions)…"

> "The coordinate system so generated is not necessarily orthogonal, but orthogonality is not
> required… An orthogonal system cannot be achieved with arbitrary spacing of the coordinate
> lines, and the capability for such concentration of coordinate lines is of more importance
> than orthogonality."

**[V]** Three things follow and are worth separating. First, the boundary point is a **Dirichlet
datum**: whatever you put there is where it stays. Second, the *incidence angle at the boundary*
is a named, separately controlled quantity — the field has always treated "where the point is"
and "at what angle the line leaves it" as two different questions. Third, the trade-off in L2 is
stated as a limitation of the whole approach, in the founding document, not as a defect of an
implementation.

### 1b. GRAPE / Sorenson–Steger — orthogonality AT the boundary, by back-solving the source terms **[V]**

NASA TM 81198 (Sorenson, 1980; NTRS `19800017767`). The abstract states the design in one
sentence:

> "The inhomogeneous terms are automatically chosen such that two important effects are imposed
> on the grid at the inner (airfoil) boundary and at the outer boundary. **The first effect is
> control of the spacing between mesh points, along mesh lines intersecting the boundaries. The
> second effect is control of the angles with which mesh lines intersect the boundaries.**"

The mechanism, verbatim (lightly OCR-reconstructed — the scan loses subscripts):

> "The desired end result of the preceding manipulations is that the four geometric constraints
> be embedded in the P and Q terms. In pursuit of this we use equations (14) to compute x_η and
> y_η. We then assume that the mapping functions do satisfy the transformed Poisson equations at
> the inner and outer boundaries, **then 'back-solve' for P and Q**."

**[V, OCR-reconstructed]** The four constraints are: the normal spacing at the body, the angle at
the body, and the same pair at the outer boundary — each of which may be a **per-station array**
(`DS(J)`, `THETA(J)`, `DSOB(J)`, `THETOB(J)`), with `THETA(J) = 90.0` everywhere as the default
("thus indicating that we want 90° angles, or orthogonality, everywhere on the body"). **[V]**

**[I] GRAPE is the sharpest counter-example to the brief's conclusion that exists.** It takes
precisely the brief's complaint — a mesh line meeting a boundary at other than 90 degrees — and
fixes it **without moving a single boundary point**, by solving for the source terms that make
the interior arrive at the demanded angle. It also exposes the angle per station, so the
brief's "6.51 deg mean, 25.70 deg worst over 256 corners" is, in GRAPE's vocabulary, a
`THETA(J)` array that was never set rather than a corner array that is in the wrong place.

The price is in L4: the effect decays exponentially inward at a rate the user sets, so GRAPE
does not promise orthogonality anywhere but at the two boundaries.

### 1c. Nakamura's UBGR and FBGR — the boundary point as an UNKNOWN **[V]**

NASA CR-166523 (S. Nakamura, Ohio State, for NASA Ames), *Generation of Orthogonal Grids By
Boundary Grid Relaxation*. This is the paper that gives the brief's question its proper name.
The framing, verbatim:

> "The most fundamental difference between the conformal mapping and the elliptic grid generation
> method is that **the grids on the flow boundary are prespecified in the elliptic grid
> generation, while in the former the grids on the boundary are determined by the conformal
> mapping**."

> "The objective of the present paper is to show that orthogonal grids may be generated by using
> the elliptic grid generation equations by **automatically determining at least one half of the
> boundary grid points as part of the grid generation**."

The two schemes, verbatim:

> "In the UBGR scheme, **all the grid points on the boundary are undetermined**, while up to one
> half of the boundary grid points may be prespecified in the FBGR scheme and the remaining
> boundary grid points are undetermined."

> "In the UBGR scheme **two end points of a grid line are undetermined so both move along the
> physical boundary during iterations**, while the grid line on the computational domain is
> fixed. Another way of satisfying the orthogonal grid generation equations is that: (a) one end
> point of a grid line is fixed, (b) the other end point of the grid line is left to be variable,
> and (c) **grid spacings adjacent to the corresponding grid line on the computational domain are
> variable**. This latter approach is denoted as the FBGR scheme."

**[V]** The boundary update itself is one scalar equation in the tangential coordinate `s`,
derived in §4 of that report: the elliptic equation in the normal coordinate `t` is **discarded**
because `t` is pinned by the boundary, the cross term `B` is set to zero *because* orthogonality
is being imposed, and the resulting tridiagonal relation in `s` is solved; then "t_ij is
calculated by introducing the value of s_ij into the equation that defines the boundary". **[V]**

**[I] That last sentence is the whole algorithm this repo would need, and it is three lines.**
Solve for the arc-length position along the ring from a one-dimensional relation that encodes
"be perpendicular to the ring"; then evaluate the ring's own parametrisation at that arc length
to get `(x, y)`. The declared conic in `"curve": {"kind":"ellipse", …}` already *is* that
parametrisation, which is the piece most implementations have to fake with a projection.

Note also what FBGR trades to keep half the points fixed: **the computational spacing becomes
variable** (its Eqs. 26–28 reassign `δξ_i` and `δξ_{i+1}` by a chord-length ratio). There is no
free lunch; the freedom has to come from somewhere, and FBGR takes it from the index spacing.

### 1d. Thomas–Middlecoff and Hilgenstock — named in the tools, not read here **[2nd] / [V] on the naming only**

Both appear as shipped options — Pointwise's `InteriorControl ThomasMiddlecoff` (its default) and
`EdgeControl HilgenstockWhite` (its default), ICEM's `Sorenson/Thomas & Middlecoff` and
`Hilgenstock/*` **[V]** — and ICEM states what each is for:

> "**Sorenson** methods attempt to maintain node distributions (bunching) near the surface
> boundaries while improving orthogonality. … **Hilgenstock** methods maintain orthogonality and
> first layer height."
> "**Sorenson/Thomas & Middlecoff**: This method improves orthogonality at the boundary while
> maintaining the first layer height from the boundary surface and **holding the original
> clustering on the interior**."

**[V]** The underlying papers (Thomas & Middlecoff, *AIAA J.* 18, 1980; Hilgenstock, *Notes on
Numerical Fluid Mechanics* 21, 1988) are not open-access and **I did not read either**. See Gaps.
What matters for this note is already visible in the shipped vocabulary: every one of these is a
**control function**, i.e. a member of L3's regime, and none of them moves a boundary point.

---

## 2. Hyperbolic generation: the position is an output

### 2a. The equations, and what the user actually supplies **[V]**

Steger & Sorenson (NASA CP-2166, 1980) give the two systems verbatim:

```
ARC LENGTH-ORTHOGONALITY SCHEME        VOLUME-ORTHOGONALITY SCHEME
 x_ξ² + y_ξ² + x_η² + y_η² = (Δs)²      x_ξ y_η − x_η y_ξ = V
 x_ξ x_η + y_ξ y_η = 0                  x_ξ x_η + y_ξ y_η = 0
```

**[V]** Two equations: one **orthogonality** condition and one **geometric** (arc length, or cell
area) condition. Orthogonality is not a target to be approached by a control function; it is half
the definition of the system. HYPGEN's manual says the 3-D version the same way: "by solving the
3-D hyperbolic grid generation equations (**two orthogonality relations and one cell volume
constraint**)". **[V]**

What the user supplies in place of a point distribution is the **cell area field**:

> "The volume orthogonality scheme requires that the user specify the volume (area in 2-D) of
> each mesh cell. **The quality of the grid will, to a large extent, be determined by the user's
> cleverness in specifying these volumes.** To specify these volumes, we currently define a
> simple geometric shape (e.g. circle or straight line) which has exactly the same arc length as
> the body we wish to grid. An algebraically clustered grid is then created by the user for the
> simple geometric shape. The volumes of this simple grid, **the control volume grid**, are then
> used directly on a point by point basis in the hyperbolic grid generation equations."

**[V]** For a C-grid specifically: "Here the control volume grid is generated about a straight
line, that is, it is nothing more than a clustered rectangular grid." **[V]**

**[I] The control volume grid is the closest published object to this repo's rings-and-columns
declaration.** It is a second, simple, *topologically identical* grid whose only job is to say
how big each cell should be, built on a shape of matching arc length. In a `MESH_MODE 1`
vocabulary that is a ring/column table of target areas rather than a table of corner positions —
and it is where the body-to-polar transition of L5 is expressed.

### 2b. What a march cannot do, from the people who wrote it **[V]**

Besides L6's bullet list:

- **Orthogonality is sacrificed to survive concavity.** HYPGEN: "The algorithm ensures that the
  smoothing is small near the body surface **to preserve orthogonality**. Smoothing is increased
  locally by detecting whether grid lines are converging as in concave regions." And: "The
  strategy for selecting the 'best' value of SMU2 is that it should be **as small as possible to
  maintain orthogonality but large enough to provide sufficient smoothness** to the grid." **[V]**
  Steger & Rizk put a number on it: "Values of θ of 1 to 5 are effective in preventing numerical
  breakdown in the case of highly concave body shapes. **If some loss of grid orthogonality can
  be tolerated, θ can be set to 3 for most applications.**" **[V, OCR-reconstructed]**
- **It breaks down rather than degrading.** "For a profile with twice the camber, however, this
  process breaks down and grid lines do coalesce. In these cases a more sophisticated means of
  specifying the volumes is needed." **[V]**
- **A boundary that disagrees with the march cannot be prescribed at all.** Steger & Rizk, on a
  symmetry plane: "the grid at ξ = 0 … **cannot be prescribed as this would be incompatible with
  the grid developing in the interior when marched** in ζ. Consequently, **the grid distribution
  on this boundary surface must evolve as part of the overall solution process**." **[V,
  OCR-reconstructed]**

**[I]** That last quotation is the general statement of which L2 is the elliptic special case,
and it is the one sentence from this whole search most worth keeping: a boundary distribution
that is incompatible with the interior is not a thing you may insist on. The brief's blend is an
attempt to insist on one, and its own item 5 — two normals 5.4 degrees apart at 9.6 chords —
is the incompatibility showing up.

### 2c. HYPGEN's other two mechanisms, for completeness **[V]**

Already recorded in `cell-size-range-within-a-block.md` §2d and not repeated here: the explicit
per-point stretching array (`IZSTRT = -1`, file `zetastr.i`, up to "different stretching for each
J and K") and the per-surface-point far-field distance and end spacings (`ZREG`, `DZ0`, `DZ1`).
The two are mutually exclusive. **[V]** Both are about the **radial** direction; neither places a
point circumferentially. The circumferential answer in HYPGEN is `IVSPEC`/`EPSSS`/`ITSVOL`
(L5), and it is a cell-volume answer.

---

## 3. GridPro — the sharpest case, and the answer is "a corner is an initial guess"

Primary sources read: Eiseman, *Multiblock Grid Generation with Automatic Zoning* (NASA CP, 1995,
NTRS `19950022314`); Cheng & Eiseman, *Examples of Grid Generation with Implicitly Specified
Surfaces using GridPro/az3000* (NTRS `19950022351`); Eiseman, *Grid Generation on Surfaces in
Three Dimensions*, final report NAG-1-617 (NTRS `19870017991`); the GridPro v10 FAQ PDF; the
HiOCFD5 presentation by Sudharshanam, Ebenezer & Eiseman (2015).

### 3a. The corner position is explicitly NOT an input **[V]**

The decisive sentence, verbatim:

> "**While each corner must be put somewhere in physical space, there is no precise requirement
> to give a certain location. The only demand is the fuzzy topological one that the placement be
> in 'general position'.** In practical terms, the corners assigned to a surface should roughly
> follow it to reflect major variations in surface shape."

**[V]** Cheng & Eiseman use the word that settles it: "A corner is generally defined by
specifying a corner id, **an initial position**, a list of surfaces that the corner is supposed
to be on, and a list of existing corners to which the current corner should have links." **[V]**

And the surface assignment, not the coordinate, is what binds a block face to geometry:

> "**A block face will be placed upon a particular surface if the corresponding four topological
> face corners are assigned to that surface.** Moreover, a block edge will be placed upon the
> intersection of two surfaces if the two topological corners for the edge link are assigned to
> the two surfaces."

**[V]** So in GridPro the answer to the brief's question 1 is: **neither**. The corner is not a
user input (only a hint), and it is not solved as a position in space either — what is solved is
the whole grid, subject to "this face lives on that surface", and the corner ends up wherever
that solution puts it on the surface.

### 3b. What it moves and what it optimises **[V] on the shape, [I] on the functional**

> "the run could be started with a fairly modest number of grid points which are then increased
> in stages as the grid is relaxed towards **its equilibrium that progressively satisfies the
> underlying variational scheme**."

> "Upon activation, the volumetric grid points **distribute themselves about the boundaries in
> proportion to the boundary curvature**."

> "**Grid generator automatically projects and moves grid points to optimal locations** to create
> a smooth orthogonal grid." (HiOCFD5, slide 5, same authorship.)

**[V]** The functional itself is still not published in anything I reached, but the 1987 NAVSEA
final report names the algorithm and describes what the weights do, which is new relative to the
gap `cell-size-range-within-a-block.md` left open:

> "the basic adaptive movement technique of **mean-value-relaxation** was extended from the
> viewpoint of a single coordinate grid over a surface described by a simple scalar function to
> that of a surface more generally defined by vector functions and covered by a collection of
> smoothly connected grids."

> "the mean value relaxation algorithm with local barycentric interpolation was employed within
> the general surface context **to move the grid points into new positions on the basis of unit
> weights. The result was a push towards an equalization of cell areas** subject to the
> constraint imposed by our choice of grid topology…"

> "**By adding a curvature term to the previous weight of unity, we get a new weight for
> curvature clustering relative to the unity term which represents the cell area equalization
> force.**"

citing Eiseman, "Adaptive Grid Generation by Mean-Value Relaxation," *ASME J. Fluids Engr.* 107
(1985), 477–483. **[V]**

**[I]** So the mechanism is: move each point toward a weighted mean of its linked neighbours
**on the surface it is assigned to**, with weight 1 giving area equalisation and a curvature term
giving curvature clustering. That is the same family as Laplacian/Winslow smoothing — which is
what this repo's `MB_SMOOTH_ITERS` already runs — differing in that **the boundary points
participate**, constrained to their surface rather than to their position. This is the one
GridPro claim I would most want a second source for, because it is an inference from a 1987
precursor report to a 1995 product.

### 3c. Does it move corners along a surface, off it, or both? **[I], with the evidence**

Three primary facts: a corner is given only an "initial position" in "general position"
(§3a) **[V]**; the generator "projects and moves grid points to optimal locations" **[V]**; and
GridPro ships a third surface type, the **floating surface**, which is "abstract since there is
**no defined position or condition for this surface**. This type of surface is used to define
clustering to any block face **regardless of where it is**" **[V]**.

**[I]** Taken together: a corner assigned to a real surface is moved **along that surface**
(projection is part of the same iteration, not a post-step); a corner assigned to nothing is
moved freely in space; and the floating surface exists precisely so that a clustering
specification can be attached to a face whose position is not constrained at all. There is no
regime in which a corner's coordinates are honoured as given.

### 3d. What GridPro replaces the brief's blend with **[V]**

Not a distribution rule — **blocks**. Already recorded in `cell-size-range-within-a-block.md`
§L4/§3 and not restated: `nest` / `reverse_nest` / `Enrich`, the leading- and trailing-edge
"clamps" and "collar", and "The count can go to a thousand, ten thousand, or more." The v10 FAQ
adds the surface-assignment rules that bound the topology — e.g. "**Any sharp feature of a
single surface should be represented with two distinct surfaces**", and the singularity rules
about how many edges may emerge from an assigned corner. **[V]**

---

## 4. ICEM CFD — the vertex is constrained to its curve, and the USER slides it

### 4a. Association **[V]**

> "The **Associate Vertex** option allows you to associate vertices and **project the vertex onto
> itself, points, curves, surfaces and parts**."

> "**Green Edges/Vertices** … are being projected to curves. **The vertices can only be moved on
> the curves that they are projected to.**"

> "**Snap Project Vertices** … allows you to project all the vertices that are associated to
> respective points, curves or surfaces." Options: `All Visible`, `Selected`, and `Move Ogrid
> nodes` — "moves internal nodes (that are not projecting) which are attached via an Ogrid edge
> to external nodes (nodes that are projecting) relative to the projection."

**[V]** The constraint is exactly this repo's: a vertex associated to a curve lives on that curve
and its one freedom is the position along it. ICEM does **not** document how `Snap Project
Vertices` chooses that position — the help page says only "to their respective entity" and gives
no rule — so the obvious reading (closest point) is **[I]**, not verified. What *is* documented
is that the user may drag it: moving a vertex along an associated curve is a mouse operation.

### 4b. The smoother does move vertices, and the manual warns about it **[V]**

> "**Note:** If you smooth the pre-mesh (Blocking), **the smoother may move vertices and change
> edge distributions undesirably**. If you are outputting a structured mesh, you should save the
> blocking first so you can return to the previous state if necessary."

**[V]** And the smoother's own description:

> "The unstructured hexahedral smoother relaxes unstructured hexahedral meshes in order to obtain
> smooth grid lines orthogonal to the boundary as well as smooth grid angles and transitions in
> the inner volume. **It first smoothes the surface mesh recognizing the topological boundary
> edges.** … The mathematical basis is that an elliptical differential equation of the form […],
> where […] is the '**control function**', will be solved. … The control function will be
> specified so that the smoothed mesh will obtain certain characteristics, such as
> **orthogonality and layer height of the first layer**."

> "**Freeze Options — All Surface Boundaries**: freezes all boundary node locations."

**[V]** **[I]** Freezing is an *option*, so the default is that surface nodes move — along the
surface, since "it first smoothes the surface mesh recognizing the topological boundary edges"
and the result is still a surface mesh. ICEM therefore sits in both of L1's first two regimes,
selectable per part, with a warning attached to the sliding one.

### 4c. The tip ICEM gives for exactly the brief's problem **[V]**

> "Tips to improve smoothing success: **Create the best possible starting condition by matching
> edge distributions.** Create points (geometry) at the ends of the edges, and then associate the
> vertices (block) to them. This may be used to contain an area of fine mesh along a wall,
> preventing it from being totally smoothed out."

**[V]** **[I]** Note what the vendor's advice is: not "place the vertices better", but "match the
edge distributions, and pin the few vertices you actually care about by associating them to
*points*". A point association is the ICEM spelling of "this corner is a user input"; everything
not so associated is the smoother's.

---

## 5. Pointwise / Cadence Fidelity — the exact named counterpart of the brief's blend

### 5a. The three boundary constraints, and the one that slides **[V]**

From the Glyph reference, already quoted in L3:

```
EdgeConstraint < Fixed | Floating | Orthogonal >     (structured DOMAIN, i.e. 2-D)   default Fixed
FaceConstraint < Fixed | Floating | Adapt   >        (structured BLOCK,  i.e. 3-D)   default Fixed
```

**[V]** Two things are load-bearing in that pair. First, **`Orthogonal` exists only at the domain
(2-D) level**; the block-level attribute offers `Adapt` in its place. That is a vendor-verified
fact about the capability, not a doc-page omission — the two Glyph pages list different
enumerations. Second, **`Fixed` is the default in both**, which is L3.

The user manual's prose for these is the one page I could not reach (see "A note on source
access"). A search engine's extract of it reads: *"Orthogonal: Boundary points will move along
the boundary shape in order to maintain orthogonality with the interior points, and this option
is only available for domain edges"*, and for `Floating`: *"Boundary points will 'float' as
though they were interior grid points … only applicable if a unique neighbor can be found to the
boundary among the grids selected for the elliptic solver, and if a unique neighbor cannot be
found, the boundary condition is converted to fixed for that grid point."* **[2nd]** — a
search-result extract, not a page I read; it is consistent with the Glyph enumeration and with
Nakamura's UBGR, and nothing here rests on it.

**[I] "Boundary points will move along the boundary shape" is the literature name the brief was
looking for.** `EdgeConstraint Orthogonal` is Nakamura's UBGR packaged as a per-edge boundary
condition, and `Floating` is the weaker version where the point is treated as interior (so it
would leave the curve, were a neighbour not supplying the constraint).

### 5b. The angle and spacing targets, which are separate from the position **[V]**

```
EdgeAngleCalculation   < Orthogonal | Interpolate | Current | Adjacent >   default Orthogonal
EdgeAngleBlend         < Exponential | Linear | value >                    default Exponential
EdgeSpacingCalculation < Interpolate | Current | Adjacent | value >        default Interpolate
EdgeSpacingBlend       < Exponential | Linear | value >
EdgeControl            < HilgenstockWhite | StegerSorenson | None >        default HilgenstockWhite
InteriorControl        < ThomasMiddlecoff | Laplace | Fixed >              default ThomasMiddlecoff
SolverEngine           < MultiGrid | SuccessiveOverRelaxation >            default MultiGrid
ShapeConstraint        < constraint | db_list >
ShapeProjection        < method | normal >
```

**[V]** Three of these deserve naming for a multi-block mesher:

- **`EdgeAngleCalculation Adjacent`** — the boundary angle target is taken from the *neighbouring
  grid* rather than being 90 degrees. **[I]** That is how a production tool keeps a seam smooth
  **across a block interface** instead of making every block independently square at its own
  edge; and the brief's 128-block, 8-ring stack is exactly the configuration where "perpendicular
  to my own ring" and "continuous with my neighbour" are different demands.
- **`EdgeAngleBlend` / `EdgeSpacingBlend`** — the decay profile of the boundary control into the
  interior, with `Exponential` the default. This is GRAPE's `a, b, c, d` and ICEM's
  `Grid Expansion`, i.e. L4's missing knob, exposed as a first-class attribute.
- **`ShapeConstraint` / `ShapeProjection`** — the elliptic solve for a domain on a database
  surface is constrained to that surface, with a stated projection method; and the Solve panel's
  `Project` button "Projects any grids with database constrained shapes to the database using the
  current shape attributes. **Note this command is not available for blocks.**" **[V]**

### 5c. What Pointwise does NOT give you **[V]**

`setPoint` — "This action sets the position of a domain **interior** grid point. … The index must
be for an **interior** grid point." **[V]** **[I]** The one scripted way to move a boundary point
of a structured domain is therefore through the connector that defines the edge, i.e. by changing
the *distribution*, not by assigning a coordinate. Pointwise treats "where the boundary points
are" as owned by the edge's distribution function and by the elliptic BC, and by nothing else.

---

## 6. One more data point, labelled: a multiblock relaxation patent

US 5,453,934 (Taghavi, Behling & Mochizuki; assignee **Cray Research**, not GridPro) describes a
hexahedral mesher whose relaxation moves a surface node "to the midpoint (or center of gravity)
of all of the other directly connected surface nodes", after which "the surface nodes of the
remaining grid are **projected onto the surface definition** of the volume"; it "iteratively
smooth[s] nodes on **corners, edges, and surfaces** of the surface definition by applying a
relaxation algorithm". **[2nd]** — read through an automated extraction of the Google Patents
page rather than the USPTO PDF, and it is a *different tool from the ones the brief asked about*,
included only because it is the one place I found the smooth-then-project pattern written down as
a method claim. **[I]** Smooth-then-project is the cheapest implementable form of "slide along
the boundary": it needs no boundary-tangential equation, only a projection operator — which, for
a declared conic ring, this repo already has in closed form.

---

## 7. Is there a standard answer to "distribute N columns around a body from wall to far field"?

**No, and I looked in the places where one would live. [I] on the absence; [V] on each of the
things that ARE standardised.**

What is published is all about **the wall distribution** and **the radial distribution**, never
about the angular position of a column at an intermediate ring:

- HYPGEN §2.3.5, "Basic Rules on the Construction of a Good Surface Grid", in full: a stretching
  ratio of "1.0–1.3 is best, 1.3–3.0 is acceptable, 3.0 or above is not recommended"; "The grid
  spacings on each side of a convex or concave corner should be about equal"; "The sharper the
  angle of a convex corner, the more important it is to cluster points towards the corner … On
  the other hand, the sharper the angle of a concave corner, the more important it is to **not**
  cluster into the corner." **[V]** All three are rules for the **surface** grid, which is the
  march's initial data.
- The workshop gridding guidelines — first-cell `y+`, `GR1 < 1.25` and its per-level refinement,
  constant-spacing wall band, surface clustering as a fraction of local chord, far-field distance
  — are collected in this repo's `multi-element-airfoil-blocking.md` §5 and
  `cell-size-range-within-a-block.md` §L2/§1c, and none of them bounds a circumferential
  position. **[V] that those are what they bound.**
- GRAPE, Pointwise and ICEM all let the body distribution be anything, and then propagate it:
  GRAPE by solving, Pointwise by `EdgeSpacingCalculation Interpolate` as the default (interpolate
  the boundary spacing along the edge) **[V]**, ICEM by `Copy Parameters`, `Linked bunching` and
  `Match Edges` **[V]**, already catalogued in `cell-size-range-within-a-block.md` §2a.

**[I] The reason there is no rule is that in every published method the question is not posed.**
A column's angular position at ring *r* is an output of the generator — of a march (volume
source terms), of an elliptic solve (interior lines between two prescribed boundaries), or of a
relaxation (GridPro). Only a mesher that writes corner coordinates directly, as this one does,
has to answer it, and that is a property of the architecture rather than a gap in the
literature. The nearest published thing to an answer is the pair of endpoints in L5: the body's
own spacing at the wall, polar/uniform in the far field — stated by Steger & Sorenson in 1980
as a *practice* and by HYPGEN in 1993 as a *parameter*, in both cases as cell areas.

---

## 8. The direct answer: is "move the blend" the right next move?

Four findings, in order of how much they should change the plan.

### 8.1 The variable is right. The brief identified the only free scalar there is. **[V]**

Nakamura's derivation (L2, §1c) says that a point constrained to a boundary has exactly one
degree of freedom, the tangential coordinate, and that enforcing orthogonality consumes it. The
brief's "the angle error lives in the corner's POSITION, not the edge's shape" is that statement
re-derived from measurements. Nothing found contradicts it.

### 8.2 But no shipped tool computes that position from a geometric blend formula. It is SOLVED, or it is the user's, and those are the only two. **[V]**

- Solved: Nakamura UBGR/FBGR; Pointwise `EdgeConstraint Orthogonal`; GridPro, where a corner is
  only "an initial position" in "general position".
- The user's: Pointwise's default `Fixed`; GRAPE ("Any distribution of points on boundaries is
  acceptable"); TTM ("the assignment of the ξ-values to the boundary points … is arbitrary");
  ICEM, where "the vertices can only be moved on the curves that they are projected to" — by
  hand.

**[I]** The brief's blend is a third thing: a *formula* that computes the position without
solving anything, and whose only justification is that the two endpoints it interpolates are
each defensible. That is not a regime the field uses, and the sources say why — a formula cannot
know what the interior needs, which is Steger & Rizk's "cannot be prescribed as this would be
incompatible with the grid developing in the interior". Tuning the blend's weighting is tuning a
guess; the measured 6.51 deg mean is feedback the formula has no way to consume.

### 8.3 The thing most tools do instead is the thing the brief tried and abandoned — and it failed for a reason the vendors document. **[V]**

> **AMENDED by §10.** The claim in this section about what THIS REPO runs is wrong: the
> smoother already carries Thomas–Middlecoff control functions, and the measurement it rests on
> was taken with that smoother switched off.

L3 and L4. Pointwise's four defaults, GRAPE's `THETA(J)`, and ICEM's four
Sorenson/Hilgenstock combinations all fix the boundary point and buy the angle with a **control
function acting on the interior**, with an explicit **decay profile** (`a,b,c,d` /
`Grid Expansion` / `EdgeAngleBlend`). ICEM states the failure mode when that profile is absent:
"the first layer is orthogonal to the boundary but the next layers curve as they equalize". The
brief's item 4 — corner angle improved 3.9 deg, mesh non-orthogonality moved 0.06 deg — is that
sentence, measured.

**[I] So the brief's experiment did not disprove "bend the edge"; it showed that bending an edge
without an interior solve buys only the edge.** This repo fills a block by transfinite
interpolation from its four edges. TFI has no mechanism by which a boundary condition decays
inward with a controllable rate; it blends the four edges linearly (here, by normalised arc
length — `.claude/rules/mesher-multiblock.md:379`), so a corner-angle correction is spread across
the block in whatever way the blend dictates and cannot be concentrated near the wall where it
would matter. Every tool that succeeds at this runs an elliptic solve; this one runs TFI plus a
Winslow smoother. That is the real gap the measurements exposed, and it is not a gap in the
blend.

### 8.4 One shipped tool does blend — HYPGEN — and it is worth separating what it blends. **[V]**

`IVSPEC = 2` + `EPSSS` blends **cell volumes**, from the body's own distribution to a sphere's,
with an exponential rate, during a march; `ITSVOL` controls how much neighbouring volumes are
averaged, with "a small or zero ITSVOL … if it is desired to have the grid points maintain a
similar distribution at each L-shell as that on the surface grid" at one end. Steger & Sorenson
describe the 2-D practice directly: body-proportional control volumes near the wall, "uniformly
spaced in the circumferential direction" far out, "thus in far field a polar coordinate system
is formed."

**[I] The brief's blend and HYPGEN's are the same idea applied to different objects.** The brief
blends **trajectories** (normal direction versus arc-length fraction) and reads positions off
them. HYPGEN blends **target cell areas** and lets positions fall out. The second is strictly
better behaved for one reason that can be stated without a march: a target-area field is a
quantity the mesh can be *measured against*, so a wrong blend shows up as an area ratio you
already compute, whereas a wrong trajectory blend shows up only as the corner angle the brief
had to go and measure specially. It is also the form that survives the two-ring and C-grid cases,
where "the body's normal" stops being well defined at the wake cut.

### 8.5 A caution about the number being optimised. **[M] + [I]**

The brief's item 4 reports a 3.92 deg improvement in **mean corner perpendicularity** against a
0.06 deg change in **mean cell non-orthogonality**. Those are different populations — 256 corners
against ~180,000 cells — and the measurement says they are nearly decoupled. The field bounds the
second (it is Pointwise's `Cell Non-Orthogonality` and ICEM's `Max Ortho` / `Min Ortho`, and it is
what `MbQuality` already reports); I found **no** generator, metric library or workshop guideline
that bounds the first. Before moving the blend to improve a mean angle, it is worth settling which
mean, because the repo's own measurement is evidence that moving one moves the other by about 1.5%
of the amount.

---

## 9. What this bears on, for this repo

> **Items 1 and 3 are AMENDED by §10**, which checked them against
> `.claude/rules/mesher-smoothing.md` — a file this note did not read.

Stated as inference, because none of these sources was written about this tool. **[I]**

1. **Give a ring corner the literature's boundary condition, not a better formula.** The three
   regimes of L1 are a small, finite vocabulary — `fixed`, `floating`, `orthogonal` — and the
   declared conic already supplies what a solver needs: a parametrisation to solve the tangential
   coordinate in, and an exact evaluation to turn that coordinate back into `(x, y)`. Nakamura's
   §4 is the whole algorithm (discard the normal-direction equation, zero the cross term, solve
   one tridiagonal relation in `s`, evaluate the boundary). Starting at `fixed` — which is what
   the repo has — and adding `orthogonal` per ring is a smaller change than it sounds, and it is
   the change that turns a guess into feedback.
2. **If the blend stays, blend TARGET AREAS, not trajectories (§8.4).** It is the shipped form, it
   degrades gracefully, it is measurable against a quantity the repo already computes, and it does
   not need a well-defined body normal — which the C-grid wake cut does not have.
3. **The missing decay control is the real finding of §8.3.** Every elliptic generator read here
   exposes how fast a boundary condition decays inward (`a,b,c,d`, `Grid Expansion`,
   `EdgeAngleBlend`). This repo's TFI has no such parameter and cannot acquire one without an
   interior solve. If "the mean angle is the number to move" turns out to mean *cell*
   non-orthogonality rather than corner angle, then the honest next move is an interior
   elliptic/Winslow pass with a boundary angle target, not a change of corner placement — and
   `MB_SMOOTH_ITERS` is already the right seam for it.
4. **`EdgeAngleCalculation Adjacent` is worth remembering when the smoother grows a boundary
   angle target.** In a 128-block stack, "square to my own ring" and "continuous with my
   neighbour across the seam" are different demands, and Pointwise's answer is to let the target
   be inherited from the adjacent grid. A per-ring choice between `Orthogonal` and `Adjacent`
   costs one enum.
5. **Do not report corner perpendicularity as a quality figure without the cell metric beside it
   (§8.5).** Nothing in the field bounds it, the repo's own measurement shows it nearly decoupled
   from the metric that *is* bounded, and this is the same shape of error that
   `cell-size-range-within-a-block.md` §L1 recorded for within-block area range.

---

---

## 10. Correction: what this repo ALREADY has, and what §8.3 and §9 therefore overstate

Added after the note was handed back, by checking §8.3's claim about this repo against
`.claude/rules/mesher-smoothing.md`, which this note did not read. **[V in-repo]** — verified in
this repository's own rule file, not in a vendor source.

**§8.3 says "this one runs TFI plus a Winslow smoother" and §9.3 says the repo "cannot acquire
[a decay control] without an interior solve". Both understate what is there.** The Winslow
smoother already carries control functions, and they are the same family the vendors ship:

> "**BEYOND THE FIRST ROW THE OFF-WALL SOURCE IS THOMAS-MIDDLECOFF ON THE LINE'S OWN SPACING**,
> and the along-wall source is Thomas-Middlecoff at BOTH ends of the off-wall direction, blended
> LINEARLY in the normalized logical coordinate."
> — `.claude/rules/mesher-smoothing.md:235`

So the interior solve exists, the boundary condition is already propagated inward, and §1d's
"Thomas–Middlecoff … named in the tools, not read here" describes a scheme this repo has
implemented. Three consequences, and they move two of §9's five recommendations.

1. **The decay control is not missing — it is present and LINEAR, and the repo recorded its own
   reason for that choice**: *"The blend is LINEAR because a decay rate is a constant with no
   derivation behind it."* (`mesher-smoothing.md:242`). **§5a of this note answers that
   objection**: Pointwise ships `EdgeAngleBlend < Exponential | Linear | value >`, so `Linear` is
   one of three named options a production tool offers, not an absence of the control. What the
   repo lacks is the *choice between* them, not the control. That is a far smaller change than
   §9.3 implies, and it is the one §9.3 should have named.

2. **A direct boundary-angle source term was already tried here and REJECTED, with measurements.**
   > "The HEIGHT is solved for exactly. The 90 DEGREES has NO term stating it … A DIRECT condition
   > on the angle (Steger-Sorenson projected onto `r_s`) goes as `1/h²`, clips and destabilises,
   > and is one of **three weaker versions measured and rejected**."
   > — `mesher-smoothing.md:224-228`

   §9.1 recommends "adding `orthogonal` per ring". Read against this, that recommendation is only
   live if it means something different from what was rejected — and it does. **The rejected
   thing is a SOURCE TERM in the interior solve (Steger–Sorenson, §1b). Nakamura's UBGR (§1c)
   moves the BOUNDARY POINT and is a different mechanism**: it discards the normal-direction
   equation and solves one tridiagonal relation in the tangential coordinate `s`. Nothing in this
   repo has tried that, and the `1/h²` conditioning that killed the source term does not arise in
   it. **The distinction between the two is the single most actionable thing in this note, and the
   note as handed back blurred them.**

3. **§8.3's diagnosis of the requester's item 4 survives, but not its stated cause.** "Bending an
   edge without an interior solve buys only the edge" is right about the measurement and wrong
   about why: the measurement was taken at `MB_SMOOTH_ITERS 0`, with the interior solve
   **deliberately switched off**, because at its default of 20 it degraded the size distribution
   (ring-seam max 1.101 → 1.672 on that mesh; `README.md` of the 4412 curve study). So the
   experiment did not show that TFI cannot carry a boundary condition inward. It showed that *the
   solve that would carry it* was not running, for an unrelated and separately measured reason.
   The open question is therefore narrower and sharper than §8.3 states: **can the existing
   control functions hold a boundary angle without the size-distribution cost that made the
   smoother worth turning off?** Nothing here answers that, and it is a cheap experiment —
   `MB_SMOOTH_ITERS` against both metrics at once, which is what `mesher-smoothing.md` already
   demands of every claim about that cap.

**What this does not change.** L1–L6 and §8.1–§8.2 are about the literature, not about this repo,
and are unaffected: the position of a boundary point along its boundary is a named boundary
condition with three regimes, it is solved or it is the user's, and no shipped tool computes it
from a geometric blend formula. §9.2 (blend target areas, not trajectories) and §9.5 (do not
report corner perpendicularity alone) also stand.

## Gaps I could not close, by name

1. **Pointwise's user-manual boundary-conditions page.** `pointwise.com` 301s to `cadence.com`,
   which answers **403** behind Cloudflare, and the Internet Archive has **no capture of
   `…/structured-domains-and-blocks/edge-attributes-tab/boundary-conditions.html` under either
   host** (it has the tab's `index.html`, `solve.html` and the 2018 section index, but not the
   four leaf pages). The prose definitions of `Fixed` / `Floating` / `Orthogonal` / `Adapt` in
   §5a are therefore **[2nd]**, from a search-result extract. The Glyph enumerations and defaults
   they corroborate are **[V]**.
2. **Pointwise's `boundary-control-functions.html`, `angle-controls.html` and
   `spacing-controls.html`** — same three leaf pages, same absence. Everything in §5b comes from
   the Glyph reference's one-line attribute descriptions, so I have the option sets, the types
   and the defaults, and **no explanation of what `Interpolate` interpolates between** or how
   `Adjacent` resolves at a corner where more than two grids meet.
3. **Thomas & Middlecoff (1980) and Hilgenstock (1988).** Both are named by both commercial tools
   and neither is open-access (*AIAA Journal* and *Notes on Numerical Fluid Mechanics*
   respectively). **I did not read either.** §1d rests entirely on the vendors' one-sentence
   descriptions of what they do.
4. **GridPro's own manuals, again.** `User_Guide_for_TIL` and `WS_GUI_Manual` are behind a HubSpot
   registration form, and the FAQ cites them by section for every answer. I therefore have **no
   primary statement of what Ggrid holds fixed during relaxation** beyond the 1995 paper's
   "relaxed towards its equilibrium that progressively satisfies the underlying variational
   scheme", and §3b's mechanism is inferred from a 1987 precursor report.
5. **The GridPro variational functional.** Still not seen — the same gap
   `cell-size-range-within-a-block.md` recorded, now narrowed rather than closed: it is
   *mean-value relaxation* (Eiseman, *ASME J. Fluids Engr.* 107, 1985, 477–483), which I also
   could not read. DTIC `ADA259958` returns a 1.4 KB HTML stub, not the PDF.
6. **ICEM's projection rule.** The help pages say a vertex is projected "to their respective
   entity" and never say to *which point* of a curve. Closest-point is the obvious reading and is
   **[I]**, not verified; I found no ICEM page that states it.
7. **Whether Pointwise's `EdgeConstraint Orthogonal` is Nakamura's UBGR or something else.** The
   behavioural description matches (§5a), and `Orthogonal` being 2-D-only matches Nakamura's
   derivation being two-dimensional, but Cadence cites no literature in the Glyph reference and I
   could not reach the manual page that might.
8. **Numeca / Cadence AutoGrid**, the one tool `cell-size-range-within-a-block.md` could not
   answer at all, is still unanswered: the AutoGrid5 User Guide is not published openly. A
   turbomachinery tool with built-in O/H templates is the most likely place for a *published rule*
   about where a template's corner goes, and that remains unchecked.
9. **I did not re-derive any of §0.** The 4412 case is not in the tree; every figure there is the
   requester's, marked **[M]**, and nothing in this note's conclusions depends on their exact
   values — only on their signs and on the ratio in §8.5.
10. **Steger & Chaussée (1980), *SIAM J. Sci. Stat. Comput.* 1(4)**, the original hyperbolic
    paper, is paywalled. §2 uses the NASA conference paper by Steger & Sorenson and NASA TM 86753
    by Steger & Rizk, both of which I read, in its place.

---

## Sources

Primary, read by me:

- Thompson, J. F., Thames, F. C. & Mastin, C. W., *Boundary-Fitted Curvilinear Coordinate Systems
  for Solution of Partial Differential Equations on Fields Containing Any Number of Arbitrary
  Two-Dimensional Bodies*, NASA CR-2729, 1977 — https://ntrs.nasa.gov/citations/19770021145
  (pp. 9, 13, and the time-dependent-redistribution section).
- Sorenson, R. L., *A Computer Program to Generate Two-Dimensional Grids About Airfoils and Other
  Shapes by the Use of Poisson's Equation* (GRAPE), NASA TM 81198, 1980 —
  https://ntrs.nasa.gov/citations/19800017767 (Summary; Introduction; Theoretical Development,
  the "back-solve for P and Q" passage and the exponential-decay paragraph; the `THETAI`,
  `THETA(J)`, `THOBI`, `THETOB(J)`, `NDS`, `DSI` variable descriptions).
- Nakamura, S., *Generation of Orthogonal Grids By Boundary Grid Relaxation*, NASA CR-166523
  (Ohio State University, under NASA Ames contract), 1983 —
  https://ntrs.nasa.gov/citations/19830027436 (Abstract; §1; §2–3; §4 UBGR; §5; §6 FBGR).
- Steger, J. L. & Sorenson, R. L., *Use of Hyperbolic Partial Differential Equations to Generate
  Body Fitted Coordinates*, in *Numerical Grid Generation Techniques*, NASA CP-2166, 1980 —
  https://ntrs.nasa.gov/citations/19810006209 (the equation slides, the control-volume-grid
  slide, the fuselage and C-grid slides, the advantages/disadvantages slide).
- Steger, J. L. & Rizk, Y. M., *Generation of Three-Dimensional Body-Fitted Coordinates Using
  Hyperbolic Partial Differential Equations*, NASA TM 86753, 1985 —
  https://ntrs.nasa.gov/citations/19850023574 (the smoothing/implicitness passage, and the
  "Boundary Surfaces" section).
- Chan, W. M., Chiu, I.-T. & Buning, P. G., *User's Manual for the HYPGEN Hyperbolic Grid
  Generator and the HGUI Graphical User Interface*, NASA TM 108791, 1993 —
  https://ntrs.nasa.gov/citations/19940011311 (§1; §2.3.4 `IVSPEC`/`EPSSS`/`ITSVOL`/`IMETH`/
  `SMU2`; §2.3.5; §2.4.1).
- Eiseman, P. R., *Multiblock Grid Generation with Automatic Zoning*, Program Development
  Corporation, NASA conference paper, 1995 — https://ntrs.nasa.gov/citations/19950022314
  (the wire-frame/"general position" passage, the corner definition statement, the surface
  definition statement incl. the floating surface, the run-schedule passage).
- Cheng, Z. & Eiseman, P. R., *Examples of Grid Generation with Implicitly Specified Surfaces
  Using GridPro/az3000*, 1995 — https://ntrs.nasa.gov/citations/19950022351 (the "initial
  position" corner definition).
- Eiseman, P. R., *Grid Generation on Surfaces in Three Dimensions*, Final Scientific Report,
  NASA grant NAG-1-617 (Columbia University / NAVSEA), 1987 —
  https://ntrs.nasa.gov/citations/19870017991 (mean-value relaxation, unit weights and cell-area
  equalisation, the curvature weight).
- Sudharshanam, V., Ebenezer, S. & Eiseman, P., *GridPro — Higher order meshes*, HiOCFD5, 2015 —
  https://acdl.mit.edu/HOW5/WorkshopPresentations/GridPro_HO_Meshes.pdf (slides 4–6).
- GridPro, *Frequently Asked Questions* (v10), gridpro.com documentation page →
  `https://22821077.fs1.hubspotusercontent-na1.net/hubfs/22821077/Version 10 documents/FAQs.pdf`
  (S19–S31, T10, and the singularity/surface-assignment answers).
- Glyph 3.18.x reference (Cadence/Pointwise), via the Internet Archive raw captures
  `web.archive.org/web/20231202012148id_/…/GlyphDomainStructured-cxx.html` and
  `…/20230529054117id_/…/GlyphBlockStructured-cxx.html`: `EdgeConstraint`, `FaceConstraint`,
  `EdgeControl`, `InteriorControl`, `EdgeAngleCalculation`, `EdgeAngleBlend`,
  `EdgeSpacingCalculation`, `EdgeSpacingBlend`, `SolverEngine`, `ShapeConstraint`,
  `ShapeProjection`, `setPoint`, `getEllipticSolverResidual` — with their stated defaults.
  Live URLs (403 today): https://www.pointwise.com/doc/glyph2/
- Fidelity Pointwise User Manual, *Solve Tab* and *Edge-Face Attributes Tab*, via the Internet
  Archive captures `20230401232829` and `20230401234316` of
  `www.pointwise.com/doc/user-manual/grid/solve/structured-domains-and-blocks/`.
- Ansys ICEM CFD Help Manual, Release 2025 R1 (public):
  `.../icm_help/iedit_smoothhexameshortho.html` (the smoother description, the Smooth-type and
  Structured sub-options, Freeze Options, Release Orthogonality, Grid Expansion),
  `.../icm_help/iblock_projvert.html` (Snap Project Vertices),
  `.../icm_help/iblock_assocvert.html` (Associate Vertex),
  `.../icm_help/iblock_movevert.html` (Move Vertex; the green-edge constraint),
  `.../icm_help/iblock_assoc.html` (the association menu).
  https://ansyshelp.ansys.com/public/Views/Secured/corp/v251/en/icm_help/

Secondhand, labelled as such in the text:

- A search-engine extract of the unarchived Pointwise *Boundary Conditions* page (§5a).
- US Patent 5,453,934 (Cray Research) via an automated extraction of its Google Patents page (§6).

In this repo:

- `docs/research/arc-length-correspondence-on-an-offset-ring.md` — the offset/Frenet relation that
  §0's item 3 is the other side of.
- `docs/research/cell-size-range-within-a-block.md` — §2a/§2b/§2d (ICEM, Pointwise and HYPGEN
  distribution mechanisms), §3 (GridPro's `nest`/clamp answer), §L4 and §1c (the published
  size and growth-rate bounds), all deliberately not restated here.
- `docs/research/multi-element-airfoil-blocking.md` §5 — the workshop gridding figures §7 refers to.
- `.claude/rules/mesher-multiblock.md:190` (the `curve` conic kinds), `:379` (`coons` blends by
  normalised arc length, and the 6927% that forced it) — the two in-tree anchors §8.3 rests on.
