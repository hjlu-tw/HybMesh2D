#!/usr/bin/env python3
"""Regression tests: opening a project file by PATH, and finding its grid again.

USER-REPORTED (2026-08-13), running
``python3 tools/PreProcessor/gui/main.py config/pipeline/cyl0d5_Rot1d0.hws``:

    [ERROR] Error loading file: could not convert string '{' to float64 at row 0, column 1.
    [ERROR] No mesh generated yet. Generate a mesh (with STAR-CD export) or
            uncheck auto-link and pick .vrt/.cel/.bnd manually.

Two separate defects, one after the other:

1. Every positional argument went to the GEOMETRY loader, which handed the
   workspace to ``np.loadtxt`` — hence a numpy message naming neither the file
   nor the fact that it is a workspace. Files are now classified by CONTENT
   (``PipelineConfig.classify_file``), so a workspace opens as a workspace, a
   pipeline script as a script, and a renamed one still opens as what it is.
   The classifier is shared by the CLI, the geometry loader and the Pipeline
   menu, so they cannot disagree about what a file is.

2. Nothing had loaded, so the solver had no mesh — but the same error appears
   even on a workspace that loaded perfectly: Generate Mesh writes its output
   into the GUI's temp dir on purpose and that directory is removed on exit, so
   ``global_vtk_path`` is always empty in a REOPENED workspace. Auto-link then
   claimed "No mesh generated yet" while the grid the workspace was explicitly
   wired to sat on disk. ``_resolve_mesh_grid`` now tries this session's mesh,
   then the case's own paths, then the exported per-case mesh — and
   ``_locate_mesh_bnd`` asks the same resolver, so the BC table cannot describe
   one grid while the run reads another.

Run:  python3 tools/PreProcessor/tests/test_open_project_by_path.py
"""
import json
import os
import sys
import tempfile
import threading

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
    print("FAIL watchdog: blocked >120s (modal dialog?)", flush=True)
    os._exit(99)


