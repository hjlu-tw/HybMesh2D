import sys
import os
from PyQt6.QtWidgets import QApplication, QSpinBox, QDoubleSpinBox

# Disable scroll wheel value changes on numerical spin boxes
QSpinBox.wheelEvent = lambda self, event: event.ignore()
QDoubleSpinBox.wheelEvent = lambda self, event: event.ignore()

from app.controller import AppController

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
    
    import pyqtgraph as pg
    pg.setConfigOption('background', '#0c0d16')
    pg.setConfigOption('foreground', '#a0a8c0')
    
    controller = AppController()
    
    # Load any geometry files provided as command line arguments.
    # Multiple files may be passed; each opens in its own geometry layer/tab.
    file_paths = []
    for arg in sys.argv[1:]:
        if os.path.exists(arg):
            file_paths.append(arg)
        else:
            print(f"Warning: File not found: {arg}")
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
