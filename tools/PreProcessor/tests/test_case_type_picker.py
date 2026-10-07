#!/usr/bin/env python3
"""WHICH case type is in play, and what the window says about it (issue #169).

The existing `test_case_type_verdict.py` asks "given a case type, is the
judgement right". This one asks the question nothing asked before: WHICH case
type is in play, and what does the window show. It needs the offscreen GUI
harness, which would drag Qt into a gate that is Qt-free today, so it is a file
of its own rather than a section of that one.

WHAT IT IS FOR. Until #169 the whole case-type workflow was headless:
`case_type.active_case_type()` had exactly one call site in the repo, no
controller, view or worker read `HYBMESH_CASE_TYPE`, and with the variable unset
`run_verdict` returned `(None, "", "INFO")` — so a Trial printed nothing at all
and an operator had no way to discover that the mechanism existed. Everything
behind that silence was already built and gated (#160, #162, #166, #168), and the
DEVIATION LIST in particular was computed on the GUI path, carried on every
`Verdict`, written into the commit sidecar and shown to nobody.

The fourteen checks, in the order the operator meets them:

  1.  The picker is a field-spec row with NO `.dat` key, so the parity gate is
      structurally blind to it and no allowance list grew an entry. Its model
      field is key-less in `_KEY_MAP` for the same reason.
  1b. It is in `case_type_fields.EXCLUDED` with a reason, so a case type cannot
      have an opinion about which case type judges it.
  2.  The choice survives the model round trip AND a real `.hws` save/reopen
      through two live `AppController`s.
  3.  The panel offers `(none)`, the shipped catalogue and `Browse…`, in EVERY
      mesh mode — a case type's thresholds are scoped by METRIC, not by mode.
  4.  A catalogue file that will NOT load is listed DISABLED with its reason,
      never omitted; a file that has GONE is listed as missing. Driven with a
      real broken document dropped into the shipped directory and removed again.
  5.  `Browse…` adds a file from outside that directory and selects it; CANCEL
      restores the previous choice, and neither ever leaves the sentinel as the
      configuration's value.
  6.  With NO case type chosen, a Trial SAYS so in one line — the thing that was
      silence before this ticket.
  7.  With one chosen in the panel, the Trial is judged by it and
      `HYBMESH_CASE_TYPE` is unset throughout: the picker really is the channel.
  8.  PRECEDENCE, both directions: the configuration beats the environment, and
      a configuration naming none falls back to it.
  9.  A chosen case type whose file has GONE is named in a WARNING, keeps its
      value in the picker shown as missing, and does not stop the Trial.
  10. The summary names the fields the case type owns and MARKS the ones this run
      has moved — against the FITTED overlay, the same one the verdict uses, so
      the panel and the verdict cannot disagree about what moved.
  11. Reopening a committed case STATES which case type judged it and does not
      alter the current choice.
  12. The pipeline script carries the case type through `to_dict` ->
      `PipelineConfig.mesh` -> `build_mesh_config`, and a real headless
      `run_pipeline.sh` reproduces the verdict with `HYBMESH_CASE_TYPE` UNSET.
      The end-to-end half is skipped without a build tree.
  13. A FALLBACK run names no case type, so the script a fallback commit leaves
      cannot have anyone judge an unstructured mesh against bounds measured on
      structured quads (#167's rule, reached by #169's new route).

THREE INJECTIONS, run in-process at the end of this file so they run on every CI
run rather than by hand. Each monkeypatches the MODULE attribute the production
code resolves at call time, asserts the probe was green first, and requires the
named check's probe to go red and then green again after the restore:

  A. `case_type_picker.catalogue` dropping every unloadable entry -> check 4's
     disabled row disappears. That is the exact silence the rule exists against:
     "a case type the operator named and the tool quietly ignored is how a
     verdict goes missing".
  B. `case_type_picker.write_choice` made a no-op for a value the list does not
     hold -> check 9's "keeps its value in the picker" goes red while the
     WARNING half stays green, which is why the two halves are separate.
  C. `case_type_picker.for_config` ignoring its config and reading only the
     environment -> check 8's first direction goes red. That is the pre-#169
     behaviour exactly, so this injection restores the defect this ticket exists
     to remove.

Run:  python3 tools/PreProcessor/tests/test_case_type_picker.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
sys.path.insert(0, _GUI)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# EVERY check in this file runs with the environment channel UNSET unless it is
# the subject. The picker is what #169 delivers, and a gate that left
# `HYBMESH_CASE_TYPE` lying around would be measuring the old channel.
os.environ.pop("HYBMESH_CASE_TYPE", None)

from PyQt6.QtWidgets import QApplication, QFileDialog          # noqa: E402

from app.models.mesh_config import MeshConfig                   # noqa: E402
from app.models.mesh_config_keys import _KEY_MAP                # noqa: E402
from app.models.pipeline_config import PipelineConfig           # noqa: E402
from app.services import (case_type, case_type_fields,          # noqa: E402
                          case_type_picker, case_type_scale,
                          case_type_verdict, mesh_commit, mesh_fallback)
from app.services.field_spec import by_attr                     # noqa: E402
from app.services.mesh_field_specs import MESH_SPECS            # noqa: E402
from app.services.mesh_modes import (MESH_MODE_HYBRID,          # noqa: E402
                                     MESH_MODE_MULTIBLOCK)
from app.views.panels.mesh_config_panel import MeshConfigPanel  # noqa: E402

_SHIPPED = os.path.join("examples", "case_types", "ogrid_circle.casetype.json")

failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


_app = QApplication.instance() or QApplication([])


# ── fixtures ───────────────────────────────────────────────────────────────

#: The figures the shipped O-grid published, as `mesh_shape_stats` reads them
#: back. Copied from `test_case_type_verdict.py`'s fixture rather than imported,
#: because that file runs its whole gate on import.
_FIGS = dict(cells=3200, median=1.845977, p95=23.662285, maximum=32.767868)
_LAYER = dict(cells=800, median=5.184358, p95=28.507718, maximum=32.767868)
_BULK = dict(cells=2400, median=1.692763, p95=1.877756, maximum=1.881891)


def write_sidecar(mesh_path, metric="quad_midline_ratio"):
    base = os.path.splitext(mesh_path)[0]
    doc = {"tool": "HybMesh2D", "mesh": {"nodes": 1, "elements": 1, "quality": {
        "metric": metric, "cells": _FIGS["cells"], "median": _FIGS["median"],
        "p95": _FIGS["p95"], "max": _FIGS["maximum"],
        "layer": {"cells": _LAYER["cells"], "median": _LAYER["median"],
                  "p95": _LAYER["p95"], "max": _LAYER["maximum"]},
        "bulk": {"cells": _BULK["cells"], "median": _BULK["median"],
                 "p95": _BULK["p95"], "max": _BULK["maximum"]}}}}
    with open(base + ".provenance.json", "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


def write_case_type(path, name="Gate type", attention=10.0, unusable=200.0,
                    fields=None):
    doc = {"schema": "hybmesh-case-type", "version": 1, "name": name,
           "metric": "quad_midline_ratio",
           "thresholds": [{"key": "max", "attention": attention,
                           "unusable": unusable,
                           "advice": "Put more points round the body."}]}
    if fields:
        doc["version"] = 3
        doc["fields"] = fields
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return path


class _Any:
    """A main window that answers every call and records nothing."""

    def __getattr__(self, _name):
        return _Any()

    def __call__(self, *_a, **_k):
        return _Any()


def make_host(case_type_file=""):
    """The real mesh-generation controller over a recording stand-in window.

    The SAME shape `test_case_type_verdict.py` check 11 uses, so "a Trial says
    this" is measured through the production `_on_mesh_gen_finished` rather than
    through a re-implementation of it.
    """
    from app.controllers.mesh_gen_ctrl import MeshGenControllerMixin

    class _Host(MeshGenControllerMixin):
        def __init__(self):
            self.main_window = _Any()
            self.global_mesh_config = MeshConfig()
            self.global_mesh_config.case_type_file = case_type_file
            self.global_vtk_mesh = None
            self.global_vtk_path = ""
            self._mesh_trial = None
            self._trial_fingerprint = ""
            self._commit_after_mesh = False
            self._mesh_fallback = None
            self._trial_fallback = None
            self._pending_after_mesh = None
            self.reports = []
            self.lines = []

        def log(self, message, level=None):
            self.lines.append(str(message))

        def log_report(self, message, level="ERROR"):
            self.reports.append((str(message), level))

    return _Host()


def trial_reports(host, mesh, exit_code=0):
    host._on_mesh_gen_finished(exit_code, os.path.join(os.path.dirname(mesh),
                                                       "absent.dat"), mesh)
    return host.reports


panel = MeshConfigPanel()
panel.show()


def picker_rows(p=None):
    """`(label, stored, enabled)` per row of the live picker, in order."""
    w = (p or panel).case_type_file
    return [(w.itemText(i), str(w.itemData(i) or ""),
             w.model().item(i).isEnabled()) for i in range(w.count())]


# ══ 1. the field is declared once, and is invisible to the parity gate ══════
_spec = by_attr(MESH_SPECS).get("case_type_file")
check(_spec is not None and _spec.kind == "choice" and _spec.key == ""
      and _spec.model_name == "case_type_file" and _spec.modes is None,
      "1. the picker is ONE field-spec row, kind 'choice', with NO `.dat` key and "
      "no `modes=` restriction (spec=%r)"
      % (None if _spec is None
         else (_spec.kind, _spec.key, _spec.model_name, _spec.modes),))

_keyed = sorted(k for k, (attr, _c) in _KEY_MAP.items() if attr == "case_type_file")
check(not _keyed and "case_type_file" in {f for f in MeshConfig().to_dict()},
      "1. ...so the `.dat` KEY map carries no entry for it (%r) while `to_dict` "
      "does — which is what makes `test_gui_cpp_config_parity.py` structurally "
      "blind to it, with no allowance list touched" % (_keyed,))

_reason = case_type_fields.EXCLUDED.get("case_type_file", "")
check(bool(_reason.strip())
      and "case_type_file" not in case_type_fields.ownable_names(),
      "1b. a case type may NOT own `case_type_file`, and the exclusion states its "
      "reason (%r) — otherwise applying one could replace the thing that judged "
      "its own result" % (_reason[:60] + "…" if _reason else "",))


# ══ 2. the choice survives the model and a real `.hws` round trip ══════════
_mc = MeshConfig()
_mc.case_type_file = _SHIPPED
_back = MeshConfig()
_back.load_from_dict(_mc.to_dict())
check(_back.case_type_file == _SHIPPED,
      "2. the choice round-trips through MeshConfig.to_dict/load_from_dict "
      "(%r)" % _back.case_type_file)

_blank = MeshConfig()
_blank.load_from_dict({"case_type_file": None})
check(_blank.case_type_file == "",
      "2. ...and an explicit JSON null lands as 'no case type chosen' rather than "
      "as None, which every reader would then have to defend against (%r)"
      % _blank.case_type_file)

from app.controller import AppController                        # noqa: E402

with tempfile.TemporaryDirectory() as _tmp:
    _c = AppController()
    _c.global_mesh_config.load_from_dict(_mc.to_dict())
    _c.push_panel_config(_c.main_window.mesh_config_panel, _c.global_mesh_config)
    _hws = os.path.join(_tmp, "case.hws")
    with open(_hws, "w", encoding="utf-8") as f:
        json.dump(_c.workspace_dict(), f, indent=2)
    _c2 = AppController()
    _c2.open_workspace_path(_hws)
    _reopened = _c2.global_mesh_config.case_type_file
    _shown = case_type_picker.read_choice(
        _c2.main_window.mesh_config_panel.case_type_file)
    check(_reopened == _SHIPPED and _shown == _SHIPPED,
          "2. ...and it survives saving and reopening a real `.hws` through two "
          "live AppControllers, in the model AND in the picker the user is "
          "looking at (model=%r, picker=%r)" % (_reopened, _shown))

    _headless = PipelineConfig.load_from_file(_hws).build_mesh_config(None)
    check(_headless.case_type_file == _SHIPPED,
          "2. ...and the headless host reads the SAME file to the same answer "
          "(%r), so a workspace run from `run_pipeline.sh` is judged by the case "
          "type the window showed" % _headless.case_type_file)


# ══ 3. the list, and it is there in EVERY mesh mode ════════════════════════
_rows = picker_rows()
_stored = [s for _l, s, _e in _rows]
check(_stored[0] == "" and _stored[-1] == case_type_picker.BROWSE
      and _SHIPPED in _stored,
      "3. the picker offers `(none)` first, the shipped catalogue, and `Browse…` "
      "last (%r)" % (_stored,))

_seen = {}
for _mode in (MESH_MODE_HYBRID, MESH_MODE_MULTIBLOCK):
    _cfg = MeshConfig()
    _cfg.mesh_mode = _mode
    panel.set_config(_cfg)
    _seen[_mode] = (panel.case_type_file.isVisible(),
                    panel.case_type_summary.isVisible())
check(all(all(v) for v in _seen.values()),
      "3. ...and the row and its read-out are visible in EVERY mesh mode (%r) — a "
      "case type's thresholds are scoped by METRIC, not by mode, and `judge` "
      "already refuses a mesh measured with a different quantity" % (_seen,))


# ══ 4. a file that will not load is LISTED, disabled, with its reason ══════
_broken = os.path.join(_REPO, "examples", "case_types",
                       "_gate_unreadable.casetype.json")
try:
    with open(_broken, "w", encoding="utf-8") as fh:
        fh.write('{"schema": "hybmesh-case-type", "version": 1, "name": "x"}\n')
    panel._populate_case_types(keep="")
    _rows = picker_rows()
    _bad = [r for r in _rows if "_gate_unreadable" in r[1]]
    check(len(_bad) == 1 and _bad[0][2] is False and "will not load" in _bad[0][0],
          "4. a catalogue file that will NOT load is SHOWN and unselectable rather "
          "than omitted (%r) — dropping it from the list is the silence this seam "
          "exists against" % (_bad,))
    _entry = case_type_picker.entry_for(
        os.path.relpath(_broken, _REPO))
    check(not _entry.loadable and _entry.why
          and _entry.why == str(_entry.why).strip() and "metric" in _entry.why,
          "4. ...and the reason shown is the LOADER's own sentence, naming what is "
          "wrong with the document (%r)" % (_entry.why[:90],))
finally:
    if os.path.exists(_broken):
        os.remove(_broken)
    panel._populate_case_types(keep="")

_gone = case_type_picker.entry_for("config/no_such.casetype.json")
check(not _gone.loadable and "missing" in _gone.label
      and "not there any more" in _gone.why,
      "4. a chosen case type whose FILE has gone is a row of its own, labelled "
      "missing (%r / %r)" % (_gone.label, _gone.why))


# ══ 5. Browse adds one from outside the catalogue; Cancel restores ═════════
with tempfile.TemporaryDirectory() as _tmp:
    _outside = write_case_type(os.path.join(_tmp, "sent_to_me.casetype.json"),
                               name="From a maintainer")
    _cfg = MeshConfig()
    _cfg.case_type_file = _SHIPPED
    panel.set_config(_cfg)

    _real = QFileDialog.getOpenFileName
    try:
        QFileDialog.getOpenFileName = staticmethod(
            lambda *_a, **_k: (_outside, ""))
        panel.case_type_file.setCurrentIndex(panel.case_type_file.count() - 1)
        _after = panel.get_config().case_type_file
        _rows = picker_rows()
        check(_after == os.path.abspath(_outside)
              and os.path.abspath(_outside) in [s for _l, s, _e in _rows]
              and [s for _l, s, _e in _rows][-1] == case_type_picker.BROWSE,
              "5. `Browse…` picks a case type from outside the shipped directory, "
              "and CHOOSING it is what adds it to the list — with the sentinel "
              "still last (chose=%r)" % (_after,))

        QFileDialog.getOpenFileName = staticmethod(lambda *_a, **_k: ("", ""))
        panel.case_type_file.setCurrentIndex(panel.case_type_file.count() - 1)
        _cancelled = panel.get_config().case_type_file
        _current = str(panel.case_type_file.currentData() or "")
        check(_cancelled == os.path.abspath(_outside)
              and _current != case_type_picker.BROWSE,
              "5. ...and CANCELLING restores the previous choice and never leaves "
              "the sentinel selected (config=%r, combo=%r)"
              % (_cancelled, _current))
    finally:
        QFileDialog.getOpenFileName = _real
        panel.set_config(MeshConfig())


# ══ 6. with NO case type chosen, a Trial SAYS so — in one line ═════════════
with tempfile.TemporaryDirectory() as _tmp:
    _mesh = os.path.join(_tmp, "m.vtk")
    open(_mesh, "w").close()
    write_sidecar(_mesh)

    _silent = trial_reports(make_host(""), _mesh)
    _said = [t for t, _l in _silent if case_type_verdict.NO_CASE_TYPE in t]
    check(len(_said) == 1 and _said[0].count("\n") == 0,
          "6. with no case type chosen a Trial SAYS so, in ONE line (%r) — before "
          "#169 this path returned the empty string and the host logged nothing "
          "at all, so silence read as approval" % (_said,))

    # ══ 7. the PICKER is the channel: the panel's choice judges the Trial ══
    _ct = write_case_type(os.path.join(_tmp, "picked.casetype.json"),
                          name="Picked in the window")
    _reports = trial_reports(make_host(_ct), _mesh)
    _verdicts = [t for t, _l in _reports if t.startswith("Verdict:")]
    check("HYBMESH_CASE_TYPE" not in os.environ and len(_verdicts) == 1
          and case_type_verdict.NEEDS_ATTENTION in _verdicts[0]
          and "Picked in the window" in _verdicts[0],
          "7. a case type chosen in the panel judges the Trial with "
          "`HYBMESH_CASE_TYPE` UNSET — the picker really is the channel, not a "
          "second way to set the variable (%r)"
          % (_verdicts[0].splitlines()[0] if _verdicts else _reports,))

    # ══ 8. precedence, in BOTH directions ═════════════════════════════════
    _env_ct = write_case_type(os.path.join(_tmp, "from_env.casetype.json"),
                              name="From the environment")
    _cfg = MeshConfig()
    _cfg.case_type_file = _ct
    os.environ["HYBMESH_CASE_TYPE"] = _env_ct
    try:
        _wins = case_type_picker.for_config(_cfg)
        _falls_back = case_type_picker.for_config(MeshConfig())
    finally:
        os.environ.pop("HYBMESH_CASE_TYPE", None)
    _none = case_type_picker.for_config(MeshConfig())
    check(_wins is not None and _wins.name == "Picked in the window",
          "8. the configuration's own choice BEATS `HYBMESH_CASE_TYPE` — a "
          "committed script that names its case type must reproduce ITS verdict, "
          "not the one the shell happened to be carrying (got %r)"
          % (None if _wins is None else _wins.name,))
    check(_falls_back is not None and _falls_back.name == "From the environment",
          "8. ...and a configuration naming NONE falls back to the variable, so a "
          "batch queue of many scripts can still be run under one case type "
          "(got %r)" % (None if _falls_back is None else _falls_back.name,))
    check(_none is None,
          "8. ...and with neither set the answer is `None`, which is the ordinary "
          "state and not an error (got %r)" % (_none,))

    # ══ 9. a chosen case type whose FILE has gone ═════════════════════════
    _vanished = write_case_type(os.path.join(_tmp, "vanishes.casetype.json"))
    _stored_vanished = case_type_picker.stored_spelling(_vanished)
    _cfg = MeshConfig()
    _cfg.case_type_file = _stored_vanished
    panel.set_config(_cfg)
    os.remove(_vanished)
    panel.set_config(_cfg)
    _rows = picker_rows()
    _row = [r for r in _rows if r[1] == _stored_vanished]
    check(panel.get_config().case_type_file == _stored_vanished
          and len(_row) == 1 and _row[0][2] is False and "missing" in _row[0][0],
          "9. a chosen case type whose file has GONE keeps its value in the "
          "picker, shown as missing (%r) — falling back to `(none)` would turn "
          "'your case type has moved' into 'you never chose one'" % (_row,))

    _host = make_host(_stored_vanished)
    _reports = trial_reports(_host, _mesh)
    _warned = [(t, lv) for t, lv in _reports if "No verdict" in t]
    check(len(_warned) == 1 and _warned[0][1] == "WARNING"
          and os.path.basename(_vanished) in _warned[0][0]
          and _host._mesh_trial is not None,
          "9. ...and the Trial NAMES it in a warning and still runs (%r, trial=%r)"
          % (_warned, _host._mesh_trial is not None))
    panel.set_config(MeshConfig())

# ══ 10. the summary names what the case type owns and what has moved ══════
with tempfile.TemporaryDirectory() as _tmp:
    _owning = write_case_type(
        os.path.join(_tmp, "owns.casetype.json"), name="Owns three",
        fields={"mesh_mode": 1, "bl_initial_thickness": 0.001, "export_vtk": True})
    _cfg = MeshConfig()
    _cfg.case_type_file = _owning
    _cfg.mesh_mode = 1
    _cfg.export_vtk = True
    _cfg.bl_initial_thickness = 0.05          # the ONE field this run has moved
    panel.set_config(_cfg)
    _text = panel.case_type_summary.text()
    check("Owns three" in _text and "mesh_mode" in _text
          and "bl_initial_thickness" in _text and "export_vtk" in _text,
          "10. the read-out names EVERY field the case type has an opinion about "
          "(story 24) — it was computed on this path and shown to nobody until "
          "#169 (%r)" % (_text.splitlines()[:2],))
    _moved_lines = [ln for ln in _text.splitlines() if "MOVED" in ln]
    check(len(_moved_lines) == 1 and "bl_initial_thickness" in _moved_lines[0]
          and "0.05" in _moved_lines[0],
          "10. ...and MARKS the one this run has moved, with both values (story "
          "20) (%r)" % (_moved_lines,))

    # ONE owner: the panel's list must be the verdict's list, against the FITTED
    # overlay. A second derivation here would be free to disagree with the
    # judgement the operator then reads, which is the whole failure this seam is
    # shaped around.
    _loaded = case_type.load(_owning)
    _wanted, _scale, _why = case_type_scale.fit(_loaded, _cfg)
    _service = {d.name for d in case_type_fields.deviations(_wanted, _cfg)}
    check(_service == {"bl_initial_thickness"}
          and all(any(n in ln for ln in _moved_lines) for n in _service),
          "10. ...and that set IS `case_type_fields.deviations` against the "
          "FITTED overlay — the same call `run_verdict` makes, so the panel and "
          "the verdict cannot disagree about what moved (%r)" % (sorted(_service),))
    panel.set_config(MeshConfig())

# ══ 11. a reopened committed case states its history and changes nothing ══
with tempfile.TemporaryDirectory() as _tmp:
    _case = os.path.join(_tmp, "case")
    os.makedirs(_case)
    _src = os.path.join(_tmp, "global_mesh.vtk")
    open(_src, "w").close()
    write_sidecar(_src)
    _ct = write_case_type(os.path.join(_tmp, "judge.casetype.json"),
                          name="Judged this case")
    _dest = os.path.join(_case, "mesh_probe.vtk")
    _cfg = MeshConfig()
    _cfg.case_type_file = _ct
    _trial = mesh_commit.judge_run(_src, 0, config=_cfg)
    mesh_commit.commit(_trial, _dest)

    _note = case_type_picker.committed_note(_dest)
    check("Judged this case" in _note and "unchanged" in _note,
          "11. reopening a committed case STATES which case type judged it "
          "(%r)" % (_note[:110],))

    # The REAL controller method over a recording host, so "a reopened case says
    # this" is measured through production code rather than a re-implementation.
    from app.controllers.project_state_ctrl import (                    # noqa: E402
        ProjectStateControllerMixin)

    class _Host2(ProjectStateControllerMixin):
        def __init__(self):
            self.global_mesh_config = MeshConfig()
            self.lines = []

        def _get_expected_vtk_path(self, _cfg):
            return _dest

        def log(self, message, level=None):
            self.lines.append(str(message))

    _h = _Host2()
    _h._say_committed_case_type()
    check(any("Judged this case" in ln for ln in _h.lines)
          and _h.global_mesh_config.case_type_file == "",
          "11. ...and it does NOT become the current choice: the embedded copy is "
          "FROZEN so a later correction cannot rewrite a finished case's "
          "judgement, and selecting it would judge the next Trial against a "
          "historical document (choice=%r)"
          % (_h.global_mesh_config.case_type_file,))

    _h2 = _Host2()
    _h2._get_expected_vtk_path = lambda _c: os.path.join(_tmp, "nothing.vtk")
    _h2._say_committed_case_type()
    check(not _h2.lines,
          "11. ...and a case carrying no embedded copy says NOTHING rather than "
          "inventing a history — which is every case committed before #166 and "
          "every one committed with no case type in play (%r)" % (_h2.lines,))

# ══ 12. the pipeline script carries it, and a headless run reproduces it ══
with tempfile.TemporaryDirectory() as _tmp:
    _ct = write_case_type(os.path.join(_tmp, "script.casetype.json"),
                          name="Carried by the script", attention=10.0,
                          unusable=1e9)
    _demo = os.path.join(_REPO, "config", "pipeline",
                         "multiblock_cgrid_demo.json")
    _pc = PipelineConfig.load_from_file(_demo)
    _pc.mesh["case_type_file"] = _ct
    _script = os.path.join(_tmp, "carried.json")
    _pc.save_to_file(_script)
    _reloaded = PipelineConfig.load_from_file(_script)
    check(_reloaded.build_mesh_config(None).case_type_file == _ct,
          "12. a pipeline script carries the case type through `to_dict` -> the "
          "`mesh` section -> `build_mesh_config` (%r)"
          % _reloaded.build_mesh_config(None).case_type_file)

    # ...and it is the ONE builder a Generate commits through: `from_configs` is
    # what `pipeline_io_ctrl.build_pipeline_config` hands the live mesh config to,
    # and `mesh_commit.commit(pipeline=)` writes its `save_to_file` into the case.
    _mc = MeshConfig()
    _mc.case_type_file = _ct
    _built = PipelineConfig.from_configs("probe", [], _mc, None, {})
    check(_built.mesh.get("case_type_file") == _ct,
          "12. ...and the script a Generate COMMITS carries it, through the one "
          "builder both the Pipeline menu and the commit use (%r)"
          % _built.mesh.get("case_type_file"))

    _exe = os.path.join(_REPO, "build", "HybMesh2D")
    if not os.path.isfile(_exe):
        print("      (skipping the end-to-end half of check 12: no build tree)",
              flush=True)
    else:
        _env = dict(os.environ)
        _env.pop("HYBMESH_CASE_TYPE", None)
        _p = subprocess.run(["./run_pipeline.sh", _script, "--no-solver"],
                            cwd=_REPO, env=_env, capture_output=True, text=True,
                            timeout=900)
        check("Verdict: " in _p.stdout
              and case_type_verdict.NEEDS_ATTENTION in _p.stdout
              and "Carried by the script" in _p.stdout,
              "12. ...and a REAL headless run of that script reproduces the "
              "verdict with `HYBMESH_CASE_TYPE` unset (rc=%d)" % _p.returncode)

# ══ 13. a FALLBACK run names no case type ═════════════════════════════════
_cfg = MeshConfig()
_cfg.mesh_mode = MESH_MODE_MULTIBLOCK
_cfg.case_type_file = _SHIPPED
_cfg.topology.family = "ogrid"
_hybrid = mesh_fallback.as_hybrid(_cfg)
check(_hybrid.case_type_file == "" and _cfg.case_type_file == _SHIPPED,
      "13. the hybrid FALLBACK transformation clears the case type as well as the "
      "family, so the script a fallback commit leaves cannot have anyone judge an "
      "unstructured mesh against bounds measured on structured quads — and the "
      "operator's own configuration is untouched (fallback=%r, panel=%r)"
      % (_hybrid.case_type_file, _cfg.case_type_file))


# ══ injections ════════════════════════════════════════════════════════════
# Each monkeypatches the MODULE attribute the production code resolves at CALL
# time (never a `FieldSpec`'s captured function object, which a monkeypatch
# cannot reach), asserts the mutation really changed the answer, and requires the
# named check's own probe to go RED and then GREEN again after the restore — a
# probe that stayed red would mean the injection had leaked into the checks
# printed after it. Run on every CI run rather than by hand.

_REAL = {name: getattr(case_type_picker, name)
         for name in ("catalogue", "write_choice", "for_config")}


def injected(label, name, replacement, probe):
    real = getattr(case_type_picker, name)
    assert real is _REAL[name], "%s: the world was not clean before %s" % (label, name)
    if probe():
        check(False, "%s: the probe was ALREADY red before the injection, so it "
                     "cannot measure anything" % label)
        return
    try:
        setattr(case_type_picker, name, replacement)
        went_red = probe()
    finally:
        setattr(case_type_picker, name, real)
    check(went_red, "%s — the check it is aimed at goes RED" % label)
    check(not probe(), "%s: ...and the restore really put it back" % label)


def _probe_disabled_row():
    """True when the disabled row check 4 asserts is MISSING from the picker."""
    broken = os.path.join(_REPO, "examples", "case_types",
                          "_gate_inj.casetype.json")
    try:
        with open(broken, "w", encoding="utf-8") as fh:
            fh.write('{"schema": "hybmesh-case-type", "version": 1, "name": "x"}\n')
        panel._populate_case_types(keep="")
        rows = [r for r in picker_rows() if "_gate_inj" in r[1]]
        return not (len(rows) == 1 and rows[0][2] is False)
    finally:
        os.remove(broken)
        panel._populate_case_types(keep="")


def _probe_kept_value():
    """True when a chosen case type whose file has gone LOSES its picker row."""
    cfg = MeshConfig()
    cfg.case_type_file = "config/_gate_gone.casetype.json"
    panel.set_config(cfg)
    rows = [r for r in picker_rows() if "_gate_gone" in r[1]]
    kept = panel.get_config().case_type_file
    panel.set_config(MeshConfig())
    return not (len(rows) == 1 and kept == cfg.case_type_file)


def _probe_precedence():
    """True when the configuration's own choice no longer beats the variable."""
    with tempfile.TemporaryDirectory() as tmp:
        mine = write_case_type(os.path.join(tmp, "mine.casetype.json"),
                               name="Mine")
        theirs = write_case_type(os.path.join(tmp, "theirs.casetype.json"),
                                 name="Theirs")
        cfg = MeshConfig()
        cfg.case_type_file = mine
        os.environ["HYBMESH_CASE_TYPE"] = theirs
        try:
            _v, text, _lvl = case_type_verdict.run_verdict(
                os.path.join(tmp, "absent.vtk"), 0, config=cfg)
        finally:
            os.environ.pop("HYBMESH_CASE_TYPE", None)
        return "Mine" not in text


injected("injection A. `catalogue` drops every unloadable entry — the exact "
         "silence the rule exists against",
         "catalogue",
         lambda extra=(): [e for e in _REAL["catalogue"](extra) if e.loadable],
         _probe_disabled_row)

injected("injection B. `write_choice` is a no-op for a value the list does not "
         "hold, so a vanished case type silently reverts to `(none)`",
         "write_choice", lambda _w, _v: None, _probe_kept_value)

injected("injection C. `for_config` ignores its config and reads only the "
         "environment — the pre-#169 behaviour exactly",
         "for_config", lambda config=None: case_type.active_case_type(),
         _probe_precedence)


print()
if failures:
    print("FAILED %d check(s)" % len(failures))
# `os._exit` because Qt's offscreen teardown crashes on a machine with no GPU
# AFTER every check has printed, and `run_all.sh` reads that crash as a failing
# test — the house ending for every script here that builds a QApplication,
# gated by `test_qt_teardown_exit.py`. It skips stdout flushing, hence the flush.
print("All checks passed." if not failures else "", flush=True)
sys.stdout.flush()
os._exit(1 if failures else 0)
