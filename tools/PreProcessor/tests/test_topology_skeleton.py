#!/usr/bin/env python3
"""The block skeleton on the canvas, and the node count on every edge (issue #136).

Two halves, and the first is what the ticket is actually about. Drawing an outline
is easy and says little; what a user cannot predict is the NODE COUNT, because a
count in a topology document is a SEED. Opposite sides of a block carry equal counts
and a shared edge is one edge two blocks name, so four declarations decide twelve
edges on the shipped H-grid. So the checks here are mostly about the number beside
each line, and only then about the line.

THE PROPAGATION IS A SECOND HOME FOR THE MESHER'S OWN RULE, and this file is what
makes that affordable rather than a drift waiting to happen:

  * check 2 reads the side PAIRING out of `src/MultiBlock.cpp` and out of
    `services/topology_skeleton.py`, and compares them. It FAILS rather than skips
    when it cannot find either — a check that cannot see its subject must not report
    success about it.
  * check 8 runs the REAL mesher and compares its own `Point counts` banner row —
    how many it declared, how many it propagated, and every propagated edge by name
    and value — against what this module resolved from the same document. That is
    the authority, not a restatement of it.

The GUI half is headless against panel and canvas state, in the style of
`test_topology_panel.py` next door.

INJECTIONS: twelve, run 2026-09-23 over a mutated copy of the shipped sources, each
restored BY CONTENT from a snapshot rather than by `git checkout` (#131's lesson, and
two of the three files were new). All twelve bit. Recorded as MEASURED:

  A. `resolve_counts` unions ADJACENT sides ((0,1),(2,3)) instead of opposite ones
     -> 8 red: 2b, 3, 3c, 4b, 4c, 4d and 12c on BOTH documents. 12b stayed GREEN,
     which is the measurement worth keeping: mis-partitioning the classes does not
     change HOW MANY counts were declared, so the split half of the mesher
     cross-check cannot see it and only the edge-by-edge half can.
  B. no propagation at all — each edge keeps its own declaration -> 6 red: 3, 3c, 4,
     4b, 12c twice. 12b green again, for the same reason.
  C. a conflicting class picks one of its two seeds instead of resolving to None ->
     4b alone. Exactly one check for exactly one behaviour, which is what 4b's
     negative control next door is there to make trustworthy.
  D. the canvas never rebuilds the skeleton -> 13 red (7 through 7g, 10, 10b, 10c,
     11c). **Its first run CRASHED instead**, with `AttributeError: 'NoneType' has
     no attribute 'edges'` at check 7 and TWO FAIL lines printed — a mutation that
     removes the whole feature, scoring almost nothing to a reader counting FAIL
     lines. The exit code was right and the report was not, so the three places this
     file dereferenced `topology_skeleton` were changed to TEST it; the 13 above are
     the re-run. This file is not the first in the repo to hit that shape.
  E. the rebuild moves INSIDE `update_mesh_config`'s `if self.mesh_config:` branch
     -> 7e alone, and only its third instance (`there is no config at all`). The
     mode and family clears still work, which is why 7e is three cases and not one.
  F. the mode combo is not wired to `_on_topology_edited` -> 10d alone.
  G. `_on_topology_edited` refreshes the read-out and emits nothing -> 10b, 10c,
     10d. Check 10 stays GREEN: a programmatic push goes through `set_config`, which
     ends with its own emit, so "the overlay appears" cannot see this at all.
  H. bound and free corners drawn with the same symbol -> 8 alone.
  I. an unplaceable bound corner placed at the origin -> 5b alone.
  J. an unresolved count labelled blank instead of `?` -> 4d alone.
  K. declared and propagated counts share one colour -> 7f alone.
  L. `auto_range` loses the skeleton as a source -> 11c alone. 11b stays green, as
     it must: it is the negative control for exactly this source.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_SHIPPED = os.path.join(_REPO, "examples", "topology", "hgrid_blocks.json")
_MULTIBLOCK_CPP = os.path.join(_REPO, "src", "MultiBlock.cpp")
_SKEL_PY = os.path.join(_GUI, "app", "services", "topology_skeleton.py")
_MIXIN_PY = os.path.join(_GUI, "app", "views", "mesh_canvas_skeleton_mixin.py")
sys.path.insert(0, _HERE)
sys.path.insert(0, _GUI)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from mesher_bin import NO_SMOOTH, mesher_env  # noqa: E402

from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.models.mesh_config import MeshConfig  # noqa: E402
from app.services import topology_hgrid, topology_skeleton  # noqa: E402
from app.services.mesh_modes import (  # noqa: E402
    MESH_MODE_HYBRID, MESH_MODE_MULTIBLOCK,
)
from app.services.topology_model import TopologyModel, build_document  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def read_doc(path):
    """A shipped topology document. Its `//` comments are the mesher's own
    extension, so `json` cannot read one without them stripped."""
    raw = open(path, encoding="utf-8").read()
    return json.loads(re.sub(r"(?m)^\s*//.*$", "", raw))


def model(**kw):
    m = TopologyModel(family=topology_hgrid.FAMILY)
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def cfg_for(mode=MESH_MODE_MULTIBLOCK, family=topology_hgrid.FAMILY, **kw):
    c = MeshConfig()
    c.mesh_mode = mode
    c.topology.family = family
    for k, v in kw.items():
        setattr(c.topology, k, v)
    return c


# ── 1. every declared corner and edge is drawn, and placed ────────────────
doc = build_document(model(hgrid_nx=3, hgrid_ny=2))
skel = topology_skeleton.skeleton(doc)
check(f"1. the skeleton carries one entry per declared corner and edge "
      f"({len(skel.corners)} corners, {len(skel.edges)} edges for "
      f"{len(doc['corners'])}/{len(doc['edges'])} declared)",
      len(skel.corners) == len(doc["corners"])
      and len(skel.edges) == len(doc["edges"]))
check("1b. ...and every one of them has a position to draw at, so the outline is "
      "the whole declaration and not the part that happened to resolve",
      all(c.xy is not None for c in skel.corners)
      and all(e.xy is not None for e in skel.edges))
check(f"1c. ...and the extent it reports is the domain the parameters asked for "
      f"({skel.bounds()})", skel.bounds() == (0.0, 2.0, 0.0, 1.0))

# ── 2. the propagation rule is the MESHER's, not a lookalike ──────────────
# `resolveEdgeCounts` unions a block's OPPOSITE sides, and a block declares its
# edges [south, east, north, west] — so the pairs are (0, 2) and (1, 3). Both
# spellings are read rather than asserted, because the claim is that they AGREE
# and a hardcoded expectation here would agree with neither.
_cpp = open(_MULTIBLOCK_CPP, encoding="utf-8").read()
_py = open(_SKEL_PY, encoding="utf-8").read()
_m_cpp = re.search(r"pairs\[2\]\[2\]\s*=\s*\{\{\s*(\d)\s*,\s*(\d)\s*\}\s*,"
                   r"\s*\{\s*(\d)\s*,\s*(\d)\s*\}\s*\}", _cpp)
_m_py = re.search(r"for a, b in \(\(\s*(\d)\s*,\s*(\d)\s*\)\s*,"
                  r"\s*\(\s*(\d)\s*,\s*(\d)\s*\)\s*\)", _py)
check("2. the side-pairing literal is findable in BOTH src/MultiBlock.cpp and "
      "services/topology_skeleton.py — a check that cannot see its subject must "
      "fail, not report success about it "
      f"(cpp={bool(_m_cpp)}, py={bool(_m_py)})",
      _m_cpp is not None and _m_py is not None)
if _m_cpp and _m_py:
    c_pairs = {frozenset((int(_m_cpp.group(1)), int(_m_cpp.group(2)))),
               frozenset((int(_m_cpp.group(3)), int(_m_cpp.group(4))))}
    p_pairs = {frozenset((int(_m_py.group(1)), int(_m_py.group(2)))),
               frozenset((int(_m_py.group(3)), int(_m_py.group(4))))}
    check(f"2b. ...and they are the same two pairs of block sides "
          f"(mesher {sorted(sorted(p) for p in c_pairs)}, "
          f"GUI {sorted(sorted(p) for p in p_pairs)})", c_pairs == p_pairs)

# ── 3. a count PROPAGATES, and says which of the two it is ────────────────
# The shipped four-block H-grid is the ticket's own demo: unequal counts per
# direction, four declared, eight nobody wrote down.
shipped = read_doc(_SHIPPED)
res = topology_skeleton.resolve_counts(shipped)
declared = sorted(k for k, (_, d) in res.items() if d)
propagated = {k: v for k, (v, d) in res.items() if not d}
check(f"3. every edge of the shipped H-grid resolves to a count, including the "
      f"eight nobody declared ({propagated})",
      len(res) == len(shipped["edges"])
      and all(v is not None for v, _ in res.values()))
check(f"3b. ...and declared is kept apart from propagated, which is the question "
      f"a surprising number sends the user to ({declared})",
      declared == ["h00", "h10", "v00", "v01"] and len(propagated) == 8)
check("3c. ...and a propagated count is the SEED of its class, not a default: "
      "the two column classes carry 7 and 5, the two row classes 4 and 6",
      propagated["h01"] == 7 and propagated["h02"] == 7
      and propagated["h11"] == 5 and propagated["h12"] == 5
      and propagated["v10"] == 4 and propagated["v20"] == 4
      and propagated["v11"] == 6 and propagated["v21"] == 6)

# ── 4. what the mesher REFUSES resolves to no number, never to a guess ────
# Two blocks sharing one line, the same layout the C++ gate uses: 'w' seeds the
# j count of both blocks through the shared edge 'm'.
def two_blocks(w_count=3, ee_count=None):
    edges = [
        {"id": "s0", "corners": ["a", "b"], "kind": "wall", "count": 3},
        {"id": "s1", "corners": ["b", "c"], "kind": "wall", "count": 3},
        {"id": "w", "corners": ["a", "d"], "kind": "wall"},
        {"id": "m", "corners": ["b", "e"], "kind": "interface"},
        {"id": "ee", "corners": ["c", "f"], "kind": "wall"},
        {"id": "n0", "corners": ["d", "e"], "kind": "wall"},
        {"id": "n1", "corners": ["e", "f"], "kind": "wall"},
    ]
    if w_count:
        edges[2]["count"] = w_count
    if ee_count:
        edges[4]["count"] = ee_count
    return {"format_version": 1,
            "corners": [{"id": i, "kind": "free", "xy": xy} for i, xy in
                        (("a", [0, 0]), ("b", [1, 0]), ("c", [2, 0]),
                         ("d", [0, 1]), ("e", [1, 1]), ("f", [2, 1]))],
            "edges": edges,
            "blocks": [{"id": "b0", "edges": ["s0", "m", "n0", "w"]},
                       {"id": "b1", "edges": ["s1", "ee", "n1", "m"]}]}


ok = topology_skeleton.resolve_counts(two_blocks())
check(f"4. NEGATIVE CONTROL: one seed two blocks away resolves the whole chain "
      f"(w=3 -> m={ok['m'][0]}, ee={ok['ee'][0]})",
      ok["m"][0] == 3 and ok["ee"][0] == 3 and ok["w"][1] is True)
conflict = topology_skeleton.resolve_counts(two_blocks(w_count=3, ee_count=9))
check(f"4b. two seeds that disagree resolve to NO number, because that is a "
      f"document the mesher refuses — drawing one of the two would label a mesh "
      f"no run will produce ({conflict['m']})",
      conflict["m"][0] is None and conflict["ee"][0] is None
      and conflict["w"][0] is None)
noseed = topology_skeleton.resolve_counts(two_blocks(w_count=None))
check(f"4c. ...and so does a class with no seed at all, the other refusal "
      f"({noseed['w']}, {noseed['m']})",
      noseed["w"][0] is None and noseed["m"][0] is None
      and noseed["s0"][0] == 3)
_unresolved = topology_skeleton.skeleton(two_blocks(w_count=None))
check("4d. ...and the overlay SAYS so rather than going blank: an unresolved "
      "count labels '?', which is the one state that stops the run",
      {e.label for e in _unresolved.edges if e.id in ("w", "m")} == {"?"}
      and {e.label for e in _unresolved.edges if e.id == "s0"} == {"3"})

# ── 5. a bound corner is a different thing from a free one ────────────────
# No shipped family declares one yet — that arrives with the O-grid (#137) — so
# the fixture is a document of the shape the mesher already accepts, which is the
# shipped cavity case's.
bound_doc = {
    "format_version": 1,
    "corners": [
        {"id": "sw", "kind": "on_geometry", "geom": "g.dat", "seg": 0, "t": 0.0},
        {"id": "se", "kind": "on_geometry", "geom": "g.dat", "seg": 1, "t": 0.0},
        {"id": "ne", "kind": "free", "xy": [1.0, 1.0]},
        {"id": "nw", "kind": "free", "xy": [0.0, 1.0]},
    ],
    "edges": [
        {"id": "s", "corners": ["sw", "se"], "kind": "wall", "count": 5},
        {"id": "e", "corners": ["se", "ne"], "kind": "wall", "count": 4},
        {"id": "n", "corners": ["nw", "ne"], "kind": "wall"},
        {"id": "w", "corners": ["sw", "nw"], "kind": "wall"},
    ],
    "blocks": [{"id": "b", "edges": ["s", "e", "n", "w"]}],
}
b = topology_skeleton.skeleton(bound_doc)
by_id = {c.id: c for c in b.corners}
check(f"5. a corner of kind on_geometry is reported as BOUND and a free one is "
      f"not ({ {k: v.bound for k, v in by_id.items()} })",
      by_id["sw"].bound and by_id["se"].bound
      and not by_id["ne"].bound and not by_id["nw"].bound)
check("5b. ...and with nothing to resolve an arc length, a bound corner has NO "
      "position rather than one at the origin — an invented coordinate draws a "
      "topology the user did not declare",
      by_id["sw"].xy is None
      and next(e for e in b.edges if e.id == "s").xy is None
      and next(e for e in b.edges if e.id == "n").xy is not None)
placed = topology_skeleton.skeleton(
    bound_doc, locate=lambda c: (float(c["seg"]), -1.0))
check("5c. ...and a caller that CAN place one (the O-grid's binding resolution, "
      "#137) gets it placed, still marked bound",
      {c.id: c.xy for c in placed.corners}["sw"] == (0.0, -1.0)
      and {c.id: c.bound for c in placed.corners}["sw"] is True
      and next(e for e in placed.edges if e.id == "s").xy is not None)

# ── 6. one owner decides whether there is a skeleton at all ───────────────
check("6. a config naming a family in the multi-block mode has a skeleton",
      topology_skeleton.skeleton_for_config(cfg_for()) is not None)
check("6b. ...one naming NO family has none, which is what clears the overlay on "
      "the way into a case with no topology model",
      topology_skeleton.skeleton_for_config(cfg_for(family="")) is None)
check("6c. ...and so does one whose mode is hybrid, where the whole template "
      "section is hidden and the document drives nothing",
      topology_skeleton.skeleton_for_config(
          cfg_for(mode=MESH_MODE_HYBRID)) is None)
check("6d. ...and None is not a crash", topology_skeleton.skeleton_for_config(None) is None)

# ── 7. the canvas draws exactly that, and clears it ───────────────────────
_app = QApplication.instance() or QApplication([])
from app.views.mesh_canvas import MeshCanvasView  # noqa: E402

canvas = MeshCanvasView()
canvas.update_mesh_config(cfg_for(hgrid_nx=3, hgrid_ny=2, hgrid_cell=0.3,
                                  hgrid_counts_x="4,9,6"))
labels = [t.toPlainText() for t in canvas.skeleton_label_items]
drawn = canvas.topology_skeleton
# `drawn` is tested rather than dereferenced: injection D (the canvas never
# rebuilding) left it None and this file CRASHED at the next line, scoring zero
# FAIL lines for a mutation that removes the whole feature. The bite was real and
# the exit code said so, but a gate that crashes is a gate that stops reporting.
_n_drawn = len(drawn.edges) if drawn is not None else -1
check(f"7. the overlay draws one label per declared edge ({len(labels)} labels "
      f"for {_n_drawn} edges): {sorted(set(labels))}",
      len(labels) == _n_drawn and len(labels) > 0)
_xc, _yc = topology_hgrid.hgrid_counts(
    model(hgrid_nx=3, hgrid_ny=2, hgrid_cell=0.3, hgrid_counts_x="4,9,6"))
check(f"7b. ...and every count the FAMILY derives is on the canvas, including the "
      f"ones the user overrode per column (family x={_xc} y={_yc})",
      all(str(v) in labels for v in _xc + _yc))
_propagated_on_canvas = [e.id for e in (drawn.edges if drawn else ()) if not e.declared]
check(f"7c. ...and most of those labels are on edges nobody declared a count "
      f"for — the whole point of showing them ({len(_propagated_on_canvas)} of "
      f"{_n_drawn})",
      len(_propagated_on_canvas) == _n_drawn - (len(_xc) + len(_yc)))
check("7d. ...drawn as line items with the corner marks beside them",
      len(canvas.skeleton_edge_items) >= 1 and "free" in canvas.skeleton_corner_marks)
_styles = {it.opts["pen"].style() for it in canvas.skeleton_edge_items}
check(f"7g. ...and a boundary edge is drawn differently from an interior one, which "
      f"this grid has both of ({len(canvas.skeleton_edge_items)} items, "
      f"{len(_styles)} pen styles)",
      len(canvas.skeleton_edge_items) == 2 and len(_styles) == 2)

for label, cfg in (("the mode goes back to hybrid", cfg_for(mode=MESH_MODE_HYBRID)),
                   ("the family is cleared", cfg_for(family="")),
                   ("there is no config at all", None)):
    canvas.update_mesh_config(cfg_for(hgrid_nx=2, hgrid_ny=2))
    before = len(canvas.skeleton_label_items)
    canvas.update_mesh_config(cfg)
    check(f"7e. the overlay clears when {label} (was {before} labels, now "
          f"{len(canvas.skeleton_label_items)})",
          before > 0 and not canvas.skeleton_label_items
          and not canvas.skeleton_edge_items
          and not canvas.skeleton_corner_marks
          and canvas.topology_skeleton is None)

# A declared count and a propagated one must be TELLABLE APART on the canvas, not
# only in the model: the mesher's own banner splits them for the same reason.
canvas.update_mesh_config(cfg_for(hgrid_nx=2, hgrid_ny=2))
# Zipped over the edges that GOT a label (one is created per placed midpoint), so
# the pairing is the drawing order and not an assumption that every edge got one.
_drawn = canvas.topology_skeleton
_labelled = [e for e in (_drawn.edges if _drawn else ()) if e.midpoint is not None]
_cols = {}
for _e, _t in zip(_labelled, canvas.skeleton_label_items):
    _cols.setdefault(_e.declared, set()).add(_t.color.name().lower())
check(f"7f. declared and propagated counts are drawn in different colours "
      f"({_cols})",
      len(_cols.get(True, set())) == 1 and len(_cols.get(False, set())) == 1
      and not (_cols[True] & _cols[False]))

canvas.update_topology_skeleton(topology_skeleton.skeleton(
    bound_doc, locate=lambda c: (float(c["seg"]), -1.0)))
_free = canvas.skeleton_corner_marks.get("free")
_bound = canvas.skeleton_corner_marks.get("bound")
check("8. a bound corner is drawn as its own item with its own symbol and pen, "
      "so it is not two dots that differ only in hue",
      _free is not None and _bound is not None
      and _free.opts["symbol"] != _bound.opts["symbol"]
      and _free.opts["pen"].color().name() != _bound.opts["pen"].color().name())

# ── 9. read-only, in the form that is checkable ───────────────────────────
# Over the PARSED module, not its text: the mixin's own header explains the rule
# by naming `movable=True`, and a substring scan read that prose as the defect it
# was written to rule out. A check that its own subject's documentation can fail
# is measuring the wrong thing.
import ast  # noqa: E402

_tree = ast.parse(open(_MIXIN_PY, encoding="utf-8").read())
_names = {n.id for n in ast.walk(_tree) if isinstance(n, ast.Name)}
_names |= {n.attr for n in ast.walk(_tree) if isinstance(n, ast.Attribute)}
_names |= {n.name for n in ast.walk(_tree) if isinstance(n, ast.FunctionDef)}
_kwargs = {k.arg for n in ast.walk(_tree) if isinstance(n, ast.Call)
           for k in n.keywords if k.arg}
_interactive = ({"TargetItem", "sigClicked", "sigPositionChanged",
                 "sigPositionChangeFinished", "mousePressEvent",
                 "mouseDragEvent", "mouseClickEvent"} & _names) | (
                    {"movable"} & _kwargs)
check(f"9. the overlay declares no drag handle and no click handler — dragging a "
      f"bound corner edits an arc length while dragging a free one moves a "
      f"coordinate, and v1 does neither (found: {sorted(_interactive)})",
      not _interactive)

# ── 10. through the REAL panel, a typed parameter reaches the canvas ──────
# The panel-only checks above cannot see this: `mesh_config_changed` fires for
# STRUCTURAL edits (the geometry list, a role, a BC) and not for a spin box, so a
# typed block count would leave the overlay showing the topology before it.
from app.controller import AppController  # noqa: E402

_c = AppController()
_panel = _c.main_window.mesh_config_panel
_canvas = _c.main_window.mesh_canvas_view
_c.push_panel_config(_panel, cfg_for(hgrid_nx=2, hgrid_ny=2, hgrid_cell=0.5))
_before = [t.toPlainText() for t in _canvas.skeleton_label_items]


def n_edges(c):
    """Edges on `c`'s skeleton, or -1 when there is none — see check 7."""
    return len(c.topology_skeleton.edges) if c.topology_skeleton is not None else -1


