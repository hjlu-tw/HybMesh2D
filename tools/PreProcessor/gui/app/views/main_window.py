from PyQt6.QtWidgets import QMainWindow, QDockWidget, QSplitter
from PyQt6.QtCore import Qt
from app.views.canvas import CanvasView
from app.views.sidebar import SidebarView
from app.views.log_panel import LogPanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HybMesh PreProcessor")
        self.resize(1024, 768)

        # Create main views
        self.canvas_view = CanvasView()
        self.sidebar_view = SidebarView()
        self.log_panel = LogPanel()

        # Center widget: Splitter containing sidebar and canvas
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar_view)
        splitter.addWidget(self.canvas_view)
        splitter.setSizes([250, 774]) # Initial sizes

        self.setCentralWidget(splitter)

        # Bottom Dock for Log Panel
        log_dock = QDockWidget("Log Console", self)
        log_dock.setWidget(self.log_panel)
        log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
