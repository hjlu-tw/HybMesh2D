import numpy as np
import os
from PyQt6.QtWidgets import QFileDialog
from app.views.main_window import MainWindow
from app.models.project import ProjectModel
from app.workers.backend_run import BackendWorker

class AppController:
    def __init__(self):
        self.main_window = MainWindow()
        self.project_model = ProjectModel()
        self.split_indices = []
        self.selected_point_idx = None
        self.current_segment_idx = -1

        # Connect signals
        self.main_window.sidebar_view.load_btn.clicked.connect(self.load_geometry)
        self.main_window.sidebar_view.split_btn.clicked.connect(self.add_split_point)
        self.main_window.sidebar_view.remove_split_btn.clicked.connect(self.remove_split_point)
        self.main_window.canvas_view.point_clicked.connect(self.handle_point_clicked)
        
        # Connect segment list and dynamic forms
        self.main_window.sidebar_view.segment_list.currentRowChanged.connect(self.handle_segment_selected)
        self.main_window.sidebar_view.strategy_combo.currentTextChanged.connect(self.handle_strategy_changed)
        
        # Connect input fields to model update
        sb = self.main_window.sidebar_view
        sb.uniform_n.valueChanged.connect(self.update_segment_params)
        sb.uniform_spacing.valueChanged.connect(self.update_segment_params)
        sb.uniform_type_combo.currentTextChanged.connect(self.update_segment_params)
        sb.tanh_n.valueChanged.connect(self.update_segment_params)
        sb.tanh_intensity.valueChanged.connect(self.update_segment_params)
        sb.cosine_n.valueChanged.connect(self.update_segment_params)
        sb.curv_n.valueChanged.connect(self.update_segment_params)
        sb.curv_sens.valueChanged.connect(self.update_segment_params)
        sb.geo_n.valueChanged.connect(self.update_segment_params)
        sb.geo_ratio.valueChanged.connect(self.update_segment_params)
        
        sb.is_closed_combo.currentTextChanged.connect(self.handle_is_closed_changed)
        sb.generate_btn.clicked.connect(self.generate_json)
        sb.run_btn.clicked.connect(self.run_backend)

    def show_main_window(self):
        self.main_window.show()

    def auto_detect_features(self, points, angle_threshold_deg=30.0):
        """Automatically detect sharp corners to use as split points."""
        indices = [0]
        n = len(points)
        threshold_rad = np.radians(angle_threshold_deg)
        
        for i in range(1, n - 1):
            v1 = points[i] - points[i-1]
            v2 = points[i+1] - points[i]
            
            n1 = np.linalg.norm(v1)
            n2 = np.linalg.norm(v2)
            
            if n1 == 0 or n2 == 0:
                continue
                
            v1_norm = v1 / n1
            v2_norm = v2 / n2
            
            dot = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)
            angle = np.arccos(dot)
            
            if angle > threshold_rad:
                indices.append(i)
                
        if (n - 1) not in indices:
            indices.append(n - 1)
            
        return indices
        
    def _sync_segments_to_view(self):
        self.project_model.update_segments_from_indices(self.split_indices)
        list_widget = self.main_window.sidebar_view.segment_list
        list_widget.clear()
        for i, seg in enumerate(self.project_model.segments):
            list_widget.addItem(f"Segment {seg.id}: Idx {seg.start_index} -> {seg.end_index}")
        
        self.main_window.sidebar_view.segment_props_group.setVisible(False)
        self.current_segment_idx = -1
        self.main_window.canvas_view.update_active_segment(None, None)

    def _apply_geometry_update(self):
        if not hasattr(self, 'original_points') or self.original_points is None:
            return
            
        points = self.original_points.copy()
        
        # If the user sets "is_closed" to True, logically connect the tail to the head
        if self.project_model.is_closed and len(points) > 0:
            if not np.allclose(points[0], points[-1]):
                points = np.vstack((points, points[0]))
        
        self.main_window.canvas_view.load_data(points)
        self.split_indices = self.auto_detect_features(points, angle_threshold_deg=30.0)
        self.main_window.canvas_view.update_split_points(self.split_indices)
        
        self.selected_point_idx = None
        self.main_window.canvas_view.update_selected_point(None)
        self.main_window.sidebar_view.selected_info.setText("Selected Point: None")
        self.main_window.sidebar_view.split_btn.setEnabled(False)
        self.main_window.sidebar_view.remove_split_btn.setEnabled(False)
        
        self._sync_segments_to_view()

    def load_geometry(self):
        default_dir = "examples/geometries"
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window, 
            "Open Geometry File", 
            default_dir, 
            "Data Files (*.dat)"
        )
        if file_path:
            self.load_geometry_from_path(file_path)

    def load_geometry_from_path(self, file_path):
        try:
            self.project_model.input_file = file_path
            self.project_model.output_file = file_path.replace(".dat", "_resampled.dat")
            self.original_points = np.loadtxt(file_path)
            
            # Update filename label
            filename = os.path.basename(file_path)
            self.main_window.sidebar_view.file_name_label.setText(f"File: {filename}")
            self.main_window.sidebar_view.file_name_label.setStyleSheet("color: black; font-weight: bold; margin-bottom: 5px;")
            
            self._apply_geometry_update()
            
            self.main_window.log_panel.log(f"Loaded {file_path} with {len(self.original_points)} points.")
            self.main_window.log_panel.log(f"Auto-detected {len(self.split_indices)-1} segments based on sharp corners.")
        except Exception as e:
            self.main_window.log_panel.log(f"Error loading file: {str(e)}")

    def handle_point_clicked(self, idx):
        self.selected_point_idx = idx
        self.main_window.canvas_view.update_selected_point(idx)
        self.main_window.sidebar_view.selected_info.setText(f"Selected Point: Index {idx}")
        
        if idx in self.split_indices:
            self.main_window.sidebar_view.split_btn.setEnabled(False)
            if idx not in [0, len(self.main_window.canvas_view.points) - 1]:
                self.main_window.sidebar_view.remove_split_btn.setEnabled(True)
            else:
                self.main_window.sidebar_view.remove_split_btn.setEnabled(False)
        else:
            self.main_window.sidebar_view.split_btn.setEnabled(True)
            self.main_window.sidebar_view.remove_split_btn.setEnabled(False)

    def add_split_point(self):
        if self.selected_point_idx is not None and self.selected_point_idx not in self.split_indices:
            self.split_indices.append(self.selected_point_idx)
            self.split_indices.sort()
            self.main_window.canvas_view.update_split_points(self.split_indices)
            self._sync_segments_to_view()
            self.main_window.log_panel.log(f"Manually added split point at index {self.selected_point_idx}.")
            self.handle_point_clicked(self.selected_point_idx)

    def remove_split_point(self):
        if self.selected_point_idx is not None and self.selected_point_idx in self.split_indices:
            self.split_indices.remove(self.selected_point_idx)
            self.main_window.canvas_view.update_split_points(self.split_indices)
            self._sync_segments_to_view()
            self.main_window.log_panel.log(f"Manually removed split point at index {self.selected_point_idx}.")
            self.handle_point_clicked(self.selected_point_idx)

    def handle_segment_selected(self, row):
        if row < 0:
            self.main_window.canvas_view.update_active_segment(None, None)
            return
        self.current_segment_idx = row
        seg = self.project_model.get_segment(row)
        if not seg:
            self.main_window.canvas_view.update_active_segment(None, None)
            return
        
        self.main_window.canvas_view.update_active_segment(seg.start_index, seg.end_index)
        
        sb = self.main_window.sidebar_view
        sb.segment_props_group.setVisible(True)
        
        sb.strategy_combo.blockSignals(True)
        sb.strategy_combo.setCurrentText(seg.strategy)
        sb.strategy_combo.blockSignals(False)
        
        sb.switch_param_form(seg.strategy)
        self._populate_form_from_model(seg)
        
    def handle_strategy_changed(self, strategy_name):
        if self.current_segment_idx < 0: return
        seg = self.project_model.get_segment(self.current_segment_idx)
        if seg:
            seg.update_strategy(strategy_name)
            self.main_window.sidebar_view.switch_param_form(strategy_name)
            self._populate_form_from_model(seg)
            self.main_window.log_panel.log(f"Segment {seg.id} strategy changed to {strategy_name}.")

    def _populate_form_from_model(self, seg):
        sb = self.main_window.sidebar_view
        def block_all(block):
            for widget in [sb.uniform_n, sb.tanh_n, sb.tanh_intensity, sb.cosine_n, 
                           sb.curv_n, sb.curv_sens, sb.geo_n, sb.geo_ratio]:
                widget.blockSignals(block)
        
        block_all(True)
        sb.uniform_type_combo.blockSignals(True)
        
        params = seg.parameters
        if seg.strategy == "uniform":
            if "spacing" in params:
                sb.uniform_type_combo.setCurrentText("Specify Spacing")
                sb.uniform_spacing.setValue(params["spacing"])
                sb._toggle_uniform_mode(True)
            else:
                sb.uniform_type_combo.setCurrentText("Specify Num Points")
                sb.uniform_n.setValue(params.get("n_points", 50))
                sb._toggle_uniform_mode(False)
        elif seg.strategy == "tanh":
            sb.tanh_n.setValue(params.get("n_points", 50))
            sb.tanh_intensity.setValue(params.get("intensity", 2.0))
        elif seg.strategy == "cosine":
            sb.cosine_n.setValue(params.get("n_points", 50))
        elif seg.strategy == "curvature":
            sb.curv_n.setValue(params.get("n_points", 50))
            sb.curv_sens.setValue(params.get("sensitivity", 1.5))
        elif seg.strategy == "geometric":
            sb.geo_n.setValue(params.get("n_points", 50))
            sb.geo_ratio.setValue(params.get("ratio", 1.2))
        block_all(False)
        sb.uniform_type_combo.blockSignals(False)

    def update_segment_params(self):
        if self.current_segment_idx < 0: return
        seg = self.project_model.get_segment(self.current_segment_idx)
        if not seg: return
        
        sb = self.main_window.sidebar_view
        if seg.strategy == "uniform":
            seg.parameters.clear() # Clear to ensure we don't mix n_points and spacing
            if sb.uniform_type_combo.currentText() == "Specify Spacing":
                seg.parameters["spacing"] = sb.uniform_spacing.value()
            else:
                seg.parameters["n_points"] = sb.uniform_n.value()
        elif seg.strategy == "tanh":
            seg.parameters["n_points"] = sb.tanh_n.value()
            seg.parameters["intensity"] = sb.tanh_intensity.value()
        elif seg.strategy == "cosine":
            seg.parameters["n_points"] = sb.cosine_n.value()
        elif seg.strategy == "curvature":
            seg.parameters["n_points"] = sb.curv_n.value()
            seg.parameters["sensitivity"] = sb.curv_sens.value()
        elif seg.strategy == "geometric":
            seg.parameters["n_points"] = sb.geo_n.value()
            seg.parameters["ratio"] = sb.geo_ratio.value()

    def handle_is_closed_changed(self, text):
        self.project_model.is_closed = (text == "True")
        self._apply_geometry_update()
        
    def generate_json(self):
        if not self.project_model.input_file:
            self.main_window.log_panel.log("Error: No geometry loaded.")
            return
        
        config_path = "gui_config.json"
        self.project_model.export_config(config_path)
        self.main_window.log_panel.log(f"Successfully generated configuration: {config_path}")

    def run_backend(self):
        if not self.project_model.input_file:
            self.main_window.log_panel.log("Error: No geometry loaded.")
            return
            
        config_path = "gui_config.json"
        self.project_model.export_config(config_path)
        
        # Determine executable path relative to the root project directory
        # The GUI is run from tools/PreProcessor/gui, so we need to go up to root
        # Or if the user runs `python main.py` inside `gui` directory, the relative path to build is `../../../build/surface_resampler`
        # Let's try to be smart about the path. 
        executable = "../../../build/surface_resampler"
        if not os.path.exists(executable):
            # Fallback if run from project root
            executable = "./build/surface_resampler"
            if not os.path.exists(executable):
                self.main_window.log_panel.log(f"Error: Executable not found. Please build the C++ project first.")
                return
            
        self.main_window.sidebar_view.run_btn.setEnabled(False)
        self.main_window.log_panel.log("--- Starting Backend ---")
        
        self.worker = BackendWorker(executable, config_path)
        self.worker.log_signal.connect(self.main_window.log_panel.log)
        self.worker.finished_signal.connect(self.handle_backend_finished)
        self.worker.start()

    def handle_backend_finished(self, return_code):
        self.main_window.sidebar_view.run_btn.setEnabled(True)
        if return_code == 0:
            self.main_window.log_panel.log("--- Backend Finished Successfully ---")
            out_file = self.project_model.output_file
            if os.path.exists(out_file):
                try:
                    resampled_pts = np.loadtxt(out_file)
                    self.main_window.canvas_view.load_resampled_data(resampled_pts)
                    self.main_window.log_panel.log(f"Loaded resampled result with {len(resampled_pts)} points.")
                except Exception as e:
                    self.main_window.log_panel.log(f"Error loading result: {str(e)}")
            else:
                self.main_window.log_panel.log(f"Error: Output file {out_file} not found.")
        else:
            self.main_window.log_panel.log(f"--- Backend Failed with code {return_code} ---")
