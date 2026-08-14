from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QFormLayout, QComboBox, QCheckBox, QWidget
from app.utils import (make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels,
                       block_signals, help_label, help_widget)
from app.models.transform_spec import TransformSpec, kind_for_index
from app.views.clean_double_spin_box import CleanDoubleSpinBox
from app.views.adjusting_stacked_widget import AdjustingStackedWidget

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

        # Stacked parameter areas per transform type (sizes to the current page
        # so a 1-field transform like Mirror Horizontal leaves no dead space).
        self._dup_stack = AdjustingStackedWidget()
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

        # 6: Scale (independent X / Y factors -> uniform when equal,
        #    non-uniform / directional stretch when different)
        w_scale = QWidget()
        fl_scale = QFormLayout(w_scale)
        fl_scale.setContentsMargins(0, 0, 0, 0)
        _sx_tip = ("X scale factor (>1 enlarges, <1 shrinks). Set Scale X ≠ "
                   "Scale Y for a non-uniform / directional stretch.")
        _sy_tip = ("Y scale factor (>1 enlarges, <1 shrinks). Set Scale X ≠ "
                   "Scale Y for a non-uniform / directional stretch.")
        self.dup_scale_sx = _dspin(val=1.0)
        self.dup_scale_sx.setToolTip(_sx_tip)
        self.dup_scale_sy = _dspin(val=1.0)
        self.dup_scale_sy.setToolTip(_sy_tip)
        self.dup_scale_px = _dspin()
        self.dup_scale_px.setToolTip("X-coordinate of the scale pivot point")
        self.dup_scale_py = _dspin()
        self.dup_scale_py.setToolTip("Y-coordinate of the scale pivot point")
        fl_scale.addRow(help_label("Scale X:", _sx_tip), self.dup_scale_sx)
        fl_scale.addRow(help_label("Scale Y:", _sy_tip), self.dup_scale_sy)
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

        # (The base point / mirror axis gizmo and live preview now appear
        # automatically whenever this Duplicate & Transform window is open —
        # no explicit "Edit on Canvas" toggle is needed.)

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

    # ── The Duplicate & Transform form's interface ───────────────────────
    # Two controllers used to read and write these twenty widgets by name. They
    # now exchange a TransformSpec, which is Qt-free and owns the geometry (see
    # models/transform_spec).

    #: Every pivot / axis-position field. Editable only in Custom base mode:
    #: in any other mode they display the computed reference point, and a value
    #: typed into a read-only-by-intent field would be overwritten without
    #: warning on the next recompute.
    _PIVOT_FIELDS = ("dup_rot_px", "dup_rot_py", "dup_mh_py", "dup_mv_px",
                     "dup_ma_px", "dup_ma_py", "dup_ps_px", "dup_ps_py",
                     "dup_scale_px", "dup_scale_py")
    #: Fields that change the transform's result (the mode combos are separate,
    #: since selecting a type is not the same event as editing its parameters).
    _VALUE_FIELDS = _PIVOT_FIELDS + (
        "dup_rot_angle", "dup_ma_dx", "dup_ma_dy",
        "dup_trans_dx", "dup_trans_dy", "dup_scale_sx", "dup_scale_sy")
    #: handle name -> the fields it drives, per transform kind. This table is
    #: view knowledge: which spin box a canvas handle lands in is a property of
    #: the form's layout, not of the drag.
    _HANDLE_FIELDS = {
        ("point", "rotate"): ("dup_rot_px", "dup_rot_py"),
        ("point", "point_symmetry"): ("dup_ps_px", "dup_ps_py"),
        ("point", "scale"): ("dup_scale_px", "dup_scale_py"),
        ("hline", None): (None, "dup_mh_py"),
        ("vline", None): ("dup_mv_px", None),
        ("axis_pivot", None): ("dup_ma_px", "dup_ma_py"),
        ("axis_dir", None): ("dup_ma_dx", "dup_ma_dy"),
        ("translate", None): ("dup_trans_dx", "dup_trans_dy"),
        ("rotate_angle", None): ("dup_rot_angle", None),
    }

    def _widgets(self, names):
        return [getattr(self, n) for n in names if n]

    def wire_transform_edits(self, on_edited, on_type_changed, on_base_mode_changed):
        """Collapse seventeen value widgets into one 'the transform changed'."""
        for w in self._widgets(self._VALUE_FIELDS):
            w.valueChanged.connect(lambda *_: on_edited())
        self.dup_delete_orig_cb.toggled.connect(lambda *_: on_edited())
        self.dup_type_combo.currentIndexChanged.connect(lambda *_: on_type_changed())
        self.dup_base_mode_combo.currentIndexChanged.connect(
            lambda *_: on_base_mode_changed())

    def transform_spec(self) -> TransformSpec:
        """What the Duplicate & Transform form currently says."""
        return TransformSpec(
            kind=kind_for_index(self.dup_type_combo.currentIndex()),
            label=self.dup_type_combo.currentText(),
            base_mode=self.dup_base_mode_combo.currentText(),
            delete_original=self.dup_delete_orig_cb.isChecked(),
            angle_deg=self.dup_rot_angle.value(),
            rot_pivot=(self.dup_rot_px.value(), self.dup_rot_py.value()),
            axis_y=self.dup_mh_py.value(),
            axis_x=self.dup_mv_px.value(),
            axis_pivot=(self.dup_ma_px.value(), self.dup_ma_py.value()),
            axis_dir=(self.dup_ma_dx.value(), self.dup_ma_dy.value()),
            sym_centre=(self.dup_ps_px.value(), self.dup_ps_py.value()),
            delta=(self.dup_trans_dx.value(), self.dup_trans_dy.value()),
            factors=(self.dup_scale_sx.value(), self.dup_scale_sy.value()),
            scale_pivot=(self.dup_scale_px.value(), self.dup_scale_py.value()),
        )

    def set_transform_reference(self, point):
        """Show the reference point every transform will pivot about.

        `point` is None when the user owns it (Custom base mode): the fields
        become editable and keep whatever is in them. A point means the mode
        computed it, so the fields display it and are read-only.
        """
        fields = self._widgets(self._PIVOT_FIELDS)
        editable = point is None
        for w in fields:
            w.setEnabled(editable)
        if editable:
            return
        px, py = point
        with block_signals(*fields):
            for name in self._PIVOT_FIELDS:
                getattr(self, name).setValue(py if name.endswith("_py") else px)

    def set_transform_reference_applicable(self, applicable: bool):
        """Translate is defined by a shift, so it has no base point to choose."""
        self.dup_base_mode_combo.setEnabled(applicable)
        if not applicable:
            self.dup_trans_dx.setEnabled(True)
            self.dup_trans_dy.setEnabled(True)

    def use_custom_transform_reference(self):
        """A manual drag means the user wants a custom reference point."""
        if self.dup_base_mode_combo.currentText() != "Custom (Manual)":
            with block_signals(self.dup_base_mode_combo):
                self.dup_base_mode_combo.setCurrentText("Custom (Manual)")
        for w in self._widgets(self._PIVOT_FIELDS):
            w.setEnabled(True)

    def set_transform_handle(self, handle: str, x: float, y: float) -> bool:
        """Place the canvas handle the user dragged; True if it landed anywhere.

        Silent: a drag already IS the user's edit, so echoing it back through
        valueChanged would re-enter the preview once per mouse move.
        """
        kind = kind_for_index(self.dup_type_combo.currentIndex())
        names = self._HANDLE_FIELDS.get((handle, kind)) \
            or self._HANDLE_FIELDS.get((handle, None))
        if not names:
            return False
        for name, value in zip(names, (x, y)):
            if name:
                with block_signals(getattr(self, name)):
                    getattr(self, name).setValue(value)
        return True
