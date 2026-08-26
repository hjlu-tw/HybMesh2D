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

Seven rules the shape follows from:

* **A leg is found by its STEM, not by a fixed name.** #30 renames every archived
  file to ``.prev_<NNN>``, so the same solver output is ``xtecp_sol_allz.dat.gui``
  in ``work/`` and ``xtecp_sol_allz.dat.prev_001`` in an archive. Stripping the
  archive suffix and then the run tag (``case_files.strip_archive_suffix`` +
  ``strip_run_tag``, i.e. exactly what ``archive_name`` replaced) recovers the one
  name both carry. Matching a literal ``xtecp_sol_allz.dat.*`` would tie playback
  to one solver's output name.

* **How far a leg got is not computed here.** Every leg's span comes from
  ``case_run_note.iteration_span``, the one owner of that arithmetic (#43), which
  prefers an archive's ``RUN.txt`` and falls back to the convergence history the
  archive holds. The first version of this module read the note ONLY, so an
  archive written before #30 played with no count at all while the live leg —
  eight lines further down — computed its own from exactly that kind of file. On
  this repo's own restarted case that was every archive it has.

* **Order by the corrected iteration count; lineage says who resumed from whom,
  which is a different question.** The issue asks to "order by ``RUN.txt``'s
  recorded lineage". Lineage IS recoverable — ``resumed_from`` is a basename, and
  ``case_archive.bare_link_for_archived_dump`` links an archived dump into
  ``work/`` under its ARCHIVED name, so a reference reading
  ``binDumpZ.dat.prev_001`` names that leg exactly (an earlier version of this
  module claimed the opposite and was simply wrong). What lineage gives is a
  PREDECESSOR relation, not a position: it says where a leg started, never how
  far it went, and two legs resumed from the same point are indistinguishable by
  it — which is precisely the re-run the issue is worried about. So the span's
  ``end`` orders the legs, and it is the CORRECTED end rather than the raw last
  row: two legs printing at different intervals sort correctly only after the
  correction.

* **A leg that still cannot be measured is played WHERE IT RAN — the THIRD
  fallback, not the first.** The issue says a legacy archive is "offered last,
  unlabelled, rather than excluded", and that is right for a chooser LIST, where
  last means least prominent. This is a playback ORDER, an axis with physical
  meaning, and the difference is not academic: measured on this repo's own
  restarted case, "last" put the NEWEST leg first and the two oldest after it —
  the solve played backwards. So an unmeasurable leg inherits the position its
  creation order gives it (``prev_001`` ran before ``prev_002`` ran before
  ``work/``): it sorts with the last count recorded BEFORE it and stays put.
  It was the FIRST line of defence when the note was the only source; now that a
  convergence history answers too, it is what is left after both have failed.

* **An overlap is a MEASUREMENT, and it is reported, never interleaved.**
  Re-running a leg from an earlier point is easy after #31, and then a later run
  covers ground an earlier one already did. Because a leg now reports a SPAN
  rather than an endpoint, the test is interval intersection over the half-open
  ranges ``(start, end]`` — precise, and it says WHICH iterations repeat.
  Lineage stays as the fallback for a pair whose spans cannot both be computed:
  two legs whose ``resumed_from`` names the same start really did re-run one
  segment, and that holds when neither reports a count.

  **Non-monotonicity is GONE** (#43). "A leg that ran later reporting no higher a
  count" false-positives on a later leg covering an earlier, DISJOINT range — a
  genuinely separate re-run — and wherever both spans are measurable, intersection
  answers the same question correctly. It was the right heuristic while a start
  iteration was unavailable; it is strictly dominated now that one is not.
  Nothing is dropped, merged or spliced either way: both legs are named.

* **The legs are the legs of ONE run.** A case run by both hosts holds
  ``…dat.gui`` and ``…dat.cli`` side by side, and those are two different solves
  — the live-directory lookup has always said so and picked the file the user
  opened. Archived legs get the same rule: the anchor is the run tag of the file
  that was opened (from its name where it has one, otherwise from its own
  ``RUN.txt``, since #30's rename replaces the tag with the archive suffix), and
  a leg whose tag differs is excluded and NAMED. A leg whose tag cannot be
  determined is included rather than dropped — an unreadable record must not
  hide part of a solve.

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
    IterationSpan,
    convergence_file,
    convergence_interval,
    iteration_span,
    mtime_stamp,
    read_run_note,
)
from app.services.logging_setup import get_logger
from app.services.restart_points import (
    ARCHIVE,
    LATEST,
    OTHER,
    convg_beside,
    work_dir_of,
)

_log = get_logger(__name__)

#: The directory a case's live (un-archived) run works in.
_WORK = "work"

# ``UNKNOWN_ITERATION`` used to be re-exported from here as well. It is
# ``case_run_note``'s and nothing imported this copy once a leg carried a whole
# ``IterationSpan``; a hop through two modules is two places for one number to
# stop meaning one thing.
__all__ = ["LegSeries", "ResultLeg", "leg_stem", "list_result_legs"]


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
    #: How far this leg's run got, from ``case_run_note.iteration_span``. A SPAN
    #: rather than an endpoint, which is what makes an overlap an intersection
    #: instead of a heuristic (#43).
    span: IterationSpan = IterationSpan()
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
        return self.span.known


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
    anchor = _anchor_tag(path)
    legs = _archive_legs(case_root, stem)
    live = _live_leg(work_dir_of(case_root), stem,
                     prefer=path, order=len(legs), tag=anchor)
    if live is not None:
        legs.append(live)
    legs, foreign = _same_run(legs, anchor)
    if not legs:
        # The file is inside a case work dir but nothing there matches its stem —
        # only reachable if it vanished between the caller's open and this listing.
        return LegSeries(legs=(ResultLeg(kind=OTHER, key="", path=path),))
    return LegSeries(legs=tuple(_ordered(legs)),
                     warnings=tuple(_warnings(legs, foreign, anchor)))


def _anchor_tag(path: str) -> str:
    """Which RUN the user opened, as a run tag, or "" when it cannot be told.

    From the file's own name where it carries one (a live leg is
    ``…dat.gui``), otherwise from the ``RUN.txt`` beside it — #30's rename
    replaces the tag with the archive suffix, so an archived leg's NAME cannot
    say which host produced it and only its own note can.

    "" is a real third state and nothing is filtered on it: an unreadable record
    must not hide part of a solve (#43, story 27).
    """
    tag = run_tag(os.path.basename(path))
    if tag:
        return tag
    return read_run_note(os.path.dirname(path)).get("run_tag", "")


def _same_run(legs: list, anchor: str) -> tuple:
    """``(the legs of the anchor's run, the legs of another)``.

    A case run by both hosts holds two solves in one directory tree, and splicing
    them into one animation would show a discontinuity as physics. The live
    lookup has always applied this (it plays the file the user OPENED); this
    extends it to the archives, which is where the tag lives in a note rather
    than in the name.
    """
    if not anchor:
        return legs, []
    keep = [leg for leg in legs if leg.tag in ("", anchor)]
    return keep, [leg for leg in legs if leg.tag not in ("", anchor)]


# ── ordering ──────────────────────────────────────────────────────────────
def _ordered(legs: list) -> list:
    """``legs`` (in creation order) sorted for playback.

    By the CORRECTED end of each leg's span, ascending, creation order breaking a
    tie — corrected because two legs printing at different intervals sort
    correctly only after the raw last rows have been turned into the counts the
    solver reported. A leg whose span cannot be computed at all takes the last
    count recorded BEFORE it, so it lands between the legs that ran either side of
    it rather than at the end; see the module docstring for the case that measured
    the difference, and for why that rule is now the third fallback rather than
    the first. A leg with no span and no measured predecessor sorts first, which
    is the same rule: nothing ran before it.
    """
    keyed, floor = [], float("-inf")
    for leg in legs:
        if leg.known:
            floor = leg.span.end
        keyed.append(((floor, leg.order), leg))
    keyed.sort(key=lambda pair: pair[0])
    return [leg for _key, leg in keyed]


def _warnings(legs: list, foreign: list = (), anchor: str = "") -> list:
    """What to tell the user about this series — empty when it is a clean chain.

    Three things are worth saying and none is an error: two legs cover the same
    iterations, so a stretch of the animation repeats; a leg belongs to the other
    host's run in this directory and is not being played; and a leg cannot be
    measured at all, so it is placed by the order it RAN in.
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
    if foreign:
        out.append(
            f"[Results] not playing {', '.join(leg.key for leg in foreign)}: "
            f"produced by a {'/'.join(sorted({leg.tag.lstrip('.') for leg in foreign}))} "
            f"run, while you opened a {anchor.lstrip('.')} one. This case was run "
            "by both hosts, and those are two different solves — open one of "
            "those files to play that run instead.")
    missing = [leg.key for leg in legs if not leg.known]
    if missing:
        out.append(
            f"[Results] {', '.join(missing)} carries neither a {RUN_NOTE_NAME} "
            "record of how far it got nor a readable convergence history, so it "
            "is played in the order it RAN rather than left out.")
    return out


def _overlaps(legs: list):
    """``(earlier, later, reason)`` for each pair of legs covering one stretch.

    **Interval intersection is the measurement.** A leg reports the half-open
    range ``(start, end]`` it covers, so two legs re-running one segment share an
    interior and the report can name the iterations that repeat. Half-open is
    what keeps an ordinary restart chain quiet: consecutive legs MEET at a
    boundary iteration and share no interior.

    Lineage is the fallback for a pair whose spans cannot BOTH be measured: two
    legs whose ``resumed_from`` names the same start really did re-run one
    segment, and that holds when neither reports a count. A blank
    ``resumed_from`` is not matched against another blank — it means "cold start"
    for a leg whose note says so and "we have no note" for one that has none, and
    conflating them would report an overlap between two legs about which nothing
    is known.

    Non-monotonicity ("ran later, got no further") is deliberately gone; see the
    module docstring.
    """
    for i, leg in enumerate(legs):
        for earlier in legs[:i]:
            shared = earlier.span.overlap(leg.span)
            if shared:
                yield earlier, leg, (
                    f"iterations {shared[0] + 1}-{shared[1]} are in both")
            elif (not (earlier.span.measurable and leg.span.measurable)
                    and earlier.resumed_from
                    and earlier.resumed_from == leg.resumed_from):
                yield earlier, leg, f"both resumed from {leg.resumed_from}"


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


def _result_in(directory: str, stem: str, prefer: str = "",
               tag: str = "") -> str:
    """The basename of ``stem``'s result file in ``directory``, or "".

    ``prefer`` wins when it is in this directory: the file the user actually
    opened decides which host's leg is being played, since a case run by both the
    GUI and the headless pipeline holds ``…dat.gui`` and ``…dat.cli`` side by side
    and they are two different solves. Failing that, ``tag`` narrows to the run
    being played — the user may have opened an ARCHIVED leg, in which case
    ``prefer`` names no file here and "newest" would otherwise hand back the other
    host's live output (#43, story 25). Failing both, newest wins and
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
    # Only when something here carries it: an ARCHIVE's names never do (the
    # rename replaced the tag), so this must narrow rather than exclude.
    tagged = [n for n in cands if run_tag(n) == tag] if tag else []
    return newest_first(directory, tagged or cands)[0]


def _archive_legs(case_root: str, stem: str) -> list:
    """One leg per ``work/prev_<NNN>/`` that holds this stem, oldest first.

    The identifying fields come from that archive's own ``RUN.txt`` (#30). The
    SPAN comes from ``case_run_note.iteration_span``, which prefers that record
    and falls back to the convergence history the archive holds — so an archive
    written before the record existed reports a real count instead of a blank
    (#43). An archive that can supply neither still gets a leg: hiding a part of
    the solve that exists is worse than playing it without a number.
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
            span=iteration_span(_convg_in(d, note), note=note),
            stamp=note.get("archived_at", ""),
            tag=note.get("run_tag", ""),
            has_note=bool(note),
            resumed_from=_started_at(note)))
    return out


def _convg_in(archive_dir: str, note: dict) -> str:
    """The archived run's convergence history, or "".

    The note's recorded name first — it is the record — but an archive predating
    #30 has no note at all and is exactly the leg this fallback exists for, so it
    is found by pattern when the record does not resolve. Both go through
    ``case_run_note.convergence_file``, which owns what such a file is called.
    """
    named = note.get("convergence_file") or ""
    if named and os.path.isfile(os.path.join(archive_dir, named)):
        return os.path.join(archive_dir, named)
    found = convergence_file(archive_dir)
    return os.path.join(archive_dir, found) if found else ""


def _live_leg(work: str, stem: str, prefer: str, order: int, tag: str = ""):
    """The un-archived leg in ``work/`` as a leg, or None.

    It has no ``RUN.txt`` — nothing has archived it yet — so its iteration count
    comes from the convergence history beside it, which is the same file and the
    same computation ``case_run_note.write_run_note`` will perform on it when it
    IS archived. ``restart_points._latest_point`` does this for the dump; this
    does it for the field output, through the same
    :func:`~app.services.restart_points.convg_beside`.
    """
    name = _result_in(work, stem, prefer=prefer, tag=tag)
    if not name:
        return None
    path = os.path.abspath(os.path.join(work, name))
    convg = convg_beside(work, name)
    return ResultLeg(
        kind=LATEST, key=LATEST, path=path, order=order,
        span=iteration_span(convg,
                            declared_interval=convergence_interval(work)),
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
