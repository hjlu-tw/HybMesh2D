#!/usr/bin/env python3
"""Item: all-BL boundaries came out bc_flag=2 (wall). Root cause — the group
label->BC-type map (group_bc) lived only in memory, so a session reset / config
reload dropped it while the .meta kept the labels; the mesher then wrote the raw
labels as patch names and getPGrid defaulted every unknown label to wall.

Fix: persist the label->type map in the .meta and self-heal it on set_config.
This checks: (1) meta_io round-trip, (2) the writers preserve the trailer,
(3) set_config self-heals an EMPTY group_bc from the .meta so get_config re-emits
the GROUP_BC lines.

Run: python3 tools/PreProcessor/tests/test_meta_group_bc_persist.py
"""
import os
import sys
import tempfile
import functools

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


from app.services import meta_io

tmp = tempfile.mkdtemp()
dat = os.path.join(tmp, "dom.dat")
with open(dat, "w") as f:
    f.write("0 0\n1 0\n1 1\n0 1\n0 0\n")
with open(dat + ".meta", "w") as f:
    f.write("HYBMESH_META 3\nCOUNT 5\nNPIECES 0\nNSEGMENTS 4\n")
    f.write("1 dom_s1 line 1\n2 dom_s2 line 1\n3 dom_s3 line 1\n4 dom_s4 line 1\n")
    f.write("POINTS 5\n1 1\n1 0\n2 0\n3 0\n4 1\n")

# 1. Round-trip.
meta_io.write_meta_group_bc(dat, {"dom_s1": "wall", "dom_s2": "inlet",
                                  "dom_s3": "wall", "dom_s4": "outlet"})
got = meta_io.read_meta_group_bc(dat)
check(got == {"dom_s1": "wall", "dom_s2": "inlet", "dom_s3": "wall", "dom_s4": "outlet"},
      f"group_bc round-trips through the .meta trailer (got {got})")

# 2. The segbc / growbl writers preserve the trailer, and segment reads are intact.
meta_io.write_meta_seg_growbl(dat, {2: False})
meta_io.write_meta_segbc(dat, {1: "dom_s1"})
check(meta_io.read_meta_group_bc(dat) == got,
      "GROUP_BC trailer survives write_meta_seg_growbl + write_meta_segbc")
segs = meta_io.read_meta_segments(dat)
check([s[0] for s in segs] == [1, 2, 3, 4] and segs[1][1] == "dom_s2",
      "NSEGMENTS block still parses correctly under the trailer")
check(meta_io.read_meta_seg_growbl(dat)[2] is False,
      "grow-BL flag still parses correctly under the trailer")

# 3. set_config self-heals an EMPTY group_bc from the .meta.
from PyQt6.QtWidgets import QApplication  # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402
from app.models.mesh_config import MeshConfig  # noqa: E402

c = AppController()
panel = c.main_window.mesh_config_panel
cfg = MeshConfig()
cfg.geom_files = [dat]
cfg.group_bc = {}                       # desynced: labels on disk, map lost
panel.set_config(cfg)
app.processEvents()
healed = dict(getattr(panel, "_group_bc", {}))
check(healed.get("dom_s2") == "inlet" and healed.get("dom_s4") == "outlet"
      and healed.get("dom_s1") == "wall",
      f"set_config self-heals group_bc from the .meta (got {healed})")

out_cfg = panel.get_config()
check(out_cfg.group_bc.get("dom_s2") == "inlet",
      "get_config carries the healed group_bc (so GROUP_BC lines are re-emitted)")

# 4. An explicit config GROUP_BC stays authoritative over the .meta.
cfg2 = MeshConfig()
cfg2.geom_files = [dat]
cfg2.group_bc = {"dom_s2": "symmetry"}   # config overrides the .meta's 'inlet'
panel.set_config(cfg2)
app.processEvents()
check(dict(panel._group_bc).get("dom_s2") == "symmetry",
      "explicit config GROUP_BC wins over the .meta trailer")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
