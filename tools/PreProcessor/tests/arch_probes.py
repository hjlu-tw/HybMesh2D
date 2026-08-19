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


def probe_6a_ib_handoff():
    """DONE when the IB artefact reaches the solve in BOTH hosts and a gate keeps it.

    The number that decided this one was a signature: ``_run_solver`` took no phi
    at all, so the stage that produced one could only hand it over by
    coincidence — and did not. Retired to a pointer at the gate, which is
    strictly stronger than anything measurable from here: it drives the real
    conversion, pins the Tecplot header count against the reader that shares the
    format, compiles the DLL it generates, and proves the chain by AST instead of
    by a parameter name existing.
    """
    runner = read(APP, "services", "pipeline_runner.py")
    gui = read(APP, "controllers", "pipeline_ctrl.py")
    gate = read(TESTS, "test_pipeline_ib_handoff.py")
    shared = read(APP, "services", "ib_handoff.py")
    sig = re.search(r"def _run_solver\((.*?)\)\s*->", runner, re.S)
    phi_passed = bool(sig and "phi" in sig.group(1))
    gui_ib = "_pipe_stl3d" in gui
    if phi_passed and gui_ib and shared and gate:
        return DONE, ("gated by test_pipeline_ib_handoff.py; phi reaches the "
                      "solve in both hosts through services/ib_handoff")
    bits = []
    if not phi_passed:
        bits.append("out['phi'] never reaches _run_solver (defect)")
    if not gui_ib:
        bits.append("GUI Run All has no IB stage (recorded asymmetry)")
    if not shared:
        bits.append("the phi -> solver conversion lives only in a Qt controller")
    if phi_passed and gui_ib and shared and not gate:
        bits.append("wired but ungated — a re-broken hand-off would not be caught")
    return OPEN, "; ".join(bits)


def probe_6b_one_stage_declaration():
    """DONE when the stage set is declared once AND a gate keeps it that way.

    Candidate 6 was one row and is two invariants with disjoint machinery — the
    same discovery that split ``test_cpp_linkable_seam.py`` from
    ``test_cpp_pure_layer.py``. Keeping them in one row meant a DONE earned by
    the hand-off read as a DONE for the review's actual Solution: *"Declare the
    stages and what each consumes and produces once. The two runners become
    adapters differing only in how they wait."*

    Retired to a pointer at ``test_pipeline_stages.py``, which is strictly
    stronger than anything measurable from here. The number this probe used to
    report — how many places enumerate the sequence — could not distinguish a
    declaration both hosts READ from one they merely import, and said nothing at
    all about order or about artefacts. The gate matches the declared set against
    both hosts IN BOTH DIRECTIONS by AST, recovers the GUI's signal chain as a
    reachability graph to check the order, asserts the produced/consumed graph
    closes, and verifies each of those by injection.

    Worth recording, because it is the case this probe was watching for: when the
    work landed the two host lists AGREED (4 stages each, same order, same
    names). The divergence the candidate was named for had already been repaired
    by hand in 6a; its cause — two lists — had not. A probe that had only watched
    for divergence would have read that as nothing to do.
    """
    runner = read(APP, "services", "pipeline_runner.py")
    gui = read(APP, "controllers", "pipeline_ctrl.py")
    decl = read(APP, "services", "pipeline_stages.py")
    gate = read(TESTS, "test_pipeline_stages.py")
    read_by_both = "pipeline_stages" in runner and "pipeline_stages" in gui
    if decl and read_by_both and gate:
        return DONE, ("gated by test_pipeline_stages.py; both hosts read the "
                      "stage set from services/pipeline_stages")

    head = sorted(set(re.findall(r"^def (_run_\w+)\(", runner, re.M)))
    # A GUI stage is a _pipe_* entry; the _pipe_after_* continuations and the
    # _pipe_chain/_pipe_resample_next/_pipe_label plumbing are not stages.
    hosted = sorted(set(re.findall(
        r"^    def (_pipe_(?!after_|chain|resample_next|label)\w+)\(", gui, re.M)))
    agree = [h[len("_run_"):] for h in head] == [g[len("_pipe_"):] for g in hosted]
    named = ", ".join(sorted(h[len("_run_"):] for h in head))      # not run order
    if decl and read_by_both and not gate:
        return OPEN, ("declared and read by both hosts, but ungated — a stage "
                      "added to one host only would not be caught")
    return OPEN, (f"the same {len(head)} stages ({named}) are enumerated once "
                  "per host, no shared declaration"
                  + ("; the two lists agree" if agree else "; THE LISTS DIVERGE"))


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
    """DONE when the flag is a model field AND a gate keeps the compensation gone.

    The snapshot/restore pairs were the tell: they compensated for the resampler
    rewriting the sidecar from the CAD config, and they had to disappear WITH
    that wipe rather than before it — removing them first would have lost the
    user's flag outright. Their absence alone is therefore not the property; a
    field on the segment that reaches the resampler's own config is, which is
    what the gate drives against the real binary.

    Counting the files mentioning ``grow_bl`` is deliberately NOT the signal any
    more. Before the work it was 1 (the sidecar reader) and that low number WAS
    the defect — the fact had no model home; afterwards it is ~8 and that reads
    like sprawl while being the fix. A number whose good and bad directions are
    the same number is worse than no number.
    """
    # Require a CALL or a DEF, not a mention: meta_io.py carries a comment naming
    # the removed helpers and why they went, and prose is not a call site. The
    # gate does this properly, by AST — this is only a pointer at it.
    sites = []
    for path in walk_py(APP):
        if re.search(r"(?:def |\.)(?:snapshot|restore)_seg_edits\s*\(", read(path)):
            sites.append(os.path.relpath(path, APP))
    gate = read(TESTS, "test_seg_edit_carryover.py")
    field = re.search(r"^\s+self\.grow_bl\b", read(APP, "models", "segment.py"), re.M)
    emitted = 'd["grow_bl"]' in read(APP, "models", "segment.py")
    if not sites and gate and field and emitted:
        return DONE, ("SegmentModel.grow_bl reaches the resampler's own config; "
                      "gated by test_seg_edit_carryover.py against the real binary")
    if sites:
        return OPEN, (f"{len(sites)} snapshot/restore call site(s) still compensate "
                      f"for the wipe: {', '.join(sites)}")
    if not field:
        return OPEN, "no SegmentModel.grow_bl field — the flag has no model home"
    if not emitted:
        return OPEN, "SegmentModel.grow_bl exists but to_dict() does not emit it, "\
                     "so it never reaches the resampler"
    return OPEN, "compensation gone but no gate — the wipe would return unnoticed"


