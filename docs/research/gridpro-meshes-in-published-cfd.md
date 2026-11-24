# GridPro meshes in published CFD work

**A RESEARCH NOTE, like the twelve beside it.** Not `.claude/rules/*.md` (what the rule is), not
`docs/design_notes/` (why a shipped rule was chosen). It records what **third-party** published
CFD work — papers and reports by people who are not GridPro — actually shows when it meshes with
GridPro. Nothing here is binding; no rule, gate, test or source file was changed to write it.
Searched and drafted 2026-11-12; §1 independently re-verified and one of its readings walked back
2026-11-24 (see the block in §1c).

**What was asked.** Find published CFD work (journal, conference, thesis, technical report) that
used GridPro to generate its mesh AND shows that mesh in a figure; learn how practitioners who use
GridPro BLOCK and PRESENT a mesh, and in particular **how the blocking carries from the near field
out to the far field**.

**What this note is NOT.** `gridpro-blocking-method.md` and
`nesting-blocks-at-a-complicated-leading-edge.md` already cover GridPro's own material — two of its
YouTube videos, its *Airfoil with icing* application article, its WS GUI Manual, its blog, its
tutorials. All of that is **vendor self-published**. This note deliberately excludes it, and §12
below names the two pieces of vendor material that turned up in this search so they are not
miscounted as third-party.

## How to read the markers

- **[V]** verified in a primary source I read myself (the vendor's own page, the video's own
  published frames, an HTTP response I made), or measured by me.
- **[I]** my own inference from a **[V]** fact. Stated as reasoning, not as fact.

Those two definitions are copied verbatim from `nesting-blocks-at-a-complicated-leading-edge.md`.
In this note the primary source is almost always **a PDF I downloaded and rendered page by page**,
so "a figure I read myself" means I looked at the rendered page or at the figure's own embedded
image extracted at full resolution — never at a caption alone. **Every claim about what a figure
shows is marked, and where I could only read the caption or the body text, it says so.**

---

## 0. The result in one block

**Ten third-party publications were found that used GridPro AND carry a figure of the resulting
mesh or topology that I could see.** **[V]** They are listed in §1–§10. Two more name GridPro as
the mesher and show **no mesh figure at all** (§11). The search method and its reach are in §13;
what the ten say together is §14.

| # | Case | What the mesh figure shows | Blocking vs. distance from the body |
|---|------|---------------------------|--------------------------------------|
| 1 | Venus entry capsule, transonic wake | wake zoom + whole-domain circle | **count REDUCES outward** — "nested topological refinement", visible |
| 2 | MEADS II ballistic-range capsule | 4 panels: full / side / forebody / backshell | body wrap morphs into a near-isotropic outer field; refined wake strip |
| 3 | Shuttle Orbiter | surface grid + outer envelope as a surface | 191 wall-normal elements from wall to shock envelope — no reduction |
| 4 | REST hypersonic inlet | **wireframe only** (block edges + corners) | 290 elemental blocks merged to 17 superblocks |
| 5 | HPT rotating blade (LES, 120 M cells) | surface grid lines, **once-coarsened**, 3 zoom panels | not shown — no far-field panel |
| 6 | Flat plate + film-cooling hole; OSU HPT stage | **block outlines**, coloured by boundary condition | 19 blocks, internal flow |
| 7 | DrivAer car (DG/ILES) | surface grid + tunnel-plane grid, 2 zoom panels | lines reach the outer planes, stretching smoothly |
| 8 | Marine propeller S6368 | meridional cut + blade surface | cylindrical domain at 5 D; cut shows outward coarsening |
| 9 | Spinning golf ball | one dimple close-up, surface only | **GridPro grid STOPS** and is overset onto a Cartesian background |
| 10 | ICE3 high-speed train | surface + ground-plane grid | ground grid grades away from the train |

**Of those ten, exactly two state a block count** (§4's 290→17 and §6's 19), and **not one colours
its cells by block.** **[V]** Nine of ten state a cell count and nine state a y+ or a first-cell
height. **[V]** See §14.

---

## 1. Stern, Barnhardt, Venkatapathy, Candler & Prabhu (2012) — the one case that answers the question outright

**Citation.** E. Stern, M. Barnhardt, E. Venkatapathy, G. Candler, D. Prabhu, *Investigation of
transonic wake dynamics for mechanically deployable entry systems*, **2012 IEEE Aerospace
Conference**, Big Sky MT, 3–10 March 2012. DOI `10.1109/AERO.2012.6187000`. NTRS
`20120011649`, report `ARC-E-DAA-TN4603`. **[V]** — I downloaded and read the full NTRS PDF
(`https://ntrs.nasa.gov/api/citations/20120011649/downloads/20120011649.pdf`, 10.7 MB); the author
block, affiliations (U. Minnesota / ERC Inc. / NASA Ames) and the conference line are on page 1,
and the NTRS citation record returned the meeting and date.

**Is the figure visible to me: YES.** I rendered page 3 and then extracted both figures' own
embedded images at full resolution (1769x577 and 1183x1027 px) and read those. **[V]**

### 1a. What the authors say about the blocking, verbatim **[V]**

> "A commercial grid generation package, GridPro [4], was used to generate the grid topology and
> smooth the body-fitted mesh. Care is taken to maintain local grid isotropy in the wake region,
> meaning that the computational cells are nearly uniform and cartesian in this area of interest.
> Furthermore, the topology is designed such that one can cluster points in regions where strong
> gradients and unsteadiness are likely to be present (in this case, the wake), while having a
> fairly coarse mesh in more quiescent regions of the flow. **This is achieved by using a nested
> topological refinement strategy** which can be seen in the plane shown in Figure 4."

And:

> "The final grid used for the simulation had approximately 120 cells across the wake. Finally, as
> is often done in transonic flow simulations, the refined portion of the grid was extruded to a
> large distance from the probe resulting in a large sphere as the total computational domain, as
> depicted in Figure 5. In general, the boundary for this grid is approximately 30 vehicle
> diameters from the vehicle itself."

Vehicle diameter 8.6 m (Table 2 of that paper). Ref [4] is `http://www.gridpro.com/`. **[V]**

### 1b. What Figure 4 actually shows, read off the image **[V]**

Figure 4's caption is "Wake portion of the grid used for all simulations. Note that the grid is
refined within the wake while being comparatively coarse outside of the wake region."

What I see in the 1769x577 image: a half-plane, the vehicle as a black silhouette at the lower
left, the symmetry axis and the wake running along the **bottom** edge. The wake band is the
finest region and its cells are nearly square. Moving **away** from the wake (upward in the
figure), the grid passes through **two visible tiers of arch- or dome-shaped seams**: a lower tier
of roughly eight smaller domes and, above it, a tier of roughly five larger domes. Each dome is a
closed interface: the fine lines coming up out of the wake **end on the dome**, and above it the
line spacing is visibly coarser. **[V]** — this is a count read off the picture; the paper states
no block count anywhere.

**That is a count-reducing, terminating blocking, drawn.** The number of grid lines crossing a
horizontal cut falls as you move away from the wake, in discrete steps, each step marked by one of
those domes. **[I]** from the **[V]** reading above plus the authors' own phrase "nested
topological refinement".

