from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QSpinBox,
    QCheckBox, QStackedWidget, QLineEdit, QRadioButton, QButtonGroup, QDialog
)
from PyQt6.QtCore import Qt
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels, help_label, help_widget
from app.views.panels.transform_panel import TransformPanel
from app.views.clean_double_spin_box import CleanDoubleSpinBox
from app.views.adjusting_stacked_widget import AdjustingStackedWidget
from app.views.polygon_editor import PolygonEditor
from app.models import shape_spec
from app.views.panels.edge_props_shapes_mixin import EdgePropsShapesMixin
from app.views.panels.edge_props_dist_mixin import EdgePropsDistMixin
from app.views.panels.edge_props_dialogs_mixin import EdgePropsDialogsMixin

class EdgePropsPanel(CollapsibleSection, EdgePropsShapesMixin, EdgePropsDistMixin, EdgePropsDialogsMixin):
    def __init__(self, parent=None):
        super().__init__("Edge Properties", start_collapsed=True, parent=parent)

        self.segment_type_label = QLabel("—")
        self.segment_type_label.setStyleSheet("font-weight: bold; color: #64B5F6;")

        # ── File segment info ─────────────────────────────────────────────
        self._file_seg_label = QLabel("Start: —   End: —")
        self._file_seg_label.setStyleSheet("color:#6a7aaa; font-size:11px;")
        self._file_seg_label.setVisible(False)

        # ── Curve / Shape Properties group (collapsible) ──────────────────
        self._curve_group = CollapsibleSection("Shape", start_collapsed=False)

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
        self.curve_type_combo.setToolTip("Select the geometric shape type for this curve edge")
        self._curve_group.add_widget(self.curve_type_combo)

        # Stacked widget for switching parameters based on curve type.
        # Sizes to the current page so a short shape (e.g. Circle) leaves no
        # dead space below it.
        self.shape_stack = AdjustingStackedWidget()
        self._curve_group.add_widget(self.shape_stack)

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

        # Connect combobox switch
        self.curve_type_combo.currentIndexChanged.connect(self.shape_stack.setCurrentIndex)

        # General curve properties (applicable to all shapes)
        rf = QFormLayout()
        self.curve_n = QSpinBox()
        self.curve_n.setRange(2, 100000)
        self.curve_n.setValue(100)
        self.curve_n.setStyleSheet(SPIN_STYLE)
        self.curve_n.setToolTip("Total number of points to distribute along this edge")
        self.curve_start_node = QSpinBox()
        self.curve_start_node.setRange(-1, 1000000)
        self.curve_start_node.setValue(-1)
        self.curve_start_node.setSpecialValueText("None")
        self.curve_start_node.setStyleSheet(SPIN_STYLE)
        self.curve_start_node.setToolTip("Index of the anchor node at the start (or None for auto)")
        self.curve_end_node = QSpinBox()
        self.curve_end_node.setRange(-1, 1000000)
        self.curve_end_node.setValue(-1)
        self.curve_end_node.setSpecialValueText("None")
        self.curve_end_node.setStyleSheet(SPIN_STYLE)
        self.curve_end_node.setToolTip("Index of the anchor node at the end (or None for auto)")
        rf.addRow(help_label("Node Count:", "Total number of points to distribute along this edge"), self.curve_n)
        rf.addRow(help_label("Start Anchor:", "Index of the anchor node at the start (or None for auto)"), self.curve_start_node)
        rf.addRow(help_label("End Anchor:", "Index of the anchor node at the end (or None for auto)"), self.curve_end_node)

        self._curve_group.add_layout(rf)

        self._curve_group.setVisible(False)

        # ── Strategy ─────────────────────────────────────────────────────
        sf = QFormLayout()
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["uniform", "tanh", "cosine", "curvature", "geometric"])
        self.strategy_combo.setStyleSheet(COMBO_STYLE)
        self.strategy_combo.setToolTip("Point distribution strategy along this edge")
        sf.addRow(help_label("Distribution:", "Point distribution strategy along this edge"), self.strategy_combo)

        self.match_previous_cb = QCheckBox("Match spacing with previous edge")
        self.match_previous_cb.setStyleSheet("color:#a0b0d0; font-size:11px;")
        self.match_previous_cb.setToolTip("Match the end spacing of the previous edge for smooth transitions")

        self.auto_split_angle_sb = CleanDoubleSpinBox()
        self.auto_split_angle_sb.setRange(0.0, 180.0)
        self.auto_split_angle_sb.setValue(30.0)
        self.auto_split_angle_sb.setDecimals(1)
        self.auto_split_angle_sb.setSuffix("°")
        self.auto_split_angle_sb.setStyleSheet(SPIN_STYLE)
        self.auto_split_angle_sb.setToolTip("Angle threshold (degrees) for detecting sharp corners in auto-split")

        self.auto_split_form = QFormLayout()
        self.auto_split_form.addRow(help_label("Detection Angle:", "Angle threshold (degrees) for detecting sharp corners in auto-split"), self.auto_split_angle_sb)

        self.auto_split_btn = make_button("Split at Corners", '#1b2a4a')
        self.auto_split_btn.setToolTip("Split selected edge at sharp corners based on threshold")

        self.param_stack = AdjustingStackedWidget()
        self._setup_param_forms()

        # ── Slim inspector: definition inline, tools in standalone windows ──
        # Header already names the edge & type, so the geometry definition is
        # shown directly beneath it (no collapsible). Distribution / Split /
        # Transform open as separate tool windows to keep the panel compact.
        self.add_widget(self.segment_type_label)
        self.add_widget(self._file_seg_label)
        self.add_widget(self._curve_group)

        # NOTE: "Assign patch / group…" was moved out of this per-edge inspector
        # into the always-visible Edge Actions panel (#1), so grouping acts on the
        # whole selection at once instead of one edge at a time. See
        # app/views/panels/edge_list_panel.py (group_btn).

        # Tool buttons (open standalone windows).
        self.distribution_btn = make_button("Distribution…", '#1b2a4a')
        self.distribution_btn.setToolTip("Set the point distribution for this edge — live preview on the canvas")
        self.split_corner_btn = make_button("Split at Corners…", '#1b2a4a')
        self.split_corner_btn.setToolTip("Split this edge at sharp corners")
        self.transform_btn = make_button("Duplicate & Transform…", '#243a52')
        self.transform_btn.setToolTip("Open the duplicate / transform tools in a separate window")
        self.add_widget(help_widget(self.distribution_btn, "Set the point distribution for this edge — live preview on the canvas"))
        self.add_widget(help_widget(self.split_corner_btn, "Split this edge at sharp corners"))
        self.add_widget(help_widget(self.transform_btn, "Open the duplicate / transform tools in a separate window"))

        def _tool_dialog(title):
            # Parented to this panel → the dialog floats above the MAIN window
            # but not above other applications (no global stay-on-top), and
            # follows the app when you switch away.
            dlg = QDialog(self)
            dlg.setWindowTitle(title)
            dlg.setStyleSheet("background:#121422; color:#cdd6f4;")
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(8, 8, 8, 8)
            lay.setSpacing(4)
            dlg.hide()
            return dlg, lay

        # Distribution window — strategy + params + match-previous + Apply.
        self._distribution_dialog, _qv = _tool_dialog("Edge Distribution")
        _qv.addLayout(sf)
        _qv.addWidget(help_widget(self.match_previous_cb, "Match the end spacing of the previous edge for smooth transitions"))
        _qv.addWidget(self.param_stack)
        self.distribution_apply_btn = make_button("Apply", '#1e4620')
        self.distribution_apply_btn.setToolTip("Apply the distribution and show the resampled result on the canvas")
        _qv.addWidget(help_widget(self.distribution_apply_btn, "Apply the distribution and show the resampled result on the canvas"))

        # Split-at-corners window — detection angle + action.
        self._split_dialog, _sv = _tool_dialog("Split at Corners")
        _sv.addLayout(self.auto_split_form)
        _sv.addWidget(help_widget(self.auto_split_btn, "Split selected edge at sharp corners based on threshold"))

        # Duplicate & Transform window.
        self._transform_dup_group = TransformPanel()
        self._transform_dialog, _tl = _tool_dialog("Duplicate & Transform")
        _tl.addWidget(self._transform_dup_group)

        self.split_corner_btn.clicked.connect(self._open_split_dialog)
        # distribution_btn and transform_btn are wired by the controller (they
        # also start the live canvas preview / transform gizmo).

        # Align form layouts
        for layout in [pf, ef, layout_limits, layout_h_line, layout_v_line,
                       layout_line, layout_circle, layout_tri, layout_quad,
                       rf, sf, self.auto_split_form]:
            align_form_labels(layout)

        # Slightly smaller fonts throughout the inspector for a denser, more
        # industrial feel.
        self.setStyleSheet(
            "QLabel{font-size:11px;} QCheckBox{font-size:11px;}"
            " QGroupBox{font-size:11px;} QGroupBox::title{font-size:11px;}"
            " QSpinBox,QDoubleSpinBox,QLineEdit{font-size:11px;}")

        self.curve_mode_param.toggled.connect(self._on_curve_mode_toggled)

    def show_file_segment(self, start: int, end: int):
        self._file_seg_label.setVisible(True)
        self._curve_group.setVisible(False)
        # Discrete edges are resampled → offer the Distribution tool.
        self.distribution_btn.setVisible(True)
        # The toolbar "Apply" duplicated "Preview" (both run the full resampler),
        # so it is no longer shown — use the toolbar "Preview" for a full preview
        # and the Distribution window's Apply for a single edge.
        if self.file_preview_btn:
            self.file_preview_btn.setVisible(False)
        if self.curve_preview_btn:
            self.curve_preview_btn.setVisible(False)
        self._file_seg_label.setText(f"Start Index: {start}    End Index: {end}")

    def show_curve_segment(self, seg):
        self._file_seg_label.setVisible(False)
        self._curve_group.setVisible(True)
        # Analytic edges set their point count in Definition (Node Count); the
        # resampling-strategy Distribution does not apply to analytic edges.
        self.distribution_btn.setVisible(False)
        self._distribution_dialog.hide()
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

        # Populate shape-specific inputs from the shared param↔widget mapping.
        shape_spec.write_widget_params(self, curve_type, seg.parameters)

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
        if visible:
            # Selecting an edge should surface its properties immediately rather
            # than leaving them behind a collapsed header the user must hunt for.
            self.expand()
        if not visible:
            if self.curve_preview_btn:
                self.curve_preview_btn.setVisible(False)
            if self.file_preview_btn:
                self.file_preview_btn.setVisible(False)

