#!/usr/bin/env python3
"""Regression tests for the 2026-08-06 GUI review batch (findings N3, N5, N1).

One check per defect, so none of them can quietly come back:

N3 — gmsh loader path was never handed to the C++ subprocesses.
     `build/HybMesh2D` links `@rpath/libgmsh` and the baked LC_RPATH points at
     the *build machine's* gmsh directory. The workers passed no `env=` at all,
     and `pipeline_runner._mesh_env()` deliberately inherited `os.environ` on the
     theory that a shell wrapper had exported DYLD_LIBRARY_PATH — which macOS SIP
     strips the moment a protected python3 starts, so it never arrived. Off the
     build machine the GUI's Generate Mesh died in dyld.
       1. env_setup locates libgmsh and mesher_env() puts it on the loader path.
       2. Every subprocess launcher actually passes that env.
       3. No developer-specific absolute path is hardcoded anywhere any more.

N5 — cancel/shutdown could not kill a wedged backend.
     `cancel()` sent SIGTERM only, with no escalation, and the close handler
     called `QThread.wait()` with no timeout on the GUI thread: a mesher stuck
     inside gmsh made the app unclosable except by `kill -9`. Helper processes
     spawned by the child also survived, since only the direct child was signalled.
       4. popen_kwargs puts the child in its own process group.
       5. stop_process kills a SIGTERM-ignoring process AND its grandchildren.
       6. stop_process_async returns immediately (never blocks the GUI thread).
       7. Every worker cancel() path routes through the escalating helper.
       8. handle_close_event uses bounded waits, not an unbounded wait().

N1 — Save Workspace silently dropped the Mesh / Solver / IB configuration.
     Only `session.mesh_config` (a near-vestigial object holding geom_files) was
     written; the panels edit `global_mesh_config`, which is replaced only when a
     stage runs, and the solver / immersed-solid configs were not serialized at
     all. Autosave keyed off geometry changes alone, so a session spent tuning
     the mesh was never checkpointed either.
       9. A workspace round-trip preserves mesh, solver and IB settings.
      10. A pre-v2 workspace still loads (migration adds an empty project section).
      11. project_is_dirty() tracks panel edits and clears on save.
      12. Autosave fires for a config-only change (no geometry edit).
      13. Editing the mesh config makes the close prompt report unsaved changes.

Run:  python3 tools/PreProcessor/tests/test_gui_review_batch_2026_08_06.py
(the script forces the offscreen platform itself, so the env var is optional).
"""
import inspect
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >90s (modal dialog / unbounded wait?)", flush=True)
    os._exit(99)


_wd = threading.Timer(90, _watchdog)
_wd.daemon = True
_wd.start()

# ═══════════════════════════════════════════════════════════════════════════
# N3 — gmsh loader path injection
# ═══════════════════════════════════════════════════════════════════════════
from app.services.env_setup import (  # noqa: E402
    LIB_PATH_VAR, gmsh_lib_dir, mesher_env,
)

_lib = gmsh_lib_dir()
if _lib is None:
    # No gmsh wheel installed (bare CI): the *mechanism* is still testable.
    print("SKIP gmsh not installed — checking mesher_env passthrough only", flush=True)
    check(mesher_env({"FOO": "bar"}) == {"FOO": "bar"},
          "1. mesher_env leaves the env untouched when libgmsh is absent")
else:
    check(os.path.isdir(_lib) and any(f.startswith("libgmsh") for f in os.listdir(_lib)),
          f"1a. gmsh_lib_dir() points at a directory holding libgmsh ({_lib})")
    env = mesher_env({})
    check(env.get(LIB_PATH_VAR, "").split(os.pathsep)[0] == _lib,
          f"1b. mesher_env prepends it to {LIB_PATH_VAR}")
    # An existing value must be preserved, and the dir must not be duplicated.
    env2 = mesher_env({LIB_PATH_VAR: "/pre/existing"})
    check(env2[LIB_PATH_VAR] == f"{_lib}{os.pathsep}/pre/existing",
          "1c. an existing loader path is preserved, not overwritten")
    check(mesher_env({LIB_PATH_VAR: _lib})[LIB_PATH_VAR] == _lib,
          "1d. an already-present directory is not duplicated")

# 2. Every launcher of the C++ mesh binaries passes an env (regression: they
#    passed none, so the loader path could never reach the child).
import app.workers.mesh_gen_run as mesh_gen_run  # noqa: E402
import app.workers.backend_run as backend_run  # noqa: E402
import app.services.pipeline_runner as pipeline_runner  # noqa: E402

for mod, label in ((mesh_gen_run, "MeshGenWorker"), (backend_run, "BackendWorker")):
    src = inspect.getsource(mod)
    check("env=mesher_env()" in src,
          f"2. {label} passes env=mesher_env() to Popen")

check("return mesher_env()" in inspect.getsource(pipeline_runner._mesh_env),
      "2. pipeline_runner._mesh_env() resolves the path instead of inheriting it")
# The resample stage used to launch with no env at all.
check(inspect.getsource(pipeline_runner._run_resample).count("_mesh_env()") == 1,
      "2. the headless resample stage also launches with the mesher env")

