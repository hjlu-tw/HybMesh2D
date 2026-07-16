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


def _dir_has_content(path: str) -> bool:
    """True when ``path`` exists and is a non-empty directory."""
    return os.path.isdir(path) and bool(os.listdir(path))


def resolve_case_root(root: str, case: str, overwrite: bool, log=_noop) -> str:
    """Pick the ``results/solver/<case>`` directory to write into.

    When the default case dir already holds prior results and ``overwrite`` is
    False, auto-version to ``<case>_002``, ``<case>_003``, … so a re-run never
    silently clobbers earlier output. Returns the actual directory path (not yet
    created). ``overwrite=True`` reuses the default dir in place.
    """
    default = os.path.join(root, "results", "solver", case)
    if overwrite or not _dir_has_content(default):
        return default
    for n in range(2, 1000):
        candidate = os.path.join(root, "results", "solver", f"{case}_{n:03d}")
        if not _dir_has_content(candidate):
            log(f"[case] '{case}' already has results; writing to "
                f"'{os.path.basename(candidate)}' to preserve them "
                "(pass overwrite=True to reuse the existing dir).")
            return candidate
    # Pathological: 998 versions exist. Fall back to overwriting the default
    # rather than looping forever.
    log(f"[WARNING] too many versions of case '{case}'; overwriting "
        f"'{case}'.")
    return default


def stage_dll(src: str, out_dir: str, rel_prefix: str = "../dll",
              log=_noop) -> str:
    """Compile a .cc/.cpp DLL source into ``out_dir`` (or copy a prebuilt .so).

    Returns the path the solver should reference from its work dir
    (``<rel_prefix>/<name>.so``, e.g. "../dll/foo.so" for IBM DLLs staged into
    the sibling dll/ dir, or "./foo.so" for a BC DLL staged into the work dir
    itself) or "" if no source given / compilation failed.
    """
    if not src:
        return ""
    base = os.path.splitext(os.path.basename(src))[0]
    out_so = os.path.join(out_dir, f"{base}.so")
    if src.endswith(".so"):
        if os.path.abspath(src) != os.path.abspath(out_so):
            shutil.copy2(src, out_so)
    else:
        if not os.path.exists(src):
            log(f"[WARNING] DLL source not found, skipping: {src}")
            return ""
        cmd = ["g++", "-D_INCLUDE_TEMPLATE_IMPLEMENTATION", "-fPIC",
               "-shared", "-O3", "-o", out_so, src]
        log(f"[DLL] compiling {os.path.basename(src)} -> {base}.so")
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                log(f"[WARNING] DLL compile failed: {r.stderr.strip()}")
                return ""
        except OSError as e:
            log(f"[WARNING] g++ unavailable, cannot compile DLL: {e}")
            return ""
    return f"{rel_prefix}/{base}.so"


def stage_bc_dll_paths(cfg: SolverConfig, work_dir: str, log=_noop) -> None:
    """Resolve BC type-11 (user DLL) paths so the solver can dlopen them (#7).

    The BC .def line for a type-11 patch is ``<seg>  11  "./name.so"`` — a
    quoted path the solver loads from its cwd (the work dir). The GUI's DLL
    builder hands back a ``.cc`` source, so here we compile/copy each type-11
    source into the work dir and rewrite the row's ``values`` to ``"./name.so"``.
    A value that is already a bare ``./name.so`` reference (the user manages the
    binary themselves) is just normalised + quoted. Mutates cfg.bc_definitions
    in place; runs before generate_bc_def so the written table is correct.
    """
    for bc in cfg.bc_definitions:
        if bc.get("bc_type") != 11:
            continue
        raw = str(bc.get("values", "") or "").strip().strip('"').strip("'")
        if not raw:
            continue
        if os.path.exists(raw):
            rel = stage_dll(raw, work_dir, rel_prefix=".", log=log)
            if rel:
                bc["values"] = f'"{rel}"'
                continue
        # A bare / relative reference whose binary the user stages themselves:
        # keep it, but give it a leading ./ and quotes so the .def line is valid.
        name = raw if raw.startswith(("./", "../", "/")) else "./" + raw
        bc["values"] = f'"{name}"'


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


def prepare_case_dir(cfg: SolverConfig, log=_noop, overwrite: bool = False):
    """Build ``results/solver/<name>/{work,grid,dll}``, stage getPGrid inputs,
    rename outputs, write ``input.in`` / ``.def``, and compile IBM DLLs.

    Mutates ``cfg`` in place (paths are rewritten to the staged locations, as the
    solver worker expects). Returns ``(work_dir, grid_dir, input_in_path)``.

    By default (``overwrite=False``) an existing, non-empty case dir is NOT
    clobbered: the case auto-versions to ``<case>_002`` etc. (see
    :func:`resolve_case_root`) so prior results are preserved. Pass
    ``overwrite=True`` to reuse the existing dir in place.
    """
    root = repo_root()
    case = sanitize_case_name(cfg.case_name)
    case_root = resolve_case_root(root, case, overwrite, log)
    # If auto-versioning renamed the case, keep cfg's case_name in sync so the
    # solver's -t tag / result path and any later references use the real dir.
    actual_case = os.path.basename(case_root)
    if actual_case != case:
        cfg.case_name = actual_case
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

    # Initial-condition DLL (IBM or not): compile the .cc into dll/ and reference
    # it as ../dll/*.so. Non-IBM cases can drive the initial field from a DLL too
    # (#4), so this is staged independently of the immersed-solid block below.
    if cfg.init_cond_dll:
        cfg.init_cond_dll = stage_dll(cfg.init_cond_dll, dll_dir,
                                      rel_prefix="../dll", log=log)

    # IBM extras: motion DLL into dll/, phi field into work/.
    if cfg.immersed_solid:
        cfg.motion_dll = stage_dll(cfg.motion_dll, dll_dir,
                                   rel_prefix="../dll", log=log)
        if cfg.ibm_phi_file:
            stage_phi_file(cfg.ibm_phi_file, work_dir, log)

    # Solver boundary-condition table. The solver reads "<bc>.def" from its cwd;
    # by default it uses getPGrid's own companion verbatim (copied by the runner).
    # Only when the user fills the BC table do we write an override here. BC
    # type-11 user DLLs are compiled into the work dir + rewritten to "./x.so"
    # BEFORE the table is written so the .def references a loadable binary (#7).
    if cfg.bc_definitions:
        stage_bc_dll_paths(cfg, work_dir, log)
        def_name = os.path.basename(cfg.output_bc_file) + ".def"
        cfg.generate_bc_def(os.path.join(work_dir, def_name))

    # input.in with paths relative to the work dir.
    input_in_path = os.path.join(work_dir, "input.in")
    cfg.generate_input_in(
        input_in_path,
        grid_rel=f"../grid/{stem}.grid",
        bc_rel=f"../grid/{stem}.bc")

    return work_dir, grid_dir, input_in_path
