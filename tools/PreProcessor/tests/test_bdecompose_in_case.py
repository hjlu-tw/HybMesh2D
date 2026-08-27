#!/usr/bin/env python3
"""bDecompose runs IN THE CASE, and the failure is named before the run (#37).

Split out of #29 §5, which refused to conflate a path shape with where a stage
runs. Triage then read the code and found the problem is worse than "the output
lands next to the binary":

 1. **the stage could not find its inputs, by construction.**
    ``_run_bdecompose`` ran with ``cwd = os.path.dirname(cfg.bdecompose_binary)``
    — the binary's install dir — while ``generate_bdecompose_para`` writes the
    grid and bc as BARE BASENAMES. Those two files are written by getPGrid into
    the case's ``grid/`` and nothing ever copied them across, so bDecompose was
    asked to read a grid from a directory that does not contain it;
 2. **and the install dir holds a stale hand-copied grid**, which made that
    silent: ``solver/preprocess/bDecompose/work/`` still carries
    ``mesh_cartesian.grid`` / ``.bc`` from the one hand run. For a case NAMED
    ``mesh_cartesian`` the stage therefore found a grid, decomposed the STALE
    one, and the solver ran MPI on a decomposition of a different mesh — the
    same class as the stale ``work/phi.dat`` this repo has two defences against;
 3. **the binary's own para.in was written into a shared install dir**, so two
    concurrent runs raced on one file and a read-only install broke the stage.

The decision (recorded on the issue): run it in the case's ``grid/``, like
getPGrid. The inputs decide it — after stage 1, ``grid/`` holds all three files
bDecompose reads by bare name (``<case>.grid``, ``<case>.bc``, and the
``<case>.bc.def`` segment table getPGrid leaves beside them).

Two places where this deviates from the issue's own proposed scope, both
deliberate and both pinned below:

* **the answer file is NOT called para.in.** The issue says "writes its
  ``para.in`` there, exactly as ``_run_getpgrid`` already does" — but getPGrid
  already owns ``grid/para.in``, ``case_export`` ships that file as
  ``grid/getPGrid.in`` and ``run_case.sh --regrid`` feeds it back to getPGrid.
  Sharing the name would silently replace getPGrid's answers with bDecompose's
  in every exported package. The file is fed on **stdin**, so its name is ours
  to choose: ``grid/bDecompose.in``, named after the program whose stdin it is,
  which is the reason ``_RENAMES`` gives for the getPGrid one;
* **``case_export`` is not quite unchanged.** It cannot be: this change makes
  bDecompose's outputs appear in ``grid/`` for the first time. The new answer
  file is allow-listed (so a file this toolchain wrote is not reported as
  "unrecognised"), and the outputs are classified as outputs.

What is deliberately NOT done, because it is measurably harmful:
``is_run_output`` does **not** learn ``mpi_*``. For the comm map, "the file
bDecompose produces" and "the file the solver reads" are THE SAME NAME, and
``case_input_paths._stage_table`` asks ``is_run_output`` to decide whether to
stage a table — so teaching it ``mpi_*`` would stop #29 staging the comm map and
send the run back to referencing this machine's filesystem.

**Measured in-test, not argued** — the reasoning above is the shape of an
argument this repo has had reversed on it once for being written down without its
evidence being checked (#43), and a measurement taken once at a shell decays the
same way. So check 13 INJECTS it, permanently: it adds ``^mpi_`` to
``_OUTPUT_PATTERNS`` in the live module, re-runs the real ``_stage_table``, and
asserts the consequence — nothing copied into ``work/`` and ``input.in`` left
quoting the absolute source path — then restores the module and asserts the
control passes. Check 12 pins the precondition (``is_run_output`` says No);
check 13 is why that precondition matters.

Checks, against the real worker method, the real validator and the real export
planner on a temp tree:

 1. the stage runs with ``cwd`` = the case's ``grid/``, not the install dir;
 2. its stdin answer file is written inside that directory;
 3. and is NOT ``para.in`` — getPGrid's own answer file survives the stage
    byte-for-byte (the export regression above);
 4. every input the answer file names by bare basename really exists in the
    directory the stage runs in — finding 1, stated as the property rather than
    as a path;
 5. a case named ``mesh_cartesian`` decomposes ITS OWN grid: the cwd is the
    case's, so the stale install-dir copy cannot be the one read (finding 2);
 6. the install dir is not written to at all (finding 3 / the race);
 7. decomposition enabled with a MISSING bDecompose binary is refused by
    ``_validate_solver_config``, naming the field and the path;
 8. …and with a binary that is not in this platform's executable format, naming
    both formats — the reported case was an ELF x86-64 binary on an arm64 mac,
    which passed validation and died as a bare exit code in stage 2;
 9. …while a plausible binary raises no bDecompose error (control);
10. and with decomposition OFF, a missing binary is not an error at all — the
    field is optional and defaults blank (control);
11. ``case_export`` ships ``grid/bDecompose.in`` as an input and STILL ships
    ``grid/para.in`` as ``grid/getPGrid.in``, and bDecompose's outputs in
    ``grid/`` are named as skipped OUTPUTS rather than as unrecognised files;
12. (negative control on the shared classifier) ``is_run_output`` still says No
    to bDecompose's own output names, so #29 keeps staging a comm map;
13. and the INJECTION behind that control: widening ``is_run_output`` with
    ``^mpi_`` really does stop the comm map being staged, so folding the two
    classifiers together is measurably harmful rather than merely untidy.

Blind spots, named rather than papered over:

* **nothing here runs bDecompose.** It ships as a prebuilt x86-64 ELF binary
  with no source, and this machine is arm64 macOS — check 8 exists precisely
  because that is not runnable here. So checks 1-6 pin the SHAPE of the run
  (cwd, stdin file, inputs present), not the binary's acceptance of it. The
  issue asks for an acceptance run on an x86-64 Linux machine with MPI, and this
  repo's own #26 is the reason: it shipped broken with 85 green tests that
  pinned strings and never ran the solver;
* check 4 asserts the named inputs exist, not that bDecompose reads exactly
  those three lines. That order is pinned separately, against the shipped
  reference para.in, by ``test_solver_para_in_parity.py``;
* the comm map reaches ``work/`` only on the NEXT run, and bDecompose's other
  four outputs are never staged there at all. Both are recorded at the call site
  in ``_run_bdecompose`` and neither is pinned here, because the second one is a
  question the Linux acceptance run has to answer rather than a behaviour to
  freeze;
* check 8 refuses only on an executable-FORMAT mismatch (ELF here / Mach-O on
  Linux), which is never runnable. It deliberately does not compare machine
  words: macOS runs x86-64 Mach-O on arm64 under Rosetta, so an ``e_machine``
  refusal would be wrong there.
"""
import os
import re
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

