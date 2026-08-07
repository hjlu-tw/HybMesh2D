#!/usr/bin/env python3
"""Canvas industrial tools (Phase-3 item): measure, grid snap, view history.

The canvas could draw and drag but not *measure*: checking a slat gap, a chord, or the
clearance a boundary layer has to fit into meant exporting the geometry and computing
it elsewhere. It also had only endpoint snapping (no grid) and no way back to a
previous zoom.

The most important behaviour here is the SNAP ORDER. Endpoint snapping runs first and
wins; if the grid ran last unconditionally it would drag a just-welded endpoint back
off the geometry, silently reopening the gap the user had closed.

Checks:
 1. snap_to_grid rounds to the nearest multiple; a zero/negative/non-finite step means
    "off" and returns the point untouched.
 2. compose_snap: an endpoint hit WINS over the grid and is reported as such.
 3. measure() reports distance/dx/dy/angle, with the angle in (-180, 180]; degenerate
    input yields {} so callers show "—" rather than a measured-looking zero.
 4. ViewHistory collapses near-identical consecutive views (a wheel notch must not
    become a history step), truncates the forward branch on new navigation, and is
    capped.
 5. The history ignores pushes while a restore is in flight, so back/forward do not
    record themselves as new steps.
 6. The toolbar exposes the controls and they belong to the CAD stage.
 7. Live: grid snap applies through the real snap callback, measuring completes a
    span, its result survives switching the tool off, and view back/forward move the
    viewbox and update the button enablement.
 8. There is ONE source of truth for the grid step (the spin box), not a mirrored
    copy on the window.

Run:  python3 tools/PreProcessor/tests/test_canvas_tools.py
"""
import math
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

from app.services.canvas_tools import (  # noqa: E402
    MAX_VIEW_HISTORY, ViewHistory, compose_snap, format_measure, measure,
    snap_to_grid,
)

# ── 1. grid rounding ──────────────────────────────────────────────────────
check(snap_to_grid(0.31, 0.42, 0.25) == (0.25, 0.5),
      f"1. rounds to the nearest multiple ({snap_to_grid(0.31, 0.42, 0.25)})")
check(snap_to_grid(-0.31, -0.42, 0.25) == (-0.25, -0.5),
      "1. ...including negative coordinates")
for bad in (0.0, -1.0, float("nan"), float("inf")):
    check(snap_to_grid(1.234, 5.678, bad) == (1.234, 5.678),
          f"1. step={bad!r} means snapping off, point untouched")

# ── 2. snap order ─────────────────────────────────────────────────────────
ep = compose_snap(0.97, 0.03, endpoint_snap=lambda x, y: (1.0, 0.0), grid_step=0.25)
check(ep == (1.0, 0.0, True),
      f"2. an endpoint hit WINS over the grid and is reported (got {ep}) — the grid "
      "must not drag a welded endpoint back off the geometry")
no_ep = compose_snap(0.31, 0.42, endpoint_snap=lambda x, y: (x, y), grid_step=0.25)
check(no_ep == (0.25, 0.5, False),
      f"2. with no endpoint nearby the grid applies ({no_ep})")
check(compose_snap(0.31, 0.42) == (0.31, 0.42, False),
      "2. neither rule configured leaves the point alone")

# ── 3. measure ────────────────────────────────────────────────────────────
m = measure((0, 0), (3, 4))
check(abs(m["distance"] - 5.0) < 1e-12 and m["dx"] == 3 and m["dy"] == 4,
      f"3. distance and deltas ({m['distance']})")
check(abs(m["angle_deg"] - math.degrees(math.atan2(4, 3))) < 1e-9,
      "3. angle is measured from the +x axis")
check(abs(measure((0, 0), (-1, 0))["angle_deg"] - 180.0) < 1e-9,
      "3. a due-west span reads 180°, not -180°")
check(abs(measure((0, 0), (0, -1))["angle_deg"] + 90.0) < 1e-9,
      "3. a downward span reads -90°")
check(measure((0, 0), (0, 0))["distance"] == 0.0,
      "3. a zero-length span is a valid measurement of 0")
