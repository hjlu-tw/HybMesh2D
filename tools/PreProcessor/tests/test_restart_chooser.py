#!/usr/bin/env python3
"""The restart point is picked from the case's own history, not typed as a path.

#31, USER-REQUESTED (2026-08-21), blocked by #30 (the ``RUN.txt`` this reads).
After restarting once, the next run is one of two intentions and a path field
expressed neither: **continue further** from the newest dump, or **re-run the
same leg** from the dump the last run itself resumed from. The panel offered a
``Restart`` tick plus a free-text ``zdump_fn_restart`` autofilled from a fixed
name in ``work/`` only — blind to the ``work/prev_<NNN>/`` archives #26 creates —
so "re-run the same leg" meant remembering which file that was.

Pinned here, against the real ``prepare_case_dir`` (so the archives are the ones
the toolchain really makes), the real ``RestartChooser`` widget on the offscreen
platform, and the real ``SolverControllerMixin``:

 1. a case with no history offers Cold start alone; the rows are DERIVED, so the
    same call after a run returns more of them with nothing invalidated;
 2. the newest un-archived dump in ``work/`` is the "latest" row, and its
    iteration count comes from the convergence history beside it;
 3. the archives are rows, newest first, each carrying the iteration count and
    timestamp from its own ``RUN.txt``;
 4. an archive with NO ``RUN.txt`` (one from before #30) still appears, with no
    iteration count rather than being hidden;
 5. the row the previous run resumed from is marked — by BASENAME, because the
    bare-named hard link that reference pointed at is retired by the next
    archive while the bytes keep that name inside ``prev_<NNN>/``;
 6. …and a cold-started previous run marks the Cold row, while an unreadable
    ``input.in`` marks nothing (three states, per ``case_run_note``);
 7. the bare-named hard link in ``work/`` is NOT a second "latest" row — it is
    the same bytes as an archive row under a second name;
 8. the widget writes the model: a row sets ``restart`` + both paths, Cold start
    clears both and unticks restart, and "Other file…" keeps an arbitrary path
    (a dump in another case dir, which #25 supports);
 9. a restart whose source does not exist is refused by ``_validate`` — naming
    the field AND the missing path — before the solver is launched, for both
    routes that still reach that state ("Other file…" and a restored workspace);
10. Run does not raise the case-dir modal on a restart: the disposition is the
    archiving one and it is said in the log, naming the concrete directory. The
    non-restart path still asks, and Run All still auto-versions without asking;
11. a restart source that lives INSIDE an archive is quoted as a bare name in
    ``work/``, which is the only shape the solver can read (#30, measured);
12. the pick reaches the MODEL and not only the panel — through the real
    ``AppController``, because every other check here reads the panel and would
    pass with the model left holding the previous answer.

Property 11 is why this is more than a view. #26 measured that the solver
derives a per-zone path from the reference and dies on anything with a directory
component in it, so the chooser offering an older archive would produce a run
that fails inside ``unicones`` — the very class of failure property 9 exists to
move into the GUI. The archive already keeps a bare-named hard link for the dump
the run resumes from; re-using that mechanism for a dump the USER picked out of
an older archive is what makes "re-run the same leg" runnable.

Two of these were written after the mechanism and then MEASURED against its
absence, rather than asserted:

* deleting the ``panel_edited`` hand-back in ``undo_ctrl._wire_widget_edits``
  fails check 12 alone (measured: 1 FAIL, the other 39 green) — that traversal
  knows spin boxes, combos, line edits and checkable buttons, and the chooser
  rebuilds its rows after it has run, so without the hand-back the panel edits
  and the model keeps the previous answer;
* check 11 was RED before ``bare_link_for_archived_dump`` existed, with the
  reference coming out as ``prev_001/binDumpZ.dat.prev_001`` — the exact shape
  #26 measured the solver dying on.

Blind spots, named rather than papered over: nothing here runs ``unicones``, so
property 11 pins the reference's SHAPE against the shape #30's acceptance run
measured, not the solver's acceptance of it; and check 8 drives the widget's own
verbs rather than a mouse, so a row the user cannot physically click would still
pass.

Run:  python3 tools/PreProcessor/tests/test_restart_chooser.py
"""
import os
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
    print("TIMEOUT: test_restart_chooser.py exceeded its budget", flush=True)
    os._exit(1)


