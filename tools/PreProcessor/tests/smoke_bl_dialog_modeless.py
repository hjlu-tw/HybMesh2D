#!/usr/bin/env python3
"""Headless check that the boundary-layer editor dialog is MODELESS.

If it were still opened with QDialog.exec() (application-modal), the offscreen
run would block forever (no user to close it) and the watchdog would hard-exit.
A modeless show() returns immediately, so the script proceeds and asserts the
dialog is non-modal, is kept alive on self._bl_dialog, and is cleared on close.

Run: python3 tools/PreProcessor/tests/smoke_bl_dialog_modeless.py
"""
import os, sys, threading
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)

def _watchdog():
    print("FAIL watchdog: BL dialog open() blocked >15s (still modal .exec()?)", flush=True)
    os._exit(99)
threading.Timer(15.0, _watchdog).start()

from PyQt6.QtWidgets import QApplication
from app.views.panels.mesh_config_panel import MeshConfigPanel

app = QApplication.instance() or QApplication(sys.argv)
panel = MeshConfigPanel()

# --- open the GLOBAL BL editor: must return immediately (modeless) ----------
panel._open_global_bl_dialog()
print("PASS _open_global_bl_dialog() returned (did not block -> modeless)", flush=True)

dlg = getattr(panel, "_bl_dialog", None)
check(dlg is not None, "dialog kept alive on panel._bl_dialog")
check(dlg is not None and not dlg.isModal(), "dialog is non-modal (isModal() == False)")

# --- single-instance guard: a second open() must not replace the dialog -----
panel._open_global_bl_dialog()
check(getattr(panel, "_bl_dialog", None) is dlg, "second open() reuses the same dialog (single instance)")

# --- OK commits via the accepted signal (mesh_config_changed emitted) -------
emitted = []
panel.mesh_config_changed.connect(lambda cfg: emitted.append(cfg))
dlg.result_params = lambda: dict(panel._global_bl)   # stub: return current params
dlg.accept()                                          # OK -> accepted -> on_accept=_commit
check(len(emitted) >= 1, "OK (accepted) committed -> mesh_config_changed emitted")

# --- closing clears the reference (finished handler) ------------------------
check(getattr(panel, "_bl_dialog", None) is None, "panel._bl_dialog cleared after close (accept)")

print(("\nRESULT: " + ("ALL PASS" if not _FAILS else f"{len(_FAILS)} FAIL")), flush=True)
os._exit(1 if _FAILS else 0)