# Genuinely degenerate points. NOTE: (0, 0) is NOT in this list — it is a perfectly
# valid coordinate, and a zero-length span is asserted above as a real measurement.
for bad in (None, (0,), "xy", (float("nan"), 0.0), (0.0, float("inf"))):
    check(measure(bad, (1, 1)) == {},
          f"3. degenerate first point {bad!r} yields {{}}")
    check(measure((1, 1), bad) == {},
          f"3. degenerate second point {bad!r} yields {{}}")
check(format_measure({}) == "—", "3. an empty result formats as a dash")
check("d = 5" in format_measure(m), "3. the read-out leads with the distance")

# ── 4/5. view history ─────────────────────────────────────────────────────
h = ViewHistory()
check(h.push(((0, 1), (0, 1))) and len(h) == 1, "4. the first view is recorded")
check(not h.push(((0, 1), (0, 1))),
      "4. an identical consecutive view is collapsed (a wheel notch is not a step)")
check(not h.push(((0, 1 + 1e-15), (0, 1))),
      "4. ...and so is a near-identical one, within tolerance")
# The tolerance is a FRACTION OF THE SPAN, not an absolute distance: it used to be
# 1e-9, which only ever merged bit-identical views, so pyqtgraph's per-axis range
# signals pushed two entries a hair apart and one press of Back looked broken.
tolh = ViewHistory()                      # its own instance: the shared `h` below
tolh.push(((0, 1), (0, 1)))               # continues a sequence these must not disturb
check(not tolh.push(((0, 1.005), (0, 1))),
      "4. a sub-1% nudge is the same navigation step")
check(tolh.push(((0, 1.5), (0, 1.5))),
      "4. ...but a real zoom is a new one")
big = ViewHistory()
big.push(((0, 2000), (0, 1000)))
check(not big.push(((0, 2010), (0, 1000))),
      "4. the tolerance is scale-free: 10 units on a 2000-unit span is the same step, "
      "so a millimetre model and a metre model behave identically")
check(big.push(((0, 2600), (0, 1000))),
      "4. ...while 600 units on that span is not")
degen = ViewHistory()
degen.push(((5, 5), (5, 5)))
check(not degen.push(((5, 5), (5, 5))),
      "4. a degenerate (zero-span) view does not divide by zero")
h.push(((0, 2), (0, 2)))
h.push(((0, 3), (0, 3)))
check(len(h) == 3 and h.can_back and not h.can_forward,
      f"4. three views, at the end of the stack ({len(h)})")
check(h.back() == ((0, 2), (0, 2)), "4. back returns the previous view")
check(h.can_forward, "4. ...and forward becomes available")
h.push(((0, 9), (0, 9)))
check(not h.can_forward and len(h) == 3,
      f"4. navigating after a back truncates the forward branch ({len(h)})")

capped = ViewHistory(max_len=4)
for i in range(10):
    capped.push(((0, i + 1), (0, i + 1)))
check(len(capped) == 4, f"4. the history is capped ({len(capped)})")
check(MAX_VIEW_HISTORY >= 10, "4. the default cap is deep enough to be useful")

r = ViewHistory()
r.push(((0, 1), (0, 1)))
r.restoring = True
check(not r.push(((0, 5), (0, 5))),
      "5. a push during a restore is ignored (back/forward must not self-record)")
r.restoring = False
check(r.push(((0, 5), (0, 5))), "5. ...and normal pushes resume afterwards")
check(not r.push(None) and not r.push(((0, float("nan")), (0, 1))),
      "5. None / non-finite views are refused")

# ── 6/7/8. live in the app ────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402

ctl = AppController()
mw = ctl.main_window
cv = mw.canvas_view

for name in ("measure_btn", "grid_snap_cb", "grid_snap_step",
             "view_back_btn", "view_fwd_btn"):
    w = getattr(mw, name, None)
    check(w is not None, f"6. {name} exists on the toolbar")
    check(w in mw.cad_tb_widgets, "6. ...and belongs to the CAD stage")
check(mw.measure_btn.isCheckable(), "6. Measure is a toggle, not a one-shot")

