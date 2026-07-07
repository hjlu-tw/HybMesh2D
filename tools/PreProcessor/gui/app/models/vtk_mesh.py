from __future__ import annotations
import os
import numpy as np


# ── Vectorised cell metrics (operate on a (M, n, 2) block of M cells with n
#    vertices each, returning (M,)). Vertices go counter-/clockwise around the
#    cell; `roll(..., 1, axis=1)` therefore yields the previous vertex. ──────
def _cell_areas(cp: np.ndarray) -> np.ndarray:
    x = cp[..., 0]; y = cp[..., 1]
    return 0.5 * np.abs(np.sum(x * np.roll(y, 1, axis=1) - y * np.roll(x, 1, axis=1), axis=1))


def _cell_aspect_ratios(cp: np.ndarray) -> np.ndarray:
    d = cp - np.roll(cp, 1, axis=1)                 # edge vectors (M, n, 2)
    lengths = np.hypot(d[..., 0], d[..., 1])        # (M, n)
    mx = lengths.max(axis=1)
    mn = lengths.min(axis=1)
    safe = mn > 1e-12
    return np.where(safe, mx / np.where(safe, mn, 1.0), 1e6)


def _cell_skewness(cp: np.ndarray) -> np.ndarray:
    prev = np.roll(cp, 1, axis=1)
    nxt = np.roll(cp, -1, axis=1)
    v1 = prev - cp
    v2 = nxt - cp
    l1 = np.hypot(v1[..., 0], v1[..., 1])
    l2 = np.hypot(v2[..., 0], v2[..., 1])
    dot = v1[..., 0] * v2[..., 0] + v1[..., 1] * v2[..., 1]
    good = (l1 > 1e-12) & (l2 > 1e-12)              # degenerate edges -> angle 0
    cos = np.clip(np.divide(dot, l1 * l2, out=np.zeros_like(dot), where=good), -1.0, 1.0)
    angles = np.where(good, np.degrees(np.arccos(cos)), 0.0)   # (M, n) in degrees
    n = cp.shape[1]
    theta_e = (n - 2) * 180.0 / n
    theta_max = angles.max(axis=1)
    theta_min = angles.min(axis=1)
    skew_max = ((theta_max - theta_e) / (180.0 - theta_e)
                if (180.0 - theta_e) > 1e-12 else np.zeros_like(theta_max))
    skew_min = ((theta_e - theta_min) / theta_e
                if theta_e > 1e-12 else np.zeros_like(theta_min))
    return np.maximum(skew_max, skew_min)


