# Why local nesting — what the method is claimed to buy, and what it is measured in

**A RESEARCH NOTE, like the eleven beside it.** Not `.claude/rules/*.md` (what the rule is), not
`docs/design_notes/` (why a shipped rule was chosen). It records what an outside literature check
says about a question this repo is currently deciding by feel, so the decision can be argued from
sources rather than from a table of our own numbers. Nothing here is binding; **no rule, gate,
test or source file was changed to write it**, and neither
`nesting-blocks-at-a-complicated-leading-edge.md` nor `gridpro-blocking-method.md` was touched.
2026-11-10.

> **THAT SENTENCE WAS TRUE WHEN WRITTEN AND IS NO LONGER, recorded rather than quietly edited
> (2026-11-10, later the same day).** The decision this note fed —
> `nesting-blocks-at-a-complicated-leading-edge.md` §14 — declined local nesting and took §3.4's
> spacing-match criterion instead, so **issue #183 changed `include/MbQuality.hpp`,
> `src/MbQuality.cpp`, `src/cli.cpp`, two gates, `.claude/rules/mesher-quality.md` and
> `docs/design_notes/mesher.md`**, and §14 was added to the note above. Nothing in THIS file's
> findings moved; what changed is that it stopped being a note nothing acted on. The whole value
> of the `[V]` / `[I]` / `[M]` markers is that a claim can be checked against the world, and a
> self-description left to go stale would be the first one to fail.

**The question, as asked.** 如果沒有比較好的話為什麼影片中要用這個方法? — if local block nesting
at a complicated leading edge does not produce a better mesh, why does GridPro's video teach it?
What benefit is the method actually *claimed and shown* to deliver, and under what conditions?

## How to read the markers

- **[V]** verified in a primary source I read myself (vendor manual, conference paper, report).
- **[I]** my own inference from a **[V]** fact. Stated as reasoning, not as fact.
- **[2nd]** I could only find this secondhand. Treat as unconfirmed. **It does not appear below**:
  every claim in this note is either a source I read myself or an inference marked as one.
- **[M]** a measurement supplied by the requester in the brief that commissioned this note. **I did
  not re-derive any of these.** They are quoted so the sources can be set against them.
- **[V, OCR]** verbatim from a source I read myself, but one that is a scan whose OCR is poor. The
  two AIAA papers from 2002 are scans; their text carries artefacts (`beeb`, `Di viding`, `rvrn`),
  and every quotation from them is reconstructed from OCR and marked at the point of use.

**A note on source access.** The GridPro *WS GUI Manual* v1.0 (2014) and the GridPro *FAQ* are the
two documents that carry the vendor's own statement of what `nest` is for. Both are behind a
HubSpot form on the live site; I read the Internet Archive captures named in Sources, as PDFs
fetched with `curl` and extracted with `pdftotext -layout`. They are the vendor's own text, not a
summary of it, so they are **[V]**; they are archived copies, and that is stated rather than
hidden. The journal version of the nesting paper (*Engineering with Computers*, 2005) is closed
access; **I did not read it**. I read instead the authors' own earlier conference version of the
same work, IMR12 (2003), which Semantic Scholar lists as its green open-access copy. The
underlying University of Virginia master's thesis, which is where both papers send the reader for
every quantitative comparison, **I could not obtain at all** — see Gaps.

---

## 0. The measurements this note is set against — the requester's, verbatim, not re-derived

**[M]** both:

1. §6f of `nesting-blocks-at-a-complicated-leading-edge.md`: on an iced aerofoil, **adding blocks
   at the feature made the mesh worse** — `--split` 32 → 48 → 64 gave **8 → 25 → 99 inverted
   cells**.
2. §11 of the same note: a valence-3 nest on a NACA 0012 works (26 blocks, 648 quads, **0
   inverted**) but **could not be made thin** — swept as a fraction of the body-to-far-field gap,
   0.02 folds **9** cells, 0.04 folds 7, 0.06 and 0.10 fold 2, and only **0.15** holds at 0.

---

## Lead: the seven answers, in order of how much they should change the reading

### L1 — The stated benefit is CELL COUNT at a required resolution, and ASPECT RATIO at the feature. Neither is a number the §6f or §11 sweeps produced. **[V]**

GridPro's own *WS GUI Manual*, §4.8.2 *Nest*, in full and verbatim — this is the fuller statement
the brief asked for, and it is longer and more specific than the FAQ line this repo already holds:

