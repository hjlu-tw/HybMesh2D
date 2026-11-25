# What published work that used GridPro actually reports about its mesh

**A RESEARCH NOTE, like the thirteen beside it.** Not `.claude/rules/*.md` (what the rule is),
not `docs/design_notes/` (why a shipped rule was chosen). It is a **census**: one row per
document that used GridPro, saying whether that document reports LOCAL or GLOBAL mesh
information and what the numbers are. Nothing here is binding; **no rule, gate, test or source
file was changed to write it.** Searched, downloaded and drafted 2026-11-25.

**What was asked** (user, in Chinese, paraphrased). Find GridPro-generated meshes of decent
quality. Find PUBLICATIONS that used GridPro — mesh-generation research, CFD research, or any use
at all — and check whether each one reports LOCAL or GLOBAL mesh information. **As many mesh
samples as possible**; breadth is the deliverable.

**What counts as "mesh information" here.** Total cell/node/element count; block count (elemental
blocks, superblocks, surface blocks); per-block or per-region counts; wall-normal layer counts;
first-cell height; y+ (max/avg); growth or expansion ratio; far-field distance in body
diameters/chords/widths; a grid-refinement series with its counts; quality metrics (skewness,
equiangle skew, orthogonality/minimum angle, aspect ratio, Jacobian, determinant, volume ratio,
GCI); spacing distributions; topology descriptions; and whether a mesh/topology FIGURE exists and
what it shows.

**How this differs from the note beside it.** `gridpro-meshes-in-published-cfd.md` (2026-11-12,
§1 re-verified 2026-11-24) asked a narrower question — how practitioners BLOCK and PRESENT a
GridPro mesh from the near field out to the far field — reached **ten** third-party documents with
a visible mesh figure plus two without, and **deliberately excluded vendor-authored material**.
**This note includes vendor-authored work**, because the user asked for "any publication that used
GridPro", and labels it. It also **does not re-mine** those twelve: §3 below cross-references them
and lists only what this session added.

## How to read the markers

