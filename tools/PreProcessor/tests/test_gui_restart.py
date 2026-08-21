#!/usr/bin/env python3
"""Issue #28 — the toolbar "Restart" button: close this GUI, then open a fresh one.

The feature is one click, but its correctness is entirely in the ORDER and in what
it does NOT do:

  * **Close first, spawn second.** Spawning first and then asking "discard unsaved
    changes?" leaves two GUIs running when the answer is No, which is the opposite
    of what the button is for.
  * **No second copy of the unsaved-work prompt.** ``handle_close_event`` already
    lists modified geometry sessions *and* a dirty Mesh/Solver/IB configuration; a
    second prompt would be a second place to forget a dirty-state source.
  * **No pipes.** ``proc_util.popen_kwargs()`` pipes stdout/stderr for the
    streaming workers. With the parent gone nobody drains them and the child stalls
    once the buffer fills, so the restart builds its own kwargs.

Two measured facts are pinned here rather than trusted:

  * ``close()``'s return value is the outcome signal, not ``isVisible()``. Measured
    under the offscreen platform: a *cancelled* close on a window that was never
    shown reports ``isVisible() == False`` / ``isHidden() == True``, exactly like a
    successful one, while ``close()`` returns False iff the event was ignored.
    Issue #28's own text suggests ``isVisible()`` as an option; it would have made
    check 4 pass for the wrong reason.
  * The button's LABEL is a width decision. At the narrowest supported window
    (``setMinimumSize(900, 600)``, of which the sidebar keeps >= 300) the tab row is
    540px; "⟳ Restart" is 88px and leaves 31px of slack, "⟳ New Session" measured
    119px, i.e. none. A guessed threshold has already caused a truncation bug here.

Checks:
 1. restart_command()'s argv: this interpreter + main.py resolved under repo_root(),
    and NO arguments (a brand-new session, not a clone of this case).
 2. Its kwargs: detached, cwd at the repo root, and stdin/stdout/stderr all DEVNULL
    with no PIPE anywhere. Negative control: popen_kwargs() really does pipe, so the
    reason for not reusing it is still true.
 3. preflight() refuses a missing entry point, and restart_gui() then closes nothing
    and launches nothing.
 4. A CANCELLED close (dirty session, prompt answered No) launches nothing, leaves
    the window open, and says so in the user log.
 5. A clean close launches exactly one detached child with the argv from check 1 —
    and does so only after the window closed, with the autosave file removed so the
    new instance does not offer to recover the session just left.
 6. restart_gui() contains no prompt of its own (the unsaved-work question stays in
    handle_close_event).
 7. The button is in the persistent tab row, present in every stage mode, and its
    tooltip states both halves (this window closes, a new one opens).
 8. At the narrowest supported window nothing in the tab row is squeezed below its
    own size hint.

Run:  python3 tools/PreProcessor/tests/test_gui_restart.py
"""
import os
import subprocess
import sys
import threading

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
    print("FAIL watchdog: blocked >90s (an unguarded modal?)", flush=True)
    os._exit(99)


