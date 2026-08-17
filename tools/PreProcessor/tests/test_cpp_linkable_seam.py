#!/usr/bin/env python3
"""Gate: the C++ implementation must stay linkable by a test.

The mesher used to have exactly one seam — the process boundary. CMakeLists had
no library target, so `src/main.cpp`, `Mesh.cpp` and `BoundaryLayer.cpp` were
compiled straight into the executable and nothing could link them;
`classifyJunctions`, extracted specifically so the junction binning could be
reasoned about and tested, sat unreachable for that reason alone. The
implementation now lives in a library and the executable compiles ONE source: a
twelve-line shim. This test keeps that true, because it is the kind of property
that decays silently — adding a new `.cpp` to `add_executable` builds and runs
perfectly well, and the loss shows up only as a test nobody could write.

SEVEN checks:
  1. `add_executable(HybMesh2D ...)` lists exactly `src/main.cpp`.
  2. The root CMakeLists defines only the expected executables.
  3. Every `src/*.cpp` on disk belongs to some `add_library` source list.
  4. Nothing under `src/` or `include/` `#include`s a `.cpp`.
  5. No `add_executable` anywhere compiles a source under `src/` except the shim.
  6. Every `tests/cpp/test_*.cpp` on disk is in a list that a `foreach` really
     turns into an executable AND registers with ctest.
  7. `tests/cpp` never names `src/` — a test links the library, it does not
     recompile the implementation.

The DECISION-LAYER purity rule is a different invariant with different data and
lives in `test_cpp_pure_layer.py`; only the CMake parsing is shared, via
`cmake_probe.py`.

Checks 4, 5 and 7 exist because check 1 alone has holes, and each hole is a way
to have the property look satisfied while it is not:

  * `#include "cli.cpp"` inside another translation unit links fine and puts the
    implementation somewhere no library contains (check 4).
  * A test executable listing `../../src/Mesh.cpp` compiles its own second build
    of the implementation — testable, but not the code the binary runs (5, 7).
  * A brand-new `add_executable` can quietly become a second place for logic (2).

Known remaining blind spots, stated rather than pretended away:
  * Logic moved into a header is not caught — and does not need to be, since a
    header-only module is already linkable by anything.
  * Check 5 matches a literal `src/` path. A source reached through a CMake
    variable (`${CMAKE_SOURCE_DIR}/src/...`) would slip past; no target in this
    repo writes one, and check 3 still catches the file itself.
  * A CMakeLists added in a directory this test does not walk. It walks every
    CMakeLists.txt in the repo except `build/`, so that requires a new top-level
    tree, which is not a quiet change.
  * A registered test that asserts nothing. No static check can see that; the
    mutation-injection habit in the commit messages is the counter-measure.

Run:  python3 tools/PreProcessor/tests/test_cpp_linkable_seam.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmake_probe import (REPO, cmake_files, consumed_lists, list_vars,  # noqa: E402
                         read, src_cpp_files, targets, uncommented)

# The executables the root CMakeLists is allowed to define. A new entry here is a
# deliberate decision that needs a reason next to it, the same way
# test_gui_cpp_config_parity.py's KNOWN_CPP_ONLY does.
EXPECTED_EXECUTABLES = {
    "HybMesh2D",          # the mesher: a shim over hybmesh_core
    "surface_resampler",  # the preprocessor CLI; its own single-TU tool
}

# The one source the mesher's executable may compile.
SHIM = "src/main.cpp"

failures = []


def check(msg, cond):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def main():
    root_txt = read(os.path.join(REPO, "CMakeLists.txt"))
    exes = targets(root_txt, "add_executable")
    libs = targets(root_txt, "add_library")

    # --- 1. the executable compiles the shim and nothing else -----------------
    hyb = exes.get("HybMesh2D")
    check("the root CMakeLists defines HybMesh2D", hyb is not None)
    if hyb is not None:
        sources = [t for t in hyb if t.endswith(".cpp")]
        check(f"HybMesh2D compiles ONLY {SHIM} (got {sources})", sources == [SHIM])

    # --- 2. no unannounced executable ----------------------------------------
    extra = sorted(set(exes) - EXPECTED_EXECUTABLES)
    check("the root CMakeLists defines no unexpected executable "
          f"(extra: {extra}; add it to EXPECTED_EXECUTABLES with a reason)",
          not extra)

    # --- 3. every implementation source belongs to a library -----------------
    lib_sources = set()
    for toks in libs.values():
        lib_sources.update(t for t in toks if t.endswith(".cpp"))
    on_disk = src_cpp_files()
    orphans = [s for s in on_disk if s != SHIM and s not in lib_sources]
    check(f"every src/*.cpp is in a library target (orphans: {orphans})",
          not orphans)
    check(f"...and there is at least one library holding them ({sorted(lib_sources)})",
          bool(lib_sources))

    # --- 4. nothing includes a .cpp ------------------------------------------
    includers = []
    for sub in ("src", "include"):
        d = os.path.join(REPO, sub)
        for name in sorted(os.listdir(d)):
            if not name.endswith((".cpp", ".hpp", ".h")):
                continue
            for m in re.finditer(r'#\s*include\s*[<"]([^">]+)[">]',
                                 read(os.path.join(d, name))):
                if m.group(1).endswith(".cpp"):
                    includers.append(f"{sub}/{name} -> {m.group(1)}")
    check(f"no source under src/ or include/ #includes a .cpp ({includers})",
          not includers)

    # --- 5. no executable anywhere recompiles the implementation -------------
    offenders = []
    for path in cmake_files():
        rel = os.path.relpath(path, REPO)
        for target, toks in targets(read(path), "add_executable").items():
            for t in toks:
                if not t.endswith(".cpp"):
                    continue
                norm = t.replace("../", "")
                if norm.startswith("src/") and t != SHIM:
                    offenders.append(f"{rel}: {target} compiles {t}")
    check(f"no add_executable compiles a src/ source except the shim ({offenders})",
          not offenders)

    # --- 6. every C++ test file is really built AND registered ---------------
    tdir = os.path.join(REPO, "tests", "cpp")
    check("tests/cpp exists", os.path.isdir(tdir))
    if os.path.isdir(tdir):
        tests_txt = read(os.path.join(tdir, "CMakeLists.txt"))
        # Only the list variables a foreach turns into an executable AND registers
        # with ctest count. Merely appearing in the file does not: deleting one
        # foreach block leaves the other block's add_test() behind, which is
        # exactly how a "the name is mentioned somewhere" check passes while the
        # test is neither built nor run.
        live = consumed_lists(tests_txt, "add_executable", "add_test")
        declared = list_vars(tests_txt)
        registered = set()
        for var in live:
            registered.update(declared.get(var, []))
        check(f"tests/cpp has at least one live test list ({sorted(live)})", bool(live))
        unregistered = [n for n in sorted(os.listdir(tdir))
                        if n.startswith("test_") and n.endswith(".cpp")
                        and n[:-4] not in registered]
        check("every tests/cpp/test_*.cpp is built and registered with ctest "
              f"(unregistered: {unregistered})", not unregistered)

        # --- 7. tests link the library, they do not rebuild it ---------------
        check("tests/cpp never names src/ (it links a library instead)",
              "src/" not in uncommented(tests_txt))

    print()
    print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
