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
  ``Global Iteration count`` to stdout, and by archive time that is gone). The
  solver writes one row every ``print_convg_per_niter`` iterations and none for
  the final one, so a run that reached 1000 with an interval of 10 leaves 990 in
  the file — and ``990 + 10`` recovers the count it printed, exactly.

**That last sentence is a REVERSAL, not a tweak** (#43). #30 recorded the
argument that naming 1000 would be a "fabrication", so the count was written down
and rendered as the bound ``990+``; #31 then adopted it as a deliberate departure
from its own specification, which had asked for a bare ``iteration 2000``. The
specification was right. The argument's own evidence contradicted it: the archive
gate's docstring stated the bound as ``[1990, 2000)`` — a half-open interval that
EXCLUDES the value it claimed to contain — and that sentence sat in a gate for two
issues. The interval is ``(1990, 2000]``, the point estimate is 2000, and it is
confirmed against both figures this repo already measured against the real solver
(990 -> 1000 for #26, 1990 -> 2000 for #30). The residual caveat is real but is an
UPPER bound — a run interrupted mid-interval got no further than the printed count
— and it belongs in a tooltip, not in a refusal to name the number.

:func:`iteration_span` is the one place that arithmetic lives. Both consumers ask
it — the restart chooser through ``services/restart_points`` and the playback leg
list through ``services/result_legs`` — so the two windows cannot disagree about
one archive, and neither computes a count of its own.

Written by the archiver and read back by whoever lists archives, so the format
is ``key: value`` lines plus a ``files:`` block rather than prose — a record
only a human can parse is a record the next feature re-derives.

Qt-free, like the rest of the case services.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime

from app.services.case_files import (
    QUOTED_RE,
    RUN_NOTE_NAME,
    human_size,
    is_restart_dump,
    size,
)
from app.services.logging_setup import get_logger

_log = get_logger(__name__)

# The solver's convergence history: iteration number in column 1, one row per
# ``print_convg_per_niter`` iterations.
_CONVG_RE = re.compile(r"^unicones\.enorm")

_HEADER = ("# HybMesh solver run archive — the run whose outputs this folder "
           "holds.")

#: How a run's time is written in a note, and read back off a file's mtime for a
#: leg that has not been archived yet. One spelling, so the two are comparable.
_STAMP_FMT = "%Y-%m-%d %H:%M:%S"

#: "we could not tell how far that run got" — never 0, which is a real answer the
#: solver prints for a cold start. Declared HERE, beside the reader that produces
#: it, and re-exported by ``restart_points`` (which used to declare its own copy);
#: one number means one thing in every module that reports an iteration count.
UNKNOWN_ITERATION = -1


def convergence_file(archive_dir: str) -> str:
    """The archived convergence history's basename, or ""."""
    try:
        names = sorted(os.listdir(archive_dir))
    except OSError:
        # The caller has just created and filled this directory, so a failure
        # here is a real surprise rather than an allowed step — but it only
        # costs the note one field, so it degrades rather than raising.
        _log.warning("could not list %s, so the archived run's convergence "
                     "history cannot be found", archive_dir, exc_info=True)
        return ""
    return next((n for n in names if _CONVG_RE.match(n)), "")


def _iteration_rows(path: str) -> tuple:
    """``(iteration numbers in file order, non-blank line count)``.

    The ONE parse of a convergence history: :func:`last_iteration` takes the last
    value, :func:`iteration_span` takes the first, the last and the spacing
    between the final two. A row whose first column is not a number (a header) is
    skipped but still counted, which is what ``convergence_rows`` has always
    reported.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            rows = [ln.split() for ln in f if ln.split()]
    except FileNotFoundError:
        # A run that produced no convergence history is a normal thing to meet
        # (it never reached the first print interval), and -1 says so.
        return (), 0
    except OSError:
        _log.warning("could not read %s, so the run's iteration count is "
                     "reported as unknown", path, exc_info=True)
        return (), 0
    out = []
    for row in rows:
        try:
            out.append(int(float(row[0])))
        except ValueError:
            continue
    return tuple(out), len(rows)


def last_iteration(path: str) -> tuple:
    """``(last_iteration, row_count)`` from a convergence history, ``(-1, 0)``
    when it cannot be read.

    The last row's first column — the LOW-LEVEL reader, kept as the row parser
    :func:`iteration_span` is built on rather than as an answer a consumer should
    quote: a bare last row is 990 where the run reached 1000. A blank or
    unreadable file gives -1 rather than 0, because 0 is a real answer the solver
    prints for a cold start and "we could not tell" must not be spelled the same
    way as "it had not started".
    """
    values, rows = _iteration_rows(path)
    return (values[-1] if values else UNKNOWN_ITERATION), rows


def convergence_interval(work_dir: str) -> int:
    """``print_convg_per_niter`` from the ``input.in`` the archived run used, or
    -1 when it cannot be read.

    It is what turns :func:`last_iteration` from a number that is quietly WRONG
    into the count the solver printed: the solver writes one row every N
    iterations and none for the final one, so a history ending at 1990 means the
    run reached 1990 + N (measured: 2000, N = 10). Without N a reader has no way
    to know how far the file's last row is from the truth, which is the complaint
    #30 makes about the folder in the first place.

    A FALLBACK only, and :func:`iteration_span` says why: this is what the run was
    CONFIGURED to print at, while the question being asked is about the interval
    in force when the last row was written. The file's own spacing answers that
    and a declaration made before a mid-run change may not.
    """
    try:
        with open(os.path.join(work_dir, "input.in"),
                  encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if parts[:1] == ["print_convg_per_niter"] and len(parts) > 1:
                    return int(parts[1])
    except (OSError, ValueError):
        # Already reported by resumed_from, which reads the same file for the
        # same archive; a second warning would say nothing new.
        return -1
    return -1


def resumed_from(work_dir: str):
    """What the run being archived itself restarted FROM, read out of the
    ``input.in`` it ran with: the quoted value, ``""`` for a cold start, or
    **None** when the file could not be read at all.

    That file is still the previous run's at archive time —
    ``prepare_case_dir`` writes the new one after archiving — so this is the
    last moment the answer exists. ``generate_input_in`` emits the key only
    under ``restart``, so its absence IS "cold start" rather than a guess, and
    a work dir with no ``input.in`` has never run one.

    None is a third state for :func:`last_iteration`'s reason, and it matters
    more here: "we could not tell" rendered as "cold start" would be a POSITIVE
    FALSE CLAIM in the one field #30 exists to provide, on a case whose history
    the reader cannot check any other way.
    """
    path = os.path.join(work_dir, "input.in")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except FileNotFoundError:
        return ""
    except OSError:
        _log.warning("could not read %s, so what the archived run resumed from "
                     "is reported as unknown rather than as a cold start",
                     path, exc_info=True)
        return None
    for line in text.splitlines():
        if line.split()[:1] == ["zdump_fn_restart"]:
            found = QUOTED_RE.findall(line)
            return found[0].strip() if found else ""
    return ""


def mtime_stamp(path: str) -> str:
    """``path``'s mtime in :func:`write_run_note`'s ``archived_at`` format, or "".

    Here because THIS module owns that format. Two callers need it for a leg that
    has not been archived and so has no note — ``restart_points`` for the live
    dump, ``result_legs`` for the live field output — and a reader comparing an
    archived row against a live one is then comparing one thing.
    """
    try:
        return datetime.fromtimestamp(os.path.getmtime(path)).strftime(
            _STAMP_FMT)
    except OSError:
        # The file was listed a moment ago, so this is a real surprise — but it
        # costs the row one field, so it degrades rather than raising.
        _log.warning("could not read the mtime of %s, so this run is listed "
                     "without a date", path, exc_info=True)
        return ""


def finished_stamp(archive_dir: str, note: dict | None = None) -> str:
    """When the run whose outputs this archive holds FINISHED, or "".

    NOT ``archived_at``, and the difference is a user-visible defect this
    replaces (USER-REPORTED 2026-08-27). An archive is made by the NEXT run, at
    the moment it starts — so ``archived_at`` answers "when was this folder
    made?" while a live leg's stamp answers "when did this run finish?". Both
    were rendered as a bare parenthesised timestamp in the same list, which is
    what invited the two to be compared: on this repo's own
    ``results/solver/case`` the chooser read

        Latest result   iteration 3000   (2026-08-27 09:35:11)
        prev_005        iteration 2000   (2026-08-27 09:35:01)

    — ten seconds apart, and a reader concludes they are one run. They are not:
    prev_005 finished at 09:32:31, and the ten seconds are merely how long the
    latest run took. Worse in the other direction, ``prev_003`` displayed
    ``2026-08-27 09:29:22`` for a run that finished on 2026-08-21 — six days
    out.

    The run's own outputs still carry the answer: ``shutil.move`` preserves
    mtime, and #30's hard link shares the inode, so an archived dump's mtime is
    still the moment the solver wrote it. Preferring the ZONE DUMP is what makes
    that "when the run finished" rather than "when some file in here changed" —
    it is written at the end of a run — with the convergence history next and
    any other output last. ``RUN.txt`` is excluded because it is written at
    ARCHIVE time and is the very fact being corrected.

    ``archived_at`` is the last resort rather than the first, and it is not
    discarded: it is a real fact about the folder, so the caller keeps it and
    shows it as its own labelled line.

    Here, beside :func:`mtime_stamp`, because THIS module owns the format and
    because both consumers ask it — ``restart_points`` for the chooser and
    ``result_legs`` for playback. They had the same defect independently
    (``stamp=note.get("archived_at", "")`` in each), which is what one owner
    prevents: two windows must not describe one folder differently.
    """
    best = ""
    try:
        names = sorted(os.listdir(archive_dir))
    except OSError:
        names = []

    def _rank(name: str) -> int:
        if is_restart_dump(name):
            return 0
        if _CONVG_RE.match(name):
            return 1
        return 2

    for name in sorted(names, key=_rank):
        if name == RUN_NOTE_NAME:
            continue
        path = os.path.join(archive_dir, name)
        if not os.path.isfile(path):
            continue
        best = mtime_stamp(path)
        if best:
            return best
    return (note or {}).get("archived_at", "") or ""


def note_int(note: dict, key: str, default: int = -1) -> int:
    """An integer field of a note, or ``default``.

    :func:`read_run_note` already coerces the numeric fields, but a note that is
    missing (a pre-#30 archive) or whose field did not parse leaves a non-int
    there — so every caller wrote the same ``isinstance`` guard beside the same
    ``.get``. One guard, in the module that decides what a note's fields mean.
    """
    val = note.get(key, default)
    return val if isinstance(val, int) else default


@dataclass(frozen=True)
class IterationSpan:
    """The stretch of a solve one leg covers: the half-open range ``(start, end]``.

    ``end`` is the count the solver PRINTED — ``last_row + interval``, not the
    last row itself; see the module docstring for why naming it is a reversal of
    #30/#31 rather than a tweak. ``start`` is where the leg took over
    (``first_row - interval``), i.e. 0 for a cold start and the resume point
    otherwise.

    **Half-open is load bearing.** Consecutive legs of a restart chain meet at a
    shared boundary iteration — leg 1 ends at 1000 and leg 2's first row is 1010,
    so leg 2 starts at 1000 — and a CLOSED range would report every ordinary
    restart as an overlap. Half-open gives the boundary to the earlier leg alone.
    """

    start: int = UNKNOWN_ITERATION
    end: int = UNKNOWN_ITERATION
    interval: int = UNKNOWN_ITERATION
    #: The convergence history's last row verbatim, i.e. ``end - interval``. Kept
    #: because a tooltip explaining where ``end`` came from has to be able to
    #: show it.
    last_row: int = UNKNOWN_ITERATION
    #: ``end`` came from a ``RUN.txt`` record rather than being recomputed from a
    #: convergence history. A reader is entitled to know which (#43, story 4).
    recorded: bool = False

    @property
    def known(self) -> bool:
        """Whether this leg reports how far its run got."""
        return self.end != UNKNOWN_ITERATION

    @property
    def measurable(self) -> bool:
        """Whether BOTH endpoints are known, i.e. this leg can be intersected."""
        return self.known and self.start != UNKNOWN_ITERATION

    def overlap(self, other: "IterationSpan") -> tuple:
        """The stretch this leg and ``other`` both cover, or ``()``.

        Intersection of two half-open ranges, which is what makes "these two legs
        re-ran the same segment" a measurement rather than a heuristic. Two legs
        that merely MEET (one ends where the next starts) share no interior and
        are correctly reported as disjoint.
        """
        if not (self.measurable and other.measurable):
            return ()
        lo, hi = max(self.start, other.start), min(self.end, other.end)
        return (lo, hi) if lo < hi else ()


def iteration_span(convg_path: str, *, note: dict | None = None,
                   declared_interval: int = UNKNOWN_ITERATION) -> IterationSpan:
    """How far the run that wrote ``convg_path`` got — the ONE answer (#43).

    Before this, an archived leg's count was read only from its ``RUN.txt`` while
    the LIVE leg computed its own from the convergence history beside it, using
    this module's own reader. So one module applied a computation to one leg and
    refused it for its siblings: on this repo's own twice-restarted case both
    archives report "iteration unknown" with every number needed sitting inside
    them. Both consumers now ask this instead, so the restart chooser and the
    Results leg list cannot disagree about one folder.

    **The convergence file is the primary evidence.** ``interval`` is the spacing
    the history itself EXHIBITS, measured on its final segment; ``note``'s
    recorded ``convergence_interval`` and then ``declared_interval`` (read from
    ``input.in``) are fallbacks used only when the file cannot supply one — a
    single-row history exhibits no spacing. The question ``end`` asks is "how far
    past the last row did the run get?", which is about the interval in force when
    that row was WRITTEN: the file shows that, and a declaration made before a
    mid-run change may no longer describe it.

    ``end`` prefers ``note``'s ``last_iteration`` when it has one — the record is
    the record — and falls back to the file's own last row, which is what gives a
    pre-#30 archive a count at all. ``start`` is ALWAYS read from the file, even
    for a noted archive: the note records a last row and no first row, so
    otherwise the best-documented archives would be the ones with an endpoint and
    no span, and interval intersection would be unavailable for exactly them. The
    file is inside the archive and cheap to read.

    Everything unknown when neither source yields an interval: a count with no
    interval cannot be corrected, and reporting the raw last row as if it were the
    answer is the defect this function exists to remove.
    """
    note = note or {}
    values, _rows = _iteration_rows(convg_path) if convg_path else ((), 0)
    measured = values[-1] - values[-2] if len(values) >= 2 else UNKNOWN_ITERATION
    interval = next((n for n in (measured,
                                 note_int(note, "convergence_interval"),
                                 declared_interval) if n > 0),
                    UNKNOWN_ITERATION)
    noted = note_int(note, "last_iteration")
    last = noted if noted >= 0 else (values[-1] if values else UNKNOWN_ITERATION)
    if last < 0 or interval <= 0:
        return IterationSpan(interval=interval, last_row=last,
                             recorded=noted >= 0)
    first = values[0] if values else UNKNOWN_ITERATION
    # `first >= interval`, not `first >= 0`: the solver's first row IS its first
    # print interval, so a leg that took over at k has first = k + interval and
    # start = k >= 0. A file starting earlier than that has no meaningful start,
    # and computing one would be a NEGATIVE start — which at exactly -1 collides
    # with UNKNOWN_ITERATION and reads as "not measurable" by accident rather
    # than by decision (found in review of #43).
    return IterationSpan(
        start=(first - interval) if first >= interval else UNKNOWN_ITERATION,
        end=last + interval, interval=interval, last_row=last,
        recorded=noted >= 0)


def write_run_note(archive_dir: str, suffix: str, *, tag: str = "",
                   came_from="", zone_dump: str = "", interval: int = -1,
                   now: datetime | None = None) -> str:
    """Write ``RUN.txt`` into ``archive_dir`` and return its path.

    Called after everything has moved, so the file list and the convergence
    history it reports are the archive as it actually is rather than as the
    caller intended it. ``zone_dump`` is the dump's archived name (``work/``
    holds a hard link to it, which is what keeps the archive complete without a
    second copy of the largest file in the case).
    """
    stamp = (now or datetime.now()).strftime(_STAMP_FMT)
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
        f"resumed_from: {_resumed_field(came_from)}",
        f"zone_dump: {zone_dump}",
        f"convergence_file: {convg}",
        f"last_iteration: {iters}",
        f"convergence_rows: {rows}",
        f"convergence_interval: {interval}",
        f"total_bytes: {total}",
        "",
        "# last_iteration is the last ROW of the convergence history, not the",
        "# solver's own final 'Global Iteration count' — that goes to stdout and",
        "# is gone by the time a run is archived. The solver writes one row every",
        "# convergence_interval iterations and none for the final one, so this run",
        "# reached last_iteration + convergence_interval: that SUM is the count",
        "# the solver printed (measured against the real binary: 990 -> 1000 and",
        "# 1990 -> 2000), and it is the number to quote. A run interrupted",
        "# mid-interval got no further, so the sum is an upper bound.",
        "# -1 in either field means it could not be determined, which is NOT the",
        "# same as 0 (a real answer, printed for a cold start).",
        "",
        f"files: {len(names)}",
    ]
    lines += [f"  {n:<46} {human_size(size(os.path.join(archive_dir, n))):>9}"
              for n in names]
    path = os.path.join(archive_dir, RUN_NOTE_NAME)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _resumed_field(came_from) -> str:
    """``resumed_from``'s three states as three distinct strings — see
    :func:`resumed_from`. None must not collapse onto "cold start"."""
    if came_from is None:
        return "unknown (the previous input.in could not be read)"
    return came_from or "cold start"


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
    except FileNotFoundError:
        # An archive written before #30 has no note. Normal, not a failure.
        return {}
    except OSError:
        _log.warning("could not read %s, so this archive reads as one with no "
                     "record even though it has one", path, exc_info=True)
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
    for key in ("last_iteration", "convergence_rows", "convergence_interval",
                "total_bytes"):
        try:
            out[key] = int(out[key])
        except (KeyError, ValueError):
            pass
    out["files"] = files
    return out
