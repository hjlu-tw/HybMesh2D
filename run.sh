#!/bin/bash

# --- Locate the Gmsh dynamic library directory (OS-aware, portable) ---------
# Prefer asking the installed gmsh Python module where it lives (the pip wheel
# ships libgmsh two dirs up from gmsh.py: <prefix>/lib/python/site-packages ->
# <prefix>/lib). Fall back to this developer's known path so the local run keeps
# working even if that probe fails.
GMSH_LIB_DIR="$(python3 -c 'import gmsh, os; print(os.path.normpath(os.path.join(os.path.dirname(gmsh.__file__), "..", "..")))' 2>/dev/null || true)"
if [ -z "${GMSH_LIB_DIR}" ] || ! ls "${GMSH_LIB_DIR}"/libgmsh* >/dev/null 2>&1; then
    GMSH_LIB_DIR="/Users/hjlu_nchc/Library/Python/3.9/lib"
fi

# On macOS use DYLD_LIBRARY_PATH; on Linux use LD_LIBRARY_PATH. Prepend so an
# existing value is preserved.
case "$(uname -s)" in
    Darwin)
        export DYLD_LIBRARY_PATH="${GMSH_LIB_DIR}:${DYLD_LIBRARY_PATH:-}"
        ;;
    *)
        export LD_LIBRARY_PATH="${GMSH_LIB_DIR}:${LD_LIBRARY_PATH:-}"
        ;;
esac

# 確保結果輸出目錄存在
mkdir -p Results

# 檢查執行檔是否存在
if [ ! -f "./build/HybMesh2D" ]; then
    echo "錯誤: 執行檔 ./build/HybMesh2D 不存在！"
    echo "請先執行 ./build.sh 進行編譯。"
    exit 1
fi

# 執行程式並傳遞所有參數
./build/HybMesh2D "$@"
