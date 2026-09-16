from __future__ import annotations
import math
import numpy as np

from app.services.logging_setup import get_logger

_log = get_logger(__name__)


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
        # DEBUG, and the grade is decided by the CALL RATE rather than by how
        # much it matters: this runs once per sample, so a formula the user is
        # still halfway through typing would write one WARNING per point of the
        # curve. The user-facing answer to a bad formula is the NaN itself,
        # which draws nothing; this record is for the case where the expression
        # looks right and the evaluation still fails.
        _log.debug("formula %r failed at %s=%r; returning NaN", expr, var_name,
                   val, exc_info=True)
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
        # DEBUG: this handler RECOVERS rather than discards -- the scalar path
        # below evaluates the same expression per sample and is the answer, so
        # nothing is lost when it is taken. What is worth a record is that the
        # vectorised route failed at all, because the fallback is O(n) evals and
        # a formula that always takes it is a silent slow path.
        _log.debug("vectorised evaluation of %r failed; falling back to %d "
                   "per-sample evaluations", expr, len(vals), exc_info=True)
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
