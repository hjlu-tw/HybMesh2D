from __future__ import annotations
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QFormLayout, QComboBox, QStackedWidget, QDoubleSpinBox, QCheckBox, QWidget
from app.utils import make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels

class TransformPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Duplicate & Transform", parent=parent)
        self.setStyleSheet(
            "QGroupBox { color:#a0c0d0; border:1px solid #2a4060;"
            "  margin-top:6px; padding-top:6px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }")
        gl = QVBoxLayout(self)
        gl.setSpacing(4)

        # Transform type combo
        self.dup_type_combo = QComboBox()
        self.dup_type_combo.addItems([
            "Rotate",
            "Mirror Horizontal (flip Y)",
            "Mirror Vertical (flip X)",
            "Mirror Axis (custom)",
            "Point Symmetry",
            "Translate",
            "Scale",
        ])
        self.dup_type_combo.setStyleSheet(COMBO_STYLE)
        gl.addWidget(self.dup_type_combo)

        # Base point selection
        self.dup_base_form = QFormLayout()
        self.dup_base_mode_combo = QComboBox()
        self.dup_base_mode_combo.addItems([
            "Custom (Manual)",
            "Start Point",
            "End Point"
        ])
        self.dup_base_mode_combo.setStyleSheet(COMBO_STYLE)
        self.dup_base_form.addRow("Base Point:", self.dup_base_mode_combo)
        gl.addLayout(self.dup_base_form)

        # Stacked parameter areas per transform type
        self._dup_stack = QStackedWidget()
        gl.addWidget(self._dup_stack)

        def _dspin(lo=-1e9, hi=1e9, val=0.0, dec=4):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setValue(val)
            s.setDecimals(dec)
            s.setStyleSheet(SPIN_STYLE)
            return s

        # 0: Rotate
        w_rot = QWidget()
        fl_rot = QFormLayout(w_rot)
        fl_rot.setContentsMargins(0, 0, 0, 0)
        self.dup_rot_angle = _dspin(-360, 360, 90.0, 3)
        self.dup_rot_angle.setSuffix("  °")
        self.dup_rot_px = _dspin()
        self.dup_rot_py = _dspin()
        fl_rot.addRow("Angle:", self.dup_rot_angle)
        fl_rot.addRow("Pivot X:", self.dup_rot_px)
        fl_rot.addRow("Pivot Y:", self.dup_rot_py)
        self._dup_stack.addWidget(w_rot)

        # 1: Mirror Horizontal (flip Y around pivot_y)
        w_mh = QWidget()
        fl_mh = QFormLayout(w_mh)
        fl_mh.setContentsMargins(0, 0, 0, 0)
        self.dup_mh_py = _dspin()
        fl_mh.addRow("Axis Y:", self.dup_mh_py)
        self._dup_stack.addWidget(w_mh)

        # 2: Mirror Vertical (flip X around pivot_x)
        w_mv = QWidget()
        fl_mv = QFormLayout(w_mv)
        fl_mv.setContentsMargins(0, 0, 0, 0)
        self.dup_mv_px = _dspin()
        fl_mv.addRow("Axis X:", self.dup_mv_px)
        self._dup_stack.addWidget(w_mv)

        # 3: Mirror Axis (arbitrary direction through pivot)
        w_ma = QWidget()
        fl_ma = QFormLayout(w_ma)
        fl_ma.setContentsMargins(0, 0, 0, 0)
        self.dup_ma_px = _dspin()
        self.dup_ma_py = _dspin()
        self.dup_ma_dx = _dspin(val=1.0)
        self.dup_ma_dy = _dspin(val=0.0)
        fl_ma.addRow("Pivot X:", self.dup_ma_px)
        fl_ma.addRow("Pivot Y:", self.dup_ma_py)
        fl_ma.addRow("Dir X:", self.dup_ma_dx)
        fl_ma.addRow("Dir Y:", self.dup_ma_dy)
        self._dup_stack.addWidget(w_ma)

        # 4: Point Symmetry
        w_ps = QWidget()
        fl_ps = QFormLayout(w_ps)
        fl_ps.setContentsMargins(0, 0, 0, 0)
        self.dup_ps_px = _dspin()
        self.dup_ps_py = _dspin()
        fl_ps.addRow("Centre X:", self.dup_ps_px)
        fl_ps.addRow("Centre Y:", self.dup_ps_py)
        self._dup_stack.addWidget(w_ps)

        # 5: Translate
        w_trans = QWidget()
        fl_trans = QFormLayout(w_trans)
        fl_trans.setContentsMargins(0, 0, 0, 0)
        self.dup_trans_dx = _dspin()
        self.dup_trans_dy = _dspin()
        fl_trans.addRow("Shift X:", self.dup_trans_dx)
        fl_trans.addRow("Shift Y:", self.dup_trans_dy)
        self._dup_stack.addWidget(w_trans)

        # 6: Scale
        w_scale = QWidget()
        fl_scale = QFormLayout(w_scale)
        fl_scale.setContentsMargins(0, 0, 0, 0)
        self.dup_scale_factor = _dspin(val=1.0)
        self.dup_scale_px = _dspin()
        self.dup_scale_py = _dspin()
        fl_scale.addRow("Factor:", self.dup_scale_factor)
        fl_scale.addRow("Pivot X:", self.dup_scale_px)
        fl_scale.addRow("Pivot Y:", self.dup_scale_py)
        self._dup_stack.addWidget(w_scale)

        # Connect combo → stack
        self.dup_type_combo.currentIndexChanged.connect(self._dup_stack.setCurrentIndex)

        # Delete original checkbox
        self.dup_delete_orig_cb = QCheckBox("Delete original")
        self.dup_delete_orig_cb.setStyleSheet("color:#a0b0d0; font-size:11px;")
        self.dup_delete_orig_cb.toggled.connect(
            lambda checked: self.dup_btn.setText("Transform Edge" if checked else "Duplicate Edge")
        )
        gl.addWidget(self.dup_delete_orig_cb)

        # Duplicate button
        self.dup_btn = make_button("Duplicate Edge", '#1a3a2a')
        gl.addWidget(self.dup_btn)

        # Align form layouts in duplicate options
        for layout in [self.dup_base_form, fl_rot, fl_mh, fl_mv, fl_ma, fl_ps, fl_trans, fl_scale]:
            align_form_labels(layout)
