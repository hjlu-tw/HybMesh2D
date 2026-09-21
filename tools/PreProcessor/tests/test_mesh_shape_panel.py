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
  7. NOTHING COMPUTES THE SUMMARY A SECOND TIME. Statically, over the WHOLE GUI
     package rather than over the panels directory: `get_element_aspect_ratios`
     has exactly two homes — the model that defines it and the colour map that is
     now its only consumer — and the reader imports no mesh model. A fallback
     computation is the second implementation coming back wherever it is written.
  8. THE COLOUR MAP IS UNTOUCHED, in both cases. The fixture puts one cell in
     each of the four quality buckets, and the shading is compared by BRUSH
     COLOUR with and without a sidecar — the per-cell arrays were demoted to a
     rendering input, not taken away.
  9. Skewness is untouched by this ticket: its client-side min / max / mean rows
     still populate.
 11. AN UNRECOGNISED METRIC still displays, under its own name, and KEEPS the
     tooltip explaining what these rows are — the one case that could otherwise
     reach a user with a number and no way to find out what it measures.
 10. AGAINST THE REAL BINARY (skipped without a build): a shipped MESH_MODE 1
     case is run, and the panel fed the mesh it produced displays that run's own
     sidecar figures. This is what a hand-written fixture cannot prove — that the
     reader and `include/Provenance.hpp`'s writer still agree about the schema.
 12. THE SPLIT IS READ, AND ITS ABSENCE IS NOT A DEFECT (#145). Both halves come
     back unrounded and unswapped; the whole-mesh four are untouched by their
     arrival; a sidecar written BEFORE #143/#144 reads as not-split and still
     yields exactly the same whole-mesh figures; half a split is no split; and a
     half that is PRESENT and empty is split-and-not-measured, which is a third
     state again.
 13. THE PANEL SHOWS THE SPLIT, in all three of those states — both halves
     through `format_figures`, the one rendering the headless hosts also use, so
     a precision or wording change cannot land on one surface only. An old
     sidecar's rows say `not split` while its whole-mesh rows are unchanged; an
     empty half says `not measured`, never 0.000; a cleared panel blanks them.
 14. THE SPLIT AGAINST THE REAL BINARY, inside check 10's run: the panel's two
     rows are that run's own published halves, and on the shipped O-grid the bulk
     p95 is below 3 while the whole-mesh p95 is above 20 — the split is proven to
     DO something rather than merely to exist.

Injections, RUN BY HAND on 2026-09-17 and dated here rather than claimed as
automated — the harness lived in a scratchpad and is not in the tree. Each was
scored by EXIT CODE first, because a mutation that crashes the gate prints zero
FAIL lines and would otherwise read as inert. Eleven, all of which bit — the last
four were added after a review round that found checks 7 and 8 weaker than their
own labels, and h's original form stopped compiling when the fix landed, which is
why it is stated in its CURRENT shape:

  a. the panel falls back to computing the summary when there is no sidecar
     -> red: 6 (the blank) and 7 (the static scan finds the call)
  b. the negative figures are formatted as numbers instead of `not measured`
     -> red: both 4s
  c. the reader composes `<stem>.provenance.json` itself instead of calling
     `mesh_provenance_paths` -> red: both 2s (the second spelling stops
     resolving, AND the AST scan finds the literal)
  d. the metric's name is dropped from the row -> red: 5 and the real-binary 10
  e. the figures are shown at a different precision -> red: 5 and 10
  f. the `quality_aspect` branch of the fills mixin is disabled -> red: 8
  g. `measured` returns True unconditionally -> red: three 4s
  h. the blank leaves the metric row showing the last mesh's metric -> red: both
     of 6's blanking checks
  i. the clear blanks the four labels in place instead of routing through
     `_apply_shape_summary(None)`, leaving the tooltip naming the cleared mesh's
     sidecar -> red: 6's tooltip check
  j. an unknown metric drops `SHAPE_METRIC_TIP` from the tooltip -> red: two 11s
  k. a second client-side computation appears OUTSIDE `views/panels/` -> red: 7
     (the check the first version of this file would have let through)

Five more for the SPLIT (#145), run by hand on 2026-09-21 in the same way, all of
which bit:

  l. `_figures` answers None for every half, so the split is never parsed
     -> red: both of 12's parse checks, three 13s and 14 (seven lines). The
     "through `format_figures`" check stays GREEN and correctly so — both sides
     agree that there is nothing to render, which is what that check compares.
  m. the panel writes its OWN f-string for a half, at `.2f` -> red: 13's exact
     text, 13's `format_figures` identity, 14 — and 13's empty-half check, which
     it reaches by rendering the sentinel as `median -1.00`. Four lines, and the
     fourth is the reason the empty half is checked on the panel and not only in
     the report.
  n. half a split is accepted as a split (`or` -> `and` in the collapse)
     -> red: 12's half-split check, and ONLY that.
  o. an ABSENT half is rendered as an EMPTY one (`not split` -> `not measured`)
     -> red: 13's old-sidecar row, and ONLY that. The two absences are one edit
     apart in the source and three states apart in meaning.
  p. the panel's two half rows are swapped -> red: four 13s and 14. A swap is the
     mutation a check written as "both rows are non-empty" would miss, which is
     why 13 asserts the exact text of each.

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
# client-side computation COULD have answered with — and one that lands a cell in
# EACH of the colour map's four aspect-ratio buckets (<=1.25, <=1.8, <=2.5, and
# above), so check 8's comparison is over four distinct fills rather than over one.
# The four measure 1.000, 1.414, 2.236 and 8.062 — one per bucket — and their
# longest/shortest edge ratios are nothing like the figures the fixture sidecar
# carries — a fallback computation could not pass any check here by accident.
VTK = """# vtk DataFile Version 3.0
fixture
ASCII
DATASET UNSTRUCTURED_GRID
POINTS 12 float
0.0 0.0 0.0
1.0 0.0 0.0
0.5 0.866 0.0
2.0 0.0 0.0
4.0 0.0 0.0
2.0 2.0 0.0
5.0 0.0 0.0
7.0 0.0 0.0
5.0 1.0 0.0
9.0 0.0 0.0
17.0 0.0 0.0
9.0 1.0 0.0
CELLS 4 16
3 0 1 2
3 3 4 5
3 6 7 8
3 9 10 11
CELL_TYPES 4
5
5
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


# The sidecar as it was written BEFORE #143/#144: the whole-mesh four and no
# split. This is the shape the ticket's acceptance is written around, and it is
# the DEFAULT fixture here on purpose — every check that predates #145 goes on
# running against the file it was written for.
MEASURED = ('{ "metric": "tri_edge_ratio", "cells": 11396, "median": 1.584671, '
            '"p95": 9.901041, "max": 35.608279 }')
UNMEASURED = ('{ "metric": "tri_edge_ratio", "cells": 0, "median": -1.000000, '
              '"p95": -1.000000, "max": -1.000000 }')
# ...and as a splitting path writes it (#145). The whole-mesh four are BYTE FOR
# BYTE those of MEASURED above, so a check comparing the two sidecars is reading
# the split and nothing else. The halves' figures are the shipped NACA case's own
# shape — a layer p95 of 70.5 against a bulk 1.4 — so a check that confused them
# could not pass by arithmetic accident.
SPLIT = ('{ "metric": "tri_edge_ratio", "cells": 11396, "median": 1.584671, '
         '"p95": 9.901041, "max": 35.608279, '
         '"layer": { "cells": 3215, "median": 35.281749, "p95": 70.541670, '
         '"max": 78.703074 }, '
         '"bulk": { "cells": 12018, "median": 1.112154, "p95": 1.411765, '
         '"max": 11.901852 } }')
# A geometry meshed with NO boundary layer: the path split, and one half is
# empty. An ordinary case, and the one that must never print 0.000.
SPLIT_EMPTY_LAYER = (
    '{ "metric": "tri_edge_ratio", "cells": 900, "median": 1.100000, '
    '"p95": 1.400000, "max": 2.000000, '
    '"layer": { "cells": 0, "median": -1.000000, "p95": -1.000000, '
    '"max": -1.000000 }, '
    '"bulk": { "cells": 900, "median": 1.100000, "p95": 1.400000, '
    '"max": 2.000000 } }')


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
from app.views.panels.mesh_stats_panel import (  # noqa: E402
    SHAPE_METRIC_TIP, MeshStatsPanel)

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
check(len(ratios) == 4 and float(ratios.max()) > 1.4,
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

# A cleared panel blanks them rather than leaving the last mesh's numbers —
# TOOLTIP INCLUDED. The rows and the tooltip are cleared by one verb because
# blanking the four labels in place left the metric row pointing at the previous
# mesh's sidecar path under a row reading "—".
panel.update_stats(mesh, mesh_measured)
_measured_tip = panel.shape_metric_label.toolTip()
panel.update_stats(None)
check(panel.shape_metric_label.text() == "—"
      and panel.shape_median_label.text() == "—",
      "6. clearing the panel blanks the shape rows")
_side = mesh_shape_stats.sidecar_for(mesh_measured)
check(_side and _side in _measured_tip
      and _side not in panel.shape_metric_label.toolTip(),
      "6. ...and drops the cleared mesh's SIDECAR path from the tooltip, which it "
      "really was carrying a moment before (the mesh path is not what the tooltip "
      "names, and asserting on that one would pass for the wrong reason)")

# ── 11. an UNKNOWN metric keeps the explanation ───────────────────────────
# A metric this GUI has no gloss for is the one case that can reach a user
# unannotated, so it is exactly where the base tooltip must survive.
mesh_unknown = case("unknown_metric",
                    '{ "metric": "some_future_ratio", "cells": 7, "median": 1.2, '
                    '"p95": 1.4, "max": 2.0 }')
panel.update_stats(VTKMesh.from_file(mesh_unknown), mesh_unknown)
check(panel.shape_metric_label.text().startswith("some_future_ratio")
      and panel.shape_median_label.text() == "1.200",
      "11. an unrecognised metric is still displayed, under its own name")
check(SHAPE_METRIC_TIP in panel.shape_metric_label.toolTip(),
      "11. ...and the tooltip still explains what these rows are")
panel.update_stats(mesh, mesh_measured)
check(SHAPE_METRIC_TIP in panel.shape_metric_label.toolTip()
      and mesh_shape_stats.METRIC_MEANING["tri_edge_ratio"]
      in panel.shape_metric_label.toolTip(),
      "11. a KNOWN metric carries both the gloss and the explanation")

# ── 12. the reader parses the SPLIT, and its absence is not a defect ──────
mesh_split = case("split", SPLIT)
sp = mesh_shape_stats.read_shape_summary(mesh_split)
check(sp is not None and sp.split
      and (sp.layer.cells, sp.layer.median, sp.layer.p95, sp.layer.max)
      == (3215, 35.281749, 70.541670, 78.703074)
      and (sp.bulk.cells, sp.bulk.median, sp.bulk.p95, sp.bulk.max)
      == (12018, 1.112154, 1.411765, 11.901852),
      "12. both halves are read back, unrounded and not swapped")
check(sp is not None
      and (sp.cells, sp.median, sp.p95, sp.max) == (11396, 1.584671, 9.901041,
                                                    35.608279),
      "12. ...and the WHOLE-MESH four are untouched by their arrival — the same "
      "numbers a reader that knows only #129's keys has always read")
_old = mesh_shape_stats.read_shape_summary(mesh_measured)
check(_old is not None and not _old.split
      and _old.layer is None and _old.bulk is None,
      "12. A SIDECAR WRITTEN BEFORE THIS WORK reads as NOT SPLIT — the two halves "
      "are absent, which is a different state from empty")
check(_old is not None
      and (_old.cells, _old.median, _old.p95, _old.max)
      == (sp.cells, sp.median, sp.p95, sp.max),
      "12. ...and still yields its figures, identical to the split sidecar's "
      "whole-mesh set — the acceptance this ticket is written around")
_half = mesh_shape_stats.read_shape_summary(case(
    "halfsplit",
    '{ "metric": "tri_edge_ratio", "cells": 10, "median": 1.0, "p95": 1.0, '
    '"max": 1.0, "layer": { "cells": 4, "median": 2.0, "p95": 2.0, "max": 2.0 } }'))
check(_half is not None and not _half.split and _half.layer is None,
      "12. HALF a split is no split — the writer emits the pair under one flag, "
      "and one band with nothing to compare it against is worse than none")
_empty = mesh_shape_stats.read_shape_summary(case("emptylayer", SPLIT_EMPTY_LAYER))
check(_empty is not None and _empty.split
      and not _empty.layer.measured and _empty.bulk.measured,
      "12. a PRESENT but empty half is split-and-not-measured, never absent — a "
      "geometry meshed with no boundary layer is an ordinary case here")

# ── 13. the panel shows the split, in its three states ────────────────────
panel.update_stats(VTKMesh.from_file(mesh_split), mesh_split)
check(panel.shape_layer_label.text()
      == "median 35.282, p95 70.542, max 78.703 (3215 cells)"
      and panel.shape_bulk_label.text()
      == "median 1.112, p95 1.412, max 11.902 (12018 cells)",
      f"13. both halves are displayed, at the precision the other rows use "
      f"({panel.shape_layer_label.text()!r} / {panel.shape_bulk_label.text()!r})")
check(panel.shape_median_label.text() == "1.585"
      and panel.shape_p95_label.text() == "9.901",
      "13. ...beside the whole-mesh rows, which still show the whole mesh")
# ONE formatter for a half, shared with the headless hosts: the rows are that
# function's output verbatim, so a precision or wording change cannot land on one
# surface only.
check(panel.shape_layer_label.text()
      == mesh_shape_stats.format_figures(sp.layer)
      and panel.shape_bulk_label.text()
      == mesh_shape_stats.format_figures(sp.bulk),
      "13. ...through `format_figures`, the same rendering the headless hosts "
      "put on their line — not a second set of f-strings in the panel")
check(mesh_shape_stats.LAYER_MEANING["tri_edge_ratio"]
      in panel.shape_layer_label.toolTip(),
      "13. the layer row's tooltip names what THIS path's layer is (the sidecar's "
      "key is neutral; the banner's word is not)")

panel.update_stats(VTKMesh.from_file(mesh_measured), mesh_measured)
check(panel.shape_layer_label.text() == "not split"
      and panel.shape_bulk_label.text() == "not split",
      f"13. AN OLD SIDECAR reads as `not split` on both rows — not a dash, which "
      f"is this panel's word for 'no figures at all', and not 0.000 "
      f"({panel.shape_layer_label.text()!r})")
check(panel.shape_median_label.text() == "1.585"
      and panel.shape_max_label.text() == "35.608"
      and panel.shape_metric_label.text().startswith("tri_edge_ratio"),
      "13. ...while its whole-mesh figures display exactly as they did before "
      "#145 — the state #128 bought and paid for")
check(mesh_shape_stats.LAYER_MEANING["tri_edge_ratio"]
      not in panel.shape_layer_label.toolTip(),
      "13. ...and nothing explains a wall band that this mesh never published")

mesh_empty_layer = case("emptylayer_panel", SPLIT_EMPTY_LAYER)
panel.update_stats(VTKMesh.from_file(mesh_empty_layer), mesh_empty_layer)
check(panel.shape_layer_label.text() == "not measured"
      and "0.000" not in panel.shape_layer_label.text()
      and "-1" not in panel.shape_layer_label.text(),
      f"13. an EMPTY layer says `not measured`, never 0.000 — the metric's floor "
      f"is 1.0 and a zero would read as perfection "
      f"({panel.shape_layer_label.text()!r})")
check(panel.shape_bulk_label.text().startswith("median 1.100"),
      f"13. ...while the half that WAS measured still shows its figures "
      f"({panel.shape_bulk_label.text()!r})")

panel.update_stats(None)
check(panel.shape_layer_label.text() == "—"
      and panel.shape_bulk_label.text() == "—",
      "13. clearing the panel blanks the split rows too — a dash here is 'no "
      "mesh', which is what a cleared panel means")

# ── 7. nothing computes the summary a second time ─────────────────────────
# An ALLOW-LIST over the whole GUI package, not a scan of the panels directory:
# the criterion is that no client-side fallback exists anywhere, and the first
# version of this check would have passed a fallback added in a controller, a
# service or a canvas mixin. Two files may name the per-cell array — the model
# that defines it, and the colour map that is now its only consumer. A third is
# the second implementation coming back, wherever it is written.
_ALLOWED_ASPECT_CALLERS = {
    "app/models/vtk_mesh.py",              # defines it
    "app/views/mesh_canvas_fills_mixin.py",  # the Quality (Aspect Ratio) colour map
}
_callers = set()
for dirpath, _dirs, files in os.walk(os.path.join(_GUI, "app")):
    for fn in files:
        if not fn.endswith(".py"):
            continue
        full = os.path.join(dirpath, fn)
        with open(full, encoding="utf-8") as fh:
            if "get_element_aspect_ratios" in fh.read():
                _callers.add(os.path.relpath(full, _GUI).replace(os.sep, "/"))
check(_callers == _ALLOWED_ASPECT_CALLERS,
      f"7. the per-cell aspect array has exactly its two allowed homes "
      f"(unexpected: {sorted(_callers - _ALLOWED_ASPECT_CALLERS) or 'none'}; "
      f"missing: {sorted(_ALLOWED_ASPECT_CALLERS - _callers) or 'none'})")
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
    # The BRUSH COLOURS, not the item count: the fixture puts one cell in each of
    # the four quality buckets, so this is a comparison of which cell was shaded
    # how. A count alone would have been 1 == 1 on a one-bucket mesh and could not
    # have shown anything about the shading at all.
    fills[tag] = sorted(it.brush().color().name() for it in mcv.filled_items)
check(len(fills["with sidecar"]) == 4 and len(set(fills["with sidecar"])) == 4,
      f"8. Quality (Aspect Ratio) shading still fills all four buckets "
      f"({fills['with sidecar']})")
check(fills["with sidecar"] == fills["without"],
      "8. ...and colours them identically with and without a sidecar — the sidecar "
      "is a summary source, not a rendering input")
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
        # 14: the SPLIT, against the writer rather than against a fixture. A
        # hand-written sidecar cannot show that `include/Provenance.hpp` and this
        # reader still agree about where the two halves live and what they are
        # called — which is the whole reason this leg runs the binary.
        check(set(want) >= {"layer", "bulk"},
              f"14. the run's own sidecar carries both halves ({sorted(want)})")
        if set(want) >= {"layer", "bulk"}:
            check(panel.shape_layer_label.text()
                  == (f"median {want['layer']['median']:.3f}, "
                      f"p95 {want['layer']['p95']:.3f}, "
                      f"max {want['layer']['max']:.3f} "
                      f"({want['layer']['cells']} cells)")
                  and panel.shape_bulk_label.text()
                  == (f"median {want['bulk']['median']:.3f}, "
                      f"p95 {want['bulk']['p95']:.3f}, "
                      f"max {want['bulk']['max']:.3f} "
                      f"({want['bulk']['cells']} cells)"),
                  f"14. ...and the panel displays THAT run's two halves "
                  f"({panel.shape_layer_label.text()!r} / "
                  f"{panel.shape_bulk_label.text()!r})")
            # The split is proven to DO something on the shipped case, not merely
            # to exist: #144's own surface gate asserts the same inequality on the
            # machine line, and this is the panel end of it.
            check(want["bulk"]["p95"] < 3.0 < 20.0 < want["p95"],
                  f"14. ...and on the shipped O-grid the bulk p95 ({want['bulk']['p95']:.3f}) "
                  f"is below 3 while the whole-mesh p95 ({want['p95']:.3f}) is above "
                  f"20 — the rows a user reads describe two different meshes")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
