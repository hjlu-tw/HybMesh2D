#!/usr/bin/env python3
"""Q2: separately-drawn boundary edges are welded at their near-coincident
endpoints so the mesher chains them into ONE connected boundary (instead of
disconnected pieces), while each edge stays a distinct segment (keeping its own
per-segment BC).

No-Qt weld-logic checks + an offscreen check that Preview's config writer welds
transiently (without mutating the user's in-memory edges) + a guarded
end-to-end backend run.

Run: python3 tools/PreProcessor/tests/test_endpoint_weld.py
"""
import os
import sys
import json
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

from app.models import shape_spec
from app.models.project import ProjectModel
from app.models.segment import SegmentModel
from app.services.geometry_service import GeometryService


def line_seg(sid, x0, y0, x1, y1, bc=""):
    s = SegmentModel(sid, -1, -1)
    s.type = "curve"
    s.curve_type = "line"
    s.curve_mode = "parametric"
    s.parameters = {"n_points": 8, "x0": x0, "y0": y0, "x1": x1, "y1": y1}
    s.bc = bc
    return s


# ── boundary_endpoints exposes the two free ends of open shapes only ──────
check([h for h, _ in shape_spec.boundary_endpoints("line", {"x0": 0, "y0": 0, "x1": 1, "y1": 2})]
      == ["p0", "p1"], "boundary_endpoints(line) → p0,p1")
check(shape_spec.boundary_endpoints("circle", {"cx": 0, "cy": 0, "r": 1}) == [],
      "boundary_endpoints(circle) → [] (closed, not weldable)")
_poly = shape_spec.boundary_endpoints("polygon", {"vertices_str": "0,0; 1,0; 1,1"})
check([h for h, _ in _poly] == ["v0", "v2"], "boundary_endpoints(polygon) → first/last vertex")

# ── weld: a box of 4 lines with ~1e-4 corner gaps → 3 welds, ends coincide ─
segs = [line_seg(1, 0, 0, 1.0, 0.0, "wall"),
        line_seg(2, 1.0001, 0.0001, 1, 1, "outlet"),
        line_seg(3, 1.0001, 1.0001, 0, 1, "wall"),
        line_seg(4, 0.0001, 1.0001, 0, 0, "inlet")]
tol = 0.01 * float(np.hypot(1.0, 1.0))          # mirrors _endpoint_tolerance
nw = GeometryService.weld_boundary_endpoints(segs, tol)
check(nw == 3, f"welded 3 near-coincident box corners (got {nw})")
# every consecutive junction now matches to < 1e-7
ok = True
for a, b in ((segs[0], segs[1]), (segs[1], segs[2]), (segs[2], segs[3])):
    pa = (a.parameters["x1"], a.parameters["y1"])
    pb = (b.parameters["x0"], b.parameters["y0"])
    ok = ok and abs(pa[0] - pb[0]) < 1e-7 and abs(pa[1] - pb[1]) < 1e-7
check(ok, "welded junctions coincide to < 1e-7 (mesher chains them)")

# ── a genuinely separate pair (far apart) is NOT welded ───────────────────
far = [line_seg(1, 0, 0, 1, 0), line_seg(2, 5, 5, 6, 6)]
check(GeometryService.weld_boundary_endpoints(far, 0.05) == 0,
      "far-apart edges are left untouched")

# ── Offscreen: Preview's config writer welds transiently, model untouched ─
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController

c = AppController()
c.new_blank_tab()
s = c.active_session()
pm = s.project_model
pm.segments = [line_seg(1, 0, 0, 1.0, 0.0, "wall"),
               line_seg(2, 1.001, 0.001, 1.0, 1.0, "outlet")]
pm._next_curve_id = 3
before = (pm.segments[0].parameters["x1"], pm.segments[0].parameters["y1"])

out = os.path.join(c.temp_dir, "weld_preview_out.dat")
cfg_path, created = c._write_temp_config(s, out, preview_markers=True)
cfg = json.load(open(cfg_path))
L1, L2 = cfg["segments"][0], cfg["segments"][1]
p1 = L1["parameters"]
p2 = L2["parameters"]
check(abs(p1["x1"] - p2["x0"]) < 1e-7 and abs(p1["y1"] - p2["y0"]) < 1e-7,
      "exported config has welded (coincident) junction")
after = (pm.segments[0].parameters["x1"], pm.segments[0].parameters["y1"])
check(after == before,
      "the user's in-memory edges are NOT mutated by the weld (transient)")
check(L1.get("bc") == "wall" and L2.get("bc") == "outlet",
      "each welded edge keeps its own per-segment BC")
for f in created:
    try:
        os.remove(f)
    except OSError:
        pass

# ── Guarded end-to-end: run the real resampler if it is built ─────────────
exe = os.path.join(_REPO, "build", "surface_resampler")
if os.path.exists(exe):
    segs2 = [line_seg(1, 0, 0, 1.0, 0.0, "wall"),
             line_seg(2, 1.0001, 0.0001, 1, 1, "outlet"),
             line_seg(3, 1.0001, 1.0001, 0, 1, "wall"),
             line_seg(4, 0.0001, 1.0001, 0, 0, "inlet")]
    pm2 = ProjectModel()
    pm2.segments = segs2
    pm2.closed_mode = "closed"
    pm2.is_closed = True
    GeometryService.weld_boundary_endpoints(pm2.segments, tol)
    out2 = os.path.join(c.temp_dir, "weld_e2e_out.dat")
    cfg2 = os.path.join(c.temp_dir, "weld_e2e.json")
    pm2.output_file = out2
    pm2.export_config(cfg2)
    r = subprocess.run([exe, cfg2], capture_output=True, text=True)
    npieces = next((ln.strip() for ln in open(out2 + ".meta")
                    if ln.startswith("NPIECES")), "?") if os.path.exists(out2 + ".meta") else "?"
    check(r.returncode == 0 and npieces == "NPIECES 0",
          f"end-to-end: welded box resamples as ONE piece ({npieces})")
    for f in (out2, out2 + ".meta", cfg2):
        try:
            os.remove(f)
        except OSError:
            pass
else:
    print("SKIP end-to-end backend run (surface_resampler not built)")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
