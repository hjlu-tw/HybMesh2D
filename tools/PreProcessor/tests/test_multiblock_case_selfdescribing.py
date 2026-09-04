#!/usr/bin/env python3
"""A multi-block case describes itself, and runs with no GUI in the room (#56).

This repo already holds the rule that **a case describes its own geometry**: the
CAD it was cut from, the resampled ``.dat`` the mesher actually read and the
mesh parameter file are all copied into ``grid/cad/`` and indexed in
``SOURCES.txt`` (``services/case_sources``, ``.claude/rules/pipeline-case.md``).
In ``MESH_MODE 1`` that rule had a hole in exactly the place it exists to cover:
**the topology document decides the mesh as much as the geometry does** — and two
of this repo's five shipped topology cases (``config/multiblock_square.dat``,
``multiblock_hgrid.dat``) declare every corner themselves and name no ``GEOM_FILE``
at all, so the topology is the *only* input there is — and nothing staged it. A
case meshed this way was a folder full of evidence with the one file that shaped
the grid missing from it.

Two things were measured on the tree before any of this was written, and both
turned out to be already true, so they are pinned here rather than rebuilt:

  * ``mesh_mode`` / ``mesh_topology_file`` are ordinary ``_KEY_MAP`` fields, so
    ``to_dict``/``load_from_dict`` already carried them through a workspace and a
    pipeline script. The round-trip checks below are a GATE on that, not a fix —
    the failure they exist to catch is the next person adding a mode field
    outside the key map, where a save would drop it silently.
  * A multi-block case with GEOMETRY already ran headless (measured with
    ``examples/topology/cgrid_naca0012.json``, 11520 cells, 0 inverted).

What did NOT work, and is fixed with this file:

  * **A topology-only case could not run headless at all.**
    ``pipeline_runner._run_mesh`` refused with "mesh stage has no geometry input
    (geom_files empty)" — a precondition of the HYBRID path, applied to both.
    ``config/multiblock_square.dat`` and ``multiblock_hgrid.dat`` are precisely
    that case and mesh fine from ``run.sh``, so the CLI could do what the
    pipeline could not.
  * **Neither host staged the topology file**, so criteria 1, 2 and 7 of #56 had
    nothing to be true about.

BLIND SPOTS, named rather than papered over:

  * The staged ``Background_para_<case>.dat`` still names the topology at its
    ORIGINAL path, not the staged copy — exactly as it already does for
    ``GEOM_FILE``. Re-pointing one and not the other would be worse than
    re-pointing neither; the case is self-describing (you can see which topology
    it used), not self-contained (you cannot re-run it from the folder alone).
  * The export planner ships the topology because ``_SOURCE_KEEP`` already allows
    ``.json`` — which is the browse filter's own default and every shipped
    topology's extension. A topology named ``topo.mbt`` would be NAMED as a skip
    rather than shipped. That is the allow-list working (visible, never silent),
    and widening it to "whatever is in the folder" is the assumption the
    allow-list exists to deny.
  * Nothing here runs the SOLVER on a multi-block case. That is
    ``test_multiblock_cgrid_surface.py``'s dated acceptance run.

Run:  python3 tools/PreProcessor/tests/test_multiblock_case_selfdescribing.py
Skips the two binary-dependent groups cleanly if ./build/HybMesh2D is absent.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
for _p in (_GUI, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >300s", flush=True)
    os._exit(99)


_wd = threading.Timer(300, _watchdog)
_wd.daemon = True
_wd.start()

from app.models.mesh_config import MeshConfig            # noqa: E402
from app.models.pipeline_config import PipelineConfig    # noqa: E402
from app.services import case_export, case_sources       # noqa: E402
from app.services.mesh_modes import (                    # noqa: E402
    MESH_MODE_HYBRID, MESH_MODE_MULTIBLOCK, missing_mesh_input, topology_file,
)
import test_multiblock_surface as mb                     # noqa: E402

tmp = tempfile.mkdtemp(prefix="hybmesh_mb56_")


def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def mbcfg(topology, mode=MESH_MODE_MULTIBLOCK):
    c = MeshConfig()
    c.mesh_mode = mode
    c.mesh_topology_file = topology
    return c


# ── A. the topology file is an INPUT of the run, and only when it is one ──
os.makedirs(os.path.join(tmp, "topo"), exist_ok=True)
topo = mb.write_topology(os.path.join(tmp, "topo", "square_block.json"))

check(case_sources.mesh_input_paths(mbcfg(topo)) == [topo],
      "1. a multi-block config's topology file is one of the mesh stage's input "
      "files — the thing that decides the grid, listed beside the geometry")

check(case_sources.mesh_input_paths(mbcfg(topo, MESH_MODE_HYBRID)) == [],
      "1. the SAME path in a HYBRID config is not an input: the mesher warns "
      "about a key the active mode never reads, and staging a file it never "
      "read would be that same lie told the other way round")

check(case_sources.mesh_input_paths(mbcfg("")) == []
      and case_sources.mesh_input_paths(mbcfg("   ")) == []
      and case_sources.mesh_input_paths(None) == [],
      "1. no topology declared (or no config at all) contributes nothing, "
      "rather than a blank path the staging service has to recognise")

_rel = case_sources.mesh_input_paths(
    mbcfg("examples/topology/square_block.json"), base_dir=_REPO)
check(_rel == [os.path.join(_REPO, "examples", "topology", "square_block.json")],
      "1. a relative topology resolves against the RUN's base directory, not "
      "the interpreter's cwd — a pipeline script quotes repo-relative paths and "
      "run_batch is launched from wherever the user happens to be")

check(case_sources.mesh_input_paths(mbcfg(os.path.join(tmp, "nope.json"))) ==
      [os.path.join(tmp, "nope.json")],
      "1. a declared-but-absent topology is still RETURNED: existence is "
      "stage_case_sources' single decision, exactly as for mesh_provenance_paths")

# ── B. staged, indexed, and renamed on a collision ────────────────────────
grid_dir = os.path.join(tmp, "case", "grid")
os.makedirs(grid_dir, exist_ok=True)
geom = w(os.path.join(tmp, "geom", "body.dat"), "0 0\n1 0\n")
# A geometry beside the topology whose basename collides with it: the topology
# must not overwrite it, nor be overwritten by it.
clash = w(os.path.join(tmp, "geom", "square_block.json"), '{"not": "a topology"}')

logged = []
staged = case_sources.stage_case_sources(
    [geom, clash] + case_sources.mesh_input_paths(mbcfg(topo)),
    grid_dir, log=logged.append)
cad_dir = os.path.join(grid_dir, case_sources.SOURCE_DIR_NAME)
names = sorted(os.listdir(cad_dir))

check("square_block.json" in names and "square_block_2.json" in names,
      f"2. the topology is staged into grid/cad/ alongside the CAD, and a "
      f"basename collision is RENAMED rather than overwritten ({names})")

_bodies = {open(os.path.join(cad_dir, n)).read()
           for n in ("square_block.json", "square_block_2.json")}
check(len(_bodies) == 2 and open(topo).read() in _bodies,
      "2. ...and the two really are the two different files — the topology's "
      "own bytes survive the rename, which is the whole point of not "
      "overwriting")

idx = open(os.path.join(cad_dir, case_sources.SOURCES_INDEX)).read()
_staged_as = next((os.path.basename(d) for s, d in staged if s == topo), "")
check(topo in idx,
      "3. SOURCES.txt names the topology with its ORIGINAL absolute origin, so "
      "the file that shaped this grid can be traced back to the one on disk")
check(_staged_as and any(line.startswith(_staged_as) and topo in line
                         for line in idx.splitlines()),
      f"3. ...on the line for the name it was actually staged under "
      f"({_staged_as!r}), which a rename is what makes non-obvious")

# ── C. the export planner treats it as an input, not as a lump ────────────
w(os.path.join(tmp, "case", "work", "input.in"), "'case'\n")
for _e in (".vrt", ".cel", ".bnd"):
    w(os.path.join(grid_dir, "input" + _e), "grid")
plan = case_export.plan_export(os.path.join(tmp, "case"))
_rel_topo = f"grid/{case_sources.SOURCE_DIR_NAME}/{_staged_as}"
check(plan.has(_rel_topo),
      f"4. the portable export SHIPS the staged topology ({_rel_topo}) — a "
      f"package without it cannot be re-meshed on the other machine")
check(not any(r == _rel_topo for r, *_ in plan.skipped_other),
      "4. ...and does not report it as an unrecognised file, which is what an "
      "input that no allow-list knows about looks like from the manifest")

# ── D. the mesh stage's precondition is per-MODE ──────────────────────────
_hyb = MeshConfig()
check(missing_mesh_input(_hyb),
      "5. the hybrid path with no geometry still refuses: geom_files empty "
      "means there is nothing to grow a boundary layer from")
check(not missing_mesh_input(mbcfg(topo)),
      "5. a multi-block config with a topology and NO geometry is runnable — "
      "square_block and hgrid_blocks declare their own corners, and the CLI has "
      "always meshed them")
_no_topo = mbcfg("")
check("MESH_TOPOLOGY_FILE" in (missing_mesh_input(_no_topo) or ""),
      "5. ...and a multi-block config with NO topology refuses by naming the "
      "key that is missing, rather than by the hybrid path's geometry message")
_both = mbcfg(topo)
_both.geom_files = [geom]
check(not missing_mesh_input(_both),
      "5. geometry in multi-block mode is allowed, not required — the O-grid "
      "and C-grid cases bind their edges to a real body")

check(topology_file(mbcfg(topo)) == topo
      and topology_file(mbcfg(topo, MESH_MODE_HYBRID)) == ""
      and topology_file(None) == "",
      "5. one owner answers 'did the run read a topology' — the precondition and "
      "the staging list both call it, so they cannot come to different answers "
      "about the same config")

# ── E. both hosts stage it, from one rule ─────────────────────────────────
from app.services import pipeline_runner                 # noqa: E402

pc = PipelineConfig(name="mb56", cads=[],
                    mesh=mbcfg(topo).to_dict(), solver={"skip": True})
_src, _gen = pipeline_runner._case_sources(pc, _REPO, [], "")
check(topo in _src,
      "6. the headless host stages the topology (pipeline_runner._case_sources)")
check(any(n.startswith("Background_para_") for n, _t in _gen),
      "6. ...without disturbing the generated mesh parameter file beside it")

# The two halves JOINED, not each proved alone: checks 2-3 drive the staging
# service with a hand-built list and check 6 only asks what the host collected.
# A host that returns the right paths into a service nobody hands them to is two
# green checks and no staged topology, which is what a real run showed.
_pipe_grid = os.path.join(tmp, "hostcase", "grid")
os.makedirs(_pipe_grid, exist_ok=True)
case_sources.stage_case_sources(_src, _pipe_grid, generated=_gen)
_pipe_cad = os.path.join(_pipe_grid, case_sources.SOURCE_DIR_NAME)
_pipe_idx = open(os.path.join(_pipe_cad, case_sources.SOURCES_INDEX)).read()
check(os.path.basename(topo) in os.listdir(_pipe_cad) and topo in _pipe_idx,
      f"6. ...and feeding that host's own list to the staging service really "
      f"lands the topology in grid/cad/ with its absolute origin in "
      f"{case_sources.SOURCES_INDEX} ({sorted(os.listdir(_pipe_cad))})")

# ── F. the mode and the topology round-trip ───────────────────────────────
_text = mbcfg(topo).to_dict()
_back = MeshConfig()
_back.load_from_dict(json.loads(json.dumps(_text)))
check(_back.mesh_mode == MESH_MODE_MULTIBLOCK and _back.mesh_topology_file == topo,
      "7. mode and topology survive a JSON round-trip through MeshConfig — the "
      "one carrier both the .hws 'mesh_config' block and a pipeline script's "
      "'mesh' block are built from")

from app.models.mesh_config_io import config_to_text     # noqa: E402
_dat = config_to_text(_back)
check(f"MESH_MODE {MESH_MODE_MULTIBLOCK}" in _dat
      and f"MESH_TOPOLOGY_FILE {topo}" in _dat,
      "7. ...and reach the .dat the mesher reads, which is what 'the case still "
      "meshes the same way' actually means")

_pipe = PipelineConfig(name="mb56", cads=[], mesh=_text, solver={"skip": True})
_pipe2 = PipelineConfig.from_dict(json.loads(json.dumps(_pipe.to_dict())))
_mc2 = _pipe2.build_mesh_config([])
check(_mc2.mesh_mode == MESH_MODE_MULTIBLOCK and _mc2.mesh_topology_file == topo,
      "8. the mode and the topology round-trip through a pipeline script")

_ws = {"format_version": 2, "sessions": [],
       "project": {"mesh_config": _text}}
_mc3 = PipelineConfig.from_workspace_dict(_ws, name="mb56").build_mesh_config([])
check(_mc3.mesh_mode == MESH_MODE_MULTIBLOCK and _mc3.mesh_topology_file == topo,
      "8. ...and out of a saved workspace read AS a pipeline script, which is "
      "how run_pipeline.sh accepts a .hws")

# ── G. through the real GUI: save the workspace, reopen it ────────────────
from PyQt6.QtWidgets import QApplication                 # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController                 # noqa: E402

ctl = AppController()
ctl.global_mesh_config.mesh_mode = MESH_MODE_MULTIBLOCK
ctl.global_mesh_config.mesh_topology_file = topo
ctl.push_panel_config(ctl.main_window.mesh_config_panel, ctl.global_mesh_config)

hws = os.path.join(tmp, "ws", "mb56.hws")
ctl._write_workspace_file(hws)
saved = json.load(open(hws))
check(saved.get("project", {}).get("mesh_config", {}).get("mesh_topology_file")
      == topo,
      "9. the topology reaches the .hws on disk — the panel is authoritative, "
      "so a field the panel cannot round-trip is silently blank here")

ctl2 = AppController()
check(ctl2.open_workspace_path(hws),
      "9. (precondition) the saved workspace reopens")
check(ctl2.global_mesh_config.mesh_mode == MESH_MODE_MULTIBLOCK
      and ctl2.global_mesh_config.mesh_topology_file == topo,
      "9. ...and the reopened case still meshes the same way: mode and "
      "topology are both back")

ctl2.sync_panels_to_models()
check(ctl2.global_mesh_config.mesh_topology_file == topo,
      "9. ...and survive the panel->model sync that runs on every edit — a "
      "field the panel does not own reads back blank on the first keystroke")

# The pre-flight message the USER is shown, not just the service behind it: the
# first cut of #56 wrote `if not geom_files and missing_mesh_input(cfg)` and so
# told a multi-block config with no topology that it had no geometry.
from app.controllers.mesh_gen_ctrl import mesh_input_warning   # noqa: E402

_no_topo_msg = mesh_input_warning(mbcfg(""))
check("MESH_TOPOLOGY_FILE" in _no_topo_msg
      and "CAD mode" not in _no_topo_msg and "boundary/BL" not in _no_topo_msg,
      f"9b. a multi-block config with no topology is told about "
      f"MESH_TOPOLOGY_FILE, and is NOT sent to the CAD tab to draw a geometry "
      f"the multi-block path would not read anyway ({_no_topo_msg!r})")
check("CAD mode" in mesh_input_warning(MeshConfig()),
      "9b. ...while the hybrid path with no geometry still gets the guidance it "
      "always had — the message is keyed on the MODE, not on the reason's text")
check(mesh_input_warning(mbcfg(topo)) == "",
      "9b. ...and a runnable topology-only config is warned about NOTHING, "
      "which is the whole reason square_block stopped being a defect")

_gui_src = ctl2._case_source_files()
check(topo in _gui_src,
      "10. the GUI host stages the topology too (solver_ctrl._case_source_files) "
      "— one rule, two callers, which is the shape the staging rule is written in")

ctl2.global_mesh_config.mesh_mode = MESH_MODE_HYBRID
check(topo not in ctl2._case_source_files(),
      "10. ...keyed on the LIVE config's mode, so a hybrid session never stages "
      "a topology it did not read — and, the same fact read the other way, a "
      "grid MESHED in mode 1 and sent to the solver after the panel was flipped "
      "back stages no topology either (blind spot, named in the rule file: this "
      "list describes the config as it stands, exactly as it already does for "
      "the session's geometry and the output name)")

# ── H. headless and batch, in a process that CANNOT import Qt ─────────────
_NO_QT = """
import sys
class _NoQt:
    def find_spec(self, name, path=None, target=None):
        if name == "PyQt6" or name.startswith("PyQt6."):
            raise ImportError("a headless run must not need a GUI")
        return None