> "**Nest is very useful when you are handling geometries with large-scale differences.** It
> automates the creation of topology to achieve nested refinement in a simple and efficient way.
>
> Conventional meshing techniques on geometries with scale differences create **grids with large
> aspect ratio especially near the smaller features**. Improvement on the aspect ratio can be done
> by increasing the density throughout the geometry to capture the geometry of a smaller scale.
> **The refinement near the geometry is necessary, but limiting because refinement propagates to
> the far field.** This limitation can be overcome by using nesting. It helps to **increase number
> of grid points near the geometry of concentration locally, with one to one connectivity, without
> increasing the points elsewhere**. The nested structure **loops back blocks** near the geometry
> and in the defined region."

**[V]** Rajagopalan and Eiseman state the same thing as an arithmetic argument, in the paper that
carries the phrase `nesting-blocks-at-a-complicated-leading-edge.md` §5.5 looked for and could not
find — *Automatic Nested Refinement*, IMR12, 2003:

> "If the same size cells are used in the large-scale field too, then there will be **too many
> cells at places where it is not needed**, and this can cause **the computational time of the
> numerical simulation to be too big for any practical purposes**."

> "But suppose we set quality criteria on the grid. — **Set the worst aspect ratio of the grid to
> be less than 10**, and the grid should be smooth etc. A simple way is to just build a structured
> grid with a lot of grid points to capture the small features in the geometry. If we take this
> strategy, then the grid in figure 5(a) will have **about a million cells**. In figure 8, the
> radius of the tiny tube is about 0.005, and the box dimensions are of the order 10*10*10. This
> means that a simplistic strategy like the one described above will yield a grid having **more
> than 10 billion cells**!"

**[V]** **[I] The unit of the claim is the whole answer to the brief's question.** Both statements
are in *cells at a stated resolution*, and the secondary one is in *aspect ratio*. The §6f sweep
reports **inverted cells at a fixed `--split`** and §11's sweep reports **inverted cells against
band thickness**; §11c adds mean and max non-orthogonality. **None of those is cells-at-a-fixed-
resolution and none of them is aspect ratio.** The claimed benefit was never on the instrument.

### L2 — The second stated benefit is that the refinement does not reach the far field, and the vendor describes the mechanism geometrically: grid lines are turned back into the body. **[V]**

> "Figure 7(b) shows a closer view of the grid where one can note how **nested refinement helps in
> reducing the propagation of many grid lines by redirecting many of them back into the island**."
> — IMR12, on the Oahu coastline case

**[V]** The same paper calls the result "a structured grid which lies inside **a cocoon of nested
refinement**" **[V]** — the word the GridPro blog already uses in this repo
(`gridpro-blocking-method.md` §2c, "the central cocoon of blocks"). The FAQ's three
nest answers are the GUI-level statement of the same thing, and the third adds the reverse
direction: `nest` refines "near the geometry **without affecting the far field**" (T37);
`reverse_nest` reduces blocks and "thereby reducing the cell count" in the far field (G52);
`Enrich` refines "near the geometry which **will not affect the far field**" (G53). **[V]**

### L3 — The ratio law is 1:3ⁿ per level, and the shipped examples use FIVE levels. A nest is a BAND, not a ring, and this bears directly on §11b. **[V]**

> "The ratios specified alongside the number give the overall cell size/resolution ratio which will
> be achieved between the high and low density regions. For example, in the case of the wavy wall
> shown in figure 5, the number of cells required in the top is 12 and the number of cells we need
> in the bottom is around 3000. This threshold ratio is close to 200, and hence, **the number of
> levels can be chosen to be 5, which will give an average ratio of 243. The ratios go as 1:3ⁿ,
> where n is the number of levels of nested refinement.** This can be mathematically proved."
> — IMR12 §5

**[V]** And the GUI manual says the same structure from the topology side:

> "As you can see, **for each layer three corners are substituted for each corner on the previous
> layer**."
> — *WS GUI Manual* §4.8.2, *Forward Nest*; its Figure 4.97 is captioned *Nesting structure* and
> labelled "Levels of Refinement = 2"

**[V]** **[I] Two things follow for §11.** First, the requester's valence-3 construction is the
right primitive — three corners replacing one *is* a valence-3 substitution, and the repo arrived
at it independently. Second, **one level buys a factor of 3 and nothing more**, so a nest that
does useful work is several levels deep; the wavy-wall case needed five to reach ~243. A single
terminating ring is a 1-level nest, which is the thinnest and weakest member of the family, and
§11b measured exactly that member.

### L4 — No source read here claims nesting improves folds, orthogonality or skewness. GridPro attributes fold removal to the OPTIMISER, which is the part this repo does not have. **[V]**

