#!/usr/bin/env python3
"""The GUI workspace that travels inside a portable case package.

``run_case.sh`` reruns the SOLVER. Nothing reopened the case in the GUI: there
is no importer for an exported package, so "load the case I exported" had no
answer — the engineer had to keep a separate ``.hws`` and remember which folder
it belonged to. USER-REQUESTED (2026-08-13): ask on export, and make the
workspace point at the exported case.

Pointing it there is the whole difficulty, and there are exactly three ways to
get it wrong:

 * **Re-point something the package does not carry.** The allow-list ships
   solver inputs only, and it drops files the user declined (the restart dump).
   A path rewritten to a name that is not in the folder is worse than one left
   alone: it looks local and resolves to nothing.
 * **Miss the same file under a different spelling.** ``results/`` vs
   ``Results/`` on a case-insensitive volume, or a symlinked scratch directory,
   is the SAME file — so the match is on ``(st_dev, st_ino)``, not on the string.
 * **Strand the paths a second time.** A package exists to be copied elsewhere,
   which invalidates every absolute path in it all over again. So the workspace
   records the root it was written for and re-points itself on load.

Also pinned: the export asks before writing one, the manifest names it (the
package's standing promise that nothing arrives unaccounted for), and paths that
CANNOT be re-pointed — the CAD source, the mesh — are reported rather than
mangled or silently left.

Run:  python3 tools/PreProcessor/tests/test_case_workspace_export.py
"""
import json
import os
import shutil
import sys
import tempfile
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >180s", flush=True)
    os._exit(99)


_wd = threading.Timer(180, _watchdog)
_wd.daemon = True
_wd.start()

from app.services import case_export, case_workspace  # noqa: E402


# A case laid out as solver_case.prepare_case_dir leaves one. Built here rather
# than imported from test_case_export: that file is a script with no __main__
# guard, so importing it runs the whole suite and exits.
def build_case(root):
    case = os.path.join(root, "mycase")
    for sub in ("grid", "work", "dll"):
        os.makedirs(os.path.join(case, sub), exist_ok=True)
    away = os.path.join(root, "elsewhere")
    src = os.path.join(root, "dll_src")
    os.makedirs(away, exist_ok=True)
    os.makedirs(src, exist_ok=True)

    def w(rel, text, base=case):
        p = os.path.join(base, *rel.split("/"))
        with open(p, "w") as f:
            f.write(text)
        return p

    for rel in ("grid/mycase.grid", "grid/mycase.bc", "grid/mycase.bc.def",
                "grid/input.vrt", "grid/input.cel", "grid/input.bnd",
                "grid/para.in", "work/mycase.bc.def", "work/phi.dat",
                "work/binDumpZ.dat.gui"):
        w(rel, rel)
    w("dll/user.so", "ELF")
    w("user.cc", "// source", base=src)
    probe = w("probe_points.dat", "0.5 0.5", base=away)
    w("work/input.in", "\n".join([
        '   grid_fname  "../grid/mycase.grid"',
        '   bc_fname    "../grid/mycase.bc"',
        '   init_cond_use_zdump_fn  "../dll/user.so"',
        '   immersed_solid                       true',
        f'   probe_points_def_fn  "{probe}"',
        '   zdump_fn_restart  "binDumpZ.dat.gui"']) + "\n")
    return case, src, probe


tmp = tempfile.mkdtemp(prefix="hybmesh_ws_export_")
case, dll_src, probe = build_case(tmp)
dest = os.path.join(tmp, "out")

# A workspace as the GUI would hand one over: solver paths INSIDE the case, plus
# the CAD/mesh paths that are no part of a solver case and cannot travel.
cad = os.path.join(tmp, "geom.dat")
with open(cad, "w") as f:
    f.write("0 0\n1 0\n")
mesh_vtk = os.path.join(tmp, "mesh.vtk")
with open(mesh_vtk, "w") as f:
    f.write("# vtk\n")

