#!/usr/bin/env python3
"""A module that claims to be headless-safe must not load the GUI toolkit.

Candidate 9 of the architecture backlog. ``app/utils.py`` was a namespace, not a
module: message boxes, signal guards, pop-up stacking and form builders in the
first two thirds, pure ``os``/``shutil`` path resolution in the last third, one
name, and that name sits on the Qt side of a seam running through the middle of
the file. So every headless module that needed a path imported PyQt6 —
measured before the split: ``import app.services.pipeline_runner`` loaded
``PyQt6``, ``PyQt6.sip``, ``PyQt6.QtCore``, ``PyQt6.QtGui`` and
``PyQt6.QtWidgets``, four lines below its own comment saying "no PyQt import, so
this module stays headless-safe". ``run_pipeline.sh`` and ``run_batch.sh``
therefore required the toolkit on a compute node that will never draw a window.

What this pins, and why each check is shaped the way it is:

1. THE CHECK MUST BE A SUBPROCESS. In-process the answer is always "yes, PyQt6
   is loaded" once any other test in the suite has imported it, so an in-process
   assertion would pass for the wrong reason exactly when it matters. Every
   import check below runs in a fresh interpreter.

2. THE HEADLESS ENTRY POINTS, AS SCRIPTS. ``run_pipeline.py`` / ``run_batch.py``
   are what the shell wrappers actually run, so they are loaded from their own
   paths rather than approximated by importing a service they happen to use.

3. EVERY services/ MODULE, AS A DENY-LIST. A hand-picked list of modules to
   check would not cover the next service somebody adds. The list here is
   therefore inverted: a new ``services/*.py`` is assumed Qt-free, and making
   one Qt-dependent costs an entry in ``QT_SERVICES`` with its reason — the same
   reasoning as ``HEAVY_SOURCES`` in test_cpp_pure_layer.py. An allow-list would
   have the failure mode backwards: forgetting to enrol a new pure module would
   silently exempt it.

4. THE DEPTH IS PINNED BY RESOLVED PATH, NOT BY SEGMENT COUNT. ``repo_root``
   walks up a fixed number of ``..`` from ``__file__``; its own docstring warns
   this is an easy off-by-one, and moving it one level deeper is exactly that
   situation. Counting segments in the source would pin the bug as readily as
   the fix, so this resolves the value and checks the tree it lands on. The
   block moved contained a SECOND, disagreeing count — ``find_binary_executable``
   walked five levels from ``gui/app`` and so resolved outside the repo
   (``…/CESE/build``); it now goes through ``repo_root()``, and check 4c fails
   if a second count reappears.

5. THE RE-EXPORT MUST STAY A RE-EXPORT. ``app/utils.py`` keeps the names so the
   Qt-side call sites are untouched, which means the seam can be undone by
   pasting a body back next to them. Both halves must be the same object.

6. A DEFERRED IMPORT IS STILL A DEPENDENCY, and checks 1-3 cannot see it.
   Measured: with checks 1-3 green, ``run_pipeline.sh`` on a machine with PyQt6
   uninstalled still died in stage 2 — ``mesh_config_io.config_to_text`` did
   ``from app.utils import repo_root`` inside a function body, so it loaded no
   Qt at import time (the sweep called it clean) and needed the toolkit anyway
   the moment a mesh config was written. Three such sites existed, in
   ``models/`` and ``workers/``. So 6a reads the AST for a moved name imported
   from ``app.utils`` at ANY nesting depth, and 6b blocks PyQt6 outright in a
   subprocess and drives the exact path that failed.

Known blind spots, named rather than papered over:
  - 6b exercises the config writers, not a whole pipeline; a Qt dependency
    reachable only from a stage this repo cannot run without its binaries would
    still hide. The end-to-end claim was verified by hand once
    (``PYTHONPATH=<blocker> ./run_pipeline.sh config/pipeline/naca_demo.json
    --no-solver`` completed), which is evidence about one commit, not a gate.
  - 6a lists the MOVED names. A *new* pure helper added to ``app/utils.py``
    rather than to ``paths.py`` is not covered — nothing here says the Qt file
    may not grow a pure function, only that these six are not in it.
  - ``models/`` is not swept for import-time Qt: ``models/shape_spec.py``
    imports ``block_signals``, a genuinely Qt helper, and the cycle in
    CANNOT_IMPORT_STANDALONE blocks a clean sweep besides.

Run:  python3 tools/PreProcessor/tests/test_qt_free_seam.py
"""
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_PRE = os.path.abspath(os.path.join(_HERE, ".."))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, _GUI)

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


