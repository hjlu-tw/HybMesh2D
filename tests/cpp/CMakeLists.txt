# C++ unit tests: one executable per file, each registered with ctest. A test
# returns the number of failed checks (see check.hpp), so ctest's verdict is the
# executable's own.
#
# The rule that matters here: a test LINKS A LIBRARY TARGET, never a list of
# sources. Compiling src/*.cpp into the test executable would "work" and would
# quietly reintroduce exactly what this stage removed — a second build of the
# implementation, testable but not the one the binary runs.
# tests/../test_cpp_linkable_seam.py enforces it.

# check.hpp only needs to be found; nothing to compile.
add_library(hybmesh_test_check INTERFACE)
target_include_directories(hybmesh_test_check INTERFACE ${CMAKE_CURRENT_SOURCE_DIR})

# Tests of the mesh / BL implementation. These link hybmesh_core and therefore
# also gmsh; the rpath is copied from the main executable so they run without
# DYLD_LIBRARY_PATH (macOS SIP strips it from anything a protected binary spawns,
# so relying on the environment would make them unrunnable from the GUI's
# test harness).
set(HYBMESH_CORE_TESTS
    test_mesh_boundary_edge
)

foreach(t IN LISTS HYBMESH_CORE_TESTS)
    add_executable(${t} ${t}.cpp)
    target_link_libraries(${t} PRIVATE hybmesh_core hybmesh_test_check)
    set_target_properties(${t} PROPERTIES
        INSTALL_RPATH "${GMSH_RPATH}"
        BUILD_WITH_INSTALL_RPATH TRUE)
    add_test(NAME ${t} COMMAND ${t})
endforeach()