_wd = threading.Timer(180, _watchdog)
_wd.daemon = True
_wd.start()

from app.models.solver_config import SolverConfig                   # noqa: E402
from app.services import restart_points as rp                       # noqa: E402
from app.services import solver_case                                # noqa: E402
from app.services.case_files import RUN_NOTE_NAME                   # noqa: E402

tmp = tempfile.mkdtemp(prefix="hybmesh_restart_chooser_")
repo = os.path.join(tmp, "repo")
mesh = os.path.join(repo, "m")


def w(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


for ext in (".vrt", ".cel", ".bnd"):
    w(mesh + ext, "mesh")

# `case_root_for` lives in solver_case (which owns a case's layout) and
# restart_points re-exports it, so ONE patch redirects every caller.
solver_case.repo_root = lambda: repo

LOG = []

# One row every 10 iterations, which is what makes RUN.txt's number a BOUND
# rather than the final count (#30).
CONVG = "".join(f"{n}   1.5e-16  5.5e-03\n" for n in range(10, 1000, 10))
INPUT_IN = '   print_convg_per_niter\t10\n'


def case_root(case):
    return os.path.join(repo, "results", "solver", case)


def seed_run(case, *, resumed=""):
    """A ``work/`` as a finished run leaves it: this run's staged inputs plus the
    outputs it produced. ``resumed`` is what that run itself restarted from, i.e.
    what its own ``input.in`` quotes."""
    work = os.path.join(case_root(case), "work")
    for name in ("binDumpZ.dat.gui", "xtecp_sol_allz.dat.gui", "fort.11"):
        w(os.path.join(work, name), name)
    w(os.path.join(work, "unicones.enorm.gui"), CONVG)
    w(os.path.join(work, "input.in"), INPUT_IN + (
        f'   zdump_fn_restart\t"{resumed}"\n' if resumed else ""))
    w(os.path.join(case_root(case), "grid", f"{case}.grid"), "G")
    return work


def prep(case, *, zdump="", convg="", archive_prev=True, restart=True):
    LOG.clear()
    cfg = SolverConfig()
    cfg.case_name = case
    cfg.input_vrt_file, cfg.input_cel_file, cfg.input_bnd_file = (
        mesh + ".vrt", mesh + ".cel", mesh + ".bnd")
    cfg.restart, cfg.zdump_fn_restart, cfg.convg_fn_restart = restart, zdump, convg
    return cfg, solver_case.prepare_case_dir(
        cfg, log=LOG.append, overwrite=True, archive_prev=archive_prev)


def quoted(input_in, key):
    with open(input_in) as f:
        for line in f:
            parts = line.split()
            if parts[:1] == [key]:
                return line.split('"')[1] if '"' in line else parts[1]
    return None


def keys(points):
    return [p.key for p in points]


def by_key(points, key):
    return next((p for p in points if p.key == key), None)


# ── 1. no history: Cold start alone, and the answer is derived ─────────────
fresh = case_root("fresh")
os.makedirs(os.path.join(fresh, "work"), exist_ok=True)
rows = rp.list_restart_points(fresh)
check(keys(rows) == [rp.COLD],
      f"1. a case with no history offers Cold start and nothing else ({keys(rows)})")
check(rows[0].selectable and rows[0].zdump == "",
      "1. ...and Cold start is pickable while naming no file")
check(rp.list_restart_points(os.path.join(repo, "nope")) == rows[:1]
      or keys(rp.list_restart_points(os.path.join(repo, "nope"))) == [rp.COLD],
      "1. a case directory that does not exist answers the same way rather than "
      "raising — the panel asks before a case has ever been run")

# ── 2. the latest result, with its iteration count ────────────────────────
work = seed_run("alpha")
rows = rp.list_restart_points(case_root("alpha"))
latest = by_key(rows, rp.LATEST)
check(keys(rows) == [rp.COLD, rp.LATEST],
      f"2. the newest un-archived dump in work/ is offered ({keys(rows)})")
check(latest is not None
      and os.path.basename(latest.zdump) == "binDumpZ.dat.gui"
      and os.path.isabs(latest.zdump),
      f"2. ...as an ABSOLUTE path, which is what the model holds (#25) "
      f"({latest.zdump if latest else None!r})")
check(latest.convg.endswith("unicones.enorm.gui"),
      f"2. ...paired with the convergence history of the SAME run ({latest.convg!r})")
check(latest.stamp and latest.stamp[:2] == "20",
      f"2. ...and WHEN it ran, from the dump's own mtime — an archive records "
      f"that when its files move and nothing has moved this one yet, so the "
      f"newest leg would otherwise be the one row with no date ({latest.stamp!r})")
check(latest.iteration == 990 and latest.interval == 10,
      f"2. ...and its iteration count is the last ROW of that history, with the "
      f"print interval beside it so the number reads as a bound "
      f"({latest.iteration}, every {latest.interval})")

# ── 3./5. archives, newest first, marked ──────────────────────────────────
# Two real legs: restart from the dump, which archives the previous run.
dump = os.path.join(work, "binDumpZ.dat.gui")
cfg, (w1, _g1, in1) = prep("alpha", zdump=dump,
                           convg=os.path.join(work, "unicones.enorm.gui"))
ref1 = quoted(in1, "zdump_fn_restart")
# A second finished run in the same work dir, resuming from what run 1 did.
w(os.path.join(work, "binDumpZ.dat.gui"), "run2 dump")
w(os.path.join(work, "unicones.enorm.gui"), CONVG)
w(os.path.join(work, "input.in"), INPUT_IN + f'   zdump_fn_restart\t"{ref1}"\n')
rows = rp.list_restart_points(case_root("alpha"))
check(keys(rows) == [rp.COLD, rp.LATEST, "prev_001"],
      f"3. the archived leg is a row, after the latest result ({keys(rows)})")
a1 = by_key(rows, "prev_001")
check(a1.iteration == 990 and a1.interval == 10,
      f"3. ...with the iteration count from its OWN RUN.txt ({a1.iteration})")
check(a1.stamp and a1.tag == ".gui",
      f"3. ...and when it ran, plus the run tag the rename discards "
      f"({a1.stamp!r}, {a1.tag!r})")
check(a1.zdump.endswith(os.path.join("prev_001", "binDumpZ.dat.prev_001")),
      f"3. ...pointing at the dump INSIDE the archive ({a1.zdump!r})")
check(a1.resumed_by_last and not by_key(rows, rp.LATEST).resumed_by_last
      and not by_key(rows, rp.COLD).resumed_by_last,
      "5. the row the previous run resumed from is the marked one — and only it")

# A third leg, so an archive that is NOT the newest is the marked one — this is
# "re-run the same leg", the intention #31 exists for.
cfg2, (w2, _g2, in2) = prep("alpha", zdump=a1.zdump, convg=a1.convg)
w(os.path.join(work, "binDumpZ.dat.gui"), "run3 dump")
w(os.path.join(work, "unicones.enorm.gui"), CONVG)
w(os.path.join(work, "input.in"),
  INPUT_IN + f'   zdump_fn_restart\t"{quoted(in2, "zdump_fn_restart")}"\n')
rows = rp.list_restart_points(case_root("alpha"))
check(keys(rows) == [rp.COLD, rp.LATEST, "prev_002", "prev_001"],
      f"3. archives are newest FIRST ({keys(rows)})")
check(by_key(rows, "prev_001").resumed_by_last
      and not by_key(rows, "prev_002").resumed_by_last,
      "5. an OLDER archive is the marked row when that is what the last run "
      "resumed from — the case the path field made the user remember")
# The bare link that reference NAMES is retired by a later archive, while the
# bytes keep that basename inside prev_001/ — so the mark cannot be by path or
# by inode. Removed here directly, because that is the state a third restart
# leaves and the property has to hold in it.
os.remove(os.path.join(work, "binDumpZ.dat.prev_001"))
_after = rp.list_restart_points(case_root("alpha"))
check(by_key(_after, "prev_001").resumed_by_last,
      f"5. ...and the mark survives the file that reference named being gone, "
      f"so it is matched by BASENAME rather than by path or inode "
      f"({quoted(os.path.join(work, 'input.in'), 'zdump_fn_restart')!r})")

check(len([p for p in rows if p.kind == rp.LATEST]) == 1,
      f"7. work/ still offers ONE latest row, not a second one for the "
      f"bare-named hard link to the archived dump ({keys(rows)})")

# ── 4. a legacy archive, with no RUN.txt ──────────────────────────────────
os.remove(os.path.join(work, "prev_002", RUN_NOTE_NAME))
rows = rp.list_restart_points(case_root("alpha"))
legacy = by_key(rows, "prev_002")
check(legacy is not None and legacy.selectable,
      "4. an archive from before #30 still appears, and is still pickable")
check(legacy.iteration == rp.UNKNOWN_ITERATION and legacy.stamp == "",
      f"4. ...with no iteration count rather than a fabricated one "
      f"({legacy.iteration}, {legacy.stamp!r})")

# ── 6. the marker's three states ──────────────────────────────────────────
w(os.path.join(work, "input.in"), INPUT_IN)            # cold-started last run
rows = rp.list_restart_points(case_root("alpha"))
check(by_key(rows, rp.COLD).resumed_by_last
      and not any(p.resumed_by_last for p in rows if p.kind != rp.COLD),
      "6. a previous run that COLD started marks the Cold row")
os.remove(os.path.join(work, "input.in"))
rows = rp.list_restart_points(case_root("alpha"))
check(not any(p.resumed_by_last for p in rows),
      "6. ...and a work dir whose input.in cannot be read marks NOTHING — "
      "'we could not tell' must not render as the claim 'cold start'")
w(os.path.join(work, "input.in"), INPUT_IN)

# ── 11. a restart source inside an archive is quoted BARE ─────────────────
older = by_key(rp.list_restart_points(case_root("alpha")), "prev_001")
cfg3, (w3, _g3, in3) = prep("alpha", zdump=older.zdump, convg=older.convg)
ref3 = quoted(in3, "zdump_fn_restart")
check(ref3 == "binDumpZ.dat.prev_001",
      f"11. a dump the user picked out of work/prev_001/ is quoted as a BARE "
      f"name in work/ — the only shape the solver can read (#30) ({ref3!r})")
link = os.path.join(w3, ref3 or "x")
real = os.path.join(w3, "prev_001", "binDumpZ.dat.prev_001")
check(os.path.isfile(link) and os.path.isfile(real)
      and os.stat(link).st_ino == os.stat(real).st_ino,
      "11. ...and that name is a hard LINK to the file in the archive, so the "
      "archive stays complete and the case grows by ~0 bytes")
check(cfg3.zdump_fn_restart == older.zdump,
      f"11. ...while the MODEL keeps its absolute path to the real file (#25) "
      f"({cfg3.zdump_fn_restart!r})")
check(any("prev_001" in m and "bare" in m.lower() for m in LOG),
      f"11. ...and the link is said out loud rather than appearing silently "
      f"({[m for m in LOG if 'prev_001' in m]})")

# ── 8. the widget writes the model ────────────────────────────────────────
from PyQt6.QtWidgets import QApplication                            # noqa: E402
from app.views.panels.solver_config_panel import SolverConfigPanel   # noqa: E402
import app.services.paths as paths_mod                              # noqa: E402

# The last restart archived work/'s outputs into prev_003, so seed one more
# finished run: the panel is then looking at the state a user actually sees — a
# latest result AND three archived legs behind it.
w(os.path.join(work, "binDumpZ.dat.gui"), "run4 dump")
w(os.path.join(work, "unicones.enorm.gui"), CONVG)
w(os.path.join(work, "input.in"), INPUT_IN + (
    '   zdump_fn_restart\t"binDumpZ.dat.prev_001"\n'))

_app = QApplication.instance() or QApplication([])
paths_mod.repo_root = lambda: repo

panel = SolverConfigPanel()
cfg = SolverConfig()
cfg.case_name = "alpha"
panel.set_config(cfg)
chooser = panel.restart_chooser
row_keys = [b.property("restart_key") for b in chooser._buttons]
check(row_keys == [rp.COLD, rp.LATEST, "prev_003", "prev_002", "prev_001",
                   rp.OTHER],
      f"8. the panel shows one row per restart point, with Cold start first and "
      f"'Other file…' last ({row_keys})")
check(chooser._buttons[row_keys.index(rp.COLD)].isChecked(),
      "8. a config with restart off lands on Cold start")
out = panel.get_config()
check(out.restart is False and out.zdump_fn_restart == "" == out.convg_fn_restart,
      f"8. ...and reads back as no restart with BOTH fields cleared, so nothing "
      f"stale is saved ({out.restart}, {out.zdump_fn_restart!r})")

chooser._buttons[row_keys.index("prev_001")].setChecked(True)
out = panel.get_config()
older = by_key(rp.list_restart_points(case_root("alpha")), "prev_001")
check(out.restart is True and out.zdump_fn_restart == older.zdump
      and out.convg_fn_restart == older.convg,
      f"8. picking an archived leg sets the Restart flag and BOTH paths together "
      f"— 're-run the same leg' in one click ({out.zdump_fn_restart!r})")
check(any("started here" in b.text() for b in chooser._buttons),
      f"8. ...and the row the previous run resumed from is visibly marked "
      f"({[b.text() for b in chooser._buttons if 'started here' in b.text()]})")

elsewhere = os.path.join(repo, "other", "work", "binDumpZ.dat.cli")
w(elsewhere, "a dump in another case")
chooser._buttons[row_keys.index(rp.OTHER)].setChecked(True)
chooser.zdump_fn_restart.setText(elsewhere)
out = panel.get_config()
check(out.restart is True and out.zdump_fn_restart == elsewhere,
      f"8. 'Other file…' still allows an arbitrary path — a dump in another case "
      f"dir, which #25 supports ({out.zdump_fn_restart!r})")

# Re-listing must REPLACE the rows, not draw over them. `deleteLater` is
# deferred and a widget merely removed from a layout keeps its parent, its
# geometry and its visibility, so the previous case's rows survived the first
# refresh (measured: a stale "Other file…" radio, before setParent(None)).
from PyQt6.QtWidgets import QRadioButton                            # noqa: E402

other_case = SolverConfig()
other_case.case_name = "fresh"
panel.set_config(other_case)
live = [b.text() for b in chooser.findChildren(QRadioButton)]
check(len(live) == len(chooser._buttons) == 2,
      f"8. switching to a case with no history REPLACES the rows — a widget "
      f"removed from a layout keeps its parent, so a deferred delete leaves the "
      f"previous case's rows drawn on top ({live})")
panel.set_config(cfg)

stale = SolverConfig()
stale.case_name = "alpha"
stale.restart = True
stale.zdump_fn_restart = os.path.join(repo, "gone", "binDumpZ.dat.gui")
panel.set_config(stale)
check(chooser._picked().kind == rp.OTHER
      and panel.get_config().zdump_fn_restart == stale.zdump_fn_restart,
      f"8. a path this case's history does not offer lands on 'Other file…' with "
      f"the path INTACT — it is not rewritten into something that merely looks "
      f"valid ({panel.get_config().zdump_fn_restart!r})")

# ── 9. a restart whose source is gone is refused before the solver runs ────
from app.controllers.solver_ctrl import SolverControllerMixin        # noqa: E402
import app.controllers.solver_ctrl as solver_ctrl                   # noqa: E402


class _Ctl(SolverControllerMixin):
    def __init__(self):
        self.msgs = []
        self.main_window = None
        self._pipeline_running = False

    def log(self, msg):
        self.msgs.append(msg)


ctl = _Ctl()
errs = ctl._validate_solver_config(stale)
check(any(stale.zdump_fn_restart in e and "Zone dump" in e for e in errs),
      f"9. a restart pointing at a file that does not exist is refused, naming "
      f"the FIELD and the missing PATH — the solver's own message named neither "
      f"({errs})")
good = SolverConfig()
good.case_name, good.restart = "alpha", True
good.zdump_fn_restart, good.convg_fn_restart = older.zdump, older.convg
check(not [e for e in ctl._validate_solver_config(good) if "Restart" in e],
      f"9. ...while a source that IS there passes "
      f"({[e for e in ctl._validate_solver_config(good) if 'Restart' in e]})")
blank = SolverConfig()
blank.case_name, blank.restart = "alpha", True
check(any("no restart zone-dump file is set" in e
          for e in ctl._validate_solver_config(blank)),
      "9. ...and 'restart with no source at all' keeps its own separate message")
relative = SolverConfig()
relative.case_name, relative.restart = "alpha", True
relative.zdump_fn_restart = "binDumpZ.dat.gui"
check(not [e for e in ctl._validate_solver_config(relative) if "Restart" in e],
      "9. a RELATIVE reference is resolved against this case's work dir, not "
      "the process cwd — #25 emits one and a re-loaded .hws can hold one")

# ── 10. Run does not raise the case-dir modal on a restart ─────────────────
asked = []
solver_ctrl.ask_case_disposition = (
    lambda *a, **k: asked.append(a) or solver_case.CASE_NEW_VERSION)

ctl.msgs.clear()
got = ctl._resolve_case_disposition(good)
check(got == solver_case.CASE_ARCHIVE and not asked,
      f"10. a restart is not asked about: the disposition is the archiving one "
      f"and no modal is raised ({got!r}, asked={len(asked)})")
check(any("prev_" in m and "work/" in m for m in ctl.msgs),
      f"10. ...and it is said in the LOG, naming the concrete directory — that "
      f"legibility is what the removed confirmation step used to provide "
      f"({ctl.msgs})")

cold = SolverConfig()
cold.case_name = "alpha"
ctl.msgs.clear()
got = ctl._resolve_case_disposition(cold)
check(len(asked) == 1 and got == solver_case.CASE_NEW_VERSION,
      f"10. the NON-restart path still asks — that question is genuinely "
      f"ambiguous and #31 only removed the one that was not ({len(asked)})")

ctl._pipeline_running = True
asked.clear()
got = ctl._resolve_case_disposition(good)
check(got == solver_case.CASE_NEW_VERSION and not asked,
      f"10. Run All / batch is unchanged: it auto-versions without a modal and "
      f"without archiving, even for a restart ({got!r}, asked={len(asked)})")
ctl._pipeline_running = False

# ── 12. the pick reaches the MODEL, through the real controller ────────────
# The panel→model sync is driven by ONE traversal that connects the "user
# changed me" signal of every input widget it knows (undo_ctrl), and it knows
# spin boxes, combos, line edits and checkable buttons — not a control that
# rebuilds its own rows after that traversal has run. Without the `panel_edited`
# hand-back the chooser edits the panel and the model keeps the previous answer,
# which is exactly the staleness the single data-flow direction exists to remove
# and is invisible to every check above: they all read the PANEL.
from app.controller import AppController                            # noqa: E402

ctrl = AppController()
sp = ctrl.main_window.solver_config_panel
seed = SolverConfig()
seed.case_name = "alpha"
ctrl.push_panel_config(sp, seed)
before = ctrl.global_solver_config.zdump_fn_restart
target = next(b for b in sp.restart_chooser._buttons
              if b.property("restart_key") == "prev_001")
target.setChecked(True)
check(ctrl.global_solver_config.restart is True
      and ctrl.global_solver_config.zdump_fn_restart == older.zdump,
      f"12. picking a row updates the MODEL, not just the panel — the chooser's "
      f"rows are built after the sync traversal has run, so it hands its own "
      f"edits back ({before!r} -> "
      f"{ctrl.global_solver_config.zdump_fn_restart!r})")

print()
if _FAILS:
    print(f"{len(_FAILS)} FAILED:")
    for m in _FAILS:
        print("  - " + m)
print(f"{len(_FAILS)} failure(s)" if _FAILS else "all checks passed")
os._exit(1 if _FAILS else 0)