geom = os.path.join(_REPO, "examples", "geometries", "naca0012.dat")
if not os.path.exists(geom):
    print("SKIP naca0012.dat missing — live checks skipped", flush=True)
else:
    ctl.load_geometry_from_path(geom)

    # 7. grid snap through the REAL callback the canvas uses.
    mw.grid_snap_cb.setChecked(True)
    mw.grid_snap_step.setValue(0.25)
    got = tuple(round(v, 9) for v in ctl._snap_draw_xy(0.31, 0.42))
    check(got == (0.25, 0.5), f"7. grid snap applies through snap_cb ({got})")
    mw.grid_snap_cb.setChecked(False)
    got = tuple(round(v, 9) for v in ctl._snap_draw_xy(0.31, 0.42))
    check(got == (0.31, 0.42), f"7. unchecking it stops snapping ({got})")

    # 8. one source of truth for the step.
    check(not hasattr(mw, "grid_snap_step_value"),
          "8. no mirrored copy of the grid step on the window — the spin box is "
          "the single source")

    # 7. measure through the toggle.
    mw.measure_btn.setChecked(True)
    check(cv.measuring, "7. toggling Measure enters the tool")
    check(cv.handle_measure_click(0.0, 0.0) == {},
          "7. the first click anchors and returns nothing")
    res = cv.handle_measure_click(1.0, 1.0)
    check(res and abs(res["distance"] - math.sqrt(2)) < 1e-12,
          f"7. the second click completes the span ({res.get('distance')})")
    check(cv.handle_measure_click(2.0, 2.0) == {},
          "7. a further click starts a NEW span (chaining along a gap)")
    mw.measure_btn.setChecked(False)
    check(not cv.measuring and cv._measure_result,
          "7. switching the tool off keeps the last span readable")
    cv.clear_measure()
    check(not cv._measure_result, "7. clear_measure drops it")

    # 7. view history through the canvas.
    # Recording is DEBOUNCED: a view is stored once it stops moving, so that one
    # wheel-zoom or drag-pan is one entry. Without that, pyqtgraph's per-axis range
    # signals stored two entries a hair apart and the first press of Back appeared to
    # do nothing at all.
    from PyQt6.QtCore import QEventLoop, QTimer  # noqa: E402
    from app.views.canvas_tools_mixin import VIEW_PUSH_IDLE_MS  # noqa: E402

    def settle(extra=200):
        loop = QEventLoop()
        QTimer.singleShot(VIEW_PUSH_IDLE_MS + extra, loop.quit)
        loop.exec()

    vb = cv.plot_widget.getViewBox()
    settle()
    before = len(cv.view_history)
    spans = []
    for lo, hi in ((0.0, 4.0), (1.0, 3.0), (1.8, 2.2)):
        vb.setRange(xRange=(lo, hi), yRange=(lo, hi), padding=0)
        settle()
        spans.append(round(vb.viewRange()[0][1] - vb.viewRange()[0][0], 4))
    check(len(cv.view_history) == before + 3,
          f"7. three gestures record exactly three views, not one per axis signal "
          f"({before} -> {len(cv.view_history)})")
    check(mw.view_back_btn.isEnabled(),
          "7. the Back button enables once there is history")

    span_now = vb.viewRange()[0][1] - vb.viewRange()[0][0]
    check(cv.view_back(), "7. Back moves the viewbox")
    span_back = vb.viewRange()[0][1] - vb.viewRange()[0][0]
    check(abs(span_back - span_now) > 0.5 * abs(span_now),
          f"7. ...by a WHOLE gesture — one press used to land a hair from where you "
          f"already were ({span_now:.3f} -> {span_back:.3f})")
    check(mw.view_fwd_btn.isEnabled(), "7. ...and enables Forward")
    settle()
    check(len(cv.view_history) == before + 3,
          "7. going back does not record the restored view as a new step")
    check(cv.view_forward(), "7. Forward returns")
    check(abs((vb.viewRange()[0][1] - vb.viewRange()[0][0]) - span_now)
          < 0.05 * abs(span_now),
          "7. ...to the view it came from")
    check(not mw.view_fwd_btn.isEnabled(),
          "7. at the end of the history Forward disables again")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
