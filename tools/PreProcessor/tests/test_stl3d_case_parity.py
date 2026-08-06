#!/usr/bin/env python3
"""STL3d (immersed-solid) staging + para.in ↔ C++ stdin parity.

Two things are covered, and the second one is why this file exists.

**The bug it locks out.** ``Stl3dConfig.para_in_text()`` wrote SIX lines, the
second being an ASCII-vs-binary ``y/n`` answer. But ``stl3d.cpp`` was changed to
auto-detect the STL format from the file instead of prompting (its own comment says
so), leaving only FIVE ``cin >>`` reads. The extra line was therefore consumed as
the **case name**: the real case name was then read as the domain, ``cin`` failed on
that non-numeric token, and the run produced an empty phi field under the wrong
filename (``y_phi_tec.dat``) — with a zero exit code. The GUI was affected exactly
the same way, since it shares the same writer.

That is a Python-writer ↔ C++-reader drift, the same class as
``test_gui_cpp_config_parity.py`` guards for the mesh ``.dat``. So this test parses
the ``cin >>`` sequence out of ``stl3d.cpp`` and asserts para.in matches it, line
for line.

Checks:
 1. para.in has exactly as many lines as stl3d.cpp has stdin reads, in order.
 2. There is no ASCII y/n line (the binary auto-detects).
 3. The case name is on the line the binary reads as the case name, so the
    predicted output filenames match what the binary will actually write.
 4. Staging is shared: services/stl3d_case lays out the work dir, and the GUI
    controller uses it rather than its own copy.
 5. Validation accepts a DEGENERATE z range (this is a 2D project: the STL is a
    flat z=0 sheet) but rejects an inverted one.
 6. The headless runner really has an IB stage now, honouring "skip" and --no-ib.

Run:  python3 tools/PreProcessor/tests/test_stl3d_case_parity.py
"""
import inspect
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

STL3D_CPP = os.path.join(_REPO, "solver", "preprocess", "STL3d", "src", "stl3d.cpp")

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


from app.models.stl3d_config import Stl3dConfig  # noqa: E402
from app.services import stl3d_case  # noqa: E402


def make_cfg() -> Stl3dConfig:
    cfg = Stl3dConfig()
    cfg.stl_path = "/tmp/some model.stl"        # deliberately contains a space
    cfg.case_name = "parity case"              # and so does the case name
    cfg.xmin, cfg.xmax = -1.0, 2.0
    cfg.ymin, cfg.ymax = -0.5, 0.5
    cfg.zmin, cfg.zmax = 0.0, 0.0              # 2D: flat sheet at z = 0
    cfg.nx, cfg.ny, cfg.nz = 30, 24, 1
    cfg.all_search = True
    return cfg


cfg = make_cfg()
lines = cfg.para_in_text().rstrip("\n").split("\n")

# ── 1/2/3. parity against the C++ stdin sequence ──────────────────────────
if not os.path.exists(STL3D_CPP):
    print(f"SKIP {STL3D_CPP} not found (solver sources absent)", flush=True)
