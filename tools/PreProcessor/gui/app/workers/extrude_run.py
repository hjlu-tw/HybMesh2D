"""Background worker for 2D-profile → STL export (flat sheet or extruded prism).

``triangulate_polygon_2d`` (ear clipping) is O(N^2) and the imported profile can
be thousands of points, so triangulating + writing the binary STL on the GUI
thread freezes the window. This QThread mirrors the FitCheckWorker run path: the
controller gathers the loops and asks for the path on the GUI thread, then hands
the heavy work here and finishes (load hand-off) in a callback.
"""
from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal


class ExtrudeWorker(QThread):
    """Triangulate every loop and write the STL off the GUI thread."""

    result_signal = pyqtSignal(object)       # result dict (may carry an "error")

    def __init__(self, loops: list[np.ndarray], names: list[str],
                 z0: float, z1: float, path: str, flat: bool = False):
        super().__init__()
        # Copy so editing the canvas mid-run cannot mutate the data underneath.
        self._loops = [np.array(a, dtype=np.float64) for a in loops]
        self._names = list(names)
        self._z0, self._z1 = float(z0), float(z1)
        self._path = path
        self._flat = bool(flat)             # True = planar z=z0 sheet (2D), no walls

    def run(self):
        try:
            from app.services.stl_extrude import (
                extrude_loop, flat_sheet_loop, write_ascii_stl)
            parts, failed = [], []
            for arr, nm in zip(self._loops, self._names):
                t = (flat_sheet_loop(arr, self._z0) if self._flat
                     else extrude_loop(arr, self._z0, self._z1))
                if len(t):
                    parts.append(t)
                else:
                    failed.append(nm)
            if not parts:
                self.result_signal.emit({"error": "no_facets", "failed": failed})
                return
            tris = np.vstack(parts)
            # ASCII STL (same format as the reference naca0012.stl): the format the
            # STL3d preprocessor reads most robustly, and human-readable.
            name = "hybmesh_2d_profile" if self._flat else "hybmesh_extruded"
            write_ascii_stl(self._path, tris, name=name)
            self.result_signal.emit(
                {"path": self._path, "n_facets": int(len(tris)), "failed": failed})
        except Exception as e:                # surface, don't crash the GUI thread
            self.result_signal.emit({"error": f"extrude failed: {e}"})
