"""The analytic immersed-solid shape behind an analytic-φ run.

``solver_tools_ctrl.generate_phi_from_cad_shape`` compiles a CAD shape straight
into the init DLL: a circle/arc becomes a solid disk tested by radius, anything
else closed becomes a point-in-polygon over its sampled boundary. That means the
solid's surface is known EXACTLY — no grid, no reconstruction — which is why the
Results surface plot can offer it as a source.

Both the DLL generator and the surface plot read the shape through this module, so
the curve the user plots is by construction the same shape the run is solving. A
second copy of "which CAD edges count as a solid" would be a silent divergence:
the plot would describe a body the DLL never marked.

Qt-free; the geometry sampler is injected via ``GeometryService`` at call time.
"""
from __future__ import annotations

import numpy as np

# Curve types that are always a closed body; polygon/custom qualify only when
# their own `closed` flag says so (an open polyline encloses nothing).
_ALWAYS_CLOSED = ("circle", "triangle", "quadrilateral")
_CLOSED_IF_FLAGGED = ("polygon", "custom")


def is_solid_shape(seg) -> bool:
    """True when this CAD segment can act as an analytic immersed solid."""
    if getattr(seg, "type", "") != "curve":
        return False
    ct = getattr(seg, "curve_type", "")
    if ct in _ALWAYS_CLOSED:
        return True
    if ct in _CLOSED_IF_FLAGGED:
        return bool(getattr(seg, "closed", False))
    return False


def solid_shapes(session) -> list:
    """Every CAD segment in ``session`` that qualifies as an analytic solid."""
    if session is None or getattr(session, "project_model", None) is None:
        return []
    return [s for s in session.project_model.segments if is_solid_shape(s)]


def shape_dict(session, seg) -> dict | None:
    """The analytic shape of one segment, in the form ``surface_source`` consumes.

    circle/arc -> ``{"type": "circle", "cx", "cy", "r"}`` (the disk the DLL tests
    by radius); anything else -> ``{"type": <curve_type>, "verts": [(x, y), …]}``
    (the polygon the DLL tests by point-in-polygon), sampled through
    ``GeometryService`` so the vertices are the ones the DLL was handed.
    """
    from app.services.geometry_service import GeometryService

    if seg is None:
        return None
    ct = getattr(seg, "curve_type", "")
    if ct in ("circle", "arc"):
        p = getattr(seg, "parameters", {}) or {}
        return {"type": "circle", "cx": float(p.get("cx", 0.0)),
                "cy": float(p.get("cy", 0.0)), "r": float(p.get("r", 1.0)),
                "seg_id": getattr(seg, "id", None)}
    pr = GeometryService.get_segment_points(session, seg)
    if pr is None or len(pr[0]) < 3:
        return None
    verts = np.column_stack([np.asarray(pr[0], dtype=float),
                             np.asarray(pr[1], dtype=float)])
    return {"type": ct or "polygon", "verts": [(float(x), float(y)) for x, y in verts],
            "seg_id": getattr(seg, "id", None)}


def describe(shape: dict) -> str:
    """One-line description, matching the wording the DLL generator logs."""
    s = dict(shape or {})
    if str(s.get("type", "")).lower() in ("circle", "arc", "disk"):
        return (f"disk @({s.get('cx', 0.0):g},{s.get('cy', 0.0):g}) "
                f"r={s.get('r', 0.0):g}")
    n = len(s.get("verts") or [])
    return f"{s.get('type', 'polygon')} point-in-polygon ({n} verts)"
