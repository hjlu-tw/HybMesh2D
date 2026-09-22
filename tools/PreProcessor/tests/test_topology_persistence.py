#!/usr/bin/env python3
"""The topology template SURVIVES THE SESSION, and both hosts reproduce it
(issue #135, parent #133).

#134 made the template a model and hooked its projection into the one call both
hosts make before launching the mesher. That model was already carried by
``MeshConfig.to_dict``/``load_from_dict``, so a great deal of what this ticket asks
for was true the day it was written. What was NOT true, and what this gate holds,
is the part that only shows up once the model is allowed to be ABSENT:

  * the section is OPTIONAL — a project with no template configured writes no
    ``topology`` key at all, following the ``stl3d`` precedent one file over. That
    is one line in ``to_dict``, and it silently breaks undo unless the other
    direction is defined with it: an absent key must RESET the model, or the first
    template edit is a step Ctrl+Z can never walk back. `to_dict` and
    `load_from_dict` are exact inverses here, and "absent means the DEFAULT model"
    is the whole rule.
  * the document is BYTE-IDENTICAL across save -> reload -> project, through a real
    file on disk rather than through a dict, because a dict round-trip cannot see a
    float that lost a digit to JSON or a parameter the writer never emitted.
  * the GUI host and the headless host produce the SAME document from the SAME
    project file. Not "both call the shared function" — that is a source claim, and
    #134's own finding was that a source claim about the funnel was true while the
    edit never reached it. Both hosts are driven here, from one file, to two
    documents that are then compared.
  * a case a template drove STAGES ITS DOCUMENT into ``grid/cad/``. This was
    #134's named blind spot, explicitly deferred here: the two callers that want
    the config as CONTENT read ``cfg.mesh_topology_file``, which is EMPTY for a
    template case because the path only exists once the projection has run. A
    staged config therefore carried no ``MESH_TOPOLOGY_FILE`` line at all, and a
    case that cannot say what topology it was cut from is exactly what
    ``grid/cad/`` exists to prevent.

WHAT THIS FILE DOES NOT CHECK, because another gate owns it: that the document
satisfies the mesher's structural rules (``test_topology_templates.py``), that the
parameters and the family functions agree in both directions
(``test_topology_param_specs.py``), and that the panel displays and carries an edit
(``test_topology_panel.py``).

INJECTIONS: run by hand, 2026-09-22, each reverted and the file compared against
its pre-injection copy afterwards.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
sys.path.insert(0, _GUI)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.models.mesh_config import MeshConfig            # noqa: E402
from app.models.mesh_config_io import save_config_to_file  # noqa: E402
from app.models.pipeline_config import PipelineConfig    # noqa: E402
from app.services import case_sources, topology_model    # noqa: E402
from app.services.mesh_modes import MESH_MODE_MULTIBLOCK  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def configured() -> MeshConfig:
    """A mesh config a template drives, with every parameter moved off default.

    Off-default deliberately: a round-trip that only carries the defaults proves
    nothing, because a writer that dropped the section entirely would still
    reload into a model that happens to agree.
    """
    c = MeshConfig()
    c.mesh_mode = MESH_MODE_MULTIBLOCK
    c.output_filename = "results/meshes/topo_rt/mesh_topo_rt.vtk"
    c.bc_geom = "wall"
    c.bl_initial_thickness = 0.002
    t = c.topology
    t.family = "hgrid"
    t.hgrid_x_min, t.hgrid_x_max = -0.5, 2.5
    t.hgrid_y_min, t.hgrid_y_max = 0.0, 1.25
    t.hgrid_nx, t.hgrid_ny = 3, 2
    t.hgrid_cell = 0.125
    t.hgrid_wall_bottom = True
    t.hgrid_counts_x = "9,,7"
    return c


def doc_of(cfg, tmp: str, name: str = "case.dat") -> str:
    """Write ``cfg`` through the real funnel and return the DOCUMENT's text."""
    conf = os.path.join(tmp, name)
    save_config_to_file(cfg, conf)
    with open(topology_model.projection_path(conf), encoding="utf-8") as f:
        return f.read()


# ══ A. the section is OPTIONAL, and absent means the DEFAULT model ═════════

_default = MeshConfig().to_dict()
check("1. a project with NO template configured writes no `topology` key at all, "
      "so a plain hybrid case's project file reads as it did before templates "
      f"existed (keys ending in 'topology': "
      f"{[k for k in _default if 'topology' in k]})",
      "topology" not in _default)

