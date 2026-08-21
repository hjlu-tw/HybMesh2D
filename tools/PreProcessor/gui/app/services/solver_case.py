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
from app.services.case_archive import archive_previous_outputs
from app.services.case_sources import stage_case_sources
from app.services.paths import repo_root

# The three answers to "this case name already has results". One value rather
# than a pair of booleans, because the GUI asks ONE question and the two
# mechanical facts ``prepare_case_dir`` takes are derived from the answer by
# :func:`case_dir_flags` — so a caller cannot get half of the mapping right.
CASE_NEW_VERSION = "version"    # leave them; run in <case>_002
CASE_ARCHIVE = "archive"        # same dir; move the previous outputs aside first
CASE_IN_PLACE = "in_place"      # same dir; write over them


def _noop(_msg: str) -> None:
    pass


def sanitize_case_name(name: str, default: str = "case") -> str:
    """Make a filesystem-safe, whitespace-free token (case / phi field / STL3d
    para.in name). Collapses any run of unsafe chars to '_' (dots/dashes kept for
    ``*.stl``). ``default`` is returned when the sanitized result is empty.

    Single source of truth for the ``[^A-Za-z0-9_.-]+`` sanitizer; callers that
    need a different empty-name fallback pass ``default`` (e.g. "phi", "x")."""
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", (name or "").strip())
    return s or default


def dir_has_content(path: str) -> bool:
    """True when ``path`` exists and is a non-empty directory.

    Public because ``solver_ctrl`` asks it before deciding whether the case-dir
    question needs asking at all."""
    return os.path.isdir(path) and bool(os.listdir(path))


def resolve_case_root(root: str, case: str, overwrite: bool, log=_noop) -> str:
    """Pick the ``results/solver/<case>`` directory to write into.

    When the default case dir already holds prior results and ``overwrite`` is
    False, auto-version to ``<case>_002``, ``<case>_003``, … so a re-run never
    silently clobbers earlier output. Returns the actual directory path (not yet
    created). ``overwrite=True`` reuses the default dir in place.
    """
    default = os.path.join(root, "results", "solver", case)
    if overwrite or not dir_has_content(default):
        return default
    for n in range(2, 1000):
        candidate = os.path.join(root, "results", "solver", f"{case}_{n:03d}")
        if not dir_has_content(candidate):
            log(f"[case] '{case}' already has results; writing to "
                f"'{os.path.basename(candidate)}' to preserve them "
                "(pass overwrite=True to reuse the existing dir).")
            return candidate
    # Pathological: 998 versions exist. Fall back to overwriting the default
    # rather than looping forever.
    log(f"[WARNING] too many versions of case '{case}'; overwriting "
        f"'{case}'.")
    return default


def case_dir_flags(disposition: str) -> tuple[bool, bool]:
    """``(overwrite, archive_prev)`` for one of the ``CASE_*`` answers above.

    The user is asked one question — which directory this run writes into and
    what happens to what is already there — and ``prepare_case_dir`` takes two
    independent mechanical facts. Mapping them in one place is what stops a
    caller passing ``archive_prev`` without ``overwrite`` (an archive of a
    directory the run is not going to use) or, worse, the reverse.
    """
    if disposition not in (CASE_NEW_VERSION, CASE_ARCHIVE, CASE_IN_PLACE):
        # A typo must not resolve to a plausible answer. ``(False, False)`` is a
        # real disposition — auto-version — so a misspelling would silently run
        # somewhere the user did not choose. The same defect the pipeline-stage
        # gate records for ``plan()`` ignoring an unknown key.
        raise ValueError(f"unknown case disposition {disposition!r}")
    return (disposition in (CASE_ARCHIVE, CASE_IN_PLACE),
            disposition == CASE_ARCHIVE)


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


