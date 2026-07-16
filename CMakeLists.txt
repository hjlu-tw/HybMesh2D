cmake_minimum_required(VERSION 3.10)
project(HybMesh VERSION 1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Default to an optimized build. Without a build type, `cmake ..` produces an
# unoptimized (-O0) binary; Release gives -O3 -DNDEBUG (often 2-10x faster).
# CMAKE_BUILD_TYPE stays selectable (e.g. -DCMAKE_BUILD_TYPE=Debug); we only
# supply the default when the user did not choose one.
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING
      "Build type (Debug/Release/RelWithDebInfo/MinSizeRel)" FORCE)
endif()

# --- Build options ---------------------------------------------------------
# -march=native produces binaries tuned to (and only runnable on) the building
# CPU. It is great for a local perf build but causes SIGILL / illegal-instruction
# crashes on other machines and destroys build reproducibility, so it is OFF by
# default and must be opted into explicitly.
option(ENABLE_NATIVE_ARCH "Add -march=native (local perf build only, not portable)" OFF)
# AddressSanitizer + UndefinedBehaviorSanitizer for local debugging.
option(ENABLE_SANITIZERS "Build with -fsanitize=address,undefined" OFF)

include(CheckCXXCompilerFlag)
if(ENABLE_NATIVE_ARCH)
  check_cxx_compiler_flag("-march=native" HAS_MARCH_NATIVE)
  if(HAS_MARCH_NATIVE)
    set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -march=native")
    message(STATUS "ENABLE_NATIVE_ARCH ON: adding -march=native (non-portable binary).")
  else()
    message(WARNING "ENABLE_NATIVE_ARCH requested but compiler rejects -march=native; ignoring.")
  endif()
endif()

# Warning flags — guarded per compiler. NOTE: no -Werror here on purpose;
# treat-warnings-as-errors belongs in CI, which is out of scope for this file.
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang")
  add_compile_options(-Wall -Wextra -Wpedantic)
elseif(MSVC)
  add_compile_options(/W4)
endif()

# Sanitizers wire into both compile and link.
if(ENABLE_SANITIZERS)
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang")
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
    message(STATUS "ENABLE_SANITIZERS ON: address+undefined sanitizers active.")
  else()
    message(WARNING "ENABLE_SANITIZERS is only supported for GNU/Clang; ignoring.")
  endif()
endif()

# --- Provenance / versioning ----------------------------------------------
# Stamp outputs with the git SHA and version so produced meshes are traceable
# to the exact source. Reading git here is a build-time, read-only convenience;
# if git is missing or this is not a checkout, degrade gracefully to "unknown".
set(HYBMESH_GIT_SHA "unknown")
find_package(Git QUIET)
if(GIT_FOUND)
  execute_process(
    COMMAND ${GIT_EXECUTABLE} rev-parse --short HEAD
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    OUTPUT_VARIABLE _hybmesh_git_sha
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
    RESULT_VARIABLE _hybmesh_git_rc)
  if(_hybmesh_git_rc EQUAL 0 AND _hybmesh_git_sha)
    set(HYBMESH_GIT_SHA "${_hybmesh_git_sha}")
  endif()
endif()
set(HYBMESH_VERSION "${PROJECT_VERSION}")
message(STATUS "HybMesh version ${HYBMESH_VERSION} (git ${HYBMESH_GIT_SHA})")

# --- Gmsh discovery --------------------------------------------------------
# Gmsh ships its SDK (gmsh.h + libgmsh) via the pip `gmsh` wheel or a manual
# SDK install. Discover it instead of hardcoding one machine's absolute paths.
# Override with -DGMSH_ROOT=/path/to/gmsh (expects <root>/include and <root>/lib).
# The HINTS include this developer's known pip location so the local build keeps
# working with no extra flags, plus the usual system prefixes.
set(GMSH_ROOT "" CACHE PATH "Root of a Gmsh SDK install (contains include/ and lib/)")
find_path(GMSH_INCLUDE_DIR gmsh.h
    HINTS
        ${GMSH_ROOT}/include
        /Users/hjlu_nchc/Library/Python/3.9/include
        /usr/local/include
        /opt/homebrew/include)