**AND THE TERMINATION IS LOCAL TO A REGION, NOT A RING AROUND THE BODY — which is where this
differs from what this repo built for #192.** **[V]** on the figure, **[I]** on the comparison. The
domes TILE along the wake: each one caps a patch of the refined band and the lines coming out of
that patch end on it, so the refinement is spent where the wake is and nowhere else. #192's
`reducing_stack` halves the count on a CONCENTRIC RING, all the way round the body, whether or not
the flow there needs it — the same device (a corner shared by three blocks, lines ending on a
seam), applied to a different footprint. Nothing here says which is better; what it says is that
the published instance solves the harder problem, and that a ring is the easy case of it.

### 1c. What Figure 5 shows **[V]**

Caption: "Wide view of the mesh used which shows the exaggerated stretching of the grid near the
boundaries. The size of the cells at the boundary are of the order of the diameter of the
vehicle."

In the 1183x1027 image I see a near-circular outer boundary with radial lines running from a dark,
saturated core (the body plus the refined wake, which reads as a four-pointed black star) out to
the circle. The azimuthal line count at the outer circle is far lower than at the core, and the
outermost ring of cells is coarse and nearly square. **[V]**

> **ONE READING IN THIS SUBSECTION WAS WALKED BACK, 2026-11-24, by the session that commissioned
> this note re-extracting the same image.** The sentence above originally continued "and the radial
> families visibly **fan and terminate** on the way out", marked **[V]**. On a second look the
> DENSITY plainly falls outward, but at this resolution **termination cannot be told apart from
> stretching** in Figure 5 — in the upwind half the radial lines read as continuous from the core
> to the boundary. Figure 4 is where termination is unambiguous, because each dome is a seam with
> coarser spacing above it. The claim is therefore **[I]** at best from Figure 5, and §1b carries
> the evidence. Kept as a specimen rather than silently edited: a figure that agrees with the
> conclusion you already reached is the one you read least carefully.

**This pair — a near-field zoom that shows where the lines stop, plus a whole-domain view that
shows what survives to the boundary — is the single most on-point presentation found in this
search.** **[I]**

> **AND COUNTED, 2026-11-24.** `gridpro-blocking-method/plot_vs_stern_fig4.py` counts the grid
> lines crossing a horizontal cut through Figure 4 off the raster and plots them beside this
> repo's own reducing stack (`vs_stern_fig4.png`) — the first measurement of a GridPro mesh's own
> line count in any of these notes, and half of the blind spot
> `nesting-blocks-at-a-complicated-leading-edge.md` §15g names. **Both fall.** The lower 39% of
> that figure SATURATES — median white gap 2 px, 50-66% ink, lines merged — so the count there is
> a severe undercount and is excluded by a drawn saturation line. The source image is not
> committed, per the convention in this directory's Sources.
>
> **ADOPTED, 2026-11-24.** `gridpro-blocking-method/plot_two_panel.py` draws this repo's own
> `MESH_MODE 1` meshes in that format, and the omissions are copied as deliberately as the
> inclusions: black cell edges, no colour by block, no axes, no legend, and the numbers in a
> printed caption rather than burnt into the panel. §14b is the measurement that licenses each of
> those. Worked: `two_panel_stack_deep.png` beside it, and
> `nesting-blocks-at-a-complicated-leading-edge.md` §16h.

### 1d. Stated numbers **[V]**

~120 cells across the wake; outer boundary ≈ 30 vehicle diameters; vehicle diameter 8.6 m;
Re_D ≈ 2.1–2.9 x 10^6; ballistic (α = 0°) with a 0.5°/1°/2°/5° sweep at M 0.8. **No total cell
count, no block count and no y+ is stated in the text I read.** **[V]** (negative)

---

## 2. Stern, Schwing, Brock & Schoenenberger (2016) — MEADS II, the four-panel near→far sequence

**Citation.** E. C. Stern, A. M. Schwing, J. M. Brock, M. Schoenenberger, *Dynamic CFD Simulations
of the MEADS II Ballistic Range Test Model*, **AIAA Aviation 2016**, Washington DC, 13–17 June
2016, **AIAA 2016-3243**, DOI `10.2514/6.2016-3243`. NTRS `20190002018`, report
`ARC-E-DAA-TN56834`. **[V]** — full PDF downloaded from NTRS (13.5 MB); authors and affiliations
(NASA Ames / NASA JSC / AMA Inc. / NASA Langley) read off page 1; the DOI came from OpenAlex,
which also records that this paper **cites Eiseman's 2005 "Automatic nested refinement" paper**
(`10.1007/s00366-005-0310-1`).

**Is the figure visible to me: YES.** Page 4 rendered, and all four of Figure 2's embedded images
extracted at 2044x1817 px; I read panels (a) and (b) at that resolution. **[V]**

### 2a. What the authors say **[V]**

> "The grid is generated using the commercial package GridPro.12 … Because we use the same grid
> for a range of Mach numbers, as well as pitch angles, we have added refinement to accommodate,
> both ahead of the body, and aft. Additionally, for performing dynamic simulations, it is
> desirable to have greater distance between the body and domain boundaries than would ordinarily
> be required. … The grid used for these simulations had a total of 20 million cells. Typical grid
> spacings in the wake are approximately 2mm. The first cell wall spacing was set to be 1µm, which
> results in a y+ < 1 for the entire vehicle surface."

Reference 12 is the Eiseman *Automatic nested refinement* paper (Eng. Comput. 21(1), 2005,
29–35). **[V]**

### 2b. How it is PRESENTED **[V]**

Figure 2, "Grid used for US3D simulations", is **four panels in a 2x2 block**: (a) Full, (b)
Close-up side, (c) Forebody, (d) Backshell. The body is filled solid blue; the grid is drawn as
black lines on a cut plane through the axis. No colouring by block, no block outlines, no legend.
**[V]**

The paper then shows, as **Figure 3**, the OVERFLOW overset grid system for the same vehicle
("automatic off-body grids … and manual box grids, which extend into the far field"), so the
reader gets a GridPro body-fitted grid and an overset grid side by side in one paper. **[V]** on
the captions; I did not render Figure 3.

### 2c. What the blocking does with distance, read off panels (a) and (b) **[V]**

Panel (b), the close-up: a body-conforming wrap hugs the capsule — the near-wall lines are too
fine to separate at this scale and read as a solid black rim — and within roughly **one body
diameter** that wrap has relaxed into a field of **nearly square, nearly uniform quads**. The
circumferential clustering of the wall does **not** persist outward as thin wedges, and the
corner/shoulder singularities do not throw spokes to the frame edge. **[V]**

Panel (a), the full view: the outer field is essentially a smooth, almost rectangular grid running
to all four frame edges, with the body-conforming patch embedded in it and a **solid black refined
strip** extending downstream from the shoulder to the right-hand edge — the wake refinement the
text describes — plus a visibly denser region ahead of the body. **[V]**

**I could not see a discrete count-reducing seam in either panel** — unlike §1's domes, the
transition here reads as continuous. **[V]** (a negative about the picture, not about the mesh:
at this reproduction scale a single halving seam could be invisible.)

---

## 3. Candler & Campbell (2010) — Shuttle Orbiter: the far field drawn as a SURFACE

**Citation.** G. V. Candler (U. Minnesota) and C. H. Campbell (NASA JSC), *Hypersonic
Navier-Stokes Comparisons to Orbiter Flight Data*, **48th AIAA Aerospace Sciences Meeting**,
Orlando FL, 4–7 January 2010, **AIAA 2010-455**, DOI `10.2514/6.2010-455`. NTRS `20100001402`,
report `JSC-CN-19534`. **[V]** — PDF downloaded from NTRS (2.7 MB) and read; NTRS citation record
gave the meeting and date.

**Is the figure visible to me: YES.** Page 3 rendered. **[V]**

