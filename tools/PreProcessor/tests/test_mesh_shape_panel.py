#!/usr/bin/env python3
"""The Mesh Statistics panel QUOTES the mesher's shape figures (issue #131, parent #128).

Before this, the same mesh could be described by two implementations with two
definitions: the mesher measured cell shape and printed median / p95 / max, while
the GUI computed its own per-cell aspect ratio and showed min / max / mean. This
gate holds the half that makes the mesher the single OWNER — the panel reads
`mesh.quality` out of the `.provenance.json` sidecar and displays it, and shows a
BLANK when there is no sidecar rather than a number computed under the other
definition.

What this pins down:

  1. The reader parses the sidecar's `mesh.quality` object as the mesher writes
     it — metric, cell count and the three figures.
  2. IT FINDS THE SIDECAR THROUGH THE EXISTING LOOKUP. Both spellings
     `case_sources.mesh_provenance_paths` produces are accepted, and the module
     really calls that function rather than spelling a second convention.
  3. NO SUMMARY IS NO NUMBERS: no sidecar, an unreadable one, one with no
     `quality` object, and one whose `metric` is empty all come back as None.
  4. "Looked and could not measure" is its OWN answer: the mesher writes
     `cells: 0` with NEGATIVE figures there, and that must never reach a user as
     0.000 — which on this metric would read as a perfect mesh.
  5. The panel displays the sidecar's numbers, to the precision it shows, with
     the metric NAMED beside them (the two paths measure different quantities).
  6. THE HONEST BLANK, MEASURED AGAINST A NEGATIVE CONTROL: the same mesh with
     its sidecar removed shows `—`, while its client-side per-cell array is
     non-empty and would have produced numbers. That is the accepted regression,
     visible rather than papered over.
  7. NOTHING IN THE PANEL COMPUTES THE SUMMARY. Statically: no panel module
     touches `get_element_aspect_ratios`, and the reader imports no mesh model —
     a fallback computation would be the second implementation coming back.
  8. THE COLOUR MAP IS UNTOUCHED, in both cases. Quality (Aspect Ratio) shading
     is rebuilt from the per-cell array, with and without a sidecar, and produces
     the same fills — the per-cell arrays were demoted to a rendering input, not
     taken away.
  9. Skewness is untouched by this ticket: its client-side min / max / mean rows
     still populate.
 10. AGAINST THE REAL BINARY (skipped without a build): a shipped MESH_MODE 1
     case is run, and the panel fed the mesh it produced displays that run's own
     sidecar figures. This is what a hand-written fixture cannot prove — that the
     reader and `include/Provenance.hpp`'s writer still agree about the schema.

Run:  python3 tools/PreProcessor/tests/test_mesh_shape_panel.py
Check 10 skips cleanly if ./build/HybMesh2D has not been built.
"""
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
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >300s", flush=True)
    os._exit(99)


_wd = threading.Timer(300, _watchdog)
_wd.daemon = True
_wd.start()

from app.services import mesh_shape_stats  # noqa: E402

TMP = tempfile.mkdtemp(prefix="hybmesh_shape_panel_")

# A mesh with real cells, so the "no sidecar" checks below have something a
# client-side computation COULD have answered with. Two triangles of a unit
# square: their edge ratio is sqrt(2), which is nothing like the figures the
# fixture sidecar carries, so a fallback computation could not pass by accident.
VTK = """# vtk DataFile Version 3.0
fixture
ASCII
DATASET UNSTRUCTURED_GRID
POINTS 4 float
0.0 0.0 0.0
1.0 0.0 0.0
1.0 1.0 0.0
0.0 1.0 0.0
CELLS 2 8
3 0 1 2
3 0 2 3
CELL_TYPES 2
5
5
"""


def sidecar_text(quality_json):
    """A provenance sidecar in the mesher's own shape (include/Provenance.hpp)."""
    q = "" if quality_json is None else ", \"quality\": %s" % quality_json
    return ("{\n"
            "  \"tool\": \"HybMesh2D\",\n"
            "  \"version\": \"1.0\",\n"
            "  \"git_sha\": \"deadbee\",\n"
            "  \"timestamp_utc\": \"2026-09-17T00:00:00Z\",\n"
            "  \"gmsh_version\": \"unknown\",\n"
            "  \"mesh\": { \"nodes\": 4, \"elements\": 2%s },\n"
            "  \"inputs\": [\n  ],\n"
            "  \"config\": \"\"\n"
            "}\n" % q)


MEASURED = ('{ "metric": "tri_edge_ratio", "cells": 11396, "median": 1.584671, '
            '"p95": 9.901041, "max": 35.608279 }')
UNMEASURED = ('{ "metric": "tri_edge_ratio", "cells": 0, "median": -1.000000, '
              '"p95": -1.000000, "max": -1.000000 }')


