#!/bin/bash
# Headless end-to-end pipeline: CAD resample -> mesh -> solver -> contour PNG.
# Usage: ./run_pipeline.sh config/pipeline/my_case.json [--png out.png] [--no-solver]

# --- Locate the Gmsh dynamic library directory (OS-aware, portable) ---------
# Belt-and-braces only: on Linux this export is inherited all the way down to
# HybMesh2D, but on macOS SIP strips DYLD_* the moment python3 starts, so the
# real handover happens inside the runner (pipeline_runner._mesh_env ->
# app/services/env_setup.mesher_env, passed to subprocess via env=).
. "$(dirname "$0")/tools/scripts/gmsh_lib_dir.sh"
hybmesh_export_gmsh_lib_path

python3 tools/PreProcessor/run_pipeline.py "$@"