### 3a. What the authors say **[V]**

> "A new grid for the Shuttle Orbiter was generated using the GridPro grid generation software.
> The grid was designed to resolve the windward side of the Orbiter, while providing a supersonic
> outflow condition. This was achieved by **wrapping the grid around the fuselage and wing leading
> edge**, so that the flow would expand to supersonic conditions before leaving the grid domain.
> **The outer boundary of the grid was defined by a smooth surface that approximates the bow shock
> envelope** at the lowest Mach number condition."

> "The resulting grid for the half Orbiter has **206,400 elements on the surface, with 191
> wall-normal elements**, resulting in a total of nearly **40 million** hexahedral elements. For
> the cases in which the full vehicle was computed, this grid was mirrored across the symmetry
> plane to obtain a grid of about 80 million elements."

The grid is then **shock-tailored**: each wall-normal line is re-cut so the bow shock sits at a
given wall-normal index, the points between wall and shock are redistributed to put the first
point at y+ = 1, and several smoothing passes follow. **[V]**

### 3b. The blocking-vs-distance answer here is explicit in the numbers **[I]**

206,400 surface elements x 191 wall-normal elements = 39.4 M, i.e. **every one of the 206,400
surface lines runs unbroken from the wall to the outer boundary**. There is no de-refinement
outward at all — the near-wall surface resolution is paid for over the whole wall-to-shock
distance. **[I]**, arithmetic on the two **[V]** numbers above, and consistent with the paper's own
"wrapping the grid around the fuselage" and per-line shock tailoring.

### 3c. How it is PRESENTED **[V]**

Figure 1, "Several images of the surface grid and shock-adapted outer envelop of grid for the
half-Orbiter", is three panels: two red **surface-grid** views (lines only, so dense they read as a
red wash, with a handful of black dots marking thermocouple locations) and one view of the
**outer envelope drawn as an opaque white surface** with the vehicle inside it in green. **[V]**

**So the far field appears in the figure as a SHAPE, not as grid lines** — the reader is shown
where the domain ends, never how the mesh fills it. **[V]**

---

## 4. Ferlemann & Gollan (2009/2010) — REST hypersonic inlet: the only wireframe figure found

**Citation.** P. G. Ferlemann (ATK Space Systems) and R. J. Gollan (National Institute of
Aerospace), *Parametric Geometry, Structured Grid Generation, and Initial Design Study for
REST-Class Hypersonic Inlets*, **JANNAF 43rd Combustion / 31st Airbreathing Propulsion Joint
Meeting**, La Jolla CA, 7–11 December 2009. NTRS `20100002213`, report `LF99-8882`. **[V]** — PDF
downloaded from NTRS (4.4 MB), read, and page 6 rendered; NTRS citation record gave the meeting.

**Is the figure visible to me: YES.** Page 6 rendered. **[V]**

### 4a. The most explicit statement of the GridPro WORKFLOW found in any third-party paper **[V]**

> "GridPro grid generation software focuses human effort on creating the block topology, or the
> wire frame, created by the block edges. While each grid block must be structured (8 corners and
> 6 faces), they can be connected in an unstructured way. In two dimensions, this means that **3 or
> 5 edges could share the same corner point**, rather than the usual 4 edges. Such points are
> referred to as **singularities and are best used only when necessary** to achieve the desired grid
> flow. Once a topology is created, the grid solver produces a grid which conforms to the geometry
> and **maintains a relatively equal cell size and aspect ratio outside the boundary layer**."

> "The topology primarily consisted of block corners defined at the sidewall start, mid-point of
> the sidewall, cowl start corner, midpoint of the cowl, notch, inlet exit, and isolator exit. Grid
> topology **singularities on the surface were limited to** the start of the sidewall, start of the
> cowl, middle of the external cowl, and on the interior and exterior surfaces at the notch."

> "Due to the high curvature created by the blunt leading edges and twisting required by some
> blocks, **the behavior and results of the GridPro grid solver were significantly affected by the
> initial block corner locations.** Therefore, although the topology remained constant conceptually,
> the corner locations were adjusted to the geometry for each case."

> "Since the corners were positioned properly before executing the GridPro solver, it only had to
> project the surface grid to the geometry and perform a fairly small amount of smoothing. Only
> **500 iterations, or about 2 minutes**, were required (single 2.33 GHz processor). An inviscid
> cell dimension of 0.2 inches or less was selected … GridPro utilities were used to add boundary
> layer points with a **near wall spacing of 0.0005 inches to achieve a y+ of approximately one**
> for most of the model and to **merge the 290 elemental blocks into 17 superblocks**. … Each case
> had **2.7 million cells**."

### 4b. How it is PRESENTED **[V]**

Figure 3, "Structured grid block topology (top – complete volume, bottom – surface only)", is
**two stacked panels**: the top is the **GridPro wireframe** — grey block edges with **orange
block corners** marked as dots, plus a handful of coloured block faces (purple, magenta, yellow,
cyan) to orient the reader — and the bottom is the inlet **surface geometry alone**, in teal, with
a "Flow" arrow. **[V]**

**No grid lines appear anywhere in that figure.** The paper shows the topology and the geometry,
and never the cells. **[V]**

### 4c. Why this one matters to this repo **[I]**

