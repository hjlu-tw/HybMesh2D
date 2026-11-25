# GridPro's blocking method, and what reproducing it here would take

**A RESEARCH NOTE.** Not `.claude/rules/*.md` (what the rule is), not `docs/design_notes/`
(why a shipped rule was chosen). It records what GridPro's own blog, manual, FAQ and shipped
tutorial actually say about how a GridPro user decomposes a 2-D region into blocks, so that a
decision to imitate — or deliberately not imitate — that model in this repo's `MESH_MODE 1`
path can be argued from sources rather than from a vendor's marketing. Nothing here is
binding; no rule, gate, test or source file was changed to write it. 2026-11-05.

**Subject.** The maintainer asked for GridPro's 分區方式 (block-decomposition method) off two
GridPro blog posts, well enough that this repo could attempt the same blocking as a
`MESH_MODE 1` topology document. The two posts turned out to be an *opinion* piece and a
*topology-families* piece: neither describes the mechanism. The mechanism is in GridPro's GUI
manual, its FAQ, and — decisively — in the 2-D airfoil tutorial GridPro ships with the
program, whose topology file, internal-surface geometry and final quality report are all
readable text. This note is built on those, with the blog posts used for what they are good
for: the family comparison and the sizing numbers.

## How to read the markers

- **[V]** verified in a primary source I read myself (the vendor's own page body, manual,
  FAQ, tutorial PDF or shipped data file; a NASA page's own text).
- **[I]** my own inference or derivation from a **[V]** fact — including arithmetic I did on
  a **[V]** data file. Stated as reasoning, not fact.
- **[2nd]** I could only find this secondhand. Treat as unconfirmed.

Where a claim is read off a **picture** rather than text, it says so in the claim itself.

---

## Lead: the three answers a reader needs first

### L1 — GridPro's blocking input is a *coarse wireframe that is allowed to be in the wrong place*, and that is the whole method. **[V]**

The GUI manual states it as a rule with a name:

> "GridPro **essentially reduces grid generation to topology generation**. The primary user
> input is a pattern of points referred to as the grid topology."

> "It partially automates topology generation by **reducing the user task to generate a coarse
> wireframe of the topology in which only imprecise corner and edge information is required**;
> while the blocks and block faces are automatically generated from the wireframe."

> "Remarkably, GridPro can also grid **loosely positioned topology**… A wireframe topology does
> not have to exactly fit the boundaries for the region to be gridded. However, **the topology
> itself should be precise**. If a topology is positioned too far from a surface, the gridding
> process might take longer than it normally should… you would do well to remember this
> **golden rule: the topology for a region has to be precise but does not have to be positioned
> precisely, just positioned to roughly follow the geometry of its bounding surfaces**."

> "GridPro employs a powerful proprietary **Dynamic Boundary Conforming (DBC)** technology,
> which **automatically morphs the topology wireframe grid into conformity with the bounding
> geometry**, generating a multi-block grid."

— *GridPro GUI Manual*, Version 1.0, 24 September 2014, §1.1–§1.2 (pp. 2–4) and §4.1 (p. 83).
Retrieved from the Internet Archive snapshot of
`http://sp.gridpro.com/docs/WS_GUI_Manual.pdf` (capture `20150505181147`), because the live
`sp.gridpro.com/docs/` now 301-redirects every PDF to `gridpro.com/signin` — see §7.

**[I]** So the *topological* content (which corner links to which, what the block graph is) is
exact user input; the *geometric* content (where the corners are) is an initial guess. That is
the opposite split from this repo, where a corner's position is exact — either coordinates or
a normalized arc length on a named segment — and nothing moves it afterwards.

### L2 — GridPro's own 2-D airfoil tutorial blocks a single-element section into **14 blocks / 4608 cells**, with the sharp trailing edge resolved by **three straight "internal surfaces"** radiating from it to the far field. **[V]**

The quality dialog at the end of `Tutorials/Medium/Tutorial_1_Airfoil/Tutorial_1_Airfoil.pdf`
(Figure 36, p. 20) reports, verbatim, for the finished grid:

| field | value |
|---|---|
| No of Blocks | **14** |
| No of Cells | **4608** |
| No of Folds | **0** |
| Worst Skew | **0.255576** ("A skew of 0 is good and 1 is bad") |
| Max Aspect Ratio | **2.58781** ("Ideal block should have an aspect ratio of 1") |
| Max Warpage | **0** ("Exist only for 3D grids") |

**This corrects `docs/research/cell-size-range-within-a-block.md` §3**, which says a 2-D
aerofoil block count "gets no answer from this tool's documentation: the question is not posed
to the user." It is posed and answered, in GridPro's own shipped tutorial; that note's gap
entry 2 named `sp.gridpro.com/docs/WS_10.0_Tutorials.zip` as unreachable, and the **2014**
`ws_Tutorials.zip` at the same path *is* archived and does contain it.

### L3 — The repo already owns most of GridPro's declarative half, and none of its solver half. **[I] on the mapping; [V] on each side.**

> **The blocking was then BUILT and MEASURED — §8.** Two runnable cases live under
> `docs/research/gridpro-blocking-method/`. The reproduction lands on **14 blocks, four
> corners on the aerofoil and eight on the circle**, against the tutorial's 14, four and
> "about nine" — with 0 inverted cells and the wall first cell held to 0.014% of what the
> declaration asks for. Two of the rules this note recovered from GridPro's manual bit from
> the inside while it was being built, and §8e is what they cost.
>
> **And then refined the way the post's own FIGURES arrange it — §9.** N concentric rings by
> 2K sectors, up to **58 blocks** at the same 17408 cells. More SECTORS is free and works;
> more RINGS looks far more like the figures and measures worse here. §9d is a result about
> GridPro's own rule: equal bisection CAPS the trailing-edge fan at three on a thin section.
>
> **And then the block BOUNDARIES were made curves — §10**, which is what GridPro's figures
> show and what §9 still had as straight chords. The curvature cannot be relaxed into
> existence here (§10b: the smoother diverges at sweep 13 and folds cells at 20), so it is
> DERIVED — and the result is the best mesh in this note, the only one the wall-control
> function holds everywhere without clipping.
>
> **§11 is the correction to all of that.** Three causes were found for the partition still
> not looking like GridPro's, and two are mine: every figure was the TRIANGLE-split export
> against GridPro's quads, §9a MISREAD fig5 (its outer field is ONE layer of sectors, not
> two), and §10's arcs kinked at every ring crossing. The shipped case is now **38 blocks,
> 2 rings x 16 sectors**, which is both the arrangement the figure shows and the best mesh
> here on both non-orthogonality columns.
>
> **§12 is where this stops, with a NEGATIVE result.** GridPro's single-body far field is a
> C/H arrangement — a straight wake band and a Cartesian lattice against a RECTANGLE — not an
> O-fan against a circle. `--box` reaches the rectangle and measures much worse (89.2° against
> 48.1°), the nested-box H field that would fix it FOLDS for a reason that is arithmetic, and
> what it would really take is a different topology document.
>
> **§13 then BUILT that document.** A C/H topology, 24 blocks, and it is the best mesh in this
> note on mean non-orthogonality (**4.30°** against the O-ring's 7.14°) and on size grading
> (**7.8** against 14.1), with the far field a rectangle the grid is aligned to. Five defects
> found on the way are in §13c, including one where **GridPro's own equal-bisection rule
> cannot be used** — its trailing-edge ray lands behind the next station's and the radials
> cross.
>
> **§14 then put it through the SOLVER — gate 2, the one that bit on this repo's C-grid.** It
> does **not NaN**: 10000 iterations, exit 0, nothing non-finite, against the shipped C-grid
> run identically as a control. Its residual does STALL about 30× above the control's floor,
> at both domain sizes. Its residual STALLS 23-35× above the control's floor — **§16 finds
> out why, and it is the leading-edge clustering: `--turn-blend 0.6` takes it to 8.85e-07,
> below the shipped case's own floor, at the cost of the 10° leading-edge angle §15a was
> pleased about.** The control
> is **the repo's own four-block C-grid, which §13e now shows is the better mesh** — 31.4°
> worst corner against the best 48.1° built here, at two thirds of the cells. §§9-13 are a
> reproduction of GridPro's ARRANGEMENT and a record of what each step cost; they are not a
> better grid for this body.

| GridPro | this repo |
|---|---|
| wireframe corners + links, exact topologically | `corners` / `edges` / `blocks`, exact topologically **[V]** |
| corner position is a guess; DBC relaxes it onto the surface | corner position is a declaration; **nothing moves it** **[V]**, `.claude/rules/mesher-multiblock.md` |
| corner→surface *assignment* | `kind: "on_geometry"` + `binding` / `follows`, by **arc length** **[V]** |
| edge *density* (cells per edge), default 8 | `count`, a **seed** that propagates across shared edges **[V]** |
| `clu` / off-wall spacing + stretch ratio per surface | `spacing: {wall_ends, ds_start, ds_end}` + `BL_INITIAL_THICKNESS` **[V]** |
| Ggrid relaxes to near-orthogonality over 10⁵ sweeps | `MB_SMOOTH_ITERS` Winslow, default **20**, wall nodes frozen **[V]** |
| `nest` / `reverse_nest` / clamps / sleeve surfaces | **nothing** |
| surface projection of a non-conforming framework | **nothing** |

---

## 0. What is new here, against the three notes that overlap

Read first, as instructed: `cell-size-range-within-a-block.md` (§3 is a GridPro section),
`multi-element-airfoil-blocking.md`, `where-a-block-corner-sits-on-its-ring.md` (§3 is a
GridPro section).

New in this note, and not in any of them:

1. **The two blog posts themselves**, read in full. The prior notes used Eiseman's 1995 NASA
   CP paper, the v10 FAQ and the HiOCFD5 slides; none used either blog post.
2. **The GridPro GUI Manual**, 184 pages, recovered from the Internet Archive. Both prior
   notes list it as behind a registration form and unread. It supplies the golden rule, DBC,
   the full-face-matching rule, the wrap/inner-layer construction, the default edge density,
   and the file set.
3. **GridPro's shipped 2-D airfoil tutorial** — the topology file, the three internal-surface
   coordinate files, the edge densities, and the final block/cell/skew report (L2). This is the
   first concrete, numbered GridPro 2-D aerofoil blocking in this repo's notes.
4. **The singularity-valence rules** from the FAQ (§1e) — a 2-D blocking rule this repo can
   apply directly and currently does not state anywhere.
5. **One correction** (L2), and **one nuance correction**: GridPro's blog attributes the
   500-chord far field to NASA "for sequential grids generated for grid convergence study";
   NASA's own stated reason is different (§5).

Nothing here contradicts `where-a-block-corner-sits-on-its-ring.md` §3 ("a corner is an initial
guess"). The manual's golden rule is the same claim in the vendor's own words, from a document
that note could not reach, and the tutorial's "**Drag the corners and position them
approximately** as shown in figure 15… **for the grid to converge faster a better positioning
is required**" is the operational consequence. **[V]**

---

## 1. The method: what a GridPro user actually hands the program

### 1a. The four stages, as GridPro names them **[V]**

> "The grid generation process in GridPro is primarily consists of four sequential process;
> they are 1. Surface preparation 2. Topology generation 3. Grid generation 4. Property
> setting." — GUI Manual §1.2, p. 3.

and the airfoil tutorial draws its own pipeline on p. 2 as:

> "Surface → Wireframe (+ Internal surface) → Assign → Grid (Density, Quality)" **[V]**

> "Topology generation contains two parts: (a) wireframe construction, and (b) **surface
> assignments**." — GUI Manual §1.2, p. 4. **[V]**

### 1b. The wireframe, and the rules it must satisfy **[V]**

> "In two dimensions, gridded blocks are represented by **convex quadrilaterals**, or quads…
> GridPro will read only topologies containing **"full face matching."**… In other words, **one
> side of one quad cannot intersect one side of two other quads**." — GUI Manual §4.1, p. 84.

> "If a surface is smooth, decompose the surface, as you normally would, then create an
> **"inner layer"** between the smooth surface and decomposed block… this example shows how
> topology is **wrapped** around the continuously curved portion of the surface. The figure
> formed by the dark lines is considered a partial **"wrap."**" — GUI Manual §4.1, p. 87.

A further rule appears only in the tutorial, and it is the one that explains the block count:

> "NOTE: This structure also satisfies the rule of surface assignments, "**Two faces (edges in
> 2D) of a same block cannot be assigned/associated to a single surface.**" for the circle."
> — Tutorial 1 (Airfoil), p. 8. **[V]**

**[I]** That rule is why a GridPro far field made of ONE circle needs as many outer blocks as
it has corners on that circle, and it is the structural constraint that forces the extra ring
(see §6c).

### 1c. The files **[V]**

| file | what it is | source |
|---|---|---|
| `*.fra` | the topology (wireframe + surface assignments). "All user-defined topology files must have the extension '*.fra'." | GUI Manual §2.3.3, p. 42 |
| `_ws.fra` | "the file that is used by" the grid engine; keeps four backups `_ws.fra.~1~` … `~4~` | GUI Manual §2.3.3, p. 44 |
| `_auto.fra`, `_auto.undo`, `_undo.stack`, `_az.fra` | autosave, every 2 minutes by default | GUI Manual §2.3.3, pp. 42–43 |
| `_ws.sch` | **the schedule file**; "The gridding process is controlled by a schedule file (`_ws.sch`)" | FAQ G41 |
| `blk.tmp` | "GridPro saves grids to the default file name as `blk.tmp`" | GUI Manual §2.3.5, p. 45 |
| `dump.tmp` | the restart dump; Restart Ggrid takes a file "having `.tmp` or `.grd` extension" | GUI Manual §2.3.21, p. 58 |
| `badB.tmp` | "a grid file which would be created as soon as the gridding process is started. This will have the **blocks information which are highly skewed based on the position**." | FAQ G43 |
| `*.conn_m` | block-merge connectivity written by the merge utilities | FAQ (merge answers) |
| `*.lin` | a 2-D curve: first line is the point count, then `x y z` per line | tutorial data files **[I]** from reading them |

**The actual TIL, from the shipped tutorial** (`airfoil.fra`, 240 bytes, dated 2012-07-23) —
this is GridPro's own text, not a reconstruction: **[V]**

```
SET DIMENSION 2
SET GRIDDEN 8
SET DISPLAY.SURF ON

COMPONENT main()
BEGIN
  INPUT 1 surf(sOUT (0..0));
  INPUT 2 corn(sIN (1:1..1));
END

COMPONENT surf()
BEGIN
s    0 -linear "S830.lin"	;#TIL:1:1
END

COMPONENT corn(sIN s[0..0])
BEGIN
END
```

**[I]** `SET GRIDDEN 8` is the base edge density the manual names ("Every edge has a default
density of 8, which is called as base density", GUI Manual §4.2, p. 100 **[V]**). `s 0 -linear
"S830.lin"` is a surface declaration: index, type flag, file. The corner block is empty here
because this is *step 1*, before any corner exists — the file is the surfaces-only starting
state the tutorial tells you to save. **I did not obtain a `.fra` with corners and `-s`
assignments in it**, so I cannot quote the corner/assignment syntax; see §7. The brief's
guessed `-s` / `-s` label spelling is attested only as a **command-line** flag (`clu … -s
<surface id> <spacing> <growth ratio>`, FAQ G47 **[V]**), not as a corner attribute.

### 1d. The schedule file and Ggrid **[V]**

The shipped sample (`Tutorials/Basic/Tutorial_1_Square/_ws.sch`, 140 bytes), verbatim:

```
#This is a sample schedule file. You may edit it.
step 1: -c all 1.0 0 -C all 1.0 24 -r -S 100 -w 

write -f blk.tmp
write -D 0 -f dump.tmp
```

Around it:

- "If the topology is valid, a window will pop-up to **schedule** the generation engine… All
  the edge densities of the topology can be **doubled, quadrapled, halved or quartered.
  Density designates to cell count per edge**… In the schedule file, density can be scaled by
  **any multiplier**." — GUI Manual §2.3.19, p. 38. **[V]**
- "The **dump frequency is the sweep interval** after which the output grid is rewritten. This
  is typically a multiple of hundred." — same. **[V]**
- "The gridding process is set to **stop only after 100000 sweeps by default**, however the
  user can change the settings by modifying the schedule file. **Since the gridding process do
  not stop depends on the convergence**, the user has to analyze the quality of the grid at
  frequent intervals." — FAQ G15. **[V]**
- "**Instead of running the gridding process with full density** for a complex geometry, the
  density should be **gradually increased to full density**. This can be done by modifying the
  schedule file manually." — FAQ G42. **[V]**
- `Start Euler` / `Restart Euler` "**ignores all the clustering parameters and offwall spacing**
  of the topology" — GUI Manual §2.3.19/§2.3.21; FAQ G45 says the same. **[V]**
- `Gridden` "changes the edge density **dynamically**" while Ggrid is running — GUI Manual
  §2.3.22, p. 59; FAQ T31. **[V]**

**[I]** So Ggrid is a *relaxation that never terminates on a convergence test* — it runs to a
sweep cap and the user judges. This repo's `MB_SMOOTH_ITERS` is the same shape (a fixed
iteration count, default 20) at four orders of magnitude less, which is consistent with the
difference in what the two are relaxing: GridPro is still moving every boundary node onto its
surface, this repo's smoother is not allowed to move a wall node at all.

### 1e. Surface assignment, internal surfaces, and the valence rules **[V]**

Assignment:

> "After completing the wireframe, an association between wireframe and surfaces is required;
> which is done by **assigning appropriate wireframe corners to the respective surfaces**. This
> is called assignments or association in GridPro." — GUI Manual §1.2, p. 4.

**An internal surface is GridPro's name for what this repo calls a cut or a seam**, and the
tutorial says so outright:

> "An **internal surface** is a surface for which **both sides of the surface are to be
> gridded**… The grids on both sides of an internal surface will be **matched** on the surface.
> **A typical example is the wake of flow over an air foil**." — Tutorial 1, p. 14. **[V]**

> "Basic rules to create internal surface: 1. It should **exactly pass through/touch the sharp
> feature** of the geometry. 2. It should **bisect the angle equally at the sharp feature**.
> 3. It should be a **closed surface or extend till the farfield** (It cannot be a hanging
> surface). 4. It should be a **smooth surface**. To obtain a high grid quality, it is
> desirable to have internal surfaces **relatively flat**. 5. It should be created with the
> final grid in mind. Since the block boundaries will be assigned to the internal surface, the
> **grid lines would align itself along the internal surface**." — Tutorial 1, p. 14. **[V]**

Their orientation is a surface property: "Change the orientation of the surface to '**2 Sided
with auto match**'" — Tutorial 1, p. 16. **[V]**

**The valence rules**, which are the most directly transferable blocking rule I found, from
FAQ T13–T15, verbatim: **[V]**

> "The corners which are being assigned to the **external** surfaces should have **two adjacent
> blocks** on either one of its normal sides whereas in case of **internal** surfaces, it should
> have **two blocks on both of its normal sides**. In other words, **there should be three edges
> emerging out of the assigned corner in case of external surfaces and 4 edges emerging out in
> case of internal surfaces in 2D**."

and the three named failures:

| name | 2-D condition at a corner assigned to an **external** surface | at an **internal** surface | stated fix |
|---|---|---|---|
| very severe singularity | **2** edges emerge | 3 edges | "external wrap outside" |
| (correct) | **3** edges | 4 edges | — |
| mediumly severe singularity | **4** edges | 5 edges | "internal wrap" |
| mildly severe singularity | "3 or more edges emerges out of a **fixed** corner" | — | surface-by-surface wrap (convex) or an internal surface (concave) |

**[I]** Translated to this repo: a corner declared `on_geometry` on a wall should have exactly
**three** edges naming it — the two wall segments either side, and one radial. The repo's
shipped `cgrid_naca0012.json` puts **five** edges on `te`; by GridPro's table that is two steps
past "mediumly severe". GridPro's own airfoil tutorial *also* trips this: "It will pop out a
message saying that the topology is having **Mediumly severe singularity**… Click on 'Ok' to
proceed to grid generation." **[V]** — so it is a warning and a quality signal, not a refusal,
in GridPro too. The repo has no equivalent diagnostic; §6d.

### 1f. Clustering and smoothing **[V]**

> "**E-wall parameter is the off-wall spacing** used for clustering within the grid generation
> engine… The number you insert in the **Off wall spacing** field is the length of the cell edge
> measured between a boundary grid point and the next closest "off-wall" grid point. The ratio
> between this length and the cell edge length measured between the off-wall grid point and the
> next off-wall grid point is the number you input in the **stretch ratio** field. This number
> becomes the ratio for a **geometric progression** of cell edges, which propagates outward from
> the boundary surface along off-wall grid points. Typically, the value of off wall spacing is
> **less than 0.001 of the length of the boundary**. The stretching value usually lies
> **between 1.1 and 1.5**." — GUI Manual §3.4.8, pp. 78–79.

> "The parameter **Multi-grid** ensures that the number of cells (in the normal direction) in
> the adjacent block is a **multiple of this parameter**. It is a unique value for the entire
> topology." — same, p. 79.

> "This quality comes in the form of **near orthogonality, smoothness, low warpage, and
> curvature clustering for both concave and convex boundaries**." — GUI Manual §1.1, p. 2.

> "**I fix the wavy lines on the grid?** Sometimes, you may see wavy lines on the grid instead a
> straight lines. It is because of the **aspect ratio of the cells**; in such cases, **increase
> the density of the edges** to reduce the aspect ratio." — FAQ G44.

**[I]** Two things matter for this repo. First, **clustering is a property of a SURFACE, not of
an edge** — which is why GridPro never asks "what is the distribution on this edge". Second,
the stretch ratio is a *geometric* progression, where this repo's default law is `tanh` with
the wall height solved for by bisection (`.claude/rules/mesher-spacing.md`); a GridPro
clustering spec therefore does not transfer as a number, only as a wall height plus a ratio
band (§5).

---

## 2. The airfoil post specifically

Source: *The Art and Science of Meshing Airfoil*, Ravindra Krishnamurthy, 6 November 2017,
https://gridpro.com/blog/the-art-and-science-of-meshing-airfoil/ — "2098 words / 11 minute
Read". The post body came back as a summary through WebFetch; I re-fetched the page with
`curl` and extracted the article text and the `<img alt>` strings directly, so every quote
below is from the page's own HTML. **[V]**

### 2a. The post is a comparison of three families, not a description of a workflow **[V]**

It does **not** name a single GridPro file, command or step. What it rules on is which
topology family to use and why.

**H-type.** "It has finely clustered cells at the leading and trailing edges… simple to
construct and holds good for a **biconvex airfoil with sharp leading and trailing edges**.
However, when applied to an airfoil with a **curved leading edge**, the H-pattern creates a
**singular point**… can partly be alleviated by **splitting the singularity into two weaker
singularities**… it falls short of capturing the leading edge curvature accurately and also
**propagates the boundary layer in the transverse direction**… the high clustered cells both
parallel and perpendicular in regions where the flow accelerates can result in **significant
time step reductions due to CFL conditions**."

**C-type.** "An improved variant of H-type topology… **captures the leading edge curvature
without any singularities**. Though the C-type pattern **avoids the propagation of boundary
layer fineness upstream, it fails to do so downstream** of the airfoil trailing edge. In a way,
this downstream fineness proves beneficial as it helps to **capture the shear layer** for
solver runs at low angles of attack… most applications of the C-type pattern have **not taken
advantage** of the wonderful alignment of the grid lines… To take full advantage of this
pattern, the CFD analysis would have to **continually shift the grid curves to dynamically
align with the shear layer**… it does result in the **wastage of grid points downstream**."

**O-type.** "the **entire grid sheet is wrapped up around the airfoil without any propagation
of the boundary-layer fineness into the field**. This helps in getting an **optimal cell
count**… However… It creates **highly skewed cells for zero thickness trailing edge
airfoils**. The grid cell on the upper airfoil surface **directly connects to the cell on the
lower airfoil surface** across the horizontal grid line emanating from the trailing edge. For a
single cell-to-cell step, it **nearly creates a 360-degree turn in one step**. Thus, each cell
will have an **angle of slightly less than 180 degrees**… The level of skewness created in such
cases is **acceptable for Euler grids but is extremely high in viscous grids**… For this
reason, **many prefer to go with the C-type grid and live with the excessive cells in the wake
region**."

**[I]** That last sentence is GridPro's verdict on the choice this repo already made in
`cgrid_naca0012.json`, and it agrees with it. The O-grid objection is specifically about a
**zero-thickness** trailing edge; the repo's shipped O-grid cases are a circle and an ellipse,
which have no trailing edge, so the objection does not reach them.

### 2b. What the figures show — read off the images, not the text

I downloaded the post's figure images from `media.gridpro.com` and read them. Each claim here
is a reading of a picture and is marked as such.

- **Figure 1** (`2017/11/f12.webp`, alt "Structured multiblock mesh blocks around an airfoil")
  — a block-coloured mesh around a thin section at zero incidence, leading edge at left. A
  dense radial fan surrounds the nose; a long, thin, many-stranded band runs aft from the
  trailing edge and is picked out in its own colours, i.e. the wake is a stack of thin blocks
  rather than one. **Read off an image.**
- **Figure 9** (`2017/10/img10.webp`, "Topology for shock capturing on the upper surface of the
  airfoil") — **the most informative figure in the post.** Its top panel is the raw wireframe:
  orange corner dots joined by **straight** yellow links. I can see (i) an outer **rectangle**
  of four far-field corners, (ii) a ring of corners loosely following the aerofoil outline,
  (iii) a small closed **box of corners sitting above the upper surface at mid-chord** — the
  "cocoon" the text describes for the shock — and (iv) a **fan of roughly 6–8 links converging
  on one corner at the trailing edge**. The bottom panel is the resulting grid, whose block
  boundaries are **curved** where the wireframe's links were straight. **Read off an image.**
  **[I]** This single pair of panels is the clearest published demonstration of L1: straight
  links in, curved block boundaries out, corners nowhere on the geometry.
- **Figure 10** (`2017/10/img12.webp`) — three stacked zooms of "O-Type grid for an Airfoil with
  Blunt Leading and Trailing Edges with trailing edge and upper surface resolution plus shear
  layer resolution **with a sleeve surface to contain the anticipated shear layer**". The third
  panel shows a bundle of thin, differently-coloured strips leaving the nose along the upper
  surface and running downstream — the sleeve. **Read off an image.**
- **Figure 11** (`2017/11/img11_1.webp`) — four panels, the first of which is a **topology
  wireframe on a black background**: a loose O of corners around the body, a dense band of
  small cells hugging it, and an outer fan of links reaching a rectangular far field. The third
  panel shows the same region block-coloured, with the near-body band resolved into dozens of
  small blocks. **Read off an image.**

### 2c. Loop, sleeve, nesting — the post's actual recommendation **[V]**

> "Figure 9 shows the grid block layout for **shock capturing with a known shock position**. As
> it can be observed, **the blocks are placed right at the discontinuity**, capturing the shock
> with a dense cloud of grid points and gradually smoothing out as we move away… The grid
> density in the **central cocoon of blocks** can be varied to the user's desired level of
> resolution, **without affecting the neighboring block grid size**."

> "…the wake from the airfoil is accurately captured, by using a **loop topology**. Stretched
> high aspect ratio cells are used… By **extending the width of the loop**, a larger region
> engulfing the upper part of the airfoil and the region downstream can be captured… **the
> aspect ratio of the cells inside the loop is under the user's control**."

> "A more effective technique… is the topology building concept of "**nesting**"… the added
> advantage of **rapid cell count reduction in the direction normal to the wake**. This serves
> as a very powerful tool to creatively capture any mid-field flow physics **without the
> humongous increase in cell count**."

**[I]** "The grid density in the central cocoon can be varied… **without affecting the
neighboring block grid size**" is the claim this repo cannot currently make: a `count` here is
an **equivalence class** that propagates across every shared edge in the chain
(`.claude/rules/mesher-multiblock.md`), so refining one block's i-direction refines the whole
row. GridPro's answer to that is `nest`, which inserts a sub-block whose density is independent
— and which has no counterpart here. `cell-size-range-within-a-block.md` §3 already reached
this conclusion from the FAQ; the blog is the same claim from the vendor's marketing side.

---

## 3. GridPro's own 2-D airfoil tutorial — the reproduction target, measured

Source: `ws_Tutorials.zip`, `Tutorials/Medium/Tutorial_1_Airfoil/`, retrieved from the Internet
Archive capture `20150910111645` of `http://sp.gridpro.com/docs/ws_Tutorials.zip`. The folder
holds `Tutorial_1_Airfoil.pdf` (20 pages), `airfoil.fra`, `S830.lin`, `surf1.lin`, `surf2.lin`,
`surf3.lin`. Everything in this section is from those files. **[V]**

### 3a. The case **[V]** / **[I]**

- Geometry: `S830.lin`, **64 points**, a closed loop that starts and ends at `(1.0, 0.0)`.
  x ∈ [0.0000, 1.0000], y ∈ [−0.0733, 0.1365]. **[V]** → chord = 1, trailing edge at (1, 0),
  leading edge at (0, 0). The tutorial calls it "An airfoil with **sharp trailing edge**… whose
  **center is (0.5, 0)**". **[V]** The two surface tangents leaving the trailing edge are at
  162.38° and 166.07°, so the included wedge is **3.7°** — sharp, nearly cusped. **[I]**
- Far field: "Create a **circle of radius 3 units with center 1 0**". **[V]**
  **[I]** That is **3 chords** from the trailing edge and 2–4 chords from the body — an order
  of magnitude *inside* the same company's blog advice of "at least 30 chords" (§5). A tutorial
  domain, not a production one; worth saying out loud before anyone copies the 3.
- "Note: **GridPro has no dimension**. It takes the geometry's measurement as such." **[V]**

### 3b. The wireframe, step by step **[V]** (text) + figures read off the PDF

1. "**Create a wireframe structure around the airfoil** as shown in figure 10 using the Corner
   and Link buttons." — Figure 10 shows **four corners** forming one coarse quadrilateral
   *around* the aerofoil, none of them on it. **Read off an image.**
2. "**Expand the existing wireframe** as shown in figure 11 which represents a **C-Shaped
   wireframe to get a C-grid**." — Figure 11 shows that quad surrounded by a second layer, plus
   a column of corners **aft of the trailing edge**: that aft column is the C. **Read off an
   image.**
3. "**Group the outer corners** in a group, say group c1" (Figure 12). **[V]**
4. "**Wrap** the group c1 corners with a **wrap length of 200%** so that the wrapped layer is
   created approximately at the outer boundary." The dialog is titled "**Wrap (O Grid)**" with
   the options **Intelliwrap / Carry assignment / No assignment** and "Wrap length %: 200.000".
   **Read off an image + [V] from the text.**
5. "The corners created from the wrap are approximately close to the surface. **For the grid to
   converge faster a better positioning is required**… **Drag the corners and position them
   approximately** as shown in figure 15." **[V]** — L1, operationally.
6. Assignment: corner group **c2** → the aerofoil; corner group **c3** → the outer circle.
   Figure 18 shows the two assignment sets separately: **a polygon of about nine corners on the
   circle**, and **a quadrilateral of four corners around the aerofoil**. **Read off an image.**

### 3c. The three internal surfaces at the trailing edge — fully measured **[V]**/**[I]**

The three files are each 9 **collinear** points. Computed from the coordinates: **[I]**

| file | starts at | direction | length | end point | distance of end from (1, 0) |
|---|---|---|---|---|---|
| `surf1.lin` | (1.0, 0.0) | **+78.09°** | 3.201 | (1.66051, 3.13210) | 3.201 |
| `surf2.lin` | (1.0, 0.0) | **−18.10°** | 3.320 | (4.15577, −1.03140) | 3.320 |
| `surf3.lin` | (1.0, 0.0) | **−101.63°** | 3.231 | (0.34836, −3.16477) | 3.231 |

All three **start exactly at the trailing edge** and all three **end just outside the
r = 3 circle** — GridPro's own internal-surface rules 1 and 3, satisfied to the digit. **[I]**

Taking the two surface tangents at the trailing edge (162.38° upper, −193.93° lower) and the
three rays, the exterior fluid angle of **356.3°** is divided into four sectors of
**84.3° / 96.2° / 83.5° / 92.3°** (mean 89.1°). **[I]** That is rule 2 — "it should bisect the
angle equally at the sharp feature" — applied three times to produce **four blocks meeting at
the trailing edge, each with a corner near 90°**. This is the single most reusable number in
the whole note.

The tutorial states why one surface is not enough, with a figure: a single internal surface
aft of the trailing edge would be "making an **angle close to 180 degree with the airfoil**" and
"Creating a grid for the above will result in **highly skewed grid**… Hence we need to create
**three internal surface** as shown above to get a good quality grid." **[V]**

And why they were needed at all: "The grid obtained has **not captured the sharp trailing edge**
of the airfoil. In order to capture the sharp features of the geometry, **the block boundaries
should be fixed on the sharp features**, which can be done by using an internal surface."
**[V]** The first grid (Figure 25, before the internal surfaces) shows exactly that — zoomed in
on the trailing edge, the grid lines round it off. **Read off an image.**

### 3d. Densities, run and result **[V]**

- Section 4 ("DENSITY") sets five edges by hand. Figure 19 labels them **16, 16, 16, 16** and
  **24**, with the arrows pointing at radial edges running from the inner ring out to the
  circle (the 24 at the lower right, aft). Every other edge keeps the base density **8**.
  **[V]** on the numbers (they are typeset labels), **read off an image** for which edge is
  which.
- "**Stop the gridding process after 1500 sweeps**" — stated twice, once for each of the two
  runs. **[V]**
- Ggrid warns "**Mediumly severe singularity**"; the tutorial says "Click on 'Ok' to proceed".
  **[V]**
- Final report: **14 blocks, 4608 cells, 0 folds, worst skew 0.255576, max aspect ratio
  2.58781** (L2). **[V]**

**[I]** 14 blocks against roughly nine corners assigned to the circle and four to the
aerofoil: a plausible decomposition is **~9 outer blocks, each touching the circle on exactly
one side** (which is what the one-side-per-surface rule of §1b forces) **plus ~5 inner blocks**
carrying the body ring and the trailing-edge fan. I could not count the blocks reliably off
Figure 24, so **the 9 + 5 split is an inference and the 14 is the fact.**

---

## 4. What is parameterised by hand, and what the generator derives

From §1 and §3, with nothing added: **[V]** unless marked.

**The user states, exactly:**

- the surfaces (CAD curves, or GridPro's built-in plane / circle / cylinder / ellipsoid /
  periodic);
- the wireframe's **topology** — which corners exist and which are linked;
- **which surface each corner is assigned to** (and, for an internal surface, that it is
  "2 Sided with auto match");
- the **edge densities** (cells per edge; base 8, scalable wholesale in the schedule file);
- the per-surface **off-wall spacing** and **stretch ratio**, and the global **multi-grid**
  integer;
- the **schedule**: sweep caps, density ramp, dump frequency, output names;
- whether to run `Ggrid` or `Ggrid euler` (the latter ignoring all clustering).

**The user states approximately, and the generator overrides:**

- **every corner's position.** The golden rule, the wrap at 200% "approximately at the outer
  boundary", and "drag the corners and position them approximately". The DBC relaxation then
  morphs the wireframe onto the surfaces.

**The generator derives:**

- the **blocks and block faces** ("while the blocks and block faces are automatically generated
  from the wireframe");
- all **surface and volume grid points** simultaneously ("users are not required to generate
  surface grids or build items such as block edges and their **point wise distributions**");
- **orthogonality, smoothness, and curvature clustering** on both concave and convex
  boundaries;
- the **position of every boundary node on its surface**.

**[I]** The dividing line is clean and is the opposite of this repo's: GridPro lets the user
own the *combinatorics* and owns the *geometry* itself; this repo lets the user own both, and
owns only the interior.

---

## 5. Numbers, verbatim with units — and whether a primary source backs them

All from the airfoil blog post unless noted. Each row says what, if anything, confirms it.

| GridPro says | checked against |
|---|---|
| "a sufficient number of points on the body, say typically in the range of **300-400 points for RANS simulation**" | **unconfirmed [2nd]** — I found no workshop or NASA guideline stating a surface point count for a single-element 2-D section. The TMR NACA 0012 family runs 113×33 → 1793×513 **[V]**, i.e. 113–1793 points around the body, which brackets 300–400 without endorsing it. |
| "A finite thickness trailing edge demands **at least 20-30 points**" | **unconfirmed [2nd]**. Note the tension: the tutorial's own aerofoil is *sharp*, and this sentence is about a *finite-thickness* edge. |
| "The point placement is of the order of **0.1 percent of chord length** at the leading and trailing edges" | **unconfirmed [2nd]**. |
| "at the least, **20-40 layers of stretched elements** are stacked orthogonally to the wall… with a first cell height placement estimated for a **Y-plus of ~1.0**" | **y+ ≈ 1 is corroborated** — the workshop families this repo already verified use y+ ≈ 1 at their medium level (`multi-element-airfoil-blocking.md` §"Viscous clustering", quoting HiLiftPW and the TMR tables **[V]** there). I did not re-fetch those pages for this note, so for *this* note's purposes the corroboration is **[2nd] via a repo note that marked it [V]**. The 20–40 **layer count** is unconfirmed. |
| "Usage of a **smaller stretching ratio, say lesser than 1.2** is highly recommended" | **corroborated but not identical.** The AIAA High Lift Prediction Workshop guidelines say "Growth rate in the viscous layer (GR1) should be **< 1.25 for all grids**" (quoted verbatim in `multi-element-airfoil-blocking.md` **[V]**). GridPro's own manual says the stretch ratio "usually lies **between 1.1 and 1.5**" **[V]** — i.e. the vendor's manual is *looser* than the vendor's blog. Both numbers are the vendor's; the workshop number is 1.25. |
| "For a single-element airfoil, the farfield needs to be **at least 30 chords away in all directions**" | **unconfirmed [2nd]** as a threshold, and **contradicted by GridPro's own tutorial**, whose far field is a circle of radius **3** on a unit chord **[V]**. |
| "NASA's website for Turbulence Model Verification recommends keeping the farfield as far away as **500 chords**. This is too far than actually needed, but **they recommend it for sequential grids generated for grid convergence study**." | **The number is right, the reason is not.** NASA's own text: "To minimize issues associated with **effect of the farfield boundary (which can particularly influence drag and lift levels at high lift conditions)**, the farfield boundary in the grids provided have been located **almost 500 chords** away from the airfoil" — https://tmbwg.github.io/turbmodels/naca0012_val.html **[V]**. NASA frames it as a *boundary-influence* measure and offers a farfield point-vortex correction as the alternative; it does **not** tie it to grid-convergence sequencing, and the grids page states the topology as "a so-called "**C-grid**"" with "the finest grid has minimum spacing at the wall of **y = 4 × 10⁻⁷**" https://tmbwg.github.io/turbmodels/naca0012_grids.html **[V]**. |
| "the solution one obtains from a **30-100 chord** farfield distance is of sufficient quality and accuracy" for production | **unconfirmed [2nd]**, vendor opinion. |

GridPro's own tutorial numbers, which are **[V]** and are the ones worth reproducing:

- far field: **circle, radius 3, centre (1, 0)**, on a **chord 1** aerofoil;
- base edge density **8**; five edges raised to **16, 16, 16, 16, 24**;
- **1500 sweeps**, twice;
- result **14 blocks / 4608 cells / 0 folds / worst skew 0.255576 / max aspect ratio 2.58781**;
- the trailing-edge fan at **+78.09° / −18.10° / −101.63°**, giving four sectors of
  **84.3° / 96.2° / 83.5° / 92.3°**.

**[I] One caution on the skew number.** GridPro's dialog says "A skew of 0 is good and 1 is
bad" and nothing else; the formula is not published in anything I read. This repo's
`HYBMESH_MB_QUALITY` reports **non-orthogonality in degrees** and a separate cell-shape metric
(`.claude/rules/mesher-quality.md`). **0.255576 is not comparable to any number this repo
prints**, and quoting it as a target would be the mistake
`a-constant-copied-across-units.md` records.

---

## 6. What a reproduction here would have to declare

This section is written so that someone can open an editor and write the topology JSON. It
uses this repo's real schema (`.claude/rules/mesher-multiblock.md`,
`.claude/rules/mesher-spacing.md`, and the shipped `examples/topology/cgrid_naca0012.json` and
`tworing_ogrid.json`), not an invented one.

### 6a. What this repo HAS of GridPro's model **[V]**

- **A declared topology.** `corners` / `edges` / `blocks`, every id unique, unknown JSON keys
  refused, a declaration reaching nothing refused. The combinatorial half of a GridPro
  wireframe, stated the same way.
- **Binding to a curve by ARC LENGTH, with no tolerance anywhere.** `kind: "on_geometry"` with
  `{geom, seg, t}` for a corner; `binding: {geom, seg}` for a wall edge; `follows: {geom, seg}`
  for an interior line. This is GridPro's *surface assignment*, except that it resolves
  exactly instead of by relaxation.
- **Topological welding.** A shared edge is one edge two blocks name; nodes are shared by
  identity, so no tolerance is needed at a seam. GridPro's "full face matching", enforced by
  declaration rather than checked after the fact.
- **Counts that propagate.** `count` is a **seed** on an equivalence class of opposite sides,
  not a per-edge number. GridPro's *density* propagates the same way through the block graph.
- **Analytic edges with no file.** `"curve": {"kind": "arc", "centre": [x, y], "r": R}` (and
  `ellipse`), span derived from the edge's own two corners plus a `sweep`. This is GridPro's
  built-in circle surface, and it means **the tutorial's r = 3 circle needs no `.dat` at all**.
- **A cut.** `kind: "cut"` — an edge that is the side of two blocks, carries no boundary
  condition, and exports no face. This is GridPro's *internal surface* for the wake case,
  exactly.
- **Wall-clustered spacing.** `spacing: {wall_ends: "start"}` resolves the first cell height
  from `BL_INITIAL_THICKNESS` by bisection on a `tanh` law; `ds_start` / `ds_end` set it
  directly, and a two-sided law handles an edge wanting a different height at each end.
- **Winslow smoothing with wall control functions**, `MB_SMOOTH_ITERS`, default 20.
- **A two-ring construction with a computed middle ring.** `tworing_offset.json` takes the
  middle ring from the GUI's offset service — the nearest thing here to GridPro's "inner layer"
  / wrap.

### 6b. What this repo does NOT have **[V]** on each absence

1. **Surface projection of a non-conforming framework.** A corner's declared position *is* its
   position. There is no step that pulls a loosely placed corner onto a curve. The rule file's
   blind-spot list says so in as many words, and `curve` (#175) added an analytic edge but "the
   projection `MbCurve` carries has no production caller".
2. **Corner relaxation.** Nothing moves a corner, ever — and the smoother is explicitly
   forbidden from moving wall nodes. GridPro's entire quality argument rests on doing the
   opposite.
3. **`nest` / `reverse_nest` / clamps / sleeve surfaces / `Enrich`.** There is no way to refine
   one block without refining its whole propagation chain.
4. **Block merging** (`hex2emb`, `segb`). Blocks here are exactly what was declared.
5. **A singularity-valence diagnostic.** Nothing counts the edges meeting at a wall corner, so
   GridPro's "mediumly severe" warning has no counterpart (§1e).
6. **A skew metric comparable to GridPro's**, see §5.
7. **A convergence-free relaxation schedule.** `MB_SMOOTH_ITERS` is a small fixed count; there
   is no density ramp, no dump/restart, no `Ggrid euler` equivalent — though `MB_SMOOTH_ITERS 0`
   is the nearest thing to the last.

### 6c. The topology document, concretely

**The structural finding that decides the shape, stated first.** Three rays at a single
trailing-edge corner in a **single** ring cannot be written here, and cannot be written in
GridPro either without breaking one of its own rules. Walk the inner boundary of the
(disc − aerofoil) region: it visits the trailing edge once, between the lower-aft wall segment
and the upper-aft one. Putting three edges there means two consecutive rays with **no inner
edge between them**, so the block they bound has only three corners — a degenerate wedge, which
this repo would either refuse (a block's four edges must close a ring) or mesh as folded cells.
The two published escapes are: **[I]**

- **give the far field a flat outlet where the cut lands**, so each wake block gains two more
  corners — which is exactly what `cgrid_naca0012.json` already does with `wk`/`fu`/`fl` and
  `e_out_up`/`e_out_lo`; or
- **add a ring**, so that between consecutive rays there is a piece of the inner ring's outer
  curve to be the block's fourth side. GridPro took this one, which is why its count is 14 and
  not 4, and it is also forced by its "two sides of one block cannot be on one surface" rule
  once the far field is a single circle.

**So the faithful-but-writable target is the first escape with GridPro's angles.** Sketch,
schema-correct; the aerofoil needs a two-segment `.meta` sidecar split at the trailing and
leading edges, because those are the two places a block corner has to sit:

```jsonc
{
  "format_version": 1,
  "corners": [
    // The aerofoil's .meta sidecar splits it in two at the trailing and leading
    // edges — seg 0 upper, seg 1 lower — because those are the two places a
    // block corner has to sit.
    {"id": "te", "kind": "on_geometry", "geom": "s830.dat", "seg": 0, "t": 0.0},
    {"id": "le", "kind": "on_geometry", "geom": "s830.dat", "seg": 1, "t": 0.0},

    // The far field: GridPro's r = 3 circle about (1, 0), TRUNCATED by a flat
    // outlet at x = 3.5 so that the wake cut lands in the MIDDLE of a side
    // rather than at a corner — see the note under the block list. Declared as
    // COORDINATES, because the `curve` edges below derive their span from their
    // own two corners and so those corners must LIE on the circle; `wk` does
    // not, and is therefore only ever an end of the two straight outlet edges.
    {"id": "fo", "kind": "free", "xy": [ 3.5,      1.6583]},  // outlet top, on the circle
    {"id": "fa", "kind": "free", "xy": [ 1.6193,   2.9354]},  // GridPro's surf1 ray, +78.09 deg
    {"id": "fl", "kind": "free", "xy": [-2.0,      0.0   ]},  // dead ahead of the nose
    {"id": "fc", "kind": "free", "xy": [ 0.3925,  -2.9378]},  // GridPro's surf3 ray, -101.63 deg
    {"id": "fu", "kind": "free", "xy": [ 3.5,     -1.6583]},  // outlet bottom, on the circle
    {"id": "wk", "kind": "free", "xy": [ 3.5,     -0.8174]}   // where the -18.10 deg wake meets x = 3.5
  ],
  "edges": [
    // ── The wake: ONE cut edge, the west of BOTH wake blocks. GridPro's
    //    surf2.lin, which it calls an internal surface and says is "a typical
    //    example ... the wake of flow over an air foil".
    {"id": "wake", "corners": ["te", "wk"], "kind": "cut", "count": 25,
     "spacing": {"ds_start": 0.002}},

    // ── The trailing-edge fan: GridPro's surf1 and surf3, at its own angles.
    //    Ordinary interfaces; they carry no boundary condition.
    {"id": "r_te_up", "corners": ["te", "fa"], "kind": "interface", "count": 41,
     "spacing": {"wall_ends": "start"}},
    {"id": "r_te_lo", "corners": ["te", "fc"], "kind": "interface",
     "spacing": {"wall_ends": "start"}},
    {"id": "r_le",    "corners": ["le", "fl"], "kind": "interface",
     "spacing": {"wall_ends": "start"}},

    // ── The body. One block side per source segment, each bound so it FOLLOWS
    //    the aerofoil, each clustered where the surface turns.
    {"id": "af_up", "corners": ["te", "le"], "kind": "wall", "count": 49,
     "binding": {"geom": "s830.dat", "seg": 0},
     "spacing": {"ds_start": 0.001, "ds_end": 0.001}},
    {"id": "af_lo", "corners": ["le", "te"], "kind": "wall", "count": 49,
     "binding": {"geom": "s830.dat", "seg": 1},
     "spacing": {"ds_start": 0.001, "ds_end": 0.001}},

    // ── The far field. The two arcs are ANALYTIC: no .dat, no sidecar, the
    //    span derived from each edge's own two corners (#175).
    {"id": "ff_up", "corners": ["fa", "fl"], "kind": "wall",
     "curve": {"kind": "arc", "centre": [1.0, 0.0], "r": 3.0, "sweep": "ccw"}},
    {"id": "ff_lo", "corners": ["fl", "fc"], "kind": "wall",
     "curve": {"kind": "arc", "centre": [1.0, 0.0], "r": 3.0, "sweep": "ccw"}},
    {"id": "ff_aft_up", "corners": ["fo", "fa"], "kind": "wall",
     "curve": {"kind": "arc", "centre": [1.0, 0.0], "r": 3.0, "sweep": "ccw"}},
    {"id": "ff_aft_lo", "corners": ["fc", "fu"], "kind": "wall",
     "curve": {"kind": "arc", "centre": [1.0, 0.0], "r": 3.0, "sweep": "ccw"}},
    {"id": "out_up", "corners": ["wk", "fo"], "kind": "wall",
     "spacing": {"wall_ends": "start"}},
    {"id": "out_lo", "corners": ["wk", "fu"], "kind": "wall",
     "spacing": {"wall_ends": "start"}}
  ],
  // [south, east, north, west] = [radial in, far-field side, radial out, body side]
  // The wake cut is the WEST of both wake blocks: that is the C's cut.
  "blocks": [
    {"id": "b_wake_up", "edges": ["out_up", "ff_aft_up", "r_te_up", "wake"]},
    {"id": "b_upper",   "edges": ["r_te_up", "ff_up",    "r_le",    "af_up"]},
    {"id": "b_lower",   "edges": ["r_le",    "ff_lo",    "r_te_lo", "af_lo"]},
    {"id": "b_wake_lo", "edges": ["r_te_lo", "ff_aft_lo","out_lo",  "wake"]}
  ]
}
```

**Why the outlet is at x = 3.5 and not on the circle.** GridPro's `surf2.lin` ends *outside*
the r = 3 circle, so in GridPro the wake meets the far field at a corner of the outer polygon
and the wedge is absorbed by the inner ring. Here there is no inner ring, so the wake must land
**strictly inside** a far-field side: the outlet chord runs from `fo` to `fu` and `wk` sits
between them, which is what gives `b_wake_up` its fourth corner (`te → wk → fo → fa`) and
`b_wake_lo` its own (`te → wk → fu → fc`). Land the wake on the circle instead and both wake
blocks become triangles. The **−18.10° direction is GridPro's and is preserved**; the landing
point is not. **[I]**

**What is GridPro's and what is mine, in that file.** GridPro's: the circle's radius and
centre; the three trailing-edge ray directions, and therefore `fa`, `fc` and the wake's slope;
the four-sectors-of-about-90° rule those three rays encode; the principle
that the wake is an internal surface and that the sharp edge needs the block boundaries pinned
to it. Mine: the four-block count (GridPro's is 14), the `out_up`/`out_lo` outlet (GridPro has
no outlet — it closes the circle and pays with a ring), the counts, and the clustering numbers.
**The outlet is a departure from GridPro and should be labelled as one**, not quietly presented
as a reproduction.

**Checks that will bite when this is written.** Each from the rule file, so they are known in
advance rather than discovered: **[V]**

- a `curve` edge's two corners must **lie on** the curve, since the span is derived from them
  and never declared — `fo`, `fa`, `fl`, `fc` and `fu` are on `r = 3` by construction, but
  `wk` at (3.5, −0.8174) is **not**, which is why `out_up`/`out_lo` are straight and `wk` is
  their shared corner rather than an arc's;
- every block's four edges must **close a ring**, counter-clockwise;
- `count` is an **equivalence class** seed: declaring it on `r_te_up` fixes `r_te_lo`, `r_le`
  and both outlet edges, and declaring it on `af_up` fixes `af_lo` and both far-field arcs.
  Declaring it twice inconsistently is refused;
- `binding` is **wall-only** and `follows` is **interior-only**; the wake is a `cut` and may
  carry neither;
- unknown keys are refused, so `"spacng"` is an error, not a silent default.

**The second escape — GridPro's own — in this repo's terms.** If the goal is GridPro's
*shape* rather than a 4-block minimum, the two-ring idiom is already shipped: take
`tworing_ogrid.json`'s structure (body ring → seam ring → far field, two separate radial
equivalence classes, the seam declared with `follows` so it carries no boundary condition) and
produce the seam by offsetting the aerofoil through the GUI's offset service, as
`tworing_offset.json` does for the ellipse. Then the three trailing-edge rays can start on the
**seam** rather than on `te`, each pair of consecutive rays having a piece of seam between
them, and the wedge problem disappears without an outlet. **[I]** That is the closest this repo
can currently get to the 14-block tutorial, and it is a real piece of work — not a JSON edit —
because the offset of a sharp trailing edge is not a curve the shape library can express.

### 6d. What would have to change in the repo for a *faithful* reproduction

In order of how much it costs, smallest first: **[I]**

1. **Nothing**, for the 4-block version in 6c — it is writable today, and `curve` means the
   circular far field needs no geometry file.
2. **A sharp-trailing-edge offset**, for the two-ring version. The offset service already ships;
   what it does at a 3.7° wedge is not characterised anywhere I read.
3. **A valence diagnostic**: count the edges naming each `on_geometry` corner and report 2 / 3 /
   4+ against GridPro's table (§1e). Cheap, and it would have flagged the shipped C-grid's
   five-edge `te` the day it landed.
4. **Independent block density** (`nest`). Expensive: it breaks the equivalence-class model the
   whole count system rests on, and it is the one feature both blog posts single out as the
   reason to use GridPro at all.
5. **Corner relaxation / surface projection.** This is GridPro's product, not a feature, and
   `where-a-block-corner-sits-on-its-ring.md` already argues the repo made the opposite choice
   deliberately. Nothing in this note says that choice was wrong — only that the two tools
   therefore need different topology documents for the same mesh.

---

## 7. What I could not verify, and what refused me

1. **Neither blog post describes the blocking workflow.** The "art or science" post is an
   opinion piece; its only mechanism sentence in 3832 words is "Since what the primary user
   inputs are the **pattern of points expressed through a coarse overlaid wireframe**, it is
   quite easy to create grids with many blocks" **[V]**. WebFetch's first pass on it reported,
   correctly, that it "does not contain the specific technical content you're requesting". The
   brief's assumption that these two posts would carry the vocabulary was wrong, and the note
   says so rather than padding them out.
2. **`gridpro.com/documentation` and every `sp.gridpro.com/docs/*.pdf` now 301-redirect to
   `gridpro.com/signin`.** Measured: `GridPro Installation Guide v6.5SP1.pdf`,
   `WS_GUI_Manual_v6.5SP1.pdf`, `User_Guide_for_TIL.pdf` and `What's_New v6.7.pdf` all return
   HTTP 200 with the **same 81,837-byte sign-in page**. Everything in §1, §3 and the FAQ quotes
   came from **Internet Archive captures**, named at each use. The two prior notes recorded
   this gate as a HubSpot form; it is now a sign-in wall, and the archive route is the one that
   works.
3. **The TIL corner/assignment syntax is still unseen.** `User_Guide_for_TIL.pdf` is not in the
   Wayback CDX index for `sp.gridpro.com/docs*` under that name. The only `.fra` files in the
   2014 tutorial archive that I opened are *step-1* files with empty `corn()` components, so I
   have GridPro's `COMPONENT` / `INPUT` / `s <id> -linear "<file>"` syntax **[V]** and nothing
   for a corner line. **The brief's `-s` / `-s` corner-label spelling is therefore unconfirmed**
   — I will not write a syntax I have not seen, after `refusal-describes-the-implementation.md`.
4. **`.conn` and `.tmp` as the brief spelled them.** `.tmp` is attested (`blk.tmp`, `dump.tmp`,
   `badB.tmp`, and `.tmp`/`.grd` as restart dumps) **[V]**. `.conn` is attested only as
   `*.conn_m`, a block-merge connectivity file **[V]**. The topology file is `.fra`, not
   `.conn`.
5. **GridPro's variational functional** — what Ggrid actually minimises — remains unseen, the
   same gap `where-a-block-corner-sits-on-its-ring.md` §Gaps records. The GUI manual calls it
   "a unique algorithm using advanced mathematical techniques" and stops. **[V]**
6. **The 14-block layout.** I have the count, the cell count and the quality figures from
   GridPro's dialog **[V]**, and I could not count the blocks reliably off Figure 24. The
   9 outer + 5 inner split in §3d is an inference and is marked as one.
7. **The blog's sizing numbers** (300–400 surface points, 20–30 trailing-edge points, 0.1% of
   chord, 20–40 BL layers, 30 chords) have **no primary backing I could find** and are listed
   as `[2nd]` in §5. Only the y+ ≈ 1 band, the growth-rate band and the 500-chord figure are
   corroborated, and the last one's *reason* is corroborated **against** GridPro.
8. **I did not re-fetch the AIAA workshop gridding guidelines** for this note; the GR1 < 1.25
   quote is taken from `multi-element-airfoil-blocking.md`, where it is marked **[V]**. For
   this note it is secondhand, and §5 says so.
9. **No image I read is a substitute for a block diagram.** Every figure-derived claim is
   marked "read off an image" in place. The tutorial figures (vector line art rendered at
   150 dpi) are far more legible than the blog's photographs of coloured meshes, and almost
   everything structural in this note comes from the former.

---

## 8. The reproduction, BUILT and MEASURED

Section 6 said what a reproduction would have to declare. This section is what happened when
it was declared and run, 2026-11-05, on the binary in this checkout. Two cases, both under
`docs/research/gridpro-blocking-method/`, both generated rather than hand-written so that the
GridPro-derived numbers are **derived at build time and not transcribed**:

| | generator | document | config |
|---|---|---|---|
| **A — the minimum** | `make_topology.py` | `gridpro_airfoil.json` | `gridpro_airfoil.dat` |
| **B — the reproduction** | `make_tworing.py` | `gridpro_tworing.json` | `gridpro_tworing.dat` |
| **C — §9 and §10, added later** | `make_rings.py` | `gridpro_rings.json` | `gridpro_rings.dat` |
| **— §16's chart** | `plot_residuals.py` | `residual_compare.png` | — |
| **D — §13, the C/H** | `make_ch.py` | `gridpro_ch.json` | `gridpro_ch.dat` |
| **E — §17, fig6 as the target** | `make_ch.py --layers 3 --split 16 --turn-blend 0.8` | `gridpro_ch_fig6.json` | `gridpro_ch_fig6.dat` |
| **F — §18, with an H outer field** | `make_ch.py --layers 4 --split 16 --turn-blend 0.8 --h-outer --box -0.8 1.0` | `gridpro_ch_h.json` | `gridpro_ch_h.dat` |

```bash
python3 docs/research/gridpro-blocking-method/make_tworing.py        # --split K, --blend W
./run.sh -conf docs/research/gridpro-blocking-method/gridpro_tworing.dat
python3 tools/scripts/view_mesh_vtk.py \
    results/meshes/gridpro_tworing/mesh_gridpro_tworing.vtk out.png
```

Nothing in `config/`, `examples/`, `src/`, `include/` or `.claude/` was touched to build
either. **No gate covers them** — they are a reproduction attempt, not a shipped case.

Four figures are committed beside the generators. They are those same views rendered at 95 dpi
rather than `view_mesh_vtk.py`'s own 140, which is the only difference between them and what
the command above prints:

| figure | what it shows |
|---|---|
| `gridpro_tworing_full.png` | case B whole — the fourteen blocks, coloured by declaration index |
| `gridpro_tworing_te.png` | the trailing edge: four blocks meeting on one node, the three internal surfaces, the ring's tail |
| `gridpro_tworing_le.png` | the nose: the inner ring's wall-normal cells and the nose radial |
| `gridpro_4block_full.png` | case A, for the comparison §8c makes |

### 8a. The one structural fact that makes this clean **[I]**, from §3's **[V]** numbers

**GridPro's far-field circle is centred ON THE TRAILING EDGE.** §3a records the tutorial's own
words — "a circle of radius 3 units with center 1 0" — and §3a records that `S830.lin` starts
and ends at `(1.0, 0.0)`. They are the same point. So the three internal surfaces, which §3c
measured as starting exactly at `(1, 0)` and ending at 3.201 / 3.320 / 3.231 from it against a
radius of 3, are **RADII of the far field**, and that is why they reach the outer boundary at
all without any construction. Nothing in the tutorial text says this; it falls out of the two
measurements being set side by side.

In this repo that means the whole far field needs **no geometry file**: every outer side is
`"curve": {"kind": "arc", "centre": [1, 0], "r": 3}` and each span comes from the edge's own
two corners (#175). Both cases below do that, and neither ships a far-field `.dat`.

### 8b. The body is ours, so the three angles are GridPro's RULE and not GridPro's numbers

GridPro's S830 is inside `ws_Tutorials.zip`, which §7 records as now behind a sign-in wall; it
could not be fetched again for this. So the rule is executed on the aerofoil this repo already
ships, `examples/geometries/naca0012_cgrid.dat`, and the generator **derives** the angles from
that polyline's own two trailing-edge tangents rather than carrying GridPro's across:

| | GridPro's S830 **[V]**/§3c | this body, derived **[V]** (measured by the generator) |
|---|---|---|
| trailing-edge wedge | 3.7° | **16.5372°** |
| exterior fluid angle | 356.3° | **343.4628°** |
| the four sectors | 84.3 / 96.2 / 83.5 / 92.3 | **85.8657** each |
| the three rays | +78.09 / −18.10 / −101.63 | **+85.8657 / 0 / −85.8657** |

**[I]** The body here is symmetric, so the middle ray comes out as the x axis *exactly* and
the wake is straight **by derivation**. On GridPro's cambered S830 it is not, and the −18.10°
is the same rule answering a different body. Change the body and these four rows move; that is
the point of deriving them.

### 8c. Case A — the minimum, and the mapping that defeats it

Four blocks: the two trailing-edge rays and the wake, the aerofoil's two sides bound to their
own segments, six analytic arcs closing the circle, and one extra corner on each aft arc
(§6c's structural finding — without it the region between two consecutive rays has three
corners and is not a block).

**It meshes, and it is not a grid anyone should use.** Measured:

```
cells=11520 inverted=0 nonortho_max=87.449 nonortho_mean=20.908
wall_first_cell_worst_rel=0.264  adjacent_area_ratio_max=2.195
```

**[I]**, derived from two figures the generator prints **[V]**. The cause is the mapping and
not the node counts, and it fails from both ends:

- distributing the far-field arc **proportionally to the body's arc length** leaves the grid
  line from mid-chord 36° off the body's own normal, because the opposite point of mid-chord
  lands at 133° round the circle;
- casting the **body's own outward normals** out to the circle instead collapses the upper
  surface's 94° of arc into **10.4°** (the mid-chord normal lands at 96.23°, the
  trailing-edge ray at 85.87°), which makes one outer block an eighth the width of its
  neighbour.

**[I]** Both follow from 8a: the circle is centred on the trailing edge, so seen from the
centre the entire body is a thin wedge of directions. No distribution along those two sides
fixes it. **GridPro's own answer to exactly this is the step its tutorial calls `Wrap (O
Grid)` at 200% (§3b step 4)** — put a ring in between. Case B is that.

### 8d. Case B — the reproduction, and it lands on GridPro's own block count

A wrapped inner ring between the body and the outer region, an outer ring out to the circle,
and the trailing edge's fan between the three internal surfaces. At `--split 2` it comes out
at **FOURTEEN BLOCKS, FOUR CORNERS ON THE AEROFOIL AND EIGHT ON THE CIRCLE** — against the
tutorial's **[V]** 14 blocks, four corners on the aerofoil and "about nine" on the circle
(§3b step 6, §3d). **[I]** The count is not fitted: it is `4K + 6` for K body sides per
surface, and K = 2 is what "four corners on the aerofoil" means.

```
cells=17408 inverted=0 nonortho_max=59.856 nonortho_mean=12.307
wall_first_cell_worst_rel=0.000139  quad_midline_ratio_median=2.751 p95=13.815
adjacent_area_ratio_max=11.713
```

The wall first cell is held to **0.014%** of the height asked for, against case A's 26.4%, and
every wall edge's grid line leaves within **4.68°** of normal — the worst figure in the run's own per-edge control-function warnings.

**The ring is an analytic ellipse (centre 0.5 0, a 0.9, b 0.30), not a relaxed wrap**, because
nothing in this repo moves a corner once it is declared (§6b). Where a ring corner sits is this
repo's own documented blend (`where-a-block-corner-sits-on-its-ring.md`) taken at both ends:
**on the ring** it is where the body's own outward normal arrives, which is what makes the first
cell off the wall orthogonal; **on the circle** it is half way between an even share of the arc
and where the ring's own normal lands. That weight is `--blend`, and it was measured rather than
picked (measured at `--split 4`, 5 sweeps, so the absolute figures are that case's and the trend is what the weight was chosen on):

| `--blend` | 0 | 0.25 | **0.5** | 0.75 | 1.0 |
|---|---|---|---|---|---|
| worst non-orthogonality | 60.59 | 59.77 | **58.21** | 55.99 | 56.25 |
| mean | 9.58 | 8.63 | **8.01** | 7.73 | 7.95 |
| worst adjacent area ratio | 10.57 | 10.66 | **13.32** | 23.81 | 65.43 |

### 8e. TWO of this note's own recovered rules bit, from the inside

**[V]** **1. "Two sides of one block cannot be on one surface" (§1b) is not a style rule.**
The first build gave each trailing-edge wedge its fourth corner by splitting the ring's own
ellipse arc in two. A corner declared in the middle of a SMOOTH curve is not a corner: the
wedge meets itself there at **178.468°**, at `(1.29874, ±0.13825)`, and that is the worst
corner in the whole mesh. The fix is to give the ring a straight **TAIL** — two chords and a
flat face behind the trailing edge, with real corners where the perpendicular to the wake
meets the perpendicular to each ray. Same blocking, same counts, same everything else; only
the four aft ring sides change from arcs to chords. `--no-tail` keeps the rejected placement
runnable, so this is a comparison and not a recollection (both at `--split 2 --blend 0.5`,
5 sweeps):

| | m2/m3 ON the ring curve | the ring given a TAIL |
|---|---|---|
| worst non-orthogonality | 88.468° | **59.856°** |
| mean non-orthogonality | **10.866°** | 12.307° |
| worst wall first cell | 0.037% | **0.014%** |
| worst adjacent area ratio | 60.53 | **11.71** |

**The mean goes the other way, and that is the trade rather than a defect in the measurement**:
the tail puts two genuine corners into a region that was a smooth curve, so more cells sit near
a corner, while the one cell that was nearly folded stops being so. **[I]** Taking the worst
corner at the cost of 1.4° of mean is the right way round for a solver, but it is a choice and
the table is what it was made on.

**[V]** **2. The worst corner that is left is a SINGULARITY, and GridPro's tutorial has one
too.** It sits at `(1.4, ±0.21776)`, the ring's two tail corners, where **three blocks meet**
— the wedge and two outer blocks. Three blocks share 360°, so one of them must take at least
120°; measured, 150.593°. It cannot be removed by moving anything, only by changing the
blocking. §3d records that Ggrid prints "**Mediumly severe singularity**" on this very
tutorial and that the tutorial's instruction is "Click on 'Ok' to proceed" — so the
reproduction reproduces the warning as well as the mesh. §1e's valence table is the rule it is
an instance of, and §6d item 3 (a valence diagnostic) is what would make this repo say so by
itself.

### 8f. Refining the way GridPro refines

§1b and the blog's own recommendation (§2c) are that the answer to a badly shaped region is
more blocks, not more nodes. `--split K` does that — K body sides per surface, `4K + 6` blocks
— and it is measured (blend 0.5, 5 sweeps):

| `--split` | 2 | 3 | 4 | 6 |
|---|---|---|---|---|
| blocks | **14** | 18 | 22 | 30 |
| cells | 17408 | 22784 | 28160 | 38912 |
| mean non-orthogonality | 12.31 | 9.60 | 8.01 | **6.26** |
| worst non-orthogonality | 59.86 | 58.21 | 58.21 | 58.21 |
| worst wall first cell | 0.014% | 0.014% | 0.014% | 0.014% |

**[I]** The mean halves and **the worst does not move**, because the worst is the valence-3
singularity of 8e, which is a property of the blocking and not of its refinement. That is the
sharpest single thing this reproduction says: subdividing buys the average and not the worst
corner, and only a different topology buys the worst corner.

### 8g. The smoother had to be turned DOWN, and that is a measurement

This repo's default is `MB_SMOOTH_ITERS 20`. On this topology the Winslow iteration
**DIVERGES** and the mesher says so itself — at a cap of 20 it stops at sweep 7 with
`diverged=1` in `HYBMESH_MB_SMOOTH`, which is why 20, 40 and 80 are one number:

| cap | 0 | **5** | 10 | 20 | 40 | 80 |
|---|---|---|---|---|---|---|
| sweeps actually run | 0 | **5** | 10 | 7 | 7 | 7 |
| worst non-orthogonality | 59.918 | **59.856** | 84.244 | 69.617 | 69.617 | 69.617 |
| mean non-orthogonality | 12.565 | **12.307** | 12.236 | 12.271 | 12.271 | 12.271 |
| worst wall first cell | 13.98% | **0.014%** | 0.011% | 0.014% | 0.014% | 0.014% |

So the config carries `MB_SMOOTH_ITERS 5`: five sweeps is what takes the wall height from 14%
to 0.014% while the solve is still descending (`diverged=0`, best sweep 5 of 5). **[I]** The
cap-10 row is the one to read twice — it runs all ten *without* the divergence being detected
and produces the worst mesh of the six, so "it did not report divergence" is not the same as
"it helped". This is the mesher's own machine-readable report, not a tuning campaign.

### 8h. What was NOT reproduced, said plainly

1. **GridPro's S830**, for 8b's reason. The blocking is GridPro's; the body is not, and
   therefore neither are the three angles — only the rule that produced them.
2. **The wrap itself.** GridPro's ring is a 200% wrap of a corner group followed by the user
   dragging the new corners into place and then the solver relaxing everything (§3b steps
   4–5). Ours is an ellipse chosen by hand, because §6b item 2 holds: nothing here moves a
   corner.
3. **Block merging** (`hex2emb` / `segb`, §1c). GridPro's 14 is after whatever merge policy its
   tutorial uses; ours is 14 as declared. **[I]** The two being equal is a coincidence worth
   stating as one.
4. **The quality comparison.** §5 records that GridPro's skew 0.255576 has no published
   formula; `HYBMESH_MB_QUALITY`'s non-orthogonality is an angle off 90° and its cell-shape
   figure is a quad midline ratio. **Nothing in 8c–8g is comparable with the tutorial's
   0.255576 or its 2.58781**, and no attempt is made here to compare them.
5. **A solver run.** Neither case was taken through `getPGrid`/`unicones`. Gate 1 (it meshes,
   0 inverted) is all that is claimed; `.claude/rules/mesher-multiblock.md` records that gate
   2 is the one that has bitten on a C-grid that passed gate 1.

---

## 9. More blocks, the way the post's own FIGURES arrange them

§8 refined circumferentially only, because `make_tworing.py` hard-codes two rings. The
maintainer then asked whether **more blocks would make it more like GridPro's**, pointing at
the pictures in *Grid Generation: an Art or Science?* rather than at its text. They do, and
they do not, and the split between the two is the whole of this section. 2026-11-06.

### 9a. A correction to §7 item 1 **[V]**

§7 says that post "does not describe the blocking workflow" and that its only mechanism
sentence in 3832 words is the one about a coarse overlaid wireframe. **That is true of its
TEXT and it is not true of the page.** Its figures are GridPro meshes with the blocks coloured
in, and two of them are the clearest statement of the arrangement anywhere in either post. I
had read `<img alt>` strings for that post; I had not downloaded and looked at its images,
which is a different act, and §2b did it for the *other* post only.

The two that bear on a single body (both `media.gridpro.com/wp-content/uploads/2017/09/`,
fetched 2026-11-06):

- **`fig6.webp`**, alt "Airfoil with Icing, Multi-Block Structured grid using GridPro". Six
  panels; the top one is a whole block-coloured mesh round a thin section. **Read off the
  image:** a very thin ring hugging the surface, cut into **about ten blocks chordwise per
  side** and into **two or three layers radially**; outside it a second band of thicker
  blocks cut the same way; outside that a coarse field; a **dense rosette of small blocks at
  the leading edge** and another **fan at the trailing edge**. The bottom two panels are the
  wireframes that produced it.
- **`fig5.webp`**, alt "Structured Multi-block grid for MDA-3 Element Configuration using
  GridPro". **Read off the image:** a dense rosette of small blocks on the bodies, then a ring
  of roughly **sixteen petal-shaped blocks**, then an outer ring of about the same number
  reaching the far field. It reads as **concentric rings × many circumferential sectors**, and
  that is the arrangement this section reproduces.
  > **THE "OUTER RING" CLAUSE IS WRONG, AND §11b CORRECTS IT.** Zoomed into the figure's
  > upper-right quadrant, those outer colour bands are **azimuthally** adjacent and each one
  > spans the whole radial extent, so there is **no concentric seam** in the outer field at
  > all. §9's three rings put two seams there that GridPro has none of.

**[I]** Neither is the tutorial's case and neither is a single aerofoil in a circle, so nothing
here overrides §3. What they add is the SHAPE of the refinement: both are subdivided in BOTH
directions, and §8 only had one of them.

### 9b. `make_rings.py` — N concentric rings × 2K sectors

A third generator beside the other two; `make_tworing.py` is not superseded, it is the case
§8 measures and it is unchanged.

```bash
python3 docs/research/gridpro-blocking-method/make_rings.py \
    [--split K] [--rings N] [--te-rays R] [--blend W] [--per-layer M] [--free-rings]
./run.sh -conf docs/research/gridpro-blocking-method/gridpro_rings.dat
```

Ring 1 is the wrap and ring N is GridPro's circle **exactly**; the ones between morph from one
to the other with the centre moving linearly and the two semi-axes **geometrically**, so the
rings grow the way a boundary layer does instead of jumping from a thin wrap to a fat blob.
The walk round a ring is **a sort by each station's own parameter on ring 1**, not a hand-built
list, which is what lets the ray count and the sector count move independently — and it doubles
as the check in 9d.

The shipped case is `--split 8 --rings 3`: **58 blocks, 76 corners, 134 edges**, figures
`gridpro_rings_full.png` and `gridpro_rings_te.png`.

```
cells=17408 inverted=0 nonortho_max=63.195 nonortho_mean=9.298
wall_first_cell_worst_rel=0.001423  quad_midline_ratio_median=2.737 p95=13.093
adjacent_area_ratio_max=12.744
```

> **THOSE ARE THE NUMBERS OF THE VERSION WITH STRAIGHT BLOCK BOUNDARIES, AND THE SHIPPED FILE
> IS NO LONGER IT.** Every table in §9 was measured with the radials and the trailing-edge tail
> as straight chords, which is what `--chord-radials --chord-tail` still produces, so §9's
> comparisons remain internally consistent and re-runnable. §10 then made those boundaries
> CURVES and that is what `gridpro_rings.json` now holds; §10c carries its figures.

### 9c. The answer, and it is not "yes"

Every row below is at the SAME NODE BUDGET — 17408 cells, 5 sweeps, `--blend 0.5` — so what
changes is the BLOCKING and nothing else. **[V]**

| rings | sectors | blocks | worst non-orth | mean non-orth | worst wall cell | worst area jump |
|---|---|---|---|---|---|---|
| 2 | 4 | 14 | 60.69 | 12.47 | 0.059% | 10.41 |
| 2 | 8 | 22 | 60.69 | 8.47 | 0.059% | 10.41 |
| 2 | 12 | 30 | 60.69 | 7.29 | 0.059% | 10.56 |
| 2 | 16 | 38 | 60.69 | **6.77** | 0.059% | 13.01 |
| 3 | 4 | 22 | 63.19 | 15.23 | 0.142% | 8.03 |
| 3 | 8 | 34 | 63.19 | 11.02 | 0.142% | 8.80 |
| 3 | 12 | 46 | 63.19 | 9.82 | 0.142% | 10.37 |
| 3 | 16 | **58** | 63.19 | 9.30 | 0.142% | 12.74 |
| 4 | 4 | 30 | 59.86 | 15.78 | 0.172% | **7.74** |
| 4 | 8 | 46 | 57.59 | 11.57 | 0.172% | 8.79 |
| 4 | 12 | 62 | 56.89 | 10.37 | 0.172% | 10.37 |
| 4 | 16 | 78 | **56.29** | 9.84 | 0.172% | 12.73 |

Three things fall out, and they point in different directions:

1. **More SECTORS is the one that works.** Along any row the mean non-orthogonality falls
   monotonically — 12.47 → 6.77 at two rings — for no extra cells. This is §8f's result
   again, and it is GridPro's own advice (§1b, §2c) measured.
2. **More RINGS buys SIZE GRADING and costs ANGLE.** Down any column the worst adjacent area
   ratio improves (10.41 → 8.03 → 7.74 at four sectors) while the mean non-orthogonality gets
   WORSE (12.47 → 15.23 → 15.78). **[I]** Each extra ring is one more curve the grid is
   required to pass through, and ours are CHOSEN (a geometric ellipse morph) rather than
   solved, so every one of them is a constraint the field did not ask for.
3. **Neither moves the worst corner much.** It stays between 56 and 63 everywhere, because it
   is §8e's valence-3 node at the ring's tail — a property of the topology, which subdividing
   that topology does not touch.

**And paying for the extra rings in NODES does not rescue them** (12 radial intervals in each
layer rather than one budget shared over them, 12 sectors): **[V]**

| rings | blocks | cells | worst non-orth | mean non-orth | worst area jump |
|---|---|---|---|---|---|
| 2 | 30 | 12800 | 47.92 | **8.13** | 26.22 |
| 3 | 46 | 17408 | 63.19 | 9.82 | **10.37** |
| 4 | 62 | 22016 | 53.75 | 10.38 | 10.45 |

The mean still gets worse; what the extra rings genuinely fix is the size jump, which at two
rings and this radial count is **26.2** and at three is **10.4**.

**One explanation was tested and REFUTED, so it is not offered.** A declared shape is FROZEN by
the Winslow smoother (`.claude/rules/mesher-smoothing.md`), so the obvious reading is that each
intermediate ring pins a whole circle of nodes. `--free-rings` drops the `curve` on rings
2..N-1 and leaves them straight chords between the same corners, which the smoother may move.
It makes the mean **worse**, not better — 9.82 → 10.16 at three rings, 10.37 → 10.91 at four,
and the wall figure worse in both. **[I]** What both variants still pin is the ring's CORNERS,
and nothing in this repo can relax a corner (§6b item 2); that is where the cost must sit, but
this note has not isolated it and does not claim to have.

### 9d. A NEW result about GridPro's own rule: equal bisection CAPS the trailing-edge fan

`fig6` shows a fan of more than three links at the trailing edge, so `--te-rays` was built to
divide the exterior angle into more than four sectors. **On a thin section it does not fit, and
the generator now refuses it by name rather than failing three functions later as a missing
edge.** **[V]**

```
--te-rays 5 does not fit this body: dividing its 343.463 deg exterior angle equally puts
a ray at 114.488 deg, which lands on the ring INTERLEAVED with the body's own stations
```

**[I]** The arithmetic is the whole argument: the exterior fluid angle at a sharp trailing edge
is nearly 360°, so **n** rays make sectors of about **360/(n+1)**. At n = 3 that is 86° and
every ray points aft. At n = 5 it is 57° and the outermost pair point at ±114° — back OVER the
body — so their landings on the wrap interleave with the body's own normals and the region
between two interleaved stations is not a block. **So the tutorial's THREE is not a modest
choice: on a section like this it is the largest number equal bisection admits**, and §3c's
"it should bisect the angle equally at the sharp feature" and §1e's valence table are two
statements of one constraint. A fan of six or eight links at a trailing edge is therefore
either a blunt trailing edge, or rays placed unequally, or links that are not all rays — the
figure cannot distinguish them and this note does not.

### 9e. What the 58-block case costs against the 14-block one

Both at 17408 cells, 5 sweeps: **[V]**

| | §8's 14 blocks | §9's 58 blocks |
|---|---|---|
| mean non-orthogonality | 12.307° | **9.298°** |
| worst non-orthogonality | **59.856°** | 63.195° |
| cell shape, median / p95 | 2.751 / 13.815 | **2.737 / 13.093** |
| worst wall first cell | **0.014%** | 0.142% |
| worst wall grid-line angle | **4.68°** | 15.31° |
| worst adjacent area ratio | **11.713** | 12.744 |

Both columns are the STRAIGHT-BOUNDARY versions, which is what makes this a comparison of
BLOCKING alone; §10e redoes the right-hand one with curved boundaries and it changes the
verdict on the wall rows.

**[I]** So the picture that looks most like GridPro's is better in the field and worse at the
wall, and for a viscous solve the wall columns are the ones that decide. **The honest answer to
"would more blocks be more like GridPro's mesh" is: more SECTORS, yes, and they are free; more
RINGS, it looks much more like the figures and measures worse here, for a reason that is
GridPro's capability and not its blocking** — its rings are where its relaxation puts them, and
ours are where we put them.

**A DISCREPANCY, NAMED RATHER THAN SMOOTHED OVER.** At `--rings 2 --split 2` this generator
declares the same 14-block shape as `make_tworing.py` with the same counts, and does not
produce the same mesh: 60.69° / 0.059% here against 59.856° / 0.014% there. I checked the node
counts, the ring geometry, the tail construction, the blend and the arc declarations and they
agree; I did not localise it, and nothing in §9 rests on the two being identical. §8's figures
remain `make_tworing.py`'s and §9's remain this one's.

---

## 10. The block boundaries themselves are CURVES

The maintainer's next observation, and it is correct: in §9's mesh the trailing edge was
handled by rounding off one sharp corner while the block boundary itself stayed a straight
polyline, and in the far field the block boundaries were straight radial lines — while
GridPro's, in every figure in either post, are **curves all the way**. 2026-11-06.

### 10a. What was actually straight, measured **[V]**

Of the shipped §9 document's **98 interior lines**, **36 carried a declared shape** (ring 1's
and ring 2's arcs) and were therefore FROZEN by the smoother, and **62 were free** — every
radial, and the four chords of the trailing-edge tail. The run says so itself:

```
Movable nodes : 8268 of 8848, of which 1074 on a shared edge (walls, declared corners and
any interior line WITH A DECLARED SHAPE — one that FOLLOWS a curve or IS one — are frozen)
```

**[I]** So the straightness was not a freeze. A free interior line in this repo starts as the
straight chord between its two corners and is whatever the smoother leaves it — and at the
five sweeps this family runs, it leaves it straight.

### 10b. GridPro's curves are a CONVERGED SOLVE, and this repo cannot run one here **[V]**

§1a's golden rule is "straight links in, curved block boundaries out": in GridPro the
curvature is the OUTPUT of the elliptic solve, not an input. The equivalent experiment here is
to declare nothing — `--free-wrap --chord-radials --chord-tail` drops the `curve` on every
interior ring and every other edge, leaving **0 of 98 interior lines frozen**, so every block
boundary is free to be relaxed into whatever shape the solve wants — and then let it run
(verified against the cap-5 row before this was written):

| `MB_SMOOTH_ITERS` | 0 | 5 | 20 | 50 | 100 | 200 | 400 |
|---|---|---|---|---|---|---|---|
| sweeps actually run | 0 | 5 | 20 | 13 | 13 | 13 | 13 |
| diverged | no | no | no | **yes** | yes | yes | yes |
| inverted cells | 0 | 0 | **6** | 0 | 0 | 0 | 0 |
| worst non-orthogonality | 60.99 | 61.96 | 83.29 | 89.08 | 89.08 | 89.08 | 89.08 |
| mean | 10.65 | 9.96 | 9.54 | 9.67 | 9.67 | 9.67 | 9.67 |
| worst adjacent area ratio | 13.04 | 11.85 | **80.27** | 12.35 | 12.35 | 12.35 | 12.35 |

**The solve never gets far enough to curve anything**: it reports `diverged=1` at sweep 13, and
forced to 20 it folds six cells. **[I]** This is §6b item 2 — no corner relaxation — arriving
as a measurement rather than a stated absence, and it is the sharpest single thing this whole
note has to say about the difference between the two tools. GridPro's curved block boundaries
are not a drawing style; they are what a converged elliptic solve over a free wireframe
produces, and the reproduction cannot have them by that route.

### 10c. So the curve is DERIVED instead, and both constructions are unique

Two one-line constructions, each determined by its own data rather than chosen, which is the
only honest way to put a curve into a declaration here:

- **A RADIAL is the arc through its two corners that LEAVES ITS INNER RING ALONG THAT RING'S
  OWN NORMAL.** A circular arc through two points with a prescribed tangent at one of them is
  unique: the centre sits on the normal at that end, at `r = |d|² / (2 d·n)`
  (`arc_tangent_at` in `make_rings.py`). It is the orthogonality condition at the inner end
  written as a shape — the one the straight chord was violating.
- **THE TRAILING-EDGE TAIL IS THE RING'S OWN CURVE CONTINUED.** Each of its two sides leaves
  ring 1 along the **ellipse's own tangent** there, so the ring is smooth where the tail joins
  it and the only corner left is the one the wedge needs for its fourth side (§8e). §9's
  version was two straight chords meeting in a box behind the trailing edge.

**One of the four tail sides comes back STRAIGHT, and that is derived rather than an
exception.** The side leaving the wake's own landing is asked to leave along the ellipse's
tangent at its rightmost point, which is vertical — and its tail corner sits vertically above
it, so the unique arc through the two is the straight line, `arc_tangent_at` returns no curve,
and the chord is the answer. **[I]**

Both are DEFAULTS now; `--chord-radials` and `--chord-tail` put either back, which is what
makes the table below a measurement. All four rows: `--split 8 --rings 3`, 17408 cells,
5 sweeps. **[V]**

| | worst non-orth | mean non-orth | worst wall cell | worst wall angle | worst area jump |
|---|---|---|---|---|---|
| both chords (§9's version) | 63.195 | **9.298** | 0.142% | 15.31° | 12.744 |
| curved tail only | 56.611 | 9.232 | 0.142% | 15.31° | 12.744 |
| curved radials only | 63.483 | 9.594 | 0.014% | 4.74° | 12.565 |
| **both curved (shipped)** | **55.277** | 9.552 | **0.011%** | **none reported** | **12.565** |

The two do different jobs and neither substitutes for the other: **the tail buys the worst
corner** (63.195 → 56.611 on its own) and **the radials buy the wall** (0.142% → 0.014%, and
the worst wall grid-line angle 15.31° → 4.74°). Together the run reports **no wall-control
warning at all and `clipped=0`** — the control function holds the declared first-cell height
and the 90 degrees at every wall edge without once asking for a push the kernel cannot take,
which no other case in this note manages.

### 10d. The shipped case, restated **[V]**

`make_rings.py --split 8 --rings 3 --ring-normal-radials` — named by flag rather than as
"the defaults", because §11 moves them:

```
cells=17408 inverted=0 nonortho_max=55.277 nonortho_mean=9.552
wall_first_cell_worst_rel=0.000111  quad_midline_ratio_median=2.801 p95=13.058
adjacent_area_ratio_max=12.565      smoother: 5 of 5 sweeps, diverged=0, clipped=0
```

**§11 supersedes this as the shipped case**, and the two figures are §11's mesh, not this one.

### 10e. Against everything before it

All at 17408 cells and 5 sweeps, so the columns differ in BLOCKING and in BOUNDARY SHAPE and
in nothing else: **[V]**

| | §8: 14 blocks | §9: 58 blocks, chords | §10: 58 blocks, curves |
|---|---|---|---|
| worst non-orthogonality | 59.856° | 63.195° | **55.277°** |
| mean non-orthogonality | 12.307° | 9.298° | 9.552° |
| cell shape, median / p95 | 2.751 / 13.815 | 2.737 / **13.093** | 2.801 / 13.058 |
| worst wall first cell | 0.0139% | 0.142% | **0.0111%** |
| worst wall grid-line angle | 4.68° | 15.31° | **none reported** |
| worst adjacent area ratio | **11.713** | 12.744 | 12.565 |

**[I]** The curved version is the best mesh in this note on four of the six rows and is the
only one with no wall-control warning; it loses the area-ratio row to §8's much coarser
blocking and the mean by a quarter of a degree to §9's. §9e said the arrangement that looks
most like GridPro's was "better in the field and worse at the wall"; **with the boundaries
curved, the wall half of that verdict is gone.**

### 10f. What is still NOT GridPro's, and it is the same thing as always

**[I]** A curve here is fixed by ONE tangency condition at ONE end of ONE edge. GridPro's is
the solution of an elliptic system over the whole field, so its boundaries are smooth at
**both** ends of every edge and consistent across every block at once. The two constructions in
10c buy the ends that matter most — the ring-normal at the inner end of each radial, the
ellipse tangent where the tail joins the ring — and leave the far end of each to the Coons
fill. That is a cheaper object than what GridPro ships, it is derived rather than drawn, and
10b is the measurement of why the expensive one is not available here.

---

## 11. Why it still did not look like GridPro, and what was actually wrong

The maintainer's verdict on §10 was that the partition curves are drawn nothing like
GridPro's. Putting the two pictures side by side found **three** causes. Two of them are mine
and one of them is not a mesh property at all. 2026-11-06.

### 11a. The first cause was the RENDERING, not the mesh **[V]**

GridPro's figures are **quad** grids. Every figure this note had produced was the
**triangle-split** export — `MB_SPLIT_QUADS 1`, which is what the solver needs and what the
shipped config carries — so the whole picture was criss-crossed with diagonals that have no
counterpart in GridPro's and that dominate its texture. On top of that
`tools/scripts/view_mesh_vtk.py` draws block seams **heavy**, while in GridPro's figures a
block boundary is an ordinary grid line and only the colour says where it is.

Re-rendering the SAME mesh with `MB_SPLIT_QUADS 0` is most of the difference, and it costs
nothing:

```bash
sed 's/^MB_SPLIT_QUADS 1/MB_SPLIT_QUADS 0/' \
    docs/research/gridpro-blocking-method/gridpro_rings.dat > /tmp/q.dat
./run.sh -conf /tmp/q.dat
```

**The two committed figures are now that view** — the same case, exported as quads purely so it
is comparable with GridPro's. **[I]** Worth stating as a method point rather than a footnote:
three sections of this note compared a triangulated picture against a quad one and read the
difference as being about blocking.

### 11b. The second cause was a MISREADING of fig5, in §9a **[V]**

§9a says fig5 is "a dense rosette of small blocks on the bodies, then a ring of roughly
sixteen petal-shaped blocks, then **an outer ring of about the same number reaching the far
field**". Zoomed into its upper-right quadrant, that last clause is wrong. The colour bands in
the outer field — red, orange, green, brown — are **azimuthally** adjacent, and each one spans
the whole radial extent from the near-body rosette out to the outer boundary. **There is no
concentric seam cutting across them.** What fig5 shows is a dense near-body rosette plus
**ONE** layer of sectors.

So §9's three rings put **two** concentric seams into the field where GridPro has none, and
those seams are the most visible structure in the picture. §9c had already measured that more
rings cost mean non-orthogonality; the figure says the same about the shape. Both point at
**two rings**, which is now the default.

**[I]** And a second thing the zoom settles: adjacent blocks in GridPro's outer field carry
visibly **different grid-line directions** — radial in one, nearly horizontal in its
neighbour. Its grid is not one global smooth curvilinear family that blocks are merely
coloured regions of; the blocks really do have their own local orientation, as here.

### 11c. The third cause was a real defect in §10's construction **[V]**

§10c launched **every layer's** radial along **its own ring's** normal. Two consecutive layers
therefore start and end with unrelated tangents, so the partition has a **KINK at every ring
crossing** — visible in §10's figures as a corner on what should be one curve, and the
opposite of GridPro's, which run smoothly from the body to the far field.

The fix is one line and it is still derived: **chain the arcs C1** — each layer leaves along
the tangent the layer inside it arrived with (`arc_exit_tangent`). `--ring-normal-radials`
puts the kinked version back, which is what keeps §10's table re-runnable. At three rings,
where there is something to chain:

| `--split 8 --rings 3` | worst non-orth | mean non-orth | worst wall cell | worst area jump |
|---|---|---|---|---|
| per-ring normal (§10) | 55.277 | **9.552** | 0.0111% | 12.565 |
| C1 chained | **54.339** | 10.754 | 0.0111% | **10.513** |

**[I]** Not a clean numerical win — the worst corner and the size grading improve, the mean
gets worse by 1.2° — and it is kept for the SHAPE rather than for the table. At two rings
there is only one layer to chain and the worst corner is identical either way (48.095).

### 11d. The shipped case, after all three **[V]**

`make_rings.py` with its defaults is now **`--split 8 --rings 2`, curved radials chained C1,
curved tail**: **38 blocks, 56 corners, 94 edges**.

```
cells=17408 inverted=0 nonortho_max=48.095 nonortho_mean=7.137
wall_first_cell_worst_rel=0.001058  quad_midline_ratio_median=2.818 p95=14.107
adjacent_area_ratio_max=14.149      worst wall grid-line angle 5.965 deg
```

What the curves buy at this arrangement, with `--chord-radials --chord-tail` as the control:

| `--split 8 --rings 2` | worst non-orth | mean non-orth | worst wall cell | worst wall angle |
|---|---|---|---|---|
| both chords | 60.688 | **6.767** | **0.059%** | 16.355° |
| curved, C1 (shipped) | **48.095** | 7.137 | 0.106% | **5.965°** |

### 11e. Everything side by side, and the verdict changes again **[V]**

All at 17408 cells, 5 sweeps:

| | §8: 14 blocks | §9: 58, chords, 3 rings | §10: 58, curved, 3 rings | §11: 38, curved, 2 rings |
|---|---|---|---|---|
| worst non-orthogonality | 59.856° | 63.195° | 55.277° | **48.095°** |
| mean non-orthogonality | 12.307° | 9.298° | 9.552° | **7.137°** |
| cell shape, median | **2.751** | 2.737 | 2.801 | 2.818 |
| worst wall first cell | 0.0139% | 0.142% | **0.0111%** | 0.106% |
| worst wall grid-line angle | 4.68° | 15.31° | **none** | 5.97° |
| worst adjacent area ratio | **11.713** | 12.744 | 12.565 | 14.149 |

**[I]** The arrangement that matches the figure is also the best on both non-orthogonality
columns and the worst on the size-jump one. **§9e's and §10e's verdicts were each written
against a blocking with two seams GridPro does not have**, so this row supersedes them rather
than refining them.

### 11f. What is STILL different, and it is now only two things

1. **DENSITY.** GridPro's fig5 outer field carries several times the radial resolution of this
   17408-cell budget, which is why its cells look uniform where the big outer blocks here look
   empty. That is a node count, not a blocking — `N_AROUND`, `N_WALL` and `N_OUT_TOTAL` in
   `make_rings.py` — and every table in §§9-11 holds the budget fixed on purpose so that the
   blocking is what is being compared.
2. **§10b, unchanged.** GridPro's curvature is a converged elliptic solve; here the smoother
   reports `diverged=1` at sweep 13 and folds cells if forced past it, so every curve in this
   reproduction is DECLARED from a tangency condition rather than solved for. That is the one
   difference no amount of re-blocking closes.

---

## 12. The far field, and a NEGATIVE result

§11 fixed the near-body blocking; the maintainer's next observation is that the far field
still looks nothing like GridPro's. It does not, the reason is structural, and after building
the thing that would fix it I could not make it work. This section is that attempt.
2026-11-06.

### 12a. What GridPro's far field actually is **[V]**, read off fig6

`fig6.webp`'s top panel, zoomed into its two halves:

- **Upstream and above/below**: the grid lines wrap the nose in a C and then run **parallel
  and streamwise** — horizontal lines ahead of the leading edge and over the body, with the
  vertical family crossing them. Not a fan.
- **Downstream**: the lines leaving the trailing edge run **horizontally** in a straight wake
  band, with a lattice of blocks above and below it.
- ~~**The outer boundary is a RECTANGLE**, and the grid becomes a Cartesian lattice aligned
  with it.~~

> **THAT LAST CLAIM IS WRONG AND §18d RETRACTS IT.** fig6's panel does not show an outer
> boundary, because **it does not reach one**. Measured off the panel itself: the body's chord
> is 555 px of its 701, so it covers about `x ∈ [-0.10, 1.16]`, `y ∈ [-0.37, 0.35]` CHORDS, and
> the grid runs off all four edges (edge luminance 0.56-0.81, no closed dark boundary
> anywhere). It is a NEAR-BODY view. What this section read as "a Cartesian lattice against a
> rectangle" is the near-body grid, which is streamwise there for the ordinary reason. **The
> only far field any source in this note states is the tutorial's own "circle of radius 3 units
> with center 1 0" (§3a), quoted from GridPro's text.**

**[I]** So GridPro's single-body far field is a **C/H** arrangement: a body-conforming ring,
a straight wake band, and Cartesian H blocks filling the rest out to a rectangle. Everything
§§9-11 built is O-rings fanning out to a circle. That is not a difference of curvature or of
block count; it is a different topology family.

### 12b. `--box`: a rectangular far field, built and measured **[V]**

The cheap half is reachable: `--box` replaces GridPro's tutorial circle with a rectangle
(`x ∈ [-2, 7]`, `y ∈ [±3]` about the trailing edge) and morphs the rings out to it. The four
corners of the box have to BE stations, or the ring side spanning one chamfers it off, so the
four nearest stations are pinned to the corner directions and the rest re-spread between all
eight anchors.

It runs, and the downstream half does become a streamwise band. The rest does not:

| `--split 8 --rings 2`, 17408 cells | circle (shipped) | `--box` |
|---|---|---|
| inverted | 0 | 0 |
| worst non-orthogonality | **48.095°** | 89.236° |
| mean non-orthogonality | **7.137°** | 16.602° |
| worst wall first cell | 0.106% | **0.020%** |
| worst wall grid-line angle | **5.97°** | 43.84° |
| worst adjacent area ratio | **14.149** | 24.191 |

**[I]** The upstream half stays a radial fan, because a ring is a ring: nothing about naming
the outer boundary a rectangle makes the lines ahead of the nose horizontal. `--box` is kept
as the record of that, not as a default.

### 12c. ONE BUG FOUND ON THE WAY, worth recording **[V]**

The first `--box` run came back with **216 inverted cells**. The cause was not the box: the
step that BLENDS a station's far-field angle toward where the wrap's own normal lands was
still measuring against the **circle**, which with a box is a boundary that is not there. It
moved one station (`u3`) past two of its neighbours — 90.63, 99.62, 108.41, **135.00**, 125.40,
133.81, 142.74 round the walk — so their radials crossed. On a box the even share between
anchors is also the right answer, and skipping the blend there fixed it.

**[I]** The shape of this is one this repo has seen before: a step that is correct for one
boundary silently applied to another. It cost nothing to find only because the mesher counts
inverted cells and refuses.

### 12d. AND THE FIX FOR 12a WAS ATTEMPTED AND ABANDONED **[V]**

A Cartesian H field needs the outer rings to be **nested BOXES joined AXIS-ALIGNED** —
vertical lines above the box, horizontal lines beside it — rather than a ray from a centre.
That was built: a box family growing geometrically, with each station keeping its side and
its coordinate along that side on every box.

**It folds, and the reason is arithmetic rather than a coding slip.** The innermost box has to
clear the wrap ellipse, which reaches `x = -0.4`; measured from the far field's centre at the
trailing edge that needs at least **0.47 of the far box's upstream extent**, while the
downstream and vertical directions need only 0.07 and 0.10. A box family that keeps the far
field's aspect therefore cannot be small anywhere, and at the sizes that are small enough
downstream it **cuts inside the wrap ellipse ahead of the nose** — the ring-1-to-ring-2 layer
inverts. Measured: **376 inverted cells at three rings, 228 at four.** The code was removed and
the comment where the blend now sits says why.

**[I]** The escape is to drop the homothety — let each box have its own aspect — but then the
four corner DIRECTIONS differ from box to box, and a station pinned to a corner on one is not
on a corner of the next, which is the thing 12b needed corners for. The two requirements are
in direct conflict in this construction.

### 12e. What it would actually take **[I]**

A C/H topology document: a C-ring around the body **and its wake**, a straight wake band to the
outlet, and Cartesian H blocks filling the rest to a rectangle. That is not a knob on this
generator — the walk, the station mapping and the block list are all different — and it is a
piece of work rather than an edit.

It is also not unexplored ground here. `docs/research/multi-element-airfoil-blocking.md`
records this group building exactly that shape for a **two-element** section — "two 8-block
O-rings, each wrapped to an AXIS-ALIGNED RECTANGULAR box embedded in a Cartesian H grid" — with
**0 inverted cells but a neighbouring-cell area ratio reaching 23×**. So the construction is
known to be reachable in this repo, and known to cost on the quantity §12b's table already
shows the box costing.

**The honest summary of §§9-12**: the near-body blocking now matches GridPro's and measures
better than anything else in this note; **the far field does not match and this note did not
get it to.** What is in the tree is the measurement of why, and `--box` is the runnable record
of the half that is reachable.

---

## 13. The C/H topology, built

§12e said what matching GridPro's far field would take and called it "a piece of work rather
than an edit". This is that work. `make_ch.py` + `gridpro_ch.json` + `gridpro_ch.dat`,
**24 blocks**, and it is the best mesh in this note on two of the six columns. 2026-11-06.

### 13a. The shape **[I]**, from §12a's **[V]** reading of fig6

A C-ring around the body **and its wake**. The xi walk runs from the outlet BELOW the wake,
forward along it to the trailing edge, round the lower surface to the nose, back along the
upper surface to the trailing edge, and out along the wake to the outlet ABOVE it. **Every
wake edge is met twice and is ONE edge both times** — that is what makes it a cut and not two
coincident walls — and the trailing edge is one node on five edges where four blocks meet.
The eta lines run from that C out to a RECTANGLE. **The DEFAULT extent is `x ∈ [-2, 7]`,
`y ∈ [±3]`** — 9 × 6 chords — because that is closest to what the O-ring cases of §§9-11 have
(GridPro's tutorial circle of radius 3), so §13e's comparison is made at a comparable domain.
**It is not the size to solve on**, and §14c is the measurement: at Re 200 it cuts through the
viscous region and its residual band sits **1.5×** above the one at the shipped C-grid case's
own 30 × 20. `--domain -10 20 10` is that one. Both have been run through the solver.

Nothing wraps round the front, so the lines leaving the nose point **at the inlet** and the
lines leaving the wake point at the top and bottom. That is §12a's fig6, and it is a property
of the topology rather than of any tuning.

```
cells=18240 inverted=0 nonortho_max=44.735 nonortho_mean=4.503
quad_midline_ratio_median=2.721 p95=26.753  adjacent_area_ratio_max=3.026
wall first cell: 0.09% worst on the BODY, 3.32% worst counting the far-field edges
```

At `--domain -10 20 10` the same document measures **39.578 / 4.203 / 3.594 / 4.556**. Both
rows are in §13e's table. **These are §15's numbers**, after the trailing-edge fan's first wake
station was pushed aft; before that they were 54.793 / 4.304 / 2.648 / 7.813 and
61.529 / 3.908 / 3.505 / 14.180.

### 13b. The map that makes it streamwise: a station's own NORMAL, cast **[V]**

Where a body station's far-field point goes decides everything, and three laws were tried:

| the far-field point of a body station is... | result |
|---|---|
| its share of the far-field C by ARC LENGTH | mid-chord lands opposite **x = -1.89**, so every grid line leaving the body swings forward to reach it: **18.2°** mean with straight radials, and a set of near-concentric arcs with curved ones |
| where its own outward NORMAL arrives | mid-chord's normal is vertical, so it lands on the top or bottom at the **same x** — streamwise by construction — and the nose, whose normals fan through 180°, sweeps the whole corner. **4.3°** mean |
| (a monotone cubic through four anchors) | written, then made unreachable by the row above and **deleted** rather than left in |

**[I]** And a consequence worth stating: with this map the chord from a body station to its
far-field point is ALREADY along the normal, so §10c's "arc that leaves perpendicular"
degenerates to the chord and `--chord-radials` produces the same mesh. The curvature machinery
is still there and is simply not needed here.

### 13c. FIVE defects found while building it, each with its measurement **[V]**

Recorded because every one of them produced a mesh that looked plausible and was not, and
because four are properties of the C shape rather than of this code.

1. **The walk had the lower surface's stations in REVERSE** — it went from the trailing edge
   to the station nearest the NOSE and back. **4042 of 17280 cells inverted.** The fix was to
   record what lies between two walk entries WHEN THE WALK IS BUILT instead of deducing it
   from the two corner names afterwards.
2. **The arc-length map**, 13b's first row. 18.2° mean.
3. **GridPro's equal bisection CANNOT be used at the trailing edge here.** Its lower ray leaves
   at -85.866° and lands on the rectangle at **x = 1.2170**, while the normal of the very next
   station on the lower surface lands at **x = 1.2425** — BEHIND it — so the two radials cross
   and the map refuses. The bisection ray is *steeper* than the surface normal it sits beside,
   and on a thin trailing edge that is enough. What is used instead is the surface's own
   one-sided normal, which makes the four sectors there **90.0 / 81.7 / 81.7 / 90.0** degrees
   rather than 85.87 each. **[I]** This is the first thing in this note that GridPro's own
   rule and a C-grid disagree about, and the disagreement is small but real.
4. **Equal arc-length body stations.** With the normal map, the last stretch before the nose
   faced a far-field stretch **36 times its own length**: 12 inverted and a worst adjacent area
   ratio of **2132**. The law that fits is **equal increments of the surface NORMAL's own
   direction** — which is also what puts the stations where the surface turns. Area ratio
   2132 → 432.
5. **The first wake station has to be DERIVED from the trailing-edge radial.** That radial
   leaves along the surface normal and lands a little aft of the trailing edge; a wake station
   closer in than that lands in FRONT of it and the two pinch. Measured: they landed **0.013
   apart** and four cells inverted between them. Putting the first station at half as far again
   as that landing fixes it by construction. Area ratio 432 → 198.
6. **The cut's clustering has to turn round with it.** The wake is one edge walked twice in
   opposite senses, so the far-field edge facing it the second time must carry the MIRRORED
   spacing; otherwise its fine end sits opposite the inner edge's coarse one, the block's two
   xi sides cluster against each other and the fill twists. Measured: **two inverted cells just
   aft of the trailing edge and a 177.894° corner between them.** Area ratio 198 → **7.8**, and
   the last inverted cells gone.

**[I]** Defects 5 and 6 are both the trailing edge, and both are the price of the cut: it is
the one place where two different parts of the walk have to agree about the same geometry.

### 13d. The figures **[V]**

`gridpro_ch_full.png` (the whole 9 × 6 default domain) and `gridpro_ch_te.png` (the body and
the near wake), rendered as QUADS for §11a's reason. `gridpro_ch_M.png` is a Mach field from
§14, taken on this same default domain. The
downstream half is a streamwise lattice, the upstream half points at the inlet, the wake is a
thin band along `y = 0`, and the far field is a rectangle the grid is aligned to — which is
what §12a set out to reproduce.

### 13e. Against everything before it **[V]**

| | **the repo's OWN C-grid** | §8: 14 blk | §10: 58 blk, 3 rings | §11: 38 blk, 2 rings | §13: C/H, DEFAULT 9×6 | §13: C/H, `--domain -10 20 10` |
|---|---|---|---|---|---|---|
| blocks | **4** | 14 | 58 | 38 | 24 | 24 |
| cells | 11520 | 17408 | 17408 | 17408 | 18240 | 18240 |
| inverted | 0 | 0 | 0 | 0 | 0 | 0 |
| worst non-orthogonality | **31.382°** | 59.856° | 55.277° | 48.095° | 44.735° | 39.578° |
| mean non-orthogonality | 4.340° | 12.307° | 9.552° | 7.137° | 4.503° | **4.203°** |
| cell shape, median | 4.791 | 2.751 | 2.801 | 2.818 | **2.721** | 3.594 |
| cell shape, p95 | 148.672 | **13.815** | 13.093 | 14.107 | 26.753 | 58.356 |
| worst adjacent area ratio | **1.484** | 11.713 | 12.565 | 14.149 | 3.026 | 4.556 |
| worst wall first cell, BODY only | 0.05% | 0.01% | 0.01% | **0.01%** | 0.09% | 0.09% |
| worst wall first cell, ALL wall edges | 0.0846% | **0.0139%** | 0.0111% | 0.106% | 3.32% | 16.11% |
| far-field extent, chords | 30 × 20 | 30 × 20 | 6 × 6 | 6 × 6 | 9 × 6 | 30 × 20 |
| far field | D of a circle | D of a circle | circle | circle | **rectangle** | **rectangle** |

**THE FIRST COLUMN IS `config/multiblock_cgrid.dat`, THE CASE THIS REPO ALREADY SHIPS**, and
it was missing from every version of this table until §14's solver run needed it as a control.
It is four blocks, 11520 cells, and it still **beats everything in this note on the worst
corner and on size grading** — 31.4° and 1.48 against the C/H's 39.6° and 3.0. It is quoted at
5 sweeps like the rest of the table; at its own shipped default of 20 it reads 29.895° /
3.821° / 2.276.

**[I]** So the honest ranking is not the one the preceding sections were building toward. What
the C/H does win is **cell shape at the median** — 2.721 against 4.791, and the shipped case's
p95 of 148.7 is a long tail of very stretched cells that none of the subdivided blockings here
have. It is level on the mean and 8° behind on the worst corner. **§15 is where that 8°
went**, and it is not the block count.

**The two C/H columns are the same document at two domain sizes**, and the LEFT one is the
default — it is the fair comparison with §§9-11, whose far field is the tutorial's r = 3 circle.
The §8 and shipped columns' far field is already 30 × 20, so it is the right-hand C/H column
that is comparable with THEM. **Neither is "the" answer**: §14c shows the big domain is the
better one to solve on, and the table shows it is the worse mesh on four of the six metrics.
The cell counts are not equal either — 11520, 17408 and 18432 — and no column here is a
controlled experiment against another; they are six documents measured the same way.

**Every "all wall edges" figure here is AFTER smoothing**, read off `HYBMESH_MB_QUALITY`
rather than the `_BEFORE` line beside it — the two differ by 3× on this case (5.95% against
16.88%), and an earlier draft of this table mixed them.

**The cell counts are not equal** — 18432 against 17408, 5.9% more — because the C/H's station
law is derived rather than dialled, and the nearest settings either side came out at 17088
(worse grading) and 21504 (better). The columns are still worth reading: a 6% cell difference
does not move a mean from 7.1° to 4.3° or an area ratio from 14.1 to 7.8.

**[I]** Against the O-ring family the C/H wins the mean by a wide margin and cell shape
outright, and loses the far-field spacing — its outer boundary is a rectangle whose four
corners the control function has to turn through. **The BODY's own first cell is held by all
of them**: 0.01% for the ring cases, 0.05% for the shipped one, 0.09% here, all measured off
the bound aerofoil edges only, which is the figure a viscous solve cares about; the "all wall
edges" row is dominated by the far field, which no case is asked to resolve.

**What this note does NOT support is "use the C/H".** The repo's own four-block C-grid is
better on the worst corner and on size grading than anything built here, at two thirds of the
cells. What §§9-13 establish is a reproduction of GridPro's ARRANGEMENT and what each step of
it cost — not a better mesh for this body.

### 13f. What is still not GridPro's **[I]**

§10b, and only §10b: its curvature is a converged elliptic solve and this repo's smoother
diverges at sweep 13, so every line here is placed by a declaration rather than solved for.
Everything else §§9-12 listed as different — the far field's shape, the streamwise lattice, the
wake band, the block count being in the right range — is now reproduced.

---

## 14. GATE 2: the C/H through the solver

§13 is gate 1 — it meshes, 0 inverted. **And setting this run up is what put the repo's own
shipped C-grid into §13e's table, where it changes the verdict**: it was only ever here as the
control, and it is the better mesh.

 `.claude/rules/mesher-multiblock.md` records that on
this repo's C-grid **gate 2 is the one that bit**: zero inverted cells on the first run of the
shipped declaration, and the solver then went to NaN in 40 iterations. So the C/H was run.
2026-11-06.

**It does not NaN.** Ten thousand iterations, exit 0, and no NaN or Inf anywhere in the
solution, the residual history or the surface quantities.

### 14a. How it was run **[V]**

`docs/research/gridpro-blocking-method/gridpro_ch_demo.json` through `./run_pipeline.sh` — it
meshes whatever `gridpro_ch.json` currently holds, so the big-domain run is
`make_ch.py --domain -10 20 10` first — at
**#57's own operating point** — laminar NS, M 0.2, Re 200, zero incidence, `cfl 0.6`,
`constant_cfl`. The headless runner derives the `.bc.def` from the mesh's own patches (#91),
so nothing was hand-edited:

```
segm_no   bc_flag          1 -> 2   the aerofoil's upper surface (no-slip wall)
        1        2         2 -> 2   its lower surface
        2        2         3 -> 1   everything else (non-reflecting far field / outflow)
        3        1
```

**[V]** That is the SAME flag set the shipped C-grid case gets — its `outlet` and `farfield`
patches both map to 1 in `services/bnd_io._NAME_TO_FLAG` — so the boundary treatment is not a
difference between the two runs and the mesh is.

**The control is the shipped `config/pipeline/multiblock_cgrid_demo.json`**, run identically,
because "the solver runs" is only worth quoting against something.

### 14b. The NaN question, answered **[V]**

| | C/H, 9 × 6 (shipped) | C/H, 9 × 6 before §15b | C/H, 30 × 20 | control: shipped C-grid |
|---|---|---|---|---|
| 100 iterations | — | exit 0, no NaN | exit 0, no NaN | exit 0, no NaN |
| 2000 iterations | — | exit 0, no NaN | exit 0, no NaN | exit 0, no NaN |
| **10000 iterations** | **exit 0, no NaN** | **exit 0, no NaN** | **exit 0, no NaN** (159.6 s) | exit 0, no NaN (128.7 s) |

**Four runs, four passes.** The mesh changed under §15b after the first three, so gate 2 was
re-run on the shipped one rather than inherited.

**ONE FALSE POSITIVE, RECORDED SO IT IS NOT RE-FOUND.** `work/tWall_values.dat.cli` contains
the literal `NAN` in both runs — three fields of its third row. It is a property of that output
file and not of either solve; **the control has it too**, and the control is the run
`.claude/rules/mesher-multiblock.md` already records as passing. The files that matter
(`xtecp_sol_allz.dat.cli`, `unicones.enorm.cli`, `vsurface_qty.dat.cli`, `binDumpZ.dat.cli`)
are clean in both.

### 14c. BUT THE RESIDUAL STALLS **[V]**

Worst-of-row from `unicones.enorm.cli`, 10000 iterations, all three runs:

| iteration | 1000 | 2000 | 3000 | 4000 | 5000 | 6000 | 7000 | 8000 | 9000 | median |
|---|---|---|---|---|---|---|---|---|---|---|
| C/H, 9 × 6, **shipped** | 1.46e-04 | 1.30e-04 | 1.41e-04 | 1.78e-04 | 1.65e-04 | 1.04e-04 | 1.23e-04 | 1.10e-04 | 9.04e-05 | 1.30e-04 |
| C/H, 9 × 6, before §15b | 1.44e-04 | 1.55e-04 | 1.61e-04 | 1.80e-04 | 1.68e-04 | 1.39e-04 | 8.59e-05 | 1.28e-04 | 7.85e-05 | 1.44e-04 |
| C/H, 30 × 20, before §15b | 4.71e-05 | 1.13e-04 | 1.13e-04 | 8.96e-05 | 5.50e-05 | 9.34e-05 | 1.14e-04 | 6.23e-05 | 1.01e-04 | 9.34e-05 |
| control (C-grid, 30 × 20) | 5.26e-05 | 8.59e-06 | 4.11e-06 | 4.05e-06 | 4.11e-06 | 1.61e-06 | 5.38e-06 | 3.00e-06 | 2.91e-06 | **4.11e-06** |

The control descends two orders and holds. **Every C/H run stops descending after about a
thousand iterations and then oscillates in a band.** None diverges — the bands are flat over
9000 iterations — and nothing goes non-finite in any of them. The C/H sits **32×** above the
control's floor as shipped, and **23×** on the big domain.

> **AND §15b's MESH FIX BARELY MOVED IT, WHICH IS THE MOST USEFUL ROW IN THIS TABLE.** That
> change took the worst corner from **54.79° to 44.74°** and the worst adjacent area ratio
> from **7.81 to 3.03** — and the residual's median went from 1.44e-04 to 1.30e-04, **10%**.
> **[I]** So whatever the solve is reacting to, it is not the worst corner and not the size
> grading; those were the two obvious suspects and both are now ruled out by measurement
> rather than by argument. What is left unexplained is most of the 32×. **§16 explains it**:
> it is the leading-edge clustering, worth 147× on its own, while the domain is worth 2× and
> the cell count 1×.

> **A FIGURE I GOT WRONG, CORRECTED HERE RATHER THAN QUIETLY REPLACED.** An earlier draft of
> this section said the domain was worth "a factor of four", from comparing a **2e-04** sample
> on the small domain against a **5e-05** sample on the big one. Those are two single points in
> two OSCILLATING bands, picked at different iterations — exactly the comparison
> `docs/research/hermite-wall-normal-fill.md` records as worthless for ranking. Over the whole
> 10000 iterations the medians give **1.54×**, not 4×. The domain helps; it helps a third as
> much as the first look suggested.

**[I]** So the domain is worth 1.5× as measured here — **2× when §16a measures it properly,
on the SHIPPED C-grid moved between domains rather than on two versions of mine** — and
§15b's mesh fix 1.1×. **§16 has the rest of the 32×, and it is one thing.** As shipped the
C/H is the worse mesh for this solve; at §16's `--turn-blend 0.6` it converges further than
the case this repo ships. What is claimed here is the gate: it runs, at both domain sizes and
every version of the mesh tried, without going non-finite.

**[I]** What is left is the mesh. The C/H's worst corner is 61.5° against the shipped C-grid's
29.9°, and its worst adjacent area ratio 14.2; those are the obvious suspects, and this note
has not separated them. **No claim is made here that the C/H is a better mesh for this solve.**
What is claimed is the gate: it runs.

### 14d. What is NOT claimed **[I]**

- **Not convergence.** Neither run converges — the control's own floor at 3e-06 is a floor,
  not a solution, and `docs/research/hermite-wall-normal-fill.md` already records that no
  shipped case in this repo reaches a settled force at this operating point.
- **Not accuracy, and no forces are quoted.** A force difference between two unconverged
  transients drifts with the iteration count; that is the finding of #157 and quoting one here
  would repeat the mistake it recorded.
- **Nothing is committed from the runs.** The solver output lives under `results/solver/` like
  every other run; what is in the tree is the pipeline script that reproduces it.

---

## 15. Why the repo's FOUR-block C-grid beats the 24-block one

The question §13e's new first column raises. The answer is not the block count, and the way
to tell is to stop comparing one number per mesh and ask WHERE each one's worst corner is.
2026-11-09.

### 15a. The two worst corners are in different places, for different reasons **[V]**

Both at 5 sweeps, both read off the quad export:

| | C/H, 24 blocks | shipped C-grid, 4 blocks |
|---|---|---|
| worst corner | 54.79° at **(1.408, ±2.792)** | 31.38° at **(0.013, ±0.020)** |
| what is there | the trailing-edge fan reaching the top and bottom boundary | **the leading edge itself** |

Worst corner BY REGION, same two meshes:

| region | C/H | shipped |
|---|---|---|
| within 0.1 of the leading edge | **10.01°** | 31.38° |
| within 0.1 of the trailing edge | 21.82° | **8.22°** |
| the body band (`\|y\| < 0.5`, `0 < x < 1.2`) | 39.61° | **31.38°** |
| the far field (`\|y\| > 2.5`) | 54.79° | **5.72°** |

**[V]** **At the leading edge the C/H is three times better** — 10.0° against 31.4° — and the
leading edge is where the shipped case's own worst corner is. The extra blocks and §13b's
equal-normal-turn station law did exactly what they were meant to. **§16d is what that 10°
cost**, which this section did not know when it was written: the same law makes the smallest
cell in the mesh six times smaller, and that is what stalls the solve. The C/H loses overall in
ONE region: the far field.

### 15b. The far-field defect was MINE, and pushing on it proved it **[V]**

The worst corner sat where the trailing-edge fan meets the top and bottom boundary. §13c
defect 5 already had the first wake station derived from the trailing-edge radial's landing,
at `f = 1.5` times it — enough to stop the two radials CROSSING, not enough to stop the block
between them tapering into the boundary. Its far side is its body side minus that landing, so
its taper ratio is `(f - 1) / f` while every other wake block's is 1.

Pushing `f` is the test, and a localisation is not a cause until it is:

| `f` | worst corner | where | worst area ratio |
|---|---|---|---|
| 1.5 | 54.793° | (1.408, -2.792), the fan | 7.813 |
| 2.5 | 46.481° | the same point | 3.846 |
| **4.0** | **44.735°** | **(-2.000, 2.007), the INLET** | **3.026** |
| 6.0 | 44.735° | the same inlet point | 2.946 |

**The worst corner moves somewhere else and then stops responding** — identical at `f = 4` and
`f = 6`. That is the confirmation: the fan's taper WAS the 54.79°, and `f = 4` (taper ratio
0.75) is where it stops being what decides. **That is the criterion the shipped generator
uses** — pushed until it is no longer binding, not tuned to a target.

What it bought, on the default domain: worst corner **54.793 → 44.735**, worst area ratio
**7.813 → 3.026**, the body band **39.61° → 20.89°**, the trailing-edge neighbourhood
**21.82° → 13.29°**, and the far-field wall spacing 5.95% → 3.32%, against mean
**4.304 → 4.503** and cell-shape p95 24.4 → 26.8. On `--domain -10 20 10` the worst corner
goes **61.529 → 39.578** and the area ratio **14.180 → 4.556**.

### 15c. What is LEFT is the far field's own corners **[I]**

At `f = 4` the worst corner is **44.735° at (-2.000, 2.007)** — on the INLET, a third of the
way from the rectangle's top-left corner. The shipped case cannot have that corner: **its far
field is a smooth D** — straight top and bottom, a nose semicircle, an outlet plane — with no
90° turn anywhere. Mine is a rectangle with four.

This repo has measured the same thing once before. §12b put a rectangular far field on the
O-ring family and the worst corner went **48.095° → 89.236°** for no other change. A rectangle
is expensive here, and it is in the C/H because §12a's reading of fig6 says GridPro's is one.

**[I]** So the three-way answer to "why is the four-block one better":

1. **Not the blocks.** Region by region the C/H is better at the leading edge and in the body
   band after §15b, which is most of what a viscous solve resolves.
2. **One defect of mine**, the trailing-edge fan's taper, worth 10° of worst corner and 2.6×
   of area ratio — found, fixed, and the fix is in the tree.
3. **One difference of KIND**: a rectangular far field against a smooth D. That is not a
   defect, it is what §12a set out to reproduce, and §12b has already measured what it costs.

**And §14c is the sting in it**: §15b's fix, which is a real improvement on every mesh metric
that moved, changed the solver's residual by **10%**. The worst corner and the size grading
were the two obvious explanations for the stall and the measurement rules both out. Whatever
separates these two meshes in the solve, this note has not found it.

**And a fourth thing that is not a defect either**: the shipped case spends 11520 cells on
30 × 20 chords, so its far-field cells are enormous and very stretched — cell-shape p95
**148.7** against the C/H's 26.8. Stretched cells aligned with a smooth boundary have
excellent ANGLES and terrible ASPECT. The two meshes are good at different things, and the
single "worst non-orthogonality" number was never going to say so.

---

## 16. What the 32× actually was

§14c left the C/H's residual stalling **32×** above the shipped C-grid's floor with the two
obvious explanations ruled out. This section chases it, and the answer is none of the things
§§13-15 were about. 2026-11-09.

**It is the LEADING-EDGE CLUSTERING — §13b's own station law — and the trade is 20 degrees of
leading-edge non-orthogonality against two orders of residual.**

### 16a. Five suspects, eliminated one at a time **[V]**

Every row is an experiment, not an argument. All at #57's operating point, 10000 iterations.

| suspect | how it was tested | worth |
|---|---|---|
| the residual column is per-ZONE, so a 24-block max beats a 4-block max | counted the non-trivial columns: **30 of 30 in both**, and the max is column 2 in every row of both | **nothing** — the comparison is like for like |
| the worst corner and the size grading | §15b's fix: 54.79° → 44.74°, area ratio 7.81 → 3.03 | **1.1×** |
| the domain | the SHIPPED C-grid rebuilt on the C/H's own 9 × 6 box — same topology, same 4 blocks, same 11520 cells, mesh quality unmoved (33.4° / 4.75° / 1.39) | **2×** (4.11e-06 → 8.28e-06) |
| the cell count | that control REFINED to 18000 cells on the same 9 × 6 box, matching the C/H's 18240 | **1×** — it still reaches 4.73e-06 |
| **the smallest cell** | `--turn-blend`, which relaxes §13b's station law from equal normal turn toward equal arc | **147×** |

**[I]** The third and fourth rows are the ones worth having done. Both were plausible, both
are standard explanations for a slow steady solve, and both are worth nothing here — and the
only way to know was to move the CONTROL onto my domain and my cell count rather than move my
mesh toward its.

### 16b. The smallest cell is in the SAME PLACE in both, and six times smaller in mine **[V]**

| | C/H (blend 1.0) | control, 9 × 6, 18000 cells |
|---|---|---|
| smallest cell, area | **3.905e-07** | 2.334e-06 |
| ... its side | 6.25e-04 | 1.53e-03 |
| where it is | **(0.001, -0.006)** | (-0.001, 0.002) |

Both are **at the leading edge**. The wall-normal height is the same `BL_INITIAL_THICKNESS` of
1e-3 in both, so what differs is the CHORDWISE spacing there — and that is §13b's law. Equal
increments of the surface normal put the stations where the surface turns, and on an aerofoil
nose the normal sweeps through 180° in a few per cent of chord.

### 16c. Relaxing it is the whole of the 32× **[V]**

`--turn-blend w` interpolates the station fractions between equal arc length (`w = 0`) and
equal normal turn (`w = 1`, §13b's law and the default).

| `w` | smallest cell | residual at 9000 | shape of the history |
|---|---|---|---|
| **1.0** (default) | 3.905e-07 | **9.04e-05** | stalls after ~1000, flat band |
| 0.6 | 2.220e-06 | **8.85e-07** | descends monotonically, still falling |
| 0.0 | 2.249e-06 | 1.88e-06 | descends monotonically |
| — control, 9×6, 18000 cells | 2.334e-06 | 6.63e-06 | descends, plateaus near 3e-06 |
| — control, 9×6, 11520 cells | 2.417e-06 | 8.28e-06 | descends, plateaus near 6e-06 |

**Every mesh whose smallest cell is about 2.2e-06 converges; the one at 3.9e-07 does not**, and
that is the only property in this table that sorts it. **[I]** It is the expected behaviour of
a pseudo-time steady iteration with local time stepping — the smallest cell sets the smallest
local step — but this note measured it, and measured it only after assuming three other things
that turned out to be worth 1.1×, 2× and 1×.

**At `w = 0.6` the C/H reaches 8.85e-07, below the shipped C-grid's own floor at either
domain.**

### 16c-bis. The two figures **[V]**

**`nose_compare.png`** — the same leading edge under the three station laws, quad export, same
window. The left panel is what `w = 1.0` does: a dozen blocks crammed into a few per cent of
chord, because that is where the normal turns. The middle and right panels are `w = 0.6` and
the shipped C-grid, which look like each other. Under each panel: the smallest cell, the
leading-edge angle, and what the residual did.

**`residual_compare.png`** — the four residual histories of 16c on one log axis, drawn by
`plot_residuals.py` beside it. One line stays flat; three descend. The flat one is the mesh
with the 3.9e-07 cell.

### 16d. And the trade is exactly §15a's leading-edge win, bought back **[V]**

| | `w = 1.0` (shipped) | `w = 0.6` |
|---|---|---|
| worst corner within 0.1 of the LEADING EDGE | **10.01°** | 30.30° |
| mean non-orthogonality | 4.503° | **3.144°** |
| worst non-orthogonality | **44.735°** | 52.197° |
| worst adjacent area ratio | **3.026** | 6.665 |
| cells | 18240 | 16128 |
| residual at 9000 iterations | 9.04e-05 | **8.85e-07** |

**[I]** §15a presented the leading edge as where the extra blocks and the station law simply
WON — 10.0° against the shipped case's 31.4°. They did not win it for free. Relaxing the law
gives that 20° straight back (30.30°, which is the shipped case's 31.4° to within a degree)
and buys two orders of residual. **The 10° and the stall are one decision seen from two ends.**

### 16e. What is shipped, and what to use **[I]**

**The default is still `w = 1.0`**, so every figure in §§13-15 stands as measured and this
section invalidates none of them. **For a solve, pass `--turn-blend 0.6`** — it is the only
version of this mesh that converges, and it converges further than the case this repo ships.

The general statement, which is the part worth keeping: **on this path a station law chosen
for ANGLES silently sets the smallest cell, and the smallest cell is what the solver feels.**
Nothing in `HYBMESH_MB_QUALITY` reports it — the cell-shape figure is a RATIO and the
area-jump figure is between NEIGHBOURS, so a uniformly tiny region scores well on both.
§16a's first four rows are what reading only those metrics costs.

---

## 17. fig6 as the target, built

§13's C/H got the TOPOLOGY FAMILY right and §11 got the far field right, but put side by side
with `fig6.webp` the two still do not look alike, and the maintainer said so. This section
takes that figure as the target. 2026-11-09.

`make_ch.py --layers 3 --split 16 --turn-blend 0.8`, shipped as
`gridpro_ch_fig6.{json,dat}`: **120 blocks**, 25984 cells, 0 inverted, and it **converges**.

### 17a. What was missing, read off the figure **[V]**

Three things, and only the third is about block count:

1. **A thin ring HUGGING the body**, cut into blocks chordwise — fig6 has two or three of them
   before the field opens out. §13 had ONE layer: every block ran from the aerofoil straight
   to the far field. **§12a had already recorded "two or three layers radially" and §13 did
   not build it.**
2. **The nose fan**, which §13 has.
3. **Density** — fig6 is subdivided far more finely, both ways.

### 17b. The rings go at a constant DISTANCE, not a constant fraction **[V]**

`--layers L` puts `L - 1` rings between the body and the rectangle. Placing them at a constant
fraction of each radial is the obvious thing and is wrong here: these radials run **2.0 chords
at the nose to 6.0 down the wake**, so a fixed fraction makes a band three times thicker at one
end than the other — not a ring hugging anything. Measured, at three layers:

| rings placed at | worst non-orth | mean | worst area ratio |
|---|---|---|---|
| a constant FRACTION of the radial | 59.189° | 5.481° | 9.020 |
| a constant DISTANCE (0.05, 0.25 chords) | 55.369° | 3.885° | 13.749 |
| ... and with 17c's seams matched | **44.982°** | **2.902°** | **3.494** |

### 17c. Each layer's first cell is the previous layer's LAST **[V]**

Three rings means three radial segments per station, and left to themselves their cells come
out at **0.002 / 0.013 / 0.17** — the seams are 6× and 14× jumps in cell size. The fix is the
idiom `.claude/rules/mesher-multiblock.md` records for the shipped two-ring O-grid: **"the
outer ring's `ds_start` IS the inner ring's last interval"**. `layer_last_interval` estimates
that trailing cell by solving for the geometric ratio that fills the span, and hands it to the
layer outside as its leading one.

Worth **13.749 → 3.494** on the area ratio and **3.885° → 2.902°** on the mean. DERIVED: change a
layer's thickness or its node count and the one outside follows.

**[I]** And one thing that looked like a defect and is not: the rings visibly bulge between
stations in the render. That is the smoother relaxing them — they are plain interfaces with no
declared shape, so it may. At **0 sweeps the worst area ratio is 19.809**, against 13.749 at
five. The bulge is the smoother equalising cell sizes, not spoiling them.

### 17d. The nose: stations by COUNT, not by clustering **[V]**

§16 found that getting nose resolution by CLUSTERING (`--turn-blend 1.0`) makes the smallest
cell 3.9e-07 and stalls the solve. The three-layer mesh reproduced that independently — at
`--turn-blend 1.0` its smallest cell is **3.907e-07** and its residual stalls at **1.42e-04**,
the same as §13's single layer. So §16's finding is not an artefact of one blocking.

But relaxing to `0.6` **also takes the nose fan away** — fewer stations near the nose, so fewer
radials fanning to the inlet, and the picture stops looking like fig6. The way out is not to
tune the clustering: it is to **buy the nose with SECTORS**.

| `--split` | `--turn-blend` | blocks | worst non-orth | mean | smallest cell |
|---|---|---|---|---|---|
| 8 | 1.0 | 72 | 44.982° | 2.902° | 3.907e-07 (stalls) |
| 12 | 0.6 | 96 | 50.283° | 2.062° | 1.639e-06 |
| 16 | 0.6 | 120 | 54.704° | 1.882° | 1.846e-06 |
| **16** | **0.8** | **120** | **42.873°** | 2.090° | **1.630e-06** |
| 20 | 0.6 | 144 | 47.801° | **1.733°** | 1.963e-06 |

`--split 16 --turn-blend 0.8` is shipped: the best worst-corner of the set, and a smallest cell
above §16c's threshold.

### 17e. Where it stands **[V]**

All at 5 sweeps, the 9 × 6 box, #57's operating point:

| | the repo's C-grid | §13: C/H, 1 layer | **§17: C/H, 3 layers** |
|---|---|---|---|
| blocks | 4 | 24 | **120** |
| cells | 11520 | 18240 | 25984 |
| inverted | 0 | 0 | 0 |
| worst non-orthogonality | **31.383°** | 44.735° | 42.873° |
| mean non-orthogonality | 4.340° | 4.503° | **2.090°** |
| cell shape, median / p95 | 4.791 / 148.672 | **2.721 / 26.753** | 4.152 / 87.144 |
| worst adjacent area ratio | **1.484** | 3.026 | 4.553 |
| worst wall first cell, BODY | 0.05% | 0.09% | **0.01%** |
| smallest cell | 2.3e-06 | 3.9e-07 | 1.6e-06 |
| residual at 9000 iterations | **2.91e-06** | 9.04e-05 (stalls) | 6.50e-06 |

**[I]** It is the best mean non-orthogonality in this note by a wide margin, holds the wall an
order better than either, and **converges** — which §13's does not. It still loses the worst
corner and the size grading to the repo's own four blocks, and its cell-shape tail is long
because the thin rings are high-aspect by construction, exactly as fig6's are.

### 17f. The figures, and how close it is **[I]**

`vs_fig6.png` is the two side by side, `gridpro_ch_fig6_full.png` and `_te.png` are the mesh
alone. What now matches: the thin rings hugging the body and the wake, cut into blocks
chordwise; the fan at the nose; the straight wake band; the rectangular far field with a
streamwise lattice against it; and a block count in the same range.

What still does not: **fig6 is denser**, and its rings continue forward around the nose as
rings, where mine hands the nose region to the fan instead. Neither is a topology difference
any more — they are node counts and where the fan starts.

---

## 18. The H outer field, built — and the premise it was built on

§17f left one structural difference against fig6: GridPro's outer region looked like a
Cartesian lattice and mine was the C-wrap's own fan. The maintainer asked for that to be
tried. It was, it works, it costs — and then measuring fig6 properly showed the difference was
never there to begin with. Both halves are below, in that order, because that is the order
they happened in. 2026-11-09.

### 18a. It builds, and §12d's blocker does not apply **[V]**

`--h-outer` makes the second-to-last ring a BOX **open at the outlet** — the same C shape the
far field is — and the step from it to the far field **axis-aligned**: top and bottom straight
out at the same x, the inlet side straight forward, the two corners to the far field's own
corners. `gridpro_ch_h.{json,dat}`, **160 blocks**, 0 inverted.

**§12d failed at this on the O-ring family and this does not, for a nameable reason.** There
the inner box had to clear a CLOSED ellipse upstream while keeping the far field's aspect, and
at the sizes that were small enough downstream it cut inside the ellipse. Here the inner object
is a thin band hugging the body, and **the box is open downstream**, so there is no downstream
extent to match. The conflict is gone.

`gridpro_ch_h_full.png` is it: vertical lines above and below the box, horizontal ones ahead of
it, and the two corner wedges.

### 18b. ONE BUG, because the bands and the box have to agree **[V]**

The body-conforming bands grow geometrically, `0.05 × 5^(k-1)`, so at five layers the third sits
at **1.25** against a box at **1.0** — outside it. The band crosses the box and the layer folds:
**727 inverted cells at five layers, 453 at six.** With a box the bands now run geometrically
from `WALL_BAND` up to **half the box's own inset** instead, which fits by construction. Every
layer count from 4 to 7 then meshes at 0 inverted, and the four-layer worst corner improves
**59.432° → 57.754°**.

### 18c. And it costs, on every column **[V]**

| | §17: fan outer field | §18: H outer field |
|---|---|---|
| blocks | 120 | 160 |
| cells | 25984 | 33408 |
| inverted | 0 | 0 |
| worst non-orthogonality | **42.873°** | 57.754° |
| mean non-orthogonality | **2.090°** | 4.866° |
| worst adjacent area ratio | **4.553** | 10.172 |
| smallest cell | 1.63e-06 | 1.64e-06 |
| residual at 9000 iterations | **6.50e-06** | 1.17e-05 |

The worst corner sits on the box's own inlet side, at `(-0.80, ±0.726)`, and **four levers do
not move it**: a bigger box trades it for the mean (at `(-1.6, 2.0)`: mean 3.136° but worst
79.838°); carrying the inlet side straight forward so the upstream lines are truly parallel
makes it **worse** (71-89°, because the corner wedges then skew instead); more sectors make it
worse (16 → 24 takes it 59° → 77°); and more rings do nothing (max stays 57-60° from four
layers to seven), **because the crowding is AZIMUTHAL — 32 stations carried onto a short box
perimeter — and subdividing radially cannot reach it.**

**[I]** This is §12b's measurement again, one layer in: a rectangle is expensive on this path.
There it cost the O-ring family 48.095° → 89.236° as a far-field boundary; here it costs the
C/H 42.873° → 57.754° as an interior ring.

### 18d. THEN THE PREMISE TURNED OUT TO BE WRONG **[V]**

§12a read "the outer boundary is a RECTANGLE" off fig6's top panel. That panel **does not
contain an outer boundary**. Measured: the body's chord is **555 px** of the panel's 701, so it
covers roughly `x ∈ [-0.10, 1.16]` and `y ∈ [-0.37, 0.35]` chords, and the grid **runs off all
four edges** — edge luminance 0.556 / 0.596 / 0.645 / 0.811, with no closed dark boundary. Its
other four panels are two leading-edge zooms (the icing horn is visible in both) and two
wireframes. **None of the six shows a far field.**

So the rectangle was my inference from a crop, and the only far field any source here states is
the tutorial's **circle of radius 3 about the trailing edge** (§3a, GridPro's own words) — which
is what §§8-11 used and what §13 moved away from.

**[I]** What this does and does not invalidate:

- **The measurements all stand.** A rectangle really is expensive here (§12b, 18c); the H field
  really is buildable (18a); §16's smallest-cell finding is untouched; §17's rings and seam
  matching are untouched and are supported by fig6, which **does** show the near body.
- **The motive for §§12b, 12d, 13's rectangle, 17's rectangle and 18 does not.** They were
  aimed at a far field no source describes.
- **`near_body_compare.png` is the only comparison fig6 supports**, and it is in the tree:
  fig6 against §17 and §18 at fig6's own measured extent.

### 18e. What that comparison actually says **[V]**, read off the figure

At fig6's own window the three are directly comparable, and:

1. **fig6 subdivides the surface far more**: its thin rings carry roughly 15-20 blocks per side
   within this window, against 5-6 in mine. **[THE 5-6 IS WRONG — §25a.** §17's topology already
   carries 32 wall-bound edges over 32 distinct blocks, i.e. **16 per side**, which is inside the
   band this line says it is short of. The 5-6 was an eyeball count off `near_body_compare.png`,
   whose window shows only part of the chord. The fig6 side of the claim is unmeasured either
   way.**]**
2. **its rings are thinner and there are more of them** — several very thin strips where mine
   has two or three thicker ones.
3. **it is denser** throughout.
4. **§17 and §18 are nearly indistinguishable in this window.** The whole difference between
   them is outside it. **[I]** So the figure that motivated §18 cannot adjudicate §18.

---

## 19. The far field, compared — a comparison with no vendor side

### 19a. There is no vendor far field for an aerofoil **[V]**

§18d had just retracted §12a's "GridPro's far field is a rectangle", because that reading came
off a crop. So before drawing a far-field comparison the first question is whether **any** image
on either page contains an outer boundary at all.

Measured, on all six mesh images from the two pages: for each of the four edges, the mean and
standard deviation of a thin strip along it. A bounded mesh photographed on a white page has
**bright, low-variance** edge strips; a crop has mesh running off every side, so every strip
carries edges and its variance stays high.

| image | edge mean L R T B | edge std L R T B |
|-------|-------------------|------------------|
| `fig5.png` | 0.63 0.36 0.67 0.51 | 0.144 0.266 0.150 0.284 |
| `fig6.png` | 0.56 0.47 0.63 0.67 | 0.158 0.251 0.124 0.253 |
| `image17_GP.png` | 0.93 0.77 0.99 0.55 | 0.126 0.399 0.105 0.459 |
| `image18_GP.png` | 0.90 0.72 0.92 0.67 | 0.135 0.380 0.134 0.372 |
| `image15_GP.png` | 0.54 0.55 0.43 0.46 | 0.217 0.361 0.152 0.417 |
| `feature.png` | 0.12 0.27 0.17 0.33 | 0.206 0.409 0.233 0.444 |

No strip in the table is a uniform background: the lowest standard deviation anywhere is 0.105.
**Every one of the six is a crop.** **[V]**

Two honesty notes on that verdict. First, `image17_GP.png` is the weakest reading in the set —
its left and top strips are both bright and the two lowest-variance strips in the table
(0.93/0.126 and 0.99/0.105), which is the *bounded* signature, and it does visually appear to
have a closed outer arch. Its right and bottom do not, and it carries an inset panel in a corner,
which puts mesh on an edge that would otherwise be empty — so the per-edge test cannot resolve
it. Second, and decisively for this section: **`image17_GP.png` is a three-blade wind turbine,
not an aerofoil**, so even read the other way it is not a far field for the case being
reproduced here.

My first pass at this test had the logic **backwards** — it looked for a *dark* rim, where a mesh
on a white page has a *bright* one — and would have called every image bounded. The table above
is the redone test. **[V]**

### 19b. The only far field any source STATES **[V]**

One, and it is text rather than an image: the tutorial's own
`a circle of radius 3 units with center 1 0` (§3a). That is the circle §8/§10/§11 were built on.
Everything else about a GridPro far field in this note is either inference from a crop or
retracted (§12a, §18d).

### 19c. The four-way comparison, measured

`docs/research/gridpro-blocking-method/farfield_compare.png`
(regenerate: `python3 docs/research/gridpro-blocking-method/plot_farfield_compare.py <out.png>`).
Top left, the four outer boundaries on one scale; top right, the table below; bottom, each mesh
at its own extent, all four windows cut to the same aspect ratio so the panels align.

All four at `BL_INITIAL_THICKNESS 0.001` and `MB_SMOOTH_ITERS 5`, the same normalisation §15's
table used: **[V]**

| far field | blocks | cells | max | mean | area jump |
|-----------|--------|-------|-----|------|-----------|
| C arc, 30 × 20 (`config/multiblock_cgrid.dat`) | 4 | 5760 | **31.382** | 4.340 | **1.484** |
| rectangle, 9 × 6 (§13/§17) | 120 | 12992 | 42.873 | **2.090** | 4.553 |
| circle, r = 3 @ (1,0) (§8–11, the tutorial's own) | 38 | 8704 | 48.095 | 7.137 | 14.149 |
| H box, 9 × 6 (§18) | 160 | 16704 | 57.754 | 4.866 | 10.172 |

The shipped C-grid's **own** default is `MB_SMOOTH_ITERS 20`, not 5; at 20 it measures
max 29.895, mean 3.821, jump 2.276 — better angles, worse area jump. The figure states this
rather than leaving "shipped" to be read as the as-shipped config. **[V]**

### 19d. What it says

1. **The smallest far field is not the best one.** The tutorial's own circle, r = 3, is the
   worst of the four on every column — max 48.1°, mean 7.14°, area jump 14.1. The best is the
   **largest**, 30 × 20, and it gets there with 4 blocks and 5760 cells. **[V]**
2. **Changing the far field's SHAPE costs more than changing the block count.** The same C/H
   topology, same body, same spacing laws, rectangle → H box: max 42.873 → 57.754, area jump
   4.553 → 10.172, for 40 more blocks. **[V]** That is the same direction and roughly the same
   size as §12b's measurement on the O-ring family (48.095 → 89.236), so it is a property of
   putting straight far-field segments where the body's own rays want to land, not of one
   topology. **[I]**
3. **The one column the fine blocking wins is the mean.** 2.090° against the C arc's 4.340°,
   which is §16's finding seen from the far-field side: the fine blocking buys interior
   smoothness and pays for it at the corners where its many declared edges meet. **[V]**

---

## 20. The far field, compared AGAINST GridPro

§19 compared four far fields of my own, because no page image shows an outer *boundary*. That
answered a narrower question than the one asked. A boundary is not needed to compare the
far-field **blocking pattern** — only a region, and `fig5`'s top panel is one.

### 20a. Which image, and at what scale **[V]**

Of the six mesh images, three are 3-D (`image15_GP`, `image17_GP`, `image18_GP` — nacelle,
turbine, turbine) and `fig6` and the centre of `feature.png` are near-body views of a
multi-element aerofoil. **`fig5`'s top panel is the only 2-D aerofoil far-field blocking in
either article**: one body at the centre, block-coloured, rings crossed by radial sectors, mesh
running off all four edges.

The scale had to be measured off the image. The body renders as a pale region; its largest
connected pale component is **86 px** long (x 571–656), with a second pale fragment at x 684–697
that is probably the trailing edge behind a grid line, which would make it **127 px**. Taking
100 px and carrying ±15%, with the body's centre at (621, 388) in the 1260 × 716 panel, the
panel's window is

**x ∈ [−6.2, +6.4], y ∈ [−3.3, +3.9]** chords — about 12.6 × 7.2 chords. **[V]**

### 20b. The comparison **[V]**

`docs/research/gridpro-blocking-method/vs_fig5_farfield.png`
(regenerate: `python3 docs/research/gridpro-blocking-method/plot_vs_fig5.py <fig5_top.png>
results/meshes/<rings mesh>.vtk <out.png>`; the source image is not committed, see the Sources
note). Top row, the same on-screen chord length; bottom row, GridPro cropped to my own window.
The counterpart is §11's O-ring case — 2 concentric rings × 16 circumferential sectors, 38 blocks
— because that is the family `fig5` shows.

1. **Range. `fig5` already *shows* about twice my whole domain.** My O-ring far field is the
   tutorial's circle, r = 3 about (1,0): 6 × 6 chords in all. `fig5`'s panel is 12.6 × 7.2 and
   **is itself a crop** (§19a), so its real boundary is further out again. The top row is that
   statement as a picture: GridPro fills the frame; mine occupies the middle of it. **[V]**
2. **Sector width. GridPro's sectors are many and roughly EVEN in angular width all the way
   round. Mine are not** — four wide wedges (two downstream, two upstream, ~60° each) and twelve
   narrow ones bunched at the leading edge. **[V]** No sector *count* is claimed for `fig5`: an
   automated count of colour runs round a circle, after a median filter to remove the grid lines,
   bounced between 7 and 21 depending on radius, which is not a measurement. **[V]**
3. **Radial lines. GridPro's curve; mine are straight rays.** Its sector boundaries fan and bend
   as they go out; mine leave the body on a normal and keep going. **[V]**
4. **Cell size in the far field. GridPro's stays roughly constant out there; mine grows.** In
   `fig5`'s outer half the grid is nearly uniform; my outer ring's cells are much larger than its
   inner ones. That is exactly §19c's `adjacent_area_ratio_max` = **14.149**, the worst of the
   four far fields I built, seen as a picture rather than a number. **[I]** on the attribution of
   GridPro's uniformity to a deliberate choice; **[V]** on both appearances.

### 20c. What this does NOT say

`fig5` is a crop with no scale bar, no axis, and a body whose length can only be measured to
±15%. Every quantity in 20a is derived from that one measurement. Nothing here establishes where
GridPro's outer boundary is, only that it is **beyond** the 6.4 chords the panel reaches — which
is still enough to settle the one comparison that was asked for, since my own stops at 3. **[V]**

---

## 21. The O-ring re-partitioned THE WAY FIG5 PARTITIONS

§20b named four differences between `fig5`'s far-field blocking and §11's O-ring. This section
tries to adopt them. Two could be, one was refused with its cost measured, and one turned out to
have been attributed to the wrong place.

Case: `gridpro_rings_even.dat` / `.json`, generated by
`make_rings.py --even-sectors --prop-nodes body`. Figure:
`vs_fig5_even.png` (`plot_vs_fig5_even.py`), three panels at one window — `fig5`, before, after.

### 21a. What was adopted, and what it measures **[V]**

**Equal ANGLE on ring 1** (`--even-sectors`) in place of equal arc length on the body. The
station is no longer picked on the body and followed outward; a target angle is picked on the
ring and the body fraction that lands there is solved for, so every circumferential block
subtends the same angle. **And each stretch's node count follows its own length**
(`--prop-nodes body`) instead of every stretch getting `N_AROUND / 2K`.

**The two are a pair, and the second is not optional.** Equal angle alone is a REGRESSION:

| | blocks | cells | max | mean | area jump |
|---|---|---|---|---|---|
| §11, equal arc, uniform counts | 38 | 17408 | 48.095 | 7.137 | 14.149 |
| equal angle, uniform counts | 38 | 17408 | 47.550 | **7.900** | 15.325 |
| equal angle + counts by body arc | 38 | 18528 | **47.550** | **5.958** | 15.282 |
| equal angle + counts by far arc | 38 | 17184 | 47.550 | 8.851 | 15.413 |
| equal angle + counts by their geometric mean | 38 | 17856 | 47.550 | 6.316 | 15.301 |

Equal angle makes the stretches unequal in length; a uniform count then puts a 15× cell-area
jump across the radial between two neighbouring sectors, which is worse than the 14.1 it was
meant to improve. With the counts following the body arc the mean falls **17%**, 7.137 → 5.958,
and the worst corner improves slightly, 48.095 → 47.550, for 6.4% more cells. The area jump is
0.8 worse. **[V]**

**More rings and linear ring growth were both tried and both lose**, so neither is in the shipped
case: **[V]**

| variant | max | mean | area jump |
|---------|-----|------|-----------|
| 4 rings, semi-axes growing LINEARLY | 48.095 | 8.962 | 16.305 |
| … plus equal angle | 47.348 | 9.271 | 18.468 |
| … plus 24 sectors | 47.348 | 9.245 | 26.923 |
| 3 rings, geometric, equal angle + counts | 54.339 | 9.254 | 13.121 |
| 4 rings, geometric, equal angle + counts | 62.035 | 9.964 | 25.012 |

Linear growth was adopted on a wrong premise — that geometric growth is what makes the outer
cells large. It is, at the outer end; but at the INNER end geometric is what keeps the first step
off the thin wrap small, and linear puts ring 2's semi-minor at 1.2 where geometric puts it at
0.646, a 4× first step off `b = 0.3`. The flag stays in the file with that written at its own
definition. **[V]**

### 21b. The default case is untouched, and that was checked rather than assumed **[V]**

Every edit above is behind a flag, and `make_rings.py` with no flags reproduced
`gridpro_rings.json` **byte for byte** after each one — until the last, which could not be
behind a flag: with five or more trailing-edge rays the fan's arcs split into equivalence classes
that ray 0 does not reach, and the mesher refuses by name ("no edge in a group of 5 structurally
linked edge(s) declares a 'count'"). Seeding EVERY ray's radial with the same `N_WALL` fixes it
and adds one line to the default's JSON, so that file was regenerated; the default mesh is
**coordinate-identical** across the change (`POINTS` block diffed, and all three quality figures
agree to six decimals). **[V]**

### 21c. What was REFUSED: fig5's all-narrow sectors **[V]**

The four wide wedges in my picture are the trailing-edge fan's own sectors, 85.87° each, and
`--even-sectors` cannot touch them — it only redistributes the body's stations within what the
fan leaves. `fig5`'s sectors are **all** narrow, which needs a finer fan, and a finer fan is
refused on this body.

Ignoring the refusal costs, measured: `--te-rays 5` → **816 inverted cells of 14384**;
`--te-rays 7` → 1810 of 19504; `--te-rays 9` → 2616 of 24848. In every case exactly TWO blocks
are inverted and they are a mirror pair, whole-block (408 of 408 cells each). **[V]**

**The cause took two attempts.** The first was that the rays at ±114.488° point back over the
body and cross it — written up as a guard, and it **fired on nothing**: a ray leaving (1, 0) at
that angle clears a 12%-thick body easily. The second came from printing the walk: the stations
are ordered correctly on ring 1 and **not on the far circle**. A ray reaches the circle at its
own angle, 114.488°, while the first body station behind it reaches it by a normal, at about
108° — so the ray's radial overtakes the station's and the two cross. The cyclic walk's
far-circle steps then sum to **1042°** instead of 360, with two steps of +353.5°, and the two
ring blocks declared across those steps are the two inverted ones. **[V]**

That is the check now in the file: the far-circle steps must sum to 360. It refuses `--te-rays`
5, 7 and 9 and passes 3, every pre-existing flag combination, and the `--even-sectors`
combinations. Note that `--te-rays 5` WITHOUT `--even-sectors` was already refused, by §9's
ordinal check on ring 1 — equal-arc stations interleave there. Equal-angle stations do not, so
they walked straight past that refusal into a folded mesh. **Two conditions, two checks; the
first does not imply the second.** **[I]**

This is §10's incompatibility between GridPro's equal bisection and a normal-cast far map,
reached from the other side — there the lower ray landed at x = 1.2170 and the next station's
normal at 1.2425, behind it. **[V]**

### 21d. A correction to §20b, reading 4 **[V]**

§20b said my far-field cells grow outward where GridPro's stay uniform, and attributed
§19c's `adjacent_area_ratio_max` = 14.149 to that. **The attribution is wrong.** Localised: in
§11's mesh the worst pair sits at **r = 0.44 from the trailing edge**, between blocks 16 and 19,
and the worst corner (48.095°) at **(−0.2449, +0.1684)**, which is the nose. Neither is in the
far field. After the restyle the worst pair moves out to r = 2.94 but is still at the junction
between the trailing-edge fan and the first body stretch, and the worst corner moves to
(+1.4000, −0.2178), r = 0.455 — the fan again.

**So the far-field blocking is not what limits this mesh, before or after.** The appearance in
§20b reading 4 is real — the cells do grow outward, and that is visible — but the number quoted
beside it is set somewhere else. What the restyle bought is the 17% in the mean; what it could
not touch is the fan, which is where both extremes live. **[V]**

---

## 22. The difference inventory, with the evidence each row rests on

`docs/research/gridpro-blocking-method/vs_fig5_differences.png`
(`plot_differences.py`). `fig5` and §21's restyled O-ring at one window, with the seven
differences and, for each, **what kind of evidence it rests on** — because two of this note's
readings have now been quoted with more confidence than their evidence carried (§18d, §20b).

| # | item | GridPro (`fig5`) | this O-ring | status | evidence |
|---|------|------------------|-------------|--------|----------|
| 1 | fineness of the trailing-edge fan | fine; every sector narrow | four wedges of 85.87° | **REFUSED** | §21c: `--te-rays` 5/7/9 → 816/1810/2616 inverted cells; the radials cross on the far circle |
| 2 | are the sector angles even | roughly even all the way round | a dozen narrow ones bunched at the nose | **ADOPTED** | §21a: mean 7.137° → 5.958°, max 48.095° → 47.550°, cells +6.4% |
| 3 | shape of the radial lines | curve as they go out | near-straight after leaving the normal | **not done** | appearance only. `CURVED` is already an arc here, too slight to see. Not quantified |
| 4 | far-field reach | the panel alone reaches ±6.4 chords, and is a crop | circle r = 3, the tutorial's own | **changeable, at a cost** | §19c: the same C/H in a rectangle goes max 42.9° → 57.8°, jump 4.55 → 10.2 |
| 5 | number of concentric rings | no concentric seam visible when zoomed — one outer layer | 2 rings (body ring + one) | **same** | §11b's correction; §21a measured 3 and 4 rings at max 54.3 / 62.0 |
| 6 | far-field cell size | looks roughly uniform | grows outward | **not done** | appearance only. §21d: the 14.149 jump is at r = 0.44 from the TE, not out there |
| 7 | the body-hugging ring (Wrap) | present, and stated in the vendor's own text | present; ring 1 is it | **same** | §3's Wrap step; both have one |

### 22a. TWO image measurements that FAILED, named so the table is not over-read **[V]**

Neither number appears in the table, and both were attempts to quantify a row:

1. **`fig5`'s sector count** (row 2). Counting colour runs round a circle after a median filter to
   remove the grid lines gave 21, 15, 7, 11, 11, 18 at r = 1.25 … 3.33 chords. A count that
   depends that strongly on where it is taken is not a measurement.
2. **Mesh density** (an attempt at rows 1 and 2 together). Counting line crossings round a circle
   gave 127/170/174/159 at r = 1.5/2.0/2.5/3.0 on `fig5`. Run as a CONTROL on my own mesh, whose
   true answer is `N_AROUND` = **96**, the same detector returned 157/204/163/110 — it
   over-counts about 2×, because a circle grazes the circumferential lines and registers each as
   a crossing. The control is what killed the number; without it, "GridPro has ~170 lines around
   the body against my 96" is a sentence this note would now contain, and it would be false.

A third quantity was attempted and abandoned the same way: radial spacing along rays, which the
same detector reports between 0.04 and 0.35 chords on neighbouring bands of the same ray, because
it cannot tell a radial line from the circumferential one crossing it. **[V]**

### 22b. What the inventory says overall **[I]**

Of the seven, three already agreed, one was adopted and measured, one is refused with the cost of
ignoring it measured, and two remain as appearance with no number behind them. The two that
remain are rows 3 and 6 — the curvature of the radials and far-field cell uniformity — and both
are cosmetic in the sense that §21d established: this mesh's worst corner and worst area jump
both live at the trailing-edge fan, which is row 1, the one thing the body's own exterior angle
refuses.

---

## 23. Block COUNT and block STRATEGY, compared

`docs/research/gridpro-blocking-method/vs_fig5_counts.png` (`plot_counts.py`).

### 23a. The count: one vendor number, and one that cannot be had **[V]**

**Stated by GridPro: 14 blocks / 4608 cells**, read off its own tutorial dialog (§L2, and the
run report in §3: 0 folds, worst skew 0.255576, max aspect ratio 2.58781).

**`fig5`'s block count is not recoverable from the image.** Three methods, each checked rather
than trusted, and all three failed:

| method | on `fig5` | the check that killed it |
|--------|-----------|--------------------------|
| colour runs round a circle | 21, 15, 7, 11, 11, 18 at r = 1.25…3.33 | internal: a count that swings 3× with the sampling radius is not a count |
| line crossings round a circle | 127 / 170 / 174 / 159 at r = 1.5…3.0 | CONTROL: my own mesh, true answer `N_AROUND` = **96**, came back 157 / 204 / 163 / 110 |
| connected colour blobs, dilated | 315 at r ≥ 0.8, 249 at r ≥ 1.2 | CONTROL: my own mesh, true answer **38 blocks**, came back **96** |

None of those nine numbers is quoted anywhere as a property of GridPro's mesh. The note already
recorded the same limit for Figure 24 in §3 ("I could not count the blocks reliably off Figure
24"); this section is that limit re-established on `fig5` with the methods written down. **[V]**

### 23b. What IS comparable: cells per block **[V]**

The vendor's own stated rule — "the answer to a badly shaped region is MORE BLOCKS, not more
nodes" (§3) — has a number attached to it, and that number survives where the block count does
not, because it only needs each mesh's own totals:

| case | blocks | cells | cells/block |
|------|--------|-------|-------------|
| this repo's shipped C-grid | 4 | 11520 | 2880 |
| §8, my reproduction of the tutorial | 14 | 17408 | 1243 |
| §13 C/H, one layer | 24 | 18240 | 760 |
| §21 O-ring restyled to `fig5` | 38 | 18528 | 488 |
| §11 O-ring | 38 | 17408 | 458 |
| **GridPro's own tutorial** | **14** | **4608** | **329** |
| §17 C/H, three layers (fig6-shaped) | 120 | 25984 | 217 |
| §18 C/H + H outer field | 160 | 33408 | 209 |

Three readings: **[V]**

1. **At GridPro's own block count I used 3.8× the cells** — 14 blocks either way, 1243 against
   329. The reproduction matched the blocking and not the philosophy.
2. **The O-ring family sits at 458–488**, between the two: more block-led than my own C-grid,
   less than GridPro.
3. **§17 and §18 went PAST GridPro**, at 217 and 209. The fig6-shaped C/H is more block-led
   than the vendor's own tutorial case — and §15 and §16 measured what that bought and what it
   cost, so this is the axis those sections were moving along without naming it. **[I]**

### 23c. The strategy, and why it is not a style difference **[V]**

| | GridPro | this repo, `MESH_MODE 1` |
|---|---|---|
| where a corner sits | a GUESS; DBC relaxes it onto the surface | a DECLARATION; **nothing moves it** |
| a badly shaped region | add more blocks (stated rule) | the same, but adding them must pass a refusal first |
| the trailing edge | equal bisection of the exterior angle, 3 internal surfaces | the same rule, with the angles DERIVED from this repo's own aerofoil tangents |
| node counts | a point-wise distribution per edge | `count` is a SEED on an equivalence class; opposite sides follow |
| the smoother | relaxation moves corners and interfaces | declared shapes are FROZEN; only plain interfaces move |

**The last row is the root of every refusal in §§9, 10 and 21.** GridPro's corners get out of each
other's way, so equal bisection keeps working as the ray count rises. Nothing here gets out of the
way, so the same rule pushes the radials into crossing at `--te-rays 5` (§21c), and the same
incompatibility appeared in §10's C/H from the other side. The rule was transcribed correctly;
what does not transfer is the relaxation that makes it safe. **[I]** on the causal claim, **[V]**
on both halves of it — the rule is quoted in §3 and the crossings are measured in §21c.

---

## 24. GridPro's mesh beside the MOST SIMILAR one of mine

`docs/research/gridpro-blocking-method/vs_fig6_matched.png` (`plot_vs_fig6_matched.py`) — the
matched-scale comparison offered in §18e and not delivered until now.

### 24a. Which pair is "most similar", and a correction to §20a **[V]**

Not `fig5` against the O-ring. **`fig5`'s alt text is "Structured Multi-block grid for MDA-3
Element Configuration"** — a THREE-ELEMENT aerofoil, and this repo has no multi-element case at
all. Zoomed, the pixels corroborate it: the main element is one pale blob at x 571–656 and there
is a SECOND, separate pale element behind it at x 684–697.

**That retracts two things in §20a.** "The only 2-D aerofoil far-field blocking in either
article: ONE BODY at the centre" is wrong on the body count. And the 100 px chord it set the
scale with was the main element's 86 px plus what I called "a second pale fragment … probably the
trailing edge behind a grid line" — it is the second ELEMENT. With the main element's own 86 px,
`fig5`'s panel is **x ∈ [−7.2, +7.4], y ∈ [−3.9, +4.5]** rather than ±6.4/±3.9. §20b's reading 1
is unaffected in direction and strengthened in size: `fig5` shows about 2.4× my whole O-ring
domain, not 2×. The far-field *blocking pattern* comparison in §§20–22 stands — an O-fan in the
far field does not depend on the body count — but it is not a like-for-like geometry, and §22's
table did not say so. **[V]**

**`fig6`'s alt text is "Airfoil with Icing, Multi-Block Structured grid using GridPro"** — one
body, and §17 was built with it as the target. That is the only pair in this note that is the
same KIND of geometry with the same intent on both sides. **[V]**

### 24b. The window, measured **[V]**

`fig6`'s top panel: the body is one pale blob **999 px long and 85 px thick** in a 1261 × 720
panel, so the panel spans **1.26 chords** — `x ∈ [−0.08, +1.18]`, `y ∈ [−0.38, +0.34]`. It is a
near-body view and cannot support any far-field claim, which is what §18e found from the other
direction when §17 and §18 came out indistinguishable in it. The 85/999 also makes **GridPro's
section 8.5% thick against NACA 0012's 12%** — measured, ice horn included. **[V]**

### 24c. The seven differences at one scale

| # | item | GridPro (`fig6`) | §17's C/H | status | evidence |
|---|------|------------------|-----------|--------|----------|
| 1 | the body itself | iced section, horn at the nose | clean NACA 0012 | **different** | the vendor's alt text; 8.5% thick against 12%, measured |
| 2 | thin body-hugging rings | 2–3, each cut chordwise | 3 (`--layers 3`) | **adopted** | §17b; §17 was built against `fig6` |
| 3 | surface blocks per side | ~15–20 in this window | **20** (was 16, and never 5–6 — §25a) | **inside the band** | §25: 40 wall edges over 40 blocks, and 21 seams counted back off the figure |
| 4 | rings continue round the nose | yes | yes | **same** | §17f |
| 5 | overall density | visibly denser | 25984 cells | **short of it** | §17f/§18e appearance; no usable density measurement (§23a) |
| 6 | the trailing edge | a fan of more than three links | one `cut` edge shared by both wake blocks | **different strategy** | §3's `fig6` reading vs §13c; both mesh, the shapes differ |
| 7 | cells per block | the tutorial reports 329 (`fig6` has no figure of its own) | 217 | **past it** | §23b |

Three of the seven differences are now things the FIGURE shows rather than things I assert: the
body shape, the ring count, and the trailing edge. Two — rows 3 and 5 — remain appearance,
because §23a's three attempts to count blocks or density off an image all failed their controls.
Row 1 is a geometry difference rather than a blocking difference, and nothing in this note ever
set out to match an iced section. **[I]**

---

## 25. Twenty blocks per surface — and the number that sent me there was mine

The instruction was to raise the surface blocks per side into `fig6`'s 15–20 band and redo the
comparison. Checking the current value first showed the band was **already met**, by a number this
note had got wrong twice.

### 25a. §17 was at 16 per side, not 5–6 **[V]**

`gridpro_ch_fig6.json` carries **32 wall-bound edges over 32 distinct blocks — 16 per surface**,
which is `--split 16` doing exactly what it says. §18e wrote "5–6 in mine" and §24c row 3 repeated
it; both are wrong. The miscount came from eyeballing `near_body_compare.png`, whose window shows
only part of the chord, so only part of the blocks were in frame.

Checked a second way, against the figure rather than the file: counting colour runs along a line
adjacent to the upper surface in the matched-scale panel gives **16** at the row nearest the body
(and 20 and 22 further out, where the second and third ring layers come into the line). The figure
was showing 16 all along. **[V]**

### 25b. The case at 20 per side, and what the extra four cost **[V]**

`gridpro_ch_fig6_s20.{json,dat}`, from `make_ch.py --layers 3 --split 20 --turn-blend 0.8`.
Swept across the band:

| per side | blocks | cells (quads) | inverted | max | mean | area jump |
|----------|--------|---------------|----------|-----|------|-----------|
| 16 (§17) | 120 | 12992 | 0 | **42.873** | 2.090 | 4.553 |
| 18 | 132 | 13776 | 0 | 48.225 | 2.095 | 4.053 |
| **20 (§25)** | **144** | **14560** | **0** | **48.372** | **2.066** | **4.089** |
| 24 | 168 | 16128 | 0 | 49.420 | 1.953 | 3.494 |

**The worst corner gets worse and it is not on the body.** Localised: at 16 it sits at
(−2.0000, +1.7853) and at 20 at (−1.9560, −2.3908) — both at the **upstream far-field corner**,
3.5–3.8 chords from the trailing edge. §17e already predicted this in as many words: raising the
split sends "more radials fanning to the inlet". The step is 5.3° between 16 and 18 and then flat,
so it is the first few extra radials reaching the inlet that cost, not each one. **[V]**

What the extra four buy is small and real: mean 2.090 → 2.066 and area jump 4.553 → 4.089, with
the jump's own worst pair also at the inlet rather than on the body. Going on to 24 continues both
trends (1.953 / 3.494) and costs another degree at the inlet. **[V]**

Cells per block falls 217 → **202**, so §23b's reading 3 holds a little harder: this case is now
further past GridPro's own tutorial ratio of 329. **[V]**

### 25c. GATE 2: the 20-per-side case through the solver **[V]**

`run_pipeline.sh` on the same chain as §17's, 9000 half-iterations: **exit 0, zero NaN**, contour
written. The NaN check itself needed fixing first — `grep -ci nan` matched
`grid/cad/mesh.provena`**nan**`ce.json`, a substring hit in a path, so the count is word-bounded
now. Worst-of-row from `unicones.enorm.cli`, against §17's run at matched iterations:

| iteration | 16 per side (§17) | 20 per side (§25) |
|-----------|-------------------|-------------------|
| 5000 | 1.384e-05 | 5.111e-06 |
| 6000 | 1.073e-05 | 5.392e-06 |
| 7000 | 4.798e-06 | 4.449e-06 |
| 8000 | 7.296e-06 | 6.266e-06 |

**This ranks nothing.** Both sit in the same few-e-06 band and NEITHER is monotone — §25's is
lower at all four matched iterations, but it oscillates by 40% between them, which is the
signature of a solve that has not arrived rather than one that has arrived lower. The claim gate 2
supports is the one it was set up for: the extra four blocks per side do not break the solve. §17's
run printed through 9000 and this one's last printed row is 8000, both from the same
`num_half_iter`; the run exited 0 and nothing was chased there. **[V]**

### 25d. The figures now carry their own proof **[V]**

`vs_fig6_matched.png` draws every block-to-block seam heavy, so the per-side count is countable
off the image instead of asserted. Verified as a control: 21 heavy seams along the upper surface
at the row nearest the body — 20 blocks plus both ends — against the topology's 40 wall edges over
40 blocks. That is the check §18e's claim never had. **[V]**

`vs_fig6_side_by_side.png` (`plot_side_by_side.py`) is the same pair with the difference table
stripped out and both panels filling the page width — the two meshes and nothing else, for looking
at rather than for reading off.

---

## 26. Three observations from the maintainer, measured

Raised against `vs_fig6_side_by_side.png`: (1) the wake region is not like GridPro's; (2) the
blocks carry a curvature in the direction NORMAL to the geometry that looks bolted on; (3) the
aspect ratios look very large — is that good? All three are measurable and all three are right,
and they turn out to be **one** finding seen from three sides.

### 26a. The wake IS different, and it is where everything bad lives **[V]**

`fig6`'s trailing edge, zoomed: a full **rosette centred ON the trailing-edge point** — radials
fanning into every downstream direction with concentric arcs crossing them, the wake being one
direction within that fan rather than a band. Mine: the wall-layer blocks hand over across a
single vertical seam at the TE to two wake blocks, and the wake continues as an **H
continuation**. There is no rosette; the TE is one corner where four blocks meet (§13c's `cut`).

And the wake is where the mesh is worst. Of the worst 1% of quads by cell-shape (midline) ratio,
**145 of 145 — 100% — are in the wake strip**, at x = 1.34…2.47, |y| < 0.05. The single worst is
282.4 at (+2.4713, −0.0010). **[V]**

### 26b. The normal-direction curvature is real, and it is NOT the smoother **[V]**

`docs/research/gridpro-blocking-method/normal_turning.png` (`plot_normal_turning.py`). Every grid
line leaving the body perpendicular to it is followed out to the far field and its accumulated
turning summed:

> **THE FIGURES IN THIS SUBSECTION WERE WRONG AND §27 REPLACES THEM.** The walk had no
> termination condition: on reaching the outer boundary it turned onto that boundary and kept
> going, so the totals include turning that is not in any grid line. The corrected walk stops at
> the outer boundary and reports how many lines fail to reach it; the C/H's real figures are
> **median 6.9°, p95 34.2°, max 82.2°**, not 14.3 / 87.6 / 130.5. The shipped C-grid's 1.8 / 2.7 /
> 2.8 are unchanged, because nothing there ever got near the cap. **Reading 3 below is also
> wrong** — see §27a. What survives is reading 1 and reading 2, and the direction of the
> comparison. Kept rather than rewritten, as §60's specimen rule asks.

| | median | p95 | max |
|---|--------|-----|-----|
| §25's C/H (rectangular far field) | ~~14.3°~~ **6.9°** | ~~87.6°~~ **34.2°** | ~~130.5°~~ **82.2°** |
| this repo's shipped C-grid (concentric C arc) | **1.8°** | 2.7° | **2.8°** |

A line that turns 82° on its way out is not following anything, which is what "bolted on" picks
up. Three things the measurement settles: **[V]**

1. **It is not the smoother.** At `MB_SMOOTH_ITERS 0` the cell-shape max is 285.1 against 282.4 at
   5 and 278.7 at 20, and non-orthogonality is **worse** unsmoothed (53.0° against 48.4°). The
   curvature is there at generation; the smoother slightly reduces it.
2. **It is not at the wall.** The first cross-wall edge leaves along the true surface normal to
   within a median of **0.27°** (p95 2.98°, max 7.66°, and the max is at the nose, x < 0.005).
   The shipped C-grid is far worse there — median **7.84°**, max 31.38°. So mine starts better
   and accumulates worse.
3. ~~**It is the far field's SHAPE.**~~ **WRONG — §27a.** Two predictions this made were tested
   and both failed: the O-ring, whose far field IS a circle, turns the MOST of any case measured
   (median 37.7°  — **that is the family's WORST member; §29a measures the other two at 17.81
   and 8.88**), and enlarging the C/H's rectangle from 9×6 to 40×20 changes nothing
   (6.9 → 7.5 median, p95 identical at 34.2). The cause is the **third body-hugging layer ring**;
   §27a has the sweep.

### 26c. The aspect ratios ARE large — and that is not, by itself, the problem **[V]**

Cell-shape (midline) ratio, split by the quality report's own wall-band / bulk line:

| | wall band p95 / max | bulk p95 / max |
|---|---------------------|----------------|
| §25's C/H, 20 per side | 21.1 / 50.9 | 87.1 / **282.4** |
| §17's C/H, 16 per side | 22.9 / 49.4 | 87.1 / **282.4** |
| this repo's shipped C-grid | **523.3 / 3145.7** | 103.8 / 898.9 |

Two things fall out. **A large ratio in the wall band is intentional** — boundary-layer cells are
deliberately long and thin — and the shipped C-grid, which beats every mesh in this note on every
angle metric and converges best, runs at **3145.7** there, 62× mine. So "the aspect ratio is
large" is not a defect on its own. In the BULK mine is 282.4 against the shipped case's 898.9, so
mine is the milder of the two there as well.

**And raising the split did nothing to them.** §17 at 16 per side and §25 at 20 have the same bulk
p95 and the same bulk max **to six decimal places** — 87.143754 and 282.387906. The worst-shaped
cells are in a part of the mesh the chordwise split does not reach: the wake. **[V]**

### 26d. The three are one finding **[I]**

The wake's blocking (26a) and the worst aspect ratios (26c) sit in the same place — **the wake**
— and neither is in the surface blocking that §21 and §25 were spent on. The normal-direction
turning (26b) turned out to belong somewhere else entirely, and this paragraph's conclusion —
that a concentric far-field boundary was the thing to try next — **was built on the reading §27a
disproves**. What was actually tried, and what it cost, is §27.

---

## 27. The fix, and the two causes that were wrong first

§26d said the thing to try next was a concentric far-field boundary and a trailing-edge rosette.
Both halves of that came from a reading that does not survive measurement. This section replaces
it.

### 27a. The measurement was wrong, then two causes were wrong **[V]**

**The walk had no stop condition.** On reaching the outer boundary it turned onto that boundary
and kept walking, so the totals included turning that is in no grid line. The corrected walk
terminates at the outer boundary and REPORTS how many lines fail to reach it — 0 of 192, 0 of 192
and 0 of 96 across the three cases, which is the control the first version had none of. The C/H's
real figures are **6.9 / 34.2 / 82.2** where §26b published 14.3 / 87.6 / 130.5. The shipped
C-grid's 1.8 / 2.7 / 2.8 are unchanged because nothing there came near the cap, which is exactly
why the error survived a plausibility check.

**Then the cause in §26b reading 3 — the far field's shape — made two predictions and both
failed:** **[V]**

| test | prediction if the far field's shape is the cause | measured |
|------|--------------------------------------------------|----------|
| the O-ring, whose far field IS a circle | low turning | **37.7° median** — the WORST of every case measured, and **§29a: the worst MEMBER of its own family**, whose other two are 17.81 and 8.88 |
| enlarge the C/H's rectangle 9×6 → 20×10 → 40×20 | turning falls toward the C-grid's 1.8° | 6.9 → 7.4 → **7.5°**, and p95 identical at 34.2 all three times |

**The cause is the number of body-hugging LAYER RINGS**, and it is not linear: **[V]**

| layers | median | p95 | max |
|--------|--------|-----|-----|
| 1 | **0.5°** | 7.2° | 17.2° |
| 2 | 1.2° | 8.1° | 12.0° |
| 3 | **6.9°** | **34.2°** | **82.2°** |

At one and two layers the lines are straighter than the shipped C-grid's 1.8° median. The third
ring is where it appears. `--layer-growth` softens it but does not remove it (at 3 layers: 5.0 →
6.9°, 3.0 → 6.0°, 2.0 → 4.8°, 8.0 → 7.7°), so it is the ring's presence, not its thickness.

§17 chose three because `fig6` shows "two or three" thin rings. **The geometry supports two.**

### 27b. The case **[V]**

`gridpro_ch_straight.{json,dat}` — `make_ch.py --layers 2 --split 32 --turn-blend 0.8 --wake 8`.
The split is 32 rather than 20 so the **cell count matches §25's**, 28640 against 29120, which is
what lets the two be compared at all (§27f).

| | §25 (3 layers) | §27 (2 layers) |
|---|----------------|----------------|
| blocks | 144 | 176 |
| cells (split) | 29120 | 28640 |
| inverted | 0 | 0 |
| **wall-normal turning, median / p95 / max** | 6.9° / 34.2° / 82.2° | **0.4° / 4.9° / 10.9°** |
| non-orthogonality max | **48.372°** | 50.062° |
| non-orthogonality mean | 2.066° | **1.840°** |

Turning falls **17× at the median and 7.5× at the worst**, and the result is straighter than this
repo's own shipped C-grid at the median (0.4° against 1.8°). The cost is 1.7° on the worst corner,
which §25 established sits at the upstream far-field corner rather than on the body. The mean
improves to 1.840°, the best of any C/H in this note. At 20 per surface the same change gives
1.2° / 8.1° / 12.0° over 112 blocks and 21600 cells; 32 was chosen for the cell match.

### 27c. The trailing-edge rosette was NOT built, and why **[I]**

Inside a C/H the wake is a `cut` by construction — the C-ring wraps the body AND its wake (§13).
A rosette means the C-ring stops at the trailing edge and a fan takes over, which is not a
modification of the C/H: it **is** the O-ring topology, which this note already has and which
measures worse on the very thing the rosette was proposed to fix — **37.7° median turning**
against the C/H's 6.9 — as well as on every angle metric (§19c: 48.095° against 42.873°).

> **THIS CONCLUSION DOES NOT SURVIVE — §29.** The 37.7 is `gridpro_rings`, the worst of the three
> O-ring cases this note ships; the matched member is `gridpro_tworing` at **8.88** against this
> C/H's 6.92. And total turning is the ruler §28 spent a section moving the C/H AWAY from. The
> sentence above is kept rather than rewritten, as §60's specimen rule asks: §29d's gate-2 run has
> the fan 2.6–4.9× BELOW a cell-matched C/H at every iteration. The first clause — that a rosette
> is not a modification of a C/H — still holds.

What was tried instead is the cheap part of `fig6`'s wake appearance: subdividing the wake
streamwise, `--wake` 4 → 6 → 8 → 10. It buys the mean (2.102 → 2.087 → 2.030 → 2.002) and
**nothing else** — the worst corner is identical to six decimals at all four, and the wake's cell
shape moves 282.553 → 282.534. The shipped case takes `--wake 8`. **[V]**

### 27d. The aspect ratio: intrinsic, not a defect **[V]**

§26c's answer stands and `--wake` confirms it from a second direction: four extra wake blocks do
not move the wake's cell-shape ratio at all. That ratio is set by carrying a `BL_INITIAL_THICKNESS`
0.001 first cell down a C-grid wake, and the repo's shipped C-grid — which converges best of
anything in this note — runs **3145.7** in its wall band and 898.9 in its bulk, against this
case's 50.9 and 282.5. Reducing it means coarsening the wake, which costs wake resolution. It is
what a wake with a y+≈1 first cell costs, not something to fix.

### 27f. GATE 2, and the control that was needed to read it **[V]**

Both variants pass — exit 0, zero NaN. The first reading was misleading:

| iteration | §25, 3 layers, 29120 cells | 2 layers, **21600** cells | 2 layers, **28640** cells |
|-----------|---------------------------|---------------------------|---------------------------|
| 5000 | 5.111e-06 | 2.129e-05 | 5.170e-06 |
| 6000 | 5.392e-06 | 1.816e-05 | **3.264e-06** |
| 7000 | 4.449e-06 | 2.882e-05 | **3.260e-06** |
| 8000 | 6.266e-06 | 1.306e-05 | **2.565e-06** |

At 20 per surface the straightened case sits **3–6× above** §25 at every matched iteration, which
reads as "straightening costs convergence". It is not: that variant also has **26% fewer cells**.
With the cell count matched the straightened case is level at 5000 and **1.7–2.4× below** at
6000–8000 — so the penalty was the cell count and the straightening is free.

One further thing the middle column makes visible: **the matched case is the only history in this
note that descends monotonically** (5.17 → 3.26 → 3.26 → 2.57), where §17's, §25's and the
21600-cell variant's all oscillate by tens of percent. Four points is not a convergence proof and
this still does not rank meshes — §25c's caveat applies unchanged — but it is the first case here
that does not oscillate. **[I]** on reading anything into that; **[V]** on the four numbers.

The run was executed under the case name `gridpro_ch_straight32`, before the split-32 variant was
promoted to be *the* straight case; its residual file is
`results/solver/gridpro_ch_straight32/work/unicones.enorm.cli`.

### 27e. A defect found while shipping this **[V]**

`gridpro_ch_fig6_s20.dat` (§25, already committed) carried
`OUTPUT_FILENAME results/meshes/gridpro_ch_fig6/mesh.vtk` — §17's directory. The `sed` that was
supposed to re-point it matched a filename that file does not contain, so the replacement silently
did nothing. §25's measurements are unaffected (they are read from the quality line on stdout, not
from the file), but running that case overwrote §17's mesh. Fixed, §17's output regenerated, and
all nine research `.dat` files audited: each now writes somewhere distinct.

---

## 28. Perpendicular at the body, arcs further out — built

Two observations against the straightened figure: (1) the wake region still is not GridPro's, and
(2) the odd curvature is gone, so the next step toward `fig6` is that **GridPro's lines are
perpendicular NEAR the geometry and then curve into arcs further out**.

(1) is unchanged and §27c holds: inside a C/H the wake is a `cut` by construction, so a
trailing-edge rosette is not a modification of this topology, it is the O-ring topology, which
measures 37.7° median turning against 6.9°. Nothing in this section touches it. **§29 does, and
the comparison in that sentence does not survive it** — the matched member measures 8.88.

(2) is built: `gridpro_ch_arcout.{json,dat}`, figure `arc_outward.png`, measurement script
`measure_turning_profile.py`.

### 28a. The profile, which is what the observation is about **[V]**

Total turning (§27) cannot see this; WHERE along the line it happens can. Splitting each
wall-normal line's turning into four quarters of its own arc length, medians in degrees:

| | wall→25% | 25–50% | 50–75% | 75%→outer |
|---|----------|--------|--------|-----------|
| §27, 2 layers | 0.34 | **0.00** | **0.00** | 0.01 |
| §25, 3 layers | 6.65 | 0.01 | 0.00 | 0.02 |
| this repo's shipped C-grid | 1.79 | 0.01 | 0.01 | 0.01 |

**Every mesh in this note turns only against the wall and then runs dead straight** — the opposite
of the reading. The cause is one line of the generator: `curve=cv if k == 0 else None`. Only the
innermost layer's radial was declared as an arc; every layer outside it was a straight chord.

### 28b. Two mechanisms that did NOT work **[V]**

1. **The smoother.** `MB_SMOOTH_ITERS` 0 / 5 / 20 moves the first quarter 0.00 → 0.34 → 1.26 and
   leaves the other three at zero; **60 folds the mesh** (1000 inverted cells, cell-shape max
   12462) and 150 still folds 52. It adds turning against the wall, never outward. This is
   `arc_tangent_at`'s own docstring restated by measurement — "the smoother diverges long before
   it curves anything" — and §10 had already found it from another direction.
2. **C1-continuing the inner arc outward.** Implemented first, and **inert**: byte-identical
   output and an unchanged profile. Layer 0's arc over a 0.05-chord wall band is within 1e-4 of
   its own chord, so continuing its tangent asks `arc_tangent_at` for a radius it correctly
   rejects as indistinguishable from a straight line. Faithful, and useless.

### 28c. The mechanism that worked, and the one failure that located it **[V]**

Declare the OUTER radial as an arc arriving perpendicular to the far field. First version aimed at
**the rectangle's own normal** and folded: 112 inverted at full strength, and still **16 inverted
at a blend of only 0.15**. Localised: exactly two mirrored blocks at x = −0.27, |y| = 0.47 — the
nose. A rectangle has CORNERS, so "perpendicular to the far field" is discontinuous across them;
two neighbouring radials off the nose land one on the inlet and one on the top, take target
tangents 90° apart, and their arcs bend opposite ways and cross.

Aiming instead **radially outward from a centre near the body** (0.25, 0) varies smoothly
everywhere — which is what perpendicular-to-a-circle would give, and a circle is the far field
GridPro's own tutorial text states (§3a). That meshes at every blend:

| blend | inverted | non-ortho max | non-ortho mean | wall→25% / 25–50% / 50–75% / 75%→outer |
|-------|----------|---------------|----------------|----------------------------------------|
| 0 (§27) | 0 | **50.062** | **1.840** | 0.34 / 0.00 / 0.00 / 0.01 |
| 0.25 | 0 | 52.233 | 2.352 | 1.14 / 0.37 / 0.25 / 0.29 |
| **0.5 (shipped)** | **0** | 51.655 | 2.980 | **2.22 / 0.74 / 0.50 / 0.59** |
| 0.75 | 0 | 51.077 | 3.685 | 3.31 / 1.11 / 0.74 / 0.87 |
| 1.0 | 0 | 57.925 | 4.388 | 4.41 / 1.49 / 1.00 / 1.12 |

The turning now continues outward instead of stopping at the wall, which is the shape asked for.
**It costs non-orthogonality mean, 1.840° → 2.980° at the shipped blend**, roughly linearly in the
blend. §27's case is kept beside it unchanged, because that is a choice and not an improvement.

### 28d. GATE 2: the curvature costs nothing in the solve **[V]**

Exit 0, zero NaN, and against §27's case at matched cell count (both 28640):

| iteration | §27, straight | §28, arc blend 0.5 |
|-----------|---------------|--------------------|
| 5000 | 5.170e-06 | 5.734e-06 |
| 6000 | 3.264e-06 | 3.716e-06 |
| 7000 | 3.260e-06 | **3.060e-06** |
| 8000 | 2.565e-06 | **2.473e-06** |

Within 11% at every point, crossing over twice, and **both descend monotonically** — the only two
histories in this note that do. So the 1.840° → 2.980° the curvature costs in non-orthogonality
mean **does not show up in the solve at all** at this cell count. §25c's caveat still applies and
neither is converged; what this supports is the narrow claim that the change is not paid for
here. **[V]**

### 28e. IS THE BLEND THE SAME AS GRIDPRO'S? No — and no vendor image can tell **[V]**

The blend was picked because the arcs are visible in MY rendering. Asked whether it matches
GridPro's, the answer is measurable, and it is no.

Each line's **sagitta** — its greatest departure from the straight chord — converted to pixels at
each vendor image's own scale:

| | full line | inside `fig6`'s window, at 999 px/chord | whole line, at `fig5`'s 86 px/chord |
|---|-----------|----------------------------------------|--------------------------------------|
| blend 0 (straight) | 0.0002 chord | **0.03 px** median | 0.02 px |
| blend 0.5 (shipped) | 0.0178 chord | **0.86 px** median, 2.30 p95 | 1.5 px median, 6.4 p95 |
| blend 1.0 | 0.0355 chord | 1.74 px median | 3.1 px median, 12.8 p95 |

**Neither figure can resolve the difference.** `fig6` has the resolution — 999 px per chord — but
its panel spans only 1.26 chords (§24b), so it contains about 12% of each line's length and the
straight and blended cases differ there by **0.83 px at the median**, under one pixel on a
compressed image whose grid lines are about 2 px wide. `fig5` contains the whole line but at 86 px
per chord, where blend 0.5 is 1.5 px at the median — and `fig5` is the three-element configuration
(§24a), a different geometry.

So: **the shape of the change is right and its magnitude is unfalsifiable from these sources.** Any
blend between 0 and 1 would look identical in the only windows GridPro published. The value 0.5 is
a choice, and it is recorded as a choice rather than as a match. The one thing measurement does
settle is the direction: at blend 0 the turning stops at the wall (§28a), and GridPro's does not —
that reading survives even though the amount cannot be checked. **[V]** on every number here;
**[I]** on the reading of `fig6` that the direction rests on.

This also means §27's case, not this one, is the defensible default: it has the better
non-orthogonality (1.840° against 2.980°) and the difference this case buys cannot be seen in any
source. Both ship; neither supersedes the other.

### 28f. The appearance agrees; the provenance does not **[I]**

GridPro's arcs are what a converged elliptic solve leaves over straight wireframe links (§1a).
Here the arc is **declared** — a circular arc through two fixed corners with a prescribed tangent
at one end. The shape matches what `fig6` shows; the mechanism does not, and §28b measures why the
matching mechanism is unavailable rather than asserting it. A reader taking this case as evidence
that the two tools do the same thing would be wrong in a way this note can now name.

One further limit worth stating: `arc_outward.png` is drawn at x ∈ [−1.6, 3.4], y ∈ [±1.6]
because that is where the arcs live, and **`fig6`'s own panel is 1.26 chords wide** (§24b) — so the
figure that prompted this cannot show the region the change acts on. The appearance claim rests on
reading `fig6`'s near-body quarter and extrapolating. **[I]**

---

---

## 29. The topology route, REOPENED — the number that closed it does not survive

§27c closed the radial-fan route with one comparison: "the O-ring measures 37.7° median turning
against the C/H's 6.9". Both halves of that are wrong — the member, and the ruler — and with the
route reopened the fan turns out to **beat** the C/H in the solve at matched cell count. This
section is that, built and measured.

Everything here is measured on QUADS (`MB_SPLIT_QUADS 0`). That matters and §29a says why — and
**every `.dat` this section ships carries `MB_SPLIT_QUADS 1`**, because that is what the solver
needs and gate 2 is run on the same files. So `./run.sh -conf gridpro_quilt.dat` as written
reproduces the cell counts and the non-orthogonality but NOT one turning or sector figure here;
flip that key to 0 first, which is the same instruction `gridpro_rings.dat`'s own header has
carried since §9. Stated once, for all six.

### 29a. The closure compared the family's WORST member, on a ruler §28 argues the other way **[V]**

**First, the member.** `gridpro_rings` is one of three O-ring cases this note already ships, and
it is the worst of them. Total wall-normal turning, the corrected walk of §27a:

| case | median | p95 | max | wall→25% / 25-50% / 50-75% / 75%→outer |
|------|--------|-----|-----|----------------------------------------|
| `gridpro_rings` — **the 37.7 quoted in §27c** | **37.74** | 67.23 | 84.05 | 7.99 / 9.22 / 10.74 / 8.90 |
| `gridpro_rings_even` (§20b's equal-angle sectors) | 17.81 | 37.19 | 49.30 | 3.91 / 4.53 / 5.36 / 4.45 |
| `gridpro_tworing` (§8's 14-block case) | **8.88** | 27.09 | 28.12 | 8.64 / 0.04 / 0.01 / 0.08 |
| §25's C/H, 3 layers — **the 6.9 quoted in §27c** | 6.92 | 34.21 | 82.18 | 6.65 / 0.01 / 0.00 / 0.02 |
| §27's C/H, 2 layers | 0.36 | 4.91 | 10.86 | 0.34 / 0.00 / 0.00 / 0.01 |

The honest matched comparison is **8.88 against 6.92**, not 37.74 against 6.92. `gridpro_tworing`
is a radial fan to a circle whose turning is within 28% of the C/H that §27c held it against, and
its PROFILE is the C/H's shape exactly — everything at the wall, nothing outward.

**Second, the ruler.** §28 spent a whole section ADDING outward turning to the C/H, on the reading
that GridPro's lines curve out where ours run dead straight, and paid 1.840° → 2.980° of
non-orthogonality mean for it — moving the outer quarter from 0.01 to 0.59. The radial fan has
7.5× that for free: `gridpro_rings_even`'s outer quarter is 4.45. **Total turning counts §28's
deliverable as a defect.** It is the right ruler for "does this line follow anything" and the wrong
one for "is this the shape GridPro's figures show", and §27c used it for the second question.

**Why the figures must be quads.** The published 6.9 / 34.2 / 82.2 reproduces **exactly** —
6.92 / 34.21 / 82.18 — from `make_ch.py --layers 3 --split 20 --turn-blend 0.8` exported as quads.
Measured on the committed triangulated `.vtk` of the same case the median and max are unchanged and
the p95 reads **39.13**, because a split quad's diagonal is a turn the walk counts. Nothing in §27
is stale; the first attempt at this section said it was, off the triangulated export, which is
[[read-the-wrong-artefact-in-the-chain]] for the second time in this chain.

### 29b. THE QUILT, built — and the sector count has a measured ceiling **[V]**

`gridpro_quilt.{json,dat}`: two concentric rings × **24 even sectors**, 54 blocks, from
`make_rings.py --rings 2 --split 12 --even-sectors --prop-nodes body --per-layer 20`.
`gridpro_quilt_control.{json,dat}` is §27's C/H at `--split 12`, which is what puts the two at
8664 and 8640 cells — a 0.3% match, and §27f is why a gate-2 comparison needs one.

| | quilt (radial fan) | control (C/H) |
|---|--------------------|---------------|
| blocks | **54** | 80 |
| cells (quads) | 8664 | 8640 |
| inverted | **0** | **0** |
| non-orthogonality max | **47.030** | 48.855 |
| non-orthogonality mean | 6.259 | **2.284** |
| worst cell shape | **43.0** | 282.4 |
| turning median | 18.84 | **1.76** |

The fan's **worst corner is better** and its worst cell shape is 6.6× milder; its mean
non-orthogonality is 2.7× worse. Both pass gate 1.

**The ceiling on even sectors is 12 per surface, measured, not chosen.** At `--split 16` the worst
corner goes 47.550 → **66.326** and the worst cell shape 43.0 → **184.1**; at 20 the generator
refuses by name — *"equal-angle station 19 of 20 on one surface falls outside the angular span its
own end corners reach (125.12 deg)"*. And **more rings is strongly worse**, which is §27a's own
finding reaching this family: at `--split 8 --even-sectors` the median turning runs 17.81 (2 rings)
→ 29.98 (3) → 56.65 (4) with p95 37.19 → 137.91 → 223.36 and the mean non-orthogonality 5.958 →
9.254 → 9.964. **§29f WITHDRAWS that as a general claim**: it holds at `--split 8` with the default
arc radials and not at `--split 12` with `--linear-rings`, where three rings reach 46.346 / 7.369 at the
two-ring quilt's own 8664 cells — better on the worst corner than its 47.030 — and three is an
optimum rather than a ceiling. (The 45.703 / 7.328 in 29f's flag table is the same case at the
generator's default 9488 cells, and quoting THAT against 47.030 is the cross-count comparison
§27f forbids.) `--linear-rings` is **inert at two rings** — identical to six decimals — because it
only governs rings 2..N-1 and there are none.

### 29c. THE BIG WEDGES ARE ALL DOWNSTREAM, and lifting §9d's cap breaks the mesh **[V]**

`measure_block_partition.py --gaps` is new here and is the complaint measured: the angular widths
of the sectors a circle is cut into. N(r) cannot see this — 24 even sectors and 4 wedges plus 20
slivers give the same count — and max/min is the figure, 1 being a perfect quilt.

| max/min **about (1, 0)**, the far-field circle's own centre | r = 1.5 | r = 2 | r = 2.5 |
|---|---------|-------|---------|
| quilt | **22.78** | **12.30** | **14.27** |
| control | 41.47 | 36.15 | 30.67 |

So the fan is 1.8–2.9× more uniform, and still far from 1. Walking the 28 crossings at r = 2 says
exactly where the residue is: the body's 24 even sectors cover **71.2° to 288.8°**, and the whole
remaining **142.4° downstream is carried by four sectors** of 34.4 / 36.8 / 36.8 / 34.4. The wedges
are not a distribution defect; they are the trailing-edge ray fan, and `--te-rays` is capped at 3.

**§9d names the escape and this section builds it.** That section proved equal bisection of a 343°
exterior angle caps the fan at three — the 5th ray lands at ±114°, back over the body — and listed
three things a figure showing more links could be, one of them *"rays placed unequally"*. `--te-fan`
is that: the rays stay evenly spaced among themselves but span a narrower cone about the bisector,
so the exterior angle is divided UNEQUALLY. It is not GridPro's rule and does not claim to be.

| rays / fan | inverted | non-ortho max | mean | worst shape | widest sector | max/min |
|------------|----------|---------------|------|-------------|---------------|---------|
| 3 / equal bisection | **0** | 47.030 | 6.259 | 43.0 | 36.77° | 9.68 |
| 3 / 120° | **0** | 58.474 | 8.132 | 70.7 | 26.18° | **3.32** |
| 5 / 120° | **898** | 89.986 | 16.017 | 3693 | 17.01° | 2.25 |
| 7 / 120° or wider | — | the generator refuses: *the radials CROSS between ring 1 and the far circle* | | | | |

The uniformity arrives and the mesh goes with it. At five rays the widest sector is 17.0°, within
2° of the 15° a 24-sector quilt wants, and 898 of 13272 cells are inverted; `--blend` 0.00/0.25
improve the uniformity further (1.86, 1.95) and make the inversions worse (986, 962), and 0.75/1.00
are refused. **The wake quadrant's coarseness is structural to this ring construction**: a narrow
fan puts consecutive rays close together at the trailing edge while their ring-1 landings and
far-field corners stay spread, and the tail block between each pair degenerates.

So the one usable improvement is `--te-rays 3 --te-fan 120`, which trades 11.4° off the widest
wedge for 1.9° of worst corner and 1.9° of mean. It is NOT shipped as the quilt: §29d's gate-2
result is measured on the equal-bisection case, and a knob that costs the mean is a choice.

The figure is `docs/research/gridpro-blocking-method/quilt_vs_control.png` (regenerate:
`python3 docs/research/gridpro-blocking-method/plot_quilt_vs_control.py "<label>=<quilt quads>"
"<label>=<control quads>" <out.png>`; the label is required and the block and cell counts are
appended from the mesh). Both panels of each case fill the blocks by colour and draw the partition
heavy over a greyed grid, because the complaint is about the PARTITION — drawing the grid alone is
how that question got dropped once already (§24).

**And beside GridPro's own ring fan, at a matched frame:**
`docs/research/gridpro-blocking-method/quilt_vs_gridpro.png` (regenerate:
`plot_quilt_vs_gridpro.py --topo <that case's .json> <img12.webp> <quilt quads> <out.png>`; the
vendor image is not committed, and `--topo` is what makes the caption's ring and sector counts
derived rather than absent). The panel is the MIDDLE one of `img12.webp` — the only published GridPro figure
showing a single aerofoil inside a radial fan cut into concentric bands, which is what this
section's quilt is. Its separators re-derive by row brightness at y = 350..357 and 706..713,
reproducing the committed reading of 350..359 / 706..717.

- **The frame is matched on a READING, not a measurement.** Segmenting the body automatically
  fails on this image — heavily compressed, blocks painted over the grid, and three attempts
  returned runs that are plainly not the body — so the chord was read off a 2× crop at
  **140 ± 15 px of the panel's 700**, making the panel **5.0 ± 0.5 chords** wide. §20b's
  "an automated count bounced between 7 and 21, which is not a measurement" is why this is
  stated as a reading with an error bar rather than dressed up. **[I]** on the number,
  **[V]** on the separators.
- **What the figure shows:** **three to five concentric bands** of roughly **20–24 sectors**
  each, the outermost ending about **1.5 chords** off the body where a coarser outer field
  takes over. The count is a range because a closer look at its upper-left quadrant at 4×
  counts four to five where the first reading of this panel said three, and an automated
  count does not settle it: sampling colour round circles at four radii returned 3, 4, 2 and
  4 changes where the eye sees about twenty, which is §20b's finding reproduced on a second
  figure. **The grid lines are coloured BY BLOCK in this figure** — a block's own grid is
  drawn in its own colour — so a colour boundary is a block boundary, which is what makes
  even the eye count sound. Ours is **two** bands of 24 — and §29b measured the third: median turning
  17.81° → 29.98°, mean non-orthogonality 5.958° → 9.254°. **So the remaining structural gap
  to this figure is one ring, and this repo has measured what that ring costs it** — then
  §29f BUILT it, at the same cell count and gate-1 clean, and the cost turned out to be the
  mean non-orthogonality and nothing in the solve.
- **§11b does NOT cover this panel.** That correction — "the outer colour bands are azimuthally
  adjacent and each spans the whole radial extent, there is no concentric seam out there at
  all" — was read off `fig5`, the MDA-3 three-element figure. `img12`'s middle panel is a
  different figure of a different configuration and it plainly does band concentrically. The
  two are not in conflict and neither generalises to the other.
- **The nose panel is NOT matched** and is labelled so in the figure: the body leaves that
  panel diagonally, so no chord can be fixed on it.

### 29d. GATE 2: the fan WINS at matched cell count **[V]**

Both pass — exit 0, zero NaN, 9000 half-iterations. Worst-of-row from `unicones.enorm.cli`:

| iteration | quilt, 8664 cells | control, 8640 cells |
|-----------|-------------------|---------------------|
| 3000 | 9.238e-06 | 2.431e-05 |
| 4000 | **5.702e-06** | 2.798e-05 |
| 5000 | **4.578e-06** | 1.399e-05 |
| 6000 | **3.952e-06** | 1.477e-05 |
| 7000 | **3.356e-06** | 9.537e-06 |
| 8000 | **2.787e-06** | 8.326e-06 |

**2.6–4.9× below the control at every matched iteration**, and the quilt descends monotonically
across all six points where the control rises twice. The fan's mean non-orthogonality is 2.7× the
control's and its turning 10.7×, and neither shows up here except in the fan's favour.

§25c's caveat applies unchanged: six points is not convergence and this does not rank meshes. What
it does establish is the narrow claim §27c needed and never had — **that the radial fan is not
paid for in the solve** — and it is the opposite of what the closure assumed.

### 29f. THE THIRD RING, added — and EVERY angle ruler ranks the winner last **[V]**

§29b said "more rings is strongly worse" and §29d's figure said the remaining structural gap to
GridPro's own ring fan is one ring. Both are now measured properly, and the third ring is
affordable: `gridpro_quilt3.{json,dat}` and `gridpro_quilt3_arc.{json,dat}`, **3 rings × 24 even
sectors, 82 blocks**, at **exactly 8664 cells** — the two-ring quilt's own count, so all four
meshes this section compares differ by 0.3% and §27f's lesson is satisfied without approximation.

**§29b's claim was measured at `--split 8` with the DEFAULT arc radials, and does not generalise.**
At `--split 12` the knobs that make a third ring work are `--linear-rings` and the radial
construction, and 29f has the control that separates them:

**These four rows are at the generator's DEFAULT `--per-layer`, which is 9488 cells, not the 8664
the rest of this section compares at.** They are a comparison of four FLAG SETS against each other
and are sound as that; the figure to carry into any comparison with the two-ring quilt is the
matched one below, **46.346 at 8664**. §29b quotes 45.703 against the two-ring 47.030 and those are
9488 against 8664 — the cross-cell-count comparison §27f exists to forbid, committed here by the
same section that states the rule.

| three rings, `--split 12 --even-sectors`, 9488 cells | inverted | non-ortho max | mean | turning median |
|---|----------|---------------|------|----------------|
| plain (arcs, geometric rings) | 0 | 54.339 | 9.205 | 31.37 |
| `--linear-rings` | 0 | 49.442 | 7.699 | 26.52 |
| `--chord-radials` alone | 0 | 56.385 | 8.203 | 22.45 |
| `--linear-rings --chord-radials` | 0 | **45.703** | 7.328 | **21.62** |

**Both flags are needed**, and **three is an optimum rather than a ceiling**: four rings gives
49.146 / 7.486 and five 50.807 / 7.450, worse than three on every figure but the mean. GridPro's
own figure reads as three (§29d).

**The control that matters: `--chord-radials` is NOT what the third ring buys.** On two rings it
moves the turning median 18.84 → 10.03 and the p95 40.23 → 25.50 all by itself, leaving the worst
corner unchanged at 47.030. So it is a general improvement on that ruler and its effect has to be
held fixed before the third ring can be priced at all.

#### The four meshes, all at 8664 cells (the C/H at 8640) and all gate-1 clean

| | 2-ring quilt | 3-ring, chords | 3-ring, ARCS | §27's C/H |
|---|--------------|----------------|--------------|-----------|
| blocks | 54 | 82 | 82 | 80 |
| non-ortho max | 47.030 | **46.346** | 49.491 | 48.855 |
| non-ortho mean | 6.259 | 7.369 | 7.702 | **2.284** |
| turning median | 18.84 | 21.33 | 26.38 | **1.76** |
| turning, by quarter | 3.4/5.7/4.8/4.8 | 9.1/0.2/13.6/0.0 | 4.8/6.7/10.2/9.0 | 1.4/0.0/0.0/0.0 |
| sector width max/min **about (0.5, 0)**, r = 1.5 / 2 / 2.5 | 7.58 / 9.68 / 11.45 | **3.54** / 4.53 / 7.65 | 4.97 / **4.54** / **4.61** | 31.26 / 45.71 / 39.06 |

**The third ring delivers what §29c could not — and this row's CENTRE is not 29c's, which the
first draft of it did not say.** 29c measures about **(1, 0)**, the far-field circle's own centre;
this row measures about **(0.5, 0)**, the generator's default and the wrap ellipse's centre. Both
are stated now, and the comparison holds either way but by different factors:

| arc 3-ring against | about (0.5, 0) | about (1, 0) |
|---|----------------|--------------|
| the two-ring quilt | 1.52× / 2.13× / 2.48× more uniform | 1.16× / 1.24× / 2.11× |
| the C/H control | 6.29× / 10.07× / 8.47× | 2.11× / 3.65× / 4.54× |

So the honest statement is **1.5–2.5× more uniform than the two-ring quilt and 6.3–10.1× more
uniform than the C/H about (0.5, 0)**, and 1.2–2.1× / 2.1–4.5× about (1, 0) — not the "1.5–2.1×"
and "7–9×" this paragraph first claimed, neither of which is either column. The arc variant is
also the only mesh here whose uniformity does not DECAY outward — 4.97 / 4.54 / 4.61 against the
chord variant's 3.54 / 4.53 / 7.65. That is the "quilt" the complaint asked for, measured.

**And the two radial constructions are a real trade, visible in the profile.** Chord radials put
all the turning at the wall and at the ring-2 crossing and run dead straight in between
(9.1 / 0.2 / 13.6 / 0.0); the arcs spread it over the whole line (4.8 / 6.7 / 10.2 / 9.0), which is
the shape §28 read off GridPro's figures and spent a whole section ADDING to the C/H at a cost of
1.840° → 2.980° in mean non-orthogonality.

The figures are `quilt3_vs_gridpro.png` (the three-ring quilt beside GridPro's own panel, the
same matched frame as 29d) and `quilt3_vs_control.png` (beside the C/H). Both are regenerated by
the scripts named in 29d, and **every count in their captions is derived** — the block and cell
counts from the mesh's own block field, the ring and sector counts from the topology document's
header via `--topo`. The first cut of both scripts wrote those counts in as literals and then
drew a different mesh under them unchanged, which is this repo's commonest figure defect reached
once more.

#### GATE 2: the mesh every angle ruler ranked LAST wins **[V]**

All four pass — exit 0, zero NaN, 9000 half-iterations, same operating point.

| iteration | 3-ring, chords | **3-ring, ARCS** | 2-ring quilt | §27's C/H |
|-----------|----------------|------------------|--------------|-----------|
| 3000 | 1.162e-05 | 1.329e-05 | **9.238e-06** | 2.431e-05 |
| 4000 | 5.916e-06 | **4.899e-06** | 5.702e-06 | 2.798e-05 |
| 5000 | 4.600e-06 | **3.381e-06** | 4.578e-06 | 1.399e-05 |
| 6000 | 4.151e-06 | **2.786e-06** | 3.952e-06 | 1.477e-05 |
| 7000 | 3.618e-06 | **2.078e-06** | 3.356e-06 | 9.537e-06 |
| 8000 | 3.026e-06 | **1.463e-06** | 2.787e-06 | 8.326e-06 |

The arc variant is the WORST of the three quilts on non-orthogonality max, on non-orthogonality
mean and on every turning figure — and from 4000 on it is the best in the solve, by a margin that
widens monotonically to **1.9× below the two-ring quilt, 2.1× below the chord three-ring and 5.7×
below the C/H** at 8000. **Three rulers, all pointing the wrong way, on four meshes that differ by
0.3% in cell count.** §29a argued that from one direction — total turning scores §28's own
deliverable as a defect — and this is the same finding reached against our own primary quality
metric.

**Where this is weakest, stated:** at 3000 the arc variant is the WORST of the four, so the
ordering depends on where the history is read, and §25c's caveat is unchanged — six points is not
convergence and nothing here ranks meshes for accuracy. What it does support is narrow and now
twice-measured: **the angle metrics this repo reports do not predict which of these meshes the
solver prefers.**

**The three-ring ARC quilt is what 29f recommends** of the four, and it is also the more canonical
construction — §10 chose curved block boundaries for this family and `--chord-radials` is the
deviation introduced here. The chord variant ships beside it because it is what the angle metrics
pick, and keeping both is what makes the disagreement checkable.

### 29g. THE DIFFERENCES FROM GRIDPRO, enumerated — seven, and which can be closed **[V]** on ours, **[I]** on theirs

Read off `quilt3_vs_gridpro.png`: `gridpro_quilt3_arc` against the middle panel of `img12.webp`
at a matched frame. **Every count on the vendor side is an EYE reading** — sampling colour round
circles at four radii returned 3, 4, 2 and 4 changes where the eye sees about twenty, which is
§20b's finding reproduced on a second figure. What makes the eye reading sound is that **this
figure colours each block's GRID LINES in that block's own colour**, so a colour boundary is a
block boundary and not a shading choice.

| # | the difference | theirs | ours | status |
|---|----------------|--------|------|--------|
| 1 | **Far-field cell size** | texture is near-uniform from the body to the panel edge | a 4.2× RADIAL STEP at ring 1, then flat; and a 184× spread of one `DS_SURF` across the outer boundary | §29h closes the step 2.9× (`--match-ring1`); §29i closes the boundary and moves the worst pair OFF it (`--far-uniform`) |
| 2 | **Fan → Cartesian transition** | some outer blocks carry an AXIS-ALIGNED grid while their neighbours carry a radial one | fan all the way to the circle, no transition | §29h REFUSED it by measurement, confirming §12b: a FORK, not a defect |
| 3 | **Concentric bands** | three to five | three | §29f priced four and five as WORSE |
| 4 | **The nose** | a dense rosette of small blocks wrapping the leading edge | 24 sectors converging on one point, no local clustering | §17d: stations by COUNT, not clustering |
| 5 | **Downstream** | a thin banded wake strip with the fan cut around it | four wedges of ~30–36° carrying the whole quadrant | §29c measured the ceiling |
| 6 | **Where the curves come from** | a converged elliptic solve: smooth at BOTH ends of every edge, consistent across every block at once | one tangency condition at one end, Coons fill for the rest | §10b/§10f — the one no re-blocking closes |
| 7 | **Extent** | unknown: this panel does NOT reach a boundary, as §18d measured for `fig6` | far-field circle r = 3 about (1,0) — GridPro's own stated one (§3a) | unknowable from these sources |

**One reading was left UNRESOLVED and deliberately not in the table** — whether their radial
boundaries CONTINUE through the bands or stagger between them — and **§29j settles it for the
inner 0.4 chord of `img11_1`'s topology wireframe: N(r) runs 39 / 40 / 40 / 42 / 54 / 50, flat then
rising, so they PROPAGATE and nothing terminates there.** Past 0.4 chord that figure's own crop
cannot answer. On img12 it stays open and §29j measures why: the colour method's control, a
partition whose radials are declared continuous, scores 55–68% where GridPro's scores 22–56%, so
that method cannot distinguish anything at 140 px per chord.

**Triage, and what §29h did with it.** 1 is **closed** — and its first diagnosis in this very
section was wrong, which 29h records. 2 is **refused by measurement**, twice now, and is a fork
rather than a defect. 3 was **priced** in §29f and four and five rings are worse. 5 has its
**ceiling measured** in §29c. 4 is **not attempted**, because closing it means reversing §20b's
equal-angle choice or adding a local refinement this generator does not have. 6 and 7 cannot be
closed at all.

### 29h. ATTACKING THE LIST — one closed, one refused by measurement, and TWO instruments that said the fix had failed **[V]**

29g's triage named 1, 2, 4 and 5 as the movable ones. This is what moving them produced.

#### Difference 2 — the fan-to-Cartesian transition: REFUSED, confirming §12b

`--box` replaces the tutorial circle with a rectangle and morphs the rings out to it. On the quilt,
at the same 8664 cells and 0 inverted throughout:

| | non-ortho max | mean | adjacent area max | turning median | sector max/min |
|---|---------------|------|-------------------|----------------|----------------|
| arc, circle (§29f) | **49.491** | **7.702** | **18.30** | 26.38 | **4.54** |
| arc, `--box` | 81.203 | 13.195 | 25.38 | 59.30 | 9.05 |
| arc, `--box`, 2 rings | 70.690 | 13.992 | 30.94 | 32.14 | 7.59 |
| chord, `--box` | 64.973 | 12.769 | 25.67 | **26.11** | 5.59 |

Worse on every figure but one. §12b reached the same verdict from the other direction — "the
downstream half does become a streamwise band, the rest does not" — so this is a second,
independent refusal of the same mechanism. **Difference 2 is a FORK, not a defect**: the
arrangement GridPro's figure shows needs the C/H family, which §27 ships and which §29d's gate 2
beats at matched cell count.

#### Difference 1 — the coarsening: the first DIAGNOSIS was wrong, and then the fix worked

**Wrong first:** this section's own first reading said the coarsening is azimuthal and the radial
direction is already handled by `--linear-rings`. Measuring cell extent by radius about the
trailing edge says otherwise — the radial extent STEPS 4.2× at r ≈ 1 (0.0220 → 0.0931) and is
then flat (0.093 / 0.131 / 0.132 / 0.128), while the azimuthal extent grows gently, 0.027 → 0.073
over r 1→3, which is the 2.7× a fixed angular count gives by construction. **The dominant term is
a single step at ring 1's crossing**, not a gradual stretch.

**The cause is the wall law.** `wall_ends: start` is one-sided: it pins the first cell to
`BL_INITIAL_THICKNESS` and spends the tanh law filling the band, so the band's LAST cell is far
finer than the first cell outside ring 1. `--match-ring1` makes it two-sided, giving `ds_end` the
first cell the outer region has at that same station, per-station because the band's thickness is,
and backed off to the law's own feasibility bound `(L/ds_start - 1)(L/ds_end - 1) >= (count - 2)^2`
rather than handed over to be warned about and silently pinned.

**It works, measured on the pairs ON ring 1** — 134 of them, found by testing both endpoints
against the wrap ellipse:

| across ring 1 | median | p95 | max |
|---|--------|-----|-----|
| without `--match-ring1` | 7.88 | 10.14 | 12.86 |
| with | **2.78** | **3.88** | **4.47** |

**AND TWO INSTRUMENTS SAID IT HAD FAILED.** Both were wrong in a way worth naming:

1. **`adjacent_area_ratio_max` did not move, to six figures — 18.297 both ways.** Not because
   nothing changed: its worst pair is at the FAR-FIELD boundary, r = 2.945 at (1.266, ±2.933)
   between blocks 79|80 and 55|56, with a second cluster at the trailing-edge fan (r = 0.25–0.38,
   ratios 12.9 and 12.7). **A mesh-wide max names no location**, which is the lesson §16e of the
   sibling note recorded under another name and this is its second instance. **§29i then went and
   fixed that pair**, so the number this paragraph says did not move does move — to 9.87, with the
   worst pair no longer on the far field at all.
2. **A band-median radial extent said the step got WORSE, 4.23× → 4.50×.** `ds_end` sets the LAST
   cell of the band; a median over a band cannot see an end cell. The instrument could not measure
   the thing the flag changes, and it did not return "no change" — it returned the opposite sign.

Before reading either null result as a null result, the document was checked for the change:
**25 wall edges carry a `ds_end` of 0.040–0.051**, so the flag had reached the mesh and the
question was the instrument, not the mechanism.

The figure is `ring1_grading.png` (regenerate: `plot_ring1_grading.py <without quads> <with
quads> <out.png>`). It draws the GRID, not the partition — the two meshes have the SAME partition
and a block figure shows nothing — zoomed onto a stretch of ring 1, because what changes is the
last row of cells inside it and at body scale that is one thin line. Its ratios are derived by the
same ellipse selection the table above uses.

**GATE 2 prices it at about 9%.** Exit 0, zero NaN, 9000 half-iterations, 8664 cells:

| iteration | graded | arc (§29f) | chord | 2-ring |
|-----------|--------|------------|-------|--------|
| 3000 | 2.053e-05 | 1.329e-05 | 1.162e-05 | **9.238e-06** |
| 5000 | 4.400e-06 | **3.381e-06** | 4.600e-06 | 4.578e-06 |
| 8000 | 1.589e-06 | **1.463e-06** | 3.026e-06 | 2.787e-06 |

So grading across ring 1 costs **8.6% of the residual at 8000** and 6.7% of the mean
non-orthogonality (7.702 → 8.216), leaves the worst corner and the turning unchanged, and buys a
2.9× flatter size transition at the one seam where the mesh changes character. **It is a trade and
is recorded as one**; `gridpro_quilt3_arc` remains what §29f recommends, and
`gridpro_quilt3_graded` ships beside it because the trade is the finding.

#### Differences 4 and 5 — not attempted here, and why

**5** has its ceiling measured in §29c and nothing new was tried. **4**, the nose rosette, needs
blocks CLUSTERED at the leading edge, and `--even-sectors` — which §20b adopted because it is how
`fig5` arranges its sectors — works directly against that: equal angle puts FEWER stations at the
nose than equal arc length does. So closing 4 means either reversing §20b's choice or a local
refinement this generator does not have, and both are larger than one flag. **Not attempted, and
named rather than left to look unexamined.**

### 29i. DIFFERENCE 1, THE OTHER END — the far-field worst pair, found and fixed **[V]**

29h closed the size step across ring 1 and said in as many words that the mesh-wide
`adjacent_area_ratio_max` did not move because **its worst pair is on the far-field BOUNDARY**, at
r = 2.945. 29h named that and did not touch it. This does.

**What the pair IS.** Not a size step at all. The two cells have near-identical extents —
0.109 × 0.110 and 0.115 × 0.123 — and areas 18.3× apart, because one of them is a **sliver**:
0.0054 × 0.155, aspect 28.8, its four corners at r = 3.000 spanning 274.03° to 276.28° about the
trailing edge. It sits where the trailing-edge ray at −85.866° lands on the circle.

**Its short side is `DS_SURF`.** 0.00538 against the generator's 0.005. The circumferential arcs
carry the body stretch's clustering **scaled by arc length**, so the whole radial family shares one
normalised distribution — derived, not tuned, and the right thing for the family. But scaling
preserves the RELATIVE distribution and destroys the ABSOLUTE one, and on the far field only the
absolute one matters. The outermost ring's four spaced arcs say it outright:

| arc | declared spacing | against the boundary's uniform interval, 0.196 |
|-----|------------------|------------------------------------------------|
| `c3_lo_11`, `c3_up_0` | **0.005378** | **36× finer** — this is the sliver |
| `c3_lo_0`, `c3_up_11` | **0.990347** | **5× coarser** |

One value of `DS_SURF`, 184× apart at the two ends, because the nose stretch is short in body arc
and long in ring arc while the trailing-edge stretch is not.

**`--far-uniform` blends each ring's clustering toward THAT RING's own uniform interval**, by the
ring index: the wrap keeps the body's distribution, the outer boundary is exactly uniform, and the
rings between are graded. One line, and the whole mechanism is `rl / cnt`, the arc's own mean.

| 8664 cells, 0 inverted throughout | non-ortho max | mean | adjacent area max | seam p95 | where the worst pair is |
|---|---------------|------|-------------------|----------|-------------------------|
| §29f, neither flag | 49.491 | **7.702** | 18.30 | 8.08 | r = 2.945, the FAR FIELD |
| `--far-uniform` | 49.491 | 7.683 | 13.42 | 7.96 | r = 0.246, the trailing edge |
| **both flags (shipped)** | 49.491 | 8.198 | **9.87** | **3.51** | r = 0.444, the trailing edge |

**The worst pair MOVES OFF the far field**, which is the result rather than the 46% the number
falls by: what is left is 29h's second cluster, the trailing-edge fan, and the far-field boundary
is no longer the mesh's worst place.

**The residue at the far field is `--prop-nodes`, and it cannot be improved here.** With
`--far-uniform` on, the outer arcs' spacings are 0.0239 and 0.2648 — each that stretch's OWN
uniform interval, so the blend is doing exactly what it says; the remaining 11× spread is the
per-stretch node density `--prop-nodes body` assigns. Swept: `far` is much worse (32.78),
`mean` and no proportioning are identical to `body` at 9.87 because the surviving worst pair is in
the fan, which `--prop-nodes` does not reach. `body` is kept — best mean (8.198 against 8.557 and
10.054) and the only one at the matched 8664 cells.

**The cost is the mean, again.** 7.702 → 8.198, the same 6.5% `--match-ring1` cost on its own,
with `--far-uniform` contributing nothing to it (7.702 → 7.683, slightly better).

The figure is `farfield_sliver.png` (regenerate: `plot_farfield_sliver.py <before quads> <after
quads> <out.png>`). Both panels show **the same place** — the FIRST mesh's worst pair, not each
mesh's own — because 29i's result is that the worst pair MOVES, and recentring the second panel on
its own worst pair somewhere else would hide exactly that. The left panel's grid lines crowd into
the boundary and the sliver is filled red; the right panel's are evenly spaced and its worst pair
is not in frame.

**GATE 2, re-run on the shipped pair.** Exit 0, zero NaN, 9000 half-iterations, 8664 cells:

| iteration | arc, neither flag | `--match-ring1` only | **both (shipped)** | 2-ring quilt |
|-----------|-------------------|----------------------|--------------------|--------------|
| 5000 | **3.381e-06** | 4.400e-06 | 4.699e-06 | 4.578e-06 |
| 7000 | **2.078e-06** | 2.368e-06 | 2.437e-06 | 3.356e-06 |
| 8000 | **1.463e-06** | 1.589e-06 | 1.720e-06 | 2.787e-06 |

**Each fix costs about 8–9% of the residual** and they add: +8.6% for `--match-ring1`, +8.2% more
for `--far-uniform`, 17.6% in all at 8000, and the shipped pair is still 38% BELOW the two-ring
quilt there. So the arc variant with neither flag remains the best mesh in the solve and §29f's
recommendation is unchanged; what 29h and 29i buy is a mesh whose worst local transitions are no
longer at the two places the quality report points to, for a seventh of the residual. **A trade,
twice, and recorded as one both times.**

**29h's ring-1 table is `--match-ring1` ALONE and stays as written; the shipped case now carries
both flags** and its 134 ring-1 pairs measure 2.78 / 3.88 / **4.66** against that table's
2.78 / 3.88 / 4.47 — the median and p95 unmoved, the max 4% higher, which is `--far-uniform`
re-spacing the arcs ring 1 is one of. `ring1_grading.png` is drawn from the shipped mesh, so its
caption carries 4.66 and the table carries 4.47; they measure different flag sets and both say
which.

### 29j. THE UNRESOLVED READING, SETTLED FOR THE INNER 0.4 CHORD — and the first N(r) ever taken off a vendor figure **[V]**

§29g left one reading out of its table: do GridPro's radial block boundaries CONTINUE through the
concentric bands, or stagger between them? Staggering is #192's count-reducing device, and finding
it in the vendor's own figure would be the most important structural item in this whole comparison.
It is now answered where it can be, with the instrument validated first.

#### What made it measurable: the LOSSLESS source, and then a different figure

**The PNG, not the WebP.** Both are served at the same 700×1064, but the WebP is lossy: its middle
panel holds **81,346 distinct colours whose 24 commonest cover 5.6%** of it, against the PNG's
**11,129 whose 24 commonest cover 57.4%**. §29d's automated colour count returned 3, 4, 2 and 4
changes at four radii where the eye sees about twenty — **and that was the SOURCE, not the method**.
`media.gridpro.com` serves `.png` for every figure this note cites; nothing here knew that.

**But the colour method still cannot answer it, and a CONTROL is what establishes that.** Rendering
our own `gridpro_quilt3_arc` the way img12 renders GridPro's — blocks filled, grid lines coloured by
block, 140 px per chord — and running the same circle-walk on it, a partition whose radials are
DECLARED continuous carries only **55–68%** of its own boundaries from one radius to the next, with
run counts of 32–51 where the true sector count is 24. GridPro's figure scores **22–56%**. The
ranges overlap, so the method has no discriminating power at that resolution. A first attempt
blamed the palette — `tab20` repeats every 20 colours, so two adjacent blocks can share one and
DELETE a real boundary — and re-rendering with one distinct colour per block moved the control to
55–68% from 30–76%: tighter, and no higher. **The resolution is the limit, not the palette.**

#### The figure that does answer it: `img11_1`'s first panel

`img11_1.png`'s first panel is a **topology WIREFRAME on black** — the drawing IS the partition,
there is no grid to tell it apart from — and the body spans about **380 px** there against img12's
140, so every figure is **2.7× better resolved per chord**. §2b read this panel off the image in
2026; nothing has measured it until now.

**`measure_vendor_wireframe.py` takes N(r) off it**, which is §15a's own instrument and the vendor
side §15g named as missing — §16j said in as many words that it "takes no count off the vendor
raster". The method walks a circle and keeps the SHORT bright runs: a radial link crosses and
leaves a blob, a concentric link lies along the circle and leaves a long arc, rejected by its own
angular width, which is the raster counterpart of `rings_along`'s perpendicularity test.

**THE INSTRUMENT IS VALIDATED, not assumed.** Our own partition rendered the same way, raster count
against the true count from the mesh:

| r (chord) | 0.14 | 0.18 | 0.24 | 0.29 | 0.34 | 0.39 |
|-----------|------|------|------|------|------|------|
| raster N(r) | 4 | 4 | 6 | 8 | 12 | 14 |
| **true** N(r) from the mesh | **4** | **4** | **6** | **8** | **12** | 16 |

Exact at five of six, within 2 at the sixth. At 380 px per chord the raster method reads a partition
correctly.

#### The answer

| r (chord) | 0.14 | 0.18 | 0.24 | 0.29 | 0.34 | 0.39 |
|-----------|------|------|------|------|------|------|
| **GridPro, N(r)** | **39** | **40** | **40** | **42** | **54** | **50** |

**Flat, then rising 38% — it does not fall.** In the range this crop can measure, GridPro's radial
boundaries PROPAGATE; there is no count reduction. The staggering read by eye off img12's middle
panel is not a termination here, and `img11_1` is a different figure of a different configuration,
so it does not refute that reading either — it answers the question for ITS OWN case.

**Beyond 0.39 chord the crop cannot answer and is not allowed to pretend.** The panel is 354 px
tall about a centre 172 px from its nearest edge, so a circle is fully inside only to 0.45 chord;
past that the tool reports the **fraction in frame** and marks the row not comparable. Its raw
counts there fall — 53, 43, 29 — and every one of those falls is the crop. **That is §18d's
retraction, which read fig6's edge as a boundary, turned into a guard rather than a warning.**

**What would settle the rest:** a source at more pixels per chord, or a wireframe whose frame
reaches past half a chord. Both are a fetch, not a method — the method is now validated and the
tool is committed.

### 29e. What this changes, and what it does not

- **SUPERSEDES §27c's conclusion, not its facts.** The rosette still is not a modification of a
  C/H — inside one the wake is a `cut` by construction — and that remains true. What does not
  survive is "it measures worse on the very thing the rosette was proposed to fix": on the matched
  member that figure is 8.88 against 6.92, and on the ruler it is §28's own deliverable.
- **Does NOT supersede §27's or §28's cases.** Both ship. §27's straightened C/H is still the
  defensible default at its own cell count, and nothing here was run at 28640.
- **Does NOT make the fan the recommendation.** One operating point, six residual points, no force
  compared with anything (#157), and the mean non-orthogonality is genuinely 2.7× worse. What is
  established is that the route is open, which §27c said it was not.
- **The quilt is still not GridPro's far field**, and §29c measures the gap rather than asserting
  it: four wedges of ~36° carry the downstream quadrant, and every mechanism tried for making them
  finer either costs the worst corner or inverts the mesh. §29f's third ring does NOT close that
  one — it makes the sectors uniform at every radius and leaves the four downstream wedges where
  they are.
- **§29f's recommendation rests on six residual points and inverts three rulers.** That the arc
  variant starts WORST at 3000 and ends best is stated there and is the weakest part of it; a
  longer run was not done, and no force was compared with anything (#157).
- **The ring sweep stopped at five.** Four and five were measured worse than three at
  `--split 12`; nothing says the trend is monotone beyond that, and nobody looked.
- **The sector-width ruler is new and ungated**, like everything else in this note.
- **The vendor comparison's scale is a reading with a ±10% error bar**, and every count in it
  is by eye. At 5.0 ± 0.5 chords the frames agree to within half a chord, which is enough to
  compare the SHAPE of a partition and not enough to compare a density — the same limit §28e
  established for the sagitta, reached here from the other side.
- **`--te-fan` has no case shipped using it**, which is deliberate: 29c's table is its whole
  justification and the only setting that passes gate 1 is 3 rays, where the fan is a trade rather
  than a win.
- **Four generators recorded only a chosen pair of their flags** — `make_rings.py` wrote
  `--split` and `--rings` out of nine, `make_ch.py` `--split` and `--wake` out of nine,
  `make_tworing.py` and `make_topology.py` `--split` alone. #192 fixed this for the generators it
  created and the fix did not reach these. All four now write the full argv, verified byte-inert on
  `gridpro_rings_even.json`. **The twelve documents committed before the fix still carry partial
  headers** and regenerating them is not done here.


## Sources

Direct fetches (`curl`, article text and `<img alt>` extracted from the page HTML):

- Krishnamurthy, R., *The Art and Science of Meshing Airfoil*, GridPro blog, 6 November 2017 —
  https://gridpro.com/blog/the-art-and-science-of-meshing-airfoil/
- Krishnamurthy, R., *Is Grid Generation an Art or Science?*, GridPro blog, 17 September 2017 —
  https://gridpro.com/blog/grid-generation-an-art-or-science/
- Figure images, read visually (not committed to this repo — the composite figures in
  `docs/research/gridpro-blocking-method/` quote crops of them, and `plot_vs_fig5.py`
  takes the source path as an argument): `media.gridpro.com/wp-content/uploads/2017/11/f12.webp`,
  `.../2017/10/img10.webp`, `.../2017/10/img12.webp`, `.../2017/11/img11_1.webp`,
  `.../2017/10/img6.webp`.
  **EVERY ONE IS ALSO SERVED AS `.png`, LOSSLESS, at the same pixel size** — swap the extension.
  §29j measured what that is worth: img12's middle panel as WebP holds 81,346 distinct colours
  whose 24 commonest cover 5.6% of it, and as PNG 11,129 whose 24 commonest cover 57.4%. Any
  measurement that reads these figures by COLOUR must use the PNG; §29d's automated count was run
  on the WebP and its failure was the source, not the method. Measurements that read LUMINANCE
  only — the panel separators, the sagitta, the grid-line saturation line — are unaffected and
  their published figures stand.

Internet Archive (the live paths now redirect to `gridpro.com/signin`):

- *GridPro GUI Manual*, Version 1.0, Program Development Corporation, 24 September 2014,
  184 pp. — capture `20150505181147` of `http://sp.gridpro.com/docs/WS_GUI_Manual.pdf`.
- GridPro, *Frequently Asked Questions* — capture `20170918042045` of
  `http://sp.gridpro.com/docs/FAQ's.pdf`. Answers quoted: T10, T13, T14, T15, T31, G15, G39,
  G41, G42, G43, G44, G45, G46, G47, G48.
- GridPro, `ws_Tutorials.zip` — capture `20150910111645` of
  `http://sp.gridpro.com/docs/ws_Tutorials.zip`. Files used:
  `Tutorials/Medium/Tutorial_1_Airfoil/{Tutorial_1_Airfoil.pdf, airfoil.fra, S830.lin,
  surf1.lin, surf2.lin, surf3.lin}` and `Tutorials/Basic/Tutorial_1_Square/_ws.sch`.

NASA:

- NASA Turbulence Modeling Resource, *2D NACA 0012 Airfoil Validation* —
  https://tmbwg.github.io/turbmodels/naca0012_val.html (the live
  `turbmodels.larc.nasa.gov/naca0012_val.html` 301-redirects to `nasa.gov`).
- NASA Turbulence Modeling Resource, *NACA 0012 grids* —
  https://tmbwg.github.io/turbmodels/naca0012_grids.html

This repo, read for overlap and for the schema:

- `docs/research/cell-size-range-within-a-block.md` §3 (corrected here, see L2 and §0).
- `docs/research/multi-element-airfoil-blocking.md` (the workshop growth-rate and y+ quotes).
- `docs/research/where-a-block-corner-sits-on-its-ring.md` §3 (confirmed, from a source that
  note could not reach).
- `.claude/rules/mesher-multiblock.md`, `.claude/rules/mesher-spacing.md`,
  `.claude/rules/mesher-quality.md`.
- `examples/topology/cgrid_naca0012.json`, `examples/topology/tworing_ogrid.json`.