- **[V]** verified in a primary source I read myself (the PDF I downloaded, an HTTP response I
  made, an indexer's own API), or measured by me.
- **[I]** my own inference from a **[V]** fact. Stated as reasoning, not as fact.

Those two definitions are copied verbatim from
`nesting-blocks-at-a-complicated-leading-edge.md` and `gridpro-meshes-in-published-cfd.md`.

Two further labels, required by the scope change:

- **[3P]** third-party — no author carries a GridPro / Program Development Company / PDC
  affiliation. Checked against the author block on page 1 of the PDF and, where a DOI existed,
  against the Crossref/OpenAlex author records. **[V]**
- **[V-GP]** vendor-authored or vendor-co-authored. The vendor people named in
  `gridpro-meshes-in-published-cfd.md` §12 are Peter R. Eiseman, Vimalraj Anbumani, Samuel E.
  James, Vijay Sudharshanam, Samuel Ebenezer, with affiliation strings "PDC/GridPro" and "Program
  Development Company"/"Program Development Corp."; Zheming Cheng is added here from the author
  block of entry 57. **[V]**

**Every candidate was `curl`-ed and grepped for `gridpro` (case-insensitive) before it was
recorded.** That is the discipline `gridpro-meshes-in-published-cfd.md` §12c bought the hard way,
and it was applied without exception here: an indexer hit is a lead, not a finding. **[V]**

---

## 0. The result in one block

**70 census entries: 58 NEW here, and the 12 already covered by the note beside this one.**
**[V]** Of the 58 new, **55 are [3P]** and **3 are [V-GP]** (entries 7, 57 and 58; entry 41 is
[3P] but its acknowledgements thank a named GridPro employee for meshing support, which is
flagged in its row). Two of the 58 rows deliberately **group** several reports of the same grid
family — entry 19 covers three Ameri NASA reports and entry 56 covers five LANL annual reports —
so the number of underlying PDFs is larger than 58 and is **not** claimed as a count. **[V]**

**Counting the whole census (70): 49 state a cell/point count, 33 state a block count, 40 state a
y+ or a first-cell height, 17 state a far-field distance in body units, 20 carry a
grid-refinement series, 16 report a named QUALITY metric, and 56 carry a mesh or topology
figure.** **[V]** Each of those seven is re-derived by counting one column of the table below
under the rule stated in §4a, plus a hand count over the other note's §14c; the per-table
breakdown is §4a and must be used rather than these totals if the table changes. The
quality-metric list is §4b — the note beside this one found **exactly one** in its whole search,
so that is the largest single change this census makes.

**Three mesh figures were extracted** (open licence only) into
`docs/research/gridpro-mesh-samples/`, with `PROVENANCE.md` beside them. Everything else is a
pointer. **[V]**

### The census

Sorted richest first within the new entries; the twelve already-covered documents are the last
block and are detailed only in §3. "LOCAL" in the last column means the document reports
something attached to a place in the mesh (per-block counts, first cell, a named feature's
resolution); "GLOBAL" means a whole-mesh aggregate only.

| # | Citation (short) | Label | Application | Cells / points | Blocks | First cell / y+ | Far field | Quality metric | Refinement series | Mesh figure — what it shows | L/G |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Matthews & Key 2025, *IJTPP* 10(1) 5 | [3P] | 3-stage axial compressor (Purdue PAX200) | not stated in what I read | not stated | avg y+ < 1, max < 5; expansion ratio 1.1; >10 cells in BL | internal | **GCI (ASME), skewness, orthogonality, ks+/y+ < 3.6** | yes, GCI table, base/fine | no grid-line figure I found | LOCAL |
| 2 | Luk 2008, OSU MS thesis `osu1224705112` | [3P] | 1-stage HP turbine, flat tip | 2,461,740 (709,900 stator + 1,751,840 rotor) | **31 (11 + 20)** | 1e-5 m; **y+ ≈ 0.38** | internal | **GridPro's own check: block count, cell count, fold count, skewness, warpage, stretching ratio, smoothness, aspect ratio** | no | yes — stator & rotor **topology**, H-O cross-section, blade and tip mesh | LOCAL |
| 3 | Gollan & Ferlemann 2011, AIAA 2011-2254 | [3P] | REST scramjet inlet | 2.3 M Euler → **4.1 M** viscous | **207 elemental → 13 superblocks** | 0.0127 mm; y+ < 2 | internal | "equal cell size and aspect ratio throughout the volume" | 3 levels of grid sequencing | yes (topology/geometry) | LOCAL |
| 4 | Heidmann, Rigby & Ameri 1999, NASA/TM-1999-209078 (99-GT-186) | [3P] | film-cooled turbine vane | not stated in what I read | **2298 → 140** (Method of Weakest Descent) | y+ < 1.0 at first point | internal | full face-matching blocks | no | yes — blade-to-blade multiblock grid + LE zoom | LOCAL |
| 5 | Garg 2000, NASA/CR-2000-210510 | [3P] | VKI rotor, shower-head holes | **106,496**; 128 cells in the hole exit | **162 → 13** | y+ < 1 | 80% Cax up / 70% Cax down | — | 2 grids (one with twice the cells) | yes — LE grid + two hole insets | LOCAL |
| 6 | **Vatsa, Sanetrik & Parlette 1995, NASA CP-3291** | [3P] | **2-D three-element high-lift aerofoil** | not stated | **97** | — | — | "smooth and nearly orthogonal, except near singular points" | — | **YES — the 97-block grid, block seams drawn HEAVY** (extracted) | LOCAL |
| 7 | **Eiseman 1995, NASA CP-3291** | **[V-GP]** | **2-D aerofoil in ground effect**; fuel tank; cloth fibres | not stated | not stated | — | wake cut runs to the downstream boundary | "near orthogonality, smoothness, low warpage, curvature clustering" | — | **YES — global view + near-field zoom, "clamps" and "collar"** (extracted) | LOCAL |
| 8 | **Repko, Nix, Uysal & Sisler 2016, *JFCMV* 4(1) 13-29** | [3P] | multi-hole film cooling | **2.5 M** (4.5 M unsteady, Star-CCM+) | ~30 drawn | y+ < 1.0, nominally **0.1**; **stretching ratio 1.2** | 10 d_m above; 3 d_m wide | — | **1.2 / 2.5 / 3.0 M** | **YES — each block a DIFFERENT COLOUR** (extracted) | LOCAL |
| 9 | Ramesh, Edwards *et al.* 2015, AIAA 2015-0356 | [3P] | dual-mode scramjet, LES | **93 M** | **13,369** | 5 µm on all solid surfaces | internal | "very high aspect ratio cells" in the dump region | no | domain figure, not grid lines | LOCAL |
| 10 | Nielsen, Edwards & Chelliah 2021, *AIAA J* 59(6), LA-UR-19-29624 | [3P] | premixed ethylene dual-mode scramjet | not read | **25,278** | **5e-6 m wall-normal, stretch ratio 1.3** | internal | — | no | yes — body-fitted grid around insert/cavity (Fig. 3) | LOCAL |
| 11 | Schwing 2013, NTRS 20120017946 | [3P] | capsule aerodynamics (US3D, 05-CA tunnel) | **18,217,949 points / 18,113,216 cells** | not stated | y+ < 1 on entire geometry | **30 diameters** | — | no | presentation; grid panel not rendered by me | LOCAL |
| 12 | Papadopoulos *et al.* 2001, AIAA 2001-3067 | [3P] | Shuttle Orbiter contingency abort | 2.2 M points + **1.4 M wake** | **365 non-merged** | — | — | — | no | yes — "(a) topological morphology, (b) 365 non-merged blocks" | LOCAL |
| 13 | Rigby & Steinthorsson 2000, VKI LS 1999-2000 | [3P] | ribbed/bleed coolant passage | not stated | **282 → 22**; a merge study 124 → 992 / 1776 / 7936 | y+ named as the sizing criterion | internal | — | no | **yes — Fig. 9b block boundaries before merge, 9c after** | LOCAL |
| 14 | Oswald *et al.* 2005, DLR-ONERA Pre-X | [3P] | re-entry demonstrator | 1,044,992 (M25); **1,428,992** (M17.75); ~700,000 final | **376** and **548** | y+ < 1 | — | — | **3 grid levels, space-convergence** | yes — symmetry-plane grid, surface grid, body-flap zoom | LOCAL |
| 15 | Gaffney & Norris 2008, AIAA 2008-3703 | [3P] | Mach-3 TBCC nozzle | **8,990,720** (coarsened 1,123,840 and 140,480) | **275** (for load balancing) | y+ < 0.8 | internal | — | **3 levels** | not rendered by me | LOCAL |
| 16 | Crivellini, Golubev, Mankbadi, Scott, Hixon *et al.* 2002, AIAA 2002-2535 | [3P] | **2-D Joukowski aerofoil, gust response** | **600 x 240** and **591 x 238** | **single block** | algebraic clustering Δn = 0.01 normal, clustered at TE | **≥ 10 chords each direction** | — | prior density + domain-size sensitivity study (ref. 4) | **no mesh figure** (Fig. 1 is a speedup plot) | LOCAL |
| 17 | Allampalli 2010, U. Toledo PhD | [3P] | **NACA 0012**, 2-D cylinder, stator passage | Grid 3 = **51,465 points** | **95** (Grid 3) | — | **C-H topology, ≥ 10 chords** | — | 2 grids for the NACA 0012 | yes — single-block O-grid around a 2-D cylinder; block-cut diagrams | LOCAL |
| 18 | Brown 2010, U. Akron PhD | [3P] | LAFPA plasma actuator, jet | ~1.9 M (DES), ~3 M (2-D LES), "million points" 3-D | **506** (2-D), **924** (3-D) | — | 50 nozzle diameters (acoustic far field) | full face block-to-block matching forced the block count | no | **yes — Fig. 5.5 the TOPOLOGY with internal surfaces** | LOCAL |
| 19 | Ameri 2012, NASA/CR-2012-217434 and -217435 (GT2012-69591); Ameri 2012 NTRS 20120009201 | [3P] | variable-speed power turbine, flat plate | 610,000 / 608,000 points; **2,313,984** very fine; 25,000 (2-D); 34,000 (stacked 81x) | **100** (GE2), **16** (flat plate, each 1664-point array) | y+ ≈ 1 | 1 Cax up, 1.5 Cax down | — | **yes, several levels; "grid convergence has been [verified]"** | yes — 2-D grid, LE zoom, midspan, full 3-D, very fine 3-D | LOCAL |
| 20 | Garg & Ameri 2001, NASA/CR-2001-210810 (2001-GT-0165) | [3P] | transonic turbine blade | **55,296** viscous; 112 cells around the blade | **28 → 5** | avg y+ **0.26**, "less than half" | 1 Cax up, 0.8 Cax down | — | no | yes — spanwise section of the multi-block viscous grid | LOCAL |
| 21 | Rigby *et al.* 1998, 98-GT-329 / NASA/TM-1999-208501 | [3P] | rotating ribbed passage, 180° turn | **1,489,920** | merged to **64** | largest y+ at a cell centre limited to **< 1.25** | internal | "significant improvement in grid orthogonality" by not wrapping outer corners | no | yes — grid in the x=0 and y=0 planes | LOCAL |
| 22 | Ameri 2002, NASA/CR-2002-211515 (GT-2002-30211) | [3P] | 180° turn channel | **340,000 / 523,000 / 1,060,000** | not stated | avg y+ ≈ 1; stretching ratio stated | internal | — | **yes, 3 grids** | **yes — Fig. 2 (a) topology, (b)(c)(d) the three grids, (e) y+ distribution** | LOCAL |
| 23 | Garg 2002, NASA/CR-2002-211689 (GT-2002-30229) | [3P] | LPT separation control, vortex-generator jets | **160,128** viscous from **92,928** inviscid; **224 cells per hole exit** | not stated | y+ < 0.5 | 1 Cax up, 0.8 Cax down | **ratio of two adjacent grid sizes kept within 0.8–1.25** | no | yes — spanwise section of the multi-block grid | LOCAL |
| 24 | Heidmann 2008, NASA/TM-2008-215209 (GT2008-50845) | [3P] | anti-vortex film cooling | **~2.5 M** per case, ~300,000 after one multigrid coarsening | not stated | y+ < 1.0; **stretching ratios < 1.2** | 7 d downstream | — | one coarsening level | not rendered by me | LOCAL |
| 25 | Roy 2005, NASA final report NNC04GA21G | [3P] | film cooling over a GE flat plate (DES) | **4 M** (converted to one unstructured block) | GridPro multiblock, then merged to a single block | y+ < 1.0 everywhere; **stretching ratios < 1.2** | — | — | no | not rendered by me | LOCAL |
| 26 | Ameri 2001, NASA/CR-2001-210764 (2001-GT-0156) | [3P] | blade tip, mean-camberline strip | **1.2 M** sharp tip, **1.4 M**, **1.8 M** with strip | not stated | y+ stated as the first-cell criterion | internal | — | 3 geometries, not a refinement series | yes — blade surface, grid, strip detail (Fig. 3a-e) | LOCAL |
| 27 | Steinthorsson 1996, AIAA 96-0621 / NASA CR-198539 | [3P] | branched duct with pin array | **~2 M** | **283** | — | internal | "smooth, nearly orthogonal everywhere" | no | yes — Fig. 3 multiblock grid for the branched duct | LOCAL |
| 28 | Steinthorsson & Modiano 1995, NASA CP-3291 | [3P] | branched duct, pin array, NACA 0012 | not stated | not stated | — | — | "grid quality (smoothness and orthogonality) degrades" if a block moves too far | — | yes — Fig. 2 **topology** of the multiblock system; Fig. 3 centre region | LOCAL |
| 29 | Ameri 2009, NASA/CR-2010-216235 (AIAA 2009-1060) | [3P] | NASA Rotor 37 | **~1.8 M** | not stated | — | internal | — | **explicitly none** — "only one grid resolution was tried" | yes — two views + tip close-up | GLOBAL |
| 30 | Shyam 2009, OSU PhD `osu1258931807` | [3P] | HP turbine stage (unsteady), flat plate | **2,461,740** (1,751,840 rotor); 156 radial x 101 rotor-to-rotor | **20 rotor + 11 stator**; **19** for the flat plate | y+ < 1; y+ ≈ 1 on the plate | internal | H-O-H chosen for "more control over the grid quality" | **explicitly none** — "no refinement study was deemed necessary" | yes — flat-plate mesh, **block structure**, 35° cooling hole, rotor grid | LOCAL |
| 31 | OSU MS thesis 2009 `osu1230064860` (CHT on a turbine blade) | [3P] | C3X vane, conjugate heat transfer | **~0.4 M** (75% hot gas path) | **440** | y+ ≤ 1 | internal | "orthogonality maintained as much as possible" | no | yes — Fig. 4.2 C3X grid | LOCAL |
| 32 | Shankara 2009, OSU MS thesis `osu1262290700` | [3P] | particulate deposition on turbine vanes | 746,554 / 1,260,184 (tet comparators); hex grid via GridPro | multiple "regions of interest" | y+ **15-40** (wall-function model), and a fine mesh with y+ < 1 | internal | "**skewness in the grid was kept to a minimum**" | coarse mesh found inadequate | yes — cut-section of the hexahedral volume mesh (Fig. 6.8), VKI blade grid (7.1) | LOCAL |
| 33 | Ayyalasomayajula 2003, U. Cincinnati MS `ucin1054757181` | [3P] | LPT linear cascade, cylinder | **750,000 points** (cylinder) | **12** (O- and H- dual topology) | non-uniform wall-normal clustering; min near-wall spacing stated | — | "H-grid alone increases the skewness near the [LE]" | no | yes — 12-block cascade grid, enlarged mid-blade view, O-grid around a cylinder | LOCAL |
| 34 | Singh 2005, U. Cincinnati MS `ucin1109095348` | [3P] | LPT cascade, separated flow | **2 M points**, 32 spanwise planes | **12** | — | — | "orthogonal at boundaries, almost orthogonal within the domain" | no | yes — Fig. 4.1(a) 12-block grid, (b) enlarged | LOCAL |
| 35 | Kasliwal 2006, U. Cincinnati MS `ucin1141413192` | [3P] | cylinder (Re_D 3900) + LPT cascade | **3.9 M points** (48 spanwise); 2 M for the cascade | **8** (cylinder), **24** (partitioned) | ~70% of points in the near-wall region | **75 diameters** | "good quality near-orthogonal multi-block" | **yes — coarse vs fine profiles at three stations** | yes — Fig. 1 the 8-block grid; Fig. 16 the fine grid's **block layout**; Fig. 18 grid over vorticity | LOCAL |
| 36 | Mansouri 2016, U. Toledo PhD `toledo1463099661` | [3P] | block-interface treatment for CAA | 21^3 per block; a 201^2 case; 41^3-point blocks | a quarter patterned 3x; **eight 3- and 5-way singularities** | — | domains 0.5 x 0.45 and 3.0 x 2.5 | the subject of the thesis is accuracy ACROSS block interfaces and at singularities | block sizes 11^2 … 401^2 | **yes — grids built in GridPro specifically to carry 3- and 5-way singular points** | LOCAL |
| 37 | Ingraham 2015, U. Toledo PhD `toledo1430491745` | [3P] | verification of unsteady PDE solvers | 41^3 points | **5 blocks, 2 singular points** | — | cube -0.5…0.5 | "singular grid convergence rate is markedly [lower]" | **yes — a formal grid-refinement study, the thesis's subject** | yes — the test-case grid, and a multiblock grid **coloured by block** (a different, non-GridPro grid) | LOCAL |
| 38 | Heminger 2010, U. Toledo MS `toledo1272550725` | [3P] | dynamic grid motion, CAA | **327,184 points** | **104** | — | — | "attempt to remain orthogonal to the surfaces" | no | yes — Figs. 6-2…6-5 images of the grid | LOCAL |
| 39 | Baltazar, Rijpkema, Falcão de Campos & Bosschers 2018, *JMSE* 6(1) 27 | [3P] | ducted propeller, open water | **1.1 → 26.8 M**, five grids | not stated | max y+ < 1 on all five | **5 propeller diameters** all directions | "nearly-geometrically similar" grids | **yes — 5-grid series, 12.9 M within 1%** | yes — Fig. 4 surface grids | LOCAL |
| 40 | Maljaars, Bronswijk, Windt, Grasso & Kaminski 2018, *JMSE* 6(2) 51 | [3P] | flexible composite propeller (FSI) | not stated in what I read | "a standard block topology developed at MARIN" | y+ < 1, no wall functions | **3 D diameter x 5 D length** | "gives good quality grids, **most of the time**"; high skew made it cumbersome | no | yes — Fig. 1 domain and grid | LOCAL |
| 41 | Harries & Uharek 2021, *JMSE* 9(10) 1069 | [3P]* | catamaran hull optimisation | **460,000 / 1.5 M / 3.7 M** per demi-hull | "initial topology (block structure)" fixed, re-run per variant | — | — | "resulting grids are all of high quality … topology practically identical" | **yes — 3-grid convergence study (Table 5)** | **yes — Fig. 13 the bow-region mesh for two hulls overlaid, showing the far field UNCHANGED** | LOCAL |
| 42 | Camci, Averbach & Town 2019, *Aerospace* 6(5) 60 | [3P] | turbine rim-seal cavity, purge flow | not stated in what I read | multiblock | — | internal | "uses **automated subroutines to improve mesh quality**" | no | not rendered by me | GLOBAL |
| 43 | Wu *et al.* 2021, *Appl. Sci.* 11(17) 8180 | [3P] | double-blade centrifugal pump | **940,000**; head insensitive beyond ~3 M | not stated | smooth-wall | internal | "the quality of the grid directly affects the accuracy" | **yes — Fig. 3 grid independence** | yes — Fig. 2 the computational grid | GLOBAL |
| 44 | Ledermann *et al.* 2025, *CEAS Space J.* 18, 209-234 | [3P] | destructive re-entry (MISTRAL/Pampero) | **> 14.5 M** | "massively multi-blocked" | **first cell 2e-6 m** | — | — | an AMR comparison (…000 → 1,300,000) | yes — Fig. 9 the multi-block mesh | LOCAL |
| 45 | Midani 2024, Aix-Marseille PhD `tel-05248848` | [3P] | atmospheric re-entry + ML | 710,400; 70,144; 1,359,461; 36,824; **71,343** initial | "input mesh generated by hand with GridPro" | "clustering to improve the quality of the mesh near the wall" | — | the thesis's own octree/AMR is compared against it | yes, several | yes — octree and input-mesh screenshots | LOCAL |
| 46 | Kroll & Mahesh 2025, *Flow* 5 E2 | [3P] | marine propeller, crashback, water tunnel | not stated in what I read | — | **min wall-normal spacing 0.0017 D, growth ratio 1.01** | tunnel walls modelled | — | no | yes — Fig. 2 cross-section of the domain | LOCAL |
| 47 | McGinn *et al.* 2021, ICLASS 2021 | [3P] | multi-hole GDI injector (ECN Spray G) | **5.5 M** | not stated | **min 5 µm at the needle tip, avg 10 µm, max 65 µm** | — | — | no | yes — Fig. 1(b)(c) domain and mesh detail | LOCAL |
| 48 | Borynyak 2019, *J. Phys. Conf. Ser.* 1382 012004 | [3P] | vortex breakdown, swirling jet (LES) | **4e6** and **1.6e7** | not stated | **y+ ≈ 10** | pipe D=15, honeycomb 10 D | — | no | Fig. 1 domain with velocity field, not grid lines | GLOBAL |
| 49 | Drozda, Baurle & Drummond 2016, NTRS 20160009131 | [3P] | scramjet strut and ramp injectors | not stated in what I read | GridPro near the injector + Pointwise h-blocks | y+ → 1 target; **growth rates 5%-15%** | — | "**grid skewness issues**" named as the reason for a modelling choice | **yes — GCI (Richardson)** | yes — Figs. 5, 6 coarse-grid elements (each drawn cell holds 4x4x4) | LOCAL |
| 50 | Reschke, Pfeiffer & Fasoulas 2020, arXiv 2007.06339 | [3P] | ESA standard pressure probe (DSMC) | not stated | hexahedral, GridPro | — | **≈ 40° cylindrical sector** | — | no | yes — a representative mesh slice (Figs. 4, 5) | LOCAL |
| 51 | Klečková 2019, Univ. of West Bohemia PhD (cs) | [3P] | turbine blade flutter, 2-D cascade | not stated | quadrilateral blocks; "four edges from each interior node, exceptions with three or five" | **y+ in (0.1, 4), average ≈ 1** | periodic boundaries built from blade count 90 at r=1461.9 mm | **skewness (zkosení) defined and used** | no | yes — Fig. 6.4 the **topology** (left) and the wall BL definition (right) | LOCAL |
| 52 | CSME-CFDSC-CSR 2025 WAAM paper, DOI `10.82417/mc39-6943` | [3P] | GMA arc heat source (WAAM) | **9,000** | not stated | — | — | "**GridPro … minimizes skewness and provides a high-quality structured mesh**" | no | Fig. 1 domain with boundary types | GLOBAL |
| 53 | Hauser, Ludewig, Gollnick & Winkelmann 1999, CACR-170 / AIAA 99-549 | [3P] | X-33, solver (JParNSS) | 48,000 and 192,000 | **38**, **148**, 10, 3 | — | — | — | no | **yes — Fig. 1 a multiblock grid for the X-33, one block per thread** | LOCAL |
| 54 | Zhao, Knight, Taskinoglu & Jovanovic 2004, Springer LNCS | [3P] | S-shaped subsonic diffuser, optimisation loop | not stated | GridPro is the meshing stage of an automated CF-SQP loop | — | internal | — | no | not rendered by me | GLOBAL |
| 55 | DOE/Solar Turbines, *LES software … Vision 21* quarterly, OSTI 822313 | [3P] | gas-turbine combustor LES | not stated | — | — | internal | — | no | no — the report's content about GridPro is that converting the mesh took **~3 months** | GLOBAL |
| 56 | LANL KIVA-hpFE / FEARCE reports, OSTI 1330623, 1338726, 1395001, 1484615, 1578023 | [3P] | IC-engine overset grids | not stated | GridPro builds the valve/port parts overlaid on the cylinder grid | — | internal | "robust and automatic grid generation" | no | **yes — Fig. 1(a) a valve overlaying the grid as constructed in GridPro** | GLOBAL |
| 57 | **Cheng & Eiseman 1995, NASA CP-3291** | **[V-GP]** | filleted multi-tube intersections (3-, 4-, 5-, 6-tube) | not stated | not stated | clustering criteria set in TIL | — | "smooth (and nearly orthogonal) grids"; aspect ratio discussed | — | **yes — Figs. 3, 4, 5, with "the thicker lines are block boundaries"** | LOCAL |
| 58 | Wang & Eiseman 1995, NASA CP-3291 (*Interactive high quality grid generation*, GridPro/IGgen) | **[V-GP]** | pipe, hexagon, supercircle, torus, sphere | not stated | **1, 2, 3, 7** blocks by case | — | — | **an explicit orthogonality function f(u) minimised; "smoothness and lack of grid skewness"** | — | yes — Figs. 2-6, one per block count | LOCAL |
| 59-70 | the twelve already covered — see §3 | mixed | see `gridpro-meshes-in-published-cfd.md` §1-§11b | 9 of 12 | 3 of 12 | 9 of 12 | 4 of 12 | 2 of 12 | 3 of 12 | 10 of 12 | — |

(The table has **58 numbered new rows**, and that — not a PDF count — is the number quoted
throughout. Entry 19 groups three Ameri NASA reports of one grid family and entry 56 groups five
LANL annual reports, so the number of underlying PDFs is larger; the Sources list names each one.
Row 59-70 is a single summary row for the twelve the other note already covers, and its cells are
a hand count over that note's §14c and §11, not over this table. **[V]**)

---

## 1. The new entries, one short section each

Each gives the citation, the verbatim mesh sentence, every number, and what the figure shows.
Roughly 15-40 lines each was the brief; most are shorter because most documents say less.

### 1.1 Entry 1 — Matthews & Key 2025, the richest quality reporting in the whole census **[V]**

**Citation.** D. R. Matthews and N. L. Key (High-Speed Compressor Research Laboratory, Purdue
University), *Considerations for High-Fidelity Modeling of Unsteady Flows in a Multistage Axial
Compressor*, **Int. J. Turbomachinery, Propulsion and Power 10(1), 5**, 2025, DOI
`10.3390/ijtpp10010005`. CC-BY. **[V]** — PDF from `mdpi-res.com`, grepped (2 hits), read.

> "spatially discretized using GridPro [19], a commercial multi-block, structured [grid
> generator] … domains for orthogonal, flow-aligned cells throughout the model. The O-grid
> topology extends … increase orthogonality and reduce cell skewness. The average first cell
> offset from every wall is consistent with an average and maximum y+ of less than one and five,
> respectively, ensuring a well-resolved viscous sublayer. With an expansion ratio of 1.1, more
> than ten [cells in the boundary layer] …"

Also: "dimensional surface roughness to grid cell height (ks+/y+) averages less than 3.6"; a grid
sensitivity study following the **Grid Convergence Index (GCI)** method with ASME guidelines, with
`GCI_base/r^p`, `GCI_fine` columns, stage total-pressure-ratio GCIs **0.14-0.44%** and 0.85%
overall. **[V]** This is the only document in the census that names orthogonality, skewness,
expansion ratio, BL cell count, y+ (avg and max) and GCI **together**. It is the same facility as
`gridpro-meshes-in-published-cfd.md` §11b but a **different paper and different authors**. **[V]**

### 1.2 Entry 2 — Luk 2008: the only document that prints GridPro's OWN quality report **[V]**

**Citation.** D. H.-F. Luk, *Steady Heat Transfer Predictions For A Highly Loaded Single Stage
Turbine With Flat Tip*, MS thesis, The Ohio State University, 2008, OhioLINK `osu1224705112`.
**[V]** — PDF downloaded from `etd.ohiolink.edu`, 32 `gridpro` hits.

> "The quality check function provides a status report on **block count, cell count, fold count,
> skewness, warpage, stretching ratio, smoothness, and aspect ratio**. The most important
> condition that must be met is the condition that there would be zero folds in the grid. The CFD
> code will not be able to run if there are any folds in the grid."

Numbers: stator **709,900** cells, rotor **1,751,840**, total **2,461,740**; rotor blade **122
cells spanwise, 161 blade-to-blade**; 156 nodes radially; "the stator is made up of 11 individual
blocks and the rotor is made up of 20 blocks resulting in **31 total**"; wall spacing "specified
using GridPro is **1E-5**"; "the present computation has a **y+ ≈ 0.38** for the 1st [cell]".
**[V]** Figures: 3.1 stator grid **topology**, 3.2 rotor grid topology, 4.3 stator and rotor
clustered and matched at the interface, 4.4 cross-section of the **H-O two-blade-row** grid, 4.5
rotor blade mesh, 4.6 rotor tip mesh, 9.1 "Use Gumbo to check block orientation". **[V]** (captions
read from the text layer; pages not rendered)

### 1.3 Entry 3 — Gollan & Ferlemann 2011: the REST inlet, two years after §4 of the other note **[V]**

**Citation.** R. J. Gollan and P. G. Ferlemann (NASA Langley Research Center), *Investigation of
REST-class Hypersonic Inlet Designs*, **AIAA 2011-2254**, DOI `10.2514/6.2011-2254`, NTRS
`20110010977`. **[V]** — NTRS PDF, 6 hits.

> "the initial Euler grids have approximately **2.3 million cells**. By contrast, after using the
> clustering utility, the grids for viscous cases have roughly **4.1 million cells**. The GridPro
> utility was used to give a near wall spacing of **0.0127 mm**. This corresponds to **y+ values
> of less than 2** for most of the model."
> "In final preparation of the grid, **207 elemental blocks were merged into 13 superblocks**."

This is the **follow-on to `gridpro-meshes-in-published-cfd.md` §4** (Ferlemann & Gollan 2009, 290
→ 17 superblocks, 2.7 M cells, 0.0005 in, y+ ≈ 1). Same team, different design study, different
numbers — so it is a new document here, and the pair is the only case in the whole census where
the same group publishes a block count twice. **[I]**

### 1.4 Entries 4, 5, 20-26 — the NASA Glenn turbine-heat-transfer family **[V]**

Nine documents by overlapping authors (Garg, Ameri, Heidmann, Rigby, Steinthorsson) that all mesh
with GridPro/az3000 and all merge the elemental blocks with Rigby's **Method of Weakest Descent**.
They are the densest source of **block counts before and after merging** in the census:

| Document | before → after | cells | y+ / spacing |
|---|---|---|---|
| Heidmann, Rigby & Ameri 1999 (99-GT-186) | **2298 → 140** | not stated | y+ < 1.0 |
| Garg 2000 (NASA/CR-2000-210510) | **162 → 13** | 106,496; 128 cells in hole M's exit | y+ < 1 |
| Garg & Ameri 2001 (2001-GT-0165) | **28 → 5** | 55,296; 112 cells around the blade | avg y+ 0.26 |
| Rigby *et al.* 1998 (98-GT-329) | merged to **64** | 1,489,920 | largest cell-centre y+ < 1.25 |
| Ameri 2002 (GT-2002-30211) | not stated | **340k / 523k / 1.06 M** | avg y+ ≈ 1 |
| Garg 2002 (GT-2002-30229) | not stated | 160,128 from 92,928 inviscid | y+ < 0.5; **adjacent-size ratio 0.8-1.25** |
| Heidmann 2008 (GT2008-50845) | not stated | 2.5 M, ~300k coarsened | y+ < 1; **stretch < 1.2** |
| Roy 2005 (NNC04GA21G) | merged to **one** block | 4 M | y+ < 1; **stretch < 1.2** |
| Ameri 2001 (2001-GT-0156) | not stated | 1.2 / 1.4 / 1.8 M | y+ criterion stated |

**[V]** — every row read off the PDF named in Sources. Two of these carry a figure whose subject
is the mesh rather than the flow: Heidmann *et al.* 1999 Figs. 3-4 (blade-to-blade multiblock grid
plus a leading-edge zoom) and Ameri 2002 Fig. 2, which is **five panels — (a) grid topology, (b)
coarse, (c) medium, (d) fine, (e) the y+ distribution on the fine grid**. That last one is the
only figure in the census that draws a refinement series and its y+ together. **[V]**

### 1.5 Entry 6 — Vatsa, Sanetrik & Parlette 1995: a 2-D MULTI-ELEMENT AEROFOIL, with its blocks drawn **[V]**

**Citation.** V. N. Vatsa (NASA Langley Research Center), M. D. Sanetrik (AS&M), E. B. Parlette
(ViGYAN Inc.), *Block-structured grids for complex aerodynamic configurations: Current status*,
in **NASA CP-3291**, *Surface Modeling, Grid Generation, and Related Issues in Computational Fluid
Dynamic (CFD) Solutions*, 1995, pp. 165-180. NTRS `19950022315`. **[V]** — NTRS PDF, 5 hits.

> "An excellent test case representative of realistic high-lift configuration is now available as
> a result of a joint effort between NASA Langley Research Center and McDonnell Douglas Aircraft
> Co. for a **two-dimensional, 3-element high-lift configuration**. The newly available
> GRIDPRO/AZ3000 software has been used successfully to grid this configuration (ref. 18). A
> partial view of the resulting **97-block grid** is shown here in Fig. 1. The grid lines are
> smooth and nearly orthogonal, **except near singular points formed by the block boundaries**.
> This grid clearly demonstrates the flexibility of GRIDPRO/AZ3000 to generate CFD-quality grids
> for geometrically complex configurations, and in being able to concentrate grid points near
> solid surfaces. However, this software package does not lend i[tself] …"

**I rendered page 11 and read Figure 1 myself. [V]** It draws **block boundaries as heavy black
lines over thin grid lines** — the one presentation convention this repo's own
`view_mesh_vtk.py` already uses. What I see: the three elements (slat, main, flap) sit inside a
common near-body wrap whose near-wall layers are so fine they read as solid black at the slat and
flap; outside that wrap the field relaxes to near-square cells within roughly one chord; and at
least **six heavy seams radiate outward** from corners on the wrap — two upward, four downward —
each a block boundary along which the grid changes direction. **[V]**, a reading off the rendered
image, with no scale bar.

**This closes the single largest gap `gridpro-meshes-in-published-cfd.md` named.** That note's
"Tried and could not get" ends with "**A third-party 2-D aerofoil GridPro mesh figure — none was
found.** Every aerofoil-shaped lead resolved to either the vendor's own material or to a paper
that does not use GridPro." Entry 6 is third-party (NASA Langley / AS&M / ViGYAN), is a 2-D
aerofoil, carries the figure, and states a block count. **[V]** It also answers that note's §14b
tally in the other direction: here the blocking IS the subject of a figure in a paper whose topic
is neither grid generation nor tooling but a **status survey of block-structured CFD**. **[I]**

Extracted to `gridpro-mesh-samples/entry06-vatsa1995-fig1-97block-multielement-airfoil.png` under
the NASA public-use determination recorded in `PROVENANCE.md`.

### 1.6 Entry 7 — Eiseman 1995: the vendor's own 2-D aerofoil in ground effect **[V-GP]**

**Citation.** P. R. Eiseman (Program Development Corp.), *Multiblock grid generation with
automatic zoning*, in **NASA CP-3291**, 1995, pp. 145-164. NTRS `19950022314`. **[V-GP]** — the
affiliation string on the NTRS record is "Program Development Corp." **[V]**

I rendered page 14 and read **Figure 4** myself. It is **two panels**: a whole-domain view of a
digitised aerofoil near a ground plane, and a near-field zoom. Its caption is the clearest
statement of blocking intent found anywhere in this census:

> "An airfoil close to the ground. … This is an example of the use of **compact enrichment**. In
> the global picture, it is clear that there are **no undesireable clusters of points on the
> boundaries** either above or upstream of the airfoil. While a cluster appears for the full
> length of wake branch cut, **it too could have been limited to some distance before the
> downstream boundary if desired**. However, this option was not chosen. In the vicinity of both
> the leading and tailing edge, the coordinate curve density is at its highest. One can readily
> see that the chosen pattern of points (grid topology) sends **curves looping from the bottom of
> the airfoil to the top about both leading and trailing edges**. It also can be seen that similar
> loops appear from the top of the airfoil and end upon the ground surface. By contrast, the
> bottom of the airfoil was left to be that of a simple block. We often call such loop structures
> **"clamps"** or as in the case of the trailing edge structure **"a collar."** The TIL code for
> this case was a little over one page. The run time is less than one hour on a medium grade
> workstation."

**[V]**, verbatim. Reading the figure: in the zoom I can follow heavy seams that loop around the
leading edge and around the trailing edge and close on themselves — the "clamps" — while the
wake cut runs unbroken to the right-hand boundary, and the cells away from the aerofoil are
large and near-square. **[V]** The global panel shows the wake cluster persisting to the outflow,
exactly as the caption concedes. **[V]**

**Why this matters to this repo.** "Clamps" and "a collar" are the vendor's own names for the
device `nesting-blocks-at-a-complicated-leading-edge.md` and `meshing-the-cove-and-the-trailing-edges.md`
discuss, published in 1995 in a NASA conference proceedings, with a drawn 2-D aerofoil instance.
Nothing here binds a rule; it is a primary source for a vocabulary this repo reached
independently. **[I]**

Extracted to `gridpro-mesh-samples/entry07-eiseman1995-fig4-airfoil-in-ground-effect.png`.

### 1.7 Entry 8 — Repko *et al.* 2016: a GridPro grid COLOURED BY BLOCK **[V]**

**Citation.** T. W. Repko, A. C. Nix, S. C. Uysal, A. T. Sisler (Dept. of Mechanical and Aerospace
Engineering, West Virginia University), *Flow Visualization of Multi-Hole Film-Cooling Flow under
Varying Freestream Turbulence Levels*, **J. Flow Control, Measurement & Visualization 4(1)**,
2016, 13-29, DOI `10.4236/jfcmv.2016.41002`. **CC BY 4.0.** **[V]**

> "A multi-block structured hexahedral grid was produced using GridPro™ for the three turbulence
> condition cases. This grid contained **2.5 million hexahedral cells** and employed viscous
> clustering near to the solid walls with a **y+ value less than 1.0** at all locations. Nominally
> the y+ value was **on the order of 0.1** at nearly all locations along the top surface. A
> **stretching ratio of 1.2** was used normal to the viscous walls … **Figure 3** shows the
> boundary conditions and structured multi-block grid created in GridPro™, **with each block
> indicated by a different color**."

Domain: top plane **10 hole diameters** above the surface, **19 d_m** upstream and **30 d_m**
downstream, **1.5 d_m** half-width; grid independence over **1.2 / 2.5 / 3.0 M** cells. **[V]**

**I extracted Figure 3's own embedded bitmap (2530x806 px) and read it. [V]** It is a
side-elevation of the whole domain in which **about thirty blocks are each filled with a distinct
colour**, with thin white grid lines inside them, plus a separate plenum/hole panel below whose
blocks fan into the hole. Block seams are therefore readable as colour boundaries rather than as
heavy lines, and the near-wall band is a thin strip of blocks running the full length.

**This falsifies, as a general claim about practitioners, the "colour by block: zero of ten"
finding in `gridpro-meshes-in-published-cfd.md` §14b.** That tally was true of the ten documents
that note reached and it says so; with a wider net the practice does occur in third-party work.
**[V]** on the figure; **[I]** on the generalisation, which is now "rare but not absent — one in
the 58 new entries here, i.e. **one in 70** across both notes."

Extracted to `gridpro-mesh-samples/entry08-repko2016-fig3-grid-coloured-by-block.png`.

### 1.8 Entries 9, 10 — the two largest block counts in the census **[V]**

**Entry 9.** K. Ramesh, J. R. Edwards, H. Chelliah, C. Goyne, J. McDaniel, R. Rockwell, J. Kirik,
A. Cutler, P. Danehy, *Large Eddy Simulation of High-Speed, Premixed Ethylene Combustion
(Invited)*, **AIAA 2015-0356**, 53rd AIAA Aerospace Sciences Meeting. Open copy at
`eprints.gla.ac.uk/103543`. **[V]**

> "The computational model of the domain consists of **93 million grid cells subdivided into
> 13,369 blocks**. The mesh was generated using GridPro (Program Development Company) and was
> designed to maintain a **nominal isotropic mesh spacing of about 0.25 mm** in the interior of
> the geometry. The mesh spacing on all solid surfaces is **5 µm**. The mesh expands rapidly in
> the dump region, leading to very high aspect ratio cells."

**Entry 10.** T. B. Nielsen, J. R. Edwards, H. K. Chelliah *et al.*, *Hybrid LES/RANS Analysis of
a Premixed Ethylene-Fueled Dual-Mode Scramjet Combustor*, ***AIAA J.*** 2021, DOI
`10.2514/1.j059343`, LA-UR-19-29624 (OSTI 1830574). **[V]**

> "cells distributed over **25,278 blocks**" … "The wall-normal mesh spacing is set to **5E-6 m**
> throughout using GridPro's clustering ('clu') command with a **1.3 stretch ratio**, which
> attempts to maintain the stretch ratio and wall spacing while yielding a nearly [uniform
> freestream spacing of ~0.2 mm]"

**13,369 and 25,278 are the two largest block counts anywhere in this census**, and both come from
the same research community (Edwards, NC State). **[V]** For scale, `gridpro-meshes-in-published-cfd.md`'s
largest was 290 elemental blocks. **[I]**

### 1.9 Entries 11, 12, 14, 44, 45 — hypersonic / re-entry **[V]**

- **Entry 11.** A. Schwing (NASA JSC / U. Minnesota), *Validation of US3D for Capsule Aerodynamics
  Using 05-CA Wind Tunnel Test Data*, NTRS `20120017946` (presentation, 2012-11-19). "All grid
  generation was performed with GridPro." "Final grid of **18,217,949 points and 18,113,216
  cells**." "the outer boundaries extended **30 diameters** from the vehicle". "Viscous
  wall-spacing selected to maintain **y+ of less than 1** on entire geometry." **[V]** The 30
  diameters matches `gridpro-meshes-in-published-cfd.md` §1's capsule exactly — the same group's
  house convention. **[I]**
- **Entry 12.** P. E. Papadopoulos, D. K. Prabhu, M. J. Wright, C. B. Davies, R. D. McDaniel,
  E. Venkatapathy, P. Wercinski *et al.*, *CFD simulations in support of Shuttle Orbiter
  contingency abort aerodynamic database enhancement*, **AIAA 2001-3067**, NTRS `20010089699`.
  "GridPro was used to build the complex topological structure and Gridgen was implemented for
  local grid modifications. The volume grid consists of **three topological layers**." Figure 7's
  own caption: "**ARC volume grid (2.2 million points without the wake grid — wake grid added 1.4
  million points): (a) topological morphology, (b) 365 non-merged blocks.**" **[V]** This is the
  only document found where a figure panel's subject is literally "the 365 non-merged blocks".
