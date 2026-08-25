"""The paths ``work/input.in`` QUOTES, as the solver's own work dir should see
them.

``SolverConfig.generate_input_in`` quotes nine values and every one is a file
path. It is a writer — it emits what it is handed — so something has to decide
what each of those nine strings should say from inside the directory the solver
actually runs in, given a panel that fills them with browsable absolute paths.
That decision is this module; :func:`~app.services.solver_case.prepare_case_dir`
is the only caller, and hands the results straight to the writer beside
``grid_rel`` / ``bc_rel``.

There are two answers, and the difference is SIZE rather than taste:

* the two RESTART references are **relativised, never copied**
  (:func:`restart_refs_for_work_dir`) — the zone dump is the largest file in a
  case, which is why ``case_export`` treats it specially, and a copy would leave
  two dumps whose relationship nothing records (#25, #26);
* the three TABLES — a CFL schedule, a probe-point list, an MPI comm map — are
  **copied into the work dir and quoted by bare name**
  (:func:`table_refs_for_work_dir`), because they are small and a case that does
  not hold its own inputs is the problem (#29).

Split out of ``services/solver_case`` when that file passed the GUI size budget,
the same way ``services/case_archive`` was — but this is a concept and not only a
file: "what should input.in say here?" is one question with nine instances, and
it was being answered halfway down a function about making directories.

Qt-free, like the rest of the case services.
"""
from __future__ import annotations

import os
import shutil

from app.models.solver_config import SolverConfig
from app.services.case_files import WORK_STAGED, is_run_output, keep_matches


def _noop(_msg: str) -> None:
    pass


