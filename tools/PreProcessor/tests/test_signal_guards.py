#!/usr/bin/env python3
"""Regression tests for finding N8 — signal-suppression guards that could leak.

The GUI suppresses change signals while writing widgets from the model, so a
programmatic write is not fed back as if the user had typed it. Two mechanisms do
that, and both used to be written in a way that leaks:

* **43 raw ``blockSignals(True) … blockSignals(False)`` pairs with no
  try/finally.** An exception between the halves left the widget *permanently
  unable to emit* — silently dead for the rest of the session, with no traceback
  to explain it, because the unblock line simply never ran. They now all go
  through ``app.utils.block_signals`` (a context manager), so the unblock is
  guaranteed.

* **``_is_populating`` as a bare bool.** The four set sites already had
  try/finally (so they did not leak), but a bool cannot nest: an inner populate's
  exit re-enabled every handler while the outer one was still writing widgets. It
  is now a depth counter written only through ``controller.populating()``.

The checks are deliberately mostly *static*: these are whole-class-of-bug
problems, and the point is that a new occurrence fails the build rather than
waiting to be noticed in the field.

Checks:
 1. No unguarded / unmatched ``blockSignals(True)`` anywhere under app/.
 2. ``block_signals`` really restores state, including when the body raises.
 3. ``_is_populating`` is never assigned directly — only via ``populating()``.
 4. ``populating()`` nests correctly and is exception-safe.
 5. The guard actually suppresses: selecting an edge (a heavy populate) does not
    feed the programmatic widget writes back into the model.

Run:  python3 tools/PreProcessor/tests/test_signal_guards.py
"""
import os
import re
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_APP = os.path.join(_GUI, "app")
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >90s", flush=True)
    os._exit(99)


_wd = threading.Timer(90, _watchdog)
_wd.daemon = True
_wd.start()


def py_files():
    for root, _dirs, files in os.walk(_APP):
        for fn in sorted(files):
            if fn.endswith(".py"):
                yield os.path.join(root, fn)


# ── 1. no unguarded blockSignals pairs ────────────────────────────────────
# app/utils.py is the helper's own implementation — the only legitimate place for
# a raw blockSignals call, and it already wraps the body in try/finally.
HELPER = os.path.join(_APP, "utils.py")
offenders = []
for path in py_files():
    if path == HELPER:
        continue
    lines = open(path, encoding="utf-8").read().splitlines()
    for i, line in enumerate(lines):
        m = re.search(r"(\S+)\.blockSignals\(True\)", line)
        if not m:
            continue
        target = m.group(1)
        close = None
        for j in range(i + 1, min(i + 70, len(lines))):
            if re.search(re.escape(target) + r"\.blockSignals\(False\)", lines[j]):
                close = j
                break
        rel = os.path.relpath(path, _GUI)
        if close is None:
            offenders.append(f"{rel}:{i + 1} (never unblocked)")
            continue
        body = lines[i + 1:close]
        if not any(re.match(r"\s*(try:|finally:)\s*$", b) for b in body):
            offenders.append(f"{rel}:{i + 1} (no try/finally)")
check(not offenders,
      f"1. every blockSignals pair is exception-safe ({len(offenders)} offenders)"
      + (f": {offenders[:5]}" if offenders else ""))

# The conversion should have left the codebase using the helper widely; if this
# drops to ~0 someone has reverted the pattern wholesale.
with_count = sum(1 for p in py_files()
                 for ln in open(p, encoding="utf-8") if "with block_signals(" in ln)
check(with_count >= 40,
      f"1. the block_signals context manager is the prevailing idiom ({with_count} sites)")

# ── 2. block_signals restores state, even on an exception ─────────────────
from PyQt6.QtWidgets import QApplication, QCheckBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from app.utils import block_signals  # noqa: E402

box = QCheckBox()
check(not box.signalsBlocked(), "2. a fresh widget is not blocked")
with block_signals(box):
    check(box.signalsBlocked(), "2. inside the block it is blocked")
check(not box.signalsBlocked(), "2. and unblocked on normal exit")

try:
    with block_signals(box):
        raise RuntimeError("boom")
except RuntimeError:
    pass
check(not box.signalsBlocked(),
      "2. ...and unblocked even when the body raises (the whole point)")

# None entries must be tolerated (call sites pass optional widgets).
with block_signals(box, None):
    pass
check(not box.signalsBlocked(), "2. a None widget in the list is tolerated")

# ── 3. _is_populating is never assigned directly ──────────────────────────
assigns = []
for path in py_files():
    for i, line in enumerate(open(path, encoding="utf-8").read().splitlines()):
        if re.search(r"self\._is_populating\s*=", line):
            assigns.append(f"{os.path.relpath(path, _GUI)}:{i + 1}")
check(not assigns,
      "3. _is_populating is read-only; population goes through populating()"
      + (f" (assigned at: {assigns})" if assigns else ""))

# ── 4. populating() nests and is exception-safe ───────────────────────────
from app.controller import AppController  # noqa: E402

ctl = AppController()
check(not ctl._is_populating, "4. not populating by default")
with ctl.populating():
    check(ctl._is_populating, "4. inside the guard")
    with ctl.populating():
        check(ctl._is_populating, "4. ...and inside a nested guard")
    check(ctl._is_populating,
          "4. the INNER exit must not clear the outer guard (bool could not do this)")
check(not ctl._is_populating, "4. cleared after the outer exit")

try:
    with ctl.populating():
        raise RuntimeError("boom")
except RuntimeError:
    pass
check(not ctl._is_populating, "4. cleared even when the body raises")

# ── 5. the guard actually suppresses model write-back ─────────────────────
GEOM = os.path.join(_REPO, "examples", "geometries", "naca0012.dat")
if not os.path.exists(GEOM):
    print("SKIP naca0012.dat missing — write-back check skipped", flush=True)
else:
    ctl.load_geometry_from_path(GEOM)
    session = ctl.active_session()
    if not session.project_model.segments:
        session.split_indices = ctl._auto_detect_features(session.original_points)
        ctl._sync_file_segments(session)
    check(bool(session.project_model.segments), "5. the geometry has edges to select")

    # Selecting an edge populates the whole sidebar from the model. If the guard
    # leaked, those programmatic widget writes would come back as user edits and
    # dirty the session (and push undo steps).
    session.is_geometry_modified = False
    depth_before = len(session.command_history._undo_stack)
    session.current_segment_idx = 0
    ctl._refresh_segment_list(clear_resampled=False)
    check(len(session.command_history._undo_stack) == depth_before,
          "5. populating the sidebar records no undo command")
    check(not session.is_geometry_modified,
          "5. ...and does not mark the geometry modified")
    check(not ctl._is_populating,
          "5. ...and leaves the guard cleared afterwards")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
