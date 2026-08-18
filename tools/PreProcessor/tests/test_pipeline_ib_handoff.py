#!/usr/bin/env python3
"""The immersed-solid stage's phi field must reach the solve — in BOTH hosts.

**The bug this locks out.** STL3d writes a *Tecplot* phi field; the solver's
initial-condition DLL reads a *headerless* ``phi.dat`` with the STL3d grid spec
baked into the DLL source. Producing a phi field is therefore not the same as
wiring one up, and nothing carried it across:

* ``pipeline_runner.run_pipeline`` collected the stage's output into
  ``out["phi"]`` and passed it nowhere. ``_run_solver`` built its SolverConfig
  from the script alone, so a script that declared ``immersed_solid`` without
  naming a phi file solved against whatever ``work/phi.dat`` the reused case
  directory still held — the PREVIOUS geometry's solid, converging to a
  believable answer for the wrong shape (the failure ``solver_case.
  report_stale_ibm_artifacts`` warns about, from the other end).
* the GUI's Run All had no IB stage at all, so it did the same.
* the conversion + wiring existed only inside ``stl3d_ctrl.send_stl3d_to_solver``
  — a Qt controller method no headless runner can call.

So the fix is one shared, Qt-free hand-off (``services/ib_handoff``) that both
hosts call, and the checks below are about the two failure modes that would
bring the bug back: the hand-off drifting from the file format, and a host
growing its own private copy again.

Checks:
 1. The header count is not guessed twice: ``PHI_HEADER_LINES`` equals the
    ``skiprows=`` the field's own reader uses.
 2. The headerless phi.dat is byte-identical to the Tecplot tail, and the
    solver config points at it.
 3. The init DLL is generated with THIS field's grid spec baked in.
 4. The hand-off does not declare ``immersed_solid``: a stage may not overrule
    a script (or a panel) that says the solve has no immersed solid.
 5. The headless auto-link keeps explicitly-scripted IB inputs (the rule
    ``_run_solver`` already applies to .vrt/.cel/.bnd) and takes over the phi
    field and its DLL TOGETHER or not at all — they are one fact, since the DLL
    is baked for the grid of the field it reads.
 6. A phi file with no data rows is REFUSED, not written out as an empty field.
 7. The headless chain is connected end to end (by AST, not by grep):
    run_pipeline -> out["phi"] -> _run_solver -> link_phi_to_solver.
 8. GUI Run All really runs the stage, in the headless runner's ORDER (IB
    before mesh), skips out loud with no STL, hands off on success, and aborts
    without meshing on failure.
 9. Neither host has a second private copy of the conversion.
10. The stage downstream can consume what the hand-off produced: the generated
    DLL really COMPILES (a compile failure degrades silently to "no init DLL")
    and phi.dat lands in the work dir headerless.
11. A shipped example script carries both sections, so the schema converter is
    covered too — and a relative `stl_path` resolves like a relative CAD input.

Run:  python3 tools/PreProcessor/tests/test_pipeline_ib_handoff.py
"""
import ast
import os
import re
import sys
import tempfile
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []
_CLEANUP = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >60s (headless hang?)", flush=True)
    os._exit(99)


_wd = threading.Timer(60, _watchdog)
_wd.daemon = True
_wd.start()

from app.models.solver_config import SolverConfig            # noqa: E402
from app.models.stl3d_config import Stl3dConfig              # noqa: E402
from app.services import ib_handoff                          # noqa: E402

_APP = os.path.join(_GUI, "app")


def read(*parts):
    with open(os.path.join(_APP, *parts)) as f:
        return f.read()


# A 4-row Tecplot phi field, written the way STL3d writes one.
_HEADER = ['title = "phi"\n', 'variables = "x" "y" "z" "phi"\n',
           'zone t = "phi", i = 4\n']
_ROWS = ["0.0 0.0 0.0 0\n", "0.5 0.0 0.0 1\n",
         "0.5 0.5 0.0 1\n", "1.0 1.0 0.0 0\n"]


def write_phi_tec(path, rows=_ROWS):
    with open(path, "w") as f:
        f.writelines(_HEADER + list(rows))
    return path


