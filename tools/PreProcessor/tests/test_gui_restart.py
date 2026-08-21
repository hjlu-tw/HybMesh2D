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
 4. A CANCELLED close (dirty session, prompt answered No) launches nothing — through
    neither launch() nor Popen — leaves the window open, and says so in the user log.
 5. A CONFIRMED close (dirty session, prompt answered Yes) runs the normal shutdown
    and then launches exactly one detached child with the argv from check 1: layout
    saved, a live worker cancelled and joined through the existing bounded
    _shutdown_workers, autosave file removed, and the spawn strictly after the close.
 6. What restart_gui must not contain, read as AST rather than as text: no prompt of
    its own, no isVisible(), no kill logic, and a real main_window.close() call.
    Every one verified by injection.
 7. The button is in the persistent tab row, present in every stage mode, its tooltip
    states both halves — and CLICKING it really runs restart_gui.
 8. At the narrowest supported window nothing in the tab row is squeezed below its
    own size hint, in any stage, and the chosen caption leaves slack where the
    rejected longer one leaves none.
 9. A launch that fails after the window has gone is still reported.

Blind spots, named rather than papered over:
  * Check 6 reads ONE function, so a prompt reached indirectly (a helper that calls
    confirm, an alias bound elsewhere) is invisible to it.
  * Nothing here spawns a real second GUI. That was verified once by hand — the child
    was reparented to init in its own session and outlived the parent — and is not
    re-run per test, so a change to the kwargs is caught by checks 2/5 but a platform
    that ignores start_new_session would not be.
  * Check 5's worker is a duck-typed fake. It proves the restart drives the existing
    join path; it does not prove a real wedged QThread is escaped within budget (the
    watchdog above is what covers "no hang").

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

from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402

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

# The issue asks for this case with ``Popen`` patched. ``launch`` is patched too
# (it is what restart_gui calls), but patching only that would be blind to a
# ``subprocess.Popen`` added straight onto the cancel path.
_cancel_popen = []
_real_popen = subprocess.Popen
subprocess.Popen = lambda a, **kw: _cancel_popen.append(a)

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
    subprocess.Popen = _real_popen
check(ok is False, f"4a. restart_gui reports the cancellation (ok={ok})")
check(not _launched and not _cancel_popen,
      f"4b. a cancelled close launches nothing - neither through launch() nor "
      f"through Popen directly ({_launched}, {_cancel_popen})")
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

# ── 5. answering YES: the normal shutdown runs, THEN one detached child ────
# This is the dirty-session Yes path, not a pristine one: the prompt is the thing
# the restart must go THROUGH, and a pristine controller never reaches it. The
# four shutdown effects the issue lists are checked individually, because "the
# window closed" says nothing about whether the layout was saved or a worker
# joined.
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
c_ok.sessions[0].is_geometry_modified = True     # so the prompt is really reached
_asked_yes = []
_utils.confirm = lambda *a, **k: (_asked_yes.append(1), True)[1]

# A live worker, so "the existing bounded _shutdown_workers path is used" is
# exercised rather than assumed. Duck-typed to what _join_worker actually asks
# for: isRunning / cancel / wait.
class _FakeWorker:
    def __init__(self):
        self.cancelled = 0
        self.waited = 0
        self._running = True

    def isRunning(self):
        return self._running

    def cancel(self):
        self.cancelled += 1
        self._running = False

    def wait(self, ms):
        self.waited += 1
        return True


_worker = _FakeWorker()
c_ok._worker = _worker

# The three shutdown effects that happen ON the close (the temp dir is a fourth,
# but it hangs off QApplication.aboutToQuit, i.e. process exit, not this call).
_saved_layout = []
from app.services import ui_state as _ui_state  # noqa: E402
_real_save = _ui_state.save_ui_state
_ui_state.save_ui_state = lambda mw: (_saved_layout.append(1), _real_save(mw))[1]
_joined = []
_real_shutdown = c_ok._shutdown_workers
c_ok._shutdown_workers = lambda: (_joined.append(1), _real_shutdown())[1]
_autosave_before = c_ok._autosave_path
open(_autosave_before, "w").write("{}")          # something to be removed

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
    _utils.confirm = _real_confirm
    _ui_state.save_ui_state = _real_save

check(ok is True, f"5a. a restart the user confirmed succeeds (ok={ok})")
check(len(_asked_yes) == 1,
      f"5a2. and it went through the unsaved-work prompt ({len(_asked_yes)})")
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
check(not os.path.exists(_autosave_before),
      f"5f. the autosave file is gone, so the new instance starts clean "
      f"({_autosave_before})")
