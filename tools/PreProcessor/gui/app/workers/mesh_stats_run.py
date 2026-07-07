from __future__ import annotations
from PyQt6.QtCore import QThread, pyqtSignal


class MeshStatsWorker(QThread):
    """Computes the O(cells) mesh quality metrics (aspect ratio, skewness) off
    the UI thread. The mesh is read-only here — a new mesh is always a fresh
    object, so the worker keeps operating on its own (possibly superseded)
    snapshot; the panel discards stale results by generation token.
    """

    # (generation, {"ar": (min,max,mean), "sk": (min,max,mean), "error": str})
    done = pyqtSignal(int, dict)

    def __init__(self, mesh, generation: int):
        super().__init__()
        self._mesh = mesh
        self._gen = generation

    def run(self):
        out: dict = {}
        try:
            ar = self._mesh.get_element_aspect_ratios()
            if len(ar):
                out["ar"] = (float(ar.min()), float(ar.max()), float(ar.mean()))
            sk = self._mesh.get_element_skewness()
            if len(sk):
                out["sk"] = (float(sk.min()), float(sk.max()), float(sk.mean()))
        except Exception as e:  # pragma: no cover - defensive against bad data
            out["error"] = str(e)
        self.done.emit(self._gen, out)
