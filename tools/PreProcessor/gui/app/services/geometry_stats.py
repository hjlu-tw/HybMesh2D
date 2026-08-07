"""Metrics for a CAD geometry (Qt-free).

An industrial pre-processor tells you what you are looking at. Before this, the only
numbers on screen were the ones the user had typed: nothing showed how many points a
geometry actually had, how long its boundary was, or — the one that matters for
meshing — how uneven its point spacing was. A geometry whose spacing jumps 50x
between neighbouring intervals will produce a bad boundary layer, and that was only
discoverable by generating a mesh and looking at the failure.

Pure numpy, no Qt, so the numbers can also be logged from a headless run.
"""
from __future__ import annotations

import numpy as np

#: Expansion ratio above which neighbouring intervals are flagged. Matches the
#: thresholds the .dat quality view already uses (green < 1.05, amber < 1.2), so the
#: panel and the heatmap never disagree about what "uneven" means.
RATIO_WARN = 1.2


def _finite_xy(points) -> np.ndarray:
    """(N,2) float array of the finite points, or an empty array."""
    if points is None:
        return np.empty((0, 2))
    a = np.asarray(points, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] == 0 or a.shape[1] < 2:
        return np.empty((0, 2))
    a = a[:, :2]
    return a[np.all(np.isfinite(a), axis=1)]


def compute(points, *, closed: bool = False, n_segments: int = 0) -> dict:
    """Metrics for one geometry's point array.

    ``closed`` adds the closing interval (last -> first) to the length and spacing
    statistics: on a closed body that interval is a real mesh edge, and leaving it
    out understates the perimeter and can hide the worst expansion ratio, which
    often sits exactly at the seam.

    Returns ``{}`` for an empty/unusable array so callers can show "—" rather than
    inventing zeros that look like real measurements.
    """
    a = _finite_xy(points)
    n = int(a.shape[0])
    if n == 0:
        return {}

    out = {
        "n_points": n,
        "n_segments": int(n_segments),
        "closed": bool(closed),
        "xmin": float(a[:, 0].min()), "xmax": float(a[:, 0].max()),
        "ymin": float(a[:, 1].min()), "ymax": float(a[:, 1].max()),
    }
    out["width"] = out["xmax"] - out["xmin"]
    out["height"] = out["ymax"] - out["ymin"]

    if n < 2:
        return out

    seg = np.diff(a, axis=0)
    if closed and not np.allclose(a[0], a[-1]):
        seg = np.vstack((seg, a[0] - a[-1]))
    ds = np.linalg.norm(seg, axis=1)
    ds = ds[ds > 0.0]                     # duplicate points carry no length
    if ds.size == 0:
        return out

    out.update({
        "length": float(ds.sum()),
        "ds_min": float(ds.min()),
        "ds_max": float(ds.max()),
        "ds_mean": float(ds.mean()),
    })

    if ds.size >= 2:
        # Expansion ratio between neighbours, always >= 1 so growing and shrinking
        # are treated the same — a 2x drop is as bad for the mesh as a 2x jump.
        a_, b_ = ds[:-1], ds[1:]
        ratio = np.maximum(a_ / b_, b_ / a_)
        out["ratio_max"] = float(ratio.max())
        out["ratio_over"] = int((ratio > RATIO_WARN).sum())
        out["ratio_total"] = int(ratio.size)
        # Where the worst jump is, so the number is actionable rather than a verdict.
        out["ratio_max_at"] = int(np.argmax(ratio)) + 1
    return out


def fmt(stats: dict, unit: str = "") -> dict:
    """``compute`` output as display strings ("—" for anything unavailable).

    ``unit`` is appended to the rows that ARE lengths (extent, bounds, perimeter,
    spacing) and withheld from the ones that are not (point/edge counts, topology,
    and the expansion ratio — a ratio of two lengths is dimensionless, and labelling
    it "1.35x mm" would be nonsense presented with authority).
    """
    if not stats:
        return {k: "—" for k in
                ("points", "edges", "closed", "bbox", "size", "length",
                 "spacing", "quality")}

    def g(fmt_str, *keys):
        if any(k not in stats for k in keys):
            return "—"
        return fmt_str % tuple(stats[k] for k in keys)

    u = f" {unit}" if unit else ""
    out = {
        "points": f"{stats['n_points']:,}",
        "edges": f"{stats['n_segments']:,}" if stats.get("n_segments") else "—",
        "closed": "closed" if stats.get("closed") else "open",
        # The unit goes once at the end of a compound read-out rather than on each
        # number: "[0, 4.5] x [0, 1.8] m" reads; four repeats of "m" does not.
        "bbox": g("[%.6g, %.6g] x [%.6g, %.6g]" + u,
                  "xmin", "xmax", "ymin", "ymax"),
        "size": g("%.6g x %.6g" + u, "width", "height"),
        "length": g("%.6g" + u, "length"),
        "spacing": g("min %.4g / mean %.4g / max %.4g" + u,
                     "ds_min", "ds_mean", "ds_max"),
    }
    if "ratio_max" in stats:
        over, total = stats["ratio_over"], stats["ratio_total"]
        out["quality"] = (f"max expansion {stats['ratio_max']:.2f}x"
                          + (f" — {over}/{total} over {RATIO_WARN}x"
                             f" (worst near point {stats['ratio_max_at']})"
                             if over else " — all within "
                             f"{RATIO_WARN}x"))
    else:
        out["quality"] = "—"
    return out


def is_uneven(stats: dict) -> bool:
    """True when the spacing is uneven enough to hurt boundary-layer growth."""
    return bool(stats) and stats.get("ratio_over", 0) > 0
