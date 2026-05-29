from __future__ import annotations
import os
from PyQt6.QtWidgets import QWidget, QFormLayout, QComboBox, QLabel, QCheckBox, QPushButton, QHBoxLayout, QVBoxLayout
from PyQt6.QtCore import pyqtSignal
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, COMBO_STYLE, align_form_labels
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
        super().__init__("Mesh Statistics", start_collapsed=True, parent=parent)

        # ── Rendering Controls ────────────────────────────────────────────
        self.color_mode_combo = QComboBox()
        self.color_mode_combo.addItems([
            "Element Type", 
            "Quality (Aspect Ratio)", 
            "Quality (Skewness)",
            "Uniform"
        ])
        self.color_mode_combo.setStyleSheet(COMBO_STYLE)
        self.color_mode_combo.currentTextChanged.connect(self._on_color_mode_changed)

        # Rendering options checkboxes
        self.show_domain_box_cb = QCheckBox("Show Domain Box")
        self.show_domain_box_cb.setStyleSheet("color: #a0b0d0; font-size: 11px;")
        self.show_domain_box_cb.setChecked(True)
        self.show_domain_box_cb.toggled.connect(self.show_domain_box_toggled.emit)

        self.show_bc_coloring_cb = QCheckBox("Show BC Coloring")
        self.show_bc_coloring_cb.setStyleSheet("color: #a0b0d0; font-size: 11px;")
        self.show_bc_coloring_cb.setChecked(True)
        self.show_bc_coloring_cb.toggled.connect(self.show_bc_coloring_toggled.emit)

        self.show_wireframe_cb = QCheckBox("Show Wireframe")
        self.show_wireframe_cb.setStyleSheet("color: #a0b0d0; font-size: 11px;")
        self.show_wireframe_cb.setChecked(True)
        self.show_wireframe_cb.toggled.connect(self.show_wireframe_toggled.emit)

        self.fit_view_btn = make_button("Fit Mesh to Screen", "#1d2a3a")
        self.fit_view_btn.clicked.connect(self.fit_view_requested.emit)

        # ── Statistics Display labels ─────────────────────────────────────
        self.vrt_label = QLabel("—")
        self.vrt_label.setStyleSheet("color: #dde6ff; font-weight: bold;")
        self.cel_label = QLabel("—")
        self.cel_label.setStyleSheet("color: #dde6ff; font-weight: bold;")
        self.tri_label = QLabel("—")
        self.tri_label.setStyleSheet("color: #64b5f6;")
        self.quad_label = QLabel("—")
        self.quad_label.setStyleSheet("color: #b388ff;")
        self.poly_label = QLabel("—")
        self.poly_label.setStyleSheet("color: #ffd54f;")

        self.bounds_label = QLabel("—")
        self.bounds_label.setStyleSheet("color: #dde6ff; font-size: 11px;")
        self.bounds_label.setWordWrap(True)

        # Quality metrics (Aspect Ratio)
        self.ar_min_label = QLabel("—")
        self.ar_min_label.setStyleSheet("color: #81c784;")
        self.ar_max_label = QLabel("—")
        self.ar_max_label.setStyleSheet("color: #e57373;")
        self.ar_mean_label = QLabel("—")
        self.ar_mean_label.setStyleSheet("color: #ffb74d;")

        # Quality metrics (Skewness)
        self.sk_min_label = QLabel("—")
        self.sk_min_label.setStyleSheet("color: #81c784;")
        self.sk_max_label = QLabel("—")
        self.sk_max_label.setStyleSheet("color: #e57373;")
        self.sk_mean_label = QLabel("—")
        self.sk_mean_label.setStyleSheet("color: #ffb74d;")

        # Layout setup
        ctrls_form = QFormLayout()
        ctrls_form.addRow("Color Mode:", self.color_mode_combo)
        align_form_labels(ctrls_form)

        # Checkboxes layout
        cbs_layout = QVBoxLayout()
        cbs_layout.setSpacing(4)
        cbs_layout.addWidget(self.show_domain_box_cb)
        cbs_layout.addWidget(self.show_bc_coloring_cb)
        cbs_layout.addWidget(self.show_wireframe_cb)

        stats_form = QFormLayout()
        stats_form.addRow("Vertices (VRT):", self.vrt_label)
        stats_form.addRow("Elements (CEL):", self.cel_label)
        stats_form.addRow("  - Triangles:", self.tri_label)
        stats_form.addRow("  - Quadrilaterals:", self.quad_label)
        stats_form.addRow("  - Polygons:", self.poly_label)
        stats_form.addRow("Bounds (X, Y):", self.bounds_label)
        stats_form.addRow("Min Aspect Ratio:", self.ar_min_label)
        stats_form.addRow("Max Aspect Ratio:", self.ar_max_label)
        stats_form.addRow("Mean Aspect Ratio:", self.ar_mean_label)
        stats_form.addRow("Min Skewness:", self.sk_min_label)
        stats_form.addRow("Max Skewness:", self.sk_max_label)
        stats_form.addRow("Mean Skewness:", self.sk_mean_label)
        align_form_labels(stats_form)

        # Add widgets to collapsible container
        self.add_layout(ctrls_form)
        self.add_layout(cbs_layout)
        self.add_widget(self.fit_view_btn)
        
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
        
        exp_layout.addWidget(self.export_vtk_btn)
        exp_layout.addWidget(self.export_star_btn)
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
