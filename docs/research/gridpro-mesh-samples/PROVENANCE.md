# Provenance of the extracted GridPro mesh figures

One block per source document, then one line per file taken from it. Every figure in this
directory was opened and looked at before it was kept; candidates that turned out to be a
plot, a photograph, a CAD rendering or an outline with no grid lines were discarded and are
not here. The census that these illustrate is `../gridpro-mesh-data-in-publications.md`.

## The two licence classes

The first version of this file had only class A, because only open-licence figures were
extracted. This set is larger and introduces class B, so both are stated:

- **(A) Redistributable** — a US Government work (NASA via NTRS, DOE via OSTI) or an
  explicit open licence (CC-BY). The evidence is named on each document block.
- **(B) Openly downloadable, rights reserved** — university theses on institutional
  repositories, technical reports and conference PDFs served openly with no open licence
  stated. These are kept as a **local research copy for this repository’s own
  mesh-design work**; the rights holder is the author or publisher named in the citation,
  and they are not relicensed by being here.

No paywall was circumvented and no bot check was bypassed to obtain any file here.

## Extraction method

Two routes, chosen per figure. Where the page carried the figure as its own embedded
bitmap, `pdfimages` pulled that bitmap at its native resolution. Otherwise `pdftoppm`
rendered the page (200-300 dpi) and the figure was cropped from it; a file whose name ends
`-page` is a whole rendered page kept deliberately, because its figures and their captions
read together. Every file was then trimmed of white margin, reduced to at most 1800 px on
the long edge, and PNG-optimised; line art that was already monochrome was stored as
grayscale. Nothing was redrawn, recoloured or retouched.

## entry02 — `luk2008` — class B

D. H.-F. Luk, *Steady Heat Transfer Predictions For A Highly Loaded Single Stage Turbine With Flat Tip*, MS thesis, The Ohio State University, 2008, OhioLINK `osu1224705112`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=osu1224705112&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry02-luk2008-fig3.1-stator-grid-topology.png` — figure 3.1 of that document, cropped to the figure.
- `entry02-luk2008-fig3_2-rotor-grid-topology.png` — PDF page 31, 1145x880 px. Caption(s): “Figure 3.2: Rotor Grid Topology”
- `entry02-luk2008-fig4_3-stator-rotor-grid-clustered-matched-interface.png` — PDF page 38, 1180x1068 px. Caption(s): “Figure 4.3: Stator and rotor grid clustered and matched at the interface”
- `entry02-luk2008-fig4.4-h-o-two-blade-row-grid.png` — figure 4.4 of that document, cropped to the figure.

## entry04 — `heidmann1999` — class A

J. D. Heidmann, D. L. Rigby, A. A. Ameri, *A Three-Dimensional Coupled Internal/External Simulation of a Film-Cooled Turbine Vane*, NASA/TM-1999-209078 (99-GT-186), NTRS `19990052582`

- Source PDF: `https://ntrs.nasa.gov/api/citations/19990052582/downloads/19990052582.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry04-heidmann1999-fig3-blade-to-blade-multiblock-grid.png` — figure 3 of that document, cropped to the figure.
- `entry04-heidmann1999-fig4-leading-edge-grid-zoom.png` — figure 4 of that document, cropped to the figure.

## entry05 — `garg2000` — class A

V. K. Garg, *Modeling Film-Coolant Flow Characteristics at the Exit of Shower-Head Holes*, NASA/CR-2000-210510, NTRS `20000120214`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20000120214/downloads/20000120214.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry05-garg2000-fig2-vki-rotor-viscous-grid.png` — figure 2 of that document, cropped to the figure.

## entry06 — `vatsa1995` — class A

V. N. Vatsa, M. D. Sanetrik, E. B. Parlette, *Block-structured grids for complex aerodynamic configurations: Current status*, NASA CP-3291, 1995, NTRS `19950022315`

- Source PDF: `https://ntrs.nasa.gov/api/citations/19950022315/downloads/19950022315.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry06-vatsa1995-fig1-97block-multielement-airfoil.png` — figure 1 of that document, cropped to the figure.
- `entry06-vatsa1995-fig1-and-fig2-97block-airfoil-and-fa18-forebody-page.png` — figure 1 of that document, cropped to the figure.
- `entry06-vatsa1995-fig4-grid-topology-19-block-supersonic-transport.png` — figure 4 of that document, cropped to the figure.

## entry07 — `eiseman1995` — class A

P. R. Eiseman (Program Development Corp.), *Multiblock grid generation with automatic zoning*, NASA CP-3291, 1995, NTRS `19950022314` — VENDOR-AUTHORED [V-GP]

