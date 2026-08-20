"""Geometry statistics panel + service (Phase-3 item).

Nothing on screen said what you were looking at: not the point count, not the
boundary length, and — the one that matters for meshing — not how uneven the point
spacing was. A geometry whose neighbouring intervals jump more than ~1.2x grows a
poor boundary layer, and that was only discoverable by generating a mesh and looking
at the failure.

Checks:
 1. compute() reports counts, bbox, extent and perimeter for a known shape.
 2. A CLOSED geometry includes the seam interval in the perimeter and in the
    spacing/ratio statistics — that interval is a real mesh edge, and the worst
    expansion often sits exactly there.
 3. Expansion ratio is direction-agnostic (a 2x drop is as bad as a 2x jump) and
    reports where the worst one is.
 4. Degenerate input is refused rather than answered with zeros that look like
    measurements: empty, 1-point, all-NaN, all-duplicate.
 5. NaN/Inf points are dropped, not propagated into the numbers.
 6. fmt() gives "—" for everything unavailable.
 7. The panel is in the CAD sidebar, collapsed by default (the sidebar is a fixed
    360 px), and its uniformity row turns amber only when the spacing is uneven.
 8. Loading a geometry populates it live; clearing the sidebar blanks it rather
    than leaving the previous geometry's numbers on screen.

Run:  python3 tools/PreProcessor/tests/test_geometry_stats.py
"""
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

import numpy as np  # noqa: E402

from app.services import geometry_stats as gs  # noqa: E402

# A unit square, given as 4 corners (the closing edge is implied).
SQUARE = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])

# ── 1. basic metrics ──────────────────────────────────────────────────────
st = gs.compute(SQUARE, closed=False, n_segments=4)
check(st["n_points"] == 4 and st["n_segments"] == 4,
      "1. point and edge counts are reported")
check(st["xmin"] == 0 and st["xmax"] == 1 and st["ymin"] == 0 and st["ymax"] == 1,
      "1. bounding box is correct")
check(st["width"] == 1 and st["height"] == 1, "1. extent is correct")
check(abs(st["length"] - 3.0) < 1e-12,
      f"1. an OPEN square walks 3 sides ({st['length']})")

# ── 2. the closing interval counts ────────────────────────────────────────
stc = gs.compute(SQUARE, closed=True, n_segments=4)
check(abs(stc["length"] - 4.0) < 1e-12,
      f"2. a CLOSED square perimeter includes the seam ({stc['length']})")
check(stc["closed"] is True and st["closed"] is False,
      "2. the closed flag is reported")
# An already-repeated first point must not be double-counted.
repeated = np.vstack((SQUARE, SQUARE[0]))
check(abs(gs.compute(repeated, closed=True)["length"] - 4.0) < 1e-12,
      "2. a geometry that already repeats its first point is not double-counted")
# The seam interval participates in the ratio stats: here the seam is the ONLY
# uneven one, so it must be what raises ratio_max.
seam = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [2.0, 0.01]])
check(gs.compute(seam, closed=True).get("ratio_max", 0)
      > gs.compute(seam, closed=False).get("ratio_max", 0),
      "2. closing the geometry exposes an uneven seam the open form hides")

# ── 3. expansion ratio ────────────────────────────────────────────────────
grow = np.array([[0.0, 0.0], [1.0, 0.0], [3.0, 0.0]])          # 1 then 2 -> 2x
shrink = np.array([[0.0, 0.0], [2.0, 0.0], [3.0, 0.0]])        # 2 then 1 -> 2x
check(abs(gs.compute(grow)["ratio_max"] - 2.0) < 1e-12
      and abs(gs.compute(shrink)["ratio_max"] - 2.0) < 1e-12,
      "3. a 2x jump and a 2x drop score the same (direction-agnostic)")
uneven = np.array([[0, 0], [1, 0], [1.001, 0], [3, 0]], float)
su = gs.compute(uneven)
check(su["ratio_over"] >= 1 and su["ratio_total"] == 2,
      f"3. intervals over {gs.RATIO_WARN}x are counted ({su['ratio_over']}/{su['ratio_total']})")
