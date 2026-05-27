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
        self._spin_style = "background:#181b2a; color:#a0a8c0; border:1px solid #333852; padding: 2px; max-width: 110px;"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: #0c0d16;")
        scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: #0c0d16;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #2c2e43;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3e415e;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content = QWidget()
        content.setStyleSheet("background: #121422; color: #a0a8c0;")
        self.layout = QVBoxLayout(content)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(6)

        self._build_file_section()
        self._build_geometries_section()

        # Vertex-related categories nested under a parent
        self.sec_vertex_parent = CollapsibleSection("Vertex", start_collapsed=True)
        self.layout.addWidget(self.sec_vertex_parent)
        self._build_split_section()
        self._build_insert_section()

        # Edge-related categories nested under a parent
        self.sec_edge_parent = CollapsibleSection("Edge", start_collapsed=True)
        self.layout.addWidget(self.sec_edge_parent)
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
        sec = CollapsibleSection("Project", start_collapsed=True)
        self.layout.addWidget(sec)

        self.load_btn = self._btn("Import Geometry (.dat)")
        self.load_json_btn = self._btn("Load Configuration (.json)", '#301540')
        self.new_tab_btn = self._btn("New Session", '#1a2525')

        self.file_name_label = QLabel("No geometry imported")
        self.file_name_label.setStyleSheet(
            "color: #6a7aaa; font-style: italic; margin-bottom: 4px;")
        self.file_name_label.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.is_closed_combo = QComboBox()
        self.is_closed_combo.addItems(["True", "False"])
        self.is_closed_combo.setStyleSheet(self._combo_style)
        form.addRow("Closed Curve:", self.is_closed_combo)

        sec.add_widget(self.load_btn)
        sec.add_widget(self.load_json_btn)
        sec.add_widget(self.new_tab_btn)
        sec.add_widget(self.file_name_label)
        sec.add_layout(form)

    def _build_geometries_section(self):
        sec = CollapsibleSection("Geometry Entities", start_collapsed=True)
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
            QListWidget::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #4f5b8c;
                border-radius: 3px;
                background-color: #181b2a;
            }
            QListWidget::indicator:checked {
                background-color: #5a9ad4;
                border-color: #5a9ad4;
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iNCIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSIyMCA2IDkgMTcgNCAxMiI+PC9wb2x5bGluZT48L3N2Zz4=");
            }
            QListWidget::indicator:unchecked:hover {
                border-color: #5a9ad4;
            }
        """)

        self.toggle_visibility_btn = self._btn("Toggle Visibility", '#1a2035')
        self.toggle_visibility_btn.setToolTip(
            "Toggle visibility of the selected geometry on the canvas")

        sec.add_widget(self.geom_list)
        sec.add_widget(self.toggle_visibility_btn)

    def _build_split_section(self):
        sec = CollapsibleSection("Vertex Selection", start_collapsed=True)
        self.sec_vertex_parent.add_widget(sec)

        self.selected_info = QLabel("Selected Vertex: None")
        self.selected_info.setStyleSheet(
            "color: #00E5FF; font-weight: bold;")

        self.split_btn = self._btn("Add Breakpoint", '#102438')
        self.split_btn.setEnabled(False)
        self.remove_split_btn = self._btn("Remove Breakpoint", '#251010')
        self.remove_split_btn.setEnabled(False)
        self.auto_detect_btn = self._btn("Auto Detect Breakpoints", '#1b2a4a')

        self.keep_vertex_cb = QCheckBox("Preserve vertex on removal")
        self.keep_vertex_cb.setStyleSheet(
            "color: #FF8A65; font-size: 11px;")

        sec.add_widget(self.selected_info)
        sec.add_widget(self.split_btn)
        sec.add_widget(self.remove_split_btn)
        sec.add_widget(self.keep_vertex_cb)
        sec.add_widget(self.auto_detect_btn)

    def _build_insert_section(self):
        sec = CollapsibleSection("Insert Vertex", start_collapsed=True)
        self.sec_vertex_parent.add_widget(sec)

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
        self._sec_segments = CollapsibleSection("Edge List", start_collapsed=True)
        self.sec_edge_parent.add_widget(self._sec_segments)

        list_style = """
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
        """

        # Separator/label for geometry segments
        lbl_file = QLabel("Discrete Edges:")
        lbl_file.setStyleSheet("color: #a0c0d0; font-weight: bold; font-size: 11px; margin-top: 4px;")
        
        self.file_segment_list = QListWidget()
        self.file_segment_list.setMaximumHeight(120)
        self.file_segment_list.setStyleSheet(list_style)

        # Separator/label for curve segments
        lbl_curve = QLabel("Analytic Edges:")
        lbl_curve.setStyleSheet("color: #a0c0d0; font-weight: bold; font-size: 11px; margin-top: 6px;")

        self.curve_segment_list = QListWidget()
        self.curve_segment_list.setMaximumHeight(120)
        self.curve_segment_list.setStyleSheet(list_style)

        self.add_curve_seg_btn = self._btn("Add Analytic Edge", '#3a180a')
        self.remove_seg_btn = self._btn("Remove Edge", '#4a1212')
        self.remove_seg_btn.setEnabled(False)
        self.curve_bake_btn = self._btn("Convert to Discrete", '#1b5e20')

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self.add_curve_seg_btn)
        btn_layout.addWidget(self.remove_seg_btn)

        self._sec_segments.add_widget(lbl_file)
        self._sec_segments.add_widget(self.file_segment_list)
        self._sec_segments.add_widget(lbl_curve)
        self._sec_segments.add_widget(self.curve_segment_list)
        self._sec_segments.add_layout(btn_layout)
        self._sec_segments.add_widget(self.curve_bake_btn)

    def _build_seg_props_section(self):
        self._sec_seg_props = CollapsibleSection(
            "Edge Properties", start_collapsed=True)
        self.sec_edge_parent.add_widget(self._sec_seg_props)

        _combo_style = self._combo_style
        _spin_style = self._spin_style

        self.segment_type_label = QLabel("—")
        self.segment_type_label.setStyleSheet(
            "font-weight: bold; color: #64B5F6;")

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
        self.curve_type_combo.setStyleSheet(_combo_style)
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
        self.curve_x_formula.setStyleSheet(_spin_style)
        self.curve_y_formula.setStyleSheet(_spin_style)
        pf.addRow("x(t) =", self.curve_x_formula)
        pf.addRow("y(t) =", self.curve_y_formula)
        layout_custom.addWidget(self._param_widget)

        self._explicit_widget = QWidget()
        ef = QFormLayout(self._explicit_widget)
        ef.setContentsMargins(0, 0, 0, 0)
        self.curve_formula = QLineEdit("sin(x)")
        self.curve_formula.setStyleSheet(_spin_style)
        ef.addRow("y(x) =", self.curve_formula)
        self._explicit_widget.setVisible(False)
        layout_custom.addWidget(self._explicit_widget)

        # Form layout for t/x min/max limits
        self.custom_limits_widget = QWidget()
        layout_limits = QFormLayout(self.custom_limits_widget)
        layout_limits.setContentsMargins(0, 0, 0, 0)
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
        layout_limits.addRow("t / x  min:", self.curve_t_min)
        layout_limits.addRow("t / x  max:", self.curve_t_max)
        layout_custom.addWidget(self.custom_limits_widget)
        
        self.shape_stack.addWidget(widget_custom)

        # ── Widget 1: Horizontal Line ───────────────────────────────────
        widget_h_line = QWidget()
        layout_h_line = QFormLayout(widget_h_line)
        layout_h_line.setContentsMargins(0, 0, 0, 0)
        self.h_line_y = QDoubleSpinBox()
        self.h_line_y.setRange(-1e6, 1e6)
        self.h_line_y.setDecimals(4)
        self.h_line_y.setStyleSheet(_spin_style)
        self.h_line_x_start = QDoubleSpinBox()
        self.h_line_x_start.setRange(-1e6, 1e6)
        self.h_line_x_start.setDecimals(4)
        self.h_line_x_start.setStyleSheet(_spin_style)
        self.h_line_x_end = QDoubleSpinBox()
        self.h_line_x_end.setRange(-1e6, 1e6)
        self.h_line_x_end.setDecimals(4)
        self.h_line_x_end.setStyleSheet(_spin_style)
        layout_h_line.addRow("Y:", self.h_line_y)
        layout_h_line.addRow("X Start:", self.h_line_x_start)
        layout_h_line.addRow("X End:", self.h_line_x_end)
        self.shape_stack.addWidget(widget_h_line)

        # ── Widget 2: Vertical Line ─────────────────────────────────────
        widget_v_line = QWidget()
        layout_v_line = QFormLayout(widget_v_line)
        layout_v_line.setContentsMargins(0, 0, 0, 0)
        self.v_line_x = QDoubleSpinBox()
        self.v_line_x.setRange(-1e6, 1e6)
        self.v_line_x.setDecimals(4)
        self.v_line_x.setStyleSheet(_spin_style)
        self.v_line_y_start = QDoubleSpinBox()
        self.v_line_y_start.setRange(-1e6, 1e6)
        self.v_line_y_start.setDecimals(4)
        self.v_line_y_start.setStyleSheet(_spin_style)
        self.v_line_y_end = QDoubleSpinBox()
        self.v_line_y_end.setRange(-1e6, 1e6)
        self.v_line_y_end.setDecimals(4)
        self.v_line_y_end.setStyleSheet(_spin_style)
        layout_v_line.addRow("X:", self.v_line_x)
        layout_v_line.addRow("Y Start:", self.v_line_y_start)
        layout_v_line.addRow("Y End:", self.v_line_y_end)
        self.shape_stack.addWidget(widget_v_line)

        # ── Widget 3: Line (Diagonal) ───────────────────────────────────
        widget_line = QWidget()
        layout_line = QFormLayout(widget_line)
        layout_line.setContentsMargins(0, 0, 0, 0)
        self.line_x0 = QDoubleSpinBox()
        self.line_x0.setRange(-1e6, 1e6)
        self.line_x0.setDecimals(4)
        self.line_x0.setStyleSheet(_spin_style)
        self.line_y0 = QDoubleSpinBox()
        self.line_y0.setRange(-1e6, 1e6)
        self.line_y0.setDecimals(4)
        self.line_y0.setStyleSheet(_spin_style)
        self.line_x1 = QDoubleSpinBox()
        self.line_x1.setRange(-1e6, 1e6)
        self.line_x1.setDecimals(4)
        self.line_x1.setStyleSheet(_spin_style)
        self.line_y1 = QDoubleSpinBox()
        self.line_y1.setRange(-1e6, 1e6)
        self.line_y1.setDecimals(4)
        self.line_y1.setStyleSheet(_spin_style)
        layout_line.addRow("X Start:", self.line_x0)
        layout_line.addRow("Y Start:", self.line_y0)
        layout_line.addRow("X End:", self.line_x1)
        layout_line.addRow("Y End:", self.line_y1)
        self.shape_stack.addWidget(widget_line)

        # ── Widget 4: Circle ─────────────────────────────────────────────
        widget_circle = QWidget()
        layout_circle = QFormLayout(widget_circle)
        layout_circle.setContentsMargins(0, 0, 0, 0)
        self.circle_cx = QDoubleSpinBox()
        self.circle_cx.setRange(-1e6, 1e6)
        self.circle_cx.setDecimals(4)
        self.circle_cx.setStyleSheet(_spin_style)
        self.circle_cy = QDoubleSpinBox()
        self.circle_cy.setRange(-1e6, 1e6)
        self.circle_cy.setDecimals(4)
        self.circle_cy.setStyleSheet(_spin_style)
        self.circle_r = QDoubleSpinBox()
        self.circle_r.setRange(1e-6, 1e6)
        self.circle_r.setDecimals(4)
        self.circle_r.setValue(1.0)
        self.circle_r.setStyleSheet(_spin_style)
        layout_circle.addRow("Center X:", self.circle_cx)
        layout_circle.addRow("Center Y:", self.circle_cy)
        layout_circle.addRow("Radius R:", self.circle_r)
        self.shape_stack.addWidget(widget_circle)

        # ── Widget 5: Triangle ───────────────────────────────────────────
        widget_tri = QWidget()
        layout_tri = QFormLayout(widget_tri)
        layout_tri.setContentsMargins(0, 0, 0, 0)
        self.tri_x0 = QDoubleSpinBox(); self.tri_x0.setRange(-1e6, 1e6); self.tri_x0.setDecimals(4); self.tri_x0.setStyleSheet(_spin_style)
        self.tri_y0 = QDoubleSpinBox(); self.tri_y0.setRange(-1e6, 1e6); self.tri_y0.setDecimals(4); self.tri_y0.setStyleSheet(_spin_style)
        self.tri_x1 = QDoubleSpinBox(); self.tri_x1.setRange(-1e6, 1e6); self.tri_x1.setDecimals(4); self.tri_x1.setStyleSheet(_spin_style)
        self.tri_y1 = QDoubleSpinBox(); self.tri_y1.setRange(-1e6, 1e6); self.tri_y1.setDecimals(4); self.tri_y1.setStyleSheet(_spin_style)
        self.tri_x2 = QDoubleSpinBox(); self.tri_x2.setRange(-1e6, 1e6); self.tri_x2.setDecimals(4); self.tri_x2.setStyleSheet(_spin_style)
        self.tri_y2 = QDoubleSpinBox(); self.tri_y2.setRange(-1e6, 1e6); self.tri_y2.setDecimals(4); self.tri_y2.setStyleSheet(_spin_style)
        layout_tri.addRow("P0 X:", self.tri_x0); layout_tri.addRow("P0 Y:", self.tri_y0)
        layout_tri.addRow("P1 X:", self.tri_x1); layout_tri.addRow("P1 Y:", self.tri_y1)
        layout_tri.addRow("P2 X:", self.tri_x2); layout_tri.addRow("P2 Y:", self.tri_y2)
        self.shape_stack.addWidget(widget_tri)

        # ── Widget 6: Quadrilateral ──────────────────────────────────────
        widget_quad = QWidget()
        layout_quad = QFormLayout(widget_quad)
        layout_quad.setContentsMargins(0, 0, 0, 0)
        self.quad_x0 = QDoubleSpinBox(); self.quad_x0.setRange(-1e6, 1e6); self.quad_x0.setDecimals(4); self.quad_x0.setStyleSheet(_spin_style)
        self.quad_y0 = QDoubleSpinBox(); self.quad_y0.setRange(-1e6, 1e6); self.quad_y0.setDecimals(4); self.quad_y0.setStyleSheet(_spin_style)
        self.quad_x1 = QDoubleSpinBox(); self.quad_x1.setRange(-1e6, 1e6); self.quad_x1.setDecimals(4); self.quad_x1.setStyleSheet(_spin_style)
        self.quad_y1 = QDoubleSpinBox(); self.quad_y1.setRange(-1e6, 1e6); self.quad_y1.setDecimals(4); self.quad_y1.setStyleSheet(_spin_style)
        self.quad_x2 = QDoubleSpinBox(); self.quad_x2.setRange(-1e6, 1e6); self.quad_x2.setDecimals(4); self.quad_x2.setStyleSheet(_spin_style)
        self.quad_y2 = QDoubleSpinBox(); self.quad_y2.setRange(-1e6, 1e6); self.quad_y2.setDecimals(4); self.quad_y2.setStyleSheet(_spin_style)
        self.quad_x3 = QDoubleSpinBox(); self.quad_x3.setRange(-1e6, 1e6); self.quad_x3.setDecimals(4); self.quad_x3.setStyleSheet(_spin_style)
        self.quad_y3 = QDoubleSpinBox(); self.quad_y3.setRange(-1e6, 1e6); self.quad_y3.setDecimals(4); self.quad_y3.setStyleSheet(_spin_style)
        layout_quad.addRow("P0 X:", self.quad_x0); layout_quad.addRow("P0 Y:", self.quad_y0)
        layout_quad.addRow("P1 X:", self.quad_x1); layout_quad.addRow("P1 Y:", self.quad_y1)
        layout_quad.addRow("P2 X:", self.quad_x2); layout_quad.addRow("P2 Y:", self.quad_y2)
        layout_quad.addRow("P3 X:", self.quad_x3); layout_quad.addRow("P3 Y:", self.quad_y3)
        self.shape_stack.addWidget(widget_quad)

        # ── Widget 7: Polygon ────────────────────────────────────────────
        widget_poly = QWidget()
        layout_poly = QVBoxLayout(widget_poly)
        layout_poly.setContentsMargins(0, 0, 0, 0)
        layout_poly.setSpacing(2)
        lbl_poly = QLabel("Vertices (x,y separated by semicolon):")
        lbl_poly.setStyleSheet("color:#a0b0d0; font-size:10px;")
        self.poly_vertices = QLineEdit("0,0; 1,0; 1,1; 0,1")
        self.poly_vertices.setStyleSheet(_spin_style)
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
        self.curve_n.setStyleSheet(_spin_style)
        self.curve_start_node = QSpinBox()
        self.curve_start_node.setRange(-1, 1000000)
        self.curve_start_node.setValue(-1)
        self.curve_start_node.setSpecialValueText("None")
        self.curve_start_node.setStyleSheet(_spin_style)
        self.curve_end_node = QSpinBox()
        self.curve_end_node.setRange(-1, 1000000)
        self.curve_end_node.setValue(-1)
        self.curve_end_node.setSpecialValueText("None")
        self.curve_end_node.setStyleSheet(_spin_style)
        rf.addRow("Node Count:", self.curve_n)
        rf.addRow("Start Anchor:", self.curve_start_node)
        rf.addRow("End Anchor:", self.curve_end_node)

        self.curve_preview_btn = self._btn("Preview Edge", '#3a1f00')

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
        sf.addRow("Distribution:", self.strategy_combo)

        self.match_previous_cb = QCheckBox(
            "Match spacing with previous edge")
        self.match_previous_cb.setStyleSheet(
            "color:#a0b0d0; font-size:11px;")

        self.auto_split_angle_sb = QDoubleSpinBox()
        self.auto_split_angle_sb.setRange(0.0, 180.0)
        self.auto_split_angle_sb.setValue(30.0)
        self.auto_split_angle_sb.setDecimals(1)
        self.auto_split_angle_sb.setSuffix("°")
        self.auto_split_angle_sb.setStyleSheet(_spin_style)

        self.auto_split_form = QFormLayout()
        self.auto_split_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.auto_split_form.addRow("Detection Angle:", self.auto_split_angle_sb)

        self.auto_split_btn = self._btn("Auto Detect Sub-edges", '#1b2a4a')
        self.auto_split_btn.setToolTip("Split selected edge at sharp corners based on threshold")

        self.param_stack = QStackedWidget()
        self._setup_param_forms()

        self.file_preview_btn = self._btn("Apply & Preview", '#082544')
        self.file_preview_btn.setVisible(False)

        self._sec_seg_props.add_widget(self.segment_type_label)
        self._sec_seg_props.add_widget(self._file_seg_label)
        self._sec_seg_props.add_widget(self._curve_group)
        self._sec_seg_props.add_layout(sf)
        self._sec_seg_props.add_widget(self.match_previous_cb)
        self._sec_seg_props.add_widget(self.param_stack)
        self._sec_seg_props.add_widget(self.file_preview_btn)

        # Auto-detect sub-edges is placed below distribution parameters
        self._sec_seg_props.add_layout(self.auto_split_form)
        self._sec_seg_props.add_widget(self.auto_split_btn)

        # Align form layouts in properties
        for layout in [pf, ef, layout_limits, layout_h_line, layout_v_line,
                       layout_line, layout_circle, layout_tri, layout_quad,
                       rf, sf, self.auto_split_form]:
            self._align_form_labels(layout)

        # ── Duplicate with Transform (only for curve segments) ────────────
        self._transform_dup_group = self._build_transform_group(_spin_style, _combo_style)
        self._transform_dup_group.setVisible(False)
        self._sec_seg_props.add_widget(self._transform_dup_group)

        self.curve_mode_param.toggled.connect(self._on_curve_mode_toggled)

    def _build_transform_group(self, spin_style: str, combo_style: str) -> QGroupBox:
        """Build the 'Duplicate with Transform' group box for curve segments."""
        grp = QGroupBox("Duplicate \u0026 Transform")
        grp.setStyleSheet(
            "QGroupBox { color:#a0c0d0; border:1px solid #2a4060;"
            "  margin-top:6px; padding-top:6px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }")
        gl = QVBoxLayout(grp)
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
        self.dup_type_combo.setStyleSheet(combo_style)
        gl.addWidget(self.dup_type_combo)

        # Base point selection
        self.dup_base_form = QFormLayout()
        self.dup_base_mode_combo = QComboBox()
        self.dup_base_mode_combo.addItems([
            "Custom (Manual)",
            "Start Point",
            "End Point"
        ])
        self.dup_base_mode_combo.setStyleSheet(combo_style)
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
            s.setStyleSheet(spin_style)
            return s

        # ── 0: Rotate ────────────────────────────────────────────────────
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

        # ── 1: Mirror Horizontal (flip Y around pivot_y) ────────────────
        w_mh = QWidget()
        fl_mh = QFormLayout(w_mh)
        fl_mh.setContentsMargins(0, 0, 0, 0)
        self.dup_mh_py = _dspin()
        fl_mh.addRow("Axis Y:", self.dup_mh_py)
        self._dup_stack.addWidget(w_mh)

        # ── 2: Mirror Vertical (flip X around pivot_x) ──────────────────
        w_mv = QWidget()
        fl_mv = QFormLayout(w_mv)
        fl_mv.setContentsMargins(0, 0, 0, 0)
        self.dup_mv_px = _dspin()
        fl_mv.addRow("Axis X:", self.dup_mv_px)
        self._dup_stack.addWidget(w_mv)

        # ── 3: Mirror Axis (arbitrary direction through pivot) ───────────
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

        # ── 4: Point Symmetry ───────────────────────────────────────────
        w_ps = QWidget()
        fl_ps = QFormLayout(w_ps)
        fl_ps.setContentsMargins(0, 0, 0, 0)
        self.dup_ps_px = _dspin()
        self.dup_ps_py = _dspin()
        fl_ps.addRow("Centre X:", self.dup_ps_px)
        fl_ps.addRow("Centre Y:", self.dup_ps_py)
        self._dup_stack.addWidget(w_ps)

        # ── 5: Translate ─────────────────────────────────────────────────
        w_trans = QWidget()
        fl_trans = QFormLayout(w_trans)
        fl_trans.setContentsMargins(0, 0, 0, 0)
        self.dup_trans_dx = _dspin()
        self.dup_trans_dy = _dspin()
        fl_trans.addRow("Shift X:", self.dup_trans_dx)
        fl_trans.addRow("Shift Y:", self.dup_trans_dy)
        self._dup_stack.addWidget(w_trans)

        # ── 6: Scale ─────────────────────────────────────────────────────
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
        self.dup_btn = self._btn("Duplicate Edge", '#1a3a2a')
        gl.addWidget(self.dup_btn)

        # Align form layouts in duplicate options
        for layout in [self.dup_base_form, fl_rot, fl_mh, fl_mv, fl_ma, fl_ps, fl_trans, fl_scale]:
            self._align_form_labels(layout)

        return grp


    def _build_advanced_section(self):
        sec = CollapsibleSection("Global Settings", start_collapsed=True)
        self.layout.addWidget(sec)

        _spin_style = (
            "background:#181b2a; color:#a0a8c0; border:1px solid #333852; max-width: 110px;")

        self.global_spline_cb = QCheckBox(
            "Global Spline Smoothing (G1 continuity)")
        self.global_spline_cb.setStyleSheet("color:#a0b0d0; font-size:11px;")
        hint = QLabel("Disable for geometries with true sharp corners.")
        hint.setStyleSheet("color:#556; font-size:10px;")
        hint.setWordWrap(True)

        self.quality_check_cb = QCheckBox("Show Quality Heatmap")
        self.quality_check_cb.setStyleSheet("color:#a0b0d0; font-size:11px;")

        self.show_vertices_cb = QCheckBox("Show Geometry Vertices")
        self.show_vertices_cb.setStyleSheet("color:#a0b0d0; font-size:11px;")
        self.show_vertices_cb.setChecked(True)

        tf_box = QGroupBox("Output Transform")
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

        self.apply_transform_cb = QCheckBox("Enable output transform")
        self.apply_transform_cb.setStyleSheet("color:#a0b0d0;")
        tf_box.setEnabled(False)
        self.apply_transform_cb.toggled.connect(tf_box.setEnabled)
        self._transform_box = tf_box

        sec.add_widget(self.global_spline_cb)
        sec.add_widget(hint)
        sec.add_widget(self.apply_transform_cb)
        sec.add_widget(tf_box)

    def _build_actions_section(self):
        sec = CollapsibleSection("Output", start_collapsed=True)
        self.layout.addWidget(sec)

        self.preview_btn = self._btn("Run & Preview", '#082544')
        self.save_btn = self._btn("Export Mesh (.dat)", '#062510')
        self.generate_btn = self._btn("Save Configuration (.json)", '#1b1f2a')

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
            ["By Node Count", "By Spacing"])
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
        tl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.tanh_n = mk_spin()
        self.tanh_intensity = mk_dspin(0.1, 10.0, 2.0, 2, 0.1)
        tl.addRow("Node Count:", self.tanh_n)
        tl.addRow("Intensity:", self.tanh_intensity)
        self.param_stack.addWidget(tw)

        # 2 — Cosine
        cw = QWidget()
        cfl = QFormLayout(cw)
        cfl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.cosine_n = mk_spin()
        cfl.addRow("Node Count:", self.cosine_n)
        self.param_stack.addWidget(cw)

        # 3 — Curvature
        kw = QWidget()
        kl = QFormLayout(kw)
        kl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.curv_n = mk_spin()
        self.curv_sens = mk_dspin(0.1, 10.0, 1.5, 2, 0.1)
        kl.addRow("Node Count:", self.curv_n)
        kl.addRow("Sensitivity:", self.curv_sens)
        self.param_stack.addWidget(kw)

        # 4 — Geometric
        gw = QWidget()
        gl2 = QFormLayout(gw)
        gl2.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
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

        # Align form layouts in distribution options
        for layout in [ul, tl, cfl, kl, gl2]:
            self._align_form_labels(layout)

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
        self.file_preview_btn.setVisible(True)
        self._file_seg_label.setText(
            f"Start Index: {start}    End Index: {end}")

    def show_curve_segment(self, seg):
        self._file_seg_label.setVisible(False)
        self._curve_group.setVisible(True)
        self.file_preview_btn.setVisible(False)

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

    def show_segment_props(self, visible: bool):
        if visible:
            self.sec_edge_parent.expand()
            self._sec_seg_props.expand()
        else:
            self._sec_seg_props.collapse()

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

    def _align_form_labels(self, layout: QFormLayout, width: int = 120):
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        for i in range(layout.rowCount()):
            label_item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if label_item:
                lbl = label_item.widget()
                if lbl:
                    lbl.setFixedWidth(width)
