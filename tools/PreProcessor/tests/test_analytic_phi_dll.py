#!/usr/bin/env python3
"""Item 1: CAD shape -> analytic phi init DLL (immersed solid WITHOUT an STL3d
phi.dat). Checks the rendered C++ compiles, sets phi=Q[4]=1 inside / 0 outside,
and that the controller wires it into the solver IBM config with ibm_phi_file
left EMPTY (analytic path — stage_phi_file self-skips).

Run: python3 tools/PreProcessor/tests/test_analytic_phi_dll.py
"""
import os
import sys
import shutil
import tempfile
import subprocess
import functools
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

import builtins
print = functools.partial(builtins.print, flush=True)
_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        _FAILS.append(msg)


threading.Timer(60, lambda: (print("FAIL watchdog >60s"), os._exit(99))).start()

from app.services.dll_templates import render_analytic_phi_from_shape

tmp = tempfile.mkdtemp()
cxx = shutil.which("g++") or shutil.which("clang++") or shutil.which("c++")


def compiles(src: str, name: str) -> bool:
    cc = os.path.join(tmp, name + ".cc")
    so = os.path.join(tmp, name + ".so")
    with open(cc, "w") as f:
        f.write(src)
    if not cxx:
        print(f"  (no C++ compiler found; skipping compile of {name})")
        return True
    r = subprocess.run([cxx, "-fPIC", "-shared", "-O3", "-o", so, cc],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:])
    return r.returncode == 0 and os.path.exists(so)


# ── Disk (circle) ─────────────────────────────────────────────────────────────
disk = render_analytic_phi_from_shape("circle", cx=0.5, cy=0.25, radius=0.4)
check("initQ_at_p" in disk and "Q[4] = phi" in disk, "disk DLL has the phi contract")
check("0.4" in disk and "0.5" in disk, "disk DLL bakes the circle center/radius")
check(compiles(disk, "disk"), "disk analytic phi DLL compiles")

# ── Polygon (point-in-polygon) ────────────────────────────────────────────────
poly = render_analytic_phi_from_shape(
    "polygon", verts=[(0, 0), (2, 0), (2, 1), (0, 1), (0, 0)])   # closing dup dropped
check("inside = !inside" in poly, "polygon DLL uses ray-crossing PIP")
check("const int NV = 4" in poly, "polygon DLL drops the repeated closing vertex (NV=4)")
check("Q[4] = phi" in poly, "polygon DLL sets phi into Q[4]")
check(compiles(poly, "poly"), "polygon analytic phi DLL compiles")

# ── Controller flow: CAD circle -> solver IBM config ──────────────────────────
from PyQt6.QtWidgets import QApplication  # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402
from app.models.segment import SegmentModel  # noqa: E402

c = AppController()
sess = c.active_session()
circ = SegmentModel(1, -1, -1)
circ.type = "curve"; circ.curve_type = "circle"
circ.parameters = {"cx": 1.0, "cy": 0.0, "r": 0.5, "n_points": 64}
sess.project_model.segments = [circ]
c.generate_phi_from_cad_shape()
app.processEvents()

sc = c.global_solver_config
check(sc.immersed_solid is True, "controller enables immersed_solid")
check(bool(sc.init_cond_dll) and os.path.exists(sc.init_cond_dll),
      f"controller writes the init DLL ({sc.init_cond_dll})")
check(sc.ibm_phi_file == "",
      "controller leaves ibm_phi_file EMPTY (analytic; stage_phi_file self-skips)")
if sc.init_cond_dll and os.path.exists(sc.init_cond_dll):
    with open(sc.init_cond_dll) as f:
        body = f.read()
    check("0.5" in body and "1.0" in body, "generated DLL bakes the CAD circle's cx/r")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