# --------------------------------------------------------------------------- #
print("\n--- 1-6. the shared hand-off ---", flush=True)
# --------------------------------------------------------------------------- #
skip = re.findall(r"skiprows\s*=\s*(\d+)", read("models", "stl3d_config.py"))
check(skip and all(int(s) == ib_handoff.PHI_HEADER_LINES for s in skip),
      f"1. PHI_HEADER_LINES ({ib_handoff.PHI_HEADER_LINES}) matches every "
      f"skiprows= the reader uses ({skip})")

_tmp = tempfile.mkdtemp(prefix="ib_handoff_")
phi_tec = write_phi_tec(os.path.join(_tmp, "ibtest_phi_tec.dat"))
cfg = Stl3dConfig(stl_path=os.path.join(_tmp, "body.stl"), case_name="ibtest",
                  xmin=-1.5, xmax=2.5, ymin=-1.0, ymax=1.0, nx=17, ny=9, nz=2)
sc = SolverConfig()
sc.immersed_solid = False
lines = []
out = ib_handoff.link_phi_to_solver(sc, phi_tec, cfg, _tmp, log=lines.append)
_CLEANUP.append(out["init_dll"])

check(os.path.exists(sc.ibm_phi_file) and sc.ibm_phi_file == out["phi_dat"],
      f"2. solver config points at the phi.dat that was written "
      f"({os.path.basename(sc.ibm_phi_file)})")
with open(sc.ibm_phi_file) as f:
    got = f.readlines()
check(got == _ROWS,
      f"2. phi.dat is the Tecplot tail with no header ({len(got)} rows, "
      f"{out['rows']} reported)")

dll_src = open(out["init_dll"]).read() if os.path.exists(out["init_dll"]) else ""
check(sc.init_cond_dll == out["init_dll"] and dll_src,
      "3. init DLL source written and referenced by the solver config")
check("17" in dll_src and "-1.5" in dll_src,
      "3. ...with THIS field's grid spec baked in (nx=17, xmin=-1.5)")

check(not sc.immersed_solid,
      "4. the hand-off does NOT declare the immersed solid: whether the solve "
      "has one is the caller's to say, and a script's `immersed_solid: false` "
      "has exactly as much standing as its motion preset")
check(any("solver reads phi from" in ln and "4 cells" in ln for ln in lines),
      "4. the file the solve reads is named in the log with ITS OWN cell count")

# 5. The headless auto-link rule: explicit wins, and the phi field and the DLL
# move TOGETHER — the DLL is baked for this stage's grid, so it can only read
# this stage's field. Pairing one caller's half with one of ours would hand the
# solve a field read on the wrong grid: a wrong answer, not an error.
sc2 = SolverConfig()
sc2.ibm_phi_file = "/scripted/by/hand/phi.dat"
lines2 = []
out2 = ib_handoff.link_phi_to_solver(sc2, phi_tec, cfg, _tmp,
                                     log=lines2.append, replace=False)
check(sc2.ibm_phi_file == "/scripted/by/hand/phi.dat",
      "5. replace=False keeps a phi path the script named itself")
check(sc2.init_cond_dll == "",
      f"5. ...and does NOT pair it with this stage's DLL ({sc2.init_cond_dll!r})")
check(any("keeping the immersed-solid inputs" in ln for ln in lines2),
      "5. ...saying which inputs it kept")
check(any("no init DLL" in ln and "WARNING" in ln for ln in lines2),
      "5. ...and naming the half now missing, since a phi with no DLL is unread")
check(any(out2["phi_dat"] in ln and "NOT what the solve reads" in ln
          for ln in lines2),
      "5. ...while still naming where the traced field went, so it is not lost")
check(not any("solver reads phi from" in ln for ln in lines2),
      "5. and NO 'solver reads phi from N cells' line, which used to attribute "
      "this stage's cell count to the file the solve actually reads")

