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
| **D — §13, the C/H** | `make_ch.py` | `gridpro_ch.json` | `gridpro_ch.dat` |

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
- **The outer boundary is a RECTANGLE**, and the grid becomes a Cartesian lattice aligned with
  it.

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
The eta lines run from that C out to a RECTANGLE (`x ∈ [-2, 7]`, `y ∈ [±3]`).

Nothing wraps round the front, so the lines leaving the nose point **at the inlet** and the
lines leaving the wake point at the top and bottom. That is §12a's fig6, and it is a property
of the topology rather than of any tuning.

```
cells=18432 inverted=0 nonortho_max=54.793 nonortho_mean=4.304
quad_midline_ratio_median=2.648 p95=24.393  adjacent_area_ratio_max=7.813
wall first cell: 0.09% worst on the BODY, 5.95% worst counting the far-field edges
```

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

`gridpro_ch_full.png` and `gridpro_ch_te.png`, rendered as QUADS for §11a's reason. The
downstream half is a streamwise lattice, the upstream half points at the inlet, the wake is a
thin band along `y = 0`, and the far field is a rectangle the grid is aligned to — which is
what §12a set out to reproduce.

### 13e. Against everything before it **[V]**

| | §8: 14 blk | §10: 58 blk, 3 rings | §11: 38 blk, 2 rings | §13: 24 blk, C/H |
|---|---|---|---|---|
| cells | 17408 | 17408 | 17408 | 18432 |
| inverted | 0 | 0 | 0 | 0 |
| worst non-orthogonality | 59.856° | 55.277° | **48.095°** | 54.793° |
| mean non-orthogonality | 12.307° | 9.552° | 7.137° | **4.304°** |
| cell shape, median | 2.751 | 2.801 | 2.818 | **2.648** |
| worst adjacent area ratio | 11.713 | 12.565 | 14.149 | **7.813** |
| worst wall first cell, BODY only | 0.01% | 0.01% | 0.01% | 0.09% |
| worst wall first cell, ALL wall edges | **0.0139%** | 0.0111% | 0.106% | 5.95% |
| far field | D of the tutorial's circle | circle | circle | **rectangle** |

**The cell counts are not equal** — 18432 against 17408, 5.9% more — because the C/H's station
law is derived rather than dialled, and the nearest settings either side came out at 17088
(worse grading) and 21504 (better). The columns are still worth reading: a 6% cell difference
does not move a mean from 7.1° to 4.3° or an area ratio from 14.1 to 7.8.

**[I]** So the C/H wins the two columns that describe the FIELD — mean non-orthogonality and
size grading — by a wide margin, and loses the two that describe the BOUNDARIES: its worst
corner is 6.7° behind §11's, and it holds the far-field spacing far less well, because its
outer boundary is a rectangle whose four corners the control function has to turn through.
**The BODY's own first cell is held by all four** — the run prints 0.01% for the three ring
cases and 0.09% here, all of them measured off the bound aerofoil edges only, which is the
figure a viscous solve cares about; the "all wall edges" row is dominated by the far field,
which no case is asked to resolve.
**For a viscous solve on this body the C/H is the one to use, and that is the first time in
this note the answer has not been the O-ring.**

### 13f. What is still not GridPro's **[I]**

§10b, and only §10b: its curvature is a converged elliptic solve and this repo's smoother
diverges at sweep 13, so every line here is placed by a declaration rather than solved for.
Everything else §§9-12 listed as different — the far field's shape, the streamwise lattice, the
wake band, the block count being in the right range — is now reproduced.

---

## Sources

Direct fetches (`curl`, article text and `<img alt>` extracted from the page HTML):

- Krishnamurthy, R., *The Art and Science of Meshing Airfoil*, GridPro blog, 6 November 2017 —
  https://gridpro.com/blog/the-art-and-science-of-meshing-airfoil/
- Krishnamurthy, R., *Is Grid Generation an Art or Science?*, GridPro blog, 17 September 2017 —
  https://gridpro.com/blog/grid-generation-an-art-or-science/
- Figure images, read visually: `media.gridpro.com/wp-content/uploads/2017/11/f12.webp`,
  `.../2017/10/img10.webp`, `.../2017/10/img12.webp`, `.../2017/11/img11_1.webp`,
  `.../2017/10/img6.webp`.

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