_edited = MeshConfig()
_edited.topology.hgrid_nx = 5
check("2. ...and the key appears as soon as ANY parameter is off its default, "
      "even with the family still '(none)' — the omission must never be able to "
      "eat a number the user typed",
      "topology" in _edited.to_dict()
      and _edited.to_dict()["topology"]["hgrid_nx"] == 5)

# The undo direction. `_collect_project_state` IS `to_dict()` and
# `_apply_project_state` IS `load_from_dict()`, so a snapshot taken before the
# first template edit carries NO topology key — and if an absent key were a
# no-op, undoing back to it would leave the edit in place. Every other field is
# restored by being present; this one is restored by being absent.
_undone = configured()
_undone.load_from_dict(_default)
check("3. a dict with no `topology` key RESETS the model to its defaults, which "
      "is what makes the first template edit undoable: the snapshot taken before "
      f"it has no key to restore from (family={_undone.topology.family!r}, "
      f"nx={_undone.topology.hgrid_nx})",
      _undone.topology == MeshConfig().topology)

_null = configured()
_null.load_from_dict({"topology": None})
check("3b. ...and an explicit JSON null, or anything that is not an object, is "
      "the same answer rather than a crash on the way to the family function",
      _null.topology == MeshConfig().topology)

# ══ B. the round-trip, through a real file on disk ════════════════════════

with tempfile.TemporaryDirectory() as _tmp:
    _cfg = configured()
    _before = doc_of(_cfg, _tmp, "before.dat")

    _script = os.path.join(_tmp, "case.json")
    PipelineConfig.from_configs("topo_rt", None, _cfg, None).save_to_file(_script)
    with open(_script, encoding="utf-8") as f:
        _saved = json.load(f)
    check("4. the saved project file carries the family and its parameters in its "
          "own section "
          f"(family={(_saved.get('mesh') or {}).get('topology', {}).get('family')!r})",
          (_saved.get("mesh") or {}).get("topology", {}).get("family") == "hgrid")

    _reloaded = PipelineConfig.load_from_file(_script).build_mesh_config(None)
    _after = doc_of(_reloaded, _tmp, "after.dat")
    check("5. save -> reload -> project reproduces a BYTE-IDENTICAL topology "
          f"document ({len(_before)} bytes; first difference at "
          f"{next((i for i, (a, b) in enumerate(zip(_before, _after)) if a != b), 'none')})",
          _before == _after and len(_before) > 0)

    check("5b. ...and the round-tripped model is the one that was saved, field by "
          "field, so check 5 is not two writers agreeing on a document neither "
          "populated", _reloaded.topology == _cfg.topology)

# ══ C. a project file written before templates existed ════════════════════

_legacy_path = os.path.join(_REPO, "config", "pipeline",
                            "multiblock_cgrid_demo.json")
with open(_legacy_path, encoding="utf-8") as f:
    _legacy_raw = json.load(f)
check("6. the shipped legacy project file this check reads really has no topology "
      "section — a legacy check against a file that grew one proves nothing",
      "topology" not in (_legacy_raw.get("mesh") or {}))

_legacy = PipelineConfig.load_from_file(_legacy_path).build_mesh_config(None)
check("6b. it loads with no topology model, so nothing about it changed: the "
      f"family is '' (got {_legacy.topology.family!r}) and MESH_MODE 1 still "
      f"reads the topology FILE it names "
      f"({_legacy.mesh_topology_file!r})",
      _legacy.topology.family == ""
      and _legacy.mesh_topology_file.endswith("cgrid_naca0012.json"))

with tempfile.TemporaryDirectory() as _tmp:
    _conf = os.path.join(_tmp, "legacy.dat")
    save_config_to_file(_legacy, _conf)
    _sidecars = [n for n in os.listdir(_tmp) if n != "legacy.dat"]
    with open(_conf, encoding="utf-8") as f:
        _text = f.read()
    _line = next((ln for ln in _text.splitlines()
                  if ln.startswith("MESH_TOPOLOGY_FILE")), "")
    check("6c. ...and writing its config projects NOTHING beside it and leaves the "
          f"MESH_TOPOLOGY_FILE line exactly as the project file declares it "
          f"(wrote {_sidecars}; line: {_line!r})",
          not _sidecars
          and _line == f"MESH_TOPOLOGY_FILE {_legacy.mesh_topology_file}")

# ══ D. the two hosts, from ONE project file ═══════════════════════════════

from PyQt6.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])
from app.controller import AppController  # noqa: E402

