"""Single source of truth for analytic-shape geometry.

Before this module the per-curve-type mapping (which handle / widget / drawn
point maps to which defining parameter) was hand-written in six places — the
sidebar editor, the modal ``ShapeParamDialog``, and four methods of the curve
controller — plus the defaults were duplicated in two of them. Adding a shape
type meant editing all of them, and any one missed branch produced a shape that
previewed but could not be dragged (or dragged but did not sync its widgets).

Everything geometric lives here now, keyed by ``curve_type``:

* ``DEFAULTS`` / ``FIELDS`` — clean defaults and dialog field layout.
* ``SIDEBAR_ATTRS`` — sidebar widget attribute name per parameter key.
* ``control_points`` — defining parameters → draggable control points.
* ``apply_drag`` — a dragged control point → mutated parameters.
* ``params_from_points`` — points drawn with a tool → (parameters, curve_type).
* ``read_widget_params`` / ``write_widget_params`` — sidebar widgets ↔ params.

The module is pure (no Qt import); the widget helpers are duck-typed so any
object exposing the named widgets works.
"""
from __future__ import annotations
import math


# Per-type clean defaults, applied on a type switch so the shared shape widgets
# never carry a stale value (e.g. a long vertices_str left from a polygon).
DEFAULTS: dict[str, dict] = {
    "horizontal_line": {"y": 0.0, "x0": 0.0, "x1": 1.0},
    "vertical_line": {"x": 0.0, "y0": 0.0, "y1": 1.0},
    "line": {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
    "circle": {"cx": 0.0, "cy": 0.0, "r": 1.0},
    "triangle": {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 0.0, "x2": 0.5, "y2": 1.0},
    "quadrilateral": {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 0.0,
                      "x2": 1.0, "y2": 1.0, "x3": 0.0, "y3": 1.0},
    "polygon": {"vertices_str": "0,0; 1,0; 1,1; 0,1"},
}

# Numeric-field layout (param_key, label) for the modal dialog / sidebar.
# Polygon is excluded: it is edited as a single free-form vertices string.
FIELDS: dict[str, list[tuple[str, str]]] = {
    "line": [("x0", "X Start"), ("y0", "Y Start"),
             ("x1", "X End"), ("y1", "Y End")],
    "horizontal_line": [("y", "Y"), ("x0", "X Start"), ("x1", "X End")],
    "vertical_line": [("x", "X"), ("y0", "Y Start"), ("y1", "Y End")],
    "circle": [("cx", "Centre X"), ("cy", "Centre Y"), ("r", "Radius")],
    "triangle": [("x0", "P0 X"), ("y0", "P0 Y"), ("x1", "P1 X"),
                 ("y1", "P1 Y"), ("x2", "P2 X"), ("y2", "P2 Y")],
    "quadrilateral": [("x0", "P0 X"), ("y0", "P0 Y"), ("x1", "P1 X"),
                      ("y1", "P1 Y"), ("x2", "P2 X"), ("y2", "P2 Y"),
                      ("x3", "P3 X"), ("y3", "P3 Y")],
}

# Sidebar (edge-props panel) widget attribute name per parameter key.
# Polygon is excluded: it binds to a single QLineEdit (``poly_vertices``).
SIDEBAR_ATTRS: dict[str, dict[str, str]] = {
    "horizontal_line": {"y": "h_line_y", "x0": "h_line_x_start", "x1": "h_line_x_end"},
    "vertical_line": {"x": "v_line_x", "y0": "v_line_y_start", "y1": "v_line_y_end"},
    "line": {"x0": "line_x0", "y0": "line_y0", "x1": "line_x1", "y1": "line_y1"},
    "circle": {"cx": "circle_cx", "cy": "circle_cy", "r": "circle_r"},
    "triangle": {"x0": "tri_x0", "y0": "tri_y0", "x1": "tri_x1",
                 "y1": "tri_y1", "x2": "tri_x2", "y2": "tri_y2"},
    "quadrilateral": {"x0": "quad_x0", "y0": "quad_y0", "x1": "quad_x1",
                      "y1": "quad_y1", "x2": "quad_x2", "y2": "quad_y2",
                      "x3": "quad_x3", "y3": "quad_y3"},
}

POLYGON_VERTICES_ATTR = "poly_vertices"
POLYGON_DEFAULT = DEFAULTS["polygon"]["vertices_str"]

# Every shape-defining parameter key (cleared on a type switch before the new
# type's defaults are applied). Derived from DEFAULTS so it can never drift.
ALL_SHAPE_KEYS: set[str] = {k for d in DEFAULTS.values() for k in d}


def _verts(params: dict) -> list:
    """Parse a polygon's ``vertices_str`` into a list of (x, y)."""
    from app.services.geometry_service import _parse_vertices_str
    return list(_parse_vertices_str(params.get("vertices_str", POLYGON_DEFAULT)))


def control_points(curve_type: str, params: dict) -> list:
    """Return ``[(handle_id, (x, y)), ...]`` control points for ``curve_type``,
    from its raw defining parameters (no anchoring/transform). ``custom`` (or
    any unknown type) has no draggable control points → ``[]``."""
    p = params
    if curve_type == "line":
        return [("p0", (p.get("x0", 0.0), p.get("y0", 0.0))),
                ("p1", (p.get("x1", 1.0), p.get("y1", 1.0)))]
    if curve_type == "horizontal_line":
        y = p.get("y", 0.0)
        return [("p0", (p.get("x0", 0.0), y)), ("p1", (p.get("x1", 1.0), y))]
    if curve_type == "vertical_line":
        x = p.get("x", 0.0)
        return [("p0", (x, p.get("y0", 0.0))), ("p1", (x, p.get("y1", 1.0)))]
    if curve_type == "circle":
        cx, cy, r = p.get("cx", 0.0), p.get("cy", 0.0), p.get("r", 1.0)
        return [("c", (cx, cy)), ("rim", (cx + r, cy))]
    if curve_type == "triangle":
        return [(f"v{i}", (p.get(f"x{i}", 0.0), p.get(f"y{i}", 0.0)))
                for i in range(3)]
    if curve_type == "quadrilateral":
        return [(f"v{i}", (p.get(f"x{i}", 0.0), p.get(f"y{i}", 0.0)))
                for i in range(4)]
    if curve_type == "polygon":
        return [(f"v{i}", (float(vx), float(vy)))
                for i, (vx, vy) in enumerate(_verts(p))]
    return []


def apply_drag(curve_type: str, params: dict, handle_id: str, x: float, y: float):
    """Mutate ``params`` in place from a dragged control point."""
    p = params
    if curve_type == "line":
        if handle_id == "p0":
            p["x0"], p["y0"] = x, y
        else:
            p["x1"], p["y1"] = x, y
    elif curve_type == "horizontal_line":
        p["y"] = y
        p["x0" if handle_id == "p0" else "x1"] = x
    elif curve_type == "vertical_line":
        p["x"] = x
        p["y0" if handle_id == "p0" else "y1"] = y
    elif curve_type == "circle":
        if handle_id == "c":
            p["cx"], p["cy"] = x, y
        else:
            p["r"] = max(1e-6, math.hypot(x - p.get("cx", 0.0),
                                          y - p.get("cy", 0.0)))
    elif curve_type in ("triangle", "quadrilateral"):
        i = int(handle_id[1])
        p[f"x{i}"], p[f"y{i}"] = x, y
    elif curve_type == "polygon":
        i = int(handle_id[1:])
        verts = [list(v) for v in _verts(p)]
        if 0 <= i < len(verts):
            verts[i] = [x, y]
            p["vertices_str"] = "; ".join(f"{a:.6g},{b:.6g}" for a, b in verts)


def params_from_points(tool: str, pts: list):
    """Map the points drawn with a creation ``tool`` → (parameters, curve_type).
    Returns ``(None, None)`` when there are too few points. Note ``rectangle``
    is a drawing tool that produces a ``quadrilateral``."""
    p = [(float(x), float(y)) for x, y in pts]
    if tool == "line" and len(p) >= 2:
        return ({"x0": p[0][0], "y0": p[0][1],
                 "x1": p[1][0], "y1": p[1][1]}, "line")
    if tool == "circle" and len(p) >= 2:
        cx, cy = p[0]
        r = math.hypot(p[1][0] - cx, p[1][1] - cy)
        return ({"cx": cx, "cy": cy, "r": (r if r > 1e-9 else 1.0)}, "circle")
    if tool == "rectangle" and len(p) >= 2:
        (x0, y0), (x1, y1) = p[0], p[1]
        return ({"x0": x0, "y0": y0, "x1": x1, "y1": y0,
                 "x2": x1, "y2": y1, "x3": x0, "y3": y1}, "quadrilateral")
    if tool == "triangle" and len(p) >= 3:
        return ({"x0": p[0][0], "y0": p[0][1],
                 "x1": p[1][0], "y1": p[1][1],
                 "x2": p[2][0], "y2": p[2][1]}, "triangle")
    if tool == "polygon" and len(p) >= 3:
        v = "; ".join(f"{x:.6g},{y:.6g}" for x, y in p)
        return ({"vertices_str": v}, "polygon")
    return None, None


def read_widget_params(owner, curve_type: str) -> dict:
    """Read the sidebar shape widgets for ``curve_type`` into a params dict.
    ``owner`` is the object exposing the widgets. Unknown types → ``{}``."""
    if curve_type == "polygon":
        return {"vertices_str": getattr(owner, POLYGON_VERTICES_ATTR).text()}
    attrs = SIDEBAR_ATTRS.get(curve_type, {})
    return {key: getattr(owner, attr).value() for key, attr in attrs.items()}


def write_widget_params(owner, curve_type: str, params: dict, silent: bool = False):
    """Push ``params`` into the sidebar shape widgets for ``curve_type``,
    falling back to ``DEFAULTS`` for missing keys. When ``silent`` the widgets'
    signals are blocked so the write does not trigger live-preview re-entrancy.
    Unknown types write nothing."""
    if curve_type == "polygon":
        w = getattr(owner, POLYGON_VERTICES_ATTR)
        if silent:
            w.blockSignals(True)
        w.setText(params.get("vertices_str", POLYGON_DEFAULT))
        if silent:
            w.blockSignals(False)
        return
    defaults = DEFAULTS.get(curve_type, {})
    for key, attr in SIDEBAR_ATTRS.get(curve_type, {}).items():
        w = getattr(owner, attr)
        if silent:
            w.blockSignals(True)
        w.setValue(params.get(key, defaults.get(key, 0.0)))
        if silent:
            w.blockSignals(False)
