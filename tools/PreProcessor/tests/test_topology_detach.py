#!/usr/bin/env python3
"""DETACHING a generated topology into a hand-maintained file (issue #139, parent #133).

The escape hatch, and the four claims the ticket makes about it: detach STOPS the
projection, the detached file is NOT overwritten, re-attach RESUMES the projection
having said plainly what it costs, and the state ROUND-TRIPS through the project
file. Plus the surface it asks for — after detaching the panel is a read-only
summary that still names the family and the parameters that produced the file.

WHAT THIS FILE MEASURES RATHER THAN DESCRIBES. "Nothing overwrites it" is not a
source claim about a branch not taken: the document is hand-edited to something no
family would produce, the REAL funnel is run over it twice, and the REAL mesher is
then asked to cut it — a mesh with the node count the EDIT implies and not the one
the template does. A check that only compared the file's bytes would pass on a
configuration whose run never read the file at all.

WHAT ANOTHER GATE OWNS: the document's structure (`test_topology_templates.py`),
parameters <-> families in both directions (`test_topology_param_specs.py`, whose
checks 3 and 3b hold the STATE-row exclusion this ticket's flag needed), the
round-trip of the ATTACHED model (`test_topology_persistence.py`) and the binding
repair (`test_topology_repair.py`).

ONE DEFECT ADJACENT TO THIS TICKET WAS FOUND AND FIXED, and check 15 is its gate:
`mesh_modes.missing_mesh_input` refused every ATTACHED template case, because
`mesh_topology_file` is an output while a family drives the run and is therefore
empty until `save_config_to_file` projects the document — which happens after the
precondition. The GUI showed "MESH_TOPOLOGY_FILE names none" on a fully configured
case and `pipeline_runner` raised it as a `PipelineError` before writing anything, so
no template case could run through the pipeline at all. It is #139's business only
because "re-attach returns to generating" would otherwise return the user to a case
the pipeline refuses.

INJECTIONS: run by hand, 2026-09-23, each applied to a real source file, this gate
run in a subprocess, and the file restored from its pre-injection text with the
checksum compared afterwards. What is recorded is what each run PRINTED. (Every run
prints `QOpenGLWidget is not supported on this platform` on stderr, green runs
included — the exit code is the signal.)

  A. `names_a_family` back to `bool(self.family)`, so the flag stops turning the
     projection off -> 3, 3c, 5, 5b, 6c and 14 red. The blast radius is the point:
     one predicate carries detaching everywhere, which is why it is stated as the
     ONE owner rather than re-spelled at the funnel and the staging.
  B. `detach` sets the flag BEFORE writing the document -> 4d red, alone: a family
     that refuses leaves the configuration half detached, the projection off and no
     file for the run to read. Nothing else here reaches that state, which is why
     4d builds it deliberately with a broken binding.
  C. `reattach` leaves `mesh_topology_file` pointing at the detached file -> 6b red
     and 6 GREEN. That is the finding: with the family attached again the funnel
     OVERRIDES the line, so the run is correct and the panel still shows a path that
     decides nothing — the control that does nothing this ticket exists to remove,
     invisible to every behavioural check.
  D. `_refresh_topology_detach` not called from `_refresh_topology_counts` -> 10, 11,
     11b, 12 and 13b red. The one route in, the same shape #138's injection F found.
  E. the rows left ENABLED when detached (the `set_spec_row_enabled` loop dropped)
     -> 11 red alone; 12 stays green, because the summary is built from the model
     rather than from the widgets. An editable panel whose edits no longer take
     effect is precisely the state the ticket names, and only one check sees it.
  F. `_confirm_reattach` returning True unconditionally -> 7 red alone. The gate
     declines through the panel's own hook, so an implementation that asks nothing
     cannot be distinguished from one that asks and is refused by any other check.
  G. `provenance` hand-listing the H-grid's rows instead of deriving them from the
     table by prefix -> 12b red. 12 stays green on the hand-list, which is why 12b
     compares the summary against the TABLE rather than against a literal.

  Negative control: the unmutated tree passes every check below.

Run:  python3 tools/PreProcessor/tests/test_topology_detach.py
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
sys.path.insert(0, _HERE)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gui_file_lengths as fl  # noqa: E402
from topology_outline_fixture import split_segment_in_meta, write_outline  # noqa: E402

from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.models.mesh_config import MeshConfig  # noqa: E402
from app.models.mesh_config_io import save_config_to_file  # noqa: E402
from app.models.pipeline_config import PipelineConfig  # noqa: E402
from app.services import case_sources, topology_detach  # noqa: E402
from app.services import topology_binding as tb  # noqa: E402
from app.services import topology_ogrid as og  # noqa: E402
from app.services.mesh_modes import (  # noqa: E402
    MESH_MODE_MULTIBLOCK, missing_mesh_input,
)
from app.services.topology_field_specs import TOPOLOGY_SPECS  # noqa: E402
from app.views.panels.mesh_config_panel import MeshConfigPanel  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


_app = QApplication.instance() or QApplication([])
_TMP = tempfile.TemporaryDirectory()
_T = _TMP.name


def configured() -> MeshConfig:
    """A template-driven H-grid case, every parameter off its default.

    Off-default for `test_topology_persistence.py`'s reason: a round-trip that only
    carries the defaults would pass on a writer that dropped the section entirely.
    """
    c = MeshConfig()
    c.mesh_mode = MESH_MODE_MULTIBLOCK
    c.output_filename = os.path.join(_T, "mesh_detach.vtk")
    c.export_vtk = True
    c.export_starcd = False
    c.bl_initial_thickness = 0.002
    t = c.topology
    t.family = "hgrid"
    t.hgrid_x_min, t.hgrid_x_max = -0.5, 2.5
    t.hgrid_y_min, t.hgrid_y_max = 0.0, 1.25
    t.hgrid_nx, t.hgrid_ny = 3, 2
    t.hgrid_cell = 0.125
    t.hgrid_wall_bottom = True
    return c


def sidecars(d: str) -> list:
    """Every projected document sitting in ``d`` — what a projection LEAVES."""
    return sorted(n for n in os.listdir(d) if n.endswith("_topology.json"))


def topo_line(path: str) -> str:
    return next((ln.strip() for ln in open(path, encoding="utf-8")
                 if ln.startswith("MESH_TOPOLOGY_FILE")), "")


# ══ A. the flag, and the one predicate it turns off ════════════════════════

_m = configured().topology
check("1. an attached template drives the configuration: the family is named and "
      f"`names_a_family()` is True (family={_m.family!r})",
      _m.names_a_family() and not topology_detach.is_detached(_m))

_m.detached = True
check("2. detaching turns exactly that predicate off while LEAVING THE FAMILY "
      f"NAMED (family={_m.family!r}, names_a_family={_m.names_a_family()}, "
      f"is_detached={topology_detach.is_detached(_m)}) — the difference between "
      "'no template' and 'a template that has been detached' is the whole "
      "provenance this ticket is about",
      _m.family == "hgrid" and not _m.names_a_family()
      and topology_detach.is_detached(_m))

_none = MeshConfig().topology
check("2b. ...and a configuration that never had a template is NOT detached, so the "
      "panel's summary branch cannot fire for one",
      not topology_detach.is_detached(_none) and not _none.names_a_family())

check("2c. the flag makes the model CONFIGURED, so the optional project-file "
      "section carries it — a detached case whose section was omitted would reopen "
      "attached and regenerate over the file on its first run",
      _m.is_configured() and "topology" in
      (lambda c: (setattr(c.topology, "detached", True), c.to_dict())[1])(
          MeshConfig()))

# ══ B. detach stops the projection, and the file is left alone ════════════

_d1 = os.path.join(_T, "run1")
os.makedirs(_d1, exist_ok=True)
_attached = configured()
save_config_to_file(_attached, os.path.join(_d1, "case.dat"))
check(f"3pre. the NEGATIVE CONTROL: with the template attached, the funnel projects "
      f"a document beside the config and names it ({sidecars(_d1)})",
      sidecars(_d1) == ["case_topology.json"]
      and topo_line(os.path.join(_d1, "case.dat")).endswith("case_topology.json"))

_hand = os.path.join(_T, "hand_topology.json")
_detached = configured()
_written = topology_detach.detach(_detached.topology, _detached, _hand)
check(f"3b. detach writes the generated document at the path it is given and points "
      f"the configuration at it ({_detached.mesh_topology_file!r})",
      os.path.exists(_hand) and _written == _hand
      and json.load(open(_hand, encoding="utf-8")).get("blocks"))

# The hand edit: a block count no derivation would produce, so the mesh it cuts is
# distinguishable from the template's by counting nodes and not by reading a file.
_doc = json.load(open(_hand, encoding="utf-8"))
for _e in _doc["edges"]:
    if _e.get("count"):
        _e["count"] = 5
_doc["edges"][0]["count"] = 5
with open(_hand, "w", encoding="utf-8") as f:
    json.dump(_doc, f, indent=2)
_HAND_TEXT = open(_hand, encoding="utf-8").read()

_d2 = os.path.join(_T, "run2")
os.makedirs(_d2, exist_ok=True)
_conf2 = os.path.join(_d2, "case.dat")
save_config_to_file(_detached, _conf2)
check(f"3. a DETACHED configuration projects NOTHING — the funnel writes no document "
      f"beside the config ({os.listdir(_d2)}), because `names_a_family()` is the one "
      "predicate it asks and detaching turned it off",
      sidecars(_d2) == [])
check(f"3c. ...and the mesher parameters name the detached FILE, as they do for any "
      f"hand-written topology ({topo_line(_conf2)!r})",
      topo_line(_conf2) == f"MESH_TOPOLOGY_FILE {_detached.mesh_topology_file}")

save_config_to_file(_detached, os.path.join(_d2, "again.dat"))
check("4. the hand edit SURVIVES the run, byte for byte, across two passes through "
      "the real funnel — nothing on the write path so much as opens the file",
      open(_hand, encoding="utf-8").read() == _HAND_TEXT)

# 4d: the transition is ATOMIC. A family that refuses must leave the configuration
# attached rather than half detached (the projection off and no file to read).
_bodyd = write_outline(os.path.join(_T, "body"), 0.5, [0, 1, 2, 3], 12, "wall")
_fard = write_outline(os.path.join(_T, "far"), 4.0, [0, 1, 2, 3], 12, "farfield")
_og = MeshConfig()
_og.mesh_mode = MESH_MODE_MULTIBLOCK
_og.bl_initial_thickness = 1e-3
_og.add_geom_file(_bodyd)
_og.add_geom_file(_fard)
_og.topology.family = og.FAMILY
_og.topology.ogrid_body_geom, _og.topology.ogrid_far_geom = _bodyd, _fard
_og.topology.ogrid_body_segs = "0, 1, 2, 3"
_og.topology.ogrid_far_segs = "0, 1, 2, 3"
_og.topology.ogrid_cell = 0.2
split_segment_in_meta(_bodyd, 2, [8, 9])          # the CAD edit that breaks it
_bad_path = os.path.join(_T, "never_written.json")
_refusal = ""
try:
    topology_detach.detach(_og.topology, _og, _bad_path, tb.context_for_config(_og))
except ValueError as exc:
    _refusal = str(exc)
check(f"4d. a family that REFUSES leaves the configuration exactly as it was — still "
      f"attached, with no file written and no path stored, because the document is "
      f"built before anything is changed (refusal: {_refusal[:60]!r}, detached="
      f"{_og.topology.detached}, file={_og.mesh_topology_file!r})",
      bool(_refusal) and not os.path.exists(_bad_path)
      and not _og.topology.detached and _og.mesh_topology_file == ""
      and _og.topology.names_a_family())

# ══ C. the case a detached run stages ═════════════════════════════════════

_gen = case_sources.mesh_config_generated(_detached, "detach_rt")
check(f"5. a detached case stages ONLY its mesher parameters — no GENERATED document, "
      f"because there is nothing to generate ({[n for n, _ in _gen]})",
      len(_gen) == 1 and _gen[0][0].endswith(".dat"))
_ins = case_sources.mesh_input_paths(_detached, _REPO)
check(f"5b. ...and the detached FILE is staged as an input the case COPIES, which is "
      f"how a hand-written topology has always reached grid/cad/ ({_ins})",
      len(_ins) == 1 and os.path.abspath(_ins[0]) == os.path.abspath(_hand))

# ══ D. re-attach resumes, and says what it costs first ════════════════════

_re = configured()
_re.topology.detached = True
_re.mesh_topology_file = _hand
topology_detach.reattach(_re.topology, _re)
_d3 = os.path.join(_T, "run3")
os.makedirs(_d3, exist_ok=True)
save_config_to_file(_re, os.path.join(_d3, "case.dat"))
check(f"6. re-attach resumes the projection: the funnel writes the document again "
      f"({sidecars(_d3)}) and the run reads it rather than the file",
      sidecars(_d3) == ["case_topology.json"]
      and _re.topology.names_a_family())
check(f"6b. ...and the detached path is FORGOTTEN rather than left in the input row "
      f"({_re.mesh_topology_file!r}) — a path the next projection overrides is a "
      "control that does nothing, and it becomes live again the moment the family "
      "combo is set back to '(none)'",
      _re.mesh_topology_file == "")
check("6c. ...and the user's file is still on disk and still exactly as they left "
      "it: re-attaching stops READING it, it does not delete it",
      open(_hand, encoding="utf-8").read() == _HAND_TEXT)
check("6d. the discard is stated in ONE place both the dialog and this gate read, "
      f"and it says what is lost: {topology_detach.REATTACH_WARNING[:48]!r}...",
      "DISCARDED" in topology_detach.REATTACH_WARNING
      and "left on disk" in topology_detach.REATTACH_WARNING)

# ══ E. the panel ══════════════════════════════════════════════════════════

panel = MeshConfigPanel()
panel.show()
panel.sec_topology.expand()


def row_states() -> dict:
    """Every template row's enabled state, by attribute."""
    return {sp.attr: bool(getattr(panel, sp.attr).isEnabled())
            for sp in TOPOLOGY_SPECS if getattr(panel, sp.attr, None) is not None}


