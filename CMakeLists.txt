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
# SDK install. Override with -DGMSH_ROOT=/path/to/gmsh (expects <root>/include
# and <root>/lib).
#
# ASK THE WHEEL FIRST. The fixed HINTS below used to be the only discovery, and
# they named one developer's macOS pip prefix plus /usr/local and /opt/homebrew.
# A pip prefix is per-machine — a --user dir here, the hosted toolcache on a
# GitHub runner — so CI installed gmsh and then failed at configure with "Gmsh
# SDK not found"; and because the test job is `needs: build`, the entire
# regression suite was SKIPPED rather than run. The workflow had never been
# green. tools/scripts/gmsh_sdk_dirs.py is the single resolver (gmsh_lib_dir.sh
# uses it too, for the run-time loader path).
set(GMSH_ROOT "" CACHE PATH "Root of a Gmsh SDK install (contains include/ and lib/)")
set(GMSH_PY_INCLUDE "")
set(GMSH_PY_LIB "")
set(GMSH_PY_LIBFILE "")
find_program(HYBMESH_PYTHON3 NAMES python3 python)
if(HYBMESH_PYTHON3)
    execute_process(
        COMMAND ${HYBMESH_PYTHON3}
                ${CMAKE_CURRENT_SOURCE_DIR}/tools/scripts/gmsh_sdk_dirs.py
        OUTPUT_VARIABLE _gmsh_sdk_out
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
        RESULT_VARIABLE _gmsh_sdk_rc)
    if(_gmsh_sdk_rc EQUAL 0)
        string(REGEX MATCH "INCLUDE=[^\n]*" _gmsh_inc_line "${_gmsh_sdk_out}")
        if(_gmsh_inc_line)
            string(REPLACE "INCLUDE=" "" GMSH_PY_INCLUDE "${_gmsh_inc_line}")
        endif()
        string(REGEX MATCH "\nLIB=[^\n]*" _gmsh_lib_line "\n${_gmsh_sdk_out}")
        if(_gmsh_lib_line)
            string(REPLACE "\nLIB=" "" GMSH_PY_LIB "${_gmsh_lib_line}")
        endif()
        string(REGEX MATCH "LIBFILE=[^\n]*" _gmsh_libfile_line "${_gmsh_sdk_out}")
        if(_gmsh_libfile_line)
            string(REPLACE "LIBFILE=" "" GMSH_PY_LIBFILE "${_gmsh_libfile_line}")
        endif()
        message(STATUS "Gmsh SDK via the Python wheel: "
                       "include='${GMSH_PY_INCLUDE}' lib='${GMSH_PY_LIB}'")
    endif()
endif()
find_path(GMSH_INCLUDE_DIR gmsh.h
    HINTS
        ${GMSH_ROOT}/include
        ${GMSH_PY_INCLUDE}
        /usr/local/include
        /opt/homebrew/include)
# Accept the version-tagged 4.15 dylib as well as the unversioned name; do not
# pin to a single filename so future gmsh installs keep resolving.
find_library(GMSH_LIBRARY NAMES gmsh gmsh.4.15
    HINTS
        ${GMSH_ROOT}/lib
        ${GMSH_PY_LIB}
        /usr/local/lib
        /opt/homebrew/lib)
# On Linux the wheel ships `lib/libgmsh.so.4.15` and NO unversioned
# `libgmsh.so` symlink, so find_library's NAMES (which become `libgmsh.so` and
# `libgmsh.4.15.so`) match nothing. macOS ships `libgmsh.4.15.dylib`, which
# `gmsh.4.15` does match — which is why the build worked on the developer's
# machine and nowhere else, with CI red from the day the workflow was added.
# The resolver already globbed the real file, so use it rather than teaching
# NAMES another platform's spelling and baking the version in a second place.
if(NOT GMSH_LIBRARY AND GMSH_PY_LIBFILE AND EXISTS "${GMSH_PY_LIBFILE}")
    set(GMSH_LIBRARY "${GMSH_PY_LIBFILE}" CACHE FILEPATH "Gmsh library" FORCE)
    message(STATUS "Gmsh library taken from the wheel: ${GMSH_LIBRARY}")