GridPro's quality report has four parameters, and **Folds** is one of them — "Fold are defined as
the inconsistency in the positioning of the grid nodes of a cell, with respect to the neighboring
cells", beside *Aspect ratio*, *Skewness* and *Warpage* (*WS GUI Manual* §5.5). **[V]** So the
vendor does measure the quantity §6f and §11 report. **It does not claim `nest` moves it.** The
word "fold" does not occur in §4.8.2 at all, and in the IMR12 paper it occurs only about the
relaxation:

> "The robust optimization algorithms can **untwist a folded block** as shown in figure 3."

> "Figure 4 illustrates the grid point movement algorithms by showing pictures of a grid at
> different iteration steps for the grid generation engine. Again, we see that **the folded grid
> cells in (a) have been unfolded and neatly placed in (c)**. This illustrates the robustness of
> the GridPro's grid generation engine."
> — IMR12 §2, on iterations 100 / 500 / 3000 of the same topology

**[V]** **[I] This is the cleanest corroboration §6f could have asked for, and it is the vendor's
own.** §6f attributed the 8 → 25 → 99 to the generator's cast far-field map rather than to the
blocking, and noted that "GridPro does not have this failure mode because its far-field positions
are relaxed by the solver". The IMR12 figure 4 sequence *is* that relaxation, shown recovering
from folds that the topology as declared did contain. In GridPro's division of labour, the nest
chooses *how many cells go where* and the optimiser is what makes the result valid; the repo's
`MESH_MODE 1` has the first and casts rather than relaxes the second. **A rising inverted-cell
count under added blocks is therefore not evidence against the claimed benefit of nesting — it is
a measurement of the half of GridPro's mechanism this repo does not run.**

### L5 — The general literature names this operation (pillowing / shrink-and-connect / buffer insertion), states its purpose, AND states its cost — and the cost is exactly §11b's symptom. **[V]**

Tchon, Dompierre & Camarero, *Conformal Refinement of All-Quadrilateral and All-Hexahedral Meshes
According to an Anisotropic Metric*, IMR11, 2002 — a paper IMR12 itself cites. The purpose first:

> "The present refinement primitive is based on a shrink and connect strategy and has been
> extensively used, although under several names, because **it is one of the few local operations
> that preserves the conformity and the all-quadrilateral or all-hexahedral characteristic of a
> mesh**."

> "…iterative local refinement methods using quadtrees in two dimensions can be extended in three
> dimensions using octrees but **result in non-conformal elements with hanging nodes that cannot be
> treated by some solvers**."

**[V]** Then the cost, and this is the sentence worth the whole search:

> "Note that **the corner configurations located at the extremities of the layers degrade mesh
> quality. This phenomenon is even more acute when several layers terminate at the same
> location.**"

> "Starting from such a perfect mesh, the present refinement primitive will modify this valence and
> **tend to degrade mesh quality, particularly at the corners of the shrunk layers.** That is why,
> to minimize this side effect, edge tags are propagated in step 1 using a strategy similar to
> quadtree and octree balancing. … Furthermore, **layers are augmented in the direction
> perpendicular to the refinement by their immediate neighbors in order to smooth out abrupt size
> variations.**"

**[V]** And two of their three named remedies are thickness:

> "Another way to improve mesh quality is to modify the layer agglomeration method. **The thickness
> of the layers can be increased.** Path optimization can be added. Balancing inspired from
> quadtree and octree methods can also help."

> "Element quality can, nevertheless, still be improved. Future work should include implementation
> of reconnection primitives, stronger coupling between refinement and smoothing, **thicker shrink
> layers** and an improved vertex relocation scheme."

**[V]** The authors also state, of their own method on a 3-D test case, "a non-negligible reduction
of the average shape indicator from 0.895 to 0.770. **The present algorithm trades off shape
quality for size conformity.**" **[V]**

**[I] §11b is this paragraph, measured.** The requester's construction terminates the nested row at
**one valence-3 corner at each end** — which is "several layers terminating at the same location"
in its limiting form — and the sweep found quality collapsing as the band is thinned. The
literature's named remedies are *thicker layers*, *balancing*, and *augmenting the layer with its
perpendicular neighbours*. §11b's own closing **[I]** — "GridPro's frame spreads each transition
over several diagonal edges rather than one, which is the obvious thing to try next" — is the same
remedy reached from the picture, and an independent primary source now states it.

### L6 — The only measured comparison I could reach on an ICED AEROFOIL runs against the method: blocking the leading edge cost grid points, CPU and drag accuracy. **[V, OCR]**

Choo & Slater, *Modeling and Grid Generation of Iced Airfoils*, ISGG 2002 (NTRS 20020071136), took
one iced-aerofoil inner block and **divided it into five blocks including one wrap-around block**,
same geometry, and ran WIND on all three variants:

