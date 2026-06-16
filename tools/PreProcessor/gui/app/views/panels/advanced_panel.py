from __future__ import annotations
from PyQt6.QtWidgets import QFormLayout, QGroupBox, QCheckBox, QLabel
from PyQt6.QtCore import Qt
from app.views.collapsible import CollapsibleSection
from app.utils import SPIN_STYLE, align_form_labels, help_label, help_widget
from app.views.clean_double_spin_box import CleanDoubleSpinBox

class AdvancedPanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Global Settings", start_collapsed=True, parent=parent)

        _spin_style = SPIN_STYLE

        self.global_spline_cb = QCheckBox("Global Spline Smoothing (G1 continuity)")
        self.global_spline_cb.setStyleSheet("color:#a0b0d0; font-size:11px;")
        self.global_spline_cb.setToolTip("Apply cubic spline interpolation across all edges for G1 continuity. Disable for geometries with intentional sharp corners.")
        hint = QLabel("Disable for geometries with true sharp corners.")
        hint.setStyleSheet("color:#6a7aaa; font-size:10px;")
        hint.setWordWrap(True)

        tf_box = QGroupBox("Output Transform")
        tf_box.setStyleSheet(
            "QGroupBox { color:#a0b0d0; border:1px solid #3a4060;"
            "  margin-top:6px; padding-top:6px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }")
        tf_layout = QFormLayout(tf_box)

        self.transform_scale = CleanDoubleSpinBox()
        self.transform_scale.setRange(1e-6, 1e6)
        self.transform_scale.setValue(1.0)
        self.transform_scale.setDecimals(6)
        self.transform_scale.setStyleSheet(_spin_style)
        self.transform_scale.setToolTip("Uniform scale factor about the geometry's bounding-box centre (scales in place)")

        self.transform_rotate = CleanDoubleSpinBox()
        self.transform_rotate.setRange(-360.0, 360.0)
        self.transform_rotate.setDecimals(3)
        self.transform_rotate.setSuffix("  °")
        self.transform_rotate.setStyleSheet(_spin_style)
        self.transform_rotate.setToolTip("Rotation angle (degrees) about the geometry's bounding-box centre (rotates in place)")

        self.transform_tx = CleanDoubleSpinBox()
        self.transform_tx.setRange(-1e9, 1e9)
        self.transform_tx.setDecimals(6)
        self.transform_tx.setStyleSheet(_spin_style)
        self.transform_tx.setToolTip("Horizontal translation offset applied to the resampled geometry output")

        self.transform_ty = CleanDoubleSpinBox()
        self.transform_ty.setRange(-1e9, 1e9)
        self.transform_ty.setDecimals(6)
        self.transform_ty.setStyleSheet(_spin_style)
        self.transform_ty.setToolTip("Vertical translation offset applied to the resampled geometry output")

        tf_layout.addRow(help_label("Scale:", "Uniform scale factor about the geometry's bounding-box centre (scales in place)"), self.transform_scale)
        tf_layout.addRow(help_label("Rotate:", "Rotation angle (degrees) about the geometry's bounding-box centre (rotates in place)"), self.transform_rotate)
        tf_layout.addRow(help_label("Translate X:", "Horizontal translation offset applied to the resampled geometry output"), self.transform_tx)
        tf_layout.addRow(help_label("Translate Y:", "Vertical translation offset applied to the resampled geometry output"), self.transform_ty)
        align_form_labels(tf_layout)

        self.apply_transform_cb = QCheckBox("Enable output transform")
        self.apply_transform_cb.setStyleSheet("color:#a0b0d0;")
        self.apply_transform_cb.setToolTip("Enable or disable the output coordinate transformation")
        tf_box.setEnabled(False)
        self.apply_transform_cb.toggled.connect(tf_box.setEnabled)
        self._transform_box = tf_box

        self.add_widget(help_widget(self.global_spline_cb, "Apply cubic spline interpolation across all edges for G1 continuity. Disable for geometries with intentional sharp corners."))
        self.add_widget(hint)
        self.add_widget(help_widget(self.apply_transform_cb, "Enable or disable the output coordinate transformation"))
        self.add_widget(tf_box)
