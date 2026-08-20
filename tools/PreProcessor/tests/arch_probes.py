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

import ast
import itertools
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
    """RETIRED to a pointer at ``test_gui_cpp_config_parity.py`` (issue #9, 2026-08-19).

    This probe counted how many FILES mention one parameter — ``BL_JUNCTION_ANGLE_C2``
    — and called the candidate done when the count fell to two. That measure had the
    same defect as candidate 5's first probe: an authoritative-looking number measuring
    almost nothing. It could not distinguish a file that DECLARES the parameter from
    one that merely reads a declaration, so collapsing five C++ traversals onto one
    list moved it from 6 files to 5 (the declaration became its own file) while the
    property that matters — that adding a parameter is one edit and a mismatch fails
    the build — changed completely.

    What replaced it, and where each half now lives:

      * ``include/BLParams.hpp`` — one row per BL parameter carrying KEY, type, field
        and default. The struct, the .dat reader, the per-geometry override parser and
        ``isBLParam`` are GENERATED from it, so a missing parse branch is not a thing
        that can exist. Gated by ``tests/cpp/test_bl_params_decl.cpp``.
      * ``models/mesh_config_keys.py`` — the GUI's KEY map, DERIVED from the field-spec
        tables plus ``MeshConfig``'s own field types. Gated by
        ``tests/test_field_spec_tables.py`` checks 13a-13f.
      * ``tests/test_gui_cpp_config_parity.py`` — the two declarations compared on key,
        TYPE and DEFAULT, in both directions, with its failure modes verified by
        injection INSIDE the test (check 7), not by hand at review time. This is the gate that makes the candidate's actual claim checkable,
        and it is what found the one real defect left: ``BL_AUTO_FAN_NODES`` was an int
        in C++ (with a live ``== 2`` branch) and a bool in the GUI, so the GUI's own
        three-item combo could not express the LOCAL it offered.

    Kept as a pointer rather than deleted, because a reader who remembers candidate 3
    needs to be told where its answer moved, and because the alternative — deleting the
    entry — would make the backlog silently shorter rather than visibly finished.

    WHAT THIS PROBE CANNOT SEE, stated because a probe that overstates itself is the
    failure mode this file exists to avoid: it checks that each gate is PRESENT and
    REGISTERED, by looking for identifiers and for the runner picking the file up. It
    does not re-derive what the gates prove. A gate whose checks were gutted while its
    identifiers stayed would still read DONE here — the same substring weakness CLAUDE.md
    records for the first version of `test_pipeline_stages.py`. That is accepted rather
    than papered over: the authority is the gate, and the gate is what fails. The
    registration check is the part worth having, because a test nobody runs passes by
    never running.
    """
    #: The gates candidate 3 retired into: (file, the identifier that must survive).
    gates = (
        (os.path.join(TESTS, "test_gui_cpp_config_parity.py"),
         "PINNED_DEFAULT_DIVERGENCE"),
        (os.path.join(TESTS, "test_gui_cpp_config_parity.py"), "cpp_declarations"),
        (os.path.join(TESTS, "test_field_spec_tables.py"), "build_key_map"),
        (os.path.join(REPO, "include", "BLParams.hpp"), "HYBMESH_BL_PARAMS"),
        (os.path.join(APP, "models", "mesh_config_keys.py"), "build_key_map"),
    )
    missing = [f"{os.path.basename(f)}:{ident}"
               for f, ident in gates if ident not in read(f)]
    # A gate the runner never picks up passes by never running.
    runner = read(TESTS, "run_all.sh")
    unrun = [n for n in ("test_gui_cpp_config_parity", "test_field_spec_tables")
             if n not in runner and "test_*.py" not in runner and "*.py" not in runner]
    if not missing and not unrun:
        return DONE, ("superseded by test_gui_cpp_config_parity.py (key + type + "
                      "default, both directions, 13 injections in-test), "
                      "test_bl_params_decl.cpp and test_field_spec_tables.py 13a-13f")
    bits = []
    if missing:
        bits.append("gates gone: " + ", ".join(missing))
    if unrun:
        bits.append("not run by run_all.sh: " + ", ".join(unrun))
    return OPEN, "; ".join(bits)


