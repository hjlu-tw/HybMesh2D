#!/bin/bash
# Build HybMesh2D + surface_resampler.
# Usage: ./build.sh [BUILD_TYPE]   (BUILD_TYPE defaults to Release)
#   ./build.sh            # Release
#   ./build.sh Debug      # Debug
#   ./build.sh RelWithDebInfo
# Extra CMake flags (e.g. -DENABLE_NATIVE_ARCH=ON) can be appended after the type.
set -euo pipefail

# Build type: first positional arg, default Release. Remaining args pass through
# to cmake (so `./build.sh Release -DENABLE_SANITIZERS=ON` works).
BUILD_TYPE="${1:-Release}"
if [ "$#" -gt 0 ]; then
    shift
fi

# Ensure build directory exists
mkdir -p build

# Configure. Fail loudly if CMake configuration fails.
if ! cmake -S . -B build -DCMAKE_BUILD_TYPE="${BUILD_TYPE}" "$@"; then
    echo "Error: CMake configuration failed." >&2
    exit 1
fi

# Compile. Fail loudly if the build fails.
if ! cmake --build build; then
    echo "Error: build failed." >&2
    exit 1
fi

echo "Build complete (${BUILD_TYPE}): ./build/HybMesh2D, ./build/surface_resampler"
