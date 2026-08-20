#!/usr/bin/env python3
"""End-to-end headless smoke test for the full AppController.

Guards the regression where the autosave-recovery *modal* hung construction on
headless Qt platforms (see ``controller._maybe_recover_autosave``): it builds the
whole controller off-screen — even with a leftover autosave file present, the
exact condition that used to hang — then opens a geometry by path, switches
across every mode, and reads back the mesh/solver panel configs, all without any
interactive dialog.

macOS has no ``timeout``, so a watchdog thread hard-exits (code 99) if anything
blocks. ``os._exit`` skips stdout flushing, so every line prints with flush=True.

Run:  python3 tools/PreProcessor/tests/smoke_headless_appcontroller.py
(the script forces the offscreen platform itself, so the env var is optional).
"""
import os
import sys
import threading
import tempfile

# Force a headless Qt platform BEFORE importing PyQt, so this runs anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# This file lives in tools/PreProcessor/tests/; the package root (where `app`
# lives) is tools/PreProcessor/gui/, and the repo root is three levels up.
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


# Watchdog: if construction (or anything else) blocks — e.g. a modal-dialog
# regression — hard-exit with a clear message instead of hanging forever.
def _watchdog():
    print("FAIL watchdog: AppController blocked >30s "
          "(headless hang regression!)", flush=True)
    os._exit(99)


_wd = threading.Timer(30, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
check(app.platformName() in ("offscreen", "minimal"),
      f"running on a headless Qt platform ({app.platformName()})")

# Reproduce the exact regression condition: a leftover autosave file that used to
# trigger the modal recovery prompt. Construction must NOT block on it.
_autosave = os.path.join(tempfile.gettempdir(),
                         "hybmesh_preprocessor_autosave.hws")
_created_autosave = not os.path.exists(_autosave)
if _created_autosave:
    open(_autosave, "w").close()

from app.controller import AppController  # noqa: E402

c = AppController()
check(True, "AppController constructed headless with a leftover autosave (no hang)")
check(len(c.sessions) >= 1, f"has a startup session ({len(c.sessions)})")
check(c.main_window.tab_bar.count() >= 1,
      f"has a startup tab ({c.main_window.tab_bar.count()})")

# A blank tab is a real controller path (undo stack, canvas, sidebar wiring).
n0 = len(c.sessions)
c.new_blank_tab()
check(len(c.sessions) == n0 + 1, "new_blank_tab adds a session")

# Open a geometry by path (dialog-free) and confirm it materialised points.
geom = os.path.join(_REPO, "examples", "geometries", "naca0012.dat")
if os.path.exists(geom):
    c.load_geometry_from_path(geom)
    sess = c.active_session()
    npts = len(sess.original_points) if (sess is not None
                                         and sess.original_points is not None) else 0
    check(npts > 0, f"loaded geometry by path (naca0012.dat, {npts} pts)")
else:
    print(f"SKIP geometry load (missing {geom})", flush=True)

# Switching across every mode drives the mesh/solver/results/STL panels + canvas.
try:
    for idx in range(c.main_window.mode_combo.count()):
        c.main_window.mode_combo.setCurrentIndex(idx)
    check(True, f"switched across all {c.main_window.mode_combo.count()} modes (no crash)")
except Exception as e:  # pragma: no cover - defensive
    check(False, f"mode switching raised: {e}")

# Panels round-trip their configs (the get_config paths the pipeline/solver use).
mc = c.main_window.mesh_config_panel.get_config()
sc = c.main_window.solver_config_panel.get_config()
check(mc is not None and sc is not None, "mesh + solver panels return a config")

# Tidy the repro autosave file if we created it.
if _created_autosave:
    try:
        os.remove(_autosave)
    except OSError:
        pass

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