It is the only third-party paper found that (a) states a block count, (b) states the elemental →
superblock merge, (c) names the odd-valence corner ("3 or 5 edges could share the same corner
point") as a thing to be rationed, and (d) says out loud that the **initial corner positions
decide whether the solver converges to something usable**. All four are repo-adjacent concerns.
**[I]** from the **[V]** quotes above.

---

## 5. Miki, Ameri, Beach, Steinthorsson, Poinsatte, Thurman, Arisi, Prenter & Vincent (2025) — 120 M-cell HPT blade LES

**Citation.** K. Miki *et al.* (NASA Glenn Research Center, with Ohio State, HX5 LLC, A&E
Consulting), *LES Analysis of a High-Pressure Turbine Rotating Blade Flow Including Purge and Tip
Flows*, **Proceedings of ASME Turbo Expo 2025**, Memphis, 16–20 June 2025, paper
**GT2025-153348**; journal version *J. Turbomach.* 148(8) 081011, DOI `10.1115/1.4071899`.
**[V]** — I downloaded and read NASA's copy of the proceedings paper
(`https://ntrs.nasa.gov/api/citations/20240016026/downloads/IGTI_2025_Miki.pdf`, 5.6 MB); title,
paper number, venue and author block are on page 1. The journal DOI came from OpenAlex.

**Is the figure visible to me: YES.** Page 4 rendered. **[V]**

### 5a. What the authors say **[V]**

> "A high-quality structured grid with **120 million cells** was used to resolve the
> high-Reynolds-number flow and the complex secondary flow structures. **The grid was constructed
> using GridPro.** Figures 4(a)-(c) show the grid topology at the midspan, near the endwall, and
> close-ups of the grid near critical areas, including the trailing edge, the leading edge/tip, and
> the leading edge at the hub."

> "The grid spacing near the wall was placed at **3 x 10^-6 m**, achieving a **y+ value of 0.3**,
> which ensured adequate resolution of the viscous sublayer."

Normalized tip clearance 0.014 of axial chord; geometry is the Penn State START rig blade, "the
detailed geometry information is proprietary, and the blade shape has been arbitrarily scaled."
**[V]**

### 5b. How it is PRESENTED — the one paper that says it coarsened the picture **[V]**

Figure 4 is captioned "**TOPOLOGY OF MESH AND A ONCE-COARSENED MESH** NEAR THE TRAILING/LEADING
EDGES, TIP, AND ENDWALL" and is three panels: **(a) Topology of multi-block** — grid lines on the
blade and endwall surfaces in a perspective view; **(b) Near trailing edge** — a flat zoom showing
the lines wrapping the rounded trailing edge; **(c) Leading edge at the hub (PS)** — a zoom at the
blade/hub junction. All three are grey-scale surface grid lines. **[V]**

Despite "Topology of multi-block" in the sub-caption, **(a) draws grid lines, not block
boundaries** — nothing in the figure identifies where one block ends and the next begins. **[V]**

**There is no far-field or whole-passage mesh panel.** The 120 M-cell grid is shown only as blade
and endwall surfaces plus two feature zooms, at half resolution. **[V]**

---

## 6. Shyam (2010) — NASA TM: block outlines, coloured by boundary condition

**Citation.** V. Shyam (NASA Glenn Research Center), *Preprocessor that Enables the Use of
GridPro™ Grids for Unsteady Reynolds-Averaged Navier-Stokes Code TURBO*, **NASA/TM—2010-216739**
(E-17316), June 2010. NTRS `20100025865`. **[V]** — 91-page PDF downloaded from NTRS and read;
pages 9 and 14 rendered.

**Is the figure visible to me: YES.** Pages 9 and 14 rendered. **[V]**

This one is a tooling report, not a flow study — it documents a converter from GridPro's grid,
`.conn` connectivity and boundary-condition numbering into TURBO's `GU`, `bc.in`, `dmap.in`,
`turbo.in`. Its interest here is that **it is the only document found that draws the blocks
themselves as the subject of the figure.** **[V]**

### 6a. What the figures show **[V]**

**Figure 3, "Computational domain for example 1"** (flat plate with a film-cooling hole): a
perspective line drawing of **block outlines only** — three large boxes end to end plus a plenum
box below, the hole's blocks drawn as a narrow twisted bundle between them. Three faces are filled
with flat colour and labelled by arrows: grey **Inlet**, blue (a second inlet), red **Outlet**,
and a **Plenum inlet**. The text says "The grey inlet patch belongs to **block 8 of the 19-block
grid**. The blue inlet patch belongs to block 9. The grey exit patch belongs to block 11 while the
red exit patch belongs to block 12." **[V]**

**Figure 8, "Computational domain for example 2"** (the Ohio State HPT stage): the same style for a
stator/rotor pair — black block outlines around each blade row, with the blade surfaces as dark
solids, the **sliding interface in blue**, and the two **periodic (time-shift) boundaries in green
and red**, each drawn as a mesh sheet so the reader can see that those two faces must match.
**[V]**

### 6b. Why that presentation choice is the interesting part **[I]**

This figure is not trying to show mesh quality; it is trying to show **which block carries which
boundary condition**, because that is what the preprocessor has to get right. Colour is spent on
boundary **role**, not on block identity, and the block count is given in the body text, not in a
legend. **[I]** from the **[V]** readings above.

---

## 7. Colombo, Bortoli, Conti, Crivellini, Ghidoni, Nigro & Noventa (2021) — DrivAer car

**Citation.** A. Colombo *et al.* (U. Bergamo, U. Brescia, Politecnica delle Marche),
*Assessment of a Discontinuous Galerkin Method for the Simulation of the Turbulent Flow around the
DrivAer Car Model*, **Applied Sciences 11(21), 10202**, 2021, DOI `10.3390/app112110202`. **[V]** —
open-access PDF downloaded from `mdpi-res.com` (25.4 MB) and read; page 6 rendered.

**Is the figure visible to me: YES.** Page 6 rendered (Figures 4 and 5). **[V]**

### 7a. What the authors say **[V]**

> "In this work, the generation of the curved high-order meshes, suitable for the DG method, is
> performed using the **GridPro** [40] software. Different structured meshes with high-order
> hexahedral elements are generated for each geometry. **The software elevates the linear meshes
> into 2nd- (quadratic edges), 3rd- (cubic edges) or 4th- (quartic edges) order meshes.** A cubic
> representation of the edges is adopted for the simulations presented in the following."

> "The 'original' DrivAer fastback model has been slightly simplified, removing the handles and the
> rear-view mirrors, smoothing the underbody and closing the front radiator grid. … The mesh
> consists of **406,304 cubic-edges hexahedral elements**."

A second, simplified geometry uses **113,780 cubic-edges elements** (Figure 6's caption). **[V]**
The acknowledgements thank "GridPro (Block Structured Mesher) for the support regarding meshing",
and reference [40] is the GridPro website. **[V]**

### 7b. How it is PRESENTED **[V]**

**Figure 4** is a single perspective view: the car's **surface mesh** plus the grid drawn on the
**tunnel floor and the two far planes behind and beside it** — so one picture carries both the
body and the outer boundary. **Figure 5** is a two-panel zoom, "Detail of the mesh near the rear
end of the body (left) and the front wheel (right)". The same pair is repeated for the simplified
geometry as Figures 6 and 7. Grey-scale, grid lines only, **no block colouring, no wireframe**.
**[V]**

### 7c. What the blocking does with distance, read off Figure 4 **[V]**

On the floor and the back plane I can follow individual grid lines from the region under and
behind the car out to the frame edge: they **arrive at the outer boundary**, stretching smoothly
and bending around the car's silhouette, and the cells near the top of the frame are many times
larger than those at the body. Around the wheels and the wheel arches the lines crowd and turn to
follow the feature, and that crowding visibly **relaxes within about a car height**. **[V]**

I see **no terminating seam** on the visible planes. **[V]** The near-body line families appear to
run all the way out. **[I]** — stated as an inference because a perspective view of three planes
cannot rule out a seam hidden behind the body.

---

## 8. Baltazar, Rijpkema & Falcão de Campos (2021) — marine propeller, six-grid refinement series

**Citation.** J. Baltazar (IST Lisbon / MARETEC-LARSyS), D. Rijpkema (MARIN), J. Falcão de
Campos, *Prediction of the Propeller Performance at Different Reynolds Number Regimes with RANS*,
**J. Mar. Sci. Eng. 9(10), 1115**, 2021, DOI `10.3390/jmse9101115`. **[V]** — open-access PDF
downloaded from `mdpi-res.com` (18.4 MB) and read; page 9 rendered and Figure 1's embedded image
extracted at 2400x1563 px.

**Is the figure visible to me: YES.** Both the page and the figure's own image. **[V]**

### 8a. What the authors say **[V]**

> "Two series of six nearly-geometrically similar **multi-block structured grids** are generated
> using the commercial grid generation package **GridPro** [50]. The first grid series is used for
> the calculations at the Reynolds numbers from 1 x 10^4 to 5 x 10^5. The grids range from **1 to 35
> million cells**. The second grid series … range from **1 to 39 million cells**. … The differences
> between the two grid series are due to the **grid space weighting in the boundary-layer region** in
> order to obtain a y+ < 1 for all Reynolds number regimes. Therefore, the boundary-layer is fully
> resolved and no wall functions are used."

> "In the simulations a **cylindrical domain** is considered, where the inlet, the outlet and the
> outer boundary are located **five propeller diameters** from the propeller origin."

Table 3 gives the whole series: volume cells 1.0/2.2/4.3/8.0/17.8/34.8 M against 4/6/10/15/25/39 k
**cell faces on a single blade**, with max y+ falling from 0.74 to 0.31 at Re = 5 x 10^5 and from
0.34 to 0.10 at Re = 1 x 10^7. Propeller S6368, D = 0.2714 m, 4 blades. **[V]**

### 8b. How it is PRESENTED **[V]**

**Figure 1**, "Overview of the grid around propeller and blades. Grid with 8.0 M cells", is **two
panels side by side**: left, a **meridional cut** through hub and blade (the hub reads as a white
body, the blade sections as thin white spikes above and below it); right, a **blade surface mesh**
in perspective with the hub and a neighbouring blade. Black lines on white, no block colouring.
**One grid out of twelve is shown.** **[V]**

### 8c. What the blocking does with distance, read off the extracted image **[V]**

In the left panel: a dense wall-clustered wrap hugs the hub and both blade-section spikes. Where
each spike meets the hub there is a **point from which grid lines fan out radially** — a corner of
odd valence, drawn. Around each blade section I can see **small closed loops**, i.e. a local wrap
that closes on itself rather than running to the frame. Away from those, the lines coarsen
steadily and the cells become large and nearly square towards the top, bottom and left of the
panel, where the grid is essentially a smooth H-field. The frame cuts off well inside the 5 D
boundary, so **the actual far field is not in the picture**. **[V]**

---

## 9. Crabill, Witherden & Jameson (2019) — spinning golf ball: GridPro's grid STOPS and is overset

**Citation.** J. Crabill, F. Witherden, A. Jameson, *High-order computational fluid dynamics
simulations of a spinning golf ball*, **Sports Engineering** 22, 2019, DOI
`10.1007/s12283-019-0300-y`. **[V]** — I read the authors' arXiv preprint
`arXiv:1806.00378v1` (7.5 MB, header "Sports Engineering manuscript No."), downloaded from
`https://arxiv.org/pdf/1806.00378`; page 6 rendered. The journal DOI came from OpenAlex.

**Is the figure visible to me: YES.** Page 6 rendered. **[V]**

### 9a. What the authors say **[V]**

> "The surface was exported in the STL format and used within the multiblock structured mesh
> generator **GridPro** [11] to create a spherical grid with a boundary layer. **The surface of the
> golf ball was divided into 24 roughly square regions, each with a resolution of 144 x 144
> quadrilaterals, with 60 layers in the radial direction, for a total of 29,859,840 linear
> hexahedra**, or 1,105,920 cubically curved hexahedra after agglomeration. The first cell height
> was chosen to be at an estimated y+ value of 6.667 (3.4 x 10^-5 m), **the first 18 layers were
> held to a constant thickness, and the remaining 42 layers were allowed to grow out to a final
> outer diameter of 31.82mm**."

388 dimples, ball diameter 42.7 mm, dimple depth 6.41 x 10^-4 m, dimple diameter 2.99 mm, edges
filleted at 0.75 mm radius. Measured max y+ at the solution points is 3.5, average 1.0. **[V]**

> "**This pseudo-structured golf ball grid was then combined with a mostly Cartesian background
> grid created in Gmsh** [13] to fill the desired extents of the full computational domain. The box
> has a width and height of 0.6832m (**16 times the golf ball diameter D**), and length 1.0248m
> (**−12D to 12D**). A refined region was created in the area to be occupied by the golf ball, with
> a refined wake region stretching out to the rear of the domain for a total of 715,750 linear
> hexahedra elements."

Reference [11] is "Eiseman, P.R., Ebenezer, S.J., Sudharshanam, V., Anbumani, V.: GridPro manuals
(2017)", and the acknowledgements thank Eiseman "for providing academic licensing to the GridPro
meshing software and assisting with" the meshing. **[V]**

### 9b. The answer to the near→far question here is: the GridPro grid never reaches the far field **[V]**

**The structured GridPro block grid is a shell around the ball and stops.** The far field is a
separate, mostly Cartesian Gmsh box, and the two are joined by **overset** connectivity (TIOGA).
So the question "how does the blocking carry out to the far field" has, in this paper, the answer
"**it does not — it is terminated at a sphere and handed to another grid**". **[V]** from the
quotes above.

### 9c. How it is PRESENTED **[V]**

Figure 1 is four images: (a) side view and (b) top view of the **dimpled surface**, shaded, with no
mesh visible at this reproduction; (c) "**Closeup of dimple mesh**" — grid lines over a single
dimple and its surroundings, roughly 40 x 40 cells of visible mesh; (d) three views of the ball
coloured by computed y+ (0 to 3.5), where the dimple pattern is visible but the individual cells
are not. **[V]**

**So the only mesh picture in the paper is one dimple.** The 24-region blocking, the 60 radial
layers, the overset interface and the Cartesian background are all described **in words only** and
never drawn. **[V]**

### 9d. One figure I could not reconcile **[V]**

The ball is 42.7 mm in diameter, yet the boundary-layer grid is said to "grow out to a final outer
**diameter** of 31.82mm". Taken literally the outer boundary of the near-body grid would be inside
the ball. I quote it as printed and do not resolve it; the most likely readings are that 31.82 mm
is a radial **extent** or a thickness rather than a diameter. **[I]**

---

## 10. Norouzi, Hossainpour & Rashidi (2023) — ICE3 high-speed train

**Citation.** S. Norouzi, S. Hossainpour (Sahand University of Technology, Tabriz) and M. M.
Rashidi (UESTC, Chengdu), *Investigating the effect of train speed and ground clearance on
aerodynamics of a simplified high-speed train*, **Scientia Iranica B 30(2)**, 2023, 428–441, DOI
`10.24200/sci.2022.60478.6817`. **[V]** — open-access PDF downloaded from the journal
(`scientiairanica.sharif.edu`, 5.8 MB) and read; page 4 rendered.

**Is the figure visible to me: YES.** Page 4 rendered. **[V]**

### 10a. What the authors say — and an internal contradiction **[V]**

> "The domain mesh is generated using a **predominately Cartesian cut-cell approach**. … **The
> computational mesh has been generated using GridPro software and imported into OpenFOAM**
> open-source code. Due to the large gradients in the two areas next to the train and the ground
> clearance, these areas have been **subdivided using two separate blocks**."

> "The cells have grown in a proportion less than 0.1 from the train's surface to the outermost
> regions. … the cells near the buckets are arranged such that **y+ value be considered around 30 to
> 100**."

Three grids (coarse / medium / fine) were compared; a "6.2 M cell mesh" is named in a figure
caption. **[V]**

**"A predominately Cartesian cut-cell approach" is not what GridPro does, and it is not what their
own Figure 3 shows.** I record the sentence verbatim and flag it rather than choosing one of the
two claims. **[V]** on the quote; the judgement that the two disagree is **[I]**.

### 10b. How it is PRESENTED, and what it shows **[V]**

Figure 3, "Surface meshing system", is a single perspective view: the train body carried by a
**body-fitted quad surface mesh** that follows the nose and the roofline, standing on a **ground
plane whose structured quad grid is dense under and beside the train and fans outward**, coarsening
with distance. Nothing in the picture resembles a cut-cell grid — there are no hanging nodes and no
staircase at the body. **[V]**

Figure 2 gives the domain as a dimensioned sketch: **40 W x 20 W** in the cross-plane, with **10 W
upstream, 35 W across the train region and 52 W downstream** (W = train width). **[V]**, read off
the rendered figure.

---

## 11. Two more that named GridPro and showed NO mesh figure

Both are included because the negative is part of the answer: naming GridPro in the method section
and never drawing the grid is common.

**11a. Synáč & Rudas (2011), Škoda Power.** *Numerical and experimental investigations of
supersonic turbine cascade flow*, **ETC2011-028**, 9th European Conference on Turbomachinery
(ETC09), Istanbul, 21–25 March 2011. PDF downloaded from `euroturbo.eu` and read. **[V]**

> "The 2D model of the tip cascade blade channel was realized in the preprocessor **GridPro**, where
> the calculation domain was meshed with quadrilateral cells. The grid quality was measured by the
> **equiangle skew. Only 1.01% cells exhibited skew value over 0.6, while the maximal value of skew
> was 0.72.** The cells near airfoil contours, near the shock wave and in the wake downstream the
> trailing edge were refined. **The 2D grid consisted of 95,000 cells.** … thickness of the first
> cell layer near the wall corresponded to **y+ < 2.5**."

I enumerated all fifteen figure captions in that paper: geometry, tunnel scheme, cascade scheme,
experimental setup, Mach distributions, schlieren, interferograms, loss and choking curves.
**None is a mesh.** **[V]** It is, notably, the only third-party paper in this whole search that
reports a **quality metric** for its GridPro mesh.

**11b. Brown, Kormanik III, Matthews & Key (2023), Purdue.** *Experimental and computational
analysis of heat transfer effects on the performance of a multi-stage axial compressor*,
**ETC2023-369**, ETC15, Budapest, 24–28 April 2023. PDF downloaded from `euroturbo.eu` and read.
**[V]**

> "The computational domain is discretized using **GridPro** - a multi-block, structured grid
> generation tool. … includes hub and shroud fillets, shrouded stator domains with cavities and
> knife seals, hot rotor tip and knife seal clearances, and bleed flow paths. … the targeted first
> cell offset from all walls is **y+ ≤ 1, with greater than ten elements within the boundary layer**.
> A grid convergence study … resulted in **grid convergence indices of less than 0.25% and 0.6%** in
> total pressure ratio and total temperature ratio … **The mesh is conformal through the tip
> clearance gap.**"

All nine figure captions enumerated: facility, hardware, temperature maps, heat flux, "CHT CFD
Model of the PAX200 Compressor", two profile comparisons. **No mesh figure.** **[V]** (I did not
render Figure 7, so whether that "CFD Model" picture incidentally carries grid lines is
unverified. **[V]** as a stated gap.)

---

## 12. What is NOT third-party, and must not be counted as such

**12a. AIAA 2018-0659, "High Lift CRM Locally Structured Grid Generation with GridPro"** — this is
the paper a web search surfaces first for "GridPro airfoil grid generation", and it is **by
GridPro**. Authors Vimalraj Anbumani, Samuel E. James and Peter R. Eiseman, all with the raw
affiliation string **"PDC/GridPro"**, presented at the 2018 AIAA Aerospace Sciences Meeting, DOI
`10.2514/6.2018-0659`. **[V]** — read from the OpenAlex record for that DOI, which carries the
three authorship entries with their affiliation strings. I could not open the paper itself (AIAA
ARC is paywalled), so **I make no claim about its figures.** It is cited as reference [14] by the
2026 *Applied Sciences* paper in §13c below. **[V]**

**12b. "GridPro HO Meshes", HiOCFD5.** A 27-page presentation by Vijay Sudharshanam, Samuel
Ebenezer and Peter Eiseman, "Program Development Company © 2015", given at the **5th International
Workshop on High-Order CFD Methods** and hosted at `acdl.mit.edu/HOW5/WorkshopPresentations/`.
**[V]** — PDF downloaded (14 MB) and its text read. Vendor material in a third-party venue; it is
listed here so a future reader does not mistake the MIT URL for third-party authorship. I did not
mine its figures.

**12c. The GridPro blog is where several web-search "findings" actually came from.** A WebSearch
for GridPro + C-grid/O-grid + far field returned a confident summary about "six grids for a 2D
NACA-0012 … two structured grids using GridPro — one O-type and one C-type … in C-type, the
boundary layer extends downstream carrying the boundary layer fitness till the farfield", attached
to a list of links that included four arXiv aerofoil papers. **I downloaded all four
(arXiv 1705.00230, 2109.02183, 2401.14793, 2609.27568) and grepped them: GridPro appears zero
times in each.** **[V]** The claim traces to `blog.gridpro.com`, i.e. vendor material, not to any
of those papers. **This is the one place in this search where a search engine's synthesis would
have produced a false third-party citation.**

---

## 13. How the search was done, and what it reached

**13a. Two bibliographic indexes were queried directly, not through a search engine.** **[V]**

- **NASA NTRS**, `https://ntrs.nasa.gov/api/citations/search?q=GridPro` → **11 records**, of which
  I resolved every one: 3 are by Program Development Corp. themselves (Eiseman, Cheng), 1 is the
  NASA Spinoff article, 1 is a conference-proceedings parent record, 2 are metadata-only abstracts
  by students (Kiefer, Jordan), and 4 are the third-party documents used above or adjacent to them.
- **OpenAlex**, `https://api.openalex.org/works?search=GridPro` → **184 works** (fuzzy, so most are
  false positives), and `filter=title_and_abstract.search:GridPro` → **37 works** (tight). I read
  all 37 titles and the first 150 of the 184, and pulled every open-access PDF that looked like an
  external-aerodynamics or turbomachinery user of the tool.

**13b. Then every candidate PDF was downloaded and grepped for "gridpro" before any figure was
looked at.** That is how §1–§11 were separated from near-misses. Papers downloaded and found to
contain **no** mention of GridPro: arXiv 2208.14793 (partially submerged cylinder), arXiv
1705.00230, arXiv 2109.02183, arXiv 2401.14793, arXiv 2609.27568. **[V]**

**13c. One paper worth naming because it is about exactly this repo's problem and does NOT use
GridPro.** M. Jiang, Z. Zhao, J. Chen, M. Mao, Y. Sun (China Aerodynamics Research and Development
Center), *Automatic Structured Mesh Generation Method for Airfoil Configuration Based on Parametric
Multi-Block Topology*, **Applied Sciences 16(2), 1116**, 2026, DOI `10.3390/app16021116`. **[V]** —
open-access PDF downloaded from `mdpi-res.com` (4.2 MB) and grepped: **GridPro appears exactly
once, in reference [14]**, which is the vendor-authored AIAA 2018 CRM paper of §12a. So the nearest
published neighbour of this repo's own problem cites GridPro as prior art and meshes with something
else. **[V]**

**13d. The "automatic nested refinement" technique is barely cited.** OpenAlex records **four**
works citing Eiseman's *Automatic nested refinement: a technique for the generation of high quality
multi-block structured grids for multi-scale problems using GridPro* (Eng. Comput. 21(1), 2005,
29–35, DOI `10.1007/s00366-005-0310-1`): the MEADS II paper of §2, two AIAA papers on thermal
propellant gauging (2007), and a Springer book chapter *Automatic Topology Generation* (2006).
**[V]** The §1 paper describes the same technique in its own words without citing that paper.
**[I]**

---

## 14. What the ten say together

### 14a. On blocking vs. distance from the body, the ten split four ways **[I]**, from the **[V]** readings above

1. **The count REDUCES outward, visibly, and the paper says so** — §1 only. "Nested topological
   refinement", two tiers of terminating domes between the wake and the quiescent field, drawn in
   a zoom panel and corroborated by the whole-domain panel.
2. **The body wrap dissolves into a near-isotropic outer field with no visible seam** — §2 and §7,
   and §8 within its frame. This is the behaviour Ferlemann's **[V]** quote describes as GridPro's
   own: the grid solver "maintains a relatively equal cell size and aspect ratio outside the
   boundary layer". What the eye sees is the *shape* of the blocks changing from body-conforming to
   Cartesian-like, not the *number* of lines changing. **Whether the line count reduces in these
   cases cannot be read off the published figures.** **[V]** as a limit.
3. **Every near-wall line runs to the outer boundary** — §3, where the arithmetic is explicit
   (206,400 x 191) and the outer boundary is a fitted bow-shock envelope.
4. **The structured grid is terminated and handed to a different grid** — §9, an overset Cartesian
   background.

**There is no case in this set where a paper states a block count as a function of distance**, and
only §1 draws the near and the far field in a way that lets a reader compare them. **[V]**

### 14b. On presentation, the patterns are narrow **[V]**

> **BOUNDED, 2026-11-24.** Every figure in this note is a THIRD-PARTY one, and the findings below
> are about those. **The VENDOR's own aerofoil figure IS coloured by block**, in three panels from
> the far field in to the nose (`media.gridpro.com/.../2017/10/img12.webp`, compared in
> `nesting-blocks-at-a-complicated-leading-edge.md` §16j). So "zero of ten" is a statement about
> what PRACTITIONERS publish, not about what the tool's own material does, and the two audiences
> differ.

- **Colour by block: zero of ten.** The only colour used on a mesh figure in this whole set is
  §6's, and it marks **boundary conditions** (inlet / outlet / sliding interface / periodic), not
  block identity. §4's wireframe colours four faces, as orientation aids rather than as a
  classification. **[V]**
- **A block skeleton as the subject of the figure: two of ten** — §4 (wireframe with corners) and
  §6 (block outlines). Both are *grid-generation* or *tooling* papers. **No flow-physics paper in
  this set drew its blocking.** **[V]**
- **A near→far panel sequence: two of ten** — §2 (full / side / forebody / backshell) and §1
  (wake zoom + whole domain). **[V]**
- **A whole-domain mesh panel at all: two of ten** — §1 and §2. §3 shows the far field as an opaque
  surface, §7 shows it as the tunnel planes in a perspective view, and the rest stop at the body.
  **[V]**
- **Surface-grid-only figures: five of ten** — §3, §5, §9, §10, and §7's zoom panels. **[V]**
- **One paper states that its figure is coarsened** — §5, "A ONCE-COARSENED MESH", in the caption.
  That is the only explicit admission in the set that what is drawn is not what was run. **[V]**

### 14c. On numbers **[V]**

| Case | Cells | Block count | Far field | y+ / first cell |
|------|-------|-------------|-----------|-----------------|
| §1 capsule wake | not stated | not stated | ~30 vehicle diameters | not stated |
| §2 MEADS II | 20 M | not stated | "greater … than ordinarily required", no number | y+ < 1, 1 µm |
| §3 Orbiter | 40 M half / 80 M full; 206,400 surface x 191 normal | not stated | fitted bow-shock envelope | y+ = 1 by construction |
| §4 REST inlet | 2.7 M | **290 elemental → 17 superblocks** | internal flow | y+ ≈ 1, 0.0005 in |
| §5 HPT blade | 120 M | not stated | internal flow | y+ = 0.3, 3 x 10^-6 m |
| §6 TURBO preproc. | not stated | **19 (example 1)** | internal flow | not stated |
| §7 DrivAer | 406,304 (and 113,780) cubic-edge hexes | not stated | tunnel planes, no distance stated | not stated in what I read |
| §8 propeller | 1.0–39.0 M, twelve grids | not stated | cylindrical, 5 D | max y+ 0.74 → 0.10 |
| §9 golf ball | 29,859,840 linear / 1,105,920 curved + 715,750 background | 24 surface regions, 60 radial layers | 16 D x 24 D box (Gmsh, not GridPro) | y+ ≈ 1 at solution points, max 3.5 |
| §10 train | 6.2 M named | "two separate blocks" for the clearance regions | 40 W x 20 W, 10 W / 52 W | y+ 30–100 |

**Cell count is near-universal (9 of 10), y+ or first-cell height is near-universal (9 of 10),
block count is rare (2 of 10 as a real count), and a mesh quality metric appears exactly once in
the whole search — §11a's equiangle skew.** **[V]**

### 14d. What this does and does not settle for this repo

It settles nothing: this is a research note and binds no rule. What it adds to what the repo
already holds is that **§1 is a published, third-party, drawn instance of the count-reducing
outward blocking** that `nesting-blocks-at-a-complicated-leading-edge.md` §15d and §16 discuss on
this repo's own meshes — in a paper that reached it with GridPro and called it "nested topological
refinement". The second thing it adds is a sobering one for presentation: **of ten papers that
used GridPro, none drew its blocks in colour and only two drew its blocks at all**, so "how
practitioners present a GridPro mesh" answers mostly "as surface grid lines, with the blocking
described in prose or not at all". **[I]** from §14a and §14b.

---

## Sources

Primary, downloaded and read by me (every PDF was fetched with `curl` and read with `pdftotext
-layout`; pages named below were rendered as images and looked at, and where it says "image
extracted", the figure's own embedded bitmap was pulled out with `pdfimages` and read at full
resolution):

- `https://ntrs.nasa.gov/api/citations/20120011649/downloads/20120011649.pdf` — §1, Stern *et al.*
  2012. Page 3 rendered; Figures 4 and 5 images extracted (1769x577, 1183x1027).
- `https://ntrs.nasa.gov/api/citations/20190002018/downloads/20190002018.pdf` — §2, MEADS II
  (AIAA 2016-3243). Page 4 rendered; all four Figure 2 panels extracted at 2044x1817, panels (a)
  and (b) read.
- `https://ntrs.nasa.gov/api/citations/20100001402/downloads/20100001402.pdf` — §3, Candler &
  Campbell 2010 (AIAA 2010-455). Page 3 rendered.
- `https://ntrs.nasa.gov/api/citations/20100002213/downloads/20100002213.pdf` — §4, Ferlemann &
  Gollan. Page 6 rendered.
- `https://ntrs.nasa.gov/api/citations/20240016026/downloads/IGTI_2025_Miki.pdf` — §5, Miki *et
  al.* 2025 (GT2025-153348). Page 4 rendered.
- `https://ntrs.nasa.gov/api/citations/20100025865/downloads/20100025865.pdf` — §6, Shyam,
  NASA/TM—2010-216739. Pages 9 and 14 rendered.
- `https://mdpi-res.com/d_attachment/applsci/applsci-11-10202/article_deploy/applsci-11-10202.pdf?version=1635741607`
  — §7, Colombo *et al.* 2021. Page 6 rendered.
- `https://mdpi-res.com/d_attachment/jmse/jmse-09-01115/article_deploy/jmse-09-01115.pdf?version=1634696514`
  — §8, Baltazar *et al.* 2021. Page 9 rendered; Figure 1 image extracted (2400x1563).
- `https://arxiv.org/pdf/1806.00378` — §9, Crabill, Witherden & Jameson, Sports Engineering
  preprint. Page 6 rendered.
- `https://scientiairanica.sharif.edu/article_22941_ee651f25a93c1b922367564320a5a2de.pdf` — §10,
  Norouzi *et al.* 2023. Page 4 rendered.
- `https://www.euroturbo.eu/paper/ETC2011-028.pdf` — §11a, Synáč & Rudas. All fifteen figure
  captions enumerated from the text layer; no page rendered (no mesh figure to render).
- `https://www.euroturbo.eu/paper/ETC2023-369.pdf` — §11b, Brown *et al.* All nine captions
  enumerated; no page rendered.
- `https://mdpi-res.com/d_attachment/applsci/applsci-16-01116/article_deploy/applsci-16-01116.pdf`
  — §13c, Jiang *et al.* 2026. Text grepped only.
- `https://acdl.mit.edu/HOW5/WorkshopPresentations/GridPro_HO_Meshes.pdf` — §12b, the vendor's
  HiOCFD5 presentation. Text read, figures not mined.
- `https://arxiv.org/pdf/2208.14793`, `https://arxiv.org/pdf/1705.00230`,
  `https://arxiv.org/pdf/2109.02183`, `https://arxiv.org/pdf/2401.14793`,
  `https://arxiv.org/pdf/2609.27568` — downloaded and grepped for §13b's negative result.

Bibliographic APIs, queried with `curl` and parsed by me:

- **NASA NTRS search API**, `https://ntrs.nasa.gov/api/citations/search?q=GridPro&page.size=25` —
  11 records with titles, author affiliations, STI types and dissemination status; plus the
  per-record endpoint `https://ntrs.nasa.gov/api/citations/<id>` for meetings, dates and report
  numbers on five of them.
- **OpenAlex**, `https://api.openalex.org/works?search=GridPro` (184 works, pages 1–4) and
  `https://api.openalex.org/works?filter=title_and_abstract.search:GridPro` (37 works) — the
  candidate list.
- **OpenAlex single-work endpoints** — `works/doi:10.2514/6.2018-0659` for §12a's three
  "PDC/GridPro" affiliation strings; `works/doi:10.1007/s00162-016-0388-7` for the closed-access
  status in "Tried and could not get"; `works/doi:10.1007/s00366-005-0310-1` and
  `works?filter=cites:W2030912463` for §13d's four citing works.

Secondary, in this repo, referred to rather than re-derived:

- `docs/research/gridpro-blocking-method.md` and
  `docs/research/nesting-blocks-at-a-complicated-leading-edge.md` — the vendor-material notes this
  one deliberately does not repeat, and the source of the marker discipline copied above.

## Tried and could not get

- **`www.mdpi.com` PDF and HTML endpoints** — plain `curl` returns a 414-byte HTML stub, and
  WebFetch on `https://www.mdpi.com/2076-3417/16/2/1116` returned **HTTP 403**. Sending a browser
  User-Agent to get round it was **refused by this environment's policy (bot-check
  circumvention)**, and was not retried by any other route. **The fix that worked was legitimate
  and is worth recording: MDPI's own file host `mdpi-res.com` serves the same PDFs to plain `curl`,
  at `https://mdpi-res.com/d_attachment/<journal>/<journal-vol-issue>/article_deploy/<name>.pdf`,
  and needs the `?version=<n>` query that the OpenAlex `oa_url` carries** — without the version
  query it returns a 146-byte redirect stub.
