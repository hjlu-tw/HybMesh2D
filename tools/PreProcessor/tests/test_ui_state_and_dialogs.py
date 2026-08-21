#!/usr/bin/env python3
"""Regression tests for findings N11 (layout persistence) and N12 (message grading).

**N11** — ``QSettings`` was used only for the recent-files list, so every launch
reset the window size/position and the Log Console dock.
``app/services/ui_state.py`` now saves and restores those, namespaced by
``LAYOUT_VERSION`` so a future layout change ignores stale state instead of
restoring it into a window it no longer describes.

N11 originally covered two more facts — the open stage and every collapsible
section's expanded flag — and **issue #27 took both back out** (USER-REQUESTED):
every launch must start from one known state, the CAD stage with every sidebar
section collapsed, because an unpredictable stage and an arbitrary set of open
sections cost more than the view they saved. Checks 1/2/4 below are therefore the
INVERSE of what they used to assert, and are kept inverted rather than deleted so
that reinstating either restore fails this gate instead of passing it. Dialog
accordions (``save_section_states`` / ``restore_section_states``, the Edit-BL
dialog) are a different, still-wanted feature and are out of scope here.

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
 1. A launch lands on the CAD stage with every sidebar section collapsed, even
    with a previous version's stage/section keys present; geometry and dock state
    are still saved and restored, and neither the stage nor a section flag is
    written or read any more.
 2. Keys are namespaced by LAYOUT_VERSION (now 2), and a version bump reads only
    its own namespace.
 3. It never touches QSettings on a headless platform (tests must not overwrite
    the real user's saved layout).
 4. The dialog-scope accordion API survives untouched, and every
    CollapsibleSection still exposes the stable `title` its keys depend on.
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
_real_headless = ui_state._headless
ui_state._settings = lambda: _SpySettings()
from app.controller import AppController  # noqa: E402

probe = AppController()
ui_state.save_ui_state(probe.main_window)
ui_state.restore_ui_state(probe.main_window)
check(not touched,
      f"3. headless neither reads nor writes the saved layout ({touched[:4]})")

# ── 1/2/4. a launch lands on CAD with every sidebar section collapsed ─────
# These checks are the INVERSE of what they used to assert. ui_state used to
# save and restore the active stage and every sidebar section's expanded flag;
# issue #27 removed both halves of both, deliberately, so that every launch
# starts from one known state. Window furniture (geometry + dock state) is the
# only thing a previous session still carries over. Inverting the checks rather
# than deleting them is what stops the old behaviour arriving back as a bug fix.
from app.views.collapsible import CollapsibleSection  # noqa: E402


class _MemSettings:
    """Records every read, so "the key is not written" and "the key is never
    even looked at" stay distinguishable."""

    def __init__(self, store, reads):
        self.store = store
        self.reads = reads

    def setValue(self, key, val):
        self.store[key] = val

    def value(self, key, default=None):
        self.reads.append(key)
        return self.store.get(key, default)

    def sync(self):
        pass


def _sidebar_sections(mw):
    """``(scope, section)`` for every collapsible section on every sidebar page,
    ``scope`` being the owning page's class name — i.e. the key format the deleted
    restore used, so the seeding below and the assertions share one walk. Walked
    here rather than asked of ui_state, which no longer has a helper for it: a
    gate that asked the code under test where to look would move with it."""
    out = []
    stack = getattr(mw, "sidebar_stack", None)
    for i in range(stack.count() if stack is not None else 0):
        page = stack.widget(i)
        if page is not None:
            out.extend((type(page).__name__, sec)
                       for sec in page.findChildren(CollapsibleSection))
    return out


store: dict = {}
reads: list = []
ui_state._settings = lambda: _MemSettings(store, reads)
ui_state._headless = lambda: False        # pretend we have a screen

# Settings a PREVIOUS version wrote: stage 3 (Solver) and every section expanded.
# The keys are rebuilt in the old format from the live sidebar rather than typed
# out, so a stale key is really one the removed restore would have consumed —
# under v1 (what a real upgrade finds on disk) and under the current prefix, so
# the invariant cannot pass merely because the namespace moved.
_seeded = _sidebar_sections(probe.main_window)
for _pfx in ("ui/v1", ui_state._PREFIX):
    store[f"{_pfx}/mode"] = 3
    for _scope, _sec in _seeded:
        store[f"{_pfx}/sections/{_scope}/{_sec.title}"] = True

launch = AppController()          # a launch, with that stale state in place
lmw = launch.main_window
# Index 0 is the invariant; the label is reported for diagnosis, not asserted, so
# that renaming the combo item is not a test failure.
check(lmw.mode_combo.currentIndex() == 0,
      f"1. a launch lands on stage index 0 (CAD) whatever was saved "
      f"(index {lmw.mode_combo.currentIndex()}, {lmw.mode_combo.currentText()!r})")

