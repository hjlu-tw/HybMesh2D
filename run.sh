#!/bin/bash

# --- Locate the Gmsh dynamic library directory (OS-aware, portable) ---------
# Shared with run_pipeline.sh and mirrored in Python by
# tools/PreProcessor/gui/app/services/env_setup.py, so the GUI, the headless
# pipeline and this script all resolve libgmsh the same way. Override with
# HYBMESH_GMSH_LIB_DIR for a non-standard install.
. "$(dirname "$0")/tools/scripts/gmsh_lib_dir.sh"
hybmesh_export_gmsh_lib_path

# 確保結果輸出目錄存在（HybMesh2D 會自動建立各 case 的 results/meshes/<case>/ 子目錄）
mkdir -p results/meshes

# 檢查執行檔是否存在
if [ ! -f "./build/HybMesh2D" ]; then
    echo "錯誤: 執行檔 ./build/HybMesh2D 不存在！"
    echo "請先執行 ./build.sh 進行編譯。"
    exit 1
fi

# 執行程式並傳遞所有參數
./build/HybMesh2D "$@"