def resolve_ref(raw: str, work_dir: str) -> str:
    """The absolute file a quoted restart value names, resolving a relative one
    against the work dir the solver runs in.

    One spelling, because it is asked TWICE about the same value and the two
    answers have to be the same file: ``solver_case.prepare_case_dir`` builds the
    archive's ``keep_bare`` from it, and :func:`_work_dir_ref` looks the result up in the
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
    resolved = resolve_ref(raw, work_dir)
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


def _occupied(work_dir: str, base: str) -> bool:
    """Whether staging a table as ``base`` would write over a file the work dir
    already means something by — ``input.in``, the phase field, the BC ``.def``,
    a type-11 BC ``.so``.

    ``WORK_STAGED`` comes from ``case_files`` rather than being restated here,
    which is the point: the first spelling was a three-name tuple built at the
    call site and it had already drifted from the archive's copy — a type-11 BC
    ``.so`` is copied into the work dir by :func:`stage_bc_dll_paths` before any
    table is staged, and was in one list and not the other.

    It asks whether the file EXISTS, and that is load bearing twice. It is more
    precise — only ``<case>.bc.def`` is at risk, not every ``.def`` a user might
    name a probe list — and it is what makes the caller's counter TERMINATE: a
    numbered name eventually names nothing, whereas a rule on the name alone
    cannot be escaped by numbering at all (``bcuser.so`` -> ``bcuser_2.so`` is
    still a ``.so``). A table left by an earlier run is deliberately not
    occupied: overwriting its own staged copy is what makes a re-run idempotent.

    ``input.in`` is the exception, and existence is exactly why it needs one: it
    is the only file here that :func:`prepare_case_dir` writes AFTER the tables
    are staged, so on a fresh case dir it does not exist yet and the staged copy
    would be silently written over a moment later. (``work/<bc>.def`` has a
    narrower version of this — the runner's :func:`stage_bc_def_companion` copies
    it in later still — but only on a first run whose user named a table exactly
    ``<case>.bc.def``, so it is named here rather than machined around.)
    """
    return (base == "input.in"
            or (keep_matches(base, WORK_STAGED)
                and os.path.exists(os.path.join(work_dir, base))))


def _stage_table(raw: str, work_dir: str, what: str, taken: set,
                 log=_noop) -> str:
    """``raw`` as ``input.in`` should quote it, copying the file it names into
    ``work_dir`` when it is a PATH.

    Three of the nine quoted values are small tables the case ought to hold
    rather than reach out of this machine for — a CFL schedule, a probe-point
    list, an MPI comm map — so the answer here is the opposite of the restart
    dump's (#25), and for a stated reason: the dump is the largest file in a
    case, which is why it is referenced and never copied, while a table costs
    nothing to carry and a case that does not hold its own inputs is the
    problem. Staging is also what ``case_export`` already does to exactly these
    three, so the exported case was self-contained while the case it came from
    referenced this machine's filesystem.

    Three shapes, and only one of them copies anything:

    * a **bare name** is returned unchanged (and reserves itself in ``taken``) —
      it is already relative to the work dir, which is the solver's cwd, and is
      the intended form for ``cfl_schedule_fn`` (whose tip says "schedule table
      filename");
    * a **path to an existing file** (absolute, or relative with a separator and
      resolving from the work dir) is copied in under a collision-safe basename
      and quoted by that bare name;
    * anything that does **not** resolve is returned unchanged, so it surfaces as
      the solver's own error rather than being rewritten into something that
      merely looks valid (#25's rule 4).

    Copy, never move and never hard-link: one table may feed several cases, the
    user's own copy must not be taken away, and one inode would let a later edit
    silently rewrite what the case holds (``case_sources``' rule, same reason).

    ``taken`` collects the basenames this pass has claimed, so two tables with
    the same basename from different directories both travel. A name left by an
    EARLIER run is deliberately not in it, or re-running a case would walk
    ``probe.dat`` -> ``probe_2.dat`` -> ``probe_3.dat`` instead of overwriting
    its own staged copy, exactly as the grid and phi staging above overwrite
    theirs. Two further refusals are separate rules, for separate reasons — see
    :func:`_occupied` and the run-output branch below.
    """
    raw = (raw or "").strip()
    if not raw:
        return raw
    if os.sep not in raw and "/" not in raw:
        # A bare name is returned untouched — but it still CLAIMS that basename,
        # or a later field holding an absolute path to a different file with the
        # same basename would be copied on top of the name this one quotes and
        # both references would resolve to one table. It claims it even when
        # nothing is there yet: the whole point of a bare name is that the user
        # manages that file themselves, so the work dir not holding it at
        # staging time says nothing about the run.
        taken.add(raw)
        return raw
    src = raw if os.path.isabs(raw) else os.path.join(work_dir, raw)
    if not os.path.isfile(src):
        return raw
    stem, ext = os.path.splitext(os.path.basename(src))
    if is_run_output(stem + ext):
        # A name this toolchain reads as a file a RUN PRODUCES gets the other
        # answer, because numbering cannot escape it — the rules are anchored
        # (``^binDump``, ``\.plt$``), so every candidate is still an output. A
        # copy under such a name would be archived aside by the next restart
        # (#26) or reported as a skipped output by the export, i.e. quietly
        # detached from the run that needs it. Left as written, and said out
        # loud: rule 4's principle, that a value which cannot be made portable
        # must surface rather than be rewritten into something plausible.
        log(f"[WARNING] {what} names '{stem}{ext}', which this toolchain reads "
            f"as a file a solver run produces; it is referenced as written "
            f"rather than copied into the work dir. Rename it if the case "
            f"should carry it.")
        return raw
    base = stem + ext
    n = 2
    while base in taken or _occupied(work_dir, base):
        base = f"{stem}_{n}{ext}"
        n += 1
    taken.add(base)
    dst = os.path.join(work_dir, base)
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copy2(src, dst)
        log(f"[case] {what} -> {base} (copied into the work dir the solver "
            f"runs in)")
    return base


def table_refs_for_work_dir(cfg: SolverConfig, work_dir: str,
                            log=_noop) -> tuple[str, str, str]:
    """``(comm_map_rel, cfl_rel, probe_rel)``: the three remaining quoted paths
    as ``input.in`` should quote them, with the files they name staged into the
    work dir.

    Found in review of #25 (#29), not from a user report: of the nine values
    ``SolverConfig.generate_input_in`` quotes — and every quoted value in
    ``input.in`` is a file path — six were resolved before the file was written
    (grid, bc, the two restart references, the init-condition DLL, the motion
    DLL) and these three were emitted with ``.strip()`` and nothing else. Two of
    them are ``"path"`` field specs with a file dialog behind them, so the GUI
    routinely puts an absolute path on this machine into them, in the same shape
    #25 was about.

    Per-value rules are :func:`_stage_table`'s. Returned rather than written back
    onto ``cfg``, for the reason the restart references are: ``cfg`` is the model
    the ``.hws`` and the pipeline script are saved from, so a work-dir-relative
    value stored there resolves to nothing from the next, auto-versioned work
    dir — and the panel keeps its browsable absolute path, the same
    absolute-in-the-GUI / relative-in-``input.in`` split every other path field
    has. (This is the opposite of :func:`stage_dll`, which does write back; the
    difference is whether the value can be re-derived next run.)

    The three fields are named here rather than walked by string, so renaming one
    is a NameError instead of a staging step that silently stops happening.

    A table never lands on a file the work dir already means (``input.in``, the
    phi field, the BC ``.def``, a staged BC ``.so``: :func:`_occupied`), and a
    table NAMED like a run output is referenced rather than copied, because that
    name cannot be made safe by renumbering.
    """
    taken = set()
    return (_stage_table(cfg.mpi_comm_map_fn, work_dir, "mpi_comm_map_fn",
                         taken, log),
            _stage_table(cfg.cfl_schedule_fn, work_dir, "cfl_schedule_fn",
                         taken, log),
            _stage_table(cfg.probe_points_def_fn, work_dir,
                         "probe_points_def_fn", taken, log))


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

    All nine quoted paths are handled now — but "handled" is the word, not
    "relative": both this function and :func:`table_refs_for_work_dir` pass a
    value that does not RESOLVE through untouched, on purpose. The last three —
    ``mpi_comm_map_fn``, ``cfl_schedule_fn`` and ``probe_points_def_fn`` — were
    residue this docstring named until #29, and they got the OPPOSITE answer:
    the file is copied into the work dir and quoted by bare name, because a table
    is small and a case that does not hold its own inputs is the problem, while
    the dump below is the largest file in a case. #29 exists because the first
    write-up of #25 claimed "every quoted path is work-dir relative" and it was
    false in three files at once; do not restate it here in a wider form than
    the code supports.

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
