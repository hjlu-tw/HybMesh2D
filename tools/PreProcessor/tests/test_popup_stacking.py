#!/usr/bin/env python3
"""Modeless pop-ups stay above the main window without vanishing behind other apps.

USER-REPORTED (2026-08-10): "in the GUI the pop-up is always on top, which is
right — but when I click another application's window the GUI is still there and
the pop-up I just opened is gone." That was ``Qt.Tool``: on macOS a Tool window
is an NSPanel with ``hidesOnDeactivate``, so the OS orders it off screen as soon
as the app is deactivated (measured on Qt 6.10: ``isExposed()`` goes False for a
Tool pop-up while a plain dialog stays put).

The fix is NOT to keep the Tool level and disable the auto-hide — a Tool window
sits at NSFloatingWindowLevel, so it would then float over the other app, which
is the intrusive behaviour ``WindowStaysOnTopHint`` was removed for. Instead the
pop-up is an ordinary normal-level window and ``_PopupRaiser`` lifts it back
above the main window whenever that window is activated.

USER-REPORTED follow-up (2026-08-11): "the CAD tab's arc pop-up opens BELOW the
main window." Dropping the Tool level exposed *when* the raise happens: a raise
issued from inside the event that reorders the windows is undone when the
platform finishes handling that event. The arc/line/… editor is shown from the
canvas mouse press that finishes the shape (``_begin_pending_edit``), so its
own ``show(); raise_()`` lost to the press, and the activation raise lost the
same way. Both raises are now deferred by one event-loop turn (``raise_later``),
and the pop-up re-raises itself on Show so every call site is covered.

Checks:
 1. keep_on_top() produces a normal-level Dialog window — no Tool bit (which
    would auto-hide on macOS), no WindowStaysOnTopHint (which would float over
    other applications).
 2. The pop-up is re-parented to the TOP-LEVEL window and marked, which is what
    lets the raiser find it and what stops a panel from hiding it.
 3. Activating the main window raises the pop-up back on top — the in-app half
    of the contract, which no longer comes from the window level.
 4. Only *marked, visible* windows are raised: a hidden pop-up and a plain child
    window are left alone.
 5. The raiser never consumes the activation event, and is installed once per
    top-level window however many pop-ups are opened.
 6. The raise is DEFERRED, not synchronous (the arc regression), and merely
    showing a pop-up schedules one — no call site has to remember to raise.
 7. A pop-up deleted between the event and the deferred raise is survivable
    (modeless dialogs are deleteLater()'d on close).

Run:  python3 tools/PreProcessor/tests/test_popup_stacking.py
"""
import os
import sys

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


from PyQt6.QtCore import QEvent, Qt                                  # noqa: E402
from PyQt6.QtWidgets import (                                        # noqa: E402
    QApplication, QDialog, QMainWindow, QWidget,
)
from app.utils import (                                              # noqa: E402
    KEEP_ON_TOP_PROP, _PopupRaiser, _RAISER_PROP, keep_on_top,
)

app = QApplication.instance() or QApplication(sys.argv)


