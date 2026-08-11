#!/usr/bin/env python3
"""A grid whose BCs never made it in must not reach the solver unannounced.

USER-REPORTED (2026-08-11): "當我更新了 STARCD 檔案的邊界條件後，跑 solver 還是
一樣的結果." Reconstructed from the session log + the files it left behind:

  09:46  the domain geometry is re-resampled -> its .meta NSEGMENTS bc column is
         rewritten from the pipeline config, i.e. the per-segment BC LABELS are
         gone (the label->type map in the trailer survives)
  09:51-09:54  eight mesh runs, each printing "NO boundary segment carries any of
         the 6 GROUP_BC label(s)"; every .bnd patch exports as `wall`
  09:56  the user re-applies the per-segment BCs -> .meta gets its labels back
  09:56 / 10:00 / 10:03  export Star-CD -> Send to Solver -> Run, three times,
         WITHOUT regenerating the mesh. Same all-`wall` grid, same answer.

Nothing between the BC edit and the solve compares the two: the mesher's warning
is printed at mesh time, and export/send/run just pass the file along. (Verified
independently: re-running HybMesh2D against that same .meta produces
`2 inlet / 3 outlet` — the mesher was right, the mesh was simply older than the
edit.)

``services/mesh_bc_audit.py`` is the check that closes it; the GUI runs it at
Export Star-CD, at Send to Solver, and once more against the exact .bnd the run
resolved to (there it asks "run anyway?" rather than deciding for the user).

Checks:
 1. a mesh carrying the assigned BC types is silent — no false alarm
 2. the reported case: labels assigned, every patch `wall` -> named as missing
 3. a label with no type mapping, and a mapping whose label no segment carries,
    are both ignored (they resolve to nothing at mesh time too)
 4. the .meta trailer stands in for group_bc when the live map is empty
 5. a .meta modified after the mesh flags the mesh as older than the edit
 6. audit_mesh_bc explains the problem AND says what to do about it
 7. no geometry / unreadable .bnd / no assignment -> no problems invented

Run:  python3 tools/PreProcessor/tests/test_mesh_bc_audit.py
"""
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

from app.services.mesh_bc_audit import (                          # noqa: E402
    audit_mesh_bc, expected_bc_types, mesh_bc_gap, stale_meta_files,
)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


tmp = tempfile.mkdtemp(prefix="hybmesh_bc_audit_")


def write_meta(name, segs, group_bc):
    """Write a geometry .dat + .meta the way the resampler does."""
    dat = os.path.join(tmp, name)
    with open(dat, "w") as f:
        f.write("0 0\n1 0\n1 1\n0 1\n")
    lines = ["HYBMESH_META 3", "COUNT 4", "NPIECES 0",
             f"NSEGMENTS {len(segs)}"]
    for sid, label in segs:
        lines.append(f"{sid} {label or '-'} smooth 1")
    lines += ["POINTS 4", "1 1", "1 0", "1 0", "1 0"]
    lines += [f"GROUP_BC {lbl} {bc}" for lbl, bc in group_bc.items()]
    with open(dat + ".meta", "w") as f:
        f.write("\n".join(lines) + "\n")
    return dat


def write_bnd(name, patches):
    """STAR-CD .bnd: <bndId> v1 v2 0 0 <segId> 0 <patchName>."""
    path = os.path.join(tmp, name)
    with open(path, "w") as f:
        for i, (sid, patch) in enumerate(patches, start=1):
            f.write(f"{i} {i} {i + 1} 0 0 {sid} 0 {patch}\n")
    return path


# The reported geometry: a duct wall split into 4 segments, two of them flow BCs.
LABELS = [(1, "duct_s1"), (2, "duct_s2"), (3, "duct_s3"), (4, "duct_s4")]
GROUP = {"duct_s1": "wall", "duct_s2": "outlet",
         "duct_s3": "wall", "duct_s4": "inlet"}
geom = write_meta("duct.dat", LABELS, GROUP)
# Two foils, written here so every .meta predates the meshes below (check 5
# gives one of them a later mtime on purpose).
loose = write_meta("loose.dat", [(1, "loose_s1"), (2, "")], {"loose_s1": "wall"})
plain = write_meta("plain.dat", [(1, ""), (2, "")], {})

good = write_bnd("good.bnd", [(1, "wall"), (2, "inlet"), (3, "outlet"),
                              (4, "wall"), (5, "wall")])
all_wall = write_bnd("all_wall.bnd", [(i, "wall") for i in range(1, 9)])

# ── 1. a mesh that carries the BCs is silent ────────────────────────────────
check(mesh_bc_gap(good, [geom], GROUP) == [],
      "1. a mesh carrying inlet+outlet raises nothing")
check(audit_mesh_bc(good, [geom], GROUP) == [],
      "1. ...and the full audit is empty for it")