def case(name, quality_json, stem_named=True, sidecar=True, raw=None):
    """A `<name>.vtk` in its own directory, with the sidecar asked for."""
    d = os.path.join(TMP, name)
    os.makedirs(d, exist_ok=True)
    vtk = os.path.join(d, name + ".vtk")
    with open(vtk, "w", encoding="utf-8") as fh:
        fh.write(VTK)
    if sidecar:
        side = os.path.join(d, name + (".provenance.json" if stem_named
                                       else ".vtk.provenance.json"))
        with open(side, "w", encoding="utf-8") as fh:
            fh.write(raw if raw is not None else sidecar_text(quality_json))
    return vtk


# ── 1. the reader parses what the mesher writes ───────────────────────────
mesh_measured = case("measured", MEASURED)
s = mesh_shape_stats.read_shape_summary(mesh_measured)
check(s is not None and s.metric == "tri_edge_ratio" and s.cells == 11396,
      "1. the sidecar's metric and cell count are read back")
check(s is not None and (s.median, s.p95, s.max) == (1.584671, 9.901041, 35.608279),
      "1. ...and its three figures, unrounded")
check(s is not None and s.measured, "1. ...and it reports itself measured")

# ── 2. found through the EXISTING provenance lookup ───────────────────────
mesh_pathnamed = case("pathnamed", MEASURED, stem_named=False)
check(mesh_shape_stats.read_shape_summary(mesh_pathnamed) is not None,
      "2. the `<mesh>.vtk.provenance.json` spelling is found too")
from app.services import case_sources  # noqa: E402
check(mesh_shape_stats.sidecar_for(mesh_measured)
      in case_sources.mesh_provenance_paths(mesh_measured),
      "2. the sidecar it uses is one mesh_provenance_paths names")
_src_path = os.path.join(_GUI, "app", "services", "mesh_shape_stats.py")
_src = open(_src_path, encoding="utf-8").read()


def _code_strings(text):
    """Every string literal in a module that is NOT a docstring.

    Docstrings are excluded because this module's own prose quotes the sidecar's
    name, and a check that could not tell prose from code would have to be
    written against a comment-free file to stay true.
    """
    import ast
    tree = ast.parse(text)
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docs.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs]


_composed = [t for t in _code_strings(_src) if "provenance" in t]
check("mesh_provenance_paths" in _src and not _composed,
      f"2. the module calls that lookup rather than composing the name itself "
      f"({_composed or 'no sidecar name is spelled in its code'})")

# ── 3. no summary is no numbers ───────────────────────────────────────────
check(mesh_shape_stats.read_shape_summary(case("nosidecar", None, sidecar=False))
      is None, "3. a mesh with NO sidecar reads as None")
check(mesh_shape_stats.read_shape_summary(case("noquality", None)) is None,
      "3. a sidecar with no `quality` object reads as None")
check(mesh_shape_stats.read_shape_summary(
          case("broken", None, raw="{not json at all")) is None,
      "3. a malformed sidecar reads as None rather than raising")
check(mesh_shape_stats.read_shape_summary(
          case("nometric", '{ "metric": "", "cells": 3, "median": 1.0, '
                           '"p95": 1.0, "max": 1.0 }')) is None,
      "3. an EMPTY metric reads as None — an unnamed quantity is not comparable")
check(mesh_shape_stats.read_shape_summary("") is None,
      "3. no mesh path at all reads as None")

# ── 4. looked and could not measure ───────────────────────────────────────
mesh_unmeasured = case("unmeasured", UNMEASURED)
u = mesh_shape_stats.read_shape_summary(mesh_unmeasured)
check(u is not None and not u.measured,
      "4. `cells: 0` with negative figures is a summary, and reports NOT measured")
check(u is not None and u.median < 0.0 and u.p95 < 0.0 and u.max < 0.0,
      "4. ...and the figures stay negative, never 0.0")

# ── the panel, headless ───────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
from app.models.vtk_mesh import VTKMesh  # noqa: E402
from app.views.panels.mesh_stats_panel import MeshStatsPanel  # noqa: E402

panel = MeshStatsPanel()
mesh = VTKMesh.from_file(mesh_measured)

# ── 5. the panel displays the sidecar's figures ───────────────────────────
panel.update_stats(mesh, mesh_measured)
check(panel.shape_median_label.text() == "1.585"
      and panel.shape_p95_label.text() == "9.901"
      and panel.shape_max_label.text() == "35.608",
      "5. median / p95 / max are the sidecar's, to the precision shown")
check("tri_edge_ratio" in panel.shape_metric_label.text()
      and "11396" in panel.shape_metric_label.text(),
      f"5. the metric and its cell count are named ({panel.shape_metric_label.text()})")

# ── 9. skewness untouched ─────────────────────────────────────────────────
check(panel.sk_min_label.text() not in ("—", "computing…")
      and panel.sk_max_label.text() not in ("—", "computing…"),
      f"9. the skewness rows still populate ({panel.sk_min_label.text()} / "
      f"{panel.sk_max_label.text()})")

# ── 6. the honest blank, against a negative control ───────────────────────
mesh_blank_path = case("blank", None, sidecar=False)
mesh_blank = VTKMesh.from_file(mesh_blank_path)
ratios = mesh_blank.get_element_aspect_ratios()
check(len(ratios) == 2 and float(ratios.max()) > 1.4,
      f"6. the negative control HAS computable per-cell shape ({len(ratios)} cells, "
      f"max {float(ratios.max()):.3f}) — a fallback would have had numbers to show")
