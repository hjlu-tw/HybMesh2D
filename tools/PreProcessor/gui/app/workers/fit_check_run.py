"""Background worker for the STL ↔ φ fit check.

``compute_fit_metrics`` does point-to-triangle distances over every interface
cell against every STL triangle (KD-tree, or an O(P·T) numpy fallback without
scipy). That is far too heavy to run on the GUI thread, so the controller hands
it to this QThread — mirroring the Stl3dWorker run path — and renders the result
in a finished callback.
"""
from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal


class FitCheckWorker(QThread):
    """Run ``compute_fit_metrics`` off the GUI thread and emit the result dict."""

    result_signal = pyqtSignal(object)       # metrics dict (may carry an "error")

    def __init__(self, tris: np.ndarray, pts: np.ndarray, phi: np.ndarray,
                 nx: int, ny: int, nz: int, dx: float, dy: float, dz: float):
        super().__init__()
        # Copy so the controller clearing its caches mid-run cannot pull the data
        # out from under the computation.
        self._tris = np.array(tris, dtype=np.float64)
        self._pts = np.array(pts, dtype=np.float64)
        self._phi = np.array(phi, dtype=np.float64)
        self._nx, self._ny, self._nz = int(nx), int(ny), int(nz)
        self._dx, self._dy, self._dz = float(dx), float(dy), float(dz)

    def run(self):
        try:
            from app.services.phi_quality import compute_fit_metrics
            m = compute_fit_metrics(
                self._tris, self._pts, self._phi,
                self._nx, self._ny, self._nz, self._dx, self._dy, self._dz)
        except Exception as e:               # surface, don't crash the GUI thread
            m = {"error": f"fit check failed: {e}"}
        self.result_signal.emit(m)
