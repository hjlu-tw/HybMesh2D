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
    
    # Check if a file path is provided as a command line argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            # Load the file automatically after showing the window
            # Use QTimer.singleShot to ensure the UI is fully rendered before loading
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, lambda: controller.load_geometry_from_path(file_path))
        else:
            print(f"Warning: File not found: {file_path}")

    controller.show_main_window()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
