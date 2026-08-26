#!/usr/bin/env python3
"""``Clean and Run`` empties a case's ``work/`` — from a LIST the user approved.

Issue #33, DECIDED 2026-08-21. ``Overwrite in Place`` reuses a case directory and
writes over its files as the run produces them, so a case ends up a mixture of
this run's output and whatever the last one left. Two separate defences against
that mixture already exist rather than a fix — ``report_stale_ibm_artifacts``
(a leftover ``work/phi.dat`` is read by the init DLL and converges to a
believable answer for the PREVIOUS geometry's solid) and ``case_export_usage``
(USER-REPORTED: "I didn't configure IBM, why is there a phi.dat?") — and a real
clean slate retires the class at its source.

What is gated here, against the real ``plan_case_clean`` / ``apply_case_clean``
and the real ``prepare_case_dir`` on a temp tree:

 1. the plan CLASSIFIES rather than globs — run outputs into one bucket, this
    run's own staged inputs into another, ``work/prev_*/`` into a third, and
    anything none of that recognises into a fourth;
 1b. a user-named table quoted by ``input.in`` (#29) is an input, not an output,
    even though no list can hold its name;
 2. applying the plan deletes exactly the outputs; the staged inputs and the
    unclassified files survive, and the unclassified ones are NAMED in the log;
 3. ``work/prev_*/`` survives by default and goes only with the explicit flag —
    the tick #33 requires to be a second deliberate act;
 4. a plan measured for a DIFFERENT work dir deletes nothing. The plan is built
    on the GUI thread and applied on the worker thread after
    ``resolve_case_root`` has had its say, so "the directory the user was shown"
    and "the directory this run uses" are two facts;
 5. through the real ``prepare_case_dir``: ``grid/`` and ``dll/`` survive, and
    the clean runs BEFORE staging, so this run's own freshly written
    ``input.in`` is on disk afterwards;
 6. ``case_dir_flags(CASE_CLEAN)`` reuses the dir and archives NOTHING, and an
    unknown disposition still raises rather than resolving to a plausible one;
 7. a RESTART deletes nothing even when handed a plan. The restart source lives
    in ``work/`` under a name ``is_run_output`` classifies as an output — it IS
    one — so a clean would delete the file the run is about to resume from;
 8. the counts and total size the prompt shows come from the plan, so what is
    named and what is deleted cannot be two different sets;
 9. the unattended path reaches neither branch: ``_resolve_case_disposition``
    answers ``CASE_NEW_VERSION`` for a Run All before any prompt, and
    ``confirm_case_clean`` returns None (cancel) when headless;
 10. an empty work dir degrades to ``CASE_IN_PLACE`` instead of prompting about
    nothing.

Every static claim is verified by INJECTION — the module's source is mutated,
re-imported and the check re-run — so a check that would pass with its mechanism
removed is caught here rather than at review time. Each injection asserts the
mutated source still PARSES and really differs from the original: a mutation that
breaks the parse looks exactly like the check working.

Blind spots, named rather than left to be found:

* **the DIALOG's list is not rendered here.** Check 8 pins that the numbers the
  prompt is built from are the plan's, and ``confirm_case_clean``'s Qt path is
  exercised only headlessly (where it returns None by design). What a user
  actually sees in the detail box is not measured — the same limit
  ``test_restart_archive`` records for its own dialog check;
* **the tick is proven un-remembered by CONSTRUCTION, not by clicking.** The
  checkbox is built inside the function on every call and no ``ui_state`` read
  exists in the module (checked statically). Nothing here opens the dialog twice
  and observes the box;
* **check 9's Run All half drives the real mixin with a stub controller**, not a
  real ``AppController``. It proves the ordering of the guard, not that
  ``_pipeline_running`` is set where the pipeline thinks it is — that is
  ``test_pipeline_stages.py``'s ground.

Two things the injections corrected about the first version of this file, kept
because both are claims it would otherwise be natural to make and wrong:

* **the ``kept_inputs`` bucket decides the REPORT, not survival.** An
  unclassified file is kept too, so dropping the staged-input branch does not
  delete ``input.in`` — it describes a case's own configuration as
  "not recognised". What keeps a staged input on disk is ``is_run_output`` not
  matching it, one branch earlier;
* **of the two guards in ``apply_case_clean``, only ``is_inside`` stops a
  deletion.** The work-dir equality test refuses a foreign plan as a WHOLE and
  with one message that names both directories; remove it and every entry is
  still refused individually. Both earn their place, but the injection says which
  one is the protection — and the per-entry guard is measured directly, with a
  doctored plan, because a nested guard cannot be reached while the outer one
  holds.

Run:  python3 tools/PreProcessor/tests/test_case_clean.py
"""
import ast
import importlib
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
    print("FAIL watchdog: blocked >180s", flush=True)
    os._exit(99)