_secs = [s for _scope, s in _sidebar_sections(lmw)]
# Not a magic threshold: this is the same sidebar that was just walked to seed the
# stale keys, so a smaller count would let "every section is collapsed" pass
# vacuously on a window that has no sections to speak of.
check(bool(_secs) and len(_secs) == len(_seeded),
      f"1. the launched window exposes the same {len(_seeded)} sidebar sections "
      f"whose flags were seeded open ({len(_secs)})")
_open = [s.title for s in _secs if s.is_expanded]
check(not _open,
      f"1. ...and every one of them is collapsed at launch (open: {_open})")

_stale = [k for k in reads if k.endswith("/mode") or "/sections/" in k]
check(not _stale,
      f"1. neither the stage nor a section flag is even read back ({_stale[:3]})")
check(not hasattr(ui_state, "restore_active_stage"),
      "1. ui_state exposes no restore_active_stage for a caller to reinstate")
check(not hasattr(ui_state, "_sections"),
      "1. ...nor the private sidebar walker the section loops used")

# The save half goes with the restore half: a value written and never read is
# dead code that reads as a working feature.
store.clear()
ui_state.save_ui_state(lmw)
check(any(k.endswith("/geometry") for k in store),
      "1. window geometry is still saved")
check(any(k.endswith("/windowState") for k in store),
      "1. dock/window state is still saved")

# ...and the half that is KEPT has to come BACK, not merely be written. Two Qt
# facts bound what can be asserted here, and both were measured on a plain
# QMainWindow rather than assumed:
#   * ``saveState()`` is NOT byte-canonical across a restore (hide a dock,
#     restoreState the old blob -> the dock reappears but the blob differs), so
#     the dock is pinned by whether it is explicitly HIDDEN. ``isHidden()``, not
#     ``isVisible()``: this main window is never shown, so every child of it is
#     invisible and ``isVisible()`` would answer False either way;
#   * the offscreen platform does not honour a restored window SIZE at all (a
#     1234x777 blob comes back 798x774), so geometry is pinned as "the exact blob
#     written is what is read back, and restoreGeometry accepts it" — which is the
#     part this module actually owns.
_geom_saved = bytes(lmw.saveGeometry())
lmw.log_dock.hide()
check(lmw.log_dock.isHidden(), "1. (dock perturbed for the test)")
ui_state.restore_ui_state(lmw)
check(not lmw.log_dock.isHidden(),
      "1. restore brings the Log Console dock back")
_geom_disk = bytes(store[f"{ui_state._PREFIX}/geometry"])
check(_geom_disk == _geom_saved and lmw.restoreGeometry(_geom_disk),
      "1. ...and the geometry blob read back is the one written, and is accepted")

check(not any(k.endswith("/mode") for k in store),
      f"1. no active-stage key is written ({sorted(store)})")
check(not any("/sections/" in k for k in store),
      f"1. no sidebar section key is written "
      f"({[k for k in store if '/sections/' in k][:3]})")

# 2. Namespacing / version bump.
check(ui_state.LAYOUT_VERSION >= 2,
      f"2. LAYOUT_VERSION has moved past the v1 state this change orphans "
      f"({ui_state.LAYOUT_VERSION}) — `>=`, so a later legitimate layout bump "
      f"does not fail a check about this one")
check(all(k.startswith(f"ui/v{ui_state.LAYOUT_VERSION}/") for k in store),
      f"2. every written key is namespaced by layout version ({sorted(store)})")
old_prefix = ui_state._PREFIX
try:
    ui_state._PREFIX = f"ui/v{ui_state.LAYOUT_VERSION + 1}"
    reads.clear()
    ui_state.restore_ui_state(lmw)        # nothing saved under the next version
    check(bool(reads) and all(k.startswith(ui_state._PREFIX) for k in reads),
          f"2. a version bump reads only its own namespace ({reads})")
finally:
    ui_state._PREFIX = old_prefix

# 4. Dialog accordions are OUT of scope and must keep working: they key off the
#    same stable `title`, through the two functions that had to survive.
check(all(isinstance(getattr(s, "title", None), str) and s.title for s in _secs),
      "4. every section still exposes a non-empty `title` for a settings key")
check(callable(getattr(ui_state, "save_section_states", None))
      and callable(getattr(ui_state, "restore_section_states", None)),
      "4. the dialog-scope save/restore pair is untouched")

ui_state._settings = _real_settings
ui_state._headless = _real_headless

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

