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
    ARCHIVE_SUFFIX_PLACEHOLDER,
    RUN_TAGS,
    WORK_STAGED,
    archive_name,
    archive_name_collisions,
    archive_subdirs,
    archive_suffix,
    human_size,
    is_restart_dump,
    is_run_output,
    keep_matches,
    run_tag,
    staged_bare_names,
)
from app.services.case_run_note import (
    convergence_interval,
    resumed_from,
    write_run_note,
)


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

    ``tagged`` are basenames the archive will also leave a HARD LINK to directly
    in ``work/``, under their archived name (see
    :func:`archive_previous_outputs`). One counter has to clear BOTH, or the
    directory could be free while the link name is not and creating it would
    clobber the very dump it is protecting.
    """
    for n in range(1, 1000):
        suffix = f"{ARCHIVE_DIR_PREFIX}{n:03d}"
        candidate = os.path.join(work_dir, suffix)
        if os.path.exists(candidate):
            continue
        if any(os.path.exists(os.path.join(work_dir, archive_name(t, suffix)))
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


def archive_notice(case: str, case_root: str) -> str:
    """What continuing a RESTART in this case dir will do, as one log line.

    #31 dropped the case-dir prompt on the restart path, so this is where that
    confirmation's information now lives: with nobody agreeing to the archive in
    a dialog first, the step has to be legible in the user log on its own. Here
    rather than in the controller because it is a promise about what this module
    is about to do, naming the concrete directory the counter has already picked
    (``prev_003`` also tells the user this has happened twice).
    """
    prev = next_archive_name(case_root) or ARCHIVE_SUFFIX_PLACEHOLDER
    return (f"[case] restarting in '{case}': the previous run's outputs move to "
            f"work/{prev}/, each renamed to end in .{prev}, and work/ keeps a "
            f"link to the dump this run resumes from — the solver reads a "
            f"restart source only by a bare name in its own directory. Nothing "
            f"is overwritten and nothing is copied.")


def _archived_inodes(work_dir: str) -> dict:
    """``{(st_dev, st_ino): "prev_001/binDumpZ.dat.prev_001"}`` for every file
    already inside an archive under this work dir.

    By INODE, because that is the question: the zone dump lives in its archive
    and ``work/`` holds a HARD LINK to it, so "is this work-dir file already
    archived?" is "does something in an archive share its bytes?" — not "is
    there a file with the same name over there", which two runs of the same case
    satisfy by coincidence.
    """
    out = {}
    case_dir = os.path.dirname(os.path.abspath(work_dir))
    for rel in archive_subdirs(case_dir):
        d = os.path.join(case_dir, *rel.split("/"))
        for name in sorted(os.listdir(d)):
            f = os.path.join(d, name)
            if not os.path.isfile(f):
                continue
            st = os.stat(f)
            out.setdefault((st.st_dev, st.st_ino),
                           f"{os.path.basename(d)}/{name}")
    return out


def _into_archive(work_dir: str, name: str, dest: str, suffix: str,
                  moved: dict) -> str:
    """Move one output into ``dest`` under its archived name; return that path.

    The step both the plain move and the hard-linked zone dump begin with — one
    spelling, because recording the move in ``moved`` and deriving the archived
    name are the two things a caller must not forget and the linked path forgot
    neither by luck.
    """
    src = os.path.join(work_dir, name)
    dst = os.path.join(dest, archive_name(name, suffix))
    shutil.move(src, dst)
    moved[os.path.abspath(src)] = os.path.abspath(dst)
    return dst


def _retire(work_dir: str, name: str, inodes: dict, log) -> tuple:
    """Deal with a work-dir output whose name already carries an archive suffix,
    i.e. one that belongs to a run archived earlier. Returns
    ``(old_abspath, new_abspath)`` when it moved, else ``()``.

    This is the wart #26 left and #30 retires. There, the dump a restart resumed
    from was renamed in place and stayed in ``work/``, so on the NEXT restart it
    was just another output and got archived into ``prev_002/`` — prev_001's dump
    filed under run 2. Now the real file is already in its own archive and this
    is only the hard link that made it reachable by a bare name; that job is
    over, so the link goes and the bytes stay where they belong.

    Two other shapes reach here and neither may be moved blind. A file whose
    inode is NOT in an archive is a real file — the archive it names exists but
    something (a copy of the tree, which does not preserve links, or #26's own
    rename) left the only copy out here — so it is moved into the archive it is
    already named for, never into this run's. And if that archive cannot take it,
    it stays and is said out loud: a file this module cannot place is not a file
    to guess about.
    """
    src = os.path.join(work_dir, name)
    st = os.stat(src)
    known = inodes.get((st.st_dev, st.st_ino))
    if known:
        os.remove(src)
        log(f"[case] work/{name} was a hard link to {known}, which is where the "
            f"bytes stay — the link existed so a restart could read the dump by "
            f"a bare name, and nothing resumes from it now.")
        return ()
    suffix = archive_suffix(name)
    dest = os.path.join(work_dir, suffix)
    dst = os.path.join(dest, name)
    if not os.path.isdir(dest) or os.path.exists(dst):
        log(f"[case] work/{name} belongs to {suffix}, which "
            + ("already holds a file of that name" if os.path.isdir(dest)
               else "no longer exists")
            + " — left where it is rather than filed under this run.")
        return ()
    shutil.move(src, dst)
    log(f"[case] work/{name} -> {suffix}/{name} — it belongs to the run it is "
        f"named for, not to the one being archived now.")
    return os.path.abspath(src), os.path.abspath(dst)


def _report_collision(clash, log) -> None:
    """Say which files wanted one archived name, and why they did.

    A message that only says "collision" leaves the user with nothing to do, so
    it names both files of every pair, the name they both wanted, and the reason
    they wanted it — that archiving REPLACES the run tag, which is the whole
    point of #30's one-naming-scheme rule and is invisible from the file names
    alone. The last line is what makes it actionable, and it does not soften
    what a refusal leaves behind: nothing was destroyed by the ARCHIVE, but the
    run that follows carries one of the two tags and so writes over the half of
    every pair that shares it — the same claim the exhausted-counter refusal
    makes about the files it declines to move, for the same reason (a
    reassuring-but-not-quite-true line is the failure class ``resumed_from``
    keeps None and "" apart to avoid).
    """
    for wanted, names in clash:
        log(f"[WARNING] work/ holds {len(names)} files that archiving would "
            f"give ONE name: {', '.join(names)} -> {wanted}. Archiving replaces "
            f"a run's tag ({'/'.join(RUN_TAGS)}, saying which host produced the "
            f"file) with the archive's, so two runs' outputs want the same "
            f"archived name.")
    log("[WARNING] nothing was archived and nothing was moved — every file is "
        "still where it was, which is what makes this recoverable. Move or "
        "rename one of each pair out of work/ and restart again. THIS run "
        "carries one of those tags itself, so until then it writes over the "
        "half of every pair that shares it — the dump it is resuming from "
        "included.")


def bare_link_for_archived_dump(work_dir: str, resolved: str,
                                log=_noop) -> str:
    """Give a restart dump that lives in one of this work dir's own archives a
    BARE name in ``work/``, and return that path — or "" when there is nothing to
    do or it cannot be done.

    The other half of #31's chooser. :func:`archive_previous_outputs` already
    leaves such a link for the dump a run resumes from, because the solver reads
    a restart source only by a bare name in its own directory: point
    ``zdump_fn_restart`` at ``prev_001/binDumpZ.dat.prev_001`` and it derives a
    per-zone path out of it — ``binDumpZ.dat.prev_001/binDumpZ.0`` — into a
    directory that does not exist, and the run dies with ``Can't open file``
    (measured on the real binary; see the docstring below).

    That link is retired the next time this case is archived, and #31 lets the
    user pick ANY archived leg — "re-run the same leg", the whole point of the
    chooser — so the one mechanism has to be available on demand rather than only
    as a side effect of the run that produced it. Same trade for the same reason:
    a HARD link, so the archive stays complete and the case does not grow by a
    second copy of its largest file, and the file is never edited (the one place
    this repo's "a hard link is not the cheap version of a copy" rule flips —
    ``services/case_sources``).

    Two things it refuses to do rather than guess. A name in ``work/`` that is
    already taken by a DIFFERENT file is not overwritten — the reference then
    stays as it was and the solver reports its own error, which is honest, where
    clobbering would destroy a file nobody asked about. And on a filesystem that
    cannot make the link, nothing is copied: the dump is the largest file in a
    case, so silently doubling it is worse than saying the restart cannot be made
    readable and letting the run fail with its own message.
    """
    resolved = os.path.abspath(resolved)
    parent = os.path.dirname(resolved)
    if (not os.path.isfile(resolved)
            or not os.path.basename(parent).startswith(ARCHIVE_DIR_PREFIX)
            or os.path.dirname(parent) != os.path.abspath(work_dir)):
        # Not a dump inside one of THIS work dir's archives: a dump sitting
        # directly in work/ is already bare, and one in another case dir is #25's
        # relative reference, which resumes correctly as it is.
        return ""
    link = os.path.join(work_dir, os.path.basename(resolved))
    if os.path.exists(link):
        if os.path.samefile(link, resolved):
            return link
        log(f"[WARNING] work/{os.path.basename(link)} is a different file, so "
            f"the dump in {os.path.basename(parent)}/ cannot be given the bare "
            f"name the solver needs; the restart reference is left pointing "
            f"into the archive.")
        return ""
    try:
        os.link(resolved, link)
    except OSError:
        log(f"[WARNING] could not link work/{os.path.basename(link)} to "
            f"{os.path.basename(parent)}/{os.path.basename(resolved)}; the "
            f"solver reads a restart source only by a bare name in its own "
            f"directory, so this run may not find what it is resuming from.")
        return ""
    log(f"[case] the dump this run resumes from is in "
        f"{os.path.basename(parent)}/, so work/ gets a bare-named hard link to "
        f"it ({os.path.basename(link)}) — the solver reads a restart source "
        f"only by a bare name, and one inode means no second copy.")
    return link


def archive_previous_outputs(work_dir: str, log=_noop, keep_bare=()) -> dict:
    """Put the previous run's OUTPUTS in ``work_dir`` beyond this run's reach.
    Returns ``{old_abspath: where_a_reference_should_now_point}``.

    This is what makes "continue in the same folder" a safe answer for a restart
    (#26, USER-REPORTED 2026-08-20). Reusing a case directory meant the new run
    wrote over the previous one's solution dumps and convergence history as it
    went — and the file it was RESUMING FROM is one of those. That is not a
    hypothetical: the solver's output dump is ``binDumpZ.dat`` + its ``-t`` tag,
    which is the SAME name a GUI restart resumes from, so **every** same-folder
    restart overwrote its own restart point in place (measured on the real
    binary: the source file's checksum changes).

    Everything moves into a fresh ``work/prev_<NNN>/``, the zone dump included,
    and every archived file is renamed so it ends in ``.prev_<NNN>``
    (:func:`~app.services.case_files.archive_name`). The dump named in
    ``keep_bare`` additionally gets a **hard link** at ``work/<archived name>``,
    because the solver can only read a restart source by a bare name in its own
    cwd. Measured on the real binary, with the dump in the subdirectory and
    ``zdump_fn_restart`` pointing at ``prev_001/binDumpZ.dat.gui``, it derives a
    per-zone path from the reference — ``binDumpZ.dat.prev_001/binDumpZ.0`` —
    whose directory does not exist, and the run dies with ``Can't open file``.
    The link satisfies both halves at once: bare, so the derivation never
    happens, and different from the output name, so the run cannot write over it
    (measured: ``Global Iteration count 1000``, i.e. a real resume, with the
    source file unchanged).

    Seven rules:

    * **An allow-list decides, not a glob.** Only what ``case_files`` classifies
      as produced-by-a-run is touched. The inputs ``prepare_case_dir`` stages
      stay, or the resumed run loses its own configuration — the fixed-name ones
      by ``case_files.WORK_STAGED``, the user-named tables of #29 by the previous
      ``input.in`` quoting them (``case_files.staged_bare_names``), since no list
      can hold a name the user chose. Anything none of that recognises **stays and is
      named in the log** — a file nobody classified is not a file to move blind.
    * **Move or link, never copy.** The zone dump is the largest file in a case
      — 10.6 MB in the reported one and hundreds of MB in a real one — so a
      copy would grow the case on every resume and leave two dumps whose
      relationship nothing records. The hard link is the one place this repo's
      "a hard link is not the cheap version of a copy" rule (``case_sources``)
      flips, and for the reason that rule gives: there the danger is that
      editing one path rewrites what the case holds, and a zone dump is never
      edited. Sharing the inode is the property wanted here, not a shortcut.
    * **A file that already names an earlier run is not this run's to file.**
      See :func:`_retire` — this is what retires #26's ``prev_002``-holds-
      ``prev_001``'s-dump wart. Note the precise shape of "an archive is
      finished": what a later run may not do is add ITS OWN outputs to one.
      Putting a file the previous version left in ``work/`` into the archive it
      is *already named for* is the opposite move — it completes that archive
      rather than mixing two runs — and it is refused the moment the name is
      taken.
    * **Two files that want ONE archived name are REFUSED, wholesale.** The
      rename above replaces a run's tag, so ``xtecp_sol_allz.dat.cli`` and
      ``xtecp_sol_allz.dat.gui`` — the same output of one case run by the two
      hosts, which a work dir holds after a headless run is reused from the GUI
      with "Overwrite" — both want ``xtecp_sol_allz.dat.prev_001``, and the
      second move landed on the first: a whole run's field output and
      convergence history destroyed with no message (#42, and which of the two
      survived was decided by directory listing order). Asked once over the set
      about to move (``case_files.archive_name_collisions``) and refused BEFORE
      anything moves, so a refusal is a no-op rather than a half-archive: same
      answer, and the same reason, as the exhausted counter below. The run then
      proceeds on its own terms with every file still on disk.

    * **Nothing is created when nothing moves.** An empty or output-free work dir
      (a fresh case, or an auto-versioned one) returns ``{}`` silently, which is
      what lets the caller pass ``archive_prev`` without first asking whether
      there is anything to archive.
    * **One counter clears both names** (see :func:`next_archive_dir`).
    * **The archive describes itself**, in a ``RUN.txt`` beside the files (see
      ``services/case_run_note``). It is the one file in there that does NOT end
      in ``.prev_<NNN>``, deliberately: it is the archive's own record rather
      than something the run produced, and #30 asks for it by that name.

    The returned mapping is how the restart reference follows the file it
    names: see :func:`~app.services.solver_case.restart_refs_for_work_dir`. It
    maps a file's old path to **where a reference to it should now point**,
    which for the zone dump is the hard link in ``work/`` rather than the real
    file in the archive — the bare name is the whole reason the link exists.
    """
    if not os.path.isdir(work_dir):
        return {}
    bare = {os.path.abspath(p) for p in keep_bare}
    to_move, to_link, retired, unknown = [], [], [], []
    staged = staged_bare_names(work_dir)
    inodes = _archived_inodes(work_dir)
    for name in sorted(os.listdir(work_dir)):
        src = os.path.join(work_dir, name)
        if not os.path.isfile(src):
            # Earlier archives are ours and expected; any other directory is the
            # same "nobody classified this" case as an unknown file, and gets the
            # same treatment — left alone, and said out loud. An `isfile` guard
            # that just skips is how a folder becomes invisible.
            if not name.startswith(ARCHIVE_DIR_PREFIX):
                unknown.append(name + "/")
            continue
        if is_run_output(name):
            resumed = os.path.abspath(src) in bare
            if archive_suffix(name):
                # Already named for the run it came from. Leave it completely
                # alone when it is the dump THIS run resumes from: it is already
                # bare, already differs from the name the solver will write, and
                # re-tagging it would file it under a run it did not come from.
                if not resumed:
                    retired.append(name)
            elif resumed:
                to_link.append(name)
            else:
                to_move.append(name)
        elif not keep_matches(name, WORK_STAGED) and name not in staged:
            unknown.append(name)
    for name in unknown:
        log(f"[case] work/{name} is not a recognised solver input or output — "
            "left where it is, not archived.")
    # Two names collide under EVERY suffix or none — it is the same suffix for
    # both — so detecting one costs a dict build and no directory scan, which is
    # what keeps the common case free. Naming the archive they wanted DOES cost
    # the counter, so it is asked once a refusal is certain and never otherwise.
    if archive_name_collisions(to_move + to_link, ARCHIVE_SUFFIX_PLACEHOLDER):
        wanted = os.path.basename(next_archive_dir(work_dir, tagged=to_link))
        _report_collision(
            archive_name_collisions(to_move + to_link,
                                    wanted or ARCHIVE_SUFFIX_PLACEHOLDER), log)
        return {}
    # Read before anything moves: this is the run being archived, and its own
    # input.in is the only record of what IT resumed from. Above the retire loop
    # rather than beside its use, because that loop already moves files.
    came_from = resumed_from(work_dir)
    interval = convergence_interval(work_dir)
    moved = {}
    for name in retired:
        pair = _retire(work_dir, name, inodes, log)
        if pair:
            moved[pair[0]] = pair[1]
    if not to_move and not to_link:
        return moved

    dest = next_archive_dir(work_dir, tagged=to_link)
    if not dest:
        log("[WARNING] work/ already holds 999 archived runs; the previous "
            "outputs were left in place and THIS run will write over them.")
        return moved
    suffix = os.path.basename(dest)
    os.makedirs(dest)
    total = 0
    for name in to_move:
        total += os.path.getsize(os.path.join(work_dir, name))
        _into_archive(work_dir, name, dest, suffix, moved)
    if to_move:
        log(f"[case] previous outputs -> work/{suffix}/ "
            f"({len(to_move)} file{'s' if len(to_move) != 1 else ''}, "
            f"{human_size(total)}); this run writes clean files into work/.")
    for name in to_link:
        src = os.path.join(work_dir, name)
        real = _into_archive(work_dir, name, dest, suffix, moved)
        arch = os.path.basename(real)
        link = os.path.join(work_dir, arch)
        try:
            os.link(real, link)
        except OSError:
            # A filesystem with no hard links (or one refusing this one): the
            # RESTART matters more than a complete archive, so the dump goes back
            # out to the bare name the solver requires and the archive is short
            # one file — said out loud rather than left to be discovered.
            shutil.move(real, link)
            log(f"[WARNING] work/ cannot hold a hard link, so the zone dump "
                f"stays directly in work/{arch} instead of inside {suffix}/. "
                f"The restart is unaffected; the archive is incomplete.")
        else:
            log(f"[case] the dump this run resumes from -> "
                f"work/{suffix}/{arch} ({human_size(os.path.getsize(real))}), "
                f"with a hard link at work/{arch} — the solver reads a restart "
                f"source only by a bare name in its own directory, and one inode "
                f"means the archive is complete without a second copy.")
        # The map points at the LINK, not at the file in the archive: the bare
        # name is the whole reason the link exists (see the docstring).
        moved[os.path.abspath(src)] = os.path.abspath(link)
    # to_link first, so a case holding two dumps reports the one being resumed
    # from rather than whichever the directory listing reached first.
    dump_name = next((archive_name(n, suffix) for n in to_link + to_move
                      if is_restart_dump(n)), "")
    if dump_name and not os.path.isfile(os.path.join(dest, dump_name)):
        # The no-hard-link fallback above put it back in work/, so the archive
        # does not hold it. Read off the tree rather than from a flag, because a
        # note claiming a file the folder has not got is the same false-record
        # failure `resumed_from` returning None exists to avoid.
        dump_name = ""
    if os.listdir(dest):
        note = write_run_note(
            dest, suffix, came_from=came_from, zone_dump=dump_name,
            interval=interval,
            # Read off the names BEFORE the rename, since replacing that tag is
            # what makes the archive uniformly named — RUN.txt is where it
            # survives.
            tag=next((run_tag(n) for n in to_move + to_link if run_tag(n)), ""))
        log(f"[case] work/{suffix}/{os.path.basename(note)} records when that "
            f"run happened, what it resumed from and how far it got.")
    else:
        # Only reachable through the no-hard-link fallback above, where the one
        # file the archive was for went back out to work/. An empty prev_NNN/
        # with a RUN.txt in it would describe an archive that holds nothing.
        os.rmdir(dest)
    return moved
