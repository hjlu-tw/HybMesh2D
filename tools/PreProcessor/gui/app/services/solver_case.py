"""Qt-free solver case-directory orchestration.

Extracted from ``controllers/solver_ctrl.py`` so the GUI solver pipeline and the
headless CLI runner share one source of truth for how a ``results/solver/<case>``
directory is laid out, how getPGrid inputs are staged, how IBM DLLs are compiled,
and how ``input.in`` is written. The actual input-file *formats* live on
:class:`SolverConfig`; this module only orchestrates directories + staging.
"""
from __future__ import annotations
import os
import re
import shutil
import subprocess

from app.models.solver_config import SolverConfig
from app.utils import repo_root


def _noop(_msg: str) -> None:
    pass


def sanitize_case_name(name: str) -> str:
    """Make a filesystem-safe case name."""
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", (name or "").strip())
    return s or "case"


def stage_dll(src: str, dll_dir: str, log=_noop) -> str:
    """Compile a .cc/.cpp DLL source into ``dll_dir`` (or copy a prebuilt .so).

    Returns the path relative to the work dir ("../dll/<name>.so") or "" if no
    source given / compilation failed.
    """
    if not src:
        return ""
    base = os.path.splitext(os.path.basename(src))[0]
    out_so = os.path.join(dll_dir, f"{base}.so")
    if src.endswith(".so"):
        if os.path.abspath(src) != os.path.abspath(out_so):
            shutil.copy2(src, out_so)
    else:
        if not os.path.exists(src):
            log(f"[WARNING] DLL source not found, skipping: {src}")
            return ""
        cmd = ["g++", "-D_INCLUDE_TEMPLATE_IMPLEMENTATION", "-fPIC",
               "-shared", "-O3", "-o", out_so, src]
        log(f"[IBM] compiling {os.path.basename(src)} -> {base}.so")
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                log(f"[WARNING] DLL compile failed: {r.stderr.strip()}")
                return ""
        except OSError as e:
            log(f"[WARNING] g++ unavailable, cannot compile DLL: {e}")
            return ""
    return f"../dll/{base}.so"


def stage_phi_file(src: str, work_dir: str, log=_noop) -> None:
    """Copy the STL3d phi field into the work dir as phi.dat (the name the
    generated init DLL reads)."""
    if not os.path.exists(src):
        log(f"[IBM] phi field not found, skipping: {src}")
        return
    dst = os.path.join(work_dir, "phi.dat")
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copy2(src, dst)
    log(f"[IBM] phi field -> {os.path.basename(dst)}")


def stage_bc_def_companion(cfg: SolverConfig, grid_dir: str, work_dir: str,
                           log=_noop) -> None:
    """Stage getPGrid's boundary-condition table so the solver finds it in its
    cwd: copy ``grid/<bc>.def`` -> ``work/<bc>.def``.

    Skipped when the user supplied an explicit BC override (``prepare_case_dir``
    already wrote it into ``work_dir``). Shared by the GUI solver worker and the
    headless pipeline runner so both stage the table identically.
    """
    if cfg.bc_definitions:
        return
    def_name = os.path.basename(cfg.output_bc_file) + ".def"
    companion = os.path.join(grid_dir, def_name)
    target = os.path.join(work_dir, def_name)
    if (os.path.exists(companion)
            and os.path.abspath(companion) != os.path.abspath(target)):
        shutil.copy2(companion, target)
        log(f"[getPGrid] segment table -> {def_name}")


def prepare_case_dir(cfg: SolverConfig, log=_noop):
    """Build ``results/solver/<name>/{work,grid,dll}``, stage getPGrid inputs,
    rename outputs, write ``input.in`` / ``.def``, and compile IBM DLLs.

    Mutates ``cfg`` in place (paths are rewritten to the staged locations, as the
    solver worker expects). Returns ``(work_dir, grid_dir, input_in_path)``.
    """
    root = repo_root()
    case = sanitize_case_name(cfg.case_name)
    case_root = os.path.join(root, "results", "solver", case)
    work_dir = os.path.join(case_root, "work")
    grid_dir = os.path.join(case_root, "grid")
    dll_dir = os.path.join(case_root, "dll")
    for d in (work_dir, grid_dir, dll_dir):
        os.makedirs(d, exist_ok=True)
    cfg.work_dir = work_dir

    # getPGrid runs in grid_dir: stage the STAR-CD inputs there with the
    # basenames para.in will reference, and have it write <case>.grid/.bc there.
    stem = case
    cfg.output_grid_file = f"{stem}.grid"
    cfg.output_bc_file = f"{stem}.bc"
    for src, base in [(cfg.input_vrt_file, "input.vrt"),
                      (cfg.input_cel_file, "input.cel"),
                      (cfg.input_bnd_file, "input.bnd")]:
        dst = os.path.join(grid_dir, base)
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)
    cfg.input_vrt_file = os.path.join(grid_dir, "input.vrt")
    cfg.input_cel_file = os.path.join(grid_dir, "input.cel")
    cfg.input_bnd_file = os.path.join(grid_dir, "input.bnd")

    # Solver boundary-condition table. The solver reads "<bc>.def" from its cwd;
    # by default it uses getPGrid's own companion verbatim (copied by the runner).
    # Only when the user fills the BC table do we write an override here.
    if cfg.bc_definitions:
        def_name = os.path.basename(cfg.output_bc_file) + ".def"
        cfg.generate_bc_def(os.path.join(work_dir, def_name))

    # IBM DLLs: compile .cc sources into dll/, reference as ../dll/*.so.
    if cfg.immersed_solid:
        cfg.init_cond_dll = stage_dll(cfg.init_cond_dll, dll_dir, log)
        cfg.motion_dll = stage_dll(cfg.motion_dll, dll_dir, log)
        if cfg.ibm_phi_file:
            stage_phi_file(cfg.ibm_phi_file, work_dir, log)

    # input.in with paths relative to the work dir.
    input_in_path = os.path.join(work_dir, "input.in")
    cfg.generate_input_in(
        input_in_path,
        grid_rel=f"../grid/{stem}.grid",
        bc_rel=f"../grid/{stem}.bc")

    return work_dir, grid_dir, input_in_path
