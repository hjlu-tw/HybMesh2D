#!/usr/bin/env python3
"""The analytic-edge form's one real rule, exercised without Qt.

`_sync_active_curve_segment_from_ui` read twelve sidebar widgets and assigned
them onto a SegmentModel, with the polygon node-count rule buried among the
assignments — so the rule needed a QApplication, a sidebar AND a live session to
run at all.

The rule: a polygon distributed "By Spacing" derives its node count from its own
PERIMETER, so density follows edge length instead of a fixed count that means
something different on every shape. Two things about it are easy to break and
are pinned here:

* **Order.** The perimeter is measured from the shape parameters, so those must
  land BEFORE the count is derived. Applying the spec to a segment carrying a
  stale polygon would otherwise size the new shape from the old one.
* **`spacing` is kept in By-Spacing mode and DROPPED otherwise**, because the
  backend consumes `n_points`; a leftover `spacing` key would put the segment
  back into By-Spacing mode on the next round-trip.

Also pinned: apply_to writes only the fields the form authors. The form covers a
subset of an edge, so a whole-model write is the hazard PRESERVED_FIELDS
documents for the stage panels.

Run:  python3 tools/PreProcessor/tests/test_curve_edit_spec.py
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "gui"))

from app.models.curve_edit_spec import (  # noqa: E402
    CURVE_TYPES, CurveEditSpec, curve_type_for_index, polygon_perimeter)

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


class _Seg:
    """Only what the form authors, so an unexpected write shows up as an error."""

    def __init__(self, **kw):
        self.type = "curve"
        self.curve_type = "custom"
        self.curve_mode = "parametric"
        self.x_formula = self.y_formula = self.formula = ""
        self.t_min, self.t_max = 0.0, 1.0
        self.start_index = self.end_index = -1
        self.parameters = {}
        self.__dict__.update(kw)


# Importing the rules must not require Qt — that is what moving them out of
# the controller bought. shape_spec (needed to parse a polygon's vertices)
# reaches app.utils, which imports PyQt6 at module level, so curve_edit_spec
# defers that import into the one function that needs it.
check("0. importing the spec does not pull Qt in", "PyQt6" not in sys.modules)

# ── 1. the combo row order is one list, owned by the model ────────────────
check("1. nine curve types, arc last", len(CURVE_TYPES) == 9
      and CURVE_TYPES[8] == "arc" and CURVE_TYPES[0] == "custom")
check("1. an unknown row is a custom formula, not an IndexError",
      curve_type_for_index(99) == "custom" and curve_type_for_index(-1) == "custom")

# ── 2. perimeter includes the closing edge ───────────────────────────────
unit_square = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
check("2. the unit square's perimeter is 4 (the closing edge counts)",
      abs(polygon_perimeter(unit_square) - 4.0) < 1e-12)
check("2. fewer than two vertices has no perimeter",
      polygon_perimeter([(0.0, 0.0)]) == 0.0 and polygon_perimeter([]) == 0.0)

# ── 3. By Spacing derives the node count from the perimeter ──────────────
poly = CurveEditSpec(curve_type="polygon", n_points=7, by_spacing=True,
                     spacing=0.25,
                     shape_params={"vertices_str": "0,0; 1,0; 1,1; 0,1"})
seg = _Seg()
poly.apply_to(seg)
check("3. a 4-perimeter polygon at Δs=0.25 gets 16 nodes, not the form's 7",
      seg.parameters["n_points"] == 16)
check("3. spacing is kept for round-trip", seg.parameters["spacing"] == 0.25)

# The order is the point: the count must come from the NEW vertices.
stale = _Seg(parameters={"vertices_str": "0,0; 10,0; 10,10; 0,10", "n_points": 3})
poly.apply_to(stale)
check("3. the count is derived from the incoming shape, not the stale one",
      stale.parameters["n_points"] == 16)

# ── 4. any other mode leaves the node count alone and drops spacing ──────
by_count = CurveEditSpec(curve_type="polygon", n_points=7, by_spacing=False,
                         shape_params={"vertices_str": "0,0; 1,0; 1,1; 0,1"})
seg = _Seg(parameters={"spacing": 0.25})
by_count.apply_to(seg)
check("4. By Node Count keeps the form's count", seg.parameters["n_points"] == 7)
check("4. ...and drops a leftover spacing, which would flip the mode back",
      "spacing" not in seg.parameters)

# A non-polygon never takes the rule, even with by_spacing set.
circle = CurveEditSpec(curve_type="circle", n_points=40, by_spacing=True,
                       spacing=0.25, shape_params={"cx": 0.0, "cy": 0.0, "r": 1.0})
seg = _Seg()
circle.apply_to(seg)
check("4. a non-polygon ignores the spacing rule",
      seg.parameters["n_points"] == 40 and "spacing" not in seg.parameters)

# ── 5. a degenerate polygon does not produce a zero or negative count ────
# Coincident vertices, not an unparseable string: polygon_vertices falls back
# to a default shape when the text does not parse, so an invalid string never
# reaches the rule at all.
degenerate = CurveEditSpec(curve_type="polygon", n_points=9, by_spacing=True,
                           spacing=0.25,
                           shape_params={"vertices_str": "1,1; 1,1; 1,1"})
seg = _Seg()
degenerate.apply_to(seg)
check("5. a polygon with no perimeter keeps the form's count",
      seg.parameters["n_points"] == 9)
huge = CurveEditSpec(curve_type="polygon", n_points=9, by_spacing=True,
                     spacing=1e9,
                     shape_params={"vertices_str": "0,0; 1,0; 1,1; 0,1"})
seg = _Seg()
huge.apply_to(seg)
check("5. a spacing larger than the shape still leaves at least 2 nodes",
      seg.parameters["n_points"] == 2)

# ── 6. the scalar fields are transcribed, and nothing else is touched ────
spec = CurveEditSpec(curve_type="arc", parametric=False, x_formula="cos(t)",
                     y_formula="sin(t)", formula="x**2", t_min=-1.0, t_max=2.0,
                     n_points=33, start_index=4, end_index=9,
                     shape_params={"r": 2.0})
seg = _Seg(parameters={"keep_me": "untouched"})
seg.strategy = "tanh"
spec.apply_to(seg)
check("6. explicit mode is written as 'explicit'", seg.curve_mode == "explicit")
check("6. every scalar the form owns is transcribed",
      (seg.curve_type, seg.x_formula, seg.y_formula, seg.formula,
       seg.t_min, seg.t_max, seg.start_index, seg.end_index)
      == ("arc", "cos(t)", "sin(t)", "x**2", -1.0, 2.0, 4, 9))
check("6. shape params are merged in", seg.parameters["r"] == 2.0)
check("6. a parameter the form does not author survives",
      seg.parameters["keep_me"] == "untouched")
check("6. a segment field the form does not author survives",
      seg.strategy == "tanh")

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All curve-edit-spec checks passed.")