> "The multiple-inner-block simulation with matching block boundaries required about **7.59% more
> CPU time** than the single-inner-block simulation to run the same number of iterations. However,
> the multi-block simulation had **2.72% more grid points** due to the blocking. Per grid point, the
> multi-block simulation required **4.74% more CPU time** than the single-block simulation."

and the accuracy table, verbatim:

| Grid | C_l | C_d |
|---|---|---|
| Single inner block | 0.432 | 0.0277 |
| Multiple inner block — matching | 0.450 (4.17%) | 0.0333 (20.22%) |
| Multiple inner block — overlapping | 0.429 (−0.69%) | 0.0303 (9.39%) |

> "Dividing the single inner block into five separate blocks resulted in **the convergence not
> dropping to the level observed with the single-block simulation**. In addition, high-frequency
> oscillations were greater for the multi-block simulation."

> "The general conclusion to draw from these studies is that when multiple blocks are needed to
> resolve complicated ice shapes, **overlapping the blocks in a contiguous manner will improve
> convergence and reduce errors in the transfer of flow information across block boundaries**."

**[V, OCR]** all four. The companion paper, Chi, Zhu, Shih, Slater, Addy & Choo, AIAA-2002-0381,
reports the same direction in its own grid table: the single-block inner grid SB-2 is
**816 × 101**, while the three multi-block inner grids are **131,197 / 98,898 / 111,594** points.
**[V, OCR]** **[I]** 816 × 101 is 82,416, so every multi-block variant of the same case carries
**more** points than the single-block one — 20% more for the cheapest. And on convergence:

> "When the inner grid is a multi-block grid, then the convergence has been either extremely slow
> or do not converge… up to 30,000 iterations have been performed with the behavior being similar.
> **The culprit is the data transfer across block boundaries in critical regions such as flow
> separation.**"

**[V, OCR]** **[I] Read carefully, this does not refute L1 — it is a different experiment.** Those
five blocks were cut to make the ice shape *griddable at all*, at unchanged density; nobody
nested, and no block's resolution was raised relative to another. What the numbers measure is the
**price of a block interface**, paid once per interface, in CPU and in solver accuracy. That price
is what a nest spends in order to buy L1's cell count, and it is the only published figure I found
for it on this class of geometry.

### L7 — GridPro's own nested-versus-globally-refined comparison is CLAIMED, in one sentence, with its numbers in a document I could not obtain — and the authors call validation future work. **[V]**

> "Figure 5(f) shows flow field solution for the wavy wall problem computed using Fluent®.
> **Comparisons between flow field solutions using the nested grid … and a overpopulated grid on
> the same geometry shows that the nested grid runs much faster but gives the same results.** For
> more details on this comparative simulation, refer to [1]."

where [1] is "Automatic Nested Refinement … Master's Thesis for Krishnakumar Rajagopalan presented
to the University of Virginia, May 2003". **[V]** I could not obtain that thesis (Gaps 1), so
**there is no number behind "much faster" in anything I read**, and this note does not supply one.

The same paper's conclusion says so itself:

> "**Verification and validation of the use of nested refinement by comparing performance of nested
> grids with other hybrid and unstructured grid methods will also be an important future
> direction.**"

**[V]** **[I] That is the honest state of the public record as of the paper that introduced the
technique**: the economy argument is arithmetic (L1), the one solver comparison is asserted in a
sentence with its detail elsewhere, and the authors list V&V as not yet done.

---

## 1. Iced aerofoils specifically: NASA Glenn's published answer is NOT local nesting

This matters because it is the one geometry class both halves of the question are about, and
because the brief asked whether there is a standard practice to name. There is, and it is
different.

**The stated multi-block problem for iced aerofoils is the near-wall clustering escaping along
block boundaries, and it is stated in aspect-ratio units.** **[V, OCR]**

> "Grid lines that are highly clustered next to solid walls propagate into the interior of the
> domain along block boundaries. Since these clustered grids next to walls typically have **very
> high aspect ratios (from hundreds to hundreds of thousands)**, they can induce considerable
> errors in the solution. **If this problem is not resolved, then it is impossible to generate a
> high-quality multi-block structured grid for iced airfoils.**"
> — Chi et al., AIAA-2002-0381

**The two named remedies are a THICK wrap-around and a transition layer**, and the thickness
criterion is stated as a rule a mesher could check: **[V, OCR]**

> "To overcome the first problem, a '**thick wrap-around**' grid is proposed… Basically, one layer
> of grid with clustering next to the wall is wrapped around the iced airfoil. **The thickness of
> this wrap-around is such that grid spacing from contiguous blocks will be comparable in size at
> all block boundaries.**"

