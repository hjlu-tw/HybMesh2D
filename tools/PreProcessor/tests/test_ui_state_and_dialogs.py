#!/usr/bin/env python3
"""Regression tests for findings N11 (layout persistence) and N12 (message grading).

**N11** — ``QSettings`` was used only for the recent-files list, so every launch
reset the window size/position, the Log Console dock, the open stage and every
collapsible section in every panel. ``app/services/ui_state.py`` now saves and
restores those, namespaced by ``LAYOUT_VERSION`` so a future layout change ignores
stale state instead of restoring it into a window it no longer describes.

**N12** — a correction first: the original review claimed error severity was never
used, having counted only the static ``QMessageBox.critical()`` method. In fact
``report_error()`` already used ``Icon.Critical`` and the project already had a
documented error/warning split (failed write vs failed read). The real defects were
narrower:

  * a failed STL **export** (a failed *write*) reported itself as a *warning*,
    contradicting that very convention;
  * preconditions ("draw a closed profile first") used warning/information
    inconsistently — nothing had gone wrong, so grading them like failures trains
    users to dismiss real problems;
  * several prompts were hand-rolled ``QMessageBox`` calls with **no headless
    guard**, i.e. a hang in tests, CI or the headless pipeline. That had already
    been patched three times site-by-site; the guard now lives in the helpers.

Checks:
 1. ui_state saves/restores geometry, dock state, sections and stage.
 2. It is namespaced by LAYOUT_VERSION, and a version bump ignores stale state.
 3. It never touches QSettings on a headless platform (tests must not overwrite
    the real user's saved layout).
 4. Every CollapsibleSection exposes the stable `title` the keys depend on.
 5. report_error / report_warning / report_info map to Critical / Warning /
    Information, and none of them blocks when headless.
 6. confirm() returns its headless_default instead of blocking.
 7. No raw QMessageBox severity/question call remains outside the helpers.
 8. A failed export reports at error severity, not warning.

Run:  python3 tools/PreProcessor/tests/test_ui_state_and_dialogs.py
"""
import os
import re
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_APP = os.path.join(_GUI, "app")
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >90s (an unguarded modal?)", flush=True)
    os._exit(99)