- **Entry 14.** J. Oswald *et al.*, *DLR-ONERA accurate CFD support for the Pre-X project*, 2005,
  `elib.dlr.de/21745`. "a grid of **376 blocks and 1,044,992 cells**" (Mach 25); "**548 blocks and
  1,428,992 cells** for the fine mesh" (Mach 17.75); "The overall first wall spacing of the grid
  is kept in a range, where **y+ < 1**"; "The final grids contain about **700,000 cells**"; "three
  grid levels have been used". Figures 4-6: symmetry-plane grid with sting, surface grid, body-flap
  close-up. **[V]**
- **Entry 44.** V. Ledermann, I. Midani, E. Constant, P. Van Hauwert, M. Spel, L. Stainier *et
  al.*, *Pampero HiFi*, **CEAS Space J. 18**, 2025/2026, 209-234, DOI `10.1007/s12567-025-00655-2`.
  "The MISTRAL structured multi-block mesh was made using GridPro. It contains more than **14.5
  million cells** and the **height of the first cell layer at the wall is 2e-6 m** (Fig. 9)."
  "The direct integration of the grid generator GridPro [30] allows the efficient creation of these
  **massively multi-blocked grids**." **[V]**
- **Entry 45.** I. Midani, *Automatic meshing and Machine Learning methods for predicting fluid
  quantities during atmospheric re-entry*, PhD, Aix-Marseille Université, 2024, `tel-05248848`.
  "The input mesh is generated **by hand with GridPro** [28], allowing high-quality mesh with
  specific features such as **clustering to improve the quality of the mesh near the wall**." The
  thesis's own octree/AMR meshes are the comparison; cell counts 36,824 / 70,144 / 71,343 /
  710,400 / 1,359,461. **[V]** Same group as entry 44 — not an independent practitioner. **[I]**

