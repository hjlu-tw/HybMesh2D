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
  5. The restart zone dump travels only when input.in restarts from it, and is
     named as a skipped output otherwise.
  6. run_case.sh is valid sh, runs the solver from work/, and hard-codes no
     compiler.
  7. Refusing to export into the case itself (which would copy into the source).
  8. The tarball, and a manifest that accounts for every file.
 14. grid/para.in travels as grid/getPGrid.in, and run_case.sh reads THAT name.
 15. work/phi.dat and dll/* travel only when the run actually uses them: a reused
     case directory keeps an earlier immersed-solid run's leftovers, and the
     allow-list matches on NAME alone.

USER-REPORTED (2026-08-12), all three in section 5/6/14: "rename grid/para.in to
something obvious"; "why is work/binDumpZ.dat.gui in there?"; and "run_case.sh
uses g++ — what if the other machine wants icpc? Don't hard-code it, suggest it."

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
               restart_ref=False, dll_ref=True, immersed=False):
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
             '   bc_fname    "../grid/mycase.bc"']
    # A DLL is loaded only when input.in names it, and phi.dat is read BY such a
    # DLL — so a case with neither is one where both are fossils of an earlier run.
    if dll_ref:
        lines += ['   init_cond_use_zdump_fn  "../dll/user.so"']
    if immersed:
        lines += ['   immersed_solid                       true']
    if abs_refs:
        lines += [f'   probe_points_def_fn  "{probe}"',
                  '   zdump_fn_restart  "/nowhere/vanished.dat"']
    if restart_ref:
        # A real restart run: input.in names the dump that lives in work/.
        lines += ['   zdump_fn_restart  "binDumpZ.dat.gui"']
    w("work/input.in", "\n".join(lines) + "\n")
    return case, src, probe


tmp = tempfile.mkdtemp(prefix="hybmesh_export_")
# restart_ref: this case's input.in really does restart from the dump, which is
# what makes the dump an INPUT of this run (see section 5).
case, dll_src, probe = build_case(tmp, restart_ref=True)
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
           "grid/input.vrt", "grid/input.cel", "grid/input.bnd",
           "grid/getPGrid.in",
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

# ── 5. the restart dump travels only when the run restarts from it ────────
# USER-REPORTED: "why is there a work/binDumpZ.dat.gui?" — it is an OUTPUT that a
# restart run reads back, and it is the largest file in the case, so shipping it
# unasked is how a 100 MB package appears with nothing to explain it.
check(on_disk("work", "binDumpZ.dat.gui"),
      "5. the restart zone dump ships when input.in restarts from it — then it "
      "IS an input of this run")
check(any(i.rel.endswith("binDumpZ.dat.gui") and "input.in" in i.reason
          for i in plan.items),
      "5. ... and the manifest reason says WHY it is there, not just that it is")

no_ref_case, no_ref_src, _ = build_case(os.path.join(tmp, "noref"),
                                        restart_ref=False)
auto = case_export.plan_export(no_ref_case, dll_src_dirs=(no_ref_src,))
check(not auto.has("work/binDumpZ.dat.gui")
      and any(r == "work/binDumpZ.dat.gui" for r, _ in auto.skipped_output),
      "5. a case that does NOT restart leaves the dump behind by default, and "
      "still names it in the skipped list rather than dropping it silently")
forced = case_export.plan_export(no_ref_case, dll_src_dirs=(no_ref_src,),
                                 include_restart=True)
check(forced.has("work/binDumpZ.dat.gui"),
      "5. include_restart=True still carries it — someone who wants to continue "
      "the run over there can ask for it")
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

# USER-REPORTED: "what if the other machine uses icpc? Don't hard-code it."
check("CXX=${CXX:-g++}" in body and '"$CXX"' in body,
      "6. the compiler is a DEFAULT, not a decision — CXX overrides it, which "
      "is the name an HPC user already expects")
check("CXXFLAGS" in body and "CXX=icpc" in body,
      "6. ... and the script says so in its own comments, so the suggestion "
      "arrives with the package instead of living in our heads")
check(subprocess.run(
          ["sh", "-c", f"CXX=echo REBUILD_DLL=1 sh -n {script}"]).returncode == 0,
      "6. the script still parses with the compiler overridden")

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

# ── 14. para.in travels under a name that says what reads it ──────────────
# USER-REPORTED: "grid/para.in — give it a more intuitive name." It is getPGrid's
# stdin input, and there is a second para.in in this project (the STL3d stage),
# so the copy is named after the program that consumes it. run_case.sh must feed
# it that same name: a rename the script does not know about breaks --regrid.
check(not on_disk("grid", "para.in"),
      "14. the ambiguous para.in name does not reach the package")
check(open(os.path.join(dest, "grid", "getPGrid.in")).read() == "grid/para.in",
      "14. grid/getPGrid.in IS the case's para.in, byte for byte — only the "
      "name changed")
check(f"< {case_export.GETPGRID_INPUT}" in body,
      f"14. run_case.sh --regrid feeds getPGrid the exported name "
      f"({case_export.GETPGRID_INPUT}), not the one it had here")
check("getPGrid.in" in manifest and "para.in" in manifest,
      "14. the manifest records BOTH names, so the rename is auditable rather "
      "than a file that mysteriously vanished")

# ── 15. the allow-list also asks whether the RUN uses the file ────────────
# USER-REPORTED (2026-08-12): "I didn't configure IBM — why is there a phi.dat and
# a dll/ in the exported case?" Because prepare_case_dir reuses a case directory in
# place: an earlier immersed-solid run left work/phi.dat and dll/*.so behind, they
# pass the allow-list on NAME alone, and 730 KB of fossil was presented as "input".
# input.in decides: it declares immersed_solid and names every DLL it loads.
plain_case, plain_src, _ = build_case(os.path.join(tmp, "noibm"), dll_ref=False)
p15 = case_export.plan_export(plain_case, dll_src_dirs=(plain_src,))
unused = {rel: why for rel, _s, why in p15.skipped_unused}
check(not p15.has("work/phi.dat") and not p15.has("dll/user.so"),
      "15. a run whose input.in loads no DLL and declares no immersed solid "
      "carries neither the phi field nor the DLL")
check("work/phi.dat" in unused and "dll/user.so" in unused,
      f"15. ...and both are NAMED as skipped-with-a-reason, so the absence is a "
      f"line in the manifest rather than a silent difference ({sorted(unused)})")
check(all("earlier run" in w for w in unused.values()),
      f"15. ...the reason says what they actually are ({list(unused.values())})")
check(not p15.has("dll/user.cc"),
      "15. and the .cc is not fetched from dll_src for a .so that is not shipped")
check(p15.has("work/input.in") and p15.has("grid/mycase.grid"),
      "15. (control) the run's real inputs are unaffected")

p15_dest = os.path.join(tmp, "noibm_out")
case_export.export_case(plain_case, p15_dest, dll_src_dirs=(plain_src,))
man15 = open(os.path.join(p15_dest, "MANIFEST.txt"), encoding="utf-8").read()
check("not used by this run" in man15 and "phi.dat" in man15,
      "15. the manifest has its own section for them — the far machine can tell "
      "'left behind on purpose' from 'forgotten'")
check(not os.path.exists(os.path.join(p15_dest, "dll")),
      "15. dll/ is not even created when nothing in it belongs to the run")

# The immersed solid is declared in input.in, so an IBM run that loads no DLL of
# its own (a restart, say) still takes its phi field.
ibm_case, ibm_src, _ = build_case(os.path.join(tmp, "ibm"), dll_ref=False,
                                  immersed=True)
p_ibm = case_export.plan_export(ibm_case, dll_src_dirs=(ibm_src,))
check(p_ibm.has("work/phi.dat"),
      "15. an input.in declaring immersed_solid keeps phi.dat even with no DLL "
      "reference — the declaration is the authority, not a guess about IBM")

# A type-11 (user BC) DLL is named by the BC .def, never by input.in.
bc_case, bc_src, _ = build_case(os.path.join(tmp, "bcdll"), dll_ref=False)
with open(os.path.join(bc_case, "work", "mycase.bc.def"), "w") as f:
    f.write('3  11  "./user.so"\n')
p_bc = case_export.plan_export(bc_case, dll_src_dirs=(bc_src,))
check(p_bc.has("dll/user.so"),
      "15. a DLL named only by the type-11 BC .def row still ships — 'loaded' "
      "means loaded by the case, not mentioned in input.in")

# ── 13. every write is explicitly UTF-8 ───────────────────────────────────
# MANIFEST.txt embeds the case path verbatim and the UI ships a zh_TW translation, so a
# platform-default encoding fails on a non-ASCII path AFTER every file has been copied.
# Every module the service writes through: the selection (case_export) and the generated
# files (case_export_docs), which is where all four writes now live — manifest, run
# script, rewritten input.in, and the caller's extras (the .hws).
src_txt = "".join(
    open(os.path.join(_GUI, "app", "services", mod), encoding="utf-8").read()
    for mod in ("case_export.py", "case_export_docs.py", "case_export_usage.py"))
check('"w") as f:' not in src_txt and src_txt.count('"w", encoding="utf-8"') == 4,
      "13. all four writes (manifest, run script, rewritten input.in, extras) name "
      "UTF-8, like every read in the module already does")
uni_case, uni_src, _ = build_case(os.path.join(tmp, "案例"))
uni_dest = os.path.join(tmp, "匯出")
case_export.export_case(uni_case, uni_dest, dll_src_dirs=(uni_src,))
man = open(os.path.join(uni_dest, "MANIFEST.txt"), encoding="utf-8").read()
check("案例" in man,
      "13. ...and a case exported from a non-ASCII path really round-trips")

# --------------------------------------------------------------------------- #
# 16. A nested directory in the case is never INVISIBLE.
#
# A restart that continues in an existing case dir archives the previous run's
# outputs into work/prev_NNN/ (services/case_archive, #26). plan_export used to
# `continue` past anything that was not a file, so such a folder was neither
# shipped nor named as skipped — the same bug class as plan_export once walking
# only one level deep into grid/cad/. The archive's own behaviour is gated by
# test_restart_archive.py; what is pinned HERE is the exporter's side of it, in
# the exporter's own gate.
arch_case, arch_src, _ = build_case(os.path.join(tmp, "arch"), restart_ref=True)
prev = os.path.join(arch_case, "work", "prev_001")
os.makedirs(prev)
for name in ("binDumpZ.dat.gui", "unicones.enorm.gui", "xtecp_sol_allz.dat.gui"):
    with open(os.path.join(prev, name), "w") as f:
        f.write("archived " + name)
stray = os.path.join(arch_case, "grid", "notes_dir")
os.makedirs(stray)
with open(os.path.join(stray, "a.txt"), "w") as f:
    f.write("x")

plan = case_export.plan_export(arch_case, dll_src_dirs=(arch_src,))
shipped = {i.rel for i in plan.items}
named = ({r for r, _s in plan.skipped_output}
         | {r for r, _s in plan.skipped_other}
         | {r for r, _s, _w in plan.skipped_unused})
on_disk = {f"work/prev_001/{n}" for n in os.listdir(prev)}
check(on_disk <= (shipped | named),
      f"16. every file in work/prev_001/ is either shipped or NAMED as skipped "
      f"({sorted(on_disk - (shipped | named))})")
check("grid/notes_dir/" in {r for r, _s in plan.skipped_other},
      f"16. ...and an unrecognised subdirectory is named as a lump rather than "
      f"passed over in silence "
      f"({sorted(r for r, _s in plan.skipped_other)})")
check(all(sz > 0 for r, sz in plan.skipped_other if r.endswith("/")),
      "16. a directory skip line carries the tree's size, so 'not shipped' "
      "comes with the number that makes it a decision")
check("work/binDumpZ.dat.gui" in shipped
      and "work/prev_001/binDumpZ.dat.gui" not in shipped,
      f"16. only the dump input.in actually resolves to ships — a case with an "
      f"archive legitimately holds two files of that name, and matching a "
      f"reference by BASENAME shipped both, doubling the largest file in the "
      f"package ({sorted(r for r in shipped if 'binDump' in r)})")

shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
