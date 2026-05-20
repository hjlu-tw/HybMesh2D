import sys
from PyQt6.QtWidgets import QApplication
from app.controller import AppController

def main():
    app = QApplication(sys.argv)
    controller = AppController()
    controller.show_main_window()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