# Accept the version-tagged 4.15 dylib as well as the unversioned name; do not
# pin to a single filename so future gmsh installs keep resolving.
find_library(GMSH_LIBRARY NAMES gmsh gmsh.4.15
    HINTS
        ${GMSH_ROOT}/lib
        /Users/hjlu_nchc/Library/Python/3.9/lib
        /usr/local/lib
        /opt/homebrew/lib)
if(NOT GMSH_INCLUDE_DIR OR NOT GMSH_LIBRARY)
    message(FATAL_ERROR
        "Gmsh SDK not found (need gmsh.h and libgmsh).\n"
        "  Fix options:\n"
        "    * pip3 install --user \"gmsh>=4.15,<4.16\"   (installs the SDK), or\n"
        "    * download the Gmsh SDK and pass -DGMSH_ROOT=/path/to/gmsh-sdk\n"
        "      (expects <root>/include/gmsh.h and <root>/lib/libgmsh.*).\n"
        "  Searched: \${GMSH_ROOT}/{include,lib}, this machine's pip prefix,\n"
        "  /usr/local, and /opt/homebrew.")
endif()
# Derive the runtime library search path from wherever libgmsh was found.
get_filename_component(GMSH_RPATH "${GMSH_LIBRARY}" DIRECTORY)
message(STATUS "Gmsh include: ${GMSH_INCLUDE_DIR}")
message(STATUS "Gmsh library: ${GMSH_LIBRARY}")

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

# Stamp provenance into the binary. The C++ side has an `#ifndef HYBMESH_GIT_SHA`
# fallback, so these definitions only override the default when available.
target_compile_definitions(HybMesh2D PRIVATE
    HYBMESH_GIT_SHA="${HYBMESH_GIT_SHA}"
    HYBMESH_VERSION="${HYBMESH_VERSION}")

# 4b. 選用的 CGNS 輸出 (Phase 4)
# 找得到 CGNS 函式庫就編進 exportCGNS；找不到時 exportCGNS 退化為 runtime
# stub，預設 build 不會因為缺少 CGNS 而失敗。CGNS 透過 install_name 內含
# HDF5 的絕對路徑，因此這裡只需連結 libcgns。
#
# 重要：libcgns 必須排在 libgmsh 之前。libgmsh 內部靜態包了一份「32-bit
# cgsize_t」的 CGNS 並匯出所有 cg_* 符號；在 macOS two-level namespace 下，
# 連結順序在前者會綁定我們的 cg_* 呼叫。我們的 header 是 homebrew 的 64-bit
# 版本，必須綁到 homebrew libcgns，否則 zone 維度會被當成 32-bit 而寫壞。
find_path(CGNS_INCLUDE_DIR cgnslib.h
    HINTS /opt/homebrew/opt/cgns/include /opt/homebrew/include /usr/local/include)
find_library(CGNS_LIBRARY NAMES cgns
    HINTS /opt/homebrew/opt/cgns/lib /opt/homebrew/lib /usr/local/lib)
if(CGNS_INCLUDE_DIR AND CGNS_LIBRARY)
    message(STATUS "CGNS export ENABLED: ${CGNS_LIBRARY}")
    target_compile_definitions(HybMesh2D PRIVATE HAVE_CGNS)
    target_include_directories(HybMesh2D PRIVATE ${CGNS_INCLUDE_DIR})
    target_link_libraries(HybMesh2D ${CGNS_LIBRARY})  # 必須先於 Gmsh
else()
    message(STATUS "CGNS not found — exportCGNS compiled as a no-op stub.")
endif()

# 連結 Gmsh (排在 CGNS 之後，見上方說明)
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
