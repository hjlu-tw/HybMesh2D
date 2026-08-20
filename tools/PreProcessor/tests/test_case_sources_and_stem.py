#!/usr/bin/env python3
"""A solver case carries the geometry it was cut from, and is named once.

Two USER-REPORTED items (2026-08-13), both about a case directory that does not
describe itself:

 A. **The case held only the mesh.** ``grid/`` had the STAR-CD triplet, the
    binary grid and ``input.in`` — enough to rerun, nothing to say WHICH body it
    is. The CAD lived in ``examples/geometries/`` or on a Desktop, free to be
    edited or deleted while the case sat there looking complete. Sources are now
    copied into ``grid/cad/`` (``services/case_sources``): copy never move,
    sidecars follow their file, collisions renamed not overwritten, and
    ``SOURCES.txt`` records where each came from.

 B. **Auto-versioning renamed the directory but not the grid.**
    ``prepare_case_dir`` took the stem from the pre-version case name, so
    choosing "New Versioned Dir" wrote ``case.grid`` into ``case_002/``. It runs
    — ``input.in`` names the file it just wrote — so nothing complains until the
    user later types ``case_002`` by hand and the SAME directory ends up holding
    ``case.grid`` and ``case_002.grid``: two 1.3 MB grids, and only ``input.in``
    says which one the solver reads. Reported as "why are there two STAR-CD file
    sets in case_002/grid?"

Also pinned: the portable export descends into ``grid/cad/`` — a folder it
cannot see is neither shipped nor named as skipped, which is the one outcome
this export's allow-list exists to make impossible.

Run:  python3 tools/PreProcessor/tests/test_case_sources_and_stem.py
"""
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

from app.services import case_export, case_sources, solver_case  # noqa: E402
from app.models.solver_config import SolverConfig  # noqa: E402

tmp = tempfile.mkdtemp(prefix="hybmesh_src_")


def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return path


# ── A. staging the sources ────────────────────────────────────────────────
geom = os.path.join(tmp, "geom")
cad_stl = w(os.path.join(geom, "body.stl"), "solid\nendsolid\n")
resampled = w(os.path.join(geom, "body_resampled.dat"), "0 0\n1 0\n")
w(resampled + ".meta", "NSEGMENTS 1\ninlet\n")
ib_stl = w(os.path.join(tmp, "ib", "solid.stl"), "solid ib\nendsolid\n")
# A second body whose file has the SAME basename from a different directory.
other = w(os.path.join(tmp, "other", "body.stl"), "solid other\nendsolid\n")

grid_dir = os.path.join(tmp, "case", "grid")
os.makedirs(grid_dir, exist_ok=True)
logged = []
staged = case_sources.stage_case_sources(
    [cad_stl, resampled, "", os.path.join(tmp, "missing.dat"), cad_stl,
     other, ib_stl],
    grid_dir, log=logged.append)
cad_dir = os.path.join(grid_dir, "cad")
names = sorted(os.listdir(cad_dir))

check(set(names) >= {"body.stl", "body_resampled.dat",
                     "body_resampled.dat.meta", "solid.stl"},
      f"1. the CAD, the resampled .dat and the immersed STL are all in "
      f"grid/cad/ ({names})")
check("body_resampled.dat.meta" in names,
      "1. the .meta sidecar comes along without being asked for — it is where "
      "the per-segment BC labels live, so the .dat without it is a different "
      "geometry")
check(os.path.isfile(cad_stl) and os.path.isfile(resampled),
      "1. the originals are still where they were — this is a COPY; the mesher, "
      "the GUI session and every other case still point at them")
check("body_2.stl" in names,
      f"1. two different bodies both called body.stl do not overwrite each "
      f"other; the second is renamed ({names})")
check(open(os.path.join(cad_dir, "body.stl")).read() != open(
      os.path.join(cad_dir, "body_2.stl")).read(),
      "1. ...and they really are the two different files, not one copied twice")
check(len([1 for s, _d in staged if s == cad_stl]) == 1,
      "1. the same path listed twice is staged once")
check(not any("missing.dat" in d for _s, d in staged),
      "1. a path that does not exist is dropped, not staged as an empty file — "
      "callers assemble this list from whatever the case happens to have")

idx = open(os.path.join(cad_dir, case_sources.SOURCES_INDEX)).read()
check(cad_stl in idx and other in idx and ib_stl in idx,
      "2. SOURCES.txt records the absolute path every staged file came from — "
      "copying discards it, and a renamed collision discards the name too")
check("body_2.stl" in idx,
      "2. ...under the name it was actually staged as, so a renamed file can "
      "still be traced back")
check(any("body_2.stl" in m and "renamed" in m for m in logged),
      "2. the rename is named in the log as it happens, not only in the index")

