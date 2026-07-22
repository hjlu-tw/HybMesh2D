#!/usr/bin/env python3
"""Offscreen tests for: arc analytic edge, Redraw button, and even point
distribution after an arc-preserving join.

Run: python3 tools/PreProcessor/tests/test_arc_redraw_join_gui.py
"""
import os
import sys
import math
import subprocess
import threading
import functools

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

import builtins
print = functools.partial(builtins.print, flush=True)
_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        _FAILS.append(msg)


threading.Timer(40, lambda: (print("FAIL watchdog >40s"), os._exit(99))).start()

# ── Arc geometry (no Qt needed) ───────────────────────────────────────────
from app.models import shape_spec
from app.models.segment import SegmentModel
from app.services.geometry_service import GeometryService

res = shape_spec.arc_from_3points((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0))
check(res is not None, "arc_from_3points: non-collinear returns a fit")
ux, uy, r, t0, t1 = res
check(abs(ux) < 1e-9 and abs(uy) < 1e-9 and abs(r - 1.0) < 1e-9,
      f"arc fit: unit circle at origin (c=({ux:.3g},{uy:.3g}), r={r:.4g})")
check(shape_spec.arc_from_3points((0, 0), (1, 0), (2, 0)) is None,
      "arc_from_3points: collinear → None")

_pp, _ct = shape_spec.params_from_points("arc", [(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0)])
check(_ct == "arc" and {"cx", "cy", "r", "theta0", "theta1"} <= set(_pp),
      "params_from_points('arc') → arc params")

seg = SegmentModel(1, -1, -1)
seg.type = "curve"
seg.curve_type = "arc"
seg.curve_mode = "parametric"
seg.parameters = {"cx": ux, "cy": uy, "r": r, "theta0": t0, "theta1": t1, "n_points": 24}
xs, ys = GeometryService.compute_curve_preview_pts(seg, 24, None)
on_circle = np.allclose(np.hypot(xs, ys), 1.0, atol=1e-6)
upper = np.all(ys >= -1e-6)
ends = (abs(xs[0] - 1.0) < 1e-6 and abs(xs[-1] + 1.0) < 1e-6)
check(on_circle and upper and ends,
      "arc sampling: points ride the unit upper semicircle end-to-end")

# ── Precise arc editing: mid handle + lock-radius drag (no Qt) ─────────────
_ap = {"cx": 0.0, "cy": 0.0, "r": 1.0, "theta0": 0.0, "theta1": math.pi / 2}
_cps = shape_spec.control_points("arc", _ap)
_ids = [h for h, _ in _cps]
check(_ids == ["c", "p0", "p1", "m"], f"arc control points are c/p0/p1/m ({_ids})")
_mid = dict(_cps)["m"]
check(abs(_mid[0] - math.cos(math.pi / 4)) < 1e-9
      and abs(_mid[1] - math.sin(math.pi / 4)) < 1e-9,
      "arc mid handle sits at the sweep midpoint")

# lock_radius: dragging an END handle only changes the angle, radius stays put.
_lp = dict(_ap)
shape_spec.apply_drag("arc", _lp, "p1", 5.0, 5.0, lock_radius=True)
check(abs(_lp["r"] - 1.0) < 1e-9 and abs(_lp["theta1"] - math.pi / 4) < 1e-9,
      f"lock_radius end drag: r fixed (r={_lp['r']:.4g}, θ1={_lp['theta1']:.4g})")

# without lock: an end drag re-fits the radius (legacy behaviour).
_fp = dict(_ap)
shape_spec.apply_drag("arc", _fp, "p1", 0.0, 3.0, lock_radius=False)
check(abs(_fp["r"] - 3.0) < 1e-9, f"unlocked end drag re-fits radius (r={_fp['r']:.4g})")

# mid handle: changes radius but pins the two endpoints in place.
_mp = dict(_ap)
p0_before = (_mp["cx"] + _mp["r"] * math.cos(_mp["theta0"]),
             _mp["cy"] + _mp["r"] * math.sin(_mp["theta0"]))
p1_before = (_mp["cx"] + _mp["r"] * math.cos(_mp["theta1"]),
             _mp["cy"] + _mp["r"] * math.sin(_mp["theta1"]))
shape_spec.apply_drag("arc", _mp, "m", 0.3, 0.3, lock_radius=True)   # flatter bulge
p0_after = (_mp["cx"] + _mp["r"] * math.cos(_mp["theta0"]),
            _mp["cy"] + _mp["r"] * math.sin(_mp["theta0"]))
p1_after = (_mp["cx"] + _mp["r"] * math.cos(_mp["theta1"]),
            _mp["cy"] + _mp["r"] * math.sin(_mp["theta1"]))
check(np.allclose(p0_before, p0_after, atol=1e-6)
      and np.allclose(p1_before, p1_after, atol=1e-6)
      and abs(_mp["r"] - 1.0) > 1e-3,
      f"mid handle changes radius, endpoints pinned (r={_mp['r']:.4g})")

# ── Full AppController: arc widget + Redraw button ────────────────────────
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController
from app.controllers.curve_ctrl import CURVE_TYPES

