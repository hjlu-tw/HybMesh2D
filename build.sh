#!/bin/bash

# Build script for HybMesh2D

echo "Compiling HybMesh2D..."

# Ensure build directory exists
mkdir -p build

# Compile using g++ with C++17 standard
# Includes and libraries are pointing to the Gmsh SDK location
g++ -std=c++17 -Iinclude -I/Users/hjlu_nchc/Library/Python/3.9/include \
    src/main.cpp src/Mesh.cpp src/BoundaryLayer.cpp \
    /Users/hjlu_nchc/Library/Python/3.9/lib/libgmsh.4.15.dylib \
    -Wl,-rpath,/Users/hjlu_nchc/Library/Python/3.9/lib \
    -o build/HybMesh2D

# Check if compilation was successful
if [ $? -ne 0 ]; then
    echo "Compilation failed! Please check the error messages above."
    exit 1
fi

echo "Compilation successful! Executable is located at build/HybMesh2D"