# ds = [1.0, 0.001, 1.999]; the worst transition is 0.001 -> 1.999, and those two
# intervals meet at point index 2 — which is what ratio_max_at must name.
check(su["ratio_max_at"] == 2,
      f"3. the worst ratio names the POINT where the two intervals meet "
      f"(got {su['ratio_max_at']}, want 2)")
check(gs.is_uneven(su) and not gs.is_uneven(gs.compute(SQUARE, closed=True)),
      "3. is_uneven() flags the uneven case and not a perfect square")

# ── 4/5. degenerate input is refused, not answered ────────────────────────
for label, pts in (("None", None), ("empty", np.empty((0, 2))),
                   ("all-NaN", np.array([[np.nan, np.nan], [np.nan, 1.0]])),
                   ("1-D", np.array([1.0, 2.0]))):
    check(gs.compute(pts) == {},
          f"4. {label} input yields {{}} — no invented zeros")
one = gs.compute(np.array([[5.0, 7.0]]))
check(one.get("n_points") == 1 and "length" not in one,
      "4. a single point reports its count and bbox but no length")
dup = gs.compute(np.array([[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]]))
check("length" not in dup,
      "4. all-duplicate points report no length (zero-length intervals dropped)")

mixed = np.array([[0.0, 0.0], [np.inf, 0.0], [1.0, 0.0], [2.0, 0.0]])
sm = gs.compute(mixed)
check(sm["n_points"] == 3 and np.isfinite(sm["length"]),
      f"5. non-finite points are dropped, not propagated ({sm['n_points']} kept)")

# ── 6. formatting ─────────────────────────────────────────────────────────
blank = gs.fmt({})
check(all(v == "—" for v in blank.values()),
      "6. fmt({}) is all em-dashes")
one_fmt = gs.fmt(one)
check(one_fmt["length"] == "—" and one_fmt["points"] == "1",
      "6. an unavailable metric shows '—' beside the ones that ARE known")
check(gs.fmt(gs.compute(SQUARE, closed=True, n_segments=4))["closed"] == "closed",
      "6. topology is worded, not a bare boolean")

# ── 7/8. the panel ────────────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from app.views.sidebar import SidebarView  # noqa: E402

sb = SidebarView(None)
panel = getattr(sb, "geom_stats_panel", None)
check(panel is not None, "7. the stats panel is part of the CAD sidebar")
check(panel is not None and not panel.section.is_expanded,
      "7. it starts collapsed (the sidebar is a fixed 360 px)")

panel.update_stats(SQUARE, closed=True, n_segments=4)
check(panel._values["points"].text() == "4"
      and panel._values["length"].text() == "4",
      "7. the panel shows the computed values")
even_style = panel._values["quality"].styleSheet()
panel.update_stats(uneven, closed=False, n_segments=1)
check(panel._values["quality"].styleSheet() != even_style
      and "e5a13a" in panel._values["quality"].styleSheet(),
      "7. the uniformity row turns amber ONLY when the spacing is uneven")

from app.controller import AppController  # noqa: E402

geom = os.path.join(_REPO, "examples", "geometries", "naca0012.dat")
if not os.path.exists(geom):
    print("SKIP naca0012.dat missing — live-update check skipped", flush=True)
else:
    ctl = AppController()
    ctl.load_geometry_from_path(geom)
    live = ctl.main_window.sidebar_view.geom_stats_panel
    check(live._values["points"].text() not in ("—", "0"),
          f"8. loading a geometry populates the panel live "
          f"({live._values['points'].text()} points)")
    check(live._values["length"].text() != "—",
          f"8. ...including the perimeter ({live._values['length'].text()})")
    ctl._clear_sidebar()
    check(live._values["points"].text() == "—"
          and live._values["quality"].text() == "—",
          "8. clearing the sidebar blanks it rather than leaving stale numbers")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
