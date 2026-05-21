from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QStackedWidget,
    QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox,
    QCheckBox, QScrollArea, QLineEdit, QSizePolicy,
    QRadioButton, QButtonGroup, QFrame
)
from PyQt6.QtCore import Qt
from app.views.collapsible import CollapsibleSection


class SidebarView(QWidget):
    """
    Left-hand control panel — scrollable, grouped into collapsible sections.
    No emoji icons on buttons; muted/dark colour palette.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._combo_style = """
            QComboBox {
                background: #181b2a;
                color: #a0a8c0;
                border: 1px solid #333852;
                border-radius: 3px;
                padding: 3px 20px 3px 6px;
                min-width: 80px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 1px;
                border-left-color: #333852;
                border-left-style: solid;
            }
            QComboBox::down-arrow {
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMCIgaGVpZ2h0PSIxMCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNhMGE4YzAiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSI2IDkgMTIgMTUgMTggOSI+PC9wb2x5bGluZT48L3N2Zz4=");
            }
        """
        self._spin_style = "background:#181b2a; color:#a0a8c0; border:1px solid #333852; padding: 2px;"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: #0c0d16;")

        content = QWidget()
        content.setStyleSheet("background: #121422; color: #a0a8c0;")
        self.layout = QVBoxLayout(content)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(6)

        # Undo / Redo buttons at the very top
        self.undo_btn = self._btn("Undo", '#181b30')
        self.redo_btn = self._btn("Redo", '#181b30')
        self.undo_btn.setToolTip("Undo last action (Ctrl+Z)")
        self.redo_btn.setToolTip("Redo last action (Ctrl+Y)")

        hb = QHBoxLayout()
        hb.setSpacing(6)
        hb.addWidget(self.undo_btn)
        hb.addWidget(self.redo_btn)
        self.layout.addLayout(hb)

        self._build_file_section()
        self._build_geometries_section()
        self._build_split_section()
        self._build_insert_section()
        self._build_segments_section()
        self._build_seg_props_section()
        self._build_advanced_section()
        self._build_actions_section()

        self.layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ── Button style helper ───────────────────────────────────────────────

    @staticmethod
    def _btn(text: str, color: str = '#26293c') -> QPushButton:
        b = QPushButton(text)
        b.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {color}; color: #dde6ff;"
            f"  border: 1px solid #4a5070; border-radius: 4px;"
            f"  padding: 6px 10px; font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{ background-color: #32364e; }}"
            f"QPushButton:disabled {{ background-color: #171926; color: #555; }}")
        return b

    # ═════════════════════════════════════════════════════════════════════
    # Section builders
    # ═════════════════════════════════════════════════════════════════════

    def _build_file_section(self):
        sec = CollapsibleSection("File & Output", start_collapsed=True)
        self.layout.addWidget(sec)

        self.load_btn = self._btn("Load Geometry (.dat)")
        self.load_json_btn = self._btn("Load Config (.json)", '#301540')
        self.new_tab_btn = self._btn("New Empty Tab", '#1a2525')

        self.file_name_label = QLabel("No file loaded")
        self.file_name_label.setStyleSheet(
            "color: #6a7aaa; font-style: italic; margin-bottom: 4px;")
        self.file_name_label.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.is_closed_combo = QComboBox()
        self.is_closed_combo.addItems(["True", "False"])
        self.is_closed_combo.setStyleSheet(self._combo_style)
        form.addRow("Is Closed:", self.is_closed_combo)

        sec.add_widget(self.load_btn)
        sec.add_widget(self.load_json_btn)
        sec.add_widget(self.new_tab_btn)
        sec.add_widget(self.file_name_label)
        sec.add_layout(form)

    def _build_geometries_section(self):
        sec = CollapsibleSection("Loaded Geometries", start_collapsed=True)
        self.layout.addWidget(sec)

        self.geom_list = QListWidget()
        self.geom_list.setMaximumHeight(120)
        self.geom_list.setStyleSheet("""
            QListWidget {
                background: #181b2a;
                color: #8892b0;
                border: 1px solid #333852;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:selected {
                background: #2e3e70;
                color: #ffffff;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background: #20243c;
                color: #dde6ff;
            }
        """)
        self.focus_geom_btn = self._btn("Focus View to Shape", '#102a45')

        sec.add_widget(self.geom_list)
        sec.add_widget(self.focus_geom_btn)

    def _build_split_section(self):
        sec = CollapsibleSection("Split Control", start_collapsed=True)
        self.layout.addWidget(sec)

        self.selected_info = QLabel("Selected Point: None")
        self.selected_info.setStyleSheet(
            "color: #00E5FF; font-weight: bold;")

        self.split_btn = self._btn("Add Split Point", '#102438')
        self.split_btn.setEnabled(False)
        self.remove_split_btn = self._btn("Remove Split Point", '#251010')
        self.remove_split_btn.setEnabled(False)
        self.auto_detect_btn = self._btn("Auto Detect Segments", '#1b2a4a')

        self.keep_vertex_cb = QCheckBox("Keep vertex in geometry")
        self.keep_vertex_cb.setStyleSheet(
            "color: #FF8A65; font-size: 11px;")

        sec.add_widget(self.selected_info)
        sec.add_widget(self.split_btn)
        sec.add_widget(self.remove_split_btn)
        sec.add_widget(self.keep_vertex_cb)
        sec.add_widget(self.auto_detect_btn)

    def _build_insert_section(self):
        sec = CollapsibleSection("Insert Exact Point", start_collapsed=True)
        self.layout.addWidget(sec)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.insert_x = QDoubleSpinBox()
        self.insert_x.setRange(-1e6, 1e6)
        self.insert_x.setDecimals(6)
        self.insert_x.setStyleSheet(
            "background:#181b2a; color:#a0a8c0; border:1px solid #333852;")

        self.insert_y = QDoubleSpinBox()
        self.insert_y.setRange(-1e6, 1e6)
        self.insert_y.setDecimals(6)
        self.insert_y.setStyleSheet(
            "background:#181b2a; color:#a0a8c0; border:1px solid #333852;")

        form.addRow("X:", self.insert_x)
        form.addRow("Y:", self.insert_y)
        self.insert_btn = self._btn("Insert & Split")

        sec.add_layout(form)
        sec.add_widget(self.insert_btn)

    def _build_segments_section(self):
        self._sec_segments = CollapsibleSection("Segments", start_collapsed=True)
        self.layout.addWidget(self._sec_segments)

        self.segment_list = QListWidget()
        self.segment_list.setMaximumHeight(160)
        self.segment_list.setStyleSheet("""
            QListWidget {
                background: #181b2a;
                color: #8892b0;
                border: 1px solid #333852;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:selected {
                background: #2e3e70;
                color: #ffffff;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background: #20243c;
                color: #dde6ff;
            }
        """)

        self.add_curve_seg_btn = self._btn("Add Curve Segment", '#3a180a')

        self._sec_segments.add_widget(self.segment_list)
        self._sec_segments.add_widget(self.add_curve_seg_btn)

    def _build_seg_props_section(self):
        self._sec_seg_props = CollapsibleSection(
            "Segment Properties", start_collapsed=True)
        self.layout.addWidget(self._sec_seg_props)

        _combo_style = self._combo_style
        _spin_style = self._spin_style

        self.segment_type_label = QLabel("—")
        self.segment_type_label.setStyleSheet(
            "font-weight: bold; color: #64B5F6;")

        # ── Curve formula group ───────────────────────────────────────────
        self._curve_group = QGroupBox("Curve Formula")
        self._curve_group.setStyleSheet(
            "QGroupBox { color:#a0b0d0; border:1px solid #3a4060;"
            "  margin-top:6px; padding-top:6px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }")
        cl = QVBoxLayout(self._curve_group)
        cl.setSpacing(4)

        mode_row = QHBoxLayout()
        self.curve_mode_param = QRadioButton("Parametric x(t),y(t)")
        self.curve_mode_explicit = QRadioButton("Explicit y=f(x)")
        self.curve_mode_param.setChecked(True)
        self.curve_mode_param.setStyleSheet("color:#c0c8e0;")
        self.curve_mode_explicit.setStyleSheet("color:#c0c8e0;")
        self._curve_mode_group = QButtonGroup(self)
        self._curve_mode_group.addButton(self.curve_mode_param, 0)
        self._curve_mode_group.addButton(self.curve_mode_explicit, 1)
        mode_row.addWidget(self.curve_mode_param)
        mode_row.addWidget(self.curve_mode_explicit)
        cl.addLayout(mode_row)

        self._param_widget = QWidget()
        pf = QFormLayout(self._param_widget)
        pf.setContentsMargins(0, 0, 0, 0)
        self.curve_x_formula = QLineEdit("cos(t)")
        self.curve_y_formula = QLineEdit("sin(t)")
        self.curve_x_formula.setStyleSheet(_spin_style)
        self.curve_y_formula.setStyleSheet(_spin_style)
        pf.addRow("x(t) =", self.curve_x_formula)
        pf.addRow("y(t) =", self.curve_y_formula)

        self._explicit_widget = QWidget()
        ef = QFormLayout(self._explicit_widget)
        ef.setContentsMargins(0, 0, 0, 0)
        self.curve_formula = QLineEdit("sin(x)")
        self.curve_formula.setStyleSheet(_spin_style)
        ef.addRow("y(x) =", self.curve_formula)
        self._explicit_widget.setVisible(False)

        rf = QFormLayout()
        self.curve_t_min = QDoubleSpinBox()
        self.curve_t_min.setRange(-1e6, 1e6)
        self.curve_t_min.setDecimals(6)
        self.curve_t_min.setValue(0.0)
        self.curve_t_min.setStyleSheet(_spin_style)
        self.curve_t_max = QDoubleSpinBox()
        self.curve_t_max.setRange(-1e6, 1e6)
        self.curve_t_max.setDecimals(6)
        self.curve_t_max.setValue(6.283185307)
        self.curve_t_max.setStyleSheet(_spin_style)
        self.curve_n = QSpinBox()
        self.curve_n.setRange(2, 100000)
        self.curve_n.setValue(100)
        self.curve_n.setStyleSheet(_spin_style)
        rf.addRow("t / x  min:", self.curve_t_min)
        rf.addRow("t / x  max:", self.curve_t_max)
        rf.addRow("Points:", self.curve_n)

        self.curve_preview_btn = self._btn("Preview Formula", '#3a1f00')

        cl.addWidget(self._param_widget)
        cl.addWidget(self._explicit_widget)
        cl.addLayout(rf)
        cl.addWidget(self.curve_preview_btn)

        # ── File segment info ─────────────────────────────────────────────
        self._file_seg_label = QLabel("Start: —   End: —")
        self._file_seg_label.setStyleSheet("color:#6a7aaa; font-size:11px;")
        self._file_seg_label.setVisible(False)
        self._curve_group.setVisible(False)

        # ── Strategy ─────────────────────────────────────────────────────
        sf = QFormLayout()
        sf.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(
            ["uniform", "tanh", "cosine", "curvature", "geometric"])
        self.strategy_combo.setStyleSheet(_combo_style)
        sf.addRow("Strategy:", self.strategy_combo)

        self.match_previous_cb = QCheckBox(
            "Match spacing with previous segment")
        self.match_previous_cb.setStyleSheet(
            "color:#a0b0d0; font-size:11px;")

        self.param_stack = QStackedWidget()
        self._setup_param_forms()

        self._sec_seg_props.add_widget(self.segment_type_label)
        self._sec_seg_props.add_widget(self._file_seg_label)
        self._sec_seg_props.add_widget(self._curve_group)
        self._sec_seg_props.add_layout(sf)
        self._sec_seg_props.add_widget(self.match_previous_cb)
        self._sec_seg_props.add_widget(self.param_stack)

        self.curve_mode_param.toggled.connect(self._on_curve_mode_toggled)

    def _build_advanced_section(self):
        sec = CollapsibleSection("Advanced Settings", start_collapsed=True)
        self.layout.addWidget(sec)

        _spin_style = (
            "background:#181b2a; color:#a0a8c0; border:1px solid #333852;")

        self.global_spline_cb = QCheckBox(
            "Global Spline  (G1 continuity at boundaries)")
        self.global_spline_cb.setStyleSheet("color:#a0b0d0; font-size:11px;")
        hint = QLabel("Disable for geometries with true sharp corners.")
        hint.setStyleSheet("color:#556; font-size:10px;")
        hint.setWordWrap(True)

        tf_box = QGroupBox("Post-process Transform")
        tf_box.setStyleSheet(
            "QGroupBox { color:#a0b0d0; border:1px solid #3a4060;"
            "  margin-top:6px; padding-top:6px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }")
        tf_layout = QFormLayout(tf_box)
        tf_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.transform_scale = QDoubleSpinBox()
        self.transform_scale.setRange(1e-6, 1e6)
        self.transform_scale.setValue(1.0)
        self.transform_scale.setDecimals(6)
        self.transform_scale.setStyleSheet(_spin_style)

        self.transform_rotate = QDoubleSpinBox()
        self.transform_rotate.setRange(-360.0, 360.0)
        self.transform_rotate.setDecimals(3)
        self.transform_rotate.setSuffix("  °")
        self.transform_rotate.setStyleSheet(_spin_style)

        self.transform_tx = QDoubleSpinBox()
        self.transform_tx.setRange(-1e9, 1e9)
        self.transform_tx.setDecimals(6)
        self.transform_tx.setStyleSheet(_spin_style)

        self.transform_ty = QDoubleSpinBox()
        self.transform_ty.setRange(-1e9, 1e9)
        self.transform_ty.setDecimals(6)
        self.transform_ty.setStyleSheet(_spin_style)

        tf_layout.addRow("Scale:", self.transform_scale)
        tf_layout.addRow("Rotate:", self.transform_rotate)
        tf_layout.addRow("Translate X:", self.transform_tx)
        tf_layout.addRow("Translate Y:", self.transform_ty)

        self.apply_transform_cb = QCheckBox("Apply transform on output")
        self.apply_transform_cb.setStyleSheet("color:#a0b0d0;")
        tf_box.setEnabled(False)
        self.apply_transform_cb.toggled.connect(tf_box.setEnabled)
        self._transform_box = tf_box

        sec.add_widget(self.global_spline_cb)
        sec.add_widget(hint)
        sec.add_widget(self.apply_transform_cb)
        sec.add_widget(tf_box)

    def _build_actions_section(self):
        sec = CollapsibleSection("Actions", start_collapsed=True)
        self.layout.addWidget(sec)

        self.preview_btn = self._btn("Preview on Canvas", '#082544')
        self.save_btn = self._btn("Save Output (.dat)", '#062510')
        self.generate_btn = self._btn("Export JSON Config", '#1b1f2a')

        sec.add_widget(self.preview_btn)
        sec.add_widget(self.save_btn)
        sec.add_widget(self.generate_btn)

    # ═════════════════════════════════════════════════════════════════════
    # Parameter form stack
    # ═════════════════════════════════════════════════════════════════════

    def _setup_param_forms(self):
        spin_style = self._spin_style
        combo_style = self._combo_style
        def mk_spin(lo=2, hi=100000, val=50):
            s = QSpinBox()
            s.setRange(lo, hi)
            s.setValue(val)
            s.setStyleSheet(spin_style)
            return s

        def mk_dspin(lo=0.0, hi=1e4, val=1.0, dec=5, step=0.1):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setValue(val)
            s.setDecimals(dec)
            s.setSingleStep(step)
            s.setStyleSheet(spin_style)
            return s

        # 0 — Uniform
        uw = QWidget()
        ul = QFormLayout(uw)
        ul.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.uniform_type_combo = QComboBox()
        self.uniform_type_combo.addItems(
            ["Specify Num Points", "Specify Spacing"])
        self.uniform_type_combo.setStyleSheet(combo_style)
        ul.addRow("Mode:", self.uniform_type_combo)
        self.uniform_n = mk_spin(2, 100000, 50)
        ul.addRow("Num Points:", self.uniform_n)
        self.uniform_spacing = mk_dspin(1e-6, 1e4, 0.1, 5, 0.01)
        self.uniform_spacing.setVisible(False)
        ul.addRow("Spacing (ds):", self.uniform_spacing)
        self._uniform_spacing_label = ul.labelForField(self.uniform_spacing)
        if self._uniform_spacing_label:
            self._uniform_spacing_label.setVisible(False)
        self.uniform_type_combo.currentTextChanged.connect(
            lambda t: self._toggle_uniform_mode(t == "Specify Spacing"))
        self.param_stack.addWidget(uw)

        # 1 — Tanh
        tw = QWidget()
        tl = QFormLayout(tw)
        tl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.tanh_n = mk_spin()
        self.tanh_intensity = mk_dspin(0.1, 10.0, 2.0, 2, 0.1)
        tl.addRow("Num Points:", self.tanh_n)
        tl.addRow("Intensity:", self.tanh_intensity)
        self.param_stack.addWidget(tw)

        # 2 — Cosine
        cw = QWidget()
        cfl = QFormLayout(cw)
        cfl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.cosine_n = mk_spin()
        cfl.addRow("Num Points:", self.cosine_n)
        self.param_stack.addWidget(cw)

        # 3 — Curvature
        kw = QWidget()
        kl = QFormLayout(kw)
        kl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.curv_n = mk_spin()
        self.curv_sens = mk_dspin(0.1, 10.0, 1.5, 2, 0.1)
        kl.addRow("Num Points:", self.curv_n)
        kl.addRow("Sensitivity:", self.curv_sens)
        self.param_stack.addWidget(kw)

        # 4 — Geometric
        gw = QWidget()
        gl2 = QFormLayout(gw)
        gl2.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.geo_n = mk_spin()
        self.geo_ratio = mk_dspin(1.0, 5.0, 1.2, 3, 0.05)
        gl2.addRow("Num Points:", self.geo_n)
        gl2.addRow("Ratio:", self.geo_ratio)
        self.param_stack.addWidget(gw)

    # ═════════════════════════════════════════════════════════════════════
    # Public helpers (called by controller)
    # ═════════════════════════════════════════════════════════════════════

    def switch_param_form(self, strategy_name: str):
        m = {"uniform": 0, "tanh": 1, "cosine": 2, "curvature": 3,
             "geometric": 4}
        if strategy_name in m:
            self.param_stack.setCurrentIndex(m[strategy_name])

    def show_file_segment(self, start: int, end: int):
        self._file_seg_label.setVisible(True)
        self._curve_group.setVisible(False)
        self._file_seg_label.setText(
            f"Start index: {start}    End index: {end}")

    def show_curve_segment(self, seg):
        self._file_seg_label.setVisible(False)
        self._curve_group.setVisible(True)
        is_p = (seg.curve_mode == "parametric")
        self.curve_mode_param.setChecked(is_p)
        self.curve_mode_explicit.setChecked(not is_p)
        self._param_widget.setVisible(is_p)
        self._explicit_widget.setVisible(not is_p)
        self.curve_x_formula.setText(seg.x_formula)
        self.curve_y_formula.setText(seg.y_formula)
        self.curve_formula.setText(seg.formula)
        self.curve_t_min.setValue(seg.t_min)
        self.curve_t_max.setValue(seg.t_max)
        self.curve_n.setValue(seg.parameters.get("n_points", 100))

    def show_segment_props(self, visible: bool):
        if visible:
            self._sec_seg_props.expand()

    def _toggle_uniform_mode(self, is_spacing: bool):
        self.uniform_n.setVisible(not is_spacing)
        lbl = self.uniform_n.parentWidget().layout().labelForField(
            self.uniform_n)
        if lbl:
            lbl.setVisible(not is_spacing)
        self.uniform_spacing.setVisible(is_spacing)
        if self._uniform_spacing_label:
            self._uniform_spacing_label.setVisible(is_spacing)

    def _on_curve_mode_toggled(self, is_parametric: bool):
        self._param_widget.setVisible(is_parametric)
        self._explicit_widget.setVisible(not is_parametric)

    def get_transform_dict(self) -> dict | None:
        if not self.apply_transform_cb.isChecked():
            return None
        return {
            "scale": self.transform_scale.value(),
            "rotate": self.transform_rotate.value(),
            "translate": [self.transform_tx.value(),
                          self.transform_ty.value()],
        }

    def set_transform_from_dict(self, d: dict | None):
        if d:
            self.apply_transform_cb.setChecked(True)
            self.transform_scale.setValue(d.get("scale", 1.0))
            self.transform_rotate.setValue(d.get("rotate", 0.0))
            tr = d.get("translate", [0.0, 0.0])
            self.transform_tx.setValue(tr[0])
            self.transform_ty.setValue(tr[1])
        else:
            self.apply_transform_cb.setChecked(False)
