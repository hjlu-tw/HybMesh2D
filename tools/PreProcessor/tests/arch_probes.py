#!/usr/bin/env python3
"""Architecture backlog status, re-derived from the tree. Not a test.

Run:  python3 tools/PreProcessor/tests/arch_probes.py

The candidates come from ``docs/architecture_review_2026-08-14.md``, which is
FROZEN — it is the rationale (file:line evidence, deletion tests, the "leave these
alone" list) and it deliberately never learns what has since been done. This file
is the other half: it answers "what is left?" by measuring, so the answer cannot
go stale between sessions.

WHY THIS EXISTS. Reviewing that document on 2026-08-17 recommended a batch of
three, and two of the three were already finished — including its own top
recommendation, landed in six commits the document could not know about.
Re-deriving the status by hand took six rounds of measurement and still got one
candidate wrong on the first pass, because the signal that it was done (a leak
count of 148 where the document said 389) was explained away as a measurement
artefact. A written-down status decays in silence; a computed one cannot.

HOW A PROBE IS SUPPOSED TO BEHAVE.

* It reports the NUMBER that decides the answer, never a bare verdict. A number
  that has moved without crossing the line is the interesting case — it is what
  distinguishes "nobody has started" from "half of it landed and the document
  still says 389".
* DONE names the GATE that now guards the property. Once real work lands it
  leaves a test behind (``test_sidebar_seam.py``, ``test_cpp_linkable_seam.py``),
  and from that moment the gate is the authority — the probe retires to a pointer
  at it rather than keeping a second, weaker opinion that could disagree.
* STALE is a real answer. A candidate whose PREMISE evaporated is not done and is
  not open; saying so is how the backlog stops carrying work that no longer
  exists.
* A probe is cheap and reads only source. Nothing here needs a build tree, a Qt
  display, or the mesher binary, because a status check that can be skipped is a
  status check that will be.

NOT A TEST, ON PURPOSE. ``run_all.sh`` globs ``test_*.py`` and ``smoke_*.py``;
this file matches neither, and its exit code is 0 whatever the candidates say. An
OPEN candidate is a decision not yet taken, not a regression — wiring it to a red
build would make the backlog into a permanently failing gate, which this repo has
already recorded as worse than no gate at all. Exit 1 means a PROBE broke.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GUI = os.path.join(REPO, "tools", "PreProcessor", "gui")
APP = os.path.join(GUI, "app")
TESTS = HERE

DONE, OPEN, STALE = "DONE ", "OPEN ", "STALE"


def read(*parts: str) -> str:
    """File contents, or "" when the file is gone (a deletion is an answer)."""
    try:
        with open(os.path.join(*parts), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def walk_py(root: str, skip=()):
    for dirpath, _dirs, files in os.walk(root):
        if any(s in dirpath.split(os.sep) for s in skip):
            continue
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def count_across(root: str, pattern: str, skip=()) -> tuple[int, int]:
    """(total matches, distinct group-1 values) of `pattern` under `root`."""
    rx = re.compile(pattern)
    total, names = 0, set()
    for path in walk_py(root, skip):
        for m in rx.finditer(read(path)):
            total += 1
            if m.groups():
                names.add(m.group(1))
    return total, len(names)


# ── The probes ──────────────────────────────────────────────────────────────
# Each returns (state, detail). Keep the detail short: it is read as a column.


def probe_1_sidebar_seam():
    """DONE when the forwarder is gone AND a gate keeps it gone.

    Both halves are required and that is the lesson the gate's own docstring
    records: a static allow-list can be edited by whoever trips it, and a deleted
    ``__getattr__`` cannot be worked around at all, but only the list stops a new
    caller reaching a widget through a panel it names directly.
    """
    sidebar = read(APP, "views", "sidebar.py")
    gate = read(TESTS, "test_sidebar_seam.py")
    forwarder = re.search(r"^\s*def __getattr__", sidebar, re.M) is not None
    if gate and not forwarder:
        return DONE, "gated by test_sidebar_seam.py; Sidebar.__getattr__ deleted"
    if forwarder:
        return OPEN, "Sidebar.__getattr__ still forwards unknown attributes"
    return OPEN, "forwarder gone but no gate — a new leak would not be caught"


def probe_2_mesher_seam():
    """DONE when the implementation is a library the tests can link.

    The executable compiling no implementation is the property; a test that lists
    ``src/*.cpp`` would link a SECOND build of the mesher and pass while the seam
    was gone, which is why the gate is the authority here and not this probe.
    """
    cmake = read(REPO, "CMakeLists.txt")
    gate = read(TESTS, "test_cpp_linkable_seam.py")
    lib = "add_library(hybmesh_core" in cmake
    testing = "enable_testing()" in cmake
    cpp = [f for f in os.listdir(os.path.join(REPO, "tests", "cpp"))
           if f.endswith(".cpp")] if os.path.isdir(
               os.path.join(REPO, "tests", "cpp")) else []
    if lib and testing and cpp and gate:
        return DONE, (f"hybmesh_core + hybmesh_pure, {len(cpp)} C++ tests; "
                      "gated by test_cpp_linkable_seam.py + test_cpp_pure_layer.py")
    missing = [n for n, ok in (("add_library", lib), ("enable_testing", testing),
                               ("tests/cpp/*.cpp", bool(cpp)), ("gate", bool(gate)))
               if not ok]
    return OPEN, "missing: " + ", ".join(missing)


def probe_3_param_schema():
    """How many places must agree to add one mesh parameter.

    Counted by tracing a real parameter rather than by counting declaration
    sites in the abstract — a schema is only reached when the count falls to one
    or two, and a partial cleanup shows up here as a falling number.
    """
    probe_key = "BL_JUNCTION_ANGLE_C2"
    hits = []
    for root, skip in ((os.path.join(REPO, "include"), ()),
                       (os.path.join(REPO, "src"), ()),
                       (APP, ("tests",))):
        for dirpath, _d, files in os.walk(root):
            for f in files:
                if f.endswith((".py", ".cpp", ".hpp")) and probe_key in read(
                        dirpath, f):
                    hits.append(os.path.relpath(os.path.join(dirpath, f), REPO))
    branches = read(REPO, "include", "Config.hpp").count('key == "')
    state = DONE if len(hits) <= 2 else OPEN
    return state, (f"{probe_key} declared in {len(hits)} files; "
                   f"{branches} `key ==` branches in Config.hpp")


def probe_4_signal_wiring():
    """The review's premise here was the hand-listed 35 spin boxes at :67-77.

    That region is now the shape-tool menu and the shape fields are wired from
    ``shape_spec``'s own parameter table, so the candidate as WRITTEN no longer
    describes the file. What is left is reported instead of being scored against
    a premise that has gone.
    """
    src = read(APP, "controllers", "signal_wiring_ctrl.py")
    if not src:
        return DONE, "signal_wiring_ctrl.py no longer exists"
    lines = len(src.splitlines())
    sb = len(set(re.findall(r"\bsb\.([A-Za-z_]\w*)", src)))
    mw = len(set(re.findall(r"\b(?:mw|self\.main_window)\.([A-Za-z_]\w*)", src)))
    handlisted = bool(re.search(r"for\s+\w+\s+in\s*\(\s*[\"']\w+_spin", src))
    if not handlisted:
        return STALE, (f"premise gone (no hand-listed spin boxes); {lines} lines, "
                       f"{sb} sidebar verbs, {mw} main_window names remain")
    return OPEN, f"{lines} lines, hand-listed widget names still present"


def probe_5_field_spec_tables():
    """Attributes the build halves assign vs the AST test that reconciles them.

    Counted as every ``self.x =`` in a build mixin, NOT as assignments whose
    right-hand side names a widget class. The first version of this probe did the
    latter and reported 34 where the true figure is 138: the solver mixins build
    their widgets through local factory helpers (``_edit()``, ``_check()``), so a
    class-name pattern matched 1 assignment out of 49 in one file and 29 out of 53
    in another — an authoritative-looking number measuring almost nothing. A build
    mixin assigns essentially nothing but widgets, so the crude count is the
    faithful one here.
    """
    panels = os.path.join(APP, "views", "panels")
    assigned = 0
    for f in ("solver_config_build_mixin.py", "solver_config_build_mixin_b.py",
              "mesh_config_build_mixin.py"):
        assigned += len(re.findall(r"^\s+self\.\w+\s*=", read(panels, f), re.M))
    ast_gate = len(read(TESTS, "test_panel_model_sync.py").splitlines())
    state = DONE if ast_gate == 0 else OPEN
    return state, (f"{assigned} attrs assigned across 3 build mixins, read back by "
                   f"the sync halves; test_panel_model_sync.py is {ast_gate} lines "
                   "of AST proving the lists agree")


def probe_6_pipeline_stage_seam():
    """Two questions: does the IB artefact reach the solve, and is there one stage list?

    The hand-off is the defect half and is fixable alone; the unification of the
    blocking and threaded runners is the architectural half. They are reported
    together because fixing only the first must not read as closing the candidate.
    """
    runner = read(APP, "services", "pipeline_runner.py")
    sig = re.search(r"def _run_solver\((.*?)\)\s*->", runner, re.S)
    phi_passed = bool(sig and "phi" in sig.group(1))
    gui = read(APP, "controllers", "pipeline_ctrl.py")
    gui_ib = "_pipe_stl3d" in gui
    if phi_passed and gui_ib:
        return DONE, "phi reaches _run_solver; both hosts run the IB stage"
    bits = []
    if not phi_passed:
        bits.append("out['phi'] never reaches _run_solver (defect)")
    if not gui_ib:
        bits.append("GUI Run All has no IB stage (recorded asymmetry)")
    return OPEN, "; ".join(bits)


def probe_7_pending_edit_owner():
    """Modal edit state still declared on the god object."""
    ctrl = read(APP, "controller.py")
    attrs = sorted(set(re.findall(r"self\.(_pending\w*|_edit_in_progress)\s*=",
                                  ctrl)))
    owner = read(APP, "controllers", "pending_edit_ctrl.py")
    verbs = len(re.findall(r"^    def [a-z]\w*\(", owner, re.M))
    state = DONE if len(attrs) <= 1 else OPEN
    return state, (f"{len(attrs)} pending-edit attrs on AppController; "
                   f"pending_edit_ctrl exposes {verbs} public methods")


def probe_8_nobl_flag_model():
    """The snapshot/restore pairs are the tell: they compensate for the wipe.

    They must disappear WITH the wipe, not before it — removing them first loses
    the user's flag outright.
    """
    sites = []
    for path in walk_py(APP):
        if os.path.basename(path) == "meta_io.py":
            continue
        if re.search(r"(snapshot|restore)_seg_edits", read(path)):
            sites.append(os.path.relpath(path, APP))
    homes = [os.path.relpath(p, APP) for p in walk_py(APP)
             if "grow_bl" in read(p)]
    state = DONE if not sites else OPEN
    return state, (f"{len(sites)} snapshot/restore call sites; "
                   f"grow_bl lives in {len(homes)} file(s): {', '.join(homes)}")


def probe_9_utils_qt_line():
    """The only probe that runs code: the question is what an IMPORT pulls in.

    A subprocess is required. In-process the answer is always "yes, PyQt6 is
    loaded" once anything else has imported it, so the check would pass for the
    wrong reason exactly when it matters.
    """
    code = ("import sys; import app.services.pipeline_runner as m; "
            "print(','.join(sorted(n for n in sys.modules if n.split('.')[0]=='PyQt6')))")
    try:
        r = subprocess.run([sys.executable, "-c", code], cwd=GUI, timeout=90,
                           capture_output=True, text=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return OPEN, f"probe could not run: {exc}"
    if r.returncode != 0:
        return OPEN, "importing pipeline_runner failed: " + (
            r.stderr.strip().splitlines() or ["?"])[-1]
    loaded = [m for m in r.stdout.strip().split(",") if m]
    if not loaded:
        return DONE, "importing the headless runner loads no PyQt6 module"
    return OPEN, (f"importing services.pipeline_runner loads {len(loaded)} PyQt6 "
                  f"modules ({', '.join(loaded[:3])}…)")


def probe_10_refresh_contract():
    """How many repaint verbs a caller must choose between after a geometry edit."""
    ctl = os.path.join(APP, "controllers")
    verbs = set()
    for path in list(walk_py(ctl)) + [os.path.join(APP, "controller.py")]:
        verbs |= set(re.findall(
            r"^\s+def (_?(?:refresh|sync|update|redraw)\w*)\(", read(path), re.M))
    state = DONE if len(verbs) <= 5 else OPEN
    return state, f"{len(verbs)} refresh/sync/update/redraw verbs across controllers/"


PROBES = [
    ("1", "Close the sidebar seam", probe_1_sidebar_seam),
    ("2", "A mesher seam that is not the process", probe_2_mesher_seam),
    ("3", "Declare a mesh parameter once", probe_3_param_schema),
    ("4", "Retire the signal-wiring table", probe_4_signal_wiring),
    ("5", "One field-spec table per config panel", probe_5_field_spec_tables),
    ("6", "A pipeline stage seam", probe_6_pipeline_stage_seam),
    ("7", "An owner for the edge being edited", probe_7_pending_edit_owner),
    ("8", "A model for the per-segment No-BL flag", probe_8_nobl_flag_model),
    ("9", "Split app/utils.py at the Qt line", probe_9_utils_qt_line),
    ("10", "Name the refresh contract", probe_10_refresh_contract),
]


def main() -> int:
    print("Architecture backlog — measured from the tree, not from a document.")
    print("Rationale: docs/architecture_review_2026-08-14.md (frozen, 854f53e)\n")
    broke = []
    counts = {DONE: 0, OPEN: 0, STALE: 0}
    for num, title, fn in PROBES:
        try:
            state, detail = fn()
        except Exception as exc:                       # a broken probe is the only failure
            broke.append(f"{num}: {type(exc).__name__}: {exc}")
            state, detail = "ERROR", str(exc)
        else:
            counts[state] = counts.get(state, 0) + 1
        print(f"  [{state}] {num:>2} · {title}")
        print(f"           {detail}")
    print(f"\n{counts[DONE]} done · {counts[OPEN]} open · {counts[STALE]} stale "
          f"premise · {len(PROBES)} candidates")
    print("A candidate reported DONE is guarded by the gate named beside it; the "
          "probe is only a pointer at that gate.")
    if broke:
        print("\nPROBE FAILURES (the probe is broken, not the codebase):")
        for b in broke:
            print("  - " + b)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
