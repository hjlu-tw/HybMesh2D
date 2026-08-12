#!/usr/bin/env python3
"""Portable case export: what travels to another machine, and what does not.

A solver case directory mixes ~18 MB of inputs with ~110 MB of output. Handing
someone the whole thing ships results nobody asked for; handing them a hand-picked
subset loses whichever input was not on the picker's mental list. Two failure
modes decide whether the package actually reruns:

 * **A missing input.** So the selection is an ALLOW-list (an output can never
   sneak in by being new) and everything rejected is NAMED in the manifest —
   a skipped input is a visible line, not a surprise on the far machine.
 * **A path that only exists here.** Every quoted value in ``input.in`` is a file
   path, and the GUI writes an absolute one for any file the user browsed to.
   Those must be staged into the package and the reference rewritten, or the run
   dies on a path belonging to somebody else's home directory.

What is pinned here:
  1. The three subdirectories, and outputs excluded / named as skipped.
  2. dll/*.so is paired with the .cc it was compiled from (which lives OUTSIDE
     the case, in results/solver/dll_src) — the binary alone is not portable.
  3. Absolute paths in input.in are staged + rewritten; in-case relative ones are
     left exactly as they were.
  4. A reference to a file that does not exist warns instead of silently dropping.
  5. The restart zone dump is opt-out, and named as an output when excluded.
  6. run_case.sh is valid sh and runs the solver from work/.
  7. Refusing to export into the case itself (which would copy into the source).
  8. The tarball, and a manifest that accounts for every file.

Run:  python3 tools/PreProcessor/tests/test_case_export.py
"""
import os
import shutil
import subprocess
import sys
import tarfile
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

from app.services import case_export  # noqa: E402


# --------------------------------------------------------------------------- #
def build_case(root, *, with_outputs=True, abs_refs=True, restart_dump=True,
               restart_ref=False):
    """A case laid out exactly as solver_case.prepare_case_dir leaves one."""
    case = os.path.join(root, "mycase")
    for sub in ("grid", "work", "dll"):
        os.makedirs(os.path.join(case, sub), exist_ok=True)
    away = os.path.join(root, "elsewhere")
    os.makedirs(away, exist_ok=True)
    src = os.path.join(root, "dll_src")
    os.makedirs(src, exist_ok=True)

    def w(rel, text, base=case):
        p = os.path.join(base, *rel.split("/"))
        with open(p, "w") as f:
            f.write(text)
        return p

    # Inputs.
    for rel in ("grid/mycase.grid", "grid/mycase.bc", "grid/mycase.bc.def",
                "grid/input.vrt", "grid/input.cel", "grid/input.bnd",
                "grid/para.in", "work/mycase.bc.def", "work/phi.dat"):
        w(rel, rel)
    w("dll/user.so", "ELF")
    w("user.cc", "// source", base=src)
    probe = w("probe_points.dat", "0.5 0.5", base=away)
    if restart_dump:
        w("work/binDumpZ.dat.gui", "DUMP")
    # Outputs a finished run leaves behind.
    if with_outputs:
        for rel in ("work/xtecp_sol_allz.dat.gui", "work/tWall_values.dat.gui",
                    "work/unicones.enorm.gui", "work/vsurface_qty.dat.gui",
                    "work/xxprocess_bc_segments_tmpyy0", "grid/mesh_tecplot.dat"):
            w(rel, "RESULT DATA")
    w("work/scratch.note", "?")          # neither input nor known output

    lines = ['   grid_fname  "../grid/mycase.grid"',
             '   bc_fname    "../grid/mycase.bc"',
             '   init_cond_use_zdump_fn  "../dll/user.so"']
    if abs_refs:
        lines += [f'   probe_points_def_fn  "{probe}"',
                  '   zdump_fn_restart  "/nowhere/vanished.dat"']
    if restart_ref:
        # A real restart run: input.in names the dump that lives in work/.
        lines += ['   zdump_fn_restart  "binDumpZ.dat.gui"']
    w("work/input.in", "\n".join(lines) + "\n")
    return case, src, probe


tmp = tempfile.mkdtemp(prefix="hybmesh_export_")
case, dll_src, probe = build_case(tmp)
dest = os.path.join(tmp, "out")

summary = case_export.export_case(case, dest, dll_src_dirs=(dll_src,),
                                  make_tarball=True)
