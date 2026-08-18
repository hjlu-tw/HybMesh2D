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

from app.models.mesh_config import MeshConfig
from app.models.pipeline_config import PipelineConfig
from app.services import (
    case_sources, ib_handoff, solver_case, stl3d_case,
)
from app.services.logging_setup import get_logger
from app.services.env_setup import mesher_env, gmsh_missing_hint
from app.services.paths import (
    find_binary_executable, find_solver_executables, repo_root,
)
# Qt-free process helpers (no PyQt import), so this module stays headless-safe.
from app.workers.proc_util import stop_process

_log = get_logger(__name__)

# tag distinguishes CLI solver output (xtecp_sol_allz.dat.cli) from the GUI's.
SOLVER_TAG = ".cli"


class PipelineError(RuntimeError):
    """A pipeline stage failed; message is human-readable and already logged."""


def _stream(cmd, cwd, log, env=None, stdin_path=None, timeout=1800,
            on_process=None) -> int:
    """Run a subprocess, streaming stdout to ``log`` line by line. Any stderr is
    captured separately and, on failure, logged prefixed with ``[stderr]`` so the
    warning/error stream stays distinguishable from normal stdout output.
    Returns the process return code.

    ``on_process(proc)`` is called as soon as the child exists, so a caller can cancel
    a stage that is already running. Without it a GUI Cancel could only take effect
    between stages, which for a mesh or a solve means minutes to hours of "cancelling"
    — a button that does not do what it says. The child is in its own process group
    (below), so ``proc_util.stop_process`` can take down its whole tree.
    """
    log(f"$ {' '.join(cmd)}   (cwd={cwd})")
    # Open stdin inside the try so a Popen failure can't leak the handle.
    try:
        stdin_f = open(stdin_path, "rb") if stdin_path else None
        try:
            proc = subprocess.Popen(
                cmd, cwd=cwd, env=env, stdin=stdin_f,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                # Own process group so the timeout path can take down the whole
                # tree (mpirun ranks, gmsh helpers), not just the direct child.
                start_new_session=True,
            )
            if on_process is not None:
                on_process(proc)
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
            stop_process(proc)
            log(f"[ERROR] timed out after {timeout}s")
            return -3
        finally:
            if stdin_f:
                stdin_f.close()
    except OSError as e:
        log(f"[ERROR] failed to launch {cmd[0]!r}: {e}")
        return -1


def _mesh_env():
    """Environment for HybMesh2D / surface_resampler.

    Resolves the libgmsh directory here rather than inheriting it from a shell
    wrapper: on macOS, SIP strips every ``DYLD_*`` variable when a protected
    interpreter starts, so ``run_pipeline.sh``'s export is already gone by the
    time this process reads ``os.environ`` (see app/services/env_setup.py)."""
    return mesher_env()


# --------------------------------------------------------------------------- #
# Stage 1: CAD resample
# --------------------------------------------------------------------------- #
def _run_resample(pcfg: PipelineConfig, repo: str, log, index: int = 0,
                  on_process=None) -> str:
    exe = find_binary_executable("surface_resampler")
    if not exe:
        raise PipelineError("surface_resampler binary not found — run ./build.sh")
    cad_out = pcfg.default_cad_output(repo, index)
    os.makedirs(os.path.dirname(cad_out), exist_ok=True)
    pm = pcfg.build_project_model(repo, cad_out, index)
    if not pm.input_file or not os.path.exists(pm.input_file):
        raise PipelineError(f"CAD input geometry not found: {pm.input_file!r}")

    # No snapshot/restore of the MESH-stage per-segment edits around this
    # subprocess any more. The BC label and the No-BL flag are SegmentModel
    # fields, so pm.export_config() below carries them into the resampler's own
    # config (which has always read sj["bc"] / sj["grow_bl"]) and the sidecar is
    # written correctly the first time. The old wrapper had to refuse itself
    # whenever the segment id set changed, because it re-applied by id after a
    # subprocess had rewritten the file; a field on the segment has no such gap.

    # Create the temp config inside the try so its removal is guaranteed even if
    # creation or export raises before we'd otherwise reach a guard.
    cfg_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", suffix="_pipe_cad.json",
                                         delete=False) as tf:
            cfg_path = tf.name
        pm.export_config(cfg_path)
        rc = _stream([exe, cfg_path], cwd=repo, log=log, env=_mesh_env(),
                     on_process=on_process)
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
def _mesh_output_path(mc: MeshConfig, script_name: str, repo: str) -> str:
    """The absolute ``.vtk`` path this stage will make the mesher write.

    Pinned rather than discovered, so we know exactly where the VTK — and the
    sibling STAR-CD ``.vrt``/``.cel``/``.bnd`` — land. Two things it has to get
    right:

    * an **empty** name is auto-named after the FIRST boundary geometry (the
      primary body), or after the script when there is none: with several
      geometries in play ``geom_files[0]`` is the choice a re-run reproduces;
    * a name carrying the GUI Output field's ``.*`` all-formats placeholder (it
      travels verbatim in a workspace / pipeline script) resolves to the real
      ``.vtk``. The mesher would otherwise write a file literally NAMED
      ``<case>.*`` — which the caller's existence check then accepted, so the
      pipeline "succeeded" and handed the contour stage a glob.
    """
    name = mc.output_filename
    if not name:
        primary = mc.geom_files[0] if mc.geom_files else ""
        stem = os.path.splitext(os.path.basename(primary))[0] if primary else script_name
        name = os.path.join(repo, "results", "meshes", f"mesh_{stem}.vtk")
    name = MeshConfig.output_path_for(name, ".vtk")
    return name if os.path.isabs(name) else os.path.abspath(os.path.join(repo, name))


