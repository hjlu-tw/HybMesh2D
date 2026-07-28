from __future__ import annotations
import numpy as np


def project_point_to_segment(p, a, b):
    """Nearest point on segment a→b to point p, and the parameter t in [0, 1].

    Returns ``(proj_xy: np.ndarray, t: float)``; t is clamped so the projection
    stays on the segment (degenerate a==b → t=0, proj=a). Shared by the polygon
    edge-insert hit-test and the discrete-geometry insert-point hit-test."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    p = np.asarray(p, dtype=float)
    ab = b - a
    l2 = float(ab @ ab)
    t = float(np.clip((p - a) @ ab / l2, 0.0, 1.0)) if l2 > 0.0 else 0.0
    return a + t * ab, t


def proportional_edge_move(orig: np.ndarray, split_indices, idx: int,
                           x: float, y: float,
                           is_closed: bool = False) -> np.ndarray:
    """#2: move vertex ``idx`` and stretch the WHOLE edge it belongs to
    proportionally, so a baked / discrete edge keeps its shape instead of
    spiking at a single point. The edge is the span between its split boundaries
    (``split_indices``) or the geometry ends; the far boundary(ies) stay pinned
    so adjacent edges keep their connectivity. Each point's displacement is the
    drag delta scaled by a weight that ramps linearly with arc length from the
    pinned boundary (0) up to the dragged vertex (1): dragging an endpoint scales
    the whole edge, dragging an interior point tapers the shift off toward both
    ends. Returns a new points array.

    #3: when ``is_closed`` and the first/last points coincide (an explicit seam,
    e.g. after converting a closed shape to discrete), dragging either endpoint
    also drags the other to the same target so the loop stays sealed — the head
    and tail move together instead of tearing the seam open."""
    new = orig.copy()
    N = len(orig)
    if not (0 <= idx < N):
        return new
    if (is_closed and N >= 2 and idx in (0, N - 1)
            and np.allclose(orig[0], orig[-1])):
        mirror = N - 1 if idx == 0 else 0
        new = proportional_edge_move(new, split_indices, idx, x, y)
        return proportional_edge_move(new, split_indices, mirror, x, y)
    delta = np.array([x, y], dtype=float) - orig[idx]
    bounds = sorted({0, N - 1, *(int(s) for s in (split_indices or [])
                                 if 0 <= int(s) < N)})
    intervals = [(a, b) for a, b in zip(bounds[:-1], bounds[1:]) if a <= idx <= b]
    if not intervals:                     # degenerate (e.g. single point)
        new[idx] = [x, y]
        return new
    for a, b in intervals:
        seg = orig[a:b + 1]
        if len(seg) < 2:
            continue
        d = np.sqrt((np.diff(seg, axis=0) ** 2).sum(axis=1))
        s = np.concatenate([[0.0], np.cumsum(d)])
        total = s[-1]
        if total <= 1e-12:
            continue
        s_idx = s[idx - a]
        w = np.zeros(len(s))
        if s_idx > 1e-12:
            m = s <= s_idx
            w[m] = s[m] / s_idx
        if total - s_idx > 1e-12:
            m = s >= s_idx
            w[m] = (total - s[m]) / (total - s_idx)
        new[a:b + 1] = seg + np.outer(w, delta)
    return new


def _sample_polyline_pinned(vertices: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Sample n points along a closed polyline, guaranteeing that every specified
    vertex is included in the output.
    """
    k = len(vertices) - 1
    if k < 1:
        return np.full(n, vertices[0, 0]), np.full(n, vertices[0, 1])

    diffs = np.diff(vertices, axis=0)
    edge_lengths = np.sqrt(np.sum(diffs ** 2, axis=1))
    L_total = float(np.sum(edge_lengths))

    if L_total < 1e-12:
        return np.full(n, vertices[0, 0]), np.full(n, vertices[0, 1])

    n_pinned = k + 1
    n_interior = max(0, n - n_pinned)

    exact = n_interior * edge_lengths / L_total
    edge_interior = np.floor(exact).astype(int)
    remainders = exact - edge_interior

    remaining = n_interior - int(np.sum(edge_interior))
    if remaining > 0:
        order = np.argsort(-remainders, kind='stable')
        for i in range(remaining):
            edge_interior[order[i % k]] += 1

    xs: list[float] = []
    ys: list[float] = []
    for i in range(k):
        v_s = vertices[i]
        v_e = vertices[i + 1]
        xs.append(float(v_s[0]))
        ys.append(float(v_s[1]))
        ni = int(edge_interior[i])
        for j in range(1, ni + 1):
            t = j / (ni + 1)
            xs.append(float(v_s[0] + t * (v_e[0] - v_s[0])))
            ys.append(float(v_s[1] + t * (v_e[1] - v_s[1])))
    xs.append(float(vertices[-1][0]))
    ys.append(float(vertices[-1][1]))

    return np.array(xs), np.array(ys)


def _resample_polyline_uniform(xs: np.ndarray, ys: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Resample a 2D polyline (xs, ys) to have n points spaced uniformly in arc length."""
    if len(xs) < 2:
        return xs, ys
    dx = np.diff(xs)
    dy = np.diff(ys)
    dists = np.sqrt(dx**2 + dy**2)
    s = np.zeros(len(xs))
    s[1:] = np.cumsum(dists)

    L = s[-1]
    if L < 1e-12:
        return np.linspace(xs[0], xs[-1], n), np.linspace(ys[0], ys[-1], n)

    t_input = s / L
    t_output = np.linspace(0.0, 1.0, n)
    xs_new = np.interp(t_output, t_input, xs)
    ys_new = np.interp(t_output, t_input, ys)
    return xs_new, ys_new
