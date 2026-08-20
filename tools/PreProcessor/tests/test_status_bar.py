#!/usr/bin/env python3
"""Persistent status bar (finding N10).

The window had no status bar, so three things had nowhere to live: which workflow
stage is active (only the combo said so), how much is selected (nothing said so at
all), and what background work is running — the toolbar progress bar showed a moving
bar but never *what* was moving.

Two deliberate omissions are asserted here so they are not "fixed" by mistake:

* **No cursor coordinates.** All three canvases already carry a ``coord_label`` that
  floats next to the pointer, which is more useful than a fixed read-out and was
  specifically fixed to clear on leave. Two coordinate read-outs that can disagree
  are worse than one.
* **No units field.** There is no unit system yet, and a field that always says the
  same thing teaches people to stop reading the bar.

Checks:
 1. The status bar exists with the three permanent fields.
 2. Stage follows mode_changed, using short names (the combo's labels are too long).
 3. Activity is driven by the EXISTING progress-ownership methods, so every current
    and future claim/set/release call site is covered without touching it — and the
    ownership guard is respected: a non-owner cannot relabel the bar.
 4. An unknown progress owner is shown as-is rather than blank, so a new call site
    is visible instead of silently missing.
 5. Selection reports edges, a vertex, and always which layer they belong to
    (with several geometries open, "2 edges" alone is ambiguous).
 6. A transient flash_status() message does not erase the permanent fields.
 7. refresh_status_selection is separate from get_selected_segment_indices, which
    is a pure query on hot paths and must stay side-effect free.

Run:  python3 tools/PreProcessor/tests/test_status_bar.py
"""
import inspect
import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
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

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.controller import AppController  # noqa: E402
from app.views import main_window_statusbar_mixin as sbm  # noqa: E402

ctl = AppController()
mw = ctl.main_window

# ── 1. the bar and its fields ─────────────────────────────────────────────
check(mw.statusBar() is not None, "1. the window has a status bar")
for name in ("status_stage", "status_selection", "status_activity"):
    check(hasattr(mw, name), f"1. {name} exists")
check(mw.status_stage.text().startswith("Stage:"), "1. stage field is labelled")
check(mw.status_selection.text() == "Selection: —",
      "1. selection starts as a dash, not an invented '0'")
check(mw.status_activity.text() == "", "1. activity is blank when idle")

labels = " ".join(w.text() for w in
                  (mw.status_stage, mw.status_selection, mw.status_activity))
check("X:" not in labels and "Y:" not in labels,
      "1. no coordinate read-out (the canvases' floating labels own that)")
check(not hasattr(mw, "status_units"),
      "1. no units field while there is no unit system to report")

# ── 2. stage follows the mode ─────────────────────────────────────────────
for idx, want in ((1, "Mesh"), (3, "Solver"), (5, "Immersed Solid"), (0, "CAD")):
    mw.mode_combo.setCurrentIndex(idx)
    check(mw.status_stage.text() == f"Stage: {want}",
          f"2. stage {idx} reads {want!r} (got {mw.status_stage.text()!r})")
check(all(len(n) <= 14 for n in sbm._STAGE_NAMES),
      "2. stage names are short enough for a status field")

# ── 3/4. activity from the progress-ownership methods ─────────────────────
mw.claim_progress("mesh", determinate=True)
check("Generating mesh" in mw.status_activity.text(),
      f"3. claim_progress names the work ({mw.status_activity.text()!r})")
mw.set_progress("mesh", 61)
check("61%" in mw.status_activity.text(), "3. set_progress shows the percentage")

before = mw.status_activity.text()
mw.set_progress("solver", 99)
check(mw.status_activity.text() == before,
      "3. a NON-OWNER cannot relabel the bar (ownership guard respected)")
mw.release_progress("solver")
check(mw.status_activity.text() == before, "3. ...nor clear it")
mw.release_progress("mesh")
check(mw.status_activity.text() == "", "3. the owner's release clears it")

mw.claim_progress("some_new_stage")
check("some_new_stage" in mw.status_activity.text(),
      "4. an unknown owner is shown as-is, not silently blank")
mw.release_progress("some_new_stage")

# The wiring must live in the ownership methods, not be duplicated per call site.
from app.views import main_window_toolbar_build_mixin as tb  # noqa: E402

tb_src = inspect.getsource(tb)
check(tb_src.count("set_status_activity") == 3,
      f"3. exactly the three ownership methods drive the field "
      f"({tb_src.count('set_status_activity')} call sites)")

# ── 5/6. selection + transient message ────────────────────────────────────
geom = os.path.join(_REPO, "examples", "geometries", "naca0012.dat")
if not os.path.exists(geom):
    print("SKIP naca0012.dat missing — selection checks skipped", flush=True)
else:
    ctl.load_geometry_from_path(geom)
    session = ctl.active_session()
    if not session.project_model.segments:
        session.split_indices = ctl._auto_detect_features(session.original_points)
        ctl._sync_file_segments(session)

    session.current_segment_idx = 0
    session.selected_point_idx = None
    ctl.refresh_status_selection()
    txt = mw.status_selection.text()
    check("1 edge" in txt and "naca0012.dat" in txt,
          f"5. one edge is reported WITH its layer ({txt!r})")

    session.selected_point_idx = 7
    ctl.refresh_status_selection()
    check("vertex 7" in mw.status_selection.text(),
          f"5. a selected vertex is reported ({mw.status_selection.text()!r})")

    session.current_segment_idx = -1
    session.selected_point_idx = None
    ctl.refresh_status_selection()
    check(mw.status_selection.text() == "Selection: —",
          f"5. nothing selected reads as a dash ({mw.status_selection.text()!r})")

    stage_before = mw.status_stage.text()
    mw.flash_status("Undo (Update Params)")
    check(mw.statusBar().currentMessage() == "Undo (Update Params)",
          "6. flash_status shows a transient message")
    check(mw.status_stage.text() == stage_before,
          "6. ...without erasing the permanent stage field")

# ── 7. the pure query stayed pure ─────────────────────────────────────────
from app.controllers.segment_ctrl import SegmentControllerMixin  # noqa: E402

q = inspect.getsource(SegmentControllerMixin.get_selected_segment_indices)
check("status" not in q,
      "7. get_selected_segment_indices has no UI side effect (it is a hot-path "
      "query, also used by non-interactive callers)")
check(hasattr(ctl, "refresh_status_selection"),
      "7. the update is a separate, explicitly-called method")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
