from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QListWidget, 
                             QStackedWidget, QFormLayout, QComboBox, QSpinBox, 
                             QDoubleSpinBox, QGroupBox)

class SidebarView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # --- File & Global Properties ---
        self.layout.addWidget(QLabel("<h2>Global Settings</h2>"))
        self.load_btn = QPushButton("Load Geometry (.dat)")
        self.layout.addWidget(self.load_btn)
        
        self.file_name_label = QLabel("No file loaded")
        self.file_name_label.setStyleSheet("color: gray; font-style: italic; margin-bottom: 5px;")
        self.layout.addWidget(self.file_name_label)
        
        global_form = QFormLayout()
        self.is_closed_combo = QComboBox()
        self.is_closed_combo.addItems(["True", "False"])
        global_form.addRow("Is Closed Loop:", self.is_closed_combo)
        self.layout.addLayout(global_form)
        
        # --- Selection & Split ---
        self.layout.addWidget(QLabel("<h2>Split Control</h2>"))
        self.selected_info = QLabel("Selected Point: None")
        self.selected_info.setStyleSheet("color: green; font-weight: bold;")
        self.layout.addWidget(self.selected_info)
        
        self.split_btn = QPushButton("Add Split Point")
        self.split_btn.setEnabled(False)
        self.layout.addWidget(self.split_btn)
        
        self.remove_split_btn = QPushButton("Remove Split Point")
        self.remove_split_btn.setEnabled(False)
        self.layout.addWidget(self.remove_split_btn)
        
        # --- Segments List ---
        self.layout.addWidget(QLabel("<h2>Segments</h2>"))
        self.segment_list = QListWidget()
        self.layout.addWidget(self.segment_list)
        
        # --- Segment Properties (Dynamic Form) ---
        self.segment_props_group = QGroupBox("Segment Properties")
        self.segment_props_layout = QVBoxLayout()
        self.segment_props_group.setLayout(self.segment_props_layout)
        
        strategy_form = QFormLayout()
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["uniform", "tanh", "cosine", "curvature", "geometric"])
        strategy_form.addRow("Strategy:", self.strategy_combo)
        self.segment_props_layout.addLayout(strategy_form)
        
        self.param_stack = QStackedWidget()
        self.segment_props_layout.addWidget(self.param_stack)
        
        # Create param forms for each strategy
        self._setup_param_forms()
        
        self.layout.addWidget(self.segment_props_group)
        self.segment_props_group.setVisible(False) # Hide until a segment is selected
        
        # Run Button & Generate JSON Button
        self.layout.addStretch()
        
        self.run_btn = QPushButton("Run C++ Backend")
        self.run_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.layout.addWidget(self.run_btn)
        
        self.generate_btn = QPushButton("Generate JSON Config")
        self.generate_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        self.layout.addWidget(self.generate_btn)
        
    def _setup_param_forms(self):
        # 1. Uniform
        uniform_widget = QWidget()
        uniform_layout = QFormLayout(uniform_widget)
        
        self.uniform_type_combo = QComboBox()
        self.uniform_type_combo.addItems(["Specify Num Points", "Specify Spacing"])
        uniform_layout.addRow("Mode:", self.uniform_type_combo)
        
        self.uniform_n = QSpinBox()
        self.uniform_n.setRange(2, 100000)
        self.uniform_n.setValue(50)
        uniform_layout.addRow("Num Points:", self.uniform_n)
        
        self.uniform_spacing = QDoubleSpinBox()
        self.uniform_spacing.setRange(0.00001, 10000.0)
        self.uniform_spacing.setValue(0.1)
        self.uniform_spacing.setDecimals(5)
        self.uniform_spacing.setSingleStep(0.01)
        
        uniform_layout.addRow("Spacing (ds):", self.uniform_spacing)
        
        self.uniform_spacing.setVisible(False) # Hidden by default
        self.uniform_spacing_label = uniform_layout.labelForField(self.uniform_spacing)
        if self.uniform_spacing_label:
            self.uniform_spacing_label.setVisible(False)
        
        # Connect mode toggle
        self.uniform_type_combo.currentTextChanged.connect(
            lambda text: self._toggle_uniform_mode(text == "Specify Spacing")
        )
        
        self.param_stack.addWidget(uniform_widget)
        
        # 2. Tanh
        tanh_widget = QWidget()
        tanh_layout = QFormLayout(tanh_widget)
        self.tanh_n = QSpinBox()
        self.tanh_n.setRange(2, 1000)
        self.tanh_n.setValue(50)
        self.tanh_intensity = QDoubleSpinBox()
        self.tanh_intensity.setRange(0.1, 10.0)
        self.tanh_intensity.setValue(2.0)
        self.tanh_intensity.setSingleStep(0.1)
        tanh_layout.addRow("Num Points:", self.tanh_n)
        tanh_layout.addRow("Intensity:", self.tanh_intensity)
        self.param_stack.addWidget(tanh_widget)
        
        # 3. Cosine
        cosine_widget = QWidget()
        cosine_layout = QFormLayout(cosine_widget)
        self.cosine_n = QSpinBox()
        self.cosine_n.setRange(2, 1000)
        self.cosine_n.setValue(50)
        cosine_layout.addRow("Num Points:", self.cosine_n)
        self.param_stack.addWidget(cosine_widget)
        
        # 4. Curvature
        curv_widget = QWidget()
        curv_layout = QFormLayout(curv_widget)
        self.curv_n = QSpinBox()
        self.curv_n.setRange(2, 1000)
        self.curv_n.setValue(50)
        self.curv_sens = QDoubleSpinBox()
        self.curv_sens.setRange(0.1, 10.0)
        self.curv_sens.setValue(1.5)
        self.curv_sens.setSingleStep(0.1)
        curv_layout.addRow("Num Points:", self.curv_n)
        curv_layout.addRow("Sensitivity:", self.curv_sens)
        self.param_stack.addWidget(curv_widget)
        
        # 5. Geometric
        geo_widget = QWidget()
        geo_layout = QFormLayout(geo_widget)
        self.geo_n = QSpinBox()
        self.geo_n.setRange(2, 1000)
        self.geo_n.setValue(50)
        self.geo_ratio = QDoubleSpinBox()
        self.geo_ratio.setRange(1.0, 5.0)
        self.geo_ratio.setValue(1.2)
        self.geo_ratio.setSingleStep(0.05)
        geo_layout.addRow("Num Points:", self.geo_n)
        geo_layout.addRow("Ratio:", self.geo_ratio)
        self.param_stack.addWidget(geo_widget)

    def _toggle_uniform_mode(self, is_spacing):
        self.uniform_n.setVisible(not is_spacing)
        n_label = self.uniform_n.parentWidget().layout().labelForField(self.uniform_n)
        if n_label: n_label.setVisible(not is_spacing)
        
        self.uniform_spacing.setVisible(is_spacing)
        if self.uniform_spacing_label: self.uniform_spacing_label.setVisible(is_spacing)

    def switch_param_form(self, strategy_name):
        index_map = {"uniform": 0, "tanh": 1, "cosine": 2, "curvature": 3, "geometric": 4}
        if strategy_name in index_map:
            self.param_stack.setCurrentIndex(index_map[strategy_name])
