#!/bin/bash
# Headless batch: several pipeline cases in sequence.
# Usage: ./run_batch.sh case_a.json case_b.json
#        ./run_batch.sh @config/pipeline/cases.txt --no-solver
#
# Exit code is 0 only when EVERY queued case succeeded, so this is safe to drive
# from cron / CI without a batch that "finished with 12 failures" looking green.

# --- Locate the Gmsh dynamic library directory (OS-aware, portable) ---------
# Belt-and-braces only, exactly as in run_pipeline.sh: on Linux this export is
# inherited by HybMesh2D, but on macOS SIP strips DYLD_* the moment python3 starts,
# so the real handover happens inside the runner (app/services/env_setup.py).
. "$(dirname "$0")/tools/scripts/gmsh_lib_dir.sh"
hybmesh_export_gmsh_lib_path

python3 tools/PreProcessor/run_batch.py "$@"
