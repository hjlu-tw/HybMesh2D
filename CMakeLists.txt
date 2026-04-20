cmake_minimum_required(VERSION 3.10)
project(HybMesh2D)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(include)

# 暫時只加入 main.cpp，後續再加入 Mesh.cpp
add_executable(HybMesh2D src/main.cpp src/Mesh.cpp src/BoundaryLayer.cpp)
