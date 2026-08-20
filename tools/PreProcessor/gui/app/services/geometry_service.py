from __future__ import annotations
import math
import os
import numpy as np
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.session import GeometrySession
    from app.models.segment import SegmentModel

# Re-export the moved free functions so the public API at
# ``app.services.geometry_service`` stays identical (existing call sites do
# ``from app.services.geometry_service import project_point_to_segment`` etc.).
from .geometry_primitives import (
    project_point_to_segment,
    proportional_edge_move,
    _sample_polyline_pinned,
    _resample_polyline_uniform,
)
from .geometry_formula import (
    _eval_formula,
    _eval_formula_array,
    _parse_vertices_str,
    format_vertices_str,
)

__all__ = [
    "GeometryLoadError",
    "load_points_dat",
    "GeometryService",
    "project_point_to_segment",
    "proportional_edge_move",
    "_sample_polyline_pinned",
    "_resample_polyline_uniform",
    "_eval_formula",
    "_eval_formula_array",
    "_parse_vertices_str",
    "format_vertices_str",
]


class GeometryLoadError(ValueError):
    """A geometry .dat file could not be parsed into valid (x, y) points.

    Message names the file and the specific problem so it can be surfaced to
    the user instead of letting NaN/garbage propagate into split detection,
    the previews, or the C++ mesher."""


def load_points_dat(file_path: str, allow_nonfinite: bool = False) -> np.ndarray:
    """Load a whitespace-separated ``.dat`` geometry file into an (N, 2+) array,
    validating shape and finiteness up front.

    Shared, single validated loader for every ``np.loadtxt`` geometry call site
    (session/backend controllers, mesh canvas) so a malformed file fails with a
    clear, user-facing :class:`GeometryLoadError` rather than injecting NaN or a
    1-D/empty array downstream.

    Raises :class:`GeometryLoadError` when the file is empty, not 2-D with at
    least two columns, or contains any non-finite (NaN/Inf) coordinate.

    ``allow_nonfinite=True`` keeps the shape validation but permits ``nan``/``inf``
    rows to pass through — used by the multi-piece preview loader, where the
    backend intentionally writes ``nan nan`` piece-separator rows (preview_markers)
    that a downstream splitter strips.
    """
    name = os.path.basename(file_path) or file_path
    pts = np.asarray(np.loadtxt(file_path), dtype=float)
    # A single data row loads as 1-D (N,) — promote it to (1, N). A single
    # *column* also loads as 1-D but must NOT be reinterpreted as one wide row,
    # so require >=2 columns after the promotion (a lone column stays (1, N) with
    # N being the row count, which we reject via the ndim/shape guard below only
    # if it genuinely has <2 values — instead treat any original 1-D array of
    # length !=2 as malformed, and length ==2 as a single (x, y) point row).
    if pts.ndim == 1:
        if pts.shape[0] == 2:
            pts = pts.reshape(1, 2)
        else:
            raise GeometryLoadError(
                f"'{name}': expected rows of 'x y' coordinates but got a single "
                f"column / 1-D array of length {pts.shape[0]}. The file may have "
                "only one coordinate per line or be malformed.")
    if pts.ndim != 2 or pts.shape[0] == 0 or pts.shape[1] < 2:
        raise GeometryLoadError(
            f"'{name}': expected rows of at least 'x y' coordinates, got array "
            f"of shape {pts.shape}. The file may be empty or malformed.")
    if not allow_nonfinite and not np.all(np.isfinite(pts)):
        n_bad = int(np.count_nonzero(~np.isfinite(pts)))
        raise GeometryLoadError(
            f"'{name}': contains {n_bad} non-finite (NaN/Inf) coordinate(s). "
            "Check the geometry data or the curve formula that produced it.")
    return pts


