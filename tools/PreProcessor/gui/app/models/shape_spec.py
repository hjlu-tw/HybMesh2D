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
from contextlib import nullcontext

from app.utils import block_signals


# Per-type clean defaults, applied on a type switch so the shared shape widgets
# never carry a stale value (e.g. a long vertices_str left from a polygon).
DEFAULTS: dict[str, dict] = {
    "horizontal_line": {"y": 0.0, "x0": 0.0, "x1": 1.0},
    "vertical_line": {"x": 0.0, "y0": 0.0, "y1": 1.0},
    "line": {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
    "circle": {"cx": 0.0, "cy": 0.0, "r": 1.0},
    "arc": {"cx": 0.0, "cy": 0.0, "r": 1.0, "theta0": 0.0, "theta1": math.pi / 2},
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
    "arc": [("cx", "Centre X"), ("cy", "Centre Y"), ("r", "Radius"),
            ("theta0", "Start angle"), ("theta1", "End angle")],
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
    "arc": {"cx": "arc_cx", "cy": "arc_cy", "r": "arc_r",
            "theta0": "arc_theta0", "theta1": "arc_theta1"},
    "triangle": {"x0": "tri_x0", "y0": "tri_y0", "x1": "tri_x1",
                 "y1": "tri_y1", "x2": "tri_x2", "y2": "tri_y2"},
    "quadrilateral": {"x0": "quad_x0", "y0": "quad_y0", "x1": "quad_x1",
                      "y1": "quad_y1", "x2": "quad_x2", "y2": "quad_y2",
                      "x3": "quad_x3", "y3": "quad_y3"},
}

POLYGON_VERTICES_ATTR = "poly_vertices"
POLYGON_DEFAULT = DEFAULTS["polygon"]["vertices_str"]

# Parameter keys that are ANGLES: stored internally in radians (the samplers and
# drag math need radians) but shown to the user in DEGREES. The widget helpers
# and the modal dialog convert at the UI boundary so storage never changes.
ANGLE_KEYS: dict[str, set[str]] = {"arc": {"theta0", "theta1"}}

# Every shape-defining parameter key (cleared on a type switch before the new
# type's defaults are applied). Derived from DEFAULTS so it can never drift.
ALL_SHAPE_KEYS: set[str] = {k for d in DEFAULTS.values() for k in d}


def _verts(params: dict) -> list:
    """Parse a polygon's ``vertices_str`` into a list of (x, y)."""
    from app.services.geometry_service import _parse_vertices_str
    return list(_parse_vertices_str(params.get("vertices_str", POLYGON_DEFAULT)))


def polygon_vertices(params: dict) -> list:
    """Public alias for :func:`_verts` — a polygon's vertices as (x, y) tuples."""
    return _verts(params)


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
    if curve_type == "arc":
        cx, cy, r = p.get("cx", 0.0), p.get("cy", 0.0), p.get("r", 1.0)
        t0, t1 = p.get("theta0", 0.0), p.get("theta1", math.pi / 2)
        # Radius handle angle: free, stored as a cosmetic ``theta_m`` grab-point.
        # Defaults to the sweep midpoint (backward compatible); once the user
        # drags it, its own angle is honoured instead of snapping back to mid.
        tm = p.get("theta_m", 0.5 * (t0 + t1))
        return [("c", (cx, cy)),
                ("p0", (cx + r * math.cos(t0), cy + r * math.sin(t0))),
                ("p1", (cx + r * math.cos(t1), cy + r * math.sin(t1))),
                ("m", (cx + r * math.cos(tm), cy + r * math.sin(tm)))]
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


def boundary_endpoints(curve_type: str, params: dict) -> list:
    """The 0–2 FREE endpoints of an OPEN curve as ``[(handle_id, (x, y)), ...]``
    — the points that may be welded onto an adjacent edge to form one connected
    boundary. Inherently-closed / centre-defined shapes (circle, triangle,
    quadrilateral, arc) return ``[]`` (their closure is not a weldable end).
    A polygon yields its first and last vertex; the caller skips it when the
    segment is flagged closed."""
    if curve_type in ("line", "horizontal_line", "vertical_line"):
        return control_points(curve_type, params)          # [p0, p1]
    if curve_type == "polygon":
        cps = control_points("polygon", params)
        return [cps[0], cps[-1]] if len(cps) >= 2 else []
    return []


def apply_drag(curve_type: str, params: dict, handle_id: str, x: float, y: float,
               lock_radius: bool = False):
    """Mutate ``params`` in place from a dragged control point.

    ``lock_radius`` (arc only): when True, dragging an end handle (``p0``/``p1``)
    changes only that end's angle and keeps the radius fixed; the ``m`` (mid)
    handle is the way to change the radius. When False an end handle re-fits both
    radius and angle (legacy behaviour)."""
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
    elif curve_type == "arc":
        cx, cy = p.get("cx", 0.0), p.get("cy", 0.0)
        if handle_id == "c":
            p["cx"], p["cy"] = x, y
        elif handle_id == "m":
            # Radius handle: change the radius (distance to the FIXED centre) AND
            # record its own angle, so it is no longer locked to the sweep
            # midpoint — the user can park it anywhere around the circle while it
            # still drives the radius. The centre never moves (use the c handle
            # for that) and the sweep is unchanged (use p0/p1 for that).
            p["r"] = max(1e-6, math.hypot(x - cx, y - cy))
            p["theta_m"] = math.atan2(y - cy, x - cx)
        else:                                    # p0 / p1 endpoints
            if not lock_radius:
                p["r"] = max(1e-6, math.hypot(x - cx, y - cy))
            p["theta0" if handle_id == "p0" else "theta1"] = math.atan2(y - cy, x - cx)
    elif curve_type in ("triangle", "quadrilateral"):
        i = int(handle_id[1])
        p[f"x{i}"], p[f"y{i}"] = x, y
    elif curve_type == "polygon":
        i = int(handle_id[1:])
        verts = [list(v) for v in _verts(p)]
        if 0 <= i < len(verts):
            verts[i] = [x, y]
            from app.services.geometry_service import format_vertices_str
            p["vertices_str"] = format_vertices_str(verts)


def arc_from_3points(p1, p2, p3):
    """Circle through 3 points → (cx, cy, r, theta0, theta1), with the sweep
    from p1 (start) to p2 (end) going the way that passes through p3 (a point on
    the arc). Returns None if the three points are collinear."""
    (ax, ay), (bx, by), (cxp, cyp) = p1, p2, p3
    d = 2.0 * (ax * (by - cyp) + bx * (cyp - ay) + cxp * (ay - by))
    if abs(d) < 1e-12:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cxp * cxp + cyp * cyp
    ux = (a2 * (by - cyp) + b2 * (cyp - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cxp - bx) + b2 * (ax - cxp) + c2 * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    t_s = math.atan2(ay - uy, ax - ux)
    t_m = math.atan2(cyp - uy, cxp - ux)
    t_e = math.atan2(by - uy, bx - ux)
    two_pi = 2.0 * math.pi
    d_e = (t_e - t_s) % two_pi
    d_m = (t_m - t_s) % two_pi
    theta1 = t_s + d_e if d_m <= d_e else t_s - (two_pi - d_e)
    return (ux, uy, r, t_s, theta1)


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
    if tool == "arc" and len(p) >= 3:
        # New click sequence: p0 = centre, p1 = radius/start-angle, p2 = end
        # angle. r is |p1-centre|; theta0 is the angle of p1 about the centre;
        # theta1 sweeps CCW from theta0 to the angle of p2 (so the swept angle
        # is 0..360°, matching the "CCW positive" convention).
        (cx, cy), (rx, ry), (ax, ay) = p[0], p[1], p[2]
        r = math.hypot(rx - cx, ry - cy)
        if r <= 1e-9:
            return None, None
        t0 = math.atan2(ry - cy, rx - cx)
        sweep = (math.atan2(ay - cy, ax - cx) - t0) % (2.0 * math.pi)
        return ({"cx": cx, "cy": cy, "r": r,
                 "theta0": t0, "theta1": t0 + sweep}, "arc")
    if tool == "rectangle" and len(p) >= 2:
        (x0, y0), (x1, y1) = p[0], p[1]
        return ({"x0": x0, "y0": y0, "x1": x1, "y1": y0,
                 "x2": x1, "y2": y1, "x3": x0, "y3": y1}, "quadrilateral")
    if tool == "triangle" and len(p) >= 3:
        return ({"x0": p[0][0], "y0": p[0][1],
                 "x1": p[1][0], "y1": p[1][1],
                 "x2": p[2][0], "y2": p[2][1]}, "triangle")
    if tool == "polygon" and len(p) >= 3:
        from app.services.geometry_service import format_vertices_str
        return ({"vertices_str": format_vertices_str(p)}, "polygon")
    if tool == "polyline" and len(p) >= 2:
        # An open polyline is a polygon with closed=False (set by the caller);
        # only two points are needed. The renderer skips the closing seam.
        from app.services.geometry_service import format_vertices_str
        return ({"vertices_str": format_vertices_str(p)}, "polygon")
    return None, None


def read_widget_params(owner, curve_type: str) -> dict:
    """Read the sidebar shape widgets for ``curve_type`` into a params dict.
    ``owner`` is the object exposing the widgets. Unknown types → ``{}``."""
    if curve_type == "polygon":
        return {"vertices_str": getattr(owner, POLYGON_VERTICES_ATTR).text()}
    attrs = SIDEBAR_ATTRS.get(curve_type, {})
    angle_keys = ANGLE_KEYS.get(curve_type, ())
    out: dict = {}
    for key, attr in attrs.items():
        v = getattr(owner, attr).value()
        out[key] = math.radians(v) if key in angle_keys else v   # widget °→rad
    return out


def write_widget_params(owner, curve_type: str, params: dict, silent: bool = False):
    """Push ``params`` into the sidebar shape widgets for ``curve_type``,
    falling back to ``DEFAULTS`` for missing keys. When ``silent`` the widgets'
    signals are blocked so the write does not trigger live-preview re-entrancy.
    Unknown types write nothing."""
    # `_hush` gives the same paired block/unblock as before, but via a context
    # manager: an exception between the two halves used to leave the widget
    # permanently unable to emit — silently dead, with no traceback either.
    def _hush(widget):
        return block_signals(widget) if silent else nullcontext()

    if curve_type == "polygon":
        w = getattr(owner, POLYGON_VERTICES_ATTR)
        with _hush(w):
            w.setText(params.get("vertices_str", POLYGON_DEFAULT))
        return
    defaults = DEFAULTS.get(curve_type, {})
    angle_keys = ANGLE_KEYS.get(curve_type, ())
    for key, attr in SIDEBAR_ATTRS.get(curve_type, {}).items():
        w = getattr(owner, attr)
        with _hush(w):
            val = params.get(key, defaults.get(key, 0.0))
            w.setValue(math.degrees(val) if key in angle_keys else val)  # rad→° widget
