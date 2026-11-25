# Figure index — block counts, node counts and tags

One row per file in this directory. Built to answer one question fast: **which picture
do I compare against?** Sort or grep by block count, by tag, or by entry.

The census this indexes is `../gridpro-mesh-data-in-publications.md`; the per-file
citation, page and licence are in `PROVENANCE.md`; `gallery.html` is the visual version
of this same table.

## Read the two count columns differently

- **blocks (on the figure)** — stated by the figure itself or by its own caption, so it
  describes THIS picture. Blank means the figure does not say.
- **blocks (document)** and **cells / points (document)** — taken from the paper’s text
  via the census table. They describe the CASE the paper reports, which is usually but
  **not always** the exact mesh in this particular figure: a paper that states 2.46 M
  cells may also print a coarse topology sketch, and both rows carry the same document
  number. Treat it as the document’s number, not the picture’s measurement.
- **per-block node counts** appear for the two figures that print them; they are
  readings off the picture, listed in full at the end.

## How the tags were assigned

- `monochrome-line-art` and `multi-colour` are **MEASURED**: each file was quantised to
  24 colours and the saturated regions covering ≥2% of the image counted. Zero such
  regions → `monochrome-line-art`; four or more → `multi-colour`.
- `coloured-by-block` is **VERIFIED BY EYE** and narrower than `multi-colour`: a figure
  can be multi-colour because it carries a contour field or a CAD rendering. It is
  applied only to files from the documents confirmed in the census’s §4c, and only
  where the file actually carries colour — so it tags **files**, not documents. Three of
  the twelve documents §4c names (entries 19, 26 and 33) have no file here that measures
  as coloured, because the kept crop is pale or is a different panel.
- Every other tag is derived from the filename and caption text, so it is a **keyword**
  match, not a judgement: `far-field` means the words are there, not that the figure
  resolves the far field well.

## The table