def report_stale_ibm_artifacts(cfg: SolverConfig, work_dir: str,
                               log=_noop) -> None:
    """Name a ``work/phi.dat`` this run did not stage, so it cannot pass for one.

    A case directory is reused in place (``overwrite=True``), and ``phi.dat`` is
    only ever WRITTEN here by :func:`stage_phi_file`. So an existing one after a
    run that staged nothing is the previous run's field, and it is invisible: no
    log line mentions it and it sits next to this run's real inputs. Two ways
    that matters, one harmless and one not:

    * immersed solid OFF — nothing reads it (the export lists it as unused), but
      it still looks like an input to whoever browses the case.
    * immersed solid ON with no phi field chosen — the init DLL reads ``phi.dat``
      by that fixed name, so the run silently uses the OLD geometry's solid and
      converges to a believable answer for the wrong shape.

    Reporting only; nothing is deleted, because a phi field is expensive to
    regenerate and the user may well mean to reuse it.
    """
    phi = os.path.join(work_dir, "phi.dat")
    if not os.path.exists(phi):
        return
    if cfg.immersed_solid and not cfg.ibm_phi_file:
        log("[WARNING] immersed solid is ON but no phi field was given: the run "
            "will use the work/phi.dat already in this case directory (from an "
            "earlier run). Check it matches this geometry.")
    elif not cfg.immersed_solid:
        log("[IBM] work/phi.dat is left over from an earlier immersed-solid run "
            "in this case directory; this run does not read it (and Export Case "
            "leaves it out).")


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


def _resolve_ref(raw: str, work_dir: str) -> str:
    """The absolute file a quoted restart value names, resolving a relative one
    against the work dir the solver runs in.

    One spelling, because it is asked TWICE about the same value and the two
    answers have to be the same file: :func:`prepare_case_dir` builds the archive's
    ``keep_bare`` from it, and :func:`_work_dir_ref` looks the result up in the
    archive's move map. If those two ever disagreed, the dump would be archived
    under one identity and looked up under another — the reference would fall
    through to the pass-through branch and strand the restart, which is the exact
    failure #26 exists to prevent.
    """
    return os.path.abspath(
        raw if os.path.isabs(raw) else os.path.join(work_dir, raw))


def _work_dir_ref(raw: str, work_dir: str, what: str, log=_noop,
                  moved: dict | None = None) -> str:
    """``raw`` as ``input.in`` should quote it: relative to ``work_dir``.

    Rewritten only when ``raw`` is an ABSOLUTE path to an existing file — inside
    ``work_dir`` it becomes its bare basename, elsewhere a relative path out and
    back (``../../<case>/work/<name>``). A blank, an already-relative or a
    non-resolving value is returned unchanged: relative is by definition relative
    to the work dir the solver runs in, and a path that is simply wrong must
    surface as the solver's own error rather than be rewritten into something
    that merely looks valid.

    ``moved`` is :func:`~app.services.case_archive.archive_previous_outputs`'
    mapping, consulted BEFORE the existence check for the reason the check
    exists: the file this reference names has just been moved, so at its old path
    it is gone, and "does not resolve" would send the run's own restart point
    through the pass-through branch and into the solver as a path to nothing. It
    is the one thing that also rewrites a RELATIVE value — a bare
    ``binDumpZ.dat.gui`` (hand-written, or loaded from a ``.hws`` / pipeline
    script) names nothing once the file is in ``prev_001/``, and the autofilled
    absolute path is not the only way that field gets filled in.
    """
    raw = (raw or "").strip()
    if not raw:
        return raw
    resolved = _resolve_ref(raw, work_dir)
    archived = bool(moved) and resolved in moved
    if not archived and not os.path.isabs(raw):
        # Rule 3 stands: an already-relative value is relative to the work dir
        # the solver runs in, so it is passed through untouched. The ONE
        # exception is a file this run just moved — a hand-written or scripted
        # ``binDumpZ.dat.gui`` names nothing once it is in prev_001/, and the
        # archive must not strand the restart it exists to protect.
        return raw
    if archived:
        resolved = moved[resolved]
    if not os.path.isfile(resolved):
        return raw
    rel = os.path.relpath(resolved,
                          os.path.abspath(work_dir)).replace(os.sep, "/")
    log(f"[restart] {what} -> {rel}"
        + (" (moved with the previous run's outputs; the resumed run reads it "
           "there)" if archived else
           " (relative to the work dir the solver runs in)"))
    return rel


