// HybMesh2D's entry point, and deliberately nothing else.
//
// Every line of implementation lives in the `hybmesh_core` library (see
// CMakeLists.txt), so a test executable can link the very code the binary runs.
// This file exists to keep that true: it is the ONLY source the executable
// compiles, which leaves no place to add logic a test could not reach. The
// command line itself is `hybmesh::runCli` in src/cli.cpp.
#include "Cli.hpp"

int main(int argc, char* argv[]) {
    return hybmesh::runCli(argc, argv);
}