panel.set_config(MeshConfig())
check("10pre. with no template the detach box is HIDDEN whole — there is nothing to "
      "detach, and a button that refuses when pressed is worse than none",
      panel._topo_detach.isHidden())

panel.set_config(configured())
check(f"10. with a template attached the box offers DETACH and not re-attach "
      f"(detach={not panel._topo_detach.detach_btn.isHidden()}, "
      f"re-attach={not panel._topo_detach.reattach_btn.isHidden()})",
      not panel._topo_detach.isHidden()
      and not panel._topo_detach.detach_btn.isHidden()
      and panel._topo_detach.reattach_btn.isHidden())
_attached_states = row_states()
check("10b. ...and every template row is EDITABLE, apart from the state read-out "
      f"itself ({[k for k, v in _attached_states.items() if not v]})",
      [k for k, v in _attached_states.items() if not v] == ["topo_detached"])

_panel_file = os.path.join(_T, "from_panel.json")
panel._ask_detach_path = lambda default: _panel_file
panel._on_topology_detach()
_cfg_after = panel.get_config()
check(f"11pre. pressing Detach wrote the document and both rows the state lives in "
      f"(checkbox={panel.topo_detached.isChecked()}, "
      f"file={os.path.basename(panel.mesh_topology_file.text())!r})",
      os.path.exists(_panel_file) and panel.topo_detached.isChecked()
      and os.path.abspath(panel.mesh_topology_file.text())
      == os.path.abspath(_panel_file)
      and _cfg_after.topology.detached
      and not _cfg_after.topology.names_a_family())