| # | figure | blocks (on the figure) | blocks (document) | cells / points (document) | wall / y+ (document) | tags | file |
|---|---|---|---|---|---|---|---|
| 02 | Fig. 3.1 | — | 31 (11 + 20) | 2,461,740 (709,900 stator + 1,751,840 rotor) | 1e-5 m; y+ ≈ 0.38 | `topology-only` `turbomachinery` | `entry02-luk2008-fig3.1-stator-grid-topology.png` |
| 02 | Fig. 3.2 | — | 31 (11 + 20) | 2,461,740 (709,900 stator + 1,751,840 rotor) | 1e-5 m; y+ ≈ 0.38 | `multi-colour` `topology-only` `turbomachinery` | `entry02-luk2008-fig3_2-rotor-grid-topology.png` |
| 02 | Fig. 4.4 | — | 31 (11 + 20) | 2,461,740 (709,900 stator + 1,751,840 rotor) | 1e-5 m; y+ ≈ 0.38 | `h-grid` `monochrome-line-art` `o-grid` `turbomachinery` | `entry02-luk2008-fig4.4-h-o-two-blade-row-grid.png` |
| 02 | Fig. 4.3 | — | 31 (11 + 20) | 2,461,740 (709,900 stator + 1,751,840 rotor) | 1e-5 m; y+ ≈ 0.38 | `multi-colour` `turbomachinery` `wall-spacing` | `entry02-luk2008-fig4_3-stator-rotor-grid-clustered-matched-interface.png` |
| 04 | Fig. 3 | — | 2298 → 140 (Method of Weakest Descent) | not stated in what I read | y+ < 1.0 at first point | `monochrome-line-art` `turbomachinery` | `entry04-heidmann1999-fig3-blade-to-blade-multiblock-grid.png` |
| 04 | Fig. 4 | — | 2298 → 140 (Method of Weakest Descent) | not stated in what I read | y+ < 1.0 at first point | `monochrome-line-art` `near-field-zoom` | `entry04-heidmann1999-fig4-leading-edge-grid-zoom.png` |
| 05 | Fig. 2 | — | 162 → 13 | 106,496; 128 cells in the hole exit | y+ < 1 | `monochrome-line-art` `turbomachinery` | `entry05-garg2000-fig2-vki-rotor-viscous-grid.png` |
| 06 | Fig. 1 | 97 blocks | 97 | not stated | — | `2d-aerofoil` `monochrome-line-art` | `entry06-vatsa1995-fig1-97block-multielement-airfoil.png` |
| 06 | Fig. 1 | 97 blocks | 97 | not stated | — | `2d-aerofoil` `monochrome-line-art` | `entry06-vatsa1995-fig1-and-fig2-97block-airfoil-and-fa18-forebody-page.png` |
| 06 | Fig. 4 | 19 blocks | 97 | not stated | — | `monochrome-line-art` `topology-only` | `entry06-vatsa1995-fig4-grid-topology-19-block-supersonic-transport.png` |
| 07 | Fig. 10 | — | — | — | — | `monochrome-line-art` `vendor` | `entry07-eiseman1995-fig10-field-about-cloth-fibers-grid-generated.png` |
| 07 | Fig. 3 | — | — | — | — | `monochrome-line-art` `vendor` | `entry07-eiseman1995-fig3-half-full-fuel-tank-automobile-this.png` |
| 07 | Fig. 4 | — | — | — | — | `2d-aerofoil` `far-field` `monochrome-line-art` `vendor` | `entry07-eiseman1995-fig4-airfoil-in-ground-effect.png` |
| 08 | Fig. 3 | — | ~30 drawn | 2.5 M (4.5 M unsteady, Star-CCM+) | y+ < 1.0, nominally 0.1; stre… | `coloured-by-block` `multi-colour` | `entry08-repko2016-fig3-grid-coloured-by-block.png` |
| 10 | Fig. 3 | — | 25,278 | not read | 5e-6 m wall-normal, stretch r… | `internal-flow` `multi-colour` | `entry10-nielsen2021-fig3-body-fitted-grid-insert-cavity.png` |
| 11 | Slide 7 | — | not stated | 18,217,949 points / 18,113,216 cells | y+ < 1 on entire geometry | `monochrome-line-art` | `entry11-schwing2012-slide7-capsule-grid-overview.png` |
| 11 | Slide 8 | — | not stated | 18,217,949 points / 18,113,216 cells | y+ < 1 on entire geometry | `monochrome-line-art` | `entry11-schwing2012-slide8-capsule-symmetry-plane-grid.png` |
| 12 | Fig. 5 | — | 365 non-merged | 2.2 M points + 1.4 M wake | — | `monochrome-line-art` | `entry12-papadopoulos2001-fig5-multi-layer-grid-generation-strategy.png` |
| 12 | Fig. 7 | — | 365 non-merged | 2.2 M points + 1.4 M wake | — | `merge` `monochrome-line-art` | `entry12-papadopoulos2001-fig7-orbiter-365-nonmerged-blocks.png` |
| 13 | Fig. 2 | 12 blocks | 282 → 22; a merge study 124 → 992 / 1776 / 79… | not stated | y+ named as the sizing criter… | `monochrome-line-art` `topology-only` | `entry13-rigby2000-fig2-twelve-block-circle-in-box-topology.png` |
| 13 | Fig. 3 | — | 282 → 22; a merge study 124 → 992 / 1776 / 79… | not stated | y+ named as the sizing criter… | `merge` `monochrome-line-art` `topology-only` | `entry13-rigby2000-fig3-block-merge-stages.png` |
| 13 | Fig. 9 | 282→22 blocks (merge) | 282 → 22; a merge study 124 → 992 / 1776 / 79… | not stated | y+ named as the sizing criter… | `merge` `monochrome-line-art` | `entry13-rigby2000-fig9-282-blocks-merged-to-22.png` |
| 14 | Fig. 4 | — | 376 and 548 | 1,044,992 (M25); 1,428,992 (M17.75); ~700,0… | y+ < 1 | `monochrome-line-art` | `entry14-oswald2005-fig4-symmetry-plane-basic-adapted-grid-sting.png` |
| 14 | Fig. 5.6 | — | 376 and 548 | 1,044,992 (M25); 1,428,992 (M17.75); ~700,0… | y+ < 1 | `3d` | `entry14-oswald2005-fig5-6-prex-surface-grid-and-bodyflap.png` |
| 17 | Fig. 4.13a | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `2d-aerofoil` `coloured-by-block` | `entry17-allampalli2010-fig4-13a-grid-joukowski-airfoil-case.png` |
| 17 | Fig. 4.13b | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `2d-aerofoil` `coloured-by-block` `multi-colour` | `entry17-allampalli2010-fig4-13b-grid-joukowski-airfoil-case.png` |
| 17 | Fig. 4.18 | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `2d-aerofoil` `3d` `coloured-by-block` `multi-colour` `near-field-zoom` `refinement-series` | `entry17-allampalli2010-fig4-18-levels-new-grid-blocks-near-airfoil.png` |
| 17 | Fig. 4.2 | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `coloured-by-block` `multi-colour` | `entry17-allampalli2010-fig4-2-grid-acoustic-scattering-benchmark-problem.png` |
| 17 | Fig. 4.27 | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `3d` `coloured-by-block` `multi-colour` | `entry17-allampalli2010-fig4-27-grid-3d-workshop-problem.png` |
| 17 | Fig. 5.1 | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `2d-aerofoil` `coloured-by-block` `multi-colour` | `entry17-allampalli2010-fig5-1-complete-grid-naca0012-airfoil.png` |
| 17 | Fig. 5.17 | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `2d-aerofoil` `coloured-by-block` `multi-colour` | `entry17-allampalli2010-fig5-17-complete-grid-naca64a010-airfoil.png` |
| 17 | Fig. 5.3 | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `coloured-by-block` `multi-colour` `wall-spacing` | `entry17-allampalli2010-fig5-3-grid-clustering-approximate-shock-location-grid.png` |
| 17 | Fig. 6.1 | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `coloured-by-block` `internal-flow` `multi-colour` | `entry17-allampalli2010-fig6-1-complete-grid-flow-over-flat-plate.png` |
| 17 | Fig. 6.15 | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `coloured-by-block` `cylinder` `multi-colour` | `entry17-allampalli2010-fig6-15-complete-grid-2d-cylinder-case.png` |
| 17 | Fig. 6.16 | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `coloured-by-block` `cylinder` `multi-colour` `near-field-zoom` | `entry17-allampalli2010-fig6-16-close-up-view-grid-near-cylinder.png` |
| 17 | Fig. 6.2 | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `coloured-by-block` `internal-flow` `multi-colour` `near-field-zoom` | `entry17-allampalli2010-fig6-2-grid-near-flat-plate.png` |
| 17 | Fig. 6.3 | — | 95 (Grid 3) | Grid 3 = 51,465 points | — | `coloured-by-block` `internal-flow` `multi-colour` `near-field-zoom` | `entry17-allampalli2010-fig6-3-grid-near-leading-edge-flat-plate.png` |
| 18 | Fig. 5.4 | 506 blocks | 506 (2-D), 924 (3-D) | ~1.9 M (DES), ~3 M (2-D LES), "million poin… | — | `coloured-by-block` `multi-colour` | `entry18-brown2010-fig5.4-506-block-grid-coloured-by-block.png` |
| 18 | Fig. 5.5 | — | 506 (2-D), 924 (3-D) | ~1.9 M (DES), ~3 M (2-D LES), "million poin… | — | `3d` `monochrome-line-art` `topology-only` | `entry18-brown2010-fig5.5-topology-with-internal-surfaces.png` |
| 18 | Fig. 5.14 | — | 506 (2-D), 924 (3-D) | ~1.9 M (DES), ~3 M (2-D LES), "million poin… | — | `3d` `coloured-by-block` `internal-flow` `multi-colour` | `entry18-brown2010-fig5_14-3-d-grid-osu-nozzle-dj.png` |
| 18 | Fig. 5.16 | — | 506 (2-D), 924 (3-D) | ~1.9 M (DES), ~3 M (2-D LES), "million poin… | — | `3d` `coloured-by-block` `multi-colour` | `entry18-brown2010-fig5_16-computational-grid-3-d-les-simulations.png` |
| 18 | Fig. 5.3 | — | 506 (2-D), 924 (3-D) | ~1.9 M (DES), ~3 M (2-D LES), "million poin… | — | `coloured-by-block` `multi-colour` | `entry18-brown2010-fig5_3-computational-grid-axisymmetric-simulations-osu.png` |
| 19 | Fig. 17 | — | 100 (GE2), 16 (flat plate, each 1664-point ar… | 610,000 / 608,000 points; 2,313,984 very fi… | y+ ≈ 1 | `monochrome-line-art` `turbomachinery` | `entry19-ameri2012-fig17-three-dimensional-blade-grid-e3-blade.png` |
| 19 | Fig. 2 | 16 blocks | 100 (GE2), 16 (flat plate, each 1664-point ar… | 610,000 / 608,000 points; 2,313,984 very fi… | y+ ≈ 1 | `internal-flow` | `entry19-ameri2012-fig2-flat-plate-16-block-grid.png` |
| 19 | Fig. 3 | — | 100 (GE2), 16 (flat plate, each 1664-point ar… | 610,000 / 608,000 points; 2,313,984 very fi… | y+ ≈ 1 | `3d` | `entry19-ameri2012-fig3-ge2-midspan-and-3d-grids.png` |
| 20 | Fig. 1 | — | 28 → 5 | 55,296 viscous; 112 cells around the blade | avg y+ 0.26, "less than half" | `monochrome-line-art` | `entry20-garg2001-fig1-spanwise-multiblock-viscous-grid.png` |
| 21 | Fig. 2 | — | merged to 64 | 1,489,920 | largest y+ at a cell centre l… | `internal-flow` `monochrome-line-art` `turbomachinery` | `entry21-rigby1998-fig2-ribbed-passage-grid-x0.png` |
| 21 | Fig. 3 | — | merged to 64 | 1,489,920 | largest y+ at a cell centre l… | `internal-flow` `monochrome-line-art` `turbomachinery` | `entry21-rigby1998-fig3-ribbed-passage-grid-y0.png` |
| 22 | Fig. 2 | — | not stated | 340,000 / 523,000 / 1,060,000 | avg y+ ≈ 1; stretching ratio … | `monochrome-line-art` `topology-only` | `entry22-ameri2002-fig2-topology-three-grids-and-yplus.png` |
| 23 | Fig. 1 | — | not stated | 160,128 viscous from 92,928 inviscid; 224 c… | y+ < 0.5 | `monochrome-line-art` `near-field-zoom` | `entry23-garg2002-fig1-spanwise-grid-with-hole-exit-detail.png` |
| 24 | Fig. 9 | — | not stated | ~2.5 M per case, ~300,000 after one multigr… | y+ < 1.0; stretching ratios <… | `coloured-by-block` `multi-colour` | `entry24-heidmann2008-fig9-grid-coloured-by-block.png` |
| 26 | Fig. 3 | — | not stated | 1.2 M sharp tip, 1.4 M, 1.8 M with strip | y+ stated as the first-cell c… | `near-field-zoom` `turbomachinery` | `entry26-ameri2001-fig3-blade-tip-grid-construction.png` |
| 27 | — | — | 283 | ~2 M | — | `internal-flow` `junction` `monochrome-line-art` | `entry27-steinthorsson1996-fig3ab-branched-duct-grid.png` |
| 27 | — | — | 283 | ~2 M | — | `monochrome-line-art` | `entry27-steinthorsson1996-fig3cd-corner-and-pin-fin-grid.png` |
| 28 | Fig. 2 | — | not stated | not stated | — | `monochrome-line-art` `topology-only` | `entry28-steinthorsson1995-fig2-multiblock-topology.png` |
| 28 | Fig. 3 | — | not stated | not stated | — | `monochrome-line-art` | `entry28-steinthorsson1995-fig3-centre-region-grid.png` |
| 28 | Fig. 4 | — | not stated | not stated | — | `2d-aerofoil` `monochrome-line-art` | `entry28-steinthorsson1995-fig4-transonic-naca0012-adapted-structured-grid.png` |
| 29 | Fig. 1 | — | not stated | ~1.8 M | — | `coloured-by-block` `multi-colour` `turbomachinery` | `entry29-ameri2009-fig1-rotor37-grid-two-views.png` |
| 30 | Fig. 2.2 | — | 20 rotor + 11 stator; 19 for the flat plate | 2,461,740 (1,751,840 rotor); 156 radial x 1… | y+ < 1; y+ ≈ 1 on the plate | `internal-flow` `monochrome-line-art` | `entry30-shyam2009-fig2_2-mesh-2d-flow-over-flat-plate.png` |
| 30 | Fig. 4.3 | — | 20 rotor + 11 stator; 19 for the flat plate | 2,461,740 (1,751,840 rotor); 156 radial x 1… | y+ < 1; y+ ≈ 1 on the plate | `monochrome-line-art` | `entry30-shyam2009-fig4_3-mesh-35-cooling-hole.png` |
| 30 | Fig. 5.1 | — | 20 rotor + 11 stator; 19 for the flat plate | 2,461,740 (1,751,840 rotor); 156 radial x 1… | y+ < 1; y+ ≈ 1 on the plate | `monochrome-line-art` `turbomachinery` | `entry30-shyam2009-fig5.1-rotor-grid.png` |
| 31 | Fig. 4.2 | — | 440 | ~0.4 M (75% hot gas path) | y+ ≤ 1 | `multi-colour` `turbomachinery` | `entry31-osu2009-fig4.2-c3x-vane-grid.png` |
| 32 | Fig. 6.8 | — | multiple "regions of interest" | 746,554 / 1,260,184 (tet comparators); hex … | y+ 15-40 (wall-function model… | `multi-colour` | `entry32-shankara2009-fig6.8-hexahedral-cut-section.png` |
| 32 | Fig. 7.1 | — | multiple "regions of interest" | 746,554 / 1,260,184 (tet comparators); hex … | y+ 15-40 (wall-function model… | `monochrome-line-art` `turbomachinery` | `entry32-shankara2009-fig7_1-computational-grid-vki-blade.png` |
| 33 | Fig. 5.2 | — | 12 (O- and H- dual topology) | 750,000 points (cylinder) | non-uniform wall-normal clust… | `monochrome-line-art` `near-field-zoom` `turbomachinery` | `entry33-ayyalasomayajula2003-fig5_2-enlarged-view-grid-around-mid-blade.png` |
| 33 | Fig. 6.6 | — | 12 (O- and H- dual topology) | 750,000 points (cylinder) | non-uniform wall-normal clust… | `cylinder` `monochrome-line-art` `o-grid` | `entry33-ayyalasomayajula2003-fig6.6-ogrid-around-cylinder.png` |
| 33 | Fig. 6.14 | 12 blocks | 12 (O- and H- dual topology) | 750,000 points (cylinder) | non-uniform wall-normal clust… | `c-grid` `monochrome-line-art` `topology-only` | `entry33-ayyalasomayajula2003-fig6_14-12-block-structured-periodic-grid-hpt.png` |
| 34 | Fig. 4.1 | 12 blocks | 12 | 2 M points, 32 spanwise planes | — | `coloured-by-block` `multi-colour` `turbomachinery` | `entry34-singh2005-fig4.1-twelve-block-lpt-cascade-grid.png` |
| 35 | Fig. 1 | 8 blocks | 8 (cylinder), 24 (partitioned) | 3.9 M points (48 spanwise); 2 M for the cas… | ~70% of points in the near-wa… | `cylinder` `monochrome-line-art` | `entry35-kasliwal2006-fig1-eight-block-cylinder-grid.png` |
| 35 | Fig. 16 | — | 8 (cylinder), 24 (partitioned) | 3.9 M points (48 spanwise); 2 M for the cas… | ~70% of points in the near-wa… | `monochrome-line-art` `refinement-series` `topology-only` | `entry35-kasliwal2006-fig16-fine-grid-block-layout.png` |
| 35 | Fig. 34 | — | 8 (cylinder), 24 (partitioned) | 3.9 M points (48 spanwise); 2 M for the cas… | ~70% of points in the near-wa… | `far-field` `topology-only` | `entry35-kasliwal2006-fig34-multi-block-structured-block-layout-computational.png` |
| 36 | Fig. 1.3 | — | a quarter patterned 3x; eight 3- and 5-way si… | 21^3 per block; a 201^2 case; 41^3-point bl… | — | — | `entry36-mansouri2016-fig1-3-typical-form-structured-grid.png` |
| 36 | Fig. 1.6 | — | a quarter patterned 3x; eight 3- and 5-way si… | 21^3 per block; a 201^2 case; 41^3-point bl… | — | `coloured-by-block` `multi-colour` `singularity` | `entry36-mansouri2016-fig1-6-typical-form-grid-discontinuities-singularities-around.png` |
| 36 | Fig. 1.8 | 3-way singularity, 5-way singularity | a quarter patterned 3x; eight 3- and 5-way si… | 21^3 per block; a 201^2 case; 41^3-point bl… | — | `monochrome-line-art` `singularity` | `entry36-mansouri2016-fig1-8-grid-blocks-3-way-b-3.png` |
| 36 | Fig. 4.1 | — | a quarter patterned 3x; eight 3- and 5-way si… | 21^3 per block; a 201^2 case; 41^3-point bl… | — | `monochrome-line-art` `singularity` | `entry36-mansouri2016-fig4-1-cartesian-singular-b-grid-blocks-evaluate.png` |
| 36 | Fig. 4.6 | 3-way singularity; 4-way singularity; 5-way… | a quarter patterned 3x; eight 3- and 5-way si… | 21^3 per block; a 201^2 case; 41^3-point bl… | — | `monochrome-line-art` `singularity` | `entry36-mansouri2016-fig4-6-three-four-and-five-way-singularities.png` |
| 36 | Fig. 4.15 | 3-way singularity | a quarter patterned 3x; eight 3- and 5-way si… | 21^3 per block; a 201^2 case; 41^3-point bl… | — | `coloured-by-block` `multi-colour` `singularity` | `entry36-mansouri2016-fig4.15-three-way-singularity-grid.png` |
| 36 | Fig. 4.17 | 5-way singularity | a quarter patterned 3x; eight 3- and 5-way si… | 21^3 per block; a 201^2 case; 41^3-point bl… | — | `coloured-by-block` `multi-colour` `singularity` | `entry36-mansouri2016-fig4.17-five-way-singularity-grid.png` |
| 36 | Fig. 5.10 | — | a quarter patterned 3x; eight 3- and 5-way si… | 21^3 per block; a 201^2 case; 41^3-point bl… | — | `monochrome-line-art` `wall-spacing` | `entry36-mansouri2016-fig5-10-clustered-grid-using-0-692.png` |
| 37 | Fig. 4.17 | — | 5 blocks, 2 singular points | 41^3 points | — | `coloured-by-block` | `entry37-ingraham2015-fig4-17-multiblock-grid-parallel-test-cases-colored.png` |
| 37 | Fig. 4.44 | — | 5 blocks, 2 singular points | 41^3 points | — | `coloured-by-block` `refinement-series` `singularity` | `entry37-ingraham2015-fig4-44-coarsest-singular-grid-grid-singularity-test.png` |
| 37 | Fig. 4.17 | coloured by block ID | 5 blocks, 2 singular points | 41^3 points | — | — | `entry37-ingraham2015-fig4.17-grid-coloured-by-block-index.png` |
| 38 | Fig. 6.2 | — | 104 | 327,184 points | — | `far-field` `monochrome-line-art` | `entry38-heminger2010-fig6-2-yz-x-slice-far-eld-grid.png` |
| 38 | Fig. 6.4 | — | 104 | 327,184 points | — | `monochrome-line-art` `wall-spacing` | `entry38-heminger2010-fig6-4-xy-z-slice-showing-piston-edge.png` |
| 38 | Fig. 6.4 | — | 104 | 327,184 points | — | `monochrome-line-art` `wall-spacing` | `entry38-heminger2010-fig6.4-6.5-piston-grid-clustering.png` |
| 39 | Fig. 4 | — | not stated | 1.1 → 26.8 M, five grids | max y+ < 1 on all five | `3d` `internal-flow` `monochrome-line-art` `turbomachinery` | `entry39-baltazar2018-fig4-ducted-propeller-surface-grids.png` |
| 40 | Fig. 1 | — | "a standard block topology developed at MARIN" | not stated in what I read | y+ < 1, no wall functions | `far-field` `monochrome-line-art` `turbomachinery` | `entry40-maljaars2018-fig1-propeller-domain-and-grid.png` |
| 41 | Fig. 12 | — | "initial topology (block structure)" fixed, r… | 460,000 / 1.5 M / 3.7 M per demi-hull | — | `3d` `monochrome-line-art` `near-field-zoom` | `entry41-harries2021-fig12-close-up-panel-mesh-hull-free.png` |
| 41 | Fig. 13 | — | "initial topology (block structure)" fixed, r… | 460,000 / 1.5 M / 3.7 M per demi-hull | — | `o-grid` | `entry41-harries2021-fig13-bow-mesh-two-hulls-superposed.png` |
| 43 | Fig. 2 | — | not stated | 940,000; head insensitive beyond ~3 M | smooth-wall | `monochrome-line-art` | `entry43-wu2021-fig2-centrifugal-pump-grid.png` |
| 44 | Fig. 9 | — | "massively multi-blocked" | > 14.5 M | first cell 2e-6 m | `coloured-by-block` `multi-colour` | `entry44-ledermann2025-fig9-mistral-multiblock-mesh.png` |
| 47 | Fig. 1c | — | not stated | 5.5 M | min 5 µm at the needle tip, a… | `internal-flow` `near-field-zoom` | `entry47-mcginn2021-fig1c-injector-nozzle-mesh-detail.png` |
| 49 | Fig. 5 | — | GridPro near the injector + Pointwise h-blocks | not stated in what I read | y+ → 1 target; growth rates 5… | `monochrome-line-art` `topology-only` | `entry49-drozda2016-fig5-strut-grid-block-topology.png` |
| 49 | Fig. 6 | — | GridPro near the injector + Pointwise h-blocks | not stated in what I read | y+ → 1 target; growth rates 5… | `refinement-series` | `entry49-drozda2016-fig6-elements-coarse-grid-ramp-simulations-each.png` |
| 50 | Fig. 4 | — | hexahedral, GridPro | not stated | — | `monochrome-line-art` | `entry50-reschke2020-fig4-radial-slice-of-mesh.png` |
| 51 | Obr. 6.4 | — | quadrilateral blocks; "four edges from each i… | not stated | y+ in (0.1, 4), average ≈ 1 | `topology-only` `turbomachinery` `wall-spacing` | `entry51-kleckova2019-obr6.4-blade-topology-and-bl-settings.png` |
| 51 | Obr. 6.5 | — | quadrilateral blocks; "four edges from each i… | not stated | y+ in (0.1, 4), average ≈ 1 | `wall-spacing` | `entry51-kleckova2019-obr6.5-leading-and-trailing-edge-bl-mesh.png` |
| 53 | Fig. 1 | — | 38, 148, 10, 3 | 48,000 and 192,000 | — | — | `entry53-hauser1999-fig1-x33-multiblock-grid.png` |
| 55 | Fig. 6 | — | — | not stated | — | `monochrome-line-art` | `entry55-doe2003-fig6-structured-grid-test-case.png` |
| 56 | Fig. 1 | — | GridPro builds the valve/port parts overlaid … | not stated | — | `o-grid` | `entry56-lanl2016-fig1-valve-overlaying-gridpro-grid.png` |
| 57 | Fig. 2 | — | — | — | — | `monochrome-line-art` `topology-only` `vendor` | `entry57-cheng1995-fig2-topology-components-most-basic-component-loop4.png` |
| 57 | Fig. 3 | — | — | — | — | `internal-flow` `junction` `monochrome-line-art` `topology-only` `vendor` | `entry57-cheng1995-fig3-6tube-block-boundaries.png` |
| 57 | Fig. 4 | — | — | — | — | `internal-flow` `junction` `monochrome-line-art` `topology-only` `vendor` | `entry57-cheng1995-fig4-5tube-block-boundaries.png` |
| 57 | Fig. 5 | — | — | — | — | `internal-flow` `junction` `monochrome-line-art` `vendor` | `entry57-cheng1995-fig5-4tube-and-3tube-grids.png` |
| 58 | Fig. 2 | 3 blocks | — | — | — | `3d` `monochrome-line-art` `vendor` | `entry58-lu1995-fig2-three-block-hexagon-grid.png` |
| 58 | Fig. 3 | 1 block | — | — | — | `internal-flow` `monochrome-line-art` `vendor` | `entry58-lu1995-fig3-single-block-2d-pipe.png` |
| 58 | Fig. 4 | 2 blocks | — | — | — | `2d-aerofoil` `monochrome-line-art` `vendor` | `entry58-lu1995-fig4-two-block-grid-around-supercircle.png` |
| 58 | Fig. 5 | 1 block | — | — | — | `3d` `monochrome-line-art` `vendor` | `entry58-lu1995-fig5-half-single-block-volume-grid-inside-torus.png` |
| 58 | Fig. 6 | 7 blocks | — | — | — | `3d` `monochrome-line-art` `vendor` | `entry58-lu1995-fig6-seven-block-volume-grid-inside-sphere.png` |
| 71 | Fig. 1 | — | "several topologically rectangular blocks" pe… | not stated | not stated | `monochrome-line-art` `refinement-series` | `entry71-nasa1994-fig1-grid-system-three-levels-coarse.png` |
| 71 | Fig. 6 | — | "several topologically rectangular blocks" pe… | not stated | not stated | `2d-aerofoil` `monochrome-line-art` `refinement-series` | `entry71-nasa1994-fig6-refined-grid-around-naca0012-airfoil-m.png` |
| 72 | Fig. 1 | 12 blocks | 12 (O-in-H); 3 (NACA0012 cascade, merging to … | not stated | not stated | `monochrome-line-art` | `entry72-nasa1993-fig1-multiblock-grid-system-12-blocks.png` |
| 72 | Fig. 10 | — | 12 (O-in-H); 3 (NACA0012 cascade, merging to … | not stated | not stated | `internal-flow` `monochrome-line-art` `turbomachinery` | `entry72-nasa1993-fig10-grid-system-radial-turbine-coolant-passage.png` |
| 73 | Fig. 3 | — | not stated | not stated | not stated | `multi-colour` | `entry73-nasa2013-fig3-typical-three-dimensional-grid-vspt-as.png` |
| §03 | Fig. 1 | — | — | — | — | `3d` `far-field` | `othernote03-candler2010-fig1-several-images-surface-grid-shock-adapted.png` |

## The two figures that print a per-block node count **[V]**

- `entry18-brown2010-fig5_3-computational-grid-axisymmetric-simulations-osu.png` — block node counts printed on the figure: 81x81, 142x81, 241x211, and a 19x19 actuator block
- `entry72-nasa1993-fig1-multiblock-grid-system-12-blocks.png` — blocks 1/2/3 of Fig. 2 on the same page: 49x41, 57x41, 49x41 nodes (printed on the figure)

## Tag counts

| tag | files | how |
|---|---|---|
| `monochrome-line-art` | 66 | measured |
| `multi-colour` | 30 | measured |
| `coloured-by-block` | 27 | verified by eye |
| `turbomachinery` | 20 | keyword in filename/caption |
| `internal-flow` | 17 | keyword in filename/caption |
| `topology-only` | 16 | keyword in filename/caption |
| `3d` | 13 | keyword in filename/caption |
| `vendor` | 12 | keyword in filename/caption |
| `2d-aerofoil` | 11 | keyword in filename/caption |
| `near-field-zoom` | 10 | keyword in filename/caption |
| `wall-spacing` | 7 | keyword in filename/caption |
| `singularity` | 7 | keyword in filename/caption |
| `refinement-series` | 6 | keyword in filename/caption |
| `far-field` | 5 | keyword in filename/caption |
| `o-grid` | 4 | keyword in filename/caption |
| `cylinder` | 4 | keyword in filename/caption |
| `junction` | 4 | keyword in filename/caption |
| `merge` | 3 | keyword in filename/caption |
| `h-grid` | 1 | keyword in filename/caption |
| `c-grid` | 1 | keyword in filename/caption |

**115 files.** 21 state a block count on the
figure itself; the rest carry only their document’s number, or none.
