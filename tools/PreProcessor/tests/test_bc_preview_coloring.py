#!/usr/bin/env python3
"""Headless regression test: BC Preview colours geometry outlines by the assigned
BC TYPE, not by the raw grouping label.

Guards the bug where pressing "BC Preview" after setting per-group BCs in "Edit
segment BCs…" showed the wrong colours (an arbitrary per-label palette whose first
colour is red — read as "wall"), because the preview coloured by the raw .meta
grouping label and ignored the group->type map (MeshConfig.group_bc). It must
resolve label -> BC type and use the semantic BC_COLORS.

Run:  python3 tools/PreProcessor/tests/test_bc_preview_coloring.py
"""
import os
import sys
import tempfile
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        failures.append(msg)


threading.Timer(40, lambda: (print("FAIL watchdog timeout", flush=True),
                             os._exit(99))).start()


def _write_square(dat_path):
    n = 10
    corners = [(-5, -5), (5, -5), (5, 5), (-5, 5)]
    pts, seg = [], []
    for i in range(4):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % 4]
        for k in range(n):
            t = k / n
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
            seg.append(i + 1)
    with open(dat_path, "w") as f:
        f.write("\n".join(f"{x} {y}" for x, y in pts) + "\n")
    meta = ["HYBMESH_META 3", f"COUNT {len(pts)}", "NPIECES 0", "NSEGMENTS 4"]
    for s, lab in ((1, "g0"), (2, "g1"), (3, "g2"), (4, "g3")):
        meta.append(f"{s} {lab} line 1")
    meta.append(f"POINTS {len(pts)}")
    meta += [f"{s} {1 if i % n == 0 else 0}" for i, s in enumerate(seg)]
    with open(dat_path + ".meta", "w") as f:
        f.write("\n".join(meta) + "\n")


def main():
    from PyQt6.QtWidgets import QApplication
    # Bound to a name on purpose: it keeps the QApplication alive for the
    # duration of the test (F841 would have us drop it).
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    from app.controller import AppController
    from app.models.mesh_config import MeshConfig
    from app.utils import BC_COLORS

    tmp = tempfile.mkdtemp(prefix="hybmesh_bcprev_")
    dat = os.path.join(tmp, "sq.dat")
    _write_square(dat)

    c = AppController()
    mcv = c.main_window.mesh_canvas_view
    mc = MeshConfig()
    mc.geom_files = [dat]
    mc.geom_roles = {dat: {"role": "wall"}}
    mc.group_bc = {"g0": "inlet", "g1": "outlet", "g2": "free", "g3": "SYMP"}
    mcv.domain_is_custom = True
    mcv.update_mesh_config(mc)

    got = set()
    for it in mcv.geom_bc_items:
        pen = it.opts.get("pen")
        try:
            got.add(pen.color().name().lower())
        except Exception:
            pass
    want = {BC_COLORS[k].lower() for k in ("inlet", "outlet", "free", "symp")}
    print("  got   :", sorted(got), flush=True)
    print("  expect:", sorted(want), flush=True)
    check("BC Preview colours geometry by assigned BC TYPE (group_bc), not label",
          got == want)
    # The raw-label palette's first colour (~red) must NOT be what we get for inlet.
    check("no arbitrary palette colour leaks through", "#e63946" not in got)

    # #4 regression: once a mesh exists, the boundary-colouring pass used to lump
    # the whole custom outline into ONE flat bc_geom colour (default "wall" → red)
    # drawn on top of (masking) the correct per-segment Path-A colours above. For a
    # custom domain it must now add NO such overlay and let the per-segment colours
    # show. Drive _rebuild_boundary_coloring directly with a stand-in mesh.
    import numpy as np

    class _FakeMesh:
        bounds = (-5.0, 5.0, -5.0, 5.0)   # (xmin, xmax, ymin, ymax)
        points = np.array([[-5.0, -5.0], [5.0, -5.0], [5.0, 5.0], [-5.0, 5.0]])

    mcv.mesh = _FakeMesh()
    mcv.show_bc_coloring = True
    mcv.bc_items = []
    mcv._rebuild_boundary_coloring([(0, 1), (1, 2), (2, 3), (3, 0)])
    check("custom domain adds no flat bc_geom overlay masking per-segment colours",
          len(mcv.bc_items) == 0)

    print(flush=True)
    print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED",
          flush=True)
    os._exit(1 if failures else 0)


if __name__ == "__main__":
    main()