- **`https://www.epj-conferences.org/articles/epjconf/pdf/2015/11/epjconf_efm2014_02080.pdf`** —
  returns a 779-byte HTML document, twice. So *Scalability of the parallel CFD simulations of flow
  past a fluttering airfoil in OpenFOAM* (EPJ Web Conf. 92, 02080, 2015), which OpenAlex lists as a
  GridPro mention and which is an **aerofoil** case, could not be checked. This is the most
  regrettable gap in the set.
- **`https://doi.org/10.1007/s00162-016-0388-7`** — *Effect of boundary representation on viscous,
  separated flows in a discontinuous-Galerkin Navier–Stokes solver* (Theor. Comput. Fluid Dyn.,
  2016), by the same group as §7 and a likely aerofoil/cylinder GridPro case. OpenAlex reports
  `oa_status: closed`, `any_repository_has_fulltext: false`, and the only location is the Springer
  landing page. Not read.
- **`https://doi.org/10.82366/111`** (*CFD Based Airfoil Shape Optimization for Aerodynamic Drag
  Reduction*, American University of Sharjah) and
  **`https://upcommons.upc.edu/bitstream/handle/2117/330625/MARINE_2017.pdf`** (Delft Twist11
  hydrofoil cavitation, MARIN/UPC) — both returned HTML, not PDF, at the URLs I had; I did not
  find the real file paths. Both are plausible aerofoil/hydrofoil GridPro cases and remain
  unchecked.
