from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QSpinBox, QGroupBox,
    QCheckBox, QStackedWidget, QLineEdit, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels
from app.views.panels.transform_panel import TransformPanel
from app.views.clean_double_spin_box import CleanDoubleSpinBox

class EdgePropsPanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Edge Properties", start_collapsed=True, parent=parent)

        self.segment_type_label = QLabel("—")
        self.segment_type_label.setStyleSheet("font-weight: bold; color: #64B5F6;")

        # ── File segment info ─────────────────────────────────────────────
        self._file_seg_label = QLabel("Start: —   End: —")
        self._file_seg_label.setStyleSheet("color:#6a7aaa; font-size:11px;")
        self._file_seg_label.setVisible(False)

        # ── Curve / Shape Properties group ────────────────────────────────
        self._curve_group = QGroupBox("Edge Definition")
        self._curve_group.setStyleSheet(
            "QGroupBox { color:#a0b0d0; border:1px solid #3a4060;"
            "  margin-top:6px; padding-top:6px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }")
        cl = QVBoxLayout(self._curve_group)
        cl.setSpacing(4)

        # Curve Type Selection
        self.curve_type_combo = QComboBox()
        self.curve_type_combo.addItems([
            "Custom Formula",
            "Horizontal Line",
            "Vertical Line",
            "Line",
            "Circle",
            "Triangle",
            "Quadrilateral",
            "Polygon"
        ])
        self.curve_type_combo.setStyleSheet(COMBO_STYLE)
        cl.addWidget(self.curve_type_combo)

        # Stacked widget for switching parameters based on curve type
        self.shape_stack = QStackedWidget()
        cl.addWidget(self.shape_stack)

        # ── Widget 0: Custom Formula ─────────────────────────────────────
        widget_custom = QWidget()
        layout_custom = QVBoxLayout(widget_custom)
        layout_custom.setContentsMargins(0, 0, 0, 0)
        layout_custom.setSpacing(4)

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
        layout_custom.addLayout(mode_row)

        self._param_widget = QWidget()
        pf = QFormLayout(self._param_widget)
        pf.setContentsMargins(0, 0, 0, 0)
        self.curve_x_formula = QLineEdit("cos(t)")
        self.curve_y_formula = QLineEdit("sin(t)")
        self.curve_x_formula.setStyleSheet(SPIN_STYLE)
        self.curve_y_formula.setStyleSheet(SPIN_STYLE)
        pf.addRow("x(t) =", self.curve_x_formula)
        pf.addRow("y(t) =", self.curve_y_formula)
        layout_custom.addWidget(self._param_widget)

        self._explicit_widget = QWidget()
        ef = QFormLayout(self._explicit_widget)
        ef.setContentsMargins(0, 0, 0, 0)
        self.curve_formula = QLineEdit("sin(x)")
        self.curve_formula.setStyleSheet(SPIN_STYLE)
        ef.addRow("y(x) =", self.curve_formula)
        self._explicit_widget.setVisible(False)
        layout_custom.addWidget(self._explicit_widget)

        # Form layout for t/x min/max limits
        self.custom_limits_widget = QWidget()
        layout_limits = QFormLayout(self.custom_limits_widget)
        layout_limits.setContentsMargins(0, 0, 0, 0)
        self.curve_t_min = CleanDoubleSpinBox()
        self.curve_t_min.setRange(-1e6, 1e6)
        self.curve_t_min.setDecimals(6)
        self.curve_t_min.setValue(0.0)
        self.curve_t_min.setStyleSheet(SPIN_STYLE)
        self.curve_t_max = CleanDoubleSpinBox()
        self.curve_t_max.setRange(-1e6, 1e6)
        self.curve_t_max.setDecimals(6)
        self.curve_t_max.setValue(6.283185307)
        self.curve_t_max.setStyleSheet(SPIN_STYLE)
        layout_limits.addRow("t / x  min:", self.curve_t_min)
        layout_limits.addRow("t / x  max:", self.curve_t_max)
        layout_custom.addWidget(self.custom_limits_widget)

        self.shape_stack.addWidget(widget_custom)

        # ── Widget 1: Horizontal Line ───────────────────────────────────
        widget_h_line = QWidget()
        layout_h_line = QFormLayout(widget_h_line)
        layout_h_line.setContentsMargins(0, 0, 0, 0)
        self.h_line_y = CleanDoubleSpinBox()
        self.h_line_y.setRange(-1e6, 1e6)
        self.h_line_y.setDecimals(4)
        self.h_line_y.setStyleSheet(SPIN_STYLE)
        self.h_line_x_start = CleanDoubleSpinBox()
        self.h_line_x_start.setRange(-1e6, 1e6)
        self.h_line_x_start.setDecimals(4)
        self.h_line_x_start.setStyleSheet(SPIN_STYLE)
        self.h_line_x_end = CleanDoubleSpinBox()
        self.h_line_x_end.setRange(-1e6, 1e6)
        self.h_line_x_end.setDecimals(4)
        self.h_line_x_end.setStyleSheet(SPIN_STYLE)
        layout_h_line.addRow("Y:", self.h_line_y)
        layout_h_line.addRow("X Start:", self.h_line_x_start)
        layout_h_line.addRow("X End:", self.h_line_x_end)
        self.shape_stack.addWidget(widget_h_line)

        # ── Widget 2: Vertical Line ─────────────────────────────────────
        widget_v_line = QWidget()
        layout_v_line = QFormLayout(widget_v_line)
        layout_v_line.setContentsMargins(0, 0, 0, 0)
        self.v_line_x = CleanDoubleSpinBox()
        self.v_line_x.setRange(-1e6, 1e6)
        self.v_line_x.setDecimals(4)
        self.v_line_x.setStyleSheet(SPIN_STYLE)
        self.v_line_y_start = CleanDoubleSpinBox()
        self.v_line_y_start.setRange(-1e6, 1e6)
        self.v_line_y_start.setDecimals(4)
        self.v_line_y_start.setStyleSheet(SPIN_STYLE)
        self.v_line_y_end = CleanDoubleSpinBox()
        self.v_line_y_end.setRange(-1e6, 1e6)
        self.v_line_y_end.setDecimals(4)
        self.v_line_y_end.setStyleSheet(SPIN_STYLE)
        layout_v_line.addRow("X:", self.v_line_x)
        layout_v_line.addRow("Y Start:", self.v_line_y_start)
        layout_v_line.addRow("Y End:", self.v_line_y_end)
        self.shape_stack.addWidget(widget_v_line)

        # ── Widget 3: Line ──────────────────────────────────────────────
        widget_line = QWidget()
        layout_line = QFormLayout(widget_line)
        layout_line.setContentsMargins(0, 0, 0, 0)
        self.line_x0 = CleanDoubleSpinBox()
        self.line_x0.setRange(-1e6, 1e6)
        self.line_x0.setDecimals(4)
        self.line_x0.setStyleSheet(SPIN_STYLE)
        self.line_y0 = CleanDoubleSpinBox()
        self.line_y0.setRange(-1e6, 1e6)
        self.line_y0.setDecimals(4)
        self.line_y0.setStyleSheet(SPIN_STYLE)
        self.line_x1 = CleanDoubleSpinBox()
        self.line_x1.setRange(-1e6, 1e6)
        self.line_x1.setDecimals(4)
        self.line_x1.setStyleSheet(SPIN_STYLE)
        self.line_y1 = CleanDoubleSpinBox()
        self.line_y1.setRange(-1e6, 1e6)
        self.line_y1.setDecimals(4)
        self.line_y1.setStyleSheet(SPIN_STYLE)
        layout_line.addRow("X Start:", self.line_x0)
        layout_line.addRow("Y Start:", self.line_y0)
        layout_line.addRow("X End:", self.line_x1)
        layout_line.addRow("Y End:", self.line_y1)
        self.shape_stack.addWidget(widget_line)

        # ── Widget 4: Circle ─────────────────────────────────────────────
        widget_circle = QWidget()
        layout_circle = QFormLayout(widget_circle)
        layout_circle.setContentsMargins(0, 0, 0, 0)
        self.circle_cx = CleanDoubleSpinBox()
        self.circle_cx.setRange(-1e6, 1e6)
        self.circle_cx.setDecimals(4)
        self.circle_cx.setStyleSheet(SPIN_STYLE)
        self.circle_cy = CleanDoubleSpinBox()
        self.circle_cy.setRange(-1e6, 1e6)
        self.circle_cy.setDecimals(4)
        self.circle_cy.setStyleSheet(SPIN_STYLE)
        self.circle_r = CleanDoubleSpinBox()
        self.circle_r.setRange(1e-6, 1e6)
        self.circle_r.setDecimals(4)
        self.circle_r.setValue(1.0)
        self.circle_r.setStyleSheet(SPIN_STYLE)
        layout_circle.addRow("Center X:", self.circle_cx)
        layout_circle.addRow("Center Y:", self.circle_cy)
        layout_circle.addRow("Radius R:", self.circle_r)
        self.shape_stack.addWidget(widget_circle)

        # ── Widget 5: Triangle ───────────────────────────────────────────
        widget_tri = QWidget()
        layout_tri = QFormLayout(widget_tri)
        layout_tri.setContentsMargins(0, 0, 0, 0)
        
        self.tri_x0 = CleanDoubleSpinBox()
        self.tri_x0.setRange(-1e6, 1e6)
        self.tri_x0.setDecimals(4)
        self.tri_x0.setStyleSheet(SPIN_STYLE)
        
        self.tri_y0 = CleanDoubleSpinBox()
        self.tri_y0.setRange(-1e6, 1e6)
        self.tri_y0.setDecimals(4)
        self.tri_y0.setStyleSheet(SPIN_STYLE)
        
        self.tri_x1 = CleanDoubleSpinBox()
        self.tri_x1.setRange(-1e6, 1e6)
        self.tri_x1.setDecimals(4)
        self.tri_x1.setStyleSheet(SPIN_STYLE)
        
        self.tri_y1 = CleanDoubleSpinBox()
        self.tri_y1.setRange(-1e6, 1e6)
        self.tri_y1.setDecimals(4)
        self.tri_y1.setStyleSheet(SPIN_STYLE)
        
        self.tri_x2 = CleanDoubleSpinBox()
        self.tri_x2.setRange(-1e6, 1e6)
        self.tri_x2.setDecimals(4)
        self.tri_x2.setStyleSheet(SPIN_STYLE)
        
        self.tri_y2 = CleanDoubleSpinBox()
        self.tri_y2.setRange(-1e6, 1e6)
        self.tri_y2.setDecimals(4)
        self.tri_y2.setStyleSheet(SPIN_STYLE)
        
        layout_tri.addRow("P0 X:", self.tri_x0)
        layout_tri.addRow("P0 Y:", self.tri_y0)
        layout_tri.addRow("P1 X:", self.tri_x1)
        layout_tri.addRow("P1 Y:", self.tri_y1)
        layout_tri.addRow("P2 X:", self.tri_x2)
        layout_tri.addRow("P2 Y:", self.tri_y2)
        self.shape_stack.addWidget(widget_tri)

        # ── Widget 6: Quadrilateral ──────────────────────────────────────
        widget_quad = QWidget()
        layout_quad = QFormLayout(widget_quad)
        layout_quad.setContentsMargins(0, 0, 0, 0)
        
        self.quad_x0 = CleanDoubleSpinBox()
        self.quad_x0.setRange(-1e6, 1e6)
        self.quad_x0.setDecimals(4)
        self.quad_x0.setStyleSheet(SPIN_STYLE)
        
        self.quad_y0 = CleanDoubleSpinBox()
        self.quad_y0.setRange(-1e6, 1e6)
        self.quad_y0.setDecimals(4)
        self.quad_y0.setStyleSheet(SPIN_STYLE)
        
        self.quad_x1 = CleanDoubleSpinBox()
        self.quad_x1.setRange(-1e6, 1e6)
        self.quad_x1.setDecimals(4)
        self.quad_x1.setStyleSheet(SPIN_STYLE)
        
        self.quad_y1 = CleanDoubleSpinBox()
        self.quad_y1.setRange(-1e6, 1e6)
        self.quad_y1.setDecimals(4)
        self.quad_y1.setStyleSheet(SPIN_STYLE)
        
        self.quad_x2 = CleanDoubleSpinBox()
        self.quad_x2.setRange(-1e6, 1e6)
        self.quad_x2.setDecimals(4)
        self.quad_x2.setStyleSheet(SPIN_STYLE)
        
        self.quad_y2 = CleanDoubleSpinBox()
        self.quad_y2.setRange(-1e6, 1e6)
        self.quad_y2.setDecimals(4)
        self.quad_y2.setStyleSheet(SPIN_STYLE)
        
        self.quad_x3 = CleanDoubleSpinBox()
        self.quad_x3.setRange(-1e6, 1e6)
        self.quad_x3.setDecimals(4)
        self.quad_x3.setStyleSheet(SPIN_STYLE)
        
        self.quad_y3 = CleanDoubleSpinBox()
        self.quad_y3.setRange(-1e6, 1e6)
        self.quad_y3.setDecimals(4)
        self.quad_y3.setStyleSheet(SPIN_STYLE)
        
        layout_quad.addRow("P0 X:", self.quad_x0)
        layout_quad.addRow("P0 Y:", self.quad_y0)
        layout_quad.addRow("P1 X:", self.quad_x1)
        layout_quad.addRow("P1 Y:", self.quad_y1)
        layout_quad.addRow("P2 X:", self.quad_x2)
        layout_quad.addRow("P2 Y:", self.quad_y2)
        layout_quad.addRow("P3 X:", self.quad_x3)
        layout_quad.addRow("P3 Y:", self.quad_y3)
        self.shape_stack.addWidget(widget_quad)

        # ── Widget 7: Polygon ────────────────────────────────────────────
        widget_poly = QWidget()
        layout_poly = QVBoxLayout(widget_poly)
        layout_poly.setContentsMargins(0, 0, 0, 0)
        layout_poly.setSpacing(2)
        lbl_poly = QLabel("Vertices (x,y separated by semicolon):")
        lbl_poly.setStyleSheet("color:#a0b0d0; font-size:10px;")
        self.poly_vertices = QLineEdit("0,0; 1,0; 1,1; 0,1")
        self.poly_vertices.setStyleSheet(SPIN_STYLE)
        layout_poly.addWidget(lbl_poly)
        layout_poly.addWidget(self.poly_vertices)
        self.shape_stack.addWidget(widget_poly)

        # Connect combobox switch
        self.curve_type_combo.currentIndexChanged.connect(self.shape_stack.setCurrentIndex)

        # General curve properties (applicable to all shapes)
        rf = QFormLayout()
        self.curve_n = QSpinBox()
        self.curve_n.setRange(2, 100000)
        self.curve_n.setValue(100)
        self.curve_n.setStyleSheet(SPIN_STYLE)
        self.curve_start_node = QSpinBox()
        self.curve_start_node.setRange(-1, 1000000)
        self.curve_start_node.setValue(-1)
        self.curve_start_node.setSpecialValueText("None")
        self.curve_start_node.setStyleSheet(SPIN_STYLE)
        self.curve_end_node = QSpinBox()
        self.curve_end_node.setRange(-1, 1000000)
        self.curve_end_node.setValue(-1)
        self.curve_end_node.setSpecialValueText("None")
        self.curve_end_node.setStyleSheet(SPIN_STYLE)
        rf.addRow("Node Count:", self.curve_n)
        rf.addRow("Start Anchor:", self.curve_start_node)
        rf.addRow("End Anchor:", self.curve_end_node)

        cl.addLayout(rf)

        self._curve_group.setVisible(False)

        # ── Strategy ─────────────────────────────────────────────────────
        sf = QFormLayout()
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["uniform", "tanh", "cosine", "curvature", "geometric"])
        self.strategy_combo.setStyleSheet(COMBO_STYLE)
        sf.addRow("Distribution:", self.strategy_combo)

        self.match_previous_cb = QCheckBox("Match spacing with previous edge")
        self.match_previous_cb.setStyleSheet("color:#a0b0d0; font-size:11px;")

        self.auto_split_angle_sb = CleanDoubleSpinBox()
        self.auto_split_angle_sb.setRange(0.0, 180.0)
        self.auto_split_angle_sb.setValue(30.0)
        self.auto_split_angle_sb.setDecimals(1)
        self.auto_split_angle_sb.setSuffix("°")
        self.auto_split_angle_sb.setStyleSheet(SPIN_STYLE)

        self.auto_split_form = QFormLayout()
        self.auto_split_form.addRow("Detection Angle:", self.auto_split_angle_sb)

        self.auto_split_btn = make_button("Auto Detect Sub-edges", '#1b2a4a')
        self.auto_split_btn.setToolTip("Split selected edge at sharp corners based on threshold")

        self.param_stack = QStackedWidget()
        self._setup_param_forms()

        # Adding widgets to self (which is CollapsibleSection)
        self.add_widget(self.segment_type_label)
        self.add_widget(self._file_seg_label)
        self.add_widget(self._curve_group)
        self.add_layout(sf)
        self.add_widget(self.match_previous_cb)
        self.add_widget(self.param_stack)

        # Auto-detect sub-edges
        self.add_layout(self.auto_split_form)
        self.add_widget(self.auto_split_btn)

        # Align form layouts
        for layout in [pf, ef, layout_limits, layout_h_line, layout_v_line,
                       layout_line, layout_circle, layout_tri, layout_quad,
                       rf, sf, self.auto_split_form]:
            align_form_labels(layout)

        # ── Duplicate with Transform (only for curve segments) ────────────
        self._transform_dup_group = TransformPanel()
        self._transform_dup_group.setVisible(False)
        self.add_widget(self._transform_dup_group)

        self.curve_mode_param.toggled.connect(self._on_curve_mode_toggled)

    def _setup_param_forms(self):
        spin_style = SPIN_STYLE
        combo_style = COMBO_STYLE
        def mk_spin(lo=2, hi=100000, val=50):
            s = QSpinBox()
            s.setRange(lo, hi)
            s.setValue(val)
            s.setStyleSheet(spin_style)
            return s

        def mk_dspin(lo=0.0, hi=1e4, val=1.0, dec=5, step=0.1):
            s = CleanDoubleSpinBox()
            s.setRange(lo, hi)
            s.setValue(val)
            s.setDecimals(dec)
            s.setSingleStep(step)
            s.setStyleSheet(spin_style)
            return s

        # 0 — Uniform
        uw = QWidget()
        ul = QFormLayout(uw)
        self.uniform_type_combo = QComboBox()
        self.uniform_type_combo.addItems(["By Node Count", "By Spacing"])
        self.uniform_type_combo.setStyleSheet(combo_style)
        ul.addRow("Mode:", self.uniform_type_combo)
        self.uniform_n = mk_spin(2, 100000, 50)
        ul.addRow("Node Count:", self.uniform_n)
        self.uniform_spacing = mk_dspin(1e-6, 1e4, 0.1, 5, 0.01)
        self.uniform_spacing.setVisible(False)
        ul.addRow("Spacing (\u0394s):", self.uniform_spacing)
        self._uniform_spacing_label = ul.labelForField(self.uniform_spacing)
        if self._uniform_spacing_label:
            self._uniform_spacing_label.setVisible(False)
        self.uniform_type_combo.currentTextChanged.connect(
            lambda t: self._toggle_uniform_mode(t == "By Spacing"))
        self.param_stack.addWidget(uw)

        # 1 — Tanh
        tw = QWidget()
        tl = QFormLayout(tw)
        self.tanh_n = mk_spin()
        self.tanh_intensity = mk_dspin(0.1, 10.0, 2.0, 2, 0.1)
        tl.addRow("Node Count:", self.tanh_n)
        tl.addRow("Intensity:", self.tanh_intensity)
        self.param_stack.addWidget(tw)

        # 2 — Cosine
        cw = QWidget()
        cfl = QFormLayout(cw)
        self.cosine_n = mk_spin()
        cfl.addRow("Node Count:", self.cosine_n)
        self.param_stack.addWidget(cw)

        # 3 — Curvature
        kw = QWidget()
        kl = QFormLayout(kw)
        self.curv_n = mk_spin()
        self.curv_sens = mk_dspin(0.1, 10.0, 1.5, 2, 0.1)
        kl.addRow("Node Count:", self.curv_n)
        kl.addRow("Sensitivity:", self.curv_sens)
        self.param_stack.addWidget(kw)

        # 4 — Geometric
        gw = QWidget()
        gl2 = QFormLayout(gw)
        self.geo_n = mk_spin()
        self.geo_ratio = mk_dspin(1.0, 5.0, 1.2, 3, 0.05)
        self.geo_ratio_end = mk_dspin(1.0, 5.0, 1.0, 3, 0.05)
        gl2.addRow("Node Count:", self.geo_n)
        gl2.addRow("Growth Ratio (start):", self.geo_ratio)
        gl2.addRow("Growth Ratio (end):", self.geo_ratio_end)
        _hint = QLabel("Growth ratio = 1.0 \u2192 uniform at end")
        _hint.setStyleSheet("color:#556688; font-size:10px;")
        gl2.addRow("", _hint)
        self.param_stack.addWidget(gw)

        # Align form layouts
        for layout in [ul, tl, cfl, kl, gl2]:
            align_form_labels(layout)

    def switch_param_form(self, strategy_name: str):
        m = {"uniform": 0, "tanh": 1, "cosine": 2, "curvature": 3, "geometric": 4}
        if strategy_name in m:
            self.param_stack.setCurrentIndex(m[strategy_name])

    def show_file_segment(self, start: int, end: int):
        self._file_seg_label.setVisible(True)
        self._curve_group.setVisible(False)
        if self.file_preview_btn:
            self.file_preview_btn.setVisible(True)
        if self.curve_preview_btn:
            self.curve_preview_btn.setVisible(False)
        self._file_seg_label.setText(f"Start Index: {start}    End Index: {end}")

    def show_curve_segment(self, seg):
        self._file_seg_label.setVisible(False)
        self._curve_group.setVisible(True)
        if self.file_preview_btn:
            self.file_preview_btn.setVisible(False)
        if self.curve_preview_btn:
            self.curve_preview_btn.setVisible(True)

        CURVE_TYPES = ["custom", "horizontal_line", "vertical_line", "line", "circle", "triangle", "quadrilateral", "polygon"]
        curve_type = getattr(seg, "curve_type", "custom")
        if curve_type in CURVE_TYPES:
            idx = CURVE_TYPES.index(curve_type)
            self.curve_type_combo.blockSignals(True)
            self.curve_type_combo.setCurrentIndex(idx)
            self.curve_type_combo.blockSignals(False)
            self.shape_stack.setCurrentIndex(idx)
        else:
            self.curve_type_combo.blockSignals(True)
            self.curve_type_combo.setCurrentIndex(0)
            self.curve_type_combo.blockSignals(False)
            self.shape_stack.setCurrentIndex(0)

        # Populate shape specific inputs
        params = seg.parameters
        if curve_type == "horizontal_line":
            self.h_line_y.setValue(params.get("y", 0.0))
            self.h_line_x_start.setValue(params.get("x0", 0.0))
            self.h_line_x_end.setValue(params.get("x1", 1.0))
        elif curve_type == "vertical_line":
            self.v_line_x.setValue(params.get("x", 0.0))
            self.v_line_y_start.setValue(params.get("y0", 0.0))
            self.v_line_y_end.setValue(params.get("y1", 1.0))
        elif curve_type == "line":
            self.line_x0.setValue(params.get("x0", 0.0))
            self.line_y0.setValue(params.get("y0", 0.0))
            self.line_x1.setValue(params.get("x1", 1.0))
            self.line_y1.setValue(params.get("y1", 1.0))
        elif curve_type == "circle":
            self.circle_cx.setValue(params.get("cx", 0.0))
            self.circle_cy.setValue(params.get("cy", 0.0))
            self.circle_r.setValue(params.get("r", 1.0))
        elif curve_type == "triangle":
            self.tri_x0.setValue(params.get("x0", 0.0))
            self.tri_y0.setValue(params.get("y0", 0.0))
            self.tri_x1.setValue(params.get("x1", 1.0))
            self.tri_y1.setValue(params.get("y1", 0.0))
            self.tri_x2.setValue(params.get("x2", 0.5))
            self.tri_y2.setValue(params.get("y2", 1.0))
        elif curve_type == "quadrilateral":
            self.quad_x0.setValue(params.get("x0", 0.0))
            self.quad_y0.setValue(params.get("y0", 0.0))
            self.quad_x1.setValue(params.get("x1", 1.0))
            self.quad_y1.setValue(params.get("y1", 0.0))
            self.quad_x2.setValue(params.get("x2", 1.0))
            self.quad_y2.setValue(params.get("y2", 1.0))
            self.quad_x3.setValue(params.get("x3", 0.0))
            self.quad_y3.setValue(params.get("y3", 1.0))
        elif curve_type == "polygon":
            self.poly_vertices.setText(params.get("vertices_str", "0,0; 1,0; 1,1; 0,1"))

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
        self.curve_start_node.setValue(seg.start_index)
        self.curve_end_node.setValue(seg.end_index)

    def _toggle_uniform_mode(self, is_spacing: bool):
        self.uniform_n.setVisible(not is_spacing)
        lbl = self.uniform_n.parentWidget().layout().labelForField(self.uniform_n)
        if lbl:
            lbl.setVisible(not is_spacing)
        self.uniform_spacing.setVisible(is_spacing)
        if self._uniform_spacing_label:
            self._uniform_spacing_label.setVisible(is_spacing)

    def _on_curve_mode_toggled(self, is_parametric: bool):
        self._param_widget.setVisible(is_parametric)
        self._explicit_widget.setVisible(not is_parametric)

    @property
    def curve_preview_btn(self):
        win = self.window()
        return win.cad_curve_preview_btn if (win and hasattr(win, "cad_curve_preview_btn")) else None

    @property
    def file_preview_btn(self):
        win = self.window()
        return win.cad_file_preview_btn if (win and hasattr(win, "cad_file_preview_btn")) else None

    def show_segment_props(self, visible: bool):
        self.setVisible(visible)
        if not visible:
            if self.curve_preview_btn:
                self.curve_preview_btn.setVisible(False)
            if self.file_preview_btn:
                self.file_preview_btn.setVisible(False)

