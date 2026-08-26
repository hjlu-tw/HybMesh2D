"""A restarted solve's result is SEVERAL files, ordered into one animation.

#32, USER-REQUESTED (2026-08-21), blocked by #30 because it reads the ``RUN.txt``
#30 writes. A restarted solve is **one physical run split across several files**:
``work/xtecp_sol_allz.dat.gui`` plus one per archive (``work/prev_001/``,
``prev_002/``, …), because #26 moves a finished run's outputs aside so the next
one can continue in the same directory. The Results tab could only ever play one
of them, so watching a restarted solve evolve meant opening each leg by hand and
losing the animation at every boundary.

This module answers the FACTS — which files are the legs of the case a given
result belongs to, and in what order they should be played. Whether to open them
together is the view's question (it asks), and how to serve frames across them is
``models/result_series``'s.

Four rules the shape follows from:

* **A leg is found by its STEM, not by a fixed name.** #30 renames every archived
  file to ``.prev_<NNN>``, so the same solver output is ``xtecp_sol_allz.dat.gui``
  in ``work/`` and ``xtecp_sol_allz.dat.prev_001`` in an archive. Stripping the
  archive suffix and then the run tag (``case_files.strip_archive_suffix`` +
  ``strip_run_tag``, i.e. exactly what ``archive_name`` replaced) recovers the one
  name both carry. Matching a literal ``xtecp_sol_allz.dat.*`` would tie playback
  to one solver's output name.

* **Order by ITERATION COUNT; lineage says who resumed from whom, which is a
  different question.** The issue asks to "order by ``RUN.txt``'s recorded
  lineage". Lineage IS recoverable — ``resumed_from`` is a basename, and
  ``case_archive.bare_link_for_archived_dump`` links an archived dump into
  ``work/`` under its ARCHIVED name, so a reference reading
  ``binDumpZ.dat.prev_001`` names that leg exactly (an earlier version of this
  module claimed the opposite and was simply wrong). What lineage gives is a
  PREDECESSOR relation, not a position: it says where a leg started, never how
  far it went, and two legs resumed from the same point are indistinguishable by
  it — which is precisely the re-run the issue is worried about. So
  ``last_iteration`` orders the legs and lineage is what DETECTS the overlap
  (below), each used for the question it can answer.

* **A leg with no count is played WHERE IT RAN, not last.** The issue says a
  legacy archive is "offered last, unlabelled, rather than excluded", and that is
  right for a chooser LIST — last means least prominent. This is a playback
  ORDER, an axis with physical meaning, and the difference is not academic:
  measured on this repo's own restarted case (``results/solver/case``, whose two
  archives predate #30 and so carry no note), "last" put the NEWEST leg first and
  the two oldest after it — the solve played backwards. Creation order is a
  total, always-available fact (``prev_001`` ran before ``prev_002`` ran before
  ``work/``) and it agrees with iteration order in every case except a leg
  re-run from an earlier point — which is exactly the case where the note exists
  and its count decides. So an unknown leg inherits the position its creation
  order gives it: it sorts with the last count recorded BEFORE it, and stays put.

* **An overlap is REPORTED, never interleaved.** Re-running a leg from an earlier
  point is easy after #31, and then a later run covers ground an earlier one
  already did. Two independent signals, because they catch different cases:
  **lineage** — two legs whose ``resumed_from`` names the same start really did
  re-run the same segment, and this holds even when neither reports a count — and
  **non-monotonicity** — a leg that ran later reporting a count no higher than
  one that ran earlier, which catches a pair whose notes are missing or whose
  start was never recorded. Both name both legs. The legs are still concatenated
  in count order; nothing is dropped, merged or spliced.

* **A path outside a case is one leg and no history.** The Results view opens any
  Tecplot file, including one that was never a solver case's own output. That is
  a single-leg :class:`LegSeries` with :data:`~app.services.restart_points.OTHER`
  as its kind, so every caller builds a series the same way and "is there
  anything to offer?" is one length test rather than a None branch.

Qt-free, like the rest of the case services.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from app.services.case_files import (
    ARCHIVE_DIR_PREFIX,
    RUN_NOTE_NAME,
    archive_subdirs,
    archive_suffix,
    newest_first,
    run_tag,
    strip_archive_suffix,
    strip_run_tag,
)
from app.services.case_run_note import (
    convergence_interval,
    last_iteration,
    mtime_stamp,
    note_int,
    read_run_note,
)
from app.services.logging_setup import get_logger
from app.services.restart_points import (
    ARCHIVE,
    LATEST,
    OTHER,
    UNKNOWN_ITERATION,
    convg_beside,
    work_dir_of,
)

_log = get_logger(__name__)

#: The directory a case's live (un-archived) run works in.
_WORK = "work"

__all__ = ["LegSeries", "ResultLeg", "UNKNOWN_ITERATION", "leg_stem",
           "list_result_legs"]


@dataclass(frozen=True)
class ResultLeg:
    """One leg of a restarted solve: the result file one run produced.

    ``order`` is the order the runs HAPPENED in (0 = the oldest archive, the live
    ``work/`` leg last), which is what makes an overlap detectable — it is the one
    fact the directory layout records that iteration counts cannot contradict.
    """
    kind: str                               #: LATEST / ARCHIVE / OTHER
    key: str                                #: "latest" / "prev_002" / ""
    path: str                               #: ABSOLUTE path to the result file
    order: int = 0
    iteration: int = UNKNOWN_ITERATION
    interval: int = UNKNOWN_ITERATION
    stamp: str = ""                         #: RUN.txt's archived_at, or the mtime
    tag: str = ""                           #: ".gui" / ".cli", when known
    has_note: bool = False                  #: this leg carries a RUN.txt
    #: RUN.txt's ``resumed_from`` verbatim — a basename, "" for a cold start, or
    #: "" again when unknown. Only :func:`_overlaps` reads it, and only to ask
    #: whether two legs started from the SAME place; see the module docstring for
    #: why it cannot order them.
    resumed_from: str = ""

    @property
    def known(self) -> bool:
        """Whether this leg reports how far its run got."""
        return self.iteration != UNKNOWN_ITERATION


@dataclass(frozen=True)
class LegSeries:
    """The legs of one solve in PLAYBACK order, plus what to say about them.

    Warnings travel as data rather than being logged here, for
    ``classifyJunctions``' reason: the ordering is testable without a log sink,
    and the caller owns the user-facing channel.
    """
    legs: tuple = ()
    warnings: tuple = ()

    def __len__(self) -> int:
        return len(self.legs)

    @property
    def paths(self) -> tuple:
        return tuple(leg.path for leg in self.legs)

    @property
    def labels(self) -> tuple:
        return tuple(leg.key for leg in self.legs)

    def index_of(self, path: str) -> int:
        """Which leg ``path`` is, or -1 — so a caller can say "and this is the
        one you asked for" without re-deriving the match."""
        want = os.path.abspath(path)
        for i, leg in enumerate(self.legs):
            if os.path.abspath(leg.path) == want:
                return i
        return -1


