"""Canvas measuring / snapping / view-history logic (Qt-free).

The canvas could draw and drag but not *measure*: checking a slat gap, a chord, or
the clearance a boundary layer has to fit into meant exporting the geometry and
computing it elsewhere. It also had no grid snap (only endpoint snap) and no way back
to a previous zoom.

The maths lives here, away from Qt, so it is testable without a display and reusable
from a headless report.
"""
from __future__ import annotations

import math

#: Cap on the view history. Deep enough to undo a session's worth of zooming,
#: bounded so a long session cannot grow it without limit.
MAX_VIEW_HISTORY = 50


def snap_to_grid(x: float, y: float, step: float) -> tuple:
    """Round (x, y) to the nearest multiple of ``step``.

    ``step <= 0`` (or non-finite) means "snapping off" and returns the point
    unchanged — the caller should not have to special-case a disabled grid.
    """
    if not step or step <= 0 or not math.isfinite(step):
        return float(x), float(y)
    return (round(float(x) / step) * step, round(float(y) / step) * step)


def compose_snap(x: float, y: float, *, endpoint_snap=None, grid_step: float = 0.0):
    """Apply endpoint snapping first, then the grid.

    Order is deliberate and is the whole point of this helper: landing exactly on an
    existing geometry point matters more than landing on an abstract grid line. If the
    grid ran last unconditionally it would drag a just-welded endpoint back off the
    geometry, silently reintroducing the gap the user was closing.

    Returns ``(x, y, snapped_to_endpoint)`` so the caller can report which rule won.
    """
    if endpoint_snap is not None:
        sx, sy = endpoint_snap(x, y)
        if (sx, sy) != (x, y):
            return float(sx), float(sy), True
        x, y = sx, sy
    gx, gy = snap_to_grid(x, y, grid_step)
    return gx, gy, False


def measure(p0, p1) -> dict:
    """Distance / dx / dy / angle between two points.

    ``angle_deg`` is measured from the +x axis in (-180, 180], the convention a CFD
    user reads as "angle of attack"-like. Returns ``{}`` for a degenerate input so a
    caller shows "—" rather than a zero that looks measured.
    """
    try:
        x0, y0 = float(p0[0]), float(p0[1])
        x1, y1 = float(p1[0]), float(p1[1])
    except (TypeError, IndexError, ValueError):
        return {}
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
        return {}
    dx, dy = x1 - x0, y1 - y0
    return {
        "p0": (x0, y0), "p1": (x1, y1),
        "dx": dx, "dy": dy,
        "distance": math.hypot(dx, dy),
        "angle_deg": math.degrees(math.atan2(dy, dx)),
    }


def format_measure(m: dict) -> str:
    """One-line read-out for the status bar / log."""
    if not m:
        return "—"
    return (f"d = {m['distance']:.6g}   "
            f"dx = {m['dx']:.6g}   dy = {m['dy']:.6g}   "
            f"angle = {m['angle_deg']:.2f}°")


class ViewHistory:
    """Back/forward stack of canvas view ranges.

    A view is ``((x0, x1), (y0, y1))``. Two views count as the same navigation step
    when every edge is within ``tol`` of the other's, **measured as a fraction of the
    span** — 1% of the visible width, not an absolute distance, because a canvas showing
    a 2000 mm domain and one showing a 0.02 m aerofoil need the same answer.

    An earlier version documented this collapsing but set ``tol = 1e-9``, which only ever
    merged bit-identical views. pyqtgraph emits a range change per axis, so a single
    ``setRange`` pushed two entries a hair apart and one press of Back visibly did
    nothing. The tolerance is the second half of the fix; the first is not recording
    until the view stops moving (see ``canvas_tools_mixin``), so Back means "back one
    gesture" rather than "back one wheel notch".
    """

    def __init__(self, max_len: int = MAX_VIEW_HISTORY, tol: float = 0.01):
        self._views: list = []
        self._index = -1
        self._max = int(max_len)
        self._tol = float(tol)
        #: Set while back()/forward() is applying a view, so the resulting range
        #: change is not recorded as a new navigation step.
        self.restoring = False

    # ------------------------------------------------------------------ #
    def _same(self, a, b) -> bool:
        """True when ``a`` and ``b`` are the same navigation step.

        Compared per axis against that axis's span, so the test is scale-free. A
        degenerate span falls back to the coordinate magnitude rather than dividing by
        zero.
        """
        try:
            for pair_a, pair_b in zip(a, b):
                span = max(abs(pair_a[1] - pair_a[0]), abs(pair_b[1] - pair_b[0]))
                if span <= 0:
                    span = max(1.0, abs(pair_a[0]), abs(pair_b[0]))
                if any(abs(u - v) > self._tol * span
                       for u, v in zip(pair_a, pair_b)):
                    return False
            return True
        except (TypeError, ValueError, IndexError):
            return False

    def push(self, view) -> bool:
        """Record a view. Returns True if it was actually added."""
        if self.restoring or view is None:
            return False
        try:
            view = ((float(view[0][0]), float(view[0][1])),
                    (float(view[1][0]), float(view[1][1])))
        except (TypeError, IndexError, ValueError):
            return False
        if not all(math.isfinite(v) for pair in view for v in pair):
            return False
        if self._index >= 0 and self._same(self._views[self._index], view):
            return False
        # A new navigation after going back truncates the forward branch, which is
        # what every browser and CAD tool does.
        del self._views[self._index + 1:]
        self._views.append(view)
        if len(self._views) > self._max:
            self._views.pop(0)
        self._index = len(self._views) - 1
        return True

    @property
    def can_back(self) -> bool:
        return self._index > 0

    @property
    def can_forward(self) -> bool:
        return 0 <= self._index < len(self._views) - 1

    def back(self):
        """Previous view, or None."""
        if not self.can_back:
            return None
        self._index -= 1
        return self._views[self._index]

    def forward(self):
        """Next view, or None."""
        if not self.can_forward:
            return None
        self._index += 1
        return self._views[self._index]

    def clear(self):
        self._views.clear()
        self._index = -1

    def __len__(self) -> int:
        return len(self._views)
