"""Facts about the FILES in a solver case directory.

Two modules need the same answers and neither is the other's owner:

* ``services/case_export`` decides what a portable copy of a case contains, so
  it has to know what a run produced (to skip it and say so) and how big that
  is (to say how big);
* ``services/case_archive`` moves the previous run's outputs aside so a restart
  can continue in the same directory, so it has to know **exactly the same**
  set of files, plus where the archive goes.

Both lived in ``case_export`` when the archive was the only new reader, which
made the export the owner of a name the archiver creates and left the import
running in one awkward direction. They are facts about a case, not about an
export, so they live here and both sides import them as peers.

Qt-free, like the case services around it.
"""
from __future__ import annotations

import os
import re

from app.services.logging_setup import get_logger

# Files a run PRODUCES. Used to explain a skip in an export manifest and to pick
# what an archive moves — never to decide what an export COPIES, which is what
# the allow-lists are for.
_OUTPUT_PATTERNS = (
    re.compile(r"^xtecp"), re.compile(r"^tWall"), re.compile(r"^unicones\."),
    re.compile(r"^vsurface"), re.compile(r"^probe_data"),
    re.compile(r"^xxprocess"), re.compile(r"^mesh_tecplot"),
    re.compile(r"\.plt$"), re.compile(r"^fort\.\d+$"),
)

_RESTART_RE = re.compile(r"^binDump", re.IGNORECASE)

# Where ``case_archive`` puts a previous run's outputs: ``work/prev_001/``,
# ``prev_002/``, … One spelling, so the module that creates the directory and the
# one that has to account for it in a package cannot disagree about its name.
ARCHIVE_DIR_PREFIX = "prev_"

# Quoted values in input.in are ALL file paths (see SolverConfig.generate_input_in).
# Public: three modules read it — the export planner, "does this run use that
# file?" and the reference resolver below. It was copied into two of them before
# this module existed.
QUOTED_RE = re.compile(r'"([^"]*)"')


def is_restart_dump(name: str) -> bool:
    """The zone dump — an OUTPUT that a restart run happens to read back, which
    is why it is asked about separately everywhere it comes up."""
    return _RESTART_RE.match(name) is not None


def is_run_output(name: str) -> bool:
    """Whether ``name`` is a file a solver run PRODUCES, the zone dump
    included."""
    return (any(p.search(name) for p in _OUTPUT_PATTERNS)
            or is_restart_dump(name))


# What ``solver_case.prepare_case_dir`` stages INTO work/ under a FIXED name:
# input.in, the BC table, the phase field and a type-11 BC DLL. Two modules ask
# about it and neither owns it — ``case_archive`` must not archive them (they are
# the resumed run's own configuration) and ``solver_case`` must not stage a
# user-named table on top of one. It lived in ``case_archive`` and was restated
# as a shorter tuple in ``solver_case``; the two could already disagree, and did:
# the ``.so`` was in one and not the other.
WORK_STAGED = ({"input.in", "phi.dat"}, (".def", ".so"))


def keep_matches(name: str, keep) -> bool:
    """``name`` against a ``(exact_names, suffixes)`` allow-list."""
    exact, suffixes = keep
    return name in exact or name.endswith(suffixes)


def size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def tree_size(path: str) -> int:
    """Bytes under ``path``, recursively — a directory's own weight in a skip
    line, so "not shipped" comes with the number that makes it a decision."""
    total = 0
    for root, _dirs, files in os.walk(path):
        total += sum(size(os.path.join(root, f)) for f in files)
    return total


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def is_inside(child: str, parent: str) -> bool:
    """Whether ``child`` lives under ``parent`` (False across volumes, where
    commonpath refuses to answer rather than returning something misleading)."""
    try:
        return os.path.commonpath(
            [os.path.abspath(child), os.path.abspath(parent)]
        ) == os.path.abspath(parent)
    except ValueError:
        return False


def archive_subdirs(case_dir: str) -> tuple:
    """``("work/prev_001", …)`` — the archived previous runs, oldest name first."""
    work = os.path.join(case_dir, "work")
    try:
        names = sorted(os.listdir(work))
    except OSError:
        return ()
    return tuple(f"work/{n}" for n in names
                 if n.startswith(ARCHIVE_DIR_PREFIX)
                 and os.path.isdir(os.path.join(work, n)))


def referenced_inside(case_dir: str, input_in: str) -> set:
    """Case-relative paths of the files ``input.in``'s quoted values name, for
    the ones that resolve INSIDE the case.

    By BASENAME would be ambiguous the moment a case holds two files with the
    same name — which is exactly what an archived restart leaves behind
    (``work/binDumpZ.dat.gui`` from this run, ``work/prev_001/binDumpZ.dat.gui``
    from the one it resumed from), and treating both as "the dump input.in
    restarts from" doubles the largest file in a package. A reference pointing
    OUTSIDE the case is ``case_export._resolve_input_in``'s business (it stages a
    copy); here the question is only which of the case's own files a run reads.
    """
    work = os.path.join(case_dir, "work")
    out = set()
    for raw in QUOTED_RE.findall(input_in):
        ref = raw.strip()
        if not ref:
            continue
        resolved = os.path.normpath(
            ref if os.path.isabs(ref) else os.path.join(work, ref))
        if is_inside(resolved, case_dir):
            out.add(os.path.relpath(resolved, os.path.abspath(case_dir))
                    .replace(os.sep, "/"))
    return out


def staged_bare_names(work_dir: str) -> set:
    """Basenames the work dir's own ``input.in`` quotes as files sitting in it.

    The counterpart to :data:`WORK_STAGED` for what ``prepare_case_dir`` stages
    under a name the USER chose — the CFL schedule, the probe-point list and the
    MPI comm map (#29) — which no list can hold. ``input.in`` can, and it is the
    same authority :func:`referenced_inside` and ``case_export_usage`` read for
    "is this file an input of THIS run?".

    Bare names only, so an archived restart's ``prev_001/binDumpZ.dat.gui`` is
    not swept up. Callers that must not confuse a staged input with an output ask
    :func:`is_run_output` first; this function does not, because "quoted by
    input.in" and "produced by a run" are both true of a restart dump and the
    caller is the one that knows which answer it wants.
    """
    path = os.path.join(work_dir, "input.in")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except FileNotFoundError:
        # A work dir with no input.in yet is the normal case for a fresh run,
        # not a problem: nothing was staged, so the answer is genuinely empty.
        return set()
    except OSError:
        # An input.in that exists and cannot be READ is different, and the
        # failure is not inert — every user-named staged table would come back
        # unclassified, which is what the caller then says out loud about it.
        get_logger(__name__).warning(
            "could not read %s, so a file staged into this work dir under a "
            "user-chosen name cannot be recognised as an input", path,
            exc_info=True)
        return set()
    out = set()
    for raw in QUOTED_RE.findall(text):
        ref = raw.strip()
        if not ref or os.path.isabs(ref) or "/" in ref or os.sep in ref:
            continue
        if os.path.isfile(os.path.join(work_dir, ref)):
            out.add(ref)
    return out