_wd = threading.Timer(120, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtWidgets import QApplication              # noqa: E402
_app = QApplication.instance() or QApplication([])

import main as gui_main                               # noqa: E402
from app.controller import AppController              # noqa: E402
from app.models.pipeline_config import PipelineConfig  # noqa: E402

_TMP = tempfile.TemporaryDirectory()
TD = _TMP.name


def _write(name, text):
    p = os.path.join(TD, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


# ── 1. classification is by content, not extension ────────────────────────
ws_file = _write("case.hws", json.dumps(
    {"format_version": 2, "active_idx": 0, "sessions": [], "project": {}}))
pipe_file = _write("run.json", json.dumps(
    {"pipeline_version": 2, "name": "x", "cads": [{"input_file": "a.dat"}]}))
cad_file = _write("cad.json", json.dumps(
    {"input_file": "a.dat", "segments": [{"id": 0}]}))
dat_file = _write("pts.dat", "0.0 0.0\n1.0 0.0\n1.0 1.0\n")
# The regression in miniature: a workspace whose name says .dat.
disguised = _write("looks_like_geometry.dat", json.dumps(
    {"format_version": 2, "sessions": [], "project": {}}))

check(PipelineConfig.classify_file(ws_file) == "workspace",
      "1. a .hws is classified as a workspace")
check(PipelineConfig.classify_file(pipe_file) == "pipeline",
      "1. a pipeline script is classified as a pipeline")
check(PipelineConfig.classify_file(cad_file) == "",
      "1. a PreProcessor CAD config is neither (it keeps its own loader)")
check(PipelineConfig.classify_file(dat_file) == "",
      "1. a .dat geometry is neither")
check(PipelineConfig.classify_file(disguised) == "workspace",
      "1. a workspace named .dat is still a workspace (content, not extension)")
check(PipelineConfig.classify_file(os.path.join(TD, "nope.hws")) == "",
      "1. a missing file classifies as nothing rather than raising")
check(PipelineConfig.classify_file(_write("empty.json", "")) == "",
      "1. an empty file classifies as nothing")
check(PipelineConfig.classify_file(_write("half.json", '{"sessions": [')) == "",
      "1. truncated JSON classifies as nothing rather than raising")
check(PipelineConfig.is_workspace_file(ws_file)
      and not PipelineConfig.is_workspace_file(pipe_file),
      "1. is_workspace_file still answers for the headless CLI")

# ── 2. the CLI splits project files from geometry ──────────────────────────
proj, geoms = gui_main.split_project_files([dat_file, ws_file])
check(proj == ws_file and geoms == [dat_file],
      "2. a workspace argument is separated from the geometry arguments")
# Loading either project kind closes every tab, so a second one would silently
# cancel the first — refused with a warning instead.
proj2, geoms2 = gui_main.split_project_files([ws_file, pipe_file])
check(proj2 == ws_file and geoms2 == [],
      "2. only the first of two project files is used")
check(gui_main.split_project_files([dat_file]) == ("", [dat_file]),
      "2. plain geometry arguments are unaffected")

# ── 3. the reported command: a .hws handed to the geometry loader ──────────
GEOM = os.path.join(_REPO, "examples", "geometries", "naca0012.dat")
ctl = AppController()
logs = []
ctl.main_window.log_panel.log = lambda m: logs.append(str(m))

# A workspace with real content: one session + a mesh/solver project section.
ctl.load_geometry_from_path(GEOM)
ctl.global_mesh_config.bl_layers = 11
# Through the panel: saving re-syncs panel -> model first (the model is the
# truth, but the panel is what the user edited), so a model-only poke is undone.
ctl.push_panel_config(ctl.main_window.mesh_config_panel, ctl.global_mesh_config)
real_ws = os.path.join(TD, "real.hws")
ctl._write_workspace_file(real_ws)

ctl.reset_all_state()
logs.clear()
ctl.load_geometry_from_path(real_ws)     # exactly what main.py used to do
check(not any("float64" in m for m in logs),
      "3. opening a workspace by path no longer fails in the coordinate reader")
check(any("workspace" in m.lower() for m in logs),
      "3. ...and the log says it was recognised as a workspace")
check(len(ctl.sessions) == 1
      and os.path.basename(ctl.sessions[0].file_path) == "naca0012.dat",
      f"3. the workspace's session was restored ({[s.file_path for s in ctl.sessions]})")
check(int(ctl.global_mesh_config.bl_layers) == 11,
      "3. ...and its mesh configuration came with it")

# A pipeline script by path must load as a script, not as a CAD config missing
# its input_file (which is all the .json branch could have made of it).
script = os.path.join(TD, "demo.json")
PipelineConfig(name="demo",
               cads=[{"input_file": GEOM, "segments": [{"id": 0}]}],
               mesh={"bl_layers": 5}).save_to_file(script)
logs.clear()
ctl.load_geometry_from_path(script)
check(not any("lacks 'input_file'" in m for m in logs),
      "3. a pipeline script by path is not mistaken for a CAD config")
check(int(ctl.global_mesh_config.bl_layers) == 5,
      "3. ...the script's mesh section was applied")

# ── 4. Pipeline ▸ Load on a workspace keeps the full state ────────────────
# from_workspace_dict() drops working state by design (it exists to make a .hws
# RUNNABLE headlessly). In the GUI the real loader is available, so opening a
# workspace here must not silently downgrade it.
logs.clear()
ctl.open_pipeline_path(real_ws)
check(len(ctl.sessions) == 1 and ctl.sessions[0].original_points is not None,
      "4. open_pipeline_path routes a workspace to the workspace loader")
check(any("workspace" in m.lower() for m in logs),
      "4. ...and says so rather than loading it silently as a script")

# ── 5. a reopened workspace can still find its grid ────────────────────────
# Fake an exported STAR-CD trio and wire the case to it, as a workspace saved
# after a "Send to Solver" would.
grid_dir = os.path.join(TD, "grid")
os.makedirs(grid_dir, exist_ok=True)
base = os.path.join(grid_dir, "mesh_case")
for ext in (".vrt", ".cel", ".bnd"):
    _write(os.path.join("grid", "mesh_case" + ext), "1\n")
cfg = ctl.global_solver_config
cfg.input_vrt_file, cfg.input_cel_file, cfg.input_bnd_file = (
    base + ".vrt", base + ".cel", base + ".bnd")
ctl.global_vtk_path = ""                 # what a reopened workspace always has
logs.clear()
ok = ctl._auto_link_mesh_output(cfg)
check(ok, "5. auto-link succeeds on the grid the case is already wired to")
check(not any("No mesh generated yet" in m for m in logs),
      "5. ...instead of reporting 'No mesh generated yet'")
check(cfg.input_bnd_file == base + ".bnd",
      "5. ...and the wired paths are left pointing where they did")
check(any("already wired to" in m for m in logs),
      f"5. ...naming which grid it linked and why ({logs})")

# The BC table must resolve the SAME .bnd the run just linked.
ctl.main_window.solver_config_panel.auto_link_mesh.setChecked(True)
check(ctl._locate_mesh_bnd() == base + ".bnd",
      "5. _locate_mesh_bnd agrees with the run's resolver")

# A mesh generated in THIS session still wins over the wired one.
live = os.path.join(TD, "live")
os.makedirs(live, exist_ok=True)
for ext in (".vtk", ".vrt", ".cel", ".bnd"):
    _write(os.path.join("live", "global_mesh" + ext), "1\n")
ctl.global_vtk_path = os.path.join(live, "global_mesh.vtk")
logs.clear()
ctl._auto_link_mesh_output(cfg)
check(cfg.input_bnd_file == os.path.join(live, "global_mesh.bnd"),
      "5. this session's freshly generated mesh takes precedence")

# Nothing anywhere: the message must still tell the user what to do, and name
# what was looked for rather than only the first candidate.
ctl.global_vtk_path = ""
cfg.input_vrt_file = cfg.input_cel_file = cfg.input_bnd_file = ""
ctl.global_mesh_config.output_filename = os.path.join(TD, "absent", "m.vtk")
logs.clear()
check(not ctl._auto_link_mesh_output(cfg),
      "5. no grid anywhere still fails the run")
check(any("Tried:" in m and "absent" in m for m in logs),
      f"5. ...naming the paths it looked for ({logs})")

# ── 6. no "this closes all tabs" modal over an empty canvas ───────────────
# The GUI opens with one pristine blank session, so the guard question fired for
# `main.py case.hws` too — a modal before the user has done anything. `confirm`
# is patched to REFUSE, so a load that still succeeds proves it was not asked.
import app.utils as _utils                             # noqa: E402
_asked = []
_real_confirm = _utils.confirm
_utils.confirm = lambda *a, **k: (_asked.append(a[1] if len(a) > 1 else ""), False)[1]
try:
    fresh = AppController()
    check(not fresh.has_unsaved_work(),
          "6. a freshly started GUI has nothing to lose")
    fresh.load_geometry_from_path(real_ws)
    check(not _asked and len(fresh.sessions) == 1,
          f"6. ...so opening a workspace at startup is not questioned ({_asked})")

    fresh.load_geometry_from_path(GEOM)
    check(fresh.has_unsaved_work(),
          "6. an open geometry IS something to lose")
    _asked.clear()
    fresh.load_geometry_from_path(real_ws)
    check(bool(_asked), "6. ...so that load is questioned, and refusing it stops")
finally:
    _utils.confirm = _real_confirm

_wd.cancel()
_TMP.cleanup()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
