#!/usr/bin/env python3
"""A DERIVED geometry through the whole headless chain, and into the case (#154).

#152 made an offset an ordinary geometry to every stage that handles one. This
gate is about the stage that does not handle a geometry at all — the one that
DESCRIBES the run. A pipeline script names a CAD input by its file path, and a
derived geometry has none, so a script saved from a workspace holding an offset
carried the record and no curve: the headless runner's ``cad_skip`` skipped that
entry and the GUI's script loader warned that a tab was missing. The mesh ran one
geometry short, and on a two-ring case the geometry it drops is the seam.

``app/services/derived_geoms.py`` closes it by PRODUCING the curve from the
record at the start of the run, through the same ``geometry_offset`` the CAD
stage calls. What is checked here is that the chain then behaves like any other,
measured by running it rather than by reading it:

  1. THE SHIPPED SCRIPT REALLY IS A DERIVED CASE. Read from disk, never composed,
     for the reason ``mb_shipped_config`` gives about the mesher's configs:
     ``config/pipeline/tworing_offset_demo.json`` is documentation a user runs.
  2. ONE OWNER, MEASURED. What the runner writes to disk is what
     ``geometry_offset.offset_points`` returns for the source's own points — to
     the last digit the file carries, so a second implementation could not pass.
  3. THE WHOLE CHAIN RUNS HEADLESS FROM THAT ONE SCRIPT: derive, resample three
     geometries, mesh. Exit 0, zero inverted cells, and the run NAMES the four
     seam edges following their own segment of the RESAMPLED offset — which is
     the claim that the seam is bound to the curve this run produced and not to
     the one checked in beside it.
  4. THE CASE SAYS WHAT IT WAS BUILT FROM. The derived curve is staged into
     ``grid/cad/`` alongside the CAD inputs, and ``SOURCES.txt`` gives it the
     record instead of a path under ``results/derived/`` — the distance and the
     source geometry by its own absolute path, so
     ``tools/scripts/case_sources_index.py`` still finds this case when asked
     what a change to that body makes stale.
  5. THE BINDINGS SURVIVE A RE-RESAMPLE OF THE SOURCE, PROVEN BY RUNNING IT. The
     same script at half the sampling: the geometries on disk really are a
     different size, the topology document is not touched, and the mesh still
     comes out at exit 0 with zero inverted cells — because a binding is a
     segment's STABLE ID and resampling does not move one.
  6. A BINDING BROKEN BY RE-SEGMENTING IS REPORTED BY THE PATH THAT ALREADY
     EXISTS, NAMING THE OFFSET GEOMETRY. Three segments where the topology
     declares four, and the mesher's own refusal names the geometry, the segment
     it cannot find and the ones it carries. No new vocabulary: this is the same
     sentence a hand-drawn geometry gets.
  7. EVERY REFUSAL OF THE DERIVATION ITSELF NAMES WHAT IS WRONG, and none of them
     is a skip: a record whose source the script does not carry, a source whose
     file is not on disk, and an offset that would fold.
  8. THE GUI PRODUCES THE SAME CURVE. The real ``AppController`` loads the same
     script and the derived tab's points equal the headless ones bit for bit —
     not because the two agree today, but because there is one function and both
     hosts call it.
  9. A WORKSPACE'S RECORD REACHES THE SCRIPT. ``from_workspace_dict`` carried
     seven of ``to_state_dict``'s keys and dropped the eighth, which is how a
     ``.hws`` holding an offset became a script that could not produce one.

NAMED BLIND SPOTS.

  * **Nothing here runs the solver.** Check 3 stops after the mesh; the dated
    solver run for this case is in
    ``tests/test_multiblock_tworing_offset_surface.py``'s docstring, in the
    convention this repo adopted after a change shipped broken behind green tests
    that never executed the solver.
  * **Check 8 does not run the GUI's own Run All.** 8b compares the curve bit for
    bit and 8d meshes the GUI's points through the same chain and compares the
    exported vertices, so what is left uncovered is the QThread SEQUENCING —
    whether the GUI's chain feeds the stages the same things in the same order.
    That is `tests/test_pipeline_stages.py`'s subject, not this gate's.
  * **The derivation is only ever exercised on a CLOSED outline.** The offset
    law's open-polyline end rule is ``test_geometry_offset.py``'s; nothing in the
    pipeline shape depends on it.
  * **Check 6's "existing broken-binding path" is the MESHER's refusal, and that
    is the only one a hand-written document has.** #138's ``BrokenBinding`` rows
    and the panel that repairs them are reported by a topology FAMILY, and this
    case declares its own document rather than generating one — #150 keeps the
    family out of the batch on purpose. So a user who re-segments the offset
    meets the refusal at run time and not in the panel, exactly as they would on
    any other hand-written document, which is what "no new vocabulary" means
    here.

Run:  python3 tools/PreProcessor/tests/test_pipeline_derived_geometry.py
Skips cleanly if ./build/HybMesh2D or ./build/surface_resampler is missing.
"""
import functools
import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)
sys.path.insert(0, _HERE)

