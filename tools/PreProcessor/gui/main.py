import sys
import os
from PyQt6.QtWidgets import QApplication, QSpinBox, QDoubleSpinBox

# Disable scroll wheel value changes on numerical spin boxes
QSpinBox.wheelEvent = lambda self, event: event.ignore()
QDoubleSpinBox.wheelEvent = lambda self, event: event.ignore()

from app.controller import AppController


def _resolve_listed_path(raw: str, list_dir: str) -> str:
    """Resolve a path read from a list file: try as given (cwd-relative or
    absolute) first, then relative to the list file's own directory."""
    if os.path.isabs(raw) or os.path.exists(raw):
        return raw
    candidate = os.path.join(list_dir, raw)
    return candidate if os.path.exists(candidate) else raw


def _read_list_file(path: str) -> list[str]:
    """Read a manifest of geometry paths, one per line. Blank lines and lines
    starting with '#' are ignored."""
    list_dir = os.path.dirname(os.path.abspath(path))
    paths = []
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                paths.append(_resolve_listed_path(line, list_dir))
    except OSError as e:
        print(f"Warning: Could not read list file '{path}': {e}")
    return paths


def collect_geometry_files(args: list[str]) -> list[str]:
    """Expand command-line args into geometry file paths.

    An argument is treated as a *list file* (a manifest of paths, one per line)
    when it starts with '@' or ends with '.txt' / '.list'; otherwise it is a
    geometry file path. This lets several files be opened at once via, e.g.,
    `main.py @geoms.txt` instead of listing every path on the command line.
    """
    file_paths = []
    for arg in args:
        is_list = arg.startswith("@") or arg.lower().endswith((".txt", ".list"))
        if is_list:
            list_path = arg[1:] if arg.startswith("@") else arg
            if not os.path.exists(list_path):
                print(f"Warning: List file not found: {list_path}")
                continue
            for fp in _read_list_file(list_path):
                if os.path.exists(fp):
                    file_paths.append(fp)
                else:
                    print(f"Warning: File not found (from {list_path}): {fp}")
        elif os.path.exists(arg):
            file_paths.append(arg)
        else:
            print(f"Warning: File not found: {arg}")
    return file_paths


def main():
    # Ensure default directories exist
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    for sub in [
        "config/preprocessor",
        "config/mesh",
        "results/resampled",
        "results/meshes"
    ]:
        os.makedirs(os.path.join(root_dir, sub), exist_ok=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Slightly smaller global font for a denser, industrial-style UI.
    from PyQt6.QtGui import QFont
    _f = app.font()
    _ps = _f.pointSizeF()
    if _ps > 0:
        _f.setPointSizeF(max(8.0, _ps - 1.5))
    else:
        _f.setPixelSize(max(10, _f.pixelSize() - 2))
    app.setFont(_f)
    
    import pyqtgraph as pg
    pg.setConfigOption('background', '#0c0d16')
    pg.setConfigOption('foreground', '#a0a8c0')
    
    controller = AppController()
    
    # Load any geometry files provided as command line arguments. Multiple
    # files may be passed directly, or via a list file (@list.txt / *.txt /
    # *.list) holding one path per line. Each file opens in its own tab.
    file_paths = collect_geometry_files(sys.argv[1:])
    if file_paths:
        # Use QTimer.singleShot to ensure the UI is fully rendered before loading.
        from PyQt6.QtCore import QTimer

        def load_all():
            for fp in file_paths:
                controller.load_geometry_from_path(fp)

        QTimer.singleShot(100, load_all)

    controller.show_main_window()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