else:
    src = open(STL3D_CPP, encoding="utf-8", errors="replace").read()
    # main() is what reads stdin; the #if'd-out demo block above it does not.
    main_body = src[src.rindex("string fn;"):]
    reads = re.findall(r"cin\s*>>\s*([^;]+);", main_body)
    # Each `cin >> a >> b >> c;` consumes one whitespace-separated line in para.in.
    read_groups = [[t.strip() for t in r.split(">>")] for r in reads]
    print(f"     stl3d.cpp reads: {[' '.join(g) for g in read_groups]}", flush=True)

    check(len(lines) == len(read_groups),
          f"1. para.in line count matches the binary's stdin reads "
          f"({len(lines)} lines vs {len(read_groups)} reads)")

    if len(lines) == len(read_groups):
        # Per-line token counts must agree too: `cin >> xmin >> ... >> zmax`
        # consumes six numbers from one line.
        mismatched = [(i, len(lines[i].split()), len(g))
                      for i, g in enumerate(read_groups)
                      if len(lines[i].split()) != len(g)]
        check(not mismatched,
              "1. every para.in line supplies exactly as many tokens as its read"
              + (f" (line/got/want: {mismatched})" if mismatched else ""))

    # 2. No ascii y/n line. stl3d.cpp auto-detects, and its own comment says so.
    check("detect_ascii_stl" in main_body,
          "2. stl3d.cpp auto-detects the STL format (no ascii prompt)")
    first_reads = " ".join(" ".join(g) for g in read_groups[:2])
    check("ascii" not in first_reads.lower(),
          "2. ...and reads no ascii answer from stdin")
    check(len(lines) >= 2 and lines[1] not in ("y", "n"),
          f"2. para.in line 2 is NOT a y/n answer (got {lines[1]!r}) — that was "
          "the off-by-one that made the case name be read as 'y'")

    # 3. The case name must land on the line the binary reads as case_fn.
    case_idx = next((i for i, g in enumerate(read_groups)
                     if any("case" in t for t in g)), None)
    check(case_idx is not None, "3. found the case-name read in stl3d.cpp")
    if case_idx is not None:
        expected_case = "parity_case"          # sanitised: space -> underscore
        check(lines[case_idx] == expected_case,
              f"3. the case name is on line {case_idx + 1} "
              f"(got {lines[case_idx]!r}, want {expected_case!r})")
        stl_tec, phi_tec = cfg.output_basenames()
        check(phi_tec == f"{lines[case_idx]}_phi_tec.dat"
              and stl_tec == f"{lines[case_idx]}_stl_tec.dat",
              f"3. predicted output names match what the binary will write "
              f"({phi_tec})")

# The STL filename on line 1 must be whitespace-free (cin >> splits on spaces).
check(" " not in lines[0],
      f"0. the staged STL basename is a single token ({lines[0]!r})")

# ── 4. staging is shared, not duplicated ──────────────────────────────────
import app.controllers.stl3d_ctrl as stl3d_ctrl  # noqa: E402

ctrl_src = inspect.getsource(stl3d_ctrl)
check("stl3d_case.prepare_case_dir" in ctrl_src,
      "4. the GUI controller stages through services/stl3d_case")
check("shutil.copy2" not in ctrl_src and "para_in_text()" not in ctrl_src,
      "4. ...and no longer keeps its own copy of the staging logic")

wd = stl3d_case.work_dir_for(cfg, root="/tmp/root")
check(wd == os.path.join("/tmp/root", "results", "stl3d", "parity_case"),
      f"4. the work dir is results/stl3d/<sanitised case> ({wd})")

# ── 5. z may be degenerate (2D), but not inverted ─────────────────────────
check(stl3d_case.validate(cfg) == [] or all("Z" not in p for p in stl3d_case.validate(cfg)),
      "5. a flat z=0 STL (zmin == zmax) is accepted — this is a 2D project")
bad = make_cfg()
bad.zmin, bad.zmax = 1.0, 0.0
check(any("Z" in p for p in stl3d_case.validate(bad)),
      "5. ...but an inverted z range is rejected")
missing = make_cfg()
missing.stl_path = ""
check(any("STL" in p for p in stl3d_case.validate(missing)),
      "5. a missing STL path is rejected")
flat_x = make_cfg()
flat_x.xmax = flat_x.xmin
check(any("X" in p for p in stl3d_case.validate(flat_x)),
      "5. a degenerate X range IS rejected (only z may be flat)")

# ── 6. the headless runner has a real IB stage ────────────────────────────
import app.services.pipeline_runner as pr  # noqa: E402

runner_src = inspect.getsource(pr)
check("_run_stl3d" in runner_src,
      "6. the headless runner defines an immersed-solid stage")
check("does not execute it" not in runner_src,
      "6. ...and no longer says the stage is unimplemented")
check("run_ib" in inspect.signature(pr.run_pipeline).parameters,
      "6. run_pipeline takes run_ib (backing --no-ib)")
check('"phi"' in runner_src or "'phi'" in runner_src,
      "6. the produced phi path is reported among the artifacts")

if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    sys.exit(1)
print("\nRESULT: ALL PASS", flush=True)
sys.exit(0)