sys.meta_path.insert(0, _NoQt())
sys.path.insert(0, %r)
"""


def _run_headless(body: str, script: str):
    """Run ``body`` in a fresh interpreter where importing PyQt6 raises.

    A subprocess rather than an in-process assertion: this file has already
    built a QApplication by now, so "no GUI present" can only be measured
    somewhere that never could have had one.
    """
    from mesher_bin import mesher_env
    code = (_NO_QT % _GUI) + body
    return subprocess.run([sys.executable, "-c", code, script],
                          cwd=_REPO, env=mesher_env(),
                          capture_output=True, text=True, timeout=240)


if not os.path.exists(_BIN):
    print("SKIP 11-12: ./build/HybMesh2D not built", flush=True)
else:
    out_vtk = os.path.join(tmp, "out", "mb56.vtk")
    script = os.path.join(tmp, "script", "mb56.json")
    mc = mbcfg(topo)
    mc.export_vtk = True
    mc.export_starcd = True
    mc.output_filename = out_vtk
    w(script, json.dumps({
        "pipeline_version": 2, "name": "mb56", "cads": [],
        "mesh": mc.to_dict(), "solver": {"skip": True},
    }, indent=2))

    r = _run_headless(
        "from app.services.pipeline_runner import run_pipeline\n"
        "from app.models.pipeline_config import PipelineConfig\n"
        "import json, sys\n"
        "pc = PipelineConfig.from_dict(json.load(open(sys.argv[1])))\n"
        "run_pipeline(pc, log=lambda m: print(m, flush=True), run_solver=False)\n",
        script)
    check(r.returncode == 0 and os.path.exists(out_vtk),
          "11. a topology-only multi-block case meshes HEADLESS, in a process "
          f"that cannot import PyQt6 (rc={r.returncode}; "
          f"{(r.stdout + r.stderr).strip().splitlines()[-1:] or ['']})")
    check("Multi-block" in (r.stdout + r.stderr),
          "11. ...and it really is the multi-block path that ran, not the "
          "hybrid one quietly meshing an empty domain")

    os.remove(out_vtk) if os.path.exists(out_vtk) else None
    r2 = _run_headless(
        "from app.services import batch_runner\n"
        "import sys\n"
        "log = lambda m: print(m, flush=True)\n"
        "jobs = batch_runner.load_jobs([sys.argv[1]], log=log)\n"
        "summary = batch_runner.run_batch(jobs, log=log, run_solver=False)\n"
        "sys.exit(batch_runner.exit_code(summary))\n",
        script)
    check(r2.returncode == 0 and os.path.exists(out_vtk),
          "12. and so does the same script through the BATCH queue's engine "
          f"(rc={r2.returncode}; "
          f"{(r2.stdout + r2.stderr).strip().splitlines()[-1:] or ['']})")

    # A topology-only case is the half that was BROKEN, so it is the half the two
    # runs above use. The other half — a topology bound to real geometry — is the
    # one this repo actually ships, and "already true" is a claim that decays.
    geo_vtk = os.path.join(tmp, "out", "mb56_geo.vtk")
    geo_script = os.path.join(tmp, "script", "mb56_geo.json")
    gmc = mbcfg(os.path.join(_REPO, "examples", "topology",
                             "cgrid_naca0012.json"))
    gmc.bl_initial_thickness = 0.001
    gmc.bc_geom = "wall"
    gmc.export_vtk = True
    gmc.output_filename = geo_vtk
    w(geo_script, json.dumps({
        "pipeline_version": 2, "name": "mb56_geo",
        "cads": [{"input_file": "examples/geometries/naca0012_cgrid.dat",
                  "skip": True},
                 {"input_file": "examples/geometries/cgrid_farfield.dat",
                  "skip": True}],
        "mesh": gmc.to_dict(), "solver": {"skip": True},
    }, indent=2))
    r3 = _run_headless(
        "from app.services.pipeline_runner import run_pipeline\n"
        "from app.models.pipeline_config import PipelineConfig\n"
        "import json, sys\n"
        "pc = PipelineConfig.from_dict(json.load(open(sys.argv[1])))\n"
        "run_pipeline(pc, log=lambda m: print(m, flush=True), run_solver=False)\n",
        geo_script)
    check(r3.returncode == 0 and os.path.exists(geo_vtk),
          "13. a multi-block case whose edges BIND to a real geometry meshes "
          f"headless too, with the same no-PyQt6 finder in place "
          f"(rc={r3.returncode}; "
          f"{(r3.stdout + r3.stderr).strip().splitlines()[-1:] or ['']})")
    check("Inverted cells       : 0 of" in (r3.stdout + r3.stderr),
          "13. ...and the mesher's own quality report says the blocks filled: "
          "an empty domain would also produce a .vtk")

shutil.rmtree(tmp, ignore_errors=True)
_wd.cancel()
print(f"\n{len(_FAILS)} failure(s)" if _FAILS else "\nall checks passed")
for m in _FAILS:
    print("  FAILED: " + m)
# os._exit: Qt's offscreen teardown segfaults on a machine with no GPU, which
# run_all.sh would report as a failing assertion.
os._exit(1 if _FAILS else 0)
