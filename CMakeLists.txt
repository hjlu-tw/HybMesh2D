cmake_minimum_required(VERSION 3.10)
project(HybMesh2D)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(GMSH_SDK "/Users/hjlu_nchc/Library/Python/3.9")
include_directories(include ${GMSH_SDK}/include)

add_executable(HybMesh2D src/main.cpp src/Mesh.cpp src/BoundaryLayer.cpp)
target_link_libraries(HybMesh2D "${GMSH_SDK}/lib/libgmsh.4.15.dylib")