c = AppController()
mw = c.main_window
mw.show()
app.processEvents()
sb = mw.sidebar_view
ep = sb.edge_props_panel

check(len(CURVE_TYPES) == 9 and CURVE_TYPES[8] == "arc", "CURVE_TYPES has arc at index 8")
check(ep.curve_type_combo.count() == len(CURVE_TYPES)
      and ep.shape_stack.count() == len(CURVE_TYPES),
      f"combo({ep.curve_type_combo.count()}) == stack({ep.shape_stack.count()}) == types(9)")
check(all(hasattr(ep, a) for a in
          ("arc_cx", "arc_cy", "arc_r", "arc_theta0", "arc_theta1")),
      "edge-props has the arc spin boxes")
check(hasattr(ep, "arc_lock_radius") and ep.arc_lock_radius.isChecked(),
      "edge-props has a Lock-radius checkbox, on by default")
# Selecting Arc in the combo switches the stack to the arc page (index 8).
ep.curve_type_combo.setCurrentIndex(8)
app.processEvents()
check(ep.shape_stack.currentIndex() == 8, "combo 'Arc' selects the arc widget page")

check(hasattr(mw, "cad_redraw_btn"), "Redraw button exists in the toolbar")
try:
    c.redraw_canvas()
    app.processEvents()
    check(True, "redraw_canvas() runs without error")
except Exception as e:  # pragma: no cover
    check(False, f"redraw_canvas() raised: {e}")

# vertex-panel width guard (#3): coord spin boxes are capped to fit the sidebar
vp = sb.vertex_panel if hasattr(sb, "vertex_panel") else None
if vp is not None:
    check(vp.move_x.sizeHint().width() <= 95 and vp.insert_x.sizeHint().width() <= 95,
          "vertex coord spin boxes are width-capped")
else:
    print("SKIP vertex_panel width check (panel not exposed)")

# ── #4: arc-preserving join distributes vertices evenly ───────────────────
c.new_blank_tab()
s = c.active_session()
pm = s.project_model
N = 21
th = np.linspace(0.0, math.pi, N)
arc = np.column_stack([np.cos(th), np.sin(th)])
s.original_points = arc.copy()
s.split_indices = [0, N - 1]
fseg = SegmentModel(1, 0, N - 1)
fseg.type = "file"
fseg.parameters = {"n_points": N}
line = SegmentModel(10001, -1, -1)
line.type = "curve"
line.curve_type = "line"
line.curve_mode = "parametric"
line.parameters = {"n_points": 12, "x0": -1.0, "y0": 0.0, "x1": 1.0, "y1": 0.0}
pm.segments = [fseg, line]
pm._next_curve_id = 10002
c._refresh_segment_list()
c.join_selected_edges_to_polygon()
app.processEvents()
polys = [x for x in pm.segments if getattr(x, "curve_type", "") == "polygon"]
check(len(polys) == 1, "arc+line joined into one polygon")
if polys:
    v = np.asarray(shape_spec.polygon_vertices(polys[0].parameters), float)
    loop = np.vstack([v, v[0]])          # include the closing edge
    seglen = np.hypot(np.diff(loop[:, 0]), np.diff(loop[:, 1]))
    ratio = float(seglen.max() / max(seglen.min(), 1e-12))
    check(ratio < 1.6,
          f"joined polygon vertices are evenly spaced (max/min edge = {ratio:.2f})")

# ── Guarded: an arc resamples as an arc through the C++ backend ────────────
# (Regression for the backend arc branch — without it the arc fell through to
# the cos/sin formula fallback and resampled as a FULL circle.)
_exe = os.path.join(_REPO, "build", "surface_resampler")
if os.path.exists(_exe):
    from app.models.project import ProjectModel
    aseg = SegmentModel(1, -1, -1)
    aseg.type = "curve"; aseg.curve_type = "arc"; aseg.curve_mode = "parametric"
    aseg.parameters = {"n_points": 9, "cx": 0.0, "cy": 0.0, "r": 1.0,
                       "theta0": 0.0, "theta1": math.pi}
    apm = ProjectModel(); apm.segments = [aseg]
    apm.closed_mode = "open"; apm.is_closed = False
    aout = os.path.join(c.temp_dir, "arc_be_out.dat")
    acfg = os.path.join(c.temp_dir, "arc_be.json")
    apm.output_file = aout; apm.export_config(acfg)
    ar = subprocess.run([_exe, acfg], capture_output=True, text=True)
    if ar.returncode == 0 and os.path.exists(aout):
        pts = np.loadtxt(aout)
        on_c = np.allclose(np.hypot(pts[:, 0], pts[:, 1]), 1.0, atol=1e-6)
        semis = np.all(pts[:, 1] >= -1e-6) and len(pts) == 9
        check(on_c and semis,
              "backend resamples the arc as an upper semicircle (not a full circle)")
    else:
        check(False, f"arc backend run failed (rc={ar.returncode})")
    for f in (aout, aout + ".meta", acfg):
        try:
            os.remove(f)
        except OSError:
            pass
else:
    print("SKIP arc backend check (surface_resampler not built)")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
