"""Where things are: the repository root and the binaries the stages run.

Qt-free on purpose, and that is the whole reason this module exists rather than
living in :mod:`app.utils`. These helpers answer ``os``/``shutil`` questions —
they have nothing to do with a window — but they used to sit in a file whose
first line is ``from PyQt6.QtCore import ...``. Every headless module that
needed a path therefore imported the entire GUI toolkit: ``run_pipeline.sh`` and
``run_batch.sh`` required PyQt6 on a compute node that will never draw
anything, and the "Qt-free, headless-safe" claim three service docstrings make
was not checkable by anything. ``tests/test_qt_free_seam.py`` now checks it, in
a subprocess — in-process the answer is always "PyQt6 is loaded" as soon as any
other test has imported it, so the check would pass for the wrong reason exactly
when it matters.

:func:`is_headless` deliberately stayed behind in :mod:`app.utils`: it asks
which Qt platform plugin is running, so it belongs with the Qt helpers even
though its own import of ``QApplication`` is deferred into the function body.
"""
from __future__ import annotations
import os
import shutil

# The module's own list of what moved here off the Qt side. `test_qt_free_seam`
# derives its check from this rather than repeating the six names, so the gate
# cannot describe a different set than the module exports.
__all__ = [
    "repo_root",
    "find_binary_executable",
    "find_solver_executables",
    "find_stl3d_binary",
    "find_mpi_launcher",
    "is_mpi_binary",
]


def repo_root() -> str:
    """Absolute path to the repository root (the HybMesh project directory).

    Single source of truth for the project root. Callers previously derived it
    ad-hoc as ``os.path.join(dirname(__file__), "../...")`` with the number of
    ``..`` segments depending on the file's depth — an easy off-by-one to get
    wrong. This file lives at ``gui/app/services/paths.py``, five levels below
    the repo root.

    That warning earned itself: this module's own move down one level (from
    ``gui/app/utils.py``) is exactly the situation it describes, so the count
    here is pinned by resolved *path* in ``tests/test_qt_free_seam.py`` rather
    than by counting segments. Nothing else in this file computes a depth —
    :func:`find_binary_executable` used to keep a second, disagreeing count and
    now goes through here.
    """
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../.."))


def find_binary_executable(bin_name: str) -> str | None:
    """Locate binary executable in PATH environment or local build candidates."""
    path_run = shutil.which(bin_name)
    if path_run:
        return path_run

    candidates = [
        os.path.join(repo_root(), "build"),
        os.path.abspath("../../../build"),
        os.path.abspath("./build"),
        os.path.abspath("."),
    ]
    for folder in candidates:
        full_path = os.path.join(folder, bin_name)
        if os.path.exists(full_path) and os.access(full_path, os.X_OK) and not os.path.isdir(full_path):
            return full_path
    return None


# Prebuilt solver-pipeline binaries shipped under solver/ (decision D5: use the
# existing binaries, no compilation step). Paths are relative to the repo root.
_SOLVER_BIN_REL = {
    "getpgrid": "solver/preprocess/getPGrid/work/getPGrid",
    "bdecompose": "solver/preprocess/bDecompose/work/bDecompose",
    "solver": "solver/execute/unicones.eqn6.mac",
}


def find_solver_executables() -> dict:
    """Locate the prebuilt getPGrid / bDecompose / unicones binaries.

    Returns a dict {name: abs_path | None}. Existence (not executability) is
    reported, since bDecompose ships without the +x bit and the solver worker
    chmods it on demand when domain decomposition is enabled.
    """
    repo = repo_root()
    found: dict[str, str | None] = {}
    for name, rel in _SOLVER_BIN_REL.items():
        full = os.path.join(repo, rel)
        found[name] = full if os.path.exists(full) else None
    return found


def find_stl3d_binary() -> str | None:
    """Locate the prebuilt STL3d immersed-solid preprocessor binary.

    Mirrors find_solver_executables (decision D5: use the existing binaries). The
    binary ships in both the work and src dirs; prefer the work-dir copy.
    """
    repo = repo_root()
    for rel in ("solver/preprocess/STL3d/work/stl3d",
                "solver/preprocess/STL3d/src/stl3d"):
        full = os.path.join(repo, rel)
        if os.path.exists(full):
            return full
    return None


def find_mpi_launcher() -> str | None:
    """Return the path to mpirun/mpiexec on PATH, or None if neither is present."""
    return shutil.which("mpirun") or shutil.which("mpiexec")


def is_mpi_binary(path: str) -> bool:
    """Heuristic: does this executable actually link MPI?

    Scans the binary for the `MPI_Init` symbol name. A pthread/serial build (like
    the bundled unicones) has no MPI symbols, so domain decomposition + mpirun
    would be meaningless against it.
    """
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as f:
            blob = f.read()
    except OSError:
        return False
    return b"MPI_Init" in blob