def restart_refs_for_work_dir(cfg: SolverConfig, work_dir: str, log=_noop,
                              moved: dict | None = None) -> tuple[str, str]:
    """``(zdump_rel, convg_rel)``: the two restart references as ``input.in``
    should quote them, i.e. relative to the work dir the solver runs in.

    The paths ``input.in`` quotes are made work-dir relative by
    :func:`prepare_case_dir` — the grid/bc as ``../grid/<case>.*``, the
    init-condition and motion DLLs as ``../dll/*.so`` (:func:`stage_dll`), a BC
    type-11 DLL as ``./x.so``, the phi field staged into ``work/`` under a fixed
    name. The two restart fields were the only ones nothing touched, so they
    reached the solver as an absolute path on the machine that wrote them and the
    run errored out (USER-REPORTED 2026-08-20, #25). The shipped reference case
    quotes them the same way (``solver/case/Cyl_IBM_Rotate/work/input.in``), and
    ``case_export`` already relativises exactly these references when it packages
    a case — so an exported case ran while the case it was exported from did not.

    Not every quoted path is covered even now, and it is worth being exact rather
    than tidy about it: ``mpi_comm_map_fn``, ``cfl_schedule_fn`` and
    ``probe_points_def_fn`` are still emitted verbatim, so a browsed-to absolute
    path reaches the solver in the same shape #25 was about. They are out of
    scope here — nothing has reported them, and each needs its own answer about
    whether the file should be STAGED into the case rather than referenced out of
    it (which is what ``case_export`` already does for them). Tracked as **#29**;
    they are the residue, not an oversight.

    Relative-path rules are :func:`_work_dir_ref`'s. The dump itself is never
    copied: it is the largest file in a case — which is why ``case_export``
    treats it specially — and a reference costs nothing. That the reference may
    need to point OUT of the case is the real case rather than a hypothetical
    one: the panel computes the dump's path from the case NAME, before
    :func:`resolve_case_root` may auto-version the directory, so a run landing in
    ``<case>_002/`` genuinely restarts from ``<case>/work/`` and a hard-coded
    basename would point at nothing.

    Returned rather than written back onto ``cfg``, which is the one place this
    departs from the staging around it. ``prepare_case_dir`` mutates ``cfg``
    freely because it can RE-derive what it overwrites (``output_grid_file`` is
    rebuilt from ``case_name`` every run), and it cannot re-derive this: the
    absolute path is the only form that still means the same thing from another
    work dir, so overwriting it would put a work-dir-relative value into the
    model the ``.hws`` and the pipeline script are saved from — where the next
    run, landing in an auto-versioned directory, would resolve it to nothing. The
    panel keeps its absolute path for the same reason it is filled in that way:
    it is browsable, and it is the same absolute-in-the-GUI /
    relative-in-``input.in`` split ``grid_rel``/``bc_rel`` already have.

    The two fields are named here rather than walked by string, so renaming one
    is a NameError instead of a rewrite that silently stops happening.

    ``moved`` carries :func:`archive_previous_outputs`' result, so a reference to
    a dump that was archived a moment ago follows it into ``prev_NNN/`` instead
    of resolving to nothing. That is the other half of #26: continuing in the
    same folder is only safe if the run can still find what it is resuming from.
    """
    return (_work_dir_ref(cfg.zdump_fn_restart, work_dir, "zdump_fn_restart",
                          log, moved),
            _work_dir_ref(cfg.convg_fn_restart, work_dir, "convg_fn_restart",
                          log, moved))