import builtins                                                    # noqa: E402
print = functools.partial(builtins.print, flush=True)

SCRIPT = os.path.join(_REPO, "config", "pipeline", "tworing_offset_demo.json")
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_RESAMPLER = os.path.join(_REPO, "build", "surface_resampler")

_FAILS, _RUN = [], []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    _RUN.append(msg)
    if not cond:
        _FAILS.append(msg)


def finish():
    print("\n%d checks, %d failed" % (len(_RUN), len(_FAILS)))
    for f in _FAILS:
        print("  - " + f)
    return 1 if _FAILS else 0


if not (os.path.exists(_BIN) and os.path.exists(_RESAMPLER)):
    print("SKIP: build/HybMesh2D or build/surface_resampler not found "
          "(run ./build.sh first)")
    sys.exit(0)

import numpy as np                                                 # noqa: E402
from app.models.pipeline_config import PipelineConfig              # noqa: E402
from app.services import case_sources, derived_geoms               # noqa: E402
from app.services import pipeline_runner                           # noqa: E402
from app.services.derived_geoms import DerivedGeometryError        # noqa: E402
from app.services.geometry_offset import offset_points             # noqa: E402
from app.services.geometry_service import load_points_dat          # noqa: E402
from app.services.pipeline_case_sources import (                   # noqa: E402
    case_sources_for, derived_origins)
from mesher_bin import mesher_env                                  # noqa: E402

# ── the injection hook ────────────────────────────────────────────────────
# Each injection takes a checker away and this same file is re-run as a CHILD
# with it applied, so what is read is the harness's EXIT CODE and not only the
# count of its FAIL lines — a mutation that crashes the gate scores as silence
# otherwise. The negative control runs the child with no injection at all.
_INJECT = os.environ.get("HYBMESH_GATE_INJECT", "")
#: injection name -> (what it takes away, the checks that must go red).
INJECTIONS = {
    "no_derive": ("the run stops producing a derived geometry at all",
                  ("2a", "3a", "3d")),
    "blind_source": ("source_index falls back to a neighbour instead of "
                     "refusing", ("7a",)),
    "no_source_guard": ("the missing-source-file guard", ("7b",)),
    "drop_origins": ("stage_case_sources' origins argument", ("4c", "4d")),
    "origins_by_record": ("derived_origins' 'did this run write it?' test",
                          ("4e",)),
    "drop_ws_key": ("from_workspace_dict's carry of the record", ("9",)),
    "fmt12": ("the %.10f parity constant", ("8c",)),
}