def probe_4_signal_wiring():
    """RETIRED by decision on 2026-08-19, not merely observed to be stale.

    The review's premise was the hand-listed 35 spin boxes at :67-77, wired to one
    handler by name. That region is now the shape-tool menu and the shape fields
    are wired from ``shape_spec``'s own parameter table, so the candidate as
    WRITTEN stopped describing the file some time ago. This probe reported that
    and then reported the residue every session, which reads like unfinished
    business and is what a decision is for.

    THE NUMBER THAT DECIDED IT: 127 ``connect()`` calls reach 118 DISTINCT
    handlers, 109 of them used exactly once (measured 2026-08-19). The nine
    repeats are sidebar controls and their toolbar twins. So the wiring is
    irreducibly HETEROGENEOUS, and that is the whole argument: the review's
    Solution — ``undo_ctrl.py``-style ``findChildren`` introspection — works there
    because every editable widget gets the SAME treatment, and here there is no
    same treatment to introspect toward. A spec table would be 127 rows of
    (widget, signal, handler): the identical information, one indirection further
    away, no complexity removed. The convertible part of this file was the
    homogeneous part, and it has already been converted.

    The candidate's biggest listed win — "removes 116 of the 389 sidebar
    reach-throughs" — was banked by candidate 1 instead and is gated by
    test_sidebar_seam.py, so retiring this one forfeits nothing.

    What remains (347 lines, 0 public methods, one call site for the six wiring
    verbs, ~186 assumed names) is the mixin shape used throughout this repo, and
    the documented ~500-line file rule actively produces it. Re-scoping the
    candidate around that would be a fight with a policy, not a deepening.

    RETIRED IS NOT BLIND. The probe still watches the one thing that would revive
    it: a hand-listed widget-name table reappearing. If one does, this goes back
    to OPEN with the premise the review actually wrote.
    """
    src = read(APP, "controllers", "signal_wiring_ctrl.py")
    if not src:
        return DONE, "signal_wiring_ctrl.py no longer exists"
    handlisted = bool(re.search(r"for\s+\w+\s+in\s*\(\s*[\"']\w+_spin", src))
    if handlisted:
        return OPEN, ("a hand-listed widget-name table is back — the retired "
                      "premise has returned, re-open the candidate")
    pairs = re.findall(r"\.connect\(\s*([^)]*?)\s*\)", src, re.S)
    distinct = len({re.sub(r"\s+", " ", h) for h in pairs})
    return STALE, (f"RETIRED 2026-08-19: {len(pairs)} connects reach {distinct} "
                   "distinct handlers, so the wiring is heterogeneous and a table "
                   "would not remove complexity; premise (hand-listed spin boxes) "
                   "gone, and candidate 1 banked the reach-through win")