plan = summary["plan"]
rels = sorted(i.rel for i in plan.items)
skipped_out = {r for r, _ in plan.skipped_output}
skipped_other = {r for r, _ in plan.skipped_other}


def on_disk(*parts):
    return os.path.exists(os.path.join(dest, *parts))


# ── 1. the three folders, inputs in / outputs out ─────────────────────────
check(all(on_disk(d) for d in ("grid", "work", "dll")),
      "1. the export has grid/ work/ dll/, the layout the solver expects")
check(all(on_disk(*p.split("/")) for p in
          ("grid/mycase.grid", "grid/mycase.bc", "grid/mycase.bc.def",
           "grid/input.vrt", "grid/input.cel", "grid/input.bnd", "grid/para.in",
           "work/input.in", "work/mycase.bc.def", "work/phi.dat")),
      "1. every input travels: the grid+bc, the .def table, the getPGrid "
      "sources, input.in and the IBM phi field")
check(not any(on_disk("work", n) for n in
              ("xtecp_sol_allz.dat.gui", "tWall_values.dat.gui",
               "unicones.enorm.gui", "vsurface_qty.dat.gui"))
      and not on_disk("grid", "mesh_tecplot.dat"),
      "1. no result file is copied — that is the whole point of exporting "
      "inputs rather than the directory")
check({"work/xtecp_sol_allz.dat.gui", "work/tWall_values.dat.gui",
       "grid/mesh_tecplot.dat"} <= skipped_out,
      "1. skipped outputs are NAMED, so nothing is dropped invisibly")
check("work/scratch.note" in skipped_other,
      "1. a file that is neither a known input nor a known output is listed "
      "separately — the person can then judge it instead of never seeing it")

# ── 2. the DLL source ─────────────────────────────────────────────────────
check(on_disk("dll", "user.so") and on_disk("dll", "user.cc"),
      "2. the .so ships WITH the .cc it was built from (pulled from dll_src, "
      "which sits outside the case) — a binary alone only loads on this arch")

# ── 3./4. input.in path handling ──────────────────────────────────────────
text = open(os.path.join(dest, "work", "input.in")).read()
check('"../grid/mycase.grid"' in text and '"../dll/user.so"' in text,
      "3. references that already point inside the case are left untouched")
check(on_disk("work", "probe_points.dat") and '"./probe_points.dat"' in text
      and probe not in text,
      "3. a file referenced by ABSOLUTE path is staged into work/ and the "
      "reference rewritten — an absolute path is exactly what breaks elsewhere")
check(any("vanished.dat" in w for w in plan.warnings),
      "4. a reference to a file that does not exist here is WARNED about, not "
      "silently dropped")
check('"/nowhere/vanished.dat"' in text,
      "4. ... and left verbatim, so the exported case fails the same way this "
      "one would rather than differently")

# ── 5. the restart dump is opt-out ────────────────────────────────────────
check(on_disk("work", "binDumpZ.dat.gui"),
      "5. the restart zone dump ships by default (a restart run needs it as "
      "an input)")
no_dump = case_export.plan_export(case, dll_src_dirs=(dll_src,),
                                  include_restart=False)
check(not no_dump.has("work/binDumpZ.dat.gui")
      and any(r == "work/binDumpZ.dat.gui" for r, _ in no_dump.skipped_output),
      "5. excluding it moves it to the skipped-output list rather than making "
      "it disappear from the record")

# ── 6. the run script ─────────────────────────────────────────────────────
script = os.path.join(dest, "run_case.sh")
check(os.access(script, os.X_OK), "6. run_case.sh is executable")
check(subprocess.run(["sh", "-n", script]).returncode == 0,
      "6. run_case.sh is valid POSIX sh")
body = open(script).read()
check('cd "$HERE/work"' in body and "input.in" in body and "--regrid" in body,
      "6. it runs the solver from work/ (where the relative grid paths resolve) "
      "and offers to rebuild the grid, since *.grid is c_binary")
check("unicones" in body and not on_disk("work", "unicones"),
      "6. the solver binary is referenced but deliberately NOT shipped")
check("REBUILD_DLL" in body,
      "6. it can recompile the DLL, because a .so built here will not load on "
      "a different architecture")

# ── 7. refuse to export into the case ─────────────────────────────────────
refused = False
try:
    case_export.export_case(case, os.path.join(case, "portable"))