def _inject(name):
    # "none" is the NEGATIVE CONTROL's name, and it has to be a name rather than
    # an empty string: the runner below is guarded on `not _INJECT`, so a child
    # launched with an empty value would run the injections itself, and the gate
    # would fork forever instead of failing.
    if name in ("", "none"):
        return
    if name == "no_derive":
        derived_geoms.materialise_all = lambda pcfg, repo, log=None: []
    elif name == "blind_source":
        derived_geoms.source_index = lambda pcfg, repo, i: next(
            j for j in pcfg.cad_indices() if j != i)
    elif name == "no_source_guard":
        _real = derived_geoms.source_points
        derived_geoms.source_points = lambda path, index, rec: (
            np.zeros((4, 2)) if not os.path.exists(path or "")
            else _real(path, index, rec))
    elif name == "drop_origins":
        _real_stage = case_sources.stage_case_sources
        case_sources.stage_case_sources = (
            lambda srcs, grid, log=None, generated=(), origins=None:
            _real_stage(srcs, grid, generated=generated))
    elif name == "origins_by_record":
        import app.services.pipeline_case_sources as _pcs
        _real_org = _pcs.derived_origins

        def _by_record(pcfg, repo):
            out = _real_org(pcfg, repo)
            for i in pcfg.cad_indices():
                rec = derived_geoms.record_for(pcfg.cad_at(i))
                if rec is not None:
                    out[derived_geoms.output_path(pcfg, repo, i)] = (
                        "(derived) %s" % rec.describe())
            return out
        _pcs.derived_origins = _by_record
        globals()["derived_origins"] = _by_record
    elif name == "drop_ws_key":
        _real_ws = PipelineConfig.from_workspace_dict.__func__

        def _drop(cls, data, name=""):
            pc = _real_ws(cls, data, name)
            for c in pc.cads:
                c.pop("derived_from", None)
            return pc
        PipelineConfig.from_workspace_dict = classmethod(_drop)
    elif name == "fmt12":
        derived_geoms._FMT = "%.12f"
    elif name:
        raise SystemExit("unknown injection %r" % name)