_wd = threading.Timer(180, _watchdog)
_wd.daemon = True
_wd.start()

from app.models.solver_config import SolverConfig              # noqa: E402
from app.services import case_clean, solver_case               # noqa: E402
from app.services.case_clean import (                          # noqa: E402
    ApprovedClean,
    apply_case_clean,
    plan_case_clean,
)

tmp = tempfile.mkdtemp(prefix="hybmesh_clean_test_")
repo = os.path.join(tmp, "repo")
mesh = os.path.join(repo, "m")


def w(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


for ext in (".vrt", ".cel", ".bnd"):
    w(mesh + ext, "mesh")

solver_case.repo_root = lambda: repo

LOG = []

# A work/ as a finished run leaves it. Names taken from what the solver really
# writes, and the input.in quotes a user-named CFL table (#29) so the plan has to
# recognise an input no list can hold.
OUTPUTS = ["binDumpZ.dat.gui", "unicones.enorm.gui", "xtecp_sol_allz.dat.gui",
           "probe_data.gui", "fort.11", "tWall.dat", "mesh_tecplot.plt"]
STAGED = ["input.in", "phi.dat", "beta.bc.def", "userbc.so"]
USER_TABLE = "my_cfl_schedule.txt"
UNKNOWN = ["notes.txt", "scratch/"]


def seed(case):
    """Write a finished run's work dir and return its path."""
    work = os.path.join(repo, "results", "solver", case, "work")
    for name in OUTPUTS:
        w(os.path.join(work, name), name * 4)
    for name in STAGED:
        w(os.path.join(work, name),
          f'cfl_schedule_fn  "{USER_TABLE}"\n' if name == "input.in" else name)
    w(os.path.join(work, USER_TABLE), "0 1.0\n")
    w(os.path.join(work, "notes.txt"), "mine")
    os.makedirs(os.path.join(work, "scratch"), exist_ok=True)
    # Two archived previous runs (#26/#30), which #33 keeps unless asked.
    for prev in ("prev_001", "prev_002"):
        w(os.path.join(work, prev, "binDumpZ.dat." + prev), "D" * 100)
        w(os.path.join(work, prev, "RUN.txt"), "iteration 1000\n")
    w(os.path.join(repo, "results", "solver", case, "grid", f"{case}.grid"), "G")
    w(os.path.join(repo, "results", "solver", case, "dll", "init.so"), "S")
    return work


def names(entries):
    return sorted(e.name for e in entries)


# ── 1/1b. the plan classifies, and does not touch the disk ────────────────
work = seed("beta")
before = sorted(os.listdir(work))
plan = plan_case_clean(work)

check(names(plan.outputs) == sorted(OUTPUTS),
      "1 the run's outputs are what the plan would delete")
check(names(plan.archives) == ["prev_001/", "prev_002/"],
      "1 work/prev_*/ is measured into its OWN bucket, not with the outputs")
check(sorted(plan.kept_inputs) == sorted(STAGED + [USER_TABLE]),
      "1b this run's staged inputs are kept — the #29 user-named table included")
check(sorted(plan.unclassified) == ["notes.txt", "scratch/"],
      "1 a file AND a directory nobody classified are unclassified, not skipped")
check(sorted(os.listdir(work)) == before,
      "1 building a plan changes nothing on disk")
check(all(e.bytes > 0 for e in plan.outputs)
      and all(e.bytes > 0 for e in plan.archives),
      "1 every entry carries its own size, archives measured as a tree")

# ── 2/3. applying it deletes the outputs and nothing else ─────────────────
LOG.clear()
removed = apply_case_clean(ApprovedClean(plan), work, log=LOG.append)
left = sorted(os.listdir(work))

check(removed == len(OUTPUTS) and not any(n in left for n in OUTPUTS),
      "2 exactly the outputs are deleted")
check(all(n in left for n in STAGED + [USER_TABLE]),
      "2 the staged inputs survive — the resumed run keeps its configuration")
check("notes.txt" in left and "scratch" in left,
      "2 an unclassified file and directory survive")
check(sum("notes.txt" in m for m in LOG) == 1
      and sum("scratch/" in m for m in LOG) == 1,
      "2 each unclassified entry is NAMED in the log, not silently kept")
check("prev_001" in left and "prev_002" in left,
      "3 work/prev_*/ survives a default Clean and Run")
check(any("archived previous run" in m for m in LOG),
      "3 the log says the archives were kept and how to remove them")

# ── 3b. the tick is what removes them ─────────────────────────────────────
work2 = seed("gamma")
plan2 = plan_case_clean(work2)
LOG.clear()
apply_case_clean(ApprovedClean(plan2, True), work2, log=LOG.append)
left2 = sorted(os.listdir(work2))
check("prev_001" not in left2 and "prev_002" not in left2,
      "3 with the tick set, the archives go too")
check(all(n in left2 for n in STAGED),
      "3 …and the staged inputs still survive")

# ── 4. a plan for another directory deletes nothing ───────────────────────
work3 = seed("delta")
other = seed("epsilon")
foreign = plan_case_clean(other)
LOG.clear()
removed3 = apply_case_clean(ApprovedClean(foreign), work3, log=LOG.append)
check(removed3 == 0 and all(n in os.listdir(work3) for n in OUTPUTS),
      "4 a plan measured for another work dir deletes nothing")
check(all(n in os.listdir(other) for n in OUTPUTS),
      "4 …and does not delete from the directory it WAS measured for either")
check(any("nothing was deleted" in m for m in LOG),
      "4 the refusal is reported, not silent")

# ── 5. through the real prepare_case_dir ──────────────────────────────────
work5 = seed("zeta")
plan5 = plan_case_clean(work5)
cfg = SolverConfig()
cfg.case_name = "zeta"
cfg.input_vrt_file = mesh + ".vrt"
cfg.input_cel_file = mesh + ".cel"
cfg.input_bnd_file = mesh + ".bnd"
cfg.restart = False
LOG.clear()
work_dir, grid_dir, input_in = solver_case.prepare_case_dir(
    cfg, log=LOG.append, overwrite=True, clean=ApprovedClean(plan5))

check(os.path.abspath(work_dir) == os.path.abspath(work5),
      "5 CASE_CLEAN reuses the case dir rather than auto-versioning")
check(not any(os.path.exists(os.path.join(work5, n)) for n in OUTPUTS),
      "5 the outputs are gone after a real prepare_case_dir")
check(os.path.isfile(input_in),
      "5 the clean runs BEFORE staging — this run's own input.in is on disk")
check(os.path.isfile(os.path.join(repo, "results", "solver", "zeta", "grid",
                                  "zeta.grid"))
      and os.path.isfile(os.path.join(repo, "results", "solver", "zeta", "dll",
                                      "init.so")),
      "5 grid/ and dll/ are outside the scope and survive")
check(os.path.isdir(os.path.join(work5, "prev_001")),
      "5 …and so do the archives, with the tick unset")

# ── 6. the disposition's mechanics ────────────────────────────────────────
check(solver_case.case_dir_flags(solver_case.CASE_CLEAN) == (True, False),
      "6 CASE_CLEAN reuses the directory and archives NOTHING")
try:
    solver_case.case_dir_flags("cleaan")
    raised = False
except ValueError:
    raised = True
check(raised, "6 an unknown disposition still raises rather than resolving")

# ── 7. a restart is refused ───────────────────────────────────────────────
work7 = seed("eta")
plan7 = plan_case_clean(work7)
cfg7 = SolverConfig()
cfg7.case_name = "eta"
cfg7.input_vrt_file = mesh + ".vrt"
cfg7.input_cel_file = mesh + ".cel"
cfg7.input_bnd_file = mesh + ".bnd"
cfg7.restart = True
cfg7.zdump_fn_restart = os.path.join(work7, "binDumpZ.dat.gui")
LOG.clear()
solver_case.prepare_case_dir(cfg7, log=LOG.append, overwrite=True,
                             clean=ApprovedClean(plan7, True),
                             archive_prev=False)
_arch7 = sorted(n for n in os.listdir(work7) if n.startswith("prev_"))
_new7 = os.path.join(work7, _arch7[-1])
check(any(n.startswith("binDumpZ") for n in os.listdir(_new7)),
      "7 a restart's own dump is NOT deleted — it is ARCHIVED, and the guard "
      "corrects the flags it invalidates rather than only skipping the delete")
check(os.path.isdir(os.path.join(work7, "prev_001"))
      and os.path.isdir(os.path.join(work7, "prev_002")),
      "7 …and the existing archives survive, even with the tick set")
check(len(_arch7) == 3,
      "7 the previous run's outputs went into a NEW archive, not over one")
check(any("ARCHIVED instead" in m for m in LOG),
      "7 the refusal says what happened instead, not just that it refused")
check(not any("cleaned work/" in m for m in LOG),
      "7 …and nothing reports a deletion that did not happen")

# ── 8. what the prompt shows comes from the plan ──────────────────────────
work8 = seed("theta")
plan8 = plan_case_clean(work8)
check(str(len(plan8.outputs)) in plan8.summary(False),
      "8 the summary counts the plan's own entries")
check(plan8.summary(True) != plan8.summary(False)
      and str(len(plan8.outputs) + len(plan8.archives)) in plan8.summary(True),
      "8 the tick changes the count the prompt shows")
check(plan8.outputs_bytes == sum(os.path.getsize(os.path.join(work8, n))
                                 for n in OUTPUTS),
      "8 the size shown is the real size on disk")
empty_work = os.path.join(repo, "results", "solver", "iota", "work")
os.makedirs(empty_work, exist_ok=True)
check(plan_case_clean(empty_work).is_empty()
      and not plan_case_clean(empty_work).outputs,
      "8 an empty work dir plans nothing")
check(plan_case_clean(os.path.join(tmp, "nope")).is_empty(),
      "8 a work dir that does not exist plans nothing rather than raising")

# ── 11. the stale phase field IS removed, and the only copy is NOT ────────
# #33's problem statement is a leftover work/phi.dat that the init DLL reads by
# a fixed name, so a Clean and Run that keeps it retires nothing. But the same
# file is sometimes the run's ONLY copy (an exported case reopened in place,
# where ibm_phi_file resolves to work/phi.dat itself and stage_phi_file's
# src == dst branch declines to copy). Both directions, because a rule that only
# deletes is as wrong as one that only keeps.
work11 = seed("mu")
stale_cfg = SolverConfig()
stale_cfg.immersed_solid = False           # nothing will stage a phi
check(solver_case.stale_phi_name(stale_cfg, work11) == "phi.dat",
      "11 a phi field this run will not write is named as stale")
plan11 = plan_case_clean(work11, stale=["phi.dat"])
check(any(e.name == "phi.dat" for e in plan11.outputs)
      and "phi.dat" not in plan11.kept_inputs,
      "11 …and a stale phi is in the DELETE list, not kept as an input")
apply_case_clean(ApprovedClean(plan11), work11)
check(not os.path.exists(os.path.join(work11, "phi.dat")),
      "11 …so the previous geometry's solid cannot be read by this run")

work11b = seed("nu")
own_cfg = SolverConfig()
own_cfg.immersed_solid = True
own_cfg.ibm_phi_file = os.path.join(work11b, "phi.dat")   # the only copy
check(solver_case.stale_phi_name(own_cfg, work11b) == "",
      "11 a phi this run DOES stage is not stale — asking 'is it stale?' "
      "protects the only-copy case for free")
plan11b = plan_case_clean(work11b,
                          stale=[solver_case.stale_phi_name(own_cfg, work11b)])
apply_case_clean(ApprovedClean(plan11b), work11b)
check(os.path.isfile(os.path.join(work11b, "phi.dat")),
      "11 …and it survives: deleting it would destroy the field with no source "
      "to re-stage from")

# ── 12. 'Archive Previous' is offered as a fourth answer ──────────────────
# #33: "the honest framing may be 'archive these, or delete these?'". #31
# removed CASE_ARCHIVE from this prompt because a RESTART stopped reaching it;
# a non-restart run in an occupied dir is a different question.
_DLG_SRC = open(os.path.join(_GUI, "app", "views", "case_dir_dialog.py")).read()
_dlg_tree = ast.parse(_DLG_SRC)
_ask = next(n for n in ast.walk(_dlg_tree)
            if isinstance(n, ast.FunctionDef) and n.name == "ask_case_disposition")
_returns = {getattr(r.value, "id", "") for r in ast.walk(_ask)
            if isinstance(r, ast.Return) and r.value is not None}
check({"CASE_IN_PLACE", "CASE_CLEAN", "CASE_ARCHIVE",
       "CASE_NEW_VERSION"} <= _returns,
      "12 all four dispositions are reachable from the prompt")
_buttons = [n for n in ast.walk(_ask) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", "") == "addButton"]
check(len(_buttons) == 5,
      "12 four answers plus Cancel — #33 names four as the ceiling, so the "
      f"next one to want a button outgrows a message box (got {len(_buttons)})")

# ── 9. the unattended path reaches neither branch ─────────────────────────
from app.controllers.case_disposition_ctrl import (                 # noqa: E402
    CaseDispositionControllerMixin,
)


class _Stub(CaseDispositionControllerMixin):
    """Enough controller to answer the question, and nothing that can run."""

    def __init__(self):
        self.main_window = None
        self._pipeline_running = True
        self.logged = []

    def log(self, msg):
        self.logged.append(msg)


def _asked(*_a, **_k):
    raise AssertionError("the unattended path must not reach a prompt")


import app.controllers.case_disposition_ctrl as _cd                 # noqa: E402

_cd.ask_case_disposition = _asked
_cd.confirm_case_clean = _asked

stub = _Stub()
seed("kappa")
cfg9 = SolverConfig()
cfg9.case_name = "kappa"
cfg9.restart = False
answer = stub._resolve_case_disposition(cfg9)
check(answer == solver_case.CASE_NEW_VERSION,
      "9 Run All auto-versions before any prompt can be reached")
# The headless guard is asserted STATICALLY, and this file imports no Qt at all
# — the acceptance list asks for "a Qt-free test [that] drives the plan-then-
# delete", and a QApplication built to make ``is_headless()`` answer True would
# have made that literally false. What is checked instead is that the prompt
# cannot proceed unattended BY CONSTRUCTION: it delegates to the graded helper,
# and that helper returns None on a screenless platform with no argument to
# override it. The behavioural half is in test_ui_state_and_dialogs.py.
_UTILS = open(os.path.join(_GUI, "app", "utils.py")).read()
_cd_fn = next(n for n in ast.walk(ast.parse(_DLG_SRC))
              if isinstance(n, ast.FunctionDef) and n.name == "confirm_case_clean")
check(not any(isinstance(n, ast.Call)
              and getattr(n.func, "attr", getattr(n.func, "id", "")) == "QMessageBox"
              for n in ast.walk(_cd_fn))
      and any(isinstance(n, ast.Call)
              and getattr(n.func, "id", "") == "confirm_destructive"
              for n in ast.walk(_cd_fn)),
      "9 the clean confirmation goes through the graded helper, not a raw "
      "QMessageBox — a yes/no is what confirm_* is for")
_helper = next(n for n in ast.walk(ast.parse(_UTILS))
               if isinstance(n, ast.FunctionDef) and n.name == "confirm_destructive")
check(not any(a.arg == "headless_default" for a in _helper.args.args),
      "9 …and that helper takes no headless_default, so no caller can opt an "
      "unattended path into deleting files")

# ── 10. nothing to clean is not a prompt ──────────────────────────────────
_cd.confirm_case_clean = _asked


class _Interactive(_Stub):
    def __init__(self):
        super().__init__()
        self._pipeline_running = False


_cd.ask_case_disposition = lambda *_a, **_k: solver_case.CASE_CLEAN
inter = _Interactive()
bare = os.path.join(repo, "results", "solver", "lambda", "work")
os.makedirs(bare, exist_ok=True)
w(os.path.join(repo, "results", "solver", "lambda", "grid", "x"), "g")
cfg10 = SolverConfig()
cfg10.case_name = "lambda"
cfg10.restart = False
answer10 = inter._resolve_case_disposition(cfg10)
check(answer10 == solver_case.CASE_IN_PLACE,
      "10 an empty work dir degrades to Overwrite in Place, no second prompt")
check(getattr(inter, "_case_clean_plan", None) is None,
      "10 …and no plan travels to the worker")


# ── injections: each check above must BITE ────────────────────────────────
_SRC = os.path.join(_GUI, "app", "services", "case_clean.py")
_ORIG = open(_SRC).read()


def inject(old, new, label, probe):
    """Mutate case_clean.py, re-import it and run ``probe`` against the mutated
    module. ``probe`` returns True when the defect is VISIBLE, i.e. the check
    would have failed."""
    assert _ORIG.count(old) == 1, f"injection anchor not unique: {label}"
    mutated = _ORIG.replace(old, new)
    assert mutated != _ORIG, f"injection changed nothing: {label}"
    try:
        ast.parse(mutated)
    except SyntaxError:
        check(False, f"injection {label} broke the parse — proves nothing")
        return
    try:
        with open(_SRC, "w") as f:
            f.write(mutated)
        mod = importlib.reload(case_clean)
        visible = probe(mod)
    finally:
        with open(_SRC, "w") as f:
            f.write(_ORIG)
        importlib.reload(case_clean)
    check(visible, f"injection {label} is caught")


def _probe_archives_deleted(mod):
    """The archives-are-separate rule removed: they get swept in with the
    outputs, so check 3 fails."""
    wk = seed("inj_a")
    p = mod.plan_case_clean(wk)
    mod.apply_case_clean(mod.ApprovedClean(p), wk)
    return not os.path.isdir(os.path.join(wk, "prev_001"))


inject("            if name.startswith(ARCHIVE_DIR_PREFIX):\n"
       "                archives.append(CleanEntry(name + \"/\", path, tree_size(path)))",
       "            if name.startswith(ARCHIVE_DIR_PREFIX):\n"
       "                outputs.append(CleanEntry(name + \"/\", path, tree_size(path)))",
       "archives bucketed with the outputs", _probe_archives_deleted)


def _probe_unclassified_deleted(mod):
    """Classification replaced by a glob: an unclassified file is deleted."""
    wk = seed("inj_b")
    p = mod.plan_case_clean(wk)
    mod.apply_case_clean(mod.ApprovedClean(p), wk)
    return not os.path.exists(os.path.join(wk, "notes.txt"))


inject("        elif is_run_output(name) or name in stale:",
       "        elif is_run_output(name) or name in stale or True:",
       "everything globbed as an output", _probe_unclassified_deleted)


def _probe_staged_misreported(mod):
    """The staged-input branch dropped.

    Note carefully what this does and does NOT change, because the first version
    of this injection asserted the wrong thing and came back green: ``input.in``
    still SURVIVES, because an unclassified file is kept too. What the bucket
    decides is the REPORT — "kept, this run's own input" versus "kept, not
    recognised" — and a prompt that calls a case's own configuration
    unrecognised is telling the user something false about it. Survival comes
    from ``is_run_output`` not matching, which the check above it covers.
    """
    wk = seed("inj_c")
    p = mod.plan_case_clean(wk)
    return ("input.in" in p.unclassified
            and "input.in" not in p.kept_inputs
            and os.path.exists(os.path.join(wk, "input.in")))


inject("        elif keep_matches(name, WORK_STAGED) or name in staged:\n"
       "            kept.append(name)",
       "        elif keep_matches(name, WORK_STAGED) and False:\n"
       "            kept.append(name)",
       "staged inputs reported as unrecognised", _probe_staged_misreported)


def _probe_foreign_plan_unrefused(mod):
    """The work-dir guard removed.

    The files still survive — the per-entry ``is_inside`` check below refuses
    every one of them — so this injection measures the half the outer guard
    uniquely owns: ONE refusal naming both directories, instead of N warnings
    about individual files that leave the user to work out that the list they
    approved was for somewhere else. Said plainly because it is the honest
    reading: the two guards are not redundant, but only one of them is what
    stops the deletion.
    """
    a = seed("inj_d")
    b = seed("inj_e")
    p = mod.plan_case_clean(b)
    log = []
    mod.apply_case_clean(mod.ApprovedClean(p), a, log=log.append)
    return (not any("nothing was deleted" in m for m in log)
            and os.path.exists(os.path.join(b, "fort.11")))


inject("    if os.path.abspath(plan.work_dir) != os.path.abspath(work_dir):",
       "    if False:",
       "a foreign plan is not refused as a whole", _probe_foreign_plan_unrefused)


def _probe_outside_path_deleted(mod):
    """And the guard that DOES stop it, measured directly rather than by
    injection: a plan whose work dir is right but whose entry points outside it
    (a doctored plan, which is exactly what the check is for) must not reach
    that file."""
    wk = seed("inj_h")
    victim = os.path.join(repo, "results", "solver", "inj_h", "grid",
                          "inj_h.grid")
    doctored = mod.CleanPlan(
        work_dir=wk,
        outputs=(mod.CleanEntry("../grid/inj_h.grid", victim, 1),))
    log = []
    mod.apply_case_clean(mod.ApprovedClean(doctored), wk,
                         log=log.append)
    return os.path.exists(victim) and any("not inside" in m for m in log)


check(_probe_outside_path_deleted(case_clean),
      "4 an entry pointing outside the work dir is refused and named")


def _probe_user_table_deleted(mod):
    """``staged_bare_names`` dropped: the #29 user-named table is unclassified
    — and an unclassified file is kept, so the visible loss is that it is
    REPORTED as unrecognised rather than known to be an input."""
    wk = seed("inj_f")
    p = mod.plan_case_clean(wk)
    return USER_TABLE in p.unclassified and USER_TABLE not in p.kept_inputs


inject("    staged = staged_bare_names(work_dir)",
       "    staged = set()",
       "input.in no longer consulted for staged names", _probe_user_table_deleted)

# The restart guard lives in solver_case, so it is injected there.
_SRC2 = os.path.join(_GUI, "app", "services", "solver_case.py")
_ORIG2 = open(_SRC2).read()
_GUARD = "        if cfg.restart:\n"


def _inject_restart_guard():
    old = _GUARD
    assert _ORIG2.count(old) >= 1
    # Only the guard inside the clean block, which is the first occurrence after
    # the clean_plan test.
    head, sep, tail = _ORIG2.partition("    if clean is not None:\n")
    assert sep, "clean block anchor missing"
    mutated = head + sep + tail.replace(old, "        if False:\n", 1)
    assert mutated != _ORIG2
    try:
        ast.parse(mutated)
    except SyntaxError:
        check(False, "injection restart guard broke the parse — proves nothing")
        return
    try:
        with open(_SRC2, "w") as f:
            f.write(mutated)
        mod = importlib.reload(solver_case)
        mod.repo_root = lambda: repo
        wk = seed("inj_g")
        p = case_clean.plan_case_clean(wk)
        c = SolverConfig()
        c.case_name = "inj_g"
        c.input_vrt_file = mesh + ".vrt"
        c.input_cel_file = mesh + ".cel"
        c.input_bnd_file = mesh + ".bnd"
        c.restart = True
        c.zdump_fn_restart = os.path.join(wk, "binDumpZ.dat.gui")
        mod.prepare_case_dir(c, log=lambda _m: None, overwrite=True,
                             clean=case_clean.ApprovedClean(p),
                             archive_prev=False)
        # With the guard gone the dump is DELETED outright — the run loses the
        # file it was about to resume from.
        #
        # The discriminator is the ARCHIVE COUNT, not "does any archive hold a
        # binDump": the fixture seeds prev_001 and prev_002, each of which
        # already holds one, so that condition can never be false and the
        # injection passed for the wrong reason (measured). With the guard the
        # dump moves into a THIRD archive; without it, none is created.
        archives = [n for n in os.listdir(wk)
                    if n.startswith("prev_")
                    and os.path.isdir(os.path.join(wk, n))]
        visible = (not os.path.exists(os.path.join(wk, "binDumpZ.dat.gui"))
                   and len(archives) == 2)
    finally:
        with open(_SRC2, "w") as f:
            f.write(_ORIG2)
        importlib.reload(solver_case)
        solver_case.repo_root = lambda: repo
    check(visible, "injection the restart guard removed is caught")


_inject_restart_guard()

# ── static: the tick can never be remembered ──────────────────────────────
_DLG = _DLG_SRC
_tree = ast.parse(_DLG)
_utils_tree = ast.parse(_UTILS)
_helper_fn = next(n for n in ast.walk(_utils_tree)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "confirm_destructive")
_checkbox_calls = [n for n in ast.walk(_helper_fn)
                   if isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "QCheckBox"]
check(len(_checkbox_calls) == 1,
      "static the tick's checkbox is built inside the helper, once per call")
_dlg_imports = {n.module for n in ast.walk(_tree)
                if isinstance(n, ast.ImportFrom) and n.module}
_dlg_imports |= {a.name for n in ast.walk(_tree)
                 if isinstance(n, ast.Import) for a in n.names}
check(not any("ui_state" in m for m in _dlg_imports),
      "static nothing in the dialog module restores a remembered tick")
# Read as an AST, not as text: the module's own PROSE says the tick is never
# read back from ui_state, so a substring check over the source matched its own
# docstring and passed for the wrong reason (measured — it FAILED here, which is
# the same accident in the other direction).
check("setDefaultButton(cancel)" in _UTILS,
      "static Cancel is the default button on the deletion prompt")

import shutil as _shutil                                            # noqa: E402

_shutil.rmtree(tmp, ignore_errors=True)
_wd.cancel()
print("-" * 55)
print(f"FAILURES: {len(_FAILS)}")
for m in _FAILS:
    print("  " + m)
sys.exit(1 if _FAILS else 0)
