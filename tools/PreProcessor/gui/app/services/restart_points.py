"""What a solver case can be restarted FROM — its own history, as a list.

#31, USER-REQUESTED (2026-08-21). After restarting once, the next run is one of
two different intentions and a path field expresses neither: **continue further**
from the newest dump, or **re-run the same leg** from the dump the last run
itself resumed from, having looked at the results and wanted that segment
redone. The Solver panel offered a ``Restart`` tick plus a free-text
``zdump_fn_restart``, autofilled by looking for a fixed ``binDumpZ.dat`` +
``.gui``/``.cli`` **in work/ only** — so it knew nothing about the
``work/prev_<NNN>/`` archives #26 creates, and "re-run the same leg" meant the
user remembering which file that was and browsing to it.

The thing being decided is really an **iteration count**, and after #30 the case
records it: every archive carries a ``RUN.txt`` saying when that leg ran, what it
resumed from and how far it got. So this module reads the case dir and returns
the rows a chooser shows. It answers facts only — the row's prose, its marker and
the "Other file…" escape are the view's (``views/panels/restart_chooser``).

Four rules the shape follows from:

* **One function answers "how far did that run get?", and it is not here.**
  Every row's count comes from ``case_run_note.iteration_span``, which prefers
  the archive's ``RUN.txt`` and falls back to its own convergence history. #31
  shipped the opposite rule — the note IS the record, its history "deliberately
  not re-read", on the argument that a second computation would make two answers
  — and #43 reverses it, because the rule cost exactly the legs it was meant to
  protect: an archive written before #30 has no note and reported
  :data:`UNKNOWN_ITERATION` with a perfectly readable history sitting inside it,
  while the LIVE row two functions below computed its count from that same file
  with that same reader. One module was applying a computation to one leg and
  refusing it for its siblings. There is still exactly one answer; it just is not
  read from exactly one place.
* **The count shown is the count the solver PRINTED**, not the last row it wrote
  — ``last_row + interval``. #31 rendered it as the bound ``1990+`` and recorded
  that as a deliberate departure from its own specification; that departure is
  reversed (see ``case_run_note``'s module docstring for the full reversal and
  its evidence). An archive whose span cannot be computed at all still gets a
  row, unlabelled: hiding a restart point that exists would be worse than showing
  it without a number.
* **The list is derived on every call, never cached.** The case dir is the truth.
  A ``.hws`` reopened after the case moved on must not offer rows that are gone,
  which is also why the workspace stores none of this. The cost is stated rather
  than optimised away: one ``RUN.txt`` (under 2 KB) per archived leg, re-read
  whenever the case name is edited, so a case with hundreds of archived legs
  pays hundreds of small reads per keystroke. A cache is the wrong answer to
  that — it is the thing this rule forbids — and the honest one, if it is ever
  measured as a problem, is to debounce the caller.
* **The marker is matched by BASENAME.** The last run's restart reference is
  read out of ``work/input.in``, and for an archived dump it is the bare name of
  a hard link (#30) that the NEXT archive retires — so the file that reference
  named no longer exists at that path, while the bytes it pointed at are still
  in ``prev_<NNN>/`` under the same basename. Matching by path or inode would
  lose the mark on exactly the row #31 exists to highlight.

Qt-free, like the rest of the case services.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace

from app.services.case_files import (
    archive_subdirs,
    archive_suffix,
    is_restart_dump,
    newest_first,
    run_tag,
)
from app.services.case_run_note import (
    UNKNOWN_ITERATION,
    IterationSpan,
    convergence_interval,
    finished_stamp,
    iteration_span,
    mtime_stamp,
    read_run_note,
    resumed_from,
)
from app.services.logging_setup import get_logger
from app.services.solver_case import case_root_for, work_dir_of

_log = get_logger(__name__)

# ``UNKNOWN_ITERATION`` is ``case_run_note``'s, imported above rather than
# re-declared: it is what that module's readers return, and two copies of a
# sentinel is two chances for them to stop being the same number.

#: The kinds of row, which is also what the view switches on.
COLD = "cold"          #: no restart at all — initial conditions
LATEST = "latest"      #: the newest dump sitting directly in work/
ARCHIVE = "archive"    #: a dump inside one of work/prev_<NNN>/
OTHER = "other"        #: an arbitrary path the user browsed to (view-only)

#: The solver's convergence history, whose last row is how far a run got.
_CONVG_STEM = "unicones.enorm"


@dataclass(frozen=True)
class RestartPoint:
    """One row of the chooser: a place this case can be restarted from.

    ``zdump``/``convg`` are ABSOLUTE, because that is what the model holds (#25:
    it is the only form that still means the same thing from an auto-versioned
    work dir, and ``prepare_case_dir`` is what makes it work-dir relative on the
    way into ``input.in``). A row with no ``zdump`` is a real archive that holds
    no dump — it happened, it is worth seeing, and it cannot be resumed from.
    """
    kind: str
    key: str                                #: "cold" / "latest" / "prev_002"
    zdump: str = ""
    convg: str = ""
    #: How far that run got, from ``case_run_note.iteration_span`` — the whole
    #: answer, rather than the raw last row plus an interval the view has to
    #: combine for itself. It used to be exactly that pair, and the view combined
    #: them into a bound instead of a count (#43).
    span: IterationSpan = IterationSpan()
    #: When that run FINISHED — from ``case_run_note.finished_stamp``, which is
    #: the same event a live leg's stamp reports. It used to be the archive's
    #: ``archived_at``, i.e. when the NEXT run started, so one run changed its
    #: displayed time the moment it was archived (USER-REPORTED 2026-08-27); see
    #: that function for the measurement.
    stamp: str = ""
    #: When the folder was MADE, kept as its own labelled fact for the tooltip
    #: rather than discarded — it is true, it is just not what ``stamp`` answers.
    archived_at: str = ""
    tag: str = ""                           #: ".gui" / ".cli", when known
    resumed_by_last: bool = False

    @property
    def selectable(self) -> bool:
        """Whether picking this row can produce a run.

        Cold start and "Other file…" always can — the first names no file and
        the second is where the user names one. An ARCHIVE with no dump cannot:
        it happened, it is worth seeing in the list, and there is nothing in it
        to resume from.
        """
        return self.kind in (COLD, OTHER) or bool(self.zdump)


# ``case_root_for`` / ``work_dir_of`` are re-exported from ``solver_case``, which
# owns a case's layout — imported above rather than restated here, and named in
# ``__all__`` so a reader of this module's API still finds them.
__all__ = ["RestartPoint", "case_root_for", "convg_beside",
           "list_restart_points", "missing_source", "restart_errors",
           "work_dir_of",
           "COLD", "LATEST", "ARCHIVE", "OTHER", "UNKNOWN_ITERATION"]


def list_restart_points(case_root: str) -> tuple:
    """The rows a chooser offers for this case: cold start, the latest result,
    then the archived legs newest-first.

    Newest-first because "continue further" is the common intention and its row
    should be near the top; the archives descend from there, which is also the
    order they were created in reverse.
    """
    work = work_dir_of(case_root)
    marked = _last_resumed_basename(work)
    rows = [RestartPoint(kind=COLD, key=COLD,
                         resumed_by_last=marked == "")]
    latest = _latest_point(work)
    if latest is not None:
        rows.append(latest)
    rows.extend(_archive_points(case_root))
    return tuple(
        r if r.zdump == "" or os.path.basename(r.zdump) != marked
        else _marked(r)
        for r in rows)


def missing_source(raw: str, work_dir: str) -> str:
    """The absolute path ``raw`` names when that file is NOT there, else "".

    The half of :func:`restart_errors` that is worth asking on its own — see
    there for why a stale path had to become a GUI error. A blank value is not
    this function's business: "restart with no source at all" is a different
    error with its own message.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    resolved = os.path.abspath(
        raw if os.path.isabs(raw) else os.path.join(work_dir, raw))
    return "" if os.path.isfile(resolved) else resolved