sc2b = SolverConfig()
sc2b.init_cond_dll = "/scripted/by/hand/ibm_init.cc"
ib_handoff.link_phi_to_solver(sc2b, phi_tec, cfg, _tmp, replace=False)
check(sc2b.ibm_phi_file == ""
      and sc2b.init_cond_dll == "/scripted/by/hand/ibm_init.cc",
      "5. the reverse pairing is refused too: an explicitly named DLL is not "
      "fed this stage's field (a real case does exactly this — an analytic-shape "
      "DLL with ibm_phi_file blank)")

sc2c = SolverConfig()
ib_handoff.link_phi_to_solver(sc2c, phi_tec, cfg, _tmp, replace=False)
check(sc2c.ibm_phi_file and sc2c.init_cond_dll,
      "5. ...but when BOTH are blank the stage supplies both")

sc3 = SolverConfig()
empty = write_phi_tec(os.path.join(_tmp, "empty_phi_tec.dat"), rows=[])
try:
    ib_handoff.link_phi_to_solver(sc3, empty, cfg, _tmp)
    refused = False
except ib_handoff.IbHandoffError:
    refused = True
check(refused, "6. a phi field with no data rows is refused, not silently emptied")
try:
    ib_handoff.link_phi_to_solver(SolverConfig(), os.path.join(_tmp, "nope.dat"),
                                  cfg, _tmp)
    missing_refused = False
except ib_handoff.IbHandoffError:
    missing_refused = True
check(missing_refused, "6. a missing phi field is refused too")


# --------------------------------------------------------------------------- #
print("\n--- 7. the headless chain, by AST ---", flush=True)
# --------------------------------------------------------------------------- #
runner_src = read("services", "pipeline_runner.py")
tree = ast.parse(runner_src)
fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

solver_fn = fns.get("_run_solver")
params = [a.arg for a in solver_fn.args.args] if solver_fn else []
check("phi" in params, f"7. _run_solver takes phi ({params})")

def calls_to(fn, name, attr=False):
    hits = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if attr and isinstance(f, ast.Attribute) and f.attr == name:
            hits.append(n)
        elif not attr and isinstance(f, ast.Name) and f.id == name:
            hits.append(n)
    return hits

passed_artifact = False
for call in calls_to(fns["run_pipeline"], "_run_solver"):
    for kw in call.keywords:
        v = kw.value
        if (kw.arg == "phi" and isinstance(v, ast.Subscript)
                and isinstance(v.value, ast.Name) and v.value.id == "out"
                and isinstance(v.slice, ast.Constant) and v.slice.value == "phi"):
            passed_artifact = True
check(passed_artifact,
      '7. run_pipeline passes the produced out["phi"] into _run_solver')

handed_off = False
for call in calls_to(solver_fn, "link_phi_to_solver", attr=True):
    if any(isinstance(a, ast.Name) and a.id == "phi" for a in call.args):
        handed_off = True
check(handed_off, "7. _run_solver hands its phi to link_phi_to_solver")
check("if phi and sc.immersed_solid:" in runner_src
      and "immersed_solid off" in runner_src,
      "7. ...only when the SCRIPT declares an immersed solid, and says so when "
      "it does not (a stage may not turn the solid on by itself)")


# --------------------------------------------------------------------------- #
print("\n--- 8. GUI Run All ---", flush=True)
# --------------------------------------------------------------------------- #
from PyQt6.QtWidgets import QApplication                     # noqa: E402
_app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController                     # noqa: E402

c = AppController()
reached = []
c._pipe_mesh = lambda: reached.append("mesh")
logged = []
c.log = logged.append

# The route into meshing must go through the IB stage, from BOTH entries.
c._pipe_stl3d = lambda: reached.append("ib")
c._pipe_cad_queue = []
c._pipe_resample_next()
check(reached == ["ib"],
      f"8. an emptied CAD queue enters the IB stage, not the mesh ({reached})")
del c._pipe_stl3d
# The other entry — a case with no CAD to resample — starts at the same stage.
# Checked in the source rather than by driving it, because reaching that branch
# needs a whole geometry-less-but-mesh-ready controller state.
_gui_tree = ast.parse(read("controllers", "pipeline_ctrl.py"))
_gui_fns = {n.name: n for n in ast.walk(_gui_tree)
            if isinstance(n, ast.FunctionDef)}