with tempfile.TemporaryDirectory() as _tmp:
    # The GUI writes the project file the way it writes every workspace, with the
    # live global config in it...
    _c = AppController()
    _c.global_mesh_config.load_from_dict(configured().to_dict())
    _c.push_panel_config(_c.main_window.mesh_config_panel, _c.global_mesh_config)
    _hws = os.path.join(_tmp, "case.hws")
    with open(_hws, "w", encoding="utf-8") as f:
        json.dump(_c.workspace_dict(), f, indent=2)

    # ...and reopens it, which is the user's "save, quit, reopen".
    _c2 = AppController()
    _c2.open_workspace_path(_hws)
    _gui_doc = doc_of(_c2.global_mesh_config, _tmp, "gui.dat")

    # The headless host reads the SAME file through the pipeline bridge.
    _headless_cfg = PipelineConfig.load_from_file(_hws).build_mesh_config(None)
    _headless_doc = doc_of(_headless_cfg, _tmp, "headless.dat")

    check("7. reopening the project in the GUI restores the template, so the mesh "
          f"the user regenerates is the one they saved "
          f"(family={_c2.global_mesh_config.topology.family!r}, "
          f"nx={_c2.global_mesh_config.topology.hgrid_nx}, "
          f"counts_x={_c2.global_mesh_config.topology.hgrid_counts_x!r})",
          _c2.global_mesh_config.topology == configured().topology)

    check("8. the GUI host and the headless host produce the SAME topology "
          f"document from the same project file, byte for byte "
          f"({len(_gui_doc)} vs {len(_headless_doc)} bytes)",
          _gui_doc == _headless_doc and len(_gui_doc) > 0)

    check("8b. ...and it is the document the model describes, not two hosts "
          "agreeing on an empty file",
          _gui_doc == topology_model.document_text(
              topology_model.build_document(configured().topology)))

    _gui_text = open(os.path.join(_tmp, "gui.dat"), encoding="utf-8").read()
    _hl_text = open(os.path.join(_tmp, "headless.dat"), encoding="utf-8").read()

    def _strip_paths(t: str) -> list:
        return [ln for ln in t.splitlines()
                if not ln.startswith("MESH_TOPOLOGY_FILE")]

    check("8c. ...and the mesher parameters the two hosts write agree line for "
          "line apart from the projected document's own path, which is beside "
          "each host's own config by construction",
          _strip_paths(_gui_text) == _strip_paths(_hl_text))

# ══ E. the staged case carries its document (#134's named blind spot) ═════

_case = configured()
_gen = case_sources.mesh_config_generated(_case, "topo_rt")
_names = [n for n, _ in _gen]
check("9. a case a template drove stages BOTH the mesher parameters and the "
      f"document they name, because `cfg.mesh_topology_file` is empty for a "
      f"template case and a staged config that quotes nothing records a grid "
      f"nobody can recut (got {_names})",
      len(_gen) == 2 and _names[0].endswith(".dat")
      and _names[1].endswith("_topology.json"))

_para = dict(_gen)[_names[0]]
_topo_line = next((ln for ln in _para.splitlines()
                   if ln.startswith("MESH_TOPOLOGY_FILE")), "")
check("9b. ...and the parameter file names its sibling by BARE FILENAME, so the "
      f"pair resolves wherever the case folder is copied to "
      f"(line: {_topo_line!r})",
      _topo_line == f"MESH_TOPOLOGY_FILE {_names[1]}")

check("9c. ...and the staged document is the same text the run itself projected, "
      "from the one builder rather than from a second copy",
      dict(_gen)[_names[1]] == topology_model.document_text(
          topology_model.build_document(_case.topology)))

_plain = MeshConfig()
_plain.mesh_mode = MESH_MODE_MULTIBLOCK
_plain.mesh_topology_file = "examples/topology/hgrid_blocks.json"
_plain_gen = case_sources.mesh_config_generated(_plain, "plain")
check("9d. a case whose topology is a hand-written FILE stages only the parameter "
      "file, as it always did — that file is copied in as a source, and a second "
      f"generated copy of it would be a second home for it (got "
      f"{[n for n, _ in _plain_gen]})",
      len(_plain_gen) == 1
      and f"MESH_TOPOLOGY_FILE {_plain.mesh_topology_file}"
      in dict(_plain_gen)[_plain_gen[0][0]])

# Both hosts through the ONE function, not two copies of the rule. The source
# scan is the half that #134's own finding says is not enough on its own, so the
# headless host is also driven for real below it.
_hosts = {
    "controllers/solver_ctrl.py": os.path.join(
        _GUI, "app", "controllers", "solver_ctrl.py"),
    "services/pipeline_case_sources.py": os.path.join(
        _GUI, "app", "services", "pipeline_case_sources.py"),
}
_calls = {k: "mesh_config_generated" in open(v, encoding="utf-8").read()
          for k, v in _hosts.items()}