def restart_errors(cfg) -> list:
    """Why this config's restart cannot run, as messages — empty when it can.

    Both halves belong here rather than in the controller because both are
    questions about a case's history: whether a source was chosen at all, and
    whether the files it names are still there. ``solver_ctrl._validate`` used to
    ask only the first, so a stale path — a case that moved on, a reopened
    ``.hws``, a hand-typed one — reached the solver and died there with a message
    about a derived per-zone filename that named neither the field nor the file
    (#31). The chooser closes most routes to that state, since it can only list
    files that exist, but "Other file…" and a restored workspace still reach it.
    """
    if not cfg.restart:
        return []
    work = work_dir_of(case_root_for(cfg.case_name))
    errs = []
    if not (cfg.zdump_fn_restart or "").strip():
        errs.append("Restart is on but no restart zone-dump file is set. Pick a "
                    "row under 'Start from' on the Solver panel — this case's "
                    "own results and archived legs are listed there — or "
                    "'Other file…' to name one elsewhere.")
    for what, raw in (("Zone dump", cfg.zdump_fn_restart),
                      ("Convg file", cfg.convg_fn_restart)):
        gone = missing_source(raw, work)
        if gone:
            errs.append(f"Restart {what!r} points at a file that does not "
                        f"exist: {gone}. Pick a row under 'Start from' on the "
                        "Solver panel, or correct the path.")
    return errs


# ── the three kinds of row ────────────────────────────────────────────────
def _marked(point: RestartPoint) -> RestartPoint:
    return replace(point, resumed_by_last=True)


