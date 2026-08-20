#!/usr/bin/env python3
"""Gate: the C++ decision layer must stay free of Mesh and gmsh.

`hybmesh_pure` is the C++ analogue of the GUI's "`services/*.py` must be Qt-free"
rule, for the same reason: testing a decision should not require a heavy
environment. The BUILD already proves most of it — the decision-layer tests link
`hybmesh_pure` alone and are not linked against libgmsh, so the moment such a
module *uses* `Mesh` or gmsh those executables stop linking. This gate covers the
half the linker cannot see: an INCLUDE that has not been used yet.

FOUR checks:
  8.  Every non-heavy `src/*.cpp` is in the `hybmesh_pure` source list.
  9.  Nothing in that list reaches `Mesh.hpp` or `gmsh.h`.
  10. No `src/*.cpp` outside `HEAVY_SOURCES` reaches them either.
  11. The same for `include/*.hpp` outside `HEAVY_HEADERS`.

The numbering continues `test_cpp_linkable_seam.py`'s 1-7; the two were one file
until a review pointed out they are two invariants with disjoint machinery.

Reach is TRANSITIVE, and that is not a refinement: `BoundaryLayer.cpp` includes
only `BoundaryLayer.hpp` and gets `Mesh.hpp` through it, so a direct-include
check would call it pure and would let any new module launder its dependency the
same way.

The lists below are a DENY-list, and the direction is the point: a new
`src/*.cpp` is assumed pure, and making it heavy costs an entry with a reason. An
allow-list would have the failure mode backwards — forgetting to enrol a new pure
module would exempt it from the rule, with no symptom at all.

Run:  python3 tools/PreProcessor/tests/test_cpp_pure_layer.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmake_probe import REPO, heavy_reach, read, src_cpp_files, targets  # noqa: E402

# The library holding the decision layer.
PURE_LIB = "hybmesh_pure"

# The one source the mesher's executable compiles; it is a shim, not a module.
SHIM = "src/main.cpp"

# What makes a file heavy, as reached transitively.
HEAVY_ROOTS = {"Mesh.hpp", "gmsh.h"}

HEAVY_SOURCES = {
    "src/cli.cpp": "the command line: owns config loading, geometry IO and every export",
    "src/Mesh.cpp": "the mesh data structure itself, and the gmsh far-field integration",
    "src/BoundaryLayer.cpp": "grows the layers, mutating the mesh as it goes",
}
HEAVY_HEADERS = {
    "include/Mesh.hpp": "IS the mesh interface (and pulls gmsh in for the far field)",
    "include/BoundaryLayer.hpp": "the generator holds a Mesh& and a Config&",
}

failures = []


def check(msg, cond):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def main():
    root_txt = read(os.path.join(REPO, "CMakeLists.txt"))
    libs = targets(root_txt, "add_library")
    on_disk = src_cpp_files()

    # --- 8. the decision layer holds everything that is not heavy ------------
    pure = [t for t in libs.get(PURE_LIB, []) if t.endswith(".cpp")]
    check(f"{PURE_LIB} exists and holds sources ({pure})", bool(pure))
    misplaced = [s for s in on_disk
                 if s != SHIM and s not in HEAVY_SOURCES and s not in pure]
    check(f"every non-heavy src/*.cpp is in {PURE_LIB} (misplaced: {misplaced})",
          not misplaced)

    # --- 9. the decision layer really is gmsh-free and Mesh-free -------------
    impure = {s: sorted(heavy_reach(os.path.join(REPO, s), HEAVY_ROOTS))
              for s in pure}
    impure = {s: h for s, h in impure.items() if h}
    check(f"nothing in {PURE_LIB} reaches Mesh.hpp or gmsh.h ({impure})", not impure)

    # --- 10. heavy is the exception and must be declared ---------------------
    undeclared = {}
    for s in on_disk:
        if s == SHIM or s in HEAVY_SOURCES:
            continue
        h = sorted(heavy_reach(os.path.join(REPO, s), HEAVY_ROOTS))
        if h:
            undeclared[s] = h
    check("no undeclared heavy source under src/ "
          f"({undeclared}; add it to HEAVY_SOURCES with a reason, or keep it pure)",
          not undeclared)

    # --- 11. the same, for headers -------------------------------------------
    hdr_undeclared = {}
    for name in sorted(os.listdir(os.path.join(REPO, "include"))):
        rel = "include/" + name
        if not name.endswith(".hpp") or rel in HEAVY_HEADERS:
            continue
        h = sorted(heavy_reach(os.path.join(REPO, rel), HEAVY_ROOTS))
        if h:
            hdr_undeclared[rel] = h
    check("no undeclared heavy header under include/ "
          f"({hdr_undeclared}; add it to HEAVY_HEADERS with a reason)",
          not hdr_undeclared)

    print()
    print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