def probe_5_field_spec_tables():
    """DONE when each config panel declares its fields once AND a gate keeps it.

    Retired to a pointer at ``test_field_spec_tables.py``, which is strictly
    stronger than anything measurable from here. This probe used to count
    ``self.x =`` lines in the three build mixins (138 at the last reading) against
    the size of the AST test reconciling them, and neither number could see the
    property that matters: whether the build half, the read half and the write
    half are the SAME declaration. A build mixin that walks a table still assigns
    nothing, so the count goes to zero the moment the tables exist — including if
    someone had merely moved the widgets somewhere else.

    Worth recording: the first version of this probe matched assignments whose
    right-hand side named a widget CLASS and reported 34 where the true figure was
    138, because the solver mixins build through local ``_edit()`` / ``_check()``
    factories. An authoritative-looking number measuring almost nothing is the
    failure mode a probe is most prone to, which is why a landed candidate hands
    over to its gate instead of keeping one.

    The gate checks ten properties and verifies each static one by injection: no
    field declared twice, each panel's declared residue equal to what its
    hand-written ``get_config`` still assigns, no table field ALSO hand-built or
    hand-read/written, every declared group walked by a builder and vice versa,
    every kind buildable (and a typo'd kind refused at construction), every kind's
    read/write pair round-tripping on the live panels, ``PRESERVED_FIELDS`` and
    ``LENGTH_FIELDS`` derived rather than listed, every field with no widget named
    with its reason, and the three escape hatches used only where justified.
    """
    # Where a table lives is not fixed, and this probe must not accept a STAND-IN for
    # one. The mesh tables moved to ``services/`` so the .dat key map could derive from
    # them without pulling PyQt6 onto the headless pipeline's path, leaving 17- and
    # 25-line re-export shims behind on the old paths. Checking the old paths for
    # existence therefore counted a shim as a table and reported DONE with the message
    # "3 panels declare their fields in 4 tables" — true of neither location. So each
    # table is looked for in either home and must actually CONTAIN specs.
    panels = os.path.join(APP, "views", "panels")
    services = os.path.join(APP, "services")
    tables = [f for f in ("mesh_field_specs.py", "solver_field_specs.py",
                          "stl3d_field_specs.py", "mesh_bl_field_specs.py")
              if "FieldSpec(" in (read(services, f) or read(panels, f) or "")]
    spec = read(APP, "services", "field_spec.py")
    gate = read(TESTS, "test_field_spec_tables.py")
    sync = read(APP, "controllers", "panel_sync_ctrl.py")
    derived = "preserved_fields(" in sync and 'frozenset({"' not in sync
    # A build mixin that walks its table assigns no widgets of its own.
    assigned = 0
    for f in ("solver_config_build_mixin.py", "solver_config_build_mixin_b.py",
              "mesh_config_build_mixin.py"):
        assigned += len(re.findall(r"^\s+self\.\w+\s*=", read(panels, f), re.M))
    if len(tables) == 4 and spec and gate and derived:
        return DONE, ("gated by test_field_spec_tables.py; 3 panels declare their "
                      "fields in 4 tables (the 2 mesh tables in services/, so the "
                      ".dat key map derives from them headlessly), "
                      "PRESERVED_FIELDS derived")
    bits = []
    if len(tables) < 4:
        bits.append(f"only {len(tables)}/4 spec tables exist")
    if not spec:
        bits.append("no services/field_spec.py")
    if not derived:
        bits.append("PRESERVED_FIELDS is still hand-listed")
    if assigned:
        bits.append(f"{assigned} attrs still assigned across the 3 build mixins")
    if not gate:
        bits.append("ungated — a field declared twice would not be caught")
    return OPEN, "; ".join(bits)


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
    """RETIRED. The owner landed; a gate now keeps it, so this only points there.

    Counting ``_pending_*`` attributes was the right measure while the state was
    being moved and the wrong one afterwards: it reached zero at ticket 2 of
    five, with three tickets and the whole invariant still to do. What the
    candidate is actually about — nobody reaching past the verbs, the owner
    staying Qt-free, one predicate, a commit resolving its own session — is not
    a count of anything, and is what ``test_edge_edit_owner_seam.py`` fails the
    build on. So this probe asks whether that gate exists, not whether the tree
    still looks tidy.
    """
    gate = read(TESTS, "test_edge_edit_owner_seam.py")
    owner = read(APP, "services", "edge_edit.py")
    if gate and owner:
        return DONE, ("gated by test_edge_edit_owner_seam.py (5 properties, "
                      "9 injections); both edit kinds + the drag live in "
                      "services/edge_edit, bound to their session")
    if owner:
        return OPEN, "the owner exists but no gate keeps the state off AppController"
    return OPEN, "modal edit state still declared on the god object"


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


# ── Probe 10's measurement, shared by its three questions ───────────────────
# Kept here rather than inside the probe because all three read the same parse
# of the same files, and because the definitions are the argument: what counts
# as a "verb", a "UI write" and a "re-derived sequence" is what the retirement
# rests on, so each is stated once where it can be read.

_VERB_NAME = re.compile(r"^_?(refresh|sync|update|redraw)\w*$")

# A receiver that is a STABLE piece of UI. Deliberately NOT `item` or `dlg`:
# those name a widget CONSTRUCTED in the body (a QTreeWidgetItem in one verb, a
# QListWidgetItem in another), so two verbs sharing that local name share
# nothing — counting them reported three overlapping pairs where there is one.
_UI_RECV = re.compile(r"^(canvas|cv|mesh_canvas|result_canvas|sidebar|sb|tree|"
                      r"panel|\w+_panel|\w+_btn|\w+_list_widget|tab_widget)$")
# A MUTATOR. A shared read is not a shared refresh — `sb.transform_spec()` is a
# getter two verbs both consult, and counting it was the second false pair.
_UI_WRITE = re.compile(r"^(set|show|clear|update|add|insert|remove|take|hide)")


def _controller_py():
    return [os.path.join(APP, "controller.py")] + sorted(
        walk_py(os.path.join(APP, "controllers")))


def _receiver_method(func):
    """('receiver', 'method') for a Call's func, or None. `_view` is stripped so
    `self.main_window.canvas_view.x` and a local `canvas.x` are one receiver."""
    if not isinstance(func, ast.Attribute):
        return None
    val = func.value
    if isinstance(val, ast.Attribute):
        recv = val.attr
    elif isinstance(val, ast.Name):
        recv = val.id
    else:
        return None
    return re.sub(r"_view$", "", recv), func.attr