class VTKMesh:
    """Parse and store a VTK Legacy ASCII unstructured grid."""

    def __init__(self):
        self.points: np.ndarray = np.empty((0, 2))  # Nx2
        self.triangles: list[tuple[int, int, int]] = []
        self.quads: list[tuple[int, int, int, int]] = []
        self.polygons: list[list[int]] = []

    @classmethod
    def from_file(cls, path: str) -> "VTKMesh":
        """Load and parse a VTK Legacy ASCII file from the given path."""
        mesh = cls()
        if not os.path.exists(path):
            raise FileNotFoundError(f"VTK file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Simple line-by-line parser state
        i = 0
        n_lines = len(lines)
        temp_cells = []

        while i < n_lines:
            line = lines[i].strip()
            if not line or line.startswith("#"):
                i += 1
                continue

            tokens = line.split()
            if not tokens:
                i += 1
                continue

            cmd = tokens[0].upper()

            if cmd == "POINTS":
                n_pts = int(tokens[1])
                pts = []
                i += 1
                # Read points coordinates
                pts_read = 0
                while pts_read < n_pts and i < n_lines:
                    pt_line = lines[i].strip()
                    if not pt_line or pt_line.startswith("#"):
                        i += 1
                        continue
                    pt_tokens = pt_line.split()
                    # A line can contain multiple points or one point (x, y, z)
                    # Typically, main.cpp writes one point per line: "x y 0.0"
                    for k in range(0, len(pt_tokens), 3):
                        if k + 1 < len(pt_tokens):
                            pts.append([float(pt_tokens[k]), float(pt_tokens[k+1])])
                            pts_read += 1
                    i += 1
                mesh.points = np.array(pts, dtype=np.float64)
                continue

            elif cmd == "CELLS":
                n_cells = int(tokens[1])
                temp_cells = []
                i += 1
                cells_read = 0
                while cells_read < n_cells and i < n_lines:
                    c_line = lines[i].strip()
                    if not c_line or c_line.startswith("#"):
                        i += 1
                        continue
                    c_tokens = c_line.split()
                    # A line contains: size id0 id1 id2 ...
                    # Typically, main.cpp writes one cell per line
                    idx = 0
                    while idx < len(c_tokens):
                        size = int(c_tokens[idx])
                        node_ids = [int(x) for x in c_tokens[idx+1 : idx+1+size]]
                        temp_cells.append(node_ids)
                        cells_read += 1
                        idx += 1 + size
                    i += 1
                continue

            elif cmd == "CELL_TYPES":
                n_types = int(tokens[1])
                cell_types = []
                i += 1
                types_read = 0
                while types_read < n_types and i < n_lines:
                    t_line = lines[i].strip()
                    if not t_line or t_line.startswith("#"):
                        i += 1
                        continue
                    t_tokens = t_line.split()
                    for tok in t_tokens:
                        cell_types.append(int(tok))
                        types_read += 1
                    i += 1

                # Group temp_cells into triangles/quads/polygons based on vertex count
                for cell, c_type in zip(temp_cells, cell_types):
                    if len(cell) == 3:  # Triangle
                        mesh.triangles.append(tuple(cell))
                    elif len(cell) == 4:  # Quad
                        mesh.quads.append(tuple(cell))
                    else:  # Polygon (5+ sides)
                        mesh.polygons.append(cell)
                continue

            i += 1

        return mesh

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Return the bounding box of the mesh: (xmin, xmax, ymin, ymax)."""
        if len(self.points) == 0:
            return (0.0, 0.0, 0.0, 0.0)
        xmin = np.min(self.points[:, 0])
        xmax = np.max(self.points[:, 0])
        ymin = np.min(self.points[:, 1])
        ymax = np.max(self.points[:, 1])
        return (xmin, xmax, ymin, ymax)

    # ── Vectorised per-cell metrics ──────────────────────────────────────
    # Each metric fans out over all triangles, then all quads, then all
    # polygons — the SAME order the fill renderer (`_rebuild_mesh_fills`) uses
    # to index the returned array, so ordering must be preserved. Triangles
    # and quads are the bulk and are computed as whole (M, n, 2) blocks; the
    # rare variable-length polygons fall back to a per-cell numpy call.

    def _assemble_metric(self, fn) -> np.ndarray:
        """Apply a vectorised (M, n, 2) -> (M,) metric to tris, quads and each
        polygon, concatenated in cell order."""
        P = self.points
        parts: list[np.ndarray] = []
        for cells in (self.triangles, self.quads):
            if cells:
                parts.append(fn(P[np.asarray(cells, dtype=np.int64)]))
        for poly in self.polygons:
            parts.append(fn(P[np.asarray(poly, dtype=np.int64)][None]))
        return np.concatenate(parts) if parts else np.array([], dtype=float)

    def get_element_areas(self) -> np.ndarray:
        """Area of each cell (shoelace formula)."""
        return self._assemble_metric(_cell_areas)

    def get_element_aspect_ratios(self) -> np.ndarray:
        """Aspect ratio (max edge length / min edge length) of each cell;
        closer to 1 is better. Degenerate (zero min edge) -> 1e6."""
        return self._assemble_metric(_cell_aspect_ratios)

    def get_element_skewness(self) -> np.ndarray:
        """Equiangle skewness of each cell: max((θmax-θe)/(180-θe),
        (θe-θmin)/θe), θe = (n-2)·180/n. 0 (perfect) .. 1 (degenerate)."""
        return self._assemble_metric(_cell_skewness)