endif()
if(NOT GMSH_INCLUDE_DIR OR NOT GMSH_LIBRARY)
    # Name WHICH half is missing. The combined message cost a full CI round trip
    # to diagnose: the headers were found and only the library was not.
    if(GMSH_INCLUDE_DIR)
        set(_gmsh_missing "the LIBRARY (headers found at ${GMSH_INCLUDE_DIR})")
    elseif(GMSH_LIBRARY)
        set(_gmsh_missing "the HEADERS (library found at ${GMSH_LIBRARY})")
    else()
        set(_gmsh_missing "BOTH the headers and the library")
    endif()
    message(FATAL_ERROR
        "Gmsh SDK not found: missing ${_gmsh_missing}.\n"
        "  Fix options:\n"
        "    * pip3 install --user \"gmsh>=4.15,<4.16\"   (installs the SDK), or\n"
        "    * download the Gmsh SDK and pass -DGMSH_ROOT=/path/to/gmsh-sdk\n"
        "      (expects <root>/include/gmsh.h and <root>/lib/libgmsh.*).\n"
        "  Searched: \${GMSH_ROOT}/{include,lib}, the installed gmsh wheel\n"
        "  (include='${GMSH_PY_INCLUDE}' lib='${GMSH_PY_LIB}', resolved by\n"
        "  tools/scripts/gmsh_sdk_dirs.py), /usr/local, and /opt/homebrew.")
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

# 3b. 決策層: hybmesh_pure
# gmsh-free / Mesh-free 的純判定模組。這條規則與 GUI 那邊「services/*.py 必須
# Qt-free」同構，理由也一樣：測它不該需要重型執行環境。而且這裡不只是宣稱——
# 純模組的測試只 link hybmesh_pure、**不** link ${GMSH_LIBRARY}，所以一旦模組真的
# 用到 Mesh 或 gmsh，那支測試會在連結期就失敗。grep 抓得到 include，連結器抓得到
# use，兩者互補，缺一不可。
# 新增的 src/*.cpp 預設就該落在這裡；要成為重型檔必須具名進
# tools/PreProcessor/tests/test_cpp_pure_layer.py 的 HEAVY_SOURCES 並附理由。
add_library(hybmesh_pure STATIC
    src/JunctionScheme.cpp
)
target_include_directories(hybmesh_pure PUBLIC include)

# 4. 核心實作庫: hybmesh_core
# 實作全部住在這個 library 裡，執行檔只是 src/main.cpp 那五行 shim。這是刻意的：
# 測試連結到的必須就是 binary 真正在跑的那份程式碼，而執行檔既然不編譯任何實作，
# 就沒有地方可以放「測試連不到」的邏輯。tests/cpp 連的就是這個 target。
add_library(hybmesh_core STATIC
    src/cli.cpp
    src/Mesh.cpp
    src/BoundaryLayer.cpp
)
target_include_directories(hybmesh_core PUBLIC include ${GMSH_INCLUDE_DIR})
target_link_libraries(hybmesh_core PUBLIC hybmesh_pure)

# Stamp provenance into the LIBRARY, not into the executable. The code that reads
# these macros (src/cli.cpp, via Provenance.hpp) compiles as part of hybmesh_core
# now, so a definition left on HybMesh2D would apply to the shim only and silently
# degrade every banner and provenance sidecar to "unknown". PUBLIC so a test
# linking the library reports the same build. The C++ side has an
# `#ifndef HYBMESH_GIT_SHA` fallback, so these only override when available.
target_compile_definitions(hybmesh_core PUBLIC
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
    target_compile_definitions(hybmesh_core PUBLIC HAVE_CGNS)
    target_include_directories(hybmesh_core PUBLIC ${CGNS_INCLUDE_DIR})
    target_link_libraries(hybmesh_core PUBLIC ${CGNS_LIBRARY})  # 必須先於 Gmsh
else()
    message(STATUS "CGNS not found — exportCGNS compiled as a no-op stub.")
endif()

# 連結 Gmsh (排在 CGNS 之後，見上方說明)。PUBLIC 讓連結順序原封不動傳遞到每個
# 連結 hybmesh_core 的 target，否則上面那段 cgsize_t 的說明就白寫了。
target_link_libraries(hybmesh_core PUBLIC ${GMSH_LIBRARY})

# 4c. 核心執行檔: HybMesh2D — 只有 shim，不編譯任何實作 (見 4. 的說明)
add_executable(HybMesh2D src/main.cpp)
target_link_libraries(HybMesh2D PRIVATE hybmesh_core)

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

# 5b. C++ 單元測試 (ctest)
# 預設 ON 是刻意的：如果預設建置不含測試，`run_all.sh` 的 ctest 掛鉤就會對絕大
# 多數人靜默 skip，而「可連結的 seam」又退回成理論上存在。多編幾個小 TU 的成本
# 可以忽略。CI 的 build job 直接跑 `ctest --test-dir build`（test job 只下載
# binary、沒有 build tree，跑不了 ctest）。
option(HYBMESH_BUILD_TESTS "Build the C++ unit tests (ctest)" ON)
enable_testing()
if(HYBMESH_BUILD_TESTS)
    add_subdirectory(tests/cpp)
endif()

# 6. 輸出目錄設置
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

message(STATUS "HybMesh configuration complete.")