def _run_mesh(pcfg: PipelineConfig, repo: str, geom_files: str | list,
              need_starcd: bool, log, on_process=None) -> str:
    exe = find_binary_executable("HybMesh2D")
    if not exe:
        raise PipelineError("HybMesh2D binary not found — run ./build.sh")

    mc = pcfg.build_mesh_config(geom_files)
    mc.export_vtk = True
    if need_starcd:
        mc.export_starcd = True
    vtk = _mesh_output_path(mc, pcfg.name, repo)
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
        hint = gmsh_missing_hint()
        if hint:
            log(hint)
        rc = _stream([exe, "-conf", cfg_path], cwd=repo, log=log, env=_mesh_env(),
                     on_process=on_process)
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
def _run_stl3d(pcfg: PipelineConfig, repo: str, log, on_process=None) -> str:
    """Immersed-solid stage: STL -> phi field. Returns the phi Tecplot path.

    Uses the same staging service as the GUI (``services/stl3d_case``), so a case
    described by a pipeline script lands in the same ``results/stl3d/<case>``
    directory with the same para.in the interactive run would produce.
    """
    cfg = pcfg.build_stl3d_config(repo)
    case = stl3d_case.prepare_case_dir(cfg, root=repo)      # raises Stl3dError
    log(f"[IB] {stl3d_case.describe(cfg)} -> {case['work_dir']}")

    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(case["threads"])
    # STL3d is interactive: it reads its answers from stdin, which is exactly what
    # para.in is (see Stl3dConfig.para_in_text).
    rc = _stream([case["binary"]], cwd=case["work_dir"], log=log, env=env,
                 on_process=on_process,
                 stdin_path=case["para_path"])
    if rc != 0:
        raise PipelineError(f"STL3d failed (code {rc})")
    if not os.path.exists(case["phi_path"]):
        raise PipelineError(
            f"STL3d produced no phi field at {case['phi_path']}")
    log(f"[IB] phi field -> {case['phi_path']}")
    return case["phi_path"]


def _case_sources(pcfg: PipelineConfig, repo: str, geoms, vtk: str):
    """``(sources, generated)`` for staging a scripted case's grid/cad/.

    The headless twin of ``solver_ctrl._case_source_files`` /
    ``_case_generated_files``: the same things per body — the imported source and
    the resampled ``.dat`` the mesher read, plus the immersed STL, the mesh
    provenance sidecar and the mesh parameter file — so a case run from a script
    carries what a case run from the GUI carries. Nothing is filtered by whether
    the resample ran: a skipped CAD entry still points at a geometry the mesh was
    cut from, and the staging service drops whatever does not exist on disk.
    """
    from app.models.mesh_config_io import config_to_text

    out: list = []
    for i in pcfg.cad_indices():
        out.append(pcfg.resolve_input_file(repo, i))
        out.append(pcfg.default_cad_output(repo, i))
    stl = (pcfg.stl3d or {}).get("stl_path", "")
    if stl:
        out.append(stl if os.path.isabs(stl) else os.path.join(repo, stl))
    out.extend(case_sources.mesh_provenance_paths(vtk))

    generated: list = []
    try:
        mc = pcfg.build_mesh_config(geoms)
        mc.output_filename = vtk or mc.output_filename
        generated.append((f"Background_para_{pcfg.name or 'case'}.dat",
                          config_to_text(mc)))
    except Exception:
        # Staging the geometry is worth having even when the settings cannot be
        # re-serialised; failing the solver run over it is not.
        _log.warning("could not serialise the mesh config for the case's cad/ "
                     "folder", exc_info=True)
    return [p for p in out if p], generated