# A re-run with a different body must not leave the old one described.
grid2 = os.path.join(tmp, "case2", "grid")
os.makedirs(grid2, exist_ok=True)
case_sources.stage_case_sources([cad_stl], grid2)
case_sources.stage_case_sources([ib_stl], grid2)
idx2 = open(os.path.join(grid2, "cad", case_sources.SOURCES_INDEX)).read()
check(ib_stl in idx2 and cad_stl not in idx2,
      "2. SOURCES.txt is rewritten, not appended to — it describes the case as "
      "it stands, so a body that is no longer part of it leaves no line behind")

empty_grid = os.path.join(tmp, "empty", "grid")
os.makedirs(empty_grid, exist_ok=True)
check(case_sources.stage_case_sources([], empty_grid) == []
      and not os.path.exists(os.path.join(empty_grid, "cad")),
      "3. a case with no known sources gets no empty cad/ folder implying its "
      "geometry went missing")

# ── B. the stem follows the auto-versioned directory ──────────────────────
repo = os.path.join(tmp, "repo")
os.makedirs(os.path.join(repo, "results", "solver"), exist_ok=True)
mesh = os.path.join(repo, "m")
for ext in (".vrt", ".cel", ".bnd"):
    w(mesh + ext, "mesh")

_real_repo_root = solver_case.repo_root
solver_case.repo_root = lambda: repo


def prep(case_name, sources=(), generated=()):
    cfg = SolverConfig()
    cfg.case_name = case_name
    cfg.input_vrt_file = mesh + ".vrt"
    cfg.input_cel_file = mesh + ".cel"
    cfg.input_bnd_file = mesh + ".bnd"
    return cfg, solver_case.prepare_case_dir(
        cfg, sources=sources, generated_sources=generated)


cfg1, (_w1, g1, _in1) = prep("case")
check(cfg1.output_grid_file == "case.grid"
      and os.path.basename(os.path.dirname(g1)) == "case",
      "4. (precondition) an unversioned case names its grid after itself")

# Make it non-empty so the next run auto-versions.
w(os.path.join(repo, "results", "solver", "case", "grid", "case.grid"), "G")
cfg2, (_w2, g2, in2) = prep("case")
check(os.path.basename(os.path.dirname(g2)) == "case_002",
      "4. (precondition) the second run auto-versions the directory")
check(cfg2.output_grid_file == "case_002.grid"
      and cfg2.output_bc_file == "case_002.bc",
      f"4. the GRID follows the versioned directory — a case_002/ holding "
      f"case.grid is what put two STAR-CD sets in one folder "
      f"({cfg2.output_grid_file})")
check('"../grid/case_002.grid"' in open(in2).read(),
      "4. ...and input.in references that same name, so the run stays "
      "self-consistent")
check(cfg2.case_name == "case_002",
      "4. cfg.case_name is the versioned name too — it is the solver's -t tag "
      "and the result path, which must agree with the grid")

# ── C. the sources reach the case, and then the portable package ──────────
cfg3, (w3, g3, _i3) = prep("withcad", sources=[cad_stl, resampled])
check(os.path.isfile(os.path.join(g3, "cad", "body.stl")),
      "5. prepare_case_dir stages the sources, so every GUI and scripted run "
      "lands them in the same place")

# Make it a plausible case for the exporter.
w(os.path.join(w3, "input.in"), '  grid_fname "../grid/withcad.grid"\n')
w(os.path.join(g3, "withcad.grid"), "G")
w(os.path.join(g3, "withcad.bc"), "B")
plan = case_export.plan_export(os.path.dirname(g3))
rels = {i.rel for i in plan.items}
check("grid/cad/body.stl" in rels and "grid/cad/body_resampled.dat" in rels,
      f"6. the portable export descends into grid/cad/ and ships the geometry "
      f"— the package now answers 'which body?' on the far machine "
      f"({sorted(r for r in rels if r.startswith('grid/cad'))})")
check("grid/cad/body_resampled.dat.meta" in rels,
      "6. including the .meta, without which the exported geometry has lost its "
      "per-segment BCs")
check(f"grid/cad/{case_sources.SOURCES_INDEX}" in rels,
      "6. and SOURCES.txt, or the far machine gets files with no provenance")
check("grid/cad" not in rels,
      "6. the cad/ directory itself is not listed as a file")

dest = os.path.join(tmp, "portable")
case_export.export_case(os.path.dirname(g3), dest)
check(os.path.isfile(os.path.join(dest, "grid", "cad", "body.stl")),
      "6. ...and it is really written into the package, nested folder and all")
man = open(os.path.join(dest, "MANIFEST.txt"), encoding="utf-8").read()
check("grid/cad/body.stl" in man,
      "6. the manifest names it, like every other file that travels")

# A file in cad/ that is not a geometry is skipped AND named, not shipped blind.
w(os.path.join(g3, "cad", "leftover.bin"), "junk")
plan2 = case_export.plan_export(os.path.dirname(g3))
check(not plan2.has("grid/cad/leftover.bin")
      and any(r == "grid/cad/leftover.bin" for r, _s in plan2.skipped_other),
      "6. grid/cad/ is still an ALLOW-list — an unrecognised file there is "
      "skipped and NAMED, never shipped because we happened to own the folder")