### 1.10 Entries 16, 17 — the 2-D aerofoil cases this repo asked about **[V]**

**Entry 16.** A. Crivellini, V. Golubev, R. Mankbadi, J. R. Scott, R. Hixon, L. Povinelli,
L. J. Kiraly, *Nonlinear Analysis of Airfoil High-Intensity Gust Response Using a High-Order
Prefactored Compact Code*, **AIAA 2002-2535**, NTRS `20020087944`. **[V]** — the author list is
from the NTRS citation record; the scan's own author line is illegible. I rendered page 3:

> "the grid extending **at least 10 chords away from the surface in each direction**. All the
> meshes are generated as **single blocks** by the GridPro commercial software [9]."
> "with grid densities **600x240** (for the cambered airfoil cases) and **591x238** (for the
> symmetric airfoil cases). Similar to [4], the grids are generated by GridPro using **algebraic
> clustering around the profile in the normal direction (Δn=0.01)** and near the trailing edge"

Geometries: unloaded symmetric 12%-thick Joukowski, and loaded 12%-thick 2%-cambered Joukowski at
2°. **There is no mesh figure** — Figure 1 is a parallel-speedup plot. **[V]** So this is the first
2-D aerofoil GridPro case in either note with full spacing numbers, and it draws nothing.

**Entry 17.** V. Allampalli, *Fourth order Multi-Time-Stepping Adams-Bashforth (MTSAB) scheme for
NASA Glenn Research Center's Broadband Aeroacoustic Stator Simulation (BASS) Code*, PhD, Univ. of
Toledo, 2010, OhioLINK `toledo1270739741`. **[V]** — 7 `gridpro` hits.

