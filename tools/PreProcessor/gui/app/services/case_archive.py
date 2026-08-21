"""Move a previous run's outputs aside so a RESTART can continue in place.

A restart belongs in the case folder it is resuming — that is the point of one.
Reusing the directory used to mean the new run wrote over the previous run's
solution dumps and convergence history as it went, and the file it was resuming
FROM is one of those, so a crash part-way through a dump write could leave no
usable restart point at all. USER-REPORTED (2026-08-20, #26).

So the outputs move first, into ``work/prev_001/``, ``prev_002/``, … and the run
then writes clean files into ``work/``. It is a separate module from
``services/solver_case`` only because that one was at the GUI file-size budget;
the concept belongs beside :func:`~app.services.solver_case.prepare_case_dir`,
which is its only caller, and the restart reference that has to follow the file
it names is handled there (``restart_refs_for_work_dir(..., moved=)``).

Qt-free, like the rest of the case services.
"""
from __future__ import annotations

import os
import shutil

# "What does a solver run PRODUCE?", and where an archived one goes. Shared with
# ``services/case_export``, which skips-and-names exactly the files this module
# moves — see ``services/case_files``.
from app.services.case_files import (
    ARCHIVE_DIR_PREFIX,
    human_size,
    is_run_output,
    keep_matches,
)

# What ``solver_case.prepare_case_dir`` stages INTO work/: input.in, the BC
# table, the phase field and a type-11 BC DLL. They are the resumed run's own
# configuration and must survive the archive, or it restarts into nothing. Its
# own list rather than the export's ``_WORK_KEEP`` because the two answer
# different questions — that one is "does this ship in a package?", which has
# never had to include a staged ``.so``.
_WORK_STAGED = ({"input.in", "phi.dat"}, (".def", ".so"))


def _noop(_msg: str) -> None:
    pass


def next_archive_dir(work_dir: str, tagged=()) -> str:
    """The ``work/prev_<NNN>/`` this work dir would archive into next, or "" when
    999 of them already exist.

    Same never-clobber discipline as
    :func:`~app.services.solver_case.resolve_case_root`, and the same
    refusal to loop forever — but the fallback is the opposite one. There, giving
    up means overwriting the default dir, which costs the user a re-run; here it
    would mean moving a run's outputs on top of an earlier archive, which is the
    exact destruction the archive exists to prevent. So an exhausted counter
    archives NOTHING and says so.

    ``tagged`` are basenames that will be renamed ``<name>.prev_<NNN>`` and left
    in ``work/`` (see :func:`archive_previous_outputs`). One counter has to clear
    BOTH, or the directory could be free while the renamed file is not and the
    rename would clobber the very dump it is protecting.
    """
    for n in range(1, 1000):
        suffix = f"{ARCHIVE_DIR_PREFIX}{n:03d}"
        candidate = os.path.join(work_dir, suffix)
        if os.path.exists(candidate):
            continue
        if any(os.path.exists(os.path.join(work_dir, f"{t}.{suffix}"))
               for t in tagged):
            continue
        return candidate
    return ""


def next_archive_name(case_root: str) -> str:
    """The bare name (``"prev_003"``) the next archive of ``<case_root>/work``
    would take, or "" when the counter is exhausted.

    For the prompt, which promises the user a concrete directory. Given the CASE
    root rather than the work dir so a view never has to know that ``work/`` is
    where a run's files live, nor strip a basename off a path this module built.
    """
    return os.path.basename(
        next_archive_dir(os.path.join(case_root, "work")))


