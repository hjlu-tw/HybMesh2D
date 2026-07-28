from __future__ import annotations
import math
import numpy as np


# ── Helper functions for formula evaluation and sampling ────────────────────

def _eval_formula(expr: str, var_name: str, val: float) -> float:
    """Safely evaluate a single math expression."""
    if "__" in expr:
        return float("nan")
    safe = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    safe["pi"] = math.pi
    safe[var_name] = float(val)
    try:
        return float(eval(expr.replace("^", "**"), {"__builtins__": None}, safe))
    except Exception:
        return float("nan")


def _eval_formula_array(expr: str, var_name: str, vals: np.ndarray) -> np.ndarray:
    """Evaluate a math expression over a numpy array in a vectorized manner."""
    if "__" in expr:
        return np.full_like(vals, float("nan"), dtype=float)
    safe = {
        "pi": np.pi,
        "sin": np.sin,
        "cos": np.cos,
        "tan": np.tan,
        "asin": np.arcsin,
        "acos": np.arccos,
        "atan": np.arctan,
        "sinh": np.sinh,
        "cosh": np.cosh,
        "tanh": np.tanh,
        "exp": np.exp,
        "log": np.log,
        "log10": np.log10,
        "sqrt": np.sqrt,
        "pow": np.power,
        "abs": np.abs,
    }
    import math
    safe["math"] = math

    parsed_expr = expr.replace("^", "**")
    try:
        safe[var_name] = vals
        res = eval(parsed_expr, {"__builtins__": None}, safe)
        if isinstance(res, np.ndarray):
            return res.astype(float)
        return np.full_like(vals, float(res), dtype=float)
    except Exception:
        return np.array([_eval_formula(expr, var_name, v) for v in vals])


def _parse_vertices_str(s: str) -> np.ndarray:
    pairs = s.split(";")
    pts = []
    for p in pairs:
        if not p.strip():
            continue
        parts = p.split(",")
        if len(parts) == 2:
            try:
                pts.append([float(parts[0].strip()), float(parts[1].strip())])
            except ValueError:
                pass
    if len(pts) < 2:
        return np.array([[0.0, 0.0], [1.0, 1.0]])
    return np.array(pts)


# Canonical polygon vertices_str serialisation, shared by every producer (canvas
# drag, right-click insert/delete, transform bake, sidebar table) so the format
# lives in ONE place next to its parser. %.10g (not %.6g) keeps ~10 significant
# digits, so repeated drag/edit round-trips through the string don't accumulate
# visible coordinate drift.
def format_vertices_str(verts) -> str:
    """Serialise an iterable of (x, y) to the canonical ``"x,y; x,y; …"`` form."""
    return "; ".join(f"{float(x):.10g},{float(y):.10g}" for x, y in verts)