_n_before = n_edges(_canvas)
check(f"10. a programmatic push paints the skeleton on the app's own canvas "
      f"({_n_before} edges, labels {sorted(set(_before))})", _n_before == 12)
_panel.topo_hgrid_nx.setValue(4)
_after = [t.toPlainText() for t in _canvas.skeleton_label_items]
check(f"10b. ...and TYPING a block count redraws it, which no other mesh panel "
      f"field does today ({_n_before} edges -> "
      f"{n_edges(_canvas)})",
      n_edges(_canvas) == 22)
_panel.topo_hgrid_counts_x.setText("3,,9,")
_after_ov = [t.toPlainText() for t in _canvas.skeleton_label_items]
check(f"10c. ...and so does an override typed into a text row, at the position it "
      f"names ({sorted(set(_after_ov))})",
      "9" in _after_ov and _after_ov != _after)
_panel.mesh_mode.setCurrentIndex(MESH_MODE_HYBRID)
check("10d. ...and switching the mode back to hybrid clears it through the same "
      "route", not _canvas.skeleton_label_items)

# ── 11. the canvas in every OTHER mode is untouched ───────────────────────
_plain = MeshCanvasView()
_plain.update_mesh_config(MeshConfig())
check("11. a hybrid config leaves no skeleton item on the canvas at all",
      not _plain.skeleton_edge_items and not _plain.skeleton_label_items
      and not _plain.skeleton_corner_marks
      and _plain.skeleton_bounds() is None)
