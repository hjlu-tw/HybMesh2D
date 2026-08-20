#!/usr/bin/env python3
"""Which solver cases were built from which geometry?

Each case records what it was cut from in ``results/solver/<case>/grid/cad/
SOURCES.txt`` (written by ``app/services/case_sources.py``). That answers
"which body is this case?" from inside the case. This script answers the
question the other way round — **"if I change this CAD file, which cases go
stale?"** — which nothing else can, because the arrow only points one way: a
geometry has no idea who used it.

Usage:
    # every case and the geometry it was built from
    python3 tools/scripts/case_sources_index.py

    # which cases used this file (by path, or by any part of the name)
    python3 tools/scripts/case_sources_index.py examples/geometries/naca0012.dat
    python3 tools/scripts/case_sources_index.py naca

    # look somewhere other than results/solver
    python3 tools/scripts/case_sources_index.py --root /path/to/cases naca

A file is matched by identity ((st_dev, st_ino)) when it still exists, so a
different spelling of the same path — or a symlink to it — still matches; by
recorded path and then by substring otherwise, which is what lets a query name a
geometry that has already been deleted or renamed.

Exit code 1 when a query matched nothing, so this is usable in a check script.
"""
from __future__ import annotations

import argparse
import os
import sys

SOURCES_INDEX = "SOURCES.txt"
SOURCE_DIR_NAME = "cad"
GENERATED = "(generated)"
_SEP = "  <-  "


def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", ".."))


def read_index(path: str) -> list:
    """``[(staged_name, origin)]`` from one SOURCES.txt; [] if unreadable."""
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("#") or _SEP not in line:
                    continue
                name, origin = line.split(_SEP, 1)
                out.append((name.strip(), origin.strip()))
    except OSError:
        pass
    return out


def scan(root: str) -> list:
    """``[(case_name, case_dir, [(staged, origin)])]`` for every case under root."""
    cases = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return cases
    for name in names:
        case_dir = os.path.join(root, name)
        idx = os.path.join(case_dir, "grid", SOURCE_DIR_NAME, SOURCES_INDEX)
        if os.path.isfile(idx):
            cases.append((name, case_dir, read_index(idx)))
    return cases


def _ident(path: str):
    try:
        st = os.stat(path)
    except (OSError, ValueError):
        return None
    return (st.st_dev, st.st_ino)


def matches(query: str, origin: str) -> bool:
    """Whether a recorded origin is the thing the user asked about."""
    if origin == GENERATED:
        return False
    q_id = _ident(query)
    if q_id is not None and q_id == _ident(origin):
        return True
    if os.path.abspath(query) == os.path.abspath(origin):
        return True
    return query.lower() in origin.lower()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Which solver cases were built from which geometry.")
    ap.add_argument("query", nargs="?", default="",
                    help="geometry path, or any part of its name; omit to list "
                         "every case")
    ap.add_argument("--root", default="",
                    help="cases directory (default: results/solver)")
    args = ap.parse_args(argv)

    root = args.root or os.path.join(repo_root(), "results", "solver")
    if not os.path.isdir(root):
        print(f"No cases directory at {root}", file=sys.stderr)
        return 1

    cases = scan(root)
    if not cases:
        print(f"No case under {root} records its sources yet.")
        print("(grid/cad/ is written when a case is prepared; cases built "
              "before that feature have none.)")
        return 0 if not args.query else 1

    if not args.query:
        for name, _dir, entries in cases:
            print(f"{name}")
            if not entries:
                print("    (index present but empty)")
            for staged, origin in entries:
                mark = "" if origin != GENERATED else "  [generated]"
                print(f"    {staged}{mark}")
                if origin != GENERATED:
                    print(f"        {origin}")
        print(f"\n{len(cases)} case(s) under {root}")
        return 0

    hits = [(name, [(s, o) for s, o in entries if matches(args.query, o)])
            for name, _d, entries in cases]
    hits = [(name, found) for name, found in hits if found]
    if not hits:
        print(f"No case under {root} was built from anything matching "
              f"'{args.query}'.")
        return 1
    print(f"Cases built from something matching '{args.query}':\n")
    for name, found in hits:
        print(f"{name}")
        for staged, origin in found:
            print(f"    {staged}  <-  {origin}")
    print(f"\n{len(hits)} of {len(cases)} case(s) match. Re-run them if that "
          "geometry has changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