panel.update_stats(mesh_blank, mesh_blank_path)
check(panel.shape_median_label.text() == "—"
      and panel.shape_p95_label.text() == "—"
      and panel.shape_max_label.text() == "—"
      and panel.shape_metric_label.text() == "—",
      "6. a mesh with no sidecar shows a BLANK, not a number of its own")

# ...and the "could not measure" sidecar says so rather than showing 0.000.
panel.update_stats(VTKMesh.from_file(mesh_unmeasured), mesh_unmeasured)
check(panel.shape_median_label.text() == "not measured"
      and panel.shape_max_label.text() == "not measured",
      "4. the panel prints `not measured` for it, never 0.000")
check("not measured" in panel.shape_metric_label.text(),
      "4. ...and the metric row says so too")

# A cleared panel blanks them rather than leaving the last mesh's numbers.
panel.update_stats(mesh, mesh_measured)
panel.update_stats(None)
check(panel.shape_metric_label.text() == "—"
      and panel.shape_median_label.text() == "—",
      "6. clearing the panel blanks the shape rows")

# ── 7. nothing in the panel computes the summary ──────────────────────────
_panels_dir = os.path.join(_GUI, "app", "views", "panels")
_offenders = []
for fn in sorted(os.listdir(_panels_dir)):
    if not fn.endswith(".py"):
        continue
    with open(os.path.join(_panels_dir, fn), encoding="utf-8") as fh:
        if "get_element_aspect_ratios" in fh.read():
            _offenders.append(fn)
check(not _offenders,
      f"7. no panel module computes per-cell aspect ratio ({_offenders or 'none'})")
check("vtk_mesh" not in _src and "numpy" not in _src,
      "7. the reader imports no mesh model and no array library — it reads, it "
      "does not measure")

# ── 8. the colour map is untouched, with and without a sidecar ────────────
from app.controller import AppController  # noqa: E402

ctl = AppController()
mcv = ctl.main_window.mesh_canvas_view
fills = {}
for tag, path in (("with sidecar", mesh_measured), ("without", mesh_blank_path)):
    mcv.render_mesh(VTKMesh.from_file(path))
    mcv.set_color_mode("quality_aspect")
    fills[tag] = len(mcv.filled_items)
check(fills["with sidecar"] > 0 and fills["without"] > 0,
      f"8. Quality (Aspect Ratio) shading still builds fills in both cases ({fills})")
check(fills["with sidecar"] == fills["without"],
      "8. ...identically — the sidecar is a summary source, not a rendering input")
_modes = []
panel.color_mode_changed.connect(lambda m: _modes.append(m))
panel.color_mode_combo.setCurrentText("Quality (Aspect Ratio)")
check(_modes and _modes[-1] == "quality_aspect",
      f"8. the panel still offers the mode and emits it ({_modes})")

# ── 10. against the real binary ───────────────────────────────────────────
if not os.path.exists(_BIN):
    print(f"SKIP 10. {_BIN} not built — real-binary leg skipped", flush=True)
else:
    from mb_shipped_config import shipped_config  # noqa: E402
    from mesher_bin import mesher_env  # noqa: E402

    run_dir = os.path.join(TMP, "ogrid")
    os.makedirs(run_dir, exist_ok=True)
    stem = os.path.join(run_dir, "mesh_ogrid")
    conf = os.path.join(run_dir, "ogrid.dat")
    with open(conf, "w", encoding="utf-8") as fh:
        fh.write(shipped_config("multiblock_ogrid").replace("@STEM@", stem))
    p = subprocess.run([_BIN, "-conf", conf], cwd=run_dir, env=mesher_env(),
                       capture_output=True, text=True, timeout=900)
    produced = stem + ".vtk"
    check(p.returncode == 0 and os.path.exists(produced),
          f"10. the shipped O-grid meshed (rc={p.returncode})")
    if os.path.exists(produced):
        live = mesh_shape_stats.read_shape_summary(produced)
        raw = json.load(open(stem + ".provenance.json", encoding="utf-8"))
        want = raw["mesh"]["quality"]
        check(live is not None and live.metric == want["metric"]
              and live.cells == want["cells"],
              "10. the reader agrees with the sidecar this run actually wrote")
        panel.update_stats(VTKMesh.from_file(produced), produced)
        check(panel.shape_median_label.text() == f"{want['median']:.3f}"
              and panel.shape_p95_label.text() == f"{want['p95']:.3f}"
              and panel.shape_max_label.text() == f"{want['max']:.3f}",
              f"10. the panel displays that run's own figures "
              f"({panel.shape_median_label.text()} / {panel.shape_p95_label.text()} "
              f"/ {panel.shape_max_label.text()})")
        check(want["metric"] == "quad_midline_ratio"
              and panel.shape_metric_label.text().startswith("quad_midline_ratio"),
              "10. ...under MESH_MODE 1's own metric name, not the hybrid path's")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
