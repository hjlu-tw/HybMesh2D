#!/bin/bash

echo "正在編譯 HybMesh2D..."
mkdir -p build
g++ -std=c++17 -Iinclude -I/Users/hjlu_nchc/Library/Python/3.9/include \
    src/main.cpp src/Mesh.cpp src/BoundaryLayer.cpp \
    /Users/hjlu_nchc/Library/Python/3.9/lib/libgmsh.4.15.dylib \
    -Wl,-rpath,/Users/hjlu_nchc/Library/Python/3.9/lib \
    -o build/HybMesh2D

if [ $? -ne 0 ]; then
    echo "編譯失敗！請檢查錯誤訊息。"
    exit 1
fi
echo "編譯成功！執行檔位於 build/HybMesh2D"