# ── 9. toolbar widgets are owned and placed ───────────────────────────────
# A QWidget created with NO PARENT is a top-level window in Qt. Five canvas-tool
# controls were built that way and never added to a toolbar layout, so two of them
# appeared as stray floating windows that did not close with the main window, and all
# five were unreachable. Both halves of that are checked here because both are silent:
# nothing warns, and the widget "exists" so any attribute test still passes.
from PyQt6.QtWidgets import QApplication as _QApp  # noqa: E402
from app.controller import AppController as _AppController  # noqa: E402

_ctl = _AppController()
_mw = _ctl.main_window
_mw.show()
_QApp.instance().processEvents()

_tops = [w for w in _QApp.instance().topLevelWidgets() if w.isVisible()]
check(_tops == [_mw],
      f"9. the main window is the ONLY visible top-level widget — a parentless widget "
      f"becomes its own window and outlives the main window "
      f"({[type(w).__name__ for w in _tops]})")

_STAGE_LISTS = (("cad_tb_widgets", 0), ("mesh_tb_widgets", 1),
                ("solver_tb_widgets", 3), ("ib_tb_widgets", 5))
for _attr, _stage in _STAGE_LISTS:
    _widgets = getattr(_mw, _attr, None)
    if not _widgets:
        continue
    _mw.mode_combo.setCurrentIndex(_stage)
    _QApp.instance().processEvents()
    # A widget must be positioned by the toolbar layout, or deliberately hidden
    # (separators are hidden in the two-row arrangement). "Neither" means it was
    # declared for visibility toggling and then never laid out.
    _orphans = [w for w in _widgets
                if _mw.tb_layout.indexOf(w) < 0 and not w.isHidden()]
    check(not _orphans,
          f"9. every widget in {_attr} is placed in the toolbar (or hidden on "
          f"purpose); unplaced: "
          f"{[w.text() if hasattr(w, 'text') else type(w).__name__ for w in _orphans]}")
    _unowned = [w for w in _widgets if w.isWindow()]
    check(not _unowned,
          f"9. ...and none of them is a top-level window ({_unowned})")

# ── 10. the toolbar arrangement is measured, not guessed ──────────────────
# This used to compare the WINDOW width against a hardcoded threshold, which was wrong
# twice: the toolbar is narrower than the window (the sidebar takes the rest), and a
# fixed number goes stale whenever a control is added, renamed or translated. The
# result was a single row whose labels were simply cut off.
check("threshold" not in open(
          os.path.join(_APP, "views", "main_window_toolbar_mixin.py"),
          encoding="utf-8").read().split('"""')[2],
      "10. no hardcoded width threshold is left in the layout code")

# Back to CAD: section 9 left the stage on IB, whose toolbar is short enough to fit
# anywhere — measuring that would make this section pass without testing the crowded
# row it exists for.
_mw.mode_combo.setCurrentIndex(0)
_QApp.instance().processEvents()

for _w in (1800, 1500, 1300, 1100, 950):
    _mw.resize(_w, 900)
    _QApp.instance().processEvents()
    _mw.adjust_toolbar_layout()
    _QApp.instance().processEvents()
    _avail = _mw.canvas_toolbar.width()
    # Whatever arrangement was chosen, every occupied row must fit. A row wider than
    # the toolbar is exactly the "labels cut off" the user reported.
    _need = [0] * max(_mw.tb_layout.rowCount(), 1)
    _counts = [0] * len(_need)
    for _i in range(_mw.tb_layout.count()):
        _it = _mw.tb_layout.itemAt(_i)
        _wd_ = _it.widget()
        if _wd_ is None:
            continue
        _r, _c, _rs, _cs = _mw.tb_layout.getItemPosition(_i)
        _need[_r] += _wd_.sizeHint().width()
        _counts[_r] += 1
    _margins = _mw.tb_layout.contentsMargins()
    _need = [n + _mw.tb_layout.horizontalSpacing() * max(c - 1, 0)
             + _margins.left() + _margins.right()
             for n, c in zip(_need, _counts)]
    _worst = max(_need) if _need else 0
    check(_worst <= _avail,
          f"10. at a {_w}px window the chosen arrangement fits the {_avail}px toolbar "
          f"(rows need {_need})")

# And the fallback is honest: when even two rows cannot fit, two rows is still what is
# chosen — the alternative is a single row that is even more truncated.
_mw.resize(700, 900)
_QApp.instance().processEvents()
_mw.adjust_toolbar_layout()
_QApp.instance().processEvents()
check(_mw.canvas_toolbar.height() > 50,
      "10. an extremely narrow window still gets the two-row arrangement")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