check(len(_saved_layout) == 1,
      f"5g. the layout was saved before teardown ({len(_saved_layout)})")
check(len(_joined) == 1 and _worker.cancelled == 1 and _worker.waited >= 1,
      f"5h. the existing bounded _shutdown_workers path cancelled and joined the "
      f"live worker - no new kill logic, and the watchdog above proves no hang "
      f"(joined={_joined}, cancelled={_worker.cancelled}, waited={_worker.waited})")
check(os.path.isdir(c_ok.temp_dir),
      "5i. the temp dir is still there: cleanup_temp_dir hangs off "
      "QApplication.aboutToQuit, so it goes at process exit, not on this close")

# ── 6. what restart_gui must NOT contain, read as syntax rather than text ──
# These are source-reading checks, so they are AST-based and each one is verified
# by INJECTION below: a substring check here would be satisfied by the word
# appearing in a comment, and this repo has already shipped a gate that passed
# for exactly that reason. The docstring is dropped rather than scanned, because
# it legitimately discusses isVisible() to explain why the code does not use it.
#
# Named blind spots: these read ONE function. A prompt reached indirectly (a
# helper that calls confirm, or an alias bound elsewhere) is invisible, as is a
# close() on something other than self.main_window. They defend against the cheap
# regression, not a determined one.
import ast  # noqa: E402
import inspect  # noqa: E402
import textwrap  # noqa: E402
from app.controllers import lifecycle_ctrl  # noqa: E402

_src = textwrap.dedent(
    inspect.getsource(lifecycle_ctrl.LifecycleControllerMixin.restart_gui))


def _body_of(src: str):
    """The statements of the function in `src`, its docstring dropped."""
    fn = ast.parse(src).body[0]
    body = fn.body
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return body


def _callee_names(src: str) -> set:
    """Every name called in the body (``f()`` and ``x.f()`` alike)."""
    out = set()
    for stmt in _body_of(src):
        for n in ast.walk(stmt):
            if isinstance(n, ast.Call):
                f = n.func
                out.add(f.attr if isinstance(f, ast.Attribute)
                        else getattr(f, "id", ""))
    return out


def _referenced(src: str) -> set:
    """Every name or attribute referenced in the body."""
    out = set()
    for stmt in _body_of(src):
        for n in ast.walk(stmt):
            if isinstance(n, ast.Attribute):
                out.add(n.attr)
            elif isinstance(n, ast.Name):
                out.add(n.id)
    return out


def _closes_main_window(src: str) -> bool:
    """True iff the body really calls ``<something>.main_window.close()``."""
    for stmt in _body_of(src):
        for n in ast.walk(stmt):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "close"
                    and isinstance(n.func.value, ast.Attribute)
                    and n.func.value.attr == "main_window"):
                return True
    return False


_KILL = {"kill_process", "terminate", "kill", "_join_worker"}
check("confirm" not in _callee_names(_src),
      "6a. restart_gui asks nothing itself; the prompt stays in handle_close_event")
check(_closes_main_window(_src),
      "6b. it really calls main_window.close(), not handle_close_event directly")
check(not ({"isVisible", "isHidden"} & _referenced(_src)),
      "6c. the outcome comes from close()'s return value, not from isVisible()")
check(not (_KILL & _callee_names(_src)),
      f"6d. it adds no kill logic of its own; shutdown stays with "
      f"_shutdown_workers ({_KILL & _callee_names(_src)})")


def _inject(src: str, stmt: str) -> str:
    """Insert `stmt` as the function's first statement after the docstring."""
    lines = src.splitlines(True)
    end = next(i for i, ln in enumerate(lines)
               if i > 0 and ln.strip().endswith('"""'))
    return "".join(lines[:end + 1] + ["    " + stmt + "\n"] + lines[end + 1:])


_inj = [("6a", _inject(_src, 'confirm(self.main_window, "t", "q")'),
         lambda m: "confirm" in _callee_names(m)),
        ("6c", _inject(_src, "if self.main_window.isVisible():\n        pass"),
         lambda m: bool({"isVisible"} & _referenced(m))),
        ("6d", _inject(_src, "kill_process(None)"),
         lambda m: bool(_KILL & _callee_names(m))),
        ("6b", _src.replace("self.main_window.close()", "True"),
         lambda m: not _closes_main_window(m))]
for _tag, _mut, _pred in _inj:
    # A mutation that fails to parse looks exactly like the check working, so the
    # predicate parses it (via _body_of) and would raise here if it did not.
    _caught = _pred(_mut)
    check(_mut != _src and _caught,
          f"6e. injection: a violation of {_tag} is caught "
          f"(source changed={_mut != _src}, caught={_caught})")

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

