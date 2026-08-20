"""The environment that lets the mesher actually start.

Nothing here answers "where is the binary": each caller already builds its own
path beside the other paths it needs, and exporting a second answer would be a
second place for one to go stale. What the callers could NOT get right on their
own is the loader path, and that is the whole module.

Five test files each carried ``_LIB = os.path.join(_REPO, "build")`` and passed
it as ``LD_LIBRARY_PATH`` / ``DYLD_LIBRARY_PATH`` when launching HybMesh2D. That
directory holds the BINARY; it has never held ``libgmsh``, on CI or on a
developer machine. So the loader path was inert and every one of those runs was
relying on the binary's baked **rpath** instead — which the repo's own
``tools/scripts/gmsh_lib_dir.sh`` warns "is only reliably right on the machine
that built it".

On a developer machine that rpath is a personal pip prefix
(``/Users/<name>/Library/Python/3.9/lib``), which is the hardcoded-absolute-path
smell CLAUDE.md says to treat as a defect on sight. On CI the build job and the
test job are separate runners: the rpath points at the BUILD runner's Python
prefix, so the mesher starts only while both runners happen to resolve the same
``3.11.x`` directory. When they diverge every mesher test fails at once with

    HybMesh2D: error while loading shared libraries: libgmsh.so.4.15:
    cannot open shared object file: No such file or directory

and exit code 127 — measured on run 32323005967, where all five files failed
together while the run ten minutes earlier had passed with the same gmsh 4.15.2
and an identical binary.

This module routes them through the ONE resolver the GUI already uses
(``services/env_setup``), which is what CLAUDE.md names as the single answer to
"where is Gmsh". Qt-free: ``env_setup`` imports only the stdlib and ``gmsh``.
"""
from __future__ import annotations   # local python3 is 3.9; CI is 3.11

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)


def mesher_env(base: dict | None = None) -> dict:
    """Environment for launching the mesher, with libgmsh really on the path.

    Falls back to ``build/`` — the old, inert value — only if the resolver comes
    up empty, so a layout it does not know about is no worse off than before.
    """
    from app.services.env_setup import mesher_env as _resolve

    env = _resolve(dict(os.environ if base is None else base))
    if not any(env.get(k) for k in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH")):
        fallback = os.path.join(_REPO, "build")
        env["LD_LIBRARY_PATH"] = fallback
        env["DYLD_LIBRARY_PATH"] = fallback
    return env
