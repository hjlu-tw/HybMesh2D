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

# The archive's own record of the run it holds, written by ``case_run_note``.
# Beside ARCHIVE_DIR_PREFIX for that constant's reason: ``case_export`` has to
# know the name so it does not report it as "not recognised as a solver input",
# and the module that WRITES it must not become the owner of a name the export
# reads — that is exactly the one-way import this file was created to undo.
RUN_NOTE_NAME = "RUN.txt"

# The ``-t`` tag every solver output carries, one per HOST: ``.gui`` for a run
# driven by the GUI, ``.cli`` for the headless pipeline. Declared here because
# THREE modules need the same two strings and each used to spell them itself —
# ``solver_ctrl`` and ``pipeline_runner`` PRODUCE them, the restart autofill
# looks for them, and :func:`archive_name` below has to strip one. A rename rule
# that strips a tag nobody writes silently does nothing, which is the failure
# mode a second spelling has here.
GUI_RUN_TAG = ".gui"
CLI_RUN_TAG = ".cli"
RUN_TAGS = (GUI_RUN_TAG, CLI_RUN_TAG)

# ``…prev_001`` at the END of a file name: an archived file says which run it
# belongs to (#30). Built from ARCHIVE_DIR_PREFIX so the directory's name and the
# file suffix inside it cannot drift apart.
_ARCHIVE_SUFFIX_RE = re.compile(
    r"\.(" + re.escape(ARCHIVE_DIR_PREFIX) + r"\d{3})$")


def run_tag(name: str) -> str:
    """The run tag ``name`` ends in (``".gui"``), or "" — the one piece of
    information :func:`archive_name` discards, which is why ``RUN.txt`` records
    it (see ``services/case_run_note``)."""
    for tag in RUN_TAGS:
        if name.endswith(tag):
            return tag
    return ""


def strip_run_tag(name: str) -> str:
    """``name`` without its trailing run tag, if it has one.

    The counterpart of :func:`run_tag`, in one place because two callers strip
    the same slot: :func:`archive_name` replaces it with the archive suffix, and
    ``services/result_legs`` normalises a result file's name to the stem its
    other legs carry it under (``xtecp_sol_allz.dat.gui`` and
    ``xtecp_sol_allz.dat.prev_001`` are the same output of two runs).
    """
    tag = run_tag(name)
    return name[:-len(tag)] if tag else name


def archive_suffix(name: str) -> str:
    """The ``"prev_001"`` an already-archived name carries, or ""."""
    m = _ARCHIVE_SUFFIX_RE.search(name)
    return m.group(1) if m else ""


def strip_archive_suffix(name: str) -> str:
    """``name`` without its trailing ``.prev_<NNN>``, if it has one.

    Its own function so the dot is counted in ONE place: the suffix travels as a
    bare ``"prev_001"`` (it is also a directory name), so every reader that
    stripped it by hand had to remember the separator too.
    """
    suffix = archive_suffix(name)
    return name[:-(len(suffix) + 1)] if suffix else name


def archive_name(name: str, suffix: str) -> str:
    """What ``name`` is called once it belongs to the archive ``suffix``.

    ONE naming scheme: every archived file ends in ``.prev_<NNN>`` (#30). #26
    left two — the zone dump was renamed with the archive's tag while everything
    moved into the folder kept its run tag verbatim, so one archive read as two.
    A trailing run tag is REPLACED (``unicones.enorm.gui`` ->
    ``unicones.enorm.prev_001``) because it is the same slot saying the same kind
    of thing; a name with no tag is appended to (``fort.11`` ->
    ``fort.11.prev_001``).

    A name that already carries an archive suffix is returned UNCHANGED: it
    already says which run it belongs to, and re-tagging it would move that
    claim onto a run it did not come from.
    """
    if archive_suffix(name):
        return name
    return strip_run_tag(name) + "." + suffix


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
    r"""Whether ``name`` is a file a solver run PRODUCES, the zone dump
    included — and an ARCHIVED one still is.

    The archive suffix is stripped before the patterns are applied, because two
    of them anchor on the END of the name (``\.plt$``, ``^fort\.\d+$``) and #30's
    rename moves that end. Without this an archived ``fort.11.prev_001`` reads as
    "not a recognised solver input or output" — a false statement about a file
    this toolchain named itself, and the same class of wrong skip line
    ``case_archive`` already refuses to print. Widening the patterns instead
    would loosen them for every future name; seeing through a suffix this repo
    creates does not.
    """
    base = strip_archive_suffix(name)
    return (any(p.search(base) for p in _OUTPUT_PATTERNS)
            or is_restart_dump(base))


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