class GeometryService:
    """Pure computational service for geometry tasks, separating UI from domain logic."""

    @staticmethod
    def compute_curve_preview_pts(
        seg: SegmentModel, n: int, original_points: np.ndarray | None
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Compute (xs, ys) for the given curve segment without updating UI/Canvas."""
        gp = original_points

        if seg.curve_type == "horizontal_line":
            y_val = seg.parameters.get("y", 0.0)
            x0 = seg.parameters.get("x0", 0.0)
            x1 = seg.parameters.get("x1", 1.0)
            xs_raw = np.linspace(x0, x1, n)
            ys_raw = np.full(n, y_val)
            xs, ys = _resample_polyline_uniform(xs_raw, ys_raw, n)
        elif seg.curve_type == "vertical_line":
            x_val = seg.parameters.get("x", 0.0)
            y0 = seg.parameters.get("y0", 0.0)
            y1 = seg.parameters.get("y1", 1.0)
            xs_raw = np.full(n, x_val)
            ys_raw = np.linspace(y0, y1, n)
            xs, ys = _resample_polyline_uniform(xs_raw, ys_raw, n)
        elif seg.curve_type == "line":
            x0 = seg.parameters.get("x0", 0.0);  y0 = seg.parameters.get("y0", 0.0)
            x1 = seg.parameters.get("x1", 1.0);  y1 = seg.parameters.get("y1", 1.0)
            xs_raw = np.linspace(x0, x1, n)
            ys_raw = np.linspace(y0, y1, n)
            xs, ys = _resample_polyline_uniform(xs_raw, ys_raw, n)
        elif seg.curve_type in ("circle", "arc"):
            # A circle is the full-turn special case of an arc; share one sampler
            # so a fix to circle/arc sampling can't drift between the two.
            cx = seg.parameters.get("cx", 0.0);  cy = seg.parameters.get("cy", 0.0)
            r  = seg.parameters.get("r",  1.0)
            if seg.curve_type == "circle":
                t0, t1 = 0.0, 2.0 * math.pi
            else:
                t0 = seg.parameters.get("theta0", 0.0)
                t1 = seg.parameters.get("theta1", math.pi / 2)
            ts = np.linspace(t0, t1, n)
            xs_raw = cx + r * np.cos(ts)
            ys_raw = cy + r * np.sin(ts)
            xs, ys = _resample_polyline_uniform(xs_raw, ys_raw, n)
        elif seg.curve_type == "triangle":
            verts = np.array([
                [seg.parameters.get("x0", 0.0), seg.parameters.get("y0", 0.0)],
                [seg.parameters.get("x1", 1.0), seg.parameters.get("y1", 0.0)],
                [seg.parameters.get("x2", 0.5), seg.parameters.get("y2", 1.0)],
                [seg.parameters.get("x0", 0.0), seg.parameters.get("y0", 0.0)],
            ])
            xs, ys = _sample_polyline_pinned(verts, n)
        elif seg.curve_type == "quadrilateral":
            verts = np.array([
                [seg.parameters.get("x0", 0.0), seg.parameters.get("y0", 0.0)],
                [seg.parameters.get("x1", 1.0), seg.parameters.get("y1", 0.0)],
                [seg.parameters.get("x2", 1.0), seg.parameters.get("y2", 1.0)],
                [seg.parameters.get("x3", 0.0), seg.parameters.get("y3", 1.0)],
                [seg.parameters.get("x0", 0.0), seg.parameters.get("y0", 0.0)],
            ])
            xs, ys = _sample_polyline_pinned(verts, n)
        elif seg.curve_type == "polygon":
            v_str = seg.parameters.get("vertices_str", "0,0; 1,0; 1,1; 0,1")
            verts = _parse_vertices_str(v_str)
            # A polygon closes back to its first vertex when closed=True (the
            # default, like triangle/quad). When closed=False it stays an OPEN
            # polyline (used by "Join Edges" without force-close), so its two
            # ends are honoured (and flagged as open endpoints).
            if (getattr(seg, "closed", True) and len(verts) >= 3
                    and not np.allclose(verts[0], verts[-1])):
                verts = np.vstack([verts, verts[0]])
            xs, ys = _sample_polyline_pinned(verts, n)
        else:  # custom
            t_vals = np.linspace(seg.t_min, seg.t_max, n)
            if seg.curve_mode == "parametric":
                xs_raw = _eval_formula_array(seg.x_formula, "t", t_vals)
                ys_raw = _eval_formula_array(seg.y_formula, "t", t_vals)
            else:
                xs_raw = t_vals
                ys_raw = _eval_formula_array(seg.formula, "x", t_vals)
            xs, ys = _resample_polyline_uniform(xs_raw, ys_raw, n)

        valid = np.isfinite(xs) & np.isfinite(ys)
        if not np.any(valid):
            return None, None
        xs, ys = xs[valid], ys[valid]

        # Apply anchoring if start/end node are set
        if gp is not None and len(xs) >= 2:
            si, ei = seg.start_index, seg.end_index
            sv = (si >= 0 and si < len(gp))
            ev = (ei >= 0 and ei < len(gp))
            P0 = np.array([xs[0], ys[0]])
            P1 = np.array([xs[-1], ys[-1]])
            if sv and ev:
                Q0, Q1 = gp[si], gp[ei]
                dx_P, dy_P = P1 - P0
                L_P2 = dx_P**2 + dy_P**2
                if L_P2 > 1e-12:
                    dx_Q, dy_Q = Q1 - Q0
                    A = (dx_Q * dx_P + dy_Q * dy_P) / L_P2
                    B = (dy_Q * dx_P - dx_Q * dy_P) / L_P2
                    xr = xs - P0[0];  yr = ys - P0[1]
                    xs = A * xr - B * yr + Q0[0]
                    ys = B * xr + A * yr + Q0[1]
                else:
                    xs = xs - P0[0] + Q0[0];  ys = ys - P0[1] + Q0[1]
                xs[0], ys[0] = Q0[0], Q0[1]
                xs[-1], ys[-1] = Q1[0], Q1[1]
            elif sv:
                Q0 = gp[si]
                xs = xs - P0[0] + Q0[0];  ys = ys - P0[1] + Q0[1]
                xs[0], ys[0] = Q0[0], Q0[1]
            elif ev:
                Q1 = gp[ei]
                xs = xs - P1[0] + Q1[0];  ys = ys - P1[1] + Q1[1]
                xs[-1], ys[-1] = Q1[0], Q1[1]

        return xs, ys

    @staticmethod
    def _geo_cum(n: int, ratio: float) -> np.ndarray:
        """Normalised cumulative node positions (0..1, length n) for a one-sided
        geometric distribution, mirroring C++ Spacing::generateGeometric."""
        if n < 2:
            return np.zeros(1)
        if abs(ratio - 1.0) < 1e-9:
            return np.linspace(0.0, 1.0, n)
        w = ratio ** np.arange(n - 1)                 # relative cell widths
        cs = np.concatenate([[0.0], np.cumsum(w)])
        return cs / cs[-1]

    @staticmethod
    def _geometric_u(n: int, r0: float, r1: float) -> np.ndarray:
        """Normalised parameter (0..1, length n) for a geometric distribution
        with start ratio r0 and end ratio r1. Mirrors the C++ resampler: both
        ratios non-unit and n>=4 -> two-sided blend; start unit -> single from
        the end; otherwise single from the start."""
        r0 = max(float(r0), 1e-6)
        r1 = max(float(r1), 1e-6)
        s0 = abs(r0 - 1.0) > 1e-9
        s1 = abs(r1 - 1.0) > 1e-9
        if s0 and s1 and n >= 4:
            n_left = (n - 1) // 2
            n_right = (n - 1) - n_left
            fL = n_left / (n - 1)
            a = GeometryService._geo_cum(n_left + 1, r0) * fL          # 0..fL
            b = GeometryService._geo_cum(n_right + 1, r1) * (1.0 - fL)  # 0..(1-fL)
            u = np.concatenate([a, 1.0 - b[:n_right][::-1]])
        elif not s0 and s1:
            u = 1.0 - GeometryService._geo_cum(n, r1)[::-1]
        else:
            u = GeometryService._geo_cum(n, r0)
        u = np.asarray(u, dtype=float)
        if u.size:
            u[0] = 0.0
            u[-1] = 1.0
        return u

    @staticmethod
    def resample_preview(xs, ys, strategy: str, params: dict):
        """Lightweight Python preview of a point distribution along a polyline.

        Re-parametrises by normalised arc length per the chosen strategy so the
        canvas can show the node layout live while the Distribution dialog is
        open.  This is a visual preview — the exact node positions are still
        produced by the C++ resampler on Preview/Export."""
        xs = np.asarray(xs, dtype=float)
        ys = np.asarray(ys, dtype=float)
        if len(xs) < 2:
            return xs, ys
        d = np.sqrt(np.diff(xs) ** 2 + np.diff(ys) ** 2)
        s = np.concatenate([[0.0], np.cumsum(d)])
        L = float(s[-1])
        if L < 1e-12:
            return xs, ys
        t_in = s / L

        if strategy == "uniform" and "spacing" in params:
            sp = max(float(params.get("spacing", 0.1)), 1e-9)
            n = max(2, int(round(L / sp)) + 1)
        else:
            n = max(2, int(params.get("n_points", 50)))
        lin = np.linspace(0.0, 1.0, n)

        if strategy == "cosine":
            u = (1.0 - np.cos(np.pi * lin)) / 2.0
        elif strategy == "tanh":
            it = float(params.get("intensity", 2.0))
            u = lin if it < 1e-6 else 0.5 * (1.0 + np.tanh(it * (lin - 0.5)) / np.tanh(it * 0.5))
        elif strategy == "geometric":
            # Honour BOTH the start and end growth ratios, mirroring the C++
            # resampler (tools/PreProcessor/src/main.cpp, "geometric" branch) so
            # the live preview matches the exported result. Previously only the
            # start ratio was read, so changing the end ratio showed no change.
            r0 = float(params.get("ratio", 1.2))
            r1 = float(params.get("ratio_end", 1.0))
            u = GeometryService._geometric_u(n, r0, r1)
        else:  # uniform / curvature (curvature shown as uniform in preview)
            u = lin

        rx = np.interp(u, t_in, xs)
        ry = np.interp(u, t_in, ys)
        return rx, ry

    @staticmethod
    def auto_detect_features(points: np.ndarray, angle_threshold_deg: float = 30.0) -> list[int]:
        indices = [0]
        n = len(points)
        threshold_rad = math.radians(angle_threshold_deg)
        for i in range(1, n - 1):
            v1 = points[i] - points[i - 1]
            v2 = points[i + 1] - points[i]
            n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
            if n1 == 0 or n2 == 0:
                continue
            dot = float(np.clip(np.dot(v1 / n1, v2 / n2), -1.0, 1.0))
            if math.acos(dot) > threshold_rad:
                indices.append(i)
        if (n - 1) not in indices:
            indices.append(n - 1)
        return indices

    @staticmethod
    def detect_closed(points: np.ndarray | None) -> bool:
        """Decide whether a point list forms a closed loop, from geometry alone.

        Industry-style tolerance detection (cf. Pointwise/Fluent node-merge
        tolerance): the boundary is closed when its first and last points are
        effectively the same *relative to the local point spacing*. Concretely,
        closed when the first↔last gap is either near-zero (endpoints coincide,
        e.g. a NACA .dat that repeats the trailing-edge point, or a circle) or no
        larger than ~1.5× the median edge length (a polygon whose last vertex is
        simply one edge away from the first). A genuinely open polyline (flat
        plate, wall segment) leaves a gap many times the spacing and reads open.

        Spacing-relative so it is scale-invariant. Kept separate from
        ``open_endpoint_ctrl.find_geometry_gaps`` (which uses 4× median to flag
        *anomalous* gaps) — different purpose, different threshold. Pure numpy /
        session-free so the Qt-free model can call it.
        """
        if points is None:
            return False
        pts = np.asarray(points, dtype=float)
        if pts.ndim != 2 or len(pts) < 3:
            return False
        d = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
        pos = d[d > 1e-12]
        if len(pos) == 0:
            return False
        gap = float(np.hypot(pts[0, 0] - pts[-1, 0], pts[0, 1] - pts[-1, 1]))
        med = float(np.median(pos))
        # Coincident endpoints (gap ≈ 0, tolerance tied to the point spacing so
        # it is scale-free) or last vertex within one edge of the first.
        if gap <= 1e-6 * med:
            return True
        return gap <= 1.5 * med

    @staticmethod
    def weld_boundary_endpoints(segments, tol: float) -> int:
        """Snap near-coincident endpoints of adjacent OPEN curve edges onto one
        shared point so separately-drawn edges chain into a SINGLE connected
        boundary. The GUI treats endpoints within ``tol`` (a fraction of the
        bounding box) as connected, but the mesher only joins pieces whose
        endpoints coincide within 1e-7 — so hand-drawn corners that miss by a
        hair are silently split into disconnected pieces. Welding closes that
        gap while keeping every segment (and thus its per-segment BC) separate.

        Mutates ``segments`` in place (callers pass a throw-away copy). Returns
        the number of welded clusters. File segments (shared polyline) and
        centre-defined / closed shapes are left untouched."""
        from app.models import shape_spec
        items = []                       # [seg, handle_id, np.array([x, y])]
        for seg in segments:
            if getattr(seg, "type", "file") != "curve":
                continue
            ct = getattr(seg, "curve_type", "custom")
            if ct == "polygon" and getattr(seg, "closed", True):
                continue                 # already a self-contained loop
            for hid, (x, y) in shape_spec.boundary_endpoints(ct, seg.parameters):
                items.append([seg, hid, np.array([float(x), float(y)])])

        n = len(items)
        if n < 2:
            return 0
        parent = list(range(n))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for i in range(n):
            for j in range(i + 1, n):
                if np.hypot(*(items[i][2] - items[j][2])) <= tol:
                    parent[find(i)] = find(j)
        groups: dict[int, list[int]] = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(i)

        welds = 0
        for members in groups.values():
            if len(members) < 2:
                continue
            pts = np.array([items[k][2] for k in members])
            rep = pts.mean(axis=0)
            if float(np.max(np.hypot(pts[:, 0] - rep[0], pts[:, 1] - rep[1]))) <= 1e-9:
                continue                 # already coincident — nothing to do
            for k in members:
                seg, hid, _ = items[k]
                shape_spec.apply_drag(seg.curve_type, seg.parameters, hid,
                                      float(rep[0]), float(rep[1]))
            welds += 1
        return welds

    @staticmethod
    def get_segment_points(session: GeometrySession, seg: SegmentModel) -> tuple[np.ndarray, np.ndarray] | None:
        """Get points (xs, ys) for the given segment.
        If seg.type is 'file', extracts it from session.original_points.
        If seg.type is 'curve', computes them using compute_curve_preview_pts.
        """
        if seg.type == "file":
            gp = session.original_points
            if gp is None or len(gp) == 0:
                return None
            s, e = seg.start_index, seg.end_index
            if s < 0 or s >= len(gp) or e <= s:
                return None
            if e < len(gp):
                pts = gp[s:e + 1]
            elif session.project_model.is_closed:
                # Closing edge of a closed loop: end index is one past the last
                # point, so it wraps from `start` back to the first point. Keep
                # that wrap so the edge's point count / geometry is complete
                # everywhere (transform, preview, selection).
                pts = np.vstack([gp[s:], gp[:1]])
            else:
                pts = gp[s:]
            if len(pts) == 0:
                return None
            return pts[:, 0].copy(), pts[:, 1].copy()
        else:
            n = seg.parameters.get("n_points", 100)
            try:
                return GeometryService.compute_curve_preview_pts(seg, n, session.original_points)
            except Exception:
                return None

