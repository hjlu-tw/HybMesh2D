cmake_minimum_required(VERSION 3.10)
project(HybMesh VERSION 1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Default to an optimized build. Without a build type, `cmake ..` produces an
# unoptimized (-O0) binary; Release gives -O3 -DNDEBUG (often 2-10x faster).
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# Add -march=native when the compiler accepts it (portable guard).
include(CheckCXXCompilerFlag)
check_cxx_compiler_flag("-march=native" HAS_MARCH_NATIVE)
if(HAS_MARCH_NATIVE)
  set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -march=native")
endif()

# 1. 設置路徑 (根據原本 build.sh 的路徑)
set(GMSH_INCLUDE_DIR "/Users/hjlu_nchc/Library/Python/3.9/include")
set(GMSH_LIBRARY "/Users/hjlu_nchc/Library/Python/3.9/lib/libgmsh.4.15.dylib")
set(GMSH_RPATH "/Users/hjlu_nchc/Library/Python/3.9/lib")

# 2. 包含目錄
include_directories(include ${GMSH_INCLUDE_DIR})

# 3. 定義共用工具庫 (目前先包含基礎結構)
# 未來可以把 IOUtils 等抽出來放在這裡
add_library(HybMeshUtils INTERFACE)
target_include_directories(HybMeshUtils INTERFACE include)

# 4. 核心執行檔: HybMesh2D
add_executable(HybMesh2D 
    src/main.cpp 
    src/Mesh.cpp 
    src/BoundaryLayer.cpp
)

# 連結 Gmsh
target_link_libraries(HybMesh2D ${GMSH_LIBRARY})

# 設置 RPATH 以確保執行時能找到 dylib
set_target_properties(HybMesh2D PROPERTIES
    INSTALL_RPATH "${GMSH_RPATH}"
    BUILD_WITH_INSTALL_RPATH TRUE
)

# 5. 前處理工具: surface_resampler
add_executable(surface_resampler 
    tools/PreProcessor/src/main.cpp
)
target_include_directories(surface_resampler PRIVATE tools/PreProcessor/include)
target_link_libraries(surface_resampler HybMeshUtils)

# 6. 輸出目錄設置
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

message(STATUS "HybMesh configuration complete.")