> "A **transition-layer** grid is introduced to ensure that **jaggedness on the ice-surface
> geometry do not to propagate into the domain**. This is important for grid-generation methods
> based on hyperbolic PDEs and **algebraic transfinite interpolation**."

> "…if the wrap-around grid is **of the right thickness**, the problem shown in Fig. 2 can be
> eliminated."

**[V, OCR]** **[I] The last of those names this repo's method.** `MESH_MODE 1` fills a block by
transfinite interpolation, so the transition-layer argument is addressed to exactly this class of
generator, not to GridPro's relaxation.

**NASA's shipped tool decomposes the near field by RADIAL CUTS and couples the near field to the
far field by OVERSET, not by nesting.** From the SmaggIce 2.0 TM (clean text, not OCR): **[V]**

> "The viscous sublayer block is a **thin C-shaped domain** that wraps around the wake and iced
> airfoil. It serves as a **transition from the irregular geometry of the iced surface to a
> smoother outer boundary** while simultaneously providing a very dense mesh near the no-slip
> boundary with firm control."

> "For clean airfoils, or airfoils with relatively simple rime ice shapes, a single block topology
> may be sufficient. **For more complicated ice shapes, multiple blocks are recommended.** … **The
> multiple block topology is based on user-defined radial cuts.**"

> "The viscous sublayer block and near field blocks are created with **one-to-one abutting
> connectivity** to each other, while **the near field blocks and the outer block have overlapping
> (overset) connectivity** between them."

> "Frequently, points need to be distributed along a block edge so that **the cell spacings match
> those of the block's neighbors**. SmaggIce provides a tool to do this."

**[V]** And it records rejecting the all-conforming many-block route for multi-element cases:

> "Another method allowed for all structured, **all abutting one-to-one blocks. This method would
> have created many blocks which would quickly become tedious to modify with an interactive
> tool.**"

**[V]** **[I] So on this geometry the named standard practice is: a thin viscous sublayer that
absorbs the ice's jaggedness; a thick enough wrap-around that spacings match across each interface;
radial cuts rather than nests in the near field; and an overset handoff to the far field, which
gets the "refinement does not reach the far field" property for free and pays for it in the
solver.** `where-a-block-corner-sits-on-its-ring.md` §4 and
`cell-size-range-within-a-block.md` §4 already record overset's cost; nothing is new there. What
is new is that the people who mesh ice shapes for a living chose it over conformal nesting for
this exact case.

**One caution, because two sources pull opposite ways on thickness and the difference is real.**
SmaggIce says tangles in the viscous sublayer "can be removed by **reducing the thickness of the
block**" **[V]**, while Tchon et al. prescribe *thicker* shrink layers **[V]** and Chi et al. name
theirs *thick* **[V, OCR]**. **[I]** These are different objects: an offset band from a concave
surface tangles when its normals cross, which thinning fixes; a refinement transition degrades when
the density step is compressed into too few layers, which thinning makes worse. **§11b's object is
the second** — it is a transition between two densities, not an offset band — so the thicker-layer
reading is the applicable one, and the SmaggIce sentence is not a counter-example to it.

---

## 2. The direct answer to the question as asked

**Why does the video teach it, if it does not produce a better mesh?** Because the benefit the
vendor claims for it is not "a better mesh" in the sense §6f and §11 measured. In one line, from
the sources: **you get the cell count of a coarse far field and the resolution of a fine leading
edge at the same time, conformally, with no hanging nodes and no solver support required** — and
the price is a transition whose quality the literature says is poor at its terminations and has to
be bought back with layer thickness and a relaxer.

Four things follow, stated separately because they carry different weight.

1. **[V]** The claimed benefits are cell count at a required resolution (L1), bounded aspect ratio
   at the feature (L1), and a far field that does not inherit the refinement (L2). All three are
   measured in cells or in aspect ratio.
2. **[V]** No source read here claims nesting reduces inverted cells, improves orthogonality or
   improves skewness (L4). GridPro's own quality report measures folds and does not attribute them
   to the nest; it attributes unfolding to the relaxer.
3. **[V]** The literature that owns the general technique states that quality *degrades* at the
   terminations of a conformal refinement layer, worst where several terminate together, and names
   thicker layers and balancing as the remedies (L5).
4. **[V]** The one measured iced-aerofoil comparison I reached is a cost, not a benefit: five
   blocks instead of one bought 2.72% more points, 7.59% more CPU and a 20.22% drag difference that
   overset coupling reduced to 9.39% (L6). The benefit comparison GridPro claims is one sentence
   pointing at an unreachable thesis (L7).

