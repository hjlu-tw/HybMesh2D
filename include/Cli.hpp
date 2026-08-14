#ifndef HYBMESH_CLI_HPP
#define HYBMESH_CLI_HPP

namespace hybmesh {

// The whole of HybMesh2D's command line: argument parsing, config loading,
// geometry loading, the collision checks, the BL + Gmsh pipeline and every
// export. Returns a process exit code (see ExitCodes.hpp).
//
// This exists as a declaration, rather than as `main()`, so that it — and
// everything it calls — compiles into a LIBRARY that a test executable can
// link. The binary is a shim over this one call and compiles no implementation
// of its own, which is the point: there is then no place to put logic that a
// test cannot reach.
int runCli(int argc, char* argv[]);

}  // namespace hybmesh

#endif
