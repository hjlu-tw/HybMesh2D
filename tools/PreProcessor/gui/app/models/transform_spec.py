"""The Duplicate & Transform settings, and the geometry they mean.

Qt-free on purpose. `_apply_transform` was pure geometry — rotate, mirror about
a horizontal / vertical / arbitrary axis, point symmetry, translate, scale about
a pivot — that read all nine of its parameters off sidebar spin boxes, so none
of it could be exercised without building a QApplication and a sidebar. Mirror-
about-an-arbitrary-axis and non-uniform scale are the two easiest to get subtly
wrong and were the two with no reachable test.

Two facts that are decisions rather than arithmetic, and so live here with the
geometry that depends on them:

* **A zero-length mirror axis is not a transform.** Reflecting about a direction
  vector requires normalising it; with |d| below tolerance there is no axis, and
  `apply` reports that by returning None instead of dividing by ~0 and emitting
  NaNs the caller would then try to draw.
* **A scale with different X and Y factors is affine but NOT a similarity.**
  Lines and polygons survive it (their vertices simply move), but a circle
  becomes an ellipse the circle model cannot hold, so the callers that rebuild
  typed edges ask `is_nonuniform_scale` and bake to a polygon instead of
  emitting a wrong-radius circle.

`kind` is a name rather than the combo's row index: the index is a property of
the widget order, and reordering the combo silently changed which transform ran.
`label` carries the UI's own wording so a caller can name the transform in the
log without reading the combo back.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# Combo row -> name. The order is the widget's; the names are the model's.
KINDS = ("rotate", "mirror_h", "mirror_v", "mirror_axis",
         "point_symmetry", "translate", "scale")

#: Base-mode row -> name, and the display text each row carries. The combo's
#: wording used to be compared as a bare string in three places across two
#: layers, so rewording "Custom (Manual)" would have silently stopped the
#: manual-pivot branch from ever matching — the same defect `kind` was given a
#: name to avoid.
BASE_MODES = ("centre", "custom", "start", "end")
BASE_MODE_TEXT = {
    "centre": "Center (selection)",
    "custom": "Custom (Manual)",
    "start": "Start Point",
    "end": "End Point",
}
_BASE_MODE_BY_TEXT = {text: name for name, text in BASE_MODE_TEXT.items()}


def base_mode_for_text(text: str) -> str:
    """The base-mode name for the combo's wording; unknown text is the centre."""
    return _BASE_MODE_BY_TEXT.get(text, "centre")


#: Below this, a mirror-axis direction vector has no direction.
AXIS_EPS = 1e-12
#: Below this, two scale factors are the same number. A separate constant from
#: AXIS_EPS on purpose: one is the length of a direction vector, the other a
#: difference between two ratios, and they are free to diverge.
SCALE_EPS = 1e-12


def kind_for_index(index: int) -> str:
    """The transform name for a combo row (empty for a row we do not know)."""
    return KINDS[index] if 0 <= index < len(KINDS) else ""


@dataclass
class TransformSpec:
    """One Duplicate & Transform configuration, independent of widgets."""

    kind: str
    label: str = ""
    #: One of BASE_MODES, not the combo's wording.
    base_mode: str = "centre"
    delete_original: bool = False

    angle_deg: float = 0.0
    rot_pivot: tuple[float, float] = (0.0, 0.0)
    axis_y: float = 0.0                                    # mirror_h
    axis_x: float = 0.0                                    # mirror_v
    axis_pivot: tuple[float, float] = (0.0, 0.0)           # mirror_axis
    axis_dir: tuple[float, float] = field(default=(1.0, 0.0))
    sym_centre: tuple[float, float] = (0.0, 0.0)           # point_symmetry
    delta: tuple[float, float] = (0.0, 0.0)                # translate
    factors: tuple[float, float] = (1.0, 1.0)              # scale
    scale_pivot: tuple[float, float] = (0.0, 0.0)

    # ── properties the callers branch on ─────────────────────────────────
    @property
    def is_degenerate(self) -> bool:
        """True when the settings describe no transform at all (see AXIS_EPS)."""
        return (self.kind == "mirror_axis"
                and math.hypot(*self.axis_dir) < AXIS_EPS)

    @property
    def is_nonuniform_scale(self) -> bool:
        """A scale whose X and Y factors differ — affine, but not a similarity."""
        return (self.kind == "scale"
                and abs(self.factors[0] - self.factors[1]) > SCALE_EPS)

    @property
    def manual_reference(self) -> bool:
        """True when the user places the pivot rather than the mode deriving it."""
        return self.base_mode == "custom"

    @property
    def has_reference_point(self) -> bool:
        """Translate is defined by a shift, so it has no base point to place."""
        return self.kind != "translate"

    # ── the geometry ─────────────────────────────────────────────────────
    def apply(self, xs, ys):
        """Transform the points, or None when the spec describes no transform.

        Returns fresh arrays; the inputs are never modified in place, because
        callers preview a transform on the same points they may then apply.
        """
        xs = np.asarray(xs, dtype=float).copy()
        ys = np.asarray(ys, dtype=float).copy()

        if self.kind == "rotate":
            theta = math.radians(self.angle_deg)
            px, py = self.rot_pivot
            xr, yr = xs - px, ys - py
            return (px + xr * math.cos(theta) - yr * math.sin(theta),
                    py + xr * math.sin(theta) + yr * math.cos(theta))

        if self.kind == "mirror_h":
            return xs, 2.0 * self.axis_y - ys

        if self.kind == "mirror_v":
            return 2.0 * self.axis_x - xs, ys

        if self.kind == "mirror_axis":
            px, py = self.axis_pivot
            dx, dy = self.axis_dir
            d_len = math.hypot(dx, dy)
            if d_len < AXIS_EPS:
                return None
            dx /= d_len
            dy /= d_len
            xr, yr = xs - px, ys - py
            dot = xr * dx + yr * dy
            return (2.0 * (px + dot * dx) - xs,
                    2.0 * (py + dot * dy) - ys)

        if self.kind == "point_symmetry":
            cx, cy = self.sym_centre
            return 2.0 * cx - xs, 2.0 * cy - ys

        if self.kind == "translate":
            return xs + self.delta[0], ys + self.delta[1]

        if self.kind == "scale":
            sx, sy = self.factors
            px, py = self.scale_pivot
            return px + (xs - px) * sx, py + (ys - py) * sy

        # An unrecognised kind moves nothing rather than guessing.
        return xs, ys