# ---------------------------------------------------------------------------
# services/ modules that legitimately depend on Qt. Each entry costs a reason.
# ---------------------------------------------------------------------------
QT_SERVICES = {
    "i18n": "wraps QTranslator/QLocale — the translation machinery IS Qt's",
    "ui_state": "wraps QSettings for window geometry and dock state",
}

# Modules that cannot be imported first today, for a reason that has nothing to
# do with Qt. Recorded so the sweep neither hides them nor fails the build on a
# pre-existing defect it did not cause.
CANNOT_IMPORT_STANDALONE = {
    "index_helpers": (
        "pre-existing import cycle, unrelated to the Qt seam: index_helpers -> "
        "models.segment -> models/__init__ -> models.session -> commands.base "
        "-> commands/__init__ -> commands.segment_cmds -> "
        "commands.segment_structure_cmds -> index_helpers (partially "
        "initialized). Enabled by the eager re-exports in the two __init__.py"),
}

_PROBE = (
    "import sys\n"
    "{load}\n"
    "print('QT:' + ','.join(sorted(n for n in sys.modules "
    "if n.split('.')[0] == 'PyQt6')))\n"
)


def qt_modules_after(load_stmt, cwd):
    """Names of PyQt6 modules loaded by *load_stmt* in a FRESH interpreter.

    Returns (list_or_None, error). None means the load itself failed, which is a
    different finding from "loaded Qt" and is reported as such.
    """
    try:
        r = subprocess.run([sys.executable, "-c", _PROBE.format(load=load_stmt)],
                           cwd=cwd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"probe could not run: {exc}"
    if r.returncode != 0:
        tail = (r.stderr.strip().splitlines() or ["?"])[-1]
        return None, tail
    line = [ln for ln in r.stdout.splitlines() if ln.startswith("QT:")]
    if not line:
        return None, "probe produced no QT: line"
    return [m for m in line[-1][3:].split(",") if m], ""


# ---------------------------------------------------------------------------
# 1 + 2. The headless entry points the shell wrappers actually run.
# ---------------------------------------------------------------------------
_SCRIPT_LOAD = (
    "import importlib.util, sys\n"
    "spec = importlib.util.spec_from_file_location('_probe_entry', {path!r})\n"
    "mod = importlib.util.module_from_spec(spec)\n"
    "sys.modules['_probe_entry'] = mod\n"
    "spec.loader.exec_module(mod)\n"
)

for script in ("run_pipeline.py", "run_batch.py"):
    path = os.path.join(_PRE, script)
    if not os.path.exists(path):
        check(f"2. {script} exists to be checked", False)
        continue
    qt, err = qt_modules_after(_SCRIPT_LOAD.format(path=path), cwd=_PRE)
    if qt is None:
        check(f"2. {script} loads in a fresh interpreter", False)
        print(f"       {err}")
        continue
    check(f"2. {script} loads no PyQt6 module in a fresh interpreter"
          + (f" (loaded {len(qt)}: {', '.join(qt[:3])}…)" if qt else ""), not qt)

# The runner named in the acceptance criterion, checked by name as well as via
# the script, since the script could stop importing it.
qt, err = qt_modules_after("import app.services.pipeline_runner", cwd=_GUI)
check("1. importing app.services.pipeline_runner loads no PyQt6 module"
      + (f" (loaded {len(qt or [])})" if qt else f" [{err}]" if err else ""),
      qt == [])

# ---------------------------------------------------------------------------
# 3. Every services/ module, deny-list style.
# ---------------------------------------------------------------------------
svc_dir = os.path.join(_GUI, "app", "services")
mods = sorted(f[:-3] for f in os.listdir(svc_dir)
              if f.endswith(".py") and f != "__init__.py")
check(f"3. the services/ sweep found modules to check ({len(mods)})", len(mods) > 20)

leaked, broke = [], []
for name in mods:
    if name in QT_SERVICES:
        continue
    qt, err = qt_modules_after(f"import app.services.{name}", cwd=_GUI)
    if qt is None:
        if name not in CANNOT_IMPORT_STANDALONE:
            broke.append(f"{name} ({err})")
        continue
    if qt:
        leaked.append(f"{name} -> {len(qt)} PyQt6 modules")

check("3a. no services/ module outside QT_SERVICES loads PyQt6 at import"
      + (f": {leaked}" if leaked else ""), not leaked)
check("3b. every services/ module imports standalone (or is recorded as not)"
      + (f": {broke}" if broke else ""), not broke)

# A stale deny-list entry is a silent exemption: if a module stopped needing Qt,
# it must leave the list rather than sit there excused.
stale = []
for name in sorted(QT_SERVICES):
    if name not in mods:
        stale.append(f"{name} (module gone)")
        continue
    qt, _ = qt_modules_after(f"import app.services.{name}", cwd=_GUI)
    if qt == []:
        stale.append(f"{name} (no longer loads Qt — drop the entry)")
check("3c. no stale QT_SERVICES entry" + (f": {stale}" if stale else ""), not stale)

for name in sorted(CANNOT_IMPORT_STANDALONE):
    if name not in mods:
        continue
    qt, _ = qt_modules_after(f"import app.services.{name}", cwd=_GUI)
    check(f"3d. {name} is still the recorded import cycle, not a Qt leak "
          "(drop the entry once the cycle is fixed)", qt is None)

# ---------------------------------------------------------------------------
# 4. repo_root: pin the RESOLVED path, never the number of ".." segments.
# ---------------------------------------------------------------------------
from app.services import paths as _paths        # noqa: E402
from app import utils as _utils                 # noqa: E402

root = _paths.repo_root()
check(f"4a. repo_root() resolves to this repository ({root})",
      os.path.realpath(root) == os.path.realpath(_REPO))
markers = ("CMakeLists.txt", "CLAUDE.md", os.path.join("src", "BoundaryLayer.cpp"),
           os.path.join("tools", "PreProcessor"))
missing = [m for m in markers if not os.path.exists(os.path.join(root, m))]
check("4b. the resolved root is the tree that holds the project's own files"
      + (f" (missing {missing})" if missing else ""), not missing)

# The module that just moved must be UNDER the root it computes — the check that
# actually catches an off-by-one in either direction.
check("4c. app/services/paths.py lives under the root it computes",
      os.path.realpath(os.path.abspath(_paths.__file__)).startswith(
          os.path.realpath(root) + os.sep))

# 4d. One depth count in the module, not two. find_binary_executable used to
# keep its own, five levels from gui/app, resolving to <repo>/../build.
_src = open(_paths.__file__, encoding="utf-8").read()
check(f"4d. paths.py computes a depth exactly once "
      f"({_src.count('os.path.dirname(os.path.abspath(__file__))')} occurrence(s))",
      _src.count("os.path.dirname(os.path.abspath(__file__))") == 1)

hyb = _paths.find_binary_executable("HybMesh2D")
if hyb is None:
    print("SKIP 4e. find_binary_executable: no HybMesh2D built (run ./build.sh)")
else:
    check(f"4e. find_binary_executable returns a path inside the repo ({hyb})",
          os.path.realpath(hyb).startswith(os.path.realpath(root) + os.sep))

# ---------------------------------------------------------------------------
# 5. The re-export must stay a re-export, not a second body.
# ---------------------------------------------------------------------------
MOVED = ("repo_root", "find_binary_executable", "find_solver_executables",
         "find_stl3d_binary", "find_mpi_launcher", "is_mpi_binary")
divergent = [n for n in MOVED
             if getattr(_utils, n, None) is not getattr(_paths, n, object())]
check("5a. app.utils re-exports the moved names as the SAME objects"
      + (f" (diverged: {divergent})" if divergent else ""), not divergent)

_utils_src = open(_utils.__file__, encoding="utf-8").read()
redefined = [n for n in MOVED if f"\ndef {n}(" in _utils_src]
check("5b. app/utils.py defines no body for a moved name"
      + (f" (redefined: {redefined})" if redefined else ""), not redefined)

# is_headless deliberately stayed on the Qt side: it asks which Qt platform
# plugin is running. If it ever moves into paths.py, that module stops being
# Qt-free in anything but name.
check("5c. is_headless stayed with the Qt helpers",
      hasattr(_utils, "is_headless") and not hasattr(_paths, "is_headless"))

# ---------------------------------------------------------------------------
# 6a. A deferred import is still a dependency. Read the AST, at any depth.
# ---------------------------------------------------------------------------
import ast                                       # noqa: E402

offenders = []
scanned = []
for sub in ("app/services", "app/models", "app/workers"):
    base = os.path.join(_GUI, sub)
    for dirpath, _dirs, files in os.walk(base):
        for fn in sorted(f for f in files if f.endswith(".py")):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, _GUI)
            scanned.append(rel)
            try:
                tree = ast.parse(open(full, encoding="utf-8").read())
            except SyntaxError as exc:
                offenders.append(f"{rel}: unparseable ({exc})")
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.module != "app.utils":
                    continue
                # Other names are app.utils' own business; these six are not in it.
                hit = sorted({a.name for a in node.names} & set(MOVED))
                if hit:
                    offenders.append(f"{rel}:{node.lineno} imports {hit}")