def _dump_in(directory: str, archived: bool) -> str:
    """The newest zone dump directly in ``directory``, or "".

    ``archived`` selects which half of a work dir to look at: an archive's files
    all carry a ``.prev_<NNN>`` suffix, and ``work/`` holds BOTH this run's own
    output and the bare-named hard link to the dump it resumed from (#30). The
    link is the same bytes as an archive row, so counting it as "the latest
    result" would list one dump twice under two names.
    """
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return ""
    cands = [n for n in names
             if is_restart_dump(n) and bool(archive_suffix(n)) == archived
             and os.path.isfile(os.path.join(directory, n))]
    if not cands:
        return ""
    # Newest wins, with RUN_TAGS order as the tie-break so a work dir holding
    # both a .gui and a .cli dump of the same age answers the way the retired
    # autofill did. Only ONE row is offered for work/; a second dump there is
    # reachable through "Other file…", which is what that escape is for.
    # ``case_files.newest_first`` owns that rule: ``result_legs`` asks the same
    # question about the Tecplot field output beside these dumps (#32).
    return newest_first(directory, cands)[0]


def convg_beside(directory: str, name: str) -> str:
    """The convergence history that belongs with the file ``name``, or "".

    Same tag / same archive suffix, so a work dir holding a ``.gui`` and a
    ``.cli`` leg does not report one run's iteration count against the other's
    dump.

    Public because it is not a question about DUMPS: ``services/result_legs``
    asks it about a leg's *Tecplot result* file, which carries the same
    ``.gui`` / ``.prev_001`` slot for the same reason. One answer to "how far did
    the run that produced this file get?", rather than a second copy of the
    tag-matching rule in the module that plays the legs back.
    """
    suffix = archive_suffix(name)
    tag = run_tag(name)
    wanted = _CONVG_STEM + (("." + suffix) if suffix else tag)
    path = os.path.join(directory, wanted)
    if os.path.isfile(path):
        return path
    # No exact partner: fall back to any convergence file on the same side of
    # the archived/live split, which is the single-run case.
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return ""
    for name in names:
        if (name.startswith(_CONVG_STEM)
                and bool(archive_suffix(name)) == bool(suffix)
                and os.path.isfile(os.path.join(directory, name))):
            return os.path.join(directory, name)
    return ""


def _latest_point(work: str):
    """The newest un-archived dump in ``work/`` as a row, or None.

    Its iteration count comes from the convergence history beside it rather than
    from a note, because this leg has not been archived and so has none — the
    same computation ``case_run_note.write_run_note`` performs, on the same file,
    at the moment the archive is made. Its timestamp comes from the dump's own
    mtime for the same reason: an archive's ``archived_at`` is recorded when the
    files move, and nothing has moved this one yet. Formatted exactly like
    ``RUN.txt``'s, so a reader comparing rows is comparing one thing.
    """
    dump = _dump_in(work, archived=False)
    if not dump:
        return None
    path = os.path.abspath(os.path.join(work, dump))
    convg = convg_beside(work, dump)
    return RestartPoint(
        kind=LATEST, key=LATEST,
        zdump=path,
        convg=os.path.abspath(convg) if convg else "",
        span=iteration_span(convg,
                            declared_interval=convergence_interval(work)),
        stamp=mtime_stamp(path),
        tag=run_tag(dump))


def _archive_points(case_root: str) -> list:
    """One row per ``work/prev_<NNN>/``, newest first.

    The identifying fields come from that archive's own ``RUN.txt``; the
    iteration span comes from :func:`~app.services.case_run_note.iteration_span`,
    which prefers the note and falls back to the convergence history the archive
    holds — so an archive predating #30 gets a real count instead of a blank
    (#43). One with neither still gets a row, unlabelled.
    """
    out = []
    for rel in reversed(archive_subdirs(case_root)):
        d = os.path.join(case_root, *rel.split("/"))
        note = read_run_note(d)
        dump = note.get("zone_dump") or ""
        if not dump or not os.path.isfile(os.path.join(d, dump)):
            # The note names no dump (the no-hard-link fallback left it in
            # work/), or the folder no longer holds it. Look, rather than
            # reporting an archive as unusable on the strength of a text file.
            dump = _dump_in(d, archived=True)
        convg = note.get("convergence_file") or ""
        if not convg or not os.path.isfile(os.path.join(d, convg)):
            convg = os.path.basename(convg_beside(d, dump or ""))
        out.append(RestartPoint(
            kind=ARCHIVE, key=os.path.basename(d),
            zdump=os.path.abspath(os.path.join(d, dump)) if dump else "",
            convg=os.path.abspath(os.path.join(d, convg)) if convg else "",
            span=iteration_span(
                os.path.join(d, convg) if convg else "", note=note),
            stamp=finished_stamp(d, note),
            archived_at=note.get("archived_at", ""),
            tag=note.get("run_tag", "")))
    return out


def _last_resumed_basename(work: str) -> str | None:
    """The basename of what the run that last used ``work/`` resumed from, ""
    for a cold start, or None when it cannot be told.

    ``case_run_note.resumed_from`` reads the reference out of ``work/input.in``,
    which is the run that most recently ran here — the one whose result the user
    has just looked at. Its three states are kept apart for that module's
    reason: "we could not tell" must not render as the positive claim "cold
    start", which here would MARK the cold row.
    """
    if not os.path.isfile(os.path.join(work, "input.in")):
        return None
    ref = resumed_from(work)
    if ref is None:
        return None
    return os.path.basename(ref.strip()) if ref.strip() else ""