_plain._did_initial_fit = False
_plain.auto_range()
check("11b. ...and auto_range with nothing to fit to still moves nothing, so the "
      "third source it gained cannot fire on a case that has none",
      _plain._did_initial_fit is False)

# ...and the third source EARNS its place: an empty `cads` is legal in MESH_MODE 1, so
# this is a case with no mesh and no geometry preview whose skeleton is the only thing
# on the canvas with an extent. The domain box is turned off so that it cannot be what
# fitted the view — its default -10..10 brackets any skeleton and would pass this check
# for the wrong reason.
_far = MeshCanvasView()
_far.show_domain_box = False
_far.update_mesh_config(cfg_for(hgrid_nx=2, hgrid_ny=2, hgrid_x_min=5.0,
                                hgrid_x_max=7.0, hgrid_y_min=5.0, hgrid_y_max=6.0))
(_x0, _x1), (_y0, _y1) = _far.plot_widget.getViewBox().viewRange()
# Asserted on Y and on the CENTRE rather than on both spans: the plot widget locks
# its aspect, so whichever axis is taller wins and the other is stretched around the
# same centre — existing behaviour, and not this ticket's to change.
check(f"11c. a template case with NO geometry at all still fits the view to its "
      f"skeleton (x {_x0:.2f}..{_x1:.2f}, y {_y0:.2f}..{_y1:.2f} for a 5..7 by 5..6 "
      f"domain, where an unfitted view would be the default -10..10)",
      _far._did_initial_fit and _y0 < 5.0 and _y1 > 6.0 and _y1 < 6.5
      and abs(0.5 * (_x0 + _x1) - 6.0) < 0.1)

