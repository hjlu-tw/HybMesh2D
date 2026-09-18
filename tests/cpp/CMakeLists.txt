# C++ unit tests: one executable per file, each registered with ctest. A test
# returns the number of failed checks (see check.hpp), so ctest's verdict is the
# executable's own.
#
# The rule that matters here: a test LINKS A LIBRARY TARGET, never a list of
# sources. Compiling src/*.cpp into the test executable would "work" and would
# quietly reintroduce exactly what this stage removed — a second build of the
# implementation, testable but not the one the binary runs.
# tools/PreProcessor/tests/test_cpp_linkable_seam.py enforces it (checks 5 and 7).

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
    # exportVTK's all-or-nothing block-id rule, driven from the partially tagged
    # state no MESH_MODE 1 run can produce. It is unreachable from production,
    # not untestable — which is only true because Mesh is a library target this
    # tree can link, and is the reason the test lives here rather than beside the
    # Python gate that covers the rule from the outside (#113).
    test_mesh_vtk_block_field
)

foreach(t IN LISTS HYBMESH_CORE_TESTS)
    add_executable(${t} ${t}.cpp)
    target_link_libraries(${t} PRIVATE hybmesh_core hybmesh_test_check)
    set_target_properties(${t} PROPERTIES
        INSTALL_RPATH "${GMSH_RPATH}"
        BUILD_WITH_INSTALL_RPATH TRUE)
    add_test(NAME ${t} COMMAND ${t})
endforeach()

# Tests of the DECISION LAYER. These link hybmesh_pure and NOTHING ELSE — in
# particular not gmsh and not hybmesh_core. That is not tidiness: it is what
# proves the module under test really needs no heavy environment, because the
# moment it uses Mesh or gmsh these executables stop linking. A rule saying
# "keep this module pure" would be a claim; this is the build failing.
# No rpath either, deliberately: needing one would mean a dylib crept in.
set(HYBMESH_PURE_TESTS
    test_junction_scheme
    # Config.hpp is a header-only .dat parser with no Mesh and no gmsh in it,
    # so the BL declaration is testable here; this executable failing to link
    # is the signal that stopped being true.
    test_bl_params_decl
    # "which parameters does the active mode never read?" — the same argument:
    # a mode's applicability is a decision over declarations, not a mesh.
    test_mesh_mode
    # The whole multi-block path — parse, resolve, fill, split, adapt input —
    # behind one seam. This executable failing to link is the signal that the
    # path has reached for the mesh container or for gmsh.
    test_multiblock
    # The quality instrument the v1 acceptance gate is measured with. Measuring a
    # mesh must not require the mesh container, so it belongs on this side of the
    # line: half its checks hand `measureMbQuality` a mesh nobody parsed.
    test_mb_quality
    # The per-cell SHAPE metric both generation paths share. It takes cells as
    # corner coordinates and nothing else, so this executable failing to link is
    # the signal that the one definition of cell shape has grown a dependency on
    # a mesh, a topology or gmsh -- the property that lets both paths use it.
    test_cell_shape
    # WHICH cells the hybrid path offers to that metric, and what the two counts
    # beside the figures mean. It was a `static` function inside src/cli.cpp until
    # #141, so no test could link to it; this executable is what that lift bought,
    # and it never builds a `Mesh` either.
    test_hybrid_quality
)

foreach(t IN LISTS HYBMESH_PURE_TESTS)
    add_executable(${t} ${t}.cpp)
    target_link_libraries(${t} PRIVATE hybmesh_pure hybmesh_test_check)
    add_test(NAME ${t} COMMAND ${t})
endforeach()
