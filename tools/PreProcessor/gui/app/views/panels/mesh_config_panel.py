from __future__ import annotations
import os
from PyQt6.QtWidgets import (

    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QFormLayout, QComboBox, QSpinBox, QLabel,
    QCheckBox, QLineEdit, QListWidget, QListWidgetItem, QFileDialog,
    QPushButton, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from app.views.collapsible import CollapsibleSection
from app.utils import (
    make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels,
    help_label, help_widget, LINEEDIT_STYLE, BC_COLORS, DEFAULT_BC_COLOR
)
from app.models.mesh_config import MeshConfig
from app.views.bc_widget import BCWidget
from app.views.clean_double_spin_box import CleanDoubleSpinBox


class MeshConfigPanel(QScrollArea):
    """Scrollable panel containing editor widgets for all Background_para.dat options."""
    geom_files_changed = pyqtSignal(list)
    mesh_config_changed = pyqtSignal(object)

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

        # Row 2: Preview / Run / Cancel (Redundant, not added to layout to keep sidebar clean since they are in the top toolbar)
        self.preview_btn = make_button("BC Preview", "#1e2a38")
        self.run_mesh_btn = make_button("Mesh Generate", "#1e4620")
        self.cancel_mesh_btn = make_button("Cancel", "#4a1c1c")
        self.cancel_mesh_btn.setEnabled(False)

        # ── 1. Domain & Geometry Files ────────────────────────────────────
        self.sec_domain = CollapsibleSection("1. Domain & Geometry", start_collapsed=True)
        self._layout.addWidget(self.sec_domain)

        # Bounding box
        dom_form = QFormLayout()
        self.domain_x_min = CleanDoubleSpinBox()
        self.domain_x_min.setRange(-1e6, 1e6)
        self.domain_x_min.setDecimals(4)
        self.domain_x_min.setStyleSheet(SPIN_STYLE)
        self.domain_x_min.setToolTip("Left boundary of the rectangular computational domain")

        self.domain_x_max = CleanDoubleSpinBox()
        self.domain_x_max.setRange(-1e6, 1e6)
        self.domain_x_max.setDecimals(4)
        self.domain_x_max.setStyleSheet(SPIN_STYLE)
        self.domain_x_max.setToolTip("Right boundary of the rectangular computational domain")

        self.domain_y_min = CleanDoubleSpinBox()
        self.domain_y_min.setRange(-1e6, 1e6)
        self.domain_y_min.setDecimals(4)
        self.domain_y_min.setStyleSheet(SPIN_STYLE)
        self.domain_y_min.setToolTip("Bottom boundary of the rectangular computational domain")

        self.domain_y_max = CleanDoubleSpinBox()
        self.domain_y_max.setRange(-1e6, 1e6)
        self.domain_y_max.setDecimals(4)
        self.domain_y_max.setStyleSheet(SPIN_STYLE)
        self.domain_y_max.setToolTip("Top boundary of the rectangular computational domain")

        dom_form.addRow(help_label("Domain X Min:", "Left boundary of the rectangular computational domain"), self.domain_x_min)
        dom_form.addRow(help_label("Domain X Max:", "Right boundary of the rectangular computational domain"), self.domain_x_max)
        dom_form.addRow(help_label("Domain Y Min:", "Bottom boundary of the rectangular computational domain"), self.domain_y_min)
        dom_form.addRow(help_label("Domain Y Max:", "Top boundary of the rectangular computational domain"), self.domain_y_max)
        align_form_labels(dom_form, 130)
        self.sec_domain.add_layout(dom_form)

        # Geometry file list
        geom_label = QLabel("Geometry Input Files:")
        geom_label.setStyleSheet("color: #a0b0d0; margin-top: 6px; font-weight: bold;")
        self.sec_domain.add_widget(help_widget(geom_label, "Geometry files to load for meshing"))

        self.geom_list_widget = QListWidget()
        self.geom_list_widget.setFixedHeight(80)
        self.geom_list_widget.setStyleSheet(
            "background: #181b2a; color: #a0a8c0; border: 1px solid #333852; border-radius: 3px;"
        )
        self.sec_domain.add_widget(help_widget(self.geom_list_widget, "List of geometry boundary files to include in the computational domain"))

        # Geometry list control buttons
        geom_btn_layout = QHBoxLayout()
        geom_btn_layout.setSpacing(4)
        self.add_active_geom_btn = make_button("Add Active", "#1a2525")
        self.add_active_geom_btn.setToolTip("Add the active PreProcessor resampled file")
        self.add_file_geom_btn = make_button("Browse", "#1d2a3a")
        self.remove_geom_btn = make_button("Remove", "#301a1a")

        geom_btn_layout.addWidget(help_widget(self.add_active_geom_btn, "Add the active PreProcessor resampled geometry"))
        geom_btn_layout.addWidget(help_widget(self.add_file_geom_btn, "Browse for geometry files on disk"))
        geom_btn_layout.addWidget(help_widget(self.remove_geom_btn, "Remove selected geometry file from list"))
        self.sec_domain.add_layout(geom_btn_layout)

        # ── 2. General Sizing ─────────────────────────────────────────────
        self.sec_sizing = CollapsibleSection("2. Mesh Sizing", start_collapsed=True)
        self._layout.addWidget(self.sec_sizing)

        sizing_form = QFormLayout()
        self.surface_mesh_size = CleanDoubleSpinBox()
        self.surface_mesh_size.setRange(1e-4, 1e4)
        self.surface_mesh_size.setDecimals(4)
        self.surface_mesh_size.setStyleSheet(SPIN_STYLE)
        self.surface_mesh_size.setToolTip("Target element size along the geometry boundary walls")

        self.auto_surface_size = QCheckBox("Auto Surface Sizing")
        self.auto_surface_size.setStyleSheet("color:#a0a8c0;")
        self.auto_surface_size.setToolTip("Automatically determine surface mesh size from geometry spacing")

        self.farfield_mesh_size = CleanDoubleSpinBox()
        self.farfield_mesh_size.setRange(1e-4, 1e4)
        self.farfield_mesh_size.setDecimals(4)
        self.farfield_mesh_size.setStyleSheet(SPIN_STYLE)
        self.farfield_mesh_size.setToolTip("Target element size in the far-field region away from geometry")

        self.farfield_growth_rate = CleanDoubleSpinBox()
        self.farfield_growth_rate.setRange(0.01, 10.0)
        self.farfield_growth_rate.setDecimals(4)
        self.farfield_growth_rate.setStyleSheet(SPIN_STYLE)
        self.farfield_growth_rate.setToolTip("Rate of element size expansion from surface to far-field (0.0~1.0)")

        sizing_form.addRow(help_label("Surface Size:", "Target element size along the geometry boundary walls"), self.surface_mesh_size)
        sizing_form.addRow("", help_widget(self.auto_surface_size, "Automatically determine surface mesh size from geometry spacing"))
        sizing_form.addRow(help_label("Far-field Size:", "Target element size in the far-field region away from geometry"), self.farfield_mesh_size)
        sizing_form.addRow(help_label("Growth Rate:", "Rate of element size expansion from surface to far-field (0.0~1.0)"), self.farfield_growth_rate)
        align_form_labels(sizing_form, 130)
        self.sec_sizing.add_layout(sizing_form)

        # ── 3. Boundary Layer Core ────────────────────────────────────────
        self.sec_bl_core = CollapsibleSection("3. Boundary Layer Core", start_collapsed=True)
        self._layout.addWidget(self.sec_bl_core)

        bl_form = QFormLayout()
        self.bl_initial_thickness = CleanDoubleSpinBox()
        self.bl_initial_thickness.setRange(1e-6, 1.0)
        self.bl_initial_thickness.setDecimals(6)
        self.bl_initial_thickness.setStyleSheet(SPIN_STYLE)
        self.bl_initial_thickness.setToolTip("Height of the first boundary layer cell adjacent to the wall")

        self.bl_growth_rate = CleanDoubleSpinBox()
        self.bl_growth_rate.setRange(1.001, 5.0)
        self.bl_growth_rate.setDecimals(4)
        self.bl_growth_rate.setStyleSheet(SPIN_STYLE)
        self.bl_growth_rate.setToolTip("Multiplicative growth factor between successive BL layers (e.g. 1.2 = 20% increase per layer)")

        self.bl_layers = QSpinBox()
        self.bl_layers.setRange(0, 100)
        self.bl_layers.setStyleSheet(SPIN_STYLE)
        self.bl_layers.setToolTip("Total number of structured boundary layer rows to generate")

        bl_form.addRow(help_label("Initial Thick:", "Height of the first boundary layer cell adjacent to the wall"), self.bl_initial_thickness)
        bl_form.addRow(help_label("Growth Rate:", "Multiplicative growth factor between successive BL layers (e.g. 1.2 = 20% increase per layer)"), self.bl_growth_rate)
        bl_form.addRow(help_label("Layers:", "Total number of structured boundary layer rows to generate"), self.bl_layers)
        align_form_labels(bl_form, 130)
        self.sec_bl_core.add_layout(bl_form)

        # ── 4. Transition & Meshing Algorithm ─────────────────────────────
        self.sec_transition = CollapsibleSection("4. Transition & Algorithm", start_collapsed=True)
        self._layout.addWidget(self.sec_transition)

        trans_form = QFormLayout()
        self.bl_transition_layers = QSpinBox()
        self.bl_transition_layers.setRange(0, 100)
        self.bl_transition_layers.setStyleSheet(SPIN_STYLE)
        self.bl_transition_layers.setToolTip("Number of transitional element rows blending BL quads into far-field triangles")

        self.bl_auto_transition_layers = QComboBox()
        self.bl_auto_transition_layers.addItems(["0: OFF", "1: GLOBAL", "2: LOCAL"])
        self.bl_auto_transition_layers.setStyleSheet(COMBO_STYLE)
        self.bl_auto_transition_layers.setToolTip("Automatically compute transition layer count (OFF / GLOBAL / LOCAL)")

        self.bl_transition_growth_rate = CleanDoubleSpinBox()
        self.bl_transition_growth_rate.setRange(1.001, 5.0)
        self.bl_transition_growth_rate.setDecimals(4)
        self.bl_transition_growth_rate.setStyleSheet(SPIN_STYLE)
        self.bl_transition_growth_rate.setToolTip("Growth rate applied within the transition zone between BL and far-field")

        self.bl_transition_buffer = CleanDoubleSpinBox()
        self.bl_transition_buffer.setRange(0.0, 100.0)
        self.bl_transition_buffer.setDecimals(4)
        self.bl_transition_buffer.setStyleSheet(SPIN_STYLE)
        self.bl_transition_buffer.setToolTip("Buffer distance multiplier around geometry for transition smoothing")

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
        self.gmsh_algorithm.setToolTip("Meshing algorithm used by Gmsh for far-field triangulation")

        self.gmsh_optimize = QCheckBox("Optimize Mesh Quality")
        self.gmsh_optimize.setStyleSheet("color:#a0a8c0;")
        self.gmsh_optimize.setToolTip("Enable Gmsh mesh quality optimization pass after generation")

        trans_form.addRow(help_label("Transition Layers:", "Number of transitional element rows blending BL quads into far-field triangles"), self.bl_transition_layers)
        trans_form.addRow(help_label("Auto Transition:", "Automatically compute transition layer count (OFF / GLOBAL / LOCAL)"), self.bl_auto_transition_layers)
        trans_form.addRow(help_label("Trans Growth Rate:", "Growth rate applied within the transition zone between BL and far-field"), self.bl_transition_growth_rate)
        trans_form.addRow(help_label("Trans Buffer:", "Buffer distance multiplier around geometry for transition smoothing"), self.bl_transition_buffer)
        trans_form.addRow(help_label("Gmsh Algorithm:", "Meshing algorithm used by Gmsh for far-field triangulation"), self.gmsh_algorithm)
        trans_form.addRow("", help_widget(self.gmsh_optimize, "Enable Gmsh mesh quality optimization pass after generation"))
        align_form_labels(trans_form, 130)
        self.sec_transition.add_layout(trans_form)

        # ── 5. Fan & Convex Corner Handling ────────────────────────────────
        self.sec_convex = CollapsibleSection("5. Convex Corner Handling", start_collapsed=True)
        self._layout.addWidget(self.sec_convex)

        self.convex_form = QFormLayout()
        self.bl_convex_method = QComboBox()
        self.bl_convex_method.addItems(["0: Fan", "2: Parallelogram"])
        self.bl_convex_method.setStyleSheet(COMBO_STYLE)
        self.bl_convex_method.setCurrentIndex(1)  # Default: Parallelogram
        self.bl_convex_method.setToolTip("Method for handling convex (outward-pointing) corners in the boundary layer")

        self.bl_fan_nodes = QSpinBox()
        self.bl_fan_nodes.setRange(1, 100)
        self.bl_fan_nodes.setStyleSheet(SPIN_STYLE)
        self.bl_fan_nodes.setToolTip("Number of fan elements inserted at convex corners (Fan method only)")

        self.bl_auto_fan_nodes = QCheckBox("Auto Fan Nodes")
        self.bl_auto_fan_nodes.setStyleSheet("color:#a0a8c0;")
        self.bl_auto_fan_nodes.setToolTip("Automatically determine fan node count based on corner angle")

        self.bl_fan_angle_threshold = CleanDoubleSpinBox()
        self.bl_fan_angle_threshold.setRange(0.0, 360.0)
        self.bl_fan_angle_threshold.setDecimals(2)
        self.bl_fan_angle_threshold.setStyleSheet(SPIN_STYLE)
        self.bl_fan_angle_threshold.setToolTip("Minimum corner angle (degrees) to trigger fan insertion")

        self.bl_convex_angle_threshold = CleanDoubleSpinBox()
        self.bl_convex_angle_threshold.setRange(0.0, 360.0)
        self.bl_convex_angle_threshold.setDecimals(2)
        self.bl_convex_angle_threshold.setStyleSheet(SPIN_STYLE)
        self.bl_convex_angle_threshold.setToolTip("Angle threshold to classify a corner as convex")

        self.bl_para_fallback_angle = CleanDoubleSpinBox()
        self.bl_para_fallback_angle.setRange(0.0, 360.0)
        self.bl_para_fallback_angle.setDecimals(2)
        self.bl_para_fallback_angle.setStyleSheet(SPIN_STYLE)
        self.bl_para_fallback_angle.setToolTip("When corner angle exceeds this, fall back to parallelogram method")

        self.convex_form.addRow(help_label("Convex Method:", "Method for handling convex (outward-pointing) corners in the boundary layer"), self.bl_convex_method)
        self.convex_form.addRow(help_label("Fan Nodes:", "Number of fan elements inserted at convex corners (Fan method only)"), self.bl_fan_nodes)
        self.convex_form.addRow("", help_widget(self.bl_auto_fan_nodes, "Automatically determine fan node count based on corner angle"))
        self.convex_form.addRow(help_label("Fan Threshold (deg):", "Minimum corner angle (degrees) to trigger fan insertion"), self.bl_fan_angle_threshold)
        self.convex_form.addRow(help_label("Convex Threshold (deg):", "Angle threshold to classify a corner as convex"), self.bl_convex_angle_threshold)
        self.convex_form.addRow(help_label("Fallback Angle (deg):", "When corner angle exceeds this, fall back to parallelogram method"), self.bl_para_fallback_angle)
        align_form_labels(self.convex_form, 130)
        self.sec_convex.add_layout(self.convex_form)

        # Wire visibility updates for Fan parameters
        self.bl_convex_method.currentIndexChanged.connect(self._update_convex_widgets_visibility)
        self._update_convex_widgets_visibility()

        # ── 6. Concave Corner Handling ────────────────────────────────────
        self.sec_concave = CollapsibleSection("6. Concave Corner Handling", start_collapsed=True)
        self._layout.addWidget(self.sec_concave)

        concave_form = QFormLayout()
        self.bl_concave_method = QComboBox()
        self.bl_concave_method.addItems(["5: Thickness Blending"])
        self.bl_concave_method.setStyleSheet(COMBO_STYLE)
        self.bl_concave_method.setToolTip("Method for handling concave (inward-pointing) corners in the boundary layer")

        self.bl_concave_angle_threshold = CleanDoubleSpinBox()
        self.bl_concave_angle_threshold.setRange(0.0, 360.0)
        self.bl_concave_angle_threshold.setDecimals(2)
        self.bl_concave_angle_threshold.setStyleSheet(SPIN_STYLE)
        self.bl_concave_angle_threshold.setToolTip("Angle threshold to classify a corner as concave")

        self.bl_concave_influence_multiplier = CleanDoubleSpinBox()
        self.bl_concave_influence_multiplier.setRange(0.0, 100.0)
        self.bl_concave_influence_multiplier.setDecimals(2)
        self.bl_concave_influence_multiplier.setStyleSheet(SPIN_STYLE)
        self.bl_concave_influence_multiplier.setToolTip("Controls how far the concave corner correction propagates along the wall")

        self.bl_merge_concave = QCheckBox("Merge Concave")
        self.bl_merge_concave.setStyleSheet("color:#a0a8c0;")
        self.bl_merge_concave.setToolTip("Merge nearby concave corners into a single correction zone")

        self.bl_smoothing_iters = QSpinBox()
        self.bl_smoothing_iters.setRange(0, 100)
        self.bl_smoothing_iters.setStyleSheet(SPIN_STYLE)
        self.bl_smoothing_iters.setToolTip("Number of Laplacian smoothing passes applied to BL cells near concave corners")

        concave_form.addRow(help_label("Concave Method:", "Method for handling concave (inward-pointing) corners in the boundary layer"), self.bl_concave_method)
        concave_form.addRow(help_label("Concave Threshold:", "Angle threshold to classify a corner as concave"), self.bl_concave_angle_threshold)
        concave_form.addRow(help_label("Influence Mult:", "Controls how far the concave corner correction propagates along the wall"), self.bl_concave_influence_multiplier)
        concave_form.addRow("", help_widget(self.bl_merge_concave, "Merge nearby concave corners into a single correction zone"))
        concave_form.addRow(help_label("Smoothing Iters:", "Number of Laplacian smoothing passes applied to BL cells near concave corners"), self.bl_smoothing_iters)
        align_form_labels(concave_form, 130)
        self.sec_concave.add_layout(concave_form)



        # ── 7. Boundary Conditions & I/O ──────────────────────────────────
        self.sec_io = CollapsibleSection("7. BCs & Output Options", start_collapsed=True)
        self._layout.addWidget(self.sec_io)

        io_form = QFormLayout()
        
        self.bc_xmin = BCWidget()
        self.bc_xmin_indicator = self.bc_xmin.indicator
        self.bc_xmin.setToolTip("Boundary condition type for the left domain boundary")

        self.bc_xmax = BCWidget()
        self.bc_xmax_indicator = self.bc_xmax.indicator
        self.bc_xmax.setToolTip("Boundary condition type for the right domain boundary")

        self.bc_ymin = BCWidget()
        self.bc_ymin_indicator = self.bc_ymin.indicator
        self.bc_ymin.setToolTip("Boundary condition type for the bottom domain boundary")

        self.bc_ymax = BCWidget()
        self.bc_ymax_indicator = self.bc_ymax.indicator
        self.bc_ymax.setToolTip("Boundary condition type for the top domain boundary")

        self.bc_geom = BCWidget()
        self.bc_geom_indicator = self.bc_geom.indicator
        self.bc_geom.setToolTip("Boundary condition type assigned to the geometry wall surface")

        self.output_filename = QLineEdit()
        self.output_filename.setStyleSheet(LINEEDIT_STYLE)
        self.output_filename.setToolTip("Base filename for mesh output files (extension .* means all formats)")

        self.export_vtk = QCheckBox("Export VTK File")
        self.export_vtk.setStyleSheet("color:#a0a8c0;")
        self.export_starcd = QCheckBox("Export STAR-CD Files")
        self.export_starcd.setStyleSheet("color:#a0a8c0;")
        self.enable_collision_detection = QCheckBox("Collision Detection")
        self.enable_collision_detection.setStyleSheet("color:#a0a8c0;")
        self.enable_collision_detection.setToolTip("Enable self-intersection detection during boundary layer generation")

        self.export_vtk_btn = QPushButton("Export VTK")
        self.export_vtk_btn.setToolTip("Export the generated mesh to a VTK file (.vtk)")
        self.export_vtk_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a3b5c;
                color: #dde2ff;
                border: 1px solid #3d527a;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3b5280;
                border-color: #3b82f6;
                color: #ffffff;
            }
        """)

        self.export_starcd_btn = QPushButton("Export STAR-CD")
        self.export_starcd_btn.setToolTip("Export the generated mesh to STAR-CD files (.vrt, .cel, .bnd)")
        self.export_starcd_btn.setStyleSheet("""
            QPushButton {
                background-color: #301540;
                color: #f5d6ff;
                border: 1px solid #5a2e7a;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #482060;
                border-color: #a855f7;
                color: #ffffff;
            }
        """)

        export_layout = QHBoxLayout()
        export_layout.setSpacing(6)
        export_layout.addWidget(help_widget(self.export_vtk_btn, "Export the generated mesh to a VTK file (.vtk)"))
        export_layout.addWidget(help_widget(self.export_starcd_btn, "Export the generated mesh to STAR-CD files (.vrt, .cel, .bnd)"))

        io_form.addRow(help_label("BC XMin:", "Boundary condition type for the left domain boundary"), self.bc_xmin)
        io_form.addRow(help_label("BC XMax:", "Boundary condition type for the right domain boundary"), self.bc_xmax)
        io_form.addRow(help_label("BC YMin:", "Boundary condition type for the bottom domain boundary"), self.bc_ymin)
        io_form.addRow(help_label("BC YMax:", "Boundary condition type for the top domain boundary"), self.bc_ymax)
        io_form.addRow(help_label("BC Geom (Wall):", "Boundary condition type assigned to the geometry wall surface"), self.bc_geom)
        io_form.addRow(help_label("Output Filename:", "Base filename for mesh output files (extension .* means all formats)"), self.output_filename)
        io_form.addRow("", help_widget(self.enable_collision_detection, "Enable self-intersection detection during boundary layer generation"))
        io_form.addRow(help_label("Export:", "Export options for outputting mesh files in various formats"), export_layout)
        align_form_labels(io_form, 130)
        self.sec_io.add_layout(io_form)

        # Spacer at the end
        self._layout.addStretch()

        # Connect internal Browse button
        self.add_file_geom_btn.clicked.connect(self._on_browse_geom)
        self.remove_geom_btn.clicked.connect(self._on_remove_geom)

        # Connect BC textChanged signals
        self.bc_xmin.textChanged.connect(self._update_bc_indicators)
        self.bc_xmax.textChanged.connect(self._update_bc_indicators)
        self.bc_ymin.textChanged.connect(self._update_bc_indicators)
        self.bc_ymax.textChanged.connect(self._update_bc_indicators)
        self.bc_geom.textChanged.connect(self._update_bc_indicators)

    def _update_bc_indicators(self):
        """Parse boundary condition texts and update indicator backgrounds accordingly."""
        for edit, indicator in [
            (self.bc_xmin, self.bc_xmin_indicator),
            (self.bc_xmax, self.bc_xmax_indicator),
            (self.bc_ymin, self.bc_ymin_indicator),
            (self.bc_ymax, self.bc_ymax_indicator),
            (self.bc_geom, self.bc_geom_indicator),
        ]:
            val = edit.text().strip().lower()
            color = BC_COLORS.get(val, DEFAULT_BC_COLOR)
            indicator.setStyleSheet(
                f"background-color: {color}; border-radius: 4px; border: 1px solid #333852;"
            )

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
            
        geom_files = []
        for row in range(self.geom_list_widget.count()):
            geom_files.append(self.geom_list_widget.item(row).data(Qt.ItemDataRole.UserRole))
        self.geom_files_changed.emit(geom_files)

    def _on_remove_geom(self):
        """Remove selected geometry file from the list."""
        for item in self.geom_list_widget.selectedItems():
            self.geom_list_widget.takeItem(self.geom_list_widget.row(item))

        geom_files = []
        for row in range(self.geom_list_widget.count()):
            geom_files.append(self.geom_list_widget.item(row).data(Qt.ItemDataRole.UserRole))
        self.geom_files_changed.emit(geom_files)

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
            self.bl_convex_method.setCurrentIndex(1)
        self.bl_fan_nodes.setValue(cfg.bl_fan_nodes)
        self.bl_auto_fan_nodes.setChecked(cfg.bl_auto_fan_nodes)
        self.bl_fan_angle_threshold.setValue(cfg.bl_fan_angle_threshold)
        self.bl_convex_angle_threshold.setValue(cfg.bl_convex_angle_threshold)
        self.bl_para_fallback_angle.setValue(cfg.bl_para_fallback_angle)

        # 5. Concave
        concave_methods = [5]
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
        
        if not cfg.output_filename:
            if not cfg.geom_files:
                default_name = "results/meshes/mesh_cartesian.*"
            elif len(cfg.geom_files) == 1:
                stem = os.path.splitext(os.path.basename(cfg.geom_files[0]))[0]
                default_name = f"results/meshes/mesh_{stem}.*"
            else:
                default_name = "results/meshes/mesh_multiple.*"
            self.output_filename.setText(default_name)
        else:
            self.output_filename.setText(cfg.output_filename)

        self.export_vtk.setChecked(cfg.export_vtk)
        self.export_starcd.setChecked(cfg.export_starcd)
        self.enable_collision_detection.setChecked(cfg.enable_collision_detection)

        # Update canvas preview geometries and config
        self.mesh_config_changed.emit(cfg)

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
        concave_methods = [5]
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

    def _update_convex_widgets_visibility(self):
        method_str = self.bl_convex_method.currentText()
        is_fan = "0: Fan" in method_str

        self.bl_fan_nodes.setVisible(is_fan)
        self.bl_auto_fan_nodes.setVisible(is_fan)
        self.bl_fan_angle_threshold.setVisible(is_fan)

        label_nodes = self.convex_form.labelForField(self.bl_fan_nodes)
        if label_nodes:
            label_nodes.setVisible(is_fan)

        label_threshold = self.convex_form.labelForField(self.bl_fan_angle_threshold)
        if label_threshold:
            label_threshold.setVisible(is_fan)
