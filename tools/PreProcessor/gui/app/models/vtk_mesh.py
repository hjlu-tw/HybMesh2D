from __future__ import annotations
import os
import numpy as np

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

                # Group temp_cells into triangles/quads/polygons based on type
                for cell, c_type in zip(temp_cells, cell_types):
                    if c_type == 5 and len(cell) == 3:  # Triangle
                        mesh.triangles.append(tuple(cell))
                    elif c_type == 9 and len(cell) == 4:  # Quad
                        mesh.quads.append(tuple(cell))
                    else:
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

    def get_element_areas(self) -> np.ndarray:
        """Calculate and return area of each cell element."""
        areas = []
        
        # 1. Triangles
        for tri in self.triangles:
            p = self.points[list(tri)]
            # Shoelace formula for triangle
            area = 0.5 * abs(p[0, 0] * (p[1, 1] - p[2, 1]) + p[1, 0] * (p[2, 1] - p[0, 1]) + p[2, 0] * (p[0, 1] - p[1, 1]))
            areas.append(area)
            
        # 2. Quads
        for quad in self.quads:
            p = self.points[list(quad)]
            # Shoelace formula for 4-vertex polygon
            x = p[:, 0]
            y = p[:, 1]
            area = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
            areas.append(area)
            
        # 3. Polygons
        for poly in self.polygons:
            p = self.points[poly]
            x = p[:, 0]
            y = p[:, 1]
            area = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
            areas.append(area)

        return np.array(areas)

    def get_element_aspect_ratios(self) -> np.ndarray:
        """Calculate aspect ratios of each cell element.
        For a cell, aspect ratio is defined as (max edge length) / (min edge length).
        For triangles/quads, aspect ratio closer to 1 is better.
        """
        ratios = []

        # Helper to compute edge lengths of a polygon
        def poly_aspect_ratio(nodes):
            p = self.points[nodes]
            # Compute distances between consecutive vertices
            diffs = p - np.roll(p, 1, axis=0)
            lengths = np.hypot(diffs[:, 0], diffs[:, 1])
            max_len = np.max(lengths)
            min_len = np.min(lengths)
            return max_len / min_len if min_len > 1e-12 else 1e6

        for tri in self.triangles:
            ratios.append(poly_aspect_ratio(list(tri)))
        for quad in self.quads:
            ratios.append(poly_aspect_ratio(list(quad)))
        for poly in self.polygons:
            ratios.append(poly_aspect_ratio(poly))

        return np.array(ratios)
