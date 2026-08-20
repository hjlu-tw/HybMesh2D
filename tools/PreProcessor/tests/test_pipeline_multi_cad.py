#!/usr/bin/env python3
"""Regression tests for finding N2 — one complete project description.

The defect: two project-file formats existed and NEITHER could describe a whole
case.

  * The ``.hws`` workspace held multiple CAD sessions but (before the N1 fix) no
    mesh/solver/IB configuration.
  * The pipeline script held mesh/solver/results but only ONE ``cad`` object and
    no immersed-solid section — so ``save_pipeline_file`` silently dropped every
    open session except the active one, and a multi-body case (airfoil + ground
    plane, multi-element wing) could not be re-run from its own script.

Pipeline schema v2 makes ``cads`` a list and adds ``stl3d``; a ``.hws`` workspace
is also accepted directly by the headless runner, so a case configured
interactively can be re-run without re-authoring it.

Checks:
 1. v1 (single ``cad``) and v0 (no version) migrate to a one-entry ``cads``, and
    the ``cad`` property still reads the first entry for old call sites.
 2. A multi-entry script round-trips through save/load with order preserved.
 3. Per-entry helpers (skip / input resolution / default output) are independent,
    and two entries cannot collide on one default output name.
 4. build_mesh_config wires ALL resampled outputs as boundaries, de-duplicated
    and in order; an explicit mesh.geom_files still wins.
 5. The GUI's Save Pipeline captures every open session, not just the active one.
 6. Loading a multi-entry script opens one CAD tab per entry.
 7. The stl3d section round-trips and is applied to the IB panel on load.
 8. A ``.hws`` workspace converts to a runnable PipelineConfig (recognised by
    contents, not extension) carrying every session plus mesh/solver/IB.
 9. The shipped multi-geometry example parses and declares >1 geometry.

Run:  python3 tools/PreProcessor/tests/test_pipeline_multi_cad.py
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
    print("FAIL watchdog: blocked >90s (modal dialog?)", flush=True)
    os._exit(99)


_wd = threading.Timer(90, _watchdog)
_wd.daemon = True
_wd.start()

from app.models.pipeline_config import (  # noqa: E402
    PIPELINE_FORMAT_VERSION, PipelineConfig,
)

check(PIPELINE_FORMAT_VERSION >= 2,
      f"0. pipeline schema bumped for multi-CAD (v{PIPELINE_FORMAT_VERSION})")

# ── 1. migration from the single-cad era ──────────────────────────────────
v1 = {"pipeline_version": 1, "name": "old",
      "cad": {"input_file": "a.dat", "segments": [{"id": 0}]},
      "mesh": {"bl_layers": 7}, "solver": {"case_name": "c"}}
p = PipelineConfig.from_dict(v1)
check([c.get("input_file") for c in p.cads] == ["a.dat"],
      "1. a v1 'cad' object migrates to a one-entry 'cads'")
check(p.cad.get("input_file") == "a.dat",
      "1. the .cad property still reads the first entry (old call sites)")
check(p.mesh == {"bl_layers": 7} and p.solver == {"case_name": "c"},
      "1. the other sections survive migration untouched")
p0 = PipelineConfig.from_dict({"cad": {"input_file": "b.dat"}})
check([c.get("input_file") for c in p0.cads] == ["b.dat"],
      "1. a v0 script (no version field) migrates too")
p2bare = PipelineConfig.from_dict(
    {"pipeline_version": 2, "cad": {"input_file": "c.dat"}})
check([c.get("input_file") for c in p2bare.cads] == ["c.dat"],
      "1. a hand-written v2 script may still use the singular 'cad' key")
# The .cad setter must write through to cads[0], not shadow it.
ps = PipelineConfig(name="s")
ps.cad = {"input_file": "z.dat"}
check([c.get("input_file") for c in ps.cads] == ["z.dat"],
      "1. assigning .cad writes through to cads[0]")

# ── 2. multi-entry round-trip ─────────────────────────────────────────────
# Entries 0/1 carry segments (so they would actually be resampled); entry 2 sets
# skip. An entry WITHOUT segments is skipped by design — there is nothing to
# redistribute — so segments are what make the skip flag distinguishable here.
_SEG = [{"id": 0, "type": "file", "strategy": "uniform", "parameters": {"n": 40}}]
multi = PipelineConfig(
    name="multi",
    cads=[{"input_file": "one.dat", "is_closed": True, "segments": _SEG},
          {"input_file": "two.dat", "is_closed": False, "segments": _SEG},
          {"input_file": "three.dat", "segments": _SEG, "skip": True}],
    mesh={"bl_layers": 3}, solver={"skip": True})
with tempfile.TemporaryDirectory() as td:
    path = os.path.join(td, "multi.json")
    multi.save_to_file(path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    check(len(raw.get("cads", [])) == 3, "2. all three entries are written")
    check("cad" not in raw, "2. the obsolete singular key is not written")
    back = PipelineConfig.load_from_file(path)
    check([c["input_file"] for c in back.cads]
          == ["one.dat", "two.dat", "three.dat"],
          "2. order is preserved through the round-trip")
    check(back.cad_skip(2) and not back.cad_skip(1),
          "2. per-entry skip survives the round-trip")

# ── 3. per-entry helpers are independent ──────────────────────────────────
check(multi.cad_indices() == [0, 1, 2], "3. cad_indices covers every entry")
check(not multi.cads_all_skipped(), "3. cads_all_skipped is False when one runs")
check(PipelineConfig(name="n", cads=[{"input_file": "x.dat", "skip": True}])
      .cads_all_skipped(),
      "3. ...and True when every entry is skipped")
check(PipelineConfig(name="n").cads_all_skipped(),
      "3. ...and True when there is no CAD section at all")
check(PipelineConfig(name="n",
                     cads=[{"input_file": "x.dat"}]).cad_skip(0),
      "3. an entry with no segments is skipped (nothing to redistribute)")
check(PipelineConfig(name="n", cads=[{"segments": _SEG}]).cad_skip(0),
      "3. an entry with no source file is skipped (segments index a source)")
# Default outputs must be distinct per entry, or one resample would overwrite
# another's result and the mesh would silently see the same geometry twice.
outs = [multi.default_cad_output(_REPO, i) for i in multi.cad_indices()]
check(len(set(outs)) == 3,
      f"3. each entry gets its own default output name ({[os.path.basename(o) for o in outs]})")
# Nameless entries fall back to the script name, still suffixed per index.
nameless = PipelineConfig(name="anon", cads=[{}, {}])
n_outs = [nameless.default_cad_output(_REPO, i) for i in (0, 1)]
check(len(set(n_outs)) == 2,
      "3. even two nameless entries do not collide on a default output")

# ── 4. all resampled outputs become mesh boundaries ───────────────────────
mc = multi.build_mesh_config(["/tmp/a.dat", "/tmp/b.dat", "/tmp/a.dat"])
check(mc.geom_files == ["/tmp/a.dat", "/tmp/b.dat"],
      f"4. every output is wired as a boundary, de-duplicated ({mc.geom_files})")
check(mc.bl_layers == 3, "4. the mesh section itself is still applied")
mc1 = multi.build_mesh_config("/tmp/single.dat")
check(mc1.geom_files == ["/tmp/single.dat"],
      "4. a single path (old call style) still works")
explicit = PipelineConfig(name="e", cads=[{"input_file": "i.dat"}],
                          mesh={"geom_files": ["/tmp/explicit.dat"]})
check(explicit.build_mesh_config(["/tmp/from_cad.dat"]).geom_files
      == ["/tmp/explicit.dat"],
      "4. an explicit mesh.geom_files still wins over the CAD outputs")

# ── GUI-side checks ───────────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402

GEOMS = [os.path.join(_REPO, "examples", "geometries", n) for n in
         ("30p30n_jaxa_slat.dat", "30p30n_jaxa_flap.dat")]
have_geoms = all(os.path.exists(g) for g in GEOMS)

ctl = AppController()
if not have_geoms:
    print("SKIP example geometries missing — GUI multi-session checks skipped",
          flush=True)
else:
    for g in GEOMS:
        ctl.load_geometry_from_path(g)
    loaded = [s for s in ctl.sessions if s.original_points is not None]
    check(len(loaded) >= 2,
          f"5. two geometries opened as separate sessions ({len(loaded)})")

    # 5. Save Pipeline must describe EVERY session (the regression: only active).
    pcfg = PipelineConfig.from_configs(
        "case", [s.project_model for s in ctl.sessions],
        ctl.global_mesh_config, ctl.global_solver_config, {})
    named = [os.path.basename(c.get("input_file") or "") for c in pcfg.cads]
    check(len(pcfg.cads) == len(ctl.sessions),
          f"5. from_configs emits one entry per session ({len(pcfg.cads)})")
    check(all(os.path.basename(g) in named for g in GEOMS),
          f"5. ...naming both geometries ({named})")
    # A single model still works (back-compat with the old signature).
    one = PipelineConfig.from_configs(
        "one", ctl.sessions[0].project_model, None, None, {})
    check(len(one.cads) == 1, "5. a single ProjectModel still yields one entry")

    # 6. Loading a multi-entry script opens one tab per entry.
    script = PipelineConfig(
        name="multi_load",
        cads=[{"input_file": GEOMS[0], "is_closed": True, "skip": True},
              {"input_file": GEOMS[1], "is_closed": True, "skip": True}],
        mesh={"bl_layers": 5})
    with tempfile.TemporaryDirectory() as td:
        sp = os.path.join(td, "multi_load.json")
        script.save_to_file(sp)
        ctl2 = AppController()
        ctl2._apply_pipeline_config(PipelineConfig.load_from_file(sp), sp)
        with_pts = [s for s in ctl2.sessions if s.original_points is not None]
        check(len(with_pts) == 2,
              f"6. loading the script opened 2 CAD tabs ({len(with_pts)})")
        check(ctl2.global_mesh_config.bl_layers == 5,
              "6. ...and applied the mesh section")

# ── 7. immersed-solid section ─────────────────────────────────────────────
from app.models.stl3d_config import Stl3dConfig  # noqa: E402

ib = Stl3dConfig()
ib.stl_path = "/tmp/body.stl"
ib.case_name = "ib_case"
with_ib = PipelineConfig.from_configs("ibcase", None, None, None, {},
                                      stl3d_config=ib)
check(with_ib.stl3d.get("case_name") == "ib_case",
      "7. an IB config is emitted into the stl3d section")
no_ib = PipelineConfig.from_configs("plain", None, None, None, {},
                                    stl3d_config=Stl3dConfig())
check("stl3d" not in no_ib.to_dict(),
      "7. an unconfigured IB config adds no inert stl3d block")
rt = PipelineConfig.from_dict(with_ib.to_dict())
check(rt.stl3d.get("stl_path") == "/tmp/body.stl",
      "7. the stl3d section round-trips")
check(rt.build_stl3d_config().case_name == "ib_case",
      "7. build_stl3d_config rebuilds the Stl3dConfig")

ctl3 = AppController()
ctl3._apply_pipeline_config(rt, "in_memory.json")
check(ctl3.global_stl3d_config.case_name == "ib_case",
      "7. loading a script applies the IB section to the panel")

# ── 8. a .hws workspace is a runnable pipeline ────────────────────────────
if have_geoms:
    ws = os.path.join(ctl.temp_dir, "case.hws")
    ctl.global_mesh_config.bl_layers = 11
    ctl.main_window.mesh_config_panel.set_config(ctl.global_mesh_config)
    ctl._write_workspace_file(ws)

    check(PipelineConfig.is_workspace_file(ws),
          "8. a workspace is recognised as such")
    check(not PipelineConfig.is_workspace_file(
              os.path.join(_REPO, "config", "pipeline", "naca_demo.json")),
          "8. ...and a pipeline script is not")
    check(PipelineConfig.file_version(ws) == PIPELINE_FORMAT_VERSION,
          "8. a workspace reports no bogus pipeline-version migration")

    from_ws = PipelineConfig.load_from_file(ws)
    ws_named = [os.path.basename(c.get("input_file") or "") for c in from_ws.cads]
    check(len(from_ws.cads) >= 2 and all(os.path.basename(g) in ws_named
                                        for g in GEOMS),
          f"8. every workspace session became a CAD entry ({ws_named})")
    check(int(from_ws.mesh.get("bl_layers", 0)) == 11,
          "8. the workspace's mesh configuration came across")
    derived = [k for k in ("work_dir", "getpgrid_binary", "solver_binary")
               if k in from_ws.solver]
    check(not derived,
          f"8. machine-specific solver paths are stripped for portability ({derived})")

# ── 9. the shipped example ────────────────────────────────────────────────
demo = os.path.join(_REPO, "config", "pipeline", "multi_element_demo.json")
if os.path.exists(demo):
    d = PipelineConfig.load_from_file(demo)
    check(len(d.cads) > 1,
          f"9. the shipped multi-geometry example declares {len(d.cads)} geometries")
    missing = [c["input_file"] for c in d.cads
               if not os.path.exists(os.path.join(_REPO, c.get("input_file", "")))]
    check(not missing, f"9. ...and all of its geometry files exist ({missing})")
else:
    print("SKIP config/pipeline/multi_element_demo.json not present", flush=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