_wd = threading.Timer(90, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.services import gui_restart  # noqa: E402
from app.services import user_log  # noqa: E402
from app.services.paths import repo_root  # noqa: E402
from app.workers.proc_util import popen_kwargs  # noqa: E402

# ── 1. argv: this interpreter, the resolved entry point, nothing else ──────
argv, kwargs = gui_restart.restart_command()
expect_entry = os.path.join(repo_root(), "tools", "PreProcessor", "gui", "main.py")
check(argv == [sys.executable, expect_entry],
      f"1a. argv is [interpreter, <repo_root>/tools/PreProcessor/gui/main.py] ({argv})")
check(len(argv) == 2,
      f"1b. no arguments travel to the new session ({argv[2:]})")
check(os.path.isfile(expect_entry),
      f"1c. the resolved entry point exists ({expect_entry})")
# repo_root() rather than a counted path: the entry must sit INSIDE the repo.
check(os.path.abspath(expect_entry).startswith(os.path.abspath(repo_root()) + os.sep),
      "1d. the entry point resolves inside the repo root, not beside it")

# ── 2. kwargs: detached, DEVNULL, and definitely not the worker bundle ─────
check(kwargs.get("start_new_session") is True,
      "2a. start_new_session=True, so the child outlives this process")
check(kwargs.get("cwd") == repo_root(),
      f"2b. cwd is the repo root ({kwargs.get('cwd')})")
check(all(kwargs.get(k) == subprocess.DEVNULL
          for k in ("stdin", "stdout", "stderr")),
      "2c. stdin/stdout/stderr are all DEVNULL")
check(subprocess.PIPE not in kwargs.values(),
      f"2d. nothing is a PIPE ({kwargs})")
# Negative control: the reason for not reusing popen_kwargs() must still hold.
_wk = popen_kwargs()
check(_wk.get("stdout") == subprocess.PIPE
      and _wk.get("stderr") == subprocess.STDOUT,
      "2e. popen_kwargs() DOES pipe - stdout, with stderr folded into it - so "
      "'do not reuse that bundle here' is still true")

# ── 3. preflight refuses a missing entry point, before anything closes ─────
_real_entry = gui_restart.entry_script
gui_restart.entry_script = lambda: os.path.join(repo_root(), "no", "such", "main.py")
try:
    reason = gui_restart.preflight()
    check(bool(reason) and "main.py" in reason,
          f"3a. preflight names a missing entry point ({reason[:60]!r})")
finally:
    gui_restart.entry_script = _real_entry
check(gui_restart.preflight() == "",
      "3b. preflight passes on this installation")

from app.controller import AppController  # noqa: E402

_launched = []
_real_launch = gui_restart.launch
gui_restart.launch = lambda: _launched.append("launched")

c_pf = AppController()
_closes = []
_pf_close = c_pf.main_window.close
c_pf.main_window.close = lambda: (_closes.append(1), _pf_close())[1]
gui_restart.entry_script = lambda: os.path.join(repo_root(), "no", "such", "main.py")
try:
    ok = c_pf.restart_gui()
finally:
    gui_restart.entry_script = _real_entry
check(ok is False and not _launched,
      f"3c. a failed preflight launches nothing (ok={ok}, launched={_launched})")
check(not _closes,
      "3d. and closes nothing either - the check happens while there is still "
      "a window to report it in")

# ── 4. a cancelled close launches nothing and says so ─────────────────────
_lines = []
user_log.add_sink(_lines.append)

c_no = AppController()
c_no.sessions[0].is_geometry_modified = True
_asked = []
import app.utils as _utils  # noqa: E402
_real_confirm = _utils.confirm
_utils.confirm = lambda *a, **k: (_asked.append(1), False)[1]   # "No, do not discard"
try:
    ok = c_no.restart_gui()
finally:
    _utils.confirm = _real_confirm
check(ok is False, f"4a. restart_gui reports the cancellation (ok={ok})")
check(not _launched, f"4b. a cancelled close launches nothing ({_launched})")
check(len(_asked) == 1,
      f"4c. the unsaved-work question was asked exactly once ({len(_asked)})")
# The outcome came from close()'s return value. isVisible() cannot tell these
# apart on a window that was never shown, which is what makes this the check:
_utils.confirm = lambda *a, **k: False
try:
    still_open = c_no.main_window.close() is False
finally:
    _utils.confirm = _real_confirm
check(still_open,
      "4d. the window is still there - it refuses the close again, which is a "
      "state isVisible() cannot report on a never-shown window")
check(any("cancel" in ln.lower() for ln in _lines),
      f"4e. the log says the restart was cancelled ({[ln for ln in _lines][-2:]})")

# ── 5. a clean close launches exactly one detached child, after the close ──
_spawned = []
_order = []


class _FakeProc:
    pid = 4242


def _spy_popen(a, **kw):
    _spawned.append((list(a), dict(kw)))
    _order.append("spawn")
    return _FakeProc()


gui_restart.launch = _real_launch            # exercise the real launch()
_real_popen = subprocess.Popen
subprocess.Popen = _spy_popen

c_ok = AppController()
_real_close = c_ok.main_window.close


def _watched_close():
    r = _real_close()
    _order.append("close")
    return r


c_ok.main_window.close = _watched_close
try:
    ok = c_ok.restart_gui()
finally:
    subprocess.Popen = _real_popen

check(ok is True, f"5a. a clean restart succeeds (ok={ok})")
check(len(_spawned) == 1, f"5b. exactly one child is spawned ({len(_spawned)})")
if _spawned:
    sa, skw = _spawned[0]
    check(sa == [sys.executable, expect_entry], f"5c. the spawned argv is the pinned one ({sa})")
    check(skw.get("start_new_session") is True
          and skw.get("stdout") == subprocess.DEVNULL
          and skw.get("stderr") == subprocess.DEVNULL,
          f"5d. the spawned kwargs are detached + DEVNULL ({skw})")
check(_order == ["close", "spawn"],
      f"5e. the window closes BEFORE anything is spawned ({_order})")
# Worth a check, not a change: the clean-shutdown path removes the autosave file,
# so the instance that is about to start does not offer to recover the session the
# user just chose to leave.
check(not os.path.exists(c_ok._autosave_path),
      f"5f. the autosave file is gone, so the new instance starts clean "
      f"({c_ok._autosave_path})")

# ── 6. no second copy of the unsaved-work prompt ───────────────────────────
import inspect  # noqa: E402
from app.controllers import lifecycle_ctrl  # noqa: E402

_fn = lifecycle_ctrl.LifecycleControllerMixin.restart_gui
_src = inspect.getsource(_fn)
# The docstring legitimately explains why isVisible() is the wrong signal, so
# check 6c reads the BODY only or it would fail on its own rationale. Split on
# the docstring's own delimiters: inspect.getdoc() is dedented and therefore
# does not appear verbatim in the indented source.
_body = _src.split('"""')[2] if _src.count('"""') >= 2 else _src
check("confirm(" not in _src,
      "6a. restart_gui asks nothing itself; the prompt stays in handle_close_event")
check("main_window.close()" in _src,
      "6b. it routes through MainWindow.close(), not handle_close_event directly")
check("isVisible" not in _body,
      "6c. the outcome comes from close()'s return value, not isVisible()")

# ── 7/8. the button, in every mode, and the row's width at its narrowest ──
c_ui = AppController()
mw = c_ui.main_window
btn = getattr(mw, "restart_btn", None)
check(btn is not None, "7a. MainWindow has a restart_btn")
check(btn is not None and btn.parent() is mw.tab_row,
      "7b. it lives in the persistent tab row (present in every mode)")
tip = (btn.toolTip() if btn is not None else "").lower()
check("close" in tip and "new" in tip,
      f"7c. the tooltip states both halves ({tip!r})")

mw.resize(900, 600)          # the narrowest supported window
mw.show()
app.processEvents()
missing = []
for i in range(mw.mode_combo.count()):
    mw.mode_combo.setCurrentIndex(i)
    app.processEvents()
    if btn is None or btn.isHidden():
        missing.append(i)
check(not missing, f"7d. the button is present in every stage mode (hidden in {missing})")

row_hl = mw.tab_row.layout()
squeezed = []
for i in range(row_hl.count()):
    w = row_hl.itemAt(i).widget()
    if w is None or w.isHidden():
        continue
    # What the widget asked for: its size hint, or the width it was pinned to.
    wanted = min(w.sizeHint().width(), w.maximumWidth())
    if w.width() < wanted:
        squeezed.append((w.__class__.__name__, w.width(), wanted))
check(not squeezed,
      f"8a. nothing in the tab row is squeezed at 900px ({squeezed})")
check(btn is not None and btn.sizeHint().width() <= 100,
      f"8b. the label stays short enough to leave slack "
      f"({btn.sizeHint().width() if btn else '?'}px of a {mw.tab_row.width()}px row)")

print()
if _FAILS:
    print(f"{len(_FAILS)} FAILED:")
    for f in _FAILS:
        print("  - " + f)
    sys.stdout.flush()
    os._exit(1)
print("ALL CHECKS PASSED")
# os._exit skips Qt's offscreen teardown (which crashes on a machine with no
# GPU) AND skips flushing stdout, so flush by hand or the summary vanishes.
sys.stdout.flush()
os._exit(0)