from app.models.solver_config import SolverConfig            # noqa: E402
from app.services import case_export, case_files, paths      # noqa: E402
from app.workers.solver_run import SolverPipelineWorker      # noqa: E402


def w(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


tmp = tempfile.mkdtemp(prefix="hybmesh_bdecompose_")


# --------------------------------------------------------------------------- #
# A case whose stage 1 has already run: grid/ holds getPGrid's outputs (.grid,
# .bc, the .bc.def companion) and getPGrid's own answer file.
# --------------------------------------------------------------------------- #
def build_case(name):
    case = os.path.join(tmp, name)
    grid = os.path.join(case, "grid")
    work = os.path.join(case, "work")
    os.makedirs(grid, exist_ok=True)
    os.makedirs(work, exist_ok=True)
    w(os.path.join(grid, f"{name}.grid"), "GRID " + name)
    w(os.path.join(grid, f"{name}.bc"), "BC " + name)
    w(os.path.join(grid, f"{name}.bc.def"), "segm_no   bc_flag\n")
    w(os.path.join(grid, "para.in"), GETPGRID_ANSWERS)
    w(os.path.join(work, "input.in"), 'grid_fn "../grid/%s.grid"\n' % name)
    return case, grid, work


GETPGRID_ANSWERS = "y\ninput.vrt\ninput.cel\ninput.bnd\n"

# The stale hand-run leftovers this repo really carries, reproduced so finding 2
# is exercised rather than described: a case named mesh_cartesian used to find
# THESE.
install = os.path.join(tmp, "bDecompose_install")
bd_bin = os.path.join(install, "bDecompose")
w(bd_bin, "#!/bin/sh\nexit 0\n")
os.chmod(bd_bin, 0o755)
w(os.path.join(install, "mesh_cartesian.grid"), "STALE GRID")
w(os.path.join(install, "mesh_cartesian.bc"), "STALE BC")
w(os.path.join(install, "para.in"), "mesh_cartesian.grid\nmesh_cartesian.bc\n")
install_before = sorted(os.listdir(install))
# The CONTENT, not just the listing: the old code wrote its para.in over
# THIS file, which a directory listing cannot see. Measured — the listing
# form of check 6 passed against the unfixed code.
install_para_before = open(os.path.join(install, "para.in")).read()


def run_stage(case_name):
    """Drive the REAL ``_run_bdecompose``, capturing what it would launch.

    ``_run_stdin_stage`` is the seam: it is the one call that turns a (binary,
    answer file, cwd) triple into a process, and stubbing it keeps a stage that
    cannot execute on this machine testable without pretending it ran.
    """
    case, grid, work = build_case(case_name)
    cfg = SolverConfig()
    cfg.case_name = case_name
    cfg.enable_decompose = True
    cfg.num_partitions = 4
    cfg.bdecompose_binary = bd_bin
    cfg.output_grid_file = os.path.join(grid, f"{case_name}.grid")
    cfg.output_bc_file = os.path.join(grid, f"{case_name}.bc")

    seen = {}
    worker = SolverPipelineWorker(cfg, grid_dir=grid, solver_work_dir=work)

    def fake_stage(binary, para_path, cwd, label):
        seen.update(binary=binary, para_path=para_path, cwd=cwd, label=label)
        seen["para_text"] = open(para_path).read()
        return 0

    worker._run_stdin_stage = fake_stage
    worker.log_signal = type("S", (), {"emit": staticmethod(lambda *_a: None)})()
    worker.stage_signal = worker.log_signal
    worker.progress_signal = worker.log_signal
    worker.finished_signal = worker.log_signal
    ok = worker._run_bdecompose()
    return ok, seen, case, grid, work


# ── 1-4, 6: the stage runs in the case ──────────────────────────────────────
ok, seen, case, grid, work = run_stage("alpha")
check(ok, "0. the stage reports success when the (stubbed) process exits 0")
check(os.path.abspath(seen["cwd"]) == os.path.abspath(grid),
      f"1. bDecompose runs in the case's grid/, not the binary's install dir "
      f"(cwd={seen['cwd']!r}, want={grid!r})")
check(os.path.abspath(os.path.dirname(seen["para_path"]))
      == os.path.abspath(grid),
      f"2. its stdin answer file is written inside the case "
      f"({seen['para_path']!r})")
check(os.path.basename(seen["para_path"]) != "para.in",
      f"3. the answer file is NOT para.in — getPGrid owns that name in this "
      f"directory and case_export ships it as getPGrid.in "
      f"({os.path.basename(seen['para_path'])!r})")
check(open(os.path.join(grid, "para.in")).read() == GETPGRID_ANSWERS,
      "3. ...so getPGrid's own answer file survives the stage byte-for-byte; "
      "sharing the name would put bDecompose's answers into every exported "
      "package's getPGrid.in and break 'run_case.sh --regrid'")
named = [ln.strip() for ln in seen["para_text"].splitlines()
         if ln.strip() and ("." in ln)]
missing = [n for n in named if not os.path.isfile(os.path.join(seen["cwd"], n))]
check(named and not missing,
      f"4. every input the answer file names by bare basename exists in the "
      f"directory the stage runs in — finding 1 as a property, not a path "
      f"(named={named}, missing={missing})")
check(sorted(os.listdir(install)) == install_before
      and open(os.path.join(install, "para.in")).read() == install_para_before,
      f"4b. the shared install dir is not written to at all, so two concurrent "
      f"runs cannot race on one para.in, and a read-only install still works. "
      f"The CONTENT is compared, not only the listing: the old code overwrote "
      f"that very file, which a listing cannot see "
      f"({sorted(os.listdir(install))})")

# ── 5: finding 2 — a case named like the stale leftovers ─────────────────────
ok2, seen2, case2, grid2, _w2 = run_stage("mesh_cartesian")
check(os.path.abspath(seen2["cwd"]) == os.path.abspath(grid2)
      and os.path.abspath(seen2["cwd"]) != os.path.abspath(install),
      f"5. a case named 'mesh_cartesian' decomposes ITS OWN grid: the cwd is "
      f"the case's grid/, so the stale install-dir copy cannot be the one read "
      f"({seen2['cwd']!r})")
first = seen2["para_text"].splitlines()[0].strip()
check(open(os.path.join(seen2["cwd"], first)).read() == "GRID mesh_cartesian",
      f"5. ...and the grid that basename resolves to in that cwd is the case's, "
      f"not the stale one ({first!r})")

# ── 7-10: the failure is named before the run ────────────────────────────────
from app.controllers.solver_ctrl import SolverControllerMixin      # noqa: E402


class _Ctl(SolverControllerMixin):
    def __init__(self):
        self.msgs = []
        self.main_window = None
        self._pipeline_running = False

    def log(self, msg):
        self.msgs.append(msg)


ctl = _Ctl()


def bd_errors(cfg):
    return [e for e in ctl._validate_solver_config(cfg)
            if "bdecompose" in e.lower() or "bDecompose" in e]


def mpi_ok_cfg():
    """A config whose OTHER decomposition preconditions are satisfied, so a
    bDecompose error is the only thing these checks can be reading."""
    cfg = SolverConfig()
    cfg.case_name = "alpha"
    cfg.enable_decompose = True
    cfg.bdecompose_binary = bd_bin
    return cfg


gone = os.path.join(tmp, "nowhere", "bDecompose")
cfg7 = mpi_ok_cfg()
cfg7.bdecompose_binary = gone
errs7 = bd_errors(cfg7)
check(any(gone in e for e in errs7),
      f"7. decomposition on + a missing bDecompose binary is refused before the "
      f"run, naming the path — it used to pass validation and die in stage 2 as "
      f"a bare exit code ({errs7})")

# An executable in the format of the OTHER platform: never runnable here, which
# is the reported case (x86-64 ELF on an arm64 mac).
alien = os.path.join(tmp, "alien_bDecompose")
_ELF = b"\x7fELF\x02\x01\x01" + b"\x00" * 57
_MACHO = b"\xcf\xfa\xed\xfe" + b"\x00" * 60
with open(alien, "wb") as f:
    f.write(_MACHO if sys.platform.startswith("linux") else _ELF)
os.chmod(alien, 0o755)
cfg8 = mpi_ok_cfg()
cfg8.bdecompose_binary = alien
errs8 = bd_errors(cfg8)
check(any(alien in e for e in errs8),
      f"8. …and a binary that is not in this platform's executable format is "
      f"refused too, naming it ({errs8})")
check(paths.wrong_executable_format(alien)
      and not paths.wrong_executable_format(sys.executable),
      "8. …the format test itself: it rejects the other platform's format and "
      "accepts this platform's own interpreter (control)")

cfg9 = mpi_ok_cfg()
check(not bd_errors(cfg9),
      f"9. a bDecompose binary that is there and is this platform's format "
      f"raises no bDecompose error (control) ({bd_errors(cfg9)})")

cfg10 = SolverConfig()
cfg10.case_name = "alpha"
cfg10.enable_decompose = False
cfg10.bdecompose_binary = gone
check(not bd_errors(cfg10),
      f"10. with decomposition OFF a missing binary is not an error — the field "
      f"is optional (control) ({bd_errors(cfg10)})")

# ── 11: the export accounts for what now lands in grid/ ──────────────────────
case11, grid11, work11 = build_case("beta")
w(os.path.join(grid11, case_files.BDECOMPOSE_INPUT), "beta.grid\nbeta.bc\n")
# What bDecompose produces, from the .bench files the one hand run left behind.
outs = ("mpi_grid.dat", "mpi_bc0.dat", "mpi_bc1.dat", "mpi_comm_map.dat",
        "beta.bc.def.mpi")
for name in outs:
    w(os.path.join(grid11, name), "produced")
plan = case_export.plan_export(case11)
dests = {i.rel for i in plan.items}
check(f"grid/{case_files.BDECOMPOSE_INPUT}" in dests,
      f"11. case_export ships grid/{case_files.BDECOMPOSE_INPUT} as an input "
      f"({sorted(d for d in dests if d.startswith('grid/'))})")
check("grid/getPGrid.in" in dests and "grid/para.in" not in dests,
      f"11. ...and getPGrid's own answer file still travels under its "
      f"self-explaining name ({sorted(dests)})")
skipped_out = {rel for rel, _sz in plan.skipped_output}
unrecognised = {rel for rel, *_r in plan.skipped_other}
for name in outs:
    rel = f"grid/{name}"
    check(rel in skipped_out,
          f"11. bDecompose's output {name} is named as a skipped OUTPUT, not as "
          f"a file nobody recognised — this toolchain produced it "
          f"(skipped_output={sorted(skipped_out)})")
    check(rel not in dests and rel not in unrecognised,
          f"11. ...and does not ship, and is not ALSO reported as unrecognised: "
          f"the package holds a case's inputs ({rel})")

# ── 12: the shared classifier is deliberately NOT widened ────────────────────
for name in ("mpi_comm_map.dat", "mpi_grid.dat", "mpi_bc0.dat"):
    check(not case_files.is_run_output(name),
          f"12. (negative control) is_run_output still says No to {name}: "
          f"case_input_paths._stage_table asks it whether to stage a table, and "
          f"for the comm map the file bDecompose PRODUCES and the file the "
          f"solver READS are the same name — teaching it mpi_* would stop #29 "
          f"staging the comm map into work/")

# ── 13: the injection behind check 12 ────────────────────────────────────────
# Not a source-reading check, so this is a real mutation of the LIVE module
# rather than of a copy of its text: patch the compiled pattern tuple, drive the
# real _stage_table, then put it back and prove the control passes. The point is
# the CONSEQUENCE (nothing staged, input.in left absolute), which check 12's
# precondition cannot show on its own.
from app.services import case_input_paths as _cip                  # noqa: E402


def stage_comm_map():
    """``(quoted, listing)`` from the real ``_stage_table`` for a comm map that
    lives outside the case, i.e. where a file dialog leaves one."""
    box = os.path.join(tmp, f"stage{len(os.listdir(tmp))}")
    work = os.path.join(box, "work")
    os.makedirs(work)
    src = os.path.join(box, "elsewhere", case_files.COMM_MAP_NAME)
    w(src, "MAP")
    quoted = _cip._stage_table(src, work, "mpi_comm_map_fn", set(),
                              lambda _m: None)
    return quoted, sorted(os.listdir(work)), src


_orig_patterns = case_files._OUTPUT_PATTERNS
case_files._OUTPUT_PATTERNS = _orig_patterns + (re.compile(r"^mpi_"),)
try:
    check(case_files.is_run_output(case_files.COMM_MAP_NAME),
          "13. (the mutation really took: is_run_output now matches the comm map)")
    bad_quoted, bad_listing, bad_src = stage_comm_map()
finally:
    # A live-module mutation must be undone on the failure path too, or every
    # check after this one is measured against a doctored classifier.
    case_files._OUTPUT_PATTERNS = _orig_patterns
check(bad_quoted == bad_src and not bad_listing,
      f"13. widening is_run_output with '^mpi_' stops #29 staging the comm map: "
      f"nothing is copied into work/ and input.in is left quoting the absolute "
      f"source path on this machine — which is why is_decompose_output is a "
      f"SEPARATE question rather than a tidier fold "
      f"(quoted={bad_quoted!r}, work={bad_listing})")
ok_quoted, ok_listing, _src = stage_comm_map()
check(ok_quoted == case_files.COMM_MAP_NAME
      and ok_listing == [case_files.COMM_MAP_NAME],
      f"13. (control, module restored) the same call stages the comm map and "
      f"quotes it by bare name ({ok_quoted!r}, {ok_listing})")

# ── 14: the comm map input.in QUOTES still ships ─────────────────────────────
# The issue is explicit: "case_export must keep shipping the comm map either
# way." #37's grid-output branch ``continue``d BEFORE ``elif rel in referenced``
# could be reached, so a comm map the run actually reads stopped travelling and
# picked up the restart-specific "deliberately NOT exported" warning — prose
# that is simply false about a comm map. Check 11 cannot see this: build_case's
# input.in quotes only the grid, so every file it lists is UNREFERENCED, and
# "does not ship" is the correct answer there. The two checks together are what
# pin the carve-out: drop ``and rel not in referenced`` from plan_export and
# this one goes red while 11 stays green. BEHAVIOURAL, verified by reverting
# that condition by hand — which is not an in-test injection and is not
# written down as one.
case14, grid14, work14 = build_case("gamma")
w(os.path.join(grid14, case_files.COMM_MAP_NAME), "produced")
w(os.path.join(grid14, "mpi_grid.dat"), "produced")
w(os.path.join(work14, "input.in"),
  'grid_fn "../grid/gamma.grid"\n'
  'mpi_comm_map_fn "../grid/%s"\n' % case_files.COMM_MAP_NAME)
plan14 = case_export.plan_export(case14)
dests14 = {i.rel for i in plan14.items}
skipped14 = {rel for rel, _sz in plan14.skipped_output}
rel14 = f"grid/{case_files.COMM_MAP_NAME}"
check(rel14 in dests14 and rel14 not in skipped14,
      f"14. a comm map input.in quotes SHIPS - the issue's third consequence, "
      f"'case_export must keep shipping the comm map either way' "
      f"(grid items={sorted(d for d in dests14 if d.startswith('grid/'))}, "
      f"skipped={sorted(skipped14)})")
check(not any("NOT exported" in m for m in plan14.warnings),
      f"14. ...and no 'deliberately NOT exported' warning is emitted for it: "
      f"that prose is restart-specific and false about a comm map "
      f"({plan14.warnings})")
check("grid/mpi_grid.dat" in skipped14,
      f"14. (control) an UNreferenced decompose output in the SAME case is "
      f"still named as a skipped output, so the carve-out is the reference and "
      f"not the pattern ({sorted(skipped14)})")

shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED")
    for m in _FAILS:
        print("  - " + m)
    sys.exit(1)
print("\nRESULT: ALL PASS")