_detached_states = row_states()
check(f"11. after detaching, every template row is READ-ONLY — the panel is a "
      f"summary and not an editable form whose edits no longer take effect, which "
      f"is the state the ticket names "
      f"(still enabled: {[k for k, v in _detached_states.items() if v]})",
      not any(_detached_states.values()))
check("11b. ...and the box now offers RE-ATTACH and not detach",
      panel._topo_detach.reattach_btn.isHidden() is False
      and panel._topo_detach.detach_btn.isHidden())

_summary = panel._topo_detach.summary_text()
check(f"12. ...and it still names the originating FAMILY and the file, which is the "
      f"only useful thing left three months later "
      f"({_summary.splitlines()[0][:52]!r}...)",
      "DETACHED" in _summary
      and "H-grid (rectangular blocks)" in _summary
      and os.path.basename(_panel_file) in _summary)

# DERIVED from the table, not hand-listed: a parameter added to a family and its
# table appears here with no edit. Compared against the table's own labels and the
# model's own values, so a hand-written summary that happens to agree today fails.
_hg = [sp for sp in TOPOLOGY_SPECS
       if sp.model_name and sp.model_name.startswith("hgrid_")]
_missing = [sp.label for sp in _hg
            if f"{sp.label}: " not in _summary]
check(f"12b. ...and EVERY parameter of that family, by the table's own labels "
      f"({len(_hg)} rows): "
      + (", ".join(_missing) + " are absent" if _missing else "all present"),
      bool(_hg) and not _missing)
