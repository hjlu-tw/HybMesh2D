"""Headless (no-Qt) tests for the CAD closure feature (closed_mode / is_closed).

Exercises the model + command layer directly against a lightweight fake session
(no display), covering:
  - GeometryService.detect_closed on coincident / polygon / open / degenerate pts
  - ProjectModel.resolve_closure under each mode
  - SetClosedModeCmd execute/undo/redo restoring mode + resolved value + dirty flag
  - closed_mode serialization round-trip and legacy is_closed -> mode migration
  - PipelineConfig cad round-trip of closed_mode

Run: python3 tools/PreProcessor/tests/test_closed_mode.py
"""
import os
import sys
import json
import types
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI_DIR = os.path.normpath(os.path.join(_HERE, "..", "gui"))
sys.path.insert(0, _GUI_DIR)

from app.models.project import ProjectModel
from app.models.pipeline_config import PipelineConfig
from app.services.geometry_service import GeometryService
from app.commands.segment_cmds import SetClosedModeCmd

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def make_session(points):
    s = types.SimpleNamespace()
    s.project_model = ProjectModel()
    s.original_points = points
    s.is_geometry_modified = False
    return s


# Geometry fixtures
LOOP_COINCIDENT = np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]], float)
SQUARE = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)          # gap == 1 edge
OPEN_LINE = np.array([[0, 0], [1, 0], [2, 0], [3, 0]], float)       # gap == 3 edges
TWO_PTS = np.array([[0, 0], [1, 0]], float)

# ── 1. detect_closed ──────────────────────────────────────────────────────
check("detect_closed: coincident endpoints -> True",
      GeometryService.detect_closed(LOOP_COINCIDENT) is True)
check("detect_closed: unit square (gap ~ 1 edge) -> True",
      GeometryService.detect_closed(SQUARE) is True)
check("detect_closed: open polyline (gap >> spacing) -> False",
      GeometryService.detect_closed(OPEN_LINE) is False)
check("detect_closed: <3 points -> False",
      GeometryService.detect_closed(TWO_PTS) is False)
check("detect_closed: None -> False",
      GeometryService.detect_closed(None) is False)

# ── 2. resolve_closure ────────────────────────────────────────────────────
pm = ProjectModel()
pm.closed_mode = "auto"
check("resolve auto on square -> closed", pm.resolve_closure(SQUARE) is True)
check("resolve auto on open line -> open", pm.resolve_closure(OPEN_LINE) is False)
pm.closed_mode = "open"
check("resolve open forces False", pm.resolve_closure(SQUARE) is False)
pm.closed_mode = "closed"
check("resolve closed forces True", pm.resolve_closure(OPEN_LINE) is True)

# ── 3. SetClosedModeCmd execute / undo / redo ─────────────────────────────
s = make_session(OPEN_LINE)
s.project_model.closed_mode = "auto"
s.project_model.resolve_closure(s.original_points)      # auto -> open
check("start: mode auto, is_closed False",
      s.project_model.closed_mode == "auto" and s.project_model.is_closed is False)

cmd = SetClosedModeCmd(s, "closed", refresh_cb=lambda: None)
cmd.execute()
check("execute: mode closed + resolved True + dirty",
      s.project_model.closed_mode == "closed" and s.project_model.is_closed is True
      and s.is_geometry_modified is True)
cmd.undo()
check("undo: mode back to auto + resolved False + dirty restored",
      s.project_model.closed_mode == "auto" and s.project_model.is_closed is False
      and s.is_geometry_modified is False)
cmd.execute()   # redo
check("redo: mode closed + resolved True",
      s.project_model.closed_mode == "closed" and s.project_model.is_closed is True)

# ── 4. Serialization round-trip ───────────────────────────────────────────
pm = ProjectModel()
pm.closed_mode = "open"
pm.is_closed = False
pm.input_file = "x.dat"
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    tmp = f.name
try:
    pm.export_config(tmp)
    with open(tmp) as fh:
        data = json.load(fh)
    check("export writes closed_mode", data.get("closed_mode") == "open")
    pm2 = ProjectModel()
    pm2.load_from_config(json.load(open(tmp)))
    check("round-trip preserves closed_mode", pm2.closed_mode == "open")
finally:
    os.remove(tmp)

# ── 5. Legacy migration (no closed_mode key) ──────────────────────────────
pm_legacy_open = ProjectModel()
pm_legacy_open.load_from_config({"is_closed": False, "input_file": "a"})
check("legacy is_closed=False -> mode open + is_closed False",
      pm_legacy_open.closed_mode == "open" and pm_legacy_open.is_closed is False)
pm_legacy_closed = ProjectModel()
pm_legacy_closed.load_from_config({"is_closed": True})
check("legacy is_closed=True -> mode closed",
      pm_legacy_closed.closed_mode == "closed" and pm_legacy_closed.is_closed is True)

# ── 6. PipelineConfig cad round-trip ──────────────────────────────────────
pm_in = ProjectModel()
pm_in.closed_mode = "open"
pm_in.is_closed = False
pm_in.input_file = "x.dat"
pc = PipelineConfig.from_configs("t", pm_in, None, None)
check("from_configs carries closed_mode", pc.cad.get("closed_mode") == "open")
pm_out = pc.build_project_model("/tmp", "out.dat")
check("build_project_model restores closed_mode + is_closed",
      pm_out.closed_mode == "open" and pm_out.is_closed is False)
# legacy pipeline cad (no closed_mode) maps from is_closed
pc2 = PipelineConfig(name="t2")
pc2.cad = {"input_file": "x.dat", "is_closed": False}
pm_out2 = pc2.build_project_model("/tmp", "out.dat")
check("legacy pipeline cad maps is_closed -> mode open",
      pm_out2.closed_mode == "open")

print()
if failures:
    print(f"RESULT: {len(failures)} FAILED")
    sys.exit(1)
print("RESULT: ALL PASS")
