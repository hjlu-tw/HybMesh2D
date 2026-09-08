#!/usr/bin/env python3
"""A headless run must solve the boundary conditions the MESH declares.

#91, blocked by #90. `services/solver_case.py` writes `<case>.bc.def` from
`SolverConfig.bc_definitions` when it has any, and otherwise copies the table
getPGrid wrote for itself. getPGrid does not know the name `farfield` and
defaults those patches to a NO-SLIP ADIABATIC WALL. Nothing in the headless path
populated `bc_definitions`, so the fallback always won.

Measured on the shipped C-grid demo (2026-09-07, and still on disk in this
checkout as `results/solver/multiblock_cgrid_demo/work/multiblock_cgrid_demo.bc.def`):
the four `farfield` patches came back flag 2 instead of flag 1 — a body solved in
a CLOSED VISCOUS BOX rather than external flow. Exit 0, 100 iterations, no NaN,
a plausible contour plot. Nothing said a word.

A GUI-authored script was never affected: a saved `.hws` carries
`project.solver_config` wholesale, so its `bc_definitions` travel with it. A
HAND-WRITTEN pipeline script was — and that is every script in
`config/pipeline/`, the documented headless entry points, including the one CI
runs end to end.

**This is the first automated coverage of the `.bnd` name -> solver flag
mapping**, which #55, #57 and #85 all name as an outstanding blind spot. Before
this file the mapping was exercised only by hand-editing a `.bc.def` before each
recorded acceptance run.

Checks:
 1. the premise, from the shipped mesh itself: its patch names, and the fact that
    a `farfield` patch must be flag 1 while the recorded run gave it 2
 2. the shipped C-grid script states NO `bc_definitions`, so it is exactly the
    case the fix is for — asserted, since the fix is invisible if it isn't
 3. `derive_bc_definitions` fills an empty table from the mesh's own `.bnd`:
    every `farfield`/`outlet` flag 1, every `wall` flag 2
 4. a script that STATES the table wins — deriving fills a gap, it never
    overwrites a declaration
 5. no `.bnd`, or one with no patches, derives NOTHING and says so, leaving the
    pre-#91 getPGrid fallback exactly as it was
 6. through the REAL `prepare_case_dir`: `work/<case>.bc.def` — the file the
    solver actually reads — carries those flags
 7. …and `stage_bc_def_companion` does NOT then overwrite it with getPGrid's
    table, which is the one way the fix could be undone one line later
 8. …while with nothing derived the companion still copies, so the fallback that
    served the un-meshed case is untouched
 9. END TO END on the shipped script with the real binaries: the `.bc.def` on
    disk after a real mesher -> getPGrid -> unicones run. OPT-IN — see below
10. the mapping ITSELF, read out of getPGrid's own `getBCType` C++ and compared
    token by token, so the coverage is the whole table and not one mesh's four
    names. One divergence is PINNED with both values and its reason

THE ACCEPTANCE RUN, DATED. 2026-09-08, this checkout, `run_pipeline.sh
config/pipeline/multiblock_cgrid_demo.json` with NO edit to the script:

    case          results/solver/multiblock_cgrid_demo_003/
    exit          0 / 0 / 0 (mesher, getPGrid, unicones), ~2.5 s wall
    work/*.bc.def 1=2 2=2 (wall)  3=1 4=1 (outlet)  5..8=1 (farfield)
    grid/*.bc.def 1=2 2=2 3=1 4=1 5..8=2   <- getPGrid's own, correctly NOT copied
    iterations    100 requested, convergence rows to 90, residuals O(1e-4), no NaN

That is the first time the PIPELINE route reproduced #57's and #85's recorded
operating point instead of approximating it: every non-wall patch at flag 1, the
value those runs got by hand-editing the `.bc.def` before each solve.

Check 9 is OPT-IN (`HYBMESH_E2E_SOLVER=1`) even though it costs only seconds
here, because a real run auto-versions a NEW `results/solver/<case>_NNN/` every
time and a suite run must not grow the user's tree unasked. CI has no solver
binary in any case.

WHAT RUNS UNCONDITIONALLY IS WEAKER THAN #91's WORDING, and that is said here
rather than left to be discovered. The criterion asks for "a test [that] drives
the headless path on a shipped case and asserts the flags in the produced
`.bc.def`". Checks 6-7 do drive the real `prepare_case_dir` /
`stage_bc_def_companion` and assert the flags in the file they produce, using the
SHIPPED script's own solver section — but from a SYNTHETIC `.bnd`, so that they
run in a clean clone with nothing built. The shipped mesh itself is reached by
check 1 (skips when it is not built) and check 9 (opt-in). Nothing that runs
everywhere ties the flag assertion to a file the mesher actually wrote. Check 1
is what stops the fixture drifting away from the mesh it stands in for.

Run:  python3 tools/PreProcessor/tests/test_pipeline_bc_from_mesh.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def skip(msg):
    print("SKIP " + msg, flush=True)


def read_def(path):
    """``{segment_no: bc_flag}`` from a solver ``.def`` table, header dropped."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit():
                out[int(parts[0])] = int(parts[1])
    return out