# 3. No developer-specific path may be baked into the shell entry points or the
#    Python probe (the old fallback hardcoded one engineer's home directory).
_HOME_RE = re.compile(r"/Users/[A-Za-z0-9_.-]+/Library")
_bad_paths = []
for rel in ("run.sh", "run_pipeline.sh", "tools/scripts/gmsh_lib_dir.sh",
            "tools/PreProcessor/gui/app/services/env_setup.py"):
    p = os.path.join(_REPO, rel)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            if _HOME_RE.search(f.read()):
                _bad_paths.append(rel)
check(not _bad_paths,
      "3. no hardcoded developer home path in the gmsh discovery"
      + (f" (found in: {_bad_paths})" if _bad_paths else ""))

# ═══════════════════════════════════════════════════════════════════════════
# N5 — escalating termination
# ═══════════════════════════════════════════════════════════════════════════
from app.workers.proc_util import (  # noqa: E402
    popen_kwargs, stop_process, stop_process_async,
)

check(popen_kwargs().get("start_new_session") is True,
      "4. popen_kwargs puts the child in its own process group")
check(popen_kwargs(cwd="/tmp")["cwd"] == "/tmp",
      "4. popen_kwargs lets a caller override/extend the defaults")

# A child that IGNORES SIGTERM and forks a grandchild — the exact shape a plain
# proc.terminate() cannot kill.
_STUBBORN = (
    "import os, signal, sys, time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "if os.fork() == 0:\n"
    "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "    print('g', os.getpid(), flush=True); time.sleep(120); sys.exit()\n"
    "print('c', os.getpid(), flush=True)\n"
    "time.sleep(120)\n"
)


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _spawn_stubborn():
    p = subprocess.Popen([sys.executable, "-c", _STUBBORN], **popen_kwargs())
    pids = [int(p.stdout.readline().split()[1]) for _ in range(2)]
    return p, pids


if hasattr(os, "fork"):
    # 5. Escalation reaps the whole tree, not just the direct child.
    proc, pids = _spawn_stubborn()
    reaped = stop_process(proc, grace=1.0)
    time.sleep(0.5)
    check(reaped and not any(_alive(x) for x in pids),
          "5. stop_process kills a SIGTERM-ignoring child AND its grandchild")

    # Prove the old behaviour really was insufficient (guards against someone
    # "simplifying" the helper back to a bare terminate()).
    proc, pids = _spawn_stubborn()
    proc.send_signal(signal.SIGTERM)
    time.sleep(0.8)
    check(proc.poll() is None and all(_alive(x) for x in pids),
          "5. (control) a bare SIGTERM leaves that same tree running")
    stop_process(proc, grace=1.0)

    # 6. The GUI-thread path must not block for the grace period.
    proc, pids = _spawn_stubborn()
    t0 = time.time()
    stop_process_async(proc, grace=1.0)
    elapsed = time.time() - t0
    check(elapsed < 0.5,
          f"6. stop_process_async returns immediately ({elapsed * 1000:.0f} ms)")
    deadline = time.time() + 6.0
    while proc.poll() is None and time.time() < deadline:
        time.sleep(0.1)
    time.sleep(0.4)
    check(proc.poll() is not None and not any(_alive(x) for x in pids),
          "6. ...and the off-thread escalation still kills the tree")
else:
    print("SKIP no os.fork on this platform — process-tree checks skipped", flush=True)

# 7. No worker may go back to a bare terminate() in its cancel path.
import app.workers.solver_run as solver_run  # noqa: E402
import app.workers.stl3d_run as stl3d_run  # noqa: E402

for mod, label in ((mesh_gen_run, "MeshGenWorker"), (backend_run, "BackendWorker"),
                   (solver_run, "SolverWorker"), (stl3d_run, "Stl3dWorker")):
    src = inspect.getsource(mod)
    check("_process.terminate()" not in src and "stop_process_async" in src,
          f"7. {label} cancels through the escalating helper, not terminate()")

# 8. The close handler must never wait() unbounded on the GUI thread.
import app.controllers.lifecycle_ctrl as lifecycle_ctrl  # noqa: E402

_lc_src = inspect.getsource(lifecycle_ctrl)
# Strip comments first: the module *documents* why an unbounded ``wait()`` is
# wrong, and that prose must not read as the defect itself.
_lc_code = "\n".join(ln.split("#", 1)[0] for ln in _lc_src.splitlines())
check(not re.search(r"\.wait\(\s*\)", _lc_code),
      "8. handle_close_event has no unbounded QThread.wait()")
check(re.search(r"\.wait\(_JOIN_MS\)", _lc_src) is not None,
      "8. ...it joins each worker within a bounded budget instead")

# ═══════════════════════════════════════════════════════════════════════════
# N1 — full project state in the workspace
# ═══════════════════════════════════════════════════════════════════════════
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.controller import AppController  # noqa: E402
from app.controllers.session_io_ctrl import WORKSPACE_FORMAT_VERSION  # noqa: E402

