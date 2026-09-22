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

INJECTIONS: run by hand, 2026-09-22, each reverted with `git checkout` against a
committed tree (the restore this repo has been bitten by doing on a mixed
tracked/untracked set). Nine, all of which bit in the end — and THREE of them
changed this file, which is recorded rather than tidied away:

  A. `MeshConfig.to_dict` emits the section unconditionally again -> check 1, and
     only check 1.
  B. `load_from_dict` back to the no-op-on-absent form -> checks 3 and 3b. Run
     under the same injection, `test_undo_redo.py` and `test_topology_panel.py`
     BOTH stay green: check 3 is the only thing standing between the user and a
     first template edit that Ctrl+Z cannot walk back, which is why it is stated
     as the inverse of check 1 rather than as a defensive nicety.
  C. `mesh_config_generated` drops its template branch -> checks 9, 9b, 9c, 10b.
     The FIRST run of this injection CRASHED the file at `_names[1]` instead of
     printing four red lines, which a reader scoring by FAIL count reads as no
     bite at all. Section E is indexed defensively now, and the four reds above
     are from the re-run.
  D. the staged document named by its ABSOLUTE `projection_path` -> INERT on the
     first run. Check 9b compared the parameter file's line against the staged
     NAME, and both came from the same variable, so it agreed with itself about a
     name that is not a filename. It now asserts the name has no directory part at
     all, because `stage_case_sources` writes a generated entry with
     `os.path.join(dest_dir, name)` and an absolute name lands OUTSIDE the case
     folder — a real defect the check could not see. Red on the re-run.
  E. `is_configured` asks `bool(self.family)` -> check 2. The number a user typed
     before touching the family combo is dropped by the omission.
  F. the pair ships but `config_to_text` is not given the path -> check 9b: the
     document is staged and nothing names it.
  G. the headless host keeps its own `Background_para_` copy of the rule ->
     checks 10 and 10b.
  H. `TopologyModel.load_from_dict` silently drops one parameter -> checks 5, 5b,
     7, 8b and 13 — and check 8 stays GREEN, because both hosts reload the same
     lossy way and agree about what they both lost. That is exactly why 5 compares
     BEFORE against AFTER and 13 compares the LIVE model's mesh against the
     round-tripped one; a two-host comparison alone cannot see a lossy restore.
  I. the funnel projects for a model naming no family -> check 6c. The first run
     CRASHED with `build_document`'s own ValueError out of the legacy config's
     save; 6c catches and reports it now, so the legacy file's whole promise is
     one red line rather than a stack trace.

  J. (added in review) one host spells the "does a template drive this?" predicate
     out of the model's attribute again instead of calling `names_a_family()` ->
     check 11b, which is a SOURCE scan on purpose: two spellings that agree today
     are exactly the state it refuses.

  K. (added in review) generated entries step aside from a PREVIOUS run's file
     again -> checks 10c and 10d. The first version of 10c stayed GREEN on it: it
     asked only whether each quoted document exists in the folder, and with two
     parameter files both quoting the first run's document every name still
     resolved. It measures a BIJECTION now — two parameter files pointing at one
     document while two documents sit there is what makes the record false.
  L. (added in review) the document failure costs the parameter file again ->
     check 10e. INERT twice before it bit: the first run crashed the file, and the
     `except` added to stop that made the raised placeholder satisfy the very
     condition the check was testing (one entry, no `MESH_TOPOLOGY_FILE` line). It
     pins the entry's NAME now, so "it raised" cannot read as "it fell back".

  Negative control: the unmutated tree passes all 32 checks, so the reds above are
  the mutations and not the checker.

  And a restore hazard this file re-learned: injection J was reverted with
  `git checkout`, which restored the file from HEAD and silently ate the
  UNCOMMITTED review fix in the same file. Commit before injecting, or restore by
  content — the repo has recorded this once already.
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

import logging  # noqa: E402


