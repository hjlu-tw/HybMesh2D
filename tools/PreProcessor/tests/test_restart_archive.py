#!/usr/bin/env python3
"""A restart continues in the SAME case dir without writing over what it resumes
from.

USER-REPORTED (2026-08-20, issue #26). Continuing a converging run belongs in the
case folder it is resuming — that is the point of a restart — but the case-dir
prompt offered only "Overwrite" (reuse the dir and write over the previous run's
outputs as this one produces its own) and "New Versioned Dir" (preserve them, and
split one continued solution across two directories). The destructive option was
therefore the only one that did what the user asked for, and the file it
destroyed includes the dump the run is RESUMING FROM: a crash part-way through a
dump write could leave no usable restart point at all.

So the previous run's outputs move into ``work/prev_<NNN>/`` first
(``services/case_archive``), and the restart reference follows them
(``solver_case.restart_refs_for_work_dir(..., moved=)`` — which is why this was
blocked by #25: the reference has to be emitted work-dir relative to resolve).

Pinned here, against the real ``prepare_case_dir`` on a temp tree, the real
``case_export`` planner, and the real ``ask_case_disposition`` dialog:

 1. the outputs move, the run's own staged inputs stay, and every archived file
    is named for the run it belongs to — ONE scheme, ending in ``.prev_<NNN>``;
 1b. the zone dump is IN the archive and ``work/`` holds a hard link to it, so
    the archive is complete and the case grows by ~0 bytes (#30);
 2. the resumed run READS the archived dump — the reference is the bare
    ``binDumpZ.dat.prev_001`` and it resolves from the work dir;
 2b. …and that is not free: without the moved mapping the same reference comes
    out as this machine's absolute path, i.e. the mechanism is load bearing;
 2c. a RELATIVE reference (a hand-written script, a re-loaded .hws) follows the
    move too — #25's "a relative value is left alone" is narrowed by exactly the
    one file this run moved, and by nothing else;
 3. a file neither list recognises stays put and is NAMED in the log;
 4. the counter increments — a second restart archives into prev_002/, leaves
    prev_001/ untouched, and no longer files prev_001's dump under run 2;
 5. the destructive escape still overwrites in place (archive_prev=False), and
    archiving a dir with nothing to archive creates no directory at all;
 6. ``case_export`` accounts for ``work/prev_001/`` — every file in it is either
    shipped or named as skipped, never silently omitted (the exporter's own gate
    sees an archive too: ``test_case_export.py`` check 16);
 7. the prompt is now the NON-restart question only — #31 took the restart
    branch away, because once the start point is chosen from this case's own
    history there is nothing left to ask (the controller's side of that is
    pinned in tests/test_restart_chooser.py check 10);
 8. each archive carries a ``RUN.txt`` recording when that leg ran, the run tag
    the rename discards, what it resumed from and how far it got — and it round
    trips through the reader the next feature will use, rather than being prose
    only a human can parse;
 9. two runs' outputs in ONE work dir (a headless run reused from the GUI with
    "Overwrite", then restarted) are REFUSED rather than archived on top of each
    other — #42, and the only property here that is about what the archive must
    NOT do. 9b injects the guard's absence and measures the destruction it
    prevents; 9c is the negative control that a work dir holding one run's
    outputs still archives exactly as before.

#30 is the finishing work on top of #26 and changed two of the properties above
rather than adding to them, so the old expectations are gone from this file
deliberately: the dump used to be renamed **in place** and left in ``work/``
(one archive, two naming schemes), and the next restart then filed prev_001's
dump inside ``prev_002/`` — check 4 pinned that wart, and now pins its absence.
The bare-name requirement is unchanged and non-negotiable; what changed is that
a hard link, not a rename, is what satisfies it.

What the checks here cannot give, an acceptance run did — and it is what
established the design, so it is recorded rather than left as a blind spot.
Driving the real ``prepare_case_dir`` over the reported case and then the real
``unicones`` binary on what it produced: **exit 0, ``Global Iteration count
1000``** (a cold start reports 0, so the run really resumed), the restart source
byte-identical afterwards, no path errors, and a fresh dump written beside it.
The same run measured the two facts the design turns on, neither of which is
guessable from the file layout:

* **the reference must be a BARE name.** With the dump moved into ``prev_001/``
  and the reference pointing there, the solver derives a per-zone path from it —
  ``binDumpZ.dat.prev_001/binDumpZ.0`` — into a directory that does not exist,
  and dies with ``Can't open file``. That was the first, shipped version of this
  fix, and it is why ``work/`` keeps a bare-named hard link to the archived dump
  (#26 renamed it in place; #30 moved the bytes into the archive and left the
  link, which satisfies the same requirement with one copy of the file).
* **it must DIFFER from the solver's own output dump name.** That name is
  ``binDumpZ.dat`` + the ``-t`` tag, i.e. exactly what a GUI restart resumes
  from, so before this change every same-folder restart rewrote its own restart
  point (measured: the source file's checksum changes). The issue described that
  as a crash-window risk; it is in fact what happened on every run.

Property 9's own blind spots, named rather than left to be discovered:

* **the mixed-tag work dir is SEEDED, not reached.** The route the issue
  measured is headless run -> GUI run answering *Overwrite* -> GUI restart, and
  nothing here drives it; the pre-state is written by hand. What the checks
  therefore prove is that the archiver refuses the state, not that the state is
  reachable — reachability was established in the issue and re-derived by
  reading (the headless pipeline auto-versions and can never land on an occupied
  case dir, so the GUI's Overwrite is the only door);
* **the guard protects the ARCHIVE, and the run that follows still overwrites.**
  A refusing restart carries one of the two tags itself, so it writes over the
  half of every pair that shares it — including the dump it resumes from. That
  is #26's hazard reappearing through the door the refusal deliberately leaves
  open (the issue puts the Overwrite disposition out of scope), and the only
  thing pinned about it is that the message SAYS so. Nothing here runs the
  solver;
* **9b injects by monkeypatching the imported name**, not by mutating source and
  re-parsing it. That is this file's existing idiom for a behavioural gate (see
  the 2b negative control) and it removes the exact call the fix added, so the
  destruction it measures is real; what it does not give is the AST-level
  "the mutation still parses and really differs" the static gates in this repo
  perform on their own source.

One genuine residue, measured and out of scope: a reference into ANOTHER case
dir (#25's ``../../own/work/binDumpZ.dat.gui``, which auto-versioning produces)
does resume correctly — iteration 1000, source untouched — but leaves one empty
``binDumpZ.dat.0`` behind in the work dir from the same derivation. Harmless,
not fixed here.

#30 was accepted the same way, on the same case, because the issue says so in as
many words ("Run the binary — a green test suite did not catch this class of bug
in #26"). Two consecutive restarts through the real ``prepare_case_dir`` and the
real ``unicones`` binary:

* **run 1** — exit 0, first line ``Global Iteration count 2000`` (the previous
  leg's convergence history ends at 1990, so it really resumed rather than
  cold-starting at 0), the restart source **sha256-identical** afterwards, a
  fresh ``binDumpZ.dat.gui`` written beside it, and ``prev_003/`` holding all
  six outputs named ``…prev_003`` plus ``RUN.txt`` reporting
  ``last_iteration: 1990`` beside ``convergence_interval: 10`` — i.e. the note's
  own bound, [1990, 2000), containing the 2000 the solver reported. That is the
  "records 1990, reached 2000" gap measured rather than argued, and the reason
  the interval is recorded at all;
* **run 2** — exit 0, resumed again (``Global Iteration count 4020``), source
  identical, ``prev_004/`` created, ``prev_003/`` byte-for-byte untouched and
  its dump down to ONE link because the stale bare-named link in ``work/`` was
  removed rather than archived into ``prev_004/``. That is acceptance item 4,
  on real data.

Two more numbers from the same runs. The case grew from **24352 KB to 24356 KB**
across an archive whose zone dump is 1597 KB — the +4 KB is the new directory
and its note, so the hard link really is one copy of the bytes. And the case on
disk still carried ``binDumpZ.dat.gui.prev_002`` from #26's shipped in-place
rename; it was filed into ``prev_002/``, where it belongs, rather than into this
run's archive — the upgrade path exercised on the file that motivated the issue.

Run:  python3 tools/PreProcessor/tests/test_restart_archive.py
"""
import os
import shutil
import sys
import tempfile
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >180s", flush=True)
    os._exit(99)


