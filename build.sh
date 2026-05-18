#!/bin/bash

# Ensure build directory exists
mkdir -p build

# Navigate to build directory
cd build || exit

# Run CMake and Make
cmake ..
make