from app.services import pipeline_bc_derive, solver_case             # noqa: E402
from app.services.pipeline_bc_derive import derive_bc_definitions    # noqa: E402
from app.services.bnd_io import default_bc_flag_for_name             # noqa: E402
from app.services.bnd_io import read_bnd_segments                    # noqa: E402
from app.models.pipeline_config import PipelineConfig                # noqa: E402

_SCRIPT = os.path.join(_REPO, "config", "pipeline", "multiblock_cgrid_demo.json")
_MESH_BND = os.path.join(_REPO, "results", "meshes", "multiblock_cgrid_demo",
                         "mesh_multiblock_cgrid_demo.bnd")
# The C-grid demo's eight patches. A fixture rather than the shipped mesh, so
# checks 3-8 run in a fresh clone with nothing built — check 1 is what stops the
# fixture drifting away from the mesh it stands in for.
_PATCHES = [(1, "wall"), (2, "wall"), (3, "outlet"), (4, "outlet"),
            (5, "farfield"), (6, "farfield"), (7, "farfield"), (8, "farfield")]
_WANT = {1: 2, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1}

tmp = tempfile.mkdtemp(prefix="hybmesh_pipe_bc_")


def write_bnd(path, patches):
    """A STAR-CD `.bnd`: segment id is column 6, patch name column 8."""
    with open(path, "w", encoding="utf-8") as f:
        for i, (sid, name) in enumerate(patches, start=1):
            f.write(f"{i:>6}{i:>8}{i + 1:>8}{0:>8}{0:>8}{sid:>8}{0:>8}  {name}\n")
    return path


# ── 1. the premise, from the shipped mesh ────────────────────────────────────
if os.path.exists(_MESH_BND):
    _real = read_bnd_segments(_MESH_BND)
    check(_real == _PATCHES,
          f"1. the shipped C-grid mesh names the eight patches this file's "
          f"fixture stands in for ({_real})")
else:
    skip("1. the shipped C-grid mesh is not built here — the fixture is unchecked "
         "against it (run ./run.sh -conf config/multiblock_cgrid.dat)")
check(default_bc_flag_for_name("farfield") == 1
      and default_bc_flag_for_name("outlet") == 1
      and default_bc_flag_for_name("wall") == 2,
      "1. a farfield/outlet patch is a non-reflect far field (flag 1) and a wall "
      "is no-slip adiabatic (flag 2), per getPGrid's own BCType enum")

_RECORDED = os.path.join(_REPO, "results", "solver", "multiblock_cgrid_demo",
                         "work", "multiblock_cgrid_demo.bc.def")
if os.path.exists(_RECORDED):
    _rec = read_def(_RECORDED)
    check(_rec.get(5) == 2 and _rec.get(1) == 2,
          f"1. …and the run recorded on disk gave patch 5 (`farfield`) flag "
          f"{_rec.get(5)} — the same flag as the wall, which is the defect ({_rec})")
else:
    skip("1. no recorded C-grid run in results/solver/ to quote the defect from")

# ── 2. the shipped script states nothing ─────────────────────────────────────
_pcfg = PipelineConfig.load_from_file(_SCRIPT)
_sc_shipped = _pcfg.build_solver_config(_REPO)
check(not _sc_shipped.bc_definitions,
      f"2. the shipped C-grid script declares NO bc_definitions, so it is the "
      f"case #91 is about ({_sc_shipped.bc_definitions})")

