"""What the analytic-edge form authors, and the one rule that is not a copy.

Qt-free. The controller used to read twelve sidebar widgets by name and assign
them onto a ``SegmentModel`` field by field, with the polygon node-count rule
buried in the middle of the assignments — so the rule could not be exercised
without a QApplication, a sidebar and a live session.

Only the polygon rule is a decision; the rest is transcription:

**A polygon distributed "By Spacing" derives its node count from its own
perimeter**, so point density follows edge length rather than a fixed count that
means something different on every shape. The order matters and is why this
lives with the spec rather than beside the form: the perimeter is measured from
the shape parameters, so those must be written BEFORE the count is derived.
``spacing`` is kept in the parameters for round-trip; any other mode drops the
key so the node-count spin box governs, because the backend reads ``n_points``.

This spec deliberately does NOT stand in for ``SegmentModel``. The form authors
a subset of an edge — a whole-model write from a partial form is exactly the
hazard ``PRESERVED_FIELDS`` documents for the stage panels — so ``apply_to``
assigns only the fields the form owns and leaves the rest of the segment alone.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


#: Curve-type names, indexed by the type combo's row order. Held here rather
#: than in the controller and the panel, which each kept their own copy: two
#: lists indexed by the same combo is a reordering away from disagreeing about
#: which shape the user picked.
CURVE_TYPES = ("custom", "horizontal_line", "vertical_line", "line",
               "circle", "triangle", "quadrilateral", "polygon", "arc")


def curve_type_for_index(index: int) -> str:
    """The curve type for a combo row; anything unknown is a custom formula."""
    return CURVE_TYPES[index] if 0 <= index < len(CURVE_TYPES) else "custom"


def _polygon_vertices(params: dict):
    """Parse a polygon's vertices, importing shape_spec only when asked.

    Deferred on purpose: shape_spec reaches app.utils, which imports PyQt6 at
    module level, so a plain `import` here would make this module — and the
    rules in it — untestable without Qt, which is the whole reason they moved
    out of the controller. The same deferral app.models.solver_config and
    mesh_config_io already use for the same import.
    """
    from app.models import shape_spec
    return shape_spec.polygon_vertices(params)


def polygon_perimeter(verts) -> float:
    """Closed-polygon perimeter (including the closing edge) from (x, y) pairs."""
    n = len(verts)
    if n < 2:
        return 0.0
    return sum(math.hypot(verts[(i + 1) % n][0] - verts[i][0],
                          verts[(i + 1) % n][1] - verts[i][1])
               for i in range(n))


@dataclass
class CurveEditSpec:
    """One analytic edge's form state, independent of widgets."""

    curve_type: str = "custom"
    parametric: bool = True
    x_formula: str = ""
    y_formula: str = ""
    formula: str = ""
    t_min: float = 0.0
    t_max: float = 1.0
    n_points: int = 50
    start_index: int = 0
    end_index: int = 0
    #: Shape-defining parameters, already in model units (shape_spec converts
    #: the widgets' degrees to radians on the way out).
    shape_params: dict = field(default_factory=dict)
    #: Polygon only: distribute by target spacing rather than by node count.
    by_spacing: bool = False
    spacing: float = 0.0

    def apply_to(self, seg) -> None:
        """Write the fields this form owns onto `seg`, in place."""
        seg.curve_type = self.curve_type
        seg.curve_mode = "parametric" if self.parametric else "explicit"
        seg.x_formula = self.x_formula
        seg.y_formula = self.y_formula
        seg.formula = self.formula
        seg.t_min = self.t_min
        seg.t_max = self.t_max
        seg.parameters["n_points"] = self.n_points
        seg.start_index = self.start_index
        seg.end_index = self.end_index

        # Shape parameters first: the polygon rule below measures them.
        if self.shape_params:
            seg.parameters.update(self.shape_params)

        if self.curve_type == "polygon" and self.by_spacing:
            spacing = max(1e-9, self.spacing)
            seg.parameters["spacing"] = spacing
            per = polygon_perimeter(_polygon_vertices(seg.parameters))
            if per > 0:
                seg.parameters["n_points"] = max(2, int(round(per / spacing)))
        else:
            seg.parameters.pop("spacing", None)
