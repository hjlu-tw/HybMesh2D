from __future__ import annotations
import copy


class SegmentModel:
    """Represents one resampling segment (either from a .dat file or a math formula)."""

    def __init__(self, segment_id: int, start_index: int, end_index: int):
        self.id = segment_id
        self.type = "file"          # "file" | "curve"
        self.start_index = start_index
        self.end_index = end_index

        # Resampling strategy (applies to both file and curve types)
        self.strategy = "uniform"
        self.parameters: dict = {"n_points": 50}

        # Curve-segment fields (only used when type == "curve")
        self.curve_type = "line"      # "custom" | "horizontal_line" | "vertical_line" | "line" | "circle" | "triangle" | "quadrilateral" | "polygon"
        self.curve_mode = "parametric"   # "parametric" | "explicit"
        self.x_formula = "cos(t)"
        self.y_formula = "sin(t)"
        self.formula = "sin(x)"         # explicit y=f(x)
        self.t_min = 0.0
        self.t_max = 6.283185307        # 2π

        # Advanced
        self.match_previous: bool = False

        # Per-segment boundary condition tag. Empty -> inherits the mesh's
        # global geometry BC (BC_GEOM). Carried to the mesher via the .meta
        # sidecar (the C++ backend reads sj["bc"]).
        self.bc: str = ""

        # Whether a polygon / polyline-style edge closes back to its first
        # vertex. Inherently-closed shapes (triangle/quad/circle) ignore this;
        # it matters for `polygon` (incl. file edges baked into a polygon).
        self.closed: bool = True

    # ── Strategy helpers ──────────────────────────────────────────────────

    def update_strategy(self, new_strategy: str):
        self.strategy = new_strategy
        defaults = {
            "uniform":   {"n_points": 50},
            "tanh":      {"n_points": 50, "intensity": 2.0},
            "cosine":    {"n_points": 50},
            "curvature": {"n_points": 50, "sensitivity": 1.5, "max_angle": 15.0},
            "geometric": {"n_points": 50, "ratio": 1.2},
        }
        self.parameters = defaults.get(new_strategy, {"n_points": 50})

    # ── Serialisation ─────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, segment_id: int, d: dict) -> "SegmentModel":
        actual_id = d.get("id", segment_id)
        seg_type = d.get("type", "file")
        if seg_type == "curve":
            seg = cls(actual_id, d.get("start_index", -1), d.get("end_index", -1))
            seg.type = "curve"
            seg.curve_type = d.get("curve_type", "custom")
            seg.strategy = d.get("strategy", "uniform")
            params = copy.deepcopy(d.get("parameters", {"n_points": 50}))
            r = params.pop("range", [0.0, 6.283185307])
            seg.parameters = params
            seg.t_min = float(r[0])
            seg.t_max = float(r[1])
            seg.match_previous = d.get("match_previous", False)
            seg.closed = d.get("closed", True)

            curve_mode = d.get("curve_mode")
            if curve_mode:
                seg.curve_mode = curve_mode
                seg.x_formula = d.get("x_formula", "cos(t)")
                seg.y_formula = d.get("y_formula", "sin(t)")
                seg.formula = d.get("formula", "sin(x)")
            elif "x_formula" in d and "y_formula" in d:
                seg.curve_mode = "parametric"
                seg.x_formula = d["x_formula"]
                seg.y_formula = d["y_formula"]
                seg.formula = d.get("formula", "sin(x)")
            elif "formula" in d:
                seg.curve_mode = "explicit"
                seg.formula = d["formula"]
                seg.x_formula = d.get("x_formula", "cos(t)")
                seg.y_formula = d.get("y_formula", "sin(t)")
            else:
                seg.curve_mode = "parametric"
                seg.x_formula = d.get("x_formula", "cos(t)")
                seg.y_formula = d.get("y_formula", "sin(t)")
                seg.formula = d.get("formula", "sin(x)")
        else:
            seg = cls(actual_id, d.get("start_index", 0), d.get("end_index", -1))
            seg.type = d.get("type", "file")
            seg.strategy = d.get("strategy", "uniform")
            seg.parameters = copy.deepcopy(d.get("parameters", {"n_points": 50}))
            seg.match_previous = d.get("match_previous", False)
            seg.closed = d.get("closed", True)
        seg.bc = d.get("bc", "")
        return seg

    def to_dict(self) -> dict:
        if self.type == "curve":
            params = copy.deepcopy(self.parameters)
            params["range"] = [self.t_min, self.t_max]
            d: dict = {
                "id": self.id,
                "type": "curve",
                "curve_type": self.curve_type,
                "strategy": self.strategy,
                "parameters": params,
                "start_index": int(self.start_index),
                "end_index": int(self.end_index),
            }
            d["curve_mode"] = self.curve_mode
            if self.curve_mode == "parametric":
                d["x_formula"] = self.x_formula
                d["y_formula"] = self.y_formula
            else:
                d["formula"] = self.formula
            if self.match_previous:
                d["match_previous"] = True
            if not self.closed:
                d["closed"] = False
        else:
            d = {
                "id": self.id,
                "type": self.type,
                "start_index": int(self.start_index),
                "end_index": int(self.end_index),
                "strategy": self.strategy,
                "parameters": copy.deepcopy(self.parameters),
            }
            if self.match_previous:
                d["match_previous"] = True
            if not self.closed:
                d["closed"] = False
        if self.bc:
            d["bc"] = self.bc
        return d