# ── 3. derive fills an empty table ───────────────────────────────────────────
_bnd = write_bnd(os.path.join(tmp, "mesh.bnd"), _PATCHES)
_sc = _pcfg.build_solver_config(_REPO)
_sc.input_bnd_file = _bnd
_LOG = []
_n = derive_bc_definitions(_sc, {}, log=_LOG.append)
check(_n == 8
      and {r["segment_no"]: r["bc_type"] for r in _sc.bc_definitions} == _WANT
      and [r["name"] for r in _sc.bc_definitions] == [n for _s, n in _PATCHES],
      f"3. the mesh's own patches decide the table: farfield/outlet 1, wall 2 "
      f"({[(r['segment_no'], r['bc_type'], r['name']) for r in _sc.bc_definitions]})")
check(any("farfield" in m or "8" in m for m in _LOG),
      f"3. …and it is said out loud rather than happening silently ({_LOG})")

# ── 4. an explicit declaration wins ──────────────────────────────────────────
_stated = [{"segment_no": 5, "bc_type": 3, "values": "2.5", "name": "farfield"}]
_sc2 = _pcfg.build_solver_config(_REPO)
_sc2.input_bnd_file = _bnd
_sc2.bc_definitions = [dict(r) for r in _stated]
_n2 = derive_bc_definitions(_sc2, {}, log=_LOG.append)
check(_n2 == 0 and _sc2.bc_definitions == _stated,
      f"4. a script that states the table keeps it, untouched — deriving fills a "
      f"gap, it never overwrites a declaration ({_sc2.bc_definitions})")

# ── 5. nothing to derive from ────────────────────────────────────────────────
_sc3 = _pcfg.build_solver_config(_REPO)
_sc3.input_bnd_file = os.path.join(tmp, "does_not_exist.bnd")
_n3 = derive_bc_definitions(_sc3, {}, log=_LOG.append)
_empty = write_bnd(os.path.join(tmp, "empty.bnd"), [])
_sc4 = _pcfg.build_solver_config(_REPO)
_sc4.input_bnd_file = _empty
_n4 = derive_bc_definitions(_sc4, {}, log=_LOG.append)
check(_n3 == 0 and not _sc3.bc_definitions and _n4 == 0 and not _sc4.bc_definitions,
      f"5. a missing or patch-less .bnd derives nothing and leaves the table "
      f"empty, so the pre-#91 getPGrid fallback still applies ({_n3}, {_n4})")

# ── 6-8. through the real case writer ────────────────────────────────────────
_case_root = os.path.join(tmp, "repo")
os.makedirs(os.path.join(_case_root, "results", "solver"), exist_ok=True)
_orig_repo_root = solver_case.repo_root
solver_case.repo_root = lambda: _case_root

# prepare_case_dir stages the STAR-CD trio into grid/, so they must exist.
for _ext in (".vrt", ".cel"):
    with open(os.path.join(tmp, "mesh" + _ext), "w") as _f:
        _f.write("stub\n")
_sc.input_vrt_file = os.path.join(tmp, "mesh.vrt")
_sc.input_cel_file = os.path.join(tmp, "mesh.cel")
_sc.case_name = "bc_from_mesh"
_work, _grid, _ = solver_case.prepare_case_dir(_sc, log=_LOG.append)
_def_name = os.path.basename(_sc.output_bc_file) + ".def"
_work_def = os.path.join(_work, _def_name)
check(os.path.exists(_work_def) and read_def(_work_def) == _WANT,
      f"6. the file the SOLVER reads — work/{_def_name} — carries the mesh's "
      f"flags ({read_def(_work_def) if os.path.exists(_work_def) else 'missing'})")

# getPGrid then writes its OWN table into grid/. It must not win.
with open(os.path.join(_grid, _def_name), "w", encoding="utf-8") as _f:
    _f.write("segm_no   bc_flag\n" + "".join(
        f"   {s:>6}   {2:>6}\n" for s, _n in _PATCHES))
