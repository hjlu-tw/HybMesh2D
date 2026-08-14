from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QCheckBox, QLineEdit, QRadioButton, QButtonGroup
)
from app.utils import SPIN_STYLE, help_label, help_widget
from app.views.clean_double_spin_box import CleanDoubleSpinBox
from app.views.polygon_editor import PolygonEditor
from app.models import shape_spec
from app.models.curve_edit_spec import CurveEditSpec, curve_type_for_index


class EdgePropsShapeBuildMixin:
    """Builds the 9-widget shape stack for EdgePropsPanel, extracted from
    __init__. Runs on the composed panel (uses self.shape_stack + self.*)."""

    def _build_shape_stack(self):
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
        self.curve_x_formula.setToolTip("Mathematical expression for x-coordinate as a function of parameter t")
        self.curve_y_formula = QLineEdit("sin(t)")
        self.curve_y_formula.setToolTip("Mathematical expression for y-coordinate as a function of parameter t")
        self.curve_x_formula.setStyleSheet(SPIN_STYLE)
        self.curve_y_formula.setStyleSheet(SPIN_STYLE)
        pf.addRow(help_label("x(t) =", "Mathematical expression for x-coordinate as a function of parameter t"), self.curve_x_formula)
        pf.addRow(help_label("y(t) =", "Mathematical expression for y-coordinate as a function of parameter t"), self.curve_y_formula)
        layout_custom.addWidget(self._param_widget)

        self._explicit_widget = QWidget()
        ef = QFormLayout(self._explicit_widget)
        ef.setContentsMargins(0, 0, 0, 0)
        self.curve_formula = QLineEdit("sin(x)")
        self.curve_formula.setToolTip("Mathematical expression for y as a function of x")
        self.curve_formula.setStyleSheet(SPIN_STYLE)
        ef.addRow(help_label("y(x) =", "Mathematical expression for y as a function of x"), self.curve_formula)
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
        self.curve_t_min.setToolTip("Start value of the parametric range (t or x)")
        self.curve_t_max = CleanDoubleSpinBox()
        self.curve_t_max.setRange(-1e6, 1e6)
        self.curve_t_max.setDecimals(6)
        self.curve_t_max.setValue(6.283185307)
        self.curve_t_max.setStyleSheet(SPIN_STYLE)
        self.curve_t_max.setToolTip("End value of the parametric range (t or x)")
        layout_limits.addRow(help_label("t / x  min:", "Start value of the parametric range (t or x)"), self.curve_t_min)
        layout_limits.addRow(help_label("t / x  max:", "End value of the parametric range (t or x)"), self.curve_t_max)
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
        self.h_line_y.setToolTip("Y-coordinate of the horizontal line")
        self.h_line_x_start = CleanDoubleSpinBox()
        self.h_line_x_start.setRange(-1e6, 1e6)
        self.h_line_x_start.setDecimals(4)
        self.h_line_x_start.setStyleSheet(SPIN_STYLE)
        self.h_line_x_start.setToolTip("Starting X-coordinate of the horizontal line")
        self.h_line_x_end = CleanDoubleSpinBox()
        self.h_line_x_end.setRange(-1e6, 1e6)
        self.h_line_x_end.setDecimals(4)
        self.h_line_x_end.setStyleSheet(SPIN_STYLE)
        self.h_line_x_end.setToolTip("Ending X-coordinate of the horizontal line")
        layout_h_line.addRow(help_label("Y:", "Y-coordinate of the horizontal line"), self.h_line_y)
        layout_h_line.addRow(help_label("X Start:", "Starting X-coordinate of the horizontal line"), self.h_line_x_start)
        layout_h_line.addRow(help_label("X End:", "Ending X-coordinate of the horizontal line"), self.h_line_x_end)
        self.shape_stack.addWidget(widget_h_line)

        # ── Widget 2: Vertical Line ─────────────────────────────────────
        widget_v_line = QWidget()
        layout_v_line = QFormLayout(widget_v_line)
        layout_v_line.setContentsMargins(0, 0, 0, 0)
        self.v_line_x = CleanDoubleSpinBox()
        self.v_line_x.setRange(-1e6, 1e6)
        self.v_line_x.setDecimals(4)
        self.v_line_x.setStyleSheet(SPIN_STYLE)
        self.v_line_x.setToolTip("X-coordinate of the vertical line")
        self.v_line_y_start = CleanDoubleSpinBox()
        self.v_line_y_start.setRange(-1e6, 1e6)
        self.v_line_y_start.setDecimals(4)
        self.v_line_y_start.setStyleSheet(SPIN_STYLE)
        self.v_line_y_start.setToolTip("Starting Y-coordinate of the vertical line")
        self.v_line_y_end = CleanDoubleSpinBox()
        self.v_line_y_end.setRange(-1e6, 1e6)
        self.v_line_y_end.setDecimals(4)
        self.v_line_y_end.setStyleSheet(SPIN_STYLE)
        self.v_line_y_end.setToolTip("Ending Y-coordinate of the vertical line")
        layout_v_line.addRow(help_label("X:", "X-coordinate of the vertical line"), self.v_line_x)
        layout_v_line.addRow(help_label("Y Start:", "Starting Y-coordinate of the vertical line"), self.v_line_y_start)
        layout_v_line.addRow(help_label("Y End:", "Ending Y-coordinate of the vertical line"), self.v_line_y_end)
        self.shape_stack.addWidget(widget_v_line)

        # ── Widget 3: Line ──────────────────────────────────────────────
        widget_line = QWidget()
        layout_line = QFormLayout(widget_line)
        layout_line.setContentsMargins(0, 0, 0, 0)
        self.line_x0 = CleanDoubleSpinBox()
        self.line_x0.setRange(-1e6, 1e6)
        self.line_x0.setDecimals(4)
        self.line_x0.setStyleSheet(SPIN_STYLE)
        self.line_x0.setToolTip("X-coordinate of the line start point")
        self.line_y0 = CleanDoubleSpinBox()
        self.line_y0.setRange(-1e6, 1e6)
        self.line_y0.setDecimals(4)
        self.line_y0.setStyleSheet(SPIN_STYLE)
        self.line_y0.setToolTip("Y-coordinate of the line start point")
        self.line_x1 = CleanDoubleSpinBox()
        self.line_x1.setRange(-1e6, 1e6)
        self.line_x1.setDecimals(4)
        self.line_x1.setStyleSheet(SPIN_STYLE)
        self.line_x1.setToolTip("X-coordinate of the line end point")
        self.line_y1 = CleanDoubleSpinBox()
        self.line_y1.setRange(-1e6, 1e6)
        self.line_y1.setDecimals(4)
        self.line_y1.setStyleSheet(SPIN_STYLE)
        self.line_y1.setToolTip("Y-coordinate of the line end point")
        layout_line.addRow(help_label("Start:", "Line start point (x, y)"),
                           self._xy_row(self.line_x0, self.line_y0))
        layout_line.addRow(help_label("End:", "Line end point (x, y)"),
                           self._xy_row(self.line_x1, self.line_y1))
        self.shape_stack.addWidget(widget_line)

        # ── Widget 4: Circle ─────────────────────────────────────────────
        widget_circle = QWidget()
        layout_circle = QFormLayout(widget_circle)
        layout_circle.setContentsMargins(0, 0, 0, 0)
        self.circle_cx = CleanDoubleSpinBox()
        self.circle_cx.setRange(-1e6, 1e6)
        self.circle_cx.setDecimals(4)
        self.circle_cx.setStyleSheet(SPIN_STYLE)
        self.circle_cx.setToolTip("X-coordinate of the circle center")
        self.circle_cy = CleanDoubleSpinBox()
        self.circle_cy.setRange(-1e6, 1e6)
        self.circle_cy.setDecimals(4)
        self.circle_cy.setStyleSheet(SPIN_STYLE)
        self.circle_cy.setToolTip("Y-coordinate of the circle center")
        self.circle_r = CleanDoubleSpinBox()
        self.circle_r.setRange(1e-6, 1e6)
        self.circle_r.setDecimals(4)
        self.circle_r.setValue(1.0)
        self.circle_r.setStyleSheet(SPIN_STYLE)
        self.circle_r.setToolTip("Radius of the circle")
        layout_circle.addRow(help_label("Center:", "Circle center (x, y)"),
                             self._xy_row(self.circle_cx, self.circle_cy))
        layout_circle.addRow(help_label("Radius R:", "Radius of the circle"), self.circle_r)
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
        
        layout_tri.addRow(help_label("P0:", "First triangle point (x, y)"),
                          self._xy_row(self.tri_x0, self.tri_y0))
        layout_tri.addRow(help_label("P1:", "Second triangle point (x, y)"),
                          self._xy_row(self.tri_x1, self.tri_y1))
        layout_tri.addRow(help_label("P2:", "Third triangle point (x, y)"),
                          self._xy_row(self.tri_x2, self.tri_y2))
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
        
        layout_quad.addRow(help_label("P0:", "First quad point (x, y)"),
                           self._xy_row(self.quad_x0, self.quad_y0))
        layout_quad.addRow(help_label("P1:", "Second quad point (x, y)"),
                           self._xy_row(self.quad_x1, self.quad_y1))
        layout_quad.addRow(help_label("P2:", "Third quad point (x, y)"),
                           self._xy_row(self.quad_x2, self.quad_y2))
        layout_quad.addRow(help_label("P3:", "Fourth quad point (x, y)"),
                           self._xy_row(self.quad_x3, self.quad_y3))
        self.shape_stack.addWidget(widget_quad)

        # ── Widget 7: Polygon ────────────────────────────────────────────
        widget_poly = QWidget()
        layout_poly = QVBoxLayout(widget_poly)
        layout_poly.setContentsMargins(0, 0, 0, 0)
        layout_poly.setSpacing(2)
        lbl_poly = QLabel("Vertices:")
        lbl_poly.setStyleSheet("color:#a0b0d0; font-size:10px;")
        self.poly_vertices = PolygonEditor("0,0; 1,0; 1,1; 0,1")
        layout_poly.addWidget(help_widget(lbl_poly, "Polygon boundary vertices. Edit in the table, load from a file, generate a regular polygon, or append points by absolute / relative (@dx,dy) / polar (@r<deg) coordinate."))
        layout_poly.addWidget(self.poly_vertices)
        self.shape_stack.addWidget(widget_poly)

        # ── Widget 8: Arc (centre / radius / start & end angle) ──────────
        widget_arc = QWidget()
        layout_arc = QFormLayout(widget_arc)
        layout_arc.setContentsMargins(0, 0, 0, 0)
        self.arc_cx = CleanDoubleSpinBox()
        self.arc_cx.setRange(-1e6, 1e6); self.arc_cx.setDecimals(4)
        self.arc_cx.setStyleSheet(SPIN_STYLE)
        self.arc_cx.setToolTip("X-coordinate of the arc centre")
        self.arc_cy = CleanDoubleSpinBox()
        self.arc_cy.setRange(-1e6, 1e6); self.arc_cy.setDecimals(4)
        self.arc_cy.setStyleSheet(SPIN_STYLE)
        self.arc_cy.setToolTip("Y-coordinate of the arc centre")
        self.arc_r = CleanDoubleSpinBox()
        self.arc_r.setRange(1e-6, 1e6); self.arc_r.setDecimals(4)
        self.arc_r.setValue(1.0); self.arc_r.setStyleSheet(SPIN_STYLE)
        self.arc_r.setToolTip("Radius of the arc")
        self.arc_theta0 = CleanDoubleSpinBox()
        self.arc_theta0.setRange(-720.0, 720.0); self.arc_theta0.setDecimals(2)
        self.arc_theta0.setSuffix("°"); self.arc_theta0.setStyleSheet(SPIN_STYLE)
        self.arc_theta0.setToolTip("Start angle in degrees (0 = +X axis, CCW positive)")
        self.arc_theta1 = CleanDoubleSpinBox()
        self.arc_theta1.setRange(-720.0, 720.0); self.arc_theta1.setDecimals(2)
        self.arc_theta1.setSuffix("°")
        self.arc_theta1.setValue(90.0); self.arc_theta1.setStyleSheet(SPIN_STYLE)
        self.arc_theta1.setToolTip("End angle in degrees (sweep runs from start to end)")
        layout_arc.addRow(help_label("Center:", "Arc centre (x, y)"),
                          self._xy_row(self.arc_cx, self.arc_cy))
        layout_arc.addRow(help_label("Radius R:", "Radius of the arc"), self.arc_r)
        layout_arc.addRow(help_label("Start θ:", "Start angle in degrees"), self.arc_theta0)
        layout_arc.addRow(help_label("End θ:", "End angle in degrees"), self.arc_theta1)
        self.arc_lock_radius = QCheckBox("Lock radius (drag ends = angle only)")
        self.arc_lock_radius.setChecked(True)
        self.arc_lock_radius.setStyleSheet("color:#a0a8c0; font-size:11px;")
        self.arc_lock_radius.setToolTip(
            "When on, dragging an arc END handle changes only its angle (radius "
            "fixed). Drag the MID handle to change the radius. Turn off to let an "
            "end handle re-fit both radius and angle.")
        layout_arc.addRow(help_widget(self.arc_lock_radius,
                          "Dragging an end handle changes only the angle; drag the mid handle to change the radius"))
        self.shape_stack.addWidget(widget_arc)

        # The per-shape QFormLayouts are section-local; return them so __init__
        # can label-align them alongside its own strategy/split forms.
        return [pf, ef, layout_limits, layout_h_line, layout_v_line,
                layout_line, layout_circle, layout_arc, layout_tri, layout_quad]

        # Connect combobox switch

    # ── The analytic-edge form's interface ───────────────────────────────
    def _curve_scalar_widgets(self):
        """The curve fields that are not shape parameters."""
        return [self.curve_t_min, self.curve_t_max, self.curve_n,
                self.curve_start_node, self.curve_end_node, self.curve_spacing]

    def _shape_widgets(self):
        """Every shape-defining widget, taken from shape_spec's own table.

        The wiring used to hand-list thirty-eight spin boxes. shape_spec already
        holds the per-type parameter -> widget mapping that the read/write pair
        uses, so a shape gaining a field is wired by the same edit that gives it
        a parameter, instead of by remembering a second list in a controller.
        """
        names = {attr for attrs in shape_spec.SIDEBAR_ATTRS.values()
                 for attr in attrs.values()}
        return [getattr(self, n) for n in sorted(names) if hasattr(self, n)]

    def wire_curve_edits(self, on_edited, on_type_changed):
        """Collapse every analytic-edge widget into one 'the edge changed'."""
        for w in self._curve_scalar_widgets() + self._shape_widgets():
            w.valueChanged.connect(lambda *_: on_edited())
        for w in (self.curve_x_formula, self.curve_y_formula, self.curve_formula,
                  self.poly_vertices):
            w.textChanged.connect(lambda *_: on_edited())
        self.curve_dist_mode.currentTextChanged.connect(lambda *_: on_edited())
        self.curve_mode_param.toggled.connect(lambda *_: on_type_changed())
        self.curve_type_combo.currentIndexChanged.connect(
            lambda *_: on_type_changed())

    def curve_spec(self) -> CurveEditSpec:
        """What the analytic-edge form currently says."""
        curve_type = curve_type_for_index(self.curve_type_combo.currentIndex())
        shape_params = {}
        if curve_type in shape_spec.SIDEBAR_ATTRS or curve_type == "polygon":
            shape_params = shape_spec.read_widget_params(self, curve_type)
        return CurveEditSpec(
            curve_type=curve_type,
            parametric=self.curve_mode_param.isChecked(),
            x_formula=self.curve_x_formula.text(),
            y_formula=self.curve_y_formula.text(),
            formula=self.curve_formula.text(),
            t_min=self.curve_t_min.value(),
            t_max=self.curve_t_max.value(),
            n_points=self.curve_n.value(),
            start_index=self.curve_start_node.value(),
            end_index=self.curve_end_node.value(),
            shape_params=shape_params,
            by_spacing=self.curve_dist_mode.currentText() == "By Spacing",
            spacing=self.curve_spacing.value(),
        )