# The headless entry scripts too — they are what the shell wrappers run.
for script in ("run_pipeline.py", "run_batch.py"):
    full = os.path.join(_PRE, script)
    if not os.path.exists(full):
        continue
    scanned.append(script)
    for node in ast.walk(ast.parse(open(full, encoding="utf-8").read())):
        if isinstance(node, ast.ImportFrom) and node.module == "app.utils":
            hit = sorted({a.name for a in node.names} & set(MOVED))
            if hit:
                offenders.append(f"{script}:{node.lineno} imports {hit}")

check(f"6a. no Qt-free module reaches a moved name through app.utils, at any "
      f"nesting depth ({len(scanned)} files scanned)"
      + (f": {offenders[:4]}" if offenders else ""), not offenders)

# A shrunken scan passes quietly, so assert it reached the files the three real
# offenders were found in.
for must in ("app/models/mesh_config_io.py", "app/models/solver_config.py",
             "app/workers/solver_run.py", "app/services/pipeline_runner.py"):
    check(f"6a. the scan actually covers {must}", must in scanned)

# ---------------------------------------------------------------------------
# 6b. Behavioural: with PyQt6 refused outright, the config writers still run.
#     This is the path that died in stage 2 with checks 1-3 already green.
# ---------------------------------------------------------------------------
_BLOCK_QT = """
import sys
class _NoQt:
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] == 'PyQt6':
            raise ImportError("No module named 'PyQt6' (simulated: uninstalled)")
        return None
sys.meta_path.insert(0, _NoQt())
import tempfile, os
from app.models.mesh_config import MeshConfig
from app.models.solver_config import SolverConfig
from app.services import pipeline_runner            # noqa: F401
from app.services.paths import repo_root
d = tempfile.mkdtemp()
MeshConfig().save_to_file(os.path.join(d, 'p.dat'))  # <- the stage-2 failure
SolverConfig().generate_input_in(os.path.join(d, 'input.in'))
assert os.path.isdir(repo_root())
print('OK')
"""
try:
    r = subprocess.run([sys.executable, "-c", _BLOCK_QT], cwd=_GUI,
                       capture_output=True, text=True, timeout=120)
    ok, why = r.returncode == 0 and "OK" in r.stdout, (
        (r.stderr.strip().splitlines() or ["?"])[-1])
except (OSError, subprocess.TimeoutExpired) as exc:
    ok, why = False, f"probe could not run: {exc}"
check("6b. with PyQt6 refused, writing a mesh config + solver input still works"
      + ("" if ok else f" [{why}]"), ok)

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All Qt-free seam checks passed.")