def archive_previous_outputs(work_dir: str, log=_noop, keep_bare=()) -> dict:
    """Put the previous run's OUTPUTS in ``work_dir`` beyond this run's reach.
    Returns ``{old_abspath: new_abspath}`` of everything that moved.

    This is what makes "continue in the same folder" a safe answer for a restart
    (#26, USER-REPORTED 2026-08-20). Reusing a case directory meant the new run
    wrote over the previous one's solution dumps and convergence history as it
    went — and the file it was RESUMING FROM is one of those. That is not a
    hypothetical: the solver's output dump is ``binDumpZ.dat`` + its ``-t`` tag,
    which is the SAME name a GUI restart resumes from, so **every** same-folder
    restart overwrote its own restart point in place (measured on the real
    binary: the source file's checksum changes).

    Most outputs go into a fresh ``work/prev_<NNN>/``. The zone dump named in
    ``keep_bare`` does NOT: it is renamed **in place** to ``<name>.prev_<NNN>``
    and stays directly in ``work/``, because the solver can only read a restart
    source by a bare name in its own cwd. Measured on the real binary, with the
    dump moved into the subdirectory and ``zdump_fn_restart`` pointing at
    ``prev_001/binDumpZ.dat.gui``, it derives a per-zone path from the reference
    — ``binDumpZ.dat.prev_001/binDumpZ.0`` — whose directory does not exist, and
    the run dies with ``Can't open file``. The rename satisfies both halves at
    once: bare, so the derivation never happens, and different from the output
    name, so the run cannot write over it (measured: ``Global Iteration count
    1000``, i.e. a real resume, with the source file unchanged).

    Four rules:

    * **An allow-list decides, not a glob.** Only what ``case_files`` classifies
      as produced-by-a-run is touched. The inputs ``prepare_case_dir`` stages
      (``_WORK_STAGED``) stay, or the resumed run loses its own configuration.
      Anything the two lists between them do not recognise **stays and is named
      in the log** — a file nobody classified is not a file to move blind.
    * **Move or rename, never copy.** The zone dump is the largest file in a
      case; copying it doubles the case on every resume and leaves two dumps
      whose relationship nothing records.
    * **Nothing is created when nothing moves.** An empty or output-free work dir
      (a fresh case, or an auto-versioned one) returns ``{}`` silently, which is
      what lets the caller pass ``archive_prev`` without first asking whether
      there is anything to archive.
    * **One counter clears both names** (see :func:`next_archive_dir`).

    The returned mapping is how the restart reference follows the file it
    names: see :func:`~app.services.solver_case.restart_refs_for_work_dir`.
    """
    if not os.path.isdir(work_dir):
        return {}
    bare = {os.path.abspath(p) for p in keep_bare}
    to_move, to_tag, unknown = [], [], []
    for name in sorted(os.listdir(work_dir)):
        src = os.path.join(work_dir, name)
        if not os.path.isfile(src):
            continue                       # earlier archives, and nothing else
        if is_run_output(name):
            (to_tag if os.path.abspath(src) in bare else to_move).append(name)
        elif not keep_matches(name, _WORK_STAGED):
            unknown.append(name)
    for name in unknown:
        log(f"[case] work/{name} is not a recognised solver input or output — "
            "left where it is, not archived.")
    if not to_move and not to_tag:
        return {}

    dest = next_archive_dir(work_dir, tagged=to_tag)
    if not dest:
        log("[WARNING] work/ already holds 999 archived runs; the previous "
            "outputs were left in place and THIS run will write over them.")
        return {}
    suffix = os.path.basename(dest)
    moved, total = {}, 0
    if to_move:
        os.makedirs(dest)
    for name in to_move:
        src = os.path.join(work_dir, name)
        total += os.path.getsize(src)
        shutil.move(src, os.path.join(dest, name))
        moved[os.path.abspath(src)] = os.path.abspath(os.path.join(dest, name))
    if to_move:
        log(f"[case] previous outputs -> work/{suffix}/ "
            f"({len(to_move)} file{'s' if len(to_move) != 1 else ''}, "
            f"{human_size(total)}); this run writes clean files into work/.")
    for name in to_tag:
        src = os.path.join(work_dir, name)
        dst = os.path.join(work_dir, f"{name}.{suffix}")
        shutil.move(src, dst)
        moved[os.path.abspath(src)] = os.path.abspath(dst)
        log(f"[case] the dump this run resumes from -> work/{name}.{suffix} "
            f"({human_size(os.path.getsize(dst))}); it stays in work/ rather "
            f"than in {suffix}/ because the solver reads a restart source only "
            f"by a bare name in its own directory, and it is renamed so this "
            f"run's own dump cannot land on top of it.")
    return moved
