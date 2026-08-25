"""``RUN.txt`` — what an archived run says about itself.

``services/case_archive`` moves a finished run's outputs into
``work/prev_<NNN>/`` so a restart can continue in the same case dir (#26). A
folder of files is not a record of a run, though: it says nothing about WHEN
that leg ran, what it resumed from, or the one number anybody reasons about
when picking a restart point — how far it got. #30 asks for that, and it is
what makes a restart chooser or a playback list over the archives possible
without opening a 300 MB binary dump.

Two facts have to be recovered rather than remembered, because nothing records
them and the run itself is over:

* **the run tag** (``.gui`` / ``.cli``) is read off the file names BEFORE
  :func:`~app.services.case_files.archive_name` replaces it — that rename is
  what makes one archive uniformly named, and the tag is the information it
  discards;
* **how far the run got** comes from the LAST ROW of its own convergence
  history, which is the only evidence left in the case (the solver prints
  ``Global Iteration count`` to stdout, and by archive time that is gone). It is
  recorded as ``last_iteration`` and labelled as the last *recorded* one on
  purpose: the solver writes a row every ``print_convg_per_niter`` iterations,
  so a run that reached 1000 with an interval of 10 leaves 990 in the file.
  Reporting that as the final count would be a small lie in the one field a user
  reads.

Written by the archiver and read back by whoever lists archives, so the format
is ``key: value`` lines plus a ``files:`` block rather than prose — a record
only a human can parse is a record the next feature re-derives.

Qt-free, like the rest of the case services.
"""
from __future__ import annotations

import os
import re
from datetime import datetime

from app.services.case_files import QUOTED_RE, human_size, size

RUN_NOTE_NAME = "RUN.txt"

# The solver's convergence history: iteration number in column 1, one row per
# ``print_convg_per_niter`` iterations.
_CONVG_RE = re.compile(r"^unicones\.enorm")

_HEADER = ("# HybMesh solver run archive — the run whose outputs this folder "
           "holds.")


def convergence_file(archive_dir: str) -> str:
    """The archived convergence history's basename, or ""."""
    try:
        names = sorted(os.listdir(archive_dir))
    except OSError:
        return ""
    return next((n for n in names if _CONVG_RE.match(n)), "")


def last_iteration(path: str) -> tuple:
    """``(last_iteration, row_count)`` from a convergence history, ``(-1, 0)``
    when it cannot be read.

    The last row's first column. A blank or unreadable file gives -1 rather than
    0, because 0 is a real answer the solver prints for a cold start and "we
    could not tell" must not be spelled the same way as "it had not started".
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            rows = [ln.split() for ln in f if ln.split()]
    except OSError:
        return -1, 0
    for row in reversed(rows):
        try:
            return int(float(row[0])), len(rows)
        except ValueError:
            continue
    return -1, len(rows)


def resumed_from(work_dir: str) -> str:
    """What the run being archived itself restarted FROM, read out of the
    ``input.in`` it ran with, or "" for a cold start.

    That file is still the previous run's at archive time —
    ``prepare_case_dir`` writes the new one after archiving — so this is the
    last moment the answer exists. ``generate_input_in`` emits the key only
    under ``restart``, so its absence IS "cold start" rather than a guess.
    """
    try:
        with open(os.path.join(work_dir, "input.in"),
                  encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.split()[:1] == ["zdump_fn_restart"]:
                    found = QUOTED_RE.findall(line)
                    return found[0].strip() if found else ""
    except (OSError, IndexError):
        return ""
    return ""


def write_run_note(archive_dir: str, suffix: str, *, tag: str = "",
                   came_from: str = "", zone_dump: str = "",
                   now: datetime | None = None) -> str:
    """Write ``RUN.txt`` into ``archive_dir`` and return its path.

    Called after everything has moved, so the file list and the convergence
    history it reports are the archive as it actually is rather than as the
    caller intended it. ``zone_dump`` is the dump's archived name (``work/``
    holds a hard link to it, which is what keeps the archive complete without a
    second copy of the largest file in the case).
    """
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    convg = convergence_file(archive_dir)
    iters, rows = (last_iteration(os.path.join(archive_dir, convg))
                   if convg else (-1, 0))
    names = sorted(n for n in os.listdir(archive_dir)
                   if n != RUN_NOTE_NAME
                   and os.path.isfile(os.path.join(archive_dir, n)))
    total = sum(size(os.path.join(archive_dir, n)) for n in names)
    lines = [
        _HEADER,
        f"archive: {suffix}",
        f"archived_at: {stamp}",
        f"run_tag: {tag}",
        f"resumed_from: {came_from or 'cold start'}",
        f"zone_dump: {zone_dump}",
        f"convergence_file: {convg}",
        f"last_iteration: {iters}",
        f"convergence_rows: {rows}",
        f"total_bytes: {total}",
        "",
        "# The last row of the convergence history, not the solver's own final",
        "# 'Global Iteration count': it writes one row every",
        "# print_convg_per_niter iterations, so the run reached at least this.",
        "",
        f"files: {len(names)}",
    ]
    lines += [f"  {n:<46} {human_size(size(os.path.join(archive_dir, n))):>9}"
              for n in names]
    path = os.path.join(archive_dir, RUN_NOTE_NAME)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def read_run_note(archive_dir: str) -> dict:
    """``RUN.txt``'s fields back as a dict (``files`` a list of basenames), or
    ``{}`` when the archive predates it / cannot be read.

    The counterpart of the writer rather than a second parser of the same
    prose: a caller listing archives asks this, and the round trip is what the
    gate pins.
    """
    path = os.path.join(archive_dir, RUN_NOTE_NAME)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return {}
    out, files, in_files = {}, [], False
    for raw in text.splitlines():
        if raw.startswith("#") or not raw.strip():
            continue
        if raw.startswith("  "):
            if in_files:
                files.append(raw.split()[0])
            continue
        key, _, val = raw.partition(":")
        in_files = key == "files"
        out[key.strip()] = val.strip()
    for key in ("last_iteration", "convergence_rows", "total_bytes"):
        try:
            out[key] = int(out[key])
        except (KeyError, ValueError):
            pass
    out["files"] = files
    return out