check(WORKSPACE_FORMAT_VERSION >= 2,
      f"9. workspace format bumped for the project section (v{WORKSPACE_FORMAT_VERSION})")

c = AppController()

# Configure all three stages with values distinguishable from the defaults.
c.global_mesh_config.bl_layers = 23
c.global_mesh_config.bl_growth_rate = 1.234
c.global_mesh_config.domain_x_min = -17.5
c.main_window.mesh_config_panel.set_config(c.global_mesh_config)

c.global_solver_config.num_half_iter = 4321
c.main_window.solver_config_panel.set_config(c.global_solver_config)

c.global_stl3d_config.case_name = "review_batch_case"
c.main_window.stl3d_config_panel.set_config(c.global_stl3d_config)

ws = os.path.join(c.temp_dir, "roundtrip.hws")
c._write_workspace_file(ws)

with open(ws, encoding="utf-8") as f:
    saved = json.load(f)
proj = saved.get("project", {})
check(bool(proj), "9. the workspace carries a 'project' section")
check(proj.get("mesh_config", {}).get("bl_layers") == 23,
      "9. mesh config is serialized (bl_layers=23)")
check(proj.get("solver_config", {}).get("num_half_iter") == 4321,
      "9. solver config is serialized (num_half_iter=4321)")
check(proj.get("stl3d_config", {}).get("case_name") == "review_batch_case",
      "9. immersed-solid config is serialized (case_name)")

# Reload into a clean controller: every panel must come back configured.
c2 = AppController()
c2._read_workspace_file(ws)
check(c2.global_mesh_config.bl_layers == 23
      and abs(c2.global_mesh_config.bl_growth_rate - 1.234) < 1e-9
      and abs(c2.global_mesh_config.domain_x_min - (-17.5)) < 1e-9,
      "9. mesh config survives the round-trip")
check(c2.global_solver_config.num_half_iter == 4321,
      "9. solver config survives the round-trip")
check(c2.global_stl3d_config.case_name == "review_batch_case",
      "9. immersed-solid config survives the round-trip")
# The panels — not just the models — must show the restored values.
check(c2.main_window.mesh_config_panel.get_config().bl_layers == 23,
      "9. the mesh panel itself shows the restored value")

# 10. A pre-v2 workspace (no project section) must still load.
legacy = dict(saved)
legacy["format_version"] = 1
legacy.pop("project", None)
legacy_path = os.path.join(c.temp_dir, "legacy_v1.hws")
with open(legacy_path, "w", encoding="utf-8") as f:
    json.dump(legacy, f)
migrated = AppController._migrate_workspace(legacy, 1)
check(migrated.get("format_version") == WORKSPACE_FORMAT_VERSION
      and migrated.get("project") == {},
      "10. v1->v2 migration stamps the version and seeds an empty project section")
c3 = AppController()
c3._read_workspace_file(legacy_path)
check(len(c3.sessions) == len(saved.get("sessions", [])),
      "10. a v1 workspace still loads its sessions (no crash, no data loss)")

# 11. Dirty tracking: clean right after a load, dirty after an edit, clean again
#     once saved.
check(not c2.project_is_dirty(),
      "11. a freshly-loaded workspace is not reported as modified")
c2.global_mesh_config.bl_layers = 99
c2.main_window.mesh_config_panel.set_config(c2.global_mesh_config)
check(c2.project_is_dirty(), "11. editing the mesh config marks the project dirty")
c2._write_workspace_file(os.path.join(c2.temp_dir, "saved_again.hws"))
c2._reset_project_baseline()
check(not c2.project_is_dirty(), "11. saving clears the dirty state")

# 12. Autosave must trigger on a config-only change (regression: it keyed off
#     is_geometry_modified alone, so mesh/solver tuning was never checkpointed).
c4 = AppController()
c4._autosave_path = os.path.join(c4.temp_dir, "autosave_probe.hws")
for s in c4.sessions:
    s.is_geometry_modified = False
c4._autosave()
check(not os.path.exists(c4._autosave_path),
      "12. no autosave when nothing has changed")
c4.global_mesh_config.bl_layers = 31
c4.main_window.mesh_config_panel.set_config(c4.global_mesh_config)
c4._autosave()
check(os.path.exists(c4._autosave_path),
      "12. a config-only change DOES get checkpointed")
if os.path.exists(c4._autosave_path):
    with open(c4._autosave_path, encoding="utf-8") as f:
        check(json.load(f)["project"]["mesh_config"]["bl_layers"] == 31,
              "12. ...and the checkpoint contains the edited value")

# 13. The exit prompt must know about a config-only change. handle_close_event
#     would open a modal, so assert on the condition it branches on instead.
c5 = AppController()
for s in c5.sessions:
    s.is_geometry_modified = False
check(not c5.project_is_dirty() and not any(s.is_geometry_modified for s in c5.sessions),
      "13. a pristine app reports nothing unsaved (no spurious exit prompt)")
c5.global_solver_config.num_half_iter = 777
c5.main_window.solver_config_panel.set_config(c5.global_solver_config)
check(c5.project_is_dirty(),
      "13. a solver-only edit is reported as unsaved work at exit")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
