"""Where the "surface" of a Results surface plot comes from.

Plotting Cp along "the surface" first has to answer *which* curve that is. Until
now there was exactly one answer — the inner boundary loops of the solved
triangulation (``TecplotResult.geometry_boundary_loops``) — which is the only
honest choice for a body-fitted mesh and is useless for an immersed-boundary run,
where the solid does not touch the mesh boundary at all. This module turns "the
surface" into a *choice* (``SurfaceSpec``) over five sources and returns each as
an ORDERED polyline (``SurfaceCurve``), which is what makes arc length mean
anything:

1. ``mesh``            — inner boundary loops of the mesh (the previous, exact path;
                          the points ARE mesh nodes, so ``node_ids`` is carried and
                          values can be read off the nodal field with no interpolation).
2. ``field_iso``       — an iso-line of a field variable the result already carries
                          (``phi`` at 0.5 = the immersed solid's surface).
3. ``grid_iso``        — the same, on the STL3d structured ``phi`` field of the IB
                          stage (a different grid from the CFD mesh).
4. ``interface_cells`` — the point cloud the Fit Δ check reconstructs
                          (``phi_quality.interface_points``: solid cells with a fluid
                          face neighbour). Same points as the STL3d deviation
                          heatmap, so the plotted surface is exactly what Fit Δ
                          measured — but they are cell CENTRES, so the curve is a
                          staircase and has to be chained by nearest neighbour,
                          which can misorder at a thin waist or a branch. That
                          risk is reported in ``SurfaceCurve.note``, never hidden.
5. ``analytic``        — the analytic φ shape itself (circle → exact circle,
                          polygon → its vertices). No reconstruction error at all:
                          when the run defines the solid analytically
                          (``solver_tools_ctrl.generate_phi_from_cad_shape``) this
                          is the true surface and every other source is an
                          approximation of it.
6. ``cad``             — the CAD outline as drawn/imported, straight from the open
                          sessions (the same polylines the Results CAD overlay draws).

**Iso-lines are chained by mesh EDGE identity, not by coordinate matching.** Every
crossing point sits on one mesh edge, so it is computed ONCE per edge (from the
canonically sorted node pair) and shared by both triangles that own it. Chaining
then walks triangle→triangle through shared edge keys, with no distance tolerance
anywhere — a tolerance is what makes contour chaining fail on a fine mesh, where
two genuinely distinct crossings can be closer together than the rounding used to
weld them.

Qt-free and matplotlib-free (numpy only) so it can be unit-tested headless.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

# ── Source kinds ───────────────────────────────────────────────────────────── #
KIND_MESH = "mesh"
KIND_FIELD_ISO = "field_iso"
KIND_GRID_ISO = "grid_iso"
KIND_INTERFACE_CELLS = "interface_cells"
KIND_ANALYTIC = "analytic"
KIND_CAD = "cad"

ALL_KINDS = (KIND_MESH, KIND_FIELD_ISO, KIND_GRID_ISO, KIND_INTERFACE_CELLS,
             KIND_ANALYTIC, KIND_CAD)

KIND_LABELS = {
    KIND_MESH: "Mesh boundary (solved grid)",
    KIND_FIELD_ISO: "φ iso-line (result field)",
    KIND_GRID_ISO: "φ iso-line (STL3d grid)",
    KIND_INTERFACE_CELLS: "Fit Δ interface cells (STL3d)",
    KIND_ANALYTIC: "Analytic φ shape",
    KIND_CAD: "CAD geometry",
}

# Start-of-arc-length rules. Deliberately no default: the caller must pick one
# (USER-REQUESTED) because s = 0 otherwise lands on whichever node the loop
# tracer happened to start from, which is geometrically arbitrary.
START_RULES = ("xmin", "xmax", "ymin", "ymax")
START_RULE_LABELS = {
    "xmin": "x min (leading edge)",
    "xmax": "x max (trailing edge)",
    "ymin": "y min (bottom)",
    "ymax": "y max (top)",
}


@dataclass
class SurfaceCurve:
    """One ordered surface polyline.

    ``node_ids`` is set only when the points ARE mesh nodes (the ``mesh`` source),
    which lets the sampler read exact nodal values instead of interpolating.
    ``closed`` means the last point connects back to the first; the closing chord
    is NOT duplicated in ``points`` (the arc-length code adds it).
    """
    points: np.ndarray
    closed: bool = False
    label: str = ""
    node_ids: np.ndarray | None = None
    note: str = ""

    def __len__(self) -> int:
        return int(len(self.points))

    @property
    def perimeter(self) -> float:
        p = self.points
        if len(p) < 2:
            return 0.0
        d = np.diff(p, axis=0)
        total = float(np.hypot(d[:, 0], d[:, 1]).sum())
        if self.closed:
            total += float(np.hypot(*(p[0] - p[-1])))
        return total


@dataclass
class SurfaceSpec:
    """A complete description of the surface to plot — everything the user picked.

    Nothing here computes: the spec is what the dialog holds while the user is
    still choosing, and extraction happens only when they ask for it.
    """
    kind: str = KIND_MESH
    var: str = "phi"                 # field_iso: which variable to contour
    level: float = 0.5               # field_iso / grid_iso: iso value
    loop: int = -1                   # -1 = longest loop, else its index
    session_ids: tuple = ()          # cad: which CAD sessions
    shape: dict | None = None        # analytic: {"type","cx","cy","r"} / {"type","verts"}
    grid_slice: int = -1             # grid_iso: k index into a 3D φ field, -1 = middle
    start_rule: str = ""             # "" = not chosen yet (no silent default)
    ccw: bool = True                 # traversal direction
    offset: float = 0.0              # sample δ along the outward normal
    flip_normal: bool = False        # which side "outward" is on an open curve
    extras: dict = field(default_factory=dict)

    def label(self) -> str:
        base = KIND_LABELS.get(self.kind, self.kind)
        if self.kind in (KIND_FIELD_ISO, KIND_GRID_ISO):
            return f"{base}  {self.var} = {self.level:g}"
        return base


# --------------------------------------------------------------------------- #
# Iso-line extraction over a triangulation
# --------------------------------------------------------------------------- #
def _crossing_edges(tris: np.ndarray, vals: np.ndarray, level: float):
    """Per-triangle crossing edges of ``vals == level``.

    Returns ``(sel_tris, ek)`` where ``ek`` is (M, 2) canonical edge keys (the two
    edges of each selected triangle that the level crosses). With ``pos = v > 0``
    a triangle's three vertices are 2-coloured, so the number of bichromatic
    edges is 0 or 2 — never 1 or 3, which is why every selected triangle
    contributes exactly one segment.
    """
    tris = np.asarray(tris, dtype=np.int64)
    v = np.asarray(vals, dtype=float)[tris] - float(level)
    pos = v > 0
    pairs = ((0, 1), (1, 2), (2, 0))
    cross = np.stack([pos[:, a] != pos[:, b] for a, b in pairs], axis=1)
    sel = cross.sum(axis=1) == 2
    if not sel.any():
        return np.empty(0, dtype=np.int64), np.empty((0, 2), dtype=np.int64)
    n_nodes = int(tris.max()) + 1
    # Canonical key per edge so both owning triangles agree bit-for-bit.
    keys = np.stack([
        np.minimum(tris[:, a], tris[:, b]) * n_nodes
        + np.maximum(tris[:, a], tris[:, b]) for a, b in pairs], axis=1)
    sel_idx = np.flatnonzero(sel)
    # The two crossing edges of each selected triangle, in edge order (a stable
    # sort of "not crossing" puts the crossing ones first).
    order = np.argsort(~cross[sel_idx], axis=1, kind="stable")[:, :2]
    rows = np.arange(len(sel_idx))
    ek = keys[sel_idx][rows[:, None], order]
    return sel_idx, ek


def _edge_points(ek_unique: np.ndarray, nodes: np.ndarray, vals: np.ndarray,
                 level: float, n_nodes: int) -> np.ndarray:
    """Linear crossing point on each edge key — computed once per edge, so the
    two triangles sharing it get the identical coordinate."""
    a = (ek_unique // n_nodes).astype(np.int64)
    b = (ek_unique % n_nodes).astype(np.int64)
    va = np.asarray(vals, dtype=float)[a] - float(level)
    vb = np.asarray(vals, dtype=float)[b] - float(level)
    denom = va - vb
    denom = np.where(np.abs(denom) < 1e-300, 1.0, denom)
    t = np.clip(va / denom, 0.0, 1.0)[:, None]
    pa = np.asarray(nodes, dtype=float)[a][:, :2]
    pb = np.asarray(nodes, dtype=float)[b][:, :2]
    return pa + t * (pb - pa)


def _walk_chains(ek: np.ndarray, pt_of_key: dict) -> list:
    """Chain per-triangle segments into ordered polylines.

    Graph nodes are the crossing triangles; graph edges are the mesh edges the
    level crosses. Every triangle has degree 2, so each component is a simple
    path (an iso-line that leaves through the mesh boundary) or a cycle (a closed
    iso-line). Paths are walked from their loose end first, so a cycle is only
    ever reported ``closed`` when it really has no loose end.
    """
    m = len(ek)
    inc: dict = defaultdict(list)
    for i in range(m):
        inc[int(ek[i, 0])].append(i)
        inc[int(ek[i, 1])].append(i)
    used = np.zeros(m, dtype=bool)
    curves: list = []

    def walk(i0: int, k0: int):
        pts = [pt_of_key[int(ek[i0, k0])]]
        i, k = i0, k0
        entry0 = int(ek[i0, k0])
        closed = False
        while True:
            used[i] = True
            k_out = 1 - k
            key_out = int(ek[i, k_out])
            pts.append(pt_of_key[key_out])
            nxt = [j for j in inc[key_out] if j != i and not used[j]]
            if not nxt:
                # A cycle can only end by arriving back at the edge it started
                # from; any other dead end is a path that left the mesh.
                closed = key_out == entry0
                break
            j = nxt[0]
            k = 0 if int(ek[j, 0]) == key_out else 1
            i = j
        arr = np.asarray(pts, dtype=float)
        if closed and len(arr) > 1:
            arr = arr[:-1]          # drop the duplicated start point
        return SurfaceCurve(points=arr, closed=bool(closed))

    # Loose ends first (an edge crossed by only one triangle is a boundary exit).
    for i in range(m):
        for k in (0, 1):
            if not used[i] and len(inc[int(ek[i, k])]) == 1:
                curves.append(walk(i, k))
    for i in range(m):
        if not used[i]:
            curves.append(walk(i, 0))
    return [c for c in curves if len(c) >= 2]


def iso_curves(nodes: np.ndarray, tris: np.ndarray, vals: np.ndarray,
               level: float) -> list:
    """Iso-line of a nodal field over a triangulation, as ordered polylines."""
    nodes = np.asarray(nodes, dtype=float)
    tris = np.asarray(tris, dtype=np.int64)
    if tris.size == 0 or nodes.size == 0:
        return []
    sel_idx, ek = _crossing_edges(tris, vals, level)
    if len(sel_idx) == 0:
        return []
    n_nodes = int(tris.max()) + 1
    uniq = np.unique(ek)
    pts = _edge_points(uniq, nodes, vals, level, n_nodes)
    pt_of_key = {int(k): pts[i] for i, k in enumerate(uniq)}
    return _walk_chains(ek, pt_of_key)


# --------------------------------------------------------------------------- #
# Structured (STL3d) φ field
# --------------------------------------------------------------------------- #
def grid_slice_xy(pts: np.ndarray, phi: np.ndarray, nx: int, ny: int, nz: int,
                  k: int = -1):
    """One k-layer of a Tecplot POINT-order structured field as (xy, values).

    STL3d writes i fastest, then j, then k, so the flat field reshapes to
    [k, j, i] — the same convention ``phi_quality`` relies on. ``k = -1`` takes
    the middle layer, which for the quasi-2D immersed-solid case (the default) is
    the only layer that matters.
    """
    pts = np.asarray(pts, dtype=float)
    phi = np.asarray(phi, dtype=float)
    nx, ny, nz = int(nx), int(ny), int(nz)
    if nx * ny * nz != len(phi):
        raise ValueError(f"grid {nx}×{ny}×{nz} does not match the φ field "
                         f"({len(phi)} points)")
    kk = (nz // 2) if k < 0 else max(0, min(nz - 1, int(k)))
    layer = slice(kk * ny * nx, (kk + 1) * ny * nx)
    return pts[layer][:, :2], phi[layer]


def grid_triangles(nx: int, ny: int) -> np.ndarray:
    """Two triangles per structured cell, so the iso-line extractor above serves
    the structured φ field as well (one code path, one set of tests)."""
    nx, ny = int(nx), int(ny)
    if nx < 2 or ny < 2:
        return np.empty((0, 3), dtype=np.int64)
    j, i = np.meshgrid(np.arange(ny - 1), np.arange(nx - 1), indexing="ij")
    n0 = (j * nx + i).ravel()
    n1, n2, n3 = n0 + 1, n0 + nx, n0 + nx + 1
    return np.vstack([np.stack([n0, n1, n3], axis=1),
                      np.stack([n0, n3, n2], axis=1)]).astype(np.int64)


def grid_iso_curves(pts: np.ndarray, phi: np.ndarray, nx: int, ny: int, nz: int,
                    level: float = 0.5, k: int = -1) -> list:
    xy, vals = grid_slice_xy(pts, phi, nx, ny, nz, k)
    return iso_curves(xy, grid_triangles(nx, ny), vals, level)


# --------------------------------------------------------------------------- #
# Fit Δ interface cells -> a chained polyline
# --------------------------------------------------------------------------- #
_NN_CHAIN_LIMIT = 20000


def chain_points_nn(pts: np.ndarray) -> SurfaceCurve:
    """Order an UNORDERED point cloud (the Fit Δ interface cells) by walking
    nearest neighbours from the min-x point.

    This is the honest cost of using the Fit Δ points as a curve: they are cell
    centres of a staircase, carry no connectivity, and a greedy walk can jump
    across a thin waist or take the wrong branch at a junction. When a hop is
    much longer than the typical one, that is exactly what happened, and the
    curve says so in ``note`` rather than quietly producing a plausible-looking
    arc length.
    """
    pts = np.atleast_2d(np.asarray(pts, dtype=float))[:, :2]
    n = len(pts)
    if n < 2:
        return SurfaceCurve(points=pts, closed=False,
                            note="too few interface points to chain")
    if n > _NN_CHAIN_LIMIT:
        return SurfaceCurve(
            points=np.empty((0, 2)), closed=False,
            note=f"{n} interface points exceeds the {_NN_CHAIN_LIMIT} chaining "
                 "limit; coarsen Nx/Ny or use the φ iso-line source")
    order = [int(np.lexsort((pts[:, 1], pts[:, 0]))[0])]   # min x (then min y)
    left = np.ones(n, dtype=bool)
    left[order[0]] = False
    hops: list = []
    for _ in range(n - 1):
        cur = pts[order[-1]]
        d = np.hypot(pts[:, 0] - cur[0], pts[:, 1] - cur[1])
        d[~left] = np.inf
        j = int(np.argmin(d))
        if not np.isfinite(d[j]):
            break
        hops.append(float(d[j]))
        order.append(j)
        left[j] = False
    chain = pts[np.asarray(order, dtype=int)]
    med = float(np.median(hops)) if hops else 0.0
    closing = float(np.hypot(*(chain[0] - chain[-1]))) if len(chain) > 2 else np.inf
    closed = bool(med > 0 and closing <= 3.0 * med)
    note = ""
    if med > 0 and hops:
        worst = max(hops)
        if worst > 5.0 * med:
            note = (f"nearest-neighbour chaining jumped {worst / med:.0f}× the "
                    "typical spacing — the arc-length order is unreliable here "
                    "(prefer the φ iso-line source)")
    return SurfaceCurve(points=chain, closed=closed, note=note)


# --------------------------------------------------------------------------- #
# Analytic φ shape / CAD polylines
# --------------------------------------------------------------------------- #
def analytic_curve(shape: dict, n: int = 361) -> SurfaceCurve:
    """The analytic solid's own boundary — no reconstruction, no grid error.

    Mirrors what ``render_analytic_phi_from_shape`` compiles into the init DLL:
    circle/arc -> a disk of radius r about (cx, cy); polygon/triangle/quad ->
    point-in-polygon over its vertices.
    """
    s = dict(shape or {})
    st = str(s.get("type", "")).lower()
    if st in ("circle", "arc", "disk"):
        cx = float(s.get("cx", 0.0)); cy = float(s.get("cy", 0.0))
        r = float(s.get("r", s.get("radius", 0.0)))
        if r <= 0:
            return SurfaceCurve(points=np.empty((0, 2)), note="radius <= 0")
        th = np.linspace(0.0, 2.0 * np.pi, max(16, int(n)), endpoint=False)
        pts = np.column_stack([cx + r * np.cos(th), cy + r * np.sin(th)])
        return SurfaceCurve(points=pts, closed=True,
                            label=f"disk @({cx:g},{cy:g}) r={r:g}")
    verts = np.atleast_2d(np.asarray(s.get("verts") or [], dtype=float))
    if verts.size == 0 or verts.shape[1] < 2:
        return SurfaceCurve(points=np.empty((0, 2)),
                            note=f"analytic shape '{st}' has no vertices")
    verts = verts[:, :2]
    if len(verts) > 2 and np.allclose(verts[0], verts[-1]):
        verts = verts[:-1]
    return SurfaceCurve(points=verts, closed=True,
                        label=f"{st or 'polygon'} ({len(verts)} verts)")


def cad_curves(polylines) -> list:
    """CAD outline pieces as surface curves. ``cad_overlay_polylines`` already
    closes a closed project by repeating the first point; drop that duplicate so
    the closing chord is added once, by the arc-length code, like every other
    source."""
    out: list = []
    for k, p in enumerate(polylines or []):
        arr = np.atleast_2d(np.asarray(p, dtype=float))
        if arr.ndim != 2 or arr.shape[1] < 2 or len(arr) < 2:
            continue
        arr = arr[:, :2]
        closed = len(arr) > 2 and bool(np.allclose(arr[0], arr[-1]))
        if closed:
            arr = arr[:-1]
        out.append(SurfaceCurve(points=arr, closed=closed,
                                label=f"CAD piece {k + 1}"))
    return out


def mesh_boundary_curves(result) -> list:
    """The previous source: inner boundary loops of the solved triangulation.
    ``node_ids`` is carried so the sampler can read exact nodal values."""
    out: list = []
    nodes = np.asarray(result.nodes, dtype=float)
    for k, loop in enumerate(result.geometry_boundary_loops()):
        idx = np.asarray(loop, dtype=int)
        if len(idx) < 3:
            continue
        out.append(SurfaceCurve(points=nodes[idx][:, :2], closed=True,
                                node_ids=idx, label=f"Loop {k + 1}"))
    return out


def pick_curve(curves: list, loop: int = -1) -> SurfaceCurve | None:
    """Choose one curve from a multi-piece extraction: the longest by PERIMETER
    (not by point count — a densely resampled flap can carry more points than the
    main body it hangs off), or an explicit index."""
    curves = [c for c in curves if len(c) >= 2]
    if not curves:
        return None
    if 0 <= loop < len(curves):
        return curves[loop]
    return max(curves, key=lambda c: c.perimeter)
