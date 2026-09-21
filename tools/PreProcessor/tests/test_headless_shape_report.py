#!/usr/bin/env python3
"""The HEADLESS hosts report the mesher's cell-shape figures (issue #132, parent #128).

#129 and #130 made the mesher publish `mesh.quality` in the `.provenance.json`
sidecar for both generation paths, and #131 made the GUI panel quote it. This
gate holds the half a run nobody is watching depends on: `run_pipeline` reports
the figures when its mesh stage finishes, and the batch queue shows them per
case — from ONE reader, so a row and a log line cannot describe one mesh
differently.

What this pins down:

  1. THE REPORT'S THREE STATES, which are three different facts and must read as
     three different strings: measured (metric name + median/p95/max + the cell
     count), `not measured` (the mesher looked and could not — never `0.000`,
     which on a metric whose floor is 1.0 reads as perfection), and `not
     published` (no sidecar at all — never a blank, which in a column of numbers
     is read as a zero).
  2. ONE READER, ONE FORMATTER. Both hosts call `mesh_shape_stats.shape_report`;
     neither composes a sidecar name of its own, and the VIEW calls neither —
     the read happens once, Qt-free, off the GUI thread, and the row displays
     what the job carries.
  3. QT-FREE, in a subprocess: importing the reader, and importing the batch
     runner that calls it, leaves PyQt6 unimported. In-process this check can
     only ever say "PyQt6 is loaded" once anything else has imported it.
  4. NOTHING IS REPORTED OFF NOTHING. A case with no `vtk` artifact carries no
     figures at all (not "not published", which is a fact about a mesh), and the
     runner's own report sits BELOW the guard that refuses a stage producing no
     VTK.
  5. AGAINST THE REAL BINARY, BOTH PATHS (skipped without a build): the two
     shipped demo scripts the ticket names — a hybrid case and a `MESH_MODE 1`
     case — run through the batch queue, and for each one the row's figures, the
     `[Mesh] cell shape` line the pipeline runner logged, and the sidecar that
     run wrote are compared against each other. The two metric NAMES differ,
     which is what stops a quad midline ratio being read against a triangle edge
     ratio.
  6. THE GUI ROW. The dialog's Cell Shape cell is the job's report verbatim, and
     a case with no figures shows a dash whose tooltip points at the Status
     column rather than an empty cell — and does NOT say "this case made no
     mesh", which would be false for a case that meshed and then failed later.
  7. THE PANEL AND THE REPORT DO NOT DRIFT. #131's panel renders the same
     `ShapeSummary` as four rows and this renders it as one line; the two are not
     merged, because the layouts differ, so they are PINNED to each other — same
     precision, same metric name, same `not measured` wording.
  8. THE SPLIT REACHES BOTH HOSTS THROUGH THE LINE THEY ALREADY PRINT (#145),
     and NEITHER HOST CHANGED to get it. The old line is a PREFIX of the new one,
     so every token a script greps today survives; both halves follow it, layer
     first; an empty half says `not measured`; and A SIDECAR WRITTEN BEFORE THIS
     WORK reports exactly the line it always did, with no split clause at all —
     this ticket's acceptance, held as a string equality.
  9. ONE RENDERING OF A HALF, shared with the panel. The report's two clauses are
     `format_figures` verbatim and the panel calls the same function for its two
     rows, so unlike the whole-mesh set (pinned by 7 because the layouts differ)
     there is no second place where a half's precision or wording is decided.

Injections, RUN BY HAND on 2026-09-17 and dated here rather than claimed as
automated (the harness lived in a scratchpad and is not in the tree). Each was
scored by EXIT CODE first, because a mutation that crashes the gate prints zero
FAIL lines and would otherwise read as inert. **Two harness hazards bit during
this run and are recorded because they cost real work**: restoring by
`git checkout` reverted UNCOMMITTED edits in the same files (commit first, as
`.claude/rules` has said since #131), and a same-SIZE, same-second restore of
`mesh_shape_stats.py` was ignored by this platform's bytecode cache — the file on
disk was correct and the gate went on failing until it was `touch`ed. Eight, all
of which bit:

  a. `format_shape_report` renders an unmeasured summary as numbers
     -> red: 1 (`not measured`) and 1 (neither `0.000` nor the sentinel)
  b. `format_shape_report` returns "" for a missing sidecar
     -> red: 1 (`not published`), and ONLY that. 6's dash is fed by `_shape_of`'s
        own empty string, so it stays green — which is exactly why the blank has
        to be refused where the report is MADE and not only where it is shown.
  c. `_shape_of` drops its `if vtk` guard -> red: both 4s
  d. the runner's report is moved ABOVE the "produced no VTK" raise -> red: 4's
     ordering check
  e. the batch dialog reformats the report (`.2f` via a re-parse) -> red: BOTH of
     6's row checks, and NOT 5 — which compares the job's string against the log
     and never reads the table, so a view that diverges is visible only where the
     view is read. The two sections are not redundant.
  f. `batch_ctrl` stops clearing `job.shape` on a re-run -> red: 6's reset check
  g. the runner reads the sidecar itself (`json.load` on a composed
     `<stem>.provenance.json`) -> red: both of 2's pipeline_runner checks, AND 4's
     ordering check — the latter because its anchor is the report's exact
     spelling, which this mutation replaces. Honest but coupled, so that check now
     says when an anchor went MISSING rather than reporting it as an ordering
     defect.
  h. the report formats at `.2f` -> red: 1's precision check, 7, and BOTH of 5's
     "the figures are the ones that run PUBLISHED" checks — which rebuild the
     expected string from the sidecar JSON, so they carry the precision too. NOT
     an isolated probe of 7, and said so rather than claimed as one; what 7 adds
     over them is that it compares the PANEL against the report and would fire on
     a change to either side alone. (a) reddens 7 as well, for the unmeasured
     wording.

Run:  python3 tools/PreProcessor/tests/test_headless_shape_report.py
Section 5 skips cleanly if ./build/HybMesh2D has not been built.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_BINS = [os.path.join(_REPO, "build", n) for n in ("HybMesh2D", "surface_resampler")]
_BINS_READY = all(os.path.exists(b) for b in _BINS)
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >600s", flush=True)
    os._exit(99)


_wd = threading.Timer(600, _watchdog)
_wd.daemon = True
_wd.start()

from app.services import batch_runner, mesh_shape_stats  # noqa: E402

TMP = tempfile.mkdtemp(prefix="hybmesh_shape_hosts_")


def _sidecar(dirname: str, quality) -> str:
    """A mesh path with a sidecar beside it holding `quality` (or none)."""
    d = os.path.join(TMP, dirname)
    os.makedirs(d, exist_ok=True)
    mesh = os.path.join(d, "mesh.vtk")
    open(mesh, "w", encoding="utf-8").write("# not read by the reader\n")
    if quality is not None:
        doc = {"mesh": {"quality": quality}}
        with open(mesh[:-4] + ".provenance.json", "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
    return mesh


# ── 1. the report's three states ──────────────────────────────────────────
measured = _sidecar("measured", {"metric": "tri_edge_ratio", "cells": 11396,
                                 "median": 1.584671, "p95": 9.901041,
                                 "max": 35.608279})
unmeasured = _sidecar("unmeasured", {"metric": "quad_midline_ratio", "cells": 0,
                                     "median": -1.0, "p95": -1.0, "max": -1.0})
bare = _sidecar("bare", None)

r_measured = mesh_shape_stats.shape_report(measured)
check("tri_edge_ratio" in r_measured,
      f"1. the measured report names the metric ({r_measured})")
check("1.585" in r_measured and "9.901" in r_measured and "35.608" in r_measured,
      f"1. ...carries median, p95 and max at the panel's precision ({r_measured})")
check("11396" in r_measured,
      f"1. ...and the cell count the three cover ({r_measured})")

r_un = mesh_shape_stats.shape_report(unmeasured)
check("not measured" in r_un,
      f"1. a run that measured nothing says so ({r_un})")
check("0.000" not in r_un and "-1" not in r_un,
      f"1. ...and prints neither 0.000 (which reads as a perfect mesh on a metric "
      f"whose floor is 1.0) nor the negative sentinel ({r_un})")
check("quad_midline_ratio" in r_un,
      f"1. ...while still naming what was not measured ({r_un})")

r_bare = mesh_shape_stats.shape_report(bare)
check(r_bare.strip() and "not published" in r_bare,
      f"1. a mesh with no sidecar says the figures were never published ({r_bare})")
check(len({r_measured, r_un, r_bare}) == 3,
      "1. the three states are three distinct strings — none is another's blank")

# ── 2. one reader, one formatter ──────────────────────────────────────────
_SRC = {
    "pipeline_runner": os.path.join(_GUI, "app", "services", "pipeline_runner.py"),
    "batch_runner": os.path.join(_GUI, "app", "services", "batch_runner.py"),
    "batch_dialog": os.path.join(_GUI, "app", "views", "batch_dialog.py"),
}
_TREES = {k: ast.parse(open(p, encoding="utf-8").read(), p)
          for k, p in _SRC.items()}


def _calls_to(tree, module: str) -> list:
    """Names of `<module>.<fn>(...)` calls made anywhere in `tree`."""
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == module):
            out.append(node.func.attr)
    return out


for host in ("pipeline_runner", "batch_runner"):
    check("shape_report" in _calls_to(_TREES[host], "mesh_shape_stats"),
          f"2. {host} reads the figures through mesh_shape_stats.shape_report")
check(not _calls_to(_TREES["batch_dialog"], "mesh_shape_stats"),
      "2. the VIEW calls the reader for nothing — the read happens once, Qt-free "
      "and off the GUI thread, and the row displays what the job carries")


def _sidecar_name_literals(tree) -> list:
    """String constants that COMPOSE a sidecar name, i.e. end in the suffix.

    Prose mentioning `.provenance.json` is not this: the defect is a module
    spelling a second path convention, which reaches the reader's own suffix at
    the END of a literal it then joins onto a stem.

    DELIBERATELY WEAKER THAN `test_mesh_shape_panel.py` check 2, which refuses
    the substring anywhere in a code string of `mesh_shape_stats` itself. That
    module is the one that could plausibly compose a name, so there nothing is
    worth the hole; a HOST's job includes telling the user where the figures came
    from, and the batch dialog's tooltip says so in prose.
    """
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value.endswith(".provenance.json")]


for host, tree in _TREES.items():
    check(not _sidecar_name_literals(tree),
          f"2. {host} composes no sidecar name of its own — "
          f"{mesh_shape_stats.sidecar_for.__name__} is the one lookup "
          f"({_sidecar_name_literals(tree)})")

# ── 3. Qt-free, measured in a subprocess ──────────────────────────────────
_probe = (
    "import sys;"
    "sys.path.insert(0, %r);"
    "import app.services.mesh_shape_stats, app.services.batch_runner;"
    "print('PyQt6' in sys.modules)" % _GUI
)
p = subprocess.run([sys.executable, "-c", _probe], capture_output=True, text=True,
                   cwd=_REPO, timeout=120)
check(p.returncode == 0 and p.stdout.strip() == "False",
      f"3. the reader and the batch runner import with no PyQt6 — a headless host "
      f"acquires no GUI dependency (rc={p.returncode}, out={p.stdout.strip()!r}, "
      f"err={p.stderr.strip()[-160:]!r})")

# ── 4. nothing reported off nothing ───────────────────────────────────────
check(batch_runner._shape_of(batch_runner.BatchJob(source="x")) == "",
      "4. a case with no artifacts carries NO figures — not 'not published', "
      "which is a statement about a mesh that exists")
check(batch_runner._shape_of(
          batch_runner.BatchJob(source="x", artifacts={"vtk": ""})) == "",
      "4. ...and neither does one whose vtk artifact is empty")
_runner_src = open(_SRC["pipeline_runner"], encoding="utf-8").read()
_guard = _runner_src.find("mesh generation produced no VTK")
_report = _runner_src.find("cell shape — {mesh_shape_stats.shape_report")
# Both anchors are exact spellings, so say which one went missing rather than
# reporting a reworded line as an ordering defect: a gate whose failure message
# misnames the problem costs the next reader the time the gate was meant to save.
_missing = [n for n, i in (("the no-VTK guard", _guard), ("the report", _report))
            if i < 0]
check(not _missing and _guard < _report,
      f"4. the runner's report sits BELOW the refusal for a stage that produced no "
      f"VTK, so there is no path on which it describes a mesh that was never "
      f"written (guard@{_guard}, report@{_report}"
      + (f"; NOT FOUND: {', '.join(_missing)} — re-anchor this check" if _missing
         else "") + ")")

# ── 5/6. the real binary, both generation paths, both hosts ───────────────
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from app.views.batch_dialog import (  # noqa: E402
    BatchDialog, _NO_SHAPE, _SHAPE_COL,
)

# 6 first, on a fixture: a queued case has produced no mesh and must not show a
# blank in a column of numbers. Runs with or without a build.
dlg = BatchDialog()
dlg.jobs = [batch_runner.BatchJob(source="queued.json", name="queued"),
            batch_runner.BatchJob(source="done.json", name="done",
                                  status="ok", shape=r_measured)]
dlg._refresh()
check(dlg.table.item(0, _SHAPE_COL).text() == _NO_SHAPE,
      f"6. a case with no mesh shows a dash, not an empty cell "
      f"({dlg.table.item(0, _SHAPE_COL).text()!r})")
_tip = (dlg.table.item(0, _SHAPE_COL).toolTip() or "").lower()
check("no figures for this run" in _tip and "status" in _tip
      and "no mesh from this case" not in _tip,
      f"6. ...and says why on hover, WITHOUT denying the mesh — a case that "
      f"meshed and then failed later shows the same dash, and its mesh exists "
      f"({dlg.table.item(0, _SHAPE_COL).toolTip()!r})")
check(dlg.table.item(1, _SHAPE_COL).text() == r_measured,
      f"6. a finished case shows the report VERBATIM — the view reformats nothing "
      f"({dlg.table.item(1, _SHAPE_COL).text()!r})")

# ── 7. the panel and the report do not drift ──────────────────────────────
# Two formatters render the same `ShapeSummary` — `format_shape_report` as one
# line for the headless hosts, `mesh_stats_panel._apply_shape_summary` as four
# rows — and nothing made them agree. Not merged, because a line and a row layout
# are different renderings; pinned instead, so a precision or a wording change on
# either side has to be a deliberate change to both.
from app.views.panels.mesh_stats_panel import MeshStatsPanel  # noqa: E402

_panel = MeshStatsPanel()
_summary = mesh_shape_stats.ShapeSummary("tri_edge_ratio", 11396, 1.584671,
                                         9.901041, 35.608279)
_panel._apply_shape_summary(_summary)
_line = mesh_shape_stats.format_shape_report(_summary)
_rows = [_panel.shape_median_label.text(), _panel.shape_p95_label.text(),
         _panel.shape_max_label.text()]
check(all(r in _line for r in _rows),
      f"7. every figure the panel shows appears in the headless report, to the "
      f"same precision ({_rows} vs {_line!r})")
check(_panel.shape_metric_label.text().startswith("tri_edge_ratio")
      and _line.startswith("tri_edge_ratio"),
      f"7. ...under the same metric name in both "
      f"({_panel.shape_metric_label.text()!r} vs {_line!r})")
_panel._apply_shape_summary(
    mesh_shape_stats.ShapeSummary("quad_midline_ratio", 0, -1.0, -1.0, -1.0))
check("not measured" in _panel.shape_metric_label.text() and "not measured" in r_un,
      f"7. and an unmeasured run reads the same way on both surfaces "
      f"({_panel.shape_metric_label.text()!r} vs {r_un!r})")

# ── 8. the SPLIT reaches both headless hosts, through the same one line ───
# The producers (#143/#144) publish `layer` and `bulk` beside the whole-mesh set;
# #145 is the reader half, and its whole claim is that NEITHER host changed —
# `pipeline_runner` and `batch_runner` still make one `shape_report` call each and
# the split arrives in the string they already print. Section 5 below proves that
# against the real binary; this proves what the string is.
split_q = {"metric": "tri_edge_ratio", "cells": 11396, "median": 1.584671,
           "p95": 9.901041, "max": 35.608279,
           "layer": {"cells": 3215, "median": 35.281749, "p95": 70.541670,
                     "max": 78.703074},
           "bulk": {"cells": 12018, "median": 1.112154, "p95": 1.411765,
                    "max": 11.901852}}
r_split = mesh_shape_stats.shape_report(_sidecar("split", split_q))
check(r_split.startswith(r_measured),
      f"8. THE OLD LINE IS A PREFIX OF THE NEW ONE — every token the report "
      f"carried before #145 is still in it, in the same order and at the same "
      f"precision, so a log a user greps is not broken by the split arriving "
      f"({r_split!r})")
check("layer median 35.282, p95 70.542, max 78.703 (3215 cells)" in r_split
      and "bulk median 1.112, p95 1.412, max 11.902 (12018 cells)" in r_split,
      f"8. ...and both halves follow it, named and at that same precision "
      f"({r_split!r})")
check(r_split.index("layer") < r_split.index("bulk"),
      "8. ...layer first, as the sidecar and both banners order them")

# THE OLD-SIDECAR CASE, which is this ticket's acceptance: `measured` is the same
# fixture section 1 built, with no split in it, and its report must be what it
# always was — not a blank, not a crash, not a pair of dashes.
check("layer" not in r_measured and "bulk" not in r_measured,
      f"8. A SIDECAR WRITTEN BEFORE THIS WORK reports NO split clause at all — "
      f"the absence reads as absence ({r_measured!r})")
check(r_measured == ("tri_edge_ratio: median 1.585, p95 9.901, max 35.608 "
                     "(11396 cells)"),
      f"8. ...and its whole-mesh figures are the exact line it produced before "
      f"#145 ({r_measured!r})")

r_empty = mesh_shape_stats.shape_report(_sidecar("emptylayer", {
    "metric": "tri_edge_ratio", "cells": 900, "median": 1.1, "p95": 1.4,
    "max": 2.0,
    "layer": {"cells": 0, "median": -1.0, "p95": -1.0, "max": -1.0},
    "bulk": {"cells": 900, "median": 1.1, "p95": 1.4, "max": 2.0}}))
check("layer not measured" in r_empty and "0.000" not in r_empty
      and "-1" not in r_empty,
      f"8. a geometry meshed with NO boundary layer has an empty half, and it "
      f"says so — never 0.000, which on a metric whose floor is 1.0 reads as "
      f"perfection ({r_empty!r})")
check("bulk median 1.100" in r_empty,
      f"8. ...while the half that WAS measured reports its figures ({r_empty!r})")
check(len({r_measured, r_split, r_empty, r_un, r_bare}) == 5,
      "8. the split states are distinct from the three that predate them — five "
      "facts, five strings, none of them another's blank")

# ── 9. ONE rendering of a HALF, shared with the panel ─────────────────────
# Check 7 pins the panel's whole-mesh rows against this line by comparing their
# text. The halves are held harder than that: the panel's two rows ARE
# `format_figures`' output, and this line is built from the same call, so there
# is no second place where a half's precision or wording is decided.
_split_summary = mesh_shape_stats.read_shape_summary(_sidecar("split2", split_q))
for _tag, _half in (("layer", _split_summary.layer), ("bulk", _split_summary.bulk)):
    check(mesh_shape_stats.format_figures(_half) in r_split,
          f"9. the report's {_tag} clause is `format_figures` verbatim "
          f"({mesh_shape_stats.format_figures(_half)!r})")
_fmt_src = ast.parse(open(os.path.join(_GUI, "app", "views", "panels",
                                       "mesh_stats_panel.py"),
                          encoding="utf-8").read())
_panel_fmt = [n.func.attr for n in ast.walk(_fmt_src)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and isinstance(n.func.value, ast.Name)
              and n.func.value.id == "mesh_shape_stats"]
check(_panel_fmt.count("format_figures") == 2,
      f"9. and the PANEL renders its two half rows through that same function, "
      f"once each — not a second set of f-strings that could round differently "
      f"({_panel_fmt})")

if not _BINS_READY:
    print(f"SKIP  5 and 6's real-binary leg need the compiled binaries "
          f"({[b for b in _BINS if not os.path.exists(b)]}) — run ./build.sh",
          flush=True)
else:
    def _retarget(shipped: str, case: str) -> str:
        """The shipped demo script, renamed and writing into TMP. Read, never composed.

        The ticket's demo IS these two files, so a gate that rebuilt equivalents
        would leave an edit to either invisible here.
        """
        d = json.load(open(os.path.join(_REPO, "config", "pipeline", shipped),
                           encoding="utf-8"))
        d["name"] = case
        d.setdefault("solver", {})["skip"] = True
        out = os.path.join(TMP, case, f"mesh_{case}.vtk")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        d.setdefault("mesh", {})["output_filename"] = out
        path = os.path.join(TMP, case + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        return path

    scripts = [_retarget("naca_demo.json", "shape_host_hybrid"),
               _retarget("multiblock_cgrid_demo.json", "shape_host_mb")]
    jobs = batch_runner.load_jobs(scripts)
    lines = []
    batch_runner.run_batch(jobs, log=lambda m: lines.extend(str(m).splitlines()),
                           run_solver=False, run_ib=False)
    check([j.status for j in jobs] == ["ok", "ok"],
          f"5. both shipped demo cases ran ({[(j.label, j.status, j.error) for j in jobs]})")

    # Split the batch log into per-case blocks, so a line is attributed to the
    # case it came from rather than to whichever one happens to match.
    blocks, cur = {}, None
    for line in lines:
        if line.startswith("--- [") and line.endswith("---"):
            cur = line.strip("- ").split("] ", 1)[-1].strip()
            blocks[cur] = []
        elif cur is not None:
            blocks[cur].append(line)

    want = {"shape_host_hybrid": "tri_edge_ratio",
            "shape_host_mb": "quad_midline_ratio"}
    for job in jobs:
        block = blocks.get(job.label, [])
        reported = [ln.split("cell shape — ", 1)[1] for ln in block
                    if "[Mesh] cell shape — " in ln]
        check(len(reported) == 1,
              f"5. {job.label}: the mesh stage reported cell shape exactly once "
              f"({len(reported)} lines)")
        check(job.shape and reported and reported[0] == job.shape,
              f"5. {job.label}: the queue's row and the runner's log line are the "
              f"SAME string for the same mesh "
              f"(row={job.shape!r}, log={reported[0] if reported else None!r})")
        check(want[job.label] in job.shape,
              f"5. {job.label}: reported under its own path's metric name, "
              f"{want[job.label]} ({job.shape})")
        # ...and both are the sidecar's, not a recomputation: rebuild the expected
        # string from the JSON the run itself wrote.
        vtk = job.artifacts.get("vtk", "")
        side = mesh_shape_stats.sidecar_for(vtk)
        raw = json.load(open(side, encoding="utf-8"))["mesh"]["quality"] if side else {}
        check(bool(raw) and all(
            f"{raw[k]:.3f}" in job.shape for k in ("median", "p95", "max")),
              f"5. {job.label}: the figures are the ones that run PUBLISHED "
              f"({raw}) -> {job.shape!r}")
        # ...and so are BOTH HALVES (#145). Against the real writer, not a
        # fixture: this is where `include/Provenance.hpp` and the reader are
        # shown to still agree about where the split lives and what it is called,
        # on BOTH generation paths, in the string the two hosts actually print.
        check(all(k in raw for k in ("layer", "bulk")),
              f"5. {job.label}: that run published the split too "
              f"({sorted(raw)})")
        for _half in ("layer", "bulk"):
            _h = raw.get(_half) or {}
            check(bool(_h) and (
                f"{_half} median {_h['median']:.3f}, p95 {_h['p95']:.3f}, "
                f"max {_h['max']:.3f} ({_h['cells']} cells)") in job.shape,
                  f"5. {job.label}: the row carries that run's own {_half} "
                  f"figures ({_h}) -> {job.shape!r}")

    check(len({j.shape.split(":")[0] for j in jobs}) == 2,
          f"5. the two generation paths report under DIFFERENT metric names, so "
          f"neither can be read against the other "
          f"({[j.shape.split(':')[0] for j in jobs]})")

    # 6, against the real run: the rows carry what the batch produced, and a
    # re-run that fails before meshing must not leave them standing.
    dlg2 = BatchDialog()
    dlg2.jobs = jobs
    dlg2._refresh()
    check([dlg2.table.item(r, _SHAPE_COL).text() for r in range(len(jobs))]
          == [j.shape for j in jobs],
          "6. the queue's rows show each case's own figures after a real batch")
    _ctrl = ast.parse(open(os.path.join(_GUI, "app", "controllers",
                                        "batch_ctrl.py"), encoding="utf-8").read())
    _cleared = [n for n in ast.walk(_ctrl)
                if isinstance(n, ast.Assign)
                and isinstance(n.value, ast.Constant) and n.value.value == ""
                and any(isinstance(t, ast.Attribute) and t.attr == "shape"
                        and isinstance(t.value, ast.Name) and t.value.id == "job"
                        for t in n.targets)]
    check(len(_cleared) == 1,
          f"6. the re-run reset clears job.shape, so a FAILED row cannot stand "
          f"beside the figures of a mesh this run never made ({len(_cleared)} "
          f"assignments found)")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
