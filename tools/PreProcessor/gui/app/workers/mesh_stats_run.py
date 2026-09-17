from __future__ import annotations
from PyQt6.QtCore import QThread, pyqtSignal


class MeshStatsWorker(QThread):
    """Computes the O(cells) mesh skewness metric off the UI thread.

    The mesh is read-only here — a new mesh is always a fresh object, so the
    worker keeps operating on its own (possibly superseded) snapshot; the panel
    discards stale results by generation token.

    It stopped computing ASPECT RATIO with #131: the panel's shape summary is
    read from the mesher's provenance sidecar, and the client-side per-cell
    array survives only as the canvas colour map's input, which builds it where
    it draws (``views/mesh_canvas_fills_mixin.py``). Computing it here as well
    would be a second pass over every cell for a number nothing displays.
    """

    # (generation, {"sk": (min,max,mean), "error": str})
    done = pyqtSignal(int, dict)

    def __init__(self, mesh, generation: int):
        super().__init__()
        self._mesh = mesh
        self._gen = generation

    def run(self):
        out: dict = {}
        try:
            sk = self._mesh.get_element_skewness()
            if len(sk):
                out["sk"] = (float(sk.min()), float(sk.max()), float(sk.mean()))
        except Exception as e:  # pragma: no cover - defensive against bad data
            out["error"] = str(e)
        self.done.emit(self._gen, out)