workspace = {
    "format_version": 2,
    "active_idx": 0,
    "sessions": [{
        "file_path": cad,
        "display_name": "geom",
        # Bulk arrays: skipped by the walk, and must survive it untouched.
        "original_points": [[0.0, 0.0], [1.0, 0.0]],
        "project_config": {"input_file": cad, "output_file": cad,
                           "segments": [{"id": 0, "type": "line",
                                         "group_bc": "inlet"}]},
        "vtk_path": mesh_vtk,
    }],
    "project": {
        "solver_config": {
            "case_name": "mycase",
            "work_dir": os.path.join(case, "work"),
            "input_vrt_file": os.path.join(case, "grid", "input.vrt"),
            "input_cel_file": os.path.join(case, "grid", "input.cel"),
            "input_bnd_file": os.path.join(case, "grid", "input.bnd"),
            "phi_file": os.path.join(case, "work", "phi.dat"),
            "restart_dump": os.path.join(case, "work", "binDumpZ.dat.gui"),
            "probe_file": probe,
            "length_unit": "m",
            "bc_geom": "wall",
        },
        "mesh_config": {"output_file": mesh_vtk, "bl_layers": 5},
        "vtk_path": mesh_vtk,
    },
}

plan = case_export.plan_export(case, dll_src_dirs=(dll_src,),
                               include_restart=True)
ws, report = case_workspace.build_case_workspace(workspace, plan, dest)
sol = ws["project"]["solver_config"]

# ── 1. solver paths now point into the package ────────────────────────────
check(sol["input_vrt_file"] == os.path.join(dest, "grid", "input.vrt")
      and sol["input_bnd_file"] == os.path.join(dest, "grid", "input.bnd"),
      "1. the getPGrid inputs point at the exported grid/, not at the case they "
      "were exported from")
check(sol["phi_file"] == os.path.join(dest, "work", "phi.dat"),
      "1. the IBM phase field follows into the package too")
check(sol["probe_file"] == os.path.join(dest, "work", "probe_points.dat"),
      "1. a file that lived OUTSIDE the case is re-pointed at where the export "
      "staged it (work/), the same rewrite input.in gets")
check(report.n_repointed >= 5,
      f"1. and the count is reported for the user ({report.n_repointed})")

# ── 2. only what the package actually carries ─────────────────────────────
check(ws["sessions"][0]["file_path"] == cad
      and ws["project"]["mesh_config"]["output_file"] == mesh_vtk,
      "2. the CAD source and the mesh are NOT in a solver package, so they are "
      "left exactly as they were — a rewritten path would name a missing file")
outside = {p for _k, p in report.outside}
check(cad in outside and mesh_vtk in outside,
      f"2. ...and they are REPORTED as outside the package, not silently kept "
      f"({sorted(os.path.basename(p) for p in outside)})")
check(all("wall" != p and "inlet" != p and "m" != p for _k, p in report.outside),
      "2. a BC name / unit label is not mistaken for a stranded path — the "
      "report needs a separator and an existing file, not just a string")
check(os.path.join(case, "work") not in outside,
      "2. work_dir is a DIRECTORY — a breadcrumb prepare_case_dir rebuilds from "
      "the case name — so it is not reported as data left behind")

# The restart dump is the case where a plan the user did not approve would lie.
plan_no_dump = case_export.plan_export(case, dll_src_dirs=(dll_src,),
                                       include_restart=False)
ws2, _r2 = case_workspace.build_case_workspace(workspace, plan_no_dump, dest)
check(ws2["project"]["solver_config"]["restart_dump"]
      == os.path.join(case, "work", "binDumpZ.dat.gui"),
      "2. declining the restart dump leaves its path alone — re-pointing it "
      "would send the solver at a file the package deliberately does not hold")
check(sol["restart_dump"] == os.path.join(dest, "work", "binDumpZ.dat.gui"),
      "2. (control) with the dump included, that same path IS re-pointed")

# ── 3. matched by file identity, not by string ────────────────────────────
link = os.path.join(tmp, "case_link")
identity_ok = True
try:
    os.symlink(case, link)
except (OSError, NotImplementedError):
    identity_ok = False
if identity_ok:
    aliased = {"project": {"solver_config": {
        "input_vrt_file": os.path.join(link, "grid", "input.vrt")}}}
    ws3, _r3 = case_workspace.build_case_workspace(aliased, plan, dest)
    check(ws3["project"]["solver_config"]["input_vrt_file"]
          == os.path.join(dest, "grid", "input.vrt"),
          "3. the same file reached through a symlinked case directory is still "
          "recognised — the map is keyed by (st_dev, st_ino), not by the string")
