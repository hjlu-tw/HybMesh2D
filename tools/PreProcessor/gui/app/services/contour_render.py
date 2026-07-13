"""Qt-free contour rendering for solver Tecplot results.

Renders a filled contour of one scalar field to a PNG using matplotlib's Agg
backend, so it works headless (no display). Parsing is delegated to
:class:`TecplotResult`; the GUI keeps its own interactive canvas.
"""
from __future__ import annotations
import os

import numpy as np

from app.models.result_data import TecplotResult

# Preferred default field to contour, in order (Mach, pressure, density, ...).
_PREFERRED = ["M", "p", "T", "r", "`r", "vort", "u", "v"]


def _pick_variable(result: TecplotResult, requested: str | None) -> str:
    scalars = result.scalar_variables()
    if not scalars:
        raise ValueError("result has no scalar field variables to contour")
    if requested and requested in scalars:
        return requested
    for name in _PREFERRED:
        if name in scalars:
            return name
    return scalars[0]


def render_contour(result_path: str, out_png: str, *,
                   variable: str | None = None, cmap: str = "jet",
                   levels: int = 40, mesh_overlay: bool = False,
                   overlays: list | None = None, dpi: int = 130,
                   zone: int = -1) -> str:
    """Render a filled contour of ``variable`` from a Tecplot result to a PNG.

    ``overlays`` is an optional list of (N,2) polyline arrays drawn on top (e.g.
    the CAD outline). Returns the chosen variable name.
    """
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri

    if not os.path.exists(result_path):
        raise FileNotFoundError(f"Result file not found: {result_path}")

    result = TecplotResult.from_file(result_path, zone=zone)
    if len(result.nodes) == 0 or len(result.elements) == 0:
        raise ValueError(f"result has no usable mesh ({len(result.nodes)} nodes, "
                         f"{len(result.elements)} elems) — file may be truncated")

    var = _pick_variable(result, variable)
    values = result.cell_to_node(var)          # node-resident field for tricontourf
    x, y = result.nodes[:, 0], result.nodes[:, 1]
    tri = mtri.Triangulation(x, y, result.elements)

    fig, ax = plt.subplots(figsize=(9, 6))
    try:
        fig.patch.set_facecolor("white")

        finite = np.isfinite(values)
        if finite.any():
            vmin, vmax = float(np.min(values[finite])), float(np.max(values[finite]))
        else:
            vmin, vmax = 0.0, 1.0
        if vmin == vmax:
            vmax = vmin + 1.0

        cf = ax.tricontourf(tri, values, levels=levels, cmap=cmap,
                            vmin=vmin, vmax=vmax)
        if mesh_overlay:
            ax.triplot(tri, color="k", linewidth=0.15, alpha=0.4)

        for poly in (overlays or []):
            poly = np.asarray(poly, dtype=float)
            if poly.ndim == 2 and len(poly) >= 2:
                ax.plot(poly[:, 0], poly[:, 1], color="k", linewidth=1.0)

        cbar = fig.colorbar(cf, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(var)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        title = f"{var}"
        if result.zone and result.zone.title:
            title += f"   ({result.zone.title})"
        ax.set_title(title)
        fig.tight_layout()

        os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
        fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    finally:
        plt.close(fig)
    return var