_starts = {a.func.attr for a in ast.walk(_gui_fns["run_full_pipeline"])
           if isinstance(a, ast.Call) and isinstance(a.func, ast.Attribute)
           and a.func.attr.startswith("_pipe_")}
check("_pipe_stl3d" in _starts and "_pipe_mesh" not in _starts,
      f"8. ...and so does the no-CAD start of run_full_pipeline ({sorted(_starts)})")

# No STL configured: skip out loud, then mesh.
reached.clear()
logged.clear()
c.global_stl3d_config = Stl3dConfig()
c._pipe_stl3d()
check(reached == ["mesh"], f"8. no STL -> straight on to meshing ({reached})")
check(any("skipped" in ln and "STL" in ln for ln in logged),
      f"8. ...and the skip is a visible line, not silence ({logged})")

# A finished stage, with the Solver stage declaring an immersed solid: hand off,
# then mesh.
reached.clear()
logged.clear()
c.global_stl3d_config = cfg
c._stl3d_phi_path = phi_tec
c.global_solver_config.ibm_phi_file = ""
c.global_solver_config.init_cond_dll = ""
c.global_solver_config.immersed_solid = True
c._pipe_after_stl3d(0)
if c.global_solver_config.init_cond_dll.startswith(_REPO):
    _CLEANUP.append(c.global_solver_config.init_cond_dll)
check(reached == ["mesh"], f"8. a finished IB stage proceeds to mesh ({reached})")
check(os.path.basename(c.global_solver_config.ibm_phi_file) == "ibtest_phi.dat"
      and c.global_solver_config.init_cond_dll.endswith(".cc"),
      "8. ...having wired BOTH the phi field and its DLL into the solver config "
      f"({os.path.basename(c.global_solver_config.ibm_phi_file)})")
check(c.main_window.solver_config_panel.get_config().ibm_phi_file
      == c.global_solver_config.ibm_phi_file,
      "8. ...and pushed it to the panel (the panel is a view of the model)")

# ...and with Immersed Solid OFF, the stage may not turn it on for the user.
reached.clear()
logged.clear()
c.global_solver_config.ibm_phi_file = ""
c.global_solver_config.init_cond_dll = ""
c.global_solver_config.immersed_solid = False
c._pipe_after_stl3d(0)
check(reached == ["mesh"] and not c.global_solver_config.immersed_solid
      and c.global_solver_config.ibm_phi_file == "",
      "8. Immersed Solid off: Run All neither turns it on nor wires phi "
      f"(immersed={c.global_solver_config.immersed_solid})")
check(any("Immersed Solid OFF" in ln for ln in logged),
      f"8. ...and names the box that would include it ({logged})")

# A failed stage aborts the pipeline instead of meshing without a solid.
reached.clear()
logged.clear()
c._pipeline_running = True
c._pipe_after_stl3d(1)
check(reached == [] and not c._pipeline_running,
      f"8. a failed IB stage aborts and does NOT mesh ({reached})")


# --------------------------------------------------------------------------- #
print("\n--- 9. one owner for the conversion ---", flush=True)
# --------------------------------------------------------------------------- #
ctrl_src = read("controllers", "stl3d_ctrl.py")
check("link_phi_to_solver" in ctrl_src and "open(phi_tec)" not in ctrl_src,
      "9. send_stl3d_to_solver delegates and keeps no private header-strip")
check("PHI_HEADER_LINES" in read("services", "ib_handoff.py")
      and "skiprows" not in ctrl_src,
      "9. the header count lives in the service alone")
for f in sorted(os.listdir(os.path.join(_APP, "controllers"))):
    if f.endswith(".py") and "render_phi_field_init" in read("controllers", f):
        check(False, f"9. {f} renders the init DLL itself instead of via the "
                     "service (a second private copy is how this drifted before)")
        break
else:
    check(True, "9. no controller renders the init DLL itself")

# --------------------------------------------------------------------------- #
print("\n--- 10. the next stage can actually consume it ---", flush=True)
# --------------------------------------------------------------------------- #
# A hand-off is only real if the stage downstream accepts it. ``stage_dll``
# returns "" and logs a mere WARNING when a compile fails, so a generated DLL
# source that does not build degrades SILENTLY to "no init DLL" and the solve
# runs with a default initial condition — which is why this compiles the .cc the
# hand-off just wrote rather than trusting that it renders.
import shutil                                                # noqa: E402
from app.services import solver_case                         # noqa: E402