else:
    print("SKIP 3. symlinks unavailable on this platform", flush=True)

# ── 4. bulk arrays are untouched (and not walked) ─────────────────────────
check(ws["sessions"][0]["original_points"] == [[0.0, 0.0], [1.0, 0.0]],
      "4. the geometry arrays come through byte-identical — they hold thousands "
      "of floats and never a path, so the walk skips them by name")

# ── 5. the package is written, with the workspace in it and in the manifest ─
text = json.dumps(ws, indent=2, allow_nan=False)
summary = case_export.export_case(
    case, dest, dll_src_dirs=(dll_src,), include_restart=True, plan=plan,
    extra_files=[("mycase.hws", text, "GUI workspace — File > Load Workspace")])
hws_path = os.path.join(dest, "mycase.hws")
check(os.path.isfile(hws_path),
      "5. the .hws lands in the export folder next to run_case.sh")
man = open(os.path.join(dest, "MANIFEST.txt"), encoding="utf-8").read()
check("mycase.hws" in man and "ALSO WRITTEN BY THE EXPORT" in man,
      "5. the manifest names it under its own heading — generated here, not "
      "copied out of the case, and never silently present")
check("File > Load Workspace" in man,
      "5. ...and says what to do with it")
check(summary["n_files"] == len(plan.items),
      "5. the INCLUDED count still means 'files copied from the case', so the "
      "generated workspace does not inflate it")

# An extra that tries to escape the package is refused, not written.
esc_dest = os.path.join(tmp, "out_escape")
esc = case_export.export_case(
    case, esc_dest, dll_src_dirs=(dll_src,),
    extra_files=[("../evil.hws", "x", "nope")])
check(not os.path.exists(os.path.join(tmp, "evil.hws"))
      and any("outside the export folder" in w for w in esc["plan"].warnings),
      "5. an extra whose name would land outside the folder is refused and "
      "warned about — an export must not write to the machine it is reading")

# ── 6. the package survives being moved ───────────────────────────────────
moved_dir = os.path.join(tmp, "moved_elsewhere")
shutil.copytree(dest, moved_dir)
loaded = json.load(open(os.path.join(moved_dir, "mycase.hws"), encoding="utf-8"))
n = case_workspace.rebase_case_workspace(
    loaded, os.path.join(moved_dir, "mycase.hws"))
msol = loaded["project"]["solver_config"]
check(n >= 5 and msol["input_vrt_file"] == os.path.join(moved_dir, "grid",
                                                        "input.vrt"),
      f"6. scp'ing the folder somewhere else re-points every path at the new "
      f"location on load ({n} path(s))")
check(msol["probe_file"] == os.path.join(moved_dir, "work", "probe_points.dat"),
      "6. ...including the staged copies, so nothing is left aimed at the "
      "exporting machine")
check(loaded["sessions"][0]["file_path"] == cad,
      "6. a path that was never inside the package is not dragged into it by "
      "the rebase either")

again = json.load(open(os.path.join(moved_dir, "mycase.hws"), encoding="utf-8"))
case_workspace.rebase_case_workspace(
    again, os.path.join(moved_dir, "mycase.hws"))
check(case_workspace.rebase_case_workspace(
      again, os.path.join(moved_dir, "mycase.hws")) == 0,
      "6. rebasing an already-rebased workspace is a no-op — the stamp is "
      "updated, so re-opening in place never rewrites anything")

plain = {"format_version": 2, "sessions": [], "project": {}}
check(case_workspace.rebase_case_workspace(plain, "/tmp/whatever.hws") == 0
      and case_workspace.EXPORT_ROOT_KEY not in plain,
      "6. an ordinary saved workspace carries no stamp, so loading one is "
      "untouched by any of this")

# ── 7. the GUI asks first, and one builder makes both workspaces ──────────
ctrl_src = open(os.path.join(_GUI, "app", "controllers", "case_export_ctrl.py"),
                encoding="utf-8").read()
check("want_hws = confirm(" in ctrl_src,
      "7. the export ASKS before writing a workspace (USER-REQUESTED) rather "
      "than always producing one")