_wd = threading.Timer(90, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.services import ui_state  # noqa: E402

# ── 3. headless must not touch QSettings at all ───────────────────────────
# Verified before anything else, because the rest of this test deliberately
# forces the non-headless path and must not be what proves this.
touched = []


class _SpySettings:
    def setValue(self, *a):
        touched.append(a[0] if a else "?")

    def value(self, key, default=None):
        touched.append(key)
        return default

    def sync(self):
        pass


_real_settings = ui_state._settings
ui_state._settings = lambda: _SpySettings()
from app.controller import AppController  # noqa: E402

probe = AppController()
ui_state.save_ui_state(probe.main_window)
ui_state.restore_ui_state(probe.main_window)
ui_state.restore_active_stage(probe.main_window)
check(not touched,
      f"3. headless neither reads nor writes the saved layout ({touched[:4]})")

# ── 1/2/4: force the non-headless path with an in-memory settings double ───
class _MemSettings:
    def __init__(self, store):
        self.store = store

    def setValue(self, key, val):
        self.store[key] = val

    def value(self, key, default=None):
        return self.store.get(key, default)

    def sync(self):
        pass


store: dict = {}
ui_state._settings = lambda: _MemSettings(store)
ui_state._headless = lambda: False        # pretend we have a screen

mw = probe.main_window

# 4. Stable section keys depend on the title attribute.
sections = [s for _k, s in ui_state._sections(mw)]
check(bool(sections), f"4. sidebar collapsible sections are discoverable ({len(sections)})")
check(all(isinstance(getattr(s, "title", None), str) and s.title for s in sections),
      "4. every section exposes a non-empty `title` for its settings key")
keys = [k for k, _s in ui_state._sections(mw)]
check(len(keys) == len(set(keys)),
      f"4. section keys are unique ({len(keys)} sections, {len(set(keys))} keys)")

# 1. Round-trip: flip some sections and the stage, save, change, restore.
target = sections[0]
target.expand() if not target.is_expanded else target.collapse()
want_expanded = target.is_expanded
stage_before = mw.mode_combo.currentIndex()
new_stage = (stage_before + 1) % mw.mode_combo.count()
mw.mode_combo.setCurrentIndex(new_stage)

ui_state.save_ui_state(mw)
check(any(k.endswith("/geometry") for k in store),
      "1. window geometry is saved")
check(any(k.endswith("/windowState") for k in store),
      "1. dock/window state is saved")
check(any("/sections/" in k for k in store),
      "1. collapsible section states are saved")
check(store.get(f"{ui_state._PREFIX}/mode") == new_stage,
      "1. the active stage is saved")

# Perturb, then restore.
target.expand() if not want_expanded else target.collapse()
check(target.is_expanded != want_expanded, "1. (section perturbed for the test)")
ui_state.restore_ui_state(mw)
check(target.is_expanded == want_expanded,
      "1. restore brings the section's expanded state back")

mw.mode_combo.setCurrentIndex(stage_before)
ui_state.restore_active_stage(mw)
check(mw.mode_combo.currentIndex() == new_stage,
      "1. restore brings back the active stage")

# 2. Namespacing / version bump.
check(all(k.startswith("ui/v") for k in store),
      f"2. every key is namespaced by layout version ({sorted(store)[:2]})")
old_prefix = ui_state._PREFIX
try:
    ui_state._PREFIX = f"ui/v{ui_state.LAYOUT_VERSION + 1}"
    marker = target.is_expanded
    target.collapse() if marker else target.expand()
    ui_state.restore_ui_state(mw)        # nothing saved under the new version
    check(target.is_expanded != marker,
          "2. a version bump ignores stale state instead of restoring it")
finally:
    ui_state._PREFIX = old_prefix

ui_state._settings = _real_settings

# ── 5/6. graded, non-blocking message helpers ─────────────────────────────
import app.utils as utils  # noqa: E402

check(utils.is_headless(), "5. (the test platform is headless)")

seen = []
_real_box = utils._message_box
utils._message_box = lambda parent, title, msg, detail, severity: seen.append(severity)
utils.report_error(None, "t", "m")
utils.report_warning(None, "t", "m")
utils.report_info(None, "t", "m")
utils._message_box = _real_box
check(seen == ["error", "warning", "info"],
      f"5. the three helpers pass distinct severities ({seen})")

from PyQt6.QtWidgets import QMessageBox  # noqa: E402

check(utils._ICONS["error"] == "Critical"
      and utils._ICONS["warning"] == "Warning"
      and utils._ICONS["info"] == "Information",
      "5. severities map to Critical / Warning / Information icons")
check(all(hasattr(QMessageBox.Icon, name) for name in utils._ICONS.values()),
      "5. ...and all three icon names exist in this Qt version")

# None of them may block (they return immediately when headless).
utils.report_error(None, "t", "m")
utils.report_warning(None, "t", "m")
utils.report_info(None, "t", "m")
check(True, "5. no helper blocks on a headless platform")

check(utils.confirm(None, "t", "q?") is True,
      "6. confirm() returns its headless_default (True) instead of blocking")
check(utils.confirm(None, "t", "q?", headless_default=False) is False,
      "6. ...and honours headless_default=False for destructive prompts")

# ── 7. no raw severity/question modal outside the helpers ─────────────────
ALLOWED = {
    # Pure informational dialogs with no failure semantics and no batch path.
    "app/views/main_window_menu_mixin.py",      # Help > Keyboard Shortcuts
    "app/views/result_canvas_plots_mixin.py",   # plot-window notice
    "app/utils.py",                             # the helpers themselves
}
RAW = re.compile(r"QMessageBox\.(warning|critical|information|question)\s*\(")
offenders = []
for root, _dirs, files in os.walk(_APP):
    for fn in sorted(files):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(root, fn)
        rel = os.path.relpath(path, _GUI)
        if rel in ALLOWED:
            continue
        for i, line in enumerate(open(path, encoding="utf-8").read().splitlines()):
            if RAW.search(line):
                offenders.append(f"{rel}:{i + 1}")
check(not offenders,
      "7. prompts go through the graded, headless-safe helpers"
      + (f" (raw: {offenders})" if offenders else ""))

# ── 8. a failed export is an ERROR, not a warning ─────────────────────────
extrude_src = open(os.path.join(_APP, "controllers", "extrude_ctrl.py"),
                   encoding="utf-8").read()
check("report_error(" in extrude_src,
      "8. the STL export failure path reports at error severity")
check(not RAW.search(extrude_src),
      "8. ...and no raw QMessageBox call is left in that file")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
