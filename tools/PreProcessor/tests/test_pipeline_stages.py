#!/usr/bin/env python3
"""The pipeline's stage set is declared once, and both hosts implement all of it.

Candidate 6b of the architecture backlog. The four stages — CAD resample,
immersed solid, mesh, solver — are implemented twice: ``pipeline_runner.py``
blocking and linear, ``pipeline_ctrl.py`` chained on QThread ``finished_signal``.
Until ``services/pipeline_stages.py`` nothing knew the set, so each host named,
ordered and connected its own stages and the only thing comparing them was a
reader.

Candidate 6a closed one instance of that — the immersed-solid stage produced a
phi field ``_run_solver`` had no parameter to receive, and GUI Run All had no IB
stage at all — and left ``test_pipeline_ib_handoff.py`` behind. That gate watches
ONE artefact crossing ONE seam. It cannot see a fifth stage added to one host, a
reordering, or the next artefact produced for nobody. This one gates where the
stage list lives.

What each check is shaped the way it is, and why:

1. BOTH DIRECTIONS, OR IT IS NOT A GATE. Checking only that every declared stage
   is implemented leaves the obvious hole: adding ``_pipe_foo`` to the GUI alone
   passes. Checking only that every host function is declared leaves the mirror
   hole. 1a/1b do both, per host.

2. THE HOSTS ARE MATCHED BY NAME, RESOLVED BY AST. ``pipeline_stages`` must not
   import either host — the GUI one is a Qt mixin, and importing it would undo
   the Qt-free property the headless runner depends on — so the declaration
   carries function NAMES and this test resolves them. That is what turns "a
   stage exists in one host only" from a review finding into a build failure.

2b. READING THE DECLARATION MEANS DERIVING FROM IT, NOT IMPORTING IT. Checks
   2a/2b assert each host passes EVERY declared stage key to its label adapter,
   and 2c/2d that each builds its plan by calling ``pipeline_stages.plan``. The
   first version of this check was ``"pipeline_stages" in src`` — a substring
   match a code review broke in one line: keep the import, replace the label
   calls with plain strings, and all 27 checks passed while the host had stopped
   deriving anything at all. Measured on the real gate, not argued.

3. THE ARTEFACT GRAPH MUST CLOSE. Every consumed artefact is produced by an
   EARLIER stage; every produced artefact is consumed by a later one or declared
   terminal. This is candidate 6a's defect stated as a static property: ``phi``
   produced by the IB stage and consumed by nobody would not have got past it.

4. ORDER IS RECOVERED, NOT ASSUMED. The runner's order is the source order of
   its ``_run_*`` calls. The GUI's is a signal chain, so it is recovered as a
   reachability graph over ``self._pipe*`` references — references, not calls,
   because ``_pipe_chain("_mesh_worker", self._pipe_after_mesh, ...)`` hands the
   continuation over as an ATTRIBUTE and a call-only walk would miss every
   second link. Both directions are asserted for each consecutive pair (B
   reachable from A, A not reachable from B), since forward reachability alone
   does not distinguish "after" from "either way round". 4d additionally pins
   that the GUI fixes its plan before the first stage starts: ``_pipe_label``
   falls back to the full declared set when there is no plan, and a fallback the
   normal path relies on is a wrong label on every run rather than a safety net.
   4d measures against stage ENTRY POINTS — anything from which a stage is
   reachable — not against the stage methods themselves, because
   ``run_full_pipeline`` never names the CAD stage: it goes through
   ``_pipe_resample_next``. Comparing against stage methods alone silently used
   the ``_pipe_stl3d`` call in the *else* branch, so moving the plan to just
   after ``self._pipe_resample_next()`` left the CAD stage on the fallback plan
   with 4d green. Found by review, reproduced, then widened.

5. NO HAND-WRITTEN STAGE COUNT. The thing that went wrong without anyone typing
   a wrong number: ``Stage 1/3`` … ``Stage 3/3`` at 8 sites across the two hosts
   while four stages existed, because the immersed solid was logged outside the
   numbering in both. A literal denominator where the plan is a variable. If a
   host grows one again, the declaration has stopped being read and check 5
   fails.

6. THE CHECKS VERIFY THEMSELVES BY INJECTION. Section 7 runs the same helpers
   against deliberately broken sources and asserts they FAIL. A gate that has
   never been shown to fail is a gate nobody has tested — and these are static
   checks, so the injection is free and permanent rather than a one-off done by
   hand at review time. Ten of them, three added after a review found the holes
   they now cover. One warning the review also produced: an injection that makes
   the source FAIL TO PARSE looks exactly like the check working. Every mutation
   here either compiles the result or asserts the text actually changed.

Known blind spots, named rather than papered over:
  - The GUI graph is syntactic. A continuation reached through a variable
    (``getattr(self, name)()``, a dict of slots) is invisible to it; today every
    link is a literal ``self._pipe*`` reference.
  - Nothing here runs a pipeline. That a declared stage's body does what its
    title says is the per-stage tests' job (test_pipeline_ib_handoff.py and the
    end-to-end run_pipeline.sh in CI).
  - Qt-freeness of the declaration is NOT re-checked here: test_qt_free_seam.py
    sweeps every ``services/*.py`` as a deny-list, so it is already gated and a
    second copy would be a second thing to keep in agreement.

Run:  python3 tools/PreProcessor/tests/test_pipeline_stages.py
"""
import ast
import io
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
sys.path.insert(0, _GUI)