# ── D. the settings that cut the grid, not only the body ──────────────────
from app.models.mesh_config import MeshConfig  # noqa: E402
from app.models.mesh_config_io import config_to_text  # noqa: E402

mcfg = MeshConfig()
mcfg.bl_layers = 7
mcfg.bl_initial_thickness = 1.5e-6
text = config_to_text(mcfg)
check("BL_LAYERS 7" in text and "1.5e-06" in text.replace("1.5E-06", "1.5e-06"),
      "7. config_to_text renders the live mesh config as Background_para.dat "
      "text without going through a file")

tmpcfg = os.path.join(tmp, "roundtrip", "Background_para.dat")
os.makedirs(os.path.dirname(tmpcfg), exist_ok=True)
mcfg.save_to_file(tmpcfg)
check(open(tmpcfg).read() == config_to_text(mcfg, tmpcfg),
      "7. ...and Save Mesh Config writes exactly that, so the config staged into "
      "a case is byte-identical to the one the user can save by hand")

cfg4, (_w4, g4, _i4) = prep(
    "withcfg", sources=[resampled],
    generated=[("Background_para_withcfg.dat", config_to_text(mcfg))])
staged_cfg = os.path.join(g4, "cad", "Background_para_withcfg.dat")
check(os.path.isfile(staged_cfg) and "BL_LAYERS 7" in open(staged_cfg).read(),
      "8. the mesh parameter file is staged into grid/cad/ — the GUI only ever "
      "writes it to a temp path it deletes on exit, so a case would otherwise "
      "record every input except the one that shaped its grid")
idx4 = open(os.path.join(g4, "cad", case_sources.SOURCES_INDEX)).read()
check(f"Background_para_withcfg.dat  <-  {case_sources.GENERATED}" in idx4,
      "8. SOURCES.txt marks it as GENERATED, not as a file copied from "
      "somewhere — a reconstruction must not read as evidence")

prov = os.path.join(tmp, "meshout")
w(os.path.join(prov, "mesh_x.provenance.json"), '{"tool":"HybMesh2D"}')
cands = case_sources.mesh_provenance_paths(os.path.join(prov, "mesh_x.vtk"))
check(os.path.join(prov, "mesh_x.provenance.json") in cands,
      "9. the mesh provenance sidecar is found from the mesh output path — it "
      "carries the git sha, the gmsh version and the config as text, which is "
      "the difference between 'which body?' and 'which run?'")

# The GUI reads it off the config, and the field is output_filenameNOT
# output_file: a getattr on the wrong name returns "" and stages nothing, and a
# missing provenance file is a legal outcome, so the mistake is invisible.
import ast  # noqa: E402
_ctrl_src = open(os.path.join(_GUI, "app", "controllers", "solver_ctrl.py"),
                 encoding="utf-8").read()
_fields = {f.target.id for f in ast.walk(ast.parse(open(
    os.path.join(_GUI, "app", "models", "mesh_config.py"),
    encoding="utf-8").read()))
    if isinstance(f, ast.AnnAssign) and isinstance(f.target, ast.Name)}
_asked = {n.args[1].value for n in ast.walk(ast.parse(_ctrl_src))
          if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "getattr"
          and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant)
          and isinstance(n.args[1].value, str)
          and "mesh_config" in ast.dump(n.args[0])}
check(_asked and _asked <= _fields,
      f"9. every mesh-config field solver_ctrl reads by name really exists on "
      f"MeshConfig ({sorted(_asked)})")

# ── E. the reverse index: who used this geometry? ──────────────────────────
sys.path.insert(0, os.path.join(_HERE, "..", "..", "scripts"))
import case_sources_index as csi  # noqa: E402

solver_root = os.path.join(repo, "results", "solver")
found = {n for n, _d, _e in csi.scan(solver_root)}
check({"withcad", "withcfg"} <= found,
      f"10. the index script finds every case that recorded its sources "
      f"({sorted(found)})")

rc = csi.main(["--root", solver_root, resampled])
check(rc == 0,
      "10. querying by the geometry's own path reports the cases built from it "
      "— the arrow only points one way in the case dir, so this is the only "
      "way to ask 'if I change this CAD, what goes stale?'")
check(csi.main(["--root", solver_root, "body_resampled"]) == 0,
      "10. ...and a partial name works too, which is what lets you ask about a "
      "geometry that has since been renamed or deleted")
check(csi.main(["--root", solver_root, "no_such_body"]) == 1,
      "10. a query that matches nothing exits non-zero, so this is usable from "
      "a check script")
check(not csi.matches("Background_para_withcfg.dat", csi.GENERATED),
      "10. a generated file is never reported as a source someone can change")

solver_case.repo_root = _real_repo_root
shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED")
    for m in _FAILS:
        print("  - " + m)
    sys.exit(1)
print("\nRESULT: ALL PASS")