# ── 12. the MESHER agrees, on its own report ──────────────────────────────
# The authority, not a restatement of it. Self-skips without a build tree, the
# convention every binary-dependent gate here uses.
_BANNER = re.compile(r"Point counts\s*:\s*(\d+) declared, (\d+) propagated"
                     r"(?:\s*\(([^)]*)\))?")


def mesher_counts(topo_path, tmp):
    conf = os.path.join(tmp, "c.dat")
    with open(conf, "w", encoding="utf-8") as f:
        f.write(f"MESH_MODE 1\nMESH_TOPOLOGY_FILE {topo_path}\n"
                f"EXPORT_VTK 1\nBC_GEOM wall\n"
                f"OUTPUT_FILENAME {os.path.join(tmp, 'm.vtk')}\n" + NO_SMOOTH)
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=mesher_env(),
                       capture_output=True, text=True, timeout=300)
    m = _BANNER.search((p.stdout or "") + (p.stderr or ""))
    if m is None:
        return None
    named = dict(re.findall(r"'([^']+)'\s*=\s*(\d+)", m.group(3) or ""))
    return (int(m.group(1)), int(m.group(2)),
            {k: int(v) for k, v in named.items()})


if not os.path.exists(_BIN):
    print(f"SKIP 12. mesher not built ({_BIN}) — build it to compare the "
          f"propagation against its own report")
