from __future__ import annotations
from PyQt6.QtCore import QThread, pyqtSignal

from app.services.geom_path_identity import canonical_geom_path


class GeomLoaderThread(QThread):
    """Loads multiple geometry files in a background thread to prevent UI freezing."""
    loaded_signal = pyqtSignal(int, list)  # (generation token, results)

    def __init__(self, geom_files: list[str], token: int = 0):
        super().__init__()
        # NOT `geom_files`: the identity gate forbids raw list constructs over an
        # attribute of that name outside the model's mixin, and it scans by NAME
        # because an AST cannot resolve the type of `self`. This thread holds a
        # plain list of paths to load, not MeshConfig's geometry list, so it says
        # so rather than being allow-listed into the one exemption.
        # `list(...)` rather than the argument itself: the caller's list used to be
        # aliased into a thread that reads it on another thread while the GUI is
        # free to edit it. Not a bug anyone hit, and copying is the cheap side.
        self.paths = list(geom_files)
        self.token = token

    def run(self):
        import os
        from app.services.geometry_service import load_points_dat
        results = []
        for f in self.paths:
            # A stored geometry entry is a spelling, resolved against the REPO
            # (services/geom_path_identity); reading it raw resolved a relative
            # entry against the process cwd and the preview silently vanished.
            f = canonical_geom_path(f)
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