except case_export.CaseExportError:
    refused = True
check(refused,
      "7. exporting INTO the case is refused — it would copy the case into "
      "itself while walking it")

missing = False
try:
    case_export.plan_export(os.path.join(tmp, "not_a_case"))
except case_export.CaseExportError:
    missing = True
check(missing, "7. a directory that is not a case is rejected up front")

empty = os.path.join(tmp, "empty_case")
os.makedirs(os.path.join(empty, "work"), exist_ok=True)
with open(os.path.join(empty, "work", "xtecp_sol_allz.dat.x"), "w") as f:
    f.write("only output")
nothing = False
try:
    case_export.export_case(empty, os.path.join(tmp, "empty_out"))
except case_export.CaseExportError:
    nothing = True
check(nothing,
      "7. a case holding only outputs exports nothing and says so, instead of "
      "writing an empty folder that looks like success")

# ── 8. tarball + manifest ─────────────────────────────────────────────────
tarball = summary["tarball"]
check(tarball.endswith(".tar.gz") and os.path.exists(tarball),
      "8. the optional archive is written next to the folder")
with tarfile.open(tarball) as tf:
    names = tf.getnames()
check(any(n.endswith("work/input.in") for n in names)
      and any(n.endswith("run_case.sh") for n in names)
      and not any("xtecp_sol" in n for n in names),
      "8. the archive holds the same selection as the folder")

manifest = open(os.path.join(dest, "MANIFEST.txt")).read()
check(all(r in manifest for r in rels),
      "8. the manifest lists every included file")
check("SKIPPED" in manifest and "xtecp_sol_allz.dat.gui" in manifest,
      "8. ... and every skipped one, with the reason it was skipped")
check("run_case.sh" in manifest and "REBUILD_DLL" in manifest,
      "8. ... and tells the reader how to run it on the far machine")
check(str(probe) in manifest and "./probe_points.dat" in manifest,
      "8. ... and records each rewritten path, so a surprising path change is "
      "auditable rather than invisible")

# ── 9. the GUI path (dialogs stubbed) ─────────────────────────────────────
# The service is only half the feature: the button has to reach it with the
# right case, and the answers a person gives have to arrive intact.
from PyQt6.QtWidgets import QApplication, QFileDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402

gui_case, gui_src, _ = build_case(os.path.join(tmp, "gui"))
gui_dest = os.path.join(tmp, "gui", "exported")

ctrl = AppController()
mw = ctrl.main_window
check(hasattr(mw, "solver_export_case_btn")
      and mw.solver_export_case_btn in mw.solver_tb_widgets,
      "9. the Export Case button rides the Solver-stage toolbar (registered in "
      "solver_tb_widgets, which is what the per-stage layout reads)")
mw.mode_combo.setCurrentIndex(3)
app.processEvents()
check(mw.solver_export_case_btn.isVisibleTo(mw),
      "9. ... and is visible in the Solver stage")
mw.mode_combo.setCurrentIndex(0)
app.processEvents()
check(not mw.solver_export_case_btn.isVisibleTo(mw),
      "9. ... and hidden in the others, like every other stage-owned control")

menu_labels = [a.text() for m in mw.menuBar().actions() if m.menu()
               for a in m.menu().actions()]
check(any("Portable Case" in t for t in menu_labels),
      "9. it is also reachable from the Solver menu, not only the toolbar")

# Drive the real slot with the two dialogs answered.
ctrl.global_solver_config.work_dir = os.path.join(gui_case, "work")
_saved = QFileDialog.getSaveFileName
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (gui_dest, ""))
try:
    ctrl.export_portable_case()
finally:
    QFileDialog.getSaveFileName = _saved
check(os.path.exists(os.path.join(gui_dest, "work", "input.in"))
      and os.path.exists(os.path.join(gui_dest, "run_case.sh")),
      "9. the slot exports the case the Solver stage is pointed at (its "
      "work_dir, which already carries any auto-versioned <case>_002 name)")
check(not os.path.exists(os.path.join(gui_dest, "work",
                                      "xtecp_sol_allz.dat.gui")),
      "9. ... with the same input-only selection as the service")
check(not os.path.exists(gui_dest.rstrip("/") + ".tar.gz"),
      "9. headless answers 'no' to the archive prompt instead of blocking on a "
      "modal nobody can click")