def _run_solver(pcfg: PipelineConfig, repo: str, vtk: str, log,
                on_process=None, geoms=None, phi: str = "") -> str:
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

    # Auto-link the immersed-solid stage's own output by the same rule: the phi
    # field this run just traced is what the solve reads unless the script named
    # one itself. Nothing carried it before, so the stage's result went nowhere
    # and the solve fell back to whatever work/phi.dat the reused case directory
    # still held — the previous geometry's solid (services/ib_handoff explains
    # why handing over a Tecplot path alone would not have been enough either).
    if phi and sc.immersed_solid:
        try:
            ib_handoff.link_phi_to_solver(sc, phi,
                                          pcfg.build_stl3d_config(repo),
                                          repo, log=log, replace=False)
        except ib_handoff.IbHandoffError as e:
            raise PipelineError(f"immersed-solid hand-off: {e}") from e
    elif phi:
        # The stage ran because the script has an stl3d section; whether the
        # SOLVE is immersed is the solver section's declaration to make.
        log("[IB] [WARNING] phi was traced but the solver section has "
            f"immersed_solid off, so the solve does not read it: {phi}")

    bins = find_solver_executables()
    if not bins.get("getpgrid"):
        raise PipelineError("getPGrid binary not found under solver/")
    if not bins.get("solver"):
        raise PipelineError("unicones solver binary not found under solver/")
    sc.getpgrid_binary = bins["getpgrid"]
    sc.solver_binary = bins["solver"]

    src_files, src_generated = _case_sources(pcfg, repo, geoms, vtk)
    work_dir, grid_dir, input_in = solver_case.prepare_case_dir(
        sc, log=log, sources=src_files, generated_sources=src_generated)

    # getPGrid: interactive, answers fed on stdin via para.in (run in grid_dir).
    para = os.path.join(grid_dir, "para.in")
    sc.generate_getpgrid_para(para)
    rc = _stream([sc.getpgrid_binary], cwd=grid_dir, log=log, stdin_path=para,
                 on_process=on_process)
    if rc != 0:
        raise PipelineError(f"getPGrid failed (code {rc})")

    # The solver reads "<bc>.def" from its cwd; use getPGrid's companion verbatim
    # unless the user supplied an explicit BC table (already written to work/).
    solver_case.stage_bc_def_companion(sc, grid_dir, work_dir, log=log)

    # unicones solver (run in work_dir so relative grid/bc paths resolve).
    rc = _stream([sc.solver_binary, "-t", SOLVER_TAG, input_in],
                 on_process=on_process,
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
def run_pipeline(pcfg: PipelineConfig, log=print, run_solver: bool = True,
                 run_ib: bool = True, on_process=None) -> dict:
    """Run CAD -> (immersed solid) -> mesh -> (solver). Returns a dict of the
    produced artifact paths: {"cad_out", "cad_outs", "phi", "vtk", "result"}.
    Raises :class:`PipelineError` on any stage failure (message already
    logged)."""
    repo = repo_root()
    out = {"cad_out": "", "cad_outs": [], "phi": "", "vtk": "", "result": ""}

    # Stage 1 — CAD, once per `cads` entry. A case routinely has several
    # geometries (airfoil + ground plane, multi-element wing, custom domain), and
    # every resampled output becomes a boundary for the mesh stage.
    indices = pcfg.cad_indices()
    if not indices:
        log("[CAD] no CAD section; meshing configured geometry files.")
        geoms = []
    elif pcfg.cads_all_skipped():
        geoms = [g for g in (pcfg.resolve_input_file(repo, i) for i in indices) if g]
        if geoms:
            log(f"[CAD] resample skipped; using {', '.join(geoms)}")
        else:
            log("[CAD] resample skipped (no source geometry); "
                "meshing configured geometry files.")
    else:
        log(f"=== Stage 1/3: CAD resample ({len(indices)} geometr"
            f"{'y' if len(indices) == 1 else 'ies'}) ===")
        geoms = []
        for i in indices:
            if pcfg.cad_skip(i):
                # Not an error: an entry may deliberately feed its raw geometry
                # straight to the mesher. Say so rather than dropping it silently.
                raw = pcfg.resolve_input_file(repo, i)
                log(f"[CAD] [{i + 1}/{len(indices)}] resample skipped"
                    + (f"; using {raw}" if raw else " (no source geometry)"))
                if raw:
                    geoms.append(raw)
                continue
            log(f"[CAD] [{i + 1}/{len(indices)}] resampling...")
            geoms.append(_run_resample(pcfg, repo, log, i, on_process=on_process))
    out["cad_outs"] = geoms
    # Back-compat: callers (and run_pipeline.py's summary) read "cad_out".
    out["cad_out"] = geoms[0] if geoms else ""

    # Immersed solid (optional): STL -> phi, before meshing, because the solver
    # stage links the phi field it produces.
    if pcfg.stl3d and run_ib and not pcfg.stl3d.get("skip"):
        log("=== Immersed solid: STL -> phi ===")
        try:
            out["phi"] = _run_stl3d(pcfg, repo, log, on_process=on_process)
        except stl3d_case.Stl3dError as e:
            # A malformed IB section is the user's mistake, not a crash: report it
            # in the pipeline's own vocabulary.
            raise PipelineError(f"immersed-solid stage: {e}") from e
    elif pcfg.stl3d:
        why = "--no-ib" if not run_ib else '"skip": true'
        log(f"[IB] immersed-solid stage skipped ({why}).")

    # Stage 2 — mesh.
    log("=== Stage 2/3: mesh generation ===")
    need_solver = run_solver and not pcfg.solver_skip()
    out["vtk"] = _run_mesh(pcfg, repo, geoms, need_starcd=need_solver, log=log,
                           on_process=on_process)

    # Stage 3 — solver.
    if need_solver:
        log("=== Stage 3/3: solver ===")
        out["result"] = _run_solver(pcfg, repo, out["vtk"], log,
                                    on_process=on_process, geoms=geoms,
                                    phi=out["phi"])
    else:
        log("=== solver stage skipped ===")
    return out
