import sys
import os
from PyQt6.QtWidgets import QApplication
from app.controller import AppController

def main():
    app = QApplication(sys.argv)
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
