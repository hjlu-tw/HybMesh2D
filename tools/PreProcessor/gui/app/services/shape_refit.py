"""Re-fitting an imported shape from its moving corner vertices — pure geometry.

Double-clicking an imported (discrete) edge opens a whole-shape editing session:
one draggable handle per corner of the connected outline, and every edge re-fits
between ITS two corners, so dragging a corner two edges share redistributes both.

The arithmetic that does it is a similarity transform per edge, computed from
that edge's ORIGINAL layout — which is why the pristine points are snapshotted
once and every re-fit recomputes from them rather than from the last frame:
accumulating transform onto transform would let a corner dragged in a circle
drift, and would make the revert on Cancel approximate instead of exact.

It read three ``self.`` attributes on the god object and had no test at all.
Here it is two functions over values, so both halves of the contract the editing
session depends on can be pinned:

* **A zero-length edge falls back to a pure translation.** Two corners that
  coincide define no direction, so the similarity transform is undefined (its
  divisor is the squared length); the interior points move rigidly with the
  corner instead. Without the fallback they would be scaled by a division by
  ~zero and fly off the canvas.
* **The closing edge wraps to index 0 rather than being skipped.** An outline's
  last edge runs from its final corner back to the first point, and its
  ``end_index`` is one past the end of the array to say so. Reading that as an
  out-of-range edge and dropping it leaves the closing run of points frozen
  while the corners either side of them move.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Below this squared edge length the two corners are treated as coincident and
#: the edge translates rather than transforming. It is the divisor of the
#: similarity transform, so this is a guard against dividing by ~zero, not a
#: modelling tolerance.
DEGENERATE_LEN2 = 1e-12


@dataclass(frozen=True)
class EdgeSpec:
    """One discrete edge: its two corner indices and the points between them."""

    i0: int
    i1: int
    interior: tuple[int, ...]


def build_edge_specs(segments, n: int) -> tuple[list[EdgeSpec], list[int]]:
    """Map the file segments of an ``n``-point outline onto edge specs.

    Returns ``(specs, corners)`` with the corner indices sorted — that order is
    the handle order the canvas shows, so it has to be stable rather than a set's
    iteration order. Non-file segments (analytic edges drawn on top) take no
    part; a segment whose two corners are the same point, or out of range,
    describes no edge and is dropped.
    """
    specs: list[EdgeSpec] = []
    corners: set[int] = set()
    for s in segments:
        if getattr(s, "type", "") != "file":
            continue
        si = s.start_index
        if s.end_index < n:
            ei = s.end_index
            interior = tuple(range(si + 1, ei))
        else:
            # The closing edge: end_index is one past the end, meaning "back to
            # the first point", so its interior is the whole tail of the array.
            ei = 0
            interior = tuple(range(si + 1, n))
        if not (0 <= si < n and 0 <= ei < n) or si == ei:
            continue
        specs.append(EdgeSpec(si, ei, interior))
        corners.add(si)
        corners.add(ei)
    return specs, sorted(corners)


def refit_shape(orig, specs, corner_pos) -> np.ndarray:
    """Return the outline with every edge re-fitted between its current corners.

    ``orig`` is the pristine point array, ``specs`` the edges from
    :func:`build_edge_specs`, ``corner_pos`` a ``{corner index: [x, y]}`` map of
    where the corners are now. Nothing is mutated: a point belonging to no
    edge's interior — and no corner — keeps its original position, which is what
    the in-place version also did by never writing it.
    """
    orig = np.asarray(orig, dtype=float)
    out = orig.copy()
    for spec in specs:
        i0, i1 = spec.i0, spec.i1
        op0, op1 = orig[i0], orig[i1]
        cp0, cp1 = corner_pos[i0], corner_pos[i1]
        dxP, dyP = float(op1[0] - op0[0]), float(op1[1] - op0[1])
        dxQ, dyQ = float(cp1[0] - cp0[0]), float(cp1[1] - cp0[1])
        len2 = dxP * dxP + dyP * dyP
        if len2 > DEGENERATE_LEN2:
            # The similarity (rotate + uniform scale) taking the original edge
            # vector onto the current one, as a complex quotient Q/P: A is its
            # real part, B its imaginary one.
            A = (dxQ * dxP + dyQ * dyP) / len2
            B = (dyQ * dxP - dxQ * dyP) / len2
            for i in spec.interior:
                xr = float(orig[i][0]) - op0[0]
                yr = float(orig[i][1]) - op0[1]
                out[i] = [A * xr - B * yr + cp0[0], B * xr + A * yr + cp0[1]]
        else:
            for i in spec.interior:
                out[i] = [float(orig[i][0]) - op0[0] + cp0[0],
                          float(orig[i][1]) - op0[1] + cp0[1]]
        out[i0] = list(cp0)
        out[i1] = list(cp1)
    return out