check("12c. ...and the values shown are the model's, not a re-derivation: the "
      f"3x2 block counts and the 0.125 target cell this case was built with "
      f"({[ln.strip() for ln in _summary.splitlines() if 'Blocks in X' in ln]})",
      "Blocks in X: 3" in _summary and "Blocks in Y: 2" in _summary
      and "Target Cell Size: 0.125" in _summary)

# Re-attach, DECLINED, through the panel's own consent hook.
panel._confirm_reattach = lambda: False
panel._on_topology_reattach()
check("7. re-attach DECLINED changes nothing — the state, the row and the file are "
      f"all as they were (detached={panel.topo_detached.isChecked()}, "
      f"file={bool(panel.mesh_topology_file.text())})",
      panel.topo_detached.isChecked() and bool(panel.mesh_topology_file.text()))

panel._confirm_reattach = lambda: True
panel._on_topology_reattach()
check(f"7b. ...and accepted, it puts the panel back to generating: the rows are "
      f"editable again, the file row is empty and the box offers Detach "
      f"(file={panel.mesh_topology_file.text()!r})",
      not panel.topo_detached.isChecked()
      and panel.mesh_topology_file.text() == ""
      and not panel._topo_detach.detach_btn.isHidden()
      and [k for k, v in row_states().items() if not v] == ["topo_detached"])