def leg_stem(name: str) -> str:
    """The name a solver output carries in EVERY leg.

    ``xtecp_sol_allz.dat.gui`` (live) and ``xtecp_sol_allz.dat.prev_001``
    (archived) are the same output of two runs; both reduce to
    ``xtecp_sol_allz.dat``. The archive suffix comes off first because #30's
    rename REPLACES the run tag with it, so a name never carries both.
    """
    return strip_run_tag(strip_archive_suffix(os.path.basename(name)))


def list_result_legs(result_path: str) -> LegSeries:
    """The legs of the solve ``result_path`` belongs to, oldest solution first.

    Always at least one leg — the file itself — so a caller never has to branch
    on "is this a case result at all?"; ``len(...) > 1`` is the question worth
    asking.
    """
    path = os.path.abspath(result_path)
    case_root = _case_root_of(path)
    if not case_root:
        return LegSeries(legs=(ResultLeg(kind=OTHER, key="", path=path),))
    stem = leg_stem(path)
    legs = _archive_legs(case_root, stem)
    live = _live_leg(work_dir_of(case_root), stem,
                     prefer=path, order=len(legs))
    if live is not None:
        legs.append(live)
    if not legs:
        # The file is inside a case work dir but nothing there matches its stem —
        # only reachable if it vanished between the caller's open and this listing.
        return LegSeries(legs=(ResultLeg(kind=OTHER, key="", path=path),))
    ordered = _ordered(legs)
    return LegSeries(legs=tuple(ordered), warnings=tuple(_warnings(legs)))


