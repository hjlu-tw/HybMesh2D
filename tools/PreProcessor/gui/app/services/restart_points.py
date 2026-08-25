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

Three rules the shape follows from:

* **``RUN.txt`` is the record; nothing here parses a dump.** That is why #31 was
  blocked by #30. An archive from before that (or one whose note cannot be read)
  still gets a row, with :data:`UNKNOWN_ITERATION` — hiding a restart point that
  exists would be worse than showing it without a number, and its convergence
  history is deliberately not re-read: the note IS the record, and inventing a
  second way to compute the field would make two answers for one question.
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
from dataclasses import dataclass, field, replace

from app.services.case_files import (
    RUN_TAGS,
    archive_subdirs,
    archive_suffix,
    is_restart_dump,
)
from app.services.case_run_note import (
    convergence_interval,
    last_iteration,
    read_run_note,
    resumed_from,
)
from app.services.paths import repo_root
from app.services.solver_case import sanitize_case_name

#: "we could not tell how far that run got" — never 0, which is a real answer
#: the solver prints for a cold start (``case_run_note.last_iteration``'s rule,
#: reused so one number means one thing across the two modules).
UNKNOWN_ITERATION = -1

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
    iteration: int = UNKNOWN_ITERATION
    interval: int = UNKNOWN_ITERATION
    stamp: str = ""                         #: RUN.txt's archived_at
    tag: str = ""                           #: ".gui" / ".cli", when known
    resumed_by_last: bool = False
    files: tuple = field(default_factory=tuple)

    @property
    def selectable(self) -> bool:
        """Whether picking this row can produce a run.

        Cold start and "Other file…" always can — the first names no file and
        the second is where the user names one. An ARCHIVE with no dump cannot:
        it happened, it is worth seeing in the list, and there is nothing in it
        to resume from.
        """
        return self.kind in (COLD, OTHER) or bool(self.zdump)


def case_root_for(case_name: str) -> str:
    """``<repo>/results/solver/<sanitised case>`` — where a case's history lives.

    One spelling: the panel needs it to list the rows, the controller to decide
    the case disposition, and the validator to resolve a relative reference. It
    was written out by hand in each.
    """
    return os.path.join(repo_root(), "results", "solver",
                        sanitize_case_name(case_name or "case"))


def work_dir_of(case_root: str) -> str:
    """``<case>/work`` — the directory the solver runs in."""
    return os.path.join(case_root, "work")


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

    ``solver_ctrl._validate`` used to check only that the field was non-empty, so
    a stale path — a case that moved on, a reopened ``.hws``, a hand-typed one —
    passed validation and died inside ``unicones`` with a message about a derived
    per-zone filename that names neither the field nor the file. The chooser
    removes most routes to that state (it can only list files that are there),
    but "Other file…" and a restored workspace still reach it.

    A blank value is not this function's business: "restart with no source at
    all" is a different error with its own message.
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
    def key(name):
        try:
            mtime = os.path.getmtime(os.path.join(directory, name))
        except OSError:
            mtime = 0.0
        tag = next((i for i, t in enumerate(RUN_TAGS) if name.endswith(t)),
                   len(RUN_TAGS))
        return (-mtime, tag, name)
    return sorted(cands, key=key)[0]


def _convg_beside(directory: str, dump: str) -> str:
    """The convergence history that belongs with ``dump``, or "".

    Same tag / same archive suffix, so a work dir holding a ``.gui`` and a
    ``.cli`` leg does not report one run's iteration count against the other's
    dump.
    """
    suffix = archive_suffix(dump)
    tag = next((t for t in RUN_TAGS if dump.endswith(t)), "")
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
    at the moment the archive is made.
    """
    dump = _dump_in(work, archived=False)
    if not dump:
        return None
    convg = _convg_beside(work, dump)
    iters = last_iteration(convg)[0] if convg else UNKNOWN_ITERATION
    return RestartPoint(
        kind=LATEST, key=LATEST,
        zdump=os.path.abspath(os.path.join(work, dump)),
        convg=os.path.abspath(convg) if convg else "",
        iteration=iters,
        interval=convergence_interval(work),
        tag=next((t for t in RUN_TAGS if dump.endswith(t)), ""))


def _archive_points(case_root: str) -> list:
    """One row per ``work/prev_<NNN>/``, newest first.

    Every field comes from that archive's own ``RUN.txt``; an archive without one
    predates #30 and gets a row anyway, with :data:`UNKNOWN_ITERATION`.
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
            convg = os.path.basename(_convg_beside(d, dump or ""))
        iters = note.get("last_iteration", UNKNOWN_ITERATION)
        out.append(RestartPoint(
            kind=ARCHIVE, key=os.path.basename(d),
            zdump=os.path.abspath(os.path.join(d, dump)) if dump else "",
            convg=os.path.abspath(os.path.join(d, convg)) if convg else "",
            iteration=iters if isinstance(iters, int) else UNKNOWN_ITERATION,
            interval=note.get("convergence_interval", UNKNOWN_ITERATION)
            if isinstance(note.get("convergence_interval"), int)
            else UNKNOWN_ITERATION,
            stamp=note.get("archived_at", ""),
            tag=note.get("run_tag", ""),
            files=tuple(note.get("files", ()))))
    return out


def _last_resumed_basename(work: str) -> str:
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