def probe_9_utils_qt_line():
    """DONE when the pure helpers live off the Qt side AND a gate keeps them there.

    The only probe that ran code, because the question is what an IMPORT pulls
    in, and it kept that check in a subprocess: in-process the answer is always
    "yes, PyQt6 is loaded" once anything else has imported it, so the check would
    pass for the wrong reason exactly when it matters. That reasoning now lives
    in the gate, along with the half this probe could never have seen — a
    DEFERRED ``from app.utils import repo_root`` inside a function body loads no
    Qt at import time, so the subprocess sweep called three such modules clean
    while ``run_pipeline.sh`` still died on a machine without the toolkit.
    """
    gate = read(TESTS, "test_qt_free_seam.py")
    pure = read(APP, "services", "paths.py")
    moved = ("repo_root", "find_binary_executable", "find_solver_executables",
             "find_stl3d_binary", "find_mpi_launcher", "is_mpi_binary")
    homed = [n for n in moved if re.search(rf"^def {n}\(", pure, re.M)]
    if gate and len(homed) == len(moved):
        return DONE, ("gated by test_qt_free_seam.py; the 6 path/binary helpers "
                      "live in Qt-free services/paths.py")
    if not homed:
        return OPEN, "the path/binary helpers still live in the Qt-side app/utils.py"
    if len(homed) < len(moved):
        return OPEN, (f"only {len(homed)}/{len(moved)} helpers moved: missing "
                      + ", ".join(n for n in moved if n not in homed))
    return OPEN, "helpers moved but no gate — a new import would not be caught"


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
    ("6a", "A pipeline stage seam: the IB hand-off", probe_6a_ib_handoff),
    ("6b", "A pipeline stage seam: one stage declaration",
     probe_6b_one_stage_declaration),
    ("7", "An owner for the edge being edited", probe_7_pending_edit_owner),
    ("8", "A model for the per-segment No-BL flag", probe_8_nobl_flag_model),
    ("9", "Split app/utils.py at the Qt line", probe_9_utils_qt_line),
    ("10", "Name the refresh contract", probe_10_refresh_contract),
]


def run_probes() -> tuple[list[str], str, list[str]]:
    """(report lines, one-line tally, broken-probe messages)."""
    lines = ["Architecture backlog — measured from the tree, not from a document.",
             "Rationale: docs/architecture_review_2026-08-14.md (frozen, 854f53e)", ""]
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
        lines.append(f"  [{state}] {num:>2} · {title}")
        lines.append(f"           {detail}")
    # Candidates are numbered by the frozen review; a candidate that turns out to
    # be two invariants gets two probes (6a/6b), so rows and candidates differ.
    cands = len({re.match(r"\d+", num).group() for num, _t, _fn in PROBES})
    tally = (f"{counts[DONE]} done · {counts[OPEN]} open · {counts[STALE]} stale "
             f"premise · {len(PROBES)} probes over {cands} candidates")
    lines += ["", tally,
              "A candidate reported DONE is guarded by the gate named beside it; "
              "the probe is only a pointer at that gate."]
    if broke:
        lines.append("")
        lines.append("PROBE FAILURES (the probe is broken, not the codebase):")
        lines += ["  - " + b for b in broke]
    return lines, tally, broke


def emit_hook() -> int:
    """SessionStart hook envelope: the report goes to the model, the tally to the user.

    The JSON is built HERE rather than by piping the human report through ``jq``
    in the settings.json command string, for two reasons. The wrapper is then
    version-controlled and testable on its own (``--hook | jq .``) instead of
    living as an escaped one-liner inside JSON; and a hook that cannot run must
    stay silent rather than emit half an envelope, which is easier to guarantee
    in one place. If anything here raises, nothing is injected — the session
    simply starts without the status, and CLAUDE.md still tells the reader to run
    the probes by hand. Degrading to "no context" is correct; degrading to "stale
    context" is the failure this whole arrangement exists to prevent.
    """
    import json
    try:
        lines, tally, _broke = run_probes()
    except Exception:
        return 0                                       # silence beats a broken envelope
    report = "\n".join(lines)
    print(json.dumps({
        "systemMessage": f"Architecture backlog: {tally}",
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "Architecture backlog, measured at session start by "
                "tools/PreProcessor/tests/arch_probes.py. This is the AUTHORITY on "
                "what is left to do; docs/architecture_review_2026-08-14.md is "
                "frozen rationale and does not know what has since been done. Do "
                "not re-derive any of this by reading source.\n\n" + report),
        },
    }))
    return 0


def main() -> int:
    if "--hook" in sys.argv[1:]:
        return emit_hook()
    lines, _tally, broke = run_probes()
    print("\n".join(lines))
    return 1 if broke else 0


if __name__ == "__main__":
    sys.exit(main())