- **`https://iris.unibs.it/bitstream/11379/626248/2/Bulgarini_2025.pdf`** and the UniBG `aisberg`
  copy of Colombo *et al.*'s 2022 CAA paper — 5.5 KB and 6.3 KB HTML stubs respectively.
- **AIAA ARC** — no attempt was made to fetch `10.2514/6.2018-0659` or `10.2514/6.2023-3020`
  (*A Shock Fitting Technique For Hypersonic Flows Using Hexahedral Meshes*) past the paywall;
  both are recorded as unread.
- **A third-party 2-D aerofoil GridPro mesh figure** — none was found. Every aerofoil-shaped lead
  resolved to either the vendor's own material (§12) or to a paper that does not use GridPro
  (§13b, §13c).

## Named limits

1. **"Ten" is a floor, not a count of the literature.** It is the number of third-party documents
   I could reach, open and read in this session. The index coverage is the binding constraint:
   NTRS's 11 hits and OpenAlex's 37 tight hits are **metadata** matches. A paper that names GridPro
   only in its method section — which is exactly where it would be named — is invisible to both
   unless the indexer has full text. §11a and §11b were found this way only because their
   full-text PDFs happened to be openly indexed by the search engine. **The true population is
   certainly larger and probably much larger.** **[I]**
2. **Nine of the ten are external to this repo's problem in at least one way.** Four are internal
   flow, three are 3-D blunt bodies, one is a car, one a propeller, one a train. **None is a 2-D
   aerofoil.** Any transfer of §14's conclusions to a 2-D aerofoil blocking is an extrapolation.
