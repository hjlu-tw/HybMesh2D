"""Turning a surface curve into a plottable series: orientation, where s = 0 is,
and how a field value is read off a point that is not a mesh node.

Three things here are not cosmetic:

* **s = 0 must be chosen, not inherited.** The old surface plot took the loop
  order straight from the boundary tracer, whose start is ``next(iter(set))`` —
  deterministic but geometrically meaningless, so the same body in two runs could
  start its arc length in two different places and the curves could not be
  compared. ``rotate_to_start`` pins it to a stated rule (x min, x max, …) and
  reports the coordinate it landed on, which is what the canvas marks.

* **Direction is part of the answer.** A closed curve traversed CW gives the
  mirror image of the same Cp(s), so the traversal is forced to the requested
  handedness via the polygon's signed area rather than left to the extractor.

* **Values off the mesh nodes have to be interpolated, and the sample point may
  not be where the user wants it.** For the mesh-boundary source the points ARE
  nodes, so the nodal field is read directly and the numbers are identical to
  before. Every other source (φ iso-line, analytic shape, CAD outline) lands on
  arbitrary locations, and in an immersed-boundary run those locations sit ON the
  solid interface, where the field is the solid's state, not the wall value. The
  outward-normal offset δ exists for that; it defaults to 0 (sample exactly where
  the curve is, USER-REQUESTED) so nothing is silently moved, and the caller is
  told the offset it used.

Qt-free; numpy only. Interpolation is injected as a callable, so this module is
unit-testable without matplotlib or a live canvas.
"""
from __future__ import annotations

import numpy as np

from app.services.surface_source import START_RULES, SurfaceCurve


def signed_area(points: np.ndarray) -> float:
    """Shoelace area of a closed polyline; > 0 = counter-clockwise."""
    p = np.asarray(points, dtype=float)
    if len(p) < 3:
        return 0.0
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def orient_curve(curve: SurfaceCurve, ccw: bool = True) -> SurfaceCurve:
    """Force the traversal handedness. A closed curve is decided by its signed
    area; an open one has no handedness, so ``ccw=False`` simply reverses it."""
    pts = np.asarray(curve.points, dtype=float)
    ids = curve.node_ids
    reverse = False
    if curve.closed and len(pts) >= 3:
        reverse = (signed_area(pts) > 0) != bool(ccw)
    elif not ccw:
        reverse = True
    if not reverse:
        return curve
    return SurfaceCurve(points=pts[::-1].copy(), closed=curve.closed,
                        label=curve.label, note=curve.note,
                        node_ids=None if ids is None else np.asarray(ids)[::-1].copy())


def start_index(points: np.ndarray, rule: str) -> int:
    """Index of the point the rule selects. Ties break on the other coordinate so
    the choice is reproducible on a symmetric body (a blunt leading edge has two
    x-min points; without a tie-break the pick would depend on point order)."""
    p = np.atleast_2d(np.asarray(points, dtype=float))
    if rule not in START_RULES:
        raise ValueError(f"unknown start rule {rule!r}; expected one of "
                         f"{', '.join(START_RULES)}")
    x, y = p[:, 0], p[:, 1]
    if rule == "xmin":
        return int(np.lexsort((y, x))[0])
    if rule == "xmax":
        return int(np.lexsort((y, -x))[0])
    if rule == "ymin":
        return int(np.lexsort((x, y))[0])
    return int(np.lexsort((x, -y))[0])


def rotate_to_start(curve: SurfaceCurve, rule: str) -> tuple:
    """Put the rule's point at index 0. Returns ``(curve, start_xy)``.

    An OPEN curve cannot be rotated without inventing a connection its geometry
    does not have, so it is only reversed when the rule's point is nearer the far
    end — and the caller is told (via the returned coordinate) where s = 0
    actually ended up.
    """
    pts = np.asarray(curve.points, dtype=float)
    if len(pts) < 2:
        return curve, (float("nan"), float("nan"))
    i = start_index(pts, rule)
    ids = curve.node_ids
    if not curve.closed:
        if i > (len(pts) - 1) / 2.0:
            pts = pts[::-1].copy()
            ids = None if ids is None else np.asarray(ids)[::-1].copy()
            i = len(pts) - 1 - i
        out = SurfaceCurve(points=pts, closed=False, label=curve.label,
                           note=curve.note, node_ids=ids)
        return out, (float(pts[i][0]), float(pts[i][1]))
    rolled = np.roll(pts, -i, axis=0)
    rids = None if ids is None else np.roll(np.asarray(ids), -i)
    out = SurfaceCurve(points=rolled, closed=True, label=curve.label,
                       note=curve.note, node_ids=rids)
    return out, (float(rolled[0][0]), float(rolled[0][1]))


