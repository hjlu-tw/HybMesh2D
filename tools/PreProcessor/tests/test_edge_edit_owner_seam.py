#!/usr/bin/env python3
"""The edge-edit owner is a seam, and this is the ratchet that keeps it one.

Architecture backlog candidate 7, ticket 5 (issue #19) — the one that makes the
candidate DONE. #15-#18 moved the state; this fails the build when it starts
moving back.

What the seam is. A modeless edge edit — analytic (arc/line/circle/polygon), the
imported-outline corner edit, or a committed edge's handle drag — used to be
**thirteen attributes on ``AppController``**, declared in one file and mutated
from four, with "an edit is live" enforced by every reader remembering a ``None``
check. They are one owner now (``services/edge_edit.EdgeEditSession``), Qt-free,
with the lifecycle behind verbs.

Five properties, each a function over SOURCE so the injection at the bottom can
run it against mutated text:

1. NO MODAL-EDIT STATE ON ``AppController``. The thing the candidate exists to
   remove. A new ``self._pending_*`` or ``self._drag_*`` in ``__init__`` is the
   drift, and it is the cheap kind to make — one line, in the file that already
   holds forty other attributes.

2. NOBODY REACHES PAST THE VERBS. A caller doing ``self.edge_edit._seg`` gets
   the same coupling back with an underscore in front of it, and that is how a
   seam decays in silence — the same failure ``test_user_log_seam.py`` and
   ``test_sidebar_seam.py`` guard for their own.

3. THE OWNER IS QT-FREE, CHECKED IN A SUBPROCESS. In-process the answer is
   always "yes, PyQt6 is loaded" once any other test has imported it, so the
   assertion would pass for the wrong reason exactly when it matters — the
   lesson ``test_qt_free_seam.py`` records. And a DEFERRED import inside a
   function body is still a dependency an import-time sweep cannot see, so the
   AST is read at any nesting depth as well.

4. ``_edit_in_progress()`` ASKS EXACTLY ONE THING. Two edit kinds in one owner
   is what bought that; an ``or`` creeping back means a second home for the
   state exists again.

5. A COMMIT RESOLVES ITS SESSION FROM THE OUTCOME. The #18 defect in one line:
   resolving through ``active_session()`` alone commits an edit onto whichever
   tab is in front, which — because segment ids collide across tabs — lands it
   on another tab's edge.

BLIND SPOTS, named rather than papered over:

* Check 1 matches attribute NAMES. State smuggled back under a name that does
  not look like edit state (``self._live``, ``self._ctx``) is invisible to it.
  What it really defends is the cheap regression, not a determined one.
* Check 2 resolves ``self.edge_edit`` and simple local aliases of it. A less
  direct route (``getattr(owner, "_seg")``, or the owner passed as an argument
  and poked there) escapes — the same "a string is not an attribute access"
  hole that let issue #20 live for six days in a neighbouring seam.
* Check 3 proves the module IMPORTS and DRIVES without Qt. It does not prove
  every branch is Qt-free; a PyQt6 import added inside a rarely-taken branch
  would pass the drive and be caught only by the AST half.
* Check 5 reads the two commit paths' source. A third commit path added
  elsewhere is not enrolled, and nothing here would notice.
* Behaviour is NOT this file's job — the owner's verbs are pinned in
  ``test_edge_edit_owner.py``, the drag wiring in ``test_committed_drag_undo.py``
  and the session binding + prompts in ``test_edit_session_binding.py``. This
  gate pins the SHAPE those three depend on.

Run:  python3 tools/PreProcessor/tests/test_edge_edit_owner_seam.py
"""
import ast
import os
import subprocess
import sys
import textwrap

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def read(*parts):
    with open(os.path.join(_GUI, *parts)) as fh:
        return fh.read()


# ══════════════════════════════════════════════════════════════════════════
# The checks, as functions over source text. Each returns a list of
# violations, so a passing check is an empty list and the injection at the
# bottom can run the same function against mutated text.
# ══════════════════════════════════════════════════════════════════════════

#: Attribute-name shapes that mean "modal edit state" on the god object. These
#: are the thirteen that were removed, generalised one step.
_EDIT_STATE_PREFIXES = ("_pending", "_drag_", "_edit_", "_geom_edit")


def controller_edit_state(src: str) -> list[str]:
    """Attributes on AppController that look like modal-edit state."""
    tree = ast.parse(src)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if (isinstance(tgt, ast.Attribute)
                    and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == "self"
                    and tgt.attr.startswith(_EDIT_STATE_PREFIXES)):
                found.append(tgt.attr)
    return sorted(set(found))