# The gmsh loader path the mesher needs, put where the runner's subprocesses
# will inherit it. `pipeline_runner` builds its own env from os.environ, so this
# is the one way in from a test process.
os.environ.update({k: v for k, v in mesher_env().items()
                   if k in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH")})


_inject(_INJECT)


def shipped(tmp, **mesh):
    """The shipped demo script, retargeted at ``tmp`` and stopped before the solver.

    Read from disk and never composed: the thing under test includes the script
    itself, and a gate that rebuilt an equivalent one would leave an edit to the
    shipped file invisible from here.
    """
    pc = PipelineConfig.load_from_file(SCRIPT)
    for i in pc.cad_indices():
        base = os.path.basename(pc.cad_at(i)["output_file"])
        pc.cads[i]["output_file"] = os.path.join(tmp, "resampled", base)
    pc.mesh["output_filename"] = os.path.join(tmp, "mesh.vtk")
    pc.mesh.update(mesh)
    pc.solver = {"skip": True}
    pc.results = {}
    # Under tmp as well, so a gate run leaves nothing in results/derived/.
    pc.name = os.path.join("gate", os.path.basename(tmp))
    return pc


def run(pc, log=None):
    lines = []

    def _log(s):
        lines.append(str(s))
        if log:
            print("    " + str(s))
    try:
        out = pipeline_runner.run_pipeline(pc, log=_log, run_solver=False,
                                           run_ib=False)
        return out, "\n".join(lines), None
    except Exception as e:                       # noqa: BLE001 - reported below
        return {}, "\n".join(lines), e


def quality(text):
    for ln in text.splitlines():
        if ln.startswith("HYBMESH_MB_QUALITY "):
            return dict((k, float(v)) for k, v in
                        (t.split("=") for t in ln.split()[1:]))
    return {}


def derived_index(pc):
    return next(i for i in pc.cad_indices()
                if derived_geoms.record_for(pc.cad_at(i)) is not None)


# ── 1. the shipped script really is a derived case ─────────────────────────
base = PipelineConfig.load_from_file(SCRIPT)
d_i = derived_index(base)
rec = derived_geoms.record_for(base.cad_at(d_i))
check(rec is not None and not base.cad_at(d_i).get("input_file"),
      "1a. the shipped demo script carries a CAD entry with an offset record "
      "and no source file — the shape that used to be skipped")
check(derived_geoms.needs_derivation(base.cad_at(d_i)),
      "1b. ...which is what `needs_derivation` answers about")
src_i = derived_geoms.source_index(base, _REPO, d_i)
check(src_i != d_i and os.path.basename(
          base.resolve_input_file(_REPO, src_i)) == "ellipse_body.dat",
      "1c. and its source resolves to another entry of the same script (%s)"
      % os.path.basename(base.resolve_input_file(_REPO, src_i)))
check(abs(rec.distance - 0.25) < 1e-12,
      "1d. at the distance the case is documented with (%g)" % rec.distance)

# UNDER THE REPO, not in the system temp dir. The mesher config writer emits a
# geometry path RELATIVE to the config it writes, and the mesher resolves it from
# its own working directory — which agree only while both are inside the repo.
# (On macOS the system temp dir is also reached through the /var -> /private/var
# symlink, so the relative path it produces climbs out of a tree it never
# entered.) A pre-existing property of the writer, worked around here rather than
# measured here; every shipped script's outputs are repo-relative.
_SCRATCH = os.path.join(_REPO, "results", "gate")
os.makedirs(_SCRATCH, exist_ok=True)
tmp = os.path.realpath(tempfile.mkdtemp(prefix="derived_pipe_", dir=_SCRATCH))

# ── 2. one owner, measured ─────────────────────────────────────────────────
pc = shipped(tmp)
made = derived_geoms.materialise_all(pc, _REPO)
check([i for i, _p in made] == [d_i],
      "2a. exactly the derived entry is produced (%r)" % ([i for i, _p in made],))
# Nothing below may assume the derivation happened: an injection that takes it
# away must leave the REST of the gate running, or the checks it should have
# turned red are never reached and the mutation scores as silence.
dest = made[0][1] if made else ""
got = (np.asarray(load_points_dat(dest), dtype=float)[:, :2]
       if dest and os.path.exists(dest) else np.zeros((0, 2)))
src_pts = np.asarray(load_points_dat(base.resolve_input_file(_REPO, src_i)),
                     dtype=float)[:, :2]
want = offset_points(src_pts, rec.distance, True)
check(got.shape == want.shape and np.array_equal(
          got, np.round(want, 10) + 0.0),
      "2b. what is written IS what geometry_offset returns for the source's own "
      "points, to every digit the file carries")
check(len(got) == len(src_pts),
      "2c. one point per source point, so the source's segment INDICES index it "
      "unchanged (%d)" % len(got))
check(pc.cad_at(d_i)["input_file"] == dest and not pc.cad_skip(d_i),
      "2d. and the entry now names a file, so nothing downstream sees a second "
      "kind of CAD entry")

# ── 3. the whole chain, headless, from that one script ─────────────────────
pc = shipped(tmp)
out, text, err = run(pc)
check(err is None, "3a. the shipped script runs headless end to end (%s)"
      % (err or "ok"))
check(bool(out.get("vtk")) and os.path.exists(out.get("vtk", "")),
      "3b. and writes its mesh")
q = quality(text)
check(q.get("inverted") == 0 and q.get("cells") == 9216,
      "3c. zero inverted cells, at the case's own budget (%r)"
      % ({k: q.get(k) for k in ("cells", "inverted")},))
follows = [ln for ln in text.splitlines() if "following segment" in ln]
resampled_off = os.path.basename(pc.cad_at(d_i)["output_file"])
check(len(follows) == 4 and all(resampled_off in ln for ln in follows),
      "3d. all four seam edges follow a segment of the RESAMPLED offset — the "
      "curve this run produced, not the one checked in (%d/4)" % len(follows))
check(len(out.get("cad_outs") or []) == 3,
      "3e. three geometries reached the mesher, the derived one among them")

# ── 4. the case says what it was built from ────────────────────────────────
srcs, generated = case_sources_for(pc, _REPO, out.get("cad_outs"), out.get("vtk"))
origins = derived_origins(pc, _REPO)
check(bool(dest) and dest in [os.path.abspath(s) for s in srcs],
      "4a. the derived curve is staged alongside the CAD inputs")
check(bool(dest) and dest in origins and "offset +0.25" in origins[dest],
      "4b. and SOURCES.txt is given the RECORD rather than its results/derived "
      "path (%r)" % (origins.get(dest, "")[:40],))
grid = os.path.join(tmp, "grid")
os.makedirs(grid, exist_ok=True)
case_sources.stage_case_sources(srcs, grid, generated=generated, origins=origins)
index = open(os.path.join(grid, "cad", case_sources.SOURCES_INDEX),
             encoding="utf-8").read()
body_abs = base.resolve_input_file(_REPO, src_i)
check("(derived) offset +0.25 from 'ellipse_body.dat'" in index,
      "4c. ...and the index really carries it")
check(any(body_abs in ln and "(derived)" in ln for ln in index.splitlines()),
      "4d. naming the source body by its own absolute path, so the case index "
      "still answers 'what goes stale if I change this body?'")
# An offset the user EXPORTED and then listed by path carries a record and was
# derived by nobody, so `output_path` would name a file the case does not hold.
# Without this the index would say "(derived)" for one such entry and not
# another, keyed on nothing a reader could see.
listed = shipped(os.path.join(tmp, "listed"))
listed.cads[d_i]["input_file"] = base.resolve_input_file(_REPO, src_i)
check(derived_geoms.record_for(listed.cad_at(d_i)) is not None
      and not derived_origins(listed, _REPO),
      "4e. an entry that carries a record AND names a file of its own gets NO "
      "note — nothing derived it, so the column keeps the path it really has")

# ── 5. the bindings survive a RE-RESAMPLE of the source ────────────────────
coarse = shipped(os.path.join(tmp, "coarse"))
os.makedirs(os.path.join(tmp, "coarse"), exist_ok=True)
for i in coarse.cad_indices():
    for seg in coarse.cads[i]["segments"]:
        seg["parameters"]["n_points"] = (seg["parameters"]["n_points"] + 1) // 2
before = {os.path.basename(p): sum(1 for _ in open(p, encoding="utf-8"))
          for p in (out.get("cad_outs") or [])}
topo_before = open(os.path.join(_REPO, "examples", "topology",
                                "tworing_offset.json"), encoding="utf-8").read()
out2, text2, err2 = run(coarse)
after = {os.path.basename(p): sum(1 for _ in open(p, encoding="utf-8"))
         for p in (out2.get("cad_outs") or [])}
check(err2 is None, "5a. the same script at half the sampling still runs (%s)"
      % (err2 or "ok"))
check(before and after and all(after[k] < before[k] for k in before),
      "5b. the geometries on disk really are a different size — the resample is "
      "not a no-op (%r -> %r)" % (sorted(before.values()), sorted(after.values())))
q2 = quality(text2)
check(q2.get("inverted") == 0 and q2.get("cells") == 9216,
      "5c. and the mesh is still exit 0 with zero inverted cells, because a "
      "binding is a segment's STABLE ID (%r)"
      % ({k: q2.get(k) for k in ("cells", "inverted")},))
check(topo_before == open(os.path.join(_REPO, "examples", "topology",
                                       "tworing_offset.json"),
                          encoding="utf-8").read(),
      "5d. ...with not one character of the topology document changed")

# ── 6. a binding broken by RE-SEGMENTING, on the existing path ─────────────
broken = shipped(os.path.join(tmp, "broken"))
os.makedirs(os.path.join(tmp, "broken"), exist_ok=True)
segs = broken.cads[d_i]["segments"]
segs[2]["end_index"] = segs[3]["end_index"]
del segs[3]
_o3, text3, err3 = run(broken)
msg = (str(err3) + "\n" + text3)
check(err3 is not None, "6a. re-segmenting the offset to three edges fails the "
      "run rather than meshing something else")
check("ellipse_offset.dat" in msg,
      "6b. and the refusal names the OFFSET GEOMETRY, not something the user has "
      "never heard of")
check("segment 4" in msg and "1 2 3" in msg,
      "6c. ...the segment it cannot find and the ones that geometry now carries")
check("has no segment" in msg,
      "6d. in the sentence a hand-drawn geometry already gets — no new "
      "vocabulary was invented for a derived one")

# ── 7. every refusal of the derivation names what is wrong ─────────────────
orphan = shipped(os.path.join(tmp, "orphan"))
del orphan.cads[src_i]
try:
    derived_geoms.materialise_all(orphan, _REPO)
    e7a = None
except DerivedGeometryError as e:
    e7a = e
check(e7a is not None and "ellipse_body.dat" in str(e7a),
      "7a. a record whose source the script does not carry is refused BY NAME "
      "(%r)" % (str(e7a)[:60],))

gone = shipped(os.path.join(tmp, "gone"))
# The SAME basename, so the source is still found and the refusal is about the
# file rather than about the record — the two are different failures and each
# has its own sentence.
gone.cads[src_i]["input_file"] = os.path.join(tmp, "ellipse_body.dat")
try:
    derived_geoms.materialise_all(gone, _REPO)
    e7b = None
except DerivedGeometryError as e:
    e7b = e
check(e7b is not None and "not on disk" in str(e7b),
      "7b. a source whose file is gone is refused by name, never filled in from "
      "whatever is nearest (%r)" % (str(e7b)[:60],))

fold = shipped(os.path.join(tmp, "fold"))
fold.cads[d_i]["derived_from"] = dict(fold.cads[d_i]["derived_from"])
fold.cads[d_i]["derived_from"]["distance"] = -5.0
try:
    derived_geoms.materialise_all(fold, _REPO)
    e7c = None
except DerivedGeometryError as e:
    e7c = e
check(e7c is not None and "largest that works" in str(e7c),
      "7c. an offset that would fold carries the law's own refusal through, "
      "number and all (%r)" % (str(e7c)[-60:],))
_, text7, err7 = run(fold)
check(err7 is not None and "fold" in (str(err7) + text7),
      "7d. and the RUN stops on it rather than meshing one geometry short")

# ── 8. the GUI produces the same curve ─────────────────────────────────────
from PyQt6.QtWidgets import QApplication                           # noqa: E402
_app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController                           # noqa: E402

gui_script = os.path.join(tmp, "gui_case.json")
gui_pc = shipped(os.path.join(tmp, "gui"))
os.makedirs(os.path.join(tmp, "gui"), exist_ok=True)
gui_pc.save_to_file(gui_script)
c = AppController()
c.open_pipeline_path(gui_script)
names = [s.display_name.lstrip("*") for s in c.sessions]
check(len(c.sessions) == 3,
      "8a. the GUI opens a tab for EVERY entry of the script, the derived one "
      "included (%d: %r)" % (len(c.sessions), names))
gui_pts = None
for s in c.sessions:
    if s.project_model.derived_from is not None:
        gui_pts = np.asarray(s.original_points, dtype=float)[:, :2]
check(gui_pts is not None and len(got) and np.array_equal(gui_pts, got),
      "8b. and the derived tab's points are the headless run's, bit for bit — "
      "one function, two hosts")

# The precision the derived file is written at is the one the GUI writes when it
# hands a session's points BACK to the resampler (`backend_ctrl._write_temp_config`,
# np.savetxt fmt="%.10f"). Finer here and the GUI's temp copy would be a rounding
# of the file the headless run resamples, so the two hosts' meshes would differ
# in the eleventh digit for no reason a reader could find.
_buf = os.path.join(tmp, "gui_roundtrip.dat")
np.savetxt(_buf, gui_pts if gui_pts is not None else np.zeros((1, 2)),
           fmt="%.10f")
_A = open(_buf, encoding="utf-8").read() if os.path.exists(_buf) else "?"
_B = open(dest, encoding="utf-8").read() if dest and os.path.exists(dest) else "!"
if _A != _B:
    _la, _lb = _A.splitlines(), _B.splitlines()
    print("   DEBUG lines %d/%d" % (len(_la), len(_lb)))
    for _i, (_x, _y) in enumerate(zip(_la, _lb)):
        if _x != _y:
            print("   DEBUG first diff %d %r %r" % (_i, _x, _y))
            break
check(bool(dest) and os.path.exists(dest) and _A == _B,
      "8c. and the GUI writing those points back for the resampler reproduces "
      "the derived file byte for byte — which is what the %.10f in "
      "derived_geoms is for")

# AND THE MESH, not only the curve. Driving the GUI's own Run All needs its
# QThread chain and three subprocesses, which this gate does not build; what it
# can do is take the points the GUI is holding, hand them to the same chain as an
# ordinary geometry, and require the mesh to be the one the headless run wrote.
# That closes the step between "the two hosts agree about the curve" and "the two
# hosts produce the same mesh" — the criterion's own noun — while leaving the
# QThread sequencing itself uncovered, which the blind-spot list says.
gui_dat = os.path.join(tmp, "gui_points.dat")
np.savetxt(gui_dat, gui_pts if gui_pts is not None else np.zeros((1, 2)),
           fmt="%.10f")
same = shipped(os.path.join(tmp, "guimesh"))
same.cads[d_i] = dict(same.cads[d_i])
same.cads[d_i].pop("derived_from", None)
same.cads[d_i]["input_file"] = gui_dat
same.mesh["output_filename"] = os.path.join(tmp, "gui_mesh.vtk")
out8, _t8, err8 = run(same)
first_vrt = os.path.join(tmp, "mesh.vrt")
gui_vrt = os.path.join(tmp, "gui_mesh.vrt")
check(err8 is None and os.path.exists(gui_vrt) and os.path.exists(first_vrt),
      "8d. the points the GUI holds mesh through the same chain (%s)"
      % (err8 or "ok"))
check(os.path.exists(gui_vrt) and os.path.exists(first_vrt)
      and open(gui_vrt, encoding="utf-8").read()
      == open(first_vrt, encoding="utf-8").read(),
      "8d. ...and the mesh is the headless run's, vertex for vertex")

# ── 9. a workspace's record reaches the script ─────────────────────────────
ws = {"format_version": 2, "sessions": [
    {"file_path": "", "display_name": "body_offset+0p25",
     "project_config": {"input_file": "", "segments": [],
                        "derived_from": {"kind": "offset",
                                         "source_name": "body.dat",
                                         "distance": 0.25}}}],
    "project": {}}
w = PipelineConfig.from_workspace_dict(ws)
check(derived_geoms.record_for(w.cad_at(0)) is not None,
      "9. a .hws holding an offset becomes a script that still carries the "
      "record — the eighth key from_workspace_dict used to drop")

shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(os.path.join(_REPO, "results", "derived", "gate"),
              ignore_errors=True)


# ── injections ─────────────────────────────────────────────────────────────
def _child(inject):
    import subprocess
    env = dict(os.environ)
    env["HYBMESH_GATE_INJECT"] = inject
    p = subprocess.run([sys.executable, os.path.abspath(__file__)], env=env,
                       cwd=_REPO, capture_output=True, text=True, timeout=900)
    red = set()
    for ln in p.stdout.splitlines():
        if ln.startswith("FAIL "):
            red.add(ln[5:].split(".")[0])
    return p.returncode, red, p.stdout


if not _INJECT:
    for name, (what, want) in INJECTIONS.items():
        rc, red, _o = _child(name)
        check(rc != 0,
              "injection %s: with %s removed the gate EXITS NON-ZERO (rc=%d) — "
              "the exit code, not the FAIL count, because a mutation that "
              "crashes scores as silence otherwise" % (name, what, rc))
        check(red >= set(want),
              "injection %s: and the checks that go red are the ones that "
              "measure it (wanted %r, got %r)" % (name, sorted(want), sorted(red)))
    rc0, red0, _o0 = _child("none")
    check(rc0 == 0 and not red0,
          "injection control: the unmutated gate run as the same child exits 0 "
          "(rc=%d, red=%r) — so every red above is the mutation and not the "
          "harness" % (rc0, sorted(red0)))

try:
    os.rmdir(_SCRATCH)
except OSError:
    pass
# os._exit, not sys.exit: this process built a real QApplication for check 8, and
# Qt's offscreen teardown is where this repo has already had a gate print "all
# checks passed" and then exit 139. The injection runner above reads the child's
# EXIT CODE, so a teardown crash would be read as the mutation working.
os._exit(finish())