> "The grid used was **C-H topology, extending at least 10 chord lengths away in each direction**.
> The grid was generated using the commercial package GridPro [31]."
> "grids were generated for the **steady flow over the NACA0012 airfoil with a rounded trailing
> edge**. The grids for these cases were generated using the GridPro package [31]. Two grids were
> generated."
> "The grid (Grid 3) was again generated using the GridPro software. Grid 3 has a total of
> **51,465 points**. The **number of grid blocks in this grid was 95**."
> "An **O-grid** is used for this test case is generated using GridPro [31]."

Figure 3-3 is captioned "**Single block O-grid around a 2D cylinder** has one MTSAB level", and
Figures 3-4 and 3-6 show the same block cut into 6 and then 24 blocks by the thesis's own
algorithm. **[V]** (captions read from the text layer)

### 1.11 Entries 33-38 — the university-thesis seam, where block counts actually get printed **[V]**

Six theses, all reached through OhioLINK's `send_file` endpoint, all confirmed by grep:

- **33.** H. Ayyalasomayajula (U. Cincinnati MS, 2003): "a **12-block** structured grid … **Dual
  topologies O- and H-** have been utilized"; a cylinder case with "**750,000 grid points**";
  "H-grid alone increases the **skewness** of the grid near the [leading edge]". **[V]**
- **34.** N. Singh (U. Cincinnati MS, 2005): the same 12-block LPT cascade grid, "**two-million
  grid points**, with 32 planes along the spanwise"; "made **orthogonal at boundaries, and almost
  orthogonal within the solution domain**". **[V]**
- **35.** A. Kasliwal (U. Cincinnati MS, 2006): "the **far-field boundary is located 75 diameters
  away**"; "the domain is decomposed into **8 blocks**" and elsewhere **24**; "approximately
  **3.9 million grid points**, with 48 points in the spanwise direction. Approximately **70% of
  the total grid points** are [near the wall]"; figures 16, 18, 22, 23 are the **block layout**,
  the grid over vorticity, and two grid-refinement profile comparisons. **[V]**
- **36.** N. Mansouri (U. Toledo PhD, 2016), *A High-Order High-Accuracy Geometric Block Interface
  Treatment for Computational Aeroacoustics Codes*: three GridPro grids built **specifically to
  contain singular points** — "a **3-way singularity**", "each block contains **21 grid points
  along each coordinate**", and "A quarter of this grid is made by GridPro [110] and patterned
  three times … The grid topology contains **eight 3 and 5-way singularities**." **[V]** This is
  the only document in the census whose subject is what happens to accuracy AT an odd-valence
  block corner, and it uses GridPro to manufacture them on purpose.
- **37.** D. Ingraham (U. Toledo PhD, 2015): "a two-dimensional grid with **five blocks and two
  singular points** was constructed using the GridPro [81] grid generation program"; the thesis is
  a formal grid-refinement/verification study and reports that "the **singular grid convergence
  rate is markedly** [lower]". **[V]**
- **38.** M. A. Heminger (U. Toledo MS, 2010): "The mesh was created using GridPro [14], which has
  the ability to create the **face-matched** structured grid that the BASS Code requires … The
  final mesh consists of **104 blocks** and a total of **327,184 grid points**." **[V]**

Entries 36 and 37 together are the clearest third-party statement found that **a GridPro grid's
3- and 5-way corners are a measurable accuracy concern**, which is the same object
`.claude/rules/mesher-multiblock.md` calls a shared corner. **[I]**

### 1.12 Entries 39-43, 46 — marine, pumps, hulls **[V]**

- **39.** J. M. Baltazar, D. Rijpkema, J. Falcão de Campos, J. Bosschers, *Prediction of the
  Open-Water Performance of Ducted Propellers with a Panel Method*, **JMSE 6(1) 27**, 2018, DOI
  `10.3390/jmse6010027`: "**five nearly-geometrically similar multi-block structured grids** were
  generated using … GridPro. The grids range from **1.1 to 26.8 million cells**. … the maximum
  dimensionless distance to the wall of the first cell, known as **y+, is lower than 1**."
  Cylindrical domain **5 propeller diameters** in all directions; "differences are less than 1% for
  the grid with 12.9 million cells". **[V]** Same first author as
  `gridpro-meshes-in-published-cfd.md` §8, three years earlier and a different propeller — so the
  twelve-grid series there and the five-grid series here are one group's practice, not two. **[I]**
- **40.** P. Maljaars, L. Bronswijk, J. Windt, N. Grasso, M. Kaminski, **JMSE 6(2) 51**, 2018,
  DOI `10.3390/jmse6020051`: "a structured multi-block grid built with GridPro, using a **standard
  block topology developed at MARIN**. The topology is applied quite often and **gives good quality
  grids, most of the time**. However, for the propeller considered here, grid generation was
  cumbersome due to the relatively **high skew** of the propeller". Domain diameter **3 D**, length
  **5 D**; "**y+ was below 1**". **[V]** The "most of the time" is the frankest sentence about
  GridPro reliability in the census.
- **41.** S. Harries and S. Uharek (FRIENDSHIP SYSTEMS AG), **JMSE 9(10) 1069**, 2021, DOI
  `10.3390/jmse9101069`: "The main advantage of GridPro is the ability to **separate topology and
  geometry**. This allows setting up the initial topology (block structure) of the grid **prior to
  the optimisation study** and simply re-run the meshing process for each variant. The resulting
  grids are all of high quality and due to the ident[ical topology] …" and "**GridPro allows to
  change the grid in the vicinity of the hull, leaving the far-field grid untouched**." Grid
  convergence over **3.7 M (S1) / 1.5 M (S2) / 460,000 (S3)** cells per demi-hull. Figure 13 draws
  the bow-region mesh for the baseline (grey) and a modified hull (red) **superposed**. **[V]**
  *Labelled [3P] because no author carries a GridPro affiliation, but the acknowledgements thank
  "**Samuel James from GridPro** for the support regarding the automated meshing" — Samuel E.
  James is on the vendor list. Flagged rather than reclassified.* **[V]**
- **42.** C. Camci, M. Averbach, J. Town, **Aerospace 6(5) 60**, 2019, DOI `10.3390/aerospace6050060`:
  "Grid generation was completed with GridPro which creates a multiblock, body-fitted, and
  structured hexahedral grid and **uses automated subroutines to improve mesh quality**." No
  numbers in what I read. **[V]** (negative, partial)
- **43.** D. Wu *et al.*, **Appl. Sci. 11(17) 8180**, 2021, DOI `10.3390/app11178180`: "**the
  quality of the grid directly affects the accuracy and time** of numerical calculation. … the
  structured meshes were constructed using Gridpro software, as shown in Figure 2. The grid
  sensitivity analysis … as the number of cells exceeds about **3 million**, the head [stabilises]";
  final domain **940,000 cells**. **[V]**
- **46.** T. B. Kroll and K. Mahesh, ***Flow* 5 E2**, 2025, DOI `10.1017/flo.2024.36`: meshes made
  with "Pointwise (Cadence) **and GridPro**"; "a **minimum wall-normal spacing of 0.0017 D with a
  growth ratio of 1.01**". **[V]**

### 1.13 Entries 47-52 — one-paragraph users **[V]**

- **47.** P. McGinn, A. Gander, G. Tretola, C. Crua, K. Vogiatzaki (U. Brighton), ICLASS 2021, DOI
  `10.2218/iclass.2021.6014`: "A conventional curvilinear structured mesh provided by the **ECN
  Workshop** [5] and **generated with GridPro** … The mesh consists of **5.5 million cells**, with
  a **minimum size of 5 µm** in the needle tip and nozzle and an **average size of 10 µm** in the
  counter-bore. The **maximum cell size is 65 µm** approaching the domain exit." **[V]** Notable
  because the mesh is a **community reference grid**, not the authors' own.
- **48.** K. I. Borynyak, *J. Phys. Conf. Ser.* **1382** 012004, 2019: "**4×10^6 elements** for
  rotating pipe case and **1.6×10^7** for rotating nozzle case with the wall-adjacent gridcell
  width (**y+**) of about **10** in wall units". **[V]** The only case in the census that is
  deliberately wall-function-coarse besides entry 32 and
  `gridpro-meshes-in-published-cfd.md` §10.
