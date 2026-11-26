# This repo's 2-D aerofoil C-grid, measured against the GridPro samples

**A RESEARCH NOTE, like the others beside it.** Not `.claude/rules/*.md` (what the rule is), not
`docs/design_notes/` (why a shipped rule was chosen). It takes one mesh this repo actually
produces, puts it beside the published GridPro aerofoil grids collected in
`gridpro-mesh-samples/`, and says what is the same and what is not. Nothing here is binding; no
rule, gate, test or source file was changed to write it. Run and measured 2026-11-25.

**What was asked.** Draw a 2-D aerofoil mesh with this repo's mesher and compare it with the
meshes in `gridpro-mesh-samples/`.

**Markers.** **[V]** = measured by me in this session, or read off a figure I opened myself.
**[I]** = my own inference from a **[V]** fact.

---

## 0. The mesh

```bash
HYBMESH_MB_QUALITY=1 ./run.sh -conf config/multiblock_cgrid.dat
```

A shipped case: `MESH_MODE 1`, the four-block C-grid around a NACA 0012 declared in
`examples/topology/cgrid_naca0012.json`. Nothing was tuned for this comparison. **[V]**

| | |
|---|---|
| blocks | **4** — `b_upper`, `b_lower`, `b_wake_up`, `b_wake_lo` |
| nodes per block | **49x41**, **49x41**, **25x41**, **25x41** (read off the topology's own `count` fields) |
| structured quads | **5,760** (exported split into 11,520 triangles) |
| vertices | 5,920 |
| aerofoil wall nodes | **96** (49 per side, sharing the leading- and trailing-edge corners) |
| far field | **10 c** upstream, **19 c** downstream, **10 c** lateral |
| first wall cell | 1.000e-3 c, honoured to **0.05%** |
| inverted cells | **0** |
| non-orthogonality | max **29.9 deg**, mean **3.8 deg** |

Figures: `our-cgrid-vs-gridpro/ours_full.png`, `our-cgrid-vs-gridpro/ours_near.png`, `our-cgrid-vs-gridpro/ours_le.png`, `our-cgrid-vs-gridpro/ours_wake.png`.
**[V]** — all four rendered by `tools/scripts/view_mesh_vtk.py` from the run above, coloured by
block.

---

## 1. The one like-for-like comparison in the whole sample set **[V]**

**Entry 72** (NASA TM-106356 / ICOMP-93-34 / AIAA-93-2380), Figure 2, is a NACA 0012 in a linear
cascade and is **the only AEROFOIL figure in these samples that prints a per-block node count on
the picture**. It is therefore the only one that can be compared number to number rather than by
eye. (One other sample prints per-block counts — entry 18's nozzle, 81x81, 142x81, 241x211 and a
19x19 actuator block — but it is not an aerofoil. Both are listed at the end of
`gridpro-mesh-samples/FIGURE-INDEX.md`.)

| | this repo, `multiblock_cgrid` | GridPro, entry 72 Fig. 2 |
|---|---|---|
| aerofoil | NACA 0012 | NACA 0012 |
| blocks | **4** | **3** |
| nodes per block | 49x41, 49x41, 25x41, 25x41 | **49x41, 57x41, 49x41** |
| structured quads | **5,760** | **6,080** (48x40 + 56x40 + 48x40) |
| what the blocks do | two wall blocks split at the leading edge, two wake blocks split by a `cut` | three blocks that **merge into a single-block C-grid** |
| block seams drawn | coloured by block | bold lines over thin grid lines |

**The sizes land on top of each other.** 49x41 is the same wall block, and 5,760 against 6,080
quads is a 5% difference. **[V]** Two meshers, 32 years apart, reached for the same resolution
for the same aerofoil. **[I]**

**The topologies do not.** Entry 72 declares three blocks and then **merges them into one**, so
what the solver reads is a single-block C-grid with no interior seam at all. This repo declares
four and welds them topologically, so four blocks reach the solver. **[V]** on both. Entry 72's
caption states the merge outright: *"merging of block creates a single-block C-grid."*

---

## 2. The leading edge, where the two differ most **[V]**

Put `our-cgrid-vs-gridpro/ours_le.png` beside `gridpro-mesh-samples/entry36-mansouri2016-fig1-6-typical-form-grid-discontinuities-singularities-around.png`
(entry 36, *"A Typical Form of Grid Discontinuity/Singularities around the Leading Edge of NACA
0012 Airfoil for a Multi-Block Structured Grid"*).

- **GridPro wraps the nose in its own ring of blocks.** The figure shows several blocks meeting
  around the leading edge, their grid lines following the curvature all the way round, and the
  block corners placed where the singularities are wanted. **[V]**
- **This repo's C-grid puts one straight radial line out of the stagnation point** — the `r_le`
  interface — and the upper and lower wall blocks meet along it. There is no leading-edge block.
  **[V]**

**A reading I had to correct.** Looking at `our-cgrid-vs-gridpro/ours_le.png` I first wrote that the nose was
under-resolved chordwise. **Measuring it says otherwise**: the first surface cell at the nose is
**0.00498 c**, the NACA 0012 leading-edge radius is **0.01587 c**, so the first cell is
**0.31 r_LE** and **five surface nodes sit within one leading-edge radius**. **[V]** The nose is
resolved; what the picture actually shows is wall-normal-to-chordwise *stretch*, which is a
different complaint, and one the numbers in Section 3 carry properly. The lesson is the one this
repo keeps relearning: a figure is evidence of shape, not of size.

---

## 3. Spacing and growth, against the bounds GridPro users publish **[V]**

The census note's section 4b lists every quality figure found in the GridPro literature. Three of
them are directly comparable to something this run measures, and one is not — which matters more
than the agreement.

| quantity | this repo | published GridPro practice | source |
|---|---|---|---|
| surface spacing growth ratio along the wall | **1.14** (first ten cells from the nose: 1.141, 1.144, 1.141, 1.138, 1.134, ...) | **1.1** expansion ratio; **1.2** stretching ratio | entry 1 (Matthews & Key 2025); entries 8, 24, 25 |
| cells in the boundary layer | not reported by this mesher | **> 10** | entry 1 |
| first cell / y+ | 1.0e-3 c, geometric only (no flow) | y+ < 1 near-universally | entries 1-51, 40 of 70 |
| **adjacent-cell AREA ratio** | median **1.22**, p95 **1.40**, max **2.28** | **no GridPro paper publishes this quantity** | — |

**Where it agrees.** The 1-D surface growth ratio of **1.14** sits inside the 1.1-1.2 band that
every GridPro paper reporting one uses. **[V]**

**Where it cannot be compared, and must not be.** This mesher's headline shape numbers are a
**quad midline ratio** (median 4.83, p95 148, max 3,148) and an **adjacent-cell area ratio**. A
GridPro paper's "stretching ratio 1.2" is a **one-dimensional spacing growth**, and an area ratio
of 2.28 is roughly a 1-D ratio of 1.5, not of 2.28. **Quoting 2.28 against 1.2 would be comparing
an area with a length.** **[I]** Only the surface growth ratio row above is a like-for-like
comparison; the other rows are stated so the gap is visible, not so the numbers can be subtracted.

**One number with no GridPro counterpart at all, and it is this repo's strongest.** The size jump
**across block seams** is median **1.003**, p95 **1.009**, max **1.055**, against **1.219 / 1.398
/ 2.276** *inside* blocks. **[V]** The seams are the smoothest part of the mesh. No paper in
either note publishes a seam-local figure, so there is nothing to compare it to — the census note
found that what gets published is a bound or a convergence index, never a distribution. **[I]**

---

## 4. The defect this comparison found **[V]**

`our-cgrid-vs-gridpro/ours_wake.png` shows it. The quality report puts the worst cells in the wake blocks —
`b_wake_up` and `b_wake_lo` carry a quad midline ratio of median **10.1**, p95 **610**, max
**3,148**, against **3.69 / 48.3 / 211** in the two wall blocks. **[V]**

The cause is visible in the picture: **the C-grid carries the aerofoil's own wall clustering
along the wake cut all the way to the outlet at 19 chords**, while the streamwise spacing out
there grows to roughly half a chord. A cell 1e-3 tall and 0.5 long is the max 3,148. **[I]** from
the **[V]** figure and the per-block table. There is no wall in the wake, so nothing asks for
that height past the near wake.

**What the samples show other people doing about it**, as options rather than a recommendation:

- **Entry 72 merges the blocks away** — three blocks become one C-grid, so the wake is not a
  separate block whose radial count is inherited from the wall block. **[V]**
- **Entry 13** (Rigby & Steinthorsson, VKI LS 1999-2000) merges **282 elemental blocks into 22**
  and draws the before and after, Figure 9b beside 9c; Figure 3 draws the merge stage by stage.
  **[V]** It is the only published picture in either note of what merging does to a grid.
- **The other note's section 1** (Stern *et al.* 2012) ends grid lines on interior seams so the
  count *reduces* away from the refined region — "nested topological refinement", drawn. That is
  the opposite move to this repo's `reducing_stack`, which halves on a concentric ring; theirs
  tiles the refinement where the wake is. **[V]** in that note.

None of these is proposed here. This note measures; what to do is a ticket's decision.

---

## 4b. The partition, drawn the way the quilt sections draw one **[V]**

`our-cgrid-vs-gridpro/partition.png` (regenerate with
`our-cgrid-vs-gridpro/plot_cgrid_partition.py`, whose docstring carries the two-run recipe and
the restore line). The convention is borrowed unchanged from
`gridpro-blocking-method/plot_quilt_vs_gridpro.py` — **block fill by colour, the grid pale, the
partition heavy** — which is GridPro's own convention in its published figures. Every number in
the caption is derived from the mesh: 4 blocks, 5,760 quads as 960 + 1,920 + 1,920 + 960, 144
seam edges, and each panel's span from the point bounds.

**Two things had to be done differently, and both are stated in the script rather than left to
be noticed.** The partition is measured by `seam_edges`, which by its own contract skips any
cell that is not a quad — so against the shipped triangles it returns **zero** seam edges and
would draw a mesh with no partition at all. The figure therefore comes from a second run with
`MB_SPLIT_QUADS 0`, the diagnostic the config banner itself names, and that run **overwrites the
shipped mesh**, so the recipe restores it. And `tab20` is strided by two: it is ten colour pairs,
a saturated member then a pale one, which is harmless for a 54-to-82-block quilt and exactly
wrong for four blocks, where the upper and lower wall blocks would read as one block lit
differently.

**What the drawing shows that the earlier renders did not.** Stripped to the partition, this
mesh's entire block structure is **a cross**: one horizontal cut along y = 0 (the stagnation line
forward of the body, the wake cut aft of it) and one vertical cut at x = 1 (the trailing-edge
radial), each running the full depth of the domain. Four quadrants, three straight lines. **[V]**
Nothing in the partition follows the body, and nothing changes between one chord and nineteen.
Put beside the sample set's aerofoil partitions — entry 36's blocks wrapping the nose, entry 72's
O-grid inside an H-grid, entry 6's 97 — the comparison is not about resolution at all, which is
where Section 1's agreement sits. **It is that those meshes spend blocks on the geometry and this
one spends them on the two cuts a C-grid needs to exist.** **[I]**

Whether that is a deficiency or an economy is not settled here. Four blocks reaching 0 inverted
cells and a 1.003 median seam jump is not an obviously bad trade, and the census found no
published GridPro aerofoil whose block count is as low as four to compare the trade against.

## 5. What the comparison does not establish

1. **One case, one mesher setting.** `config/multiblock_cgrid.dat` as shipped, with
   `MB_SMOOTH_ITERS` at its default 20 — and that run reports *"NOT converged, and PAST ITS
   BEST"*, best residual at sweep 1. The exported mesh is an iterate. **[V]** A different cap
   would give different numbers in Section 3.
2. **No flow was run.** Every number here is geometric. The y+ column is the only place the
   GridPro literature's dominant figure appears, and this repo cannot produce it without a solve.
3. **Entry 72 is one figure.** Its 49x41 is a cascade block with periodic sides, not a C-grid
   wrapping a free-flight aerofoil, so the agreement in Section 1 is an agreement about
   *resolution*, not about *topology*. **[I]**
4. **The exported mesh is triangles.** This mesher fills with structured quads and splits them on
   export, so every rendered figure here shows diagonals that the GridPro figures do not have.
   The quad count, not the cell count, is the comparable number, and Section 1 uses it. **[V]**
