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

 1. the outputs move, the run's own staged inputs stay;
 2. the resumed run READS the archived dump — the reference is
    ``prev_001/binDumpZ.dat.gui`` and it resolves from the work dir;
 2b. …and that is not free: without the moved mapping the same reference comes
    out as this machine's absolute path, i.e. the mechanism is load bearing;
 2c. a RELATIVE reference (a hand-written script, a re-loaded .hws) follows the
    move too — #25's "a relative value is left alone" is narrowed by exactly the
    one file this run moved, and by nothing else;
 3. a file neither list recognises stays put and is NAMED in the log;
 4. the counter increments — a second restart archives into prev_002/;
 5. the destructive escape still overwrites in place (archive_prev=False), and
    archiving a dir with nothing to archive creates no directory at all;
 6. ``case_export`` accounts for ``work/prev_001/`` — every file in it is either
    shipped or named as skipped, never silently omitted (the exporter's own gate
    sees an archive too: ``test_case_export.py`` check 16);
 7. the prompt's restart branch offers the archiving option, makes it the
    default, says where the outputs go, and keeps the destructive one and Cancel.

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
  fix, and it is why the dump is renamed in place instead.
* **it must DIFFER from the solver's own output dump name.** That name is
  ``binDumpZ.dat`` + the ``-t`` tag, i.e. exactly what a GUI restart resumes
  from, so before this change every same-folder restart rewrote its own restart
  point (measured: the source file's checksum changes). The issue described that
  as a crash-window risk; it is in fact what happened on every run.

One genuine residue, measured and out of scope: a reference into ANOTHER case
dir (#25's ``../../own/work/binDumpZ.dat.gui``, which auto-versioning produces)
does resume correctly — iteration 1000, source untouched — but leaves one empty
``binDumpZ.dat.0`` behind in the work dir from the same derivation. Harmless,
not fixed here.

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
from app.services import case_archive, case_export, solver_case   # noqa: E402

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


def seed_previous_run(case, extra=()):
    """A work/ as a finished run leaves it: this run's staged inputs, plus the
    outputs it produced. Names taken from what the solver really writes."""
    work = os.path.join(repo, "results", "solver", case, "work")
    outputs = ["binDumpZ.dat.gui", "unicones.enorm.gui",
               "xtecp_sol_allz.dat.gui", "probe_data.gui", "fort.11",
               "tWall.dat", "mesh_tecplot.plt"]
    inputs = ["input.in", "phi.dat", f"{case}.bc.def", "userbc.so"]
    for name in outputs + inputs + list(extra):
        w(os.path.join(work, name), name)
    w(os.path.join(repo, "results", "solver", case, "grid", f"{case}.grid"), "G")
    return work, outputs, inputs


# ── 1/2/3. the archive itself, through the real prepare_case_dir ───────────
work, outputs, inputs = seed_previous_run("beta", extra=["notes.txt"])
dump = os.path.join(work, "binDumpZ.dat.gui")
convg = os.path.join(work, "unicones.enorm.gui")
cfg1, (w1, _g1, in1) = prep("beta", zdump=dump, convg=convg)

check(os.path.abspath(w1) == os.path.abspath(work),
      "1. (precondition) the run continues in the SAME case dir — that is what "
      "a restart asked for")
arch = os.path.join(work, "prev_001")
archived_expected = sorted(n for n in outputs if n != "binDumpZ.dat.gui")
check(sorted(os.listdir(arch)) == archived_expected,
      f"1. every one of the previous run's outputs moved into work/prev_001/ — "
      f"except the dump this run resumes from "
      f"({sorted(os.listdir(arch)) if os.path.isdir(arch) else 'no such dir'})")
check(os.path.isfile(os.path.join(work, "binDumpZ.dat.gui.prev_001"))
      and not os.path.exists(os.path.join(work, "binDumpZ.dat.gui")),
      f"1. the dump stays directly in work/, RENAMED — the solver reads a "
      f"restart source only by a bare name in its own cwd (a dump moved into "
      f"prev_001/ makes it derive binDumpZ.dat.prev_001/binDumpZ.0 and die), "
      f"and the new name is what stops this run's own dump landing on top of it "
      f"({sorted(n for n in os.listdir(work) if n.startswith('binDump'))})")
check(all(not os.path.exists(os.path.join(work, n)) for n in outputs),
      "1. ...MOVED or renamed, never copied — the zone dump is the largest file "
      "in a case, and two of them would leave nothing recording their "
      "relationship")
check(all(os.path.isfile(os.path.join(work, n)) for n in inputs),
      f"1. the run's own staged inputs stay in work/ — input.in, the BC table, "
      f"the phase field and a type-11 BC .so. Archive them and the resumed run "
      f"restarts into nothing "
      f"({[n for n in inputs if not os.path.isfile(os.path.join(work, n))]})")

ref = quoted(in1, "zdump_fn_restart")
check(ref == "binDumpZ.dat.gui.prev_001",
      f"2. the restart reference follows the dump to its new name ({ref!r})")
check("/" not in ref and os.path.isfile(os.path.join(w1, ref)),
      "2. ...and it is a BARE name that resolves in the work dir the solver "
      "runs in. Bare is not tidiness: measured on the real binary, any "
      "reference with a directory component makes the solver build a per-zone "
      "path out of it (prev_001/... -> binDumpZ.dat.prev_001/binDumpZ.0) and "
      "the run dies with \"Can't open file\"")
check(ref != "binDumpZ.dat.gui",
      "2. ...and it differs from the name the solver writes its OWN dump to "
      "(binDumpZ.dat + the -t tag), which is the whole hazard: measured, a "
      "same-name restart rewrites the file it resumed from")
check(quoted(in1, "convg_fn_restart") == "prev_001/unicones.enorm.gui",
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

check(os.path.isfile(os.path.join(work, "notes.txt")),
      "3. a file neither the output list nor the staged-input list recognises "
      "is LEFT where it is — nobody classified it, so nobody moves it")
check(any("notes.txt" in m and "not a recognised" in m for m in LOG),
      f"3. ...and it is named in the log rather than quietly ignored "
      f"({[m for m in LOG if 'notes.txt' in m]})")
check(any("prev_001/" in m and "previous outputs" in m for m in LOG),
      f"3. the move itself is logged with a count — a silent move is as hard to "
      f"reason about as a silent overwrite ({[m for m in LOG if 'prev_001' in m]})")

# ── 4. the counter increments ──────────────────────────────────────────────
for name in ["binDumpZ.dat.gui", "unicones.enorm.gui"]:
    w(os.path.join(work, name), "run 2 " + name)
cfg2, (w2, _g2, in2) = prep("beta", zdump=dump, convg=convg)
check(sorted(n for n in os.listdir(work) if n.startswith("prev_"))
      == ["prev_001", "prev_002"],
      f"4. a second restart archives into prev_002/ — the same never-clobber "
      f"counter discipline resolve_case_root uses for the case dir "
      f"({sorted(n for n in os.listdir(work) if n.startswith('prev_'))})")
check(open(os.path.join(work, "binDumpZ.dat.gui.prev_002")).read()
      == "run 2 binDumpZ.dat.gui",
      "4. ...the dump kept bare in work/ is run 2's, tagged with the archive it "
      "belongs to")
check(os.path.isfile(os.path.join(work, "prev_002", "binDumpZ.dat.gui.prev_001"))
      and not os.path.exists(os.path.join(work, "binDumpZ.dat.gui.prev_001")),
      f"4. ...and the dump the PREVIOUS restart kept bare is now archived: it is "
      f"an output like any other once nothing resumes from it, so no special "
      f"case is needed to retire it "
      f"({sorted(os.listdir(os.path.join(work, 'prev_002')))})")
check(quoted(in2, "zdump_fn_restart") == "binDumpZ.dat.gui.prev_002",
      f"4. the reference points at the newest one, which is the run being "
      f"resumed ({quoted(in2, 'zdump_fn_restart')!r})")

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
check(ref2c == "binDumpZ.dat.gui.prev_001"
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
check("work/binDumpZ.dat.gui.prev_002" in shipped,
      f"6. the dump the resumed run restarts FROM ships, for the same reason an "
      f"un-renamed one does: input.in quotes it, and the rename keeps matching "
      f"^binDump ({sorted(r for r in shipped if 'binDump' in r)})")
check("work/prev_001/xtecp_sol_allz.dat.gui" in {r for r, _s in plan.skipped_output},
      f"6. the rest of an archive is skipped as produced-by-the-run, not shipped "
      f"— an archive is a folder of outputs by construction, and only what "
      f"input.in quotes is read back "
      f"({sorted(r for r, _s in plan.skipped_output if 'prev_' in r)})")
check(len([r for r in shipped if "binDump" in r]) == 1,
      f"6. and only ONE dump ships: a restarted case legitimately holds several, "
      f"and matching a reference by BASENAME would have carried the archived "
      f"copies too ({sorted(r for r in shipped if 'binDump' in r)})")

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


drive(by_text("Continue Here"))
got = case_dir_dialog.ask_case_disposition(None, "beta", case_dir, True)
box = _seen["box"]
labels = [b.text() for b in box.buttons()]
check(got == solver_case.CASE_ARCHIVE,
      f"7. the restart branch offers a same-directory option and it returns the "
      f"ARCHIVING disposition ({got!r}, buttons {labels})")
check(box.defaultButton() is not None
      and "Continue Here" in box.defaultButton().text()
      and box.buttonRole(box.defaultButton()) == QMessageBox.ButtonRole.AcceptRole,
      f"7. ...and it is the DEFAULT and the accept role — the destructive option "
      f"was the only thing that stayed in the folder, which is the bug "
      f"({box.defaultButton().text() if box.defaultButton() else None!r})")
info = box.informativeText()
check("prev_003" in info and "work/" in info,
      f"7. the prompt says where the previous outputs go, naming the concrete "
      f"directory ({info!r})")
check("restart" in info.lower() or "RESTARTS" in info,
      "7. ...and that this is a restart at all — the old dialog said nothing "
      "about it, so the safe reading was not available to the user")

drive(by_text("Overwrite in Place"))
check(case_dir_dialog.ask_case_disposition(None, "beta", case_dir, True)
      == solver_case.CASE_IN_PLACE,
      "7. the destructive escape survives: a user who wants a clean slate in "
      "place still has it")
check(_seen["box"].buttonRole(
          next(b for b in _seen["box"].buttons() if "Overwrite" in b.text()))
      == QMessageBox.ButtonRole.DestructiveRole,
      "7. ...still labelled destructive")

drive(by_text("New Versioned Dir"))
check(case_dir_dialog.ask_case_disposition(None, "beta", case_dir, True)
      == solver_case.CASE_NEW_VERSION,
      "7. and the versioned dir is still reachable from the restart branch")

drive(lambda box: box.button(QMessageBox.StandardButton.Cancel))
check(case_dir_dialog.ask_case_disposition(None, "beta", case_dir, True) is None,
      "7. Cancel still cancels")

drive(by_text("Overwrite"))
got = case_dir_dialog.ask_case_disposition(None, "beta", case_dir, False)
labels = [b.text() for b in _seen["box"].buttons()]
check(got == solver_case.CASE_IN_PLACE
      and not any("Continue Here" in t for t in labels),
      f"7. the NON-restart branch is unchanged — two answers and Cancel, no "
      f"archive option for a run that is not resuming anything ({labels})")
check(_seen["box"].defaultButton() is not None
      and "New Versioned" in _seen["box"].defaultButton().text(),
      "7. ...and its default is still the preserving one")

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