- **49.** T. G. Drozda, R. A. Baurle, J. P. Drummond (NASA Langley), NTRS `20160009131`, 2016:
  "Both grids were generated with GridPro in the vicinity of the injector bodies … and further
  combined with **Pointwise-generated h-blocks**"; "clustered towards all of the walls with the
  **growth rates varying from 5% to 15%**"; "**Grid Convergence Index (GCI)**, which is based on
  Richardson extrapolation"; "to help alleviate **grid skewness** issues at the top of [the
  domain]". Figures 5-6 draw the coarse grid where "each visible cell contains 4x4x4 cells".
  **[V]**
- **50.** W. Reschke, M. Pfeiffer, S. Fasoulas (U. Stuttgart), arXiv 2007.06339: "PICLas uses 3D
  hexahedral meshes, and here it is build using GridPro [23]. The setup consist of a **≈ 40°
  cylindrical domain** to reduce computational effort. Figures 4 and 5 show a representative mesh
  slice". **[V]**
- **51.** J. Klečková, *Modelování aeroelastických jevů se zaměřením na predikci flutteru
  turbínových lopatek*, PhD, Univ. of West Bohemia, 2019, `dspace.zcu.cz`. In Czech. It states the
  **topology rule** in the vendor's own terms — "the topology consists exclusively of
  quadrilateral blocks; from each interior node of a block four edges should emanate where
  possible; exceptions may be nodes with three or [five]" — builds the periodic boundaries from
  the blade count (90) at r = 1461.9 mm, defines **skewness** as the quality measure, and reports
  "**y+ in the interval (y+min = 0.1; y+max = 4) with an average y+ around 1**". **[V]**
- **52.** CSME-CFDSC-CSR 2025, *Numerical analysis of heat-generating terms … for wire arc
  additive manufacturing*, DOI `10.82417/mc39-6943`: "A total number of **9,000 cells** were
  generated using GridPro [15] **that minimizes skewness and provides a high-quality structured
  mesh**." **[V]** The **smallest** mesh in the census, and one of the few that names a quality
  property as the reason for the tool choice.

### 1.14 Entries 53-56 — tooling, loops and pipelines **[V]**

- **53.** J. Hauser, T. Ludewig, T. Gollnick, R. Winkelmann, *A Pure Java Parallel Flow Solver*,
  CACR-170 / **AIAA 99-549**: "Grids are accepted in **GridPro or Plot3D format**. Using GridPro
  **property settings**, grids of any size or block number can be **directly read** by JParNSS
  without any further modifications." Figure 1: "A multiblock grid for the **X-33** vehicle. Each
  block is run in its own thread." Measurements over **38-block / 48,000-cell** and
  **38-block / 192,000-cell** grids and a **148-block** case. **[V]**
- **54.** H. Zhao, D. Knight, E. Taskinoglu, V. Jovanovic (Rutgers), *Data Driven Design
  Optimization Methodology Development and Application*, Springer LNCS 3044, DOI
  `10.1007/978-3-540-24688-6_97`: GridPro is one of five components in an automated loop
  (CF-SQP / Pro/Engineer / **GridPro** / GASPex / auxiliary), meshing an S-shaped subsonic
  diffuser once per optimiser iteration. **No mesh numbers at all.** **[V]** (negative)