**[I] So, to the brief's two live possibilities: the first is the one the sources support.** The
benefit is something the reproduction's metrics do not measure, and the reproduction is not
thereby wrong — §6f's rising inverted count is a real defect of a cast far-field map, and §11b's
fold-when-thin is a real and *predicted* property of a one-level conformal transition. But neither
measurement tests the claim, because the claim is denominated in cells.

---

## 3. What this bears on, for this repo

Stated as inference, because none of these sources was written about this tool. **[I]**

1. **If the method is to be tested, the experiment is cells at a fixed resolution, not inverted
   cells at a fixed `--split`.** The shape of it is given by the sources: fix a resolution
   requirement at the feature (IMR12 fixes "worst aspect ratio < 10"), then count the cells a
   globally refined grid needs against the cells a nested one needs. §6f held `--split` and varied
   the blocking; the claim holds the resolution and varies the strategy.
2. **§11b should be re-run with more than one level before "cannot be thin" is treated as the
   method's limit.** 1:3ⁿ (L3) says a single terminating row is a factor of 3; GridPro's own
   worked example uses five levels. Tchon et al. (L5) say the single-termination corner is the
   worst configuration there is, and that augmenting the layer with its perpendicular neighbours is
   the fix.
3. **A per-interface price exists and this repo has never measured it.** L6 is the only number I
   found for it: ~7.6% CPU for five blocks instead of one, on an iced aerofoil, in a solver that
   exchanges flux across block boundaries. `MESH_MODE 1` welds topologically and point-matched, so
   the geometric part of that price is zero here; the solver part is not this repo's to pay, but it
   is the reason the method is not free in the literature either.