solver_case.stage_bc_def_companion(_sc, _grid, _work, log=_LOG.append)
check(read_def(_work_def) == _WANT,
      f"7. getPGrid's own table does NOT overwrite the derived one — the one way "
      f"this fix could be undone a line later ({read_def(_work_def)})")

_sc5 = _pcfg.build_solver_config(_REPO)
_sc5.case_name = "no_derivation"
_sc5.bc_definitions = []
_work5 = os.path.join(_case_root, "results", "solver", "no_derivation", "work")
_grid5 = os.path.join(_case_root, "results", "solver", "no_derivation", "grid")
os.makedirs(_work5, exist_ok=True)
os.makedirs(_grid5, exist_ok=True)
_def5 = os.path.basename(_sc5.output_bc_file) + ".def"
with open(os.path.join(_grid5, _def5), "w", encoding="utf-8") as _f:
    _f.write("segm_no   bc_flag\n   1   2\n")
solver_case.stage_bc_def_companion(_sc5, _grid5, _work5, log=_LOG.append)
check(os.path.exists(os.path.join(_work5, _def5)),
      "8. …while with nothing derived the companion is still copied, so the "
      "fallback that serves an un-meshed case is untouched")
solver_case.repo_root = _orig_repo_root

# ── 9. end to end, with the real binaries ────────────────────────────────────
from app.services.paths import find_solver_executables                # noqa: E402

_bins = find_solver_executables()
_mesher = os.path.join(_REPO, "build", "HybMesh2D")
if not (_bins.get("getpgrid") and _bins.get("solver") and os.path.exists(_mesher)):
    skip("9. end-to-end run needs ./build.sh AND a solver tree "
         f"(mesher={os.path.exists(_mesher)}, getpgrid={bool(_bins.get('getpgrid'))}, "
         f"solver={bool(_bins.get('solver'))}) — CI has neither binary")
elif not os.environ.get("HYBMESH_E2E_SOLVER"):
    # OPT-IN, and the minutes it costs are not the only reason: a real run
    # auto-versions a NEW results/solver/multiblock_cgrid_demo_NNN/ every time,
    # so a suite that ran it on every invocation would grow the user's tree
    # without being asked. The dated run that ACCEPTED #91 is quoted in this
    # file's docstring, the way every solver run in this repo is recorded.
    skip("9. end-to-end run is opt-in: HYBMESH_E2E_SOLVER=1 python3 "
         "tools/PreProcessor/tests/test_pipeline_bc_from_mesh.py")
else:
    _rc = subprocess.run(
        [os.path.join(_REPO, "run_pipeline.sh"), _SCRIPT],
        cwd=_REPO, capture_output=True, text=True, timeout=1800)
    # The case auto-versions rather than clobbering, so take the newest — and
    # glob the .def rather than naming it: auto-versioning renames the case, and
    # `output_bc_file` follows the case name, so `<case>_002.bc.def` is what is
    # really on disk.
    _root = os.path.join(_REPO, "results", "solver")
    _cases = sorted((d for d in os.listdir(_root)
                     if d.startswith("multiblock_cgrid_demo")),
                    key=lambda d: os.path.getmtime(os.path.join(_root, d)))
    _got, _defs = {}, []
    if _cases:
        _w = os.path.join(_root, _cases[-1], "work")
        _defs = [f for f in os.listdir(_w) if f.endswith(".bc.def")]
        if len(_defs) == 1:
            _got = read_def(os.path.join(_w, _defs[0]))
    check(_rc.returncode == 0 and _got == _WANT,
          f"9. a real headless run of the SHIPPED script, with no edit to it, "
          f"leaves the solver a table with every farfield/outlet at flag 1 "
          f"(rc={_rc.returncode}, case={_cases[-1] if _cases else '?'}, "
          f"def={_defs}, {_got})")

# ── 11. the ORDERING, read from the runner's source ──────────────────────────
# Check 7 catches a companion copy that lands on top of the derived table. This
# states the rule that prevents it: the derivation runs BEFORE prepare_case_dir,
# which is what writes work/<bc>.def FROM bc_definitions. Deriving afterwards
# would leave a correct table in memory and a wrong one on disk.
_runner_src = open(os.path.join(_GUI, "app", "services", "pipeline_runner.py"),
                   encoding="utf-8").read()
