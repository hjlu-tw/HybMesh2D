#!/bin/bash

# 設定 Gmsh 函式庫路徑
export DYLD_LIBRARY_PATH=/Users/hjlu_nchc/Library/Python/3.9/lib:$DYLD_LIBRARY_PATH

# 確保結果輸出目錄存在
mkdir -p results

# 檢查執行檔是否存在
if [ ! -f "./build/HybMesh2D" ]; then
    echo "錯誤: 執行檔 ./build/HybMesh2D 不存在！"
    echo "請先執行 ./build.sh 進行編譯。"
    exit 1
fi

# 執行程式並傳遞所有參數
./build/HybMesh2D "$@"