def prepare_case_dir(cfg: SolverConfig, log=_noop, overwrite: bool = False,
                     sources=(), generated_sources=(),
                     archive_prev: bool = False):
    """Build ``results/solver/<name>/{work,grid,dll}``, stage getPGrid inputs,
    rename outputs, write ``input.in`` / ``.def``, and compile IBM DLLs.

    ``sources`` are the CAD/STL files the case was built from and
    ``generated_sources`` the ``(name, text)`` it can only reconstruct (the mesh
    parameter file, which the GUI writes to a temp path it then deletes). Both
    land in ``grid/cad/`` (see ``services/case_sources``) so the case carries the
    geometry and the settings it describes, not only the mesh cut from them.

    Mutates ``cfg`` in place (paths are rewritten to the staged locations, as the
    solver worker expects). Returns ``(work_dir, grid_dir, input_in_path)``.

    By default (``overwrite=False``) an existing, non-empty case dir is NOT
    clobbered: the case auto-versions to ``<case>_002`` etc. (see
    :func:`resolve_case_root`) so prior results are preserved. Pass
    ``overwrite=True`` to reuse the existing dir in place.

    ``archive_prev`` moves the previous run's outputs into ``work/prev_<NNN>/``
    before this run writes anything, which is what makes reusing the directory
    safe for a restart (#26). The two flags are independent rather than one
    tri-state because the second is well defined without the first: an
    auto-versioned run archives nothing because its work dir holds nothing. The
    GUI never spells the pair out — see :func:`case_dir_flags`.
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

    # Before anything is written here: put the previous run's outputs out of
    # reach, so "continue in the same folder" cannot mean "write over the run
    # you are resuming from". Empty when there is nothing to archive.
    #
    # The zone dump this run RESUMES FROM is named so the archive can keep it
    # reachable: the solver reads a restart source only by a bare name in its own
    # cwd, so that one file is renamed in place instead of moved into prev_NNN/
    # (see archive_previous_outputs). A dump living in some OTHER case dir is not
    # in work_dir, so it is simply not among the files the archive considers.
    keep_bare = ()
    if archive_prev and cfg.restart:
        raw = (cfg.zdump_fn_restart or "").strip()
        if raw:
            keep_bare = (_resolve_ref(raw, work_dir),)
    archived = (archive_previous_outputs(work_dir, log, keep_bare=keep_bare)
                if archive_prev else {})

    # getPGrid runs in grid_dir: stage the STAR-CD inputs there with the
    # basenames para.in will reference, and have it write <case>.grid/.bc there.
    #
    # ``actual_case``, NOT ``case``: auto-versioning renames the DIRECTORY, and
    # a stem left on the pre-version name puts case.grid inside case_002/. That
    # runs (input.in names the file it wrote), so it is invisible until the user
    # later types the versioned name by hand — then the same directory holds
    # case.grid AND case_002.grid, two 1.3 MB grids distinguishable only by which
    # one input.in happens to reference. USER-REPORTED (2026-08-13).
    stem = actual_case
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

    # The geometry this grid was cut from, and the settings that cut it.
    stage_case_sources(sources, grid_dir, log, generated=generated_sources)

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
    # A phi field this run did not stage belongs to an earlier one: say so rather
    # than leave it sitting among the inputs (see report_stale_ibm_artifacts).
    report_stale_ibm_artifacts(cfg, work_dir, log)

    # Solver boundary-condition table. The solver reads "<bc>.def" from its cwd;
    # by default it uses getPGrid's own companion verbatim (copied by the runner).
    # Only when the user fills the BC table do we write an override here. BC
    # type-11 user DLLs are compiled into the work dir + rewritten to "./x.so"
    # BEFORE the table is written so the .def references a loadable binary (#7).
    if cfg.bc_definitions:
        stage_bc_dll_paths(cfg, work_dir, log)
        def_name = os.path.basename(cfg.output_bc_file) + ".def"
        cfg.generate_bc_def(os.path.join(work_dir, def_name))

    # input.in with paths relative to the work dir -- now including the two
    # restart references, which this function used to leave as the absolute path
    # the panel put in them (#25).
    zdump_rel, convg_rel = restart_refs_for_work_dir(cfg, work_dir, log,
                                                     moved=archived)
    input_in_path = os.path.join(work_dir, "input.in")
    cfg.generate_input_in(
        input_in_path,
        grid_rel=f"../grid/{stem}.grid",
        bc_rel=f"../grid/{stem}.bc",
        zdump_rel=zdump_rel,
        convg_rel=convg_rel)

    return work_dir, grid_dir, input_in_path