io_src = open(os.path.join(_GUI, "app", "controllers", "session_io_ctrl.py"),
              encoding="utf-8").read()
check("def workspace_dict(self)" in io_src
      and "self.workspace_dict()" in io_src
      and "self.workspace_dict()" in ctrl_src,
      "7. Save Workspace and the export take the SAME snapshot, so an exported "
      "workspace can never describe less than a saved one")
check("rebase_case_workspace(workspace_data, file_path)" in io_src,
      "7. and every .hws load goes through the rebase, or a moved package "
      "would still open with the exporting machine's paths")

# ── 8. the whole loop, through the real GUI ───────────────────────────────
# The service being right is half of it. This drives the actual Export Case slot
# and then the actual Load Workspace, because the question behind the feature
# was "how do I reopen the case I exported" — and only this proves the answer.
from PyQt6.QtWidgets import QApplication, QFileDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402

gui_case, gui_src, gui_probe = build_case(os.path.join(tmp, "gui"))
gui_dest = os.path.join(tmp, "gui", "exported")

ctrl = AppController()
cfg = ctrl.global_solver_config
cfg.case_name = "mycase"
cfg.work_dir = os.path.join(gui_case, "work")
cfg.input_vrt_file = os.path.join(gui_case, "grid", "input.vrt")
cfg.input_bnd_file = os.path.join(gui_case, "grid", "input.bnd")
cfg.ibm_phi_file = os.path.join(gui_case, "work", "phi.dat")
# Through the panel, because that is the only way a person sets these — and
# _collect_project_state re-syncs panel -> model first, so a model written
# behind the panel's back is overwritten with the blank widgets before it is
# ever serialised (controllers/panel_sync_ctrl.py: the model is the truth, and
# the panel is what keeps it true).
ctrl.push_panel_config(ctrl.main_window.solver_config_panel, cfg)

_saved = QFileDialog.getSaveFileName
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (gui_dest, ""))
try:
    ctrl.export_portable_case()
finally:
    QFileDialog.getSaveFileName = _saved

gui_hws = os.path.join(gui_dest, "exported.hws")
check(os.path.isfile(gui_hws),
      "8. the Export Case slot writes the workspace into the package (headless "
      "answers yes; a person is asked)")
check(os.path.isfile(os.path.join(gui_dest, "run_case.sh")),
      "8. ...alongside run_case.sh — the package now serves both 'rerun the "
      "solver' and 'reopen it in the GUI'")

# Move the package, exactly as scp'ing it to another machine would.
gui_moved = os.path.join(tmp, "gui", "moved")
shutil.copytree(gui_dest, gui_moved)
shutil.rmtree(gui_dest)

_saved_open = QFileDialog.getOpenFileName
QFileDialog.getOpenFileName = staticmethod(
    lambda *a, **k: (os.path.join(gui_moved, "exported.hws"), ""))
try:
    ctrl.load_workspace()
finally:
    QFileDialog.getOpenFileName = _saved_open

back = ctrl.global_solver_config
check(back.input_bnd_file == os.path.join(gui_moved, "grid", "input.bnd")
      and back.input_vrt_file == os.path.join(gui_moved, "grid", "input.vrt"),
      "8. loading it from the MOVED folder points the Solver stage at the grid "
      "sitting right there — the original case is gone and nothing needed it")
check(back.ibm_phi_file == os.path.join(gui_moved, "work", "phi.dat"),
      "8. ...and at the phi field in the same package")
check(os.path.isfile(back.input_bnd_file),
      "8. every re-pointed path names a file that actually exists — the whole "
      "point of matching against what the package carries")

shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
# os._exit, like the other 41 scripts here: this test builds the main window,
# and Qt's teardown under the offscreen platform crashes on a machine with no GPU
# ("QOpenGLWidget is not supported on this platform"). Every check passed and the
# script's own result was 0, yet the process exited non-zero and CI read it as a
# failing test. Skipping interpreter finalization is what the rest of the suite
# already does for exactly this.
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED")
    for m in _FAILS:
        print("  - " + m)
    sys.stdout.flush()
    os._exit(1)
print("\nRESULT: ALL PASS")
sys.stdout.flush()
os._exit(0)
