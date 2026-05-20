from PyQt6.QtWidgets import QMainWindow, QDockWidget, QSplitter
from PyQt6.QtCore import Qt
from app.views.canvas import CanvasView
from app.views.sidebar import SidebarView
from app.views.log_panel import LogPanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HybMesh PreProcessor")
        self.resize(1200, 800) # Slightly larger default window

        # Create main views
        self.canvas_view = CanvasView()
        self.sidebar_view = SidebarView()
        
        # Fix the sidebar width to prevent jumping when dynamic forms appear
        self.sidebar_view.setFixedWidth(300)

        self.log_panel = LogPanel()

        # Center widget: Splitter containing sidebar and canvas
        # Since sidebar has a fixed width, the splitter is less necessary for resizing it,
        # but it still holds them together nicely.
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar_view)
        splitter.addWidget(self.canvas_view)
        
        # Disable collapsing the sidebar completely to avoid weird UI states
        splitter.setCollapsible(0, False)

        self.setCentralWidget(splitter)

        # Bottom Dock for Log Panel
        log_dock = QDockWidget("Log Console", self)
        log_dock.setWidget(self.log_panel)
        log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
