from __future__ import annotations
import os
from PyQt6.QtWidgets import QWidget, QFormLayout, QComboBox, QLabel, QCheckBox, QPushButton, QHBoxLayout, QVBoxLayout
from PyQt6.QtCore import pyqtSignal
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, COMBO_STYLE, align_form_labels, help_label, help_widget
from app.models.vtk_mesh import VTKMesh

class MeshStatsPanel(CollapsibleSection):
    """Panel displaying mesh statistics and rendering controls."""

    color_mode_changed = pyqtSignal(str)         # Emitted when the color mode is changed
    fit_view_requested = pyqtSignal()            # Emitted when the "Fit View" button is clicked
    show_domain_box_toggled = pyqtSignal(bool)   # Emitted when Show Domain Box checkbox state changes
    show_bc_coloring_toggled = pyqtSignal(bool)  # Emitted when Show BC Coloring checkbox state changes
    show_wireframe_toggled = pyqtSignal(bool)    # Emitted when Show Wireframe checkbox state changes
    export_vtk_requested = pyqtSignal()           # Emitted when user requests VTK export
    export_star_cd_requested = pyqtSignal()       # Emitted when user requests Star-CD export

    def __init__(self, parent=None):
        super().__init__("Mesh Statistics", start_collapsed=False, parent=parent)

        # ── Rendering Controls ────────────────────────────────────────────
        self.color_mode_combo = QComboBox()
        self.color_mode_combo.addItems([
            "Element Type", 
            "Quality (Aspect Ratio)", 
            "Quality (Skewness)",
            "Uniform"
        ])
        self.color_mode_combo.setStyleSheet(COMBO_STYLE)
        self.color_mode_combo.setToolTip("Select the color visualization mode for mesh elements")
        self.color_mode_combo.currentTextChanged.connect(self._on_color_mode_changed)

        # Rendering options checkboxes
        self.show_domain_box_cb = QCheckBox("Show Domain Box")
        self.show_domain_box_cb.setStyleSheet("color: #a0b0d0; font-size: 11px;")
        self.show_domain_box_cb.setChecked(True)
        self.show_domain_box_cb.setToolTip("Toggle visibility of the rectangular domain boundary")
        self.show_domain_box_cb.toggled.connect(self.show_domain_box_toggled.emit)

        self.show_bc_coloring_cb = QCheckBox("Show BC Coloring")
        self.show_bc_coloring_cb.setStyleSheet("color: #a0b0d0; font-size: 11px;")
        self.show_bc_coloring_cb.setChecked(True)
        self.show_bc_coloring_cb.setToolTip("Toggle boundary condition color indicators on edges")
        self.show_bc_coloring_cb.toggled.connect(self.show_bc_coloring_toggled.emit)

        self.show_wireframe_cb = QCheckBox("Show Wireframe")
        self.show_wireframe_cb.setStyleSheet("color: #a0b0d0; font-size: 11px;")
        self.show_wireframe_cb.setChecked(True)
        self.show_wireframe_cb.setToolTip("Toggle mesh wireframe overlay on the canvas")
        self.show_wireframe_cb.toggled.connect(self.show_wireframe_toggled.emit)

        self.fit_view_btn = make_button("Fit Mesh to Screen", "#1d2a3a")
        self.fit_view_btn.clicked.connect(self.fit_view_requested.emit)

        # ── Statistics Display labels ─────────────────────────────────────
        self.vrt_label = QLabel("—")
        self.vrt_label.setStyleSheet("color: #dde6ff; font-weight: bold;")
        self.vrt_label.setToolTip("Total number of mesh vertices (nodes)")
        self.cel_label = QLabel("—")
        self.cel_label.setStyleSheet("color: #dde6ff; font-weight: bold;")
        self.cel_label.setToolTip("Total number of mesh elements (cells)")
        self.tri_label = QLabel("—")
        self.tri_label.setStyleSheet("color: #64b5f6;")
        self.tri_label.setToolTip("Count of triangular elements in the mesh")
        self.quad_label = QLabel("—")
        self.quad_label.setStyleSheet("color: #b388ff;")
        self.quad_label.setToolTip("Count of quadrilateral elements in the mesh")
        self.poly_label = QLabel("—")
        self.poly_label.setStyleSheet("color: #ffd54f;")
        self.poly_label.setToolTip("Count of polygonal elements (5+ sides) in the mesh")

        self.bounds_label = QLabel("—")
        self.bounds_label.setStyleSheet("color: #dde6ff; font-size: 11px;")
        self.bounds_label.setWordWrap(True)
        self.bounds_label.setToolTip("Bounding box coordinates of the mesh (Xmin, Xmax, Ymin, Ymax)")

        # Quality metrics (Aspect Ratio)
        self.ar_min_label = QLabel("—")
        self.ar_min_label.setStyleSheet("color: #81c784;")
        self.ar_min_label.setToolTip("Minimum aspect ratio among all mesh elements (closer to 1.0 is better)")
        self.ar_max_label = QLabel("—")
        self.ar_max_label.setStyleSheet("color: #e57373;")
        self.ar_max_label.setToolTip("Maximum aspect ratio among all mesh elements")
        self.ar_mean_label = QLabel("—")
        self.ar_mean_label.setStyleSheet("color: #ffb74d;")
        self.ar_mean_label.setToolTip("Average aspect ratio across all mesh elements")

        # Quality metrics (Skewness)
        self.sk_min_label = QLabel("—")
        self.sk_min_label.setStyleSheet("color: #81c784;")
        self.sk_min_label.setToolTip("Minimum skewness among all mesh elements (closer to 0.0 is better)")
        self.sk_max_label = QLabel("—")
        self.sk_max_label.setStyleSheet("color: #e57373;")
        self.sk_max_label.setToolTip("Maximum skewness among all mesh elements")
        self.sk_mean_label = QLabel("—")
        self.sk_mean_label.setStyleSheet("color: #ffb74d;")
        self.sk_mean_label.setToolTip("Average skewness across all mesh elements")

        # Layout setup
        ctrls_form = QFormLayout()
        ctrls_form.addRow(help_label("Color Mode:", "Select the color visualization mode for mesh elements"), self.color_mode_combo)
        align_form_labels(ctrls_form)

        # Checkboxes layout
        cbs_layout = QVBoxLayout()
        cbs_layout.setSpacing(4)
        cbs_layout.addWidget(help_widget(self.show_domain_box_cb, "Toggle visibility of the rectangular domain boundary"))
        cbs_layout.addWidget(help_widget(self.show_bc_coloring_cb, "Toggle boundary condition color indicators on edges"))
        cbs_layout.addWidget(help_widget(self.show_wireframe_cb, "Toggle mesh wireframe overlay on the canvas"))

        stats_form = QFormLayout()
        stats_form.addRow(help_label("Vertices (VRT):", "Total number of mesh vertices (nodes)"), self.vrt_label)
        stats_form.addRow(help_label("Elements (CEL):", "Total number of mesh elements (cells)"), self.cel_label)
        stats_form.addRow(help_label("  - Triangles:", "Count of triangular elements in the mesh"), self.tri_label)
        stats_form.addRow(help_label("  - Quadrilaterals:", "Count of quadrilateral elements in the mesh"), self.quad_label)
        stats_form.addRow(help_label("  - Polygons:", "Count of polygonal elements (5+ sides) in the mesh"), self.poly_label)
        stats_form.addRow(help_label("Bounds (X, Y):", "Bounding box coordinates of the mesh (Xmin, Xmax, Ymin, Ymax)"), self.bounds_label)
        stats_form.addRow(help_label("Min Aspect Ratio:", "Minimum aspect ratio among all mesh elements (closer to 1.0 is better)"), self.ar_min_label)
        stats_form.addRow(help_label("Max Aspect Ratio:", "Maximum aspect ratio among all mesh elements"), self.ar_max_label)
        stats_form.addRow(help_label("Mean Aspect Ratio:", "Average aspect ratio across all mesh elements"), self.ar_mean_label)
        stats_form.addRow(help_label("Min Skewness:", "Minimum skewness among all mesh elements (closer to 0.0 is better)"), self.sk_min_label)
        stats_form.addRow(help_label("Max Skewness:", "Maximum skewness among all mesh elements"), self.sk_max_label)
        stats_form.addRow(help_label("Mean Skewness:", "Average skewness across all mesh elements"), self.sk_mean_label)
        align_form_labels(stats_form)

        # Add widgets to collapsible container
        self.add_layout(ctrls_form)
        self.add_layout(cbs_layout)
        self.add_widget(help_widget(self.fit_view_btn, "Fit the mesh view to the canvas boundaries"))
        
        # Spacer/separator
        sep = QLabel("")
        sep.setStyleSheet("border-bottom: 1px solid #2d3345; margin-top: 8px; margin-bottom: 8px;")
        self.add_widget(sep)

        self.add_layout(stats_form)

        # Results Export Section
        sep_exp = QLabel("")
        sep_exp.setStyleSheet("border-bottom: 1px solid #2d3345; margin-top: 8px; margin-bottom: 8px;")
        self.add_widget(sep_exp)

        export_title = QLabel("Results Export")
        export_title.setStyleSheet("font-weight: bold; color: #a0a8c0; margin-bottom: 4px;")
        self.add_widget(export_title)

        self.file_path_label = QLabel("File: No mesh loaded")
        self.file_path_label.setStyleSheet("color: #6b738c; font-size: 10px; margin-bottom: 6px;")
        self.file_path_label.setWordWrap(True)
        self.add_widget(self.file_path_label)

        exp_layout = QHBoxLayout()
        self.export_vtk_btn = make_button("Save VTK...", "#263238")
        self.export_vtk_btn.setToolTip("Export generated VTK mesh to a custom location")
        self.export_vtk_btn.clicked.connect(self.export_vtk_requested.emit)

        self.export_star_btn = make_button("Export Star-CD", "#3e2723")
        self.export_star_btn.setToolTip("Export mesh to Star-CD (.vrt, .cel, .bnd) format")
        self.export_star_btn.clicked.connect(self.export_star_cd_requested.emit)
        
        exp_layout.addWidget(help_widget(self.export_vtk_btn, "Export generated VTK mesh to a custom location"))
        exp_layout.addWidget(help_widget(self.export_star_btn, "Export mesh to Star-CD (.vrt, .cel, .bnd) format"))
        self.add_layout(exp_layout)

    def update_stats(self, mesh: VTKMesh | None, file_path: str = ""):
        """Update statistics display based on the loaded mesh."""
        if file_path:
            self.file_path_label.setText(f"File: {os.path.basename(file_path)}")
            self.file_path_label.setToolTip(file_path)
        else:
            self.file_path_label.setText("File: No mesh loaded")
            self.file_path_label.setToolTip("")

        if not mesh or len(mesh.points) == 0:
            self.vrt_label.setText("—")
            self.cel_label.setText("—")
            self.tri_label.setText("—")
            self.quad_label.setText("—")
            self.poly_label.setText("—")
            self.bounds_label.setText("—")
            self.ar_min_label.setText("—")
            self.ar_max_label.setText("—")
            self.ar_mean_label.setText("—")
            self.sk_min_label.setText("—")
            self.sk_max_label.setText("—")
            self.sk_mean_label.setText("—")
            return

        self.vrt_label.setText(str(len(mesh.points)))
        total_cells = len(mesh.triangles) + len(mesh.quads) + len(mesh.polygons)
        self.cel_label.setText(str(total_cells))
        self.tri_label.setText(str(len(mesh.triangles)))
        self.quad_label.setText(str(len(mesh.quads)))
        self.poly_label.setText(str(len(mesh.polygons)))

        xmin, xmax, ymin, ymax = mesh.bounds
        self.bounds_label.setText(f"X: [{xmin:.4f}, {xmax:.4f}]\nY: [{ymin:.4f}, {ymax:.4f}]")

        ratios = mesh.get_element_aspect_ratios()
        if len(ratios) > 0:
            self.ar_min_label.setText(f"{ratios.min():.3f}")
            self.ar_max_label.setText(f"{ratios.max():.3f}")
            self.ar_mean_label.setText(f"{ratios.mean():.3f}")
        else:
            self.ar_min_label.setText("—")
            self.ar_max_label.setText("—")
            self.ar_mean_label.setText("—")

        skew_vals = mesh.get_element_skewness()
        if len(skew_vals) > 0:
            self.sk_min_label.setText(f"{skew_vals.min():.3f}")
            self.sk_max_label.setText(f"{skew_vals.max():.3f}")
            self.sk_mean_label.setText(f"{skew_vals.mean():.3f}")
        else:
            self.sk_min_label.setText("—")
            self.sk_max_label.setText("—")
            self.sk_mean_label.setText("—")

    def _on_color_mode_changed(self, text: str):
        """Translate combobox selections to mode IDs."""
        mapping = {
            "Element Type": "element_type",
            "Quality (Aspect Ratio)": "quality_aspect",
            "Quality (Skewness)": "quality_skewness",
            "Uniform": "uniform"
        }
        mode = mapping.get(text, "element_type")
        self.color_mode_changed.emit(mode)
