#!/usr/bin/env bash
# Rebuild every mesh and every figure in this directory, from the repo root.
#
#     bash docs/research/allampalli-2010-reproductions/rebuild.sh
#
# A RESEARCH HARNESS. It writes only inside this directory: four generators
# write their own geometries, topology documents and MESH_MODE 1 configs, the
# mesher writes into out/, and plot.py writes the comparison figures. Nothing
# in config/, examples/, src/ or include/ is touched.
set -euo pipefail
cd "$(dirname "$0")/../../.."
D=docs/research/allampalli-2010-reproductions
P=red,green,blue,cyan,magenta,yellow

python3 $D/mblib.py
python3 $D/make_cylinder.py --run
python3 $D/make_plate.py --run
python3 $D/make_airfoil.py --case naca0012 --run
python3 $D/make_airfoil.py --case naca64a010 --run

cd $D
# The cylinder keeps Tecplot's own quadrant colours from fig6.15 so the two
# pictures can be compared colour for colour; the other three have too many
# blocks for that and use the six-colour cycle the figures themselves run on.
python3 plot.py out/cylinder_quads.vtk out/fig6-15_vs_ours.png \
    --palette cyan,green,red,blue --lw 0.6 --size 6 \
    --target entry17-allampalli2010-fig6-15-complete-grid-2d-cylinder-case.png \
    --target-title "entry 17, Fig. 6.15 (GridPro)" \
    --title "this repo — 4 blocks, 36,000 quads"
python3 plot.py out/cylinder_quads.vtk out/fig6-16_vs_ours.png \
    --palette cyan,green,red,blue --window -1.85 2.35 -1.4 2.45 --lw 0.6 --size 6 \
    --target entry17-allampalli2010-fig6-16-close-up-view-grid-near-cylinder.png \
    --target-title "entry 17, Fig. 6.16 (GridPro)" --title "this repo, the same window"

python3 plot.py out/plate_quads.vtk out/fig6-1_vs_ours.png --palette $P \
    --window -2 3 -1.5 1.5 --lw 0.6 --size 6 \
    --target entry17-allampalli2010-fig6-1-complete-grid-flow-over-flat-plate.png \
    --target-title "entry 17, Fig. 6.1 (GridPro)" \
    --title "this repo — 70 blocks, 19,488 quads"
python3 plot.py out/plate_quads.vtk out/fig6-2_vs_ours.png --palette $P \
    --window -0.204 1.254 -0.496 0.703 --lw 0.6 --size 6 \
    --target entry17-allampalli2010-fig6-2-grid-near-flat-plate.png \
    --target-title "entry 17, Fig. 6.2 (GridPro)" --title "this repo, the same window"
python3 plot.py out/plate_quads.vtk out/fig6-3_vs_ours.png --palette $P \
    --window -0.135 0.139 -0.123 0.128 --lw 0.6 --size 6 \
    --target entry17-allampalli2010-fig6-3-grid-near-leading-edge-flat-plate.png \
    --target-title "entry 17, Fig. 6.3 (GridPro)" --title "this repo, the same window"

python3 plot.py out/naca0012_quads.vtk out/fig5-1_vs_ours.png --palette $P \
    --window -10 24.06 -10.13 10.13 --lw 0.6 --size 6 \
    --target entry17-allampalli2010-fig5-1-complete-grid-naca0012-airfoil.png \
    --target-title "entry 17, Fig. 5.1 (GridPro)" \
    --title "this repo — 98 blocks, 30,596 quads"
python3 plot.py out/naca0012_quads.vtk out/fig5-3_vs_ours.png --palette $P \
    --window -0.158 1.121 -0.574 0.584 --lw 0.6 --size 6 \
    --target entry17-allampalli2010-fig5-3-grid-clustering-approximate-shock-location-grid.png \
    --target-title "entry 17, Fig. 5.3 (GridPro)" --title "this repo, the same window"
python3 plot.py out/naca64a010_quads.vtk out/fig5-17_vs_ours.png --palette $P \
    --window -0.421 1.494 -0.823 0.911 --lw 0.6 --size 6 \
    --target entry17-allampalli2010-fig5-17-complete-grid-naca64a010-airfoil.png \
    --target-title "entry 17, Fig. 5.17 (GridPro)" --title "this repo, the same window"

echo "done -- figures are in $D/out/"