class _Catch(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.seen = []

    def emit(self, record):
        self.seen.append(f"{record.name}: {record.getMessage()}")


_catch = _Catch()
logging.getLogger().addHandler(_catch)
_legacy = PipelineConfig.load_from_file(_legacy_path).build_mesh_config(None)
check("6b. it loads with no topology model, so nothing about it changed: the "
      f"family is '' (got {_legacy.topology.family!r}) and MESH_MODE 1 still "
      f"reads the topology FILE it names "
      f"({_legacy.mesh_topology_file!r})",
      _legacy.topology.family == ""
      and _legacy.mesh_topology_file.endswith("cgrid_naca0012.json"))

with tempfile.TemporaryDirectory() as _tmp:
    _conf = os.path.join(_tmp, "legacy.dat")
    # Caught rather than allowed to propagate: a funnel that projected for a model
    # naming no family RAISES out of `build_document`, and an uncaught stack trace
    # here is scored as no bite at all by a reader counting red lines.
    try:
        save_config_to_file(_legacy, _conf)
        _raised = ""
    except Exception as exc:                                   # noqa: BLE001
        _raised = f"{type(exc).__name__}: {exc}"
    _sidecars = [n for n in os.listdir(_tmp) if n != "legacy.dat"]
    _text = open(_conf, encoding="utf-8").read() if os.path.exists(_conf) else ""
    _line = next((ln for ln in _text.splitlines()
                  if ln.startswith("MESH_TOPOLOGY_FILE")), "")
    logging.getLogger().removeHandler(_catch)
    check("6b2. ...and loading and writing it emits NO WARNING anywhere — the "
          "criterion's literal words are \"no migration prompt, no warning, no "
          "behaviour change\", and the first two are only visible on the log "
          f"stream and `parse_warnings`, not in the config that comes back "
          f"(warnings: {_catch.seen}; parse_warnings: "
          f"{getattr(_legacy, 'parse_warnings', 'unset — only a .dat read sets it')})",
          not _catch.seen and not getattr(_legacy, "parse_warnings", []))
    check("6c. ...and writing its config raises nothing, projects NOTHING beside "
          f"it and leaves the MESH_TOPOLOGY_FILE line exactly as the project file "
          f"declares it (raised {_raised or 'nothing'}; wrote {_sidecars}; "
          f"line: {_line!r})",
          not _raised and not _sidecars
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

# Indexed defensively, and every check below stated so that it can go RED rather
# than raise: an injection that removes the document entirely made this section
# CRASH at the first `_names[1]`, which a reader counting FAIL lines scores as a
# weaker bite than the one that only mis-NAMES it.
_doc_name = _names[1] if len(_names) > 1 else ""
_para = dict(_gen).get(_names[0] if _names else "", "")
_topo_line = next((ln for ln in _para.splitlines()
                   if ln.startswith("MESH_TOPOLOGY_FILE")), "")
check("9b. ...and the parameter file names its sibling by BARE FILENAME — no "
      "directory part at all, because `stage_case_sources` writes a generated "
      "entry with `os.path.join(dest_dir, name)` and an absolute name lands "
      f"OUTSIDE the case folder, where nothing then points at it "
      f"(name: {_doc_name!r}, line: {_topo_line!r})",
      bool(_doc_name) and _doc_name == os.path.basename(_doc_name)
      and not os.path.isabs(_doc_name)
      and _topo_line == f"MESH_TOPOLOGY_FILE {_doc_name}")

check("9c. ...and the staged document is the same text the run itself projected, "
      "from the one builder rather than from a second copy",
      dict(_gen).get(_doc_name) == topology_model.document_text(
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

# The pair must survive STAGING, not only be produced correctly. `grid/cad/` is
# never cleared between runs (`solver_case.prepare_case_dir` has no rmtree), and
# the staging renames a colliding entry, so before this was fixed a second run of
# the same case wrote `Background_para_<case>_2.dat` quoting the FIRST run's
# document — a folder stating in writing that a grid was cut from a topology it
# was not. Found by review, then reproduced; this drives the real service twice.
with tempfile.TemporaryDirectory() as _tmp:
    _grid = os.path.join(_tmp, "grid")
    case_sources.stage_case_sources([], _grid, generated=_gen)
    case_sources.stage_case_sources([], _grid, generated=_gen)
    _cad = os.path.join(_grid, "cad")
    _staged = sorted(n for n in os.listdir(_cad) if n != "SOURCES.txt")
    _dats = [n for n in _staged if n.endswith(".dat")]
    _quoted = {}
    for n in _dats:
        for ln in open(os.path.join(_cad, n), encoding="utf-8"):
            if ln.startswith("MESH_TOPOLOGY_FILE"):
                _quoted[n] = ln.split(None, 1)[1].strip()
    _docs = [n for n in _staged if n.endswith("_topology.json")]
    # A BIJECTION, not "the name resolves". The first version of this check asked
    # only whether the quoted document exists in the folder, and the injection that
    # restores the bug LEFT IT GREEN: with two parameter files both quoting the
    # first run's document, every quoted name still resolved. What makes the record
    # false is two parameter files pointing at ONE document while two documents sit
    # there, so that is what is measured.
    check("10c. re-staging the same case replaces the pair rather than renaming "
          "half of it: staged parameter files and staged documents are one-to-one, "
          f"each naming its OWN (staged {_staged}; quoted {_quoted})",
          len(_dats) == len(_docs) == len(_quoted)
          and sorted(_quoted.values()) == sorted(_docs)
          and len(set(_quoted.values())) == len(_dats))
    check("10d. ...and a generated entry does not accumulate `_2` copies across "
          "runs, because it is a reconstruction of the config as it stands now "
          f"and a previous run's is stale, not evidence ({_staged})",
          len(_staged) == 2)

# A family that cannot build must not cost the case its PARAMETER FILE too.


class _Broken:
    family = "broken"

    def names_a_family(self):
        return True


_broken_cfg = MeshConfig()
_broken_cfg.topology = _Broken()
# Caught, so the regression this closes goes RED rather than ending the file: the
# injection that restores it raises straight out of the family function.
try:
    _bgen = case_sources.mesh_config_generated(_broken_cfg, "broken")
except Exception as exc:                                       # noqa: BLE001
    _bgen = [(f"<raised {type(exc).__name__}>", "")]
check("10e. a template whose document cannot be built still stages the mesh "
      "parameters, with no MESH_TOPOLOGY_FILE line rather than one naming a file "
      f"that was never written — the record that shipped before templates, which "
      f"is worse than the pair and far better than the nothing the callers' own "
      f"`except` would have left ({[n for n, _ in _bgen]})",
      len(_bgen) == 1 and _bgen[0][0] == "Background_para_broken.dat"
      and "MESH_TOPOLOGY_FILE" not in dict(_bgen)[_bgen[0][0]])

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

# The predicate has ONE owner. Review found it spelled twice and INVERTED — the
# funnel asking whether to PROJECT, the staging asking whether to GENERATE — which
# is how two halves of one feature drift into disagreeing about what a template
# case even is. Scanned rather than asserted through behaviour, because two
# spellings that agree today are exactly the state this check exists to refuse.
_PRED_HOSTS = {
    "models/mesh_config_io.py": os.path.join(
        _GUI, "app", "models", "mesh_config_io.py"),
    "services/case_sources.py": os.path.join(
        _GUI, "app", "services", "case_sources.py"),
}
_own_pred = {k: re.findall(r"""getattr\(\s*model\s*,\s*["']family["']""",
                           open(v, encoding="utf-8").read())
             for k, v in _PRED_HOSTS.items()}
_uses = {k: "names_a_family()" in open(v, encoding="utf-8").read()
         for k, v in _PRED_HOSTS.items()}
check("11b. \"does a template drive this config?\" has ONE owner "
      f"(`TopologyModel.names_a_family`): both sites call it ({_uses}) and neither "
      f"spells it out of the model's attribute itself "
      f"({ {k: len(v) for k, v in _own_pred.items()} })",
      all(_uses.values()) and not any(_own_pred.values()))

_m = MeshConfig().topology
check("11c. ...and it is NOT `is_configured`, which answers a different question: "
      "parameters typed before the family combo is touched are configured (so the "
      "project file must carry them) while naming no family (so there is no "
      "document to build)",
      not _m.names_a_family() and not _m.is_configured()
      and (lambda t: t.is_configured() and not t.names_a_family())(
          _edited.topology))

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

        # THREE configs, because the criterion's words are "a headless run of the
        # same project file produces the same mesh as the GUI run" and a live
        # in-memory config is neither run. `gui` is a real AppController that
        # REOPENED the project file, `headless` is the pipeline bridge reading the
        # same file, and `live` is the model that was never written out — the
        # round-trip's own control, which is what caught the injection that drops
        # a field on restore while the two hosts agreed with each other about it.
        script = os.path.join(tmp, "case.json")
        PipelineConfig.from_configs("topo_rt", None, configured(),
                                    None).save_to_file(script)
        _hws2 = os.path.join(tmp, "reopen.hws")
        _c3 = AppController()
        _c3.global_mesh_config.load_from_dict(configured().to_dict())
        # The push is NOT decoration. `_collect_project_state` refreshes each model
        # FROM ITS PANEL before serialising, so an AppController whose panel was
        # never populated saves the panel's defaults over the config just loaded —
        # which this gate found by producing a 441-node hybrid mesh where the other
        # two hosts produced 253. The real GUI always has a populated panel.
        _c3.push_panel_config(_c3.main_window.mesh_config_panel,
                              _c3.global_mesh_config)
        with open(_hws2, "w", encoding="utf-8") as f:
            json.dump(_c3.workspace_dict(), f, indent=2)
        _c4 = AppController()
        _c4.open_workspace_path(_hws2)

        runs = {}
        for host, cfg in (("gui", _c4.global_mesh_config),
                          ("headless", PipelineConfig.load_from_file(script)
                           .build_mesh_config(None)),
                          ("live", configured())):
            conf = os.path.join(tmp, f"{host}.dat")
            cfg.output_filename = os.path.join(tmp, f"{host}.vtk")
            cfg.export_vtk = True
            cfg.export_starcd = False
            save_config_to_file(cfg, conf)
            p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=env,
                               capture_output=True, text=True, timeout=900)
            runs[host] = (p, (p.stdout or "") + (p.stderr or ""),
                          os.path.join(tmp, f"{host}.vtk"))

        for suffix, host in (("", "gui"), ("b", "headless"), ("c", "live")):
            p, out, vtk = runs[host]
            mm = re.search(r"Inverted cells\s*:\s*(\d+) of (\d+)", out)
            check(f"12{suffix}. the {host} config meshes: exit {p.returncode}, "
                  f"{mm.group(0) if mm else 'no Inverted cells row'}",
                  p.returncode == 0 and bool(mm) and mm.group(1) == "0"
                  and int(mm.group(2)) > 0 and os.path.exists(vtk))

        a, b = _points(runs["gui"][2]), _points(runs["headless"][2])
        check("13. a headless run of the project file produces the SAME MESH as "
              "the GUI run of it — node for node, snapped to 1e-10 and canonically "
              "ordered, both sides having been through the file rather than shared "
              f"an object ({len(a)} vs {len(b)} nodes)", a == b and len(a) > 0)

        c = _points(runs["live"][2])
        check("13b. ...and it is the mesh the model that was never written out "
              "produces, which is the round-trip's own control: without it, two "
              "hosts that reload the same lossy way would agree with each other "
              f"about a parameter they both lost ({len(c)} nodes)",
              a == c and len(c) > 0)

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