# ── ordering ──────────────────────────────────────────────────────────────
def _ordered(legs: list) -> list:
    """``legs`` (in creation order) sorted for playback.

    Known iteration counts ascending, creation order breaking a tie. A leg with
    no count of its own takes the last count recorded BEFORE it, so it lands
    between the legs that ran either side of it rather than at the end — see the
    module docstring for the case that measured the difference. A leg with no
    count and no counted predecessor sorts first, which is the same rule: nothing
    ran before it.
    """
    keyed, floor = [], float("-inf")
    for leg in legs:
        if leg.known:
            floor = leg.iteration
        keyed.append(((floor, leg.order), leg))
    keyed.sort(key=lambda pair: pair[0])
    return [leg for _key, leg in keyed]


def _warnings(legs: list) -> list:
    """What to tell the user about this ordering — empty when it is a clean chain.

    Three things are worth saying and none is an error: two legs that started
    from the same place re-ran the same segment, a leg that ran later and got no
    further than one that ran earlier covers ground twice, and a leg with no
    ``RUN.txt`` is being placed by the order it RAN in rather than by a number it
    reports.
    """
    out = []
    seen = set()
    for a, b, why in _overlaps(legs):
        if (a.key, b.key) in seen:
            continue
        seen.add((a.key, b.key))
        out.append(
            f"[Results] '{b.key}' and '{a.key}' cover the same part of the "
            f"solve ({why}). They are played in iteration order, not merged — "
            "expect that stretch to repeat.")
    missing = [leg.key for leg in legs if not leg.known]
    if missing:
        out.append(
            f"[Results] {', '.join(missing)} carries no {RUN_NOTE_NAME} record "
            "of how far it got (an archive written before that record existed), "
            "so it is played in the order it RAN rather than left out.")
    return out


def _overlaps(legs: list):
    """``(earlier, later, reason)`` for each pair of legs covering one stretch.

    The lineage signal first because it is the direct evidence: two legs whose
    ``resumed_from`` names the same start really did re-run the same segment, and
    that holds even when neither reports an iteration count. Non-monotonicity is
    the fallback for the pairs lineage cannot see — a leg whose note is missing
    records no start at all — and it needs both counts, which is why neither
    signal makes the other redundant.

    A blank ``resumed_from`` is NOT matched against another blank: it means "cold
    start" for a leg whose note says so and "we have no note" for one that has
    none, and treating those as the same start would report an overlap between
    two legs about which nothing is known.
    """
    for i, leg in enumerate(legs):
        for earlier in legs[:i]:
            if earlier.resumed_from and earlier.resumed_from == leg.resumed_from:
                yield earlier, leg, (
                    f"both resumed from {leg.resumed_from}")
            elif (earlier.known and leg.known
                    and earlier.iteration >= leg.iteration):
                yield earlier, leg, (
                    f"'{leg.key}' ran later but records iteration "
                    f"{leg.iteration} against {earlier.iteration}")


# ── finding the legs ──────────────────────────────────────────────────────
def _case_root_of(path: str) -> str:
    """The case directory ``path`` is a result of, or "".

    A leg lives either directly in ``<case>/work/`` or in one of that dir's
    ``prev_<NNN>/`` archives, so the answer is read off the two directory names
    above the file rather than guessed from the file's own name.
    """
    parent = os.path.dirname(path)
    name = os.path.basename(parent)
    if name == _WORK:
        return os.path.dirname(parent)
    if name.startswith(ARCHIVE_DIR_PREFIX):
        grand = os.path.dirname(parent)
        if os.path.basename(grand) == _WORK:
            return os.path.dirname(grand)
    return ""