def _refresh_verbs():
    """({verb: (path, ast node)}, {closure name: count}).

    A verb is a refresh/sync/update/redraw method in a CLASS BODY under
    controllers/. A same-named function nested inside one is a callback, not an
    interface — separating them is what turned 37 into 33.
    """
    methods, closures = {}, {}
    for path in _controller_py():
        # A SyntaxError is deliberately NOT swallowed. Dropping an unparsable
        # file would silently drop its verbs, so the count would fall and the
        # verdict would still read STALE for the wrong reason — measured while
        # verifying this probe by injection, where a mis-indented mutation took
        # three verbs with it and looked like a passing check.
        tree = ast.parse(read(path), filename=path)
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            for m in cls.body:
                if not isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if _VERB_NAME.match(m.name):
                    methods[m.name] = (path, m)
                for sub in ast.walk(m):
                    if sub is m or not isinstance(
                            sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if _VERB_NAME.match(sub.name):
                        closures[sub.name] = closures.get(sub.name, 0) + 1
    return methods, {k: v for k, v in closures.items() if k not in methods}


def _refresh_ui_write_overlap(verbs):
    """[(verb_a, verb_b, shared writes)] for pairs where NEITHER already calls the
    other. Containment is a fan-out tree and is the design; overlap between two
    verbs that are not in one another's closure is the near-duplicate signal."""
    writes, calls = {}, {}
    for name, (_path, node) in verbs.items():
        w, c = set(), set()
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            got = _receiver_method(sub.func)
            if not got:
                continue
            recv, meth = got
            if meth in verbs and meth != name:
                c.add(meth)
            elif _UI_RECV.match(recv) and _UI_WRITE.match(meth):
                w.add(f"{recv}.{meth}")
        writes[name], calls[name] = w, c

    def reaches(name, seen=None):
        seen = set() if seen is None else seen
        for callee in calls[name]:
            if callee not in seen:
                seen.add(callee)
                reaches(callee, seen)
        return seen

    closure = {n: reaches(n) for n in verbs}
    out = []
    for a, b in itertools.combinations(sorted(verbs), 2):
        if b in closure[a] or a in closure[b]:
            continue
        shared = writes[a] & writes[b]
        if shared:
            out.append((a, b, ", ".join(sorted(shared))))
    return out


def _refresh_repeated_sequences(verbs):
    """[(sequence, number of functions repeating it)] for verb sequences of length
    >= 2 that appear in two or more functions anywhere in the GUI. This is the
    review's real complaint — a fan-out order re-derived by each caller."""
    seen = {}
    for path in walk_py(GUI, skip=("tests",)):
        tree = ast.parse(read(path), filename=path)   # see _refresh_verbs
        for fn in [n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            hits = sorted((c.lineno, c.func.attr) for c in ast.walk(fn)
                          if isinstance(c, ast.Call)
                          and isinstance(c.func, ast.Attribute)
                          and c.func.attr in verbs and c.func.attr != fn.name)
            seq = []
            for _line, verb in hits:            # collapse consecutive repeats
                if not seq or seq[-1] != verb:
                    seq.append(verb)
            if len(seq) >= 2:
                seen[tuple(seq)] = seen.get(tuple(seq), 0) + 1
    return [(s, n) for s, n in sorted(seen.items()) if n >= 2]


def probe_10_refresh_contract():
    """RETIRED by decision on 2026-08-20 (issue #14), the premise measured first.

    The review counted 35 refresh/sync/update/redraw verbs and read the COUNT as
    the problem: "after changing geometry a caller must know which of 35 refresh
    verbs to invoke and in what order". Measuring what the verbs actually touch
    says the count was never the problem, in the same shape as candidate 4.

    THE NUMBER THAT DECIDED IT: of the 33 verbs (the old reading of 37 counted
    four NESTED CLOSURE names — ``refresh``, ``_refresh``, ``sync_fn``,
    ``sync_color_mode``, 10 definitions between them — which are the ``refresh_cb``
    the command pattern hands to a Command so undo repaints too; no caller can
    pick one, so they are not part of any interface), exactly ONE pair writes the
    same UI element without one already calling the other, and it is a shared
    CONCLUDING STEP rather than a duplicate job: ``_refresh_segment_list`` and
    ``_sync_geometry_list`` both end with ``tree.setCurrentItem`` to restore the
    selection, over DISJOINT rows (the active session's edge rows vs the top-level
    session rows). They are co-called at four sites, never chosen between.

    So the number of verbs a caller could have swapped for another is ZERO, and
    the one pair the ticket suspected is the sharpest evidence. ``redraw_canvas``
    is the canonical full rebuild; ``_redraw_file_geometry`` is a seven-line fast
    path called from ``_on_file_handle_dragged`` on every mouse-move of a corner
    drag. Substituting the general verb is not a harmless over-refresh — it calls
    ``clear_edge_handles()`` and would delete the handle the gesture is holding.
    The two verbs look like near-duplicates by NAME and are not interchangeable in
    either direction, which is the whole argument: these are 33 honestly-named
    different jobs, and a caller reads the name to learn which job it is.

    The review's other half — "124 call sites learn one verb instead of a
    sequence" — does not survive either: 47 of the 74 call-site functions call
    exactly ONE verb, so most callers already have one verb to learn. And the
    proposed Solution, a single ``geometry_changed()`` fanning out to all of them,
    is what the drag path proves cannot exist: an unconditional fan-out clears the
    drag's own handles.

    THE RESIDUE, AND WHAT LANDED (2026-08-20, same day): four ordered sequences
    were repeated at 11 sites, the worst being ``update_duplicate_base_point ->
    update_duplicate_preview -> _refresh_transform_handles`` four times over in
    ``transform_ctrl.py`` (:10, :27, :39, :47). That was one extract-method inside
    one controller, not a repaint contract for the app, and it is now
    ``_refresh_duplicate_gizmo(rebase=)`` — done directly, because a ticket to
    carry it would have been longer than the change.

    NOTICE WHICH WAY THE NUMBERS MOVED. Naming that sequence ADDED a verb
    (33 -> 34) and removed four hand-derived orders (4 sequences -> 3). If the
    verb count were the problem, this fix would have made things worse; it did
    not, which is the same conclusion the interchangeability measurement above
    reaches from the other side. The worst sequence left is
    ``_refresh_session_colors -> _sync_geometry_list`` at 3 sites — half the
    revive line.

    THE DEAD-VERB BY-PRODUCT WAS MEASURED WRONG: it was one verb, not two.
    ``update_segment_bc`` was genuinely a leftover — the CAD sidebar's
    "Boundary:" combo that called it is gone and the live path is
    ``open_cad_patch_dialog -> _apply_bc_to_indices`` — and it is now DELETED.
    ``update_colormap`` is NOT
    dead — it is one of five methods under ``postprocess_ctrl.py``'s own
    "Programmatic delegates" heading, four of which have no caller BY DESIGN
    (``change_variable``, ``toggle_mesh_overlay``, ``toggle_streamlines`` are the
    others), listed as a planned scripting API in
    ``docs/solver_integration_plan.md:135``. The probe singled it out only because
    its regex catches ``update_*`` and not ``toggle_*`` / ``change_*``, so the
    lesson is about the instrument: a verb with no caller is dead only if nothing
    DECLARED it an entry point. So the count reads 33 again, and for the second
    time in one candidate the number moved for a reason unrelated to the thing it
    was supposed to measure: +1 for naming a sequence, -1 for deleting a verb
    whose caller went away when the per-edge patch/group name moved out of the
    sidebar into a pop-up (``segment_ctrl.py``'s own ``(#1)`` comment records it).

    THE ZERO IS NOT MACHINE-MEASURED, AND THE ROW SAYS SO. Substitutability is a
    question about what a caller INTENDED — the drag path above is settled by
    knowing that clearing the handles mid-gesture is wrong, which no regex can
    read. What this probe computes is the two machine-checkable proxies below; a
    hand count dressed up as a measurement is exactly the staleness this
    candidate is about, so the row attributes it.

    RETIRED IS NOT BLIND. Two lines revive it, and both are the premise actually
    returning rather than the count moving: a SECOND non-containment pair writing
    the same UI element (two verbs really repainting one widget), or any one
    sequence re-derived at six or more sites (a fan-out with no owner, which is
    the verb the review wanted).
    """
    verbs, closures = _refresh_verbs()
    if not verbs:
        return OPEN, "no refresh verbs found — the probe can no longer see them"
    overlap = _refresh_ui_write_overlap(verbs)
    seqs = _refresh_repeated_sequences(set(verbs))
    worst = max((n for _s, n in seqs), default=0)
    if len(overlap) > 1:
        return OPEN, ("two verbs now repaint the same widget outside containment: "
                      + "; ".join(f"{a} ∩ {b} on {c}" for a, b, c in overlap))
    if worst >= 6:
        return OPEN, (f"one refresh sequence is re-derived at {worst} sites — the "
                      "missing verb the review asked for; re-open the candidate")
    return STALE, (f"RETIRED 2026-08-20: {len(verbs)} verbs (not "
                   f"{len(verbs) + len(closures)} — {len(closures)} were nested "
                   f"refresh_cb closures), {len(overlap)} pair sharing a UI write, "
                   f"0 of {len(verbs)} interchangeable BY HAND (this probe measures "
                   f"write-overlap and repeated sequences, not substitutability); "
                   f"distinct jobs, not {len(verbs)} ways to do one. Residue: "
                   f"{len(seqs)} repeated sequences (worst x{worst}, named in the "
                   "docstring)")


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