_wd = threading.Timer(180, _watchdog)
_wd.daemon = True
_wd.start()

from app.models.solver_config import SolverConfig          # noqa: E402
from app.services import (                                     # noqa: E402
    case_archive, case_export, case_run_note, solver_case,
)
from app.services.case_files import archive_name                # noqa: E402

tmp = tempfile.mkdtemp(prefix="hybmesh_restart_arch_")
repo = os.path.join(tmp, "repo")
mesh = os.path.join(repo, "m")


def w(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


for ext in (".vrt", ".cel", ".bnd"):
    w(mesh + ext, "mesh")

_real_repo_root = solver_case.repo_root
solver_case.repo_root = lambda: repo

LOG = []


def prep(case_name, *, zdump="", convg="", overwrite=True, archive_prev=True,
         restart=True):
    LOG.clear()
    cfg = SolverConfig()
    cfg.case_name = case_name
    cfg.input_vrt_file = mesh + ".vrt"
    cfg.input_cel_file = mesh + ".cel"
    cfg.input_bnd_file = mesh + ".bnd"
    cfg.restart = restart
    cfg.zdump_fn_restart = zdump
    cfg.convg_fn_restart = convg
    return cfg, solver_case.prepare_case_dir(
        cfg, log=LOG.append, overwrite=overwrite, archive_prev=archive_prev)


def quoted(input_in, key):
    with open(input_in) as f:
        for line in f:
            parts = line.split()
            if parts[:1] == [key]:
                return line.split('"')[1] if '"' in line else parts[1]
    return None


# The solver's convergence history: iteration number in column 1, one row every
# print_convg_per_niter iterations. Real rows, because RUN.txt's one number is
# read off the last one (check 8) and a placeholder would only prove it says -1.
CONVG = "10   1.55e-16  5.5e-03\n20   1.69e-16  2.1e-03\n30   1.60e-16  1.5e-03\n"


def seed_previous_run(case, extra=()):
    """A work/ as a finished run leaves it: this run's staged inputs, plus the
    outputs it produced. Names taken from what the solver really writes."""
    work = os.path.join(repo, "results", "solver", case, "work")
    outputs = ["binDumpZ.dat.gui", "unicones.enorm.gui",
               "xtecp_sol_allz.dat.gui", "probe_data.gui", "fort.11",
               "tWall.dat", "mesh_tecplot.plt"]
    inputs = ["input.in", "phi.dat", f"{case}.bc.def", "userbc.so"]
    for name in outputs + inputs + list(extra):
        w(os.path.join(work, name),
          CONVG if name.startswith("unicones.enorm") else name)
    w(os.path.join(repo, "results", "solver", case, "grid", f"{case}.grid"), "G")
    return work, outputs, inputs


def inode(path):
    st = os.stat(path)
    return (st.st_dev, st.st_ino)


# ── 1/2/3. the archive itself, through the real prepare_case_dir ───────────
work, outputs, inputs = seed_previous_run("beta", extra=["notes.txt"])
os.makedirs(os.path.join(work, "stray_dir"), exist_ok=True)
w(os.path.join(work, "stray_dir", "something.txt"), "x")
dump = os.path.join(work, "binDumpZ.dat.gui")
convg = os.path.join(work, "unicones.enorm.gui")
cfg1, (w1, _g1, in1) = prep("beta", zdump=dump, convg=convg)

check(os.path.abspath(w1) == os.path.abspath(work),
      "1. (precondition) the run continues in the SAME case dir — that is what "
      "a restart asked for")
arch = os.path.join(work, "prev_001")
archived_expected = sorted([archive_name(n, "prev_001") for n in outputs]
                           + [case_run_note.RUN_NOTE_NAME])
check(sorted(os.listdir(arch)) == archived_expected,
      f"1. every one of the previous run's outputs moved into work/prev_001/, "
      f"the zone dump included "
      f"({sorted(os.listdir(arch)) if os.path.isdir(arch) else 'no such dir'})")
check(all(n.endswith(".prev_001")
          for n in os.listdir(arch) if n != case_run_note.RUN_NOTE_NAME),
      f"1. ...and every one of them is named for the RUN it belongs to — one "
      f"scheme, not two. #26 tagged the dump with the archive while everything "
      f"beside it kept its .gui run tag, so one folder read as two "
      f"({sorted(os.listdir(arch))})")
check("unicones.enorm.prev_001" in os.listdir(arch)
      and "fort.11.prev_001" in os.listdir(arch),
      f"1. ...a trailing run tag is REPLACED and a name without one is appended "
      f"to — the same slot says the same kind of thing "
      f"({sorted(os.listdir(arch))})")
check(all(not os.path.exists(os.path.join(work, n)) for n in outputs),
      "1. ...MOVED, never copied — the zone dump is the largest file in a case, "
      "and two of them would leave nothing recording their relationship")
check(all(os.path.isfile(os.path.join(work, n)) for n in inputs),
      f"1. the run's own staged inputs stay in work/ — input.in, the BC table, "
      f"the phase field and a type-11 BC .so. Archive them and the resumed run "
      f"restarts into nothing "
      f"({[n for n in inputs if not os.path.isfile(os.path.join(work, n))]})")

# ── 1b. the dump is IN the archive; work/ holds a hard link to it ──────────
real_dump = os.path.join(arch, "binDumpZ.dat.prev_001")
link_dump = os.path.join(work, "binDumpZ.dat.prev_001")
check(os.path.isfile(real_dump) and os.path.isfile(link_dump)
      and not os.path.exists(os.path.join(work, "binDumpZ.dat.gui")),
      f"1b. the dump this run resumes from lives in the archive it belongs to, "
      f"with a bare-named link in work/ — #26 had to leave the file itself out "
      f"here, so the archive was never complete "
      f"({sorted(n for n in os.listdir(work) if n.startswith('binDump'))})")
check(os.path.isfile(link_dump) and inode(link_dump) == inode(real_dump),
      "1b. ...and it is the same inode, not a copy: st_dev/st_ino match, so "
      "archiving grows the case by ~0 bytes. This is the ONE place the repo's "
      "'a hard link is not the cheap version of a copy' rule flips, and for "
      "that rule's own reason — a zone dump is never edited")
check(os.stat(link_dump).st_nlink == 2,
      f"1b. ...two links to one file, which is what the NEXT restart reads to "
      f"tell an already-archived dump from a fresh one "
      f"({os.stat(link_dump).st_nlink} link(s))")

ref = quoted(in1, "zdump_fn_restart")
check(ref == "binDumpZ.dat.prev_001",
      f"2. the restart reference follows the dump to its new name ({ref!r})")
check("/" not in ref and os.path.isfile(os.path.join(w1, ref)),
      "2. ...and it is a BARE name that resolves in the work dir the solver "
      "runs in. Bare is not tidiness: measured on the real binary, any "
      "reference with a directory component makes the solver build a per-zone "
      "path out of it (prev_001/... -> binDumpZ.dat.prev_001/binDumpZ.0) and "
      "the run dies with \"Can't open file\"")
check(ref != "binDumpZ.dat.gui" and not os.path.exists(
          os.path.join(w1, "binDumpZ.dat.gui")),
      "2. ...and it differs from the name the solver writes its OWN dump to "
      "(binDumpZ.dat + the -t tag), which is the whole hazard: measured, a "
      "same-name restart rewrites the file it resumed from")
check(quoted(in1, "convg_fn_restart") == "prev_001/unicones.enorm.prev_001",
      f"2. both restart fields, not just the dump — and the convergence file "
      f"DOES go into the archive, because only the zone dump has the bare-name "
      f"constraint (measured: a subdirectory path here runs clean) "
      f"({quoted(in1, 'convg_fn_restart')!r})")
check(cfg1.zdump_fn_restart == dump,
      "2. the CONFIG keeps its absolute path to work/ — unchanged from #25, and "
      "right: the panel's field means 'the dump in this case's work dir', which "
      "the NEXT restart archives in its turn")

# Negative control: the mapping is what makes 2 true, not the relative-path fix
# alone. Without it the reference resolves to a file that is no longer there and
# falls through to the pass-through branch — this machine's absolute path.
bare = solver_case.restart_refs_for_work_dir(cfg1, w1)[0]
check(bare == dump,
      f"2b. without the moved mapping the same reference comes back as this "
      f"machine's absolute path — the archive would have broken the restart it "
      f"exists to protect ({bare!r})")

check(any("stray_dir/" in m and "not a recognised" in m for m in LOG),
      f"3. an unrecognised SUBDIRECTORY is named too — skipping every non-file "
      f"is how a folder becomes invisible, which is the bug this repo already "
      f"had in the exporter ({[m for m in LOG if 'stray_dir' in m]})")
check(os.path.isdir(os.path.join(work, "stray_dir")),
      "3. ...and it is left where it is, like an unrecognised file")

check(os.path.isfile(os.path.join(work, "notes.txt")),
      "3. a file neither the output list nor the staged-input list recognises "
      "is LEFT where it is — nobody classified it, so nobody moves it")
check(any("notes.txt" in m and "not a recognised" in m for m in LOG),
      f"3. ...and it is named in the log rather than quietly ignored "
      f"({[m for m in LOG if 'notes.txt' in m]})")
check(any("prev_001/" in m and "previous outputs" in m for m in LOG),
      f"3. the move itself is logged with a count — a silent move is as hard to "
      f"reason about as a silent overwrite ({[m for m in LOG if 'prev_001' in m]})")

# ── 4. the counter increments, and prev_001 is left alone ──────────────────
first_archive = sorted(os.listdir(arch))
w(os.path.join(work, "binDumpZ.dat.gui"), "run 2 binDumpZ.dat.gui")
w(os.path.join(work, "unicones.enorm.gui"), "1000 1e-5\n1010 9e-6\n")
cfg2, (w2, _g2, in2) = prep("beta", zdump=dump, convg=convg)
check(sorted(n for n in os.listdir(work) if n.startswith("prev_"))
      == ["prev_001", "prev_002"],
      f"4. a second restart archives into prev_002/ — the same never-clobber "
      f"counter discipline resolve_case_root uses for the case dir "
      f"({sorted(n for n in os.listdir(work) if n.startswith('prev_'))})")
check(open(os.path.join(work, "prev_002", "binDumpZ.dat.prev_002")).read()
      == "run 2 binDumpZ.dat.gui",
      "4. ...prev_002/ holds run 2's dump, named for run 2")
check(sorted(os.listdir(arch)) == first_archive,
      f"4. ...and prev_001/ is byte-for-byte the folder it was: a later run has "
      f"no business adding ITS OWN outputs to a finished archive (the one thing "
      f"that may still land in an old archive is a file already NAMED for it — "
      f"see 4b, which is the opposite move) "
      f"({sorted(set(os.listdir(arch)) ^ set(first_archive))})")
check(not any("prev_001" in n
              for n in os.listdir(os.path.join(work, "prev_002"))),
      f"4. ...so prev_001's dump is NOT filed under run 2 — #26 had to leave it "
      f"bare in work/, where the next restart saw it as just another output and "
      f"archived it into prev_002/. That wart is what #30 retires; this check "
      f"pinned it and now pins its absence "
      f"({sorted(os.listdir(os.path.join(work, 'prev_002')))})")
check(not os.path.exists(os.path.join(work, "binDumpZ.dat.prev_001"))
      and os.path.isfile(os.path.join(arch, "binDumpZ.dat.prev_001")),
      "4. ...the stale link in work/ is gone while its bytes stay in prev_001/: "
      "the link existed so a restart could read that dump by a bare name, and "
      "nothing resumes from it now")
check(quoted(in2, "zdump_fn_restart") == "binDumpZ.dat.prev_002",
      f"4. the reference points at the newest one, which is the run being "
      f"resumed ({quoted(in2, 'zdump_fn_restart')!r})")

# ── 4b. a file already NAMED for an earlier archive goes back to it ────────
# The upgrade path, and the only branch that writes into an existing archive.
# #26 renamed the resumed dump IN PLACE and left it in work/, so a case that ran
# under that version still has one; a real file (not a hard link) whose name
# already says which run it belongs to is filed there rather than into this
# run's archive, which is what retires the wart instead of moving it along.
# Covered here because the acceptance run is the only other thing that exercises
# it, and an acceptance run is not a gate.
ework, _eo, _ei = seed_previous_run("epsilon")
os.makedirs(os.path.join(ework, "prev_001"), exist_ok=True)
w(os.path.join(ework, "prev_001", "unicones.enorm.prev_001"), "10 1e-3\n")
w(os.path.join(ework, "binDumpZ.dat.gui.prev_001"), "#26 left this here")
w(os.path.join(ework, "tWall.dat.prev_001"), "mine")
w(os.path.join(ework, "prev_001", "tWall.dat.prev_001"), "already taken")
cfg4b, (w4b, _g4b, _in4b) = prep(
    "epsilon", zdump=os.path.join(ework, "binDumpZ.dat.gui"))
check(os.path.isfile(os.path.join(ework, "prev_001",
                                  "binDumpZ.dat.gui.prev_001"))
      and not os.path.exists(os.path.join(ework, "binDumpZ.dat.gui.prev_001")),
      f"4b. a #26-era dump left bare in work/ is filed into the archive it is "
      f"already NAMED for, not into this run's — the name is the claim, and "
      f"re-tagging it would move that claim onto a run it did not come from "
      f"({sorted(os.listdir(os.path.join(ework, 'prev_001')))})")
check(not any("prev_001" in n for n in os.listdir(os.path.join(ework, "prev_002"))),
      f"4b. ...so this run's archive holds only this run's outputs "
      f"({sorted(os.listdir(os.path.join(ework, 'prev_002')))})")
check(os.path.isfile(os.path.join(ework, "tWall.dat.prev_001"))
      and open(os.path.join(ework, "prev_001",
                            "tWall.dat.prev_001")).read() == "already taken",
      "4b. ...and when that archive already holds the name, the file STAYS in "
      "work/ — an archive is evidence, so a collision is refused rather than "
      "resolved by overwriting one run's output with another's")
check(any("tWall.dat.prev_001" in m and "already holds" in m for m in LOG),
      f"4b. ...named in the log, like every other file this module declines to "
      f"place ({[m for m in LOG if 'tWall' in m]})")

# ── 2c. a RELATIVE restart reference follows the move as well ──────────────
# The autofill writes an absolute path, but it is not the only way the field is
# filled: a hand-written pipeline script or a re-loaded .hws can carry a bare
# name, and #25's rule 3 passes a relative value through untouched. After the
# archive that bare name resolves to nothing, so the move map is consulted for
# it too — narrowly, only for a file this run actually moved.
delta_work, _do, _di = seed_previous_run("delta")
cfg2c, (w2c, _g2c, in2c) = prep("delta", zdump="binDumpZ.dat.gui",
                                convg="unicones.enorm.gui")
ref2c = quoted(in2c, "zdump_fn_restart")
check(ref2c == "binDumpZ.dat.prev_001"
      and os.path.isfile(os.path.join(w2c, ref2c)),
      f"2c. a bare relative reference to a dump the archive just moved is "
      f"re-pointed at it, instead of naming a file that is no longer there "
      f"({ref2c!r})")
cfg2d, (w2d, _g2d, in2d) = prep("delta", zdump="../../elsewhere/w/e.dat",
                                archive_prev=False)
check(quoted(in2d, "zdump_fn_restart") == "../../elsewhere/w/e.dat",
      f"2c. ...and every OTHER relative value is still passed through "
      f"untouched — #25's rule 3, narrowed by exactly one case, not relaxed "
      f"({quoted(in2d, 'zdump_fn_restart')!r})")

# ── 5. the destructive escape, and the no-op ───────────────────────────────
gwork, goutputs, _gi = seed_previous_run("gamma")
cfg3, (w3, _g3, _in3) = prep("gamma", zdump=os.path.join(gwork, "binDumpZ.dat.gui"),
                             archive_prev=False)
check(not any(n.startswith("prev_") for n in os.listdir(gwork))
      and all(os.path.isfile(os.path.join(gwork, n)) for n in goutputs),
      "5. archive_prev=False is the explicit destructive escape: the dir is "
      "reused in place and nothing is moved (this run then writes over them, "
      "which is what the user chose)")

cfg4, (w4, _g4, _in4) = prep("fresh")
check(not os.path.isdir(os.path.join(w4, "prev_001")),
      "5. archiving a work dir with nothing to archive creates no directory — "
      "which is what lets a caller pass archive_prev without first asking "
      "whether there is anything there")

check(solver_case.case_dir_flags(solver_case.CASE_ARCHIVE) == (True, True)
      and solver_case.case_dir_flags(solver_case.CASE_IN_PLACE) == (True, False)
      and solver_case.case_dir_flags(solver_case.CASE_NEW_VERSION) == (False, False),
      "5. one answer maps to the two mechanical flags in one place, so a caller "
      "cannot archive a directory the run is not going to use")

check(case_archive.next_archive_name(os.path.dirname(work)) == "prev_003",
      f"5. next_archive_name gives the prompt the concrete directory it will "
      f"promise, from the CASE root — so a view never assembles work/ itself "
      f"({case_archive.next_archive_name(os.path.dirname(work))!r})")

try:
    solver_case.case_dir_flags("overwrite")     # a plausible misspelling
    raised = False
except ValueError:
    raised = True
check(raised,
      "5. an unknown disposition RAISES rather than resolving to (False, False) "
      "— which is a real answer (auto-version), so a typo would silently run in "
      "a directory the user did not choose")

# ── 6. case_export accounts for the archive ────────────────────────────────
case_dir = os.path.dirname(work)
w(os.path.join(case_dir, "grid", "beta.bc"), "B")
plan = case_export.plan_export(case_dir, include_restart="auto")
shipped = {i.rel for i in plan.items}
named = ({r for r, _s in plan.skipped_output} | {r for r, _s in plan.skipped_other}
         | {r for r, _s, _w in plan.skipped_unused})
on_disk = {f"work/{d}/{n}" for d in ("prev_001", "prev_002")
           for n in os.listdir(os.path.join(work, d))}
check(on_disk <= (shipped | named),
      f"6. every file in the archive is either shipped or NAMED as skipped — a "
      f"nested folder the exporter cannot see is neither, and this repo has had "
      f"that exact bug ({sorted(on_disk - (shipped | named))})")
check("work/binDumpZ.dat.prev_002" in shipped,
      f"6. the dump the resumed run restarts FROM ships, for the same reason an "
      f"un-renamed one does: input.in quotes it, and the rename keeps matching "
      f"^binDump ({sorted(r for r in shipped if 'binDump' in r)})")
check("work/prev_001/xtecp_sol_allz.dat.prev_001"
      in {r for r, _s in plan.skipped_output},
      f"6. the rest of an archive is skipped as produced-by-the-run, not shipped "
      f"— an archive is a folder of outputs by construction, and only what "
      f"input.in quotes is read back "
      f"({sorted(r for r, _s in plan.skipped_output if 'prev_' in r)})")
check(len([r for r in shipped if "binDump" in r]) == 1,
      f"6. and only ONE dump ships: a restarted case legitimately holds several, "
      f"and matching a reference by BASENAME would have carried the archived "
      f"copies too — note the hard link makes work/binDumpZ.dat.prev_002 and "
      f"work/prev_002/binDumpZ.dat.prev_002 the same bytes under two paths, so "
      f"a name-blind planner would ship 2x the largest file in the case "
      f"({sorted(r for r in shipped if 'binDump' in r)})")
check("work/prev_001/fort.11.prev_001" in {r for r, _s in plan.skipped_output},
      f"6. an archived file whose OUTPUT pattern anchors on the end of the name "
      f"(\\.plt$, ^fort\\.\\d+$) is still classified as produced-by-the-run: the "
      f"rename moves that end, so is_run_output strips the archive suffix "
      f"before matching rather than the patterns being widened for every "
      f"future name ({sorted(r for r, _s in plan.skipped_output if 'fort' in r)})")
check(f"work/prev_001/{case_run_note.RUN_NOTE_NAME}"
      in {r for r, _s in plan.skipped_output},
      f"6. and the archive's own RUN.txt is named as an output rather than "
      f"falling through to \"not recognised as a solver input\" — a false "
      f"statement about a file this toolchain wrote. It does not ship: the "
      f"package carries a case's INPUTS "
      f"({sorted(r for r, _s in plan.skipped_other if 'prev_' in r)})")

# ── 8. the archive describes itself ───────────────────────────────────────
note = case_run_note.read_run_note(arch)
check(os.path.isfile(os.path.join(arch, case_run_note.RUN_NOTE_NAME))
      and note.get("archive") == "prev_001",
      f"8. each archive carries a RUN.txt naming itself — a folder of files is "
      f"not a record of a run ({note!r})")
check(note.get("run_tag") == ".gui",
      f"8. ...it records the run TAG, which is the one thing the rename "
      f"discards: every archived name ends in .prev_001 now, so .gui/.cli would "
      f"otherwise be lost with it ({note.get('run_tag')!r})")
check(note.get("resumed_from") == "cold start",
      f"8. ...and what that run itself resumed from, read out of the input.in it "
      f"ran with — the last moment the answer exists, since prepare_case_dir "
      f"overwrites that file next ({note.get('resumed_from')!r})")
note2 = case_run_note.read_run_note(os.path.join(work, "prev_002"))
check(note2.get("convergence_interval") == SolverConfig().print_convg_per_niter
      and note.get("convergence_interval") == -1,
      f"8. ...and the INTERVAL the solver printed at, which is what turns a "
      f"last row into a bound instead of a quietly wrong number: the run "
      f"reached at least last_iteration and fewer than last_iteration + this. "
      f"Read from the same input.in as resumed_from, so run 1 — whose work dir "
      f"held no real input.in — reports -1 rather than a made-up interval "
      f"({note.get('convergence_interval')!r} then "
      f"{note2.get('convergence_interval')!r})")
check(note.get("last_iteration") == 30 and note.get("convergence_rows") == 3,
      f"8. ...and how far it got, from the last row of its own convergence "
      f"history: the solver prints Global Iteration count to stdout, which by "
      f"archive time is gone ({note.get('last_iteration')!r}, "
      f"{note.get('convergence_rows')!r} row(s))")
note_text = open(os.path.join(arch, case_run_note.RUN_NOTE_NAME)).read()
check("reached at least" in note_text
      and "not the" in note_text and "final" in note_text
      and "-1 in either field" in note_text,
      "8. ...and the FILE says which number it is: the last recorded row, not "
      "the solver's final count, bounded above by the interval, with -1 called "
      "out as 'could not determine' rather than 0. A run that reached 2000 "
      "leaves 1990 here (measured), so a field labelled 'final' would be a "
      "small lie in the one number a user reads")
check(note.get("zone_dump") == "binDumpZ.dat.prev_001",
      f"8. ...and which file in it is the zone dump, so a restart chooser does "
      f"not have to know the naming rule ({note.get('zone_dump')!r})")
check(sorted(note.get("files", []))
      == sorted(archive_name(n, "prev_001") for n in outputs),
      f"8. ...with the folder's contents listed, so the record survives being "
      f"read on its own ({sorted(note.get('files', []))})")
check(case_run_note.read_run_note(os.path.join(work, "prev_002")).get(
          "resumed_from") == "binDumpZ.dat.prev_001"
      and case_run_note.read_run_note(os.path.join(work, "prev_002")).get(
          "last_iteration") == 1010,
      f"8. run 2's note reports what run 2 resumed from and where it got to — "
      f"which is the chain a user follows back through the archives "
      f"({case_run_note.read_run_note(os.path.join(work, 'prev_002'))!r})")
w(os.path.join(tmp, "empty.enorm"), "\n\n")
check(case_run_note.last_iteration(os.path.join(tmp, "empty.enorm")) == (-1, 0)
      and case_run_note.last_iteration(os.path.join(tmp, "nope")) == (-1, 0),
      f"8. an unreadable or empty convergence history reports -1, NOT 0: the "
      f"solver really prints 0 for a cold start, so 'we could not tell' must "
      f"not be spelled the same way as 'it had not started' "
      f"({case_run_note.last_iteration(os.path.join(tmp, 'empty.enorm'))})")
unreadable = os.path.join(tmp, "unreadable")
w(os.path.join(unreadable, "input.in"), '   zdump_fn_restart  "x.dat"\n')
os.chmod(os.path.join(unreadable, "input.in"), 0)
got_unreadable = case_run_note.resumed_from(unreadable)
os.chmod(os.path.join(unreadable, "input.in"), 0o644)
check(got_unreadable is None
      and case_run_note.resumed_from(os.path.join(tmp, "no_work_dir")) == "",
      f"8. an input.in that cannot be READ reports None, and only a work dir "
      f"with no input.in at all reports a cold start — 'we could not tell' "
      f"rendered as 'cold start' would be a POSITIVE FALSE CLAIM in the one "
      f"field #30 exists to provide, on a case whose history the reader cannot "
      f"check any other way ({got_unreadable!r})")
check(case_run_note._resumed_field(None).startswith("unknown")
      and case_run_note._resumed_field("") == "cold start"
      and case_run_note._resumed_field("d.dat") == "d.dat",
      "8. ...and the three states reach the file as three distinct strings")
check(case_run_note.read_run_note(os.path.join(work, "no_such_archive")) == {},
      "8. and an archive with no note (one written before #30) reads as empty "
      "rather than raising — a reader over a case's history meets both")

# ── 9. two runs' outputs in one work dir: refuse, do not destroy ──────────
# #42. Every solver output carries a run tag saying which HOST produced it, and
# archiving REPLACES that tag (#30's one-naming-scheme rule), so `x.cli` and
# `x.gui` want ONE archived name. The move was unguarded: the second landed on
# the first and an entire run's field output and convergence history were gone
# with no message, the survivor decided by directory listing order. Reachable
# without misuse — run a case headless (.cli), reopen it in the GUI and answer
# Overwrite (.gui joins it), then restart (a restart archives).
#
# The property pinned is what the USER can observe, not the name mapping: the
# mapping's return value was always right, and the defect is that its caller
# never asked the question.
zwork, zoutputs, zinputs = seed_previous_run("zeta")
cli_twins = ["binDumpZ.dat.cli", "unicones.enorm.cli", "xtecp_sol_allz.dat.cli"]
for name in cli_twins:
    w(os.path.join(zwork, name), "headless run: " + name)
# input.in is left out on purpose: it is the file prepare_case_dir WRITES for
# the run it is preparing, so it is the one thing in a work dir that is meant to
# change. Everything else — both runs' outputs and the staged inputs beside them
# — must come out byte-identical.
before = {n: open(os.path.join(zwork, n)).read()
          for n in zoutputs + cli_twins
          + [i for i in zinputs if i != "input.in"]}
cfg9, (w9, _g9, in9) = prep("zeta", zdump=os.path.join(zwork, "binDumpZ.dat.gui"))

after = {n: (open(os.path.join(zwork, n)).read()
             if os.path.isfile(os.path.join(zwork, n)) else None)
         for n in before}
check(after == before,
      f"9. every file of BOTH runs is still where it was, with its own bytes — "
      f"an archive may not cost a solve, so a collision refuses wholesale "
      f"rather than moving the pairs that happen not to clash "
      f"({[n for n in before if after[n] != before[n]]})")
check(not any(n.startswith("prev_") for n in os.listdir(zwork)),
      f"9. ...and nothing was half-archived: the check runs BEFORE the first "
      f"move, so the refusal is a no-op the user can retry after tidying up "
      f"({sorted(n for n in os.listdir(zwork) if n.startswith('prev_'))})")
check(any("binDumpZ.dat.cli" in m and "binDumpZ.dat.gui" in m
          and "binDumpZ.dat.prev_001" in m for m in LOG),
      f"9. the zone dump is protected by the same rule as everything else — the "
      f"largest and most irreplaceable file in a case, and the one a restart "
      f"reads back — and the name the pair WANTED is the concrete one the "
      f"counter would have given them, not a prev_NNN template: detecting the "
      f"collision needs no counter (a pair collides under every suffix), but "
      f"saying which name they fought over does "
      f"({[m for m in LOG if 'binDump' in m and 'WARNING' in m]})")
check(any("unicones.enorm.cli" in m and "unicones.enorm.gui" in m for m in LOG),
      f"9. ...and so is the convergence history, or the record of how far a run "
      f"got is lost while its field output survives "
      f"({[m for m in LOG if 'unicones' in m and 'WARNING' in m]})")
check(any(".gui" in m and ".cli" in m and "tag" in m for m in LOG),
      f"9. the message says WHY they collided — archiving drops the run tag, "
      f"which is invisible from the file names alone. A message that only says "
      f"'collision' leaves the user with nothing to do "
      f"({[m for m in LOG if 'WARNING' in m]})")
check(any("nothing was archived" in m and "work/" in m for m in LOG),
      f"9. ...and what to do about it, in the same user log every other archive "
      f"decision appears in ({[m for m in LOG if 'nothing was archived' in m]})")
check(any("writes over" in m and "resuming from" in m for m in LOG),
      f"9. ...without softening what the refusal leaves behind: the ARCHIVE "
      f"destroyed nothing, but the run that follows carries one of the two tags "
      f"and overwrites the half of every pair that shares it — the dump it "
      f"resumes from included. 'writes beside them' would be the reassuring "
      f"half-truth this repo keeps `resumed_from`'s None and \"\" apart to "
      f"avoid ({[m for m in LOG if 'nothing was archived' in m]})")
check(os.path.isfile(in9) and os.path.abspath(w9) == os.path.abspath(zwork),
      "9. the run that triggered the archive still makes progress or fails on "
      "its own terms — a refusal to archive is not a refusal to work (same "
      "shape as the exhausted-counter refusal, which also returns an empty map "
      "every caller already handles)")

# Negative control 1: the guard is what saved those files, not something else.
# Injected by taking the QUESTION away — the shipped code's exact shape — and
# the same seeded state then really does lose a run's output.
ywork, youtputs, _yi = seed_previous_run("eta")
for name in cli_twins:
    w(os.path.join(ywork, name), "headless run: " + name)
_real_collisions = case_archive.archive_name_collisions
case_archive.archive_name_collisions = lambda *a, **k: ()
try:
    prep("eta", zdump=os.path.join(ywork, "binDumpZ.dat.gui"))
finally:
    case_archive.archive_name_collisions = _real_collisions
yarch = os.path.join(ywork, "prev_001")
survivors = [n for n in cli_twins + youtputs
             if os.path.isfile(os.path.join(ywork, n))
             or os.path.isfile(os.path.join(yarch, n))]
check(os.path.isdir(yarch) and not survivors
      and len(os.listdir(yarch)) < len(youtputs) + len(cli_twins) + 1,
      f"9b. (injection) with the collision question removed, the archive moves "
      f"one run's file on top of the other's and {len(youtputs) + len(cli_twins)} "
      f"files come out as {len(os.listdir(yarch)) - 1} — the destruction this "
      f"guard exists to refuse, measured rather than argued "
      f"({sorted(os.listdir(yarch))})")

# Negative control 2: a fix that simply stopped archiving would pass everything
# above. One run's outputs still archive exactly as they did (checks 1-2 are the
# full version of this; here it is the CONTRAST that matters).
twork, toutputs, _ti = seed_previous_run("theta")
prep("theta", zdump=os.path.join(twork, "binDumpZ.dat.gui"))
tarch = os.path.join(twork, "prev_001")
check(os.path.isdir(tarch)
      and sorted(os.listdir(tarch)) == sorted(
          [archive_name(n, "prev_001") for n in toutputs]
          + [case_run_note.RUN_NOTE_NAME]),
      f"9c. a work dir holding ONE run's outputs still archives normally — the "
      f"refusal is a collision guard, not a switch that turned archiving off, "
      f"and a user who has only ever run one host pays nothing "
      f"({sorted(os.listdir(tarch)) if os.path.isdir(tarch) else 'no archive'})")

# The mapping's own answer, asked directly: the collision is a property of the
# SET, so it is reported per wanted name with every source that wants it, and a
# clean set costs one dict build (no stat, no listdir).
from app.services.case_files import (                             # noqa: E402
    ARCHIVE_SUFFIX_PLACEHOLDER, archive_name_collisions,
)

check(archive_name_collisions(
          ["a.dat.gui", "a.dat.cli", "fort.11", "b.dat.gui"], "prev_001")
      == (("a.dat.prev_001", ("a.dat.cli", "a.dat.gui")),)
      and archive_name_collisions(["a.dat.gui", "fort.11"],
                                  ARCHIVE_SUFFIX_PLACEHOLDER) == (),
      f"9d. (shape only) the question is answered once over the whole set, "
      f"naming the wanted name and every source that wants it — a per-move "
      f"check could only see a collision from one side, by which time the other "
      f"file has moved. This one pins the mapping's CONTRACT and would have "
      f"passed on the shipped code, where the function was right and nobody "
      f"called it; 9/9b are the checks that would have failed "
      f"({archive_name_collisions(['a.dat.gui', 'a.dat.cli'], 'prev_001')})")

# ── 7. the prompt ──────────────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication, QMessageBox      # noqa: E402
from app.views import case_dir_dialog                      # noqa: E402

_app = QApplication.instance() or QApplication([])
# The dialog refuses to show anything headless (a modal there blocks forever with
# nobody to answer it) — which is the branch under test, so it is turned off here
# deliberately rather than worked around.
case_dir_dialog.is_headless = lambda: False

_seen = {}


def drive(pick):
    """Show the real dialog and click the button ``pick`` selects."""
    def fake_exec(box):
        _seen["box"] = box
        btn = pick(box)
        if btn is not None:
            btn.click()
        return 0
    QMessageBox.exec = fake_exec


def by_text(frag):
    return lambda box: next((b for b in box.buttons() if frag in b.text()), None)


# #31 removed the restart BRANCH of this prompt, and the checks below are the
# inverted versions of the ones that used to pin it. Once the start point is
# picked from the case's own history there is nothing left to ask: "same
# directory, archive the previous outputs" is the only coherent answer, so
# `solver_ctrl._resolve_case_disposition` returns it without showing anything
# (pinned in tests/test_restart_chooser.py check 10, with the log line that
# replaces the confirmation). The archive MECHANISM above is untouched — what
# changed is who chooses it.
import inspect                                                    # noqa: E402

check("restart" not in inspect.signature(
          case_dir_dialog.ask_case_disposition).parameters,
      f"7. the prompt no longer takes a restart flag at all — a branch nothing "
      f"can reach reads as a working feature, so it is gone rather than left as "
      f"an answer the dialog can no longer give "
      f"({list(inspect.signature(case_dir_dialog.ask_case_disposition).parameters)})")

drive(by_text("Overwrite"))
got = case_dir_dialog.ask_case_disposition(None, "beta", case_dir)
labels = [b.text() for b in _seen["box"].buttons()]
check(got == solver_case.CASE_IN_PLACE
      and not any("Continue Here" in t or "archive" in t.lower() for t in labels),
      f"7. what is left is the genuinely ambiguous NON-restart question — two "
      f"answers and Cancel, no archive option for a run that is not resuming "
      f"anything ({labels})")
check(_seen["box"].buttonRole(
          next(b for b in _seen["box"].buttons() if "Overwrite" in b.text()))
      == QMessageBox.ButtonRole.DestructiveRole,
      "7. ...with the overwrite still labelled destructive")

drive(by_text("New Versioned Dir"))
check(case_dir_dialog.ask_case_disposition(None, "beta", case_dir)
      == solver_case.CASE_NEW_VERSION,
      "7. the preserving answer still comes back")
check(_seen["box"].defaultButton() is not None
      and "New Versioned" in _seen["box"].defaultButton().text(),
      "7. ...and is still the default")

drive(lambda box: box.button(QMessageBox.StandardButton.Cancel))
check(case_dir_dialog.ask_case_disposition(None, "beta", case_dir) is None,
      "7. Cancel still cancels")

# The window dismissed with its close button / Esc: clickedButton() is None, and
# an unmatched answer used to fall through to CASE_NEW_VERSION — i.e. dismissing
# the question STARTED A SOLVER RUN. Same rule as case_dir_flags refusing an
# unknown disposition, from the other side.
drive(lambda box: None)
check(case_dir_dialog.ask_case_disposition(None, "beta", case_dir) is None,
      "7. dismissing the window (no button clicked) cancels — it must not fall "
      "through to a disposition and launch a run nobody chose")

solver_case.repo_root = _real_repo_root
shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED")
    for m in _FAILS:
        print("  - " + m)
    os._exit(1)
print("\nRESULT: ALL PASS")
os._exit(0)
