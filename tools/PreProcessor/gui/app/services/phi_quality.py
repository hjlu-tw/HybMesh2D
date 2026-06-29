"""Fit metrics between an STL surface and the STL3d ``phi`` marker field.

``phi`` is a *binary* in/out field sampled exactly at the grid points (0 = fluid,
1 = solid), so the only discrepancy versus the original STL is the finite-grid
staircase (discretisation) error. These metrics therefore answer the practical
question "is the chosen Nx/Ny/Nz resolution enough to capture this geometry?".

Two layers are reported:

1. **Volume / area agreement** — a cheap global check. In a full-3D grid the
   solid-cell volume is compared with the STL's signed volume; in the quasi-2D
   case (Nz<=2 or dz=0) the per-layer solid *area* is compared with the STL's
   XY footprint (volume is ill-defined for a zero-thickness grid).

2. **Surface deviation** — the real "吻合度". The reconstructed solid boundary
   (interface cells) is measured against the STL surface with an exact
   point-to-triangle distance, and the reverse direction (STL -> interface)
   gives a symmetric Hausdorff distance. Deviations are reported in model units
   and in cell counts (dev / h).

A *quasi-2D branch* collapses everything to the XY plane and ignores the STL's
top/bottom cap triangles, so the slab end-caps of an extruded geometry do not
pollute the in-plane deviation (this is the default immersed-solid case).

Dependencies: numpy only. ``scipy.spatial.cKDTree`` is used as an accelerator
when importable, with an exact (slower) numpy fallback otherwise.
"""
from __future__ import annotations

import numpy as np

# Candidate triangles examined per query point when the KD-tree accelerator is
# available. Exact distance is computed against these nearest-centroid
# candidates; 32 is robust for reasonably uniform tessellations.
_K_CANDIDATES = 32

# Surface-fit verdict thresholds, in cell counts (max deviation / cell size).
# Single source of truth shared by the fit report (stl3d_ctrl) and the canvas
# deviation heatmap colour ramp (stl3d_canvas), so the verdict, the heatmap
# saturation point, and the legend never drift apart.
FIT_WELL_CELLS = 1.0    # max deviation <= 1 cell  -> well resolved
FIT_OK_CELLS = 2.0      # <= 2 cells -> acceptable; also the heatmap red endpoint

# scipy's cKDTree is an optional accelerator. Import it lazily (and cache the
# result) so merely importing this module never pulls in scipy at GUI startup.
_cKDTree = None
_kdt_resolved = False


def _get_kdtree():
    global _cKDTree, _kdt_resolved
    if not _kdt_resolved:
        _kdt_resolved = True
        try:
            from scipy.spatial import cKDTree
            _cKDTree = cKDTree
        except Exception:                  # pragma: no cover - numpy fallback
            _cKDTree = None
    return _cKDTree


# --------------------------------------------------------------------------- #
# Geometry primitives
# --------------------------------------------------------------------------- #
def signed_volume(tris: np.ndarray) -> float:
    """Signed volume of a closed triangulated surface (divergence theorem).

    Works regardless of how vertices are shared; the absolute value is the
    enclosed volume for a watertight, consistently-wound surface.
    """
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    return float(np.sum(np.einsum("ij,ij->i", v0, np.cross(v1, v2))) / 6.0)


def xy_footprint_area(tris: np.ndarray) -> float:
    """XY footprint (cross-section) area of a closed surface.

    For a vertical extrusion the top and bottom caps each project to the full
    footprint while side walls project to zero-area lines, so summing the
    absolute projected triangle areas double-counts the footprint exactly:
    area = 0.25 * sum |cross of the XY-projected edges|.
    """
    v0, v1, v2 = tris[:, 0, :2], tris[:, 1, :2], tris[:, 2, :2]
    cross = ((v1[:, 0] - v0[:, 0]) * (v2[:, 1] - v0[:, 1])
             - (v1[:, 1] - v0[:, 1]) * (v2[:, 0] - v0[:, 0]))
    return 0.25 * float(np.sum(np.abs(cross)))