3. **"No visible seam" is a statement about a published picture, not about a mesh.** In §2, §7 and
   §8 I could not see a count-reducing interface; at the reproduction scale of a journal figure a
   single halving seam can be invisible, and in §7's perspective view a seam can be behind the
   body. Only §1's claim of a reducing count is supported by both the figure **and** the authors'
   own words.
4. **I read one figure from each paper in most cases.** §2, §5, §7 and §8 each contain more mesh
   panels than I rendered; §11b's Figure 7 was not rendered at all. A fuller read could change the
   presentation tallies in §14b, though not the block-colouring one, which rests on every mesh
   figure I did see.
5. **Three of the ten papers I read are the work of overlapping author groups.** §1, §2 and §3 all
   involve the US3D community (Stern, Candler) and the NASA Ames entry-systems group; §1 and §2
   share a first author. **So the "nested topological refinement" finding of §1 and the
   near-isotropic outer field of §2 are not two independent practitioners.** **[V]** from the
   author lists.
6. **Nothing here was checked against a GridPro installation.** No claim in this note about what
   GridPro *can* do rests on anything but what these authors wrote and drew; the vendor's own
   account is in the two notes named at the top, and where the two disagree — §10's "Cartesian
   cut-cell" sentence — this note flags the disagreement rather than resolving it.
7. **Figure interpretation is mine.** Counts like "roughly eight smaller domes" in §1b and "within
   about one body diameter" in §2c were read off a rendered image by eye, with no scale bar in the
   original. They are marked **[V]** as *readings*, and should be re-measured before any of them is
   quoted as a number.
