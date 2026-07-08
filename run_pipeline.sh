#!/bin/bash
# Headless end-to-end pipeline: CAD resample -> mesh -> solver -> contour PNG.
# Usage: ./run_pipeline.sh config/pipeline/my_case.json [--png out.png] [--no-solver]

# Gmsh dynamic library path (same as run.sh) so HybMesh2D can load libgmsh.
export DYLD_LIBRARY_PATH=/Users/hjlu_nchc/Library/Python/3.9/lib:$DYLD_LIBRARY_PATH

python3 tools/PreProcessor/run_pipeline.py "$@"
