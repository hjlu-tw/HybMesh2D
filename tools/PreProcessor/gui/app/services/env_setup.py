"""Runtime environment for the compiled C++ binaries (Qt-free).

``build/HybMesh2D`` links ``@rpath/libgmsh.<ver>.dylib`` and the link-time
``LC_RPATH`` points at whatever gmsh directory the *build machine* happened to
have. On any other machine that path does not exist, so the loader needs
``DYLD_LIBRARY_PATH`` (macOS) / ``LD_LIBRARY_PATH`` (Linux) to find libgmsh —
exactly what ``run.sh`` exports before exec'ing the binary.

Relying on a shell wrapper to export it does **not** work when the binary is
launched from Python, and not only because the GUI is started as a bare
``python3 main.py``: on macOS, SIP purges every ``DYLD_*`` variable from the
environment of a protected interpreter (``/usr/bin/python3`` and the Command
Line Tools python are both protected). A wrapper's export is therefore already
gone by the time ``os.environ`` is read, so ``os.environ.copy()`` can never
carry it through.

Computing the directory here and handing it to ``Popen(env=...)`` does work: the
value goes straight into ``execve`` for the child, and our own binaries are
ad-hoc/linker-signed rather than hardened, so dyld honours it.

Usage::

    from app.services.env_setup import mesher_env
    subprocess.Popen(cmd, env=mesher_env(), ...)
"""
from __future__ import annotations

import functools
import glob
import os
import sys

# The loader's search-path variable for this platform.
LIB_PATH_VAR = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"

_LIB_GLOB = "libgmsh*"


def _has_libgmsh(directory: str) -> bool:
    """True if ``directory`` holds a libgmsh shared library."""
    if not directory or not os.path.isdir(directory):
        return False
    return bool(glob.glob(os.path.join(directory, _LIB_GLOB)))


@functools.lru_cache(maxsize=1)
def gmsh_lib_dir() -> str | None:
    """Directory containing libgmsh, or None if it cannot be located.

    Probed from the installed ``gmsh`` Python module — the same trick ``run.sh``
    uses — because the pip wheel ships the shared library two levels above
    ``gmsh.py`` (``<prefix>/lib/python3.x/site-packages/gmsh.py`` ->
    ``<prefix>/lib``). Other layouts (module dir itself, a sibling ``lib/``) are
    checked too so a conda/homebrew install also resolves.

    Cached: the answer cannot change within a process, and every subprocess
    launch would otherwise re-import gmsh and re-stat the candidates.
    """
    # An explicit override wins, so a user with a non-standard layout can always
    # point the GUI at the right directory without editing code.
    override = os.environ.get("HYBMESH_GMSH_LIB_DIR", "")
    if _has_libgmsh(override):
        return os.path.abspath(override)

    try:
        import gmsh  # noqa: PLC0415  (probe only; import cost is paid once)
    except Exception:
        return None

    mod_file = getattr(gmsh, "__file__", None)
    if not mod_file:
        return None
    here = os.path.dirname(os.path.abspath(mod_file))

    candidates = [
        os.path.normpath(os.path.join(here, "..", "..")),        # pip wheel
        here,                                                    # side-by-side
        os.path.normpath(os.path.join(here, "..", "..", "lib")),
        os.path.normpath(os.path.join(here, "..", "lib")),
        os.path.normpath(os.path.join(here, "..", "..", "..", "lib")),
    ]
    for cand in candidates:
        if _has_libgmsh(cand):
            return cand
    return None


def gmsh_missing_hint() -> str | None:
    """A ready-to-log warning when libgmsh cannot be found, else None.

    Kept separate from :func:`mesher_env` so the env builder stays side-effect
    free and each caller decides where the message goes (log panel / stderr).
    """
    if gmsh_lib_dir() is not None:
        return None
    return (
        "[WARNING] Could not locate libgmsh — the mesh generator may fail to "
        "start. Install the matching gmsh wheel (pip install -r "
        "tools/PreProcessor/gui/requirements.txt) or set HYBMESH_GMSH_LIB_DIR "
        "to the directory containing libgmsh, then rebuild with ./build.sh."
    )


def mesher_env(base: dict | None = None) -> dict:
    """Environment for launching HybMesh2D / surface_resampler.

    Returns a copy of ``base`` (default: the current environment) with the
    gmsh library directory prepended to the platform's loader search path. An
    existing value is preserved, and an already-present directory is not
    duplicated. When libgmsh cannot be found the environment is returned
    unchanged — the run still proceeds, since a correctly-baked ``rpath`` or a
    system-wide install may well satisfy the loader on its own.
    """
    env = dict(os.environ if base is None else base)
    lib_dir = gmsh_lib_dir()
    if not lib_dir:
        return env
    existing = [p for p in env.get(LIB_PATH_VAR, "").split(os.pathsep) if p]
    if lib_dir not in existing:
        env[LIB_PATH_VAR] = os.pathsep.join([lib_dir] + existing)
    return env
