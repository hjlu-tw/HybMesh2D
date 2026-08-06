#!/bin/bash
# Shared Gmsh library-directory discovery for the shell entry points.
#
# Sourced by run.sh / run_pipeline.sh. Defines the loader search-path variable
# for this OS and exports it so a directly-exec'd HybMesh2D can find libgmsh
# (the binary links @rpath/libgmsh.<ver>.dylib and its baked LC_RPATH only
# happens to be right on the machine that built it).
#
# Resolution order — no developer-specific path is hardcoded anywhere:
#   1. $HYBMESH_GMSH_LIB_DIR, if it holds a libgmsh
#   2. the installed gmsh Python module (pip wheel: libgmsh sits two dirs above
#      gmsh.py), plus the common conda/homebrew layouts
# Not finding it is a warning, not a hard failure: a correctly-baked rpath or a
# system-wide install may satisfy the loader on its own.
#
# NOTE (macOS): exporting DYLD_LIBRARY_PATH here only helps when the *next*
# process is the binary itself. SIP strips every DYLD_* variable when a
# protected interpreter (python3) starts, so run_pipeline.sh cannot pass it
# through Python — the Python side resolves the directory again and hands it to
# subprocess via env=. See tools/PreProcessor/gui/app/services/env_setup.py.

hybmesh_gmsh_lib_dir() {
    if [ -n "${HYBMESH_GMSH_LIB_DIR:-}" ] \
       && ls "${HYBMESH_GMSH_LIB_DIR}"/libgmsh* >/dev/null 2>&1; then
        printf '%s\n' "${HYBMESH_GMSH_LIB_DIR}"
        return 0
    fi
    python3 - <<'PY' 2>/dev/null
import glob, os
try:
    import gmsh
except Exception:
    raise SystemExit(1)
here = os.path.dirname(os.path.abspath(gmsh.__file__))
for cand in (os.path.join(here, "..", ".."), here,
             os.path.join(here, "..", "..", "lib"),
             os.path.join(here, "..", "lib"),
             os.path.join(here, "..", "..", "..", "lib")):
    cand = os.path.normpath(cand)
    if glob.glob(os.path.join(cand, "libgmsh*")):
        print(cand)
        break
else:
    raise SystemExit(1)
PY
}

hybmesh_export_gmsh_lib_path() {
    local dir
    dir="$(hybmesh_gmsh_lib_dir || true)"
    if [ -z "${dir}" ]; then
        echo "警告: 找不到 libgmsh —— HybMesh2D 可能無法啟動。" >&2
        echo "      請安裝對應版本的 gmsh wheel（pip install -r tools/PreProcessor/gui/requirements.txt）" >&2
        echo "      或將 HYBMESH_GMSH_LIB_DIR 指向含 libgmsh 的目錄。" >&2
        return 0
    fi
    case "$(uname -s)" in
        Darwin) export DYLD_LIBRARY_PATH="${dir}:${DYLD_LIBRARY_PATH:-}" ;;
        *)      export LD_LIBRARY_PATH="${dir}:${LD_LIBRARY_PATH:-}" ;;
    esac
}
