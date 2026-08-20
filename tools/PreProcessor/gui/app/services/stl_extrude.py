"""Extrude 2D profile loops into a watertight 3D STL (immersed-solid Q2 path).

The 2D CAD canvas already authors closed profile loops; for an immersed solid
the STL3d preprocessor needs a closed 3D surface. This module turns each loop
into a prism (triangulated top + bottom caps + side walls) and writes a binary
STL — no external CAD or extra dependency required.

The caps matter: STL3d marks cells by shooting rays parallel to z, so a vertical
ray must cross the bottom cap once and the top cap once. The caps are therefore
triangulated with an ear-clipping tessellation (valid for non-convex simple
polygons), not a fan (which is only correct for convex shapes).

Limitations: each loop becomes a separate solid body; holes (a loop meant as a
void inside another) are not subtracted. Self-intersecting profiles are not
supported.
"""
from __future__ import annotations

import struct
import numpy as np

from app.services.stl_loader import _BIN_TRI_DTYPE, triangle_normals


# --------------------------------------------------------------------------- #
# Polygon helpers
# --------------------------------------------------------------------------- #
def _signed_area(poly: np.ndarray) -> float:
    """Signed area of a 2D polygon (positive => counter-clockwise)."""
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def _clean_loop(poly: np.ndarray, tol: float = 1e-12) -> np.ndarray:
    """Drop a repeated closing vertex and consecutive duplicate points."""
    poly = np.asarray(poly, dtype=np.float64)[:, :2]
    if len(poly) > 1 and np.allclose(poly[0], poly[-1]):
        poly = poly[:-1]
    if len(poly) < 3:
        return poly
    keep = [0]
    for i in range(1, len(poly)):
        if not np.allclose(poly[i], poly[keep[-1]], atol=tol):
            keep.append(i)
    poly = poly[keep]
    if len(poly) > 1 and np.allclose(poly[0], poly[-1], atol=tol):
        poly = poly[:-1]
    return poly


