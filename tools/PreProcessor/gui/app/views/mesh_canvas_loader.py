from __future__ import annotations
from PyQt6.QtCore import QThread, pyqtSignal


class GeomLoaderThread(QThread):
    """Loads multiple geometry files in a background thread to prevent UI freezing."""
    loaded_signal = pyqtSignal(int, list)  # (generation token, results)

    def __init__(self, geom_files: list[str], token: int = 0):
        super().__init__()
        self.geom_files = geom_files
        self.token = token

    def run(self):
        import os
        from app.services.geometry_service import load_points_dat
        results = []
        for f in self.geom_files:
            if not f or not os.path.exists(f):
                continue
            try:
                # Validated loader: reject NaN/Inf and non-(N,2) shapes with a
                # clear, file-named error instead of feeding garbage into the
                # preview (or, worse, silently past it).
                pts = load_points_dat(f)
                results.append(pts)
            except Exception as e:
                print(f"[preview] skipping malformed geometry '{f}': {e}")
        self.loaded_signal.emit(self.token, results)
