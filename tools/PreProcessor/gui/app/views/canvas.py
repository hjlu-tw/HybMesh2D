import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt

class CanvasView(QWidget):
    # Signal emitted when a point is clicked, passing the point index
    point_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Configure PyQtGraph globally
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setAspectLocked(True) # Keep 1:1 aspect ratio
        self.layout.addWidget(self.plot_widget)
        
        # Add a plot item for the lines
        self.curve = self.plot_widget.plot(pen=pg.mkPen('b', width=2), symbolBrush='b', symbolSize=3)
        
        # Add a scatter plot item for the split points (red markers)
        self.split_scatter = pg.ScatterPlotItem(size=10, pen=pg.mkPen(None), brush=pg.mkBrush('r'))
        self.plot_widget.addItem(self.split_scatter)
        
        # Add a scatter plot item for the selected point (green hollow circle)
        self.selected_scatter = pg.ScatterPlotItem(size=14, pen=pg.mkPen('g', width=2), brush=None)
        self.plot_widget.addItem(self.selected_scatter)
        
        # Add a plot item for the resampled output (magenta dashed line with dots)
        self.resampled_curve = self.plot_widget.plot(pen=pg.mkPen('m', width=2, style=Qt.PenStyle.DashLine), symbolBrush='m', symbolSize=5)
        
        # Add a plot item to highlight the active segment (thick orange line)
        self.active_segment_curve = self.plot_widget.plot(pen=pg.mkPen('#FF9800', width=4))

        self.points = None
        self.split_indices = []

        # Hook up mouse click event
        self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

    def load_data(self, points: np.ndarray):
        self.points = points
        # Update curve
        self.curve.setData(points[:, 0], points[:, 1])
        self.resampled_curve.setData([], []) # Clear previous results
        # Auto fit view
        self.plot_widget.autoRange()

    def load_resampled_data(self, points: np.ndarray):
        if points is not None:
            self.resampled_curve.setData(points[:, 0], points[:, 1])
        else:
            self.resampled_curve.setData([], [])

    def update_active_segment(self, start_idx, end_idx):
        if self.points is not None and start_idx is not None and end_idx is not None:
            if start_idx <= end_idx:
                seg_pts = self.points[start_idx:end_idx+1]
                self.active_segment_curve.setData(seg_pts[:, 0], seg_pts[:, 1])
        else:
            self.active_segment_curve.setData([], [])

    def update_split_points(self, indices):
        self.split_indices = indices
        if self.points is not None and len(indices) > 0:
            split_pts = self.points[indices]
            self.split_scatter.setData(split_pts[:, 0], split_pts[:, 1])
        else:
            self.split_scatter.clear()

    def update_selected_point(self, idx):
        if self.points is not None and idx is not None:
            pt = self.points[idx]
            self.selected_scatter.setData([pt[0]], [pt[1]])
        else:
            self.selected_scatter.clear()

    def _on_mouse_clicked(self, event):
        if self.points is None:
            return

        # Check if left button was clicked (handle both PyQt6 enum and int just in case)
        btn = event.button()
        if btn != Qt.MouseButton.LeftButton and btn != 1:
            return

        # Get mouse position in plot coordinates
        pos = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
        x, y = pos.x(), pos.y()

        # Find the nearest point index
        dists = np.sqrt((self.points[:, 0] - x)**2 + (self.points[:, 1] - y)**2)
        nearest_idx = np.argmin(dists)

        self.point_clicked.emit(int(nearest_idx))
