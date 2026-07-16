#!/bin/bash
# Headless end-to-end pipeline: CAD resample -> mesh -> solver -> contour PNG.
# Usage: ./run_pipeline.sh config/pipeline/my_case.json [--png out.png] [--no-solver]

# --- Locate the Gmsh dynamic library directory (OS-aware, portable) ---------
# Same discovery logic as run.sh so HybMesh2D can load libgmsh: ask the installed
# gmsh module (libgmsh sits two dirs up from gmsh.py), fall back to this
# developer's known path so the local run keeps working.
GMSH_LIB_DIR="$(python3 -c 'import gmsh, os; print(os.path.normpath(os.path.join(os.path.dirname(gmsh.__file__), "..", "..")))' 2>/dev/null || true)"
if [ -z "${GMSH_LIB_DIR}" ] || ! ls "${GMSH_LIB_DIR}"/libgmsh* >/dev/null 2>&1; then
    GMSH_LIB_DIR="/Users/hjlu_nchc/Library/Python/3.9/lib"
fi

case "$(uname -s)" in
    Darwin)
        export DYLD_LIBRARY_PATH="${GMSH_LIB_DIR}:${DYLD_LIBRARY_PATH:-}"
        ;;
    *)
        export LD_LIBRARY_PATH="${GMSH_LIB_DIR}:${LD_LIBRARY_PATH:-}"
        ;;
esac

python3 tools/PreProcessor/run_pipeline.py "$@"
