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
 7. A geometry file that EXISTS and cannot be read is named, with its
    exception, by all FOUR readers that open one (#117).
 8. ...while a geometry file that is simply ABSENT still produces no record.

Checks 7-8 are proved non-vacuous by five injections, the verdict read from the
EXIT CODE and with a negative control on the unmutated tree (this repo has
scored a crashed injection as a bite that never happened):

  * the BC overlay reverted to ``except Exception: continue``   -> check 7 red
  * the selection highlight reverted to ``except Exception: return`` -> 7 red
  * the bbox scan's fallback reverted to ``except OSError: pass``     -> 7 red
  * the loader thread's print replaced by ``pass``                    -> 7 red
  * the BC overlay made to log the ABSENT case as well               -> 8 red

Run:  python3 tools/PreProcessor/tests/test_silent_exceptions.py
"""
import logging
import os
import re
import shutil
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

# ── 7. a geometry that EXISTS and cannot be READ reaches the log ──────────
# #117. Until #112 the broad `except` around np.loadtxt in these readers WAS
# the existence answer, so discarding it was correct: a missing geometry is not
# an error. #112 moved existence out into readable_geom_path, so everything that
# still reaches those handlers is a GENUINE read failure on a file that is
# there -- and both of them discarded it without a word. Driven against a real
# unreadable file rather than by reading the code: the point is what the user
# can find in results/logs/gui.log afterwards.
from app.models.mesh_config import MeshConfig  # noqa: E402

_geo = tempfile.mkdtemp(prefix="hybmesh_geomtest_")
unreadable = os.path.join(_geo, "unreadable.dat")
with open(unreadable, "w", encoding="utf-8") as _f:
    _f.write("0 0\n1 0\n1 1\n")
os.chmod(unreadable, 0o000)
try:
    open(unreadable, encoding="utf-8").close()
    # Running as a user who can read anything (root in a container): fall back to
    # the other failure the ticket names -- a directory where a file should be.
    os.chmod(unreadable, 0o600)
    os.remove(unreadable)
    os.mkdir(unreadable)
    _kind = "a directory where a file should be"
except OSError:
    _kind = "a chmod-000 file"
check(os.path.exists(unreadable),
      f"7. the fixture EXISTS ({_kind}) -- readable_geom_path answers it")

bad_cfg = MeshConfig()
bad_cfg.add_geom_file(unreadable)
check(bool(bad_cfg.geom_files), "7. the fixture is in the mesh config")

mcv.mesh_config = bad_cfg
mcv.show_bc_coloring = True
mcv.geom_bc_items = []          # nothing to remove (removeItem is stubbed above)
mcv._sel_highlight_item = None

before = len(read_log())
mcv._rebuild_geom_bc_preview()
bc_log = read_log()[before:]
check("unreadable.dat" in bc_log and "BC overlay" in bc_log,
      "7. the BC overlay names the unreadable geometry in the log")
check("hybmesh.gui.views.mesh_canvas_bc_mixin" in bc_log
      and "Traceback" in bc_log,
      "7. ...from its own module, with the exception (exc_info=True)")

before = len(read_log())
mcv.highlight_geometry_file(unreadable)
hi_log = read_log()[before:]
check("unreadable.dat" in hi_log and "selection highlight" in hi_log,
      "7. the selection highlight names the unreadable geometry in the log")
check("hybmesh.gui.views.mesh_canvas_geom_mixin" in hi_log
      and "Traceback" in hi_log,
      "7. ...from its own module, with the exception (exc_info=True)")

# The third opener of the same entry: the bbox scan's fallback read fails too,
# and its `except OSError: pass` used to end the story there.
before = len(read_log())
ctl._scan_geometry_files(bad_cfg)
bb_log = read_log()[before:]
check("unreadable.dat" in bb_log and "bbox scan" in bb_log
      and "hybmesh.gui.controllers.mesh_gen_ctrl" in bb_log,
      "7. the mesh bbox scan names it too (the third caller that OPENS)")

# The FOURTH opener records to stdout rather than to the log file, beside its
# own malformed-geometry line. Measured here rather than asserted from the
# code, because "we looked and it names the file" is exactly the evidence this
# ticket exists to replace. run() is called directly: it is an ordinary method,
# and the point is what it writes, not which thread wrote it.
import contextlib  # noqa: E402
import io as _io  # noqa: E402

from app.views.mesh_canvas_loader import GeomLoaderThread  # noqa: E402

from app.services.geometry_service import load_points_dat  # noqa: E402

try:
    load_points_dat(unreadable)
    _exc_text = ""
except Exception as _e:               # the exception the thread has to report
    _exc_text = str(_e)

_buf = _io.StringIO()
with contextlib.redirect_stdout(_buf):
    GeomLoaderThread([unreadable]).run()
loader_out = _buf.getvalue()
# The head only: the OS embeds a path in the message, and the thread reports
# the CANONICAL one (/private/var/... on macOS) while our own call used the
# spelling tempfile handed us. What is measured is that the exception reaches
# stdout at all, not that two spellings of one path match.
_exc_head = _exc_text.split(": ")[0]         # e.g. "[Errno 13] Permission denied"
check(bool(_exc_head), "7. the fixture really does fail the loader")
check("unreadable.dat" in loader_out and _exc_head in loader_out,
      f"7. the preview loader thread names it and the exception ({_exc_head}), "
      f"on stdout")

# ── 8. a geometry that is simply ABSENT stays silent ──────────────────────
# The change must DISTINGUISH the two cases, not make both noisy: a file the
# user has not made yet is answered by readable_geom_path and never reaches an
# open, so there is nothing to record.
absent = os.path.join(_geo, "not_made_yet.dat")
check(not os.path.exists(absent), "8. the absent fixture really is absent")
gone_cfg = MeshConfig()
gone_cfg.add_geom_file(absent)
mcv.mesh_config = gone_cfg
mcv.geom_bc_items = []
mcv._sel_highlight_item = None

before = len(read_log())
_buf = _io.StringIO()
with contextlib.redirect_stdout(_buf):
    mcv._rebuild_geom_bc_preview()
    mcv.highlight_geometry_file(absent)
    ctl._scan_geometry_files(gone_cfg)
    GeomLoaderThread([absent]).run()
check(len(read_log()) == before and _buf.getvalue().strip() == "",
      "8. an absent geometry produces no record from any of the four")

# The fixture is chmod-000 (or a directory): leave nothing undeletable behind.
if os.path.isfile(unreadable):
    os.chmod(unreadable, 0o600)
shutil.rmtree(_geo, ignore_errors=True)
check(not os.path.exists(_geo), "8. the fixture directory is cleaned up")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