def private_reach(src: str) -> list[str]:
    """Accesses of a PRIVATE attribute on the owner, from outside it.

    Resolves ``self.edge_edit`` and any local name assigned from it, so the
    one-line alias dodge does not walk straight past.
    """
    tree = ast.parse(src)
    aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt, val = node.targets[0], node.value
            if (isinstance(tgt, ast.Name) and isinstance(val, ast.Attribute)
                    and val.attr == "edge_edit"):
                aliases.add(tgt.id)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not node.attr.startswith("_"):
            continue
        base = node.value
        is_owner = (isinstance(base, ast.Attribute) and base.attr == "edge_edit") \
            or (isinstance(base, ast.Name) and base.id in aliases)
        if is_owner:
            hits.append(f"line {node.lineno}: .{node.attr}")
    return hits


_QT_ROOTS = ("PyQt6", "PyQt5", "pyqtgraph")


def qt_imports(src: str) -> list[str]:
    """Qt imports anywhere in the module, at ANY nesting depth."""
    tree = ast.parse(src)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            if name.split(".")[0] in _QT_ROOTS or name.startswith(
                    ("app.views", "app.utils")):
                hits.append(f"line {node.lineno}: {name}")
    return hits


def predicate_terms(src: str) -> list[str]:
    """What ``_edit_in_progress()`` asks. More than one term is the drift."""
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_edit_in_progress"), None)
    if fn is None:
        return ["_edit_in_progress is missing"]
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    bools = [n for n in ast.walk(fn) if isinstance(n, ast.BoolOp)]
    terms = [ast.unparse(c) for c in calls]
    if bools:
        terms.append("BoolOp (an 'or' is back)")
    if not any("edge_edit.is_active" in t for t in terms):
        terms.append("does not ask the owner")
    return terms if (len(calls) != 1 or bools
                     or not any("edge_edit.is_active" in t for t in terms)) else []


def commit_session_resolution(src: str, fn_names) -> list[str]:
    """Commit paths that never read the outcome's own session."""
    tree = ast.parse(src)
    bad = []
    for name in fn_names:
        fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                   and n.name == name), None)
        if fn is None:
            bad.append(f"{name} is missing")
            continue
        body = ast.unparse(fn)
        if ".session" not in body:
            bad.append(f"{name} never reads the outcome's session")
    return bad


# ══════════════════════════════════════════════════════════════════════════
# Run them against the tree
# ══════════════════════════════════════════════════════════════════════════
CONTROLLER = read("app", "controller.py")
OWNER = read("app", "services", "edge_edit.py")
DRAW = read("app", "controllers", "curve_draw_ctrl.py")
PENDING = read("app", "controllers", "pending_edit_ctrl.py")
FILE_EDIT = read("app", "controllers", "file_edit_ctrl.py")

leaked = controller_edit_state(CONTROLLER)
check(f"1. no modal-edit state on AppController ({leaked or 'none'})", not leaked)
check("1b. …and the owner IS declared there", "EdgeEditSession()" in CONTROLLER)

reach = []
for root, _dirs, files in os.walk(os.path.join(_GUI, "app")):
    for fn in sorted(files):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(root, fn)
        rel = os.path.relpath(path, _GUI)
        with open(path) as fh:
            hits = private_reach(fh.read())
        reach += [f"{rel} {h}" for h in hits]
check(f"2. nobody reaches past the owner's verbs ({reach or 'none'})", not reach)

owner_qt = qt_imports(OWNER)
check(f"3a. the owner imports nothing Qt at any depth ({owner_qt or 'none'})",
      not owner_qt)
refit_qt = qt_imports(read("app", "services", "shape_refit.py"))
check(f"3b. …nor does shape_refit ({refit_qt or 'none'})", not refit_qt)

_DRIVE = textwrap.dedent('''
    import sys
    class NoQt:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in ("PyQt6", "PyQt5", "pyqtgraph"):
                raise ImportError("Qt refused: " + name)
            return None
    sys.meta_path.insert(0, NoQt())
    sys.path.insert(0, sys.argv[1])
    from app.services.edge_edit import EdgeEditSession

    class Seg:
        id = 1
        type = "curve"
        curve_type = "polygon"
        parameters = {"n_points": 5}
        closed = True
        def to_dict(self):
            return {"id": self.id, "parameters": dict(self.parameters)}

    o = EdgeEditSession()
    s = Seg()
    assert o.is_active() is False
    assert o.begin(s, is_new=False, session="S") is True
    assert o.is_active() and o.owning_session == "S"
    assert o.update({"a": 1}, 9) is True
    assert o.begin(Seg(), is_new=True, session="T") is False   # the invariant
    out = o.cancel()
    assert out is not None and out.session == "S" and out.reverted is True
    assert o.is_active() is False
    assert o.begin_drag(s, session="S") is True
    assert o.release_drag_for("S") is True and o.is_dragging() is False
    assert not any(m.split(".")[0] in ("PyQt6", "PyQt5", "pyqtgraph")
                   for m in sys.modules)
    print("DROVE-CLEAN")
''')
proc = subprocess.run([sys.executable, "-c", _DRIVE, _GUI],
                      capture_output=True, text=True)