_rs_body = _runner_src[_runner_src.index("def _run_solver("):]
_rs_body = _rs_body[:_rs_body.index("\ndef ")]
_i_derive = _rs_body.find("derive_bc_definitions(")
_i_prep = _rs_body.find("solver_case.prepare_case_dir(")
check(_i_derive > 0 and _i_prep > 0 and _i_derive < _i_prep,
      f"11. _run_solver derives the BC table BEFORE prepare_case_dir writes it "
      f"out (derive@{_i_derive}, prepare@{_i_prep})")
check("derive_bc_definitions" in _runner_src
      and pipeline_bc_derive.derive_bc_definitions is derive_bc_definitions,
      "11. …and it is the runner that calls it, not only this test")

# ── 10. the mapping itself, against getPGrid's OWN source ────────────────────
# The blind spot #55, #57 and #85 all name is "the .bnd name -> solver flag
# mapping is not exercised". Checks 1-9 exercise it on ONE mesh's four names;
# this exercises the WHOLE table against the C++ that defines it, so a token
# added to either side without the other fails the build.
import re                                                            # noqa: E402
from app.services.bnd_io import _NAME_TO_FLAG                        # noqa: E402

_GP = os.path.join(_REPO, "solver", "preprocess", "getPGrid", "src")
# getPGrid's lowercase `nozzle` is FIXED_BC_Q (50) while its `NOZZLE` is a
# no-slip wall (2). `default_bc_flag_for_name` is deliberately CASE-INSENSITIVE
# — a GUI patch label must not mean two different things depending on how it was
# typed — so it CANNOT represent a token whose meaning flips with case, and
# picks the wall. Pinned with BOTH values, not silenced: flag 50 also requires
# trailing `rho u v et` values that no patch name can supply, so deriving it
# would write a row the solver cannot read.
_PINNED = {"nozzle": (50, 2)}

if not os.path.isdir(_GP):
    skip("10. no getPGrid source in this checkout to compare the mapping against")
else:
    _src = open(os.path.join(_GP, "getPGrid.cpp"), encoding="utf-8",
                errors="replace").read()
    _body = _src[_src.index("BCType getBCType("):]
    _body = _body[:_body.index("\n  }")]
    _enum = open(os.path.join(_GP, "bc.hh"), encoding="utf-8").read()
    _enum = _enum[_enum.index("enum BCType"):]
    _vals = {m.group(1): int(m.group(2))
             for m in re.finditer(r"(\w+)\s*=\s*(\d+)", _enum)}
    _parts = re.split(r"return\s+(\w+)\s*;", _body)
    _gp = {}
    for _i in range(1, len(_parts), 2):
        for _n in re.findall(r's\s*==\s*"([^"]+)"', _parts[_i - 1]):
            _gp[_n] = _vals[_parts[_i]]
    check(len(_gp) == 25 and _gp.get("wall") == 2 and _gp.get("outlet") == 1,
          f"10. getPGrid's own getBCType table was READ, not assumed "
          f"({len(_gp)} tokens)")
    _diff = {n: (f, default_bc_flag_for_name(n))
             for n, f in sorted(_gp.items())
             if default_bc_flag_for_name(n) != f}
    check(_diff == _PINNED,
          f"10. every token getPGrid knows maps to the same flag here, with one "
          f"PINNED case-fold collision ({_diff})")
    _extra = sorted(k for k in _NAME_TO_FLAG if k not in {n.lower() for n in _gp})
    check(_extra == ["far-field", "far_field", "farfield", "moving_wall",
                     "movingwall", "slip", "symmetry"],
          f"10. …and the GUI's own additions are exactly the friendly aliases "
          f"getPGrid does NOT know — `farfield` among them, which is the whole "
          f"of #91 ({_extra})")

shutil.rmtree(tmp, ignore_errors=True)
print()
if _FAILS:
    print(f"{len(_FAILS)} FAILED:")
    for m in _FAILS:
        print("  - " + m)
print(f"{len(_FAILS)} failure(s)" if _FAILS else "all checks passed")
os._exit(1 if _FAILS else 0)
