"""Offscreen GUI smoke test for undo/redo.

Boots the real AppController + MainWindow under the Qt 'offscreen' platform,
loads a real geometry, and drives undo/redo through actual controller methods.
It never enters the event loop and avoids modal dialogs, so it does not hang.
Requires PyQt6 + pyqtgraph (a display is NOT required). Run with:

    python3 tools/PreProcessor/tests/smoke_undo_redo.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Resolve paths relative to this file so the test runs from any cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI_DIR = os.path.normpath(os.path.join(_HERE, "..", "gui"))
_REPO_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, _GUI_DIR)

from PyQt6.QtWidgets import QApplication, QSpinBox, QDoubleSpinBox, QComboBox

QSpinBox.wheelEvent = lambda self, e: e.ignore()
QDoubleSpinBox.wheelEvent = lambda self, e: e.ignore()
QComboBox.wheelEvent = lambda self, e: e.ignore()

app = QApplication(sys.argv)
import pyqtgraph as pg
pg.setConfigOption('background', '#0c0d16')
pg.setConfigOption('foreground', '#a0a8c0')

from app.controller import AppController

fails = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        fails.append(name)


def main():
    c = AppController()
    c.show_main_window()
    mw = c.main_window

    geom = os.path.join(_REPO_ROOT, "examples", "geometries", "naca0012.dat")
    c.load_geometry_from_path(geom)
    app.processEvents()
    sess = c.active_session()
    check("boot: session loaded", sess is not None)
    check("boot: geometry has points",
          sess.original_points is not None and len(sess.original_points) > 2)

    n0 = len(sess.project_model.segments)

    # add_curve_segment -> AddCurveSegmentCmd (blank path)
    c.add_curve_segment(); app.processEvents()
    check("add curve: +1 segment", len(sess.project_model.segments) == n0 + 1)
    check("add curve: undo btn enabled", mw.undo_btn.isEnabled())
    check("add curve: redo btn disabled", not mw.redo_btn.isEnabled())

    c.undo(); app.processEvents()
    check("undo add: back to n0 (no phantom)", len(sess.project_model.segments) == n0)
    check("undo add: redo btn enabled", mw.redo_btn.isEnabled())

    c.redo(); app.processEvents()
    check("redo add: +1 again", len(sess.project_model.segments) == n0 + 1)
    c.undo(); app.processEvents()

    # auto-detect breakpoints -> AutoDetectSplitCmd, then undo/redo
    splits0 = list(sess.split_indices)
    try:
        c.auto_detect_segments(angle_threshold_deg=30.0); app.processEvents()
        detected = list(sess.split_indices)
        c.undo(); app.processEvents()
        check("auto-detect undo: split_indices restored",
              list(sess.split_indices) == splits0)
        c.redo(); app.processEvents()
        check("auto-detect redo: split_indices == detected",
              list(sess.split_indices) == detected)
        c.undo(); app.processEvents()
    except Exception as e:  # pragma: no cover - surfaced as a failure
        check(f"auto-detect path raised: {e!r}", False)

    # empty-stack safety
    guard = 0
    while mw.undo_btn.isEnabled() and guard < 500:
        c.undo(); app.processEvents(); guard += 1
    c.undo(); app.processEvents()  # extra undo on empty stack -> no crash
    check("empty-stack undo: no crash, undo btn disabled", not mw.undo_btn.isEnabled())

    print()
    print("SMOKE RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
    app.quit()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