# --------------------------------------------------------------------------- #
# Point -> triangle distance (vectorised; Ericson, Real-Time Collision Det.)
# --------------------------------------------------------------------------- #
def _pt_tri_dist(p: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Distance from each point p[i] to triangle (a[i], b[i], c[i]).

    All inputs are (M, 3). Robust to degenerate (collapsed-to-segment)
    triangles, which the quasi-2D branch produces when it flattens side walls.
    """
    ab, ac = b - a, c - a
    ap = p - a
    d1 = np.einsum("ij,ij->i", ab, ap)
    d2 = np.einsum("ij,ij->i", ac, ap)
    bp = p - b
    d3 = np.einsum("ij,ij->i", ab, bp)
    d4 = np.einsum("ij,ij->i", ac, bp)
    cp = p - c
    d5 = np.einsum("ij,ij->i", ab, cp)
    d6 = np.einsum("ij,ij->i", ac, cp)

    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    denom = va + vb + vc
    denom_s = np.where(np.abs(denom) < 1e-30, 1.0, denom)

    # face interior (default)
    v = vb / denom_s
    w = vc / denom_s
    Q = a + v[:, None] * ab + w[:, None] * ac

    def _seg(t, p0, d):                     # clamped point on segment p0 + t*d
        t = np.clip(t, 0.0, 1.0)
        return p0 + t[:, None] * d

    # Override in reverse priority so vertex regions win over edges over face.
    den_bc = (d4 - d3) + (d5 - d6)
    t_bc = np.where(np.abs(den_bc) < 1e-30, 0.0,
                    (d4 - d3) / np.where(np.abs(den_bc) < 1e-30, 1.0, den_bc))
    m_bc = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    Q = np.where(m_bc[:, None], _seg(t_bc, b, c - b), Q)

    den_ac = d2 - d6
    t_ac = np.where(np.abs(den_ac) < 1e-30, 0.0,
                    d2 / np.where(np.abs(den_ac) < 1e-30, 1.0, den_ac))
    m_ac = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    Q = np.where(m_ac[:, None], _seg(t_ac, a, ac), Q)

    den_ab = d1 - d3
    t_ab = np.where(np.abs(den_ab) < 1e-30, 0.0,
                    d1 / np.where(np.abs(den_ab) < 1e-30, 1.0, den_ab))
    m_ab = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    Q = np.where(m_ab[:, None], _seg(t_ab, a, ab), Q)

    Q = np.where(((d6 >= 0) & (d5 <= d6))[:, None], c, Q)   # vertex C
    Q = np.where(((d3 >= 0) & (d4 <= d3))[:, None], b, Q)   # vertex B
    Q = np.where(((d1 <= 0) & (d2 <= 0))[:, None], a, Q)    # vertex A
    return np.linalg.norm(p - Q, axis=1)


def _dirA_distances(pts: np.ndarray, tris: np.ndarray, k: int = _K_CANDIDATES) -> np.ndarray:
    """Min distance from each point to the triangle set (point -> surface)."""
    P, T = len(pts), len(tris)
    if P == 0 or T == 0:
        return np.zeros(P)
    a_all, b_all, c_all = tris[:, 0], tris[:, 1], tris[:, 2]

    KDTree = _get_kdtree()
    if KDTree is not None and T > k:
        # Index each triangle by its centroid AND its three vertices, all tagged
        # with the triangle they belong to. A large triangle has a distant
        # centroid, so a centroid-only tree can miss it for a query point near one
        # of its corners/edges (and then report a too-large deviation); including
        # the vertices makes the nearest-triangle search robust on non-uniform
        # meshes (big side walls + small caps, exactly what the extruder emits).
        cent = (a_all + b_all + c_all) / 3.0
        reps = np.vstack((cent, a_all, b_all, c_all))
        tri_of = np.tile(np.arange(T), 4)
        tree = KDTree(reps)
        out = np.empty(P)
        for s in range(0, P, 20000):        # chunk to bound the gather size
            pc = pts[s:s + 20000]
            _, idx = tree.query(pc, k=k)
            if idx.ndim == 1:
                idx = idx[:, None]
            cand = tri_of[idx.ravel()]      # candidate triangle per (point, rep)
            p = np.repeat(pc, idx.shape[1], axis=0)
            d = _pt_tri_dist(p, a_all[cand], b_all[cand], c_all[cand])
            out[s:s + len(pc)] = d.reshape(len(pc), idx.shape[1]).min(axis=1)
        return out

    # Exact brute force, double-chunked to keep memory bounded.
    out = np.full(P, np.inf)
    for ps in range(0, P, 512):
        pc = pts[ps:ps + 512]
        best = np.full(len(pc), np.inf)
        for ts in range(0, T, 4096):
            av, bv, cv = a_all[ts:ts + 4096], b_all[ts:ts + 4096], c_all[ts:ts + 4096]
            t = len(av)
            p = np.repeat(pc, t, axis=0)
            d = _pt_tri_dist(p, np.tile(av, (len(pc), 1)),
                             np.tile(bv, (len(pc), 1)), np.tile(cv, (len(pc), 1)))
            best = np.minimum(best, d.reshape(len(pc), t).min(axis=1))
        out[ps:ps + len(pc)] = best
    return out


def _nearest_point_dist(query: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Distance from each query point to the nearest reference point."""
    if len(query) == 0 or len(ref) == 0:
        return np.zeros(len(query))
    KDTree = _get_kdtree()
    if KDTree is not None:
        d, _ = KDTree(ref).query(query, k=1)
        return d
    out = np.empty(len(query))
    for s in range(0, len(query), 1024):
        q = query[s:s + 1024]
        d = np.linalg.norm(q[:, None, :] - ref[None, :, :], axis=2)
        out[s:s + len(q)] = d.min(axis=1)
    return out


# --------------------------------------------------------------------------- #
# Interface (reconstructed boundary) extraction
# --------------------------------------------------------------------------- #
def _interface_points(solid_flat: np.ndarray, nx: int, ny: int, nz: int,
                      pts: np.ndarray) -> np.ndarray:
    """Grid coords of solid cells with at least one fluid face-neighbour.

    Tecplot POINT order is i fastest, then j, then k, so the flat field
    reshapes to [k, j, i].
    """
    g = solid_flat.reshape(nz, ny, nx)
    fluid = ~g
    inter = np.zeros_like(g)
    inter[:, :, :-1] |= g[:, :, :-1] & fluid[:, :, 1:]
    inter[:, :, 1:] |= g[:, :, 1:] & fluid[:, :, :-1]
    inter[:, :-1, :] |= g[:, :-1, :] & fluid[:, 1:, :]
    inter[:, 1:, :] |= g[:, 1:, :] & fluid[:, :-1, :]
    if nz > 1:
        inter[:-1, :, :] |= g[:-1, :, :] & fluid[1:, :, :]
        inter[1:, :, :] |= g[1:, :, :] & fluid[:-1, :, :]
    return pts[inter.reshape(-1)]


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def compute_fit_metrics(tris: np.ndarray, pts: np.ndarray, phi: np.ndarray,
                        nx: int, ny: int, nz: int,
                        dx: float, dy: float, dz: float) -> dict:
    """Volume/area + surface-deviation agreement between the STL and phi.

    Returns a dict of scalar metrics plus ``dev_points`` / ``dev_values`` (the
    interface points and their point->STL deviation) for the canvas heatmap. On
    a degenerate input (all-solid / all-fluid / no interface) the dict carries
    an ``error`` key and no metrics.
    """
    tris = np.asarray(tris, dtype=np.float64)
    pts = np.asarray(pts, dtype=np.float64)
    phi = np.asarray(phi, dtype=np.float64)

    solid = phi > 0.5
    n, n_solid = int(len(phi)), int(solid.sum())
    if nx * ny * nz != n:
        return {"error": f"grid {nx}×{ny}×{nz} ({nx * ny * nz} pts) does not match "
                         f"the phi field ({n} pts)"}
    quasi2d = (nz <= 2) or (dz <= 0.0)
    if quasi2d:
        h = float(np.sqrt(max(dx, 1e-300) * max(dy, 1e-300)))
    else:
        h = float((max(dx, 1e-300) * max(dy, 1e-300) * max(dz, 1e-300)) ** (1.0 / 3.0))

    res: dict = {"quasi2d": quasi2d, "h": h, "n": n, "n_solid": n_solid,
                 "dx": dx, "dy": dy, "dz": dz}
    if n_solid == 0 or n_solid == n:
        res["error"] = "the domain is entirely fluid or entirely solid (no interface)"
        return res

    # Triangle geometry, computed once: the raw cross product gives both the area
    # weighting and the |normal_z| used to tell caps (|nz|≈1) from walls (|nz|≈0).
    raw = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    twoA = np.linalg.norm(raw, axis=1)            # 2 × triangle area
    total_area = float(twoA.sum())
    nz_abs = np.abs(raw[:, 2]) / np.where(twoA < 1e-300, 1.0, twoA)

    # A vertical extrusion has only horizontal caps and vertical walls; a sphere /
    # tilted / curved STL has a large *area* of intermediate-tilt facets. The XY
    # footprint identity (and the cap-dropping in the in-plane deviation below)
    # only holds for a vertical extrusion, so detect it and, when violated, skip
    # the area agreement rather than report a meaningless number.
    tilted = (nz_abs > 0.1) & (nz_abs < 0.9)
    tilted_frac = float(twoA[tilted].sum() / total_area) if total_area > 0 else 1.0
    is_extruded = tilted_frac < 0.05
    res["extruded"] = is_extruded

    # 1) Volume (3D) or footprint area (quasi-2D).
    if quasi2d:
        if is_extruded:
            # Cross-section area from the fullest z-layer rather than averaging the
            # solid-point count over nz: averaging underestimates the footprint when
            # the slab does not span every z-layer (padded z-range, caps between grid
            # levels). xy_footprint_area assumes a vertical extrusion (horizontal
            # end caps) — the documented immersed-solid input.
            layer_cells = solid.reshape(nz, -1).sum(axis=1) if nz > 0 else np.array([n_solid])
            a_phi = float(layer_cells.max()) * dx * dy
            a_stl = xy_footprint_area(tris)
            res.update(mode="area", v_phi=a_phi, v_stl=a_stl,
                       v_rel=((a_phi - a_stl) / a_stl if a_stl > 0 else float("nan")))
        else:
            # Not a vertical extrusion: the XY footprint double-count identity does
            # not hold, so the area Δ would be misleading. Report it as n/a.
            res.update(mode="area", v_phi=float("nan"), v_stl=float("nan"),
                       v_rel=float("nan"),
                       note="area agreement skipped — STL is not a vertical extrusion")
    else:
        # signed_volume is the divergence theorem: valid for any closed, well-wound
        # surface (not only extrusions), so the 3D volume check stands as-is.
        v_phi = n_solid * dx * dy * dz
        v_stl = abs(signed_volume(tris))
        res.update(mode="volume", v_phi=v_phi, v_stl=v_stl,
                   v_rel=((v_phi - v_stl) / v_stl if v_stl > 0 else float("nan")))

    # 2) Surface deviation.
    ipts = _interface_points(solid, nx, ny, nz, pts)
    res["n_interface"] = int(len(ipts))
    if len(ipts) == 0:
        res["error"] = "no interface cells were found"
        return res

    side = nz_abs < 0.5
    if quasi2d and is_extruded and int(side.sum()) >= 1:
        # Vertical extrusion in a quasi-2D grid: drop near-horizontal cap triangles
        # and collapse to XY so the slab end-caps do not contribute; distances
        # become in-plane deviations.
        wtris = tris[side].copy()
        wtris[:, :, 2] = 0.0
        wpts = ipts.copy()
        wpts[:, 2] = 0.0
    else:
        # Full 3D (or a non-extruded / cap-only STL): measure the true
        # point-to-surface distance. Flattening a cap-only STL onto z=0 would put
        # every interface point inside a cap polygon and fake a ~0 deviation.
        wtris, wpts = tris, ipts

    devA = _dirA_distances(wpts, wtris)             # interface -> STL surface
    # Reverse direction uses STL vertices; deduplicate first so shared vertices
    # are not queried multiple times (a coarse mesh shares each vertex ~6 ways).
    stl_verts = np.unique(wtris.reshape(-1, 3), axis=0)
    devB = _nearest_point_dist(stl_verts, wpts)    # STL verts -> interface

    res.update(
        meanA=float(devA.mean()),
        rmsA=float(np.sqrt(np.mean(devA ** 2))),
        maxA=float(devA.max()),
        dev_points=ipts,        # original 3D coords (for rendering)
        dev_values=devA,
    )
    # Symmetric Hausdorff = max over both directions (the reverse max has no other
    # consumer, so it is folded in here rather than stored separately).
    res["hausdorff"] = max(res["maxA"], float(devB.max()) if len(devB) else 0.0)
    return res
