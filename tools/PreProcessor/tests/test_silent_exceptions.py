#!/usr/bin/env python3
"""Regression tests for finding N7 — silently swallowed exceptions.

The defect: 36 handlers across the GUI were ``except Exception: pass``. The app
already configures a rotating log file and an uncaught-exception hook
(``services/logging_setup.py``), but none of these sites used it, so when a
canvas overlay, a snap callback, a probe overlay or the CAD-to-pipeline-script
sync failed in the field, the log contained *nothing at all* — the behaviour just
quietly degraded. They now log at:

  * ``debug``   — genuinely best-effort (cursor changes, teardown/removeItem);
                  nothing the user asked for is lost.
  * ``warning`` — a failure silently degrades requested behaviour (an unsnapped
                  point, missing iso-lines, a saved pipeline script that does not
                  match the canvas, an export under the wrong name).

Checks:
 1. get_logger() returns a ``hybmesh.gui.<module>`` child, usable before setup.
 2. No new ``except Exception: pass`` — only the documented allowlist, which is
    limited to logging's own write path (logging a logging failure recurses) and
    the escalation thread's terminal catch.
 3. A converted warning site really writes a record *with a traceback*.
 4. A converted debug site records at DEBUG and is dropped at INFO.
 5. HYBMESH_LOG_LEVEL raises the level so best-effort diagnostics are reachable.
 6. Log records carry the module name, so a message can be traced to its site.

Run:  python3 tools/PreProcessor/tests/test_silent_exceptions.py
"""
import logging
import os
import re
import sys
import tempfile
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
    print("FAIL watchdog: blocked >60s", flush=True)
    os._exit(99)


_wd = threading.Timer(60, _watchdog)
_wd.daemon = True
_wd.start()

# ── 1. get_logger ─────────────────────────────────────────────────────────
from app.services.logging_setup import LOGGER_NAME, get_logger  # noqa: E402

lg = get_logger("app.controllers.demo_ctrl")
check(lg.name == f"{LOGGER_NAME}.controllers.demo_ctrl",
      f"1. get_logger names the child after the module (got {lg.name!r})")
check(get_logger(None).name == LOGGER_NAME,
      "1. get_logger(None) returns the root GUI logger")
# Usable at import time, before configure_logging() has run.
lg.debug("harmless")
check(True, "1. logging before configure_logging() does not raise")

# ── 2. no new silent handlers ─────────────────────────────────────────────
# Each entry is silent ON PURPOSE; the reason must be in a comment at the site.
ALLOWED_SILENT = {
    # Moved out of app/views/log_panel.py when the user-facing log grew a seam:
    # the file mirror belongs to the service, so the widget no longer writes it.
    ("app/services/user_log.py", "this IS the write-to-log-file path"),
    ("app/services/logging_setup.py", "logging setup / excepthook"),
    ("app/workers/proc_util.py", "escalation thread terminal catch"),
}
ALLOWED_FILES = {f for f, _ in ALLOWED_SILENT}

_EXCEPT_RE = re.compile(r"^\s*except\s+Exception(\s+as\s+\w+)?\s*:\s*$")
offenders = []
for root, _dirs, files in os.walk(_APP):
    for fn in sorted(files):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(root, fn)
        rel = os.path.relpath(path, _GUI)
        lines = open(path, encoding="utf-8").read().splitlines()
        for i, line in enumerate(lines):
            if not _EXCEPT_RE.match(line):
                continue
            indent = len(line) - len(line.lstrip())
            body = []
            for j in range(i + 1, min(i + 8, len(lines))):
                s = lines[j].strip()
                if not s or s.startswith("#"):
                    continue
                if len(lines[j]) - len(lines[j].lstrip()) <= indent:
                    break
                body.append(s)
            if body == ["pass"] and rel not in ALLOWED_FILES:
                offenders.append(f"{rel}:{i + 1}")
check(not offenders,
      f"2. no undocumented `except Exception: pass` ({len(offenders)} found)"
      + (f": {offenders[:6]}" if offenders else ""))

# Every allowlisted silent site must still carry an explanatory comment.
undocumented = []
for rel in sorted(ALLOWED_FILES):
    lines = open(os.path.join(_GUI, rel), encoding="utf-8").read().splitlines()
    for i, line in enumerate(lines):
        if not _EXCEPT_RE.match(line):
            continue
        nxt = [s.strip() for s in lines[i + 1:i + 5] if s.strip()]
        if nxt and nxt[0] == "pass":
            undocumented.append(f"{rel}:{i + 1}")
check(not undocumented,
      "2. every intentionally-silent handler explains itself in a comment"
      + (f" (bare: {undocumented})" if undocumented else ""))

# ── 3-6. the handlers really log ──────────────────────────────────────────
import app.services.logging_setup as ls  # noqa: E402

tmpdir = tempfile.mkdtemp(prefix="hybmesh_logtest_")
ls._log_dir = lambda: tmpdir
os.environ["HYBMESH_LOG_LEVEL"] = "DEBUG"
root_logger = ls.configure_logging()
check(root_logger.level == logging.DEBUG,
      "5. HYBMESH_LOG_LEVEL=DEBUG raises the effective level")

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402

ctl = AppController()
logfile = os.path.join(tmpdir, "gui.log")


def read_log() -> str:
    for h in root_logger.handlers:
        h.flush()
    return open(logfile, encoding="utf-8").read() if os.path.exists(logfile) else ""


# 3. warning site: the live output-name read fails -> export would use a
#    different name than the user typed, so this must never be silent.
def _boom(*_a, **_k):
    raise RuntimeError("panel exploded")


ctl.main_window.mesh_config_panel.get_config = _boom
ctl.global_mesh_config.output_filename = "fallback_name.vtk"
name = ctl._current_output_filename()
log = read_log()
check(name == "fallback_name.vtk", "3. the warning path still falls back correctly")
check("could not read the live output name" in log,
      "3. ...and records a WARNING instead of swallowing it")
check("panel exploded" in log and "Traceback" in log,
      "3. ...with the full traceback (exc_info=True)")

# 4/6. debug site: a teardown removeItem() that raises.
mcv = ctl.main_window.mesh_canvas_view
mcv._error_highlight_items = ["not-an-item"]
mcv.plot_widget.removeItem = lambda _item: (_ for _ in ()).throw(
    RuntimeError("removeItem refused"))
mcv.clear_error_highlights()
log = read_log()
check("could not remove an error-highlight item" in log
      and "removeItem refused" in log,
      "4. a best-effort teardown failure is recorded at DEBUG")
check("hybmesh.gui.views.mesh_canvas_geom_mixin" in log,
      "6. records carry the module name of the failing site")

# 4b. At INFO those DEBUG diagnostics are dropped again (no log spam by default).
root_logger.setLevel(logging.INFO)
before = len(read_log())
mcv._error_highlight_items = ["not-an-item"]
mcv.clear_error_highlights()
check(len(read_log()) == before,
      "4. ...and is dropped at the default INFO level (no routine spam)")

os.environ.pop("HYBMESH_LOG_LEVEL", None)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