- **55.** DOE/NETL, *LES software for the design of low emission combustion systems for Vision 21
  plants*, quarterly report, OSTI 822313, 2003: "Solar used the mesh generation software GridPro
  by Program [Development Company] … The next **3 months or so were spent trying to convert the
  GridPro mesh** into [the solver's format]. … **DTF key number must be repaired from Gridpro DTF
  output.**" **[V]** The only document found that reports GridPro as a **cost**, and it reports no
  mesh numbers. (negative)
- **56.** LANL KIVA-hpFE / FEARCE annual reports, OSTI 1330623 (2016), 1338726 (2017), 1395001
  (2017), 1484615 (2018), 1578023 (2019): "We are using **GridPro tools for robust and automatic
  grid generation** and collaborating with the GridPro team on use for engine modeling for all
  KIVA versions." Figure 1(a) is captioned "**valve overlaying the grid as constructed in
  GridPro**". No counts. **[V]** (negative on numbers, positive on a figure)

### 1.15 Entries 57, 58 — the vendor's own NASA CP papers **[V-GP]**

- **57.** Z. Cheng and P. R. Eiseman (Program Development Corp.), *Examples of grid generation with
  implicitly specified surfaces using GridPro/az3000. 1: Filleted multi-tube configurations*,
  NASA CP-3291, 1995, NTRS `19950022351`. Figures 3, 4 and 5 are grids inside 6-, 5-, 4- and
  3-tube intersections, each captioned "**The thicker lines are block boundaries.**" — i.e. the
  same convention entry 6 uses, declared in the caption. The paper explains that "the primary user
  input is the **pattern** of grid lines or surfaces. This pattern is referred to as the grid
  **topology**. The definition of grid topology is given by a **topology input language (TIL)**.
  This is also used to specify the **number of grid points and clustering criteria**." **[V]**
- **58.** Z. Wang and P. R. Eiseman, *Interactive high quality grid generation* (GridPro/IGgen),
  NASA CP-3291, 1995, NTRS `19950022353`. It derives **an explicit orthogonality function f(u)**
  and minimises it, and its figures are a **single-block** 2-D pipe, a **three-block** hexagon, a
  **two-block** supercircle, a half **single-block** torus, and a **seven-block** sphere. "These
  examples clearly show the **smoothness and lack of grid skewness** that can be [obtained]."
  **[V]** It is the only document in the census that writes down a quality functional rather than
  reporting a number.

---

## 2. Documents that NAME GridPro but did not mesh with it — recorded so they are not miscounted

All were downloaded and grepped. **[V]** None is counted in the 70.

| Document | What the GridPro mention actually is |
|---|---|
| *Comparison of Numerical Schemes for a Realistic CAA Benchmark Problem* (NTRS 20050207390) | reference-list entry only |
| *Validation of a High-Order Compact Code…* (NTRS 20040201019) | reference-list entry only |
| *Development of an explicit multiblock/multigrid flow solver…* (AIAA 93-2380) | reference-list entry only |
| *Computations of unsteady viscous compressible flows using AMR* (AIAA 94-2330) | reference-list entry only |
| *Effects of Leading-Edge Tubercles … NACA 4412* (DOI 10.58445/6vcxpz86) | cites **`blog.gridpro.com`**, not a GridPro mesh — the same trap as `gridpro-meshes-in-published-cfd.md` §12c |
| *Unstructured Kiva* (OSTI 977395), *LAURA Users Manual* (NTRS 20130009520), *A Geometry Based Infra-structure…* (NTRS 19980009321), *A survey of AI methods for … mesh generation* (DOI 10.1007/s00366-026-02379-1), *Bringing out Fluids Experiments…* | GridPro listed among available mesh tools |
| *A HPC "Cyber Wind Facility"…* (OSTI 1355906) | "We have **since learned about** GridPro, which **may** allow…" — explicitly not used |
| *CPIC* (DOI 10.1109/tps.2013.2290060, and OSTI 1211594) | "see for instance GridPro" as an example of structured meshers; the grids are the authors' own |
| *Návrh a pevnostní kontrola požární proudnice*, *Citlivostní analýza…*, *Análisis del inyector Venturi*, *EFFECTIVE ALGORITHM…* | cite a GridPro web page or manual in a tool list |
| *Development of a RANS and LES/RANS Flow Solver…* (OSTI 1260372) | "Gridgen and GridPro mesh-generation techniques are usually employed" — no case |

Three further NTRS records matched `GridPro` in metadata and have **no downloadable full text**:
`20020050562` (X-33 aerothermal grid-generation issues, Polsky *et al.*), `20050186801` (Kiefer)
and `20050186861` (Jordan). The NTRS API returns an empty `downloads` list for all three. **[V]**

---

## 3. The twelve already covered — what this session ADDED

Full treatment is in `docs/research/gridpro-meshes-in-published-cfd.md`; nothing below repeats a
number that note already records.

| Its § | Document | What this session added |
|---|---|---|
| §1 | Stern *et al.* 2012, Venus capsule | nothing new; its 30-diameter far field is now corroborated as a group convention by entry 11 **[I]** |
| §2 | Stern *et al.* 2016, MEADS II | nothing new; panels (c)(d) still unrendered |
| §3 | Candler & Campbell 2010, Orbiter | **a companion document**: entry 12 (AIAA 2001-3067), same vehicle, an earlier GridPro grid, which DOES state a block count (365 non-merged) where §3's paper states none |
| §4 | Ferlemann & Gollan 2009, REST inlet | **the follow-on**: entry 3 (AIAA 2011-2254), 207 → 13 superblocks, 4.1 M cells, 0.0127 mm, y+ < 2 |
| §5 | Miki *et al.* 2025, HPT blade LES | nothing new; its ASME journal PDF is behind a Cloudflare check |
| §6 | Shyam 2010, NASA TM (TURBO preprocessor) | **the author's own PhD thesis**, entry 30 (`osu1258931807`), which states 20 + 11 blocks, 2,461,740 cells, 19 blocks for the flat plate, y+ < 1, and says outright "**no refinement study was deemed necessary**" — none of which is in the TM |
| §7 | Colombo *et al.* 2021, DrivAer | nothing new |
| §8 | Baltazar *et al.* 2021, propeller S6368 | **an earlier paper by the same first author**, entry 39 (JMSE 6(1) 27, 2018), five grids 1.1-26.8 M, y+ < 1, 5 D — establishing that §8's twelve-grid series is one group's standing practice, not an isolated instance **[I]** |
| §9 | Crabill *et al.* 2019, golf ball | nothing new |
| §10 | Norouzi *et al.* 2023, ICE3 train | nothing new |
| §11a | Synáč & Rudas 2011, ETC2011-028 | nothing new; its equiangle skew is no longer the only quality metric in the literature (§4b) |
| §11b | Brown *et al.* 2023, ETC2023-369 | **the gap it names is now closed**: I rendered **page 7 and looked at Figure 7**. It is a **solid-shaded, cyan, meridional cut of the CHT solid model with no grid lines anywhere**. So "no mesh figure" is confirmed for all nine figures, not eight. **[V]** Separately, entry 1 (Matthews & Key 2025) is a **different paper on the same Purdue PAX200 compressor** that reports GCI, skewness, orthogonality, expansion ratio and y+ |

---

## 4. What the census says in aggregate

### 4a. The counts **[V]** — re-derived from the table, with the rule stated

**The counting rule, so these can be re-derived and disagreed with.** For the 58 new rows a
column counts when it contains a **digit** that is not part of the phrase "not stated" (columns
"cells", "blocks", "first cell / y+"), when the far-field cell gives a distance in **body units**
(diameters, chords, widths, hole diameters — "internal", a sector angle and an absolute domain
size do not count), when the refinement cell names **two or more grids** or a formal
convergence/GCI study, when the quality cell is in §4b's list, and when the figure cell begins
"yes". The 12 already-covered entries are hand-counted from
`gridpro-meshes-in-published-cfd.md` §14c and §11.

| Reported | New (of 58) | Already covered (of 12) | Total (of 70) | Share |
|---|---|---|---|---|
| a cell / point / element count | **40** | 9 | **49** | 70% |
| a **block count** | **30** | 3 | **33** | 47% |
| a y+ or a first-cell height | **31** | 9 | **40** | 57% |
| a far-field distance in body units | **13** | 4 | **17** | 24% |
| a **grid-refinement series** | **17** | 3 | **20** | 29% |
| a named **quality metric** | **14** | 2 | **16** | 23% |
| a mesh or topology **figure** | **46** | 10 | **56** | 80% |

**The block count is the thing that moved.** `gridpro-meshes-in-published-cfd.md` found 2 of 10;
here it is 33 of 70, and the reason is visible in the data: **block counts are printed by theses,
NASA contractor reports and solver-coupling papers, and omitted by journal flow-physics papers.**
**[I]**, from the rows — of the 30 new ones, nineteen are theses or agency reports
(2, 3, 4, 5, 6, 12, 13, 14, 15, 17, 18, 19, 20, 21, 27, 30, 31, 53, 58) and eleven are journal or
conference papers. **[V]**, by counting that list.

**LOCAL vs GLOBAL, which is what the user asked.** A row is LOCAL if it reports at least one
quantity attached to a PLACE in the mesh — a per-block or per-region count, a first-cell height,
a named feature's resolution, a before/after merge — and GLOBAL if it reports only whole-mesh
aggregates. The last column of the census carries that verdict per row: **50 of the 58 new rows
are LOCAL and 8 are GLOBAL**. **[V]**, by counting that column.

### 4b. Which documents report a QUALITY metric — fourteen new, sixteen in all **[V]**

This is the answer to "find GridPro meshes of decent quality": these are the documents that say
something measurable about quality rather than asserting it.

| # | Document | The metric, as printed |
|---|---|---|
| 1 | Matthews & Key 2025 | **GCI** (ASME method, 0.14-0.44% and 0.85%); skewness and orthogonality named as design goals; **expansion ratio 1.1**; **>10 cells in the BL**; ks+/y+ < 3.6 |
| 2 | Luk 2008 | **GridPro's own quality check: block count, cell count, fold count, skewness, warpage, stretching ratio, smoothness, aspect ratio**, with "**zero folds**" as the pass condition |
| 21 | Rigby *et al.* 1998 | largest cell-centre **y+ < 1.25**; "significant improvement in **grid orthogonality**" from a named topology choice |
| 23 | Garg 2002 | "**the ratio of two adjacent grid sizes in any direction was kept within 0.8-1.25**" |
| 24 | Heidmann 2008 | **stretching ratios < 1.2** |
| 25 | Roy 2005 | **stretching ratios < 1.2** |
| 8 | Repko *et al.* 2016 | **stretching ratio 1.2**, plus a three-grid independence study |
| 32 | Shankara 2009 | "**skewness in the grid was kept to a minimum**" (and a y+ band, 15-40) |
| 37 | Ingraham 2015 | measured **grid-convergence RATE**, and reports it is **worse at singular points** |
| 46 | Kroll & Mahesh 2025 | **growth ratio 1.01** |
| 49 | Drozda *et al.* 2016 | **GCI**; growth rates 5-15%; skewness named as a modelling constraint |
| 51 | Klečková 2019 | **skewness** (defined by formula) and a **y+ band 0.1-4, average ≈ 1** |
| 52 | WAAM 2025 | "GridPro … **minimizes skewness**" |
| 58 | Wang & Eiseman 1995 **[V-GP]** | an explicit **orthogonality function** minimised; "smoothness and lack of grid skewness" |
| — | Synáč & Rudas 2011 (already covered, §11a) | **equiangle skew**: 1.01% of cells > 0.6, max 0.72 |
| — | Brown *et al.* 2023 (already covered, §11b) | **GCI** < 0.25% and 0.6% |

(**14** rows are new entries — 13 of them [3P] and one [V-GP] — and **16** is the total including
the two already-covered ones. §0 and §4a quote 14 and 16; the 13 is the [3P]-only subset, and is
the figure to use when comparing against `gridpro-meshes-in-published-cfd.md`'s single
third-party hit. **[V]**, my own tally of this table.)

**The shape of the answer.** `gridpro-meshes-in-published-cfd.md` found **one** quality metric in
its whole search and said so. With a full-text index instead of an abstract index, the figure is
not one — but it is still only about **one document in five**, and **no document anywhere in
either note publishes a quality HISTOGRAM or a per-cell quality field for a GridPro mesh**.
**[V]** What gets published is a **bound** (y+ < 1, stretch < 1.2, skew < 0.6) or a **convergence
index**, not a distribution. **[I]**

**And the one place a distribution-like artefact appears is the vendor's own GUI**: entry 2's
eight-field status report (block count, cell count, fold count, skewness, warpage, stretching
ratio, smoothness, aspect ratio) is a GridPro screen a student transcribed into a thesis, not a
figure anyone printed. **[V]** It is also the closest published analogue of what
`.claude/rules/mesher-quality.md` makes this repo's mesher print. **[I]**

### 4c. On figures and mesh SAMPLES **[V]**

- **56 of 70 carry a mesh or topology figure** (46 of the 58 new, 10 of the 12 covered).
  Of those, **nine draw the BLOCKING as the subject**
  (entries 2, 6, 7, 12, 13, 18, 28, 35, 57, plus §4 and §6 of the other note) rather than drawing
  grid lines. **[V]**
- **Block boundaries drawn HEAVY over thin grid lines** is the dominant convention when blocking
  is shown at all: entries 6, 57 (whose caption says so outright), and 35. **[V]**
- **Colour by block: one** — entry 8. **[V]** Against 66 documents, which is why the other note's
  "zero of ten" was a fair reading of its sample.
- **A before/after MERGE drawn in two panels: one** — entry 13, Figure 9b (282 blocks) beside 9c
  (22 blocks). **[V]** This is the only published picture found of what "merge elemental blocks
  into superblocks" does to a grid.
- **A refinement series drawn with its y+: one** — entry 22, Figure 2(a)-(e). **[V]**
- **Two 2-D aerofoil GridPro mesh figures now exist in this repo's notes**, entries 6 and 7, where
  the other note recorded none. One is third-party, one is vendor. **[V]**

### 4d. What this does and does not settle for this repo

It settles nothing — this is a research note and binds no rule, gate, test or source file. What it
adds to what the repo holds:

1. **A published, third-party, drawn 2-D multi-element aerofoil GridPro grid with its block count**
   (entry 6, 97 blocks), which the repo did not have.
2. **The vendor's own words for the leading-/trailing-edge loop device** — "clamps" and "a
   collar" (entry 7) — published in 1995 with a drawn aerofoil instance.
3. **Evidence that 3- and 5-way block corners are a measured accuracy concern in the literature**
   (entries 36, 37), not only a modelling convenience.
4. **A realistic distribution for what a GridPro user publishes about mesh quality**: a bound or a
   GCI, in about one document in five, and never a distribution.

---

## Sources

Every URL below was fetched by me with `curl` or WebFetch in this session, and the result is
stated. PDFs were read with `pdftotext -layout`; pages named as "rendered" were turned into images
with `pdftoppm` and looked at; "image extracted" means `pdfimages` pulled the figure's own bitmap.

**Bibliographic APIs, queried directly** (the route change that produced this note):

- `https://api.openalex.org/works?filter=fulltext.search:GridPro&per-page=200` — **196 works**,
  the whole result set in one page. **This filter is the single reason this note exists**: the
  note beside it used `search=` (184 fuzzy) and `filter=title_and_abstract.search:GridPro` (37),
  both of which are metadata-only, and named that as its binding limit. **[V]**
- `https://api.openalex.org/works?filter=fulltext.search:az3000&per-page=100` — **76 works**, most
  of them false positives about a dental panoramic X-ray machine called AZ3000; it contributed
  entries 16, 53 and several NTRS leads. **[V]**
- `https://api.openaire.eu/search/publications?keywords=GridPro&size=50&format=json` — **21
  publications**; contributed the LPT-cascade and film-cooling clusters and the UQ/TUHH leads.
  **[V]**
- `https://api.crossref.org/works?query=GridPro&rows=100` — **2 results only** (Crossref does not
  index full text). Both are the vendor's: `10.2514/6.2018-0659` with three `PDC/GridPro`
  affiliation strings, and `10.1007/s00366-005-0310-1`. **[V]**
- `https://www.osti.gov/api/v1/records?q=GridPro&rows=50` — **41 records**, but the query is
  tokenised (`grid` + `pro`): I downloaded and grepped the three most promising
  (`1976053`, `1876298`, `1883942`) and **all three contain zero occurrences of "gridpro"**. A
  quoted query `q=%22GridPro%22` returns **0 records**. OSTI contributed entries 10, 55 and 56
  only via OpenAlex. **[V]**
- `https://ntrs.nasa.gov/api/citations/search?q=<GridPro|Eiseman|Program+Development+Company|multiblock+structured+grid+GridPro>`
  — 11 / 40 / 279 / 2 records; the `Eiseman` query is what surfaced entries 6, 7, 57, 58. **[V]**
- `https://ntrs.nasa.gov/api/citations/<id>` for `20020050562`, `20040182280`, `20010061395`,
  `20050186801`, `20050186861`, `19950022314`, `19950022315`, `19920064435`, `20020087944` —
  author affiliations, venues and the `copyright.determinationType` used in `PROVENANCE.md`.
  **[V]**
- `https://api.semanticscholar.org/graph/v1/paper/search?query=GridPro` — **HTTP 429**, rate
  limited, not retried. **[V]**
- `https://api.core.ac.uk/v3/search/works?q=GridPro` — returns a Cloudflare interstitial without
  an API key. **[V]**
- `https://gridpro.com/sitemap_index.xml` → `page-sitemap.xml` — **115 pages**, of which **35 are
  case studies**; harvested as LEADS only and each resolved to a primary source where one could be
  found (entries 14, 29, 39, 43 and `gridpro-meshes-in-published-cfd.md` §11b all appear in that
  list). `https://www.gridpro.com/resources/papers/` is **404**. **[V]**

**Bulk harvest.** 167 of the 196 OpenAlex works carried an `oa_url`; I downloaded all 167, of
which **83 arrived as PDFs** on the first pass. A second wave recovered 6 MDPI PDFs via
`mdpi-res.com/d_attachment/<journal>/<name>/article_deploy/<name>.pdf?version=<n>` (the route
`gridpro-meshes-in-published-cfd.md` records) and 8 OhioLINK theses via
`etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=<id>&disposition=inline`. **Every one
of the resulting 97 PDFs was grepped for `gridpro` before anything was recorded; 85 matched.**
**[V]**

**Primary documents, by entry** (NTRS and arXiv URLs are given in full; the rest are identified by
DOI or repository accession, each of which I resolved and downloaded):

- 1 `https://mdpi-res.com/d_attachment/ijtpp/ijtpp-10-00005/article_deploy/ijtpp-10-00005.pdf?version=1741613548`
- 2 `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=osu1224705112&disposition=inline`
- 3 `https://ntrs.nasa.gov/api/citations/20110010977/downloads/20110010977.pdf`
- 4 `https://ntrs.nasa.gov/api/citations/19990052582/downloads/19990052582.pdf`
- 5 `https://ntrs.nasa.gov/api/citations/20000120214/downloads/20000120214.pdf`
- 6 `https://ntrs.nasa.gov/api/citations/19950022315/downloads/19950022315.pdf` — **page 11 rendered at 150 and 300 dpi; Figure 1 cropped and extracted**
- 7 `https://ntrs.nasa.gov/api/citations/19950022314/downloads/19950022314.pdf` — **page 14 rendered; Figure 4 cropped and extracted**
- 8 `http://www.scirp.org/journal/PaperDownload.aspx?paperID=62027` — **page 4 rendered; Figure 3's embedded bitmap extracted at 2530x806**
- 9 `https://eprints.gla.ac.uk/103543/7/103543.pdf`
- 10 `https://www.osti.gov/servlets/purl/1830574`
- 11 `https://ntrs.nasa.gov/api/citations/20120017946/downloads/20120017946.pdf`
- 12 `https://ntrs.nasa.gov/api/citations/20010089699/downloads/20010089699.pdf`
- 13 `https://ntrs.nasa.gov/api/citations/20000062308/downloads/20000062308.pdf`
- 14 `https://elib.dlr.de/21745/1/A4.1_CFDsupport_tp_Pre-X_project_Jean_Oswald.pdf`
- 15 `https://ntrs.nasa.gov/api/citations/20080023454/downloads/20080023454.pdf`
- 16 `https://ntrs.nasa.gov/api/citations/20020087944/downloads/20020087944.pdf` — **page 3 rendered**
- 17 `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=toledo1270739741&disposition=inline`
- 18 `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=akron1270860381&disposition=inline`
- 19 `https://ntrs.nasa.gov/api/citations/20120009217/…`, `…/20120011131/…`, `…/20120009201/…`
- 20 `https://ntrs.nasa.gov/api/citations/20010047410/downloads/20010047410.pdf`
- 21 `https://ntrs.nasa.gov/api/citations/19990019396/downloads/19990019396.pdf`
- 22 `https://ntrs.nasa.gov/api/citations/20020085369/downloads/20020085369.pdf`
- 23 `https://ntrs.nasa.gov/api/citations/20020070525/downloads/20020070525.pdf`
- 24 `https://ntrs.nasa.gov/api/citations/20080047695/downloads/20080047695.pdf`
- 25 `https://ntrs.nasa.gov/api/citations/20050040868/downloads/20050040868.pdf`
- 26 `https://ntrs.nasa.gov/api/citations/20010050140/downloads/20010050140.pdf` (NASA/CR-2001-210764; journal version DOI `10.1115/1.1400114`)
- 27 `https://ntrs.nasa.gov/api/citations/19970007342/downloads/19970007342.pdf`
- 28 `https://ntrs.nasa.gov/api/citations/19950022345/downloads/19950022345.pdf`
- 29 `https://ntrs.nasa.gov/api/citations/20100029589/downloads/20100029589.pdf`
- 30 `…send_file/send?accession=osu1258931807`
- 31 `…send_file/send?accession=osu1230064860`
- 32 `…send_file/send?accession=osu1262290700`
- 33-35 `…accession=ucin1054757181`, `ucin1109095348`, `ucin1141413192`
- 36-38 `…accession=toledo1463099661`, `toledo1430491745`, `toledo1272550725`
- 39 `https://mdpi-res.com/d_attachment/jmse/jmse-06-00027/article_deploy/jmse-06-00027.pdf?version=1521424747`
- 40 `…/jmse-06-00051/…?version=1525866986`
- 41 `…/jmse-09-01069/…?version=1632995799`
- 42 `…/aerospace-06-00060/…?version=1558780456`
- 43 `…/applsci-11-08180/…?version=1630663895`
- 44 `https://link.springer.com/content/pdf/10.1007/s12567-025-00655-2.pdf`
- 45 `https://theses.hal.science/tel-05248848/document`
- 46 `https://www.cambridge.org/core/services/aop-cambridge-core/content/view/501F0D86EBA4441305337DA79E946E01/S2633425924000369a.pdf`
- 47 `http://journals.ed.ac.uk/ICLASS_Edinburgh/article/download/6014/7861`
- 48 `https://iopscience.iop.org/article/10.1088/1742-6596/1382/1/012004/pdf`
- 49 `https://ntrs.nasa.gov/api/citations/20160009131/downloads/20160009131.pdf`
- 50 `https://arxiv.org/pdf/2007.06339`
- 51 `https://dspace.zcu.cz/bitstreams/76f22693-7e53-4d51-b704-07c77c12e561/download`
- 52 `https://espace2.etsmtl.ca/id/eprint/32360/1/379%20-%20Numerical%20analysis%20of%20heat-generat.pdf`
- 53 `https://authors.library.caltech.edu/28169/1/cacr170.pdf`
- 54 `https://link.springer.com/content/pdf/10.1007%2F978-3-540-24688-6_97.pdf`
- 55 `https://www.osti.gov/servlets/purl/822313`
- 56 `https://www.osti.gov/servlets/purl/1330623` (+ `1338726`, `1395001`, `1484615`, `1578023`)
- 57 `https://ntrs.nasa.gov/api/citations/19950022351/downloads/19950022351.pdf`
- 58 `https://ntrs.nasa.gov/api/citations/19950022353/downloads/19950022353.pdf`
- §3's ETC2023-369 re-read: `https://www.euroturbo.eu/paper/ETC2023-369.pdf` — **page 7 rendered**

**Secondary, in this repo, referred to rather than re-derived:**
`docs/research/gridpro-meshes-in-published-cfd.md`,
`docs/research/gridpro-blocking-method.md`,
`docs/research/nesting-blocks-at-a-complicated-leading-edge.md`.

## Tried and could not get

- **Anything behind a Cloudflare "Just a moment…" interstitial.** Plain `curl` and WebFetch both
  receive a 5.5-6 KB challenge page. This blocked, among others: `commons.erau.edu` (Lessiau 2003,
  *Numerical Analysis of an Airfoil Response to an Impinging Gust* — an **aerofoil** GridPro case),
  `digitalcommons.calpoly.edu`, `stars.library.ucf.edu`, `repository.lsu.edu` (three LSU
  dissertations), `oaktrust.library.tamu.edu`, `uknowledge.uky.edu`, `asmedigitalcollection.asme.org`
  (the journal versions of entries covered elsewhere, and
  `gridpro-meshes-in-published-cfd.md` §5). **Sending a spoofed browser User-Agent to get past a
  bot check is refused by this environment's policy, was refused here, and must stay refused.**
  **[V]**
- **`https://www.epj-conferences.org/articles/epjconf/pdf/2015/11/epjconf_efm2014_02080.pdf`** —
  779-byte JS/anti-bot stub to `curl`, **HTTP 403** to WebFetch. So *Scalability of the parallel
  CFD simulations of flow past a **fluttering airfoil** in OpenFOAM* (EPJ Web Conf. 92, 02080,
  2015) is **still unread**, exactly as `gridpro-meshes-in-published-cfd.md` recorded, and remains
  the single most on-point unreachable document in both notes. The companion
  `epjconf_efm2016_02106.pdf` (*Numerical and Experimental Study of a Cooling for Vanes in a Small
  Turbine*) failed the same way. **[V]**
- **`hdl.handle.net/2117/*` (UPC/UPCommons)** — eight marine-hydrodynamics items (ReFRESCO AMR,
  NACA0015 hydrofoil cavitation, Delft Twist11, KVLCC2 deep/shallow water, propeller
  boundary-layer, tip-vortex refinement, roll damping) all return a ~560 KB HTML landing page, not
  the bitstream. I did not find the bitstream path. **[V]**
- **`https://api.core.ac.uk/v3/search/works`** — needs an API key; the keyless endpoint returns a
  Cloudflare redirect page. **BASE (`base-search.net`) was not attempted**, because its API
  requires IP registration. **[V]** Both are named in §5 as unclosed.
- **`https://www.osti.gov/servlets/purl/416563`** — *Interactive topology generation and grid viewer
  for GridPro/az3000* (1996, the one OSTI record that is unambiguously vendor work) returns HTML,
  not a PDF. **[V]**
- **TUHH `10.15480/882.3359`** (*Fully automatic design space exploration by RANS computations*) and
  **UQ `10.14264/uql.2017.219`** (*A parametric grid generation tool for the aerodynamic evaluation
  of hypersonic vehicles* — a **thesis about building a GridPro-adjacent tool**) — I could not
  resolve either to a bitstream URL. Both are likely rich and both are unread. **[V]**
- **AIAA ARC** — `10.2514/6.2018-0659` (the vendor's High-Lift CRM paper) and `10.2514/6.2023-3020`
  (*A Shock Fitting Technique For Hypersonic Flows Using Hexahedral Meshes*) remain unread behind
  the paywall, as in the other note. **[V]**
- **NTRS records with no full text**: `20020050562` (X-33 aerothermal **grid-generation issues** —
  by title the most on-point NASA document in the whole search), `20050186801`, `20050186861`.
  **[V]**
- **Figures for most entries.** I rendered pages for entries 6, 7, 8, 16 and for §11b's Figure 7.
  **For every other entry, "what the figure shows" is read from the caption and the surrounding
  text, not from the picture**, and the table says so by being terse. **[V]**

## Named limits

1. **70 is a floor, not a count of the literature, and it is a floor on a different quantity than
   the other note's ten.** That note counted third-party documents with a *visible mesh figure*;
   this one counts documents that *used GridPro at all and could be opened*. The binding limit
   has moved from index coverage to **access**: OpenAlex's full-text filter returned 196 works and
   I could open 97 of them, so **roughly half the known candidate set is unread**, and the
   Cloudflare block is responsible for most of that. **[V]**
2. **OpenAlex's `fulltext.search` is not exhaustive either.** It can only match documents whose
   full text OpenAlex has ingested. A paywalled journal paper that names GridPro once in a methods
   section is still invisible. **The true population remains certainly larger and probably much
   larger.** **[I]**
3. **The census is dominated by two communities.** NASA Glenn turbine heat transfer (entries 4, 5,
   13, 19-27, 29) and the Ohio/Toledo/Cincinnati CAA-and-turbomachinery theses (entries 2, 17, 18,
   30-38) together are **more than a third of the new entries**, and they share authors, advisors
   and in some cases the same grid (entries 33, 34 and 35 all use "the grid generated by Mutnuri
   (2003)"). **Counting them as independent practitioners would be wrong.** **[V]**
4. **Numbers were taken from the text layer of a PDF.** Where `pdftotext` ran on a 1990s scan the
   layer is noisy — entry 16's author line is illegible in the scan and was taken from the NTRS
   record instead, and entry 27's "283 blocks" is read from a line that also contains unrelated
   text. **Any number here should be re-read in the source before it is quoted.** **[V]**
5. **The aggregate counts in §4a are my own tally of my own table**, not a measurement by a
   script. They are re-derivable by counting the non-empty cells in that column and no more
   reliable than that. **[V]**
6. **"Quality metric" is my classification, not the authors'.** I counted a stretching-ratio bound
   as a quality metric and a y+ bound as a first-cell statement rather than a quality metric. A
   different line would move the figure in §4b by several. The rule applied is stated so it can be
   disagreed with: **a quality metric is a statement about cell SHAPE or about solution
   convergence with refinement; y+ and cell counts are not.** **[V]**
7. **Three figures were extracted and the rest are pointers.** The rule applied, per the brief:
   **extract only where the source is open-licence**, which here meant two NASA records whose own
   `copyright.determinationType` is `GOV_PUBLIC_USE_PERMITTED` and one article whose publisher page
   states CC BY 4.0. Everything paywalled or all-rights-reserved — including every ASME, AIAA,
   Springer, Elsevier, IOP, Cambridge and SAGE item above — is recorded as a **pointer only, with
   page and figure number**. **[V]**
8. **Nothing here was checked against a GridPro installation**, and no claim about what GridPro
   *can* do rests on anything but what these authors wrote. Where a document contradicts another
   — entry 40's "good quality grids, **most of the time**" against entry 41's "the resulting grids
   are all of high quality" — both are quoted and neither is resolved. **[V]**