# ── 13. through the REAL controller: the global model, the project snapshot,
#        and undo. A panel cannot make any of those claims about itself.
from app.controller import AppController  # noqa: E402

_ctl = AppController()
_p = _ctl.main_window.mesh_config_panel
_ctl.push_panel_config(_p, configured())
_ctl_file = os.path.join(_T, "from_controller.json")
_p._ask_detach_path = lambda default: _ctl_file
_before = _ctl._collect_project_state()["mesh_config"]
_p._on_topology_detach()
_snap = _ctl._collect_project_state()["mesh_config"]
check(f"13. detaching in the panel reaches the GLOBAL model and the project snapshot "
      f"— which is what the project file is written from — through the same funnel "
      f"as every other panel edit (detached {_before['topology']['detached']} -> "
      f"{_snap['topology']['detached']}, file {_snap['mesh_topology_file']!r})",
      _before["topology"]["detached"] is False
      and _snap["topology"]["detached"] is True
      and os.path.abspath(_snap["mesh_topology_file"])
      == os.path.abspath(_ctl_file)
      and _ctl.global_mesh_config.topology.detached)
check("13b. ...and the family and its parameters went with it, so the reopened "
      f"project can still say where the file came from "
      f"(family={_snap['topology']['family']!r}, nx={_snap['topology']['hgrid_nx']})",
      _snap["topology"]["family"] == "hgrid"
      and _snap["topology"]["hgrid_nx"] == 3)
check("13c. ...and it was RECORDED as an undo step rather than merely applied",
      _ctl.flush_project_snapshot())
_ctl.undo()
check(f"13d. ...so Ctrl+Z walks the detach back — the one panel action that writes a "
      f"file is no more special to undo than a spin box "
      f"(detached={_ctl.global_mesh_config.topology.detached}, "
      f"file={_ctl.global_mesh_config.mesh_topology_file!r})",
      not _ctl.global_mesh_config.topology.detached
      and _ctl.global_mesh_config.mesh_topology_file == "")

# ══ F. the round trip, through a real project file ════════════════════════

_rt = configured()
topology_detach.detach(_rt.topology, _rt, os.path.join(_T, "rt_topology.json"))
_script = os.path.join(_T, "case.json")
PipelineConfig.from_configs("detach_rt", None, _rt, None).save_to_file(_script)
_saved = json.load(open(_script, encoding="utf-8"))
check("8. the saved project file carries the detached FLAG beside the family and "
      f"its parameters ({ {k: v for k, v in (_saved['mesh'].get('topology') or {}).items() if k in ('family', 'detached', 'hgrid_nx')} })",
      (_saved["mesh"].get("topology") or {}).get("detached") is True
      and (_saved["mesh"].get("topology") or {}).get("family") == "hgrid")