4. **The two cheapest things to take from the iced-aerofoil practice are not the nest.** They are
   the *transition layer* (absorb the surface's jaggedness in one band so the TFI fill never sees
   it — stated against TFI by name, §1) and the *spacing-match criterion* ("grid spacing from
   contiguous blocks will be comparable in size at all block boundaries"), which is a checkable
   rule and which `MbQuality` **already measures — it simply does not SEPARATE it**.
   **[V]**, corrected 2026-11-10: this read "is already positioned to measure as an across-seam
   ratio", which understates a live instrument into an absent one. `MbAdjacentAreaRatio`
   (`540c9df`) keys adjacency by NODE ID rather than by logical `(i, j)` **expressly so that a
   pair straddling a block boundary is measured like any other** — its own header says so — so
   the seam pairs were in the sample all along, reduced into one median with the thousands of
   pairs inside blocks, where they cannot move it (8928 against 192 on the shipped O-grid).
   **Acted on in issue #183**, which reports the figure again over each population; what it cost
   was one integer comparison.

---

## Gaps I could not close, by name

1. **Rajagopalan's University of Virginia master's thesis (May 2003).** This is reference [1] of
   the IMR12 paper and is where *both* quantitative claims live: the proof that the ratios go as
   1:3ⁿ, and the nested-versus-overpopulated Fluent comparison behind "runs much faster but gives
   the same results". It is not in any repository I could reach; UVA's Libra, ProQuest and general
   web search all came back empty. **Nothing in this note rests on its contents**, and L7 states
   the absence rather than paraphrasing the claim.
2. **The journal version, *Engineering with Computers* 21(4), 2005, DOI
   `10.1007/s00366-005-0310-1`.** Closed access (OpenAlex `oa_status: closed`; no repository copy).
   **I did not read it, not even its abstract** — a fetch of the Springer landing page was refused
   in this environment. Everything attributed to Rajagopalan & Eiseman here is from the IMR12
   conference paper, which Semantic Scholar lists as the green OA copy of the same work; I did not
   verify that the two texts agree.
3. **The GridPro TIL manual**, reference [2] of IMR12 and the reference the FAQ gives for `clu`,
   `mildclu` and every TIL answer. Behind the same HubSpot form as the GUI manual, and the Wayback
   CDX index has no capture of it under `sp.gridpro.com/docs`. So I have no primary statement of
   the nest's TIL-level syntax or of the component structure the IMR12 paper says the manual uses
   to illustrate nesting.
4. **Hauser, Eiseman, Xia & Cheng, "Parallel Multi-Block Structured Grids", Handbook of Grid
   Generation ch. 12** — IMR12's reference [3] for the statement that "nested refinement can be
   looked at as a generalization of a structure called the clamp". The Handbook is not
   open-access and **I did not read that chapter**; the clamp/collar quotation this repo already
   holds comes from the 1995 NASA paper, not from here.
5. **A published nested-versus-globally-refined comparison on an AEROFOIL.** I found none. L7's is
   on a wavy wall and is unquantified in the paper; L6's is a block-count comparison at constant
   density, not a nesting comparison. If one exists I did not find it.
6. **Candidate framing (c) from the brief — "keeping the first-cell height uniform along a wall
   when surface curvature varies" — is NOT stated by any source I read as a purpose of nesting.**
   What I found adjacent to it is a different claim: Chi et al.'s thickness criterion is about
   spacings being comparable **across a block boundary**, and SmaggIce's viscous sublayer is about
   "a very dense mesh near the no-slip boundary with firm control". Neither is the brief's
   sentence, and I did not find a source that states it.
7. **Whether GridPro's `nest` and the pillowing family are the same operation.** The IMR12 abstract
   says "conformal adaptive refinement of hex meshes" and cites Tchon et al.'s conformal-refinement
   paper as future-work material **[V]**, and the two produce the same valence-3 substitution, but
   **no source I read says they are the same thing**, and §L5's transfer to §11b is **[I]**, not
   **[V]**.
8. **The 3-refinement over-refinement figure.** Tong & Zhang (arXiv 2512.14862v2, 2025) state that
   previous 3-refinement techniques "severely over-refin[e] grids **by factors of ten to one
   hundred**" **[V]**, which would be a cost figure for the 1:3ⁿ family. I am **not** carrying it
   into the argument: their setting is an adaptive Cartesian octree with balancing conditions, not
   a hand-declared block topology, and I could not establish that the figure transfers.
9. **The two GridPro videos themselves** are unchanged from
   `nesting-blocks-at-a-complicated-leading-edge.md` §5: still no transcript, still two content
   frames each, still a dead geometry download. I did not re-attempt any of them.

---

## Sources

Primary, read by me:

- **GridPro, *WS GUI Manual*, Version 1.0, Program Development Corporation, 24 September 2014** —
  Internet Archive capture `20150505181147` of `http://sp.gridpro.com/docs/WS_GUI_Manual.pdf`,
  fetched by `curl` with the `id_` raw-content form, extracted with `pdftotext -layout`. Sections
  read and quoted: **§4.8 Topology Optimization Utilities**, **§4.8.1 Density**, **§4.8.2 Nest**
  (Forward Nest, Area Nest, Topology Densifier, Reverse nest, and the four numbered requirements),
  **§4.8.3 Compact enrichment**, **§4.9 Surface Assignment Utilities**, **§4.10.4 Ribbon nest**,
  **§5.5** (the Folds / Aspect ratio / Skewness / Warpage definitions). Note the version drift: the
  FAQ cites "Section 4.9.2 in the WS GUI manual" for `nest`, and in this 2014 v1.0 the same text is
  **§4.8.2**.
- **GridPro, *Frequently Asked Questions*** — Internet Archive capture `20170918042045` of
  `http://sp.gridpro.com/docs/FAQ's.pdf`. Answers read, by their
  identifiers: **T37** (what Nest is for), **S24** (Ribbon nest), **G52** (`reverse_nest` for
  far-field coarsening), **G53** (`Enrich`), **G54** (nest as adaptive refinement at topology
  level). `cell-size-range-within-a-block.md` §L4 already holds the substance of T37, G52 and G53
  without naming them; S24 and G54 are new here, and the identifiers are recorded so the next
  reader does not re-fetch the PDF to find them.
- **Rajagopalan, K. & Eiseman, P. R., *Automatic Nested Refinement — A Technique for the Generation
  of High Quality Multi-Block Structured Grids for Multi-Scale Problems Using GridPro*, 12th
  International Meshing Roundtable, 2003**, 13 pp. — Internet Archive capture of
  `http://www.imr.sandia.gov/papers/imr12/rajagopalan03.pdf` (the live `imr.sandia.gov` path returns
  a stub). Identified via the Semantic Scholar graph API entry for DOI
  `10.1007/s00366-005-0310-1`, which lists this as the paper's green OA copy. Sections read:
  Abstract, §1 Introduction, §2 GridPro's topological paradigm, §3 The need for nested refinement,
  §4 Automatic nested refinement, §5 Implementation of nest, §6 Applications (Oahu; wavy tube),
  §7 Conclusion, References.
- **Tchon, K.-F., Dompierre, J. & Camarero, R., *Conformal Refinement of All-Quadrilateral and
  All-Hexahedral Meshes According to an Anisotropic Metric*, 11th International Meshing Roundtable,
  2002** (CERCA report R2002) — Internet Archive capture of
  `http://www.imr.sandia.gov/papers/imr11/tchon.pdf`. Sections read: Abstract, §1 Introduction,
  §2 Conformal refinement primitive, §4 the algorithm's five steps and the quality-mitigation
  paragraph, the 3-D test-case discussion, §7 Conclusion.
- **Chi, X., Zhu, B., Shih, T. I-P., Slater, J. W., Addy, H. E. & Choo, Y. K., *Computing
  Aerodynamic Performance of a 2D Iced Airfoil: Blocking Topology and Grid Generation*,
  AIAA-2002-0381** — https://ntrs.nasa.gov/api/citations/20030007845/downloads/20030007845.pdf .
  A scan; every quotation above is **OCR-reconstructed** and marked. Sections read: Abstract,
  Introduction, Grid Generation Issues, the single-block method, Blocking Topology for Multi-Block
  Grids, Results (Tables 1 and 2, validation, convergence), Summary.
- **Choo, Y. K. & Slater, J. W., *Modeling and Grid Generation of Iced Airfoils*, 8th International
  Conference on Numerical Grid Generation in Computational Field Simulations, Honolulu, June 2002**
  (NTRS 20020071136) — https://ntrs.nasa.gov/api/citations/20020071136/downloads/20020071136.pdf .
  Also a scan; **OCR-reconstructed** and marked. Source of the 7.59% / 2.72% / 4.74% figures and of
  the C_l / C_d table.
- **Kreeger, R. E., Baez, M., Braun, D. C., Schilling, H. W. & Vickerman, M. B., *SmaggIce 2.0:
  Additional Capabilities for Interactive Grid Generation of Iced Airfoils*, NASA/TM—2008-214829 /
  AIAA-2007-0502** — https://ntrs.nasa.gov/api/citations/20080010685/downloads/20080010685.pdf .
  Digital text, not a scan. Sections read: Abstract, §I, §II.A–B (domain decomposition, the viscous
  sublayer block, near-field radial cuts, the overset handoff), §II.C (multi-element blocking),
  References.

Consulted and not used, or used only as labelled:

- **Tong, H. & Zhang, Y. J., *Element-Saving Hexahedral 3-Refinement Templates*, arXiv
  2512.14862v2, 2025** — read; its over-refinement figure is quoted only inside Gap 8, with the
  reason it is not carried into the argument.
- **Sandia CUBIT 15.7 help, *Mesh Pillowing*** — read via WebFetch; corroborates the name and the
  purpose of pillowing but adds nothing the IMR11 paper does not say better, so nothing rests on it.
- **NLR TP 96338, *Multiblock grid generation, Part 11: Multiblock aspects*** — downloaded and
  searched; it contains no statement about local refinement, aspect ratio or propagation, so it is
  not cited above. A second NLR report from the same search downloaded corrupt (`Invalid XRef`) and
  was abandoned.
- **Vickerman et al., *SmaggIce: Surface Modeling and Grid Generation for Iced Airfoils — Phase 1
  Results*, AIAA-2000-0235** (NTRS 20000025235) — downloaded and skimmed; superseded for this
  question by the 2008 TM and not quoted.

Tried and could not get:

- **`link.springer.com/article/10.1007/s00366-005-0310-1`** — a direct fetch was refused in this
  environment; the DOI is closed access and no repository copy exists. The abstract was **not**
  read. Metadata (title, authors, journal, year) is from the Crossref and OpenAlex APIs.
- **`citeseerx.ist.psu.edu` `10.1.1.79.8873`**, both the modern and legacy PDF URLs — HTML stubs,
  no PDF.
- **Rajagopalan's UVA master's thesis (2003)** — not found in any repository, see Gap 1.
- **`imr.sandia.gov` live** — returns a 199-byte stub for both IMR11 and IMR12 paper paths; the
  Internet Archive served both.
- **`d.lib.msu.edu/etd/33803`** — the `OBJ/download` endpoint returned a 2.6 KB HTML page, not the
  document.

In this repo, read for overlap and deliberately not restated:

- `docs/research/nesting-blocks-at-a-complicated-leading-edge.md` — §1–§3b (the two videos, the
  "forward nest creates a local nesting (loopback structure)" caption, the 421 / 96,768 article
  figures), §5 (what could not be verified), §6f and §11 (the measurements §0 quotes), §11a (the
  conformality step). **Not edited.**
- `docs/research/gridpro-blocking-method.md` — §2c (the blog's cocoon / loop / nesting paragraph),
  §3 (the airfoil tutorial), the Sources section's archive URLs, which is where this note's two
  GridPro captures came from. **Not edited.**
- `docs/research/cell-size-range-within-a-block.md` — §L4 and §3 (the FAQ's `nest` /
  `reverse_nest` / `Enrich` wording and Eiseman's clamp/collar), §4 (the cost of overset and
  patched interfaces).
- `docs/research/where-a-block-corner-sits-on-its-ring.md` — §3 (GridPro's corner as an initial
  guess, and the relaxation), which is what L4's reading of IMR12 figure 4 rests against; and its
  house style, which this note copies.
