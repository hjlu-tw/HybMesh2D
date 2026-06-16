from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QFormLayout, QComboBox, QStackedWidget, QCheckBox, QWidget
from app.utils import make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels, help_label, help_widget
from app.views.clean_double_spin_box import CleanDoubleSpinBox

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
        self.dup_type_combo.setToolTip("Select the type of geometric transformation to apply")
        gl.addWidget(help_widget(self.dup_type_combo, "Select the type of geometric transformation to apply"))

        # Base point selection
        self.dup_base_widget = QWidget()
        self.dup_base_form = QFormLayout(self.dup_base_widget)
        self.dup_base_form.setContentsMargins(0, 0, 0, 0)
        self.dup_base_mode_combo = QComboBox()
        self.dup_base_mode_combo.addItems([
            "Center (selection)",
            "Custom (Manual)",
            "Start Point",
            "End Point"
        ])
        self.dup_base_mode_combo.setStyleSheet(COMBO_STYLE)
        _base_tip = ("Reference point for the transform. 'Center (selection)' "
                     "uses the bounding-box centre of all selected edges so "
                     "Rotate/Scale happen in place.")
        self.dup_base_mode_combo.setToolTip(_base_tip)
        self.dup_base_form.addRow(help_label("Base Point:", _base_tip), self.dup_base_mode_combo)
        gl.addWidget(self.dup_base_widget)

        # Stacked parameter areas per transform type
        self._dup_stack = QStackedWidget()
        gl.addWidget(self._dup_stack)

        def _dspin(lo=-1e9, hi=1e9, val=0.0, dec=4):
            s = CleanDoubleSpinBox()
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
        self.dup_rot_angle.setToolTip("Rotation angle in degrees (positive = counter-clockwise)")
        self.dup_rot_px = _dspin()
        self.dup_rot_px.setToolTip("X-coordinate of the rotation pivot point")
        self.dup_rot_py = _dspin()
        self.dup_rot_py.setToolTip("Y-coordinate of the rotation pivot point")
        fl_rot.addRow(help_label("Angle:", "Rotation angle in degrees (positive = counter-clockwise)"), self.dup_rot_angle)
        fl_rot.addRow(help_label("Pivot X:", "X-coordinate of the rotation pivot point"), self.dup_rot_px)
        fl_rot.addRow(help_label("Pivot Y:", "Y-coordinate of the rotation pivot point"), self.dup_rot_py)
        self._dup_stack.addWidget(w_rot)

        # 1: Mirror Horizontal (flip Y around pivot_y)
        w_mh = QWidget()
        fl_mh = QFormLayout(w_mh)
        fl_mh.setContentsMargins(0, 0, 0, 0)
        self.dup_mh_py = _dspin()
        self.dup_mh_py.setToolTip("Y-coordinate of the horizontal mirror axis")
        fl_mh.addRow(help_label("Axis Y:", "Y-coordinate of the horizontal mirror axis"), self.dup_mh_py)
        self._dup_stack.addWidget(w_mh)

        # 2: Mirror Vertical (flip X around pivot_x)
        w_mv = QWidget()
        fl_mv = QFormLayout(w_mv)
        fl_mv.setContentsMargins(0, 0, 0, 0)
        self.dup_mv_px = _dspin()
        self.dup_mv_px.setToolTip("X-coordinate of the vertical mirror axis")
        fl_mv.addRow(help_label("Axis X:", "X-coordinate of the vertical mirror axis"), self.dup_mv_px)
        self._dup_stack.addWidget(w_mv)

        # 3: Mirror Axis (arbitrary direction through pivot)
        w_ma = QWidget()
        fl_ma = QFormLayout(w_ma)
        fl_ma.setContentsMargins(0, 0, 0, 0)
        self.dup_ma_px = _dspin()
        self.dup_ma_px.setToolTip("X-coordinate of the custom mirror axis origin")
        self.dup_ma_py = _dspin()
        self.dup_ma_py.setToolTip("Y-coordinate of the custom mirror axis origin")
        self.dup_ma_dx = _dspin(val=1.0)
        self.dup_ma_dx.setToolTip("X-component of the mirror axis direction vector")
        self.dup_ma_dy = _dspin(val=0.0)
        self.dup_ma_dy.setToolTip("Y-component of the mirror axis direction vector")
        fl_ma.addRow(help_label("Pivot X:", "X-coordinate of the custom mirror axis origin"), self.dup_ma_px)
        fl_ma.addRow(help_label("Pivot Y:", "Y-coordinate of the custom mirror axis origin"), self.dup_ma_py)
        fl_ma.addRow(help_label("Dir X:", "X-component of the mirror axis direction vector"), self.dup_ma_dx)
        fl_ma.addRow(help_label("Dir Y:", "Y-component of the mirror axis direction vector"), self.dup_ma_dy)
        self._dup_stack.addWidget(w_ma)

        # 4: Point Symmetry
        w_ps = QWidget()
        fl_ps = QFormLayout(w_ps)
        fl_ps.setContentsMargins(0, 0, 0, 0)
        self.dup_ps_px = _dspin()
        self.dup_ps_px.setToolTip("X-coordinate of the symmetry center point")
        self.dup_ps_py = _dspin()
        self.dup_ps_py.setToolTip("Y-coordinate of the symmetry center point")
        fl_ps.addRow(help_label("Centre X:", "X-coordinate of the symmetry center point"), self.dup_ps_px)
        fl_ps.addRow(help_label("Centre Y:", "Y-coordinate of the symmetry center point"), self.dup_ps_py)
        self._dup_stack.addWidget(w_ps)

        # 5: Translate
        w_trans = QWidget()
        fl_trans = QFormLayout(w_trans)
        fl_trans.setContentsMargins(0, 0, 0, 0)
        self.dup_trans_dx = _dspin()
        self.dup_trans_dx.setToolTip("Horizontal shift distance")
        self.dup_trans_dy = _dspin()
        self.dup_trans_dy.setToolTip("Vertical shift distance")
        fl_trans.addRow(help_label("Shift X:", "Horizontal shift distance"), self.dup_trans_dx)
        fl_trans.addRow(help_label("Shift Y:", "Vertical shift distance"), self.dup_trans_dy)
        self._dup_stack.addWidget(w_trans)

        # 6: Scale
        w_scale = QWidget()
        fl_scale = QFormLayout(w_scale)
        fl_scale.setContentsMargins(0, 0, 0, 0)
        self.dup_scale_factor = _dspin(val=1.0)
        self.dup_scale_factor.setToolTip("Scale factor (>1 enlarges, <1 shrinks)")
        self.dup_scale_px = _dspin()
        self.dup_scale_px.setToolTip("X-coordinate of the scale pivot point")
        self.dup_scale_py = _dspin()
        self.dup_scale_py.setToolTip("Y-coordinate of the scale pivot point")
        fl_scale.addRow(help_label("Factor:", "Scale factor (>1 enlarges, <1 shrinks)"), self.dup_scale_factor)
        fl_scale.addRow(help_label("Pivot X:", "X-coordinate of the scale pivot point"), self.dup_scale_px)
        fl_scale.addRow(help_label("Pivot Y:", "Y-coordinate of the scale pivot point"), self.dup_scale_py)
        self._dup_stack.addWidget(w_scale)

        # Connect combo → stack
        def _on_type_changed(index: int):
            self._dup_stack.setCurrentIndex(index)
            # Only Translate (5) has no reference point; every other transform
            # (incl. Mirror H/V, whose axis position is a reference point) keeps
            # the Base Point selector so it can snap to the selection centre.
            hide_base = (index == 5)
            self.dup_base_widget.setVisible(not hide_base)
        self.dup_type_combo.currentIndexChanged.connect(_on_type_changed)
        _on_type_changed(self.dup_type_combo.currentIndex())

        # Interactive canvas-editing toggle — the intuitive way to "start":
        # shows the draggable base point / axis and a live result preview.
        _interactive_tip = ("Show the draggable base point / mirror axis and a "
                            "live preview of the result on the canvas. Drag to "
                            "position, then Duplicate / Transform to apply.")
        self.dup_interactive_btn = make_button("✎  Edit on Canvas", '#243a52')
        self.dup_interactive_btn.setCheckable(True)
        self.dup_interactive_btn.setStyleSheet(
            self.dup_interactive_btn.styleSheet()
            + "QPushButton:checked { background-color:#1f6feb;"
              " border-color:#5b9bff; }")
        self.dup_interactive_btn.setToolTip(_interactive_tip)
        gl.addWidget(help_widget(self.dup_interactive_btn, _interactive_tip))

        # Delete original checkbox
        self.dup_delete_orig_cb = QCheckBox("Delete original")
        self.dup_delete_orig_cb.setStyleSheet("color:#a0b0d0; font-size:11px;")
        self.dup_delete_orig_cb.setToolTip("Remove the original edge after transformation (transform instead of duplicate)")
        self.dup_delete_orig_cb.toggled.connect(
            lambda checked: self.dup_btn.setText("Transform Edge" if checked else "Duplicate Edge")
        )
        gl.addWidget(help_widget(self.dup_delete_orig_cb, "Remove the original edge after transformation (transform instead of duplicate)"))

        # Duplicate button
        self.dup_btn = make_button("Duplicate Edge", '#1a3a2a')
        self.dup_btn.setToolTip("Create a transformed copy of the selected edge")
        gl.addWidget(help_widget(self.dup_btn, "Create a transformed copy of the selected edge"))

        # Align form layouts in duplicate options
        for layout in [self.dup_base_form, fl_rot, fl_mh, fl_mv, fl_ma, fl_ps, fl_trans, fl_scale]:
            align_form_labels(layout)
