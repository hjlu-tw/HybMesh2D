#!/usr/bin/env python3
"""Locate the Gmsh SDK (gmsh.h and libgmsh) that the installed `gmsh` wheel ships.

Prints up to two lines and exits 0 if it found anything, 1 if not:

    INCLUDE=/path/holding/gmsh.h
    LIB=/path/holding/libgmsh.*
    LIBFILE=/path/holding/libgmsh.so.4.15      (the library FILE itself)

`LIBFILE` exists because the directory is not enough on Linux. The wheel ships
`lib/libgmsh.so.4.15` with **no unversioned `libgmsh.so` symlink**, and CMake's
`find_library(NAMES gmsh gmsh.4.15)` looks for `libgmsh.so` / `libgmsh.4.15.so` —
neither of which is there. macOS ships `libgmsh.4.15.dylib`, which that same
NAMES list does match, so the build worked on the developer's machine and only
there. Reporting the resolved file lets the caller skip the guesswork, and it
does not bake a version number into a second place.

Why this exists as its own file: the pip wheel is how this project's own
instructions AND its CI install Gmsh, and its prefix is different on every
machine — a `--user` directory locally, the hosted toolcache on a GitHub runner,
a virtualenv elsewhere. `CMakeLists.txt` used to carry a fixed HINTS list that
named one developer's macOS pip prefix plus /usr/local and /opt/homebrew, so
configure failed on CI with "Gmsh SDK not found" — and because the test job
`needs: build`, the whole regression suite was skipped rather than run. The CI
had never been green.

Both `CMakeLists.txt` (configure time, needs the headers too) and
`gmsh_lib_dir.sh` (run time, needs only the library) resolve through this, so
there is one answer to "where is Gmsh" rather than one per entry point.
"""
import glob
import os
import sys


def _roots():
    """Directories worth searching, most specific first."""
    out = []
    try:
        import gmsh
        here = os.path.dirname(os.path.abspath(gmsh.__file__))
        # A wheel puts gmsh.py in site-packages and libgmsh a few levels up.
        out += [here]
        cur = here
        for _ in range(4):
            cur = os.path.dirname(cur)
            out.append(cur)
    except Exception:
        # No gmsh module is a normal outcome (a manual SDK install, or a build
        # host without the wheel); the caller falls back to its own hints.
        pass
    out.append(sys.prefix)
    try:
        import site
        if getattr(site, "USER_BASE", None):
            out.append(site.USER_BASE)
    except Exception:
        pass
    seen, uniq = set(), []
    for r in out:
        r = os.path.normpath(r)
        if r and r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq


def _find(patterns):
    """(directory, first matching file) for the first hit, or ("", "")."""
    for root in _roots():
        for sub in ("", "include", "lib", os.path.join("..", "include"),
                    os.path.join("..", "lib")):
            d = os.path.normpath(os.path.join(root, sub))
            for pat in patterns:
                hits = sorted(glob.glob(os.path.join(d, pat)))
                if hits:
                    return d, hits[0]
    return "", ""


def main():
    inc, _ = _find(["gmsh.h"])
    lib, libfile = _find(["libgmsh.*", "libgmsh*.dylib", "libgmsh*.so*", "gmsh.lib"])
    if inc:
        print("INCLUDE=" + inc)
    if lib:
        print("LIB=" + lib)
    if libfile:
        print("LIBFILE=" + libfile)
    return 0 if (inc or lib) else 1


if __name__ == "__main__":
    sys.exit(main())
