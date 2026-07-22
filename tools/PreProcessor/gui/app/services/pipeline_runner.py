"""Qt-free, blocking end-to-end pipeline runner.

Drives the same three CLI binaries the GUI drives — surface_resampler,
HybMesh2D, then the getPGrid -> unicones solver chain — but synchronously and
without any Qt dependency, so it can run headless from a plain Python process.

The per-stage *config file formats* all come from the shared config models
(:class:`ProjectModel`, :class:`MeshConfig`, :class:`SolverConfig`) and the case
layout from :mod:`app.services.solver_case`, so this runner only owns the
sequencing + subprocess plumbing.
"""
from __future__ import annotations
import os
import tempfile
import subprocess
import threading

from app.models.pipeline_config import PipelineConfig
from app.services import solver_case
from app.utils import (
    find_binary_executable, find_solver_executables, repo_root,
)

# tag distinguishes CLI solver output (xtecp_sol_allz.dat.cli) from the GUI's.
SOLVER_TAG = ".cli"


class PipelineError(RuntimeError):
    """A pipeline stage failed; message is human-readable and already logged."""


def _stream(cmd, cwd, log, env=None, stdin_path=None, timeout=1800) -> int:
    """Run a subprocess, streaming stdout to ``log`` line by line. Any stderr is
    captured separately and, on failure, logged prefixed with ``[stderr]`` so the
    warning/error stream stays distinguishable from normal stdout output.
    Returns the process return code."""
    log(f"$ {' '.join(cmd)}   (cwd={cwd})")
    # Open stdin inside the try so a Popen failure can't leak the handle.
    try:
        stdin_f = open(stdin_path, "rb") if stdin_path else None
        try:
            proc = subprocess.Popen(
                cmd, cwd=cwd, env=env, stdin=stdin_f,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
            # Drain stderr on a background thread so it is read CONCURRENTLY with
            # stdout. Reading stdout to completion first and only then reading
            # stderr deadlocks the moment a stage writes more than the OS stderr
            # pipe buffer (~64KB) before exiting: the child blocks on write(stderr),
            # stops producing stdout, and we block forever in the stdout loop.
            err_lines: list[str] = []

            def _drain_stderr():
                if not proc.stderr:
                    return
                for eline in proc.stderr:
                    es = eline.rstrip()
                    if es:
                        err_lines.append(es)

            err_thread = threading.Thread(target=_drain_stderr, daemon=True)
            err_thread.start()
            for line in proc.stdout:
                s = line.rstrip()
                if s:
                    log(s)
            proc.wait(timeout=timeout)
            # stderr is fully consumed once the pipe closes at process exit.
            err_thread.join(timeout=timeout)
            # Surface the captured stderr (kept separate from stdout above),
            # prefixed so it is clearly the error/warning stream.
            for s in err_lines:
                log(f"[stderr] {s}")
            return proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            log(f"[ERROR] timed out after {timeout}s")
            return -3
        finally:
            if stdin_f:
                stdin_f.close()
    except OSError as e:
        log(f"[ERROR] failed to launch {cmd[0]!r}: {e}")
        return -1


def _mesh_env():
    """Environment for HybMesh2D: inherit the caller's env (so a wrapper that
    exports DYLD_LIBRARY_PATH for Gmsh — like run.sh — is honoured)."""
    return os.environ.copy()


# --------------------------------------------------------------------------- #
# Stage 1: CAD resample
# --------------------------------------------------------------------------- #
def _run_resample(pcfg: PipelineConfig, repo: str, log) -> str:
    exe = find_binary_executable("surface_resampler")
    if not exe:
        raise PipelineError("surface_resampler binary not found — run ./build.sh")
    cad_out = pcfg.default_cad_output(repo)
    os.makedirs(os.path.dirname(cad_out), exist_ok=True)
    pm = pcfg.build_project_model(repo, cad_out)
    if not pm.input_file or not os.path.exists(pm.input_file):
        raise PipelineError(f"CAD input geometry not found: {pm.input_file!r}")

    # Create the temp config inside the try so its removal is guaranteed even if
    # creation or export raises before we'd otherwise reach a guard.
    cfg_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", suffix="_pipe_cad.json",
                                         delete=False) as tf:
            cfg_path = tf.name
        pm.export_config(cfg_path)
        rc = _stream([exe, cfg_path], cwd=repo, log=log)
    finally:
        _rm(cfg_path)
    if rc != 0:
        raise PipelineError(f"surface_resampler failed (code {rc})")
    if not os.path.exists(cad_out):
        raise PipelineError(f"resampler produced no output at {cad_out}")
    log(f"[CAD] resampled -> {cad_out}")
    return cad_out