_back = PipelineConfig.load_from_file(_script).build_mesh_config(None)
check("8b. ...and reloading it comes back detached, with the same provenance and "
      f"the same file (detached={_back.topology.detached}, "
      f"family={_back.topology.family!r})",
      _back.topology == _rt.topology
      and _back.mesh_topology_file == _rt.mesh_topology_file
      and not _back.topology.names_a_family())

_hws = os.path.join(_T, "case.hws")
_c1 = AppController()
_c1.global_mesh_config.load_from_dict(_rt.to_dict())
_c1.push_panel_config(_c1.main_window.mesh_config_panel, _c1.global_mesh_config)
with open(_hws, "w", encoding="utf-8") as f:
    json.dump(_c1.workspace_dict(), f, indent=2)
_c2 = AppController()
_c2.open_workspace_path(_hws)
check("9. save -> quit -> reopen in the GUI restores the detached state, so the case "
      f"the user comes back to still reads THEIR file rather than regenerating over "
      f"it (detached={_c2.global_mesh_config.topology.detached}, "
      f"family={_c2.global_mesh_config.topology.family!r})",
      _c2.global_mesh_config.topology == _rt.topology
      and _c2.global_mesh_config.mesh_topology_file == _rt.mesh_topology_file)

_legacy = PipelineConfig.load_from_file(
    os.path.join(_REPO, "config", "pipeline", "multiblock_cgrid_demo.json")
).build_mesh_config(None)
check("9b. a project file written before templates existed still loads ATTACHED to "
      f"nothing and detached from nothing (family={_legacy.topology.family!r}, "
      f"detached={_legacy.topology.detached})",
      _legacy.topology == MeshConfig().topology
      and not _legacy.topology.detached)

# ══ G. the preconditions both hosts apply ═════════════════════════════════

_tpl, _det, _plain, _naked = configured(), configured(), MeshConfig(), MeshConfig()
_det.topology.detached = True
_det.mesh_topology_file = _hand
_plain.mesh_mode = MESH_MODE_MULTIBLOCK
_plain.mesh_topology_file = "examples/topology/hgrid_blocks.json"
_naked.mesh_mode = MESH_MODE_MULTIBLOCK
_why = {k: missing_mesh_input(v) for k, v in
        (("template", _tpl), ("detached", _det), ("hand file", _plain),
         ("nothing", _naked))}
check(f"15. the mesh stage's precondition understands all four multi-block cases: a "
      f"TEMPLATE case declares its topology without naming a file and is no longer "
      f"refused for it, a DETACHED one and a hand-written one name theirs, and a "
      f"case with neither is still refused with the reason ({_why})",
      not _why["template"] and not _why["detached"] and not _why["hand file"]
      and "MESH_TOPOLOGY_FILE names none" in _why["nothing"])

# ══ H. the real mesher: the hand edit is what gets cut ════════════════════


def _nodes(vtk: str) -> int:
    with open(vtk, encoding="utf-8") as f:
        for ln in f:
            if ln.startswith("POINTS"):
                return int(ln.split()[1])
    return -1


if not os.path.exists(_BIN):
    print("SKIP  build/HybMesh2D not built; the real-mesh half is not measured.")
