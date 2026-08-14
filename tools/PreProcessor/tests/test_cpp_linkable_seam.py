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

Checks:
  1. `add_executable(HybMesh2D ...)` lists exactly `src/main.cpp`.
  2. The root CMakeLists defines only the expected executables.
  3. Every `src/*.cpp` on disk belongs to some `add_library` source list.
  4. Nothing under `src/` or `include/` `#include`s a `.cpp`.
  5. No `add_executable` anywhere compiles a source under `src/` except the shim.
  6. Every `tests/cpp/test_*.cpp` on disk is registered as a ctest executable.
  7. `tests/cpp` never names `src/` — a test links the library, it does not
     recompile the implementation.

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

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

# The executables the root CMakeLists is allowed to define. A new entry here is a
# deliberate decision that needs a reason next to it, the same way
# test_gui_cpp_config_parity.py's KNOWN_CPP_ONLY does.
EXPECTED_EXECUTABLES = {
    "HybMesh2D",        # the mesher: a shim over hybmesh_core
    "surface_resampler",  # the preprocessor CLI; its own single-TU tool
}

# The one source the mesher's executable may compile.
SHIM = "src/main.cpp"

failures = []


def check(msg, cond):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def uncommented(text):
    """`text` with CMake `#` comments removed. Every check that greps for a token
    must go through this: the first version of check 7 was tripped by the very
    comment in tests/cpp/CMakeLists.txt explaining why naming src/ is wrong."""
    return "\n".join(re.sub(r"#.*$", "", ln) for ln in text.splitlines())


def cmake_calls(text, name):
    """The argument text of every `name(...)` call, comments stripped."""
    src = uncommented(text)
    out = []
    for m in re.finditer(r"\b" + name + r"\s*\(", src):
        i, depth = m.end(), 1
        while i < len(src) and depth:
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
            i += 1
        out.append(src[m.end():i - 1])
    return out


def targets(text, name):
    """{target: [remaining tokens]} for each `name(target ...)` call."""
    out = {}
    for args in cmake_calls(text, name):
        toks = args.split()
        if toks:
            out[toks[0]] = toks[1:]
    return out


def cmake_files():
    found = []
    for root, dirs, names in os.walk(_REPO):
        dirs[:] = [d for d in dirs if d not in ("build", ".git", "node_modules")]
        if "CMakeLists.txt" in names:
            found.append(os.path.join(root, "CMakeLists.txt"))
    return sorted(found)


def main():
    root_txt = read(os.path.join(_REPO, "CMakeLists.txt"))
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
    on_disk = sorted("src/" + n for n in os.listdir(os.path.join(_REPO, "src"))
                     if n.endswith(".cpp"))
    orphans = [s for s in on_disk if s != SHIM and s not in lib_sources]
    check(f"every src/*.cpp is in a library target (orphans: {orphans})",
          not orphans)
    check(f"...and there is at least one library holding them ({sorted(lib_sources)})",
          bool(lib_sources))

    # --- 4. nothing includes a .cpp ------------------------------------------
    includers = []
    for sub in ("src", "include"):
        d = os.path.join(_REPO, sub)
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
        rel = os.path.relpath(path, _REPO)
        for target, toks in targets(read(path), "add_executable").items():
            for t in toks:
                if not t.endswith(".cpp"):
                    continue
                norm = t.replace("../", "")
                if norm.startswith("src/") and t != SHIM:
                    offenders.append(f"{rel}: {target} compiles {t}")
    check(f"no add_executable compiles a src/ source except the shim ({offenders})",
          not offenders)

    # --- 6. every C++ test file is registered --------------------------------
    tdir = os.path.join(_REPO, "tests", "cpp")
    check("tests/cpp exists", os.path.isdir(tdir))
    if os.path.isdir(tdir):
        tests_txt = uncommented(read(os.path.join(tdir, "CMakeLists.txt")))
        registered = tests_txt  # names appear in the foreach list and add_test
        unregistered = [n for n in sorted(os.listdir(tdir))
                        if n.startswith("test_") and n.endswith(".cpp")
                        and n[:-4] not in registered]
        check("every tests/cpp/test_*.cpp is named in its CMakeLists "
              f"(unregistered: {unregistered})", not unregistered)
        check("tests/cpp registers its executables with ctest",
              "add_test(" in tests_txt)

        # --- 7. tests link the library, they do not rebuild it ---------------
        check("tests/cpp never names src/ (it links hybmesh_core instead)",
              "src/" not in tests_txt)

    print()
    print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