from app.services import pipeline_stages as ps          # noqa: E402

RUNNER = os.path.join(_GUI, "app", "services", "pipeline_runner.py")
CTRL = os.path.join(_GUI, "app", "controllers", "pipeline_ctrl.py")
PROBES = os.path.join(_HERE, "arch_probes.py")

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def read(path):
    return io.open(path, encoding="utf-8").read()


# --------------------------------------------------------------------------- #
# Helpers. Each takes SOURCE TEXT rather than a path, so section 7 can run the
# very same code against a mutated copy.
# --------------------------------------------------------------------------- #
def runner_stage_defs(src):
    """Module-level ``_run_*`` functions — the runner's stage bodies."""
    tree = ast.parse(src)
    return {n.name for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name.startswith("_run_")}


def gui_methods(src, cls="PipelineControllerMixin"):
    """Every method of the GUI mixin, by name."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            return {n.name: n for n in node.body
                    if isinstance(n, ast.FunctionDef)}
    return {}


def gui_stage_defs(src):
    """The stage-shaped methods: ``_pipe_*`` minus the plumbing.

    The exclusions are the continuations (``_pipe_after_*``), the connect helper,
    the CAD-queue pump and the label formatter — none of which is a stage.
    ``arch_probes.probe_6b`` reads the same thing with a regex; that is a SECOND
    hand-kept copy, so check 1e below lifts the probe's own pattern out of its
    source and asserts the two classify this file identically. The docstring used
    to claim they "cannot disagree" while nothing compared them.
    """
    out = set()
    for name in gui_methods(src):
        if not name.startswith("_pipe_"):
            continue
        if name.startswith("_pipe_after_"):
            continue
        if name in ("_pipe_chain", "_pipe_resample_next", "_pipe_label"):
            continue
        out.add(name)
    return out


def derived_stage_keys(src, adapter):
    """Stage keys this host passes to its label adapter.

    Check 2 used to be ``"pipeline_stages" in src`` — a SUBSTRING match, which a
    review broke in one line: keep the import, replace every ``_label(...)`` with
    a plain string, and all 27 checks passed while the host had stopped deriving
    anything. Measured, on the real gate. A host that merely imports the module
    is not reading it, and the whole point of the declaration is that the labels
    come from it.
    """
    out = set()
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        f = node.func
        name = (f.id if isinstance(f, ast.Name)
                else f.attr if isinstance(f, ast.Attribute) else "")
        if name == adapter and isinstance(node.args[0], ast.Constant):
            out.add(node.args[0].value)
    return out


def calls_attr(src, module, attr):
    """Does the source call ``<module>.<attr>(...)`` anywhere?"""
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == attr
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == module):
            return True
    return False


def stage_entry_points(src, stage_fns, entry):
    """Methods that START a stage: a stage itself, or anything reaching one.

    4d used to compare the plan's line against the first reference to a STAGE
    method, and ``run_full_pipeline`` never names one for the CAD stage — it goes
    through ``_pipe_resample_next``, which the plumbing filter excludes. So the
    comparison silently used the ``_pipe_stl3d`` call in the *else* branch, and
    moving the plan assignment to just after ``self._pipe_resample_next()`` left
    the CAD stage running on the fallback plan with 4d still green. Measured on
    the real gate before this was widened.
    """
    graph = gui_chain_graph(src)
    starts = set()
    for m in graph:
        if m == entry:
            continue
        if m in stage_fns or any(reaches(graph, m, s, set()) for s in stage_fns):
            starts.add(m)
    return starts


def runner_call_order(src, func="run_pipeline"):
    """The ``_run_*`` stage calls inside the orchestrator, in source order."""
    tree = ast.parse(src)
    fn = next((n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == func), None)
    if fn is None:
        return []
    seen, order = set(), []
    for node in sorted((n for n in ast.walk(fn) if isinstance(n, ast.Call)),
                       key=lambda n: (n.lineno, n.col_offset)):
        f = node.func
        if isinstance(f, ast.Name) and f.id.startswith("_run_") and f.id not in seen:
            seen.add(f.id)
            order.append(f.id)
    return order


def gui_chain_graph(src):
    """method -> the mixin methods it hands control to.

    Edges come from any ``self.<name>`` REFERENCE, not only calls: the chain is
    built by passing a bound continuation to ``_pipe_chain``, so half the links
    are attribute loads. Filtered to names that are actually methods of the
    mixin, which drops the ``_pipe_plan`` / ``_pipe_cad_queue`` state attributes.
    """
    methods = gui_methods(src)
    graph = {}
    for name, node in methods.items():
        refs = set()
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name)
                    and sub.value.id == "self" and sub.attr in methods
                    and sub.attr != name):
                refs.add(sub.attr)
        graph[name] = refs
    return graph


def reaches(graph, start, target, barriers):
    """Is ``target`` reachable from ``start`` without passing THROUGH a barrier?

    Barriers are the other stages: stopping at them is what makes this answer
    "does A hand over to B", rather than "is B somewhere downstream of A".
    """
    seen, stack = set(), [start]
    while stack:
        cur = stack.pop()
        for nxt in graph.get(cur, ()):
            if nxt == target:
                return True
            if nxt in seen or nxt in barriers:
                continue
            seen.add(nxt)
            stack.append(nxt)
    return False


# Widened past the literal `Stage 2/3`: an f-string (`Stage {i}/3`) re-derives the
# count just as badly and the narrow form missed it. Both sides must be a digit or
# a `{...}` placeholder, so PROSE describing the format ("Stage i/N") is not a hit
# — a first attempt matched any slash within 14 characters and flagged three
# comments and a docstring, which is the shape of a check nobody keeps green.
# Blind spot named rather than chased: "Stage 2 of 3" still gets through, which is
# why checks 2a/2b — every stage label must come from the declaration — are the
# primary defence and this is only the backstop.
COUNT_RE = re.compile(r"Stage\s*(?:\{[^}\n]*\}|\d+)\s*/\s*(?:\{[^}\n]*\}|\d+)")


def literal_counts(src):
    """Lines hand-writing a ``Stage i/N`` count.

    Unconditional on purpose: an exemption marker would be an escape hatch that
    the next person reintroducing a literal can reach for. The one line that
    needed to show the format shows the SHAPE instead (``Stage i/N``), so there
    is nothing legitimate left to exempt.
    """
    return [ln.strip() for ln in src.splitlines() if COUNT_RE.search(ln)]


def plan_before_first_stage(src, stage_fns, entry="run_full_pipeline"):
    """``(plan_line, first_stage_line)`` inside the GUI's entry point.

    ``10**9`` for "never", so a missing plan sorts after every stage and the
    caller's ``<`` comparison fails rather than silently passing.
    """
    fn = gui_methods(src).get(entry)
    if fn is None:
        return 10 ** 9, 0

    def lines(pred):
        return [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name) and n.value.id == "self"
                and pred(n.attr)] or [10 ** 9]

    return min(lines(lambda a: a == "_pipe_plan")), min(lines(stage_fns.__contains__))


def move_plan_after_cad_start(src):
    """Inject: the plan fixed only AFTER the CAD stage has been started.

    Re-indented into the if-branch so the result still PARSES — a first attempt
    at this injection produced an orphaned ``else`` and the gate failed on the
    syntax error, which looks exactly like the check working and is not.
    """
    block = src[src.index("        ib_cfg = getattr"):
                src.index("        if self._pipe_cad_queue:")]
    inner = "".join(("    " + ln if ln.strip() else ln) + "\n"
                    for ln in block.rstrip("\n").split("\n"))
    out = src.replace(block, "").replace(
        "            self._pipe_resample_next()\n",
        "            self._pipe_resample_next()\n" + inner, 1)
    compile(out, "<injected>", "exec")
    return out


def artefact_problems(stages, terminal):
    """Every way the produced/consumed graph fails to close."""
    problems = []
    produced_so_far = set()
    produced_all, consumed_all = set(), set()
    for st in stages:
        for a in st.consumes:
            if a not in produced_so_far:
                problems.append(
                    f"{st.key!r} consumes {a!r}, which no earlier stage produces")
        produced_so_far |= set(st.produces)
        produced_all |= set(st.produces)
        consumed_all |= set(st.consumes)
    for a in sorted(produced_all - consumed_all - set(terminal)):
        problems.append(f"{a!r} is produced but consumed by no stage "
                        "and is not declared terminal")
    for a in sorted(set(terminal) - produced_all):
        problems.append(f"{a!r} is declared terminal but no stage produces it")
    return problems


runner_src, ctrl_src = read(RUNNER), read(CTRL)

# --------------------------------------------------------------------------- #
# 0. The declaration is well formed.
# --------------------------------------------------------------------------- #
keys = [s.key for s in ps.STAGES]
check(f"0a. the stage set is declared and non-trivial ({len(ps.STAGES)} stages)",
      len(ps.STAGES) >= 2)
check("0b. stage keys are unique" + (f": {keys}" if len(set(keys)) != len(keys) else ""),
      len(set(keys)) == len(keys))
check("0c. a non-optional stage is always in the plan",
      all(s in ps.plan({}) for s in ps.STAGES if not s.optional))
check("0d. an optional stage is absent from a plan that does not ask for it",
      all(s not in ps.plan({}) for s in ps.STAGES if s.optional))

# --------------------------------------------------------------------------- #
# 1. Both hosts implement exactly the declared set — in both directions.
# --------------------------------------------------------------------------- #
declared_runner = {s.runner_fn for s in ps.STAGES}
declared_gui = {s.gui_fn for s in ps.STAGES}
found_runner = runner_stage_defs(runner_src)
found_gui = gui_stage_defs(ctrl_src)

missing_r = sorted(declared_runner - found_runner)
missing_g = sorted(declared_gui - found_gui)
extra_r = sorted(found_runner - declared_runner)
extra_g = sorted(found_gui - declared_gui)

check("1a. every declared stage is implemented in the headless runner"
      + (f" (missing: {missing_r})" if missing_r else ""), not missing_r)
check("1b. every declared stage is implemented in the GUI host"
      + (f" (missing: {missing_g})" if missing_g else ""), not missing_g)
check("1c. the headless runner has no undeclared stage"
      + (f" (undeclared: {extra_r})" if extra_r else ""), not extra_r)
check("1d. the GUI host has no undeclared stage"
      + (f" (undeclared: {extra_g})" if extra_g else ""), not extra_g)

# 1e. arch_probes reads the GUI's stage list too, with its own regex. Lift that
# pattern out of the probe rather than restating it, so the two cannot drift.
_pat = re.search(r'r"(\^ +def \(_pipe_[^"]*)"', read(PROBES))
# No unescaping: the text lifted from the source of a RAW string literal is
# already the regex. Running it through "unicode_escape" would also silently
# turn a `\b` word-boundary into a backspace character.
_probe_view = set(re.findall(_pat.group(1), ctrl_src, re.M)) if _pat else None
check("1e. arch_probes and this gate classify the GUI's stages identically"
      + ("" if _pat else " [probe pattern not found]"),
      _probe_view == found_gui)

# --------------------------------------------------------------------------- #
# 2. Both hosts actually READ the declaration.
# --------------------------------------------------------------------------- #
declared_keys = {s.key for s in ps.STAGES}
for tag, src, adapter, host in (("2a", runner_src, "_label", "headless runner"),
                                ("2b", ctrl_src, "_pipe_label", "GUI host")):
    got = derived_stage_keys(src, adapter)
    check(f"{tag}. the {host} derives a label for every declared stage "
          + (f"(missing: {sorted(declared_keys - got)})"
             if declared_keys - got else f"({len(got)} keys)"),
          got == declared_keys)
check("2c. the headless runner builds its plan from the declaration",
      calls_attr(runner_src, "pipeline_stages", "plan"))
check("2d. the GUI host builds its plan from the declaration",
      calls_attr(ctrl_src, "pipeline_stages", "plan"))

# --------------------------------------------------------------------------- #
# 3. The artefact graph closes.
# --------------------------------------------------------------------------- #
probs = artefact_problems(ps.STAGES, ps.TERMINAL)
check("3. every artefact is produced before it is consumed, and consumed or "
      "terminal after it is produced" + (f": {probs}" if probs else ""), not probs)

# --------------------------------------------------------------------------- #
# 4. Both hosts run the stages in the declared order.
# --------------------------------------------------------------------------- #
expected = [s.runner_fn for s in ps.STAGES]
actual = runner_call_order(runner_src)
check(f"4a. the runner calls its stages in the declared order (got {actual})",
      actual == expected)

graph = gui_chain_graph(ctrl_src)
stage_nodes = {s.gui_fn for s in ps.STAGES}
fwd, back = [], []
for a, b in zip(ps.STAGES, ps.STAGES[1:]):
    if not reaches(graph, a.gui_fn, b.gui_fn, stage_nodes - {a.gui_fn, b.gui_fn}):
        fwd.append(f"{a.key} -/-> {b.key}")
    if reaches(graph, b.gui_fn, a.gui_fn, stage_nodes - {a.gui_fn, b.gui_fn}):
        back.append(f"{b.key} --> {a.key}")
check("4b. the GUI chain hands each stage to the next, in the declared order"
      + (f": {fwd}" if fwd else ""), not fwd)
check("4c. the GUI chain does not run a stage before its predecessor"
      + (f": {back}" if back else ""), not back)

# 4d. The GUI fixes its plan BEFORE the first stage runs. `_pipe_label` falls
# back to the full declared set when there is no plan, which keeps a stray
# continuation from taking the run down — but a fallback that the normal path
# relies on is a wrong label on every run, so the ordering is pinned here rather
# than left to the fallback to hide.
_entries = stage_entry_points(ctrl_src, stage_nodes, "run_full_pipeline")
_plan_at, _stage_at = plan_before_first_stage(ctrl_src, _entries)
check("4d. run_full_pipeline fixes the plan before it starts the first stage "
      f"(plan at line {_plan_at}, first stage at {_stage_at})",
      _plan_at < _stage_at)

# --------------------------------------------------------------------------- #
# 5. Neither host hand-writes a stage count.
# --------------------------------------------------------------------------- #
for label, src in (("headless runner", runner_src), ("GUI host", ctrl_src)):
    hits = literal_counts(src)
    check(f"5. the {label} writes no literal stage count"
          + (f": {hits}" if hits else ""), not hits)

# --------------------------------------------------------------------------- #
# 6. The count follows the plan — the user-visible half.
# --------------------------------------------------------------------------- #
full = ps.plan({s.key: True for s in ps.STAGES})
lean = ps.plan({s.key: True for s in ps.STAGES if s.key != "stl3d"})
check(f"6a. a run with every stage numbers them out of {len(ps.STAGES)} "
      f"(got {ps.label(ps.STAGES[0], full)})",
      ps.label(ps.STAGES[0], full)
      == f"Stage 1/{len(ps.STAGES)}: {ps.STAGES[0].title}")
check("6b. dropping the immersed solid drops the denominator too "
      f"(got {ps.label(ps.STAGES[0], lean)})",
      ps.label(ps.STAGES[0], lean) == f"Stage 1/{len(full) - 1}: {ps.STAGES[0].title}")
check("6c. a stage that is not running is labelled without a position",
      ps.label(ps.by_key("stl3d"), lean) == ps.by_key("stl3d").title)

# --------------------------------------------------------------------------- #
# 7. The checks fail when they should. Each mutation is the real defect this
#    candidate exists to prevent, injected into a copy of the source.
# --------------------------------------------------------------------------- #
inj = []


def injected(name, cond):
    print(("PASS " if cond else "FAIL ") + f"7. injection: {name}")
    if not cond:
        inj.append(name)


# 7a. a stage added to the GUI only
mutated = ctrl_src.replace(
    "    def _pipe_resample_next(self):",
    "    def _pipe_contour(self):\n        pass\n\n    def _pipe_resample_next(self):",
    1)
injected("a stage implemented in the GUI alone is caught",
         bool(gui_stage_defs(mutated) - declared_gui))

# 7b. a declared stage deleted from the headless runner
mutated = runner_src.replace("def _run_stl3d(", "def _run_stl3d_disabled(", 1)
injected("a declared stage missing from the runner is caught",
         bool(declared_runner - runner_stage_defs(mutated)))

# 7c. an artefact produced for nobody — candidate 6a's defect, as data
mutated_stages = tuple(
    ps.Stage(s.key, s.title, (), s.produces, s.optional, s.runner_fn, s.gui_fn)
    if s.key == "solver" else s
    for s in ps.STAGES)
injected("an artefact produced and consumed by nobody is caught",
         bool(artefact_problems(mutated_stages, ps.TERMINAL)))

# 7d. an artefact consumed before anything produces it
mutated_stages = tuple(
    ps.Stage(s.key, s.title, (ps.VTK,), s.produces, s.optional, s.runner_fn,
             s.gui_fn)
    if s.key == "resample" else s
    for s in ps.STAGES)
injected("an artefact consumed before it is produced is caught",
         bool(artefact_problems(mutated_stages, ps.TERMINAL)))

# 7e. the GUI chain reordered so a stage no longer hands over to its successor
mutated = ctrl_src.replace("        self._pipe_mesh()", "        pass")
g2 = gui_chain_graph(mutated)
injected("a broken GUI hand-off is caught",
         not reaches(g2, ps.by_key("stl3d").gui_fn, ps.by_key("mesh").gui_fn,
                     stage_nodes - {ps.by_key("stl3d").gui_fn,
                                    ps.by_key("mesh").gui_fn}))

# 7f. a host that stops reading the declaration and hard-codes a count again
mutated = ctrl_src.replace(
    "self.log(f\"[Pipeline] {self._pipe_label('mesh')} — generating mesh...\")",
    'self.log("[Pipeline] Stage 2/3: generating mesh...")', 1)
injected("a re-introduced literal stage count is caught",
         mutated != ctrl_src and bool(literal_counts(mutated)))

# 7g. the plan computed after the first stage has already started
mutated = re.sub(r"\n *self\._pipe_plan = pipeline_stages\.plan\(\{.*?\n *\}\)\n",
                 "\n", ctrl_src, count=1, flags=re.S)
_p, _s = plan_before_first_stage(mutated, stage_nodes)
injected("a plan that is not fixed before the first stage is caught",
         mutated != ctrl_src and not (_p < _s))

# 7h. a host that keeps the import but stops DERIVING (the substring hole)
mutated = runner_src.replace('log(f"=== {_label(\'mesh\')} ===")',
                             'log("=== mesh generation ===")', 1)
injected("a host that imports the declaration but stops deriving is caught",
         mutated != runner_src and "pipeline_stages" in mutated
         and derived_stage_keys(mutated, "_label") != declared_keys)

# 7i. the plan fixed only after the CAD stage has started
mutated = move_plan_after_cad_start(ctrl_src)
_p, _s = plan_before_first_stage(
    mutated, stage_entry_points(mutated, stage_nodes, "run_full_pipeline"))
injected("a plan fixed after the CAD stage starts is caught",
         mutated != ctrl_src and not (_p < _s))

# 7j. a misspelt stage key silently dropping a stage from the plan
try:
    ps.plan({"resamlpe": True, "solver": True})
    _raised = False
except KeyError:
    _raised = True
injected("an unknown stage key is refused rather than ignored", _raised)

failures.extend(f"injection did not fail the check: {n}" for n in inj)

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All pipeline stage-declaration checks passed.")
