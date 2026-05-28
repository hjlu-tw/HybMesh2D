from __future__ import annotations
import os
from PyQt6.QtWidgets import (

    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox, QLabel,
    QCheckBox, QLineEdit, QListWidget, QListWidgetItem, QFileDialog
)
from PyQt6.QtCore import Qt
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels
from app.models.mesh_config import MeshConfig

# Style for QLineEdit fields matching spinboxes
LINEEDIT_STYLE = "background:#181b2a; color:#a0a8c0; border:1px solid #333852; padding:3px; border-radius:3px;"

class MeshConfigPanel(QScrollArea):
    """Scrollable panel containing editor widgets for all Background_para.dat options."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: #0c0d16;")

        # Custom scrollbar styling
        self.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: #0c0d16;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #2c2e43;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3e415e;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content = QWidget()
        content.setStyleSheet("background: #121422; color: #a0a8c0;")
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(6)
        self.setWidget(content)

        # ── Control Buttons ───────────────────────────────────────────────
        self.load_config_btn = make_button("Load Config File")
        self.save_config_btn = make_button("Save Config File", "#301540")
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        btn_layout.addWidget(self.load_config_btn)
        btn_layout.addWidget(self.save_config_btn)
        self._layout.addLayout(btn_layout)

        # Row 2: Run / Cancel
        self.run_mesh_btn = make_button("Generate Mesh", "#1e4620")
        self.cancel_mesh_btn = make_button("Cancel", "#4a1c1c")
        self.cancel_mesh_btn.setEnabled(False)

        btn_layout2 = QHBoxLayout()
        btn_layout2.setSpacing(4)
        btn_layout2.addWidget(self.run_mesh_btn)
        btn_layout2.addWidget(self.cancel_mesh_btn)
        self._layout.addLayout(btn_layout2)

        # ── 1. Domain & Geometry Files ────────────────────────────────────
        self.sec_domain = CollapsibleSection("1. Domain & Geometry", start_collapsed=False)
        self._layout.addWidget(self.sec_domain)

        # Bounding box
        dom_form = QFormLayout()
        self.domain_x_min = QDoubleSpinBox()
        self.domain_x_min.setRange(-1e6, 1e6)
        self.domain_x_min.setDecimals(4)
        self.domain_x_min.setStyleSheet(SPIN_STYLE)

        self.domain_x_max = QDoubleSpinBox()
        self.domain_x_max.setRange(-1e6, 1e6)
        self.domain_x_max.setDecimals(4)
        self.domain_x_max.setStyleSheet(SPIN_STYLE)

        self.domain_y_min = QDoubleSpinBox()
        self.domain_y_min.setRange(-1e6, 1e6)
        self.domain_y_min.setDecimals(4)
        self.domain_y_min.setStyleSheet(SPIN_STYLE)

        self.domain_y_max = QDoubleSpinBox()
        self.domain_y_max.setRange(-1e6, 1e6)
        self.domain_y_max.setDecimals(4)
        self.domain_y_max.setStyleSheet(SPIN_STYLE)

        dom_form.addRow("Domain X Min:", self.domain_x_min)
        dom_form.addRow("Domain X Max:", self.domain_x_max)
        dom_form.addRow("Domain Y Min:", self.domain_y_min)
        dom_form.addRow("Domain Y Max:", self.domain_y_max)
        align_form_labels(dom_form, 130)
        self.sec_domain.add_layout(dom_form)

        # Geometry file list
        geom_label = QLabel("Geometry Input Files:")
        geom_label.setStyleSheet("color: #a0b0d0; margin-top: 6px; font-weight: bold;")
        self.sec_domain.add_widget(geom_label)

        self.geom_list_widget = QListWidget()
        self.geom_list_widget.setFixedHeight(80)
        self.geom_list_widget.setStyleSheet(
            "background: #181b2a; color: #a0a8c0; border: 1px solid #333852; border-radius: 3px;"
        )
        self.sec_domain.add_widget(self.geom_list_widget)

        # Geometry list control buttons
        geom_btn_layout = QHBoxLayout()
        geom_btn_layout.setSpacing(4)
        self.add_active_geom_btn = make_button("Add Active", "#1a2525")
        self.add_active_geom_btn.setToolTip("Add the active PreProcessor resampled file")
        self.add_file_geom_btn = make_button("Browse", "#1d2a3a")
        self.remove_geom_btn = make_button("Remove", "#301a1a")

        geom_btn_layout.addWidget(self.add_active_geom_btn)
        geom_btn_layout.addWidget(self.add_file_geom_btn)
        geom_btn_layout.addWidget(self.remove_geom_btn)
        self.sec_domain.add_layout(geom_btn_layout)

        # ── 2. General Sizing ─────────────────────────────────────────────
        self.sec_sizing = CollapsibleSection("2. Mesh Sizing", start_collapsed=True)
        self._layout.addWidget(self.sec_sizing)

        sizing_form = QFormLayout()
        self.surface_mesh_size = QDoubleSpinBox()
        self.surface_mesh_size.setRange(1e-4, 1e4)
        self.surface_mesh_size.setDecimals(4)
        self.surface_mesh_size.setStyleSheet(SPIN_STYLE)

        self.auto_surface_size = QCheckBox("Auto Surface Sizing")
        self.auto_surface_size.setStyleSheet("color:#a0a8c0;")

        self.farfield_mesh_size = QDoubleSpinBox()
        self.farfield_mesh_size.setRange(1e-4, 1e4)
        self.farfield_mesh_size.setDecimals(4)
        self.farfield_mesh_size.setStyleSheet(SPIN_STYLE)

        self.farfield_growth_rate = QDoubleSpinBox()
        self.farfield_growth_rate.setRange(0.01, 10.0)
        self.farfield_growth_rate.setDecimals(4)
        self.farfield_growth_rate.setStyleSheet(SPIN_STYLE)

        sizing_form.addRow("Surface Size:", self.surface_mesh_size)
        sizing_form.addRow("", self.auto_surface_size)
        sizing_form.addRow("Far-field Size:", self.farfield_mesh_size)
        sizing_form.addRow("Growth Rate:", self.farfield_growth_rate)
        align_form_labels(sizing_form, 130)
        self.sec_sizing.add_layout(sizing_form)

        # ── 3. Boundary Layer Core ────────────────────────────────────────
        self.sec_bl_core = CollapsibleSection("3. Boundary Layer Core", start_collapsed=True)
        self._layout.addWidget(self.sec_bl_core)

        bl_form = QFormLayout()
        self.bl_initial_thickness = QDoubleSpinBox()
        self.bl_initial_thickness.setRange(1e-6, 1.0)
        self.bl_initial_thickness.setDecimals(6)
        self.bl_initial_thickness.setStyleSheet(SPIN_STYLE)

        self.bl_growth_rate = QDoubleSpinBox()
        self.bl_growth_rate.setRange(1.001, 5.0)
        self.bl_growth_rate.setDecimals(4)
        self.bl_growth_rate.setStyleSheet(SPIN_STYLE)

        self.bl_layers = QSpinBox()
        self.bl_layers.setRange(0, 100)
        self.bl_layers.setStyleSheet(SPIN_STYLE)

        bl_form.addRow("Initial Thick:", self.bl_initial_thickness)
        bl_form.addRow("Growth Rate:", self.bl_growth_rate)
        bl_form.addRow("Layers:", self.bl_layers)
        align_form_labels(bl_form, 130)
        self.sec_bl_core.add_layout(bl_form)

        # ── 4. Fan & Convex Corner Handling ────────────────────────────────
        self.sec_convex = CollapsibleSection("4. Convex Corner Handling", start_collapsed=True)
        self._layout.addWidget(self.sec_convex)

        convex_form = QFormLayout()
        self.bl_convex_method = QComboBox()
        self.bl_convex_method.addItems(["0: Fan", "2: Parallelogram"])
        self.bl_convex_method.setStyleSheet(COMBO_STYLE)

        self.bl_fan_nodes = QSpinBox()
        self.bl_fan_nodes.setRange(1, 100)
        self.bl_fan_nodes.setStyleSheet(SPIN_STYLE)

        self.bl_auto_fan_nodes = QCheckBox("Auto Fan Nodes")
        self.bl_auto_fan_nodes.setStyleSheet("color:#a0a8c0;")

        self.bl_fan_angle_threshold = QDoubleSpinBox()
        self.bl_fan_angle_threshold.setRange(0.0, 360.0)
        self.bl_fan_angle_threshold.setDecimals(2)
        self.bl_fan_angle_threshold.setStyleSheet(SPIN_STYLE)

        self.bl_convex_angle_threshold = QDoubleSpinBox()
        self.bl_convex_angle_threshold.setRange(0.0, 360.0)
        self.bl_convex_angle_threshold.setDecimals(2)
        self.bl_convex_angle_threshold.setStyleSheet(SPIN_STYLE)

        self.bl_para_fallback_angle = QDoubleSpinBox()
        self.bl_para_fallback_angle.setRange(0.0, 360.0)
        self.bl_para_fallback_angle.setDecimals(2)
        self.bl_para_fallback_angle.setStyleSheet(SPIN_STYLE)

        convex_form.addRow("Convex Method:", self.bl_convex_method)
        convex_form.addRow("Fan Nodes:", self.bl_fan_nodes)
        convex_form.addRow("", self.bl_auto_fan_nodes)
        convex_form.addRow("Fan Threshold (deg):", self.bl_fan_angle_threshold)
        convex_form.addRow("Convex Threshold (deg):", self.bl_convex_angle_threshold)
        convex_form.addRow("Fallback Angle (deg):", self.bl_para_fallback_angle)
        align_form_labels(convex_form, 130)
        self.sec_convex.add_layout(convex_form)

        # ── 5. Concave Corner Handling ────────────────────────────────────
        self.sec_concave = CollapsibleSection("5. Concave Corner Handling", start_collapsed=True)
        self._layout.addWidget(self.sec_concave)

        concave_form = QFormLayout()
        self.bl_concave_method = QComboBox()
        self.bl_concave_method.addItems(["0: Vector Merge", "5: Thickness Blending"])
        self.bl_concave_method.setStyleSheet(COMBO_STYLE)

        self.bl_concave_angle_threshold = QDoubleSpinBox()
        self.bl_concave_angle_threshold.setRange(0.0, 360.0)
        self.bl_concave_angle_threshold.setDecimals(2)
        self.bl_concave_angle_threshold.setStyleSheet(SPIN_STYLE)

        self.bl_concave_influence_multiplier = QDoubleSpinBox()
        self.bl_concave_influence_multiplier.setRange(0.0, 100.0)
        self.bl_concave_influence_multiplier.setDecimals(2)
        self.bl_concave_influence_multiplier.setStyleSheet(SPIN_STYLE)

        self.bl_merge_concave = QCheckBox("Merge Concave")
        self.bl_merge_concave.setStyleSheet("color:#a0a8c0;")

        self.bl_smoothing_iters = QSpinBox()
        self.bl_smoothing_iters.setRange(0, 100)
        self.bl_smoothing_iters.setStyleSheet(SPIN_STYLE)

        concave_form.addRow("Concave Method:", self.bl_concave_method)
        concave_form.addRow("Concave Threshold:", self.bl_concave_angle_threshold)
        concave_form.addRow("Influence Mult:", self.bl_concave_influence_multiplier)
        concave_form.addRow("", self.bl_merge_concave)
        concave_form.addRow("Smoothing Iters:", self.bl_smoothing_iters)
        align_form_labels(concave_form, 130)
        self.sec_concave.add_layout(concave_form)

        # ── 6. Transition & Meshing Algorithm ─────────────────────────────
        self.sec_transition = CollapsibleSection("6. Transition & Algorithm", start_collapsed=True)
        self._layout.addWidget(self.sec_transition)

        trans_form = QFormLayout()
        self.bl_transition_layers = QSpinBox()
        self.bl_transition_layers.setRange(0, 100)
        self.bl_transition_layers.setStyleSheet(SPIN_STYLE)

        self.bl_auto_transition_layers = QComboBox()
        self.bl_auto_transition_layers.addItems(["0: OFF", "1: GLOBAL", "2: LOCAL"])
        self.bl_auto_transition_layers.setStyleSheet(COMBO_STYLE)

        self.bl_transition_growth_rate = QDoubleSpinBox()
        self.bl_transition_growth_rate.setRange(1.001, 5.0)
        self.bl_transition_growth_rate.setDecimals(4)
        self.bl_transition_growth_rate.setStyleSheet(SPIN_STYLE)

        self.bl_transition_buffer = QDoubleSpinBox()
        self.bl_transition_buffer.setRange(0.0, 100.0)
        self.bl_transition_buffer.setDecimals(4)
        self.bl_transition_buffer.setStyleSheet(SPIN_STYLE)

        self.gmsh_algorithm = QComboBox()
        self.gmsh_algorithm.addItems([
            "1: MeshAdapt",
            "2: Automatic",
            "5: Delaunay",
            "6: Frontal-Delaunay",
            "7: BAMG",
            "8: Frontal-Delaunay Quads"
        ])
        self.gmsh_algorithm.setStyleSheet(COMBO_STYLE)

        self.gmsh_optimize = QCheckBox("Optimize Mesh Quality")
        self.gmsh_optimize.setStyleSheet("color:#a0a8c0;")

        trans_form.addRow("Transition Layers:", self.bl_transition_layers)
        trans_form.addRow("Auto Transition:", self.bl_auto_transition_layers)
        trans_form.addRow("Trans Growth Rate:", self.bl_transition_growth_rate)
        trans_form.addRow("Trans Buffer:", self.bl_transition_buffer)
        trans_form.addRow("Gmsh Algorithm:", self.gmsh_algorithm)
        trans_form.addRow("", self.gmsh_optimize)
        align_form_labels(trans_form, 130)
        self.sec_transition.add_layout(trans_form)

        # ── 7. Boundary Conditions & I/O ──────────────────────────────────
        self.sec_io = CollapsibleSection("7. BCs & Output Options", start_collapsed=True)
        self._layout.addWidget(self.sec_io)

        io_form = QFormLayout()
        
        self.bc_xmin = QLineEdit()
        self.bc_xmin.setStyleSheet(LINEEDIT_STYLE)
        self.bc_xmax = QLineEdit()
        self.bc_xmax.setStyleSheet(LINEEDIT_STYLE)
        self.bc_ymin = QLineEdit()
        self.bc_ymin.setStyleSheet(LINEEDIT_STYLE)
        self.bc_ymax = QLineEdit()
        self.bc_ymax.setStyleSheet(LINEEDIT_STYLE)
        self.bc_geom = QLineEdit()
        self.bc_geom.setStyleSheet(LINEEDIT_STYLE)

        self.output_filename = QLineEdit()
        self.output_filename.setStyleSheet(LINEEDIT_STYLE)

        self.export_vtk = QCheckBox("Export VTK File")
        self.export_vtk.setStyleSheet("color:#a0a8c0;")
        self.export_starcd = QCheckBox("Export STAR-CD Files")
        self.export_starcd.setStyleSheet("color:#a0a8c0;")
        self.enable_collision_detection = QCheckBox("Collision Detection")
        self.enable_collision_detection.setStyleSheet("color:#a0a8c0;")

        io_form.addRow("BC XMin:", self.bc_xmin)
        io_form.addRow("BC XMax:", self.bc_xmax)
        io_form.addRow("BC YMin:", self.bc_ymin)
        io_form.addRow("BC YMax:", self.bc_ymax)
        io_form.addRow("BC Geom (Wall):", self.bc_geom)
        io_form.addRow("Output Filename:", self.output_filename)
        io_form.addRow("", self.export_vtk)
        io_form.addRow("", self.export_starcd)
        io_form.addRow("", self.enable_collision_detection)
        align_form_labels(io_form, 130)
        self.sec_io.add_layout(io_form)

        # Spacer at the end
        self._layout.addStretch()

        # Connect internal Browse button
        self.add_file_geom_btn.clicked.connect(self._on_browse_geom)
        self.remove_geom_btn.clicked.connect(self._on_remove_geom)

    def _on_browse_geom(self):
        """Prompt file dialog to select external geometry files."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Geometry File", "", "Geometry Files (*.dat);;All Files (*)"
        )
        for f in files:
            # We want to display the relative path or absolute path
            # For simplicity, store absolute path but list basename
            item = QListWidgetItem(os.path.basename(f))
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.geom_list_widget.addItem(item)

    def _on_remove_geom(self):
        """Remove selected geometry file from the list."""
        for item in self.geom_list_widget.selectedItems():
            self.geom_list_widget.takeItem(self.geom_list_widget.row(item))

    def set_config(self, cfg: MeshConfig):
        """Populate widget values from a MeshConfig model instance."""
        # 1. Domain
        self.domain_x_min.setValue(cfg.domain_x_min)
        self.domain_x_max.setValue(cfg.domain_x_max)
        self.domain_y_min.setValue(cfg.domain_y_min)
        self.domain_y_max.setValue(cfg.domain_y_max)

        # Geometries
        self.geom_list_widget.clear()
        for f in cfg.geom_files:
            item = QListWidgetItem(os.path.basename(f))
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.geom_list_widget.addItem(item)

        # 2. Sizing
        self.surface_mesh_size.setValue(cfg.surface_mesh_size)
        self.auto_surface_size.setChecked(cfg.auto_surface_size)
        self.farfield_mesh_size.setValue(cfg.farfield_mesh_size)
        self.farfield_growth_rate.setValue(cfg.farfield_growth_rate)

        # 3. BL Core
        self.bl_initial_thickness.setValue(cfg.bl_initial_thickness)
        self.bl_growth_rate.setValue(cfg.bl_growth_rate)
        self.bl_layers.setValue(cfg.bl_layers)

        # 4. Convex
        convex_methods = [0, 2]
        if cfg.bl_convex_method in convex_methods:
            self.bl_convex_method.setCurrentIndex(convex_methods.index(cfg.bl_convex_method))
        else:
            self.bl_convex_method.setCurrentIndex(0)
        self.bl_fan_nodes.setValue(cfg.bl_fan_nodes)
        self.bl_auto_fan_nodes.setChecked(cfg.bl_auto_fan_nodes)
        self.bl_fan_angle_threshold.setValue(cfg.bl_fan_angle_threshold)
        self.bl_convex_angle_threshold.setValue(cfg.bl_convex_angle_threshold)
        self.bl_para_fallback_angle.setValue(cfg.bl_para_fallback_angle)

        # 5. Concave
        concave_methods = [0, 5]
        if cfg.bl_concave_method in concave_methods:
            self.bl_concave_method.setCurrentIndex(concave_methods.index(cfg.bl_concave_method))
        else:
            self.bl_concave_method.setCurrentIndex(0)
        self.bl_concave_angle_threshold.setValue(cfg.bl_concave_angle_threshold)
        self.bl_concave_influence_multiplier.setValue(cfg.bl_concave_influence_multiplier)
        self.bl_merge_concave.setChecked(cfg.bl_merge_concave)
        self.bl_smoothing_iters.setValue(cfg.bl_smoothing_iters)

        # 6. Transition
        self.bl_transition_layers.setValue(cfg.bl_transition_layers)
        self.bl_auto_transition_layers.setCurrentIndex(cfg.bl_auto_transition_layers)
        self.bl_transition_growth_rate.setValue(cfg.bl_transition_growth_rate)
        self.bl_transition_buffer.setValue(cfg.bl_transition_buffer)

        gmsh_algos = [1, 2, 5, 6, 7, 8]
        if cfg.gmsh_algorithm in gmsh_algos:
            self.gmsh_algorithm.setCurrentIndex(gmsh_algos.index(cfg.gmsh_algorithm))
        else:
            self.gmsh_algorithm.setCurrentIndex(3)  # default: 6
        self.gmsh_optimize.setChecked(cfg.gmsh_optimize != 0)

        # 7. BCs & IO
        self.bc_xmin.setText(cfg.bc_xmin)
        self.bc_xmax.setText(cfg.bc_xmax)
        self.bc_ymin.setText(cfg.bc_ymin)
        self.bc_ymax.setText(cfg.bc_ymax)
        self.bc_geom.setText(cfg.bc_geom)
        self.output_filename.setText(cfg.output_filename)

        self.export_vtk.setChecked(cfg.export_vtk)
        self.export_starcd.setChecked(cfg.export_starcd)
        self.enable_collision_detection.setChecked(cfg.enable_collision_detection)

    def get_config(self) -> MeshConfig:
        """Collect widget values and return a MeshConfig model instance."""
        cfg = MeshConfig()
        
        # 1. Domain
        cfg.domain_x_min = self.domain_x_min.value()
        cfg.domain_x_max = self.domain_x_max.value()
        cfg.domain_y_min = self.domain_y_min.value()
        cfg.domain_y_max = self.domain_y_max.value()

        # Geometries
        cfg.geom_files = []
        for row in range(self.geom_list_widget.count()):
            item = self.geom_list_widget.item(row)
            cfg.geom_files.append(item.data(Qt.ItemDataRole.UserRole))

        # 2. Sizing
        cfg.surface_mesh_size = self.surface_mesh_size.value()
        cfg.auto_surface_size = self.auto_surface_size.isChecked()
        cfg.farfield_mesh_size = self.farfield_mesh_size.value()
        cfg.farfield_growth_rate = self.farfield_growth_rate.value()

        # 3. BL Core
        cfg.bl_initial_thickness = self.bl_initial_thickness.value()
        cfg.bl_growth_rate = self.bl_growth_rate.value()
        cfg.bl_layers = self.bl_layers.value()

        # 4. Convex
        convex_methods = [0, 2]
        cfg.bl_convex_method = convex_methods[self.bl_convex_method.currentIndex()]
        cfg.bl_fan_nodes = self.bl_fan_nodes.value()
        cfg.bl_auto_fan_nodes = self.bl_auto_fan_nodes.isChecked()
        cfg.bl_fan_angle_threshold = self.bl_fan_angle_threshold.value()
        cfg.bl_convex_angle_threshold = self.bl_convex_angle_threshold.value()
        cfg.bl_para_fallback_angle = self.bl_para_fallback_angle.value()

        # 5. Concave
        concave_methods = [0, 5]
        cfg.bl_concave_method = concave_methods[self.bl_concave_method.currentIndex()]
        cfg.bl_concave_angle_threshold = self.bl_concave_angle_threshold.value()
        cfg.bl_concave_influence_multiplier = self.bl_concave_influence_multiplier.value()
        cfg.bl_merge_concave = self.bl_merge_concave.isChecked()
        cfg.bl_smoothing_iters = self.bl_smoothing_iters.value()

        # 6. Transition
        cfg.bl_transition_layers = self.bl_transition_layers.value()
        cfg.bl_auto_transition_layers = self.bl_auto_transition_layers.currentIndex()
        cfg.bl_transition_growth_rate = self.bl_transition_growth_rate.value()
        cfg.bl_transition_buffer = self.bl_transition_buffer.value()

        gmsh_algos = [1, 2, 5, 6, 7, 8]
        cfg.gmsh_algorithm = gmsh_algos[self.gmsh_algorithm.currentIndex()]
        cfg.gmsh_optimize = 1 if self.gmsh_optimize.isChecked() else 0

        # 7. BCs & IO
        cfg.bc_xmin = self.bc_xmin.text().strip()
        cfg.bc_xmax = self.bc_xmax.text().strip()
        cfg.bc_ymin = self.bc_ymin.text().strip()
        cfg.bc_ymax = self.bc_ymax.text().strip()
        cfg.bc_geom = self.bc_geom.text().strip()
        cfg.output_filename = self.output_filename.text().strip()

        cfg.export_vtk = self.export_vtk.isChecked()
        cfg.export_starcd = self.export_starcd.isChecked()
        cfg.enable_collision_detection = self.enable_collision_detection.isChecked()

        return cfg