_drove = proc.returncode == 0 and "DROVE-CLEAN" in proc.stdout
_why = "" if _drove else " — " + (
    proc.stderr.strip().splitlines() or ["no output"])[-1]
check(f"3c. the whole lifecycle DRIVES in a subprocess with Qt blocked{_why}",
      _drove)

terms = predicate_terms(DRAW)
check(f"4. _edit_in_progress() asks exactly one thing ({terms or 'one'})",
      not terms)

bad = (commit_session_resolution(PENDING, ["_commit_pending_edge"])
       + commit_session_resolution(FILE_EDIT, ["_commit_file_edit"]))
check(f"5. every commit resolves its session from the outcome ({bad or 'both'})",
      not bad)


# ══════════════════════════════════════════════════════════════════════════
# Injection: each static check, proven to fire — and each mutation proven to
# still PARSE and to really differ, because a mutation that breaks the parse
# looks exactly like the check working.
# ══════════════════════════════════════════════════════════════════════════
print()
print("── injections ──")


def inject(name, src, old, new, fn, *args):
    if old not in src:
        check(f"INJ {name}: target present in the source", False)
        return
    mutated = src.replace(old, new, 1)
    if mutated == src:
        check(f"INJ {name}: the mutation really changed the source", False)
        return
    try:
        ast.parse(mutated)
    except SyntaxError as exc:
        check(f"INJ {name}: the mutated source still parses ({exc})", False)
        return
    check(f"INJ {name}: the check fires on the mutation",
          bool(fn(mutated, *args)))


inject("1 a new pending attribute on the controller", CONTROLLER,
       "self.edge_edit = EdgeEditSession()",
       "self.edge_edit = EdgeEditSession()\n        self._pending_seg = None",
       controller_edit_state)

inject("2 a mixin reaching for a private field", PENDING,
       "done = self.edge_edit.commit()",
       "done = self.edge_edit._seg and self.edge_edit.commit()",
       private_reach)

inject("2b …through a one-line alias", PENDING,
       "done = self.edge_edit.commit()",
       "ee = self.edge_edit\n        done = ee._orig_state and ee.commit()",
       private_reach)

inject("3 a Qt import deferred inside a function body", OWNER,
       "    def is_active(self) -> bool:",
       "    def is_active(self) -> bool:\n        from PyQt6.QtCore import Qt  "
       "# noqa\n        _ = Qt",
       qt_imports)

inject("3b a Qt import at module level", OWNER,
       "import copy", "import copy\nimport pyqtgraph", qt_imports)

inject("4 the predicate's 'or' comes back", DRAW,
       "return self.edge_edit.is_active()",
       "return self.edge_edit.is_active() or self._pending_file is not None",
       predicate_terms)

inject("4b the predicate stops asking the owner", DRAW,
       "return self.edge_edit.is_active()", "return False",
       predicate_terms)

inject("5 commit resolves through the active tab again", PENDING,
       "session = done.session or self.active_session()",
       "session = self.active_session()",
       commit_session_resolution, ["_commit_pending_edge"])

inject("5b the shape commit does the same", FILE_EDIT,
       "session = done.session or self.active_session()",
       "session = self.active_session()",
       commit_session_resolution, ["_commit_file_edit"])

# Anti-vacuity: the sweep in check 2 must really have read the controllers a
# reach-through would hide in. A walk that quietly stops covering a file still
# reports a clean pass.
_scanned = set()
for root, _dirs, files in os.walk(os.path.join(_GUI, "app", "controllers")):
    for fn in files:
        if fn.endswith(".py"):
            _scanned.add(fn)
for must in ("pending_edit_ctrl.py", "file_edit_ctrl.py", "curve_draw_ctrl.py",
             "curve_edit_ctrl.py", "session_tabs_ctrl.py"):
    check(f"6. the reach-through sweep covers {must}", must in _scanned)

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All edge-edit owner seam checks passed.")