else:
    with tempfile.TemporaryDirectory() as tmp:
        for name, path in (
                ("the shipped four-block H-grid", _SHIPPED),
                ("a document this repo's own H-grid FAMILY produced",
                 os.path.join(tmp, "gen.json"))):
            if not os.path.exists(path):
                # The generated one, written here so the family path is compared
                # against the mesher too and not only the hand-written document.
                gen = build_document(model(hgrid_nx=3, hgrid_ny=2, hgrid_cell=0.3,
                                           hgrid_counts_x="4,9,6"))
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(gen, f)
            got = mesher_counts(path, tmp)
            mine = topology_skeleton.resolve_counts(read_doc(path))
            n_decl = sum(1 for _, d in mine.values() if d)
            n_prop = len(mine) - n_decl
            prop = {k: v for k, (v, d) in mine.items() if not d}
            check(f"12. the mesher's own banner is readable for {name} ({got})",
                  got is not None)
            if got is None:
                continue
            check(f"12b. ...and it declared/propagated the same split this module "
                  f"resolved (mesher {got[0]}/{got[1]}, GUI {n_decl}/{n_prop})",
                  (got[0], got[1]) == (n_decl, n_prop))
            check(f"12c. ...and every count it PROPAGATED matches, edge by edge "
                  f"({len(got[2])} named)", got[2] == prop)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.stdout.flush()
    os._exit(1)
print("All checks passed.")
sys.stdout.flush()
os._exit(0)
