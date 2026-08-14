#!/usr/bin/env python3
"""Offscreen AppController test for the CAD closure feature end-to-end.

Verifies the render/UI wiring of closed_mode against the full controller:
  - fresh .dat load auto-detects closure; sidebar combo shows "Auto" + resolved hint
  - a real last->first gap draws the dashed closing edge; coincident loops do not
  - Open mode clears the closing edge and shows red endpoint markers
  - Closed mode restores the closing edge and clears the open markers
  - a mode sweep + panel get_config still works (no crash from the new combo items)

Run: python3 tools/PreProcessor/tests/test_closed_mode_gui.py
"""
import os
import sys
import threading
import tempfile
import functools

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

print = functools.partial(__builtins__.print if hasattr(__builtins__, "print")
                          else __import__("builtins").print, flush=True)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        _FAILS.append(msg)


def _n(item):
    xd, _ = item.getData()
    return 0 if xd is None else len(xd)


threading.Timer(40, lambda: (print("FAIL watchdog >40s"), os._exit(99))).start()

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402

c = AppController()
mw = c.main_window
mw.show()
app.processEvents()
sb = mw.sidebar_view
cv = mw.canvas_view

# A non-coincident closed polygon: auto-detects closed, with a REAL last->first
# gap (so the dashed closing edge must be drawn).
sq = os.path.join(tempfile.gettempdir(), "hybmesh_test_square.dat")
with open(sq, "w") as f:
    f.write("0 0\n1 0\n1 1\n0 1\n")

c.load_geometry_from_path(sq)
app.processEvents()
pm = c.active_session().project_model
check(pm.closed_mode == "auto", f"fresh .dat load stays Auto (got {pm.closed_mode})")
check(pm.is_closed is True, "square auto-detected as closed")
check(sb.file_panel.is_closed_combo.currentText() == "Auto", "combo shows 'Auto'")
check("Closed" in sb.file_panel.closed_mode_status.text(),
      f"status hint shows resolved Closed (got '{sb.file_panel.closed_mode_status.text()}')")
check(_n(cv._closing_edge) == 2, "dashed closing edge drawn for the real gap")

# Force Open: closing edge clears, endpoints get red markers.
c.handle_closed_mode_changed("Open")
app.processEvents()
check(pm.is_closed is False, "Open forces is_closed False")
check(sb.file_panel.is_closed_combo.currentText() == "Open", "combo shows 'Open'")
check(sb.file_panel.closed_mode_status.text() == "", "status hint blank when not Auto")
check(_n(cv._closing_edge) == 0, "closing edge cleared when Open")
check(_n(cv._open_endpoint_markers) >= 2, "open endpoints marked red when Open")

# Force Closed: closing edge returns, open markers clear.
c.handle_closed_mode_changed("Closed")
app.processEvents()
check(pm.is_closed is True, "Closed forces is_closed True")
check(_n(cv._closing_edge) == 2, "closing edge redrawn when Closed")
check(_n(cv._open_endpoint_markers) == 0, "open markers cleared when Closed")

# Back to Auto.
c.handle_closed_mode_changed("Auto")
app.processEvents()
check(pm.closed_mode == "auto" and pm.is_closed is True, "Auto re-resolves to closed")

# NACA (coincident endpoints): closed, but NO visible bridge needed.
naca = os.path.join(_REPO, "examples", "geometries", "naca0012.dat")
if os.path.exists(naca):
    c.new_blank_tab()
    c.load_geometry_from_path(naca)
    app.processEvents()
    pmn = c.active_session().project_model
    check(pmn.closed_mode == "auto" and pmn.is_closed is True,
          "naca0012 auto-detected closed")
    check(_n(cv._closing_edge) == 0,
          "coincident loop draws no bridge (closing edge empty)")
else:
    print("SKIP naca0012 (missing)")

# Regression: sweep all modes + panels still return configs.
try:
    for idx in range(mw.mode_combo.count()):
        mw.mode_combo.setCurrentIndex(idx)
        app.processEvents()
    check(True, f"mode sweep across {mw.mode_combo.count()} modes (no crash)")
except Exception as e:  # pragma: no cover
    check(False, f"mode sweep raised: {e}")
check(mw.mesh_config_panel.get_config() is not None
      and mw.solver_config_panel.get_config() is not None,
      "mesh + solver panels return a config")

try:
    os.remove(sq)
except OSError:
    pass

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