if shutil.which("g++"):
    dll_dir = os.path.join(_tmp, "dll")
    work_dir = os.path.join(_tmp, "work")
    os.makedirs(dll_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)
    dll_log = []
    ref = solver_case.stage_dll(out["init_dll"], dll_dir, rel_prefix="../dll",
                                log=dll_log.append)
    check(ref == "../dll/ibm_init_ibtest.so"
          and os.path.exists(os.path.join(dll_dir, "ibm_init_ibtest.so")),
          f"10. the generated init DLL compiles ({ref or dll_log})")
    solver_case.stage_phi_file(out["phi_dat"], work_dir, log=dll_log.append)
    staged = os.path.join(work_dir, "phi.dat")
    with open(staged) as f:
        check(f.readlines() == _ROWS,
              "10. ...and phi.dat lands in the work dir headerless, as the DLL "
              "reads it")
else:
    print("SKIP 10. g++ unavailable (cannot compile the generated DLL)",
          flush=True)

# --------------------------------------------------------------------------- #
print("\n--- 11. a shipped example actually covers the pair ---", flush=True)
# --------------------------------------------------------------------------- #
# No script under config/pipeline/ had ever carried both an `stl3d` and a
# `solver` section, so the section -> config converter the runner calls
# (PipelineConfig.build_stl3d_config) was exercised by nothing, and the schema
# half of this hand-off was uncovered even once the wiring was gated. Writing the
# example is what found the defect check 11.4 pins.
from app.models.pipeline_config import PipelineConfig                # noqa: E402
from app.models.stl3d_config import stl_bounding_box                 # noqa: E402
from app.services import stl3d_case                                  # noqa: E402

demo = os.path.join(_REPO, "config", "pipeline", "ib_demo.json")
check(os.path.exists(demo), f"11. {os.path.basename(demo)} is shipped")
pc = PipelineConfig.load_from_file(demo)
check(bool(pc.stl3d) and bool(pc.solver),
      "11. it carries BOTH an stl3d and a solver section (no script did)")
check(pc.solver.get("immersed_solid") is True
      and pc.solver.get("ibm_phi_file") == ""
      and pc.solver.get("init_cond_dll") == "",
      "11. ...declaring the solid but leaving both IB inputs blank, so the "
      "hand-off is what supplies them — which is the point of the example")
s3 = pc.build_stl3d_config(_REPO)
check(os.path.isabs(s3.stl_path) and os.path.exists(s3.stl_path),
      f"11. a RELATIVE stl_path resolves against the repo like a CAD input does "
      f"({os.path.relpath(s3.stl_path, _REPO)})")
check(pc.build_stl3d_config().stl_path == pc.stl3d["stl_path"],
      "11. ...and is left alone when no repo is given (round-trip callers)")
problems = stl3d_case.validate(s3)
check(problems == [], f"11. the IB stage accepts the example ({problems})")
bb = stl_bounding_box(s3.stl_path)
check(s3.xmin < bb[0] and bb[1] < s3.xmax and s3.ymin < bb[2] and bb[3] < s3.ymax,
      f"11. the immersed body sits inside the phi box "
      f"(body {[round(v, 3) for v in bb[:4]]}, box "
      f"{(s3.xmin, s3.xmax, s3.ymin, s3.ymax)})")
m = pc.mesh
check(m["domain_x_min"] < s3.xmin and s3.xmax < m["domain_x_max"]
      and m["domain_y_min"] < s3.ymin and s3.ymax < m["domain_y_max"],
      "11. ...and the phi box inside the mesh domain, so the field covers cells "
      "the solve actually has")
check("sc.immersed_solid = True" in read("controllers", "stl3d_ctrl.py"),
      "11. Send to Solver declares the solid itself (the button may have the "
      "opinion the stage may not)")

for p in _CLEANUP:
    try:
        os.remove(p)
    except OSError:
        pass

if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
