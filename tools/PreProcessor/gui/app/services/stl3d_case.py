"""Qt-free immersed-solid (STL3d) case-directory orchestration.

Extracted from ``controllers/stl3d_ctrl.py`` for the same reason
:mod:`app.services.solver_case` was extracted from the solver controller: the
staging logic — where ``results/stl3d/<case>`` lives, how the STL is copied under a
whitespace-safe name, how ``para.in`` is written — was tangled with Qt widget
updates, so the headless pipeline could not run the IB stage at all. A pipeline
script could *describe* an immersed-solid case (schema v2's ``stl3d`` section) but
``run_pipeline.sh`` had to say "not executed here".

The input-file *format* stays on :class:`Stl3dConfig` (``para_in_text``,
``stl_run_basename``, ``output_basenames``); this module only orchestrates
directories and staging, and validates the preconditions once for both callers.
"""
from __future__ import annotations

import os
import shutil

from app.models.stl3d_config import Stl3dConfig
from app.services.solver_case import sanitize_case_name
from app.utils import find_stl3d_binary, repo_root


class Stl3dError(RuntimeError):
    """A precondition failed or the work directory could not be staged.

    The message is user-facing and already explains the remedy, so callers can log
    it verbatim (the GUI to its log panel, the runner to stdout).
    """


def work_dir_for(cfg: Stl3dConfig, root: str | None = None) -> str:
    """``results/stl3d/<sanitised case name>`` for this config."""
    base = root or repo_root()
    return os.path.join(base, "results", "stl3d",
                        sanitize_case_name(cfg.case_name, default="phi"))


def validate(cfg: Stl3dConfig) -> list:
    """Preconditions for a runnable IB case; empty list when it is runnable.

    Checked in one place so the GUI's Run button and the headless runner refuse the
    same cases for the same stated reasons.
    """
    problems = []
    if not cfg.stl_path:
        problems.append("No STL file selected (set the STL input path).")
    elif not os.path.exists(cfg.stl_path):
        problems.append(f"STL file not found: {cfg.stl_path}")
    if cfg.xmax <= cfg.xmin:
        problems.append("Domain X range must have max > min.")
    if cfg.ymax <= cfg.ymin:
        problems.append("Domain Y range must have max > min.")
    # Z may legitimately be DEGENERATE: this is a 2D project, so the STL is a flat
    # sheet at z=0 and fit_to_bbox produces zmin == zmax == 0 with nz == 1. Only a
    # genuinely inverted range is an error. (Requiring zmax > zmin here rejected
    # every normal 2D case.)
    if cfg.zmax < cfg.zmin:
        problems.append("Domain Z range is inverted (max < min).")
    if min(cfg.nx, cfg.ny, cfg.nz) < 1:
        problems.append("Grid resolution (Nx/Ny/Nz) must be at least 1 in each axis.")
    return problems


def omp_threads(cfg: Stl3dConfig) -> int:
    """OMP_NUM_THREADS for this run (1 = serial).

    The enable flag and the thread count are independent on the config, so
    "enabled with 1 thread" stays serial rather than being read as disabled.
    """
    if not getattr(cfg, "omp_enabled", False):
        return 1
    return max(int(getattr(cfg, "omp_threads", 1) or 1), 1)


def prepare_case_dir(cfg: Stl3dConfig, root: str | None = None) -> dict:
    """Stage the STL3d work directory and return everything needed to run it.

    Returns ``{work_dir, para_path, stl_path, phi_path, stl_tec_path, binary,
    threads}``. Raises :class:`Stl3dError` with a user-facing message when a
    precondition fails or the directory cannot be written.
    """
    problems = validate(cfg)
    if problems:
        raise Stl3dError(" ".join(problems))

    binary = find_stl3d_binary()
    if not binary:
        raise Stl3dError("STL3d binary not found under solver/preprocess/STL3d/.")

    work_dir = work_dir_for(cfg, root)
    try:
        os.makedirs(work_dir, exist_ok=True)
        # Stage under a whitespace-safe basename matching para.in line 1: STL3d
        # reads the filename with `cin >>`, so a space in the source name (e.g. a
        # CAD profile "my model" -> "my model_2d.stl") would misalign every later
        # answer in para.in and crash or hang the binary.
        stl_dst = os.path.join(work_dir, cfg.stl_run_basename())
        if os.path.abspath(cfg.stl_path) != os.path.abspath(stl_dst):
            shutil.copy2(cfg.stl_path, stl_dst)
        para_path = os.path.join(work_dir, "para.in")
        with open(para_path, "w", encoding="utf-8") as f:
            f.write(cfg.para_in_text())
    except OSError as e:
        raise Stl3dError(f"Failed to stage the STL3d work dir: {e}") from e

    stl_tec, phi_tec = cfg.output_basenames()
    return {
        "work_dir": work_dir,
        "para_path": para_path,
        "stl_path": stl_dst,
        "phi_path": os.path.join(work_dir, phi_tec),
        "stl_tec_path": os.path.join(work_dir, stl_tec),
        "binary": binary,
        "threads": omp_threads(cfg),
    }


def describe(cfg: Stl3dConfig) -> str:
    """One-line summary of what a run will do, for the log."""
    return (f"{cfg.nx}x{cfg.ny}x{cfg.nz} grid, "
            f"{'all-element' if cfg.all_search else 'close x-range'} search, "
            + ("serial" if omp_threads(cfg) == 1
               else f"OpenMP {omp_threads(cfg)} threads"))
