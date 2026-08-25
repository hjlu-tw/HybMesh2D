#!/usr/bin/env python3
"""The three remaining quoted paths in ``input.in`` are STAGED into the work dir.

Found in review of #25 (issue #29), not from a user report.
``SolverConfig.generate_input_in`` quotes nine values and every quoted value in
``input.in`` is a file path. Six were resolved by ``prepare_case_dir`` before the
file was written — the grid, the bc table, the two restart references (#25), the
init-condition DLL and the motion DLL. Three were written with ``.strip()`` and
nothing else: ``mpi_comm_map_fn``, ``cfl_schedule_fn`` and
``probe_points_def_fn``. Two of the three are ``"path"`` field specs with a file
dialog behind them, so the GUI routinely puts an absolute path on this machine
into them — the exact shape #25 was about, for three more fields.

The answer here is the OPPOSITE of #25's and for a stated reason. The restart
zone dump is the largest file in a case, so it is referenced and never copied.
These three are small tables, and a case that does not hold its own inputs is
the problem, so they are **copied into work/ and quoted by bare name** — which
is already what ``case_export`` does to them, so an exported case was
self-contained while the case it was exported from referenced this machine's
filesystem.

Pinned here, all against the real ``prepare_case_dir`` / the real export
planner on a temp tree:

 1. an absolute path outside the repo is copied into work/ and quoted by its
    bare name, and that name really resolves from the work dir — for all three
    fields, not just the one the review happened to name;
 2. the source file is still where the user put it (copy, never move), and the
    CONFIG still holds the absolute path, so a ``.hws`` saved after the run is
    unchanged and the panel stays browsable;
 3. a BARE name is emitted unchanged and nothing is copied — it is already
    relative to the work dir, which is the solver's cwd, and is the intended
    form for ``cfl_schedule_fn``;
 4. a value that does not resolve is emitted unchanged and nothing is copied,
    so it surfaces as the solver's own error rather than being rewritten into
    something that merely looks valid (#25's rule 4);
 5. two tables with the SAME basename from different directories both travel,
    under distinct names;
 6. a staged table cannot land on top of the fixed names ``prepare_case_dir``
    writes into the work dir itself;
 7. re-running the same case overwrites its own staged copy instead of walking
    ``probe.dat`` -> ``probe_2.dat`` -> ``probe_3.dat``;
 8. ``case_export`` still ships all three and the exported ``input.in`` resolves
    inside the package — and reports each of them exactly ONCE, which is the
    regression the staging made reachable: two of the three carry no name
    ``_WORK_KEEP`` knows, so before the planner learned to see a reference they
    were listed under INCLUDED (by ``_resolve_input_in``) *and* under a SKIPPED
    heading in the same manifest;
 9. a restart that archives the previous run's outputs leaves a staged table
    alone AND stops calling it unrecognised — it is an input this toolchain put
    there.

Blind spots, named rather than papered over. This pins the STRING written into
``input.in`` and that it resolves on this filesystem; whether ``unicones``
accepts a bare name in these three positions is unanswerable here, because it
ships as a binary with no source and no case in this repo sets any of the three
keys. Unlike #25 — where the solver's own path derivation WAS the failure — the
justification is self-containment and one rule for all nine quoted paths, and
the target shape (``./<name>`` beside ``input.in``) is already proven runnable
by ``case_export``'s own acceptance run. Nothing here claims a solver failure
was fixed. Separately, WHERE bDecompose runs is untouched: it still writes the
comm map next to its own binary, outside the case (#37).

Run:  python3 tools/PreProcessor/tests/test_input_in_staged_paths.py
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

from app.models.solver_config import SolverConfig      # noqa: E402
from app.services import case_export, solver_case      # noqa: E402


def w(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


tmp = tempfile.mkdtemp(prefix="hybmesh_staged_paths_")
repo = os.path.join(tmp, "repo")
mesh = os.path.join(repo, "m")
for ext in (".vrt", ".cel", ".bnd"):
    w(mesh + ext, "mesh")

_real_repo_root = solver_case.repo_root
solver_case.repo_root = lambda: repo

# The three tables, outside the repo entirely — where a file dialog leaves them.
outside = os.path.join(tmp, "outside")
SRC = {"mpi_comm_map_fn": os.path.join(outside, "comm_map.txt"),
       "cfl_schedule_fn": os.path.join(outside, "cfl_table.txt"),
       "probe_points_def_fn": os.path.join(outside, "probe_points.txt")}
for key, path in SRC.items():
    w(path, key)


def prep(case_name, *, comm_map=None, cfl=None, probe=None, overwrite=False,
         archive_prev=False, log=None):
    cfg = SolverConfig()
    cfg.case_name = case_name
    cfg.input_vrt_file = mesh + ".vrt"
    cfg.input_cel_file = mesh + ".cel"
    cfg.input_bnd_file = mesh + ".bnd"
    # mpi_comm_map_fn is only written under decomposition (unchanged by #29).
    cfg.enable_decompose = True
    cfg.mpi_comm_map_fn = SRC["mpi_comm_map_fn"] if comm_map is None else comm_map
    cfg.cfl_schedule_fn = SRC["cfl_schedule_fn"] if cfl is None else cfl
    cfg.probe_points_def_fn = (SRC["probe_points_def_fn"] if probe is None
                               else probe)
    kw = {} if log is None else {"log": log}
    return cfg, solver_case.prepare_case_dir(
        cfg, overwrite=overwrite, archive_prev=archive_prev, **kw)


def quoted(input_in, key):
    """The value ``generate_input_in`` wrote for ``key``, or None."""
    with open(input_in) as f:
        for line in f:
            parts = line.split()
            if parts[:1] == [key]:
                return line.split('"')[1] if '"' in line else parts[1]
    return None


KEYS = ("mpi_comm_map_fn", "cfl_schedule_fn", "probe_points_def_fn")

# ── 1. an absolute path outside the case is staged and quoted by bare name ──
cfg1, (w1, g1, in1) = prep("tables")
for key in KEYS:
    ref = quoted(in1, key)
    check(ref is not None and ref == os.path.basename(SRC[key]),
          f"1. {key} is quoted by the bare name of the file staged into work/, "
          f"not by this machine's absolute path ({ref!r})")
    check(ref is not None and not os.path.isabs(ref)
          and os.path.isfile(os.path.join(w1, ref)),
          f"1. ...and {key}'s reference really resolves from the work dir the "
          f"solver runs in (an absolute path would satisfy the join too, so it "
          f"is excluded here)")

# ── 2. copy, not move; and cfg keeps the browsable absolute path ───────────
check(all(os.path.isfile(p) for p in SRC.values()),
      "2. the source files are still where the user put them — copy, never "
      "move: one table may feed several cases")
check(cfg1.mpi_comm_map_fn == SRC["mpi_comm_map_fn"]
      and cfg1.cfl_schedule_fn == SRC["cfl_schedule_fn"]
      and cfg1.probe_points_def_fn == SRC["probe_points_def_fn"],
      f"2. the CONFIG keeps its absolute path — the bare name is injected into "
      f"the writer like grid_rel/zdump_rel, never written back, because cfg is "
      f"the model the .hws and the pipeline script are saved from and a "
      f"work-dir-relative value there resolves to nothing from the next, "
      f"auto-versioned work dir ({cfg1.probe_points_def_fn!r})")
check(open(os.path.join(w1, os.path.basename(SRC["cfl_schedule_fn"]))).read()
      == "cfl_schedule_fn",
      "2. ...and the staged copy really is the file the field named, not an "
      "empty placeholder")

# ── 3. a bare name is left exactly as it is, and nothing is copied ─────────
cfg3, (w3, _g3, in3) = prep("bare", comm_map="", cfl="cfl.table", probe="")
check(quoted(in3, "cfl_schedule_fn") == "cfl.table",
      f"3. a bare name is emitted unchanged — it is already relative to the "
      f"work dir, which is the solver's cwd, and is the intended form for a "
      f"CFL schedule ({quoted(in3, 'cfl_schedule_fn')!r})")
check(sorted(os.listdir(w3)) == ["input.in"],
      f"3. ...and nothing was copied for it: a bare name names no source to "
      f"copy ({sorted(os.listdir(w3))})")
check(quoted(in3, "mpi_comm_map_fn") is None
      and quoted(in3, "probe_points_def_fn") is None,
      "3. a blank field still emits no line at all — staging must not change "
      "which lines input.in has, only what they quote")

# ...and a bare name RESERVES its basename, or a later field holding an absolute
# path to a different file with the same name would be copied on top of the file
# this one quotes and both references would resolve to one table. Narrow, but the
# only thing separating "leave a bare name alone" from "a value that happens not
# to resolve is left alone" — which is a different rule that happens to agree.
bare_clash = os.path.join(tmp, "a2", "table.txt")
w(bare_clash, "FROM_A2")
cfg3b, (w3b, _g3b, in3b) = prep("bare_clash", comm_map="", cfl="table.txt",
                                probe=bare_clash)
ref3b_cfl = quoted(in3b, "cfl_schedule_fn")
ref3b_probe = quoted(in3b, "probe_points_def_fn")
check(ref3b_cfl == "table.txt" and ref3b_probe != "table.txt"
      and not os.path.isfile(os.path.join(w3b, "table.txt"))
      and open(os.path.join(w3b, ref3b_probe)).read() == "FROM_A2",
      f"3. a bare name reserves its basename: a staged table never lands on the "
      f"name another field already quotes, so the run cannot be handed one "
      f"table twice ({ref3b_cfl!r}, {ref3b_probe!r})")

# ── 4. a non-resolving path is emitted verbatim, and nothing is copied ─────
gone = os.path.join(tmp, "nowhere", "vanished.tbl")
cfg4, (w4, _g4, in4) = prep("gone", comm_map="", cfl=gone, probe="")
check(quoted(in4, "cfl_schedule_fn") == gone,
      f"4. an absolute path that does not resolve is written verbatim, so it "
      f"surfaces as the solver's own error instead of being rewritten into "
      f"something that looks valid ({quoted(in4, 'cfl_schedule_fn')!r})")
check(sorted(os.listdir(w4)) == ["input.in"],
      f"4. ...and nothing was fabricated in work/ for it "
      f"({sorted(os.listdir(w4))})")

# ── 5. same basename, different directories: both travel ──────────────────
dir_a = os.path.join(tmp, "a")
dir_b = os.path.join(tmp, "b")
w(os.path.join(dir_a, "table.txt"), "FROM_A")
w(os.path.join(dir_b, "table.txt"), "FROM_B")
cfg5, (w5, _g5, in5) = prep("clash", comm_map="",
                            cfl=os.path.join(dir_a, "table.txt"),
                            probe=os.path.join(dir_b, "table.txt"))
ref_a, ref_b = quoted(in5, "cfl_schedule_fn"), quoted(in5, "probe_points_def_fn")
check(ref_a != ref_b
      and not os.path.isabs(ref_a) and not os.path.isabs(ref_b)
      and open(os.path.join(w5, ref_a)).read() == "FROM_A"
      and open(os.path.join(w5, ref_b)).read() == "FROM_B",
      f"5. two tables sharing a basename both travel under distinct names, "
      f"each resolving to its OWN content — a collision would silently give "
      f"the run one table twice ({ref_a!r}, {ref_b!r})")

# ── 6. a staged table cannot land on top of what the case dir already means ─
w(os.path.join(dir_a, "input.in"), "USER_TABLE_NAMED_LIKE_THE_SOLVER_INPUT")
cfg6, (w6, _g6, in6) = prep("reserved", comm_map="",
                            cfl=os.path.join(dir_a, "input.in"), probe="")
ref6 = quoted(in6, "cfl_schedule_fn")
check(ref6 != "input.in" and not os.path.isabs(ref6)
      and os.path.isfile(os.path.join(w6, ref6)),
      f"6. a table whose basename collides with a fixed name prepare_case_dir "
      f"writes into work/ is staged beside it, not over it ({ref6!r})")
check("solver" not in open(os.path.join(w6, "input.in")).read().lower()
      or quoted(in6, "grid_fname") is not None,
      "6. ...and work/input.in is still the solver input file it was")

# ── 7. re-running the same case overwrites its own staged copy ─────────────
w(os.path.join(g1, "tables.grid"), "G")
w(os.path.join(g1, "tables.bc"), "B")
cfg7, (w7, _g7, in7) = prep("tables", overwrite=True)
check(os.path.abspath(w7) == os.path.abspath(w1),
      "7. (precondition) overwrite=True re-runs in the same work dir")
for key in KEYS:
    check(quoted(in7, key) == os.path.basename(SRC[key]),
          f"7. a re-run overwrites its own staged copy instead of walking "
          f"<name>_2, <name>_3, … — the collision counter is per-run, like the "
          f"grid and phi staging beside it ({key}={quoted(in7, key)!r})")

# ── 8. the export ships all three, ONCE, and the package resolves ──────────
case8 = os.path.dirname(w1)
plan = case_export.plan_export(case8)
rels = [i.rel for i in plan.items]
skipped = ([r for r, _s in plan.skipped_output]
           + [r for r, _s, _w in plan.skipped_unused]
           + [r for r, _s in plan.skipped_other])
for key in KEYS:
    rel = f"work/{os.path.basename(SRC[key])}"
    check(rels.count(rel) == 1,
          f"8. the export ships the staged {key} exactly once ({rel})")
    check(rel not in skipped,
          f"8. ...and does NOT also report it as skipped — one path under "
          f"INCLUDED and under a SKIPPED heading in one manifest is the "
          f"contradiction the named-skip design exists to make impossible, and "
          f"staging is what made it reachable ({rel}; skipped={skipped})")
pkg = os.path.join(tmp, "pkg")
case_export.export_case(case8, pkg, plan=plan)
pkg_in = os.path.join(pkg, "work", "input.in")
for key in KEYS:
    ref = quoted(pkg_in, key)
    check(ref is not None and os.path.isfile(os.path.join(pkg, "work", ref)),
          f"8. the exported input.in quotes {key} by a name that resolves "
          f"inside the package ({ref!r})")

# ── 9. an archiving restart leaves a staged table alone, and knows why ─────
lines = []
dump = os.path.join(w1, "binDumpZ.dat.gui")
w(dump, "DUMP")
w(os.path.join(w1, "xtecplot.plt"), "OUT")
cfg9 = SolverConfig()
cfg9.case_name = "tables"
cfg9.input_vrt_file = mesh + ".vrt"
cfg9.input_cel_file = mesh + ".cel"
cfg9.input_bnd_file = mesh + ".bnd"
cfg9.enable_decompose = True
cfg9.mpi_comm_map_fn = SRC["mpi_comm_map_fn"]
cfg9.cfl_schedule_fn = SRC["cfl_schedule_fn"]
cfg9.probe_points_def_fn = SRC["probe_points_def_fn"]
cfg9.restart = True
cfg9.zdump_fn_restart = dump
w9, _g9, in9 = solver_case.prepare_case_dir(
    cfg9, log=lines.append, overwrite=True, archive_prev=True)
for key in KEYS:
    base = os.path.basename(SRC[key])
    check(os.path.isfile(os.path.join(w9, base)),
          f"9. the archive leaves the staged {key} in work/ — it is an input "
          f"of the resumed run, not one of its outputs ({base})")
    check(not any(f"work/{base}" in ln and "not a recognised" in ln
                  for ln in lines),
          f"9. ...and no longer calls it unrecognised: this toolchain staged "
          f"it, so 'nobody classified this' would be a false statement about "
          f"a file the previous input.in names ({base})")
check(os.path.isfile(os.path.join(w9, "prev_001", "xtecplot.plt"))
      and not os.path.isfile(os.path.join(w9, "xtecplot.plt")),
      "9. (control) a real output still moves into prev_001/ — the tables were "
      "exempted from the archive, not the whole classification")

solver_case.repo_root = _real_repo_root
shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED")
    for m in _FAILS:
        print("  - " + m)
    sys.exit(1)
print("\nRESULT: ALL PASS")