class SpyDialog(QDialog):
    """Counts raise_() so the stacking contract is observable offscreen (where
    there is no real z-order to look at)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.raises = 0

    def raise_(self):
        self.raises += 1
        super().raise_()


def activate(win):
    QApplication.sendEvent(win, QEvent(QEvent.Type.WindowActivate))
    app.processEvents()


# ── fixture: a main window with a panel, the way real call sites are shaped ──
mw = QMainWindow()
panel = QWidget()
mw.setCentralWidget(panel)
mw.show()

dlg = SpyDialog(panel)          # parented to a PANEL, like sidebar/canvas dialogs
keep_on_top(dlg)

# ── 1. normal-level Dialog, not a Tool and not always-on-top ────────────────
flags = dlg.windowFlags()
wtype = flags & Qt.WindowType.WindowType_Mask
check(wtype == Qt.WindowType.Dialog,
      f"1. the pop-up is a plain Dialog window (got {wtype!r})")
check(wtype != Qt.WindowType.Tool,
      "1. not a Qt.Tool window — that is what macOS auto-hides on deactivation")
check(not (flags & Qt.WindowType.WindowStaysOnTopHint),
      "1. no WindowStaysOnTopHint — that would float above other applications")
check(bool(flags & Qt.WindowType.WindowCloseButtonHint),
      "1. it keeps a close button / title bar")

# ── 2. re-parented to the top level and marked for the raiser ───────────────
check(dlg.parent() is mw,
      f"2. re-parented from the panel to the top-level window (got {dlg.parent()!r})")
check(dlg.property(KEEP_ON_TOP_PROP) is True, "2. the pop-up is marked keep-on-top")
check(mw.property(_RAISER_PROP) is True, "2. a raiser is installed on the main window")
check(dlg.isWindow(), "2. it is still its own window, not an embedded child widget")

# ── 3. activating the main window lifts the pop-up back on top ──────────────
dlg.show()
app.processEvents()
before = dlg.raises
activate(mw)
check(dlg.raises > before,
      f"3. activating the main window raises the pop-up ({before} -> {dlg.raises})")

# ── 4. only marked, visible windows are touched ─────────────────────────────
plain = SpyDialog(mw)           # a child window that never asked to stay on top
plain.show()
app.processEvents()
dlg.hide()
app.processEvents()
n_dlg, n_plain = dlg.raises, plain.raises
activate(mw)
check(dlg.raises == n_dlg, "4. a HIDDEN pop-up is not resurrected by an activation")
check(plain.raises == n_plain, "4. an unmarked child window is left where it is")

dlg.show()
app.processEvents()
n_dlg = dlg.raises
activate(mw)
check(dlg.raises > n_dlg, "4. ...and showing it again puts it back under the contract")

# ── 5. the filter is transparent, and installed once ────────────────────────
ev = QEvent(QEvent.Type.WindowActivate)
check(_PopupRaiser(mw).eventFilter(mw, ev) is False,
      "5. the raiser never consumes the activation event")
second = SpyDialog(panel)
keep_on_top(second)             # a second pop-up must not add a second filter
second.show()
app.processEvents()
n_dlg, n_second = dlg.raises, second.raises
activate(mw)
check(dlg.raises == n_dlg + 1 and second.raises == n_second + 1,
      f"5. one raise per pop-up per activation (dlg +{dlg.raises - n_dlg}, "
      f"second +{second.raises - n_second}) — no duplicated filters")

# ── 6. the raise is deferred, and a plain show() schedules one ──────────────
# The arc regression: a raise issued INSIDE the event that reorders the windows
# is undone when the platform finishes that event, so nothing may be raised
# before control returns to the event loop.
n_dlg = dlg.raises
QApplication.sendEvent(mw, QEvent(QEvent.Type.WindowActivate))   # no processEvents
check(dlg.raises == n_dlg,
      "6. the activation raise is DEFERRED, not issued inside the event")
app.processEvents()
check(dlg.raises == n_dlg + 1,
      f"6. ...and lands on the next event-loop turn (+{dlg.raises - n_dlg})")

third = SpyDialog(panel)        # a call site that only show()s, never raise_()s
keep_on_top(third)
third.show()                    # opened from a canvas press, like the arc editor
check(third.raises == 0, "6. showing a pop-up does not raise inside the show")
app.processEvents()
check(third.raises >= 1,
      f"6. ...the pop-up raises itself one turn after being shown "
      f"({third.raises}) — no call site has to remember")

# ── 7. a pop-up closed before its deferred raise does not blow up ───────────
doomed = SpyDialog(panel)
keep_on_top(doomed)
doomed.show()                   # schedules a deferred raise
doomed.deleteLater()            # ...and dies first, as a modeless dialog does
try:
    app.processEvents()
    app.processEvents()
    ok = True
except RuntimeError as e:       # pragma: no cover - the bug this guards
    ok = False
    print(f"    deferred raise raised: {e}")
check(ok, "7. deleting a pop-up before its deferred raise is survivable")

print(("\nRESULT: " + ("ALL PASS" if not _FAILS else f"{len(_FAILS)} FAIL")), flush=True)
sys.exit(1 if _FAILS else 0)
