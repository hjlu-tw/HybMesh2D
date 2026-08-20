"""Shared CMake / include-graph probing for the C++ structural gates.

Two gates read the build files — `test_cpp_linkable_seam.py` (the implementation
stays linkable by a test) and `test_cpp_pure_layer.py` (the decision layer stays
free of Mesh and gmsh). They check unrelated invariants with unrelated data, so
they are separate tests; only this parsing is common, and a second copy of a
CMake parser is how two gates start disagreeing about what the build says.

Not named `test_*.py`, so `run_all.sh`'s glob does not try to run it.
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def uncommented(text):
    """`text` with CMake `#` comments removed. Every check that greps for a token
    must go through this: the first version of the "tests never name src/" check
    was tripped by the very comment explaining why naming src/ is wrong."""
    return "\n".join(re.sub(r"#.*$", "", ln) for ln in text.splitlines())


def _balanced(src, start):
    """Index just past the `)` matching the `(` that `start` sits after."""
    i, depth = start, 1
    while i < len(src) and depth:
        if src[i] == "(":
            depth += 1
        elif src[i] == ")":
            depth -= 1
        i += 1
    return i


def cmake_calls(text, name):
    """The argument text of every `name(...)` call, comments stripped."""
    src = uncommented(text)
    out = []
    for m in re.finditer(r"\b" + name + r"\s*\(", src):
        i = _balanced(src, m.end())
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


def list_vars(text):
    """{VAR: [values]} for each `set(VAR ...)`."""
    return targets(text, "set")


def consumed_lists(text, *required_calls):
    """The `set()` variables that a `foreach(... IN LISTS VAR)` really consumes in
    a body containing every one of `required_calls`.

    Checking that a name merely APPEARS in the file is not enough, and that was a
    real hole: deleting a whole foreach block left both the name list and the
    `add_test(` of the OTHER block in place, so a "registered" check passed while
    the test was neither built nor run.
    """
    src = uncommented(text)
    found = set()
    for m in re.finditer(r"\bforeach\s*\(", src):
        i = _balanced(src, m.end())
        args = src[m.end():i - 1]
        end = src.find("endforeach", i)
        body = src[i:end if end >= 0 else len(src)]
        if not all(c in body for c in required_calls):
            continue
        lists = re.search(r"\bIN\s+LISTS\s+(.+)$", args.strip())
        if lists:
            found.update(lists.group(1).split())
    return found


def includes(path):
    """The quoted/angled include names in one file. Comments are NOT stripped:
    `#include` is a preprocessor line, so a commented-out one is dead anyway and
    flagging it is the safe direction."""
    return [m.group(1) for m in
            re.finditer(r'^\s*#\s*include\s*[<"]([^">]+)[">]',
                        read(path), re.MULTILINE)]


def heavy_reach(path, heavy_roots, seen=None):
    """The headers in `heavy_roots` that `path` reaches, following this project's
    own headers TRANSITIVELY.

    Transitive is the whole point: BoundaryLayer.cpp includes only
    BoundaryLayer.hpp and reaches Mesh.hpp through it, so a direct-include check
    would call it pure and would let any new module launder its dependency the
    same way. Only include/ is followed — a system or third-party header cannot
    lead back here — and a root that does not live there (gmsh.h) registers by
    name as a leaf.
    """
    if seen is None:
        seen = set()
    hit = set()
    for name in includes(path):
        base = os.path.basename(name)
        if base in heavy_roots:
            hit.add(base)
        nxt = os.path.join(REPO, "include", base)
        if base not in seen and os.path.exists(nxt):
            seen.add(base)
            hit |= heavy_reach(nxt, heavy_roots, seen)
    return hit


def cmake_files():
    found = []
    for root, dirs, names in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in ("build", ".git", "node_modules")]
        if "CMakeLists.txt" in names:
            found.append(os.path.join(root, "CMakeLists.txt"))
    return sorted(found)


def src_cpp_files():
    """`src/*.cpp`, repo-relative, sorted."""
    return sorted("src/" + n for n in os.listdir(os.path.join(REPO, "src"))
                  if n.endswith(".cpp"))