def _result_in(directory: str, stem: str, prefer: str = "") -> str:
    """The basename of ``stem``'s result file in ``directory``, or "".

    ``prefer`` wins when it is in this directory: the file the user actually
    opened decides which host's leg is being played, since a case run by both the
    GUI and the headless pipeline holds ``…dat.gui`` and ``…dat.cli`` side by side
    and they are two different solves. Failing that, newest wins with
    ``case_files.newest_first`` decides, which is the same rule ``_dump_in``
    applies to dumps and now the same code.
    """
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return ""
    cands = [n for n in names
             if leg_stem(n) == stem
             and os.path.isfile(os.path.join(directory, n))]
    if not cands:
        return ""
    if prefer:
        want = os.path.basename(prefer)
        if (os.path.dirname(os.path.abspath(prefer))
                == os.path.abspath(directory) and want in cands):
            return want
    return newest_first(directory, cands)[0]


def _archive_legs(case_root: str, stem: str) -> list:
    """One leg per ``work/prev_<NNN>/`` that holds this stem, oldest first.

    Every field comes from that archive's own ``RUN.txt`` (#30) — the record, not
    a re-derivation. An archive whose note is missing or unreadable still gets a
    leg, with :data:`UNKNOWN_ITERATION`, for ``restart_points``' reason: hiding a
    part of the solve that exists is worse than playing it without a number.
    """
    out = []
    for rel in archive_subdirs(case_root):
        d = os.path.join(case_root, *rel.split("/"))
        name = _result_in(d, stem)
        if not name:
            continue                      # this leg dumped no field output
        note = read_run_note(d)
        out.append(ResultLeg(
            kind=ARCHIVE, key=os.path.basename(d),
            path=os.path.abspath(os.path.join(d, name)),
            order=len(out),
            iteration=note_int(note, "last_iteration", UNKNOWN_ITERATION),
            interval=note_int(note, "convergence_interval", UNKNOWN_ITERATION),
            stamp=note.get("archived_at", ""),
            tag=note.get("run_tag", ""),
            has_note=bool(note),
            resumed_from=_started_at(note)))
    return out


def _live_leg(work: str, stem: str, prefer: str, order: int):
    """The un-archived leg in ``work/`` as a leg, or None.

    It has no ``RUN.txt`` — nothing has archived it yet — so its iteration count
    comes from the convergence history beside it, which is the same file and the
    same computation ``case_run_note.write_run_note`` will perform on it when it
    IS archived. ``restart_points._latest_point`` does this for the dump; this
    does it for the field output, through the same
    :func:`~app.services.restart_points.convg_beside`.
    """
    name = _result_in(work, stem, prefer=prefer)
    if not name:
        return None
    path = os.path.abspath(os.path.join(work, name))
    convg = convg_beside(work, name)
    return ResultLeg(
        kind=LATEST, key=LATEST, path=path, order=order,
        iteration=last_iteration(convg)[0] if convg else UNKNOWN_ITERATION,
        interval=convergence_interval(work),
        stamp=mtime_stamp(path),
        tag=run_tag(name))


def _started_at(note: dict) -> str:
    """Where the run this note describes STARTED, as a comparable key, or "".

    ``resumed_from`` is a basename, and an archived dump is linked into ``work/``
    under its archived name (``case_archive.bare_link_for_archived_dump``), so a
    reference carrying a ``.prev_<NNN>`` suffix names one leg exactly. A bare
    live-dump name (``binDumpZ.dat.gui``) names whatever was live at the time,
    which is not a leg identity — two legs quoting it did NOT necessarily start
    in the same place — so it is deliberately not a key. The prose forms
    ``write_run_note`` emits for the other two states are not keys either: "cold
    start" is a real shared start but the note for a leg with no record spells
    its unknown differently, and conflating them would report an overlap between
    two legs about which nothing is known.
    """
    raw = (note.get("resumed_from") or "").strip()
    return raw if archive_suffix(raw) else ""