# 7e. The one line joining the button to the feature. Without this the two
# `clicked.connect` lines in signal_wiring_ctrl could be deleted and every other
# property here would still pass. Driven through preflight rather than by patching
# restart_gui: the connection was made to the ORIGINAL bound method, so replacing
# the attribute now would not intercept it. A refused preflight makes the click
# observable and closes nothing.
_reached = []
_pf = gui_restart.preflight
gui_restart.preflight = lambda: (_reached.append(1), "not now")[1]
try:
    btn.click()
    app.processEvents()
finally:
    gui_restart.preflight = _pf
check(len(_reached) == 1,
      f"7e. clicking the button really runs restart_gui ({len(_reached)} calls)")

row_hl = mw.tab_row.layout()


def _row_need(caption_w: int) -> int:
    """Width the tab row needs AS IT IS NOW, with Restart taken as `caption_w`.

    Sums what every visible widget asked for — its size hint, or the width it was
    pinned to (mode_combo is setFixedWidth 2px under its own hint, deliberately).
    """
    need = row_hl.contentsMargins().left() + row_hl.contentsMargins().right()
    for k in range(row_hl.count()):
        w = row_hl.itemAt(k).widget()
        if w is None or w.isHidden():
            continue
        need += caption_w if w is btn else min(w.sizeHint().width(),
                                               w.maximumWidth())
    return need


# The tightest mode, not whichever one happened to be left showing: a tab bar is
# visible in some stages and hidden in others, and a hidden one contributes
# nothing — measuring in an IB-stage window reported 171px of slack where the CAD
# stage has 31. Squeezing is checked per mode for the same reason.
_slack = {}
_alt_slack = {}
_squeezed = []
_alt = QPushButton("⟳ New Session", mw.tab_row)   # the caption that was rejected
_alt.setStyleSheet(btn.styleSheet())
_alt_w = _alt.sizeHint().width()
_alt.setParent(None)
_chosen_w = btn.sizeHint().width()
for i in range(mw.mode_combo.count()):
    mw.mode_combo.setCurrentIndex(i)
    app.processEvents()
    _slack[i] = mw.tab_row.width() - _row_need(_chosen_w)
    _alt_slack[i] = mw.tab_row.width() - _row_need(_alt_w)
    for k in range(row_hl.count()):
        w = row_hl.itemAt(k).widget()
        if w is None or w.isHidden():
            continue
        wanted = min(w.sizeHint().width(), w.maximumWidth())
        if w.width() < wanted:
            _squeezed.append((i, w.__class__.__name__, w.width(), wanted))
check(not _squeezed,
      f"8a. nothing in the tab row is squeezed, in any stage, at the 900px "
      f"minimum window ({_squeezed})")
check(min(_slack.values()) > 0,
      f"8b. the chosen caption leaves the row slack in every stage "
      f"({_chosen_w}px caption; worst stage {min(_slack, key=_slack.get)} has "
      f"{min(_slack.values())}px spare in a {mw.tab_row.width()}px row)")
check(_alt_w > _chosen_w and min(_alt_slack.values()) <= 0,
      f"8c. and it was the caption LENGTH that decided it: '⟳ New Session' "
      f"({_alt_w}px) leaves {min(_alt_slack.values())}px in the worst stage")

# ── 9. a launch that fails AFTER the close is still said out loud ─────────
# The issue's item 6 names this case ("a launch failure after the window has
# closed is otherwise invisible"). preflight() catches the foreseeable causes
# while a dialog still works; anything left cannot reach a modal — there is no
# parent window and the app is already quitting — so the requirement it can still
# meet is that the failure is REPORTED, through user_log's own file mirror. That
# is what this pins; a dialog for it is deliberately not attempted.
c_boom = AppController()
_boom_lines = []
user_log.add_sink(_boom_lines.append)
_real_popen = subprocess.Popen


def _raising_popen(a, **kw):
    raise OSError(12, "Cannot allocate memory")


subprocess.Popen = _raising_popen
try:
    ok = c_boom.restart_gui()
finally:
    subprocess.Popen = _real_popen
    user_log.remove_sink(_boom_lines.append)
check(ok is False, f"9a. a failed launch is reported as a failure (ok={ok})")
check(any("could not start the new session" in ln.lower() for ln in _boom_lines),
      f"9b. and it is said out loud, not swallowed ({_boom_lines[-2:]})")

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