# ── 10. the export folder may not CONTAIN the case either ─────────────────
# Only the dest-inside-case direction was guarded. Naming results/solver as the target
# while exporting results/solver/mycase wrote grid/, work/, run_case.sh and MANIFEST.txt
# into the shared cases directory — and with the tarball option, archived every other
# case's hundreds of MB of output with them.
try:
    case_export.export_case(case, os.path.dirname(os.path.abspath(case)))
    check(False, "10. exporting INTO the case's parent must be refused")
except case_export.CaseExportError as e:
    check("contain" in str(e).lower(),
          f"10. a destination that contains the case is refused, naming why ({e})")
check(not os.path.isdir(os.path.join(tmp, "grid")),
      "10. ...and nothing was written into it before the refusal")

# ── 11. the allow-list is a list, not a glob ──────────────────────────────
# `_WORK_KEEP`'s ".in" suffix accepted every *.in in work/, which both made its own
# "input.in" entry dead and broke the module's stated promise that a new output cannot
# sneak in. A file kept by REFERENCE (input.in naming it) is the supported route.
stray = os.path.join(case, "work", "monitor.in")
with open(stray, "w") as f:
    f.write("not an input")
p11 = case_export.plan_export(case)
check(not p11.has("work/monitor.in"),
      "11. an unrecognised *.in in work/ is NOT copied just for its extension")
check(any(rel == "work/monitor.in" for rel, _s in p11.skipped_other),
      f"11. ...it is NAMED as a skip, which is how it gets noticed "
      f"({[r for r, _ in p11.skipped_other]})")
check(p11.has("work/input.in"), "11. while input.in itself still ships")
os.remove(stray)

for _name, _keep in (("_GRID_KEEP", case_export._GRID_KEEP),
                     ("_WORK_KEEP", case_export._WORK_KEEP),
                     ("_DLL_KEEP", case_export._DLL_KEEP)):
    _exact, _sfx = _keep
    _subsumed = sorted(n for n in _exact if _sfx and n.endswith(_sfx))
    check(not _subsumed,
          f"11. {_name}'s suffixes must not subsume its own exact names — a suffix that "
          f"does turns the allow-list into a glob, silently ({_subsumed})")

# ── 12. a declined file is not smuggled back in by reference ──────────────
ref_case, ref_src, _ = build_case(os.path.join(tmp, "restartref"), restart_ref=True)
p_with = case_export.plan_export(ref_case, include_restart=True)
check(p_with.has("work/binDumpZ.dat.gui"),
      "12. (precondition) with include_restart the dump ships")
p_without = case_export.plan_export(ref_case, include_restart=False)
check(not p_without.has("work/binDumpZ.dat.gui"),
      "12. include_restart=False is respected even though input.in references the dump "
      "— 'referenced by input.in' must not overrule an explicit exclusion")
check(any("deliberately NOT exported" in w for w in p_without.warnings),
      f"12. ...and the reference is reported rather than silently dropped "
      f"({p_without.warnings})")
_inc = {i.rel for i in p_without.items}
_skip = {rel for rel, _s in p_without.skipped_output}
check(not (_inc & _skip),
      f"12. no path is listed as both INCLUDED and SKIPPED in one plan ({_inc & _skip})")

# ── 13. every write is explicitly UTF-8 ───────────────────────────────────
# MANIFEST.txt embeds the case path verbatim and the UI ships a zh_TW translation, so a
# platform-default encoding fails on a non-ASCII path AFTER every file has been copied.
src_txt = open(os.path.join(_GUI, "app", "services", "case_export.py"),
               encoding="utf-8").read()
check('"w") as f:' not in src_txt and src_txt.count('"w", encoding="utf-8"') == 3,
      "13. all three writes (manifest, run script, rewritten input.in) name UTF-8, like "
      "every read in the module already does")
uni_case, uni_src, _ = build_case(os.path.join(tmp, "案例"))
uni_dest = os.path.join(tmp, "匯出")
case_export.export_case(uni_case, uni_dest, dll_src_dirs=(uni_src,))
man = open(os.path.join(uni_dest, "MANIFEST.txt"), encoding="utf-8").read()
check("案例" in man,
      "13. ...and a case exported from a non-ASCII path really round-trips")

shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