_own = {k: bool(re.search(r"Background_para_", open(v, encoding="utf-8").read()))
        for k, v in _hosts.items()}
check(f"10. both hosts stage the case's mesh parameters through the ONE shared "
      f"function ({_calls}) and neither still spells the name itself ({_own})",
      all(_calls.values()) and not any(_own.values()))

_pcfg = PipelineConfig.from_configs("topo_rt", None, configured(), None)
from app.services import pipeline_case_sources  # noqa: E402

_srcs, _generated = pipeline_case_sources.case_sources_for(_pcfg, _REPO, None, "")
check("10b. ...and driving the real headless collector produces the pair, so "
      f"check 10's source scan is not the only evidence "
      f"(got {[n for n, _ in _generated]})",
      len(_generated) == 2
      and any(n.endswith("_topology.json") for n, _ in _generated))

# ══ F. Qt-free, and the real binary on the reloaded model ═════════════════

_probe = (
    "import sys; sys.path.insert(0, %r);"
    "import app.services.case_sources, app.models.pipeline_config;"
    "print('PyQt6' in sys.modules)" % _GUI)
_p = subprocess.run([sys.executable, "-c", _probe], capture_output=True,
                    text=True, cwd=_REPO)
check("11. the whole reload-and-stage path is Qt-free, so the headless host is "
      f"not a GUI that happens not to draw (subprocess said {_p.stdout.strip()!r})",
      _p.stdout.strip() == "False")


def _points(path: str) -> list:
    """The POINTS block of a legacy VTK, snapped to 1e-10 and canonically sorted.

    SNAPPED BEFORE SORTING, which is the lesson `tools/scripts/golden_mesh.py`
    records: this mesher wobbles at ~1e-13 run to run, so sorting raw coordinates
    lets a last-bit difference reshuffle the ranking and report a deviation that
    is really a permutation.
    """
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("POINTS"))
    n = int(lines[i].split()[1])
    vals = []
    for ln in lines[i + 1:]:
        vals.extend(float(v) for v in ln.split())
        if len(vals) >= 3 * n:
            break
    pts = [tuple(round(v / 1e-10) for v in vals[3 * k:3 * k + 3]) for k in range(n)]
    return sorted(pts)


if not os.path.exists(_BIN):
    print("SKIP  build/HybMesh2D not built; the real-mesh half is not measured.")
else:
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        lib = subprocess.run(["bash", os.path.join(_REPO, "tools", "scripts",
                                                   "gmsh_lib_dir.sh")],
                             capture_output=True, text=True)
        if lib.returncode == 0 and lib.stdout.strip():
            env["DYLD_LIBRARY_PATH"] = lib.stdout.strip()

        script = os.path.join(tmp, "case.json")
        PipelineConfig.from_configs("topo_rt", None, configured(),
                                    None).save_to_file(script)
        runs = {}
        for host, cfg in (("gui", configured()),
                          ("headless", PipelineConfig.load_from_file(script)
                           .build_mesh_config(None))):
            conf = os.path.join(tmp, f"{host}.dat")
            cfg.output_filename = os.path.join(tmp, f"{host}.vtk")
            cfg.export_vtk = True
            cfg.export_starcd = False
            save_config_to_file(cfg, conf)
            p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=env,
                               capture_output=True, text=True, timeout=900)
            runs[host] = (p, (p.stdout or "") + (p.stderr or ""),
                          os.path.join(tmp, f"{host}.vtk"))

        for host in ("gui", "headless"):
            p, out, vtk = runs[host]
            mm = re.search(r"Inverted cells\s*:\s*(\d+) of (\d+)", out)
            check(f"12{'' if host == 'gui' else 'b'}. the {host} host's project "
                  f"file meshes: exit {p.returncode}, "
                  f"{mm.group(0) if mm else 'no Inverted cells row'}",
                  p.returncode == 0 and bool(mm) and mm.group(1) == "0"
                  and int(mm.group(2)) > 0 and os.path.exists(vtk))

        a, b = _points(runs["gui"][2]), _points(runs["headless"][2])
        check("13. ...and the two meshes are the SAME mesh, node for node, snapped "
              f"to 1e-10 and canonically ordered ({len(a)} vs {len(b)} nodes)",
              a == b and len(a) > 0)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
# `os._exit` because Qt's teardown under the offscreen platform crashes on a
# machine with no GPU and `run_all.sh` would read that as a failing assertion —
# the same reason 41 other scripts here end this way. It skips stdout flushing,
# hence the explicit flush.
print("All checks passed." if not failures else "", flush=True)
sys.stdout.flush()
os._exit(1 if failures else 0)