- Source PDF: `https://ntrs.nasa.gov/api/citations/19950022314/downloads/19950022314.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry07-eiseman1995-fig10-field-about-cloth-fibers-grid-generated.png` — PDF page 20, 1364x1800 px. Caption(s): “Figure 10: The field about cloth fibers. The grid is generated in the region about interwoven fibers”
- `entry07-eiseman1995-fig3-half-full-fuel-tank-automobile-this.png` — PDF page 13, 1270x1800 px. Caption(s): “Figure 3: A half full fuel tank for an automobile. This grid is for a crash analysis application.(with”
- `entry07-eiseman1995-fig4-airfoil-in-ground-effect.png` — figure 4 of that document, cropped to the figure.

## entry08 — `repko2016` — class A

T. W. Repko, A. C. Nix, S. C. Uysal, A. T. Sisler, *Flow Visualization of Multi-Hole Film-Cooling Flow under Varying Freestream Turbulence Levels*, J. Flow Control Meas. Vis. 4(1), 13-29, 2016

- Source PDF: `http://www.scirp.org/journal/PaperDownload.aspx?paperID=62027`
- Licence: **class A** — Creative Commons Attribution 4.0 (publisher-stated)

- `entry08-repko2016-fig3-grid-coloured-by-block.png` — figure 3 of that document, cropped to the figure.
- `entry08-repko2016-fig4-computational-grid-unsteady-rans-analyses.png` — PDF page 5, 1800x1363 px. Caption(s): “Figure 4. Computational grid used in unsteady RANS analyses.”

## entry10 — `nielsen2021` — class A

E. Nielsen, J. R. Edwards, H. K. Chelliah, *Hybrid LES/RANS Analysis of a Premixed Ethylene-Fueled Dual-Mode Scramjet Combustor*, LA-UR-19-29624, OSTI `1830574`

- Source PDF: `https://www.osti.gov/servlets/purl/1830574`
- Licence: **class A** — US DOE work released through OSTI; public

- `entry10-nielsen2021-fig3-body-fitted-grid-insert-cavity.png` — figure 3 of that document, cropped to the figure.

## entry11 — `schwing2012` — class A

A. Schwing (NASA JSC / University of Minnesota), *Validation of US3D for Capsule Aerodynamics using 05-CA Wind Tunnel Test Data*, NTRS `20120017946` (presentation)

- Source PDF: `https://ntrs.nasa.gov/api/citations/20120017946/downloads/20120017946.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry11-schwing2012-slide7-capsule-grid-overview.png` — figure ? of that document, cropped to the figure.
- `entry11-schwing2012-slide8-capsule-symmetry-plane-grid.png` — figure ? of that document, cropped to the figure.

## entry12 — `papad2001` — class A

P. Papadopoulos et al., *CFD Simulations in Support of Shuttle Orbiter Contingency Abort Aerodynamic Database Enhancement*, AIAA 2001-3067, NTRS `20010089699`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20010089699/downloads/20010089699.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry12-papad2001-fig5-multi-layer-grid-generation-strategy.png` — PDF page 16, 1357x1800 px. Caption(s): “Fig. 5 Multi-layer grid generation strategy.”

## entry12 — `papadopoulos2001` — class A

P. Papadopoulos et al., *CFD Simulations in Support of Shuttle Orbiter Contingency Abort Aerodynamic Database Enhancement*, AIAA 2001-3067, NTRS `20010089699`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20010089699/downloads/20010089699.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry12-papadopoulos2001-fig7-orbiter-365-nonmerged-blocks.png` — figure 7 of that document, cropped to the figure.

## entry13 — `rigby2000` — class A

D. L. Rigby and E. Steinthorsson, *Aero-Thermal Performance of Internal Cooling Systems in Turbomachines*, VKI Lecture Series 1999-2000, NTRS `20000062308`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20000062308/downloads/20000062308.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry13-rigby2000-fig2-twelve-block-circle-in-box-topology.png` — figure 2 of that document, cropped to the figure.
- `entry13-rigby2000-fig3-block-merge-stages.png` — figure 3 of that document, cropped to the figure.
- `entry13-rigby2000-fig9-282-blocks-merged-to-22.png` — figure 9 of that document, cropped to the figure.
- `entry13-rigby2000-fig9_1n-passage-ribs-bleed-topology.png` — PDF page 25, 1395x1800 px. Caption(s): “Figure 9.1nternal passage with ribs and bleed topology”

## entry14 — `oswald2005` — class B

J. Oswald et al., *DLR-ONERA accurate CFD support for the Pre-X project*, DLR elib `21745`

- Source PDF: `https://elib.dlr.de/21745/1/A4.1_CFDsupport_tp_Pre-X_project_Jean_Oswald.pdf`
- Licence: **class B** — openly downloadable; no open licence stated, rights reserved by the publisher/author

- `entry14-oswald2005-fig4-symmetry-plane-basic-adapted-grid-sting.png` — PDF page 4, 940x583 px. Caption(s): “Figure 4 : Symmetry plane of basic and adapted grid with sting”
- `entry14-oswald2005-fig5-6-prex-surface-grid-and-bodyflap.png` — figure 5 of that document, cropped to the figure.

## entry17 — `allampalli2010` — class B

V. Allampalli, *Fourth order Multi-Time-Stepping Adams-Bashforth (MTSAB) scheme for NASA Glenn Research Center’s BASS Code*, PhD thesis, University of Toledo, 2010, OhioLINK `toledo1270739741`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=toledo1270739741&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry17-allampalli2010-fig4-13a-grid-joukowski-airfoil-case.png` — PDF page 79, 1197x1800 px. Caption(s): “Figure 4-13a: Grid used for the Joukowski airfoil case”
- `entry17-allampalli2010-fig4-13b-grid-joukowski-airfoil-case.png` — PDF page 80, 753x611 px. Caption(s): “Figure 4-13b: Grid used for the Joukowski airfoil case”
- `entry17-allampalli2010-fig4-18-levels-new-grid-blocks-near-airfoil.png` — PDF page 86, 1169x1800 px. Caption(s): “Figure 4-18: Levels of the new grid blocks near the airfoil surface after the original blocks are cut”
- `entry17-allampalli2010-fig4-2-grid-acoustic-scattering-benchmark-problem.png` — PDF page 71, 612x544 px. Caption(s): “Figure 4-2: Grid for the Acoustic-Scattering Benchmark problem”
- `entry17-allampalli2010-fig4-27-grid-3d-workshop-problem.png` — PDF page 95, 726x645 px. Caption(s): “Figure 4-27: Grid for the 3D Workshop Problem”
- `entry17-allampalli2010-fig5-1-complete-grid-naca0012-airfoil.png` — PDF page 108, 575x438 px. Caption(s): “Figure 5-1: Complete grid for NACA0012 airfoil”
- `entry17-allampalli2010-fig5-17-complete-grid-naca64a010-airfoil.png` — PDF page 127, 602x535 px. Caption(s): “Figure 5-17 Complete grid for NACA64A010 airfoil”
- `entry17-allampalli2010-fig5-3-grid-clustering-approximate-shock-location-grid.png` — PDF page 114, 602x531 px. Caption(s): “Figure 5-3: Grid clustering at approximate shock location (Grid 2)”
- `entry17-allampalli2010-fig6-1-complete-grid-flow-over-flat-plate.png` — PDF page 145, 606x390 px. Caption(s): “Figure 6-1: Complete grid for the flow over a flat plate”
- `entry17-allampalli2010-fig6-15-complete-grid-2d-cylinder-case.png` — PDF page 159, 692x615 px. Caption(s): “Figure 6-15: Complete grid for the 2D cylinder case”
- `entry17-allampalli2010-fig6-16-close-up-view-grid-near-cylinder.png` — PDF page 160, 692x615 px. Caption(s): “Figure 6-16: Close-up view of the grid near the cylinder”
- `entry17-allampalli2010-fig6-2-grid-near-flat-plate.png` — PDF page 146, 602x474 px. Caption(s): “Figure 6-2: Grid near the flat plate”
- `entry17-allampalli2010-fig6-3-grid-near-leading-edge-flat-plate.png` — PDF page 149, 598x533 px. Caption(s): “Figure 6-3 Grid near the leading edge of the flat plate”

## entry18 — `brown2010` — class B

C. A. Brown, *Simulation of the Localized Arc Filament Plasma Actuators*, PhD thesis, University of Akron, 2010, OhioLINK `akron1270860381`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=akron1270860381&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry18-brown2010-fig5_14-3-d-grid-osu-nozzle-dj.png` — PDF page 152, 759x651 px. Caption(s): “Figure 5.14: The 3-D grid of the OSU nozzle (Dj = 1.0 in.) used to test the axisym-”
- `entry18-brown2010-fig5_16-computational-grid-3-d-les-simulations.png` — PDF page 169, 1248x1799 px. Caption(s): “Figure 5.16: Computational grid used for the 3-D LES simulations (top) shown with”
- `entry18-brown2010-fig5_3-computational-grid-axisymmetric-simulations-osu.png` — PDF page 130, 1800x1251 px. Caption(s): “Figure 5.3: The computational grid used for the axisymmetric simulations of the OSU”
- `entry18-brown2010-fig5.4-506-block-grid-coloured-by-block.png` — figure 5.4 of that document, cropped to the figure.
- `entry18-brown2010-fig5.5-topology-with-internal-surfaces.png` — figure 5.5 of that document, cropped to the figure.

## entry19 — `ameri2012` — class A

A. A. Ameri, *Implementation of a Transition Model in a NASA Code and Validation Using Heat Transfer Data*, NASA/CR-2012-217436, NTRS `20120009201`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20120009201/downloads/20120009201.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry19-ameri2012-fig2-flat-plate-16-block-grid.png` — figure 2 of that document, cropped to the figure.
- `entry19-ameri2012-fig3-ge2-midspan-and-3d-grids.png` — figure 3 of that document, cropped to the figure.

## entry19 — `ameri2012b` — class A

A. A. Ameri, *Implementation of a Transition Model in a NASA Code and Validation Using Heat Transfer Data*, NASA/CR-2012-217436, NTRS `20120009201`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20120009201/downloads/20120009201.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry19-ameri2012b-fig17-three-dimensional-blade-grid-e3-blade.png` — PDF page 24, 693x454 px. Caption(s): “Figure 17.—(a) Three-dimensional blade grid of the E3 blade tip section cascade.(b) A two-dimensional section at the”

## entry20 — `garg2001` — class A

V. K. Garg and A. A. Ameri, *Two-Equation Turbulence Models for Prediction of Heat Transfer on a Transonic Turbine Blade*, NASA/CR-2001-210810 (2001-GT-0165), NTRS `20010047410`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20010047410/downloads/20010047410.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry20-garg2001-fig1-spanwise-multiblock-viscous-grid.png` — figure 1 of that document, cropped to the figure.

## entry21 — `rigby1998` — class A

D. L. Rigby et al., *Prediction of Heat and Mass Transfer in a Rotating Ribbed Coolant Passage With a 180 Degree Turn*, NASA/TM-1999-208501 (98-GT-329), NTRS `19990019396`

- Source PDF: `https://ntrs.nasa.gov/api/citations/19990019396/downloads/19990019396.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry21-rigby1998-fig2-ribbed-passage-grid-x0.png` — figure 2 of that document, cropped to the figure.
- `entry21-rigby1998-fig3-ribbed-passage-grid-y0.png` — figure 3 of that document, cropped to the figure.

## entry22 — `ameri2002` — class A

A. A. Ameri, *Computation of Turbulent Heat Transfer on the Walls of a 180 Degree Turn Channel*, NASA/CR-2002-211515 (GT-2002-30211), NTRS `20020085369`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20020085369/downloads/20020085369.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry22-ameri2002-fig2-topology-three-grids-and-yplus.png` — figure 2 of that document, cropped to the figure.

## entry23 — `garg2002` — class A

V. K. Garg, *Low-Pressure Turbine Separation Control—Comparison With Experimental Data*, NASA/CR-2002-211689 (GT-2002-30229), NTRS `20020070525`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20020070525/downloads/20020070525.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry23-garg2002-fig1-spanwise-grid-with-hole-exit-detail.png` — figure 1 of that document, cropped to the figure.

## entry24 — `heidmann2008` — class A

J. D. Heidmann, *A Numerical Study of Anti-Vortex Film Cooling Designs at High Blowing Ratio*, NASA/TM-2008-215209 (GT2008-50845)

- Source PDF: `https://ntrs.nasa.gov/api/citations/20080030074/downloads/20080030074.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry24-heidmann2008-fig9-grid-coloured-by-block.png` — figure 9 of that document, cropped to the figure.

## entry26 — `ameri2001` — class A

A. A. Ameri, *Heat Transfer and Flow on the Blade Tip of a Gas Turbine Equipped With a Mean-Camberline Strip*, NASA/CR-2001-210764 (2001-GT-0156), NTRS `20010050140`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20010050140/downloads/20010050140.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry26-ameri2001-fig3-blade-tip-grid-construction.png` — figure 3 of that document, cropped to the figure.

## entry27 — `steinthorsson1996` — class A

E. Steinthorsson, *Simulations of Turbine Cooling Flows Using a Multiblock-Multigrid Scheme*, NASA CR-198539 / ICOMP-96-7 / AIAA-96-0621, NTRS `19970007342`

- Source PDF: `https://ntrs.nasa.gov/api/citations/19970007342/downloads/19970007342.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry27-steinthorsson1996-fig3ab-branched-duct-grid.png` — figure ? of that document, cropped to the figure.
- `entry27-steinthorsson1996-fig3cd-corner-and-pin-fin-grid.png` — figure ? of that document, cropped to the figure.

## entry28 — `steinth1995` — class A

E. Steinthorsson and D. Modiano, *Advanced methodology for simulation of complex flows using structured grid systems*, NASA CP-3291, 1995, NTRS `19950022345`

- Source PDF: `https://ntrs.nasa.gov/api/citations/19950022345/downloads/19950022345.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry28-steinth1995-fig4-transonic-naca0012-adapted-structured-grid.png` — figure 4 of that document, cropped to the figure.

## entry28 — `steinthorsson1995` — class A

E. Steinthorsson and D. Modiano, *Advanced methodology for simulation of complex flows using structured grid systems*, NASA CP-3291, 1995, NTRS `19950022345`

- Source PDF: `https://ntrs.nasa.gov/api/citations/19950022345/downloads/19950022345.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry28-steinthorsson1995-fig2-multiblock-topology.png` — figure 2 of that document, cropped to the figure.
- `entry28-steinthorsson1995-fig3-centre-region-grid.png` — figure 3 of that document, cropped to the figure.

## entry29 — `ameri2009` — class A

A. A. Ameri, *NASA Rotor 37 CFD Code Validation: Glenn-HT Code*, NASA/CR-2010-216235 (AIAA-2009-1060), NTRS `20100029589`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20100029589/downloads/20100029589.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry29-ameri2009-fig1-rotor37-grid-two-views.png` — figure 1 of that document, cropped to the figure.

## entry30 — `shyam2009` — class B

V. Shyam, *3-D Unsteady Simulation of a Modern High Pressure Turbine Stage: Analysis of Heat Transfer and Flow*, PhD thesis, The Ohio State University, 2009, OhioLINK `osu1258931807`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=osu1258931807&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry30-shyam2009-fig2_2-mesh-2d-flow-over-flat-plate.png` — PDF page 49, 1179x1800 px. Caption(s): “Figure 2.2 Mesh for 2D flow over flat plate”
- `entry30-shyam2009-fig4_3-mesh-35-cooling-hole.png` — PDF page 62, 887x333 px. Caption(s): “Figure 4.3 Mesh for 35° cooling hole”
- `entry30-shyam2009-fig5.1-rotor-grid.png` — figure 5.1 of that document, cropped to the figure.

## entry31 — `osu2009` — class B

*Application of Conjugate Heat Transfer (CHT) Methodology for Computation of Heat Transfer on a Turbine Blade*, MS thesis, The Ohio State University, 2009, OhioLINK `osu1230064860`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=osu1230064860&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry31-osu2009-fig4.2-c3x-vane-grid.png` — figure 4.2 of that document, cropped to the figure.

## entry32 — `shankara2009` — class B

P. Shankara, *CFD Simulation and Analysis of Particulate Deposition on Gas Turbine Vanes*, MS thesis, The Ohio State University, 2009, OhioLINK `osu1262290700`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=osu1262290700&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry32-shankara2009-fig6_7-view-tetrahedral-volume-mesh-3d-case.png` — PDF page 67, 714x522 px. Caption(s): “Fig. 6.7: View of the tetrahedral volume mesh for the 3D case”
- `entry32-shankara2009-fig6.8-hexahedral-cut-section.png` — figure 6.8 of that document, cropped to the figure.
- `entry32-shankara2009-fig7_1-computational-grid-vki-blade.png` — PDF page 81, 1199x1800 px. Caption(s): “Fig 7.1: Computational grid used for the VKI blade”

## entry33 — `ayyala2003` — class B

H. Ayyalasomayajula, MS thesis, University of Cincinnati, 2003, OhioLINK `ucin1054757181`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=ucin1054757181&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry33-ayyala2003-fig5_2-enlarged-view-grid-around-mid-blade.png` — PDF page 100, 1135x1800 px. Caption(s): “Fig. 5.2. Enlarged-view of Grid around the mid-blade of Turbine Cascade”
- `entry33-ayyala2003-fig6_14-12-block-structured-periodic-grid-hpt.png` — PDF page 112, 1371x1800 px. Caption(s): “Fig. 6.14. 12-Block, Structured, Periodic Grid for HPT Blade Cascade”

## entry33 — `ayyalasomayajula2003` — class B

H. Ayyalasomayajula, MS thesis, University of Cincinnati, 2003, OhioLINK `ucin1054757181`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=ucin1054757181&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry33-ayyalasomayajula2003-fig6.6-ogrid-around-cylinder.png` — figure 6.6 of that document, cropped to the figure.

## entry34 — `singh2005` — class B

R. Singh, MS thesis, University of Cincinnati, 2005, OhioLINK `ucin1109095348`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=ucin1109095348&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry34-singh2005-fig4.1-twelve-block-lpt-cascade-grid.png` — figure 4.1 of that document, cropped to the figure.

## entry35 — `kasliwal2006` — class B

A. Kasliwal, MS thesis, University of Cincinnati, 2006, OhioLINK `ucin1141413192`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=ucin1141413192&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry35-kasliwal2006-fig1-eight-block-cylinder-grid.png` — figure 1 of that document, cropped to the figure.
- `entry35-kasliwal2006-fig16-fine-grid-block-layout.png` — figure 16 of that document, cropped to the figure.
- `entry35-kasliwal2006-fig34-multi-block-structured-block-layout-computational.png` — PDF page 119, 1575x1799 px. Caption(s): “Figure 34(a). Multi-block structured block layout of the computational domain with”

## entry36 — `mansouri2016` — class B

M. Mansouri, *A High-Order High-Accuracy Geometric Block Interface Treatment for Computational Aeroacoustics Codes*, PhD thesis, University of Toledo, 2016, OhioLINK `toledo1463099661`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=toledo1463099661&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry36-mansouri2016-fig1-3-typical-form-structured-grid.png` — PDF page 24, 722x722 px. Caption(s): “Figure 1-3: A Typical Form of A Structured Grid”
- `entry36-mansouri2016-fig1-6-typical-form-grid-discontinuities-singularities-around.png` — PDF page 26, 1116x744 px. Caption(s): “Figure 1-6: A Typical Form of Grid Discontinuities/Singularities around the”
- `entry36-mansouri2016-fig1-8-grid-blocks-3-way-b-3.png` — PDF page 28, 1226x1800 px. Caption(s): “Figure 1-8: Grid Blocks with (a) 3-way and (b) 3 and 5-way Singularities”
- `entry36-mansouri2016-fig4-1-cartesian-singular-b-grid-blocks-evaluate.png` — PDF page 84, 1285x1800 px. Caption(s): “Figure 4-1: Cartesian (a) and Singular (b) Grid Blocks to Evaluate BASS”
- `entry36-mansouri2016-fig4-19-grid-topology-contains-several-singularities.png` — PDF page 106, 656x656 px. Caption(s): “Figure 4-19: Grid Topology Contains Several Singularities”
- `entry36-mansouri2016-fig4-6-3-way-4-way-b-5.png` — PDF page 88, 744x709 px. Caption(s): “Figure 4-6: 3-way (a), 4-way (b), and 5-way (c) Two-dimensional Grid Sin-”
- `entry36-mansouri2016-fig4.15-three-way-singularity-grid.png` — figure 4.15 of that document, cropped to the figure.
- `entry36-mansouri2016-fig4.17-five-way-singularity-grid.png` — figure 4.17 of that document, cropped to the figure.
- `entry36-mansouri2016-fig5-10-clustered-grid-using-0-692.png` — PDF page 122, 1228x1800 px. Caption(s): “Figure 5-10: Clustered Grid Using α = 0.692”

## entry37 — `ingraham2015` — class B

D. Ingraham, *External Verification Analysis: A Code-Independent Approach to Verifying Unsteady Partial Differential Equation Solvers*, PhD thesis, University of Toledo, 2015, OhioLINK `toledo1430491745`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=toledo1430491745&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry37-ingraham2015-fig4-17-multiblock-grid-parallel-test-cases-colored.png` — PDF page 115, 1218x1102 px. Caption(s): “Figure 4-17: Multiblock grid used for parallel test cases colored by block”
- `entry37-ingraham2015-fig4-44-coarsest-singular-grid-grid-singularity-test.png` — PDF page 144, 1292x1449 px. Caption(s): “Figure 4-44: The coarsest singular grid used in the grid singularity test cases.”
- `entry37-ingraham2015-fig4.17-grid-coloured-by-block-index.png` — figure 4.17 of that document, cropped to the figure.

## entry38 — `heminger2010` — class B

M. A. Heminger, *Dynamic Grid Motion in a High-Order Computational Aeroacoustic Solver*, MS thesis, University of Toledo, 2010, OhioLINK `toledo1272550725`

- Source PDF: `https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=toledo1272550725&disposition=inline`
- Licence: **class B** — OhioLINK ETD; openly downloadable, copyright retained by the author

- `entry38-heminger2010-fig6-2-yz-x-slice-far-eld-grid.png` — PDF page 58, 1084x695 px. Caption(s): “Figure 6-2: YZ (+X) Slice Farﬁeld Grid”
- `entry38-heminger2010-fig6-4-xy-z-slice-showing-piston-edge.png` — PDF page 59, 1088x697 px. Caption(s): “Figure 6-4: XY (+Z) Slice Showing Piston Edge Grid Clustering”
- `entry38-heminger2010-fig6.4-6.5-piston-grid-clustering.png` — figure 6.4 of that document, cropped to the figure.

## entry39 — `baltazar2018` — class A

J. Baltazar, D. Rijpkema, J. Falcão de Campos, J. Bosschers, *Prediction of the Open-Water Performance of Ducted Propellers with a Panel Method*, J. Mar. Sci. Eng. 6(1) 27, 2018

- Source PDF: `https://www.mdpi.com/2077-1312/6/1/27/pdf`
- Licence: **class A** — Creative Commons Attribution 4.0 (publisher-stated)

- `entry39-baltazar2018-fig4-ducted-propeller-surface-grids.png` — figure 4 of that document, cropped to the figure.

## entry40 — `maljaars2018` — class A

P. Maljaars et al., *Experimental Validation of Fluid-Structure Interaction Computations of Flexible Composite Propellers in Open Water Conditions*, J. Mar. Sci. Eng. 6(2) 51, 2018

- Source PDF: `https://www.mdpi.com/2077-1312/6/2/51/pdf?version=1525866986`
- Licence: **class A** — Creative Commons Attribution 4.0 (publisher-stated)

- `entry40-maljaars2018-fig1-propeller-domain-and-grid.png` — figure 1 of that document, cropped to the figure.

## entry41 — `harries2021` — class A

S. Harries and S. Uharek, *Application of Radial Basis Functions for Partially-Parametric Modeling and Principal Component Analysis Applied to the Design of Catamarans*, J. Mar. Sci. Eng. 9(10) 1069, 2021

- Source PDF: `https://www.mdpi.com/2077-1312/9/10/1069/pdf?version=1632995799`
- Licence: **class A** — Creative Commons Attribution 4.0 (publisher-stated)

- `entry41-harries2021-fig12-close-up-panel-mesh-hull-free.png` — PDF page 14, 1098x580 px. Caption(s): “Figure 12. Close-up of the panel mesh on the hull and free surface in the vicinity of the hull.”
- `entry41-harries2021-fig13-bow-mesh-two-hulls-superposed.png` — figure 13 of that document, cropped to the figure.

## entry43 — `wu2021` — class A

D. Wu et al., *Numerical Simulation of the Flow Field in a Double-Blade Centrifugal Pump*, Appl. Sci. 11(17) 8180, 2021, DOI `10.3390/app11178180`

- Source PDF: `https://www.mdpi.com/2076-3417/11/17/8180/pdf`
- Licence: **class A** — Creative Commons Attribution 4.0 (publisher-stated)

- `entry43-wu2021-fig2-centrifugal-pump-grid.png` — figure 2 of that document, cropped to the figure.

## entry44 — `ledermann2025` — class A

V. Ledermann et al., *Pampero HiFi: improvements in aerodynamic modeling of a spacecraft-oriented destructive re-entry code*, CEAS Space J. 18, 209-234, 2026

- Source PDF: `https://link.springer.com/content/pdf/10.1007/s12567-025-00655-2.pdf`
- Licence: **class A** — Creative Commons Attribution 4.0 (publisher-stated)

- `entry44-ledermann2025-fig2-mesh-obtained-after-refinement-process.png` — PDF page 2, 965x692 px. Caption(s): “Fig. 2 Mesh obtained after the refinement process”
- `entry44-ledermann2025-fig9-mistral-multiblock-mesh.png` — figure 9 of that document, cropped to the figure.

## entry47 — `mcginn2021` — class A

P. McGinn, A. Gander, G. Tretola, C. Crua, K. Vogiatzaki (University of Brighton), ICLASS 2021

- Source PDF: `http://journals.ed.ac.uk/ICLASS_Edinburgh/article/download/6014/7861`
- Licence: **class A** — ICLASS 2021 proceedings, published open access by the University of Edinburgh

- `entry47-mcginn2021-fig1c-injector-nozzle-mesh-detail.png` — figure ? of that document, cropped to the figure.

## entry49 — `drozda2016` — class A

T. G. Drozda, R. A. Baurle, J. P. Drummond, *Impact of Flight Enthalpy, Fuel Simulant, and Chemical Reactions on the Mixing Characteristics of Several Injectors at Hypervelocity Flow Conditions*, NTRS `20160009131`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20160009131/downloads/20160009131.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry49-drozda2016-fig5-strut-grid-block-topology.png` — figure 5 of that document, cropped to the figure.
- `entry49-drozda2016-fig6-elements-coarse-grid-ramp-simulations-each.png` — PDF page 14, 976x799 px. Caption(s): “Figure 6: Elements of the coarse grid used for the ramp simulations. Each visible cell contains 4x4x4 cells”

## entry50 — `reschke2020` — class B

W. Reschke, M. Pfeiffer, S. Fasoulas (University of Stuttgart), arXiv `2007.06339`

- Source PDF: `https://arxiv.org/pdf/2007.06339`
- Licence: **class B** — arXiv default licence; no Creative Commons licence recorded

- `entry50-reschke2020-fig4-radial-slice-of-mesh.png` — figure 4 of that document, cropped to the figure.

## entry51 — `kleckova2019` — class B

J. Klečková, *Modelování aeroelastických jevů se zaměřením na predikci flutteru*, PhD thesis, University of West Bohemia, 2019 (in Czech)

- Source PDF: `(university repository; see the census note’s Sources list)`
- Licence: **class B** — openly downloadable; no open licence stated, rights reserved by the publisher/author

- `entry51-kleckova2019-obr6.4-blade-topology-and-bl-settings.png` — figure ? of that document, cropped to the figure.
- `entry51-kleckova2019-obr6.5-leading-and-trailing-edge-bl-mesh.png` — figure ? of that document, cropped to the figure.

## entry53 — `hauser1999` — class B

J. Hauser, T. Ludewig, R. Gollnick, M. Winkelmann, *A Pure Java Parallel Flow Solver*, CACR Technical Report CACR-170 / AIAA 99-549, 1999

- Source PDF: `https://authors.library.caltech.edu/28169/1/cacr170.pdf`
- Licence: **class B** — openly downloadable; no open licence stated, rights reserved by the publisher/author

- `entry53-hauser1999-fig1-x33-multiblock-grid.png` — figure 1 of that document, cropped to the figure.

## entry55 — `doe2003` — class A

*LES Software for the Design of Low Emission Combustion Systems for Vision 21 Plants*, Quarterly Technical Progress Report, DOE/Solar Turbines, OSTI `822313`

- Source PDF: `https://www.osti.gov/servlets/purl/822313`
- Licence: **class A** — US DOE work released through OSTI; public

- `entry55-doe2003-fig6-structured-grid-test-case.png` — figure 6 of that document, cropped to the figure.

## entry56 — `lanl2016` — class A

*2016 KIVA-hpFE Development: A Robust and Accurate Engine Modeling Software*, LA-UR-16-28135, Los Alamos National Laboratory, OSTI `1330623`

- Source PDF: `https://www.osti.gov/servlets/purl/1330623`
- Licence: **class A** — US DOE work released through OSTI; public

- `entry56-lanl2016-fig1-valve-overlaying-gridpro-grid.png` — figure 1 of that document, cropped to the figure.

## entry57 — `cheng1995` — class A

Z. Cheng and P. R. Eiseman (Program Development Corp.), *Examples of grid generation with implicitly specified surfaces using GridPro/az3000: filleted multi-tube configurations*, NASA CP-3291, 1995, NTRS `19950022351` — VENDOR-AUTHORED [V-GP]

- Source PDF: `https://ntrs.nasa.gov/api/citations/19950022351/downloads/19950022351.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry57-cheng1995-fig2-topology-components-most-basic-component-loop4.png` — PDF page 9, 1389x1800 px. Caption(s): “Figure 2: Topology components. (a). The most basic component, loop4. (b). The component,”
- `entry57-cheng1995-fig3-6tube-block-boundaries.png` — figure 3 of that document, cropped to the figure.
- `entry57-cheng1995-fig4-5tube-block-boundaries.png` — figure 4 of that document, cropped to the figure.
- `entry57-cheng1995-fig5-4tube-and-3tube-grids.png` — figure 5 of that document, cropped to the figure.

## entry58 — `lu1995` — class A

N. Lu and P. R. Eiseman (Program Development Corporation), *Interactive high quality grid generation*, NASA CP-3291, 1995, NTRS `19950022353` — VENDOR-AUTHORED [V-GP]

- Source PDF: `https://ntrs.nasa.gov/api/citations/19950022353/downloads/19950022353.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry58-lu1995-fig2-three-block-hexagon-grid.png` — figure 2 of that document, cropped to the figure.
- `entry58-lu1995-fig3-single-block-2d-pipe.png` — figure 3 of that document, cropped to the figure.
- `entry58-lu1995-fig4-two-block-grid-around-supercircle.png` — figure 4 of that document, cropped to the figure.
- `entry58-lu1995-fig5-half-single-block-volume-grid-inside-torus.png` — figure 5 of that document, cropped to the figure.
- `entry58-lu1995-fig6-seven-block-volume-grid-inside-sphere.png` — figure 6 of that document, cropped to the figure.

## entry71 — `nasa1994` — class A

*Computations of Unsteady Viscous Compressible Flows Using Adaptive Mesh Refinement in Curvilinear Body-fitted Grid Systems*, NASA TM-106704 / ICOMP-94-17 / AIAA-94-2330, NTRS `19950015542`

- Source PDF: `https://ntrs.nasa.gov/api/citations/19950015542/downloads/19950015542.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry71-nasa1994-fig1-grid-system-three-levels-coarse.png` — figure 1 of that document, cropped to the figure.
- `entry71-nasa1994-fig6-refined-grid-around-naca0012-airfoil-m.png` — figure 6 of that document, cropped to the figure.

## entry72 — `nasa1993` — class A

NASA TM-106356 / ICOMP-93-34 / AIAA-93-2380, NTRS `19940010255`

- Source PDF: `https://ntrs.nasa.gov/api/citations/19940010255/downloads/19940010255.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry72-nasa1993-fig1-multiblock-grid-system-12-blocks.png` — figure 1 of that document, cropped to the figure.
- `entry72-nasa1993-fig10-grid-system-radial-turbine-coolant-passage.png` — figure 10 of that document, cropped to the figure.

## entry73 — `nasa2013` — class A

*Validation of a CFD Methodology for Variable Speed Power Turbine Relevant Conditions*, NASA/TM-2013-217860 (GT2013-95030), NTRS `20130013998`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20130013998/downloads/20130013998.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `entry73-nasa2013-fig3-typical-three-dimensional-grid-vspt-as.png` — figure 3 of that document, cropped to the figure.

## othernote03 — `candler2010` — class A

G. V. Candler and C. H. Campbell, *Hypersonic Navier-Stokes Comparisons to Orbiter Flight Data*, NTRS `20100001402` — covered as §3 of `gridpro-meshes-in-published-cfd.md`

- Source PDF: `https://ntrs.nasa.gov/api/citations/20100001402/downloads/20100001402.pdf`
- Licence: **class A** — NASA work hosted on NTRS; US Government work, public domain

- `othernote03-candler2010-fig1-several-images-surface-grid-shock-adapted.png` — PDF page 3, 1336x1800 px. Caption(s): “Figure 1. Several images of the surface grid and shock-adapted outer envelop of grid for the half-Orbiter.”

## othernote09 — `crabill2019` — class B

J. Crabill, F. D. Witherden, A. Jameson, *High-Order Computational Fluid Dynamics Simulations of a Spinning Golf Ball*, arXiv `1806.00378` (Sports Engineering) — covered as §9 of `gridpro-meshes-in-published-cfd.md`

- Source PDF: `https://arxiv.org/pdf/1806.00378`
- Licence: **class B** — arXiv default licence; no Creative Commons licence returned by the arXiv API for this id

- `othernote09-crabill2019-fig1-golf-ball-surface-grid-resolution-figure.png` — PDF page 6, 640x640 px. Caption(s): “Fig. 1 Golf ball surface and grid resolution. Figure (c) shows the pre-agglomerated element”


**121 files: 63 class A, 58 class B, from 55 documents.**
