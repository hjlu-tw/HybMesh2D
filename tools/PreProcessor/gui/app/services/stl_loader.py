"""STL surface loader for 2D (z=0) planar geometry.

The HybMesh2D solver is strictly 2D, so only STL files whose triangles all
lie on the z = 0 plane are accepted.  The "surface points" of such a planar
triangulation are its boundary outline — the edges that belong to exactly one
triangle.  ``extract_planar_boundary_loops`` walks those edges into ordered
closed loops that can be used directly as geometry polylines.
"""
from __future__ import annotations
import os
import struct
import numpy as np

# Reject pathologically large STL files up front rather than reading gigabytes
# into memory and freezing/crashing the GUI.
MAX_STL_BYTES = 256 * 1024 * 1024  # 256 MB

# numpy view of one binary-STL triangle record: normal(3 f4) + 3 verts(3x3 f4)
# + 2-byte attribute. Used to parse the whole buffer in one vectorised call.
_BIN_TRI_DTYPE = np.dtype([
    ("normal", "<f4", (3,)),
    ("v", "<f4", (3, 3)),
    ("attr", "<u2"),
])


class STLPlanarError(ValueError):
    """Raised when an STL file is not a valid z=0 planar surface."""


def _is_binary_stl(data: bytes) -> bool:
    """Heuristically detect a binary STL via the exact size relationship.

    A binary STL is an 80-byte header + uint32 triangle count + N*50 bytes.
    ASCII files almost never satisfy this exact byte-count identity.
    """
    if len(data) < 84:
        return False
    n = struct.unpack("<I", data[80:84])[0]
    return len(data) == 84 + n * 50


def _parse_binary_stl(data: bytes) -> np.ndarray:
    n = struct.unpack("<I", data[80:84])[0]
    if len(data) < 84 + n * 50:
        raise STLPlanarError("Binary STL is truncated or its triangle count is corrupt.")
    # Vectorised parse: one frombuffer instead of a per-triangle Python loop.
    recs = np.frombuffer(data, dtype=_BIN_TRI_DTYPE, count=n, offset=84)
    return recs["v"].astype(np.float64)  # (n, 3, 3)


def _parse_ascii_stl(text: str) -> np.ndarray:
    verts: list[tuple[float, float, float]] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("vertex"):
            parts = s.split()
            if len(parts) >= 4:
                verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
    if len(verts) < 3:
        raise STLPlanarError("STL file contains no triangle vertices.")
    n_tris = len(verts) // 3
    arr = np.array(verts[:n_tris * 3], dtype=np.float64)
    return arr.reshape(n_tris, 3, 3)


def load_stl_triangles(path: str) -> np.ndarray:
    """Return an (N, 3, 3) array of triangle vertex coordinates (x, y, z)."""
    size = os.path.getsize(path)
    if size > MAX_STL_BYTES:
        raise STLPlanarError(
            f"STL file is too large ({size / (1024 * 1024):.0f} MB > "
            f"{MAX_STL_BYTES // (1024 * 1024)} MB limit)."
        )
    with open(path, "rb") as f:
        data = f.read()
    if _is_binary_stl(data):
        tris = _parse_binary_stl(data)
    else:
        # Strict decode: a binary blob misdetected as ASCII, or a genuinely
        # corrupt text file, should fail loudly rather than silently mangle
        # coordinates via error-replacement.
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise STLPlanarError(f"STL file is not valid UTF-8 text STL: {e}") from e
        tris = _parse_ascii_stl(text)
    if tris.shape[0] == 0:
        raise STLPlanarError("STL file contains no triangles.")
    return tris


def assert_planar_z0(tris: np.ndarray) -> None:
    """Raise STLPlanarError if any triangle vertex lies off the z=0 plane."""
    zs = tris[:, :, 2]
    xy = tris[:, :, :2]
    extent = float(np.max(xy) - np.min(xy)) if xy.size else 0.0
    tol = max(1e-6 * extent, 1e-9)
    max_z = float(np.max(np.abs(zs)))
    if max_z > tol:
        raise STLPlanarError(
            f"STL is not planar at z=0 (max |z| = {max_z:.6g} > tol {tol:.3g}). "
            "Only flat z=0 geometry is supported by this 2D solver."
        )


def extract_planar_boundary_loops(tris: np.ndarray,
                                  tol: float | None = None) -> list[np.ndarray]:
    """Extract ordered boundary outline loops from a planar triangulation.

    Boundary edges are those referenced by exactly one triangle.  They are
    chained into closed loops.  Returns a list of (M, 2) arrays, one per loop,
    sorted by perimeter (largest first).  The closing vertex is not repeated.
    """
    if tol is None:
        xy = tris[:, :, :2]
        extent = float(np.max(xy) - np.min(xy)) if xy.size else 1.0
        tol = max(1e-7 * extent, 1e-12)

    inv_tol = 1.0 / tol
    coords: list[tuple[float, float]] = []
    key_to_idx: dict[tuple[int, int], int] = {}

    def vid(x: float, y: float) -> int:
        key = (int(round(x * inv_tol)), int(round(y * inv_tol)))
        idx = key_to_idx.get(key)
        if idx is None:
            idx = len(coords)
            key_to_idx[key] = idx
            coords.append((x, y))
        return idx

    edge_count: dict[tuple[int, int], int] = {}
    for tri in tris:
        ids = [vid(float(tri[k, 0]), float(tri[k, 1])) for k in range(3)]
        for a, b in ((ids[0], ids[1]), (ids[1], ids[2]), (ids[2], ids[0])):
            if a == b:
                continue
            ekey = (a, b) if a < b else (b, a)
            edge_count[ekey] = edge_count.get(ekey, 0) + 1

    boundary = {e for e, c in edge_count.items() if c == 1}
    if not boundary:
        return []

    # Adjacency over boundary edges
    adj: dict[int, list[int]] = {}
    remaining = set(boundary)
    for a, b in boundary:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    loops: list[np.ndarray] = []
    while remaining:
        a, b = next(iter(remaining))
        remaining.discard((a, b))
        loop = [a, b]
        current, start = b, a
        while current != start:
            nxt = None
            for nb in adj.get(current, []):
                ekey = (current, nb) if current < nb else (nb, current)
                if ekey in remaining:
                    nxt = nb
                    remaining.discard(ekey)
                    break
            if nxt is None:
                break  # open chain (shouldn't happen for closed surfaces)
            loop.append(nxt)
            current = nxt
        # Drop the duplicated closing vertex if the loop closed
        if len(loop) > 1 and loop[0] == loop[-1]:
            loop = loop[:-1]
        if len(loop) >= 3:
            loops.append(np.array([coords[i] for i in loop], dtype=np.float64))

    def perimeter(pts: np.ndarray) -> float:
        closed = np.vstack([pts, pts[0]])
        return float(np.sum(np.linalg.norm(np.diff(closed, axis=0), axis=1)))

    loops.sort(key=perimeter, reverse=True)
    return loops


def load_planar_boundary_loops(path: str) -> list[np.ndarray]:
    """Full pipeline: parse STL, verify z=0, return ordered boundary loops."""
    tris = load_stl_triangles(path)
    assert_planar_z0(tris)
    loops = extract_planar_boundary_loops(tris)
    if not loops:
        raise STLPlanarError(
            "No boundary outline could be detected in the STL surface."
        )
    return loops