# ── 2. the reported case: every patch fell back to wall ─────────────────────
gap = mesh_bc_gap(all_wall, [geom], GROUP)
check(gap == ["inlet", "outlet"],
      f"2. an all-`wall` mesh names the missing BC types (got {gap})")
problems = audit_mesh_bc(all_wall, [geom], GROUP)
check(problems and "inlet" in problems[0] and "outlet" in problems[0],
      "2. the audit's first line names them")
check(any("wall default" in p for p in problems),
      "2. ...and says what the solver will do instead")

# ── 3. labels and mappings that resolve to nothing are ignored ──────────────
check(mesh_bc_gap(all_wall, [loose], {"loose_s1": "wall"}) == [],
      "3. a segment with no label and a wall-only geometry raise nothing")
orphan_map = dict(GROUP)
orphan_map["duct_s9"] = "symp"      # a label no segment carries (stale map)
check("symp" not in mesh_bc_gap(all_wall, [geom], orphan_map),
      "3. a mapping whose label no segment carries is not demanded of the mesh")

# ── 4. the .meta trailer stands in for an empty live map ────────────────────
check(mesh_bc_gap(all_wall, [geom], {}) == ["inlet", "outlet"],
      "4. with no live group_bc, the .meta trailer supplies the types")
exp = expected_bc_types([geom], {"duct_s4": "symp"})
check(exp.get("symp") == ["duct_s4"] and "inlet" not in exp,
      f"4. the LIVE map wins over the trailer for the same label (got {exp})")

# ── 5. a .meta newer than the mesh means the mesh predates the edit ─────────
check(stale_meta_files(good, [geom]) == [],
      "5. a mesh newer than the .meta is not flagged")
os.utime(geom + ".meta", (os.path.getmtime(good) + 10,) * 2)
check(stale_meta_files(good, [geom]) == [geom + ".meta"],
      "5. a .meta edited after the mesh flags that geometry")
problems = audit_mesh_bc(good, [geom], GROUP)
check(any("generated before" in p for p in problems),
      "5. ...and the audit reports it even though the BC types are all present "
      "(changing seg 2 from inlet to outlet leaves both names in the file)")

# ── 6. every audit ends with the action that fixes it ───────────────────────
check(problems and "Generate" in problems[-1],
      "6. the audit closes with 'regenerate the mesh', not just a complaint")

# ── 7. nothing to compare -> nothing invented ──────────────────────────────
check(audit_mesh_bc(good, [], GROUP) == [], "7. no geometries -> no problems")
check(audit_mesh_bc(os.path.join(tmp, "nope.bnd"), [geom], GROUP) == [],
      "7. an unreadable .bnd is not evidence of a missing BC")
check(audit_mesh_bc(all_wall, [plain], {}) == [],
      "7. a geometry with no per-segment BCs at all -> no problems")

# ── 8. the controllers are wired to it ──────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                                 # noqa: E402
from app.controllers.mesh_export_ctrl import MeshExportControllerMixin   # noqa: E402
from app.controllers.solver_ctrl import SolverControllerMixin            # noqa: E402
from app.models.mesh_config import MeshConfig                            # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)   # is_headless() reads it
# A mesh newer than every .meta, including the one check 5 aged forward.
fresh = write_bnd("fresh.bnd", [(1, "wall"), (2, "inlet"), (3, "outlet")])
os.utime(fresh, (os.path.getmtime(geom + ".meta") + 60,) * 2)


class _Ctrl(MeshExportControllerMixin, SolverControllerMixin):
    def __init__(self, cfg):
        self.global_mesh_config = cfg
        self.main_window = None          # headless: confirm() never reaches it


cfg = MeshConfig()
cfg.geom_files = [geom, loose]
cfg.geom_roles = {loose: {"role": "seed"}}      # a seed has no boundary patches
cfg.group_bc = dict(GROUP, loose_s1="symp")     # symp is in NO mesh below
ctrl = _Ctrl(cfg)
check(ctrl.mesh_bc_problems(fresh) == [],
      "8. the controller is silent about a mesh that carries the BCs")
check(any("outlet" in p for p in ctrl.mesh_bc_problems(all_wall)),
      "8. ...and reports the all-`wall` grid the user actually solved")
check(not any("symp" in p for p in ctrl.mesh_bc_problems(all_wall)),
      "8. refinement seeds are excluded — they have no boundary patches, so an "
      "assignment on one must not be demanded of the mesh")
check(ctrl._confirm_mesh_bc_state(all_wall) is True,
      "8. a HEADLESS run is never blocked by the prompt (batch/CI regenerate "
      "the mesh in the same pass)")

print(("\nRESULT: " + ("ALL PASS" if not _FAILS else f"{len(_FAILS)} FAIL")), flush=True)
sys.exit(1 if _FAILS else 0)