else:
    env = dict(os.environ)
    _lib = subprocess.run(["bash", os.path.join(_REPO, "tools", "scripts",
                                                "gmsh_lib_dir.sh")],
                          capture_output=True, text=True)
    if _lib.returncode == 0 and _lib.stdout.strip():
        env["DYLD_LIBRARY_PATH"] = _lib.stdout.strip()

    def run(cfg, tag: str):
        d = os.path.join(_T, f"mesh_{tag}")
        os.makedirs(d, exist_ok=True)
        conf = os.path.join(d, "case.dat")
        cfg.output_filename = os.path.join(d, f"{tag}.vtk")
        cfg.export_vtk, cfg.export_starcd = True, False
        save_config_to_file(cfg, conf)
        p = subprocess.run([_BIN, "-conf", conf], cwd=d, env=env,
                           capture_output=True, text=True, timeout=900)
        return p, os.path.join(d, f"{tag}.vtk")

    _pt, _vt = run(configured(), "template")
    check(f"14pre. the ATTACHED template still meshes (exit {_pt.returncode}, "
          f"{_nodes(_vt) if os.path.exists(_vt) else 'no mesh'} nodes) — the control "
          "every claim below is measured against",
          _pt.returncode == 0 and os.path.exists(_vt))

    _hand_cfg = configured()
    _hand_cfg.topology.detached = True
    _hand_cfg.mesh_topology_file = _hand
    _ph, _vh = run(_hand_cfg, "hand")
    check(f"14. the DETACHED run cuts the HAND-EDITED document: exit "
          f"{_ph.returncode}, and the node count is the edit's rather than the "
          f"template's ({_nodes(_vh) if os.path.exists(_vh) else 'no mesh'} vs "
          f"{_nodes(_vt) if os.path.exists(_vt) else '-'}). Byte-comparing the file "
          "could not make this claim — a run that never opened it would pass.",
          _ph.returncode == 0 and os.path.exists(_vh)
          and _nodes(_vh) > 0 and _nodes(_vh) != _nodes(_vt))
    check("14b. ...and the hand edit is STILL what is on disk after that run",
          open(_hand, encoding="utf-8").read() == _HAND_TEXT)

    # Both hosts, from ONE project file, on the detached case — the criterion's own
    # words are "behaves identically in a headless run". The round-trip's OWN file is
    # hand-edited first, and differently from the one above: without that the
    # detached document is byte-identical to what the template would have produced,
    # so a host that quietly re-projected would agree with one that read the file and
    # neither this check nor the next could tell.
    _rt_file = _rt.mesh_topology_file
    _rt_doc = json.load(open(_rt_file, encoding="utf-8"))
    for _e in _rt_doc["edges"]:
        if _e.get("count"):
            _e["count"] = 4
    with open(_rt_file, "w", encoding="utf-8") as f:
        json.dump(_rt_doc, f, indent=2)

    _hl = PipelineConfig.load_from_file(_script).build_mesh_config(None)
    _gui = AppController()
    _gui.open_workspace_path(_hws)
    _pg, _vg = run(_gui.global_mesh_config, "gui")
    _pl, _vl = run(_hl, "headless")
    _mm = [re.search(r"Inverted cells\s*:\s*(\d+) of (\d+)", (p.stdout or "") + (p.stderr or ""))
           for p in (_pg, _pl)]
    check(f"16. a detached case runs identically from the GUI-reopened project and "
          f"from the headless bridge: both exit 0 with zero inverted cells "
          f"({[m.group(0) if m else 'no row' for m in _mm]})",
          _pg.returncode == 0 and _pl.returncode == 0 and all(_mm)
          and all(m.group(1) == "0" for m in _mm))
    check(f"16b. ...and they produce the same mesh, node for node "
          f"({_nodes(_vg)} vs {_nodes(_vl)})",
          _nodes(_vg) > 0 and _nodes(_vg) == _nodes(_vl)
          and open(_vg, encoding="utf-8").read().split("CELLS")[0]
          == open(_vl, encoding="utf-8").read().split("CELLS")[0])
    check(f"16c. ...and BOTH read the hand-edited file rather than re-projecting: "
          f"the node count is the edit's and not the template's "
          f"({_nodes(_vg)} vs the control's {_nodes(_vt)})",
          _nodes(_vg) != _nodes(_vt)
          and json.load(open(_rt_file, encoding="utf-8")) == _rt_doc)

# ══ I. the files this ticket touched ══════════════════════════════════════

_lengths = fl.measure(fl.gui_dir(_REPO))
_touched = {k: v for k, v in _lengths.items()
            if "mesh_config" in k or "topology" in k or "field_widgets" in k}
_over = {k: v for k, v in _touched.items() if v > fl.LIMIT}
check(f"17. every panel and service file this ticket touched is under the repo's "
      f"~{fl.LIMIT}-line standard, measured from the same walk "
      f"`test_file_length.py` enforces (worst: "
      f"{max(_touched.items(), key=lambda kv: kv[1])})",
      not _over)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
print("All checks passed." if not failures else "", flush=True)
sys.stdout.flush()
# `os._exit` because Qt's teardown under the offscreen platform crashes on a machine
# with no GPU, which `run_all.sh` would read as a failing assertion.
os._exit(1 if failures else 0)