# --------------------------------------------------------------------------- #
# Stage 2: mesh generation (HybMesh2D)
# --------------------------------------------------------------------------- #
def _run_mesh(pcfg: PipelineConfig, repo: str, geom_file: str,
              need_starcd: bool, log) -> str:
    exe = find_binary_executable("HybMesh2D")
    if not exe:
        raise PipelineError("HybMesh2D binary not found — run ./build.sh")

    mc = pcfg.build_mesh_config(geom_file)
    mc.export_vtk = True
    if need_starcd:
        mc.export_starcd = True
    # Pin a deterministic output path so we know exactly where the VTK (and the
    # sibling STAR-CD .vrt/.cel/.bnd) land.
    if not mc.output_filename:
        stem = os.path.splitext(os.path.basename(geom_file))[0] if geom_file else pcfg.name
        mc.output_filename = os.path.join(repo, "results", "meshes", f"mesh_{stem}.vtk")
    vtk = mc.output_filename if os.path.isabs(mc.output_filename) \
        else os.path.abspath(os.path.join(repo, mc.output_filename))
    mc.output_filename = vtk
    os.makedirs(os.path.dirname(vtk), exist_ok=True)

    if not mc.geom_files:
        raise PipelineError("mesh stage has no geometry input (geom_files empty)")

    # Create the temp config inside the try so its removal is guaranteed even if
    # creation or save raises before we'd otherwise reach a guard.
    cfg_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", suffix="_pipe_mesh.dat",
                                         delete=False) as tf:
            cfg_path = tf.name
        mc.save_to_file(cfg_path)
        rc = _stream([exe, "-conf", cfg_path], cwd=repo, log=log, env=_mesh_env())
    finally:
        _rm(cfg_path)
    if rc != 0:
        raise PipelineError(f"HybMesh2D failed (code {rc})")
    if not os.path.exists(vtk):
        raise PipelineError(f"mesh generation produced no VTK at {vtk}")
    log(f"[Mesh] generated -> {vtk}")
    return vtk


# --------------------------------------------------------------------------- #
# Stage 3: solver (getPGrid -> unicones)
# --------------------------------------------------------------------------- #
def _run_solver(pcfg: PipelineConfig, repo: str, vtk: str, log) -> str:
    sc = pcfg.build_solver_config(repo)

    # Auto-link the STAR-CD output of the mesh, filling each input independently
    # so an explicitly-named input isn't clobbered when the others are blank.
    base = os.path.splitext(vtk)[0]
    sc.input_vrt_file = sc.input_vrt_file or base + ".vrt"
    sc.input_cel_file = sc.input_cel_file or base + ".cel"
    sc.input_bnd_file = sc.input_bnd_file or base + ".bnd"
    for f, label in [(sc.input_vrt_file, ".vrt"), (sc.input_cel_file, ".cel"),
                     (sc.input_bnd_file, ".bnd")]:
        if not os.path.exists(f):
            raise PipelineError(
                f"solver input {label} missing: {f} "
                "(enable STAR-CD export in the mesh stage)")

    bins = find_solver_executables()
    if not bins.get("getpgrid"):
        raise PipelineError("getPGrid binary not found under solver/")
    if not bins.get("solver"):
        raise PipelineError("unicones solver binary not found under solver/")
    sc.getpgrid_binary = bins["getpgrid"]
    sc.solver_binary = bins["solver"]

    work_dir, grid_dir, input_in = solver_case.prepare_case_dir(sc, log=log)

    # getPGrid: interactive, answers fed on stdin via para.in (run in grid_dir).
    para = os.path.join(grid_dir, "para.in")
    sc.generate_getpgrid_para(para)
    rc = _stream([sc.getpgrid_binary], cwd=grid_dir, log=log, stdin_path=para)
    if rc != 0:
        raise PipelineError(f"getPGrid failed (code {rc})")

    # The solver reads "<bc>.def" from its cwd; use getPGrid's companion verbatim
    # unless the user supplied an explicit BC table (already written to work/).
    solver_case.stage_bc_def_companion(sc, grid_dir, work_dir, log=log)

    # unicones solver (run in work_dir so relative grid/bc paths resolve).
    rc = _stream([sc.solver_binary, "-t", SOLVER_TAG, input_in],
                 cwd=work_dir, log=log)
    if rc != 0:
        raise PipelineError(f"unicones solver failed (code {rc})")

    result = os.path.join(work_dir, f"xtecp_sol_allz.dat{SOLVER_TAG}")
    if not os.path.exists(result):
        raise PipelineError(
            "solver finished but wrote no Tecplot result "
            f"({os.path.basename(result)}); check print_sol_per_niter vs num_half_iter")
    log(f"[Solver] result -> {result}")
    return result


def _rm(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_pipeline(pcfg: PipelineConfig, log=print, run_solver: bool = True) -> dict:
    """Run CAD -> mesh -> (solver). Returns a dict of produced artifact paths:
    {"cad_out", "vtk", "result"}. Raises :class:`PipelineError` on any stage
    failure (message already logged)."""
    repo = repo_root()
    out = {"cad_out": "", "vtk": "", "result": ""}

    # Stage 1 — CAD (optional).
    if pcfg.cad_skip():
        geom = pcfg.resolve_input_file(repo)
        if geom:
            log(f"[CAD] resample skipped; using {geom}")
        else:
            log("[CAD] resample skipped (no source geometry); "
                "meshing configured geometry files.")
    else:
        log("=== Stage 1/3: CAD resample ===")
        geom = _run_resample(pcfg, repo, log)
    out["cad_out"] = geom

    # Stage 2 — mesh.
    log("=== Stage 2/3: mesh generation ===")
    need_solver = run_solver and not pcfg.solver_skip()
    out["vtk"] = _run_mesh(pcfg, repo, geom, need_starcd=need_solver, log=log)

    # Stage 3 — solver.
    if need_solver:
        log("=== Stage 3/3: solver ===")
        out["result"] = _run_solver(pcfg, repo, out["vtk"], log)
    else:
        log("=== solver stage skipped ===")
    return out