def arc_length(points: np.ndarray, closed: bool = False,
               wrap: bool = False) -> np.ndarray:
    """Cumulative chord length from the first point.

    With ``wrap`` the array is one longer than ``points``: the extra entry is the
    full perimeter, i.e. the closing chord back to s = 0. That is what makes a
    closed-body plot continuous all the way round instead of stopping one chord
    short of where it started — the old ``perimeter_series`` computed the closing
    segment and then sliced it off, so its last point was NOT the perimeter.
    """
    p = np.atleast_2d(np.asarray(points, dtype=float))
    if len(p) == 0:
        return np.empty(0)
    seg = np.hypot(*np.diff(p, axis=0).T) if len(p) > 1 else np.empty(0)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if closed and wrap and len(p) > 1:
        s = np.concatenate([s, [s[-1] + float(np.hypot(*(p[0] - p[-1])))]])
    return s


def outward_normals(points: np.ndarray, closed: bool = False,
                    flip: bool = False) -> np.ndarray:
    """Unit outward normal per point (mean of the adjacent segment normals).

    "Outward" is taken from the polygon's own signed area, NOT from the requested
    traversal direction: rotating the normal by the handedness the caller asked
    for would point the offset into the solid on exactly the curves that were
    reversed to satisfy it.
    """
    p = np.atleast_2d(np.asarray(points, dtype=float))
    n = len(p)
    if n < 2:
        return np.zeros((n, 2))
    d = np.diff(p, axis=0)
    if closed:
        d = np.vstack([d, p[0] - p[-1]])
    seg_n = np.column_stack([d[:, 1], -d[:, 0]])       # right of travel
    ln = np.hypot(seg_n[:, 0], seg_n[:, 1])
    seg_n = seg_n / np.where(ln[:, None] < 1e-300, 1.0, ln[:, None])
    if closed:
        acc = seg_n + np.roll(seg_n, 1, axis=0)        # segments i-1 and i
    else:
        acc = np.vstack([seg_n[:1], seg_n[:-1] + seg_n[1:], seg_n[-1:]])
    ln = np.hypot(acc[:, 0], acc[:, 1])
    out = acc / np.where(ln[:, None] < 1e-300, 1.0, ln[:, None])
    # Walking CCW keeps the interior on the left, so the right of travel — which
    # is what (dy, -dx) is — already points out of the body; a CW loop needs the
    # sign flipped. (Checked against a CCW unit circle: (dy, -dx) is radial.)
    if closed and signed_area(p) < 0:
        out = -out
    if flip:
        out = -out
    return out


def sample_on_curve(curve: SurfaceCurve, *, nodal_values=None, interp=None,
                    offset: float = 0.0, flip: bool = False) -> dict:
    """Field values along a surface curve.

    ``nodal_values`` (the full per-node array) is used when the curve's points ARE
    mesh nodes and no offset is asked for — exact, and byte-identical to what the
    surface plot produced before this module existed. Otherwise ``interp(xs, ys)``
    is called; masked / out-of-mesh samples come back as NaN so a point that fell
    outside the domain reads as missing data instead of a fabricated number.
    """
    pts = np.atleast_2d(np.asarray(curve.points, dtype=float))
    if len(pts) == 0:
        return {"points": pts, "values": np.empty(0), "exact": False, "offset": 0.0}
    delta = float(offset or 0.0)
    if delta != 0.0:
        pts = pts + delta * outward_normals(pts, curve.closed, flip)
    if curve.node_ids is not None and delta == 0.0 and nodal_values is not None:
        vals = np.asarray(nodal_values, dtype=float)[np.asarray(curve.node_ids, int)]
        return {"points": pts, "values": vals, "exact": True, "offset": 0.0}
    if interp is None:
        return {"points": pts, "values": np.full(len(pts), np.nan),
                "exact": False, "offset": delta}
    raw = interp(pts[:, 0], pts[:, 1])
    vals = np.asarray(np.ma.filled(np.ma.masked_invalid(raw), np.nan), dtype=float)
    return {"points": pts, "values": vals, "exact": False, "offset": delta}


def wrap_series(s: np.ndarray, columns: dict, closed: bool) -> tuple:
    """Repeat the first sample at s = perimeter for a closed curve, so every
    plotted column closes the loop instead of ending one chord short."""
    if not closed or len(s) < 2:
        return np.asarray(s), {k: np.asarray(v) for k, v in columns.items()}
    out = {}
    for k, v in columns.items():
        v = np.asarray(v)
        out[k] = np.concatenate([v, v[:1]]) if len(v) == len(s) - 1 else v
    return np.asarray(s), out