def _pts_in_tri(P: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Barycentric containment test of points P (M,2) in triangle a,b,c."""
    v0, v1, v2 = c - a, b - a, P - a
    d00 = v0 @ v0
    d01 = v0 @ v1
    d11 = v1 @ v1
    d02 = v2 @ v0
    d12 = v2 @ v1
    inv = 1.0 / (d00 * d11 - d01 * d01 + 1e-30)
    u = (d11 * d02 - d01 * d12) * inv
    v = (d00 * d12 - d01 * d02) * inv
    return (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1.0 + 1e-9)


def triangulate_polygon_2d(poly: np.ndarray) -> np.ndarray:
    """Ear-clipping triangulation of a simple polygon -> (K, 3) vertex indices.

    Indices wind counter-clockwise. Robust to collinear vertices (dropped without
    emitting a degenerate facet) and ~O(N^2): each pass recomputes the reflex set
    once via a vectorised cross-product and tests ear containment only against
    reflex vertices (an ear can only ever be blocked by a reflex vertex), instead
    of rebuilding an all-vertices array per candidate.

    Returns an EMPTY array when the polygon cannot be fully triangulated
    (self-intersecting / non-simple), so the caller fails loudly rather than
    writing a cap with holes — a partial cap would silently produce a
    non-watertight STL that STL3d then mis-marks.
    """
    poly = np.asarray(poly, dtype=np.float64)
    n = len(poly)
    if n < 3:
        return np.empty((0, 3), dtype=int)
    idx = list(range(n))
    if _signed_area(poly) < 0:               # work on a CCW copy
        idx.reverse()

    tris: list[tuple[int, int, int]] = []
    while len(idx) > 3:
        m = len(idx)
        ring = poly[idx]                     # current polygon in order
        prevv = np.roll(ring, 1, axis=0)
        nextv = np.roll(ring, -1, axis=0)
        cross = ((ring[:, 0] - prevv[:, 0]) * (nextv[:, 1] - prevv[:, 1])
                 - (ring[:, 1] - prevv[:, 1]) * (nextv[:, 0] - prevv[:, 0]))
        # Reflex indices + their coords, gathered once per pass: an ear can only be
        # blocked by a reflex vertex, so each candidate is tested against this set
        # (excluding the candidate's own 3 vertices) without rebuilding a list or
        # re-indexing ``poly`` per candidate.
        reflex_idx = np.array([idx[t] for t in range(m) if cross[t] < -1e-14], dtype=int)
        reflex_pts = poly[reflex_idx] if len(reflex_idx) else None

        clipped = False
        for k in range(m):
            ck = cross[k]
            if ck < -1e-14:                  # reflex vertex: never an ear tip
                continue
            i0, i1, i2 = idx[(k - 1) % m], idx[k], idx[(k + 1) % m]
            if ck <= 1e-14:                  # collinear tip: drop it, emit nothing
                idx.pop(k)
                clipped = True
                break
            a, b, c = poly[i0], poly[i1], poly[i2]
            if reflex_pts is not None:
                keep = (reflex_idx != i0) & (reflex_idx != i1) & (reflex_idx != i2)
                if keep.any() and _pts_in_tri(reflex_pts[keep], a, b, c).any():
                    continue                 # a reflex vertex sits inside -> not an ear
            tris.append((i0, i1, i2))
            idx.pop(k)
            clipped = True
            break
        if not clipped:                      # no ear and no collinear tip -> non-simple
            return np.empty((0, 3), dtype=int)

    # Final triangle (skip if the last three are collinear / zero-area).
    a, b, c = poly[idx[0]], poly[idx[1]], poly[idx[2]]
    cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if abs(cross) > 1e-14:
        tris.append((idx[0], idx[1], idx[2]))
    return np.array(tris, dtype=int) if tris else np.empty((0, 3), dtype=int)


# --------------------------------------------------------------------------- #
# Extrusion
# --------------------------------------------------------------------------- #
def extrude_loop(poly: np.ndarray, z0: float, z1: float) -> np.ndarray:
    """Extrude one closed 2D loop into a prism -> (M,3,3) triangle vertices."""
    poly = _clean_loop(poly)
    if len(poly) < 3:
        return np.empty((0, 3, 3), dtype=np.float64)
    if _signed_area(poly) < 0:               # canonical CCW (interior on left)
        poly = poly[::-1]
    n = len(poly)
    cap = triangulate_polygon_2d(poly)       # CCW indices
    if len(cap) == 0:
        return np.empty((0, 3, 3), dtype=np.float64)

    tris: list = []
    # Bottom cap (normal -z): reverse winding of the CCW cap.
    for i, j, k in cap:
        tris.append([[poly[i, 0], poly[i, 1], z0],
                     [poly[k, 0], poly[k, 1], z0],
                     [poly[j, 0], poly[j, 1], z0]])
    # Top cap (normal +z): keep CCW winding.
    for i, j, k in cap:
        tris.append([[poly[i, 0], poly[i, 1], z1],
                     [poly[j, 0], poly[j, 1], z1],
                     [poly[k, 0], poly[k, 1], z1]])
    # Side walls: for a CCW loop the outward normal is to the right of b->c.
    for i in range(n):
        bx, by = poly[i]
        cx, cy = poly[(i + 1) % n]
        b0 = [bx, by, z0]
        c0 = [cx, cy, z0]
        c1 = [cx, cy, z1]
        b1 = [bx, by, z1]
        tris.append([b0, c0, c1])
        tris.append([b0, c1, b1])
    return np.array(tris, dtype=np.float64)


def flat_sheet_loop(poly: np.ndarray, z: float = 0.0) -> np.ndarray:
    """Triangulate one closed 2D loop into a flat sheet at height ``z``.

    Unlike :func:`extrude_loop` this emits ONE cap only — no second cap, no side
    walls — i.e. the filled profile as a planar z=const lamina. That is the
    quasi-2D immersed-solid input (cf. a 2D airfoil STL): STL3d ray-traces a flat
    sheet the same way it does an extruded slab's cap, so the project's 2D solver
    can mark phi without a (here unnecessary) z-extrusion. Returns (M,3,3)
    triangle vertices; empty if the loop cannot be triangulated.
    """
    poly = _clean_loop(poly)
    if len(poly) < 3:
        return np.empty((0, 3, 3), dtype=np.float64)
    if _signed_area(poly) < 0:               # canonical CCW
        poly = poly[::-1]
    cap = triangulate_polygon_2d(poly)       # CCW indices
    if len(cap) == 0:
        return np.empty((0, 3, 3), dtype=np.float64)
    # Single cap with a -z normal (reversed CCW winding), matching the facet
    # orientation of a 2D profile exported as a planar STL.
    tris = [[[poly[i, 0], poly[i, 1], z],
             [poly[k, 0], poly[k, 1], z],
             [poly[j, 0], poly[j, 1], z]] for i, j, k in cap]
    return np.array(tris, dtype=np.float64)


def write_binary_stl(path: str, tris: np.ndarray,
                     header: bytes = b"HybMesh extruded profile") -> None:
    """Write an (M,3,3) triangle array as a binary STL with computed normals."""
    tris = np.asarray(tris, dtype=np.float64)
    n = len(tris)
    recs = np.zeros(n, dtype=_BIN_TRI_DTYPE)
    recs["normal"] = triangle_normals(tris).astype(np.float32)
    recs["v"] = tris.astype(np.float32)
    recs["attr"] = 0
    with open(path, "wb") as f:
        f.write(header[:80].ljust(80, b"\0"))
        f.write(struct.pack("<I", n))
        f.write(recs.tobytes())


def write_ascii_stl(path: str, tris: np.ndarray, name: str = "hybmesh_profile") -> None:
    """Write an (M,3,3) triangle array as an ASCII STL (same layout as the
    reference ``naca0012.stl``: ``solid`` … ``facet normal`` / ``outer loop`` /
    three ``vertex`` lines / ``endloop`` / ``endfacet`` … ``endsolid``).

    ASCII is the format the STL3d preprocessor reads most robustly, and it is
    human-readable for debugging. Normals are computed per facet.
    """
    tris = np.asarray(tris, dtype=np.float64)
    normals = triangle_normals(tris)
    out = [f"solid {name}"]
    for tri, nrm in zip(tris, normals):
        out.append(f"facet normal {nrm[0]:.6e} {nrm[1]:.6e} {nrm[2]:.6e}")
        out.append("  outer loop")
        for v in tri:
            out.append(f"    vertex {v[0]:.6e} {v[1]:.6e} {v[2]:.6e}")
        out.append("  endloop")
        out.append("endfacet")
    out.append(f"endsolid {name}")
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
