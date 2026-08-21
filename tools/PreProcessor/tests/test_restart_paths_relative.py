#!/usr/bin/env python3
"""Restart references in ``input.in`` are relative to the work dir, like every
other quoted path ``prepare_case_dir`` writes.

USER-REPORTED (2026-08-20, issue #25): a GUI restart run errors on its restart
path. The panel's autofill (``solver_config_sync_mixin._autofill_restart_from_
last_run``) fills the two restart fields with an ABSOLUTE path — deliberately,
so the field is browsable and discoverable — and ``generate_input_in`` is a dumb
writer that emits whatever the config holds. ``prepare_case_dir`` is what makes a
quoted path work-dir relative: the grid/bc as ``../grid/<case>.*``, the IBM DLLs
as ``../dll/*.so``, a BC type-11 DLL as ``./x.so``. Of the paths it knew about,
the two restart fields were the only ones it never touched, so they alone reached
the solver as this machine's filesystem. The shipped reference case agrees
(``solver/case/Cyl_IBM_Rotate/work/input.in``), and ``case_export`` already
relativises exactly these references when it packages a case — so an EXPORTED
case ran while the case it was exported from did not.

Pinned here, all against the real ``prepare_case_dir`` on a temp tree:

 1. a dump inside the run's own ``work/`` becomes its bare basename;
 2. a dump in ANOTHER case dir becomes a relative path out and back, and that
    path really resolves from the work dir (this is not hypothetical: the
    autofill computes the path BEFORE ``resolve_case_root`` may auto-version the
    directory, so a versioned run genuinely restarts from the previous dir);
 2b. and the model keeps its absolute path, which is what lets a FOLLOWING run
    in a different work dir get a reference that resolves from there;
 3. an already-relative value is left alone — it is by definition relative to
    the work dir, which is where the solver runs;
 4. a blank or non-resolving value is left alone — ``solver_ctrl._validate``
    already refuses a restart with no dump, and a path that does not exist must
    surface as the solver's own error rather than be rewritten into something
    that merely looks valid;
 5. the dump is NOT copied into the case (it is the largest file in a case; a
    reference costs nothing) — pinned inside 2;
 6. ``case_export`` still recognises the now-relative reference, so the dump is
    shipped rather than dropped from the package as unreferenced, AND the
    reference resolves inside the written package.

Two blind spots, named rather than papered over. This pins the STRING written
into ``input.in`` and that it resolves on this filesystem; whether the solver
accepts it is evidence only the acceptance run can give (the original error text
was not captured in the report — see the issue's open question). And three quoted
paths are NOT covered by the fix or by this test — ``mpi_comm_map_fn``,
``cfl_schedule_fn``, ``probe_points_def_fn`` are still emitted verbatim, so a
browsed-to absolute path still reaches the solver in the shape #25 was about.
That is scoped-out residue, not a passing check.

Run:  python3 tools/PreProcessor/tests/test_restart_paths_relative.py
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


tmp = tempfile.mkdtemp(prefix="hybmesh_restart_rel_")
repo = os.path.join(tmp, "repo")
mesh = os.path.join(repo, "m")
for ext in (".vrt", ".cel", ".bnd"):
    w(mesh + ext, "mesh")

_real_repo_root = solver_case.repo_root
solver_case.repo_root = lambda: repo


def prep(case_name, *, zdump="", convg="", overwrite=False):
    cfg = SolverConfig()
    cfg.case_name = case_name
    cfg.input_vrt_file = mesh + ".vrt"
    cfg.input_cel_file = mesh + ".cel"
    cfg.input_bnd_file = mesh + ".bnd"
    cfg.restart = True
    cfg.zdump_fn_restart = zdump
    cfg.convg_fn_restart = convg
    return cfg, solver_case.prepare_case_dir(cfg, overwrite=overwrite)


def quoted(input_in, key):
    """The value ``generate_input_in`` wrote for ``key``, or None."""
    with open(input_in) as f:
        for line in f:
            parts = line.split()
            if parts[:1] == [key]:
                return line.split('"')[1] if '"' in line else parts[1]
    return None


# ── 1. a dump in the run's own work/ is written as its bare basename ───────
# Seed the case dir as a previous run of it would have left it.
own_work = os.path.join(repo, "results", "solver", "own", "work")
own_dump = os.path.join(own_work, "binDumpZ.dat.gui")
own_convg = os.path.join(own_work, "unicones.enorm.gui")
w(own_dump, "DUMP")
w(own_convg, "CONVG")

cfg1, (w1, _g1, in1) = prep("own", zdump=own_dump, convg=own_convg,
                            overwrite=True)
check(os.path.abspath(w1) == os.path.abspath(own_work),
      "1. (precondition) overwrite=True reuses the case dir the dump sits in")
check(quoted(in1, "zdump_fn_restart") == "binDumpZ.dat.gui",
      f"1. an absolute dump inside the run's own work/ is written as its bare "
      f"name, like the grid is written as ../grid/<case>.grid "
      f"({quoted(in1, 'zdump_fn_restart')!r})")
check(quoted(in1, "convg_fn_restart") == "unicones.enorm.gui",
      f"1. ...and so is the convergence file — both restart fields, not just "
      f"the one the report happened to name "
      f"({quoted(in1, 'convg_fn_restart')!r})")
check(cfg1.zdump_fn_restart == own_dump
      and cfg1.convg_fn_restart == own_convg,
      f"1. the CONFIG keeps its absolute path — the relative form is injected "
      f"into the writer like grid_rel/bc_rel, never written back. This is the "
      f"one place the fix departs from the staging around it, because it is "
      f"the one value prepare_case_dir cannot RE-derive: output_grid_file is "
      f"rebuilt from case_name every run, while a work-dir-relative restart "
      f"path saved into the .hws would resolve to nothing from the next, "
      f"auto-versioned work dir ({cfg1.zdump_fn_restart!r})")

# ── 2. a dump in ANOTHER case dir resolves out and back ───────────────────
# This is the auto-versioning case: the panel computed the path from the case
# NAME, then resolve_case_root sent this run to <case>_002.
w(os.path.join(repo, "results", "solver", "own", "grid", "own.grid"), "G")
cfg2, (w2, _g2, in2) = prep("own", zdump=own_dump)
check(os.path.basename(os.path.dirname(w2)) == "own_002",
      "2. (precondition) the second run auto-versions into own_002/")
ref2 = quoted(in2, "zdump_fn_restart")
check(ref2 == "../../own/work/binDumpZ.dat.gui",
      f"2. the dump in the PREVIOUS case dir is written as a relative path out "
      f"and back — a bare basename would point at a file that is not there "
      f"({ref2!r})")
check(not os.path.isabs(ref2) and os.path.exists(os.path.join(w2, ref2)),
      "2. ...and that reference really resolves from the work dir the solver "
      "runs in, which is the only thing the solver checks (an absolute path "
      "would satisfy the join too, so it is excluded here)")
check(not os.path.exists(os.path.join(w2, "binDumpZ.dat.gui")),
      "2. the dump is NOT copied into the new case dir — it is the largest "
      "file in a case, and a copy would leave two dumps whose relationship "
      "nothing records")
check(os.path.exists(own_dump),
      "2. ...nor moved: the case it belongs to still has it")

# ...and that is what keeps a SECOND run correct: the model still holds the
# absolute path, so relativising it against the new work dir gives a reference
# that resolves from there. Had the first run overwritten it with a basename,
# rule 3 (a relative value is passed through) would carry that basename into a
# directory the dump is not in.
w(os.path.join(repo, "results", "solver", "own", "grid", "seed.grid"), "G")
cfg1b, (w1b, _g1b, in1b) = prep("own", zdump=cfg1.zdump_fn_restart)
ref1b = quoted(in1b, "zdump_fn_restart")
check(os.path.basename(os.path.dirname(w1b)) != "own"
      and os.path.exists(os.path.join(w1b, ref1b)),
      f"2b. a following run in a different work dir gets a reference that "
      f"resolves from THERE, which is only possible because the model was left "
      f"absolute ({ref1b!r} from {os.path.basename(os.path.dirname(w1b))}/work)")

# ── 3. an already-relative value is left exactly as it is ─────────────────
cfg3, (w3, _g3, in3) = prep("rel", zdump="binDumpZ.dat.cli",
                            convg="../../elsewhere/work/e.enorm")
check(quoted(in3, "zdump_fn_restart") == "binDumpZ.dat.cli"
      and quoted(in3, "convg_fn_restart") == "../../elsewhere/work/e.enorm",
      "3. a relative value is untouched — it is already relative to the work "
      "dir, so 'fix' it against a cwd and a scripted case breaks")

# ── 4. blank / non-resolving values are left alone ────────────────────────
gone = os.path.join(tmp, "nowhere", "vanished.dat")
cfg4, (_w4, _g4, in4) = prep("gone", zdump=gone)
check(quoted(in4, "zdump_fn_restart") == gone.replace(os.sep, "/")
      or quoted(in4, "zdump_fn_restart") == gone,
      f"4. an absolute path that does not resolve is written verbatim, so it "
      f"surfaces as the solver's own error instead of being rewritten into "
      f"something that looks valid ({quoted(in4, 'zdump_fn_restart')!r})")
cfg5, (_w5, _g5, in5) = prep("blank", zdump="", convg="")
check(quoted(in5, "zdump_fn_restart") is None
      and quoted(in5, "convg_fn_restart") is None,
      "4. a blank field emits no line at all (unchanged: solver_ctrl._validate "
      "is what refuses a restart with no dump)")

# ── 6. the relative reference is still an EXPORT signal ───────────────────
# case_export ships the dump only when input.in restarts from it. It matches on
# basename, so a relative reference must not make the dump look unreferenced.
export_case = os.path.dirname(w1)
w(os.path.join(export_case, "grid", "own.grid"), "G")
w(os.path.join(export_case, "grid", "own.bc"), "B")
plan = case_export.plan_export(export_case, include_restart="auto")
rels = {i.rel for i in plan.items}
check("work/binDumpZ.dat.gui" in rels,
      f"6. case_export still recognises the now-relative reference and ships "
      f"the dump — the fix must not turn a restart case into one whose dump "
      f"looks like a stray output ({sorted(r for r in rels if 'binDump' in r)})")

# ...and the package the plan describes really runs: the reference inside the
# EXPORTED input.in has to resolve from the exported work dir. Planning to carry
# the file and quoting a name that finds it are two different things — the
# exporter rewrites absolute references and must leave a relative one alone.
pkg = os.path.join(tmp, "pkg")
case_export.export_case(export_case, pkg, include_restart="auto", plan=plan)
pkg_in = os.path.join(pkg, "work", "input.in")
pkg_ref = quoted(pkg_in, "zdump_fn_restart")
check(pkg_ref == "binDumpZ.dat.gui"
      and os.path.exists(os.path.join(pkg, "work", pkg_ref)),
      f"6. the exported input.in quotes the dump by a name that resolves inside "
      f"the package — the relative reference is passed through, not rewritten "
      f"into this machine's filesystem ({pkg_ref!r})")

solver_case.repo_root = _real_repo_root
shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED")
    for m in _FAILS:
        print("  - " + m)
    sys.exit(1)
print("\nRESULT: ALL PASS")
